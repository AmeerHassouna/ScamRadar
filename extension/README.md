# ScamRadar+ — Chrome Extension (Prototype v0.1.0)

A privacy-first Chrome extension that analyzes any text you explicitly
highlight, by sending it to your local ScamRadar+ API.

This is a **local proof of concept**. It is deliberately minimal, deliberately
manual, and deliberately platform-agnostic — the entire interaction is:

> **Highlight → Right-click → "Analyze with ScamRadar+" → See the verdict.**

---

## Prerequisites

- Google Chrome 116 or newer (or a Chromium-based browser: Edge, Brave, Arc)
- The ScamRadar+ API running locally on `http://127.0.0.1:8000`:
  ```bash
  # from repo root
  uvicorn api.main:app --host 127.0.0.1 --port 8000
  ```
- Confirm the API is up: `curl http://127.0.0.1:8000/health` should return
  `{"status":"ready", ...}`.

---

## Load the extension in Chrome

1. Open `chrome://extensions/`.
2. Toggle **Developer mode** on (top-right).
3. Click **Load unpacked**.
4. Select the `extension/` folder in this repo.
5. Pin the ScamRadar+ icon to the toolbar for easy access (optional).

That's it — the extension is now live in this Chrome profile.

## Using it

1. Go to any webpage (email, forum, article, DM…).
2. Highlight the suspicious text.
3. Right-click on the highlight.
4. Pick **Analyze with ScamRadar+** from the context menu.
5. A floating card appears in the top-right of the page with:
   - A colour-coded verdict (🟢 LEGIT / 🟠 SUSPICIOUS / 🔴 SCAM)
   - Confidence percentage and scam type
   - The reasons the model flagged the text
   - Signal intensities (urgency / fear / reward / threat)
   - Any URLs found and whether they are dangerous

Click the toolbar icon at any time to see whether the local API is reachable.

---

## Architecture

```
extension/
├── manifest.json      Manifest V3 declaration
├── background.js      Service worker — context menu, API client, orchestration
├── content.js         On-demand overlay renderer (Shadow DOM)
├── popup.html         Toolbar popup markup
├── popup.js           Health-check indicator
├── popup.css          Popup styles
├── icons/             16 / 32 / 48 / 128 PNGs
└── README.md
```

### Permissions

| Permission | Why |
| --- | --- |
| `contextMenus` | Register the "Analyze with ScamRadar+" entry. |
| `scripting` | Inject `content.js` on demand when the user picks the menu item. |
| `activeTab` | Temporary access to the current tab only when the user invokes the extension — no persistent per-site permissions. |
| `storage` | Reserved for future user preferences. Not read/written yet. |
| `host_permissions: 127.0.0.1:8000` | Allow `fetch()` from the service worker to the local API. |

There are **no `content_scripts` matches in the manifest.** Nothing is
injected into any page unless and until the user explicitly picks the context
menu item.

### Data flow

```
   ┌─── User highlights text on any page
   │
   │   User right-clicks → "Analyze with ScamRadar+"
   ▼
┌────────────────────────────────────────────────────────────────────┐
│ background.js  (service worker)                                    │
│   • chrome.contextMenus.onClicked fires with info.selectionText     │
│   • Validates length locally (20–5,000 chars)                       │
│   • chrome.scripting.executeScript → injects content.js on demand   │
│   • chrome.tabs.sendMessage({status: 'loading', excerpt})          │
│   • fetch('http://127.0.0.1:8000/predict',                          │
│           {method:'POST', body: {text: selection}})                 │
│   • chrome.tabs.sendMessage({status: 'result', result})            │
└────────────────────────────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────────────────────────────┐
│ content.js  (page context, Shadow DOM)                             │
│   • Idempotent: guarded by window.__scamRadarPlusLoaded            │
│   • Attaches a closed Shadow DOM host in the top-right corner      │
│   • Listens for SCAMRADAR_STATE messages                           │
│   • Renders loading / result / error card, fully style-isolated    │
└────────────────────────────────────────────────────────────────────┘
```

### Why Shadow DOM?

The overlay lives inside a `closed` Shadow Root so:

- Host-page CSS cannot restyle or break the overlay.
- The overlay cannot leak styles into the host page.
- Page scripts cannot inspect or manipulate the overlay's internals.

### Why on-demand script injection?

Static `content_scripts` in the manifest would run on every matching page for
the lifetime of the extension. That would be inconsistent with a privacy-first
promise. Instead, `background.js` calls `chrome.scripting.executeScript` only
after the user has explicitly chosen the context menu item — the content
script never touches a page the user didn't opt into.

---

## Privacy guarantees

- **Only your explicit selection leaves the browser.** The extension never
  reads the DOM, form fields, cookies, tabs, history, or emails.
- **No telemetry, no analytics, no third-party calls.** The only network
  destination is `127.0.0.1:8000` (or `localhost:8000`).
- **No persistent access to any site.** `activeTab` grants scripting rights
  only for the tab the user just interacted with, and only for that
  interaction.
- **No auto-injected content scripts.** The manifest declares zero
  `content_scripts` matches. The overlay is injected on demand only.

---

## Error handling

Friendly messages are shown for each failure mode:

| Scenario | Message |
| --- | --- |
| No text highlighted | "Nothing selected — highlight the text first." |
| Selection under 20 chars | "Selection too short (currently N)." |
| API unreachable | "Could not reach ScamRadar+ at 127.0.0.1:8000." |
| Request > 20s | "Request took longer than 20 seconds — API may be starting up." |
| API returns 429 | "You are sending requests too quickly." |
| API returns 503 | "The model is still starting up." |
| API returns 4xx with body | Detail message from the API is surfaced. |
| chrome:// or PDF viewer | Silent no-op — Chrome blocks script injection on privileged pages. |

---

## Future expansion

The current entry point is a single context menu handler. The architecture
leaves room for optional, opt-in adapters — each one gated behind an
explicit user setting:

- **Gmail** — parse `mail.google.com` DOM into individual message blocks,
  add an inline "Analyze" button per message.
- **Outlook Web** — same idea for `outlook.live.com` / `outlook.office.com`.
- **LinkedIn** — inline analysis inside `/messaging`.
- **Reddit / Facebook Messenger / Discord** — DM-scoped analyzers.

None of these are implemented in v0.1.0. Adding one would mean:

1. A new script under a `sites/` subdirectory.
2. A new opt-in toggle in the toolbar popup.
3. A new context or content-script match, only registered after the toggle
   is enabled by the user.

The universal highlight → right-click flow will always remain the default
and always work everywhere, even when site-specific adapters are absent or
disabled.

---

## Assumptions and limitations

- **English-only.** The API returns `400` for non-English input. The overlay
  surfaces the API's own error message when this happens.
- **Local only.** `host_permissions` is limited to `127.0.0.1:8000` and
  `localhost:8000`. To point at a remote deployment, add its origin to
  `manifest.json → host_permissions` and update `API_BASE` in
  `background.js`.
- **HTTP, not HTTPS.** Chrome allows extensions to fetch plain-HTTP
  `127.0.0.1` URLs without mixed-content warnings, which is why the
  prototype works over `http://` locally.
- **Chrome-family only.** Firefox uses a similar but not identical MV3
  surface. Porting is straightforward but not done here.
- **Chrome-restricted pages.** The overlay cannot render on `chrome://`
  URLs, the Chrome Web Store, or PDF viewer pages. This is a Chrome
  security policy, not a bug in the extension.
- **Selection limit.** The API accepts 20–5,000 characters. Selections over
  the max are truncated (with a note in the card); selections under the min
  are rejected before the network request.
