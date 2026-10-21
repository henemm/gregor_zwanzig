# ADR-0098: Liefer-Workflow — `main` ändert sich nur per Pull Request mit sechs grünen Checks

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — PO-go 2026-08-05, Commit `ccc741493`, PR #1509)
- **Datum:** 2026-10-21
- **Bezug:** CLAUDE.md §„Liefer-Workflow (PFLICHT — PR statt Direkt-Push)" und §„CI-Ampel & Merge-Regel", Commits `d94acb574` (2026-08-04, CI-Ampel & Merge-Regel), `ccc741493` (2026-08-05, Direkt-Push abgeschafft), `27cc89c20` (2026-09-20, `--delete-branch`), Issues #1196 (CI-Rote), #1199 (Branch-Haufen); ADR-0054 (Playwright-E2E als sechster Check), ADR-0085 (CI-Deploy nur mit `/e2e-verify`-Nachweis)

## Kontext

Mehrere Sessions arbeiten parallel und liefern unabhängig aus; Integrationspunkt ist `origin/main`.
Direkt-Pushes auf `main` haben Rote hinterlassen, die wochenlang unbemerkt blieben (#1196:
„6 wochenlang unbemerkte test-Rote", Prüfdaten-Tabelle in `docs/reference/gates_und_ratschen.md`).
Ohne Aufräumen beim Merge wuchsen die Arbeitsbranches an (20.09.: 312 lokale Branches, 278 davon
Karteileichen, #1199).

## Entscheidung

1. **Direkt-Push auf `main` ist abgeschafft.** Arbeitsbranch pushen, PR eröffnen
   (`gh pr create --fill`), mergen (`gh pr merge --merge --delete-branch`).
2. **Merge-Regel:** Ein PR wird nur gemerged, wenn alle sechs Checks der CI-Ampel (`test`, `lint`,
   `go-test`, `svelte-check`, `frontend-test`, `e2e`) auf seinem letzten Stand grün sind. Fremde
   Rote auf der Basis werden erst grün gezogen oder belegt einer anderen Session zugeordnet und in
   #1196 gebucht — nie „auf Rot obendrauf".
3. **`--delete-branch` ist Pflicht** beim Merge; er räumt den Branch lokal und auf GitHub weg.
4. **Wird `main` trotzdem rot,** hat Drive-to-green Vorrang vor neuer Feature-Arbeit.
5. **Ein Merge ist kein Prod-Deploy.** Der CI-Job `deploy` liefert nur mit `/e2e-verify`-Nachweis
   aus (ADR-0085); ein PR ersetzt nicht die Staging-Validierung.

## Verworfene Alternativen

- **Direkt-Push mit nachgelagerter CI:** verworfen — Rote landen auf `main` und treffen alle
  parallelen Sessions.
- **Merge ohne Branch-Löschung:** verworfen — Branch-Haufen (#1199).

## Konsequenzen

- **Positiv:** `main` bleibt grün; jede Session hat eine verlässliche Basis.
- **Negativ / Preis:** Jede Lieferung wartet auf die volle Ampel, auch kleine Änderungen.
- **Folgepflichten:** Den mechanischen Schalter (Branch-Protection) setzt der PO; bis dahin gilt die
  Regel organisatorisch, ein Direkt-Push ist ein Regelverstoß. Die CI-Ampel trägt Prüfdatum
  2026-11-02 (Regel-Budget, ADR-0100).
