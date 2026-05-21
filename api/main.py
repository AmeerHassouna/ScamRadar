from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, field_validator, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import asyncio
import sys
import re
import os

# Portable path — works on any machine / container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src._09_prediction_pipeline import load_pipeline, predict_message
from api.cache import get_prediction, set_prediction, cache_info
from api.translate import detect_and_translate
from config import (
    GOOGLE_SAFEBROWSING_API_KEY, VIRUSTOTAL_API_KEY,
    MIN_MESSAGE_LENGTH, MAX_MESSAGE_LENGTH,
)

# ── Constants ──────────────────────────────────────────────────────────────────
MAX_CONVERSATION_LENGTH   = 100_000    # 100 KB of plain text
MAX_FILE_BYTES            = 1_048_576  # 1 MB binary
ALLOWED_UPLOAD_EXTENSIONS = {'.txt', '.log', '.csv'}

# ── Pipeline state — populated by background task at startup ──────────────────
_pipe: dict | None = None

_RETRY_DELAYS = [5, 15, 30]  # seconds between load attempts


async def _load_pipeline_bg() -> None:
    global _pipe
    for attempt, delay in enumerate(_RETRY_DELAYS + [None], start=1):
        print(f'Loading ScamRadar+ pipeline (attempt {attempt}/{len(_RETRY_DELAYS) + 1})...')
        try:
            result = await asyncio.to_thread(load_pipeline)
            _pipe = {
                'model':      result[0],
                'tfidf':      result[1],
                'char_tfidf': result[2],
                'scaler':     result[3],
                'scam_index': result[4],
                'st_model':   result[5],
            }
            print('✅ Pipeline ready!')
            return
        except Exception as exc:
            print(f'❌ Pipeline load failed (attempt {attempt}): {exc}')
            if delay is not None:
                await asyncio.sleep(delay)
    print('❌ Pipeline failed to load after all attempts — service will return 503.')


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start loading in background — uvicorn serves requests immediately
    asyncio.create_task(_load_pipeline_bg())
    yield


# ── Rate limiter ───────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

app = FastAPI(title='ScamRadar+ API', lifespan=lifespan)
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
# Default to "*" so the public API works from any origin when ALLOWED_ORIGINS
# is not explicitly configured (e.g. on a fresh Render deployment).
# Set ALLOWED_ORIGINS=https://yourdomain.com to lock down to specific origins.
_raw_origins = os.environ.get('ALLOWED_ORIGINS', '*')
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(',') if o.strip()]
_allow_all = ALLOWED_ORIGINS == ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    # Allow all localhost ports for local development when not in wildcard mode
    allow_origin_regex=None if _allow_all else r'https?://localhost(:\d+)?',
    # allow_credentials is incompatible with allow_origins=["*"]
    allow_credentials=not _allow_all,
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['Content-Type', 'Authorization'],
)


# ── Request models ────────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator('text')
    @classmethod
    def validate_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_MESSAGE_LENGTH:
            raise ValueError(f'Message too short — minimum {MIN_MESSAGE_LENGTH} characters')
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


# ── Core prediction helper (cache-aware, non-blocking) ─────────────────────────

async def _predict(text: str, *, with_url_checks: bool = True) -> dict:
    if _pipe is None:
        raise HTTPException(status_code=503, detail='starting_up')

    cached = get_prediction(text)
    if cached is not None:
        return cached

    # Translate non-English input before model inference (non-blocking)
    translated_text, detected_lang = await asyncio.to_thread(detect_and_translate, text)

    result = await asyncio.to_thread(
        predict_message,
        translated_text,
        _pipe['model'], _pipe['tfidf'], _pipe['char_tfidf'],
        _pipe['scaler'], _pipe['scam_index'], _pipe['st_model'],
        vt_api_key=VIRUSTOTAL_API_KEY  if with_url_checks else None,
        gsb_api_key=GOOGLE_SAFEBROWSING_API_KEY if with_url_checks else None,
    )

    if detected_lang:
        result['detected_language'] = detected_lang
        result['was_translated'] = True

    set_prediction(text, result)
    return result


# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_conversation(text: str) -> list:
    messages = []
    whatsapp_pattern = r'\[(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*([^:]+):\s*(.+)'
    whatsapp_alt     = r'(\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.+)'

    matches = re.findall(whatsapp_pattern, text, re.MULTILINE)
    if not matches:
        matches = re.findall(whatsapp_alt, text, re.MULTILINE)

    if matches:
        for ts, sender, msg in matches:
            messages.append({'timestamp': ts.strip(), 'sender': sender.strip(), 'text': msg.strip()})
    else:
        for line in text.split('\n'):
            line = line.strip()
            if len(line) > 10:
                messages.append({'timestamp': '', 'sender': 'Unknown', 'text': line})

    return messages


# ── Prediction endpoints ───────────────────────────────────────────────────────

@app.post('/predict')
@limiter.limit("30/minute")
async def predict(request: Request, body: MessageRequest):
    return await _predict(body.text)


@app.post('/analyze-conversation')
@limiter.limit("20/minute")
async def analyze_conversation(request: Request, body: ConversationRequest):
    messages = parse_conversation(body.text)
    if not messages:
        raise HTTPException(status_code=400, detail='No messages found in conversation')

    texts = [m['text'] for m in messages if len(m['text'].strip()) > 5]
    if not texts:
        raise HTTPException(status_code=400, detail='No valid messages found in conversation')

    # ── Method 1: full conversation (with URL checks) ─────────────────────
    full_text = ' '.join(texts)
    full_result_task = _predict(full_text, with_url_checks=True)

    # ── Method 2: sliding windows — fan out concurrently ─────────────────
    window_size = min(5, len(texts))
    window_inputs = []
    for i in range(0, len(texts), max(1, window_size // 2)):
        window_text = ' '.join(texts[i:i + window_size])
        if len(window_text.strip()) >= 20:
            window_inputs.append((i, window_text))

    window_tasks = [_predict(wt, with_url_checks=False) for _, wt in window_inputs]

    # ── Method 3: final 30% of messages ───────────────────────────────────
    final_start = max(0, int(len(texts) * 0.7))
    final_text  = ' '.join(texts[final_start:])
    final_task  = _predict(final_text, with_url_checks=True) if len(final_text.strip()) > 20 else None

    all_tasks = [full_result_task] + window_tasks + ([final_task] if final_task else [])
    all_results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # Surface any exception (including 503 if pipeline not ready yet)
    for r in all_results:
        if isinstance(r, Exception):
            raise r

    full_result    = all_results[0]
    window_results = all_results[1:1 + len(window_tasks)]
    final_result   = all_results[1 + len(window_tasks)] if final_task else None

    full_score = full_result['confidence'] / 100

    window_scores = [
        wr['confidence'] / 100 * (1 + (idx / len(texts)))
        for (idx, _), wr in zip(window_inputs, window_results)
    ]
    max_window_score = min(max(window_scores), 1.0) if window_scores else 0.0

    final_score = (final_result['confidence'] / 100) if final_result else full_score

    risk_score = round(
        (full_score * 0.40 + max_window_score * 0.35 + final_score * 0.25) * 100, 1
    )

    if risk_score >= 43:
        overall_verdict = 'SCAM'
    elif risk_score >= 30:
        overall_verdict = 'SUSPICIOUS'
    else:
        overall_verdict = 'LEGIT'

    return {
        'overall_verdict':         overall_verdict,
        'risk_score':              risk_score,
        'total_messages':          len(messages),
        'messages_analyzed':       len(texts),
        'full_conversation_score': round(full_score * 100, 1),
        'window_analysis_score':   round(max_window_score * 100, 1),
        'final_messages_score':    round(final_score * 100, 1),
        'why_flagged':             full_result.get('why_flagged', ''),
        'urls_found':              full_result.get('urls_found', []),
        'vt_malicious':            full_result.get('vt_malicious', 0),
        'gsb_flagged':             full_result.get('gsb_flagged', False),
        'tone_urgency':            full_result.get('tone_urgency', 0),
        'tone_fear':               full_result.get('tone_fear', 0),
        'tone_reward':             full_result.get('tone_reward', 0),
        'tone_threat':             full_result.get('tone_threat', 0),
        'scam_type':               full_result.get('scam_type', 'general_spam'),
    }


@app.post('/analyze-conversation-file')
@limiter.limit("10/minute")
async def analyze_conversation_file(request: Request, file: UploadFile = File(...)):
    if not file.content_type:
        raise HTTPException(status_code=400, detail='Content-Type header is required')
    if not file.content_type.startswith('text/'):
        raise HTTPException(status_code=415, detail='Only plain-text files are accepted')

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


# ── Auth stub ─────────────────────────────────────────────────────────────────

@app.post('/login')
@limiter.limit("5/15minutes")
async def login(request: Request):
    return JSONResponse(status_code=501, content={'detail': 'Auth not yet implemented.'})


# ── Utility endpoints ──────────────────────────────────────────────────────────

@app.get('/health')
@limiter.limit("120/minute")
async def health(request: Request):
    if _pipe is None:
        return JSONResponse(status_code=200, content={'status': 'loading'})
    return {'status': 'ready', 'model': 'ScamRadar+ v5', **cache_info()}


@app.get('/warmup')
@limiter.limit("30/minute")
async def warmup(request: Request):
    """Fires a lightweight prediction to ensure all model code paths are hot."""
    await _predict("URGENT: Your account has been suspended. Verify now at http://secure-login.tk")
    return {'status': 'warm'}


@app.get('/stats')
@limiter.limit("30/minute")
async def stats(request: Request):
    return {
        'total_messages': 46360,
        'scam_messages':  22164,
        'legit_messages': 24196,
        'channels':       4,
        'accuracy':       97.39,
        'precision':      97.47,
        'recall':         97.12,
        'f1':             97.30,
        'auc':            99.58,
        'scam_types':     17,
        'features':       25,
        **cache_info(),
    }
