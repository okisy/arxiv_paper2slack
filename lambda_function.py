import json
import os
import random
import requests
import argparse
import time
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import arxiv
from googleapiclient.discovery import build
from google.oauth2 import service_account

# config.py から設定をインポート
import config

# 追加する環境変数
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
# サービスアカウントのJSON
GOOGLE_CREDS = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

# Slackのトークンを環境変数から取得
slack_token = os.environ.get("SLACK_API_TOKEN")

# Slackクライアントの初期化
if slack_token:
    slack_client = WebClient(token=slack_token)
else:
    slack_client = None

# その他の設定は config.py から利用
SLACK_CHANNEL = config.SLACK_CHANNEL
ARXIV_QUERY = config.ARXIV_QUERY
MAX_RESULTS = config.MAX_RESULTS
NUM_PAPERS = config.NUM_PAPERS


def save_to_sheets(paper_data, dify_data, insert_index=0):
    """Google Sheetsにデータを蓄積 (新しいデータを上に挿入)"""
    if not GOOGLE_CREDS or not SPREADSHEET_ID:
        print("GOOGLE_CREDS or SPREADSHEET_ID not set. Skipping sheet save.")
        return

    try:
        creds_info = json.loads(GOOGLE_CREDS)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)

        values = [
            paper_data.published.strftime('%Y-%m-%d'),
            paper_data.title,
            dify_data.get('theme_id', ''),
            dify_data.get('importance', ''),
            dify_data.get('summary', ''),
            paper_data.entry_id
        ]
        
        # Calculate row index (0-based) for insertion. 
        # Header is row 0. We want to insert at row 1 + insert_index.
        # e.g. 1st paper (i=0) -> row 1.
        # e.g. 2nd paper (i=1) -> row 2.
        target_index = 1 + insert_index
        
        # 1. Insert a blank row
        requests = [{
            'insertDimension': {
                'range': {
                    'sheetId': 0,
                    'dimension': 'ROWS',
                    'startIndex': target_index,
                    'endIndex': target_index + 1
                },
                'inheritFromBefore': False
            }
        }]
        
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={'requests': requests}
        ).execute()
        
        # 2. Write data to that row
        # Range string uses 1-based indexing. row index `target_index` corresponds to row number `target_index + 1`.
        row_number = target_index + 1  
        range_name = f"A{row_number}"
        
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption="RAW",
            body={'values': [values]}
        ).execute()
        
        print(f"Saved to sheets at row {row_number}: {paper_data.title}")
    except Exception as e:
        print(f"Error saving to sheets: {e}")


def get_dify_result(result):
    """
    Dify Workflow APIを使用して構造化データを取得する
    Returns: dict with data, or None on error
    """
    if not DIFY_API_KEY:
        print("Error: DIFY_API_KEY not set.")
        return None

    url = "https://api.dify.ai/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Truncate inputs to avoid errors (Title < 512, Abstract < 8192 as per Dify settings)
    title_input = result.title[:500] 
    abstract_input = result.summary[:8000]

    payload = {
        "inputs": {
            "title": title_input,
            "abstract": abstract_input
        },
        "response_mode": "blocking",
        "user": "lambda-orchestrator"
    }
    
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            
            resp_json = response.json()
            if "data" not in resp_json or "outputs" not in resp_json["data"]:
                 print(f"Error: Unexpected Dify response format.\n{json.dumps(resp_json)}")
                 return None
                 
            data = resp_json["data"]["outputs"]["result"]
            return data

        except Exception as e:
            print(f"Attempt {attempt+1}/{max_retries} failed in get_dify_result: {e}")
            try:
                if 'response' in locals():
                    print(f"Dify Error Response: {response.text}")
            except:
                pass
            
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt) # Exponential backoff: 2s, 4s, 8s
                print(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print("Max retries reached. Giving up on this paper.")
                return None

def build_slack_blocks(paper, dify_data, index):
    """Slack Block Kitを構築する"""
    
    if dify_data:
        theme_id = dify_data.get('theme_id')
        theme_label = "表現学習" if theme_id == 1 else "プライバシー" if theme_id == 3 else "その他"
        importance = dify_data.get('importance', '?')
        summary = dify_data.get('summary', 'No summary')
        reason = dify_data.get('reason', 'No reason')
        
        # Determine emoji based on importance
        try:
            imp_val = int(importance)
            star = "⭐️" * imp_val
        except:
            star = str(importance)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📄 {index}本目: {paper.title[:140]}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*カテゴリ:*\n{theme_label}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*重要度:*\n{star}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*発行日:*\n{paper.published.strftime('%Y-%m-%d')}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*要約:*\n{summary}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*理由:*\n{reason}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Read Paper",
                            "emoji": True
                        },
                        "url": paper.entry_id
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        return blocks, f"New Paper: {paper.title}" # Fallback text
    else:
        # Fallback for errors
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"⚠️ *Error getting details for paper {index}*\nTitle: {paper.title}\nURL: {paper.entry_id}"
                }
            },
            {
                "type": "divider"
            }
        ]
        return blocks, f"Error processing paper: {paper.title}"


def main(slack_channel, query, max_results, num_papers):        
    # arxiv APIで最新の論文情報を取得する
    print(f"Searching arxiv for: {query}")
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,  # 検索クエリ        
        max_results=max_results,  # 取得する論文数
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 論文を投稿された日付でソートする
        sort_order=arxiv.SortOrder.Descending,  # 新しい論文から順に取得する
    )
    #searchの結果をリストに格納
    result_list = []
    for result in client.results(search):
        result_list.append(result)
    
    print(f"Found {len(result_list)} papers.")
    
    #ランダムにnum_papersの数だけ選ぶ
    if len(result_list) > num_papers:
        results = random.sample(result_list, k=num_papers)
    else:
        results = result_list

    # 論文情報をSlackに投稿する
    for i, result in enumerate(results):
        try:
            print(f"Processing paper {i+1}: {result.title}...")
            
            # Difyからデータを取得
            dify_data = get_dify_result(result)
            
            # Save to sheets if successful
            if dify_data:
                save_to_sheets(result, dify_data, insert_index=i)

            # Build Slack Blocks
            blocks, fallback_text = build_slack_blocks(result, dify_data, i+1)
            
            if slack_client:
                # Slackにメッセージを投稿する            
                response = slack_client.chat_postMessage(                
                    channel=slack_channel,
                    text=fallback_text,
                    blocks=blocks
                )
                print(f"Message posted: {response['ts']}")
            else:
                print("Slack client not initialized, skipping post.")
            
            # Rate limit avoidance (sleep 2 seconds between requests)
            time.sleep(2)

        except SlackApiError as e:
            print(f"Error posting message: {e}")

def lambda_handler(event, context):
    """
    AWS Lambdaのハンドラー関数
    """        
    main(SLACK_CHANNEL, ARXIV_QUERY, MAX_RESULTS, NUM_PAPERS)
    return {
        'statusCode': 200,
        'body': json.dumps('Slackへの投稿が完了しました。')
    }

if __name__ == "__main__":    
    parser = argparse.ArgumentParser(description='Arxiv papers to Slack poster')
    parser.add_argument('--slack_channel', type=str, default=SLACK_CHANNEL, help='Slack channel to post to')
    parser.add_argument('--query', type=str, default=ARXIV_QUERY, help='Search query for arxiv')
    parser.add_argument('--max_results', type=int, default=MAX_RESULTS, help='Maximum number of papers to fetch')
    parser.add_argument('--num_papers', type=int, default=NUM_PAPERS, help='Number of papers to randomly select')
    
    args = parser.parse_args()
    
    # Override global if args provided (though main takes args so it's fine)
    main(args.slack_channel, args.query, args.max_results, args.num_papers)
