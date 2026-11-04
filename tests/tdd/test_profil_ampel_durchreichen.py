"""TDD RED — Issue #2792 S1c-1 „Durchreichen, Ausgabe unverändert".

SPEC: docs/specs/modules/feat_2792_s1_profil_ampel.md §5 „Träger", AC-20 (Struktur)
KONTEXT: docs/context/feat-2792-s1c-leser.md (Abschnitt „S1c-1: Einstieg vs. intern")

Was S1c-1 liefert: Das AUFGELÖSTE Ampel-Objekt (``resolve_ampel(sub)``) geht
als keyword-only Pflichtparameter ``ampel`` ohne Default bis an jede
Farbentscheidung. Die Einstiege (Funktionen mit Abo-Argument: ``format_email``,
``render_html``/``render_plain``/``render_compact``, ``render_compare_html``,
``build_outlook_row``) lösen in S1c-1 noch fest ``resolve_ampel(None)`` auf ⇒
Ausgabe byte-gleich (Golden-Fixtures + Modus-Matrix wachen darüber). Erst
S1c-4 schaltet die Einstiege auf das Abo um.

Darum prüft diese Datei die INTERNEN Farbentscheider direkt mit einer
übergebenen Skitouren-/Wassersport-Ampel gegen „allgemein": bei „allgemein"
wäre ein vergessenes Durchreichen unsichtbar (Spec Test Plan,
Mutationsgegenprobe).

Kern-Schicht: keine Mocks, kein Netz, kein Dateiinhalt-Check. Der
Signatur-Test prüft eine Laufzeit-Eigenschaft (``inspect.signature``) — ein
vergessener Parameter soll laut scheitern statt still „allgemein" zu färben.

Interne Funktionen mit Pflicht-``ampel`` (Liste festgelegt in /40, nicht in
/50 neu entscheiden): ``metric_format.severity_for``,
``helpers.ampel_level``, ``outlook._metric_column_bg``,
``outlook.render_outlook_table``, ``alert.hours._stage``,
``alert.hours.affected_hours``, ``alert.project.to_alert_message``,
``alert.project.to_point_alert_message``,
``compare_html.build_cv2_metrics``, ``compare_html.build_hour_metrics``.
"""
from __future__ import annotations

import inspect

import pytest

from app.ampel import resolve_ampel
from app.metric_catalog import get_metric

SKI = resolve_ampel({"display_config": {"preset_name": "skitouren"}})
WASSER = resolve_ampel({"display_config": {"preset_name": "wassersport"}})
ALLG = resolve_ampel(None)

# Die 10 Metriken, die HEUTE (vor S1) eine Farbe tragen: Katalog-
# display_thresholds. CAPE ist die elfte Lesestelle (Katalog ja, Vorlage nein).
_HEUTIGE_LESER = (
    "temperature", "wind_chill", "wind", "gust", "precipitation",
    "rain_probability", "visibility", "uv_index", "fresh_snow",
)
# Vorlagen-Zeilen ohne heutigen Leser (Spec §2): dürfen in S1 nichts färben.
_OHNE_LESER = (
    "temperature_night", "dewpoint", "cloud_total", "cloud_low", "sunshine",
    "freezing_level", "snowfall_limit",
)


def _schwellen_aus_ampel():
    from app.ampel import schwellen_aus_ampel  # neu in S1c-1
    return schwellen_aus_ampel


# ---------------------------------------------------------------------------
# 1. Träger: Schwellen aus dem AUFGELÖSTEN Objekt
# ---------------------------------------------------------------------------

def test_schwellen_aus_aufgeloester_ampel_tragen_die_vorlage():
    """Given die aufgelöste Skitouren-Ampel / When die Böen-Schwellen daraus
    gelesen werden / Then gelb 40, orange 55, rot 70.

    Falle (gemessen in /40): ``ampel_for(resolve_ampel(...))`` findet im
    aufgelösten Dict kein ``ampel``/``preset_name`` und fällt STILL auf
    „allgemein" (gelb 30) zurück. Der Träger braucht daher eine eigene
    Lesefunktion für das aufgelöste Objekt."""
    schwellen = _schwellen_aus_ampel()
    assert schwellen(SKI, "gust") == {"yellow": 40, "orange": 55, "red": 70}
    assert schwellen(WASSER, "wind") == {
        "yellow": 30, "orange": 40, "red": 50, "orange_lt": 4, "yellow_lt": 8}


@pytest.mark.parametrize("metric_id", _HEUTIGE_LESER + ("cape",))
def test_allgemein_liefert_genau_die_heutigen_katalog_schwellen(metric_id):
    """Given die Vorlage „allgemein" / When die Schwellen einer heute
    gefärbten Metrik gelesen werden / Then exakt das heutige
    ``display_thresholds`` (Byte-Gleichheit S1c-1).

    CAPE: S1c-1 bleibt byte-gleich, CAPE wird noch wie heute nach Katalog
    gefärbt (Brücke in ``app.ampel``). Diese Zeile kehrt sich in S1c-4 um
    (P1, AC-6/AC-19 a: CAPE ohne Farbe) — dort anpassen, nie lockern."""
    schwellen = _schwellen_aus_ampel()
    erwartet = {k: float(v) for k, v in get_metric(metric_id).display_thresholds.items()}
    ist = {k: float(v) for k, v in schwellen(ALLG, metric_id).items()}
    assert ist == erwartet


@pytest.mark.parametrize("metric_id", _OHNE_LESER)
@pytest.mark.parametrize("ampel", [ALLG, SKI], ids=["allgemein", "skitouren"])
def test_vorlagen_zeilen_ohne_heutigen_leser_faerben_nichts(metric_id, ampel):
    """Given Vorlagen-Zeilen, die in S1 keinen Leser haben (Taupunkt,
    Bewölkung, Sonnenstunden …) / When ihre Schwellen für einen Renderer
    gelesen werden / Then leer — sonst begänne z. B. die Vergleichs-
    Stundentabelle, Taupunkt und Bewölkung zu färben (Spec §2, AC-19)."""
    assert _schwellen_aus_ampel()(ampel, metric_id) == {}


# ---------------------------------------------------------------------------
# 2. Zentrale Bewertung: severity_for nimmt die Ampel
# ---------------------------------------------------------------------------

def test_severity_for_bewertet_nach_uebergebener_ampel():
    """Given +9 °C / When mit Skitouren- bzw. Allgemein-Ampel bewertet /
    Then orange (Skitouren orange ab 8) bzw. grün (gelb erst ab 28)."""
    from output.metric_format import severity_for
    assert severity_for("temperature", 9.0, ampel=SKI) == "orange"
    assert severity_for("temperature", 9.0, ampel=ALLG) == "green"


def test_severity_for_wertet_die_untere_seite_der_ampel_aus():
    """AC-3 am Entstehungsort: Wassersport-Wind 3 orange, 6 gelb, 15 grün."""
    from output.metric_format import severity_for
    assert severity_for("wind", 3.0, ampel=WASSER) == "orange"
    assert severity_for("wind", 6.0, ampel=WASSER) == "yellow"
    assert severity_for("wind", 15.0, ampel=WASSER) == "green"


def test_severity_for_ohne_ampel_scheitert_laut():
    """Ein vergessenes Durchreichen darf nicht still „allgemein" färben."""
    from output.metric_format import severity_for
    with pytest.raises(TypeError):
        severity_for("temperature", 9.0)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# 3. Interne Farbentscheider je Leser
# ---------------------------------------------------------------------------

def test_mail_ampel_level_folgt_der_uebergebenen_ampel():
    """Mail-Stundentabelle/Kachel (helpers.ampel_level): Böen 52 km/h ist
    bei Skitouren gelb (orange erst ab 55), bei Allgemein orange (ab 45)."""
    from output.renderers.email.helpers import ampel_level
    assert ampel_level("gust", 52.0, ampel=SKI) == "yellow"
    assert ampel_level("gust", 52.0, ampel=ALLG) == "orange"


def test_ausblick_zellhintergrund_folgt_der_uebergebenen_ampel():
    """3-Tages-Ausblick (outlook._metric_column_bg): dieselbe Böe 52 km/h
    bekommt bei Skitouren den Gelb-, bei Allgemein den Orange-Hintergrund."""
    from output.renderers.email.design_tokens import tone_css
    from output.renderers.email.outlook import _metric_column_bg
    col = {"metric_id": "gust"}
    assert _metric_column_bg(col, 52.0, ampel=SKI) == f"background:{tone_css('yellow')[0]};"
    assert _metric_column_bg(col, 52.0, ampel=ALLG) == f"background:{tone_css('orange')[0]};"


def test_alarm_stundenstufe_folgt_der_uebergebenen_ampel():
    """AC-21 am Entstehungsort (Alarm-Mail/-Telegram teilen ``_stage``):
    Böen 52 km/h → Stufe gelb (Skitouren) bzw. orange (Allgemein)."""
    from output.renderers.alert.hours import _stage
    from output.renderers.email.helpers import _AMPEL_STAGE_ORDER
    assert _stage("gust", 52.0, ampel=SKI) == _AMPEL_STAGE_ORDER.index("yellow")
    assert _stage("gust", 52.0, ampel=ALLG) == _AMPEL_STAGE_ORDER.index("orange")


def _sev_von(rows: list[dict], feld: str, wert: str) -> object:
    row = next(r for r in rows if r.get(feld) == wert)
    return row["sev"]


def test_vergleich_listen_werden_je_ampel_gebaut_unabhaengig_von_der_reihenfolge():
    """AC-20 (Struktur): Given Skitouren- und Allgemein-Ampel nacheinander im
    selben Prozess / When Übersicht (``build_cv2_metrics``) und Stundenverlauf
    (``build_hour_metrics``) gebaut werden / Then ist +9 °C bei Skitouren
    „warn" (orange) und bei Allgemein „ok" (grün) — in beiden Reihenfolgen,
    ohne Zustandsübernahme zwischen den Aufrufen."""
    from output.renderers.email.compare_html import build_cv2_metrics, build_hour_metrics
    erwartet = {"ski": "warn", "allg": "ok"}
    ampeln = {"ski": SKI, "allg": ALLG}
    for reihenfolge in (("ski", "allg", "ski"), ("allg", "ski", "allg")):
        for name in reihenfolge:
            cv2 = build_cv2_metrics(ampel=ampeln[name])
            hour = build_hour_metrics(ampel=ampeln[name])
            assert _sev_von(cv2, "key", "temp_max")(9.0) == erwartet[name], (reihenfolge, name)
            assert _sev_von(hour, "metric_id", "temperature")(9.0) == erwartet[name], (reihenfolge, name)


@pytest.mark.parametrize("ampel", [ALLG, SKI], ids=["allgemein", "skitouren"])
def test_vergleich_stundenzeilen_mit_ampel_sind_dieselben_wie_heute(ampel):
    """Byte-Gleichheit S1c-1: genau diese Stundenspalten tragen eine Ampel
    (heutiger Stand ``HOUR_METRICS``, gemessen in /40) — Taupunkt, Bewölkung,
    gefühlte Temperatur usw. bleiben ohne Farbe, auch wenn die Vorlage Daten
    für sie führt."""
    from output.renderers.email.compare_html import build_hour_metrics
    mit_sev = {r["metric_id"] for r in build_hour_metrics(ampel=ampel) if "sev" in r}
    assert mit_sev == {
        "fresh_snow", "gust", "precipitation", "rain_probability",
        "temperature", "thunder", "uv_index", "visibility", "wind",
    }


def test_vergleich_uebersichtszeilen_mit_ampel_sind_dieselben_wie_heute():
    from output.renderers.email.compare_html import build_cv2_metrics
    mit_sev = [r["key"] for r in build_cv2_metrics(ampel=ALLG) if "sev" in r]
    assert mit_sev == [
        "temp_max", "wind_max", "precip_sum", "pop_max", "thunder_max",
        "uv_max", "visibility_min", "temp_min", "gust_max",
    ]


# ---------------------------------------------------------------------------
# 4. Kurzkanäle: Hervorhebung per Stufe vorbereitet (noch nicht verdrahtet)
# ---------------------------------------------------------------------------

def _hv(*paare):
    from output.tokens.dto import HourlyValue
    return tuple(HourlyValue(hour=h, value=v) for h, v in paare)


def _stufe(metric_id, ampel):
    from output.metric_format import severity_for
    return lambda v: severity_for(metric_id, v, ampel=ampel)


def test_spitzenwert_per_stufe_oben_ab_gelb():
    """Given Allgemein-Wind (gelb ab 30) / When 25, 31 @14, 28 / Then „31@14";
    ohne Gelb „-" (E1-Vorbereitung, AC-7 erste Hälfte)."""
    from output.tokens.metrics import render_threshold_peak_value
    stufe = _stufe("wind", ALLG)
    assert render_threshold_peak_value(
        "W", _hv((12, 25.0), (14, 31.0), (16, 28.0)), None, ampel_stufe=stufe) == "31@14"
    assert render_threshold_peak_value(
        "W", _hv((12, 25.0), (14, 20.0)), None, ampel_stufe=stufe) == "-"


def test_spitzenwert_per_stufe_erste_stunde_und_schlimmste_stunde():
    """Erste gelbe Stunde 12 (31), schlimmste Stunde 15 (55, orange) →
    bestehende Form „erst@h(spitze@h)"."""
    from output.tokens.metrics import render_threshold_peak_value
    assert render_threshold_peak_value(
        "W", _hv((10, 20.0), (12, 31.0), (15, 55.0)), None,
        ampel_stufe=_stufe("wind", ALLG)) == "31@12(55@15)"


def test_spitzenwert_per_stufe_unterschreiten_der_unteren_grenze():
    """AC-7 zweite Hälfte: Wassersport-Wind 3 km/h (unter Gelb 8) um 14 Uhr
    ist ein Spitzenwert „3@14" — die heutige Max-Logik sähe nur die 15."""
    from output.tokens.metrics import render_threshold_peak_value
    assert render_threshold_peak_value(
        "W", _hv((10, 15.0), (14, 3.0), (16, 12.0)), None,
        ampel_stufe=_stufe("wind", WASSER)) == "3@14"


def test_spitzenwert_per_stufe_wert_null_wird_nicht_verschluckt():
    """Falle: heute gilt ``peak.value <= 0 → "-"``. Windstille (0 km/h) ist
    bei Wassersport orange und muss erscheinen."""
    from output.tokens.metrics import render_threshold_peak_value
    assert render_threshold_peak_value(
        "W", _hv((9, 15.0), (14, 0.0)), None,
        ampel_stufe=_stufe("wind", WASSER)) == "0@14"


# ---------------------------------------------------------------------------
# 5. Alarm-Nachricht trägt die Ampel
# ---------------------------------------------------------------------------

def test_alarm_nachricht_hat_ein_ampel_feld():
    from dataclasses import fields

    from output.renderers.alert.model import AlertMessage
    assert "ampel" in {f.name for f in fields(AlertMessage)}


# ---------------------------------------------------------------------------
# 6. Pflichtparameter: keyword-only, ohne Default
# ---------------------------------------------------------------------------

_INTERN = [
    ("output.metric_format", "severity_for"),
    ("output.renderers.email.helpers", "ampel_level"),
    ("output.renderers.email.outlook", "_metric_column_bg"),
    ("output.renderers.email.outlook", "render_outlook_table"),
    ("output.renderers.alert.hours", "_stage"),
    ("output.renderers.alert.hours", "affected_hours"),
    ("output.renderers.alert.project", "to_alert_message"),
    ("output.renderers.alert.project", "to_point_alert_message"),
    ("output.renderers.email.compare_html", "build_cv2_metrics"),
    ("output.renderers.email.compare_html", "build_hour_metrics"),
]


@pytest.mark.parametrize("modul,name", _INTERN, ids=[f"{m.rsplit('.', 1)[-1]}.{n}" for m, n in _INTERN])
def test_interne_farbentscheider_verlangen_die_ampel(modul, name):
    """Given eine interne Funktion der Renderkette / Then hat sie einen
    keyword-only Parameter ``ampel`` OHNE Default (Spec §5: ein Default
    „allgemein" würde vergessenes Durchreichen bei Skitouren verdecken)."""
    import importlib
    fn = getattr(importlib.import_module(modul), name)
    param = inspect.signature(fn).parameters.get("ampel")
    assert param is not None, f"{modul}.{name} hat keinen Parameter 'ampel'"
    assert param.kind is inspect.Parameter.KEYWORD_ONLY
    assert param.default is inspect.Parameter.empty
