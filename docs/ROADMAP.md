# Project Roadmap

## Phase 3: Infrastructure Modernization & Reliability

### 1. Infrastructure as Code (IaC) Migration (Issue #20)
*   **Goal**: Replace manual AWS management with AWS CDK (TypeScript).
*   **Scope**:
    *   Migrate Lambda functions, EventBridge, and permissions to CDK constructs in `infra/` directory.
    *   Stop using manual `aws lambda update-function-code` commands in CI/CD.

### 2. Integration Testing
*   **Goal**: Verify end-to-end functionality in a real AWS environment.
*   **Timing**: After stable IaC deployment capability is established.
*   **Scope**:
    *   Deploy ephemeral stack or staging environment via CDK.
    *   Run E2E tests:
        *   Trigger Notifier Lambda -> Verify Slack Post -> Verify Sheet Update.
        *   Post Slack Reaction -> Verify Listener Lambda -> Verify Sheet Update.
    *   Tear down environment (if ephemeral).

### 3. Cost Implications
*   **Infrastructure Management**:
    *   **AWS CDK**: Free to use (open source framework).
    *   **CloudFormation**: Free for standard resource management.
    *   **State Management**: CDK metadata stored in S3/SSM may incur negligible costs.
*   **Integration Testing**:
    *   Ephemeral stacks created for CI/CD integration tests will generate temporary resources (Lambda, Logs, etc.).
    *   **Estimated Impact**: Minimal increase due to short-lived nature of test resources, provided `cdk destroy` is executed reliably.

### 4. Monitoring & Alerting
*   Implement CloudWatch Alarms for Lambda errors (e.g., Slack rate limits, API failures).
