# Gates & Ratschen — Detailmechanik

Ausgelagert aus `CLAUDE.md` (2026-08-15), damit die Detailmechanik nicht in **jeder** Modell-Anfrage
mitgeladen wird. In `CLAUDE.md` steht je Gate nur noch der Merksatz und der Verweis hierher.
**Hier nachsehen, wenn ein Gate blockiert und die Meldung nicht selbsterklärend ist.**

## Frontend-Browser-Gate (#1558, seit 2026-08-08)

Berührt der committete Scope `frontend-only` oder `full-stack`, lädt `staging_gate.py --write-verdict`
**selbst** sechs Kernseiten (`/`, `/trips`, `/trips/new`, `/compare`, `/compare/new`, `/locations`) in
einem echten Chromium gegen Staging und sammelt `console(type=error)` sowie `pageerror` — Warnungen
zählen nicht. Schlägt das fehl, entsteht **keine** Attestation, der Prod-Deploy bleibt blockiert.

**Fail-Grenze:** Lässt sich das Gate-Modul selbst nicht laden (Import-/Syntaxfehler), läuft der Aufruf
mit Warnung durch — ein kaputter Wächter darf nie die Ursache sein, dass niemand mehr ausliefert.
Fehlt dagegen Playwright, ist Staging nicht erreichbar, scheitert die Anmeldung oder fehlen
Zugangsdaten, wird **blockiert** — das ist „Nachweis nicht erbringbar", nicht „Gate kaputt".

**Notausgang: `GZ_SKIP_FRONTEND_BROWSER_GATE=1`** (exakt `1`, laut auf stderr).
**`GZ_SKIP_E2E_GATE` wirkt hier NICHT** — das sitzt in `gate_check()` (Deploy-Check, Mode B), der
Browserlauf hängt in `write_verdict()` (Mode A). Zwei Schalter mit Absicht: der Deploy-Skip ist
flüchtig, der Browserlauf-Skip erzeugt ein **dauerhaftes** Artefakt. Bei bestandenem Lauf trägt die
Attestation `frontend_pages_checked`; wurde übersprungen oder war das Gate-Modul nicht ladbar, trägt
sie stattdessen `frontend_browser_gate: "UEBERSPRUNGEN via …"` bzw. `"NICHT GELAUFEN …"` — das
Artefakt darf keinen Nachweis behaupten, den es nie gab.

*Regel-Budget: Prüfdatum 2026-11-05. Fang-Beleg: #1552 (Kernseite auf Staging unbedienbar bei 5837
grünen Tests, Adversary VERIFIED, alle CI-Checks grün). Am Prüfdatum mitzubewerten: ob
`ui_screenshot_gate.py` dadurch ganz oder teilweise entbehrlich wird.*

## Zugangsdaten: DREI Quellen, nicht zwei (2026-08-08)

Bei einer Blockade **zuerst hier** nachsehen, nicht in der `.env` des Arbeitsordners.

| Zweck | Variablen | Quelle |
|---|---|---|
| nginx-Schranke | `GZ_VALIDATOR_*` | `.claude/validator.env` |
| App-Anmeldung (Staging-Ziel) | `GZ_AUTH_*` | `/home/hem/gregor_zwanzig_staging/.env` |
| App-Anmeldung (lokal) | `GZ_AUTH_*` | lokale `.env` |

Die Staging-Instanz hat **eigene** Anmeldedaten — gleicher Benutzername, **anderes Passwort**;
gemessen an `POST /api/auth/login`: Arbeitsordner-`.env` → **401**, Staging-`.env` → **200**. Genau
daran blockierte das frisch ausgelieferte Gate jede Frontend-Auslieferung. Modul-Attribut
`STAGING_ENV_PATH`, überschreibbar per `GZ_STAGING_ENV_PATH`.

**„Anmeldung abgelehnt" ≠ „zurückgeleitet auf die Anmeldemaske"** — wer beides gleichsetzt, hält
einen generell kaputten Anmeldeweg für den Beleg, dass ein falsches Passwort erkannt wurde. Die
Ablehnung kommt als `POST 401` auf **`/login`** (SvelteKit-Form-Action), nicht auf
`/api/auth/login`. Die Tests bewachen die **Quelle** der Anmeldedaten, nicht ihre **Gültigkeit** —
ein gedrehtes Staging-Passwort lässt die Kern-Suite grün und blockiert trotzdem.
Meldungs-Tabelle: `docs/reference/operations_playbook.md`.

## E2E-Nachweis-Ablage (seit #1382)

**Eine Datei je Stand** unter `.claude/e2e_verified/<sha>.json` — geschrieben und gelesen über
dieselbe Auflösung. Die frühere einzelne Sammeldatei wird **nicht mehr gelesen**; fehlt der Nachweis
für den Zielstand, blockiert das Gate und sagt genau das, statt einen fremden Stand zu nennen.
Dieselbe Bedingung gilt für Deploy-Gate und Post-Deploy-Selftest: exakter Treffer ODER ein Vorgänger,
der bestanden **und** frisch ist **und** dessen Zuwachs reine Doku ist. Ein ausdrücklich übergebener
`--e2e-path` ist maßgeblich (keine Vorgänger-Suche).

Meldet ein Lauf `verified_commit (<fremder Stand>) != expected-commit`, ist das der **alte** Wortlaut
— dann läuft dort noch Code vor #1382.

## Renderer-Commit-Gate (#811)

`renderer_mail_gate.py` blockiert jeden Commit, der eine Mail-Inhalts-Datei staged
(`src/output/renderers/email/*.py`, `src/output/renderers/{trip_report,sms_trip,compact_summary}.py`,
`src/output/renderers/alert/*.py`, `src/output/channels/email.py`), bis im aktiven Workflow **beide**
frisch vorliegen: (1) `tests/tdd/test_issue_811_mode_matrix.py` grün, (2) erfolgreicher
`briefing_mail_validator.py`-Lauf. Abhilfe bei Blockade: den Test ausführen, dann Validator grün
bekommen.

**„Un-überspringbar" gilt erst seit #1431 (2026-08-04) wirklich.** Davor entschied dieses Gate — wie
vier weitere — per Teilstring `"git commit"`, ob es überhaupt prüft; `git -C /pfad commit`,
`git -c k=v commit` und `git --no-pager commit` umgingen es **still**. Seit #1431 entscheidet
`hook_utils.is_git_subcommand` tokenbasiert (agent-os-openspec ≥ 3.10.0) mit umgedrehter Frage: nicht
„erkenne ich einen Aufruf?", sondern „bin ich sicher, dass hier keiner drinsteckt?".
**Merksatz für jede solche Zusicherung: nachmessen, nicht glauben.**

## Pendant-Sperre (#1481 B, seit 2026-08-04)

`pendant_gate.py` blockiert jeden Commit, der eine **neu angelegte** Datei in einem einseitigen
Bereich enthält — `frontend/src/lib/components/{compare,compare-new,trip-detail,trip-new}/**` und
`src/output/renderers/**/{compare_*,trip_*}.py` (rekursiv).

Zwei Auswege, beide ohne Rückfrage: die Datei unter `frontend/src/lib/components/shared/**` bzw. als
Renderer **ohne** `compare_`/`trip_`-Präfix ablegen — **oder** eine Kopfzeile
`gz-eigenstaendig: <fachlicher Grund>` in die ersten 20 Zeilen setzen (mind. 15 sinnvolle Zeichen).
**Der Ausweg verhindert nichts — er macht die Entscheidung im Änderungssatz zitierbar.**

**Bewusste Grenzen** (Spec `docs/specs/modules/feat_1481b_pendant_gate.md`): keine Go-Seite,
unpräfigierte Trip-Gegenstücke wie `email/html.py` sind unerkennbar, die Begründung wird auf Länge
geprüft (nicht auf Substanz), und ein Commit in ein **anderes** Verzeichnis wird nicht geprüft.
Ausgenommen: Testdateien und der gesamte Bestand — nur Neuanlagen greifen. Prüfdatum 2026-11-03.

## Commit-Gate „Tests der berührten Dateien" (#1481 A, seit 2026-08-04)

`touched_tests_gate.py` blockiert jeden Commit, der einen Test rot macht, der zu einer der geänderten
Dateien gehört (Python/Go/Frontend). Vorbestehend rote Tests blockieren nicht — der Vorzustand wird an
einem Wegwerf-Abzug des letzten Commits **gemessen**, nicht gepflegt. Geprüft wird nur `tests/unit/`;
was ungeprüft blieb, nennt die Meldung. Abhilfe: den genannten Test reparieren oder löschen — nicht
drumherum arbeiten. Prüfdatum 2026-11-03.

## Test-Pfadregel-Ratsche (#1409, ab 2026-07-29)

Ein Test löst seinen **Prüfling** relativ zur eigenen Testdatei auf
(`Path(__file__).resolve().parents[2]`), NIE über den festen Hauptrepo-Pfad — sonst prüft er aus einem
Worktree die unveränderte Hauptrepo-Kopie und meldet **falsches Grün**. Bewusst fest bleibt die
**geteilte Ablage**: HEAD-Ermittlung, Attestation, `docs/artifacts`, `cwd` und Daten, die der Prüfling
über sein `cwd` liest (z. B. Soll-Bilder).

Durchgesetzt via `tests/tdd/test_repo_path_hardcoding_ratchet.py` (AST-Auflösung inkl.
Konstanten-Joins; Fund = Ziel liegt per `git ls-files` als Datei im Repo; Prüfdatum 2026-10-27).
Begründete Ausnahme als Kommentar **an der Zeile**: `# gz-main-path: <Begründung>` (mind. 15 sinnvolle
Zeichen). Grenzen — u. a. tote Pfade und Ketten ab 26 Gliedern — in
`docs/specs/modules/fix_1409b_repo_path_ratchet.md` unter „Known Limitations".

## Testnamens-Gate

Testdateien nach Verhalten benennen (`test_alert_throttle.py`), NICHT nach Issue-Nummer. Durchgesetzt
via `test_naming_gate.py`; Prüfdatum 2026-10-09. Bestand: 262 issue-nummerierte Dateien, Sanierung
läuft unter #1196.

**Kein Big-Bang-Reorg des Bestands (Tech-Lead-Entscheid 2026-08-08):** Testpfade sind hart verdrahtet
in `.github/ci_tdd_excludes.txt`, den Collection-Meta-Tests und den Ratschen — Massen-Umbenennung
bricht diese Wächter. Bestand nur opportunistisch (Datei ohnehin angefasst) oder themenweise mit
eigenem PR konsolidieren, in dem alle Referenzen mitgezogen werden.

## Breiter Testlauf gesperrt (ab 2026-08-03)

`uv run pytest` **ohne konkret benannte Testdateien** ist blockiert — voller Suite-Lauf und
Verzeichnis-Lauf. Grund: eine ungemarkerte Testdatei genügt, um echten Versand auszulösen; am
2026-08-03 gingen so echte Telegram-Nachrichten an den **Produktiv-Chat des PO** (#1477 —
`Settings(...)` fällt bei fehlenden Feldern still auf die Prod-`.env` im Worktree zurück, und ein
`mail_sink` schützt nur Mail). Durchgesetzt via `.claude/hooks/broad_test_run_gate.py`.

**Erlaubt:** Dateien benennen · `--collect-only` · `--disable-socket` (pytest-socket) · Einmal-Freigabe,
die **nur der User** durch Tippen von `override` erzeugt. Prüfdatum 2026-11-01.

## CI-Ratschen

### tdd-Ratsche
`.github/ci_tdd_excludes.txt` listet die offline-roten `tests/tdd/`-Dateien. Nur ENTFERNEN erlaubt
(Datei grün gemacht → Zeile raus); neue tdd-Dateien laufen automatisch auf CI. Ergänzen einer Zeile
nur mit Begründung im PR.

### e2e-Ratsche (umgekehrte Richtung)
`.github/ci_e2e_specs.txt` ist eine **Positivliste** und darf nur WACHSEN — eine Ausschlussliste würde
eine grüne Grundmenge voraussetzen, die eine Stichprobenmessung (30,6 % rot) widerlegt hat.
Stand nach #1771 S3 (2026-08-14): **45 Dateien / 224 Testfälle**.

Aufnahme nur nach **Filter A** (strukturell) + **Filter B** (3× hintereinander grün) + **Filter C**
(die Datei darf beim Laufen keine *versionierte* Datei verändern — 3 Specs schrieben Screenshots ohne
`../` nach `frontend/docs/artifacts/`, das die Ignore-Regel `docs/artifacts/` nicht abdeckt).

🔴 **Filter B MUSS im ZIELVERBUND gemessen werden**, nie im Kandidatenverbund. Genau daran hing #1771
S3: zwei Dateien waren im 51er-Verbund grün und in der echten Positivliste **rot** —
`bug-703-login-ratelimit.spec.ts` feuert absichtlich 32 Anmeldungen gegen das IP-Limit von 30/Stunde
(`internal/router/router.go`) und verbrennt das Kontingent des **ganzen Jobs**; Playwright sortiert
**alphabetisch**, die CLI-Reihenfolge ist wirkungslos. Deshalb läuft die Datei in `ci.yml` als eigener,
nachgelagerter Aufruf. Bestandsdateien merken nichts davon (sie nutzen `storageState`) — es trifft nur
Dateien mit **eigenem** Login, also ausgerechnet Mandantentrennungs-Tests. **Der Split behandelt das
Symptom; beim nächsten Wachstum um Login-Tests neu bewerten.**

**Beide Schwellen exakt nachziehen, kein Puffer** (F006): `E2E_MIN_SPECS` ist mechanisch an die
Listenlänge gebunden (`tests/unit/test_e2e_positivliste_ratschen_bindung.py`, prüft auch Filter C);
`E2E_MIN_EXECUTED_HAUPT`/`_RATELIMIT` bleiben **Handpflege** — ohne echten Browserlauf nicht statisch
ableitbar, als Known Limitation benannt statt als gelöst behauptet.

**Der rote Restbestand ist veraltet, nicht kaputt:** #1771 S3 hat 200 rote Testfälle diagnostiziert —
**0 echte Produktfehler**, dafür 22 gesuchte Testids, die es im Frontend nicht mehr gibt. Es gibt
**keinen gemeinsamen Hebel** (dreifach belegt, ADR-0054-Nachtrag) ⇒ jede weitere Aufnahme ist
Einzelfallarbeit. **Diese Messung nicht wiederholen.**

Specs: `fix_1771_s2_playwright_ci_ampel.md` (Lane), `fix_1771_s3_e2e_listen_wachstum.md` (Wachstum,
Verfahren, Abbruchgrenze).

## Regel-Budget: Prüfdaten im Überblick

| Regel / Gate | Prüfdatum | Fang-Beleg bei Einführung |
|---|---|---|
| Mutations-Gegenprobe | 2026-11-01 | #1448 (2 von 3 Scheiben), #1457 (6 Findings) |
| Breiter Testlauf gesperrt | 2026-11-01 | #1477 (echter Telegram-Versand an Prod-Chat) |
| CI-Ampel (5 Checks) | 2026-11-02 | 6 wochenlang unbemerkte test-Rote + ~5000 unbewachte tdd-Tests (#1196) |
| Pendant-Sperre (#1481 B) | 2026-11-03 | — |
| Touched-Tests-Gate (#1481 A) | 2026-11-03 | — |
| Testnamens-Gate | 2026-10-09 | — |
| Test-Pfadregel-Ratsche (#1409) | 2026-10-27 | — |
| Frontend-Browser-Gate (#1558) | 2026-11-05 | #1552 (Kernseite unbedienbar bei grüner Ampel) |
| 6. Check `e2e` (#1771 S2) | 2026-11-11 | offen — Kriterium: eine Regression, die die anderen fünf durchlassen |
| staging_gate — `frontend/e2e/` nicht als Code klassifiziert (#1197) | 2026-11-15 | Live erlebt 2026-08-15 (PR-Stack #1736/#1852/#1881/#1882), Fix folgt |

Am Prüfdatum gilt: kein nachweisbarer Fang → **Rückbau**. Wirkmodell:
`docs/analysis/backlog-spirale-2026-07.md`.

## Grundprinzip aller Wächter

Beide Commit-Gates aus #1481 — und das Frontend-Browser-Gate — lassen bei **eigener** Störung immer
durch und sagen es. Ein defektes Gate darf nie die Ursache sein, dass nicht mehr gearbeitet werden
kann. Umgekehrt gilt: „Nachweis nicht erbringbar" ist **kein** Gate-Defekt und blockiert.
