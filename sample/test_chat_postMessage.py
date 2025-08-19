import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 環境変数からSlack Bot Tokenを取得
slack_token = os.environ["SLACK_API_TOKEN"]
client = WebClient(token=slack_token)

channel_id = "general"  # 送信先チャンネルIDを指定
# message = "Hello, Slack! :tada:"
message = "こんにちは、Slack！ :tada:"

try:
    response = client.chat_postMessage(
        channel=channel_id,
        text=message
    )
    print("Message sent: ", response["ts"])
except SlackApiError as e:
    print(f"Error sending message: {e.response['error']}")