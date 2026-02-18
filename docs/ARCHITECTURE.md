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
*   **ランタイム**: Python 3.12 (Container Image)
*   **役割**:
    *   クエリに基づいてArxivから新規論文を取得
    *   Google Sheetsを参照して重複を除外
    *   OpenAIを使用して要約と重要度判定を実施
    *   Slackへ整形されたブロックメッセージを投稿
    *   論文情報をGoogle Sheetsへ保存
*   **主要な環境変数**: `SLACK_API_TOKEN`, `OPENAI_API_KEY`, `SPREADSHEET_ID`

### 2. `paperReactionListener` (Listener)
*   **トリガー**: Lambda Function URL (Public, Auth: NONE - コード内で署名検証)
*   **ランタイム**: Python 3.12 (Container Image)
*   **役割**:
    *   Slack Event SubscriptionからのHTTP POSTを受信
    *   リクエスト署名 (`x-slack-signature`) を検証
    *   `reaction_added` イベントを解析
    *   SlackのタイムスタンプをキーにGoogle Sheetsの該当行を特定
    *   "Reactions" カラムに対応する絵文字を追記
*   **主要な環境変数**: `SLACK_SIGNING_SECRET`, `SPREADSHEET_ID`

## プロジェクト構造 (Mono-Repo)

本リポジトリはMono-Repo構成を採用しており、各サービスとインフラコードが統合されています。

```
.
├── services/
│   ├── notifier/        # 通知用Lambda (paperNotification)
│   │   ├── src/         # ソースコード
│   │   ├── tests/       # ユニットテスト
│   │   └── Dockerfile
│   └── listener/        # リアクション同期用Lambda (paperReactionListener)
│       ├── src/         # ソースコード
│       ├── tests/       # ユニットテスト
│       └── Dockerfile
├── infra/               # インフラストラクチャ定義 (AWS CDK - TypeScript)
├── .github/workflows/   # CI/CD パイプライン定義
└── docs/                # ドキュメント
```

## シーケンス図

### 1. 通知フロー (Notifier)

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant Lambda as Function: Notifier
    participant Arxiv as Arxiv API
    participant Sheet as Google Sheets
    participant OpenAI as OpenAI API
    participant Slack as Slack API

    EB->>Lambda: Trigger (Schedule)
    activate Lambda
    Lambda->>Arxiv: Search Papers (Query)
    activate Arxiv
    Arxiv-->>Lambda: List of Papers
    deactivate Arxiv

    Lambda->>Sheet: Get Existing Paper IDs
    activate Sheet
    Sheet-->>Lambda: ID List
    deactivate Sheet

    loop For each New Paper
        Lambda->>OpenAI: Abstract Summary & Scoring
        activate OpenAI
        OpenAI-->>Lambda: Summary Text
        deactivate OpenAI
        
        Lambda->>Slack: Post Message (Blocks)
        activate Slack
        Slack-->>Lambda: Success (ts)
        deactivate Slack

        Lambda->>Sheet: Save Paper Data (ID, Title, Summary, etc.)
    end
    deactivate Lambda
```

### 2. リアクション同期フロー (Listener)

```mermaid
sequenceDiagram
    participant User as Slack User
    participant Slack as Slack Platform
    participant Lambda as Function: Listener
    participant Sheet as Google Sheets

    User->>Slack: Add Reaction (:white_check_mark:)
    Slack->>Lambda: HTTP POST (event: reaction_added)
    activate Lambda
    Lambda->>Lambda: Verify Signature (HMAC)
    
    alt Invalid Signature
        Lambda-->>Slack: 401 Unauthorized
    else Valid Signature
        Lambda-->>Slack: 200 OK (Ack)
        note right of Lambda: Async Processing if heavy
        
        Lambda->>Sheet: Search Row by Timestamp (ts)
        activate Sheet
        Sheet-->>Lambda: Row Index
        deactivate Sheet
        
        Lambda->>Sheet: Update "Reactions" Column
    end
    deactivate Lambda
```

## データモデル (Google Sheets)

システムはGoogle Sheetsを簡易データベースとして使用します。

| Column | Field Name | Description |
| :--- | :--- | :--- |
| **A** | Published Date | 論文の公開日 |
| **B** | Title | 論文のタイトル |
| **C** | URL | ArxivのURL (IDとして利用) |
| **D** | Summary | OpenAIによる要約 |
| **E** | Author | 筆頭著者 |
| **F** | Categories | Arxivカテゴリタグ |
| **G** | Slack TS | Slack投稿時のタイムスタンプ (Listenerの検索キー) |
| **H** | Reactions | Slackで付与されたリアクション絵文字 |

## インフラ管理
*   **現状**: AWSリソースは手動またはCLIで作成済み。
*   **移行計画**: `infra/` ディレクトリにてAWS CDK (TypeScript) を用いたIaC管理へ移行予定 (参照: Issue #20)。
