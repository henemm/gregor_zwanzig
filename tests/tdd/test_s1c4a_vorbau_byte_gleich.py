"""Issue #2792 S1c-4a — Vorbau für das Umschalten, Ausgabe byte-gleich (AC-26).

Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md (v1.4, Schnitt-Tabelle
Zeile S1c-4a, Nachtrag §5 „Pflichten beim Umschalten" Punkte 1, 2, 9; AC-15
Nachtrag; AC-26; AC-27 Prädikat-Teil).

4a baut nur die Mechanik, die 4b braucht, OHNE dass sich irgendeine Ausgabe
ändert:

1. Prädikat „gelb oder schlechter" (beidseitig) + Gewitter-Prädikat in
   ``app/ampel.py`` — noch ohne Leser. Es nimmt das AUFGELÖSTE Ampel-Objekt
   (``resolve_ampel(sub)``, wie ``thunder_color``) und nutzt den einzigen
   Vergleichs-Kern ``severity_from_thresholds`` (über ``schwellen_aus_ampel``),
   keine zweite Vergleichslogik.
2. ``hiking_field_min_max_ts`` (Schwesterfunktion mit ``min_ts``);
   ``hiking_field_min_max`` delegiert und behält seine Tupelform.
3. Signaturlücken: ``render_comparison_text(preset=)`` und die
   Vergleichs-Alarme (``send_multi_location_deviation_alert``,
   ``send_multi_location_radar_alert``, Wrapper ``send_location_deviation_alert``)
   bekommen ``preset`` als Pflichtparameter (keyword-only, ohne Default);
   die Aufrufer reichen das Preset durch. Aufgelöst wird dort weiter
   ``resolve_ampel(None)`` (die Wirkung kommt erst in 4b).
4. ``build_outlook_row``/``_outlook_row`` bekommen einen expliziten
   Zweig-Parameter ``context="route"|"vergleich"`` (Pflicht, ohne Default;
   derselbe Name und dieselben Werte wie die übrigen geteilten Trip/Vergleich-
   Bausteine, z. B. ``compact_summary.py``, ``narrow.py``):
   die Wahl zwischen Trip- und Ortsvergleichs-Zweig hängt nicht mehr an
   ``trip_display_config is None``.
5. Katalogschlüssel für die 7 Vorlagen-Labels DE/EN. Abweichung zur
   Spec-Schreibweise ``mail.vorlage.<template_id>``: das Schlüsselmuster des
   Katalogs (``i18n.catalog.SCHLUESSEL_RE``) erlaubt keinen Bindestrich, daher
   ``mail.vorlage.<template_id mit "-" → "_">`` (``alpen-trekking`` →
   ``mail.vorlage.alpen_trekking``). Die Vorlagen-ID selbst bleibt
   Protokoll-Token und wird nie übersetzt. Den Schlüssel bildet EINE Stelle,
   ``app.ampel.vorlage_label_schluessel(template_id)`` (noch ohne Leser):
   ``t(f"mail.vorlage.{tid}")`` gäbe für ``alpen-trekking`` still den rohen
   Schlüssel zurück, weil ``t()`` auf den Schlüssel selbst zurückfällt.

Grenzen für die Umsetzung (bleiben grün, von anderen Tests bewacht):
kein neuer ``resolve_ampel``-Aufrufer (Zähl-Ratschen in
``test_profil_ampel_kette.py``), jeder ``ampel``-Parameter in ``src/output``
bleibt Pflicht + keyword-only, die Übergangstests ``:656/:779/:905`` bleiben
grün, alle Golden-Dateien und ``test_issue_811_mode_matrix.py`` unverändert.
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"


def _ampel(vorlage: str | None) -> dict:
    from app.ampel import resolve_ampel
    return resolve_ampel(None if vorlage is None else {"preset_name": vorlage})


# ---------------------------------------------------------------------------
# 1. Prädikat „gelb oder schlechter" (beidseitig), Gewitter-Prädikat
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vorlage,metrik,wert,erwartet", [
    # Allgemein, Wind oben: gelb ab 30 (Wert >= Grenze)
    ("allgemein", "wind", 29.0, False),
    ("allgemein", "wind", 30.0, True),
    ("allgemein", "wind", 31.0, True),
    # Wassersport, Wind unten: gelb unter 8, orange unter 4 (Wert < Grenze)
    ("wassersport", "wind", 3.0, True),
    ("wassersport", "wind", 7.0, True),
    ("wassersport", "wind", 8.0, False),
    ("wassersport", "wind", 9.0, False),
    # Skitouren-Temperatur oben orange ab 8, Allgemein gelb erst ab 28 (AC-1)
    ("skitouren", "temperature", 9.0, True),
    ("allgemein", "temperature", 9.0, False),
    # Skitouren-Temperatur unten gelb unter -15 (AC-4)
    ("skitouren", "temperature", -17.0, True),
    # Skitouren-Böen gelb ab 40, Allgemein gelb ab 30
    ("skitouren", "gust", 35.0, False),
    ("allgemein", "gust", 35.0, True),
])
def test_gelb_oder_schlechter_wertet_beide_seiten_der_aufgeloesten_ampel(vorlage, metrik, wert, erwartet):
    """AC-27 (Prädikat-Teil), §5 Punkt 9: ein Prädikat, beidseitig, aus dem
    AUFGELÖSTEN Objekt — Wassersport-Wind unter 8 km/h ist hervorzuheben."""
    from app.ampel import gelb_oder_schlechter
    assert gelb_oder_schlechter(_ampel(vorlage), metrik, wert) is erwartet


def test_gelb_oder_schlechter_ohne_wert_oder_ohne_ampel_leser_ist_falsch():
    from app.ampel import gelb_oder_schlechter
    allg = _ampel("allgemein")
    assert gelb_oder_schlechter(allg, "wind", None) is False
    # Luftdruck hat keine Ampel (kein Leser) -> nie hervorgehoben
    assert gelb_oder_schlechter(allg, "pressure", 5000.0) is False


@pytest.mark.parametrize("vorlage", ["allgemein", "skitouren", "wassersport", "wandern",
                                     "alpen-trekking", "wintersport", "radtour"])
@pytest.mark.parametrize("metrik", ["temperature", "wind", "gust", "precipitation",
                                    "rain_probability", "visibility", "uv_index", "fresh_snow",
                                    "wind_chill"])
def test_ampel_stufe_und_praedikat_folgen_dem_einzigen_vergleichskern(vorlage, metrik):
    """Keine zweite Vergleichslogik: Stufe == ``severity_for`` (SSoT
    ``severity_from_thresholds``), Prädikat == Stufe in {gelb, orange, rot},
    über einen Werte-Sweep beider Seiten."""
    from app.ampel import ampel_stufe, gelb_oder_schlechter
    from output.metric_format import severity_for
    amp = _ampel(vorlage)
    werte = [-40.0, -31.0, -20.0, -15.5, -5.0, 0.0, 0.5, 3.0, 4.0, 7.9, 8.0, 9.0, 15.0,
             20.0, 29.9, 30.0, 45.0, 60.0, 80.0, 500.0, 999.0, 1000.0, 2000.0, 9999.0]
    for w in werte:
        stufe = severity_for(metrik, w, ampel=amp)
        assert ampel_stufe(amp, metrik, w) == stufe, (vorlage, metrik, w)
        assert gelb_oder_schlechter(amp, metrik, w) is (stufe in {"yellow", "orange", "red"}), (
            vorlage, metrik, w)


def test_ampel_stufe_passt_als_callable_in_die_kurzkanal_hervorhebung():
    """``render_threshold_peak_value(ampel_stufe=)`` (vorbereitet in S1c-1)
    nimmt Wert -> Stufe. Das neue ``ampel_stufe`` muss dort direkt passen:
    Allgemein-Wind 25 bleibt ohne Spitzenwert, 31 um 14 Uhr erscheint (AC-7)."""
    from app.ampel import ampel_stufe
    from output.tokens.dto import HourlyValue
    from output.tokens.metrics import render_threshold_peak_value
    allg = _ampel("allgemein")

    def stufe(v):
        return ampel_stufe(allg, "wind", v)

    ruhig = (HourlyValue(hour=10, value=20.0), HourlyValue(hour=14, value=25.0))
    assert render_threshold_peak_value("W", ruhig, None, ampel_stufe=stufe) == "-"
    boeig = (HourlyValue(hour=10, value=20.0), HourlyValue(hour=14, value=31.0))
    assert render_threshold_peak_value("W", boeig, None, ampel_stufe=stufe) == "31@14"


@pytest.mark.parametrize("stufe,erwartet", [
    (None, False), ("NONE", False), ("LOW", True), ("MED", True), ("HIGH", True),
])
def test_gewitter_ist_ab_leicht_gelb_oder_schlechter(stufe, erwartet):
    """§5 Punkt 9 / P2: Gewitter ist ordinal, „≥ leicht" == bisherige
    Schwelle 1,0 == „gelb oder schlechter" (leicht ist fest gelb)."""
    from app.ampel import gewitter_gelb_oder_schlechter
    from app.models import ThunderLevel
    level = None if stufe is None else ThunderLevel(stufe)
    assert gewitter_gelb_oder_schlechter(level) is erwartet


@pytest.mark.parametrize("vorlage", ["allgemein", "wassersport", "skitouren"])
def test_gewitter_praedikat_deckt_sich_mit_der_zentralen_gewitterfarbe(vorlage):
    from app.ampel import gewitter_gelb_oder_schlechter, thunder_color
    from app.models import ThunderLevel
    amp = _ampel(vorlage)
    for lvl in ThunderLevel:
        assert gewitter_gelb_oder_schlechter(lvl) is (
            thunder_color(lvl, amp) in {"yellow", "orange", "red"}), (vorlage, lvl)


# ---------------------------------------------------------------------------
# 2. hiking_field_min_max_ts (Schwesterfunktion), alte Tupelform unverändert
# ---------------------------------------------------------------------------

def _punkte(stunden_werte):
    from app.models import ForecastDataPoint
    return [
        ForecastDataPoint(ts=datetime(2026, 7, 20, h, 0, tzinfo=timezone.utc), t2m_c=v)
        for h, v in stunden_werte
    ]


def test_schwesterfunktion_liefert_minimum_und_maximum_je_mit_stunde():
    from output.renderers.day_window import hiking_field_min_max_ts
    pts = _punkte([(6, -2.0), (10, 5.0), (14, 9.0), (16, 3.0)])
    # ForecastDataPoint normalisiert ts auf naive UTC (#1345)
    assert hiking_field_min_max_ts(pts, "t2m_c") == (
        -2.0, 9.0, datetime(2026, 7, 20, 6),
        datetime(2026, 7, 20, 14),
    )


def test_schwesterfunktion_nimmt_bei_gleichstand_die_frueheste_stunde():
    from output.renderers.day_window import hiking_field_min_max_ts
    pts = _punkte([(6, -2.0), (8, -2.0), (14, 9.0), (16, 9.0)])
    mn, mx, min_ts, max_ts = hiking_field_min_max_ts(pts, "t2m_c")
    assert min_ts.hour == 6
    assert max_ts.hour == 14


def test_schwesterfunktion_ohne_werte_liefert_none():
    from output.renderers.day_window import hiking_field_min_max_ts
    assert hiking_field_min_max_ts([], "t2m_c") is None
    assert hiking_field_min_max_ts(_punkte([(6, -2.0)]), "wind_chill_c") is None


@pytest.mark.parametrize("stunden_werte", [
    [(6, -2.0), (10, 5.0), (14, 9.0), (16, 3.0)],
    [(6, -2.0), (8, -2.0), (14, 9.0), (16, 9.0)],
    [(12, 4.0)],
])
def test_alte_funktion_behaelt_tupelform_und_dasselbe_max_ts(stunden_werte):
    """AC-26: ``hiking_field_min_max`` liefert für seine 7 Aufrufstellen
    unverändert ``(min, max, max_ts)``; ``max_ts`` ist dasselbe wie in der
    Schwesterfunktion (auch bei Gleichstand)."""
    from output.renderers.day_window import hiking_field_min_max, hiking_field_min_max_ts
    pts = _punkte(stunden_werte)
    alt = hiking_field_min_max(pts, "t2m_c")
    neu = hiking_field_min_max_ts(pts, "t2m_c")
    assert len(alt) == 3
    assert alt == (neu[0], neu[1], neu[3])


# ---------------------------------------------------------------------------
# 3. Signaturlücken: Preset als Pflichtparameter, Aufrufer reichen durch
# ---------------------------------------------------------------------------

def _pflicht_keyword_only(fn, name: str) -> None:
    sig = inspect.signature(fn)
    assert name in sig.parameters, f"{fn.__qualname__} kennt keinen Parameter {name!r}"
    p = sig.parameters[name]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY, f"{fn.__qualname__}({name}) nicht keyword-only"
    assert p.default is inspect.Parameter.empty, (
        f"{fn.__qualname__}({name}) hat einen Default — ein vergessenes "
        "Durchreichen fiele in 4b still auf „allgemein\"")


def test_vergleichs_klartext_verlangt_das_preset():
    from output.renderers.comparison import render_comparison_text
    _pflicht_keyword_only(render_comparison_text, "preset")


@pytest.mark.parametrize("methode", [
    "send_multi_location_deviation_alert",
    "send_multi_location_radar_alert",
    "send_location_deviation_alert",
])
def test_vergleichs_alarme_verlangen_das_preset(methode):
    from services.notification_service import NotificationService
    _pflicht_keyword_only(getattr(NotificationService, methode), "preset")


def _aufrufe(datei: Path, funktion: str, aufgerufen: str) -> list[ast.Call]:
    """Alle Aufrufe ``aufgerufen(...)`` innerhalb der Funktion ``funktion``
    (Funktion ``"*"`` = ganze Datei)."""
    baum = ast.parse(datei.read_text(encoding="utf-8"), filename=str(datei))
    wurzeln = [baum] if funktion == "*" else [
        n for n in ast.walk(baum)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == funktion
    ]
    assert wurzeln, f"{funktion} nicht in {datei}"
    funde = []
    for w in wurzeln:
        for n in ast.walk(w):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if name == aufgerufen:
                    funde.append(n)
    return funde


def _reicht_durch(call: ast.Call, kw: str, quelle: str | None = None) -> bool:
    for k in call.keywords:
        if k.arg == kw:
            return quelle is None or (isinstance(k.value, ast.Name) and k.value.id == quelle)
    return False


@pytest.mark.parametrize("datei,funktion,aufgerufen,quelle", [
    # render_compare_email reicht sein Preset an den Klartext weiter
    ("output/renderers/comparison.py", "render_compare_email", "render_comparison_text", "preset"),
    # der Ein-Ort-Wrapper reicht sein Preset an den Mehr-Orte-Versand weiter
    ("services/notification_service.py", "send_location_deviation_alert",
     "send_multi_location_deviation_alert", "preset"),
    # die Ortsvergleich-Alarme haben das Preset im Scope und reichen es durch
    ("services/compare_alert.py", "*", "send_multi_location_deviation_alert", "preset"),
    ("services/compare_radar_alert.py", "*", "send_multi_location_radar_alert", "preset"),
])
def test_aufrufer_reichen_das_preset_durch(datei, funktion, aufgerufen, quelle):
    """§5 Punkt 1: die Aufrufer übergeben in 4a das Preset (aufgelöst wird
    dort noch ``None``, erst 4b löst auf)."""
    funde = _aufrufe(_SRC / datei, funktion, aufgerufen)
    assert funde, f"kein Aufruf {aufgerufen} in {datei}:{funktion}"
    ohne = [c.lineno for c in funde if not _reicht_durch(c, "preset", quelle)]
    assert ohne == [], f"{datei}: {aufgerufen} ohne preset={quelle} in Zeile {ohne}"


# ---------------------------------------------------------------------------
# 4. Ausblick: expliziter Zweig-Parameter statt `trip_display_config is None`
# ---------------------------------------------------------------------------

def _gewitter_tag_nacht_fall():
    """Aggregat sagt „hoch", die Gewitterstunde liegt aber nachts (0 Uhr UTC),
    im Tagesfenster ist keine: der Trip-Zweig zeigt „–", der
    Ortsvergleichs-Zweig behält das Aggregat „hoch"."""
    from app.models import ForecastDataPoint, SegmentWeatherSummary, ThunderLevel
    summary = SegmentWeatherSummary(
        temp_min_c=9.4, temp_max_c=21.6, precip_sum_mm=3.5,
        wind_max_kmh=28.0, thunder_level_max=ThunderLevel.HIGH, pop_max_pct=60,
    )
    points = [
        ForecastDataPoint(ts=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
                          gust_kmh=42.0, thunder_level=ThunderLevel.HIGH,
                          precip_1h_mm=1.5, wind10m_kmh=22.0),
        ForecastDataPoint(ts=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
                          gust_kmh=30.0, thunder_level=ThunderLevel.NONE,
                          precip_1h_mm=0.0, wind10m_kmh=15.0),
    ]
    return summary, points


_THUNDER_SPALTE = [{"metric_id": "thunder", "aggregation": "max"}]


def test_ausblick_verlangt_den_zweig_ausdruecklich():
    from output.renderers.email.outlook import _outlook_row, build_outlook_row
    _pflicht_keyword_only(build_outlook_row, "context")
    _pflicht_keyword_only(_outlook_row, "context")


def test_route_ohne_display_config_waehlt_trotzdem_den_trip_zweig():
    """§5 Punkt 2: ein Trip ohne ``display_config`` darf nicht still in den
    Ortsvergleichs-Zweig fallen."""
    from output.renderers.email.outlook import build_outlook_row
    summary, points = _gewitter_tag_nacht_fall()
    row = build_outlook_row(
        summary, points, "Mo", ZoneInfo("Europe/Berlin"),
        metrics=_THUNDER_SPALTE, outlook_metric_formats={},
        trip_display_config=None, context="route",
    )
    assert row["cells"] == ["–"], row["cells"]


def test_vergleich_behaelt_das_aggregat_auch_mit_display_config():
    """Gegenprobe: der Zweig folgt dem Parameter, nicht dem ``dc``."""
    from output.renderers.email.outlook import build_outlook_row
    summary, points = _gewitter_tag_nacht_fall()
    row = build_outlook_row(
        summary, points, "Mo", ZoneInfo("Europe/Berlin"),
        metrics=_THUNDER_SPALTE, outlook_metric_formats={},
        trip_display_config=object(), context="vergleich",
    )
    assert row["cells"] == ["hoch"], row["cells"]


def test_unbekannter_zweig_scheitert_laut():
    from output.renderers.email.outlook import build_outlook_row
    summary, points = _gewitter_tag_nacht_fall()
    with pytest.raises(ValueError):
        build_outlook_row(
            summary, points, "Mo", ZoneInfo("Europe/Berlin"),
            metrics=_THUNDER_SPALTE, outlook_metric_formats={}, context="trip",
        )


@pytest.mark.parametrize("datei,funktion,aufgerufen,zweig", [
    ("services/trip_report_scheduler.py", "*", "build_outlook_row", "route"),
    ("output/renderers/email/compare_html.py", "*", "_outlook_row", "vergleich"),
])
def test_produktive_aufrufer_nennen_ihren_zweig(datei, funktion, aufgerufen, zweig):
    funde = _aufrufe(_SRC / datei, funktion, aufgerufen)
    assert funde, f"kein Aufruf {aufgerufen} in {datei}"
    falsch = [
        c.lineno for c in funde
        if not any(k.arg == "context" and isinstance(k.value, ast.Constant) and k.value.value == zweig
                   for k in c.keywords)
    ]
    assert falsch == [], f"{datei}: {aufgerufen} ohne context={zweig!r} in Zeile {falsch}"


# ---------------------------------------------------------------------------
# 5. Katalogschlüssel der 7 Vorlagen-Labels (AC-15 Nachtrag, ADR-0104)
# ---------------------------------------------------------------------------

def _mail_katalog(lang: str) -> dict:
    return json.loads((_SRC / "i18n" / "messages" / lang / "mail.json").read_text(encoding="utf-8"))


def _schluessel(template_id: str) -> str:
    return "mail.vorlage." + template_id.replace("-", "_")


def test_jede_eingebaute_vorlage_hat_ein_label_in_beiden_sprachen():
    from app.ampel_templates import AMPEL_TEMPLATES
    from app.metric_catalog import WEATHER_TEMPLATES
    assert set(AMPEL_TEMPLATES) == set(WEATHER_TEMPLATES)  # Selbsttest der Quelle
    de, en = _mail_katalog("de"), _mail_katalog("en")
    for tid, daten in WEATHER_TEMPLATES.items():
        key = _schluessel(tid)
        assert de.get(key) == daten["label"], f"{key}: DE muss wortgleich zu WEATHER_TEMPLATES sein"
        assert (en.get(key) or "").strip(), f"{key}: EN-Label fehlt"
    vorhanden = {k for k in de if k.startswith("mail.vorlage.")}
    assert vorhanden == {_schluessel(t) for t in WEATHER_TEMPLATES}
    assert {k for k in en if k.startswith("mail.vorlage.")} == vorhanden


def test_vorlagen_label_kommt_in_der_nutzersprache():
    from i18n import t
    assert t("mail.vorlage.alpen_trekking", "de") == "Alpen-Trekking"
    en = t("mail.vorlage.alpen_trekking", "en")
    assert en and en != "mail.vorlage.alpen_trekking"
    assert t("mail.vorlage.allgemein", "de") == "Allgemein"


def test_eine_stelle_bildet_den_label_schluessel_fuer_jede_vorlage():
    """Kein Leser bildet den Schlüssel selbst: für jede eingebaute Vorlage
    (auch ``alpen-trekking`` mit Bindestrich) liefert die Abbildung einen
    Schlüssel, den der Katalog in DE und EN kennt."""
    from app.ampel import vorlage_label_schluessel
    from app.metric_catalog import WEATHER_TEMPLATES
    from i18n import t
    de, en = _mail_katalog("de"), _mail_katalog("en")
    for tid, daten in WEATHER_TEMPLATES.items():
        key = vorlage_label_schluessel(tid)
        assert key in de and key in en, (tid, key)
        assert t(key, "de") == daten["label"]
        assert t(key, "en") == en[key]
    assert vorlage_label_schluessel("alpen-trekking") == "mail.vorlage.alpen_trekking"


def test_label_schluessel_fuer_unbekannte_vorlage_scheitert_laut():
    """Eine unbekannte ID ist ein Programmierfehler (aufgelöst wird vorher
    über ``resolve_ampel``, das unbekannte IDs schon auf „allgemein" setzt)."""
    from app.ampel import vorlage_label_schluessel
    with pytest.raises(KeyError):
        vorlage_label_schluessel("gibt-es-nicht")
