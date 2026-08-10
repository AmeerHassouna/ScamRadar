"""Dataset source registry — every source has documented URL + license (spec §1).

NO KAGGLE. Sources are either directly downloadable (`auto=True`) or documented
for manual download (`auto=False`, with instructions). Parsers normalize every
source into the canonical schema:

    sample_id, text, label (1=scam, 0=legit), category, source, license,
    is_synthetic, era, platform, acquired_at
"""
from dataclasses import dataclass, field


@dataclass
class Source:
    name: str
    url: str
    license: str
    label: int                  # 1 scam, 0 legit, -1 mixed (parser decides per-row)
    category: str               # default category; parser may override per-row
    platform: str               # email | sms | chat | job_posting | mixed
    era: str                    # modern | legacy
    auto: bool                  # True = downloadable by acquire.py directly
    notes: str = ""
    benchmark_eligible: bool = True  # may be reserved for the external benchmark


SOURCES: list[Source] = [
    # ----------------------------- SCAM ----------------------------------
    Source(
        name="sms_spam_collection",
        url="https://archive.ics.uci.edu/static/public/228/sms+spam+collection.zip",
        license="CC BY 4.0 (Almeida & Gomez Hidalgo, UCI SMS Spam Collection)",
        label=-1, category="smishing", platform="sms", era="legacy", auto=True,
        notes="UCI ML Repository direct download (dataset 228). Zip contains "
              "SMSSpamCollection (tab-separated <label>\\t<text>). "
              "Legacy: weight-capped via era tag.",
    ),
    # ---- Zenodo record 8339691 (Champa/Rabbi/Zibran 2024, CC BY 4.0) ----
    # We split the record into per-corpus sources so era tags stay honest
    # (Nazario_5 is the 2020s refresh; Nazario proper is the legacy set).
    Source(
        name="zenodo_champa_nazario_legacy",
        url="https://zenodo.org/api/records/8339691/files/Nazario.csv/content",
        license="CC BY 4.0 (Champa, Rabbi & Zibran 2024; underlying Nazario corpus)",
        label=1, category="email_phishing", platform="email", era="legacy", auto=True,
        notes="Nazario base corpus (older phishing emails).",
    ),
    Source(
        name="zenodo_champa_nazario_modern",
        url="https://zenodo.org/api/records/8339691/files/Nazario_5.csv/content",
        license="CC BY 4.0 (Champa, Rabbi & Zibran 2024; Nazario 5 refresh)",
        label=1, category="email_phishing", platform="email", era="modern", auto=True,
        notes="Nazario 5 = 2020s refresh subset of the Nazario corpus.",
    ),
    Source(
        name="zenodo_champa_nigerian_fraud_legacy",
        url="https://zenodo.org/api/records/8339691/files/Nigerian_Fraud.csv/content",
        license="CC BY 4.0 (Champa, Rabbi & Zibran 2024; Nigerian fraud base)",
        label=1, category="advance_fee_fraud", platform="email", era="legacy", auto=True,
        notes="419 / advance-fee scam emails (classic set).",
    ),
    Source(
        name="zenodo_champa_nigerian_fraud_modern",
        url="https://zenodo.org/api/records/8339691/files/Nigerian_5.csv/content",
        license="CC BY 4.0 (Champa, Rabbi & Zibran 2024; Nigerian 5 refresh)",
        label=1, category="advance_fee_fraud", platform="email", era="modern", auto=True,
        notes="Advance-fee scam emails, 2020s refresh subset.",
    ),
    Source(
        name="zenodo_champa_ceas08",
        url="https://zenodo.org/api/records/8339691/files/CEAS_08.csv/content",
        license="CC BY 4.0 (Champa, Rabbi & Zibran 2024; underlying CEAS 2008 corpus)",
        label=-1, category="email_phishing", platform="email", era="legacy", auto=True,
        notes="CEAS 2008 spam-challenge emails (labels 0/1).",
    ),
    Source(
        name="zenodo_miltchev_phishing_2024",
        url="https://zenodo.org/records/13474746/files/Phishing_validation_emails.csv?download=1",
        license="CC BY 4.0 (Miltchev, Rangelov & Genchev 2024; Zenodo 13474746)",
        label=-1, category="email_phishing", platform="email", era="modern", auto=True,
        notes="2,000 modern (Aug-2024) phishing validation emails, labelled "
              "'Safe Email' / 'Phishing Email'.",
    ),
    Source(
        name="mendeley_sms_phishing_2022",
        url="https://data.mendeley.com/public-files/datasets/f45bkkt8pr/files/edb361de-918d-469f-9106-e84823830665/file_downloaded",
        license="CC BY 4.0 (Mishra & Soni 2022; Mendeley dataset f45bkkt8pr v1)",
        label=-1, category="smishing", platform="sms", era="modern", auto=True,
        notes="Dataset_5971.zip — modern smishing corpus.",
    ),
    Source(
        name="emscad_job_scams",
        # Retrieval mirror: FelixLuciano/Fake-JobPosting-Prediction on GitHub.
        # Underlying dataset is EMSCAD (Vidros et al. 2017, University of the
        # Aegean, published for research use). NOT the Kaggle site.
        url="https://raw.githubusercontent.com/FelixLuciano/Fake-JobPosting-Prediction/main/src/dataset/fake_job_postings.csv",
        license="EMSCAD research use (Vidros et al. 2017, University of the Aegean); GitHub mirror",
        label=-1, category="recruitment_scam", platform="job_posting", era="legacy", auto=True,
        notes="17,880 real job ads (866 fraudulent). Aegean HTTPS cert is broken; "
              "we mirror via GitHub while citing the original research publication.",
    ),
    Source(
        name="clair_fraud_email",
        url="https://aclweb.org/aclwiki/CLAIR_collection_of_fraud_email",
        license="Research use",
        label=1, category="advance_fee_fraud", platform="email", era="legacy", auto=False,
        notes="Advance-fee / 419 fraud; mbox into data/raw/clair/.",
    ),
    # -------------------------- LEGITIMATE --------------------------------
    Source(
        name="spamassassin_ham",
        url="https://spamassassin.apache.org/old/publiccorpus/",
        license="Apache 2.0 (SpamAssassin Public Corpus)",
        label=0, category="ham_email", platform="email", era="legacy", auto=True,
        notes="Auto-downloads easy_ham + hard_ham tarballs from the Apache public corpus.",
    ),
    Source(
        name="multiwoz_v22",
        # MIT-licensed multi-domain task-oriented dialogue (2020+). Auto-converted
        # parquet mirror from HuggingFace of the canonical Budzianowski et al. repo.
        url="https://huggingface.co/datasets/pfb30/multi_woz_v22/resolve/refs%2Fconvert%2Fparquet/v2.2",
        license="MIT (Budzianowski et al. 2018-2020; MultiWOZ 2.2)",
        label=0, category="ham_chat", platform="chat", era="modern", auto=True,
        notes="~10k task-oriented dialogues; parser flattens nested `turns[*].utterance` "
              "into per-utterance ham_chat rows.",
    ),
    Source(
        name="dailydialog",
        # Original host yanran.li is now a parked domain. We use the HuggingFace
        # auto-generated parquet mirror (refs/convert/parquet branch of the
        # canonical `li2017dailydialog/daily_dialog` dataset).
        url="https://huggingface.co/datasets/li2017dailydialog/daily_dialog/resolve/refs%2Fconvert%2Fparquet/default",
        # CC BY-NC-SA 4.0 — non-commercial. This project is an offline research
        # system (DESIGN §11); commercial deployment would require re-licensing
        # or removing this source.
        license="CC BY-NC-SA 4.0 (Li et al. 2017, IJCNLP DailyDialog) — non-commercial only",
        label=0, category="ham_chat", platform="chat", era="modern", auto=True,
        benchmark_eligible=False,  # NC clause makes benchmark redistribution risky
        notes="13k multi-turn dialogues on daily topics. Each utterance becomes "
              "one ham_chat row (min length filter). Parquet mirror auto-generated "
              "by HuggingFace from the canonical dataset.",
    ),
    Source(
        name="enron_ham_sample",
        url="https://raw.githubusercontent.com/MWiechmann/enron_spam_data/master/enron_spam_data.zip",
        license="Public record (FERC release); repo MIT",
        label=-1, category="ham_email", platform="email", era="legacy", auto=True,
        notes="Enron ham + spam split prepared by Wiechmann (GitHub). Parser keeps both labels.",
    ),
    # --------------------------- SYNTHETIC --------------------------------
    Source(
        name="synthetic_v1",
        url="local://data/raw/synthetic/",
        license="Project-generated (no restrictions)",
        label=-1, category="mixed", platform="mixed", era="modern", auto=False,
        benchmark_eligible=False,   # synthetic never enters the external benchmark
        notes="LLM-generated fill-in for categories lacking public corpora (BEC, romance, "
              "delivery/marketplace smishing, giveaway, refund, charity, Discord ham, family "
              "chat ham...). Generate with scripts/gen_synthetic_prompts.md; JSONL with "
              "fields text,label,category,platform.",
    ),
]


def get(name: str) -> Source:
    for s in SOURCES:
        if s.name == name:
            return s
    raise KeyError(name)
