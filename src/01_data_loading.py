"""
ScamRadar+ | Step 01: Data Loading
Loads data from SQLite database and performs basic EDA
"""

import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os

# ─── CONFIG ───────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'db 4.db')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'outputs')
os.makedirs(OUTPUT_PATH, exist_ok=True)

# ─── CONNECT ──────────────────────────────────────────────
conn = sqlite3.connect(DB_PATH)
print("✅ Connected to database")

# ─── VERIFY TABLES ────────────────────────────────────────
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", cursor.fetchall())

# ─── LOAD DATA ────────────────────────────────────────────
query = """
SELECT 
    m.message_id,
    m.raw_text,
    m.label,
    c.type AS channel,
    ds.name AS source,
    mf.text_length,
    mf.word_count,
    mf.has_url,
    mf.url_count,
    mf.exclamation_count,
    mf.uppercase_ratio,
    mf.digit_ratio,
    mf.urgency_score
FROM Message m
JOIN Channel c ON m.channel_id = c.channel_id
JOIN DataSource ds ON m.source_id = ds.source_id
JOIN MessageFeatures mf ON m.message_id = mf.message_id
"""

df = pd.read_sql_query(query, conn)
conn.close()

print(f"✅ Data loaded: {df.shape[0]} rows, {df.shape[1]} columns")
print(f"\nLabel distribution:\n{df['label'].value_counts()}")
print(f"\nChannels:\n{df['channel'].value_counts()}")
print(f"\nSources:\n{df['source'].value_counts()}")

# ─── EDA PLOTS ────────────────────────────────────────────
# 1. Class Distribution
df['label'].value_counts().plot(kind='bar', color=['steelblue', 'salmon'])
plt.title("Class Distribution")
plt.xlabel("Label (0=Legit, 1=Scam)")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_PATH, 'class_distribution.png'), dpi=200)
plt.close()

# 2. Label by Channel
import seaborn as sns
channel_counts = df.groupby(['channel', 'label']).size().unstack(fill_value=0)
channel_counts.columns = ['Legit (0)', 'Scam (1)']
channel_counts.plot(kind='bar', stacked=True)
plt.title("Label Distribution by Channel")
plt.xlabel("Channel")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_PATH, 'label_by_channel.png'), dpi=200)
plt.close()

# 3. Text Length Distribution
for lab, name in [(0, "Legit"), (1, "Scam")]:
    df[df['label'] == lab]['text_length'].hist(bins=50)
    plt.title(f"Text Length Distribution - {name}")
    plt.xlabel("Text length")
    plt.ylabel("Frequency")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_PATH, f'textlen_{name}.png'), dpi=200)
    plt.close()

print("✅ EDA plots saved to outputs/")
print("\ndf is ready for next step!")
