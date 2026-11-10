---
entity_id: feat_2794_s3a_teil3_wetter
type: module
created: 2026-11-10
updated: 2026-11-10
status: draft
version: "1.0"
tags: [hub, reiter, wetter, ampel, vorlagen, alarm-ab, alarmquelle, amtliche-warnungen, i18n, epic-2791]
---

# Einstellungen neu S3a, Teil-PR 3: Reiter „Wetter“ (#2794)

## Approval

- [ ] Approved

## Purpose

Teil-PR 3 der freigegebenen Gesamt-Spec `feat_2794_s3a_reiter_wetter.md` (Epic #2791, Issue #2794). Der Reiter **Wetter** in Hub und Anlege-Kette von Trip und Orts-Briefing bekommt seinen neuen Inhalt nach Mockup Fassung 3: Vorlage-Karte, „Alarm ab für alle“, Metrik-Zeilen mit Ampel-Leiste und „Grenzen ändern“, „Nicht im Briefing“, Karte Amtliche Warnungen & Radar und die Karte Anpassen (Tagesfenster). Der Dialog „Als eigene Vorlage speichern“ wird auf die Ampel umgestellt. Trip und Orts-Briefing nutzen denselben Code (`context="route"|"vergleich"`).

Zusätzlich schließt diese Lieferung zwei Lücken, die die Analyse gefunden hat: (1) Die Auswahl der Metriken wirkt heute nicht über die Ampel, sondern über `display_config.metrics[]` (Trip) bzw. `active_metrics` (Vergleich); der Reiter muss beide Quellen konsistent halten (AC-37). (2) Das Alarmquellen-Gate in `trip_alert.py` erkennt `alarm_ab` nicht; ohne Korrektur stellt die Oberfläche Alarme ein, die nie kommen (AC-29).

Diese Spec übernimmt AC-9 bis AC-21, AC-28 (Frontend-Spiegel), AC-29 und AC-30 der Gesamt-Spec, präzisiert sie für diese Lieferung und ergänzt AC-37 bis AC-42. Die Nummern AC-31 bis AC-35 bleiben der Gesamt-Spec (Teil-PR 4) vorbehalten, daher beginnen die neuen Kriterien bei AC-37 (nach AC-36 der Gesamt-Spec).

Grundlagen: Gesamt-Spec (§4 Reiter Wetter, §5 Dialog, §6 Backend, Lieferplan), Teil-Spec `feat_2794_s3a_teil2_leiste.md`, Analyse `docs/context/feature-2794-s3a-teil3-wetter.md` und `docs/context/feature-2794-s3a-reiter-wetter.md`, Konzept `docs/context/einstellungen_neu.md` §4 bis §8, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`, ADR-0109 (Reiterstruktur), ADR-0106 (Ampel als einzige Bewertung, Gewitter ohne Gelb), ADR-0111 (Design), ADR-0035 (Tagesfenster), ADR-0104 (zweisprachig), ADR-0101 (Read-Modify-Write).

PO-Entscheidungen 2026-11-08 (P1 bis P3 und Abgleich W1, W4, W5b, A3, A5, A6, K17) gelten unverändert; Texte in Anführungszeichen sind PO-freigegeben und werden wörtlich über den Katalog umgesetzt.

## Source

- **Frontend (produktive Oberfläche):** `frontend/src/lib/components/shared/wetter-tab/` (neu), `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-detail/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte`, `shared/WetterMetrikenVersandPanel.svelte`, `shared/WeatherMetricsTab.svelte`, `shared/weather-metrics-tab/{SavePresetDialog,DayWindowCard,weatherMetricsCompareSave}.*`, `frontend/src/lib/types.ts`, `frontend/src/lib/i18n/messages/{de,en}/wetter.json` (neu).
- **Go-API (nur Tests, keine Produktivänderung erwartet):** `internal/handler/weather_config.go`, `internal/handler/compare_preset.go`, `internal/handler/ampel.go`, `internal/model/trip.go` (`mergeConfigMap`).
- **Python-Core:** `src/services/trip_alert.py` (beide Gate-Blöcke), `src/services/compare_alert.py` (nur Test), `src/app/ampel.py` (Referenz), `src/app/metric_catalog.py` (Referenz).
- **Doku/Betrieb:** `docs/reference/i18n_glossar.md`, `docs/reference/operations_playbook.md` (Runbook „Vorlagen-Zeithorizonte entfernen“), `scripts/migrate_2794_preset_horizons.py` (existiert, Lauf beim Deploy).

> **Schicht-Hinweis:** Der Reiter, seine Bausteine, der Dialog und die Speicher-Payloads sind Frontend (SvelteKit). Die Speichergrenze (Ampel-Validierung, Merge) ist Go und bleibt unverändert; Go bekommt in dieser Lieferung nur Tests. Das Alarmquellen-Gate ist Python (`src/services/trip_alert.py`). Katalog und Vorlagen-API liefern die Daten (Teil-PR 1, live) und werden nicht neu kopiert.
>
> **Trip/Ortsvergleich-Teilung (PFLICHT, #1170, Epic #2345):** `WetterTab` und alle Bausteine (`VorlageKarte`, `AlarmAbKopf`, `MetrikZeile`, `AmpelLeiste`, `GrenzenEditor`, `NichtImBriefing`, `WarnungenRadarKarte`, `AnpassenKarte`) liegen unter `shared/wetter-tab/` mit `context="route"|"vergleich"`. Es entsteht keine Compare-Komponente mit Trip-Pendant. Unterschiede zwischen den Kontexten sind nur Daten- und Speicherweg (Abschnitt „Datenfluss“), die Radar-Zeile (nur Vergleich) und die Vorlagen-Art (`kind`).
>
> **Mandantentrennung:** Der Reiter bewegt Nutzerdaten (Abo-Speichern, eigene Vorlagen). `user_id` kommt aus dem Auth-Kontext, nie `"default"`. AC-30 und die Vorlagen-Wege werden mit zwei verschiedenen Nutzern getestet.
>
> **Kanäle:** Der Reiter bestimmt Metrik-Auswahl, Ampel und „Alarm ab“ und wirkt damit in allen vier Kanälen (E-Mail · Telegram · SMS · Premium-SMS) gleich; der Alarm erreicht über das Gate (AC-29) alle vier. Der Mail-Inhalt ändert sich in S3a nicht (nur Auswahl und Auslöser); Renderer-Gate und Mail-Validatoren werden nicht berührt.

## Estimated Scope

- **LoC:** Frontend ca. +2500 bis 3500 (inkl. Tests), Python ca. +150, Go-Tests ca. +200. LoC-Override begründet wie bei Teil-PR 1: zentrale Einstellfläche beider Kontexte, Neubau von ca. neun Bausteinen mit Modell-Schicht und Tests; Löschung der Altkomponenten erst Teil-PR 4, daher kein Gegenposten.
- **Files:** ca. 25 bis 30 (davon ca. 15 neu)
- **Effort:** high (Risiko HIGH: zwei Speicherwege, Mount-Regressionen aus Teil 2, Auswahl-Mechanismus, Alarm-Gate)

**Lieferung:** ein Workflow, eine Teil-Spec, ein PR, intern zwei Stufen, jede lauffähig und mit grüner Kern-Schicht:

- **Stufe 3.1 (ohne Oberfläche):** Modell-Schicht (`ampelModell.ts`, `ampelSchreiben.ts`, `amtlicheWarnungen.ts`), Ampel-Typen in `types.ts`, Alarmquellen-Gate (AC-29), Go-Tests (AC-20 Roundtrip, AC-30), Glossar und Katalog-Schlüssel. Kern-Tests: AC-17 (Regeln), AC-28, AC-37 (Parität), AC-29, AC-30.
- **Stufe 3.2 (Oberfläche):** `WetterTab` und Bausteine, Umstellung der vier Mount-Stellen, Dialog, `DayWindowCard`, Nachziehen der AST-Wächter, Playwright-E2E.

Die Benennung „3.1/3.2“ (nicht 3a/3b) vermeidet die Kollision mit S3b (#2795).

## Scope

### In Scope

- Reiter Wetter vollständig (Gesamt-Spec §4), für Hub und Anlege-Kette, Trip und Orts-Briefing.
- Auswahl-Mechanismus und Vorlagen-Fallback (AC-37, AC-39), Speicher-Einzigkeit (AC-38).
- Dialog „Als eigene Vorlage speichern“ (W5b, AC-42), `DayWindowCard` mit Select-Atom.
- Alarmquellen-Gate (AC-29), Lese-Regel Amtliche Warnungen (AC-20), Mandanten- und Schreibsicherheit (AC-30).
- Katalog DE/EN, Glossar zuerst (AC-41), Design-Audit-Befunde (AC-40).
- Nachziehen der AST-Wächter auf den neuen Wetter-Träger.

### Out of Scope

- **Teil-PR 4:** Löschung von `CorridorEditor`/`CorridorEditorMobile`, `AlarmeTab`, Alt-Wetterzweig in `WeatherMetricsTab`, `HorizonChips`, `MetricCheckbox`; Übersicht U3/U4; Listen-Sprünge K17; Hilfe-Texte X1; Bereinigung veralteter Glossar-Einträge. Bis dahin bleibt der Alt-Code ungenutzt im Reiter Wetter erhalten, wird aber dort nicht mehr gemountet.
- **Orts-Standardvorlage beim Anlegen** (Gesamt-Spec Known Limitations: Standard übernimmt nur die `ampel`, nicht `active_metrics`): Das Ableiten von `active_metrics` aus Vorlagen-`enabled` beim Anlegen gehört zur Anlege-Kette (Teil-PR 4). Die Gesamt-Spec ordnet es nicht ausdrücklich Teil 3 zu, verlangt nur den Abgleich mit AC-13. Dieser Abgleich geschieht über den Lese-Fallback (AC-39): Der Reiter leitet die Auswahl eines Orts-Briefings ohne `active_metrics` aus der aufgelösten Ampel ab, sodass ein neu angelegtes Briefing mit Standardvorlage korrekt dargestellt wird.
- **S3b (#2795):** Inhalt je Kanal und Fläche, Roh/Einfach, Kanal-Tabelle.
- **S8 (#2800):** Radar-Schalter für Trips (im Trip erscheint die Zeile nicht).
- Neue Grenzwerte oder Vorlagen; Ampel für Nullgradgrenze, Schneefallgrenze, Schneehöhe, Nacht (S7).
- Umstellung von Renderer, Resolver und Alarm-Engine auf `resolve_ampel` als Auswahlquelle (verworfen, siehe Implementation Details).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Teil-PR 1 (#2870, live) | Vorarbeit | `/api/metrics` mit `group`, `alertable`, `is_precursor`, `allowed_sides`, `display_only`; `/api/templates` mit `ampel`; eigene Vorlagen mit `kind`, `ampel`, Duplikatprüfung (409 `name_exists`), Standard je Art; Migration `scripts/migrate_2794_preset_horizons.py` |
| Teil-PR 2 (#2892, live) | Vorarbeit | Reiterkennung `wetter`, Umleitungen, Anlege-Ketten, `WeatherMetricsTab` mit `bereich` |
| S2b (PR #2862, gemergt 2026-11-09) | Vorarbeit | Alarm nach Ampel (`alarm_ab`), Katalog `alarm.ampel.*`, Altstufen-Migration |
| `src/app/ampel.py`, `src/app/ampel_templates.py` | Code | Referenz für Auflösung (`_verschmelzen`, `resolve_ampel`) und Zähler (`deviation_count`) |
| `tests/fixtures/ampel_deviation_cases.json` | Testdaten | gemeinsame Fixture für pytest und `node --test` |
| `alerts-tab/alarmAbAnzeige.ts` | Code | Typ `AlarmAb`, `alarmAbZeile`, `ladeVorlagenAmpeln`, `STANDARD_VORLAGE` (wiederverwendet) |
| `ui/select/Select.svelte`, `ui/segmented/Segmented.svelte`, `molecules/DatumFeld`, `UhrzeitFeld`, `Dot` | Code | Ersatz nativer Controls (ADR-0111) |
| `DayWindowCard.svelte`, `versand-tab/dayWindowClamp.ts` | Code | Tagesfenster (ADR-0035), Clamp unverändert |
| `enqueueHubWrite` (Hub-Schreibschlange), `saveController` | Code | Speicherwege (Vergleich mit ETag, Trip) |
| `docs/reference/i18n_glossar.md`, `i18n_konventionen.md` | Doku | Glossar zuerst, Katalog-Regeln |
| Teil-PR 4, S3b #2795, S8 #2800 | Folgearbeit | Löschung Altkomponenten, Inhalt je Kanal, Radar Trip |

## Affected Files

(Pfade ohne Präfix liegen unter `frontend/src/lib/components/`.)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` (Gate-Blöcke bei :684-709 und :1190-1218) | MODIFY | gemeinsamer Helfer „Ampel-Alarmquelle aktiv“ in beiden Blöcken (AC-29) |
| `tests/tdd/test_2794_teil3_alarmquelle.py` | CREATE | Trip- und Vergleichs-Einstieg mit/ohne `alarm_ab`, Versand beobachtet (AC-29) |
| `tests/tdd/test_2794_teil3_auswahl_paritaet.py` | CREATE | über 7 Vorlagen: Ableitung aus `ampel` gleich `resolve_ampel` (AC-37, Python-Seite der Parität über gemeinsame Fixture) |
| `shared/wetter-tab/ampelModell.ts` | CREATE | Ampel-Typen, Auflösung (Spiegel `_verschmelzen`), Abweichungszähler (AC-28), Reihenfolge-Regeln (AC-17), Gewitter-Regeln (AC-18), Erklärsatz-Modell, Auswahl-Ableitung (AC-37, AC-39) |
| `shared/wetter-tab/ampelSchreiben.ts` | CREATE | Speicher-Payload: minimale `ampel`-Abweichungsmenge plus vollständige `metrics[]`/`active_metrics` |
| `shared/wetter-tab/amtlicheWarnungen.ts` | CREATE | ODER-Lese-Regel und Doppelschreiben (AC-20) |
| `shared/wetter-tab/__tests__/*.test.ts` | CREATE | `node --test`: Zähler gegen `ampel_deviation_cases.json`, Reihenfolge, ODER-Regel, Auswahl-Ableitung, Payload |
| `shared/wetter-tab/WetterTab.svelte` | CREATE | Reiter mit `context`, genau ein Speicherer (AC-9 bis AC-21, AC-38) |
| `shared/wetter-tab/VorlageKarte.svelte`, `AlarmAbKopf.svelte`, `MetrikZeile.svelte`, `AmpelLeiste.svelte`, `GrenzenEditor.svelte`, `NichtImBriefing.svelte`, `WarnungenRadarKarte.svelte`, `AnpassenKarte.svelte` | CREATE | Bausteine nach Mockup Fassung 3 |
| `shared/weather-metrics-tab/SavePresetDialog.svelte` | MODIFY | + `ampel`, + `kind`, Texte, ohne Zeithorizonte/Zusammenfassung (AC-42) |
| `shared/weather-metrics-tab/DayWindowCard.svelte` | MODIFY | `<select>` durch `ui/select/Select.svelte`, Clamp unverändert |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | Vergleich-Speichern um `ampel`, `active_metrics`, Warn-Felder, `radar_alert_enabled` erweitern, oder neuer Speicherer nutzt `enqueueHubWrite` direkt (siehe Datenfluss) |
| `trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte`, `trip-detail/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | MODIFY | Reiter `wetter` auf `WetterTab`; `WeatherMetricsTab` nur noch `bereich="zustellung"`; Hydrations-Bedingung `wetterMetrikenLayoutHydrationBereit` im Vergleich erhalten |
| `shared/WetterMetrikenVersandPanel.svelte` | MODIFY | Reiter-Wetter-Pfad entfällt (nur noch Zustellung) |
| `frontend/src/lib/types.ts` (:368-369) | MODIFY | typisiertes `ampel`-Feld statt `Record<string, unknown>` |
| `frontend/src/lib/i18n/messages/de/wetter.json`, `.../en/wetter.json` | CREATE | alle Texte des Reiters und des Dialogs |
| `docs/reference/i18n_glossar.md` | MODIFY | Wetter (Reiter), Vorlage, Ampel, Grenzen ändern, Nicht im Briefing (Glossar zuerst) |
| `internal/handler/weather_config_test.go`, `compare_preset_test.go` | CREATE/MODIFY | AC-30 zwei Nutzer, Feld-Erhalt; AC-20 Roundtrip beider Speicherwege |
| `shared/__tests__/s3a2794_eine_wmt_instanz.test.ts`, `s3a2794_speicher_owner_waechter.test.ts`, `s3a2794_zustellung_vergleich_ein_speicherer.test.ts`, `s3a2794_hub_zustellung_verdrahtung.test.ts`, `weather-metrics-tab/__tests__/s3a2794_bereich_filter.test.ts`, `tests/tdd/test_issue_934_wizard_schedule.py` | MODIFY | Wächter auf den neuen Träger nachziehen, nicht aufweichen |
| `frontend/e2e/s3a2794-teil3-*.spec.ts` | CREATE | Playwright je AC, gleicher Test-Code für `route` und `vergleich` |
| `docs/reference/operations_playbook.md` | MODIFY | Deploy-Hinweis Migration `horizons` für Teil 3 (Runbook besteht) |

## Datenfluss und Speicherwege

**Lesen (beide Kontexte):** Katalog `/api/metrics` (Gruppe, Alarmfähigkeit, erlaubte Seiten), Vorlagen `/api/templates` (je Vorlage `ampel`), eigene Vorlagen `/api/metric-presets` (gefiltert nach `kind`), Abo-Daten aus der Hub-Hydration.

| | Trip (`route`) | Orts-Briefing (`vergleich`) |
|---|---|---|
| Auswahl lesen | `display_config.metrics[]` (`enabled`) | `display_config.active_metrics`; fehlt der Schlüssel, aus der aufgelösten Ampel (AC-39) |
| Ampel lesen | `display_config.ampel` (nur Abweichungen), aufgelöst gegen die Vorlage | wie Trip |
| Warnungen lesen | ODER-Regel (AC-20) | ODER-Regel, zusätzlich `radar_alert_enabled` |
| Tagesfenster | `report_config.day_window_*_hour` | top-level `day_window_*_hour` |
| Speichern | ein Speichervorgang des Reiters aus zwei disjunkten PUTs wie heute (`tripSpeicherung.ts`): `PUT /api/trips/{id}/weather-config` mit `display_config`-Feldern (`ampel`, `metrics`), danach `PUT /api/trips/{id}` mit den Trip-Feldern `official_alerts_enabled`, `official_warnings` (top-level) und `report_config.day_window_*_hour`; kein PUT wiederholt den Inhalt des anderen (Phase 5: `/weather-config` mergt nur in `display_config`, Warn-Felder und Tagesfenster gingen dort verloren) | `enqueueHubWrite` mit ETag (`UpdateComparePresetHandler`), `ampel` immer als vollständige Abweichungsmenge, `active_metrics`, Warn-Felder, `radar_alert_enabled`, Tagesfenster |
| Serverseitig | `PutTripWeatherConfigHandler`: Ampel-Prüfung, `mergeConfigMap` (flach, `ampel` als Ganzes ersetzt, fremde `display_config`-Schlüssel bleiben) | `applyComparePresetPatch`, Ampel-Prüfung |
| Konflikt | nicht anwendbar (kein ETag) | bei ETag-Konflikt Abo neu laden, Eingaben nicht still überschreiben |

**Genau ein Speicherer je Reiter** (Lehre aus Teil 2, doppelter PUT durch zwei gemountete Instanzen): `WetterTab` ist der einzige Schreiber der Felder des Reiters Wetter. `WeatherMetricsTab` bleibt nur mit `bereich="zustellung"` im Reiter Zustellung und schreibt dort ausschließlich Zustellungs-Felder. Die Felder beider Reiter sind disjunkt; die AST-Wächter prüfen das.

## Implementation Details

### 1. Modell-Schicht (Stufe 3.1)

- **`ampelModell.ts`:** Typen für `Ampel` (`template`, `metrics.<id>` mit `enabled`, `alarm_ab`, `lower{red,orange,yellow}`, `upper{yellow,orange,red}`, `thunder{mittel,hoch}`). Auflösung Vorlage → Abo als Spiegel von `_verschmelzen` (`src/app/ampel.py:159`). Abweichungszähler als Spiegel von `deviation_count` (`ampel.py:245`): eine Abweichung je betroffener Metrik und Änderungsart (`enabled`, `alarm_ab`, Grenze, Metrik hinzugefügt/entfernt, Gewitterfarbe); Rückkehr auf den Vorlagenwert zählt nicht. Reihenfolge-Regeln: unten rot < orange < gelb, oben gelb < orange < rot, unten nicht über oben. Gewitter-Regeln (mittel: gelb · orange · rot; hoch: orange · rot; „keins“ immer grün; kein „Alarm ab Gelb“). Erklärsatz-Modell liefert nur Katalogschlüssel und Platzhalter, keine Texte. Eigenschaften der Metriken (Gruppe, alarmfähig, Vorbote, erlaubte Seiten, nur Anzeige) kommen aus `/api/metrics`, nie aus einer Frontend-Kopie.
- **`ampelSchreiben.ts`:** erzeugt aus dem Bearbeitungsstand die Payload: `ampel` als vollständige Abweichungsmenge gegen die gewählte Vorlage, `metrics[]` bzw. `active_metrics` als vollständige Liste (Reihenfolge = bestehende Liste, neu hinzugefügte Metriken hängen hinten an), dazu `ampel.metrics.<id>.enabled` als minimale Abweichung von der Vorlage.
- **`amtlicheWarnungen.ts`:** Lese-Regel: ist `official_warnings` vorhanden, gilt `official_warnings.enabled || official_alerts_enabled`; sonst `official_alert_triggers_enabled` (Default an). Schreib-Regel: setzt `official_alerts_enabled` und `official_warnings.enabled` auf denselben Wert. Renderer und Alarm-Engine bleiben unverändert.

### 2. Auswahl-Mechanismus (AC-37)

Entscheidung (Tech Lead): **Das Frontend hält beide Quellen konsistent.** Der Reiter liest die Auswahl aus `metrics[]` (Trip) bzw. `active_metrics` (Vergleich), sodass Bestandsabos korrekt bleiben. Beim Speichern schreibt er `metrics[]`/`active_metrics` vollständig und zusätzlich `ampel.metrics.<id>.enabled` als minimale Abweichung von der Vorlage. Vorlagenwechsel und Zurücksetzen setzen die Auswahl aus den Vorlagen-`enabled`-Werten und leeren die Abweichungen.

**Verworfene Alternativen:**
- **(ii) Renderer/Resolver auf `resolve_ampel` umstellen:** würde vier Kanäle, den Compare-Resolver (`report_config_resolver.py`, `compare_metric_ids.py`) und `SyncAlertRules` ändern; der Mail-Inhalt soll sich in S3a nicht ändern; die Reihenfolge der Metriken gehört nicht in die Ampel.
- **(iii) Go leitet beim Schreiben ab:** doppeltes Katalogwissen in Go, zwei Handler (Trip und Vergleich) müssten es getrennt umsetzen.

**Absicherung:** Test über alle 7 Systemvorlagen, dass die Frontend-Ableitung (aus Vorlagen-`ampel`) und Python `resolve_ampel` dieselbe Menge aktiver Metriken liefern. Der Mail-Inhalt ändert sich in S3a nicht, weil Renderer und Resolver weiter dieselben Quellen lesen wie vorher.

### 3. Alarmquellen-Gate (AC-29)

In `src/services/trip_alert.py` wird ein gemeinsamer Helfer „Ampel-Alarmquelle aktiv“ eingeführt: wahr, wenn in der effektiven Auswahl mindestens eine aktive Metrik mit `alarm_ab` ≠ `never` steht (aufgelöst über `resolve_ampel`). **Präzisierung (Phase 5, Tech Lead):** Der Helfer greift nur, wenn das Abo den Schlüssel `display_config.ampel` trägt (Ampel-Welt; der Reiter Wetter schreibt ihn bei jedem Speichern, mindestens `template`). Dann zählt die aufgelöste Ampel einschließlich der Vorlagen-Vorgaben, so wie der Reiter sie anzeigt (S2b: Abos ohne Altstufen bekommen `alarm_ab` aus der Vorlage). Abos ohne `ampel`-Schlüssel bleiben im Gate exakt wie bisher, sonst würde jeder Bestandstrip über die Vorlage alarmfähig. „Aktiv“ heißt: aktiv in derselben Quelle, aus der die Alarm-Engine die zu prüfenden Metriken nimmt (Developer weist die Stelle nach); der Reiter hält `metrics[]` und `ampel.metrics.<id>.enabled` ohnehin gleich (AC-37). Beide Gate-Blöcke (`has_active_rules` bei :684-709 und :1190-1218) rufen ihn auf; bestehende Gate-Fälle (Preset, Altstufen, Regeln, Wetteränderungs-Alarme) bleiben unverändert. `compare_alert.py` braucht keine Code-Änderung (kein entsprechendes Gate, Fallback auf Standardstufen, `ampel=resolve_ampel(preset)`); ein Test sichert dieses Verhalten mit und ohne `alarm_ab` ab und prüft, dass `_display_config_from_active_metrics` Ampel-Metriken nicht wegfiltert. Die Tests laufen aus Nutzersicht (Versand beobachtet), ohne `Mock()`/`patch()`.

### 4. Oberfläche (Stufe 3.2)

Aufbau von oben nach unten laut Gesamt-Spec §4 und Mockup Fassung 3: Kopf mit Lade- und Fehlerzustand (W1), Vorlage-Karte mit Picker und Rückfrage (W4), „Alarm ab für alle“ mit Zähler (A3, A5), Metrik-Zeilen in fünf Gruppen mit Ampel-Leiste, Erklärsatz, „grün: …“-Zeile, „Alarm ab“ und „Grenzen ändern“, „Nicht im Briefing“, Karte Amtliche Warnungen & Radar, eingeklappte Karte Anpassen. Keine CAPE-Zeile (A6), keine Aggregationswahl, kein Roh/Einfach in den Zeilen (S3b).

Design (ADR-0111, Design-Audit #2794 vom 2026-11-09): keine nativen Controls (`<select>` in `DayWindowCard` wird `ui/select/Select.svelte`, Segmente über `ui/segmented/Segmented.svelte`, Datum/Uhrzeit über `DatumFeld`/`UhrzeitFeld`, Häkchen in `WeatherV2Grundauswahl` entfallen mit dem Neubau), Kontrast mindestens 4,5:1 (WCAG-AA), Touch-Ziele mindestens 44 px, gleicher Panel-Rahmen in Trip und Vergleich.

Mount-Stellen (Teil-2-Lehre F012): `TripTabs.svelte` mountet `WetterTab` im Reiter `wetter` per if-Kette; `CompareTabs.svelte` nur nach der bestehenden Bedingung `wetterMetrikenLayoutHydrationBereit`; die beiden Anlege-Editoren mounten `WetterTab` im Schritt `wetter`. Nie zwei Instanzen derselben Speicher-Zuständigkeit zugleich.

### 5. Dialog „Als eigene Vorlage speichern“ (W5b)

Auf Basis von `SavePresetDialog.svelte`: zusätzlich `ampel` (die aufgelöste Abo-Ampel des Abos) und `kind` (`route` im Trip, `vergleich` im Orts-Briefing) im POST `/api/metric-presets`; ohne Zeithorizonte und ohne Zusammenfassung. Die Duplikatprüfung läuft serverseitig (409 `name_exists`, bereits live) und wird im Dialog angezeigt. Texte laut Gesamt-Spec §5.

### 6. Offene technische Punkte (entschieden)

- **(a) Eigene Bestandsvorlagen ohne `ampel`:** Fallback ist die Ampel der Standardvorlage `allgemein`, wobei `enabled` aus den Metriken der Vorlage gesetzt wird (Metrik in der Vorlage aktiv = `enabled` an). Der Abweichungszähler zählt gegen diese abgeleitete Ampel (AC-39).
- **(b) Orts-Standardvorlage beim Anlegen:** siehe Out of Scope; Abgleich über den Lese-Fallback (AC-39), Ableitung beim Anlegen gehört zu Teil-PR 4.
- **(c) Altstufen-Migration (`alarm_ab_migration`):** Ob Bestandsabos schon alarmfähig migriert sind, betrifft nur die Dringlichkeit, nicht die Korrektheit; AC-29 gilt unabhängig davon (Known Limitations).

- **(d) Trip-Anlege-Kette, Vorbelegung der Wertebereiche (Phase 5):** Der `CorridorEditor` verschwindet im Schritt wetter aus der Sicht; bleibt er als unsichtbare Datenquelle für `corridors` im Anlege-POST nötig (Teil-2-Wächter AC-2.T4, F005, `defaultsBereit`/`wertebereicheVorbelegt`), wird er unsichtbar weiter gemountet, bis Teil-PR 4 die Anlege-Kette umbaut. Die Vorbelegung darf nicht verloren gehen.
- **(e) SMS-Schwellen (#624, Phase 5):** Der Abschnitt gehört zum Kanal-Inhalt (S3b) und wandert vom Bereich `wetter` in den Bereich `zustellung` von `WeatherMetricsTab`; er darf nicht unerreichbar werden. Feld-Eigentum: `display_config.metrics[]` gehört dem `WetterTab` (Auswahl `enabled`, Reihenfolge); er erhält beim Schreiben alle übrigen Eintragsfelder (u. a. `sms_threshold`, `use_friendly_format`) unverändert. Der Zustellungs-Abschnitt ändert je Eintrag nur `sms_threshold` auf frisch geladenem Stand (Read-Modify-Write), nie `enabled`/Reihenfolge/`ampel`.
- **(f) Wächter-Nachzug (Phase 5, Liste aus dem RED-Lauf):** zwingend anzupassen sind `s3a2794_eine_wmt_instanz` (Reiter wetter = `WetterTab`, WMT nur `zustellung`), `s3a2794_trip_hub_wetter_wertebereiche` (F013, kein `CorridorEditor` im Reiter wetter), `s3a2794_flush_hydration_kette` (Hydration auf `WetterTab` umstellen), `s3a2794_speicher_owner_waechter` (neuer `STELLEN`-Eintrag für `WetterTab`), ggf. `s3a2794_bereich_filter` (SMS-Schwellen, Punkt e), `i18n/__tests__/paritaet_de_en.test.ts` (`'wetter'` in `BEREICHE`, beide `index.ts`); zu prüfen: `compare_mobile_shared_hub`, `compare_wetter_metriken_wertprops`, `compare_hub_idealwerte_hydration`, `wetter_metriken_versand_panel_paritaet`, `infobox_nur_beim_anlegen`, `anlegen_ohne_autosave`, `compare_new_editor_postet_einmal`, `trip_new_editor_weather_metrics_wiring`, `standardwerte_wartet_auf_wertebereiche_vorbelegung`, `tests/tdd/test_issue_934_wizard_schedule.py`. Nachziehen heißt: Zusicherung auf den neuen Träger übertragen, nicht aufweichen.
- **(g) Test-Vertrag aus Phase 5:** Die Modul-API von `ampelModell.ts`, `ampelSchreiben.ts`, `amtlicheWarnungen.ts` und der testid-Vertrag `WT` (`frontend/e2e/s3a2794-teil3.helpers.ts`) sind in den Testköpfen festgelegt. Erklärsätze: Der Python-Katalog `alarm.ampel.*` enthält nur Alarm-Meldungen und Farbwörter, keine Erklärsätze; der Abgleich aus AC-18 beschränkt sich auf gemeinsame Farbwörter/Stufennamen. In Phase 6 anzulegen: `frontend/playwright.2794-s3a3.staging.config.ts` analog `playwright.2794-s3a2.staging.config.ts` (`testMatch /s3a2794-teil3-[a-z-]+\.spec\.ts/`).

### 7. Deploy

Migration `scripts/migrate_2794_preset_horizons.py` mit Probelauf (ohne `--execute`) und Pre-Snapshot je Nutzer, bei gestoppter `gregor-api` bzw. `gregor-api-staging` (Runbook „Vorlagen-Zeithorizonte entfernen“ in `docs/reference/operations_playbook.md`: stoppen, migrieren, starten). Sie läuft auf Staging und Produktion, bevor der neue Dialog (ohne Zeithorizonte) verfügbar ist.

## Expected Behavior

- **Input:** Öffnen des Reiters Wetter in Hub oder Anlege-Kette (auch über alte Adressen aus Teil 2); Bedienung von Vorlage, „Alarm ab“, Grenzen, „Nicht im Briefing“, Warnungen, Radar (Vergleich), Tagesfenster; Speichern eigener Vorlagen.
- **Output:** Reiter Wetter nach Mockup Fassung 3 mit Ampel-Leisten und „Alarm ab“; gespeicherte `display_config.ampel` nur mit Abweichungen von der Vorlage; `metrics[]`/`active_metrics` und `ampel.metrics.<id>.enabled` konsistent; Alarme, die zu den eingestellten „Alarm ab“-Stufen passen.
- **Side effects:** beide Felder der Amtlichen Warnungen gleich gesetzt; eigene Vorlagen mit `ampel` und `kind`; Migration der Zeithorizonte beim Deploy. Renderer, Alarm-Engine (außer Gate) und Mail-Inhalt unverändert.

## Acceptance Criteria

Testschichten: **Kern** = ohne Netz (pytest, `go test`, `node --test`); **Live** = Playwright-E2E gegen Staging (`/e2e-verify`). Der Playwright-Code ist je AC derselbe für `route` und `vergleich` (Datei `frontend/e2e/s3a2794-teil3-*.spec.ts`), wenn der AC beide Kontexte nennt.

- **AC-9:** Given der Nutzer öffnet den Reiter Wetter in Trip oder Orts-Briefing / When die Metriken laden / Then steht oben die Überschrift „Wetter“ mit dem Erklärsatz „Was im Briefing steht, was für dich zu viel oder zu wenig ist und ab wann du einen Alarm bekommst.“, währenddessen „Lade Metriken …“ mit Platzhaltern; bricht der Katalog-Abruf ab, erscheint die Fehlermeldung „Die Metriken konnten nicht geladen werden. Die Verbindung zum Server ist abgebrochen. Deine Einstellungen sind gespeichert und gehen nicht verloren.“ mit dem Knopf „Erneut laden“, die gespeicherten Einstellungen bleiben unverändert, und ein Klick lädt neu
  - Test: Live, `s3a2794-teil3-laden.spec.ts`: Playwright mit blockierter Katalog-Anfrage (Netzwerk-Abbruch im Browser, keine Mock-Logik im Code), danach Freigabe und Neu-Laden; Abo-Datei vorher/nachher gleich.

- **AC-10:** Given ein Trip mit Vorlage „Alpen-Trekking“ / When der Nutzer den Vorlagen-Picker öffnet / Then sieht er die 7 Systemvorlagen mit Kurzbeschreibung (Metrikzahl und Stichworte aus den Vorlagen-Daten, z. B. „14 Metriken“ bei Alpen-Trekking) und darunter „Eigene“ (nur eigene Vorlagen der Art Trip), und der Picker zeigt „unverändert“ oder „{n} Abweichungen“
  - Test: Live, `s3a2794-teil3-vorlage.spec.ts`: Zahlen werden gegen `/api/templates` geprüft statt gegen feste Werte; zweiter Lauf im Kontext `vergleich` zeigt „Eigene“ nur mit Vorlagen der Art Orte.

- **AC-11:** Given ein Trip oder Orts-Briefing mit 3 Abweichungen von „Alpen-Trekking“ / When der Nutzer „Wandern“ wählt / Then fragt ein Dialog „‚Wandern‘ übernehmen? Ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen dieses {Trips|Orts-Briefings}. Deine 3 Abweichungen von ‚Alpen-Trekking‘ gehen verloren. Zustellung, Etappen und Orte bleiben unverändert.“ mit [Übernehmen] [Abbrechen]; „Abbrechen“ ändert nichts, „Übernehmen“ ersetzt Metrik-Auswahl, Ampel-Grenzen und Alarmstufen, und Zustellung, Etappen und Orte sind danach unverändert; ohne Abweichungen entfällt der Verlust-Satz
  - Test: Live, `s3a2794-teil3-vorlage.spec.ts`: Abo-Datei vorher/nachher (Ampel und Auswahl ersetzt; `report_config`, Etappen bzw. Orte, Zustellung gleich), beide Wege (Abbrechen, Übernehmen), beide Kontexte. Kern: `node --test` auf die Ersetzungs-Payload (`ampelSchreiben.test.ts`).

- **AC-12:** Given ein Trip oder Orts-Briefing mit Abweichungen von seiner Vorlage / When der Nutzer „Auf ‚{Vorlage}‘ zurücksetzen“ wählt / Then stehen Auswahl, Grenzen und Alarm-ab-Stufen wieder wie in der Vorlage, der Picker zeigt „unverändert“, und der Zurücksetzen-Knopf ist verschwunden
  - Test: Live, `s3a2794-teil3-vorlage.spec.ts`: Abo-Zustand vorher/nachher, beide Kontexte. Kern: `node --test` (`ampelModell.test.ts`), Zurücksetzen liefert Abweichungsmenge null.

- **AC-13:** Given ein Orts-Briefing (bisher ohne Vorlagen) / When der Nutzer den Reiter Wetter öffnet / Then hat es dieselbe Vorlage-Karte mit den 7 Systemvorlagen und den eigenen Vorlagen der Art Orte, und ein Vorlagenwechsel verhält sich wie beim Trip (AC-11)
  - Test: Live, `frontend/e2e/s3a2794-teil3-vorlage.spec.ts` (derselbe Test-Code wie AC-10 und AC-11) im Kontext `vergleich`.

- **AC-14:** Given ein Trip oder Orts-Briefing, bei dem Böen und Gewitter alarmfähig sind / When der Nutzer in der Kopfzeile „Alarm ab für alle“ auf Orange stellt / Then steht bei jeder alarmfähigen Metrik „Alarm ab Orange“, Vorboten und reine Anzeige bleiben „kein Alarm“, der Zähler lautet „{x} von {y} Metriken lösen einen Alarm aus. {z} können keinen auslösen (Vorboten und reine Anzeige).“, jede geänderte Metrik zählt als Abweichung, und ist keine alarmfähige Metrik gewählt, erscheint „Keine der gewählten Metriken kann einen Alarm auslösen. Nimm z.B. Wind, Böen oder Gewitter dazu.“
  - Test: Live, `s3a2794-teil3-alarm-ab.spec.ts`: Zählung der Segmente; zweiter Lauf mit einer Auswahl aus lauter Vorboten (z. B. Luftfeuchte, Regenwahrscheinlichkeit). Kern: `node --test` auf Zähler-Text-Modell und Wirkung nur auf alarmfähige Metriken.

- **AC-15:** Given ein Trip oder Orts-Briefing mit mehreren Metriken / When der Nutzer den Reiter Wetter öffnet / Then stehen die Metrik-Zeilen in den fünf Gruppen Temperatur · Wind · Niederschlag & Gewitter · Himmel & Sicht · Schnee & Höhe (nur belegte Gruppen), jede Zeile zeigt Ampel-Leiste mit Grenzzahlen, Erklärsatz, „grün: …“-Zeile („grün: a bis b {Einheit}“, „grün: ab …“, „grün: bis …“ oder „immer grün (keine Grenze gesetzt)“), „Alarm ab“ bzw. „kein Alarm (Vorbote)“ / „kein Alarm“ und „Grenzen ändern“, und es gibt keine CAPE-Zeile, keine Aggregationswahl und keine Roh/Einfach-Wahl
  - Test: Live, `s3a2794-teil3-zeilen.spec.ts`: Gruppenzugehörigkeit je Metrik aus `/api/metrics`, kein Test gegen eine Frontend-Kopie. Kern: `node --test` auf „grün“-Zeile und Erklärsätze (`ampelModell.test.ts`).

- **AC-16:** Given Böen mit „Alarm ab Orange“ in einer Vorlage mit Böen-Grenzen / When der Nutzer „Grenzen ändern“ öffnet und oben orange auf 50 setzt / Then zeigt der Erklärsatz „über 50 km/h“, der Picker „1 Abweichung“, nur die erlaubten Seiten sind als Felder sichtbar (beidseitig, nur oben, nur unten), und nach Speichern und Neuladen ist der Wert gespeichert und die Zeile zeigt „Fertig“ nicht mehr; der Hinweis „Grün ist alles zwischen ‚gelb unten‘ und ‚gelb oben‘. Ein leeres Feld heißt: auf dieser Seite keine Grenze.“ steht im aufgeklappten Zustand, der Satz „Abweichend von der Vorlage ‚{Vorlage}‘.“ nur bei Abweichung
  - Test: Live, `s3a2794-teil3-grenzen.spec.ts`: Neuladen, Abo-Datei prüft `ampel.metrics.gust` (nur die Abweichung steht dort), beide Kontexte.

- **AC-17:** Given ein Nutzer gibt in „Grenzen ändern“ eine ungültige Reihenfolge ein (oben gelb 50 und orange 40, oder unten gelb unter 0 und orange unter 5, oder unten über oben) / When er speichern will / Then zeigt die Zeile einen Fehlertext, nichts wird gespeichert, und die zuvor gespeicherten Grenzen bleiben
  - Test: Kern, `ampelModell.test.ts` (`node --test`): Reihenfolge-Regeln oben, unten, unten nicht über oben. Live, `s3a2794-teil3-grenzen.spec.ts`: Abo-Datei unverändert, beide Kontexte.

- **AC-18:** Given ein Trip oder Orts-Briefing mit Gewitter und Windrichtung / When der Nutzer die beiden Zeilen ansieht / Then zeigt Gewitter „mittel: gelb · orange · rot“ und „hoch: orange · rot“ mit dem Hinweis „‚keins‘ ist immer grün.“, bietet kein „Alarm ab Gelb“ an, und Windrichtung zeigt „keine Ampel, nur Anzeige“ ohne „Grenzen ändern“; bei Vorlage „Wassersport“ erscheint für Gewitter mit Alarm ab Rot der Satz „Alarm, wenn die Gewitter-Stufe seit dem letzten Briefing auf {mittel oder hoch} steigt ({Stufe}). Entwarnung, wenn sie wieder fällt.“, bei Farben, die die Stufe nie erreichen, „Mit diesen Farben erreicht Gewitter nie {Stufe}, daher kein Alarm.“
  - Test: Live, `s3a2794-teil3-gewitter.spec.ts`, zwei Vorlagen, beide Kontexte. Kern: `node --test` auf Gewitter-Regeln und Erklärsatz-Modell. Der Wortlaut aller Erklärsätze wird mit dem S2b-Katalog `alarm.ampel.*` abgeglichen (keine zwei Fassungen derselben Aussage).

- **AC-19:** Given ein Trip oder Orts-Briefing mit der Metrik Wind im Briefing / When der Nutzer „−“ an Wind klickt und danach unter „Nicht im Briefing“ „+ Wind“ wählt / Then verschwindet Wind aus den Zeilen (Picker zeigt 1 Abweichung), taucht nach „+“ wieder auf (hinten angehängt) mit der Meldung „Wind ist jetzt im Briefing und steht in allen Listen unter ‚Inhalt je Kanal und Fläche‘. Dort stellst du Roh oder Einfach ein.“, und der Picker zeigt dann wieder „unverändert“
  - Test: Live, `s3a2794-teil3-nicht-im-briefing.spec.ts`: der Abweichungszähler wird dabei als Nutzer sichtbarer Wert geprüft; Abo-Datei enthält nach „−“ die Metrik nicht in `metrics[]`/`active_metrics`.

- **AC-20:** Given ein Orts-Briefing oder Trip, dessen Altfelder auseinanderlaufen (Bericht an, Alarm aus) / When der Nutzer den Reiter Wetter öffnet / Then steht der Schalter „Amtliche Warnungen — im Briefing und als Alarm, sobald sie dein Gebiet betreffen“ auf an (ODER-Regel); nach dem Umlegen auf aus und Speichern sind `official_alerts_enabled` und `official_warnings.enabled` beide false, bei an beide true, und ein Abo ohne den Schlüssel `official_warnings` fällt auf `official_alert_triggers_enabled` (Default an) zurück
  - Test: Kern, `amtlicheWarnungen.test.ts` (`node --test`) mit allen Kombinationen; Go-Roundtrip-Test beider Speicherwege (`internal/handler/weather_config_2794_teil3_test.go`, `internal/handler/compare_preset_2794_teil3_test.go`), jeweils mit zwei Nutzern; Python-Konsistenzprobe der bestehenden Alarm-Lesart (`trip_alert.py:1116-1118`, `compare_official_alert.py`) ohne Code-Änderung. Live: Playwright mit Datei-Zustand, beide Kontexte; Renderer und Alarm-Engine bleiben unverändert (bestehende Tests grün).

- **AC-21:** Given ein Orts-Briefing und ein Trip / When der Nutzer die Karten Radar und Anpassen ansieht / Then zeigt nur das Orts-Briefing den Schalter „Radar-Regen — Alarm, wenn in der nächsten Stunde Regen auf {deine Orte} zukommt“ (Speichern setzt `radar_alert_enabled`), der Trip zeigt ihn nicht, und die eingeklappte Karte „Anpassen“ lässt das Tagesfenster von–bis (über `ui/select/Select.svelte`, kein natives `<select>`) einstellen, das wie bisher begrenzt (ADR-0035) und gespeichert wird (Trip `report_config.day_window_*_hour`, Orte top-level)
  - Test: Live, `s3a2794-teil3-karten.spec.ts` je Kontext; Tagesfenster-Grenzen über den bestehenden Clamp-Test (`dayWindowClamp`), unverändert grün.

- **AC-28:** Given dieselben Fixtures (Vorlage, Abo-Ampel mit Änderungen an Grenze, `enabled`, `alarm_ab`, Metrik hinzugefügt/entfernt, Gewitterfarbe) / When die Abweichungen gezählt werden / Then liefern die Python-Referenz (`deviation_count`) und der Frontend-Spiegel (`ampelModell.ts`) dieselbe Zahl, jede der fünf Änderungsarten zählt einmal je betroffener Metrik, eine Änderung zurück auf den Vorlagenwert zählt nicht mehr, und der Picker zeigt die Zahl nach jeder Eingabe sofort
  - Test: Kern, `ampelModell.paritaet.test.ts` (`node --test`) liest dieselbe Datei `tests/fixtures/ampel_deviation_cases.json` wie der bestehende pytest; Live: Playwright prüft die Anzeige im Picker nach einer Änderung.

- **AC-29:** Given ein Trip und ein Orts-Briefing, die keine Altstufen, keinen Alarm-Preset, keine Regeln und keine Wetteränderungs-Alarme haben, aber eine aktive Metrik mit `alarm_ab` ≠ `never` in der aufgelösten Ampel / When Werte von grün auf Alarmfarbe springen / Then gilt das Abo als alarmfähig und der Alarm kommt (Trip und Vergleich), und ohne aktive Metrik mit `alarm_ab` ≠ `never` (oder wenn die Metrik mit `alarm_ab` nicht aktiv ist) bleibt es wie bisher stumm; beide Gate-Blöcke von `trip_alert.py` verhalten sich gleich
  - Test: Kern, `tests/tdd/test_2794_teil3_alarmquelle.py` (pytest): Läufe über den Trip-Einstieg (beide Gate-Blöcke) und den Vergleichs-Einstieg mit und ohne `alarm_ab`, beobachtet wird Versand bzw. kein Versand; kein `Mock()`/`patch()` der eigenen Annahme.

- **AC-30:** Given zwei Nutzer A und B mit je einem Trip und einem Orts-Briefing, bei A mit gesetzten Grenzen und Alarm-ab-Stufen / When Nutzer B in seinem Reiter Wetter Grenzen ändert und speichert und A parallel eine unabhängige Einstellung speichert / Then bleiben die Daten von A unverändert, B bekommt keine Werte von A, und das Speichern erhält alle Felder von `display_config`, die der Reiter nicht anfasst (`metric_alert_levels`, `alarm_ab_migration`, Zustellungs-Felder), unverändert (Read-Modify-Write, kein Replace)
  - Test: Kern, Go-Handler-Tests (`internal/handler/weather_config_2794_teil3_test.go`, `internal/handler/compare_preset_2794_teil3_test.go`) mit zwei Nutzern und Feld-Vergleich; Live: Playwright auf Staging mit zwei Konten, `frontend/e2e/s3a2794-teil3-mandanten.spec.ts`.

- **AC-37:** Given ein Trip (Auswahl in `metrics[]`) und ein Orts-Briefing (Auswahl in `active_metrics`) mit beliebiger der 7 Systemvorlagen / When der Nutzer im Reiter Wetter eine Metrik entfernt, hinzufügt, eine Vorlage übernimmt oder zurücksetzt und speichert / Then enthalten `metrics[]` bzw. `active_metrics` die vollständige gewählte Liste (Reihenfolge der bestehenden Liste, neue Metriken hinten), `ampel.metrics.<id>.enabled` steht nur dort als Abweichung, wo die Auswahl von der Vorlage abweicht, und die aus Vorlage und Abweichungen aufgelöste Menge aktiver Metriken ist identisch mit der Auswahlliste; über alle 7 Vorlagen liefern Frontend-Ableitung und Python `resolve_ampel` dieselbe Menge aktiver Metriken, und der Mail-Inhalt eines unveränderten Abos bleibt gleich
  - Test: Kern, `ampelSchreiben.test.ts` (`node --test`) und `tests/tdd/test_2794_teil3_auswahl_paritaet.py` (pytest) über alle 7 Vorlagen mit gemeinsamer Fixture; Live: Playwright, Abo-Datei nach Speichern prüft beide Quellen je Kontext; bestehende Renderer- und Resolver-Tests bleiben unverändert grün.

- **AC-38:** Given der Reiter Wetter in Trip bzw. Orts-Briefing / When der Nutzer mehrere Änderungen macht und speichert, sowie wenn der Reiter im Hub geladen ist, Zustellung ebenfalls gemountet wurde oder das Abo zwischenzeitlich anderswo geändert wurde / Then entsteht genau ein Schreibvorgang des Reiters (Trip: ein `PUT /api/trips/{id}/weather-config` ohne zusätzlichen zweiten PUT desselben Inhalts; Vergleich: ein Eintrag in der Hub-Schreibschlange mit ETag), `ampel` wird als vollständige Abweichungsmenge gesendet, `WeatherMetricsTab` schreibt im Reiter Zustellung keines der Felder des Reiters Wetter, und bei einem ETag-Konflikt im Vergleich lädt der Reiter das Abo neu und überschreibt die fremde Änderung nicht still
  - Test: Kern, angepasste AST-Wächter `s3a2794_eine_wmt_instanz.test.ts`, `s3a2794_speicher_owner_waechter.test.ts`, `s3a2794_zustellung_vergleich_ein_speicherer.test.ts`, `s3a2794_hub_zustellung_verdrahtung.test.ts`, `s3a2794_bereich_filter.test.ts` (Zusicherung „ein Speicherer je Reiter“ bleibt bestehen, wird nicht aufgeweicht); Live: Playwright zählt die Schreib-Anfragen beim Speichern je Kontext und prüft den Konfliktfall mit zwei Browser-Sitzungen.

- **AC-39:** Given eine eigene Bestandsvorlage ohne `ampel`, ein Orts-Briefing ohne Schlüssel `active_metrics` (z. B. neu angelegt mit Standardvorlage, die nur `ampel` mitgibt) und ein Abo mit Vorlage „allgemein“ / When der Nutzer den Reiter Wetter öffnet / Then zeigt der Reiter für die Vorlage ohne `ampel` die Ampel der Standardvorlage `allgemein` mit `enabled` aus den Metriken der Vorlage und zählt Abweichungen gegen diese Ableitung, das Orts-Briefing zeigt die Auswahl aus der aufgelösten Ampel (`enabled`), und beim ersten Speichern wird `active_metrics` vollständig geschrieben; es erscheint kein Fehler und keine leere Auswahl
  - Test: Kern, `ampelModell.test.ts` (`node --test`) mit Fixture-Daten (Vorlage ohne `ampel`, Abo ohne `active_metrics`); Live: Playwright mit angelegtem Orts-Briefing nach Vorlagen-Standard, Abo-Datei vor und nach dem ersten Speichern.

- **AC-40:** Given der Reiter Wetter und der Dialog in Trip und Orts-Briefing am Desktop und Mobil / When der Nutzer ihn bedient / Then gibt es kein natives `<select>`, keine native Checkbox und kein natives Datum-/Zeitfeld (Ersatz-Atome laut ADR-0111), Text und Bedienelemente haben mindestens 4,5:1 Kontrast, alle Schaltflächen und Segmente haben mindestens 44 px Touch-Ziel, und beide Kontexte haben denselben Panel-Rahmen
  - Test: Live, `s3a2794-teil3-design.spec.ts`: Playwright misst Kontrast, Zielgröße und Rahmen je Kontext; Kern: AST-Wächter prüft den Reiter-Ordner auf native Controls; Fresh-Eyes-Abgleich der Screenshots gegen Mockup Fassung 3.

- **AC-41:** Given alle neuen und geänderten Texte dieses Teils (Reiter, Dialog, Fehler- und Hinweistexte, Erklärsätze) / When die Oberfläche auf Deutsch und auf Englisch läuft / Then erscheinen alle über den Katalog `wetter` in beiden Sprachen mit gleichen Platzhaltern, es gibt keinen hartkodierten Nutzertext, Protokoll-Token (z. B. `sms_code`, `compact_label`) bleiben unübersetzt, und die Begriffe Wetter, Vorlage, Ampel, Grenzen ändern, Nicht im Briefing (zusammen mit dem vorhandenen „Alarm ab“) stehen vorab im Glossar `docs/reference/i18n_glossar.md`
  - Test: Kern, bestehender Wächter `keine_hartkodierten_nutzertexte.test.ts` und Katalog-Paritäts-Test (Platzhaltermengen DE = EN); Live: Playwright mit `language=en` für beide Kontexte, `frontend/e2e/s3a2794-teil3-englisch.spec.ts`.

- **AC-42:** Given der Dialog „Als eigene Vorlage speichern“ in Trip bzw. Orts-Briefing / When der Nutzer ihn öffnet und speichert / Then enthält er Name (Pflicht: „Gib der Vorlage einen Namen.“), Beschreibung, den Schalter „Als Standard für neue {Trips|Orte}“ und den Hinweis „Gespeichert werden Metrik-Auswahl, Ampel-Grenzen und Alarmstufen. Zustellung, Etappen und Orte gehören nicht dazu.“, aber weder Zeithorizonte noch Zusammenfassung; die gespeicherte Vorlage enthält die `ampel` des Abos und die Art (`kind`) des Kontexts; ein vorhandener Name zeigt „Eine Vorlage ‚{n}‘ gibt es schon. Wähle einen anderen Namen.“; nach Erfolg erscheint „Vorlage ‚{n}‘ gespeichert. Du findest sie unter ‚Eigene‘.“, und die Vorlage steht in der Vorlagen-Liste nur der passenden Art
  - Test: Live, `s3a2794-teil3-dialog.spec.ts` mit Datei-Zustand je Kontext und zwei Konten; Kern: Go-Handler-Tests aus Teil-PR 1 (`kind`, `ampel`, Duplikat) bleiben grün; `node --test` auf die Dialog-Payload (kein `horizons`, kein `summary`).

## Test Plan

### Automated Tests (TDD RED)

- [ ] **Kern Python (pytest, ohne Netz, ohne Mocks):** Alarmquellen-Gate Trip (beide Blöcke) und Vergleich mit und ohne `alarm_ab`, Versand beobachtet (AC-29); Auswahl-Parität über 7 Vorlagen (AC-37); Konsistenzprobe der Amtliche-Warnungen-Lesart (AC-20).
- [ ] **Kern Go (`go test`):** Zwei-Nutzer-Tests für `PutTripWeatherConfigHandler` und `UpdateComparePresetHandler`: Feld-Erhalt (`metric_alert_levels`, `alarm_ab_migration`, Zustellungs-Felder), `ampel` als Ganzes ersetzt, Roundtrip beider Warn-Felder (AC-20, AC-30).
- [ ] **Kern Frontend (`node --test`):** Zähler-Parität gegen `tests/fixtures/ampel_deviation_cases.json` (AC-28), Reihenfolge- und Gewitter-Regeln (AC-17, AC-18), Auswahl-Ableitung und Fallbacks (AC-37, AC-39), ODER-Lese-Regel (AC-20), Speicher-Payload (AC-11, AC-12, AC-38), Katalog-Parität und Wächter gegen hartkodierte Texte (AC-41), angepasste AST-Wächter (AC-38, AC-40).
- [ ] **RED zuerst aus Nutzersicht:** Je Stufe (3.1, 3.2) werden die zugehörigen ACs vor der Umsetzung rot nachgewiesen, Artefakte im Workflow registriert. Stufe 3.1: AC-17, AC-20 (Kern), AC-28, AC-29, AC-30, AC-37; Stufe 3.2: AC-9 bis AC-16, AC-18, AC-19, AC-21, AC-38 bis AC-42.
- [ ] **Mutations-Gegenprobe (Adversary):** mindestens Gate ohne `alarm_ab`-Erkennung, Zähler ohne `alarm_ab`, Auswahl-Payload ohne `metrics[]`/`active_metrics` (nur `ampel`), Speichern als Replace statt Merge (Feld-Erhalt), ODER-Regel zu UND verändert, Doppelschreiben nur eines Warn-Feldes, `<select>` zurück in `DayWindowCard`; jede Verfälschung muss einen Test rot machen. Mutationen nur per String-Ersetzung mit externer Sicherungskopie.

### Live-E2E (nur `/e2e-verify` gegen Staging)

- [ ] Playwright je Kontext (Trip und Orte), Desktop und Mobil, für AC-9 bis AC-21, AC-38 bis AC-42 mit Datei- bzw. API-Zustand vorher/nachher.
- [ ] Zwei-Konten-Lauf für alle datenbewegenden Wege (Vorlagen, Abo-Speichern, AC-30).
- [ ] Fresh-Eyes-Abgleich der Screenshots beider Kontexte gegen Mockup Fassung 3 (Teil von AC-40).
- [ ] Staging-Voraussetzung: Migration `horizons` auf Staging gelaufen (Runbook), Staging-Mailweg ist für diesen Teil nicht nötig (Mail-Inhalt unverändert).

## Definition of Done

- [ ] AC-9 bis AC-21, AC-28 bis AC-30 und AC-37 bis AC-42 grün in ihrer Schicht, jeweils in beiden Kontexten (`route`, `vergleich`), wo zutreffend; Kern-Schicht zu 100 % grün, alle 6 CI-Checks grün.
- [ ] Stufe 3.1 (Modelle, Alarmquellen-Gate, Lese-Regel amtliche Warnungen, Go-Tests) vor Stufe 3.2 (Oberfläche) grün.
- [ ] AST-Wächter auf den neuen Wetter-Träger nachgezogen, nicht aufgeweicht; genau ein Speicherer je Reiter.
- [ ] Adversary-Verdict VERIFIED inklusive Mutations-Gegenprobe (alle Mutationen aus dem Test Plan rot).
- [ ] Migration der Vorlagen-Zeithorizonte auf Staging und Prod mit Dry-Run und Pre-Snapshot gelaufen (Runbook „Vorlagen-Zeithorizonte entfernen“).
- [ ] `/e2e-verify` auf Staging grün, Prod-Deploy mit Selftest Exit 0.
- [ ] Gesamt-Spec `feat_2794_s3a_reiter_wetter.md` (Lieferplan Teil-PR 3) und Glossar nachgezogen; Issue #2794 bleibt offen bis Teil-PR 4.

## Known Limitations

- **Löschung erst Teil-PR 4:** `CorridorEditor`, `CorridorEditorMobile`, der Alt-Wetterzweig in `WeatherMetricsTab` und die zugehörigen Tests bleiben im Repository, werden aber im Reiter Wetter nicht mehr gemountet. Bis dahin gibt es toten, aber lauffähigen Code.
- **Orts-Standardvorlage beim Anlegen:** Das Ableiten von `active_metrics` aus Vorlagen-`enabled` bei der Neuanlage ist nicht Teil dieses PR (Teil-PR 4, Anlege-Kette); der Reiter fängt den Fall über den Lese-Fallback ab (AC-39). Sendet die Anlege-Kette ein (auch leeres) `display_config`, bleibt der Standard weiterhin aus (Befund aus Teil-PR 1).
- **Zwei Quellen der Auswahl:** Solange Renderer und Resolver `metrics[]`/`active_metrics` lesen (Entscheidung zu AC-37), steht die Auswahl in zwei Feldern. Eine spätere Vereinheitlichung (Resolver auf `resolve_ampel`) ist ein eigenes Vorhaben mit eigenem ADR.
- **Altstufen-Migration:** Ob jedes Bestandsabo bereits durch `alarm_ab_migration` alarmfähig migriert ist, wird nicht geprüft; AC-29 gilt unabhängig davon und macht nur Abos mit gesetztem `alarm_ab` alarmfähig.
- **Radar-Alarm beim Trip** fehlt bis S8 (#2800); der Hinweis „Nicht im Briefing“ verweist auf „Inhalt je Kanal und Fläche“, der bis S3b nur als Abschnitt im Übergangsreiter Zustellung existiert.
- **Veraltete Glossar-Einträge** („Wertebereiche“, „Versand“ als Reiter) werden erst in Teil-PR 4 bereinigt.
- **Migration `horizons`:** läuft nur bei gestoppter `gregor-api` bzw. `gregor-api-staging` (Sperre nur innerhalb des Go-Prozesses), daher kurzer geplanter Stopp beim Deploy.

## Risiken

- **Mount-Regressionen (HIGH):** Teil 2 hatte Fehler durch doppelt gemountete Speicherer. Gegenmaßnahme: AC-38, AST-Wächter nachziehen statt aufweichen, Hydrations-Bedingung im Vergleich erhalten, Playwright zählt Schreib-Anfragen.
- **Ampel als Ganzes ersetzt:** Der Server ersetzt `ampel` komplett; sendet das Frontend eine unvollständige Menge, gehen Abweichungen verloren. Gegenmaßnahme: `ampelSchreiben.ts` sendet immer die vollständige Abweichungsmenge, Konflikt im Vergleich lädt neu, Go-Test mit Feld-Erhalt (AC-30).
- **Auseinanderlaufende Quellen:** `metrics[]`/`active_metrics` und `ampel.metrics.<id>.enabled` könnten abweichen. Gegenmaßnahme: AC-37 mit Parität über 7 Vorlagen und Fixture.
- **Gate-Änderung in `trip_alert.py`:** zentrale Alarm-Logik. Gegenmaßnahme: bestehende Gate-Fälle bleiben unverändert, Helfer additiv, Mutations-Gegenprobe, Tests aus Nutzersicht (AC-29).
- **Umfang:** großer Neubau; zwei Stufen mit eigener grüner Kern-Schicht halten jeden Stand lauffähig.
- **Mandantentrennung:** neue Schreibwege im Frontend, Merge im Go-Handler; AC-30 mit zwei Nutzern, kein Fallback auf `"default"`.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue. ADR-0109 (Reiterstruktur, Pendant-Sperre), ADR-0106 (Ampel als einzige Bewertung, Gewitter ohne Gelb), ADR-0111 (Design), ADR-0035 (Tagesfenster), ADR-0104 (zweisprachig), ADR-0101 (Read-Modify-Write) tragen die Entscheidung.
- **Rationale:** Der Auswahl-Mechanismus (Frontend hält beide Quellen konsistent, Abschnitt Implementation Details) ist eine lokale, umkehrbare Tech-Lead-Entscheidung innerhalb dieser Scheibe, stützt sich auf die bestehenden Leser von `metrics[]`/`active_metrics` und ändert keine Entscheidungsfläche. Eine spätere Umstellung der Resolver auf die Ampel als Auswahlquelle wäre eine Abweichung mit eigenem ADR (siehe Known Limitations).

## Changelog

- 2026-11-10: Initial spec created (Phase 3), Teil-Spec zu `feat_2794_s3a_reiter_wetter.md`; ACs AC-9 bis AC-21, AC-28, AC-29, AC-30 aus der Gesamt-Spec präzisiert, neue ACs AC-37 bis AC-42 (Auswahl-Mechanismus, Speicher-Einzigkeit, Fallbacks, Design, i18n, Dialog); AC-31 bis AC-35 bleiben Teil-PR 4 vorbehalten. Grundlage: Analyse `docs/context/feature-2794-s3a-teil3-wetter.md`.
- 2026-11-10: Phase 5 (Tech-Lead-Korrektur, keine fachliche Änderung): Trip-Speicherweg im Datenfluss auf die bestehenden zwei disjunkten PUTs berichtigt; der Go-Test hatte gezeigt, dass `/weather-config` Warn-Felder und Tagesfenster nicht am Trip ablegt. AC-38 bleibt unverändert gültig (kein zweiter PUT desselben Inhalts).
- 2026-11-10: Phase 5: §3 präzisiert, ab wann die Ampel-Alarmquelle zählt (nur Abos mit `display_config.ampel`, dann inkl. Vorlagen-Vorgaben); Befund des RED-Tests, dass sonst jeder Bestandstrip über die Vorlage alarmfähig würde.
- 2026-11-10: Phase 5: §6 um (d) Anlege-Vorbelegung, (e) SMS-Schwellen und Feld-Eigentum `metrics[]`, (f) Wächter-Nachzug, (g) Test-Vertrag ergänzt (Befunde des RED-Laufs, Tech-Lead-Entscheidungen ohne fachliche Änderung).
