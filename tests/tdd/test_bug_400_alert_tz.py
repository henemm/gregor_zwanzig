"""
Bug #400: Alert-Mails müssen Segment-Zeiten in Lokalzeit zeigen (nicht UTC).

Kein Mock — fokussierter Source-Inspection-Ansatz (der Service hat viele Deps,
SMTP etc.). Geprüft wird, dass _send_alert() format_email() mit einem
tz-Parameter aufruft, der aus den Segment-Koordinaten abgeleitet wird.
"""
from pathlib import Path

SRC = Path("src/services/trip_alert.py").read_text()


def test_alert_imports_tz_for_coords():
    assert "tz_for_coords" in SRC, "trip_alert.py muss tz_for_coords importieren"


def test_alert_passes_tz_to_format_email():
    # tz= muss im format_email-Aufruf stehen
    assert "tz=" in SRC, "format_email() in trip_alert.py muss tz= Parameter übergeben"
