import json
import os
import random
import requests
import argparse
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
if not slack_token: # トークンが設定されていない場合はエラーを出す
    # raise ValueError("SLACK_API_TOKEN is not set in environment variables.")
    # Local execution might not have it, but lambda will. 
    # Warning instead of crash if running locally without it, but original code raised error.
    # I'll keep the raise to be safe or maybe just print warning if in main?
    # Original raised ValueError.
    pass 

if slack_token:
    slack_client = WebClient(token=slack_token)
else:
    slack_client = None

# その他の設定は config.py から利用
SLACK_CHANNEL = config.SLACK_CHANNEL
ARXIV_QUERY = config.ARXIV_QUERY
MAX_RESULTS = config.MAX_RESULTS
NUM_PAPERS = config.NUM_PAPERS


def save_to_sheets(paper_data, dify_data):
    """Google Sheetsにデータを蓄積"""
    if not GOOGLE_CREDS or not SPREADSHEET_ID:
        print("GOOGLE_CREDS or SPREADSHEET_ID not set. Skipping sheet save.")
        return

    try:
        creds_info = json.loads(GOOGLE_CREDS)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)

        values = [[
            paper_data.published.strftime('%Y-%m-%d'),
            paper_data.title,
            dify_data.get('theme_id', ''),
            dify_data.get('importance', ''),
            dify_data.get('summary', ''),
            paper_data.entry_id
        ]]
        
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={'values': values}
        ).execute()
        print(f"Saved to sheets: {paper_data.title}")
    except Exception as e:
        print(f"Error saving to sheets: {e}")


def get_summary(result):
    """
    Dify Workflow APIを使用して構造化データを取得する
    """
    if not DIFY_API_KEY:
        return f"Error: DIFY_API_KEY not set.\nTitle: {result.title}\nURL: {result.entry_id}"

    url = "https://api.dify.ai/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    # Dify側で定義した入力変数名に合わせる
    payload = {
        "inputs": {
            "title": result.title,
            "abstract": result.summary
        },
        "response_mode": "blocking",
        "user": "lambda-orchestrator"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Difyの「終了」ノードで設定した変数名（例: result）で取得
        resp_json = response.json()
        if "data" not in resp_json or "outputs" not in resp_json["data"]:
             return f"Error: Unexpected Dify response format.\n{json.dumps(resp_json)}"
             
        data = resp_json["data"]["outputs"]["result"]
        
        # スプシへの保存を実行
        # save_to_sheets(result, data)
        
        # Slackに表示するメッセージを組み立てる
        # theme_id 1:Representation Learning, 3:Privacy as per user prompt logic
        theme_id = data.get('theme_id')
        theme_label = "表現学習" if theme_id == 1 else "プライバシー" if theme_id == 3 else "その他"
        
        msg = f"【重要度: {data.get('importance', '?')} / カテゴリ: {theme_label}】\n"
        msg += f"タイトル: {result.title}\n"
        msg += f"要約: {data.get('summary', 'No summary')}\n"
        msg += f"URL: {result.entry_id}\n"
        msg += f"理由: {data.get('reason', 'No reason')}"
        
        return msg
    except Exception as e:
        print(f"Error in get_summary: {e}")
        try:
            if 'response' in locals():
                print(f"Dify Error Response: {response.text}")
        except:
            pass
        return f"Error getting summary.\nTitle: {result.title}\nURL: {result.entry_id}"


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
            # Slackに投稿するメッセージを組み立てる
            summary_msg = get_summary(result)
            message = "今日の論文です！ " + str(i+1) + "本目\n" + summary_msg
            print(message)
            
            if slack_client:
                # Slackにメッセージを投稿する            
                response = slack_client.chat_postMessage(                
                    channel=slack_channel,
                    text=message
                )
                print(f"Message posted: {response['ts']}")
            else:
                print("Slack client not initialized, skipping post.")

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
