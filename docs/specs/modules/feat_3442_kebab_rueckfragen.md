---
entity_id: feat_3442_kebab_rueckfragen
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: feat-3442-kebab-rueckfragen
tags: [hub, kebab, menue, rueckfrage, i18n, "#3442", "#2797", "#2791"]
---

# S5c: Rückfragen im Kebab-Menü (Archivieren, Löschen) in Trip- und Orts-Vergleich-Hub

## Approval

- [ ] Approved

## Purpose

Das Kebab-Menü (⋮) im Kopf des Trip-Hubs und des Orts-Vergleich-Hubs fragt bei „Archivieren …“ und „Löschen …“ im Menü selbst nach, statt einen eigenen Dialog zu öffnen. „Abbrechen“ führt zur Menüliste zurück und ändert nichts; erst die Bestätigung schreibt. Danach erscheint eine einheitliche Erfolgs- oder Fehlermeldung. Der Orts-Vergleich archiviert heute ohne Rückfrage und springt zur Liste; er bekommt dieselbe Rückfrage und bleibt auf der Seite. Grundlage sind die PO-Entscheidungen K14/K15 in #2797 Punkt 4 und das Mockup Fassung 4 (`renderKebab()`, Klick-Logik).

## Source

- **File:** `frontend/src/lib/components/molecules/SubscriptionKebab.svelte`, `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte`, `frontend/src/lib/components/shared/kebabBestaetigung.ts` (neu), `frontend/src/lib/components/shared/KebabBestaetigungPanel.svelte` (neu)
- **Identifier:** `SubscriptionKebab` (Desktop-Dropdown), `SubscriptionActionSheet` (mobil), `kebabBestaetigung` (reines Modell: `braucheRueckfrage`, `rueckfrage`, `erfolgsText`, `fehlerText`), `KebabBestaetigungPanel`

> **Schicht:** ausschließlich Frontend (SvelteKit, `frontend/src/...`). Es gibt keine Änderung an Go-API oder Python-Core; die Aktionen laufen weiter über die bestehenden Endpunkte (`subscriptionExec`).
> **Trip/Orts-Vergleich:** ein Code. Kebab, Blatt, Panel und Modell sind geteilt (ADR-0097, #1170); die Seiten unterscheiden sich nur im Aufruf der bestehenden Aktionen. Keine Compare-eigene Komponente.
> **Kanäle:** nicht betroffen (keine Briefing- oder Alarminhalte).

## Estimated Scope

- **LoC:** Produktivcode ca. 350, Tests ca. 250 (ca. 500 insgesamt)
- **Files:** ca. 10 Produktiv-/Katalogdateien, dazu 3 Test-Neuanlagen und 8 umgestellte Bestandstests
- **Effort:** medium

**Scope-Hinweis:** Die Größe liegt über dem Projektlimit `scope_guard.max_loc_delta: 250`. Der Workflow setzt dafür `loc_limit_override 400` (Produktivcode) und `test_loc_limit_override 500` (Tests, weil acht Bestandstests auf die Rückfrage im Menü umgestellt statt gelöscht werden), wie bei #3440. Begründung: Menü, mobiles Blatt und beide Seiten müssen zusammen umgestellt werden, sonst bleibt der Hub halb mit Dialog und halb mit Rückfrage im Menü. Es sind keine Änderungen an der Gate-Konfiguration und keine Schritte vorgesehen, die ein menschliches Override brauchen (Autark-Modus).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/subscriptionActions.ts` | module | Einzige Aktionsquelle des Hubs (pause/resume, archive/unarchive, delete); Labels „Archivieren …“ / „Löschen …“ |
| `shared/subscriptionExec.ts` (`SubscriptionExecError`) | module | Fehlerklassifikation (Status, Detail) für Fehlertexte |
| `shared/hub-kopf/HubKopf.svelte` | component | Reicht Aktionen und neu `name` an den Kebab |
| bits-ui `DropdownMenu` (2.17.3) | atom | Item-`onSelect` mit abbrechbarem Event; `preventDefault()` hält das Menü offen |
| `Sheet` | atom | Mobiles Aktionsblatt (≤899 px) |
| `ConfirmDialog` | molecule | Bleibt für Listen und andere Orte; im Hub entfällt er für Archivieren/Löschen |
| `molecules/TestSchickenMenue.svelte`, `testSchickenModell.ts` (#3440) | module | Vorbild: reines Modell + Katalogtexte per `tr()`/`$locale` |
| `shared/__tests__/aktionsmodell_seiten_bindung.test.ts`, `aktionsmodellAst.ts` | test | Vorbild für Seitenbindung per AST ohne DOM |
| Katalog `frontend/src/lib/i18n/messages/{de,en}/` | i18n | Schlüssel `aktionen.archive/unarchive/delete/pause/resume/abbrechen`, `listen.archiv.endgueltig_loeschen`, neue Schlüssel `aktionen.kebab.*` |
| `docs/context/einstellungen_neu/elementliste.json` / `elementliste_besitzer.json` | doc | Abschnitte `kebab-menue`, `kebab-bestaetigung-archivieren`, `kebab-bestaetigung-loeschen`; Besitzer-Einträge entfallen |
| ADR-0097, 0104, 0109, 0112, 0118 | ADR | Trip/Orte ein Code; DE/EN; Menü-Struktur; Bausteine/Tokens; Knopf-Stil |
| `feat_2278_aktionsmodell.md`, `bug_2214_compare_hub_delete_confirm.md`, `feat_3440_test_schicken_menue.md` | spec | Werden fortgeschrieben (siehe unten) |

## Implementation Details

**Gewählte Variante A:** Zustand und Panel liegen im Kebab-Baustein (Desktop) und im Blatt (mobil); beide nutzen ein gemeinsames Panel und ein reines Modell. Die Seite bekommt `onSelect(id)` für Archivieren und Löschen erst nach der Bestätigung. (Variante B, Zustand auf der Seite, hätte die Logik je Seite verdoppelt; Variante C, ConfirmDialog behalten, verfehlt das Mockup.)

**Reines Modell `kebabBestaetigung.ts`** (node-testbar, ohne DOM):
- `braucheRueckfrage(id)` ist wahr nur für `archive` und `delete`.
- `rueckfrage(id, name)` liefert Titel, Text und Bestätigungs-Beschriftung. Löschen: „Löschen?“, „„{Name}“ wird endgültig gelöscht. Briefings und Alarme hören sofort auf. Das lässt sich nicht rückgängig machen.“, Knopf „Endgültig löschen“ (`listen.archiv.endgueltig_loeschen`). Archivieren: „Archivieren?“, „„{Name}“ verschwindet aus der Liste. Es kommen keine Briefings und Alarme mehr. Du kannst es im Archiv reaktivieren.“, Knopf „Archivieren“ (`aktionen.archive`). Zweiter Knopf immer „Abbrechen“ (`aktionen.abbrechen`).
- `erfolgsText(id)`: Pausieren „Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.“, Fortsetzen „Fortgesetzt. Das nächste Briefing kommt wie geplant.“, Archivieren „Archiviert. Im Archiv kannst du es reaktivieren.“, Reaktivieren „Reaktiviert.“ (Wortlaut #2797). Alle Texte als Katalogschlüssel DE und EN.
- `fehlerText(id, e)` (Tech-Lead-Entscheidung 1): Netzfehler (kein `SubscriptionExecError`) „{Löschen|Archivieren} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.“; Server-5xx „{Aktion} hat nicht geklappt: Fehler auf dem Server. Versuch es später noch einmal.“ (Ergänzung im selben Ton); 4xx mit Server-Detail zeigt das Detail (bisheriges Verhalten). Beide Seiten nutzen dieselbe Klassifikation.

**Desktop (`SubscriptionKebab`):** Neue Prop `name`. Bei Archivieren/Löschen ruft der Eintrag `event.preventDefault()` im `onSelect`, das Menü bleibt offen, der Inhalt wechselt auf das Panel. Die Panel-Knöpfe sind `DropdownMenu.Item` (Pfeiltasten, Enter, Fokus wird nach dem Umschalten auf das Panel gesetzt). „Abbrechen“ ruft `preventDefault()` und kehrt zur Liste zurück, ohne `onSelect`. Die Bestätigung ruft `onSelect(id)` und schließt das Menü. Beim Schließen des Menüs (Escape, Außenklick, Auswahl) wird der Rückfrage-Zustand über `onOpenChange` zurückgesetzt, ein erneutes Öffnen zeigt wieder die Liste. Der Gefahrknopf „Endgültig löschen“ erfüllt WCAG-AA-Kontrast (Design-Leitprinzip).

**Mobil (`SubscriptionActionSheet`):** Dasselbe Panel im Blatt anstelle der Aktionsliste; das Blatt schließt nicht mehr sofort bei Archivieren/Löschen, sondern erst nach Bestätigung oder Schließen. Zeilen mindestens 44 px hoch.

**Menülabels im Hub (`subscriptionActions.ts`):** „Archivieren …“ und „Löschen …“ (Ellipse = fragt nach); „Reaktivieren“, „Pausieren“, „Fortsetzen“ ohne Ellipse. Entwurf: nur „Löschen …“ (Rückfrage gilt auch dort, Entscheidung 4). „Aktivieren“ im Kebab gehört zu #3443.

**Seiten:**
- `routes/trips/[id]/+page.svelte`: `ConfirmDialog` für Archivieren und Löschen entfällt, ebenso der Reaktivieren-Dialog (Reaktivieren ohne Rückfrage, Entscheidung 3). Löschen führt nach Erfolg zur Liste (`/trips`). Archivieren bleibt auf der Seite, Status wird übernommen, Meldung „Archiviert. …“. Fehler über das Modell statt `aktionen.fehler.*` allein.
- `routes/compare/[id]/+page.svelte`: `ConfirmDialog` für Löschen entfällt; Archivieren mit Rückfrage, bleibt auf der Seite (kein `window.location.href='/compare'`), Stand wird ohne Konflikt-Banner übernommen (Muster Trip `uebernehmeNachStatusAenderung`, ETag/Konfliktschutz beachtet); Reaktivieren ohne Reload und ohne Rückfrage. Pausieren bleibt über `toggleActiveFromParent()` (Entscheidung 2, kein Umbau): Erfolg zeigt „Pausiert.“/„Fortgesetzt.“, Misserfolg die bisherige Meldung.
- Beide Seiten zeigen Erfolgs- und Fehlermeldungen über einen gemeinsamen Meldungsweg (das Snippet `meldungen` wie bei #3440).
- `HubKopf.svelte` reicht `name` an den Kebab.

**Abschnitt-Haken und Elementliste:** `data-abschnitt="kebab-menue"` am Menü (Liste), `data-abschnitt="kebab-bestaetigung-archivieren"` und `data-abschnitt="kebab-bestaetigung-loeschen"` am jeweiligen Panel. Die Zeile „Pausieren, Archivieren, Löschen“ im Mockup ist eine K14-Anmerkung und kein UI-Text, sie wird nicht gebaut. Die sechs Besitzer-Einträge `kebab-*` in `docs/context/einstellungen_neu/elementliste_besitzer.json` (je Kontext trip/orte) werden entfernt, weil der Abschnitt jetzt gebaut ist.

**Nicht im Umfang (Entscheidung 5):** Listen-Menüs (`ListActionsMenu`, `/trips`, `/compare`), „Aktivieren“ im Kebab (#3443), Test-Alarm (#3441), Umbau des Pausen-Wegs im Orts-Vergleich.

**Fortschreibung:** `feat_2278_aktionsmodell.md` und `bug_2214_compare_hub_delete_confirm.md` gelten für Archivieren/Löschen nur noch für die Listen; im Hub ersetzt die Rückfrage im Menü den Dialog. Vermerk im jeweiligen Changelog.

**Zwei-Nutzer-Thema:** Diese Scheibe bewegt keine neuen Nutzerdaten und führt keinen neuen Endpunkt ein. Archivieren, Reaktivieren, Pausieren und Löschen laufen unverändert über die bestehenden Endpunkte, deren Mandantentrennung (`user_id` aus dem Auth-Kontext, Zwei-Nutzer-Tests) bereits dort abgesichert ist. Ein zusätzlicher Zwei-Nutzer-Test entfällt daher; der E2E-Test legt sein Abo mit dem Prüfkonto selbst an und löscht nur dieses.

## Expected Behavior

- **Input:** Klick auf ⋮ im Hub-Kopf, danach auf „Archivieren …“ oder „Löschen …“, danach auf „Abbrechen“ oder die Bestätigung.
- **Output:** Rückfrage im Menü; erst die Bestätigung führt die Aktion aus. Erfolg: Meldung laut Katalog; Löschen geht zur Liste, Archivieren bleibt auf der Seite mit Status „archiviert“. Fehler: Meldung nach Fehlerklasse.
- **Side effects:** Archivieren/Löschen/Reaktivieren/Pausieren wie bisher am Server; Löschen ist endgültig.

## Acceptance Criteria

- **AC-1:** Given der Hub eines aktiven Trips oder Orts-Vergleichs / When der Nutzer im Kebab-Menü „Löschen …“ anklickt / Then erscheint die Rückfrage „Löschen?“ im Menü selbst (Menü bleibt offen), es geht kein Löschaufruf an den Server, und kein Dialog öffnet sich.
  - Test: Kern-Schicht `node --test` auf das Modell und die Seitenbindung per AST (kein Aufruf von `deleteSubscription` im Auswahlpfad vor der Bestätigung) plus Playwright gegen Staging (nach dem Klick kein DELETE-Request, Rückfrage sichtbar, Abo noch in der Liste).

- **AC-2:** Given die Rückfrage „Löschen?“ im offenen Menü / When der Nutzer „Endgültig löschen“ bestätigt / Then wird der Trip bzw. Orts-Vergleich genau einmal gelöscht und der Nutzer landet auf seiner Liste (`/trips` bzw. `/compare`), wo er nicht mehr steht.
  - Test: Playwright gegen Staging mit einem selbst angelegten Trip des Prüfkontos (Request-Zählung ein DELETE, Navigation zu `/trips`, Eintrag fehlt).

- **AC-3:** Given der Hub eines aktiven Trips oder Orts-Vergleichs / When der Nutzer „Archivieren …“ anklickt / Then erscheint die Rückfrage „Archivieren?“ mit dem Namen, und bis zur Bestätigung geht kein Archivier-Aufruf an den Server.
  - Test: Kern-Schicht `node --test` (`rueckfrage('archive', name)`, `braucheRueckfrage`) plus Playwright gegen Staging in beiden Hubs (kein Request nach dem ersten Klick, Rückfrage mit Name sichtbar).

- **AC-4:** Given die Rückfrage „Archivieren?“ im Trip-Hub / When der Nutzer „Archivieren“ bestätigt / Then bleibt er auf der Seite, der Status zeigt „archiviert“, und die Meldung „Archiviert. Im Archiv kannst du es reaktivieren.“ erscheint.
  - Test: Playwright gegen Staging (kein Seitenwechsel, Statusanzeige archiviert, Meldungstext).

- **AC-5:** Given der Orts-Vergleich-Hub eines aktiven Vergleichs / When der Nutzer „Archivieren“ in der Rückfrage bestätigt / Then bleibt er auf der Seite (keine Navigation zu `/compare`, kein Seiten-Reload), der Stand wird ohne Konflikt-Banner übernommen, der Status zeigt „archiviert“, und dieselbe Meldung wie beim Trip erscheint.
  - Test: Playwright gegen Staging mit selbst angelegtem Vergleich (URL bleibt `/compare/{id}`, kein Konflikt-Banner, Statusanzeige, Meldung) plus Kern-Schicht `node --test` auf die Seitenbindung (Compare-Seite enthält keine Navigation `window.location.href='/compare'` im Archivierpfad).

- **AC-6:** Given eine offene Rückfrage im Desktop-Menü / When der Nutzer „Abbrechen“ wählt / Then kehrt das Menü zur Liste (Pausieren, Archivieren …, Löschen …) zurück, bleibt offen, und es wurde weder Aktion noch Meldung ausgelöst.
  - Test: Playwright gegen Staging (nach „Abbrechen“ Menüeinträge sichtbar, `aria-expanded` bleibt true, kein Request, keine Meldung) plus `node --test` auf das Modell (Abbrechen ändert keinen Zustand außer der Ansicht).

- **AC-7:** Given eine offene Rückfrage im Desktop-Menü / When der Nutzer Escape drückt oder außerhalb klickt / Then schließt das Menü ohne Wirkung, und beim erneuten Öffnen zeigt es wieder die Liste statt der Rückfrage.
  - Test: Playwright gegen Staging (Escape und Außenklick getrennt; Wiederöffnen zeigt Liste; kein Request).

- **AC-8:** Given das Menü ist geöffnet / When der Nutzer nur die Tastatur nutzt (Pfeiltasten, Enter) / Then erreicht er „Archivieren …“ und „Löschen …“, den Bestätigungsknopf und „Abbrechen“ in der Rückfrage, der Fokus liegt nach dem Umschalten auf der Rückfrage, und der Knopf „Endgültig löschen“ ist kontrastreich (WCAG-AA).
  - Test: Playwright gegen Staging (Tastaturdurchlauf bis Bestätigung, Fokuselement in der Rückfrage) plus Kontrastprüfung des Gefahrknopfs aus den Design-Tokens.

- **AC-9:** Given ein Viewport ≤899 px / When der Nutzer das Kebab öffnet und „Löschen …“ oder „Archivieren …“ wählt / Then erscheint die Rückfrage im Aktionsblatt (nicht als Dialog), das Blatt schließt erst nach Bestätigung, „Abbrechen“ führt zurück zur Aktionsliste ohne Wirkung, und die Zeilen sind mindestens 44 px hoch.
  - Test: Playwright gegen Staging bei 390 px (Blatt-Rückfrage sichtbar, Abbrechen, Zeilenhöhe, kein Request vor Bestätigung).

- **AC-10:** Given ein archivierter Trip oder Orts-Vergleich / When der Nutzer im Kebab „Reaktivieren“ wählt / Then geschieht es ohne Rückfrage, der Status wechselt auf aktiv ohne Seiten-Reload, und die Meldung „Reaktiviert.“ erscheint.
  - Test: Playwright gegen Staging in beiden Hubs (kein Panel, Statuswechsel, Meldungstext, kein Reload) plus `node --test` (`braucheRueckfrage('unarchive')` ist falsch).

- **AC-11:** Given ein aktiver bzw. pausierter Trip oder Orts-Vergleich / When der Nutzer „Pausieren“ bzw. „Fortsetzen“ wählt / Then gilt dasselbe ohne Rückfrage, und die Meldung lautet „Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.“ bzw. „Fortgesetzt. Das nächste Briefing kommt wie geplant.“; schlägt es beim Orts-Vergleich fehl, erscheint die bisherige Fehlermeldung.
  - Test: Playwright gegen Staging in beiden Hubs (Meldungstexte) plus `node --test` auf `erfolgsText` für alle vier Statusaktionen.

- **AC-12:** Given ein Löschen oder Archivieren, das fehlschlägt (Server nicht erreichbar, Serverfehler, Ablehnung mit Detail) / When der Nutzer bestätigt hat / Then erscheint eine Fehlermeldung der passenden Klasse („{Löschen|Archivieren} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.“ bzw. „… Fehler auf dem Server. Versuch es später noch einmal.“ bzw. das Server-Detail), der Nutzer bleibt auf der Seite, und das Abo bleibt unverändert.
  - Test: `node --test` auf `fehlerText` mit echten `SubscriptionExecError`-Objekten (Netz, 5xx, 4xx mit Detail; je Aktion) plus Playwright gegen Staging mit erzwungenem Netzabbruch der Anfrage (Meldung, Seite bleibt, Abo noch vorhanden).

- **AC-13:** Given Trip-Hub und Orts-Vergleich-Hub / When Menü, Rückfragen und Meldungen angezeigt werden / Then stammen beide aus demselben Baustein und demselben Modell, tragen die Abschnitt-Haken `kebab-menue`, `kebab-bestaetigung-archivieren` und `kebab-bestaetigung-loeschen`, und es gibt keine Compare-eigene Kebab-Komponente und keinen ConfirmDialog für Archivieren/Löschen mehr im Hub.
  - Test: Kern-Schicht `node --test` auf die Seitenbindung per AST (beide Seiten binden `HubKopf` ohne eigene Rückfrage-Dialoge; `ConfirmDialog`-Importe für diese Aktionen entfernt) plus Playwright gegen Staging (Haken im DOM in beiden Kontexten).

- **AC-14:** Given Sprache Deutsch oder Englisch am Nutzer / When Menülabels, Rückfragen, Knöpfe und Meldungen erscheinen / Then stehen alle neuen Texte im Katalog in beiden Sprachen (Nutzertexte, kein hartkodierter String), der Name wird als Platzhalter eingesetzt, und die Texte des Mockups stimmen in DE mit der Elementliste überein.
  - Test: `node --test` Katalog-Parität DE/EN und `keine_hartkodierten_nutzertexte` plus Elementlisten-Abgleich `elementliste-abgleich.staging.spec.ts` gegen Staging in DE und EN.

- **AC-15:** Given die Elementliste und die Besitzer-Liste / When der Abgleich läuft / Then sind die Abschnitte `kebab-menue`, `kebab-bestaetigung-archivieren` und `kebab-bestaetigung-loeschen` für Trip und Orte im Hub gefunden, und die Besitzer-Einträge für diese drei Abschnitte stehen nicht mehr in `elementliste_besitzer.json`.
  - Test: Playwright-Abgleich gegen Staging (Abschnitte gefunden) plus `node --test` auf die echte Besitzer-Datei (keine Einträge mit `abschnitt` beginnend `kebab-`).

- **AC-16:** Given die Listen `/trips` und `/compare` / When der Nutzer dort eine Aktion aus dem Listenmenü wählt / Then verhalten sich die Listen unverändert zu heute, und die Hub-Umstellung hat keinen Einfluss auf sie.
  - Test: unveränderte bestehende Listen-Tests (`hub-list-menu.spec.ts` auf die Liste, `confirm_dialog.test.ts` für Listen-Dialoge) bleiben grün.

## Definition of Done

- [ ] Rückfrage „Löschen?“/„Archivieren?“ im Menü (Desktop) und im Aktionsblatt (mobil), kein Server-Aufruf vor der Bestätigung, Abbrechen/Escape/Außenklick ohne Wirkung, Tastatur (AC-1 bis AC-9)
- [ ] Löschen → Liste; Archivieren bleibt auf der Seite (auch Orte, ohne Konflikt-Banner); Reaktivieren, Pausieren, Fortsetzen ohne Rückfrage mit Meldung; Fehlertexte je Klasse (AC-2, AC-4, AC-5, AC-10 bis AC-12)
- [ ] Ein Baustein + ein Modell für Trip und Orte, kein ConfirmDialog für Archivieren/Löschen im Hub, Abschnitt-Haken gesetzt (AC-13)
- [ ] DE/EN über den Katalog, Elementliste stimmt, Besitzer-Einträge kebab-* entfernt; Listen unverändert (AC-14 bis AC-16)
- [ ] Bestandstests umgestellt, nicht gelöscht; Adversary-Verdict VERIFIED mit Mutations-Gegenprobe; alle 6 CI-Checks grün; Staging-E2E grün; ausgeliefert, Selftest grün

## Test Plan

### Automated Tests (TDD RED)

Kern-Schicht (deterministisch, `node --test`, kein Mock-Theater):

- [ ] Neu `shared/__tests__/kebab_bestaetigung.test.ts`: GIVEN `archive`/`delete`/`pause`/`resume`/`unarchive` WHEN `braucheRueckfrage` THEN nur archive/delete wahr; `rueckfrage(id, name)` mit Namen mit Sonderzeichen; `erfolgsText` je Aktion; `fehlerText` Netz/5xx/4xx mit echten `SubscriptionExecError` (AC-3, AC-10, AC-11, AC-12)
- [ ] Neu `shared/__tests__/kebab_seiten_bindung.test.ts` (AST über `aktionsmodellAst.ts`): beide Seiten nutzen den geteilten Kebab, keine ConfirmDialogs für Archivieren/Löschen, Compare-Archivierpfad ohne Navigation, Löschaufruf nur im Bestätigungspfad (AC-1, AC-5, AC-13)
- [ ] Neu `i18n`-Parität: DE/EN-Schlüssel `aktionen.kebab.*` vollständig (AC-14)
- [ ] Neu/Prüfung Besitzer-Datei ohne `kebab-*` (AC-15)

E2E gegen Staging (Playwright, neu `frontend/e2e/hub-kebab-rueckfragen.staging.spec.ts`): AC-1 bis AC-12, AC-13 (Haken), AC-14 (EN), AC-15; Trip und Orts-Vergleich je mit selbst angelegtem Abo des Prüfkontos; Desktop und 390 px.

Umgestellt statt gelöscht (alte Dialog-Testids):
- [ ] `shared/__tests__/aktionsmodell_seiten_bindung.test.ts` (F008), `confirm_dialog.test.ts` (Testid-Liste Trip-Hub)
- [ ] E2E `trip-detail-actions.spec.ts`, `trip-header-btn-migration.spec.ts`, `issue-1059-trip-resume-error-feedback.spec.ts`, `hub-list-menu.spec.ts` (ca. Z. 475), `hub-konfliktschutz-zwei-kontexte.spec.ts` (ca. Z. 577), `aktionsmodell-durchklick.spec.ts` (ca. Z. 253)

## Scope (Affected Files)

| File | Change Type | LoC (ca.) | Description |
|------|-------------|-----------|-------------|
| `frontend/src/lib/components/shared/kebabBestaetigung.ts` | CREATE | +90 | Reines Modell: Rückfrage, Erfolgs- und Fehlertexte |
| `frontend/src/lib/components/shared/KebabBestaetigungPanel.svelte` | CREATE | +70 | Geteiltes Panel (Titel, Text, Bestätigen, Abbrechen), `data-abschnitt` |
| `frontend/src/lib/components/molecules/SubscriptionKebab.svelte` | MODIFY | +60/-10 | Rückfrage im Dropdown, `name`, `preventDefault`, Reset beim Schließen |
| `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte` | MODIFY | +40/-10 | Rückfrage im Blatt |
| `frontend/src/lib/components/shared/subscriptionActions.ts` | MODIFY | +10 | Hub-Labels „Archivieren …“/„Löschen …“ |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY | +5 | `name` an den Kebab |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | +40/-50 | ConfirmDialogs raus, Meldungen, Reaktivieren ohne Rückfrage |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | +50/-45 | Dialog raus, Archivieren auf der Seite, Reaktivieren ohne Reload, Meldungen |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | MODIFY | +30 | Neue Schlüssel `aktionen.kebab.*` |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY | -6 Einträge | Besitzer-Einträge `kebab-*` entfernen |
| `docs/specs/modules/feat_2278_aktionsmodell.md`, `bug_2214_compare_hub_delete_confirm.md` | MODIFY | +3 | Changelog-Vermerk Fortschreibung |
| Tests (Liste im Test Plan), neu `hub-kebab-rueckfragen.staging.spec.ts`, `kebab_bestaetigung.test.ts`, `kebab_seiten_bindung.test.ts` | CREATE/MODIFY | +250 | Neue und umgestellte Tests |

## Known Limitations

- Die Listen-Menüs (`/trips`, `/compare`) behalten ihr bisheriges Verhalten; die Rückfrage im Menü gilt nur im Hub-Kopf.
- Der Pausen-Weg im Orts-Vergleich (`toggleActiveFromParent`, Bool-Ergebnis) bleibt unverändert; Fehlermeldungen beim Pausieren dort bleiben die bisherigen.
- Der 5xx-Text ist eine Tech-Lead-Ergänzung im Ton der PO-Texte; die übrigen Texte sind PO-Wortlaut (#2797 K14/K15).
- „Aktivieren“ eines Entwurfs im Kebab folgt in #3443.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine (setzt ADR-0097, ADR-0109 und die PO-Entscheidungen K14/K15 aus #2797 um)
- **Rationale:** Die Struktur (Rückfrage im Menü, Trip und Orte ein Code, Katalogtexte) ist bereits entschieden. Es gibt keine neue Grundsatzentscheidung, nur den Ersatz zweier Dialoge durch ein Panel im Menü.

## Changelog

- 2026-11-27: Initial spec created (Issue #3442, Scheibe S5c von #2797, Epic #2791)
- 2026-11-27: Fortschreibung durch #3443 (`feat_3443_entwurf_aktivieren.md`): im Hub-Entwurf steht „Aktivieren“ (ohne Rückfrage, ohne Ellipse) als erster Kebab-Eintrag vor „Löschen …“; Rückfragen für Archivieren und Löschen unverändert.
