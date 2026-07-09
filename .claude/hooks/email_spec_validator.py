#!/usr/bin/env python3
"""
E-Mail Spec v4.0 Compliance Validator

DIESER VALIDATOR IST ZWINGEND VOR JEDEM "E2E TEST BESTANDEN" AUSZUFÜHREN!

Prüft:
1. Struktur (2 Tabellen, 9 Zeilen)
2. Location-Anzahl (mind. 3 oder alle verfügbaren)
3. Daten-Plausibilität (Sonnenstunden vs Wolkenlage)
4. Format-Korrektheit (Wind/Böen, Sonnenstunden)
5. Vollständigkeit (Stunden-Tabelle)

Exit codes:
    0 = Alle Checks bestanden
    1 = Spec-Verletzung gefunden
    2 = Technischer Fehler
"""

import argparse
import os
import sys
import imaplib
import email
import re
from pathlib import Path
from typing import List, Tuple


def _write_validation_log(
    success: bool,
    errors: list,
    min_locations: int,
    log_dir: "Path | None" = None,
    workflow_id: "str | None" = None,
) -> None:
    """Issue #465 (B2): Strukturiertes Validator-Log YAML.

    Schreibt in ``.claude/workflows/_log/<ts>_<wf>_email_validation.yaml``.
    Fail-soft: jeder Fehler wird unterdrueckt, damit der Validator-Exit-Code
    erhalten bleibt.
    """
    try:
        from datetime import datetime
        import yaml as _yaml

        if log_dir is None:
            hooks_dir = Path(__file__).resolve().parent
            project_root = hooks_dir.parent.parent
            log_dir = project_root / ".claude" / "workflows" / "_log"

        if workflow_id is None:
            workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")

        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"{date_str}_{workflow_id}_email_validation.yaml"

        data = {
            "validator": "email_spec_validator",
            "validated_at": datetime.utcnow().isoformat(),
            "workflow_id": workflow_id,
            "passed": bool(success),
            "error_count": len(errors),
            "errors": list(errors),
            "min_locations_checked": int(min_locations),
        }

        import tempfile
        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            _yaml.safe_dump(data, f, allow_unicode=True)
        os.rename(tmp, str(log_path))
    except Exception:
        pass  # fail-soft — darf Validator nie abbrechen


def _fetch_latest_message():
    """Gemeinsamer IMAP-Fetch: laedt die neueste Mail als geparstes
    email.message.Message (Body UND Header aus derselben IMAP-Runde)."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from app.config import Settings
    settings = Settings()

    imap_host = settings.imap_host or settings.smtp_host
    # #972: Test-Postfach-Credentials priorisieren (Referenz-Pattern aus
    # radar_alert_mail_validator.py:170-171) — sonst prueft der Validator
    # versehentlich gegen das Produktiv-Postfach.
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")

    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    imap.login(imap_user, imap_pass)
    imap.select('INBOX')

    _, data = imap.search(None, 'ALL')
    all_ids = data[0].split()
    if not all_ids:
        raise ValueError("Keine E-Mails gefunden")

    _, msg_data = imap.fetch(all_ids[-1], '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])

    imap.close()
    imap.logout()

    return msg


def _extract_html_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            return part.get_payload(decode=True).decode('utf-8')
    return ''


def fetch_latest_email() -> str:
    """Fetch latest sent email HTML body. Unveraenderter oeffentlicher Vertrag."""
    return _extract_html_body(_fetch_latest_message())


# Issue #1108: v2-Vertrag (render_compare_html, Issue #1110) hat kein
# class="matrix-table" mehr -- die Uebersichtstabelle wird stattdessen ueber
# ihre erste Datenzeile "Amtliche Warnungen" identifiziert (CV2_METRICS[0],
# immer sichtbar, auch bei preset-gefilterten Metriken, #1104).
_OVERVIEW_WARN_LABEL = "Amtliche Warnungen"
_TABLE_RE = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL)

# v2-Stunden-Spaltenvertrag (compare_html.py:HOUR_METRICS), Issue #1106:
# kanonische 10-Spalten-Superset-Liste ("Zeit" + 9 konfigurierbare Wert-
# Spalten). Konfigurierbare Teilmengen sind zulaessig (Teilmengen-mit-
# Reihenfolge-Pruefung statt Exakt-Vergleich), s. validate_structure().
_HOUR_COLUMNS_V2 = [
    "Zeit", "Temp", "Gef.", "Wind", "Böen", "Regen", "UV", "Gew.", "Regen-W.", "Sicht",
]

# Negativ-Check: Score-/Winner-Sprache ist im v2-Vertrag ein Verstoss (kein
# Ranking mehr, s. compare_html.py-Docstring "Kein Score/Ranking/Winner-Card").
# Adversary F001: Wortgrenzen statt ungebundener Substring-Suche (sonst
# false positives bei Ortsnamen wie "Scoresbysund"/"Gewinnerort"); "score"
# zusaetzlich mit Zahlen-Kontext (Score-Werte sind immer "Score: N"/"Score N"),
# damit ein isoliertes Wort "Score" (z. B. in einem Ortsnamen-Fragment mit
# Wortgrenze) nicht faelschlich als Verstoss zaehlt.
_SCORE_WINNER_RE = re.compile(
    r"\bscore\b\s*[:=]?\s*\d+|\bwinner\b|\bempfehlung\b|\bbester\s+standort\b|🏆",
    re.IGNORECASE,
)

# v2-Uebersichtstabellen-Metrikzeilen (CV2_METRICS-Label -> Format-Regex +
# plausibler Wertebereich). "Amtliche Warnungen" (Warn-Zeile) hat kein
# numerisches Format und wird hier bewusst ausgelassen.
_OVERVIEW_METRIC_CHECKS = {
    "Temp max": (re.compile(r'^-?\d+°C$'), (-40, 55)),
    "Wind": (re.compile(r'^\d+ km/h$'), (0, 250)),
    "Sonne": (re.compile(r'^\d+\.\d h$'), (0, 24)),
    "Wolken": (re.compile(r'^\d+%$'), (0, 100)),
    "UV max": (re.compile(r'^\d+$'), (0, 16)),
}


def _extract_rows_from_table_html(table_inner: str) -> List[List[str]]:
    rows = []
    for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_inner, re.DOTALL):
        row_html = row_match.group(1)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
        rows.append(clean_cells)
    return rows


def extract_table_rows(body: str) -> List[List[str]]:
    """Findet die v2-Uebersichtstabelle ueber ihre erste Datenzeile
    "Amtliche Warnungen" (Issue #1108) -- ersetzt die alte
    class="matrix-table"-Erkennung, die im v2-Renderer nicht mehr existiert."""
    for match in _TABLE_RE.finditer(body):
        rows = _extract_rows_from_table_html(match.group(1))
        if len(rows) >= 2 and rows[1] and rows[1][0].strip() == _OVERVIEW_WARN_LABEL:
            return rows
    return []


def extract_locations(body: str) -> List[str]:
    """Extract location names from comparison table header."""
    rows = extract_table_rows(body)
    if not rows:
        return []

    header = rows[0]
    # First cell is "Metrik", rest are locations with #N prefix
    locations = []
    for cell in header[1:]:
        # Remove #N prefix
        name = re.sub(r'^#\d+\s*', '', cell).strip()
        if name:
            locations.append(name)

    return locations


def _find_location_hour_table(body: str, location_name: str, occurrence: int = 0):
    """Findet die Stundentabelle eines Ortes ueber den vorausgehenden
    "ORT <Name>"-Kopf (_render_location_section, Issue #1108) -- ersetzt die
    alte CSS-Klassen-Erkennung. `occurrence` waehlt bei gleichnamigen Orten
    (Adversary F002) das N-te Vorkommen des Namens statt immer nur das erste.
    Rueckgabe: (Spaltenkoepfe, Datenzeilen) oder None, wenn kein Ort-Kopf
    dieses Vorkommens bzw. keine folgende Tabelle gefunden wird."""
    marker = re.compile(r'>ORT</span>\s*<span[^>]*>' + re.escape(location_name) + r'</span>')
    matches = list(marker.finditer(body))
    if occurrence >= len(matches):
        return None
    match = matches[occurrence]
    # Issue #1150: Suche auf die aktuelle ORT-Sektion begrenzen. Die
    # Stundentabelle eines Ortes steht VOR dem naechsten "ORT <Name>"-Kopf.
    # Ohne diese Grenze wuerde eine fehlende Tabelle faelschlich die Tabelle
    # des naechsten Ortes einsammeln -- ein fehlendes Vorkommen bliebe unerkannt
    # (Erosion der Stundentabellen-Pflicht).
    next_ort = re.search(r'>ORT</span>\s*<span[^>]*>', body[match.end():], re.DOTALL)
    section_end = match.end() + next_ort.start() if next_ort else len(body)
    # Issue #1150 (Fix-Runde 2, Adversary F001): Die Stundentabelle ueber ihr
    # STABILES Merkmal identifizieren -- erste Zelle der Kopfzeile == "Zeit"
    # (Renderer-Vertrag _render_hour_table, "Zeit" ist fest verdrahtete erste
    # Spalte). "Erste <table> nach dem ORT-Kopf" ist unsicher: beim LETZTEN Ort
    # fehlt der Vorwaerts-Bound (kein Folge-ORT-Kopf), section_end == len(body),
    # und bei FEHLENDER Stundentabelle wuerde faelschlich die naechstbeste
    # Tabelle (Legende/Abo-/App-Footer) eingesammelt -> falsche Fehlermeldung
    # statt "nicht gefunden". Legende/Footer haben nie "Zeit" als erste Spalte.
    section = body[match.end():section_end]
    for table_match in re.finditer(r'<table[^>]*>(.*?)</table>', section, re.DOTALL):
        rows = _extract_rows_from_table_html(table_match.group(1))
        if rows and rows[0] and rows[0][0].strip() == "Zeit":
            return rows[0], rows[1:]
    return None


def validate_structure(body: str, hourly_enabled: bool = True) -> List[str]:
    """Validate email structure against the v2-Vertrag (Issue #1108/#1110,
    Spalten-Konfigurierbarkeit #1106): Uebersichtstabelle (Warn-Zeile + >=1
    numerische Zeile), Stundentabellen fuer alle gelisteten Orte mit einer
    gueltigen Teilmenge-mit-Reihenfolge von ``_HOUR_COLUMNS_V2`` (Mindestens
    "Zeit" + 1 Wert-Spalte), kein Score-/Winner-Vertrag mehr."""
    errors: List[str] = []

    rows = extract_table_rows(body)
    if not rows:
        errors.append(
            f"STRUKTUR: Uebersichtstabelle nicht gefunden (erste Datenzeile "
            f"'{_OVERVIEW_WARN_LABEL}' fehlt)"
        )
    elif len(rows) < 2:
        errors.append(
            f"STRUKTUR: Uebersichtstabelle hat nur {len(rows)} Zeile(n), "
            f"erwartet: Warn-Zeile + mindestens 1 numerische Metrik-Zeile"
        )

    locations = extract_locations(body)
    if rows and not locations:
        errors.append("STRUKTUR: Keine Orte in der Uebersichtstabelle-Kopfzeile gefunden")

    # Issue #1107/#1150: bei abgeschalteter Stundenverlauf-Sektion entfaellt
    # die gesamte Pflicht-Pruefung -- eine bewusst abgeschaltete Sektion darf
    # weder Tabellen enthalten noch ist ihr Fehlen ein Fehler. Bei fehlendem
    # Header (Default True) bleibt die Pruefung exakt so streng wie bisher.
    if hourly_enabled:
        # Adversary F002: gleichnamige Orte einzeln pruefen (N-tes Vorkommen statt
        # immer nur das erste) -- sonst wird eine defekte Stundentabelle des
        # zweiten (oder n-ten) gleichnamigen Ortes nie erkannt.
        occurrence_counts: dict = {}
        # Adversary F001 (Fix-Runde 2, Issue #1106): eine Config gilt mail-weit
        # fuer ALLE Orte (render_compare_html hat genau EIN hourly_metrics-Set
        # fuer den gesamten Aufruf). Eine einzelne Stundentabelle, die fuer sich
        # genommen eine gueltige Teilmenge-mit-Reihenfolge ist, aber von den
        # Spalten der uebrigen Orte abweicht, ist trotzdem ein Fehler --
        # Referenz-Spalten = die erste Stundentabelle ohne eigene Struktur-
        # Verletzung.
        reference_cols: list | None = None
        reference_name: str | None = None
        for name in locations:
            occurrence = occurrence_counts.get(name, 0)
            occurrence_counts[name] = occurrence + 1
            table = _find_location_hour_table(body, name, occurrence)
            if table is None:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) nicht gefunden"
                )
                continue
            header_cols, _rows = table
            # Issue #1106: Teilmengen-mit-Reihenfolge-Pruefung statt Exakt-Vergleich.
            # Mindestspalten-Regel: "Zeit" muss erste Spalte sein UND es muss
            # mindestens eine Wert-Spalte daneben existieren (sonst sinnlose Config).
            if not header_cols or header_cols[0] != "Zeit" or len(header_cols) < 2:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) "
                    f"verletzt die Mindestspalten-Regel (Zeit + mind. 1 Wert-Spalte), "
                    f"Spalten {header_cols}"
                )
                continue
            if [c for c in _HOUR_COLUMNS_V2 if c in header_cols] != header_cols:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) hat "
                    f"Spalten {header_cols}, erwartet eine gueltige Teilmenge (in Reihenfolge) von "
                    f"{_HOUR_COLUMNS_V2}"
                )
                continue
            # Cross-Location-Konsistenz: erst hier pruefen, da nur individuell
            # gueltige Spaltenlisten als Referenz bzw. Vergleichswert taugen.
            if reference_cols is None:
                reference_cols = header_cols
                reference_name = name
            elif header_cols != reference_cols:
                errors.append(
                    f"STRUKTUR: Stundentabelle fuer Ort '{name}' (Vorkommen {occurrence + 1}) hat "
                    f"Spalten {header_cols}, weicht von der mail-weiten Spalten-Konfiguration "
                    f"{reference_cols} (Referenz-Ort '{reference_name}') ab"
                )

    score_match = _SCORE_WINNER_RE.search(body)
    if score_match:
        errors.append(
            f"STRUKTUR: Score-/Winner-Sprache im Mail-Body gefunden "
            f"('{score_match.group(0)}') -- im v2-Vertrag unzulaessig"
        )

    return errors


def validate_location_count(body: str, min_expected: int = 3) -> List[str]:
    """Validate number of locations."""
    errors = []

    locations = extract_locations(body)

    if len(locations) < min_expected:
        errors.append(
            f"LOCATIONS: {len(locations)} Locations gefunden, "
            f"erwartet: mindestens {min_expected}"
        )

    return errors


def validate_plausibility(body: str) -> List[str]:
    """v2 (Issue #1108): Wertebereichs-Pruefung der Uebersichtstabellen-
    Metrikzeilen (Temp max/Wind/Sonne/Wolken/UV max, _OVERVIEW_METRIC_CHECKS)
    statt String-Presence-Check der alten englischen Zeilen-Labels (Cloud
    Cover/Sunny Hours). "—" bleibt als Fehlwert-Fallback zulaessig."""
    errors = []
    rows = extract_table_rows(body)

    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip()
        check = _OVERVIEW_METRIC_CHECKS.get(label)
        if check is None:
            continue
        _, (lo, hi) = check
        for i, val in enumerate(row[1:]):
            val = val.strip()
            if val == "—":
                continue
            num_match = re.search(r'-?\d+(\.\d+)?', val)
            if not num_match:
                continue
            num = float(num_match.group(0))
            if not (lo <= num <= hi):
                errors.append(
                    f"PLAUSIBILITÄT: '{label}' Ort {i+1} Wert '{val}' liegt "
                    f"ausserhalb des plausiblen Wertebereichs [{lo}, {hi}]"
                )

    return errors


def validate_format(body: str) -> List[str]:
    """v2 (Issue #1108): Format-Check der Uebersichtstabellen-Metrikzeilen
    (z. B. 'N°C', 'N km/h') statt der alten englischen Zeilen-Labels
    (Wind/Gusts, Sunny Hours). "—" bleibt als Fehlwert-Fallback zulaessig."""
    errors = []
    rows = extract_table_rows(body)

    for row in rows[1:]:
        if not row:
            continue
        label = row[0].strip()
        check = _OVERVIEW_METRIC_CHECKS.get(label)
        if check is None:
            continue
        pattern, _ = check
        for i, val in enumerate(row[1:]):
            val = val.strip()
            if val == "—":
                continue
            if not pattern.match(val):
                errors.append(
                    f"FORMAT: '{label}' Ort {i+1} ist '{val}', erwartet Format "
                    f"gemaess '{label}'-Spalte (Muster: {pattern.pattern})"
                )

    return errors


def validate_hourly_table(body: str, time_start: int = 9, time_end: int = 16) -> List[str]:
    """v2 (Issue #1108): Vollstaendigkeits-Check pro Ort (ueber die zugehoerige
    Stundentabelle, _find_location_hour_table) statt globaler String-Presence
    im gesamten Body -- ein fehlender Ort/eine fehlende Stunde ist damit
    eindeutig benennbar."""
    errors = []
    expected_hours = [f"{h:02d}:00" for h in range(time_start, time_end + 1)]

    # Adversary F002: Vorkommens-Index statt immer nur das erste Vorkommen.
    occurrence_counts: dict = {}
    for name in extract_locations(body):
        occurrence = occurrence_counts.get(name, 0)
        occurrence_counts[name] = occurrence + 1
        table = _find_location_hour_table(body, name, occurrence)
        if table is None:
            continue  # bereits von validate_structure() gemeldet
        _header, data_rows = table
        present_hours = {row[0].strip() for row in data_rows if row}
        missing = [h for h in expected_hours if h not in present_hours]
        if missing:
            errors.append(
                f"STUNDEN-TABELLE: Ort '{name}' (Vorkommen {occurrence + 1}) fehlende "
                f"Stunden: {', '.join(missing)}"
            )

    return errors


def run_validation(min_locations: int = 3) -> Tuple[bool, List[str]]:
    """Run all validations and return (success, errors)."""
    try:
        msg = _fetch_latest_message()
    except Exception as e:
        return False, [f"FEHLER: E-Mail konnte nicht geladen werden: {e}"]

    body = _extract_html_body(msg)
    # Fehlender Header (Alt-Mails vor diesem Feature) oder Wert != "false"
    # => True (bisheriges strenges Verhalten bleibt der sichere Default).
    hourly_enabled = msg.get("X-GZ-Compare-Hourly-Enabled") != "false"

    all_errors = []

    # Run all validators
    all_errors.extend(validate_structure(body, hourly_enabled=hourly_enabled))
    all_errors.extend(validate_location_count(body, min_locations))
    all_errors.extend(validate_plausibility(body))
    all_errors.extend(validate_format(body))
    all_errors.extend(validate_hourly_table(body))

    return len(all_errors) == 0, all_errors


def main():
    parser = argparse.ArgumentParser(description="E-Mail Spec v4.0 Validator")
    parser.add_argument(
        "--min-locations",
        type=int,
        default=3,
        help="Mindestanzahl erwarteter Locations (default: 3)"
    )
    args = parser.parse_args()

    print("=" * 70)
    print("E-MAIL SPEC v4.0 COMPLIANCE VALIDATOR")
    print("=" * 70)
    print()

    success, errors = run_validation(args.min_locations)

    # Issue #465 (B2): Strukturiertes Log VOR sys.exit() schreiben (fail-soft).
    _write_validation_log(success=success, errors=errors, min_locations=args.min_locations)

    if success:
        print("✅ ALLE SPEC-ANFORDERUNGEN ERFÜLLT!")
        print()
        print("Du darfst jetzt 'E2E Test bestanden' sagen.")
        sys.exit(0)
    else:
        print("❌ SPEC-VERLETZUNGEN GEFUNDEN:")
        print()
        for error in errors:
            print(f"  • {error}")
        print()
        print("=" * 70)
        print("⛔ DU DARFST NICHT 'E2E TEST BESTANDEN' SAGEN!")
        print("   Behebe zuerst alle Fehler und führe den Validator erneut aus.")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
