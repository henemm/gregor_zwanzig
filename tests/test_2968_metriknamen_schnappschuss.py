"""TDD RED — Issue #2968, Workflow feat-2968-en-katalogtexte.

Spec: docs/specs/modules/feat_2968_elementliste_en_zuordnung.md — AC-7 (Regel d).

Drift-Test: Der Schnappschuss ``docs/context/einstellungen_neu/daten/metriknamen.json`` entspricht dem
echten Metrik-Katalog ``src/app/metric_catalog.py`` (``_METRICS``, in Katalog-Reihenfolge). Der
Elementlisten-Generator (TypeScript) liest den Schnappschuss, statt zur Laufzeit Python aufzurufen;
dieser Test hält beide gleich.

Format des Schnappschusses (vom Developer anzulegen)::

    {
      "quelle": "src/app/metric_catalog.py",
      "metriken": [
        {
          "id": "temperature",
          "label_de": "Temperatur",          # voller DE-Metrikname (Regel a/d: aufgelöster Wert)
          "alert_label": "Temp",             # Alarm-Kurzform DE ("" wenn leer)
          "compact_label": "T",              # Kurz-Token (Regel c.3)
          "col_label": "Temp",               # Spaltenkürzel, z. B. "SnowL" (Regel c.3)
          "sms_code": "T",                   # SMS-Token ("" wenn leer)
          "sms_multi_symbols": [],           # Trip-Kurzform-Kürzel, z. B. ["N"]
          "kuerzel": ["T"]                   # sortierte Schlüssel von kuerzel_bedeutung_de
        },
        ...
      ]
    }

Geprüft wird gegen den echten Katalog (kein Mock); die Gegenprobe verfälscht nur eine Kopie im Speicher.

    uv run pytest tests/test_2968_metriknamen_schnappschuss.py -v
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from app.metric_catalog import _METRICS

REPO = Path(__file__).resolve().parent.parent
SCHNAPPSCHUSS = REPO / "docs" / "context" / "einstellungen_neu" / "daten" / "metriknamen.json"

FELDER = ("id", "label_de", "alert_label", "compact_label", "col_label", "sms_code", "sms_multi_symbols", "kuerzel")


def erwartet() -> dict:
    """Schnappschuss, wie er aus dem echten Katalog entstehen muss."""
    return {
        "quelle": "src/app/metric_catalog.py",
        "metriken": [
            {
                "id": m.id,
                "label_de": m.label_de,
                "alert_label": m.alert_label,
                "compact_label": m.compact_label,
                "col_label": m.col_label,
                "sms_code": m.sms_code,
                "sms_multi_symbols": list(m.sms_multi_symbols),
                "kuerzel": sorted(m.kuerzel_bedeutung_de),
            }
            for m in _METRICS
        ],
    }


def abweichungen(ist: dict, soll: dict) -> list[str]:
    """Liste der Unterschiede je Metrik und Feld (leer = gleich)."""
    out: list[str] = []
    if ist.get("quelle") != soll["quelle"]:
        out.append(f"quelle: {ist.get('quelle')!r} != {soll['quelle']!r}")
    ist_m = ist.get("metriken")
    if not isinstance(ist_m, list):
        return out + ["Feld 'metriken' fehlt oder ist keine Liste"]
    ist_ids = [m.get("id") for m in ist_m]
    soll_ids = [m["id"] for m in soll["metriken"]]
    if ist_ids != soll_ids:
        out.append(f"ids/Reihenfolge: {ist_ids} != {soll_ids}")
        return out
    for a, b in zip(ist_m, soll["metriken"]):
        if set(a) != set(FELDER):
            out.append(f"{b['id']}: Felder {sorted(a)} != {sorted(FELDER)}")
        for f in FELDER:
            if a.get(f) != b[f]:
                out.append(f"{b['id']}.{f}: {a.get(f)!r} != {b[f]!r}")
    return out


def lade() -> dict:
    assert SCHNAPPSCHUSS.exists(), f"Schnappschuss fehlt: {SCHNAPPSCHUSS.relative_to(REPO)}"
    return json.loads(SCHNAPPSCHUSS.read_text(encoding="utf-8"))


def test_schnappschuss_entspricht_dem_metrik_katalog():
    unterschiede = abweichungen(lade(), erwartet())
    assert unterschiede == [], "metriknamen.json weicht vom Katalog ab:\n" + "\n".join(unterschiede)


def test_schnappschuss_enthaelt_die_namen_der_spec_beispiele():
    namen = {m["label_de"] for m in lade()["metriken"]}
    token = {t for m in lade()["metriken"] for t in [m["col_label"], m["sms_code"], *m["sms_multi_symbols"], *m["kuerzel"]] if t}
    assert {"Regenwahrscheinlichkeit", "Böen", "Bewölkung", "UV-Index"} <= namen
    assert {"N", "SnowL", "VS"} <= token


def test_veraenderter_katalogeintrag_wird_erkannt():
    """Gegenprobe: eine Änderung am Katalog ohne Schnappschuss-Update macht den Vergleich rot."""
    ist = lade()
    soll = erwartet()
    assert abweichungen(ist, soll) == []
    verfaelscht = copy.deepcopy(soll)
    verfaelscht["metriken"][0]["label_de"] += " (neu)"
    assert any("label_de" in u for u in abweichungen(ist, verfaelscht))
    entfernt = copy.deepcopy(soll)
    entfernt["metriken"].pop()
    assert abweichungen(ist, entfernt) != []
