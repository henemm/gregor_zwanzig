#!/usr/bin/env python3
"""
Staging Gate Hook (Issue #521 — Staging Validator Agent)

Zwei Modi:

Mode A — Verdict schreiben (vom Staging Validator Agent aufgerufen):
    python3 staging_gate.py --write-verdict "VERIFIED: ..." \
        --findings-json /tmp/findings.json [--e2e-path PATH]

    Schreibt .claude/e2e_verified.json mit verified_commit, staging_verdict,
    findings, verified_at, scope, environment.
    Exit 0 bei VERIFIED/AMBIGUOUS, Exit 1 bei BROKEN.
    Datei wird NUR bei Exit 0 geschrieben (kein BROKEN-Artefakt).

Mode B — Gate-Check (von deploy-gregor-prod.sh aufgerufen):
    python3 staging_gate.py --check [--e2e-path PATH] [--scope SCOPE]

    Prüft Reihenfolge:
      1. GZ_SKIP_E2E_GATE=1 → Warn + Exit 0
      2. --scope=docs-only ODER detect_scope==docs-only → Exit 0
      3. e2e_verified.json fehlt → Exit 1
      4. verified_commit != HEAD-SHA → Exit 1
      5. staging_verdict beginnt nicht mit VERIFIED → Exit 1
      6. verified_at älter als 24h → Exit 1
      7. Alle OK → Exit 0

Mode C — Scope detection:
    python3 staging_gate.py --detect-scope  # gibt Scope-String auf stdout
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import importlib.util as _importlib_util

_e2e_paths_spec = _importlib_util.spec_from_file_location(
    "_e2e_paths_staging_gate",
    str(Path(__file__).resolve().parent / "_e2e_paths.py"),
)
_e2e_paths = _importlib_util.module_from_spec(_e2e_paths_spec)
_e2e_paths_spec.loader.exec_module(_e2e_paths)

_DEFAULT_REPO_DIR = Path("/home/hem/gregor_zwanzig")
REPO_DIR = _DEFAULT_REPO_DIR
CANONICAL_E2E_PATH = REPO_DIR / ".claude" / "e2e_verified.json"
STALE_HOURS = 24
# Issue #666: max. behaltene commit-getaggte Attestationen (analog .backups/-Pattern)
ATTESTATION_RETENTION = 20


def _log(msg: str, stream=sys.stdout) -> None:
    print(f"[staging-gate] {msg}", file=stream)


def _shared_repo_dir() -> Path:
    """Datei-Ort der Attestation: geteiltes Hauptrepo.

    Test-Override via REPO_DIR (monkeypatch ≠ Default) → Alt-Verhalten (ein Repo).
    Sonst dynamisch via git, fail-soft auf REPO_DIR.
    Sentinel-Vergleich ist Wert-basiert (Path.__eq__): ein Test, der REPO_DIR exakt
    auf `_DEFAULT_REPO_DIR` setzt, gilt absichtlich als 'nicht umgebogen'.
    """
    if REPO_DIR != _DEFAULT_REPO_DIR:
        return REPO_DIR
    resolved = _e2e_paths.shared_repo_dir()
    return resolved if resolved is not None else REPO_DIR


def _verified_repo_dir() -> Path:
    """Commit-/Scope-Quelle: aktueller Worktree (cwd).

    Test-Override via REPO_DIR (monkeypatch ≠ Default) → Alt-Verhalten.
    Sonst dynamisch via git, fail-soft.
    """
    if REPO_DIR != _DEFAULT_REPO_DIR:
        return REPO_DIR
    resolved = _e2e_paths.worktree_repo_dir()
    return resolved if resolved is not None else REPO_DIR


def _head_sha() -> str:
    return _e2e_paths.head_sha(_verified_repo_dir())


def _commit_e2e_path(sha: str | None = None) -> Path:
    """Commit-getaggter Attestation-Pfad: .claude/e2e_verified/<sha>.json"""
    return _e2e_paths.commit_e2e_path(_shared_repo_dir(), sha or _head_sha())


def _default_e2e_path(expected_commit: str | None = None) -> Path:
    """Default-Pfad-Auflösung: commit-getaggt (Vorrang), sonst Singleton-Fallback.

    Existiert die commit-getaggte Datei für den Referenz-Commit → diese (auch wenn
    ihr Inhalt veraltet ist; das prüft gate_check). Sonst, wenn das alte Singleton
    existiert → Fallback (Migration). Sonst die (nicht existente) getaggte Datei →
    wird von gate_check als 'fehlt' behandelt.

    Issue #1130: Im Preflight (``expected_commit`` gesetzt) wird die Attestation für
    den ZIEL-Commit gesucht, nicht für den (noch alten) HEAD.
    """
    shared = _shared_repo_dir()
    canonical = CANONICAL_E2E_PATH if REPO_DIR != _DEFAULT_REPO_DIR else shared / ".claude" / "e2e_verified.json"
    return _e2e_paths.default_e2e_path(shared, canonical, expected_commit or _head_sha())


def _scope_diff_base() -> str:
    """Diff-Basis für die Scope-Erkennung (Issue #916).

    Ist ein Gate-Marker vorhanden UND der SHA im Repo auflösbar → Marker-SHA
    (deckt ALLE Commits seit dem letzten erfolgreichen Gate-Lauf ab). Sonst
    (Erstlauf oder History-Rewrite) Fallback auf 'HEAD~1'.

    Adversary-Finding F002: zeigt der Marker exakt auf HEAD, wäre der Diff
    HEAD..HEAD und immer leer (fälschlich "docs-only") — z.B. bei einem
    Marker im alten #916-Format ohne gate_last_scope, der dadurch keinen
    Cache-Treffer liefert. In diesem Fall bewusst auf HEAD~1 ausweichen statt
    den Marker (Selbstreferenz vermeiden).
    """
    marker_sha = _e2e_paths.read_last_gate_scope(_shared_repo_dir())
    if marker_sha and marker_sha != _head_sha():
        resolvable = subprocess.run(
            ["git", "cat-file", "-e", marker_sha],
            capture_output=True, text=True, cwd=str(_verified_repo_dir()),
        )
        if resolvable.returncode == 0:
            return marker_sha
    return "HEAD~1"


def _detect_committed_scope(expected_commit: str | None = None) -> str:
    """Klassifiziert die Commits seit dem Gate-Marker (Fallback HEAD~1..HEAD).

    Issue #1096: läuft ein zweiter --check-Lauf auf demselben HEAD (z.B.
    Doppel-Lauf beim Deploy), liefert der HEAD..HEAD-Diff faelschlich
    docs-only. Bevor die Diff-Logik ueberhaupt laeuft, wird daher zuerst der
    im Marker gecachte Scope fuer exakt diesen HEAD geprueft (derselbe
    Shared-Helper wie prod_selftest.py) — Treffer liefert den beim ersten
    Lauf tatsaechlich ermittelten Scope zurueck, ohne Selbstvergiftung.

    Issue #1130: Im Preflight (``expected_commit`` gesetzt) ist HEAD noch der
    alte Prod-Commit. Massgeblich ist dann, was der Deploy AUSROLLT — also der
    Diff HEAD..EXP. Der HEAD-basierte Scope-Cache wird bewusst uebergangen (sein
    Key passt nicht zum noch nicht ausgecheckten Ziel-Commit).

    Returns: frontend-only | backend | full-stack | docs-only
    """
    if expected_commit is None:
        cached = _e2e_paths.cached_scope_for_sha(_shared_repo_dir(), _head_sha())
        if cached is not None:
            return cached
        base, target = _scope_diff_base(), "HEAD"
    else:
        base, target = "HEAD", expected_commit

    return _e2e_paths._detect_scope_from_git_diff(base, target, _verified_repo_dir())


def prune_old_attestations(tagged_dir: Path, retention: int = ATTESTATION_RETENTION) -> None:
    """Issue #666: Hält das commit-getaggte Attestation-Verzeichnis auf `retention`
    Dateien (analog data_schema_backup.prune_old_backups).

    Sortiert nach mtime absteigend und löscht alles jenseits der jüngsten N. Die
    gerade geschriebene HEAD-Datei ist immer die jüngste und wird daher nie
    geprunt. Löschfehler werden geschluckt — das Verdict-Schreiben bleibt davon
    unberührt. Greift NUR im 'e2e_verified'-Verzeichnis (schützt vor einem
    --e2e-path-Override, der woanders hinschreibt) — nie im Singleton-Fallback.
    """
    if tagged_dir.name != "e2e_verified" or not tagged_dir.is_dir():
        return
    files = sorted(
        tagged_dir.glob("*.json"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for old in files[retention:]:
        try:
            old.unlink()
        except OSError:
            pass


def _telegram_live_gate() -> int:
    """Issue #686 AC-5: Verweigert das Verdict, wenn der committete Scope den
    Telegram-Pfad berührt, aber GZ_TELEGRAM_TEST_CHAT_ID fehlt (SKIPPED ≠ grün).

    Returns: 0 = ok (kein Telegram-Scope ODER Test-Chat-ID gesetzt), 1 = blocken.
    Import-Fehler des dependency-armen Hooks sind fail-soft (Warnung + 0).
    """
    import importlib.util

    hook_path = Path(__file__).parent / "e2e_telegram_live.py"
    try:
        spec = importlib.util.spec_from_file_location("_e2e_telegram_live_gate", str(hook_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 — fail-soft bei reinem Importfehler
        _log(f"WARN: e2e_telegram_live nicht ladbar ({exc}) — Telegram-Gate übersprungen.", stream=sys.stderr)
        return 0

    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True, cwd=str(_verified_repo_dir()),
    )
    if result.returncode != 0:
        # Fehlgeschlagener Diff (z.B. kein HEAD~1) -> konservativ als
        # potenziell Telegram-relevant behandeln (Issue #1121, AC-5).
        changed = None
    else:
        changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    if changed is not None and not mod._scope_touches_telegram(changed):
        return 0
    if mod.gate(scope_touches_telegram=True, env=dict(os.environ)) != 0:
        _log(
            "FEHLER: Change berührt den Telegram-Pfad, aber GZ_TELEGRAM_TEST_CHAT_ID "
            "fehlt — funktionaler Telegram-Live-Test (AC-5, Issue #686) nicht bestanden. "
            "Verdict verweigert.",
            stream=sys.stderr,
        )
        return 1
    return 0


def write_verdict(verdict: str, findings_path: Path, e2e_path: Path | None = None,
                  scope_override: str | None = None) -> int:
    """Mode A: Verdict in e2e_verified.json schreiben."""
    sha = _head_sha()
    if e2e_path is None:
        e2e_path = _commit_e2e_path(sha)
    verdict_upper = verdict.strip().upper()
    if verdict_upper.startswith("BROKEN"):
        _log(f"BROKEN-Verdict erhalten: {verdict}")
        _log("Kein VERIFIED-Artefakt geschrieben — /e2e-verify erneut ausführen.", stream=sys.stderr)
        return 1

    if _telegram_live_gate() != 0:
        return 1

    try:
        findings = json.loads(findings_path.read_text()) if findings_path.exists() else []
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Findings-Datei nicht lesbar: {exc}", stream=sys.stderr)
        return 1

    scope = scope_override or _detect_committed_scope()
    payload = {
        "verified_commit": sha,
        "staging_verdict": verdict,
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "environment": "staging",
    }
    # Issue #1197: Blind-Overwrite bei zwei Workflows auf demselben HEAD
    # vermeiden. Traegt eine bestehende Attestation denselben verified_commit,
    # werden die findings verlustfrei vereinigt (dedup ueber stabile
    # Serialisierung) statt ueberschrieben. Bei abweichendem/fehlendem/kaputtem
    # verified_commit bleibt das reguläre Überschreiben (bisheriges Verhalten).
    if e2e_path.exists():
        try:
            existing = json.loads(e2e_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = None
        if existing is not None and existing.get("verified_commit") == sha:
            existing_findings = existing.get("findings") or []
            seen = {json.dumps(f, sort_keys=True) for f in existing_findings}
            merged = list(existing_findings)
            for f in findings:
                key = json.dumps(f, sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    merged.append(f)
            payload["findings"] = merged
    e2e_path.parent.mkdir(parents=True, exist_ok=True)
    e2e_path.write_text(json.dumps(payload, indent=2))
    _log(f"Verdict geschrieben: {verdict} (commit={payload['verified_commit'][:8]}, scope={scope})")
    try:
        prune_old_attestations(e2e_path.parent)
    except OSError:
        # Pruning ist Best-Effort — ein Fehler (z.B. stat() auf einer Datei, die
        # zwischen glob() und stat() verschwindet) darf das geschriebene Verdict
        # nie kippen (AC-4-Intention).
        pass
    return 0


def _nearest_verified_ancestor(ref: str, git_dir: Path, shared_dir: Path,
                               max_count: int = 40) -> "tuple[str | None, dict | None]":
    """Issue #1197: Nächster VERIFIED, nicht-staler Ancestor von ``ref`` mit
    commit-getaggter Attestation — dient als Deploy-Basis, wenn keine exakte
    <ref>.json existiert.

    Läuft ``git rev-list --max-count=N ref`` (newest-first, ``ref``
    eingeschlossen) im ``git_dir`` durch. Für den ERSTEN Commit C, dessen
    commit-getaggte Attestation im ``shared_dir`` existiert, ``verified_commit
    == C`` trägt, deren ``staging_verdict`` mit "VERIFIED" beginnt und deren
    ``verified_at`` nicht älter als STALE_HOURS ist, wird (C, cdata)
    zurückgegeben. Andernfalls (None, None). Jeder git-/JSON-Fehler ist
    fail-closed → (None, None).

    Anker: git_dir MUSS die Wurzel des Arbeitsbaums sein (in Produktion liefert
    ``_verified_repo_dir()`` genau ``git rev-parse --show-toplevel``). Zeigt der
    konfigurierte Pfad woanders hin (z.B. Unterverzeichnis, git löst per
    Discovery ein fremdes Eltern-Repo auf), wird fail-closed geblockt.
    """
    toplevel = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=str(git_dir),
    )
    if toplevel.returncode != 0 or not toplevel.stdout.strip():
        return (None, None)
    if Path(toplevel.stdout.strip()).resolve() != Path(git_dir).resolve():
        return (None, None)
    result = subprocess.run(
        ["git", "rev-list", f"--max-count={max_count}", ref],
        capture_output=True, text=True, cwd=str(git_dir),
    )
    if result.returncode != 0:
        return (None, None)
    for sha in (line.strip() for line in result.stdout.splitlines() if line.strip()):
        path = _e2e_paths.commit_e2e_path(shared_dir, sha)
        if not path.exists():
            continue
        try:
            cdata = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if cdata.get("verified_commit") != sha:
            continue
        if not str(cdata.get("staging_verdict", "")).startswith("VERIFIED"):
            continue
        try:
            verified_at = datetime.fromisoformat(cdata.get("verified_at", ""))
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if datetime.now(timezone.utc) - verified_at > timedelta(hours=STALE_HOURS):
            continue
        return (sha, cdata)
    return (None, None)


def gate_check(e2e_path: Path | None, scope_override: str | None,
               expected_commit: str | None = None) -> int:
    """Mode B: Gate-Check für deploy-gregor-prod.sh.

    Issue #1130: Ist ``expected_commit`` gesetzt (Deploy-Preflight VOR
    ``git reset --hard``), wird gegen diesen Ziel-Commit geprüft statt gegen
    HEAD — Attestations-Vergleich, Scope-Diff und Attestations-Pfad beziehen
    sich dann auf EXP. Der HEAD-basierte Scope-Marker wird im Preflight NICHT
    geschrieben (kein Cache-Poisoning eines noch nicht ausgerollten Zustands).
    Ohne das Flag ist das Verhalten unverändert.
    """
    if os.environ.get("GZ_SKIP_E2E_GATE") == "1":
        _log("WARN: GZ_SKIP_E2E_GATE=1 — Staging-Gate übersprungen (Notfall-Override).", stream=sys.stderr)
        return 0

    preflight = expected_commit is not None
    # Issue #1130 / Adversary F001: Der Ziel-Commit ist im Preflight ungeprüfter
    # externer Input (Deploy-Script-Variable). Ist er leer oder nicht auflösbar
    # (Tippfehler, noch nicht gefetcht), scheitert der Scope-Diff still → früher
    # fälschlich "docs-only" → fail-open Exit 0 OHNE Attestations-Prüfung. Genau
    # das darf dieser Preflight nie: fail-closed VOR jeder Scope-/Skip-Logik.
    if preflight:
        resolved = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{expected_commit}^{{commit}}"],
            capture_output=True, text=True, cwd=str(_verified_repo_dir()),
        )
        if resolved.returncode != 0 or not resolved.stdout.strip():
            _log(
                f"FEHLER: --expected-commit ({expected_commit!r}) ist kein auflösbarer "
                "Commit (leer, Tippfehler oder nicht gefetcht). Gate verweigert "
                "(fail-closed) — vor dem Preflight 'git fetch' sicherstellen.",
                stream=sys.stderr,
            )
            return 1
    scope = scope_override or _detect_committed_scope(expected_commit)
    if scope == "docs-only":
        _log(f"Scope '{scope}' — Staging-Gate übersprungen (kein UI/Backend-Change).")
        # Issue #1096 (Fix 2): ein expliziter --scope-Override behält Vorrang
        # fürs Gate-Verhalten (Exit 0 bleibt), aber der Cache darf dabei nicht
        # auf docs-only heruntergestuft werden, wenn für exakt diesen HEAD
        # bereits ein besserer (Nicht-docs-only-)Wert im Marker steht.
        # Issue #1130: Im Preflight gar keinen HEAD-Marker schreiben.
        if not preflight:
            existing = _e2e_paths.cached_scope_for_sha(_shared_repo_dir(), _head_sha())
            if existing is None or existing == "docs-only":
                _e2e_paths.write_last_gate_scope(_shared_repo_dir(), _head_sha(), scope)
        return 0

    if e2e_path is None:
        e2e_path = _default_e2e_path(expected_commit)

    ref = expected_commit or _head_sha()
    ref_label = "expected-commit" if preflight else "HEAD-SHA"

    data = None
    if e2e_path.exists():
        try:
            data = json.loads(e2e_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            _log(f"FEHLER: e2e_verified.json nicht lesbar: {exc}", stream=sys.stderr)
            return 1

    verified_commit = data.get("verified_commit", "") if data is not None else ""

    # Issue #1197: Kein exakter <ref>.json-Treffer (Datei fehlt oder trägt einen
    # anderen verified_commit) → nächsten VERIFIED, nicht-stalen Ancestor als
    # Basis auflösen und NUR relaxieren, wenn ref dessen Nachfahre ist UND der
    # Zuwachs Basis..ref docs-only ist. Sonst fail-closed blocken.
    if verified_commit != ref:
        git_dir = _verified_repo_dir()
        ancestor, _cdata = _nearest_verified_ancestor(ref, git_dir, _shared_repo_dir())
        if ancestor is not None:
            is_anc = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, ref],
                capture_output=True, text=True, cwd=str(git_dir),
            )
            if (
                is_anc.returncode == 0
                and _e2e_paths._detect_scope_from_git_diff(ancestor, ref, git_dir) == "docs-only"
            ):
                _log(
                    f"OK: Ancestor-Relaxierung (#1197): Basis {ancestor[:8]} VERIFIED, "
                    f"Zuwachs {ancestor[:8]}..{ref[:8]} docs-only — Staging-Gate bestanden."
                )
                if not preflight:
                    _e2e_paths.write_last_gate_scope(_shared_repo_dir(), _head_sha(), scope)
                return 0
        if data is None:
            _log(
                f"FEHLER: e2e_verified.json fehlt unter {e2e_path}. "
                "/e2e-verify ausführen, dann erneut deployen.",
                stream=sys.stderr,
            )
            return 1
        _log(
            f"FEHLER: verified_commit ({verified_commit[:8]}) != {ref_label} ({ref[:8]}). "
            "Veraltete Verifikation — /e2e-verify erneut ausführen.",
            stream=sys.stderr,
        )
        return 1

    # Exakt-Match (unverändertes Verhalten): VERIFIED- und Staleness-Checks auf data.
    verdict = data.get("staging_verdict", "")
    if not verdict.startswith("VERIFIED"):
        _log(
            f"FEHLER: staging_verdict ist nicht VERIFIED (war: {verdict!r}). "
            "/e2e-verify ausführen, dann erneut deployen.",
            stream=sys.stderr,
        )
        return 1

    verified_at_str = data.get("verified_at", "")
    try:
        verified_at = datetime.fromisoformat(verified_at_str)
        if verified_at.tzinfo is None:
            verified_at = verified_at.replace(tzinfo=timezone.utc)
    except ValueError:
        _log(f"FEHLER: verified_at ist kein ISO-Timestamp: {verified_at_str!r}", stream=sys.stderr)
        return 1

    age = datetime.now(timezone.utc) - verified_at
    if age > timedelta(hours=STALE_HOURS):
        _log(
            f"FEHLER: Verifikation ist {age.total_seconds()/3600:.1f}h alt (max {STALE_HOURS}h). "
            "Artefakt abgelaufen — /e2e-verify erneut ausführen.",
            stream=sys.stderr,
        )
        return 1

    _log(f"OK: Staging-Gate bestanden (commit={ref[:8]}, verdict={verdict!r}).")
    # Issue #1130: Preflight schreibt keinen Marker — HEAD ist noch der alte
    # Prod-Commit, der reguläre --check nach dem Reset cached korrekt.
    if not preflight:
        _e2e_paths.write_last_gate_scope(_shared_repo_dir(), _head_sha(), scope)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="staging_gate")
    parser.add_argument("--check", action="store_true", help="Mode B: Gate-Check")
    parser.add_argument("--write-verdict", help="Mode A: Verdict-String zum Schreiben")
    parser.add_argument("--findings-json", help="Pfad zur Findings-JSON (Mode A)")
    parser.add_argument("--e2e-path", help="Pfad zur e2e_verified.json (Override)")
    parser.add_argument("--scope", help="Scope-Override (frontend-only|backend|full-stack|docs-only)")
    parser.add_argument("--expected-commit", help="Ziel-Commit für Preflight-Check (Issue #1130): prüft gegen diesen SHA statt HEAD")
    parser.add_argument("--detect-scope", action="store_true", help="Mode C: Scope ausgeben")
    args = parser.parse_args()

    e2e_path = Path(args.e2e_path) if args.e2e_path else None

    if args.detect_scope:
        print(_detect_committed_scope())
        return 0

    if args.write_verdict:
        findings_path = Path(args.findings_json) if args.findings_json else Path("/dev/null")
        return write_verdict(args.write_verdict, findings_path, e2e_path, args.scope)

    if args.check:
        return gate_check(e2e_path, args.scope, expected_commit=args.expected_commit)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
