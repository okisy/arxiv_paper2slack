import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add current dir to path
sys.path.append("/Users/maeoki/work_dir/docomo/arxiv_paper2slack")

# Mock the environment inputs
os.environ["SLACK_API_TOKEN"] = "mock_token"
os.environ["SPREADSHEET_ID"] = "mock_sheet_id"
os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = "{}"
os.environ["OPENAI_API_KEY"] = "mock_key"

# Mock config
import config
config.SLACK_PROMPT_CHANNEL = "#mock-prompt-channel"

from lambda_function import main, build_slack_blocks

class TestEnhancements(unittest.TestCase):
    
    @patch('lambda_function.arxiv.Client')
    @patch('lambda_function.slack_client')
    @patch('lambda_function.generate_paper_summary')
    @patch('lambda_function.save_to_sheets')
    def test_main_prompt_bundle(self, mock_save, mock_gen_summary, mock_slack, mock_arxiv):
        # 1. Mock Arxiv Search Results
        mock_paper1 = MagicMock()
        mock_paper1.entry_id = "http://arxiv.org/abs/2601.0001"
        mock_paper1.title = "Paper 1"
        mock_paper1.summary = "Summary 1"
        mock_paper1.published.strftime.return_value = "2026-01-01"

        mock_paper2 = MagicMock()
        mock_paper2.entry_id = "http://arxiv.org/abs/2601.0002"
        mock_paper2.title = "Paper 2"
        mock_paper2.summary = "Summary 2"
        mock_paper2.published.strftime.return_value = "2026-01-01"

        mock_client_instance = mock_arxiv.return_value
        mock_client_instance.results.return_value = [mock_paper1, mock_paper2]

        # 2. Mock AI Summary
        mock_gen_summary.return_value = {
            "summary": "AI Summary",
            "importance": 5,
            "theme_id": 1,
            "reason": "Reason"
        }

        # 3. Run main
        # We run with NUM_PAPERS=2 to send both
        main(config.SLACK_CHANNEL, config.ARXIV_QUERY, 10, 2)
        
        # 4. Verify Slack Calls
        # Should have 2 calls for papers + 1 call for prompt
        print("\nSlack Call args:")
        for call in mock_slack.chat_postMessage.call_args_list:
            print(call.kwargs.get('text') or call.kwargs.get('blocks'))

        self.assertEqual(mock_slack.chat_postMessage.call_count, 3)
        
        # Verify Prompt Call (Last call)
        last_call = mock_slack.chat_postMessage.call_args_list[2]
        self.assertEqual(last_call.kwargs['channel'], "#mock-prompt-channel")
        self.assertIn("http://arxiv.org/abs/2601.0001", last_call.kwargs['text'])
        self.assertIn("http://arxiv.org/abs/2601.0002", last_call.kwargs['text'])
        self.assertIn("についてなにがすごいのか教えて", last_call.kwargs['text'])
        
    def test_timestamp_in_blocks(self):
        mock_paper = MagicMock()
        mock_paper.title = "Test Paper"
        mock_paper.published.strftime.return_value = "2026-01-01"
        ai_data = {"summary": "sum", "importance": 5, "theme_id": 1, "reason": "reason"}
        
        blocks, text = build_slack_blocks(mock_paper, ai_data, 1)
        
        # Verify last block is context and contains "Posted at:" and "JST"
        last_block = blocks[-1]
        self.assertEqual(last_block['type'], 'context')
        content = last_block['elements'][0]['text']
        self.assertIn("Posted at:", content)
        self.assertIn("(JST)", content)
        print(f"\nTimestamp block content: {content}")

if __name__ == '__main__':
    unittest.main()
