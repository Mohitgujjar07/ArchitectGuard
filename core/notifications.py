import json
import urllib.error
import urllib.request
from typing import List, Optional

from core.logger import get_logger
from core.models import Assumption, Decision

logger = get_logger("notifications")


class NotificationService:
    """Sends webhook and Slack alerts when architectural risks exceed thresholds."""

    @staticmethod
    def send_slack_alert(
        webhook_url: str,
        project_name: str,
        expired_assumptions: List[Assumption],
        at_risk_decisions: List[Decision],
        total_blast_radius: float,
    ) -> bool:
        """Send formatted Slack message with alert blocks via incoming webhook."""
        if not webhook_url:
            logger.warning("No Slack webhook URL configured.")
            return False

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚠️ AssumptionPulse Alert: {project_name}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*System Blast Radius:*\n`{total_blast_radius:.3f}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*At-Risk Decisions:*\n`{len(at_risk_decisions)}`",
                    },
                ],
            },
        ]

        if expired_assumptions:
            expired_text = "\n".join(
                [f"• *{a.id}* (Expired: {a.valid_until}): {a.statement}" for a in expired_assumptions[:5]]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🚨 Expired Assumptions:*\n{expired_text}",
                    },
                }
            )

        if at_risk_decisions:
            risk_text = "\n".join(
                [f"• *{d.id}* `{d.title}` — Risk: `{d.risk_score:.3f}`" for d in at_risk_decisions[:5]]
            )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🔥 Decisions At Risk:*\n{risk_text}",
                    },
                }
            )

        payload = {"text": f"AssumptionPulse: Architectural risk detected in {project_name}", "blocks": blocks}

        return NotificationService._post_json(webhook_url, payload)

    @staticmethod
    def send_generic_webhook(
        webhook_url: str,
        project_name: str,
        expired_assumptions: List[Assumption],
        at_risk_decisions: List[Decision],
        total_blast_radius: float,
    ) -> bool:
        """Post a generic JSON payload to any webhook URL."""
        payload = {
            "project_name": project_name,
            "total_blast_radius": total_blast_radius,
            "expired_assumptions": [
                {"id": a.id, "statement": a.statement, "valid_until": str(a.valid_until)}
                for a in expired_assumptions
            ],
            "at_risk_decisions": [
                {"id": d.id, "title": d.title, "risk_score": d.risk_score}
                for d in at_risk_decisions
            ],
        }
        return NotificationService._post_json(webhook_url, payload)

    @staticmethod
    def _post_json(url: str, data: dict) -> bool:
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                success = 200 <= resp.status < 300
                if success:
                    logger.info("Successfully dispatched webhook notification.")
                else:
                    logger.warning(f"Webhook returned status {resp.status}")
                return success
        except urllib.error.URLError as e:
            logger.error(f"Failed to deliver webhook notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending webhook: {e}")
            return False
