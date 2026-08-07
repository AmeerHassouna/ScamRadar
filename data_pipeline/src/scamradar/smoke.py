"""End-to-end smoke test on generated toy data. SANITY CHECK ONLY —
toy data must never be mixed with real data (it is written to data/raw/ and the
pipeline is run in-place; delete data/ afterwards or run in a scratch clone)."""
from __future__ import annotations

import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import clean, split, models, evaluate

SCAM_T = [
    "URGENT your {bank} account has been suspended verify now at {url}",
    "Congratulations you won a {prize}! claim here {url} before it expires",
    "Hi dear I saw your profile, I am a {job} working abroad, can we talk on whatsapp {phone}",
    "Your package {id} is held at customs, pay the fee at {url} within 24 hours",
    "I am the CEO, I need you to buy gift cards for clients immediately, keep this confidential",
    "Invest {amt} in bitcoin today and receive guaranteed 300% returns, contact {phone}",
    "We are hiring remote data entry, {amt}/week, just send a registration fee to start",
    "Your Netflix payment failed, update billing information at {url} to avoid suspension",
]
HAM_T = [
    "Hey are we still on for dinner {day}? Let me know",
    "Your order {id} has shipped and will arrive on {day}",
    "Meeting moved to {day} at 3pm, agenda attached, thanks",
    "Thanks for your purchase, your receipt total is {amt}",
    "Mom said to call her when you land, have a safe flight",
    "The quarterly report draft is ready for your review, comments welcome by {day}",
    "gg that last match was insane, queue again tonight?",
    "Reminder: your dentist appointment is on {day} at 10am, reply C to confirm",
]
FILL = dict(bank=["Chase", "HSBC", "Leumi", "PayPal"], url=["http://bit.ly/x{n}", "http://192.168.{n}.1/v", "https://secure-{n}.xyz/login"],
            prize=["iPhone 15", "$1000 gift card", "vacation"], job=["engineer", "doctor", "soldier"],
            phone=["+1 555 01{n}2", "+44 7700 9{n}00"], id=["#A{n}91", "#ZX{n}"], amt=["$450", "$1,200", "₪300"],
            day=["Monday", "Friday", "tomorrow"], n=None)


def _gen(n=700, seed=7):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        scam = i % 2 == 0
        t = rng.choice(SCAM_T if scam else HAM_T)
        for k, vals in FILL.items():
            if "{%s}" % k in t:
                v = str(rng.randint(10, 99)) if k == "n" else rng.choice(vals).replace("{n}", str(rng.randint(10, 99)))
                t = t.replace("{%s}" % k, v)
        vocab = ["ok", "please", "thanks", "regards", "asap", "friend", "today", "kindly",
                 "cheers", "best", "soon", "really", "honestly", "quick", "note", "update",
                 "info", "detail", "reply", "sure", "maybe", "later", "morning", "evening",
                 "weekend", "office", "team", "family", "trip", "photo", "ticket", "coffee"]
        t += " " + " ".join(rng.sample(vocab, rng.randint(5, 12)))
        rows.append(dict(sample_id=f"toy{i}", text=t, label=int(scam),
                         category="toy_scam" if scam else "toy_ham",
                         source="toy", license="n/a", is_synthetic=True,
                         era="modern", platform="mixed",
                         acquired_at=datetime.now(timezone.utc).isoformat()))
    return pd.DataFrame(rows)


def run():
    print("[smoke] generating toy dataset (NOT for real experiments)")
    Path("data/raw").mkdir(parents=True, exist_ok=True)
    _gen().to_parquet("data/raw/canonical.parquet", index=False)
    # toy data is synthetic -> temporarily mark source eligible so the benchmark carve-out is exercised
    import scamradar.sources as S
    S.SOURCES.append(S.Source("toy", "local://", "n/a", -1, "toy", "mixed", "modern",
                              False, benchmark_eligible=True))
    import scamradar.split as sp
    df_patch = pd.read_parquet("data/raw/canonical.parquet")
    df_patch["is_synthetic"] = False  # allow toy rows into toy benchmark
    df_patch.to_parquet("data/raw/canonical.parquet", index=False)

    clean.run()
    sp.run()
    bundle = models.fit_final("logreg", "F6")
    evaluate.run(str(bundle), "test")
    evaluate.run_external(str(bundle), force=True)
    print("[smoke] OK — pipeline runs end to end. Delete data/* before real runs.")
