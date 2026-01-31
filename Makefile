# Makefile for paystore

.PHONY: install test lint format clean update-requirements help

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies with Poetry
	poetry install
	poetry run pre-commit install

install-pip:  ## Install dependencies with pip (alternative)
	pip install -r requirements-dev.txt
	pre-commit install

test:  ## Run tests with coverage
	poetry run pytest

test-verbose:  ## Run tests with verbose output
	poetry run pytest -vv

lint:  ## Run linters (ruff, mypy)
	poetry run ruff check paystore tests
	poetry run mypy paystore

format:  ## Format code with black
	poetry run black paystore tests
	poetry run ruff check --fix paystore tests

clean:  ## Clean up generated files
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	rm -rf htmlcov/ .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

update-requirements:  ## Update requirements.txt from Poetry
	poetry export -f requirements.txt --output requirements.txt --without-hashes
	poetry export -f requirements.txt --output requirements-dev.txt --with dev --without-hashes

build:  ## Build distribution packages
	poetry build

publish-test:  ## Publish to TestPyPI
	poetry publish -r testpypi

publish:  ## Publish to PyPI
	poetry publish

run-example:  ## Run basic example
	poetry run python examples/basic_usage.py

pre-commit:  ## Run pre-commit on all files
	poetry run pre-commit run --all-files
