// ── ScamRadar+ — background service worker ────────────────────────────────────
//
// Responsibilities:
//   1. Register the "Analyze with ScamRadar+" context-menu entry (visible only
//      when text is selected on a page).
//   2. On click, POST the selected text to the local ScamRadar+ API.
//   3. Inject the overlay content script on demand (via activeTab) and forward
//      loading / result / error states to it.
//
// Privacy-first design notes:
//   - No content script matches in the manifest. Nothing is injected until the
//     user explicitly picks "Analyze with ScamRadar+".
//   - We only ever send the exact text the user highlighted — never the URL,
//     the page contents, referrer, or any other page metadata.
//   - `activeTab` grants us temporary scripting rights only for the tab where
//     the user clicked, and only for that click.
//
// Future expansion:
//   Site-specific automatic adapters (Gmail, LinkedIn, etc.) would hook in
//   here as additional context-menu entries or content scripts gated behind
//   an explicit user opt-in. They are intentionally NOT implemented in this
//   prototype.

const API_BASE           = 'http://127.0.0.1:8000';
const PREDICT_ENDPOINT   = `${API_BASE}/predict`;
const HEALTH_ENDPOINT    = `${API_BASE}/health`;
const CONTEXT_MENU_ID    = 'scamradar-analyze-selection';
const REQUEST_TIMEOUT_MS = 20_000;

// Server-side validation constants — mirror api/main.py so we can surface a
// friendlier error before hitting the network.
const MIN_MESSAGE_LENGTH = 20;
const MAX_MESSAGE_LENGTH = 5_000;


// ── Context menu lifecycle ────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id:       CONTEXT_MENU_ID,
    title:    'Analyze with ScamRadar+',
    contexts: ['selection'],   // menu only appears when text is highlighted
  });
});


// ── User-triggered analysis flow ──────────────────────────────────────────────

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== CONTEXT_MENU_ID) return;
  if (!tab?.id) return;

  const rawText = (info.selectionText || '').trim();

  // Local validation — matches the API's own bounds so we don't waste a round-
  // trip on empty / too-short / too-long selections.
  if (!rawText) {
    await pushState(tab.id, {
      status:  'error',
      title:   'Nothing selected',
      message: 'Highlight the text you want to analyse, then right-click and pick "Analyze with ScamRadar+".',
    });
    return;
  }

  if (rawText.length < MIN_MESSAGE_LENGTH) {
    await pushState(tab.id, {
      status:  'error',
      title:   'Selection too short',
      message: `Please highlight at least ${MIN_MESSAGE_LENGTH} characters — currently ${rawText.length}.`,
    });
    return;
  }

  // Truncate rather than error on over-length selections. Users often highlight
  // an entire email including footers; keeping the head is more useful than
  // refusing outright.
  const text = rawText.length > MAX_MESSAGE_LENGTH
    ? rawText.slice(0, MAX_MESSAGE_LENGTH)
    : rawText;
  const truncated = text.length !== rawText.length;

  await pushState(tab.id, { status: 'loading', excerpt: excerptOf(text) });

  try {
    const result = await callPredict(text);
    await pushState(tab.id, {
      status:    'result',
      result,
      excerpt:   excerptOf(text),
      truncated,
    });
  } catch (err) {
    await pushState(tab.id, {
      status:  'error',
      title:   'Analysis failed',
      message: friendlyError(err),
    });
  }
});


// ── API client ───────────────────────────────────────────────────────────────

async function callPredict(text) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(PREDICT_ENDPOINT, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body:    JSON.stringify({ text }),
      signal:  controller.signal,
    });

    if (!res.ok) {
      // Surface the FastAPI `detail` field when present for better error UX.
      let detail = '';
      try {
        const body = await res.json();
        detail = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body?.detail ?? '');
      } catch {
        detail = await res.text().catch(() => '');
      }
      const suffix = detail ? ` — ${detail.slice(0, 240)}` : '';
      const err = new Error(`API responded ${res.status}${suffix}`);
      err.status = res.status;
      throw err;
    }

    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}


// ── Health probe (used by the toolbar popup) ─────────────────────────────────

async function checkHealth() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3_000);
  try {
    const res = await fetch(HEALTH_ENDPOINT, { signal: controller.signal });
    if (!res.ok) return { ok: false, status: res.status };
    const body = await res.json().catch(() => ({}));
    return { ok: true, status: res.status, body };
  } catch (err) {
    return { ok: false, error: err?.message || 'unreachable' };
  } finally {
    clearTimeout(timer);
  }
}

// The popup asks the background worker for API health rather than fetching
// itself — this keeps every network call routed through the same code path
// with the same host_permissions and error handling.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'SCAMRADAR_HEALTH') {
    checkHealth().then(sendResponse);
    return true;   // keep the message channel open for async response
  }
});


// ── Overlay injection + state push ────────────────────────────────────────────

async function pushState(tabId, payload) {
  // `activeTab` gives us temporary permission to inject into the tab the user
  // just interacted with. If injection fails (chrome://, PDF viewer, web
  // store, etc.), fall back to a browser notification so the user isn't left
  // wondering what happened.
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files:  ['content.js'],
    });
    await chrome.tabs.sendMessage(tabId, { type: 'SCAMRADAR_STATE', payload });
  } catch (err) {
    console.warn('[ScamRadar+] overlay injection failed:', err);
  }
}


// ── Helpers ───────────────────────────────────────────────────────────────────

function excerptOf(text, limit = 180) {
  const collapsed = text.replace(/\s+/g, ' ').trim();
  return collapsed.length <= limit ? collapsed : `${collapsed.slice(0, limit - 1)}…`;
}

function friendlyError(err) {
  if (err?.name === 'AbortError') {
    return 'The request took longer than 20 seconds. The API may be starting up — please try again in a moment.';
  }
  const msg = err?.message || '';
  if (msg.includes('Failed to fetch') || msg.includes('NetworkError') || msg.includes('ERR_CONNECTION')) {
    return 'Could not reach the ScamRadar+ API at 127.0.0.1:8000. Make sure the local server is running.';
  }
  if (err?.status === 400) {
    return msg.replace(/^API responded 400 — /, '');
  }
  if (err?.status === 429) {
    return 'You are sending requests too quickly. Please wait a moment and try again.';
  }
  if (err?.status === 503) {
    return 'The model is still starting up. Please try again in a few seconds.';
  }
  return msg || 'Unexpected error. Please try again.';
}
