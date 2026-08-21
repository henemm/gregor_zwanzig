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

from collections import Counter
from typing import Optional

from app.metric_catalog import get_sms_code
from app.models import Corridor, MetricConfig, UnifiedWeatherDisplayConfig
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.channel_layout import (
    CHANNEL_LIMITS, render_for_channel, telegram_metric_notice,
)
from output.renderers.compare_metric_catalog import COMPARE_METRIC_CATALOG
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.compare_html import (
    CV2_METRICS, OUTLOOK_HEADING, _build_location_outlook_rows,
    _column_legend_text, _fmt_precip_type, _fmt_thunder,
    _fmt_visibility_overview, _metric_value, _should_merge_wind_dir,
    _units_legend_text, _visible_hour_metrics, derive_row_labels,
    loc_hail_flag, loc_thunder_signals, location_render_order,
)
from output.renderers.email.outlook_state_hint import (
    OutlookState, render_outlook_state_plain,
)
from output.renderers.email.undelivered_hint import (
    has_undelivered, render_undelivered_plain,
)
from utils.geo import degrees_to_compass
from utils.timezone import (
    local_fmt, local_stamp, location_tz, resolve_location_tz, tz_abbrev,
)
from output.renderers.email.outlook import render_outlook_plain
from output.metric_format import format_value
from output.renderers.alert.official_alerts import (
    _word_boundary_truncate,
    build_official_alert_notices,
    official_alert_source_label,
    official_alerts_to_sms_entries,
    render_official_alert_telegram,
    render_official_alerts_plain,
)
import services.alert_urgency as alert_urgency

# Issue #1285: die fuenf bisher stillschweigend verworfenen Uebersichts-Zeilen
# (Renderer-Metrik-ID, Label, Formatierung). Wert-Quelle und Formatierung sind
# BEWUSST die des HTML-Pfads (`compare_html._metric_value` / `_fmt_*`) statt
# einer Klartext-Kopie -- sonst beschreibt dieselbe Wetterlage in HTML und
# Klartext derselben Mail verschiedene Zahlen.
# Issue #1401 Scheibe A2b: das zweite Tupel-Element ist NICHT mehr die
# Mail-Beschriftung -- die leitet der Mail-Klartext jetzt aus dem zentralen
# Register ab (`compare_html.derive_row_labels`, dieselbe Quelle wie der
# HTML-Teil). Es bleibt ausschliesslich das DEUTSCHE Kanal-Label des
# Telegram-Pfads (`_plain_metric_cell`), der bewusst deutsch bleibt (Spec
# "Known Limitations": drei Namens-Vokabulare parallel, Bestandsschutz).
_DAILY_PLAIN_ROWS: tuple[tuple[str, str, object], ...] = (
    ("precip_sum", "Regen", lambda v: f"{v:.1f} mm"),
    ("pop_max", "Regenwahrscheinlichkeit", lambda v: f"{v:.0f}%"),
    ("thunder_max", "Gewitter", _fmt_thunder),
    ("uv_max", "UV max", lambda v: f"{v:.0f}"),
    ("visibility_min", "Sicht min", _fmt_visibility_overview),
    # Issue #1296, Klasse B (kein LocationResult-Feld, Live-Ableitung ueber
    # _metric_value -> _daily_summary, analog den fuenf #1285-Zeilen).
    # Issue #1585: die cape_max-Zeile ist hier ersatzlos entfallen -- sie muss
    # mit CV2_METRICS (compare_html.py) synchron bleiben, `derive_row_labels`
    # schlaegt sie ueber `_CV2_BY_KEY` nach und wirft sonst KeyError.
    ("freezing_level", "Nullgradgrenze", lambda v: f"{v:.0f} m"),
    # Issue #1324, Klasse B (kein LocationResult-Feld, Live-Ableitung ueber
    # _metric_value -> _daily_summary). HTML-Parität: dieselben Werte.
    ("humidity_avg", "Luftfeuchtigkeit Ø", lambda v: f"{v:.0f}%"),
    ("dewpoint_avg", "Taupunkt Ø", lambda v: format_value("temperature", v, style="plain")),
    ("pressure_avg", "Luftdruck Ø", lambda v: f"{v:.0f} hPa"),
    ("precip_type", "Niederschlagsart", _fmt_precip_type),
    ("snowfall_limit", "Schneefallgrenze", lambda v: f"{v:.0f} m"),
)

# Issue #1359 Scheibe 1: ALLE Uebersichts-Zeilen des Klartext-Teils als EINE
# geordnete Tabelle (Renderer-Metrik-ID, Label, Formatierung). Vorher standen
# sie als feste Folge einzelner `if _metric_visible(...)`-Bloecke im Quelltext
# -- die im Editor eingestellte Metrik-Reihenfolge konnte deshalb gar nicht
# ankommen (der Test prueft nur Mitgliedschaft, nicht Position).
# Die Reihenfolge DIESER Konstante bleibt die Standard-Reihenfolge fuer
# Altbestaende ohne gespeicherte Auswahl (AC-7, eingefroren in
# tests/unit/test_compare_metric_order.py).
# Werte kommen einheitlich ueber `_metric_value` (HTML-Paritaet, keine zweite
# Wert-Quelle): fuer IDs ohne `_DAILY_AGGREGATE_FIELD`-Eintrag ist das exakt
# das bisherige `getattr(loc_result, metric_id)`.
_PLAIN_ROWS: tuple[tuple[str, str, object], ...] = (
    ("temp_max", "Temp max", lambda v: format_value("temperature", v, style="plain")),
    ("wind_max", "Wind", lambda v: format_value("wind", v, style="plain")),
    ("temp_min", "Temp min", lambda v: format_value("temperature", v, style="plain")),
    ("gust_max", "Böen", lambda v: format_value("wind", v, style="plain")),
    ("wind_direction_avg", "Windrichtung", lambda v: f"{v}°"),
    ("wind_chill_min", "Gefühlte Temp. min",
     lambda v: format_value("temperature", v, style="plain")),
    ("wind_chill_max", "Gefühlte Temp. max",
     lambda v: format_value("temperature", v, style="plain")),
    ("cloud_low_avg", "Wolken tief", lambda v: f"{v}%"),
    ("cloud_mid_avg", "Wolken mittel", lambda v: f"{v}%"),
    ("cloud_high_avg", "Wolken hoch", lambda v: f"{v}%"),
    *_DAILY_PLAIN_ROWS,
    ("sunny_hours", "Sonne", lambda v: f"{format_value('sunshine', v, style='bare')}h"),
    ("cloud_avg", "Wolken", lambda v: format_value("cloud_total", v, style="plain")),
    ("snow_depth_cm", "Schneehöhe", lambda v: format_value("snow_depth", v, style="plain")),
    ("snow_new_cm", "Neuschnee", lambda v: f"{v:.0f} cm"),
)

# Beschriftungs-Quelle des Klartext-Zwillings: dieselben Register-Verknuepfungen
# wie im HTML-Pfad, nach Zeilen-Key ansprechbar (Issue #1401 A2b).
_CV2_BY_KEY: dict[str, dict] = {m["key"]: m for m in CV2_METRICS}


def _ordered_rows(rows, enabled_metrics: list[str] | None) -> list | tuple:
    """Zeilen-/Zell-Definitionen in der vom Nutzer eingestellten Reihenfolge.

    Issue #1359: ``enabled_metrics`` ist eine GEORDNETE Liste (Listenposition
    = Reihenfolge, kein eigenes ``order``-Feld). ``None`` = Altbestand ohne
    gespeicherte Auswahl und behaelt die unveraenderte Quellcode-Reihenfolge
    (AC-7). Eine leere Liste bleibt leer (AC-8) -- sie darf nicht in "alle
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
    hourly_metrics: list[str] | None = None,
    hourly_enabled: bool = True,
    undelivered: list | None = None,
) -> str:
    """
    Render ComparisonResult als Klartext (v2, Issue #1110).

    Kein Score/🏆 mehr. Je Ort: Uebersichtswerte + amtliche Warnungen (via
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
            HTML-Pfad (``_visible_hour_metrics``) -- ``None`` = alle 9
            Spalten, sonst nur die gewaehlten, in der gewaehlten Reihenfolge.
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

    Returns:
        Klartext-String fuer die E-Mail.
    """
    _ = profile  # akzeptiert fuer API-Konsistenz, aktuell ohne Wirkung

    target_date = result.target_date
    created_at = result.created_at
    # Zentraler Sortier-Helfer (PO-Update 2026-07-08): alphabetisch, case-
    # insensitiv, identisch zu render_compare_html() -- keine Doppel-Logik.
    locations = location_render_order(result.locations)
    if not locations:
        return "Keine Vergleichsdaten verfügbar."

    lines: list[str] = []
    lines.append("ORTS-VERGLEICH")
    lines.append("=" * 24)
    lines.append(f"Datum: {target_date.strftime('%A, %d.%m.%Y')}")
    # Issue #1268: Zeitfenster-Zeile ersatzlos entfernt (Bewertung = ganzer Tag).
    # Issue #1378 (AC-4/AC-8): Ortszeit des ERSTGENANNTEN Ortes plus
    # erkennbares Zeitzonen-Kuerzel -- identische Zeitbasis und identischer
    # Wert wie die HTML-Kopfzeile derselben Mail.
    lines.append(
        f"Erstellt: {local_stamp(created_at, location_tz(locations[0].location), '%d.%m.%Y %H:%M')}"
    )
    lines.append("")
    lines.append("-" * 50)

    for loc_result in locations:
        loc = loc_result.location
        lines.append(loc.name)
        if loc_result.error is not None:
            lines.append(f"   Fehler: {loc_result.error}")
            lines.append("")
            continue

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
            [_CV2_BY_KEY[key] for key, _de, _fmt in ordered], form="long"
        )
        for (metric_id, _de_label, fmt), row in zip(ordered, labelled):
            value = _metric_value(loc_result, metric_id)
            cell = (
                # Issue #1680 S1: der Klartext-Teil der Mail zeigt die
                # Herkunft der Gewitterstufe genau wie der HTML-Teil.
                _fmt_overview_cell(fmt, value, loc_result, include_origin=True)
                if value is not None else "-"
            )
            lines.append(f"   {row['label']}: {cell}")

        # Amtliche Warnungen, eine Zeile pro Warnung (Epic #1073 Punkt 6,
        # gemeinsamer Renderer statt Copy-Paste).
        for line in render_official_alerts_plain([(loc.name, loc_result.official_alerts)]):
            lines.append(f"   ⚠️ {line}")

        lines.append("")

    # Stundentabelle + 3-Tage-Ausblick (Epic #1301 B4) je Ort, direkt
    # untereinander (Issue #1323: der Ausblick folgt unmittelbar auf den
    # Stundenblock desselben Orts, statt gesammelt in einer eigenen
    # "AUSBLICK"-Sektion am Textende). Fail-soft je Ort -- fehlt Stunden-
    # oder Ausblickdaten, entfaellt nur der jeweils fehlende Teil.
    # Issue #1366 F003 (Staging-Fund, AC-4): dieselbe Spaltenauflösung wie im
    # HTML-Pfad -- ``hourly_metrics=None`` (Altbestand) liefert alle 9
    # Spalten in Katalog-Reihenfolge, eine gesetzte Auswahl nur die
    # gewaehlten, in der gewaehlten Reihenfolge (Issue #1335/#1359).
    visible_hour_metrics = _visible_hour_metrics(hourly_metrics)
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
            _build_location_outlook_rows(loc_result, outlook_metrics)
            if outlook_enabled and loc_result.outlook_hourly_data else []
        )
        # Fix #1505 (AC-4): bei eingeschaltetem Ausblick ohne Zeilen (weder
        # Rohdaten noch etwas nach der Metrik-Filterung) stand hier bisher
        # NICHTS -- der Ort fiel unten sogar ganz aus dem Abschnitt. Jetzt
        # tritt derselbe benannte Zustand an die Stelle wie im HTML-Teil
        # (geteilter Baustein aus #1486, keine zweite Formulierung).
        outlook_state_text = (
            render_outlook_state_plain(OutlookState.UNAVAILABLE)
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
                    # Issue #1475 Nachbesserung (AC-8, Klartext-Pendant der
                    # Compare-Stundentabelle): Hagel als Text-Anhang, wie in
                    # der HTML-Fassung -- nie als Ring (das ist nur Trip).
                    if m["fmt"] is _fmt_thunder:
                        # Issue #1680 S3 (Spec D4): die Herkunft der Stufe
                        # DIESER Stunde, wie in der HTML-Fassung -- HTML und
                        # Klartext derselben Mail haben zwei unabhaengige
                        # Aufrufstellen und duerfen nicht auseinanderlaufen
                        # (AC-4). Stufe und Traeger stammen aus DEMSELBEN `dp`.
                        # KANAL: die Compare-SMS erreicht diese Schleife nie --
                        # sie baut ihre Zelle ueber `_sms_metric_cell()` ->
                        # `_fmt_overview_cell(..., include_origin=False)`
                        # (PO-Entscheidung, dort aktiv abgewaehlt).
                        text = m["fmt"](
                            getattr(dp, m["key"], None),
                            getattr(dp, "hail_flag", None),
                            getattr(dp, "thunder_level_signals", None),
                        )
                    else:
                        text = m["fmt"](getattr(dp, m["key"], None))
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
                heading=OUTLOOK_HEADING, show_name=False,
            ).strip("\n"))
        elif outlook_state_text:
            # Fix #1505 (AC-4): benannter Zustand an derselben Stelle wie
            # sonst die Ausblick-Tabelle, unter derselben Ueberschrift.
            section_lines.append(OUTLOOK_HEADING)
            section_lines.append(f"   {outlook_state_text}")
        section_lines.append("")

    if section_lines:
        if hour_rows_written:
            lines.append("STUNDENVERLAUF")
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
    if hourly_enabled:
        for _legend in (
            _units_legend_text(visible_hour_metrics),
            _column_legend_text(visible_hour_metrics),
        ):
            if _legend:
                lines.append(_legend)

    # Issue #1461 S3b-1 (AC-17): an derselben Stelle wie im HTML-Teil (vor
    # Legende/Fuss) und ueber DENSELBEN Baustein wie Trip und Compare-HTML --
    # keine zweite Fassung. Zeitbasis wie die Kopfzeile derselben Mail.
    if has_undelivered(undelivered):
        lines.append("")
        lines.append(render_undelivered_plain(
            undelivered, tz=location_tz(locations[0].location),
        ))
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
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
    corridors: list[Corridor] | None = None,
    outlook_enabled: bool = False,
    outlook_metrics: list[dict] | None = None,
    undelivered: list | None = None,
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
        preset_schedule=preset_schedule,
        preset_weekday=preset_weekday,
        corridors=corridors,
        outlook_enabled=outlook_enabled,
        outlook_metrics=outlook_metrics,
        # Issue #1461 S3b-1: geteilter Hinweis-Baustein, derselbe wie im Trip.
        undelivered=undelivered,
    )
    text_body = render_comparison_text(
        result, profile=profile, enabled_metrics=enabled_metrics,
        outlook_enabled=outlook_enabled,
        # Issue #1361/#1368: dieselbe Ausblick-Auswahl wie der HTML-Pfad --
        # der Pflicht-Validator liest nur HTML, der Klartext braucht sie
        # deshalb eigenstaendig (#1366-Erfahrung).
        outlook_metrics=outlook_metrics,
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
    )
    return html_body, text_body


# ---------------------------------------------------------------------------
# Kanal-Renderer Telegram / SMS (Issue #1270, Scheibe S3)
#
# SPEC: docs/specs/modules/compare_channel_preview_dispatch.md (AC-3)
# Neutralitaets-Vertrag identisch zu render_comparison_text (#1110): KEIN
# Score, KEIN Rang, keine Gewinner-Hervorhebung -- Score bleibt ausschliesslich
# interne Sortiergroesse der ComparisonEngine. Orte erscheinen alphabetisch
# (gemeinsamer Sortier-Helfer), damit die interne Score-Reihenfolge sich nicht
# als sichtbares Ranking niederschlaegt.
# Metrik-Vokabular = die Uebersichts-Metrik-IDs von render_comparison_text
# (Quelle: resolve_compare_render_options -> resolve_enabled_metrics). Keine
# eigene Metrik-Liste, insbesondere kein confidence_pct (#710/ADR-0005).
# ---------------------------------------------------------------------------

# (metric_id, Kurz-Label) in Anzeige-Prioritaet -- deckungsgleich mit den
# Uebersichts-Zeilen in render_comparison_text().
_CHANNEL_METRICS: tuple[tuple[str, str], ...] = (
    ("temp_max", "Temp"),
    ("wind_max", "Wind"),
    ("sunny_hours", "Sonne"),
    ("cloud_avg", "Wolken"),
    ("snow_depth_cm", "Schnee"),
    ("snow_new_cm", "Neuschnee"),
)

# Issue #1362 (Scheibe S5a): Label+Formatierung fuer ALLE 26 Compare-Groessen
# ueber dieselbe Tabelle wie der Klartext-Teil (_PLAIN_ROWS) -- ersetzt die
# alte 6-Groessen-if-Kette (_format_channel_metric) fuer den Telegram-Pfad.
_PLAIN_ROWS_BY_ID = {row[0]: row for row in _PLAIN_ROWS}


def _fmt_overview_cell(
    fmt, value, loc_result: LocationResult, *, include_origin: bool = False,
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
    """
    if fmt is _fmt_thunder:
        signale = loc_thunder_signals(loc_result) if include_origin else None
        return fmt(value, loc_hail_flag(loc_result), signale)
    return fmt(value)

# Issue #1362 (Scheibe S5b): Compare-Renderer-ID -> zentrale Katalog-Metrik-ID
# (wie von ``metric_catalog.get_sms_code()`` erwartet), abgeleitet aus den
# ZWEI bestehenden Uebersetzungstabellen -- kein drittes, hier neu getipptes
# Vokabular (s. Spec "Vier inkompatible Metrik-Vokabulare").
_METRIC_ID_BY_FRONTEND_KEY = {
    entry["key"]: entry["metric_id"] for entry in COMPARE_METRIC_CATALOG
}
_RENDERER_TO_CATALOG_METRIC_ID: dict[str, str] = {
    renderer_id: _METRIC_ID_BY_FRONTEND_KEY[frontend_key]
    for frontend_key, renderer_id in FRONTEND_TO_RENDERER_METRIC_ID.items()
}

# Issue #1362 S5b, Adversary-Fund Runde 3 (PO-Entscheidung 2026-07-29): der
# Katalog fuehrt EINE Groesse mit EINEM Kuerzel, der Ortsvergleich zeigt
# manche Groessen aber in MEHREREN Auswertungen (Hoechst-/Tiefstwert) --
# "D 33°C D 17°C" waere ohne Zusatz nicht unterscheidbar. Ermittelt aus dem
# Katalog SELBST (``COMPARE_METRIC_CATALOG``), nicht aus einer Aufzaehlung:
# jede ``metric_id``, die dort mit mehr als einem Eintrag (verschiedene
# ``aggregation``) vorkommt.
_AGGREGATION_BY_FRONTEND_KEY = {
    entry["key"]: entry["aggregation"] for entry in COMPARE_METRIC_CATALOG
}
_RENDERER_TO_AGGREGATION: dict[str, str] = {
    renderer_id: _AGGREGATION_BY_FRONTEND_KEY[frontend_key]
    for frontend_key, renderer_id in FRONTEND_TO_RENDERER_METRIC_ID.items()
}
_metric_id_occurrences = Counter(
    entry["metric_id"] for entry in COMPARE_METRIC_CATALOG
)
_AMBIGUOUS_CATALOG_METRIC_IDS = frozenset(
    mid for mid, count in _metric_id_occurrences.items() if count > 1
)


def _sms_aggregation_sign(metric_id: str) -> str:
    """PO-Vorgabe 2026-07-29 (Adversary-Fund Runde 3): ``+`` fuer den
    Hoechstwert, ``-`` fuer den Tiefstwert -- IMMER, wenn die zugrundeliegende
    Katalog-Groesse im Ortsvergleich MEHR ALS EINE Auswertung anbietet, nicht
    nur wenn der Nutzer gerade beide gewaehlt hat (ein Kuerzel darf nicht je
    nach Auswahl etwas anderes bedeuten -- dieselbe Regel wie die
    ``fresh_snow``-Kuerzel-Korrektur). Groessen mit genau einer Auswertung
    bleiben ohne Zeichen: nichts mehrdeutig, jedes Zeichen kostet SMS-Budget."""
    catalog_id = _RENDERER_TO_CATALOG_METRIC_ID.get(metric_id)
    if catalog_id not in _AMBIGUOUS_CATALOG_METRIC_IDS:
        return ""
    aggregation = _RENDERER_TO_AGGREGATION.get(metric_id)
    if aggregation == "max":
        return "+"
    if aggregation == "min":
        return "-"
    return ""


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


def _sms_metric_cell(loc_result: LocationResult, metric_id: str) -> str | None:
    """"Kuerzel[+/-] Wert"-Zelle fuer ``metric_id`` (Issue #1362 Scheibe S5b,
    Spec Implementation Details Punkt 3). Wert+Formatierung kommen aus
    derselben Quelle wie der Klartext-Teil (``_PLAIN_ROWS``/``_metric_value``),
    GSM-7-saniert ueber ``_sms_gsm7_safe`` (Adversary-Fund Runde 4); das
    Kuerzel AUSSCHLIESSLICH aus dem zentralen Katalog
    (``metric_catalog.get_sms_code``), nie zur Laufzeit abgeleitet; das
    Auswertungszeichen (``+``/``-``) ausschliesslich ueber
    ``_sms_aggregation_sign``. ``None`` = kein Wert an diesem Ort ODER keine
    ``metric_id``/kein Kuerzel bekannt -- die Zelle entfaellt dann, ohne Platz
    oder einen Zaehler zu belegen (analog ``_plain_metric_cell``/
    Telegram-Pfad)."""
    row = _PLAIN_ROWS_BY_ID.get(metric_id)
    if row is None:
        return None
    _, _label, fmt = row
    value = _metric_value(loc_result, metric_id)
    if value is None:
        return None
    catalog_id = _RENDERER_TO_CATALOG_METRIC_ID.get(metric_id)
    code = get_sms_code(catalog_id) if catalog_id else ""
    if not code:
        return None
    code = f"{code}{_sms_aggregation_sign(metric_id)}"
    # Issue #1680 S1 (Spec D8): ``include_origin`` bleibt hier AKTIV ABGEWAEHLT
    # auf dem Default ``False`` -- die SMS zeigt die Gewitterstufe, aber KEINE
    # Herkunft. PO-Entscheidung, kein vergessener Anschluss. Drei Gruende:
    # (1) 153 Zeichen Gesamtbudget und kein Spaltenbudget fuer einen zweiten
    # ``·``-Abschnitt je Ort; (2) ``_sms_gsm7_safe`` entstellt den Trenner
    # ``·`` zu ``-``, der Zusatz saehe entstellt aus; (3) der
    # ``+N``-Mechanismus wuerde die vom Zusatz verdraengten hinteren Metriken
    # nur noch zaehlen statt zeigen. Gilt ueber denselben Renderer auch fuer
    # Premium-SMS, sobald der Ortsvergleich ihn bedient.
    return f"{code} {_sms_gsm7_safe(_fmt_overview_cell(fmt, value, loc_result))}"


def _plain_metric_cell(loc_result: LocationResult, metric_id: str) -> str | None:
    """"Label Wert"-Zelle fuer ``metric_id``, aus derselben Quelle wie der
    Klartext-Teil derselben Mail (``_PLAIN_ROWS``/``_metric_value``, Issue
    #1362 -- keine zweite Werte-/Formatierungsquelle). ``None`` = Wert nicht
    vorhanden ODER ``metric_id`` unbekannt (Zelle entfaellt)."""
    row = _PLAIN_ROWS_BY_ID.get(metric_id)
    if row is None:
        return None
    _, label, fmt = row
    value = _metric_value(loc_result, metric_id)
    if value is None:
        return None
    return f"{label} {_fmt_overview_cell(fmt, value, loc_result, include_origin=True)}"


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
) -> str:
    """Rendert einen Orts-Vergleich als Telegram-Nachricht (Issue #1270).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["telegram"]``: ``max_table_cols`` = 8 zaehlt inkl. der
    impliziten Zeit-/Orts-Spalte, also hoechstens 7 Metrik-Werte je Ort;
    ``max_chars`` = 4096 begrenzt die Gesamtnachricht.
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
        enabled_metrics if enabled_metrics is not None
        else [mid for mid, _ in _CHANNEL_METRICS]
    ))

    locations = location_render_order(result.locations)
    if not locations:
        return "Keine Vergleichsdaten verfügbar."

    header: list[str] = []
    if preset_name:
        header.append(f"ORTS-VERGLEICH — {preset_name}")
    else:
        header.append("ORTS-VERGLEICH")
    header.append(f"Datum: {result.target_date.strftime('%d.%m.%Y')}")
    # Issue #1268: Zeitfenster-Zeile ersatzlos entfernt (Bewertung = ganzer Tag),
    # analog render_comparison_text() und compare_html._render_header().
    header.append("")

    blocks: list[list[str]] = []
    for loc_result in locations:
        block = [loc_result.location.name]
        if loc_result.error is not None:
            block.append(f"   Fehler: {loc_result.error}")
            blocks.append(block)
            continue
        # Werte sind ortsabhaengig -- Verfuegbarkeit VOR der Prioritaets-/
        # Slot-Kappung pruefen (Adversary-Korrektur), nicht erst beim
        # Zellenbau. `cell_values` haelt jede Zelle nur einmal vor (keine
        # doppelte `_metric_value`/`_daily_summary`-Berechnung).
        cell_values = {mid: _plain_metric_cell(loc_result, mid) for mid in dedup_ids}
        available_ids = [mid for mid in dedup_ids if cell_values[mid] is not None]
        no_data_count = len(dedup_ids) - len(available_ids)
        layout = _channel_layout_for_metrics("telegram", available_ids)
        cells = [cell_values[mid] for mid in layout.table_columns]
        block.append("   " + (" · ".join(cells) if cells else "keine Werte"))
        # Zwei getrennt zaehlbare Ausfaelle (Invariante: sichtbare Zellen +
        # Platzmangel-Zaehler + Ohne-Daten-Zaehler == Anzahl gewaehlter
        # Groessen). Je eigene Zeile INNERHALB dieses Ortsblocks, weil beide
        # Zahlen ortsabhaengig sind.
        if layout.demoted_count > 0:
            block.append("   " + telegram_metric_notice(
                layout.demoted_count, context="vergleich",
            ))
        if no_data_count > 0:
            block.append("   " + _telegram_no_data_notice(no_data_count))
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
            notices = build_official_alert_notices(None, [(a, []) for a in filtered])
            sources = list(dict.fromkeys(
                official_alert_source_label(a.source) for a in filtered
            ))
            warn_text = render_official_alert_telegram(
                notices, prefix=loc_result.location.name,
                source_label=" · ".join(sources), show_scope=False,
                tz=location_tz(loc_result.location),
            )
            block.append(f"   {warn_text}")
        blocks.append(block)

    max_chars = limits["max_chars"]
    # Metrik-Platzmangel-/Ohne-Daten-Hinweise stecken bereits als Zeilen IN
    # den jeweiligen `blocks` (s.o.) -- die folgende Ueberlauf-Logik behandelt
    # Ortsbloecke deshalb wieder atomar wie vor #1362, ohne einen separaten
    # Metrik-Hinweis mitzurechnen.
    text = _join_telegram(header, blocks)
    if max_chars is None or len(text) <= max_chars:
        return text

    # Ueberlauf: NICHT hart mitten im Wort schneiden (das ergaebe eine halbe
    # Datenzeile, die wie ein vollstaendiger Wert aussieht). Stattdessen ganze
    # ORTSBLOECKE behalten und den Verlust ausweisen — gleiche Einpass-Schleife
    # mit mitgerechnetem Hinweis wie im SMS-Pfad (alert/render.py:521-529).
    kept: list[list[str]] = []
    for block in blocks:
        notice = _telegram_notice(len(blocks) - len(kept) - 1)
        if len(_join_telegram(header, kept + [block]) + notice) <= max_chars:
            kept.append(block)
        else:
            break

    omitted = len(blocks) - len(kept)
    if not kept:
        # Degeneration: schon der erste Ortsblock sprengt 4096 Zeichen. Dann an
        # der Wortgrenze kuerzen (letztes Sicherheitsnetz, geteilter Helfer
        # `_word_boundary_truncate`) statt mitten im Wort.
        notice = _telegram_notice(omitted - 1)
        body = _join_telegram(header, [blocks[0]])
        return _word_boundary_truncate(body, max(max_chars - len(notice), 0)) + notice

    body = _join_telegram(header, kept) + _telegram_notice(omitted)
    return body if len(body) <= max_chars else _word_boundary_truncate(body, max_chars)


def _join_telegram(header: list[str], blocks: list[list[str]]) -> str:
    return "\n".join(header + [line for block in blocks for line in block])


def _telegram_notice(omitted: int) -> str:
    """Ehrlicher Kuerzungs-Hinweis (#1269): benennt die Zahl der nicht
    dargestellten Orte. Leer, wenn nichts entfaellt. Rang-/score-frei (AC-3)."""
    if omitted <= 0:
        return ""
    return f"\n… +{omitted} weitere Orte (Telegram-Limit) — vollständig per E-Mail"


def _telegram_no_data_notice(no_data_count: int) -> str:
    """Ehrlicher Hinweis fuer OHNE-DATEN (#1362, Adversary-Fund/Gegenpruefung):
    eine ausgewaehlte Groesse hat an DIESEM Ort keinen Wert (z.B. Ausfall der
    Fallback-Kette) -- anders als der Platzmangel-Fall
    (``_telegram_metric_notice``) ist das KEIN Verdraengungs-Effekt der
    7-Zellen-Grenze. Beide Faelle bleiben getrennt zaehlbar (Invariante:
    sichtbare Zellen + Platzmangel-Zaehler + Ohne-Daten-Zaehler == Anzahl
    gewaehlter Groessen). Bewusst OHNE "vollstaendig per E-Mail": die Mail
    zeigt fuer diese Groesse ebenfalls keinen Wert (nur einen "-"-Platzhalter,
    s. ``render_comparison_text``), das waere also ein falsches Versprechen.
    Leer, wenn nichts fehlt."""
    if no_data_count <= 0:
        return ""
    return f"… +{no_data_count} gewählte Wettergrößen ohne Wert an diesem Ort"


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
    parts = []
    for symbol, level, hour in entries:
        if not level:
            parts.append(symbol)
        else:
            value = f"{level}@{hour}" if hour is not None else level
            parts.append(f"{symbol}:{value}")
    return "!" + " ".join(parts)


def _sms_location_part(
    loc_result, enabled_metrics: list[str] | None, budget: "int | None",
) -> str:
    """Flache SMS-Darstellung EINES Ortes.

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
    waren nie Kandidat fuer einen Platz (analog Telegram/``_plain_metric_cell``,
    kein zweiter "ohne Wert"-Zaehler im SMS-Budget -- dafuer fehlt hier
    schlicht der Platz, s. Spec "Implementation Details Punkt 3").

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
        return f"{name} n/a"
    tz = resolve_location_tz(loc_result.location)
    # Issue #1461 S3b-2b (AC-17): derselbe Wechsel wie im Compare-Telegram
    # (oben) -- der Vorgabewert von `official_alerts_to_sms_entries()` faellt
    # sonst auf `MIN_SMS_LEVEL` (orange) zurueck. `min_level` explizit auf die
    # Startschwelle "gering" gesetzt, keine zweite Zahlenreihe.
    entries = official_alerts_to_sms_entries(
        loc_result.official_alerts, tz,
        min_level=alert_urgency.min_official_level_for_threshold("LOW"),
    )
    marker = _official_alert_sms_marker(entries)

    dedup_ids = list(dict.fromkeys(
        enabled_metrics if enabled_metrics is not None
        else [mid for mid, _ in _CHANNEL_METRICS]
    ))
    cells = [
        c for c in (_sms_metric_cell(loc_result, mid) for mid in dedup_ids)
        if c is not None
    ]

    def _assemble(kept_cells: list[str], demoted: int) -> str:
        text_parts = [name] + kept_cells
        if demoted > 0:
            text_parts.append(f"+{demoted}")
        if marker:
            text_parts.append(marker)
        return " ".join(text_parts)

    kept = list(cells)
    demoted = 0
    while kept and budget is not None and len(_assemble(kept, demoted)) > budget:
        kept.pop()
        demoted += 1

    return _assemble(kept, demoted)


def render_compare_sms(
    result: ComparisonResult,
    *,
    enabled_metrics: list[str] | None = None,
) -> str:
    """Rendert einen Orts-Vergleich als flache SMS (Issue #1270).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["sms"]``: ``max_table_cols`` = 0 (keine Tabelle, flache
    Zeile), ``max_chars`` (verkettungssicherer GSM-7-Wert -- Herleitung s.
    Konstante in ``channel_layout.py``, Adversary-Fund #1362 S5b Runde 5).

    Ueberlauf folgt der Hauskonvention aus ``alert/render.py:507-535``
    (ADR-0011:42, "SMS-Laengen-Budget mit `+k`-Ueberlauf"): Kopf immer; Orte
    solange, wie das Ergebnis INKL. des dann noetigen ` +k`-Suffixes ins Budget
    passt; die restlichen Orte werden als ` +k` AUSGEWIESEN. Ein stiller Abbruch
    waere eine luegende Ausgabe (vgl. #1269) — die SMS behauptete sonst einen
    vollstaendigen Vergleich, den sie nicht zeigt. Endgarantie:
    ``len <= CHANNEL_LIMITS["sms"]["max_chars"]``.
    """
    max_chars = CHANNEL_LIMITS["sms"]["max_chars"]
    locations = location_render_order(result.locations)
    if not locations:
        return "Vergleich: keine Daten"

    # Issue #1268: Stundenfenster-Angabe ersatzlos entfernt (Bewertung = ganzer
    # Tag). Sie waere dauerhaft "00-23h" — eine Nicht-Information, die 8 von
    # `max_chars` Zeichen belegt, die hier fuer echte Messwerte gebraucht werden.
    head = f"Vergleich {result.target_date.strftime('%d.%m.')}:"
    # Issue #1362 Scheibe S5b: Budget je Ortsteil, ALS OB dieser Ort der
    # einzige in der Nachricht waere (Kopf + ein Trennzeichen abgezogen) --
    # eine konservative, aber sichere obere Schranke: der bestehende
    # Orts-Ueberlauf (unten) haelt die GESAMTLAENGE unabhaengig davon
    # <=max_chars, indem er im Zweifel ganze Ortsbloecke weglaesst.
    #
    # Adversary-Fund (#1362 S5b, Runde 2): OHNE Reserve konnte ein einzelner,
    # bereits metrik-gekuerzter Ortsteil das GESAMTBUDGET so knapp ausschoepfen,
    # dass fuer den nachtraeglich noetigen Orts-Ueberlauf-Hinweis (" +k Orte")
    # kein Platz mehr blieb -- die Einpass-Schleife unten verwarf den Ortsteil
    # dann KOMPLETT und fiel auf die harte Wortgrenzen-Kuerzung zurueck, die
    # (anders als die Metrik-Kuerzung) mitten in einer Kuerzel/Wert-Zelle
    # schneiden kann (z.B. "...HU... +1 Orte" statt einer ganzen Zelle).
    # Deshalb wird hier EXAKT der schlimmstmoegliche Orts-Ueberlauf-Hinweis
    # fuer DIESES Ergebnis reserviert (alle Orte bis auf einen entfallen) --
    # datenabhaengig statt eines geratenen Fixwerts, und bei nur einem Ort
    # ohnehin 0 (kein Ueberlauf moeglich).
    max_possible_omitted_locations = max(len(locations) - 1, 0)
    location_overflow_reserve = len(
        _sms_location_overflow_notice(max_possible_omitted_locations)
    )
    location_budget = (
        max(max_chars - len(head) - 1 - location_overflow_reserve, 0)
        if max_chars is not None else None
    )
    parts = [
        _sms_location_part(loc, enabled_metrics, location_budget)
        for loc in locations
    ]
    if not parts:
        return f"{head} keine Werte"
    if max_chars is None:
        return f"{head} " + "; ".join(parts)

    # Einpass-Schleife mit mitgerechnetem Marker (1:1 alert/render.py:521-529):
    # der Marker darf das Budget nicht selbst sprengen.
    kept: list[str] = []
    for part in parts:
        omitted = len(parts) - len(kept) - 1  # weggelassen, wenn wir hier stoppen
        marker = _sms_location_overflow_notice(omitted)
        candidate = f"{head} " + "; ".join(kept + [part]) + marker
        if len(candidate) <= max_chars:
            kept.append(part)
        else:
            break

    omitted = len(parts) - len(kept)
    if not kept:
        # Degenerationsfall: schon der erste Ort sprengt das Budget. "Ueberschrift
        # + nichts" ist verboten — dann lieber EIN gekuerzter Ort. Gekuerzt wird
        # der Ortsblock ALLEIN (nicht Kopf+Block), weil eine Wortgrenzen-Kuerzung
        # ueber den Kopf hinweg bei einem einzigen ueberlangen Ortsnamen genau auf
        # der Kopf-Grenze schnitte und wieder "Ueberschrift + nichts" ergaebe.
        # `_word_boundary_truncate` faellt bei einem Wort > Budget auf den harten
        # Schnitt zurueck: ein unkenntlicher Ort ist ehrlicher als ein
        # verschwiegener.
        marker = _sms_location_overflow_notice(omitted - 1 if omitted > 1 else 0)
        budget = max_chars - len(head) - 1 - len(marker)
        fitted = _word_boundary_truncate(parts[0], max(budget, 0))
        if fitted != parts[0] and not fitted.endswith("..."):
            # Der Helfer schneidet nur an Wortgrenzen mit "..."; findet er keine
            # (Ortsname laenger als das Budget), schneidet er hart und stumm. Ein
            # abgeschnittener Name darf aber nicht wie ein vollstaendiger aussehen.
            fitted = fitted[: max(len(fitted) - 3, 0)] + "..."
        body = f"{head} " + fitted + marker
        return body[:max_chars]

    body = f"{head} " + "; ".join(kept)
    body += _sms_location_overflow_notice(omitted)
    # Garantie len<=limit auch im Degenerationsfall (Kopf allein zu lang).
    return body if len(body) <= max_chars else body[:max_chars]


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
