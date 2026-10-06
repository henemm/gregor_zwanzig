"""#2231: beschaedigte briefing_slots.json — was die lock-freien Leser sagen.

Echter BriefingSlotStore in tmp_path, keine Mocks.
Spec: docs/specs/modules/fix_2231_slot_reparatur.md (AC-5, AC-8). Die
Dauersperre aus AC-5 von fail_closed_versand_defaults.md ist dort abgeloest;
Reparatur-Faelle stehen in tests/test_briefing_slot_reparatur.py.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import pytest

from services.briefing_slots import BriefingSlotStore

DAY = date(2026, 8, 20)
NOW = datetime(2026, 8, 20, 6, 0, tzinfo=timezone.utc)
BROKEN = ['{"entries": [', "[]", '"text"']


@pytest.mark.parametrize("content", BROKEN)
def test_corrupt_file_readers_say_done_and_leave_file_untouched(tmp_path, caplog, content):
    path = tmp_path / "briefing_slots.json"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    store = BriefingSlotStore("user-a", data_dir=tmp_path)

    with caplog.at_level(logging.ERROR, logger="briefing_slots"):
        assert store.is_recorded_or_claimed("t1", "morning", DAY, moment=NOW) is True
        assert store.is_recorded("t1", "morning", DAY) is True

    assert path.read_bytes() == before
    assert list(tmp_path.glob("briefing_slots.json.corrupt-*")) == []
    assert any(
        r.levelno == logging.ERROR and "briefing_slots.json" in r.getMessage()
        for r in caplog.records
    )


def test_missing_file_still_reserves(tmp_path):
    store = BriefingSlotStore("user-a", data_dir=tmp_path)
    assert store.is_recorded("t1", "morning", DAY) is False
    assert store.reserve("t1", "morning", DAY, moment=NOW) is True


def test_corruption_of_user_a_does_not_lock_user_b(tmp_path):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir()
    b_dir.mkdir()
    (a_dir / "briefing_slots.json").write_text('{"entries": [', encoding="utf-8")
    BriefingSlotStore("user-a", data_dir=a_dir)
    b = BriefingSlotStore("user-b", data_dir=b_dir)

    assert b.reserve("t1", "morning", DAY, moment=NOW) is True
    assert b.is_recorded("t1", "morning", DAY) is False
