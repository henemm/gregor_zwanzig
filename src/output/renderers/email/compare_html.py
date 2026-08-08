"""Compare-Email HTML-Renderer v2 (Issue #1110).

Pure Function ``render_compare_html()`` — analog zu ``html.py`` (Trip-Mail).

v2-Layout (loest Score/Winner-Vertrag aus #253 ab, s. #1108):
- Kein Score/Ranking/Winner-Card mehr — Orte in der vom Nutzer konfigurierten
  Preset-Reihenfolge (Issue #1359 Scheibe 2, `location_render_order`; loest die
  alphabetische Sortierung des PO-Updates 2026-07-08 ab).
- Uebersichtstabelle: Metriken als Zeilen x Orte als Spalten, inkl. Warn-Zeile
  mit Kuerzel-Chips je Ort (``CV2_METRICS``). KEIN Best-Wert-Highlight (Adversary
  F001, PO-Entscheidung) -- Zellfaerbung ausschliesslich ueber die Risk-Skala.
- Warn-Lead-Block (Akzent-Bar) nur wenn mindestens ein Ort eine amtliche
  Warnung hat.
- Stundentabellen fuer ALLE Orte (nicht nur Top-N), mit Langform-Warn-Streifen
  (wiederverwendet ``render_official_alerts_html``, ADR-0011).
- Inline-CSS only (Outlook-kompatibel), kein CSS-Grid/Flexbox.
- ``@media (max-width: 480px)`` Block fuer Mobile-Layout (Header-Stats).

SPEC: docs/specs/modules/issue_1110_compare_mail_v2.md
"""
from __future__ import annotations

import html as _html
from datetime import date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from app.metric_catalog import aggregation_label_de, get_metric
from app.models import Corridor, ThunderLevel
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.compare_hourly_metric_ids import (
    HOURLY_DEFAULT_METRIC_IDS, HOURLY_MERGE_ONLY_METRIC_IDS,
    hourly_selectable_metric_ids,
)
from output.renderers.compare_metric_ids import (
    CORRIDOR_METRIC_TO_HOUR_KEY, FRONTEND_TO_RENDERER_METRIC_ID,
)
from output.renderers.email.corridor_mark import (
    MARK_BORDER as _MARK_BORDER, is_marked as _is_marked,
    mark_cell_style as _mark_cell_style, mark_lookup as _mark_lookup,
)
from output.renderers.email.design_tokens import (
    FONT_DATA, FONT_UI, G_ACCENT, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4,
    G_BOX_WARNING_BG, G_INK, G_INK_FAINT, G_INK_MUTED, G_PAPER, G_SUCCESS,
    G_WARNING, WEB_FONT_LINK, tone_css,
)
from output.renderers.email.outlook import build_outlook_row, render_outlook_table
from output.renderers.email.profile_signature import profile_signature
from output.metric_format import (
    THUNDER_LABEL_DE, format_value, severity_for, thunder_ampel_band,
)
from utils.geo import degrees_to_compass
from utils.timezone import (
    UTC, local_dt, local_hour, local_stamp, location_tz, tz_abbrev,
)
from output.renderers.alert.official_alerts import (
    _LEVEL_WORDS, OfficialAlertNotice, official_alert_source_label,
    render_official_alerts_html, render_warn_block,
)


# ---------------------------------------------------------------------------
# Risk-Skala + Metrik-Katalog (1:1 aus docs/design-requests/compare_mail_v2/
# screen-compare-email-v2.jsx uebernommen)
# ---------------------------------------------------------------------------

# Issue #1377 Scheibe B2: Compare-lokales Ampel-Vokabular (ok/caution/warn/danger)
# ist 1:1 kompatibel zum kanonischen (green/yellow/orange/red), das
# `severity_for()` liefert. Die Uebersetzung geschieht direkt in jeder
# `_sev_*`-Funktion (`_LEVEL_TO_COMPARE`, s.u.) -- ein zweiseitiges
# Uebersetzungs-Dict an den Aufrufstellen entfaellt, weil dort inzwischen
# ausschliesslich das kanonische Vokabular ankommt (`severity_for` direkt an
# `tone_css` durchgereicht).
_LEVEL_TO_COMPARE = {"green": "ok", "yellow": "caution", "orange": "warn", "red": "danger"}
_COMPARE_TO_LEVEL = {v: k for k, v in _LEVEL_TO_COMPARE.items()}


def _to_compare(level: str | None) -> str | None:
    """Kanonisches `severity_for`-Level -> Compare-lokales Vokabular.

    Issue #1377 Scheibe B2 (harte Vorgabe): KEIN `.get(level, "ok")`-Rueckfall
    -- `None` ("keine Aussage", z.B. Metrik ohne Katalog-Schwellen) bleibt
    `None` und wird NIE stillschweigend zu "ok"/gruen. Aufrufer behandeln
    `None` wie "ok" (keine Toenung), s. `_render_overview_row`/`_render_hour_row`.
    """
    return _LEVEL_TO_COMPARE[level] if level is not None else None


# Issue #1214 Scheibe 2: Zell-Toenung stammt aus der zentralen tone_css-Palette
# (design_tokens), nicht mehr aus einem lokal duplizierten Mapping. _RISK_CELL
# bleibt als abgeleiteter Kompat-Alias erhalten (registrierte Konsumenten +
# Regressionstest test_official_alert_badge_color.py locken diese Werte); es ist
# ab jetzt nur noch eine Ableitung von tone_css, keine eigene Farbquelle mehr.
_RISK_CELL = {
    "caution": tone_css("yellow"),
    "warn": tone_css("orange"),
    "danger": tone_css("red"),
}
_INFO_CELL = ("#dde8f3", "#1e3a5f")

# Issue #1056 v2.0: Warn-Chip-Zellfarbe je amtlicher Warnstufe (bg-Tint, fg) --
# eigene Map, harmonisch zu den Badge-Rand-Farben, NICHT die Metrik-Palette
# _RISK_CELL (die bleibt fuer Temp/Wind/etc. unveraendert).
_ALERT_LEVEL_CELL = {
    1: ("#dbeadd", G_SUCCESS),
    2: ("#f2e4b0", G_ALERT_L2),
    3: ("#f4d3c6", G_ALERT_L3),
    4: ("#e4d7f5", G_ALERT_L4),
}


def _sev_temp(v: float) -> str:
    # Issue #1377 Scheibe B2: nutzt die Katalog-Schwellen (Hitze 28/31/34 UND,
    # seit Scheibe A neu, Kaelte 0/-5/-15) via severity_for statt der
    # bisherigen rein hitzeseitigen Handschwelle. Bewusst gewollte Folge:
    # die Kaelte-Seite (z.B. -6°C -> "warn") wird in der Vergleichsmatrix
    # jetzt erstmals sichtbar, identisch zum Trip-Briefing.
    return _to_compare(severity_for("temperature", v))


def _sev_wind(v: float) -> str:
    # Issue #1214 Scheibe 2 (Wind-Schwellen-Angleichung, AC-3): nutzt die
    # Katalog-Schwellen (wind.display_thresholds={yellow:30,orange:50,red:70})
    # via severity_for statt der bislang hartcodierten >40/>30/>20. Sichtbare,
    # bewusst gewollte Folge: 45 km/h zeigt jetzt gelb (caution) statt rot
    # (danger) — identisch zum Trip-Briefing (helpers.ampel_level).
    return _to_compare(severity_for("wind", v))


def _sev_gust(v: float) -> str:
    # Issue #1377 Scheibe B2: Katalog-Schwellen (30/45/60) via severity_for
    # statt hartcodierter Handschwellen. Die drei Zahlen waren bereits
    # deckungsgleich, aber die Grenz-Inklusivitaet nicht (Katalog wertet
    # via `>=` ab EINSCHLIESSLICH der Schwelle, die bisherige Handschwelle
    # war exklusiv `>`) -- genau 30 km/h faerbt jetzt "caution" statt "ok".
    return _to_compare(severity_for("gust", v))


def _sev_rain(v: float) -> str:
    return _to_compare(severity_for("precipitation", v))


def _sev_uv(v: float) -> str:
    return _to_compare(severity_for("uv_index", v))


def _sev_pop(v: float) -> str:
    return _to_compare(severity_for("rain_probability", v))


def _sev_visibility(v: float) -> str:
    """v in Metern -- niedrige Sicht ist kritischer (Katalog-Schwellen
    <2000/<1000/<500m via severity_for statt der bisherigen <5000/<3000/<1000m)."""
    return _to_compare(severity_for("visibility", v))


def _sev_cape(v: float) -> str:
    return _to_compare(severity_for("cape", v))


_WEEKDAY_ABBR = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Format-Vorbild html.py:1160-1161 -- lokale Kopie statt Import (eigenstaendiges
# Compare-Vokabular, s. Spec-Modul-Docstring), NONE rendert als "—" (kein Wert).
# Issue #1474: LOW-Zeile ergaenzt; MED/HIGH-Woerter aus der geteilten Quelle
# (metric_format.THUNDER_LABEL_DE) -- NUR NONE bleibt lokal ("—" statt "kein").
_THUNDER_LEVEL_LABEL = {
    "NONE": "—",
    "LOW": THUNDER_LABEL_DE["LOW"],
    "MED": THUNDER_LABEL_DE["MED"],
    "HIGH": THUNDER_LABEL_DE["HIGH"],
}
# Issue #1491: die Ordnung stammt jetzt aus der EINEN geteilten Zuordnung
# (metric_format.thunder_ampel_band) statt aus einem eigenen Woerterbuch --
# uebersetzt ueber dieselbe _LEVEL_TO_COMPARE-Palette wie die anderen
# Ampel-Metriken (green->ok, yellow->caution, orange->warn, red->danger).
# Aussehen des Ortsvergleichs bleibt dadurch unveraendert (Spec AC-7).


def _fmt_deg(v) -> str:
    return f"{v:.0f}°" if v is not None else "—"


def _fmt_kmh(v) -> str:
    return f"{v:.0f}" if v is not None else "—"


def _fmt_rain(v) -> str:
    return f"{v:.1f}" if v else "·"


def _fmt_uv(v) -> str:
    return f"{v:.0f}" if v is not None else "—"


def _fmt_pop(v) -> str:
    return f"{v:.0f}%" if v is not None else "—"


def _fmt_visibility(v) -> str:
    # Issue #1237 (AC-2): nur der Zahlenwert -- die Einheit steht in der
    # Einheiten-Legende unter den Stundentabellen (analog Trip-Briefing).
    return f"{v / 1000:.1f}" if v is not None else "—"


def _fmt_thunder(v, hail: Optional[bool] = None) -> str:
    """Gewitterstufen-Label des Ortsvergleichs.

    Issue #1475 Nachbesserung (Punkt 5a): ``hail`` ist ADDITIV mit Default
    ``None`` — Alt-Aufrufer mit EINEM Argument bleiben zeichengleich
    (``format_hail_note(None)`` liefert nichts). Nur bei bestaetigtem Hagel
    (``True``) haengt der rein deskriptive Zusatz an (ADR-0007, kein Rat).
    Die Stufe ``v`` selbst wird davon NIE beeinflusst (AC-10).
    """
    if v is None:
        return "—"
    key = v.value if hasattr(v, "value") else str(v)
    label = _THUNDER_LEVEL_LABEL.get(key, "—")
    from output.metric_format import format_hail_note
    note = format_hail_note(hail)
    return f"{label} · {note}" if note else label


def _sev_thunder(v):
    # Issue #1491 Fix: `NONE` bleibt im Ortsvergleich bewusst UNMARKIERT
    # (anders als die Trip-Stundentabelle, die dafuer einen gruenen Punkt
    # zeigt) -- eigene Produktentscheidung, kein Versehen. LOW/MED/HIGH
    # teilen weiterhin die eine Ampelband-Quelle (`thunder_ampel_band`).
    if v is None or v == ThunderLevel.NONE:
        return None
    return _to_compare(thunder_ampel_band(v))


def _sev_rain_safe(v) -> str:
    return _sev_rain(v or 0.0)


_PRECIP_TYPE_LABEL = {
    "RAIN": "Regen",
    "SNOW": "Schnee",
    "MIXED": "Mischniederschlag",
    "FREEZING_RAIN": "Eisregen",
}


def _fmt_precip_type(v) -> str:
    """Niederschlagsart-TAGESWERT (Issue #1324): PrecipType-Enum -> deutsches
    Label, analog ``_fmt_thunder``."""
    if v is None:
        return "—"
    key = v.value if hasattr(v, "value") else str(v)
    return _PRECIP_TYPE_LABEL.get(key, "—")


def _fmt_visibility_overview(v) -> str:
    """Sicht-TAGESWERT der Uebersichts-Matrix (Issue #1285).

    Nutzt die bestehende Compare-Darstellung (`_fmt_visibility`: Meter -> km,
    eine Nachkommastelle) und haengt die Einheit an -- anders als die
    Stundentabelle hat die Uebersicht keine Einheiten-Legende unter sich, in
    der "km" sonst stuende. Der zugrundeliegende Wert bleibt der Trip-Wert in
    Metern (AC-15), nur die Anzeige ist compare-typisch.
    """
    return f"{_fmt_visibility(v)} km" if v is not None else "—"


# Issue #1214 Scheibe 2: "metric_id" verweist auf den Katalog-Eintrag
# (metric_catalog._METRICS) und ist die dokumentierte Verbindung fuer die
# Konsolidierung. In dieser Scheibe wird nur wind ueber severity_for/Katalog
# gefahren (Wind-45-Fix); die uebrigen Severity-/Format-Helfer bleiben lokal,
# weil der Katalog fuer sie KEINE aequivalenten display_thresholds/decimals
# bereitstellt (s. Report-Auffaelligkeit) und ein Umstellen sonst still das
# Rendering aendern wuerde. Die metric_id-Felder bereiten Scheibe 3+ vor.
#
# Issue #1285: precip_sum/pop_max/thunder_max/visibility_min sind NEU -- ihre
# Auswahl wurde bis 2026-07-16 STILL verworfen, weil es die Zeile gar nicht
# gab. "fmt" (optional) ersetzt die Zahl+Einheit-Standardformatierung
# `_fmt_metric` -- noetig fuer Nicht-Zahlwerte (Gewitter ist ein
# ThunderLevel-Enum und kracht in `f"{value:.0f}"` mit TypeError) und fuer die
# m->km-Umrechnung der Sicht. Zeilen OHNE "fmt" verhalten sich unveraendert.
# Issue #1401 Scheibe A2a: JEDE Metrik-Zeile nennt jetzt ihre zentrale
# Wettergroesse ("metric_id", src/app/metric_catalog.py) UND die gezeigte
# Auswertung ("aggregation" -- Schluessel aus deren `summary_fields`). Die
# Paare sind aus dem bereits kuratierten Compare-Katalog
# (output/renderers/compare_metric_catalog.py) uebernommen, nicht neu erfunden.
# Vollstaendig haelt die Verknuepfung der Waechter
# tests/unit/test_compare_mail_metric_link_completeness.py -- er schlaegt an,
# sobald eine neue Zeile ohne Verknuepfung dazukommt (Bug-Typ #1296/#1324).
# Issue #1401 Scheibe A2b: das getippte "label" ist ENTFALLEN -- die
# Beschriftung wird zur Renderzeit aus dem Register abgeleitet
# (`derive_row_labels`, s.u.). Nur die Warn-Zeile traegt weiter einen festen
# Text, weil sie keine Wettergroesse ist.
CV2_METRICS = [
    {"key": "warn", "label": "Amtliche Warnungen", "kind": "warn"},
    {"key": "temp_max", "metric_id": "temperature", "aggregation": "max",
     "unit": "°C", "sev": _sev_temp},
    {"key": "wind_max", "metric_id": "wind", "aggregation": "max",
     "unit": "km/h", "sev": _sev_wind},
    {"key": "precip_sum", "metric_id": "precipitation", "aggregation": "sum",
     "unit": "mm", "decimals": 1, "sev": _sev_rain},
    {"key": "pop_max", "metric_id": "rain_probability", "aggregation": "max",
     "unit": "%", "sev": _sev_pop},
    {"key": "thunder_max", "metric_id": "thunder", "aggregation": "max",
     "fmt": _fmt_thunder, "sev": _sev_thunder},
    {"key": "sunny_hours", "metric_id": "sunshine", "aggregation": "sum",
     "unit": "h", "decimals": 1},
    {"key": "cloud_avg", "metric_id": "cloud_total", "aggregation": "avg",
     "unit": "%"},
    {"key": "uv_max", "metric_id": "uv_index", "aggregation": "max",
     "unit": "", "sev": _sev_uv},
    {"key": "visibility_min", "metric_id": "visibility", "aggregation": "min",
     "fmt": _fmt_visibility_overview, "sev": _sev_visibility},
    {"key": "snow_depth_cm", "metric_id": "snow_depth", "aggregation": "max",
     "unit": "cm"},
    {"key": "snow_new_cm", "metric_id": "fresh_snow", "aggregation": "sum",
     "unit": "cm"},
    # Issue #1296: vier weitere bis 2026-07-17 STILL verworfene Zeilen (analog
    # #1285). freezing_level ohne "sev" (kein AC verlangt Faerbung, s. Spec
    # Known Limitations). cape_max bekam mit Issue #1298 (B2) eine
    # Ampel-Faerbung ueber _sev_cape. Issue #1377 Scheibe B2: temp_min bekommt
    # jetzt ebenfalls "sev" (_sev_temp) -- der Katalog fuehrt fuer
    # "temperature" seit Scheibe A beidseitige Schwellen (Hitze UND Kaelte),
    # `severity_for` wertet beide Richtungen aus und liefert fuer einen
    # Tiefstwert automatisch die Kaelte-Seite. Ohne diese Verdrahtung bliebe
    # die Kaelte-Warnung in der Vergleichsmatrix unsichtbar (AC-5).
    {"key": "temp_min", "metric_id": "temperature", "aggregation": "min",
     "unit": "°C", "sev": _sev_temp},
    {"key": "gust_max", "metric_id": "gust", "aggregation": "max",
     "unit": "km/h", "sev": _sev_gust},
    {"key": "cape_max", "metric_id": "cape", "aggregation": "max",
     "unit": "J/kg", "sev": _sev_cape},
    {"key": "freezing_level", "metric_id": "freezing_level", "aggregation": "min",
     "unit": "m"},
    # Issue #1324: zehn weitere additive Zeilen (keine Severity-Faerbung, s.
    # Spec Known Limitations). Klasse A (Renderer-ID = LocationResult-Feld):
    {"key": "wind_direction_avg", "metric_id": "wind_direction", "aggregation": "avg",
     "unit": "°"},
    {"key": "wind_chill_min", "metric_id": "wind_chill", "aggregation": "min",
     "unit": "°C"},
    {"key": "wind_chill_max", "metric_id": "wind_chill", "aggregation": "max",
     "unit": "°C"},
    {"key": "cloud_low_avg", "metric_id": "cloud_low", "aggregation": "avg",
     "unit": "%"},
    {"key": "cloud_mid_avg", "metric_id": "cloud_mid", "aggregation": "avg",
     "unit": "%"},
    {"key": "cloud_high_avg", "metric_id": "cloud_high", "aggregation": "avg",
     "unit": "%"},
    # Klasse B (Live-Aggregat ueber _DAILY_AGGREGATE_FIELD):
    {"key": "humidity_avg", "metric_id": "humidity", "aggregation": "avg",
     "unit": "%"},
    {"key": "dewpoint_avg", "metric_id": "dewpoint", "aggregation": "avg",
     "unit": "°C"},
    {"key": "pressure_avg", "metric_id": "pressure", "aggregation": "avg",
     "unit": "hPa"},
    {"key": "precip_type", "metric_id": "precip_type", "aggregation": "max",
     "fmt": _fmt_precip_type},
    {"key": "snowfall_limit", "metric_id": "snowfall_limit", "aggregation": "min",
     "unit": "m"},
]


# Issue #1106: ersetzt _HOUR_COLUMNS -- 9 konfigurierbare Wert-Spalten,
# kanonische Reihenfolge (AC-8). "Zeit" ist keine Metrik hier, sondern fest
# verdrahtete erste Spalte in _render_hour_row/_render_hour_table.
#
# Issue #1401 Scheibe A2b: kein getipptes "label" mehr -- die Spaltenueberschrift
# UND die Einheiten-Legende darunter kommen aus `derive_row_labels()`.
#
# Issue #1406 Scheibe B: die Spaltenliste wird nicht mehr getippt, sondern aus
# dem zentralen Register ABGELEITET (`hourly_selectable_metric_ids()`) --
# abzueglich des Merge-Signals Windrichtung (keine eigene Spalte) und der
# ausdruecklich ausgenommenen Groessen (AC-11, `HOURLY_EXCLUDED_METRIC_IDS`).
# Damit gibt es keine zehnte Handkopie des Vokabulars mehr.
#
# Formatierung: Standard ist der geteilte, katalog-getriebene
# `format_value(metric_id, wert, style="bare")` -- reine Zahl ohne Einheit,
# weil die Einheit in der Legende unter der Tabelle steht. Die
# `_HOUR_FMT_OVERRIDES` unten halten NUR die Faelle, in denen die
# Compare-Stundendarstellung bewusst abweicht: die beiden Enum-Groessen
# (Gewitter/Niederschlagsart lassen sich nicht runden) und die sechs
# historischen Darstellungen der Bestandsspalten, die zeichengleich bleiben
# muessen (AC-4).
_HOUR_FMT_OVERRIDES = {
    "temperature": _fmt_deg,
    "wind_chill": _fmt_deg,
    "wind": _fmt_kmh,
    "gust": _fmt_kmh,
    "precipitation": _fmt_rain,
    "uv_index": _fmt_uv,
    "rain_probability": _fmt_pop,
    "visibility": _fmt_visibility,
    "thunder": _fmt_thunder,       # Enum -- nicht generisch rundbar
    "precip_type": _fmt_precip_type,  # Enum -- dito
}
# Ampel-Ausnahmen. ``None`` heisst AUSDRUECKLICH "keine Faerbung" -- die
# gefuehlte Temperatur traegt zwar Katalog-Schwellen, blieb in der
# Stundentabelle aber seit jeher ungetoent; das bleibt so (AC-4, kein stiller
# Anzeigewechsel fuer Bestands-Vergleiche).
_HOUR_SEV_OVERRIDES: dict[str, object] = {
    "wind_chill": None,
    "precipitation": _sev_rain_safe,  # None/0 sollen dieselbe Stufe liefern
    "thunder": _sev_thunder,          # Enum statt Zahl
}


def _make_hour_fmt(metric_id: str):
    """Generischer Zellen-Formatierer einer Stundenspalte (Named Factory statt
    Inline-Closure -- eine Funktion je Groesse, kein Spaetbindungs-Fehler)."""
    def fmt(value) -> str:
        return format_value(metric_id, value, style="bare")
    return fmt


def _make_hour_sev(metric_id: str):
    """Generische Ampel einer Stundenspalte -- dieselbe Formel wie im Trip
    (`severity_for`), uebersetzt ins Compare-Vokabular."""
    def sev(value):
        return _to_compare(severity_for(metric_id, value))
    return sev


_UNSET = object()  # "nicht in den Ausnahmen genannt" != "ausdruecklich keine Ampel"


def _build_hour_metrics() -> list[dict]:
    rows: list[dict] = []
    for metric_id in hourly_selectable_metric_ids():
        if metric_id in HOURLY_MERGE_ONLY_METRIC_IDS:
            continue
        metric = get_metric(metric_id)
        row = {
            "key": metric.dp_field,
            "metric_id": metric_id,
            "fmt": _HOUR_FMT_OVERRIDES.get(metric_id) or _make_hour_fmt(metric_id),
        }
        sev = _HOUR_SEV_OVERRIDES.get(metric_id, _UNSET)
        if sev is _UNSET and metric.display_thresholds:
            # Ohne Katalog-Schwellen KEINE Ampel verdrahten -- sonst uebersetzte
            # "keine Aussage" in ein stilles Gruen (tests/tdd/
            # test_compare_katalog_schwellen.py).
            sev = _make_hour_sev(metric_id)
        if sev is not None and sev is not _UNSET:
            row["sev"] = sev
        rows.append(row)
    return rows


HOUR_METRICS = _build_hour_metrics()


def derive_row_labels(rows: list[dict], form: str = "short") -> list[dict]:
    """Issue #1401 Scheibe A2b: Beschriftung der Mail-Tabellenzeilen aus dem
    zentralen Wetter-Namensregister ableiten statt sie zu tippen.

    Issue #1453 (PO-Regel "Form folgt Platz"): dieselbe Ableitung liefert ZWEI
    Formen, je nachdem wieviel Platz die Zielstelle hat --

    * ``form="short"`` (Vorgabe): die englische Fachkurzform ``col_label``.
      Das ist die Stundentabelle (bis 22 Spalten, harte Platzgrenze) und die
      Einheiten-Legende darunter.
    * ``form="long"``: der ausgeschriebene deutsche Registername ``label_de``.
      Das ist die Uebersichtstabelle (Zeilenkopf, praktisch unbegrenzt Platz)
      -- im HTML-Teil wie im Klartext-Teil derselben Mail.

    Kommt dieselbe Form innerhalb der uebergebenen (= aktuell sichtbaren)
    Zeilenmenge mehrfach vor, waeren die Zeilen ununterscheidbar -- dann haengt
    jede betroffene Zeile ihre Auswertung an. Der Zusatz folgt der Form: kurz
    der rohe Auswertungsschluessel ("Temp max"), lang die deutsche Auswertung
    ``aggregation_label_de`` ("Temperatur Maximum") -- genau wie im bereits
    deutschen 3-Tages-Ausblick (``compare_outlook_metric_ids.py:110-115``).

    Zeilen ohne ``metric_id`` (Warn-Zeile) behalten ihren festen Text.
    Rueckgabe sind KOPIEN -- die Modul-Konstanten bleiben unberuehrt.

    Ein unbekannter ``form``-Wert ist ein ``ValueError``, KEIN stiller Rueckfall
    auf die Kurzform (Adversary F001, #1453). Begruendung ist ein Muster, das in
    dieser Sitzung viermal auftrat: ein fehlender oder unbekannter Parameter
    faellt lautlos auf einen Standardwert zurueck, und die Mail sieht danach
    plausibel aus, obwohl sie das Falsche zeigt -- ``build_token_line()`` ohne
    ``profile`` (Wintersport-Token erschienen nie, #1450),
    ``render_compare_html()`` ohne ``hourly_metrics`` (Vorschau zeigte immer
    alle Spalten), ``_visible_hour_metrics(None)`` als "alle Spalten" (haette
    Bestandsvergleiche ungefragt von 9 auf 22 Spalten springen lassen). Ein
    Tippfehler ("Long", "lang") wuerde hier die ganze Uebersichtstabelle
    unbemerkt wieder englisch beschriften -- genau die Regression, die diese
    Lieferung behebt. Deshalb laut scheitern.
    """
    if form not in ("short", "long"):
        raise ValueError(
            f"derive_row_labels: unbekannte Namensform {form!r} -- zulaessig "
            f"sind nur 'short' (englische Kurzform, Stundentabelle) und 'long' "
            f"(ausgeschriebener deutscher Registername, Uebersichtstabelle)"
        )
    lang = form == "long"

    def _base(row: dict) -> str:
        if not row.get("metric_id"):
            return row.get("label", "")
        metric = get_metric(row["metric_id"])
        return metric.label_de if lang else metric.col_label

    labels = [_base(row) for row in rows]
    mehrfach = {label for label in labels if labels.count(label) > 1}
    out = []
    for row, label in zip(rows, labels):
        if label in mehrfach and row.get("aggregation"):
            zusatz = row["aggregation"]
            if lang:
                zusatz = aggregation_label_de(zusatz) or zusatz
            label = f"{label} {zusatz}"
        out.append({**row, "label": label})
    return out


# ---------------------------------------------------------------------------
# Korridor-mark-Markierung (Issue #1231, Slice 7, AC-19) — rein additive
# Anzeige-Signatur neben der bestehenden Severity-Faerbung. AC-20: wirkt
# ausschliesslich hier im Renderer, calculate_score() bleibt unberuehrt.
# Issue #1425 Schritt 1: die Bausteine (_mark_lookup/_is_marked/_MARK_BORDER/
# _mark_cell_style) liegen jetzt in corridor_mark.py (s. Modul-Import oben) --
# geteilt mit dem Trip-Renderer, kein zweiter Nachbau.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Warn-Kürzel-Mapping (dünner Anzeige-Layer über OfficialAlert.hazard)
# ---------------------------------------------------------------------------

def _warn_short(alert) -> tuple[str, str]:
    """(Kuerzel-Text, Severity) je hazard. Fallback: alert.label ungekuerzt."""
    if alert.hazard == "extreme_heat":
        return "Hitze", "warn"
    if alert.hazard == "wildfire_risk":
        sev = {2: "caution", 3: "warn", 4: "danger"}.get(alert.level, "warn")
        return f"Brand · {alert.level}", sev
    if alert.hazard == "access_ban":
        return "Zugang", "caution"
    if alert.hazard == "flood":
        sev = {2: "caution", 3: "warn", 4: "danger"}.get(alert.level, "warn")
        return "Hochwasser", sev
    return alert.label, "info"


def _dedup_alerts(alerts: list) -> list:
    """Duenner Wrapper um die kanonische Dedup-Quelle `dedupe_official_alerts`
    (Issue #1217/#1218): Uebersichts-Chip und Pro-Ort-Streifen nutzen dieselbe
    Gruppierung `(region_label or label, hazard)` + hoechste Stufe."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    return [a for a, _ in dedupe_official_alerts([(a, []) for a in alerts])]


def _render_warn_cell(alerts: list) -> str:
    """Warn-Zellen-Inhalt: gestapelte Kuerzel-Chips oder '—' bei keiner Warnung.

    Block-Divs statt Flexbox (Outlook-fest, AC-8) -- stapeln sich von selbst.
    """
    if not alerts:
        return '<span style="color:#b8b4a8;font-size:12px;">—</span>'
    chips = []
    seen: set[tuple[str, str, str, tuple[str, str]]] = set()
    for alert in alerts:
        short, _sev = _warn_short(alert)
        bg, fg = _ALERT_LEVEL_CELL.get(alert.level, _ALERT_LEVEL_CELL[4])
        # Issue #1451: NAMESPACED Identitaet wie `dedupe_official_alerts` --
        # ohne sie kollabieren Warnungen VERSCHIEDENER Regionen zu einem Chip.
        # Der Namespace-Tag ist Pflicht (F002): ein zufaellig gleicher String
        # zwischen `region_label` der einen und `label` der anderen Warnung
        # darf nicht kollabieren.
        if alert.dedup_id:
            region_ident = ("id", alert.dedup_id)
        elif alert.region_label:
            region_ident = ("region", alert.region_label)
        else:
            region_ident = ("label", alert.label)
        visual_key = (short, bg, fg, region_ident)
        if visual_key in seen:
            continue
        seen.add(visual_key)
        chips.append(
            f'<div style="display:inline-block;font-size:9.5px;font-weight:700;'
            f'letter-spacing:0.01em;padding:2px 6px;margin:1px auto;white-space:nowrap;'
            f'background:{bg};color:{fg};border:1px solid {fg}22;">{_html.escape(short)}</div>'
        )
    return "".join(chips)


# ---------------------------------------------------------------------------
# Uebersichtstabelle (Metriken x Orte)
# ---------------------------------------------------------------------------

# Issue #1285: Uebersichts-Zeilen, deren Tageswert NICHT als gleichnamiges
# LocationResult-Feld vorliegt. (Renderer-Zeilen-Key -> LocationResult-Feld /
# SegmentWeatherSummary-Feld). Beide Quellen tragen denselben Namen, weil das
# LocationResult-Feld exakt das Trip-Aggregat spiegelt.
_DAILY_AGGREGATE_FIELD: dict[str, str] = {
    "precip_sum": "precip_sum_mm",
    "pop_max": "pop_max_pct",
    "thunder_max": "thunder_level_max",
    "uv_max": "uv_index_max",
    "visibility_min": "visibility_min_m",
    # Issue #1296, Klasse B: cape_max/freezing_level haben KEIN LocationResult-
    # Feld (anders als temp_min/gust_max, die ueber den field-is-None-Zweig von
    # _metric_value direkt per getattr(loc, key) gelesen werden) -- der Wert
    # kommt ausschliesslich aus der Live-Ableitung (_daily_summary).
    "cape_max": "cape_max_jkg",
    "freezing_level": "freezing_level_m",
    # Issue #1324, Klasse B: kein LocationResult-Feld, Wert kommt aus der
    # Live-Ableitung (_daily_summary -> SegmentWeatherSummary).
    "humidity_avg": "humidity_avg_pct",
    "dewpoint_avg": "dewpoint_avg_c",
    "pressure_avg": "pressure_avg_hpa",
    "precip_type": "precip_type_dominant",
    "snowfall_limit": "snowfall_limit_m",
}


def _daily_summary(loc: LocationResult):
    """Tages-Aggregat eines Ortes aus ``hourly_data`` (kanonische Trip-Regeln).

    Der Renderer darf sich NICHT darauf verlassen, dass die ComparisonEngine
    gelaufen ist: ``dict_to_comparison_result()`` und der Validator-Render-Pfad
    fuettern denselben Renderer ohne Engine. Genau dieses Live-Ableiten aus
    ``hourly_data`` macht ``uv_max`` heute schon (Issue #1110); die vier neuen
    Zeilen folgen demselben Muster.
    """
    from services.weather_metrics import summarize_points

    return summarize_points(loc.hourly_data)


def _metric_value(loc: LocationResult, key: str, summary=None):
    field = _DAILY_AGGREGATE_FIELD.get(key)
    if field is None:
        return getattr(loc, key, None)
    # Engine-Wert hat Vorrang; fehlt er (kein Engine-Lauf), live ableiten.
    value = getattr(loc, field, None)
    if value is not None:
        return value
    if summary is None:
        summary = _daily_summary(loc)
    return getattr(summary, field, None) if summary is not None else None


def loc_hail_flag(loc: LocationResult, summary=None) -> Optional[bool]:
    """Issue #1475 Nachbesserung (Punkt 5b): DER EINE Weg, an das Hagel-
    Kennzeichen eines verglichenen Ortes zu kommen — genutzt von der
    HTML-Uebersicht, der Klartext-Fassung und den Ortsvergleich-Kanaelen
    SMS/Telegram (#1481 DRY-Pflicht, keine Parallel-Logik je Kanal).

    Reihenfolge wie bei ``_metric_value``: Engine-Wert am ``LocationResult``
    hat Vorrang, sonst wird aus ``hourly_data`` live abgeleitet (kanonisch
    ueber ``summarize_points``/``hail_priority``).
    """
    value = getattr(loc, "hail_flag", None)
    if value is not None:
        return value
    if summary is None:
        summary = _daily_summary(loc)
    return getattr(summary, "hail_flag", None) if summary is not None else None


def _fmt_metric(value, decimals, unit: str) -> str:
    if value is None:
        return "—"
    text = f"{value:.{decimals if decimals is not None else 0}f}"
    if not unit:
        return text
    return f"{text}{unit}" if unit in ("°C", "%") else f"{text} {unit}"


def _render_overview_row(
    m: dict, locations: list[LocationResult], marks: dict | None = None,
    summaries: dict | None = None,
) -> str:
    marks = marks or {}
    summaries = summaries or {}
    label_cell = (
        f'<td style="text-align:left;padding:8px 5px;font-family:{FONT_UI};'
        f'color:{G_INK_MUTED};font-weight:500;font-size:12px;'
        f'border-right:1px solid #f0ece1;">{_html.escape(m["label"])}</td>'
    )
    cells = [label_cell]
    for loc in locations:
        if m["key"] == "warn":
            content = "—" if loc.error is not None else _render_warn_cell(_dedup_alerts(loc.official_alerts))
            cells.append(
                f'<td style="text-align:center;padding:7px 5px;vertical-align:middle;'
                f'border-right:1px solid #f0ece1;">{content}</td>'
            )
            continue
        value = (
            None if loc.error is not None
            else _metric_value(loc, m["key"], summaries.get(id(loc)))
        )
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        bg, fg, weight = "transparent", G_INK, "500"
        if sev_level and sev_level != "ok":
            # Issue #1214 Scheibe 2: Zell-Toenung ueber die zentrale tone_css-
            # Palette (kanonisches Vokabular), Compare-lokal -> kanonisch.
            bg, fg = tone_css(_COMPARE_TO_LEVEL[sev_level])
            weight = "700"
        fmt_fn = m.get("fmt")
        if fmt_fn is _fmt_thunder:
            # Issue #1475 Nachbesserung (Punkt 5b, Aufrufstelle 1): die
            # Gewitter-Zeile bekommt zusaetzlich das Hagel-Kennzeichen DIESES
            # Ortes durchgereicht — alle anderen Zeilen bleiben unveraendert.
            text = fmt_fn(value, loc_hail_flag(loc, summaries.get(id(loc))))
        elif fmt_fn:
            text = fmt_fn(value)
        else:
            text = _fmt_metric(value, m.get("decimals"), m.get("unit", ""))
        marked = _is_marked(marks.get(m["key"]), value)
        cls = ' class="corridor-mark"' if marked else ""
        bg, extra_style = _mark_cell_style(bg, marked)
        cells.append(
            f'<td{cls} style="text-align:center;padding:8px 5px;font-family:{FONT_DATA};'
            f'font-size:12.5px;{extra_style}background:{bg};color:{fg};font-weight:{weight};'
            f'border-right:1px solid #f0ece1;">{text}</td>'
        )
    return f'<tr style="border-bottom:1px solid #f0ece1;">{"".join(cells)}</tr>'


def _visible_metrics(enabled_metrics: list[str] | None) -> list[dict]:
    """Issue #1104: filtert die NUMERISCHEN Uebersichts-Zeilen auf
    ``enabled_metrics`` (Liste von Renderer-Metrik-IDs wie "wind_max"). Die
    Warn-Zeile ("Amtliche Warnungen") ist immer sichtbar UND immer erste
    Zeile (AC-7), unabhaengig von ihrer Position/Abwesenheit in
    ``enabled_metrics``. ``None`` = kein Filter (alle Zeilen,
    Rueckwaertskompatibilitaet).

    Issue #1335 Scheibe 1 (AC-1): die uebrigen Zeilen folgen der Reihenfolge
    von ``enabled_metrics`` statt der festen ``CV2_METRICS``-
    Deklarationsreihenfolge.

    Issue #1453: der Zeilenkopf der Uebersicht hat praktisch unbegrenzt Platz
    und traegt deshalb den ausgeschriebenen deutschen Registernamen
    (``form="long"``). Die Stundentabelle (``_visible_hour_metrics``) bleibt
    bei der englischen Kurzform -- beide Formen kommen aus derselben
    Ableitung, es gibt keine zweite Namensliste."""
    warn_row = [m for m in CV2_METRICS if m["key"] == "warn"]
    if enabled_metrics is None:
        return derive_row_labels(CV2_METRICS, form="long")
    by_key = {m["key"]: m for m in CV2_METRICS}
    ordered = [by_key[k] for k in enabled_metrics if k in by_key and k != "warn"]
    return derive_row_labels(warn_row + ordered, form="long")


def _render_overview_table(
    locations: list[LocationResult],
    enabled_metrics: list[str] | None = None,
    corridors: list[Corridor] | None = None,
) -> str:
    header_cells = [
        f'<th style="text-align:left;padding:9px 5px;font-size:10px;'
        f'color:{G_INK_FAINT};border-right:1px solid #f0ece1;">Metrik</th>'
    ]
    for loc in locations:
        name = _html.escape(loc.location.name)
        header_cells.append(
            f'<th style="text-align:center;padding:9px 5px;font-size:11px;'
            f'font-family:{FONT_UI};font-weight:600;color:{G_INK};'
            f'border-right:1px solid #f0ece1;">{name}</th>'
        )
    header_row = (
        f'<tr style="background:{G_PAPER};border-bottom:1px solid #e6e1d3;">'
        f'{"".join(header_cells)}</tr>'
    )
    marks = _mark_lookup(corridors, FRONTEND_TO_RENDERER_METRIC_ID)
    visible = _visible_metrics(enabled_metrics)
    # Tages-Aggregate EINMAL je Ort ableiten (nicht je Zeile x Ort) -- nur wenn
    # ueberhaupt eine Zeile davon lebt.
    summaries: dict = {}
    if any(m["key"] in _DAILY_AGGREGATE_FIELD for m in visible):
        summaries = {
            id(loc): _daily_summary(loc)
            for loc in locations if loc.error is None and loc.hourly_data
        }
    rows = "".join(_render_overview_row(m, locations, marks, summaries) for m in visible)
    table = (
        f'<table cellspacing="0" cellpadding="0" style="width:100%;min-width:760px;'
        f'border-collapse:collapse;font-family:{FONT_DATA};'
        f'font-variant-numeric:tabular-nums;">'
        f'<thead>{header_row}</thead><tbody>{rows}</tbody></table>'
    )
    return (
        f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        f'margin-top:12px;border:1px solid #e6e1d3;">{table}</div>'
    )


def _render_warn_banner(locations: list[LocationResult]) -> str:
    """Aggregat-WarnBlock-Banner (Issue #1216): geteilter embedded WarnBlock mit
    Orts-Scope. Nennt die höchste amtliche Stufe + den führenden Ort („höchste
    Stufe ROT · Marseille") und zählt die betroffenen Orte je Gefahr („6 von 7
    Orten"). ADDITIV zum Bestands-Warn-Lead, zur Matrix-Warn-Zeile und zum
    Pro-Ort-Streifen (PO-Entscheidung Frage D, additiver Umbau)."""
    valid = [loc for loc in locations if loc.error is None]
    alerted = [loc for loc in valid if loc.official_alerts]
    if not alerted:
        return ""

    total = len(valid)
    leading_loc = None
    leading_alert = None
    for loc in alerted:
        for a in loc.official_alerts:
            if leading_alert is None or a.level > leading_alert.level:
                leading_alert, leading_loc = a, loc
    word = _LEVEL_WORDS.get(leading_alert.level, ("🔴", "ROT"))[1]
    count_line = f"höchste Stufe {word} · {leading_loc.location.name}"

    # Je Gefahr die höchststufige Warnung, Meter nach Stufe absteigend.
    by_hazard: dict = {}
    for loc in alerted:
        for a in loc.official_alerts:
            cur = by_hazard.get(a.hazard)
            if cur is None or a.level > cur.level:
                by_hazard[a.hazard] = a
    notices = []
    for a in sorted(by_hazard.values(), key=lambda x: -x.level):
        hz_locs = [loc for loc in alerted if any(x.hazard == a.hazard for x in loc.official_alerts)]
        if len(hz_locs) > 1:
            chip = f"{len(hz_locs)} von {total} Orten"
        else:
            chip = hz_locs[0].location.name if hz_locs else ""
        notices.append(OfficialAlertNotice(
            alert=a, scope_label="", sms_scope="",
            affected_chips=[chip] if chip else [], free_chips=[],
        ))

    return render_warn_block(
        notices, variant="embedded",
        source_label=official_alert_source_label(leading_alert.source),
        source_url=getattr(leading_alert, "url", None), count_line=count_line,
        tz=location_tz(leading_loc.location),
    )


# ---------------------------------------------------------------------------
# Stundentabellen (alle Orte)
# ---------------------------------------------------------------------------

def _sev_cell_style(level: Optional[str]) -> tuple[str, str, str]:
    if level is None or level == "ok":
        return "transparent", G_INK, "500"
    # Issue #1214 Scheibe 2: zentrale tone_css-Palette, Compare-lokal -> kanonisch.
    bg, fg = tone_css(_COMPARE_TO_LEVEL[level])
    return bg, fg, "700"


def _hour_td(
    text: str, bg: str = "transparent", fg: str = G_INK, weight: str = "500",
    align: str = "center", marked: bool = False,
) -> str:
    cls = ' class="corridor-mark"' if marked else ""
    bg, extra_style = _mark_cell_style(bg, marked)
    return (
        f'<td{cls} style="text-align:{align};padding:8px 4px;font-size:13px;'
        f'{extra_style}background:{bg};color:{fg};font-weight:{weight};'
        f'border-right:1px solid #f0ece1;">{text}</td>'
    )


def _visible_hour_metrics(hourly_metrics: list[str] | None) -> list[dict]:
    """Issue #1106: filtert ``HOUR_METRICS`` auf ``hourly_metrics`` (Liste von
    Renderer-Metrik-IDs wie "t2m_c").

    Issue #1406 Scheibe B: ``None`` heisst "nie eingestellt" und liefert die
    ausgesprochene Vorgabemenge ``HOURLY_DEFAULT_METRIC_IDS`` -- exakt die neun
    Spalten von vor der Katalog-Umstellung, in genau ihrer Reihenfolge. Vorher
    hiess ``None`` "alle Spalten"; mit 22 waehlbaren Wert-Spalten waere daraus
    ein ungefragter Sprung fuer jeden Bestands-Vergleich geworden (AC-4: kein
    automatisches Hinzufuegen der neuen Groessen).

    Issue #1335 Scheibe 1 (AC-2): die sichtbaren Spalten folgen der Reihenfolge
    von ``hourly_metrics`` statt der festen ``HOUR_METRICS``-Deklarations-
    reihenfolge. "wind_direction_deg" ist bewusst KEIN ``HOUR_METRICS``-Key
    (reines Merge-Signal, s. ``_should_merge_wind_dir``) -- es erzeugt hier nie
    eine eigene Spalte."""
    by_key = {m["key"]: m for m in HOUR_METRICS}
    if hourly_metrics is None:
        by_metric_id = {m["metric_id"]: m for m in HOUR_METRICS}
        return derive_row_labels([
            by_metric_id[mid] for mid in HOURLY_DEFAULT_METRIC_IDS
            if mid in by_metric_id
        ])
    return derive_row_labels([by_key[k] for k in hourly_metrics if k in by_key])


def has_visible_hour_columns(hourly_metrics: list[str] | None) -> bool:
    """Issue #1366 (Nachtrag): Erzeugt diese Auswahl ueberhaupt eine Wert-
    Spalte? Antwortet aus ``HOUR_METRICS`` heraus, damit es keine zweite,
    driftende Liste "welche Kennung hat eine Spalte" gibt.

    ``False`` heisst: die Stundentabelle haette nur die fest verdrahtete
    Zeit-Spalte. Das trifft die bewusste Leerauswahl (``[]``) ebenso wie eine
    Auswahl aus ausschliesslich Merge-Signalen -- "wind_direction_deg" ist
    aufloesbar, hat aber bewusst keinen ``HOUR_METRICS``-Eintrag (s.
    ``_should_merge_wind_dir``). ``None`` (kein Filter/Altbestand) = alle 9
    Spalten sichtbar."""
    return bool(_visible_hour_metrics(hourly_metrics))


def _should_merge_wind_dir(hourly_metrics: list[str] | None) -> bool:
    """Issue #1335 Scheibe 1 (AC-3/AC-4), analog Trip-Muster
    ``helpers.should_merge_wind_dir``: Windrichtung wird nur dann als
    Kompass-Text in die Wind-Zelle gemergt, wenn BEIDE explizit in der
    Auswahl stehen -- "wind10m_kmh" (Wind-Spalte) UND "wind_direction_deg"
    (Merge-Signal). ``hourly_metrics=None`` (kein Filter/Altbestand) merged
    nie -- kein stiller Verhaltenswechsel fuer Bestandsnutzer ohne
    Konfiguration."""
    if hourly_metrics is None:
        return False
    return "wind10m_kmh" in hourly_metrics and "wind_direction_deg" in hourly_metrics


def _render_hour_row(
    dp, visible: list[dict], marks: dict, merge_wind_dir: bool = False,
    *, tz: ZoneInfo,
) -> str:
    # Issue #1237 (AC-1): nur die Stunde ("07"), kein Minutenanteil -- identisch
    # zur bereits korrekten Trip-Briefing-Formatierung (helpers.dp_to_row).
    # Issue #1378: die Stunde ist die ORTSZEIT-Stunde des Ortes (geteilter
    # Umrechner utils.timezone.local_hour, Trip-Vorbild helpers.py:93/142) --
    # `dp.ts` ist naive UTC (Hausnorm #1345) und wurde bisher roh beschriftet.
    # Issue #1402: `tz` ist PFLICHTPARAMETER, der einzige Aufrufer
    # (`_render_hour_table`) loest ihn immer ueber `location_tz()` auf.
    hh = f"{local_hour(dp.ts, tz):02d}" if hasattr(dp.ts, "astimezone") else str(dp.ts)
    cells = _hour_td(hh, fg=G_INK_MUTED, align="left")
    for m in visible:
        value = getattr(dp, m["key"], None)
        # Issue #1475 Nachbesserung (Punkt 5b, Aufrufstelle 2 / AC-8): die
        # Compare-Stundentabelle zeigt Gewitter als TEXT (kein Ampel-Kreis) --
        # der Hagel-Zusatz haengt deshalb als Text an, NICHT als Doppelring
        # (das ist ausschliesslich die Trip-Stundentabelle, Punkt 2). `dp` ist
        # hier bereits im Scope, analog zum Windrichtungs-Muster unten.
        if m["fmt"] is _fmt_thunder:
            text = m["fmt"](value, getattr(dp, "hail_flag", None))
        else:
            text = m["fmt"](value)
        # Issue #1335 Scheibe 1 (AC-3): Windrichtung als Kompass-Text an die
        # Wind-Zelle angehaengt, analog Trip-Muster (helpers.py:648-651) --
        # keine eigene Spalte.
        if merge_wind_dir and m["key"] == "wind10m_kmh":
            compass = degrees_to_compass(getattr(dp, "wind_direction_deg", None))
            if compass:
                text = f"{text} {compass}"
        sev_fn = m.get("sev")
        sev_level = sev_fn(value) if (sev_fn and value is not None) else None
        style = _sev_cell_style(sev_level)
        marked = _is_marked(marks.get(m["key"]), value)
        cells += _hour_td(text, *style, marked=marked)
    return f'<tr style="border-bottom:1px solid #f0ece1;">{cells}</tr>'


def _render_hour_table(
    loc: LocationResult, hourly_metrics: list[str] | None = None,
    corridors: list[Corridor] | None = None,
) -> str:
    visible = _visible_hour_metrics(hourly_metrics)
    merge_wind_dir = _should_merge_wind_dir(hourly_metrics)
    marks = _mark_lookup(corridors, CORRIDOR_METRIC_TO_HOUR_KEY)
    tz = location_tz(loc.location)  # Issue #1378 — EIN Aufloeser (E3)
    columns = ["Zeit"] + [m["label"] for m in visible]
    ths = "".join(
        f'<th style="text-align:{"left" if col == "Zeit" else "center"};padding:6px 4px;'
        f'font-size:11px;color:{G_INK};font-weight:600;border-right:1px solid #f0ece1;">'
        f'{col}</th>'
        for col in columns
    )
    header = f'<tr style="background:{G_PAPER};border-bottom:1px solid #e6e1d3;">{ths}</tr>'
    rows = "".join(
        _render_hour_row(dp, visible, marks, merge_wind_dir, tz=tz)
        for dp in loc.hourly_data
    )
    table = (
        f'<table cellspacing="0" cellpadding="0" style="width:100%;'
        f'border-collapse:collapse;margin-top:12px;font-family:{FONT_DATA};'
        f'font-size:12px;font-variant-numeric:tabular-nums;">'
        f'<thead>{header}</thead><tbody>{rows}</tbody></table>'
    )
    return (
        f'<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;'
        f'margin-top:12px;border:1px solid #e6e1d3;">{table}</div>'
    )


def _location_heading(
    loc: LocationResult, ref_ts=None, *, eyebrow: str = "ORT",
    title: Optional[str] = None,
) -> str:
    """Ort-Kopf ("ORT <Name>") MIT angeschriebener Zeitbasis.

    ``eyebrow``/``title`` (#1368): derselbe Kopfbau traegt auch die eigene
    Ausblick-Ueberschrift ("AUSBLICK 3-Tages-Ausblick (CEST)") -- kein
    zweiter Kopfbau, damit die Zeitbasis-Anschrift aus #1378 an BEIDEN
    Bloecken identisch entsteht. Defaults = Bestandsverhalten.

    Issue #1378 (Adversary F002): die Zeitzonen-Kennzeichnung darf nicht nur
    an der zentralen "Erstellt"-Kopfzeile haengen — die nennt ausschliesslich
    die Zone des ERSTgenannten Ortes. Zwei Ortsbloecke koennen identische
    Stunden-Beschriftungen (09..16) tragen und trotzdem verschiedene Zonen
    meinen (AC-6); ein nicht aufloesbarer Ort faellt sichtbar auf UTC zurueck
    (AC-7). Deshalb schreibt JEDER Block seine eigene Zeitbasis an.

    ``ref_ts`` ist der Zeitpunkt, den der Block auch zeigt — das Kuerzel ist
    zeitpunktabhaengig (CEST im Sommer, CET im Winter). Der Namens-Span bleibt
    unveraendert, damit Ableser/Validator ("ORT <Name>"-Marker) weiter greifen.
    """
    name = _html.escape(title if title is not None else loc.location.name)
    tz_span = ""
    if ref_ts is not None:
        label = _html.escape(tz_abbrev(ref_ts, location_tz(loc.location)))
        tz_span = (
            f'<span style="font-family:{FONT_DATA};font-size:11px;'
            f'color:{G_INK_MUTED};"> ({label})</span>'
        )
    return (
        f'<div style="padding-bottom:8px;border-bottom:2px solid {G_INK};">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
        f'color:{G_ACCENT};letter-spacing:0.1em;">{eyebrow}</span> '
        f'<span style="font-size:15px;font-weight:600;color:{G_INK};">{name}</span>'
        f'{tz_span}</div>'
    )


def _render_location_section(
    loc: LocationResult, index: int, hourly_metrics: list[str] | None = None,
    corridors: list[Corridor] | None = None,
) -> str:
    """Ort-Kopf + Langform-Warn-Streifen + Stundentabelle. Entfaellt bei Fehler
    bzw. fehlenden Stundendaten (SPEC §4)."""
    if loc.error is not None or not loc.hourly_data:
        return ""
    header = _location_heading(loc, loc.hourly_data[0].ts)
    strip = ""
    if loc.official_alerts:
        # F002 (Adversary Fix-Runde): kein Ortsnamen-Praefix im Compare-Streifen
        # (der Ort-Kopf direkt darueber nennt den Namen bereits) -- geloest per
        # leerem Gruppen-Label am Compare-Aufruf, das Shared-Modul selbst
        # (ADR-0011, Trip-Pfad) bleibt unveraendert.
        # Issue #1134: Dedup identischer Warnungen. Issue #1056 v2.0: Badge-
        # Farbe ist amtstreu level-basiert (kein severity_fn mehr).
        strip = render_official_alerts_html(
            [("", _dedup_alerts(loc.official_alerts))],
        )
    return (
        f'<div style="padding:{20 if index else 14}px 24px 0;">'
        f'{header}{strip}{_render_hour_table(loc, hourly_metrics, corridors)}</div>'
    )


# ---------------------------------------------------------------------------
# Epic #1301 B4 — 3-Tage-Ausblick je Ort (geteilter Renderer/Zeilenbau)
# ---------------------------------------------------------------------------

_WEEKDAYS_DE_OUTLOOK = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _group_by_calendar_day(points: list, tz: ZoneInfo, cap: int = 3) -> list[tuple]:
    """Gruppiert eine flache Punktliste nach Kalendertag, Cap auf `cap` Tage.

    Issue #1378 (AC-9): Tagesgrenze ist die ORTS-Mitternacht, nicht die
    UTC-Mitternacht -- bei UTC+2 gehoeren die Punkte 22:00-23:59 UTC bereits
    zum FOLGENDEN Ortstag. Issue #1402: `tz` ist PFLICHTPARAMETER — der
    einzige Aufrufer loest ihn immer ueber `location_tz()` auf."""
    by_day: dict = {}
    for dp in points:
        by_day.setdefault(local_dt(dp.ts, tz).date(), []).append(dp)
    days = sorted(by_day)[:cap]
    return [(d, by_day[d]) for d in days]


def _build_location_outlook_rows(
    loc: LocationResult, outlook_metrics: list[dict] | None = None,
) -> list[dict]:
    """AC-5/AC-8: bis zu 3 Tages-Zeilen aus `outlook_hourly_data`, ueber
    denselben Aggregator (`summarize_points`) und denselben Zeilenbau
    (`build_outlook_row`) wie der Trip-Pfad (Trip/Compare-Teilungs-
    Invariante).

    Issue #1378: die Zeitzone kommt aus dem EINEN Aufloeser (`location_tz`,
    Vorrang `SavedLocation.timezone`, sonst Koordinaten) statt aus der frueheren
    Ad-hoc-Kette `location.timezone or "UTC"` -- die fiel fuer jeden Ort ohne
    gepflegtes Feld still auf Serverzeit zurueck (AC-5)."""
    from services.weather_metrics import summarize_points

    # Issue #1361/#1368 (AC-8): eine bewusst geleerte Auswahl ergibt KEINE
    # Zeilen — HTML- und Klartext-Pfad lassen den Block daraufhin beide ganz
    # entfallen (statt einer Tagestabelle mit nur der Wochentag-Spalte). Eine
    # Bedingung an EINER Stelle, nicht zwei Kopien in den Renderern.
    if isinstance(outlook_metrics, list) and not outlook_metrics:
        return []

    tz = location_tz(loc.location)

    rows = []
    for day, day_points in _group_by_calendar_day(loc.outlook_hourly_data, tz):
        summary = summarize_points(day_points)
        weekday = _WEEKDAYS_DE_OUTLOOK[day.weekday()]
        rows.append(build_outlook_row(
            summary, day_points, weekday, tz, metrics=outlook_metrics,
        ))
    return rows


# Issue #1368: der Block hiess bisher wie der Stundenblock darueber ("ORT
# <Name>") und war damit fuer den Empfaenger nicht als Ausblick erkennbar.
OUTLOOK_HEADING = "3-Tages-Ausblick"


def _render_outlook_unavailable(
    loc: LocationResult, index: int, with_location: bool = False,
) -> str:
    """Fix #1505: benannter Ausblick-Zustand statt stillem ``""``.

    Derselbe Block-Rahmen wie die Erfolgstabelle (Padding-`div` + Kopf mit
    Eyebrow "AUSBLICK"), damit der Zustandstext an genau der Stelle steht, an
    der sonst die Tabelle stuende. Der Zustandstext selbst kommt aus dem
    geteilten Baustein ``outlook_state_hint`` (#1486) -- keine
    Compare-eigene Kopie, keine neuen ``OutlookState``-Werte.

    Kein Referenzzeitpunkt (``ref_ts=None``): ohne Datenpunkte gibt es keine
    Zeitbasis, die man ehrlich anschreiben koennte."""
    from output.renderers.email.outlook_state_hint import (
        OutlookState, render_outlook_state_html,
    )

    title = (
        f"{loc.location.name} · {OUTLOOK_HEADING}" if with_location
        else OUTLOOK_HEADING
    )
    header = _location_heading(loc, None, eyebrow="AUSBLICK", title=title)
    hint = render_outlook_state_html(OutlookState.UNAVAILABLE)
    return (
        f'<div style="padding:{20 if index else 14}px 24px 0;">'
        f'{header}{hint}</div>'
    )


def _render_location_outlook(
    loc: LocationResult, index: int,
    outlook_metrics: list[dict] | None = None,
    with_location: bool = False,
) -> str:
    """AC-5/AC-9: Ausblick-Tabelle je Ort; entfaellt fail-soft bei Fehler
    bzw. leerem `outlook_hourly_data` (kein Crash, restliche Mail
    unveraendert).

    Issue #1368: eigene Ueberschrift "3-Tages-Ausblick" statt des ein
    zweites Mal wiederholten Ortsnamens. ``with_location=True`` stellt den
    Ortsnamen voran -- noetig, wenn der Stundenblock desselben Ortes (der
    ihn sonst nennt) nicht gerendert wird.

    Fix #1505: die drei stillen Ausstiege (Fehler, leere Rohdaten, leere
    Zeilen nach Metrik-Filterung) sahen fuer den Empfaenger alle gleich aus
    -- eine unerklaerte Leerstelle. Sie liefern jetzt alle denselben
    benannten Zustand (``OutlookState.UNAVAILABLE``) ueber den geteilten
    Baustein aus #1486 (kein Compare-eigener Nachbau)."""
    if loc.error is not None or not loc.outlook_hourly_data:
        return _render_outlook_unavailable(loc, index, with_location)
    rows = _build_location_outlook_rows(loc, outlook_metrics)
    if not rows:
        return _render_outlook_unavailable(loc, index, with_location)
    # Issue #1378: dieselbe angeschriebene Zeitbasis wie beim Stundenblock
    # (geteilter Kopfbau, kein zweiter) — auch die Ausblick-Tageszeilen
    # und ihre @-Stunden-Tokens stehen in dieser Zeitbasis.
    title = (
        f"{loc.location.name} · {OUTLOOK_HEADING}" if with_location
        else OUTLOOK_HEADING
    )
    header = _location_heading(
        loc, loc.outlook_hourly_data[0].ts, eyebrow="AUSBLICK", title=title,
    )
    table = render_outlook_table(rows, show_acc=False, metrics=outlook_metrics)
    return (
        f'<div style="padding:{20 if index else 14}px 24px 0;">'
        f'{header}{table}</div>'
    )


def _render_official_alerts_block(locations: list[LocationResult]) -> str:
    """Badges fuer amtliche Warnungen je Ort (Thin-Wrapper, ADR-0011).

    Nicht mehr Teil des Hauptrenderpfads (v2 nutzt Warn-Chips in der
    Uebersichtstabelle + Langform-Streifen je Ort), aber als generischer
    Baustein erhalten (Byte-Gleichheit zu #1087 fuer registrierte Konsumenten).
    """
    entries = [(loc.location.name, loc.official_alerts) for loc in locations]
    return render_official_alerts_html(entries)


# ---------------------------------------------------------------------------
# Header / Section-Head / Legende / Footer
# ---------------------------------------------------------------------------

def _render_warning_banner(warning_text: str) -> str:
    """Orange-Banner mit G_WARNING-Akzent (allgemeine Betriebswarnungen,
    z.B. nicht verfuegbare Standorte -- unabhaengig von amtlichen Warnungen)."""
    safe = _html.escape(warning_text)
    return (
        f'<div style="background:{G_BOX_WARNING_BG};'
        f'border-left:4px solid {G_WARNING};'
        f'padding:12px 16px;margin:8px 20px;'
        f'border-radius:4px;font-family:{FONT_UI};font-size:14px;'
        f'color:{G_INK};">'
        f'{safe}</div>'
    )


def _render_header(result: ComparisonResult, sig, tz: ZoneInfo) -> str:
    label_text = f"ORTS-VERGLEICH · {_html.escape(sig.eyebrow)}"
    label_style = (
        f"font-family:{FONT_DATA};font-size:10px;"
        f"color:{G_ACCENT};letter-spacing:0.08em;"
        f"text-transform:uppercase;margin:0 0 6px 0;"
    )

    weekday = _WEEKDAY_ABBR[result.target_date.weekday()]
    date_str = result.target_date.strftime("%d.%m.%Y")
    # Issue #1268: keine Zeitfenster-Angabe mehr in der Kopfzeile — die
    # Bewertung laeuft immer ueber den ganzen Tag, es gibt nichts zu zeigen.
    date_line = f"{weekday}, {date_str}"
    date_style = f"font-family:{FONT_DATA};font-size:13px;color:{G_INK};margin-top:6px;"

    profil_val = _html.escape(sig.eyebrow)
    orte_val = str(len(result.locations))
    # Issue #1378 (AC-4/AC-8): Erzeugungszeit des Vergleichs (`created_at`,
    # dieselbe Quelle wie der Klartext-Teil -- vorher `datetime.now()`, das
    # beim Rendern erneut die Serveruhr las) in der Ortszeit des
    # ERSTGENANNTEN Ortes, mit erkennbarem Zeitzonen-Kuerzel. Ohne
    # aufloesbare Zeitzone steht dort sichtbar "(UTC)" statt einer
    # vorgetaeuschten Ortszeit (AC-7) -- der Aufrufer (`render_compare_email`)
    # entscheidet das bereits VOR dem Aufruf explizit (Issue #1402: `tz` ist
    # hier PFLICHTPARAMETER, kein stiller Rueckfall mehr).
    erstellt_val = _html.escape(local_stamp(result.created_at, tz))
    # Issue #1305: keine Horizont-Kachel mehr — analog #1268 (Zeitfenster-Zeile
    # entfiel ersatzlos). Der Wert ist kein Nutzer-relevanter Datenpunkt.

    cell_label_style = (
        f"font-family:{FONT_DATA};font-size:9px;"
        f"color:{G_INK_FAINT};text-transform:uppercase;"
        f"letter-spacing:0.08em;padding-bottom:2px;"
    )
    cell_value_style = f"font-family:{FONT_UI};font-size:14px;color:{G_INK};font-weight:600;"

    def _cell(label: str, value: str, width: str) -> str:
        return (
            f'<td width="{width}" style="vertical-align:top;padding:0 8px 0 0;">'
            f'<div style="{cell_label_style}">{label}</div>'
            f'<div style="{cell_value_style}">{value}</div>'
            f'</td>'
        )

    desktop_cells = (
        _cell("Profil", profil_val, "33%")
        + _cell("Orte", orte_val, "33%")
        + _cell("Erstellt", erstellt_val, "34%")
    )
    desktop_table = (
        f'<table class="header-stats-desktop" cellspacing="0" cellpadding="0" '
        f'style="width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{desktop_cells}</tr></table>'
    )

    mobile_row1 = _cell("Profil", profil_val, "50%") + _cell("Orte", orte_val, "50%")
    mobile_row2 = _cell("Erstellt", erstellt_val, "100%")
    mobile_table = (
        f'<table class="header-stats-mobile" cellspacing="0" cellpadding="0" '
        f'style="display:none;width:100%;margin-top:14px;border-collapse:collapse;">'
        f'<tr>{mobile_row1}</tr><tr>{mobile_row2}</tr></table>'
    )

    wrapper_style = f"background:{G_PAPER};padding:22px;border-bottom:1px solid #e6e1d3;"
    return (
        f'<div class="header-wrapper" style="{wrapper_style}">'
        f'<div style="{label_style}">{label_text}</div>'
        f'<div style="{date_style}">{date_line}</div>'
        f'{desktop_table}{mobile_table}</div>'
    )


def _render_section_head(accent: str, title: str, hint: str) -> str:
    return (
        f'<table style="width:100%;border-collapse:collapse;"><tr>'
        f'<td style="text-align:left;padding:0 0 8px;border-bottom:2px solid {G_INK};">'
        f'<span style="font-family:{FONT_DATA};font-size:11px;font-weight:600;'
        f'color:{G_ACCENT};letter-spacing:0.1em;">{_html.escape(accent)}</span> '
        f'<span style="font-size:14px;font-weight:600;color:{G_INK};">{_html.escape(title)}</span>'
        f'</td>'
        f'<td style="text-align:right;padding:0 0 8px;border-bottom:2px solid {G_INK};'
        f'font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};">'
        f'{_html.escape(hint)}</td>'
        f'</tr></table>'
    )


def _units_legend_text(visible: list[dict]) -> str:
    """Issue #1237 (AC-2): Einheiten-Zeile fuer die sichtbaren Stunden-Spalten.
    Einheit je Spalte kommt aus dem Metrik-Katalog (`display_unit`, sonst
    `unit`), formatiert vom geteilten Helfer `helpers.format_units_legend` --
    dieselbe Quelle wie die Trip-Briefing-Legende (keine Kopie)."""
    from app.metric_catalog import _METRICS_BY_ID
    from output.renderers.email.helpers import format_units_legend

    pairs: list[tuple[str, str]] = []
    for m in visible:
        mdef = _METRICS_BY_ID.get(m.get("metric_id", ""))
        if mdef is None:
            continue
        pairs.append((m["label"], mdef.display_unit if mdef.display_unit else mdef.unit))
    return format_units_legend(pairs)


def _column_legend_text(visible: list[dict]) -> str:
    """Issue #1472 (AC-1/AC-8): Spalten-Zeile fuer die sichtbaren Stunden-
    Spalten -- 'Spalten: Thdr = Gewitter · Visib = Sichtweite'.

    Beide Seiten des Paares stammen aus DERSELBEN Ableitung wie der
    Tabellenkopf (`derive_row_labels`), positionsgleich gezippt: kurz = der
    gerenderte Spaltenkopf, lang = der ausgeschriebene deutsche Registername.
    Damit traegt die Legende bei gleichlautender Kurzform denselben
    Auswertungs-Zusatz wie der Kopf ('Temp max = Temperatur Maximum') statt
    ein Kuerzel zu erklaeren, das in der Tabelle gar nicht vorkommt.
    Formatiert vom geteilten Helfer `helpers.format_column_legend` -- dieselbe
    Quelle wie die Trip-Briefing-Legende (keine Kopie)."""
    from output.renderers.email.helpers import format_column_legend

    kurz = derive_row_labels(visible, form="short")
    lang = derive_row_labels(visible, form="long")
    pairs = [(k["label"], lng["label"]) for k, lng in zip(kurz, lang)]
    return format_column_legend(pairs)


def _render_units_legend(hourly_metrics: list[str] | None) -> str:
    """Einheiten-Legende UNTER der Stundentabelle (nicht im Spaltenkopf) --
    die Spaltenkoepfe bleiben 'Zeit'/'Sicht' (AC-2). Issue #1472: darunter die
    zweite Zeile, die die englischen Kuerzel aufloest (ADR-0042-Bedingung)."""
    visible = _visible_hour_metrics(hourly_metrics)
    blocks = ""
    for text in (_units_legend_text(visible), _column_legend_text(visible)):
        if not text:
            continue
        blocks += (
            f'<div style="margin-top:8px;font-family:{FONT_DATA};font-size:10px;'
            f'color:{G_INK_MUTED};">{_html.escape(text)}</div>'
        )
    return blocks


def _render_legend(hourly_metrics: list[str] | None = None, hourly_enabled: bool = True) -> str:
    items = [("#2f8a3e", "unkritisch"), ("#e3b008", "Achtung"), ("#e07b1a", "Warnung"), ("#c52a22", "Gefahr")]
    dots = "".join(
        f'<span style="display:inline-block;margin-right:16px;font-family:{FONT_DATA};'
        f'font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
        f'background:{color};margin-right:6px;vertical-align:middle;"></span>{label}</span>'
        for color, label in items
    )
    units = _render_units_legend(hourly_metrics) if hourly_enabled else ""
    return (
        f'<div style="background:{G_PAPER};border-top:1px solid #e6e1d3;padding:18px 24px;'
        f'margin-top:22px;font-family:{FONT_DATA};font-size:10px;color:{G_INK_MUTED};">'
        f'<span style="font-weight:600;color:{G_INK_FAINT};letter-spacing:0.08em;'
        f'text-transform:uppercase;margin-right:16px;">Risk</span>{dots}'
        f'<span style="color:{G_INK_FAINT};">Warn-Kürzel: Hitze · Brand·Stufe · Zugang</span>'
        f'{units}'
        f'</div>'
    )


def _compute_next_send(schedule, weekday) -> Optional[str]:
    """Known Limitation (SPEC): liefert None (-> '—'), wenn schedule nicht
    ermittelbar ist."""
    if not schedule:
        return None
    today = date.today()
    schedule_str = str(schedule).lower()
    if "weekly" in schedule_str and weekday is not None:
        try:
            target_wd = int(weekday)
        except (TypeError, ValueError):
            return None
        days_ahead = (target_wd - today.weekday()) % 7 or 7
        return (today + timedelta(days=days_ahead)).strftime("%d.%m.%Y")
    if "daily" in schedule_str:
        return (today + timedelta(days=1)).strftime("%d.%m.%Y")
    return None


def _render_abo_footer(preset_name, preset_schedule, preset_weekday, location_count: int, sig) -> str:
    name = _html.escape(preset_name) if preset_name else "Ortsvergleich"
    next_send = _compute_next_send(preset_schedule, preset_weekday) or "—"
    return (
        f'<div style="padding:20px 24px;background:{G_PAPER};border-top:1px solid #e6e1d3;">'
        f'<table style="width:100%;border-collapse:collapse;"><tr>'
        f'<td style="vertical-align:top;width:50%;">'
        f'<span style="font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};'
        f'text-transform:uppercase;letter-spacing:0.1em;">Dieses Abo</span>'
        f'<div style="font-size:14px;font-weight:600;margin-top:4px;color:{G_INK};">{name}</div>'
        f'<div style="font-size:11px;color:{G_INK_MUTED};margin-top:4px;'
        f'font-family:{FONT_DATA};line-height:1.6;">'
        f'{location_count} Orte · Profil {_html.escape(sig.eyebrow)}</div>'
        f'</td>'
        f'<td style="vertical-align:top;width:50%;">'
        f'<span style="font-family:{FONT_DATA};font-size:10px;color:{G_INK_FAINT};'
        f'text-transform:uppercase;letter-spacing:0.1em;">Nächster Versand</span>'
        f'<div style="font-size:14px;font-weight:600;margin-top:4px;'
        f'font-family:{FONT_DATA};color:{G_INK};">{next_send}</div>'
        f'</td></tr></table></div>'
    )


def _render_app_footer() -> str:
    # Issue #1241/warnmail-Spec AC-5 (Befund 4a): dezente Herkunfts-Fußzeile
    # (SSoT-Helper) -- keine per-Ort-Provider-Info hier verfügbar (Known
    # Limitation der Spec), fester Fallback "Open-Meteo" (ADR-0029) statt
    # des internen Renderer-Pfads.
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html,
    )
    origin_html = render_origin_footer_html(build_origin_footer(
        "compare", source="Open-Meteo",
    ))
    return (
        f'<div style="padding:16px 24px 20px;background:{G_INK};color:#9a978d;'
        f'font-size:11px;font-family:{FONT_DATA};">'
        f'<span style="color:#ffffff;font-weight:600;letter-spacing:0.06em;">GREGOR ZWANZIG</span>'
        f' <span style="color:#5a5750;">·</span> Orts-Vergleich'
        f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #3a3835;font-size:10px;">'
        f'<a href="#" style="color:{G_ACCENT};text-decoration:none;margin-right:16px;">'
        f'Vergleich in App öffnen →</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;margin-right:16px;">Abo bearbeiten</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;margin-right:16px;">Orte ändern</a>'
        f'<a href="#" style="color:#9a978d;text-decoration:none;">Abmelden</a>'
        f'</div></div>'
        + origin_html
    )


def location_render_order(locations: list[LocationResult]) -> list[LocationResult]:
    """Zentraler Orts-Reihenfolge-Helfer (Issue #1359 Scheibe 2): reicht die
    bereits in ``ComparisonResult.locations`` ankommende, vom Nutzer
    konfigurierte Reihenfolge unveraendert durch -- einheitlich fuer
    Uebersichts-Spalten, Stundentabellen-Abschnitte (hier), Klartext, Telegram
    und SMS (output.renderers.comparison, importiert von dort -- keine
    Doppel-Implementierung).

    Bleibt als einziger Choke-Point bestehen (fruehere alphabetische
    Sortierung, PO-Update 2026-07-08, abgeloest durch #1359): sollte kuenftig
    doch wieder eine serverseitige Sortierregel gebraucht werden, gibt es
    weiterhin genau eine Stelle dafuer statt vier Aufrufstellen."""
    return list(locations)


# ---------------------------------------------------------------------------
# Oeffentliche API
# ---------------------------------------------------------------------------

def render_compare_html(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    enabled_metrics: list[str] | None = None,
    hourly_metrics: list[str] | None = None,
    hourly_enabled: bool = True,
    preset_name: Optional[str] = None,
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
    corridors: list[Corridor] | None = None,
    outlook_enabled: bool = False,
    outlook_metrics: list[dict] | None = None,
    undelivered: list | None = None,
) -> str:
    """Rendert ComparisonResult als HTML-Mail (v2-Layout, Issue #1110).

    Pure Function — keine Seiteneffekte, kein Netzwerk. Kein Score/Winner.

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: ActivityProfile fuer Eyebrow. Default ALLGEMEIN.
        warnings: Liste allgemeiner Betriebswarnungen (orange Banner).
        enabled_metrics: Optionale Liste von Renderer-Metrik-IDs (z.B.
            "wind_max"/"cloud_avg"), filtert UND ordnet die numerischen
            Uebersichts-Zeilen in genau dieser Reihenfolge (Issue #1335
            Scheibe 1, AC-1). Die Warn-Zeile "Amtliche Warnungen" ist immer
            sichtbar und immer erste Zeile (AC-7). ``None`` = alle Metriken
            in CV2_METRICS-Reihenfolge (Default, rueckwaertskompatibel).
        hourly_metrics: Optionale Liste von Renderer-Metrik-IDs (Issue #1106,
            z.B. "t2m_c"/"thunder_level"), filtert UND ordnet die Wert-Spalten
            je Stundentabelle in genau dieser Reihenfolge (Issue #1335
            Scheibe 1, AC-2). "wind_direction_deg" erzeugt keine eigene
            Spalte, sondern merged als Kompass-Text in die Wind-Zelle, wenn
            "wind10m_kmh" ebenfalls ausgewaehlt ist (AC-3/AC-4). "Zeit"
            bleibt immer erste Spalte. ``None`` = alle 9 Spalten in
            HOUR_METRICS-Reihenfolge (Default).
        hourly_enabled: Issue #1107 -- ``False`` laesst die komplette
            Stundenverlauf-Sektion (Kopf "STUNDEN" + alle Orts-
            Stundentabellen) weg. ``hourly_metrics`` (Spalten-Filter,
            #1106) hat dann keine Wirkung mehr, da die Sektion gar nicht
            gerendert wird. Default ``True`` (rueckwaertskompatibel,
            identisch zum Verhalten vor diesem Slice).
        preset_name: Name des Compare-Presets fuer den Abo-Footer.
        preset_schedule: Schedule-Wert (z.B. "daily"/"weekly") fuer "Naechster Versand".
        preset_weekday: Wochentag-Index (0=Mo) fuer weekly-Schedules.
        corridors: Issue #1231, Slice 7 -- Corridor-Liste des Presets. Zellen,
            deren Wert bei einem `mark=True`-Corridor innerhalb dessen `range`
            liegt (`corridor_inside()`, C5), erhalten zusaetzlich
            `class="corridor-mark"` (additiv zur Severity-Faerbung, AC-19).
            `None`/`[]` = kein Korridor konfiguriert, HTML unveraendert.
        outlook_enabled: Epic #1301 B4 -- ``True`` zeigt je Ort einen bis zu
            3-Tage-Ausblick (Tagestabelle ohne ACC-Spalte, `show_acc=False`,
            ADR-0005/#710). Default ``False`` (rueckwaertskompatibel; der
            Aufrufer resolved den tatsaechlichen Default ueber
            `resolve_compare_render_options`, s. `report_config_resolver.py`).
        outlook_metrics: Issue #1361/#1368 — Auswahl der Ausblick-Spalten im
            Neuformat (`[{"metric_id", "aggregation"}]`, dasselbe Vokabular
            wie `active_metrics`). Filtert UND ordnet die Wert-Spalten der
            Tagestabelle. `None` (Altbestand) = die bisherigen sieben festen
            Spalten, unveraendert.

    Returns:
        HTML-String (DOCTYPE bis </html>).

    Issue #1360: der frueher akzeptierte, sofort verworfene Parameter
    `top_n_details` (#1104) ist ersatzlos entfallen. Die Mail zeigt immer ALLE
    Orte — ein Aufruf mit `top_n_details=` scheitert jetzt sichtbar mit
    `TypeError` statt still zu wirken wie eine Einstellung.
    """
    warnings = warnings or []
    sig = profile_signature(profile)
    locations = location_render_order(result.locations)

    # Issue #1378 (AC-4): Kopfzeilen-Zeitbasis = Ortszeit des ERSTGENANNTEN
    # Ortes der konfigurierten Reihenfolge (`location_render_order`, #1359) --
    # nicht alphabetisch, nicht Serverzeit.
    header_tz = location_tz(locations[0].location) if locations else UTC
    header_html = _render_header(result, sig, header_tz)
    warnings_html = "".join(_render_warning_banner(w) for w in warnings)
    warn_banner_html = _render_warn_banner(locations)
    # Issue #1349 (Scheibe 3) — geteilter Baustein aus unavailable_hint.py,
    # kein Nachbau. Nur bei gesetztem Flag aufgerufen (AC-2 Byte-Identitaet).
    from output.renderers.email.unavailable_hint import (
        any_official_alerts_unavailable, render_official_alerts_unavailable_html,
    )
    unavailable_banner_html = (
        render_official_alerts_unavailable_html()
        if any_official_alerts_unavailable(locations) else ""
    )

    overview_html = (
        f'<div style="padding:6px 24px 0;">'
        f'{_render_section_head("ÜBERSICHT", "Alle Orte · gewählte Metriken", "← scrollen")}'
        f'{_render_overview_table(locations, enabled_metrics, corridors)}</div>'
    )
    # Issue #1278 (Nebenbefund, AC-12): die dritte Angabe war fest "09–16 Uhr" --
    # ein toter Rest des mit #1268 abgeschafften Zeitfensters. Die Bewertung
    # laeuft seit #1268 ueber den ganzen Tag; die Angabe behauptete eine
    # Einschraenkung, die es nicht gibt. Ersatzlos leer (analog zur bereits
    # entfernten Zeitfenster-Zeile im Klartext-Header, comparison.py:77).
    hourly_head_html = (
        f'<div style="padding:26px 24px 0;">'
        f'{_render_section_head("STUNDEN", "Stundenverlauf · alle Orte", "")}</div>'
    ) if hourly_enabled else ""

    # Issue #1323: der 3-Tage-Ausblick je Ort (Epic #1301 B4) steht direkt
    # unter dessen eigener Stundentabelle, statt als Sammelblock hinter
    # allen Orten. Eine Per-Ort-Schleife (Reihenfolge = Uebersichts-Spalten)
    # statt zwei getrennt gejointen Bloecken. Fail-soft je Ort bleibt
    # erhalten (_render_location_section/_render_location_outlook liefern
    # bei fehlenden Daten "").
    def _per_location(loc, i: int) -> str:
        section = (
            _render_location_section(loc, i, hourly_metrics, corridors)
            if hourly_enabled else ""
        )
        if not outlook_enabled:
            return section
        # Issue #1368: der Ausblick-Kopf nennt den Ort nur dann, wenn der
        # Stundenblock desselben Ortes ihn nicht schon nennt (abgeschalteter
        # Stundenverlauf, fehlende Stundendaten) — sonst waere der Block
        # ortslos.
        return section + _render_location_outlook(
            loc, i, outlook_metrics, with_location=not section,
        )

    per_location_html = "".join(
        _per_location(loc, i) for i, loc in enumerate(locations)
    )

    # Issue #1461 S3b-1: derselbe Baustein wie im Trip-Briefing (kein Nachbau,
    # Teilungs-Invariante). Zeitbasis ist die Kopfzeilen-Zeitzone des
    # erstgenannten Ortes -- `render_compare_html()` kennt keine eigene `tz`.
    from output.renderers.email.undelivered_hint import (
        has_undelivered, render_undelivered_html,
    )
    undelivered_html = (
        render_undelivered_html(undelivered, tz=header_tz)
        if has_undelivered(undelivered) else ""
    )

    legend_html = _render_legend(hourly_metrics, hourly_enabled)
    abo_html = _render_abo_footer(preset_name, preset_schedule, preset_weekday, len(locations), sig)
    app_footer_html = _render_app_footer()

    # Nur nicht-leere Bloecke einreihen (kein Doppel-Newline durch leeren
    # Warn-Lead/keine Warnungen, analog zur Anti-Erosion-Regel aus #1034).
    body_html = "\n".join(
        part for part in (
            header_html, warnings_html, warn_banner_html, unavailable_banner_html,
            overview_html, hourly_head_html, per_location_html,
            undelivered_html, legend_html, abo_html, app_footer_html,
        ) if part
    )

    # Adversary F001(b): zusaetzliche <style>-Regel als Backup fuer Clients,
    # die Klassen respektieren -- nur bei tatsaechlich konfigurierten
    # Korridoren, damit corridors=None/[] das HTML byte-identisch laesst
    # (Baseline-Schutz, s. test_kein_corridor_rendert_wie_bisher).
    mark_css = f".corridor-mark {{ border-left:3px solid {G_SUCCESS} !important; }}\n" if corridors else ""

    style_block = f"""<style>
body {{ margin:0;padding:0;background:{G_PAPER};font-family:{FONT_UI};color:{G_INK}; }}
.container {{ max-width:680px;margin:0 auto;background:#ffffff; }}
table {{ border-collapse:collapse; }}
th, td {{ vertical-align:top; }}
{mark_css}@media (max-width: 480px) {{
    .container {{ max-width:100% !important; }}
    .header-stats-desktop {{ display:none !important; }}
    .header-stats-mobile {{ display:table !important; }}
    table {{ font-size:12px !important; }}
    .header-wrapper {{ padding:18px !important; }}
}}
</style>"""

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Orts-Vergleich</title>
{WEB_FONT_LINK}
{style_block}
</head>
<body>
<div class="container">
{body_html}
</div>
</body>
</html>"""


__all__ = [
    "render_compare_html",
    "CV2_METRICS",
    "HOUR_METRICS",
    "derive_row_labels",
    "has_visible_hour_columns",
    "location_render_order",
]
