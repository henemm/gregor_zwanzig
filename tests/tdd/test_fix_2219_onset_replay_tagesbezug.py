"""TDD-RED #2219 (B2-72 = #2085): der Replay-Zweig der Alarm-Vorschau zeigt
den Beginn mit Tagesbezug, wie es der Versand tut.

SPEC: docs/specs/modules/fix_2219_alarm_vorschau_haerten.md AC-8, AC-9.

Teil 1: geteilte Anzeigefassung ``onset_display(now_utc, onset_minutes, tz)
-> (hhmm, offset, weekday)`` neben ``event_end_display`` -- dieselbe Regel
(Versatz entscheidet, Kuerzel nur bei Versatz != 0, Wochentag der Ortszeit).
Teil 2: echter Endpunktaufruf mit ``nowcast_frames`` und gestellter Uhr
kurz vor Mitternacht -- der Beginn nach Mitternacht traegt das Kuerzel wie
das Ende (heute: ``R…@0:23 …@Sa0:38``).

Kein Mock. Echte Renderer, echter TestClient, echte Trip-Fixture ohne
Wegpunkte (``_alert_tz_for_trip`` faellt auf UTC zurueck -- Erwartungen
direkt aus der gestellten Uhr herleitbar).
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from freezegun import freeze_time

pytestmark = pytest.mark.real_data_root

BERLIN = ZoneInfo("Europe/Berlin")


# ───────────────────────── Teil 1: onset_display ─────────────────────────────


class TestAC9OnsetDisplayRegel:
    def test_ortstag_und_utc_tag_fallen_auseinander(self):
        """AC-9 Ortszeit-Fall: jetzt Fr 22:30 UTC = 23:30 Berlin; Beginn in
        45 Min = 23:15 UTC (UTC-Tag noch Freitag) = 00:15 Berlin Samstag.
        Erwartet: Versatz 1 und Kuerzel `Sa` aus der ORTSZEIT."""
        from output.renderers.alert.project import onset_display

        now = datetime(2026, 11, 13, 22, 30, tzinfo=timezone.utc)  # Freitag
        assert onset_display(now, 45, BERLIN) == ("00:15", 1, "Sa")
        # Gegenprobe in UTC: derselbe Zeitpunkt liegt dort am selben Tag.
        assert onset_display(now, 45, ZoneInfo("UTC")) == ("23:15", 0, None)

    def test_selber_tag_ohne_kuerzel(self):
        from output.renderers.alert.project import onset_display

        now = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
        assert onset_display(now, 20, BERLIN) == ("11:20", 0, None)

    @pytest.mark.parametrize("minuten", [5, 45, 90, 600, 1500])
    @pytest.mark.parametrize("now", [
        datetime(2026, 11, 13, 22, 30, tzinfo=timezone.utc),
        datetime(2026, 3, 28, 23, 50, tzinfo=timezone.utc),  # Nacht vor Zeitumstellung
        datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
    ])
    def test_dieselbe_regel_wie_event_end_display(self, now, minuten):
        """AC-9: Beginn und Ende bilden Uhrzeit, Versatz und Kuerzel nach
        DERSELBEN Regel -- fuer dieselbe Minutenzahl stimmen beide Fassungen
        in allen drei Feldern ueberein."""
        from output.renderers.alert.project import event_end_display, onset_display

        ns = SimpleNamespace(event_end_minutes=minuten,
                             event_ongoing_beyond_horizon=False)
        hhmm, offset, _ongoing, weekday = event_end_display(now, ns, BERLIN)
        assert onset_display(now, minuten, BERLIN) == (hhmm, offset, weekday)


# ───────────────────────── Teil 2: Replay-Endpunkt ───────────────────────────


@pytest.fixture
def client():
    from api.routers import validator

    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    user_id = f"test_2219_replay_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-2219-replay"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "Replay-Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _frames(now: datetime, nass_ab: int, nass_bis: int) -> list[dict]:
    """Trockenframe bei +5, nasse Frames 0.8 mm/h im 5-Minuten-Raster von
    `nass_ab` bis `nass_bis`, danach trocken -- Beginn = `nass_ab`."""
    frames = [{"timestamp": (now + timedelta(minutes=5)).isoformat(),
               "precip_mm_h": 0.0, "is_convective": False}]
    frames += [{"timestamp": (now + timedelta(minutes=m)).isoformat(),
                "precip_mm_h": 3.0, "is_convective": False}
               for m in range(nass_ab, nass_bis + 1, 5)]
    frames.append({"timestamp": (now + timedelta(minutes=nass_bis + 5)).isoformat(),
                   "precip_mm_h": 0.0, "is_convective": False})
    return frames


def _replay(client, stub_trip, uhr: str, nass_ab: int, nass_bis: int) -> dict:
    user_id, trip_id = stub_trip
    with freeze_time(uhr):
        now = datetime.now(timezone.utc)
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview", params={"user_id": user_id},
            json={"nowcast_frames": {"source": "radar", "km_from": 0.0, "km_to": 4.0,
                                     "frames": _frames(now, nass_ab, nass_bis)}},
        )
    assert resp.status_code == 200, resp.text[:300]
    data = resp.json()
    assert data.get("onset_detected") is True, data
    return data


class TestAC8BeginnNachMitternachtTraegtKuerzel:
    def test_beginn_und_ende_nach_mitternacht_beide_mit_kuerzel(self, client, stub_trip):
        """AC-8 (Beispiel #2085): Fr 23:50 UTC, Beginn +33 Min = Sa 00:23,
        Ende nach Mitternacht. Heute: `R…@0:23` am Beginn, `@Sa…` am Ende.
        Erwartet: `@Sa0:23` am Beginn."""
        data = _replay(client, stub_trip, "2026-11-13 23:50:00+00:00", 33, 45)
        sms = data["sms"]
        assert re.search(r"\bR[\d.]*@Sa0:23", sms), (
            f"AC-8: der Beginn nach Mitternacht muss das Kuerzel tragen: {sms!r}"
        )
        assert not re.search(r"@0:23", sms), f"AC-8: nackter Beginn: {sms!r}"
        assert re.search(r"@Sa0:23@Sa0:\d{2}", sms), (
            f"AC-8: das Ende (+45..+50 Min = Sa 0:3x) traegt weiterhin sein Kuerzel: {sms!r}"
        )

    def test_langform_nennt_den_tagesbezug_als_wort(self, client, stub_trip):
        """AC-8: E-Mail/Telegram fuehren denselben Tagesbezug als Wort."""
        data = _replay(client, stub_trip, "2026-11-13 23:50:00+00:00", 33, 45)
        for feld in ("telegram", "email_plain"):
            text = data[feld]
            assert re.search(r"morgen 00:23", text), (
                f"AC-8: {feld} muss den Beginn mit Tageswort zeigen: {text!r}"
            )


class TestAC9SelberTagUnveraendert:
    def test_beginn_am_selben_tag_ohne_kuerzel(self, client, stub_trip):
        """AC-9/AC-11: 12:00 UTC, Beginn +20 Min -> `@12:20` ohne Kuerzel."""
        data = _replay(client, stub_trip, "2026-11-13 12:00:00+00:00", 20, 40)
        sms = data["sms"]
        assert re.search(r"\bR[\d.]*@12:20", sms), sms
        assert not re.search(r"@(Mo|Di|Mi|Do|Fr|Sa|So)\d", sms), sms
