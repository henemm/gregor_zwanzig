"""TDD RED — #1720 Scheibe 1: Persistenz der Vorschau-Auswahl (AC-12).

SPEC: docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md
KONTEXT: docs/context/feat-1720-vorschau-metriken.md

Prueft den ECHTEN Python-Speicherweg (``loader.save_trip`` ->
``_trip_to_dict`` -> Datei -> ``loader.load_trip``) auf einem isolierten
Datenverzeichnis (``tmp_path``) -- kein Zugriff auf ``data/``.

Zwei Zusicherungen:

1. **AC-12 / RMW.** Wer nur die Vorschau-Auswahl aendert, verliert weder die
   Grundauswahl noch das kanal-eigene Layout (Fehlerklasse #102 -> #1159).
2. **Drei-Werte-Semantik.** ``fehlt`` (Altbestand) / ``[]`` (bewusst geleert) /
   ``gefuellt`` muessen den Roundtrip UNTERSCHEIDBAR ueberleben. Wird das Feld
   unbedingt geschrieben, bekaeme jeder Trip nach dem ersten Speichern ein
   explizites ``outlook_metrics`` -- und ``None`` (sieben feste Spalten) waere
   von ``[]`` (Block entfaellt) nicht mehr zu unterscheiden.

RED-Erwartung: ``UnifiedWeatherDisplayConfig`` kennt ``outlook_metrics``
nicht; Lese- und Schreibpfad des Loaders kennen es ebenfalls nicht.

Kern-Schicht, deterministisch. Kein Mock-Framework, kein Netz.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

VORSCHAU = [
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "gust", "aggregation": "max"},
]


def _trip(trip_id: str, dc):
    from app.trip import Stage, Trip, Waypoint

    heute = date.today()
    stages = [
        Stage(
            id=f"S{i}", name=f"Tag {i}", date=heute + timedelta(days=i),
            waypoints=[
                Waypoint(id=f"W{i}a", name="Start", lat=46.65, lon=12.85,
                         elevation_m=1400.0),
                Waypoint(id=f"W{i}b", name="Ziel", lat=46.70, lon=12.95,
                         elevation_m=2100.0),
            ],
        )
        for i in range(2)
    ]
    trip = Trip(id=trip_id, name="Karnischer Höhenweg", stages=stages)
    trip.display_config = dc
    return trip


def _display_config(trip_id: str, **kwargs):
    """Grundauswahl + kanal-eigenes Layout, wie ein echter Nutzer sie hat."""
    from app.metric_catalog import build_default_display_config
    from app.models import MetricConfig

    dc = build_default_display_config()
    dc.trip_id = trip_id
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in {"precipitation", "gust", "temperature"}
    dc.per_channel_layouts = {
        "telegram": [MetricConfig(metric_id="precipitation", enabled=True)],
    }
    if not kwargs:
        return dc
    import dataclasses

    try:
        return dataclasses.replace(dc, **kwargs)
    except TypeError as exc:
        raise AssertionError(
            "UnifiedWeatherDisplayConfig kennt das Feld 'outlook_metrics' "
            "noch nicht (#1720 Scheibe 1, Spec Source: src/app/models.py:"
            f"774-807).\nUrsprungsfehler: {exc}"
        ) from exc


def _speichern_und_laden(trip, tmp_path, user_id):
    from app.loader import load_trip, save_trip

    save_trip(trip, user_id=user_id, data_dir=tmp_path)
    geladen = load_trip(trip.id, data_dir=tmp_path, user_id=user_id)
    assert geladen is not None, "Der gespeicherte Trip liess sich nicht laden."
    return geladen


def _rohes_display_config(tmp_path, user_id, trip_id) -> dict:
    pfad = Path(tmp_path) / "users" / user_id / "briefings" / f"{trip_id}.json"
    return json.loads(pfad.read_text(encoding="utf-8")).get("display_config", {})


def test_ac12_nur_die_vorschau_zu_aendern_laesst_grundauswahl_und_kanal_layout_stehen(tmp_path):
    """AC-12.

    GIVEN ein Trip mit gesetzter Grundauswahl UND kanal-eigenem Layout.
    WHEN  anschliessend AUSSCHLIESSLICH die Vorschau-Auswahl geaendert und
          gespeichert wird.
    THEN  sind Grundauswahl und Kanal-Layout nach dem Neuladen unveraendert --
          kein Datenverlust durch einen Vollersatz-Schreibvorgang
          (Fehlerklasse #102 -> #1159).

    Mutations-Gegenprobe 5 (Speichern als Vollersatz statt feldweise).
    """
    user_id = f"tdd-1720-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    trip = _trip(trip_id, _display_config(trip_id))

    erst_geladen = _speichern_und_laden(trip, tmp_path, user_id)
    grundauswahl_vorher = sorted(
        mc.metric_id for mc in erst_geladen.display_config.metrics if mc.enabled
    )
    layout_vorher = {
        ch: [mc.metric_id for mc in metrics]
        for ch, metrics in (erst_geladen.display_config.per_channel_layouts or {}).items()
    }
    assert grundauswahl_vorher and layout_vorher, (
        "Vorbedingung: Grundauswahl und Kanal-Layout muessen den ersten "
        "Roundtrip ueberleben, sonst prueft der Test nichts."
    )

    # Nur die Vorschau-Auswahl aendern -- alles andere bleibt wie geladen.
    import dataclasses

    try:
        erst_geladen.display_config = dataclasses.replace(
            erst_geladen.display_config, outlook_metrics=VORSCHAU,
        )
    except TypeError as exc:
        raise AssertionError(
            "UnifiedWeatherDisplayConfig kennt 'outlook_metrics' noch nicht "
            f"(#1720 Scheibe 1).\nUrsprungsfehler: {exc}"
        ) from exc

    zweit_geladen = _speichern_und_laden(erst_geladen, tmp_path, user_id)
    dc = zweit_geladen.display_config

    assert getattr(dc, "outlook_metrics", None) == VORSCHAU, (
        "Die geaenderte Vorschau-Auswahl hat den Roundtrip nicht ueberlebt: "
        f"{getattr(dc, 'outlook_metrics', None)!r} (AC-12)"
    )
    assert sorted(mc.metric_id for mc in dc.metrics if mc.enabled) == grundauswahl_vorher, (
        "Die Grundauswahl hat sich geaendert, obwohl nur die Vorschau-Auswahl "
        "angefasst wurde -- Blind-Replace statt Read-Modify-Write (AC-12)."
    )
    assert {
        ch: [mc.metric_id for mc in metrics]
        for ch, metrics in (dc.per_channel_layouts or {}).items()
    } == layout_vorher, (
        "Das kanal-eigene Layout ist beim Speichern der Vorschau-Auswahl "
        "verloren gegangen (AC-12)."
    )


def test_altbestand_ohne_auswahl_bekommt_beim_speichern_kein_feld(tmp_path):
    """Drei-Werte-Semantik, Teil 1 (Spec Source, loader.py:1524-1544).

    GIVEN ein Trip, dessen Vorschau-Auswahl nie gesetzt wurde.
    WHEN  er gespeichert wird.
    THEN  steht ``outlook_metrics`` NICHT in der Datei -- sonst bekaeme jeder
          Trip nach dem ersten Speichern ein explizites Feld, ohne dass der
          Nutzer die neue Flaeche je beruehrt hat, und ``fehlt`` waere von
          ``bewusst geleert`` nicht mehr zu unterscheiden.
    """
    user_id = f"tdd-1720-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    trip = _trip(trip_id, _display_config(trip_id))

    _speichern_und_laden(trip, tmp_path, user_id)
    roh = _rohes_display_config(tmp_path, user_id, trip_id)

    assert "outlook_metrics" not in roh, (
        "Ein Trip ohne gesetzte Vorschau-Auswahl hat beim Speichern ein "
        f"explizites Feld bekommen: {roh.get('outlook_metrics')!r}. Der "
        "Eintrag muss bedingt geschrieben werden (Muster alert_preset/"
        "metric_alert_levels)."
    )


def test_bewusst_geleerte_auswahl_ueberlebt_den_roundtrip_als_leere_liste(tmp_path):
    """Drei-Werte-Semantik, Teil 2.

    GIVEN ein Trip mit bewusst geleerter Vorschau-Auswahl (``[]``).
    WHEN  er gespeichert und neu geladen wird.
    THEN  ist die Auswahl weiterhin ``[]`` -- NICHT ``None``. Andernfalls
          kaeme der Nutzer aus dem "Block aus"-Zustand nie wieder heraus bzw.
          nie hinein (AC-4 haengt daran).
    """
    user_id = f"tdd-1720-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    trip = _trip(trip_id, _display_config(trip_id, outlook_metrics=[]))

    geladen = _speichern_und_laden(trip, tmp_path, user_id)

    assert getattr(geladen.display_config, "outlook_metrics", "FEHLT") == [], (
        "Die bewusst geleerte Auswahl kam als "
        f"{getattr(geladen.display_config, 'outlook_metrics', 'FEHLT')!r} "
        "zurueck. Leer heisst leer -- nicht 'nie gesetzt'."
    )
    roh = _rohes_display_config(tmp_path, user_id, trip_id)
    assert roh.get("outlook_metrics") == [], (
        f"In der Datei steht {roh.get('outlook_metrics')!r} statt []."
    )


def test_gefuellte_auswahl_ueberlebt_den_roundtrip_in_reihenfolge(tmp_path):
    """Drei-Werte-Semantik, Teil 3 (Reihenfolge, AC-5).

    GIVEN eine gefuellte Vorschau-Auswahl in bewusst unsortierter Reihenfolge.
    WHEN  sie gespeichert und neu geladen wird.
    THEN  steht sie in exakt derselben Reihenfolge im Speicher UND in der
          Datei -- eine ``set``-basierte Zwischenstufe faellt hier auf.
    """
    user_id = f"tdd-1720-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    auswahl = [
        {"metric_id": "thunder", "aggregation": "max"},
        {"metric_id": "temperature", "aggregation": "max"},
        {"metric_id": "precipitation", "aggregation": "sum"},
    ]
    trip = _trip(trip_id, _display_config(trip_id, outlook_metrics=auswahl))

    geladen = _speichern_und_laden(trip, tmp_path, user_id)

    assert getattr(geladen.display_config, "outlook_metrics", None) == auswahl, (
        "Die gespeicherte Reihenfolge der Vorschau-Auswahl ging verloren: "
        f"{getattr(geladen.display_config, 'outlook_metrics', None)!r}"
    )
    assert _rohes_display_config(tmp_path, user_id, trip_id)["outlook_metrics"] == auswahl
