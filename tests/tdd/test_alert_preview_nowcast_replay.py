"""TDD-RED: Issue #1948 Scheibe S2 — AC-6/AC-7 Zweig-c-Replay
(``nowcast_frames``) am Preview-Endpoint.

SPEC: docs/specs/modules/alarm_testeinspeisung.md

AC-6: Frames mit Regen-Onset im Nowcast-Horizont -> dieselbe
``_derive_result``-Ableitung wie der Live-Radar-Pfad, volles Preview mit
``onset_detected: true``.
AC-7: Frames ohne Onset -> HTTP 200, ``onset_detected: false``, alle
Render-Felder ``null`` -- statt Exception/HTTP 500.

RED-Grund: ``AlertPreviewBody`` kennt heute kein ``nowcast_frames``-Feld
(Pydantic ignoriert es); mit leerem ``changes``/``onset`` liefert der
Endpunkt 422 statt 200.

Wanduhr-Ratsche (#1940): alle Frame-Zeitstempel sind relativ zu einem
``request_now``, der UNMITTELBAR vor dem Request erfasst wird -- keine
festen Uhrzeiten, kein Hour-Tipping.

Kein Mock — echter FastAPI-TestClient, echte Trip-Fixture.
"""
from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

pytestmark = pytest.mark.real_data_root


@pytest.fixture
def client():
    from api.routers import validator
    app = FastAPI()
    app.include_router(validator.router)
    return TestClient(app)


@pytest.fixture
def stub_trip():
    user_id = f"test_1948s2ac6_{uuid.uuid4().hex[:8]}"
    trip_id = "trip-ac6"
    trip_dir = Path("data/users") / user_id / "briefings"
    trip_dir.mkdir(parents=True, exist_ok=True)
    (trip_dir / f"{trip_id}.json").write_text(json.dumps({
        "id": trip_id, "name": "AC-6 Trip", "stages": [],
    }))
    yield user_id, trip_id
    shutil.rmtree(Path("data/users") / user_id, ignore_errors=True)


def _wet_frames(now: datetime) -> list[dict]:
    """Erster nasser Frame nach 20 Minuten, 2.5 mm/h (>= "Maessiger Regen",
    < 4.0 mm/h Schwelle "Starker Regen")."""
    return [
        {"timestamp": (now + timedelta(minutes=5)).isoformat(),
         "precip_mm_h": 0.0, "is_convective": False},
        {"timestamp": (now + timedelta(minutes=20)).isoformat(),
         "precip_mm_h": 2.5, "is_convective": False},
        {"timestamp": (now + timedelta(minutes=40)).isoformat(),
         "precip_mm_h": 3.0, "is_convective": False},
    ]


def _spaeter_onset_frames(now: datetime) -> list[dict]:
    """Issue #2046 / Adversary-Finding F003: SPAETER Beginn (+50 Min), danach
    durchgehend 3.0 mm/h im 15-Minuten-Raster bis +125 Min.

    `_wet_frames` oben kann die beiden Mengenfelder von `_derive_result` gar
    nicht unterscheiden — bei einem Beginn nach 20 Minuten liegen alle nassen
    Frames in BEIDEN Fenstern (`[jetzt, jetzt+60)` und `[Beginn, Beginn+60)`).
    Hier fallen sie um den Faktor 6 auseinander (Herleitung von Hand,
    `_MAX_FRAME_COVERAGE` = 15 Min, Fensterende ausschliessend, Dauer je Frame
    bis zum eigenen naechsten Nachbarn):

      ab jetzt (`window_precip_mm`, `[+0, +60)`):
        +5 (0.0 mm/h) -> 0.00 mm; +50 (3.0 mm/h) bis Fensterende +60 = 10 Min
        -> 0.50 mm. Summe 0.5 mm -> Token waere `R0.5@…`.
      ab dem Beginn (`onset_precip_mm`, `[+50, +110)`):
        +50/+65/+80/+95 je 15 Min x 3.0 mm/h = je 0.75 mm; +110 und +125
        liegen ausserhalb. Summe 3.0 mm -> Token `R3.0@…`.
    """
    frames = [
        {"timestamp": (now + timedelta(minutes=5)).isoformat(),
         "precip_mm_h": 0.0, "is_convective": False},
    ]
    frames += [
        {"timestamp": (now + timedelta(minutes=m)).isoformat(),
         "precip_mm_h": 3.0, "is_convective": False}
        for m in (50, 65, 80, 95, 110, 125)
    ]
    return frames


def _dry_frames(now: datetime) -> list[dict]:
    """Alle Raten unter der Trockenschwelle (0.1 mm/h) -- kein Onset."""
    return [
        {"timestamp": (now + timedelta(minutes=m)).isoformat(),
         "precip_mm_h": 0.0, "is_convective": False}
        for m in (10, 30, 60)
    ]


class TestAC6_OnsetReplayDetectsOnset:
    def test_wet_frames_yield_onset_detected_true_with_derived_minutes(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        request_now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar", "frames": _wet_frames(request_now),
            "km_from": 2.0, "km_to": 6.0,
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        assert data.get("onset_detected") is True, (
            f"AC-6: onset_detected muss True sein: {data!r}"
        )
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert data.get(field), (
                f"AC-6: '{field}' darf bei erkanntem Onset nicht leer sein: {data!r}"
            )

        # FORTGESCHRIEBEN (Issue #1948 S4): die Kurznachricht nennt seit S4
        # den ZEITPUNKT (`R@HH:MM`) statt des Countdowns (`R!<Minuten>`). Die
        # abgeleiteten Minuten bleiben ueber `email_plain`/`telegram` pruefbar,
        # die dieselbe `_derive_result`-Ableitung wie der Live-Pfad tragen.
        # FORTGESCHRIEBEN (Issue #2046, AC-10): der Replay-Weg reicht die aus
        # DENSELBEN Frames abgeleitete Menge bis in die Kurznachricht durch —
        # das Token traegt sie jetzt zwischen Kuerzel und Zeit (`R1.4@17:32`).
        # Der Wert ist deterministisch: Beginn bei +20 Min mit 2.5 mm/h
        # (Deckung 15 Min bis zum naechsten Frame -> 0.625 mm) plus +40 Min mit
        # 3.0 mm/h (letzter Frame, auf _MAX_FRAME_COVERAGE gedeckelt ->
        # 0.75 mm) = 1.375 mm -> "1.4". Bewusst MIT Zahl geprueft statt nur
        # optional: sonst bliebe die Endpunkt-Durchreichung ungewacht.
        assert re.search(r"\bR1\.4@\d{1,2}:\d{2}\b", data["sms"]), (
            f"AC-6/AC-10: SMS muss ein nicht-konvektives Zeitpunkt-Token MIT "
            f"der abgeleiteten Menge tragen ('R1.4@HH:MM'): {data['sms']!r}"
        )
        assert not re.search(r"\b(TH|R)!\d+", data["sms"]), (
            f"AC-6: das Countdown-Format ist abgeloest: {data['sms']!r}"
        )
        match = re.search(r"Regen in (\d+) Min", data["telegram"])
        assert match, (
            f"AC-6: Telegram muss die Countdown-Minuten weiter fuehren: "
            f"{data['telegram']!r}"
        )
        actual_minutes = int(match.group(1))
        assert abs(actual_minutes - 20) <= 1, (
            f"AC-6: onset_minutes muss aus derselben _derive_result-"
            f"Ableitung stammen wie der Live-Radar-Pfad (erster nasser "
            f"Frame bei ~20 Min), bekam {actual_minutes}"
        )
        assert (
            "Mäßiger Regen" in data["email_plain"]
            or "Mäßiger Regen" in data["telegram"]
        ), (
            f"AC-6: Intensitaets-Label 'Mäßiger Regen' (2.5 mm/h) muss "
            f"reflektiert werden.\nplain={data['email_plain']!r}\n"
            f"telegram={data['telegram']!r}"
        )


    def test_spaeter_onset_zeigt_die_menge_ab_beginn_nicht_ab_jetzt(
        self, client, stub_trip,
    ):
        """AC-10 GIVEN einen Frame-Mitschnitt mit SPAETEM Beginn (+50 Min) und
        durchgehendem Regen bis +125 Min
        WHEN der Replay-Weg (`_render_nowcast_replay`) die Vorschau baut
        THEN traegt die Kurznachricht `R3.0@HH:MM` — die Menge der Stunde AB
        DEM BEGINN — und ausdruecklich NICHT `R0.5@HH:MM`, die Menge der
        Stunde ab jetzt.

        Wirkort-Nachweis (Adversary-Finding F003): der Test darueber kann die
        beiden Felder nicht unterscheiden (frueher Beginn -> deckungsgleiche
        Fenster). Wird in `services/validator_render_service.py`
        `onset_precip_mm=result.onset_precip_mm` gegen
        `result.window_precip_mm` vertauscht, wird DIESER Test rot.

        Beide Zahlen aus den Frames hergeleitet (Rechenweg im Docstring von
        `_spaeter_onset_frames`), nicht aus der Implementierung abgeschrieben.
        """
        user_id, trip_id = stub_trip
        request_now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar", "frames": _spaeter_onset_frames(request_now),
            "km_from": 2.0, "km_to": 6.0,
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, f"Body: {resp.text[:300]}"
        data = resp.json()
        assert data.get("onset_detected") is True, (
            f"Voraussetzung: der Beginn bei +50 Min liegt im Nowcast-Horizont "
            f"und muss erkannt werden: {data!r}"
        )
        sms = data["sms"]
        assert re.search(r"\bR3\.0@\d{1,2}:\d{2}\b", sms), (
            "F003: der Replay-Weg muss die Menge AB DEM BEGINN zeigen "
            f"(R3.0@HH:MM = 4 x 3.0 mm/h x 15 Min): {sms!r}"
        )
        assert not re.search(r"\bR0\.5@\d{1,2}:\d{2}\b", sms), (
            "F003: der Replay-Weg zeigt die Menge AB JETZT (R0.5@HH:MM) statt "
            f"der Menge ab dem Beginn: {sms!r}"
        )


class TestAC7_NoOnsetReturns200WithNullFields:
    def test_dry_frames_yield_200_onset_false_and_null_render_fields(
        self, client, stub_trip,
    ):
        user_id, trip_id = stub_trip
        request_now = datetime.now(timezone.utc)
        body = {"nowcast_frames": {
            "source": "radar", "frames": _dry_frames(request_now),
        }}
        resp = client.post(
            f"/api/trips/{trip_id}/alert-preview",
            params={"user_id": user_id}, json=body,
        )
        assert resp.status_code == 200, (
            f"AC-7: trockene Frames muessen 200 liefern, keine Exception "
            f"oder HTTP 500. War {resp.status_code}: {resp.text[:300]}"
        )
        data = resp.json()
        assert data.get("onset_detected") is False, (
            f"AC-7: onset_detected muss False sein: {data!r}"
        )
        for field in ("subject", "email_html", "email_plain", "telegram", "sms"):
            assert data.get(field) is None, (
                f"AC-7: '{field}' muss null sein, wenn kein Onset erkannt "
                f"wurde: {data!r}"
            )
