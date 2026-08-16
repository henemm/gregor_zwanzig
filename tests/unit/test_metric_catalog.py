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


def test_ac4_temperature_night_sms_code_ist_jetzt_leer():
    """Fix #1887 E6 Scheibe A (docs/specs/modules/
    fix_1887_e6a_sms_kuerzel_register.md, AC-3): der historische #923b-Bug
    (leeres Token in der SMS-Fidelity-Vorschau) kann nicht wiederkehren --
    ``_symbols_for_metric()`` (validator_render_service.py) liest
    ``SMS_MULTI_SYMBOLS_BY_METRIC`` VOR ``sms_code``. Der tote Wert "TN"
    (erreicht keinen der beiden ``get_sms_code()``-Leser) ist entfernt;
    ``sms_code`` ist jetzt leer, das gesendete Kuerzel "N" traegt
    ausschliesslich ``sms_multi_symbols``."""
    from app.metric_catalog import SMS_MULTI_SYMBOLS_BY_METRIC, get_sms_code

    assert get_sms_code("temperature_night") == "", (
        "temperature_night traegt noch den toten sms_code 'TN' -- er "
        "erreicht keinen der beiden get_sms_code()-Leser (AC-3) und muss "
        "leer sein."
    )
    assert SMS_MULTI_SYMBOLS_BY_METRIC.get("temperature_night") == ("N",), (
        "Das tatsaechlich gesendete Kuerzel 'N' fuer temperature_night muss "
        "in SMS_MULTI_SYMBOLS_BY_METRIC stehen (Fidelity-Vorschau-Quelle), "
        f"gefunden: {SMS_MULTI_SYMBOLS_BY_METRIC.get('temperature_night')!r}"
    )


def test_ac4_temperature_cold_bleibt_unveraendert_n():
    """Known Limitation: ``temperature_cold`` (interne Alarm-Pseudogroesse)
    behaelt weiterhin ``sms_code="N"`` -- unveraendert durch diese Scheibe,
    trotz aehnlichem Kuerzel-Praefix-Muster wie ``temperature_night``."""
    from app.metric_catalog import get_sms_code

    assert get_sms_code("temperature_cold") == "N"
