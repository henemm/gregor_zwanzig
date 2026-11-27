# Kontext: feat-3442-kebab-rueckfragen (Issue #3442, S5c aus #2797)

## Request Summary
Kebab (⋮) im Hub-Kopf von Trip und Orts-Vergleich: „Archivieren …“ und „Löschen …“ fragen **im Menü selbst**
nach (Mockup Fassung 4, `renderKebab()` Z. 423–434, Klick-Logik Z. 815–826), mit dem Mockup-Wortlaut in DE/EN.
„Abbrechen“ kehrt zur Menüliste zurück und ändert nichts; erst die Bestätigung schreibt. Danach Erfolgs-/Fehlermeldung.
Orts-Vergleich archiviert heute **ohne** Rückfrage → gleiche Rückfrage wie Trip (ein Code).
PO-Entscheidungen K14/K15 in #2797 (Wortlaut dort Punkt 4). „Aktivieren“ im Kebab ist **#3443**, nicht hier.

## Soll (Mockup + #2797 Punkt 4)
- Menüeinträge: Pausieren/Fortsetzen · „Archivieren …“ bzw. „Reaktivieren“ · „Löschen …“.
- Rückfrage Löschen: Titel „Löschen?“, Text „„{Name}“ wird endgültig gelöscht. Briefings und Alarme hören sofort auf. Das lässt sich nicht rückgängig machen.“, Knöpfe [Endgültig löschen] [Abbrechen].
- Rückfrage Archivieren: „Archivieren?“, „„{Name}“ verschwindet aus der Liste. Es kommen keine Briefings und Alarme mehr. Du kannst es im Archiv reaktivieren.“, [Archivieren] [Abbrechen].
- Meldungen: „Pausiert. Bis ‚Fortsetzen‘ kommen keine Briefings und Alarme.“ · „Fortgesetzt. Das nächste Briefing kommt wie geplant.“ · „Archiviert. Im Archiv kannst du es reaktivieren.“ · „Reaktiviert.“
- Fehler: „{Löschen|Archivieren} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.“
- Archivieren bleibt auf der Seite (Status → archiviert + Meldung); Löschen geht zur Liste. Reaktivieren ohne Rückfrage.
- Elementliste `docs/context/einstellungen_neu/elementliste.json`, Abschnitte `kebab-menue`, `kebab-bestaetigung-archivieren`,
  `kebab-bestaetigung-loeschen` (ctx trip + orte, Reiter-unabhängig); Bestätigungsknöpfe `listen.archiv.endgueltig_loeschen`,
  `aktionen.archive`, `aktionen.abbrechen`. Die Zeile „Pausieren, Archivieren, Löschen“ ist Mockup-Anmerkung (K14-Marke), kein UI-Text.
  Besitzer-Einträge in `elementliste_besitzer.json` (Z. ~555–720, Verweis #2797) für diese Abschnitte sind nach Umsetzung zu entfernen.

## Ist
| Ort | Heute |
|---|---|
| `frontend/src/lib/components/molecules/SubscriptionKebab.svelte` | bits-ui-DropdownMenu, jeder Eintrag ruft sofort `onSelect(id)`; mobil nur Knopf → `onSheetOpen` |
| `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte` | Blatt mit Aktionen, `onAction(id)` + sofort `onClose()` |
| `frontend/src/lib/components/shared/subscriptionActions.ts` | eine Aktionsquelle (Hub: pause/resume, archive/unarchive, delete; draft nur delete) |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | reicht `actions/onSelect/mobil/onSheetOpen` an den Kebab; kein `name` an den Kebab |
| `frontend/src/routes/trips/[id]/+page.svelte` Z. 143–331, 381–415 | Archivieren **und** Reaktivieren über `ConfirmDialog` (alter Text „Archivierte Trips erhalten keine Briefings mehr.“), Löschen über `ConfirmDialog` → `goto('/trips')`; Fehler über `setzeAktionsFehler` (Schlüssel `aktionen.fehler.*`); keine Erfolgsmeldung |
| `frontend/src/routes/compare/[id]/+page.svelte` Z. 333–398, 494–507 | Archivieren **sofort** + `window.location.href='/compare'`; Reaktivieren sofort + reload; Löschen über `ConfirmDialog`; Pausieren über `compareDetailRef.toggleActiveFromParent()`; Fehler `vergleich.hub.*_fehler` |
| Katalog `frontend/src/lib/i18n/messages/{de,en}/*.json` | `aktionen.archive/unarchive/delete/pause/resume/abbrechen`, `listen.archiv.endgueltig_loeschen`, `trip.hub.*_titel/_text` |

## Existing Patterns
- #3440 `TestSchickenMenue.svelte` + reines Modell `testSchickenModell.ts` (node-testbar): Desktop DropdownMenu, mobil Sheet; Texte per `tr()` + `$locale`. Vorbild für ein reines Kebab-Modell (Texte für Rückfrage/Meldungen je Aktion, Name als Platzhalter).
- Bindungstests ohne DOM: `frontend/src/lib/components/shared/__tests__/aktionsmodell_seiten_bindung.test.ts` (AST über `aktionsmodellAst.ts`), `hub_kopf_seiten_bindung.test.ts`.
- Fehlerklassifikation: `SubscriptionExecError` (status, detail) aus `shared/subscriptionExec.ts`.

## Dependencies / Dependents
- bits-ui DropdownMenu: Item-`onSelect` schließt das Menü standardmäßig; für Rückfrage im Menü `event.preventDefault()` im onSelect (Menü bleibt offen) und Inhalt auf das Bestätigungs-Panel umschalten; beim Schließen Zustand zurücksetzen.
- Liste (`ListActionsMenu`, `/trips`, `/compare`) ist **nicht** Teil dieses Issues (Mockup betrifft den Hub-Kopf).
- Betroffene Tests (müssen nachgezogen werden, weil ConfirmDialog im Hub entfällt):
  `aktionsmodell_seiten_bindung.test.ts` (F008), `confirm_dialog.test.ts` (Testid-Liste Trip-Hub),
  E2E `trip-detail-actions.spec.ts`, `trip-header-btn-migration.spec.ts`, `issue-1059-trip-resume-error-feedback.spec.ts`,
  `hub-list-menu.spec.ts` Z. ~475, `hub-konfliktschutz-zwei-kontexte.spec.ts` Z. ~577, `aktionsmodell-durchklick.spec.ts` Z. ~253.
- Specs: `docs/specs/modules/feat_2278_aktionsmodell.md`, `bug_2214_compare_hub_delete_confirm.md`, `feat_3440_test_schicken_menue.md`.

## Analyse / Ansatz (Summe 3 → Kontext + Analyse kombiniert)
1. Reines Modell `kebabBestaetigung` (neue Datei neben `subscriptionActions.ts`): `rueckfrage(id, name)` → {titel, text, ja} für `archive`/`delete`, `braucheRueckfrage(id)`, Meldungstexte für pause/resume/archive/unarchive und Fehlertext je Aktion. Alle Texte als Katalogschlüssel DE/EN.
2. `SubscriptionKebab` (Desktop) und `SubscriptionActionSheet` (mobil) bekommen `name` und zeigen bei archive/delete das Rückfrage-Panel an Stelle der Liste (ein Panel-Baustein für beide); `onSelect(id)` erst bei Bestätigung. Abbrechen → zurück zur Liste. Hub-Menüeinträge „Archivieren …“/„Löschen …“ (Ellipse = fragt nach).
3. Seiten: ConfirmDialog für Archivieren/Löschen im Hub entfernen; Orte-Archivieren bleibt auf der Seite (Status übernehmen statt Navigation), Reaktivieren ohne Reload/ohne Rückfrage; beide Seiten zeigen dieselben Erfolgs-/Fehlermeldungen (ein Meldungsweg).
4. Abschnitt-Haken `data-abschnitt="kebab-menue"` / `kebab-bestaetigung-archivieren` / `kebab-bestaetigung-loeschen`, Besitzer-Einträge entfernen.

## Risks
- Datenverlust bei Löschen ohne Rückfrage (kritisch) → Test: Klick auf „Löschen …“ ruft `deleteSubscription` nicht auf.
- bits-ui schließt beim Item-Select; ohne `preventDefault` verschwindet die Rückfrage sofort.
- Fokus/Tastatur: Bestätigungsknöpfe müssen im Menü per Tastatur erreichbar sein (Escape bricht ab).
- E2E-Bestand nutzt alte Dialog-Testids → umstellen, sonst rote CI.
- Kontrast: Gefahrknopf „Endgültig löschen“ WCAG-AA (Design-Leitprinzip).

## Analysis

**Type:** Feature (Teil-Scheibe S5c, Umbau bestehender Hub-Aktionen)

**Strategische Bewertung (Plan-Agent, bits-ui 2.17.3):** `DropdownMenu.Item`-`onSelect` bekommt ein abbrechbares Event;
`e.preventDefault()` hält das Menü offen (menu.svelte.js `#handleSelect`). Rückfrage-Zustand per `bind:open`/`onOpenChange`
beim Schließen (Escape, Außenklick) zurücksetzen. Panel-Knöpfe als `DropdownMenu.Item` (Tastatur/Roving-Fokus); „Abbrechen“ mit
`preventDefault` (zurück zur Liste), „Bestätigen“ schließt. Fokus nach dem Umschalten aufs Panel setzen.

| Variante | Beschreibung | LoC | Risiko | Wiederverwendung |
|---|---|---|---|---|
| **A (gewählt)** | Zustand + Panel im Kebab-Baustein (Desktop) und im Blatt (mobil), gemeinsames Panel + reines Modell; Seite bekommt `onSelect(id)` erst nach Bestätigung | ~500 | niedrig | Trip/Orte 100 % geteilt |
| B | Zustand auf der Seite, Panel als Slot | ~600 | mittel | doppelte Logik je Seite |
| C | ConfirmDialog behalten, nur Texte | ~120 | niedrig | verfehlt Mockup (Rückfrage im Menü) |

**Affected Files:**
| Datei | Change |
|---|---|
| `frontend/src/lib/components/shared/kebabBestaetigung.ts` | CREATE — reines Modell: `braucheRueckfrage(id)`, `rueckfrage(id, name)`, `erfolgsText(id)`, `fehlerText(id, e)` |
| `frontend/src/lib/components/shared/KebabBestaetigungPanel.svelte` (o. ä.) | CREATE — Panel, von Desktop und Blatt genutzt |
| `frontend/src/lib/components/molecules/SubscriptionKebab.svelte` | MODIFY — Rückfrage im Dropdown, Prop `name` |
| `frontend/src/lib/components/mobile/SubscriptionActionSheet.svelte` | MODIFY — Rückfrage im Blatt |
| `frontend/src/lib/components/shared/subscriptionActions.ts` | MODIFY — Hub-Labels „Archivieren …“/„Löschen …“ |
| `frontend/src/lib/components/shared/hub-kopf/HubKopf.svelte` | MODIFY — `name` an den Kebab |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY — ConfirmDialogs raus, Reaktivieren ohne Rückfrage, Erfolgs-/Fehlermeldungen übers Modell |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY — ConfirmDialog raus, Archivieren mit Rückfrage und **auf der Seite bleiben** (Stand übernehmen statt Navigation, Muster Trip `uebernehmeNachStatusAenderung`), Reaktivieren ohne Reload, Meldungen übers Modell |
| `frontend/src/lib/i18n/messages/{de,en}/aktionen.json` | MODIFY — neue Schlüssel |
| Tests: `aktionsmodell_seiten_bindung.test.ts`, `confirm_dialog.test.ts`, E2E (6 Specs) | MODIFY |
| `docs/context/einstellungen_neu/elementliste_besitzer.json` | MODIFY — Besitzer-Einträge kebab-* entfernen |

**Scope/Risk:** ~8–10 Quelldateien, ~500 LoC inkl. Tests. Risiko mittel: Löschen ist destruktiv (Test: „Löschen …“ allein ruft kein DELETE), Orte-Archivieren ändert Navigationsverhalten (ETag/Konfliktschutz beachten).

**Technical Approach / Entscheidungen (Tech Lead):**
1. Fehlertexte: Mockup-Text „{Aktion} hat nicht geklappt: keine Verbindung zum Server. Versuch es gleich noch einmal.“ für Netzfehler (kein `SubscriptionExecError`). Server-5xx analog „{Aktion} hat nicht geklappt: Fehler auf dem Server. Versuch es später noch einmal.“; 4xx mit Server-Detail zeigt das Detail (bisheriges Verhalten). Klassifikation im Modell, beide Seiten nutzen sie.
2. Orte-Pausieren bleibt über den bestehenden Weg (`toggleActiveFromParent`, Bool); Erfolg → „Pausiert./Fortgesetzt.“-Meldung, Misserfolg → bisherige Meldung. Kein Umbau des Pausen-Wegs in diesem Issue (Blast Radius).
3. Reaktivieren ohne Rückfrage (Mockup), Meldung „Reaktiviert.“
4. Entwurf: Rückfrage beim Löschen gilt auch dort. „Aktivieren“ bleibt #3443.
5. Listen-Menüs (`/trips`, `/compare`) unverändert (nicht Teil des Mockup-Kopfs).

**Open Questions:** keine (Wortlaut PO-entschieden in #2797 K14/K15; 5xx-Text ist Tech-Lead-Ergänzung im selben Ton).

## Übergabe Phase 5 → 6 (Stand 27.11.)
- RED-Commit `test(#3442): RED-Tests Kebab-Rückfragen`, 72 Tests rot (Artefakt `docs/artifacts/feat-3442-kebab-rueckfragen/test-red-output.txt`, nur lokal).
- Vertrag Modell (`shared/kebabBestaetigung.ts`): `braucheRueckfrage(id)`, `rueckfrage(id, name)` → `{id, titel, text, bestaetigen, abbrechen, gefahr, abschnitt}` bzw. `null`, `erfolgsText(id)`, `fehlerText(id, e)`. Panel-Props `rueckfrage`, `onBestaetigen`, `onAbbrechen`, `data-abschnitt={rueckfrage.abschnitt}`. Kebab: `onOpenChange(false)` setzt Rückfrage zurück.
- In GREEN mit anpassen: `shared/__tests__/subscriptionActions.test.ts` AC-6 (Hub-Labels „Archivieren …“/„Löschen …“); evtl. `i18n/__tests__/katalog_schluessel_haben_verwender.test.ts` (unbenutzte `trip.hub.*_titel/_text`), Sprachtests `trip_hub_sprache`/`vergleich_hub_sprache`; E2E-Specs laut Spec umstellen + neue `hub-kebab-rueckfragen.staging.spec.ts`.
- Seiten speichern den Meldungs-TEXT aus `erfolgsText`/`fehlerText` im Zustand (Verhaltenstests suchen den Text).
- Werkzeug: `frontend/node_modules` im Worktree als Symlink aufs Hauptrepo; `node --test` mit `[id]`-Pfaden als `'src/routes/trips/[[]id]/…'`.
- LoC-Override (`loc_limit_override`) wurde von der Rechteprüfung abgelehnt: Produktivcode möglichst knapp halten; blockt das Scope-Gate, Meldung lesen und dem Workflow folgen.
- Diese Notiz ist (wegen Commit-Sperre in Phase 6) noch nicht committet; sie liegt im Worktree `magical-hugging-sonnet`.
