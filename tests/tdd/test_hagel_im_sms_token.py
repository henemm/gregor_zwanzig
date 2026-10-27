"""TDD RED — Issue #2205, AC-3 / AC-4: Hagel-Suffix `+HL` im `sms_body` des
Stufen-Aenderungsalarms (SMS + Premium-SMS).

SPEC: docs/specs/modules/fix_2205_hagel_im_text_wettercode_bleibt.md

Es gibt KEINEN eigenen Premium-SMS-Alarm-Renderer: `_dispatch_alert_message()`
rendert `sms_body = render_alert_sms(alert_msg)` genau einmal
(notification_service.py:1587) und reicht DIESELBE Variable an
`SMSOutput.send(body=sms_body)` (:1763) und `PremiumSmsOutput.send(body=sms_body)`
(:1777); `SevenIoChannelBase.send` legt `body` unveraendert in die Nutzlast.
Der gemeinsame Pruefpunkt fuer beide Kanaele ist deshalb `render_sms()` --
ohne Transport (kein Netz, keine Mocks).

Aufrufkette: siehe `test_hagel_im_alarmtext.py` (Stundenreihe ->
`_derive_thunder_fields` -> `compute_basis_metrics` -> `detect_changes` ->
`to_alert_message` -> `render_sms`). Der erwartete Suffix kommt aus der
einzigen Wortlautquelle `tokens.builder.FORECAST_TH_HAIL_SUFFIX`.
"""
from __future__ import annotations

import pytest

from output.tokens.builder import FORECAST_TH_HAIL_SUFFIX
from tests.tdd.test_hagel_im_alarmtext import (
    gerenderte_texte,
    stufen_aenderungsalarm,
)

# Stufentoken der Trip-Kurzform (Issue #1948 S3). `@HH` fehlt auf diesem Pfad,
# weil `_peak_occurred_at()` fuer die Enum-Metrik `thunder_level` keinen
# Zeitpunkt findet (float(ThunderLevel) wirft) -- geprueft wird deshalb der
# Stufenteil, der unveraendert bleiben muss.
STUFENTOKEN = "TH:M->H"


@pytest.mark.parametrize("spitzen_code", [96, 99])
def test_ac3_sms_body_traegt_hagel_suffix_bei_hagelcode(spitzen_code: int) -> None:
    """AC-3.

    GIVEN eine Stufenaenderung mittel -> hoch mit Wettercode 96 bzw. 99 in
          der Spitzenstunde
    WHEN  der Stufen-Aenderungsalarm fuer SMS und Premium-SMS gerendert wird
          (gemeinsamer `sms_body` aus `render_sms`)
    THEN  traegt der `sms_body` das bestehende Suffix `+HL`, und das
          Stufentoken `TH:M->H` bleibt erhalten.
    """
    sms_body = gerenderte_texte(stufen_aenderungsalarm(spitzen_code))["sms_body"]

    assert STUFENTOKEN in sms_body, (
        f"Anker: Stufentoken {STUFENTOKEN!r} fehlt im sms_body: {sms_body!r}"
    )
    assert FORECAST_TH_HAIL_SUFFIX in sms_body, (
        f"Suffix {FORECAST_TH_HAIL_SUFFIX!r} fehlt im gemeinsamen sms_body "
        f"(SMS + Premium-SMS) bei Code {spitzen_code}: {sms_body!r}"
    )


def test_ac4_sms_body_ohne_hagel_suffix_bei_code_95() -> None:
    """AC-4.

    GIVEN eine Stufenaenderung mittel -> hoch mit ausschliesslich Wettercode
          95 in der Spitzenstunde
    WHEN  SMS und Premium-SMS gerendert werden (gemeinsamer `sms_body`)
    THEN  fehlt das Suffix `+HL`, die Stufenangabe `TH:M->H` bleibt
          unveraendert erhalten.
    """
    sms_body = gerenderte_texte(stufen_aenderungsalarm(95))["sms_body"]

    assert STUFENTOKEN in sms_body, (
        f"Stufentoken {STUFENTOKEN!r} muss bei Code 95 erhalten bleiben: {sms_body!r}"
    )
    assert FORECAST_TH_HAIL_SUFFIX not in sms_body, (
        f"Code 95 ist kein Hagel-Code, sms_body traegt trotzdem "
        f"{FORECAST_TH_HAIL_SUFFIX!r}: {sms_body!r}"
    )
