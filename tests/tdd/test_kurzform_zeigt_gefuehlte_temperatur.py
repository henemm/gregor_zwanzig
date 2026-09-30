"""TDD — Bug #2454 (AC-3b, AC-13): Kurzform zeigt FD/FL/FN, sobald die
wind_chill-Kind-Groessen nicht mehr eingefroren sind.

Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md
Kontext: docs/context/bug-2454-kurzform-gefuehlte-temperatur.md

AC-3b (Wirkort-Nachweis, "Pruefort = Wirkort" wie
tests/tdd/test_temp_tagesrichtung_aufloesung.py): ein bereits KORREKT
befuellter Bestand (Kind-Eintraege explizit enabled:true, wie ihn der
gefixte Editor jetzt schreibt bzw. wie ihn die Migration herstellt) muss
Loader (``src/app/loader.py::_parse_display_config``, DIESELBE Funktion, die
``load_trip()`` fuer jede ``briefings/*.json`` aufruft) und Renderer
(``TripReportFormatter``, intern ``output/tokens/builder.py::build_token_line``)
unveraendert durchlaufen und FD/FL im SMS-Kanal erzeugen. Vermutlich schon
gruen heute (Loader/Renderer sind durch diese Spec nicht angefasst) --
WAECHTER, kein RED-Beweis fuer #2454 selbst (der steht in der Editor- und
Migrations-Testschicht).

AC-13 (E2E-Kern): Fixture (eingefrorenes KHW-403-Muster) -> Migrationsskript
(RED, existiert noch nicht) -> Loader -> Renderer -> Kurzform-Text enthaelt
FD/FL, wo er sie VOR der Migration nicht enthielt. Zusaetzlich: derselbe Text
ist unveraendert der Premium-SMS-Nachrichtentext (echter lokaler HTTP-Stub
als Transport-Ersatz, Vorbild ``tests/unit/test_premium_sms_versand.py`` --
kein Mock, kein patch()).

Kern-Schicht, deterministisch: kein Netz ausser dem LOKALEN 127.0.0.1-Stub
fuer den Premium-SMS-Transport-Nachweis (dafuer laeuft diese Datei bewusst
NICHT mit --disable-socket, exakt wie ihr Vorbild).
"""
from __future__ import annotations

import http.server
import json
import socket
import subprocess
import sys
import threading
import urllib.parse
from datetime import timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from app.loader import _parse_display_config, get_data_dir  # noqa: E402
from output.channels.premium_sms import PremiumSmsOutput  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402

from tests.tdd import _min_temp_felt_fixtures as F  # noqa: E402

WIND_CHILL_KIDS = ("wind_chill_night", "wind_chill_day_low", "wind_chill_day_high")


def _script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_2454_derived_children.py"


def _frozen_wind_chill_layout(order: int = 0) -> list[dict]:
    return [
        {"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": order},
        {"metric_id": "wind_chill_night", "enabled": False, "order": 0},
        {"metric_id": "wind_chill_day_low", "enabled": False, "order": 0},
        {"metric_id": "wind_chill_day_high", "enabled": False, "order": 0},
    ]


def _clean_wind_chill_layout(order: int = 0) -> list[dict]:
    """Nach der Migration bzw. wie der gefixte Editor speichert: die drei
    Kinder stehen explizit enabled:true (die Ableitung ist beim Speichern
    schon aufgeloest -- der Loader wuerde sie notfalls ohnehin nachziehen)."""
    liste = [{"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": order}]
    for kid in WIND_CHILL_KIDS:
        liste.append({"metric_id": kid, "enabled": True, "bucket": "primary", "order": order})
    return liste


def _report_for(sms_layout: list[dict]):
    """Baut den Report exakt ueber den Loader-Parser, mit einer
    Kanal-eigenen SMS-Auswahl (channel_layouts.sms) -- derselbe Weg wie
    KHW 403."""
    raw = {
        "trip_id": "b2454",
        "metrics": [{"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 0}],
        "channel_layouts": {"sms": sms_layout},
    }
    dc = _parse_display_config(raw)
    return TripReportFormatter().format_email(
        [F.segment()], trip_name="B2454", report_type="evening",
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-3b — Wirkort-Nachweis: korrekt befuellter Bestand zeigt FD/FL im SMS-Kanal
# ═══════════════════════════════════════════════════════════════════════════

class TestAc3bLoaderUndRendererZeigenFdFl:

    def test_frozen_layout_shows_neither_fd_nor_fl(self):
        """Negativkontrolle: das eingefrorene Muster (heutiger Bug-Zustand)
        zeigt WEDER FD noch FL im SMS-Kanal."""
        sms = _report_for(_frozen_wind_chill_layout()).sms_text
        assert F.sms_token_value(sms, "FD") is None, f"FD erscheint trotz eingefrorenem Muster.\nSMS: {sms}"
        assert F.sms_token_value(sms, "FL") is None, f"FL erscheint trotz eingefrorenem Muster.\nSMS: {sms}"

    def test_clean_layout_shows_fd_and_fl_in_sms_channel(self):
        """AC-3b: ein korrekt befuellter (nicht eingefrorener) Bestand zeigt
        FD und FL im SMS-Kanal -- WAECHTER (misst den Wirkort Loader+Renderer,
        nicht den Editor/die Migration selbst)."""
        sms = _report_for(_clean_wind_chill_layout()).sms_text
        assert F.sms_token_value(sms, "FD") == str(int(F.FELT_HIKE_MAX_C)), (
            f"AC-3b: FD fehlt oder falsch, obwohl wind_chill_day_high im SMS-Kanal aktiv ist.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "FL") == str(int(F.FELT_HIKE_MIN_C)), (
            f"AC-3b: FL fehlt oder falsch, obwohl wind_chill_day_low im SMS-Kanal aktiv ist.\nSMS: {sms}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-13 — E2E-Kern: Fixture -> Migration -> Loader -> Renderer
# ═══════════════════════════════════════════════════════════════════════════

def test_ac13_fixture_migration_loader_renderer_yields_fd_fl(tmp_path):
    """AC-13 GIVEN eine Trip-JSON mit dem eingefrorenen Muster in
    channel_layouts.sms (wie KHW 403) / WHEN sie migriert UND ueber
    src/app/loader.py geladen UND ueber den Kurzform-Renderer fuer SMS
    verarbeitet wird / THEN enthaelt der erzeugte Kurzform-Text FD und FL,
    wo er sie vor der Migration nicht enthielt.

    RED heute: scripts/migrate_2454_derived_children.py existiert nicht."""
    root = tmp_path / "users"
    briefings_dir = root / "henning" / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    briefing_path = briefings_dir / "b2454.json"
    roh = {
        "id": "b2454", "name": "B2454", "kind": "route", "stages": [],
        "display_config": {
            "metrics": [{"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 0}],
            "channel_layouts": {"sms": _frozen_wind_chill_layout()},
        },
    }
    briefing_path.write_text(json.dumps(roh, ensure_ascii=False), encoding="utf-8")

    vor_migration = _report_for(_frozen_wind_chill_layout()).sms_text
    assert F.sms_token_value(vor_migration, "FD") is None, "Vorbedingung: vor der Migration keine FD."

    result = subprocess.run(
        ["uv", "run", "python3", str(_script_path()), "--root", str(root), "--execute"],
        capture_output=True, text=True, timeout=90, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    migriert = json.loads(briefing_path.read_text(encoding="utf-8"))
    sms_layout_migriert = migriert["display_config"]["channel_layouts"]["sms"]
    nach_migration = _report_for(sms_layout_migriert).sms_text

    assert F.sms_token_value(nach_migration, "FD") == str(int(F.FELT_HIKE_MAX_C)), (
        f"AC-13: FD fehlt nach der Migration -- die Ableitung greift nicht.\nSMS: {nach_migration}"
    )
    assert F.sms_token_value(nach_migration, "FL") == str(int(F.FELT_HIKE_MIN_C)), (
        f"AC-13: FL fehlt nach der Migration.\nSMS: {nach_migration}"
    )


# ---------------------------------------------------------------------------
# Premium-SMS-Transport-Nachweis — lokaler HTTP-Stub statt echtem Versand
# (Vorbild tests/unit/test_premium_sms_versand.py).
# ---------------------------------------------------------------------------

class _SevenIoStub:
    """Nimmt die echten POSTs von PremiumSmsOutput entgegen -- kein Mock."""

    def __init__(self) -> None:
        self.received: list[dict] = []
        received = self.received

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                data = urllib.parse.parse_qs(body.decode())
                received.append({k: v[0] for k, v in data.items()})
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"100")

            def log_message(self, *args):
                pass

        probe = socket.socket()
        probe.bind(("", 0))
        self.port = probe.getsockname()[1]
        probe.close()
        self._server = http.server.HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()


@pytest.fixture()
def stub():
    s = _SevenIoStub()
    yield s
    s.stop()


def _write_premium_profile(user_id: str, *, reply_to: str) -> None:
    path = get_data_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    stamp = datetime.now(timezone.utc) - timedelta(minutes=5)
    profile = {
        "id": user_id, "tier": "premium",
        "premium_sms_reply_to": reply_to,
        "premium_sms_reply_at": stamp.isoformat().replace("+00:00", "Z"),
    }
    (path / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def test_ac13_premium_sms_wire_text_matches_sms_text_and_contains_fd_fl(stub):
    """AC-13 GIVEN derselbe Report (Kinder korrekt befuellt) / WHEN sein
    report.sms_text ueber den Premium-SMS-Kanal gesendet wird (lokaler Stub
    statt echtem seven.io-Versand) / THEN traegt der TATSAECHLICH gesendete
    POST-Body genau diesen Text, inklusive FD/FL (premium_sms.py sendet
    report.sms_text unveraendert -- Spec D5)."""
    user_id = "b2454-premium"
    _write_premium_profile(user_id, reply_to="+4915799912345")
    settings = Settings().with_user_profile(user_id).model_copy(update={
        "sms_gateway_url": f"http://127.0.0.1:{stub.port}/api/sms",
        "seven_api_key": "test-stub-key",
        "seven_sandbox_key": "test-stub-key",
    })

    report = _report_for(_clean_wind_chill_layout())
    assert F.sms_token_value(report.sms_text, "FD") is not None, "Vorbedingung: Report traegt FD."

    PremiumSmsOutput(settings).send(subject="", body=report.sms_text)

    assert stub.received, "AC-13: Premium-SMS hat den lokalen Stub nicht erreicht."
    gesendeter_text = stub.received[-1]["text"]
    assert gesendeter_text == report.sms_text, (
        f"AC-13: der gesendete Premium-SMS-Text weicht von report.sms_text ab.\n"
        f"gesendet: {gesendeter_text!r}\nreport.sms_text: {report.sms_text!r}"
    )
    assert F.sms_token_value(gesendeter_text, "FD") == str(int(F.FELT_HIKE_MAX_C)), (
        f"AC-13: der tatsaechlich versendete Premium-SMS-Text enthaelt kein FD.\nText: {gesendeter_text}"
    )
    assert F.sms_token_value(gesendeter_text, "FL") == str(int(F.FELT_HIKE_MIN_C)), (
        f"AC-13: der tatsaechlich versendete Premium-SMS-Text enthaelt kein FL.\nText: {gesendeter_text}"
    )
