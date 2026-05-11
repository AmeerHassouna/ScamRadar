from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import sys
import re
import os

# Portable path — works on any machine / container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src._09_prediction_pipeline import load_pipeline, predict_message
from config import (
    GOOGLE_SAFEBROWSING_API_KEY, VIRUSTOTAL_API_KEY,
    MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH,
)

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_CONVERSATION_LENGTH = 100_000    # 100 KB of plain text
MAX_FILE_BYTES          = 1_048_576  # 1 MB binary
ALLOWED_UPLOAD_EXTENSIONS = {'.txt', '.log', '.csv'}

# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title='ScamRadar+ API')
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers middleware ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ───────────────────────────────────────────────────────────────────────
_raw_origins = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000')
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r'https?://localhost(:\d+)?',  # any localhost port for dev
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization'],
)

# Load actual trained pipeline once at startup
print('Loading ScamRadar+ pipeline...')
model, tfidf, char_tfidf, scaler, scam_index, st_model = load_pipeline()
print('✅ Pipeline loaded!')


# ── Request models with validation ────────────────────────────────────────────

class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_MESSAGE_LENGTH:
            raise ValueError(
                f'Message too short — minimum {MIN_MESSAGE_LENGTH} characters'
            )
        return v


class ConversationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_CONVERSATION_LENGTH)

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Conversation text cannot be empty')
        return v


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_conversation(text: str) -> list:
    messages = []

    # WhatsApp format: [DD/MM/YYYY, HH:MM:SS] Sender: Message
    whatsapp_pattern = r'\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*([^:]+):\s*(.+)'
    # WhatsApp alternative: DD/MM/YYYY, HH:MM - Sender: Message
    whatsapp_alt = r'(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.+)'

    matches = re.findall(whatsapp_pattern, text, re.MULTILINE)
    if not matches:
        matches = re.findall(whatsapp_alt, text, re.MULTILINE)

    if matches:
        for match in matches:
            timestamp, sender, message = match
            messages.append({
                'timestamp': timestamp.strip(),
                'sender': sender.strip(),
                'text': message.strip(),
            })
    else:
        # Plain text — treat each non-empty line as a message
        lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 10]
        for line in lines:
            messages.append({'timestamp': '', 'sender': 'Unknown', 'text': line})

    return messages


# ── Prediction endpoints ───────────────────────────────────────────────────────

@app.post('/predict')
@limiter.limit("30/minute")
async def predict(request: Request, body: MessageRequest):
    result = predict_message(
        body.text,
        model, tfidf, char_tfidf, scaler, scam_index, st_model,
        vt_api_key=VIRUSTOTAL_API_KEY,
        gsb_api_key=GOOGLE_SAFEBROWSING_API_KEY,
    )
    return result


@app.post('/analyze-conversation')
@limiter.limit("20/minute")
async def analyze_conversation(request: Request, body: ConversationRequest):
    messages = parse_conversation(body.text)

    if not messages:
        raise HTTPException(status_code=400, detail='No messages found in conversation')

    texts = [m['text'] for m in messages if len(m['text'].strip()) > 5]

    if not texts:
        raise HTTPException(status_code=400, detail='No valid messages found in conversation')

    # Method 1: Full conversation as one text
    full_text = ' '.join(texts)
    full_result = predict_message(
        full_text, model, tfidf, char_tfidf, scaler, scam_index, st_model,
        vt_api_key=VIRUSTOTAL_API_KEY,
        gsb_api_key=GOOGLE_SAFEBROWSING_API_KEY,
    )
    full_score = full_result['confidence'] / 100

    # Method 2: Sliding window (windows of 5 messages)
    window_size = min(5, len(texts))
    window_scores = []
    for i in range(0, len(texts), max(1, window_size // 2)):
        window = texts[i:i + window_size]
        window_text = ' '.join(window)
        if len(window_text.strip()) < 20:
            continue
        window_result = predict_message(
            window_text, model, tfidf, char_tfidf, scaler, scam_index, st_model
        )
        position_weight = 1 + (i / len(texts))
        window_scores.append(window_result['confidence'] / 100 * position_weight)

    max_window_score = min(max(window_scores), 1.0) if window_scores else 0.0

    # Method 3: Final messages focus (last 30%)
    final_start = max(0, int(len(texts) * 0.7))
    final_text = ' '.join(texts[final_start:])

    if len(final_text.strip()) > 20:
        final_result = predict_message(
            final_text, model, tfidf, char_tfidf, scaler, scam_index, st_model,
            vt_api_key=VIRUSTOTAL_API_KEY,
            gsb_api_key=GOOGLE_SAFEBROWSING_API_KEY,
        )
        final_score = final_result['confidence'] / 100
    else:
        final_score = full_score

    combined_score = (
        full_score * 0.40 +
        max_window_score * 0.35 +
        final_score * 0.25
    )
    risk_score = round(combined_score * 100, 1)

    if risk_score >= 43:
        overall_verdict = 'SCAM'
    elif risk_score >= 30:
        overall_verdict = 'SUSPICIOUS'
    else:
        overall_verdict = 'LEGIT'

    return {
        'overall_verdict': overall_verdict,
        'risk_score': risk_score,
        'total_messages': len(messages),
        'messages_analyzed': len(texts),
        'full_conversation_score': round(full_score * 100, 1),
        'window_analysis_score': round(max_window_score * 100, 1),
        'final_messages_score': round(final_score * 100, 1),
        'why_flagged': full_result.get('why_flagged', ''),
        'urls_found': full_result.get('urls_found', []),
        'vt_malicious': full_result.get('vt_malicious', 0),
        'gsb_flagged': full_result.get('gsb_flagged', False),
        'tone_urgency': full_result.get('tone_urgency', 0),
        'tone_fear': full_result.get('tone_fear', 0),
        'tone_reward': full_result.get('tone_reward', 0),
        'tone_threat': full_result.get('tone_threat', 0),
        'scam_type': full_result.get('scam_type', 'general_spam'),
    }


@app.post('/analyze-conversation-file')
@limiter.limit("10/minute")
async def analyze_conversation_file(request: Request, file: UploadFile = File(...)):
    # Require explicit content-type — reject missing or non-text
    if not file.content_type:
        raise HTTPException(status_code=400, detail='Content-Type header is required')
    if not file.content_type.startswith('text/'):
        raise HTTPException(status_code=415, detail='Only plain-text files are accepted')

    # Validate extension
    _, ext = os.path.splitext(file.filename or '')
    if ext.lower() not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f'File extension not allowed — accepted: {", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}',
        )

    content = await file.read()

    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail='File too large — maximum 1 MB')

    text = content.decode('utf-8', errors='ignore').strip()

    if not text:
        raise HTTPException(status_code=400, detail='File is empty or contains no readable text')

    if len(text) > MAX_CONVERSATION_LENGTH:
        raise HTTPException(status_code=413, detail='Decoded text too long — maximum 100,000 characters')

    inner = ConversationRequest(text=text)
    return await analyze_conversation.__wrapped__(request, inner)


# ── Login route (5 attempts / 15 min per IP) ──────────────────────────────────

@app.post('/login')
@limiter.limit("5/15minutes")
async def login(request: Request):
    return JSONResponse(
        status_code=501,
        content={'detail': 'Auth not yet implemented.'},
    )


# ── Utility endpoints ──────────────────────────────────────────────────────────

@app.get('/health')
@limiter.limit("120/minute")
async def health(request: Request):
    return {'status': 'ok', 'model': 'ScamRadar+ v5'}


@app.get('/stats')
@limiter.limit("30/minute")
async def stats(request: Request):
    return {
        'total_messages': 45851,
        'scam_messages': 21955,
        'legit_messages': 23896,
        'channels': 4,
        'accuracy': 99.19,
        'precision': 97.97,
        'recall': 91.5,
        'f1': 94.62,
        'auc': 98.12,
        'scam_types': 10,
        'features': 25,
    }
