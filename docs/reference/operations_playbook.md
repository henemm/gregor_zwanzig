# Operations-Playbook — ausgelagerte Mechanik

Diese Datei bündelt die **detaillierte Mechanik** von Abläufen, deren *Prinzip* in
`CLAUDE.md` steht. `CLAUDE.md` bleibt schlank (Prinzip + Verweis), die Schritt-für-Schritt-
Details stehen hier — bei Bedarf gezielt nachlesen.

---

## E2E-Verifikation (`/e2e-verify`) — Detailablauf

Die echte "funktioniert es wirklich"-Verifikation läuft **nach** dem Push gegen die
Staging-Umgebung (`https://staging.gregor20.henemm.com`) — **nie** durch einen lokalen
Neustart des Live-Servers (auf dieser Maschine = Produktion). Siehe Issue #339.

**Gesamtablauf:** Branch pushen → PR mit grüner CI-Ampel mergen (PO-go 2026-08-05,
s. „Liefer-Workflow" unten) → ~5 Min Staging-Auto-Deploy abwarten →
`/e2e-verify` (gegen Staging) → `deploy-gregor-prod.sh` → Post-Deploy-Selftest (Issue #564) → Issue close.

**Schritte in `/e2e-verify`:**

1. Smoke gegen Staging (`/` + `/api/health`)
2. Scope bestimmen (frontend-only vs. backend/full-stack)
3. frontend-only → `staging-validator` Agent prüft alle ACs aus der Spec via Playwright; schreibt den Nachweis mit `verified_commit` + `staging_verdict`
4. backend/full-stack → Test-Trip auf Staging, Mail nur an `gregor-test@henemm.com`, IMAP-Prüfung
5. Nachweis in `.claude/e2e_verified/<sha>.json` — **eine Datei je Stand** (commit-benannt), mit `verified_commit`, `staging_verdict` und strukturierten Findings pro AC

Basis-URL für Browser-Checks via `GZ_SVELTE_BASE` (Default Staging):
```bash
GZ_SVELTE_BASE=https://staging.gregor20.henemm.com \
  uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --url "/"
```

`deploy-gregor-prod.sh` liest den Nachweis für den Zielstand (`.claude/e2e_verified/<sha>.json`)
und blockiert den Prod-Deploy als Hard Gate, wenn keiner vorliegt, `verified_commit` nicht passt
oder `staging_verdict` nicht mit `VERIFIED` beginnt (Issue #521).

**Seit Fix #1382 (2026-07-26):**

- Gesucht wird **ausschließlich** die commit-benannte Datei — es gibt keinen Rückfall mehr auf eine
  einzelne Sammeldatei. Fehlt der Nachweis für den Zielstand, sagt das Gate genau das, statt einen
  fremden alten Stand zu nennen.
- Fünf unterscheidbare Meldungen: kein Nachweis · nicht bestanden · zu alt · **Zielstand von einer
  Parallelsitzung weitergeschoben** (nennt die dazwischen geänderten Dateien und zwei Auswege) ·
  Datei passt nicht zu ihrem Namen.
- Der Zielstand darf als volle Kennung, Kurzform oder `origin/main` übergeben werden — alle drei
  ergeben denselben Nachweis-Pfad.
- Wird ein Pfad **ausdrücklich** übergeben (`--e2e-path`), ist er maßgeblich; es wird dann kein
  Vorgänger-Stand gesucht.
- Trifft die Vorgänger-Suche auf einen Nachweis, der **nicht bestanden** ist, blockiert sie —
  sie läuft nicht mehr daran vorbei zu einer älteren bestandenen Basis.

---

## Frontend-Browser-Gate (Issue #1558) — Detailablauf

Berührt der committete Scope `frontend-only` oder `full-stack`, ruft `staging_gate.py
--write-verdict` selbst `.claude/hooks/e2e_frontend_browser_gate.py` auf (Modul-Pfad
`staging_gate.FRONTEND_GATE_PATH`) — nach der Scope-Berechnung, aber **bevor** die Attestation
geschrieben wird. Ohne diesen bestandenen Lauf entsteht keine Datei in `.claude/e2e_verified/`.

**Was passiert:** die sechs Kernseiten `/`, `/trips`, `/trips/new`, `/compare`, `/compare/new`,
`/locations` werden in einem echten Chromium (Playwright, headless) gegen die übergebene
Basis-URL (`GZ_VALIDATION_URL`, Default Staging) geladen. Gesammelt werden ausschließlich
`console(type == "error")` und `pageerror` — Warnungen zählen nicht. Eine erreichte
Anmeldemaske gilt NICHT als bestandene Kernseite (`unauthenticated_reason()`, Fix #1307).

**Bei Fehlschlag:** keine Attestation, `write_verdict()` endet mit Exit 1 — kein Prod-Deploy
für diesen Stand.

**Fail-Grenze** — bewusst zwei verschiedene Ausgänge:
- Gate-Modul selbst nicht ladbar (Import-/Syntaxfehler) → Warnung, der Aufruf läuft durch — ein
  kaputter Wächter darf nie die Ursache sein, dass niemand mehr ausliefern kann.
- Nachweis nicht erbringbar (Playwright fehlt, Staging nicht erreichbar, Anmeldung scheitert,
  Zugangsdaten `GZ_VALIDATOR_USER`/`GZ_VALIDATOR_PASS`/`GZ_AUTH_USER`/`GZ_AUTH_PASS` fehlen,
  Konsolenfehler auf einer Kernseite) → blockiert.

**Attestation:** bei bestandenem Lauf trägt `.claude/e2e_verified/<sha>.json` zusätzlich das
Feld `frontend_pages_checked` mit den geprüften Pfaden.

**Notausgang:** bestehender Mechanismus `GZ_SKIP_E2E_GATE=1` (laut, geloggt) — kein eigener,
zweiter Ausgang für dieses Gate.

### Zugangsdaten: DREI Quellen, nicht zwei (2026-08-08)

**Bei einer Blockade zuerst hier nachsehen — nicht in der `.env` des Arbeitsordners.**
Die Staging-Instanz hat **eigene** Anmeldedaten der Anwendung: gleicher Benutzername,
anderes Passwort. Gemessen gegen `POST /api/auth/login`: die `.env` des Arbeitsordners
liefert **401** `invalid credentials`, die Staging-`.env` **200** mit `gz_session`-Cookie.
Genau daran blockierte das Gate am 2026-08-08 **jede** Frontend-Auslieferung.

| Ebene | Variablen | Quelle |
|---|---|---|
| vorgeschaltete nginx-Schranke | `GZ_VALIDATOR_*` | `.claude/validator.env` |
| Anmeldung der Anwendung, Ziel **Staging** | `GZ_AUTH_*` | `/home/hem/gregor_zwanzig_staging/.env` |
| Anmeldung der Anwendung, sonst | `GZ_AUTH_*` | lokale `.env` |

Der Staging-Pfad steht als Modul-Attribut `e2e_frontend_browser_gate.STAGING_ENV_PATH`
und ist per Umgebungsvariable **`GZ_STAGING_ENV_PATH`** überschreibbar. Rangfolge:
bereits gesetzte Umgebungsvariable > Staging-`.env` (nur bei Staging-Ziel) >
`.claude/validator.env`/lokale `.env`. Dieselbe Quelle nennen die Playwright-Staging-Specs
(`frontend/e2e/issue-1093-compare-layout-crash.spec.ts:21-22`).

### Blockade lesen: die Meldung sagt, wo das Problem liegt

Vier unterscheidbare Ausgänge. **„Anmeldung abgelehnt" ist etwas anderes als
„zurückgeleitet auf die Anmeldemaske"** — wer beides gleichsetzt, hält einen generell
kaputten Anmeldeweg für den Beleg, dass ein falsches Passwort erkannt wurde (dieser
Fehlschluss ist am 2026-08-08 passiert):

| Meldung | Wo suchen |
|---|---|
| „Zugangsdaten fehlen (…)" | Variablen nicht gesetzt — `.claude/validator.env` bzw. Staging-`.env` |
| „Anmeldung nicht durchführbar — …" | technisch: Staging langsam/unerreichbar, Anmeldemaske umgebaut |
| „Anmeldung abgelehnt — … (HTTP 401 auf /login)" | **falsches Passwort**: Staging-`.env` gegen die Anwendung abgleichen |
| „keine angemeldete Kernseite — … Anmeldemaske" | Sitzung greift nicht durch (Cookie, Weiterleitung) |

Die Ablehnung kommt im Browser als `POST 401` auf die Route **`/login`**
(SvelteKit-Form-Action), **nicht** auf `/api/auth/login` — Letzteres ist der Weg der
Go-API und blieb als fest verdrahteter Wächter still. Erkannt wird deshalb allgemein
jede fehlgeschlagene POST-Antwort während der Anmeldung.

**Was die Tests NICHT bewachen:** sie belegen die *Quelle* der Anmeldedaten, nicht ihre
*Gültigkeit*. Wird das Staging-Passwort gedreht, ohne die Datei nachzuziehen, bleibt die
Kern-Suite grün und das Gate blockiert trotzdem — sichtbar nur an „Anmeldung abgelehnt".

Details, Acceptance Criteria, Grenzen: Spec `docs/specs/modules/feat_1558_frontend_browser_gate.md`.

---

## Post-Deploy-Selftest (Issue #564) — Detailablauf

Nach jedem Prod-Deploy erfolgt eine automatische Nachverifikation gegen Produktion — ohne
Playwright (kein Risiko für echte Sessions), stattdessen via Commit-Attestation, Health-Check
und parallele HTTP-Probes auf alle aus der Staging-Verifikation bekannten AC-Pfade.

**Ablauf (integriert in `/7-deploy`):**

1. Commit-Attestation: für `git HEAD` muss ein bestandener Nachweis vorliegen — entweder exakt (`.claude/e2e_verified/<HEAD>.json`) oder über einen Vorgänger-Stand, der bestanden **und** frisch ist **und** dessen Zuwachs bis HEAD reine Dokumentation ist (seit #1382 dieselbe Bedingung wie im Deploy-Gate). Fehlt beides bei ausgeliefertem Programmcode, blockiert der Selbsttest (löst #564 AC-5 teilweise ab)
2. Health-Check: `https://gregor20.henemm.com/api/health` muss HTTP 200 + `status=ok` antworten
3. AC-Attestation: pro Staging-Finding (max 5 parallel) HTTP GET auf entsprechende Prod-URL (erwartet 200 oder 302; ein 302 auf `/login` gilt seit Fix #1353 NICHT mehr als inhaltlicher Nachweis, s.u.)
4. Bericht: Markdown-Tabelle in `docs/artifacts/<workflow>/prod-selftest.md` mit pro-AC-Status
5. Exit-Code: 0 = alle ACs bestätigt (PASS), alle ACs übersprungen (docs-only) oder alle Probes auf den Login-Redirect gelaufen (`SKIPPED_AUTH_REDIRECT`); 1 = Mismatch/Fehler

**Verdict-Ableitung:**

- **PASS:** alle PASS-Findings bestätigen sich in Produktion
- **PARTIAL:** mind. ein PASS-Finding fehlt oder ist unerreichbar in Produktion
- **FAIL:** Commit-Mismatch oder Health unreachable
- **SKIPPED_ALL:** reiner Doku-Deploy (Scope `docs-only`) — dann wird ohne Nachweis übersprungen. Bei ausgeliefertem Programmcode **ohne** Nachweis wird seit #1382 blockiert statt übersprungen
- **SKIPPED_AUTH_REDIRECT** (Fix #1353): ALLE geprobten Findings landeten unauthentifiziert auf `302 → /login`. Der Selbsttest läuft ohne Login — ein Auth-Redirect ist strukturell nicht per unauth-GET beweisbar, kein Defekt. Zählt zur Exit-0-Menge, blockiert den Deploy also nicht, ist aber **kein Ersatz für die Staging-Verifikation**: Es wurde in Prod kein einziger AC inhaltlich bestätigt, nur die Anmelde-Schranke gesehen.

**Schutzwirkung:** Issue-Close erfolgt nur bei Exit 0. Bei PARTIAL/FAIL wird der Bericht
untersucht und ggf. Rollback eingeleitet, bevor das Issue geschlossen wird. Verhindert, dass
Issues geschlossen werden, obwohl der Deploy still fehlschlug oder der falsche Code-Stand
deployed wurde. Bei `SKIPPED_AUTH_REDIRECT` gilt „Issue-Close nur bei Exit 0" unverändert,
aber der eigentliche AC-Beweis für geschützte Endpoints bleibt Aufgabe von `/e2e-verify`
gegen Staging (Schritt 3 oben) — der Selbsttest bestätigt hier nur „Prod lebt und leitet
korrekt auf Login um", nicht „Feature funktioniert". Siehe Spec Issue #564 und #1353 für
technische Details.

---

## Liefer-Workflow — Detailablauf (PR statt Direkt-Push, PO-go 2026-08-05)

**Direkt-Push auf `main` ist abgeschafft** — `main` ändert sich nur per Pull Request,
dessen CI-Ampel (alle 5 Checks) auf dem letzten Stand grün ist. Danach in dieser Reihenfolge:

| Schritt | Was | Wie |
|---|---|---|
| 1 | Branch + PR + Merge | `git push -u origin <branch>` → `gh pr create --fill` → Ampel grün → `gh pr merge --merge` |
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
Spec `docs/specs/_archive/modules/issue_1133_testdata_cleanup.md`, Root-Cause-Eintrag
`docs/project/known_issues.md` → `BUG-1133-TESTDATA`.

---

## Null-Listenfelder in Trip-/Compare-Preset-Dateien heilen (#1244)

Bestandsdateien, die vor dem Fix in Issue #1244 angelegt wurden, können für `corridors`,
`stages`, `stage[].waypoints` bzw. `corridors`, `location_ids`, `empfaenger` noch `null` statt
`[]` auf der Platte tragen (der Loader heilt das seit dem Fix zwar fail-soft beim Lesen, die
Datei selbst bleibt aber kaputt, bis sie einmal neu geschrieben wird). Läuft **pro Host** (Prod,
Staging), als User `claude-gregor`, gegen `data/users`:

```bash
uv run python3 scripts/migrate_1244_null_lists.py --root data/users              # Dry-Run (Default)
uv run python3 scripts/migrate_1244_null_lists.py --root data/users --execute    # Backup + Schreiben
```

**Immer zuerst den Dry-Run lesen.** Das Script ist idempotent — ein zweiter Lauf über bereits
migrierte Daten erzeugt einen leeren Plan und schreibt nichts. Backup: tar.gz nach
`.backups/migrate-1244-<timestamp>.tar.gz` vor jedem `--execute`-Lauf.

**Exit-Codes:**

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg — inkl. leerem Plan beim idempotenten Wiederholungslauf |
| 1 | `--root` existiert nicht/kein Verzeichnis, oder Backup fehlgeschlagen |
| 2 | Teilerfolg — mindestens eine Datei nicht lesbar/parsebar und/oder nicht schreibbar (Details in den `ERROR`-Zeilen der Ausgabe) |

Details (Read-Modify-Write-Prinzip, Feldliste, Adversary-Findings): Spec
`docs/specs/_archive/modules/fix_1244_null_list_fields.md`.

---

## Compare-Metrik-Auswahl auf Größe+Auswertung umstellen (#1373 S2 Scheibe B)

Bestandsdateien, die vor dieser Lieferung angelegt wurden, tragen
`display_config.active_metrics` (Compare-Preset, `kind=vergleich`) noch als
Liste von Anzeige-Schlüsseln (`["temp_max_c", "temp_min_c"]`). Ab dieser
Lieferung wird nur noch das neue Format geschrieben
(`[{"metric_id": "temperature", "aggregation": "max"}, ...]`) — das Altformat
bleibt dauerhaft lesbar, aber nicht mehr geschrieben (Begründung, Restrisiken:
`docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`). Läuft **je Host**
(zuerst Staging, danach Produktion), als User `claude-gregor`, **nach**
erfolgreichem Deploy (`deploy-gregor-prod.sh` bringt Go, Python und Frontend
im selben Lauf auf denselben Commit — es gibt keinen Zwischenzustand
„schreibt neu, liest alt", zu sequenzieren ist nur die Migration selbst):

```bash
uv run python3 scripts/migrate_1373_compare_active_metrics_format.py --root data/users              # Dry-Run (Default)
uv run python3 scripts/migrate_1373_compare_active_metrics_format.py --root data/users --execute    # Backup + Schreiben
```

**Immer zuerst den Dry-Run lesen.** Das Script ist idempotent — ein zweiter
Lauf über bereits migrierte Daten erzeugt einen leeren Plan und schreibt
nichts. Backup: tar.gz nach `.backups/migrate-1373-<timestamp>.tar.gz` vor
jedem `--execute`-Lauf. Read-Modify-Write: nur `display_config.active_metrics`
ändert sich, alle anderen Felder (auch dem Skript unbekannte) bleiben
erhalten. Touren (`kind=route`) und unbekannte Alt-Einträge bleiben
unverändert stehen — die Umstellung ist eine Formatänderung, keine
Bereinigung.

**Warnung — Rollback nach Migrationsstart ist NICHT gefahrlos:** Der alte
(vor dieser Lieferung eingesetzte) Auflöser `resolve_enabled_metrics()` prüft
Mitgliedschaft eines Elements in einem Dict und wirft bei einem
Neuformat-Objekt `TypeError: unhashable type: 'dict'` — der komplette
Vergleichs-Mailversand für das betroffene Preset bricht dann ab, nicht nur
eine einzelne Metrik fällt weg. Sobald die Migration gegen einen Host
gelaufen ist, darf der Code-Commit auf diesem Host nicht mehr ohne Weiteres
zurückgerollt werden.

**Exit-Codes:**

| Code | Bedeutung |
|------|-----------|
| 0 | Erfolg — inkl. leerem Plan beim idempotenten Wiederholungslauf und beim reinen Dry-Run |
| 1 | `--root` existiert nicht/kein Verzeichnis, Backup fehlgeschlagen, oder mindestens ein Preset konnte nicht geschrieben werden (Details in den `Error:`-Zeilen der Ausgabe) |

**Verifikationsanker (gemessen am Produktionsbestand 2026-07-26):** 3
Produktions-Vergleiche mit sowohl Höchst- als auch Tiefsttemperatur in der
Auswahl, 1 mit gefühlter Tiefsttemperatur. Nach der Migration müssen es
weiterhin vier eigenständige, getrennte Einträge sein — keiner darf mit
einem anderen verschmelzen (die Falle: `temp_max_c` und `temp_min_c` teilen
sich dieselbe `metric_id` `"temperature"` und unterscheiden sich nur in der
`aggregation`).

Details (Read-Modify-Write-Prinzip, Restrisiken R1/R2, AC-Zuordnung): Spec
`docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md`.

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
