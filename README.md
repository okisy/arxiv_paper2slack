# Arxiv Paper to Slack Notifier + Reaction Sync

## 概要
Arxiv APIを使って最新の論文を取得し、AIで要約してSlackに通知するシステムです。
さらに、Slack上でそのメッセージにリアクション（スタンプ）を付けると、自動的にGoogleスプレッドシートに同期される機能（Phase 2）も備えています。

## システム構成
このプロジェクトは2つのAWS Lambda関数で構成されています。

1.  **Notification Function (`arxiv-paper-notifier`)**
    *   定期的に起動（AWS EventBridge Rule: 日本時間 朝10:00）。
    *   Arxivから論文を取得 -> OpenAIで要約 -> Slackへ通知 -> スプレッドシートへ保存。
2.  **Listener Function (`arxiv-slack-listener`)**
    *   Slackからのイベント（Event API）で起動。
    *   `reaction_added` イベントを受け取り、スプレッドシートの該当行（H列）にリアクション名を追記。

## 主な機能
*   **論文検索 & 通知**: 特定領域（Network Traffic, Geospatial AI, 6Gなど）の論文を検索し、SlackにBlock Kitで通知します。
*   **AI要約 (OpenAI)**: `gpt-5-mini` を使用して、日本語要約・重要度判定・カテゴリ分類を行います。
*   **スプレッドシート連携**:
    *   **保存**: 取得した論文を一覧化。
    *   **リアクション同期**: Slackで「🎉」などを付けると、シートの「Slack TS」列（G列）と照合し、「Reactions」列（H列）に自動反映します。

## 環境構築

### 必要な環境変数

#### 1. Notification Function (`arxiv-paper-notifier`)
通知用Lambdaの設定です。

| キー | 説明 | 例 |
|---|---|---|
| `SLACK_API_TOKEN` | Slack Bot User OAuth Token (xoxb-...) | `xoxb-123...` |
| `SLACK_CHANNEL` | 通知先のチャンネルIDまたは名前 | `#general` |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-...` |
| `SPREADSHEET_ID` | 保存先のGoogleスプレッドシートID | `1cjGSn5...` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Sheets API用サービスアカウントのJSON全文 | `{"type": "...}` |
| `LANG` | 文字コード設定 | `C.UTF-8` |

#### 2. Listener Function (`arxiv-slack-listener`) **[Phase 2 New]**
リアクション同期用Lambdaの設定です。

| キー | 説明 | 例 |
|---|---|---|
| `SLACK_SIGNING_SECRET` | Slack AppのBasic InformationにあるSigning Secret | `b69...` |
| `SPREADSHEET_ID` | (共通) 保存先のGoogleスプレッドシートID | `1cjGSn5...` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | (共通) Google Sheets API用サービスアカウント | `{"type": "...}` |
| `LANG` | 文字コード設定 | `C.UTF-8` |

### Slack App設定 (Listener用)
Listenerを動作させるには、Slack Appの管理画面で以下の設定が必要です。

1.  **Event Subscriptions** を有効化 (`On`)。
2.  **Request URL** に `arxiv-slack-listener` の **関数URL** を設定。
    *   認証タイプ: `NONE`
    *   検証が成功し `Verified` になること。
3.  **Subscribe to bot events** に `reaction_added` を追加。
4.  設定変更後、アプリを **Reinstall** する。

## ローカルでの実行

### セットアップ
`pip` を使用して依存関係をインストールします（標準）。
※ [uv](https://github.com/astral-sh/uv) を使用している場合は `uv pip install` も可能です。

#### 共通
リポジトリのルートで作業します。

#### Notification (Poster)
```bash
cd services/notifier
pip install -r requirements.txt
python src/main.py
```

#### Listener (Reaction Sync)
```bash
cd services/listener
pip install -r requirements.txt
# ローカル検証用スクリプト (環境変数の設定が必要)
# python ../verify_listener_local.py (※スクリプトが存在する場合)
```

## AWS Lambda デプロイ (CI/CD)

GitHub Actions (`.github/workflows/ci-cd.yml`) により、`main` ブランチへのプッシュ時に自動的にデプロイされます。

*   **arxiv-notifier**: Notification Function (ルートディレクトリ)
*   **arxiv-listener**: Listener Function (`arxiv-slack-listener/` ディレクトリ)
    *   こちらは新しいECRリポジトリ `arxiv-listener` を使用します。

## Google Sheets の仕様
*   **G列 (Slack TS)**: 通知時にSlackのメッセージタイムスタンプを記録（キーとして使用）。
*   **H列 (Reactions)**: 同期されたリアクション名がカンマ区切りなどで追記されます。