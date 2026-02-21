.PHONY: setup lint test clean lint-notifier lint-listener test-notifier test-listener

setup:
	@echo "Installing dependencies for notifier..."
	cd services/notifier && pip install -r requirements.txt -r requirements-test.txt
	@echo "Installing dependencies for listener..."
	cd services/listener && pip install -r requirements.txt -r requirements-test.txt

lint-notifier:
	@echo "Linting notifier..."
	cd services/notifier && ruff check .

lint-listener:
	@echo "Linting listener..."
	cd services/listener && ruff check .

lint: lint-notifier lint-listener

test-notifier: lint-notifier
	@echo "Running tests for notifier..."
	cd services/notifier && pytest tests/

test-listener: lint-listener
	@echo "Running tests for listener..."
	cd services/listener && pytest tests/

test: test-notifier test-listener

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
