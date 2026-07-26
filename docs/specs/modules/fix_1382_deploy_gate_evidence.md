---
entity_id: fix_1382_deploy_gate_evidence
type: module
created: 2026-07-25
updated: 2026-07-25
status: draft
version: "1.0"
tags: [gate, deploy, attestation, tooling]
---

# Fix #1382 — Deploy-Gate liest denselben Nachweis, den es schreibt

## Approval

- [ ] Approved

## Purpose

Der Prod-Deploy-Wächter (`staging_gate.gate_check`) und der Post-Deploy-Selbsttest
(`prod_selftest.run_selftest`) lösen den Verifikations-Nachweis für den Zielstand
heute über zwei unterschiedliche Mechanismen auf, von denen einer — der
Rückfall auf die alte Sammeldatei `.claude/e2e_verified.json` — auf einen 32 Tage
alten Fremd-Commit zeigen kann, sobald für den eigentlichen Zielstand kein
commit-getaggter Nachweis existiert. Das führt zu irreführenden Blockade-Meldungen
und, im Selbsttest, zu einem belegten Fail-open (Exit 0/PASS ohne echte Prüfung).
Dieser Fix entfernt den Rückfall, vereinheitlicht die Nachweis-Auflösung auf eine
einzige geteilte Funktion für beide Hooks, normalisiert die SHA-Eingabe und ersetzt
die irreführende bzw. blind-optimistische Meldungslage durch fünf klar
unterscheidbare, für einen Nicht-Programmierer verständliche Texte.

## Source

- **File:** `.claude/hooks/_e2e_paths.py` — `commit_e2e_path`, `default_e2e_path` (entfällt), neu: `_nearest_verified_ancestor`
- **File:** `.claude/hooks/staging_gate.py` — `gate_check`, `_default_e2e_path` (entfällt), `_nearest_verified_ancestor` (wandert weg)
- **File:** `.claude/hooks/prod_selftest.py` — `run_selftest`, `_default_e2e_path` (entfällt)

> **Schicht-Hinweis:** Ausschließlich Workflow-/Tooling-Schicht (`.claude/hooks/`),
> kein Code in `src/`, `api/`, `internal/` oder `frontend/`. Reine Deploy-Pipeline-Gates.

## Estimated Scope

- **LoC:** ~350 (steigt von der ursprünglichen Schätzung ~240 wegen der PO-Entscheidung,
  die Selbsttest-Verschärfung in denselben Workflow zu ziehen)
- **Files:** 11
- **Effort:** high
- **LoC-Limit-Hinweis:** Das Standardlimit von 250 LoC/Workflow wird überschritten.
  `loc_limit_override` ist erforderlich und wird **erst nach ausdrücklicher
  PO-Freigabe dieser Spec** gesetzt (`workflow.py set-field loc_limit_override 500`),
  nicht vorab.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/_e2e_paths.py::commit_e2e_path` | Funktion | Einzige Quelle der Wahrheit für den commit-getaggten Nachweis-Pfad; von `write_verdict`, `gate_check` und `run_selftest` gemeinsam genutzt |
| `.claude/hooks/_e2e_paths.py::_nearest_verified_ancestor` (neu) | Funktion | Einzige Definition von „gültiger Nachweis" (VERIFIED-Präfix, nicht stale, Zuwachs docs-only); von `staging_gate` und `prod_selftest` gemeinsam genutzt |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` | Aufrufer | Ruft `staging_gate.py --check --expected-commit` (Preflight) und `prod_selftest.py` (Post-Deploy) auf; `TARGET=$(git rev-parse origin/main)` bleibt unverändert (Ursache B, außerhalb dieses Repos) |
| `docs/specs/_archive/modules/issue_564_post_deploy_selftest.md` (AC-5) | Spec | Wird durch diesen Fix ausdrücklich abgelöst (s. Abschnitt „Abgelöste Festlegung") |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md` | Spec | Ancestor-Relaxierungslogik wird von hier nach `_e2e_paths.py` verschoben und für `prod_selftest` mitnutzbar gemacht |
| `docs/adr/0006-no-mocked-tests-e2e-staging.md` | ADR | Kennt nur die alte Sammeldatei als Hard-Gate-Mechanismus; Nachtrag erforderlich (s.u.) |

## Implementation Details

### Scheibe 1 — Nachweis-Auflösung + Meldungen

1. `default_e2e_path()` entfällt ersatzlos aus `_e2e_paths.py`. `staging_gate.gate_check`
   und `prod_selftest.run_selftest` lösen den Nachweis-Pfad künftig **ausschließlich**
   über `commit_e2e_path(shared_repo_dir, sha)` auf — dieselbe Funktion, die auch
   `write_verdict` beim Schreiben benutzt. `CANONICAL_E2E_PATH` entfällt in beiden
   Hooks (Konstante und alle Referenzen).
2. **SHA-Normalisierung:** `gate_check` löst `--expected-commit` bereits heute per
   `git rev-parse --verify --quiet "{expected_commit}^{commit}"` auf (Existenz-Check),
   verwirft aber das Ergebnis (`staging_gate.py:422-434`) und baut den Dateinamen
   weiterhin aus dem rohen Argument. Künftig wird das aufgelöste **volle** SHA aus
   `resolved.stdout` für die weitere Pfad-Bildung übernommen — `--expected-commit
   origin/main` oder eine Kurz-SHA erzeugen damit denselben Pfad wie die volle SHA.
3. **Fünf unterscheidbare Meldungen** ersetzen die heutigen drei (teils gemeinsamen)
   Texte in `gate_check`. Jede Meldung: (a) beschreibt zuerst den Ist-Zustand, dann
   den nächsten Schritt, (b) nennt SHAs achtstellig gekürzt, (c) ist ohne
   Programmierkenntnisse verständlich, (d) enthält an keiner Stelle die
   Zeichenkette `GZ_SKIP_E2E_GATE`:
   - **(i) Kein Nachweis für den Zielstand:** weder commit-getaggte Datei noch ein
     passender verifizierter Vorfahre existiert.
   - **(ii) Nachweis vorhanden, aber nicht VERIFIED:** Datei für den Zielstand
     existiert, `staging_verdict` beginnt nicht mit `VERIFIED` (z.B. `AMBIGUOUS`
     oder leer).
   - **(iii) Nachweis zu alt:** Datei ist VERIFIED, aber `verified_at` liegt mehr
     als `STALE_HOURS` zurück.
   - **(iv) Zielstand ist neuer als der geprüfte Stand, Zuwachs enthält
     Programmcode:** heute nicht als eigener Fall erkannt (fällt unter (ii) mit
     irreführendem „verified_commit != ref"). Neu: eigener Text, der erklärt,
     dass zwischen Prüfung und Deploy vermutlich eine parallele Sitzung gepusht
     hat, und bis zu 5 betroffene Dateipfade aus dem Zuwachs-Diff nennt.
   - **(v) Nachweisdatei trägt einen anderen Stand:** die für den Zielstand
     erwartete Datei existiert, aber ihr `verified_commit`-Feld weicht vom
     Dateinamen ab (Korruption/manuelle Manipulation) — von (i) und (iv) klar
     unterscheidbar, weil hier eine Datei physisch vorhanden ist, aber sich
     selbst widerspricht.

4. **Der Rückfall verschwindet, die Datei bleibt.** `.claude/e2e_verified.json`
   wird **nicht** gelöscht — sie verliert nur ihre Wirkung und dient bis zum
   Abschluss der Verifikation als Beweismittel (V0/V4). Ein späteres Entfernen
   ist ein reiner Betriebsschritt, keine Codeänderung.

### Scheibe 2 — Selbsttest so streng wie das Gate

5. `_nearest_verified_ancestor` wandert von `staging_gate.py:344-398` nach
   `_e2e_paths.py` (Signatur bleibt: `ref`, `git_dir`, `shared_dir`, `max_count`).
   `staging_gate.gate_check` ruft die verschobene Funktion nur noch auf
   (Delegation, kein eigener Code mehr). `prod_selftest.run_selftest` nutzt
   **dieselbe** Funktion für seine Ancestor-Prüfung. Damit existiert die
   Definition von „gültiger Nachweis" (VERIFIED-Präfix + nicht stale + Zuwachs
   docs-only) im gesamten Projekt genau einmal.
6. Die Ad-hoc-Vorfahrenprüfung `prod_selftest.py:631-646` — heute ausschließlich
   `git merge-base --is-ancestor verified_commit head`, ohne VERIFIED-Check, ohne
   Alters-Check, ohne Scope-Prüfung des Zuwachses — entfällt ersatzlos und wird
   durch den Aufruf der geteilten Funktion ersetzt.
7. `prod_selftest.py:614` (`if not e2e_path.exists(): ... return 0`) wird zu
   `return 1`. Dieser Zweig wird nur erreicht, wenn der Scope-Check
   (`prod_selftest.py:605-609`) bereits festgestellt hat, dass **kein**
   docs-only-Deploy vorliegt — echter Code wurde also ausgerollt. Fehlt dafür
   jeder Nachweis (auch kein Vorfahre), ist Blockieren die sichere Richtung.
   **Löst #564 AC-5 ausdrücklich ab** (s. eigener Abschnitt unten).

## Expected Behavior

- **Input:** `--expected-commit <sha|kurz-sha|origin/main>` (Preflight) bzw. HEAD
  (Selbsttest); commit-getaggte Nachweis-Dateien unter
  `.claude/e2e_verified/<sha>.json` im geteilten Hauptrepo.
- **Output:** Exit 0 nur, wenn für den Zielstand (exakt oder über einen gültigen
  Vorfahren) ein frischer VERIFIED-Nachweis existiert und der Zuwachs — falls
  über einen Vorfahren relaxiert — docs-only ist. Sonst Exit 1 mit genau einer
  der fünf oben beschriebenen Meldungen.
- **Side effects:** keine Schreibzugriffe auf den Nachweis selbst durch
  `gate_check`/`run_selftest` (nur Lesepfad ändert sich); `write_verdict` bleibt
  unverändert der einzige Schreiber.

## Acceptance Criteria

- **AC-1 (Scheibe 1):** Given für den Zielstand existiert weder eine commit-getaggte Nachweis-Datei noch ein verifizierter Vorfahre, When der Deploy-Wächter mit `--expected-commit <Zielstand>` geprüft wird, Then blockiert er (Exit 1) und die Meldung nennt den Zielstand-Kurz-SHA — nicht den Commit einer fremden, älteren Datei — und enthält nicht die Zeichenkette `GZ_SKIP_E2E_GATE`.
  - Test: Echtes Temp-Git-Repo ohne jede Attestation für den Zielcommit, aber mit einer alten commit-getaggten Fremd-Attestation für einen anderen, nicht verwandten Commit im selben Verzeichnis; `gate_check` läuft gegen den Zielstand; Exit-Code und Meldungstext werden geprüft (kein Dateiinhalt-Check, sondern der tatsächliche stderr-Text der Funktion).

- **AC-2 (Scheibe 1):** Given für den Zielstand existiert eine Nachweis-Datei, deren `staging_verdict` nicht mit `VERIFIED` beginnt (z.B. `AMBIGUOUS: ...` oder leer), When der Deploy-Wächter geprüft wird, Then blockiert er (Exit 1) und die Meldung nennt sowohl den Zielstand als auch das tatsächlich vorgefundene Verdict-Präfix.
  - Test: Echtes Temp-Repo mit commit-getaggter Datei für den Zielcommit, `staging_verdict="AMBIGUOUS: Login-Flow unklar"`; `gate_check` läuft; Exit-Code 1 und Meldung enthält das AMBIGUOUS-Verdict wörtlich.

- **AC-3 (Scheibe 1):** Given für den Zielstand existiert ein VERIFIED-Nachweis, dessen `verified_at` älter als die Stale-Grenze (24h) ist, When der Deploy-Wächter geprüft wird, Then blockiert er (Exit 1) und die Meldung nennt das Alter in Stunden und den Zielstand.
  - Test: Echtes Temp-Repo, Nachweis-Datei mit `verified_at` = jetzt minus 30h; `gate_check` läuft; Exit 1, Meldungstext enthält eine Stundenzahl > 24.

- **AC-4 (Scheibe 1):** Given der Zielstand ist ein Nachfahre des zuletzt geprüften Standes und der Zuwachs zwischen beiden enthält mindestens eine Datei unter `src/`, `api/`, `internal/`, `cmd/` oder `frontend/`, When der Deploy-Wächter geprüft wird, Then blockiert er (Exit 1), die Meldung erklärt, dass zwischen Prüfung und Deploy vermutlich eine parallele Sitzung gepusht hat, und nennt bis zu 5 der betroffenen Dateipfade aus dem Zuwachs.
  - Test: Echtes Temp-Repo mit zwei Commits: Basis-Commit mit VERIFIED-Nachweis, Ziel-Commit fügt eine Datei unter `src/` hinzu; `gate_check --expected-commit <Ziel>` läuft; Exit 1, Meldung enthält den Dateipfad der geänderten `src/`-Datei wörtlich.

- **AC-5 (Scheibe 1):** Given die für den Zielstand erwartete Nachweis-Datei existiert physisch, aber ihr `verified_commit`-Feld weicht vom Dateinamen ab (inkonsistente/manipulierte Datei), When der Deploy-Wächter geprüft wird, Then blockiert er (Exit 1) mit einer Meldung, die diesen Fall erkennbar von „kein Nachweis vorhanden" (AC-1) unterscheidet, indem sie nennt, dass eine Datei gefunden wurde, deren Inhalt aber nicht zum Namen passt.
  - Test: Echtes Temp-Repo, Datei unter `.claude/e2e_verified/<ziel-sha>.json` wird angelegt, aber `verified_commit` im Inhalt zeigt auf einen anderen SHA; `gate_check` läuft gegen den Zielstand; Meldungstext von AC-1 wird per String-Vergleich als abweichend bewiesen.

- **AC-6 (Scheibe 1):** Given ein Nachweis wurde für einen Commit unter seiner vollen SHA geschrieben, When derselbe Commit anschließend per Kurz-SHA und separat per `origin/main` als `--expected-commit` abgefragt wird, Then liefern beide Aufrufe exakt dasselbe Ergebnis (Exit-Code und gefundene Datei) wie die Abfrage mit der vollen SHA.
  - Test: Echtes Temp-Repo mit einem `origin`-Remote, dessen `origin/main` auf den attestierten Commit zeigt; drei `gate_check`-Läufe (volle SHA, Kurz-SHA, `origin/main`) werden verglichen — alle drei müssen dieselbe Datei unter demselben aufgelösten vollen SHA lesen wie `write_verdict` sie geschrieben hat.

- **AC-7 (Scheibe 2):** Given der Scope-Check hat bereits festgestellt, dass echter Programmcode ausgerollt wurde (kein docs-only-Deploy), und für den aktuellen Produktions-HEAD existiert weder ein exakter Nachweis noch ein verifizierter Vorfahre, When der Post-Deploy-Selbsttest läuft, Then blockiert er (Exit-Code 1) statt wie bisher zu überspringen, und der Bericht macht deutlich, dass kein Nachweis vorlag.
  - Test: Echtes Temp-Repo mit einem Commit, der eine Datei unter `src/` ändert (Scope ≠ docs-only), ohne jede Attestation; `run_selftest` läuft; Exit-Code wird gegen 1 geprüft (bisheriges Verhalten wäre 0 gewesen — Regressionstest auf die neue Regel).

- **AC-8 (Scheibe 2):** Given der aktuelle HEAD ist Nachfahre eines Commits, dessen Nachweis-Datei existiert, aber `staging_verdict` mit `BROKEN` beginnt (oder das Feld ganz fehlt), When der Post-Deploy-Selbsttest läuft, Then ergibt er **nicht** PASS, sondern blockiert (Exit 1) — die reine Vorfahren-Beziehung allein darf nie mehr zu Exit 0 führen.
  - Test: Echtes Temp-Repo, zwei Commits; Basis-Commit trägt eine Attestation mit `staging_verdict="BROKEN — Staging kaputt"`, HEAD ist direkter Nachfahre ohne eigenen Nachweis; `run_selftest` läuft; Exit-Code wird gegen 1 geprüft (das Sandkasten-Experiment aus dem Kontextdokument zeigte hier vorher Exit 0).

- **AC-9 (Scheibe 2):** Given der aktuelle HEAD ist Nachfahre eines VERIFIED, nicht-stalen Vorfahren, und der Zuwachs zwischen Vorfahre und HEAD ist ausschließlich Dokumentation/Tests (Scope docs-only), When sowohl der Deploy-Wächter als auch der Post-Deploy-Selbsttest laufen, Then liefern **beide** Exit-Code 0 — der zulässige Ancestor-Durchlass bleibt erhalten und ist für beide Aufrufer identisch, weil beide dieselbe geteilte Funktion nutzen.
  - Test: Echtes Temp-Repo, Basis-Commit mit VERIFIED-Nachweis, HEAD fügt nur eine Datei unter `docs/` hinzu; `gate_check` und `run_selftest` laufen nacheinander gegen dasselbe Repo; beide Exit-Codes werden gegen 0 geprüft.

- **AC-10 (Scheibe 2):** Given eine Nachweis-Datei für den exakten Zielstand existiert, ist VERIFIED und frisch, When der Post-Deploy-Selbsttest läuft, Then bleibt Exit 0 unverändert erhalten (keine Regression durch die Verschärfung).
  - Test: Echtes Temp-Repo, commit-getaggte Datei für HEAD, VERIFIED, `verified_at` = jetzt; `run_selftest` läuft; Exit-Code 0, Bericht wird geschrieben.

- **AC-11 (Scheibe 1):** Direkte Reproduktion des gemeldeten Fehlers. Given für den Zielstand existiert kein Nachweis, aber die alte Sammeldatei `.claude/e2e_verified.json` liegt daneben und trägt einen fremden, älteren Commit, When der Deploy-Wächter mit `--expected-commit <Zielstand>` geprüft wird, Then blockiert er (Exit 1), die Meldung nennt den fremden Commit aus der Sammeldatei **nicht**, und das Ergebnis ist identisch zu einem Lauf, bei dem die Sammeldatei gar nicht existiert.
  - Test: Echtes Temp-Repo c1→c2→c3, **kein** `<c3>.json`, dafür Sammeldatei mit `verified_commit=c1` und nur zwei Feldern (exakt wie die reale Altlast, ohne `verified_at`). Zwei Läufe — mit und ohne Sammeldatei —; beide Exit 1, beide Meldungen nennen `c3[:8]`, keine nennt `c1[:8]`, und beide Meldungsfälle sind gleich. Dies ist der Fall, der heute die irreführende Meldung erzeugt und den **kein** Bestandstest ausführt.

- **AC-12 (Scheibe 1):** Given der Deploy-Wächter blockiert aus einem der fünf Gründe (i) bis (v), When die jeweilige Meldung ausgegeben wird, Then enthält keine davon einen Hinweis auf den Notfall-Schalter zum Überspringen des Gates.
  - Test: alle fünf Meldungsfälle werden in echten Temp-Repos ausgelöst; für jeden wird der vollständige stdout+stderr geprüft: keine Ausgabe enthält die Zeichenkette `GZ_SKIP_E2E_GATE`.

- **AC-13 (Scheibe 2):** Given der einzige auffindbare Nachweis stammt von einem Vorfahren, ist zwar VERIFIED, aber älter als die Stale-Grenze (24h), When der Post-Deploy-Selbsttest läuft, Then blockiert er (Exit 1) — heute prüft der Selbsttest das Alter überhaupt nicht.
  - Test: Echtes Temp-Repo, Basis-Commit mit VERIFIED-Nachweis, `verified_at` = jetzt minus 30h, HEAD ist Nachfahre mit ausschließlich docs-Zuwachs; `run_selftest` läuft; Exit-Code wird gegen 1 geprüft (bisheriges Verhalten wäre „PASS (Ancestor)" mit Exit 0 gewesen).

- **AC-14 (Scheibe 2):** Given in der Vorgeschichte des Zielstands liegt ein Nachweis, der ausdrücklich nicht bestanden ist (BROKEN), und davor ein älterer bestandener Nachweis, und der gesamte Zuwachs ist pfadbasiert reine Dokumentation, When Deploy-Wächter und Post-Deploy-Selbsttest laufen, Then blockieren **beide** (Exit 1) — der nicht bestandene Nachweis darf nicht übersprungen werden, um an die ältere Basis zu gelangen.
  - Test: Wegwerf-Repo mit der Kette c0 (Code, bestanden) → c1 (nur `docs/`, BROKEN) → c2 (nur `docs/`, kein eigener Nachweis); `gate_check(expected_commit=c2)` und `run_selftest()` bei HEAD=c2 → beide Exit 1. Gegenprobe ohne den BROKEN-Eintrag → beide Exit 0 (der erlaubte Doku-Durchlass bleibt erhalten).

- **AC-15 (beide Scheiben):** Given dem Prüfer wird eine Nachweisdatei ausdrücklich mitgegeben (`--e2e-path`) und ihr Inhalt passt nicht zum geprüften Stand, When Deploy-Wächter oder Post-Deploy-Selbsttest laufen, Then blockieren sie (Exit 1) auf Grundlage genau dieser Datei — es wird **kein** Vorfahre gesucht, um die Ablehnung zu umgehen.
  - Test: `run_selftest` mit ausdrücklichem Pfad auf eine Datei mit erfundener Kennung (`"deadbeef"*5`) im echten Repo, in dem gültige Vorfahren existieren → Exit 1 (vor der Korrektur: Exit 0 mit „PASS (Ancestor)"). Gegenprobe: derselbe Ablauf **ohne** ausdrücklichen Pfad findet den Vorfahren weiterhin → Exit 0.

## Nachtrag 2026-07-26 (2) — AC-15 (Regressionsfund der Validierungsphase)

Der Regressionslauf in Phase 7 — **nach** dem VERIFIED-Urteil des Adversary — deckte auf, dass eine
ausdrücklich übergebene Nachweisdatei ihre Maßgeblichkeit verloren hatte: Passte ihr
`verified_commit` nicht zum geprüften Stand, fiel der Code auf die Vorfahren-Suche im echten Repo
zurück und ließ durch, obwohl absichtlich eine ungültige Kennung übergeben worden war
(`test_fix_853_842_837_tooling_gates.py::test_ac3_fail_when_not_ancestor`, Exit 0 statt 1).

Das war ein Rückschritt in dieselbe Fehlerklasse, die dieses Ticket schließt: eine benannte
Nachweisquelle wurde stillschweigend übergangen. Der Adversary hatte es nicht gefunden, weil er
durchgängig die normale Pfadauflösung prüfte, nie die ausdrückliche Übergabe.

**Umgesetzte Regel:** Wurde ein Pfad ausdrücklich übergeben, ist er maßgeblich — keine
Vorfahren-Suche. Nur ohne ausdrückliche Übergabe (Normalfall im Deploy) gilt weiterhin
„exakter Treffer → sonst Vorfahre". Stellt zugleich das Verhalten vor #1382 wieder her.

## Nachtrag 2026-07-26 — AC-14 (PO-Entscheidung nach Adversary-Fund F001)

Der unabhängige Prüfer fand einen **mehrstufigen Rest-Fail-open**, den kein Test abdeckte:
`_nearest_verified_ancestor` lief von neu nach alt und übersprang per `continue` jeden Nachweis,
der nicht mit VERIFIED begann — also auch einen ausdrücklichen BROKEN-Befund — bis eine ältere
bestandene Basis gefunden war. War der kumulierte Zuwachs bis zum Zielstand pfadbasiert
„nur Dokumentation" (und `tests/` sowie `.claude/` zählen so), ließen **beide** Prüfer durch,
ohne den BROKEN-Befund je zu erwähnen.

Der Defekt stammt aus #1197 und ist älter als dieses Ticket; er verstößt nicht gegen den Wortlaut
von AC-8, wohl aber gegen dessen Anspruch („die reine Vorfahren-Beziehung allein darf nie mehr zu
Exit 0 führen"). **PO-Entscheidung 2026-07-26: jetzt mitbeheben**, statt ihn als bekannte Grenze
zu vermerken — er gehört zur selben Fehlerklasse, die dieses Ticket schließt.

**Umgesetzte Invariante:** Die Suche endet beim **ersten** Commit, für den überhaupt ein Nachweis
existiert; dieser Nachweis ist dann in jeder Hinsicht entscheidend (nicht bestanden, zu alt,
beschädigt, Kennung passt nicht → blockieren). Kein stilles Weiterlaufen mehr. Wirkt automatisch
auf beide Prüfer, weil sie sich die Funktion teilen.

## Known Limitations

- **Ursache D (nicht behoben, dokumentierte Grenze):** Der Nachweis wird unter
  dem **Worktree**-HEAD benannt (`_head_sha()` liest den aufrufenden
  Arbeitsbaum), aber im **geteilten Hauptrepo** abgelegt. Wird vor dem Push
  rebased oder gequetscht — dokumentierte Praxis in diesem Projekt — zeigt der
  Nachweis auf einen Commit, den `origin/main` nie enthält. Dieser Fix behebt
  das nicht, sorgt aber dafür, dass in diesem Fall die richtige Meldung
  erscheint („kein Nachweis für den Zielstand", Fall (i)) statt eines
  irreführenden Fremdcommits.
- **Nebenbefund, kein Scope (Sammel-Eintrag #1199):** Läuft der Preflight mit
  `--expected-commit` gleich dem aktuellen HEAD, ist der Scope-Diff `HEAD..EXP`
  leer → gilt als `docs-only` → das Gate kehrt zurück, ohne den Nachweis
  überhaupt zu öffnen. Im normalen Deploy-Ablauf harmlos (Preflight läuft vor
  dem Reset, HEAD ≠ Zielstand); beim Wiederholungslauf eines bereits
  ausgecheckten Standes wird das Gate übersprungen. Der zweite Gate-Lauf nach
  dem Reset fängt dies in der Praxis ab.
- **Ursache B bleibt bestehen:** `deploy-gregor-prod.sh` setzt
  `TARGET=$(git rev-parse origin/main)` — ein bewegliches Ziel. Pusht eine
  Parallelsitzung zwischen Preflight und Deploy, blockiert das Gate **zu
  Recht** (Fall (iv) macht das jetzt verständlich, behebt aber nicht die
  Ursache). Die Abhilfe (`TARGET` fixierbar über eine ENV-Variable,
  `origin/main` vor/nach `git fetch` loggen) liegt in `henemm-infra` und wird
  nach PO-Freigabe per MQ an die Instanz `infra` gemeldet — nicht Teil dieses
  Workflows.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0006 (Nachtrag, kein neues ADR)
- **Rationale:** ADR-0006 hält als Grundsatzentscheidung fest, dass der
  Prod-Deploy über ein Hard Gate auf Basis von `e2e_verified.json`
  (`verified_commit` + `staging_verdict`) abgesichert ist und ein Post-Deploy-
  Selbsttest gegen Produktion nachprüft (#521, #564). Diese Kern-Entscheidung
  ändert sich durch #1382 **nicht** — es bleibt ein Hard Gate mit denselben
  zwei Feldern und derselben Zwei-Schichten-Prüfung (Staging-Gate +
  Post-Deploy-Selbsttest). Was sich ändert, ist ausschließlich der
  **Speicher-/Lesemechanismus**: von einer einzelnen Sammeldatei zu
  commit-getaggten Einzeldateien, bereits mit #662/#665 eingeführt, in ADR-0006
  aber nie nachgezogen. Ein neues ADR wäre nur nötig, wenn die
  Gate-Entscheidung selbst zur Debatte stünde (z.B. „Hard Gate abschaffen" oder
  „andere Verifikationsquelle als Staging"). Hier reicht ein Nachtrag: ADR-0006,
  Abschnitt „Entscheidung", Punkt 2, um einen Satz ergänzen, der die
  commit-getaggte Ablage als den tatsächlichen Mechanismus nennt (statt der
  impliziten Referenz auf die alte Singleton-Datei).

## Abgelöste Festlegung

`docs/specs/_archive/modules/issue_564_post_deploy_selftest.md`, **AC-5**
(2026-06-02), wörtlich:

> „Given `e2e_verified.json` existiert nicht (docs-only Deploy oder allererster
> Deploy ohne vorherige Staging-Verifikation), When `prod_selftest.py`
> aufgerufen wird, Then ist der Exit-Code 0, es wird eine INFO-Meldung
> ausgegeben (…), und kein Bericht wird geschrieben."

**Wird ersetzt durch AC-7 dieser Spec:** Fehlender Nachweis führt zu Exit 1
(Block), **sofern der Scope-Check zuvor bereits festgestellt hat, dass es sich
nicht um einen docs-only-Deploy handelt.** Der ursprüngliche docs-only-/
Erst-Deploy-Fall bleibt durch den vorgelagerten Scope-Check (`run_selftest`,
Zeile 605-609) weiterhin Exit 0 — dieser Teil von AC-5 ist unverändert gültig
und wird nicht abgelöst.

**Begründung der Ablösung:** AC-5 wurde 2026-06-02 formuliert, als der einzige
Nachweis-Speicher die Sammeldatei `e2e_verified.json` war und „Datei fehlt"
praktisch nur beim allerersten Lauf vorkam. Mit der commit-getaggten Ablage
(#662) und der belegten Möglichkeit, dass Attestationen durch die
Retention-Grenze (20 Dateien) verschwinden oder für einen abweichenden Commit
liegen, bedeutet „Nachweis fehlt für einen Code-Deploy" heute nicht mehr
zuverlässig „harmloser Erst-/Doku-Lauf", sondern kann ein echter, ungeprüfter
Deploy sein. Ein Fail-open an dieser Stelle widerspricht der Fail-closed-Pflicht
aus der Analyse (Risk #2) und wurde im Sandkasten-Experiment als real
ausnutzbarer Pfad bestätigt (Ursache C).

## Nachweis der Integrität (Pflicht — das Gate darf sich nicht selbst durchwinken)

`_detect_scope_from_git_diff` zählt `.claude/` und `tests/` als docs-only —
dieser Fix deployt damit strukturell an seinem eigenen Gate vorbei. **„Der
Deploy lief durch" ist deshalb kein Nachweis**, ebenso wenig ein grüner
Testlauf im Worktree, da die reale Altlast-Datei nur im Hauptrepo existiert und
Worktree-Tests sie nicht sehen.

Pflichtschritte für die unabhängige Prüfinstanz (auf `/home/hem/gregor_zwanzig`,
`GZ_SKIP_E2E_GATE` ungesetzt):

- **V0 (VOR jeder Codeänderung, sonst unwiederbringlich verloren):**
  Ist-Reproduktion protokollieren — `--check --expected-commit <alter, nicht
  attestierter Commit>` nennt den bekannten Fremdcommit `d850421a`.
- **V1:** Dasselbe Kommando nach der Änderung: Exit 1, Meldung nennt den
  Zielstand und **nicht** `d850421a`.
- **V2 (Negativkontrolle):** Commit ohne jede Attestation → Exit 1.
- **V3 (Positivkontrolle):** frischer VERIFIED-Nachweis für denselben Commit →
  Exit 0. V2 ohne V3 ist wertlos — „blockt immer" sähe von außen identisch aus.
- **V4:** Die Altlast liegt weiterhin unverändert da, ist aber wirkungslos:
  `grep -rn "e2e_verified\.json\|CANONICAL_E2E_PATH\|default_e2e_path"
  .claude/hooks/` liefert keine Treffer mehr.
- **V5:** `--expected-commit` mit Kurz-SHA und mit `origin/main` liefert
  dasselbe Ergebnis wie mit der vollen SHA (siehe AC-6).
- **V6:** Die fünf Meldungstexte werden dem PO im Wortlaut vorgelegt: versteht
  ein Nicht-Programmierer, *welcher* Stand fehlt und *was* zu tun ist?

## Rot werdende Bestandstests (beauftragter Spec-Wechsel, keine Regression)

Folgende Tests werden durch diesen Fix bewusst rot und müssen im selben
Workflow angepasst werden:

- `tests/tdd/test_e2e_path_helper.py::test_only_singleton_same_path` — prüft
  heute exakt den Rückfall auf die Sammeldatei, der entfernt wird.
- `tests/tdd/test_e2e_commit_namespacing.py::test_legacy_singleton_is_read_as_fallback`
  — Name und Erwartung sind der Rückfall selbst; wird umbenannt/umgedreht, nicht
  gelöscht ohne Ersatz.
- Vier `monkeypatch.setattr(..., "CANONICAL_E2E_PATH", ...)`-Zeilen in
  `test_e2e_verified_retention.py` und `test_issue_668_head_sha_dedup.py` —
  patchen eine Konstante, die entfällt.
- `tests/tdd/test_prod_selftest_564.py` (AC-5-Test „fehlende Datei → Exit 0") —
  wird auf die neue Regel (Exit 1 bei fehlendem Nachweis und Nicht-docs-only-
  Scope) umgestellt; siehe Abschnitt „Abgelöste Festlegung".

Alle fünf sind **beauftragte** Anpassungen an eine bewusst geänderte Regel, keine
unentdeckten Regressionen.

## Changelog

- 2026-07-25: Initial spec created (Issue #1382, zwei Scheiben in einem Workflow)
