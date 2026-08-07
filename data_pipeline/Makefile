.PHONY: setup smoke pipeline ablate bakeoff
PY=python

setup:
	pip install -r requirements.txt
	pip install -e .

smoke:
	$(PY) -m scamradar smoke

pipeline:
	$(PY) -m scamradar acquire
	$(PY) -m scamradar clean
	$(PY) -m scamradar split

ablate:
	$(PY) -m scamradar ablate

bakeoff:
	$(PY) -m scamradar bakeoff --features F6
