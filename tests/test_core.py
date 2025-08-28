import pytest
from src.app import core

def test_send_mail_missing_env(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    with pytest.raises(ValueError):
        core.send_mail("Subject", "Body")
