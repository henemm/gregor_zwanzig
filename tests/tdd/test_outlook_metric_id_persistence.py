"""RED — #1848 A2: der 3-Tages-Ausblick speichert KENNUNGEN statt Paare.

SPEC: docs/specs/modules/feat_1848_a2_ausblick_kennungen.md — AC-1, AC-2,
      AC-7, AC-10
KONTEXT: docs/context/feat-1848-a2-outlook-kennungen.md (M5, R-A2-3, R-A2-4)

Geprueft wird der ECHTE Python-Speicherweg (``save_trip`` -> Datei ->
``load_trip``) auf einem isolierten Datenverzeichnis (``tmp_path``) und die
daraus aufgeloeste Auswahl (``resolve_trip_outlook_metrics``). Kein Zugriff
auf ``data/``, kein Netz, kein Mock-Framework.

🔴 Warum die Drei-Werte-Faelle (AC-7) jeweils MIT Gegenprobe stehen: 'nie
gewaehlt" und 'bewusst geleert' verhalten sich heute schon richtig. Der
Fehlerpfad, den A2 aufreisst, ist der dritte Zustand — eine GEFUELLTE Auswahl
im Kennungsformat kollabiert im heutigen Aufloeser zu ``[]`` (gemessen, M5)
und wird damit von 'bewusst geleert' ununterscheidbar. Nur die Gegenprobe
macht diese Ununterscheidbarkeit sichtbar; ein Test ohne sie waere trivial
gruen und bewachte nichts.

Kern-Schicht, deterministisch.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen -- sonst
# pruefte ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

# Was der Editor nach A2 liefert: reine Kennungen.
KENNUNGEN = ["precipitation", "gust"]

# Was der Editor VOR A2 lieferte und was in Bestandsdateien liegt.
PAARE = [
    {"metric_id": "precipitation", "aggregation": "sum"},
    {"metric_id": "gust", "aggregation": "max"},
]

# Bestands-Altform mit der einzigen mehrdeutigen Groesse: Tief UND Hoch.
ALTFORM_TEMPERATUR = [
    {"metric_id": "temperature", "aggregation": "min"},
    {"metric_id": "temperature", "aggregation": "max"},
    {"metric_id": "precipitation", "aggregation": "sum"},
]


def _kennungen(auswahl):
    """Kennungsfolge einer Auswahl — unabhaengig davon, ob ihre Eintraege
    Zeichenketten oder Paar-Objekte sind.

    Der Test schreibt die Traegerform der AUFGELOESTEN Liste bewusst nicht
    vor (das ist GREEN-Freiheit), nur ihren Inhalt: welche Groessen in
    welcher Reihenfolge, und wie oft.
    """
    if auswahl is None:
        return None
    return [e if isinstance(e, str)
            else (e.get("metric_id") if isinstance(e, dict) else e)
            for e in auswahl]


def _trip(trip_id: str, dc):
    from app.trip import Stage, Trip, Waypoint

    heute = date.today()
    stages = [
        Stage(id=f"S{i}", name=f"Tag {i}", date=heute + timedelta(days=i),
              waypoints=[
                  Waypoint(id=f"W{i}a", name="Start", lat=46.65, lon=12.85,
                           elevation_m=1400.0),
                  Waypoint(id=f"W{i}b", name="Ziel", lat=46.70, lon=12.95,
                           elevation_m=2100.0),
              ])
        for i in range(2)
    ]
    trip = Trip(id=trip_id, name="Karnischer Höhenweg", stages=stages)
    trip.display_config = dc
    return trip


def _display_config(trip_id: str, **kwargs):
    import dataclasses

    from app.metric_catalog import build_default_display_config

    dc = build_default_display_config()
    dc.trip_id = trip_id
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in {"precipitation", "gust", "temperature"}
    return dataclasses.replace(dc, **kwargs) if kwargs else dc


def _pfad(tmp_path, user_id, trip_id) -> Path:
    return Path(tmp_path) / "users" / user_id / "briefings" / f"{trip_id}.json"


def _rohes_display_config(tmp_path, user_id, trip_id) -> dict:
    return json.loads(
        _pfad(tmp_path, user_id, trip_id).read_text(encoding="utf-8")
    ).get("display_config", {})


def _speichern(trip, tmp_path, user_id):
    from app.loader import save_trip

    save_trip(trip, user_id=user_id, data_dir=tmp_path)


def _laden(trip_id, tmp_path, user_id):
    from app.loader import load_trip

    return load_trip(trip_id, data_dir=tmp_path, user_id=user_id)


def _gespeichert_und_geladen(auswahl, tmp_path, user_id=None, *, trip_id=None):
    """Ein Trip mit dieser Ausblick-Auswahl: speichern, wieder laden."""
    user_id = user_id or f"a2-{uuid.uuid4().hex[:8]}"
    trip_id = trip_id or f"trip-{uuid.uuid4().hex[:8]}"
    _speichern(_trip(trip_id, _display_config(trip_id, outlook_metrics=auswahl)),
               tmp_path, user_id)
    geladen = _laden(trip_id, tmp_path, user_id)
    assert geladen is not None, "Der gespeicherte Trip liess sich nicht laden."
    return geladen, user_id, trip_id


def _aufgeloest(dc, report_type: str = "evening"):
    from output.renderers.compare_outlook_metric_ids import (
        resolve_trip_outlook_metrics,
    )

    return resolve_trip_outlook_metrics(dc, report_type)


# ---------------------------------------------------------------------------
# AC-1 — gespeichert wird die Kennung, nicht das Paar
# ---------------------------------------------------------------------------

def test_ac1_gespeicherte_ausblick_auswahl_besteht_aus_reinen_kennungen(tmp_path):
    """AC-1: Given ein Trip ohne bisherige Ausblick-Auswahl / When der Nutzer
    'Niederschlag' und 'Böen' waehlt und speichert / Then steht unter
    ``display_config.outlook_metrics`` die Liste ``["precipitation","gust"]``
    aus reinen Zeichenketten — ohne Objekte, ohne Auswertungsangabe.

    Beide Eingabeformen werden in EINEM Test geprueft, weil das Ergebnis in
    der Datei fuer beide dasselbe sein muss: der Editor liefert nach A2
    Kennungen, ein Bestands-Client (oder ein Bestands-Trip, der nur
    weitergespeichert wird) liefert weiterhin Paare. 'Beim naechsten
    Speichern wird die Auswahl im Kennungsformat zurueckgeschrieben"
    (Spec, Expected Behavior/Side effects) gilt fuer beide Wege.
    """
    for form, eingabe in (("Kennungen", list(KENNUNGEN)), ("Paare", list(PAARE))):
        _, user_id, trip_id = _gespeichert_und_geladen(eingabe, tmp_path)
        gespeichert = _rohes_display_config(tmp_path, user_id, trip_id).get(
            "outlook_metrics")

        assert gespeichert == KENNUNGEN, (
            f"Editor-Eingabe im Format '{form}' landete als {gespeichert!r} "
            f"in der Datei statt als {KENNUNGEN!r}. Der Ausblick behaelt sein "
            "eigenes, viertes Vokabular (Groesse+Auswertung), statt wie "
            "Kanal-An/Aus, Reihenfolge, SMS-Kuerzel und Schwellwerte die "
            "reine Kennung zu speichern (AC-1)."
        )
        assert all(isinstance(e, str) for e in gespeichert or []), (
            f"Die gespeicherte Auswahl enthaelt Nicht-Zeichenketten: "
            f"{gespeichert!r} (AC-1)."
        )


# ---------------------------------------------------------------------------
# AC-2 — Bestandsdatei im Paar-Format wird beim Laden zu Kennungen
# ---------------------------------------------------------------------------

def test_ac2_altform_paare_werden_beim_laden_zu_je_einer_kennung(tmp_path):
    """AC-2: Given ein Bestands-Trip, dessen Datei ``temperature/min`` UND
    ``temperature/max`` enthaelt / When der Trip geladen wird / Then enthaelt
    die aufgeloeste Auswahl ``temperature`` GENAU EINMAL, und die Reihenfolge
    der uebrigen Eintraege bleibt erhalten.

    Die Bestandsdatei wird bewusst NACHTRAEGLICH praepariert statt ueber den
    Schreibpfad erzeugt: nach AC-1 schreibt der Schreibpfad Kennungen, ueber
    ihn liesse sich eine echte Altform-Datei gar nicht mehr herstellen — der
    Test pruefte dann nur noch sich selbst.
    """
    user_id = f"a2-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    _speichern(_trip(trip_id, _display_config(trip_id)), tmp_path, user_id)

    pfad = _pfad(tmp_path, user_id, trip_id)
    roh = json.loads(pfad.read_text(encoding="utf-8"))
    roh["display_config"]["outlook_metrics"] = ALTFORM_TEMPERATUR
    pfad.write_text(json.dumps(roh), encoding="utf-8")

    geladen = _laden(trip_id, tmp_path, user_id)
    assert geladen is not None, "Die praeparierte Bestandsdatei liess sich nicht laden."

    fuer_die_flaeche = _kennungen(geladen.display_config.outlook_metrics)
    assert fuer_die_flaeche == ["temperature", "precipitation"], (
        "Die geladene Ausblick-Auswahl der Bestandsdatei lautet "
        f"{fuer_die_flaeche!r} statt ['temperature', 'precipitation']. Tief "
        "und Hoch derselben Groesse muessen beim Lesen zu EINER Kennung "
        "werden (AC-2) — sonst erscheint 'Temperatur' doppelt in der "
        "Auswahl und erzeugt zwei Spalten."
    )

    aufgeloest = _kennungen(_aufgeloest(geladen.display_config))
    assert aufgeloest == ["temperature", "precipitation"], (
        f"Die aufgeloeste Auswahl lautet {aufgeloest!r} statt "
        "['temperature', 'precipitation'] — die Altform kommt bis in den "
        "Renderpfad als zwei Temperatur-Eintraege durch (AC-2)."
    )


# ---------------------------------------------------------------------------
# AC-7 — Drei-Werte-Semantik bleibt im Kennungsformat unterscheidbar
# ---------------------------------------------------------------------------

def test_ac7a_nie_gewaehlte_auswahl_bleibt_abwesend_und_bleibt_von_gewaehlter_trennbar(tmp_path):
    """AC-7 (a): Given ein Trip, der nie eine Ausblick-Auswahl gespeichert hat
    / When der Nutzer eine ANDERE Einstellung aendert und speichert / Then
    bleibt ``outlook_metrics`` in der Datei abwesend und der Ausblick faellt
    auf die sieben festen Standardspalten zurueck (aufgeloest: ``None``).

    Gegenprobe im selben Test: ein Trip MIT gefuellter Kennungsauswahl muss
    davon unterscheidbar sein (aufgeloest: nicht ``None``, nicht leer). Ohne
    diese Gegenprobe waere 'None' trivial erreichbar — auch ein Aufloeser,
    der jede Kennungsauswahl wegwirft, bestuende die erste Haelfte.
    """
    user_id = f"a2-{uuid.uuid4().hex[:8]}"
    trip_id = f"trip-{uuid.uuid4().hex[:8]}"
    dc = _display_config(trip_id, telegram_kurzform=True)   # andere Einstellung
    _speichern(_trip(trip_id, dc), tmp_path, user_id)

    roh = _rohes_display_config(tmp_path, user_id, trip_id)
    assert "outlook_metrics" not in roh, (
        "Ein Trip ohne je gewaehlte Ausblick-Auswahl hat beim Speichern einer "
        f"anderen Einstellung ein explizites Feld bekommen: "
        f"{roh.get('outlook_metrics')!r}. Damit waere 'nie gewaehlt' von "
        "'bewusst geleert' nicht mehr zu unterscheiden (AC-7)."
    )
    geladen = _laden(trip_id, tmp_path, user_id)
    assert _aufgeloest(geladen.display_config) is None, (
        "Ohne gespeicherte Auswahl muss die Aufloesung None liefern (sieben "
        f"feste Spalten), sie lieferte {_aufgeloest(geladen.display_config)!r}."
    )

    gewaehlt, _, _ = _gespeichert_und_geladen(list(KENNUNGEN), tmp_path)
    aufgeloest = _aufgeloest(gewaehlt.display_config)
    assert _kennungen(aufgeloest) == KENNUNGEN, (
        f"Eine gefuellte Kennungsauswahl loest zu {aufgeloest!r} auf statt zu "
        f"{KENNUNGEN!r}. Damit ist 'gewaehlt' nicht mehr von 'nie gewaehlt' "
        "bzw. 'bewusst geleert' zu trennen — genau der stille Fehlerpfad "
        "R-A2-3/M5 (AC-7)."
    )


def test_ac7b_bewusst_geleerte_auswahl_bleibt_abgeschaltet_und_bleibt_von_gewaehlter_trennbar(tmp_path):
    """AC-7 (b): Given eine ausdruecklich geleerte Auswahl (``[]``) / When der
    Trip gespeichert und wieder geladen wird / Then steht ``[]`` in der Datei
    und die Aufloesung liefert ``[]`` — der Ausblick-Block bleibt
    abgeschaltet.

    Gegenprobe im selben Test: eine gefuellte Kennungsauswahl darf NICHT
    ebenfalls zu ``[]`` kollabieren. Genau das tut der heutige Aufloeser
    (gemessen, M5: ``resolve_outlook_metrics(['temperature', ...]) -> []``),
    und genau daran verschwindet der Ausblick still statt zurueckzufallen.
    """
    geleert, user_id, trip_id = _gespeichert_und_geladen([], tmp_path)
    roh = _rohes_display_config(tmp_path, user_id, trip_id)
    assert roh.get("outlook_metrics") == [], (
        f"In der Datei steht {roh.get('outlook_metrics')!r} statt [] — die "
        "bewusste Leerauswahl hat den Roundtrip nicht ueberlebt (AC-7)."
    )
    assert _aufgeloest(geleert.display_config) == [], (
        "Die bewusst geleerte Auswahl loest zu "
        f"{_aufgeloest(geleert.display_config)!r} statt zu [] auf — der Block "
        "muesste abgeschaltet bleiben (AC-7)."
    )

    gewaehlt, _, _ = _gespeichert_und_geladen(list(KENNUNGEN), tmp_path)
    aufgeloest = _aufgeloest(gewaehlt.display_config)
    assert aufgeloest, (
        f"Eine gefuellte Kennungsauswahl {KENNUNGEN!r} loest zu {aufgeloest!r} "
        "auf — zeichengleich zur bewusst geleerten Auswahl. 'Unaufloesbar' "
        "und 'bewusst geleert' duerfen nie denselben Zustand erzeugen, sonst "
        "schaltet eine gueltige Auswahl den Ausblick ab (AC-7, R-A2-3)."
    )


# ---------------------------------------------------------------------------
# AC-10 — Mandantentrennung
# ---------------------------------------------------------------------------

def test_ac10_zwei_nutzer_sehen_ausschliesslich_die_eigene_ausblick_auswahl(tmp_path):
    """AC-10: Given zwei Nutzer mit je eigener Ausblick-Auswahl / When beide
    speichern und danach ihre Trips laden / Then sieht jeder ausschliesslich
    seine eigene Auswahl, und keine erscheint beim jeweils anderen.

    Geprueft wird die AUFGELOESTE Auswahl, nicht nur der rohe Dateiinhalt:
    ein Aufloeser, der jede Kennungsauswahl zu ``[]`` macht, liesse beide
    Nutzer dasselbe (naemlich nichts) sehen — die Isolation waere dann
    trivial erfuellt und der Test wertlos.
    """
    a_id, b_id = f"a2-a-{uuid.uuid4().hex[:8]}", f"a2-b-{uuid.uuid4().hex[:8]}"
    a_auswahl, b_auswahl = ["temperature"], ["precipitation", "gust"]

    a_trip, _, a_trip_id = _gespeichert_und_geladen(a_auswahl, tmp_path, a_id)
    b_trip, _, b_trip_id = _gespeichert_und_geladen(b_auswahl, tmp_path, b_id)

    a_sicht = _kennungen(_aufgeloest(a_trip.display_config))
    b_sicht = _kennungen(_aufgeloest(b_trip.display_config))

    assert a_sicht == a_auswahl, (
        f"Nutzer A sieht {a_sicht!r} statt seiner eigenen Auswahl "
        f"{a_auswahl!r} (AC-10)."
    )
    assert b_sicht == b_auswahl, (
        f"Nutzer B sieht {b_sicht!r} statt seiner eigenen Auswahl "
        f"{b_auswahl!r} (AC-10)."
    )
    assert a_sicht != b_sicht, (
        "Beide Nutzer sehen dieselbe Ausblick-Auswahl "
        f"({a_sicht!r}) — die Trennung ist nicht nachweisbar (AC-10)."
    )
    assert _laden(a_trip_id, tmp_path, b_id) is None, (
        "Nutzer B kann den Trip von Nutzer A laden — Cross-User-Datenleck."
    )
    assert _laden(b_trip_id, tmp_path, a_id) is None, (
        "Nutzer A kann den Trip von Nutzer B laden — Cross-User-Datenleck."
    )
