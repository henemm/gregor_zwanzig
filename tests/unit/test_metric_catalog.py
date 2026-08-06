"""TDD RED — Fix #923b AC-4: temperature_night bekommt einen sms_code.

SPEC: docs/specs/modules/fix_923b_wire_live_sms_preview.md (AC-4)

RED-Grund heute: ``temperature_night`` traegt in der Registry noch keinen
``sms_code`` (Default ``""``), obwohl ``SMS_MULTI_SYMBOLS_BY_METRIC``
(``src/output/renderers/sms_trip.py``) fuer diese Metrik bereits das Symbol
"N" fuehrt -- die Metrik erscheint deshalb schon heute in ``carried_ids`` der
SMS-Fidelity-Vorschau, obwohl der Katalog keinen Token zeigt.

Mock-frei: reine Katalog-Auswertung auf der echten ``_METRICS``-Registry,
kein Netz, keine Persistenz.
"""
from __future__ import annotations


def test_ac4_temperature_night_hat_sms_code_tn():
    """AC-4 GIVEN der Katalog-Eintrag ``temperature_night``
    WHEN ``get_sms_code("temperature_night")`` aufgerufen wird
    THEN liefert er ``"TN"`` (nicht-leer, deckt sich mit dem bereits
    vorhandenen ``compact_label="TN"`` derselben Metrik und mit dem in
    ``SMS_MULTI_SYMBOLS_BY_METRIC`` tatsaechlich verwendeten Symbol)."""
    from app.metric_catalog import get_sms_code

    assert get_sms_code("temperature_night") == "TN", (
        "temperature_night traegt noch keinen sms_code -- die Metrik "
        "erscheint dadurch mit leerem Token in der SMS-Fidelity-Vorschau, "
        "obwohl sie im Renderer bereits ein Symbol traegt."
    )


def test_ac4_temperature_cold_bleibt_unveraendert_n():
    """Known Limitation: ``temperature_cold`` (interne Alarm-Pseudogroesse)
    behaelt weiterhin ``sms_code="N"`` -- unveraendert durch diese Scheibe,
    trotz aehnlichem Kuerzel-Praefix-Muster wie ``temperature_night``."""
    from app.metric_catalog import get_sms_code

    assert get_sms_code("temperature_cold") == "N"
