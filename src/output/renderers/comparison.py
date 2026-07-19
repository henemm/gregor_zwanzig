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

from typing import Optional

from app.models import Corridor
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult
from output.renderers.channel_layout import CHANNEL_LIMITS
from output.renderers.email.compare_html import (
    _build_location_outlook_rows, _fmt_thunder, _fmt_visibility_overview,
    _metric_value, sort_locations_alphabetically,
)
from output.renderers.email.outlook import render_outlook_plain
from output.metric_format import format_value
from output.renderers.alert.official_alerts import (
    _word_boundary_truncate,
    render_official_alerts_plain,
)

# Issue #1285: die fuenf bisher stillschweigend verworfenen Uebersichts-Zeilen
# (Renderer-Metrik-ID, Label, Formatierung). Wert-Quelle und Formatierung sind
# BEWUSST die des HTML-Pfads (`compare_html._metric_value` / `_fmt_*`) statt
# einer Klartext-Kopie -- sonst beschreibt dieselbe Wetterlage in HTML und
# Klartext derselben Mail verschiedene Zahlen.
_DAILY_PLAIN_ROWS: tuple[tuple[str, str, object], ...] = (
    ("precip_sum", "Regen", lambda v: f"{v:.1f} mm"),
    ("pop_max", "Regenwahrscheinlichkeit", lambda v: f"{v:.0f}%"),
    ("thunder_max", "Gewitter", _fmt_thunder),
    ("uv_max", "UV max", lambda v: f"{v:.0f}"),
    ("visibility_min", "Sicht min", _fmt_visibility_overview),
    # Issue #1296, Klasse B (kein LocationResult-Feld, Live-Ableitung ueber
    # _metric_value -> _daily_summary, analog den fuenf #1285-Zeilen).
    ("cape_max", "CAPE", lambda v: f"{v:.0f} J/kg"),
    ("freezing_level", "Nullgradgrenze", lambda v: f"{v:.0f} m"),
)


def render_comparison_text(
    result: ComparisonResult,
    profile: Optional[ActivityProfile] = None,
    enabled_metrics: set | None = None,
    *,
    outlook_enabled: bool = False,
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
        enabled_metrics: Issue #1125. Filtert die sechs Uebersichts-Zeilen
            je Ort auf die enthaltenen Renderer-Metrik-IDs (z.B.
            "temp_max", "wind_max"). ``None`` = kein Filter (alle Zeilen,
            Rueckwaertskompatibilitaet). Spiegelt exakt die Semantik von
            ``_visible_metrics()`` im HTML-Pfad
            (``output.renderers.email.compare_html``). Amtliche Warnungen
            bleiben davon unabhaengig immer sichtbar.

    Returns:
        Klartext-String fuer die E-Mail.
    """
    _ = profile  # akzeptiert fuer API-Konsistenz, aktuell ohne Wirkung

    target_date = result.target_date
    created_at = result.created_at
    # Zentraler Sortier-Helfer (PO-Update 2026-07-08): alphabetisch, case-
    # insensitiv, identisch zu render_compare_html() -- keine Doppel-Logik.
    locations = sort_locations_alphabetically(result.locations)
    if not locations:
        return "Keine Vergleichsdaten verfügbar."

    lines: list[str] = []
    lines.append("ORTS-VERGLEICH")
    lines.append("=" * 24)
    lines.append(f"Datum: {target_date.strftime('%A, %d.%m.%Y')}")
    # Issue #1268: Zeitfenster-Zeile ersatzlos entfernt (Bewertung = ganzer Tag).
    lines.append(f"Erstellt: {created_at.strftime('%d.%m.%Y %H:%M')}")
    lines.append("")
    lines.append("-" * 50)

    for loc_result in locations:
        loc = loc_result.location
        lines.append(loc.name)
        if loc_result.error is not None:
            lines.append(f"   Fehler: {loc_result.error}")
            lines.append("")
            continue

        def _metric_visible(metric_id: str) -> bool:
            return enabled_metrics is None or metric_id in enabled_metrics

        if _metric_visible("temp_max"):
            temp_max = loc_result.temp_max
            lines.append(f"   Temp max: {format_value('temperature', temp_max, style='plain')}" if temp_max is not None else "   Temp max: -")
        if _metric_visible("wind_max"):
            wind_max = loc_result.wind_max
            lines.append(f"   Wind: {format_value('wind', wind_max, style='plain')}" if wind_max is not None else "   Wind: -")
        # Issue #1296, Klasse A: temp_min/gust_max lesen -- wie temp_max/
        # wind_max oben -- direkt das LocationResult-Feld, kein _metric_value-
        # Umweg noetig (kein _DAILY_AGGREGATE_FIELD-Eintrag dafuer).
        if _metric_visible("temp_min"):
            temp_min = loc_result.temp_min
            lines.append(f"   Temp min: {format_value('temperature', temp_min, style='plain')}" if temp_min is not None else "   Temp min: -")
        if _metric_visible("gust_max"):
            gust_max = loc_result.gust_max
            lines.append(f"   Böen: {format_value('wind', gust_max, style='plain')}" if gust_max is not None else "   Böen: -")
        # Issue #1285: vier bisher still verworfene Zeilen. Werte kommen aus
        # DERSELBEN Quelle wie die HTML-Matrix (_metric_value -> Engine-Feld
        # bzw. live aus hourly_data), damit HTML und Klartext nie
        # auseinanderlaufen.
        for metric_id, label, fmt in _DAILY_PLAIN_ROWS:
            if not _metric_visible(metric_id):
                continue
            value = _metric_value(loc_result, metric_id)
            lines.append(f"   {label}: {fmt(value) if value is not None else '-'}")
        if _metric_visible("sunny_hours"):
            # Issue #1214 Scheibe 6: sunshine.decimals=1 im Katalog (vormals
            # F001-Ausnahme in Scheibe 5, s. Spec) macht die Migration jetzt
            # beweisbar verhaltensneutral: calculate_sunny_hours liefert immer
            # round(x, 1) als float, also str(4.7) == "4.7" == f"{4.7:.1f}".
            sunny_h = loc_result.sunny_hours
            lines.append(
                f"   Sonne: {format_value('sunshine', sunny_h, style='bare')}h"
                if sunny_h is not None else "   Sonne: -"
            )
        if _metric_visible("cloud_avg"):
            cloud = loc_result.cloud_avg
            lines.append(f"   Wolken: {format_value('cloud_total', cloud, style='plain')}" if cloud is not None else "   Wolken: -")
        if _metric_visible("snow_depth_cm"):
            snow_depth = loc_result.snow_depth_cm
            lines.append(f"   Schneehöhe: {format_value('snow_depth', snow_depth, style='plain')}" if snow_depth is not None else "   Schneehöhe: -")
        if _metric_visible("snow_new_cm"):
            snow_new = loc_result.snow_new_cm
            lines.append(f"   Neuschnee: {snow_new:.0f} cm" if snow_new is not None else "   Neuschnee: -")

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
    section_lines: list[str] = []
    for loc_result in locations:
        if loc_result.error is not None:
            continue
        have_hourly = bool(loc_result.hourly_data)
        outlook_rows = (
            _build_location_outlook_rows(loc_result)
            if outlook_enabled and loc_result.outlook_hourly_data else []
        )
        if not have_hourly and not outlook_rows:
            continue
        section_lines.append(loc_result.location.name)
        if have_hourly:
            for dp in loc_result.hourly_data:
                ts = dp.ts.strftime("%H:%M") if hasattr(dp.ts, "strftime") else str(dp.ts)
                temp = f"{dp.t2m_c:.0f}°" if dp.t2m_c is not None else "-"
                gef = f"{dp.wind_chill_c:.0f}°" if dp.wind_chill_c is not None else "-"
                wind = f"{dp.wind10m_kmh:.0f}" if dp.wind10m_kmh is not None else "-"
                cloud_pct = f"{dp.cloud_total_pct}%" if dp.cloud_total_pct is not None else "-"
                section_lines.append(f"   {ts}  Temp {temp}  Gef. {gef}  Wind {wind}  Wolken {cloud_pct}")
        if outlook_rows:
            section_lines.append(render_outlook_plain(outlook_rows, show_acc=False).strip("\n"))
        section_lines.append("")

    if section_lines:
        lines.append("STUNDENVERLAUF")
        lines.append("-" * 15)
        lines.extend(section_lines)

    lines.append("---")
    lines.append("Gregor Zwanzig")

    return "\n".join(lines)


def render_compare_email(
    result: ComparisonResult,
    *,
    profile: Optional[ActivityProfile] = None,
    warnings: list[str] | None = None,
    top_n_details: Optional[int] = None,
    enabled_metrics: set | None = None,
    hourly_metrics: set | None = None,
    hourly_enabled: bool = True,
    preset_name: Optional[str] = None,
    preset_schedule: Optional[str] = None,
    preset_weekday: Optional[int] = None,
    corridors: list[Corridor] | None = None,
    outlook_enabled: bool = False,
) -> tuple[str, str]:
    """Render both HTML and plain-text parts for a compare email (v2, #1110).

    Single entry point for all compare-email render callers. Keeps the HTML
    renderer (output.renderers.email.compare_html) and the plain-text renderer
    (this module) in one place. Kein Score/Winner mehr -- ``winner_tags``
    entfaellt vollstaendig. ``top_n_details`` (Issue #1104) wird angenommen,
    hat aber AKTUELL KEINE Wirkung: PO 2026-07-08 -- Mail zeigt immer alle
    Orte; die Semantik wird in #1105-#1107 neu definiert. ``enabled_metrics``
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
        top_n_details=top_n_details,
        enabled_metrics=enabled_metrics,
        hourly_metrics=hourly_metrics,
        hourly_enabled=hourly_enabled,
        preset_name=preset_name,
        preset_schedule=preset_schedule,
        preset_weekday=preset_weekday,
        corridors=corridors,
        outlook_enabled=outlook_enabled,
    )
    text_body = render_comparison_text(
        result, profile=profile, enabled_metrics=enabled_metrics,
        outlook_enabled=outlook_enabled,
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

# SMS ist flach und hart budgetiert (CHANNEL_LIMITS["sms"]["max_chars"] = 140):
# nur die zwei wichtigsten Metriken je Ort.
_SMS_METRICS_PER_LOCATION = 2


def _format_channel_metric(metric_id: str, loc_result: LocationResult) -> str | None:
    """Formatiert einen Uebersichtswert ueber die zentrale Metrik-Formatierung.
    ``None`` = Wert nicht vorhanden (Zeile/Zelle entfaellt im Kanal-Render)."""
    value = getattr(loc_result, metric_id, None)
    if value is None:
        return None
    if metric_id == "temp_max":
        return format_value("temperature", value, style="plain")
    if metric_id == "wind_max":
        return format_value("wind", value, style="plain")
    if metric_id == "sunny_hours":
        return f"{format_value('sunshine', value, style='bare')}h"
    if metric_id == "cloud_avg":
        return format_value("cloud_total", value, style="plain")
    if metric_id == "snow_depth_cm":
        return format_value("snow_depth", value, style="plain")
    if metric_id == "snow_new_cm":
        return f"{value:.0f} cm"
    return None


def _channel_metric_cells(
    loc_result: LocationResult,
    enabled_metrics: set | None,
    limit: int | None,
) -> list[str]:
    """Sichtbare "Label Wert"-Zellen eines Ortes, gefiltert ueber
    ``enabled_metrics`` (``None`` = kein Filter) und auf ``limit`` Zellen
    budgetiert (``None`` = unbegrenzt)."""
    cells: list[str] = []
    for metric_id, label in _CHANNEL_METRICS:
        if enabled_metrics is not None and metric_id not in enabled_metrics:
            continue
        value = _format_channel_metric(metric_id, loc_result)
        if value is None:
            continue
        cells.append(f"{label} {value}")
        if limit is not None and len(cells) >= limit:
            break
    return cells


def render_compare_telegram(
    result: ComparisonResult,
    *,
    enabled_metrics: set | None = None,
    preset_name: Optional[str] = None,
) -> str:
    """Rendert einen Orts-Vergleich als Telegram-Nachricht (Issue #1270).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["telegram"]``: ``max_table_cols`` = 8 zaehlt inkl. der
    impliziten Zeit-/Orts-Spalte, also hoechstens 7 Metrik-Werte je Ort;
    ``max_chars`` = 4096 begrenzt die Gesamtnachricht.
    """
    limits = CHANNEL_LIMITS["telegram"]
    max_cols = limits["max_table_cols"]
    metric_slots = None if max_cols is None else max(1, max_cols - 1)

    locations = sort_locations_alphabetically(result.locations)
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
        cells = _channel_metric_cells(loc_result, enabled_metrics, metric_slots)
        block.append("   " + (" · ".join(cells) if cells else "keine Werte"))
        for line in render_official_alerts_plain(
            [(loc_result.location.name, loc_result.official_alerts)]
        ):
            block.append(f"   ⚠️ {line}")
        blocks.append(block)

    max_chars = limits["max_chars"]
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


def _sms_location_part(loc_result, enabled_metrics: set | None) -> str:
    """Flache SMS-Darstellung EINES Ortes.

    Orte ohne abrufbare Daten (``error``) werden als ``"<Name> n/a"``
    dargestellt statt weggefiltert: ein weggefilterter Ort waere weder sichtbar
    noch im ``+k`` gezaehlt — die SMS behauptete dann einen vollstaendigen
    Vergleich ueber weniger Orte, als er hat (#1269). ``render_compare_telegram``
    haelt Fehler-Orte aus demselben Grund als "Fehler: …"-Block sichtbar; die
    SMS-Form ist nur knapper (140 Zeichen). Die Fehlerursache selbst traegt die
    SMS bewusst nicht — sie steht in der E-Mail/Telegram-Fassung.

    ASCII "n/a" statt eines Gedankenstrichs, weil ein Ort ohne Werte sonst wie
    ein Ort mit leerem Wert aussieht.
    """
    if loc_result.error is not None:
        return f"{loc_result.location.name} n/a"
    cells = _channel_metric_cells(loc_result, enabled_metrics, _SMS_METRICS_PER_LOCATION)
    return " ".join([loc_result.location.name] + cells)


def render_compare_sms(
    result: ComparisonResult,
    *,
    enabled_metrics: set | None = None,
) -> str:
    """Rendert einen Orts-Vergleich als flache SMS (Issue #1270).

    Reine Funktion, kein Score/Rang (AC-3). Budget aus
    ``CHANNEL_LIMITS["sms"]``: ``max_table_cols`` = 0 (keine Tabelle, flache
    Zeile), ``max_chars`` = 140.

    Ueberlauf folgt der Hauskonvention aus ``alert/render.py:507-535``
    (ADR-0011:42, "SMS-Laengen-Budget mit `+k`-Ueberlauf"): Kopf immer; Orte
    solange, wie das Ergebnis INKL. des dann noetigen ` +k`-Suffixes ins Budget
    passt; die restlichen Orte werden als ` +k` AUSGEWIESEN. Ein stiller Abbruch
    waere eine luegende Ausgabe (vgl. #1269) — die SMS behauptete sonst einen
    vollstaendigen Vergleich, den sie nicht zeigt. Endgarantie: ``len <= 140``.
    """
    max_chars = CHANNEL_LIMITS["sms"]["max_chars"]
    locations = sort_locations_alphabetically(result.locations)
    if not locations:
        return "Vergleich: keine Daten"

    # Issue #1268: Stundenfenster-Angabe ersatzlos entfernt (Bewertung = ganzer
    # Tag). Sie waere dauerhaft "00-23h" — eine Nicht-Information, die 8 der 140
    # Zeichen belegt, die hier fuer echte Messwerte gebraucht werden.
    head = f"Vergleich {result.target_date.strftime('%d.%m.')}:"
    parts = [_sms_location_part(loc, enabled_metrics) for loc in locations]
    if not parts:
        return f"{head} keine Werte"
    if max_chars is None:
        return f"{head} " + "; ".join(parts)

    # Einpass-Schleife mit mitgerechnetem Marker (1:1 alert/render.py:521-529):
    # der Marker darf das Budget nicht selbst sprengen.
    kept: list[str] = []
    for part in parts:
        omitted = len(parts) - len(kept) - 1  # weggelassen, wenn wir hier stoppen
        marker = f" +{omitted}" if omitted > 0 else ""
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
        marker = f" +{omitted - 1}" if omitted > 1 else ""
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
    if omitted > 0:
        body += f" +{omitted}"
    # Garantie len<=limit auch im Degenerationsfall (Kopf allein zu lang).
    return body if len(body) <= max_chars else body[:max_chars]
