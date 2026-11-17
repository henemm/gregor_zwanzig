"""
Comparison Renderers — extracted from the former NiceGUI compare page (Epic #129 Phase A.1; the source module was removed in Phase A.3).

Pure-function renderers that turn ComparisonResult into HTML / Plain-Text for
email delivery. No NiceGUI dependency.

``render_comparison_html()`` war seit Issue #253 ein bestaetigter toter
Alt-Renderer (Score/Winner-Vertrag, nie vom echten Versandpfad aufgerufen --
``render_compare_email()`` nutzt ausschliesslich ``output.renderers.email.
compare_html.render_compare_html()``) und wurde mit Issue #1110 ENTFERNT
(koordiniert mit #1108). ``render_comparison_text()`` wurde im selben Zug auf
den v2-Vertrag umgestellt: kein Score/🏆 mehr, stattdessen Uebersicht +
amtliche Warnungen je Ort, Stundentabellen fuer alle Orte.

SPEC: docs/specs/epic_129a_1_compare_helpers.md
SPEC (v2): docs/specs/modules/issue_1110_compare_mail_v2.md
"""
from __future__ import annotations

import html as _html
import re as _re
from typing import Optional

from app.ampel import ampel_seite, resolve_ampel
from app.metric_catalog import get_metric, kurzform_kuerzel
from app.models import Corridor, MetricConfig, UnifiedWeatherDisplayConfig
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from i18n import Lang, t
from i18n.format import fmt_date_numeric, fmt_weekday
from output.renderers.channel_layout import (
    CHANNEL_LIMITS, render_for_channel, selection_gap_notice,
)
from output.renderers.fallback_notice import build_compare_fallback_lines
from output.renderers.compare_metric_catalog import (
    COMPARE_METRIC_CATALOG, kuerzel_metric_id_for,
)
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import (
    CV2_ZEILEN, _build_location_outlook_rows, _daily_summary, _hour_einfach_text, _hour_zeilen,
    _column_legend_text, _fmt_precip_type, _fmt_thunder,
    _fmt_visibility_overview, _metric_value, _should_merge_wind_dir,
    _units_legend_text, _visible_hour_metrics, derive_row_labels, fmt_word_cell,
    loc_hail_flag, loc_thunder_signals, location_render_order, rowless_count,
)
from output.renderers.email.outlook_state_hint import (
    OutlookState, render_outlook_state_plain,
)
from output.renderers.email.unavailable_hint import (
    any_official_alerts_unavailable, render_official_alerts_unavailable_plain,
)
from output.renderers.email.undelivered_hint import (
    has_undelivered, render_undelivered_plain,
)
from utils.geo import degrees_to_compass
from utils.timezone import (
    local_dt, local_fmt, local_stamp, location_tz, resolve_location_tz, tz_abbrev,
)
from output.renderers.email.outlook import render_outlook_plain
from output.metric_format import format_value
# Nicht-abrufbar-Marker der SMS (sms_format.md §3.4d, Issue #3047 B-L2).
from output.tokens.builder import UNAVAILABLE_SYMBOL as _UNAVAILABLE_SYMBOL
from output.renderers.alert.official_alerts import (
    _word_boundary_truncate,
    build_official_alert_notices,
    official_alert_source_label,
    official_alerts_to_sms_entries,
    render_official_alert_telegram,
    render_official_alerts_plain,
)
import services.alert_urgency as alert_urgency

#: Formatierungs-Tags der Telegram-HTML-Vorlagen (Issue #3047 p2b).
_HTML_TAG_RE = _re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*[^<>]*>")

# Issue #1285: die fuenf bisher stillschweigend verworfenen Uebersichts-Zeilen
# (Renderer-Metrik-ID, Label, Formatierung). Wert-Quelle und Formatierung sind
# BEWUSST die des HTML-Pfads (`compare_html._metric_value` / `_fmt_*`) statt
# einer Klartext-Kopie -- sonst beschreibt dieselbe Wetterlage in HTML und
# Klartext derselben Mail verschiedene Zahlen.
# Issue #1401 Scheibe A2b: das zweite Tupel-Element ist NICHT mehr die
# Mail-Beschriftung -- die leitet der Mail-Klartext jetzt aus dem zentralen
# Register ab (`compare_html.derive_row_labels`, dieselbe Quelle wie der
# HTML-Teil). Es bleibt ausschliesslich das Kanal-Label des Telegram-Pfads
# (`_plain_metric_cell`); seit Issue #2666 als Katalog-Schluessel
# ``vergleich.zeile.<Zeilenschluessel>`` (de-Text = bisheriges Label).
_DAILY_PLAIN_ROWS: tuple[tuple[str, str, object], ...] = (
    ("precip_sum", "vergleich.zeile.precip_sum", lambda v: f"{v:.1f} mm"),
    ("pop_max", "vergleich.zeile.pop_max", lambda v: f"{v:.0f}%"),
    ("thunder_max", "vergleich.zeile.thunder_max", _fmt_thunder),
    ("uv_max", "vergleich.zeile.uv_max", lambda v: f"{v:.0f}"),
    ("visibility_min", "vergleich.zeile.visibility_min", _fmt_visibility_overview),
    # Issue #1296, Klasse B (kein LocationResult-Feld, Live-Ableitung ueber
    # _metric_value -> _daily_summary, analog den fuenf #1285-Zeilen).
    # Issue #1585: die cape_max-Zeile ist hier ersatzlos entfallen -- sie muss
    # mit CV2_METRICS (compare_html.py) synchron bleiben, `derive_row_labels`
    # schlaegt sie ueber `_CV2_BY_KEY` nach und wirft sonst KeyError.
    ("freezing_level", "vergleich.zeile.freezing_level", lambda v: f"{v:.0f} m"),
    # Issue #1324, Klasse B (kein LocationResult-Feld, Live-Ableitung ueber
    # _metric_value -> _daily_summary). HTML-Parität: dieselben Werte.
    ("humidity_avg", "vergleich.zeile.humidity_avg", lambda v: f"{v:.0f}%"),
    ("dewpoint_avg", "vergleich.zeile.dewpoint_avg", lambda v: format_value("temperature", v, style="plain")),
    ("pressure_avg", "vergleich.zeile.pressure_avg", lambda v: f"{v:.0f} hPa"),
    ("precip_type", "vergleich.zeile.precip_type", _fmt_precip_type),
    ("snowfall_limit", "vergleich.zeile.snowfall_limit", lambda v: f"{v:.0f} m"),
)

# Issue #1359 Scheibe 1: ALLE Uebersichts-Zeilen des Klartext-Teils als EINE
# geordnete Tabelle (Renderer-Metrik-ID, Label, Formatierung). Vorher standen
# sie als feste Folge einzelner `if _metric_visible(...)`-Bloecke im Quelltext
# -- die im Editor eingestellte Metrik-Reihenfolge konnte deshalb gar nicht
# ankommen (der Test prueft nur Mitgliedschaft, nicht Position).
# Issue #1356: die Quellcode-Reihenfolge dieser Tabelle ist NICHT mehr die
# Standard-Reihenfolge. Einzige Quelle der Standard-Reihenfolge (Altbestaende
# ohne gespeicherte Auswahl) ist `CV2_METRICS` (compare_html.py); die Tabelle
# wird beim Import per `_sort_by_cv2_order` in diese Folge gebracht (Spec
# docs/specs/modules/compare_metric_default_order_ssot.md).
# Werte kommen einheitlich ueber `_metric_value` (HTML-Paritaet, keine zweite
# Wert-Quelle): fuer IDs ohne `_DAILY_AGGREGATE_FIELD`-Eintrag ist das exakt
# das bisherige `getattr(loc_result, metric_id)`.
_PLAIN_ROWS_UNSORTED: tuple[tuple[str, str, object], ...] = (
    ("temp_max", "vergleich.zeile.temp_max", lambda v: format_value("temperature", v, style="plain")),
    ("wind_max", "vergleich.zeile.wind_max", lambda v: format_value("wind", v, style="plain")),
    ("temp_min", "vergleich.zeile.temp_min", lambda v: format_value("temperature", v, style="plain")),
    ("gust_max", "vergleich.zeile.gust_max", lambda v: format_value("wind", v, style="plain")),
    ("wind_direction_avg", "vergleich.zeile.wind_direction_avg", lambda v: f"{v}°"),
    ("wind_chill_min", "vergleich.zeile.wind_chill_min",
     lambda v: format_value("temperature", v, style="plain")),
    ("wind_chill_max", "vergleich.zeile.wind_chill_max",
     lambda v: format_value("temperature", v, style="plain")),
    ("cloud_low_avg", "vergleich.zeile.cloud_low_avg", lambda v: f"{v}%"),
    ("cloud_mid_avg", "vergleich.zeile.cloud_mid_avg", lambda v: f"{v}%"),
    ("cloud_high_avg", "vergleich.zeile.cloud_high_avg", lambda v: f"{v}%"),
    *_DAILY_PLAIN_ROWS,
    ("sunny_hours", "vergleich.zeile.sunny_hours", lambda v: f"{format_value('sunshine', v, style='bare')}h"),
    ("cloud_avg", "vergleich.zeile.cloud_avg", lambda v: format_value("cloud_total", v, style="plain")),
    ("snow_depth_cm", "vergleich.zeile.snow_depth_cm", lambda v: format_value("snow_depth", v, style="plain")),
    ("snow_new_cm", "vergleich.zeile.snow_new_cm", lambda v: f"{v:.0f} cm"),
)


def _sort_by_cv2_order(rows) -> tuple:
    """Klartext-Zeilen in die Reihenfolge von ``CV2_METRICS`` bringen (#1356).

    ``CV2_METRICS`` ist die einzige Quelle der Standard-Reihenfolge; ``warn``
    ist eine reine HTML-Zeile und wird uebersprungen. Fail-fast: steht ein
    Schluessel nur in einer der beiden Listen, bricht der Aufruf (und damit der
    Modulimport) mit ``ValueError`` ab, der den Schluessel nennt -- keine Zeile
    wird still ans Ende gehaengt.
    """
    cv2_keys = [m["key"] for m in CV2_ZEILEN if m["key"] != "warn"]
    by_id = {row[0]: row for row in rows}
    nur_plain = [k for k in by_id if k not in cv2_keys]
    nur_cv2 = [k for k in cv2_keys if k not in by_id]
    if nur_plain or nur_cv2:
        raise ValueError(
            "plain rows and CV2_METRICS diverge: "
            f"only in plain rows: {nur_plain}; only in CV2_METRICS: {nur_cv2}"
        )
    return tuple(by_id[k] for k in cv2_keys)


_PLAIN_ROWS: tuple[tuple[str, str, object], ...] = _sort_by_cv2_order(
    _PLAIN_ROWS_UNSORTED
)

# Beschriftungs-Quelle des Klartext-Zwillings: dieselben Register-Verknuepfungen
# wie im HTML-Pfad, nach Zeilen-Key ansprechbar (Issue #1401 A2b).
_CV2_BY_KEY: dict[str, dict] = {m["key"]: m for m in CV2_ZEILEN}


def _ordered_rows(rows, enabled_metrics: list[str] | None) -> list | tuple:
    """Zeilen-/Zell-Definitionen in der vom Nutzer eingestellten Reihenfolge.

    Issue #1359: ``enabled_metrics`` ist eine GEORDNETE Liste (Listenposition
    = Reihenfolge, kein eigenes ``order``-Feld). ``None`` = Altbestand ohne
    gespeicherte Auswahl und folgt der Standard-Reihenfolge von ``rows``
    (fuer ``_PLAIN_ROWS`` die von ``CV2_METRICS``, Issue #1356). Eine leere Liste bleibt leer (AC-8) -- sie darf nicht in "alle
    Metriken" umgedeutet werden. Semantik identisch zu ``_visible_metrics()``
    im HTML-Pfad (``output.renderers.email.compare_html``).
    """
    if enabled_metrics is None:
        return rows
    by_id = {row[0]: row for row in rows}
    return [by_id[m] for m in dict.fromkeys(enabled_metrics) if m in by_id]


def render_comparison_text(
    result: ComparisonResult,
    profile: Optional[ActivityProfile] = None,
    enabled_metrics: list[str] | None = None,
    *,
    outlook_enabled: bool = False,
    outlook_metrics: list[dict] | None = None,
    outlook_metric_formats: dict[str, bool] | None = None,
    hourly_metrics: list[str] | None = None,
    hourly_enabled: bool = True,
    undelivered: list | None = None,
    unresolved_count: int = 0,
    lang: Lang = "de",
    show_fallback_notice: bool = False,
    preset: dict,
    metric_formats: dict[str, bool] | None = None,
    hourly_metric_formats: dict[str, bool] | None = None,
) -> str:
    """
    Render ComparisonResult als Klartext (v2, Issue #1110). ``lang``: #2666.
    ``metric_formats`` (Issue #3039): Roh/Einfach je Uebersichtszeile aus
    ``channel_layouts["email"]``; ``None`` = heutiger Festzustand.
    ``hourly_metric_formats`` (Issue #3097): Roh/Einfach je Stundenverlauf-
    Spalte, derselbe Einfach-Zweig wie im HTML; ``None`` = Roh.
    ``preset`` (Issue #2792 S1c-4a/4b): rohes Vergleichs-Preset, Pflicht ohne
    Default; seine Ampel bewertet die Ausblick-Zeilen.
    ``show_fallback_notice`` (Issue #1563): Vertretungshinweis je Ort unter
    der Uebersicht, nur Briefing; Default ``False``.

    Kein Score/🏆 mehr. Je Ort: amtliche Warnungen zuerst (#3047 WV6), dann
    Uebersichtswerte (Warnungen via
    ``render_official_alerts_plain()``, kein Copy-Paste, ADR-0011). Danach
    kompakte Stundentabellen fuer ALLE Orte (kein Rang-Praefix, keine
    Top-N-Beschraenkung mehr).

    Args:
        result: ComparisonResult aus ComparisonEngine.
        profile: Optional ActivityProfile (aktuell ohne Einfluss auf den
            Klartext-Inhalt, akzeptiert fuer API-Konsistenz mit
            ``render_compare_html``).
        enabled_metrics: Issue #1125. Filtert die Uebersichts-Zeilen je Ort
            auf die enthaltenen Renderer-Metrik-IDs (z.B. "temp_max",
            "wind_max") und bestimmt seit Issue #1359 auch deren
            REIHENFOLGE (Listenposition = Reihenfolge). ``None`` = kein
            Filter (alle Zeilen in Standard-Reihenfolge,
            Rueckwaertskompatibilitaet). Spiegelt exakt die Semantik von
            ``_visible_metrics()`` im HTML-Pfad
            (``output.renderers.email.compare_html``). Amtliche Warnungen
            bleiben davon unabhaengig immer sichtbar.
        hourly_metrics: Issue #1366 F003 (Staging-Fund, AC-4): Spalten-Filter
            fuer die Stundenzeile je Ort, exakt dieselbe Semantik wie im
            HTML-Pfad (``_visible_hour_metrics``) -- nur die gewaehlten, in der
            gewaehlten Reihenfolge. Ohne Angabe (``None``, nur direkte Aufrufe)
            gilt wie im HTML-Pfad die Vorgabe aus ``resolve_hourly_metrics(None)``
            (einzige Quelle ``compare_hourly_metric_ids``, #3096).
        hourly_enabled: Issue #1366 F003: ``False`` laesst den gesamten
            Stundenverlauf-Abschnitt (Ueberschrift + Tabellenzeilen) je Ort
            entfallen -- der 3-Tage-Ausblick haengt NICHT an dieser
            Bedingung und bleibt unveraendert sichtbar (Issue #1323).
        undelivered: Issue #1461 S3b-1 (AC-17): Vorfaelle, die seit dem
            letzten Briefing einen Kanal nicht erreicht haben. GLEICHER
            geteilter Baustein wie HTML-Pfad und Trip-Briefing. Der
            Klartext-Teil wird mitgesendet (`send_compare_report(...,
            plain_text_body=text_body)`) und ist kein toter Pfad -- ein hier
            fehlender Baustein wird von KEINEM Pflicht-Validator gefunden
            (`email_spec_validator` liest nur den HTML-Body; genau so blieb
            in #1366 `hourly_enabled` im Klartext monatelang wirkungslos).
            ``None``/leer = kein Abschnitt, keine Ueberschrift.
        unresolved_count: Issue #1405 S3 -- wie im HTML-Pfad: gewaehlte
            Eintraege ohne Renderer-Zuordnung; zusammen mit den Groessen ohne
            Zeile EINE Hinweiszeile unter der Uebersicht (Baustein
            ``selection_gap_notice``), bei 0 keine.

    Returns:
        Klartext-String fuer die E-Mail.
    """
    _ = profile  # akzeptiert fuer API-Konsistenz, aktuell ohne Wirkung
    if hourly_metrics is None:
        from output.renderers.compare_hourly_metric_ids import resolve_hourly_metrics

        hourly_metrics = resolve_hourly_metrics(None)
    # Issue #2792 S1c-4b: Einstieg loest die Ampel des Presets auf (fuer die
    # Ausblick-Zeilen).
    ampel = resolve_ampel(preset)

    target_date = result.target_date
    created_at = result.created_at
    # Zentraler Orts-Reihenfolge-Helfer (#1359, loest die alphabetische
    # Sortierung vom 2026-07-08 ab): die vom Nutzer eingestellte Ortsfolge
    # (`location_ids`) bleibt, identisch zu render_compare_html() -- keine
    # Doppel-Logik.
    locations = location_render_order(result.locations)
    if not locations:
        return t("vergleich.allgemein.keine_daten", lang)

    lines: list[str] = []
    lines.append(t("vergleich.kopf.titel", lang))
    lines.append("=" * 24)
    # #2210 C2-52: beide Sprachen ueber die sprachfesten i18n-Helfer (locale-unabhaengig).
    datum = f"{fmt_weekday(target_date, lang, kurz=False)}, {fmt_date_numeric(target_date, lang)}"
    lines.append(t("vergleich.kopf.datum", lang, datum=datum))
    # Issue #1268: Zeitfenster-Zeile ersatzlos entfernt (Bewertung = ganzer Tag).
    # Issue #1378 (AC-4/AC-8): Ortszeit des ERSTGENANNTEN Ortes plus
    # erkennbares Zeitzonen-Kuerzel -- identische Zeitbasis und identischer
    # Wert wie die HTML-Kopfzeile derselben Mail.
    kopf_tz = location_tz(locations[0].location)
    erstellt = (
        f"{fmt_date_numeric(local_dt(created_at, kopf_tz), 'en')} {local_stamp(created_at, kopf_tz)}"
        if lang == "en" else local_stamp(created_at, kopf_tz, '%d.%m.%Y %H:%M')
    )
    lines.append(t("vergleich.kopf.erstellt_zeile", lang, zeit=erstellt))
    lines.append("")
    # Issue #3047 B-OM-1 (AC-28): derselbe Hinweis "nicht abrufbar" wie im
    # HTML-Teil derselben Mail (geteilter Baustein wie Trip-Klartext, #1348).
    if any_official_alerts_unavailable(locations):
        lines.append(render_official_alerts_unavailable_plain(lang=lang))
        lines.append("")
    lines.append("-" * 50)

    for loc_result in locations:
        loc = loc_result.location
        lines.append(loc.name)
        if loc_result.error is not None:
            lines.append("   " + t("vergleich.ort.fehler", lang, fehler=loc_result.error))
            lines.append("")
            continue

        # Amtliche Warnungen, eine Zeile pro Warnung (Epic #1073 Punkt 6,
        # gemeinsamer Renderer statt Copy-Paste). Issue #3047 (Konzept WV6):
        # wie im HTML-Teil ZUERST, vor den Metrik-Zeilen in Nutzerfolge.
        for line in render_official_alerts_plain([(loc.name, loc_result.official_alerts)], lang=lang):
            lines.append(f"   ⚠️ {line}")

        # Issue #1359: EINE geordnete Schleife statt fester if-Kette. Die
        # Werte kommen weiterhin aus DERSELBEN Quelle wie die HTML-Matrix
        # (`_metric_value` -> Engine-Feld bzw. live aus hourly_data), damit
        # HTML und Klartext derselben Mail nie auseinanderlaufen.
        # Issue #1401 A2b: die Beschriftung kommt aus derselben Ableitung wie
        # der HTML-Tabellenkopf -- der Kollisions-Zusatz ("Temp max"/"Temp
        # min") richtet sich damit nach genau denselben sichtbaren Zeilen.
        # Issue #1453: derselbe Uebersichtsblock wie im HTML-Teil -> dieselbe
        # Namensform (ausgeschriebener deutscher Registername). Ohne `form`
        # liefen HTML- und Klartext-Teil derselben Mail auseinander.
        ordered = _ordered_rows(_PLAIN_ROWS, enabled_metrics)
        labelled = derive_row_labels(
            [_CV2_BY_KEY[key] for key, _de, _fmt in ordered], form="long", lang=lang,
        )
        for (metric_id, _label_key, fmt), row in zip(ordered, labelled):
            value = _metric_value(loc_result, metric_id)
            cell = (
                # Issue #1680 S1: der Klartext-Teil der Mail zeigt die
                # Herkunft der Gewitterstufe genau wie der HTML-Teil.
                _fmt_overview_cell(
                    fmt, value, loc_result, include_origin=True, lang=lang,
                    metric_id=metric_id,
                    friendly=bool((metric_formats or {}).get(metric_id)),
                )
                if value is not None else "-"
            )
            lines.append(f"   {row['label']}: {cell}")

        lines.append("")

    # Issue #1405 S3: EIN Hinweis je Mail unter der Uebersicht, dieselbe Zahl
    # wie im HTML-Teil (Zeilen ohne Definition + unmappbare Eintraege).
    gap_notice = selection_gap_notice(
        rowless_count(enabled_metrics, _PLAIN_ROWS_BY_ID) + unresolved_count,
        scope="vergleich", lang=lang,
    )
    if gap_notice:
        lines.append(gap_notice)
        lines.append("")

    # Issue #1563: Vertretungshinweis je Ort, nur mit Zeilen (AC-4).
    fallback_zeilen = (
        build_compare_fallback_lines(locations, lang=lang) if show_fallback_notice else []
    )
    if fallback_zeilen:
        lines.extend(fallback_zeilen)
        lines.append("")

    # Stundentabelle + 3-Tage-Ausblick (Epic #1301 B4) je Ort, direkt
    # untereinander (Issue #1323: der Ausblick folgt unmittelbar auf den
    # Stundenblock desselben Orts, statt gesammelt in einer eigenen
    # "AUSBLICK"-Sektion am Textende). Fail-soft je Ort -- fehlt Stunden-
    # oder Ausblickdaten, entfaellt nur der jeweils fehlende Teil.
    # Issue #1366 F003 (Staging-Fund, AC-4): dieselbe Spaltenauflösung wie im
    # HTML-Pfad (derselbe ``_visible_hour_metrics``, #3096: immer eine konkrete
    # Liste) -- nur die gewaehlten, in der gewaehlten Reihenfolge (Issue
    # #1335/#1359).
    visible_hour_metrics = _visible_hour_metrics(hourly_metrics, _hour_zeilen())
    merge_wind_dir = _should_merge_wind_dir(hourly_metrics)
    section_lines: list[str] = []
    # Zweiter Staging-Fund (2026-07-26): `section_lines` ist ein GEMEINSAMER
    # Puffer fuer Stundentabelle UND 3-Tage-Ausblick. Die Ueberschrift an ihm
    # aufzuhaengen beschriftete bei leerer Stundenauswahl den Ausblick als
    # "STUNDENVERLAUF". Sie haengt jetzt an tatsaechlich geschriebenen
    # Stundenzeilen. Der HTML-Pfad hatte diese Kopplung nie: dort ist der
    # Sektionskopf ein eigener Block direkt an `hourly_enabled`
    # (compare_html.py:1139-1142), und der Ausblick wird getrennt davon in
    # `per_location_html` erzeugt -- zwei Bausteine statt eines Puffers.
    hour_rows_written = False
    for loc_result in locations:
        if loc_result.error is not None:
            continue
        # hourly_enabled=False laesst die Tabelle entfallen -- der Ausblick
        # haengt NICHT an dieser Bedingung (Issue #1323, bleibt unabhaengig).
        have_hourly = hourly_enabled and bool(loc_result.hourly_data)
        outlook_rows = (
            # Issue #2049: dieselbe Zuordnung wie der HTML-Pfad -- der
            # Pflicht-Validator liest nur HTML und ist im Klartext blind
            # (#1366-Erfahrung), die Zellen muessen trotzdem uebereinstimmen.
            _build_location_outlook_rows(
                loc_result, outlook_metrics, outlook_metric_formats, lang,
                ampel=ampel)
            if outlook_enabled and loc_result.outlook_hourly_data else []
        )
        # Fix #1505 (AC-4): bei eingeschaltetem Ausblick ohne Zeilen (weder
        # Rohdaten noch etwas nach der Metrik-Filterung) stand hier bisher
        # NICHTS -- der Ort fiel unten sogar ganz aus dem Abschnitt. Jetzt
        # tritt derselbe benannte Zustand an die Stelle wie im HTML-Teil
        # (geteilter Baustein aus #1486, keine zweite Formulierung).
        outlook_state_text = (
            render_outlook_state_plain(OutlookState.UNAVAILABLE, lang=lang)
            if outlook_enabled and not outlook_rows else None
        )
        if not have_hourly and not outlook_rows and not outlook_state_text:
            continue
        # Issue #1378 (AC-3): dieselbe Ortszeit-Auflösung wie im HTML-Pfad --
        # der Pflicht-Validator liest nur HTML, der Klartext braucht die
        # Umstellung deshalb eigenstaendig (#1366-Erfahrung).
        tz = location_tz(loc_result.location)
        # Adversary F002: jeder Ortsblock schreibt seine EIGENE Zeitbasis an
        # (analog `compare_html._location_heading`) -- die "Erstellt"-Kopfzeile
        # nennt nur die Zone des erstgenannten Ortes und sagt ueber die
        # uebrigen Bloecke nichts. Referenzzeitpunkt ist der erste Punkt, den
        # der Block auch zeigt (Kuerzel ist sommer-/winterabhaengig) -- bei
        # abgeschaltetem Stundenverlauf also der des Ausblicks, nicht der
        # ungenutzten `hourly_data` (seit #1366/9ae845d8 ein realer Fall).
        _points = loc_result.hourly_data if have_hourly else loc_result.outlook_hourly_data
        # Fix #1505: ohne jeden Datenpunkt (nur Zustandstext) gibt es keinen
        # Referenzzeitpunkt -- dann steht der Ortsname ohne angeschriebene
        # Zeitbasis da, statt eine erfundene zu behaupten (oder zu crashen).
        section_lines.append(
            f"{loc_result.location.name} ({tz_abbrev(_points[0].ts, tz)})"
            if _points else loc_result.location.name
        )
        if have_hourly:
            for dp in loc_result.hourly_data:
                ts = local_fmt(dp.ts, tz) if hasattr(dp.ts, "astimezone") else str(dp.ts)
                cells = []
                for m in visible_hour_metrics:
                    # Issue #3097: derselbe Einfach-Zweig wie in der HTML-Fassung.
                    einfach = _hour_einfach_text(
                        m, getattr(dp, m["key"], None), hourly_metric_formats,
                        lang, html=False, ampel=ampel)
                    # Issue #1475 Nachbesserung (AC-8, Klartext-Pendant der
                    # Compare-Stundentabelle): Hagel als Text-Anhang, wie in
                    # der HTML-Fassung -- nie als Ring (das ist nur Trip).
                    if einfach is not None:
                        text = einfach
                    elif m["fmt"] is _fmt_thunder:
                        # Issue #1680 S3 (Spec D4): die Herkunft der Stufe
                        # DIESER Stunde, wie in der HTML-Fassung -- HTML und
                        # Klartext derselben Mail haben zwei unabhaengige
                        # Aufrufstellen und duerfen nicht auseinanderlaufen
                        # (AC-4). Stufe und Traeger stammen aus DEMSELBEN `dp`.
                        # KANAL: die Compare-SMS erreicht diese Schleife nie --
                        # sie baut ihre Zelle ueber `_sms_metric_cell()` ->
                        # `_fmt_overview_cell(..., include_origin=False)`
                        # (PO-Entscheidung, dort aktiv abgewaehlt).
                        text = fmt_word_cell(
                            m["fmt"], getattr(dp, m["key"], None), lang,
                            getattr(dp, "hail_flag", None),
                            getattr(dp, "thunder_level_signals", None),
                        )
                    else:
                        text = fmt_word_cell(m["fmt"], getattr(dp, m["key"], None), lang)
                    if merge_wind_dir and m["key"] == "wind10m_kmh":
                        compass = degrees_to_compass(getattr(dp, "wind_direction_deg", None))
                        if compass:
                            text = f"{text} {compass}"
                    cells.append(f"{m['label']} {text}")
                section_lines.append(f"   {ts}  " + "  ".join(cells))
                hour_rows_written = True
        if outlook_rows:
            # Issue #1368: eigene Ueberschrift statt der Trip-Formulierung
            # "Nächste Etappen" (im Ortsvergleich gibt es keine Etappen) und
            # ohne das feste 26-Zeichen-Etappennamen-Feld, das der
            # Ortsvergleich nie befuellt (der Ortsname steht in der Zeile
            # darueber). Beides unabhaengig von einer gesetzten Auswahl --
            # sonst blieben Bestandsnutzer auf dem Fehler sitzen.
            section_lines.append(render_outlook_plain(
                outlook_rows, show_acc=False, metrics=outlook_metrics,
                heading=t("vergleich.ausblick.titel", lang), show_name=False, lang=lang,
                ampel=ampel,
            ).strip("\n"))
        elif outlook_state_text:
            # Fix #1505 (AC-4): benannter Zustand an derselben Stelle wie
            # sonst die Ausblick-Tabelle, unter derselben Ueberschrift.
            section_lines.append(t("vergleich.ausblick.titel", lang))
            section_lines.append(f"   {outlook_state_text}")
        section_lines.append("")

    if section_lines:
        if hour_rows_written:
            lines.append(t("vergleich.stunden.klartext_titel", lang))
            lines.append("-" * 15)
        lines.extend(section_lines)

    # Issue #1472: Einheiten- UND Spalten-Legende. Der Klartext-Teil hatte
    # bisher GAR KEINE Legende (auch keine Einheiten-Zeile) -- die englischen
    # Kuerzel der Stundenzeilen waren hier nirgends aufloesbar (ADR-0042).
    # Beide Zeilen entstehen aus derselben Ableitung wie im HTML-Teil
    # (`_units_legend_text`/`_column_legend_text` mit denselben sichtbaren
    # Spalten), damit HTML und Klartext derselben Mail nie auseinanderlaufen.
    # Bedingung identisch zum HTML-Pfad (`_render_legend`): nur bei
    # eingeschalteter Stundentabelle.
    # #2136/ADR-0068 (AC-5): dieselbe Bedingungserweiterung wie im HTML-Pfad
    # (`_render_legend`) -- die Spalten-Legende bleibt sichtbar, sobald der
    # Ausblick sichtbar ist, auch bei abgeschalteter Stundentabelle.
    if hourly_enabled or outlook_enabled:
        for _legend in (
            _units_legend_text(visible_hour_metrics, lang),
            _column_legend_text(visible_hour_metrics, outlook_metrics, outlook_enabled, lang),
        ):
            if _legend:
                lines.append(_legend)

    # Issue #1461 S3b-1 (AC-17): an derselben Stelle wie im HTML-Teil (vor
    # Legende/Fuss) und ueber DENSELBEN Baustein wie Trip und Compare-HTML --
    # keine zweite Fassung. Zeitbasis wie die Kopfzeile derselben Mail.
    if has_undelivered(undelivered):
        lines.append("")
        lines.append(render_undelivered_plain(
            undelivered, tz=location_tz(locations[0].location), lang=lang,
        ))
        lines.append("")

    from output.renderers.email.command_block import render_commands_plain
    lines.append("")
    lines.append(render_commands_plain("vergleich", lang=lang))
    lines.append("")
    lines.append("---")
    lines.append("Gregor Zwanzig")

    return "\n".join(lines)


def render_compare_email(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    enabled_metrics: list[str] | None = None,
    hourly_metrics: set | None = None,
    hourly_enabled: bool = True,
    preset_name: Optional[str] = None,
    corridors: list[Corridor] | None = None,
    outlook_enabled: bool = False,
    outlook_metrics: list[dict] | None = None,
    outlook_metric_formats: dict[str, bool] | None = None,
    undelivered: list | None = None,
    preset: dict,
    unresolved_count: int = 0,
    lang: Lang = "de",
    show_fallback_notice: bool = False,
    metric_formats: dict[str, bool] | None = None,
    hourly_metric_formats: dict[str, bool] | None = None,
) -> tuple[str, str]:
    """Render both HTML and plain-text parts for a compare email (v2, #1110).

    Single entry point for all compare-email render callers. Keeps the HTML
    renderer (output.renderers.email.compare_html) and the plain-text renderer
    (this module) in one place. Kein Score/Winner mehr -- ``winner_tags``
    entfaellt vollstaendig. ``top_n_details`` (Issue #1104) ist mit Issue #1360
    ersatzlos entfallen -- der Wert wurde von jedem Renderer verworfen, die Mail
    zeigt immer ALLE Orte. ``enabled_metrics``
    filtert die numerischen Uebersichts-Zeilen (s. ``render_compare_html``).
    ``hourly_metrics`` (Issue #1106) filtert die Wert-Spalten je
    Stundentabelle-Ort-Sektion, analog ``enabled_metrics``. ``hourly_enabled``
    (Issue #1107) schaltet die komplette Stundenverlauf-Sektion ein/aus.
    ``corridors`` (Issue #1231, Slice 7) reicht die Preset-Korridore fuer die
    mark-Markierung durch (s. ``render_compare_html``), wirkt nur auf die
    HTML-Zellfaerbung, der Klartext-Pfad bleibt unberuehrt.

    Returns:
        Tuple of (html_body, text_body).
    """
    from output.renderers.email.compare_html import render_compare_html

    html_body = render_compare_html(
        result,
        profile=profile,
        warnings=warnings,
        enabled_metrics=enabled_metrics,
        hourly_metrics=hourly_metrics,
        hourly_enabled=hourly_enabled,
        preset_name=preset_name,
        corridors=corridors,
        outlook_enabled=outlook_enabled,
        outlook_metrics=outlook_metrics,
        outlook_metric_formats=outlook_metric_formats,
        # Issue #1461 S3b-1: geteilter Hinweis-Baustein, derselbe wie im Trip.
        undelivered=undelivered,
        # Issue #1969 (AC-26): das rohe Preset fuer den Fuss "Naechster Versand".
        preset=preset,
        # Issue #1405 S3: dieselbe Zahl in BEIDE Fassungen der Mail.
        unresolved_count=unresolved_count,
        lang=lang,
        # Issue #1563: Vertretungshinweis in BEIDE Fassungen (nur Briefing).
        show_fallback_notice=show_fallback_notice,
        # Issue #3039: Roh/Einfach je Zeile aus `channel_layouts["email"]`.
        metric_formats=metric_formats,
        # Issue #3097: Roh/Einfach je Stundenverlauf-Spalte (eigener Schalter).
        hourly_metric_formats=hourly_metric_formats,
    )
    text_body = render_comparison_text(
        result, profile=profile, enabled_metrics=enabled_metrics,
        outlook_enabled=outlook_enabled,
        # Issue #1361/#1368: dieselbe Ausblick-Auswahl wie der HTML-Pfad --
        # der Pflicht-Validator liest nur HTML, der Klartext braucht sie
        # deshalb eigenstaendig (#1366-Erfahrung).
        outlook_metrics=outlook_metrics,
        # Issue #2049: aus demselben Grund auch die Roh/Einfach-Zuordnung.
        outlook_metric_formats=outlook_metric_formats,
        # Issue #1366 F003 (Staging-Fund, AC-4): dieselbe Quelle wie der
        # HTML-Pfad oben -- vorher kannte render_comparison_text diese beiden
        # Parameter gar nicht, der Klartext-Teil zeigte die Stundentabelle
        # unabhaengig von Auswahl/Schalter.
        hourly_metrics=hourly_metrics,
        hourly_enabled=hourly_enabled,
        # Issue #1461 S3b-1 (AC-17): beide Fassungen der Mail werden
        # zugestellt -- der Abschnitt gehoert in BEIDE, sonst waere der
        # Ortsvergleich gegenueber dem Trip (`email/plain.py`) schlechter
        # gestellt (Teilungs-Invariante).
        undelivered=undelivered,
        unresolved_count=unresolved_count,
        lang=lang,
        show_fallback_notice=show_fallback_notice,
        preset=preset,
        # Issue #3039: der Klartext zieht dieselbe Zeilenliste samt Format.
        metric_formats=metric_formats,
        hourly_metric_formats=hourly_metric_formats,
    )
    return html_body, text_body


# ---------------------------------------------------------------------------
# Kanal-Renderer Telegram / SMS (Issue #1270, Scheibe S3)
#
# SPEC: docs/specs/modules/compare_channel_preview_dispatch.md (AC-3)
# Neutralitaets-Vertrag identisch zu render_comparison_text (#1110): KEIN
# Score, KEIN Rang, keine Gewinner-Hervorhebung -- Score bleibt ausschliesslich
# interne Sortiergroesse der ComparisonEngine. Orte erscheinen in der vom
# Nutzer eingestellten Folge (gemeinsamer Helfer ``location_render_order``,
# #1359), damit die interne Score-Reihenfolge sich nicht als sichtbares
# Ranking niederschlaegt.
# Metrik-Vokabular = die Uebersichts-Metrik-IDs von render_comparison_text
# (Quelle: resolve_compare_render_options -> resolve_enabled_metrics). Keine
# eigene Metrik-Liste, insbesondere kein confidence_pct (#710/ADR-0005).
# ---------------------------------------------------------------------------

# Issue #3047 B-L4 (Runde 7, Tech-Lead-Entscheidung "Orte nie eingestellt =
# was die Mail zeigt", ADR-0095): ohne gespeicherte Auswahl (``None``) zeigen
# Telegram, SMS und Premium-SMS dieselben Zeilen in derselben Folge wie die
# Vergleichstabelle der Mail (``_visible_metrics(None)`` = alle CV2-Zeilen).
# Loest die fruehere feste Sechserliste ``_CHANNEL_METRICS`` ab (#1362 AC-7),
# in der Regen, Boeen und Gewitter fehlten. Kanal-Grenzen bleiben: SMS kuerzt
# vom Listenende (AC-23), Telegram ab Platz 8 in Zeile 2 (AC-24).
_NIE_EINGESTELLT_IDS: tuple[str, ...] = tuple(row[0] for row in _PLAIN_ROWS)

# Issue #1362 (Scheibe S5a): Label+Formatierung fuer ALLE 26 Compare-Groessen
# ueber dieselbe Tabelle wie der Klartext-Teil (_PLAIN_ROWS) -- ersetzt die
# alte 6-Groessen-if-Kette (_format_channel_metric) fuer den Telegram-Pfad.
_PLAIN_ROWS_BY_ID = {row[0]: row for row in _PLAIN_ROWS}


def _friendly_overview_text(
    metric_id: str, value, *, sms: bool, lang: Lang = "de",
) -> str | None:
    """Einfachform einer Uebersichtszeile (Issue #3039) oder ``None`` (= Roh).

    Wiederverwendung statt Parallel-Logik: Text-Kanaele (Telegram, Klartext
    der Mail) nutzen dieselbe Wort-/Symbol-Kette wie der Ausblick
    (``_friendly_outlook_text``: Tageswerte, Wind-/Boeen-Wort, Wolkensymbol,
    Himmelsrichtung). Die SMS kennt eine Einfachform nur fuer
    ``SMS_FORMAT_MODE_METRIC_IDS`` (Wolken als GSM-7-Stufe wie die Trip-SMS),
    sonst bleibt sie Roh. Ohne eigene Einfachform bleibt die Zahl."""
    from app.metric_catalog import SMS_FORMAT_MODE_METRIC_IDS
    from output.renderers.compare_outlook_metric_ids import _friendly_outlook_text
    from output.tokens.metrics import cloud_stufe

    catalog_id = _CV2_BY_KEY.get(metric_id, {}).get("metric_id")
    if catalog_id is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if sms:
        return cloud_stufe(number) if catalog_id in SMS_FORMAT_MODE_METRIC_IDS else None
    return _friendly_outlook_text(catalog_id, number, lang)


def _fmt_overview_cell(
    fmt, value, loc_result: LocationResult, *, include_origin: bool = False,
    lang: Lang = "de", metric_id: str | None = None, friendly: bool = False,
    sms: bool = False, summary=None,
) -> str:
    """Issue #1475 Nachbesserung (Punkt 5b, Aufrufstellen 3/5/6): DIE EINE
    Stelle, an der die Ortsvergleich-Kanaele Klartext, SMS und Telegram ihren
    Uebersichtswert formatieren.

    Fuer die Gewitter-Zeile wird zusaetzlich das Hagel-Kennzeichen DIESES
    Ortes durchgereicht; alle uebrigen Zeilen bleiben zeichengleich. Ohne
    diesen gemeinsamen Baustein haette jeder der drei Kanaele eine eigene
    Kopie derselben Fallunterscheidung bekommen (#1481).

    Issue #1680 S1: ``include_origin`` schaltet die Herkunft der Gewitterstufe
    zu. 🔴 Default ``False``, weil dieselbe Funktion AUCH die SMS-Zelle baut
    und die PO-Entscheidung dort ausdruecklich KEINE Herkunft vorsieht -- ohne
    diesen Schalter leckte der Zusatz automatisch in die SMS, wuerde dort vom
    GSM-7-Filter zu "-" entstellt und verdraengte ueber den "+N"-Mechanismus
    hintere Metriken.

    Issue #3039: ``friendly`` (Einfach aus ``channel_layouts``) schaltet fuer
    ``metric_id`` die Einfachform zu; ``sms`` beschraenkt sie auf die
    GSM-7-sicheren SMS-Formen. Default ``False`` = heutiger Festzustand.
    """
    if friendly and metric_id is not None:
        einfach = _friendly_overview_text(metric_id, value, sms=sms, lang=lang)
        if einfach is not None:
            return einfach
    if fmt is _fmt_thunder:
        # ``summary`` (Issue #3047 B-L4): das je Ort einmal berechnete Aggregat.
        signale = loc_thunder_signals(loc_result, summary) if include_origin else None
        return fmt_word_cell(fmt, value, lang, loc_hail_flag(loc_result, summary), signale)
    return fmt_word_cell(fmt, value, lang)

# Issue #1362 (Scheibe S5b): Compare-Renderer-ID -> zentrale Katalog-Metrik-ID
# (wie von ``metric_catalog.kurzform_kuerzel()`` erwartet), abgeleitet aus den
# ZWEI bestehenden Uebersetzungstabellen -- kein drittes, hier neu getipptes
# Vokabular (s. Spec "Vier inkompatible Metrik-Vokabulare").
#
# Issue #2232: gelesen wird die KUERZEL-Kennung (``kuerzel_metric_id`` mit
# Rueckfall auf ``metric_id``, aufgeloest ueber ``kuerzel_metric_id_for()`` --
# eine Regel, eine Stelle). Nur so senden Trip und Ortsvergleich fuer
# Tageshoechst/-tiefst dasselbe Kuerzel (``D``/``L``/``FD``/``FL``). Die
# Auflösungs-Identitaet (``metric_id``) bleibt davon unberuehrt: sie traegt
# weiterhin Wert, Fenster, Alarm, Ausblick und Persistenz.
_METRIC_ID_BY_FRONTEND_KEY = {
    entry["key"]: kuerzel_metric_id_for(entry) for entry in COMPARE_METRIC_CATALOG
}
_RENDERER_TO_CATALOG_METRIC_ID: dict[str, str] = {
    renderer_id: _METRIC_ID_BY_FRONTEND_KEY[frontend_key]
    for frontend_key, renderer_id in FRONTEND_TO_RENDERER_METRIC_ID.items()
}

# Issue #1362 S5b, Adversary-Fund Runde 4 (PO-Entscheidung 2026-07-30, echter
# Staging-Nachweis): das Grad-Zeichen `°` gehoert NICHT zum GSM-7-Zeichensatz
# (GSM 03.38) -- sobald es in der SMS steht, kodiert der Betreiber die GANZE
# Nachricht in UCS-2 (67 statt 153 Zeichen je Teil bei Verkettung), eine
# STILLE Kostenverdopplung. Nur der SMS-Pfad ist betroffen: `unit="°C"/"°"`
# bleibt im Katalog (`metric_catalog.py`) unveraendert -- Mail und Telegram
# lesen es weiterhin korrekt ueber `format_value`/`_PLAIN_ROWS` direkt. Die
# Umwandlung sitzt bewusst NUR hier, wo die SMS-Zelle gebaut wird.
#
# Zweiter, beim Bau des GSM-7-Waechters gefundener Fall (nicht Teil der
# PO-Meldung, gleiche Fehlerklasse): `ThunderLevel.NONE` ist ein echter Wert
# (kein fehlender, der schon vorher herausgefiltert wuerde) und formatiert
# ueber `_THUNDER_LEVEL_LABEL` auf den Halbgeviertstrich "—" (U+2014) --
# ebenfalls GSM-7-fremd. Ersetzt durch den GSM-7-eigenen Bindestrich "-"
# (0x2D), der optisch denselben Platzhalter-Charakter traegt.
_SMS_GSM7_UNSAFE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("°", ""),
    ("—", "-"),
    # Issue #1670: der Platzhalter ist jetzt `metric_format.NO_VALUE` (EN DASH
    # U+2013) -- ebenfalls GSM-7-fremd; die SMS bleibt zeichengleich "-".
    ("–", "-"),
    # Issue #1475 Nachbesserung: `_fmt_thunder` haengt den Hagel-Hinweis mit
    # einem Mittelpunkt an -- der ist wie der Geviertstrich nicht GSM-7.
    ("·", "-"),
)


def _sms_gsm7_safe(text: str) -> str:
    """Ersetzt bekannte GSM-7-fremde Zeichen aus den geteilten
    Werte-Formatierungsfunktionen (``_PLAIN_ROWS``) durch GSM-7-taugliche
    Entsprechungen -- ausschliesslich fuer den SMS-Zellwert, NICHT fuer
    Telegram/Mail (die denselben ``fmt``/``format_value`` unveraendert
    nutzen)."""
    for bad, good in _SMS_GSM7_UNSAFE_REPLACEMENTS:
        text = text.replace(bad, good)
    return text


def _sms_metric_cell(
    loc_result: LocationResult, metric_id: str, friendly: bool = False,
    *, summary=None,
) -> str | None:
    """"Kuerzel Wert"-Zelle fuer ``metric_id`` (Issue #1362 Scheibe S5b, Spec
    Implementation Details Punkt 3). Wert+Formatierung kommen aus derselben
    Quelle wie der Klartext-Teil (``_PLAIN_ROWS``/``_metric_value``),
    GSM-7-saniert ueber ``_sms_gsm7_safe`` (Adversary-Fund Runde 4); das
    Kuerzel AUSSCHLIESSLICH aus dem zentralen Katalog
    (``metric_catalog.kurzform_kuerzel`` -- dieselbe Rangfolge, die auch
    ``/api/sms-symbols`` fuer die Editor-Marke benutzt), nie zur Laufzeit
    abgeleitet.

    Issue #2232: das Auswertungszeichen (``+`` fuer Hoechst-, ``-`` fuer
    Tiefstwert, PO-Entscheidung 2026-07-29) ist ERSATZLOS entfallen. Es war
    noetig, solange beide Richtungen dasselbe Kuerzel trugen; seit die
    Kuerzel-Kennung ueber ``kuerzel_metric_id`` aufgeloest wird, tragen sie
    eigene (``D``/``L``, ``FD``/``FL``) -- dieselben, die die Trip-SMS sendet.
    Das spart zwei Zeichen je Zelle im 153-Zeichen-Budget.

    ``None`` = kein Wert an diesem Ort ODER keine ``metric_id``/kein Kuerzel
    bekannt -- die Zelle entfaellt dann und zaehlt im Zaehler ``?N`` des
    Ortsteils (Issue #1405 S3, ``_sms_location_part``)."""
    row = _PLAIN_ROWS_BY_ID.get(metric_id)
    if row is None:
        return None
    _, _label, fmt = row
    # ``summary`` (Issue #3047 B-L4): einmal je Ort berechnetes Tages-Aggregat;
    # ohne es leitet ``_metric_value`` es je Zelle neu ab.
    value = _metric_value(loc_result, metric_id, summary)
    if value is None:
        return None
    catalog_id = _RENDERER_TO_CATALOG_METRIC_ID.get(metric_id)
    code = kurzform_kuerzel(catalog_id) if catalog_id else ""
    if not code:
        return None
    # Issue #1680 S1 (Spec D8): ``include_origin`` bleibt hier AKTIV ABGEWAEHLT
    # auf dem Default ``False`` -- die SMS zeigt die Gewitterstufe, aber KEINE
    # Herkunft. PO-Entscheidung, kein vergessener Anschluss. Drei Gruende:
    # (1) 153 Zeichen Gesamtbudget und kein Spaltenbudget fuer einen zweiten
    # ``·``-Abschnitt je Ort; (2) ``_sms_gsm7_safe`` entstellt den Trenner
    # ``·`` zu ``-``, der Zusatz saehe entstellt aus; (3) der
    # ``+N``-Mechanismus wuerde die vom Zusatz verdraengten hinteren Metriken
    # nur noch zaehlen statt zeigen. Gilt ueber denselben Renderer auch fuer
    # Premium-SMS, sobald der Ortsvergleich ihn bedient.
    zelle = _fmt_overview_cell(
        fmt, value, loc_result, metric_id=metric_id, friendly=friendly, sms=True,
        summary=summary,
    )
    return f"{code} {_sms_gsm7_safe(zelle)}"


def _ampel_stunde(loc_result: LocationResult, metric_id: str, value, *, ampel: dict | None) -> str:
    """Issue #3047 B-L3 (Konzept §5 P8, ADR-0097): ``@h``-Marke einer
    Ampel-Groesse wie im Trip-Telegram (``narrow._overview_line``): nur wenn
    der Wert nach den Ampel-Grenzen des Presets gelb oder schlechter ist; die
    Stunde ist die Spitzen- (obere Grenze) bzw. Tiefststunde (untere Grenze)
    der Stundenwerte des Ortes in Ortszeit. "" = gruen, keine Ampel-Groesse,
    keine Ampel (Preset fehlt) oder keine Stundenwerte."""
    catalog_id = _CV2_BY_KEY.get(metric_id, {}).get("metric_id")
    # Groessen ohne Ampel-Leser liefern ueber ``ampel_seite`` nie eine Seite.
    if ampel is None or isinstance(value, bool):
        return ""
    try:
        seite = ampel_seite(ampel, catalog_id, float(value))
    except (TypeError, ValueError):
        return ""
    if seite is None:
        return ""
    feld = get_metric(catalog_id).dp_field
    punkte = [(p.ts, getattr(p, feld, None)) for p in loc_result.hourly_data]
    punkte = [(ts, float(v)) for ts, v in punkte if v is not None]
    if not punkte:
        return ""
    werte = [v for _, v in punkte]
    ziel = max(werte) if seite == "oben" else min(werte)
    ts = punkte[werte.index(ziel)][0]
    return f"@{local_dt(ts, location_tz(loc_result.location)).hour:02d}"


def _plain_metric_cell(
    loc_result: LocationResult, metric_id: str, lang: Lang = "de",
    friendly: bool = False, *, ampel: dict | None, summary=None,
) -> str | None:
    """"Label Wert"-Zelle fuer ``metric_id``, aus derselben Quelle wie der
    Klartext-Teil derselben Mail (``_PLAIN_ROWS``/``_metric_value``, Issue
    #1362 -- keine zweite Werte-/Formatierungsquelle). ``None`` = Wert nicht
    vorhanden ODER ``metric_id`` unbekannt (Zelle entfaellt).

    ``ampel`` (Issue #3047 B-L3): bei Einfach traegt eine Ampel-Groesse die
    ``@h``-Marke des Trip-Telegrams (``_ampel_stunde``)."""
    row = _PLAIN_ROWS_BY_ID.get(metric_id)
    if row is None:
        return None
    _, label_key, fmt = row
    value = _metric_value(loc_result, metric_id, summary)
    if value is None:
        return None
    zelle = _fmt_overview_cell(
        fmt, value, loc_result, include_origin=True, lang=lang,
        metric_id=metric_id, friendly=friendly, summary=summary,
    )
    marke = _ampel_stunde(loc_result, metric_id, value, ampel=ampel) if friendly else ""
    return f"{t(label_key, lang)} {zelle}{marke}"


def _channel_layout_for_metrics(channel: str, metric_ids: list[str]):
    """Baut aus einer bereits ORTS-GEFILTERTEN, nutzergeordneten Metrik-ID-
    Liste (``metric_ids`` -- seit #1359 Listenposition = Reihenfolge) eine
    ``UnifiedWeatherDisplayConfig`` und delegiert Priorisierung/Abschneiden an
    ``channel_layout.render_for_channel()`` -- dieselbe Logik wie der
    Trip-Kanal-Renderer (Issue #1362, Spec 'Die Naht'). Alle gewaehlten
    Groessen werden ``bucket="primary"`` (Compare kennt keine
    primary/secondary-Unterscheidung); ``order`` ist die Listenposition.

    Adversary-Korrektur (Gegenpruefung #1362): der Aufrufer MUSS
    ``metric_ids`` bereits auf die an diesem Ort tatsaechlich vorhandenen
    Werte gefiltert haben -- diese Funktion selbst kennt keine Orte/Werte
    mehr und darf deshalb je Ort mit unterschiedlichen Listen aufgerufen
    werden (s. ``render_compare_telegram``). Der fruehere ``None``-Fallback
    auf die alte Sechserliste ist in den Aufrufer gewandert (dort steht auch
    die Ortsabhaengigkeit). KEIN ``auto_distribute()`` -- das schluesselt auf
    Trip-Metrik-IDs, ein zu Compare inkompatibles Vokabular (s. Spec
    Implementation Details Punkt 1)."""
    metrics = [
        MetricConfig(metric_id=mid, bucket="primary", order=i)
        for i, mid in enumerate(metric_ids)
    ]
    dc = UnifiedWeatherDisplayConfig(metrics=metrics)
    return render_for_channel(channel, dc, report_type="evening")


def render_compare_telegram(
    result: ComparisonResult,
    *,
    enabled_metrics: list[str] | None = None,
    preset_name: Optional[str] = None,
    unresolved_count: int = 0,
    lang: Lang = "de",
    show_fallback_notice: bool = False,
    metric_formats: dict[str, bool] | None = None,
    outlook_enabled: bool = False,
    outlook_metrics: list[dict] | None = None,
    outlook_metric_formats: dict[str, bool] | None = None,
    preset: dict | None = None,
) -> str:
    """Rendert einen Orts-Vergleich als Telegram-Nachricht (Issue #1270).

    ``outlook_*``/``preset`` (Issue #3047 B-K7): 3-Tages-Ausblick je Ort mit
    denselben Optionen wie ``render_compare_email`` (Ampel aus ``preset``);
    Default aus = bisheriges Verhalten.

    ``metric_formats`` (Issue #3039): ``{renderer_id: einfach}`` aus
    ``channel_layouts``; ``None`` = heutiger Festzustand (Roh).

    ``show_fallback_notice`` (Issue #1563): Vertretungshinweis je Ort als
    Abschluss unter den Ortsbloecken (nur Briefing-Langform; Default ``False``).

    ``lang`` (Issue #2666): beschriftete Langform (Kopf, Zeilen, Hinweise) in
    Nutzersprache; Warnungs-Bubble folgt P6 (#2668).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["telegram"]``: ``max_table_cols`` = 8 zaehlt inkl. der
    impliziten Zeit-/Orts-Spalte, also hoechstens 7 Metrik-Werte je Ort;
    ``max_chars`` = 4096 begrenzt die Gesamtnachricht.

    Issue #1405 S3: ``unresolved_count`` = gewaehlte Eintraege ohne Renderer-
    Zuordnung (``CompareRenderOptions.unresolved_by_channel``); sie fehlen an
    JEDEM Ort und zaehlen in den "ohne Wert"-Hinweis jedes Ortsblocks.
    """
    limits = CHANNEL_LIMITS["telegram"]
    # Issue #1362: die feste Sechserliste verliert ihre Torwaechter-Rolle --
    # die Nutzerauswahl (dedupliziert, in ihrer Reihenfolge; `None` faellt
    # auf die alte Sechserliste zurueck, AC-7) geht in ein Layout ueber
    # channel_layout.render_for_channel() (Spec 'Die Naht').
    # Adversary-Korrektur (Gegenpruefung #1362): Werte sind ORTSABHAENGIG
    # (z.B. fehlende hourly_data bei Fallback-Ausfall) -- das Layout wird
    # deshalb JE ORT innerhalb der Schleife gebaut, NICHT einmal vorab. Eine
    # Groesse ohne Wert an diesem Ort wird VOR dem Aufruf von
    # `_channel_layout_for_metrics` herausgefiltert, damit sie keinen der 7
    # Plaetze belegen und keine andere, gueltige Groesse verdraengen kann.
    dedup_ids = list(dict.fromkeys(
        enabled_metrics if enabled_metrics is not None else _NIE_EINGESTELLT_IDS
    ))

    locations = location_render_order(result.locations)
    if not locations:
        return t("vergleich.allgemein.keine_daten", lang)

    header: list[str] = []
    titel = t("vergleich.kopf.titel", lang)
    header.append(f"{titel} — {preset_name}" if preset_name else titel)
    header.append(t("vergleich.kopf.datum", lang,
                    datum=fmt_date_numeric(result.target_date, lang)))
    # Issue #1268: Zeitfenster-Zeile ersatzlos entfernt (Bewertung = ganzer Tag),
    # analog render_comparison_text() und compare_html._render_header().
    header.append("")
    # Issue #3047 B-L2 (ADR-0095): Warndienst nicht erreichbar -> derselbe
    # Hinweis wie Trip-Telegram und Vergleichs-Mail (geteilter Baustein, in
    # Nutzersprache), vor den Ortsbloecken, weil sicherheitsrelevant.
    if any_official_alerts_unavailable(locations):
        header.extend([render_official_alerts_unavailable_plain(lang=lang), ""])

    # Issue #3047 B-K7/AC-24: 3-Tages-Ausblick je Ort wie beim Trip-Telegram.
    # Ampel aus dem Preset (Einstieg wie render_compare_email) -- nie still
    # "allgemein": ohne Preset kein Ausblick (Profil-Ampel S1c-4b, AC-25).
    if outlook_enabled and preset is None:
        raise TypeError("render_compare_telegram: preset ist Pflicht bei outlook_enabled")
    # Issue #3047 B-L3: die Preset-Ampel wirkt auch auf Einfach-Zellen der Liste.
    ampel = resolve_ampel(preset) if preset is not None else None
    outlook = (outlook_enabled, outlook_metrics, outlook_metric_formats, ampel)
    blocks: list[list[str]] = [
        _telegram_location_block(
            loc_result, dedup_ids, lang, metric_formats, unresolved_count, outlook,
            zaehle_fehlende=enabled_metrics is not None,
        )
        for loc_result in locations
    ]

    max_chars = limits["max_chars"]
    # Metrik-Platzmangel-/Ohne-Daten-Hinweise stecken bereits als Zeilen IN
    # den jeweiligen `blocks` (s.o.) -- die folgende Ueberlauf-Logik behandelt
    # Ortsbloecke deshalb wieder atomar wie vor #1362, ohne einen separaten
    # Metrik-Hinweis mitzurechnen.
    # Issue #1563: Vertretungshinweis als Abschluss, NICHT als eigener Block
    # (sonst zaehlte die Einpass-Logik ihn als verworfenen Ort).
    zeilen = build_compare_fallback_lines(locations, lang=lang) if show_fallback_notice else []
    trailer = "\n\n" + "\n".join(zeilen) if zeilen else ""
    text = _join_telegram(header, blocks) + trailer
    if max_chars is None or len(text) <= max_chars:
        return text
    # Issue #2666: EIN Hinweis-Baustein in Nutzersprache fuer alle drei
    # Stellen der Einpass-Logik (Laenge pruefen = Laenge anhaengen).
    return _fit_telegram(
        header, blocks, max_chars - len(trailer), lambda n: _telegram_notice(n, lang),
    ) + trailer


def _telegram_location_block(
    loc_result, dedup_ids: list[str], lang: Lang, metric_formats: dict[str, bool] | None,
    unresolved_count: int, outlook: tuple, *, zaehle_fehlende: bool = True,
) -> list[str]:
    """Ein Ortsblock des Orts-Vergleichs-Telegrams (Name, Warnung, Werte,
    Ausblick). ``outlook`` = ``(enabled, metrics, formats, ampel)``.

    ``zaehle_fehlende=False`` (Issue #3047 B-L4, "nie eingestellt"): Zeilen
    ohne Wert entfallen ohne "ohne Wert"-Hinweis -- der Nutzer hat nichts
    gewaehlt, und die Mail zeigt dafuer ebenfalls keinen Hinweis
    (``rowless_count(None) == 0``)."""
    block = [loc_result.location.name]
    if loc_result.error is not None:
        block.append("   " + t("vergleich.ort.fehler", lang, fehler=loc_result.error))
        return block
    warn_text = _telegram_warn_text(loc_result, lang)
    if warn_text:
        block.append(f"   {warn_text}")
    # Werte sind ortsabhaengig -- Verfuegbarkeit VOR der Prioritaets-/
    # Slot-Kappung pruefen (Adversary-Korrektur), nicht erst beim
    # Zellenbau. `cell_values` haelt jede Zelle nur einmal vor (keine
    # doppelte `_metric_value`/`_daily_summary`-Berechnung).
    # Issue #3047 B-L4: Tages-Aggregat EINMAL je Ort (nie eingestellt = alle
    # Zeilen der Mail; je Zelle neu abgeleitet waere das ein Vielfaches).
    summary = _daily_summary(loc_result) if loc_result.hourly_data else None
    cell_values = {
        mid: _plain_metric_cell(
            loc_result, mid, lang, friendly=bool((metric_formats or {}).get(mid)),
            ampel=outlook[3], summary=summary,
        )
        for mid in dedup_ids
    }
    available_ids = [mid for mid in dedup_ids if cell_values[mid] is not None]
    fehlend = len(dedup_ids) - len(available_ids) if zaehle_fehlende else 0
    no_data_count = fehlend + unresolved_count
    layout = _channel_layout_for_metrics("telegram", available_ids)
    # Issue #3047 B-K5/AC-24 (PO-Entscheidung 2026-11-16): nichts faellt weg.
    # Die ersten Plaetze (Tabellen-Budget des Layouts) bilden Zeile 1, alle
    # weiteren Zeilen der Liste folgen in Listenfolge in Zeile 2 desselben
    # Ortes -- statt eines Kappungshinweises "vollstaendig per E-Mail".
    erste = list(layout.table_columns)
    zweite = [mid for mid in available_ids if mid not in erste]
    block.append("   " + (" · ".join(cell_values[mid] for mid in erste) if erste
                             else t("vergleich.telegram.keine_werte", lang)))
    if zweite:
        block.append("   " + " · ".join(cell_values[mid] for mid in zweite))
    # Ohne-Daten-Zaehler (Invariante: sichtbare Zellen + Ohne-Daten-Zaehler ==
    # Anzahl gewaehlter Groessen), eigene Zeile INNERHALB dieses Ortsblocks.
    if no_data_count > 0:
        block.append("   " + _telegram_no_data_notice(no_data_count, lang))
    block.extend(_telegram_outlook_lines(loc_result, outlook, lang))
    return block


def _telegram_warn_text(loc_result, lang: Lang) -> str:
    """Amtliche Warnung eines Ortes fuer den Telegram-Ortsblock ("" ohne)."""
    # Issue #3047 (Konzept WV6, ADR-0095): wie in der Vergleichs-Mail steht
    # die amtliche Warnung ZUERST im Ortsblock, vor den Werten (SMS/
    # Premium-SMS: am Ende, dort unveraendert).
    # Issue #1332 (PO-Korrektur 2026-07-23): Sicherheits-Filter + geteilte,
    # kontext-agnostische Bausteine (`build_official_alert_notices`/
    # `render_official_alert_telegram`, `trip=None` fuer den einzelnen
    # Ort) -- exakt dasselbe narrative Format wie das Trip-Telegram.
    # KEIN SMS-Kuerzel-Marker hier: Compare-Telegram soll wie
    # Trip-Telegram aussehen (ausgeschrieben, kein `!TH:H`); das Kuerzel
    # bleibt exklusiv im SMS-Pfad (`_sms_location_part`).
    # Issue #1332 F001 (Adversary HIGH): `trip=None` liefert je Ort ein
    # `scope_label` von "unbekannt" (kein Trip-Segment bekannt) -- dieser
    # Render-Pfad baut aber JE ORT einen eigenen Block, dessen
    # Ortsname bereits als `prefix`/Block-Ueberschrift steht. Ein
    # Scope-Segment waere hier IMMER redundant oder irrefuehrend, egal ob
    # "unbekannt" oder (ueber den Compare-Builder) "alle Orte" fuer genau
    # den einen Block -- daher `show_scope=False` statt eines zweiten
    # Builder-Aufrufs mit demselben Ergebnis.
    # Issue #1461 S3b-2b (AC-17): der feste Vergleichswert `MIN_SMS_LEVEL`
    # (orange) geht in der Startschwelle "gering" auf -- derselbe Wechsel
    # wie beim Trip-Bericht (S3b-2a, `sms_trip.py::_official_alert_entries`).
    # Kein Compare-Kanal-Schwellenparameter hier: der Bericht bleibt beim
    # Startwert, unabhaengig von einer je Kanal eingestellten Alarm-Schwelle
    # (Spec "Zwei Wirkungsorte" -- Bericht und Alarm-Versand sind getrennt).
    _min_level = alert_urgency.min_official_level_for_threshold("LOW")
    filtered = [a for a in loc_result.official_alerts if a.level >= _min_level]
    if filtered:
        notices = build_official_alert_notices(None, [(a, []) for a in filtered], lang=lang)
        sources = list(dict.fromkeys(
            official_alert_source_label(a.source, lang=lang) for a in filtered
        ))
        warn_text = render_official_alert_telegram(
            notices, prefix=loc_result.location.name,
            source_label=" · ".join(sources), show_scope=False,
            tz=location_tz(loc_result.location), lang=lang,
        )
        # Issue #3047 p2b: der Orts-Vergleich geht mit parse_mode=None hinaus
        # (telegram_format.md) -- die HTML-Vorlage des Trips wird hier zu
        # Klartext (Tags weg, Entities aufgeloest), sonst saehe der Nutzer
        # "<b>" und "&amp;" woertlich. Nutzerdaten sind in der Vorlage
        # escaped, ein "<" im Ortsnamen ist also nie ein Tag.
        return _html.unescape(_HTML_TAG_RE.sub("", warn_text))
    return ""


def _telegram_outlook_lines(loc_result, outlook: tuple, lang: Lang) -> list[str]:
    """Issue #3047 B-K7/AC-24: 3-Tages-Ausblick eines Ortes im Telegram.

    Zeilen aus demselben Zeilenbau wie die Vergleichs-Mail
    (``_build_location_outlook_rows``: Ausblick-Liste, Folge, Roh/Einfach),
    Form und Kopf aus dem Trip-Telegram (``narrow._outlook_lines``, EIN Code
    fuer beide Kontexte). Schalter aus oder bewusst leere Liste -> nichts;
    eingeschaltet ohne Daten -> benannter Zustand wie in der Mail."""
    enabled, metrics, formats, ampel = outlook
    if not enabled or metrics == []:
        return []
    rows = (
        _build_location_outlook_rows(loc_result, metrics, formats, lang, ampel=ampel)
        if loc_result.outlook_hourly_data else []
    )
    if rows:
        from output.renderers.narrow import _outlook_lines

        lines = _outlook_lines(rows, metrics, lang=lang, ampel=ampel)
    else:
        lines = [t("telegram.kopf.ausblick", lang),
                 render_outlook_state_plain(OutlookState.UNAVAILABLE, lang=lang)]
    # Kein HTML-Escaping: der Orts-Vergleich geht mit parse_mode=None hinaus.
    return ["   " + z for z in lines]


def _fit_telegram(header: list[str], blocks: list[list[str]], max_chars: int, hinweis) -> str:
    """Ueberlauf: NICHT hart mitten im Wort schneiden (das ergaebe eine halbe
    Datenzeile, die wie ein vollstaendiger Wert aussieht). Stattdessen ganze
    ORTSBLOECKE behalten und den Verlust ausweisen — gleiche Einpass-Schleife
    mit mitgerechnetem Hinweis wie im SMS-Pfad (alert/render.py:521-529)."""
    kept: list[list[str]] = []
    for block in blocks:
        notice = hinweis(len(blocks) - len(kept) - 1)
        if len(_join_telegram(header, kept + [block]) + notice) <= max_chars:
            kept.append(block)
        else:
            break

    omitted = len(blocks) - len(kept)
    if not kept:
        # Degeneration: schon der erste Ortsblock sprengt 4096 Zeichen. Dann an
        # der Wortgrenze kuerzen (letztes Sicherheitsnetz, geteilter Helfer
        # `_word_boundary_truncate`) statt mitten im Wort.
        notice = hinweis(omitted - 1)
        body = _join_telegram(header, [blocks[0]])
        return _word_boundary_truncate(body, max(max_chars - len(notice), 0)) + notice

    body = _join_telegram(header, kept) + hinweis(omitted)
    return body if len(body) <= max_chars else _word_boundary_truncate(body, max_chars)


def _join_telegram(header: list[str], blocks: list[list[str]]) -> str:
    return "\n".join(header + [line for block in blocks for line in block])


def _telegram_notice(omitted: int, lang: Lang = "de") -> str:
    """Ehrlicher Kuerzungs-Hinweis (#1269): benennt die Zahl der nicht
    dargestellten Orte. Leer, wenn nichts entfaellt. Rang-/score-frei (AC-3)."""
    if omitted <= 0:
        return ""
    return "\n" + t("vergleich.telegram.uebersprungen", lang, n=omitted)


def _telegram_no_data_notice(no_data_count: int, lang: Lang = "de") -> str:
    """Ehrlicher Hinweis fuer OHNE-DATEN (#1362, Adversary-Fund/Gegenpruefung):
    eine ausgewaehlte Groesse hat an DIESEM Ort keinen Wert (z.B. Ausfall der
    Fallback-Kette) -- anders als der Platzmangel-Fall
    (``_telegram_metric_notice``) ist das KEIN Verdraengungs-Effekt der
    7-Zellen-Grenze. Beide Faelle bleiben getrennt zaehlbar (Invariante:
    sichtbare Zellen + Platzmangel-Zaehler + Ohne-Daten-Zaehler == Anzahl
    gewaehlter Groessen). Bewusst OHNE "vollstaendig per E-Mail": die Mail
    zeigt fuer diese Groesse ebenfalls keinen Wert (nur einen "-"-Platzhalter,
    s. ``render_comparison_text``), das waere also ein falsches Versprechen.
    Leer, wenn nichts fehlt. Issue #1405 S3: Wortlaut aus dem EINEN Baustein
    ``selection_gap_notice`` (geteilt mit E-Mail HTML/Klartext)."""
    return selection_gap_notice(no_data_count, scope="ort", lang=lang)


def _official_alert_sms_marker(
    entries: tuple[tuple[str, str, "int | None"], ...],
) -> str:
    """`!`-Kuerzel-Marker aus den geteilten `(Kuerzel, Stufe, Stunde)`-Tripeln
    (`official_alerts_to_sms_entries`) -- ausschliesslich fuer Compare-SMS
    (Issue #1332 AC-1/AC-4; PO-Korrektur 2026-07-23: Compare-Telegram
    verwendet dieses Kuerzel NICHT mehr, s. `render_compare_telegram`). Kein
    zweiter Kuerzel-Katalog: das Tripel kommt bereits gefiltert (>= orange)
    und sortiert aus dem geteilten Kern, hier nur noch String-Bau.
    Leeres Tripel -> leerer Marker (kein Ort ohne anzuzeigende Warnung zeigt
    einen `!`)."""
    if not entries:
        return ""
    # Issue #1441: dieselbe Token-Grammatik wie die Trip-SMS (geteilter Helfer).
    from output.tokens.hazard_symbols import alert_entry_token_parts

    parts = ["".join(alert_entry_token_parts(symbol, level, hour)) for symbol, level, hour in entries]
    return "!" + " ".join(parts)


def _sms_location_variants(
    loc_result, enabled_metrics: list[str] | None,
    unresolved_count: int = 0, metric_formats: dict[str, bool] | None = None,
) -> list[str]:
    """Flache SMS-Darstellung EINES Ortes -- alle Formen, absteigend nach
    Zellenzahl (Index d = d Zellen vom Listenende verdraengt).

    #3047 Runde 7 p8: die Zellen werden EINMAL je Ort gebaut; die Auswahl im
    Budget trifft ``_sms_pick_form`` (vorher ``budget``-Parameter, s. u.).

    Orte ohne abrufbare Daten (``error``) werden als ``"<Name> n/a"``
    dargestellt statt weggefiltert: ein weggefilterter Ort waere weder sichtbar
    noch im ``+k`` gezaehlt — die SMS behauptete dann einen vollstaendigen
    Vergleich ueber weniger Orte, als er hat (#1269). ``render_compare_telegram``
    haelt Fehler-Orte aus demselben Grund als "Fehler: …"-Block sichtbar; die
    SMS-Form ist nur knapper (``CHANNEL_LIMITS["sms"]["max_chars"]``). Die
    Fehlerursache selbst traegt die SMS bewusst nicht — sie steht in der
    E-Mail/Telegram-Fassung.

    ASCII "n/a" statt eines Gedankenstrichs, weil ein Ort ohne Werte sonst wie
    ein Ort mit leerem Wert aussieht.

    Issue #1362 Scheibe S5b: die frueher feste Zwei-Zellen-Grenze
    (``_SMS_METRICS_PER_LOCATION``) entfaellt. Statt einer festen Anzahl
    entscheidet ``budget`` (Zeichen, die dieser Ortsteil hoechstens belegen
    darf -- ``None`` = unbegrenzt), WIE VIELE der ausgewaehlten Groessen
    tatsaechlich erscheinen: Zellen werden in Nutzer-Reihenfolge aufgebaut und
    bei Platzmangel GANZ von HINTEN entfernt (Kuerzungsprinzip aus
    ``tokens/render.py:_truncate``, nie mitten in Kuerzel/Wert), bis der
    Ortsteil ins Budget passt. Verdraengte Zellen werden als ``+N`` ausgewiesen
    (Spec Implementation Details Punkt 3) -- nie stillschweigend weggelassen.
    Groessen OHNE Wert an diesem Ort zaehlen dabei NICHT als verdraengt: sie
    waren nie Kandidat fuer einen Platz. Issue #1405 S3: sie (plus die
    unmappbaren Eintraege, ``unresolved_count``) erscheinen als eigener
    Zaehler ``?N`` nach ``+N`` und vor dem ``!``-Marker (sms_format.md §5b),
    fester Bestandteil jeder Budget-Pruefung; ohne Luecke kein Zeichen mehr.

    Issue #1332: traegt ein Ort eine amtliche Warnung >= orange, haengt ein
    `!`-Kuerzel-Marker an (geteilter Kern ``official_alerts_to_sms_entries``,
    kein zweiter Katalog). Der Marker wird NIE verdraengt -- er ist Teil der
    festen Bestandteile jeder Budget-Pruefung, die Metrik-Zellen weichen ihm
    (Sicherheit vor Optik, Design-Leitprinzip).

    Issue #1378 (AC-10): die Zeitzone kommt aus dem EINEN Aufloeser
    (``resolve_location_tz``) -- ``SavedLocation.timezone`` mit Vorrang, sonst
    aus den Koordinaten. ``@Stunde`` entfaellt weiterhin ersatzlos, wenn sich
    ueberhaupt keine Zeitzone bestimmen laesst (bewusste SMS-Budget-Konvention,
    ``CHANNEL_LIMITS["sms"]["max_chars"]`` -- kein Platzhalter, s. Spec Known
    Limitations).
    """
    name = loc_result.location.name
    if loc_result.error is not None:
        return [f"{name} n/a"]
    marker = _location_sms_alert_marker(loc_result)

    dedup_ids = list(dict.fromkeys(
        enabled_metrics if enabled_metrics is not None else _NIE_EINGESTELLT_IDS
    ))
    summary = _daily_summary(loc_result) if loc_result.hourly_data else None
    cells = [
        c for c in (
            _sms_metric_cell(
                loc_result, mid, bool((metric_formats or {}).get(mid)), summary=summary,
            )
            for mid in dedup_ids
        )
        if c is not None
    ]
    # Issue #1405 S3 (sms_format.md §5b): fehlende Werte + unmappbare
    # Eintraege als `?N` -- fester Bestandteil wie der Warn-Marker.
    # Issue #3047 B-L4: "nie eingestellt" (None) zaehlt fehlende Werte nicht
    # (nichts gewaehlt; die Mail zeigt dafuer ebenfalls keinen Hinweis).
    fehlend = len(dedup_ids) - len(cells) if enabled_metrics is not None else 0
    missing = fehlend + unresolved_count

    def _assemble(kept_cells: list[str], demoted: int) -> str:
        text_parts = [name] + kept_cells
        if demoted > 0:
            text_parts.append(f"+{demoted}")
        if missing > 0:
            text_parts.append(f"?{missing}")
        if marker:
            text_parts.append(marker)
        return " ".join(text_parts)

    # Formen von "alle Zellen" bis "keine Zelle" (Kuerzung vom Listenende).
    return [_assemble(cells[:len(cells) - d], d) for d in range(len(cells) + 1)]


def _sms_location_part(
    loc_result, enabled_metrics: list[str] | None, budget: "int | None",
    unresolved_count: int = 0, metric_formats: dict[str, bool] | None = None,
) -> str:
    """Ortsteil im Budget (s. ``_sms_location_variants``): die zellenreichste
    Form, die ``budget`` einhaelt, sonst die Form ohne Zelle."""
    forms = _sms_location_variants(loc_result, enabled_metrics, unresolved_count, metric_formats)
    return _sms_pick_form(forms, budget, 0)


def _sms_pick_form(forms: list[str], budget: "int | None", floor: int) -> str:
    """Zellenreichste Form mit ``len <= budget``; mindestens ``floor`` Zellen
    bleiben stehen (Form mit Index ``len(forms)-1-floor`` ist die kuerzeste)."""
    last = max(len(forms) - 1 - floor, 0)
    for form in forms[:last]:
        if budget is None or len(form) <= budget:
            return form
    return forms[last]


def _location_sms_alert_marker(loc_result) -> str:
    """`!`-Marker der amtlichen Warnungen EINES Ortes ("" ohne Warnung/Fehlerort)."""
    if loc_result.error is not None:
        return ""
    tz = resolve_location_tz(loc_result.location)
    # Issue #1461 S3b-2b (AC-17): derselbe Wechsel wie im Compare-Telegram
    # (oben) -- der Vorgabewert von `official_alerts_to_sms_entries()` faellt
    # sonst auf `MIN_SMS_LEVEL` (orange) zurueck. `min_level` explizit auf die
    # Startschwelle "gering" gesetzt, keine zweite Zahlenreihe.
    entries = official_alerts_to_sms_entries(
        loc_result.official_alerts, tz,
        min_level=alert_urgency.min_official_level_for_threshold("LOW"),
    )
    return _official_alert_sms_marker(entries)


def _sms_fit_locations(
    head: str, forms: list[list[str]], gewarnt: set[int], max_chars: int,
) -> str | None:
    """Issue #3047 AC-23 (B-K3, Konzept WV6; Tech-Lead-Entscheidung p8,
    ADR-0095: ein Vergleich braucht mehrere Orte). Einpassung von hinten:

    1. zuerst die Wetterzellen ALLER gezeigten Orte vom Listenende (gleiches
       Zeichen-Budget je Ort), bis je Ort nur noch die erste Listenzeile bleibt;
    2. erst dann entfallen ganze Orte vom Ende als `` +k Orte`` -- Orte OHNE
       amtliche Warnung zuerst (Warnungen fallen zuletzt weg);
    3. sind nur Orte mit Warnung (oder ein einziger Ort) uebrig, weichen auch
       ihre ersten Zellen dem ``!``-Marker.

    ``forms[i]`` = Formen des Ortes i (``_sms_location_variants``). ``None`` =
    nicht einmal ein Ort ohne Zelle passt (Degenerationsfall beim Aufrufer)."""
    n = len(forms)
    shown = list(range(n))
    while shown:
        notice = _sms_location_overflow_notice(n - len(shown))
        floor = 0 if len(shown) == 1 or all(i in gewarnt for i in shown) else 1

        def _body(budget: "int | None") -> str:
            parts = (_sms_pick_form(forms[i], budget, floor) for i in shown)
            return f"{head} " + "; ".join(parts) + notice

        if len(_body(-1)) <= max_chars:
            # Die Laenge waechst monoton mit dem Budget: groesstes passendes suchen.
            budgets = sorted({len(f) for i in shown for f in forms[i]})
            lo, hi = 0, len(budgets) - 1
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if len(_body(budgets[mid])) <= max_chars:
                    lo = mid
                else:
                    hi = mid - 1
            return _body(budgets[lo]) if len(_body(budgets[lo])) <= max_chars else _body(-1)
        ohne = [i for i in shown if i not in gewarnt]
        shown.remove(ohne[-1] if ohne else shown[-1])
    return None


def render_compare_sms(
    result: ComparisonResult,
    *,
    enabled_metrics: list[str] | None = None,
    unresolved_count: int = 0,
    metric_formats: dict[str, bool] | None = None,
) -> str:
    """Orts-Vergleich als flache SMS (Issue #1270), Kern: ``_render_compare_sms_body``.

    Issue #3047 B-L2 (sms_format.md §3.4d): ist an einem Ort ein amtlicher
    Warndienst ausgefallen, endet die SMS mit dem Marker ``X?``. Er ist fester
    Bestandteil wie im Trip (faellt nie weg): das Budget des Kerns wird um ihn
    verkleinert, die Metrik-/Orts-Kuerzung weicht ihm."""
    max_chars = CHANNEL_LIMITS["sms"]["max_chars"]
    marker = (
        f" {_UNAVAILABLE_SYMBOL}"
        if any_official_alerts_unavailable(result.locations) else ""
    )
    if max_chars is not None:
        max_chars -= len(marker)
    return _render_compare_sms_body(
        result, enabled_metrics=enabled_metrics, unresolved_count=unresolved_count,
        metric_formats=metric_formats, max_chars=max_chars,
    ) + marker


def _render_compare_sms_body(
    result: ComparisonResult,
    *,
    enabled_metrics: list[str] | None,
    unresolved_count: int,
    metric_formats: dict[str, bool] | None,
    max_chars: int | None,
) -> str:
    """Rendert einen Orts-Vergleich als flache SMS (Issue #1270).

    ``metric_formats`` (Issue #3039): ``{renderer_id: einfach}`` aus
    ``channel_layouts``; Einfach wirkt nur fuer die GSM-7-sicheren Formen
    (``SMS_FORMAT_MODE_METRIC_IDS``). ``None`` = heutiger Festzustand.

    Issue #1405 S3: ``unresolved_count`` (unmappbare gewaehlte Eintraege)
    erhoeht den Zaehler ``?N`` jedes Ortsteils (sms_format.md §5b).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["sms"]``: ``max_table_cols`` = 0 (keine Tabelle, flache
    Zeile), ``max_chars`` (verkettungssicherer GSM-7-Wert -- Herleitung s.
    Konstante in ``channel_layout.py``, Adversary-Fund #1362 S5b Runde 5).

    Ueberlauf folgt der Hauskonvention aus ``alert/render.py:507-535``
    (ADR-0011:42, "SMS-Laengen-Budget mit `+k`-Ueberlauf"): Kopf immer; erst
    werden die Zellen aller Orte vom Listenende gekuerzt, erst danach entfallen
    Orte und werden als ` +k Orte` AUSGEWIESEN (``_sms_fit_locations``, #3047 p8). Ein stiller Abbruch
    waere eine luegende Ausgabe (vgl. #1269) — die SMS behauptete sonst einen
    vollstaendigen Vergleich, den sie nicht zeigt. Endgarantie:
    ``len <= max_chars`` (Aufrufer: ``CHANNEL_LIMITS["sms"]`` abzueglich Marker).
    """
    locations = location_render_order(result.locations)
    if not locations:
        return "Vergleich: keine Daten"  # i18n-fest: SMS-Kanal sprachfest (ADR-0104)

    # Issue #1268: Stundenfenster-Angabe ersatzlos entfernt (Bewertung = ganzer
    # Tag). Sie waere dauerhaft "00-23h" — eine Nicht-Information, die 8 von
    # `max_chars` Zeichen belegt, die hier fuer echte Messwerte gebraucht werden.
    head = f"Vergleich {result.target_date.strftime('%d.%m.')}:"
    forms = [
        _sms_location_variants(loc, enabled_metrics, unresolved_count, metric_formats)
        for loc in locations
    ]
    if max_chars is None:
        return f"{head} " + "; ".join(f[0] for f in forms)

    gewarnt = {i for i, loc in enumerate(locations) if _location_sms_alert_marker(loc)}
    body = _sms_fit_locations(head, forms, gewarnt, max_chars)
    if body is not None:
        return body
    # Degenerationsfall: schon der erste Ort ohne Zelle sprengt das Budget.
    # "Ueberschrift + nichts" ist verboten — dann lieber EIN gekuerzter Ort.
    # Gekuerzt wird der Ortsblock ALLEIN (nicht Kopf+Block), weil eine
    # Wortgrenzen-Kuerzung ueber den Kopf hinweg bei einem einzigen ueberlangen
    # Ortsnamen genau auf der Kopf-Grenze schnitte und wieder "Ueberschrift +
    # nichts" ergaebe. `_word_boundary_truncate` faellt bei einem Wort > Budget
    # auf den harten Schnitt zurueck: ein unkenntlicher Ort ist ehrlicher als
    # ein verschwiegener.
    first = forms[0][-1]
    marker = _sms_location_overflow_notice(len(forms) - 1)
    budget = max_chars - len(head) - 1 - len(marker)
    fitted = _word_boundary_truncate(first, max(budget, 0))
    if fitted != first and not fitted.endswith("..."):
        # Der Helfer schneidet nur an Wortgrenzen mit "..."; findet er keine
        # (Ortsname laenger als das Budget), schneidet er hart und stumm. Ein
        # abgeschnittener Name darf aber nicht wie ein vollstaendiger aussehen.
        fitted = fitted[: max(len(fitted) - 3, 0)] + "..."
    body = f"{head} " + fitted + marker
    # Garantie len<=limit auch im Degenerationsfall (Kopf allein zu lang).
    return body[:max_chars]


def _sms_location_overflow_notice(omitted: int) -> str:
    """Orts-Ueberlauf-Hinweis (#1269) am NACHRICHTENENDE: zaehlt weggelassene
    ORTE. Adversary-Fund (#1362 Scheibe S5b): trifft er auf den neuen
    Metrik-Ueberlauf im Ortsblock (``+N`` OHNE Wortzusatz -- dort aus dem
    Zusammenhang lesbar, s. ``_sms_location_part``), ergibt ``... +3 +4`` zwei
    Zahlen ohne erkennbaren Bezug. Dieser Hinweis traegt deshalb den Zusatz
    "Orte" (kurz gehalten, PO-Vorgabe: Platz kostet -- Orts-Ueberlauf tritt nur
    bei vielen Orten auf, dort sind die 5 Extra-Zeichen vertretbar). Leer, wenn
    nichts entfaellt."""
    if omitted <= 0:
        return ""
    return f" +{omitted} Orte"
