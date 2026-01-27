# Issue: Infrastructure as Code (IaC) Adoption

## Status: Open
**Created**: 2026-01-26

## Description
Currently, the AWS infrastructure for this project is managed manually via the AWS Management Console ("ClickOps"). To ensure reproducibility, version control, and easier environment replication (e.g., staging vs. prod), we need to migrate the infrastructure management to an IaC tool.

## Current Resources
The following resources are currently manually configured and need to be imported/definitions created:

### 1. Compute (Lambda)
*   **`paperNotification`**:
    *   Type: Container Image
    *   Trigger: EventBridge Schedule (Cron)
    *   Env Vars: `SLACK_API_TOKEN`, `SPREADSHEET_ID`, `OPENAI_API_KEY`, etc.
    *   Memory: 512MB
    *   Timeout: 300s
*   **`paperReactionListener`** (also referred to as `arxiv-slack-listener` in code):
    *   Type: Container Image
    *   Trigger: Function URL (Auth: NONE - verified within code)
    *   Env Vars: `SLACK_SIGNING_SECRET`, `SPREADSHEET_ID`, etc.
    *   Memory: 128MB
    *   Timeout: 15s

### 2. Container Registry (ECR)
*   `arxiv-paper-notifier`
*   `arxiv-slack-listener`

### 3. Identity (IAM)
*   `service-role/paperNotification-role-44vqb3s7` (and policies)
*   `service-role/paperReactionListener-role-xxxx`

### 4. Scheduler (EventBridge)
*   Daily Schedule Rule (10:00 JST)

## Candidate Tools
*   **Terraform**: Industry standard, state management backend needed (S3/DynamoDB).
*   **AWS CDK (TypeScript/Python)**: Imperative definition, compiles to CloudFormation. Good for developers.
*   **Serverless Framework**: easy for Lambda, but maybe less flexible for containers.

## Tasks
- [ ] Select IaC Tool (Terraform recommended for general AWS usage, or CDK).
- [ ] Create initial configuration importing existing resources OR create new definitions to replace them.
- [ ] Setup remote state backend (if Terraform).
- [ ] Integrate `verification`-stage in CI/CD (e.g., `terraform plan` on PR).
