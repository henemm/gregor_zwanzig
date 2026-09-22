---
entity_id: systemhinweise_unter_konto_sheet
type: module
created: 2026-09-19
updated: 2026-09-22
status: approved
version: "1.0"
tags: [frontend, mobile-shell, pwa, konto-sheet, issue-2370]
---

# Systemhinweise am unteren Rand liegen nie über dem Konto-Sheet

Issue #2370 · Mobile-Audit 2026-09-19 (`docs/analysis/mobile-audit-2026-09-19.md`, P1-1) ·
Mobile-Shell S2 (#2364, `docs/design-requests/mobile_shell_ohne_topbar.md`)

## Approval

- [x] Approved (Henning, 2026-09-22)

## Purpose

Der iOS-Install-Hinweis („Auf den Startbildschirm legen …") liegt heute auf derselben z-Ebene wie
das Panel des Konto-Sheets und wird im DOM danach gerendert. Bei offenem Sheet überdeckt er die
Zeilen „Dunkles Design" und „Datenexport" und fängt deren Klicks ab. Das Konto-Sheet ist auf dem
Handy der einzige Weg zu Konto, Dunkelmodus und Abmelden — die Zeilen müssen immer bedienbar sein.

Die Zusicherung gilt für alle drei Systemhinweise am unteren Rand (iOS-Install, Update, Passkey-
Angebot): sie liegen **unter** der Sheet-Ebene und sind bei offenem Konto-Sheet **nicht sichtbar**.
Ein fälliger, nicht weggeklickter Hinweis kehrt nach dem Schließen des Sheets zurück.

## Source

- **File:** `frontend/src/routes/+layout.svelte` (Sichtbarkeit und z-Index der drei Hinweise)
- **Identifier:** `iosHinweisSichtbar`, `updateHinweisSichtbar`, `passkeyAngebotSichtbar`, `kontoOpen`
- **Unverändert:** `frontend/src/lib/components/mobile/Sheet.svelte` (Backdrop z 60, Panel z 61),
  `frontend/src/lib/components/ui/sidebar/KontoSheet.svelte`
- **Schicht:** Frontend (SvelteKit). Kein Go-, kein Python-Anteil.

## Estimated Scope

- **LoC:** Produktiv ~+6/−3 (Layout), Tests ~+120 (eine E2E-Datei)
- **Files:** 3 (`+layout.svelte`, neue E2E-Spec, `.github/ci_e2e_specs.txt`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Sheet.svelte` | Komponente | definiert die Sheet-Ebene (Backdrop 60, Panel 61), an der sich die Hinweise unterordnen |
| `pwa_update_erkennung.md` AC-7 | Spec | Vorrangregel Update-Hinweis ↔ iOS-Hinweis bleibt unberührt |

## Implementation Details

```
+layout.svelte
  const hinweiseErlaubt = $derived(!kontoOpen);
  {#if updateHinweisSichtbar && hinweiseErlaubt} … z-index: 59
  {#if iosHinweisSichtbar && hinweiseErlaubt}    … z-index: 59
  {#if passkeyAngebotSichtbar && hinweiseErlaubt} … z-index: 59
```

- Ein gemeinsamer abgeleiteter Zustand, keine drei Einzelregeln — die Regel „bei offenem
  Konto-Sheet keine Hinweise" steht an genau einer Stelle.
- z-Index aller drei Hinweise auf **59** (< Sheet-Backdrop 60, > `bottom-shell` 50). Die relative
  Reihenfolge der Hinweise untereinander bleibt über die DOM-Reihenfolge erhalten (Passkey nach
  iOS); die bisherigen Werte 60/61/62 hatten keine andere Funktion.
- Der Merker `gz-ios-install-hint` wird durch das Ausblenden **nicht** gesetzt: nur „Schließen"
  setzt ihn. Damit erscheint der Hinweis nach dem Schließen des Sheets wieder (AC-3).
- Kein neuer Baustein, keine neue Komponente (Pendant-Sperre unberührt).

## Expected Behavior

- **Input:** iOS-Safari-UA außerhalb der installierten App, Merker nicht gesetzt ⇒ Hinweis fällig;
  Nutzer tippt den Konto-Kreis.
- **Output:** Während das Sheet offen ist, existiert kein `ios-install-hint` (und kein anderer
  Rand-Hinweis) im DOM; jede Sheet-Zeile ist an ihrer Mitte das oberste Element. Nach dem Schließen
  ist der Hinweis wieder sichtbar.
- **Side effects:** keine (kein Storage-Zugriff durch das Ausblenden).

## Acceptance Criteria

- **AC-1:** Given iOS-Safari (nicht installiert, Merker nicht gesetzt) auf 390×844 und der
  Install-Hinweis ist sichtbar / When der Nutzer den Konto-Kreis antippt / Then ist
  `data-testid="ios-install-hint"` nicht mehr im DOM, solange das Konto-Sheet offen ist.
  - Test: E2E, Vorbedingung `toBeVisible`, danach `toHaveCount(0)` bei sichtbarem `konto-sheet`.

- **AC-2:** Given das Konto-Sheet ist offen (390×844 **und** 375×667) mit fälligem
  Install-Hinweis / When `document.elementFromPoint` auf die Mitte jeder der fünf Zeilen
  (`konto-sheet-kanaele`, `-einstellungen`, `-status`, `-dark`, `-export`) und des Abmelden-Knopfs
  gesetzt wird / Then liegt der getroffene Knoten innerhalb der jeweiligen Zeile (`closest` trifft
  die Zeile) — kein Hinweis, kein Backdrop.
  - Test: E2E, `evaluate` mit `getBoundingClientRect` + `elementFromPoint` je Zeile, beide Viewports.

- **AC-3:** Given der Install-Hinweis war fällig und wurde **nicht** geschlossen / When der Nutzer
  das Konto-Sheet über „Schließen" wieder zumacht / Then ist der Install-Hinweis erneut sichtbar und
  der Merker `gz-ios-install-hint` ist weiterhin nicht gesetzt.
  - Test: E2E, nach `Schließen` `toBeVisible` + `localStorage.getItem` ist `null`.

- **AC-4:** Given ein Rand-Hinweis und das Konto-Sheet würden gleichzeitig gerendert / When man die
  z-Ebenen vergleicht / Then liegt jeder Rand-Hinweis (iOS, Update, Passkey) unter dem Sheet-Backdrop
  (z-Index < 60) — Regressionsschutz, falls die Ausblendung künftig entfällt.
  - Test: E2E, `getComputedStyle(hinweis).zIndex` bei geschlossenem Sheet < 60 (iOS-Hinweis; die
    beiden anderen Hinweise teilen dieselbe Konstante und werden per Grep-Wächter im selben Test
    nicht geprüft — sie sind über den gemeinsamen `hinweiseErlaubt`-Zustand mit abgedeckt).

- **AC-5:** Given der Nutzer klickt den Hinweis auf „Schließen" / When er danach das Konto-Sheet
  öffnet und schließt / Then bleibt der Hinweis weg (bestehendes Verhalten AC-15 aus
  `pwa_installierbar_offline_start.md` unverändert).
  - Test: E2E, `toHaveCount(0)` nach Sheet-Zyklus.

## Known Limitations

- Bezieht sich auf das Konto-Sheet des Layouts. Sheets innerhalb der Seiten (Wegpunkte, Etappen)
  bekommen die Hinweise ebenfalls unter sich (z 59 < 60), aber keine Ausblendung — dort ist der
  Bereich über der Tabbar Teil des Sheet-Panels und die Hinweise sind verdeckt, nicht überdeckend.
- Der Stapel Sticky-CTA-Footer + Hinweis + Tabbar auf `/compare/new` (Audit P1-6) bleibt offen
  (#1199).
- Eine z-Index-Token-Skala (`--g-z-*`, Audit P4-5) ist nicht Teil dieser Änderung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Ebenen-/Sichtbarkeitsregel innerhalb der bestehenden Mobile-Shell; keine
  Entscheidungsfläche (Kanal, Provider, Datenmodell, Auth) berührt.

## Changelog

- 2026-09-19: Initial spec created (Issue #2370, aus Mobile-Audit P1-1)
