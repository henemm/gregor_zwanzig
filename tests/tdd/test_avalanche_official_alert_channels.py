"""Lawinenwarnung (MeteoAlarm Typ 9) durch alle Kanaele (Issue #1430, Epic #2258).

SPEC: docs/specs/modules/fix_1430_meteoalarm_lawine.md — AC-5, AC-6, AC-7, AC-9

Quelle ist die aufgezeichnete CAP-Datei `cap_avalanche_plus_heat.xml` durch die
echte Eingangsfunktion; alle Renderer sind die echten, geteilten Funktionen.
Kein Mock, kein Netz.
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

from services.official_alerts.models import OfficialAlert
from tests.tdd.test_sms_official_alert_tokens import _notice, _sms

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "meteoalarm" / "cap_avalanche_plus_heat.xml"
_TZ = ZoneInfo("UTC")
_PREMIUM_MAX_CHARS = 153  # output/renderers/channel_layout.py "premium_sms"


def _lawine() -> OfficialAlert:
    from services.official_alerts.meteoalarm import _extract_alerts_from_cap

    alerts = _extract_alerts_from_cap(_FIXTURE.read_text(encoding="utf-8"))
    lawinen = [a for a in alerts if a.hazard == "avalanche"]
    assert lawinen, "Mapper liefert aus der aufgezeichneten Typ-9-Datei keine Lawinenwarnung"
    return lawinen[0]


def test_ac5_standalone_sms_traegt_aw_und_stufe_im_budget():
    from output.renderers.alert.official_alerts import render_official_alert_sms

    sms = render_official_alert_sms([_notice(_lawine())], tz=_TZ)
    assert "AW" in sms and ":M" in sms, f"Kuerzel/Stufe fehlen: {sms!r}"
    assert len(sms) <= 140, f"Standalone-SMS ueber Budget: {len(sms)} Zeichen"


def test_ac5_premium_sms_budget_traegt_aw_und_stufe():
    from output.renderers.alert.official_alerts import render_official_alert_sms

    text = render_official_alert_sms([_notice(_lawine())], limit=_PREMIUM_MAX_CHARS, tz=_TZ)
    assert "AW" in text and ":M" in text, f"Kuerzel/Stufe fehlen: {text!r}"
    assert len(text) <= _PREMIUM_MAX_CHARS, f"Premium-SMS ueber Budget: {len(text)} Zeichen"


def test_ac5_trip_sms_und_standalone_sms_nutzen_dasselbe_kuerzel():
    from output.renderers.alert.official_alerts import render_official_alert_sms

    alert = _lawine()
    trip = _sms([alert])
    standalone = render_official_alert_sms([_notice(alert)], tz=_TZ)
    assert "AW" in trip and "AW" in standalone, f"{trip!r} / {standalone!r}"
    assert "AV" not in standalone, f"Lawinen-Stufen-Token AV in der Warn-SMS: {standalone!r}"


def test_ac6_telegram_alarm_nennt_lawine_mit_stufe_statt_rohtext():
    from output.renderers.alert.official_alerts import render_official_alert_telegram

    text = render_official_alert_telegram(
        [_notice(_lawine())], prefix="Etappe 5", source_label="MeteoAlarm", tz=_TZ,
    )
    assert "Lawine" in text, f"Bezeichnung fehlt: {text!r}"
    assert "ORANGE" in text, f"Stufe fehlt: {text!r}"
    assert "9; avalanche" not in text and "AW" not in text, f"Rohtext/Kuerzel: {text!r}"


def test_ac7_trip_mail_warnkasten_nennt_lawine():
    from output.renderers.alert.official_alerts import render_warn_block

    html = render_warn_block(
        [_notice(_lawine())], variant="embedded", source_label="MeteoAlarm",
    )
    assert "Lawine" in html, f"Warn-Kasten ohne Bezeichnung: {html[:400]!r}"


def test_ac7_ortsvergleich_chip_zeigt_lawine_nicht_rohtext():
    from output.renderers.email.compare_html import _warn_short

    alert = _lawine()
    text, severity = _warn_short(alert)
    assert text == "Lawine" and text != alert.label
    assert severity == "warn"  # Stufe 3


def test_ac9_nur_der_nutzer_mit_lawinenwarnung_bekommt_aw():
    sms_a = _sms([_lawine()])
    sms_b = _sms([])
    assert "AW" in sms_a, f"Nutzer A: {sms_a!r}"
    assert "AW" not in sms_b and "!" not in sms_b, f"Nutzer B bekam fremde Warnung: {sms_b!r}"
