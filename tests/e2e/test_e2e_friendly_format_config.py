"""
E2E Test: use_friendly_format und alert_enabled Settings.

Sendet echte Emails via TripReportSchedulerService, prueft via IMAP ob
die display_config korrekt im HTML-Output ankommt.

Tested:
- Visibility friendly=ON -> "good/fair/poor/fog" | friendly=OFF -> numerisch ("69k")
- Cape friendly=ON -> Emoji | friendly=OFF -> Zahl
- Cloud friendly=ON -> Emoji | friendly=OFF -> Zahl
- alert_enabled steuert WeatherChangeDetectionService Thresholds

Ausfuehrung: uv run python tests/e2e/test_e2e_friendly_format_config.py
NICHT als pytest -- sendet echte Emails, braucht IMAP-Credentials.
"""

import sys
import os
import json
import time
import re
import imaplib
import email
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

TRIP_JSON = PROJECT_ROOT / "data" / "users" / "default" / "trips" / "gr221-mallorca.json"
IMAP_HOST = "imap.gmail.com"
IMAP_USER = os.getenv("GZ_SMTP_USER")
IMAP_PASS = os.getenv("GZ_SMTP_PASS")


# =====================================================================
# Helpers
# =====================================================================

def modify_metric_config(metric_id: str, **kwargs):
    """Modify a metric's config in the trip JSON."""
    with open(TRIP_JSON) as f:
        data = json.load(f)
    for mc in data["display_config"]["metrics"]:
        if mc["metric_id"] == metric_id:
            mc.update(kwargs)
    with open(TRIP_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def send_report():
    """Send morning report and return send timestamp."""
    import importlib
    import app.loader
    importlib.reload(app.loader)
    from app.loader import load_all_trips
    from services.trip_report_scheduler import TripReportSchedulerService

    trips = load_all_trips()
    trip = next(t for t in trips if t.id == "gr221-mallorca")
    service = TripReportSchedulerService()
    service.send_test_report(trip, "morning")
    return time.time()


def get_latest_email_html():
    """Get HTML of the latest GR221 email from Gmail Sent folder."""
    time.sleep(4)
    imap = imaplib.IMAP4_SSL(IMAP_HOST)
    imap.login(IMAP_USER, IMAP_PASS)
    imap.select('"[Google Mail]/Gesendet"')
    today = datetime.now(timezone.utc)
    since = today.strftime("%d-%b-%Y")
    s, data = imap.search(None, f'SUBJECT "GR221 Mallorca" SINCE {since}')
    ids = data[0].split()
    if not ids:
        imap.logout()
        return None
    s, md = imap.fetch(ids[-1], "(RFC822)")
    msg = email.message_from_bytes(md[0][1])
    imap.logout()
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode("utf-8", errors="replace")
    return None


def extract_column_values(html, col_name):
    """Extract all values from a specific column in the HTML tables."""
    headers_all = re.findall(r"<th>(.*?)</th>", html)
    if col_name not in headers_all:
        return []

    values = []
    tables = re.findall(r"<table>(.*?)</table>", html, re.DOTALL)
    for table in tables:
        headers = re.findall(r"<th>(.*?)</th>", table)
        if col_name not in headers:
            continue
        idx = headers.index(col_name)
        rows = re.findall(r"<tr>(.*?)</tr>", table, re.DOTALL)
        for row in rows:
            tds = re.findall(r"<td>(.*?)</td>", row)
            if len(tds) > idx:
                values.append(tds[idx])
    return values


# =====================================================================
# Test runner
# =====================================================================

results = {}


def run_test(test_name, setup_fn, check_fn):
    """Run a single E2E test: setup config, send email, check HTML."""
    print(f'\n{"="*60}')
    print(f"TEST: {test_name}")
    print(f'{"="*60}')

    setup_fn()
    print("  Config gesetzt, sende Report...")
    send_report()
    print("  Report gesendet, hole Email...")
    html = get_latest_email_html()
    if not html:
        print("  FAIL: Keine Email gefunden!")
        results[test_name] = "FAIL (no email)"
        return

    passed, detail = check_fn(html)
    status = "PASS" if passed else "FAIL"
    print(f"  {status}: {detail}")
    results[test_name] = f"{status}: {detail}"


# =====================================================================
# Test 1: Visibility friendly=ON -> "good/fair/poor"
# =====================================================================

def setup_visib_on():
    modify_metric_config("visibility", use_friendly_format=True)


def check_visib_friendly(html):
    vals = extract_column_values(html, "Visib")
    friendly_words = {"good", "fair", "poor"}
    has_friendly = any(any(w in v for w in friendly_words) for v in vals)
    has_fog = any("fog" in v for v in vals)
    has_numeric = any(re.match(r"^\d+\.?\d*k?$", v) for v in vals)

    if has_friendly or has_fog:
        return True, f"Friendly-Werte gefunden: {vals}"
    if has_numeric:
        return False, f"Numerische Werte statt friendly: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 2: Visibility friendly=OFF -> numerisch
# =====================================================================

def setup_visib_off():
    modify_metric_config("visibility", use_friendly_format=False)


def check_visib_numeric(html):
    vals = extract_column_values(html, "Visib")
    friendly_words = {"good", "fair", "poor", "fog"}
    has_friendly = any(any(w in v for w in friendly_words) for v in vals)
    has_numeric = any(re.search(r"\d+\.?\d*k?", v) for v in vals)

    if has_numeric and not has_friendly:
        return True, f"Numerische Werte gefunden: {vals}"
    if has_friendly:
        return False, f"Friendly-Werte obwohl OFF: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 3: Cape friendly=ON -> Emoji
# =====================================================================

def setup_cape_on():
    modify_metric_config("cape", use_friendly_format=True)


def check_cape_friendly(html):
    vals = extract_column_values(html, "Thndr%")
    emojis = ["\U0001f7e2", "\U0001f7e1", "\U0001f7e0", "\U0001f534"]
    has_emoji = any(any(e in v for e in emojis) for v in vals)
    has_numeric = any(re.match(r"^\d+$", v.strip()) for v in vals)

    if has_emoji:
        return True, f"Emoji-Werte gefunden: {vals}"
    if has_numeric:
        return False, f"Numerische Werte statt Emoji: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 4: Cape friendly=OFF -> Zahl
# =====================================================================

def setup_cape_off():
    modify_metric_config("cape", use_friendly_format=False)


def check_cape_numeric(html):
    vals = extract_column_values(html, "Thndr%")
    emojis = ["\U0001f7e2", "\U0001f7e1", "\U0001f7e0", "\U0001f534"]
    has_emoji = any(any(e in v for e in emojis) for v in vals)
    has_numeric = any(re.search(r"\d+", v) for v in vals)

    if has_numeric and not has_emoji:
        return True, f"Numerische Werte gefunden: {vals}"
    if has_emoji:
        return False, f"Emoji-Werte obwohl OFF: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 5: Cloud friendly=ON -> Emoji
# =====================================================================

def setup_cloud_on():
    modify_metric_config("cloud_total", use_friendly_format=True)


def check_cloud_friendly(html):
    vals = extract_column_values(html, "Cloud")
    cloud_emojis = ["\u2600", "\U0001f324", "\u26c5", "\U0001f325", "\u2601"]
    has_emoji = any(any(e in v for e in cloud_emojis) for v in vals)
    has_numeric = any(re.match(r"^\d+$", v.strip()) for v in vals)

    if has_emoji:
        return True, f"Emoji-Werte gefunden: {vals}"
    if has_numeric:
        return False, f"Numerische Werte statt Emoji: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 6: Cloud friendly=OFF -> Zahl
# =====================================================================

def setup_cloud_off():
    modify_metric_config("cloud_total", use_friendly_format=False)


def check_cloud_numeric(html):
    vals = extract_column_values(html, "Cloud")
    cloud_emojis = ["\u2600", "\U0001f324", "\u26c5", "\U0001f325", "\u2601"]
    has_emoji = any(any(e in v for e in cloud_emojis) for v in vals)
    has_numeric = any(re.match(r"^\d+$", v.strip()) for v in vals)

    if has_numeric and not has_emoji:
        return True, f"Numerische Werte gefunden: {vals}"
    if has_emoji:
        return False, f"Emoji-Werte obwohl OFF: {vals}"
    return False, f"Unerwartete Werte: {vals}"


# =====================================================================
# Test 7: alert_enabled Pipeline
# =====================================================================

def test_alert_enabled():
    """Test alert_enabled directly on the change detection pipeline."""
    print(f'\n{"="*60}')
    print("TEST: alert_enabled steuert Change Detection")
    print(f'{"="*60}')

    from services.weather_change_detection import WeatherChangeDetectionService
    import importlib
    import app.loader

    # A: cape alert=true, wind alert=false
    modify_metric_config("cape", alert_enabled=True)
    modify_metric_config("wind", alert_enabled=False)
    importlib.reload(app.loader)
    from app.loader import load_all_trips
    trips = load_all_trips()
    trip = next(t for t in trips if t.id == "gr221-mallorca")

    svc_a = WeatherChangeDetectionService.from_display_config(trip.display_config)
    cape_keys = [k for k in svc_a._thresholds if "cape" in k]
    wind_keys = [k for k in svc_a._thresholds if "wind_max" in k]

    print("  Config A: cape alert=true, wind alert=false")
    print(f"    Cape in thresholds: {bool(cape_keys)} ({cape_keys})")
    print(f"    Wind in thresholds: {bool(wind_keys)} ({wind_keys})")

    a_pass = bool(cape_keys) and not bool(wind_keys)

    # B: cape alert=false, wind alert=true
    modify_metric_config("cape", alert_enabled=False)
    modify_metric_config("wind", alert_enabled=True)
    importlib.reload(app.loader)
    from app.loader import load_all_trips as lat2
    trips2 = lat2()
    trip2 = next(t for t in trips2 if t.id == "gr221-mallorca")

    svc_b = WeatherChangeDetectionService.from_display_config(trip2.display_config)
    cape_keys_b = [k for k in svc_b._thresholds if "cape" in k]
    wind_keys_b = [k for k in svc_b._thresholds if "wind_max" in k]

    print("  Config B: cape alert=false, wind alert=true")
    print(f"    Cape in thresholds: {bool(cape_keys_b)} ({cape_keys_b})")
    print(f"    Wind in thresholds: {bool(wind_keys_b)} ({wind_keys_b})")

    b_pass = not bool(cape_keys_b) and bool(wind_keys_b)

    passed = a_pass and b_pass
    status = "PASS" if passed else "FAIL"
    detail = f"A={a_pass}, B={b_pass}"
    print(f"  {status}: {detail}")
    results["alert_enabled Pipeline"] = f"{status}: {detail}"


# =====================================================================
# Run all tests
# =====================================================================

if __name__ == "__main__":
    if not IMAP_USER or not IMAP_PASS:
        print("FEHLER: GZ_SMTP_USER und GZ_SMTP_PASS muessen in .env gesetzt sein.")
        sys.exit(1)

    with open(TRIP_JSON) as f:
        original_json = f.read()

    try:
        run_test("Visibility friendly=ON", setup_visib_on, check_visib_friendly)
        run_test("Visibility friendly=OFF", setup_visib_off, check_visib_numeric)
        run_test("Cape friendly=ON", setup_cape_on, check_cape_friendly)
        run_test("Cape friendly=OFF", setup_cape_off, check_cape_numeric)
        run_test("Cloud friendly=ON", setup_cloud_on, check_cloud_friendly)
        run_test("Cloud friendly=OFF", setup_cloud_off, check_cloud_numeric)
        test_alert_enabled()
    finally:
        with open(TRIP_JSON, "w") as f:
            f.write(original_json)
        print("\n  Original Trip-JSON wiederhergestellt.")

    # Summary
    print(f'\n{"="*60}')
    print("ZUSAMMENFASSUNG")
    print(f'{"="*60}')
    total = len(results)
    passed = sum(1 for v in results.values() if v.startswith("PASS"))
    for name, result in results.items():
        symbol = "+" if result.startswith("PASS") else "x"
        print(f"  {symbol} {name}: {result}")
    print(f"\n  {passed}/{total} bestanden")

    sys.exit(0 if passed == total else 1)
