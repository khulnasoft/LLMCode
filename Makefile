#!/usr/bin/env make

VERSION := 1.0.0
PYTHON := python3
VENV := venv
VENV_BIN := $(VENV)/bin
PYTEST_OPTS ?= -v  # Add configurable pytest options

# List all targets with descriptions
.PHONY: help
help:
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.PHONY: update install pip test docker-build venv dependencies build publish format pip-compile blame versionbump clean jekyll-run

update: ## Update system packages
	sudo apt-get update

install: update ## Install system dependencies
	sudo apt-get install -y libportaudio2

venv: ## Create and activate virtual environment
	test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(VENV_BIN)/python -m pip install --upgrade pip

pip: venv ## Install Python dependencies
	$(VENV_BIN)/pip install --no-cache-dir pytest black isort pip-tools
	$(VENV_BIN)/pip install -e .

test: pip ## Run tests
	$(VENV_BIN)/pytest $(PYTEST_OPTS)

docker-build: ## Build Docker image
	docker build -t llmcode:$(VERSION) -f ./docker/Dockerfile .

dependencies: venv ## Install build dependencies
	$(VENV_BIN)/pip install --no-cache-dir --upgrade pip build setuptools wheel twine importlib-metadata==7.2.1 pip-tools

build: dependencies ## Build the package
	$(VENV_BIN)/python -m build

publish: build ## Publish to PyPI
	$(VENV_BIN)/python -m twine upload dist/*

format: pip ## Format code with black and isort
	$(VENV_BIN)/black .
	$(VENV_BIN)/isort .

pip-compile: venv ## Compile requirements files
	bash scripts/pip-compile.sh
	$(VENV_BIN)/pip-compile --allow-unsafe --output-file=requirements.txt requirements/requirements.in

blame: ## Generate blame information
	$(PYTHON) ./scripts/blame.py "$(VERSION)" --all --output llmcode/website/_data/blame.yml

versionbump: ## Bump version numbers
	$(PYTHON) ./scripts/versionbump.py

clean: ## Clean up generated files
	rm -rf $(VENV) *.egg-info dist build __pycache__ .pytest_cache

jekyll-run: ## Run Jekyll server
	bash scripts/jekyll_run.sh

scripts/Dockerfile.jekyll: ## Build Jekyll Docker image
	docker build -t llmcode-jekyll:$(VERSION) -f ./scripts/Dockerfile.jekyll .

pre-commit: format ## Run pre-commit checks
	$(VENV_BIN)/black --check .
	$(VENV_BIN)/isort --check .