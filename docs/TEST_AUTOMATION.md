# Issue: Setup Automated Testing Framework

## Status: In Progress
**Created**: 2026-01-22
**Last Updated**: 2026-01-26

## Implemented: Unit Tests
We have established a `pytest` based unit testing framework.
*   **Location**: `tests/` directory
*   **Execution**: `python3 -m pip install -r requirements-test.txt -r requirements.txt && python3 -m pytest tests/`

### 1. Notifier Tests (`tests/test_notifier.py`)
Mocks external APIs (Arxiv, OpenAI, Slack, Google Sheets) to verify business logic.
*   `test_build_slack_blocks`: Verifies that Slack Block Kit JSON is constructed correctly (stars, theme labels, timestamps).
*   `test_generate_paper_summary`: Verifies LLM response parsing and fallback logic when API fails.
*   `test_main_flow`: Verifies the main orchestration loop (Fetch -> Filter -> Process -> Post -> Save).

### 2. Listener Tests (`tests/test_listener.py`)
Use dynamic imports to isolate the Lambda environment.
*   `test_verify_slack_signature`: Verifies HMCA-SHA256 signature validation logic.
*   `test_lambda_handler_url_verification`: Verifies Slack Challenge response.
*   `test_lambda_handler_reaction_added`: Verifies that `reaction_added` events trigger the sheet update function.

---

## Roadmap: Integration Tests & CI/CD

### 1. Integration Test Strategy
Since our application relies heavily on 3rd party APIs (SaaS), "Integration Testing" in CI will focus on **Contract Testing** and **Enhanced Mocking** rather than live API calls, to avoid flakiness and costs.

*   **Phase 1 (CI-Side)**:
    *   **Strict Mocking**: Ensure mocks match the exact schema of real API responses (e.g., using stored real response examples).
    *   **Env Var Validation**: Ensure all required environment variables are defined in `config.py` or Lambda environment.
*   **Phase 2 (Staging Environment)**:
    *   Deploy code to a separate "Staging" Lambda stack.
    *   **Smoke Test**: Trigger the Lambda via AWS CLI / EventBridge to ensure it doesn't crash on startup (Dependency check).
    *   *Note*: End-to-end testing with real Slack/Sheets is manual due to OAuth/Interactive limitations.

### 2. CI/CD Pipeline (GitHub Actions)
We plan to implement a GitHub Actions workflow `.github/workflows/ci-cd.yml` with the following stages:

#### **Stage 1: Pull Request Checks (CI)**
Triggered on `pull_request` to `main`, `develop`.
1.  **Linting**: Run `ruff` or `flake8` to enforce code style.
2.  **Unit Tests**:
    *   Set up Python 3.12.
    *   Install `requirements.txt` (Production) + `requirements-test.txt` (Test).
    *   Run `pytest`.
    *   **Block Merge** if tests fail.

#### **Stage 2: Deployment (CD)**
Triggered on `push` to `main` (Merge).
1.  **Build**: Docker build `paperNotification` and `paperReactionListener` images.
2.  **Push**: Push images to Amazon ECR (using OIDC for auth).
3.  **Update Lambda**: Update Lambda functions to point to the new image URI.

*Current Status*: CI/CD workflow is yet to be implemented. See [Issue #XX] for progress.

### 3. Future: IaC Integration (Terraform/CDK)
Adopting IaC (planned in `docs/IAC_ADOPTION.md`) will significantly enhance our testing capabilities:

*   **Infrastructure Testing**:
    *   **Static Analysis**: Use `tflint` or `cdk synth` to catch misconfigurations (e.g., public S3 buckets, missing env vars) before deployment.
    *   **Policy Checks**: Enforce security compliance automatically in CI.
*   **Ephemeral Environments**:
    *   Create temporary, isolated Lambda stacks for each Pull Request.
    *   Run **Smoke Tests** against these ephemeral environments to verify end-to-end deployment success without affecting Staging/Production.
*   **Unified Pipeline**:
    *   Deployment will shift from updating code only (`update-function-code`) to applying infrastructure state (`terraform apply`), preventing configuration drift.
