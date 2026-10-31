#!/usr/bin/env python3
"""
Official-Alert-Mail-Validator -- Issue #1197 (Luecke im Renderer-Mail-Gate).

Kanonischer Acceptance-Validator fuer die Standalone-Amtliche-Warnung-Mail
(Trip- und Compare-Pfad, gerendert von
`src/output/renderers/alert/official_alerts.py::render_official_alert_html`
via `render_warn_block(variant="standalone", ...)`). Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand des Marker-Headers
X-GZ-Mail-Type: official-alert und prueft sie auf Plausibilitaet.

Bislang deckte KEIN Validator diesen sicherheitskritischen Mail-Typ ab --
`radar_alert_mail_validator.py` prueft ausschliesslich X-GZ-Mail-Type:
radar-alert und behandelt official-alert-Mails als No-Op. Dieses Modul
schliesst die Luecke.

Vorbild: radar_alert_mail_validator.py (IMAP-Fetch, Exit 0/1/2, YAML-Log).
Stdlib only -- als isoliertes Modul ladbar (keine relativen Importe).

Struktur-Pruefung: der HTML-Body wird mit `html.parser.HTMLParser` (stdlib)
geparst, um die tatsaechlich vom Renderer emittierten CSS-Klassen-Tokens zu
sammeln (kein Substring-Fund auf den Rohtext -- eine Klasse zaehlt nur, wenn
sie als `class="..."`-Attributwert auftaucht). Zusaetzlich wird der
extrahierte Text auf die deterministischen Textbausteine der SOLL-Vorlage
(#1233 Slice B) geprueft: Verdict-Anzahl (Ziffer > 0), Warnstufe, Gueltig-
Zeitangabe, Quelle-Zeile, Stand-Footer.

Exit codes:
    0 = alle Checks bestanden (oder Mail ist kein official-alert -> No-Op)
    1 = Spec-Verletzung mit konkreter Fehlerliste
    2 = technischer Fehler (IMAP nicht erreichbar)
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import sys
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path

# Issue #1282 AC-4: shared-repo _log-Aufloesung (git-common-dir) -- gleiches
# Muster wie renderer_mail_gate.py fuer hook_utils (sys.path-Erweiterung fuer
# standalone-Aufruf, kein relativer Import noetig).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _e2e_paths  # noqa: E402
import _validator_log  # noqa: E402  (#1408 F005: kollisionsfreie Log-Ablage)

# Verdict-Zeile: "{N} amtliche Warnung" / "{N} amtliche Warnungen".
_VERDICT_RE = re.compile(r"(\d+)\s+amtliche Warnung(?:en)?")

# Warnstufen-Woerter (Leiter bei uniformer Stufe, Meter/Headline bei gemischten).
# Bewusst OHNE \b-Wortgrenzen: die Tag-Strip-Ableitung des Plain-Text-Parts
# (build_mime_message) fuegt zwischen benachbarten Inline-Elementen KEIN
# Leerzeichen ein (z.B. "GELBORANGEROT" in der Warnstufen-Leiter) -- ein
# Boundary-Check wuerde dort systematisch fehlschlagen, obwohl die
# Warnstufe strukturell vorhanden ist (zusaetzlich ueber S-2 abgesichert).
_LEVEL_WORD_RE = re.compile(r"(GELB|ORANGE|ROT)")

# Issue #1441 (Spec avalanche_report_bulletin.md Abschnitt 7, ADR-0089): der
# amtliche Lawinen-Lagebericht traegt die EAWS-Stufe als Wortlaut
# "Lawinenstufe N (<EAWS-Wort>)" -- die Leiter "Warnstufe X · n/3" und die
# Farbwoerter GELB/ORANGE/ROT entfallen fuer diese Gefahrenart. Der Renderer
# emittiert dafuer KEINE eigene CSS-Klasse (official_alerts.py `_is_eaws`
# unterdrueckt nur Leiter/Meter), Stufentraeger ist daher der Text.
_AVALANCHE_LEVEL_RE = re.compile(r"Lawinenstufe\s+([1-5])[-+]?\s*\(([^)\n<]+)\)")
_EAWS_WORDS = {1: "gering", 2: "mäßig", 3: "erheblich", 4: "groß", 5: "sehr groß"}
# Positive Quellen-Kennung des Lageberichts (Quellenlabel bzw. Bulletin-URL).
_AVALANCHE_SOURCE_MARKS = ("avalanche.report", "Schnee- und Lawinenforschung SLF", "slf.ch")
# Typ-Woerter aller ANDEREN Gefahrenarten (Spiegel von official_alerts.py
# `_HAZARD_LABELS` ohne die Lawinen-Eintraege; Drift bewacht
# tests/tdd/test_official_alert_mail_validator.py). Taucht eines davon auf,
# ist die Mail keine reine Lawinenmail und S-2/P-2 bleiben strikt (Adversary F012).
# Bewusst OHNE abschliessende Wortgrenze: Quell-Labels erscheinen auch
# zusammengesetzt ("Gewitterwarnung", "Hitzewarnung", `_display_label`).
_OTHER_HAZARD_RE = re.compile(
    r"\b(Hitze|Gewitter|Kälte|Sturm|Starkregen|Schneefall|Glatteis|"
    r"Zugang gesperrt|Waldbrand-Gefahr|Hochwasser/Erdrutsch)"
)

# Gueltigkeits-Zeile (P-3, Issue #1240): jedes Vorkommen mitsamt seinem Wert bis
# zum Zeilen- bzw. Element-Ende. Der Plain-Text-Part ist tag-gestrippt, der
# HTML-Part nicht -- deshalb endet der Wert am Umbruch ODER am naechsten Tag.
_VALIDITY_RE = re.compile(r"Gültig:\s*([^\n<]*)")
# Plausibler Zeitraum: DE-Wochentag + Datum, so wie `_format_validity` emittiert
# ("Sa 12.07. - ganztaegig" bzw. "Sa 12.07. - 15:00-21:00"). Alles andere --
# insbesondere "unbekannt" oder ein leerer Wert -- ist KEINE Zeitangabe.
_VALIDITY_VALUE_RE = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{2}\.\d{2}\.")

# CSS-Klassen, die die SOLL-Vorlage (#1233 Slice B) fuer die Standalone-
# Amtliche-Warnung-Mail zwingend emittiert.
_REQUIRED_CLASSES = {"verdict", "warn", "body-foot"}
# Traeger der Quellenangabe -- ZWEI gueltige Formen (Issue #1744 A2, AC-14):
# die getoente `.src`-Box (Bestand, #1233 Slice B) ODER die Quellen-Datenzeile
# im gemeinsamen Datenzeilen-Block (A2 loest die Box auf; das Label steht dann
# in einer eigenen Tabellenzelle, das Literal "Quelle:" entsteht im gebauten
# Klartext-Teil). ADDITIV erweitert, nicht gelockert: `src` bleibt eine
# gueltige Alternative, und eine Mail OHNE jede Quellenangabe faellt weiterhin
# durch -- hier UND zusaetzlich an P-4.
_SOURCE_ROW_RE = re.compile(r"^\s*Quelle:\s*\S", re.MULTILINE)
# Warnstufen-Traeger: Leiter (uniform) ODER Eskalations-Meter (gemischt).
_LADDER_CLASSES = {"stufe-line"}
_MIXED_METER_CLASSES = {"stacked", "meter"}

# Issue #2663: Gefahrenarten der Typ-Woerter (Katalog warnung.gefahr.<hazard>),
# Reihenfolge wie `_HAZARD_LABELS` in official_alerts.py, ohne Lawine.
_OTHER_HAZARD_KEYS = (
    "extreme_heat", "thunderstorm", "extreme_cold", "wind_gust", "rain", "snow",
    "black_ice", "access_ban", "wildfire_risk", "flood",
)
# Issue #2663: Schluessel, an denen die Sprache des Inhalts erkennbar ist.
_LANG_MARKER_KEYS = [
    "warnung.verdict.one", "warnung.verdict.other", "warnung.gueltig", "warnung.quelle",
    "warnung.abgerufen_bei", "warnung.stufe.gelb", "warnung.stufe.rot",
    "warnung.entwarnung.wort", "warnung.lawine.stufe",
]


def _ml():
    """Sprach-Hilfe ``_mail_lang`` (Issue #2663), lazy geladen: das Modul bleibt
    ohne Hilfsmodul importierbar (Log-Tests kopieren nur diese Datei)."""
    import _mail_lang

    return _mail_lang


def _wort_re(wort: str) -> str:
    """Regex-Literal eines Katalogworts; Leerzeichen/Bindestrich bleiben lesbar
    (der Drift-Waechter liest die Alternativen aus dem Muster)."""
    return re.escape(wort).replace("\\ ", " ").replace("\\-", "-")


def _validity_value_re(lang: str) -> "re.Pattern":
    """Plausibler Zeitraum: Wochentag (aus ``fmt_weekday``) + Datum in der
    Form der Sprache (de '29.10.', en '29 Oct'; en duldet auch '29.10.')."""
    if lang != "en":
        return _VALIDITY_VALUE_RE
    from datetime import date, timedelta

    from i18n import fmt_weekday

    tage = "|".join(fmt_weekday(date(2026, 10, 26) + timedelta(days=i), "en") for i in range(7))
    return re.compile(rf"\b({tage})\s+(\d{{1,2}}\s+[A-Z][a-z]{{2}}\b|\d{{2}}\.\d{{2}}\.)")


def _lang_patterns(lang: str) -> dict:
    """Alle sprachabhaengigen Erwartungen der Warn-Mail in ``lang`` (Katalog)."""
    ml = _ml()
    lawine_prefix = ml.vorlage("warnung.lawine.stufe", lang).split("{n}")[0].strip()
    uebergang = ml.vorlage("warnung.entwarnung.uebergang", lang).split("{alt}")[0].strip()
    stufen = "|".join(_wort_re(ml.erwartet(f"warnung.stufe.{s}", lang)) for s in ("gelb", "orange", "rot"))
    verdict = sorted((ml.kern(f"warnung.verdict.{f}", lang) for f in ("one", "other")), key=len, reverse=True)
    quelle = ml.erwartet("warnung.quelle", lang)
    return {
        "verdict": re.compile(r"(\d+)\s+(?:" + "|".join(_wort_re(v) for v in verdict) + ")"),
        "level_word": re.compile(f"({stufen})"),
        "avalanche_level": re.compile(re.escape(lawine_prefix) + r"\s+([1-5])[-+]?\s*\(([^)\n<]+)\)"),
        "eaws": {i: ml.erwartet(f"warnung.eaws.{i}", lang) for i in range(1, 6)},
        "other_hazard": re.compile(
            r"\b(" + "|".join(_wort_re(ml.erwartet(f"warnung.gefahr.{h}", lang)) for h in _OTHER_HAZARD_KEYS) + ")"
        ),
        "validity": re.compile(re.escape(ml.erwartet("warnung.gueltig", lang)) + r":\s*([^\n<]*)"),
        "validity_value": _validity_value_re(lang),
        "source_row": re.compile(r"^\s*" + re.escape(quelle) + r":\s*\S", re.MULTILINE),
        "quelle": f"{quelle}:",
        "abgerufen": ml.erwartet("warnung.abgerufen_bei", lang),
        "entwarnung": ml.erwartet("warnung.entwarnung.wort", lang),
        "transition": re.compile(
            re.escape(uebergang) + r"\s+(\d)\s*(?:→|->)\s*(\d|"
            + re.escape(ml.erwartet("warnung.entwarnung.beendet", lang)) + ")"
        ),
        "beendet": ml.erwartet("warnung.entwarnung.beendet", lang),
    }


class _ClassCollector(HTMLParser):
    """Sammelt alle `class="..."`-Attributwert-Tokens der HTML-Struktur.

    Bewusst OHNE Baum-/Nesting-Tracking (robust gegen unbalancierte Void-Tags
    wie `<br>` in der generierten Mail-HTML) -- ein Token zaehlt nur, wenn es
    tatsaechlich als Klassen-Attributwert auftaucht, nicht wenn das Wort
    irgendwo im Fliesstext vorkommt. Das unterscheidet die Pruefung von einer
    naiven Substring-Suche im Rohtext."""

    def __init__(self) -> None:
        super().__init__()
        self.classes: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "class" and value:
                self.classes.update(value.split())


def _part_text(part: Message) -> str:
    """Dekodierter Payload eines Parts (bytes->str, fail-soft)."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return part.get_payload() or ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def _extract_parts(msg: Message) -> tuple[str, str]:
    """Extrahiert (plain_text, html) aus der Mail (alle Parts)."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                plain_parts.append(_part_text(part))
            elif ctype == "text/html":
                html_parts.append(_part_text(part))
    else:
        body = _part_text(msg)
        if msg.get_content_type() == "text/html":
            html_parts.append(body)
        else:
            plain_parts.append(body)
    return "\n".join(plain_parts), "\n".join(html_parts)


# Issue #1441 S2 (ADR-0090): Entwarnungs-Uebergang "Stufe 4 → 2" bzw. "Stufe 4 → beendet".
_ALLCLEAR_TRANSITION_RE = re.compile(r"Stufe\s+(\d)\s*(?:→|->)\s*(\d|beendet)")
# Nur Daten, keine Handlungsempfehlung (Spec AC-16).
_RECOMMENDATION_WORDS = ("sicher", "kannst", "empfehlen", "gefahrlos", "aufbrechen", "losgehen")


def _decoded_subject(msg: Message) -> str:
    """Betreff RFC-2047-dekodiert (fail-soft: Rohwert)."""
    from email.header import decode_header, make_header

    raw = msg.get("Subject") or ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return str(raw)


def _allclear_errors(msg: Message, plain: str, html: str, classes: set[str],
                     w: dict | None = None) -> list[str]:
    """E-1..E-4: Abschnitt, Betreff, plausibler Uebergang (alt > neu bzw.
    'beendet'), keine Handlungsempfehlung."""
    errors: list[str] = []
    w = w or _lang_patterns("de")
    wort = w["entwarnung"]
    text = plain + "\n" + html
    if "entwarnung" not in classes or wort not in (plain or html):
        errors.append("E-1: Abschnitt 'Entwarnung' fehlt (Klasse 'entwarnung' bzw. Ueberschrift).")
    if wort not in _decoded_subject(msg):
        errors.append(f"E-2: Betreff ohne 'Entwarnung': {_decoded_subject(msg)!r}")
    transitions = w["transition"].findall(text)
    if not transitions:
        errors.append("E-3: Kein Uebergang 'Stufe N → M' bzw. 'Stufe N → beendet' gefunden.")
    for old, new in transitions:
        if new != w["beendet"] and int(old) <= int(new):
            errors.append(f"E-3: Entwarnung ohne Absenkung: 'Stufe {old} → {new}' (alt muss > neu sein).")
    # Ganzes Wort (Adversary F008): "Sicherheitsbereich"/"unsicher" sind Daten.
    hits = [w for w in _RECOMMENDATION_WORDS if re.search(rf"\b{re.escape(w)}\b", text.lower())]
    if hits:
        errors.append(f"E-4: Handlungsempfehlung im Text: {hits}")
    return errors


def validate_message(msg: Message, warnungen: list | None = None) -> tuple[bool, list[str]]:
    """Faellt das Urteil ueber ein geparstes email.message.Message-Objekt.

    Returnt (ok, errors):
    - Falscher Mail-Typ (nicht official-alert): (True, [Info]) -- sauberes No-Op.
    - Alle Checks bestanden: (True, []).
    - Mind. ein Check schlaegt fehl: (False, [Fehlerliste]).
    """
    mail_type = msg.get("X-GZ-Mail-Type")

    if mail_type is None or mail_type != "official-alert":
        info = (
            f"Kein official-alert-Header (X-GZ-Mail-Type={mail_type!r}) "
            "-- falscher Validator, uebersprungen"
        )
        return True, [info]

    try:
        lang, hinweise = _ml().mail_lang(msg)
    except ValueError as exc:
        return False, [f"SPRACHE: {exc}"]
    if warnungen is not None:
        warnungen.extend(hinweise)
    w = _lang_patterns(lang)

    plain, html = _extract_parts(msg)
    # Faellt der HTML-Part aus (z.B. non-multipart-Mail), auf den Plain-Text
    # zurueckfallen -- der enthaelt (per build_mime_message) den taggeloeschten
    # HTML-Body und traegt daher noch die Textbausteine, nur keine Klassen.
    text = plain or html
    errors: list[str] = []
    widerspruch = _ml().widerspruch(plain + "\n" + html, lang, _LANG_MARKER_KEYS)
    if widerspruch:
        errors.append(widerspruch)

    collector = _ClassCollector()
    try:
        collector.feed(html)
    except Exception as exc:  # fail-closed: kaputtes HTML ist ein echter Befund
        errors.append(f"S-0: HTML-Body nicht parsbar: {exc}")

    # Issue #1441 S2: Entwarnungs-Plausibilitaet. Eine REINE Entwarnungs-Mail
    # traegt keinen Warn-Block -- dann entfallen S-1/S-2/P-1..P-4, die
    # Entwarnungs-Pruefungen E-1..E-4 und der Stand-Footer P-5 bleiben.
    # Gemischte Mails durchlaufen zusaetzlich alle bisherigen Pruefungen.
    if "entwarnung" in collector.classes or w["entwarnung"] in _decoded_subject(msg):
        errors.extend(_allclear_errors(msg, plain, html, collector.classes, w))
        if not ({"verdict", "warn"} & collector.classes):
            if "Stand: heute" not in text:
                errors.append("P-5: 'Stand: heute'-Footer fehlt im Body.")
            return len(errors) == 0, errors

    missing_classes = _REQUIRED_CLASSES - collector.classes
    if missing_classes:
        errors.append(
            "S-1: Erwartete CSS-Struktur-Klassen fehlen im HTML-Body: "
            f"{sorted(missing_classes)}. Gefundene Klassen: {sorted(collector.classes)}"
        )

    # S-1b (#1744 A2, AC-14): die Quellenangabe muss EINE der beiden Formen
    # tragen -- Box `.src` ODER Quellen-Datenzeile im Text.
    if "src" not in collector.classes and not w["source_row"].search(text):
        errors.append(
            "S-1b: Keine Quellenangabe erkennbar -- weder eine `.src`-Box im "
            "HTML-Body noch eine Datenzeile 'Quelle: ...' im Text. "
            f"Gefundene Klassen: {sorted(collector.classes)}"
        )

    # Issue #1441: Lawinen-Lagebericht positiv erkennen (Stufen-Wortlaut UND
    # Quelle avalanche.report) -- NIE allein daraus, dass die Leiter fehlt.
    # Klartext UND HTML-Teil getrennt durchsuchen (Adversary F013): ein falsches
    # Stufen-Wort nur im HTML-Teil darf nicht unbemerkt bleiben.
    avalanche_levels = w["avalanche_level"].findall(plain) + w["avalanche_level"].findall(html)
    is_avalanche = bool(avalanche_levels) and any(m in text + html for m in _AVALANCHE_SOURCE_MARKS)
    # Reine Lawinenmail: KEIN Farbwort und KEIN Typ-Wort einer anderen
    # Gefahrenart (F012). Traegt die Mail zusaetzlich eine andere Warnung
    # (gemischt), bleibt S-2 strikt wie bisher (Leiter oder Meter Pflicht).
    avalanche_only = (
        is_avalanche
        and not w["level_word"].search(text)
        and not w["other_hazard"].search(plain + html)
    )
    # P-2b: Ziffer und EAWS-Wort muessen zusammenpassen (bewacht u. a., dass
    # Stufe 5 nie als "groß" erscheint). Gilt fuer JEDES Vorkommen.
    for digit, word in avalanche_levels:
        expected = w["eaws"][int(digit)]
        if word.strip() != expected:
            errors.append(
                f"P-2b: 'Lawinenstufe {digit} ({word.strip()})' -- EAWS-Wort passt "
                f"nicht zur Ziffer (erwartet '{expected}')."
            )

    has_ladder = bool(_LADDER_CLASSES & collector.classes)
    has_mixed_meter = _MIXED_METER_CLASSES <= collector.classes
    if not (has_ladder or has_mixed_meter or avalanche_only):
        errors.append(
            "S-2: Weder Warnstufen-Leiter ('stufe-line', uniform) noch "
            "Eskalations-Meter ('warn stacked'/'meter', gemischt) im HTML-Body "
            f"gefunden. Gefundene Klassen: {sorted(collector.classes)}"
        )

    verdict_match = w["verdict"].search(text)
    if not verdict_match or int(verdict_match.group(1)) < 1:
        errors.append(
            "P-1: Keine plausible Verdict-Zeile '{N} amtliche Warnung(en)' mit "
            f"N>=1 gefunden. Text-Ausschnitt: {text[:160]!r}"
        )

    if not w["level_word"].search(text) and not avalanche_only:
        errors.append(
            "P-2: Keine Warnstufe (GELB/ORANGE/ROT) im Text erkennbar."
        )

    # P-3 (Issue #1240): Die ANWESENHEIT der Gueltigkeits-Zeile ist kein taugliches
    # Kriterium -- Praefektur-Zugangssperren und Waldbrand-Tagesstufen liefern keine
    # valid_from/valid_to, ihre Warnungen tragen zu Recht keine Zeile (PO-Entscheidung
    # #1238). Geprueft wird stattdessen der INHALT: steht eine Zeile da, MUSS sie
    # einen echten Zeitraum tragen. Damit faellt "Gueltig: unbekannt" -- der von
    # #1238 beanstandete Zustand -- kuenftig durch, statt durchgewinkt zu werden.
    for raw_value in w["validity"].findall(text):
        value = raw_value.strip()
        if not w["validity_value"].search(value):
            errors.append(
                "P-3: 'Gültig:'-Zeile ohne plausible Zeitangabe "
                f"(Wochentag + Datum erwartet, gefunden: {value!r}). Warnungen ohne "
                "bekannten Zeitraum tragen gar keine Gültig-Zeile."
            )

    if w["quelle"] not in text or w["abgerufen"] not in text:
        errors.append(
            "P-4: Quelle nicht sichtbar -- 'Quelle:' und/oder 'abgerufen bei' "
            "fehlt im Body."
        )

    if "Stand: heute" not in text:
        errors.append("P-5: 'Stand: heute'-Footer fehlt im Body.")

    return len(errors) == 0, errors


def _write_validation_log(success: bool, errors: list, warnings: list | None = None) -> None:
    """Strukturiertes Validator-Log YAML (fail-soft).

    Issue #1282 AC-4: log_dir liegt im shared-repo (git-common-dir via
    _e2e_paths.shared_repo_dir), Fail-soft-Fallback auf die alte __file__-
    relative Berechnung (z.B. ausserhalb eines Git-Repos).
    """
    try:
        from datetime import datetime
        import tempfile

        hooks_dir = Path(__file__).resolve().parent
        fallback_log_dir = hooks_dir.parent / "workflows" / "_log"
        try:
            shared = _e2e_paths.shared_repo_dir(cwd=hooks_dir)
        except Exception:
            shared = None
        log_dir = (shared / ".claude" / "workflows" / "_log") if shared else fallback_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")

        lines = [
            f"validator: official_alert_mail_validator",
            f"validated_at: '{datetime.utcnow().isoformat()}'",
            f"workflow_id: '{workflow_id}'",
            f"passed: {str(success).lower()}",
            f"error_count: {len(errors)}",
            "errors:",
        ]
        for err in errors:
            safe = err.replace("'", "''")
            lines.append(f"  - '{safe}'")
        # Issue #2663: Warnungen (z. B. fehlender Kopf X-GZ-Lang), auch leer.
        lines.append("warnings:" if warnings else "warnings: []")
        for hinweis in warnings or []:
            safe = hinweis.replace("'", "''")
            lines.append(f"  - '{safe}'")

        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
        # #1408 F005: Mikrosekunden + exklusive Ablage, Zaehler im Praefix --
        # zwei Laeufe in derselben Sekunde duerfen einander weder
        # ueberschreiben noch aus dem Suchmuster des Gates fallen.
        _validator_log.place_exclusively(tmp, log_dir, workflow_id, "official_alert_validation")
    except Exception:
        pass  # fail-soft


def fetch_latest_message(max_scan: int = 50) -> Message:
    """Holt die neueste official-alert-Mail aus dem Test-Postfach."""
    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from app.config import Settings

    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    # Standalone-Amtliche-Warnung-Mails werden an gregor-test@henemm.com
    # gesendet (Test-Postfach). Priorisiere GZ_TEST_IMAP_*, falle auf
    # GZ_IMAP_* zurueck.
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")

    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    try:
        imap.login(imap_user, imap_pass)
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        all_ids = data[0].split()
        if not all_ids:
            raise ValueError("Keine E-Mails gefunden")

        for mid in reversed(all_ids[-max_scan:]):
            _, hdr_data = imap.fetch(mid, "(BODY.PEEK[HEADER])")
            headers = email.message_from_bytes(hdr_data[0][1])
            if headers.get("X-GZ-Mail-Type") == "official-alert":
                _, msg_data = imap.fetch(mid, "(RFC822)")
                return email.message_from_bytes(msg_data[0][1])

        raise ValueError(
            f"Keine official-alert-Mail gefunden (scan={max_scan} Mails)"
        )
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--eml", metavar="PFAD", default=None,
                        help="Mail aus dieser .eml-Datei pruefen statt per IMAP (#2663)")
    args = parser.parse_args()

    print("=" * 70)
    print("OFFICIAL-ALERT-MAIL-VALIDATOR -- #1197")
    print("=" * 70)
    print()

    warnungen: list = []
    try:
        if args.eml:  # #2663: Mail aus Datei statt IMAP
            msg = email.message_from_bytes(Path(args.eml).read_bytes())
        else:
            msg = fetch_latest_message()
        success, errors = validate_message(msg, warnungen=warnungen)
    except Exception as exc:
        print(f"  TECHNISCHER FEHLER: Mail konnte nicht geladen werden: {exc}")
        _write_validation_log(success=False, errors=[str(exc)], warnings=warnungen)
        sys.exit(2)

    for hinweis in warnungen:
        print(f"WARNUNG: {hinweis}", file=sys.stderr)
    _write_validation_log(success=success, errors=errors, warnings=warnungen)

    if success:
        for note in errors:
            print(f"  i {note}")
        print("OK Official-Alert-Mail-Checks bestanden.")
        sys.exit(0)

    print("SPEC-VERLETZUNGEN GEFUNDEN:")
    print()
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
