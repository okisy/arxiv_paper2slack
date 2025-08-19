import json
import os
import random
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import arxiv
import openai
from openai import OpenAI
import argparse


# #OpenAIのapiキー
# openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', 'OpenAIのAPIキー'))
# # Slack APIトークン
# SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN', 'SlackbotのAPIToken')

# config.py から設定をインポート
import config

# OpenAIのAPIキーとSlackのトークンを環境変数から取得
openai.api_key = os.environ.get("OPENAI_API_KEY")
slack_token = os.environ.get("SLACK_API_TOKEN")

# Slackクライアントの初期化
if not slack_token: # トークンが設定されていない場合はエラーを出す
    raise ValueError("SLACK_API_TOKEN is not set in environment variables.")
slack_client = WebClient(token=slack_token)

# OpenAIクライアントの初期化
if not openai.api_key:  # APIキーが設定されていない場合はエラーを出す
    raise ValueError("OPENAI_API_KEY is not set in environment variables.")
openai_client = OpenAI()

# その他の設定は config.py から利用
SLACK_CHANNEL = config.SLACK_CHANNEL
ARXIV_QUERY = config.ARXIV_QUERY
MAX_RESULTS = config.MAX_RESULTS
NUM_PAPERS = config.NUM_PAPERS


def get_summary(result):
    system = """与えられた論文の要点を3点のみでまとめ、以下のフォーマットで日本語で出力してください。
    ```
    タイトルの日本語訳
    ・要点1
    ・要点2
    ・要点3
    ```
    """

    text = f"title: {result.title}\nbody: {result.summary}"
    response = openai_client.chat.completions.create(model="gpt-5-mini",
    messages=[
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': text}
    ],    
    )
    summary = response.choices[0].message.content
    title_en = result.title
    title, *body = summary.split('\n')
    body = '\n'.join(body)
    date_str = result.published.strftime("%Y-%m-%d %H:%M:%S")
    message = f"発行日: {date_str}\n{result.entry_id}\n{title_en}\n{title}\n{body}\n"

    return message


def main(slack_channel, query, max_results, num_papers):        
    # arxiv APIで最新の論文情報を取得する
    search = arxiv.Search(
        query=query,  # 検索クエリ        
        max_results=max_results,  # 取得する論文数
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 論文を投稿された日付でソートする
        sort_order=arxiv.SortOrder.Descending,  # 新しい論文から順に取得する
    )
    #searchの結果をリストに格納
    result_list = []
    for result in search.results():
        result_list.append(result)
    #ランダムにnum_papersの数だけ選ぶ    
    results = random.sample(result_list, k=num_papers)

    # 論文情報をSlackに投稿する
    for i, result in enumerate(results):
        try:
            # Slackに投稿するメッセージを組み立てる
            message = "今日の論文です！ " + str(i+1) + "本目\n" + get_summary(result)
            print(message)
            # Slackにメッセージを投稿する            
            response = slack_client.chat_postMessage(                
                channel=slack_channel,
                text=message
            )
            print(f"Message posted: {response['ts']}")
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
    parser.add_argument('--slack_channel', type=str, default='#general', help='Slack channel to post to')
    parser.add_argument('--query', type=str, default='ti:"Deep Learning"', help='Search query for arxiv')
    parser.add_argument('--max_results', type=int, default=100, help='Maximum number of papers to fetch')
    parser.add_argument('--num_papers', type=int, default=3, help='Number of papers to randomly select')
    
    args = parser.parse_args()
    main(args.slack_channel, args.query, args.max_results, args.num_papers)
