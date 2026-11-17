# Context: feature-2955-wetter-metrik-inhalte

## Request Summary
Reiter Wetter (Trip und Orte, DE/EN) zeigt Metrik-Inhalte anders als das angenommene Mockup
(Fassung 3): Vorbote-Kennzeichnung, Gewitter-Skala/-Satz und -Position, Metrik-Namen, Kopfzähler.
Gebündelt mit #3012 (Katalogtexte „(Orange)“, „Luftfeuchtigkeit/Luftfeuchte“). Teil von Epic #2913.

## Soll laut Mockup (`docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, Z. 279–307)
- TRIP_METRICS (Vorlage Alpen-Trekking): temperature, temperature_night „Tiefsttemperatur Nacht“,
  wind_chill „Gefühlte Temperatur“ **Vorbote, kein Alarm**, wind, gust, wind_direction (nur Anzeige),
  precipitation, **thunder (vor rain_probability)**, rain_probability **Vorbote**, visibility,
  cloud_low „Gipfel in Wolken“ (alarm null → „kein Alarm“, **kein** Vorbote), uv_index, freezing_level,
  snowfall_limit.
- ORTE_METRICS (Vorlage Allgemein): …, thunder, rain_probability **Vorbote**, cloud_total „Bewölkung“
  **Vorbote**, sunshine.
- Vorbote-Zeile: Untertitel „Vorbote, kein Alarm“, Erklärung „Nur im Briefing gefärbt. Vorboten lösen
  keinen Alarm aus.“, rechts „kein Alarm (Vorbote)“.
- Gewitter: Skala-Ticks „keins · mittel · hoch“ (Mockup Z. 344), Hinweis „„keins“ ist immer grün“,
  Satz „… auf mittel oder hoch steigt (Orange)“ (Elementliste Z. 102, i18n `wetter.erklaer.gewitter`).
- Kopf „Alarm ab für alle“ + Zähler „{n} von {m} Metriken … {k} können keinen auslösen (Vorboten und
  reine Anzeige).“ `A5` im Mockup ist nur ein Abgleich-Tag (`tg()`, „neu aus dem Abgleich“), KEIN
  Produkttext → nicht nachbauen.
- Hinweis: Das Issue nennt „Tiefe Wolken“ als Vorbote; laut Mockup ist es cloud_low **nicht**
  (Untertitel „Gipfel in Wolken“), Vorbote ist im Orte-Kontext cloud_total „Bewölkung“.
- #3012: Mockup schreibt Stufe groß „(Orange)“; im Mockup steht in den Aus-Listen „Luftfeuchte“
  (nicht „Luftfeuchtigkeit“) – Issue-Text #3012 nennt die Richtung umgekehrt; Soll = Mockup/Elementliste.

## Related Files
| File | Relevance |
|------|-----------|
| src/app/metric_catalog.py | `MetricDefinition.is_precursor` (Z. 92), Katalog-Einträge (wind_chill Z. 262, humidity Z. 344 precursor, rain_probability Z. 471 precursor, thunder Z. 491, cloud_total Z. 579, cloud_low Z. 598), Reihenfolge `_METRICS` = Anzeige-Reihenfolge, `_REITER_WETTER`/`reiter_wetter_eigenschaften()` Z. 1208–1262 (alertable/is_precursor an /api/metrics) |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | Rendert Untertitel/Erklärung/„Alarm ab“ je Metrik, nutzt `is_precursor` |
| frontend/src/lib/components/shared/wetter-tab/ampelModell.ts | `erklaersatz()`, `gewitterSatz()` Z. 303ff, Gewitter-Stufen, Gruppenfolge |
| frontend/src/lib/components/organisms/wetter-tab/AmpelLeiste.svelte, AlarmAbKopf.svelte, WetterTabInhalt.svelte | Skala-Ticks, Kopfzähler, Reihenfolge |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | `wetter.untertitel.vorbote`, `wetter.erklaer.vorbote`, `wetter.erklaer.nie`, `wetter.alarm_ab.*`, `wetter.erklaer.gewitter` |
| docs/context/einstellungen_neu/elementliste.json | Soll-Texte, `npm run elementliste:abgleich` |
| frontend/src/lib/components/organisms/__tests__/fix2913_metrikliste_mockup.test.ts u. a. | bestehende Tests zum Mockup-Abgleich |

## Existing Patterns
- Reiter-spezifische Eigenschaften kommen aus EINER Python-Quelle (`_REITER_WETTER`) über /api/metrics,
  keine Frontend-Kopie (#2794 S3a, AC-27).
- UI unterstützt Vorbote bereits vollständig (i18n-Schlüssel vorhanden); es fehlt nur die Kennzeichnung
  der Metriken.

## Dependencies
- Upstream: Katalog `_METRICS`, ampel_templates (Vorlagen).
- Downstream von `is_precursor`: `from_display_config()`/`from_alert_rules()` (Alarm-Erzeugung ignoriert
  Vorboten), `weather_change_detection.py`, `api/routers/config.py`, Z. 1468 (Vorboten-Sonderfall).
  Downstream von `_METRICS`-Reihenfolge und `label_de`: Mail-Spalten, SMS/Telegram, Renderer.

## Risks & Considerations
- `is_precursor=True` im Katalog für wind_chill/cloud_total ändert Alarm-Erzeugung im Backend
  (Bestandsnutzer mit Alarm-Regeln auf Gefühlter Temperatur). Im Reiter sind beide heute schon
  `alertable=False`. Zu klären in der Analyse: Reiter-eigene Vorbote-Kennzeichnung vs. Katalogflag.
- Reihenfolge thunder/rain_probability und Name „Tiefsttemperatur Nacht“ nicht über `_METRICS` bzw.
  `label_de` ändern, ohne Mail/SMS-Wirkung zu prüfen (Mail-Spaltenreihenfolge, Telegram-Kopf).
- Zweisprachigkeit: neue Texte nur über Katalog, EN-Gegenstücke pflegen; Kürzel unverändert.
- Trip/Orte-Code-Teilung: eine Änderung in `shared/` bzw. Organismen gilt für beide Kontexte.

## Analysis

### Type
Bug (Inhalte weichen vom freigegebenen Mockup Fassung 3 ab), gebündelt mit #3012.

### Befunde (Ist)
- **Vorbote:** ADR-0010 nennt sechs Vorboten (humidity, dewpoint, rain_probability, cloud_total, pressure, wind_chill); `is_precursor=True` ist nur bei humidity/rain_probability gesetzt. Alle vier übrigen haben `default_change_threshold=None` und im Reiter `alertable=False`. Leser von `is_precursor`: `weather_change_detection.py:643` (from_display_config, greift erst nach threshold-None-Skip), `metric_catalog.py:1471` (Change-Map, ebenso), `reiter_wetter_eigenschaften()` Z. 1258. `from_alert_rules`, Risk-Engine (`risk_thresholds` von wind_chill), Mail/SMS/Telegram-Renderer lesen das Flag NICHT ⇒ keine Alarm-/Kanal-Wirkung.
- **Gewitter-Ticks** „keins · mittel · hoch“ sind bereits umgesetzt (AmpelLeiste.svelte, #2913 Runde 2). Offen: Erklärsatz (`gewitterSatz()` ampelModell.ts ~Z.303) liefert „auf mittel“, Mockup/Elementliste Z.102 „auf mittel oder hoch“.
- **Reihenfolge:** keine Sortierung innerhalb einer Gruppe; `zeilenGruppen()` (ampelModell.ts:333) folgt der Auswahl-Reihenfolge (Trip `metrics[]`, Vergleich `active_metrics`, aus `ampel_templates.py _ZEILEN`, rain_probability vor thunder). `briefingAngebot()` folgt `_METRICS`. Mail-Spalten unabhängig (`compare_html.py CV2_ZEILEN`, `_METRICS`).
- **Namen:** Reiter zeigt `label_de` aus dem Katalog (`metric_catalog.py:194` „Nacht-Tiefsttemperatur“, Z.344 humidity „Luftfeuchtigkeit“). Mockup/Elementliste nutzen „Tiefsttemperatur Nacht“ auch in den Kanal-Inhalt-Blöcken (E-Mail/Telegram/SMS) und „Luftfeuchte“ ⇒ ein Name überall. `label_de` wirkt auf Mail (compare_html.py:501, metric_format.label()), Alarme-Seite, Wertebereiche.
- **Kopfzähler:** `alarmZaehler()` (ampelModell.ts:442) m = Anzahl alarmfähiger; Mockup (Z. 468) m = alle ausgewählten (13), k = nicht alarmfähige (3), n = alarmfähig mit Stufe ≠ nie (9). „A5“ ist Abgleich-Tag, nicht nachbauen.
- **#3012 „(Orange)“:** MetrikZeile.svelte:38 setzt `wetter.farbe.*` (klein) in den Erklärsatz; vorhandene Schlüssel `alarme.alarm_ab.stufe.{never,yellow,orange,red}` = „Nie/Gelb/Orange/Rot“ (schon in MetrikZeile.svelte:44–48 genutzt). `wetter.farbe.*` bleibt klein (aria in AmpelLeiste/GrenzenEditor).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/app/metric_catalog.py | MODIFY | `is_precursor=True` für wind_chill, cloud_total, dewpoint, pressure; `_REITER_WETTER` auf Mockup-Reihenfolge (thunder vor rain_probability, Himmel-Block visibility/cloud_low/uv_index …); Rang-Feld in `reiter_wetter_eigenschaften()`; label_de temperature_night „Tiefsttemperatur Nacht“, wind_chill_night „Gefühlte Tiefsttemperatur Nacht“, humidity „Luftfeuchte“ (EN unverändert) |
| api/routers/config.py | MODIFY (ggf.) | neues Feld `rang` reicht über `**reiter_wetter_eigenschaften(m)` durch – prüfen |
| frontend/src/lib/components/shared/wetter-tab/ampelModell.ts | MODIFY | `MetrikEigenschaften.rang`; `zeilenGruppen()` stabil nach rang sortieren; `gewitterSatz()` Token `mittel_ab` wenn mittel greift; `alarmZaehler()` m = auswahl.length (Platzhalter ggf. umbenennen/kommentieren) |
| frontend/src/lib/components/organisms/wetter-tab/MetrikZeile.svelte | MODIFY | Stufenwort im Erklärsatz über `alarme.alarm_ab.stufe.*` |
| frontend/src/lib/i18n/messages/{de,en}/wetter.json | MODIFY | `wetter.gewitter.mittel_ab` („mittel oder hoch“ / „medium or high“) |
| frontend/src/lib/i18n/messages/de/{wertebereiche,alarme,vergleich,mail}.json | MODIFY | Namens-Kopien angleichen (Z.84/90, alarme:76, vergleich:64 „Luftfeuchte Ø“, mail:138) |
| tests/tdd/test_metrik_katalog_reiter_wetter_felder.py | MODIFY | Vorbote-Flags, Rang |
| frontend …/__tests__/ampelModell.test.ts, fix2913_metrikliste_mockup.test.ts, wetter_tab_bausteine.test.ts, deutsch_unveraendert.test.ts, nicht_im_briefing_kontextkatalog.test.ts, wertebereiche_sprache.test.ts | MODIFY | Erwartungen Zähler, Gewitter-Satz, Reihenfolge, Stufenwort |
| tests/unit/test_mail_metric_name_forms.py, test_metric_catalog_englische_namen.py, test_compare_metric_catalog_endpoint.py u. a. | MODIFY | neuer Name |
| tests/golden/** (vergleichs_mail, f5_wertebereiche, f7_alarme_tab, scheduler_texte, inbound/hilfe_trip), tests/fixtures/einstellung_gleich_mail/** | MODIFY | Golden-Neuerzeugung Namen |

### Scope Assessment
- Quelldateien: ~10–12, Estimated LoC: +60/-30 ohne Goldens; Namen-Teil zusätzlich ~20–30 Test-/Golden-Dateien (Textersatz, Neuerzeugung)
- Risk Level: MEDIUM (Namen wirken auf Mail-Texte + Goldens; Reihenfolge-Sortierung wirkt auf alle Gruppen und „Nicht im Briefing“). Vorbote, Zähler, Stufenwort, Gewitter-Satz: LOW.

### Technical Approach (Entscheidungen Tech Lead)
1. Vorbote: Katalogflag für alle ADR-0010-Vorboten nachziehen (kein reiter-eigenes Flag, eine Quelle). cloud_low bleibt KEIN Vorbote (Mockup „Gipfel in Wolken“, „kein Alarm“).
2. Gewitter-Satz: nur wenn die Stufe *mittel* die Alarmstufe erreicht → „mittel oder hoch“; greift erst *hoch* → weiter „hoch“.
3. Reihenfolge: Python bleibt einzige Quelle — Reihenfolge von `_REITER_WETTER` = Mockup-Reihenfolge, als Rang über /api/metrics; `zeilenGruppen()` (und damit `briefingAngebot()` über dieselbe Ordnung prüfen) sortiert stabil. `_METRICS` und `ampel_templates` unberührt ⇒ Mail/SMS-Spalten unverändert. Keine Frontend-Rangtabelle (Wissen verdoppeln, verstößt gegen AC-27 #2794).
4. Namen: Katalog `label_de` ändern ⇒ ein Name in Reiter und allen Kanälen (Mockup zeigt ihn in den Kanal-Inhalt-Blöcken). Eigener Commit inkl. Golden-Neuerzeugung; Renderer-Commit-Gate (Modus-Matrix + Mail-Validator) beachten. EN-Namen, Kürzel, sms_code unverändert. Alarm-Kurzlabel `alert_label` („Feuchte“) unverändert.
5. Zähler: m = alle ausgewählten Metriken, k = nicht alarmfähige, n = alarmfähige mit Stufe ≠ nie.
6. „(Orange)“: vorhandene Schlüssel `alarme.alarm_ab.stufe.*` wiederverwenden.
Reihenfolge der Umsetzung: 1 → 5/6/2 (Frontend) → 3 → 4 (separat, Goldens).

### Dependencies
- Downstream `is_precursor`: from_display_config, Change-Map, reiter_wetter_eigenschaften (alle ohne Verhaltensänderung außer Reiter-Text).
- Downstream `label_de`: Vergleichs-Mail-Zeilenköpfe, metric_format.label(), Alarme-Seite, Wertebereiche, Inbound-Hilfe.
- E2E-Specs s3a2794-teil3-*.spec.ts lesen is_precursor dynamisch; Reihenfolge-Spec s3a2794-teil3-zeilen prüfen.

### Open Questions (technisch, in Spec/RED klären – keine PO-Frage)
- [ ] Kann der Nutzer die Zeilen-Reihenfolge im Reiter selbst ändern? Falls ja, darf der Rang-Sortierer sie nicht überschreiben.
- [ ] Gewitter-Satz EN: „medium or high“ – Elementliste text_en prüfen.
- [ ] Trip-Staging-Daten: Abgleich mit Vorlage „Alpen-Trekking“/„Allgemein“ (Zähler 9/13/3 nur mit Mockup-Daten).

## TDD RED (Phase 5, 16.11.2026) — Hinweise für /50-implement
- Tests: `tests/tdd/test_2955_wetter_metrik_inhalte.py` (Python, 15 rot / 13 Regressionsschutz grün) und
  `frontend/src/lib/components/shared/wetter-tab/__tests__/fix2955_metrik_inhalte.test.ts` (28 rot / 4 grün).
- **Luftdruck (pressure) ist heute `display_only=True`** und rendert „Nur Anzeige …“. AC-1 verlangt für ihn die
  drei Vorbote-Texte; der RED-Test prüft das. Umsetzung: Vorbote hat Vorrang vor reiner Anzeige im Untertitel,
  Erklärsatz und rechten Label (oder pressure als Vorbote ohne Anzeige-Flag) — Entscheidung im GREEN.
- Gewitter EN: Spec verlangt „medium or high“ (der Skala-Tick EN bleibt „moderate“).
- Kopfzähler: Test füllt den Katalogtext mit `werte`; Platzhaltername frei, Text muss „9 von 13 …“ ergeben.
- Mail-Name: `derive_row_labels(form="long")` ohne Aggregation (Nacht-Metriken haben keine summary_fields).
