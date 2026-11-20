# Context: #3190 Vorlage-speichern-Dialog nach Mockup (Inline-Karte, Checkbox, einzeiliges Feld)

## Request Summary

Der Dialog „Als eigene Vorlage speichern“ (Reiter Wetter, Trip und Orts-Vergleich, ein geteilter Code) ist live ein modales Overlay (`role="dialog"`, Scrim, Escape, Schließen-×) mit Schalter (`role="switch"`) und Textbereich (`<textarea>`). Das Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` (Z.485-505, Aufbau in `viewWetter()`; Verhalten Z.747-752) zeigt ihn als **Inline-Karte** mit **Ankreuzfeld** „Als Standard für neue Trips/Orte“ und **einzeiligem** Beschreibungsfeld. Mockup ist Soll (Epic #2913). Abgespalten aus #3111 (Ganzseitenbild-Abweichung ohne Elementlisten-Eintrag).

Mockup-Soll (genau):
- Position: eigene `.card` mit `.dialog` (flex column, gap 12px, padding 18px 20px) **direkt unter der Vorlage-Karte (`.card.pad.vorlage`) und vor der Metrik-Karte**; erscheint nur bei `saveOpen`. Der Knopf „Als eigene Vorlage speichern“ **schaltet um** (`saveOpen=!saveOpen`, Z.747), setzt Fehler/Name zurück.
- Reihenfolge: `<b>` Titel „Als eigene Vorlage speichern“ (kein ×) · Feld `Name` (label `for=vName`, `input.wide`, Platzhalter „z.B. Mallorca Frühling“) · **Fehlerzeile `span.err role=alert` direkt unter Name** · Feld „Beschreibung (optional)“ (`input.wide`, **einzeilig**, Platzhalter „wofür die Vorlage gedacht ist“) · `label.chk` mit `<input type=checkbox>` + „Als Standard für neue Trips|Orte“ · `span.muted` 12.5px Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.“ · Knöpfe **Speichern (accent sm) vor Abbrechen (ghost sm)**.
- Kein Scrim, kein Schließen-×, kein Escape-Handler im Mockup. Nach Speichern: Karte zu, Meldung „Vorlage „X“ gespeichert. Du findest sie unter „Eigene“.“ (Mockup per Flash; live bleibt `wetter-vorlage-gespeichert` im VorlageKarte).
- Abweichung im Mockup-Namen: Mockup `.err` nutzt `--g-bad`, live `--g-danger` (Token-Frage, s. Risiken).

## Related Files

| Datei | Zeile | Rolle |
|---|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | 1-259 | Der Dialog. Overlay/Scrim 106-107, `role=dialog` 108-117, ×-Knopf 121, textarea 133, `role=switch` 135-138, Escape `taste` 94-96 + `svelte:window` 99, Fehlerzeile 141-143 (nach Hinweis, vor Knöpfen), Fuß mit Speichern→Abbrechen 147-152. Props `open`(bindable), `kind`, `ampel`, `onClose`, `onSaved`, `existingNames`, `herkunft`. Eigenes `<style>` (`spd-*`). |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | 45, 89, 144, 154 | Haupt-Einbindung (Hubs Trip und Orts-Vergleich). `dialogOffen`, Knopf `wetter-vorlage-als-eigene` setzt nur `true` (kein Toggle), Dialog **außerhalb** des `.wt-karte` als Geschwister (Z.154). `taste` Z.89 unterdrückt Picker-Escape, solange Dialog offen. Erfolgsmeldung `wetter-vorlage-gespeichert` Z.150. |
| `frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte` | 262-278 | Rendert `VorlageKarte`, danach `.wt-karte.wt-metriken` — Inline-Karte gehört an diese Stelle (zwischen beiden). |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | 311, 1706, 2017-2026 | **Zweiter Nutzer (Alt-Editor)**: `showSavePresetDialog`, geöffnet aus `WeatherV2PresetBar` (Profil-Karte), Dialog am Seitenende unter „Dialoge & Overlays“. Eingebunden nur über `WetterMetrikenVersandPanel` (`TripNewEditor.svelte:937,1200`, Bereich `zustellung`); Reiter Wetter der Hubs nutzt ihn nicht (`s3a2794_teil3_wettertab_mount.test.ts`). Ob `grundauswahl`/Profil-Karte dort noch erreichbar ist: im Schritt Analyse-Detail/Spec per Render prüfen. |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2PresetBar.svelte` | – | Alt-Auslöser `onOpenSaveDialog`. |
| `frontend/src/lib/components/shared/wetter-tab/ampelSchreiben.ts` | – | `eigeneVorlagePayload`, `vorlagenNameFehler` (unverändert nutzbar). |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | 123-133 | Katalog `wetter.dialog.*` (titel, name, beschreibung, *_platzhalter, name_pflicht, standard_route/vergleich, hinweis, name_vergeben, gespeichert). Texte stimmen mit Mockup überein; kein neuer Text nötig (Schließen-× entfällt: `aktionen.schliessen` bleibt im Katalog). |
| `frontend/src/lib/components/atoms/{Haken,Input,Btn,Card,Switch}.svelte` | – | Vorhandene Bausteine (s. Existing Patterns). Kein Textarea-/Kontrollkästchen-mit-Text-Baustein. |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` | 601 | `SavePresetDialog.svelte` steht in `BESTAND` (Ratsche, darf nur sinken; Obergrenze = Länge). Umbau nach ADR-0112 → aus `BESTAND` raus, in `SEITEN_SCOPE` rein. |
| `frontend/src/lib/__tests__/harte_farben_waechter.test.ts` | 69 | Ausnahme `SavePresetDialog.svelte: { n: 1, grund: 'Scrim …' }` — entfällt mit dem Scrim (Ausnahme auf 0/streichen). |

## Pinnende Tests (Datei:Zeile)

E2E (Playwright, Staging) — pinnen Overlay/Schalter/Escape/Testids:
- `frontend/e2e/s3a2794-teil3-dialog.spec.ts` 5-8, 43-110: Öffnen über `WT.alsEigene`, `getByTestId(WT.dialog)` (`save-preset-dialog`), `dialogStandard` (`save-preset-is-default`, **toHaveContainText** „Als Standard für neue Trips/Orte“ → muss zu Ankreuzfeld-Element mit dieser testid passen), `dialogHinweis` `toHaveText`, Pflicht-Fehler, Duplikat, `page.keyboard.press('Escape')` Z.89 und Z.103 als **Schließen** (bricht bei fehlendem Escape: Folge-Klick auf `alsEigene` würde die Karte per Toggle schließen statt öffnen!). Keine Overlay-Eigenschaft (kein `aria-modal`-Check).
- `frontend/e2e/s3a2794-teil3-design.spec.ts` 100-123: Dialog `NATIV` = 0 (Z.117 — Ankreuzfeld muss aus dem Baustein kommen UND der Selektor `NATIV` darf `input[type=checkbox]` im Haken-Atom nicht treffen: prüfen, `NATIV` oben in der Datei lesen), Kontrast `messeKontrast(dialog)`, Touch-Ziele `zuKleineZiele(dialog)` (`ZIELE` Z.22 enthält `[role="switch"]`), Escape Z.119 zum Schließen.
- `frontend/e2e/epic-138-block-b.spec.ts` 55-57 (`oeffneDialog`), 148-187: Dialog sichtbar, Hinweis, leerer Name → `save-preset-error`, Speichern → `not.toBeVisible` (Z.187, bleibt gültig für Inline-Karte).
- `frontend/e2e/issue-343-horizon-chips.spec.ts` 106-190: `save-preset-dialog` sichtbar/nicht sichtbar, kein Zeithorizonte-Block, Hinweis-Text.
- `frontend/e2e/issue-690-custom-metrics-persist.spec.ts` (Treffer „Vorlage speichern“): Alt-Pfad, Details beim Spec-Schritt prüfen.
- `frontend/e2e/s3a2794-teil3.helpers.ts` 75-82: testids `save-preset-{dialog,name,description,is-default,hinweis,error,submit}` — **müssen bleiben**.
- `frontend/e2e/elementliste_abgleich_logik.ts` 436-445: Bedienplan für Abschnitt `vorlage-speichern`: Klick `ALS_EIGENE`, lesen, **Taste Escape** (schließen); `…-fehler`: Klick Speichern, lesen, Escape. Test-Spiegel `frontend/src/lib/__tests__/elementliste_abgleich_verdrahtung.test.ts` 501 (Kommentar „SavePresetDialog stoppt Tastenereignisse“ + Regex auf `blur()`+`press`) und `elementliste_abgleich_bedienplan.test.ts` 105-112, 205, 231 (Protokoll `klick:wetter-vorlage-als-eigene`, `klick:save-preset-submit`, `lesen:…`, `taste:…`). Das Schließen per Escape ist hier Teil des Bedienplans; bei Inline-Karte: Schließen über **Abbrechen-Knopf** oder weiter Escape (s. Open/Technik).
- `frontend/e2e/elementliste-abgleich.staging.spec.ts` (Treffer SavePresetDialog): Staging-Abgleich der Elementliste gegen Live.

Node (`node --test`):
- `frontend/src/lib/components/organisms/__tests__/feat_3111_wetter_dialoge_mockup.test.ts` 350-379: Render des echten `SavePresetDialog` (`lade(SPD)`), `platzhalterVon(h,'save-preset-name'|'…-description')` mit Regex `<(?:input|textarea)\b…data-testid=…>` (**funktioniert für `<input>` weiter**), Speichern vor Abbrechen (Textpositionen `>Abbrechen<` / `>Cancel<` — bei Btn-Atom steht Text evtl. in Kind-Elementen: Muster prüfen!).
- `frontend/src/lib/components/organisms/__tests__/wetter_tab_abschnitt_marker_2966.test.ts` 238-258: `data-abschnitt="vorlage-speichern"` **am Element mit `data-testid="save-preset-dialog"`** (ersterTag), Kinder `save-preset-name`, `save-preset-submit`; `vorlage-speichern-fehler` am Element `save-preset-error` mit `role="alert"`; geschlossen → 0 Marker. Bleibt gültig, wenn die Karte beide Attribute trägt und geschlossen nichts rendert.
- `frontend/src/lib/components/shared/__tests__/s3a2794_teil3_keine_nativen_controls.test.ts` 26, 85-91: AST-Check `SavePresetDialog.svelte` **ohne** `<select>`, `<input type=checkbox|date|…>` (**native Checkbox im Dialog verboten** → `Haken`-Atom nutzen; `<input type="text">` bleibt erlaubt, wird nach ADR-0112 aber durch `Input`-Atom ersetzt).
- `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/f5Pruefstand.ts` 95, 199, 213 + `f5KatalogAnker.ts` 34: Render-Prüfstand (Dialog offen, `route_voll` mit `showSavePresetDialog: true`); `wertebereiche_sprache.test.ts` 175, 184, 295 und `ausblick_ein_name_3155.test.ts` 61: Sprachcheck des Dialogs (DE/EN, Schlüssel-Abdeckung).
- `frontend/src/lib/i18n/__tests__/keine_hartkodierten_nutzertexte.test.ts`, `deutsch_unveraendert.test.ts`: Katalog/Texte.
- `frontend/src/lib/components/trip-detail/bug_499_skala_label.test.ts` 25, 73-90: Dialog darf „Skala“ nicht enthalten (bleibt trivial).
- `compare/__tests__/compareDeadcodeCleanup.test.ts`: betrifft nur die gelöschte `compare/SavePresetDialog.svelte`.
- Elementliste: `docs/context/einstellungen_neu/elementliste.json` Zeilen 504-513 (trip/normal), 1367-1376 (trip/luecken), 1856-1865 (orte/normal), 2562-2571 (orte/luecken): Abschnitte `vorlage-speichern` (9 Einträge: Titel, Name, Platzhalter, Beschreibung(optional), Platzhalter, Standard, Hinweis, Speichern, Abbrechen) und `vorlage-speichern-fehler` (1). **Die Elementliste kennt den Dialog bereits** (Texte und Reihenfolge Speichern vor Abbrechen); sie unterscheidet nicht zwischen Overlay und Inline-Karte — keine Änderung nötig. Keine Einträge in `elementliste_besitzer.json`/`elementliste_freigaben.json` zu `vorlage-speichern` (grep leer). Ordnung 1-9 deckt sich NICHT mit der Mockup-Reihenfolge der Fehlerzeile (Mockup: Fehler nach Name) — Abgleich liest Texte, nicht Position.

## Existing Patterns

- **Kein eigener Inline-Karten-Baustein vorhanden.** In `organisms/wetter-tab/` sind alle Kartenrahmen lokale Klassen (`.wt-karte`, in `VorlageKarte.svelte` Z.158-170 und `WetterTabInhalt.svelte`; `Card`-Atom setzt per `style:` inline und ist für Seiten-Scope nach ADR-0112 Regel (a) zulässig nur über Baustein). Der Wechsel-Frage-Kasten `.wt-frage` (`role="alertdialog"`, `VorlageKarte.svelte` 111-120, 294-305) ist die nächste Verwandte: Inline-Kasten **innerhalb** des Picker-Menüs, Titel fett als `<b>`, Rumpf-Text, `.wt-reihe` mit `Btn variant=accent size=tap` + `ghost`. Er hat **kein** Escape/Fokus-Management außer dem Picker-Escape (`taste`, Z.89). → Für den Dialog dieselbe Bauweise: `<div class="wt-karte" role="group"/aria-labelledby>` mit `Btn`-Knöpfen (`variant="accent"` Speichern, `variant="ghost"` Abbrechen, `size="tap"`).
- **Atome vorhanden:** `Btn` (accent/ghost/quiet, size tap), `Input` (Wrapper um `ui/input`, `bind:value`, `data-testid`, `aria-*` durchgereicht), `Haken` (an/aus = echtes `<input type=checkbox>` im Atom, Props `zustand`, `name` = aria-label, `onAenderung`, `testid`; 28px Box + Tastaturfokus-Ring; rendert selbst ein `<label>` → **nicht in ein weiteres `<label>` schachteln**), `Switch`, `Eyebrow`. **Fehlt:** Textarea (wird mit einzeiligem Feld überflüssig — Mockup ist `input`), „Kontrollkästchen mit klickbarem Text“ (`label.chk`). Die Aufruferin kann `Haken` + `<span>` mit `for`/`aria-labelledby` zusammensetzen; der Text wäre dann nicht klickbar (Mockup: ganzes Label klickbar). Entweder kleiner neuer Baustein (ADR-0112 Pkt. 2: erst im Design-System bauen, eigener Schritt) oder `Haken` um optionalen `beschriftung`-Prop erweitern (Haken liegt in `atoms/`, Tests in `atoms/__tests__`).
- **Feldbeschriftung:** `GrenzenEditor.svelte` (organisms/wetter-tab) nutzt `type=` Felder/Beschriftungen — Muster für beschriftete Felder im Reiter dort lesen; Label-Stil Mockup `.field label`: Mono 10px, Großbuchstaben, `--g-ink-3` (live heute 13px normal) → Bild-Abweichung, beim Bau gleich mitbeheben.
- **Marker/Testids:** `data-abschnitt="vorlage-speichern"` (Karte), `…-fehler` (Fehlerzeile), `data-testid` unverändert beibehalten (s. Tests).
- **i18n:** nur `$t('wetter.dialog.*')`, `aktionen.*`; DE/EN-Parität per `deutsch_unveraendert`/Katalog-Tests.

## Dependencies

- Eingehend: `VorlageKarte` (Hauptpfad, Hubs Trip/Orts-Vergleich ab `WetterTabInhalt`), `WeatherMetricsTab` (Alt-Pfad, Anlege-Editor, voraussichtlich ohne Profil-Karte erreichbar → vor Umbau prüfen).
- Ausgehend: `api.post('/api/metric-presets')`, `eigeneVorlagePayload`, `vorlagenNameFehler`, `$lib/i18n`, Atoms (`Btn`, `Input`, `Haken`).
- Tests/Wächter: `bausteine_waechter` (BESTAND-Ratsche, ggf. SEITEN_SCOPE), `harte_farben_waechter`, `s3a2794_teil3_keine_nativen_controls`, Elementliste-Abgleich (Staging), Kontrast-/Touch-Messung im E2E.

## Existing Specs/ADRs

- `docs/specs/modules/feat_3111_wetter_dialoge_mockup.md` (AC-7: Texte, Platzhalter, Speichern vor Abbrechen; **Struktur ausdrücklich nicht** — Abspaltung #3190), `docs/specs/modules/feat_3189_vorlage_herkunft.md` (`herkunft`-Prop, bleibt), `docs/specs/modules/feat_2794_s3a_teil3_wetter.md` §5 (AC-42, AC-40 keine nativen Controls).
- ADR-0112 (nur Bausteine + Tokens; Wächter; fehlender Baustein zuerst im Design-System), ADR-0111 (keine nativen Controls, Design-Vorgaben), ADR-0104/`i18n_konventionen.md` (Katalog), ADR-0095 nicht berührt.
- `docs/reference/design_system.md` (Kontrast hoch, WCAG-AA, Touch-Ziel `--g-tap-min` 44px).
- CLAUDE.md: Trip/Ortsvergleich-Code-Teilung — ein Code mit `context="route"|"vergleich"`; der Umbau betrifft nur den geteilten Dialog, kein Pendant-Risiko.

## Risks

1. **Escape-Verhalten**: E2E (`s3a2794-teil3-dialog` 89/103, `-design` 119) und Elementliste-Bedienplan (`elementliste_abgleich_logik.ts` 436-445 + Verdrahtungstest 501) schließen den Dialog per Escape. Wird Escape bei der Inline-Karte entfernt, schlagen diese fehl bzw. der Toggle-Knopf schließt statt zu öffnen. Entscheidung (technisch): **Escape beibehalten** (Fokus in der Karte, Escape schließt und gibt Fokus an den Auslöseknopf zurück) — erhält alle Tests; Mockup ist keine Gegenaussage (er hat nur keine Tastaturbehandlung).
2. **Fokus**: Overlay hat heute weder Fokusfalle noch Fokus-auf-Name nach Öffnen (`tabindex=-1`, kein `focus()`). Inline-Karte: Fokus nach Öffnen in das Namensfeld setzen (Name ist Pflicht), nach Schließen/Speichern auf `wetter-vorlage-als-eigene` zurück; sonst Fokusverlust (Karte verschwindet unter dem Fokus). Ohne `aria-modal` kein Fokusfang nötig; `role="group"` + `aria-labelledby` genügt (kein `role=dialog`, da nicht modal; `epic-138`/`2966`-Tests prüfen kein `role=dialog` am Dialog — nur `data-testid`).
3. **Native-Control-Wächter**: Ankreuzfeld muss `Haken` sein (nicht `<input type=checkbox>` in der Datei); `<input>`/`<textarea>`/rohe `<button>` bleiben bis zum Umbau auf Atome Ausnahme im BESTAND. Zieht man auf Atome um (ADR-0112), muss `SavePresetDialog` von BESTAND nach SEITEN_SCOPE (Ratsche sinkt, `BESTAND_OBERGRENZE` mit senken) — Wächter rot sonst.
4. **Harte-Farben-Wächter** Z.69: Scrim-Ausnahme entfällt; `rgba(...)` weg, Ausnahme streichen, sonst „verwaiste Ausnahme“ rot.
5. **Alt-Pfad `WeatherMetricsTab`**: Inline-Karte am Seitenende (Z.2017) wäre unsichtbar/unpassend; entweder Platzierung unter die Profil-Karte (nahe `WeatherV2PresetBar` Z.1706) verschieben oder Pfad als totes Gleis nachweisen (Panel nur `bereich="zustellung"`). Vorher im Render prüfen, nicht raten.
6. **Toggle des Auslöseknopfs**: Mockup schaltet um (`!saveOpen`); live `dialogOffen = true`. Mit Inline-Karte ohne Scrim ist erneutes Klicken sonst folgenlos; Toggle + `aria-expanded` am Knopf empfohlen. Prüfen: `wetter_tab`-Tests, die den Knopf zweimal klicken (E2E Duplikat-Pfad Z.97 öffnet nach Escape wieder, kein Doppelklick).
7. **Fehler-Position/Stil**: Mockup `span.err` direkt unter Name, Token `--g-bad`; live Absatz am Ende, Token `--g-danger`. Elementliste gruppiert „Fehler“ als eigenen Abschnitt — Reihenfolge der Texte nicht verändert; Staging-Abgleich liest per Text.
8. **Layout/Z-Index**: Inline-Karte schiebt die Metrik-Karte nach unten (Layout-Shift beim Öffnen); bewusstes Mockup-Verhalten, im Ganzseiten-Vergleich (`mockup-bildpruefer`) „Dialog offen“-Zustand zusätzlich festhalten.
9. **Textbereich→Feld**: `maxlength=120` bleibt; Altwert mit Zeilenumbruch kann es im einzeiligen Feld nicht geben (neu eingegeben). API unverändert.

## Analysis

### Type
Änderung eines bestehenden Bausteins (Oberflächenabweichung zum Mockup; kein Bug, keine API-/Datenänderung). Frontend-only.

### Affected Files (with changes)

| Datei | Änderung |
|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | Overlay/Scrim/`role=dialog`/×-Knopf raus → Inline-Karte (`wt-karte`-Optik), Reihenfolge nach Mockup (Titel, Name, Fehler, Beschreibung, Ankreuzfeld, Hinweis, Knöpfe), `<textarea>`→`Input` (einzeilig), `role=switch`→`Haken` (+ klickbarer Text), `Btn` accent/ghost, Fokus setzen/zurückgeben, Escape-Handler behalten (nur bei Fokus in der Karte), eigenes `<style>` auf Tokens reduzieren oder ganz auf Atome. |
| `frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte` | Dialog-Einbindung als Geschwister innerhalb der Karten-Spalte: Position unter `.wt-karte`; Auslöseknopf toggelt (`aria-expanded`); Fokus-Rückgabe; Picker-Escape-Logik (Z.89) prüfen. Falls Inline-Karte unter dem Eltern-Flex stehen soll: `VorlageKarte` gibt Fragment `<div .../> <SavePresetDialog/>` zurück (bereits so; ggf. Reihenfolge im Eltern-Gap). |
| `frontend/src/lib/components/atoms/Haken.svelte` (+ `atoms/__tests__`) | Nur falls „Haken mit Beschriftung“ gewählt: optionaler Prop `beschriftung` (klickbarer Text, ein `<label>`); sonst keine Änderung. |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Alt-Pfad: Platzierung der Karte oder Nachweis „unerreichbar“ (Z.2017). |
| `frontend/src/lib/__tests__/bausteine_waechter_regeln.ts` (601) / `harte_farben_waechter.test.ts` (69) | BESTAND/Ausnahmen anpassen (Ratsche sinkt). |
| Tests (neu/angepasst) | `feat_3111_wetter_dialoge_mockup.test.ts` 350-379 (Atom-Render: Texte in Kind-Elementen), neuer Render-Test Struktur (kein `role=dialog`, kein `aria-modal`, kein Scrim, `input` statt `textarea`, `Haken`/checkbox mit Namen, Reihenfolge Fehler nach Name, Speichern vor Abbrechen), E2E `s3a2794-teil3-dialog.spec.ts` (Ankreuzfeld-Assertion `toContainText` → an `save-preset-is-default` ggf. Label-Container, Escape+Fokus), `-design.spec.ts` (Messungen im Inline-Zustand). Elementliste unverändert. |
| `frontend/src/lib/i18n/messages/{de,en}/wetter.json` | Keine Änderung erwartet (nur falls neuer a11y-Name nötig). |

### Scope Assessment
Klein bis mittel: 2-3 Quelldateien, ~100 Zeilen Svelte netto sinkend (Overlay-CSS fällt weg), 4-6 Testdateien. Unter LoC-Limit; ein Workflow. Unabhängig von #3189 (liegt bereits gemergt).

### Technical Approach

1. Dialog bleibt EIN Code in `shared/weather-metrics-tab/SavePresetDialog.svelte` (Trip/Vergleich per `kind`), wird zur Inline-Karte; Testids und `data-abschnitt` unverändert.
2. Wurzel: `<div class="wt-karte" role="group" aria-labelledby="spd-titel" data-testid="save-preset-dialog" data-abschnitt="vorlage-speichern">`; kein Scrim/×/`aria-modal`/`tabindex=-1`. Titel `<b id="spd-titel">`.
3. Name: `Input` mit zugehörigem `<label for>`; Fehlerzeile (`role="alert"`, testid `save-preset-error`, `data-abschnitt="vorlage-speichern-fehler"`) **direkt darunter** (wie Mockup), `aria-describedby`/`aria-invalid` am Feld.
4. Beschreibung: `Input` (einzeilig, `maxlength=120`), testid `save-preset-description`.
5. Standard: `Haken` (zustand `an|aus`, `onAenderung`) mit sichtbarem, klickbarem Text „Als Standard für neue …“ (testid `save-preset-is-default` am Element, das den Text enthält). Bevorzugt `Haken` um `beschriftung`-Prop erweitern statt neuen Baustein (kleinste Änderung, gleiche Familie); Text nicht doppelt schachteln.
6. Hinweis als `<p>` (`save-preset-hinweis`, 12.5px/`--g-ink-2`), Knöpfe `Btn` accent „Speichern“ (testid `save-preset-submit`) vor ghost „Abbrechen“, `size=tap`.
7. Fokus: bei `open`→true `Name` fokussieren; bei Schließen/Speichern/Abbrechen/Escape Fokus auf Auslöseknopf (`wetter-vorlage-als-eigene`) via Callback-Prop (`onClose`) bzw. Referenz in `VorlageKarte`. Escape nur wenn Fokus in der Karte (`keydown` auf der Karte statt `svelte:window`), damit Picker-Escape unabhängig bleibt; `VorlageKarte.taste` Z.89 vereinfachen.
8. `VorlageKarte`: Knopf toggelt `dialogOffen` + `aria-expanded`/`aria-controls`; Erfolgsmeldung unverändert.
9. Alt-Pfad `WeatherMetricsTab`: Nutzbarkeit prüfen; sonst Platzierung unter die Profil-Karte.
10. Wächter anpassen (BESTAND/Harte-Farben), Tests nach dem Muster in „Pinnende Tests“; Staging: Ganzseitenvergleich Zustand „Dialog offen“ (Trip und Orts-Vergleich, Desktop und mobil) gegen Mockup.

### Befunde gegen den Plan

- Issue nennt `SavePresetDialog.svelte:84-127`; tatsächlich Overlay 106-153 (Zeilenstand nach #3189), Inhalt gleich.
- Issue nennt nur `s3a2794-teil3-dialog.spec.ts` als Overlay-Pin; es pinnen zusätzlich: `-design.spec.ts` (Kontrast, Touch, Escape), `epic-138-block-b`, `issue-343-horizon-chips`, Elementliste-Bedienplan (Escape, `elementliste_abgleich_logik.ts` 436-445) und der Wächtertest `s3a2794_teil3_keine_nativen_controls` (verbietet native Checkbox in dieser Datei — Mockup-`<input type=checkbox>` darf also nur über das `Haken`-Atom entstehen).
- „ohne Elementlisten-Eintrag“ stimmt für die Struktur, nicht für den Inhalt: der Dialog (`vorlage-speichern`, `-fehler`) ist in allen vier Elementlisten-Zuständen mit allen Texten erfasst; Abgleich ist textbasiert, Strukturabweichung (Inline vs. Overlay, Checkbox vs. Switch) fiel deshalb nicht auf.
- Zweiter Nutzer `WeatherMetricsTab` (Alt-Editor) im Issue nicht erwähnt.
- Mockup nimmt Fehlerzeile direkt unter den Namen; live am Ende — im Issue nicht erwähnt, mit umzusetzen.
- Mockup `.field label` (Mono 10px caps) vs. live 13px: weitere kleine Bildabweichung im selben Bauteil.
- Ein Bildzustand „Dialog offen“ existiert als `bilder-fassung4`-Material? Nicht geprüft; im Workflow Mockup-Zustand `saveOpen` rendern.

### Open Questions

Keine echten Produktfragen: Soll ist durch das Mockup (Epic #2913) eindeutig festgelegt; Escape/Fokus/Atom-Wahl sind technische Entscheidungen (oben getroffen). Einzige rein fachliche Rückmeldung für den PO nach Fertigstellung: Bild des geöffneten Dialogs (Soll/Ist).
