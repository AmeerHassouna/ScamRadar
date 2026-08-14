"""
ScamRadar+ | Canonical E8-P9 Implementation
============================================

The `src/` package is the source-of-truth for the deployed system. Read
`src/pipeline.py` first — it is the narrative map that references every
other module.

Layout:

    src/
      canonical.py            declarative constants (paths, hyperparams,
                              feature list, threshold, metrics)
      data.py                 canonical data loaders (data/canonical/)
      preprocessing / features text preprocessing + 25 numerical features
                              (concrete impl in src/features.py; see also
                              src/rule_engine/numerical_features.py)
      model.py                LR + TF-IDF configuration; training + I/O
      rule_engine/            19-rule modular post-classifier
      inference.py            single-message prediction (used by the API)
      e5_inference.py         concrete implementation of the request-time
                              inference path
      evaluation.py           metric computation for the frozen benchmark
      pipeline.py             THE narrative that ties it all together

Historical experiments live under `experiments/` at the repository root.
Nothing in `src/` depends on them.
"""
