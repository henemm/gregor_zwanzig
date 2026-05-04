"""Inter-Instance Messaging (Claude MQ) helper.

Fail-soft helper for posting messages to the local claude-mq service.

Behaviour:
    * URL: env CLAUDE_MQ_URL, default http://127.0.0.1:3457/send
    * Auth: header X-MQ-Secret from env CLAUDE_MQ_SECRET
    * If CLAUDE_MQ_SECRET is unset → no POST is performed (silent return)
    * 5s timeout
    * Errors are logged as warnings, never raised

SPEC: docs/specs/bugfix/heartbeat_url_rotation.md
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_MQ_URL = "http://127.0.0.1:3457/send"


def send_mq(
    sender: str,
    recipient: str,
    priority: str,
    subject: str,
    body: str,
) -> None:
    """Send a message via the local claude-mq service.

    Fail-soft: returns silently if CLAUDE_MQ_SECRET is unset.
    Errors are logged as warnings, never raised.
    """
    secret = os.environ.get("CLAUDE_MQ_SECRET", "")
    if not secret:
        logger.debug("CLAUDE_MQ_SECRET not set, skipping MQ send (subject=%r)", subject)
        return

    url = os.environ.get("CLAUDE_MQ_URL", _DEFAULT_MQ_URL)
    try:
        resp = httpx.post(
            url,
            json={
                "sender": sender,
                "recipient": recipient,
                "priority": priority,
                "subject": subject,
                "body": body,
            },
            headers={
                "X-MQ-Secret": secret,
                "Content-Type": "application/json",
            },
            timeout=5.0,
        )
        if resp.status_code >= 400:
            logger.warning("MQ send HTTP %d (subject=%r)", resp.status_code, subject)
    except Exception as e:
        logger.warning("MQ send failed: %s", e)
