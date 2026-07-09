# Operations-Playbook — ausgelagerte Mechanik

Diese Datei bündelt die **detaillierte Mechanik** von Abläufen, deren *Prinzip* in
`CLAUDE.md` steht. `CLAUDE.md` bleibt schlank (Prinzip + Verweis), die Schritt-für-Schritt-
Details stehen hier — bei Bedarf gezielt nachlesen.

---

## E2E-Verifikation (`/e2e-verify`) — Detailablauf

Die echte "funktioniert es wirklich"-Verifikation läuft **nach** dem Push gegen die
Staging-Umgebung (`https://staging.gregor20.henemm.com`) — **nie** durch einen lokalen
Neustart des Live-Servers (auf dieser Maschine = Produktion). Siehe Issue #339.

**Gesamtablauf:** `git push origin main` → ~5 Min Staging-Auto-Deploy abwarten →
`/e2e-verify` (gegen Staging) → `deploy-gregor-prod.sh` → Post-Deploy-Selftest (Issue #564) → Issue close.

**Schritte in `/e2e-verify`:**

1. Smoke gegen Staging (`/` + `/api/health`)
2. Scope bestimmen (frontend-only vs. backend/full-stack)
3. frontend-only → `staging-validator` Agent prüft alle ACs aus der Spec via Playwright; schreibt `e2e_verified.json` mit `verified_commit` + `staging_verdict`
4. backend/full-stack → Test-Trip auf Staging, Mail nur an `gregor-test@henemm.com`, IMAP-Prüfung
5. Nachweis in `.claude/e2e_verified.json` mit `verified_commit` (HEAD-SHA), `staging_verdict` und strukturierten Findings pro AC

Basis-URL für Browser-Checks via `GZ_SVELTE_BASE` (Default Staging):
```bash
GZ_SVELTE_BASE=https://staging.gregor20.henemm.com \
  uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --url "/"
```

`deploy-gregor-prod.sh` liest `e2e_verified.json` und blockiert den Prod-Deploy als Hard Gate,
wenn `verified_commit` nicht dem aktuellen HEAD entspricht oder `staging_verdict` nicht mit
`VERIFIED` beginnt (Issue #521).

---

## Post-Deploy-Selftest (Issue #564) — Detailablauf

Nach jedem Prod-Deploy erfolgt eine automatische Nachverifikation gegen Produktion — ohne
Playwright (kein Risiko für echte Sessions), stattdessen via Commit-Attestation, Health-Check
und parallele HTTP-Probes auf alle aus der Staging-Verifikation bekannten AC-Pfade.

**Ablauf (integriert in `/7-deploy`):**

1. Commit-Attestation: `git HEAD` muss mit `e2e_verified.json[verified_commit]` übereinstimmen
2. Health-Check: `https://gregor20.henemm.com/api/health` muss HTTP 200 + `status=ok` antworten
3. AC-Attestation: pro Staging-Finding (max 5 parallel) HTTP GET auf entsprechende Prod-URL (erwartet 200 oder 302)
4. Bericht: Markdown-Tabelle in `docs/artifacts/<workflow>/prod-selftest.md` mit pro-AC-Status
5. Exit-Code: 0 = alle ACs bestätigt (PASS) oder alle ACs übersprungen (docs-only); 1 = Mismatch/Fehler

**Verdict-Ableitung:**

- **PASS:** alle PASS-Findings bestätigen sich in Produktion
- **PARTIAL:** mind. ein PASS-Finding fehlt oder ist unerreichbar in Produktion
- **FAIL:** Commit-Mismatch oder Health unreachable
- **SKIP:** `e2e_verified.json` nicht vorhanden (docs-only Deploy)

**Schutzwirkung:** Issue-Close erfolgt nur bei Exit 0. Bei PARTIAL/FAIL wird der Bericht
untersucht und ggf. Rollback eingeleitet, bevor das Issue geschlossen wird. Verhindert, dass
Issues geschlossen werden, obwohl der Deploy still fehlschlug oder der falsche Code-Stand
deployed wurde. Siehe Spec Issue #564 für technische Details.

---

## Post-Push-Workflow — Detailablauf

**Nach jedem `git push origin main`** in dieser Reihenfolge:

| Schritt | Was | Wie |
|---|---|---|
| 1 | Push | `git push origin main` |
| 2 | Auto-Deploy auf Staging abwarten (~5 Min) | Cron `*/5` ruft `auto-deploy-gregor-staging.sh` |
| 3 | Staging-Validierung | siehe Definition unten |
| 4 | Prod-Deploy | `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` |
| 4b | Post-Deploy-Selftest | `python3 .claude/hooks/prod_selftest.py` (Commit/Health/AC-Attestation) — nur Exit 0 fährt weiter |
| 5 | Issue schließen | `gh issue close <N>` — nur wenn 4b Exit 0 |

`systemctl restart` allein **reicht nie** — `deploy-gregor-prod.sh` macht `flock-Lock → hart
auf origin/main syncen (Daten unberührt, WIP gesichert) → Go-Binary bauen → Frontend bauen →
alle 3 Services restarten → Smoke-Test`. Ohne diesen vollen Lauf entsteht Code-Drift, den
`check-gregor20.sh` als BetterStack-Alert meldet (siehe Issue #113). Das Script ist
**parallel-session-sicher**: es blockiert nicht mehr bei „dirty" Arbeitsbaum und serialisiert
gleichzeitige Deploys über `flock`. Schritt 4 darf daher aus jeder Session jederzeit laufen.

### Was zählt als „Staging-validiert"?

Mindestens diese Checks gegen `https://staging.gregor20.henemm.com`:
- HTTP-Smoke: `/` antwortet `200` oder `302`, `/api/health` antwortet `200`
- Eine geänderte Funktion manuell durchgeklickt (oder via Playwright für UI-Features)
- Bei Mail-Änderungen: Test-Mail aus dem Scheduler triggern und IMAP-Verifikation
- Bei Scheduler-Änderungen: `last_run`-Status im Endpoint geprüft

### Ausnahme: Reine Doku-/Tooling-Änderungen

Wenn der Push **ausschließlich** `.md`-Dateien, `docs/`, `.claude/`-Inhalte (Hooks/Agents/
Commands), `.gitignore` o. ä. verändert hat — **keinen Code in `src/`, `api/`, `internal/`,
`frontend/`, `cmd/`** — dann:
- Schritt 3 (Staging-Validierung) entfällt
- Schritt 4 (Prod-Deploy) entfällt, **wenn** der Code-Drift-Monitor (`check-gregor20.sh`)
  noch keinen Alert auslöst (Drift-Schwelle > 1h gegenüber `mtime(gregor-api)`)

Im Zweifel: trotzdem deployen, dann ist der Drift-Monitor auf jeden Fall ruhig.

---

## Parallele Sessions — Detailablauf

Für Parallelarbeit eine isolierte Arbeitskopie anlegen:

```bash
bash .claude/tools/gz-workspace new <name>   # isolierter Klon unter $GZ_WS_ROOT (Default /home/hem/gz-workspaces) auf Branch ws/<name>
bash .claude/tools/gz-workspace list         # alle Workspaces mit Branch + uncommitted-Zähler
bash .claude/tools/gz-workspace clean <name> # entfernen (nur wenn sauber; --force erzwingt)
```

Danach `cd` in den Workspace und dort eine NEUE Claude-Session starten. Für Frontend-Arbeit
dort `cd frontend && npm ci`. Jeder Workspace ist voll isoliert (eigenes `.git`/Index, eigene
Dateien, eigener Workflow-State); die Klon-Objekte sind gehardlinkt (platzsparend). Hauptrepo
und andere Workspaces bleiben unberührt.

**Selbst-Isolierung (automatisch):** Erkennt der Session-Wächter eine zweite Sitzung im selben
Ordner, ruft Claude unaufgefordert `EnterWorktree` auf und arbeitet in der isolierten Kopie
weiter — kein Beenden oder Neustart nötig, der Nutzer muss nichts tun.

### Abschluss einer parallelen Session — NIE „ich warte auf die andere Session"

Jede Session liefert **unabhängig** aus. Kein Warten aufeinander, keine Koordination über den
geteilten Baum. Der Integrationspunkt ist `origin/main`, nicht der lokale Ordner:

1. **Isoliert arbeiten** (Workspace/Worktree) — erzwingt der Session-Wächter ohnehin.
2. **Grün?** Im eigenen Branch committen, dann `git fetch origin && git rebase origin/main`,
   dann nach `main` pushen. Git serialisiert gleichzeitige Pushes selbst; bei Ablehnung erneut
   rebasen und pushen.
3. **Staging** aktualisiert sich automatisch (~5 Min, eigener Klon) → gegen Staging validieren.
4. **Production ausliefern:** `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` —
   **aus jeder Session jederzeit gefahrlos.** Ein `flock` serialisiert gleichzeitige Deploys
   (zweiter Aufruf wartet kurz und liefert dann den aktuellen `origin/main`-Stand). Das Script
   hängt **nicht mehr** am Zustand des geteilten Arbeitsbaums.

**Die eine Regel, die das sicher macht:** Nach `main` wird nur Grünes (staging-validiert)
gepusht — `main` ist immer auslieferbar. Dann darf ein Deploy auch frisch gepushte Arbeit einer
anderen Session mitnehmen.

**Verboten:** Ein Deploy aufschieben, „bis der gemeinsame Ordner sauber ist" oder „bis die
andere Session fertig ist". Diese Pattsituation existiert nicht mehr — der Deploy bringt den
Code hart auf `origin/main` (untracked Live-Daten unberührt, echte uncommittete WIP wird vorher
als stash-Commit + `deploy-safety/*`-Tag gesichert).

---

## Daten-Schema-Reworks — Anti-Pattern-Codebeispiele

Prinzip (steht in `CLAUDE.md`): **Read-Modify-Write mit Merge — bestehendes Objekt laden, nur
explizit veränderte Felder überschreiben, Rest erhalten.** Niemals Replace.

**Anti-Pattern (verboten):**

```python
# Edit-Handler baut neues Objekt aus UI-State und ueberschreibt Persistenz
updated = Trip(id=tid, name=name_input.value, stages=ui_stages)
save_trip(updated)  # Felder die UI nicht kennt sind weg!
```

```go
// Backend Replace statt Merge
var trip model.Trip
json.Decode(r.Body, &trip)
store.SaveTrip(trip)  // existing.aggregation, .display_config etc. weg!
```

Hintergrund: BUG-DATALOSS-GR221 (Issue #102). Bei einem früheren Refactor gingen 3 von 4
Stages des GR221-Trips verloren — das Recovery war nur möglich, weil GPX-Dateien zufällig in
einem Stash überlebt haben.

**Pflicht-Workflow im Detail:**

1. **Pre-Snapshot:** Hook `data_schema_backup.py` erstellt automatisch ein tar.gz von
   `data/users/` nach `.backups/data-pre-rework-<ts>.tar.gz` bevor eine Schema-Datei editiert
   wird (Retention: 20 Stück).
2. **Migration mit Test:** Bei Feldumbenennung/-removal: Migration-Skript schreiben +
   Roundtrip-Test (load alt → migrate → load neu → assert keine Daten-Diff)
3. **Post-Verifikation:** Nach Deploy alle Trips/Locations/Subscriptions im Frontend laden,
   Stage-/Waypoint-Counts gegen Pre-Snapshot vergleichen
4. **Bei Datenverlust:** Sofortiges Rollback aus `.backups/`, Root-Cause in
   `docs/project/known_issues.md` dokumentieren

---

## Testdaten-Cleanup (`data/users`) — Detailablauf (#1133)

Einmaliges Ops-Script gegen Test-Residuen, die vor dem Fix in #1133
(`get_data_dir()` respektierte `_DATA_ROOT`/`GZ_DATA_DIR` nicht) in den echten
`data/users/`-Baum geschrieben wurden. Läuft **pro Host** (Prod, Staging),
als User `claude-gregor`:

```bash
uv run python3 scripts/cleanup_1133_testdata.py            # Dry-Run (Default): nur Löschplan
uv run python3 scripts/cleanup_1133_testdata.py --execute   # führt Backup + Löschung aus
```

**Immer zuerst den Dry-Run lesen**, bevor `--execute` läuft. Das Script ist
idempotent (bereits gelöschte Pfade werden übersprungen, kein Fehler bei
wiederholtem Lauf).

**Positivliste (bleibt unangetastet):**
- Prod: `admin`, `default`, `henning`, `steffi`
- Staging: `default`

**Backup:** tar.gz des kompletten Vor-Zustands unter `.backups/` vor jeder
Löschung, ohne Retention-Limit (dauerhaft aufbewahrt).

Details (In-User-Musterbereinigung, Root-Cause-Fix, Adversary-Verlauf):
Spec `docs/specs/modules/issue_1133_testdata_cleanup.md`, Root-Cause-Eintrag
`docs/project/known_issues.md` → `BUG-1133-TESTDATA`.

---

## Prod-Mail-Pfad-Nachweis: nur passiv (#1147)

**VERBOT: synthetische Sends oder Kunst-User auf Prod zur Pfad-Verifikation.**
Genau das war der 11. Vorfall (Issue #1147) — ein Kunst-User + interner
Prod-Port hat eine Test-Mail über den echten Resend-Produktivpfad an ein
Test-Postfach ausgelöst. Kunst-User wandern zudem in den Prod-Scheduler-
Fan-out und erzeugen dort Folgeschäden (Reports, Statistiken, Alert-Läufe).
Der Resend- vs. Stalwart-Pfad auf Prod darf **ausschließlich passiv**
nachgewiesen werden, nie durch einen zusätzlichen, eigens dafür ausgelösten
Versand.

**Passives Prüfrezept — drei Bausteine, alle ohne eigenen Send:**

1. **Header-Forensik an einer echten, ohnehin versendeten User-Mail:**
   Eine Mail, die durch normalen Produktivbetrieb entstanden ist (Trip-
   Briefing, Alert, Report), im Postfach des Empfängers öffnen und die
   Header prüfen:
   - `Authentication-Results: ... DKIM dkim=pass header.d=henemm.com header.s=resend`
   - `Received: from ... amazonses.com ...`

   Beide zusammen belegen zweifelsfrei die Resend-Route (Resend liefert
   über AWS SES aus). Fehlen sie, lief die Mail über Stalwart.

2. **Unit-Env-Attestation (ohne Send):**
   ```bash
   systemctl cat gregor-python gregor-api | grep GZ_RESEND_ALLOWED
   ```
   Zeigt `GZ_RESEND_ALLOWED=1` in den Prod-Units. Ergänzend die
   Settings-Auflösung prüfen (welcher `smtp_host` tatsächlich konfiguriert
   ist) — ohne einen Send auszulösen.

3. **Guard-Log-Grep:**
   ```bash
   journalctl -u gregor-python | grep "Resend Default-Deny"
   ```
   Kein Treffer im relevanten Zeitfenster bestätigt, dass der #1122-Guard
   nicht eingegriffen hat (bzw. ein Treffer zeigt einen geblockten Versuch).

Diese drei Bausteine zusammen liefern denselben Erkenntnisgewinn wie ein
synthetischer Testversand — ohne dessen Risiko (Kunst-User im Scheduler,
Test-Postfach über Resend, Kontingent-Verbrauch).
