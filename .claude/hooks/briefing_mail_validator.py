#!/usr/bin/env python3
"""
Briefing-Mail-Validator (full + compact) — Issue #733.

Kanonischer Acceptance-Validator fuer Trip-Briefing-Mails. Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand der Marker-Header
X-GZ-Mail-Type / X-GZ-Format deterministisch Typ und Format und prueft sie
format-spezifisch auf Plausibilitaet (nicht bloss String-Presence).

Vorbild: email_spec_validator.py (IMAP-Fetch, Exit 0/1/2, YAML-Log fail-soft).
Stdlib only — als isoliertes Modul ladbar (keine relativen Importe).

Exit codes:
    0 = alle format-spezifischen Checks bestanden (oder Mail ist compare → No-Op)
    1 = Spec-Verletzung mit konkreter Fehlerliste
    2 = technischer Fehler (IMAP nicht erreichbar)
"""
from __future__ import annotations

import argparse
import email
import imaplib
import os
import re
import sys
from email.header import decode_header
from email.message import Message
from pathlib import Path

# Issue #1282 AC-4: shared-repo _log-Aufloesung (git-common-dir) -- gleiches
# Muster wie renderer_mail_gate.py fuer hook_utils (sys.path-Erweiterung fuer
# standalone-Aufruf, kein relativer Import noetig).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _e2e_paths  # noqa: E402
import _validator_log  # noqa: E402  (#1408 F005: kollisionsfreie Log-Ablage)
import _mail_trust  # noqa: E402  (#2961: Absender/DKIM-SPF des eigenen Servers)

# Sequenzielle Stundentabellen-Heuristik: mind. 2 distinct HH:00-Treffer.
_HOUR_RE = re.compile(r"\b([01]?\d|2[0-3]):00\b")
# Compact-Plain: echte Tabellenzeile beginnt (ggf. eingerueckt) mit HH:00.
# Pill-Ereigniszeiten ("Wind ab 00:00 … um 23:00", #795/AC-3/AC-10) stehen
# mitten in der Zeile und sind KEINE Stundentabelle.
_HOUR_LINE_RE = re.compile(r"^\s*([01]?\d|2[0-3]):00(\s|$)", re.MULTILINE)
# Temperatur-Range: "12–18°C" / "12-18°C" / "12–18C" (Halbgeviert oder Bindestrich).
_TEMP_RANGE_RE = re.compile(r"(-?\d{1,2})\s*[–-]\s*(-?\d{1,2})\s*°?C")
_MAX_BYTES_DEFAULT = 2048

_WIND_TOL = 3       # km/h (AC-3)
_SONNE_TOL_MIN = 5  # min (AC-4)


def _ml():
    """Sprach-Hilfe ``_mail_lang`` (Issue #2663), lazy geladen: das Modul bleibt
    ohne Hilfsmodul importierbar (Log-Tests kopieren nur diese Datei)."""
    import _mail_lang

    return _mail_lang


# Issue #2663: Schluessel, an denen die Sprache des Inhalts erkennbar ist.
_LANG_MARKER_KEYS = ["mail.ausblick.spalte_tag", "mail.nacht.am_ziel", "mail.pille.kein_regen"]


class RenderUnavailable(Exception):
    """Playwright/Browser fehlt → Exit 2, nicht Exit 1 (technischer Fehler, AC-1)."""


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def _distinct_hours(text: str, html: bool = False) -> list[str]:
    """Distinct HH:00-Treffer in Reihenfolge des ersten Auftretens.

    Fuer HTML (html=True) werden Pill-Zeiten (mitten im Text) ignoriert, indem
    nur Treffer in <td> oder am Zeilenanfang (mobile <pre>) gewertet werden (#836).
    """
    seen: list[str] = []
    if html:
        # #928: Zeit-Zellen zeigen wieder die reine Stunde `HH` (statt `HH:00`).
        # Damit Datenwerte (z.B. "05 · Ausblick", Temperatur "12") NICHT
        # faelschlich als Stunde zaehlen, gilt eine zweistufige Verankerung:
        #
        #   * BARE `HH` (ohne `:00`) wird NUR an der echten Zeit-Zelle erkannt
        #     (`data-label="Time">`) oder am Zeilenanfang im mobilen <pre>.
        #     Die generischen `<td>`/`>`-Anker sind hier zu breit (bare Zahlen
        #     kommen ueberall vor) und werden bewusst NICHT zugelassen.
        #   * `HH:00` behaelt die breiteren Anker (`<td>`, `>`, fail-soft) —
        #     rueckwaertskompatibel, da `HH:00` ausserhalb von Tabellen selten ist.
        #
        # Der distinct-Key ist in beiden Faellen die reine Stunde, damit `08`
        # und `08:00` als dieselbe Stunde zaehlen.
        bare_pattern = re.compile(
            r'(?:data-label="Time">|(?:\n|^)\s*)([01]?\d|2[0-3])(?:\s|</td>|&nbsp;|<)'
        )
        colon_pattern = re.compile(
            r'(?:data-label="Time">|<td>|>|(?:\n|^)\s*)([01]?\d|2[0-3]):00(?:\s|</td>|&nbsp;|<)'
        )
        for m in colon_pattern.finditer(text):
            h = m.group(1)
            if h not in seen:
                seen.append(h)
        for m in bare_pattern.finditer(text):
            h = m.group(1)
            if h not in seen:
                seen.append(h)
    else:
        for m in _HOUR_RE.finditer(text):
            if m.group(0) not in seen:
                seen.append(m.group(0))
    return seen


def _has_hourly_table(text: str) -> bool:
    """Heuristik: >=2 distinct/sequenzielle HH:00 = Stundentabelle.

    HTML (full): jede Zelle, daher der breite \\bHH:00\\b-Treffer.
    """
    return len(_distinct_hours(text, html=True)) >= 2


def _has_hourly_table_plain(text: str) -> bool:
    """Compact-Plain-Heuristik: >=2 Zeilen, die mit HH:00 BEGINNEN.

    Schaerfer als _has_hourly_table, damit die ausgeschriebenen Pill-
    Ereigniszeiten (mitten in der Zeile, #795) NICHT faelschlich als
    Stundentabelle gewertet werden.
    """
    hours = {m.group(1) for m in _HOUR_LINE_RE.finditer(text)}
    return len([m for m in _HOUR_LINE_RE.finditer(text)]) >= 2 and len(hours) >= 2


def _part_text(part: Message) -> str:
    """Dekodierter Payload eines Parts (bytes→str, fail-soft)."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return part.get_payload() or ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


# Issue #833 — Parser-Helfer (HTML-Struktur statt String-Presence)
_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
# Issue #997 — ganze <table>-Blöcke isolieren, um Header/Zeilen pro Tabelle zu
# scopen. Der Mail-Renderer schachtelt Daten-Tabellen nicht (Stundentabelle(n),
# Trend-Tabelle liegen flach nebeneinander), daher liefert die non-greedy Regex
# pro Tabelle genau einen Block.
_TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.IGNORECASE | re.DOTALL)
_SPAN_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.IGNORECASE | re.DOTALL)
_MOBILE_PRE_RE = re.compile(
    r'class="[^"]*mobile-compact[^"]*".*?<pre[^>]*>(.*?)</pre>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s).strip()


def _th_tokens(html: str) -> list[str]:
    """Alle <th>-Inhalte (Tags gestrippt)."""
    return [_strip_tags(m) for m in _TH_RE.findall(html)]


def _table_blocks(html: str) -> list[str]:
    """Einzelne <table>…</table>-Blöcke (flach, wie der Renderer sie erzeugt).

    Issue #997: Spalten-Checks MÜSSEN pro Tabelle gescoped werden. Sammelte man
    th/td global über das ganze Dokument, mischte sich die Spaltenzahl mehrerer
    Tabellen (Stundentabelle(n) je Etappe vs. 9-spaltige Trend-Tabelle) — der
    Guard `len(cells) == len(headers)` matchte dann gegen die GLOBALE Summe und
    keine reale Zeile passte mehr (stummer False-Negative).

    Issue #1432: byte-identische Blöcke werden DEDUPLIZIERT. Der Renderer
    stellt jede Stundentabelle zweimal ins HTML — Desktop-Fassung und
    Handy-Fassung stammen aus demselben _render_html_table-Aufruf und sind
    byte-gleich, nur die Wrapper-Divs unterscheiden sich. Ohne Dedup fiel
    jede Spalten-SUMME exakt doppelt aus (Beleg: Pill 552 min vs. "Tabelle"
    1104 min). Echte Mehr-Etappen-Tabellen unterscheiden sich immer in den
    Zeitzellen und summieren unverändert.
    """
    seen: set[str] = set()
    blocks: list[str] = []
    for block in _TABLE_RE.findall(html):
        if block not in seen:
            seen.add(block)
            blocks.append(block)
    return blocks


def _hourly_table_blocks(html: str, lang: str = "de") -> list[str]:
    """Wie ``_table_blocks``, aber OHNE den 3-Tages-Ausblick (#2136 Folgebug).

    Seit #2136/ADR-0068 traegt ``render_outlook_table`` dieselben
    ``MetricDefinition.col_label``-Kuerzel wie die Stundentabelle derselben
    Mail (z.B. "Rain", "Wind", "Gust") -- ``_table_blocks()`` liefert also
    BEIDE Tabellenarten mit UEBEREINSTIMMENDEN Spaltennamen zurueck. Ohne
    Trennung mischen ``_column_values``/``_column_hours_sum``/
    ``_column_num_sum`` die TAEGLICHEN Ausblick-Werte in dieselbe Summe wie
    die STUENDLICHEN Etappen-Werte (falscher Massstab; Beleg: die "kein
    Regen"-Pruefung schlug auf einen taeglichen Ausblicks-Regenwert an, den
    die Etappen-Stundentabelle selbst gar nicht enthielt).

    Unterscheidungsmerkmal: der Ausblick traegt in BEIDEN Rendering-Pfaden
    (outlook.py, konfigurierbar wie fest) immer ``Tag`` als allerersten
    th-Text; eine Etappen-Stundentabelle beginnt nie mit ``Tag`` (produktiv
    ``Time``, s. html.py `_render_html_table`). Bloecke ohne th-Zeile
    (leere Tabellen) bleiben erhalten -- kein Filterkriterium.
    """
    day_label = _ml().erwartet("mail.ausblick.spalte_tag", lang)
    return [
        block
        for block in _table_blocks(html)
        if not _th_tokens(block) or _th_tokens(block)[0] != day_label
    ]


def _mobile_header_tokens(html: str) -> list[str]:
    """Erste nicht-leere Zeile im .mobile-compact-<pre>, per Whitespace gesplittet."""
    m = _MOBILE_PRE_RE.search(html)
    if not m:
        return []
    for line in _strip_tags(m.group(1)).splitlines():
        if line.strip():
            return line.split()
    return []


def _column_values(html: str, header_de: str, lang: str = "de") -> list[float]:
    """Numerische Zellwerte der Spalte mit th-Text == header_de (über th-INDEX).

    Mappt NICHT über data-label (kann englisch sein), nur über die Header-Reihe.
    Issue #997: pro <table>-Block gescoped. Nur Blöcke, deren EIGENE th-Reihe
    header_de enthält, tragen bei; innerhalb eines Blocks zählen nur Zeilen,
    deren <td>-Anzahl exakt zur th-Anzahl DIESES Blocks passt (Fremd-/Trend-
    Zeilen mit abweichender Spaltenzahl werden übersprungen). Werte werden über
    ALLE passenden Blöcke aggregiert — Mehr-Etappen-Mails (mehrere Stunden-
    tabellen mit gleichem Header) behalten so ihr Summenverhalten über Etappen.
    """
    values: list[float] = []
    for block in _hourly_table_blocks(html, lang):
        headers = _th_tokens(block)
        try:
            idx = headers.index(header_de)
        except ValueError:
            continue
        for row_html in _ROW_RE.findall(block):
            cells = _TD_RE.findall(row_html)
            if len(cells) != len(headers):
                continue
            num = re.search(r"-?\d+(?:\.\d+)?", _strip_tags(cells[idx]))
            if num:
                values.append(float(num.group(0)))
    return values


def _column_hours_sum(html: str, *header_names: str, lang: str = "de") -> float | None:
    """Summe der ‚X.Y h'-Zellen der Spalte (Sonne). None, wenn keine ‚h'-Zahl.

    Issue #997: pro <table>-Block gescoped (analog _column_values), damit die
    Spaltenzahl der Trend-Tabelle die Stunden-Spalte nicht verfälscht.

    Issue #2104: Die Pill bildet die ETAPPE ab — daher (1) 'Nacht am Ziel'-
    Tabellen ausschließen (fremder Bezugsraum) und (2) jede Stunde nur
    einmal zählen (Dedup über die Zeit-Zelle): die Nahtstunde zwischen zwei
    Segmenten steht bewusst in beiden Segmenttabellen.
    """
    total = 0.0
    found = False
    seen_hours: set[str] = set()
    night = _night_table_blocks(html, lang)
    for block in _hourly_table_blocks(html, lang):
        if block in night:
            continue
        headers = _th_tokens(block)
        idx = next((headers.index(h) for h in header_names if h in headers), None)
        if idx is None:
            continue
        for row_html in _ROW_RE.findall(block):
            cells = _TD_RE.findall(row_html)
            if len(cells) != len(headers):
                continue
            hour_key = _strip_tags(cells[0])
            if hour_key in seen_hours:
                continue
            m = re.search(r"(\d+(?:\.\d+)?)\s*h\b", _strip_tags(cells[idx]))
            if m:
                seen_hours.add(hour_key)
                total += float(m.group(1))
                found = True
    return total if found else None


def _night_table_blocks(html: str, lang: str = "de") -> set[str]:
    """Tabellen der 'Nacht am Ziel'-Sektion (#2104): der Renderer stellt den
    Kopf 'Nacht am Ziel' unmittelbar vor Desktop- UND Mobile-Tabelle."""
    night: set[str] = set()
    night_marker = _ml().marker("mail.nacht.am_ziel", lang)
    prev_end = 0
    for m in _TABLE_RE.finditer(html):
        if night_marker in html[prev_end:m.start()]:
            night.add(m.group(0))
        prev_end = m.end()
    return night


def _column_cells(html: str, *header_names: str, lang: str = "de") -> list[str]:
    """Roh-Zelltexte (Tags gestrippt) der Spalte — für den Emoji-Pfad (#1432).

    Gleiche Scoping-Regeln wie _column_values: pro (dedupliziertem)
    <table>-Block, nur Zeilen mit passender Spaltenzahl.
    """
    cells: list[str] = []
    for block in _hourly_table_blocks(html, lang):
        headers = _th_tokens(block)
        idx = next((headers.index(h) for h in header_names if h in headers), None)
        if idx is None:
            continue
        for row_html in _ROW_RE.findall(block):
            row_cells = _TD_RE.findall(row_html)
            if len(row_cells) != len(headers):
                continue
            cells.append(_strip_tags(row_cells[idx]))
    return cells


def _sun_capacity_minutes(html: str, *header_names: str, lang: str = "de") -> float | None:
    """Obergrenze plausibler Sonnenminuten aus der Emoji-Sonne-Spalte (#1432).

    Im Emoji-Modus trägt die Spalte keine 'X h'-Zahlen; exakt nachrechnen
    lässt sich die Pill dann nicht. Was IMMER gilt: pro Stundenzeile höchstens
    60 min Sonne. Zellen, die sicher (nahezu) keine Sonne bedeuten, senken
    die Obergrenze — ☁️ heißt DNI<=0 (0 min; im DNI-losen Wolken-Fallback
    <=6 min, daher 6), 🌙-Familie ist Nacht (0), '–'/'?' sind Leerwerte (0).
    Alle übrigen Zellen (Sonnen- wie Niederschlags-Emojis — WMO-Codes können
    sonnige DNI-Stunden überdecken) zählen konservativ mit 60 min.
    None, wenn keine Sonne-Spalte gefunden wurde.
    """
    cells = _column_cells(html, *header_names, lang=lang)
    if not cells:
        return None
    cap = 0.0
    for cell in cells:
        if cell in ("", "–", "-", "?") or cell.startswith("🌙"):
            continue
        if cell == "☁️":
            cap += 6.0
            continue
        cap += 60.0
    return cap


def _column_num_sum(html: str, *header_names: str, lang: str = "de") -> float | None:
    """Summe numerischer Zellen der Spalte. None, wenn keiner der Header-Namen
    in irgendeiner Tabelle vorkommt.

    Issue #997: Der erste vorkommende Header-Name gewinnt (unverändertes
    Verhalten); die Summe läuft über das pro-Tabelle gescopte _column_values.
    """
    all_headers = [h for block in _hourly_table_blocks(html, lang) for h in _th_tokens(block)]
    name = next((h for h in header_names if h in all_headers), None)
    if name is None:
        return None
    return sum(_column_values(html, name, lang))


def _pills(html: str) -> list[str]:
    """Pill-Texte aus dem Metriken-Überblick (alle <span>-Inhalte)."""
    return [_strip_tags(s) for s in _SPAN_RE.findall(html)]


def _check_layer_consistency(html: str, lang: str = "de") -> list[str]:
    """AC-3: Pill-Spitzenwert vs. Tabellen-Spalten-Max (Toleranz _WIND_TOL)."""
    errors: list[str] = []
    pill_re = re.compile(
        r"([A-Za-zÄÖÜäöüß]+)\s+ab\s+\d{1,2}:\d{2}.*?(\d+)\s*km/h"
    )
    for pill in _pills(html):
        m = pill_re.search(pill)
        if not m:
            continue
        label, value = m.group(1), float(m.group(2))
        col = _column_values(html, label, lang)
        if not col:
            continue
        col_max = max(col)
        if abs(value - col_max) > _WIND_TOL:
            errors.append(
                f"FULL: Ebenen-Widerspruch '{label}' — Pill {value:g} vs. "
                f"Tabellen-Max {col_max:g} (km/h, > {_WIND_TOL})"
            )
    return errors


def _check_metric_plausibility(html: str, lang: str = "de") -> list[str]:
    """AC-4: Sonne-Pill vs. Σ Sonnenstunden; ‚kein Regen' vs. Regen-Summe."""
    errors: list[str] = []
    for pill in _pills(html):
        m = re.search(r"Sonne\s+(\d+(?:\.\d+)?)h", pill)
        if not m:
            continue
        pill_min = round(float(m.group(1)) * 60)
        sun_h = _column_hours_sum(html, "Sonne", "Sun", lang=lang)
        if sun_h is None:
            # Emoji-Modus (#1432): keine 'X h'-Zahlen — statt (wie früher)
            # blind zu überspringen, greift die Obergrenzen-Prüfung: mehr
            # Sonnenminuten als sonnenfähige Stundenzeilen kann es nicht geben.
            cap = _sun_capacity_minutes(html, "Sonne", "Sun", lang=lang)
            if cap is not None and pill_min > cap + _SONNE_TOL_MIN:
                errors.append(
                    f"FULL: Sonne-Widerspruch (Emoji-Modus) — Pill {pill_min} "
                    f"min > Obergrenze {cap:.0f} min der Sonne-Spalte"
                )
            continue
        if abs(pill_min - sun_h * 60) > _SONNE_TOL_MIN:
            errors.append(
                f"FULL: Sonne-Widerspruch — Pill {pill_min} min vs. Tabelle "
                f"{sun_h * 60:.0f} min (> {_SONNE_TOL_MIN})"
            )

    overview = " ".join(_pills(html))
    no_rain = _ml().erwartet("mail.pille.kein_regen", lang)
    if no_rain in overview:
        rain = _column_num_sum(html, "Regen", "Rain", lang=lang)
        if rain is not None and rain >= 0.1:
            errors.append(
                f"FULL: ‚{no_rain}' widerspricht Tabellen-Summe {rain:g} mm"
            )
    return errors


def _data_visible(page) -> bool:
    """True, wenn bei diesem Viewport eine Wetterdaten-Tabelle sichtbar ist.

    Sichtbar = irgendeine `table[data-table="resp"]` ODER `.mobile-compact` mit
    offsetHeight>0 und display!='none'. Eine flache (nicht responsiv gewrappte)
    Tabelle ist bei jeder Breite sichtbar; nur ein per @media versteckter Block
    ohne Gegenstueck macht den Viewport leer (AC-1, #831-Klasse).

    fix-911-table-jsx AC-1: Tabellen-Marker ist data-table="resp" (kein CSS-class).
    """
    return page.evaluate(
        "()=>{const els=document.querySelectorAll('table[data-table=\"resp\"],.mobile-compact');"
        "for(const el of els){const s=getComputedStyle(el);"
        "if(el.offsetHeight>0 && s.display!=='none') return true;} return false;}"
    )


def _ausblick_visible(page, tag: str) -> bool:
    """#3047 F002: True, wenn eine Ausblick-Tabelle (erste Kopfzelle ``tag``,
    "Tag"/"Day") bei diesem Viewport sichtbar ist -- sie traegt keinen
    ``data-table``-Marker und zaehlt in ``_data_visible`` nicht mit."""
    return page.evaluate(
        "(tag)=>{for(const t of document.querySelectorAll('table')){"
        "const th=t.querySelector('th');if(!th||th.textContent.trim()!==tag) continue;"
        "const s=getComputedStyle(t);if(t.offsetHeight>0 && s.display!=='none') return true;}"
        "return false;}",
        tag,
    )


def _selector_present_and_visible(page, selector: str) -> tuple[bool, bool]:
    """(existiert, sichtbar) fuer einen Selektor im aktuellen Viewport."""
    res = page.evaluate(
        "(sel)=>{const el=document.querySelector(sel);"
        "if(!el) return [false,false];const s=getComputedStyle(el);"
        "return [true, el.offsetHeight>0 && s.display!=='none'];}",
        selector,
    )
    return bool(res[0]), bool(res[1])


def _nur_lokal(route) -> None:
    """#2961: nur ``file:``/``data:`` laden, jede Netzanfrage abbrechen."""
    if route.request.url.startswith(("file:", "data:")):
        route.continue_()
    else:
        route.abort()


def _check_rendered(html: str, daten_erwartet: bool = True,
                    ausblick_tag: str | None = None) -> list[str]:
    """AC-1: headless Render bei 390px und 1000px; Daten muessen sichtbar bleiben.

    ``daten_erwartet=False`` (#3047 J4, nur per ``--konfig``): laut Soll hat die
    Mail keine Stundentabelle (bewusst leer bzw. leere E-Mail-Liste) -- ein
    Viewport ohne Stundentabelle ist dann kein Fehler; die Dual-Render-Pruefung
    bleibt. ``ausblick_tag`` (#3047 F002): laut Soll steht ein Ausblick in der
    Mail -- seine Tabelle (erste Kopfzelle ``ausblick_tag``) muss sichtbar sein.

    Fehlt Playwright/Browser → RenderUnavailable (Exit 2), NICHT Exit 1.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RenderUnavailable(f"Playwright nicht installiert: {e}")
    import tempfile

    errors: list[str] = []
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
    try:
        tmp.write(html)
        tmp.close()
        url = f"file://{tmp.name}"
        ctx = None
        try:
            ctx = sync_playwright().start()
            browser = ctx.chromium.launch(headless=True)
        except Exception as e:
            # Gestarteten Treiber wieder stoppen, sonst blockiert seine Ereignis-
            # schleife jeden spaeteren sync_playwright()-Aufruf im selben Prozess.
            if ctx is not None:
                ctx.stop()
            raise RenderUnavailable(f"Browser-Launch fehlgeschlagen: {e}")
        try:
            wrong = {390: ".desktop-only", 1000: ".mobile-compact"}
            for w, lbl in ((390, "390px (mobil)"), (1000, "1000px (Desktop)")):
                # #2961: Mail-HTML ist fremder Inhalt -- kein JavaScript, kein Netz.
                page = browser.new_page(
                    viewport={"width": w, "height": 844}, java_script_enabled=False,
                )
                page.route("**/*", _nur_lokal)
                page.goto(url, timeout=10000, wait_until="load")
                if daten_erwartet and not _data_visible(page):
                    errors.append(
                        f"FULL: bei {lbl} ist keine Wetterdaten-Tabelle sichtbar "
                        f"(Viewport leer — responsiver Block ohne Gegenstueck?)"
                    )
                if ausblick_tag and not _ausblick_visible(page, ausblick_tag):
                    errors.append(f"SOLL: FULL: bei {lbl} ist keine Ausblick-Tabelle sichtbar")
                exists, visible = _selector_present_and_visible(page, wrong[w])
                if exists and visible:
                    errors.append(
                        f"FULL: bei {lbl} ist '{wrong[w]}' sichtbar — muss bei "
                        f"dieser Breite versteckt sein (Dual-Render, #794)"
                    )
        finally:
            browser.close()
            ctx.stop()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return errors


# --------------------------------------------------------------------------- #
# Format-spezifische Validierung
# --------------------------------------------------------------------------- #
def _validate_full(
    msg: Message, lang: str = "de", erwartet: tuple[bool, bool] = (True, False),
) -> tuple[bool, list[str]]:
    """``erwartet`` = (Stundentabelle, Ausblick) laut Soll (#3047 F002)."""
    stunden_erwartet, ausblick_erwartet = erwartet
    ausblick_tag = _ml().erwartet("mail.ausblick.spalte_tag", lang) if ausblick_erwartet else None
    errors: list[str] = []

    if not msg.is_multipart() or msg.get_content_type() != "multipart/alternative":
        errors.append(
            f"FULL: erwartet multipart/alternative, ist '{msg.get_content_type()}'"
        )

    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    plain_parts = [p for p in msg.walk() if p.get_content_type() == "text/plain"]
    if not html_parts:
        errors.append("FULL: kein text/html-Part vorhanden (multipart/alternative erwartet)")
    if not plain_parts:
        errors.append("FULL: kein text/plain-Part vorhanden")

    html = _part_text(html_parts[0]) if html_parts else ""

    if html and stunden_erwartet and not _has_hourly_table(html):
        errors.append("FULL: keine sequenzielle Stundentabelle (>=2 HH:00-Zeilen) im HTML-Part")

    errors.extend(_check_plausibility(html, lang))

    if html:
        # AC-1 (kann RenderUnavailable werfen)
        errors.extend(_check_rendered(html, stunden_erwartet, ausblick_tag))
        errors.extend(_check_layer_consistency(html, lang))   # AC-3
        errors.extend(_check_metric_plausibility(html, lang))  # AC-4

    if not (msg["Subject"] or "").strip():
        errors.append("FULL: Subject ist leer")

    return len(errors) == 0, errors


def _check_plausibility(html: str, lang: str = "de") -> list[str]:
    """Selbst-Konsistenz der Werte (weit kalibriert gegen False-Positives)."""
    errors: list[str] = []
    ranges = _TEMP_RANGE_RE.findall(html)
    for lo_s, hi_s in ranges:
        lo, hi = int(lo_s), int(hi_s)
        if lo > hi:
            errors.append(f"FULL: Temperatur-Range unplausibel ({lo}°C > {hi}°C)")

    # #974: Der Tagesfenster-Check (06-22) darf die "Nacht am Ziel"-Sektion nicht
    # pruefen — sie zeigt legitim die Stunden von der Ankunft bis 06:00 des
    # Folgetags. Nur der Teil vor dem ersten Marker-Auftreten wird geprueft.
    night_marker = html.find(_ml().marker("mail.nacht.am_ziel", lang))
    day_html = html[:night_marker] if night_marker != -1 else html

    hours = _distinct_hours(day_html, html=True)
    for hour in hours:
        h = int(hour.split(":")[0])
        if h < 6 or h > 22:
            errors.append(f"FULL: Stunde {hour} ausserhalb Tagesfenster 06–22")

    return errors


def _validate_compact(
    msg: Message, max_bytes: int, lang: str = "de", ueberblick: bool = True,
) -> tuple[bool, list[str]]:
    """``ueberblick`` = Metriken-Ueberblick laut Soll (#3047 N5)."""
    errors: list[str] = []

    if msg.is_multipart() or msg.get_content_type() != "text/plain":
        errors.append(
            f"COMPACT: erwartet single text/plain (kein multipart), "
            f"ist '{msg.get_content_type()}' multipart={msg.is_multipart()}"
        )
        # multipart → kein verlaesslicher Plain-Text; frueh raus
        return False, errors

    cte = (msg.get("Content-Transfer-Encoding") or "").strip().lower()
    text = _part_text(msg)

    # Accept quoted-printable when body is ASCII — production MIMEText(us-ascii)
    # emits 7bit; EmailMessage.set_content() may choose quoted-printable for long
    # lines but the decoded content is identical (Issue #733 F002).
    if not text.isascii():
        errors.append("COMPACT: Body ist nicht ASCII (7bit-Verletzung)")
    elif cte and cte not in ("7bit", "quoted-printable"):
        errors.append(f"COMPACT: Content-Transfer-Encoding '{cte}', erwartet 7bit")

    size = len(text.encode("utf-8"))
    if size >= max_bytes:
        errors.append(f"COMPACT: Body {size} Byte >= Limit {max_bytes} Byte (zu gross)")

    if _has_hourly_table_plain(text):
        errors.append("COMPACT: enthaelt sequenzielle Stundentabelle (>=2 HH:00-Zeilen) — verboten")

    errors.extend(_check_compact_blocks(text, lang, ueberblick))

    return len(errors) == 0, errors


def _check_compact_blocks(text: str, lang: str = "de", ueberblick: bool = True) -> list[str]:
    """Pflichtbloecke (HART): Kopf, Metriken-Ueberblick, Footer.

    #3047 N5: bei bewusst leerer Grundauswahl (alle ``enabled: false``, nur
    per ``--konfig`` bekannt) entfaellt der Metriken-Ueberblick -- dann ist
    sein Erscheinen der Fehler, nicht sein Fehlen.

    Ausblick (Wetterlage:/Naechste Etappen) ist OPTIONAL — render_compact()
    laesst ihn bei fehlendem stability_result und leerem multi_day_trend
    legitim weg (Issue #733 F001-Fix).
    """
    errors: list[str] = []
    # #3047 AC-17: Kopfzeile in Nutzersprache („<Trip> - Abend-Briefing" /
    # „<Trip> - Evening Report"), Soll aus dem Katalog statt fest „Report".
    kopf_muster = [_ml().muster(f"mail.kopf.bericht_{art}", lang)
                   for art in ("morning", "evening", "alert", "allgemein")]
    if not any(re.search(m, text) for m in kopf_muster):
        kopf = _ml().erwartet("mail.kopf.bericht_evening", lang, name="Trip")
        errors.append(f"COMPACT: Kopf-Zeile ({kopf}) fehlt")
    pille = "== " + _ml().erwartet("mail.pille.ueberschrift", lang).replace("Ü", "Ue") + " =="
    if ueberblick and pille not in text:
        errors.append(f"COMPACT: Block '{pille}' fehlt")
    elif not ueberblick and pille in text:
        errors.append(f"SOLL: COMPACT: Block '{pille}' erscheint, obwohl die Grundauswahl "
                      "bewusst leer ist bzw. keine gewaehlte Groesse eine Kachel traegt")
    if "----" not in text or "Generated:" not in text:
        errors.append("COMPACT: Footer (Trennlinie + Generated:) fehlt")
    return errors


# --------------------------------------------------------------------------- #
# Issue #3047 (Spec §6): Soll aus der gespeicherten Konfiguration (--konfig)
# --------------------------------------------------------------------------- #
_ZEIT_KOPF_RE = re.compile(r"^ {2}(?:Time|Zeit)(?: +(.*?))?\s*$", re.MULTILINE)
_REPORT_RE = re.compile(r" - (Morning|Evening|Morgen|Abend)(?: Report|-Briefing)")
_REPORT_ART = {"morning": "morning", "evening": "evening", "morgen": "morning", "abend": "evening"}
_FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def _soll_modul():
    """``_soll_aus_konfiguration`` lazy (Modul bleibt ohne ``src`` ladbar)."""
    import _soll_aus_konfiguration

    return _soll_aus_konfiguration


def _ausblick_kuerzel(zeile: str, mit_name: bool = False) -> list[str]:
    """Spaltenkuerzel einer Ausblick-Zeile in Textfolge, ohne Wochentag und
    (Trip-Klartext, ``mit_name``) Etappennamen davor (#3047 F001)."""
    return [k for _pos, k in _soll_modul().ausblick_kuerzel(zeile, mit_name)]


def _block_zeilen(text: str, ueberschrift: str) -> list[str]:
    """Zeilen unter einer Ueberschrift bis zur naechsten Leerzeile."""
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        if zeile.strip() == ueberschrift:
            block = []
            for folge in zeilen[i + 1:]:
                if not folge.strip():
                    break
                if not folge.startswith(" "):
                    block.append(folge)
            return block
    return []


def _soll_html_koepfe(html: str, lang: str) -> tuple[list, list, list]:
    """(Etappen-, Nacht-, Ausblick-Spaltenkoepfe) des HTML-Teils."""
    nacht_bloecke = _night_table_blocks(html, lang)
    tag = _ml().erwartet("mail.ausblick.spalte_tag", lang)
    etappe, nacht, ausblick = [], [], []
    for block in _table_blocks(html):
        th = _th_tokens(block)
        if th and th[0] in ("Time", "Zeit"):
            (nacht if block in nacht_bloecke else etappe).append(
                th[1:-1] if th[-1] in ("Risk", "Risiko") else th[1:])
        elif th and th[0] == tag:
            ausblick.append(th[1:-1] if th[-1] == "ACC" else th[1:])
    return etappe, nacht, ausblick


def _soll_klartext_koepfe(plain: str, lang: str) -> tuple[list, list, list]:
    """(Etappen-, Nacht-, Ausblick-Spalten) des Klartext-Teils."""
    nacht_pos = plain.find(_ml().marker("mail.nacht.am_ziel", lang))
    etappe, nacht = [], []
    for m in _ZEIT_KOPF_RE.finditer(plain):
        spalten = (m.group(1) or "").split()
        (nacht if 0 <= nacht_pos < m.start() else etappe).append(spalten)
    zeilen = _block_zeilen(plain, _ml().erwartet("mail.ausblick.naechste_etappen", lang))
    return etappe, nacht, [_ausblick_kuerzel(z, mit_name=True) for z in zeilen]


def _soll_vergleich(was: str, koepfe: list, soll: list | None) -> list[str]:
    if soll is None:
        return []
    meldungen = []
    for i, ist in enumerate(koepfe):
        diff = _soll_modul().abweichung(ist, soll)
        if diff:
            meldungen.append(f"SOLL: {was} {i + 1}: {diff}")
    return meldungen


def _soll_tabellen(teil: str, etappe: list, nacht: list, ausblick: list, s: dict) -> list[str]:
    fehler = _soll_vergleich(f"Etappen-Stundentabelle ({teil})", etappe, s["stunden"])
    if nacht and not s["nacht"]:
        fehler.append(f"SOLL: Nachttabelle ({teil}) erscheint, obwohl show_night_block aus ist")
    fehler += _soll_vergleich(f"Nachttabelle ({teil})", nacht, s["stunden"])
    if ausblick and not s["ausblick_an"]:
        fehler.append(f"SOLL: Ausblick ({teil}) erscheint, obwohl er laut Konfiguration aus ist")
    elif s["ausblick"] is not None:
        fehler += _soll_vergleich(f"Ausblick ({teil}) Zeile", ausblick, s["ausblick"][
            "html" if teil == "HTML" else "klartext"])
    return fehler


def _soll_ueberblick(html: str, plain: str, s: dict, lang: str) -> list[str]:
    """#3047 F008b (Vollformat): Metriken-Ueberblick genau dann, wenn eine
    gewaehlte Groesse eine Kachel traegt -- im HTML (``<p>``-Ueberschrift) und
    im Klartext (``━━ … ━━``). Kompakt: ``_check_compact_blocks``."""
    titel = _ml().erwartet("mail.pille.ueberschrift", lang)
    fehler = []
    for teil, da in (("HTML", f">{titel}</p>" in html), ("Klartext", f"━━ {titel} ━━" in plain)):
        if s["ueberblick"] and not da:
            fehler.append(f"SOLL: Metriken-Ueberblick fehlt im {teil}-Teil")
        elif da and not s["ueberblick"]:
            fehler.append(f"SOLL: Metriken-Ueberblick ({teil}) erscheint, obwohl keine gewaehlte "
                          "Groesse eine Kachel traegt")
    return fehler


def _soll_kompakt(text: str, s: dict, lang: str) -> list[str]:
    """Kompaktformat: Reihenfolge der Ausblick-Tokens je Tageszeile."""
    ueberschrift = _ml().erwartet("mail.ausblick.naechste_etappen", lang).translate(_FOLD)
    zeilen = [_ausblick_kuerzel(z) for z in _block_zeilen(text, ueberschrift)]
    if zeilen and not s["ausblick_an"]:
        return ["SOLL: Ausblick (Kompakt) erscheint, obwohl er laut Konfiguration aus ist"]
    if s["ausblick"] is None or s["ausblick"]["fest"]:
        return []
    fehler = _soll_vergleich("Ausblick (Kompakt) Zeile", zeilen, s["ausblick"]["klartext"])
    # #3047 N7: Roh/Einfach je Ausblick-Spalte auch im Kompaktformat (ASCII:
    # "0Line" ist die Spalte "0°Line"; Einfach = Wort, Roh = Zahl).
    ascii_ = _soll_modul()._ASCII_KUERZEL
    zellen = [[(ascii_.get(k, k), wert) for k, wert in z]
              for z in _ausblick_zellen(_block_zeilen(text, ueberschrift))]
    return fehler + [m.replace("(Klartext)", "(Kompakt)") for m in _darstellung_meldungen(
        "Ausblick", [zellen], s["ausblick"]["formen"], "Klartext", False)]


_AMPELPUNKT_RE = re.compile(r"<span[^>]*border-radius:\s*50%", re.IGNORECASE)
_FORM_NAME = {"zahl": "Zahl (Roh)", "wort": "Symbol/Wort (Einfach)", "ampel": "Ampelpunkt (Einfach)"}


def _zellform(zelle: str, html: bool) -> str | None:
    """Form einer Zelle: ``ampel`` / ``zahl`` / ``wort``; leer bzw. "–" = None."""
    if html and _AMPELPUNKT_RE.search(zelle):
        return "ampel"
    text = _strip_tags(zelle) if html else zelle.strip()
    if not text or text in ("–", "-", "—"):
        return None
    return "zahl" if re.search(r"\d", text) else "wort"


def _darstellung_meldungen(was: str, tabellen: list, formen: dict, teil: str, html: bool) -> list[str]:
    """``tabellen``: je Tabelle eine Liste Zeilen aus (Spalte, Zelle). Meldet je
    Tabelle und Spalte die erste Zelle in falscher Form, mit Spaltennamen."""
    meldungen = []
    for i, zeilen in enumerate(tabellen):
        gemeldet: set[str] = set()
        for spalte, zelle in (paar for zeile in zeilen for paar in zeile):
            erlaubt = (formen.get(spalte) or {}).get(teil)
            form = _zellform(zelle, html)
            if erlaubt is None or form is None or form in erlaubt or spalte in gemeldet:
                continue
            gemeldet.add(spalte)
            soll = " oder ".join(_FORM_NAME[f] for f in erlaubt)
            meldungen.append(f"SOLL: Darstellung {was} ({teil}) {i + 1}: Spalte '{spalte}' soll "
                             f"{soll} zeigen, zeigt {_FORM_NAME[form]} ('{_strip_tags(zelle)}')")
    return meldungen


def _html_zellen(html: str, lang: str) -> dict[str, list]:
    """Zellen je Tabellenart des HTML-Teils: {art: [[(Spalte, Zelle), ...] je Zeile] je Tabelle}."""
    nacht_bloecke = _night_table_blocks(html, lang)
    tag = _ml().erwartet("mail.ausblick.spalte_tag", lang)
    arten: dict[str, list] = {"Etappen-Stundentabelle": [], "Nachttabelle": [], "Ausblick": []}
    for block in _table_blocks(html):
        th = _th_tokens(block)
        if not th or th[0] not in ("Time", "Zeit", tag):
            continue
        art = "Ausblick" if th[0] == tag else (
            "Nachttabelle" if block in nacht_bloecke else "Etappen-Stundentabelle")
        zeilen = [list(zip(th[1:], _TD_RE.findall(r)[1:])) for r in _ROW_RE.findall(block)]
        arten[art].append([z for z in zeilen if z])
    return arten


def _klartext_zellen(plain: str, lang: str) -> dict[str, list]:
    """Wie ``_html_zellen`` fuer den Klartext: Stundentabellen ueber die
    Spaltenpositionen der Kopfzeile, Ausblick ueber die Kuerzel je Zeile."""
    nacht_pos = plain.find(_ml().marker("mail.nacht.am_ziel", lang))
    arten: dict[str, list] = {"Etappen-Stundentabelle": [], "Nachttabelle": [], "Ausblick": []}
    zeilen = plain.splitlines()
    for m in _ZEIT_KOPF_RE.finditer(plain):
        nr = plain.count("\n", 0, m.start())
        kopf = [(k.start(), k.group()) for k in re.finditer(r"\S+", zeilen[nr])][1:]
        tabelle = []
        for zeile in zeilen[nr + 2:]:
            if not re.match(r"^ {2}\d{2}\b", zeile):
                break
            grenzen = [p for p, _k in kopf] + [len(zeile)]
            tabelle.append([(k, zeile[p:grenzen[j + 1]]) for j, (p, k) in enumerate(kopf)])
        (arten["Nachttabelle"] if 0 <= nacht_pos < m.start() else arten["Etappen-Stundentabelle"]).append(tabelle)
    arten["Ausblick"].append(_ausblick_zellen(
        _block_zeilen(plain, _ml().erwartet("mail.ausblick.naechste_etappen", lang)), mit_name=True))
    return arten


def _ausblick_zellen(zeilen: list[str], mit_name: bool = False) -> list[list]:
    """Ausblick-Zeilen (Klartext/Kompakt) -> je Zeile [(Kuerzel, Wert), ...]."""
    ausblick = []
    for zeile in zeilen:
        treffer = _soll_modul().ausblick_kuerzel(zeile, mit_name)
        grenzen = [p for p, _k in treffer] + [len(zeile)]
        ausblick.append([(k, zeile[p + len(k):grenzen[j + 1]].strip().split("  ")[0])
                         for j, (p, k) in enumerate(treffer)])
    return ausblick


def _soll_darstellung(html: str, plain: str, s: dict, lang: str) -> list[str]:
    """Nachpruefung #3047 Punkt 5: Roh/Einfach je Spalte (Spec §2 Punkt 3) in
    Stunden-, Nacht- und Ausblick-Tabelle, im HTML- und im Klartext-Teil."""
    ausblick = (s.get("ausblick") or {}).get("formen") or {}
    formen = {"Etappen-Stundentabelle": s.get("formen_stunden") or {},
              "Nachttabelle": s.get("formen_stunden") or {}, "Ausblick": ausblick}
    fehler = []
    for teil, arten, ist_html in (("HTML", _html_zellen(html, lang), True),
                                  ("Klartext", _klartext_zellen(plain, lang), False)):
        for art, tabellen in arten.items():
            fehler += _darstellung_meldungen(art, tabellen, formen[art], teil, ist_html)
    return fehler


#: Kompassrichtungen der Wind-Zelle (``utils.geo.degrees_to_compass``, EN und DE).
_KOMPASS_RE = re.compile(r"(?<![A-Za-z])(?:N|NE|NO|E|O|SE|SO|S|SW|W|NW)(?![A-Za-z])")


def _soll_windrichtung(html: str, plain: str, s: dict, lang: str) -> list[str]:
    """#3047 F004: Windrichtung angehakt und mit Wind verschmolzen (keine
    eigene WDir-Spalte) -> jede Wind-Zelle der Etappen- und Nachttabelle traegt
    eine Kompassrichtung, im HTML (auch neben dem Ampelpunkt) wie im Klartext."""
    if not s.get("wind_richtung"):
        return []
    wind = _soll_modul()._REG["wind"].col_label
    fehler = []
    for teil, arten, ist_html in (("HTML", _html_zellen(html, lang), True),
                                  ("Klartext", _klartext_zellen(plain, lang), False)):
        for art in ("Etappen-Stundentabelle", "Nachttabelle"):
            for i, zeilen in enumerate(arten[art]):
                ohne = next((z for zeile in zeilen for k, z in zeile if k == wind
                             and _zellform(z, ist_html) is not None
                             and not _KOMPASS_RE.search(_strip_tags(z) if ist_html else z)), None)
                if ohne is not None:
                    fehler.append(f"SOLL: Windrichtung {art} ({teil}) {i + 1}: Wind-Zelle ohne "
                                  f"Kompassrichtung ('{_strip_tags(ohne).strip()}'), obwohl "
                                  "wind_direction mit Wind verschmolzen ist")
    return fehler + _windrichtung_paritaet(html, plain, wind, lang)


def _richtungen(tabelle: list, wind: str, ist_html: bool) -> list[str]:
    """Kompassrichtung je Wind-Zelle einer Tabelle ("" = keine)."""
    folge = []
    for zeile in tabelle:
        for k, z in zeile:
            if k == wind:
                treffer = _KOMPASS_RE.search(_strip_tags(z) if ist_html else z)
                folge.append(treffer.group() if treffer else "")
    return folge


def _windrichtung_paritaet(html: str, plain: str, wind: str, lang: str) -> list[str]:
    """#3047 F004: dieselbe Richtung je Stunde im HTML wie im Klartext."""
    h_arten, p_arten = _html_zellen(html, lang), _klartext_zellen(plain, lang)
    fehler = []
    for art in ("Etappen-Stundentabelle", "Nachttabelle"):
        if len(h_arten[art]) != len(p_arten[art]):
            continue  # Tabellenzahl prueft der Spaltenabgleich
        for i, (h, p) in enumerate(zip(h_arten[art], p_arten[art])):
            rh, rp = _richtungen(h, wind, True), _richtungen(p, wind, False)
            if rh != rp:
                fehler.append(f"SOLL: Windrichtung {art} {i + 1}: HTML {rh} ungleich Klartext {rp}")
    return fehler


def _verwaist_klartext(plain: str, lang: str) -> list[str]:
    """Etappen-/Ziel-/Nacht-Ueberschrift im Klartext ohne Stundentabelle bis
    zur naechsten Leerzeile (Fehler-Etappen mit Hinweistext ausgenommen)."""
    nacht = re.escape(_ml().marker("mail.nacht.am_ziel", lang))
    kopf = re.compile(rf"^━━ (?:Segment \S+:|\U0001f3c1 |{nacht}).*━━$")
    hinweis = _ml().erwartet("mail.segment.fehler_detail", lang)
    zeilen, fehler = plain.splitlines(), []
    for i, zeile in enumerate(zeilen):
        if not kopf.match(zeile):
            continue
        block = []
        for folge in zeilen[i + 1:]:
            if not folge.strip():
                break
            block.append(folge)
        if not any(_ZEIT_KOPF_RE.match(z) or hinweis in z for z in block):
            fehler.append(f"SOLL: verwaiste Ueberschrift (Klartext) '{zeile.strip('━ ')}' "
                          "ohne Stundentabelle")
    return fehler


def _verwaist_html(html: str, lang: str) -> list[str]:
    """Wie ``_verwaist_klartext`` fuer den HTML-Teil: zwischen einer Etappen-,
    Ziel- oder Nacht-Ueberschrift und der naechsten muss eine Tabelle mit
    Kopfzelle Zeit/Time stehen."""
    nacht = re.escape(_ml().marker("mail.nacht.am_ziel", lang))
    ziel = re.escape(_ml().erwartet("mail.ziel.titel", lang))
    kopf = re.compile(rf">(SEG [^<]+)</span>|>(SEG [^<]*·[^<]*)</div>|>({ziel})</div>|(🌙 {nacht}[^<]*)<")
    treffer = list(kopf.finditer(html))
    fehler = []
    for j, m in enumerate(treffer):
        ende = treffer[j + 1].start() if j + 1 < len(treffer) else len(html)
        tabellen = [_th_tokens(b) for b in _table_blocks(html[m.end():ende])]
        if not any(th and th[0] in ("Time", "Zeit") for th in tabellen):
            titel = next(g for g in m.groups() if g)
            fehler.append(f"SOLL: verwaiste Ueberschrift (HTML) '{titel}' ohne Stundentabelle")
    return fehler


def _soll_report(msg: Message, soll: dict) -> dict:
    """Soll des Reports (Morgen/Abend), den die Mail laut Kopf/Betreff traegt."""
    teile = {p.get_content_type(): _part_text(p) for p in msg.walk()
             if p.get_content_type() in ("text/html", "text/plain")}
    report = _REPORT_RE.search(teile.get("text/plain", "") or teile.get("text/html", "")
                               or _decode_subject(msg["Subject"]))
    return soll["je_report"][_REPORT_ART[report.group(1).lower()] if report else "evening"]


def _tabellen_erwartet(msg: Message, soll: dict | None) -> tuple[bool, bool]:
    """#3047 J4/F002: (Stundentabelle, Ausblick) laut Soll. Ohne ``--konfig``
    bleibt die Stundentabelle Pflicht (sichtbar), der Ausblick ungeprueft.
    Bewusst leer bzw. leere E-Mail-Liste (Stunden ``[]``) -> die Stundentabelle
    entfaellt (J3); ein erwarteter Ausblick muss dann selbst sichtbar sein --
    die Sichtbarkeit der Stundentabellen haengt nie am Ausblick."""
    if soll is None or soll.get("kontext") != "trip":
        return True, False
    s = _soll_report(msg, soll)
    return s["stunden"] != [], bool(s["ausblick_an"])


def pruefe_soll(msg: Message, soll: dict, lang: str = "de") -> list[str]:
    """Issue #3047 AC-19: Auswahl und Reihenfolge der Mail gegen das Soll aus der
    gespeicherten Trip-Konfiguration (``_soll_aus_konfiguration``). Prueft die
    Spaltenfolge jeder Etappen-Stundentabelle, der Nachttabelle und des
    Ausblicks im HTML- UND im Klartext-Teil, im Kompaktformat die Folge der
    Ausblick-Tokens. Jede Meldung nennt die abweichende Spalte."""
    if soll.get("kontext") != "trip":
        return ["SOLL: --konfig ist keine Trip-Konfiguration (Orte: email_spec_validator.py)"]
    teile = {p.get_content_type(): _part_text(p) for p in msg.walk()
             if p.get_content_type() in ("text/html", "text/plain")}
    html, plain = teile.get("text/html", ""), teile.get("text/plain", "")
    s = _soll_report(msg, soll)
    fehler = []
    if msg["X-GZ-Format"] != s["email_format"]:
        fehler.append(f"SOLL: Format '{msg['X-GZ-Format']}' statt '{s['email_format']}' (email_format)")
    if msg["X-GZ-Format"] == "compact":
        return fehler + _soll_kompakt(plain, s, lang)
    koepfe_html = _soll_html_koepfe(html, lang)
    koepfe_plain = _soll_klartext_koepfe(plain, lang)
    for name, h, p in zip(("Etappen-Stundentabelle", "Nachttabelle", "Ausblick"), koepfe_html, koepfe_plain):
        if bool(h) != bool(p):
            fehler.append(f"SOLL: {name} fehlt im {'Klartext' if h else 'HTML'}-Teil")
    fehler += _soll_ueberblick(html, plain, s, lang)
    fehler += _soll_tabellen("HTML", *koepfe_html, s)
    fehler += _soll_tabellen("Klartext", *koepfe_plain, s)
    # #3047 N7: keine Ueberschrift ohne Tabelle ("Segment 1"/"Nacht am Ziel"
    # bei bewusst leerer Auswahl) -- dann muss der ganze Abschnitt entfallen.
    fehler += _verwaist_html(html, lang) + _verwaist_klartext(plain, lang)
    return fehler + _soll_darstellung(html, plain, s, lang) + _soll_windrichtung(html, plain, s, lang)


# --------------------------------------------------------------------------- #
# Oeffentliche API
# --------------------------------------------------------------------------- #
def validate_message(
    msg: Message, max_bytes: int = _MAX_BYTES_DEFAULT, warnungen: list | None = None,
    soll: dict | None = None,
) -> tuple[bool, list[str]]:
    """Faellt das Urteil ueber ein geparstes email.message.Message-Objekt.

    Returnt (ok, errors). ok=True/errors=[] bei bestanden. Issue #2663: die
    Erwartungen gelten in der Sprache des Kopfes ``X-GZ-Lang``; fehlt er, ist
    das seit A2 (#2681) ein Fehler.
    """
    mail_type = msg["X-GZ-Mail-Type"]

    if mail_type is None:
        return False, [
            "Marker-Header X-GZ-Mail-Type fehlt — Mail nicht vom getaggten Renderer"
        ]

    if mail_type in ("compare", "deviation-alert"):
        # Issue #1282 AC-2: No-Op ist KEIN Pass — ein wirkungsloser Validator-
        # Lauf darf vom Renderer-Mail-Gate nie als Nachweis gewertet werden.
        # _write_validation_log() erkennt den Marker "uebersprungen" und
        # schreibt zusaetzlich skipped: true (Diagnose, kein Ersatz-Nachweis).
        return False, [
            f"Keine Trip-Briefing-Mail (Typ={mail_type}) — falscher Validator, uebersprungen"
        ]

    if mail_type != "trip-briefing":
        return False, [f"Unbekannter Mail-Typ '{mail_type}' (erwartet trip-briefing/compare/deviation-alert)"]

    try:
        lang, hinweise = _ml().mail_lang(msg)
    except ValueError as exc:
        return False, [f"SPRACHE: {exc}"]
    if warnungen is not None:
        warnungen.extend(hinweise)

    mail_format = msg["X-GZ-Format"]
    if mail_format == "full":
        ok, errors = _validate_full(msg, lang, _tabellen_erwartet(msg, soll))
    elif mail_format == "compact":
        ueberblick = soll is None or soll.get("kontext") != "trip" or _soll_report(msg, soll)["ueberblick"]
        ok, errors = _validate_compact(msg, max_bytes, lang, ueberblick)
    else:
        return False, [f"Unbekanntes Format '{mail_format}' (erwartet full/compact)"]

    text = "\n".join(_part_text(p) for p in msg.walk() if p.get_content_maintype() == "text")
    widerspruch = _ml().widerspruch(text, lang, _LANG_MARKER_KEYS)
    if widerspruch:
        return False, [widerspruch, *errors]
    if soll is not None:  # Issue #3047: nur mit --konfig, sonst unveraendert
        abweichungen = pruefe_soll(msg, soll, lang)
        return ok and not abweichungen, errors + abweichungen
    return ok, errors


# --------------------------------------------------------------------------- #
# Mail-Auswahl (Issue #780): gezielt die eigene Mail im geteilten Postfach finden
# --------------------------------------------------------------------------- #
def _decode_subject(raw: str | None) -> str:
    """Dekodiert ein (ggf. RFC-2047-kodiertes) Subject zu lesbarem str.

    Em-Dash/Umlaut-Subjects kommen per IMAP als `=?utf-8?b?...?=` zurueck. Wir
    dekodieren Python-seitig (NICHT IMAP SEARCH SUBJECT — Stalwart matcht nicht
    ueber Bindestriche, Lehre #731).
    """
    if not raw:
        return ""
    parts = []
    for chunk, enc in decode_header(raw):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _message_matches(
    headers: Message,
    mail_type: str | None = None,
    subject_contains: str | None = None,
    lang: str = "de",
    to_contains: str | None = None,
) -> bool:
    """Praedikat: passt die Mail zu den Filtern? (testbar OHNE IMAP).

    - mail_type gesetzt: X-GZ-Mail-Type muss exakt gleich sein.
    - subject_contains gesetzt: dekodiertes Subject muss den Marker enthalten.
    - #2681: Sprache UND Empfaenger des Nutzers (``_e2e_paths.mail_waehlbar``).
    """
    if not _e2e_paths.mail_waehlbar(headers, lang, to_contains):
        return False
    if mail_type is not None and headers.get("X-GZ-Mail-Type") != mail_type:
        return False
    if subject_contains is not None:
        subject = _decode_subject(headers.get("Subject"))
        if subject_contains not in subject:
            return False
    return True


# --------------------------------------------------------------------------- #
# CLI / IMAP
# --------------------------------------------------------------------------- #
def fetch_latest_message(
    mail_type: str | None = None,
    subject_contains: str | None = None,
    max_scan: int = 50,
    lang: str = "de",
    to_contains: str | None = None,
    imap=None,
    vertrauen=None,
) -> Message:
    """Holt die passende Mail aus dem Test-Postfach als Message-Objekt.

    Scannt die Header der bis zu `max_scan` neuesten Mails (newest-first) und
    liefert die erste, die `_message_matches` erfuellt (Issue #780; #2681:
    Sprache und Empfaenger). ``imap``: fertige, angemeldete Verbindung (Test-Seam).
    #2961: nur Mails des Dienst-Absenders (``_mail_trust``); mit eigener
    Verbindung kommt ``vertrauen`` aus der Konfiguration.
    """
    own_connection = imap is None
    if own_connection:
        imap = _open_test_imap()
        if vertrauen is None:
            vertrauen = _mail_trust.aus_konfiguration()
    verworfen: list = []
    try:
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        all_ids = data[0].split()
        if not all_ids:
            raise ValueError("Keine E-Mails gefunden")

        for mid in reversed(all_ids[-max_scan:]):
            _, hdr_data = imap.fetch(mid, "(BODY.PEEK[HEADER])")
            headers = email.message_from_bytes(hdr_data[0][1])
            if _message_matches(headers, mail_type, subject_contains, lang, to_contains):
                grund = _mail_trust.fehler(headers, vertrauen) if vertrauen else None
                if grund:
                    verworfen.append(grund)
                    continue
                _, msg_data = imap.fetch(mid, "(RFC822)")
                return email.message_from_bytes(msg_data[0][1])

        raise ValueError(
            f"Keine passende Mail gefunden (mail_type={mail_type!r}, "
            f"subject_contains={subject_contains!r}, lang={lang!r}, "
            f"to_contains={to_contains!r}, scan={max_scan})"
            + _mail_trust.hinweis(verworfen)
        )
    finally:
        if own_connection:
            try:
                imap.close()
                imap.logout()
            except Exception:
                pass


def _open_test_imap():
    """Angemeldete Verbindung zum Test-Postfach (#972: GZ_TEST_IMAP_* zuerst)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
    from app.config import Settings

    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")
    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    return imap


def run_validation(
    max_bytes: int = _MAX_BYTES_DEFAULT,
    mail_type: str | None = None,
    subject_contains: str | None = None,
    max_scan: int = 50,
    warnungen: list | None = None,
    lang: str = "de",
    to_contains: str | None = None,
    soll: dict | None = None,
) -> tuple[bool, list[str]]:
    """Holt die (gefilterte) Mail und validiert sie (``soll``: #3047 --konfig)."""
    msg = fetch_latest_message(
        mail_type=mail_type, subject_contains=subject_contains, max_scan=max_scan,
        lang=lang, to_contains=to_contains,
    )
    return validate_message(msg, max_bytes, warnungen=warnungen, soll=soll)


def _write_validation_log(success: bool, errors: list, warnings: list | None = None) -> None:
    """Strukturiertes Validator-Log YAML (fail-soft, Vorbild email_spec_validator).

    Issue #1282: (C) log_dir liegt im shared-repo (git-common-dir via
    _e2e_paths.shared_repo_dir), Fail-soft-Fallback auf die alte __file__-
    relative Berechnung (AC-4, z.B. ausserhalb eines Git-Repos). (A) No-Op
    (mail_type compare/deviation-alert, erkennbar am 'uebersprungen'-Marker in
    errors) zaehlt nie als Pass und traegt zusaetzlich 'skipped: true' (AC-2).
    """
    try:
        from datetime import datetime
        import tempfile
        import yaml as _yaml

        hooks_dir = Path(__file__).resolve().parent
        fallback_log_dir = hooks_dir.parent / "workflows" / "_log"
        try:
            shared = _e2e_paths.shared_repo_dir(cwd=hooks_dir)
        except Exception:
            shared = None
        log_dir = (shared / ".claude" / "workflows" / "_log") if shared else fallback_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")

        skipped = any("uebersprungen" in str(e) for e in errors)
        data = {
            "validator": "briefing_mail_validator",
            "validated_at": datetime.utcnow().isoformat(),
            "workflow_id": workflow_id,
            "passed": bool(success),
            "error_count": len(errors),
            "errors": list(errors),
            "warnings": list(warnings or []),  # #2663: z. B. fehlender X-GZ-Lang
        }
        if skipped:
            data["skipped"] = True
        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            _yaml.safe_dump(data, f, allow_unicode=True)
        # #1408 F005: Mikrosekunden + exklusive Ablage, Zaehler im Praefix --
        # zwei Laeufe in derselben Sekunde duerfen einander weder
        # ueberschreiben noch aus dem Suchmuster des Gates fallen.
        _validator_log.place_exclusively(tmp, log_dir, workflow_id, "briefing_validation")
    except Exception:
        pass  # fail-soft


def main() -> None:
    parser = argparse.ArgumentParser(description="Briefing-Mail-Validator (#733)")
    parser.add_argument("--max-bytes", type=int, default=_MAX_BYTES_DEFAULT,
                        help="Byte-Limit fuer compact-Mails (default: 2048)")
    parser.add_argument("--mail-type", default=None,
                        help="Nur Mails mit diesem X-GZ-Mail-Type waehlen (#780)")
    parser.add_argument("--subject-contains", default=None,
                        help="Nur Mails waehlen, deren Subject diesen Marker enthaelt (#780)")
    parser.add_argument("--max-scan", type=int, default=50,
                        help="Wie viele neueste Mails maximal scannen (default: 50)")
    parser.add_argument("--eml", metavar="PFAD", default=None,
                        help="Mail aus dieser .eml-Datei pruefen statt per IMAP (#2663)")
    parser.add_argument("--konfig", metavar="PFAD", default=None,
                        help="Gespeichertes Trip-JSON des Nutzers: Auswahl und Reihenfolge "
                             "der Spalten muessen ihm entsprechen (#3047)")
    _e2e_paths.sprach_argumente(parser)
    args = parser.parse_args()

    print("=" * 70)
    print("BRIEFING-MAIL-VALIDATOR (full + compact) — #733")
    print("=" * 70)
    print()

    warnungen: list = []
    try:
        # #3047: Soll aus der gespeicherten Konfiguration; ohne --konfig None.
        soll = _soll_modul().lade_soll(args.konfig, args.lang or "de") if args.konfig else None
        if args.eml:  # #2663: Mail aus Datei statt IMAP
            msg = email.message_from_bytes(Path(args.eml).read_bytes())
            success, errors = validate_message(msg, args.max_bytes, warnungen=warnungen, soll=soll)
            auswahl = _e2e_paths.eml_auswahl_fehler(msg, args.lang, args.to_contains)
            success, errors = success and not auswahl, auswahl + errors
        else:
            success, errors = run_validation(
                args.max_bytes,
                mail_type=args.mail_type,
                subject_contains=args.subject_contains,
                max_scan=args.max_scan,
                warnungen=warnungen,
                lang=args.lang or "de",
                to_contains=args.to_contains,
                soll=soll,
            )
    except Exception as e:  # IMAP / technischer Fehler
        print(f"⚠️  TECHNISCHER FEHLER: Mail konnte nicht geladen werden: {e}")
        _write_validation_log(success=False, errors=[str(e)], warnings=warnungen)
        sys.exit(2)

    for hinweis in warnungen:
        print(f"WARNUNG: {hinweis}", file=sys.stderr)
    _write_validation_log(success=success, errors=errors, warnings=warnungen)

    if success:
        for note in errors:
            print(f"  ℹ {note}")
        print("✅ Briefing-Mail-Checks bestanden.")
        sys.exit(0)

    print("❌ SPEC-VERLETZUNGEN GEFUNDEN:")
    print()
    for err in errors:
        print(f"  • {err}")
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
