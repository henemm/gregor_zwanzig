"""Hagel-Hinweis im Aenderungs-Alarm (AlertEvent-Pfad), Issue #2205 / #2230.

Echte Kette: Segment mit Hagel-Signal im Aggregat -> `to_alert_message`
(`_hail_flag_for`) -> echte Renderer. Bewacht `_hail_note_suffix`,
`_sms_hail_suffix` und den Erzeuger `hail_flag=` in der Projektion. Kein Mock.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from app.models import ChangeSeverity, SegmentWeatherSummary, WeatherChange
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    render_email, render_sms, render_subject, render_telegram,
)
from tests.tdd.test_alert_ausgabe_nach_korridor_rueckbau import TZ, _segment

HAIL = "Hagel: ja"


def _msg(hail: bool | None):
    seg = _segment("1", 47.0, 11.0, 0.0, 6.0, 8, 12)
    seg = dataclasses.replace(
        seg, aggregated=SegmentWeatherSummary(hail_flag=hail),
    )
    ch = WeatherChange(
        metric="thunder_level_max", old_value=0.0, new_value=2.0, delta=2.0,
        threshold=1.0, severity=ChangeSeverity.MAJOR, direction="increase",
        segment_id="1", occurred_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    return to_alert_message([ch], [seg], "Hagel Trip", tz=TZ, stand_at="09:30")


def test_hagel_hinweis_in_allen_kanaelen_bei_bestaetigtem_hagel():
    msg = _msg(True)
    html, plain = render_email(msg)
    assert HAIL in plain
    assert HAIL in html
    assert HAIL in render_telegram(msg)
    assert "+HL" in render_sms(msg)


def test_kein_hagel_hinweis_ohne_hagel_signal():
    for hail in (None, False):
        msg = _msg(hail)
        html, plain = render_email(msg)
        for text in (render_subject(msg), plain, html, render_telegram(msg)):
            assert HAIL not in text
        assert "+HL" not in render_sms(msg)
