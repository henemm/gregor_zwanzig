"""TDD — Issue #2036 CI-Nachschlag (PR #2055): eine Vorschau ohne Alarm und
ohne Briefing-Versand darf den Trip-Bestand nicht veraendern.

Root Cause: `PreviewService._build_report` ("kein Versand, nur Render",
Modul-Docstring `preview_service.py`) ruft
`TripReportSchedulerService._convert_trip_to_segments`, die seit #2036 als
Seiteneffekt die gemessene Wegstrecke aus dem GPX-Bestand nachtraegt UND per
`save_trip` persistiert (Issue #2036 AC-7 -- dort gewollt fuer Alarm-/
Briefing-Versand). Fuer eine reine Vorschau ist die Persistenz ein
unbeabsichtigter Seiteneffekt: `GET .../preview/...` mutiert den Trip-Bestand
auf der Platte, obwohl kein Alarm und kein Briefing tatsaechlich verschickt
wird. Entdeckt, weil ein Live-Telegram-Test dieselbe Preview-Route gegen den
echten, versionierten `default`-User-Trip aufruft und der #1265-Kern-Test-
Waechter (`tests/conftest.py::_isolate_data_root`) die Mutation an
`data/users/` faengt.

Nutzt dieselbe GR221-Fixture + denselben Testaufbau wie
`test_track_resolution_legacy_trip.py::_trip_mit_gpx_im_bestand` (echte
GPX-Aufloesung, echtes `save_trip`, isolierte Datenwurzel per
`tests/conftest.py::_isolate_data_root`, kein Mock). Demo-Modus
(`FixtureProvider`) haelt den Test netzfrei (Kern-Schicht).

Nebenbefund (bewusst NICHT mitbehoben, ausserhalb dieses Scopes):
`PreviewService._build_report` baut `TripReportSchedulerService(self.settings)`
OHNE `user_id` -- der Scheduler faellt intern IMMER auf `"default"` zurueck,
unabhaengig vom `user_id`-Argument der oeffentlichen `render_*_preview`-
Methoden. Deshalb testet dieser Test bewusst mit `user_id="default"` (unter
der isolierten Testwurzel, beruehrt NICHT den echten Repo-Baum) -- exakt die
Kollision, die den CI-Fund ausgeloest hat. Fuer jeden anderen `user_id` griffe
die Nachruestung heute am FALSCHEN (default-)Datenverzeichnis vorbei, was ein
eigenes Cross-User-Datenthema ist (CLAUDE.md-Regel "niemals auf default
zurueckfallen") und ein eigenes Ticket verdient, kein Nebenprodukt dieses Fixes.
"""
from __future__ import annotations

from datetime import date

from app.loader import get_data_dir
from services.preview_service import PreviewService
from tests.tdd.test_track_resolution_legacy_trip import _trip_mit_gpx_im_bestand

# Bewusst "default" -- siehe Nebenbefund-Absatz oben im Modul-Docstring:
# PreviewService reicht ihren `user_id`-Parameter intern nicht durch, der
# Scheduler faellt immer auf "default" zurueck. Isoliert unter der
# Test-Datenwurzel (Issue #1265 `_isolate_data_root`), NICHT der echte Baum.
_USER = "default"


def test_preview_ohne_alarm_und_briefing_veraendert_den_trip_bestand_nicht():
    """Given ein Bestandstrip ohne gemessene Wegstrecke + passender Track im
    GPX-Bestand / When eine reine Vorschau (kein Versand) gerendert wird /
    Then bleibt die persistierte Trip-Datei byte-identisch -- die Vorschau
    darf die Nachruestung nur im Rueckgabeobjekt sehen, nicht auf die Platte
    schreiben."""
    heute = date(2026, 8, 26)
    trip = _trip_mit_gpx_im_bestand(_USER, heute)

    trip_datei = get_data_dir(_USER) / "briefings" / f"{trip.id}.json"
    assert trip_datei.exists(), f"Trip-Datei fehlt: {trip_datei}"
    inhalt_vorher = trip_datei.read_bytes()
    mtime_vorher = trip_datei.stat().st_mtime_ns

    service = PreviewService()
    subject, body, bubbles = service.render_telegram_preview(
        trip.id, user_id=_USER, report_type="morning",
        target_date=heute.isoformat(), demo=True,
    )
    assert isinstance(subject, str)
    assert bubbles, "Vorschau liefert keine Bubbles -- Testaufbau fehlerhaft"

    inhalt_nachher = trip_datei.read_bytes()
    mtime_nachher = trip_datei.stat().st_mtime_ns
    assert inhalt_nachher == inhalt_vorher, (
        "Die Vorschau hat den Trip-Bestand auf der Platte veraendert -- "
        "'kein Versand, nur Render' darf keine Seiteneffekte auf "
        f"data/users/{_USER}/briefings/{trip.id}.json haben"
    )
    assert mtime_nachher == mtime_vorher, (
        "Trip-Datei wurde neu geschrieben (mtime geaendert), obwohl der "
        "Inhalt gleich geblieben sein soll -- kein reiner Lesepfad"
    )
