// ── ScamRadar+ — verdict-first overlay ────────────────────────────────────────
//
// Product-design brief: the user must answer "can I trust this?" in under a
// second. The overlay shows exactly four things, in this order:
//
//     1. A large centred shield icon, tinted by verdict.
//     2. A verdict label ("LOOKS SAFE" / "USE CAUTION" / "SCAM DETECTED" …).
//     3. One sentence of context.
//     4. A short list of 2–4 supporting reasons (and a scam type, if any).
//
// No percentages. No selected-text preview. No prototype/dev chrome. Confidence
// still exists inside the API response; the UI just translates it into a human
// verdict via the buckets defined below.
//
// Rendered inside a closed Shadow DOM so nothing from the host page can leak
// in and nothing from the overlay can leak out.

(() => {
  if (window.__scamRadarPlusLoaded) return;
  window.__scamRadarPlusLoaded = true;

  const HOST_ID = '__scamradar_plus_host';

  // ── Verdict buckets ─────────────────────────────────────────────────────
  // Probability of scam → human verdict. Mirrors the product spec exactly.
  const VERDICT_BUCKETS = [
    { max: 0.20, key: 'SAFE',      label: 'LOOKS SAFE',      accent: '#22C55E',
      caption: 'No suspicious indicators were detected.',   icon: 'shield-check' },
    { max: 0.45, key: 'PROB_SAFE', label: 'PROBABLY SAFE',   accent: '#65A30D',
      caption: 'Nothing obviously suspicious — stay alert.', icon: 'shield-check' },
    { max: 0.60, key: 'CAUTION',   label: 'USE CAUTION',     accent: '#F59E0B',
      caption: 'Some warning signs are present. Verify before acting.', icon: 'shield-alert' },
    { max: 0.85, key: 'LIKELY',    label: 'LIKELY SCAM',     accent: '#EF4444',
      caption: 'Multiple signs suggest this is a scam.',    icon: 'shield-x' },
    { max: 1.01, key: 'SCAM',      label: 'SCAM DETECTED',   accent: '#DC2626',
      caption: 'Strong evidence that this is a scam.',      icon: 'shield-x' },
  ];

  function verdictFor(result) {
    if (result?.verdict === 'TOO_SHORT') {
      return { key: 'SHORT', label: 'NOT ENOUGH TEXT', accent: '#94A3B8',
               caption: 'Highlight a longer passage to get an accurate reading.',
               icon: 'shield-question' };
    }
    const conf = Number(result?.confidence);
    const p    = Number.isFinite(conf) ? Math.max(0, Math.min(100, conf)) / 100 : 0.5;
    return VERDICT_BUCKETS.find(b => p < b.max) || VERDICT_BUCKETS[VERDICT_BUCKETS.length - 1];
  }

  const isPositiveVerdict = (v) => v.key === 'SAFE' || v.key === 'PROB_SAFE';

  // ── Reason synthesis ────────────────────────────────────────────────────
  // API returns `why_flagged` (pipe-delimited) only for scam-leaning verdicts.
  // For safe verdicts we synthesize positive reasons from the ABSENCE of the
  // signals ScamRadar+ tracks. Cap at 4.
  function reasonsFor(result, verdict) {
    if (isPositiveVerdict(verdict)) {
      const out = [];
      const tone = ['tone_urgency', 'tone_fear', 'tone_reward', 'tone_threat']
        .every(k => (Number(result?.[k]) || 0) <= 1);
      if (tone) out.push('No pressure, urgency, or fear tactics');
      const urls = Array.isArray(result?.urls_found) ? result.urls_found : [];
      if (!urls.length)            out.push('No suspicious links found');
      else if (!result?.gsb_flagged) out.push('Links match known-safe domains');
      if ((Number(result?.scam_phrase_score) || 0) < 0.2) out.push('No known scam phrasing detected');
      if ((Number(result?.sender_impersonation) || 0) < 0.2) out.push('No brand-impersonation signals');
      if (!out.length) out.push('Language matches legitimate communication');
      return out.slice(0, 4);
    }
    const raw = typeof result?.why_flagged === 'string' ? result.why_flagged : '';
    return raw.split('|').map(s => s.trim()).filter(Boolean).slice(0, 4);
  }

  function scamTypeFor(result) {
    const t = result?.scam_type;
    if (!t || t === 'general_spam') return null;
    return String(t).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  // ── Link findings (Google Safe Browsing) ────────────────────────────────
  // Emitted only when the API actually contacted GSB (`gsb_attempted: true`)
  // and at least one URL was present in the message.
  function linkFindings(result) {
    const urls = Array.isArray(result?.urls_found) ? result.urls_found : [];
    if (!urls.length || !result?.gsb_attempted) return null;
    const dangerous = !!result?.gsb_flagged;
    return {
      urls:      urls.slice(0, 3).map(hostOf),
      remaining: Math.max(0, urls.length - 3),
      dangerous,
      threat:    dangerous ? prettyThreat(result?.gsb_threat_type) : null,
    };
  }

  const THREAT_LABELS = {
    SOCIAL_ENGINEERING:              'phishing',
    MALWARE:                         'malware',
    UNWANTED_SOFTWARE:               'unwanted software',
    POTENTIALLY_HARMFUL_APPLICATION: 'a harmful app',
  };
  function prettyThreat(t) {
    if (!t) return null;
    return THREAT_LABELS[t] || String(t).toLowerCase().replace(/_/g, ' ');
  }

  function hostOf(u) {
    try {
      return new URL(String(u).startsWith('http') ? u : `https://${u}`)
        .hostname.replace(/^www\./, '');
    } catch { return String(u); }
  }

  // ── Shadow-DOM host ─────────────────────────────────────────────────────
  const host = document.createElement('div');
  host.id = HOST_ID;
  Object.assign(host.style, {
    all: 'initial', position: 'fixed', top: '0', right: '0',
    width: '0', height: '0', zIndex: '2147483647',
  });
  document.documentElement.appendChild(host);

  const shadow = host.attachShadow({ mode: 'closed' });
  shadow.innerHTML = `<style>${styleSheet()}</style><div class="sr-root" role="dialog" aria-live="polite" aria-label="ScamRadar+ analysis"></div>`;
  const root = shadow.querySelector('.sr-root');

  // ── Message handler ─────────────────────────────────────────────────────
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type !== 'SCAMRADAR_STATE') return;
    const p = msg.payload || {};
    if      (p.status === 'loading') render(loadingCard());
    else if (p.status === 'result')  render(resultCard(p.result || {}));
    else if (p.status === 'error')   render(errorCard(p));
  });

  function render(html) {
    root.innerHTML = html;
    const close = root.querySelector('[data-sr-close]');
    if (close) {
      close.addEventListener('click', dismiss);
      requestAnimationFrame(() => close.focus?.());
    }
    // Escape key closes the card.
    document.addEventListener('keydown', escHandler, { once: true });
  }

  function dismiss() {
    const card = root.querySelector('.sr-card');
    if (!card) { root.innerHTML = ''; return; }
    card.classList.add('sr-out');
    setTimeout(() => { root.innerHTML = ''; }, 160);
  }

  function escHandler(e) {
    if (e.key === 'Escape') dismiss();
    else document.addEventListener('keydown', escHandler, { once: true });
  }

  // ── Card templates ──────────────────────────────────────────────────────

  function shellHeader() {
    return `
      <header class="sr-head">
        <div class="sr-brand">
          ${brandMark()}
          <span>ScamRadar<span class="sr-brand-plus">+</span></span>
        </div>
        <button class="sr-close" data-sr-close aria-label="Close">${iconClose()}</button>
      </header>
    `;
  }

  function loadingCard() {
    return `
      <div class="sr-card">
        ${shellHeader()}
        <div class="sr-body sr-loading">
          <div class="sr-spinner" aria-hidden="true"></div>
          <p>Analysing…</p>
        </div>
      </div>
    `;
  }

  function errorCard(p) {
    return `
      <div class="sr-card" style="--sr-accent:#F87171;">
        ${shellHeader()}
        <div class="sr-body sr-error">
          <div class="sr-hero-icon">${icon('shield-alert')}</div>
          <h1 class="sr-verdict-label">${escapeHtml((p.title || 'SOMETHING WENT WRONG').toUpperCase())}</h1>
          <p class="sr-caption">${escapeHtml(p.message || 'Please try again.')}</p>
        </div>
      </div>
    `;
  }

  function resultCard(result) {
    const v        = verdictFor(result);
    const reasons  = reasonsFor(result, v);
    const scamType = scamTypeFor(result);
    const links    = linkFindings(result);
    const positive = isPositiveVerdict(v);

    return `
      <div class="sr-card" style="--sr-accent:${v.accent};">
        ${shellHeader()}

        <div class="sr-body">
          <div class="sr-hero-icon">
            <div class="sr-hero-halo" aria-hidden="true"></div>
            ${icon(v.icon)}
          </div>

          <h1 class="sr-verdict-label">${escapeHtml(v.label)}</h1>
          <p class="sr-caption">${escapeHtml(v.caption)}</p>

          ${reasons.length ? `
            <div class="sr-divider"><span>Why?</span></div>
            <ul class="sr-reasons">
              ${reasons.map((r, i) => `
                <li style="animation-delay:${140 + i * 60}ms">
                  <span class="sr-bullet" aria-hidden="true">${positive ? iconCheck() : iconDot()}</span>
                  <span class="sr-reason-text">${escapeHtml(r)}</span>
                </li>
              `).join('')}
            </ul>
          ` : ''}

          ${links ? `
            <div class="sr-divider"><span>${links.urls.length === 1 ? 'Link' : 'Links'}</span></div>
            <ul class="sr-links">
              ${links.urls.map(host => `
                <li>
                  <span class="sr-link-host">${escapeHtml(host)}</span>
                  <span class="sr-link-chip sr-link-${links.dangerous ? 'danger' : 'safe'}">
                    ${links.dangerous ? 'Dangerous' : 'Safe'}
                  </span>
                </li>
              `).join('')}
              ${links.remaining ? `
                <li class="sr-link-more">and ${links.remaining} more</li>
              ` : ''}
            </ul>
            <p class="sr-link-note">
              ${links.dangerous
                ? `Flagged as ${escapeHtml(links.threat || 'unsafe')} by Google Safe Browsing.`
                : 'Verified by Google Safe Browsing.'}
            </p>
          ` : ''}

          ${scamType ? `
            <div class="sr-divider"><span>Type</span></div>
            <p class="sr-type">${escapeHtml(scamType)}</p>
          ` : ''}
        </div>
      </div>
    `;
  }

  // ── SVG icons (Lucide-derived, consistent 24×24 stroke geometry) ────────

  const SHIELD_PATH = 'M12 2 L20 5 V12 C20 17.5 16 21.5 12 22.5 C8 21.5 4 17.5 4 12 V5 Z';

  function icon(name) {
    const inside = {
      'shield-check':    '<path d="M8.5 12.5 L11 15 L15.5 10" stroke-linecap="round" stroke-linejoin="round"/>',
      'shield-alert':    '<path d="M12 8 V13" stroke-linecap="round"/><circle cx="12" cy="16.2" r="0.9" fill="currentColor" stroke="none"/>',
      'shield-x':        '<path d="M9 10 L15 15 M15 10 L9 15" stroke-linecap="round"/>',
      'shield-question': '<path d="M10.2 10.5 C10.2 9.2 11 8.4 12 8.4 C13 8.4 13.9 9.2 13.9 10.2 C13.9 11.2 12.7 11.4 12 12.5 L12 13.5" stroke-linecap="round"/><circle cx="12" cy="16.2" r="0.9" fill="currentColor" stroke="none"/>',
    }[name] || '';
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="${SHIELD_PATH}" stroke-linejoin="round"/>${inside}</svg>`;
  }

  function iconCheck() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.5 L10 17.5 L19 6.5"/></svg>`;
  }
  function iconDot() {
    return `<svg viewBox="0 0 8 8" aria-hidden="true"><circle cx="4" cy="4" r="3" fill="currentColor"/></svg>`;
  }
  function iconClose() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true"><path d="M6 6 L18 18 M18 6 L6 18"/></svg>`;
  }
  function brandMark() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="${SHIELD_PATH}" stroke-linejoin="round"/></svg>`;
  }

  // ── Helpers ─────────────────────────────────────────────────────────────
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // ── Stylesheet (self-contained inside the Shadow DOM) ───────────────────
  function styleSheet() {
    return `
      :host, .sr-root { all: initial; }
      .sr-root {
        position: fixed; top: 20px; right: 20px;
        font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display',
                     'Segoe UI', 'Inter', Roboto, 'Helvetica Neue', Arial, sans-serif;
        color: #F5F7FA;
        pointer-events: none;
      }

      .sr-card {
        pointer-events: auto;
        width: 340px;
        max-height: calc(100vh - 40px);
        overflow-y: auto;
        background: #0B0D11;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 20px;
        box-shadow:
          0 24px 60px rgba(0, 0, 0, 0.55),
          0 4px 12px rgba(0, 0, 0, 0.35),
          inset 0 1px 0 rgba(255, 255, 255, 0.04);
        animation: sr-in 280ms cubic-bezier(0.22, 1, 0.36, 1);
      }
      .sr-card.sr-out { animation: sr-out 160ms ease forwards; }
      .sr-card::-webkit-scrollbar { width: 6px; }
      .sr-card::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 3px; }

      @keyframes sr-in  { from { opacity: 0; transform: translateY(-8px) scale(0.98); }
                          to   { opacity: 1; transform: translateY(0)    scale(1);    } }
      @keyframes sr-out { to   { opacity: 0; transform: translateY(-4px) scale(0.98); } }

      /* ── Header ───────────────────────────────────────────────────── */
      .sr-head {
        display: flex; align-items: center; justify-content: space-between;
        padding: 14px 16px 0;
      }
      .sr-brand {
        display: flex; align-items: center; gap: 7px;
        font-size: 12px; font-weight: 600;
        color: rgba(245, 247, 250, 0.55);
        letter-spacing: -0.005em;
      }
      .sr-brand svg { width: 14px; height: 14px; color: rgba(245, 247, 250, 0.6); }
      .sr-brand-plus { color: var(--sr-accent, #22C55E); margin-left: 1px; }

      .sr-close {
        appearance: none; background: transparent; border: 0;
        color: rgba(245, 247, 250, 0.5);
        width: 26px; height: 26px; border-radius: 8px;
        cursor: pointer; padding: 0;
        display: flex; align-items: center; justify-content: center;
        transition: background 140ms ease, color 140ms ease;
      }
      .sr-close svg { width: 14px; height: 14px; }
      .sr-close:hover, .sr-close:focus-visible {
        background: rgba(255, 255, 255, 0.06);
        color: #FFF; outline: none;
      }

      /* ── Body ─────────────────────────────────────────────────────── */
      .sr-body {
        padding: 24px 28px 26px;
        display: flex; flex-direction: column; align-items: center;
        text-align: center;
      }

      .sr-hero-icon {
        position: relative;
        width: 76px; height: 76px;
        display: flex; align-items: center; justify-content: center;
        color: var(--sr-accent, #94A3B8);
        margin-bottom: 20px;
        animation: sr-icon-in 480ms cubic-bezier(0.22, 1.4, 0.36, 1) both;
        animation-delay: 60ms;
      }
      .sr-hero-icon svg { width: 100%; height: 100%; }
      .sr-hero-halo {
        position: absolute; inset: -10px;
        border-radius: 50%;
        background: radial-gradient(circle,
          color-mix(in srgb, var(--sr-accent, #94A3B8) 22%, transparent) 0%,
          color-mix(in srgb, var(--sr-accent, #94A3B8) 0%, transparent) 68%);
        filter: blur(6px);
        z-index: -1;
      }

      @keyframes sr-icon-in {
        0%   { opacity: 0; transform: scale(0.72); }
        60%  { opacity: 1; transform: scale(1.05); }
        100% { opacity: 1; transform: scale(1);    }
      }

      .sr-verdict-label {
        margin: 0;
        font-size: 22px;
        font-weight: 700;
        letter-spacing: 0.12em;
        color: var(--sr-accent, #F5F7FA);
        animation: sr-rise 380ms cubic-bezier(0.22, 1, 0.36, 1) both;
        animation-delay: 140ms;
        text-shadow: 0 0 20px color-mix(in srgb, var(--sr-accent, #94A3B8) 22%, transparent);
      }
      .sr-caption {
        margin: 10px 0 0;
        max-width: 240px;
        font-size: 13px;
        line-height: 1.55;
        color: rgba(245, 247, 250, 0.62);
        animation: sr-rise 380ms cubic-bezier(0.22, 1, 0.36, 1) both;
        animation-delay: 200ms;
      }
      @keyframes sr-rise {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0);   }
      }

      /* ── Divider with label ───────────────────────────────────────── */
      .sr-divider {
        width: 100%;
        display: flex; align-items: center; gap: 12px;
        margin: 24px 0 14px;
        color: rgba(245, 247, 250, 0.32);
        font-size: 10px; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.18em;
      }
      .sr-divider::before, .sr-divider::after {
        content: ''; flex: 1;
        height: 1px;
        background: rgba(255, 255, 255, 0.06);
      }

      /* ── Reasons list ────────────────────────────────────────────── */
      .sr-reasons {
        width: 100%;
        margin: 0; padding: 0;
        list-style: none;
        display: flex; flex-direction: column; gap: 10px;
      }
      .sr-reasons li {
        display: flex; align-items: flex-start; gap: 10px;
        font-size: 13px;
        line-height: 1.5;
        color: rgba(245, 247, 250, 0.82);
        text-align: left;
        animation: sr-rise 320ms cubic-bezier(0.22, 1, 0.36, 1) both;
      }
      .sr-bullet {
        flex-shrink: 0;
        width: 16px; height: 16px;
        margin-top: 2px;
        display: flex; align-items: center; justify-content: center;
        color: var(--sr-accent, #94A3B8);
      }
      .sr-bullet svg { width: 100%; height: 100%; }
      .sr-reason-text { flex: 1; min-width: 0; }

      /* ── Links (Google Safe Browsing) ────────────────────────────── */
      .sr-links {
        width: 100%;
        margin: 0; padding: 0;
        list-style: none;
        display: flex; flex-direction: column; gap: 8px;
      }
      .sr-links li {
        display: flex; justify-content: space-between; align-items: center;
        gap: 12px;
        text-align: left;
        animation: sr-rise 320ms cubic-bezier(0.22, 1, 0.36, 1) both;
      }
      .sr-link-host {
        flex: 1;
        min-width: 0;
        font-size: 13px;
        font-weight: 500;
        color: rgba(245, 247, 250, 0.9);
        letter-spacing: -0.005em;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .sr-link-chip {
        flex-shrink: 0;
        font-size: 9.5px;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        padding: 4px 8px;
        border-radius: 6px;
        line-height: 1;
      }
      .sr-link-safe {
        color: #22C55E;
        background: rgba(34, 197, 94, 0.10);
        border: 1px solid rgba(34, 197, 94, 0.22);
      }
      .sr-link-danger {
        color: #F87171;
        background: rgba(239, 68, 68, 0.10);
        border: 1px solid rgba(239, 68, 68, 0.24);
      }
      .sr-link-more {
        justify-content: center;
        font-size: 11.5px;
        color: rgba(245, 247, 250, 0.4);
        letter-spacing: -0.005em;
      }
      .sr-link-note {
        margin: 10px 0 0;
        width: 100%;
        font-size: 11px;
        line-height: 1.5;
        color: rgba(245, 247, 250, 0.42);
        text-align: center;
        letter-spacing: -0.005em;
      }

      /* ── Scam type ───────────────────────────────────────────────── */
      .sr-type {
        margin: 0;
        font-size: 15px;
        font-weight: 600;
        color: rgba(245, 247, 250, 0.95);
        letter-spacing: -0.01em;
      }

      /* ── Loading state ───────────────────────────────────────────── */
      .sr-loading { padding: 44px 28px 40px; gap: 14px; }
      .sr-loading p {
        margin: 0;
        font-size: 13px;
        color: rgba(245, 247, 250, 0.55);
        letter-spacing: -0.005em;
      }
      .sr-spinner {
        width: 30px; height: 30px;
        border-radius: 50%;
        border: 2px solid rgba(255, 255, 255, 0.08);
        border-top-color: rgba(245, 247, 250, 0.85);
        animation: sr-spin 720ms linear infinite;
      }
      @keyframes sr-spin { to { transform: rotate(360deg); } }

      /* ── Error state (reuses hero layout) ────────────────────────── */
      .sr-error { padding-bottom: 30px; }

      @media (prefers-reduced-motion: reduce) {
        .sr-card, .sr-hero-icon, .sr-verdict-label, .sr-caption, .sr-reasons li,
        .sr-spinner { animation: none !important; }
      }
    `;
  }
})();
