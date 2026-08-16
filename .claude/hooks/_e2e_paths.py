"""
Gemeinsame E2E-Pfad-Helfer (Issue #665).

Pure Funktionen — keine Modul-Konstanten. Wird von staging_gate.py und
prod_selftest.py als dünner Shim-Layer verwendet.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Fix #1382: einzige Quelle der Stale-Grenze, geteilt von staging_gate.py und
# prod_selftest.py (vorher zwei getrennte/eine fehlende Definition).
STALE_HOURS = 24


def partition_findings(raw) -> "tuple[list, list]":
    """Trennt ein aus JSON geladenes Findings-Array in (gueltige, unverwertbare).

    Fix #1689: einziger Ort, der die Form eines Findings kennt — sowohl
    staging_gate.py (Schreibseite, hart) als auch prod_selftest.py (Leseseite,
    weich) rufen ausschließlich diese Funktion auf, statt je eigene
    isinstance-Prüfungen zu bauen (das war bereits der fünfte reaktive Guard
    an demselben Objektgraphen).

    ``raw`` ist ein beliebiger, bereits aus JSON geladener Wert. Ist ``raw``
    selbst keine Liste (z.B. ein Objekt/dict, eine Zahl oder ``None``), gilt
    der GESAMTE Wert als unverwertbar: ``gueltige`` bleibt leer, ``raw``
    landet als einziger Eintrag in ``unverwertbare``. Ist ``raw`` eine Liste,
    wird elementweise nach ``isinstance(f, dict)`` getrennt — beide
    Teillisten behalten die ursprüngliche Reihenfolge.

    Reine Funktion: keine Seiteneffekte, kein Zugriff auf Dateisystem/Zeit.
    """
    if not isinstance(raw, list):
        return [], [raw]
    gueltige = [f for f in raw if isinstance(f, dict)]
    unverwertbare = [f for f in raw if not isinstance(f, dict)]
    return gueltige, unverwertbare


def last_gate_scope_path(repo_dir) -> Path:
    """Marker-Pfad für die Gate-Scope-Basis (Issue #916):
    <repo_dir>/.claude/last_gate_scope.json.
    """
    return Path(repo_dir) / ".claude" / "last_gate_scope.json"


def write_last_gate_scope(repo_dir, sha, scope=None) -> None:
    """Schreibt {"gate_scope_sha": sha} in den Marker.

    Ist ``scope`` gesetzt, wird zusätzlich {"gate_last_scope": scope}
    mitgeschrieben (Scope-Cache für prod_selftest.py, Issue #1084). Ohne
    ``scope`` (Default None) bleibt das alte Format {"gate_scope_sha": sha}
    erhalten — bestehende Aufrufer bleiben unverändert kompatibel.

    Schreibfehler (z.B. read-only Dateisystem) werden geschluckt — das
    Gate-Ergebnis selbst darf davon nicht beeinflusst werden.
    """
    path = last_gate_scope_path(repo_dir)
    payload = {"gate_scope_sha": sha}
    if scope is not None:
        payload["gate_last_scope"] = scope
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
    except OSError:
        pass


def read_last_gate_scope(repo_dir) -> "str | None":
    """Liest gate_scope_sha aus dem Marker oder None bei fehlender/kaputter Datei."""
    path = last_gate_scope_path(repo_dir)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    sha = data.get("gate_scope_sha")
    return sha if sha else None


def read_last_gate_scope_entry(repo_dir) -> "dict | None":
    """Liest den vollen Marker-Eintrag (dict) oder None bei fehlender/kaputter Datei.

    Pendant zu read_last_gate_scope(), das ausschließlich den SHA-String
    liefert. Wird für den Scope-Cache in prod_selftest.py benötigt (Issue
    #1084), der zusätzlich das Feld gate_last_scope auswertet.
    """
    path = last_gate_scope_path(repo_dir)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def cached_scope_for_sha(repo_dir, sha) -> "str | None":
    """Gibt den im Marker gecachten Scope zurück, aber NUR wenn der Marker
    exakt auf `sha` zeigt UND ein gate_last_scope-Feld vorhanden ist. Sonst
    None (Aufrufer fällt auf die bestehende Diff-Logik zurück).

    Extrahiert aus prod_selftest.py (#1084), damit staging_gate.py und
    prod_selftest.py denselben Cache-Zugriff verwenden — Schreibseite und
    Leseseite dürfen nicht mehr auseinanderlaufen (Issue #1096).

    Adversary-Finding F001: ein gecachter Wert von "docs-only" wird NIE
    blind übernommen (gilt als Cache-Miss). Ein docs-only-Cache hat keinen
    Schutzwert — der Diff-Fallback liefert bei einem echten Doku-Commit
    ohnehin dasselbe Ergebnis, deckt bei einem VOR diesem Fix bereits
    vergifteten Marker (gate_last_scope fälschlich "docs-only" für einen
    echten Code-Commit) aber den tatsächlichen Scope auf statt den
    Altlast-Wert zu wiederholen.
    """
    entry = read_last_gate_scope_entry(repo_dir)
    if entry is None:
        return None
    cached = entry.get("gate_last_scope")
    if cached is not None and cached != "docs-only" and entry.get("gate_scope_sha") == sha:
        return cached
    return None


def last_preflight_base_path(repo_dir) -> Path:
    """Marker-Pfad fuer die Preflight-Diff-Basis (henemm-infra#148 / #1428):
    <repo_dir>/.claude/last_preflight_base.json.
    """
    return Path(repo_dir) / ".claude" / "last_preflight_base.json"


def write_preflight_base(repo_dir, target_sha, base_sha) -> None:
    """Hinterlegt {"target_sha": target_sha, "base_sha": base_sha} -- die vom
    Preflight (Issue #1130) tatsaechlich verwendete Diff-Basis (der alte, noch
    live laufende Commit) fuer den angegebenen Ziel-Commit.

    KEIN Scope-Cache (im Unterschied zu write_last_gate_scope/gate_last_scope):
    nur die Diff-BASIS wird hinterlegt, der Scope wird vom Aufrufer immer neu
    aus dem echten git-diff berechnet -- die F001-Schutzregel in
    cached_scope_for_sha() (docs-only-Werte nie blind uebernehmen) bleibt
    davon unberuehrt. Ein einzelner Eintrag genuegt (wird bei jedem Preflight
    ueberschrieben). Schreibfehler werden geschluckt.
    """
    path = last_preflight_base_path(repo_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"target_sha": target_sha, "base_sha": base_sha}))
    except OSError:
        pass


def read_preflight_base(repo_dir, target_sha) -> "str | None":
    """Liefert die vom Preflight hinterlegte Diff-Basis fuer GENAU target_sha,
    oder None (Datei fehlt/kaputt/Ziel-Commit stimmt nicht ueberein --
    Aufrufer faellt dann auf die bestehende Marker-/HEAD~1-Logik zurueck)."""
    path = last_preflight_base_path(repo_dir)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("target_sha") != target_sha:
        return None
    base = data.get("base_sha")
    return base if base else None


def _git_diff_names(base, target, repo_dir) -> "list[str] | None":
    """git diff --name-only <base> <target> in repo_dir.

    Rückgabe: Liste der geänderten Pfade bei Erfolg, None bei git-Fehler
    (returncode != 0, z.B. nicht auflösbare Basis). None ist bewusst von einer
    leeren Liste (echter Leer-Diff) unterscheidbar, damit Aufrufer fail-closed
    reagieren können statt einen Fehler wie einen Leer-Diff zu behandeln
    (Issue #1121).
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", base, target],
        capture_output=True, text=True, cwd=str(repo_dir),
    )
    if result.returncode != 0:
        return None
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def commit_exists(sha, repo_dir) -> bool:
    """Prüft per `git cat-file -e`, ob `sha` in repo_dir auflösbar ist.

    Gemeinsame Stelle für die zuvor fünffach duplizierte Existenzprüfung
    (#1307 Scheibe B, Befund 4): staging_gate._scope_diff_base() (2x) und
    prod_selftest._scope_diff_base() (3x) setzten je einen eigenen Subprozess
    ab. Verhalten unverändert übernommen: Rückgabecode 0 → True, sonst False
    (der Aufrufer weicht dann auf seine nächste Basis aus).
    """
    result = subprocess.run(
        ["git", "cat-file", "-e", sha],
        capture_output=True, text=True, cwd=str(repo_dir),
    )
    return result.returncode == 0


def _detect_scope_from_git_diff(base, target, repo_dir) -> str:
    """Scope-Klassifikation des Diffs base..target (Issue #1121).

    Konsolidiert die zuvor in staging_gate.py und prod_selftest.py doppelt
    vorliegende Präfix-Klassifikation. Schlägt der git diff fehl (returncode
    != 0, z.B. nicht auflösbare Basis), wird NICHT "docs-only" geliefert (das
    war der #1121-Bug: leerer stdout eines gescheiterten Aufrufs sah aus wie
    ein echter Leer-Diff), sondern konservativ "backend" (fail-closed).

    Returns: frontend-only | backend | full-stack | docs-only
    """
    changed = _git_diff_names(base, target, repo_dir)
    if changed is None:
        return "backend"
    if not changed:
        return "docs-only"

    has_frontend = False
    has_backend = False
    for path in changed:
        # Playwright-Testinfrastruktur (Specs, Setup, Configs, Fixtures,
        # Helfer) — kein ausgelieferter Produktivcode, wird von keinem
        # laufenden Dienst geladen, also kein Deploy-Drift-Risiko. Symmetrisch
        # zur bereits bestehenden tests/-Ausnahme weiter unten. MUSS vor dem
        # generischen frontend/-Zweig stehen, sonst greift dieser zuerst
        # (#1197: e2e-only-Diff wurde fälschlich frontend-only und blockte den
        # Deploy-Gate).
        if path.startswith("frontend/e2e/"):
            pass
        elif path.startswith("frontend/"):
            has_frontend = True
        elif (
            path.startswith("src/")
            or path.startswith("api/")
            or path.startswith("internal/")
            or path.startswith("cmd/")
        ):
            has_backend = True
        elif (
            path.startswith("docs/")
            or path.startswith(".claude/")
            or path.endswith(".md")
            or path.startswith("README")
            or path == ".gitignore"
            or path.startswith("tests/")
            # Werkzeugkonfiguration der Entwicklungs-Kette (Gates, LoC-Limit,
            # Workflow-Phasen) — von keinem laufenden Dienst gelesen, analog
            # .claude/. Bewusst exakte Gleichheit statt *.yaml: jede andere
            # YAML-Datei bleibt konservativ backend.
            or path == "openspec.yaml"
        ):
            pass
        else:
            has_backend = True

    if has_frontend and has_backend:
        return "full-stack"
    if has_frontend:
        return "frontend-only"
    if has_backend:
        return "backend"
    return "docs-only"


def head_sha(repo_dir) -> str:
    """Gibt den aktuellen Git-HEAD-SHA zurück oder 'UNKNOWN' bei Fehler."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(repo_dir),
    )
    if result.returncode != 0:
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def commit_e2e_path(repo_dir, sha) -> Path:
    """Commit-getaggter Attestation-Pfad: .claude/e2e_verified/<sha>.json

    Defensiv: leerer oder None-SHA → 'UNKNOWN' (kein kaputter Dateiname).
    """
    sha = sha or "UNKNOWN"
    return Path(repo_dir) / ".claude" / "e2e_verified" / f"{sha}.json"


def shared_repo_dir(cwd=None) -> "Path | None":
    """Geteilter Hauptrepo-Arbeitsbaum (Ort der Attestation, überlebt deploy reset --hard).

    git rev-parse --git-common-dir aus cwd → <hauptrepo>/.git; relativ→absolut gegen cwd,
    dann .parent. Bei git-Fehler/leer → None (Aufrufer fällt fail-soft zurück).
    """
    base = Path(cwd) if cwd else Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, cwd=str(base),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = (base / common).resolve()
    return common.parent


def worktree_repo_dir(cwd=None) -> "Path | None":
    """Aktueller Worktree-Arbeitsbaum (Commit-/Scope-Quelle).

    git rev-parse --show-toplevel aus cwd. Bei git-Fehler/leer → None.
    """
    base = Path(cwd) if cwd else Path.cwd()
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=str(base),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return Path(result.stdout.strip())


def _nearest_verified_ancestor(ref: str, git_dir: Path, shared_dir: Path,
                               max_count: int = 40) -> "tuple[str | None, dict | None]":
    """Fix #1382 (verschoben aus staging_gate.py, Issue #1197): Nächster VERIFIED,
    nicht-staler Ancestor von ``ref`` mit commit-getaggter Attestation — dient als
    Deploy-Basis, wenn keine exakte <ref>.json existiert.

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

    Einzige Definition dieser Ancestor-Prüfung im Projekt — staging_gate.py und
    prod_selftest.py delegieren beide hierher (Fix #1382, Scheibe 2).
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
        path = commit_e2e_path(shared_dir, sha)
        if not path.exists():
            continue
        # Fix #1382 Scheibe 2 (Adversary-Fund F001, PO-Entscheidung 2026-07-26):
        # Der ERSTE Commit mit einer existierenden Attestation ist entscheidend.
        # Vorher wurde ein nicht bestandener Nachweis (BROKEN/AMBIGUOUS/leer/
        # fehlendes Feld/korrupt/veraltet) per `continue` übersprungen, sodass
        # die Suche an ihm vorbei zu einem älteren, evtl. bestandenen Vorfahren
        # weiterlief. Jetzt beendet der erste gefundene Nachweis die Suche
        # fail-closed, sobald er nicht besteht — einheitlich für alle
        # Fehlerarten (kein Sonderfall mehr für "zu alt").
        try:
            cdata = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return (None, None)
        if not isinstance(cdata, dict):
            return (None, None)
        if cdata.get("verified_commit") != sha:
            return (None, None)
        if not str(cdata.get("staging_verdict", "")).startswith("VERIFIED"):
            return (None, None)
        try:
            verified_at = datetime.fromisoformat(cdata.get("verified_at", ""))
            if verified_at.tzinfo is None:
                verified_at = verified_at.replace(tzinfo=timezone.utc)
        except ValueError:
            return (None, None)
        if datetime.now(timezone.utc) - verified_at > timedelta(hours=STALE_HOURS):
            return (None, None)
        return (sha, cdata)
    return (None, None)
