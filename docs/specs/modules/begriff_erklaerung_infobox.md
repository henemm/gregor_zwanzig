---
entity_id: begriff_erklaerung_infobox
type: module
created: 2026-10-09
updated: 2026-10-09
status: draft
version: "1.0"
workflow: feat-2521-s1-erklaerung-infobox
tags: [frontend, onboarding, popover, infobox, i18n, textkatalog, issue-2521, s1]
---

# Begriff-Erklärung (ⓘ-Popover) und Infobox je überspringbarem Anlege-Reiter

## Approval

- [ ] Approved (PO-Freigabe ausstehend: ACs und Texte auf Deutsch lesen, dann `approved` bzw. `freigabe`)

## Purpose

Ein neuer Nutzer versteht beim Anlegen eines Trips oder Ortsvergleichs vier Fachbegriffe nicht (Wertebereiche, Dringlichkeits-Schwelle, CAPE, Cooldown) und weiß nicht, welche Reiter er überspringen darf und was dann gilt. S1 von Issue #2521 liefert dafür (a) ein ⓘ neben dem Begriff, das per Tippen/Klicken eine Sprechblase öffnet, und (b) eine feste Infobox „Kannst du überspringen — Standard: …“ oben in jedem überspringbaren Anlege-Reiter. Beides ist rein additive Anzeige, ohne Datenänderung.

## Source

- **File:** `frontend/src/lib/components/ui/popover/` (neu), `frontend/src/lib/components/molecules/BegriffErklaerung.svelte` (neu), `frontend/src/lib/components/molecules/Infobox.svelte` (neu), `frontend/src/lib/components/shared/infoboxKeys.ts` (neu), `frontend/src/lib/i18n/messages/de.json`
- **Identifier:** `BegriffErklaerung`, `Infobox`, `infoboxKey(context, tab)`, `BEGRIFF_KEYS`

> **Schicht-Hinweis:** Nur Frontend (SvelteKit). Kein Go-, kein Python-Code. Trip und Ortsvergleich teilen alle Bausteine (Parameter `context="route"|"vergleich"`), es entsteht kein Compare-Pendant. Der Entwurf `onboarding_hilfe_2521.md` bleibt Gesamtbild; S1 ist ausschließlich hier spezifiziert.

## Estimated Scope

- **LoC (produktiv, ohne Tests/Katalog/docs):** ca. +290 / −5
  - Popover-Wrapper ca. 45, `BegriffErklaerung` ca. 60, `Infobox` ca. 35, `infoboxKeys.ts` ca. 40, Einbau in fünf Reiter-Organismen ca. 25, Wertebereiche Desktop+Mobile ca. 14, Picker (Label + ⓘ) ca. 15, Cooldown ca. 8, CAPE-Zeile ca. 12, Wegpunkte ca. 6, Durchreichen von `showInfobox` ca. 25
- **Files:** ca. 17 produktiv (5 neu) plus Tests
- **Effort:** medium
- **LoC-Limit:** Schätzung liegt über 250. **`workflow.py set-field loc_limit_override 500` ist nötig.** Der Scope wird nicht gekürzt (Epic-Regel: themenweise abschließen).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `bits-ui` ^2.17.3 | Bibliothek | Popover-Primitive (Fokus-Rückgabe, Esc, Klick-daneben); bisher nirgends genutzt |
| `frontend/src/lib/i18n` (`t()`, `de.json`) | Modul (#2520) | alle Texte; `t()` hat keine Interpolation, Schlüssel typisiert über `keyof typeof de` |
| `ui/dialog/*` | Modul | Vorbild für den bits-ui-Wrapper |
| `atoms/Eyebrow`, Tokens `app.css` | Modul | Optik; Kontrast-Tokens `--g-ink-2/3`, nie `--g-ink-4` |
| `shared/WeatherMetricsTab`, `corridor-editor/CorridorEditor` + `CorridorEditorMobile`, `shared/AlarmeTab`, `shared/VersandTab`, `shared/AlertChannelPicker` | Organismen | Einbauorte, geteilt zwischen Trip und Ortsvergleich |
| `alerts-tab/AlertCooldownCard`, `alerts-tab/AlertMetricLevelRow` | Organismen | Einbauorte Cooldown und CAPE |
| `trip-new/TripNewEditor`, `compare-new/CompareNewEditor` | Editoren | setzen `showInfobox` (nur Anlegen) |
| `context_herkunft_zweige_eingefroren` (Test) | Ratsche | verbietet neue `context ===`-Zweige unter `shared/` |

## Implementation Details

### Entscheidungen (jeweils begründet)

1. **Bausteine.** `ui/popover` (bits-ui-Wrapper nach Muster `ui/dialog/*`); `molecules/BegriffErklaerung.svelte` (ⓘ als `<button type="button">` mit `aria-label`, Tippfläche mindestens 24 px, Text über `t()`); `molecules/Infobox.svelte` (`<aside>`, kein Schließen-Knopf, kein Zustand). Grund: PO-Entscheid 2026-10-08 (Tippen statt Hover, Basis bits-ui); die Atomic-Ablage (`ui/`, `molecules/`) besteht die Pendant-Sperre. Texte wählt eine Lookup-Map `shared/infoboxKeys.ts` (indexiert mit `context` und Reiter), **keine** neuen `context ===`-Zweige (Ratsche bleibt unverändert). Weil `t()` nicht interpoliert, gibt es je Kontext einen vollständigen Schlüssel. Neue Katalog-Präfixe: `info.*` und `tip.*`.
2. **Reiter mit Infobox:** `wetter-metriken`, `wertebereiche`, `alarme`, `versand` (Trip und Ortsvergleich) sowie Trip-`wegpunkte`. Grund: nur diese sind im Code ohne Eingabe weiter navigierbar bzw. tragen Standardwerte (Freischaltung prüft nur den Besuch, `anlegeLockEngine.ts:33-56`; `wegpunkte` ist `optional`). Die Pflichtreiter `route`, `etappen`, `vergleich`, `orte` bekommen keine Infobox. Der Reiter Layout existiert nicht eigenständig (Abschnitt im Reiter Wetter-Metriken) und hat deshalb keine eigene Infobox. Einbauort: oben im jeweiligen geteilten Organismus; `wegpunkte` am trip-eigenen Panel in `TripNewEditor` (nur Einbau, kein neuer Baustein unter `trip-new/`).
3. **Infobox nur beim Anlegen.** Prop `showInfobox` (Default `false`), gesetzt von `TripNewEditor` und `CompareNewEditor` (Desktop- und Mobile-Panel). In den Bearbeiten-Hubs (`TripTabs`, `CompareTabs`) fehlt die Infobox. Grund: dort gibt es keine Freischaltkette, „Kannst du überspringen“ stimmt nicht, und „Standard: 07:00“ neben einer gespeicherten 18:00 wäre irreführend (Leitprinzip Lesbarkeit). Die ⓘ-Erklärungen erscheinen dagegen überall (Anlegen und Bearbeiten), weil Begriffe überall gleich erklärungsbedürftig sind.
4. **Echte Ist-Standards.** Die Texte nennen den Standard je Kontext, geprüft gegen `alertChannelState.ts` (Alarm-Kanäle: Telegram und E-Mail an, SMS und Premium-SMS aus; Schwelle „gering“), `reportSlotAktiv.ts`/`VersandTab.svelte` (Trip: Morgen 07:00, Abend 18:00), `compareWizardState.svelte.ts` (Vergleich: nur Morgen 07:00 an, Abend aus, kein Enddatum), `tripNewLogic.ts`/`compareWizardState.svelte.ts` (keine Wertebereiche, amtliche Warnungen aus). Bewusst **ohne Zahlen**, die nicht belegt sind (Anzahl vorgewählter Metriken, Tagesfenster, Cooldown-Minuten). **Paritätsbefund zu #2518:** Die Analyse vermutete einen abweichenden Alarmkanal-Default im Vergleich (nur E-Mail). Die Prüfung zeigt: `alarmePropsAus.ts:119` fällt bei frischer Anlage auf `newEntityAlertChannelDefault()` zurück, also derselbe Default wie beim Trip. Der Text ist trotzdem je Kontext ein eigener Schlüssel; bei Abweichung im Staging-Test wird der Text an den Ist-Stand angepasst, der Default selbst wird in S1 nicht geändert.
5. **Kanal-Schwelle.** Im `AlertChannelPicker` kommt ein sichtbares Label „Dringlichkeits-Schwelle“ (derselbe Begriff wie `aria-label` und Erklärtext) mit ⓘ in den Kopfbereich. Grund: heute gibt es den Begriff nur als `aria-label`, ein ⓘ braucht einen sichtbaren Anker.
6. **CAPE.** ⓘ am Label „Gewitterenergie (CAPE)“ in der Alarm-Tabelle (`AlertMetricLevelRow`), über eine Map Metrik→Erklärschlüssel, die nur `cape` enthält. Der vorhandene `thresholdTitle` (Invariante `alertMetricTable.ts`: nur CAPE hat einen `title`) bleibt unverändert. **Eingrenzung:** CAPE ist in den Wertebereichen ausgeschlossen (`corridorEditorCapeExclusion`); in der Metrik-Auswahl der Wetter-Metriken wird das Label aus dem Metrik-Katalog dynamisch gerendert, dort gibt es keinen Anker pro Metrik, und eine Erklärung wäre eine Metrik-Sonderbehandlung in der Liste (Folgethema, nicht S1). Die Alarm-Tabelle ist die Stelle, an der CAPE einen erklärungsbedürftigen Schwellwert („Δ ≥ …“) trägt.
7. **Wertebereiche und Cooldown.** ⓘ in `CorridorEditor` **und** `CorridorEditorMobile` an der Eyebrow; Cooldown-ⓘ an der Eyebrow von `AlertCooldownCard`. Die bestehenden Lead- und `hint`-Texte bleiben unverändert (S1 ist additiv, kein Textumbau).
8. **Produktregel.** Erklär- und Infobox-Texte erklären nur Begriffe und Standards, sie geben keine Handlungsempfehlung. Es heißt durchgehend „Trip“.
9. **Eindeutigkeit.** Desktop- und Mobile-Panel rendern gleichzeitig; Popover-IDs und `data-testid` je Instanz eindeutig (Suffix aus Reiter und Kontext).

### Festgelegte Texte (Deutsch, zur Freigabe)

Infobox (Präfix `info.`, Schlüssel `info.<reiter>.<route|vergleich>`; auch bei identischem Text je Kontext ein eigener Schlüssel):

| Reiter | Kontext | Text |
|---|---|---|
| wetter-metriken | route | Kannst du überspringen — Standard: die vom System vorgewählten Wetter-Metriken. |
| wetter-metriken | vergleich | Kannst du überspringen — Standard: die vom System vorgewählten Metriken, dazu Stundenverlauf und 3-Tages-Ausblick (beide an). |
| wertebereiche | route, vergleich | Kannst du überspringen — Standard: keine Wertebereiche, im Briefing wird nichts hervorgehoben. |
| alarme | route, vergleich | Kannst du überspringen — Standard: Alarme per E-Mail und Telegram, Dringlichkeits-Schwelle „gering“, amtliche Warnungen aus. Telegram wirkt erst nach der Verknüpfung. |
| versand | route | Kannst du überspringen — Standard: E-Mail, Morgen-Briefing um 07:00 Uhr und Abend-Briefing um 18:00 Uhr. |
| versand | vergleich | Kannst du überspringen — Standard: E-Mail, Morgen-Briefing um 07:00 Uhr, kein Enddatum. |
| wegpunkte | route | Kannst du überspringen — Standard: keine zusätzlichen Wegpunkte. |

Begriff-Erklärung (Präfix `tip.`):

| Schlüssel | Text |
|---|---|
| `tip.wertebereiche` | Ein Wertebereich legt für eine Metrik fest, welche Werte als passend gelten. Werte im Bereich werden im Briefing hervorgehoben. |
| `tip.kanal_schwelle` | Die Dringlichkeits-Schwelle legt je Kanal fest, ab welcher Stufe (gering, mittel, hoch) eine Meldung über diesen Kanal kommt. |
| `tip.cape` | CAPE (Gewitterenergie) misst in J/kg, wie viel Energie in der Luft für Gewitter steckt. Der Schwellwert ist ein Richtwert und wird je Wettermodell und Gebiet umgerechnet. |
| `tip.cooldown` | Der Cooldown ist der Mindestabstand in Minuten zwischen zwei Meldungen derselben Metrik. |

Zusätzlich je ein Schlüssel `tip.aria.<begriff>` für den Namen des ⓘ-Knopfs (z. B. „Erklärung: Cooldown“). Einen Schließen-Knopf gibt es nicht (Schließen per Esc oder Tippen daneben).

## Expected Behavior

- **Input:** Nutzer öffnet `/trips/new` oder `/compare/new` und wechselt durch die Reiter; oder er öffnet einen bestehenden Trip/Ortsvergleich im Bearbeiten-Hub.
- **Output:** In den freigeschalteten, überspringbaren Anlege-Reitern steht oben die Infobox; neben den vier Begriffen steht ein ⓘ, das eine Sprechblase öffnet. Im Bearbeiten-Hub nur das ⓘ.
- **Side effects:** keine. Kein Speichern, kein `localStorage`, keine Server-Anfrage.

## Acceptance Criteria

- **AC-1:** Given ich lege einen neuen Trip an und habe den Reiter Wetter-Metriken geöffnet / When ich auf den Reiter schaue / Then steht oben eine Infobox mit dem Text „Kannst du überspringen — Standard: die vom System vorgewählten Wetter-Metriken.“
  - Prüfung: Playwright auf `/trips/new` (Desktop) plus SSR-Test des Organismus mit `showInfobox` und `context="route"`.
- **AC-2:** Given ich lege einen neuen Ortsvergleich an und habe den Reiter Wetter-Metriken geöffnet / When ich auf den Reiter schaue / Then steht oben die Infobox mit dem Vergleichs-Text (Stundenverlauf und 3-Tages-Ausblick an).
  - Prüfung: Playwright auf `/compare/new`, SSR-Test mit `context="vergleich"`.
- **AC-3:** Given ich lege einen Trip oder einen Ortsvergleich an / When ich nacheinander die Reiter Wertebereiche, Alarme und Versand öffne / Then zeigt jeder Reiter oben seine Infobox mit dem Standard dieses Reiters und dieses Kontexts (Versand: beim Trip Morgen 07:00 und Abend 18:00, beim Ortsvergleich nur Morgen 07:00 ohne Enddatum).
  - Prüfung: je Reiter und Kontext ein Test mit Text-Vergleich gegen den Katalog; Standards zusätzlich gegen die Quell-Konstanten (`reportSlotAktiv.ts`, `compareWizardState.svelte.ts`) abgeglichen.
- **AC-4:** Given ich lege einen Trip an / When ich den optionalen Reiter Wegpunkte öffne / Then steht oben die Infobox „Kannst du überspringen — Standard: keine zusätzlichen Wegpunkte.“
  - Prüfung: Playwright auf `/trips/new`.
- **AC-5:** Given ich lege einen Trip oder Ortsvergleich an / When ich die Pflichtreiter (Trip: Route, Etappen; Ortsvergleich: Vergleich, Orte) ansehe / Then zeigt keiner davon eine Infobox.
  - Prüfung: SSR/Playwright: kein Infobox-Element in diesen Reitern.
- **AC-6:** Given ich öffne einen bestehenden Trip oder Ortsvergleich zum Bearbeiten / When ich die Reiter Wetter-Metriken, Wertebereiche, Alarme und Versand ansehe / Then steht in keinem davon eine Infobox, die ⓘ-Erklärungen sind aber vorhanden.
  - Prüfung: Test auf `TripTabs`/`CompareTabs`-Mounts (Prop `showInfobox` nicht gesetzt ⇒ kein Infobox-Element); das ⓘ ist dort per Selektor auffindbar.
- **AC-7:** Given eine Infobox ist sichtbar / When ich die Seite neu lade oder zwischen Reitern wechsle / Then ist sie weiterhin sichtbar, es gibt keinen Schließen-Knopf, und es wird nichts im Browser oder auf dem Server gespeichert.
  - Prüfung: Playwright: nach Reload sichtbar, kein `button` innerhalb des `<aside>`; `localStorage` und `sessionStorage` bleiben unverändert; keine zusätzliche Netzwerkanfrage durch die Infobox.
- **AC-8:** Given ich bin im Reiter Wertebereiche eines Trips oder Ortsvergleichs / When ich neben der Überschrift auf das ⓘ tippe oder klicke / Then öffnet sich eine Sprechblase mit der Erklärung „Ein Wertebereich legt für eine Metrik fest, welche Werte als passend gelten …“
  - Prüfung: Playwright in beiden Anlege-Seiten; Desktop UND Mobile-Viewport (`CorridorEditor` und `CorridorEditorMobile`).
- **AC-9:** Given ich bin im Reiter Alarme / When ich das sichtbare Label „Dringlichkeits-Schwelle“ am Kanal-Block ansehe und auf das ⓘ daneben tippe / Then öffnet sich die Erklärung der Dringlichkeits-Schwelle, in Trip UND Ortsvergleich.
  - Prüfung: Playwright in beiden Anlege-Seiten; Label-Text, `aria-label` der Stufen-Gruppe und Erklärtext verwenden denselben Begriff.
- **AC-10:** Given ich bin im Reiter Alarme und die Alarm-Tabelle zeigt die Zeile „Gewitterenergie (CAPE)“ / When ich auf das ⓘ am Zeilen-Label tippe / Then öffnet sich die CAPE-Erklärung, und die bisherige Hover-Erklärung an der Schwellwert-Zelle ist unverändert vorhanden.
  - Prüfung: SSR-Test der Zeile (ⓘ nur bei `cape`, bei anderen Metriken kein ⓘ; `title` an der Schwellwert-Zelle unverändert) plus Playwright-Öffnen.
- **AC-11:** Given ich bin im Reiter Alarme / When ich auf das ⓘ neben „Cooldown“ tippe / Then öffnet sich die Erklärung „Der Cooldown ist der Mindestabstand in Minuten …“, und der bisherige Hinweistext unter dem Eingabefeld steht unverändert da.
  - Prüfung: Playwright (Trip- und Vergleichs-Anlage) plus SSR-Test, dass der bestehende `.hint`-Text unverändert gerendert wird.
- **AC-12:** Given eine Sprechblase ist offen / When ich Esc drücke oder neben die Sprechblase tippe / Then schließt sie sich, und der Fokus liegt wieder auf dem ⓘ.
  - Prüfung: Playwright-Spec `frontend/e2e/begriff-erklaerung.spec.ts` (Esc, Klick daneben, `toBeFocused` auf dem ⓘ), ohne `waitForTimeout` und ohne `skip`; aufgenommen in `.github/ci_e2e_specs.txt`.
- **AC-13:** Given ich bediene nur die Tastatur / When ich das ⓘ per Tab anspringe und Enter oder Leertaste drücke / Then öffnet sich die Sprechblase, ohne dass ein Mauszeiger (Hover) nötig ist, und das ⓘ hat einen sprechenden Namen für Vorlese-Hilfen.
  - Prüfung: Playwright (Enter und Space, kein `hover()`), `getByRole('button', { name: … })` über den `aria-label`-Text.
- **AC-14:** Given ich sehe eine Infobox oder eine Sprechblase / When ich den Text lese / Then ist der Kontrast mindestens 4,5 zu 1, und nie wird die Farbe `--g-ink-4` verwendet; das ⓘ lässt sich mit mindestens 24 Pixel Tippfläche treffen.
  - Prüfung: node-Test nach Muster `shared/__tests__/app_footer_kontrast_und_tippflaeche.test.ts` (Werte aus `app.css`, SSR-Markup der Bausteine, Tippfläche aus dem Stil).
- **AC-15:** Given der Textkatalog enthält die neuen Schlüssel / When der Katalogtest läuft / Then sind alle `info.*`- und `tip.*`-Schlüssel vorhanden und nicht leer, die Texte verwenden durchgehend das Wort „Trip“ (nie die Altbezeichnung), und die neuen Bausteine tragen keinen Fließtext außerhalb von `t()`.
  - Prüfung: `frontend/src/lib/i18n/__tests__/textkatalog.test.ts` erweitert (bisher nur `start.*`) mit Gegenprobe (leerer Wert bzw. Fließtext im Baustein macht den Test rot).
- **AC-16:** Given ich öffne die Seiten `/trips/new` und `/compare/new` und gehe alle Reiter durch / When ich Sprechblasen öffne und schließe / Then erscheint kein Fehler in der Browser-Konsole.
  - Prüfung: Playwright mit Konsolen-Listener (Frontend-Browser-Gate), Desktop und Mobile.
- **AC-17:** Given die Erklär- und Infobox-Texte aus dieser Spec / When ich sie lese / Then erklären sie nur Begriffe und Standardwerte und geben keine Handlungsempfehlung („du solltest …“ kommt nicht vor).
  - Prüfung: Katalogtest prüft die Texte gegen eine Verbotsliste (Empfehlungsformeln wie „solltest“, „empfehlen“, „besser“).
- **AC-18:** Given die neuen Bausteine sind eingebaut / When die bestehende Ratsche `context_herkunft_zweige_eingefroren` läuft / Then bleibt sie unverändert grün, weil die Texte über die Lookup-Map statt über neue Kontext-Verzweigungen gewählt werden.
  - Prüfung: bestehender Test läuft ohne Änderung an seinen eingefrorenen Zeilen.

## Test Plan

Frontend-Tests laufen mit `node --test` (kein Vitest), SSR über `frontend/test-svelte-ssr-hooks.mjs`; Interaktion nur per Playwright (das Popover-Portal ist im SSR-Harness nicht prüfbar).

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN Anlege-Seite Trip WHEN Reiter Alarme gerendert mit `showInfobox` THEN `<aside>` mit Text `info.alarme.route`, kein `button` darin (AC-1, AC-3, AC-7)
- [ ] Test 2: GIVEN Organismus ohne `showInfobox` (Bearbeiten-Hub) WHEN gerendert THEN kein Infobox-Element, ⓘ vorhanden (AC-6)
- [ ] Test 3: GIVEN `context="vergleich"` WHEN Versand-Infobox gerendert THEN Text nennt nur Morgen 07:00 und kein Enddatum (AC-3)
- [ ] Test 4: GIVEN Alarm-Zeile `cape` vs. `gust` WHEN gerendert THEN nur CAPE hat ⓘ, `thresholdTitle` unverändert (AC-10)
- [ ] Test 5: GIVEN Playwright `begriff-erklaerung.spec.ts` WHEN ⓘ per Klick, Enter, Space geöffnet und per Esc bzw. Klick daneben geschlossen THEN Fokus zurück auf ⓘ (AC-12, AC-13)
- [ ] Test 6: GIVEN Katalogtest WHEN alle `info.*`/`tip.*` geprüft THEN vorhanden, nicht leer, Wortwahl „Trip“, keine Empfehlungsformeln (AC-15, AC-17)
- [ ] Test 7: GIVEN Kontrasttest WHEN Infobox- und Popover-Farben gelesen THEN ≥ 4,5:1 und nie `--g-ink-4`, Tippfläche ≥ 24 px (AC-14)
- [ ] Test 8: GIVEN Playwright `/trips/new` und `/compare/new` WHEN alle Reiter durchlaufen THEN keine Konsolenfehler (AC-16)
- [ ] Test 9: GIVEN Wertebereiche Desktop und Mobile WHEN gerendert THEN beide tragen das ⓘ (AC-8)
- [ ] Mutations-Gegenprobe (Pflicht für den Adversary): `showInfobox`-Default auf `true` drehen, ⓘ aus dem Mobile-Editor entfernen, Vergleichs-Versandtext auf den Trip-Text setzen — je ein Test muss rot werden.

## Known Limitations

- Texte nennen bewusst keine Zahlen zu Metrik-Anzahl, Tagesfenster und Cooldown-Minuten (nicht belegt); spätere Schnitte können sie ergänzen.
- Keine Infobox in den Bearbeiten-Hubs (Entscheidung 3). Keine Willkommens-Seite, Checkliste, „Mit Standardwerten speichern“ und Hilfeseite — spätere Schnitte S2 bis S5.
- CAPE-Erklärung nur in der Alarm-Tabelle (Entscheidung 6).
- Mögliche Paritätsabweichung beim Alarmkanal-Default (Entscheidung 4) wird nicht in S1 behoben.
- Vor dem Bauen im Worktree-Frontend `npm ci` (kein `node_modules` im Worktree).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive UI-Bausteine auf bestehender Bibliothek (bits-ui) und bestehendem Textkatalog (#2520); keine Entscheidungsfläche aus `docs/adr/` (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma) wird berührt. Der Editor-Aufbau bleibt unverändert (ADR-0032).

## Changelog

- 2026-10-09: Initial spec created (Issue #2521, Schnitt S1)
