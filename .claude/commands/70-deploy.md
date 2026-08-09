# Phase 8: Auslieferung nach Produktion (Gregor Zwanzig)

Ersetzt das generische `70-deploy`-Template des Plugins (Vercel/Heroku/AWS-Beispiele), das
mit diesem Projekt nichts zu tun hat. Der Ablauf hier ist der einzige gueltige.

**Läuft autonom, ohne Freigabe-Halt (PO-Vorgabe 2026-08-03, korrigiert 2026-08-05 via #1511).**
Die Kette Staging-Poll → `/e2e-verify` → Schritt 4 (Prod-Deploy) → Schritt 4b (Selftest) →
Issue-Close zieht **am Stück** durch, ohne auf ein `go` zu warten. Ein selbst formulierter
„Tech-Lead-Brief" mit anschließender Bitte um `go` ist eine verbotene Prozessfrage, nur in
Freitextform. Einzige erlaubte Unterbrechung: ein echtes Hard Gate scheitert (Staging-Verdict
BROKEN, Selftest-Exit ≠ 0) — dann eskalieren mit konkretem Befund statt weiterzumachen.

## Voraussetzungen

- `workflow.py status` ⇒ Phase `phase8_complete`, Adversary-Verdict VERIFIED (oder
  AMBIGUOUS mit ausdruecklichem PO-OK)
- Arbeitsbaum sauber, Branch auf `origin/main` (der Rebase-Waechter blockt sonst den Commit)

## Schritt 1 — Branch pushen, PR mergen (PO-go 2026-08-05: kein Direkt-Push auf main)

```bash
git push -u origin HEAD:<themen-branch>
gh pr create --fill
# CI-Ampel abwarten: alle 5 Checks gruen auf dem letzten Stand, sonst erst fixen
gh pr merge --merge
```

⚠️ Vorher `git fetch origin` und rebasen. **Nie `git stash`** (geteilter Stapel ueber alle
Arbeitsordner) — externe Sicherung anlegen, `git -c rebase.autoStash=true rebase origin/main`,
danach `md5sum -c` gegenpruefen. Der Autostash loest die Vormerkung teilweise auf: nach dem
Rebase erneut `git add`.

## Schritt 2 + 3 — Staging: `/e2e-verify`

**Sofort** `/e2e-verify` aufrufen — der Befehl enthaelt den aktiven Poll auf den
Staging-Stand (prueft den Commit, stoesst bei Abweichung `auto-deploy-gregor-staging.sh` an,
fasst 5× nach). **Kein eigenes Warten, keine selbstgebauten Poll-Schleifen, keine Ankuendigung
„ich warte 5 Minuten".**

`/e2e-verify` fuehrt auch die Nachweis-Ablage aus (Schritt 5 dort):
`staging_gate.py --write-verdict … --findings-json` legt `.claude/e2e_verified/<HEAD>.json`
in der **geteilten Ablage** an und loest den Pfad selbst auf.

🔴 **Die Nachweis-Datei NIE von Hand schreiben.** Wer attestiert, muss selbst gemessen haben —
ein selbst geschriebener Nachweis ist wertlos, egal wie ehrlich sein Inhalt ist. Wird die
Verifikation an einen Agenten delegiert, schreibt **dieser** die Attestation, nicht der
Orchestrierer. Sobald du das Format einer Nachweis-Datei nachschlaegst, um sie selbst zu
erzeugen: anhalten. Ein Format nachschlagen heisst, es gibt einen Erzeuger — und du bist es
nicht.

**Ausnahme reine Doku-/Werkzeug-Aenderungen** (nur `.md`/`docs/`/`.claude/`/`.gitignore`, kein
Code in `src/`/`api/`/`internal/`/`frontend/`/`cmd/`): Schritt 2+3 entfaellt, Schritt 4
ebenfalls, solange der Drift-Monitor ruhig ist. Im Zweifel trotzdem ausliefern.

## Schritt 4 — Prod-Deploy

```bash
bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh
```

`systemctl restart` allein reicht **nie**. Das Skript nimmt ein `flock`-Lock, synchronisiert
hart auf `origin/main` (Daten unberuehrt, WIP gesichert), baut Go-Binary + Frontend, startet
alle drei Dienste neu und macht einen Smoke-Test. Parallel-sitzungssicher — jederzeit aus
jeder Sitzung.

⚠️ **Das Skript liefert immer den aktuellen Gesamtstand aus, also auch fremde Commits.**
Danach pruefen und dem PO nennen:

```bash
git merge-base --is-ancestor <eigener-sha> <live-sha> && echo "eigene Arbeit ist live"
git log --oneline <eigener-sha>..<live-sha>   # was fuhr sonst mit?
```

## Schritt 4b — Post-Deploy-Selbsttest (hartes Tor)

```bash
python3 .claude/hooks/prod_selftest.py
```

**Nur Exit 0 faehrt weiter.**

⚠️ Bekannte Blindstelle: Der Selbsttest misst `HEAD~1..HEAD`. Ist der letzte Commit auf
`origin/main` eine Doku-Aenderung einer parallelen Sitzung, meldet er „docs-only —
uebersprungen" und Exit 0, obwohl Backend ausgeliefert wurde. `--e2e-path`/`--workflow`
ueberstimmen das **nicht**. Bei paralleler Arbeit zusaetzlich von Hand belegen: Code im
Prod-Checkout greppen (`git show HEAD:<datei>`), `systemctl show <unit> -p
ActiveEnterTimestamp`, `/api/health`.

## Schritt 5 — Abschluss

1. `workflow.py write-log success`, dann `workflow.py finish`
2. Ergebnis-Kommentar ans Issue: was live ist, was nachgewiesen wurde, **was offen blieb**,
   abgeleitete Meldungen
3. `gh issue close <N>` — **nur** wenn 4b Exit 0 lieferte **und** wirklich alles erledigt ist.
   Bei Scheiben-Arbeit (S2 AG1..AGn) bleibt das Issue offen, bis die letzte Scheibe steht.

## Verboten

- Prod-Deploy ohne bestandenen, frischen Nachweis fuer den Zielstand
- Einen eigenen Freigabe-Halt einbauen (Tech-Lead-Brief + `go` abwarten o.ae.) — die Kette
  laeuft autonom durch, ausser ein echtes Hard Gate scheitert
- Die Nachweis-Datei von Hand schreiben oder ihren Inhalt selbst formulieren, ohne gemessen
  zu haben
- Den lokalen Live-Server stoppen/neu starten · in laufende Systemd-Prozesse eingreifen
- „E2E bestanden" sagen ohne Staging-Verifikation
- Deploy aufschieben, „bis der Ordner sauber ist" — das Skript ist `flock`-serialisiert,
  diese Pattsituation existiert nicht

## Rollback

`docs/reference/operations_playbook.md` — dort stehen Rollback, Verdict-Ableitung
PASS/PARTIAL/FAIL/SKIP und der Detailablauf.
