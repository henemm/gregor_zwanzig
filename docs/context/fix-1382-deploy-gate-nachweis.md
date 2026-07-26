# Context: fix-1382-deploy-gate-nachweis

Issue: [#1382](https://github.com/henemm/gregor_zwanzig/issues/1382) — „Prod-Deploy-Gate liest anderen Nachweis als die Staging-Verifikation schreibt"
Track: Full Process · erstellt 2026-07-25 · Basis-Commit `ad06a4c8` (= `origin/main`)

## Request Summary

Der Prod-Deploy blockierte mit einer Meldung, die einen **fremden, 32 Tage alten** Commit nennt (`d850421a`), obwohl für den Zielstand schlicht kein Nachweis vorlag. Die Meldung führt in die Irre und erzeugt Druck, den Notfall-Schalter `GZ_SKIP_E2E_GATE=1` zu ziehen — also Gate-Erosion.

## Ist-Zustand (recherchiert, nicht vermutet)

### Schreibpfad — eindeutig, commit-benannt

`staging_gate.py:233-234, 331-332` schreibt **ausschließlich** `.claude/e2e_verified/<sha>.json`.
`<sha>` = HEAD des aufrufenden Worktrees (`:88`), Ablageort = geteiltes Hauptrepo (`:93`).

**Keine Codestelle schreibt die alte Sammeldatei `.claude/e2e_verified.json` noch.** Sie ist reines Altlast-Artefakt.

### Lesepfad — Rückfall auf die Altlast

`_e2e_paths.py:222-234` (`default_e2e_path`):

1. Nachweis für den gesuchten Commit vorhanden → den nehmen ✅
2. **sonst: alte Sammeldatei, falls vorhanden** ⬅ hier liegt der Defekt
3. sonst: den (nicht existenten) commit-benannten Pfad

Nutzer dieses Rückfalls: `staging_gate.py:109` (→ `gate_check`, also `--check` mit und ohne `--expected-commit`) und `prod_selftest.py:131`.
**Nicht** betroffen: `_nearest_verified_ancestor` (`staging_gate.py:378`) und der Merge-Lesepfad in `write_verdict` (`:288`) — beide greifen direkt auf den commit-benannten Pfad.

### Die Altlast selbst

`/home/hem/gregor_zwanzig/.claude/e2e_verified.json` — 205 Byte, zuletzt geändert **2026-06-23**, Inhalt nur zwei Felder:

```json
{ "verified_commit": "d850421a…", "staging_verdict": "VERIFIED — backend-only SMS-Fix: …" }
```

Kein `verified_at`, kein `scope`, keine `findings`. Beide Pfade sind gitignored (`.gitignore:42-43`), existieren nur im Hauptrepo, in **keinem** der 21 Worktrees.

### Kontrollfluss in `gate_check` (`staging_gate.py:449-500`)

```
e2e_path = _default_e2e_path(expected_commit)     # :450  ← Rückfall greift hier
data     = json.load(e2e_path)                    # :456-458
if verified_commit != ref:                        # :469
    → Ancestor-Relaxierung versuchen (#1197)      # :471-487  (docs-only-Zuwachs → OK)
    → if data is None: "Nachweis fehlt unter …"   # :488-494
    → else:            "verified_commit != …"     # :495-500  ← die irreführende Meldung
```

**Wirkung des Rückfalls im Deploy-Gate ist ausschließlich der Meldungstext** — der Exit-Code ist in beiden Zweigen 1. Das Gate hat also korrekt blockiert, nur mit falscher Begründung.

## Zwei Ursachen, sauber zu trennen

**Ursache A — Rückfall auf die Altlast (Meldungs-Defekt, Kern des Tickets).**
Fehlt der Nachweis für den Zielstand, wird eine fremde uralte Datei geladen und deren Commit gemeldet. Der Nutzer sucht am falschen Ende.

**Ursache B — der Zielstand ist ein bewegliches Ziel (nicht im Ticket erkannt).**
`deploy-gregor-prod.sh:90` setzt `TARGET=$(git rev-parse origin/main)`. Pusht eine Parallelsitzung dazwischen, ist der eigene Nachweis zwangsläufig nicht für `TARGET` — das Gate blockiert dann **zu Recht**. Genau das lag am 2026-07-25 vor: verifiziert war `66138d90`, `origin/main` war bereits `87304be2` (fremder Push).

Die im Ticket vorgeschlagene Lösung („`--write-verdict` muss beide Orte bedienen") würde Ursache A **verschlimmern**: sie schriebe die Altlast dauerhaft fort, statt sie loszuwerden.

## Ursache C — Fail-open im Post-Deploy-Selbsttest (BELEGT, aktuell scharf)

`prod_selftest.py` nutzt denselben Rückfall (`:131`), kennt aber **keinen** `--expected-commit` und relaxiert über Vorfahren (`:631-646`: nur `git merge-base --is-ancestor`).

**Im Sandkasten-Experiment nachgestellt und bestätigt** (Wegwerf-Repo, Hook-Kopien md5-identisch):

```
[prod-selftest] PASS (Ancestor): verified_commit=167297e0 ist Ancestor von HEAD=1a0e859d
EXIT: 0   →  Bericht: "Verdict: PASS — Issue-Close freigegeben."
```

Die Relaxierung prüft **ausschließlich** die Vorfahren-Beziehung. Belegt durch Varianten:

| Inhalt der Altlast | Ergebnis |
|---|---|
| `staging_verdict: "BROKEN — Staging kaputt"` | **Exit 0, „PASS (Ancestor)"** |
| gar kein `staging_verdict`-Feld | **Exit 0, „PASS (Ancestor)"** |
| `verified_commit` kein Vorfahre | Exit 1 |

Kein VERIFIED-Check, kein Alters-Check, keine Scope-Prüfung des Zuwachses — anders als `staging_gate._nearest_verified_ancestor` (`:385-397`), das alle vier Bedingungen prüft. **Die beiden Relaxierungen sind asymmetrisch.**

**Nicht theoretisch:** die echte Altlast (`d850421a`, 23.06.) ist Vorfahre des heutigen HEAD, Abstand **5262 geänderte Dateien**. `.claude/e2e_verified/` enthält **genau 20** Dateien = `ATTESTATION_RETENTION` (`staging_gate.py:54`) — der nächste Nachweis löscht den ältesten. Ein Rückfall ist damit **ein Retention-Ereignis entfernt**.

Einordnung: Ursache A lügt nur im Text. **Ursache C lügt im Ergebnis** — ein Kontrollmechanismus meldet Grün ohne Prüfung. Höhere Priorität als der Meldungsfehler.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/_e2e_paths.py:222-234` | `default_e2e_path` — der Rückfall selbst |
| `.claude/hooks/staging_gate.py:96-109` | Pfad-Auflösung mit `expected_commit` |
| `.claude/hooks/staging_gate.py:449-500` | `gate_check`: Reihenfolge Ancestor → fehlt → Mismatch, beide Meldungstexte |
| `.claude/hooks/staging_gate.py:225-335` | `write_verdict` — schreibt nur commit-benannt |
| `.claude/hooks/prod_selftest.py:124-131, 611-646` | Gleicher Rückfall, ohne Ziel-Commit, mit Vorfahren-Relaxierung |
| `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh:90-101, 129-135` | Aufrufer; `TARGET` aus `origin/main`; zweiter Lauf nach dem Reset |

## Existing Specs

| Dokument | Entscheidung |
|---|---|
| `docs/specs/_archive/modules/issue_662_e2e_commit_namespacing.md:64` | Führt den Rückfall ein, wörtlich `# Fallback (Migration)`, Begründung „laufende Workflows brechen nicht" — **ohne Frist, ohne Abschaltbedingung** |
| `docs/specs/_archive/modules/issue_665_e2e_path_helper.md:70-74` | Übernimmt die Kette 1:1 beim Extrahieren nach `_e2e_paths.py` |
| `docs/specs/_archive/modules/issue_666_e2e_verified_retention.md:62` | Schließt Aufräumen ausdrücklich aus: „Migrations-Artefakt, bleibt unberührt" |
| `docs/specs/modules/bundle_e_gate_tooling.md:97-98` | Out of Scope: „**Abkündigung des Singleton-Fallbacks** … (separat)" — das dort gemeinte Folge-Ticket wurde nie angelegt. **#1382 ist dieses Ticket.** |
| `docs/specs/_archive/modules/issue_1130_expected_commit_gate.md:25` | AC-2 fordert bereits, die Meldung solle die Diskrepanz gegen EXP benennen — Pfad-Auflösung wurde dort nicht betrachtet |
| `docs/specs/modules/fix_1197_deploy_gate_ancestor_scope.md:15` | Ancestor-Zweig ergänzt; Rückfall bewusst stehen gelassen |
| `docs/adr/0006-no-mocked-tests-e2e-staging.md` | Kennt nur die alte Sammeldatei als Hard Gate (#521); commit-benannte Ablage kommt dort nicht vor → **ADR-Nachzug prüfen** |

## Test-Abdeckung

Vorhanden: `test_e2e_path_helper.py` (#665), `test_e2e_commit_namespacing.py` (#662), `test_e2e_verified_retention.py` (#666), `test_staging_gate.py`, `test_staging_gate_ancestor_scope.py` (#1197), `test_staging_gate_verdict_merge.py`, `test_issue_784_staging_gate_worktree_head.py`, `test_prod_selftest_564.py`, `test_fix_853_842_837_tooling_gates.py`.

**Lücke — genau der Fall aus #1382 ist nirgends abgedeckt:** „für den Ziel-Commit existiert kein Nachweis, aber eine alte Sammeldatei mit fremdem Commit liegt da".

- `test_e2e_commit_namespacing.py:197` schließt die Sammeldatei im Fremd-Commit-Test per `assert not (…).exists()` explizit aus
- `test_e2e_commit_namespacing.py:153` betritt den Rückfall gar nicht (commit-benannte Datei ist vorhanden)
- alle `--expected-commit`-Tests (`test_staging_gate.py:488-585`) übergeben `--e2e-path` explizit → **die Kombination Preflight + Rückfall ist von keinem Test ausgeführt**
- `test_e2e_path_helper.py` maskiert den Unterschied zwischen den beiden `_default_e2e_path`-Varianten, weil es beide auf dasselbe `REPO_DIR` umbiegt

## Risks & Considerations

1. **Selbstbegünstigung.** Geändert wird genau das Gate, durch das diese Änderung selbst ausgeliefert wird. Eine unabhängige Instanz muss beweisen, dass es echt blockt (fehlender Nachweis → Exit 1), nicht nur, dass der Deploy durchgeht. (`feedback-no-self-modifying-gates`, hier vom PO beauftragt = zulässig.)
2. **Fail-closed bleibt Pflicht.** Jede Änderung muss in der sicheren Richtung irren: im Zweifel blockieren. Der mögliche Fail-open im Selbsttest ist ein Verschärfungs-, kein Lockerungsauftrag.
3. **Schreib-/Lesesymmetrie** (`reference_verdict_write_read_path_symmetry`, #1327/#1228): dieselbe Normalisierung auf beiden Seiten, sonst entstehen „erfolgreich geschriebene", faktisch tote Nachweise.
4. **Datei-Sperre.** `.claude/hooks/` ist durch `edit_gate.py` geschützt — der User muss einmal `override` tippen (Gültigkeit 1 Stunde), bevor der Developer-Agent dort schreiben kann.
5. **Zwei Aufrufer, ein Helfer.** `staging_gate` und `prod_selftest` teilen `default_e2e_path`, brauchen aber unterschiedliche Referenz-Commits. Eine Änderung am Helfer wirkt auf beide — Wirkung je Aufrufer getrennt prüfen.
6. **Altlast-Datei entfernen ist eine Datenfrage, keine Codefrage.** Sie ist gitignored und existiert nur auf diesem Server (Prod-Repo). Wird der Rückfall entfernt, ist die Datei wirkungslos; ein aktives Löschen wäre ein separater, dokumentierter Betriebsschritt.
7. **Abgrenzung.** Ursache B (bewegliches Ziel) ist kein Fehler des Gates. Was daran verbessert werden kann, ist die Verständlichkeit der Meldung — nicht die Prüflogik.

---

# Analysis (Phase 2)

Grundlage: Sandkasten-Experiment (Fail-open belegt), `analysis-challenger` (Verdict NEEDS REVIEW — Kern korrekt, zwei Lücken), Plan-Bewertung.

## Type

**Bug** — fälschlich blockierendes bzw. fälschlich freigebendes Gate (`[triage:c]`).

## Drei Ursachen, klar getrennt

| | Ursache | Wirkung | in diesem Workflow |
|---|---|---|---|
| **A** | Lesepfad fällt auf die Altlast zurück | nur **Meldungstext** falsch, Exit-Code unverändert 1 | ✅ ja |
| **B** | `TARGET=$(git rev-parse origin/main)` ist ein bewegliches Ziel | Gate blockt **zu Recht**, Meldung erklärt es nicht | ✅ Meldung; Auswegschalter → `infra` |
| **C** | Selbsttest relaxiert über Vorfahren ohne jede weitere Prüfung | **Fail-open**: meldet PASS ohne Prüfung | ✅ teilweise (s.u.) |

Bestätigt durch den Challenger: In `gate_check` führt **kein** Pfad vom Rückfall zu `return 0`. Auch der Zufallsfall „Altlast-Commit == Zielstand" bleibt fail-closed, weil `datetime.fromisoformat("")` auf dem fehlenden `verified_at` scheitert (`staging_gate.py:512-518`) — mit einer dritten, ebenfalls irreführenden Meldung.

## Ursache D (Randbedingung, nicht in diesem Ticket zu beheben)

Der Nachweis wird unter dem **Worktree**-HEAD benannt (`staging_gate.py:88`), aber im **Hauptrepo** abgelegt (`:93`). Wird vor dem Push rebased oder gequetscht — dokumentierte Praxis in diesem Projekt —, zeigt der Nachweis auf einen Commit, den `origin/main` nie enthält. Anders als B braucht das **keinen** Wettlauf; ein einziger Rebase genügt. Die Entfernung des Rückfalls behebt das nicht, sorgt aber für die richtige Meldung („Nachweis fehlt" statt Fremdcommit). **Als bekannte Grenze dokumentieren.**

## Nebenbefund (kein Scope, Sammel-Eintrag #1199)

Preflight mit `--expected-commit`, wenn HEAD bereits **gleich** dem Zielstand ist: Der Scope-Diff `HEAD..EXP` ist leer → gilt als `docs-only` → `gate_check` kehrt bei `:447` zurück, **ohne den Nachweis überhaupt zu öffnen** (Sandkasten F3, Exit 0). Im normalen Deploy-Ablauf harmlos (Preflight läuft vor dem Reset, HEAD ≠ TARGET), aber beim Wiederholungslauf eines bereits ausgecheckten Standes wird das Gate übersprungen. Der zweite Gate-Lauf (`deploy-gregor-prod.sh:130`) fängt es ab.

## Technischer Ansatz — Empfehlung

**Rückfall ersatzlos entfernen** (Option a), nicht „beide Orte bedienen" (Ticket-Vorschlag, würde die Altlast festschreiben) und nicht „Rückfall behalten + prüfen" (konserviert einen Pfad, der nur noch von Hand erreichbar ist).

1. `default_e2e_path()` entfällt aus `_e2e_paths.py`; beide Hooks lösen über **dieselbe Funktion** auf, die auch `write_verdict` benutzt (`commit_e2e_path`). Symmetrie strukturell erzwungen statt per Kommentar zugesichert — die Lehre aus #1327/#1228. `CANONICAL_E2E_PATH` fällt in beiden Hooks weg.
2. **SHA-Normalisierung** (eigener Fund): `gate_check` prüft die Auflösbarkeit von `--expected-commit` bereits (`:422-434`), **wirft das Ergebnis aber weg** und baut den Dateinamen aus dem Rohargument. `origin/main` oder eine Kurz-SHA erzeugen so einen Pfad, der nie existieren kann. Eine Zeile; erst damit ist „gleiche Normalisierung beidseitig" erfüllt.
3. **Fünf unterscheidbare Meldungen** statt heute drei ununterscheidbarer — insbesondere ein eigener Fall für B (Zielstand wurde weitergeschoben), der heute gar nicht als eigener Fall erkannt wird. Texte nennen den Zielstand, den Grund und den nächsten Schritt; **kein** Text nennt `GZ_SKIP_E2E_GATE` (Erosions-Treiber).
4. `prod_selftest` erhält dieselbe Pfad-Auflösung → Ursache C ist damit geschlossen (ohne Altlast kommt der Vorfahren-Zweig nie mehr an einen Fremdcommit).

**Wichtig zur Ehrlichkeit:** Diese Änderung macht die Meldung richtig und schließt den Fail-open — sie macht den am 2026-07-25 blockierten Deploy **nicht** durchlaufend. Die Blockade war sachlich korrekt (Ursache B).

## PO-Entscheidung 2026-07-25: Selbsttest-Verschärfung ist IN SCOPE

Vorgelegt wurde die Wahl „nur die Lüge schließen (Folge-Ticket)" vs. „beides in einem Zug". **PO: beides in einem Zug.** Damit kommt hinzu:

5. **Vorfahren-Relaxierung des Selbsttests auf die Gate-Bedingung ziehen.** `_nearest_verified_ancestor` wandert von `staging_gate.py:344-398` nach `_e2e_paths.py`; `staging_gate` delegiert, `prod_selftest` nutzt dieselbe Funktion. Danach existiert die Definition von „gültiger Nachweis" **einmal**. Die Ad-hoc-Prüfung `prod_selftest.py:631-646` (nur `merge-base --is-ancestor`) entfällt ersatzlos.
6. **Skip bei fehlendem Nachweis schließen:** `prod_selftest.py:614` `return 0` → `return 1`. **Das ändert eine ausdrücklich festgelegte Regel (#564 AC-5, „fehlende Datei → Exit 0 + INFO, Selftest übersprungen").** Muss als AC in der Spec stehen und die alte Regel ausdrücklich ablösen — kein stilles Umdrehen.

### Umsetzung in zwei getrennt prüfbaren Scheiben (Tech-Lead-Entscheidung)

Ein Gate-Eingriff muss unabhängig nachprüfbar bleiben; ein einzelner Groß-Diff wäre es nicht. Daher zwei Scheiben in **einem** Workflow, jede für sich rot→grün und jede für sich verifizierbar:

- **Scheibe 1 — Nachweis-Auflösung + Meldungen** (Punkte 1–4): Rückfall weg, SHA-Normalisierung, fünf Meldungen. Schließt Ursache A und C.
- **Scheibe 2 — Selbsttest so streng wie das Gate** (Punkte 5–6): gemeinsame Vorfahren-Bedingung, Skip → Block. Löst #564 AC-5 ab.

### LoC-Folge

Schätzung steigt von ~240 auf **~350** → das Limit von 250 wird überschritten. **`loc_limit_override` ist erforderlich und wird erst nach ausdrücklicher PO-Freigabe der Spec gesetzt**, nicht vorab.

## Affected Files

| Datei | Art | Beschreibung |
|---|---|---|
| `.claude/hooks/_e2e_paths.py` | MODIFY | `default_e2e_path()` entfernen (−13) |
| `.claude/hooks/staging_gate.py` | MODIFY | Pfad auf `_commit_e2e_path` reduzieren, `CANONICAL_E2E_PATH` weg, SHA-Normalisierung, Meldungs-Verzweigung (~65) |
| `.claude/hooks/prod_selftest.py` | MODIFY | Gleiche Pfad-Reduktion (~14) |
| `tests/tdd/test_deploy_gate_evidence_resolution.py` | CREATE | 5–7 Tests, u.a. Schreibziel == Lesequelle für dieselbe SHA (~110) |
| `tests/tdd/test_e2e_path_helper.py` | MODIFY | Rückfall-Erwartung umdrehen, monkeypatch-Zeile |
| `tests/tdd/test_e2e_commit_namespacing.py` | MODIFY | `test_legacy_singleton_is_read_as_fallback` → erwartet jetzt Exit 1 |
| `tests/tdd/test_e2e_verified_retention.py`, `test_issue_668_head_sha_dedup.py` | MODIFY | je 1 monkeypatch-Zeile auf entfallende Konstante |
| `CLAUDE.md`, `docs/adr/0006-…`, Spec-Modul | MODIFY | Abkündigung dokumentieren; ADR kennt nur die Sammeldatei |

**Testdatei-Name bewusst verhaltensbenannt**, nicht nach Issue-Nummer (Namensregel, `test_naming_gate.py`).

## Scope Assessment

- Dateien: 3 Quell-, 5 Test-, 3 Doku-Dateien
- Geschätzte LoC: **~240 / 250** — knapp. Kürzungshebel: neue Testdatei auf 5 Kerntests (Fälle „nicht VERIFIED" und „zu alt" sind durch Bestandstests abgedeckt).
- Risiko: **MEDIUM** — Eingriff am Produktions-Torwächter, aber ausschließlich in der sicheren Richtung (es wird nur entfernt, nie geöffnet).

## Risiko: was kann brechen

| Szenario | Bewertung |
|---|---|
| Ein bisher laufender Deploy blockiert | Nur möglich, wenn die Altlast `verified_commit == Zielstand` **und** VERIFIED **und** < 24 h alt trüge. Sie hat kein `verified_at` → blockt heute schon. **Rechnerisch ausgeschlossen.** |
| Fehler im neuen Meldungscode | Liegt ausschließlich auf Fehlerpfaden; eine Ausnahme dort ⇒ Exit ≠ 0 ⇒ blockt. Irrt sicher. |
| Selbsttest verliert Abdeckung | Realer, benannter Nachteil (s.o.), kein falsches PASS mehr |
| Prod in halbem Zustand | Ausgeschlossen: der Preflight läuft **vor** `systemctl stop` und `git reset --hard` |

**Rot werdende Bestandstests (vollständig, verifiziert):** `test_e2e_path_helper.py::test_only_singleton_same_path` (:100), `test_e2e_commit_namespacing.py::test_legacy_singleton_is_read_as_fallback` (:135), sowie vier `monkeypatch.setattr(..., "CANONICAL_E2E_PATH", ...)`-Zeilen. Das ist ein beauftragter Spec-Wechsel, keine Regression.

## Nachweis der Integrität (Pflicht — das Gate darf sich nicht selbst durchwinken)

`_detect_scope_from_git_diff` zählt `.claude/` und `tests/` als docs-only (`_e2e_paths.py:145-152`) — **dieser Fix deployt an seinem eigenen Gate vorbei.** „Der Deploy lief durch" ist deshalb **kein** Nachweis. Ebenso wenig ein grüner Testlauf im Worktree: die Altlast existiert nur im Hauptrepo.

Pflichtschritte für die unabhängige Instanz (auf `/home/hem/gregor_zwanzig`, `GZ_SKIP_E2E_GATE` ungesetzt, alle nebenwirkungsfrei — der Preflight schreibt bewusst keinen Marker):

- **V0 (VOR jeder Codeänderung, sonst für immer verloren):** Ist-Reproduktion protokollieren — `--check --expected-commit <alter, nicht attestierter Commit>` nennt `d850421a`.
- **V1** Dasselbe Kommando nachher: Exit 1, Meldung nennt den Zielstand und **nicht** `d850421a`.
- **V2 Negativkontrolle:** Commit ohne Attestation → Exit 1.
- **V3 Positivkontrolle:** frischer VERIFIED-Nachweis → Exit 0. **V2 ohne V3 ist wertlos** — „blockt immer" sähe identisch aus.
- **V4** Altlast liegt weiterhin da, ist aber wirkungslos: `grep -rn "e2e_verified\.json\|CANONICAL_E2E_PATH\|default_e2e_path" .claude/hooks/` → leer.
- **V5** `--expected-commit` mit Kurz-SHA und mit `origin/main` liefert dasselbe wie die volle SHA.
- **V6** Die fünf Meldungstexte im Wortlaut dem PO vorlegen: versteht ein Nicht-Programmierer, *welcher* Stand fehlt und *was* er tun muss?

## Empfehlung an `infra` (außerhalb dieses Repos, per MQ nach PO-Freigabe)

1. `deploy-gregor-prod.sh:100` streichen/umformulieren — die Zeile bewirbt `GZ_SKIP_E2E_GATE=1` bei **jedem** Block als nächsten Schritt. Der Mechanismus bleibt, der Werbetext gehört ins Runbook. Adressiert die Gate-Erosion direkter als jede Codeänderung.
2. `TARGET=${GZ_DEPLOY_TARGET:-$(git rev-parse origin/main)}` — gibt Ursache B einen legitimen Ausweg: den geprüften Stand ausliefern statt das Gate zu überspringen.
3. `origin/main` vor/nach `git fetch` protokollieren, damit ein Vorbeiziehen im Deploy-Log sichtbar wird.

## Open Questions

- [x] **Selbsttest-Verschärfung jetzt oder als Folge-Ticket?** → **PO 2026-07-25: jetzt, in einem Zug** (zwei Scheiben, s.o.)

## Nicht in diesem Workflow

- Änderungen an `deploy-gregor-prod.sh` (liegt in `henemm-infra`) — als MQ-Empfehlung an `infra` nach PO-Freigabe
- #1367/#1358 (Selbsttest wertet 401 als FAIL) — eigenständige Tickets
- Ursache D (Nachweis unter Worktree-SHA bei Rebase vor dem Push) — als bekannte Grenze dokumentieren, Fix separat
- Nebenbefund Preflight-Selbstreferenz (HEAD == Zielstand → docs-only-Skip) — Sammel-Eintrag #1199
