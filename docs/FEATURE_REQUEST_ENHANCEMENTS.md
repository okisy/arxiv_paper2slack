# Issue: Enhancements for Slack Paper Notifications

## Status: Open
**Created**: 2026-01-22

## Description
The user requested two enhancements to the notification workflow to improve readability and integration with other AI tools (Gemini).

### 1. Display Slack Posting Timestamp
Add the timestamp of the Slack post explicitly within the message body (or footer). This improves visibility of *when* the paper was notified, independent of the message metadata.

### 2. Gemini-Optimized Prompt Output (Cross-Channel)
Provide a format that allows for immediate copy-pasting into Gemini to ask for further analysis.

*   **Format**:
    ```text
    https://arxiv.org/pdf/2601.04572v1
    https://arxiv.org/pdf/2601.10031v1
    https://arxiv.org/pdf/2601.03479v1
    これらの論文についてなにがすごいのか教えて
    ```
*   **Implementation Constraints**:
    *   This "prompt bundle" should ideally be posted to a **different channel** to avoid cluttering the main notification channel.
    *   **Correspondence**: Since it will be in a different channel, there must be a clear link or ID (e.g., matching timestamp, thread link, or "Batch ID") to understand which set of papers this prompt refers to.

## Proposed Strategy
*   **Enhancement 1**: Modify `build_slack_blocks` to include text like `Posted at: YYYY-MM-DD HH:MM`.
*   **Enhancement 2**:
    *   Add a new environment variable `SLACK_PROMPT_CHANNEL` (optional).
    *   Accumulate the PDF URLs during the loop.
    *   After the loop finishes (sending all 3 papers), post the "Gemini Prompt" message to the `SLACK_PROMPT_CHANNEL`.
    *   Include a reference (e.g., "For papers sent at [Timestamp]") to link it back to the main posts.
