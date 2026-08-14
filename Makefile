# ScamRadar+ — common developer commands.
#
# Run `make help` for a categorised summary of every target.

PY := python3
VENV_PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help setup api web train eval bakeoff summary test deploy clean

# ─── Discovery ────────────────────────────────────────────────────────────

help: ## Show this help message.
	@echo 'ScamRadar+ developer commands'
	@echo ''
	@echo 'Setup + serve:'
	@echo '  make setup       Install Python + Node dependencies'
	@echo '  make api         Start the FastAPI backend on port 8000'
	@echo '  make web         Start the Next.js frontend on port 3000'
	@echo ''
	@echo 'Model reproduction (writes to models/ + outputs/eval/):'
	@echo '  make train       Train the deployed E8-P9 classifier bundle'
	@echo '  make bakeoff     Run the final classifier bake-off (LR vs LinearSVC vs SGD)'
	@echo '  make eval        Rerun the per-item external-benchmark scoring'
	@echo '  make summary     Rebuild master_summary.{json,csv} + e8p9_findings.md'
	@echo ''
	@echo 'Verification:'
	@echo '  make test        Run the manual-acceptance-test corpus'
	@echo ''
	@echo 'Deployment:'
	@echo '  make deploy      Push to the Render deploy branch'
	@echo ''
	@echo 'Housekeeping:'
	@echo '  make clean       Remove __pycache__ + notebook checkpoint dirs'

# ─── Setup + serve ────────────────────────────────────────────────────────

setup:  ## Install Python + Node dependencies.
	$(PY) -m pip install -r requirements.txt
	cd web && npm install

api:  ## Start the FastAPI backend on port 8000.
	uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

web:  ## Start the Next.js frontend on port 3000.
	cd web && npm run dev

# ─── Model reproduction ───────────────────────────────────────────────────

train:  ## Train the deployed E8-P9 classifier bundle.
	$(PY) scripts/training/train_e8p9.py

bakeoff:  ## Run the final classifier bake-off (LR vs LinearSVC vs SGD).
	$(PY) scripts/training/bakeoff_e8p9.py

eval:  ## Score the external benchmark end-to-end with the deployed pipeline.
	$(PY) scripts/evaluation/analyze_e8p9_errors.py

summary:  ## Rebuild consolidated evaluation artifacts (fast, aggregation only).
	$(PY) scripts/evaluation/build_evaluation_summary.py

# ─── Verification ─────────────────────────────────────────────────────────

test:  ## Run the manual-acceptance-test corpus.
	$(PY) tests/manual_acceptance_test.py

# ─── Deployment ───────────────────────────────────────────────────────────

deploy:  ## Push the current branch — Render auto-deploys on push to main.
	git push origin main

# ─── Housekeeping ─────────────────────────────────────────────────────────

clean:  ## Remove __pycache__ directories.
	find . -type d -name __pycache__ -not -path './.venv/*' -not -path './node_modules/*' -exec rm -rf {} + 2>/dev/null || true
