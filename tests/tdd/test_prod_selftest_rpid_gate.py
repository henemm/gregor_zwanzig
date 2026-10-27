"""TDD RED — prod_selftest bewacht die Passkey-RP-ID aus /api/health.

Spec: docs/specs/modules/passkey_rp_konfiguration.md (AC-4)
Kontext: docs/context/feat-2130-passkey-anmeldung.md

Problem: Produktion sendet dem Browser `rpId: "localhost"`, weil
`GZ_WEBAUTHN_RP_ID` nirgends gesetzt ist und der Default in
internal/config/config.go:45 auf "localhost" steht. Der Ausfall blieb drei
Monate unbemerkt, weil kein Gate den effektiven Wert je gegen den echten
Produktions-Hostnamen gehalten hat.

Fix (noch NICHT implementiert, deshalb RED): `_check_health()` liest das neue
Feld `webauthn_rpid` aus der bereits geholten /api/health-Antwort und vergleicht
es gegen `urlparse(PROD_BASE).hostname`. Abweichung oder fehlendes Feld ->
`(False, msg)` -> Phase 2 des Selbsttests schlaegt fehl.

KEIN Netz: `_http_get` wird per monkeypatch durch einen Recorder ersetzt, der
stur die bei der Konstruktion gesetzte Antwort liefert. Er kennt weder das
Feld `webauthn_rpid` noch den erwarteten Hostnamen und spiegelt damit nicht die
zu testende Logik zurueck.

Der erwartete Hostname wird aus `mod.PROD_BASE` abgeleitet, nicht als Literal
gesetzt — sonst wuerden zwei Literale gegeneinander geprueft statt der
tatsaechlichen Zusicherung.

Das Modul wird bewusst aus der stabilen WORKTREE-Kopie geladen (Muster:
tests/tdd/test_prod_selftest_internal_url_skip.py), nicht aus dem Hauptrepo.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

WORKTREE_DIR = Path(__file__).resolve().parents[2]
HOOKS_DIR = WORKTREE_DIR / ".claude" / "hooks"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"


def _load_prod_selftest_module():
    """Laedt prod_selftest.py als Modul aus der stabilen Worktree-Kopie."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("prod_selftest_2130", PROD_SELFTEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_prod_selftest_module()

# Der erwartete Wert ist der Hostname der Produktions-Basis-URL, die der
# Selbsttest ohnehin schon kennt — kein zweites Literal im Test.
EXPECTED_RPID = urlparse(mod.PROD_BASE).hostname


class _HealthResponder:
    """Ehrlicher Netz-Grenze-Seam: liefert stur den bei der Konstruktion
    gesetzten Status und Rumpf. Kennt weder das Feld `webauthn_rpid` noch den
    erwarteten Hostnamen."""

    def __init__(self, payload: dict, status: int = 200):
        self.payload = payload
        self.status = status
        self.calls: list[str] = []

    def __call__(self, url: str, follow_redirects: bool = False):
        self.calls.append(url)
        return self.status, json.dumps(self.payload).encode("utf-8")


def test_expected_rpid_is_derived_from_prod_base():
    """Vorbedingung dieser Testdatei: PROD_BASE traegt einen echten Hostnamen."""
    assert EXPECTED_RPID, f"PROD_BASE ohne Hostname: {mod.PROD_BASE!r}"


class TestCheckHealthRpidGate:
    """AC-4: _check_health() haelt webauthn_rpid gegen den Prod-Hostnamen."""

    @pytest.mark.parametrize(
        "falsche_rpid",
        [
            "localhost",  # der real ausgelieferte Defekt (#2130)
            "staging.gregor20.henemm.com",  # Staging-Wert versehentlich in Prod
            "",  # leer statt abgeleitet
        ],
    )
    def test_abweichende_rpid_ergibt_false(self, monkeypatch, falsche_rpid):
        responder = _HealthResponder(
            {"status": "ok", "version": "0.1.0", "webauthn_rpid": falsche_rpid}
        )
        monkeypatch.setattr(mod, "_http_get", responder)

        ok, msg = mod._check_health()

        assert ok is False, (
            f"AC-4: webauthn_rpid={falsche_rpid!r} weicht von {EXPECTED_RPID!r} ab — "
            f"_check_health muss False liefern, bekommen {(ok, msg)!r}"
        )
        assert falsche_rpid in msg or "rpid" in msg.lower() or "rp-id" in msg.lower(), (
            f"AC-4: die Meldung muss die Abweichung benennen, bekommen {msg!r}"
        )

    def test_fehlendes_feld_ergibt_false(self, monkeypatch):
        # Vor dem Fix (und bei einem Rueckbau des Health-Felds) fehlt das Feld
        # ganz — das darf NICHT als "in Ordnung" durchgehen, sonst bewacht das
        # Gate genau den Zustand nicht, der drei Monate unbemerkt blieb.
        responder = _HealthResponder({"status": "ok", "version": "0.1.0"})
        monkeypatch.setattr(mod, "_http_get", responder)

        ok, msg = mod._check_health()

        assert ok is False, (
            f"AC-4: fehlendes webauthn_rpid muss False ergeben, bekommen {(ok, msg)!r}"
        )

    def test_korrekte_rpid_ergibt_true(self, monkeypatch):
        responder = _HealthResponder(
            {"status": "ok", "version": "0.1.0", "webauthn_rpid": EXPECTED_RPID}
        )
        monkeypatch.setattr(mod, "_http_get", responder)

        ok, msg = mod._check_health()

        assert ok is True, (
            f"AC-4: korrekte RP-ID {EXPECTED_RPID!r} muss True ergeben, "
            f"bekommen {(ok, msg)!r}"
        )
        assert len(responder.calls) == 1, (
            f"erwartet genau ein _http_get auf /api/health, bekommen {responder.calls}"
        )

    def test_bestehende_pruefungen_bleiben_wirksam(self, monkeypatch):
        # Nicht-Aufweichen: die vorhandene status-Pruefung darf durch die neue
        # RP-ID-Pruefung nicht ersetzt werden.
        responder = _HealthResponder(
            {"status": "degraded", "webauthn_rpid": EXPECTED_RPID}
        )
        monkeypatch.setattr(mod, "_http_get", responder)

        ok, _msg = mod._check_health()
        assert ok is False, "status != ok muss weiterhin False ergeben"
