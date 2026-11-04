"""Grenzen der 7 Profil-Ampel-Vorlagen (Issue #2792 S1a, ADR-0106).

Quelle (SSOT der Zahlen): ``docs/context/einstellungen_neu.md`` §4.4, Tabellen
je Vorlage, wortgetreu uebertragen. „–" = ``None`` (offen). Spalten je Zeile:
Metrik, im Briefing, unten (rot, orange, gelb), oben (gelb, orange, rot),
Alarm ab. „kein Alarm", „kein Alarm (Vorbote)" und „Nie" = ``"never"``.

Vergleich wie ``severity_from_thresholds``: oben ``Wert >= Grenze``, unten
``Wert < Grenze``. Die Vorlage „allgemein" ist mit dem bisherigen
``display_thresholds`` des Katalogs deckungsgleich (ohne CAPE, P1); die
Paritaets-Ratsche steht in ``tests/tdd/test_ampel_modell_und_aufloesung.py``.

Zeilen ohne heutigen Leser (z.B. Taupunkt, Nullgradgrenze) liegen nur als
Daten vor und werden erst in S7 gelesen.
"""

from __future__ import annotations

N = None
X = (N, N, N)
OR, NIE = "orange", "never"

# (metric_id, im Briefing, unten rot/orange/gelb, oben gelb/orange/rot, Alarm ab)
_ZEILEN: dict[str, list[tuple]] = {
    "alpen-trekking": [
        ("temperature", True, (-10, -3, 2), (27, 30, 33), OR),
        ("temperature_night", True, (-8, -3, 0), X, OR),
        ("wind_chill", True, (-15, -8, -2), X, NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, X, (30, 45, 60), OR),
        ("gust", True, X, (35, 50, 70), OR),
        ("wind_direction", False, X, X, NIE),
        ("precipitation", True, X, (1, 5, 15), OR),
        ("rain_probability", True, X, (30, 60, 80), NIE),
        ("thunder", True, X, X, OR),
        ("visibility", True, (100, 300, 1000), X, OR),
        ("cloud_total", True, X, (70, 90, N), NIE),
        ("cloud_low", True, X, (50, 80, N), NIE),
        ("sunshine", False, (N, 1, 3), X, NIE),
        ("uv_index", True, X, (6, 8, 10), NIE),
        ("freezing_level", True, (-300, 0, 300), X, OR),
        ("snowfall_limit", True, (-500, 0, 300), X, OR),
        ("fresh_snow", False, X, (5, 10, 20), OR),
        ("snow_depth", False, X, X, NIE),
    ],
    "wandern": [
        ("temperature", True, (-10, -5, 0), (26, 30, 33), OR),
        ("temperature_night", True, (-8, -3, 0), X, OR),
        ("wind_chill", False, (-15, -5, 0), (28, 31, 34), NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", True, X, X, NIE),
        ("wind", True, X, (30, 50, 70), OR),
        ("gust", True, X, (40, 60, 75), OR),
        ("wind_direction", False, X, X, NIE),
        ("precipitation", True, X, (1, 5, 10), OR),
        ("rain_probability", True, X, (30, 60, 80), NIE),
        ("thunder", True, X, X, OR),
        ("visibility", False, (500, 1000, 2000), X, OR),
        ("cloud_total", True, X, (70, 90, N), NIE),
        ("cloud_low", False, X, (50, 80, N), NIE),
        ("sunshine", True, (N, 1, 3), X, NIE),
        ("uv_index", True, X, (5, 7, 9), NIE),
        ("freezing_level", False, (-300, 0, 300), X, OR),
        ("snowfall_limit", False, (-300, 0, 300), X, OR),
        ("fresh_snow", False, X, (10, 20, 30), OR),
        ("snow_depth", False, X, X, NIE),
    ],
    "skitouren": [
        ("temperature", True, (-30, -20, -15), (3, 8, 15), OR),
        ("temperature_night", True, (-25, -18, -12), (0, 2, 5), OR),
        ("wind_chill", True, (-35, -25, -15), X, NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, X, (30, 45, 60), OR),
        ("gust", True, X, (40, 55, 70), OR),
        ("wind_direction", False, X, X, NIE),
        ("precipitation", True, X, (2, 10, 20), OR),
        ("rain_probability", False, X, (30, 60, 80), NIE),
        ("thunder", False, X, X, OR),
        ("visibility", True, (200, 500, 1000), X, OR),
        ("cloud_total", True, X, (70, 90, N), NIE),
        ("cloud_low", True, X, (40, 70, 90), NIE),
        ("sunshine", False, (N, 1, 3), X, NIE),
        ("uv_index", False, X, (3, 6, 8), NIE),
        ("freezing_level", True, X, (300, 800, 1500), OR),
        ("snowfall_limit", True, X, (0, 300, 800), OR),
        ("fresh_snow", True, X, (20, 30, 50), OR),
        ("snow_depth", True, (15, 30, 50), X, OR),
    ],
    "wintersport": [
        ("temperature", True, (-25, -20, -15), (5, 10, 15), OR),
        ("temperature_night", True, (-25, -18, -12), (0, 2, 5), NIE),
        ("wind_chill", True, (-30, -22, -15), X, NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, X, (30, 50, 70), OR),
        ("gust", True, X, (40, 60, 80), OR),
        ("wind_direction", False, X, X, NIE),
        ("precipitation", True, X, (2, 10, 20), OR),
        ("rain_probability", False, X, (30, 60, 80), NIE),
        ("thunder", False, X, X, OR),
        ("visibility", True, (200, 500, 1000), X, OR),
        ("cloud_total", True, X, (70, 90, N), NIE),
        ("cloud_low", False, X, (50, 80, N), NIE),
        ("sunshine", True, (N, 1, 3), X, NIE),
        ("uv_index", False, X, (3, 6, 8), NIE),
        ("freezing_level", False, (-300, 0, 300), X, OR),
        ("snowfall_limit", False, (-300, 0, 300), X, OR),
        ("fresh_snow", True, X, X, NIE),
        ("snow_depth", True, (10, 20, 40), X, OR),
    ],
    "radtour": [
        ("temperature", True, (-5, 0, 5), (28, 32, 35), OR),
        ("temperature_night", True, (-5, 0, 5), X, NIE),
        ("wind_chill", True, (-15, -5, 0), (28, 31, 34), NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, X, (20, 30, 45), OR),
        ("gust", True, X, (35, 50, 65), OR),
        ("wind_direction", True, X, X, NIE),
        ("precipitation", True, X, (0.5, 2, 5), OR),
        ("rain_probability", True, X, (30, 50, 70), NIE),
        ("thunder", True, X, X, OR),
        ("visibility", False, (500, 1000, 2000), X, OR),
        ("cloud_total", True, X, (80, 95, N), NIE),
        ("cloud_low", False, X, (50, 80, N), NIE),
        ("sunshine", True, (N, 1, 3), X, NIE),
        ("uv_index", True, X, (6, 8, 10), NIE),
        ("freezing_level", False, (-300, 0, 300), X, OR),
        ("snowfall_limit", False, (-300, 0, 300), X, OR),
        ("fresh_snow", False, X, (10, 20, 30), OR),
        ("snow_depth", False, X, X, NIE),
    ],
    "wassersport": [
        ("temperature", True, (0, 5, 10), (30, 33, 36), OR),
        ("temperature_night", True, (0, 5, 8), X, NIE),
        ("wind_chill", False, (-15, -5, 0), (28, 31, 34), NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, (N, 4, 8), (30, 40, 50), OR),
        ("gust", True, X, (40, 50, 62), OR),
        ("wind_direction", True, X, X, NIE),
        ("precipitation", True, X, (2, 5, 10), OR),
        ("rain_probability", True, X, (30, 60, 80), NIE),
        ("thunder", True, X, X, OR),
        ("visibility", True, (500, 1000, 2000), X, OR),
        ("cloud_total", True, X, (80, 95, N), NIE),
        ("cloud_low", False, X, (50, 80, N), NIE),
        ("sunshine", False, (N, 1, 3), X, NIE),
        ("uv_index", False, X, (6, 8, 10), NIE),
        ("freezing_level", False, (-300, 0, 300), X, OR),
        ("snowfall_limit", False, (-300, 0, 300), X, OR),
        ("fresh_snow", False, X, (10, 20, 30), OR),
        ("snow_depth", False, X, X, NIE),
    ],
    "allgemein": [
        ("temperature", True, (-15, -5, 0), (28, 31, 34), OR),
        ("temperature_night", False, (-10, -5, 0), X, OR),
        ("wind_chill", False, (-15, -5, 0), (28, 31, 34), NIE),
        ("dewpoint", False, X, (16, 18, 21), NIE),
        ("humidity", False, X, X, NIE),
        ("wind", True, X, (30, 50, 70), OR),
        ("gust", True, X, (30, 45, 60), OR),
        ("wind_direction", False, X, X, NIE),
        ("precipitation", True, X, (1, 5, 10), OR),
        ("rain_probability", True, X, (30, 60, 80), NIE),
        ("thunder", True, X, X, OR),
        ("visibility", False, (500, 1000, 2000), X, OR),
        ("cloud_total", True, X, (60, 85, N), NIE),
        ("cloud_low", False, X, (50, 80, N), NIE),
        ("sunshine", True, (N, 1, 3), X, NIE),
        ("uv_index", False, X, (3, 6, 8), NIE),
        ("freezing_level", False, (-300, 0, 300), X, OR),
        ("snowfall_limit", False, (-300, 0, 300), X, OR),
        ("fresh_snow", False, X, (10, 20, 30), OR),
        ("snow_depth", False, X, X, NIE),
    ],
}

# Gewitterzeile je Vorlage: (mittel, hoch). Nur Wassersport weicht ab.
_GEWITTER: dict[str, tuple[str, str]] = {tid: ("orange", "red") for tid in _ZEILEN}
_GEWITTER["wassersport"] = ("red", "red")


def _vorlage(tid: str) -> dict:
    metrics = {
        mid: {
            "enabled": an,
            "lower": dict(zip(("red", "orange", "yellow"), unten)),
            "upper": dict(zip(("yellow", "orange", "red"), oben)),
            "alarm_ab": alarm,
        }
        for mid, an, unten, oben, alarm in _ZEILEN[tid]
    }
    mittel, hoch = _GEWITTER[tid]
    return {"template": tid, "metrics": metrics, "thunder": {"mittel": mittel, "hoch": hoch}}


#: Vorlagen-ID -> vollstaendige Ampel (Struktur wie ``display_config.ampel``).
#: Nicht mutieren; Aufrufer kopieren (``copy.deepcopy``).
AMPEL_TEMPLATES: dict[str, dict] = {tid: _vorlage(tid) for tid in _ZEILEN}

DEFAULT_TEMPLATE = "allgemein"
