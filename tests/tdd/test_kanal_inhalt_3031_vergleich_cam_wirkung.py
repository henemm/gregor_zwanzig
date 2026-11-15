"""#3031 Fix-Loop 1, Finding F001 -- Wirkung der Vergleichs-Nutzlast am Python-Leser.

SPEC: docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md (AC-7, AC-9).

Solange #3039 nicht live ist, liest der Vergleich die Kanal-Auswahl allein aus
``display_config.channel_active_metrics`` (``resolve_compare_render_options`` ->
``resolve_channel_enabled_metrics``). Die Fixture
``tests/fixtures/kanal_inhalt_3031/vergleich_kanal_nutzlast.json`` haelt die
Nutzlast fest, die der ECHTE TS-Speicherer (``vergleichNutzlast``) fuer einen
festen Karten-Stand erzeugt -- das verlangt
``kanal_inhalt_3031_speicherung.test.ts`` (Test „F001: Speicherer erzeugt die
Fixture-Nutzlast"). Hier geht dieselbe Nutzlast durch den echten Leser: jeder
Kanal muss nicht leer sein, die Kartenreihenfolge tragen und die Auswertung
(max/min/sum) behalten. Gegenprobe: dieselbe Auswahl als nackte Kennungen
(die Form vor dem Fix) loest der Leser zu ``[]`` auf.

Kein ``Mock()``/``patch()``/``MagicMock``.

    uv run pytest tests/tdd/test_kanal_inhalt_3031_vergleich_cam_wirkung.py
"""
from __future__ import annotations

import json
from pathlib import Path

from services.report_config_resolver import resolve_compare_render_options

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "kanal_inhalt_3031" / "vergleich_kanal_nutzlast.json"

ERWARTET = {
    "email": ["gust_max", "temp_max", "temp_min", "precip_sum"],
    "telegram": ["temp_max", "temp_min", "wind_max", "gust_max", "precip_sum"],
    # SMS fuehrte Temperatur nur als Maximum -- die Auswertung je Kanal bleibt.
    "sms": ["precip_sum", "temp_max"],
}


def _nutzlast() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["nutzlast_display_config"]


def _je_kanal(display_config: dict) -> dict:
    return resolve_compare_render_options({"id": "cp-3031", "display_config": display_config}).enabled_metrics_by_channel


def test_f001_nutzlast_des_speicherers_wirkt_je_kanal_in_reihenfolge_mit_auswertung():
    assert _je_kanal(_nutzlast()) == ERWARTET


def test_f001_gegenprobe_nackte_kennungen_wuerden_jeden_kanal_leeren():
    dc = _nutzlast()
    dc["channel_active_metrics"] = {
        k: list(dict.fromkeys(e["metric_id"] for e in v)) for k, v in dc["channel_active_metrics"].items()
    }
    assert _je_kanal(dc) == {"email": [], "telegram": [], "sms": []}
