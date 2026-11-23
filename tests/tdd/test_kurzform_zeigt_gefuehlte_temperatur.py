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

#3237 (Altpfad entfernt): das eingefrorene Muster lebte in
``channel_layouts.sms``; dieses Altfeld wirkt nicht mehr, Auswahl je Stelle
kommt allein aus der Tabelle "Was steht wo" (abgeleitete Zeilen folgen dort
ihrer Eltern-Metrik). Entfallen sind deshalb die Negativkontrolle
``test_frozen_layout_shows_neither_fd_nor_fl`` und die Kette
``test_ac13_fixture_migration_loader_renderer_yields_fd_fl`` (Vorbedingung
"vor der Migration keine FD" ist nicht mehr herstellbar); das
Migrationsskript selbst bewacht ``test_migrate_eingefrorene_kindmetriken.py``.

Kern-Schicht, deterministisch: kein Netz ausser dem LOKALEN 127.0.0.1-Stub
fuer den Premium-SMS-Transport-Nachweis (dafuer laeuft diese Datei bewusst
NICHT mit --disable-socket, exakt wie ihr Vorbild).
"""
from __future__ import annotations

import http.server
import json
import socket
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
from output.channels.recipient import PremiumSmsRecipient  # noqa: E402
from output.renderers.trip_report import TripReportFormatter  # noqa: E402

from tests.tdd import _min_temp_felt_fixtures as F  # noqa: E402

WIND_CHILL_KIDS = ("wind_chill_night", "wind_chill_day_low", "wind_chill_day_high")


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
    Kanal-eigenen SMS-Auswahl. #3237: die Auswahl steht in der Tabelle
    "Was steht wo" (Stelle ``sms``); ``channel_layouts.sms`` bleibt als
    wirkungslose Beschreibung stehen."""
    from tests.helpers.tabelle_aus_wunsch import trip_wunsch_als_tabelle

    raw = trip_wunsch_als_tabelle({"display_config": {
        "trip_id": "b2454",
        "metrics": [{"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 0}],
        "channel_layouts": {"sms": sms_layout},
    }})["display_config"]
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

    # #1412 S4b: Empfaenger aus der Profil-Fabrik (Rueckadresse aus user.json).
    PremiumSmsOutput(
        settings, recipient=PremiumSmsRecipient.for_user(user_id, settings),
    ).send(subject="", body=report.sms_text)

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
