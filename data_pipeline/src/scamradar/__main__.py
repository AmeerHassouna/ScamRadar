"""CLI: python -m scamradar <command>

Data-first workflow (DESIGN §1). Training commands refuse to run until the
dataset audit is approved.

  acquire                       download / ingest sources -> data/raw/canonical.parquet
  clean                         dedup + near-dup clustering + provenance
  audit                         mandatory dataset audit -> reports/dataset_audit.{json,md}
  approve-dataset               human approval gate -> data/APPROVAL.json
  split                         cluster-aware split + freeze each external benchmark
  bakeoff  [--features F6]      compare all models under identical CV conditions
  ablate                        feature-set ablation (F1..F6) with logreg
  tune     --model M [--trials] Optuna HPO (cluster-grouped CV)
  fit      --model M [--features F6] [--params-json p.json]
  eval     --bundle PATH [--split test]
  external --bundle PATH [--force-i-understand]   (ONE-SHOT per benchmark)
  error-analysis --bundle PATH [--exp-id E1]      DESIGN §13 comprehensive report
  probe    [--exp-id E1]                          synthetic-vs-real probe (DESIGN §7)
  smoke                         end-to-end run on generated toy data (sanity only)
"""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None):
    p = argparse.ArgumentParser(prog="scamradar", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("acquire")
    sub.add_parser("clean")
    sub.add_parser("audit")

    ap = sub.add_parser("approve-dataset")
    ap.add_argument("--yes", action="store_true",
                    help="skip the interactive 'I APPROVE' prompt")
    ap.add_argument("--accept-red-flags", action="store_true",
                    help="approve even though the audit reports red flags")
    ap.add_argument("--approver", default=None,
                    help="name to record in APPROVAL.json (defaults to $USER)")

    sub.add_parser("split")
    b = sub.add_parser("bakeoff"); b.add_argument("--features", default="F6")
    sub.add_parser("ablate")
    t = sub.add_parser("tune")
    t.add_argument("--model", default="logreg"); t.add_argument("--trials", type=int, default=40)
    t.add_argument("--features", default="F6")
    f = sub.add_parser("fit")
    f.add_argument("--model", default="logreg"); f.add_argument("--features", default="F6")
    f.add_argument("--params-json"); f.add_argument("--calibration", default="sigmoid")
    e = sub.add_parser("eval"); e.add_argument("--bundle", required=True)
    e.add_argument("--split", default="test")
    x = sub.add_parser("external"); x.add_argument("--bundle", required=True)
    x.add_argument("--force-i-understand", action="store_true")
    ea = sub.add_parser("error-analysis")
    ea.add_argument("--bundle", required=True)
    ea.add_argument("--exp-id", default="E1")
    pr = sub.add_parser("probe")
    pr.add_argument("--exp-id", default="E1")
    sub.add_parser("smoke")
    a = p.parse_args(argv)

    from . import tracking

    # Commands that require the dataset-approval gate (DESIGN §1, §5, §16).
    GATED = {"ablate", "bakeoff", "tune", "fit", "eval", "external",
             "error-analysis", "probe"}
    if a.cmd in GATED:
        from .approval import require_dataset_approval
        require_dataset_approval()

    if a.cmd == "acquire":
        from . import acquire; acquire.run()
    elif a.cmd == "clean":
        from . import clean; clean.run()
    elif a.cmd == "audit":
        from . import audit as _audit; _audit.run()
    elif a.cmd == "approve-dataset":
        from .approval import approve_dataset
        approve_dataset(assume_yes=a.yes,
                        accept_red_flags=a.accept_red_flags,
                        approver=a.approver)
    elif a.cmd == "split":
        from . import split; split.run()
    elif a.cmd == "bakeoff":
        from . import models
        res = models.bakeoff(feature_set=a.features)
        tracking.log("E3 model bake-off", "tree/linear comparison under identical CV",
                     {"features": a.features}, res)
    elif a.cmd == "ablate":
        from . import models
        from .features import FEATURE_SETS
        res = {fs: models.bakeoff(feature_set=fs, models=["logreg"]) for fs in FEATURE_SETS}
        tracking.log("E2 feature ablation", "hybrid F6 beats single representations",
                     {"models": ["logreg"]}, res)
    elif a.cmd == "tune":
        from . import models
        res = models.tune(a.model, a.features, a.trials)
        tracking.log("E4 HPO", f"tuned {a.model} beats defaults", vars(a), res)
    elif a.cmd == "fit":
        from . import models
        params = json.load(open(a.params_json)) if a.params_json else None
        if isinstance(params, dict) and "best_params" in params:
            params = params["best_params"]
        models.fit_final(a.model, a.features, params, a.calibration)
    elif a.cmd == "eval":
        from . import evaluate
        res = evaluate.run(a.bundle, a.split)
        tracking.log(f"E7 internal eval ({a.split})", "", {"bundle": a.bundle},
                     res["at_f1_threshold"])
    elif a.cmd == "external":
        from . import evaluate
        res = evaluate.run_external(a.bundle, force=a.force_i_understand)
        tracking.log("E7 EXTERNAL one-shot", "frozen model generalizes",
                     {"bundle": a.bundle}, res["at_f1_threshold"],
                     conclusion="external benchmark consumed")
    elif a.cmd == "error-analysis":
        from . import error_analysis
        rep = error_analysis.run(a.bundle, a.exp_id)
        tracking.log(f"{a.exp_id} error analysis", "extended DESIGN §13 report",
                     {"bundle": a.bundle}, rep["recommendation"])
    elif a.cmd == "probe":
        from . import probe
        rep = probe.run(a.exp_id)
        tracking.log(f"{a.exp_id} synthetic diagnostic",
                     "DESIGN §7 rules 6.a (artifact check, gating) + 7 (probe, diagnostic)",
                     {"policy_version": "v2.0-revised"},
                     {"overall_verdict": rep["overall_verdict"],
                      "artifact_check_by_probe": rep["artifact_check_by_probe"],
                      "global_probe_auc": rep["probes"]["global"]["metrics"]["roc_auc"]})
    elif a.cmd == "smoke":
        from . import smoke; smoke.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
