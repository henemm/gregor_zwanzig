"""Gemeinsamer Renderer fuer amtliche Warnungen — Compare UND Trip-Briefings.

Issue #1087 (Epic #1073 Slice 3). Setzt die Architektur-Leitplanke aus
Epic #1073 Punkt 6 um (ein gemeinsamer Renderer statt Kopie): sowohl der
Orts-Vergleich (`compare_html.py`, `comparison.py`) als auch die drei
Trip-Mail-Renderer (`html.py`, `plain.py`, `compact.py`) rufen diese
Funktionen auf statt eigenen Iterations-Code zu duplizieren.

`render_official_alerts_html` ist der verbatim verschobene Rumpf aus
`compare_html.py::_render_official_alerts_block` (Byte-Gleichheit Pflicht,
AC-2) — nur der Input ist generalisiert auf `(label, alerts)`-Paare statt
`LocationResult`.
"""
from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from i18n import Lang, fmt_date, fmt_weekday, t, tn
from output.tokens.hazard_symbols import (
    HAZARD_ORDER, HAZARD_SMS_SYMBOLS, LEVEL_LETTERS, LEVELLESS_HAZARDS,
    MIN_SMS_LEVEL, NUMERIC_LEVEL_HAZARDS, sms_symbol_for,
)

# Issue #1744 A1: `format_segment_reference` ist seit dem Umzug nach
# `segments.py` die GEMEINSAME Ortsformatierung aller Alarmarten (vorher hier
# definiert, faktisch der amtlichen Warnung vorbehalten). Der Import haelt
# zugleich den Re-Export fuer Bestandsaufrufer (`email/html.py:53`).
from .segments import format_alert_location, format_segment_reference

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from app.trip import Trip
    from services.official_alerts.models import OfficialAlert

# Level -> (Emoji, Schwere-Wort) fuer den Standalone-Alert-Text (Issue #1172).
# Das Emoji wird ausschliesslich vom Telegram-Renderer emittiert
# (render_official_alert_telegram); alle E-Mail-/SMS-/Subject-Pfade nutzen nur
# das Wort ([1]). Issue #1222: der Plain-Notice-Pfad laesst das Emoji weg.
# Issue #2668: das Wort steht im Katalog (`_LEVEL_KEYS`, `_level_word(level,
# lang)`); `_LEVEL_WORDS` bleibt die deutsche Sicht fuer Bestandsimporteure.
_LEVEL_KEYS: dict[int, tuple[str, str]] = {
    1: ("🟢", "warnung.stufe.gruen"),
    2: ("🟡", "warnung.stufe.gelb"),
    3: ("🟠", "warnung.stufe.orange"),
    4: ("🔴", "warnung.stufe.rot"),
}
_LEVEL_WORDS: dict[int, tuple[str, str]] = {
    level: (emoji, t(key, "de")) for level, (emoji, key) in _LEVEL_KEYS.items()
}


def _level_word(level: int, lang: Lang = "de") -> str:
    """Stufenwort in ``lang``; unbekannte Stufe -> ROT (Bestand)."""
    return t(_LEVEL_KEYS.get(level, _LEVEL_KEYS[4])[1], lang)


def _level_emoji(level: int) -> str:
    return _LEVEL_KEYS.get(level, _LEVEL_KEYS[4])[0]

# Position "N/3" auf der Warnstufen-Leiter GELB->ORANGE->ROT (Issue #1216).
# Issue #1441: Stufe 1 explizit ausserhalb der Leiter (0); die EAWS-Stufe 5
# erreicht `level` nie (abgeleitetes Farblevel 5 -> 4), die Leiter entfaellt
# fuer den Lagebericht ohnehin (`_is_eaws`).
_LEVEL_POSITION: dict[int, int] = {1: 0, 2: 1, 3: 2, 4: 3}

# CSS-Klassenname je Stufe (Design-Vorlage "Alert · Amtliche Warnung", #1233
# Slice B) -- rein strukturell (Klassen tragen keine eigene Farbe im Mail-
# Output, die Farbe kommt ausschliesslich ueber Inline-Style-Tokens, AC-13).
_LEVEL_CLASS: dict[int, str] = {1: "gruen", 2: "gelb", 3: "orange", 4: "rot"}

# Positions-Wort fuer den `.stufe-hint` (Design-Vorlage, AC-8); Issue #2668:
# Katalogschluessel, Position 0 (ausserhalb der Leiter) -> "niedrigste".
_LEVEL_POSITION_KEYS: dict[int, str] = {
    1: "warnung.stufe.position.niedrigste", 2: "warnung.stufe.position.mittlere",
    3: "warnung.stufe.position.hoechste",
}


def _position_word(pos: int, lang: Lang = "de") -> str:
    return t(_LEVEL_POSITION_KEYS.get(pos, _LEVEL_POSITION_KEYS[1]), lang)


# hazard -> Anzeige-Label, Issue #1216 Spec-Tabelle. Issue #2668: der Text steht
# im Katalog `warnung.gefahr.<hazard>`; `_HAZARD_LABELS` ist die deutsche Sicht
# (Bestandsimporteure, Dedup-Heuristik), `_hazard_word(hazard, lang)` die Anzeige.
_HAZARD_KEYS: tuple[str, ...] = (
    "extreme_heat",
    "thunderstorm",
    "extreme_cold",
    "wind_gust",
    "rain",
    "snow",
    "avalanche",
    "black_ice",
    "access_ban",
    # Adversary F004 (HIGH, #1239 Nachzug Runde 2): "wildfire_risk" (Quelle
    # meteo_forets.py, Label "Waldbrand-Gefahr — Stufe N") fehlte hier -- ohne
    # Mapping fiel `_hazard_display` auf den ROHEN Quell-Label zurueck,
    # INKLUSIVE "— Stufe N". Das war die Wurzelursache aller vier
    # Doppel-Stufe-Symptome (Standalone-Titel, Betreff, embedded Detail-Banner,
    # Compare-Aggregat-Banner) -- die vier Anzeige-Stellen waren nur Symptome
    # dieser einen fehlenden Zeile.
    "wildfire_risk",
    # Issue #1427 S1: MeteoAlarm-Typen 11/12/13 (flood/flooding/rain-flood)
    # bzw. DPC Idrogeo/Idraulico -- Hochwasser- und Erdrutschwarnungen.
    "flood",
    # Issue #1441 (ADR-0089): amtlicher Lawinen-Lagebericht (EAWS 1-5), neben
    # der MeteoAlarm-Lawinenwarnung "avalanche" (Awareness 1-4).
    "avalanche_bulletin",
)
_HAZARD_LABELS: dict[str, str] = {h: t(f"warnung.gefahr.{h}", "de") for h in _HAZARD_KEYS}


def _hazard_word(hazard: str, lang: Lang = "de") -> str | None:
    """Typ-Wort der Gefahrenart in ``lang``; ``None`` fuer unbekannte Gefahrenarten."""
    return t(f"warnung.gefahr.{hazard}", lang) if hazard in _HAZARD_LABELS else None

# hazard -> (Anzeige, SMS-Kuerzel). Issue #1318 Abschnitt 1b: die Anzeige-Labels
# bleiben deutsch, das SMS-Kuerzel kommt aus dem EINZIGEN Katalog
# `output/tokens/hazard_symbols.py` — dieselbe Gefahr darf in der Trip-Briefing-
# SMS und in der Standalone-Warn-SMS nicht zwei verschiedene Codes tragen.
_HAZARD_DISPLAY: dict[str, tuple[str, str]] = {
    hazard: (label, HAZARD_SMS_SYMBOLS[hazard])
    for hazard, label in _HAZARD_LABELS.items()
}

_DE_WEEKDAYS = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

# Issue #1216: source-Kennung -> Anzeigename der amtlichen Quelle. Ersetzt das
# frueher in notification_service.py hartkodierte "GeoSphere Austria" fuer ALLE
# Quellen (Bug: Vigilance-/DWD-Warnungen zeigten falschen Absender).
_SOURCE_LABELS: dict[str, str] = {
    "geosphere_warn": "GeoSphere Austria",
    "geosphere": "GeoSphere Austria",
    "meteofrance_vigilance": "Météo-France",
    "vigilance": "Météo-France",
    "dwd": "DWD",
    "dwd_warn": "DWD",
    # MeteoAlarm-Feed feeds.meteoalarm.org (Österreich, Italien, Deutschland;
    # Issue #1445, EDR-Weg mit #2266 zurückgebaut).
    "meteoalarm": "MeteoAlarm",
    # Italienischer Zivilschutz, additive Quelle fuer Gewitter/Hochwasser/
    # Erdrutsch (services/official_alerts/dpc.py, Issue #1427 S2).
    "dpc": "Protezione Civile (DPC)",
    # Issue #1441: Lawinen-Lagebericht je Tabellenzeile (avalanche_report.py,
    # `AVALANCHE_REGION_TABLE`); Namensnennung ist Lizenzpflicht (CC BY 4.0).
    "avalanche_report:at-07": "Lawinenwarndienst Tirol, avalanche.report",
    "avalanche_report:it-32-bz": "Lawinenwarndienst Südtirol, avalanche.report",
    "avalanche_report:it-32-tn": "Lawinenwarndienst Trentino, avalanche.report",
    "avalanche_report:at-02": "Lawinenwarndienst Kärnten, avalanche.report",
    # Issue #1441 S2: Registry-Namen (Melde-Gedaechtnis `source`) -- eine reine
    # Entwarnungs-Mail nennt die Quelle ueber diesen Namen.
    "meteoalarm_feed": "MeteoAlarm",
    # Issue #1441 S3 (Antrag #7): SLF -- Registry-Name UND jede Region
    # `slf_bulletin:CH-xxxx` (Aufloesung ueber den Praefix, `_PREFIX_LABELS`).
    "slf_bulletin": "WSL-Institut für Schnee- und Lawinenforschung SLF",
}
# Issue #2668: Quellen mit beschreibendem Zusatz stehen im Katalog (in ``lang``);
# Behoerdennamen oben bleiben in jeder Sprache.
_SOURCE_KEYS: dict[str, str] = {
    # Waldbrand-Gefahrenstufen von Météo-France (services/official_alerts/meteo_forets.py).
    "meteo_forets": "warnung.quelle.waldbrand",
    # Präfektur-Zugangssperren einzelner Wander-Massive bei akuter Waldbrandgefahr
    # (services/official_alerts/massif_closure.py, Quelle risque-prevention-incendie.fr).
    "massif_closure": "warnung.quelle.zugangssperre",
    # Issue #1441 S2: Registry-Name der Lawinenwarndienste (reine Entwarnungs-Mail).
    "avalanche_report": "warnung.quelle.lawinendienste",
}
# Quellen, deren Regions-Kennungen ueber den Praefix vor dem ersten ":" aufgeloest werden.
_PREFIX_LABELS: frozenset[str] = frozenset({"slf_bulletin"})
# Issue #1441 S3 (Antrag #7, Auflage): Hinweis auf die Massgeblichkeit des
# Originalberichts -- nur Langform (Mail, Telegram), nie SMS/Kurzform.
_AUTHORITY_NOTES: dict[str, str] = {
    "slf_bulletin": "warnung.hinweis.massgeblich_slf",
}

# Issue #1441: EAWS-Woerter (`warnung.eaws.1`-`5`) und Lawinenprobleme -- Wortlaut
# des Warndienstes, nur Daten, keine Handlungsempfehlung. Unbekannter Code -> der
# Code selbst. Issue #2668: alle Woerter im Katalog.
_EAWS_LEVELS: frozenset[int] = frozenset({1, 2, 3, 4, 5})
_AVALANCHE_PROBLEMS: frozenset[str] = frozenset({
    "new_snow", "wind_slab", "persistent_weak_layers", "wet_snow", "gliding_snow", "cornices",
    "no_distinct_avalanche_problem", "favourable_situation",
})
_ELEVATION_DIRECTIONS: frozenset[str] = frozenset({"above", "below"})
_TIMES_OF_DAY: frozenset[str] = frozenset({"earlier", "later"})
# Waldgrenze ist ein Datenwert des Parsers (`caaml.elevation_from_problems`).
_TREELINE = "Waldgrenze"
# Issue #2668: Sprachen mit Namen im Katalog (Quelltext-Hinweis); sonst der Code.
_SPRACH_CODES: frozenset[str] = frozenset({"fr", "it", "sl", "hr", "es", "de", "en"})


def _is_eaws(alert: "OfficialAlert") -> bool:
    """Lagebericht-Gefahrenart: eigene Skala, keine Awareness-Leiter (ADR-0089)."""
    return alert.hazard == "avalanche_bulletin"


def _rank(alert: "OfficialAlert") -> int:
    """Originalstufe, falls gesetzt, sonst `level` -- nur innerhalb einer Gefahrenart."""
    from services.official_alerts.models import comparable_level

    return comparable_level(alert)


def avalanche_bulletin_text(alert: "OfficialAlert", *, lang: Lang = "de") -> str:
    """Zentraler Text des Lageberichts, z. B. "Lawinenstufe 4 (groß) oberhalb
    Waldgrenze · Triebschnee" (Stufe, Hoehe, Tageszeit, Probleme -- woertlich)."""
    level = _rank(alert)
    # Issue #1441 S3: amtliche Feinstufe ("3-"/"3+") nur in der Langform.
    stufe = f"{level}{alert.level_modifier or ''}"
    if level in _EAWS_LEVELS:
        text = t("warnung.lawine.stufe", lang, n=stufe, wort=t(f"warnung.eaws.{level}", lang))
    else:
        text = f"{t('warnung.gefahr.avalanche_bulletin', lang)} {stufe}"
    if alert.elevation_value and alert.elevation_direction in _ELEVATION_DIRECTIONS:
        wert = (t("warnung.hoehe.waldgrenze", lang) if alert.elevation_value == _TREELINE
                else f"{alert.elevation_value} m")
        text += f" {t(f'warnung.hoehe.{alert.elevation_direction}', lang)} {wert}"
    if alert.time_of_day in _TIMES_OF_DAY:
        text += f" ({t(f'warnung.tageszeit.{alert.time_of_day}', lang)})"
    if alert.problems:
        text += " · " + ", ".join(
            t(f"warnung.problem.{c}", lang) if c in _AVALANCHE_PROBLEMS else c for c in alert.problems
        )
    return text


def _alert_text(alert: "OfficialAlert", lang: Lang = "de") -> str:
    """Badge-/Plain-Text: Lagebericht ueber den zentralen Helfer, sonst `label`.
    Issue #2668: ausser Deutsch der Anzeige-Titel (`label` ist deutsche Kennung)."""
    if _is_eaws(alert):
        return avalanche_bulletin_text(alert, lang=lang)
    return alert.label if lang == "de" else _display_label(alert, lang=lang)


def official_alert_source_label(source: str | None, *, lang: Lang = "de") -> str:
    """source-Kennung -> menschenlesbarer Anzeigename der amtlichen Quelle
    (Issue #1216 AC-7). Exakte Treffer zuerst, dann Substring-Heuristik fuer
    Varianten (`geosphere_*`, `*vigilance*`, `dwd_*`). Unbekannte Quelle ->
    der rohe `source`-String (nie ein falscher hartkodierter Fremd-Absender).
    Issue #2668: beschreibende Zusaetze in ``lang``, Behoerdennamen bleiben."""
    if not source:
        return t("warnung.quelle.amtlich", lang)
    key = source.lower()
    if key in _SOURCE_KEYS:
        return t(_SOURCE_KEYS[key], lang)
    if key in _SOURCE_LABELS:
        return _SOURCE_LABELS[key]
    prefix = key.split(":", 1)[0]
    if prefix in _PREFIX_LABELS:
        return _SOURCE_LABELS[prefix]
    if "geosphere" in key:
        return "GeoSphere Austria"
    if "vigilance" in key or "meteofrance" in key:
        return "Météo-France"
    if "dwd" in key:
        return "DWD"
    return source


def _sprachname(code: str, lang: Lang) -> str:
    return t(f"warnung.sprache.{code}", lang) if code in _SPRACH_CODES else code.upper()


def official_alert_authority_notes(alerts: "list[OfficialAlert]", *, lang: Lang = "de") -> list[str]:
    """Massgeblichkeits-Saetze der beteiligten Quellen (Issue #1441 S3),
    je Quelle einmal, in Reihenfolge der Warnungen.

    Issue #2668: zusaetzlich der Hinweis auf die Quellsprache, wenn der
    ANGEZEIGTE Titel Behoerdentext einer anderen Sprache ist (nicht das
    Katalog-Typ-Wort). Deutsch bleibt byte-gleich: `_display_parts` meldet fuer
    Deutsch nie eine Quellsprache. Nur Langform, nie SMS."""
    keys = (_AUTHORITY_NOTES.get(str(a.source or "").split(":", 1)[0]) for a in alerts)
    notes = [t(k, lang) for k in keys if k]
    for a in alerts:
        code = _display_parts(a, lang)[1]
        if code and code != lang:
            notes.append(t("warnung.hinweis.quelltext_sprache", lang, sprache=_sprachname(code, lang)))
    return list(dict.fromkeys(notes))


@dataclass(frozen=True)
class OfficialAlertNotice:
    """Kontext-agnostisches Praesentations-DTO (Issue #1216): Trip UND
    Ortsvergleich fuellen dasselbe DTO, die vier Renderer unten kennen weder
    Trip- noch Compare-Spezifika."""
    alert: "OfficialAlert"
    scope_label: str
    sms_scope: str
    affected_chips: list[str]
    free_chips: list[str]
    # Issue #1238/#1239 (AC-12/AC-15/AC-17): explizite Kontext-Kennung statt
    # Raten am Chip-Text. "route" = Trip-Segmente (Chips = Streckenabschnitte,
    # Feld-Label "Route:"), "locations" = Ortsvergleich (Chips = Ortsnamen,
    # Feld-Label "Orte:"). Default "route" -> Bestandsaufrufer unveraendert.
    scope_kind: str = "route"
    # Issue #1239 (AC-15 Nachzug, PO-Entscheidung): Gesamtzahl der verglichenen
    # Orte bzw. Trip-Segmente -- traegt die Information "fast alle betroffen"
    # ("7 von 8 Orten"), die eine reine Anzahl ("7 Orte") nicht hat. Von den
    # Buildern gesetzt (`build_compare_official_alert_notices` kennt
    # `all_location_ids`, `build_official_alert_notices` kennt
    # `_trip_total_segment_ids`). `None` (Default) -> Bestandsaufrufer/Tests ohne
    # dieses Feld fallen auf die reine Anzahl zurueck.
    scope_total: int | None = None
    # Adversary F009 (#1239 Nachzug Runde 5): identitaets-basierter Umfang --
    # die sortierte ID-Menge der betroffenen Orte (Compare) bzw. Segmente
    # (Trip), NICHT die Anzeige-Namen. `_uniform_scope` vergleicht damit statt
    # mit `scope_label`: zwei VERSCHIEDENE Orte mit GLEICHEM Anzeigenamen (zwei
    # "Hütte") duerfen nicht faelschlich als "derselbe Umfang" durchgehen --
    # exakt die Kollisions-Regel, die schon `build_compare_official_alert_
    # notices` fuer die Scope-Berechnung selbst ueber Orts-IDs statt Namen
    # durchsetzt (#1216 Slice 2a F006). Leeres Tuple (Default) -> Bestands-
    # aufrufer/Tests ohne dieses Feld fallen auf den Namensvergleich zurueck.
    scope_ids: tuple[str, ...] = ()
    # Adversary F013 (#1239 Nachzug Runde 7, HIGH): AGGREGIERTE Regionen aller
    # gebuendelten Mitglieder (dedupliziert, Reihenfolge = erstes Auftreten),
    # NICHT nur `alert.region_label` des Repraesentanten. Von den Buildern aus
    # dem dritten `_bundle_by_hazard_level`-Rueckgabewert gesetzt. Leeres Tuple
    # (Default) -> `_standalone_src_value` faellt auf `alert.region_label`
    # zurueck (Alt-Aufrufer/handgebaute Test-Notices ohne dieses Feld,
    # Bestandsverhalten unveraendert).
    regions: tuple[str, ...] = ()
    # Issue #2122: additiv, optional, Muster `AlertEvent.stage_number` (o.).
    # Etappen-Nummer des Tages, dem der TATSAECHLICH verwendete rollierende
    # Anker entstammt (`build_official_alert_notices`). Der Compare-Builder
    # (`build_compare_official_alert_notices`) setzt sie nie (AC-9-Muster).
    stage_number: int | None = None


def render_official_alerts_html(
    entries: list[tuple[str, list["OfficialAlert"]]],
    *,
    segment_refs: dict | None = None,
    lang: Lang = "de",
) -> str:
    """Badges fuer amtliche Warnungen (div/span, kein <table>).

    Amtstreue 4-Stufen-Skala (Issue #1056 v2.0): die Rand-Farbe folgt
    ausschliesslich `alert.level` (1=G_SUCCESS, 2=G_ALERT_L2, 3=G_ALERT_L3,
    4+=G_ALERT_L4). Gilt gleichermassen fuer Trip-Briefing- UND Compare-Pfad
    (ersetzt die vormals hazard-severity-basierte Compare-Faerbung aus
    Issue #1134). Entries ohne Warnung liefern keinen Badge; insgesamt keine
    Warnungen -> leerer String.

    Ist der Praefix (`label`) identisch mit `alert.label` (z.B. Massiv-Sperren,
    die kein eigenstaendiges `region_label` setzen und daher ueber
    `collect_trip_alert_entries()` auf `alert.label` zurueckfallen), wird der
    Praefix-Span weggelassen statt das Label zu wiederholen (F002).

    Lazy import (statt Modul-Top): bricht einen Import-Zirkel mit dem
    `email`-Paket-`__init__.py`, das seinerseits `official_alerts` importiert
    (Issue #1087 F001).

    `segment_refs` (Issue #1217, optional, keyword-only): `id(alert) ->
    formatierter Segment-Bezug`-Mapping. Wird ein Alert-Objekt darin
    gefunden, haengt der Badge `" — {ref}"` an das Label an. Ohne
    `segment_refs` (Default, Compare-Pfad) bleibt das erzeugte HTML
    byte-identisch zum bisherigen Verhalten (AC-Byte-Gleichheit #1087).
    """
    from output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK, G_PAPER, G_SUCCESS,
    )

    _level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}

    badges = []
    for label, alerts in entries:
        for alert in alerts:
            color = _level_colors.get(alert.level, G_ALERT_L4)
            alert_label = _html.escape(_alert_text(alert, lang))
            prefix_html = ""
            if label and label != alert.label:
                name = _html.escape(label)
                prefix_html = f'<span style="font-weight:600;">{name}:</span> '
            seg_suffix = ""
            if segment_refs:
                ref = segment_refs.get(id(alert))
                if ref:
                    seg_suffix = f' — {_html.escape(ref)}'
            # Issue #1245 (AC-6/AC-7, Adversary F002): datumsbehaftetes Format
            # (`_format_validity`) statt des wochentag/stunden-only
            # SMS-Kurzformats (`_tag_time`) -- zwei Perioden mit gleichem
            # Wochentag+Stunde, aber unterschiedlichem Kalenderdatum (z.B.
            # exakt 7 Tage auseinander), waeren mit `_tag_time` byte-identisch
            # gerendert worden. Nur bei vorhandenem Zeitraum -- kein
            # "unbekannt"-Platzhalter (AC-7).
            time_suffix = ""
            if alert.valid_from and alert.valid_to:
                time_suffix = f" · {_html.escape(_format_validity(alert, lang=lang))}"
            badges.append(
                f'<div style="background:{G_PAPER};border-left:4px solid {color};'
                f'padding:8px 16px;margin:8px 20px;border-radius:4px;'
                f'font-family:{FONT_UI};font-size:13px;color:{G_INK};">'
                f'{prefix_html}'
                f'<span>{alert_label}{seg_suffix}{time_suffix}</span></div>'
            )
    return "".join(badges)


def render_official_alerts_plain(
    entries: list[tuple[str, list["OfficialAlert"]]], *, lang: Lang = "de",
) -> list[str]:
    """Reproduziert das alte `comparison.py`-Plain-Format exakt: eine Zeile
    je Alert, "Amtliche Warnung: {label}" — der Aufrufer haengt Ortsnamen
    bzw. Praefixe (z.B. "   ⚠️ ") selbst davor.

    Issue #1245 (AC-6/AC-7, Adversary F002): bei vorhandenem Zeitraum haengt
    die Zeile einen datumsbehafteten Zusatz " ({_format_validity})" an --
    NICHT das wochentag/stunden-only SMS-Kurzformat `_tag_time`, das zwei
    exakt 7 Tage auseinanderliegende Perioden (gleicher Wochentag+Stunde)
    byte-identisch gerendert haette. Ohne Zeitraum bleibt die Zeile
    byte-stabil zum bisherigen Verhalten (kein "unbekannt"-Platzhalter)."""
    lines: list[str] = []
    for _label, alerts in entries:
        for alert in alerts:
            suffix = ""
            if alert.valid_from and alert.valid_to:
                suffix = f" ({_format_validity(alert, lang=lang)})"
            lines.append(f"{t('mail.herkunft.amtliche_warnung', lang)}: {_alert_text(alert, lang)}{suffix}")
    return lines


def dedupe_official_alerts(
    tagged_alerts: list[tuple["OfficialAlert", list[str]]],
) -> list[tuple["OfficialAlert", list[str]]]:
    """Issue #1172/#1200/#1217/#1218: kollabiert Warnungen nach einer
    NAMESPACED Identitaet + `hazard`. Identitaets-Praezedenz: (1) `dedup_id`
    (stabile, stufen-unabhaengige Kennung, z.B. Massiv-ID -- Massiv-Sperren
    setzen dies ueber alle Eskalationsstufen konstant, F001), (2)
    `region_label`, (3) `label` (volles Label, unveraendert -- keine
    Textzerlegung). Die drei Faelle sind per Namespace-Tag
    ("id"/"region"/"label") strikt getrennt -- ein zufaellig gleicher String
    zwischen `region_label` einer Warnung und `label` einer anderen kann
    NICHT kollabieren (F002). Behaelt je Gruppe den Repraesentanten mit dem
    HOECHSTEN `level` (bei Gleichstand: erstes Vorkommen). Reihenfolge =
    erstes Auftreten je Gruppe (analog `collect_trip_alert_entries`).
    Vereinigt zusaetzlich die Segment-ID-Mengen aller zur Gruppe gehoerenden
    Rohalerts (Set-Union, dedupliziert, Reihenfolge nicht garantiert).

    BEWUSST NICHT Teil dieser Funktion (Issue #1239 AC-13): die Buendelung
    gleichartiger Warnungen (gleicher hazard + gleiche Stufe, verschiedene Zonen)
    -- die gehoert ausschliesslich in die WARN-SEKTION und laeuft dort als
    zweite Stufe in den Notice-Buildern (`_bundle_by_hazard_level`). Hier waere
    sie falsch: `dedupe_official_alerts` speist auch die Badge-/Streifen-Pfade
    (`collect_trip_alert_entries`, Compare-Pro-Ort-Streifen), und dort MUESSEN
    zwei gleichartige Warnungen mit unterschiedlichem Label sichtbar bleiben
    (#1134 AC-2a: "Massiv Alpha" und "Massiv Beta" sind zwei echte Warnungen,
    keine Dubletten).

    Issue #1245: der Schluessel traegt zusaetzlich `(valid_from, valid_to)` --
    einheitlich in allen drei Namespaces (nicht nur region/label). Zwei
    Perioden derselben Identitaet+Gefahr mit unterschiedlichem Zeitraum
    bleiben dadurch getrennt erhalten (AC-1), waehrend gleicher Zeitraum +
    unterschiedliche Stufe weiterhin zur hoechsten Stufe kollabiert (AC-2).
    Massiv-Sperren (`dedup_id`) tragen strukturell nie einen Zeitraum
    (`massif_closure.py`) -- fuer sie ist der Zusatz folgenlos, vermeidet aber
    Sonderfall-Code (AC-3)."""
    best: dict[tuple, "OfficialAlert"] = {}
    segment_ids_by_key: dict[tuple, set[str]] = {}
    order: list[tuple] = []
    for a, segment_ids in tagged_alerts:
        if a.dedup_id:
            ident = ("id", a.dedup_id)
        elif a.region_label:
            ident = ("region", a.region_label)
        else:
            ident = ("label", a.label)
        key = (ident, a.hazard, a.valid_from, a.valid_to)
        if key not in best:
            best[key] = a
            segment_ids_by_key[key] = set()
            order.append(key)
        elif _rank(a) > _rank(best[key]):
            best[key] = a
        segment_ids_by_key[key].update(segment_ids)
    return [(best[key], sorted(segment_ids_by_key[key])) for key in order]


def _warn_hour(alert: "OfficialAlert", tz: "ZoneInfo") -> Optional[int]:
    """Beginn-Stunde einer amtlichen Warnung in Ortszeit — `None` bei
    ganztaegiger Gueltigkeit oder fehlendem Zeitraum (dann entfaellt `@h`
    ersatzlos). Ganztags-Erkennung wie `_format_validity`."""
    vf, vt = alert.valid_from, alert.valid_to
    if not vf or not vt:
        return None
    # Issue #1402: local_dt() statt rohem .astimezone() -- ein naives
    # valid_from/valid_to (Hausnorm UTC, #1345) wurde sonst als Prozess-
    # Lokalzeit gedeutet.
    from utils.timezone import local_dt

    vf_l, vt_l = local_dt(vf, tz), local_dt(vt, tz)
    if (vf_l.hour, vf_l.minute, vt_l.hour, vt_l.minute) == (0, 0, 23, 59):
        return None
    return vf_l.hour


def official_alerts_to_sms_entries(
    alerts: list["OfficialAlert"], tz: Optional["ZoneInfo"] = None,
    min_level: int = MIN_SMS_LEVEL,
) -> tuple[tuple[str, str, Optional[int]], ...]:
    """Issue #1318/#1332: amtliche Warnungen -> Warn-Block-Tripel (Kuerzel,
    Stufenbuchstabe, Stunde). Dedup ueber die geteilte `dedupe_official_
    alerts()` (kein eigener Dedup-Code), Filter auf Stufe >= `min_level`
    (Vorgabewert `MIN_SMS_LEVEL`, orange), Kuerzel aus dem einzigen Katalog
    `hazard_symbols.py`. Sortierung: Stufe absteigend, bei Gleichstand
    Katalog-Reihenfolge -- deterministisch, unabhaengig von `valid_from`.

    Geteilter Kern von Trip-SMS (`sms_trip.py::_official_alert_entries`, duenner
    Wrapper) UND Compare-SMS (`comparison.py::render_compare_sms`) -- kein
    zweiter Kuerzel-Katalog, keine abweichende Filterlogik (#1332 AC-4).

    `min_level` (#1461 S3b-2a): Trip-Pfade uebergeben die per Kanal
    eingestellte Schwelle (`alert_urgency.min_official_level_for_threshold`);
    Compare-Pfade lassen den Parameter weg und bleiben beim Vorgabewert --
    keine Scheibe veraendert Verhalten, das sie nicht besitzt (S3b-2b folgt).

    `tz=None` (Compare-Orte ohne hinterlegte `SavedLocation.timezone`): der
    Stunden-Teil entfaellt ersatzlos, kein Platzhalter -- analog der
    bestehenden Trip-Konvention bei fehlendem Gueltigkeitszeitraum."""
    tagged = [(alert, []) for alert in alerts]
    rows = []
    for alert, _ in dedupe_official_alerts(tagged):
        if alert.level < min_level:
            continue
        symbol = sms_symbol_for(alert.hazard)
        if alert.hazard in LEVELLESS_HAZARDS:
            entry = (symbol, "", None)
        elif alert.hazard in NUMERIC_LEVEL_HAZARDS:
            # Issue #1441: Originalziffer (`AV4`), keine Stunde (Ausgabezeit 17:00
            # ist keine Warnstunde) -- der Builder rendert ohne Doppelpunkt.
            entry = (symbol, str(_rank(alert)), None)
        else:
            hour = _warn_hour(alert, tz) if tz is not None else None
            entry = (symbol, LEVEL_LETTERS.get(alert.level, "H"), hour)
        rows.append((-alert.level, HAZARD_ORDER.get(alert.hazard, len(HAZARD_ORDER)), entry))
    rows.sort(key=lambda r: (r[0], r[1]))
    return tuple(entry for _lvl, _ord, entry in rows)


def official_alert_state_key(alert: "OfficialAlert") -> str:
    """Issue #1245: Alarm-Trigger-State-Key, der exakt dieselbe Identitaet
    widerspiegelt wie `dedupe_official_alerts` (Praezedenz `dedup_id` >
    `region_label` > `label`, plus `hazard` und Zeitraum). Gemeinsam genutzt
    von `TripAlertService` und `CompareOfficialAlertService`, damit zwei
    echte Perioden derselben Region+Gefahr (AC-4) und zwei verschiedene
    Massiv-Sperren (AC-5) getrennte Zustands-Eintraege erhalten statt sich im
    `last-write-wins`-State zu ueberschreiben."""
    if alert.dedup_id:
        ident = f"id:{alert.dedup_id}"
    elif alert.region_label:
        ident = f"region:{alert.region_label}"
    else:
        ident = f"label:{alert.label}"
    vf = alert.valid_from.isoformat() if alert.valid_from else "none"
    vt = alert.valid_to.isoformat() if alert.valid_to else "none"
    return f"official_alert:{ident}:{alert.hazard}:{vf}:{vt}"


def _identity_hazard_prefix(alert: "OfficialAlert") -> str:
    """Issue #1685: Praefix OHNE Zeitraum, gleiche Praezedenz wie
    `official_alert_state_key` (`dedup_id` > `region_label` > `label`).
    Damit lassen sich alle Bestandsschluessel derselben Identitaet+Gefahr per
    `str.startswith` finden, ohne die ISO-Zeitstempel aus dem Schluessel-
    String zu parsen (der Zeitraum wird stattdessen aus dem Eintrags-Wert
    gelesen, s. `official_alert_state_entry`).

    Adversary F003 (#1685 Fix-Loop, LOW, widerlegt): das `:`-Trennzeichen ist
    NICHT maskiert -- theoretisch koennte ein eingebetteter Doppelpunkt in
    `region_label`/`label` (z.B. "Kartitsch:" vs. "Kartitsch" mit Suffix
    "Sued") zwei verschiedene Identitaeten auf denselben Praefix kollabieren
    lassen. Unter realen Quelldaten nicht konstruierbar: der Vermutungsfall
    "Kartitsch" vs. "Kartitsch Sued" traegt vor dem `:`-Trenner ein
    Leerzeichen, das den Praefix-Treffer bereits verhindert -- eine Kollision
    braucht einen eingebetteten Doppelpunkt, der exakt auf einen der festen
    `hazard`-Werte trifft."""
    if alert.dedup_id:
        ident = f"id:{alert.dedup_id}"
    elif alert.region_label:
        ident = f"region:{alert.region_label}"
    else:
        ident = f"label:{alert.label}"
    return f"official_alert:{ident}:{alert.hazard}:"


def official_alert_revision_verdict(
    alert: "OfficialAlert", state: dict, now: "datetime | None" = None,
) -> tuple[bool, Optional[str], Optional[dict]]:
    """Issue #1685: Melde-Entscheidung fuer eine amtliche Warnung, die eine
    reine Fenster-Revision einer bereits gemeldeten Warnung derselben
    Identitaet+Gefahr sein kann (PO-Entscheidung 2026-08-10).

    Liefert `(should_report, stale_key, merged_entry)`.
    - `should_report=True`: melden -- entweder der klassische exakte
      Schluessel-Treffer (Ist-Verhalten #1245) oder eine Eskalation/
      Vorverlegung >=2h innerhalb einer echten Ueberlappung. `stale_key` und
      `merged_entry` sind dann `None`.
    - `should_report=False` mit gesetztem `merged_entry`: stille Revision --
      der Aufrufer MUSS `stale_key` aus dem State entfernen, `merged_entry`
      unter dem NEUEN Schluessel (`official_alert_state_key(alert)`)
      ablegen und sofort persistieren (`state_svc.save`).

    Fail-soft: fehlt `alert.valid_from`/`valid_to`, oder traegt kein
    Bestandseintrag der gleichen Identitaet+Gefahr eigene `valid_from`/
    `valid_to`-Felder (Alt-Eintrag vor diesem Fix), entscheidet ausschliesslich
    der exakte Schluesseltreffer -- wie vor dieser Spec, kein Interval-
    Vergleich.

    Adversary F001 (#1685 Fix-Loop, CRITICAL): manche Quellen liefern naive
    (tz-lose) `valid_from`/`valid_to` (vigilance/meteoalarm, s.
    `services.official_alerts.base._as_aware_utc`). Ein Vergleich naiv-vs-
    aware wirft sonst `TypeError` -- und der Aufrufer `check_official_alert_
    triggers` faengt das NICHT ab, sodass der Trip fuer den Lauf ALLE amtlichen
    Warnungen verliert. Deshalb werden hier ALLE verglichenen Zeitpunkte --
    Kandidat UND `alert` selbst -- vor jedem Vergleich normalisiert, und der
    Vergleich steht im selben geschuetzten Block wie das Parsen.

    Issue #1657 (PO-Entscheidung 2026-08-17): zwei Praezisierungen.
    (1) Beruehrung zaehlt als Ueberlappung -- ein Fenster, das exakt dort
    beginnt, wo das andere endet, ist dieselbe durchgehende Gefahr in
    stundenfeiner Ausgabe. Eine echte Luecke (und sei sie eine Sekunde)
    bleibt eine eigenstaendige Warnung.
    (2) Umschliesst das neue Fenster den gewaehlten Kandidaten vollstaendig,
    ist das ein reiner Granularitaetswechsel und keine Vorverlegung -- die
    >=2h-Vorverlegungs-Ausnahme entfaellt dann. Die Eskalations-Bedingung
    bleibt davon unberuehrt. Ein 6h-Frische-Guard auf `reported_at` des
    Kandidaten verhindert, dass ein alter, nie bereinigter State-Eintrag
    (`AlertStateService.reset()` behaelt `official_alert:`-Eintraege ueber
    den Briefing-Reset hinweg, #1614) eine echte neue Warnung verschluckt.
    Referenzzeit `now` ist injizierbar (Default `datetime.now(timezone.utc)`),
    damit die 6h-Grenze exakt und nicht gegen die Laufzeituhr geprueft wird --
    beide Aufrufstellen bleiben dadurch unveraendert."""
    from services.official_alerts.base import _as_aware_utc

    key = official_alert_state_key(alert)
    prev = state.get(key)

    def _exact_match_verdict() -> tuple[bool, Optional[str], Optional[dict]]:
        should_report = prev is None or _rank(alert) > prev.get("last_reported_value", 0)
        return should_report, None, None

    if alert.valid_from is None or alert.valid_to is None:
        return _exact_match_verdict()

    alert_vf = _as_aware_utc(alert.valid_from)
    alert_vt = _as_aware_utc(alert.valid_to)

    prefix = _identity_hazard_prefix(alert)
    candidates: list[tuple[str, dict, datetime, datetime]] = []
    for cand_key, entry in state.items():
        if not cand_key.startswith(prefix):
            continue
        vf_raw, vt_raw = entry.get("valid_from"), entry.get("valid_to")
        if vf_raw is None or vt_raw is None:
            continue
        try:
            cand_vf = _as_aware_utc(datetime.fromisoformat(vf_raw))
            cand_vt = _as_aware_utc(datetime.fromisoformat(vt_raw))
            # Issue #1657 AC-1: `<=` statt `<` -- Beruehrung zaehlt als
            # Ueberlappung. Eine echte Luecke faellt weiterhin heraus (AC-2).
            if alert_vf <= cand_vt and cand_vf <= alert_vt:
                candidates.append((cand_key, entry, cand_vf, cand_vt))
        except (TypeError, ValueError):
            continue

    if not candidates:
        return _exact_match_verdict()

    stale_key, kandidat, kandidat_vf, kandidat_vt = max(
        candidates,
        key=lambda c: (c[1].get("last_reported_value", 0), c[1].get("reported_at") or ""),
    )
    kandidat_level = kandidat.get("last_reported_value", 0)

    # Issue #1657 AC-3/AC-4: Containment = das neue Fenster umschliesst den
    # Kandidaten vollstaendig. Dann ist der frueher liegende Beginn eine
    # Granularitaets-Aenderung, keine Vorverlegung. Der Guard laesst das nur
    # fuer einen FRISCHEN Kandidaten gelten; ein Eintrag ohne verwertbaren
    # `reported_at` gilt bewusst als NICHT frisch, damit im Zweifel gemeldet
    # statt verschluckt wird. Das Parsen steht im selben geschuetzten Block
    # wie die Normalisierung (Adversary F001: naiv-vs-aware wirft sonst
    # `TypeError`, den der Aufrufer nicht abfaengt).
    is_containment = alert_vf <= kandidat_vf and alert_vt >= kandidat_vt
    kandidat_frisch = False
    if is_containment:
        try:
            ref_now = _as_aware_utc(now) if now is not None else datetime.now(timezone.utc)
            reported_raw = kandidat.get("reported_at") or ""
            kandidat_reported = _as_aware_utc(datetime.fromisoformat(reported_raw))
            kandidat_frisch = (ref_now - kandidat_reported) <= timedelta(hours=6)
        except (TypeError, ValueError):
            kandidat_frisch = False

    # Der Guard unterdrueckt AUSSCHLIESSLICH die Containment-Ausnahme: nur ein
    # FRISCHES Containment entschaerft die Vorverlegung. Ein veralteter
    # Kandidat faellt damit auf das unveraenderte #1685-Verhalten zurueck
    # (Vorverlegung >=2h meldet). Der Guard darf NICHT zusaetzlich stille
    # Faelle umdrehen, die auch ohne Containment still waeren -- sonst wuerde
    # z.B. "nur verlaengert" (#1685 AC-2, gleicher Beginn, spaeteres Ende) mit
    # altem `reported_at` faelschlich erneut melden.
    # Issue #1441: Originalstufe (4 -> 5 eskaliert, abgeleitetes level bliebe 4).
    escalated = _rank(alert) > kandidat_level
    containment_greift = is_containment and kandidat_frisch
    vorverlegung = (not containment_greift) and (kandidat_vf - alert_vf) >= timedelta(hours=2)
    if escalated or vorverlegung:
        return True, None, None

    merged_entry = {
        # Issue #1441 S2: Herkunft, Ort und alte Stufe reisen mit -- sonst
        # saehe jede fortgeschriebene Warnung wie ein Alt-Eintrag aus und
        # bekaeme nie eine Entwarnung. `absent_since` faellt weg: die Warnung
        # ist gerade wieder da.
        **{f: kandidat[f] for f in ("source", "scope", "level") if f in kandidat},
        "last_reported_value": max(kandidat_level, float(_rank(alert))),
        # Adversary F002 (#1685 Fix-Loop, HIGH): `.get(..., "")` griff nur bei
        # fehlendem Schluessel, nicht bei explizit gespeichertem `None` -- ein
        # zweiter gleichrangiger Kandidat mit `reported_at: null` liess den
        # Tie-Break oben `None` mit `str` vergleichen (TypeError). Ausserdem
        # darf nie wieder ein `None` ins Melde-Gedaechtnis geschrieben werden.
        # Adversary F007 (#1685 Fix-Loop Runde 2, MEDIUM): der Ersatzwert darf
        # NICHT `datetime.now(...)` sein -- `reported_at` ist genau das
        # Tie-Break-Kriterium oben (Zeile 519, "bei Gleichstand: spaetester
        # reported_at gewinnt"). Ein erfundenes "jetzt" gewinnt damit
        # systematisch gegen echte, aeltere Zeitstempel und verzerrt kuenftige
        # Tie-Breaks. `""` ist konsistent mit der Lese-Normalisierung
        # `.get("reported_at") or ""` in Zeile 519 und verliert -- statt zu
        # gewinnen.
        "reported_at": kandidat.get("reported_at") or "",
        "valid_from": alert.valid_from.isoformat(),
        "valid_to": alert.valid_to.isoformat(),
    }
    return False, stale_key, merged_entry


def official_alert_state_entry(
    alert: "OfficialAlert", reported_at_iso: str, *,
    source: str | None = None, scope: list | None = None,
) -> dict:
    """Issue #1685: Schema-Builder fuer Melde-Gedaechtnis-Eintraege -- ersetzt
    die bisher zwei unabhaengig duplizierten Inline-Dicts in
    `record_official_alerts_reported` und `CompareOfficialAlertService.
    _record_state`. Neu ggue. dem Ist-Zustand: `valid_from`/`valid_to`, damit
    `official_alert_revision_verdict` spaeter echte Ueberlappung pruefen kann.

    Issue #1441 S2: zusaetzlich `source` (meldende Quelle, Registry-Name falls
    bekannt), `scope` (Orte der Meldung) und `level` (Dringlichkeits-Skala)
    -- Grundlage der Entwarnung. Gelesen wird nur per `.get()`."""
    entry = {
        "last_reported_value": float(_rank(alert)),
        "reported_at": reported_at_iso,
        "valid_from": alert.valid_from.isoformat() if alert.valid_from else None,
        "valid_to": alert.valid_to.isoformat() if alert.valid_to else None,
        "source": source or alert.source,
        "level": int(alert.level),
    }
    if scope:
        entry["scope"] = list(scope)
    return entry


def _bundle_by_hazard_level(
    deduped: list[tuple["OfficialAlert", list[str]]],
) -> list[tuple["OfficialAlert", list[str], tuple[str, ...]]]:
    """Zweite Verdichtungs-Stufe der WARN-SEKTION (Issue #1239 AC-13), NACH der
    Identitaets-Dedup (`dedupe_official_alerts`): buendelt Warnungen mit gleichem
    `hazard` UND gleicher Stufe zu EINER Warnung mit vereinigter Segment-/Orts-
    Liste (zwei Waldbrand-Stufe-3-Warnungen in Zone Ouest und Zone Est werden zu
    einer Warnung "Waldbrand-Gefahr" mit beiden Orten).

    GRUNDSATZ (Adversary, dritte Formulierung, F003/F012/F013): ein Buendel-
    Repraesentant darf KEIN angezeigtes Feld allein bestimmen, das sich
    zwischen den Mitgliedern unterscheiden kann. Fuer jedes vom Renderer aus
    dem Repraesentanten gelesene Feld gilt GENAU eine von zwei Kategorien:
    (A) SCHLUESSEL -- das Feld ist Teil des Buendel-Schluessels, folglich bei
    allen Mitgliedern eines Buendels gleich, ODER (B) AGGREGAT -- das Feld darf
    zwischen Mitgliedern variieren und wird ueber ALLE Mitglieder gesammelt
    (dedupliziert, stabile Erstauftritts-Reihenfolge) statt nur vom
    Repraesentanten gelesen. Vollstaendige Einordnung:

    - `hazard` -- (A) SCHLUESSEL (Bündelungskriterium selbst).
    - `level` -- (A) SCHLUESSEL (Bündelungskriterium selbst).
    - `label` -- (A) SCHLUESSEL (Adversary F012, HIGH, Staging-Regression):
      ohne das kollabierten drei verschiedene Massiv-Sperren (Toulon: "Zugang
      eingeschraenkt — Monts Toulonnais", Hyères: "— Corniche Des Maures",
      Draguignan: "— Centre Var"; alle access_ban, Stufe 3, ohne Zeitraum) zu
      EINER Karte unter dem Titel des ERSTEN Massivs -- wer in Hyères steht,
      laese eine Sperre fuer "Monts Toulonnais" und erfuehre nichts von der ihn
      tatsaechlich betreffenden Corniche-des-Maures-Sperre. Der #1239-Fall
      (zwei Waldbrand-Warnungen "Waldbrand-Gefahr — Stufe 3" aus zwei Zonen)
      hat bei beiden Warnungen DASSELBE Label -- buendelt weiterhin (AC-13).
    - `valid_from`/`valid_to` -- (A) SCHLUESSEL (Adversary F003, HIGH,
      Datenverlust): sonst wirft die Buendelung den Gueltigkeitszeitraum aller
      NICHT-repraesentativen Alerts weg. Der AC-13-Fall hat `None`/`None` bei
      beiden -- buendelt weiterhin.
    - `region_label` -- (B) AGGREGAT (Adversary F013, HIGH, Staging-Regression
      Runde 7): region_label DARF variieren -- Region in den Schluessel zu
      nehmen wuerde exakt den #1239-Bündelungsfall (zwei Waldbrand-Zonen -> EINE
      Karte) wieder aufloesen. Stattdessen sammelt `_bundle_by_hazard_level`
      jetzt die Regionen ALLER Mitglieder (dedupliziert, Reihenfolge = erstes
      Auftreten) als dritten Rueckgabewert; die `.src`-Box nennt ueber
      `OfficialAlertNotice.regions` ALLE gesammelten Regionen statt nur der des
      Repraesentanten ("Météo-France — Var, Bouches-du-Rhône." statt nur "—
      Var." fuer eine Warnung, die tatsaechlich beide Départements abdeckt).
    - `source`/`url` -- werden NICHT pro Warnung gerendert (nur global als
      Mail-Parameter `source_label`/`source_url` an `render_warn_block`) --
      unberuehrt von der Buendelung, keine der beiden Kategorien noetig.
    - `dedup_id` -- speist ausschliesslich die VORGELAGERTE Identitaets-Dedup
      (`dedupe_official_alerts`), wird nirgends direkt gerendert.

    Laeuft NUR in den Notice-Buildern des Standalone-Alarms, nicht in der
    geteilten Dedup: die Badge-/Streifen-Pfade muessen gleichartige Warnungen mit
    unterschiedlichem Label weiter einzeln zeigen (#1134 AC-2a).

    Repraesentant ist das erste Vorkommen (Reihenfolge = erstes Auftreten je
    Buendel). Warnungen desselben Typs mit UNTERSCHIEDLICHER Stufe bleiben
    getrennt (Known Limitation der Spec) und folgen weiter dem Mixed-Level-Pfad
    mit eigenem Eskalations-Meter je Warnung (AC-14 bleibt unberuehrt: die
    Massiv-Eskalation kollabiert bereits in der Identitaets-Dedup davor)."""
    rep: dict[tuple, "OfficialAlert"] = {}
    ids_by_key: dict[tuple, list[str]] = {}
    regions_by_key: dict[tuple, list[str]] = {}
    order: list[tuple] = []
    for a, segment_ids in deduped:
        # Issue #1441: fuer den Lagebericht ist der angezeigte Text (Stufe, Hoehe,
        # Probleme) Schluessel -- sonst bestimmte der Repraesentant ihn allein.
        key = (a.hazard, a.level, _alert_text(a), a.valid_from, a.valid_to)
        if key not in rep:
            rep[key] = a
            ids_by_key[key] = []
            regions_by_key[key] = []
            order.append(key)
        ids_by_key[key].extend(segment_ids)
        if a.region_label and a.region_label not in regions_by_key[key]:
            regions_by_key[key].append(a.region_label)
    return [
        (rep[key], list(dict.fromkeys(ids_by_key[key])), tuple(regions_by_key[key]))
        for key in order
    ]


def render_official_alert_notice_plain(
    alerts: list[tuple["OfficialAlert", list[str]]], tz: "ZoneInfo", *, lang: Lang = "de",
) -> list[str]:
    """Standalone-Alert-Format (Issue #1172/#1200): dedupliziert die Warnungen
    (dedupe_official_alerts) und rendert pro echter Warnung einen Block mit
    Schwere-Wort, Region (inkl. Segment-Bezug, falls vorhanden) und lokalem
    Gueltigkeitszeitraum. NICHT identisch mit render_official_alerts_plain()
    (Compare/Briefing bleiben unveraendert).

    Issue #1238 AC-7 (Nachzug): ohne bekannten Gueltigkeitszeitraum entfaellt
    die "Gültig:"-Zeile GANZ, statt "Gültig: unbekannt" zu schreiben -- gilt
    fuer die ganze Mail, nicht nur den HTML-Teil (jede Mail geht multipart
    raus, der Klartext-Teil wird von manchen Clients angezeigt und von den
    eigenen Pruef-Werkzeugen ausgewertet).

    Issue #1402: `tz` ist PFLICHTPARAMETER — der einzige produktive Aufrufer
    (`NotificationService._dispatch_alert_message`) uebergibt immer
    `alert_tz` (selbst Pflichtparameter dort)."""
    from utils.timezone import local_fmt

    fmt = "%a %d.%m. %H:%M"

    lines: list[str] = []
    for a, segment_ids in dedupe_official_alerts(alerts):
        if lines:
            lines.append("")
        # Issue #1222: E-Mail/SMS-Plain-Notice ohne Kreis-Emoji — nur das Wort ([1]).
        # Adversary F002 (warnmail, AC-2): `_display_label` statt des rohen
        # `a.label` -- sonst zeigt der eingebettete Deviation-Alert im Plain-/
        # Telegram-Body das englische Quell-Label ("Orange Thunderstorm
        # Warning") statt des gemappten deutschen Typ-Worts ("Gewitter").
        # `_display_label` bewahrt reichere Labels (access_ban "Zugang
        # gesperrt — {Massiv}", Vigilance "Extreme Hitze") unveraendert --
        # nur ein voellig eigenstaendiges Roh-Label wird durch das Typ-Wort
        # ersetzt (s. `_display_label`-Docstring Fall (d)).
        word = _level_word(a.level, lang)
        titel = _display_label(a, lang=lang)
        # Issue #1441: der Lagebericht traegt seine Stufe im Wortlaut, kein Ampelwort.
        lines.append(titel if _is_eaws(a) else f"{word} — {titel}")
        region = a.region_label or t("warnung.zeit.unbekannt", lang)
        region_line = f"{t('warnung.zeile.region', lang)}: {region}"
        if segment_ids:
            region_line += f" — {format_segment_reference(segment_ids)}"
        lines.append(region_line)
        if a.valid_from and a.valid_to:
            lines.append(
                f"{t('warnung.gueltig', lang)}: {local_fmt(a.valid_from, tz, fmt)} – "
                f"{local_fmt(a.valid_to, tz, fmt)}"
            )
        # sonst: keine "Gültig:"-Zeile (AC-7) -- kein Platzhalter "unbekannt".
    return lines


def collect_trip_alert_entries(
    segments: list["SegmentWeatherData"],
) -> list[tuple[str, list["OfficialAlert"]]]:
    """Dedupe-Helper fuer die Text-Trip-Renderer (plain/compact): sammelt alle
    seg.official_alerts, dedupliziert sie ueber die kanonische Quelle
    `dedupe_official_alerts` ((dedup_id|region_label|label, hazard), hoechste
    Stufe je Gruppe) und liefert EIN (label, [alert])-Paar je entdoppelter
    Warnung. Ersetzt die fruehere Objekt-Gleichheits-Gruppierung, die
    stufen-eskalierende Duplikate (#1217/#1218) durchliess. Segment-IDs werden
    hier bewusst NICHT durchgereicht ([] statt echter IDs) — der Segment-Bezug
    ist dem HTML-Renderer vorbehalten (html.py baut seinen eigenen dedupe-Pfad
    mit segment_refs) und `dedupe_official_alerts` nutzt die Segment-ID-Liste
    ausschliesslich fuer den zweiten Rueckgabewert, den wir hier verwerfen. So
    bleibt die Funktion mit reinen `official_alerts`-Objekten ohne `.segment`
    (z.B. Test-Doubles in test_official_alert_badge_color.py) kompatibel."""
    tagged = [
        (alert, [])
        for seg in segments
        for alert in (getattr(seg, "official_alerts", None) or [])
    ]
    deduped = dedupe_official_alerts(tagged)
    return [(a.region_label or a.label, [a]) for a, _ in deduped]


# ---------------------------------------------------------------------------
# Issue #1216: Format-Fidelity zur Design-Vorlage — vier kontext-agnostische
# Praesentations-Renderer + Aufbau-Helfer fuer den Trip-Standalone-Alarm.
# ---------------------------------------------------------------------------

def _hazard_display(alert: "OfficialAlert", lang: Lang = "de") -> tuple[str, str]:
    """hazard -> (Anzeige, SMS-Kuerzel); unbekannt -> (label, erste 2 ASCII-
    Grossbuchstaben aus hazard). Issue #2668: Anzeige in ``lang``, Kuerzel nie."""
    mapped = _HAZARD_DISPLAY.get(alert.hazard)
    if mapped:
        return _hazard_word(alert.hazard, lang) or mapped[0], mapped[1]
    # Kuerzel-Fallback kommt aus der geteilten Quelle, damit Trip-Briefing-SMS
    # und Standalone-Warn-SMS fuer denselben unbekannten hazard nie divergieren.
    return alert.label, sms_symbol_for(alert.hazard)


# Issue #1238 AC-6: numerische Quell-Stufe am Label-Ende ("Waldbrand-Gefahr —
# Stufe 3"). Wird NUR an der Anzeige-Stelle entfernt (Warn-Titel), nie in der
# Quelle (meteo_forets.py) -- die Quell-Labels speisen auch Dedup/SMS.
_SOURCE_LEVEL_SUFFIX = re.compile(r"\s*[—–-]\s*Stufe\s*\d+\s*$")


def _display_label(alert: "OfficialAlert", *, lang: Lang = "de") -> str:
    """Anzeige-Titel einer Warnung (Issue #1238 AC-4, geteilte Quelle fuer
    Betreff `_typ_tag`, Standalone-Warn-Titel `_standalone_warn_type_html` und
    embedded WarnBlock): der reichere Quell-Label ERSETZT das normalisierte
    Typ-Wort, wenn er es erweitert -- er wird ihm nie vorangestellt.

    Drei Faelle:
    (a)/(b) Detailtreue Ersetzung (F004 #1216): das Typ-Wort steckt im Label
    (Vigilance "Extreme Hitze" enthaelt "Hitze"; access_ban "Zugang gesperrt —
    {Massiv}" beginnt mit "Zugang gesperrt"), ODER das Label traegt den
    Detail-Separator "—" (Massiv-Name), auch wenn die Formulierung vom Typ-Wort
    abweicht ("Zugang eingeschraenkt — {Massiv}") -> Label ERSETZT das Typ-Wort.
    (c) Standardfall (label == Typ-Wort, z.B. GeoSphere "Gewitter"/"Hitze")
    -> exakt das Typ-Wort (AC-5).
    (d) Befund 2 (#1326b, ADR-Bestandsschutz): greift KEINE der beiden
    Ersetz-Heuristiken UND das Label ist trotzdem ungleich dem Typ-Wort (ein
    voellig eigenstaendiges Label ohne Bezug zum normalisierten Typ, z.B. ein
    englisches MeteoAlarm/Vigilance-Roh-Label) -> NUR das deutsche Typ-Wort
    erscheint. Vor #1326b wurde das Roh-Label hier an das Typ-Wort ANGEHAENGT
    ("Gewitter — Orange Thunderstorm Warning") -- diese Verkettung war der Bug
    (doppelte Gefahren-Benennung).

    Adversary F002 (MEDIUM, AC-6): die numerische Quell-Stufe am Label-Ende
    ("— Stufe 3") wird IMMER am Ende entfernt -- an ALLEN drei Anzeige-Orten
    (Standalone-Titel, Betreff via `_typ_tag`, embedded WarnBlock rufen alle
    diese Funktion auf), weil die Stufe dort bereits als Eskalations-Meter/
    Stufenwort in derselben Nachricht steht. NUR hier, am Anzeige-Ort -- nie am
    Roh-Label der Quelle oder am Dedup-Schluessel (Regress-Schutz gegen
    #1172/#1200/#1217/#1218, die beide ausschliesslich `alert.label`
    unveraendert nutzen).

    Issue #2668: ``lang`` waehlt den Titel erst beim Darstellen (Cache ist
    nutzeruebergreifend); Deutsch bleibt die Logik oben, byte-gleich."""
    return _display_parts(alert, lang)[0]


def _label_for_lang(alert: "OfficialAlert", lang: Lang) -> tuple[str, str]:
    """(Text, Sprachcode) des Sprachblocks fuer ``lang`` (Issue #2668): ``en``
    nimmt den en-Block, sonst den de-Block, sonst `label` (Sprache
    `label_lang`); ``de`` nimmt den de-Block, sonst `label`."""
    bloecke = dict(alert.label_by_lang)
    for code in (("en", "de") if lang == "en" else ("de",)):
        if bloecke.get(code):
            return bloecke[code], code
    return alert.label, alert.label_lang


def _display_parts(alert: "OfficialAlert", lang: Lang = "de") -> tuple[str, str]:
    """(Anzeige-Titel, Sprache des darin gezeigten Behoerdentexts oder "").
    Die Sprache speist den Quelltext-Hinweis (`official_alert_authority_notes`)."""
    if _is_eaws(alert):
        return avalanche_bulletin_text(alert, lang=lang), ""  # Issue #1441: Wortlaut statt Leiter
    if lang != "en":
        return _display_label_de(alert), ""
    typ, _sms = _hazard_display(alert, "en")
    text, code = _label_for_lang(alert, "en")
    text = _SOURCE_LEVEL_SUFFIX.sub("", text or "")
    if "—" in text:
        # Behoerdentext bekannter Sprache bleibt wortlich (Hinweis nennt die
        # Sprache); interne deutsche Kennungen ("Zugang gesperrt — Massiv")
        # bekommen das englische Typ-Wort, das Detail ist ein Eigenname.
        if code:
            return text, code
        return f"{typ} — {text.split('—', 1)[1].strip()}", ""
    if code == "en" and typ.lower() in text.lower():
        return text, code
    return typ, ""


def _display_label_de(alert: "OfficialAlert") -> str:
    """Bestandslogik des deutschen Titels (Faelle a-d, s. `_display_label`)."""
    typ, _sms = _hazard_display(alert)
    label = alert.label
    if label == typ or not label:
        display = typ
    elif typ in label or "—" in label:
        display = label
    else:
        # Befund 2 (#1326b): nur das gemappte deutsche Typ-Wort, keine
        # Verkettung mit dem rohen Quell-Label (s. Docstring Fall (d)).
        display = typ
    return _SOURCE_LEVEL_SUFFIX.sub("", display)


def _de_weekday_short(dt: datetime) -> str:
    """DE-Wochentagskuerzel {Mo..So} statt locale-abhaengigem '%a' ('Fri').
    Duenner Wrapper (Issue #2668) bis P9b `trip_alert.py` umstellt."""
    return fmt_weekday(dt, "de")


def _format_validity(
    alert: "OfficialAlert", tz: "ZoneInfo | None" = None, *, lang: Lang = "de",
) -> str:
    """'Fr 10.07. · ganztägig' bzw. 'Sa 11.07. · 15:00–21:00'; fehlende Zeiten
    -> 'unbekannt'. Tagesübergang (F006): 'Fr 10.07. · 22:00 – Sa 11.07. 03:00'
    -- beide Daten erscheinen, damit das Ende nicht vor dem Beginn scheint.
    Issue #2668: Datum ueber `fmt_date` (de 'Fr 10.07.', en 'Fri 10 Jul')."""
    if not alert.valid_from or not alert.valid_to:
        return t("warnung.zeit.unbekannt", lang)
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag_datum = fmt_date(vf, lang)
    if vf.date() != vt.date():
        return f"{tag_datum} · {vf.strftime('%H:%M')} – {fmt_date(vt, lang)} {vt.strftime('%H:%M')}"
    allday = (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59)
    if allday:
        return f"{tag_datum} · {t('warnung.zeit.ganztaegig', lang)}"
    return f"{tag_datum} · {vf.strftime('%H:%M')}–{vt.strftime('%H:%M')}"


def _sort_notices(notices: list["OfficialAlertNotice"]) -> list["OfficialAlertNotice"]:
    """Hoechste Stufe zuerst (level absteigend), bei Gleichstand valid_from aufsteigend."""
    fallback = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        notices,
        key=lambda n: (-n.alert.level, n.alert.valid_from or fallback),
    )


def _typ_tag(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None" = None, *, lang: Lang = "de",
) -> str:
    # Titel-Logik: `_display_label` (geteilte Quelle, #1238 AC-4).
    #
    # `tz` (#1233 Nebenbefund AC-12): der Wochentag MUSS dieselbe tz-aware
    # Quelle nutzen wie `_format_validity` im Body -- sonst zeigt der Betreff
    # bei einem Gueltigkeitsbeginn kurz vor Mitternacht einen anderen Wochentag
    # als der Body (Bug: Betreff "(Sa)" roh-UTC vs. Body "So" lokalisiert).
    display = _display_label(notice.alert, lang=lang)
    if notice.alert.valid_from is None:
        return display
    vf = notice.alert.valid_from.astimezone(tz) if tz else notice.alert.valid_from
    return f"{display} ({fmt_weekday(vf, lang)})"


# Issue #1239 (AC-15/AC-17): ab wie vielen betroffenen Orten die Reichweite als
# Mengenangabe statt als Namensliste erscheint, und wie viele Warnungen Betreff
# und Ueberschrift hoechstens ausschreiben.
_SCOPE_MAX_NAMES = 2
_SUBJECT_MAX_WARNINGS = 2


def _scope_display(notice: "OfficialAlertNotice", lang: Lang = "de") -> str:
    """Reichweite fuer Betreff/Ueberschrift (Issue #1239 AC-15/AC-16/AC-17):
    ab drei betroffenen Orten eine Mengenangabe statt der vollstaendigen
    Namensliste, die den Betreff unlesbar lang macht. Bei 1-2 Orten bleiben die
    Namen; die Sonderfaelle "alle Orte"/"gesamte Route" und der komplette
    Trip-/Segment-Pfad (`scope_kind="route"`) bleiben bit-identisch zum Stand
    vor diesem Fix.

    PO-Entscheidung (Nachzug #1239): mit bekannter Gesamtzahl (`scope_total`,
    von den Buildern gesetzt) lautet die Mengenangabe "N von M Orten" -- das
    traegt die Information "fast alle betroffen", die eine reine Anzahl
    ("N Orte") nicht hat. Ohne `scope_total` (Alt-Aufrufer/Tests ohne dieses
    Feld) faellt sie auf die reine Anzahl zurueck."""
    if notice.scope_kind != "locations":
        return notice.scope_label
    if _full_scope_kind(notice.scope_label):
        return notice.scope_label
    count = len(notice.affected_chips)
    if count > _SCOPE_MAX_NAMES:
        if notice.scope_total:
            return t("vergleich.warn.n_von_m_orten", lang, n=count, gesamt=notice.scope_total)
        return t("warnung.umfang.anzahl_orte", lang, count=count)
    return notice.scope_label


def _full_scope_kind(scope_label: str) -> str:
    """"route"/"orte", wenn `scope_label` der volle Umfang ist (in jeder
    Sprache, Issue #2668: die Notice traegt den Text in Builder-Sprache), sonst ""."""
    for art, key in (("route", "warnung.umfang.gesamte_route"), ("orte", "warnung.umfang.alle_orte")):
        if scope_label in (t(key, "de"), t(key, "en")):
            return art
    return ""


def render_official_alert_subject(
    notices: list["OfficialAlertNotice"], *, prefix: str, tz: "ZoneInfo | None" = None,
    lang: Lang = "de",
) -> str:
    """'[{prefix}] {reichweite} · {Stufe(n)} {Typ (Tag)} + …' — reichweite und
    Stufen-Reihenfolge folgen der fuehrenden (hoechsten) Warnung.

    `tz` (#1233 Nebenbefund AC-12, optional): lokalisiert den Wochentag
    konsistent mit dem Body (`_format_validity`/`render_official_alert_html`).
    Die Versand-Pfade (`notification_service.py`) reichen die tatsaechliche,
    aus den Trip-/Ort-Koordinaten abgeleitete `alert_tz` durch, die auch der
    Body erhaelt -- alle produktiven Aufrufer liefern `tz` also bereits immer
    (Wächter-Test `test_output_timezone_guard.py` prueft das). Issue #1402:
    ohne explizite `tz` faellt der Betreff auf UTC zurueck, NICHT mehr auf
    das geratene Europe/Vienna (#1233) -- eine geratene Zone sieht plausibel
    aus und faellt beim Lesen nicht auf, obwohl sie ebenso falsch sein kann
    wie rohes UTC.

    Adversary F006 (HIGH, Staging-Fund) + Befund 3 (#1248, ADR-Bestandsschutz):
    dieselbe Fehlerklasse wie in Quelle-Box/Headline -- die Reichweite ist nur
    dann die der FUEHRENDEN Warnung (`_scope_display(leading)`), wenn ALLE
    Warnungen denselben Umfang haben (`_uniform_scope`). Sonst wuerde der
    Betreff den Umfang eines einzelnen Hazards faelschlich auf alle
    aufgezaehlten Gefahren-Typen verallgemeinern (Staging-Beispiel: "Toulon,
    Hyères" im Betreff, obwohl eine Warnung ausschliesslich Draguignan
    betraf) -- ein neutraler Platzhalter ("mehrere Orte" bzw. "mehrere
    Segmente" fuer den Trip-Pfad) steht dann an dessen Stelle.

    Befund 3 (#1248): die `_uniform_scope`-Pruefung galt frueher NUR fuer
    `scope_kind="locations"` -- der Route-Pfad (Trip, Default) nahm
    bedingungslos `_scope_display(leading)`, auch wenn die Warnungen
    UNTERSCHIEDLICHE Segmente betrafen (Bug: "Segment 1" im Betreff, obwohl
    eine zweite Warnung nur Segment 3 betraf). Die Pruefung greift jetzt
    unabhaengig von `scope_kind`.

    AC-16 (Bit-Identitaet bei <=2 Orten/Warnungen) bleibt gewahrt: alle
    bisherigen Testfaelle haben einheitlichen Umfang je Notice-Liste, der neue
    Zweig greift dort nie."""
    if tz is None:
        tz = ZoneInfo("UTC")
    ordered = _sort_notices(notices)
    leading = ordered[0]
    uniform = len({n.alert.level for n in ordered}) == 1
    # AC-15: hoechstens zwei Warnungen ausgeschrieben (schwerste zuerst), der
    # Rest als "+N weitere". AC-16: bei <=2 Warnungen bleibt der Betreff
    # bit-identisch (kein Suffix, gleiche Trennzeichen).
    shown = ordered[:_SUBJECT_MAX_WARNINGS]
    omitted = len(ordered) - len(shown)
    more = f" {t('warnung.kopf.weitere', lang, count=omitted)}" if omitted > 0 else ""
    if uniform and not any(_is_eaws(n.alert) for n in ordered):
        word = _level_word(leading.alert.level, lang)
        body = f"{word} " + " + ".join(_typ_tag(n, tz, lang=lang) for n in shown)
    else:
        # Issue #1441: der Lagebericht steht ohne Ampelwort (Stufe im Wortlaut).
        body = " + ".join(
            _typ_tag(n, tz, lang=lang) if _is_eaws(n.alert)
            else f"{_level_word(n.alert.level, lang)} {_typ_tag(n, tz, lang=lang)}"
            for n in shown
        )
    if not _uniform_scope(ordered):
        mehrere = "orte" if leading.scope_kind == "locations" else "segmente"
        scope_text = t(f"warnung.umfang.mehrere_{mehrere}", lang)
    else:
        scope_text = _scope_display(leading, lang)
    return f"[{prefix}] {scope_text} · {body}{more}"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Bestands-Token-Hex -> `rgba(...)` fuer Tint-Hintergruende (Verdict-Pill).
    Nur Token-Farben, nie die Design-Vorlage-Hex (AC-13)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _join_de(items: list[str], lang: Lang = "de") -> str:
    """Aufzaehlung: 'A' / 'A und B' / 'A, B und C' (Spec Slice B Punkt 2,
    dedupliziert Wiederholungen bei gleicher Reihenfolge); Issue #2668: das
    Bindewort aus dem Katalog ('A, B and C')."""
    deduped = list(dict.fromkeys(items))
    if not deduped:
        return ""
    if len(deduped) == 1:
        return deduped[0]
    return t("warnung.liste.und", lang, liste=", ".join(deduped[:-1]), letztes=deduped[-1])


def _standalone_chip_html(label: str, *, active: bool) -> str:
    """`.seg`-Route-Chip (SOLL-Design #1233): betroffen normal, frei
    durchgestrichen (`.seg.off` + Inline-`line-through`, Outlook-sicher).
    Inline-CSS 1:1 aus der Vorlage (`.warn .facts .seg`/`.seg.off`, F002) --
    Farbe des inaktiven Chips ueber das Bestands-Token `G_INK_FAINT`
    statt der Vorlage-Hex `#9a958a` (F001/AC-13)."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK_FAINT, G_INK_MUTED

    css_class = "seg" if active else "seg off"
    base = (
        f"display:inline-block;font-family:{FONT_DATA};font-size:12px;"
        f"border-radius:3px;padding:1px 6px;margin:0 4px 4px 0;"
    )
    if active:
        style = base + f"background:#faf8f1;border:1px solid #e7e2d3;color:{G_INK_MUTED};"
    else:
        style = (
            base + "background:transparent;border:1px dashed #e7e2d3;"
            f"text-decoration:line-through;text-decoration-color:#d8d3c2;color:{G_INK_FAINT};"
        )
    return f'<span class="{css_class}" style="{style}">{_html.escape(label)}</span> '


def _standalone_verdict_html(
    n_count: int, leading_level: int, leading_word: str, uniform: bool,
    level_colors: dict[int, str], font_mono: str, lang: Lang = "de",
) -> str:
    """`.verdict`-Pill (AC-6): farbiger `.dot` + Anzahl, bei gemischten Stufen
    zusaetzlich '· höchste Stufe {WORT}'."""
    color = level_colors.get(leading_level, level_colors[4])
    css_class = _LEVEL_CLASS.get(leading_level, "rot")
    tint = _hex_to_rgba(color, 0.16)
    text = _verdict_text(n_count, leading_word, uniform, lang)
    dot = (
        f'<span class="dot {css_class}" style="width:12px;height:12px;'
        f'border-radius:999px;background:{color};'
        f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);"></span>'
    )
    return (
        f'<div class="verdict" style="display:inline-flex;align-items:center;'
        f'gap:8px;font-family:{font_mono};font-size:12px;font-weight:600;'
        f'letter-spacing:.06em;text-transform:uppercase;padding:5px 11px;'
        f'border-radius:999px;margin-bottom:16px;background:{tint};'
        f'color:{color};">{dot}{_html.escape(text)}</div>'
    )


def _headline_text(
    ordered: list["OfficialAlertNotice"], uniform: bool, lang: Lang = "de",
) -> str:
    """Kernaussage der Ueberschrift als Klartext -- gemeinsame Quelle fuer das
    HTML (escaped, `_standalone_headline_html`) und den Klartext-Teil der Mail
    (#1744 A2, AC-13). Regeln unveraendert, siehe dort."""
    types = []
    for n in ordered:
        typ = _display_label(n.alert, lang=lang)
        if not uniform and not _is_eaws(n.alert):
            typ = f"{typ} ({_level_word(n.alert.level, lang)})"
        types.append(typ)
    text = _join_de(types, lang)
    if _uniform_scope(ordered) and not _scope_matches_sole_chip(ordered[0]):
        return t("warnung.kopf.gemeldet_fuer", lang, typen=text, umfang=_scope_display(ordered[0], lang))
    return t("warnung.kopf.gemeldet", lang, typen=text)


def _verdict_text(n_count: int, leading_word: str, uniform: bool, lang: Lang = "de") -> str:
    """Kennzeichen-Text '{N} amtliche Warnung(en)' (+ Hoechststufe bei
    gemischten Stufen) -- geteilt von Verdict-Pille und Klartext-Teil."""
    # Issue #1441: leeres `leading_word` = fuehrender Lagebericht, kein Ampelwort.
    extra = "" if uniform or not leading_word else f" · {t('warnung.kopf.hoechste_stufe', lang)} {leading_word}"
    return f"{tn('warnung.verdict', n_count, lang)}{extra}"


def _standalone_headline_html(
    ordered: list["OfficialAlertNotice"], uniform: bool, lang: Lang = "de",
) -> str:
    """`.body-h1` (AC-7): deterministische Template-Headline '{Typen} für
    {scope} gemeldet.'. Bei gemischten Stufen traegt jeder Typ zusaetzlich
    sein Stufen-Wort in Klammern (Design-Vorlage Beispiel C). Inline-CSS 1:1
    aus der Vorlage (F002).

    Issue #1239 (AC-17): die Reichweite kommt aus `_scope_display` -- bei vielen
    betroffenen Orten nennt die Ueberschrift die Gefahren-Typen und eine
    Mengenangabe, statt die vollstaendige Ortsliste aus dem Betreff zu
    wiederholen (die Namen stehen ohnehin in den Chips darunter).

    Adversary F006 (HIGH, Staging-Fund): die Reichweite darf nur genannt
    werden, wenn ALLE Warnungen denselben Umfang haben (`_uniform_scope`,
    dieselbe Bedingung wie in der Quelle-Box `_standalone_src_sentence`, AC-9)
    -- sonst verallgemeinert die Headline faelschlich den Umfang der ERSTEN
    Warnung auf alle aufgezaehlten Gefahren-Typen (Staging-Beispiel: eine
    GELBE Waldbrand-Warnung betraf ausschliesslich Draguignan, die Headline
    nannte trotzdem nur Toulon/Hyeres). Bei unterschiedlichem Umfang nennt die
    Headline nur die Gefahren-Typen ohne Ortsangabe -- der Umfang steht ohnehin
    bei jeder Warnung in der Karte darunter.

    Adversary F007 (MEDIUM, Staging-Fund): der Typ-Text kommt jetzt aus dem
    geteilten `_display_label` statt aus dem rohen `_hazard_display`-Typwort --
    sonst widerspricht sich die Headline mit dem Warn-Titel/Betreff derselben
    Warnung (Staging-Beispiel: Headline "Zugang gesperrt", Warn-Titel/Betreff
    "Zugang eingeschränkt — Monts Toulonnais")."""
    from output.renderers.email.design_tokens import G_INK

    style = (
        f"font-size:26px;font-weight:700;letter-spacing:-.01em;"
        f"margin:0 0 18px;line-height:1.2;color:{G_INK};"
    )
    # #1744 A2: EINE Textquelle fuer HTML und Klartext (`_headline_text`), hier
    # escaped -- die Regeln (F006/F007, Scope-Nennung) stehen dort.
    text = _html.escape(_headline_text(ordered, uniform, lang))
    return f'<div class="body-h1" style="{style}">{text}</div>'


def _standalone_ladder_html(
    active_level: int, level_colors: dict[int, str], lang: Lang = "de",
) -> str:
    """`.stufe-line` (uniforme Stufe, AC-8): GELB->ORANGE->ROT-Leiter mit
    aktiver Stufe (`.on`) + Positions-Hinweis ('niedrigste/mittlere/höchste
    von drei'). Inline-CSS 1:1 aus der Vorlage (F002); die aktive Stufe
    faerbt sich ueber `_hex_to_rgba` des Bestands-Tokens (AC-13)."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK_FAINT

    pos = _LEVEL_POSITION.get(active_level, 0)
    hint = _html.escape(t("warnung.stufe.von_drei", lang, position=_position_word(pos, lang)))
    spans = []
    for i, lvl in enumerate((2, 3, 4)):
        word = _html.escape(_level_word(lvl, lang))
        active = lvl == active_level
        css_class = ("on " + _LEVEL_CLASS[lvl]) if active else _LEVEL_CLASS[lvl]
        dot = (
            f'<span class="p" style="width:8px;height:8px;border-radius:999px;'
            f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);'
            f'opacity:{"1" if active else ".35"};background:{level_colors[lvl]}"></span>'
        )
        base = (
            f"display:inline-flex;align-items:center;gap:6px;padding:4px 12px;"
            f"font-family:{FONT_DATA};font-size:11px;font-weight:600;"
            f"letter-spacing:.04em;"
        )
        border = "border-left:1px solid #e7e2d3;" if i else ""
        # F003 (Fix-Loop Nachzug): aktiv/inaktiv als sauberer if/else-Zweig
        # (statt Basis-Werte + Ueberschreibung), damit `background`/`color`
        # je Span nur EINMAL im style-Attribut stehen -- wie bereits in
        # `_standalone_chip_html` gehandhabt.
        if active:
            style = (
                base + border
                + f"background:{_hex_to_rgba(level_colors[lvl], .16)};"
                f"color:{level_colors[lvl]};"
            )
        else:
            style = base + border + f"color:{G_INK_FAINT};background:#fff;"
        spans.append(f'<span class="{css_class}" style="{style}">{dot}{word}</span>')
    return (
        f'<div class="stufe-line" style="display:flex;align-items:center;gap:12px;'
        f'flex-wrap:wrap;margin:0 0 18px;">'
        f'<span class="stufe-cap" style="font-family:{FONT_DATA};font-size:11px;'
        f'letter-spacing:.08em;text-transform:uppercase;color:{G_INK_FAINT};'
        f'font-weight:600;">{_html.escape(t("warnung.kopf.warnstufe", lang))}</span>'
        f'<span class="stufe" style="display:inline-flex;align-items:stretch;'
        f'border:1px solid #d8d3c2;border-radius:999px;overflow:hidden;">'
        f'{"".join(spans)}</span>'
        f'<span class="stufe-hint" style="font-size:13px;color:{G_INK_FAINT};">'
        f'{hint}</span></div>'
    )


def _standalone_bars_meter_html(level: int, color: str, lang: Lang = "de") -> str:
    """`.meter`-Baustein je Warnung bei gemischten Stufen (AC-9/AC-13): 3
    `<i>`-Balken, `pos` davon in Bestands-Token-Farbe gefuellt, Rest leer.
    Inline-CSS 1:1 aus der Vorlage (F002), inkl. der bisher fehlenden
    Container-Styles fuer `.meter`/`.bars`."""
    from output.renderers.email.design_tokens import FONT_DATA

    pos = _LEVEL_POSITION.get(level, 0)
    word = _html.escape(_level_word(level, lang))
    bar_base = (
        "width:8px;height:8px;border-radius:999px;"
        "box-shadow:inset 0 0 0 1px rgba(26,26,24,.20);"
    )
    bars = "".join(
        f'<i style="{bar_base}background:{color if i <= pos else "transparent"};"></i>'
        for i in range(1, 4)
    )
    css_class = _LEVEL_CLASS.get(level, "rot")
    return (
        f'<span class="meter {css_class}" style="display:inline-flex;'
        f'align-items:center;gap:8px;">'
        f'<span class="bars" style="display:inline-flex;gap:3px;align-items:center;">'
        f'{bars}</span>'
        # AC-18: `white-space:nowrap` -- das Stufen-Wort ("ORANGE") darf nie
        # mitten im Wort umbrechen, auch nicht in schmalen Spalten.
        f'<span class="lvl" style="font-family:{FONT_DATA};font-size:11.5px;'
        f'font-weight:600;letter-spacing:.04em;white-space:nowrap;'
        f'color:{color};">{word} · {pos}/3</span></span>'
    )


def _standalone_warn_type_html(notice: "OfficialAlertNotice", lang: Lang = "de") -> str:
    """Warn-Titel der Standalone-Zeile, bereits HTML-escaped (Issue #1238):

    - AC-4: der reichere Quell-Label ERSETZT das Typ-Wort (geteilte Quelle
      `_display_label`), statt es zu wiederholen ("Zugang gesperrt — Zugang
      eingeschraenkt — Maures" war der Bug).
    - AC-6: die numerische Quell-Stufe am Label-Ende ("— Stufe 3") entfaellt,
      weil dieselbe Stufe in derselben Zeile bereits als Eskalations-Meter bzw.
      Stufen-Wort steht ("ORANGE · 2/3"). Adversary F002: die Suffix-Bereinigung
      sitzt in `_display_label` selbst (geteilt fuer alle drei Anzeige-Orte),
      hier also implizit."""
    return _html.escape(_display_label(notice.alert, lang=lang))


#: Datenzeile der Standalone-Warn-Mail: `(Label, Klartext-Wert, HTML-Wert|None)`.
#: `None` heisst "Klartext-Wert escapen" -- fertiges Markup nur, wo es sein muss
#: (Route-Chips, `.type`-Beschriftung).
_DataRow = tuple[str, str, "str | None"]


def _standalone_datarow_html(
    label: str, value: str, *, first: bool, value_html: "str | None" = None,
) -> str:
    """Datenzeile in der Bauform des Nowcasts (#1744 A2, AC-8): GETEILTER
    Baustein `_datarow_html` (`render.py`), damit beide Alarm-Mailtypen
    dieselbe Outlook-sichere `<table role="presentation">`-Zeile emittieren
    (Label links, Wert rechtsbuendig).

    Die Beschriftung behaelt ihren Doppelpunkt: an ihm haengen die
    Pflicht-Literale des Warn-Mail-Waechters ("Gültig:" P-3, "Quelle:" P-4)
    und die Bestands-Zusicherung "keine Gültig-Zeile ohne bekannten Zeitraum"
    (#1238 AC-7)."""
    from output.renderers.email.design_tokens import G_INK

    from .render import _datarow_html

    return _datarow_html(f"{label}:", value, G_INK, first, value_html=value_html)


def _standalone_type_row(notice: "OfficialAlertNotice", lang: Lang = "de") -> _DataRow:
    """Datenzeile "Gefahr". Der Wert traegt die `.type`-Beschriftung -- die
    Detail-Fidelity aus `_display_label` (#1238 AC-4/AC-6) bleibt damit an
    derselben Stelle pruefbar wie vor dem Umbau."""
    from output.renderers.email.design_tokens import G_INK

    typ = _standalone_warn_type_html(notice, lang)  # bereits escaped
    return (
        t("warnung.zeile.gefahr", lang), _display_label(notice.alert, lang=lang),
        f'<span class="type" style="font-weight:600;color:{G_INK};">{typ}</span>',
    )


def _standalone_fact_rows(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", lang: Lang = "de",
) -> list[_DataRow]:
    """Die uebrigen Fakten EINER Warnung als Datenzeilen (Grid UND Stacked):

    - AC-7/AC-8: die "Gültig"-Zeile entfaellt VOLLSTAENDIG, wenn die Warnung
      keinen Gueltigkeitszeitraum hat (tagesbezogene Zugangssperren, Waldbrand-
      Tagesstufen) -- kein Platzhalter "unbekannt" mehr. Mit Zeiten bleibt sie
      unveraendert.
    - AC-12: Feld-Label "Orte" im Ortsvergleich (`scope_kind="locations"`),
      "Route" im Trip-Pfad (unveraendert)."""
    rows: list[_DataRow] = []
    if notice.alert.valid_from and notice.alert.valid_to:
        rows.append((t("warnung.gueltig", lang), _format_validity(notice.alert, tz, lang=lang), None))
    chips = "".join(_standalone_chip_html(c, active=True) for c in notice.affected_chips)
    chips += "".join(_standalone_chip_html(c, active=False) for c in notice.free_chips)
    scope_key = t("warnung.zeile.orte" if notice.scope_kind == "locations" else "warnung.zeile.route", lang)
    rows.append((scope_key, _join_de(list(notice.affected_chips), lang), chips or None))
    return rows


def _standalone_facts_html(rows: list[_DataRow], note: str) -> str:
    """`.facts`-Block der Standalone-Warn-Zeile: die Fakten als Datenzeilen in
    der Bauform des Nowcasts (#1744 A2, AC-8) statt als Inline-Grid mit
    `<br>`-getrennten `.k`/`.mono`-Spans."""
    zeilen = "".join(
        _standalone_datarow_html(label, value, first=(i == 0), value_html=value_html)
        for i, (label, value, value_html) in enumerate(rows)
    )
    return f'<div class="facts" style="font-size:14px;line-height:1.5;">{zeilen}{note}</div>'


def _standalone_route_note_html(notice: "OfficialAlertNotice", lang: Lang = "de") -> str:
    """`.route-note` unter den Datenzeilen: nennt die freie Reststrecke, wenn
    es eine gibt (ADR-0033 unberuehrt -- freie Chips werden nur im Trip-Pfad
    mit Teilstrecke gesetzt)."""
    if not notice.free_chips:
        return ""
    from output.renderers.email.design_tokens import G_INK_FAINT

    return (
        f'<div class="route-note" style="font-size:12.5px;color:{G_INK_FAINT};'
        f'margin-top:7px;">{_html.escape(_route_note_text(notice, lang))}</div>'
    )


def _route_note_text(notice: "OfficialAlertNotice", lang: Lang = "de") -> str:
    """Klartext der `.route-note` -- geteilt von HTML und Klartext-Teil."""
    return t("warnung.zeile.route_frei", lang, abschnitte=_join_de(list(notice.free_chips), lang))


def _standalone_row_border_style(first: bool) -> str:
    """Inline-Ersatz fuer den Geschwister-Selektor `.warn + .warn` der Vorlage
    (Inline-CSS-Mails kennen keine CSS-Kombinatoren): jede Zeile ausser der
    ersten bekommt die Trennlinie `--g-rule-soft` (`#e7e2d3`, konsistent zur
    bereits inline genutzten `.seg`-Border-Farbe) selbst inline mit."""
    return "" if first else "border-top:1px solid #e7e2d3;"


def _standalone_warn_grid_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", *, first: bool = True,
    lang: Lang = "de",
) -> str:
    """`.warn`-Zeile bei uniformer Stufe: Gefahrenart, Gueltigkeit und
    Route-Chips als Datenzeilen (#1744 A2, AC-8) -- vor A2 ein zweispaltiges
    Grid mit Typ links und einem Inline-Facts-Block rechts. Freie Chips bleiben
    durchgestrichen, die `.route-note` bleibt darunter (ADR-0033 unberuehrt).
    `first`: jede Zeile ausser der ersten traegt `border-top` als Inline-Ersatz
    fuer den Geschwister-Selektor `.warn + .warn`."""
    rows = [_standalone_type_row(notice, lang)] + _standalone_fact_rows(notice, tz, lang)
    return (
        f'<div class="warn" style="display:block;padding:14px 16px;'
        f'{_standalone_row_border_style(first)}">'
        f'{_standalone_facts_html(rows, _standalone_route_note_html(notice, lang))}</div>'
    )


def _standalone_warn_stacked_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", color: str, *, first: bool = True,
    lang: Lang = "de",
) -> str:
    """`.warn.stacked` (gemischte Stufen, Design 'Beispiel C', AC-9): eigenes
    Eskalations-Meter + Typ im `.whead`, darunter die Fakten als Datenzeilen
    (#1744 A2, AC-8). Die Gefahrenart bleibt hier im `.whead` neben dem Meter --
    sie steht deshalb NICHT zusaetzlich als Datenzeile (sonst nennte die Mail
    denselben Typ zweimal). Inline-CSS 1:1 aus der Vorlage (F002). `first`
    (Fix-Loop-Nachzug): siehe `_standalone_warn_grid_html`."""
    from output.renderers.email.design_tokens import G_INK

    typ = _standalone_warn_type_html(notice, lang)
    # Issue #1441: der Lagebericht nennt seine Stufe im Titel -- keine n/3-Leiter.
    meter = "" if _is_eaws(notice.alert) else _standalone_bars_meter_html(notice.alert.level, color, lang)
    facts = _standalone_facts_html(_standalone_fact_rows(notice, tz, lang), "")
    return (
        f'<div class="warn stacked" style="display:block;padding:14px 16px;'
        f'{_standalone_row_border_style(first)}">'
        f'<div class="whead" style="display:flex;align-items:center;gap:14px;'
        f'margin-bottom:9px;">{meter}'
        f'<span class="type" style="font-size:15px;font-weight:600;color:{G_INK};">'
        f'{typ}</span></div>'
        f'{facts}</div>'
    )


def _uniform_scope(notices: list["OfficialAlertNotice"]) -> bool:
    """Ob ALLE Warnungen denselben betroffenen Umfang haben -- geteilte
    Bedingung fuer die Quelle-Box (`_standalone_src_sentence`, AC-9), die
    Headline (`_standalone_headline_html`, Adversary F006) UND den Betreff
    (`render_official_alert_subject`, Adversary F006). Konsolidiert an EINER
    Stelle, damit die Scope-Einheitlichkeits-Pruefung nicht ein drittes Mal
    auseinanderlaeuft.

    Adversary F009 (#1239 Nachzug Runde 5, HIGH): vergleicht `scope_ids`
    (IDENTITAET -- Orts-/Segment-IDs), NICHT `scope_label` (den Anzeige-
    String). Zwei verschiedene Orte mit gleichem Anzeigenamen (zwei "Hütte")
    haetten ueber `scope_label` faelschlich als "einheitlicher Umfang"
    gegolten -- exakt der Bug, den F006 fuer die Quelle-Box/Headline/Betreff
    beheben sollte, hier nur ueber die Anzeige-Namen statt der IDs. Faellt auf
    den Namensvergleich zurueck, wenn (mindestens) eine Notice kein
    `scope_ids` traegt (Alt-Aufrufer/handgebaute Test-Notices ohne dieses
    Feld) -- Bestandsverhalten fuer diese Faelle bleibt unveraendert."""
    if all(n.scope_ids for n in notices):
        return len({n.scope_ids for n in notices}) <= 1
    return len({n.scope_label for n in notices}) <= 1


def _scope_matches_sole_chip(notice: "OfficialAlertNotice") -> bool:
    """Befund 1 (#1326a, ADR-0033): true, wenn `scope_label` exakt dem
    einzigen betroffenen Chip entspricht -- Headline/Quelle-Satz wuerden dann
    dieselbe Information ein zweites Mal wiederholen, die bereits im
    Fakten-Feld/Chip steht (der Route-Teilstrecken-Fall des Trip-Builders,
    `build_official_alert_notices`, setzt `scope_label` immer identisch zum
    einzigen Chip). Fuer Compare (`scope_label` traegt ein 'nur '-Praefix bzw.
    eine Komma-Liste, nie identisch zum bloßen Chip-Text) und fuer die
    Sonderfaelle 'gesamte Route'/'alle Orte' greift dies nie."""
    return len(notice.affected_chips) == 1 and notice.scope_label == notice.affected_chips[0]


def _standalone_src_sentence(
    ordered: list["OfficialAlertNotice"], uniform: bool, lang: Lang = "de",
) -> str:
    """Prosaischer Scope-Satz des `.src`-Bausteins (Spec Slice B Punkt 6) --
    deterministisches Template, keine freie Prosa (bereits HTML-escaped).

    AC-9 (#1238): der Satz darf den Umfang der FUEHRENDEN Warnung nicht mehr
    ueber alle Warnungen verallgemeinern. Haben die Warnungen unterschiedliche
    Umfaenge, verweist ein neutraler Satz auf die Einzelangaben oben. AC-10:
    bei einheitlichem Umfang bleibt der Satz unveraendert."""
    if not _uniform_scope(ordered):
        return _html.escape(t("warnung.satz.unterschiedlich", lang))
    if not uniform:
        leading = ordered[0]
        # Adversary-Nachzug (gleiche Fehlerklasse wie F007, proaktiv mitgefixt):
        # `_display_label` statt des rohen `_hazard_display`-Typwortes, sonst
        # widerspricht dieser Satz demselben Massiv-Titel, der direkt darueber
        # im Warn-Titel steht ("Zugang gesperrt" hier vs. "Zugang eingeschränkt
        # — Monts Toulonnais" im Titel).
        typ = _display_label(leading.alert, lang=lang)
        word_part = "" if _is_eaws(leading.alert) else f" ({_level_word(leading.alert.level, lang)})"
        return _html.escape(t("warnung.satz.kritischer", lang, typ=f"{typ}{word_part}"))
    leading = ordered[0]
    scope = leading.scope_label
    voll = _full_scope_kind(scope)
    if voll:
        return _html.escape(t(f"warnung.satz.deckt_{voll}.{'one' if len(ordered) == 1 else 'other'}", lang))
    if _scope_matches_sole_chip(leading):
        # Befund 1 (#1326a, ADR-0033): der betroffene Umfang steht bereits als
        # Chip im Fakten-Feld -- keine zweite Nennung in Prosa.
        return ""
    # Nebenbefund (#1238): der Compare-`scope_label` traegt bei einem einzelnen
    # Ort bereits "nur X" -> ohne diese Bereinigung entstand "Betrifft nur nur
    # Toulon". Das "nur" gehoert genau einmal in den Satz (jede Sprache).
    for sprache in ("de", "en"):
        praefix = t("warnung.umfang.nur", sprache, ort="")
        if scope.startswith(praefix):
            scope = scope[len(praefix):]
            break
    key = "warnung.satz.nur_orte" if leading.scope_kind == "locations" else "warnung.satz.nur_route"
    return _html.escape(t(key, lang, ort=scope))


def _standalone_src_value(
    ordered: list["OfficialAlertNotice"], source_label: str,
) -> str:
    """Wert der Quellen-Angabe als Klartext: '{Quelle} — {Regionen}.'
    Regionen dedupliziert (F007-Bestandsschutz). Geteilt von HTML-Datenzeile
    und Klartext-Teil (#1744 A2).

    Adversary F013 (#1239 Nachzug Runde 7, HIGH): pro Notice werden ALLE
    Regionen ihres Buendels genannt (`n.regions`, von den Buildern aus
    `_bundle_by_hazard_level` gesetzt), nicht nur `n.alert.region_label` des
    Buendel-Repraesentanten -- sonst nennt die Quelle-Box bei einer aus zwei
    Départements gebuendelten Warnung nur EINES ("— Var." statt "— Var,
    Bouches-du-Rhône." fuer eine Warnung, die beide abdeckt: eine falsche
    Zustaendigkeits-Zuordnung, kein blosses Auslassen). Fallback auf
    `alert.region_label`, wenn `n.regions` leer ist (Alt-Aufrufer/handgebaute
    Test-Notices ohne dieses Feld)."""
    regions: list[str] = []
    for n in ordered:
        rls = n.regions or ((n.alert.region_label,) if n.alert.region_label else ())
        for rl in rls:
            if rl and rl not in regions:
                regions.append(rl)
    region_suffix = " — " + ", ".join(regions) if regions else ""
    return f"{source_label}{region_suffix}."


def _standalone_src_html(
    ordered: list["OfficialAlertNotice"], source_label: str, uniform: bool,
    ink_muted: str, lang: Lang = "de",
) -> str:
    """Quelle als DATENZEILE innerhalb des Datenzeilen-Blocks (#1744 A2, AC-8)
    -- bis A2 eine eigene getoente `.src`-Box UNTER der Warn-Karte, also ein
    Baustein, den die gemeinsame Zielreihenfolge nicht kennt (deshalb entfallen
    die Box-Farbparameter `box_bg`/`info_color`).

    Die Klasse `.src` ist ERSATZLOS entfallen (Adversary F002): solange sie am
    Rest der alten Box klebte, war die Quelle strukturell weiter ein Sonderfall
    -- der Warn-Mail-Waechter haette seine Quellen-Pruefung unveraendert an ihr
    festmachen koennen, und seine neue Datenzeilen-Alternative (S-1b) waere von
    keiner echt gerenderten Mail je erreicht worden. Die Quelle ist jetzt eine
    Datenzeile wie Gefahr, Gueltigkeit und Ortsbezug; der aeussere `<div>`
    traegt nur noch den Zeilenabstand, keine Kennung. Der prosaische Scope-Satz
    steht als `.scope-note` unter der Zeile, statt in die rechtsbuendige
    Wert-Zelle gequetscht zu werden."""
    zeile = _standalone_datarow_html(
        t("warnung.quelle", lang), _standalone_src_value(ordered, source_label), first=False,
    )
    sentence = _standalone_src_sentence(ordered, uniform, lang)
    note = (
        f'<div class="scope-note" style="font-size:12.5px;color:{ink_muted};'
        f'margin-top:7px;">{sentence}</div>' if sentence else ""
    )
    return f'<div style="padding:0 16px 12px;">{zeile}{note}</div>'


def _stand_abgerufen(stand_at: str, quelle: str, lang: Lang, *, html: bool = False) -> str:
    """Fusszeile 'Stand: heute HH:MM · abgerufen bei {Quelle}' (Issue #2668:
    Katalog). ``html=True``: Texte escaped, ``quelle`` ist bereits Markup."""
    stand = t("warnung.zeile.stand", lang, zeit=stand_at)
    abgerufen = t("warnung.abgerufen_bei", lang)
    if html:
        stand, abgerufen = _html.escape(stand), _html.escape(abgerufen)
    return f"{stand} · {abgerufen} {quelle}"


def render_official_alert_html(
    notices: list["OfficialAlertNotice"], *, source_label: str, stand_at: str, tz: "ZoneInfo",
    context_label: str | None = None, source_url: str | None = None,
    allclear_html: str = "", lang: Lang = "de",
) -> str:
    """E-Mail-HTML auf dem SOLL-Design (#1233 Slice B, „Alert · Amtliche
    Warnung"): Verdict-Pill, deterministische Headline, Warnstufen-Leiter
    (uniforme Stufe) bzw. Eskalations-Meter je Warnung (gemischte Stufen),
    Datenzeilen-Block (Gefahr, Gültig, Route-Chips — frei durchgestrichen —,
    Quelle), Stand-Zeile, Herkunfts-Fußzeile.
    Ausschliesslich Bestands-Farb-Tokens (G_ALERT_L2/L3/L4), keine
    Design-Vorlage-Hex (AC-13).

    Issue #1744 A2 (AC-8): die Fakten stehen in DERSELBEN Datenzeilen-Bauform
    wie in der Nowcast-Mail (`render.py::_datarow_html`), und die Quelle ist
    eine Datenzeile IM Block statt einer eigenen Box darunter -- beide
    Alarm-Mailtypen tragen damit dieselbe Bausteinfolge. Den Klartext-Teil
    dazu baut `render_official_alert_mail_plain`."""
    from output.renderers.email.design_tokens import (
        FONT_DATA, FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK,
        G_INK_FAINT, G_INK_MUTED, G_SUCCESS,
    )

    # Issue #1441: Stufe 1 explizit (sonst Default ROT fuer die Lagebericht-Stufe 1).
    level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    leading_word = _level_word(leading_level, lang)
    if _is_eaws(ordered[0].alert):
        leading_word = ""  # Issue #1441: kein Ampelwort fuer den Lagebericht

    verdict = _standalone_verdict_html(
        len(ordered), leading_level, leading_word, uniform, level_colors, FONT_DATA, lang,
    )
    headline = _standalone_headline_html(ordered, uniform, lang)
    with_ladder = uniform and not any(_is_eaws(n.alert) for n in ordered)
    ladder = _standalone_ladder_html(leading_level, level_colors, lang) if with_ladder else ""

    if uniform:
        warns = "".join(
            _standalone_warn_grid_html(n, tz, first=(i == 0), lang=lang)
            for i, n in enumerate(ordered)
        )
    else:
        warns = "".join(
            _standalone_warn_stacked_html(
                n, tz, level_colors.get(n.alert.level, G_ALERT_L4), first=(i == 0), lang=lang,
            )
            for i, n in enumerate(ordered)
        )
    # #1744 A2 (AC-8): die Quellen-Datenzeile steht IM Datenzeilen-Block, nicht
    # als eigener Baustein darunter -- beide Alarm-Mailtypen tragen damit
    # dieselbe Bausteinfolge (Kennzeichen, Ueberschrift, [Skala,] Datenzeilen,
    # [Sperrzeit,] Stand, Herkunft).
    src = _standalone_src_html(ordered, source_label, uniform, G_INK_MUTED, lang)
    warns_block = (
        f'<div class="warns" style="border:1px solid #d8d3c2;border-radius:6px;'
        f'overflow:hidden;margin:4px 0 16px;">{warns}{src}</div>'
    )

    # Issue #1441 (CC BY 4.0): mit `source_url` wird der Quellenname zum Link --
    # derselbe Baustein wie im eingebetteten WarnBlock. Ohne URL unveraendert.
    abgerufen = (
        _source_link_html(source_label, source_url, f"color:{G_INK_FAINT};")
        if source_url else _html.escape(source_label)
    )
    footer = (
        f'<p class="body-foot" style="font-size:13.5px;color:{G_INK_FAINT};'
        f'margin:18px 0 0;">{_stand_abgerufen(stand_at, abgerufen, lang, html=True)}</p>'
    ) + _authority_note_html(ordered, lang)
    # Issue #1241/warnmail-Spec AC-5 (Befund 4a): Herkunfts-Fußzeile mit
    # Kontext (Trip-Name bzw. „Ortsvergleich") -- Zeile 2 zeigt die echte
    # Quelle (`source_label`, ggf. nach AC-4 mehrfach), nicht den Renderer-Pfad.
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_html,
    )
    origin = render_origin_footer_html(build_origin_footer(
        "official-alert", source=source_label, context_label=context_label, lang=lang,
    ))
    return (
        f'<html><body style="font-family:{FONT_UI};color:{G_INK};">'
        f'{verdict}{headline}{ladder}{warns_block}{allclear_html}{footer}{origin}</body></html>'
    )


def render_official_alert_mail_plain(
    notices: list["OfficialAlertNotice"], *, source_label: str, stand_at: str,
    tz: "ZoneInfo", context_label: str | None = None, source_url: str | None = None,
    allclear_lines: list[str] | None = None, lang: Lang = "de",
) -> str:
    """Klartext-Teil der eigenstaendigen amtlichen Warn-Mail (#1744 A2, AC-13).

    Baut dieselben Bausteine in derselben Reihenfolge wie
    `render_official_alert_html` aus DENSELBEN `(Label, Wert)`-Tupeln -- so wie
    der Nowcast es haelt (`render.py::_render_email_onset`).

    Bis A2 hatte diese Mail keinen eigens gebauten Klartext: `EmailOutput.send`
    bekam kein `plain_text_body`, woraufhin `build_mime_message` die Tags aus
    dem HTML strippte (`channels/email.py`) -- aus dem Warn-Block wurde eine
    einzige zusammengeklebte Zeile ("…WarnstufeGELBORANGEROT…").

    NICHT zu verwechseln mit `render_official_alert_notice_plain`: die bedient
    den in eine ANDERE Mail eingebetteten Warnblock.

    `tz` ist PFLICHT (kein stiller UTC-Rueckfall, #1402): Klartext und HTML
    derselben Mail muessen denselben Wochentag nennen."""
    from output.renderers.email.helpers import (
        build_origin_footer, render_origin_footer_text,
    )

    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    leading_word = _level_word(leading_level, lang)
    if _is_eaws(ordered[0].alert):
        leading_word = ""  # Issue #1441: kein Ampelwort fuer den Lagebericht

    zeilen = [
        _headline_text(ordered, uniform, lang),
        "",
        _verdict_text(len(ordered), leading_word, uniform, lang),
        "",
    ]
    warnstufe = t("warnung.kopf.warnstufe", lang)
    if uniform and not any(_is_eaws(n.alert) for n in ordered):
        # Gegenstueck der Warnstufen-Leiter: die Skala traegt eine Einordnung,
        # die eine blosse Wortangabe verliert (AC-9) -- im Klartext als
        # Datenzeile, weil es dort keine Leiter gibt.
        pos = _LEVEL_POSITION.get(leading_level, 0)
        hinweis = t("warnung.stufe.von_drei", lang, position=_position_word(pos, lang))
        stufen = " · ".join(_level_word(lvl, lang) for lvl in (2, 3, 4))
        zeilen.append(f"{warnstufe}: " + t("warnung.zeile.skala", lang, wort=leading_word,
                                           hinweis=hinweis, stufen=stufen))
    for n in ordered:
        rows: list[_DataRow] = []
        if not uniform and not _is_eaws(n.alert):
            word = _level_word(n.alert.level, lang)
            rows.append((warnstufe, f"{word} · {_LEVEL_POSITION.get(n.alert.level, 0)}/3", None))
        rows.append(_standalone_type_row(n, lang))
        rows.extend(_standalone_fact_rows(n, tz, lang))
        zeilen.extend(f"{label}: {value}" for label, value, _h in rows)
        if n.free_chips:
            zeilen.append(_route_note_text(n, lang))
    zeilen.append(f"{t('warnung.quelle', lang)}: {_standalone_src_value(ordered, source_label)}")
    sentence = _standalone_src_sentence(ordered, uniform, lang)
    if sentence:
        # `_standalone_src_sentence` liefert bereits escapetes HTML (geteilt mit
        # der Datenzeile) -- im Klartext gehoert der rohe Satz hin.
        zeilen.append(_html.unescape(sentence))
    zeilen.extend(allclear_lines or [])  # Issue #1441 S2: Entwarnung NACH den Warnungen
    # Issue #1441 (CC BY 4.0): Gegenstueck des Quelle-Links im HTML.
    link = f" → {source_url}" if source_url else ""
    zeilen.extend([
        "",
        _stand_abgerufen(stand_at, f"{source_label}{link}", lang),
        *official_alert_authority_notes([n.alert for n in ordered], lang=lang),
        "",
        render_origin_footer_text(build_origin_footer(
            "official-alert", source=source_label, context_label=context_label, lang=lang,
        )),
    ])
    return "\n".join(zeilen)


def _embedded_meter_html(level: int, color: str) -> str:
    """Kompaktes 3-Punkt-Meter fuer den embedded WarnBlock (Issue #1216). Nutzt
    das BESTANDS-Farb-Token (`color`), NICHT die Design-Vorlage-Hex (AC-8): die
    ersten `pos` Punkte sind in Token-Farbe gefuellt, der Rest transparent."""
    pos = _LEVEL_POSITION.get(level, 0)
    dots = ""
    for i in range(1, 4):
        fill = color if i <= pos else "transparent"
        dots += (
            f'<i style="display:inline-block;width:7px;height:7px;'
            f'border-radius:999px;background:{fill};'
            f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.20);"></i>'
        )
    return (
        f'<span class="meter" style="display:inline-flex;align-items:center;'
        f'gap:3px;margin-right:4px;">{dots}</span>'
    )


def _embedded_chip(label: str, *, active: bool) -> str:
    """Route-/Umfang-Chip (`.seg`) fuer den embedded WarnBlock. Freie (nicht
    betroffene) Chips werden durchgestrichen dargestellt (F004 aus dem
    Standalone-Pfad, hier als `.seg.off`-Aequivalent)."""
    base = (
        "display:inline-block;font-family:'JetBrains Mono',monospace;"
        "font-size:11.5px;background:#fff;border:1px solid #e6e1d3;"
        "border-radius:3px;padding:1px 6px;margin:0 3px 0 0;color:#6b6962;"
    )
    if not active:
        base += "text-decoration:line-through;border-style:dashed;"
    return f'<span class="seg" style="{base}">{_html.escape(label)}</span>'


def _source_link_html(source_label: str, source_url: str | None, style: str) -> str:
    """Quelle-Link (`.wb-src`), geteilt von eingebettetem WarnBlock und
    eigenstaendiger Warn-Mail (Issue #1441, CC BY 4.0: Namensnennung + Link).
    Ohne `source_url` nur der Quellenname."""
    if source_url:
        return (
            f'<a class="wb-src" href="{_html.escape(source_url)}" '
            f'style="{style}">{_html.escape(source_label)} →</a>'
        )
    return f'<span class="wb-src" style="{style}">{_html.escape(source_label)}</span>'


def _authority_note_html(ordered: list["OfficialAlertNotice"], lang: Lang = "de") -> str:
    """Massgeblichkeits-Satz (Issue #1441 S3) als Fusszeile des Warn-Blocks."""
    notes = official_alert_authority_notes([n.alert for n in ordered], lang=lang)
    if not notes:
        return ""
    return (f'<div class="wb-authority" style="font-size:12px;color:#6b6962;margin-top:4px;">'
            f'{_html.escape(" ".join(notes))}</div>')


def _embedded_count(ordered: list["OfficialAlertNotice"], uniform: bool, lang: Lang) -> str:
    """Count-Zeile des eingebetteten WarnBlocks ('2 aktiv · Stufe ORANGE (2/3)')."""
    n = len(ordered)
    leading_level = ordered[0].alert.level
    if any(_is_eaws(nt.alert) for nt in ordered):
        # Issue #1441: keine Awareness-Leiter fuer die EAWS-Skala -- die Stufe
        # steht im Wortlaut jeder Warnung.
        return t("warnung.block.aktiv", lang, count=n)
    word = _level_word(leading_level, lang)
    if uniform:
        pos = _LEVEL_POSITION.get(leading_level, 0)
        return t("warnung.block.aktiv_stufe", lang, count=n, wort=word, position=pos)
    return t("warnung.block.aktiv_hoechste", lang, count=n, wort=word)


def _render_warn_block_embedded(
    notices: list["OfficialAlertNotice"], *, source_label: str,
    source_url: str | None, tz: "ZoneInfo | None", count_line: str | None,
    lang: Lang = "de",
) -> str:
    """Kompakter, eingebetteter WarnBlock (`.wb`-Struktur der Design-Vorlage,
    Issue #1216): Severity-Dot, Eyebrow „Amtliche Warnung", Count-Zeile,
    Quelle-Link; pro Warnung Meter (nur bei gemischten Stufen) + Stufen-Wort +
    Typ + Zeitraum + Route/Umfang-Chips. KEINE H1/Verdict/Leiter.

    Farben: ausschliesslich die Bestands-Tokens G_ALERT_L2/L3/L4 (AC-8) — die
    Design-Vorlage-Hex tauchen NICHT im Output auf.

    `count_line` (optional): ueberschreibt die berechnete Count-Zeile — der
    Ortsvergleich-Banner nutzt das fuer den Orts-Scope („höchste Stufe ROT ·
    Marseille")."""
    from output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK, G_SUCCESS,
    )
    from services.official_alerts.fr_departments import department_name

    if not notices:
        return ""

    level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    leading_color = level_colors.get(leading_level, G_ALERT_L4)
    count = count_line if count_line is not None else _embedded_count(ordered, uniform, lang)

    src_style = (
        "margin-left:auto;font-family:'JetBrains Mono',monospace;"
        "font-size:10.5px;color:#6b6962;text-decoration:none;"
    )
    src_html = _source_link_html(source_label, source_url, src_style)

    items = []
    for nt in ordered:
        typ, _sms = _hazard_display(nt.alert, lang)
        # F001 (#1216): Typ-Wort vs. voller Roh-Label haengt am Banner-KONTEXT.
        if count_line is not None:
            # Aggregat-/Summary-Banner (Ortsvergleich, Orts-Scope): zeigt
            # ausschliesslich das kurze Typ-Wort `typ` -- NICHT
            # `_display_label`. Der volle Roh-Label ("Gewitterwarnung Stufe
            # Orange", "Zugang gesperrt — Massiv Alpha", "Hitzewarnung ...")
            # steht bereits im Matrix-Chip + Pro-Ort-Streifen (additiv, PO-
            # Entscheidung Frage D). Eine dritte Kopie hier braeche die
            # Occurrence-Invarianten #1034/#1134. Die Stufe steht im Stufen-
            # Wort/Meter -> "Stufe Orange" waere ohnehin redundant.
            #
            # Adversary F004 (HIGH, #1239 Nachzug Runde 2): dieser Kommentar
            # behauptete frueher faelschlich, `typ` sei hier immer "das
            # saubere Typ-Wort" -- das stimmte NICHT fuer ungemappte hazards
            # (z.B. "wildfire_risk" vor dem `_HAZARD_DISPLAY`-Fix): dort lief
            # `_hazard_display` in den Fallback und lieferte den ROHEN
            # Quell-Label inkl. "— Stufe N" zurueck ("Waldbrand-Gefahr —
            # Stufe 3" direkt neben "höchste Stufe ORANGE" im Banner-Kopf).
            # Der Fix sitzt bewusst NICHT hier (kein `_display_label`-Aufruf,
            # sonst braeche die Occurrence-Invariante oben), sondern an der
            # Wurzel: `_HAZARD_DISPLAY` deckt jetzt ALLE produktiven
            # hazard-Werte ab, sodass `_hazard_display` nie mehr auf den
            # Roh-Label zurueckfaellt und `typ` hier GARANTIERT das kurze,
            # stufenfreie Typ-Wort ist.
            type_display = typ
        else:
            # Detail-Banner (Trip-Briefing): der Banner ist die EINZIGE
            # Darstellung der Warnung -> reicher/voller Roh-Label bleibt erhalten
            # (Region "Hitzewarnung Haute-Corse" #1217, Massiv "Zugang gesperrt —
            # ...", Vigilance "Extreme Hitze"), sonst faende #1217 den Label-Text
            # nicht. Standardfall label == typ -> unveraendert typ.
            # #1238 AC-4: dieselbe geteilte Ersetz-Logik wie Betreff und
            # Standalone-Titel (`_display_label`) -- keine dritte Kopie mehr.
            # Adversary F002: `_display_label` entfernt die numerische
            # Quell-Stufe ("— Stufe 3") auch hier, weil der Meter/das
            # Stufenwort bei gemischten Stufen bereits im `lvl`-Span links
            # daneben steht (bei uniformer Stufe steht sie im `count_line`-Kopf
            # des ganzen Blocks).
            type_display = _display_label(nt.alert, lang=lang)
        if uniform or _is_eaws(nt.alert):
            meter, lvl = "", ""
        else:
            lw = _html.escape(_level_word(nt.alert.level, lang))
            pos = _LEVEL_POSITION.get(nt.alert.level, 0)
            item_color = level_colors.get(nt.alert.level, G_ALERT_L4)
            meter = _embedded_meter_html(nt.alert.level, item_color)
            lvl = (
                f'<span class="wb-lvl" style="font-family:\'JetBrains Mono\','
                f'monospace;font-size:11px;font-weight:600;color:{item_color};'
                f'margin-right:6px;">{lw} {pos}/3</span>'
            )
        chips = "".join(_embedded_chip(c, active=True) for c in nt.affected_chips)
        chips += "".join(_embedded_chip(c, active=False) for c in nt.free_chips)
        # AC-7: ohne bekannten Gueltigkeitszeitraum entfaellt die Zeitangabe
        # ganz (kein Platzhalter "unbekannt"); mit Zeiten unveraendert (AC-8).
        when = ""
        if nt.alert.valid_from and nt.alert.valid_to:
            when = (
                f'<span class="wb-when" style="font-family:\'JetBrains Mono\','
                f'monospace;font-size:12px;color:#6b6962;margin-right:8px;">'
                f'{_html.escape(_format_validity(nt.alert, tz, lang=lang))}</span>'
            )
        # F001 (Adversary, HIGH, #1135 Nachbesserung): der Embedded-Renderer
        # (Trip-Briefing-Pfad) nannte bisher nur die Segment-/Umfang-Chips,
        # NIE die betroffenen Departements -- `nt.regions` (alle Regionen des
        # Buendels, s. `_bundle_by_hazard_level`) wurde hier nie gelesen.
        # Codes werden ueber `department_name()` in Namen uebersetzt (AC-1
        # verlangt Namen, nicht Codes). Fallback auf `alert.region_label`
        # (Alt-Aufrufer/handgebaute Notices ohne `regions`); ist beides leer
        # (z.B. Massiv-Sperren ohne Departement-Bezug), entfaellt die Zeile
        # ganz -- Standalone-Pfad bleibt unberuehrt (eigene Funktion/Logik).
        region_codes = nt.regions or (
            (nt.alert.region_label,) if nt.alert.region_label else ()
        )
        region_line = ""
        if region_codes:
            region_names = [department_name(c) for c in region_codes]
            region_line = (
                f'<div class="wb-region" style="font-size:12px;'
                f'color:#6b6962;margin-top:2px;">'
                f'{_html.escape(", ".join(region_names))}</div>'
            )
        items.append(
            f'<div class="wb-item" style="margin:0 0 7px;line-height:1.5;">'
            f'{meter}{lvl}'
            f'<span class="wb-type" style="font-size:14px;font-weight:600;'
            f'color:{G_INK};margin-right:8px;">{_html.escape(type_display)}</span>'
            f'{when}'
            f'<span class="wb-route">{chips}</span>'
            f'{region_line}'
            f'</div>'
        )

    dot = (
        f'<span class="dot" style="display:inline-block;width:11px;height:11px;'
        f'border-radius:999px;background:{leading_color};'
        f'box-shadow:inset 0 0 0 1px rgba(26,26,24,.18);margin-right:9px;'
        f'vertical-align:middle;"></span>'
    )
    color_class = {2: "wb-gelb", 3: "wb-orange", 4: "wb-rot"}.get(leading_level, "wb-rot")
    return (
        f'<div class="wb {color_class}" style="border:1px solid {leading_color};'
        f'border-left:4px solid {leading_color};border-radius:8px;'
        f'margin:16px 20px;font-family:{FONT_UI};">'
        f'<div class="wb-body" style="padding:12px 16px 13px;">'
        f'<div class="wb-head" style="margin-bottom:10px;">'
        f'{dot}<span class="wb-ey" style="font-family:\'JetBrains Mono\','
        f'monospace;font-size:10px;letter-spacing:.1em;text-transform:uppercase;'
        f'font-weight:700;color:{leading_color};">'
        f'{_html.escape(t("mail.herkunft.amtliche_warnung", lang))}</span> '
        f'<span class="wb-count" style="font-family:\'JetBrains Mono\',monospace;'
        f'font-size:11px;font-weight:600;color:{leading_color};margin-left:9px;">'
        f'{_html.escape(count)}</span> {src_html}'
        f'</div>'
        f'<div class="wb-list">{"".join(items)}</div>'
        f'{_authority_note_html(ordered, lang)}'
        f'</div></div>'
    )


def render_warn_block(
    notices: list["OfficialAlertNotice"], *, variant: str, source_label: str,
    source_url: str | None = None, stand_at: str | None = None,
    tz: "ZoneInfo | None" = None, count_line: str | None = None,
    context_label: str | None = None, allclear_html: str = "", lang: Lang = "de",
) -> str:
    """Geteilter WarnBlock-Renderer (Issue #1216). EIN Baustein fuer alle drei
    Mail-Flaechen (Trip-Briefing, Ortsvergleich, Standalone-Alarm), einziger
    Unterschied ist `variant`:

    - `variant="standalone"`: vollstaendiges HTML-Dokument mit H1-Headline,
      Verdict-Badge und Warnstufen-Leiter (uniform) — delegiert an das
      unveraenderte `render_official_alert_html` (Rueckwaerts-Kompatibilitaet /
      Fidelity-Bestandsschutz).
    - `variant="embedded"`: kompakte `.wb`-Bannerform ohne H1/Verdict/Leiter;
      bei gemischten Stufen Meter je Warnung, bei einheitlicher Stufe
      „Stufe {WORT} ({pos}/3)". Leere Notice-Liste -> „".

    Farb-Tokens: die Bestands-Tokens G_ALERT_L2/L3/L4 (PO 2026-07-11), NICHT die
    Design-Vorlage-Hex (AC-8)."""
    if variant == "standalone":
        return render_official_alert_html(
            notices, source_label=source_label, stand_at=stand_at or "", tz=tz,
            context_label=context_label, source_url=source_url, allclear_html=allclear_html,
            lang=lang,
        )
    if variant == "embedded":
        return _render_warn_block_embedded(
            notices, source_label=source_label, source_url=source_url,
            tz=tz, count_line=count_line, lang=lang,
        )
    raise ValueError(f"Unbekannte WarnBlock-variant: {variant!r}")


def render_official_alert_telegram(
    notices: list["OfficialAlertNotice"], *, prefix: str, source_label: str,
    tz: "ZoneInfo | None" = None, show_scope: bool = True, lang: Lang = "de",
) -> str:
    """Fette erste Zeile + je Warnung eine Zeile, hoechste Stufe zuerst.

    `show_scope` (Issue #1332 F001, Default True -- bestehende Aufrufer
    unveraendert): unterdrueckt das Scope-Segment ganz, wenn `prefix` die
    Umfangs-Identitaet bereits traegt (Compare-Telegram ruft dies JE ORT auf,
    der Ortsname steht schon als Block-Ueberschrift/`prefix` -- ein per-Ort
    berechnetes `scope_label` waere dort zwangslaeufig entweder "unbekannt"
    (kein Trip-Segment bekannt) oder redundant/irrefuehrend ("alle Orte" fuer
    genau den einen Block). Bei `show_scope=False` bleibt die Kopfzeile ohne
    Scope-Segment (nur Praefix + Stufe), die Zeilen ohne Umfangs-Suffix.

    `tz` (Issue #1216 F001, optional): lokalisiert `valid_from/valid_to` wie
    `render_official_alert_html` es bereits tut. Ohne `tz` (Default None)
    bleibt das rohe (i.d.R. UTC-)Verhalten bestehender Aufrufer unveraendert.

    Issue #1249 (S3/S4/S5): der Umfang der FUEHRENDEN Warnung galt in der
    Kopfzeile bedingungslos fuer alle Warnungen, waehrend die Warnungszeilen
    gar keinen Umfang trugen -- der Empfaenger unterwegs konnte eine Gefahr
    keinem Ort zuordnen. Jetzt entscheidet `_uniform_scope` (dieselbe geteilte
    Bedingung wie in der Mail, #1238/#1239): einheitlicher Umfang -> Kopfzeile
    nennt ihn einmalig, Zeilen bleiben schlank (bit-identisch zum Bestand);
    uneinheitlicher Umfang -> Kopfzeile nennt keinen (kein Platzhalter), jede
    Zeile traegt ihren eigenen `scope_label`. Die Gefahrenbezeichnung kommt aus
    `_display_label` (S5) -- dieselbe wie in der Mail statt des generischen
    Typ-Worts aus `_hazard_display`.

    Issue #1249 Runde 2 (F001/F002, PO-Beanstandung aus #1238 lebte in
    Telegram fort):
    - F001: fehlt einer Warnung der Gueltigkeitszeitraum, entfaellt die
      Zeitangabe (samt Trennzeichen) ERSATZLOS aus der Zeile -- kein
      "unbekannt" mehr (Gleichlauf mit der Mail, #1238 AC-7).
    - F002: Label und Zeitangabe werden mit "·" statt "—" getrennt, weil ein
      reicher `_display_label` (S5) selbst einen Gedankenstrich traegt
      ("Zugang eingeschraenkt — Monts Toulonnais") -- ein zweiter "—" als
      Trenner kollidiert damit und erschwert das schnelle Lesen unterwegs.
      "·" ist bereits das Trennzeichen fuer den Umfang (S4) und etabliert
      damit ein konsistentes Satzzeichen fuer alle Zeilen-Bestandteile."""
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    uniform_scope = _uniform_scope(ordered)
    leading = ordered[0]
    leading_word = _level_word(leading.alert.level, lang)
    pos = _LEVEL_POSITION.get(leading.alert.level, 0)
    kind = t("warnung.kopf.warnstufe" if uniform else "warnung.kopf.hoechste_stufe", lang)
    scope_part = f"{leading.scope_label} · " if (show_scope and uniform_scope) else ""
    head = f"{prefix} · {scope_part}{kind} {leading_word} ({pos}/3)"
    if _is_eaws(leading.alert):
        # Issue #1441: Lagebericht-Stufe statt Awareness-Leiter im Kopf.
        head = (f"{prefix} · {scope_part}{t('warnung.gefahr.avalanche_bulletin', lang)} "
                f"{_rank(leading.alert)}{leading.alert.level_modifier or ''}")
    lines = [f"<b>{_html.escape(head)}</b>"]
    for n in ordered:
        emoji = _level_emoji(n.alert.level)
        scope = "" if (not show_scope or uniform_scope) else f" · {_html.escape(n.scope_label)}"
        body = _html.escape(_display_label(n.alert, lang=lang))
        if n.alert.valid_from and n.alert.valid_to:
            body = f"{body} · {_html.escape(_format_validity(n.alert, tz, lang=lang))}"
        lines.append(f"{emoji} {body}{scope}")
    lines.append(_html.escape(source_label))
    # Issue #1441 (CC BY 4.0): Link zum Bulletin des Warndienstes.
    for n in ordered:
        if _is_eaws(n.alert) and n.alert.url:
            lines.append(_html.escape(n.alert.url))
    notes = official_alert_authority_notes([n.alert for n in ordered], lang=lang)
    lines.extend(_html.escape(note) for note in notes)
    return "\n".join(lines)


def _tag_hour(d: "datetime") -> str:
    """Stundenteil eines Zeit-Tokens (#1929): Minuten nur, wenn sie nicht auf
    ':00' liegen -- '15' bzw. '15:20'. Zwei stundengleiche Fenster kollidieren
    nur, wenn beide Grenzen voll sind; dann sind es dieselben Uhrzeiten. Die
    Regel ist damit pro Token fuer sich entscheidbar (kein Vergleich mit
    anderen Tokens der Nachricht) und kostet nur dort Zeichen, wo sie traegt."""
    return d.strftime("%H:%M") if d.minute else d.strftime("%H")


def _tag_time(alert: "OfficialAlert", tz: "ZoneInfo | None" = None) -> str:
    """Kompakte SMS-Zeitangabe: 'Fr10.07.' (ganztaegig, mit Tag UND Monat) bzw.
    'Sa15-21' -- mit Minuten, wo diese nicht ':00' sind ('Sa15:20-21:40').
    Tagesuebergang (F006): zweites Wochentagskuerzel statt nur der zweiten
    Stunde, z.B. 'Fr22-Sa03' statt des irrefuehrenden 'Fr22-03'.

    Issue #1929: beide Kollisionsquellen gehaertet -- ohne Minuten trugen
    15:00-21:00 und 15:20-21:40 denselben Text, ohne Datum zwei Ganztags-
    Warnungen am selben Wochentag verschiedener Wochen.

    Issue #1929 F002: das Ganztags-Token traegt zusaetzlich den Monat. Der Tag
    im Monat allein bleibt mehrdeutig, sobald derselbe Wochentag mit demselben
    Datum in verschiedenen Monaten auftritt (Sa 14.02. und Sa 14.03. ergaben
    beide 'Sa14.'); das kostet drei Zeichen nur im Ganztags-Fall.

    `tz` (Issue #1216 F001, optional): lokalisiert wie `_format_validity`.

    Issue #1249 Runde 2 F003: fehlt der Gueltigkeitszeitraum, liefert diese
    Funktion "" statt des Platzhalters "?" -- die einzigen beiden Aufrufer
    (`render_official_alert_sms`, beide Zweige) lassen das Zeit-Token dann
    ganz weg (kein doppelter Leerraum, kein sinnfreies "?"), statt einen
    Platzhalter zu senden, der im knappen SMS-Budget nur Zeichen kostet ohne
    Information zu tragen (Gleichlauf mit F001/Mail #1238 AC-7).

    Issue #1948 S5 (PO-Entscheid 3, Nachtrag N-5): beginnt die Gueltigkeit am
    HEUTIGEN Tag (verglichen in `tz`), entfaellt das Wochentagskuerzel VOR der
    Beginnzeit ersatzlos -- 'Do12-22' wird zu '12-22', 'Fr10.07.' zu '10.07.',
    'Fr22-Sa03' zu '22-Sa03'. Das END-Tageskuerzel bleibt in jedem Fall stehen:
    es bezeichnet einen anderen Tag als heute und ist sicherheitsrelevant."""
    if not alert.valid_from or not alert.valid_to:
        return ""
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag = "" if vf.date() == datetime.now(tz).date() else _de_weekday_short(vf)
    if vf.date() != vt.date():
        return f"{tag}{_tag_hour(vf)}-{_de_weekday_short(vt)}{_tag_hour(vt)}"
    if (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59):
        return f"{tag}{vf.strftime('%d.%m')}."
    return f"{tag}{_tag_hour(vf)}-{_tag_hour(vt)}"


def _sms_pack(head: str, tokens: list[str], limit: int, suffix: str = "") -> tuple[str, int]:
    """Budget-Kuerzung analog `render_sms` (Issue #1216 F002): Kopf immer,
    Tokens werden solange behalten wie Kopf + behaltene Tokens + evtl.
    ' +K'-Auslassungsmarker + `suffix` (z.B. die Reichweite) <=limit bleiben.
    Ganze Tokens werden gedroppt, nie mitten im Token abgeschnitten.

    Liefert zusaetzlich die Anzahl behaltener Tokens (#1249 Runde 3, Adversary
    F004 CRITICAL): der Aufrufer `render_official_alert_sms` muss erkennen
    koennen, ob selbst das ERSTE (schwerste) Token nicht mehr hineinpasst, um
    dann die abgestufte Rueckfallebene zu greifen -- statt einer leeren oder
    mitten im Wort abgeschnittenen SMS (`body[:limit]` blieb bisher das
    einzige, unzureichende Sicherheitsnetz)."""
    kept: list[str] = []
    for tok in tokens:
        omitted = len(tokens) - len(kept) - 1
        marker = f" +{omitted}" if omitted > 0 else ""
        candidate = head + " ".join(kept + [tok]) + marker + suffix
        if len(candidate) <= limit:
            kept.append(tok)
        else:
            break
    omitted = len(tokens) - len(kept)
    marker = f" +{omitted}" if omitted > 0 else ""
    body = head + " ".join(kept) + marker + suffix
    return (body if len(body) <= limit else body[:limit]), len(kept)


def _word_boundary_truncate(text: str, limit: int) -> str:
    """Letztes Sicherheitsnetz (#1249 Runde 3, Stufe 4): kuerzt `text` auf
    `limit` Zeichen an einer WORTGRENZE (nie mitten im Wort) und haengt "..."
    an, wenn dadurch gekuerzt wurde. Nur erreichbar, wenn selbst das blanke
    Gefahren-Kuerzel allein (letzte Stufe in `_sms_pack_with_fallback`) das
    Limit sprengt. Seit #1948 S5 ist das praktisch unerreichbar: der Kopf
    darf vorher weggelassen werden (Nachtrag N-3), und der frueher denkbare
    Ausloeser -- ein absurd langer Trip-/Preset-Name als `sms_prefix` --
    existiert nicht mehr. Findet sich KEINE Wortgrenze (das
    "Wort" allein ist schon laenger als `limit`), bleibt als letzter Ausweg
    nur der harte Schnitt -- die einzige Situation, in der die Wortgrenzen-
    Garantie logisch nicht mehr einhaltbar ist, ohne komplett leer zu werden."""
    ellipsis = "..."
    if len(text) <= limit:
        return text
    budget = max(limit - len(ellipsis), 0)
    cut = text[:budget]
    boundary = cut.rfind(" ")
    if boundary > 0:
        return cut[:boundary] + ellipsis
    return text[:limit]


def _sms_leading_variants(code: str, time_part: str, location: str) -> list[str]:
    """Token-Varianten fuer die SCHWERSTE Warnung, reichhaltig -> minimal
    (#1249 Runde 3, Adversary F004 CRITICAL, PO-Zusage woertlich: "muss immer
    mindestens die schwerste Warnung samt Ort enthalten"):

    1. `code` + Zeit + Ort (Normalfall, unveraendert)
    2. `code` + Zeit, OHNE Ort -- lieber ohne Ort als ohne Inhalt
    3. nur `code` -- seit #1948 S5 ist das `{Kuerzel}:{Stufe}`-Token
       (`_sms_hazard_token`), das die Stufe selbst traegt; den frueheren
       Mixed-Level-Zweig mit separatem Stufen-WORT gibt es nicht mehr.

    Liefert IMMER genau 3 Eintraege, auch wenn `location`/`time_part` leer
    sind (dann sind Stufe 1/2 textgleich) -- der Aufrufer `_sms_pack_with_
    fallback` steuert den eigentlichen Rueckfall zusaetzlich ueber die
    vorgelagerte Kopf-Stufe (N-3) und, bei Alt-Aufrufern, ueber `suffix`,
    nicht nur ueber den Token-Text."""
    with_time = f"{code} {time_part}" if time_part else code
    primary = f"{with_time} {location}" if location else with_time
    return [primary, with_time, code]


def _sms_pack_with_fallback(
    head: str, leading_variants: list[str], tail_tokens: list[str],
    limit: int, full_suffix: str,
) -> str:
    """Baut die SMS mit abgestufter Rueckfallebene fuer die schwerste Warnung
    (#1249 Runde 3, Adversary F004 CRITICAL). Ortsnamen sind nutzereingegeben
    und im Modell nicht laengenbegrenzt -- Kopf + Token + Ort kann das Limit
    sprengen. `_sms_truncate` (Vorgaenger) garantierte dafuer KEIN Minimum:
    bei Ueberlauf konnte `kept=[]` werden (SMS ohne jeden Inhalt) oder der
    Ein-Warnung-Fall in `body[:limit]` fallen (Schnitt mitten im Ortsnamen).

    Reihenfolge (PO-Fix-Richtung woertlich): (1) Kopf + Token samt Ort passt
    -> unveraendert senden. (2) Passt nicht -> Ort weglassen, Rest (Kuerzel +
    Zeit) behalten. (3) Passt immer noch nicht -> nur Kopf + Gefahren-Kuerzel.
    (4) Niemals leer, niemals ein Schnitt mitten im Wort.

    `full_suffix` (der geteilte Ortszusatz des uniform-Scope-Zweigs) gilt NUR
    bei Stufe 1 -- er traegt dieselbe Ortsinformation wie ein Token-eigener
    Ort und wird von derselben Stufe (2) entfernt, sonst bliebe der Ort ueber
    den Suffix bestehen, waehrend der Token ihn schon verloren hat.

    Issue #1948 S5 (Nachtrag N-3): seit der Ort im KOPF steht statt im
    droppbaren Suffix, bekommt jede Stufe eine VORGELAGERTE Kopf-Rueckfallebene
    -- passt Kopf + Variante nicht, wird erst der Kopf weggelassen, bevor die
    naechst-aermere Token-Variante greift. Damit ueberleben Gefahr und Stufe
    jede Kopflaenge (Wachhunde: `test_official_alert_channel_scope.py`
    AC-15/AC-16, F004)."""
    for i, variant in enumerate(leading_variants):
        suffix = full_suffix if i == 0 else ""
        for head_variant in dict.fromkeys((head, "")):
            body, kept = _sms_pack(head_variant, [variant] + tail_tokens, limit, suffix)
            if kept >= 1:
                return body
    # Stufe 4: selbst das blanke Kuerzel passt nicht -- praktisch unerreichbar,
    # seit der Kopf weggelassen werden darf.
    minimal = leading_variants[-1]
    return minimal if len(minimal) <= limit else _word_boundary_truncate(minimal, limit)


# Vierstufige SMS-DARSTELLUNGS-Leiter (#1948 S5, Randbedingung 1): eigene,
# lokale Tabelle -- `hazard_symbols.LEVEL_LETTERS` bleibt exakt {2,3,4} und
# damit TABU. Eine Ergaenzung dort um `1: "-"` liesse
# `alert_urgency.urgency_from_official_level(1)` mit `KeyError: '-'` abstuerzen
# (`_LETTER_TO_URGENCY` kennt nur L/M/H).
_SMS_LEVEL_LETTERS: dict[int, str] = {1: "-", 2: "L", 3: "M", 4: "H"}


def _sms_hazard_token(alert: "OfficialAlert", time_part: str) -> str:
    """`{Kuerzel}:{Stufe}[ {Zeit}]` -- die Token-Grammatik, die
    Trip-Briefing-SMS und Nowcast-Alarm bereits sprechen (#1948 S5).
    `access_ban` bleibt als blankes Kuerzel stehen (LEVELLESS_HAZARDS): ein
    binaerer Zustand hat weder Schweregrad noch Stunde."""
    symbol = sms_symbol_for(alert.hazard)
    if alert.hazard in LEVELLESS_HAZARDS:
        return symbol
    if alert.hazard in NUMERIC_LEVEL_HAZARDS:
        # Issue #1441: Originalziffer (`AV5`) -- kein L/M/H, keine Stunde.
        return f"{symbol}{_rank(alert)}"
    letter = _SMS_LEVEL_LETTERS.get(alert.level, "H")
    token = f"{symbol}:{letter}"
    return f"{token} {time_part}" if time_part else token


def render_official_alert_sms(
    notices: list["OfficialAlertNotice"], *, limit: int = 140,
    tz: "ZoneInfo | None" = None,
) -> str:
    """GSM-7/ASCII, <=limit, Zielbild `Seg 4: !TH:L 12-22 HT:L` (#1948 S5).

    EIN Bau-Pfad statt zwei: jedes Token traegt seinen Stufenbuchstaben selbst,
    damit verliert die alte Stufen-Verzweigung (`AMT {WORT}{Pos}/3` vs.
    Stufenwort je Token) ihren Zweck und entfaellt. Uebrig bleibt die
    Umfangs-Verzweigung `_uniform_scope` (geteilt mit Betreff/Headline/
    Quelle-Box, unangetastet): einheitlicher Umfang -> EIN gemeinsamer
    Ortskopf; uneinheitlicher Umfang -> kein Kopf, jedes Token traegt seinen
    eigenen `sms_scope`. Der alte Ortszusatz am Satzende (`suffix`) ist damit
    ueberfluessig -- die Ortsfunktion sitzt vollstaendig im Kopf.

    `sms_prefix` (Trip-/Preset-Name) und der Quellen-Marker `AMT` sind
    ersatzlos entfallen: das Format folgt dem PHAENOMEN, nicht der Quelle.

    `tz` (F001, optional): lokalisiert `_tag_time` wie die anderen Kanaele;
    dieselbe Zeitzone entscheidet auch ueber die "heute"-Regel (N-5).

    Das "!" wird ERST nach der Variantenbildung vorangestellt, damit die
    Rueckfallkette (`_sms_leading_variants`/`_sms_pack_with_fallback`,
    Ort weglassen -> Zeit weglassen -> nur Kuerzel) unveraendert bleibt. Sie
    garantiert weiterhin, dass die schwerste Warnung IMMER mit greifbarem
    Inhalt in der SMS steht (Adversary F004), jetzt zusaetzlich abgesichert
    durch die Kopf-Rueckfallebene (N-3)."""
    from .render import _ascii, _stage_prefix

    ordered = _sort_notices(notices)
    uniform_scope = _uniform_scope(ordered)
    leading = ordered[0]
    # Issue #2122 (AC-5): das Etappen-Praefix ueber ALLE gebuendelten Warnungen
    # dieser SMS -- fehlt es bei irgendeiner, entfaellt es GANZ (AC-8-Muster).
    prefix = _stage_prefix(ordered)

    tokens = [
        _ascii(
            _sms_hazard_token(n.alert, _tag_time(n.alert, tz))
            + ("" if uniform_scope else f" {n.sms_scope}")
        )
        for n in ordered
    ]
    head = f"{prefix}{_ascii(f'{leading.sms_scope}: ')}" if uniform_scope else prefix
    # `access_ban` traegt nie eine Stunde -- auch nicht als Fallback-Variante.
    leading_time = (
        "" if leading.alert.hazard in LEVELLESS_HAZARDS | NUMERIC_LEVEL_HAZARDS
        else _tag_time(leading.alert, tz)
    )
    # ASCII-Konvertierung VOR der Kuerzung (nicht danach), damit die
    # Laengen-Buchhaltung in `_sms_pack` mit der finalen Laenge uebereinstimmt.
    # Nachtrag N-4: die Faltung gilt auch fuer die fuehrenden Varianten -- im
    # uneinheitlichen Umfang tragen sie den nutzereingegebenen Ortsnamen.
    leading_variants = [
        _ascii(f"!{v}")
        for v in _sms_leading_variants(
            _sms_hazard_token(leading.alert, ""), leading_time,
            "" if uniform_scope else leading.sms_scope,
        )
    ]
    return _sms_pack_with_fallback(head, leading_variants, tokens[1:], limit, "")


def _trip_total_segment_ids(trip: "Trip | None") -> list[str]:
    """Segment-IDs '1'..'N' + 'Ziel' fuer die 'gesamte Route'-Erkennung
    (N = Anzahl Wegpunkte - 1, minimal 0).

    Issue #1318 Scheibe B: ohne Trip-Objekt (`None`) ist die Gesamtroute
    unbekannt -> leere Liste. Der Aufrufer verliert damit nur die
    "gesamte Route"-Verdichtung, nie die Warnung selbst."""
    if trip is None:
        return []
    n = max(len(trip.all_waypoints) - 1, 0)
    return [str(i) for i in range(1, n + 1)] + ["Ziel"]


def _measured_km_span(
    segment_ids: list[str], segment_km: dict | None,
) -> tuple[float, float] | None:
    """Gemeinsame, GEMESSENE km-Spanne der betroffenen Segmente (Issue #2036)
    -- oder `None`, sobald auch nur eines der Segmente keine gemessene Spanne
    traegt. Ein Buendel, dessen Ortsangabe zur Haelfte geraten waere, bleibt
    lieber ganz bei der Segment-Sprache (Fallback-Garantie AC-10)."""
    spans = [(segment_km or {}).get(str(s)) for s in segment_ids]
    if not spans or any(s is None for s in spans):
        return None
    return min(s[0] for s in spans), max(s[1] for s in spans)


def build_official_alert_notices(
    trip: "Trip | None", tagged_alerts: list[tuple["OfficialAlert", list[str]]],
    segment_km: dict[str, tuple[float, float]] | None = None,
    stage_number: int | None = None, *, lang: Lang = "de",
) -> list["OfficialAlertNotice"]:
    """Baut die `OfficialAlertNotice`-DTOs fuer den Trip-Standalone-Alarm
    (Issue #1216): dedupliziert via `dedupe_official_alerts`, leitet
    scope_label/sms_scope/Chips aus der Trip-Segmentzahl ab.

    Issue #1239 (AC-13): nach der Identitaets-Dedup buendelt `_bundle_by_hazard_
    level` gleichartige Warnungen (gleicher Typ + gleiche Stufe) zu einer Warnung
    mit vereinigter Segmentliste.

    Issue #2036: `segment_km` (additiv, Default aus) traegt die GEMESSENE
    km-Spanne je Segment-Kennung. Nur damit spricht die amtliche Warnung
    dieselbe Ortssprache wie Nowcast- und Abweichungsalarm (Teilungs-
    Invariante #1744, AC-3) -- die Aufloesung selbst bleibt die EINE geteilte
    Funktion `segments.format_alert_location`, kein zweiter Pfad. Ohne
    Eintrag bleibt es byte-identisch bei "Segment N".

    Issue #2122: `stage_number` (additiv, optional) ist bereits vom Aufrufer
    aufgeloest (`notification_service.send_official_alert` liest den
    tatsaechlich verwendeten rollierenden Anker) -- reist unveraendert auf
    JEDE erzeugte `OfficialAlertNotice`. `None` laesst die Ausgabe
    byte-identisch (Regressions-Invariante)."""
    all_ids = _trip_total_segment_ids(trip)
    deduped = _bundle_by_hazard_level(dedupe_official_alerts(tagged_alerts))
    notices = []
    for alert, segment_ids, regions in deduped:
        # #1233 AC-11: ein Trip mit genau einem Wegpunkt hat keine echten
        # Zwischen-Segmente (`all_ids` kollabiert auf das blosse "Ziel") — jede
        # nicht-leere Warnung deckt dann zwangslaeufig die (triviale) gesamte
        # Route ab, unabhaengig von der genauen uebergebenen Segment-ID.
        is_full = bool(all_ids) and (
            set(segment_ids) >= set(all_ids) or len(all_ids) <= 1
        )
        # Issue #2668: `scope_label`/Chips in ``lang``; `sms_scope` bleibt in
        # jeder Sprache der bisherige Wert (PO-Korrektur 2026-10-31).
        if is_full:
            scope_label, sms_scope = t("warnung.umfang.gesamte_route", lang), "ges.Route"
        else:
            # Issue #2036: dieselbe Aufloesung wie jeder andere Alarm -- die
            # gemessene km-Spanne verdraengt die Segmentnummer, sonst bleibt
            # alles wie bisher.
            _span = _measured_km_span(segment_ids, segment_km)
            if _span is not None:
                scope_label = format_alert_location(
                    None, segment_ids, _span[0], _span[1], km_measured=True,
                )
            else:
                scope_label = format_segment_reference(segment_ids) or t("warnung.zeit.unbekannt")
            # #1948 S5: "Seg 4" statt des Kurzcodes "S4" -- dieselbe
            # Ortssprache, die Trip-Briefing und Nowcast-Alarm sprechen
            # (`render._ascii_alert_location`). Das fruehere "nur "-Praefix bei
            # genau einer Warnung entfaellt ersatzlos (Nachtrag N-2): die
            # PO-Zielbild-Tabelle zeigt den Kopf in BEIDEN Faellen ohne "nur".
            sms_scope = (
                scope_label.replace("Segment ", "Seg ")
                .replace("–", "-")
                .replace("🏁 Ziel", "Ziel")
            )
            if scope_label == t("warnung.zeit.unbekannt"):
                scope_label = t("warnung.zeit.unbekannt", lang)
        if is_full:
            # Volle Route -> ein sauberer Chip statt format_segment_reference()s
            # "N Segmente"-Verdichtung ab >4 Segmenten (Issue #1216 F005).
            affected = [scope_label]
        elif segment_ids:
            affected = [format_segment_reference(segment_ids)]
        else:
            affected = []
        # Befund 1 (#1326a, ADR-0033): die Karte nennt NUR den betroffenen
        # Umfang -- keine durchgestrichenen Chips der uebrigen, nicht
        # betroffenen Segmente (Vorbild: `build_compare_official_alert_notices`
        # setzt `free_chips=[]` bereits fest).
        free: list[str] = []
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=scope_label, sms_scope=sms_scope,
            affected_chips=affected, free_chips=free,
            # scope_total (Nachzug #1239 AC-15): fuer den Trip-Pfad aktuell ohne
            # Wirkung (`_scope_display` nutzt es nur bei scope_kind="locations"),
            # aber konsistent mitgesetzt -- der Builder kennt `all_ids` bereits.
            scope_total=len(all_ids) or None,
            # scope_ids (Adversary F009 Nachzug #1239): identitaets-basierter
            # Umfang -- sortierte Segment-IDs (bzw. alle IDs bei voller Route).
            scope_ids=tuple(sorted(all_ids)) if is_full else tuple(sorted(segment_ids)),
            # regions (Adversary F013 Nachzug #1239 Runde 7): alle Regionen des
            # Buendels (`_bundle_by_hazard_level`s dritter Rueckgabewert).
            regions=regions,
            stage_number=stage_number,  # Issue #2122
        ))
    return notices


def build_compare_official_alert_notices(
    all_location_ids: list[str], id_to_name: dict[str, str],
    tagged_alerts: list[tuple["OfficialAlert", list[str]]], *, lang: Lang = "de",
) -> list["OfficialAlertNotice"]:
    """Baut die `OfficialAlertNotice`-DTOs fuer den Compare-Standalone-Alarm
    (Issue #1216 Slice 2a): dedupliziert via `dedupe_official_alerts`, leitet
    scope_label/sms_scope/Chips aus den betroffenen ORTEN ab (statt
    Segment-IDs wie beim Trip-Pendant `build_official_alert_notices`).
    Die Scope-Rechnung (`is_full`/`affected`/`free`) laeuft durchgaengig ueber
    Orts-**IDs** (F006 -- gleichnamige Orte duerfen nicht als "derselbe Ort"
    kollabieren); `id_to_name` loest IDs erst fuer die Anzeige (Chips/Label)
    in Namen auf, mit stabiler Dedup NUR des Anzeige-Strings.
    `all_location_ids` = alle Orte des Presets; die zweite Komponente jedes
    `tagged_alerts`-Tupels traegt die betroffenen Orts-IDs dieser Warnung.

    Issue #1239 (AC-13): nach der Identitaets-Dedup buendelt `_bundle_by_hazard_
    level` gleichartige Warnungen (gleicher Typ + gleiche Stufe, verschiedene
    Zonen) zu einer Warnung mit vereinigter Ortsliste."""
    all_set = set(all_location_ids)
    deduped = _bundle_by_hazard_level(dedupe_official_alerts(tagged_alerts))
    notices = []
    for alert, affected_ids, regions in deduped:
        affected_set = set(affected_ids)
        affected_ordered_ids = [i for i in all_location_ids if i in affected_set]
        affected = list(dict.fromkeys(id_to_name.get(i, i) for i in affected_ordered_ids))
        is_full = bool(all_set) and affected_set >= all_set
        # Issue #2668: `scope_label` in ``lang``; `sms_scope` in jeder Sprache
        # der bisherige (deutsche) Wert (PO-Korrektur 2026-10-31).
        unbekannt = t("warnung.zeit.unbekannt")
        if is_full:
            scope_label, sms_scope = t("warnung.umfang.alle_orte", lang), "alleOrte"
        elif len(affected) == 1:
            scope_label = t("warnung.umfang.nur", lang, ort=affected[0])
            sms_scope = t("warnung.umfang.nur", ort=affected[0].replace(" ", ""))
        else:
            scope_label = ", ".join(affected) if affected else t("warnung.zeit.unbekannt", lang)
            sms_scope = (", ".join(affected) or unbekannt).replace(" ", "").replace(",", "+") or unbekannt
        # Issue #1238 AC-12: der Ortsvergleich zeigt NUR die betroffenen Orte
        # als Chips -- keine durchgestrichenen freien Orte und kein "übrige
        # Strecke frei"-Hinweistext (der gehoert zur Trip-Route, nicht zu einer
        # Ortsliste). `scope_kind="locations"` laesst den Renderer das Feld mit
        # "Orte:" statt "Route:" beschriften.
        notices.append(OfficialAlertNotice(
            alert=alert, scope_label=scope_label, sms_scope=sms_scope,
            affected_chips=affected, free_chips=[], scope_kind="locations",
            # scope_total (Nachzug #1239 AC-15, PO-Entscheidung): Gesamtzahl der
            # verglichenen Orte -- traegt die Mengenangabe im Betreff/H1 als
            # "N von M Orten" statt der reinen Anzahl "N Orte".
            scope_total=len(all_location_ids) or None,
            # scope_ids (Adversary F009 Nachzug #1239, HIGH): identitaets-
            # basierter Umfang -- sortierte Orts-IDs (bzw. ALLE Orts-IDs bei
            # vollem Umfang), NICHT die (evtl. kollidierenden) Anzeige-Namen.
            # Exakt dieselbe ID-vs-Name-Regel, die diese Funktion bereits fuer
            # `is_full`/`affected`/`free` durchsetzt (#1216 Slice 2a F006).
            scope_ids=tuple(sorted(all_location_ids)) if is_full else tuple(sorted(affected_ordered_ids)),
            # regions (Adversary F013 Nachzug #1239 Runde 7): alle Regionen des
            # Buendels (`_bundle_by_hazard_level`s dritter Rueckgabewert).
            regions=regions,
        ))
    return notices


# ═══════════════ Issue #1441 S2: Entwarnung (ADR-0090) ═══════════════════════
# Nur Daten -- Gefahr, Region/Ort, "Stufe alt → neu" bzw. "beendet". Keine
# Handlungsempfehlung. Warnungen stehen in jeder Nachricht VOR der Entwarnung.


@dataclass(frozen=True)
class OfficialAllClearNotice:
    """Praesentations-DTO einer Entwarnung (Trip und Ortsvergleich)."""
    kind: str  # "lowered" | "ended"
    hazard: str
    hazard_label: str
    region: str
    scope_label: str
    sms_scope: str
    old_rank: int
    new_rank: int
    old_level: int
    new_level: int
    source: str = ""


def build_official_allclear_notices(
    allclears: list, id_to_name: dict | None = None, *, lang: Lang = "de",
) -> list[OfficialAllClearNotice]:
    """Trip (``id_to_name=None``): ``scope_ids`` sind Segment-IDs; Ortsvergleich:
    Orts-IDs, aufgeloest ueber ``id_to_name``. Issue #2668: Anzeige-Texte in
    ``lang``, `sms_scope` in jeder Sprache wie bisher (PO-Korrektur 2026-10-31)."""
    notices = []
    for ac in allclears:
        ids = [str(i) for i in ac.scope_ids]
        if id_to_name is None:
            scope_label = format_segment_reference(ids) if ids else t("warnung.zeile.route", lang)
            sms_label = format_segment_reference(ids) if ids else t("warnung.zeile.route")
            sms_scope = sms_label.replace("Segment ", "Seg ").replace("–", "-").replace("🏁 Ziel", "Ziel")
        else:
            namen = ", ".join(dict.fromkeys(id_to_name.get(i, i) for i in ids))
            scope_label = namen or t("warnung.umfang.ort", lang)
            sms_scope = (namen or t("warnung.umfang.ort")).replace(" ", "").replace(",", "+")
        a = ac.alert
        notices.append(OfficialAllClearNotice(
            kind=ac.kind, hazard=a.hazard, hazard_label=_hazard_word(a.hazard, lang) or a.label,
            region=a.region_label or a.dedup_id or "", scope_label=scope_label,
            sms_scope=sms_scope, old_rank=int(ac.old_rank), new_rank=int(ac.new_rank),
            old_level=int(ac.old_level), new_level=int(ac.new_level), source=a.source,
        ))
    return notices


def _allclear_label(n: OfficialAllClearNotice, lang: Lang) -> str:
    """Gefahr der Entwarnung: Deutsch der Builder-Wert (byte-gleich), sonst das
    Typ-Wort in ``lang`` (die Notice kann in anderer Sprache gebaut sein)."""
    return n.hazard_label if lang == "de" else (_hazard_word(n.hazard, lang) or n.hazard_label)


def _allclear_transition(n: OfficialAllClearNotice, lang: Lang = "de") -> str:
    neu = t("warnung.entwarnung.beendet", lang) if n.kind == "ended" else n.new_rank
    return t("warnung.entwarnung.uebergang", lang, alt=n.old_rank, neu=neu)


def official_allclear_lines(allclears: list[OfficialAllClearNotice], *, lang: Lang = "de") -> list[str]:
    """Je Entwarnung eine Datenzeile: Gefahr · Region · Ort: Übergang."""
    lines = []
    for n in allclears:
        label = _allclear_label(n, lang)
        parts = [label] + [p for p in (n.region, n.scope_label) if p and p != label]
        lines.append(f"{' · '.join(parts)}: {_allclear_transition(n, lang)}")
    return lines


def render_official_allclear_subject_part(
    allclears: list[OfficialAllClearNotice], *, lang: Lang = "de",
) -> str:
    first = allclears[0]
    trans = t("warnung.entwarnung.beendet", lang) if first.kind == "ended" else f"{first.old_rank}→{first.new_rank}"
    more = f" {t('warnung.kopf.weitere', lang, count=len(allclears) - 1)}" if len(allclears) > 1 else ""
    return t("warnung.entwarnung.betreff", lang, gefahr=_allclear_label(first, lang), uebergang=trans) + more


def render_official_allclear_html(allclears: list[OfficialAllClearNotice], *, lang: Lang = "de") -> str:
    """Eigener Abschnitt "Entwarnung" (nach den Warnungen)."""
    if not allclears:
        return ""
    rows = "".join(
        f'<p style="margin:4px 0;font-size:15px;">{_html.escape(line)}</p>'
        for line in official_allclear_lines(allclears, lang=lang)
    )
    return (
        '<div class="entwarnung" style="border:1px solid #d8d3c2;border-radius:6px;'
        'padding:10px 16px;margin:4px 0 16px;">'
        f'<h2 style="font-size:17px;margin:0 0 6px;">'
        f'{_html.escape(t("warnung.entwarnung.wort", lang))}</h2>{rows}</div>'
    )


def render_official_allclear_mail_html(
    allclears: list[OfficialAllClearNotice], *, stand_at: str, source_label: str,
    context_label: str | None = None, lang: Lang = "de",
) -> str:
    """Vollstaendige Mail, wenn der Lauf NUR Entwarnungen traegt."""
    from output.renderers.email.design_tokens import FONT_UI, G_INK, G_INK_FAINT
    from output.renderers.email.helpers import build_origin_footer, render_origin_footer_html

    footer = (
        f'<p class="body-foot" style="font-size:13.5px;color:{G_INK_FAINT};margin:18px 0 0;">'
        f'{_stand_abgerufen(stand_at, _html.escape(source_label), lang, html=True)}</p>'
    )
    origin = render_origin_footer_html(build_origin_footer(
        "official-alert", source=source_label, context_label=context_label, lang=lang,
    ))
    return (
        f'<html><body style="font-family:{FONT_UI};color:{G_INK};">'
        f'{render_official_allclear_html(allclears, lang=lang)}{footer}{origin}</body></html>'
    )


def render_official_allclear_plain(
    allclears: list[OfficialAllClearNotice], *, lang: Lang = "de",
) -> list[str]:
    if not allclears:
        return []
    return ["", t("warnung.entwarnung.wort", lang), *official_allclear_lines(allclears, lang=lang)]


def render_official_allclear_mail_plain(
    allclears: list[OfficialAllClearNotice], *, stand_at: str, source_label: str,
    context_label: str | None = None, lang: Lang = "de",
) -> str:
    from output.renderers.email.helpers import build_origin_footer, render_origin_footer_text

    zeilen = render_official_allclear_plain(allclears, lang=lang)[1:]
    zeilen += ["", _stand_abgerufen(stand_at, source_label, lang), "",
               render_origin_footer_text(build_origin_footer(
                   "official-alert", source=source_label, context_label=context_label, lang=lang,
               ))]
    return "\n".join(zeilen)


def render_official_allclear_telegram(
    allclears: list[OfficialAllClearNotice], *, prefix: str | None = None, lang: Lang = "de",
) -> str:
    """Telegram-Abschnitt; mit ``prefix`` als eigenstaendige Nachricht."""
    wort = t("warnung.entwarnung.wort", lang)
    head = f"{prefix} · {wort}" if prefix else wort
    lines = [f"<b>{_html.escape(head)}</b>"]
    lines += [_html.escape(line) for line in official_allclear_lines(allclears, lang=lang)]
    return "\n".join(lines)


def _allclear_sms_token(n: OfficialAllClearNotice) -> str:
    """`TS:H>L` / `TS:H>0` bzw. numerisch `AV4>2` / `AV4>0` (Spec Abschnitt 7)."""
    symbol = sms_symbol_for(n.hazard)
    if n.hazard in NUMERIC_LEVEL_HAZARDS:
        return f"{symbol}{n.old_rank}>{n.new_rank}"
    old = _SMS_LEVEL_LETTERS.get(n.old_level, "H")
    new = "0" if n.kind == "ended" else _SMS_LEVEL_LETTERS.get(n.new_level, "-")
    return f"{symbol}:{old}>{new}"


def render_official_allclear_sms_block(
    allclears: list[OfficialAllClearNotice], *, with_scope: bool = False,
) -> str:
    """`+`-Block (GSM-7-Basiszeichen): ein `+`, Folgetoken durch Leerzeichen."""
    from .render import _ascii

    tokens = [_allclear_sms_token(n) + (f" {n.sms_scope}" if with_scope else "") for n in allclears]
    return _ascii("+" + " ".join(tokens))


def render_official_alert_sms_with_allclears(
    notices: list["OfficialAlertNotice"], allclears: list[OfficialAllClearNotice], *,
    tz: "ZoneInfo | None", limit: int = 140,
) -> tuple[str, bool]:
    """SMS mit Entwarnungs-Block: ``(text, entwarnung_enthalten)``. Warnungen
    haben Vorrang -- der Block kommt nur hinzu, wenn KEINE Warnung gekuerzt
    wurde und er vollstaendig passt; sonst gilt die Entwarnung auf diesem Kanal
    als nicht zugestellt (AC-12)."""
    from .render import _ascii

    if not notices:
        scopes = {n.sms_scope for n in allclears}
        head = _ascii(f"{allclears[0].sms_scope}: ") if len(scopes) == 1 else ""
        text = head + render_official_allclear_sms_block(allclears, with_scope=len(scopes) > 1)
        return (text, True) if len(text) <= limit else (_word_boundary_truncate(text, limit), False)
    warn = render_official_alert_sms(notices, limit=limit, tz=tz)
    if not allclears:
        return warn, False
    untruncated = render_official_alert_sms(notices, limit=10**6, tz=tz)
    warn_scopes = {n.sms_scope for n in notices}
    with_scope = len(warn_scopes) > 1 or {n.sms_scope for n in allclears} != warn_scopes
    candidate = f"{warn} {render_official_allclear_sms_block(allclears, with_scope=with_scope)}"
    if warn == untruncated and len(candidate) <= limit:
        return candidate, True
    return warn, False
