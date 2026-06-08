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
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

REPO_DIR = Path("/home/hem/gregor_zwanzig")
CANONICAL_E2E_PATH = REPO_DIR / ".claude" / "e2e_verified.json"
PROD_BASE = "https://gregor20.henemm.com"
HEALTH_URL = f"{PROD_BASE}/api/health"
PROBE_TIMEOUT = 8
MAX_WORKERS = 5


def _log(msg: str, stream=sys.stdout) -> None:
    print(f"[prod-selftest] {msg}", file=stream)


def _head_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=str(REPO_DIR),
    )
    if result.returncode != 0:
        _log(f"WARN: git rev-parse HEAD fehlgeschlagen (code {result.returncode}): {result.stderr.strip()}", stream=sys.stderr)
        return "UNKNOWN"
    return result.stdout.strip()


def _commit_e2e_path(sha: str | None = None) -> Path:
    """Commit-getaggter Attestation-Pfad: .claude/e2e_verified/<sha>.json"""
    sha = sha or _head_sha()
    return REPO_DIR / ".claude" / "e2e_verified" / f"{sha}.json"


def _default_e2e_path() -> Path:
    """Default-Pfad-Auflösung: commit-getaggt (Vorrang), sonst Singleton-Fallback.

    Existiert die commit-getaggte Datei für HEAD → diese. Sonst, wenn das alte
    Singleton existiert → Fallback (Migration). Sonst die (nicht existente)
    getaggte Datei → wird von run_selftest als 'fehlt' behandelt.
    """
    tagged = _commit_e2e_path(_head_sha())
    if tagged.exists():
        return tagged
    if CANONICAL_E2E_PATH.exists():
        return CANONICAL_E2E_PATH
    return tagged


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


def _http_get(url: str, follow_redirects: bool = False) -> tuple[int, bytes]:
    """HTTP-GET via stdlib. Returns (status_code, body).

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
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        # 3xx und 4xx/5xx landen hier — body lesen, Status zurückgeben
        try:
            body = exc.read()
        except Exception:
            body = b""
        return exc.code, body


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Blockt Redirects, lässt HTTPError mit 3xx-Code durchschlagen."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _probe_ac(finding: dict) -> dict:
    """HTTP-Probe für ein Finding. SKIPPED → ATTESTED_SKIPPED ohne Netzwerk."""
    if finding.get("status") == "SKIPPED":
        return {
            **finding,
            "prod_url": "—",
            "prod_http": "—",
            "prod_status": "ATTESTED_SKIPPED",
        }

    prod_url = _staging_to_prod_url(finding.get("url", ""))
    try:
        status, _ = _http_get(prod_url, follow_redirects=False)
        ok = status in (200, 302)
        return {
            **finding,
            "prod_url": prod_url,
            "prod_http": status,
            "prod_status": "PASS" if ok else "FAIL",
        }
    except (urllib.error.URLError, OSError) as exc:
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
        status, body = _http_get(HEALTH_URL, follow_redirects=True)
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
    else:  # PARTIAL
        fails = [p for p in probes if p.get("status") == "PASS" and p.get("prod_status") == "FAIL"]
        lines.append(
            f"PARTIAL: {len(fails)} von {len(probes)} ACs nicht erreichbar in Produktion. "
            "Issue NICHT schließen. Infrastruktur prüfen."
        )

    return "\n".join(lines) + "\n"


def _derive_verdict(probes: list[dict]) -> str:
    pass_probes = [p for p in probes if p.get("status") == "PASS"]
    skipped_probes = [p for p in probes if p.get("status") == "SKIPPED"]

    if probes and len(skipped_probes) == len(probes):
        return "SKIPPED_ALL"
    if not pass_probes:
        # Keine PASS-Findings, aber auch nicht alles SKIPPED — als PASS werten
        # (leere oder nicht-klassifizierbare Findings sind kein Block)
        return "PASS"

    failed = [p for p in pass_probes if p.get("prod_status") == "FAIL"]
    if failed:
        return "PARTIAL"
    return "PASS"


def run_selftest(e2e_path: Path, workflow: str) -> int:
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

    # Phase 1: Commit-Attestation
    if head != verified_commit:
        _log(
            f"FAIL: Commit-Mismatch — HEAD={head[:8]} vs verified={verified_commit[:8]}",
            stream=sys.stderr,
        )
        _write_report(
            report_path,
            _render_fail_commit_mismatch(workflow, head, verified_commit),
        )
        return 1

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
    _write_report(
        report_path,
        _render_full_report(workflow, head, health_msg, verdict, probes),
    )

    _log(f"Verdict={verdict} (Bericht: {report_path})")
    return 0 if verdict in ("PASS", "SKIPPED_ALL") else 1


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

    workflow = args.workflow or os.environ.get("GZ_ACTIVE_WORKFLOW")
    if not workflow:
        _log(
            "WARN: GZ_ACTIVE_WORKFLOW nicht gesetzt — Bericht wird unter "
            "docs/artifacts/unknown/prod-selftest.md abgelegt.",
            stream=sys.stderr,
        )
        workflow = "unknown"

    return run_selftest(e2e_path, workflow)


if __name__ == "__main__":
    sys.exit(main())
