# Context: rework-1215-scheibe1-python-root

## Request Summary

Issue #1215, Scheibe 1 (von 3): Risikofreier Abbau von totem Code — Python-Legacy-Block in
`weather_metrics.py`, `coordinates.py`, sowie Repo-Root-Altlasten. Kein Produktions-Verhalten
darf sich ändern (reine Löschung/Umzug).

## Verifizierte Befunde (eigene Nachprüfung 2026-07-10, Worktree auf origin/main)

### Python-Dead-Code (per Commit löschbar)

| Fundstelle | Verifikation |
|-----------|--------------|
| `src/services/weather_metrics.py` Legacy-Block ab Zeile ~1199 (`HourlyCell` :1205, `CloudStatus` :1316, `build_hourly_cell`, `hourly_cell_to_compact` :493, Cloud-Status-Methoden mit Selbst-Imports :545/:588/:619) | repo-weiter Grep: **einzige** Datei mit diesen Symbolen ist `weather_metrics.py` selbst. Kommentar „Used by src/web/pages/compare.py" — `src/web/pages/` enthält nur noch `__pycache__` |
| `src/services/coordinates.py` (57 LoC) | einziger Importer: `tests/refactor/test_epic_129a_2_module_structure.py:29` (`test_coordinates_module`, prüft nur Existenz von `parse_dms_coordinates`) → Datei löschen + Test-Funktion entfernen |

### Root-Altlasten — WICHTIGE Abweichung vom Issue-Text

**Getrackt (per Commit löschbar/verschiebbar):**
- `red_839_fmt_val_thresholds.txt` → löschen
- `atoms.jsx` + `brand-kit.jsx` → nach `docs/design-requests/archive/` verschieben (Issue-Vorgabe);
  referenziert nur von `Soll-Mockups.html` (Root) und alten Handoff-Kopien unter `claude-code-handoff/`

**NICHT getrackt (existieren nur im Hauptrepo-Arbeitsverzeichnis, kein Commit möglich — lokales `rm` im Hauptrepo als separater Schritt):**
- `trip_report_old.py`, `red_654_drilldown_v2.txt`, `red_654_telegram_thunder_drilldown.txt`,
  `commit_hash.txt`, `staging_commit.txt`, `health.json` — kein Script in gregor_zwanzig oder
  henemm-infra liest/schreibt diese Namen (Grep leer)
- 12 Sicherungskopien `.claude/validator.env.{ac1test,ac1_test_bak,bak,bak2,bak3,external_backup,test,test_backup,validator_backup_1782205985,validator_backup_1782319787,validator_test_backup_1782289842}` — **behalten:** `validator.env` (aktiv) + `validator.env.example` (getrackt)

**Binaries — Issue-Befund überholt:**
- `gregor-api`, `gregor_zwanzig`, `server` sind **NICHT eingecheckt** — `.gitignore:80-82` deckt sie bereits ab. Die AC-Forderung „.gitignore deckt Binaries ab" ist bereits erfüllt (nur nachweisen).
- **GEFAHR:** `/home/hem/gregor_zwanzig/gregor-api` ist die **laufende Prod-Binary** (`systemctl cat gregor-api` → ExecStart zeigt direkt darauf; Build von heute). **Darf NICHT gelöscht werden.**
- `gregor_zwanzig` (Apr 15) und `server` (Mai 18) referenziert kein systemd-Unit und kein Script → lokal löschbar.

### Explizit NICHT in dieser Scheibe (nur dokumentieren)

- `aggregation.py` + `trip_forecast.py`: hängen am Legacy-CLI-Pfad (`src/app/cli.py:228`) mit
  abweichender Aggregations-Semantik — Abbau ist PO-Entscheidung (CLI-Zukunft), NICHT stillschweigend
  angleichen. Als Folge-Entscheidung im Issue dokumentieren.
- `compare_subscription.py` Alt-Pfad → eigenes Issue #1131
- Frontend (Scheibe 2) + Go `internal/compare/` (Scheibe 3) → eigene Workflows

## Existing Patterns

- Struktur-Tests unter `tests/refactor/` prüfen Modul-Existenz per `importlib` — bei Löschung von
  `coordinates.py` die betreffende Testfunktion mitlöschen (Test-Politik: veraltetes Verhalten → Test löschen)
- `docs/design-requests/` ist der etablierte Ort für Design-Artefakte (Claude-Design liest nur Repo)

## Dependencies

- Upstream: keine — gelöschte Symbole haben null externe Aufrufer
- Downstream: `docs/specs/compare_email.md` erwähnt `hourly_cell_to_compact` (Doku-Referenz, kein Code)

## Risks & Considerations

1. **Prod-Binary `gregor-api` nicht anfassen** (läuft live, systemd zeigt darauf)
2. Untrackte Hauptrepo-Dateien: Löschung ist NICHT commit-bar → separater dokumentierter
   Aufräum-Schritt im Hauptrepo nach dem Merge; Worktree-Session braucht dafür Freigabe des
   Session-Wächters (nur lesende Tools im Hauptrepo) → am Ende der Scheibe als Bash-`rm` mit
   expliziter Dateiliste (kein Glob auf `validator.env*`, sonst Treffer auf aktive Datei)
3. `weather_metrics.py` ist von 1325 auf ~1080 LoC zu kürzen (aggregate_stage bleibt) — Kern-Testsuite (deterministisch)
   muss grün bleiben; gezielte Tests: `tests/integration/test_segment_weather_metrics.py` u.a.
4. LoC-Delta ist negativ (Löschung) — 250-LoC-Limit unkritisch
