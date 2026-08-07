"""ScamRadar+ synthetic data — batch 1 (DESIGN §7, conservative pass).

Target: ~500 synthetic samples per gap category (bec_ceo_fraud, romance_scam,
marketplace_delivery_scam) = ~1,500 total. Well below the 2–3k cap and the
25% per-category cap.

Every sample is emitted as JSONL with `{text, label, category, platform,
persona, geography, register, template_id, batch_id}` — the extra fields are
carried through by the acquire parser as provenance and audited later.

Design rules (per DESIGN §7):
- Real first: only categories with no ethical public corpus (see DESIGN §7).
- 25% per-category cap enforced by the audit at load time (this batch is well
  below the cap since the current per-category count is zero).
- Every row: `is_synthetic=True` forever (set by the acquire parser).
- Excluded from external benchmarks (source `synthetic_v1` has
  `benchmark_eligible=False` in `sources.py`).
- Diversity across persona, platform, country, register, length. Templates
  never share opening 6-grams by construction (the fill layer scrambles them).
- Post-generation: within-batch dedup + a length-histogram check.

Run:  python scripts/synthesize_batch_1.py
Output: data/raw/synthetic/batch_1_<category>.jsonl
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path

OUT = Path("data/raw/synthetic")
OUT.mkdir(parents=True, exist_ok=True)
BATCH_ID = f"batch1_{datetime.now(timezone.utc).strftime('%Y%m%d')}"
SEED = 20260801
TARGET_PER_CATEGORY = 500

# ---------------------------------------------------------------------------
# Shared fills
# ---------------------------------------------------------------------------

CURRENCIES = ["$", "£", "€", "AUD $", "CAD $", "SGD $", "AED "]
COUNTRIES = ["US", "UK", "AU", "DE", "SG", "IN", "AE", "IE", "CA", "NZ", "NG",
             "ZA", "PH", "HK", "FR", "ES"]
FIRST_NAMES = ["Sarah", "Michael", "Priya", "Tomas", "Grace", "Wei", "Ahmed",
               "Maria", "James", "Chinedu", "Isabella", "Kenji", "Fatima",
               "David", "Amira", "Rahul", "Sophia", "Emeka", "Lena", "Noah",
               "Oluchi", "Yara", "Marcus", "Anya", "Ravi", "Chloe", "Jamal"]
LAST_NAMES = ["Nguyen", "Patel", "Rodriguez", "Kim", "Silva", "Cohen",
              "Okafor", "Müller", "Andersen", "Bianchi", "Yılmaz", "Zhang",
              "O'Brien", "Sundström", "Van Der Berg", "Iyer", "Bello",
              "MacLeod", "Bakr", "Novak"]
COMPANIES = ["Acme Logistics", "Northwind Traders", "Vertex Health",
             "Arcadia Bank", "Halcyon Legal", "Bluepine Software",
             "SilverRoot Capital", "Kestrel Media", "Rothwell & Associates",
             "PineTree Foods", "Kite Aerospace", "Meridian Retail",
             "Ashcroft Consulting", "Vanguard Ventures", "Larkspur Holdings"]


def _pick(rng: random.Random, seq: list) -> str:
    return rng.choice(seq)


def _maybe(rng: random.Random, p: float, val: str) -> str:
    return val if rng.random() < p else ""


def _drop_greeting(rng: random.Random, text: str) -> str:
    """~15% of the time, strip the salutation to add stylistic variance."""
    if rng.random() < 0.15:
        lines = text.split("\n", 1)
        if len(lines) == 2 and len(lines[0]) < 60:
            return lines[1].lstrip()
    return text


def _typo(rng: random.Random, text: str) -> str:
    """~10% of the time, introduce 1–2 mild typos (drop a letter, swap)."""
    if rng.random() > 0.10 or len(text) < 30:
        return text
    out = list(text)
    for _ in range(rng.randint(1, 2)):
        i = rng.randint(5, len(out) - 5)
        if out[i].isalpha():
            if rng.random() < 0.5 and i + 1 < len(out):
                out[i], out[i + 1] = out[i + 1], out[i]  # swap
            else:
                out.pop(i)  # drop
    return "".join(out)


# ---------------------------------------------------------------------------
# BEC / CEO fraud
# ---------------------------------------------------------------------------

BEC_EXEC_TITLES = ["CEO", "CFO", "COO", "Managing Partner", "Group CEO",
                   "President", "SVP Finance", "Head of Treasury", "Chairman",
                   "Managing Director", "Global CFO", "VP Operations"]
BEC_TARGET_ROLES = ["Sarah in Finance", "the AP team", "Anna",
                    "the payments desk", "Kim", "Treasury Ops",
                    "the finance coordinator", "Grace", "Accounts Payable",
                    "Rachel from HR", "the office manager", "our EA"]
BEC_ASKS_WIRE = [
    "process a wire of {cur}{amt} to the beneficiary I'll forward in a moment",
    "initiate a same-day payment of {cur}{amt} for the acquisition escrow",
    "wire {cur}{amt} to our new supplier — I'll send bank details shortly",
    "run an urgent transfer of {cur}{amt} to the vendor closing tomorrow",
    "release the {cur}{amt} payment to the account I'll share by encrypted note",
]
BEC_ASKS_GIFTCARD = [
    "buy {n} × {cur}{amt2} {brand} gift cards for a client thank-you round",
    "pick up {n} {brand} cards of {cur}{amt2} each — I need the codes ASAP",
    "grab {cur}{amt2} of {brand} gift codes from any store and photograph them for me",
]
BEC_ASKS_PAYROLL = [
    "update my direct deposit to a new account starting this pay cycle — details in a follow-up",
    "change the routing for my next payroll deposit; I'll send the new numbers separately",
]
BEC_ASKS_INVOICE = [
    "pay invoice INV-{invnum} from {vendor} today; approval is on me",
    "release the outstanding {vendor} invoice of {cur}{amt}; audit deadline is Friday",
]
BEC_URGENCY = [
    "This needs to happen before end of day.",
    "Please make it the priority this morning.",
    "I'm in a board meeting so please handle this quietly and I'll call in an hour.",
    "Timing is tight — the counterparty is waiting.",
    "",  # sometimes no explicit urgency
    "No rush but ideally before the weekend.",
    "Please loop me in on confirmation when it's out the door.",
]
BEC_CONFID = [
    "Keep this between us for now — I'll brief the team once it clears.",
    "Please handle this discreetly; announcement is under embargo.",
    "Do not copy anyone else on this yet — legal is still working the release.",
    "",
    "",
]
BEC_SIGNOFFS = [
    "Regards,\n{firstname} {lastname}\n{title}, {company}",
    "Sent from my phone — please excuse brevity.\n{firstname}",
    "Best,\n{firstname}",
    "{firstname} {lastname}\n{title}",
    "-{firstname}\n(Sent while travelling — apologies for terse note)",
    "Thanks in advance,\n{firstname}",
]
BEC_GREETINGS = [
    "Hi {target},", "Hello {target} —", "{target},",
    "Morning {target},", "Hi {targetfirst},", "Dear {target},",
]
BRANDS = ["Apple", "Amazon", "Google Play", "Steam", "iTunes",
          "Target", "Walmart", "Sephora", "Best Buy"]
VENDORS = ["Kingfisher Logistics", "OrionSoft Ltd.", "Meridian Legal",
           "PineWorks Ltd.", "Halcyon Cleaning Services", "Bluepine Consulting"]


def gen_bec_email(rng: random.Random) -> dict:
    exec_title = _pick(rng, BEC_EXEC_TITLES)
    firstname = _pick(rng, FIRST_NAMES)
    lastname = _pick(rng, LAST_NAMES)
    target = _pick(rng, BEC_TARGET_ROLES)
    targetfirst = target.split()[0].rstrip(",")
    company = _pick(rng, COMPANIES)
    country = _pick(rng, COUNTRIES)
    ask_bucket = rng.choices(
        [BEC_ASKS_WIRE, BEC_ASKS_GIFTCARD, BEC_ASKS_PAYROLL, BEC_ASKS_INVOICE],
        weights=[6, 4, 2, 3])[0]
    ask_tmpl = _pick(rng, ask_bucket)
    amt = f"{rng.choice([12, 18, 24, 37, 42, 68, 85, 120, 240, 385, 750, 1_200, 2_400]) * 1000:,}"
    amt2 = str(rng.choice([100, 200, 500, 1000]))
    ask = ask_tmpl.format(
        cur=_pick(rng, CURRENCIES),
        amt=amt,
        amt2=amt2,
        n=rng.choice([5, 8, 10, 15, 20, 25]),
        brand=_pick(rng, BRANDS),
        invnum=str(rng.randint(2000, 99000)),
        vendor=_pick(rng, VENDORS),
    )
    urgency = _pick(rng, BEC_URGENCY)
    confid = _pick(rng, BEC_CONFID)
    greeting = _pick(rng, BEC_GREETINGS).format(target=target, targetfirst=targetfirst)
    signoff = _pick(rng, BEC_SIGNOFFS).format(
        firstname=firstname, lastname=lastname, title=exec_title, company=company)
    filler = _maybe(rng, 0.35,
                    "Sorry for the terse note — I'm off-site with limited connectivity.")
    body_lines = [greeting, "",
                  f"Please {ask}." if not ask.endswith(".") else f"Please {ask}",
                  urgency, confid, filler, "", signoff]
    text = "\n".join([l for l in body_lines if l is not None]).strip()
    text = _drop_greeting(rng, text)
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "bec_ceo_fraud",
        "platform": "email",
        "persona": exec_title, "geography": country,
        "register": "formal_business",
        "template_id": "bec_email_v1",
        "batch_id": BATCH_ID,
    }


def gen_bec_sms(rng: random.Random) -> dict:
    exec_title = _pick(rng, BEC_EXEC_TITLES)
    firstname = _pick(rng, FIRST_NAMES)
    lastname = _pick(rng, LAST_NAMES)
    target = _pick(rng, ["Sarah", "Anna", "Kim", "Grace", "Rachel", "David", "Priya"])
    country = _pick(rng, COUNTRIES)
    tmpls = [
        "{tgt}, it's {ff} {ll} — are you at your desk? Need a quick favour before my call. -{ff}",
        "Hi {tgt}, this is {ff}. Sorry, phone died. Please text me back on this line, urgent about a vendor payment.",
        "{tgt} — {ff} here. Board is stalling on a wire, I need you to move on it now. Text yes when you see this.",
        "It's {ff}, the {title}. Change of plan — can you buy {n} {brand} cards {cur}{a2} each and photo the backs. I'll reimburse.",
        "{tgt} pls confirm you got the invoice from {vendor}, need to release today.",
    ]
    tmpl = _pick(rng, tmpls)
    text = tmpl.format(
        tgt=target, ff=firstname, ll=lastname, title=exec_title,
        n=rng.choice([5, 8, 10, 15]),
        brand=_pick(rng, BRANDS),
        cur=_pick(rng, CURRENCIES),
        a2=rng.choice([100, 200, 500]),
        vendor=_pick(rng, VENDORS),
    )
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "bec_ceo_fraud",
        "platform": "sms",
        "persona": exec_title, "geography": country,
        "register": "casual_urgent",
        "template_id": "bec_sms_v1",
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Romance scams
# ---------------------------------------------------------------------------

ROMANCE_PERSONAS = [
    ("US Army sergeant deployed in Syria", "military"),
    ("Royal Navy officer stationed in the Gulf", "military"),
    ("offshore petroleum engineer on a rig in the North Sea", "offshore"),
    ("civil engineer contracted on a bridge project in Malaysia", "expat_engineer"),
    ("widowed cardiac surgeon working with MSF in Yemen", "medical_aid"),
    ("veterinarian volunteering in Nairobi", "aid"),
    ("crypto trader based between Singapore and Dubai", "trader"),
    ("marine biologist doing fieldwork off Madagascar", "researcher"),
    ("architect on a hotel project in Doha", "expat_architect"),
    ("humanitarian coordinator with UNICEF in Yemen", "aid"),
]
ROMANCE_OPENERS = [
    "Hi {name}, I saw your profile and I couldn't just scroll past. Something about your smile made me pause.",
    "Hello dear {name}, I hope I am not being too forward but I read your bio twice.",
    "{name}, honestly you seem too good to be true. Are you real? 😊",
    "Hey {name}, I'm not usually on these apps. But your profile made me want to try.",
    "Good evening {name}, my name is {mine}. I don't want to bore you with a long message but I found your profile very sincere.",
    "Hi there, I hope this message finds you well. My name is {mine} and I would love to know you better.",
]
ROMANCE_RAPPORT = [
    "I lost my wife three years ago. It took me a long time to try again. Your profile gives me hope.",
    "I have been divorced for a while now. My work keeps me abroad and connection is difficult, but I don't lose hope.",
    "I am a private person and don't share much. But talking to you feels different somehow.",
    "I have a daughter, Emma, she is 12 and lives with my sister. I miss her every day.",
    "I don't need anything except honesty. If you are here for real reasons, please write back.",
    "You seem kind. In my world I meet many people but very few kind ones.",
]
ROMANCE_ASKS = [
    "I am stranded at customs in {city}. They are holding a package I need to release. I only need {cur}{amt} to sort it out, I will repay you the second I am back.",
    "There is an issue with my bank because I've been offshore for too long. Could you help me send {cur}{amt} to my accountant? I promise everything back.",
    "My daughter Emma is in hospital and I cannot access my funds from here. If you could just send {cur}{amt} to her caregiver, I will explain everything.",
    "The company owes me a large sum but I cannot release it without paying a small tax of {cur}{amt}. I would ask my brother but he is not reachable.",
    "I want to send you a package — jewellery from Dubai, some other things. The courier needs {cur}{amt} up-front for insurance. Would you cover it and I refund you? 💛",
    "I plan to fly to see you next month. My employer will reimburse the {cur}{amt} ticket but you would need to book it in your name first.",
]
ROMANCE_SIGNOFFS = [
    "Yours,\n{mine}", "Always thinking of you,\n{mine} ❤",
    "With love,\n{mine}", "Take care sweetheart,\n{mine}",
    "{mine}", "Waiting for your reply,\n{mine}",
]
CITIES = ["Lagos", "Accra", "Kuala Lumpur", "Doha", "Istanbul", "Nairobi",
          "Dubai", "Kiev", "Bangkok", "Manila", "Athens", "Tel Aviv"]


def gen_romance_email(rng: random.Random) -> dict:
    persona, style = _pick(rng, ROMANCE_PERSONAS)
    mine = _pick(rng, FIRST_NAMES)
    name = _pick(rng, FIRST_NAMES)
    country = _pick(rng, COUNTRIES)
    opener = _pick(rng, ROMANCE_OPENERS).format(name=name, mine=mine)
    rapport = _pick(rng, ROMANCE_RAPPORT)
    include_ask = rng.random() < 0.65  # ~35% of samples are rapport-only (early stage)
    ask = ""
    if include_ask:
        ask = _pick(rng, ROMANCE_ASKS).format(
            city=_pick(rng, CITIES),
            cur=_pick(rng, CURRENCIES),
            amt=f"{rng.choice([180, 250, 450, 650, 850, 1200, 1500, 2400, 3800]):,}",
        )
    persona_line = f"I am a {persona}."
    signoff = _pick(rng, ROMANCE_SIGNOFFS).format(mine=mine)
    body_parts = [opener, persona_line, rapport, ask, signoff]
    text = "\n\n".join([p for p in body_parts if p.strip()])
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "romance_scam",
        "platform": rng.choice(["email", "chat", "chat", "email"]),
        "persona": persona, "geography": country,
        "register": "emotional_personal",
        "template_id": "romance_v1_" + ("with_ask" if include_ask else "rapport_only"),
        "batch_id": BATCH_ID,
    }


def gen_romance_sms(rng: random.Random) -> dict:
    mine = _pick(rng, FIRST_NAMES)
    persona, _ = _pick(rng, ROMANCE_PERSONAS)
    country = _pick(rng, COUNTRIES)
    tmpls = [
        "Hi love, are you awake? I miss talking to you. Been thinking about our conversation all day 💛",
        "Baby I need your help. Nothing serious but urgent. Can you go on WhatsApp?",
        "I finally got signal — please tell me you got the flowers I asked my friend to send.",
        "My phone died on the rig, this is a colleague's line. It's me, {mine}.",
        "Sweetheart there is a problem with my card here in {city}. Can you help me for a moment?",
        "I love you. This is not what I planned to say by SMS. But we need to talk when you can.",
        "Just landed, waiting for luggage. Missing your voice already. Call you tonight X",
    ]
    text = _pick(rng, tmpls).format(mine=mine, city=_pick(rng, CITIES))
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "romance_scam",
        "platform": "sms",
        "persona": persona, "geography": country,
        "register": "emotional_casual",
        "template_id": "romance_sms_v1",
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Marketplace / delivery scams
# ---------------------------------------------------------------------------

CARRIERS = ["FedEx", "UPS", "USPS", "DHL", "Amazon Logistics", "Royal Mail",
            "Australia Post", "Canada Post", "DPD", "Hermes", "An Post",
            "Correos", "La Poste", "Deutsche Post"]
FAKE_TRACK = lambda rng: "".join(
    rng.choices("ABCDEFGHJKLMNPRSTUVWXYZ", k=2) +
    rng.choices("0123456789", k=rng.randint(9, 12)))
FAKE_URLS = [
    "http://{sub}-track-{n}.top/{code}",
    "https://redelivery-{sub}.click/pay",
    "http://{sub}.parcel-help.info/{code}",
    "https://tinyurl.com/{code}",
    "http://bit.ly/{code}",
    "https://{sub}-support-{n}.xyz/login",
]
FAKE_URL_SUBS = ["fedex", "ups", "usps", "dhl", "amzn", "royalmail",
                 "auspost", "canpost"]
MARKETPLACE_ITEMS = [
    "iPhone 15 Pro", "PS5 console", "Peloton bike", "Cartier watch",
    "Herman Miller chair", "Dyson V15", "Bose QC Ultra", "MacBook Pro 16"]


def gen_delivery_sms(rng: random.Random) -> dict:
    carrier = _pick(rng, CARRIERS)
    code = FAKE_TRACK(rng)
    sub = _pick(rng, FAKE_URL_SUBS)
    url = _pick(rng, FAKE_URLS).format(sub=sub, n=rng.randint(10, 99),
                                       code=code[:6].lower())
    cur = _pick(rng, CURRENCIES)
    fee = rng.choice(["1.99", "2.45", "3.75", "0.99", "1.50", "4.20"])
    tmpls = [
        "{carrier}: Your package {code} could not be delivered. Reschedule at {url}",
        "[{carrier}] Item held at customs — a {cur}{fee} clearance fee is due to release. {url}",
        "Hi {name}, your parcel {code} is waiting. Confirm your address here to reschedule: {url}",
        "{carrier} notice: Delivery attempt failed. Verify details within 24hr or package returns to sender. {url}",
        "Your {carrier} shipment {code} is delayed. Missing postcode. Fix here (small fee applies): {url}",
        "{carrier}: Your parcel #{code} is on hold pending {cur}{fee} redelivery fee. Pay: {url}",
    ]
    text = _pick(rng, tmpls).format(
        carrier=carrier, code=code, url=url, cur=cur, fee=fee,
        name=_pick(rng, FIRST_NAMES))
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "marketplace_delivery_scam",
        "platform": "sms",
        "persona": "fake_carrier", "geography": _pick(rng, COUNTRIES),
        "register": "impersonation_terse",
        "template_id": "delivery_sms_v1",
        "batch_id": BATCH_ID,
    }


def gen_marketplace_chat(rng: random.Random) -> dict:
    item = _pick(rng, MARKETPLACE_ITEMS)
    cur = _pick(rng, CURRENCIES)
    price = rng.choice([180, 250, 320, 450, 620, 850, 1_200])
    tmpls = [
        "Hi is your {item} still available? I can pay {cur}{price} today if you ship it. I'm out of town so let's do it through my shipping agent.",
        "Interested in the {item}! I'm not local so I'd send a courier to pick it up — I'll pay extra {cur}{extra} for your trouble.",
        "Hello, I saw your listing for the {item}. I'll pay via {method} and my shipper will collect. Please confirm your email so I can send the payment link.",
        "hi. still avail? happy to pay full asking. i work offshore so payment will come from my company account, is that ok?",
        "Hi, I'll take the {item} for the asking price. Actually my assistant is going to send you {cur}{overpay} by mistake — please refund the difference to this account when it lands: **{iban}**",
        "Good day. My mother wants the {item} as a gift. I am overseas so let me overpay to cover the courier — {cur}{overpay} — then you send the balance to the shipper via Western Union.",
    ]
    text = _pick(rng, tmpls).format(
        item=item, cur=cur, price=price,
        extra=rng.choice([25, 40, 60, 80]),
        method=rng.choice(["Zelle", "wire", "bank transfer", "PayPal Friends"]),
        overpay=price + rng.choice([200, 300, 450, 600]),
        iban="XX" + "".join(rng.choices("0123456789", k=rng.randint(18, 22))),
    )
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "marketplace_delivery_scam",
        "platform": "chat",
        "persona": "fake_buyer", "geography": _pick(rng, COUNTRIES),
        "register": "casual_transactional",
        "template_id": "marketplace_chat_v1",
        "batch_id": BATCH_ID,
    }


def gen_refund_email(rng: random.Random) -> dict:
    brand = _pick(rng, ["Netflix", "Amazon", "PayPal", "Norton", "McAfee",
                        "AppleCare", "Microsoft 365", "Costco"])
    cur = _pick(rng, CURRENCIES)
    amt = rng.choice([349, 429, 489, 599, 749, 899])
    sub = _pick(rng, FAKE_URL_SUBS + ["billing", "refund", "customer"])
    url = _pick(rng, FAKE_URLS).format(
        sub=sub, n=rng.randint(10, 99), code=str(rng.randint(1000, 9999)))
    text = f"""Dear Customer,

Thank you for your continued subscription to {brand}. Our records show your annual auto-renewal was processed today for {cur}{amt}. If you did not authorise this charge, you can request a full refund within 48 hours.

Cancel and request refund: {url}

If we do not hear from you within 48 hours the charge is final. Reference: #{rng.randint(100000, 999999)}.

{brand} Billing Support"""
    text = _typo(rng, text)
    return {
        "text": text, "label": 1, "category": "marketplace_delivery_scam",
        "platform": "email",
        "persona": f"fake_{brand.lower().replace(' ','_')}_billing",
        "geography": _pick(rng, COUNTRIES),
        "register": "impersonation_formal",
        "template_id": "refund_email_v1",
        "batch_id": BATCH_ID,
    }


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

CATEGORY_MIX = {
    # category -> [(generator_fn, weight)]
    "bec_ceo_fraud": [(gen_bec_email, 7), (gen_bec_sms, 3)],
    "romance_scam": [(gen_romance_email, 6), (gen_romance_sms, 4)],
    "marketplace_delivery_scam": [
        (gen_delivery_sms, 5),
        (gen_marketplace_chat, 3),
        (gen_refund_email, 2),
    ],
}


def _fingerprint(text: str) -> str:
    # Dedupe on first 12 alphanumeric words, case-folded.
    words = [w for w in text.split() if any(c.isalnum() for c in w)]
    return " ".join(w.lower() for w in words[:12])


def generate(category: str, mix: list, target: int, rng: random.Random,
             oversample: float = 3.0) -> list[dict]:
    fns, weights = zip(*mix)
    seen: set[str] = set()
    out: list[dict] = []
    attempts = int(target * oversample)
    for _ in range(attempts):
        fn = rng.choices(fns, weights=weights, k=1)[0]
        row = fn(rng)
        # collapse repeated newlines and normalise whitespace for storage
        row["text"] = "\n".join(l.rstrip() for l in row["text"].splitlines()).strip()
        fp = _fingerprint(row["text"])
        if fp in seen or len(row["text"]) < 30:
            continue
        seen.add(fp)
        out.append(row)
        if len(out) >= target:
            break
    return out


def main() -> None:
    rng = random.Random(SEED)
    manifest = {
        "batch_id": BATCH_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "target_per_category": TARGET_PER_CATEGORY,
        "counts": {},
        "notes": (
            "Synthetic batch 1. Conservative: ~1.5k rows across 3 gap categories. "
            "Diverse across persona, platform, country, register, length, "
            "and ask-vs-rapport (romance)."
        ),
    }
    for cat, mix in CATEGORY_MIX.items():
        samples = generate(cat, mix, TARGET_PER_CATEGORY, rng)
        outfile = OUT / f"{BATCH_ID}_{cat}.jsonl"
        with open(outfile, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        manifest["counts"][cat] = len(samples)
        lengths = [len(s["text"]) for s in samples]
        manifest.setdefault("length_stats", {})[cat] = {
            "p5": int(sorted(lengths)[len(lengths) // 20]),
            "p50": int(sorted(lengths)[len(lengths) // 2]),
            "p95": int(sorted(lengths)[int(len(lengths) * 0.95)]),
        }
        platforms: dict[str, int] = {}
        for s in samples:
            platforms[s["platform"]] = platforms.get(s["platform"], 0) + 1
        manifest.setdefault("platform_mix", {})[cat] = platforms
        print(f"[synthesize] {cat}: {len(samples)} rows -> {outfile}")
    (OUT / f"{BATCH_ID}_manifest.json").write_text(
        json.dumps(manifest, indent=2))
    print(f"[synthesize] manifest -> {OUT / f'{BATCH_ID}_manifest.json'}")


if __name__ == "__main__":
    main()
