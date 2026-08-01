"""
Evaluator for v1.6 (L2-normalised MiniLM sentence embeddings + LogisticRegression).

Uses predict_message from _09_prediction_pipeline UNCHANGED — no production
code modification. The MiniLM encoder is wrapped in a shim that presents a
.transform() method matching TfidfVectorizer's interface. When predict_message
calls tfidf.transform([text_norm]) it receives a (1, 384) sparse matrix
holding the L2-normalised MiniLM embedding instead of a TF-IDF sparse row.

This works because predict_message hstacks [tfidf, char_tfidf, numerical_scaled]
without caring what "tfidf" internally represents, and the v1.6 model was
trained on exactly [L2-normalised MiniLM(384), char(3000), numerical(26)]
concatenation in the same order.

The shim passes normalize_embeddings=True to st.encode() so inference-time
embeddings match the L2-normalised embeddings seen at training. Rule floors
(sections 12b–12i of predict_message) apply unchanged — this gives v1.6 the
same rule-floor-augmented decision path as v1.3 and v1.5, making the
comparison apples-to-apples across all three.
"""
import argparse, os, sys, csv, pickle, json, time, sqlite3
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, roc_auc_score, average_precision_score,
                             confusion_matrix)
from scipy.sparse import csr_matrix

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import DEFAULT_THRESHOLD
from src._00_dedup import add_cluster_ids
from src._09_prediction_pipeline import predict_message

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MiniLMAsTfidf:
    """
    Wraps a SentenceTransformer to expose a TfidfVectorizer-compatible
    .transform(texts) method returning (n, 384) sparse matrix.

    predict_message calls tfidf.transform([text_norm]) — we intercept
    and encode via MiniLM instead. Rule floors, char_tfidf, numerical
    features, and scaler continue to work unchanged.
    """
    def __init__(self, st_model):
        self.st = st_model

    def transform(self, texts):
        embs = self.st.encode(list(texts), convert_to_numpy=True, normalize_embeddings=True)
        return csr_matrix(embs)

    def get_feature_names_out(self):
        return np.array([f'minilm_{i}' for i in range(384)])


def load_v1_6(models_dir):
    import faiss
    from sentence_transformers import SentenceTransformer
    payload     = pickle.load(open(f'{models_dir}/scamradar_model.pkl', 'rb'))
    char_tfidf  = pickle.load(open(f'{models_dir}/char_vectorizer.pkl', 'rb'))
    scaler      = pickle.load(open(f'{models_dir}/scaler.pkl', 'rb'))
    scam_idx    = faiss.read_index(f'{models_dir}/scam_faiss.index')
    st          = SentenceTransformer('all-MiniLM-L6-v2')
    minilm_shim = MiniLMAsTfidf(st)
    threshold   = payload.get('threshold', DEFAULT_THRESHOLD)
    return {'model': payload['model'], 'threshold': threshold,
            'minilm_shim': minilm_shim, 'char_tfidf': char_tfidf,
            'scaler': scaler, 'scam_idx': scam_idx, 'st': st}


def predict_v1_6(text, pipe):
    """Route through predict_message with the MiniLM shim in tfidf's slot."""
    return predict_message(text, pipe['model'], pipe['minilm_shim'],
                           pipe['char_tfidf'], pipe['scaler'],
                           pipe['scam_idx'], pipe['st'],
                           threshold=pipe['threshold'],
                           vt_api_key=None, gsb_api_key=None)


def metrics(y, p, pr, tag=''):
    tn, fp, fn, tp = confusion_matrix(y, p, labels=[0,1]).ravel()
    m = {
        'n': int(len(y)),
        'accuracy':  round(float(accuracy_score(y, p)), 4),
        'precision': round(float(precision_score(y, p, zero_division=0)), 4),
        'recall':    round(float(recall_score(y, p, zero_division=0)), 4),
        'f1':        round(float(f1_score(y, p, zero_division=0)), 4),
        'confusion': {'tn': int(tn), 'fp': int(fp), 'fn': int(fn), 'tp': int(tp)},
    }
    if len(set(y)) > 1:
        m['roc_auc'] = round(float(roc_auc_score(y, pr)), 4)
        m['pr_auc']  = round(float(average_precision_score(y, pr)), 4)
    if tag: print(f"\n  {tag}  {m}")
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--models-dir',  default=f'{BASE}/models/v1.6_candidate')
    ap.add_argument('--external',    action='store_true')
    ap.add_argument('--rung1',       action='store_true')
    ap.add_argument('--sample',      type=int, default=250)
    args = ap.parse_args()

    print(f"Loading v1.6 from {args.models_dir}…")
    pipe = load_v1_6(args.models_dir)
    print(f"  threshold={pipe['threshold']}")

    if args.rung1:
        print(f"\n{'='*68}\nRUNG-1 leaked/unseen bucketed eval (with rule floors)\n{'='*68}")
        conn = sqlite3.connect(f'{BASE}/data/db 4.db')
        df = pd.read_sql_query("""
            SELECT m.message_id, m.raw_text, m.label, ds.name AS source, c.type AS channel
            FROM Message m JOIN DataSource ds ON m.source_id=ds.source_id
            JOIN Channel c ON m.channel_id=c.channel_id ORDER BY m.message_id
        """, conn); conn.close()
        df['raw_text'] = df['raw_text'].fillna('')
        df = add_cluster_ids(df)

        with open(f'{BASE}/outputs/split_v1.json') as f:
            split_map = json.load(f)
        training_clusters = {cid for cid, s in split_map.items() if s == 'train'}
        _, idx_te = train_test_split(np.arange(len(df)), test_size=0.20,
                                     random_state=42, stratify=df['label'].values)
        test_df = df.iloc[idx_te].reset_index(drop=True)
        test_df = test_df[test_df['raw_text'].str.strip().str.len() >= 20].reset_index(drop=True)
        test_df['leaked'] = test_df['cluster_id'].isin(training_clusters)

        np.random.seed(42)
        buckets = []
        for leaked in [True, False]:
            for lab in [0, 1]:
                sub = test_df[(test_df.leaked == leaked) & (test_df.label == lab)]
                n = min(args.sample, len(sub))
                buckets.append(sub.sample(n, random_state=42))
        sample = pd.concat(buckets, ignore_index=True)
        print(f"  Sample: {len(sample)} items")

        preds, probs = [], []
        t0 = time.time()
        for i, row in enumerate(sample.itertuples()):
            if i and i % 100 == 0:
                rate = i / (time.time()-t0); eta = (len(sample)-i)/rate
                print(f"    {i}/{len(sample)}  ({rate:.1f} msg/s, ETA {eta:.0f}s)")
            r = predict_v1_6(row.raw_text, pipe)
            preds.append(1 if r['verdict'] in ('SCAM','SUSPICIOUS') else 0)
            probs.append(float(r.get('confidence', 0))/100)
        sample['pred'] = preds; sample['prob'] = probs

        m_leaked = metrics(sample[sample.leaked==True]['label'].values,
                           sample[sample.leaked==True]['pred'].values,
                           sample[sample.leaked==True]['prob'].values, 'LEAKED')
        m_unseen = metrics(sample[sample.leaked==False]['label'].values,
                           sample[sample.leaked==False]['pred'].values,
                           sample[sample.leaked==False]['prob'].values, 'UNSEEN')
        m_all    = metrics(sample['label'].values, sample['pred'].values,
                           sample['prob'].values, 'OVERALL')

        out = f'{BASE}/outputs/eval/v1.6_candidate.json'
        with open(out, 'w') as f:
            json.dump({'leaked': m_leaked, 'unseen': m_unseen, 'overall': m_all,
                       'gap': round(m_leaked['f1'] - m_unseen['f1'], 4)}, f, indent=2)
        print(f"\n✅ Wrote {out}")

    if args.external:
        print(f"\n{'='*68}\nEXTERNAL EVAL (400 items, SINGLE run)\n{'='*68}")
        items = []
        with open(f'{BASE}/data/external_evaluation/external_eval.csv') as f:
            for r in csv.DictReader(f):
                items.append({'raw_text': r['raw_text'], 'label': int(r['label']),
                              'source': r['source']})
        print(f"  Loaded {len(items)} items")

        preds, probs = [], []
        t0 = time.time()
        for i, it in enumerate(items):
            if i and i % 50 == 0:
                print(f"    {i}/{len(items)}  ({(i/(time.time()-t0)):.1f} msg/s)")
            r = predict_v1_6(it['raw_text'], pipe)
            preds.append(1 if r['verdict'] in ('SCAM','SUSPICIOUS') else 0)
            probs.append(float(r.get('confidence', 0))/100)
        y = np.array([it['label'] for it in items])
        m_ext = metrics(y, np.array(preds), np.array(probs), 'EXTERNAL')

        per_source = {}
        for src in set(it['source'] for it in items):
            idxs = [i for i, it in enumerate(items) if it['source'] == src]
            ys = y[idxs]; ps = np.array(preds)[idxs]; pp = np.array(probs)[idxs]
            per_source[src] = metrics(ys, ps, pp, f'src={src}')
        m_ext['per_source'] = per_source

        fps = [{'idx':i, 'confidence':round(probs[i]*100,2),
                'text': items[i]['raw_text'][:250].replace('\n',' ')}
               for i in range(len(items)) if items[i]['label']==0 and preds[i]==1]
        fns = [{'idx':i, 'confidence':round(probs[i]*100,2),
                'text': items[i]['raw_text'][:250].replace('\n',' ')}
               for i in range(len(items)) if items[i]['label']==1 and preds[i]==0]
        m_ext['false_positives'] = fps
        m_ext['false_negatives'] = fns

        out = f'{BASE}/outputs/eval/v1.6_candidate_external.json'
        with open(out, 'w') as f:
            json.dump(m_ext, f, indent=2)
        print(f"\n✅ Wrote {out}")


if __name__ == '__main__':
    main()
