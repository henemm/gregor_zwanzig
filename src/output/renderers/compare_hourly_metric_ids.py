"""EINE Quelle fuer die Zuordnung Stundenverlaufs-Schluessel -> Wettergroesse.

Issue #1406 Scheibe B (Epic #1372 / Etappe E2 von #1435).
Spec: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md

Bis #1406 B wurde dieselbe Zuordnung an VIER Stellen gepflegt (Frontend-
Anzeigeliste, Frontend-Uebersetzung, Backend-Aufloesung, Renderer-
Spaltenliste). Ab jetzt ist dieses Modul die einzige: der Vorrat der waehlbaren
Groessen kommt aus dem zentralen Register (`src/app/metric_catalog.py`), und die
zehn historischen Kurzschluessel bleiben nur noch als LESE-Alias bestehen,
damit Bestandsdaten unveraendert laden (AC-4, kein Datenumbau).

Gespeichert wird ab dieser Scheibe die Katalog-ID (`temperature`); gelesen wird
dauerhaft BEIDES. Nicht aufloesbare Werte werden weiterhin sichtbar verworfen
(Protokollwarnung, Muster aus #1361 Befund 3), nicht still.
"""
from __future__ import annotations

import logging

from app.metric_catalog import get_all_metrics, get_metric

logger = logging.getLogger(__name__)

# LESE-Alias: historischer Compare-Kurzschluessel -> Katalog-ID des Registers.
# Rechte Seite ist bewusst die REGISTER-ID (nicht der Rohwert-Feldname) -- sonst
# bliebe ein zweites Vokabular als Zwischenschicht bestehen (AC-10, geprueft in
# tests/unit/test_compare_hourly_vocabulary_single_source.py).
# Diese Tabelle waechst NICHT mehr: neue Groessen werden als Katalog-ID
# gespeichert und brauchen keinen Eintrag.
FRONTEND_TO_HOURLY_METRIC_ID: dict[str, str] = {
    "temp_c": "temperature",
    "wind_chill_c": "wind_chill",
    "wind_kmh": "wind",
    "gust_kmh": "gust",
    "precip_mm": "precipitation",
    "uv_index": "uv_index",
    "thunder_level": "thunder",
    "pop_pct": "rain_probability",
    "visibility_m": "visibility",
    # Issue #1335 Scheibe 1: reines Merge-Signal, KEIN Eintrag in HOUR_METRICS
    # (compare_html.py) -- erzeugt keine eigene Spalte, sondern wird beim
    # Rendern in die Wind-Zelle gemergt (Kompass-Text), analog Trip-Muster
    # `should_merge_wind_dir()`.
    "wind_dir_deg": "wind_direction",
}

# Umkehr-Index (kein zweites Vokabular, reine Ableitung): Katalog-ID -> ihre
# historischen Kurzschluessel. Die Bedienflaeche erkennt damit eine Alt-Auswahl
# als angehakt wieder (AC-4, Bedienflaechen-Haelfte) -- ohne eine eigene
# Alias-Tabelle im Browser.
HOURLY_LEGACY_KEYS_BY_METRIC_ID: dict[str, list[str]] = {}
for _legacy, _metric_id in FRONTEND_TO_HOURLY_METRIC_ID.items():
    HOURLY_LEGACY_KEYS_BY_METRIC_ID.setdefault(_metric_id, []).append(_legacy)

# AC-11 (PO-Entscheid 2026-08-01): ausdruecklich vom Stundenverlauf
# ausgenommene Groessen. BENANNTE Menge statt stillem Fehlen -- Bedienflaeche,
# Aufloeser und Tests geben so dieselbe Auskunft.
HOURLY_EXCLUDED_METRIC_IDS: frozenset[str] = frozenset(
    {"sunshine", "temperature_night", "wind_chill_night"}
)

# Begruendung, die die Bedienflaeche anzeigt (ueber die Katalogantwort, s.
# compare_metric_catalog.get_compare_metric_catalog). Nennt den Grund UND die
# Groessen, die dieselbe Frage stuendlich beantworten.
HOURLY_EXCLUSION_REASON: dict[str, str] = {
    "sunshine": (
        "Stuendlich nur als Einstrahlung (W/m²) verfuegbar, nicht als "
        "Sonnenstunden — die Bewölkung und der UV-Index beantworten dieselbe "
        "Frage stundengenau."
    ),
    "temperature_night": (
        "Nachtfenster-Skalar (#1484), kein Stundenwert — stuendlich "
        "beantwortet die Temperatur dieselbe Frage."
    ),
    "wind_chill_night": (
        "Nachtfenster-Skalar (#1660), kein Stundenwert — stuendlich "
        "beantwortet die gefuehlte Temperatur dieselbe Frage."
    ),
}

# Reines Merge-Signal: erzeugt nie eine eigene Spalte (s. Modul-Kommentar oben
# und `compare_html._should_merge_wind_dir`).
HOURLY_MERGE_ONLY_METRIC_IDS: frozenset[str] = frozenset({"wind_direction"})

# Die Groessen, die ein NIE eingestellter Vergleich zeigt -- exakt die neun
# Spalten von vor dieser Scheibe, in genau ihrer Reihenfolge (AC-4: kein
# automatisches Hinzufuegen der neu waehlbaren Groessen). Bewusst eine
# ausgesprochene Vorgabemenge statt "kein Filter = alles": mit 22 Wert-Spalten
# waere "alles" ein ungefragter Sprung fuer jeden Bestands-Vergleich.
HOURLY_DEFAULT_METRIC_IDS: tuple[str, ...] = (
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "uv_index", "thunder", "rain_probability", "visibility",
)


def hourly_selectable_metric_ids() -> list[str]:
    """Katalog-IDs, die im Stundenverlauf angeboten werden -- alles aus dem
    Register ausser den ausdruecklich ausgenommenen (AC-11)."""
    return [
        m.id for m in get_all_metrics() if m.id not in HOURLY_EXCLUDED_METRIC_IDS
    ]


def normalize_hourly_metrics(hourly_metrics: list[str] | None) -> list[str] | None:
    """Gespeicherte Stundenauswahl -> Katalog-IDs (reihenfolge-erhaltend).

    Nimmt beide Schreibweisen entgegen: historischer Kurzschluessel
    (``temp_c``) oder Katalog-ID (``temperature``). Ausgenommene und
    unbekannte Werte fallen heraus. ``None`` bleibt ``None`` ("nie
    eingestellt").

    Issue #1466 AP1: eine Kennung, die das zentrale Register NICHT kennt, wird
    nicht mehr kommentarlos verworfen, sondern nach dem Hausmuster
    ("Sammeln-und-melden", s. ``resolve_enabled_metrics``) mit ihrem Namen
    protokolliert. Ausgenommene Groessen (AC-11) sind dagegen eine bewusste
    Auswahlregel und bleiben still — sonst entstuende eine Dauerwarnung ueber
    korrektes Verhalten.
    """
    if not isinstance(hourly_metrics, list):
        return None
    out: list[str] = []
    dropped: list[object] = []
    for raw in hourly_metrics:
        metric_id = FRONTEND_TO_HOURLY_METRIC_ID.get(raw, raw)
        if not isinstance(metric_id, str):
            continue
        if metric_id in HOURLY_EXCLUDED_METRIC_IDS:
            continue
        try:
            get_metric(metric_id)
        except KeyError:
            dropped.append(metric_id)
            continue
        if metric_id not in out:
            out.append(metric_id)
    if dropped:
        logger.warning(
            "normalize_hourly_metrics: %s ohne Eintrag im zentralen Register — "
            "Groesse wird aus der Stundenauswahl verworfen statt angezeigt "
            "(vgl. #1466 AP1, #1361 Befund 3)",
            dropped,
        )
    return out


def resolve_hourly_metrics(hourly_metrics: list[str] | None) -> list[str] | None:
    """Gespeicherte Stundenauswahl -> Renderer-Feldnamen (``dp_field``).

    Rueckgabe ``None`` (= "nie eingestellt", Renderer zeigt seine Vorgabemenge)
    nur wenn das Feld fehlt oder kein Listenwert ist (defensiv, kein TypeError
    -- Adversary-Analogie F001, #1104). Eine bewusst leere oder komplett
    unaufloesbare Auswahl liefert ``[]``, nicht ``None`` (Issue #1366, AC-4/
    AC-5) -- "leer heisst leer" statt "leer heisst alle".

    Aufgeloest wird gegen das zentrale Register: jede waehlbare Katalog-ID geht
    direkt durch, die zehn historischen Kurzschluessel ueber den Lese-Alias
    oben. Ausgenommene Groessen (AC-11) und unbekannte Werte werden verworfen
    -- mit Protokollwarnung statt still (#1361 Befund 3).

    Issue #1335 Scheibe 1: reihenfolge-erhaltend und dedupliziert (AC-2).
    """
    if not isinstance(hourly_metrics, list):
        return None
    normalized = normalize_hourly_metrics(hourly_metrics) or []
    unmapped = [
        m for m in hourly_metrics
        if FRONTEND_TO_HOURLY_METRIC_ID.get(m, m) not in normalized
    ]
    if unmapped:
        logger.warning(
            "resolve_hourly_metrics: %s ohne Register-Entsprechung (oder "
            "ausdruecklich ausgenommen, s. HOURLY_EXCLUDED_METRIC_IDS) — "
            "Auswahl wird ignoriert statt angezeigt (vgl. #1361 Befund 3)",
            unmapped,
        )
    return [get_metric(m).dp_field for m in normalized]


__all__ = [
    "resolve_hourly_metrics",
    "normalize_hourly_metrics",
    "hourly_selectable_metric_ids",
    "FRONTEND_TO_HOURLY_METRIC_ID",
    "HOURLY_LEGACY_KEYS_BY_METRIC_ID",
    "HOURLY_EXCLUDED_METRIC_IDS",
    "HOURLY_EXCLUSION_REASON",
    "HOURLY_MERGE_ONLY_METRIC_IDS",
    "HOURLY_DEFAULT_METRIC_IDS",
]
