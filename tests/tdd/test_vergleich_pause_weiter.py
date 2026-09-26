"""TDD RED — Issue #2282 Scheibe S1: `pause`/`weiter` am Ortsvergleich.

SPEC: docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md — AC-8, AC-9, AC-10.

Ist-Stand (gemessen): `TripCommandProcessor._find_trip` sucht nur Trips; eine
Nachricht mit einem Vergleichsnamen endet in „Kein Trip mit Name … gefunden",
die Preset-Datei bleibt unberührt. Einen Resume-Schreibpfad für Vergleiche
(Gegenstück zu `save_compare_preset_pause`) gibt es nicht.

Adressiert wird über den Namen (`InboundMessage.trip_name`), wie E-Mail-Betreff
und vorangestellter Name (Spec Abschnitt 4) — und einmal über die vom Reader
vorab aufgelöste Kennung (`resolved_kind`/`resolved_preset_id`, Abschnitt 3).

Mutation 3 (zwei Schreibvorgänge statt einem RMW) wird über einen ZÄHLENDEN
Wrapper um `open`/`io.open` gefangen: gezählt werden Schreib-Öffnungen im
Briefings-Verzeichnis des Nutzers (atomares Schreiben über Temp-Datei +
Umbenennen zählt ebenfalls als genau eine).
"""
from __future__ import annotations

import builtins
import io
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import get_briefings_dir  # noqa: E402
from services.compare_alert_guard import is_silenced  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)


@pytest.fixture
def uid():
    u = f"tdd-2282-pw-{uuid.uuid4().hex[:8]}"
    yield u
    shutil.rmtree(get_briefings_dir(u).parent, ignore_errors=True)


def _preset(user_id: str, name: str = "Alpenblick", **felder) -> dict:
    pid = f"cmp-{uuid.uuid4().hex[:8]}"
    entry = {
        "id": pid,
        "name": name,
        "kind": "vergleich",
        "user_id": user_id,
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "daily",
        "previous_schedule": "",
        "created_at": "2026-09-01T08:00:00Z",
        "empfaenger": ["a@example.com"],
    }
    entry.update(felder)
    d = get_briefings_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def _path(user_id: str, pid: str) -> Path:
    return get_briefings_dir(user_id) / f"{pid}.json"


def _read(user_id: str, pid: str) -> dict:
    return json.loads(_path(user_id, pid).read_text(encoding="utf-8"))


def _send(user_id: str, body: str, name: str = "Alpenblick", channel: str = "telegram", **extra):
    return TripCommandProcessor().process(InboundMessage(
        trip_name=name, body=body, sender="12345", channel=channel,
        received_at=datetime(2026, 9, 16, 8, 0, tzinfo=timezone.utc),
        user_id=user_id, **extra,
    ))


# ---------------------------------------------------------------------------
# AC-8: pause am Vergleich — unbefristet, Dauer ignoriert, kein STOP-Verweis
# ---------------------------------------------------------------------------

class TestAC8Pause:
    def test_pause_ohne_dauer_pausiert_unbefristet(self, uid):
        p = _preset(uid, schedule="weekly")
        res = _send(uid, "pause")
        nachher = _read(uid, p["id"])
        assert nachher["schedule"] == "manual"
        assert nachher["previous_schedule"] == "weekly"
        assert nachher.get("paused_at")
        assert res.success is True
        assert "weiter" in res.confirmation_body.lower()
        assert "STOP" not in res.confirmation_body

    def test_pause_mit_dauer_identisch_zu_ohne_dauer(self, uid):
        """#2417 AC-29 löst die alte, byte-identische Text-Erwartung ab: das
        VERHALTEN (Plattenzustand, unbefristete Pause) bleibt für `pause` und
        `pause 2d` identisch, aber die `2d`-Variante sagt jetzt zusätzlich
        ausdrücklich, dass die Pause unbefristet gilt (bis WEITER) und eine
        angegebene Dauer nicht ausgewertet wird — sonst widerspräche die
        Antwort dem Vergleichs-Hilfe-Angebot, das PAUSE dort ohne Dauer zeigt.
        """
        p1 = _preset(uid, name="Alpenblick", schedule="weekly")
        p2 = _preset(uid, name="Seenblick", schedule="weekly")
        r1 = _send(uid, "pause", name="Alpenblick")
        r2 = _send(uid, "pause 2d", name="Seenblick")
        a, b = _read(uid, p1["id"]), _read(uid, p2["id"])
        for k in ("schedule", "previous_schedule", "kind"):
            assert a[k] == b[k], k
        assert b.get("paused_at") and "paused_until" not in b

        text1 = r1.confirmation_body.replace("Alpenblick", "X")
        text2 = r2.confirmation_body.replace("Seenblick", "X")
        assert text2.startswith(text1), (
            "AC-29: die 2d-Antwort muss die dauer-lose Antwort als Präfix "
            f"tragen und den Hinweis nur ANHÄNGEN: {text1!r} vs. {text2!r}"
        )
        assert "unbefristet" in text2 and "WEITER" in text2
        assert "nicht ausgewertet" in text2, (
            f"AC-29: 'pause 2d' am Vergleich muss ausdrücklich sagen, dass "
            f"die Dauer nicht ausgewertet wurde: {text2!r}"
        )
        assert "nicht ausgewertet" not in text1, (
            f"AC-29: die dauer-lose Antwort darf den Dauer-Hinweis nicht "
            f"tragen (es gab keine Dauer): {text1!r}"
        )

    def test_pause_ueber_vorab_aufgeloeste_kennung(self, uid):
        """Reader hat bereits eindeutig aufgelöst (Spec Abschnitt 3)."""
        p = _preset(uid)
        _send(uid, "pause", resolved_kind="vergleich", resolved_preset_id=p["id"])
        assert _read(uid, p["id"])["schedule"] == "manual"

    def test_pause_erhaelt_unbekannte_felder(self, uid):
        """Read-Modify-Write: Felder, die der Prozessor nicht kennt, bleiben."""
        p = _preset(uid, zukunftsfeld={"x": 1}, empfaenger=["b@example.com"])
        _send(uid, "pause")
        nachher = _read(uid, p["id"])
        assert nachher["schedule"] == "manual", "ohne Schreibvorgang beweist der Erhalt nichts"
        assert nachher["zukunftsfeld"] == {"x": 1}
        assert nachher["empfaenger"] == ["b@example.com"]


# ---------------------------------------------------------------------------
# AC-9: weiter — previous_schedule zurück (leer -> "daily"), paused_at weg,
#        EIN Schreibvorgang
# ---------------------------------------------------------------------------

def _zaehle_schreibzugriffe(monkeypatch, verzeichnis: Path) -> list[str]:
    treffer: list[str] = []
    orig_open, orig_io_open = builtins.open, io.open
    ziel = str(verzeichnis.resolve())

    def _wrap(orig):
        def _open(file, mode="r", *a, **kw):
            if isinstance(file, (str, Path)) and any(c in mode for c in "wax+"):
                if str(Path(file).resolve().parent) == ziel:
                    treffer.append(str(file))
            return orig(file, mode, *a, **kw)
        return _open

    monkeypatch.setattr(builtins, "open", _wrap(orig_open))
    monkeypatch.setattr(io, "open", _wrap(orig_io_open))
    return treffer


class TestAC9Weiter:
    def test_pause_dann_weiter_stellt_zeitplan_wieder_her(self, uid, monkeypatch):
        p = _preset(uid, schedule="weekly")
        _send(uid, "pause")
        pausiert = _read(uid, p["id"])
        assert pausiert["schedule"] == "manual" and pausiert.get("paused_at")

        schreib = _zaehle_schreibzugriffe(monkeypatch, get_briefings_dir(uid))
        res = _send(uid, "weiter")
        monkeypatch.undo()

        nachher = _read(uid, p["id"])
        assert nachher["schedule"] == "weekly"
        assert not nachher.get("paused_at")
        assert is_silenced(nachher) is False
        assert res.success is True
        assert len(schreib) == 1, f"Mutation 3: genau ein Schreibvorgang erwartet, {schreib}"

    def test_leeres_previous_schedule_wird_daily(self, uid):
        """AC-9 / subscriptionHelpers.ts computePauseToggle: Fallback 'daily'."""
        p = _preset(uid, schedule="manual", previous_schedule="",
                    paused_at="2026-09-10T08:00:00Z")
        _send(uid, "weiter")
        nachher = _read(uid, p["id"])
        assert nachher["schedule"] == "daily"
        assert not nachher.get("paused_at")
        assert is_silenced(nachher) is False

    def test_weiter_ueber_web_pause_ohne_paused_at(self, uid):
        """Über die Web-App pausiert: nur schedule=manual + previous_schedule."""
        p = _preset(uid, schedule="manual", previous_schedule="weekly")
        _send(uid, "weiter")
        assert _read(uid, p["id"])["schedule"] == "weekly"

    def test_weiter_schreibt_keine_route_datei_mit_kollidierender_id(self, uid):
        """kind-Guard (F002): eine route-Datei wird nie als Vergleich fortgesetzt."""
        p = _preset(uid, kind="route", schedule="manual", previous_schedule="weekly",
                    paused_at="2026-09-10T08:00:00Z")
        vorher = _path(uid, p["id"]).read_bytes()
        _send(uid, "weiter", resolved_kind="vergleich", resolved_preset_id=p["id"])
        assert _path(uid, p["id"]).read_bytes() == vorher


# ---------------------------------------------------------------------------
# AC-10: weiter an nicht pausiertem Vergleich — Hinweis, Datei unverändert
# ---------------------------------------------------------------------------

def test_ac10_weiter_nicht_pausiert_aendert_nichts(uid):
    p = _preset(uid, schedule="daily")
    vorher = _path(uid, p["id"]).read_bytes()
    res = _send(uid, "weiter")
    assert "nicht pausiert" in res.confirmation_body
    assert _path(uid, p["id"]).read_bytes() == vorher
