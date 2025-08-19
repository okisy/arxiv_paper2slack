import json
import os
import random
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import arxiv
from openai import OpenAI


#OpenAIのapiキー
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', 'OpenAIのAPIキー'))
# Slack APIトークン
SLACK_API_TOKEN = os.getenv('SLACK_API_TOKEN', 'SlackbotのAPIToken')
# Slackに投稿するチャンネル名を指定する
SLACK_CHANNEL = "#general"

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


def main():
    # Slack APIクライアントを初期化する
    slack_client = WebClient(token=SLACK_API_TOKEN)
    #queryを用意
    query ='ti:%22 Deep Learning %22'

    # arxiv APIで最新の論文情報を取得する
    search = arxiv.Search(
        query=query,  # 検索クエリ
        max_results=100,  # 取得する論文数
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 論文を投稿された日付でソートする
        sort_order=arxiv.SortOrder.Descending,  # 新しい論文から順に取得する
    )
    #searchの結果をリストに格納
    result_list = []
    for result in search.results():
        result_list.append(result)
    #ランダムにnum_papersの数だけ選ぶ
    num_papers = 3
    results = random.sample(result_list, k=num_papers)

    # 論文情報をSlackに投稿する
    for i, result in enumerate(results):
        try:
            # Slackに投稿するメッセージを組み立てる
            message = "今日の論文です！ " + str(i+1) + "本目\n" + get_summary(result)
            print(message)
            # Slackにメッセージを投稿する
            response = slack_client.chat_postMessage(
                channel=str(SLACK_CHANNEL),
                text=str(message)
            )
            print(f"Message posted: {response['ts']}")
        except SlackApiError as e:
            print(f"Error posting message: {e}")

def lambda_handler(event, context):
    """
    AWS Lambdaのハンドラー関数
    """
    main()
    return {
        'statusCode': 200,
        'body': json.dumps('Slackへの投稿が完了しました。')
    }

if __name__ == "__main__":
    main()
