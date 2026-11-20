---
entity_id: feat_3190_vorlage_dialog_inline
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3190-vorlage-dialog-inline
tags: [frontend, wetter, vorlage, mockup, epic-2913]
---

# Vorlage-speichern-Dialog als Inline-Karte nach Mockup (#3190)

## Approval

- [ ] Approved

## Purpose

Der Dialog „Als eigene Vorlage speichern“ im Reiter Wetter (Trip und Orts-Vergleich, ein geteilter Code) ist heute ein modales Overlay mit Schalter und Textbereich. Das Mockup (Soll, Epic #2913) zeigt eine Karte direkt unter der Vorlage-Karte mit Ankreuzfeld und einzeiligem Beschreibungsfeld. Diese Spec bringt Aufbau, Reihenfolge und Bedienelemente auf Mockup-Stand, ohne Texte, Speichern-Logik oder API zu ändern.

## Source

- **File:** `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte`
- **Identifier:** Svelte-Komponente `SavePresetDialog` (Einbindung: `VorlageKarte.svelte`, `WeatherMetricsTab.svelte`)
- **Mockup:** `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` Z.485-505 (Aufbau `viewWetter()`), Z.747-752 (Verhalten)
- **Kontext/Analyse:** `docs/context/feat-3190-vorlage-dialog-inline.md`

> Schicht: ausschließlich Frontend (`frontend/src/...`, SvelteKit). Trip/Orts-Vergleich: ein Code über `kind`, kein Pendant-Risiko. Keine Nutzerdaten-Bewegung neu (API `POST /api/metric-presets` unverändert), Kanäle nicht berührt.

## Scope

### Im Scope

- Overlay, Scrim, `role="dialog"`, Schließen-× entfallen; Dialog wird Inline-Karte.
- Reihenfolge nach Mockup: Titel, Name, Fehlerzeile, Beschreibung, Standard-Ankreuzfeld, Hinweis, Speichern vor Abbrechen.
- `<textarea>` wird einzeiliges `Input`-Atom; `role="switch"` wird `Haken`-Atom mit klickbarer Beschriftung.
- Auslöseknopf `wetter-vorlage-als-eigene` wird Umschalter.
- Fokusführung, Escape-Verhalten, a11y-Rolle `group`.
- Zweiter Nutzer `WeatherMetricsTab` (Alt-Editor) und Wächter-/Test-Anpassungen.

### Nicht im Scope

- Texte, Katalog (`wetter.dialog.*`), Platzhalter: unverändert.
- API, Datenmodell, `eigeneVorlagePayload`, `vorlagenNameFehler`, #3189-Herkunft (`herkunft`-Prop).
- Elementlisten-Inhalt (kennt den Dialog bereits textbasiert).
- Neuer Baustein für Textbereich (entfällt mit einzeiligem Feld).

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | MODIFY | Overlay zu Inline-Karte, Atome, Fokus, Escape |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | MODIFY | Umschalter, `aria-expanded`/`aria-controls`, Fokus-Rückgabe, `taste` vereinfachen |
| `frontend/src/lib/components/atoms/Haken.svelte` | MODIFY | optionaler Prop `beschriftung` (klickbarer Text) |
| `frontend/src/lib/components/atoms/__tests__/` (Haken) | MODIFY | Test für `beschriftung` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Karte unter die Profil-Karte statt Seitenende |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | MODIFY | `SavePresetDialog` aus `BESTAND` nach `SEITEN_SCOPE`, Obergrenze senken |
| `frontend/src/lib/__tests__/harte_farben_waechter.test.ts` | MODIFY | Scrim-Ausnahme (Z.69) streichen |
| `frontend/src/lib/components/organisms/__tests__/feat_3111_wetter_dialoge_mockup.test.ts` | MODIFY | Render-Muster für Atom-Knöpfe |
| `frontend/src/lib/components/organisms/__tests__/feat_3190_vorlage_dialog_inline.test.ts` | CREATE | Struktur-Render-Test (Node) |
| `frontend/e2e/s3a2794-teil3-dialog.spec.ts`, `s3a2794-teil3-design.spec.ts` | MODIFY | Ankreuzfeld, Inline-Zustand, Escape/Fokus |
| `frontend/e2e/elementliste_abgleich_logik.ts` + zugehörige Tests (`elementliste_abgleich_verdrahtung.test.ts`, `elementliste_abgleich_bedienplan.test.ts`) | MODIFY | Bedienplan `vorlage-speichern`: Schließen über Abbrechen (siehe Details) |
| `frontend/e2e/feat-3190-vorlage-dialog-inline.spec.ts` | CREATE | Staging-E2E Trip und Orts-Vergleich, DE+EN |

## Estimated Scope

- **LoC:** ca. +180/-210 (netto sinkend, Overlay-CSS fällt weg; ca. 120 davon Tests)
- **Files:** 13
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Btn`, `Input`, `Haken` | Atome (`atoms/`) | alle Bedienelemente nach ADR-0112 |
| `ampelSchreiben.ts` | Modul | `eigeneVorlagePayload`, `vorlagenNameFehler` (unverändert) |
| `wetter.dialog.*`, `aktionen.*` | i18n-Katalog | alle Texte, DE und EN |
| `POST /api/metric-presets` | API | Speichern (unverändert) |
| #3189 (`herkunft`) | Feature | Herkunft „aus <Name> gespeichert“ bleibt |
| #3192 (AC-8) | Feature | bleibt funktionsfähig, nicht verändert |
| `bausteine_waechter`, `harte_farben_waechter`, `s3a2794_teil3_keine_nativen_controls` | Wächter | müssen grün bleiben |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umsetzung bestehender Entscheidungen, keine neue. ADR-0112 (nur Bausteine und Tokens: `Btn`, `Input`, `Haken`, Karten-Optik über vorhandene Klasse `wt-karte`) und ADR-0111 (keine nativen Controls) werden angewandt. Die `Haken`-Erweiterung um einen optionalen `beschriftung`-Prop ist abwärtskompatibel und die kleinste Änderung innerhalb derselben Atom-Familie; sie ändert keine Grundsatzfrage und braucht daher kein ADR (ADR-0112 Pkt. 2 erfüllt: Baustein-Erweiterung zuerst im Atom, mit eigenem Atom-Test, dann Verwendung).

## Implementation Details

Datei-Verweise statt Code; Soll-Aufbau (Mockup):

1. **Wurzel** der Komponente: `div.wt-karte` mit `role="group"`, `aria-labelledby` auf den Titel (`<b id>`), `data-testid="save-preset-dialog"`, `data-abschnitt="vorlage-speichern"`. Kein Scrim, kein ×, kein `aria-modal`, kein `tabindex=-1`. Geschlossen wird nichts gerendert (Marker-Test 2966 bleibt gültig).
2. **Platz:** Die Karte steht als eigene Karte direkt unter `.wt-karte` der Vorlage-Karte und vor der Metrik-Karte (`WetterTabInhalt.svelte`, Reihenfolge ergibt sich aus der Geschwister-Position in `VorlageKarte`).
3. **Name:** `Input` mit `<label for>`; Fehlerzeile `role="alert"`, `data-testid="save-preset-error"`, `data-abschnitt="vorlage-speichern-fehler"` **direkt unter** dem Namensfeld; Feld trägt `aria-invalid` und `aria-describedby`. Farbe über vorhandenes Fehler-Token (`--g-danger`; die Mockup-Bezeichnung `--g-bad` ist nur dessen Mockup-Name, kein neues Token).
4. **Beschreibung:** einzeiliges `Input`, `maxlength=120`, `data-testid="save-preset-description"`.
5. **Standard:** `Haken` mit neuem optionalen Prop `beschriftung`; das Atom rendert weiter genau ein `<label>` (kein Verschachteln), ganzer Text klickbar, `data-testid="save-preset-is-default"` am beschrifteten Element. Keine native Checkbox in der Dialog-Datei (Wächter `s3a2794_teil3_keine_nativen_controls`).
6. **Hinweis** als `<p>` (`save-preset-hinweis`), Knöpfe `Btn` accent „Speichern“ (`save-preset-submit`) vor ghost „Abbrechen“, `size="tap"`.
7. **Beschriftungsstil:** Feldbeschriftungen nach Mockup (Mono 10px, Großbuchstaben, `--g-ink-3`) über Token/Atom, soweit vorhanden; sonst bleibt die Abweichung als Ganzseiten-Befund dokumentiert.
8. **Umschalter:** Klick auf `wetter-vorlage-als-eigene` wechselt offen/zu, setzt Name und Fehler zurück, trägt `aria-expanded` und `aria-controls`.
9. **Fokus:** Beim Öffnen Fokus auf das Namensfeld. Nach Speichern, Abbrechen oder Escape Fokus zurück auf den Auslöseknopf (Referenz in `VorlageKarte`, über `onClose`).
10. **Escape:** `keydown` auf der Karte (nicht mehr `svelte:window`): schließt nur bei Fokus in der Karte und stoppt das Ereignis, damit Picker-Escape unabhängig bleibt; `VorlageKarte.taste` (Z.89) wird auf den Picker-Fall vereinfacht. Begründung: erhält die Escape-Bedienung der Bestands-E2E und des Abgleich-Bedienplans, Mockup ist keine Gegenaussage.
11. **Zweiter Nutzer `WeatherMetricsTab` (Alt-Editor):** Entscheidung: **mitziehen, nicht stilllegen.** Die Komponente `SavePresetDialog` ist geteilt; ein Sonderpfad wäre eine zweite Variante. Die Karte wird dort unmittelbar unter der Profil-Karte (`WeatherV2PresetBar`, Block `grundauswahl`, Z.~1706) gerendert statt am Seitenende (Z.~2017). Ob der Block im Bereich `zustellung` überhaupt sichtbar ist, wird nicht angenommen, sondern im Render-Test geprüft (`sections` ohne/mit `grundauswahl`); ist er unerreichbar, bleibt die Verschiebung wirkungslos, aber korrekt.
12. **Wächter:** `SavePresetDialog.svelte` verlässt `BESTAND` und wandert in `SEITEN_SCOPE`; `BESTAND_OBERGRENZE` sinkt entsprechend. Die Scrim-Ausnahme in `harte_farben_waechter.test.ts` wird gestrichen (sonst „verwaiste Ausnahme“).
13. **Abgleich-Bedienplan:** Der Abschnitt `vorlage-speichern` in `elementliste_abgleich_logik.ts` (Z.436-445) schließt heute per Escape. Er wird angepasst: Fokus liegt nach dem Klick auf den Auslöseknopf im Namensfeld, Escape bleibt gültig; zusätzlich wird nach dem Lesen über „Abbrechen“ geschlossen, wenn der Fokus nicht in der Karte liegt. Der Verdrahtungs- und der Bedienplan-Test (Kommentar „SavePresetDialog stoppt Tastenereignisse“, Protokollzeilen `taste:…`) werden darauf abgestimmt.

**Elementliste/Besitzer:** Zu #3190 gibt es keine Einträge in `docs/context/einstellungen_neu/elementliste_besitzer.json` (`grep -c '"#3190"` = 0) und keine neuen sind nötig; `elementliste.json` kennt Abschnitte `vorlage-speichern` und `-fehler` in allen vier Zuständen mit unverändertem Text. Der Abgleich liest Texte, keine Position, deshalb ändert sich die Liste nicht; angepasst wird nur der Bedienplan (Punkt 13).

## Expected Behavior

- **Input:** Klick auf „Als eigene Vorlage speichern“ im Reiter Wetter (Trip oder Orts-Vergleich).
- **Output:** Karte mit Titel, Name, ggf. Fehlerzeile, Beschreibung, Ankreuzfeld, Hinweis, Speichern, Abbrechen erscheint unter der Vorlage-Karte; zweiter Klick auf den Knopf schließt sie.
- **Side effects:** Speichern legt wie bisher eine eigene Vorlage an (inkl. #3189-Herkunft); Metrik-Karte rutscht beim Öffnen nach unten (bewusst, Mockup-Verhalten).

## Test Plan

### Automated Tests (TDD RED)

- [ ] Render-Test (Node) `feat_3190_vorlage_dialog_inline.test.ts`: GIVEN geöffneter Dialog WHEN gerendert THEN kein `role="dialog"`, kein `aria-modal`, kein Scrim, kein `<textarea>`, kein `role="switch"`, `role="group"` mit `aria-labelledby`; Fehlerzeile steht vor dem Beschreibungsfeld; Speichern vor Abbrechen.
- [ ] Atom-Test `Haken`: GIVEN `beschriftung` WHEN gerendert THEN genau ein `<label>`, Text im Label, ohne Prop unverändert.
- [ ] Render-Test: GIVEN `WeatherMetricsTab` mit `showSavePresetDialog` THEN Karte steht nach der Profil-Karte, nicht am Seitenende; prüft `sections` mit/ohne `grundauswahl`.
- [ ] Bestehende Tests angepasst: `feat_3111_wetter_dialoge_mockup`, `wetter_tab_abschnitt_marker_2966`, `s3a2794_teil3_keine_nativen_controls`, `bausteine_waechter`, `harte_farben_waechter`, `wertebereiche_sprache`, `ausblick_ein_name_3155`, `f5Pruefstand`.
- [ ] E2E Staging `feat-3190-vorlage-dialog-inline.spec.ts` und angepasste `s3a2794-teil3-dialog`/`-design`, `epic-138-block-b`, `issue-343-horizon-chips`.
- [ ] Elementliste-Abgleich Staging (`elementliste-abgleich.staging.spec.ts`) grün mit angepasstem Bedienplan.

## Acceptance Criteria

- **AC-1:** Given der Reiter Wetter eines Trips ist offen / When der Nutzer „Als eigene Vorlage speichern“ klickt / Then erscheint direkt unter der Vorlage-Karte und vor der Metrik-Karte eine Karte ohne abdunkelnden Hintergrund und ohne Schließen-Kreuz, und ein zweiter Klick auf denselben Knopf schließt sie wieder.
  - Test: E2E auf Staging, Knopf zweimal klicken, Sichtbarkeit und Position der Karte prüfen (`aria-expanded` wechselt).
- **AC-2:** Given der Reiter Wetter eines Orts-Vergleichs / When der Nutzer die Karte öffnet / Then sieht er dieselbe Karte mit „Als Standard für neue Orte“, bei Trips „Als Standard für neue Trips“.
  - Test: E2E auf Staging in beiden Hubs, Text am Ankreuzfeld je Kontext.
- **AC-3:** Given die Karte ist offen / When der Nutzer sie von oben nach unten liest / Then folgt: Titel, Feld Name, Fehlerzeile direkt unter Name, Beschreibung (einzeilig), Ankreuzfeld, Hinweistext, Speichern, Abbrechen.
  - Test: Render-Test der Reihenfolge und E2E-Positionsvergleich der Elemente.
- **AC-4:** Given die Karte ist offen und der Name ist leer / When der Nutzer „Speichern“ klickt / Then erscheint die Pflicht-Fehlermeldung direkt unter dem Namensfeld, nichts wird gespeichert, und bei bereits vergebenem Namen erscheint die Duplikat-Meldung.
  - Test: E2E leerer Name und Duplikat, Fehlerzeile unter Name, Mailbox/Liste unverändert.
- **AC-5:** Given ein gültiger Name / When der Nutzer Beschreibung und Ankreuzfeld ausfüllt und „Speichern“ klickt / Then schließt die Karte, die Meldung „Vorlage gespeichert“ erscheint, die Vorlage ist unter „Eigene“ mit Herkunft „aus <Name> gespeichert“ (#3189) und, wenn angekreuzt, als Standard vorhanden.
  - Test: E2E auf Staging, danach Vorlagen-Liste lesen; Persistenz per API-Abruf.
- **AC-6:** Given die Karte ist offen / When der Nutzer „Abbrechen“ klickt oder Escape drückt, solange der Fokus in der Karte liegt / Then schließt sie ohne zu speichern und der Fokus liegt wieder auf dem Knopf „Als eigene Vorlage speichern“.
  - Test: E2E Tastatur und Maus, `document.activeElement` prüfen.
- **AC-7:** Given die Vorlagen-Auswahl (Picker) ist geöffnet / When der Nutzer Escape drückt / Then schließt nur die Auswahl; eine offene Speichern-Karte bleibt unberührt, solange der Fokus nicht in ihr liegt.
  - Test: E2E Picker offen plus Karte offen, Escape, Sichtbarkeit beider prüfen.
- **AC-8:** Given der Nutzer arbeitet nur mit Tastatur und Screenreader / When er die Karte öffnet / Then steht der Fokus im Namensfeld, die Karte ist als Gruppe mit Titel benannt, Ankreuzfeld und Fehlermeldung haben zugängliche Namen, und alle Bedienziele sind mindestens 44 px hoch.
  - Test: Render-Test (Rollen, Namen) und E2E `-design`-Messung (Kontrast WCAG-AA, Touch-Ziele, keine nativen Controls).
- **AC-9:** Given die Sprache des Nutzers ist Deutsch oder Englisch / When die Karte offen ist / Then stehen alle Texte, Platzhalter und der Hinweis unverändert aus dem Katalog (DE und EN), ohne neuen oder hartkodierten Text.
  - Test: Sprach-Tests (`wertebereiche_sprache`, `deutsch_unveraendert`, `keine_hartkodierten_nutzertexte`) und E2E in beiden Sprachen.
- **AC-10:** Given der Alt-Editor (Anlegen eines Trips, Bereich Zustellung) mit sichtbarer Profil-Karte / When dort „Als eigene Vorlage speichern“ ausgelöst wird / Then erscheint dieselbe Karte unter der Profil-Karte, nicht am Seitenende, und Speichern/Abbrechen funktionieren wie im Reiter Wetter.
  - Test: Render-Test `WeatherMetricsTab` und, falls erreichbar, E2E im Anlege-Editor.
- **AC-11:** Given die Elementliste und deren Abgleich gegen Staging / When der Abgleich den Abschnitt „Vorlage speichern“ samt Fehlerzustand bedient und liest / Then stimmen alle Texte weiterhin überein und die Karte wird danach wieder geschlossen.
  - Test: Abgleich-Lauf `elementliste-abgleich.staging.spec.ts` gegen Staging, plus Bedienplan-Tests.
- **AC-12:** Given #3192 (AC-8) und die Herkunftsanzeige aus #3189 / When die Karte genutzt wird / Then bleiben beide Verhalten unverändert.
  - Test: bestehende E2E/Render-Tests der beiden Specs bleiben grün.

## Definition of Done

- Alle ACs per Test nachgewiesen; Kern-Tests grün, Wächter (`bausteine_waechter` mit gesenkter Obergrenze, `harte_farben_waechter`, native Controls) grün.
- Staging-E2E und Abgleich grün; Ganzseitenvergleich Zustand „Dialog offen“ (Trip und Orts-Vergleich, Desktop und mobil) gegen Mockup ohne unzugeordnete Abweichung; Bild an den PO (Soll/Ist).
- Adversary und Mutations-Gegenprobe ohne Finding.

## Known Limitations

- Beim Öffnen verschiebt die Karte die Metrik-Karte nach unten (Mockup-Verhalten).
- Der Alt-Editor-Pfad ist ggf. im Bereich `zustellung` nicht sichtbar; die Verschiebung ist dort dann ohne Nutzerwirkung.
- Escape schließt nur bei Fokus in der Karte; das Mockup kennt keine Tastaturbehandlung.
- Beschriftungsstil (Mono 10px) nur, soweit über Tokens/Atome ohne Sonderstil machbar.

## Changelog

- 2026-11-20: Initial spec created
