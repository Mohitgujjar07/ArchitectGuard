from unittest.mock import MagicMock, patch
import pytest

from core.models import Assumption, Decision
from core.notifications import NotificationService


@patch("urllib.request.urlopen")
def test_send_slack_alert(mock_urlopen):
    # Mock successful HTTP 200 response
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    a = Assumption(id="A1", statement="SMS pricing stays low", valid_until="2020-01-01")
    d = Decision(id="D1", title="SMS Auth", description="desc", risk_score=0.75)

    ok = NotificationService.send_slack_alert(
        webhook_url="https://hooks.slack.com/services/TEST/TOKEN",
        project_name="FinPay",
        expired_assumptions=[a],
        at_risk_decisions=[d],
        total_blast_radius=0.75,
    )
    assert ok is True
    assert mock_urlopen.called


@patch("urllib.request.urlopen")
def test_send_generic_webhook(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    a = Assumption(id="A1", statement="Premise 1")
    d = Decision(id="D1", title="Decision 1", description="desc", risk_score=0.4)

    ok = NotificationService.send_generic_webhook(
        webhook_url="https://example.com/webhook",
        project_name="Core System",
        expired_assumptions=[a],
        at_risk_decisions=[d],
        total_blast_radius=0.4,
    )
    assert ok is True
    assert mock_urlopen.called


def test_notification_empty_url_returns_false():
    assert NotificationService.send_slack_alert("", "Test", [], [], 0.0) is False
