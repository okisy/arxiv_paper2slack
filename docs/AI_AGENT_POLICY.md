# AI Agent Development Policy

To ensure efficient collaboration with AI agents (and human developers), this repository adheres to the following "AI-Native" development standards.

## 1. Coding Standards: Context is King
AI agents rely on static analysis and clear context to understand code. Ambiguity leads to hallucinations or incorrect edits.

### 1.1 Type Hinting (Mandatory)
All Python code **must** use type hints for function arguments and return values. This allows AI to infer data structures without guessing.
*   **Good**: `def process_items(items: list[str]) -> int:`
*   **Bad**: `def process_items(items):`

### 1.2 Docstrings (Google Style)
Every function and class **must** have a docstring in **Google Style**.
*   **Description**: Clear summary of what the function does.
*   **Args**: Description of each argument.
*   **Returns**: Description of the return value.
*   **Raises**: explicitly list exceptions raised.

### 1.3 Modular Design
*   Keep files under **300 lines** when possible. Large files confuse context windows.
*   Separate configuration, logic, and interface (Adapter/Port pattern).

## 2. Testing Strategy: Reliability & Feedback
AI agents need feedback loops to self-correct.

### 2.1 Unit Tests (Pytest)
*   **Coverage**: Aim for high coverage of logic branches.
*   **Mocking**: Use `unittest.mock` strictly for external services (Slack, Arxiv, Google Sheets).
*   **Self-Correction**: Tests should provide clear error messages so AI can debug failures automatically.

### 2.2 Integration Tests
*   Infrastructure as Code (IaC) verification should be done via ephemeral environments (as per Roadmap).

## 3. Operational Standards

### 3.1 Secrets Management
*   **NEVER** hardcode credentials.
*   Use environment variables loaded via `os.environ`.
*   Provide a `.env.example` template.

### 3.2 Error Handling & Logging
*   Use structured logging (JSON preferred in production) or consistent print formats.
*   Explicitly handle known API errors (e.g., HTTP 429, 500) to allow retry logic implementation.

## 4. Documentation
*   **README.md**: Must be the single source of truth for setup and entry points.
*   **ARCHITECTURE.md**: Must be updated when system components change.
*   **ROADMAP.md**: Use to track future work and AI tasks.

## 5. Development Workflow (Agent-Centric)
1.  **Issue Driven**: Start every task with a GitHub Issue clearly defining the "Goal".
2.  **Implementation Plan**: Before coding, the Agent must create an `implementation_plan.md` to align on the approach.
3.  **Docs First**: Update documentation *before* or *with* the code changes, not after.

## 6. Branching Strategy & Version Control
To maintain a clean history and enable parallel development, we follow a lightweight **Feature Branch Workflow**.

### 6.1 Branch Naming Conventions
*   `main`: Protected branch. Always deployable.
*   `feature/description-of-feature`: New features or substantial changes.
*   `fix/issue-number-description`: Bug fixes, specifically linking to an Issue ID.
*   `docs/description`: Documentation-only changes.
*   `refactor/description`: Code cleanup without logic changes.

### 6.2 Pull Request (PR) Etiquette
*   **Title**: Use [Conventional Commits](https://www.conventionalcommits.org/) format (e.g., `feat: add retry logic`, `fix: resolve 429 error`).
*   **Body**:
    *   Link to related Issue (`Fixes #123`).
    *   Description of changes.
    *   Verification steps taken (e.g., "Ran unit tests locally", "Deployed to staging").
*   **Review**: AI Agents should request human review for logic changes.

