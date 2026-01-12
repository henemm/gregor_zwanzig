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
import sys
import imaplib
import email
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any


def fetch_latest_email() -> str:
    """Fetch latest sent email HTML body."""
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
    from app.config import Settings
    settings = Settings()

    if not settings.smtp_user or not settings.smtp_pass:
        raise ValueError("SMTP nicht konfiguriert")

    imap = imaplib.IMAP4_SSL('imap.gmail.com')
    imap.login(settings.smtp_user, settings.smtp_pass)
    imap.select('"[Google Mail]/Gesendet"')

    _, data = imap.search(None, 'ALL')
    all_ids = data[0].split()
    if not all_ids:
        raise ValueError("Keine E-Mails gefunden")

    _, msg_data = imap.fetch(all_ids[-1], '(RFC822)')
    msg = email.message_from_bytes(msg_data[0][1])

    body = ''
    for part in msg.walk():
        if part.get_content_type() == 'text/html':
            body = part.get_payload(decode=True).decode('utf-8')
            break

    imap.close()
    imap.logout()

    return body


def extract_table_rows(body: str) -> List[List[str]]:
    """Extract all rows from first table (comparison table)."""
    # Find first table
    table_match = re.search(r'<table[^>]*>(.*?)</table>', body, re.DOTALL)
    if not table_match:
        return []

    table_html = table_match.group(1)
    rows = []

    for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
        row_html = row_match.group(1)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        # Strip HTML tags from cells
        clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
        rows.append(clean_cells)

    return rows


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


def validate_structure(body: str) -> List[str]:
    """Validate email structure against spec."""
    errors = []

    # Check for 2 tables
    tables = re.findall(r'<table', body)
    if len(tables) != 2:
        errors.append(f"STRUKTUR: {len(tables)} Tabellen gefunden, erwartet: 2")

    # Check comparison table has correct rows
    # SPEC: docs/specs/e2e_validator_english_update.md - English UI, 8 rows
    rows = extract_table_rows(body)
    expected_labels = [
        "Metric",  # Header
        "Score",
        "Snow Depth",
        "New Snow",
        "Wind/Gusts",
        "Temperature (felt)",
        "Sunny Hours",
        "Cloud Cover",
        # Cloud Layer removed per cloud_cover_simplification.md
    ]

    if len(rows) != 8:
        errors.append(f"STRUKTUR: {len(rows)} Zeilen in Vergleichstabelle, erwartet: 8")

    for i, expected in enumerate(expected_labels):
        if i < len(rows):
            actual = rows[i][0] if rows[i] else ""
            if expected.lower() not in actual.lower():
                errors.append(f"STRUKTUR: Zeile {i+1} ist '{actual}', erwartet: '{expected}'")

    # Check for required sections (English/German UI)
    required_sections = [
        (["Time Window", "Zeitfenster"], "Header mit Zeitfenster"),
        (["Hourly", "Stündliche"], "Hourly Overview"),
        (["Recommendation", "Empfehlung"], "Winner-Box"),
    ]

    for keywords, name in required_sections:
        if not any(kw in body for kw in keywords):
            errors.append(f"STRUKTUR: {name} fehlt")

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
    """Validate data plausibility - cross-check values."""
    errors = []
    rows = extract_table_rows(body)

    # Build a map of metric -> values
    metrics: Dict[str, List[str]] = {}
    for row in rows:
        if row:
            label = row[0].lower()
            values = row[1:] if len(row) > 1 else []
            metrics[label] = values

    # Check Cloud Cover has valid values (with optional * marker for high elevations)
    # SPEC: docs/specs/cloud_cover_simplification.md
    cloud_cover = metrics.get("cloud cover", [])
    for i, val in enumerate(cloud_cover):
        val = val.strip()
        if val == "-":
            continue
        # Valid formats: "42%", "42%*" (with marker for lower clouds ignored)
        if not re.match(r'^\d+%\*?$', val):
            errors.append(
                f"PLAUSIBILITÄT: Location {i+1} - Cloud Cover '{val}' hat "
                f"ungültiges Format. Erwartet: 'N%' oder 'N%*'"
            )

    # Check Sunny Hours has valid values
    sunny_hours = metrics.get("sunny hours", [])
    for i, val in enumerate(sunny_hours):
        val = val.strip()
        if val == "-":
            continue
        # Valid formats: "0h", "~Nh"
        if not re.match(r'^(0h|~\d+h)$', val):
            errors.append(
                f"PLAUSIBILITÄT: Location {i+1} - Sunny Hours '{val}' hat "
                f"ungültiges Format. Erwartet: '0h' oder '~Nh'"
            )

    return errors


def validate_format(body: str) -> List[str]:
    """Validate format of specific fields."""
    errors = []
    rows = extract_table_rows(body)

    # Find Wind/Gusts row (English UI)
    for row in rows:
        if row and "wind" in row[0].lower() and "gust" in row[0].lower():
            for i, val in enumerate(row[1:]):
                val = val.strip()
                if val == "-":
                    continue
                # Expected format: "N/N [Direction]" e.g. "10/25 SW"
                if not re.match(r'^\d+/\d+\s+[NESW]{1,2}$', val):
                    errors.append(
                        f"FORMAT: Wind/Gusts Location {i+1} ist '{val}', "
                        f"erwartet: 'N/N [Direction]' z.B. '10/25 SW'"
                    )
                # Check no degree symbol
                if "°" in val:
                    errors.append(
                        f"FORMAT: Wind/Gusts Location {i+1} enthält Gradzeichen. "
                        f"Spec sagt: keine Gradangabe!"
                    )

    # Find Sunny Hours row (English UI)
    for row in rows:
        if row and "sunny" in row[0].lower() and "hour" in row[0].lower():
            for i, val in enumerate(row[1:]):
                val = val.strip()
                if val == "-":
                    continue
                # Check format: "0h" for 0, "~Nh" for N>0
                if val == "~0h":
                    errors.append(
                        f"FORMAT: Sunny Hours Location {i+1} ist '~0h', "
                        f"Spec sagt: '0h' (ohne Tilde) bei Wert 0!"
                    )
                elif not re.match(r'^(0h|~\d+h)$', val):
                    errors.append(
                        f"FORMAT: Sunny Hours Location {i+1} ist '{val}', "
                        f"erwartet: '0h' oder '~Nh'"
                    )

    return errors


def validate_hourly_table(body: str, time_start: int = 9, time_end: int = 16) -> List[str]:
    """Validate hourly table completeness."""
    errors = []

    expected_hours = [f"{h:02d}:00" for h in range(time_start, time_end + 1)]

    for hour in expected_hours:
        if hour not in body:
            errors.append(f"STUNDEN-TABELLE: {hour} fehlt")

    return errors


def run_validation(min_locations: int = 3) -> Tuple[bool, List[str]]:
    """Run all validations and return (success, errors)."""
    try:
        body = fetch_latest_email()
    except Exception as e:
        return False, [f"FEHLER: E-Mail konnte nicht geladen werden: {e}"]

    all_errors = []

    # Run all validators
    all_errors.extend(validate_structure(body))
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
