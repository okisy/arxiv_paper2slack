# Issue: Refactor Project Structure to Mono-Repo Style

## Status: Open
**Created**: 2026-01-20

## Description
Currently, the `arxiv-notifier` (paper poster) code resides in the root directory, while the new `arxiv-listener` (reaction sync) code resides in `arxiv-slack-listener/`.
To maintain a clean mono-repo structure, the root code should be moved to a dedicated directory (e.g., `arxiv-poster/`).

## Tasks
- [ ] Move root-level python files (`lambda_function.py`, `config.py`, etc.) and `Dockerfile` to `arxiv-poster/`.
- [ ] Update `ci-cd.yml` to point to the new build context for the poster function.
- [ ] Verify that the Lambda function deployment path is updated correctly.
- [ ] Update documentation to reflect the new structure.

## Context
Deferred during Phase 2 implementation to prioritize feature delivery and avoid breaking existing deployments.
