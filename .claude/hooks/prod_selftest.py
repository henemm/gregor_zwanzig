#!/usr/bin/env python3
"""
Post-Deploy-Selbsttest (Issue #564).

Läuft nach `deploy-gregor-prod.sh` und attestiert gegen Produktion:
  Phase 1 — Commit-Attestation: git HEAD == e2e_verified.json["verified_commit"]
  Phase 2 — Health-Check: https://gregor20.henemm.com/api/health → HTTP 200 + status=ok
  Phase 3 — AC-Attestation: pro Finding HTTP-Probe auf Prod-URL (parallel, max 5)

Verdict-Ableitung:
  FAIL         — Commit-Mismatch ODER Health unreachable
  PARTIAL      — mind. ein PASS-Finding lieferte prod_status=FAIL
  PASS         — alle PASS-Findings → prod_status=PASS
  SKIPPED_ALL  — alle Findings status=SKIPPED

Exit-Codes:
  0 — PASS / SKIPPED_ALL / e2e_verified.json fehlt (docs-only)
  1 — FAIL / PARTIAL

CLI:
  python3 prod_selftest.py [--e2e-path PATH] [--workflow NAME]
"""

import argparse
import ast
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import importlib.util as _importlib_util

_e2e_paths_spec = _importlib_util.spec_from_file_location(
    "_e2e_paths_prod_selftest",
    str(Path(__file__).resolve().parent / "_e2e_paths.py"),
)
_e2e_paths = _importlib_util.module_from_spec(_e2e_paths_spec)
_e2e_paths_spec.loader.exec_module(_e2e_paths)

REPO_DIR = Path("/home/hem/gregor_zwanzig")
CANONICAL_E2E_PATH = REPO_DIR / ".claude" / "e2e_verified.json"
PROD_BASE = "https://gregor20.henemm.com"
HEALTH_URL = f"{PROD_BASE}/api/health"
PROBE_TIMEOUT = 8
MAX_WORKERS = 5

# Sentinel-URL-Werte (case-insensitive, getrimmt) für Findings ohne echte Prod-URL
# (Backend-/Mail-/interaktive ACs). Werden wie leere URL behandelt → kein HTTP-GET,
# kein False-FAIL/PARTIAL (Issue #788).
_URL_SENTINELS = {"n/a", "na", "-", "none", "—", "interaktiv", ""}

# Mail-Preview-Findings für synthetische Test-Trips (#908/#973/#987): Die Trip-ID
# existiert nie in Produktion (nur auf Staging für den Test angelegt) — eine
# Prod-Attestation würde zwangsläufig FAIL/PARTIAL erzeugen, obwohl das reale
# Feature funktioniert. Erkennung: Pfad exakt /api/preview/<trip_id>/email und
# <trip_id> endet auf ein bekanntes Test-Trip-Suffix (z.B. 'e2e-908-test').
_PREVIEW_EMAIL_PATH = re.compile(r"^/api/preview/[^/]+/email$")
_TEST_TRIP_SUFFIX = ("-test", "-tdd", "-adv-test")  # bekannte Staging-Test-Trip-Marker

# Interne/auth-geschützte URL-Klassen (#1197): Findings, deren Roh-URL per
# Konstruktion nicht öffentlich per GET probebar ist — interner Loopback-Host,
# interne Ports (8000 Python-API / 8001 Scheduler / 8090 gregor-api) oder der
# auth-geschützte /send-Endpoint (echter Prod-Mailversand, darf öffentlich nie
# getriggert werden). Werden übersprungen (SKIPPED_NOT_MAPPABLE) statt False-FAIL.
_INTERNAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_INTERNAL_PORTS = {8000, 8001, 8090}
_SCHEDULER_SEND_PATH = re.compile(r"^/api/scheduler/.+/send$")


def _is_internal_or_send_url(raw_url: str) -> bool:
    """True wenn `raw_url` per Konstruktion nicht öffentlich per GET probebar ist
    (#1197): interner Loopback-Host, interner Port (8000/8001/8090) oder der
    auth-geschützte /api/scheduler/<x>/send-Pfad (host-unabhängig). Solche URLs
    werden in `_probe_ac` übersprungen statt False-FAIL/PARTIAL auszulösen."""
    try:
        parsed = urlparse(_strip_ac_suffix(raw_url))
        host = (parsed.hostname or "").lower()  # IPv6 → '::1' ohne Klammern
        if host in _INTERNAL_HOSTS:
            return True
        if parsed.port in _INTERNAL_PORTS:
            return True
        if _SCHEDULER_SEND_PATH.match(parsed.path or ""):
            return True
    except ValueError:
        # Parse-Fehler (z.B. ungültiger Port) → konservativ nicht überspringen
        return False
    return False


def _is_staging_test_trip_preview(raw_url: str) -> bool:
    """True wenn `raw_url` ein Mail-Preview-Finding für einen synthetischen
    Test-Trip ist (Pfad exakt /api/preview/{trip}/email, Trip-ID endet auf ein
    bekanntes Test-Trip-Suffix). Solche Trips existieren nur auf Staging — die
    Prod-Attestation wird für sie übersprungen statt False-FAIL/PARTIAL
    auszulösen."""
    parsed = urlparse(_strip_ac_suffix(raw_url))
    if not _PREVIEW_EMAIL_PATH.match(parsed.path or ""):
        return False
    trip_id = parsed.path.split("/")[3]  # /api/preview/{trip}/email
    return trip_id.endswith(_TEST_TRIP_SUFFIX)


def _log(msg: str, stream=sys.stdout) -> None:
    print(f"[prod-selftest] {msg}", file=stream)


def _head_sha() -> str:
    return _e2e_paths.head_sha(REPO_DIR)


def _commit_e2e_path(sha: str | None = None) -> Path:
    """Commit-getaggter Attestation-Pfad: .claude/e2e_verified/<sha>.json"""
    return _e2e_paths.commit_e2e_path(REPO_DIR, sha or _head_sha())


def _default_e2e_path() -> Path:
    """Default-Pfad-Auflösung: commit-getaggt (Vorrang), sonst Singleton-Fallback.

    Existiert die commit-getaggte Datei für HEAD → diese. Sonst, wenn das alte
    Singleton existiert → Fallback (Migration). Sonst die (nicht existente)
    getaggte Datei → wird von run_selftest als 'fehlt' behandelt.
    """
    return _e2e_paths.default_e2e_path(REPO_DIR, CANONICAL_E2E_PATH, _head_sha())


def _strip_ac_suffix(url: str) -> str:
    """Entfernt ':AC-N' aus URL — staging-URLs nutzen das als Marker."""
    idx = url.rfind(":AC-")
    return url[:idx] if idx > 0 else url


def _staging_to_prod_url(staging_url: str) -> str:
    """Baut Prod-URL aus Staging-URL: Pfad extrahieren, neu zusammensetzen."""
    clean = _strip_ac_suffix(staging_url)
    parsed = urlparse(clean)
    path = parsed.path or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{PROD_BASE}{path}{query}"


def _http_get(url: str, follow_redirects: bool = False) -> tuple[int, bytes, str]:
    """HTTP-GET via stdlib. Returns (status_code, body, location).

    location: Redirect-Ziel bei 3xx (leer bei 2xx / kein Location-Header).
    follow_redirects=False: HTTPError(3xx) wird abgefangen → status_code aus dem Fehler.
    Raises urllib.error.URLError bei DNS/Connect-Fehlern (vom Caller behandelt).
    """
    req = urllib.request.Request(url, method="GET")
    if not follow_redirects:
        # NoRedirectHandler: 3xx werfen HTTPError statt zu folgen
        opener = urllib.request.build_opener(_NoRedirectHandler())
    else:
        opener = urllib.request.build_opener()
    try:
        with opener.open(req, timeout=PROBE_TIMEOUT) as resp:
            return resp.status, resp.read(), ""
    except urllib.error.HTTPError as exc:
        # 3xx und 4xx/5xx landen hier — body lesen, Status zurückgeben
        try:
            body = exc.read()
        except Exception:
            body = b""
        location = exc.headers.get("Location", "") or "" if exc.headers else ""
        return exc.code, body, location


def _normalize_http_get_result(result: tuple) -> tuple[int, bytes, str]:
    """Normalisiert `_http_get`-Rückgaben auf ein Drei-Tupel (Spec Punkt 5):
    bestehende Tests monkeypatchen `_http_get` weiterhin mit einem Zwei-Tupel
    `(status, body)` — dieser Helper macht Aufrufstellen kompatibel zu beiden
    Formen, ohne die bestehenden Testdateien zu ändern."""
    if len(result) == 2:
        status, body = result
        return status, body, ""
    status, body, location = result
    return status, body, location


def _is_login_redirect(location: str) -> bool:
    """True wenn `location` auf die Anmeldeseite zeigt (Pfad exakt '/login'
    oder beginnt mit '/login') — robust gegen absolute/relative URL und
    Query-String (via urlparse den Pfad extrahieren)."""
    if not location:
        return False
    path = urlparse(location).path
    return path == "/login" or path.startswith("/login")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Blockt Redirects, lässt HTTPError mit 3xx-Code durchschlagen."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# Mirror von http.client: Steuerzeichen 0x00-0x20 (inkl. Space) und 0x7f (DEL)
_DISALLOWED_URL_CHARS = re.compile(r"[\x00-\x20\x7f]")


def _is_probeable_url(url: str) -> bool:
    """True nur wenn die URL gefahrlos per HTTP-GET probebar ist.

    Findings tragen teils Freitext (z.B. '/api/trips/{id} PUT/GET') statt echter
    Pfade — urllib würde dann InvalidURL werfen. Solche URLs sind nicht probebar.
    """
    if not url or _DISALLOWED_URL_CHARS.search(url):
        return False
    parsed = urlparse(url)
    return bool(
        parsed.scheme in ("http", "https")
        and parsed.netloc
        and parsed.path.startswith("/")
    )


def _probe_ac(finding: dict) -> dict:
    """HTTP-Probe für ein Finding. SKIPPED → ATTESTED_SKIPPED ohne Netzwerk."""
    if finding.get("status") == "SKIPPED":
        return {
            **finding,
            "prod_url": "—",
            "prod_http": "—",
            "prod_status": "ATTESTED_SKIPPED",
        }

    raw_url = finding.get("url") or ""  # JSON null → "" (F001: kein None.strip()-Crash)
    # Sentinel-URLs (n/a, -, interaktiv, leer …) → kein HTTP-GET, kein False-FAIL
    # (Issue #788). Robust gegen jede Notation: getrimmt + case-insensitive.
    if raw_url.strip().lower() in _URL_SENTINELS:
        return {
            **finding,
            "prod_url": "",
            "prod_http": "—",
            "prod_status": "SKIPPED_NO_URL",
        }

    # Mail-Preview-Test-Trip (#908/#973/#987): Trip existiert nie in Prod →
    # überspringen statt False-FAIL/PARTIAL.
    if _is_staging_test_trip_preview(raw_url):
        return {
            **finding,
            "prod_url": "",
            "prod_http": "—",
            "prod_status": "SKIPPED_PREVIEW_TEST_TRIP",
        }

    # Interner Host/Port oder auth-geschützter /send-Endpoint (#1197): nicht
    # öffentlich per GET probebar → überspringen statt False-FAIL/PARTIAL.
    if _is_internal_or_send_url(raw_url):
        return {
            **finding,
            "prod_url": "",
            "prod_http": "—",
            "prod_status": "SKIPPED_NOT_MAPPABLE",
        }

    # Freitext-Erkennung (#1327/#1228 Fix 1): raw_url ohne führendes 'http(s)://'
    # oder '/' ist kein echter Pfad — _staging_to_prod_url würde per
    # Konkatenation einen syntaktisch validen, aber falschen Fantasie-Host
    # bauen (z.B. 'https://gregor20.henemm.comcompareMetricDefs.ts/...'), der
    # _is_probeable_url passiert und erst per DNS-Fehler in FAIL läuft. Der
    # Kurzschluss greift VOR jeder Pfad-Konkatenation, kein _http_get-Versuch.
    trimmed = _strip_ac_suffix(raw_url).strip()
    if not (
        trimmed.startswith("/")
        or trimmed.startswith("http://")
        or trimmed.startswith("https://")
    ):
        return {
            **finding,
            "prod_url": "",
            "prod_http": "—",
            "prod_status": "SKIPPED_NO_URL",
        }

    prod_url = _staging_to_prod_url(raw_url)

    # Validitäts-Gate: nicht-probebare URLs (Freitext, Leerzeichen, Steuerzeichen)
    # werden übersprungen statt urllib.InvalidURL zu werfen (Bug #730).
    if not _is_probeable_url(prod_url):
        return {
            **finding,
            "prod_url": prod_url,
            "prod_http": "—",
            "prod_status": "SKIPPED_NO_URL",
        }

    try:
        status, _body, location = _normalize_http_get_result(
            _http_get(prod_url, follow_redirects=False)
        )
        # Method-Not-Probeable (#1327/#1228 Fix 2): POST-only-Endpoints
        # antworten auf GET korrekt mit 405 — das ist kein FAIL des Features,
        # sondern eine strukturell nicht per GET probebare Route.
        if status == 405:
            return {
                **finding,
                "prod_url": prod_url,
                "prod_http": status,
                "prod_status": "SKIPPED_METHOD_NOT_PROBEABLE",
            }
        if status in (301, 302, 303, 307, 308):
            if _is_login_redirect(location):
                prod_status = "SKIPPED_AUTH_REDIRECT"
            else:
                prod_status = "PASS"
        elif status == 200:
            prod_status = "PASS"
        else:
            prod_status = "FAIL"
        return {
            **finding,
            "prod_url": prod_url,
            "prod_http": status,
            "prod_status": prod_status,
        }
    except (urllib.error.URLError, OSError, http.client.InvalidURL, ValueError) as exc:
        return {
            **finding,
            "prod_url": prod_url,
            "prod_http": "ERR",
            "prod_status": "FAIL",
            "error": str(exc),
        }


def _check_health() -> tuple[bool, str]:
    """Prüft /api/health. Returns (ok, message)."""
    try:
        status, body, _location = _normalize_http_get_result(
            _http_get(HEALTH_URL, follow_redirects=True)
        )
        if status != 200:
            return False, f"HTTP {status}"
        try:
            payload = json.loads(body.decode("utf-8", errors="replace"))
        except (ValueError, json.JSONDecodeError):
            return False, "JSON-Decode-Fehler"
        if payload.get("status") != "ok":
            return False, f"status={payload.get('status')!r}"
        return True, "HTTP 200, status=ok"
    except (urllib.error.URLError, OSError) as exc:
        return False, f"unreachable ({exc})"


def _write_report(report_path: Path, content: str) -> None:
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(content)
    except OSError as exc:
        _log(f"WARN: Bericht konnte nicht geschrieben werden: {exc}", stream=sys.stderr)


def _render_fail_commit_mismatch(
    workflow: str, head: str, verified_commit: str
) -> str:
    return (
        f"# Prod-Selftest — {workflow}\n\n"
        f"**Datum:** {datetime.now(timezone.utc).isoformat()}\n"
        f"**Commit (HEAD):** {head[:8]}\n"
        f"**Commit (verifiziert):** {verified_commit[:8]}\n"
        f"**Verdict: FAIL**\n\n"
        f"## Fazit\n\n"
        f"Commit-Mismatch: HEAD ({head[:8]}) stimmt nicht mit "
        f"verified_commit ({verified_commit[:8]}) überein. "
        f"Veraltete Staging-Verifikation — /e2e-verify erneut ausführen.\n"
    )


def _render_fail_health(workflow: str, head: str, health_msg: str) -> str:
    return (
        f"# Prod-Selftest — {workflow}\n\n"
        f"**Datum:** {datetime.now(timezone.utc).isoformat()}\n"
        f"**Commit:** {head[:8]}\n"
        f"**Health:** FAIL ({health_msg})\n"
        f"**Verdict: FAIL**\n\n"
        f"## Fazit\n\n"
        f"Produktion-Health-Check fehlgeschlagen: {health_msg}. "
        f"Infrastruktur prüfen, Rollback erwägen.\n"
    )


def _render_full_report(
    workflow: str, head: str, health_msg: str, verdict: str, probes: list[dict]
) -> str:
    lines = [
        f"# Prod-Selftest — {workflow}",
        "",
        f"**Datum:** {datetime.now(timezone.utc).isoformat()}",
        f"**Commit:** {head[:8]}",
        f"**Health:** OK ({health_msg})",
        f"**Verdict: {verdict}**",
        "",
        "## AC-Ergebnisse",
        "",
        "| AC | Staging-Status | Prod-URL | Prod-HTTP | Prod-Status |",
        "|----|---------------|----------|-----------|-------------|",
    ]
    for p in probes:
        ac = p.get("ac", "?")
        staging = p.get("status", "?")
        prod_url = p.get("prod_url", "—")
        prod_http = p.get("prod_http", "—")
        prod_status = p.get("prod_status", "?")
        lines.append(
            f"| {ac} | {staging} | {prod_url} | {prod_http} | {prod_status} |"
        )

    lines += ["", "## Fazit", ""]
    if verdict == "PASS":
        lines.append(
            "Alle verifizierten ACs in Produktion erreichbar. "
            "Issue-Close freigegeben."
        )
    elif verdict == "SKIPPED_ALL":
        lines.append(
            "Alle Findings sind SKIPPED (Backend-/E-Mail-ACs ohne HTTP-Nachweis). "
            "Kein PASS-Block — Issue-Close freigegeben."
        )
    elif verdict == "SKIPPED_AUTH_REDIRECT":
        lines.append(
            "Alle geprobten ACs leiten unauthentifiziert auf die Anmeldeseite "
            "um (SKIPPED_AUTH_REDIRECT) — kein inhaltlicher Prod-Nachweis "
            "möglich, aber auch kein FAIL. Kein Deploy-Block — Issue-Close "
            "freigegeben (#1353)."
        )
    elif verdict == "FAIL":
        lines.append(
            "FAIL: Regression in Produktion (Bot-Menü oder AC). Issue NICHT schließen."
        )
    else:  # PARTIAL
        fails = [p for p in probes if p.get("status") == "PASS" and p.get("prod_status") == "FAIL"]
        lines.append(
            f"PARTIAL: {len(fails)} von {len(probes)} ACs nicht erreichbar in Produktion. "
            "Issue NICHT schließen. Infrastruktur prüfen."
        )

    return "\n".join(lines) + "\n"


def check_bot_menu(
    token: str,
    expected: list[dict],
    api_base: str = "https://api.telegram.org",
) -> dict:
    """Prüft ob das Live-Bot-Menü mit `expected` übereinstimmt (AC-4).

    Returns:
        dict mit "check", "status" ("PASS" | "FAIL" | "SKIPPED"), "detail".
    """
    if not token:
        return {"check": "bot_menu", "status": "SKIPPED", "detail": "kein Token"}

    url = f"{api_base}/bot{token}/getMyCommands"
    try:
        status, body, _location = _normalize_http_get_result(
            _http_get(url, follow_redirects=False)
        )
        payload = json.loads(body.decode("utf-8", errors="replace"))
        result = payload.get("result", [])
        live_names = [c["command"] for c in result]
        expected_names = [c["command"] for c in expected]
        if live_names == expected_names:
            return {
                "check": "bot_menu",
                "status": "PASS",
                "detail": f"Live-Menü stimmt überein ({len(live_names)} Befehle)",
            }
        return {
            "check": "bot_menu",
            "status": "FAIL",
            "detail": f"live={live_names} expected={expected_names}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "check": "bot_menu",
            "status": "FAIL",
            "detail": f"Fehler beim Abrufen: {exc}",
        }


def _derive_verdict(probes: list[dict]) -> str:
    pass_probes = [p for p in probes if p.get("status") == "PASS"]
    skipped_probes = [p for p in probes if p.get("status") == "SKIPPED"]

    if probes and len(skipped_probes) == len(probes):
        return "SKIPPED_ALL"
    if not pass_probes:
        # Keine PASS-Findings, aber auch nicht alles SKIPPED — als PASS werten
        # (leere oder nicht-klassifizierbare Findings sind kein Block)
        return "PASS"

    # Fix #1353 (Spec v1.1, Punkt 4): ergaben ALLE geprobten PASS-Findings
    # ausschliesslich SKIPPED_AUTH_REDIRECT (kein einziger inhaltlicher
    # Nachweis), ist die Gesamt-Note NICHT PASS, sondern spiegelt den Skip
    # wider — sonst bliebe der Bug (blinder Gesamt-PASS) auf Verdict-Ebene
    # bestehen.
    if all(p.get("prod_status") == "SKIPPED_AUTH_REDIRECT" for p in pass_probes):
        return "SKIPPED_AUTH_REDIRECT"

    failed = [p for p in pass_probes if p.get("prod_status") == "FAIL"]
    if failed:
        return "PARTIAL"
    return "PASS"


def _scope_diff_base(repo_dir: Path = REPO_DIR) -> str:
    """Diff-Basis für die Scope-Erkennung (Issue #916).

    Liest den Gate-Marker (geschrieben von staging_gate.py, nie hier). Ist er
    vorhanden UND im Repo auflösbar → Marker-SHA. Sonst Fallback 'HEAD~1'.
    prod_selftest.py schreibt den Marker bewusst NICHT (nur Leser).

    Adversary-Finding F002: zeigt der Marker exakt auf HEAD, wäre der Diff
    HEAD..HEAD und immer leer (fälschlich "docs-only") — in diesem Fall
    bewusst auf HEAD~1 ausweichen statt den Marker (Selbstreferenz vermeiden).
    Schlägt der HEAD~1-Diff in einem Ein-Commit-Repo fehl, liefert der neue
    Shared-Helper konservativ "backend" (fail-closed, #1121) statt fälschlich
    "docs-only".

    Issue #1109: Zeigt last_prod_deploy.json auf einen (auflösbaren) Commit
    ungleich HEAD, hat dieser Vorrang als Diff-Basis — der Selftest muss den
    gesamten seit dem letzten Prod-Deploy ausgerollten Bereich abdecken, nicht
    nur den (evtl. späteren) Gate-Marker-Punkt.

    Issue #1283: `previous_commit` (der Vor-Deploy-Commit, von
    deploy-gregor-prod.sh als `$LOCAL` erfasst) hat HÖCHSTE Priorität vor
    `deployed_commit` — ein reiner Doku-Commit obenauf auf einem Code-Commit
    (stacked-docs-on-code) darf nicht dazu führen, dass nur der oberste
    (Doku-)Commit geprüft wird. Fehlt `previous_commit` (alter Marker vor
    diesem Fix) oder ist er ≠ HEAD nicht auflösbar/gleich HEAD, greift
    unverändert die bestehende Kette (`deployed_commit` → Gate-Marker →
    `HEAD~1`), fail-closed (#1121) intakt.
    """
    head = _e2e_paths.head_sha(repo_dir)

    prod_deploy_path = Path(repo_dir) / ".claude" / "last_prod_deploy.json"
    if prod_deploy_path.exists():
        try:
            prod_deploy_data = json.loads(prod_deploy_path.read_text())
        except (OSError, json.JSONDecodeError, ValueError):
            prod_deploy_data = {}

        previous_commit = prod_deploy_data.get("previous_commit")
        if previous_commit and previous_commit != head:
            resolvable = subprocess.run(
                ["git", "cat-file", "-e", previous_commit],
                capture_output=True, text=True, cwd=str(repo_dir),
            )
            if resolvable.returncode == 0:
                return previous_commit

        deployed_commit = prod_deploy_data.get("deployed_commit")
        if deployed_commit and deployed_commit != head:
            resolvable = subprocess.run(
                ["git", "cat-file", "-e", deployed_commit],
                capture_output=True, text=True, cwd=str(repo_dir),
            )
            if resolvable.returncode == 0:
                return deployed_commit

    marker_sha = _e2e_paths.read_last_gate_scope(repo_dir)
    if marker_sha and marker_sha != head:
        resolvable = subprocess.run(
            ["git", "cat-file", "-e", marker_sha],
            capture_output=True, text=True, cwd=str(repo_dir),
        )
        if resolvable.returncode == 0:
            return marker_sha
    return "HEAD~1"


def _detect_committed_scope(repo_dir: Path = REPO_DIR) -> str:
    """Klassifiziert die Commits seit dem Gate-Marker (Fallback HEAD~1..HEAD).

    Gespiegelt aus staging_gate._detect_committed_scope (Issue #786) — eigene
    Scope-Erkennung, damit ein docs-only-/tooling-Deploy nicht an einer stale
    Singleton-Attestation scheitert (False-FAIL).

    Returns: docs-only | frontend-only | backend | full-stack
    """
    # Issue #1084/#1096: Scope-Cache über den gemeinsamen Shared-Helper (auch
    # von staging_gate.py genutzt — eine Quelle statt Duplikat-Logik). Lief
    # staging_gate.py gerade erfolgreich für exakt denselben HEAD, liefert
    # der Helper den damals ermittelten Scope zurück statt eines
    # selbstreferenziellen, faelschlich 'docs-only' liefernden HEAD..HEAD-Diffs.
    cached_scope = _e2e_paths.cached_scope_for_sha(repo_dir, _e2e_paths.head_sha(repo_dir))
    if cached_scope is not None:
        return cached_scope

    base = _scope_diff_base(repo_dir)
    return _e2e_paths._detect_scope_from_git_diff(base, "HEAD", repo_dir)


def run_selftest(e2e_path: Path, workflow: str, scope: str | None = None) -> int:
    # Issue #786: docs-only/tooling-Deploy → kein Code in Prod → Selftest skippen,
    # statt an stale Singleton-Attestation (Commit-Mismatch) zu scheitern.
    if scope is None:
        scope = _detect_committed_scope()
    if scope == "docs-only":
        _log("INFO: Scope docs-only — Selftest übersprungen (kein Code-Deploy).")
        return 0

    report_path = REPO_DIR / "docs" / "artifacts" / workflow / "prod-selftest.md"

    # AC-5: e2e_verified.json fehlt → docs-only / kein Block
    if not e2e_path.exists():
        _log(
            f"INFO: e2e_verified.json nicht vorhanden unter {e2e_path} — "
            "Selftest übersprungen (docs-only oder erster Deploy)."
        )
        return 0

    try:
        verified = json.loads(e2e_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"FEHLER: e2e_verified.json nicht lesbar: {exc}", stream=sys.stderr)
        return 1

    head = _head_sha()
    verified_commit = verified.get("verified_commit", "")

    # Phase 1: Commit-Attestation (Ancestor-Check)
    if head != verified_commit:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", verified_commit, head],
            cwd=str(REPO_DIR), capture_output=True
        )
        if ancestor.returncode != 0:
            _log(
                f"FAIL: Commit-Mismatch — HEAD={head[:8]} vs verified={verified_commit[:8]}",
                stream=sys.stderr,
            )
            _write_report(
                report_path,
                _render_fail_commit_mismatch(workflow, head, verified_commit),
            )
            return 1
        _log(f"PASS (Ancestor): verified_commit={verified_commit[:8]} ist Ancestor von HEAD={head[:8]}")

    # Phase 2: Health-Check
    health_ok, health_msg = _check_health()
    if not health_ok:
        _log(f"FAIL: Health-Check — {health_msg}", stream=sys.stderr)
        _write_report(
            report_path, _render_fail_health(workflow, head, health_msg)
        )
        return 1

    # Phase 3: AC-Attestation (concurrent)
    findings = verified.get("findings", [])
    if not findings:
        # Leer → als PASS werten (durch staging_gate eigentlich blockiert)
        _write_report(
            report_path,
            _render_full_report(workflow, head, health_msg, "PASS", []),
        )
        _log("PASS: keine Findings zu prüfen.")
        return 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        probes = list(pool.map(_probe_ac, findings))

    verdict = _derive_verdict(probes)

    # Phase 4: Bot-Menü-Check (additiv, gated)
    menu_finding = _check_bot_menu_prod()
    menu_line = (
        f"\n## Bot-Menü-Check\n\n"
        f"Status: **{menu_finding['status']}** — {menu_finding['detail']}\n"
    )
    if menu_finding["status"] == "FAIL":
        verdict = "FAIL"

    report_content = _render_full_report(workflow, head, health_msg, verdict, probes) + menu_line
    _write_report(report_path, report_content)

    _log(f"Verdict={verdict} (Bericht: {report_path})")
    return 0 if verdict in ("PASS", "SKIPPED_ALL", "SKIPPED_AUTH_REDIRECT") else 1


def _check_bot_menu_prod() -> dict:
    """Liest Prod-Bot-Token aus .env und prüft das Live-Menü (best-effort)."""
    token = _read_prod_bot_token()
    expected = _load_bot_commands()
    if expected is None:
        return {"check": "bot_menu", "status": "SKIPPED", "detail": "BOT_COMMANDS nicht ladbar"}
    return check_bot_menu(token, expected)


def _read_prod_bot_token() -> str:
    """Liest GZ_TELEGRAM_BOT_TOKEN aus /home/hem/gregor_zwanzig/.env (best-effort)."""
    env_path = REPO_DIR / ".env"
    try:
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("GZ_TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def _load_bot_commands() -> list[dict] | None:
    """Liest BOT_COMMANDS dependency-frei per AST aus src/output/channels/telegram.py.

    Kein Import der output-Pakete; kein pydantic nötig. Single Source of Truth
    bleibt telegram.py. Bei jedem Fehler (Datei fehlt, SyntaxError, kein
    literal-auswertbares BOT_COMMANDS) wird None zurückgegeben (fail-soft).
    """
    telegram_py = REPO_DIR / "src" / "output" / "channels" / "telegram.py"
    try:
        source = telegram_py.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(telegram_py))
        for node in tree.body:
            # ast.Assign: BOT_COMMANDS = [...]
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "BOT_COMMANDS":
                        return ast.literal_eval(node.value)
            # ast.AnnAssign: BOT_COMMANDS: list[...] = [...]
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id == "BOT_COMMANDS":
                    if node.value is not None:
                        return ast.literal_eval(node.value)
        return None  # BOT_COMMANDS nicht gefunden
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    parser = argparse.ArgumentParser(prog="prod_selftest")
    parser.add_argument(
        "--e2e-path",
        help="Override für .claude/e2e_verified.json",
    )
    parser.add_argument(
        "--workflow",
        help="Workflow-Name für Artefakt-Pfad (Fallback: GZ_ACTIVE_WORKFLOW, dann 'unknown')",
    )
    args = parser.parse_args()

    e2e_path = Path(args.e2e_path) if args.e2e_path else _default_e2e_path()

    # Fix 5 (#1327/#1228): OPENSPEC_ACTIVE_WORKFLOW ist die primäre Quelle,
    # GZ_ACTIVE_WORKFLOW (Legacy-Fallback, analog prod_send_gate.py) greift
    # nur wenn OPENSPEC_ACTIVE_WORKFLOW fehlt/leer ist.
    workflow = (
        args.workflow
        or os.environ.get("OPENSPEC_ACTIVE_WORKFLOW")
        or os.environ.get("GZ_ACTIVE_WORKFLOW")
    )
    if not workflow:
        _log(
            "WARN: weder OPENSPEC_ACTIVE_WORKFLOW noch GZ_ACTIVE_WORKFLOW "
            "gesetzt — Bericht wird unter docs/artifacts/unknown/prod-selftest.md "
            "abgelegt.",
            stream=sys.stderr,
        )
        workflow = "unknown"

    return run_selftest(e2e_path, workflow)


if __name__ == "__main__":
    sys.exit(main())
