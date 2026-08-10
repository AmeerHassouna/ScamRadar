"""Stage 0 — acquisition. Downloads auto sources, ingests manually-placed ones,
emits canonical parquet in data/raw/canonical.parquet with full provenance."""
from __future__ import annotations

import email
import hashlib
import io
import json
import mailbox
import re
import tarfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .sources import SOURCES, Source

RAW = Path("data/raw")
CANON_COLS = ["sample_id", "text", "label", "category", "source", "license",
              "is_synthetic", "era", "platform", "acquired_at"]


def _sid(text: str) -> str:
    return hashlib.sha1(text.strip().lower().encode("utf-8", "ignore")).hexdigest()


def _rows(texts, labels, cats, src: Source, synthetic=False, platforms=None):
    now = datetime.now(timezone.utc).isoformat()
    return pd.DataFrame({
        "sample_id": [_sid(t) for t in texts],
        "text": texts, "label": labels, "category": cats,
        "source": src.name, "license": src.license,
        "is_synthetic": synthetic, "era": src.era,
        "platform": platforms if platforms is not None else src.platform,
        "acquired_at": now,
    })


# ------------------------- per-source parsers ---------------------------

def parse_sms_spam_collection(src: Source) -> pd.DataFrame | None:
    """UCI ML Repository direct download (dataset 228). The zip contains a
    tab-separated `SMSSpamCollection` file: <label>\\t<text> per line, where
    label is 'ham' or 'spam'. UCI's HTTPS needs the certifi CA bundle."""
    import ssl
    import urllib.request
    import certifi
    dest = RAW / "sms_spam_collection.zip"
    if not dest.exists():
        try:
            ctx = ssl.create_default_context(cafile=certifi.where())
            req = urllib.request.Request(src.url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp, open(dest, "wb") as f:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:  # offline / blocked
            print(f"[acquire] {src.name}: download failed ({e}); skipping")
            if dest.exists() and dest.stat().st_size == 0:
                dest.unlink()
            return None
    with zipfile.ZipFile(dest) as z:
        with z.open("SMSSpamCollection") as fh:
            lines = fh.read().decode("utf-8", "ignore").splitlines()
    raw_labels: list[str] = []
    texts: list[str] = []
    for line in lines:
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            raw_labels.append(parts[0])
            texts.append(parts[1])
    labels = [1 if lbl == "spam" else 0 for lbl in raw_labels]
    cats = ["smishing" if l == 1 else "ham_sms" for l in labels]
    return _rows(texts, labels, cats, src)


def parse_enron_ham_sample(src: Source) -> pd.DataFrame | None:
    import urllib.request
    dest = RAW / "enron_spam_data.zip"
    if not dest.exists():
        try:
            urllib.request.urlretrieve(src.url, dest)
        except Exception as e:
            print(f"[acquire] {src.name}: download failed ({e}); skipping")
            return None
    with zipfile.ZipFile(dest) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        df = pd.read_csv(io.BytesIO(z.read(name)))
    df["text"] = (df["Subject"].fillna("") + "\n" + df["Message"].fillna("")).str.strip()
    df = df[df.text.str.len() > 0]
    labels = (df["Spam/Ham"].str.lower() == "spam").astype(int)
    cats = ["email_spam" if l == 1 else "ham_email" for l in labels]
    return _rows(df.text.tolist(), labels.tolist(), cats, src)


def parse_local_csv_dir(src: Source, subdir: str, text_col: str, label_col: str,
                        scam_value, cat_fn) -> pd.DataFrame | None:
    d = RAW / subdir
    files = list(d.glob("*.csv")) if d.exists() else []
    if not files:
        print(f"[acquire] {src.name}: no files in {d} — see sources.py notes; skipping")
        return None
    frames = []
    for f in files:
        df = pd.read_csv(f)
        if text_col not in df or label_col not in df:
            continue
        labels = (df[label_col] == scam_value).astype(int)
        cats = [cat_fn(l) for l in labels]
        frames.append(_rows(df[text_col].astype(str).tolist(), labels.tolist(), cats, src))
    return pd.concat(frames, ignore_index=True) if frames else None


_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
       "(KHTML, like Gecko) Version/17.0 Safari/605.1.15")


def _download(url: str, dest: Path, label: str) -> bool:
    """Idempotent download. Returns True if dest exists after the call.
    Sends a browser User-Agent because some sources (e.g. Mendeley) 403 the
    default urllib UA."""
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
        return True
    except Exception as e:
        print(f"[acquire] {label}: download failed ({e}); skipping")
        if dest.exists() and dest.stat().st_size == 0:
            dest.unlink()
        return False


def parse_zenodo_csv(src: Source) -> pd.DataFrame | None:
    """Parser for a single Zenodo curated-phishing CSV.
    Schema: sender, receiver, date, subject, body, urls, label."""
    dest = RAW / "zenodo_champa" / f"{src.name}.csv"
    if not _download(src.url, dest, src.name):
        return None
    df = pd.read_csv(dest, low_memory=False)
    if "body" not in df.columns:
        print(f"[acquire] {src.name}: unexpected schema {list(df.columns)}; skipping")
        return None
    text = (df.get("subject", "").fillna("").astype(str) + "\n"
            + df["body"].fillna("").astype(str)).str.strip()
    keep = text.str.len() > 0
    text = text[keep]
    if "label" in df.columns:
        raw = pd.to_numeric(df.loc[keep, "label"], errors="coerce").fillna(-1).astype(int)
    else:
        raw = pd.Series([src.label] * len(text), index=text.index)
    labels: list[int] = []
    cats: list[str] = []
    for lbl in raw:
        if src.label in (0, 1):
            labels.append(src.label)
        else:
            labels.append(int(lbl == 1))
        # per-row category: scam rows keep the source's category, ham rows -> ham_email
        cats.append(src.category if labels[-1] == 1 else "ham_email")
    return _rows(text.tolist(), labels, cats, src)


def parse_spamassassin_ham(src: Source) -> pd.DataFrame | None:
    """Downloads easy_ham + hard_ham tarballs from the Apache public corpus and
    parses every embedded RFC822 message. `email_spam` from Enron already covers
    the spam side, so this source contributes ham only."""
    base = "https://spamassassin.apache.org/old/publiccorpus/"
    tars = [
        ("20030228_easy_ham.tar.bz2", "easy_ham"),
        ("20030228_hard_ham.tar.bz2", "hard_ham"),
    ]
    d = RAW / "spamassassin"
    d.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    for tarname, _label in tars:
        dest = d / tarname
        if not _download(base + tarname, dest, f"{src.name}:{tarname}"):
            continue
        with tarfile.open(dest, "r:bz2") as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                # each mail is a single file under easy_ham/ or hard_ham/
                try:
                    raw = tf.extractfile(member).read()
                except Exception:
                    continue
                msg = email.message_from_bytes(raw)
                subj = str(msg.get("Subject", "") or "")
                body_parts: list[str] = []
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                body_parts.append(part.get_payload(decode=True)
                                                  .decode(part.get_content_charset() or
                                                          "utf-8", "ignore"))
                            except Exception:
                                pass
                else:
                    try:
                        payload = msg.get_payload(decode=True)
                        if payload is not None:
                            body_parts.append(payload.decode(
                                msg.get_content_charset() or "utf-8", "ignore"))
                        else:
                            body_parts.append(str(msg.get_payload() or ""))
                    except Exception:
                        pass
                text = (subj + "\n" + "\n".join(body_parts)).strip()
                if text:
                    texts.append(text)
    if not texts:
        return None
    labels = [0] * len(texts)
    cats = ["ham_email"] * len(texts)
    return _rows(texts, labels, cats, src)


def parse_mendeley_sms(src: Source) -> pd.DataFrame | None:
    """Downloads Dataset_5971.zip from Mendeley (CC BY 4.0) and extracts the CSV
    inside. Column names vary between versions; we detect text + label heuristically."""
    dest = RAW / "mendeley_sms" / "Dataset_5971.zip"
    if not _download(src.url, dest, src.name):
        return None
    with zipfile.ZipFile(dest) as z:
        csv_names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            print(f"[acquire] {src.name}: no CSV inside zip; contents={z.namelist()}")
            return None
        # Prefer the largest CSV (main dataset)
        csv_names.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
        with z.open(csv_names[0]) as fh:
            df = pd.read_csv(fh, encoding="utf-8", low_memory=False,
                             on_bad_lines="skip")
    text_col = next((c for c in df.columns
                     if c.lower() in ("text", "message", "sms", "body", "content")),
                    None)
    label_col = next((c for c in df.columns
                      if c.lower() in ("label", "type", "class", "is_spam", "target",
                                       "labeltype", "labels")),
                     None)
    if text_col is None or label_col is None:
        print(f"[acquire] {src.name}: could not identify text/label columns "
              f"in {list(df.columns)}")
        return None
    text = df[text_col].astype(str).str.strip()
    keep = text.str.len() > 0
    text = text[keep]
    raw_labels = df.loc[keep, label_col].astype(str).str.lower().str.strip()
    is_scam = raw_labels.isin({"smishing", "spam", "1", "phishing", "scam", "true"})
    labels = is_scam.astype(int).tolist()
    cats = ["smishing" if l == 1 else "ham_sms" for l in labels]
    return _rows(text.tolist(), labels, cats, src)


def parse_emscad(src: Source) -> pd.DataFrame | None:
    """Downloads EMSCAD (Vidros et al. 2017) via the GitHub mirror.
    17,880 job ads with `fraudulent ∈ {0,1}`. Positive rows → recruitment_scam.
    Negative rows → ham_job_posting (out-of-taxonomy — recorded honestly)."""
    dest = RAW / "emscad" / "fake_job_postings.csv"
    if not _download(src.url, dest, src.name):
        return None
    df = pd.read_csv(dest, low_memory=False)
    if "fraudulent" not in df.columns or "description" not in df.columns:
        print(f"[acquire] {src.name}: unexpected schema {list(df.columns)}")
        return None
    parts = []
    for col in ("title", "company_profile", "description", "requirements", "benefits"):
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str))
    text = parts[0]
    for p in parts[1:]:
        text = text + "\n" + p
    text = text.str.strip()
    keep = text.str.len() >= 20
    text = text[keep]
    labels = df.loc[keep, "fraudulent"].astype(int).tolist()
    cats = ["recruitment_scam" if l == 1 else "ham_job_posting" for l in labels]
    return _rows(text.tolist(), labels, cats, src)


def parse_dailydialog(src: Source) -> pd.DataFrame | None:
    """Downloads DailyDialog parquet shards from the HuggingFace auto-conversion
    branch. Each dialogue is an array of utterances; every utterance ≥ 20 chars
    is emitted as one `ham_chat` row (with within-source dedup)."""
    base = src.url.rstrip("/")
    d = RAW / "dailydialog"
    d.mkdir(parents=True, exist_ok=True)
    utterances: list[str] = []
    for split in ("train", "validation", "test"):
        # Each split is sharded; try shards 0000..0009 and stop on first 404.
        for shard in range(10):
            url = f"{base}/{split}/{shard:04d}.parquet"
            dest = d / f"{split}_{shard:04d}.parquet"
            if not _download(url, dest, f"{src.name}:{split}/{shard:04d}"):
                break
            df = pd.read_parquet(dest)
            for arr in df["dialog"]:
                for utt in arr:
                    u = re.sub(r"\s+", " ", str(utt)).strip()
                    # Chat utterances shorter than 40 chars cluster too aggressively
                    # ("Yes please", "Thank you", "Can I have the reference number?")
                    # and blow past the cluster-dominance cap. Kept: substantive turns.
                    if len(u) >= 40:
                        utterances.append(u)
    if not utterances:
        return None
    seen: set[str] = set()
    dedup: list[str] = []
    for u in utterances:
        k = u.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(u)
    labels = [0] * len(dedup)
    cats = ["ham_chat"] * len(dedup)
    return _rows(dedup, labels, cats, src)


def parse_miltchev_phishing_2024(src: Source) -> pd.DataFrame | None:
    """Miltchev/Rangelov/Genchev 2024 phishing validation emails (Zenodo 13474746).
    Schema: `Email Text` + `Email Type` ∈ {"Safe Email", "Phishing Email"}."""
    dest = RAW / "zenodo_miltchev" / "Phishing_validation_emails.csv"
    if not _download(src.url, dest, src.name):
        return None
    df = pd.read_csv(dest, low_memory=False)
    text_col = next((c for c in df.columns if "text" in c.lower()), None)
    label_col = next((c for c in df.columns if "type" in c.lower() or "label" in c.lower()), None)
    if text_col is None or label_col is None:
        print(f"[acquire] {src.name}: unexpected schema {list(df.columns)}")
        return None
    text = df[text_col].astype(str).str.strip()
    keep = text.str.len() > 0
    text = text[keep]
    raw = df.loc[keep, label_col].astype(str).str.lower()
    labels = raw.str.contains("phish").astype(int).tolist()
    cats = ["email_phishing" if l == 1 else "ham_email" for l in labels]
    return _rows(text.tolist(), labels, cats, src)


def parse_multiwoz(src: Source) -> pd.DataFrame | None:
    """Downloads MultiWOZ 2.2 parquet shards from the HuggingFace conversion
    branch. Nested schema: each row is a dialogue with `turns.utterance` array.
    Emits every utterance ≥ 20 chars as one `ham_chat` row (with dedup)."""
    base = src.url.rstrip("/")
    d = RAW / "multiwoz"
    d.mkdir(parents=True, exist_ok=True)
    utterances: list[str] = []
    for split in ("train", "validation", "test"):
        for shard in range(20):  # MultiWOZ train has ~2 shards
            url = f"{base}/{split}/{shard:04d}.parquet"
            dest = d / f"{split}_{shard:04d}.parquet"
            if not _download(url, dest, f"{src.name}:{split}/{shard:04d}"):
                break
            df = pd.read_parquet(dest)
            for turns in df["turns"]:
                # turns is a struct with an `utterance` array-of-strings
                arr = turns.get("utterance") if hasattr(turns, "get") else turns["utterance"]
                for utt in arr:
                    u = re.sub(r"\s+", " ", str(utt)).strip()
                    # Chat utterances shorter than 40 chars cluster too aggressively
                    # ("Yes please", "Thank you", "Can I have the reference number?")
                    # and blow past the cluster-dominance cap. Kept: substantive turns.
                    if len(u) >= 40:
                        utterances.append(u)
    if not utterances:
        return None
    seen: set[str] = set()
    dedup: list[str] = []
    for u in utterances:
        k = u.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(u)
    labels = [0] * len(dedup)
    cats = ["ham_chat"] * len(dedup)
    return _rows(dedup, labels, cats, src)


def parse_synthetic(src: Source) -> pd.DataFrame | None:
    d = RAW / "synthetic"
    files = list(d.glob("*.jsonl")) if d.exists() else []
    if not files:
        print(f"[acquire] {src.name}: no synthetic JSONL yet; skipping")
        return None
    rows = []
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    return _rows(df.text.tolist(), df.label.tolist(), df.category.tolist(), src,
                 synthetic=True, platforms=df.get("platform", src.platform))


PARSERS = {
    "sms_spam_collection": parse_sms_spam_collection,
    "enron_ham_sample": parse_enron_ham_sample,
    "mendeley_sms_phishing_2022": parse_mendeley_sms,
    "spamassassin_ham": parse_spamassassin_ham,
    "zenodo_champa_nazario_legacy": parse_zenodo_csv,
    "zenodo_champa_nazario_modern": parse_zenodo_csv,
    "zenodo_champa_nigerian_fraud_legacy": parse_zenodo_csv,
    "zenodo_champa_nigerian_fraud_modern": parse_zenodo_csv,
    "zenodo_champa_ceas08": parse_zenodo_csv,
    "zenodo_miltchev_phishing_2024": parse_miltchev_phishing_2024,
    "emscad_job_scams": parse_emscad,
    "dailydialog": parse_dailydialog,
    "multiwoz_v22": parse_multiwoz,
    "synthetic_v1": parse_synthetic,
}


def run() -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    frames, manifest = [], []
    for src in SOURCES:
        parser = PARSERS.get(src.name)
        if parser is None:
            print(f"[acquire] {src.name}: manual-only (see notes), no parser wired; skipping")
            continue
        df = parser(src)
        if df is not None and len(df):
            frames.append(df)
            manifest.append({"source": src.name, "url": src.url, "license": src.license,
                             "rows": int(len(df)), "era": src.era,
                             "benchmark_eligible": src.benchmark_eligible})
            print(f"[acquire] {src.name}: {len(df)} rows")
    if not frames:
        raise SystemExit("No sources acquired. Place manual datasets per sources.py notes.")
    canon = pd.concat(frames, ignore_index=True)[CANON_COLS]
    out = RAW / "canonical.parquet"
    canon.to_parquet(out, index=False)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/acquisition_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[acquire] canonical dataset: {len(canon)} rows -> {out}")
    return out
