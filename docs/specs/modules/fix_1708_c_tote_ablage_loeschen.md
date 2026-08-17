---
entity_id: fix_1708_c_tote_ablage_loeschen
type: feature
created: 2026-08-17
updated: 2026-08-17
status: draft
version: "1.1"
tags: [cleanup, issue-1708, trips-pfad, prod-selftest]
---

# Fix #1708 Scheibe C — tote Trip-Ablage archivieren und löschen

## Approval

- [ ] Approved

## Purpose

Der Alt-Pfad `users/<id>/trips/*.json` (seit #1250 Scheibe 7a, 2026-07-15, durch
`briefings/` abgelöst und seit Scheibe A/B produktivcodeseitig vollständig tot — 0
Leser/Schreiber) steht noch als **Datenbestand** an drei Wurzeln (Prod, Staging, lokal).
Scheibe C sichert (tar.gz) und löscht ihn je Wurzel über ein wiederverwendbares
Cleanup-Script, ergänzt einen additiven Prod-Selftest-Wächter gegen ein Wiederauftauchen
und schließt damit #1708.

## Source

- **File:** `scripts/cleanup_1708c_dead_trips.py` (neu — das Cleanup-Script)
- **File:** `.claude/hooks/prod_selftest.py` (Erweiterung — additive Phase 5)
- **Identifier:** `run_cleanup(users_root, backup_dir, execute=)` (Script-Kernfunktion,
  Vertrag analog `scripts/cleanup_1265_prod_testdata.py::run_cleanup`)
- **Identifier:** `run_selftest(...)` (Phase 5 wird dort additiv ergänzt, analog Phase 4
  `_check_bot_menu_prod()`)

Schicht: **Python-Core / Tooling** — beide Dateien liegen außerhalb von `src/`/`api/`
(Script unter `scripts/`, Hook unter `.claude/hooks/`), kein Frontend-, Go- oder
FastAPI-Domain-Code betroffen.

## Estimated Scope

- **LoC:** ~230–280 (Script ~180–220, Kern-Tests ~120–150, `prod_selftest.py`-Erweiterung
  ~30–50 + zugehöriger Test ~40–60) — knapp am 250er-LoC-Limit, ggf.
  `loc_limit_override` nötig
- **Files:** 5 (2 neu Code+Test-Script-Paar, 1 Modify Hook, 1 neu Test für Hook, 1 Modify
  Doku)
- **Effort:** high (Mechanismus ist Standard-Pattern, aber Risiko-Level HIGH wegen
  irreversibler Prod-Löschung und drei unterschiedlicher Rechte-Kontexte)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/cleanup_1265_prod_testdata.py` | Script (Vorbild) | Referenz-Muster: `--root`/`--backup-dir`/`--execute`, Dry-Run-Default, tar.gz-Backup vor Löschung, Sanity-Check auf erwartete echte Konten, Idempotenz |
| `scripts/cleanup_1133_testdata.py` | Script (Vorbild) | Zweites Referenz-Muster, gleiche Bauart |
| `.claude/hooks/data_schema_backup.py` | Hook | Bestehende Backup-Konvention (`.tar.gz` nach `.backups/`), auf die sich der Standard-Ablageort `users_root.parent / ".backups"` beruft |
| `.claude/hooks/prod_selftest.py::run_selftest` | Funktion | Ort der neuen additiven Phase 5, direkt nach Phase 4 (Bot-Menü-Check) |
| `tests/tdd/conftest.py::_load_prod_selftest_module` | Fixture | zentraler Loader, an den der neue Phase-5-Test andockt |
| Scheibe A (`05086722`) + B1/B2 (`6962e880`, `5ab7c957`) | Vorarbeit, live | Voraussetzung: null Produktivaufrufer für `trips/`-Pfade — ohne sie wäre Löschen der Daten gefährlich |

## Implementation Details

### Cleanup-Script (`scripts/cleanup_1708c_dead_trips.py`)

Ein einziges, wiederverwendbares Script für alle drei Wurzeln (Prod, Staging, lokal),
analog `cleanup_1265_prod_testdata.py`, aber mit **Muster-Liste** statt Einzel-User-
Positivliste, da die drei Wurzeln unterschiedliche Nutzerbestände haben:

- `TARGET_DIR_NAMES = ["trips", "trips.TOT-legacy-1250-nicht-lesen"]` — je iteriertem
  `users_root.iterdir()`-Eintrag (`users/<id>/`) wird geprüft, ob einer dieser beiden
  Namen als Unterordner existiert.
- Gelöscht wird **ausschließlich der gefundene Unterordner**, nie `users/<id>/` selbst
  (Staging hat ~34 sonst leere User-Hüllen, die bestehen bleiben müssen, auch wenn ihr
  `trips/`-Unterordner entfernt wird).
- CLI-Vertrag identisch zum Vorbild: `--root <pfad>` (Pflicht, kein Default wie beim
  1265-Vorbild, um Verwechslung auszuschließen), `--backup-dir <pfad>` (Default
  `users_root.parent / ".backups"`), `--execute` (ohne Flag: Dry-Run).
- **sudo bewusst nicht im Script** — stdlib-only (`argparse`, `shutil`, `tarfile`,
  `pathlib`), von außen mit `sudo -n python3 scripts/cleanup_1708c_dead_trips.py --root
  ... --execute` aufgerufen, wo Dateien anderem Owner gehören (Prod/Staging).

### Sanity-Check vor jeder Löschung (Abbruch) und Zeit-Warnung (informativ)

1. **Konten-Check (Abbruch):** eine Liste erwarteter echter Accounts (analog
   `REAL_ACCOUNTS` im 1265-Vorbild, für diesen Kontext parametrisierbar da die drei
   Wurzeln unterschiedliche Konten haben — mindestens `default` muss überall vorhanden
   sein) muss unter `--root` existieren. Fehlt eines, bricht der Lauf ab: kein Backup,
   keine Löschung, Fehlermeldung nennt den vermutlich falschen Pfad. Dies ist die
   einzige Prüfung mit Blockadewirkung.
2. **Zeit-Warnung (informativ, KEIN Abbruch):** Dateien innerhalb eines gefundenen
   Zielordners mit einer mtime nach dem Referenzdatum **2026-07-15** (#1250 Scheibe 7a,
   ADR-0023) werden gezählt und im Dry-Run-/Execute-Bericht als Warnzeile ausgegeben
   (`WARNUNG: N Datei(en) neuer als 2026-07-15 in <Zielordner> — erwarteter Fund, kein
   Blocker`). Der Lauf bricht dadurch **nicht** ab, Backup und Löschung laufen bei
   `--execute` regulär weiter, sofern der Konten-Check bestanden wurde.

   Ein harter Abbruch an dieser Stelle wurde geprüft und bewusst verworfen: die reale
   Prod-Datei `henning/trips.TOT-legacy-1250-nicht-lesen/5f534011.json` (mtime
   2026-08-10) wurde nachweislich zweimal von fehlgeleiteten Sitzungen beschrieben
   (2026-06-28 „Datumsfix", 2026-08-10 ~21:00 „13 Etappendaten verschoben"), **weil**
   sie fälschlich für den lebenden Pfad gehalten wurde — das ist genau die Fehlerklasse,
   die #1708 beschreibt, kein Indiz dafür, dass der Pfad tatsächlich noch lebt. Ein
   Abbruch-Check, der diesen Fund als „verdächtig, vielleicht doch live" wertet, würde
   den einzigen Lauf blockieren, für den das Script gebaut ist. Der eigentliche Schutz
   gegen „Pfad ist doch noch live" ist bereits durch Scheibe A+B erbracht (0
   Produktivaufrufer, per Explore-Agent bestätigt); die Zeit-Warnung liefert dem PO
   zusätzliche Sichtbarkeit, ist aber keine zweite Verteidigungslinie mit
   Blockadewirkung.

Der Konten-Check läuft vor dem Backup — ein Abbruch schreibt nichts. Die Zeit-Warnung
wird unabhängig davon berechnet und erscheint sowohl im Dry-Run- als auch im
Execute-Bericht, verhindert aber weder Backup noch Löschung.

### Backup-vor-Löschung

Bei `--execute` und mindestens einem geplanten Löschziel: zuerst `tar.gz`-Backup nach
`backup_dir / f"cleanup-1708c-<timestamp>.tar.gz"` (Inhalt: die betroffenen
`users/<id>/trips*`-Unterordner, nicht die gesamte `users_root`), danach erst
`shutil.rmtree()` je gefundenem Zielordner. Backup-Fehler (z. B. Schreibrechte) beendet
den Lauf mit Exit 1, ohne dass gelöscht wird.

### Idempotenz

Ein zweiter Lauf nach erfolgreicher Löschung findet keine `trips`/`trips.TOT-legacy-…`-
Unterordner mehr — `total_planned == 0`, kein Backup, keine Aktion, Exit 0. Kein Fehler
bei bereits bereinigtem Bestand.

### Prod-Selftest-Wächter — additive Phase 5

In `.claude/hooks/prod_selftest.py::run_selftest`, unmittelbar nach Phase 4
(Bot-Menü-Check, analoge Struktur): ein Filesystem-Check über
`sudo -n find /var/lib/gregor/users -maxdepth 2 -type d \( -name trips -o -name
'trips.TOT-legacy-*' \)`.

- **Fund** (mindestens ein Verzeichnis) → `verdict = "FAIL"`, Finding im Bericht.
- **Kein Fund** → `status = "PASS"`, kein Einfluss auf `verdict`.
- **Check selbst nicht ausführbar** (sudo-Fehler, `find` nicht verfügbar, Timeout) →
  `status = "SKIPPED"`, **kein** Einfluss auf `verdict` — fail-open bei
  Nicht-Prüfbarkeit, analog `_check_bot_menu_prod()` bei fehlendem Token. Ein
  unabhängiger Rechte-/Infra-Fehler darf keinen Prod-Deploy blockieren, der mit der
  eigentlichen Prüfung nichts zu tun hat.

### Reihenfolge — Wächter darf nicht im selben Deploy scharf gehen wie der Cleanup-Code

`prod_selftest.py` läuft bei **jedem** Prod-Deploy (Schritt 4b, Pflicht). Würde Phase 5
im selben Deploy live gehen, der das Cleanup-Script ausliefert, würde der erste
Selftest-Lauf genau diesen Deploy blockieren — die Prod-Löschung selbst ist ein
**manueller** Schritt, der zeitlich **nach** dem Code-Sync, aber **vor** dem Selftest-
Aufruf liegt, und zum Zeitpunkt des ersten Deploys naturgemäß noch nicht stattgefunden
hat.

Verbindliche Reihenfolge:

1. PR mit Script + Kern-Tests + Wächter-Code (Phase 5) mergen.
2. Staging validieren: dort den Cleanup-Lauf gegen `/var/lib/gregor-staging/users`
   ausführen (`--execute`), Ergebnis verifizieren.
3. **Vor** dem eigentlichen Prod-Deploy-Schritt (`deploy-gregor-prod.sh`): den
   Prod-Cleanup manuell laufen lassen (`sudo -n python3
   scripts/cleanup_1708c_dead_trips.py --root /var/lib/gregor/users --execute`),
   Ergebnis verifizieren (0 verbleibende Ordner).
4. Erst danach `deploy-gregor-prod.sh` ausführen — der darin laufende Selftest mit
   scharfer Phase 5 trifft auf bereits bereinigten Bestand und meldet PASS.

Diese Reihenfolge wird in `docs/reference/operations_playbook.md` dokumentiert (kurzer
Absatz, Verweis aus dem Cleanup-Abschnitt).

### Lokale Wurzel

`data/users/*/trips/` im aktuellen Worktree-Checkout wird mit demselben Script
bereinigt (`--root data/users --execute`), unabhängig von Prod/Staging — je Worktree
eigener Stand, keine Reihenfolge-Abhängigkeit zu Schritt 2/3.

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `scripts/cleanup_1708c_dead_trips.py` | CREATE | Backup+Löschung, `--root`/`--backup-dir`/`--execute`, Muster-Liste `["trips", "trips.TOT-legacy-1250-nicht-lesen"]`, Konten-Check (Abbruch) + Zeit-Warnung (informativ), Idempotenz |
| `tests/test_cleanup_1708c_dead_trips.py` | CREATE | Kern-Tests gegen `tmp_path`: Dry-Run (nichts geschrieben), Execute+Backup-Nachweis, Idempotenz, Sanity-Abbruch (Konten-Check), Zeit-Warnung ohne Abbruch, beide Namensmuster gleichzeitig in einem Root |
| `.claude/hooks/prod_selftest.py` | MODIFY | Additive Phase 5 nach Phase 4: `_check_dead_trips_prod()` + Verdrahtung in `run_selftest`, analog Bot-Menü-Check |
| `tests/tdd/test_prod_selftest_1708c_dead_trips_guard.py` | CREATE | Test für Phase 5, angedockt an `_load_prod_selftest_module()`: FAIL bei Fund, PASS bei keinem Fund, SKIPPED bei Nicht-Prüfbarkeit (kein Einfluss auf Gesamt-Verdict) |
| `docs/reference/operations_playbook.md` | MODIFY (docs) | Neuer Absatz im Cleanup-Abschnitt: Reihenfolge lokal → Staging → Prod-Cleanup manuell → erst dann Deploy mit scharfer Phase 5 |

## Expected Behavior

- **Input:** `python3 scripts/cleanup_1708c_dead_trips.py --root <pfad> [--backup-dir
  <pfad>] [--execute]`, ausgeführt gegen eine der drei Wurzeln (lokal direkt, Prod/
  Staging via `sudo -n`); nachgelagert `prod_selftest.py` als Teil von Schritt 4b des
  Deploy-Ablaufs.
- **Output:** Dry-Run listet gefundene `trips`/`trips.TOT-legacy-…`-Unterordner ohne zu
  schreiben, inklusive etwaiger Zeit-Warnzeilen. `--execute` schreibt zuerst ein
  lesbares/entpackbares `tar.gz`-Backup, löscht danach exakt diese Unterordner (nie
  `users/<id>/` selbst), meldet Backup-Pfad + Aktionszahl + Zeit-Warnungen. Fehlt ein
  erwartetes echtes Konto, bricht der Lauf ohne Backup/Löschung ab; eine Zeit-Warnung
  allein bricht **nicht** ab. Ein zweiter Lauf nach erfolgreicher Löschung meldet 0
  Aktionen. `prod_selftest.py` Phase 5 meldet nach dem Prod-Cleanup PASS; vor dem
  Cleanup (oder bei einem späteren Wiederauftauchen) FAIL; bei technischer
  Nicht-Prüfbarkeit SKIPPED ohne Einfluss auf das Gesamt-Verdict.
- **Side effects:** unwiderrufliche Löschung von Verzeichnissen unter den drei
  Datenwurzeln (abgesichert durch vorheriges Backup); keine Änderung an
  Produktivverhalten, da der Pfad seit Scheibe A/B keinen Leser/Schreiber mehr hat.

## Acceptance Criteria

- **AC-1:** Given ein `users/<id>/`-Verzeichnis enthält entweder einen Unterordner
  `trips` oder `trips.TOT-legacy-1250-nicht-lesen` / When das Cleanup-Script gegen die
  Wurzel läuft / Then erkennt es beide Namensmuster gleichwertig als Löschziel, ohne
  eine Einzel-User-Positivliste zu benötigen.
  - Test: ein `tmp_path`-Root mit einem User im Namensmuster A und einem zweiten im
    Namensmuster B — beide werden im Dry-Run-Ergebnis als Kandidaten gelistet.

- **AC-2:** Given ein User-Verzeichnis `users/<id>/` enthält neben `trips/` weitere
  Unterordner (z. B. `briefings/`) / When der Cleanup-Lauf mit `--execute` läuft / Then
  wird ausschließlich der `trips`- bzw. `trips.TOT-legacy-…`-Unterordner entfernt,
  `users/<id>/` selbst und alle Geschwister-Unterordner bleiben unangetastet.
  - Test: nach `--execute` existiert `users/<id>/` weiterhin und `users/<id>/briefings/`
    ist unverändert vorhanden, nur der Trips-Unterordner ist verschwunden.

- **AC-3:** Given kein `--execute`-Flag wird übergeben / When das Script gegen einen
  Root mit Löschkandidaten läuft / Then wird nichts geschrieben oder gelöscht (weder
  Backup noch Zielordner); erst mit `--execute` wird zuerst ein `tar.gz`-Backup
  geschrieben und danach gelöscht.
  - Test: Dry-Run-Lauf gefolgt von Dateisystem-Prüfung (Zielordner und `.backups/`
    unverändert/nicht vorhanden); Execute-Lauf gefolgt von Prüfung, dass das
    `.tar.gz` vor der Löschung existiert und mit `tarfile.open()` lesbar ist.

- **AC-4:** Given unter `--root` fehlt mindestens eines der erwarteten echten Konten /
  When ein Lauf mit `--execute` gestartet wird / Then bricht der Lauf ohne Backup und
  ohne Löschung ab, mit einer Fehlermeldung, die auf ein vermutlich falsches
  `--root` hinweist.
  - Test: `tmp_path`-Root ohne das erwartete Konto `default` — nach dem Lauf existiert
    kein `.tar.gz`, kein Zielordner wurde entfernt, Exit-Code ≠ 0.

- **AC-5:** Given ein Zielordner unter `--root` enthält eine Datei mit einer mtime nach
  dem Referenzdatum 2026-07-15 (#1250 Scheibe 7a) — wie real bei
  `henning/trips.TOT-legacy-1250-nicht-lesen/5f534011.json` (mtime 2026-08-10) — / When
  ein Lauf (Dry-Run oder `--execute`) startet / Then wird die Datei als Warnzeile im
  Bericht ausgegeben, der Lauf bricht dadurch **nicht** ab und löscht bei `--execute`
  regulär weiter, sofern der Konten-Check aus AC-4 bestanden wurde. Ein harter Abbruch
  an dieser Stelle würde den einzigen für dieses Script vorgesehenen Prod-Lauf
  fälschlich blockieren.
  - Test: `tmp_path`-Root mit einer künstlich auf ein Datum nach 2026-07-15 gesetzten
    mtime in einer Datei innerhalb eines Zielordners, Konten-Check besteht — Lauf mit
    `--execute` schreibt ein Backup und löscht den Zielordner (`actions > 0`), das
    Ergebnis-Dict enthält eine Warnliste mit genau dieser Datei.

- **AC-6:** Given ein Cleanup-Lauf mit `--execute` hat einen Zielordner bereits
  erfolgreich entfernt / When das Script ein zweites Mal mit denselben Argumenten
  läuft / Then werden 0 Aktionen gemeldet, kein neues Backup geschrieben, kein Fehler
  ausgelöst.
  - Test: zwei aufeinanderfolgende `run_cleanup(..., execute=True)`-Aufrufe gegen
    denselben `tmp_path`-Root; der zweite Aufruf liefert `actions == 0` und
    `backup_path is None`.

- **AC-7:** Given das Cleanup-Script ist als reines stdlib-Programm implementiert /
  When es mit `sudo -n python3 scripts/cleanup_1708c_dead_trips.py --root ... --execute`
  gegen Prod oder Staging aufgerufen wird / Then läuft es ohne `uv run` und ohne
  venv-Abhängigkeit durch (kein `import` außerhalb der Standardbibliothek).
  - Test: statische Prüfung der Imports in `scripts/cleanup_1708c_dead_trips.py` gegen
    eine Liste erlaubter stdlib-Module (kein `requests`, kein Projekt-internes Paket).

- **AC-8:** Given `.claude/hooks/prod_selftest.py::run_selftest` durchläuft die
  bestehenden vier Phasen / When eine neue additive Phase 5 (Filesystem-Check auf
  verbleibende `trips`/`trips.TOT-legacy-…`-Ordner unter `/var/lib/gregor/users/*/`)
  ergänzt wird / Then setzt ein Fund `verdict = "FAIL"`, kein Fund lässt das
  Gesamt-Verdict unverändert (analog zum bestehenden Bot-Menü-Check in Phase 4), und
  Nicht-Prüfbarkeit (`sudo`/`find`-Fehler) meldet `status = "SKIPPED"` ohne
  Verdict-Einfluss.
  - Test: drei Fälle über `_load_prod_selftest_module()` — gemocktes `find` liefert
    einen Treffer (Verdict wird zu `FAIL`), liefert keinen Treffer (Verdict
    unverändert), schlägt mit Nicht-Null-Exit fehl (Status `SKIPPED`, Verdict
    unverändert).

- **AC-9:** Given die Prod-Löschung muss zeitlich vor dem ersten Deploy mit scharfer
  Phase 5 liegen, weil `prod_selftest.py` bei jedem Prod-Deploy läuft und der
  Code-Sync vor jeder manuellen Aktion passiert / When der Liefer-Ablauf für Scheibe C
  durchgeführt wird / Then folgt er der Reihenfolge: (1) PR mergen inkl. Phase-5-Code,
  (2) Staging-Cleanup ausführen und verifizieren, (3) Prod-Cleanup **manuell** vor
  `deploy-gregor-prod.sh` ausführen und verifizieren (0 verbleibende Ordner), (4) erst
  danach `deploy-gregor-prod.sh` ausführen, dessen Selftest-Lauf mit scharfer Phase 5
  gegen bereits bereinigten Bestand PASS meldet.
  - Test: kein automatisierter Testnachweis möglich (Ablauf-Disziplin, keine
    Code-Zusicherung) — Nachweis über `docs/reference/operations_playbook.md`
    (dokumentierter Absatz, AC-10) plus manuelle Bestätigung im Deploy-Protokoll
    (`docs/artifacts/<workflow>/prod-selftest.md` zeigt PASS für Phase 5 nach
    Schritt 3).

- **AC-10:** Given es gibt bisher keine dokumentierte Reihenfolge für Cleanup-Scripte
  mit begleitendem Selftest-Wächter / When Scheibe C abgeschlossen ist / Then enthält
  `docs/reference/operations_playbook.md` einen Absatz, der die Reihenfolge lokal →
  Staging → Prod-Cleanup (manuell, vor Deploy) → Deploy mit scharfer Phase 5 explizit
  beschreibt.
  - Test: `docs/reference/operations_playbook.md` enthält nach der Änderung einen
    Abschnitt, der auf `scripts/cleanup_1708c_dead_trips.py` verweist und die vier
    Schritte in dieser Reihenfolge nennt (Doku-Nachweis, `# doc-compliance-test`
    zulässig für den reinen Vorhandensein-Check).

## Known Limitations

- **Prod-Cleanup ist ein manueller, nicht automatisierter Schritt** (siehe AC-9) —
  bewusst kein destruktives Datenskript in einem Hook oder Deploy-Ablauf. Ein
  vergessener manueller Schritt lässt Phase 5 einmalig FAIL melden; das ist beabsichtigt
  (Sicherheitsnetz, kein Bug).
- **Zeit-Warnung ist informativ, kein Blocker** (siehe AC-5) — geprüft am realen
  Prod-Bestand: `henning/trips.TOT-legacy-1250-nicht-lesen/5f534011.json` hat mtime
  2026-08-10 (zweimal von fehlgeleiteten Sitzungen beschrieben — 2026-06-28
  „Datumsfix", 2026-08-10 ~21:00 „13 Etappendaten verschoben" — WEIL der Pfad
  fälschlich für lebend gehalten wurde; exakt die Wirkung, die #1708 beschreibt). Ein
  harter Abbruch an dieser Stelle hätte den einzigen für dieses Script vorgesehenen
  Prod-Lauf blockiert. Der eigentliche Schutz gegen „Pfad ist doch noch live" bleibt
  der Konten-Check (AC-4) plus die durch Scheibe A+B bereits bestätigte
  Code-Pfad-Schließung (0 Produktivaufrufer).
- **Staging enthält ~34 leere `trips/`-Ordner** von E2E-Testnutzern (kein Inhalt) —
  werden vom selben Lauf mit entfernt, sind aber im Dry-Run-Bericht nicht separat von
  gefüllten Ordnern unterschieden (beide erscheinen als Löschkandidat).
- **Referenzdatum 2026-07-15 ist hart im Script verankert** (Zeit-Warnung) — sollte
  #1250 rückwirkend korrigiert werden müssen, ist das eine bewusste Code-Änderung, kein
  Konfigurationswert. Da die Warnung nicht blockiert, hat eine falsche Referenz keine
  betriebliche Auswirkung, nur eine ungenaue Warnmeldung.
- **Backup-Retention nicht Teil dieser Scheibe** — anders als `data_schema_backup.py`
  (Retention 20) rotiert `cleanup_1708c_dead_trips.py` seine Backups nicht automatisch;
  das folgt dem Vorbild `cleanup_1265_prod_testdata.py`, das ebenfalls keine Rotation
  hat.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es wird keine Grundsatzentscheidung geändert oder neu getroffen.
  ADR-0023 (Cutover `trips/` → `briefings/`) wird zu Ende geführt — Scheibe C entfernt
  lediglich den letzten toten Datenbestand am bereits abgelösten Pfad. Der
  Selftest-Wächter folgt dem bestehenden additiven Phasen-Muster in
  `prod_selftest.py`, keine neue Architekturentscheidung.

## Changelog

- 2026-08-17: Initial spec created (#1708 Scheibe C, letzte Scheibe, schließt das Issue)
- 2026-08-17: AC-5 von hartem Abbruch auf informative Zeit-Warnung umgebaut (Team-Lead-
  Befund: die reale Prod-Datei `henning/…/5f534011.json` (mtime 2026-08-10) hätte den
  einzigen für dieses Script vorgesehenen Prod-Lauf blockiert). Konten-Check (AC-4)
  bleibt die einzige Prüfung mit Abbruch-Wirkung.
