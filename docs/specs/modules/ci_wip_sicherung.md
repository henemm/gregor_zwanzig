---
entity_id: ci_wip_sicherung
type: bugfix
created: 2026-08-21
updated: 2026-08-21
status: draft
version: "1.0"
tags: [ci, deploy, wip-safety]
---

# CI-WIP-Sicherung vor `git reset --hard` im Haupt-Checkout

## Approval

- [x] Approved — PO-Freigabe 2026-08-21 („freigabe"), alle 8 ACs

## Purpose

Der CI-Schritt „Staging-Verdict schreiben (CI smoke)" führt bei jedem Merge nach `main` ein
`git reset --hard origin/main` im Haupt-Checkout `/home/hem/gregor_zwanzig` aus — ohne
WIP-Sicherung. Dieser Checkout ist zugleich das Arbeitsverzeichnis interaktiver Sessions und
der Produktions-Serving-Ordner. Ein neues Skript `scripts/wip_safety.sh` sichert
uncommittete getrackte Änderungen als Stash-Objekt + Tag, bevor der Reset sie verwirft, nach
dem bewährten Vorbild aus `deploy-gregor-prod.sh`.

## Source

- **File:** `scripts/wip_safety.sh` (neu)
- **Identifier:** Shell-Skript, aufgerufen mit einem Repo-Pfad als Argument

## Estimated Scope

- **LoC:** ~60
- **Files:** 2
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `deploy-gregor-prod.sh:149-161` | Referenz-Skript (henemm-infra) | Liefert das zu kopierende Sicherungsmuster (`git stash create` + Tag + Wiederherstellungs-Hinweis) |
| `.claude/hooks/staging_gate.py:97-110` | Konsument (indirekt) | `_head_sha()`/`_verified_repo_dir()` sind cwd-basiert — deshalb bleibt der Reset selbst funktional nötig |
| `.github/workflows/ci.yml:456-474` | Aufrufer | Ruft `wip_safety.sh` künftig vor dem `git reset --hard` auf |

## Implementation Details

`wip_safety.sh <repo_dir>`:

1. Wechselt nicht in `<repo_dir>` per `cd`, sondern arbeitet mit `git -C <repo_dir>`, damit das
   Skript aus einem beliebigen Ort aufgerufen werden kann.
2. Prüft, ob der Arbeitsbaum schmutzig ist (`git -C <repo_dir> diff --quiet` und
   `git -C <repo_dir> diff --cached --quiet`). Ist er sauber: keine Aktion, Exit 0.
3. Ist er schmutzig: `SAFETY=$(git -C <repo_dir> stash create "ci-wip-safety $(date -u +%FT%TZ)")`.
   Bewusst `stash create`, nicht `stash push` — der Arbeitsbaum bleibt unverändert, weil er mit
   anderen Sessions geteilt wird.
4. Ist `$SAFETY` leer (Stash-Objekt konnte nicht erzeugt werden, obwohl der Baum schmutzig ist):
   Fehlermeldung auf stderr, die explizit benennt, dass ungesicherte Arbeit vorliegt, Exit
   ungleich 0. Das Skript darf in diesem Fall keinen Erfolg vortäuschen — der Aufrufer (CI)
   muss den nachfolgenden `git reset --hard` unterlassen.
5. Ist `$SAFETY` gesetzt: Tag `deploy-safety/ci-$(date -u +%Y%m%d-%H%M%S)` auf das Stash-Objekt
   setzen (`git -C <repo_dir> tag <TAG> <SAFETY>`), dann eine Meldung mit dem vollständigen
   Wiederherstellungs-Befehl ausgeben, analog zur Zeile in `deploy-gregor-prod.sh:159`
   (`git -C <repo_dir> stash apply <SAFETY>` bzw. über den Tag-Namen).
6. Untrackte Dateien werden nicht angefasst — `git stash create` erfasst sie standardmäßig
   nicht, und `git reset --hard` lässt sie ebenfalls unberührt. Die Abdeckung ist damit
   deckungsgleich mit dem tatsächlichen Schaden des nachfolgenden Resets.

`.github/workflows/ci.yml` — Schritt „Staging-Verdict schreiben (CI smoke)": vor der
bestehenden `ssh ... "cd /home/hem/gregor_zwanzig && git fetch origin && git reset --hard
origin/main && ..."`-Zeile wird ein Aufruf von `wip_safety.sh` eingefügt. Das Skript wird dabei
aus `origin/main` bezogen (z. B. `git show origin/main:scripts/wip_safety.sh | bash -s --
/home/hem/gregor_zwanzig` oder ein `git fetch` + `git show`-Äquivalent per SSH), nicht aus dem
Arbeitsbaum des Servers — beim allererstmaligen Rollout liegt das Skript dort noch nicht auf
dem aktuellen Stand (Henne-Ei, siehe Context-Doc Punkt 5). Schlägt die Sicherung fehl (Exit
ungleich 0), bricht der CI-Schritt ab, bevor der Reset läuft.

## Expected Behavior

- **Input:** Pfad zu einem Git-Repo-Verzeichnis als einziges Argument.
- **Output:** Bei schmutzigem Baum ein Tag `deploy-safety/ci-<UTC-Zeitstempel>` plus eine
  stdout-Meldung mit dem vollständigen Wiederherstellungs-Befehl; bei sauberem Baum keine
  Ausgabe und Exit 0.
- **Side effects:** Legt im Erfolgsfall genau ein Git-Tag an, der auf ein Stash-Commit-Objekt
  zeigt. Verändert weder den Arbeitsbaum noch die Staging-Area noch untrackte Dateien.

## Acceptance Criteria

- **AC-1:** Given im Ziel-Repo liegt eine uncommittete Änderung an einer getrackten Datei /
  When `wip_safety.sh <repo>` läuft und danach `git reset --hard origin/main` ausgeführt wird /
  Then existiert ein Tag `deploy-safety/ci-<Zeitstempel>`, und `git stash apply <Tag>` stellt
  die Änderung inhaltlich wieder her.
  - Test: Echtes Wegwerf-Git-Repo in Temp-Verzeichnis, echter Commit + echte uncommittete
    Änderung, Skript-Aufruf, dann Reset, dann `stash apply` gegen den erzeugten Tag — der
    Dateiinhalt danach entspricht dem vor dem Reset.

- **AC-2:** Given der Arbeitsbaum enthält uncommittete Änderungen / When `wip_safety.sh` läuft /
  Then ist der Arbeitsbaum danach unverändert (dieselben Dateien weiterhin modifiziert) — die
  Sicherung darf nichts wegnehmen, weil der Checkout mit anderen Sessions geteilt wird.
  - Test: `git diff` vor und nach dem Skript-Aufruf auf Gleichheit vergleichen (kein
    Dateiinhalt-Check auf Textform, sondern realer Diff-Vergleich).

- **AC-3:** Given eine Änderung ist gestaget (`git add`), aber nicht committet / When
  `wip_safety.sh` läuft und danach hart resettet wird / Then ist auch diese Änderung über den
  Tag wiederherstellbar.
  - Test: Wie AC-1, aber die Änderung wird vor dem Skript-Aufruf per `git add` gestaget statt
    ungestaget zu bleiben; `stash apply` liefert den gestageten Inhalt zurück.

- **AC-4:** Given der Arbeitsbaum ist sauber / When `wip_safety.sh` läuft / Then wird kein Tag
  angelegt, keine Fehlermeldung ausgegeben, und der Exit-Code ist 0.
  - Test: Frisches Repo ohne uncommittete Änderungen, Skript-Aufruf, Prüfung dass
    `git tag --list 'deploy-safety/ci-*'` leer bleibt und `$?` gleich 0 ist.

- **AC-5:** Given der Arbeitsbaum ist schmutzig, aber `git stash create` liefert kein
  Stash-Objekt / When `wip_safety.sh` läuft / Then ist der Exit-Code ungleich 0 und die
  Meldung nennt, dass ungesicherte Arbeit vorliegt — die Kette darf in diesem Fall NICHT mit
  einem harten Reset weiterlaufen.
  - Test: Repo-Zustand konstruieren, in dem `stash create` real leer zurückgibt (z. B. Repo
    ohne initialen Commit, sodass kein HEAD zum Vergleich existiert), Skript-Aufruf, Prüfung
    von Exit-Code und stderr-Text — kein Reset wird im Test danach ausgeführt.

- **AC-6:** Given eine Sicherung wurde angelegt / When die Ausgabe gelesen wird / Then enthält
  sie den vollständigen Wiederherstellungs-Befehl inklusive Tag-Namen, sodass die Arbeit ohne
  Zusatzwissen zurückgeholt werden kann.
  - Test: Ausgabe des Skript-Laufs aus AC-1 parsen und prüfen, dass der ausgegebene Befehl den
    exakten Tag-Namen enthält und beim tatsächlichen Ausführen die Datei wiederherstellt (nicht
    nur String-Presence, sondern realer Ausführungsnachweis).

- **AC-7:** Given untrackte Dateien liegen im Arbeitsbaum / When `wip_safety.sh` läuft und
  danach hart resettet wird / Then sind sie unverändert vorhanden — sie werden vom Reset
  ohnehin nicht angefasst und dürfen von der Sicherung nicht angerührt werden.
  - Test: Neue Datei ohne `git add` anlegen, Skript-Aufruf, dann `git reset --hard`, dann
    prüfen dass die Datei mit identischem Inhalt weiterhin existiert.

- **AC-8:** Given der CI-Schritt „Staging-Verdict schreiben (CI smoke)" in
  `.github/workflows/ci.yml` / When der Schritt gelesen wird / Then steht der Aufruf der
  Sicherung VOR dem `git reset --hard`, und das Skript wird aus `origin/main` bezogen, nicht
  aus dem Arbeitsbaum.
  - Test: `# doc-compliance-test` — Dateiinhalt-Prüfung auf `.github/workflows/ci.yml`:
    Position des `wip_safety.sh`-Aufrufs liegt textuell vor der Position von
    `git reset --hard origin/main`, und die Aufrufzeile referenziert `origin/main` als Quelle
    des Skripts.

## Known Limitations

- Untrackte Dateien sind nicht durch die Sicherung abgedeckt — das ist beabsichtigt, weil der
  nachfolgende `git reset --hard` sie ohnehin nicht anfasst (siehe AC-7).
- Es gibt keine Retention/Aufräumung der `deploy-safety/ci-*`-Tags. Wildwuchs wird beobachtet,
  nicht in dieser Scheibe gelöst.
- Der CI-Verdict-Schritt stoppt `gregor-python.service` weiterhin nicht vor dem Reset (anders
  als `deploy-gregor-prod.sh`) — notierter Nebenbefund für Scheibe 2 von #2047, hier nicht
  behoben.
- Die Wirkungslosigkeit des Prod-Gates selbst (Kern von #2047) ist nicht Gegenstand dieser
  Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Es handelt sich um eine punktuelle Härtung eines bestehenden CI-Schritts
  (WIP-Verlust verhindern), nicht um eine neue Grundsatzentscheidung zu Test- oder
  Deploy-Strategie — der Reset selbst bleibt unverändert bestehen, es wird nur ein
  Sicherheitsnetz nach bereits etabliertem Muster (`deploy-gregor-prod.sh`) ergänzt.

## Changelog

- 2026-08-21: Initial spec created
