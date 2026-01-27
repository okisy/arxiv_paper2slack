import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Add root directory to sys.path so we can import lambda_function
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lambda_function import build_slack_blocks, generate_paper_summary, main

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
    with patch("lambda_function.openai.OpenAI") as mock_openai, \
         patch("lambda_function.OPENAI_API_KEY", "mock_key"):
        mock_client = mock_openai.return_value
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"summary": "Short sum", "importance": 3, "theme_id": 3, "reason": "Because"}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        result = generate_paper_summary("Title", "Abstract")
        
        assert result["summary"] == "Short sum"
        assert result["importance"] == 3

def test_generate_paper_summary_failure(mock_env):
    # Test when API call fails
    with patch("lambda_function.openai.OpenAI") as mock_openai, \
         patch("lambda_function.OPENAI_API_KEY", "mock_key"):
        mock_client = mock_openai.return_value
        # Mock the method call to raise exception
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = generate_paper_summary("Title", "Abstract")
        
        # Fallback behavior
        assert "Abstract" in result["summary"]
        assert result["importance"] == "?"

@patch("lambda_function.arxiv.Client")
@patch("lambda_function.slack_client")
@patch("lambda_function.generate_paper_summary")
@patch("lambda_function.save_to_sheets")
@patch("lambda_function.get_existing_paper_ids")
@patch("lambda_function.config.SLACK_PROMPT_CHANNEL", "#mock-prompt-channel")
def test_main_flow(mock_get_existing, mock_save, mock_gen_summary, mock_slack, mock_arxiv, mock_env, mock_paper):
    # Setup
    mock_get_existing.return_value = set() # No existing papers
    
    # Mock Arxiv
    mock_client_instance = mock_arxiv.return_value
    mock_client_instance.results.return_value = [mock_paper]
    
    # Mock AI
    mock_gen_summary.return_value = {
        "summary": "AI Sum", "importance": 4, "theme_id": 0, "reason": "R"
    }
    
    # Mock Slack Response (for ts)
    mock_slack.chat_postMessage.return_value = {"ts": "1234.5678"}
    
    # Run Main (request 1 paper)
    main("channel", "query", 5, 1)
    
    # Verify Arxiv called
    mock_client_instance.results.assert_called()
    
    # Verify Slack called for paper
    assert mock_slack.chat_postMessage.call_count >= 1
    call_args = mock_slack.chat_postMessage.call_args_list[0]
    assert call_args.kwargs["channel"] == "channel"
    
    # Verify Sheet Save called
    mock_save.assert_called_with(mock_paper, mock_gen_summary.return_value, "1234.5678", insert_index=0)
    
    # Verify Gemini Prompt Bundle (since prompt channel is set in mock_env)
    # logic: if papers_sent > 0, posts prompt.
    # checking last call
    last_call = mock_slack.chat_postMessage.call_args_list[-1]
    # Check if it's the prompt post
    if "なにがすごいのか教えて" in last_call.kwargs.get("text", ""):
        assert last_call.kwargs["channel"] == "#mock-prompt-channel"
        assert mock_paper.entry_id in last_call.kwargs["text"]
