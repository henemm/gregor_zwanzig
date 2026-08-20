"""
MetricCatalog - Single Source of Truth for weather metrics.

SPEC: docs/specs/modules/weather_config.md v2.0

Defines all available weather metrics with:
- ForecastDataPoint field mapping
- Provider availability
- UI labels and units
- Default aggregations
- Formatter column definitions
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models import UnifiedWeatherDisplayConfig
    from app.profile import ActivityProfile


@dataclass(frozen=True)
class MetricDefinition:
    """Definition of a single weather metric."""
    id: str
    label_de: str
    unit: str
    dp_field: str
    category: str  # temperature, wind, precipitation, atmosphere, winter
    default_aggregations: tuple[str, ...]
    compact_label: str
    col_key: str
    col_label: str
    providers: dict[str, bool]
    default_enabled: bool = True
    friendly_label: str = ""
    summary_fields: dict[str, str] = field(default_factory=dict)
    default_change_threshold: Optional[float] = None
    # #1435 E1a: Alarmfaehigkeit haengt am Paar (Groesse, Auswertung).
    # alert_metrics: Auswertung -> Alarm-Identitaet (AlertMetric-Wert), strukturell
    # parallel zu summary_fields. Nur Identitaeten, die die Auswertungskette
    # (weather_change_detection._ALERT_METRIC_TO_CATALOG_ID) auch erreichen kann --
    # sonst waere es ein Bedienelement ohne Wirkung (Epic #1374 Invariante 1).
    alert_metrics: dict[str, str] = field(default_factory=dict)
    # Aenderungsraten-Alarm: KEINE Auswertung, deshalb orthogonal zu alert_metrics
    # (dessen Schluessel muessen echte Auswertungen aus _AGGREGATION_ORDER sein).
    change_alert_metric: Optional[str] = None
    display_unit: str = ""  # Unit for legend if different from `unit` (e.g. "km" for visibility)
    # RISK-04: Configurable display/risk thresholds (catalog defaults)
    display_thresholds: dict[str, float] = field(default_factory=dict)
    highlight_threshold: Optional[float] = None
    risk_thresholds: dict[str, float] = field(default_factory=dict)
    exposition_risk_thresholds: dict[str, float] = field(default_factory=dict)
    # Issue #435: Format-Modi pro Metrik. SPEC docs/specs/modules/issue_435_metric_format_modes.md
    # Erlaubte Werte: "raw" | "scale" | "simplified" | "symbol"
    format_modes: tuple[str, ...] = ("raw",)
    default_format_mode: str = "raw"
    # Issue #1948 S3: die Groesse ist eine Stufenleiter (0-3), keine Messzahl --
    # Alarm-SMS rendert sie als Buchstaben (LEVELS, output/tokens/metrics.py)
    # statt als Rohzahl. Bewusst getrennt von default_format_mode="symbol", das
    # auch nicht-stufige Groessen wie CAPE traegt.
    is_level: bool = False
    # Issue #710/#715: selectable=False excludes a metric from the user-visible
    # catalog (get_all_metrics(), /api/metrics) while keeping it in _METRICS for
    # internal computation/aggregation (e.g. confidence for forecast hints).
    # PO-Regel (dauerhaft): confidence ist KEINE waehlbare Wetter-Metrik.
    selectable: bool = True
    # Issue #914 Slice 1: Alert-Render-Stammdaten (Single Source of Truth)
    sms_code: str = ""           # GSM-7-tauglicher Token (1–2 Großbuchstaben, ASCII), kollisionsfrei
    # Fix #1887 E6 Scheibe A: das tatsaechlich in der Trip-Kurzform gesendete
    # Kuerzel dieser Groesse -- bewusst GETRENNT von sms_code (das fuer
    # Compare-/Alarm-SMS gilt und mit demselben Kuerzel wie eine andere
    # Groesse kollidieren darf, s. temperature/temperature_cold/wind_chill).
    # Quelle fuer SMS_MULTI_SYMBOLS_BY_METRIC (dort abgeleitet, nicht mehr
    # danebengepflegt).
    sms_multi_symbols: tuple[str, ...] = ()
    decimals: Optional[int] = None  # Rundungsstellen für Darstellung; None => Einheit-Heuristik
    cmp: str = ""                # "über" | "unter" — Seite, auf der die Schwelle alarmiert
    # Issue #952: Kurzform-Label für Nicht-SMS-Alert-Renderer (E-Mail/Telegram/Betreff).
    # Fällt in get_alert_label() auf label_de zurück, wenn leer.
    alert_label: str = ""
    # Issue #914 / ADR-0010: Vorboten-Metriken haben sms_code + default_change_threshold
    # für Katalog-Vollständigkeit, lösen aber KEINEN Abweichungs-Alert aus.
    # from_display_config() und from_alert_rules() ignorieren is_precursor=True.
    is_precursor: bool = False
    # Issue #1552: reine Zusatz-Markierung "gehoert zum Trip-Anlege-Standard",
    # unabhaengig von default_enabled (das Orte/Abonnements weiter versorgt).
    # Gesetzt auf genau 7 Groessen mit expliziter Rangfolge (Reihenfolge der
    # Sieben-ID-Liste in DEFAULT_TRIP_METRIC_IDS, trip_metric_ids.py).
    trip_default_rank: Optional[int] = None

    @property
    def has_friendly_format(self) -> bool:
        return bool(self.friendly_label)


# Issue #1468: Auswertung "Beginn des Ereignisses". Bewusst KEIN Eintrag in
# `_AGGREGATION_ORDER` -- der Beginn ist keine vom Nutzer waehlbare
# Zusammenfassung einer Stundenreihe, sondern ein Zeitpunkt. Er traegt
# trotzdem einen `summary_fields`-Schluessel, weil das Alarm-Protokoll (#1954)
# seine Register-Paare ueber genau diese Zuordnung bildet.
ONSET_AGGREGATION: str = "onset"

# --- Metric Registry ---

_METRICS: list[MetricDefinition] = [
    # === TEMPERATURE ===
    MetricDefinition(
        id="temperature", label_de="Temperatur", unit="°C",
        dp_field="t2m_c", category="temperature",
        default_aggregations=("min", "max", "avg"),
        compact_label="T", col_key="temp", col_label="Temp",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"min": "temp_min_c", "max": "temp_max_c", "avg": "temp_avg_c"},
        default_change_threshold=5.0,
        # #1435 E1a: beide Richtungen haengen an der SICHTBAREN Groesse; die
        # interne Pseudo-Groesse temperature_cold bleibt ohne Deklaration.
        alert_metrics={"min": "temperature_min", "max": "temperature_max"},
        change_alert_metric="temperature_change",
        # Issue #1377 Scheibe A (PO-Entscheidung 2026-07-28): beidseitige
        # Ampel-Schwellen -- Hitze (yellow/orange/red) UND Kaelte
        # (yellow_lt/orange_lt/red_lt). Identisch zu wind_chill (s. dort).
        display_thresholds={
            "yellow": 28.0, "orange": 31.0, "red": 34.0,
            "yellow_lt": 0.0, "orange_lt": -5.0, "red_lt": -15.0,
        },
        sms_code="D", decimals=0, cmp="über", alert_label="Temp",
        trip_default_rank=1,  # Issue #1552: Trip-Anlege-Standard, Rang 1
    ),
    # Issue #914: Internal-only entry for AlertMetric.TEMPERATURE_MIN (Kältealarm).
    # cmp="unter" because cold alarm fires when temp_min_c FALLS BELOW threshold.
    # selectable=False: never shown in user catalog or /api/metrics.
    # The "temperature" entry (above) covers the warm direction (cmp="über").
    MetricDefinition(
        id="temperature_cold", label_de="Tiefsttemperatur-Alarm", unit="°C",
        dp_field="t2m_c", category="temperature",
        default_aggregations=("min",),
        compact_label="TN", col_key="temp_cold", col_label="TmpMin",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"min": "temp_min_c"},
        sms_code="N", decimals=0, cmp="unter", alert_label="Temp",
        selectable=False,
    ),
    # Issue #1484: Nacht-Tiefsttemperatur am Etappenziel als EIGENE waehlbare
    # Groesse, getrennt von "temperature" (K/D). PO 2026-08-03: "N soll
    # getrennt waehlbar sein." Traegt das N-Kuerzel der Trip-SMS (Bindung:
    # sms_trip.SMS_MULTI_SYMBOLS_BY_METRIC), erscheint nur im Abend-Briefing.
    # NICHT temperature_cold (Alarm-Pseudogroesse, #914, s.o.). Der Wert
    # entsteht im Nachtfenster (day_window.night_temp_min_c), nicht aus einem
    # Etappen-Aggregat -- deshalb keine summary_fields (= keine Auswertungs-
    # Pills, keine Tabellenspalte) und keine Alarm-Deklaration (Kaeltealarm
    # bleibt temperature_cold).
    MetricDefinition(
        id="temperature_night", label_de="Nacht-Tiefsttemperatur", unit="°C",
        dp_field="t2m_c", category="temperature",
        default_aggregations=("min",),
        compact_label="TN", col_key="temp_night", col_label="Night",
        providers={"openmeteo": True, "geosphere": True},
        # Fix #1887 E6 Scheibe A (AC-3): der DEC-8-Kompromiss "TN" ist
        # aufgehoben, nicht nur verschoben -- "TN" erreichte KEINEN der
        # beiden get_sms_code()-Leser (comparison.py:647, alert/render.py:93)
        # und war damit ein toter Wert. Das tatsaechlich gesendete Kuerzel
        # "N" traegt jetzt ausschliesslich sms_multi_symbols; sms_code ist
        # leer (deckt sich mit "nicht gesetzt", get_sms_code() liefert "").
        sms_code="",
        sms_multi_symbols=("N",),
        decimals=0,
    ),
    # Issue #1728 Scheibe 1: Tages-Tief und Tages-Hoch der GEMESSENEN
    # Temperatur als je eigene waehlbare Groesse (PO 2026-08-11), Muster
    # temperature_night (#1484, s.o.). Reine Sichtbarkeits-Gates fuer die
    # SMS-Token K/D: KEINE summary_fields (= keine Auswertungs-Pills, keine
    # Tabellenspalte), keine Alarm-Deklaration. Der Zahlenwert kommt
    # unveraendert aus der Gehzeit-Aggregation in sms_trip.py.
    # 🔴 Gehzeit-Fensterung (collect_hiking_window_points()), NICHT das
    # Tagesfenster 04-19 von temperature_min/temperature_max
    # (Alarm-Vokabular, models.py:1123-1124) -- zwei fachlich verschiedene
    # Dinge mit aehnlichem Namen, in getrennten Namensraeumen.
    MetricDefinition(
        id="temperature_day_low", label_de="Tages-Tiefsttemperatur (Gehzeit)",
        unit="°C", dp_field="t2m_c", category="temperature",
        default_aggregations=("min",),
        compact_label="L", col_key="temp_day_low", col_label="DayMin",
        providers={"openmeteo": True, "geosphere": True},
        sms_code="L", sms_multi_symbols=("L",), decimals=0,
        trip_default_rank=8,  # Issue #1728: neue Rangstufe, keine Umnummerierung
    ),
    # Wie temperature_day_low, Gegenrichtung. Fix #1887 E6 Scheibe A (AC-3):
    # der DEC-8-Kompromiss "TD" ist aufgehoben, nicht nur verschoben -- "TD"
    # erreichte KEINEN der beiden get_sms_code()-Leser (comparison.py:647,
    # alert/render.py:93) und war damit ein toter Wert. Das tatsaechlich
    # gesendete Kuerzel "D" traegt jetzt ausschliesslich sms_multi_symbols;
    # sms_code ist leer.
    # 🔴 Gehzeit-Fensterung (collect_hiking_window_points()), NICHT das
    # Tagesfenster 04-19 von temperature_min/temperature_max.
    MetricDefinition(
        id="temperature_day_high", label_de="Tages-Höchsttemperatur (Gehzeit)",
        unit="°C", dp_field="t2m_c", category="temperature",
        default_aggregations=("max",),
        compact_label="D", col_key="temp_day_high", col_label="DayMax",
        providers={"openmeteo": True, "geosphere": True},
        sms_code="",
        sms_multi_symbols=("D",),
        decimals=0,
        trip_default_rank=9,
    ),
    MetricDefinition(
        id="wind_chill", label_de="Gefühlte Temperatur", unit="°C",
        dp_field="wind_chill_c", category="temperature",
        default_aggregations=("min", "max"),
        compact_label="TF", col_key="felt", col_label="Feels",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"min": "wind_chill_min_c", "max": "wind_chill_max_c"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert.
        # is_precursor=True verhindert Alerts in from_display_config/from_alert_rules.
        default_change_threshold=None,
        # Issue #1377 Scheibe A (PO-Entscheidung 2026-07-28): dieselben Werte
        # wie "temperature" -- zwei Spalten mit demselben Mass duerfen nicht
        # verschieden faerben. risk_thresholds (Alarme) bleibt unangetastet,
        # das ist ein anderer Zweck.
        display_thresholds={
            "yellow": 28.0, "orange": 31.0, "red": 34.0,
            "yellow_lt": 0.0, "orange_lt": -5.0, "red_lt": -15.0,
        },
        risk_thresholds={"high_lt": -20.0},
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label (keine
        # neue Abkuerzungsregel, s. Spec compare_kanal_metriken.md Punkt 3).
        sms_code="TF",
    ),
    # Issue #1660 Scheibe A: gefuehlte Nacht-Tiefsttemperatur am Etappenziel
    # als EIGENE waehlbare Groesse, getrennt von "wind_chill" (FK/FD).
    # Exakt nach dem Muster von "temperature_night" (#1484, s.o.) -- nur auf
    # der gefuehlten Seite. Traegt das FN-Kuerzel der Trip-SMS (Bindung:
    # sms_trip.SMS_MULTI_SYMBOLS_BY_METRIC), erscheint nur im Abend-Briefing.
    # Der Wert entsteht im Nachtfenster (day_window.night_wind_chill_min_c),
    # nicht aus einem Etappen-Aggregat -- deshalb keine summary_fields (=
    # keine Auswertungs-Pill, keine Tabellenspalte) und keine
    # Alarm-Deklaration (Kaeltealarm bleibt temperature_cold, der gefuehlte
    # Risikowert bleibt bei "wind_chill"). Fix #1887 E6 Scheibe A
    # (PO-Entscheid): "WC" (vormals Wintersport-Tageskennzahl bei
    # "wind_chill") entfaellt ERSATZLOS -- verdoppelte nachweislich "FK".
    MetricDefinition(
        id="wind_chill_night", label_de="Gefühlte Nacht-Tiefsttemperatur",
        unit="°C", dp_field="wind_chill_c", category="temperature",
        default_aggregations=("min",),
        compact_label="TFN", col_key="felt_night", col_label="NightF",
        providers={"openmeteo": True, "geosphere": True},
        # sms_code = "FN": identisch mit dem SMS-Token-Symbol, das die
        # Groesse traegt (#1435 E3b Registerkonformitaet) -- kollisionsfrei
        # geprueft gegen alle heutigen sms_code-Werte des Katalogs.
        sms_code="FN",
        sms_multi_symbols=("FN",),
        decimals=0,
    ),
    # Issue #1728 Scheibe 1: dieselbe Aufloesung auf der GEFUEHLTEN Seite
    # (SMS-Token FK/FD), Muster wind_chill_night (#1660 A, s.o.). Ebenfalls
    # reine Sichtbarkeits-Gates ohne summary_fields und ohne Alarm.
    # KEIN trip_default_rank -- folgt exakt der heutigen Lage von
    # "wind_chill" (waehlbar, aber bei neuen Trips nicht vorbelegt, DEC-7).
    # Fix #1887 E6 Scheibe A (PO-Entscheid): "WC" (vormals Wintersport-
    # Tageskennzahl bei "wind_chill") entfaellt ERSATZLOS -- verdoppelte
    # nachweislich "FK" (identisches Feld, Fenster, Aggregation).
    # 🔴 Gehzeit-Fensterung (collect_hiking_window_points()), NICHT das
    # Tagesfenster 04-19 von temperature_min/temperature_max.
    MetricDefinition(
        id="wind_chill_day_low",
        label_de="Gefühlte Tages-Tiefsttemperatur (Gehzeit)",
        unit="°C", dp_field="wind_chill_c", category="temperature",
        default_aggregations=("min",),
        compact_label="FL", col_key="felt_day_low", col_label="DayMinF",
        providers={"openmeteo": True, "geosphere": True},
        sms_code="FL", sms_multi_symbols=("FL",), decimals=0,
    ),
    # 🔴 Gehzeit-Fensterung (collect_hiking_window_points()), NICHT das
    # Tagesfenster 04-19 von temperature_min/temperature_max.
    MetricDefinition(
        id="wind_chill_day_high",
        label_de="Gefühlte Tages-Höchsttemperatur (Gehzeit)",
        unit="°C", dp_field="wind_chill_c", category="temperature",
        default_aggregations=("max",),
        compact_label="FD", col_key="felt_day_high", col_label="DayMaxF",
        providers={"openmeteo": True, "geosphere": True},
        sms_code="FD", sms_multi_symbols=("FD",), decimals=0,
    ),
    MetricDefinition(
        id="humidity", label_de="Luftfeuchtigkeit", unit="%",
        dp_field="humidity_pct", category="temperature",
        default_aggregations=("avg",),
        compact_label="H", col_key="humidity", col_label="Humid",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "humidity_avg_pct"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert.
        # is_precursor=True verhindert Alerts in from_display_config/from_alert_rules.
        default_change_threshold=None,
        sms_code="HU", decimals=0, cmp="über", is_precursor=True, alert_label="Feuchte",
    ),
    MetricDefinition(
        id="dewpoint", label_de="Taupunkt", unit="°C",
        dp_field="dewpoint_c", category="temperature",
        default_aggregations=("avg",),
        # Issue #1453: "Cond°" benannte keine Groesse (Taupunkt ist kein
        # Kondensationsgrad) -- die Kurzform nennt jetzt die Groesse selbst.
        compact_label="DP", col_key="dewpoint", col_label="Dew",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "dewpoint_avg_c"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert.
        default_change_threshold=None,
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="DP",
    ),
    # === WIND ===
    MetricDefinition(
        id="wind", label_de="Wind", unit="km/h",
        dp_field="wind10m_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="W", col_key="wind", col_label="Wind",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"max": "wind_max_kmh"},
        default_change_threshold=20.0,
        # #1435 E1a: Wind hat KEINEN absoluten Alarm -- "wind_gust" gehoert
        # ausschliesslich zu "gust" (Entkreuzung, AC-1).
        change_alert_metric="wind_change",
        display_thresholds={"yellow": 30.0, "orange": 50.0, "red": 70.0},
        highlight_threshold=50.0,
        risk_thresholds={"medium": 50.0, "high": 70.0},
        exposition_risk_thresholds={"medium": 30, "high": 50},
        format_modes=("raw", "simplified"),
        default_format_mode="raw",
        sms_code="W", decimals=0, cmp="über", alert_label="Wind",
        trip_default_rank=2,  # Issue #1552: Trip-Anlege-Standard, Rang 2
    ),
    MetricDefinition(
        id="gust", label_de="Böen", unit="km/h",
        dp_field="gust_kmh", category="wind",
        default_aggregations=("max",),
        compact_label="G", col_key="gust", col_label="Gust",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"max": "gust_max_kmh"},
        default_change_threshold=20.0,
        alert_metrics={"max": "wind_gust"},  # #1435 E1a
        # Issue #1377 Scheibe A (PO-Entscheidung 2026-07-28): 30/45/60 statt
        # 50/65/80 -- vormals wich der Punkt-/Klartext-Wert von der
        # Zellfarbe derselben Mail ab, die schon 30 km/h nutzte.
        display_thresholds={"yellow": 30.0, "orange": 45.0, "red": 60.0},
        highlight_threshold=60.0,
        risk_thresholds={"medium": 50.0, "high": 70.0},
        exposition_risk_thresholds={"medium": 40, "high": 60},
        format_modes=("raw", "simplified"),
        default_format_mode="raw",
        sms_code="G", decimals=0, cmp="über", alert_label="Böen",
        trip_default_rank=3,  # Issue #1552: Trip-Anlege-Standard, Rang 3
    ),
    MetricDefinition(
        id="wind_direction", label_de="Windrichtung", unit="°",
        dp_field="wind_direction_deg", category="wind",
        default_aggregations=("avg",),
        compact_label="WD", col_key="wind_dir", col_label="WDir",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "wind_direction_avg_deg"},
        friendly_label="N/S/W/E",
        # Circular mean: no numeric delta comparison for alerts
        format_modes=("raw", "scale"),
        default_format_mode="scale",
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="WD",
    ),
    # === PRECIPITATION ===
    MetricDefinition(
        id="precipitation", label_de="Niederschlag", unit="mm",
        dp_field="precip_1h_mm", category="precipitation",
        default_aggregations=("sum",),
        compact_label="R", col_key="precip", col_label="Rain",
        providers={"openmeteo": True, "geosphere": True},
        summary_fields={"sum": "precip_sum_mm",
                        ONSET_AGGREGATION: "precip_heavy_onset_utc"},  # #1468
        default_change_threshold=10.0,
        alert_metrics={"sum": "precipitation_sum",
                       ONSET_AGGREGATION: "precipitation_heavy_onset"},  # #1435 E1a, #1468
        change_alert_metric="precipitation_change",
        display_thresholds={"yellow": 1.0, "orange": 5.0, "red": 10.0},
        risk_thresholds={"medium": 20.0},
        format_modes=("raw", "simplified"),
        default_format_mode="raw",
        sms_code="R", decimals=1, cmp="über", alert_label="Niedersch",
        trip_default_rank=4,  # Issue #1552: Trip-Anlege-Standard, Rang 4
    ),
    MetricDefinition(
        id="rain_probability", label_de="Regenwahrscheinlichkeit", unit="%",
        dp_field="pop_pct", category="precipitation",
        default_aggregations=("max",),
        compact_label="P%", col_key="pop", col_label="Rain%",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        summary_fields={"max": "pop_max_pct"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert über
        # from_display_config (is_precursor=True). default_change_threshold gesetzt
        # für Katalog-Vollständigkeit (sms_code PR).
        default_change_threshold=20.0,
        display_thresholds={"yellow": 30.0, "orange": 60.0, "red": 80.0},
        highlight_threshold=80.0,
        risk_thresholds={"medium": 80},
        sms_code="PR", decimals=0, cmp="über", is_precursor=True, alert_label="Regen%",
    ),
    # === FORECAST CONFIDENCE (Issue #121) ===
    # Issue #710/#715 PO-Regel (dauerhaft): confidence ist KEINE waehlbare
    # Wetter-Metrik. selectable=False schliesst sie aus dem user-sichtbaren
    # Katalog aus. Die MetricDefinition bleibt fuer interne Berechnung/
    # Aggregation/Vorhersage-Hinweis (build_confidence_hint, SMS-Symbol) erhalten.
    MetricDefinition(
        id="confidence", label_de="Sicherheit", unit="%",
        dp_field="confidence_pct", category="atmosphere",
        default_aggregations=("min",),
        compact_label="Conf", col_key="confidence", col_label="Conf",
        providers={"openmeteo": True, "geosphere": False},
        summary_fields={"min": "confidence_pct_min"},
        default_enabled=False,
        selectable=False,
    ),
    MetricDefinition(
        id="thunder", label_de="Gewitter", unit="",
        dp_field="thunder_level", category="precipitation",
        default_aggregations=("max",),
        compact_label="⚡", col_key="thunder", col_label="Thdr",
        providers={"openmeteo": True, "geosphere": False},
        summary_fields={"max": "thunder_level_max",
                        ONSET_AGGREGATION: "thunder_onset_utc"},  # #1468
        default_change_threshold=1.0,
        alert_metrics={"max": "thunder_level",
                       ONSET_AGGREGATION: "thunder_onset"},  # #1435 E1a, #1468
        friendly_label="⚡",
        # Issue #814 AC-6: "raw" in format_modes erlaubt explizites format_mode="raw"
        # im Renderer (matrix test setzt mc.format_mode="raw"). Der #435-Fallback-Test
        # nutzt jetzt temperature als Beispiel-Metrik (thunder hat seit #814 legitimerweise
        # raw+symbol). use_friendly_format=False-Pfad (loader.py:68) umgeht Validierung.
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        sms_code="TH", decimals=0, cmp="über", alert_label="Gewitter",
        is_level=True,  # Issue #1948 S3
        trip_default_rank=5,  # Issue #1552: Trip-Anlege-Standard, Rang 5
    ),
    MetricDefinition(
        id="cape", label_de="Gewitterenergie (CAPE)", unit="J/kg",
        dp_field="cape_jkg", category="precipitation",
        default_aggregations=("max",),
        compact_label="CP", col_key="cape", col_label="CAPE",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\U0001f7e2\U0001f7e1\U0001f534",
        summary_fields={"max": "cape_max_jkg"},
        default_change_threshold=500.0,
        alert_metrics={"max": "cape"},  # #1435 E1a
        # Workflow fix-briefing-grid-and-summary (PO-go 2026-07-22, CAPE-
        # Bergkalibrierung): Berg-Gewitter triggern orographisch bei deutlich
        # niedrigerem CAPE als die Flachland-Konvektionsskala (vormals
        # yellow:1000/orange:2500/red:3500) — dauergrün trotz realer
        # Gewitterwarnung. Neu kalibriert fuer Gebirgs-Kontext.
        # default_change_threshold (Alarm-Schwelle) bewusst unveraendert
        # (separate Metrik-Bedeutung).
        display_thresholds={"yellow": 300.0, "orange": 800.0, "red": 1500.0},
        highlight_threshold=1000.0,
        # risk_thresholds bewusst NICHT gesetzt (Issue #1592 Scheibe C2,
        # AC-7): die Leiter 1000/2000 J/kg war unbelegt und wurde nur von
        # der gestrichenen CAPE-Regel der RiskEngine gelesen.
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        sms_code="CP", decimals=0, cmp="über", alert_label="CAPE",
        # Issue #1585 (PO-Regel 2026-08-10, Muster ADR-0005/#710): CAPE ist
        # fachlich nur eine Zutat der Gewitterstufen-Fusion, keine fuer sich
        # entscheidungsrelevante Groesse. Die Definition bleibt vollstaendig
        # erhalten -- die interne Berechnung (thunder_level_from_signals,
        # CAPE-Delta-Alarm #1592) liest cape_jkg direkt aus den Rohdaten.
        selectable=False,
    ),
    MetricDefinition(
        id="snowfall_limit", label_de="Schneefallgrenze", unit="m",
        dp_field="snowfall_limit_m", category="precipitation",
        default_aggregations=("min", "max"),
        compact_label="SL", col_key="snow_limit", col_label="SnowL",
        providers={"openmeteo": False, "geosphere": True},
        # Issue #1391: MIN -- _compute_snowfall_limit() (weather_metrics.py)
        # rechnet das Minimum ueber die Segment-Stunden (kanonische Trip-Regel).
        summary_fields={"min": "snowfall_limit_m"},
        default_change_threshold=200.0,
        sms_code="SL", decimals=0, cmp="unter", alert_label="0°-Grenze",
    ),
    MetricDefinition(
        id="precip_type", label_de="Niederschlagsart", unit="",
        dp_field="precip_type", category="precipitation",
        default_aggregations=("max",),
        compact_label="PT", col_key="precip_type", col_label="PType",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"max": "precip_type_dominant"},
        # Enum type: no numeric delta comparison for alerts
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="PT",
    ),
    # === ATMOSPHERE ===
    MetricDefinition(
        id="cloud_total", label_de="Bewölkung", unit="%",
        dp_field="cloud_total_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="C", col_key="cloud", col_label="Cloud",
        providers={"openmeteo": True, "geosphere": True},
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        summary_fields={"avg": "cloud_avg_pct"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert.
        default_change_threshold=None,
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        # Issue #1362 Scheibe S5b: eigener sms_code "CT" (NICHT der eigene
        # compact_label "C" -- zu generisch neben CL/CM/CH, s. Spec
        # compare_kanal_metriken.md Punkt 3).
        sms_code="CT",
    ),
    MetricDefinition(
        id="cloud_low", label_de="Tiefe Wolken", unit="%",
        dp_field="cloud_low_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CL", col_key="cloud_low", col_label="CldLow",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # Issue #1392: Tages-Mittelwert (gerundet, analog cloud_total).
        summary_fields={"avg": "cloud_low_avg_pct"},
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="CL",
    ),
    MetricDefinition(
        id="cloud_mid", label_de="Mittelhohe Wolken", unit="%",
        dp_field="cloud_mid_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CM", col_key="cloud_mid", col_label="CldMid",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # Issue #1392: Tages-Mittelwert (gerundet, analog cloud_total).
        summary_fields={"avg": "cloud_mid_avg_pct"},
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="CM",
    ),
    MetricDefinition(
        id="cloud_high", label_de="Hohe Wolken", unit="%",
        dp_field="cloud_high_pct", category="atmosphere",
        default_aggregations=("avg",),
        compact_label="CH", col_key="cloud_high", col_label="CldHi",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        friendly_label="\u2600\ufe0f\u26c5\u2601\ufe0f",
        # Issue #1392: Tages-Mittelwert (gerundet, analog cloud_total).
        summary_fields={"avg": "cloud_high_avg_pct"},
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        # Issue #1362 Scheibe S5b: sms_code = bestehender compact_label.
        sms_code="CH",
    ),
    MetricDefinition(
        id="visibility", label_de="Sichtweite", unit="m",
        dp_field="visibility_m", category="atmosphere",
        default_aggregations=("min",),
        compact_label="V", col_key="visibility", col_label="Visib",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        # Issue #814 AC-5 / #819: Sicht ist numerisch-only (immer km-Zahl). Kein Einfach-Modus → has_friendly_format=False, nur Roh-Modus.
        display_unit="km",
        summary_fields={"min": "visibility_min_m"},
        default_change_threshold=1000,
        alert_metrics={"min": "visibility"},  # #1435 E1a
        # Issue #1377 Scheibe A (PO-Entscheidung 2026-07-28): vollstaendig
        # invertierte Dreier-Staffel statt bisher nur orange_lt allein --
        # die Klartext-Zeile blieb dadurch bisher IMMER gruen (F001-artig).
        display_thresholds={
            "yellow_lt": 2000.0, "orange_lt": 1000.0, "red_lt": 500.0,
        },
        risk_thresholds={"high_lt": 100.0},
        format_modes=("raw",),
        default_format_mode="raw",
        sms_code="VS", decimals=1, cmp="unter", alert_label="Sicht",
        trip_default_rank=7,  # Issue #1552: Trip-Anlege-Standard, Rang 7
    ),
    MetricDefinition(
        # #1401 A1: "Sonnenstunden" benennt die Einheit (h) korrekt (PO-Freigabe).
        id="sunshine", label_de="Sonnenstunden", unit="h",
        dp_field="dni_wm2", category="atmosphere",
        default_aggregations=("sum",),
        compact_label="☀", col_key="sunshine", col_label="Sun",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=True,
        friendly_label="☀️🌙☁️",
        # Issue #347: Sonnenstunden (h) statt DNI-Mittelwert (W/m²); DNI bleibt
        # intern als Hilfsgröße (Emoji-Logik) erhalten.
        summary_fields={"sum": "sunny_hours"},
        format_modes=("raw", "symbol"),
        default_format_mode="symbol",
        decimals=1,
        # Issue #1362 Scheibe S5b: eigener sms_code "SU" -- der eigene
        # compact_label ist das Emoji "☀", nicht GSM-7/ASCII-tauglich
        # (s. Spec compare_kanal_metriken.md Punkt 3).
        sms_code="SU",
    ),
    MetricDefinition(
        id="uv_index", label_de="UV-Index", unit="",
        dp_field="uv_index", category="atmosphere",
        default_aggregations=("max",),
        compact_label="UV", col_key="uv", col_label="UV",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        summary_fields={"max": "uv_index_max"},
        default_change_threshold=3.0,
        # Issue #1377 Scheibe A (PO-Entscheidung 2026-07-28): erstmals
        # Ampel-Schwellen -- bisher lieferte severity_for() hier "keine
        # Aussage".
        display_thresholds={"yellow": 3.0, "orange": 6.0, "red": 8.0},
        sms_code="UV", decimals=0, cmp="über", alert_label="UV-Index",
    ),
    MetricDefinition(
        id="pressure", label_de="Luftdruck", unit="hPa",
        dp_field="pressure_msl_hpa", category="atmosphere",
        default_aggregations=("avg",),
        # Issue #1453: "hPa" war die Einheit, nicht der Name der Groesse.
        compact_label="P", col_key="pressure", col_label="Press",
        providers={"openmeteo": True, "geosphere": True},
        default_enabled=False,
        summary_fields={"avg": "pressure_avg_hpa"},
        # Issue #889 / ADR-0010: Vorboten-Metrik — kein Abweichungs-Alert.
        default_change_threshold=None,
        # Issue #1362 Scheibe S5b: eigener sms_code "HP" (Hektopascal) --
        # der eigene compact_label ist "P", zu dicht an "R"/"PR"
        # (Niederschlag/Regenwahrscheinlichkeit), s. Spec Punkt 3.
        sms_code="HP",
    ),
    # === WINTER ===
    MetricDefinition(
        id="freezing_level", label_de="Nullgradgrenze", unit="m",
        dp_field="freezing_level_m", category="winter",
        default_aggregations=("min", "max"),
        compact_label="FZ", col_key="freeze_lvl", col_label="0°Line",
        providers={"openmeteo": True, "geosphere": False},
        default_enabled=False,
        # Single field on SegmentWeatherSummary (not min/max split)
        summary_fields={"min": "freezing_level_m"},
        default_change_threshold=200,
        alert_metrics={"min": "freezing_level"},  # #1435 E1a
        sms_code="FZ", decimals=0, cmp="unter", alert_label="Nullgradgrenze",
        trip_default_rank=6,  # Issue #1552: Trip-Anlege-Standard, Rang 6
    ),
    MetricDefinition(
        id="snow_depth", label_de="Schneehöhe", unit="cm",
        dp_field="snow_depth_cm", category="winter",
        default_aggregations=("max",),
        compact_label="SD", col_key="snow_depth", col_label="SnowH",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"max": "snow_depth_cm"},
        default_change_threshold=10.0,
        sms_code="SD", decimals=0, cmp="über", alert_label="Schnee",
    ),
    MetricDefinition(
        id="fresh_snow", label_de="Neuschnee", unit="cm",
        dp_field="snow_new_24h_cm", category="winter",
        default_aggregations=("sum",),
        compact_label="NS", col_key="fresh_snow", col_label="NewSn",
        providers={"openmeteo": False, "geosphere": True},
        default_enabled=False,
        summary_fields={"sum": "snow_new_sum_cm"},
        default_change_threshold=5.0,
        alert_metrics={"sum": "fresh_snow"},  # #1435 E1a
        # PO-Korrektur 2026-07-29 (Adversary-Fund #1362 S5b): "SN" kollidierte
        # semantisch mit dem Trip-SMS-Symbol fuer Schneehoehe (sms_trip.py:61,
        # tokens/builder.py:186 -- eigenes, hartcodiertes Trip-Token-Vokabular,
        # nicht ueber get_sms_code()). Neuschnee != Altschnee fuer eine
        # Tourenentscheidung. "NS" = derselbe Wert wie der bestehende
        # compact_label dieser Metrik (kollisionsfrei, mnemonisch).
        sms_code="NS", decimals=0, cmp="über", alert_label="Schnee",
        # Issue #1927 v1.1: erstmals display_thresholds fuer Neuschnee,
        # abgeleitet aus den SLF/EAWS "kritischen Neuschneemengen" (europ.
        # Lawinen-Gefahrenskala): 10-20 cm/24h (unguenstig), 20-30 cm
        # (mittel), 30-50 cm (guenstig) -- konservative untere Bandgrenze je
        # Stufe als Schwelle (gelb=10, orange=20, rot=30).
        display_thresholds={"yellow": 10.0, "orange": 20.0, "red": 30.0},
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# Kurzform-Kürzel — EINE Quelle für SMS, Premium-SMS und Telegram (#1719 S4)
# ═══════════════════════════════════════════════════════════════════════════
# PO 2026-08-12: "Warum gibt es ein extra Telegram Kürzel? Das will ich nicht!"
# `compact_label` (Telegram) wird deshalb ABGELEITET statt zweitgepflegt:
# Vorgabe ist das Kürzel, das die Kurzform tatsächlich sendet; abweichen darf
# nur, was in COMPACT_LABEL_EXCEPTIONS mit Begründung steht.
#
# Die Kürzel-Tabellen wohnen deshalb hier und nicht mehr in `sms_trip.py` --
# der Katalog liest sie beim Ableiten, ein Import in die Gegenrichtung wäre
# zirkulär (sms_trip -> metric_catalog). `sms_trip` re-exportiert sie unter
# den bisherigen Namen; alle bestehenden Importstellen bleiben gültig.

# Issue #624: metric_id -> SMS-Symbol für threshold-fähige Metriken.
#
# Issue #1435 E3b: keine gepflegte Kürzel-Liste mehr, sondern eine ABLEITUNG
# aus dem zentralen Wetter-Register (`sms_code`). Damit kann diese Tabelle
# nicht mehr vom Register abdriften. Die app-freie Formatschicht
# `output/tokens/` darf das Register nicht lesen und führt die Kürzel dort
# weiterhin als Literale (Schichtgrenze, abgesichert durch die Ratsche
# tests/unit/test_sms_token_symbol_register_ratchet.py).
# Issue #1660 Scheibe B Fix-Loop (Muster #1410, DEC-1): die 14 waehlbaren
# Metriken als eigene, benannte Konstante -- Single Source fuer
# _SMS_SYMBOL_METRIC_IDS UNTEN und fuer build_extended_metric_specs()
# (sms_trip.py). Vorher standen dieselben 14 Ids literal in
# _SMS_SYMBOL_METRIC_IDS UND in trip_report.py's disabled-only-Schleife -- das
# Auseinanderdriften war genau die Ursache des Fix-Loop-Bugs (Root-Cause:
# aktive Metriken bekamen NIE eine MetricSpec, nur abgewaehlte).
SMS_NULLFORM_METRIC_IDS: tuple[str, ...] = (
    "humidity",
    "dewpoint",
    "wind_direction",
    "cape",
    "precip_type",
    "cloud_total",
    "cloud_low",
    "cloud_mid",
    "cloud_high",
    "visibility",
    "sunshine",
    "uv_index",
    "pressure",
    "freezing_level",
)

_SMS_SYMBOL_METRIC_IDS: tuple[str, ...] = (
    "precipitation",
    "rain_probability",
    "wind",
    "gust",
    "thunder",
    "snow_depth",
    "snowfall_limit",
    "fresh_snow",
    # Issue #1660 Scheibe B: 14 waehlbare Metriken, bisher ohne SMS-Token.
    # Alle 1:1 (kein Kuerzel-Mehrfach wie wind_chill) -> gehoeren in diese
    # Register-Ableitung, NICHT in SMS_MULTI_SYMBOLS_BY_METRIC (DEC-1).
    *SMS_NULLFORM_METRIC_IDS,
)

# Benannte Ausnahme von der Register-Ableitung: 'TH:' ist Grammatikform (der
# Doppelpunkt trennt die Gewitter-Stufe vom Kürzel ab, builder.py:16), das
# Register kennt nur 'TH'. Ausdrücklich NICHT durch #1435 E3b aufgehoben.
# Fix #1450/Adversary-F001: 'fresh_snow' ebenso -- das Register-Kuerzel ist
# 'NS', der tatsaechlich gerenderte Wintersport-Token ist 'NS24+'
# (builder.py::_wintersport, '24+'-Suffix ist Grammatik fuer das
# 24-Stunden-Fenster). Ohne diese Ausnahme wuerde SMS_SYMBOL_BY_METRIC das
# falsche Symbol 'NS' fuehren, das nirgends mit dem gerenderten Token
# uebereinstimmt -- die Abwahl (#944) griffe dadurch weiterhin nicht.
# Issue #1824 (B): 'WD'/'PT' sind die einzigen zwei Kuerzel, deren Wert mit
# einem BUCHSTABEN beginnt ('WDNW', 'PTS') -- Kuerzel und Wert verschmelzen
# dort optisch zu einem Wort. Sie bekommen denselben Doppelpunkt, den 'TH:'
# bereits traegt; der Trenner gehoert ins SYMBOL, nicht in den Wert, damit
# Token.render() Leer- ('WD:-') und Lueckenform ('WD:?') ohne jede
# Sonderbehandlung mitzieht. Die Editor-Badge bleibt unveraendert 'WD'/'PT'
# (`.rstrip(":")` in _kurzform_kuerzel/_symbols_for).
SMS_SYMBOL_GRAMMAR: dict[str, str] = {
    "thunder": "TH:", "fresh_snow": "NS24+",
    "wind_direction": "WD:", "precip_type": "PT:",
}

_SMS_CODE_BY_ID: dict[str, str] = {m.id: m.sms_code for m in _METRICS}

SMS_SYMBOL_BY_METRIC: dict[str, str] = {
    metric_id: SMS_SYMBOL_GRAMMAR.get(metric_id) or _SMS_CODE_BY_ID[metric_id]
    for metric_id in _SMS_SYMBOL_METRIC_IDS
}

# Issue #1410: metric_id -> MEHRERE SMS-Kuerzel derselben Metrik. Eigene
# Zuordnung, weil eine Metrik hier mehrere Symbole traegt (Nacht/Tiefst/
# Hoechst) — SMS_SYMBOL_BY_METRIC bildet 1:1 ab und wird zusaetzlich fuer
# Schwellwerte gelesen (#624), wo diese Symbole nichts zu suchen haben.
# Fix #1450/Adversary-F001: 'WC' (Wintersport-Tageskennzahl, builder.py::
# _wintersport) ergaenzt -- ohne diesen Eintrag baut trip_report.py:283-287
# keinen disabled_specs-Eintrag fuer WC, und die Abwahl von "Gefuehlte
# Temperatur" im Trip-Editor wirkt sich nicht auf WC aus.
# Fix #1415 (PO-Entscheidung 2026-08-03): die GEMESSENE Temperatur folgt
# derselben Regel -- 'N'/'K'/'D' hingen an keinem Eintrag und erschienen
# deshalb auch bei abgewaehlter Metrik "Temperatur" (Beleg: Trip KHW 403,
# "K13 D16 FK13 FD16 ..." bei ausgeschalteter Temperatur). Register-Kuerzel
# taugen dafuer nicht: get_sms_code("temperature") == 'D' waere nur eines von
# dreien, get_sms_code("temperature_cold") == 'N' gehoert zur internen
# Alarm-Pseudogroesse (selectable=False), und ein Eintrag in
# SMS_SYMBOL_BY_METRIC wuerde zusaetzlich einen Schwellwert auf 'D' legen
# (#624), den es fuer Temperatur-Token gar nicht gibt. Daher hier, in der
# frueher 'FELT' benannten Mehrfach-Tabelle.
# Fix #1482: 'thunder' traegt ZWEI Kuerzel -- 'TH:' (berichtete Etappe) und
# 'TH+:' (Folge-Etappe). 'TH+:' hing an keinem Eintrag und blieb deshalb auch
# nach Abwahl der Metrik "Gewitter" in der Kurzform stehen. SMS_SYMBOL_BY_METRIC
# bildet 1:1 ab (nur 'TH:') und wird zusaetzlich fuer Schwellwerte gelesen
# (#624) -- ein zweiter Eintrag dort wuerde das Schwellwert-Dict verfaelschen.
# Fix #1484 (PO-Entscheidung 2026-08-03): 'N' wandert von "temperature" zur
# eigenen waehlbaren Groesse "temperature_night" -- Tages- und Nachttemperatur
# sind zwei unabhaengige Auswahl-Entscheidungen (Zelt vs. Huette).
# Fix #1660 Scheibe A: dieselbe Trennung jetzt auch auf der gefuehlten Seite --
# 'FN' wandert von "wind_chill" zur eigenen waehlbaren Groesse
# "wind_chill_night".
# Fix #1728 Scheibe 1 (PO-Entscheidung 2026-08-11): 'K'/'D' bzw. 'FK'/'FD'
# wandern von den Elterngroessen zu je eigenen waehlbaren Tagesrichtungen --
# Tages-Tief und Tages-Hoch sind zwei unabhaengige Auswahl-Entscheidungen.
# Fix #1887 E6 Scheibe A (PO-Entscheid, docs/specs/modules/
# fix_1887_e6a_sms_kuerzel_register.md): die Tabelle ist jetzt eine reine
# ABLEITUNG aus MetricDefinition.sms_multi_symbols (Muster SMS_SYMBOL_BY_METRIC
# seit E3b) statt einer eigenstaendig gepflegten Dict-Konstante -- kein
# hartkodiertes Kuerzel mehr fuer diese sechs Groessen. 'WC' (vormals
# Ein-Symbol-Eintrag bei "wind_chill", Wintersport-Tageskennzahl) entfaellt
# ERSATZLOS: verdoppelte nachweislich 'FK' (identisches Feld, Fenster,
# Aggregation) -- "wind_chill" traegt seitdem UEBERHAUPT keinen Eintrag mehr.
# 'thunder' bleibt bewusst AUSSERHALB der Feld-Ableitung: 'TH:' kommt
# weiterhin aus SMS_SYMBOL_GRAMMAR (zentrale Quelle seit E3b), 'TH+:' bleibt
# der seit #1482 dokumentierte literale Sonderfall (kein sms_code-Pendant).
SMS_MULTI_SYMBOLS_BY_METRIC: dict[str, tuple[str, ...]] = {
    m.id: m.sms_multi_symbols for m in _METRICS if m.sms_multi_symbols
} | {"thunder": (SMS_SYMBOL_GRAMMAR["thunder"], "TH+:")}

# #1719 S4: die einzigen Größen, deren Telegram-Kürzel vom Kurzform-Kürzel
# abweichen DARF. Wert = Begründung (Muster: SMS_SYMBOL_GRAMMAR oben,
# `gz-eigenstaendig` aus #1481 B). Ein Eintrag ohne Satz ist keine Ausnahme --
# der Wächter tests/unit/test_telegram_kuerzel_folgt_register.py besteht auf
# einer lesbaren Begründung.
COMPACT_LABEL_EXCEPTIONS: dict[str, str] = {
    "temperature": (
        "Die Telegram-Zelle zeigt einen STUNDENWERT. Das Register führt für "
        "diese Größe Tagesauswertungen ('K' Tagestiefst, 'D' Tageshöchst) — "
        "ein Spaltenkopf 'Tageshöchst' wäre über einem Stundenwert eine "
        "falsche Aussage."
    ),
    "wind_chill": (
        "Wie 'temperature': die Zelle zeigt einen Stundenwert, das Register "
        "führt Tagesauswertungen ('FK'/'FD' Tiefst/Höchst der gefühlten "
        "Temperatur). Fix #1887 E6 Scheibe A: das frühere Wintersport-"
        "Kürzel 'WC' entfällt ersatzlos (verdoppelte 'FK')."
    ),
}


def _kurzform_kuerzel(metric_id: str, sms_code: str) -> Optional[str]:
    """Das Kürzel, das die Kurzform (SMS/Premium-SMS) für diese Größe sendet.

    ``None``, wenn die Kurzform für diese Größe gar kein Kürzel führt — dann
    gibt es nichts zu vereinheitlichen und der gepflegte ``compact_label``
    bleibt stehen.

    Dieselbe Auflösung wie ``/api/sms-symbols::_symbols_for``: Mehrfach-Token
    haben Vorrang, davon benennt das ERSTE die Größe (die weiteren benennen
    Auswertungen); ``':'`` trennt nur eine Stufenangabe ab und gehört nicht
    zum Kürzel.
    """
    mehrfach = SMS_MULTI_SYMBOLS_BY_METRIC.get(metric_id)
    if mehrfach:
        return mehrfach[0].rstrip(":")
    if metric_id not in _SMS_SYMBOL_METRIC_IDS:
        return None
    return (SMS_SYMBOL_GRAMMAR.get(metric_id) or sms_code).rstrip(":")


# Die Ableitung selbst: ab hier trägt jede MetricDefinition das Kürzel, das
# der Nutzer in seiner Kurzform liest. Ein neuer Katalog-Eintrag kann damit
# nicht mehr unbemerkt ein zweites Kürzel einführen.
_METRICS = [
    m if m.id in COMPACT_LABEL_EXCEPTIONS
    else replace(
        m, compact_label=_kurzform_kuerzel(m.id, m.sms_code) or m.compact_label
    )
    for m in _METRICS
]

# Lookup by id
_METRICS_BY_ID: dict[str, MetricDefinition] = {m.id: m for m in _METRICS}

# Lookup by col_key (for formatter backward compat)
_METRICS_BY_COL_KEY: dict[str, MetricDefinition] = {m.col_key: m for m in _METRICS}


# Issue #1357: feste Reihenfolge der Tagesauswertungen und ihre deutschen
# Beschriftungen — EINE Quelle fuer Trip-Kachel (email/helpers.py) und
# Ortsvergleich (compare_metric_catalog.py / compare_outlook_metric_ids.py).
_AGGREGATION_ORDER: tuple[str, ...] = ("min", "max", "avg", "sum")
_AGGREGATION_LABELS_DE: dict[str, str] = {
    "min": "Minimum", "max": "Maximum", "avg": "Mittel", "sum": "Summe",
}


def summary_field_for(metric_id: object, aggregation: object) -> Optional[str]:
    """``SegmentWeatherSummary``-Feldname der Tagesauswertung (oder ``None``).

    ``selectable=False`` (``confidence``, ADR-0005/#710; ``temperature_cold``)
    ist bewusst nicht aufloesbar — nur waehlbare Groessen werden angezeigt.
    """
    definition = _METRICS_BY_ID.get(metric_id) if isinstance(metric_id, str) else None
    if definition is None or not definition.selectable:
        return None
    if not isinstance(aggregation, str):
        return None
    return definition.summary_fields.get(aggregation)


def alert_metric_for(metric_id: object, aggregation: object) -> Optional[str]:
    """Alarm-Identitaet eines Groesse-Auswertung-Paares (oder ``None``).

    #1435 E1a: absolute Alarme haengen an der Auswertung (``alert_metrics``);
    hat die gewaehlte Auswertung keinen absoluten Alarm, greift der
    Aenderungsraten-Alarm der Groesse (``change_alert_metric``). Genau dieser
    Rueckfall entkreuzt Wind/Boeen: ``("wind","max")`` loest auf
    ``"wind_change"`` auf, ``"wind_gust"`` bleibt ``("gust","max")`` vorbehalten.

    Adversary-Fund F001 (#1435 E1a-1): der Rueckfall darf NICHT blind fuer
    jede uebergebene Auswertung greifen. Wahrheitsquelle fuer "gueltig" ist
    ``summary_fields`` (dieselbe Quelle wie ``available_aggregations()`` --
    was tatsaechlich berechnet wird). Deklariert eine Groesse ausserdem
    EIGENE, auswertungsspezifische Identitaeten (``alert_metrics`` nicht
    leer, z. B. Temperatur min/max), gilt der pauschale Change-Rueckfall nur
    fuer die Groesse als Ganzes, solange KEINE solcher Deklarationen
    existieren (z. B. Wind) -- sonst wuerde eine nicht abgedeckte, aber
    valide Auswertung (Temperatur/avg) stillschweigend die
    Aenderungsraten-Identitaet einer ANDEREN Auswertung erben.
    """
    if not isinstance(metric_id, str) or not isinstance(aggregation, str):
        return None
    definition = _METRICS_BY_ID.get(metric_id)
    if definition is None or aggregation not in definition.summary_fields:
        return None
    direct = definition.alert_metrics.get(aggregation)
    if direct or definition.alert_metrics:
        return direct
    return definition.change_alert_metric


def available_aggregations(metric_id: object) -> list[str]:
    """Tatsaechlich anzeigbare Auswertungen einer Groesse, in fester Reihenfolge.

    Quelle ist ``summary_fields`` (was berechnet wird), NICHT
    ``default_aggregations`` (verspricht bei ``snowfall_limit``/
    ``freezing_level`` mehr, als berechenbar ist).
    """
    definition = _METRICS_BY_ID.get(metric_id) if isinstance(metric_id, str) else None
    if definition is None or not definition.selectable:
        return []
    return [a for a in _AGGREGATION_ORDER if a in definition.summary_fields]


def normalize_outlook_metric_ids(stored: object) -> Optional[list[str]]:
    """Gespeicherte Ausblick-Auswahl -> reine Kennungen (Issue #1848 A2).

    Versteht BEIDE Speicherformen und zwar dauerhaft, nicht als
    Uebergangskruecke: reine Kennungen (``"temperature"``, das Format seit A2)
    und die Paar-Altform (``{"metric_id": ..., "aggregation": ...}``, ADR-0037).
    Zwei Paare derselben Groesse (Tief UND Hoch) werden zu EINER Kennung --
    die Auswertungen leitet der Katalog ab, sie sind kein Speicherinhalt mehr.

    Reine Elementform-Normalisierung OHNE Katalogpruefung: sie gehoert hierher
    (Vokabular), die Existenzpruefung dagegen in den Aufloeser des
    Renderpfades. Reihenfolge des ersten Auftretens bleibt erhalten (kein
    ``set``), ``None`` heisst "kein Array" und traegt die Drei-Werte-Semantik
    unveraendert weiter.
    """
    if not isinstance(stored, list):
        return None
    kennungen: list[str] = []
    for eintrag in stored:
        if isinstance(eintrag, str):
            metric_id: object = eintrag
        elif isinstance(eintrag, dict):
            metric_id = eintrag.get("metric_id")
        else:
            metric_id = None
        if isinstance(metric_id, str) and metric_id not in kennungen:
            kennungen.append(metric_id)
    return kennungen


def aggregation_label_de(aggregation: object) -> str:
    """Deutsche Beschriftung einer Auswertung (``""`` wenn unbekannt)."""
    return _AGGREGATION_LABELS_DE.get(aggregation, "") if isinstance(aggregation, str) else ""


def get_metric(metric_id: str) -> MetricDefinition:
    """Get metric definition by ID. Raises KeyError if not found."""
    return _METRICS_BY_ID[metric_id]


def get_metric_by_col_key(col_key: str) -> MetricDefinition:
    """Get metric definition by column key. Raises KeyError if not found."""
    return _METRICS_BY_COL_KEY[col_key]


def get_all_metrics() -> list[MetricDefinition]:
    """Get user-selectable metric definitions in display order.

    Excludes metrics with selectable=False (e.g. confidence) which are
    kept in _METRICS for internal computation but must not appear in the
    user-visible catalog (/api/metrics) or any selection UI.
    Use _METRICS directly when internal iteration over all metrics is needed.
    """
    return [m for m in _METRICS if m.selectable]


def get_metrics_by_category(category: str) -> list[MetricDefinition]:
    """Get metrics filtered by category."""
    return [m for m in _METRICS if m.category == category]


def get_default_enabled_metrics() -> list[str]:
    """Get IDs of metrics enabled by default."""
    return [m.id for m in _METRICS if m.default_enabled]


def build_default_display_config(trip_id: str = "") -> "UnifiedWeatherDisplayConfig":
    """
    Build default UnifiedWeatherDisplayConfig matching current EmailReportDisplayConfig defaults.

    This ensures backward compatibility: reports without explicit config
    produce identical output to the current hardcoded defaults.
    """
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    # Issue #89: Alerts are explicit opt-ins per sms_format.md v2.0.
    # default_change_threshold from MetricDefinition serves as the Δ-default
    # WHEN the user activates the alert — not as an activation trigger.
    metrics = []
    for m in _METRICS:
        metrics.append(MetricConfig(
            metric_id=m.id,
            enabled=m.default_enabled,
            alert_enabled=False,
        ))

    return UnifiedWeatherDisplayConfig(
        trip_id=trip_id,
        metrics=metrics,
        show_night_block=True,
        night_interval_hours=2,
        thunder_forecast_days=2,
        updated_at=datetime.now(timezone.utc),
    )


WEATHER_TEMPLATES: dict[str, dict] = {
    "alpen-trekking": {
        "label": "Alpen-Trekking",
        "metrics": [
            "temperature", "temperature_night", "wind_chill", "wind", "gust", "precipitation",
            "thunder", "rain_probability", "snowfall_limit",
            "freezing_level", "cloud_total", "cloud_low", "visibility", "uv_index",
        ],
    },
    "wandern": {
        "label": "Wandern",
        "metrics": [
            "temperature", "temperature_night", "humidity", "wind", "gust", "precipitation",
            "rain_probability", "cloud_total", "sunshine", "uv_index",
        ],
    },
    "skitouren": {
        "label": "Skitouren",
        "metrics": [
            "temperature", "temperature_night", "wind_chill", "wind", "gust", "precipitation",
            "fresh_snow", "snow_depth", "snowfall_limit", "freezing_level",
            "cloud_total", "cloud_low", "visibility",
        ],
    },
    "wintersport": {
        "label": "Wintersport",
        "metrics": [
            "temperature", "temperature_night", "wind_chill", "wind", "gust", "precipitation",
            "fresh_snow", "snow_depth", "cloud_total", "sunshine", "visibility",
        ],
    },
    "radtour": {
        "label": "Radtour",
        "metrics": [
            "temperature", "temperature_night", "wind", "wind_direction", "gust", "precipitation",
            "rain_probability", "thunder", "cloud_total", "sunshine", "uv_index",
        ],
    },
    "wassersport": {
        "label": "Wassersport",
        "metrics": [
            "temperature", "temperature_night", "wind", "gust", "wind_direction", "precipitation",
            "rain_probability", "thunder", "cloud_total", "visibility",
        ],
    },
    "allgemein": {
        "label": "Allgemein",
        "metrics": [
            "temperature", "temperature_night", "wind", "gust", "precipitation",
            "rain_probability", "cloud_total", "sunshine",
        ],
    },
}


def get_all_templates() -> list[dict]:
    """Return all weather templates as a list of structured dicts.

    Returns:
        List of {"id": str, "label": str, "metrics": list[str]}
        in insertion order (alpen-trekking first, allgemein last).

    Issue #1585: nicht waehlbare Groessen (``selectable=False``) fallen aus den
    Profil-Listen heraus. ``WEATHER_TEMPLATES`` nennt ``cape`` zwar bereits
    nicht mehr -- der Filter bleibt als strukturelle Sicherung, damit die
    naechste ``selectable=False``-Groesse hier nicht erneut vergessen wird.
    """
    selectable_ids = {m.id for m in get_all_metrics()}
    return [
        {
            "id": tid,
            "label": tdata["label"],
            "metrics": [m for m in tdata["metrics"] if m in selectable_ids],
        }
        for tid, tdata in WEATHER_TEMPLATES.items()
    ]


def build_default_display_config_for_profile(
    location_id: str,
    profile: "ActivityProfile",
) -> "UnifiedWeatherDisplayConfig":
    """Build a UnifiedWeatherDisplayConfig with metrics enabled for the given profile."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig

    template = WEATHER_TEMPLATES.get(profile.value, WEATHER_TEMPLATES["allgemein"])
    enabled_ids = set(template["metrics"])
    metrics = []
    for metric_def in get_all_metrics():
        metrics.append(MetricConfig(
            metric_id=metric_def.id,
            enabled=metric_def.id in enabled_ids,
        ))
    return UnifiedWeatherDisplayConfig(
        trip_id=location_id,
        metrics=metrics,
        updated_at=datetime.now(timezone.utc),
    )


def get_change_detection_map() -> dict[str, float]:
    """
    Build {summary_field: threshold} from MetricCatalog.

    Iterates all metrics, expands summary_fields, pairs each field
    with default_change_threshold. Skips metrics with threshold=None.

    Returns:
        Dict mapping SegmentWeatherSummary field names to thresholds.
        Example: {"temp_min_c": 5.0, "temp_max_c": 5.0, "wind_max_kmh": 20.0, ...}
    """
    result: dict[str, float] = {}
    for m in _METRICS:
        if m.default_change_threshold is None:
            continue
        # Issue #889 / #914: Vorboten-Metriken (is_precursor=True) tragen
        # default_change_threshold für Katalog-Vollständigkeit (sms_code),
        # sind aber NICHT Teil der Change-Detection-Map.
        if m.is_precursor:
            continue
        # Issue #1585: eine zentral nicht wählbare Größe (cape) darf keinen
        # Änderungs-Alarm mehr auslösen — sonst bliebe cape_max_jkg als
        # Schwelle stehen, obwohl die Größe nirgends mehr wählbar ist.
        if not m.selectable:
            continue
        for aggregation, summary_field in m.summary_fields.items():
            # Issue #1468: Beginn-Felder tragen einen ZEITPUNKT, keinen
            # Messwert -- `abs(delta) > threshold` waere dort ein Vergleich
            # von timedelta mit float (TypeError). Der Beginn-Alarm laeuft
            # ueber seine eigene Weiche in `detect_changes()`.
            if aggregation == ONSET_AGGREGATION:
                continue
            result[summary_field] = m.default_change_threshold
    return result


def get_compact_label_for_field(summary_field: str) -> tuple[str, str] | None:
    """
    Reverse-lookup: summary_field -> (compact_label, unit_short).

    Finds the MetricDefinition that maps to this summary field
    and returns compact label + short unit for SMS formatting.

    Args:
        summary_field: SegmentWeatherSummary field name (e.g. "temp_max_c")

    Returns:
        (compact_label, unit_short) or None if not found.
        Example: ("T", "C") for "temp_max_c"
    """
    for m in _METRICS:
        if summary_field in m.summary_fields.values():
            # Derive short unit from full unit (remove special chars)
            unit_short = m.unit.replace("°", "").replace("/", "").replace(" ", "")
            return (m.compact_label, unit_short)
    return None


def get_label_for_field(summary_field: str) -> tuple[str, str, str] | None:
    """
    Reverse-lookup: summary_field -> (label_de, aggregation, unit).

    For human-readable display in alert emails.
    Example: "temp_max_c" -> ("Temperatur", "max", "°C")
    """
    for m in _METRICS:
        for agg, field in m.summary_fields.items():
            if field == summary_field:
                return (m.label_de, agg, m.unit)
    return None


def metric_and_aggregation_for_field(
    summary_field: str, *, _registry: Optional[list] = None,
) -> Optional[tuple[str, str]]:
    """Reverse-lookup: summary_field -> (metric_id, aggregation).

    Issue #1459 (O1): liefert die Register-Kennung selbst -- das, was
    get_label_for_field()/get_compact_label_for_field() nicht tun.

    Anders als die beiden Vorbilder NICHT "erstes Treffer-Item gewinnt": bei
    mehreren Treffern entscheidet inhaltlich, welcher `selectable=True` ist
    (die nutzersichtbare Groesse; interne Pseudo-Groessen wie
    "temperature_cold" verlieren). Bleiben danach 0 oder >=2 Kandidaten, ist
    das Feld echt mehrdeutig -- das wird geloggt, NICHT stillschweigend ueber
    die Listenposition entschieden (Praezedenzfaelle #1257, #1444 S2a).

    Fail-soft per `None` statt Exception: die Funktion laeuft innerhalb eines
    Alarm-Laufs; eine Katalog-Inkonsistenz darf keine Gewitter- oder
    Amtswarnung scheitern lassen.

    `_registry` ist ein Test-Seam fuer den Reihenfolge-Unabhaengigkeits-
    Nachweis (Issue #1459 AC-5) -- Default ist die echte `_METRICS`.
    """
    registry = _registry if _registry is not None else _METRICS
    matches = [
        (m, agg)
        for m in registry
        for agg, field in m.summary_fields.items()
        if field == summary_field
    ]
    if len(matches) == 1:
        return (matches[0][0].id, matches[0][1])
    if not matches:
        return None
    selectable_matches = [(m, agg) for m, agg in matches if m.selectable]
    if len(selectable_matches) == 1:
        return (selectable_matches[0][0].id, selectable_matches[0][1])
    logger.warning(
        "metric_and_aggregation_for_field: mehrdeutiges Summary-Feld %r "
        "(%d Treffer, %d davon selectable) -- Register-Paar im Alarm-Protokoll "
        "ausgelassen",
        summary_field, len(matches), len(selectable_matches),
    )
    return None


# Issue #914 Slice 1: Helper lookups for alert render stammdaten.

def get_sms_code(metric_id: str) -> str:
    """Get the SMS token for a metric.

    Returns empty string if metric not found or has no sms_code.
    """
    m = _METRICS_BY_ID.get(metric_id)
    return m.sms_code if m is not None else ""


def get_decimals(metric_id: str) -> int:
    """Get the display decimal places for a metric.

    Returns 0 if metric not found or decimals is None.
    """
    m = _METRICS_BY_ID.get(metric_id)
    if m is None or m.decimals is None:
        return 0
    return m.decimals


def get_cmp(metric_id: str) -> str:
    """Get the comparison direction ('über' or 'unter') for a metric.

    Returns empty string if metric not found or has no cmp set.
    """
    m = _METRICS_BY_ID.get(metric_id)
    return m.cmp if m is not None else ""


def get_alert_label(metric_id: str) -> str:
    """Get the German alert label for a metric (short form for alert renderers).

    Falls back to label_de if alert_label is empty or metric not found.
    """
    m = _METRICS_BY_ID.get(metric_id)
    if m is None:
        return metric_id
    return m.alert_label or m.label_de


def _format_de_thousand(value: float) -> str:
    """12240 → '12.240', 12240.7 → '12.241' (gerundet, integer-Display)."""
    return f"{int(round(value)):,}".replace(",", ".")


def format_metric_value(unit: str, value: float, *, signed: bool = False) -> str:
    """
    Einheits-spezifische DE-Formatierung mit Tausender-Trenner.

    - m, km, hPa            → integer, Tausender-Trenner DE (Punkt)
    - %                     → integer (kaufmännische Rundung)
    - km/h                  → integer
    - °C, mm                → 1 NK, Dezimaltrenner Komma
    - sonst                 → str(value)

    signed=True präfixt '+' bei positiven Werten (Delta-Darstellung),
    Unicode-Minus '−' (U+2212) bei negativen Werten.
    signed=False: negative Werte bei m/km/hPa/%/km/h ebenfalls Unicode-Minus.
    """
    abs_v = abs(value)
    if unit in ("m", "km", "hPa"):
        formatted = _format_de_thousand(abs_v)
    elif unit in ("%", "km/h"):
        formatted = f"{int(round(abs_v))}"
    elif unit in ("°C", "mm"):
        formatted = f"{abs_v:.1f}".replace(".", ",")
    else:
        return str(value)

    sign = ""
    if signed:
        if value > 0:
            sign = "+"
        elif value < 0:
            sign = "−"  # U+2212
    elif value < 0 and unit in ("m", "km", "hPa", "%", "km/h", "°C", "mm"):
        sign = "−"

    return f"{sign}{formatted} {unit}".strip()


def get_col_defs() -> list[tuple[str, str, str]]:
    """
    Get column definitions for formatter, ordered by catalog order.

    Returns list of (col_key, col_label, col_key) tuples matching
    the old _COL_DEFS format.
    """
    return [(m.col_key, m.col_label, m.col_key) for m in _METRICS]
