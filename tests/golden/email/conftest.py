"""Conftest for plain-text golden tests (β3 §A7).

Freezes datetime.now() so the 'Generated: YYYY-MM-DD HH:MM UTC' footer in
TripReportFormatter renders deterministically. Without this freeze the
goldens drift every minute.

Scope: only tests under tests/golden/email/.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

# Fixed clock used by both the golden-freeze script and the assertions.
_FROZEN_NOW = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # type: ignore[override]
        if tz is None:
            return _FROZEN_NOW.replace(tzinfo=None)
        return _FROZEN_NOW.astimezone(tz)


@pytest.fixture(autouse=True)
def _freeze_now(monkeypatch):
    """Freeze datetime.now() in trip_report adapter and channel renderers.

    Trip report sets `generated_at`; the email renderer module emits the
    'Generated: ...' plain-text footer and 'Generiert: ...' HTML footer.
    Both must use the same frozen clock for golden bit-equality.
    """
    import formatters.trip_report as tr_mod
    from src.output.renderers.email import plain as plain_mod
    from src.output.renderers.email import html as html_mod

    monkeypatch.setattr(tr_mod, "datetime", _FrozenDatetime)
    monkeypatch.setattr(plain_mod, "datetime", _FrozenDatetime)
    monkeypatch.setattr(html_mod, "datetime", _FrozenDatetime)
    yield
