"""Kompakt-Mail der Orte (Issue #3059).

Reine Funktion ``render_compare_compact()``: ASCII-Klartext fuer ein
Orte-Abo mit ``display_config.email_format == "compact"``. Aufbau:

* Kopf: Bereichsname ("Orte"/"Locations") und Datum,
* Hinweis, falls amtliche Warnungen nicht abrufbar waren,
* je Ort EINE Zeile: ASCII-gefalteter Name, Warnmarker bei amtlicher Warnung
  (``_severity_prefix`` wie die Trip-Kompakt-Mail), dann je fuer die E-Mail
  gewaehlter Groesse ``<Kuerzel> <Wert>`` (Kuerzel = ``compact_label`` des
  Metrik-Katalogs, Protokoll-Token, nie uebersetzt),
* je Ort eine eingerueckte 3-Tages-Ausblick-Zeile, nur wenn der Ausblick
  eingeschaltet ist (feat_3122 Nr. 6),
* Fusszeile (Herkunft).

Kein Stundenverlauf: die Kompakt-Mail ignoriert die Block-Schalter ausser
dem Ausblick (#722, PO #3160). Gesamttext strikt unter 2 KB (< 2048 Byte,
wie Trip-Kompakt und ``email_spec_validator``) inklusive Kuerzungs-Hinweis;
gekuerzt wird vom Listenende ("+N Orte nicht gezeigt").

SPEC: docs/specs/modules/feat_3059_orte_kompakt_mail.md
"""
from __future__ import annotations

from typing import Optional

from app.ampel import resolve_ampel
from app.metric_catalog import get_metric
from app.user import ComparisonResult, LocationResult
from i18n import Lang, t, tn
from i18n.format import fmt_date_numeric
from output.renderers.email.compact import _ascii, _severity_prefix
from output.renderers.email.helpers import (
    _AMPEL_STAGE_TONES, build_origin_footer, format_trend_tokens,
    render_origin_footer_text,
)

#: Obergrenze der Kompakt-Mail in Byte (renderer_email_spec.md, wie Trip);
#: der Text bleibt STRIKT darunter (``< COMPACT_MAX_BYTES``), wie der Validator.
COMPACT_MAX_BYTES = 2048


def _kuerzel_je_zeile(renderer_ids: list[str]) -> dict[str, str]:
    """Kuerzel je Renderer-Zeile: ``compact_label`` der Katalog-Groesse.
    Tragen zwei gewaehlte Zeilen dasselbe Kuerzel (z. B. Temp max und min ->
    "T"), bekommen sie das Kuerzel ihrer Kuerzel-Kennung (``D``/``L``, #2232),
    damit die Zeile eindeutig bleibt."""
    from output.renderers.comparison import (
        _CV2_BY_KEY, _RENDERER_TO_CATALOG_METRIC_ID,
    )

    def _label(catalog_id: Optional[str]) -> Optional[str]:
        if catalog_id is None:
            return None
        try:
            return get_metric(catalog_id).compact_label
        except KeyError:
            return None

    basis = {rid: _label(_CV2_BY_KEY.get(rid, {}).get("metric_id")) for rid in renderer_ids}
    zaehler: dict[str, int] = {}
    for k in basis.values():
        if k:
            zaehler[k] = zaehler.get(k, 0) + 1
    out: dict[str, str] = {}
    for rid, k in basis.items():
        if k and zaehler[k] > 1:
            k = _label(_RENDERER_TO_CATALOG_METRIC_ID.get(rid)) or k
        out[rid] = k or rid
    return out


def _warnmarker(loc_result: LocationResult) -> str:
    """ASCII-Warnmarker aus der hoechsten amtlichen Warnstufe des Ortes
    (Stufe 2 gelb "!", 3 orange "!!", 4 rot "!!!"); "" ohne Warnung.
    Startschwelle wie Telegram/SMS des Berichts (``LOW``)."""
    import services.alert_urgency as alert_urgency

    min_level = alert_urgency.min_official_level_for_threshold("LOW")
    stufen = [a.level for a in (loc_result.official_alerts or []) if a.level >= min_level]
    if not stufen:
        return ""
    index = max(0, min(max(stufen) - 1, len(_AMPEL_STAGE_TONES) - 1))
    return _severity_prefix(_AMPEL_STAGE_TONES[index])


def _ortszeile(loc_result: LocationResult, renderer_ids: list[str],
               kuerzel: dict[str, str], metric_formats: Optional[dict[str, bool]],
               lang: Lang) -> str:
    """Eine Zeile je Ort: ``Name: [!] K Wert K Wert ...``."""
    from output.renderers.comparison import (
        _PLAIN_ROWS_BY_ID, _daily_summary, _fmt_overview_cell, _metric_value,
    )

    teile = [f"{loc_result.location.name}:"]
    marker = _warnmarker(loc_result)
    if marker:
        teile.append(marker)
    if loc_result.error is not None:
        teile.append(t("vergleich.ort.fehler", lang, fehler=loc_result.error))
        return _ascii(" ".join(teile))
    summary = _daily_summary(loc_result) if loc_result.hourly_data else None
    for rid in renderer_ids:
        row = _PLAIN_ROWS_BY_ID.get(rid)
        if row is None:
            continue
        value = _metric_value(loc_result, rid, summary)
        if value is None:
            zelle = "-"
        else:
            zelle = _fmt_overview_cell(
                row[2], value, loc_result, lang=lang, metric_id=rid,
                friendly=bool((metric_formats or {}).get(rid)), summary=summary,
            )
        teile.append(f"{kuerzel[rid]} {zelle}")
    return _ascii(" ".join(teile))


def _ausblickzeile(loc_result: LocationResult, outlook_metrics: Optional[list],
                   outlook_metric_formats: Optional[dict], ampel: dict,
                   lang: Lang) -> str:
    """Eingerueckte 3-Tages-Ausblick-Zeile eines Ortes (eine Zeile, Tage
    durch " | " getrennt). Zellen aus demselben Zeilenbau wie die
    ausfuehrliche Mail (``_build_location_outlook_rows``, ``cells_ascii``)."""
    from output.renderers.compare_outlook_metric_ids import outlook_columns
    from output.renderers.email.compare_html import _build_location_outlook_rows
    from output.renderers.email.outlook_state_hint import (
        OutlookState, render_outlook_state_plain,
    )
    from output.renderers.email.thunder_branch import (
        thunder_cell_compact, thunder_column_index,
    )

    name = t("mail.ausblick.name", lang)
    rows = (
        _build_location_outlook_rows(
            loc_result, outlook_metrics, outlook_metric_formats, lang, ampel=ampel)
        if loc_result.outlook_hourly_data else []
    )
    if not rows:
        zustand = render_outlook_state_plain(
            OutlookState.UNAVAILABLE, ascii_safe=True, lang=lang)
        return _ascii(f"  {name}: {zustand}")
    tage: list[str] = []
    if outlook_metrics is not None:
        columns = outlook_columns(outlook_metrics, outlook_metric_formats)
        gew_index = thunder_column_index(columns)
        for row in rows:
            cells = row.get("cells_ascii") or row.get("cells") or []
            texte = [cells[i] if i < len(cells) else "-" for i in range(len(columns))]
            if gew_index is not None:
                texte[gew_index] = thunder_cell_compact(
                    format_trend_tokens(row, lang=lang, ampel=ampel), row, lang=lang)
            werte = " ".join(f"{c['label']} {texte[i]}" for i, c in enumerate(columns))
            tage.append(f"{row.get('weekday', '')} {werte}".strip())
    else:
        for row in rows:
            tok = format_trend_tokens(row, lang=lang, ampel=ampel)
            tage.append(" ".join(
                s for s in (row.get("weekday", ""), tok["temp_str"],
                            tok["precip_str"], tok["wind_str"]) if s))
    return _ascii(f"  {name}: " + " | ".join(tage))


def _hinweis(omitted: int, lang: Lang) -> str:
    return _ascii(tn("vergleich.kompakt.nicht_gezeigt", omitted, lang))


def _zusammensetzen(kopf: list[str], bloecke: list[list[str]], fuss: list[str],
                    hinweis: str = "") -> str:
    zeilen = list(kopf)
    for block in bloecke:
        zeilen.extend(block)
    if hinweis:
        zeilen.append(hinweis)
    zeilen.append("")
    zeilen.extend(fuss)
    return "\n".join(zeilen)


def render_compare_compact(
    result: ComparisonResult,
    *,
    enabled_metrics: Optional[list[str]] = None,
    metric_formats: Optional[dict[str, bool]] = None,
    outlook_enabled: bool = False,
    outlook_metrics: Optional[list] = None,
    outlook_metric_formats: Optional[dict] = None,
    preset: dict,
    lang: Lang = "de",
    max_bytes: int = COMPACT_MAX_BYTES,
) -> str:
    """Kompakt-Mail der Orte als reiner ASCII-Text (strikt ``< max_bytes``).

    ``enabled_metrics``: Renderer-Kennungen der E-Mail-Liste in Listenfolge
    (``CompareRenderOptions.enabled_metrics_by_channel["email"]``); ``None``
    = nie eingestellt, dieselben Zeilen wie die Vergleichstabelle.
    """
    from output.renderers.comparison import _NIE_EINGESTELLT_IDS
    from output.renderers.email.compare_html import location_render_order
    from output.renderers.email.unavailable_hint import (
        any_official_alerts_unavailable, render_official_alerts_unavailable_plain,
    )

    renderer_ids = list(dict.fromkeys(
        enabled_metrics if enabled_metrics is not None else _NIE_EINGESTELLT_IDS))
    kuerzel = _kuerzel_je_zeile(renderer_ids)
    ampel = resolve_ampel(preset)
    locations = location_render_order(result.locations)

    kopf = [_ascii(f"{t('vergleich.kopf.titel_kurz', lang)} - "
                   f"{fmt_date_numeric(result.target_date, lang)}"), ""]
    if any_official_alerts_unavailable(locations):
        kopf.extend([_ascii(render_official_alerts_unavailable_plain(
            ascii_safe=True, lang=lang)), ""])
    if not locations:
        kopf.append(_ascii(t("vergleich.allgemein.keine_daten", lang)))

    bloecke: list[list[str]] = []
    for loc_result in locations:
        block = [_ortszeile(loc_result, renderer_ids, kuerzel, metric_formats, lang)]
        if outlook_enabled and outlook_metrics != [] and loc_result.error is None:
            block.append(_ausblickzeile(
                loc_result, outlook_metrics, outlook_metric_formats, ampel, lang))
        bloecke.append(block)

    fuss = ["-" * 20, _ascii(render_origin_footer_text(build_origin_footer(
        "compare", "compact", source="Open-Meteo", lang=lang)))]

    text = _zusammensetzen(kopf, bloecke, fuss)
    if len(text.encode("ascii")) < max_bytes:
        return text
    # Kuerzung vom Listenende: so viele Orte wie mit Hinweiszeile passen.
    for behalten in range(len(bloecke) - 1, -1, -1):
        text = _zusammensetzen(kopf, bloecke[:behalten], fuss,
                               _hinweis(len(bloecke) - behalten, lang))
        if len(text.encode("ascii")) < max_bytes:
            return text
    return text
