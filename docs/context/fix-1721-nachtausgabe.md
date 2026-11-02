# Context: fix-1721-nachtausgabe

## Request Summary
Issue #1721 (Epic #2259): Die Nachtausgabe der Trip-Mail ist nicht steuerbar bzw. falsch beschriftet. Drei Punkte: (1) Nacht-Stundentabelle hat keinen Schalter in der Oberfläche, (2) Ausblick-Spalte `N` falsch beschriftet, (3) `FN` nirgends erklärt. PO-Leitplanke 2026-08-11 („KRITISCH"): Punkte 1 und 3 brauchen einen echten Browserlauf mit Klickpfad unter `frontend/e2e/`, Punkt 2 einen Nachweis an der zugestellten Mail.

## Stand der drei Punkte (am Code geprüft, Stand 2026-11-02)

| Punkt | Stand | Beleg |
|---|---|---|
| 1 Schalter `show_night_block` | **Offen.** Backend wertet aus, keine Bedienung | `trip_report.py:168` (Gate), `models.py:655`/`:829` (Default True), `loader.py:1088`/`:1615`/`:1832` (Laden/Speichern), `metric_catalog.py:1289`; Frontend nur als durchgereichtes Feld in Tests (`pick_eigenfelder_kernregel.test.ts`, `trip_reiter_nutzlast_nur_eigene_felder.test.ts`), **kein** `.svelte`-Treffer; Go: kein Treffer (vermutlich generische Durchreichung) |
| 2 Ausblick-Spalte `N` | **Vermutlich durch #2136 erledigt.** Spalten heißen jetzt `Temp min`/`Temp max` aus `col_label` + `aggregation_label_de`; die Legende „Nacht-Tief" in `html.py` ist nicht mehr auffindbar | `outlook.py:~225-245` (`_pfad1_labels`), `fix_2136_outlook_col_label.md` (status implemented). **Offen:** füllt die Spalte weiter das Tages-Minimum, und passt dazu die Beschriftung? Nachweis an zugestellter Mail fehlt noch |
| 3 `FN` erklärt | **Vermutlich erledigt.** Die Legende ist aus dem Katalog abgeleitet (`kuerzelLegende.ts`, #1888), `wind_chill_night` ist im Wetter-Metriken-Reiter eingebunden | `WeatherMetricsTab.svelte:1935-1939`. **Offen:** zeigt die Legende `FN` wirklich, wenn die Metrik gewählt ist, per Browserlauf? |

## Related Files
| File | Relevanz |
|---|---|
| `src/app/models.py` (`:655`, `:829`) | `show_night_block` im Datenmodell |
| `src/app/loader.py` (`:1088`, `:1615`, `:1832`) | Laden/Speichern, Merge-Pflicht (Schema-Regel) |
| `src/output/renderers/trip_report.py:166-170` | Gate der Nacht-Stundentabelle |
| `src/services/segment_weather.py:523-550` | `night_weather_needed()` – Nachtdaten-Beschaffung hängt an `show_night_block` ODER Nacht-Metriken/Gewitter |
| `src/output/renderers/email/outlook.py` | 3-Tages-Ausblick, Kopfzeilen |
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherMetricsTab.svelte` | Wetter-Metriken-Reiter, hier gehört der Schalter hin |
| `frontend/src/lib/components/shared/weather-metrics-tab/kuerzelLegende.ts` | Legenden-Ableitung (Trip + Ortsvergleich) |
| `frontend/src/lib/components/shared/__tests__/pick_eigenfelder_kernregel.test.ts`, `.../trip-detail/__tests__/trip_reiter_nutzlast_nur_eigene_felder.test.ts` | Nutzlast-Wächter: neue Eigenfelder müssen dort bewusst berücksichtigt werden |

## Existing Patterns
- Wetter-Metriken-Reiter ist ein geteilter Organismus für Trip und Ortsvergleich (`context="route"|"vergleich"`). Ein Schalter dort ist ein Trip/Compare-Teilungsthema: nur sinnvoll, wenn der Ortsvergleich das Konzept „Nacht-Stundentabelle" hat, sonst ausblenden und nicht doppelt bauen.
- `night_weather_needed()` ist die geteilte Entscheidung für Versand und Vorschau. Ein Schalter darf sie nicht verändern, ohne dass Vorschau und Versand weiter dieselbe Quelle nutzen (#1484 AC-8).
- Spaltenköpfe des Ausblicks kommen seit #2136 aus `col_label` (ADR-0068).

## Dependencies
- Upstream: `DisplayConfig` (Python) ↔ Go-Persistenz (generische Durchreichung, noch zu bestätigen) ↔ Frontend-Typen.
- Downstream: Trip-Mail (Voll + Kompakt), Vorschau, Briefing-Validator (`briefing_mail_validator.py`).

## Existing Specs
- `docs/specs/modules/feat_1484_night_temp_metric.md`, `fix_1339_nachtwetter_fallback.md`, `briefing_parity_night_thunder.md`, `fix_2136_outlook_col_label.md`, `fix_1888_e6b_kuerzel_legende.md`.

## Risks & Considerations
- **Schema-Regel:** Der Schalter ist ein bestehendes Feld. Beim Speichern darf `show_night_block` nicht verloren gehen oder bei Alt-Trips auf den Default springen (Read-Modify-Write mit Merge). Pre-Snapshot-Hook greift bei Schema-Dateien.
- **Wirkung nur im Reiter sichtbar:** Wird die Nachttabelle abgeschaltet, müssen Nacht-Metriken (`N`, `FN`) und der Gewitter-Nachtsatz weiter funktionieren (`night_weather_needed`).
- **Renderer-Commit-Gate:** Änderungen an `trip_report.py` oder `outlook.py` lösen Modus-Matrix-Test und Validator aus.
- **Testpflicht:** Punkt 1 braucht Klickpfad im Browser (Schalter umlegen → speichern → Mail ohne Nachttabelle), mit zwei verschiedenen Nutzern (Multi-User-Regel). Punkte 2 und 3 brauchen nur dann Code, wenn die Analyse eine echte Lücke findet; sonst genügt ein Nachweis, und das Ticket wird entsprechend eingegrenzt.
- **Scope-Frage für die Analyse:** Gilt der Schalter auch für den Ortsvergleich? Laut `models.py:829` gibt es das Feld in einer zweiten Klasse, zu klären ist, welche.

## Analysis

### Type
Bug (Teil-Feature): Punkt 1 echte Lücke, Punkte 2 und 3 am Code bereits behoben (Nachweis offen).

### Befund je Punkt
| Punkt | Ergebnis | Beleg |
|---|---|---|
| 1 Schalter `show_night_block` | **Echte Lücke.** Backend wertet aus (`trip_report.py:168`), Laden/Speichern vorhanden (`loader.py:1088`, `:1832`), Frontend hat kein Bedienelement. Nur der Trip hat eine Nacht-Stundentabelle: `_extract_night_rows` wird ausschließlich in `trip_report.py` gerufen; der Ortsvergleich-Renderer kennt keinen Nachtblock (`loader.py:1615` speichert das Feld bei Orten nur mit, ohne Wirkung). | siehe Related Files |
| 2 Spalte `N` | **Behoben durch #2136.** Köpfe lauten `Temp min`/`Temp max`, Quelle `temp_lo`/`temp_hi` = Tages-Min/-Max (`outlook.py:263-266`). Beschriftung und Inhalt passen. Legende „Nacht-Tief" existiert nicht mehr. Es fehlt nur der Nachweis an zugestellter Mail. | `outlook.py:225-245` |
| 3 `FN` erklärt | **Behoben.** `wind_chill_night` ist im Reiter eingebunden (`WeatherMetricsTab.svelte:1935`), Legende aus Katalog (#1888); `kuerzel-legende-lesbar.staging.spec.ts:61` führt `wind_chill_night` bereits. Zu prüfen: prüft diese Spec den Text der FN-Erklärung wirklich (Klickpfad, Metrik wählen → Legende zeigt FN)? | `kuerzelLegende.ts` |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Schalter „Nacht-Stundentabelle in der Mail" nur bei `context="route"`; im Ortsvergleich ausgeblendet |
| Frontend-Typ/Payload der Trip-Konfiguration (Fundort in Phase 3 klären) | MODIFY | `show_night_block` als bewusstes Eigenfeld, Nutzlast-Wächter-Tests anpassen |
| `frontend/e2e/…night-block….spec.ts` | CREATE | Klickpfad: Schalter aus → speichern → neu laden bleibt aus → zugestellte Mail ohne Nachttabelle; zwei Nutzer |
| `frontend/e2e/kuerzel-legende-lesbar.staging.spec.ts` | MODIFY (ggf.) | Nur falls FN-Text nicht explizit geprüft wird |
| Go-API | PRÜFEN | Durchreichung `show_night_block` (vermutlich generisch, `config_merge_structure_test.go`) |
| Python | keine Änderung erwartet | Gate und Persistenz stehen; `night_weather_needed` bleibt unberührt |

### Scope Assessment
- Files: ca. 3–5 · Estimated LoC: +120/-10 (überwiegend Test)
- Risk Level: LOW–MEDIUM (Speichern darf `show_night_block` bei Alt-Trips nicht auf Default springen lassen: Merge-Pflicht)

### Technical Approach
1. Schalter im Wetter-Metriken-Reiter, nur Trip-Kontext (Nachtblock existiert nur dort; kein Ortsvergleich-Pendant ⇒ keine Doppelbau-Verletzung).
2. Speichern per Read-Modify-Write; Default `True` bleibt, Alt-Trips ohne Feld laufen unverändert.
3. Abschalten wirkt nur auf die Tabelle; Nacht-Metriken `N`/`FN` und Gewitter-Nachtsatz laufen weiter über `night_weather_needed`.
4. Punkt 2: Nachweis an echter zugestellter Staging-Mail (Spaltenköpfe + Werte), kein Code. Punkt 3: Browserlauf-Nachweis, Code nur bei Lücke.
5. Ticket-Eingrenzung: Punkte 2 und 3 mit Beleg im Issue vermerken.

### Dependencies
`DisplayConfig` Python ↔ Go (generisch) ↔ Frontend-Typen; Mail-Validator `briefing_mail_validator.py` (Trip-Briefing).

### Open Questions
- [ ] Beschriftung des Schalters (Vorschlag: „Nacht-Stundentabelle in der Mail zeigen")? Reine Textfrage, wird in der Spec festgelegt.
- [ ] Go-Durchreichung des Felds: in Phase 3/4 per Test bestätigen.
