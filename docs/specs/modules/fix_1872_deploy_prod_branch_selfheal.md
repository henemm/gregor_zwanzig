---
entity_id: fix_1872_deploy_prod_branch_selfheal
type: module
created: 2026-08-15
updated: 2026-08-15
status: draft
version: "1.0"
tags: [deploy, infra, bash, henemm-infra, issue-1872]
---

# Prod-Deploy: Selbstheilung statt Abbruch bei Fremd-Branch

## Approval

- [ ] Approved

## Purpose

`deploy-gregor-prod.sh` bricht den Prod-Deploy ab, sobald der Serving-Ordner
`/home/hem/gregor_zwanzig` nicht auf `main` steht — auch dann, wenn der Zielstand
`origin/main` vollständig verifiziert, attestiert und gemergt ist. Diese Spec macht
aus dem Abbruch eine Selbstheilung: das Skript stellt die Vorbedingung selbst her
(Wechsel auf `main` auf Stand `origin/main`), ohne Arbeit zu vernichten und ohne den
Normalpfad zu verändern.

## Source

- **File:** `/home/hem/henemm-infra/scripts/deploy-gregor-prod.sh`
- **Identifier:** Pre-Flight-Abschnitt (aktuell Zeilen 133–161: Branch-Check,
  Unpushed-Check, Stash-Sicherheitsnetz)

> **🔴 Anderes Repository:** Die zu ändernde Datei liegt in `henemm/henemm-infra`,
> **nicht** in `gregor_zwanzig`. Der Schicht-Hinweis des Templates (Frontend / Go-API /
> Python-Core) greift hier nicht — es handelt sich um ein Infrastruktur-Bash-Skript
> ohne Anwendungscode-Bezug. Die Spec liegt in `gregor_zwanzig`, weil das Issue
> (henemm/gregor_zwanzig#1872) und der Workflow hier geführt werden.

## Estimated Scope

- **LoC:** ~15–25
- **Files:** 1 (`scripts/deploy-gregor-prod.sh` im Repo `henemm-infra`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `henemm-infra/scripts/deploy-gregor-prod.sh` | Skript | Einzige zu ändernde Datei |
| `origin/main` (gregor_zwanzig) | Git-Remote-Ref | Zielstand des Deploys; Quelle für den erzwungenen Branch-Stand |
| `.claude/hooks/staging_gate.py` | Gate | Läuft unverändert NACH dem Pre-Flight gegen `origin/main` — die Änderung darf seine Position nicht verschieben |
| henemm-infra#193 | Folge-Issue | Strukturelle Lösung (dedizierter Prod-Checkout) — **nicht** Teil dieser Spec |

## Implementation Details

### Ist-Reihenfolge (heute)

```
1. git fetch origin --quiet
2. Branch-Check      -> BRANCH != main  =>  ABBRUCH (exit 1)
3. Unpushed-Check    -> Commits nicht auf origin/main  =>  ABBRUCH (exit 1)
4. Stash-Sicherheitsnetz (uncommittete getrackte Arbeit -> stash-Commit + Tag)
5. Staging-Gate-Preflight gegen origin/main
6. gregor-python stoppen
7. git reset --hard origin/main
```

### Soll-Reihenfolge

```
1. git fetch origin --quiet                    (unverändert)
2. Stash-Sicherheitsnetz                       (Block VORGEZOGEN, inhaltlich unverändert)
3. Branch-Selbstheilung statt Branch-Abbruch   (NEU)
4. Unpushed-Check                              (unverändert, läuft jetzt gegen das aktive main)
5. Staging-Gate-Preflight                      (unverändert)
6. gregor-python stoppen                       (unverändert)
7. git reset --hard origin/main                (unverändert)
```

**Warum das Vorziehen des Stash-Blocks zwingend ist:** `git stash create` arbeitet auf
dem noch unveränderten Arbeitsbaum und ist branch-unabhängig. Läuft er erst nach dem
Branch-Wechsel, ist die zu sichernde Arbeit bereits verworfen. Die Sicherung MUSS also
vor jedem Eingriff in den Arbeitsbaum stehen.

### Neuer Block 3 (Selbstheilung)

```bash
# Pre-Flight: Branch — Selbstheilung statt Abbruch (gregor_zwanzig#1872).
# Der Serving-Ordner ist zugleich Arbeitsordner interaktiver Sessions und steht
# deshalb regelmäßig auf einem Themen-Branch. Ein verifizierter, gemergter Stand
# darf daran nicht scheitern: das Skript deployt ohnehin ausschließlich
# origin/main, also stellt es die Vorbedingung selbst her.
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
    echo "${LOG_PREFIX} Hauptordner stand auf Fremd-Branch '$BRANCH' — schalte auf main um."
    git checkout -f -B main origin/main --quiet
    echo "${LOG_PREFIX} Auf main umgeschaltet (Stand origin/main). Branch '$BRANCH' bleibt als Ref erhalten — Rückkehr mit: git -C $REPO_DIR checkout $BRANCH"
    BRANCH=main
fi
```

**Begründung der Kommando-Wahl:**

- `-B main origin/main` erzwingt den lokalen Branch `main` auf `origin/main` — es
  funktioniert unabhängig davon, ob ein lokales `main` existiert, ob es divergiert und
  ob HEAD detached ist (`git rev-parse --abbrev-ref HEAD` liefert dort `HEAD`, also
  `!= main`, und läuft damit korrekt in denselben Zweig).
- Die Ref des Fremd-Branches wird **nicht** angefasst: `checkout -B main` schreibt nur
  `refs/heads/main`. Committete Arbeit auf dem Fremd-Branch bleibt vollständig
  erhalten und ist per `git checkout <branch>` wieder erreichbar.
- `-f` ist erforderlich, **nicht** optional: Der Stash-Block sichert die uncommittete
  Arbeit zwar, entfernt sie aber **nicht** aus dem Arbeitsbaum (`git stash create`
  erzeugt lediglich ein Commit-Objekt). Ohne `-f` scheitert der Wechsel mit
  „Your local changes would be overwritten by checkout", sobald eine geänderte Datei
  zwischen Fremd-Branch und `main` differiert — und der Deploy bliebe genau in dem
  Fall stecken, den diese Spec beheben soll. Die verworfenen Änderungen sind zu diesem
  Zeitpunkt bereits als Stash-Commit + Tag gesichert, und Schritt 7
  (`git reset --hard origin/main`) hätte sie ohnehin verworfen.
- Untracked Dateien (Live-Daten unter `data/`, Caches, Fixtures) bleiben unberührt:
  `checkout -f` fasst sie ebenso wenig an wie das bestehende `git reset --hard`
  (kein `git clean` — bewusst, siehe Kopfkommentar des Skripts).

### Block 4 (Unpushed-Check) — unverändert, neue Bedeutung

Der Check `git rev-list origin/main..HEAD --count` läuft jetzt gegen das frisch
gesetzte lokale `main`. Da `git checkout -B main origin/main` es exakt auf
`origin/main` setzt, ist der Zähler auf dem Selbstheilungspfad definitionsgemäß `0`.
Der Check bleibt trotzdem bestehen und blockiert weiterhin, wenn der Deploy **auf
`main` gestartet** wurde und dieses `main` unveröffentlichte Commits trägt — das ist
die einzige Konstellation, in der ein Deploy committete Arbeit vernichten könnte. Die
Historie des Fremd-Branches wird nicht mehr geprüft, weil sie nicht mehr betroffen ist.

## Expected Behavior

- **Input:** Aufruf `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` bei
  beliebigem Branch-Zustand von `REPO_DIR` und beliebigem Sauberkeitsgrad des
  Arbeitsbaums.
- **Output:** Bei Fremd-Branch zwei zusätzliche Log-Zeilen (Fremd-Branch-Name vor dem
  Wechsel, Bestätigung + Rückkehr-Kommando danach); danach identischer Deploy-Verlauf
  wie bei einem Start auf `main`. Exit-Code 0 bei Erfolg.
- **Side effects:**
  - `refs/heads/main` in `REPO_DIR` wird auf `origin/main` gesetzt; HEAD zeigt danach
    auf `main`.
  - Uncommittete getrackte Änderungen werden als Stash-Commit + Tag
    `deploy-safety/<UTC-Zeitstempel>` gesichert und anschließend aus dem Arbeitsbaum
    verworfen.
  - Die Ref des vorherigen Branches bleibt unverändert bestehen.
  - Untracked Dateien bleiben unverändert bestehen.

## Acceptance Criteria

- **AC-1:** Given `REPO_DIR` steht auf einem Fremd-Branch mit sauberem Arbeitsbaum und
  `origin/main` ist erreichbar / When der Pre-Flight-Abschnitt des Deploy-Skripts läuft
  / Then bricht er nicht ab, loggt den Wechsel unter Nennung des ursprünglichen
  Branch-Namens, HEAD steht danach auf `main` mit dem Commit von `origin/main`, und der
  Ablauf läuft unverändert bis zum Staging-Gate weiter.
  - Test: **Manuell** (kein automatisierter Test — Begründung unter „Known
    Limitations"). In einem Wegwerf-Verzeichnis unter dem Session-Scratchpad ein
    Bare-Remote plus Klon anlegen, im Klon `git checkout -b thema` und einen Commit
    setzen, dann den geänderten Pre-Flight-Abschnitt **aus der echten Skriptdatei**
    extrahieren (`sed -n '<von>,<bis>p' scripts/deploy-gregor-prod.sh`) und im Klon mit
    gesetztem `LOG_PREFIX`/`REPO_DIR` ausführen. Geprüft wird die Log-Ausgabe (enthält
    `thema`) **und** danach `git rev-parse --abbrev-ref HEAD` == `main` sowie
    `git rev-parse HEAD` == `git rev-parse origin/main`.

- **AC-2:** Given `REPO_DIR` steht auf einem Fremd-Branch **und** hat uncommittete
  getrackte Änderungen (inklusive einer Datei, die sich zwischen Fremd-Branch und
  `main` unterscheidet) / When der Pre-Flight-Abschnitt läuft / Then werden die
  Änderungen **vor** dem Branch-Wechsel als Stash-Commit gesichert und als Tag
  `deploy-safety/<Zeit>` referenziert, der Wechsel auf `main` gelingt trotz des
  schmutzigen Arbeitsbaums, und der gesicherte Stand ist per
  `git stash apply <sha>` vollständig wiederherstellbar.
  - Test: **Manuell**, gleiches Testverzeichnis wie AC-1. Vor dem Lauf eine getrackte
    Datei ändern (eine, die auf `main` anderen Inhalt hat) und eine zweite Änderung per
    `git add` stagen. Nach dem Lauf: `git tag -l 'deploy-safety/*'` liefert einen Tag,
    `git stash apply <sha>` stellt beide Änderungen inhaltlich wieder her (Dateiinhalt
    vergleichen, nicht nur Exit-Code), und eine zuvor angelegte untracked Datei liegt
    unverändert vor.

- **AC-3:** Given `REPO_DIR` steht bereits auf `main` (heutiger Normalfall) / When der
  Pre-Flight-Abschnitt läuft / Then findet **kein** Branch-Wechsel statt, es entsteht
  **keine** zusätzliche Log-Zeile zum Branch, und der Ablauf (Branch, HEAD, Exit-Code,
  Tag-Anzahl, `git status`, Reihenfolge Staging-Gate → Dienst-Stop →
  `git reset --hard origin/main`) verhält sich exakt wie vor der Änderung. Ausgenommen
  von der Deckungsgleichheit ist die Wiederherstellungs-**Hinweiszeile** im
  Stash-Sicherheitsnetz (nur relevant, wenn der Arbeitsbaum zusätzlich schmutzig ist):
  sie trägt seit dem F001-Fix (Runde 1) zusätzlich ein vorangestelltes
  `checkout main && ` — auf `main` ein wirkungsloses No-op, aber Text-technisch nicht
  mehr identisch zur unveränderten Fassung. Siehe Known Limitations.
  - Test: **Manuell**, gleiches Testverzeichnis. Klon auf `main` belassen, einmal mit
    sauberem und einmal mit schmutzigem Arbeitsbaum laufen lassen; Ablauf (Branch, HEAD,
    Exit-Code, Tag-Anzahl, `git status`) gegen einen Lauf mit der **unveränderten**
    Skriptfassung vergleichen (A/B gegen unverändertes Original) — deckungsgleich bis auf
    die oben benannte Ausnahme bei der Hinweiszeile. Zusätzlich
    `bash -n scripts/deploy-gregor-prod.sh` (Syntax-Check) ohne Befund.

- **AC-4:** Given das aktive `main` trägt selbst lokale, nicht auf `origin/main`
  gepushte Commits (Edge Case, nicht der gemeldete Fall) / When der Pre-Flight-Abschnitt
  läuft / Then bricht das Skript weiterhin mit Fehlermeldung und Exit-Code 1 ab, listet
  die betroffenen Commits, stoppt keinen Dienst und resettet den Arbeitsbaum nicht —
  committete Arbeit wird niemals still verworfen.
  - Test: **Manuell**, gleiches Testverzeichnis. Im Klon auf `main` einen lokalen Commit
    setzen, ohne zu pushen; Pre-Flight ausführen. Geprüft wird: Exit-Code 1, Meldung
    nennt die Commit-Anzahl, `git log --oneline origin/main..HEAD` ist Teil der Ausgabe,
    und `git rev-parse HEAD` ist danach unverändert (der Commit existiert noch).

## Known Limitations

- **Verifikation erfolgt manuell, nicht automatisiert.** `henemm-infra` hat keine
  Test-Suite für Bash-Skripte; es gibt weder pytest noch einen Test-Runner in diesem
  Repo. Präzedenzfall: henemm-infra#192 (`575d1cf`) — Verifikation über `bash -n` plus
  gezielte Reproduktion. Für diese Änderung ist das ausreichend, weil der betroffene
  Abschnitt **reine Git-Operationen** ohne Dienst-, Netz- oder Datenbezug enthält und
  sich deshalb vollständig in einem Wegwerf-Repo nachstellen lässt.
- **Ein echter End-to-End-Lauf gegen Produktion ist NICHT erforderlich.** Der geänderte
  Abschnitt liegt vor dem Staging-Gate, vor dem Dienst-Stop und vor dem Reset; ein
  Prod-Lauf würde nichts prüfen, was der isolierte Lauf nicht auch zeigt, aber echte
  Downtime riskieren.
- **AC-3 ist Erfolgspfad-Identität, nicht Bit-Identität über alle Pfade.** Durch das
  Vorziehen des Stash-Blocks entsteht im Abbruchfall AC-4 zusätzlich ein
  `deploy-safety/*`-Tag, das es vorher an dieser Stelle nicht gab. Der Unterschied ist
  bewusst und strikt sicherheitserhöhend (er sichert Arbeit, statt sie zu vernichten);
  er ist hier benannt, statt als „identisch" behauptet zu werden. Derselbe Grundsatz gilt
  seit dem F001-Fix (Adversary-Runde 1, Fix-Loop) auch für den schmutzigen Normalfall auf
  `main`: die Wiederherstellungs-Hinweiszeile trägt dort zusätzlich `checkout main && `
  vor dem `stash apply` — ein wirkungsloses No-op auf `main`, aber Text-technisch keine
  Bit-Identität mehr zur unveränderten Fassung. Grund: derselbe Codepfad erzeugt diese
  Zeile jetzt für ALLE Branch-Zustände einheitlich (main wie Fremd-Branch), weil genau
  diese Einheitlichkeit F001 behebt (Wiederherstellung ist auf jedem Ausgangsbranch
  konfliktfrei, nicht nur auf `main`). Eine Sonderbehandlung „auf main keinen Präfix
  ausgeben" wäre möglich, hätte aber wieder zwei Codepfade für denselben Zweck — bewusst
  nicht gemacht.
- **F001/F002 (Adversary-Runde 1, Fix-Loop) behoben:** `BRANCH` wird jetzt vor dem
  Stash-Block ermittelt (inkl. Sonderfall detached HEAD → SHA statt Literal `HEAD`), die
  Wiederherstellungszeile wechselt vor `stash apply` erst auf den Ausgangsstand zurück.
  Vom Developer Agent gegen beide Findings verifiziert (Fix-Loop Runde 1); unabhängige
  Adversary-Gegenprüfung (Runde 2/3) läuft/lief separat — Ergebnis im Adversary-Protokoll
  `docs/artifacts/fix-1872-deploy-branch-checkout/adversary-dialog.md`, nicht hier
  dupliziert.
- **Uncommittete Änderungen aus dem Fremd-Branch werden verworfen** (nach der
  Sicherung). Das ist kein Sonderfall dieser Änderung, sondern das dokumentierte
  Verhalten des Skripts (`git reset --hard origin/main`); der Fremd-Branch-Pfad erbt es
  lediglich mit. Wiederherstellung über den ausgegebenen Stash-SHA bzw. Tag.
- **`git stash create` erfasst keine untracked Dateien.** Unverändert gegenüber heute;
  untracked Dateien werden aber auch nicht angefasst.
- **Die strukturelle Kopplung bleibt bestehen:** Der Prod-Deploy hängt weiterhin am
  Zustand des Serving-/Session-Ordners. Die robuste Lösung (dedizierter Prod-Checkout
  analog `gregor_zwanzig_staging`) ist ausdrücklich **nicht** Teil dieser Spec, sondern
  Scope von henemm-infra#193. Ebenfalls nicht in dieser Spec: Anpassungen an
  `check-gregor20.sh`, `staging_gate.py`, `prod_selftest.py`, `hardening.conf` und dem
  `4:15`-Cronjob, die alle denselben hardcodierten Pfad tragen.
- **Nebenläufigkeit:** `flock` serialisiert nur konkurrierende Deploys. Eine parallel
  im Hauptordner arbeitende interaktive Session sieht den Branch-Wechsel als
  Fremdeinwirkung. Das ist unvermeidbare Folge davon, dass Serving-Ordner und
  Arbeitsordner identisch sind — und genau der Grund für henemm-infra#193.
- **`CLAUDE.md`-Aussage:** Die Zeile „Verboten: Deploy aufschieben ‚bis der Ordner
  sauber ist' — diese Pattsituation existiert nicht mehr" wird durch diesen Fix erstmals
  zutreffend. Kein Textnachzug nötig; falls der Fix nicht ausgeliefert wird, ist die
  Zeile weiterhin falsch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Verhaltenskorrektur eines bereits vorhandenen Sicherheitsnetzes
  im Deploy-Skript — das Skript deployte schon immer ausschließlich `origin/main`; neu
  ist nur, dass es die dafür nötige Vorbedingung selbst herstellt, statt sie vom
  Aufrufer zu verlangen. Es entsteht keine neue Deploy-Strategie und keine neue
  Entscheidungsfläche. Die ADR-pflichtige Grundsatzentscheidung (dedizierter
  Prod-Checkout, Dienst-Cutover) liegt bei henemm-infra#193.

## Changelog

- 2026-08-15: Initial spec created (Issue henemm/gregor_zwanzig#1872, PO-Entscheid
  „Option 2 jetzt, Option 1 als henemm-infra#193")
- 2026-08-15: Nach Adversary-Runde 1 (VERDICT: BROKEN, F001 HIGH + F002 MEDIUM + F003 LOW):
  AC-3-Wortlaut und Known Limitations präzisiert (Ausnahme der Wiederherstellungs-
  Hinweiszeile von der Deckungsgleichheit, verursacht durch den F001-Fix selbst).
  F001/F002 im Code behoben (Fix-Loop Runde 1), F003 betrifft nur die AC-1-Testvorschrift,
  nicht den Code — nicht als Spec-Änderung nachgezogen, siehe Adversary-Protokoll.
