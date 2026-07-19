"""
TDD RED — Issue #1087 (Epic #1073 Slice 3): Amtliche Warnungen in
Trip-Briefings + gemeinsamer Renderer + Trip-Toggle.

SPEC: docs/specs/modules/epic_1073_trip_official_alerts.md
AC-1..AC-6

Verhaltenstests — KEINE Mocks. Echte Fake-Quellen (strukturelles Protocol-
Subtyping von OfficialAlertSource) über register_official_alert_source(),
echte Scheduler-Läufe, echter Versand + IMAP-Verifikation (analog
tests/tdd/test_issue_768_test_briefing_fallback.py / test_issue_1040_alerts_toggle.py).

Design-Entscheidung fuer schnelles RED: jeder Scheduler-basierte Test prueft
zuerst den Call-Counter der registrierten Fake-Quelle (>=1). Das schlaegt
HEUTE sofort fehl (Quelle wird fuer Trips noch gar nicht aufgerufen) -- ohne
auf den 60s-IMAP-Poll warten zu muessen. Nach der Implementierung (GREEN)
laeuft der Test weiter bis zur echten IMAP-Verifikation des Warn-Labels.
"""
from __future__ import annotations

import imaplib
import json
import time
import uuid
from datetime import date, datetime, timezone
from email import message_from_bytes
from email.header import decode_header, make_header
from pathlib import Path

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Issue #1210 B1: echter Versand + IMAP-Verifikation -> addopts-wirksamer
# Marker statt nur Credential-Skip (primaere Ausschlussmechanik).
pytestmark = pytest.mark.email

NICE_LAT = 43.7102
NICE_LON = 7.2620


# ---------------------------------------------------------------------------
# Fake Official-Alert-Quellen (echte Python-Objekte, kein Mock)
# ---------------------------------------------------------------------------

class _CoordMatchOfficialAlertSource:
    """Zustaendig fuer einen konkreten Punkt (0.05-Grad-Toleranz), liefert
    genau einen OfficialAlert und zaehlt jeden fetch()-Aufruf."""

    def __init__(self, lat: float, lon: float, alert) -> None:
        self._lat = lat
        self._lon = lon
        self._alert = alert
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1087-coord-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        return [self._alert]


class _ErroringOfficialAlertSource:
    """Zustaendig fuer einen konkreten Punkt, wirft bei fetch() immer eine
    RuntimeError (simulierter Quellenausfall, AC-4). Zaehlt Aufrufe VOR dem
    Werfen, um Invocation nachzuweisen."""

    def __init__(self, lat: float, lon: float) -> None:
        self._lat = lat
        self._lon = lon
        self.fetch_calls = 0

    @property
    def name(self) -> str:
        return "test-1087-erroring-source"

    def covers(self, lat: float, lon: float) -> bool:
        return abs(lat - self._lat) < 0.05 and abs(lon - self._lon) < 0.05

    def fetch(self, lat: float, lon: float):
        self.fetch_calls += 1
        raise RuntimeError("simulierter Quellenausfall (#1087 AC-4)")


# ---------------------------------------------------------------------------
# Helpers: Trip-/User-Fixtures, echter Versand, IMAP-Poll
# ---------------------------------------------------------------------------

def _fr_trip_dict(
    trip_id: str,
    target_date: date,
    *,
    official_alerts_enabled: bool | None = None,
    email_format: str | None = None,
) -> dict:
    """Trip mit einer Etappe an der Cote d'Azur (real, ausserhalb GeoSphere-
    Bbox lat45-50/lon8-18 -> openmeteo-Zweig -> Offline-FixtureProvider ueber
    tests/conftest.py autouse-Fixture, kein echter Netzwerkruf noetig)."""
    rc: dict = {"send_email": True, "send_telegram": False, "send_sms": False}
    if email_format is not None:
        rc["email_format"] = email_format
    d: dict = {
        "id": trip_id,
        "name": f"TDD-1087 {trip_id}",
        "stages": [{
            "id": "s1",
            "name": "Etappe Cote d'Azur",
            "date": target_date.isoformat(),
            "waypoints": [
                {"id": "w1", "name": "Nizza", "lat": NICE_LAT, "lon": NICE_LON, "elevation_m": 10},
                {"id": "w2", "name": "Villefranche", "lat": 43.7048, "lon": 7.3131, "elevation_m": 20},
            ],
        }],
        "report_config": rc,
        "alert_rules": [],
    }
    if official_alerts_enabled is not None:
        d["official_alerts_enabled"] = official_alerts_enabled
    return d


def _write_user_profile(user_id: str) -> None:
    profile_dir = REPO_ROOT / "data" / "users" / user_id
    profile_dir.mkdir(parents=True, exist_ok=True)
    (profile_dir / "user.json").write_text(
        json.dumps({"mail_to": "gregor-test@henemm.com"}), encoding="utf-8"
    )


def _cleanup_user(user_id: str) -> None:
    import shutil
    user_dir = REPO_ROOT / "data" / "users" / user_id
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)


def _poll_imap_for_marker(settings, marker: str, attempts: int = 12, wait_s: int = 5):
    """Pollt INBOX nach einer Mail mit `marker` im Betreff (analog #768).

    Returns: (subject, body_text) -- subject bleibt None, wenn nichts gefunden wurde.
    """
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    if not all([imap_host, imap_user, imap_pass]):
        pytest.skip("IMAP-Credentials fehlen")

    subject = None
    body_text = ""
    for _ in range(attempts):
        time.sleep(wait_s)
        imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port or 993, timeout=15)
        try:
            imap.login(imap_user, imap_pass)
            imap.select("INBOX")
            _, data = imap.search(None, f'SUBJECT "{marker}"')
            ids = data[0].split()
            if ids:
                _, msg = imap.fetch(ids[-1], "(RFC822)")
                parsed = message_from_bytes(msg[0][1])
                subject = str(make_header(decode_header(parsed.get("Subject", ""))))
                for part in parsed.walk():
                    if part.get_content_type() in ("text/plain", "text/html"):
                        payload = part.get_payload(decode=True)
                        if payload:
                            body_text += payload.decode("utf-8", "ignore")
                break
        finally:
            try:
                imap.logout()
            except Exception:
                pass
    return subject, body_text


def _registered_sources_backup():
    import services.official_alerts.base as oa_base
    return oa_base, list(oa_base._REGISTERED_SOURCES)


# ---------------------------------------------------------------------------
# AC-1: FR-Trip-Etappe + aktive Warnung -> Label in zugestellter Mail
# ---------------------------------------------------------------------------

class TestAC1TripOfficialAlertsFR:
    def test_scheduler_run_includes_official_alert_label_for_fr_trip(self):
        """
        GIVEN: Trip mit FR-Etappe (Nizza), aktive Test-Quelle fuer diese
               Koordinate, official_alerts_enabled nicht auf False gesetzt.
        WHEN:  Scheduler generiert + versendet ein Briefing.
        THEN:  Die zugestellte, per IMAP abgerufene Mail enthaelt das
               Warnung-Label.

        RED: Der Trip-Fetch-Pfad ruft die registrierten Official-Alert-
        Quellen noch nicht ab -> fetch_calls bleibt 0 (schneller Fehlschlag,
        kein 60s-Warten noetig).
        """
        from app.config import Settings
        from app.loader import load_trip_from_dict
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id = "tdd-1087-ac1"
        _write_user_profile(user_id)
        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP fuer tdd-1087-ac1 nicht konfiguriert")

        try:
            marker = uuid.uuid4().hex[:8]
            trip_dict = _fr_trip_dict("tdd-1087-ac1-trip", date.today())
            trip = load_trip_from_dict(trip_dict)
            trip.name = f"{trip.name} [{marker}]"

            alert = OfficialAlert(
                source="test-1087-fr",
                hazard="thunderstorm",
                level=3,
                label=f"Gewitterwarnung Cote d'Azur {marker}",
            )
            counting_source = _CoordMatchOfficialAlertSource(NICE_LAT, NICE_LON, alert)

            oa_base, backup = _registered_sources_backup()
            oa_base._REGISTERED_SOURCES.clear()
            try:
                register_official_alert_source(counting_source)

                outcome = TripReportSchedulerService(user_id=user_id).send_on_demand_report(
                    trip, "morning"
                )
                assert counting_source.fetch_calls >= 1, (
                    "RED: der Trip-Briefing-Pfad ruft die registrierten "
                    "Official-Alert-Quellen noch nicht ab (fetch_calls=0)."
                )
                assert outcome == "sent", f"Erwartet Outcome 'sent', bekommen {outcome!r}"

                subject, body = _poll_imap_for_marker(settings, marker)
                assert subject is not None, f"Keine Mail mit Marker {marker} in 60s gefunden"
                assert alert.label in body, (
                    f"Warnung-Label {alert.label!r} fehlt im zugestellten Mail-Body — "
                    "Renderer zeigt die Trip-Alerts noch nicht an."
                )
            finally:
                oa_base._REGISTERED_SOURCES.clear()
                oa_base._REGISTERED_SOURCES.extend(backup)
        finally:
            _cleanup_user(user_id)


# ---------------------------------------------------------------------------
# AC-2: Gemeinsamer Renderer -- Architektur-Compliance + Golden-Byte-Regression
# ---------------------------------------------------------------------------

class TestAC2SharedRendererNoDuplicate:

    # doc-compliance-test
    def test_shared_module_exists_and_is_wired_into_all_renderers(self):
        """AC-2(a) — Architektur-Compliance: das Shared-Modul existiert und
        wird von Compare UND allen drei Trip-Mail-Renderern importiert (kein
        eigenstaendiger Duplikat-Code fuer die Warn-Darstellung).

        Haertung (Adversary-Finding F001, Issue #1087 Fix-Runde): ein reiner
        Substring-Check im Quellcode uebersieht, wenn derselbe Modulpfad ueber
        ZWEI verschiedene Importpraefixe (`output.` vs. `src.output.`) geladen
        wird -> Python legt dann zwei unabhaengige Modul-/Funktionsobjekte in
        `sys.modules` an. Deshalb hier zusaetzlich ein `is`-Identitaetsbeweis
        auf den tatsaechlich gebundenen Funktionsobjekten.

        RED (vor F001-Fix): `compare_html.py` importierte das Shared-Modul
        ueber den bare `output.`-Praefix, alle Trip-Renderer ueber
        `src.output.` -> zwei sys.modules-Eintraege -> `is`-Vergleich `False`.
        """
        import importlib
        import inspect

        shared = importlib.import_module("output.renderers.alert.official_alerts")
        assert hasattr(shared, "render_official_alerts_html")
        assert hasattr(shared, "render_official_alerts_plain")
        assert hasattr(shared, "collect_trip_alert_entries")

        compare_html_mod = importlib.import_module("output.renderers.email.compare_html")
        html_mod = importlib.import_module("output.renderers.email.html")
        plain_mod = importlib.import_module("output.renderers.email.plain")
        compact_mod = importlib.import_module("output.renderers.email.compact")

        for mod in (compare_html_mod, html_mod, plain_mod, compact_mod):
            src = inspect.getsource(mod)
            assert "renderers.alert.official_alerts" in src, (
                f"{mod.__name__} importiert die Warn-Rendering-Funktionen "
                "nicht aus dem gemeinsamen Modul (Duplikat-Verdacht)."
            )

        # Identitaetsbeweis (F001): Compare- und alle Trip-Renderer muessen
        # DASSELBE Funktionsobjekt gebunden haben, nicht nur textuell
        # denselben Modulnamen importieren.
        assert compare_html_mod.render_official_alerts_html is shared.render_official_alerts_html, (
            "compare_html.render_official_alerts_html ist NICHT dasselbe "
            "Funktionsobjekt wie im Shared-Modul -> zwei Modulinstanzen (F001)."
        )
        assert html_mod.render_official_alerts_html is shared.render_official_alerts_html, (
            "html.render_official_alerts_html ist NICHT dasselbe Funktionsobjekt "
            "wie im Shared-Modul -> zwei Modulinstanzen (F001)."
        )
        assert plain_mod.render_official_alerts_plain is shared.render_official_alerts_plain, (
            "plain.render_official_alerts_plain ist NICHT dasselbe Funktionsobjekt "
            "wie im Shared-Modul -> zwei Modulinstanzen (F001)."
        )
        assert compact_mod.render_official_alerts_plain is shared.render_official_alerts_plain, (
            "compact.render_official_alerts_plain ist NICHT dasselbe Funktionsobjekt "
            "wie im Shared-Modul -> zwei Modulinstanzen (F001)."
        )

        # Kein eigenstaendiger Duplikat-Loop ausserhalb des Shared-Moduls.
        comparison_mod = importlib.import_module("output.renderers.comparison")
        assert comparison_mod.render_official_alerts_plain is shared.render_official_alerts_plain, (
            "comparison.render_official_alerts_plain ist NICHT dasselbe "
            "Funktionsobjekt wie im Shared-Modul -> zwei Modulinstanzen (F001)."
        )
        comparison_src = inspect.getsource(comparison_mod)
        assert "for alert in" not in comparison_src, (
            "comparison.py enthaelt weiterhin einen eigenstaendigen "
            "official_alerts-Iterations-Block statt den Shared-Renderer "
            "zu nutzen (Duplikat, verstoesst gegen Epic #1073 Punkt 6)."
        )

    def test_compare_html_official_alerts_fragment_byte_identical(self):
        """AC-2(b): Golden-Byte-Regression — der Alert-Badge-Fragment-Output
        von `render_compare_html()` stammt weiterhin aus dem Shared-Renderer
        (kein Duplikat), nur mit den compare-spezifischen Argumenten.

        F002 (Adversary Fix-Runde, Issue #1110): der Compare-Aufruf uebergibt
        ein leeres Gruppen-Label (kein Ortsnamen-Praefix mehr im Langform-
        Streifen -- der Ort-Kopf nennt den Namen bereits).

        Issue #1056 v2.0 (supersedet #1134s hazard-aware Faerbung): Compare-
        und Trip-Pfad sind jetzt WIEDER vereinheitlicht -- beide faerben
        ausschliesslich nach der amtlichen `alert.level`. Ein Level-3-Alert
        rendert in BEIDEN Pfaden **G_ALERT_L3 (#c8482a, Orange-Rot)**, ein
        gemeinsames Golden-Fragment genuegt.
        """
        from output.renderers.alert.official_alerts import render_official_alerts_html
        from app.profile import ActivityProfile
        from app.user import ComparisonResult, LocationResult, SavedLocation
        from output.renderers.email.compare_html import (
            _dedup_alerts, render_compare_html,
        )
        from services.official_alerts.models import OfficialAlert

        def _fragment(border_hex: str) -> str:
            return (
                f'<div style="background:#f6f4ee;border-left:4px solid {border_hex};'
                'padding:8px 16px;margin:8px 20px;border-radius:4px;'
                'font-family:\'Inter Tight\', -apple-system, BlinkMacSystemFont, '
                '\'Segoe UI\', Roboto, sans-serif;font-size:13px;color:#1a1a18;">'
                '<span>Gewitterwarnung Stufe Orange</span></div>'
            )

        # Level-basiert (Issue #1056 v2.0): beide Pfade Level 3 -> #c8482a.
        golden = _fragment("#c8482a")

        loc = SavedLocation(id="riviera-nice", name="Nizza", lat=NICE_LAT, lon=NICE_LON, elevation_m=10)
        alert = OfficialAlert(
            source="test-golden", hazard="thunderstorm", level=3,
            label="Gewitterwarnung Stufe Orange",
        )
        # Issue #1110 (v2): der Langform-Warnstreifen (der den Shared-Renderer
        # aufruft) erscheint nur ueber der Stundentabelle eines Ortes -- ohne
        # hourly_data entfaellt der ganze Ort-Abschnitt (Spec §4). Minimaler
        # Stundenpunkt noetig, damit der Golden-Fragment-Code-Pfad ueberhaupt
        # erreicht wird.
        from app.models import ForecastDataPoint
        from datetime import datetime as _dt
        dp = ForecastDataPoint(ts=_dt(2026, 7, 8, 9, 0), t2m_c=25.0)
        lr = LocationResult(location=loc, score=80, official_alerts=[alert], hourly_data=[dp])
        result = ComparisonResult(locations=[lr], time_window=(9, 16), target_date=date.today())

        html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
        assert golden in html, (
            "Compare-HTML Alert-Badge weicht vom eingefrorenen Level-Golden "
            "(#1056 v2.0) ab."
        )

        # Beweis: der Compare-Pfad nutzt den Shared-Renderer (kein Duplikat),
        # nur mit seinen eigenen Argumenten (dedup). Byte-Gleich zum Fragment
        # im gerenderten HTML.
        compare_shared = render_official_alerts_html(
            [("", _dedup_alerts([alert]))],
        )
        assert compare_shared == golden, (
            "Compare-Badge muss byte-gleich aus dem Shared-Renderer stammen "
            "-- kein dupliziertes Compare-Badge-Markup."
        )

        # Trip-Pfad ist jetzt byte-gleich zum Compare-Pfad (beide level-basiert).
        trip_shared = render_official_alerts_html([("", [alert])])
        assert trip_shared == golden, (
            "Trip-Pfad (render_official_alerts_html) muss byte-gleich zum "
            "level-basierten Golden bleiben."
        )

    def test_massif_closure_style_alert_renders_label_once(self):
        """F002 (Adversary-Finding, Issue #1087 Fix-Runde): eine Massiv-Sperre
        setzt NIE `region_label` (siehe `massif_closure.py::_niveau_to_alert`).
        `collect_trip_alert_entries()` faellt dann fuer den Gruppierungs-Key
        auf `alert.label` zurueck -> ohne Fix rendert
        `render_official_alerts_html()` den Praefix-Span UND den Alert-Text
        mit demselben String ("X: X"). Kein Mock — echtes `OfficialAlert`-
        Objekt (kein `region_label`) durch die echte Trip-Pipeline
        (`collect_trip_alert_entries` + `render_official_alerts_html`).

        RED (vor F002-Fix): das Label erscheint ZWEIMAL im HTML-Fragment.
        """
        from services.official_alerts.models import OfficialAlert
        from output.renderers.alert.official_alerts import (
            collect_trip_alert_entries, render_official_alerts_html,
        )

        massif_label = "Zugang gesperrt — Corniche Des Maures"
        alert = OfficialAlert(
            source="massif_closure", hazard="access_ban", level=4,
            label=massif_label,
        )  # region_label bleibt None, exakt wie massif_closure.py es erzeugt.

        seg = _sms_segment(1, date.today(), 7, 13, official_alerts=[alert])
        entries = collect_trip_alert_entries([seg])
        html = render_official_alerts_html(entries)

        assert html.count(massif_label) == 1, (
            "Massiv-Sperre-Label darf nur EINMAL im HTML erscheinen, nicht "
            f"als doppelter Praefix+Text ('X: X'). HTML: {html!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Toggle -- kein Fetch bei False (Scheduler-Gating) + Persistenz-Roundtrip
# ---------------------------------------------------------------------------

class TestAC3ToggleNoFetch:
    def test_toggle_disabled_skips_fetch_and_hides_warning(self):
        """
        GIVEN: Trip mit official_alerts_enabled=False, registrierte
               Test-Fake-Quelle mit Aufruf-Zaehler (wuerde bei Aufruf einen
               Treffer liefern).
        WHEN:  Scheduler generiert ein Briefing fuer diesen Trip.
        THEN:  Die Fake-Quelle wird NICHT aufgerufen (Call-Counter=0).

        RED: `Trip` kennt `official_alerts_enabled` noch nicht -> die erste
        Zugriffs-Assertion loest AttributeError aus (schneller Fehlschlag,
        kein Netzwerk-/SMTP-Kontakt noetig).
        """
        from app.config import Settings
        from app.loader import load_trip_from_dict
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id = "tdd-1087-ac3"
        _write_user_profile(user_id)
        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP fuer tdd-1087-ac3 nicht konfiguriert")

        try:
            trip_dict = _fr_trip_dict(
                "tdd-1087-ac3-trip", date.today(), official_alerts_enabled=False,
            )
            trip = load_trip_from_dict(trip_dict)
            assert trip.official_alerts_enabled is False, (
                "RED: Trip-Dataclass kennt official_alerts_enabled noch nicht "
                f"(erhalten: {getattr(trip, 'official_alerts_enabled', 'FEHLT')!r})."
            )

            alert = OfficialAlert(
                source="test-1087-toggle", hazard="thunderstorm", level=3,
                label="Gewitterwarnung darf NICHT erscheinen",
            )
            counting_source = _CoordMatchOfficialAlertSource(NICE_LAT, NICE_LON, alert)

            oa_base, backup = _registered_sources_backup()
            oa_base._REGISTERED_SOURCES.clear()
            try:
                register_official_alert_source(counting_source)
                outcome = TripReportSchedulerService(user_id=user_id).send_on_demand_report(
                    trip, "morning"
                )
                assert outcome == "sent", f"Erwartet Outcome 'sent', bekommen {outcome!r}"
                assert counting_source.fetch_calls == 0, (
                    "official_alerts_enabled=False muss den Fetch verhindern, aber "
                    f"fetch() wurde {counting_source.fetch_calls}x aufgerufen."
                )
            finally:
                oa_base._REGISTERED_SOURCES.clear()
                oa_base._REGISTERED_SOURCES.extend(backup)
        finally:
            _cleanup_user(user_id)


class TestAC3LoaderRoundtripPersistence:
    def test_save_load_roundtrip_preserves_official_alerts_enabled_false(self, tmp_path):
        """
        GIVEN: Trip mit official_alerts_enabled=False.
        WHEN:  save_trip() -> load_trip() (Read-Modify-Write-Roundtrip).
        THEN:  official_alerts_enabled bleibt False, andere Felder
               unveraendert (BUG-DATALOSS-GR221 — kein Datenverlust).

        RED: `Trip`-Dataclass kennt das Feld `official_alerts_enabled` noch
        nicht als Konstruktor-Kwarg -> TypeError bereits beim Aufbau.
        """
        from app.loader import load_trip, save_trip
        from app.trip import Stage, Trip, Waypoint

        wp1 = Waypoint(id="w1", name="Nizza", lat=NICE_LAT, lon=NICE_LON, elevation_m=10)
        wp2 = Waypoint(id="w2", name="Villefranche", lat=43.7048, lon=7.3131, elevation_m=20)
        stage = Stage(id="s1", name="Etappe Cote d'Azur", date=date.today(), waypoints=[wp1, wp2])
        trip = Trip(
            id="tdd-1087-loader-roundtrip",
            name="Roundtrip Trip",
            stages=[stage],
            alert_rules=[],
            official_alerts_enabled=False,
        )
        user_id = "tdd-1087-loader"

        save_trip(trip, user_id=user_id, data_dir=str(tmp_path))
        loaded = load_trip(trip.id, data_dir=str(tmp_path), user_id=user_id)

        assert loaded is not None
        assert loaded.official_alerts_enabled is False, (
            f"official_alerts_enabled=False muss erhalten bleiben, geladen: "
            f"{getattr(loaded, 'official_alerts_enabled', 'FEHLT')!r}"
        )
        assert loaded.name == "Roundtrip Trip", "Read-Modify-Write darf andere Felder nicht veraendern"
        assert len(loaded.stages) == 1 and loaded.stages[0].id == "s1"
        assert len(loaded.stages[0].waypoints) == 2


# ---------------------------------------------------------------------------
# AC-4: Fail-soft -- Quellenausfall darf Briefing nicht crashen
# ---------------------------------------------------------------------------

class TestAC4FailSoft:
    def test_erroring_source_does_not_crash_briefing(self):
        """
        GIVEN: registrierte Test-Quelle, deren fetch() eine RuntimeError wirft.
        WHEN:  Scheduler generiert ein Briefing fuer einen betroffenen Trip.
        THEN:  Outcome bleibt 'sent' (kein Crash, kein no_weather-Abbruch nur
               wegen des Alert-Fetches), Mail wird vollstaendig zugestellt.

        RED: der Trip-Fetch-Pfad ruft die Quelle noch gar nicht ab -> die
        Erroring-Quelle wird nie invoked (fetch_calls bleibt 0) -- der
        Fail-soft-Pfad kann mangels Integration noch nicht bewiesen werden.
        """
        from app.config import Settings
        from app.loader import load_trip_from_dict
        from services.official_alerts import register_official_alert_source
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id = "tdd-1087-ac4"
        _write_user_profile(user_id)
        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP fuer tdd-1087-ac4 nicht konfiguriert")

        try:
            marker = uuid.uuid4().hex[:8]
            trip_dict = _fr_trip_dict("tdd-1087-ac4-trip", date.today())
            trip = load_trip_from_dict(trip_dict)
            trip.name = f"{trip.name} [{marker}]"

            erroring_source = _ErroringOfficialAlertSource(NICE_LAT, NICE_LON)

            oa_base, backup = _registered_sources_backup()
            oa_base._REGISTERED_SOURCES.clear()
            try:
                register_official_alert_source(erroring_source)

                outcome = TripReportSchedulerService(user_id=user_id).send_on_demand_report(
                    trip, "morning"
                )
                assert erroring_source.fetch_calls >= 1, (
                    "RED: der Trip-Briefing-Pfad ruft die registrierten "
                    "Official-Alert-Quellen noch nicht ab (fetch_calls=0), "
                    "Fail-soft-Pfad daher noch nicht pruefbar."
                )
                assert outcome == "sent", (
                    f"Ein Quellenausfall darf das Briefing nicht crashen/abbrechen, "
                    f"Outcome war {outcome!r} statt 'sent'."
                )

                subject, body = _poll_imap_for_marker(settings, marker)
                assert subject is not None, f"Keine Mail mit Marker {marker} in 60s gefunden"
                assert len(body) > 200, (
                    "Briefing-Body wirkt unvollstaendig/leer trotz Fail-soft-Anspruch "
                    f"(nur {len(body)} Zeichen)."
                )
            finally:
                oa_base._REGISTERED_SOURCES.clear()
                oa_base._REGISTERED_SOURCES.extend(backup)
        finally:
            _cleanup_user(user_id)


# ---------------------------------------------------------------------------
# AC-5: Compact-Format enthaelt Warn-Zeile
# ---------------------------------------------------------------------------

class TestAC5CompactFormat:
    def test_compact_email_contains_official_alert_label(self):
        """
        GIVEN: Trip-Briefing mit email_format='compact', aktive Test-Quelle.
        WHEN:  Scheduler generiert + versendet das Briefing.
        THEN:  Der kompakte Text-Body enthaelt das Warnung-Label.

        RED: der Trip-Fetch-Pfad ruft die Quelle noch nicht ab -> fetch_calls
        bleibt 0 (schneller Fehlschlag).
        """
        from app.config import Settings
        from app.loader import load_trip_from_dict
        from services.official_alerts import OfficialAlert, register_official_alert_source
        from services.trip_report_scheduler import TripReportSchedulerService

        user_id = "tdd-1087-ac5"
        _write_user_profile(user_id)
        settings = Settings().with_user_profile(user_id)
        if not settings.can_send_email():
            pytest.skip("SMTP fuer tdd-1087-ac5 nicht konfiguriert")

        try:
            marker = uuid.uuid4().hex[:8]
            trip_dict = _fr_trip_dict(
                "tdd-1087-ac5-trip", date.today(), email_format="compact",
            )
            trip = load_trip_from_dict(trip_dict)
            trip.name = f"{trip.name} [{marker}]"

            alert = OfficialAlert(
                source="test-1087-compact", hazard="thunderstorm", level=3,
                label=f"Gewitterwarnung Kompakt {marker}",
            )
            counting_source = _CoordMatchOfficialAlertSource(NICE_LAT, NICE_LON, alert)

            oa_base, backup = _registered_sources_backup()
            oa_base._REGISTERED_SOURCES.clear()
            try:
                register_official_alert_source(counting_source)

                outcome = TripReportSchedulerService(user_id=user_id).send_on_demand_report(
                    trip, "morning"
                )
                assert counting_source.fetch_calls >= 1, (
                    "RED: der Trip-Briefing-Pfad ruft die registrierten "
                    "Official-Alert-Quellen noch nicht ab (fetch_calls=0)."
                )
                assert outcome == "sent", f"Erwartet Outcome 'sent', bekommen {outcome!r}"

                subject, body = _poll_imap_for_marker(settings, marker)
                assert subject is not None, f"Keine Mail mit Marker {marker} in 60s gefunden"
                assert alert.label in body, (
                    f"Kompakter Body enthaelt das Warnung-Label {alert.label!r} nicht."
                )
            finally:
                oa_base._REGISTERED_SOURCES.clear()
                oa_base._REGISTERED_SOURCES.extend(backup)
        finally:
            _cleanup_user(user_id)


# ---------------------------------------------------------------------------
# AC-6: SMS bleibt bewusst ohne Warn-Block
# ---------------------------------------------------------------------------

def _sms_segment(seg_id: int, day: date, hour_start: int, hour_end: int, *, official_alerts=None):
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    segment = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=NICE_LAT, lon=NICE_LON, elevation_m=10.0),
        end_point=GPXPoint(lat=43.72, lon=7.27, elevation_m=50.0),
        start_time=datetime(day.year, day.month, day.day, hour_start, 0, tzinfo=timezone.utc),
        end_time=datetime(day.year, day.month, day.day, hour_end, 0, tzinfo=timezone.utc),
        duration_hours=float(hour_end - hour_start),
        distance_km=5.0,
        ascent_m=100.0,
        descent_m=50.0,
    )
    hourly_points = [
        ForecastDataPoint(
            ts=datetime(day.year, day.month, day.day, h, 0),
            t2m_c=18.0,
            wind10m_kmh=15.0,
            precip_1h_mm=0.0,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(hour_start, hour_end + 1)
    ]
    summary = SegmentWeatherSummary(
        temp_max_c=20.0, temp_min_c=16.0, wind_max_kmh=15.0,
        thunder_level_max=ThunderLevel.NONE, precip_sum_mm=0.0,
    )
    kwargs = dict(
        segment=segment,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=hourly_points,
        ),
        aggregated=summary,
        fetched_at=datetime(2026, 7, 7, tzinfo=timezone.utc),
        provider="openmeteo",
    )
    if official_alerts is not None:
        kwargs["official_alerts"] = official_alerts
    return SegmentWeatherData(**kwargs)


class TestAC6SmsWithoutAlertBlock:
    def test_sms_with_official_alerts_segment_field_stays_alert_free(self):
        """
        GIVEN: SMS-Trip-Renderer-Aufruf mit segments, die official_alerts
               tragen.
        WHEN:  format_sms() rendert die SMS.
        THEN:  Kein Alert-Fragment im Text, Ausgabe identisch zum
               Zustand ohne Alerts, weiterhin <=160 Zeichen.

        RED: `SegmentWeatherData` kennt das Feld `official_alerts` noch
        nicht als Konstruktor-Kwarg -> TypeError bereits beim Segment-Aufbau.
        """
        from services.official_alerts.models import OfficialAlert
        from output.renderers.sms_trip import SMSTripFormatter

        today = date(2026, 7, 8)
        alert = OfficialAlert(
            source="test-1087-sms", hazard="thunderstorm", level=3,
            label="Gewitterwarnung Stufe Orange SMS",
        )

        seg_without = _sms_segment(1, today, 7, 13)
        seg_with = _sms_segment(1, today, 7, 13, official_alerts=[alert])

        formatter = SMSTripFormatter()
        sms_without = formatter.format_sms(
            [seg_without], stage_name="Etappe 1", report_type="morning",
        )
        sms_with = formatter.format_sms(
            [seg_with], stage_name="Etappe 1", report_type="morning",
        )

        assert alert.label not in sms_with, "SMS darf keinen Alert-Text enthalten (bewusst ohne Paritaet)"
        assert sms_with == sms_without, (
            "SMS-Ausgabe darf sich durch official_alerts NICHT veraendern "
            f"(ohne: {sms_without!r}, mit: {sms_with!r})"
        )
        assert len(sms_with) <= 160, f"SMS ueberschreitet 160 Zeichen: {len(sms_with)}"
