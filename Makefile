# Makefile for ADOC Toolkit
# Use this file to run common development tasks

.PHONY: help install test test-verbose test-watch test-coverage lint format type-check clean build dev-setup all-checks

# Default target - show help
help:
	@echo "ADOC Toolkit Development Commands"
	@echo "================================="
	@echo ""
	@echo "Setup:"
	@echo "  install       Install dependencies using uv"
	@echo "  dev-setup     Complete development setup (install + dev deps)"
	@echo ""
	@echo "Testing:"
	@echo "  test          Run all tests"
	@echo "  test-verbose  Run tests with verbose output"
	@echo "  test-watch    Run tests in watch mode (requires pytest-watch)"
	@echo "  test-coverage Run tests with coverage report"
	@echo "  test-export   Run export-metrics command tests only"
	@echo "  test-http     Run HTTP client tests only"
	@echo "  test-audit    Run audit functionality tests only"
	@echo "  test-logs     Run logging tests only"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint          Run linting checks (ruff)"
	@echo "  format        Format code (ruff format)"
	@echo "  type-check    Run type checking (mypy)"
	@echo "  all-checks    Run all code quality checks"
	@echo ""
	@echo "Development:"
	@echo "  clean         Clean up temporary files and caches"
	@echo "  build         Build the package"
	@echo "  run           Run the interactive toolkit"
	@echo ""
	@echo "Examples:"
	@echo "  make test                    # Run all tests"
	@echo "  make test-export             # Test export-metrics only"
	@echo "  make format lint             # Format code and run linting"
	@echo "  make all-checks              # Run all quality checks"

# Setup commands
install:
	@echo "📦 Installing dependencies..."
	uv sync

dev-setup: install
	@echo "🔧 Setting up development environment..."
	uv add --dev pytest-watch pytest-cov
	@echo "✅ Development setup complete!"

# Test commands
test:
	@echo "🧪 Running tests..."
	uv run pytest

test-verbose:
	@echo "🧪 Running tests with verbose output..."
	uv run pytest -v

test-watch:
	@echo "👀 Running tests in watch mode (Ctrl+C to stop)..."
	uv run pytest-watch

test-coverage:
	@echo "📊 Running tests with coverage..."
	uv run pytest --cov=adoc_toolkit --cov-report=html --cov-report=term

test-export:
	@echo "🧪 Testing export-metrics command..."
	uv run pytest tests/test_export_metrics_command.py -v

test-http:
	@echo "🧪 Testing HTTP client..."
	uv run pytest tests/test_http_client.py -v

test-audit:
	@echo "🧪 Testing audit functionality..."
	uv run pytest tests/test_audit.py tests/test_auditable.py -v

test-logs:
	@echo "🧪 Testing logging functionality..."
	uv run pytest tests/test_logger.py -v

# Code quality commands
lint:
	@echo "🔍 Running linting checks..."
	uv run ruff check .

format:
	@echo "✨ Formatting code..."
	uv run ruff format .

type-check:
	@echo "🔍 Running type checks..."
	uv run mypy .

all-checks: format lint type-check
	@echo "✅ All code quality checks completed!"

# Development commands
clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	rm -rf htmlcov/ 2>/dev/null || true
	rm -rf dist/ 2>/dev/null || true
	rm -rf build/ 2>/dev/null || true
	@echo "✅ Cleanup complete!"

build:
	@echo "📦 Building package..."
	uv build

run:
	@echo "🚀 Starting ADOC Toolkit interactive shell..."
	uv run adoc-toolkit

# Quick test combinations for common workflows
test-core: test-http test-audit test-logs
	@echo "✅ Core functionality tests completed!"

test-cli: test-export
	@echo "✅ CLI functionality tests completed!"

# CI/CD friendly commands
ci-test: format lint type-check test
	@echo "✅ CI checks completed!"