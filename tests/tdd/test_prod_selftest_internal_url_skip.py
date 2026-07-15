"""TDD RED — prod_selftest überspringt interne/auth-geschützte Sende-URLs statt FAIL.

Spec: docs/specs/modules/fix_1197_prod_selftest_internal_url_skip.md (AC-1..AC-6)
Kontext: docs/artifacts/fix-1197-prod-selftest-internal-urls/context.md

Problem: Findings mit einer Roh-URL, die per Konstruktion nicht öffentlich per
GET probebar ist (interner Host localhost/127.0.0.1/::1, interne Ports
8000/8001/8090, oder auth-geschützter /api/scheduler/.../send-Endpoint), werden
trotzdem geprobt → 401/405 → prod_status FAIL → Verdict PARTIAL → Exit 1 →
blockiert Issue-Close fälschlich, obwohl die Produktion gesund ist.

Fix (noch NICHT implementiert, deshalb RED): neue reine Klassifikationsfunktion
`_is_internal_or_send_url(raw_url)` und neuer Skip-Status
`SKIPPED_NOT_MAPPABLE`, ausgewertet in `_probe_ac` VOR `_staging_to_prod_url`.

KEIN Netz: die Tests öffnen NIE eine echte HTTP-Verbindung. Als ehrlicher
Boundary-Seam wird `_http_get` per monkeypatch durch einen Recorder ersetzt —
NUR um (a) zu beweisen, dass Skip-Fälle KEIN `_http_get` auslösen, und (b) für
AC-5 einen kontrollierten 401 an der Netz-Grenze zu liefern. Der Recorder
spiegelt NICHT die zu testende Logik zurück.

Das Modul wird bewusst aus der stabilen WORKTREE-Kopie geladen (Muster:
tests/tdd/test_bundle_h_908_973_987_staging_auth.py), nicht aus dem Hauptrepo.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

WORKTREE_DIR = Path(__file__).resolve().parents[2]
HOOKS_DIR = WORKTREE_DIR / ".claude" / "hooks"
PROD_SELFTEST = HOOKS_DIR / "prod_selftest.py"


def _load_prod_selftest_module():
    """Lädt prod_selftest.py als Modul aus der stabilen Worktree-Kopie."""
    if str(HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("prod_selftest_1197", PROD_SELFTEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load_prod_selftest_module()


class _HttpGetRecorder:
    """Ehrlicher Netz-Grenze-Seam: zählt Aufrufe und liefert einen kontrollierten
    Status zurück. Spiegelt NICHT die getestete Logik — er kennt weder URL-Klassen
    noch Skip-Status, sondern gibt stur den bei der Konstruktion gesetzten Status."""

    def __init__(self, status: int = 200):
        self.status = status
        self.calls: list[str] = []

    def __call__(self, url: str, follow_redirects: bool = False):
        self.calls.append(url)
        return self.status, b""


# ---------------------------------------------------------------------------
# Reine Klassifikation: _is_internal_or_send_url (existiert noch NICHT → RED)
# ---------------------------------------------------------------------------

class TestIsInternalOrSendUrlClassifier:
    """Reine Klassifikationsfunktion — kein Netz, kein Seam."""

    @pytest.mark.parametrize(
        "raw_url",
        [
            "http://localhost:8080/api/x:AC-1",   # AC-1: localhost, beliebiger Port
            "http://127.0.0.1:9000/api/x",        # AC-1: 127.0.0.1
            "http://[::1]:8080/api/x",            # AC-1: IPv6-Loopback
        ],
    )
    def test_ac1_loopback_host_is_internal(self, raw_url):
        assert mod._is_internal_or_send_url(raw_url) is True, (
            f"Loopback-Host sollte als intern klassifiziert werden: {raw_url}"
        )

    @pytest.mark.parametrize(
        "raw_url",
        [
            "https://gregor20.henemm.com:8001/api/scheduler/trips/t/send",  # 8001
            "https://gregor20.henemm.com:8000/api/x",                        # 8000
            "https://gregor20.henemm.com:8090/api/scheduler/status",         # 8090
        ],
    )
    def test_ac2_internal_port_on_public_host_is_internal(self, raw_url):
        assert mod._is_internal_or_send_url(raw_url) is True, (
            f"Interner Port (8000/8001/8090) sollte als intern gelten: {raw_url}"
        )

    @pytest.mark.parametrize(
        "raw_url",
        [
            "https://gregor20.henemm.com/api/scheduler/trips/t/send",
            "https://staging.gregor20.henemm.com/api/scheduler/compare-presets/p/send:AC-3",
        ],
    )
    def test_ac3_send_path_is_internal_regardless_of_host(self, raw_url):
        assert mod._is_internal_or_send_url(raw_url) is True, (
            f"/api/scheduler/<x>/send-Pfad sollte übersprungen werden: {raw_url}"
        )

    def test_ac6_ac_suffix_does_not_break_detection(self):
        # Derselbe :AC-N-Suffix an einer internen URL: muss vor Host-/Pfad-Prüfung
        # via _strip_ac_suffix entfernt werden, sonst greift die Erkennung nicht.
        assert mod._is_internal_or_send_url("http://localhost:8080/api/x:AC-1") is True
        assert (
            mod._is_internal_or_send_url(
                "https://staging.gregor20.henemm.com/api/scheduler/x/send:AC-6"
            )
            is True
        )

    @pytest.mark.parametrize(
        "raw_url",
        [
            "https://gregor20.henemm.com/api/health:AC-1",
            "https://gregor20.henemm.com/api/scheduler/status",
            "https://staging.gregor20.henemm.com/:AC-1",
        ],
    )
    def test_negative_normal_public_url_is_not_internal(self, raw_url):
        # Nicht-Aufweichen: normale öffentliche URLs ohne internen Host/Port und
        # ohne /send-Pfad dürfen NICHT übersprungen werden.
        assert mod._is_internal_or_send_url(raw_url) is False, (
            f"Normale öffentliche URL fälschlich als intern klassifiziert: {raw_url}"
        )


# ---------------------------------------------------------------------------
# _probe_ac: Skip-Status SKIPPED_NOT_MAPPABLE ohne HTTP-GET (existiert noch NICHT)
# ---------------------------------------------------------------------------

class TestProbeAcSkipsInternalWithoutHttp:
    """_probe_ac muss interne/send-Findings ohne HTTP-GET überspringen."""

    @pytest.mark.parametrize(
        ("ac", "url"),
        [
            ("AC-1", "http://localhost:8080/api/x:AC-1"),
            ("AC-1", "http://127.0.0.1:9000/api/x:AC-1"),
            ("AC-2", "https://gregor20.henemm.com:8001/api/scheduler/trips/t/send:AC-2"),
            ("AC-3", "https://staging.gregor20.henemm.com/api/scheduler/compare-presets/p/send:AC-3"),
        ],
    )
    def test_internal_or_send_finding_skipped_and_no_http_get(
        self, monkeypatch, ac, url
    ):
        recorder = _HttpGetRecorder(status=200)
        monkeypatch.setattr(mod, "_http_get", recorder)

        finding = {"ac": ac, "status": "PASS", "url": url, "evidence": "x"}
        result = mod._probe_ac(finding)

        assert result["prod_status"] == "SKIPPED_NOT_MAPPABLE", (
            f"Erwartet prod_status SKIPPED_NOT_MAPPABLE für {url}, "
            f"aber {result.get('prod_status')!r}"
        )
        assert recorder.calls == [], (
            f"_http_get wurde für eine interne/send-URL aufgerufen (verboten): "
            f"{recorder.calls}"
        )

    def test_ac5_normal_public_401_stays_fail_and_http_get_called(self, monkeypatch):
        # Nicht-Aufweichen: eine normale öffentliche URL wird NICHT übersprungen —
        # der echte 401 an der Netz-Grenze muss weiterhin FAIL erzeugen.
        recorder = _HttpGetRecorder(status=401)
        monkeypatch.setattr(mod, "_http_get", recorder)

        finding = {
            "ac": "AC-1",
            "status": "PASS",
            "url": "https://gregor20.henemm.com/api/health:AC-1",
            "evidence": "Health erreichbar auf Staging",
        }
        result = mod._probe_ac(finding)

        assert result["prod_status"] == "FAIL", (
            f"Normale öffentliche URL mit 401 muss FAIL bleiben, "
            f"aber {result.get('prod_status')!r}"
        )
        assert len(recorder.calls) == 1, (
            f"Normale öffentliche URL muss geprobt werden (genau 1 _http_get), "
            f"aber calls={recorder.calls}"
        )


# ---------------------------------------------------------------------------
# _derive_verdict: deterministisch, ohne Seam
# ---------------------------------------------------------------------------

class TestDeriveVerdictWithSkip:
    def test_ac4_all_skipped_not_mappable_is_not_partial(self):
        # AC-4: jedes PASS-Finding ist übersprungen (SKIPPED_NOT_MAPPABLE) →
        # Verdict darf NICHT PARTIAL sein (erwartet PASS).
        probes = [
            {"status": "PASS", "prod_status": "SKIPPED_NOT_MAPPABLE", "ac": "AC-1"},
            {"status": "PASS", "prod_status": "SKIPPED_NOT_MAPPABLE", "ac": "AC-2"},
        ]
        verdict = mod._derive_verdict(probes)
        assert verdict != "PARTIAL", (
            f"Alle-übersprungen-Liste ergab fälschlich PARTIAL: {verdict}"
        )
        assert verdict == "PASS", f"Erwartet PASS, aber {verdict}"

    def test_ac5_real_fail_still_partial_regression_guard(self):
        # Regressions-Guard: ein echtes PASS-mit-FAIL bleibt PARTIAL.
        probes = [{"status": "PASS", "prod_status": "FAIL", "ac": "AC-x"}]
        assert mod._derive_verdict(probes) == "PARTIAL"
