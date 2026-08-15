-- ScamRadar+ relational schema
-- =============================================================================
-- This schema is used by both the initial-baseline database
-- (data/initial_db/scamradar_initial_253264.db, 253,264 rows) and the final
-- E8-P9 database (data/final_db/scamradar_e8p9.db, 283,501 rows). The two
-- database files themselves are not committed to Git — each is ~200-250 MB.
-- Both are reproducible from the shipped `scripts/data_prep/build_databases.py`
-- given the parquet inputs under `data/canonical/` and `data/interim/`.

-- ---------------------------------------------------------------------------
-- Source: catalog of every acquisition source that contributed rows.
-- The initial database has 14 rows here (13 real-world corpora + 1 synthetic
-- seed `synthetic_v1`). The final E8-P9 database has 17 rows here — the
-- 12 real-world sources that survived the E8-P3 spamassassin_ham removal, a
-- catch-all `e5_base_corpus` row for legacy rows without a specific source
-- label, and 4 new synthetic-source rows produced by the E8-P2 / E8-P6 /
-- E8-P8 augmentation batches (synthetic_e8p2_legit, synthetic_e8p6_legit,
-- synthetic_e8p8_scam, synthetic_e8p8_pair).
-- ---------------------------------------------------------------------------
CREATE TABLE Source (
    source_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name   TEXT    NOT NULL UNIQUE,
    source_type   TEXT    NOT NULL CHECK (source_type IN ('real','synthetic')),
    era           TEXT,
    license       TEXT
);

-- ---------------------------------------------------------------------------
-- Message: one row per message in the corpus. `split` labels the row's
-- partition (train / val / test / external); `cluster_id` is preserved from
-- the cluster-aware split step for provenance and near-duplicate reasoning.
-- ---------------------------------------------------------------------------
CREATE TABLE Message (
    message_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    text          TEXT    NOT NULL,
    label         INTEGER NOT NULL CHECK (label IN (0,1)),
    split         TEXT    NOT NULL CHECK (split IN ('train','val','test','external')),
    cluster_id    INTEGER,
    source_id     INTEGER NOT NULL,
    FOREIGN KEY (source_id) REFERENCES Source(source_id)
);

CREATE INDEX idx_message_label  ON Message(label);
CREATE INDEX idx_message_source ON Message(source_id);
CREATE INDEX idx_message_split  ON Message(split);

-- ---------------------------------------------------------------------------
-- MessageFeatures: the 25 engineered numerical features computed by
-- src/rule_engine/numerical_features.py (tone × 4, url × 5, phrase × 3,
-- text-stats × 13). One row per message; message_id is both PK and FK.
-- ---------------------------------------------------------------------------
CREATE TABLE MessageFeatures (
    message_id                 INTEGER PRIMARY KEY,
    text_length                INTEGER,
    word_count                 INTEGER,
    has_url                    INTEGER,
    url_count                  INTEGER,
    exclamation_count          INTEGER,
    uppercase_ratio            REAL,
    digit_ratio                REAL,
    urgency_score              REAL,
    tone_urgency               INTEGER,
    tone_fear                  INTEGER,
    tone_reward                INTEGER,
    tone_threat                INTEGER,
    url_suspicious_tld         INTEGER,
    url_suspicious_keyword     INTEGER,
    url_has_ip                 INTEGER,
    scam_phrase_score          INTEGER,
    sender_impersonation_score INTEGER,
    legit_phrase_score         INTEGER,
    avg_word_length            REAL,
    capitalized_word_count     INTEGER,
    punctuation_density        REAL,
    question_mark_count        INTEGER,
    currency_symbol_count      INTEGER,
    readability_score          REAL,
    unique_word_ratio          REAL,
    FOREIGN KEY (message_id) REFERENCES Message(message_id)
);
