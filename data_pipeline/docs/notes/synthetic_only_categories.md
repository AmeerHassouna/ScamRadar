# Justification: Synthetic-Only Categories (Batch 1)

Status: **Batch 1 v2b — ACCEPTED on artifact grounds** (2026-08-01).
Downstream-benefit verification (DESIGN §7 rule 6.f) still required.

- Active batch id: `batch1v2_20260731`
  (`data/raw/synthetic/batch1v2_20260731_manifest.json`).
- Superseded batches: `batch1_20260731` (v1 — obvious surface artifacts,
  regenerated). Kept in git history but not on disk.
- Probe diagnostic: `reports/probe_E1_v2b_accepted.md`. Per-category
  artifact checks (DESIGN §7 rule 6.a) PASS on all three synthetic-only
  categories. Global aggregate check misses URL rate by 0.4pp; documented
  as a mix-arithmetic artifact of batch weighting, not a per-category style
  issue.
- Policy revision applied: DESIGN §7 rule 6 was rewritten from a single
  probe-AUC threshold into the current six-criterion acceptance policy
  (6.a–6.f). Rule 7 now marks the probe as diagnostic, not gating. The
  revision was requested after v1 → v2b iteration demonstrated that
  template-based synthesis cannot reach AUC ≤ 0.75 against a char-TFIDF
  probe trained on tens of thousands of real neighbors; but v2b does
  successfully eliminate every named cheap artifact.

## Original justification (still valid)

Per DESIGN §7 (v2.0):
> Real first. For any category with a viable real corpus, synthetic
> augmentation requires written justification in docs/notes/.

This note justifies operating three categories at 100% synthetic composition
in batch 1, because no viable ethical public real corpus was found during the
initial search pass documented in the audit conversation.

The following original justification remains applicable to batch 1 v2b (only
the surface style of the samples changed; the sourcing rationale is unchanged).

## Categories

### `bec_ceo_fraud` — 500 synthetic, 0 real
- **Why no real data**: Real BEC email content is confidential victim data
  held by security vendors (Proofpoint, Abnormal Security, Cyren) and law
  enforcement. The public academic release `r-dube/bec` (BEC-2-human.csv,
  AGPL-3.0) contains 279 rows but is itself **LLM-generated + human-validated**
  synthetic data — not real. Ingesting it would blur our real/synthetic line
  and re-import someone else's synthesis under a copyleft license.
- **Coverage plan**: batch 1 seeds 500 rows across CEO/CFO/COO/etc. personas
  × wire / gift-card / payroll / invoice asks × formal-business / casual-urgent
  registers. If a future controlled study shows model performance is
  materially lift-able by more BEC volume, we add batch 2 with distinct
  templates.

### `romance_scam` — 313 synthetic, 0 real
- **Why no real data**: `Betawolf/scamdiggerprofiles` on GitHub scrapes real
  romance-scam dating profiles from `scamdiggers.com` (~2017) but has **no
  license declared** — unusable for a project that requires documented
  licensing. Recent romance-scam dataset releases (e.g. the 2025 romance-
  baiting dialogues paper) are also LLM-generated. Real victim messages sit
  behind institutional data-sharing agreements (Cambridge Cybercrime Centre).
- **Coverage plan**: batch 1 seeds 313 rows across 10 personas (military /
  offshore / expat engineer / MSF surgeon / …) × opener / rapport / crisis /
  ask stages × email / chat / SMS platforms. The dedup fingerprint clipped
  the target from 500 → 313, indicating template diversity is currently
  tight; batch 2 would need additional persona × opener seeds.

### `marketplace_delivery_scam` — 485 synthetic (post-dedup), 0 real
- **Why no real data**: Public real corpora exist for URL-based delivery
  smishing (PhishTank, APWG feeds) but not for the *message text* of
  marketplace/delivery scams. The Mendeley SMS corpus we already ingest
  contains a small number of delivery-adjacent smishing messages but they
  are labelled `smishing`, not `marketplace_delivery_scam`, and we have not
  re-categorised them post-hoc (that would be labelling drift).
- **Coverage plan**: batch 1 seeds 485 rows across 14 carriers × fake-URL
  patterns (shorteners, punycode-adjacent, .top / .click / .xyz TLDs) ×
  fake-buyer overpayment / refund-billing patterns × SMS / chat / email.

## Provenance & recoverability

Every synthetic row carries:
- `is_synthetic = True` (forever, set by the acquire parser)
- `source = synthetic_v1`
- `platform` = per-row (email / sms / chat)
- Extra metadata in `data/raw/synthetic/*.jsonl`: `persona`, `geography`,
  `register`, `template_id`, `batch_id`.
- Manifest: `data/raw/synthetic/batch1_20260731_manifest.json`
  (batch id, seed, per-category counts, length p5/p50/p95, platform mix).

Every row is `benchmark_eligible = False` at the source level, so **no
synthetic sample can leak into any external benchmark** (asserted in
`split.py`).

## Gate for batch 2

Do not generate batch 2 unless:
1. A trained baseline model demonstrates that these categories improve
   noticeably from batch 1 volume (measurable on the internal held-out set,
   per-category recall).
2. A REAL-vs-SYNTHETIC probe classifier trained within each synthetic
   category has AUC ≤ 0.75 (DESIGN §7 rule 6). If a probe trivially detects
   our synthetic samples, we regenerate with more varied templates before
   scaling.
3. The per-category cap check (`synthetic_share ≤ 25%` once real data is
   present) is respected once any real corpus lands.
