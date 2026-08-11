#!/usr/bin/env python3
"""
Staging Gate Hook (Issue #521 — Staging Validator Agent)

Zwei Modi:

Mode A — Verdict schreiben (vom Staging Validator Agent aufgerufen):
    python3 staging_gate.py --write-verdict "VERIFIED: ..." \
        --findings-json /tmp/findings.json [--e2e-path PATH]

    Schreibt die commit-getaggte Nachweis-Datei .claude/e2e_verified/<sha>.json
    mit verified_commit, staging_verdict, findings, verified_at, scope,
    environment.
    Exit 0 bei VERIFIED/AMBIGUOUS, Exit 1 bei BROKEN.
    Datei wird NUR bei Exit 0 geschrieben (kein BROKEN-Artefakt).

Mode B — Gate-Check (von deploy-gregor-prod.sh aufgerufen):
    python3 staging_gate.py --check [--e2e-path PATH] [--scope SCOPE] [--expected-commit REF]

    Nachweis wird ausschließlich über den commit-getaggten Pfad
    .claude/e2e_verified/<sha>.json aufgelöst (Fix #1382 — kein Rückfall mehr
    auf die frühere Sammeldatei, Details s. Issue #1382). Prüft Reihenfolge:
      1. GZ_SKIP_E2E_GATE=1 → Warn + Exit 0
      2. --scope=docs-only ODER detect_scope==docs-only → Exit 0
      3. Kein exakter Treffer für den Zielstand → Ancestor-Relaxierung
         versuchen (nur bei VERIFIED, nicht-stalem Vorfahren UND docs-only
         Zuwachs); sonst Exit 1 mit einer von fünf Meldungen (i)-(v), s.
         docs/specs/modules/fix_1382_deploy_gate_evidence.md
      4. Exakter Treffer: staging_verdict beginnt nicht mit VERIFIED → Exit 1
      5. Exakter Treffer: verified_at älter als 24h → Exit 1
      6. Alle OK → Exit 0

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
# Fix #1382: der Rückfall auf die frühere Sammeldatei entfällt ersatzlos — es
# gibt keine gesonderte Konstante für ihren Pfad mehr. Der Nachweis-Pfad wird
# ausschließlich über _commit_e2e_path()/_e2e_paths.commit_e2e_path()
# aufgelöst, dieselbe Funktion, die auch write_verdict beim Schreiben nutzt.
STALE_HOURS = _e2e_paths.STALE_HOURS
# Issue #666: max. behaltene commit-getaggte Attestationen (analog .backups/-Pattern)
ATTESTATION_RETENTION = 20
# Issue #1558: Pfad des Frontend-Browser-Gates bewusst als MODUL-Attribut (nicht
# inline im Funktionsrumpf wie beim Telegram-Vorbild, Z. 224) — nur so kann ein
# Test auf eine ECHT kaputte Datei zeigen und damit einen realen Importfehler
# ausloesen statt eines gemockten (verbotenes Mock-Theater).
FRONTEND_GATE_PATH = Path(__file__).resolve().parent / "e2e_frontend_browser_gate.py"
# Issue #1558 (Nachtrag 2026-08-08): EIGENER Notausgang fuer den Browserlauf.
# GZ_SKIP_E2E_GATE wirkt nur in gate_check() (Deploy-Check) — im write_verdict()-
# Pfad gab es bis hierher gar keinen. Bewusst eine zweite Variable statt einer
# Ausweitung der ersten: gate_check() ueberspringt eine FLUECHTIGE Pruefung (ein
# Deploy), hier entsteht dagegen ein DAUERHAFTES Artefakt. Wer nur deployen will,
# soll nicht nebenbei eine Attestation erzeugen, die einen nie gefuehrten
# Nachweis behauptet. Damit das Artefakt nicht luegt, vermerkt write_verdict()
# den uebersprungenen Lauf im Payload.
SKIP_FRONTEND_GATE_VAR = "GZ_SKIP_FRONTEND_BROWSER_GATE"


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
    """Commit-getaggter Nachweis-Pfad: .claude/e2e_verified/<sha>.json — die
    einzige Pfad-Auflösung (Fix #1382, kein Rückfall mehr auf eine frühere
    Sammeldatei, s. Issue #1382). Existiert die Datei für den Referenz-Commit
    nicht, wird sie (nicht existent) zurückgegeben und von gate_check als
    'fehlt' behandelt.

    Issue #1130: Ohne ``sha`` wird die Attestation für den aktuellen HEAD
    adressiert; im Preflight übergibt gate_check den ZIEL-Commit statt HEAD.
    """
    return _e2e_paths.commit_e2e_path(_shared_repo_dir(), sha or _head_sha())


def _scope_diff_base(head: str | None = None) -> str:
    """Diff-Basis für die Scope-Erkennung (Issue #916).

    #1307 Scheibe B (AC-1): ``head`` wird vom Aufrufer durchgereicht, damit der
    Commit-Stand pro write_verdict()-Lauf genau EINMAL ermittelt wird. Ohne
    Argument (Direktaufruf) bleibt das Verhalten unverändert — der Stand wird
    dann hier selbst frisch geholt. Bewusst KEIN Zwischenspeicher über
    Aufrufgrenzen hinweg: tests/tdd/test_e2e_commit_namespacing.py:104-111 ruft
    write_verdict() zweimal im selben Prozess mit einem Commit-Wechsel dazwischen
    auf und verlangt je den eigenen Stand.

    Ist ein Gate-Marker vorhanden UND der SHA im Repo auflösbar → Marker-SHA
    (deckt ALLE Commits seit dem letzten erfolgreichen Gate-Lauf ab). Sonst
    (Erstlauf oder History-Rewrite) Fallback auf 'HEAD~1'.

    Adversary-Finding F002: zeigt der Marker exakt auf HEAD, wäre der Diff
    HEAD..HEAD und immer leer (fälschlich "docs-only") — z.B. bei einem
    Marker im alten #916-Format ohne gate_last_scope, der dadurch keinen
    Cache-Treffer liefert. In diesem Fall bewusst auf HEAD~1 ausweichen statt
    den Marker (Selbstreferenz vermeiden).

    henemm-infra#148 / #1428: Vorrang hat die vom Preflight (Issue #1130)
    tatsächlich verwendete Diff-Basis für genau diesen HEAD (den Ziel-Commit,
    der per `git reset --hard` gerade ausgecheckt wurde) — sofern hinterlegt
    und im Repo auflösbar. Das behebt den Widerspruch, dass der Preflight vor
    dem Reset gegen den alten Commit diffte, der reguläre Check danach aber
    gegen einen älteren Marker-Stand (der den zwischenzeitlich live gegangenen
    Backend-Commit fälschlich mit in den Diff zog). Es wird NUR die Basis
    übernommen, nie ein gecachter Scope-WERT — der Scope wird weiterhin immer
    frisch aus dem echten git-diff berechnet (F001 bleibt unberührt).
    """
    head = head if head is not None else _head_sha()
    preflight_base = _e2e_paths.read_preflight_base(_shared_repo_dir(), head)
    if preflight_base is not None:
        if _e2e_paths.commit_exists(preflight_base, _verified_repo_dir()):
            return preflight_base

    marker_sha = _e2e_paths.read_last_gate_scope(_shared_repo_dir())
    if marker_sha and marker_sha != head:
        if _e2e_paths.commit_exists(marker_sha, _verified_repo_dir()):
            return marker_sha
    return "HEAD~1"


def _detect_committed_scope(expected_commit: str | None = None,
                            head: str | None = None) -> str:
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
        # #1307 Scheibe B (AC-1): durchgereichten Stand nutzen, sonst genau hier
        # einmal frisch ermitteln und an _scope_diff_base() weitergeben. Bewusst
        # IN diesem Zweig statt am Funktionsanfang: der Preflight-Zweig unten
        # braucht HEAD nicht, und beim Beheben von "fragt zu oft" darf keine
        # zusaetzliche Abfrage entstehen.
        head = head if head is not None else _head_sha()
        cached = _e2e_paths.cached_scope_for_sha(_shared_repo_dir(), head)
        if cached is not None:
            return cached
        base, target = _scope_diff_base(head), "HEAD"
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

    # #1307 Scheibe B (AC-5): Datei-Diff ueber die gemeinsame Stelle statt eines
    # eigenen Subprozesses. Semantik unveraendert — _git_diff_names() liefert
    # None bei fehlgeschlagenem Diff (z.B. kein HEAD~1), was unten konservativ
    # als potenziell Telegram-relevant behandelt wird (Issue #1121, AC-5).
    changed = _e2e_paths._git_diff_names("HEAD~1", "HEAD", _verified_repo_dir())
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


def _frontend_browser_gate(scope: str, checked: list | None = None) -> int:
    """Issue #1558: Beruehrt der Aenderungssatz das Frontend, muessen die
    Kernseiten in einem echten Browser fehlerfrei laden — sonst kein Verdict.

    Konsumiert bewusst den bereits berechneten ``scope`` statt eines eigenen
    git-Diffs: das Telegram-Gate oben diefft fest HEAD~1..HEAD und uebersieht
    dadurch alles, was weiter zurueckliegt als der letzte Commit (AC-5).

    Fail-Grenze (AC-8): laesst sich das Gate-Modul SELBST nicht laden, laeuft
    der Aufruf mit Warnung durch — ein kaputtes Gate darf nie der Grund sein,
    dass niemand mehr ausliefert. Ist dagegen der NACHWEIS nicht erbringbar
    (Playwright fehlt, Staging tot, Anmeldung scheitert, Zugangsdaten fehlen,
    Konsolenfehler), blockiert es; das entscheidet das Gate-Modul selbst.

    ``checked`` nimmt — nur bei bestandenem Lauf — die geprueften Seiten auf.
    Returns: 0 = durchlassen, 1 = blocken.
    """
    if scope not in ("frontend-only", "full-stack"):
        return 0

    # Notausgang: exakt "1", damit er nicht versehentlich greift.
    if os.environ.get(SKIP_FRONTEND_GATE_VAR) == "1":
        _log(
            f"WARN: {SKIP_FRONTEND_GATE_VAR}=1 — der PFLICHT-Nachweis 'Browserlauf "
            "ueber die Kernseiten' wurde UEBERSPRUNGEN (Notfall-Override, #1558). "
            "Fuer diesen Stand ist NICHT belegt, dass das Frontend laedt; die "
            "Attestation wird entsprechend markiert.",
            stream=sys.stderr,
        )
        return 0

    import importlib.util

    try:
        spec = importlib.util.spec_from_file_location(
            "_e2e_frontend_browser_gate", str(FRONTEND_GATE_PATH)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:  # noqa: BLE001 — fail-soft NUR beim Laden des Gates
        _log(f"WARN: Browser-Gate e2e_frontend_browser_gate nicht ladbar ({exc}) — "
             "Frontend-Browserlauf uebersprungen.", stream=sys.stderr)
        return 0

    # Zugangsdaten gehoeren HIER nachgeladen, nicht in gate(): dort wuerde
    # os.environ.setdefault die Bedingung "Zugangsdaten fehlen" wieder aufheben
    # und damit unpruefbar machen.
    mod.load_validator_env()
    if mod.gate(scope, dict(os.environ)) != 0:
        # Den Notausgang HIER nennen, nicht nur in der Doku: wer ihn braucht,
        # sucht ihn genau in diesem Moment und findet ihn sonst nicht.
        _log(
            f"FEHLER: Scope '{scope}' beruehrt das Frontend, aber der Browserlauf "
            "ueber die Kernseiten wurde nicht bestanden (Issue #1558). Verdict "
            f"verweigert. Echter Notfall (Staging tot o.ae.): {SKIP_FRONTEND_GATE_VAR}=1 "
            "setzen — laut, geloggt, und die Attestation wird als ungeprueft markiert. "
            "GZ_SKIP_E2E_GATE wirkt hier NICHT (nur im Deploy-Check).",
            stream=sys.stderr,
        )
        return 1
    if checked is not None:
        checked.extend(mod.CORE_PAGES)
    return 0


def write_verdict(verdict: str, findings_path: Path, e2e_path: Path | None = None,
                  scope_override: str | None = None) -> int:
    """Mode A: Verdict in die commit-getaggte Nachweis-Datei schreiben."""
    sha = _head_sha()
    if e2e_path is None:
        e2e_path = _commit_e2e_path(sha)
    verdict = verdict.strip()
    if verdict.upper().startswith("BROKEN"):
        _log(f"BROKEN-Verdict erhalten: {verdict}")
        _log("Kein VERIFIED-Artefakt geschrieben — /e2e-verify erneut ausführen.", stream=sys.stderr)
        return 1
    # Issue #1327 (AC-5): Positiv-Whitelist statt reiner BROKEN-Abwehr. Frei
    # gewählte Verdict-Texte (z.B. "TEST") wurden bisher geschrieben und ließen
    # den Lese-Check (gate_check verlangt VERIFIED-Präfix) später hart scheitern.
    # Bewusst GROSS-/KLEINSCHREIBUNGS-GENAU auf dem bereits getrimmten String,
    # den auch payload["staging_verdict"] erhält: Schreib- und Lese-Pfad teilen
    # exakt dieselbe Bedingung. Sonst passiert "verified: …" die Prüfung, wird
    # geschrieben und vom Deploy-Gate später trotzdem abgelehnt (Fund F001).
    if not verdict.startswith(("VERIFIED", "AMBIGUOUS")):
        _log(f"Ungültiges Verdict-Präfix: {verdict!r}", stream=sys.stderr)
        _log("Erlaubt: 'VERIFIED: …' oder 'AMBIGUOUS: …' (exakt so geschrieben, "
             "BROKEN blockt). Attestation unverändert.", stream=sys.stderr)
        return 1

    if _telegram_live_gate() != 0:
        return 1

    try:
        raw_findings = json.loads(findings_path.read_text()) if findings_path.exists() else []
    except (json.JSONDecodeError, OSError) as exc:
        _log(f"Findings-Datei nicht lesbar: {exc}", stream=sys.stderr)
        return 1

    # Fix #1689 (AC-2/AC-3): hart pruefen, BEVOR irgendein Artefakt entsteht —
    # analog zur Verdict-Praefix-Pruefung oben (#1327). --findings-json muss
    # eine Liste sein, und jedes Element ein Dict; sonst kein Artefakt.
    if not isinstance(raw_findings, list):
        _log(
            f"--findings-json muss eine JSON-Liste sein, gefunden: "
            f"{type(raw_findings).__name__} statt list. Attestation unveraendert "
            "(kein Artefakt geschrieben).",
            stream=sys.stderr,
        )
        return 1
    findings, unusable_findings = _e2e_paths.partition_findings(raw_findings)
    if unusable_findings:
        first_idx = next(i for i, f in enumerate(raw_findings) if not isinstance(f, dict))
        _log(
            f"--findings-json enthaelt unverwertbare (Nicht-Dict-)Elemente: Index "
            f"{first_idx} hat Typ {type(raw_findings[first_idx]).__name__} statt dict "
            f"({len(unusable_findings)} von {len(raw_findings)} Elementen betroffen). "
            "Attestation unveraendert (kein Artefakt geschrieben).",
            stream=sys.stderr,
        )
        return 1

    # Issue #1327 (AC-3): Findings tragen ihren Urheber-Workflow, damit der
    # Merge unten eigene von fremden Einträgen unterscheiden kann.
    workflow = (
        os.environ.get("OPENSPEC_ACTIVE_WORKFLOW")
        or os.environ.get("GZ_ACTIVE_WORKFLOW")
        or "unknown"
    ).strip() or "unknown"
    findings = [{**f, "workflow": workflow} for f in findings]

    scope = scope_override or _detect_committed_scope(head=sha)
    # Issue #1558: NACH der Scope-Berechnung — nicht oben beim Telegram-Gate,
    # wo `scope` noch gar nicht existiert.
    frontend_pages: list[str] = []
    if _frontend_browser_gate(scope, frontend_pages) != 0:
        return 1
    payload = {
        "verified_commit": sha,
        "staging_verdict": verdict,
        "findings": findings,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "environment": "staging",
    }
    if frontend_pages:
        payload["frontend_pages_checked"] = frontend_pages
    elif scope in ("frontend-only", "full-stack"):
        # Das Artefakt darf einen nie gefuehrten Nachweis nicht verschweigen:
        # ohne diesen Vermerk sieht eine uebersprungene Attestation genauso aus
        # wie eine aus der Zeit vor dem Gate.
        payload["frontend_browser_gate"] = (
            f"UEBERSPRUNGEN via {SKIP_FRONTEND_GATE_VAR}=1"
            if os.environ.get(SKIP_FRONTEND_GATE_VAR) == "1"
            else "NICHT GELAUFEN (Gate-Modul nicht ladbar)"
        )
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
        # Fix #1689 (AC-8): ein valides, aber NICHT-Dict Top-Level-JSON wird wie
        # eine kaputte Attestation behandelt (isinstance-Guard VOR .get()) —
        # kein AttributeError, regulaeres Ueberschreiben bleibt moeglich.
        if isinstance(existing, dict) and existing.get("verified_commit") == sha:
            existing_findings = existing.get("findings") or []
            # Fix #1689 (AC-4): Nicht-Dict-Altlasten (z.B. aus einer frueheren
            # Objekt-statt-Liste-Fehlform, #1653/#1677) werden VOR dem
            # Workflow-Filter verworfen — jeder reguläre Folge-Schreibvorgang
            # heilt damit ein bereits verschmutztes Artefakt.
            existing_findings, existing_unusable = _e2e_paths.partition_findings(existing_findings)
            if existing_unusable:
                _log(
                    f"{len(existing_unusable)} unverwertbare (Nicht-Dict-)Altlast-"
                    "Eintraege beim Merge verworfen.",
                    stream=sys.stderr,
                )
            # Issue #1327 (AC-4): Einträge DIESES Workflows werden ersetzt statt
            # additiv angehängt — sonst überleben korrigierte Fassungen neben den
            # fehlerhaften und erzeugen dauerhaft False-FAILs. Fremde Workflows
            # und Altbestand ohne workflow-Feld bleiben unangetastet (#1197:
            # kein Evidenz-Verlust des Erstschreibers).
            kept = [
                f for f in existing_findings
                if not (isinstance(f, dict) and f.get("workflow") == workflow)
            ]
            # Der Inhalts-Dedup aus #1197 bleibt zusätzlich aktiv, aber NUR gegen
            # Altbestand OHNE workflow-Tag: dort verhindert er, dass jeder
            # Schreiber neben dem taglosen Eintrag eine inhaltsgleiche
            # Zweitfassung anhäuft (die Duplikat-Klasse aus #1327). Gegen FREMDE
            # getaggte Einträge wird NICHT dedupliziert — sonst verlöre ein
            # zweiter Workflow, der denselben Punkt eigenständig verifiziert hat,
            # lautlos seine Zuordnung und mit ihr sein Finding, sobald der
            # Erstschreiber sein Set neu schreibt (Fund F002).
            def _content_key(entry):
                if not isinstance(entry, dict):
                    return json.dumps(entry, sort_keys=True)
                return json.dumps(
                    {k: v for k, v in entry.items() if k != "workflow"},
                    sort_keys=True,
                )

            seen = {
                _content_key(f) for f in kept
                if not (isinstance(f, dict) and f.get("workflow"))
            }
            merged = list(kept)
            for f in findings:
                key = _content_key(f)
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


def gate_check(e2e_path: Path | None, scope_override: str | None,
               expected_commit: str | None = None) -> int:
    """Mode B: Gate-Check für deploy-gregor-prod.sh.

    Issue #1130: Ist ``expected_commit`` gesetzt (Deploy-Preflight VOR
    ``git reset --hard``), wird gegen diesen Ziel-Commit geprüft statt gegen
    HEAD — Attestations-Vergleich, Scope-Diff und Attestations-Pfad beziehen
    sich dann auf EXP. Der HEAD-basierte Scope-Marker wird im Preflight NICHT
    geschrieben (kein Cache-Poisoning eines noch nicht ausgerollten Zustands).
    Ohne das Flag ist das Verhalten unverändert.

    Fix #1382: ``expected_commit`` wird bei erfolgreicher Auflösung auf die
    volle, von git aufgelöste SHA normalisiert (AC-6) — Kurz-SHA/``origin/main``
    liefern damit denselben Pfad und dieselbe Meldung wie die volle SHA. Bei
    Blockade wird einer von fünf unterscheidbaren Gründen gemeldet (i)-(v),
    s. docs/specs/modules/fix_1382_deploy_gate_evidence.md.
    """
    if os.environ.get("GZ_SKIP_E2E_GATE") == "1":
        _log("WARN: GZ_SKIP_E2E_GATE=1 — Staging-Gate übersprungen (Notfall-Override).", stream=sys.stderr)
        return 0

    # Fix #1382 (Nachtrag): eine ausdruecklich uebergebene Nachweis-Datei
    # (--e2e-path) ist massgeblich. Passt ihr Inhalt nicht zum Zielstand, gibt
    # es KEINE Vorfahren-Relaxierung — sonst wuerde eine benannte
    # Nachweisquelle stillschweigend uebergangen. Muss VOR der Umwidmung von
    # e2e_path (Default-Pfad-Auflösung weiter unten) erfasst werden.
    explicit_path = e2e_path is not None

    preflight = expected_commit is not None
    # Issue #1130 / Adversary F001: Der Ziel-Commit ist im Preflight ungeprüfter
    # externer Input (Deploy-Script-Variable). Ist er leer oder nicht auflösbar
    # (Tippfehler, noch nicht gefetcht), scheitert der Scope-Diff still → früher
    # fälschlich "docs-only" → fail-open Exit 0 OHNE Attestations-Prüfung. Genau
    # das darf dieser Preflight nie: fail-closed VOR jeder Scope-/Skip-Logik.
    if preflight:
        # Bewusst eigenstaendig (AC-7, #1307 Scheibe B): `rev-parse --verify`
        # liefert die volle SHA auf stdout — das kann eine reine
        # Existenzpruefung (_e2e_paths.commit_exists) nicht, und genau die
        # volle SHA braucht die #1382-Normalisierung wenige Zeilen weiter unten.
        # Deshalb NICHT an die gemeinsame Stelle delegiert.
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
        # Fix #1382 (AC-6): die volle, aufgelöste SHA übernehmen statt des
        # rohen Arguments — sonst erzeugen Kurz-SHA/`origin/main` einen
        # Nachweis-Pfad, der nie existieren kann (schreibt wird immer mit der
        # vollen SHA benannt).
        expected_commit = resolved.stdout.strip()
        # henemm-infra#148 / #1428: Diff-BASIS (der alte, noch live laufende
        # Commit) fuer den Ziel-Commit hinterlegen -- kein Scope-Cache, siehe
        # _scope_diff_base(). Muss VOR der Scope-Berechnung stehen, damit ein
        # nachfolgender regulaerer --check (nach git reset --hard auf diesen
        # Ziel-Commit) dieselbe Basis wie der Preflight verwendet.
        _e2e_paths.write_preflight_base(_shared_repo_dir(), expected_commit, _head_sha())
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
        e2e_path = _commit_e2e_path(expected_commit)

    ref = expected_commit or _head_sha()

    data = None
    if e2e_path.exists():
        try:
            data = json.loads(e2e_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            _log(f"FEHLER: Nachweis-Datei {e2e_path} nicht lesbar: {exc}", stream=sys.stderr)
            return 1

    # Fix #1689 (AC-9): valides, aber NICHT-Dict Top-Level-JSON wird FAIL-CLOSED
    # geblockt — anders als der Merge-Lesepfad (weich), weil dies der
    # Exakt-Match-Zweig des echten Prod-Deploy-Gates ist. NICHT wie `data is
    # None` behandeln (das würde in die Ancestor-Relaxierung rutschen).
    if data is not None and not isinstance(data, dict):
        _log(
            f"FEHLER: Nachweis-Datei {e2e_path} enthält kein Dict auf oberster "
            f"Ebene (gefundener Typ: {type(data).__name__}) — Gate fail-closed "
            "blockiert.",
            stream=sys.stderr,
        )
        return 1

    verified_commit = data.get("verified_commit", "") if data is not None else ""

    # Issue #1197 / Fix #1382: Kein exakter <ref>.json-Treffer (Datei fehlt oder
    # trägt einen anderen verified_commit) → nächsten VERIFIED, nicht-stalen
    # Ancestor als Basis auflösen und NUR relaxieren, wenn ref dessen Nachfahre
    # ist UND der Zuwachs Basis..ref docs-only ist. Sonst fail-closed blocken
    # mit einer von fünf unterscheidbaren Meldungen (i)-(v).
    if verified_commit != ref:
        git_dir = _verified_repo_dir()
        # Ausdruecklich uebergebener Pfad ist massgeblich: keine
        # Vorfahren-Relaxierung, direkt zu den Fall-(i)/(v)-Meldungen unten.
        ancestor = None
        if not explicit_path:
            ancestor, _cdata = _e2e_paths._nearest_verified_ancestor(ref, git_dir, _shared_repo_dir())
        if ancestor is not None:
            # Bewusst eigenstaendig (AC-7, #1307 Scheibe B): einzige
            # Ancestor-Pruefung im Hook-Baum, kein Gegenstueck im gemeinsamen
            # Modul — deshalb NICHT an die gemeinsame Stelle delegiert.
            is_anc = subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, ref],
                capture_output=True, text=True, cwd=str(git_dir),
            )
            if is_anc.returncode == 0:
                if _e2e_paths._detect_scope_from_git_diff(ancestor, ref, git_dir) == "docs-only":
                    _log(
                        f"OK: Ancestor-Relaxierung (#1197): Basis {ancestor[:8]} VERIFIED, "
                        f"Zuwachs {ancestor[:8]}..{ref[:8]} docs-only — Staging-Gate bestanden."
                    )
                    if not preflight:
                        _e2e_paths.write_last_gate_scope(_shared_repo_dir(), _head_sha(), scope)
                    return 0
                # Fall (iv): Zielstand ist neuer als der zuletzt geprüfte Stand,
                # und der Zuwachs enthält Programmcode — vermutlich hat eine
                # parallele Sitzung dazwischen gepusht.
                changed = _e2e_paths._git_diff_names(ancestor, ref, git_dir) or []
                shown = ", ".join(changed[:5]) or "(Dateiliste nicht ermittelbar)"
                _log(
                    f"FEHLER: Zwischen dem zuletzt geprüften Stand ({ancestor[:8]}) und "
                    f"dem Zielstand ({ref[:8]}) wurde zusätzlicher Programmcode gepusht — "
                    "vermutlich hat eine parallele Sitzung deployt. Betroffene Datei(en): "
                    f"{shown}. Zuerst /e2e-verify für den neuen Zielstand ausführen, dann "
                    "erneut deployen.",
                    stream=sys.stderr,
                )
                return 1
        if data is None:
            # Fall (i): weder eine passende Nachweis-Datei noch ein Vorfahre.
            _log(
                f"FEHLER: Für den Zielstand {ref[:8]} liegt kein Nachweis vor — weder "
                "eine passende Verifikations-Datei noch ein geprüfter, aktueller "
                "Vorgänger-Stand. /e2e-verify ausführen, dann erneut deployen.",
                stream=sys.stderr,
            )
            return 1
        # Fall (v): eine Nachweis-Datei wurde gefunden, ihr Inhalt trägt aber
        # einen anderen Stand als den Dateinamen (beschädigt/manuell verändert)
        # — von Fall (i) klar unterscheidbar.
        _log(
            f"FEHLER: Für den Zielstand {ref[:8]} wurde eine Nachweis-Datei gefunden, "
            f"aber ihr Inhalt passt nicht zum Zielstand (trägt {verified_commit[:8] or 'einen leeren Stand'}). "
            "Vermutlich beschädigt oder manuell verändert. /e2e-verify erneut "
            "ausführen, dann erneut deployen.",
            stream=sys.stderr,
        )
        return 1

    # Exakt-Match: VERIFIED- und Staleness-Checks auf data.
    verdict = data.get("staging_verdict", "")
    if not verdict.startswith("VERIFIED"):
        # Fall (ii): Nachweis vorhanden, aber nicht VERIFIED.
        _log(
            f"FEHLER: Für den Zielstand {ref[:8]} liegt eine Verifikation vor, aber "
            f"ihr Ergebnis ist nicht VERIFIED (war: {verdict!r}). /e2e-verify erneut "
            "ausführen, dann erneut deployen.",
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
        # Fall (iii): Nachweis zu alt.
        _log(
            f"FEHLER: Die Verifikation für {ref[:8]} ist {age.total_seconds()/3600:.1f}h "
            f"alt (max {STALE_HOURS}h) — abgelaufen. /e2e-verify erneut ausführen, dann "
            "erneut deployen.",
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
    parser.add_argument("--e2e-path", help="Pfad zur commit-getaggten Nachweis-Datei (Override)")
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
