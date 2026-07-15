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
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from app.models import SegmentWeatherData
    from app.trip import Trip
    from services.official_alerts.models import OfficialAlert

# Level -> (Emoji, Schwere-Wort) fuer den Standalone-Alert-Text (Issue #1172).
# Das Emoji wird ausschliesslich vom Telegram-Renderer emittiert
# (render_official_alert_telegram); alle E-Mail-/SMS-/Subject-Pfade nutzen nur
# das Wort ([1]). Issue #1222: der Plain-Notice-Pfad laesst das Emoji weg.
_LEVEL_WORDS: dict[int, tuple[str, str]] = {
    1: ("🟢", "GRÜN"),
    2: ("🟡", "GELB"),
    3: ("🟠", "ORANGE"),
    4: ("🔴", "ROT"),
}

# Position "N/3" auf der Warnstufen-Leiter GELB->ORANGE->ROT (Issue #1216).
_LEVEL_POSITION: dict[int, int] = {2: 1, 3: 2, 4: 3}

# CSS-Klassenname je Stufe (Design-Vorlage "Alert · Amtliche Warnung", #1233
# Slice B) -- rein strukturell (Klassen tragen keine eigene Farbe im Mail-
# Output, die Farbe kommt ausschliesslich ueber Inline-Style-Tokens, AC-13).
_LEVEL_CLASS: dict[int, str] = {2: "gelb", 3: "orange", 4: "rot"}

# Positions-Wort fuer den `.stufe-hint` (Design-Vorlage, AC-8).
_LEVEL_POSITION_WORD: dict[int, str] = {1: "niedrigste", 2: "mittlere", 3: "höchste"}

# hazard -> (Anzeige, SMS-Kuerzel), Issue #1216 Spec-Tabelle.
_HAZARD_DISPLAY: dict[str, tuple[str, str]] = {
    "extreme_heat": ("Hitze", "HZ"),
    "thunderstorm": ("Gewitter", "TH"),
    "extreme_cold": ("Kälte", "KL"),
    "wind_gust": ("Sturm", "ST"),
    "rain": ("Starkregen", "RR"),
    "snow": ("Schneefall", "SN"),
    "black_ice": ("Glatteis", "GL"),
    "access_ban": ("Zugang gesperrt", "ZG"),
    # Adversary F004 (HIGH, #1239 Nachzug Runde 2): "wildfire_risk" (Quelle
    # meteo_forets.py, Label "Waldbrand-Gefahr — Stufe N") fehlte hier -- ohne
    # Mapping fiel `_hazard_display` auf den ROHEN Quell-Label zurueck,
    # INKLUSIVE "— Stufe N". Das war die Wurzelursache aller vier
    # Doppel-Stufe-Symptome (Standalone-Titel, Betreff, embedded Detail-Banner,
    # Compare-Aggregat-Banner) -- die vier Anzeige-Stellen waren nur Symptome
    # dieser einen fehlenden Zeile.
    "wildfire_risk": ("Waldbrand-Gefahr", "WB"),
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
    # Waldbrand-Gefahrenstufen von Météo-France (services/official_alerts/meteo_forets.py).
    "meteo_forets": "Météo-France (Waldbrand)",
    # Präfektur-Zugangssperren einzelner Wander-Massive bei akuter Waldbrandgefahr
    # (services/official_alerts/massif_closure.py, Quelle risque-prevention-incendie.fr).
    "massif_closure": "Präfektur (Zugangssperre)",
    # Amtliche OGC-EDR-API api.meteoalarm.org (Österreich + Italien, Issue #1086).
    "meteoalarm": "MeteoAlarm",
}


def official_alert_source_label(source: str | None) -> str:
    """source-Kennung -> menschenlesbarer Anzeigename der amtlichen Quelle
    (Issue #1216 AC-7). Exakte Treffer zuerst, dann Substring-Heuristik fuer
    Varianten (`geosphere_*`, `*vigilance*`, `dwd_*`). Unbekannte Quelle ->
    der rohe `source`-String (nie ein falscher hartkodierter Fremd-Absender)."""
    if not source:
        return "Amtliche Quelle"
    key = source.lower()
    if key in _SOURCE_LABELS:
        return _SOURCE_LABELS[key]
    if "geosphere" in key:
        return "GeoSphere Austria"
    if "vigilance" in key or "meteofrance" in key:
        return "Météo-France"
    if "dwd" in key:
        return "DWD"
    return source


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
    # (Default) -> `_standalone_src_html` faellt auf `alert.region_label`
    # zurueck (Alt-Aufrufer/handgebaute Test-Notices ohne dieses Feld,
    # Bestandsverhalten unveraendert).
    regions: tuple[str, ...] = ()


def render_official_alerts_html(
    entries: list[tuple[str, list["OfficialAlert"]]],
    *,
    segment_refs: dict | None = None,
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
    from src.output.renderers.email.design_tokens import (
        FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_INK, G_PAPER, G_SUCCESS,
    )

    _level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}

    badges = []
    for label, alerts in entries:
        for alert in alerts:
            color = _level_colors.get(alert.level, G_ALERT_L4)
            alert_label = _html.escape(alert.label)
            prefix_html = ""
            if label and label != alert.label:
                name = _html.escape(label)
                prefix_html = f'<span style="font-weight:600;">{name}:</span> '
            seg_suffix = ""
            if segment_refs:
                ref = segment_refs.get(id(alert))
                if ref:
                    seg_suffix = f' — {_html.escape(ref)}'
            badges.append(
                f'<div style="background:{G_PAPER};border-left:4px solid {color};'
                f'padding:8px 16px;margin:8px 20px;border-radius:4px;'
                f'font-family:{FONT_UI};font-size:13px;color:{G_INK};">'
                f'{prefix_html}'
                f'<span>{alert_label}{seg_suffix}</span></div>'
            )
    return "".join(badges)


def render_official_alerts_plain(entries: list[tuple[str, list["OfficialAlert"]]]) -> list[str]:
    """Reproduziert das alte `comparison.py`-Plain-Format exakt: eine Zeile
    je Alert, "Amtliche Warnung: {label}" — der Aufrufer haengt Ortsnamen
    bzw. Praefixe (z.B. "   ⚠️ ") selbst davor."""
    lines: list[str] = []
    for _label, alerts in entries:
        for alert in alerts:
            lines.append(f"Amtliche Warnung: {alert.label}")
    return lines


def format_segment_reference(segment_ids: list[str]) -> str:
    """Issue #1200: kompakter Segment-/Etappen-Bezug fuer die Standalone-
    Alert-Mail. Numerische IDs werden sortiert, zusammenhaengende Laeufe als
    Range ('Segment 3–5'), sonst als Aufzaehlung ('Segment 3, 5'). `"Ziel"`
    wird NIE in die numerische Range/Aufzaehlung gemischt, sondern immer als
    eigenes Element '🏁 Ziel' angehaengt. Mehr als 4 betroffene Segmente
    insgesamt -> Verdichtung 'N Segmente' (Begriff bewusst 'Segmente', nicht
    'Etappen')."""
    has_ziel = "Ziel" in segment_ids
    numeric = sorted({int(s) for s in segment_ids if s != "Ziel"})

    total = len(numeric) + (1 if has_ziel else 0)
    if total > 4:
        return f"{total} Segmente"

    numeric_part = ""
    if numeric:
        is_consecutive = numeric == list(range(numeric[0], numeric[-1] + 1))
        if is_consecutive and len(numeric) > 1:
            numeric_part = f"Segment {numeric[0]}–{numeric[-1]}"
        else:
            numeric_part = "Segment " + ", ".join(str(n) for n in numeric)

    if numeric_part and has_ziel:
        return f"{numeric_part}, 🏁 Ziel"
    if has_ziel:
        return "🏁 Ziel"
    return numeric_part


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
    keine Dubletten)."""
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
        key = (ident, a.hazard)
        if key not in best:
            best[key] = a
            segment_ids_by_key[key] = set()
            order.append(key)
        elif a.level > best[key].level:
            best[key] = a
        segment_ids_by_key[key].update(segment_ids)
    return [(best[key], sorted(segment_ids_by_key[key])) for key in order]


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
        key = (a.hazard, a.level, a.label, a.valid_from, a.valid_to)
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
    alerts: list[tuple["OfficialAlert", list[str]]], tz: "ZoneInfo | None" = None,
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
    eigenen Pruef-Werkzeugen ausgewertet)."""
    from utils.timezone import local_fmt

    if tz is None:
        tz = ZoneInfo("UTC")
    fmt = "%a %d.%m. %H:%M"

    lines: list[str] = []
    for a, segment_ids in dedupe_official_alerts(alerts):
        if lines:
            lines.append("")
        # Issue #1222: E-Mail/SMS-Plain-Notice ohne Kreis-Emoji — nur das Wort ([1]).
        word = _LEVEL_WORDS.get(a.level, ("🔴", "ROT"))[1]
        lines.append(f"{word} — {a.label}")
        region_line = f"Region: {a.region_label or 'unbekannt'}"
        if segment_ids:
            region_line += f" — {format_segment_reference(segment_ids)}"
        lines.append(region_line)
        if a.valid_from and a.valid_to:
            lines.append(
                f"Gültig: {local_fmt(a.valid_from, tz, fmt)} – "
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

def _hazard_display(alert: "OfficialAlert") -> tuple[str, str]:
    """hazard -> (Anzeige, SMS-Kuerzel); unbekannt -> (label, erste 2 ASCII-
    Grossbuchstaben aus hazard)."""
    mapped = _HAZARD_DISPLAY.get(alert.hazard)
    if mapped:
        return mapped
    letters = "".join(ch for ch in alert.hazard.upper() if ch.isascii() and ch.isalpha())
    return alert.label, (letters[:2] or "XX")


# Issue #1238 AC-6: numerische Quell-Stufe am Label-Ende ("Waldbrand-Gefahr —
# Stufe 3"). Wird NUR an der Anzeige-Stelle entfernt (Warn-Titel), nie in der
# Quelle (meteo_forets.py) -- die Quell-Labels speisen auch Dedup/SMS.
_SOURCE_LEVEL_SUFFIX = re.compile(r"\s*[—–-]\s*Stufe\s*\d+\s*$")


def _display_label(alert: "OfficialAlert") -> str:
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
    (d) Adversary F001 (HIGH, Regression): greift KEINE der beiden
    Ersetz-Heuristiken UND das Label ist trotzdem ungleich dem Typ-Wort (ein
    voellig eigenstaendiges Label ohne Bezug zum normalisierten Typ, z.B. ein
    externer Trigger-Text) -> das Label darf NICHT verlorengehen. Es wird -
    wie im Bestand vor #1238 - an das Typ-Wort ANGEHAENGT statt verworfen.

    Adversary F002 (MEDIUM, AC-6): die numerische Quell-Stufe am Label-Ende
    ("— Stufe 3") wird IMMER am Ende entfernt -- an ALLEN drei Anzeige-Orten
    (Standalone-Titel, Betreff via `_typ_tag`, embedded WarnBlock rufen alle
    diese Funktion auf), weil die Stufe dort bereits als Eskalations-Meter/
    Stufenwort in derselben Nachricht steht. NUR hier, am Anzeige-Ort -- nie am
    Roh-Label der Quelle oder am Dedup-Schluessel (Regress-Schutz gegen
    #1172/#1200/#1217/#1218, die beide ausschliesslich `alert.label`
    unveraendert nutzen)."""
    typ, _sms = _hazard_display(alert)
    label = alert.label
    if label == typ or not label:
        display = typ
    elif typ in label or "—" in label:
        display = label
    else:
        display = f"{typ} — {label}"
    return _SOURCE_LEVEL_SUFFIX.sub("", display)


def _de_weekday_short(dt: datetime) -> str:
    """DE-Wochentagskuerzel {Mo..So} statt locale-abhaengigem '%a' ('Fri')."""
    return _DE_WEEKDAYS[dt.weekday()]


def _format_validity(alert: "OfficialAlert", tz: "ZoneInfo | None" = None) -> str:
    """'Fr 10.07. · ganztägig' bzw. 'Sa 11.07. · 15:00–21:00'; fehlende Zeiten
    -> 'unbekannt'. Tagesübergang (F006): 'Fr 10.07. · 22:00 – Sa 11.07. 03:00'
    -- beide Daten erscheinen, damit das Ende nicht vor dem Beginn scheint."""
    if not alert.valid_from or not alert.valid_to:
        return "unbekannt"
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag, date_str = _de_weekday_short(vf), vf.strftime("%d.%m.")
    if vf.date() != vt.date():
        tag_to, date_str_to = _de_weekday_short(vt), vt.strftime("%d.%m.")
        return (
            f"{tag} {date_str} · {vf.strftime('%H:%M')} – "
            f"{tag_to} {date_str_to} {vt.strftime('%H:%M')}"
        )
    allday = (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59)
    if allday:
        return f"{tag} {date_str} · ganztägig"
    return f"{tag} {date_str} · {vf.strftime('%H:%M')}–{vt.strftime('%H:%M')}"


def _sort_notices(notices: list["OfficialAlertNotice"]) -> list["OfficialAlertNotice"]:
    """Hoechste Stufe zuerst (level absteigend), bei Gleichstand valid_from aufsteigend."""
    fallback = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(
        notices,
        key=lambda n: (-n.alert.level, n.alert.valid_from or fallback),
    )


def _typ_tag(notice: "OfficialAlertNotice", tz: "ZoneInfo | None" = None) -> str:
    # Titel-Logik: `_display_label` (geteilte Quelle, #1238 AC-4).
    #
    # `tz` (#1233 Nebenbefund AC-12): der Wochentag MUSS dieselbe tz-aware
    # Quelle nutzen wie `_format_validity` im Body -- sonst zeigt der Betreff
    # bei einem Gueltigkeitsbeginn kurz vor Mitternacht einen anderen Wochentag
    # als der Body (Bug: Betreff "(Sa)" roh-UTC vs. Body "So" lokalisiert).
    display = _display_label(notice.alert)
    if notice.alert.valid_from is None:
        return display
    vf = notice.alert.valid_from.astimezone(tz) if tz else notice.alert.valid_from
    return f"{display} ({_de_weekday_short(vf)})"


# Issue #1239 (AC-15/AC-17): ab wie vielen betroffenen Orten die Reichweite als
# Mengenangabe statt als Namensliste erscheint, und wie viele Warnungen Betreff
# und Ueberschrift hoechstens ausschreiben.
_SCOPE_MAX_NAMES = 2
_SUBJECT_MAX_WARNINGS = 2


def _scope_display(notice: "OfficialAlertNotice") -> str:
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
    if notice.scope_label in ("alle Orte", "gesamte Route"):
        return notice.scope_label
    count = len(notice.affected_chips)
    if count > _SCOPE_MAX_NAMES:
        if notice.scope_total:
            return f"{count} von {notice.scope_total} Orten"
        return f"{count} Orte"
    return notice.scope_label


def render_official_alert_subject(
    notices: list["OfficialAlertNotice"], *, prefix: str, tz: "ZoneInfo | None" = None,
) -> str:
    """'[{prefix}] {reichweite} · {Stufe(n)} {Typ (Tag)} + …' — reichweite und
    Stufen-Reihenfolge folgen der fuehrenden (hoechsten) Warnung.

    `tz` (#1233 Nebenbefund AC-12, optional): lokalisiert den Wochentag
    konsistent mit dem Body (`_format_validity`/`render_official_alert_html`).
    Ohne explizite `tz` faellt der Betreff auf Europe/Vienna zurueck (Bestands-
    Default, analog `alert_daily_limit.py`), NICHT mehr auf rohes UTC -- das
    war die Bug-Ursache. Die Versand-Pfade (`notification_service.py`) reichen
    die tatsaechliche, aus den Trip-/Ort-Koordinaten abgeleitete `alert_tz`
    durch, die auch der Body erhaelt.

    Adversary F006 (HIGH, Staging-Fund, proaktiv auch hier gefixt): dieselbe
    Fehlerklasse wie in Quelle-Box/Headline -- im ORTSVERGLEICH
    (`scope_kind="locations"`) ist die Reichweite nur dann die der FUEHRENDEN
    Warnung (`_scope_display(leading)`), wenn ALLE Warnungen denselben Umfang
    haben (`_uniform_scope`). Sonst wuerde der Betreff den Umfang eines
    einzelnen Hazards faelschlich auf alle aufgezaehlten Gefahren-Typen
    verallgemeinern (Staging-Beispiel: "Toulon, Hyères" im Betreff, obwohl eine
    Warnung ausschliesslich Draguignan betraf) -- ein neutraler Platzhalter
    ("mehrere Orte") steht dann an dessen Stelle.

    BEWUSST NICHT fuer den Trip-Pfad (`scope_kind="route"`): dort ist "Segment
    N der fuehrenden Warnung" ein etabliertes, separat getestetes Verhalten
    (`test_official_alert_template_render.py::test_ac3_mixed_levels_highest_
    leads_all_channels`) -- Segment-Angaben sind eine schwaechere Behauptung
    als Ortsnamen (dieselbe Route, kein falscher-Ort-Vorwurf) und werden hier
    bewusst nicht angetastet, um dieses etablierte Verhalten nicht zu brechen.

    AC-16 (Bit-Identitaet bei <=2 Orten/Warnungen) bleibt gewahrt: alle
    bisherigen Testfaelle haben einheitlichen Umfang je Notice-Liste, der neue
    Zweig greift dort nie."""
    if tz is None:
        tz = ZoneInfo("Europe/Vienna")
    ordered = _sort_notices(notices)
    leading = ordered[0]
    uniform = len({n.alert.level for n in ordered}) == 1
    # AC-15: hoechstens zwei Warnungen ausgeschrieben (schwerste zuerst), der
    # Rest als "+N weitere". AC-16: bei <=2 Warnungen bleibt der Betreff
    # bit-identisch (kein Suffix, gleiche Trennzeichen).
    shown = ordered[:_SUBJECT_MAX_WARNINGS]
    omitted = len(ordered) - len(shown)
    more = f" +{omitted} weitere" if omitted > 0 else ""
    if uniform:
        _emoji, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        body = f"{word} " + " + ".join(_typ_tag(n, tz) for n in shown)
    else:
        body = " + ".join(
            f"{_LEVEL_WORDS.get(n.alert.level, ('🔴', 'ROT'))[1]} {_typ_tag(n, tz)}"
            for n in shown
        )
    if leading.scope_kind == "locations" and not _uniform_scope(ordered):
        scope_text = "mehrere Orte"
    else:
        scope_text = _scope_display(leading)
    return f"[{prefix}] {scope_text} · {body}{more}"


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Bestands-Token-Hex -> `rgba(...)` fuer Tint-Hintergruende (Verdict-Pill).
    Nur Token-Farben, nie die Design-Vorlage-Hex (AC-13)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _join_de(items: list[str]) -> str:
    """Deutsche Aufzaehlung: 'A' / 'A und B' / 'A, B und C' (Spec Slice B
    Punkt 2, dedupliziert Wiederholungen bei gleicher Reihenfolge)."""
    deduped = list(dict.fromkeys(items))
    if not deduped:
        return ""
    if len(deduped) == 1:
        return deduped[0]
    return ", ".join(deduped[:-1]) + " und " + deduped[-1]


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
    level_colors: dict[int, str], font_mono: str,
) -> str:
    """`.verdict`-Pill (AC-6): farbiger `.dot` + Anzahl, bei gemischten Stufen
    zusaetzlich '· höchste Stufe {WORT}'."""
    color = level_colors.get(leading_level, level_colors[4])
    css_class = _LEVEL_CLASS.get(leading_level, "rot")
    tint = _hex_to_rgba(color, 0.16)
    extra = "" if uniform else f" · höchste Stufe {leading_word}"
    word = "amtliche Warnung" if n_count == 1 else "amtliche Warnungen"
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
        f'color:{color};">{dot}{n_count} {word}{extra}</div>'
    )


def _standalone_headline_html(ordered: list["OfficialAlertNotice"], uniform: bool) -> str:
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

    types = []
    for n in ordered:
        typ = _html.escape(_display_label(n.alert))
        if not uniform:
            _e, lw = _LEVEL_WORDS.get(n.alert.level, ("🔴", "ROT"))
            typ = f"{typ} ({lw})"
        types.append(typ)
    style = (
        f"font-size:26px;font-weight:700;letter-spacing:-.01em;"
        f"margin:0 0 18px;line-height:1.2;color:{G_INK};"
    )
    types_html = _join_de(types)
    if _uniform_scope(ordered):
        scope = _html.escape(_scope_display(ordered[0]))
        return f'<div class="body-h1" style="{style}">{types_html} für {scope} gemeldet.</div>'
    return f'<div class="body-h1" style="{style}">{types_html} gemeldet.</div>'


def _standalone_ladder_html(active_level: int, level_colors: dict[int, str]) -> str:
    """`.stufe-line` (uniforme Stufe, AC-8): GELB->ORANGE->ROT-Leiter mit
    aktiver Stufe (`.on`) + Positions-Hinweis ('niedrigste/mittlere/höchste
    von drei'). Inline-CSS 1:1 aus der Vorlage (F002); die aktive Stufe
    faerbt sich ueber `_hex_to_rgba` des Bestands-Tokens (AC-13)."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK_FAINT

    pos = _LEVEL_POSITION.get(active_level, 0)
    hint = f"{_LEVEL_POSITION_WORD.get(pos, 'niedrigste')} von drei"
    spans = []
    for i, (lvl, word) in enumerate(((2, "GELB"), (3, "ORANGE"), (4, "ROT"))):
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
        f'font-weight:600;">Warnstufe</span>'
        f'<span class="stufe" style="display:inline-flex;align-items:stretch;'
        f'border:1px solid #d8d3c2;border-radius:999px;overflow:hidden;">'
        f'{"".join(spans)}</span>'
        f'<span class="stufe-hint" style="font-size:13px;color:{G_INK_FAINT};">'
        f'{hint}</span></div>'
    )


def _standalone_bars_meter_html(level: int, color: str) -> str:
    """`.meter`-Baustein je Warnung bei gemischten Stufen (AC-9/AC-13): 3
    `<i>`-Balken, `pos` davon in Bestands-Token-Farbe gefuellt, Rest leer.
    Inline-CSS 1:1 aus der Vorlage (F002), inkl. der bisher fehlenden
    Container-Styles fuer `.meter`/`.bars`."""
    from output.renderers.email.design_tokens import FONT_DATA

    pos = _LEVEL_POSITION.get(level, 0)
    _emoji, word = _LEVEL_WORDS.get(level, ("🔴", "ROT"))
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


def _standalone_warn_type_html(notice: "OfficialAlertNotice") -> str:
    """Warn-Titel der Standalone-Zeile, bereits HTML-escaped (Issue #1238):

    - AC-4: der reichere Quell-Label ERSETZT das Typ-Wort (geteilte Quelle
      `_display_label`), statt es zu wiederholen ("Zugang gesperrt — Zugang
      eingeschraenkt — Maures" war der Bug).
    - AC-6: die numerische Quell-Stufe am Label-Ende ("— Stufe 3") entfaellt,
      weil dieselbe Stufe in derselben Zeile bereits als Eskalations-Meter bzw.
      Stufen-Wort steht ("ORANGE · 2/3"). Adversary F002: die Suffix-Bereinigung
      sitzt in `_display_label` selbst (geteilt fuer alle drei Anzeige-Orte),
      hier also implizit."""
    return _html.escape(_display_label(notice.alert))


def _standalone_facts_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", chips: str, note: str,
    font_data: str, ink: str, ink_faint: str, ink_muted: str,
) -> str:
    """`.facts`-Block der Standalone-Warn-Zeile (Grid UND Stacked):

    - AC-7/AC-8: die "Gültig:"-Zeile entfaellt VOLLSTAENDIG, wenn die Warnung
      keinen Gueltigkeitszeitraum hat (tagesbezogene Zugangssperren, Waldbrand-
      Tagesstufen) -- kein Platzhalter "unbekannt" mehr. Mit Zeiten bleibt sie
      unveraendert.
    - AC-12: Feld-Label "Orte:" im Ortsvergleich (`scope_kind="locations"`),
      "Route:" im Trip-Pfad (unveraendert)."""
    validity = ""
    if notice.alert.valid_from and notice.alert.valid_to:
        validity = (
            f'<span class="k" style="color:{ink_faint};">Gültig:</span> '
            f'<span class="mono" style="font-family:{font_data};font-weight:500;'
            f'color:{ink};">{_format_validity(notice.alert, tz)}</span><br>'
        )
    scope_key = "Orte:" if notice.scope_kind == "locations" else "Route:"
    return (
        f'<div class="facts" style="font-size:14px;color:{ink_muted};line-height:1.5;">'
        f'{validity}'
        f'<span class="k" style="color:{ink_faint};">{scope_key}</span> {chips}{note}'
        f'</div>'
    )


def _standalone_row_border_style(first: bool) -> str:
    """Inline-Ersatz fuer den Geschwister-Selektor `.warn + .warn` der Vorlage
    (Inline-CSS-Mails kennen keine CSS-Kombinatoren): jede Zeile ausser der
    ersten bekommt die Trennlinie `--g-rule-soft` (`#e7e2d3`, konsistent zur
    bereits inline genutzten `.seg`-Border-Farbe) selbst inline mit."""
    return "" if first else "border-top:1px solid #e7e2d3;"


def _standalone_warn_grid_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", *, first: bool = True,
) -> str:
    """`.warn`-Grid-Zeile (uniforme Stufe, Design 'Beispiel A/B'): Typ links,
    Gueltigkeit + Route-Chips rechts (AC-8/AC-10). Freie Chips durchgestrichen
    plus `.route-note`, wenn welche vorhanden sind. Inline-CSS 1:1 aus der
    Vorlage (F002). `first` (Fix-Loop-Nachzug): jede Zeile ausser der ersten
    traegt `border-top` als Inline-Ersatz fuer `.warn + .warn`."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED

    typ = _standalone_warn_type_html(notice)
    chips = "".join(_standalone_chip_html(c, active=True) for c in notice.affected_chips)
    chips += "".join(_standalone_chip_html(c, active=False) for c in notice.free_chips)
    note = ""
    if notice.free_chips:
        free_text = _html.escape(_join_de(notice.free_chips))
        note = (
            f'<div class="route-note" style="font-size:12.5px;color:{G_INK_FAINT};'
            f'margin-top:7px;">übrige Strecke frei — keine amtliche '
            f'Warnung für {free_text}</div>'
        )
    facts = _standalone_facts_html(
        notice, tz, chips, note, FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED,
    )
    return (
        # AC-18: Titel-Spalte von 130px auf 150px verbreitert -- 130px zwang
        # lange Stufen-/Typ-Woerter ("ORANGE") in den Wortumbruch.
        f'<div class="warn" style="display:grid;grid-template-columns:150px '
        f'minmax(0,1fr);gap:14px;padding:14px 16px;align-items:start;'
        f'{_standalone_row_border_style(first)}">'
        f'<div class="lead" style="display:flex;flex-direction:column;gap:6px;">'
        f'<span class="type" style="font-size:15px;font-weight:600;color:{G_INK};">'
        f'{typ}</span></div>'
        f'{facts}</div>'
    )


def _standalone_warn_stacked_html(
    notice: "OfficialAlertNotice", tz: "ZoneInfo | None", color: str, *, first: bool = True,
) -> str:
    """`.warn.stacked` (gemischte Stufen, Design 'Beispiel C', AC-9): eigenes
    Eskalations-Meter + Typ im `.whead`, Route-Chips darunter. Inline-CSS 1:1
    aus der Vorlage (F002). `first` (Fix-Loop-Nachzug): siehe
    `_standalone_warn_grid_html`."""
    from output.renderers.email.design_tokens import FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED

    typ = _standalone_warn_type_html(notice)
    chips = "".join(_standalone_chip_html(c, active=True) for c in notice.affected_chips)
    chips += "".join(_standalone_chip_html(c, active=False) for c in notice.free_chips)
    meter = _standalone_bars_meter_html(notice.alert.level, color)
    facts = _standalone_facts_html(
        notice, tz, chips, "", FONT_DATA, G_INK, G_INK_FAINT, G_INK_MUTED,
    )
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


def _standalone_src_sentence(ordered: list["OfficialAlertNotice"], uniform: bool) -> str:
    """Prosaischer Scope-Satz der `.src`-Box (Spec Slice B Punkt 6) --
    deterministisches Template, keine freie Prosa (bereits HTML-escaped).

    AC-9 (#1238): der Satz darf den Umfang der FUEHRENDEN Warnung nicht mehr
    ueber alle Warnungen verallgemeinern. Haben die Warnungen unterschiedliche
    Umfaenge, verweist ein neutraler Satz auf die Einzelangaben oben. AC-10:
    bei einheitlichem Umfang bleibt der Satz unveraendert."""
    if not _uniform_scope(ordered):
        return (
            "Die Warnungen betreffen unterschiedliche Bereiche — der jeweils "
            "betroffene Umfang steht bei jeder Warnung oben."
        )
    if not uniform:
        leading = ordered[0]
        # Adversary-Nachzug (gleiche Fehlerklasse wie F007, proaktiv mitgefixt):
        # `_display_label` statt des rohen `_hazard_display`-Typwortes, sonst
        # widerspricht dieser Satz demselben Massiv-Titel, der direkt darueber
        # im Warn-Titel steht ("Zugang gesperrt" hier vs. "Zugang eingeschränkt
        # — Monts Toulonnais" im Titel).
        typ = _display_label(leading.alert)
        _e, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        return (
            f"Das {_html.escape(typ)} ({word}) ist die kritischere Warnung "
            "und steht deshalb oben."
        )
    leading = ordered[0]
    scope = leading.scope_label
    scope_html = _html.escape(scope)
    if scope in ("gesamte Route", "alle Orte"):
        subject = "Die Warnung deckt" if len(ordered) == 1 else "Alle Warnungen decken"
        return f"{subject} die {scope_html} ab."
    # Nebenbefund (#1238): der Compare-`scope_label` traegt bei einem einzelnen
    # Ort bereits "nur X" -> ohne diese Bereinigung entstand "Betrifft nur nur
    # Toulon". Das "nur" gehoert genau einmal in den Satz.
    core = scope_html[4:] if scope_html.startswith("nur ") else scope_html
    rest = "nicht alle Orte" if leading.scope_kind == "locations" else "nicht die gesamte Route"
    return f"Betrifft nur {core}, {rest}."


def _standalone_src_html(
    ordered: list["OfficialAlertNotice"], source_label: str, uniform: bool,
    box_bg: str, info_color: str, ink_muted: str, ink: str,
) -> str:
    """`.src`-Box (Spec Slice B Punkt 6): 'Quelle: {Quelle} — {Regionen}.
    {Scope-Satz}'. Regionen dedupliziert (F007-Bestandsschutz).

    Adversary F013 (#1239 Nachzug Runde 7, HIGH): pro Notice werden ALLE
    Regionen ihres Buendels genannt (`n.regions`, von den Buildern aus
    `_bundle_by_hazard_level` gesetzt), nicht nur `n.alert.region_label` des
    Buendel-Repraesentanten -- sonst nennt die Quelle-Box bei einer aus zwei
    Départements gebuendelten Warnung nur EINES ("— Var." statt "— Var,
    Bouches-du-Rhône." fuer eine Warnung, die beide abdeckt: eine falsche
    Zustaendigkeits-Zuordnung, kein blosses Auslassen). Fallback auf
    `alert.region_label`, wenn `n.regions` leer ist (Alt-Aufrufer/handgebaute
    Test-Notices ohne dieses Feld)."""
    regions = []
    for n in ordered:
        rls = n.regions or ((n.alert.region_label,) if n.alert.region_label else ())
        for rl in rls:
            if rl and rl not in regions:
                regions.append(rl)
    region_suffix = f" — {_html.escape(', '.join(regions))}" if regions else ""
    sentence = _standalone_src_sentence(ordered, uniform)
    return (
        f'<div class="src" style="font-size:14px;color:{ink_muted};'
        f'line-height:1.5;background:{box_bg};border-left:3px solid '
        f'{info_color};padding:12px 16px;border-radius:0 4px 4px 0;">'
        f'<b style="color:{ink};font-weight:600;">Quelle:</b> '
        f'{_html.escape(source_label)}{region_suffix}. {sentence}</div>'
    )


def render_official_alert_html(
    notices: list["OfficialAlertNotice"], *, source_label: str, stand_at: str, tz: "ZoneInfo",
) -> str:
    """E-Mail-HTML auf dem SOLL-Design (#1233 Slice B, „Alert · Amtliche
    Warnung"): Verdict-Pill, deterministische Headline, Warnstufen-Leiter
    (uniforme Stufe) bzw. Eskalations-Meter je Warnung (gemischte Stufen),
    Warn-Block mit Route-Chips (frei = durchgestrichen), Quelle-Box, Footer.
    Ausschliesslich Bestands-Farb-Tokens (G_ALERT_L2/L3/L4), keine
    Design-Vorlage-Hex (AC-13)."""
    from output.renderers.email.design_tokens import (
        FONT_DATA, FONT_UI, G_ALERT_L2, G_ALERT_L3, G_ALERT_L4, G_BOX_INFO_BG,
        G_INFO, G_INK, G_INK_FAINT, G_INK_MUTED,
    )

    level_colors = {2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    _emoji, leading_word = _LEVEL_WORDS.get(leading_level, ("🔴", "ROT"))

    verdict = _standalone_verdict_html(
        len(ordered), leading_level, leading_word, uniform, level_colors, FONT_DATA,
    )
    headline = _standalone_headline_html(ordered, uniform)
    ladder = _standalone_ladder_html(leading_level, level_colors) if uniform else ""

    if uniform:
        warns = "".join(
            _standalone_warn_grid_html(n, tz, first=(i == 0))
            for i, n in enumerate(ordered)
        )
    else:
        warns = "".join(
            _standalone_warn_stacked_html(
                n, tz, level_colors.get(n.alert.level, G_ALERT_L4), first=(i == 0),
            )
            for i, n in enumerate(ordered)
        )
    warns_block = (
        f'<div class="warns" style="border:1px solid #d8d3c2;border-radius:6px;'
        f'overflow:hidden;margin:4px 0 16px;">{warns}</div>'
    )

    src = _standalone_src_html(
        ordered, source_label, uniform, G_BOX_INFO_BG, G_INFO, G_INK_MUTED, G_INK,
    )
    footer = (
        f'<p class="body-foot" style="font-size:13.5px;color:{G_INK_FAINT};'
        f'margin:18px 0 0;">Stand: heute {_html.escape(stand_at)} · '
        f'abgerufen bei {_html.escape(source_label)}</p>'
    )
    return (
        f'<html><body style="font-family:{FONT_UI};color:{G_INK};">'
        f'{verdict}{headline}{ladder}{warns_block}{src}{footer}</body></html>'
    )


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


def _render_warn_block_embedded(
    notices: list["OfficialAlertNotice"], *, source_label: str,
    source_url: str | None, tz: "ZoneInfo | None", count_line: str | None,
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

    if not notices:
        return ""

    level_colors = {1: G_SUCCESS, 2: G_ALERT_L2, 3: G_ALERT_L3, 4: G_ALERT_L4}
    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    leading_level = ordered[0].alert.level
    _emoji, leading_word = _LEVEL_WORDS.get(leading_level, ("🔴", "ROT"))
    leading_color = level_colors.get(leading_level, G_ALERT_L4)
    n = len(ordered)

    if count_line is not None:
        count = count_line
    elif uniform:
        pos = _LEVEL_POSITION.get(leading_level, 0)
        count = f"{n} aktiv · Stufe {leading_word} ({pos}/3)"
    else:
        count = f"{n} aktiv · höchste Stufe {leading_word}"

    src_style = (
        "margin-left:auto;font-family:'JetBrains Mono',monospace;"
        "font-size:10.5px;color:#6b6962;text-decoration:none;"
    )
    if source_url:
        src_html = (
            f'<a class="wb-src" href="{_html.escape(source_url)}" '
            f'style="{src_style}">{_html.escape(source_label)} →</a>'
        )
    else:
        src_html = (
            f'<span class="wb-src" style="{src_style}">'
            f'{_html.escape(source_label)}</span>'
        )

    items = []
    for nt in ordered:
        typ, _sms = _hazard_display(nt.alert)
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
            type_display = _display_label(nt.alert)
        if uniform:
            meter, lvl = "", ""
        else:
            _e, lw = _LEVEL_WORDS.get(nt.alert.level, ("🔴", "ROT"))
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
                f'{_format_validity(nt.alert, tz)}</span>'
            )
        items.append(
            f'<div class="wb-item" style="margin:0 0 7px;line-height:1.5;">'
            f'{meter}{lvl}'
            f'<span class="wb-type" style="font-size:14px;font-weight:600;'
            f'color:{G_INK};margin-right:8px;">{_html.escape(type_display)}</span>'
            f'{when}'
            f'<span class="wb-route">{chips}</span>'
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
        f'font-weight:700;color:{leading_color};">Amtliche Warnung</span> '
        f'<span class="wb-count" style="font-family:\'JetBrains Mono\',monospace;'
        f'font-size:11px;font-weight:600;color:{leading_color};margin-left:9px;">'
        f'{_html.escape(count)}</span> {src_html}'
        f'</div>'
        f'<div class="wb-list">{"".join(items)}</div>'
        f'</div></div>'
    )


def render_warn_block(
    notices: list["OfficialAlertNotice"], *, variant: str, source_label: str,
    source_url: str | None = None, stand_at: str | None = None,
    tz: "ZoneInfo | None" = None, count_line: str | None = None,
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
        )
    if variant == "embedded":
        return _render_warn_block_embedded(
            notices, source_label=source_label, source_url=source_url,
            tz=tz, count_line=count_line,
        )
    raise ValueError(f"Unbekannte WarnBlock-variant: {variant!r}")


def render_official_alert_telegram(
    notices: list["OfficialAlertNotice"], *, prefix: str, source_label: str,
    tz: "ZoneInfo | None" = None,
) -> str:
    """Fette erste Zeile + je Warnung eine Zeile, hoechste Stufe zuerst.

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
    _emoji, leading_word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
    pos = _LEVEL_POSITION.get(leading.alert.level, 0)
    kind = "Warnstufe" if uniform else "höchste Stufe"
    scope_part = f"{leading.scope_label} · " if uniform_scope else ""
    head = f"{prefix} · {scope_part}{kind} {leading_word} ({pos}/3)"
    lines = [f"<b>{_html.escape(head)}</b>"]
    for n in ordered:
        emoji, _word = _LEVEL_WORDS.get(n.alert.level, ("🔴", "ROT"))
        scope = "" if uniform_scope else f" · {_html.escape(n.scope_label)}"
        body = _html.escape(_display_label(n.alert))
        if n.alert.valid_from and n.alert.valid_to:
            body = f"{body} · {_html.escape(_format_validity(n.alert, tz))}"
        lines.append(f"{emoji} {body}{scope}")
    lines.append(_html.escape(source_label))
    return "\n".join(lines)


def _tag_time(alert: "OfficialAlert", tz: "ZoneInfo | None" = None) -> str:
    """Kompakte SMS-Zeitangabe: 'Fr' (ganztaegig) bzw. 'Sa15-21'. Tagesuebergang
    (F006): zweites Wochentagskuerzel statt nur der zweiten Stunde, z.B.
    'Fr22-Sa03' statt des irrefuehrenden 'Fr22-03'.

    `tz` (Issue #1216 F001, optional): lokalisiert wie `_format_validity`.

    Issue #1249 Runde 2 F003: fehlt der Gueltigkeitszeitraum, liefert diese
    Funktion "" statt des Platzhalters "?" -- die einzigen beiden Aufrufer
    (`render_official_alert_sms`, beide Zweige) lassen das Zeit-Token dann
    ganz weg (kein doppelter Leerraum, kein sinnfreies "?"), statt einen
    Platzhalter zu senden, der im knappen SMS-Budget nur Zeichen kostet ohne
    Information zu tragen (Gleichlauf mit F001/Mail #1238 AC-7)."""
    if not alert.valid_from or not alert.valid_to:
        return ""
    vf = alert.valid_from.astimezone(tz) if tz else alert.valid_from
    vt = alert.valid_to.astimezone(tz) if tz else alert.valid_to
    tag = _de_weekday_short(vf)
    if vf.date() != vt.date():
        return f"{tag}{vf.strftime('%H')}-{_de_weekday_short(vt)}{vt.strftime('%H')}"
    if (vf.hour, vf.minute, vt.hour, vt.minute) == (0, 0, 23, 59):
        return tag
    return f"{tag}{vf.strftime('%H')}-{vt.strftime('%H')}"


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
        candidate = head + " + ".join(kept + [tok]) + marker + suffix
        if len(candidate) <= limit:
            kept.append(tok)
        else:
            break
    omitted = len(tokens) - len(kept)
    marker = f" +{omitted}" if omitted > 0 else ""
    body = head + " + ".join(kept) + marker + suffix
    return (body if len(body) <= limit else body[:limit]), len(kept)


def _word_boundary_truncate(text: str, limit: int) -> str:
    """Letztes Sicherheitsnetz (#1249 Runde 3, Stufe 4): kuerzt `text` auf
    `limit` Zeichen an einer WORTGRENZE (nie mitten im Wort) und haengt "..."
    an, wenn dadurch gekuerzt wurde. Nur erreichbar, wenn selbst Kopf +
    blankes Gefahren-Kuerzel (Stufe 3 in `_sms_pack_with_fallback`) das Limit
    sprengt -- praktisch nur bei einem absurd langen `sms_prefix` denkbar,
    in der Praxis nicht beobachtet. Findet sich KEINE Wortgrenze (das
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
    3. nur `code` (Gefahren-Kuerzel, im Mixed-Level-Zweig inkl. Stufen-Wort)

    Liefert IMMER genau 3 Eintraege, auch wenn `location`/`time_part` leer
    sind (dann sind Stufe 1/2 textgleich) -- der Aufrufer `_sms_pack_with_
    fallback` steuert den eigentlichen Rueckfall zusaetzlich ueber `suffix`
    (der geteilte Ortszusatz des uniform-Scope-Zweigs), nicht nur ueber den
    Token-Text."""
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
    den Suffix bestehen, waehrend der Token ihn schon verloren hat."""
    for i, variant in enumerate(leading_variants):
        suffix = full_suffix if i == 0 else ""
        body, kept = _sms_pack(head, [variant] + tail_tokens, limit, suffix)
        if kept >= 1:
            return body
    # Stufe 4: selbst das blanke Kuerzel passt nicht neben dem Kopf -- in der
    # Praxis nur bei einem absurd langen `sms_prefix` erreichbar.
    minimal = head + leading_variants[-1]
    return minimal if len(minimal) <= limit else _word_boundary_truncate(minimal, limit)


def render_official_alert_sms(
    notices: list["OfficialAlertNotice"], *, sms_prefix: str, limit: int = 140,
    tz: "ZoneInfo | None" = None,
) -> str:
    """GSM-7/ASCII, <=limit. Einheitliche Stufe: gemeinsamer Kopf + Reichweite
    am Ende. Gemischte Stufen: jede Warnung mit eigenem Stufen-Wort + Segment.
    Bei Ueberlauf werden ganze Tokens gedroppt statt mitten im Token
    abzuschneiden (`_sms_pack`, F002).

    `tz` (F001, optional): lokalisiert `_tag_time` wie die anderen Kanaele.

    Issue #1249 (S1/S2): der gemeinsame Ortszusatz am Ende (`suffix`) galt im
    uniform-STUFE-Zweig fuer ALLE Warnungen, auch wenn diese unterschiedliche
    Umfaenge hatten -- der Empfaenger las ", nur Toulon" und darueber Gefahren,
    die Toulon gar nicht betreffen. Stufe und Umfang sind unabhaengige
    Dimensionen: `_uniform_scope` (geteilt mit Mail/Telegram) entscheidet ueber
    den Ortszusatz. Ist der Umfang uneinheitlich, traegt jedes Token seinen
    eigenen `sms_scope` -- nach demselben Muster, das der mixed-level-Zweig
    schon nutzt -- und der gemeinsame Suffix entfaellt. Das Zeichenbudget
    bleibt bei `_sms_pack` (S2): ganze Tokens fallen vom schwaechsten Ende
    her weg (`+N`), die schwerste Warnung samt Ort bleibt erhalten. Das
    SMS-Kuerzel (`_hazard_display(...)[1]`) bleibt unveraendert (AC-5).

    Issue #1249 Runde 2 F003: fehlt einer Warnung der Gueltigkeitszeitraum,
    liefert `_tag_time` "" statt "?" -- das Zeit-Token entfaellt dann ganz
    (kein sinnfreies "?", spart Zeichen im knappen Budget), statt eines
    Platzhalters.

    Issue #1249 Runde 3 (Adversary F004, CRITICAL): die schwerste Warnung
    durchlaeuft zusaetzlich `_sms_pack_with_fallback` -- eine abgestufte
    Rueckfallebene (Ort weglassen -> nur Kuerzel), die garantiert, dass sie
    IMMER mit greifbarem Inhalt in der SMS steht, auch wenn ein sehr langer
    (nutzereingegebener, im Modell laengenunbegrenzter) Ortsname Kopf + Token
    ueber das Limit treibt."""
    from .render import _ascii

    ordered = _sort_notices(notices)
    uniform = len({n.alert.level for n in ordered}) == 1
    uniform_scope = _uniform_scope(ordered)
    leading = ordered[0]
    if uniform:
        _emoji, word = _LEVEL_WORDS.get(leading.alert.level, ("🔴", "ROT"))
        pos = _LEVEL_POSITION.get(leading.alert.level, 0)
        scopes = ["" if uniform_scope else f" {n.sms_scope}" for n in ordered]
        tokens = []
        for n, scope in zip(ordered, scopes):
            time_part = _tag_time(n.alert, tz)
            token = f"{_hazard_display(n.alert)[1]}"
            if time_part:
                token += f" {time_part}"
            tokens.append(f"{token}{scope}")
        head = f"{sms_prefix} AMT {word}{pos}/3: "
        suffix = f", {leading.sms_scope}" if uniform_scope else ""
        lead_code = _hazard_display(leading.alert)[1]
        lead_time = _tag_time(leading.alert, tz)
        # Bei uniform_scope steckt der Ort im geteilten `suffix`, nicht im
        # Token -- die Fallback-Varianten duerfen ihn dann nicht zusaetzlich
        # in den Ort-Slot des Tokens schreiben (sonst stuende er doppelt).
        lead_location = "" if uniform_scope else leading.sms_scope
    else:
        tokens = []
        for n in ordered:
            time_part = _tag_time(n.alert, tz)
            token = (
                f"{_hazard_display(n.alert)[1]} "
                f"{_LEVEL_WORDS.get(n.alert.level, ('🔴', 'ROT'))[1]}"
            )
            if time_part:
                token += f" {time_part}"
            token += f" {n.sms_scope}"
            tokens.append(token)
        head = f"{sms_prefix} AMT: "
        suffix = ""
        lead_code = (
            f"{_hazard_display(leading.alert)[1]} "
            f"{_LEVEL_WORDS.get(leading.alert.level, ('🔴', 'ROT'))[1]}"
        )
        lead_time = _tag_time(leading.alert, tz)
        lead_location = leading.sms_scope
    # ASCII-Konvertierung VOR der Kuerzung (nicht danach), damit die
    # Laengen-Buchhaltung in `_sms_pack` mit der finalen Laenge uebereinstimmt.
    head, tokens, suffix = _ascii(head), [_ascii(t) for t in tokens], _ascii(suffix)
    lead_code, lead_time = _ascii(lead_code), _ascii(lead_time)
    lead_location = _ascii(lead_location)
    leading_variants = _sms_leading_variants(lead_code, lead_time, lead_location)
    return _sms_pack_with_fallback(head, leading_variants, tokens[1:], limit, suffix)


def _trip_total_segment_ids(trip: "Trip") -> list[str]:
    """Segment-IDs '1'..'N' + 'Ziel' fuer die 'gesamte Route'-Erkennung
    (N = Anzahl Wegpunkte - 1, minimal 0)."""
    n = max(len(trip.all_waypoints) - 1, 0)
    return [str(i) for i in range(1, n + 1)] + ["Ziel"]


def build_official_alert_notices(
    trip: "Trip", tagged_alerts: list[tuple["OfficialAlert", list[str]]],
) -> list["OfficialAlertNotice"]:
    """Baut die `OfficialAlertNotice`-DTOs fuer den Trip-Standalone-Alarm
    (Issue #1216): dedupliziert via `dedupe_official_alerts`, leitet
    scope_label/sms_scope/Chips aus der Trip-Segmentzahl ab.

    Issue #1239 (AC-13): nach der Identitaets-Dedup buendelt `_bundle_by_hazard_
    level` gleichartige Warnungen (gleicher Typ + gleiche Stufe) zu einer Warnung
    mit vereinigter Segmentliste."""
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
        if is_full:
            scope_label, sms_scope = "gesamte Route", "ges.Route"
        else:
            scope_label = format_segment_reference(segment_ids) or "unbekannt"
            sms_scope = (
                scope_label.replace("Segment ", "S")
                .replace("–", "-")
                .replace("🏁 Ziel", "Ziel")
            )
            if len(deduped) == 1:
                sms_scope = f"nur {sms_scope}"
        if is_full:
            # Volle Route -> ein sauberer Chip statt format_segment_reference()s
            # "N Segmente"-Verdichtung ab >4 Segmenten (Issue #1216 F005); keine
            # freien Chips (auch nicht bei der len(all_ids)<=1-Trivialroute).
            affected = ["gesamte Route"]
            free_ids = []
        elif segment_ids:
            affected = [format_segment_reference(segment_ids)]
            free_ids = [i for i in all_ids if i not in segment_ids]
        else:
            affected = []
            free_ids = [i for i in all_ids if i not in segment_ids]
        free = ["🏁 Ziel" if i == "Ziel" else f"Segment {i}" for i in free_ids]
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
        ))
    return notices


def build_compare_official_alert_notices(
    all_location_ids: list[str], id_to_name: dict[str, str],
    tagged_alerts: list[tuple["OfficialAlert", list[str]]],
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
        if is_full:
            scope_label, sms_scope = "alle Orte", "alleOrte"
        elif len(affected) == 1:
            scope_label = f"nur {affected[0]}"
            sms_scope = f"nur {affected[0].replace(' ', '')}"
        else:
            scope_label = ", ".join(affected) if affected else "unbekannt"
            sms_scope = scope_label.replace(" ", "").replace(",", "+") or "unbekannt"
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
