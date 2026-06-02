"""Slack webhook notifier for accepted-papers releases.

The monitor calls `notify_released` only on the first time a conference
flips from not-released to released — this module has no idempotency logic
of its own.
"""

import logging
from typing import Optional

import httpx

from backend.config import HTTP_TIMEOUT, SLACK_WEBHOOK_URL

log = logging.getLogger(__name__)


def _format_message(title: str, year: int, url: str) -> dict:
    text = f"*{title} {year}* accepted papers are now public\n<{url}>"
    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text,
                },
            }
        ],
    }


async def notify_released(
    title: str,
    year: int,
    url: str,
    client: Optional[httpx.AsyncClient] = None,
) -> bool:
    """Send a Slack notification. Returns True if the webhook accepted it."""
    if not SLACK_WEBHOOK_URL:
        log.warning("SLACK_WEBHOOK_URL is not configured; skipping notification")
        return False

    payload = _format_message(title, year, url)
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT)
    try:
        try:
            resp = await client.post(SLACK_WEBHOOK_URL, json=payload)
        except httpx.HTTPError as e:
            log.error("Slack webhook request failed: %s", e)
            return False
        if resp.status_code >= 300:
            log.error(
                "Slack webhook returned %s: %s", resp.status_code, resp.text[:200]
            )
            return False
        return True
    finally:
        if owns_client:
            await client.aclose()
