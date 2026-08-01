"""
ScamRadar+ | Step 00: Deduplication.

Provides normalised-text hashing and cluster-level deduplication.
Intervention 1a — removes template repetition that inflates internal metrics.

Two functions do the whole job:
  add_cluster_ids(df)   → adds 'norm_text' and 'cluster_id' columns
  dedup_by_cluster(df)  → keeps one representative per cluster (longest raw_text)
"""

import re
import hashlib


_URL_RE   = re.compile(r'https?://\S+')
_DIGIT_RE = re.compile(r'\d+')
_WS_RE    = re.compile(r'\s+')


def normalise_text(t) -> str:
    """
    Loose normalisation for exact-match dedup detection.
      lowercase → URLs→URL → digits→NUM → whitespace collapsed.
    Deliberately does NOT strip punctuation or email quotes — those catch
    only ~2% more duplicates but risk over-collapsing semantically distinct rows.
    """
    if not isinstance(t, str):
        return ''
    t = t.lower()
    t = _URL_RE.sub(' URL ', t)
    t = _DIGIT_RE.sub(' NUM ', t)
    t = _WS_RE.sub(' ', t).strip()
    return t


def add_cluster_ids(df, text_col: str = 'raw_text'):
    """
    Add two columns to df (in place-safe way — returns a copy):
      'norm_text'  : the normalised representation
      'cluster_id' : SHA-1 hash of norm_text (deterministic, portable)
    """
    df = df.copy()
    norms = df[text_col].fillna('').map(normalise_text)
    df['norm_text']  = norms
    df['cluster_id'] = norms.map(lambda x: hashlib.sha1(x.encode('utf-8')).hexdigest())
    return df


def dedup_by_cluster(df, strategy: str = 'longest'):
    """
    Return one row per cluster_id.
      strategy='longest' : keep the row with the longest raw_text (max information)
      strategy='first'   : keep the first row encountered
    Preserves original DataFrame column order.
    """
    df = df.copy()
    if 'cluster_id' not in df.columns:
        raise ValueError("dedup_by_cluster requires 'cluster_id' — run add_cluster_ids first")

    if strategy == 'longest':
        df['_len'] = df['raw_text'].fillna('').str.len()
        df = (df.sort_values('_len', ascending=False)
                .drop_duplicates('cluster_id', keep='first')
                .drop(columns='_len'))
    elif strategy == 'first':
        df = df.drop_duplicates('cluster_id', keep='first')
    else:
        raise ValueError(f"unknown strategy: {strategy!r}")

    return df.sort_values('message_id').reset_index(drop=True) if 'message_id' in df.columns \
           else df.reset_index(drop=True)
