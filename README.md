# Arxiv Paper to Slack Notifier

## 概要
Arxiv APIを使って最新の論文を取得し、**Dify Workflow** で要約・分類を行った後、以下の2つのアクションを実行するシステムです。

1.  **Slack通知**: Slack Block Kitを使用したリッチなUIで論文情報を通知します。
2.  **Google Sheets保存**: 論文情報をGoogleスプレッドシートに自動的に蓄積します（新しい論文が上に追加されます）。

## 主な機能
*   **高度な検索**: Network Traffic, Geospatial AI, 6G, Smart City などの特定領域にフォーカスした論文を検索します。
*   **AI要約 (Dify)**: 論文のタイトルと要約をDify Workflowに送信し、日本語要約・重要度判定・カテゴリ分類を行います。
*   **Slack連携**: 重要度に応じたスター表示、ボタンリンクなどのリッチなメッセージを送信します。
*   **Sheets連携**: 取得した論文をスプレッドシートにアーカイブします。重複チェックやヘッダー管理も行います。

## 環境構築

### 必要な環境変数
AWS Lambdaの環境変数として以下を設定してください。

| キー | 説明 | 例 |
|---|---|---|
| `SLACK_API_TOKEN` | Slack Bot User OAuth Token (xoxb-...) | `xoxb-123...` |
| `SLACK_CHANNEL` | 通知先のチャンネルIDまたは名前 | `#general` |
| `DIFY_API_KEY` | Dify Workflow API Key | `app-...` |
| `SPREADSHEET_ID` | 保存先のGoogleスプレッドシートID | `1cjGSn5...` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google Sheets API用サービスアカウントのJSON全文 | `{"type": "service_account", ...}` |
| `LANG` | 文字コード設定 | `C.UTF-8` |

### ローカルでの実行
[uv](https://github.com/astral-sh/uv) または `pip` を使用して依存関係をインストールします。

```bash
uv pip install -r requirements.txt
# または
pip install -r requirements.txt
```

実行コマンド:
```bash
python lambda_function.py
```

## AWS Lambda デプロイ (CI/CD)

GitHub Actions (`.github/workflows/ci-cd.yml`) により、`main` ブランチへのプッシュ時に自動的に Docker イメージがビルドされ、AWS Lambda にデプロイされます。

1.  **Build**: `public.ecr.aws/lambda/python:3.12` ベースのイメージを作成。
2.  **Push**: Amazon ECR にプッシュ。
3.  **Deploy**: AWS Lambda のコードを更新。

## Google Sheets の仕様
*   カラム構成: `['発行日', 'タイトル', 'カテゴリ', '重要度', '要約', 'URL']`
*   新しい論文はヘッダー行（1行目）のすぐ下（2行目）に挿入され、過去のデータは下に押し出されます。

## 開発フロー
機能追加や修正を行う際は、以下のフローを遵守してください。
1.  機能ブランチを作成 (`feature/...`)
2.  変更を実施・ローカル検証
3.  **Pull Request (または差分共有)** を通じて承認を得る
4.  `main` ブランチへマージしてデプロイ