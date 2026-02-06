import os
import sys
import json
import pytest
from unittest.mock import patch

# Dynamically import the listener lambda to avoid name collision with root lambda_function
import importlib.util

LISTENER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
LISTENER_PATH = os.path.join(LISTENER_DIR, "main.py")

spec = importlib.util.spec_from_file_location("listener_lambda", LISTENER_PATH)
listener_lambda = importlib.util.module_from_spec(spec)
sys.modules["listener_lambda"] = listener_lambda
spec.loader.exec_module(listener_lambda)

@pytest.fixture
def mock_env(monkeypatch):
    monkeypatch.setattr(listener_lambda, "SLACK_SIGNING_SECRET", "mock_secret")
    monkeypatch.setattr(listener_lambda, "SPREADSHEET_ID", "mock_sheet_id")
    monkeypatch.setattr(listener_lambda, "GOOGLE_CREDS", "{}")

def test_verify_slack_signature_success(mock_env):
    headers = {
        "x-slack-request-timestamp": "1234567890",
        "x-slack-signature": "v0=correct_signature"
    }
    body = "body"
    
    with patch("slack_sdk.signature.SignatureVerifier.is_valid", return_value=True):
        assert listener_lambda.verify_slack_signature(headers, body) is True

def test_verify_slack_signature_failure(mock_env):
    headers = {
        "x-slack-request-timestamp": "1234567890",
        "x-slack-signature": "v0=wrong_signature"
    }
    body = "body"
    
    with patch("slack_sdk.signature.SignatureVerifier.is_valid", return_value=False):
        assert listener_lambda.verify_slack_signature(headers, body) is False

def test_verify_slack_signature_missing_headers(mock_env):
    headers = {}
    body = "body"
    assert listener_lambda.verify_slack_signature(headers, body) is False

def test_lambda_handler_url_verification():
    event = {
        "body": json.dumps({
            "type": "url_verification",
            "challenge": "challenge_token"
        }),
        "headers": {}
    }
    
    # Mock signature verification to always pass
    with patch("listener_lambda.verify_slack_signature", return_value=True):
        response = listener_lambda.lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        assert response["body"] == "challenge_token"

@patch("listener_lambda.update_reaction_in_sheets")
def test_lambda_handler_reaction_added(mock_update, mock_env):
    event = {
        "body": json.dumps({
            "event": {
                "type": "reaction_added",
                "reaction": "thumbsup",
                "item": {
                    "type": "message",
                    "channel": "C123",
                    "ts": "1234.5678"
                }
            }
        }),
        "headers": {}
    }
    
    with patch("listener_lambda.verify_slack_signature", return_value=True):
        response = listener_lambda.lambda_handler(event, None)
        
        assert response["statusCode"] == 200
        mock_update.assert_called_once()
        args = mock_update.call_args[0]
        assert args[0] == "1234.5678"

@patch("listener_lambda.build")
@patch("listener_lambda.service_account.Credentials.from_service_account_info")
def test_update_reaction_in_sheets_deduplication(mock_creds, mock_build, mock_env):
    """Test that existing reaction is NOT duplicated"""
    mock_service = mock_build.return_value
    mock_sheets = mock_service.spreadsheets.return_value
    
    # 1. Search for TS -> Found at row 1
    # 2. Get current reactions -> "Existing"
    mock_sheets.values.return_value.get.return_value.execute.side_effect = [
        {'values': [['1234.5678']]}, 
        {'values': [['Existing']]}
    ]

    # Act: Add "Existing" again
    result = listener_lambda.update_reaction_in_sheets("1234.5678", "Existing")
    
    # Assert: Should return True (success) but NOT call update
    assert result is True
    mock_sheets.values.return_value.update.assert_not_called()

@patch("listener_lambda.build")
@patch("listener_lambda.service_account.Credentials.from_service_account_info")
def test_update_reaction_in_sheets_append_new(mock_creds, mock_build, mock_env):
    """Test that NEW reaction is appended"""
    mock_service = mock_build.return_value
    mock_sheets = mock_service.spreadsheets.return_value
    
    # 1. Search for TS -> Found at row 1
    # 2. Get current reactions -> "Existing"
    mock_sheets.values.return_value.get.return_value.execute.side_effect = [
        {'values': [['1234.5678']]}, 
        {'values': [['Existing']]}
    ]

    # Act: Add "New"
    result = listener_lambda.update_reaction_in_sheets("1234.5678", "New")
    
    # Assert
    assert result is True
    mock_sheets.values.return_value.update.assert_called_once()
    
    # Check arguments
    call_args = mock_sheets.values.return_value.update.call_args[1]
    assert call_args['body']['values'] == [['Existing, New']]
