# Context: #1708 Scheibe C — tote Trip-Ablage archivieren und löschen

## Request Summary

Die tote `trips/`-Ablage (Alt-Pfad vor #1250 Scheibe 7a, seit Scheibe A/B produktivcodeseitig
tot) steht als Bestand noch an **drei** Datenwurzeln. Scheibe C sichert (tar.gz) und löscht sie
je Wurzel, mit einem Prod-Selftest-Wächter, der ein Wiederauftauchen meldet. Schließt #1708.

## Gemessener Ist-Stand (2026-08-17, vor jeder Änderung)

Das Issue nennt nur die Prod-Wurzel und "14 Dateien". Nachmessung ergibt drei Wurzeln mit
unterschiedlichem Zustand:

| Wurzel | Verzeichnisname | Zustand | Dateien |
|---|---|---|---|
| **Prod** `/var/lib/gregor/users/*/` | `trips.TOT-legacy-1250-nicht-lesen` | umbenannt 2026-08-10 (Sofortmaßnahme, reversibel) | **15** (4 Nutzer: default, henning, steffi, validator-issue110) |
| **Staging** `/var/lib/gregor-staging/users/*/` | `trips` (Originalname) | **nie markiert** | 1 Datei (`validator-issue110/staging-validator-rolling.json`) + ~34 leere Verzeichnisse (E2E-Testnutzer) |
| **Lokal** (Repo-Checkout) `data/users/*/trips/` | `trips` (Originalname, untracked) | **nie markiert** | 9 Dateien (`default`: 1, `validator-issue110`: 8) — je Worktree eigener Stand |

Prod-Dateiliste (mit Größe/mtime):
```
default/trips.TOT-legacy-1250-nicht-lesen/gr221-mallorca.json               12178  2026-07-15
validator-issue110/…/ortler-2025.json                                        709  2026-07-15
validator-issue110/…/dachstein-2023.json                                     491  2026-07-15
validator-issue110/…/rofan-2025.json                                         386  2026-07-15
validator-issue110/…/khw-402.json                                           1658  2026-07-15
validator-issue110/…/venediger-2024.json                                     818  2026-07-15
validator-issue110/…/stubai-2024.json                                       1129  2026-07-15
validator-issue110/…/gardasee-2024.json                                      613  2026-07-15
validator-issue110/…/zillertal-2025.json                                     383  2026-07-15
steffi/…/34ab4f37.json                                                     11143  2026-07-15
henning/…/5f534011.json.bak-datumsfix-20260628-201416                     25542  2026-06-24
henning/…/gr221-mallorca.json                                             13379  2026-07-15
henning/…/74de939c.json                                                   20440  2026-07-15
henning/…/5f534011.json                                                   27483  2026-08-10
henning/…/14f1aafd.json                                                   16517  2026-07-15
```

**Wichtig:** Staging- und lokale Verzeichnisse tragen den unauffälligen Originalnamen `trips/` —
nur Prod ist mit `.TOT-legacy-…` als tot markiert. Genau dort greift die Falle noch, die #1708
beschreibt: eine Sitzung, die auf Staging oder in einem Worktree schnell nachsieht, sieht ein
plausibel benanntes Verzeichnis.

## Related Files

| File | Relevance |
|------|-----------|
| `scripts/cleanup_1265_prod_testdata.py` | **Vorbild-Muster** für Scheibe C: `--root`/`--backup-dir`/`--execute`, Dry-Run-Default, tar.gz-Backup vor jeder Löschung, Idempotenz (zweiter Lauf → 0 Aktionen), Sanity-Check auf erwartete echte Konten vor dem Löschen |
| `scripts/cleanup_1133_testdata.py` | Zweites Vorbild, gleiche Bauart |
| `.claude/hooks/data_schema_backup.py` | Bestehende Backup-Konvention: `.backups/data-pre-rework-<ts>.tar.gz`, Retention 20 |
| `.claude/hooks/prod_selftest.py` | Post-Deploy-Selftest — Ort für den neuen Wächter (PO-Entscheid: Prod-Selftest, nicht Infra-Monitoring). `run_selftest()` hat vier Phasen (Commit-Attestation, Health, AC-Attestation, Bot-Menü); ein fünfter Filesystem-Check passt als weitere additive Phase analog Phase 4 (Bot-Menü-Check, additiv, kann `verdict = "FAIL"` setzen) |
| `docs/reference/operations_playbook.md` | Abschnitt "Testdaten-Cleanup" (#1133) und "Compare-Metrik-Auswahl" (#1373 S2 B) dokumentieren dasselbe Backup+Execute-Muster — hier ergänzen |
| `tests/test_trips_path_revival_guard.py` | Scheibe-A-Wächter — prüft **Quellcode** auf `"trips"`-Literale, keine Überschneidung mit Datenbestand. Bleibt unverändert |
| `tests/test_briefing_route_cutover.py` | Nutzt `tmp_path`, nicht das echte `data/users` des Repos — vom lokalen Löschen nicht betroffen |

## Existing Patterns

- **Backup-vor-Löschen ist Standard**, nicht neu zu erfinden: `cleanup_1265_prod_testdata.py`,
  `cleanup_1133_testdata.py`, `migrate_1244_null_lists.py`, `migrate_1373_compare_active_metrics_format.py`
  — alle: `--root <pfad> [--execute]`, Dry-Run meldet Kandidaten ohne zu schreiben, `--execute`
  schreibt zuerst `tar.gz` nach `.backups/`, dann erst die Löschung/Änderung. Exit 1 bei
  Backup-Fehlschlag oder fehlendem `--root`.
- **Sanity-Check vor Löschung**: `cleanup_1265` bricht ab (kein Backup, keine Löschung), wenn die
  vier echten Konten unter `--root` fehlen — Indiz für falsches Zielverzeichnis. Für Scheibe C
  sinnvoll übertragbar: vor dem Löschen prüfen, dass `briefings/` (der lebende Pfad) für jeden
  betroffenen Nutzer existiert — sonst fehlt die Gegenprobe, dass die toten Daten wirklich
  redundant sind.
- **Selftest-Erweiterung additiv**: Phase 4 (Bot-Menü-Check) in `prod_selftest.py` zeigt das
  Muster für einen zusätzlichen, additiven Check, der bei Fehlschlag `verdict = "FAIL"` setzt,
  ohne die bestehenden vier Phasen anzufassen.

## Dependencies

- **Upstream:** Scheibe A (`05086722`, Quellcode-Wächter) und Scheibe B1/B2 (`6962e880`,
  `5ab7c957`, Loader/Testschicht-Rückbau) — beide live. Ohne sie wäre Löschen der Daten
  gefährlich (noch aktive Schreiber). Jetzt: **null** Produktivaufrufer für `trips/`-Pfade.
- **Downstream:** keine — der Pfad ist tot, nichts liest ihn.
- **Betroffene Prozesse:** `deploy-gregor-prod.sh` (Schritt 4b ruft `prod_selftest.py` auf, läuft
  als User `hem`, NOPASSWD-sudo bestätigt) — der neue Filesystem-Check läuft im selben Kontext.

## Existing Specs

- `docs/specs/modules/fix_1708_a_trips_pfad_waechter.md` — Scheibe A, nennt "14 toten
  Produktivdateien" als offenen Punkt (jetzt widerlegt: 15, plus zwei weitere Wurzeln)
- `docs/context/fix-1708-waechter-tote-trip-ablage.md` — Ursprungs-Context

## Risks & Considerations

- **Irreversible Löschung in Produktion.** Das Backup muss vor der Löschung verifiziert
  existieren (nicht nur "geschrieben", sondern lesbar/entpackbar) — Lehre aus
  BUG-DATALOSS-GR221 (#102): kein Pre-Snapshot existierte, Recovery war Zufall.
- **Drei unterschiedliche Nutzer/Rechte-Kontexte**: Prod-Dateien gehören `hem`/`claude-gregor`
  (rws-Gruppenrechte, per `sudo` lesbar), Staging analog, lokal `hem` direkt. Das
  Cleanup-Script muss in allen drei Kontexten lauffähig sein — ggf. `sudo` für Prod/Staging.
- **Idempotenz**: ein zweiter Lauf nach erfolgreicher Löschung darf nicht fehlschlagen (Ordner
  existiert nicht mehr → 0 Aktionen, kein Fehler) — Konvention aus `cleanup_1265`.
- **Der neue Selftest-Wächter darf nicht fail-closed auf Nicht-Erreichbarkeit reagieren**, wenn
  `sudo find` aus irgendeinem Grund fehlschlägt (z. B. Rechte-Änderung) — sonst blockiert er
  Prod-Deploys aus einem unabhängigen Grund. Fehlerbehandlung analog Bot-Menü-Check
  (`SKIPPED` bei Nicht-Prüfbarkeit, `FAIL` nur bei echtem Fund).
- **Staging-Verzeichnis enthält ~34 leere `trips/`-Ordner** von E2E-Testnutzern (kein Inhalt,
  aber ebenfalls tot) — gehören mit ins Löschziel, sonst bleibt die Falle für zukünftige
  Staging-Sichtungen an ~34 Stellen stehen.

## Analysis

### Type
Feature (kein Bug — Aufräum-/Löschauftrag mit begleitendem Wächter)

### Bestätigt durch Explore-Agent
- **Kein Produktionscode** referenziert noch `users/<id>/trips` als Verzeichnis — die Treffer sind
  ausschließlich Kommentare (die die entfernte Funktion nur erwähnen) und Tests, die selbst
  temporäre `trips`-Ordner anlegen, um einen **Negativ-Nachweis** zu führen ("wird nicht mehr
  gelesen"). `src/services/preview_service.py:67-68` hat eine irreführend benannte Variable
  `trips_dir`, die aber auf den lebenden `briefings/`-Pfad zeigt — kein toter Pfad, kein Blocker,
  ggf. spätere Kür (nicht Teil dieser Scheibe).
- **Testmuster für Cleanup-Skripte** etabliert: `tests/tdd/test_prod_testdata_cleanup.py`,
  `tests/tdd/test_issue_1133_testdata_cleanup.py`, `tests/test_cleanup_admin_prod_purge.py` —
  alle testen `run_cleanup(users_root, backup_dir, execute=)` gegen `tmp_path`, decken Dry-Run
  (nichts geschrieben), Execute (Backup vor Löschung, Assertion auf `.tar.gz`), Idempotenz
  (zweiter Lauf: 0 Aktionen) und Sanity-Abbruch ab.
- **`prod_selftest.py`-Testort**: gemeinsamer Loader `_load_prod_selftest_module()` in
  `tests/tdd/conftest.py:122-127` (bewusst zentralisiert) — dort docken neue Tests für Phase 5 an.
  Zusätzlich Subprozess-Testmuster in `tests/tdd/test_prod_selftest_730.py:53`.
- **sudo-Konvention**: einziger Präzedenzfall `.claude/hooks/auto_restart_server.py:82`
  (`subprocess.run(["sudo", "systemctl", "restart", ...])`, kein sichtbarer Timeout). Kein
  dedizierter Helper im Repo.
- **`prod_selftest.py` wird nicht importiert von CI**, nur per `python3 .claude/hooks/prod_selftest.py`
  im Deploy-Ablauf (`.claude/commands/70-deploy.md`) und per `importlib.util.spec_from_file_location`
  in Tests (kein Package-Import, da unter `.claude/hooks/`, nicht `src/`/`api/`).

### Technischer Ansatz (Plan-Agent, übernommen)
- **EIN wiederverwendbares Script** (`scripts/cleanup_1708c_dead_trips.py`, `--root`), analog
  `cleanup_1265_prod_testdata.py`, aber **Muster-Liste** statt Einzel-Positivliste:
  Zielordnernamen `["trips", "trips.TOT-legacy-1250-nicht-lesen"]` je User, ein Lauf deckt beide
  Namen ab. Iteriert über `users_root.iterdir()`, löscht **nur den Unterordner**, nie
  `users/<id>/` selbst (Staging hat ~34 sonst leere User-Hüllen, die bestehen bleiben müssen).
- **Sanity-Check zweistufig**: (a) erwartete echte Accounts müssen unter `--root` existieren
  (Verwechslungsschutz falscher Pfad, wie im 1265-Vorbild), (b) mtime-Check: keine Datei in einem
  Zielordner darf neuer sein als der Cutover-Zeitpunkt (#1250 Scheibe 7a) — sonst Abbruch statt
  Löschung, als zweite Verteidigungslinie zusätzlich zum bereits durch Scheibe A/B abgesicherten
  Code-Pfad.
- **sudo bewusst NICHT im Script** — Script bleibt stdlib-only, wird von außen mit
  `sudo -n python3 scripts/cleanup_1708c_dead_trips.py --root ... --execute` aufgerufen (kein
  `uv run` unter sudo, PATH/venv-Risiko vermieden).
- **Backup-Default vom Vorbild übernehmen**: `users_root.parent / ".backups"` — landet bei Prod
  automatisch unter `/var/lib/gregor/.backups` (außerhalb Repo), bei Staging analog, lokal unter
  `data/.backups` im Worktree (gitignored). Nachprüfpunkt: Backup-Dateien nach sudo-Lauf ggf.
  root:root-Owner — Rechte nach dem Lauf kontrollieren.

### Kritischer Reihenfolge-Punkt (Plan-Agent)
`prod_selftest.py` läuft bei **jedem** Prod-Deploy (Pflichtschritt 4b). Eine scharfe Phase 5
("kein `trips`/`trips.TOT-…` mehr vorhanden") darf **nicht** im selben Deploy live gehen, der den
Cleanup-Code ausliefert — sonst blockiert der erste Selftest-Lauf genau diesen Deploy, weil die
Prod-Löschung zu dem Zeitpunkt noch nicht stattgefunden hat (Sync passiert vor der manuellen
Löschung). **Konsequenz für die Spec:** Cleanup gegen Prod ist ein **expliziter, dokumentierter
manueller Schritt unmittelbar vor** `deploy-gregor-prod.sh` — nicht automatisiert im Deploy-Ablauf
selbst (kein destruktives Datenskript in einem Hook). Reihenfolge: (a) PR mit Script + Tests +
Wächter-Code mergen, Staging validieren (dort auch der Staging-Cleanup ausführen); (b) vor dem
eigentlichen Prod-Deploy-Schritt manuell den Prod-Cleanup laufen lassen, Ergebnis verifizieren
(0 verbleibende Ordner); (c) erst danach `deploy-gregor-prod.sh` → Selftest mit scharfer Phase 5
läuft gegen bereits bereinigten Bestand.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/cleanup_1708c_dead_trips.py` | CREATE | Backup+Löschung, `--root`/`--backup-dir`/`--execute`, Muster-Liste, Sanity-Checks |
| `tests/test_cleanup_1708c_dead_trips.py` | CREATE | Kern-Tests gegen `tmp_path`: Dry-Run, Execute+Backup, Idempotenz, Sanity-Abbruch, beide Namensmuster |
| `.claude/hooks/prod_selftest.py` | MODIFY | Additive Phase 5: Filesystem-Check auf verbleibende `trips`/`trips.TOT-…`-Ordner unter `/var/lib/gregor/users/*/` |
| `tests/tdd/test_prod_selftest_1708c.py` (Name vorläufig) | CREATE | Test für Phase 5, angedockt an `_load_prod_selftest_module()` |
| `docs/reference/operations_playbook.md` | MODIFY (docs) | Kurzer Absatz: Cleanup-Ablauf + manueller Reihenfolge-Hinweis vor Prod-Deploy |

### Scope Assessment
- Files: 5 (2 neu Code + 2 neu Test + 1 Modify + 1 Doku)
- Estimated LoC: Script ~180-220, Kern-Test ~120-150, `prod_selftest.py`-Erweiterung ~30-50 + Test ~40-60 → **Kern-Summe ~230-280, knapp am 250er-LoC-Limit** — im Blick behalten, ggf. `loc_limit_override` nötig
- Risk Level: **HIGH** (irreversible Prod-Löschung), Mechanismus selbst aber Standard-Pattern (Low Unsicherheit)

### Dependencies
- Upstream: Scheibe A (`05086722`) + B1/B2 (`6962e880`, `5ab7c957`) — beide live, Voraussetzung erfüllt
- Downstream: keine
- Kein Codepfad ist von der Löschung betroffen (Explore-Agent bestätigt: 0 Produktivaufrufer)

### Open Questions
- [x] Reichweite: alle drei Wurzeln (PO-Entscheid)
- [x] Wächter-Ort: Prod-Selftest (PO-Entscheid)
- [ ] Manuelle Reihenfolge (Cleanup vor scharfer Selftest-Phase) — geht als AC in die Spec, keine weitere Rückfrage nötig
