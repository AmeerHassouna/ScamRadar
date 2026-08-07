# Synthetic Data Generation Guide (spec §3)

Fill ONLY the categories with no adequate public corpus. Output JSONL into
`data/raw/synthetic/<category>_<batch>.jsonl`, one object per line:

```json
{"text": "...", "label": 1, "category": "bec_ceo_fraud", "platform": "email"}
```

## Categories to fill (label=1 unless noted)
bec_ceo_fraud, invoice_fraud, romance_scam, investment_crypto_scam,
marketplace_scam, delivery_smishing, banking_smishing, account_recovery_scam,
tech_support_scam, giveaway_scam, refund_scam, charity_scam, impersonation_scam,
subscription_scam, identity_theft_scam, trust_building_opener, ai_assisted_scam
— plus ham: discord_gaming_chat (0), family_friend_chat (0), social_media_dm (0),
marketplace_conversation (0), customer_support_reply (0).

## Diversity rules (mandatory)
- Generate in batches of ≤ 30; **change persona, platform, country, register, and
  length distribution every batch** (formal/casual, long/short, typos on/off,
  emoji on/off, EN + HE + AR batches for multilingual coverage).
- Ban template repetition: no two samples may share an opening 6-gram; the clean
  stage's near-dup clustering will collapse lazy batches — regenerate if a batch
  loses >15% to clustering.
- Include *hard negatives*: legitimate messages that look scammy (real bank OTP
  notifications, real recruiter cold-outreach, genuine delivery links) and
  *hard positives*: polite, well-written, no-URL scams (BEC, romance).
- After ingestion, train a quick synthetic-vs-real probe classifier within each
  label; if probe AUC > 0.75, style is too detectable — regenerate with more varied prompts.

## Example batch prompt (adapt per category/batch)
> Write 25 realistic {category} messages as they would appear on {platform} in
> {year}. Persona: {persona}. Vary length 10–120 words, {register} register,
> {quirks}. Output JSONL with fields text,label,category,platform. No numbering,
> no explanations, no repeated openings.

## Hard limits (DESIGN §7, v2.0)
- `is_synthetic` stays true forever (set automatically by the parser).
- Synthetic share per category **≤ 25%** (tightened from 40% in v2.0).
- Exceeding 25% requires a controlled experiment showing improvement on
  independent external benchmarks (not internal held-out).
- Synthetic samples are **excluded from every external benchmark by code**
  (`benchmark_eligible=False` in sources.py) — do not change that flag.
- Every batch is provenance-tagged (`batch_id`, `template_id`, `persona`,
  `geography`, `register`) so any batch can be quarantined post-hoc.

## Programmatic generator
`scripts/synthesize_batch_1.py` is the first batch generator (BEC / romance /
marketplace-delivery). Run it and drop the JSONLs into `data/raw/synthetic/`.
Manifest goes alongside as `<batch_id>_manifest.json`.
