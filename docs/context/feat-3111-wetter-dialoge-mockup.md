# Context: feat-3111-wetter-dialoge-mockup

## Request Summary
Issue #3111 (Epic #2913): Die Dialoge im Hub-Reiter Wetter (Grenzen ändern, Vorlage-Auswahl, Vorlage-Bestätigung, Vorlage speichern) an das angenommene Mockup angleichen (Soll jetzt `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html`, Fassung 3 ist entfernt), DE und EN, und die 156 Besitzer-Einträge `#3111` abräumen.

## Befunde gegen Fassung 4 (alle gelten noch)
| Punkt | Mockup F4 | Live |
|---|---|---|
| Grenzen-Gruppentitel | Z.463-464 `unten<br>zu wenig` / `oben<br>zu viel` | `wetter.grenzen.unten/oben` = „unten / zu wenig“ (de/wetter.json:84-85); `.wt-grp-name` max-width 9ch (GrenzenEditor.svelte:111-116) |
| Hinweis-Anführungszeichen | Z.465 „gelb unten“ | ‚gelb unten‘ (de/wetter.json:86) |
| „Abweichend von der Vorlage …“ | Z.465/Z.460 im selben span am Hinweis angehängt | eigenes `<p>` (GrenzenEditor.svelte:86-88, testid `wetter-grenzen-abweichend-{id}`), Quotes ‚‘ (de/wetter.json:87) |
| „· aktiv“ | Z.490 Text-Zusatz | nur `data-aktiv` (VorlageKarte.svelte:99) |
| Kurzbeschreibung Systemvorlage | Z.356 kuratiert („14 Metriken · Gewitter, Böen, Nullgradgrenze“) | Zahl + erste drei aktive Metriken (wetterTabLaden.ts:43-49; VorlageKarte.svelte:47-49); Spec feat_2794_s3a Z.123 / AC-10 Z.209 verlangt Ableitung |
| Eigene Vorlage Unterzeile | Z.357/Z.490 `eigene · aus GR221 gespeichert` | keine Unterzeile (VorlageKarte.svelte:109-111); `description` existiert am Preset (types.ts:369) |
| Vorlage-Bestätigung | Z.488 `<b>„{pending}“ übernehmen?</b><span>Ersetzt …</span>` | ein `<p>` (VorlageKarte.svelte:85-89), Quotes ‚‘ (de/wetter.json:15-18); Knopf-Reihenfolge gleich |
| Label Beschreibung | Z.497 „Beschreibung (optional)“ | „Beschreibung“ (SavePresetDialog.svelte:108; Spec feat_2794_s3a Z.139 sagt „(optional)“) |
| Platzhalter | Z.495 „z.B. Mallorca Frühling“, Z.497 „wofür die Vorlage gedacht ist“ | keine |
| Knopf-Reihenfolge Speichern-Dialog | Z.500 Speichern vor Abbrechen | Abbrechen (:122) vor Speichern (:123) |
| weitere (nicht im Issue) | Checkbox Standard (Z.498), Inline-Karte, `<input>` Beschreibung | role=switch, modales Overlay, `<textarea>` |

Zahl-Abweichung: Mockup „Wandern 10 Metriken“, Ampel-Definition 11 aktiv — Zahl bleibt aus Daten abgeleitet (Mockup-Beispieldaten-Thema, vgl. #2967/#3151).

## Related Files
| File | Relevance |
|---|---|
| frontend/src/lib/components/organisms/wetter-tab/GrenzenEditor.svelte | Grenzen-Dialog |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | Auswahl, Bestätigung, Kurzbeschreibung |
| frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte | Vorlage speichern |
| frontend/src/lib/components/organisms/wetter-tab/WetterTabInhalt.svelte | Wrapper (abweichend :226/:281) |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | Kurzbeschreibung-Ableitung |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | Texte (vorlage 8-29, grenzen 82-92, dialog 108-116) |
| docs/context/einstellungen_neu/elementliste_besitzer.json | 156 Einträge `#3111` (grenzen 96, vorlage-auswahl 36, vorlage-speichern 16, bestaetigung 8) |
| tests/test_2913_c2_besitzerliste.py:126 | Zählwächter `"#3111": 156` |
| docs/specs/modules/feat_2794_s3a_reiter_wetter.md | freigegebene Spec mit Live-Form (Z.123, 124, 139, AC-10) |

## Existing Patterns
- Trip/Orte geteilt über `context="route"|"vergleich"` (WetterTab.svelte:9-12); GrenzenEditor/MetrikZeile kontextfrei.
- Texte nur über i18n-Katalog (ADR-0104); `deutsch_unveraendert.test.ts` Z.538-629 listet die Schlüssel.
- Vorgänger-Muster für Mockup-Angleichung: #3012 (Katalogtexte), #3006/#3007.

## Dependencies / Dependents
- Upstream: Katalog, `/api/templates` (api/routers/config.py:25-35), WEATHER_TEMPLATES ohne Beschreibungsfeld.
- Downstream: Trip-Hub, Orte-Hub, TripNewEditor/CompareNewEditor (Anlegen), Elementlisten-Abgleich.

## Tests, die die Live-Form pinnen (werden angepasst)
- Unit: s3a2794_teil3_wetter_katalog.test.ts (Z.55-109), wetter_tab_abschnitt_marker_2966.test.ts, deutsch_unveraendert.test.ts, elementliste_abgleich_bedienplan.test.ts
- E2E: s3a2794-teil3-vorlage.spec.ts:48/:76/:80, s3a2794-teil3-grenzen.spec.ts:56, s3a2794-teil3-dialog.spec.ts, s3a2794-teil3-englisch.spec.ts

## Risks & Considerations
- Spec-Konflikt: feat_2794_s3a schreibt Live-Form vor. Epic #2913 (PO-Vorgabe) setzt das Mockup als Soll ⇒ neue Spec mit Verweis „löst Teile von feat_2794_s3a ab“.
- Kuratierte Stichworte für Systemvorlagen: neue Katalogtexte je Vorlage (DE/EN), keine Datenmodell-Änderung.
- Standard-Schalter/Overlay vs. Inline-Karte: Baustein-Frage (ADR-0112) — im Analyse-Schritt entscheiden, ob in Scope.
- Besitzer-Einträge: nach Umbau Staging-Abgleich DE/EN, Einträge entfernen, Zählwächter nachziehen.

## Analysis

### Type
Feature (Mockup-Angleichung, Epic #2913)

### Messung des Abgleichs
`normalisiere()` (frontend/e2e/elementliste_abgleich_logik.ts:199-206) vergleicht nur Text: Leerraum, Anführungszeichen („“→", ‚‘→') und geschütztes Leerzeichen werden vereinheitlicht. Die Elementliste verwirft `<br>`: Einträge `"untenzu wenig"` / `"obenzu viel"` (elementliste.json:362, :368). Offen: Liest der Sammler `textContent` (dann `{a}<br>{b}` ohne Leerraum passend) oder `innerText`? In den Abgleich-Dateien ist kein Treffer für beides; die Lese-Stelle ist in Phase 4 (RED) per Test im echten Browser festzustellen, bevor die `<br>`-Lösung gebaut wird.

### Affected Files (with changes)
| File | Change Type | Description |
|---|---|---|
| frontend/src/lib/components/organisms/wetter-tab/GrenzenEditor.svelte | MODIFY | Titel zweiteilig `{unten_1}<br>{unten_2}`; Abweichend-Satz im selben Absatz wie der Hinweis (Span behält testid `wetter-grenzen-abweichend-{id}`) |
| frontend/src/lib/components/organisms/wetter-tab/VorlageKarte.svelte | MODIFY | „· aktiv“ als Text; Stichworte kuratiert; Unterzeile eigener Vorlagen („eigene“ + description); Bestätigung als `<b>`-Titel + Rumpf |
| frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte | MODIFY | Label „Beschreibung (optional)“, Platzhalter Name/Beschreibung, Speichern vor Abbrechen |
| frontend/src/lib/components/shared/wetter-tab/wetterTabLaden.ts | MODIFY | Stichworte der Systemvorlagen aus Katalog je Vorlage-ID, Zahl aus Daten; Fallback Ableitung für unbekannte IDs |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | neue Schlüssel (grenzen.unten_1/_2, oben_1/_2, vorlage.aktiv_marker, vorlage.stichworte.*, vorlage.frage_titel, ersetzt_route/_vergleich, dialog.*_platzhalter), Quotes „“ |
| docs/context/einstellungen_neu/elementliste_besitzer.json | MODIFY | Einträge `#3111` entfernen (nach Staging-Abgleich) |
| tests/test_2913_c2_besitzerliste.py | MODIFY | Zählwächter `#3111` auf Reststand |
| Unit: s3a2794_teil3_wetter_katalog, deutsch_unveraendert, wetter_tab_abschnitt_marker_2966, elementliste_abgleich_bedienplan | MODIFY | neue Form |
| E2E: s3a2794-teil3-vorlage/-grenzen/-dialog/-englisch | MODIFY | neue Form |
| docs/specs/modules/feat_3111_wetter_dialoge_mockup.md | CREATE | neue Spec, löst feat_2794_s3a Z.123/124/139/AC-10 in diesen Punkten ab |

### Scope Assessment
- Produktdateien 6 (ggf. WetterTabInhalt.svelte als 7.), ca. 120-180 LoC + ca. 40 Katalogzeilen
- Risk Level: MEDIUM (geteilter Code Trip/Orte, viele Tests pinnen Live-Form; kein Backend, kein Datenmodell)

### Technical Approach (Entscheidungen Tech Lead)
1. Mockup Fassung 4 ist Soll (Epic #2913); neue Spec löst die abweichenden Stellen von feat_2794_s3a ab.
2. Grenzen-Titel: zwei Katalogschlüssel + `<br>`, kein Zeilenumbruch im JSON.
3. Kuratierte Stichworte je Systemvorlage im Katalog (DE/EN), Zahl bleibt aus Daten (elementliste.json:484 hat `{zahl}`-Muster). WEATHER_TEMPLATES unverändert.
4. Bestätigung zweiteilig; `frage_vergleich` an Mockup-Wortlaut („für diesen Ort / diese Orte“) angleichen.
5. Unterzeile eigener Vorlagen: „eigene“ + vorhandene `description`. Die Herkunft „aus GR221 gespeichert“ braucht ein neues Datenfeld (Backend) ⇒ Kind-Issue #3189 von #2913, die betroffenen Besitzer-Einträge wandern dorthin.
6. Steuerelement-Abweichungen (Checkbox statt Schalter, Inline-Karte statt modalem Dialog, einzeiliges Feld statt Textbereich) stehen nicht in der Elementliste, sind aber Ganzseitenbild-Abweichungen ⇒ Kind-Issue #3190 von #2913 (Besitzer), nicht in dieser Scheibe (Zugänglichkeit, ADR-0112-Bausteinfrage).
7. Abschluss: Staging-Abgleich DE und EN `--scope wetter`, Einträge `#3111` entfernen.

### Dependencies
Geteilter Code Trip/Orte (`context="route"|"vergleich"`, WetterTab.svelte:9-12); Anlegeseiten TripNewEditor/CompareNewEditor nutzen denselben Wetter-Reiter.

### Open Questions
- [ ] Lese-Methode des Abgleich-Sammlers (textContent/innerText) — klärt RED-Test, keine PO-Frage.
