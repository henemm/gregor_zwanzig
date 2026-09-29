"""TDD RED — Issue #2422 Scheibe S4 / Issue #1088: SMS-Paritäts-Korrektur bei
gebündelten Abweichungsalarmen mit eingebettetem amtlichem Zusatzblock.

SPEC: docs/specs/modules/fix_2422_s4_alarm_familie_kette.md (AC-7).

BUG-FALL: `_dispatch_alert_message` hängt den amtlichen Zusatzblock an
HTML/Plain/Telegram an (`notification_service.py:1758-1760` bzw. die
Plain/Telegram-Zeilen direkt danach), lässt `sms_body` aber unverändert
(`notification_service.py:1706-1708`, dokumentierte Nicht-Parität #1088).
Epic #2133 (PO-Korrektur 2026-09-05): „jeder Kanal muss jede Frage
beantworten können" — ein sang- und klangloses Weglassen ist keine
akzeptable Abweichung mehr, mindestens ein kurzer Hinweistext ist Pflicht.

Kein Netz, kein `Mock()`: der Alarm läuft ECHT über
`tests/helpers/alarm_pruefstrecke.py` (#2050 S1), `official_notices` wird
`check_and_send_alerts()` direkt als Parameter übergeben (kein Provider-
Abruf nötig — dieselbe Naht, die die S4c-Tests (#2050) für den Δ-Zweig
bereits nutzen).
"""
from __future__ import annotations

from datetime import timedelta

from tests.tdd._alarm_amtlich_fixtures import amtliche_warnung
from tests.tdd.test_952_onset_alert_fidelity import _clean_user
from tests.tdd.test_alarm_abweichung_kette import _AT, _abweichungs_trip, _strecke, _uid, _wd

#: Fix-Erwartung für `/50` (hier gepinnt, damit Implementierung und Test
#: denselben Vertrag teilen) — ein kurzer, fester Hinweistext, der der SMS
#: angehängt wird, sobald `official_notices` gebündelt vorliegen.
_AMTL_HINWEIS_TOKEN = "+ amtl. Warnung s. E-Mail/Telegram"


def test_sms_enthaelt_hinweis_auf_amtliche_warnung_bei_gebuendeltem_alarm():
    """AC-7 (BUG-FALL — rot vor dem Fix, grün danach). GIVEN ein
    Abweichungsalarm, dessen gebündelte Mail einen eingebetteten amtlichen
    Zusatzblock trägt (`official_notices` an `check_and_send_alerts()`
    durchgereicht) / WHEN die zugehörige SMS gerendert und versendet wird /
    THEN enthält die SMS mindestens den Hinweistext
    `{_AMTL_HINWEIS_TOKEN!r}` auf die amtliche Warnung.

    RED heute: die SMS lässt den Zusatzblock komplett und ohne jeden Hinweis
    weg (`sms_body` bleibt in `_dispatch_alert_message` unverändert,
    notification_service.py:1706-1708) — der Hinweistext fehlt vollständig.

    Die SMS bleibt dabei innerhalb des produktiven Alarm-SMS-Limits von 140
    Zeichen (`output/renderers/alert/render.py::render_sms`, Default
    `limit=140` — NICHT 160, das ist das Limit eines anderen Renderers fürs
    Trip-Briefing, `output/renderers/sms_trip.py`).
    """
    uid = _uid("ac7")
    try:
        trip = _abweichungs_trip(uid, alert_channels={"sms": True, "email": True})
        strecke = _strecke(uid)
        alert = amtliche_warnung(3, von=_AT - timedelta(hours=1), bis=_AT + timedelta(hours=6))

        lauf = strecke.lauf(
            at=_AT, zweig="deviation", trip=trip,
            cached_weather=[_wd(1, precip_sum_mm=2.0)],
            fresh_weather=[_wd(1, precip_sum_mm=18.0)],
            official_notices=[(alert, ["1"])],
        )

        assert lauf.triggered_count == 1, "AC-7 Vorbedingung: der Alarm muss auslösen."
        assert len(lauf.sms) == 1, f"AC-7 Vorbedingung: SMS muss bedient werden: {lauf.sms!r}"
        assert lauf.mail, (
            "AC-7 Vorbedingung: die Mail muss den Alarm tragen (Grundlage "
            "für den Bündel-Nachweis)."
        )
        mail_body = lauf.mail[0][1]
        assert "Gewitterwarnung" in mail_body or "warn" in mail_body.lower(), (
            f"AC-7 Vorbedingung: die Mail muss den eingebetteten amtlichen "
            f"Zusatzblock tragen (sonst prüft der Test kein Bündel): "
            f"{mail_body!r}"
        )

        sms_text = lauf.sms[0]
        assert _AMTL_HINWEIS_TOKEN in sms_text, (
            f"AC-7: die SMS muss einen Hinweis auf die amtliche Warnung "
            f"tragen ({_AMTL_HINWEIS_TOKEN!r}) — vor dem Fix fehlt jeder "
            f"Hinweis: {sms_text!r}"
        )
        assert len(sms_text) <= 140, (
            f"AC-7: die SMS darf das 140-Zeichen-Limit des Alarm-SMS-"
            f"Renderers auch mit Hinweis nicht überschreiten (war "
            f"{len(sms_text)} Zeichen): {sms_text!r}"
        )
    finally:
        _clean_user(uid)
