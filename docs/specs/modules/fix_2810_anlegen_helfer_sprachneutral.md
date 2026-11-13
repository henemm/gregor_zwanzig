---
entity_id: fix_2810_anlegen_helfer_sprachneutral
type: bugfix
created: 2026-11-13
updated: 2026-11-13
status: draft
version: "1.0"
workflow: fix-2810-anlegen-sprachneutral
tags: [e2e, i18n, mobile, sheet, iconbtn]
---

# Fix #2810: E2E-Helfer anlegenPflicht sprachneutral (Sheet-Schließen-Knopf mit Kennung)

## Approval

- [ ] Approved

## Purpose

Der E2E-Helfer `anlegenPflicht()` soll Anlegen-Abläufe auch mit einem Konto der Profil-Sprache Englisch durchlaufen können. Dafür darf er keine deutschen Beschriftungen als Locator nutzen; der letzte Rest ist der Schließen-Knopf des Orte-Bibliotheks-Sheets im mobilen Vergleich-Anlegen.

## Source

- **File:** `frontend/e2e/helpers.ts`
- **Identifier:** `anlegenPflicht` (Zeile ~1260), dazu `IconBtn` (`frontend/src/lib/components/mobile/IconBtn.svelte`) und `Sheet` (`frontend/src/lib/components/mobile/Sheet.svelte`, Zeile 131)

Schicht: Frontend (SvelteKit) plus E2E-Helfer. Go-API und Python-Core sind nicht berührt.

Querschnitts-Prüfpunkte:

- **Trip/Ortsvergleich-Teilung:** Sheet und IconBtn sind bereits gemeinsame mobile Bausteine; keine neue Komponente, kein Pendant nötig.
- **Mandantentrennung:** nicht berührt (keine Nutzerdaten bewegt, nur ein Attribut am Knopf und ein Test-Locator).
- **Kanäle:** nicht berührt (kein Briefing- oder Alarm-Inhalt).

## Scope

- **Im Scope:** Der Schließen-Knopf des Bibliotheks-Sheets bekommt die Kennung `sheet-close` (über ein optionales `testid`-Prop an `IconBtn`); `anlegenPflicht` nutzt diese Kennung statt der deutschen Beschriftung; eine neue E2E-Spec belegt den Ablauf mit englischem und deutschem Konto.
- **Nicht im Scope:** weitere Specs mit `aria-label="Schliessen"`, deutsche Beschriftungen in `ANLEGE_SEL` (Nebenbefund Sammel-Issue #1199).

## Definition of Done

- `anlegenPflicht` enthält keinen beschriftungsabhängigen Locator mehr.
- Vergleich (mobil) und Trip (mobil) lassen sich mit englischem und mit deutschem Konto anlegen, das Orte-Fenster schließt sich.
- Die sichtbare Beschriftung des Schließen-Knopfes bleibt übersetzt (de „Schliessen", en „Close").
- Neue E2E-Spec grün, bestehende Anlegen-Specs unverändert grün.

## Estimated Scope

- **LoC:** ~+60/-3 (davon überwiegend neue E2E-Tests)
- **Files:** 4 (IconBtn, Sheet, helpers.ts, neue E2E-Spec)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/mobile/IconBtn.svelte` | Komponente | bekommt optionales `testid`-Prop |
| `frontend/src/lib/components/mobile/Sheet.svelte` | Komponente | setzt Kennung `sheet-close` am Schließen-Knopf |
| `frontend/src/lib/components/compare/CompareNewEditor.svelte` (~706) | Komponente | öffnet das Orte-Bibliotheks-Sheet im mobilen Vergleich (nur Konsument, unverändert) |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | Katalog | Schlüssel `aktionen.schliessen` (de „Schliessen", en „Close"), unverändert |
| `PUT /api/auth/profile` (`language`) | API | setzt die Profil-Sprache des Test-Kontos in den E2E-Tests (bestehendes Muster, z. B. `s3a2794-teil3-englisch.spec.ts`) |
| #2881 Lieferung B | Vorarbeit | Reiter-Kennungen `tn-mobile-tab-etappen` / `trip-new-tab-etappen` (Teil 1 von #2810, bereits erledigt) |

## Implementation Details

Ist-Stand der Prüfung: In `anlegenPflicht` und den genutzten Helfern (`tripGpxHochladen`, `tippeDatum`, `ANLEGE_SEL.route.name`, `ANLEGE_SEL.vergleich.name`, `ANLEGE_SEL.vergleich.reiter`) steht genau noch ein deutscher Locator: `button[aria-label="Schliessen"]:visible` in Zeile ~1260. `tripGpxHochladen` (CSS-Klassen und `input[type=file]`), `tippeDatum` (`data-segment`) und die Namens-/Reiter-Locator des Vergleichs (`data-testid`) sind sprachneutral. Die übrigen deutschen Beschriftungen in `ANLEGE_SEL` (`TRIP_ANLEGE_LABEL`, `abbrechen`, `abschlussLabel`, `abschlussHinweis`) werden von `anlegenPflicht` nicht aufgerufen und bleiben außerhalb des Scopes.

Änderungen:

1. `IconBtn.svelte`: optionales Prop `testid?: string`, am `<button>` als `data-testid={testid}` gesetzt (ohne Prop kein Attribut). `aria-label={label}` bleibt unverändert.
2. `Sheet.svelte` (Zeile 131): `<IconBtn kind="close" onclick={onClose} label={$t('aktionen.schliessen')} testid="sheet-close" />`. Beschriftung bleibt über den Katalog übersetzt, der Katalog wird nicht angefasst.
3. `helpers.ts` (Zeile ~1260): `page.locator('button[aria-label="Schliessen"]:visible').click()` wird zu `page.locator('[data-testid="sheet-close"]:visible').click()`. Die `:visible`-Einschränkung bleibt, weil mehrere Sheets gleichzeitig im DOM liegen können (Strict-Mode-Schutz wie bisher).
4. Neue E2E-Spec (Name z. B. `frontend/e2e/anlegen-helfer-sprachneutral.spec.ts`) mit den Tests aus dem Test Plan.

Keine Änderung an Nutzertexten, Katalogen, Datenmodell oder Backend. Drawer (nutzt ebenfalls `IconBtn kind="close"`) bleibt unverändert; er bekommt keine Kennung, weil `anlegenPflicht` ihn nicht nutzt.

## Expected Behavior

- **Input:** `anlegenPflicht(page, 'vergleich', { name, mobil: true })` bzw. `anlegenPflicht(page, 'route', …)` mit einem Konto der Profil-Sprache `en` oder `de`.
- **Output:** Der Helfer läuft ohne Zeitüberschreitung bis zum Ende durch (Vergleich mobil: Sheet geöffnet, zwei Orte angehakt, Sheet wieder geschlossen).
- **Side effects:** Der Schließen-Knopf des mobilen Sheets trägt zusätzlich `data-testid="sheet-close"`; sichtbare und vorgelesene Beschriftung sind unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Konto mit Profil-Sprache en, mobiler Viewport, zwei frische Test-Orte WHEN `anlegenPflicht(page, 'vergleich', { mobil: true })` läuft THEN endet der Helfer ohne Fehler und das Orte-Bibliotheks-Sheet ist geschlossen (RED vor dem Fix: Locator `aria-label="Schliessen"` findet in en nur „Close" und läuft in die Zeitüberschreitung).
- [ ] Test 2: GIVEN dasselbe Setup mit Profil-Sprache de WHEN derselbe Aufruf läuft THEN identisches Ergebnis (Sheet geschlossen, Orte ausgewählt).
- [ ] Test 3: GIVEN geöffnetes Orte-Bibliotheks-Sheet im mobilen Vergleich, je Profil-Sprache de und en WHEN der Schließen-Knopf im Sheet-Kopf gelesen wird THEN trägt er die Kennung `sheet-close` und seine zugängliche Beschriftung ist „Schliessen" (de) bzw. „Close" (en); Klick schließt das Sheet.
- [ ] Test 4: GIVEN Konto mit Profil-Sprache en, mobiler Viewport WHEN `anlegenPflicht(page, 'route', { mobil: true })` läuft THEN wird Etappen-Reiter über die Kennung erreicht und je Etappe die GPX geparst, ohne Fehler (Regressionsschutz für Teil 1 aus #2881 B).
- [ ] Test 5: GIVEN Desktop-Viewport, Profil-Sprache en WHEN `anlegenPflicht(page, 'vergleich', …)` läuft THEN werden die Orte aus der Desktop-Bibliothek gewählt (Desktop-Pfad nutzt das Sheet nicht und bleibt unverändert).

Test-Politik: echter Browser gegen laufende Oberfläche, kein Mock, keine Dateiinhalt-Checks. Das en-Profil wird über `PUT /api/auth/profile` gesetzt und im Test-Abbau auf de zurückgesetzt (bestehendes Muster der englischen E2E-Specs); die Tests stützen sich auf den Konto-Zustand per API, nicht auf eine vom Menschen gepflegte Umgebungsvariable.

## Acceptance Criteria

- **AC-1:** Given ein Konto mit Profil-Sprache Englisch und ein mobiler Viewport / When der E2E-Helfer `anlegenPflicht` für einen Orts-Vergleich bis zum Ende läuft (Orte-Reiter, Bibliothek öffnen, zwei Orte anhaken, Sheet schließen) / Then endet er ohne Zeitüberschreitung und das Orte-Bibliotheks-Sheet ist geschlossen
  - Test: Nutzer mit englischer Oberfläche legt am Handy einen Vergleich an, wählt zwei Orte in der Bibliothek und schließt sie wieder.

- **AC-2:** Given ein Konto mit Profil-Sprache Deutsch und ein mobiler Viewport / When derselbe Helfer-Ablauf läuft / Then verhält er sich unverändert: Sheet geöffnet, zwei Orte angehakt, Sheet geschlossen, kein Fehler
  - Test: Nutzer mit deutscher Oberfläche durchläuft dasselbe Handy-Anlegen wie vorher; Ergebnis identisch.

- **AC-3:** Given das geöffnete Orte-Bibliotheks-Sheet im mobilen Vergleich / When der Schließen-Knopf im Sheet-Kopf geprüft wird / Then trägt er die Kennung `sheet-close`, seine Beschriftung bleibt übersetzt (Deutsch „Schliessen", Englisch „Close") und ein Klick schließt das Sheet
  - Test: Nutzer öffnet das Sheet in beiden Sprachen, liest die Beschriftung des Schließen-Knopfs und schließt damit das Sheet.

- **AC-4:** Given ein Konto mit Profil-Sprache Englisch und ein mobiler Viewport / When `anlegenPflicht` für einen Trip läuft (Name, Startdatum, Reiter Etappen, GPX je Etappe) / Then läuft er ohne Fehler durch, ohne dass eine deutsche Beschriftung gebraucht wird
  - Test: Nutzer mit englischer Oberfläche beginnt am Handy einen Trip und lädt die GPX-Dateien der Etappen hoch.

## Known Limitations

- Nicht im Scope: weitere E2E-Specs, die `aria-label="Schliessen"` direkt als Locator verwenden (u. a. hub-list-menu, compare-editor-fidelity-s8d, mobile-ux-audit, Kontrast-Specs). Sie laufen weiterhin nur mit Profil-Sprache de und werden als Nebenbefund (Sammel-Issue #1199) gemeldet; die neue Kennung `sheet-close` steht ihnen für eine spätere Umstellung zur Verfügung.
- Ebenfalls nicht im Scope: deutsche Beschriftungen in `ANLEGE_SEL` (`TRIP_ANLEGE_LABEL`, `abbrechen`, `abschlussLabel`, `abschlussHinweis`, `LISTE_SEL`), die `anlegenPflicht` nicht nutzt.
- Der Drawer (`IconBtn kind="close"`) erhält keine Kennung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein testbarer Kennungs-Zusatz an einem bestehenden Baustein nach etabliertem Muster (data-testid statt Beschriftungs-Locator, ADR-0104-konform: Nutzertexte bleiben im Katalog); keine neue Entscheidung über Kanäle, Provider, Datenmodell, Auth oder Teststrategie.

## Changelog

- 2026-11-13: Initial spec created (Issue #2810)
