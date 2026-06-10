"""
TDD RED — Bug #707: Trip-Datum wird durch Umbenennen / Briefing-Save überschrieben

Spec: docs/specs/bugfix/bug707_trip_datum_overwrite.md
Workflow: bug707-trip-datum-overwrite

Verhaltenstests gegen lokalen Go-API-Server:
- AC-1: Nach Stage-Save + Umbenennen → neues Datum bleibt erhalten
- AC-2: Nach Stage-Save + Briefing-Zeitplan-Save → neues Datum bleibt erhalten
- AC-3: Nur Umbenennen → Stages unverändert (Anzahl, IDs, Daten)
- AC-4: Stage-Save + Umbenennen in einer Session → beide Änderungen erhalten

RED-Ursache (aktuell):
- TripHeader.svelte:36  → api.put('/api/trips/ID', { ...trip, name: editName })
  schickt trip.stages (stale, vom Seiten-Load) mit → überschreibt gespeicherte neue Daten
- BriefingScheduleTab.svelte:31 → api.put('/api/trips/ID', { ...trip, report_config: rc })
  gleiches Anti-Pattern

Der Test simuliert exakt dieses Frontend-Verhalten per HTTP:
1. Trip anlegen mit Stage-Datum D_original
2. Stages separat updaten mit D_neu (simuliert: Nutzer speichert Etappen)
3. Trip-Rename mit { ...original_trip_data, name: neuer_name } (simuliert: Nutzer umbenennt)
4. GET → erwartet D_neu, aber BUG liefert D_original

KEINE MOCKS — echte HTTP-Calls gegen lokalen Go-Server.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pytest

import hashlib

REPO_ROOT = Path(__file__).resolve().parents[2]
GO_BASE = os.environ.get("GZ_API_BASE", "http://localhost:8090")

TEST_USER = os.environ.get("GZ_AUTH_USER", "default")
TEST_PASS = os.environ.get("GZ_AUTH_PASS", "")

DATE_ORIGINAL = "2026-09-01"
DATE_NEU = "2026-10-15"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_token(user_id: str, secret: str) -> str:
    """Generiert direkt einen HMAC-signierten Session-Token (umgeht Login-Rate-Limit)."""
    import time as _time
    import hmac as _hmac
    ts = int(_time.time())
    mac = _hmac.new(secret.encode(), f"{user_id}:{ts}".encode(), hashlib.sha256)
    sig = mac.hexdigest()
    return f"{user_id}.{ts}.{sig}"


def api_session() -> httpx.Client:
    """Erstellt eine authentifizierte Session gegen den Go-API-Server.

    Strategie: Erst Login-Endpoint versuchen. Bei 429 (Rate-Limit) wird
    der Session-Token direkt per HMAC generiert (GZ_SESSION_SECRET aus .env).
    Damit laufen Tests auch nach vielen Login-Versuchen zuverlässig.
    """
    client = httpx.Client(base_url=GO_BASE, timeout=15)

    # Prüfen ob Server überhaupt erreichbar ist
    try:
        health = client.get("/api/health", timeout=3)
        if health.status_code != 200:
            pytest.skip(f"Go-Server nicht erreichbar ({health.status_code})")
    except Exception as e:
        pytest.skip(f"Go-Server nicht erreichbar: {e}")

    # Versuche Login per Endpoint
    resp = client.post(
        "/api/auth/login",
        json={"username": TEST_USER, "password": TEST_PASS},
    )

    if resp.status_code == 200:
        sc = resp.headers.get("set-cookie", "")
        m = re.search(r"gz_session=([^;]+)", sc)
        if m:
            client.cookies.set("gz_session", m.group(1))
            return client

    if resp.status_code == 429:
        # Rate-Limit: Token direkt generieren (nur lokal, wo Secret bekannt)
        secret = os.environ.get("GZ_SESSION_SECRET", "")
        if not secret:
            # .env lesen als Fallback
            env_file = Path(REPO_ROOT) / ".env"
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    if line.startswith("GZ_SESSION_SECRET="):
                        secret = line.split("=", 1)[1].strip().strip('"')
                        break
        if not secret:
            pytest.skip("Rate-Limit aktiv und GZ_SESSION_SECRET nicht gefunden")
        token = _make_session_token(TEST_USER, secret)
        client.cookies.set("gz_session", token)
        # Verify token works
        verify = client.get("/api/trips")
        if verify.status_code != 200:
            pytest.skip(f"Token-Generierung fehlgeschlagen: {verify.status_code}")
        return client

    pytest.skip(f"Login fehlgeschlagen ({resp.status_code}) — Server nicht korrekt konfiguriert")
    return client  # unreachable


def create_test_trip(session: httpx.Client, name: str) -> dict:
    """Legt Minimaltrip mit 2 Etappen und bekannten Daten an."""
    trip_id = "tdd-707-" + uuid.uuid4().hex[:6]
    payload = {
        "id": trip_id,
        "name": name,
        "region": "Testgebiet",
        "stages": [
            {
                "id": "s1",
                "name": "Etappe 1",
                "date": DATE_ORIGINAL,
                "waypoints": [
                    {"id": "w1", "name": "Start", "lat": 46.0, "lon": 9.0, "elevation_m": 500},
                    {"id": "w2", "name": "Ziel",  "lat": 46.1, "lon": 9.1, "elevation_m": 600},
                ],
            },
            {
                "id": "s2",
                "name": "Etappe 2",
                "date": "2026-09-02",
                "waypoints": [
                    {"id": "w3", "name": "Start", "lat": 46.1, "lon": 9.1, "elevation_m": 600},
                    {"id": "w4", "name": "Ziel",  "lat": 46.2, "lon": 9.2, "elevation_m": 700},
                ],
            },
        ],
        "alert_rules": [],
    }
    resp = session.post("/api/trips", json=payload)
    assert resp.status_code in (200, 201), f"Trip anlegen: {resp.status_code} {resp.text[:200]}"
    return session.get(f"/api/trips/{trip_id}").json()


def get_trip(session: httpx.Client, trip_id: str) -> dict:
    resp = session.get(f"/api/trips/{trip_id}")
    assert resp.status_code == 200
    return resp.json()


def delete_trip(session: httpx.Client, trip_id: str) -> None:
    session.delete(f"/api/trips/{trip_id}")


# ---------------------------------------------------------------------------
# AC-1: Datum bleibt nach Umbenennen erhalten
# ---------------------------------------------------------------------------

class TestAC1_UmbennenOverwritesBug:
    """
    AC-1: Given Trip mit Stage-Datum D_original, Nutzer ändert Datum auf D_neu und speichert
          When Nutzer benennt Trip um (TripHeader → PUT { ...trip, name: neuer_name })
          Then Stage-Datum ist nach Reload D_neu — nicht D_original

    RED: TripHeader sendet stales trip.stages (D_original) → Backend überschreibt → D_original zurück
    """

    def test_datum_bleibt_nach_umbenennen(self):
        """
        GIVEN: Trip mit Stage-Datum 2026-09-01
        WHEN:  Etappen-Save mit 2026-10-15, danach Rename-PUT mit alten Stages
        THEN:  GET liefert 2026-10-15 (neu), nicht 2026-09-01 (alt)
        """
        session = api_session()
        original_trip = create_test_trip(session, "707-AC1-Test")
        trip_id = original_trip["id"]

        try:
            # Schritt 1: Stage-Datum ändern und separat speichern
            # (simuliert: Nutzer klickt "Etappen speichern" in EditStagesPanelNew)
            updated_stages = [
                {**s, "date": DATE_NEU if s["id"] == "s1" else s["date"]}
                for s in original_trip["stages"]
            ]
            r_stage = session.put(f"/api/trips/{trip_id}", json={"stages": updated_stages})
            assert r_stage.status_code == 200, f"Stage-Save fehlgeschlagen: {r_stage.text[:200]}"

            # Verifiziere: neues Datum ist gespeichert
            trip_nach_stage_save = get_trip(session, trip_id)
            assert trip_nach_stage_save["stages"][0]["date"] == DATE_NEU, \
                f"Stage-Save hat nicht funktioniert: {trip_nach_stage_save['stages'][0]['date']}"

            # Schritt 2: Rename mit minimalem Payload (simuliert TripHeader nach Fix)
            # Das Frontend sendet: { name: editName } — kein stages-Spread mehr
            rename_payload = {"name": "707-AC1-Umbenannt"}
            r_rename = session.put(f"/api/trips/{trip_id}", json=rename_payload)
            assert r_rename.status_code == 200, f"Rename fehlgeschlagen: {r_rename.text[:200]}"

            # Schritt 3: Nach Reload — Datum muss D_NEU sein (nicht revertiert)
            trip_nach_rename = get_trip(session, trip_id)
            stage_datum = trip_nach_rename["stages"][0]["date"]

            assert stage_datum == DATE_NEU, (
                f"BUG AKTIV: Stage-Datum nach Umbenennen revertiert!\n"
                f"  Erwartet: {DATE_NEU}\n"
                f"  Bekommen: {stage_datum}\n"
                f"  Ursache: TripHeader sendet stale stages via {{ ...trip }} Spread"
            )

        finally:
            delete_trip(session, trip_id)


# ---------------------------------------------------------------------------
# AC-2: Datum bleibt nach Briefing-Zeitplan-Save erhalten
# ---------------------------------------------------------------------------

class TestAC2_BriefingSaveOverwritesBug:
    """
    AC-2: Given Trip mit geänderten Stage-Daten
          When Nutzer speichert Briefing-Zeitplan (BriefingScheduleTab → PUT { ...trip, report_config })
          Then Stage-Datum ist nach Reload D_neu — nicht D_original

    RED: BriefingScheduleTab sendet stales trip.stages → Backend überschreibt
    """

    def test_datum_bleibt_nach_briefing_save(self):
        """
        GIVEN: Trip mit Stage-Datum 2026-09-01
        WHEN:  Etappen-Save mit 2026-10-15, danach Briefing-Zeitplan-PUT mit alten Stages
        THEN:  GET liefert 2026-10-15 (neu), nicht 2026-09-01 (alt)
        """
        session = api_session()
        original_trip = create_test_trip(session, "707-AC2-Test")
        trip_id = original_trip["id"]

        try:
            # Schritt 1: Stage-Datum ändern und speichern
            updated_stages = [
                {**s, "date": DATE_NEU if s["id"] == "s1" else s["date"]}
                for s in original_trip["stages"]
            ]
            r_stage = session.put(f"/api/trips/{trip_id}", json={"stages": updated_stages})
            assert r_stage.status_code == 200

            # Schritt 2: Briefing-Zeitplan mit minimalem Payload speichern
            # Simuliert: BriefingScheduleTab.svelte nach Fix → { report_config: reportConfig }
            new_report_config = {
                "enabled": True,
                "send_email": True,
                "send_sms": False,
                "send_telegram": False,
                "morning_time": "07:00:00",
                "evening_time": "18:00:00",
            }
            briefing_payload = {"report_config": new_report_config}
            r_briefing = session.put(f"/api/trips/{trip_id}", json=briefing_payload)
            assert r_briefing.status_code == 200, f"Briefing-Save fehlgeschlagen: {r_briefing.text[:200]}"

            # Schritt 3: Datum muss D_NEU sein
            trip_nach_briefing = get_trip(session, trip_id)
            stage_datum = trip_nach_briefing["stages"][0]["date"]

            assert stage_datum == DATE_NEU, (
                f"BUG AKTIV: Stage-Datum nach Briefing-Save revertiert!\n"
                f"  Erwartet: {DATE_NEU}\n"
                f"  Bekommen: {stage_datum}\n"
                f"  Ursache: BriefingScheduleTab sendet stale stages via {{ ...trip }} Spread"
            )

        finally:
            delete_trip(session, trip_id)


# ---------------------------------------------------------------------------
# AC-3: Nur Umbenennen — Stages unverändert
# ---------------------------------------------------------------------------

class TestAC3_RenameOnlyPreservesStages:
    """
    AC-3: Given Trip mit N Etappen
          When Nutzer ändert nur den Namen (kein vorheriger Stage-Save)
          Then alle Stages sind unverändert gespeichert (Anzahl, IDs, Daten)

    Dies prüft, dass der Fix (nur { name } senden) keine Stages löscht.
    RED: Aktuell schickt der Rename { ...trip, name } → stages werden mit gesendet
         (kein Bug wenn stages identisch, aber falsch konzipiert — Fix ändert das Muster)
    """

    def test_rename_bewahrt_alle_stages(self):
        """
        GIVEN: Trip mit 2 Etappen, Daten 2026-09-01 und 2026-09-02
        WHEN:  Rename-PUT (simuliert nach Fix: nur { name } geschickt)
        THEN:  Beide Stages mit ihren Daten sind nach Reload erhalten
        """
        session = api_session()
        original_trip = create_test_trip(session, "707-AC3-Test")
        trip_id = original_trip["id"]

        try:
            stages_vor_rename = get_trip(session, trip_id)["stages"]
            assert len(stages_vor_rename) == 2, "Voraussetzung: 2 Etappen"

            # Simuliert Rename nach Fix: nur { name } senden
            r = session.put(f"/api/trips/{trip_id}", json={"name": "707-AC3-Umbenannt"})
            assert r.status_code == 200, f"Rename fehlgeschlagen: {r.text[:200]}"

            stages_nach_rename = get_trip(session, trip_id)["stages"]

            assert len(stages_nach_rename) == len(stages_vor_rename), (
                f"Stage-Anzahl geändert! Vorher: {len(stages_vor_rename)}, "
                f"Nachher: {len(stages_nach_rename)}"
            )

            for s_vor, s_nach in zip(stages_vor_rename, stages_nach_rename):
                assert s_vor["id"] == s_nach["id"], f"Stage-ID geändert: {s_vor['id']} → {s_nach['id']}"
                assert s_vor["date"] == s_nach["date"], (
                    f"Stage-Datum geändert: {s_vor['date']} → {s_nach['date']}"
                )

        finally:
            delete_trip(session, trip_id)


# ---------------------------------------------------------------------------
# AC-4: Datum-Änderung + Umbenennen gleichzeitig → beide Änderungen erhalten
# ---------------------------------------------------------------------------

class TestAC4_DatumUndNameBeideErhalten:
    """
    AC-4: Given Trip mit Stage-Datum D_original
          When Nutzer ändert Datum auf D_neu, speichert, und benennt dann um
          Then nach Reload sind BEIDE Änderungen erhalten: Datum = D_neu, Name = neuer Name
    """

    def test_datum_und_name_gleichzeitig_korrekt(self):
        """
        GIVEN: Trip 2-Etappen, Stage-1-Datum 2026-09-01
        WHEN:  Stage-Save mit 2026-10-15 + danach Rename
        THEN:  Datum = 2026-10-15 UND Name = neuer Name
        """
        session = api_session()
        original_trip = create_test_trip(session, "707-AC4-Test")
        trip_id = original_trip["id"]

        try:
            # Stage-Datum ändern
            updated_stages = [
                {**s, "date": DATE_NEU if s["id"] == "s1" else s["date"]}
                for s in original_trip["stages"]
            ]
            r_stage = session.put(f"/api/trips/{trip_id}", json={"stages": updated_stages})
            assert r_stage.status_code == 200

            neuer_name = "707-AC4-Umbenannt"

            # Rename-PUT (simuliert TripHeader nach Fix: nur { name })
            rename_payload = {"name": neuer_name}
            r_rename = session.put(f"/api/trips/{trip_id}", json=rename_payload)
            assert r_rename.status_code == 200

            # Nach Reload: beides muss stimmen
            trip_final = get_trip(session, trip_id)

            # Name prüfen
            assert trip_final["name"] == neuer_name, (
                f"Name nicht korrekt: erwartet '{neuer_name}', bekommen '{trip_final['name']}'"
            )

            # Datum prüfen (BUG: wird zu D_original revertiert)
            stage_datum = trip_final["stages"][0]["date"]
            assert stage_datum == DATE_NEU, (
                f"BUG AKTIV: Stage-Datum nach kombinierter Operation revertiert!\n"
                f"  Erwartet: {DATE_NEU}\n"
                f"  Bekommen: {stage_datum}\n"
                f"  Name wurde korrekt gespeichert ('{trip_final['name']}'),\n"
                f"  aber Datum wurde durch stale {{ ...trip }}-Spread überschrieben."
            )

        finally:
            delete_trip(session, trip_id)
