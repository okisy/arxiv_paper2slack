import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add root directory to sys.path so we can import lambda_function
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from main import build_slack_blocks, generate_paper_summary, main

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setenv("SLACK_API_TOKEN", "mock_token")
    monkeypatch.setenv("SPREADSHEET_ID", "mock_sheet_id")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setenv("OPENAI_API_KEY", "mock_key")
    monkeypatch.setenv("SLACK_PROMPT_CHANNEL", "#mock-prompt-channel")

@pytest.fixture
def mock_paper():
    paper = MagicMock()
    paper.entry_id = "http://arxiv.org/abs/2601.0001"
    paper.title = "Test Paper"
    paper.summary = "Test Abstract"
    paper.published.strftime.return_value = "2026-01-01"
    return paper

def test_build_slack_blocks(mock_paper):
    ai_data = {
        "theme_id": 1,
        "importance": 5,
        "summary": "AI Generated Summary",
        "reason": "AI Generated Reason"
    }
    
    blocks, text = build_slack_blocks(mock_paper, ai_data, 1)
    
    assert "Test Paper" in text
    
    # Check Header
    assert blocks[0]["type"] == "header"
    assert "Test Paper" in blocks[0]["text"]["text"]
    
    # Check Theme Label (theme_id=1 -> 表現学習)
    assert "**カテゴリ:**\n表現学習" in blocks[1]["fields"][0]["text"].replace("*", "**") # slack mrkdwn check
    
    # Check Stars (importance=5 -> ⭐️⭐️⭐️⭐️⭐️)
    assert "⭐️⭐️⭐️⭐️⭐️" in blocks[1]["fields"][1]["text"]
    
    # Check Button URL
    assert blocks[4]["elements"][0]["url"] == "http://arxiv.org/abs/2601.0001"

def test_generate_paper_summary_success(mock_env):
    with patch("main.openai.OpenAI") as mock_openai, \
         patch("main.OPENAI_API_KEY", "mock_key"):
        mock_client = mock_openai.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"summary": "Short sum", "importance": 3, "theme_id": 3, "reason": "Because"}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        result = generate_paper_summary("Title", "Abstract")
        
        assert result["summary"] == "Short sum"
        assert result["importance"] == 3

def test_generate_paper_summary_failure(mock_env):
    # Test when API call fails
    with patch("main.openai.OpenAI") as mock_openai, \
         patch("main.OPENAI_API_KEY", "mock_key"):
        mock_client = mock_openai.return_value
        # Mock the method call to raise exception
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = generate_paper_summary("Title", "Abstract")
        
        # Fallback behavior
        assert "Abstract" in result["summary"]
        assert result["importance"] == "?"

@patch("main.requests.get")
@patch("main.feedparser.parse")
@patch("main.matches_query")
@patch("main.slack_client")
@patch("main.generate_paper_summary")
@patch("main.save_to_sheets")
@patch("main.get_existing_paper_ids")
@patch("main.config.SLACK_PROMPT_CHANNEL", "#mock-prompt-channel")
def test_main_flow(mock_get_existing, mock_save, mock_gen_summary, mock_slack, mock_matches, mock_feedparser, mock_requests, mock_env):
    # Setup
    mock_get_existing.return_value = set() # No existing papers
    mock_matches.return_value = True
    
    # Mock RSS
    mock_requests.return_value.status_code = 200
    mock_feed = MagicMock()
    mock_feed.entries = [{
        'title': 'Test Paper',
        'summary': 'Test Abstract',
        'link': 'http://arxiv.org/abs/2601.0001',
        'published_parsed': None
    }]
    mock_feedparser.return_value = mock_feed
    
    # Mock AI
    mock_gen_summary.return_value = {
        "summary": "AI Sum", "importance": 4, "theme_id": 0, "reason": "R"
    }
    
    # Mock Slack Response (for ts)
    mock_slack.chat_postMessage.return_value = {"ts": "1234.5678"}
    
    # Run Main (request 1 paper)
    main("channel", "query", 5, 1)
    
    # Verify Slack called for paper
    assert mock_slack.chat_postMessage.call_count >= 1
    call_args = mock_slack.chat_postMessage.call_args_list[0]
    assert call_args.kwargs["channel"] == "channel"
    
    # Verify Sheet Save called
    mock_save.assert_called()
    
    # Verify Gemini Prompt Bundle
    last_call = mock_slack.chat_postMessage.call_args_list[-1]
    if "なにがすごいのか教えて" in last_call.kwargs.get("text", ""):
        assert last_call.kwargs["channel"] == "#mock-prompt-channel"
        assert "http://arxiv.org/abs/2601.0001" in last_call.kwargs["text"]

@patch("main.requests.get")
@patch("main.feedparser.parse")
@patch("main.matches_query")
@patch("main.slack_client")
@patch("main.get_existing_paper_ids")
def test_main_no_new_papers(mock_get_existing, mock_slack, mock_matches, mock_feedparser, mock_requests, mock_env):
    """Test scenario where no new papers are found"""
    mock_get_existing.return_value = {"http://arxiv.org/abs/2601.0001"}
    mock_matches.return_value = True
    
    # Mock RSS returning same paper that already exists
    mock_requests.return_value.status_code = 200
    mock_feed = MagicMock()
    mock_feed.entries = [{
        'title': 'Test Paper',
        'summary': 'Test Abstract',
        'link': 'http://arxiv.org/abs/2601.0001',
        'published_parsed': None
    }]
    mock_feedparser.return_value = mock_feed
    
    main("channel", "query", 5, 1)
    
    # Assert Slack was NOT called (no new papers)
    mock_slack.chat_postMessage.assert_not_called()

@patch("main.requests.get")
@patch("main.feedparser.parse")
@patch("main.matches_query")
@patch("main.slack_client")
@patch("main.generate_paper_summary")
@patch("main.save_to_sheets")
@patch("main.get_existing_paper_ids")
def test_main_slack_error_handling(mock_get_existing, mock_save, mock_gen, mock_slack, mock_matches, mock_feedparser, mock_requests, mock_env):
    """Test scenario where Slack posting fails"""
    from slack_sdk.errors import SlackApiError
    
    mock_get_existing.return_value = set()
    mock_matches.return_value = True
    
    mock_requests.return_value.status_code = 200
    mock_feed = MagicMock()
    mock_feed.entries = [{
        'title': 'Test Paper',
        'summary': 'Test Abstract',
        'link': 'http://arxiv.org/abs/2601.0002',
        'published_parsed': None
    }]
    mock_feedparser.return_value = mock_feed
    
    mock_gen.return_value = {}
    
    # Mock Slack raising error
    mock_response = {"ok": False, "error": "rate_limited"}
    mock_slack.chat_postMessage.side_effect = SlackApiError("Rate limit", mock_response)
    
    # Should not crash
    main("channel", "query", 5, 1)
    
    # Verify we attempted to post
    mock_slack.chat_postMessage.assert_called()
    
    # If slack fails, save_to_sheets might or might not be called based on error handling.
    # Currently, it falls into except block before save_to_sheets.
    mock_save.assert_not_called()
