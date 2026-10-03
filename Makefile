PY      ?= python
CLI     := PYTHONPATH=src $(PY) -m skidsignal.cli
SAMPLE  := --set paths.raw=data/sample --set paths.processed=data/sample_run/processed \
           --set paths.index=data/sample_run/index --set paths.reports=data/sample_run/reports \
           --set paths.figures=data/sample_run/figures
VEHICLE ?= HYUNDAI PALISADE
Q       ?= Which vehicles report ABS activation at low speed on dry roads?

.PHONY: install install_llm download download_history prepare index signals backtest cluster evaluate briefs brief ask figures all sample test api clean

install:            ## install the package with development tools
	$(PY) -m pip install -e ".[dev]"
install_llm:        ## add the optional Anthropic client
	$(PY) -m pip install -e ".[dev,llm]"
download:           ## fetch the official NHTSA flat files (about 150 MB zipped)
	$(CLI) download
download_history:   ## also fetch complaints received from 1995 to 2019
	$(CLI) download --groups complaints complaints_history recall_documents recalls_flat investigations communications
prepare:
	$(CLI) prepare
index:
	$(CLI) index
signals:
	$(CLI) signals
backtest:
	$(CLI) backtest
cluster:
	$(CLI) cluster
evaluate:
	$(CLI) evaluate
briefs:             ## write briefs for the ten highest priority signals
	$(CLI) brief --top 10
brief:              ## make brief VEHICLE="RAM 2500"
	$(CLI) brief --vehicle "$(VEHICLE)"
ask:                ## make ask Q="your question"
	$(CLI) ask "$(Q)"
figures:
	$(CLI) figures
all:                ## prepare, index, signals, backtest, cluster, evaluate, briefs, figures
	$(CLI) all
sample:             ## run the whole pipeline on the bundled sample, outputs in data/sample_run
	$(CLI) $(SAMPLE) all
test:
	PYTHONPATH=src $(PY) -m pytest
api:
	PYTHONPATH=src $(PY) -m uvicorn skidsignal.api.app:app --port 8000
clean:
	rm -rf data/processed data/index data/sample_run .pytest_cache
