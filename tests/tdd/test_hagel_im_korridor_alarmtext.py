"""TDD RED — Issue #2205, AC-5 / AC-6: Hagel im Korridor-Alarm (Schwellen-
Treffer "deine Grenze ... ist gerissen").

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Aufrufkette (keine Mocks, kein Netz, kein Versand):

    Stundenreihe (nur `wmo_code`) -> `_derive_thunder_fields` ->
    `compute_basis_metrics`
      -> services.corridor_threshold.evaluate_corridor_thresholds()
         (Grenze Gewitter max "mittel", aktives Etappenfenster)
      -> alert.project.to_alert_message(changes=[], corridor_hits=...)
         -> to_corridor_events()
      -> alert.render.render_email() / render_telegram()
         -> _corridor_line()  (render.py ~430-460)

Erwarteter Wortlaut: `metric_format.format_hail_note(True)` -- dieselbe
Aussage wie im Stufen-Aenderungsalarm (AC-1).

Kurzkanaele (Flaeche 1 gilt fuer alle vier Kanaele, auch beim Korridor-Alarm):
`render_sms()` -> `_sms_corridor_token()` (`!TH3`) bekommt bei 96/99 das
Suffix `tokens.builder.FORECAST_TH_HAIL_SUFFIX`. Premium-SMS ist ueber
denselben `sms_body` abgedeckt: `_dispatch_alert_message()` rendert ihn einmal
(notification_service.py:1587) und reicht dieselbe Variable an
`SMSOutput.send` (:1763) und `PremiumSmsOutput.send` (:1777).
"""
from __future__ import annotations

import pytest

from app.models import Corridor, ThunderLevel
from output.metric_format import format_hail_note, thunder_ordinal
from output.renderers.alert.project import to_alert_message
from output.tokens.builder import FORECAST_TH_HAIL_SUFFIX
from services.corridor_threshold import evaluate_corridor_thresholds
from tests.tdd.test_hagel_im_alarmtext import (
    ALERT_TZ,
    HAGEL_WORT,
    gerenderte_texte,
    segment_weather,
)


def korridor_alarm(spitzen_code: int):
    """Korridor-Grenze Gewitter max "mittel"; die Etappe erreicht "hoch" in
    der Spitzenstunde mit `spitzen_code` -> AlertMessage nur mit
    Korridor-Ereignis (echter Waechter + echte Projektion)."""
    punkt = segment_weather(spitzen_code)
    grenze = Corridor(
        metric="thunder_level",
        range=[None, float(thunder_ordinal(ThunderLevel.MED))],
        notify=True,
    )
    treffer = evaluate_corridor_thresholds([punkt], [grenze])
    assert len(treffer) == 1, f"Fixture-Fehler: genau ein Korridor-Treffer erwartet, {treffer!r}"
    msg = to_alert_message(
        [], [punkt], "Testtour", tz=ALERT_TZ, stand_at="10:00",
        corridor_hits=treffer,
    )
    assert len(msg.corridor_events) == 1 and not msg.events, (
        f"Fixture-Fehler: reine Korridor-Nachricht erwartet, {msg!r}"
    )
    return msg


def _assert_korridor_alarm_gerendert(kanal: str, text: str) -> None:
    """Anker gegen leeres Gruen: die Korridor-Zeile ist ueberhaupt da."""
    assert "Gewitter" in text and "gerissen" in text, (
        f"{kanal}: kein Gewitter-Korridor-Alarmtext gerendert:\n{text}"
    )


@pytest.mark.parametrize("kanal", ["email_html", "email_plain", "telegram"])
@pytest.mark.parametrize("spitzen_code", [96, 99])
def test_ac5_korridor_alarm_mit_hagelcode_nennt_hagel(
    spitzen_code: int, kanal: str,
) -> None:
    """AC-5.

    GIVEN ein Korridor-Alarm (Grenze Gewitter "mittel" gerissen) mit
          Spitzenstunde Wettercode 96 bzw. 99
    WHEN  der Korridor-Alarmtext fuer E-Mail (HTML + Plain) und Telegram
          gerendert wird
    THEN  enthaelt er dieselbe Hagelaussage wie der Stufen-Aenderungsalarm
          (`format_hail_note(True)`).
    """
    erwartet = format_hail_note(True)
    assert erwartet, "format_hail_note(True) muss einen Wortlaut liefern"

    text = gerenderte_texte(korridor_alarm(spitzen_code))[kanal]

    _assert_korridor_alarm_gerendert(kanal, text)
    assert erwartet in text, (
        f"{kanal}: Hagelaussage {erwartet!r} fehlt im Korridor-Alarm "
        f"(Spitzenstunde Code {spitzen_code}):\n{text}"
    )


@pytest.mark.parametrize("kanal", ["email_html", "email_plain", "telegram"])
def test_ac6_korridor_alarm_mit_code_95_nennt_keinen_hagel(kanal: str) -> None:
    """AC-6.

    GIVEN ein Korridor-Alarm mit ausschliesslich Wettercode 95 in der
          Spitzenstunde
    WHEN  der Korridor-Alarmtext gerendert wird
    THEN  fehlt die Hagelaussage -- bei gleichzeitig gerenderter
          Korridor-Zeile (kein leeres Gruen).
    """
    text = gerenderte_texte(korridor_alarm(95))[kanal]

    _assert_korridor_alarm_gerendert(kanal, text)
    assert HAGEL_WORT not in text, (
        f"{kanal}: Code 95 ist kein Hagel-Code, Korridor-Alarm behauptet Hagel:\n{text}"
    )


# Korridor-Token der Kurzform (`_sms_corridor_token`: `!{code}{wert}`), Stufe
# "hoch" = Ordinal 3. `@HH` fehlt auf diesem Pfad (`_peak_occurred_at()` findet
# fuer die Enum-Metrik `thunder_level` keinen Zeitpunkt).
KORRIDOR_TOKEN = f"!TH{thunder_ordinal(ThunderLevel.HIGH)}"


@pytest.mark.parametrize("spitzen_code", [96, 99])
def test_ac5_korridor_sms_body_traegt_hagel_suffix(spitzen_code: int) -> None:
    """AC-5 (Kurzkanaele SMS + Premium-SMS, gemeinsamer `sms_body`).

    GIVEN ein Korridor-Alarm (Grenze Gewitter "mittel" gerissen) mit
          Spitzenstunde Wettercode 96 bzw. 99
    WHEN  der Korridor-Alarm fuer SMS/Premium-SMS gerendert wird (`render_sms`)
    THEN  traegt das Korridor-Token `!TH3` das bestehende Suffix
          `FORECAST_TH_HAIL_SUFFIX` (`+HL`).
    """
    sms_body = gerenderte_texte(korridor_alarm(spitzen_code))["sms_body"]

    assert KORRIDOR_TOKEN in sms_body, (
        f"Anker: Korridor-Token {KORRIDOR_TOKEN!r} fehlt im sms_body: {sms_body!r}"
    )
    assert FORECAST_TH_HAIL_SUFFIX in sms_body, (
        f"Suffix {FORECAST_TH_HAIL_SUFFIX!r} fehlt im Korridor-sms_body "
        f"(SMS + Premium-SMS) bei Code {spitzen_code}: {sms_body!r}"
    )


def test_ac6_korridor_sms_body_ohne_hagel_suffix_bei_code_95() -> None:
    """AC-6 (Kurzkanaele SMS + Premium-SMS, gemeinsamer `sms_body`).

    GIVEN ein Korridor-Alarm mit ausschliesslich Wettercode 95 in der
          Spitzenstunde
    WHEN  der Korridor-Alarm fuer SMS/Premium-SMS gerendert wird (`render_sms`)
    THEN  fehlt das Suffix `+HL`, das Korridor-Token `!TH3` ist vorhanden
          (kein leeres Gruen).
    """
    sms_body = gerenderte_texte(korridor_alarm(95))["sms_body"]

    assert KORRIDOR_TOKEN in sms_body, (
        f"Korridor-Token {KORRIDOR_TOKEN!r} muss bei Code 95 vorhanden sein: {sms_body!r}"
    )
    assert FORECAST_TH_HAIL_SUFFIX not in sms_body, (
        f"Code 95 ist kein Hagel-Code, Korridor-sms_body traegt trotzdem "
        f"{FORECAST_TH_HAIL_SUFFIX!r}: {sms_body!r}"
    )
