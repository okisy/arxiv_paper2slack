import json
import os
import random
import argparse
import time
import re
from typing import List, Dict, Any, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import feedparser
from googleapiclient.discovery import build
from google.oauth2 import service_account
import openai
import logging
import ssl
import certifi

# config.py から設定をインポート
import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)

# 環境変数
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
# サービスアカウントのJSON
GOOGLE_CREDS = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
# OpenAI Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Slackのトークンを環境変数から取得
slack_token = os.environ.get("SLACK_API_TOKEN")

# Slackクライアントの初期化 (macOSの証明書エラー対策としてcertifiを利用)
if slack_token:
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    slack_client = WebClient(token=slack_token, ssl=ssl_context)
else:
    slack_client = None

# その他の設定は config.py から利用
SLACK_CHANNEL = config.SLACK_CHANNEL
ARXIV_QUERY = config.ARXIV_QUERY
MAX_RESULTS = config.MAX_RESULTS
NUM_PAPERS = config.NUM_PAPERS


@dataclass
class Paper:
    title: str
    summary: str
    entry_id: str
    published: datetime


def extract_phrases(query_string: str) -> List[str]:
    """Extract terms enclosed in double quotes or separated by OR from config."""
    if not query_string:
        return []
    if '"' in query_string:
        return re.findall(r'"([^"]+)"', query_string)
    else:
        return [p.strip() for p in query_string.split(' OR ') if p.strip()]


def matches_query(text: str, config_ai: str, config_domain: str) -> bool:
    """Check if the text matches at least one AI keyword AND at least one Domain keyword."""
    if not text:
        return False
    text_lower = text.lower()
    
    ai_phrases = extract_phrases(config_ai)
    domain_phrases = extract_phrases(config_domain)
    
    match_ai = any(p.lower() in text_lower for p in ai_phrases) if ai_phrases else True
    match_domain = any(p.lower() in text_lower for p in domain_phrases) if domain_phrases else True
    
    return match_ai and match_domain


def get_existing_paper_ids() -> Set[str]:
    """Retrieves existing paper IDs (URLs) from Google Sheets to prevent duplicates.

    Returns:
        Set[str]: A set of paper URLs (entry_ids) already processed.
    """
    if not GOOGLE_CREDS or not SPREADSHEET_ID:
        print("GOOGLE_CREDS or SPREADSHEET_ID not set. Skipping deduplication check.")
        return set()

    try:
        creds_info = json.loads(GOOGLE_CREDS)
        creds = service_account.Credentials.from_service_account_info(creds_info)
        service = build('sheets', 'v4', credentials=creds)

        # F列 (URL/Entry ID) を取得
        range_name = "F2:F" 
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=range_name).execute()
        rows = result.get('values', [])
        
        existing_ids = set()
        for row in rows:
            if row:
                existing_ids.add(row[0])
        
        print(f"Found {len(existing_ids)} existing papers in sheets.")
        return existing_ids
    except Exception as e:
        print(f"Error fetching existing papers: {e}")
        return set()


def save_to_sheets(paper_data: Any, dify_data: Dict[str, Any], slack_ts: str, insert_index: int = 0) -> None:
    """Saves paper metadata to Google Sheets. Inserts a new row at the specified index.

    Args:
        paper_data (Any): The arxiv paper object containing metadata.
        dify_data (Dict[str, Any]): The AI-generated summary and scoring data.
        slack_ts (str): The timestamp of the Slack message posting.
        insert_index (int, optional): The offset index for insertion. Defaults to 0.
    """
    if not GOOGLE_CREDS or not SPREADSHEET_ID:
        logger.warning("GOOGLE_CREDS or SPREADSHEET_ID not set. Skipping sheet save.")
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
            paper_data.entry_id,
            slack_ts # Column G: Slack Message Timestamp
        ]
        
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
        row_number = target_index + 1  
        range_name = f"A{row_number}"
        
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_name,
            valueInputOption="RAW",
            body={'values': [values]}
        ).execute()
        
        logger.info(f"Saved to sheets at row {row_number}: {paper_data.title}")
    except Exception as e:
        logger.error(f"Failed to write to Spreadsheet: {e}")


def generate_paper_summary(paper_title: str, paper_abstract: str, model: str = "gpt-5-mini") -> Dict[str, Any]:
    """Generates a summary and score for a paper using an LLM.

    Args:
        paper_title (str): Title of the paper.
        paper_abstract (str): Abstract of the paper.
        model (str, optional): The LLM model to use. Defaults to "gpt-5-mini".

    Returns:
        Dict[str, Any]: A dictionary containing 'summary', 'importance', 'theme_id', and 'reason'.
    """
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set.")
        return _fallback_result(paper_abstract, "Missing API Key")

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""
    あなたは空間統計とプライバシーの専門家です。以下の論文を解析し、構造化JSONで出力してください。
    タイトル: {paper_title}
    抄録: {paper_abstract}

    ## 出力項目
    - importance: 1-5の整数（5が最高）
    - theme_id: 1(表現学習) または 3(プライバシー保護) または 0(その他)
    - summary: 論文の要点を実務家向けに3行で要約
    - reason: そのスコア・テーマを付けた数理的・実務的な理由
    
    Output JSON format example:
    {{
        "summary": "要約文...",
        "importance": 5,
        "theme_id": 1,
        "reason": "理由..."
    }}
    """

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful research assistant."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data

    except Exception as e:
        print(f"LLM Error: {e}")
        return _fallback_result(paper_abstract, "LLM Processing Failed")

def _fallback_result(abstract: str, reason_suffix: str) -> Dict[str, Any]:
    """Generates a fallback result dictionary when LLM processing fails.

    Args:
        abstract (str): The original paper abstract.
        reason_suffix (str): The error reason to append.

    Returns:
        Dict[str, Any]: A fallback dictionary with truncated abstract.
    """
    return {
        "summary": abstract[:500] + "..." if len(abstract) > 500 else abstract,
        "importance": "?",
        "theme_id": "?",
        "reason": f"System Error: {reason_suffix}. Showing raw abstract."
    }


def build_slack_blocks(paper: Any, ai_data: Dict[str, Any], index: int) -> Tuple[List[Dict[str, Any]], str]:
    """Constructs the Slack Block Kit message structure.

    Args:
        paper (Any): The arxiv paper object.
        ai_data (Dict[str, Any]): The AI-generated summary and scoring.
        index (int): The sequence number of the paper in the current batch.

    Returns:
        Tuple[List[Dict[str, Any]], str]: A tuple containing the blocks list and fallback text.
    """
    
    theme_id = ai_data.get('theme_id')
    
    if theme_id == 1:
        theme_label = "表現学習"
    elif theme_id == 3:
        theme_label = "プライバシー"
    elif str(theme_id) == "?":
        theme_label = "不明 (?)"
    else:
        theme_label = "その他"

    importance = ai_data.get('importance', '?')
    summary = ai_data.get('summary', 'No summary')
    reason = ai_data.get('reason', 'No reason')
    
    # Determine emoji based on importance
    try:
        imp_val = int(importance)
        star = "⭐️" * imp_val
    except (ValueError, TypeError):
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
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "plain_text",
                    "text": f"Posted at: {datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')} (JST)",
                    "emoji": True
                }
            ]
        }
    ]
    return blocks, f"New Paper: {paper.title}"


 

def main(slack_channel: str, query: str, max_results: int, num_papers: int) -> None:
    """Main execution entry point.

    Fetches papers from Arxiv, filters duplicates, generates summaries, posts to Slack,
    and saves metadata to Google Sheets.

    Args:
        slack_channel (str): The Slack channel ID or name to post to.
        query (str): The Arxiv search query.
        max_results (int): Maximum number of papers to fetch from Arxiv API.
        num_papers (int): Number of papers to select and post.
    """        
    # 0. Get existing papers for deduplication
    existing_ids = get_existing_paper_ids()

    # 1. Fetch from arXiv RSS Feeds
    logger.info("Fetching papers from arXiv RSS feeds...")
    rss_feeds = [
        'http://export.arxiv.org/rss/cs',
        'http://export.arxiv.org/rss/eess',
        'http://export.arxiv.org/rss/stat',
        'http://export.arxiv.org/rss/math'
    ]
    
    all_results = []
    seen_urls = set()
    failed_feeds = 0
    
    # User-Agent is required to bypass arXiv's basic crawler blocking
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    import requests
    
    for feed_url in rss_feeds:
        try:
            logger.info(f"Requesting RSS feed: {feed_url}")
            response = requests.get(feed_url, headers=headers, timeout=20)
            if response.status_code != 200:
                logger.warning(f"Non-200 status code from {feed_url}: {response.status_code}")
                failed_feeds += 1
                continue
                
            feed = feedparser.parse(response.content)
            if getattr(feed, 'bozo', False):
                logger.warning(f"Bozo exception parsing {feed_url} (malformed XML?): {feed.bozo_exception}")
            
            feed_matches = 0
            for entry in feed.entries:
                title = entry.get('title', '')
                title_clean = re.sub(r'<[^>]+>', '', title)
                
                summary = entry.get('summary', '')
                summary_clean = re.sub(r'<[^>]+>', '', summary)
                
                # Check keywords using the standalone config variables
                if matches_query(title_clean + " " + summary_clean, config.keywords_ai, config.keywords_domain):
                    entry_id = entry.get('link', '')
                    if entry_id in seen_urls:
                        continue
                        
                    seen_urls.add(entry_id)
                    feed_matches += 1
                    
                    published_parsed = entry.get('published_parsed') or entry.get('updated_parsed')
                    if published_parsed:
                        published_dt = datetime.fromtimestamp(time.mktime(published_parsed), tz=timezone.utc)
                    else:
                        published_dt = datetime.now(timezone.utc)
                    
                    paper = Paper(
                        title=title_clean.replace('\\n', ' '),
                        summary=summary_clean.replace('\\n', ' '),
                        entry_id=entry_id,
                        published=published_dt
                    )
                    all_results.append(paper)
                    
            logger.info(f"Extracted {feed_matches} matching papers from {feed_url} (out of {len(feed.entries)} total entries).")
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while fetching {feed_url}")
            failed_feeds += 1
        except Exception as e:
            logger.exception(f"Unexpected error processing {feed_url}: {e}")
            failed_feeds += 1
            
    if failed_feeds == len(rss_feeds):
        error_msg = "⚠️ arXiv RSSからの論文取得中に全フィードでエラーが発生しました。取得処理全体をスキップします。"
        logger.error(error_msg)
        if slack_client and slack_channel:
            try:
                slack_client.chat_postMessage(channel=slack_channel, text=error_msg)
            except Exception as slack_e:
                logger.error(f"Failed to post error to Slack: {slack_e}")
        return
    
    logger.info(f"Found {len(all_results)} papers total matching local extraction logic.")

    # 2. Filter Duplicates
    new_papers = [p for p in all_results if p.entry_id not in existing_ids]
    logger.info(f"Found {len(new_papers)} new papers after deduplication.")

    if not new_papers:
        logger.info("No new papers to send.")
        return

    # 3. Random Shuffle for selection
    random.shuffle(new_papers)
    
    # 4. Process until NUM_PAPERS sent
    papers_sent = 0
    paper_index = 0
    
    sent_paper_urls = []

    # Try to process papers until we hit the target count or run out of papers
    while papers_sent < num_papers and paper_index < len(new_papers):
        paper = new_papers[paper_index]
        paper_index += 1
        
        try:
            logger.info(f"Processing paper {papers_sent+1}/{num_papers} (Candidate {paper_index}): {paper.title}...")
            
            # AI Inference (with fallback safety)
            ai_data = generate_paper_summary(paper.title, paper.summary)
            
            # Build Slack Blocks
            blocks, fallback_text = build_slack_blocks(paper, ai_data, papers_sent+1)
            
            # デバッグやLambdaのログ用にテキストとして出力しておく
            logger.info(f"\n--- [Generated Slack Post] {paper.title} ---\n{fallback_text}\n------------------------------------------\n")
            
            slack_ts = ""
            if slack_client:
                response = slack_client.chat_postMessage(                
                    channel=slack_channel,
                    text=fallback_text,
                    blocks=blocks
                )
                slack_ts = response['ts']
                logger.info(f"Message posted: {slack_ts}")
                sent_paper_urls.append(paper.entry_id) # Track for prompt
            else:
                logger.info("Slack client not initialized, skipping post (would have posted).")

            # Save to sheets
            save_to_sheets(paper, ai_data, slack_ts, insert_index=papers_sent)
            
            papers_sent += 1
            
            # Rate limit avoidance
            time.sleep(2)

        except SlackApiError as e:
            logger.error(f"Slack API Error posting message: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in loop for paper {paper.title}: {e}")

    logger.info(f"Finished. Sent {papers_sent}/{num_papers} papers.")

    # 5. Post Gemini Prompt Bundle
    prompt_channel = config.SLACK_PROMPT_CHANNEL
    if sent_paper_urls and prompt_channel and slack_client:
        try:
            logger.info(f"Posting Gemini prompt to {prompt_channel}")
            
            urls_block = "\n".join(sent_paper_urls)
            prompt_text = f"{urls_block}\nこれらの論文についてなにがすごいのか教えて"
            
            slack_client.chat_postMessage(
                channel=prompt_channel,
                text=prompt_text
            )
            logger.info("Gemini prompt posted.")
        except Exception as e:
            logger.error(f"Failed to post Gemini prompt: {e}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Args:
        event (Dict[str, Any]): The Lambda event payload.
        context (Any): The Lambda context object.

    Returns:
        Dict[str, Any]: The response object containing statusCode and body.
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
    main(args.slack_channel, args.query, args.max_results, args.num_papers)
