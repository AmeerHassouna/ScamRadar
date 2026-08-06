// ── Toolbar popup — API health indicator ─────────────────────────────────────
// The popup itself never talks to the API directly. It asks the background
// service worker for the health status, so all network activity goes through
// a single path with the same host_permissions and error handling.

const statusEl     = document.getElementById('status');
const statusTextEl = document.getElementById('statusText');

function setStatus(state, text) {
  statusEl.dataset.state = state;   // 'ok' | 'down' | 'warn' | ''
  statusTextEl.textContent = text;
}

async function refresh() {
  setStatus('', 'Checking API…');
  try {
    const res = await chrome.runtime.sendMessage({ type: 'SCAMRADAR_HEALTH' });
    if (!res?.ok) {
      setStatus('down', 'API offline — start the local server');
      return;
    }
    const modelStatus = res.body?.status;
    if (modelStatus === 'ready') {
      setStatus('ok', 'API ready');
    } else if (modelStatus === 'loading') {
      setStatus('warn', 'Model loading — try again in a moment');
    } else {
      setStatus('ok', 'API online');
    }
  } catch {
    setStatus('down', 'Could not reach background worker');
  }
}

refresh();
