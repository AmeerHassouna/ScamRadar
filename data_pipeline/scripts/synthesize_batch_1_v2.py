"""Batch 1 v2 — regenerated to defeat the synthetic-vs-real probe (DESIGN §7.6).

Batch 1 v1 was AUC 1.000 detectable across all four probes. Root causes are in
`reports/probe_E1.md`. This regenerator fixes the surface-level tells by
MATCHING real-corpus distributions instead of using fixed templates:

  * ALL em-dashes removed (real rate: 0.1%; v1 rate: heavy in every sign-off).
  * ALL emoji removed (real rate: 0.0%; v1 romance rate: 31.9%).
  * ASCII apostrophes throughout (curly-quote rate matches real ~1%).
  * URL frequency calibrated PER CATEGORY to nearest-neighbor real rate,
    using REAL URLs sampled from real scam messages as scaffolding.
  * Length distribution sampled from empirical CDF of nearest-neighbor real
    (BEC p50 449 chars, romance p50 2286, marketplace p50 282).
  * First-person density balanced with imperative + third-person voices.
  * Greetings and sign-offs sampled from real scam emails as scaffolding
    (with within-source dedup so we don't reproduce single strings).

Nearest-neighbor mapping (for style matching; the SEMANTICS of each synthetic
sample remain category-appropriate):
  bec_ceo_fraud            <- email_phishing + email_spam + advance_fee_fraud
  romance_scam             <- advance_fee_fraud
  marketplace_delivery_scam<- smishing + email_phishing

Run:  python scripts/synthesize_batch_1_v2.py
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("data/raw/synthetic")
OUT.mkdir(parents=True, exist_ok=True)
BATCH_ID = f"batch1v2_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
SEED = 20260802
CLEAN = "data/interim/clean.parquet"
TARGET_PER_CATEGORY = 500

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
GREET_RE = re.compile(
    r"^\s*(dear\s+[^\n,.:]{1,40}|hi\s+[^\n,.:]{1,40}|"
    r"hello\s+[^\n,.:]{1,40}|greetings?|good\s+(morning|day|afternoon|evening)"
    r"[^\n,.:]{0,20}|attn:[^\n]{0,40}|to whom it may concern|"
    r"my dear[^\n,.:]{0,40})", re.I)
SIGNOFF_RE = re.compile(
    r"(regards|sincerely|best regards|yours truly|yours sincerely|"
    r"thanks|thank you|cheers|warmly|yours faithfully|"
    r"sent from my (iphone|phone|blackberry|mobile|ipad))"
    r"[^\n]{0,60}$", re.I)

NEIGHBORS = {
    "bec_ceo_fraud": ["email_phishing", "email_spam", "advance_fee_fraud"],
    "romance_scam": ["advance_fee_fraud"],
    "marketplace_delivery_scam": ["smishing", "email_phishing"],
}


# ---------------------------------------------------------------------------
# Real-corpus scaffolding
# ---------------------------------------------------------------------------

def _sample_urls(texts: pd.Series, cap: int = 2000) -> list[str]:
    urls: set[str] = set()
    for t in texts:
        for m in URL_RE.findall(str(t)):
            m = m.rstrip(".,;:!?)\"'")
            if 10 <= len(m) <= 100:
                urls.add(m)
                if len(urls) >= cap * 3:
                    break
        if len(urls) >= cap * 3:
            break
    return list(urls)[:cap]


def _sample_greetings(texts: pd.Series, cap: int = 500) -> list[str]:
    """First-line matches against the greeting regex, deduped and length-clipped."""
    seen = Counter()
    for t in texts:
        first = str(t).lstrip().split("\n", 1)[0][:120]
        m = GREET_RE.match(first)
        if m:
            g = m.group(0).strip().rstrip(",.:") + ","
            seen[g.lower()] += 1
    # Keep the most-common greetings (survive across many senders).
    return [g for g, _ in seen.most_common(cap)]


def _sample_signoffs(texts: pd.Series, cap: int = 500) -> list[str]:
    """Last-line matches against the signoff regex."""
    seen = Counter()
    for t in texts:
        lines = [l.strip() for l in str(t).splitlines() if l.strip()]
        if not lines:
            continue
        # Look at the last 3 lines for a signoff match
        for l in lines[-3:]:
            m = SIGNOFF_RE.search(l[:120])
            if m:
                s = m.group(0).strip()
                seen[s.lower()] += 1
                break
    return [s for s, _ in seen.most_common(cap)]


def load_scaffolding() -> dict:
    df = pd.read_parquet(CLEAN)
    scaff: dict = {}
    for target, neigh in NEIGHBORS.items():
        sub = df[(df.label == 1) & (~df.is_synthetic) & df.category.isin(neigh)]
        texts = sub.text.astype(str)
        lens = texts.str.len().values
        scaff[target] = {
            "n_neighbors": int(len(sub)),
            "len_percentiles": {int(p): int(np.percentile(lens, p))
                                for p in (10, 25, 50, 75, 90)},
            "url_rate": float(texts.str.contains(URL_RE).mean()),
            "urls": _sample_urls(texts),
            "greetings": _sample_greetings(texts),
            "signoffs": _sample_signoffs(texts),
        }
        print(f"[scaffolding] {target}: n={len(sub)}, "
              f"len_p50={scaff[target]['len_percentiles'][50]}, "
              f"url_rate={scaff[target]['url_rate']:.3f}, "
              f"urls={len(scaff[target]['urls'])}, "
              f"greetings={len(scaff[target]['greetings'])}, "
              f"signoffs={len(scaff[target]['signoffs'])}")
    return scaff


# ---------------------------------------------------------------------------
# Style-clean fills (ASCII only — no em-dash, no curly quotes, no emoji)
# ---------------------------------------------------------------------------

FIRST_NAMES = ["Sarah", "Michael", "Priya", "Tomas", "Grace", "Wei", "Ahmed",
               "Maria", "James", "Chinedu", "Isabella", "Kenji", "Fatima",
               "David", "Amira", "Rahul", "Sophia", "Emeka", "Lena", "Noah",
               "Oluchi", "Yara", "Marcus", "Anya", "Ravi", "Chloe", "Jamal",
               "Elena", "Farida", "Adaeze", "Sebastian", "Zara", "Hassan"]
LAST_NAMES = ["Nguyen", "Patel", "Rodriguez", "Kim", "Silva", "Cohen",
              "Okafor", "Mueller", "Andersen", "Bianchi", "Yilmaz", "Zhang",
              "OBrien", "Sundstrom", "Van Der Berg", "Iyer", "Bello",
              "MacLeod", "Bakr", "Novak", "Adeyemi", "Petersen", "Correa"]
COMPANIES = ["Acme Logistics", "Northwind Traders", "Vertex Health",
             "Arcadia Bank", "Halcyon Legal", "Bluepine Software",
             "SilverRoot Capital", "Kestrel Media", "Rothwell and Associates",
             "PineTree Foods", "Kite Aerospace", "Meridian Retail",
             "Ashcroft Consulting", "Vanguard Ventures", "Larkspur Holdings"]
CURRENCIES = ["USD ", "GBP ", "EUR ", "$", "USD", "GBP", "EUR"]
COUNTRIES = ["US", "UK", "AU", "DE", "SG", "IN", "AE", "IE", "CA", "NZ", "NG",
             "ZA", "PH", "HK", "FR", "ES"]


def _amount(rng: random.Random) -> str:
    """Realistic dollar amount formatting."""
    val = rng.choice([12_500, 24_800, 37_200, 48_500, 62_400, 85_000, 120_000,
                      240_000, 385_000, 750_000, 1_200_000, 2_400_000])
    return f"{val:,}"


def _sample_length(scaff: dict, rng: random.Random) -> int:
    """Sample a target length from the empirical CDF (linear interp)."""
    pcts = scaff["len_percentiles"]
    grid = [10, 25, 50, 75, 90]
    vals = [pcts[p] for p in grid]
    q = rng.random() * 100
    if q < 10: return int(vals[0])
    if q > 90: return int(vals[4] * rng.uniform(1.0, 1.4))
    # linear interp between grid points
    for i in range(len(grid) - 1):
        if grid[i] <= q <= grid[i + 1]:
            t = (q - grid[i]) / (grid[i + 1] - grid[i])
            return int(vals[i] + t * (vals[i + 1] - vals[i]))
    return int(vals[2])


def _pick_url(rng: random.Random, scaff: dict) -> str:
    """Return a real-sampled URL. Caller controls whether to include it."""
    if not scaff["urls"]:
        return ""
    return rng.choice(scaff["urls"])


def _maybe_url(rng: random.Random, scaff: dict) -> str:
    """Return URL with probability = real rate. Use in ONE place per sample."""
    if rng.random() > scaff["url_rate"]:
        return ""
    return _pick_url(rng, scaff)


def _greeting(rng: random.Random, scaff: dict) -> str:
    """Return a real-sampled greeting, or '' with probability that no greeting appears."""
    if rng.random() < 0.15 or not scaff["greetings"]:
        return ""
    g = rng.choice(scaff["greetings"])
    # Occasionally replace generic 'you'/'dear' target with a first name
    if rng.random() < 0.3:
        g = re.sub(r"customer|user|beneficiary|friend|sir|madam",
                   rng.choice(FIRST_NAMES).lower(), g, count=1, flags=re.I)
    return g[0].upper() + g[1:]


def _signoff(rng: random.Random, scaff: dict, name: str = "") -> str:
    if rng.random() < 0.30 or not scaff["signoffs"]:
        return ""
    base = rng.choice(scaff["signoffs"])
    return (base[0].upper() + base[1:]) + (f"\n{name}" if name and rng.random() < 0.6 else "")


def _typo(rng: random.Random, text: str) -> str:
    if rng.random() > 0.06 or len(text) < 50:
        return text
    out = list(text)
    for _ in range(rng.randint(1, 2)):
        i = rng.randint(5, len(out) - 5)
        if out[i].isalpha():
            if rng.random() < 0.5 and i + 1 < len(out):
                out[i], out[i + 1] = out[i + 1], out[i]
            else:
                out.pop(i)
    return "".join(out)


# ---------------------------------------------------------------------------
# BEC / CEO fraud (v2)
# ---------------------------------------------------------------------------

BEC_ASK_BLOCKS = [
    # Wire (imperative / third-person / first-person voices mixed)
    "Please initiate a wire transfer of {cur}{amt} to the beneficiary detailed in the attached invoice. The vendor is standing by for confirmation.",
    "A wire of {cur}{amt} needs to go out today to the new escrow account. Bank details are being forwarded from legal.",
    "Kindly release the outstanding payment of {cur}{amt} to the account referenced below. Approval is on file.",
    "Can this go out this afternoon: wire of {cur}{amt} to the counterparty account we discussed on the call.",
    "The board approved the payment. Wire {cur}{amt} to the vendor account, then confirm the trace by email.",

    # Gift cards
    "Please pick up {n} {brand} gift cards of {cur}{amt2} each from any store. Snap a photo of the codes on the back and email them across.",
    "I need help arranging {n} {brand} cards of {cur}{amt2} for a client appreciation package. Reimbursement through petty cash tomorrow.",
    "Grab {cur}{amt2} of {brand} gift codes today please. This is time-sensitive so text once done.",

    # Vendor invoice
    "Please process invoice INV-{invnum} from {vendor}. The total is {cur}{amt}. The audit review is on Friday so it needs to clear before then.",
    "Attached invoice from {vendor} for {cur}{amt} is now approved for payment. Please queue it in the next payment run.",
    "Reminder to release the outstanding {vendor} invoice ({cur}{amt}). Legal has cleared the master agreement change.",

    # Payroll change
    "Please update the routing details on my payroll deposit effective this cycle. The new account information will follow in a separate note.",
    "My banking has changed. Update direct deposit to the account provided. Confirm once the change is made in the payroll system.",
]
BEC_URGENCY_BLOCKS = [
    "This is time-sensitive so please move on it before end of day.",
    "The counterparty is waiting on confirmation, keep this a priority.",
    "I am in back to back meetings so please handle it directly and copy me when done.",
    "No rush, but before the weekend would be ideal.",
    "",
    "",
]
BEC_CONTEXT_BLOCKS = [
    "This relates to the acquisition discussed in the last leadership sync.",
    "Reference the vendor onboarding package I forwarded on Monday.",
    "It ties back to the audit remediation item from the last board pack.",
    "This is part of the international expansion budget approved last quarter.",
    "The receivable was flagged during the reconciliation review.",
    "",
    "",
]
BEC_CONFID_BLOCKS = [
    "Please treat this discreetly for now, we will brief the wider team once the announcement lands.",
    "Keep this off the shared channel until the release is public.",
    "Do not loop finance yet, legal is still finalising the disclosure.",
    "",
    "",
]
BEC_FORWARDED = [
    "\n\n-----Original Message-----\nFrom: {fwdname} <{fwdemail}>\nSubject: Re: {subj}\n\n{fwdbody}",
    "\n\n> On {date}, {fwdname} wrote:\n> {fwdbody}",
    "",
    "",
    "",
]
BEC_FWD_SUBJECTS = ["Payment approval", "Wire instructions", "Vendor onboarding",
                    "Q3 close items", "Invoice attention required",
                    "Payroll change request"]
BEC_FWD_BODIES = [
    "Thanks for the follow up. Confirming the payment amount and the beneficiary details are in the master file. Please proceed as discussed on our call.",
    "See the payment schedule from procurement. This is aligned with the master services agreement. Copy of the SOW is available on the shared drive.",
    "Confirming the change has been logged with HR and payroll. Effective next cycle. Any questions please loop me back in.",
    "Board minutes attached. Approval for the expenditure is noted in item 4.2. Please execute per the schedule.",
]


def gen_bec(rng: random.Random, scaff: dict) -> dict:
    target_len = _sample_length(scaff, rng)
    firstname = rng.choice(FIRST_NAMES)
    lastname = rng.choice(LAST_NAMES)
    company = rng.choice(COMPANIES)
    country = rng.choice(COUNTRIES)
    exec_title = rng.choice(["CEO", "CFO", "COO", "Managing Partner",
                             "Group CEO", "President", "SVP Finance"])
    ask = rng.choice(BEC_ASK_BLOCKS).format(
        cur=rng.choice(CURRENCIES), amt=_amount(rng),
        amt2=rng.choice(["100", "200", "500", "1000"]),
        n=rng.choice([5, 8, 10, 15, 20, 25]),
        brand=rng.choice(["Apple", "Amazon", "Google Play", "Steam", "Target",
                          "Walmart", "iTunes", "Sephora", "Best Buy"]),
        invnum=str(rng.randint(2000, 99000)),
        vendor=rng.choice(["Kingfisher Logistics", "OrionSoft Ltd",
                           "Meridian Legal", "PineWorks Ltd",
                           "Halcyon Cleaning Services", "Bluepine Consulting"]),
    )
    urgency = rng.choice(BEC_URGENCY_BLOCKS)
    context = rng.choice(BEC_CONTEXT_BLOCKS)
    confid = rng.choice(BEC_CONFID_BLOCKS)

    greeting = _greeting(rng, scaff)
    signoff = _signoff(rng, scaff, name=f"{firstname} {lastname}\n{exec_title}, {company}")
    # Gate URL exactly once per sample at the real target rate.
    include_url = rng.random() < scaff["url_rate"]
    url_frag = _pick_url(rng, scaff) if include_url else ""
    url_line = rng.choice([
        f"Details attached: {url_frag}",
        f"Wire details: {url_frag}",
        f"Reference document: {url_frag}",
        f"Payment portal: {url_frag}",
    ]) if url_frag else ""

    body_parts = [greeting, ask, context, url_line, urgency, confid, signoff]
    body = "\n\n".join(p for p in body_parts if p.strip())

    # If below the target length, splice one or more realistic scaffolds:
    # forwarded thread, additional context paragraph, or standard closing text.
    extra_pool = [
        "Please make sure to reference the correct GL code so this posts to the right cost centre. If unsure, use the code from the last similar payment we ran.",
        "I have looped the treasury team on the counterparty verification. Their check should not delay your action here.",
        "Legal has reviewed and signed off on the agreement. There is nothing outstanding on their side.",
        "The compliance flag on this account has been cleared as of yesterday. No further checks are required.",
        "If any issues come up while processing, please email me directly rather than calling. I am on a strict schedule today.",
        "The internal audit trail is complete. Copies of the underlying documents are on the shared drive under Q3 folder.",
        "Please note that the payment terms have been renegotiated. The new terms are in the master vendor file.",
    ]
    pool = list(extra_pool)
    rng.shuffle(pool)
    for extra in pool:
        if len(body) >= target_len * 0.8:
            break
        if signoff and signoff in body:
            body = body.replace(signoff, extra + "\n\n" + signoff, 1)
        else:
            body = body + "\n\n" + extra

    if len(body) < target_len * 0.7 and rng.random() < 0.7:
        fwd = rng.choice(BEC_FORWARDED)
        if fwd:
            body += fwd.format(
                fwdname=f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                fwdemail=f"{rng.choice(FIRST_NAMES).lower()}.{rng.choice(LAST_NAMES).lower()}@{company.lower().replace(' ','')}.com",
                subj=rng.choice(BEC_FWD_SUBJECTS),
                fwdbody=rng.choice(BEC_FWD_BODIES),
                date="Mon, 4 Feb 2024 09:12:41 -0500")

    body = _typo(rng, body).strip()
    return {
        "text": body, "label": 1, "category": "bec_ceo_fraud",
        "platform": rng.choice(["email", "email", "email", "email", "chat"]),
        "persona": exec_title, "geography": country,
        "template_id": "bec_v2",
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Romance (v2) — long-form 419-adjacent, no emoji, real URLs when applicable
# ---------------------------------------------------------------------------

ROMANCE_PERSONAS = [
    "US Army Sergeant deployed with the peacekeeping mission in Damascus",
    "Royal Navy Commander stationed in the Gulf of Aden",
    "offshore petroleum engineer contracted on a rig in the North Sea",
    "civil engineer supervising a bridge project outside Kuala Lumpur",
    "widowed cardiac surgeon working with Medecins Sans Frontieres in Yemen",
    "veterinarian volunteering with an animal welfare project in Nairobi",
    "commodities trader based between Singapore and Dubai",
    "marine biologist doing field research off the coast of Madagascar",
    "senior architect on a hospitality development in Doha",
    "logistics coordinator with a humanitarian aid group in Yemen",
    "United Nations mission officer stationed in South Sudan",
    "senior geophysicist contracted with a mining project in Ghana",
]
ROMANCE_OPENERS = [
    "It was a pleasure coming across your profile. I hope you will not mind me writing directly.",
    "My name is {mine}. I saw your profile and I felt compelled to reach out and greet you properly.",
    "Kindly permit me to write to you. Something in your profile spoke to me and I hope you will read this in the spirit it is written.",
    "Good day. I am {mine}. I am writing to introduce myself in the hope that you will find the time to reply.",
    "Greetings from Damascus. My name is {mine} and I would like to know you better if you are open to it.",
    "I hope this message meets you in good health. I felt drawn to your profile and thought it right to send a proper introduction.",
]
ROMANCE_BIO_BLOCKS = [
    "I lost my wife three years ago after a long illness. It took me a long time to consider dating again and I want to be honest about that from the start.",
    "I have been divorced for over four years. The work has kept me abroad and building connection at a distance is difficult, though not impossible.",
    "I am a private person by nature and I do not share much publicly. But I would rather write something honest here than a polished sentence that says nothing.",
    "I have one daughter, her name is Emma and she is 12. She lives with my sister in the United States and I miss her every single day.",
    "I do not use these platforms often, my colleagues insisted after months of encouragement. I hope you will not judge me for the awkwardness.",
    "I grew up in a small town and moved abroad for work in my late twenties. Distance from home is something I have learned to live with, but connection I still search for.",
]
ROMANCE_CONNECT_BLOCKS = [
    "I would like to know your favourite things and your dreams, and to tell you about mine. What music do you love. Where would you travel if there were no restrictions on time and money.",
    "Please tell me about your day, your work, your family. I want the small details, the ones that make a person real rather than a headline.",
    "If you are open to conversation, I would gladly move to a private channel where we can write more comfortably. My schedule is difficult, but I make time when it matters.",
    "I find myself writing longer messages than I intended. Please forgive me. It has been a long time since I felt worth writing to someone at all.",
]
ROMANCE_CRISIS_BLOCKS = [
    "There is an issue with my accounts. Because I have been offshore for so long, my bank is asking for identity verification I cannot complete from here. I have written to a lawyer who is helping me but the process is slow and expensive.",
    "My daughter Emma had an accident during a school trip and is in hospital. I cannot access my funds from here because of clearance restrictions on my work account. I feel completely helpless being so far from her.",
    "The company that manages my contract has held my final payment behind a compliance review. It should clear next month but until then I have very limited access to my own money.",
    "Customs in {city} are holding a package I sent home. There is a small tax due to release it and I cannot arrange the payment from here without opening an account they can freeze.",
]
ROMANCE_ASK_BLOCKS = [
    "If you could send {cur}{amt} to my lawyer to help move this along, I would repay you with interest the moment the accounts clear. Please, only if you are comfortable.",
    "I do not like to ask this and I understand if you say no. Would you consider covering {cur}{amt} until the transfer clears, so I can be with her.",
    "The clearance fee is {cur}{amt}. I would ask my brother but he is not currently reachable. If you can help I promise to make it right when I am back.",
    "The customs charge is {cur}{amt}. I have no way to pay it from here. Please consider it a loan, one I will insist on returning double.",
]
ROMANCE_CLOSE_BLOCKS = [
    "Thank you for reading. I hope to hear from you. Whatever your answer, please know that just writing this has meant a great deal.",
    "I will wait for your reply. Please take care of yourself.",
    "Your kindness in reading this is already more than I hoped for. May we speak soon.",
    "Yours faithfully,\n{mine}",
    "With very warm regards,\n{mine}",
    "{mine}",
]

CITIES = ["Lagos", "Accra", "Kuala Lumpur", "Doha", "Istanbul", "Nairobi",
          "Dubai", "Kyiv", "Bangkok", "Manila", "Athens", "Amman", "Cairo"]


def gen_romance(rng: random.Random, scaff: dict) -> dict:
    target_len = _sample_length(scaff, rng)
    mine = rng.choice(FIRST_NAMES)
    persona = rng.choice(ROMANCE_PERSONAS)
    country = rng.choice(COUNTRIES)

    parts = [
        _greeting(rng, scaff),
        rng.choice(ROMANCE_OPENERS).format(mine=mine),
        f"I am a {persona}.",
        rng.choice(ROMANCE_BIO_BLOCKS),
        rng.choice(ROMANCE_CONNECT_BLOCKS),
    ]
    # Bulk it out with more bio/connect blocks until we approach target length.
    # Real romance emails run ~2000+ chars — we need repeated distinct paragraphs.
    pool = list(ROMANCE_BIO_BLOCKS + ROMANCE_CONNECT_BLOCKS)
    rng.shuffle(pool)
    for extra in pool:
        cur_len = len("\n\n".join(p for p in parts if p))
        if cur_len >= target_len * 0.9:
            break
        parts.append(extra)

    include_ask = rng.random() < 0.65
    if include_ask:
        parts.append(rng.choice(ROMANCE_CRISIS_BLOCKS).format(city=rng.choice(CITIES)))
        parts.append(rng.choice(ROMANCE_ASK_BLOCKS).format(
            cur=rng.choice(CURRENCIES),
            amt=f"{rng.choice([180, 250, 450, 650, 850, 1200, 1500, 2400, 3800]):,}"))
    # Gate URL exactly once per sample at the real target rate.
    if rng.random() < scaff["url_rate"]:
        url_frag = _pick_url(rng, scaff)
        if url_frag:
            parts.append(rng.choice([
                f"I have set up a page with more about my situation, please read when you can: {url_frag}",
                f"You can see the news article about the mission here: {url_frag}",
                f"I put together a small profile page here so you can see who I am: {url_frag}",
                f"Please see the reference from my sister here: {url_frag}",
            ]))
    parts.append(rng.choice(ROMANCE_CLOSE_BLOCKS).format(mine=mine))
    text = "\n\n".join(p for p in parts if p and p.strip())
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "romance_scam",
        "platform": rng.choice(["email", "email", "email", "chat"]),
        "persona": persona.split(",")[0], "geography": country,
        "template_id": "romance_v2_" + ("with_ask" if include_ask else "rapport_only"),
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Marketplace / delivery (v2) — some URL, some no URL, ASCII throughout
# ---------------------------------------------------------------------------

CARRIERS = ["FedEx", "UPS", "USPS", "DHL", "Amazon Logistics", "Royal Mail",
            "Australia Post", "Canada Post", "DPD", "Hermes", "An Post",
            "Correos", "La Poste", "Deutsche Post"]


def _fake_tracking(rng: random.Random) -> str:
    letters = "".join(rng.choices("ABCDEFGHJKLMNPRSTUVWXYZ", k=2))
    digits = "".join(rng.choices("0123456789", k=rng.randint(9, 12)))
    return letters + digits


DELIVERY_SMS_WITH_URL = [
    "{carrier}: package {code} could not be delivered. Confirm redelivery: {url}",
    "[{carrier}] Item held at customs, {cur}{fee} clearance fee due to release. {url}",
    "Hi, your parcel {code} awaits address confirmation. Reschedule: {url}",
    "{carrier} notice: Delivery attempt failed. Verify within 24hr or return to sender. {url}",
    "Your {carrier} shipment {code} is delayed. Missing postcode. Please fix: {url}",
    "{carrier}: parcel {code} on hold pending {cur}{fee} redelivery fee. Pay: {url}",
]
DELIVERY_SMS_NO_URL = [
    "{carrier}: parcel {code} could not be delivered. Reply 1 to schedule redelivery or call {phone}.",
    "Hi, this is {carrier} local depot. Your package {code} needs address confirmation. Please call {phone}.",
    "{carrier}: your item {code} is at the sorting hub. Reply YES to authorise release.",
    "Your {carrier} package {code} requires a signature. Please reply with a preferred window and postcode.",
]
MARKETPLACE_CHAT_WITH_URL = [
    "Hi, is your {item} still available. I can pay {cur}{price} today and ship through my agent. Payment link: {url}",
    "Interested in the {item}. My assistant already sent payment via the portal, please confirm receipt here: {url}",
    "Hello, I would like to buy the {item} for the asking price. Please confirm your email and I will send the invoice via {url}",
    "Good day. I want the {item} as a gift for my son. Please review the shipping form: {url}",
]
MARKETPLACE_CHAT_NO_URL = [
    "Hi, is your {item} still available. I can pay {cur}{price} today if you ship it. I am out of town so my shipping agent will collect it.",
    "Interested in the {item}. I am overseas, so I will send payment from my company account. Please confirm your email so I can arrange the transfer.",
    "Hello, I saw your listing for the {item}. I would prefer to pay via bank transfer and have my courier collect. Is that acceptable.",
    "Hi. My mother wants the {item} as a gift. I am abroad, let me overpay by {cur}{overpay} to cover the courier, then you send the balance to the shipper.",
    "Still available. Happy to pay full asking. I work offshore so payment will come from my company account. Please share your bank details.",
]
REFUND_EMAIL_BLOCKS = [
    "Thank you for your continued subscription to {brand}. Our records show your annual auto-renewal was processed today for {cur}{amt}. If you did not authorise this charge, you can request a full refund within 48 hours.",
    "This is an automated notice from {brand} Billing. Your account was billed {cur}{amt} today for renewal. Cancel or request a refund within 48 hours to avoid the charge becoming final.",
    "We are writing to confirm that your {brand} plan has been renewed today for another year at {cur}{amt}. If you did not intend to renew, please respond within 24 hours.",
]


def gen_marketplace_or_delivery(rng: random.Random, scaff: dict) -> dict:
    target_len = _sample_length(scaff, rng)
    country = rng.choice(COUNTRIES)
    # Shift weight away from short SMS toward longer chat/email so that the
    # per-batch length p50 approaches the real neighbor mix (~280 chars).
    kind = rng.choices(["delivery_sms", "marketplace_chat", "refund_email"],
                       weights=[2, 4, 4])[0]
    use_url = rng.random() < scaff["url_rate"]

    if kind == "delivery_sms":
        carrier = rng.choice(CARRIERS)
        code = _fake_tracking(rng)
        fee = rng.choice(["1.99", "2.45", "3.75", "0.99", "1.50", "4.20"])
        cur = rng.choice(CURRENCIES)
        phone = f"+{rng.randint(1,44)} {rng.randint(1000,9999)} {rng.randint(100000,999999)}"
        pool = DELIVERY_SMS_WITH_URL if use_url else DELIVERY_SMS_NO_URL
        url = _pick_url(rng, scaff) if use_url else ""
        text = rng.choice(pool).format(carrier=carrier, code=code, url=url,
                                       cur=cur, fee=fee, phone=phone)
        persona, register = "fake_carrier", "impersonation_terse"
        platform = "sms"

    elif kind == "marketplace_chat":
        item = rng.choice(["iPhone 15 Pro", "PS5 console", "Peloton bike",
                           "Cartier watch", "Herman Miller chair", "Dyson V15",
                           "Bose QC Ultra", "MacBook Pro 16",
                           "Fender Stratocaster", "Bugaboo pram"])
        cur = rng.choice(CURRENCIES)
        price = rng.choice([180, 250, 320, 450, 620, 850, 1_200])
        overpay = price + rng.choice([200, 300, 450, 600])
        pool = MARKETPLACE_CHAT_WITH_URL if use_url else MARKETPLACE_CHAT_NO_URL
        url = _pick_url(rng, scaff) if use_url else ""
        opening = rng.choice(pool).format(item=item, cur=cur, price=price,
                                          overpay=overpay, url=url)
        # Follow up messages to reach real-length distribution (chat is often
        # multi-turn; smishing-neighbor p50 is ~280 chars, chat singles are ~140)
        follow_pool = [
            "I understand you may want to see the funds first. My bank will confirm the transfer within two working days.",
            "The pickup can be arranged for tomorrow or the day after, whichever suits you.",
            "I have done this before with another seller on the same platform, it works well.",
            "If you prefer to speak on the phone I can share my number, though I am in a different timezone.",
            "Please confirm the total including any handling or packaging fee.",
            "The item will be a gift so please do not include an invoice or receipt in the package.",
            "My shipper is a licensed agent, they will pay you in cash on collection if that is easier.",
            "I can also arrange the pickup this weekend if that is more convenient.",
        ]
        pool = list(follow_pool)
        rng.shuffle(pool)
        followups: list[str] = []
        for f in pool:
            if len(opening) + sum(len(x) + 2 for x in followups) >= target_len:
                break
            followups.append(f)
            if len(followups) >= 4:
                break
        text = opening + ("\n\n" + "\n".join(followups) if followups else "")
        persona, register = "fake_buyer", "casual_transactional"
        platform = "chat"

    else:  # refund_email
        brand = rng.choice(["Netflix", "Amazon", "PayPal", "Norton", "McAfee",
                            "AppleCare", "Microsoft 365", "Costco"])
        cur = rng.choice(CURRENCIES)
        amt = rng.choice([349, 429, 489, 599, 749, 899])
        greeting = _greeting(rng, scaff)
        body = rng.choice(REFUND_EMAIL_BLOCKS).format(brand=brand, cur=cur, amt=amt)
        url = _pick_url(rng, scaff) if use_url else ""
        # Add support-copy paragraphs to reach target length
        support_pool = [
            "If you have any questions about this charge, please refer to your account under the Billing tab.",
            "If you no longer wish to renew, you can manage your subscription at any time from the account settings.",
            "Please note that refunds are processed within 5-7 business days to your original method of payment.",
            "This message was sent to inform you of the recent activity on your account. Do not share your login details.",
            "You can review your recent order history and update your payment method from your account page.",
        ]
        parts = [greeting, body]
        pool = list(support_pool)
        rng.shuffle(pool)
        for s in pool:
            if len("\n\n".join(p for p in parts if p)) >= target_len * 0.8:
                break
            parts.append(s)
        if url:
            parts.append(f"Manage subscription: {url}")
        parts.append(f"Reference: {rng.randint(100000, 999999)}.")
        parts.append(rng.choice([f"{brand} Billing Support",
                                 f"{brand} Customer Care",
                                 f"{brand} Account Team", ""]))
        text = "\n\n".join(p for p in parts if p and p.strip())
        persona = f"fake_{brand.lower().replace(' ','_')}_billing"
        register = "impersonation_formal"
        platform = "email"

    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "marketplace_delivery_scam",
        "platform": platform,
        "persona": persona, "geography": country,
        "template_id": f"mkt_v2_{kind}",
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

CATEGORY_GENERATORS = {
    "bec_ceo_fraud": gen_bec,
    "romance_scam": gen_romance,
    "marketplace_delivery_scam": gen_marketplace_or_delivery,
}


def _fingerprint(text: str) -> str:
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    return " ".join(w.lower() for w in words[:12])


def generate(cat: str, gen_fn, scaff: dict, target: int,
             rng: random.Random) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for _ in range(target * 6):
        row = gen_fn(rng, scaff)
        row["text"] = "\n".join(l.rstrip() for l in row["text"].splitlines()).strip()
        # Strip any non-ASCII characters that leaked (safety net)
        row["text"] = row["text"].encode("ascii", "ignore").decode("ascii")
        fp = _fingerprint(row["text"])
        if fp in seen or len(row["text"]) < 30:
            continue
        seen.add(fp)
        out.append(row)
        if len(out) >= target:
            break
    return out


def batch_stats(rows: list[dict]) -> dict:
    if not rows:
        return {}
    texts = [r["text"] for r in rows]
    urls = [1 if URL_RE.search(t) else 0 for t in texts]
    emoji_re = re.compile(
        r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E0-\U0001F1FF]")
    emoji = [1 if emoji_re.search(t) else 0 for t in texts]
    emdash = [1 if "—" in t else 0 for t in texts]
    curly = [1 if "’" in t else 0 for t in texts]
    lens = [len(t) for t in texts]
    return {
        "n": len(rows),
        "len_p10": int(np.percentile(lens, 10)),
        "len_p50": int(np.percentile(lens, 50)),
        "len_p90": int(np.percentile(lens, 90)),
        "url_rate": round(sum(urls) / len(rows), 4),
        "emoji_rate": round(sum(emoji) / len(rows), 4),
        "emdash_rate": round(sum(emdash) / len(rows), 4),
        "curly_apostrophe_rate": round(sum(curly) / len(rows), 4),
    }


def main() -> None:
    rng = random.Random(SEED)
    scaff = load_scaffolding()
    manifest = {
        "batch_id": BATCH_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "supersedes": "batch1_20260731",
        "notes": (
            "Batch 1 v2. Regenerated to defeat the v1 probe (AUC 1.000 all 4). "
            "Style-matched to real nearest-neighbor scam corpora."),
        "targets_from_real_corpus": {
            cat: {"len_p50": s["len_percentiles"][50],
                  "url_rate": s["url_rate"]}
            for cat, s in scaff.items()
        },
        "counts": {},
        "achieved_stats": {},
    }
    for cat, gen_fn in CATEGORY_GENERATORS.items():
        rows = generate(cat, gen_fn, scaff[cat], TARGET_PER_CATEGORY, rng)
        outfile = OUT / f"{BATCH_ID}_{cat}.jsonl"
        with open(outfile, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        manifest["counts"][cat] = len(rows)
        manifest["achieved_stats"][cat] = batch_stats(rows)
        print(f"[batch1v2] {cat}: {len(rows)} rows -> {outfile}")
        print(f"           achieved: {manifest['achieved_stats'][cat]}")
    (OUT / f"{BATCH_ID}_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[batch1v2] manifest -> {OUT / f'{BATCH_ID}_manifest.json'}")


if __name__ == "__main__":
    main()
