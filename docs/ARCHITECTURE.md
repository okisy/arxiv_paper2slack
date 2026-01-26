# システムアーキテクチャ


> [!WARNING]
> 本ドキュメントの記載内容は、2026-01-26時点のAWS設定(CLI)に基づいて更新されました。

## 概要
本日開発した **Arxiv Paper to Slack** システムは、主に通知用（Notifier）とリアクション同期用（Listener）の2つのAWS Lambda関数で構成されています。

## アーキテクチャ図

```mermaid
graph TD
    %% specific styles
    style EventBridge fill:#ff9900,stroke:#333,color:white
    style Notifier fill:#ff9900,stroke:#333,color:white
    style Listener fill:#ff9900,stroke:#333,color:white
    style ECR fill:#ff9900,stroke:#333,color:white
    style Slack fill:#e01e5a,stroke:#333,color:white
    style GoogleSheets fill:#0f9d58,stroke:#333,color:white
    style OpenAI fill:#10a37f,stroke:#333,color:white
    style Arxiv fill:#b31b1b,stroke:#333,color:white

    subgraph AWS_Cloud ["AWS Cloud"]
        EventBridge["EventBridge Scheduler<br/>毎日 10:00 JST"]
        
        subgraph Compute
            Notifier["Lambda: paperNotification<br/>512MB, timeout 300s<br/>Role: paperNotification-role-***"]
            Listener["Lambda: paperReactionListener<br/>128MB, timeout 15s<br/>Role: paperNotification-role-***"]
        end
        
        subgraph Storage
            ECR["Elastic Container Registry<br/>Docker Images"]
        end
    end

    subgraph External_Services ["External Services"]
        Arxiv[Arxiv API]
        OpenAI[OpenAI API]
        Slack[Slack Workspace]
        GoogleSheets[Google Sheets]
    end

    %% Flows - Notification
    EventBridge -->|トリガー| Notifier
    Notifier -->|論文取得| Arxiv
    Notifier -->|要約・評価| OpenAI
    Notifier -->|投稿| Slack
    Notifier -->|メタデータ保存| GoogleSheets
    ECR -.->|Image Pull| Notifier

    %% Flows - Reaction Sync
    Slack -->|"イベント: reaction_added<br/>Function URL"| Listener
    Listener -->|署名検証| Slack
    Listener -->|リアクション更新| GoogleSheets
    ECR -.->|Image Pull| Listener
```

## コンポーネント詳細

### 1. `paperNotification` (Notifier)
*   **トリガー**: EventBridge スケジュール (`cron(0 1 * * ? *)` - UTC 01:00 / JST 10:00)
*   **ランタイム**: Python 3.9 (Container Image)
*   **役割**:
    *   クエリに基づいてArxivから新規論文を取得
    *   Google Sheetsを参照して重複を除外
    *   OpenAIを使用して要約と重要度判定を実施
    *   Slackへ整形されたブロックメッセージを投稿
    *   論文情報をGoogle Sheetsへ保存
*   **主要な環境変数**: `SLACK_API_TOKEN`, `OPENAI_API_KEY`, `SPREADSHEET_ID`

### 2. `paperReactionListener` (Listener)
*   **トリガー**: Lambda Function URL (Public, Auth: NONE - コード内で署名検証)
*   **ランタイム**: Python 3.9 (Container Image)
*   **役割**:
    *   Slack Event SubscriptionからのHTTP POSTを受信
    *   リクエスト署名 (`x-slack-signature`) を検証
    *   `reaction_added` イベントを解析
    *   SlackのタイムスタンプをキーにGoogle Sheetsの該当行を特定
    *   "Reactions" カラムに対応する絵文字を追記
*   **主要な環境変数**: `SLACK_SIGNING_SECRET`, `SPREADSHEET_ID`

## インフラ管理
*   **現状**: 手動管理 (AWS Management Console)
*   **今後**: IaC (Terraform/CDK) への移行を計画中 (参照: Issue #20)
