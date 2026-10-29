---
entity_id: feat_2347_s3d_paritaets_e2e
type: feature
created: 2026-10-29
updated: 2026-10-29
status: draft
version: "1.0"
workflow: feat-2347-s3d-paritaets-e2e
tags: [epic-2345, etappe-p6, ratsche, e2e, playwright, trip-compare-teilung, autosave, gesten-gate, metrik-reihenfolge, staging]
---

# Paritäts-E2E, Scheibe S3d: der compare-eigene Rest (#2347)

## Approval

- [ ] Approved

## Purpose

S1, S2, S3a, S3b und S3c sind live (ALTLAST 48 → 29). S3d räumt den **compare-eigenen Rest** der Compare-E2E-Specs, der nicht zu einer der früheren Gruppen gehört: 15 der 29 verbliebenen Altlast-Einträge (Radar-Schalter, Stundenverlauf, Reihenfolge der Stundenverlauf-Metriken, Mobil-Editor 682, Hub-Inline-Edit, Autosave, Metrik-Reihenfolge und acht `.staging`-Specs) plus die Trip-Staging-Spec `feat-1395-s4-conflict-retry`. Danach bleiben 14 Einträge, die S4 leert.

Regel für jede der 15 Dateien (Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`): entweder **kind-parametrisiert** (Schleife über `HUB_KINDS`, Trip UND Ortsvergleich) oder **mit `gz-eigenstaendig:`-Kopf und wahrer Begründung**, warum der Trip kein Pendant hat. Eine Datei wird nur **gelöscht**, wenn die Zuordnung alt → neu (unten, Fall für Fall) jede Zusicherung in einer anderen, laufenden Spec belegt. **Keine Zusicherung geht verloren oder wird abgeschwächt.** Rote Trip-Fälle in neuen Specs sind eine Produktlücke und werden im selben Ticket behoben (AC-16). Reine Testschicht, kein Produktcode (außer AC-16).

Gewählt ist Variante B der Analyse (ein Ticket, vier AC-Gruppen G1–G4, keine Abspaltung von Resten): Löschen nur dort, wo ein Pendant in CI-Reichweite existiert oder neu entsteht; Köpfe dort, wo das Produkt für den Trip nichts Gleichartiges hat.

## Source

- **File:** neu `frontend/e2e/hub-editor-autosave-gesten-gate.spec.ts` (GG) und `frontend/e2e/hub-metrik-reihenfolge-ziehen.spec.ts` (RO); erweitert `hub-alarme-wertprops.spec.ts` (AW-2b), `hub-wertebereiche-speichert-selbst.spec.ts` (WS-8), `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-1/KS-2 geschärft); gelöscht `compare-radar-toggle`, `compare-editor-autosave`, `compare-metric-order` (+ `.staging.setup.ts`, `playwright.compare-metric-order.staging.config.ts`), `feat-1395-s4-conflict-retry.staging` (+ `.setup.ts`, `e2e/playwright.feat-1395-s4.staging.config.ts`); `gz-eigenstaendig:`-Köpfe auf zwölf weiteren Specs; Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py`; Struktur-Test `tests/tdd/test_compare_e2e_storagestate_migration.py`; Config `frontend/playwright.1273-s4c.staging.config.ts`; Ratsche `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml`.
- **Identifier:** `HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `dragDndZoneItem`, `createTestLocation` (`frontend/e2e/helpers.ts`) · `AW_SEL`, `WS_SEL`, `KS_REITER` (Selektor-Tabellen der Bestandsspecs) · `ALTLAST`, `ALTLAST_MAX` · `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`.
- **Produktcode:** keiner geplant (Regel für Trip-Rotfälle: AC-16).

**Schicht und Querschnitts-Prüfpunkte:**
- **Schicht:** ausschließlich Testschicht (`frontend/e2e/`, `frontend/playwright.*.config.ts`, `tests/`, `.github/`). Kein Code in `frontend/src/`, `internal/`, `cmd/`, `api/`, `src/` — außer AC-16.
- **Trip/Ortsvergleich-Teilung:** Kern der Spec. Pendant-Fragen sind am Code beantwortet (Abschnitt „Entscheidungen"); ein kind-Zweig oder Kopf steht nur dort, wo das Produkt für den Trip nichts Gleichartiges hat, und trägt dann eine **wahre** Begründung mit Fundstelle.
- **Mandantentrennung:** keine neuen Endpunkte, keine Daten über Nutzergrenzen. Alle neuen Fälle laufen mit der Admin-Sitzung aus `global.setup.ts` (`storageState`); es gibt keine Registrierung und keinen UI-`login()` (Bremse 5/h/IP unberührt — sie begrenzt nur lokale 3×-Läufe, die über die CI-Läufe im Zielverbund laufen). Die Zwei-Nutzer-Abdeckung bleibt in `hub-cross-user-write-block` und `hub-editor-autosave-user-isolation` unverändert; letztere wird **nicht** angefasst (nur ihr Eintrag in der 1273-Config bleibt).
- **Kanäle:** nicht betroffen, es wird nichts versendet. Die SMS-Zeichengrenzen (153 Vergleich / 160 Trip / 140 Alarm) werden nur im Kopf von `kanal-grenzen-ortsvergleich` dokumentiert.

## Gesamtschnitt #2347 (Stand)

| Scheibe | Inhalt | Stand |
|---|---|---|
| S1–S3a | Helfer, Reiterleiste, Kopf, Listen-Menü, Alarme, Wertebereiche, Wetter-Metriken (48 → 34) | live |
| S3b | Versand-Gruppe (34 → 30) | live |
| S3c | Konflikt-412 über zwei Kontexte (30 → 29) | live (29.10.) |
| **S3d (diese Spec)** | **compare-eigener Rest: 15 Altlast-Einträge + feat-1395-s4**; ALTLAST 29 → **14** | diese Spec |
| S4 | Gruppe ohne Trip-Pendant, #2243-Leichen, ALTLAST leer | folgt |

Ticket und Epic bleiben offen bis S4; Scheiben werden strikt nacheinander gemergt.

## Entscheidungen zu den offenen Fragen aus der Analyse

Alle am Code beantwortet; keine Rückfrage an den PO.

1. **Hat der Trip eine Metrik-Reihenfolge per Drag über den geteilten Baustein? — JA für die Übersichts-Reihenfolge, NEIN für den Stundenverlauf.**
   - Die Reihenfolge-Karte nutzt in beiden Kontexten **denselben** Baustein `WeatherV2Reihenfolge` (SortableList + DragHandle): Vergleich `WeatherMetricsTab.svelte:1514-1537` (`LayoutTab context="vergleich"`, `onDndReorder={onCompareDndReorder}`), Trip `WeatherMetricsTab.svelte:1704-1720` (`LayoutTab context="route"`, `onDndReorder` Z. 842-850 → `scheduleAutoSave`). Der Abschnitt `'reihenfolge'` gilt seit #1359 für **beide** Kontexte (`weatherMetricsTabSections.ts`, Kommentar „Behandlung wie 'official_alerts'"). Der Kommentar in `WeatherMetricsTab.svelte:1499-1501` sagt ausdrücklich „DERSELBE geteilte Reihenfolge-Baustein wie im Trip". Das Trip-Drag-Speichern-Neuladen ist bisher nur durch `layout-tab-route.spec.ts` AC-3 belegt (UI-`login()`, fester Trip, nicht auf der Positivliste). ⇒ **`compare-metric-order` wird kind-parametrisiert** (neue Spec RO, AC-8) und die Altdatei gelöscht.
   - Der **Stundenverlauf** ist in `COMPARE_ONLY_SECTIONS` (`weatherMetricsTabSections.ts`, fachlich entschieden #2346 S3: beim Trip IST die Mail-Haupttabelle die Stundentabelle, ihre Spalten steuert die normale Metrik-Auswahl). `WeatherMetricsTab.svelte:1579` rendert den Block nur bei `sections.includes('stundenverlauf')`. ⇒ **`compare-hourly-metric-order` und `compare-stundenverlauf-wertprops` bekommen einen Kopf**, kein kind-Zweig (der Trip hat die Steuerung nicht).
2. **`compare-stundenverlauf-wertprops` wird NICHT gelöscht (Abweichung vom ersten Zuschnitt).** Die Analyse sah Löschen mit Zuordnung auf MS-2/MS-7 vor. Am Code nicht haltbar: MS-2 schaltet Grundauswahl-Metrik plus `compare-layout-hourly-enabled-toggle` und prüft `hourly_enabled`; MS-7 behandelt `display_config.hourly_metrics` als Eigenschlüssel des Reiters (`dcEigen`) und prüft ihn nicht. **Kein MS-Fall berührt `compare-layout-hourly-metric-*` oder `hourly_metrics`**; damit fiele die Mutations-Gegenprobe (`onMetricKeys` am Mount weglassen ⇒ Abwählen wirkt nicht) ersatzlos weg. Die Datei steht auf der Positivliste und bleibt dort; sie wird nur aus ALTLAST genommen (Kopf, siehe AC-10). Der ALTLAST-Zähler ändert sich dadurch nicht (29 → 14 bleibt).
3. **Radar-Schalter (`compare-radar-toggle`, 3 Fälle):** Der Radar-Alarm existiert nur im Vergleichs-Preset (`alarmeTabSections.ts:11`, `AlarmeTab.svelte:530`). Zwei der drei Fälle sind schon gedeckt (AW-2: Radar einschalten, ein PUT, überlebt Neuladen; KS-2: Alarm-Wert bleibt nach Umbenennen im Server-Stand). Offen sind „Vorgabe bei fehlendem Feld" (AW-2 setzt `radar_alert_enabled: false` **explizit**, prüft die Vorgabe also nie) und die **Anzeige** nach Umbenennen + Neuladen. Beides ist für den Trip sinnvoll (Auslöser „Amtliche Warnungen" hat Vorgabe **an**: `AlarmeTab.svelte:218-220`, `official_warnings?.enabled ?? official_alert_triggers_enabled !== false`) und wird daher **je kind** gebaut (AW-2b neu; KS-2 geschärft), nicht als vergleich-Zweig.
4. **`compare-editor-autosave` (10 Fälle):** Die Fälle sind Orte-Gesten, doch der Trip hat eine echte Entsprechung für „Punkte-Geste ohne Speichern-Klick": den Etappen-Reiter (`HUB_SEL[kind].punkteReiter`; Muster `hub-save-chip` SC-2: Vergleich „Ort entfernen", Trip „Etappen-Datum ändern + blur"). Deshalb **kein** compare-eigener Rest: alle Fälle laufen je kind (GG, AC-4 bis AC-7) oder sind vom Bestand gedeckt (Zuordnung unten). Die Datei wird gelöscht.
5. **`feat-1395-s4-conflict-retry.staging` (Trip-412-Retry):** Der Fall „fremder Schreiber ⇒ 412 ⇒ ‚Nochmal speichern' ⇒ Retry gelingt" läuft seit S3c im CI-Stack über zwei Kontexte für den Trip (KS-1 route, alle vier Reiter inkl. Alarme-Auslöser — dieselbe Geste wie der Altfall). Zwei Einzel-Zusicherungen der Altdatei werden dort **nicht** geprüft: (a) der Refresh-GET geht vor dem Retry-PUT hinaus, (b) der Retry-PUT trägt einen **frischen** `If-Match`. KS-1 wird um genau diese beiden Prüfungen geschärft (AC-12), danach wird die Altdatei samt `.setup.ts` und Config gelöscht. Der Block „Aufräum-Kontrolle" ist durch `seedHub().aufraeumen()` im `finally` und `global.teardown.ts` (Präfix-Sweep `E2E-GZ-`) gedeckt. Die Nachbarspec `feat-1395-s3-etag-ifmatch.staging` ist **nicht** Teil dieser Scheibe.
6. **Staging-only-Specs (`.staging`):** Keine wird zusammengeführt (je eigenes Setup, eigene Config, Login-Limit, Basic-Auth, Admin-/Datenzugriffs-Fallen; im CI-Stack nicht lauffähig, Mutations-Gegenprobe dort nicht prüfbar). Jede bekommt einen Kopf mit **wahrer** Begründung (Tabelle „Köpfe", AC-11) — „läuft nur auf Staging" ist ausdrücklich **kein** Pendant-Grund. `compare-active-metrics-format` und `compare-outlook-metric-selection` würden nur bei vollständiger Zuordnung gelöscht; die Zuordnung ist nicht vollständig (Rücksetzpfad nach fehlgeschlagenem PUT, verzögerte Katalogantwort, Paar-Altform-Normalisierung haben in keiner hub-Spec ein Gegenstück) ⇒ **Kopf**.
7. **Veraltete Vorbedingung `wm2-aus-gruppe` = 0:** `ci_e2e_specs.txt` (Messung 2026-08) hält fest, dass beide Fälle von `compare-metric-order` rot waren („AC-13 FAIL: eine ‚Aus in diesem Kanal'-Gruppe darf im Ortsvergleich nicht entstehen", erwartet 0, erhalten 2). Ursache: Seit #1703 S8 reicht der Vergleich `offColumns` an `WeatherV2Reihenfolge` durch (`WeatherMetricsTab.svelte:1531`) — „Aus ist ein Zustand" gilt dort nun ebenfalls. Die Vorbedingung ist **veraltet, nicht das Produkt**. Die neue Spec RO trägt sie nicht mehr; sie bindet die Zeilenprüfung an den Block der Reihenfolge-Karte (`weather-metrics-vergleich-reihenfolge` bzw. `weather-metrics-kanal-reihenfolge`), und in `compare-hourly-metric-order` wird die tote Vorbedingung entfernt (AC-10).
8. **Welcher Schreibweg trägt das Ziehen?** Offen und im RED zu **messen**, nicht festzuschreiben: der Trip schreibt über `PUT …/weather-config` (`display_config.metrics[].order` bzw. kanal-eigener Eintrag in `channel_layouts`), der Vergleich über `PUT /api/compare/presets/{id}` (`display_config.active_metrics` bzw. `channel_active_metrics`). Seit #1575/#1703 S8 hängt das Zielfeld vom aktiven Kanal-Reiter ab. Die Spec legt die **Zusicherung** fest („Reihenfolge nach Reload gleich, Server trägt sie"), das Feld je kind wird im RED an der Antwort des Servers gemessen und in die Tabelle nachgetragen.

## Kind-Kontraste (compare-eigen vs. gemeinsam)

Selektoren aus `HUB_SEL`, `AW_SEL`, `WS_SEL`, `KS_REITER`, `layout-tab-route.spec.ts` (Trip-Seed) und `compare-metric-order.spec.ts` (Vergleich-Seed); im RED gegen den gerenderten Hub gemessen.

| Fall | route (Trip) | vergleich | Begründung |
|---|---|---|---|
| AW-2b Vorgabe bei fehlendem Feld | Seed **ohne** `official_warnings`; `alerts-tab-official-alert-triggers-toggle` steht **an** | Seed **ohne** `radar_alert_enabled`; `alarme-radar-toggle` steht **aus** | Vorgaben sind je kind verschieden (`AlarmeTab.svelte:218-220` bzw. Radar Vorgabe aus); gemeinsam ist: Öffnen speichert nichts, Vorgabe wird angezeigt |
| KS-2 Anzeige nach Umbenennen | Auslöser Amtliche Warnungen (Seed an ⇒ aus) | Auslöser Radar (Seed aus ⇒ an) | `AW_SEL[kind].ausloeser` |
| WS-8 Markieren | `corridor-row-wind_gust`, Seed `mark:false` ⇒ `true` | `corridor-row-snow_depth_cm`, Seed `mark:true` ⇒ `false` | `WS_SEL[kind].zeile`; Schalter ist derselbe geteilte `CorridorEditor` |
| GG Punkte-Geste | Etappen-Reiter: `stage-date-field` ändern + blur, Körper trägt `stages` | Orte-Reiter: `hub-orte-remove`, Körper `{ location_ids }` | `HUB_SEL[kind].punkteReiter`; Muster `hub-save-chip` SC-2 |
| GG zweite unabhängige Geste (Re-Armierung) | Seed mit **zwei** Etappen, Datum der zweiten ändern | Seed mit **drei** Orten (`createTestLocation`), zweiten Ort entfernen | beide Gesten im selben Reiter, erste PUT läuft noch |
| GG Versand-Geste | `versand-abschnitt` · `report-morning-time` 06:00 ⇒ 05:00; Stand `report_config.morning_time` beginnt mit `05:00` | gleiche Auswahl; Stand `morning_time` beginnt mit `05:00` | wie S3c (Versand-Abschnitt im Reiter Wetter-Metriken) |
| RO Zeilen-Kennungen | `temperature`, `wind`, `precipitation` (Seed wie `layout-tab-route.spec.ts`) | `temp_max_c`, `wind_max_kmh`, `sunny_hours_h` (Seed wie `compare-metric-order.spec.ts`) | Vokabular je kind verschieden |
| RO Hinweis „Amtliche Warnungen zuerst" | **kein** Hinweis in der Trip-Karte (`WeatherMetricsTab.svelte:1704-1760` trägt den Text nicht; Amtliche Warnungen sind im Trip ein eigener Abschnitt `official_alerts`) | `weather-metrics-vergleich-warn-hint` (`:1523-1528`) | **echtes Compare-Eigen**, einziger kind-Zweig in RO; die Aussage „Amtliche Warnungen ist keine ziehbare Zeile" gilt für beide |

## Befunde (am Code gemessen, 2026-10-29)

1. **Ausgangsstand:** ALTLAST 29 = 28 × Regel 1 + 1 × Regel 2 (`ALTLAST_MAX` Literal 29). 15 davon sind S3d, 14 sind S4: `compare-alarm-config`, `compare-detail-edit-entry`, `compare-edit-redirect`, `compare-editor-fidelity-s8d`, `compare-editor-slice1`, `compare-editor-slice4`, `compare-flow-navigation`, `compare-hub-fidelity-s8c`, `compare-layout-tab-dissolution`, `compare-legacy-fields-survive-save`, `compare-new-vorlage`, `feat-1461-s3b2b-compare-kanal-schwelle`, `issue-1080-compare-new-url`, `issue-1093-compare-layout-crash`.
2. **Auf der Positivliste** (`ci_e2e_specs.txt`, 72 Zeilen): `compare-hub-inline-edit` (Z. 442), `compare-radar-toggle` (445), `compare-stundenverlauf-wertprops` (446), `issue-682-compare-editor-mobile` (487). **Nicht** auf der Liste: `compare-hourly-metric-order`, `compare-metric-order`, `compare-editor-autosave` und alle `.staging`-Specs. Löschen von Letzteren berührt `E2E_MIN_SPECS`/`E2E_MIN_EXECUTED_HAUPT` nicht.
3. **Falle Struktur-Test:** `tests/tdd/test_compare_e2e_storagestate_migration.py:24` führt `compare-radar-toggle.spec.ts` in `MIGRATED_FILES` und liest die Datei (`read_text` auf gelöschte Datei = rot); gleiche Datei prüft, dass `playwright.1273-s4c.staging.config.ts` jede migrierte Datei im storageState-Projekt nennt. Die Config nennt außerdem `compare-editor-autosave` (Z. 33) und `compare-radar-toggle` (Z. 35). Alle drei Stellen werden im selben Commit bereinigt (AC-9); `hub-editor-autosave-user-isolation` (Z. 34) bleibt.
4. **Verweise in Kommentaren** auf zu löschende Dateien: `e2e/compare-layout-tab-dissolution.spec.ts:39` und `playwright.compare-layout-tab-dissolution.staging.config.ts:5` (nennen die Metric-Order-Config als Vorlage), `e2e/save-status-indicator-honesty.spec.ts:12`, `e2e/hub-versand-speichert-selbst.spec.ts:8, 467`, mehrere Kommentare in `.github/ci_e2e_specs.txt` (Z. 168, 187, 245). Nur Kommentare, kein Code liest die Dateien (`compare_stundenverlauf_wertprops.test.ts:21` und `context_herkunft_baseline_ausserhalb_shared.test.ts:16` erwähnen den **bleibenden** Stundenverlauf-Spec). Zeiger werden umgehängt, nicht gelöscht (AC-18).
5. **SMS 153/140 vs. 160:** kein Widerspruch, kind- und wegabhängig (Vergleichs-Briefing 153 `channel_layout.py:48`, Trip-Briefing 160 `trip_report.py:446`, Alarm 140 `alert/render.py:621`). Das steht belegt im Kopf von `kanal-grenzen-ortsvergleich` und bleibt dort.
6. **`kanal-grenzen-ortsvergleich`** fällt unter **Regel 2** (Name ohne „compare", Text steuert `compare-detail-tab` an); ein Kopf deckt Regel 2 genauso wie Regel 1.
7. **Fallzahlen Alt:** radar-toggle 3, stundenverlauf-wertprops 4, hourly-metric-order 3, metric-order 2, 682 6, hub-inline-edit 3, editor-autosave 10, feat-1395-s4 2 (davon ein Aufräum-Kontrollfall).

## Zuordnung alt → neu (Regressionsnetz)

### `compare-radar-toggle.spec.ts` (gelöscht)

| Alt | Neu | Anmerkung |
|---|---|---|
| `test_radar_toggle_default_off_on_new_preset` | **AW-2b** je kind (Vorgabe bei fehlendem Feld) | Seed **ohne** Feld; zusätzlich: Öffnen speichert nichts (0 PUT) |
| `test_radar_toggle_enable_persists_roundtrip` | AW-2 (vergleich, Radar: ein PUT, Server `radar_alert_enabled`, Neuladen) + AW-1 (route, Auslöser) | schon gedeckt |
| `test_radar_toggle_preserved_on_unrelated_save` | **KS-2 geschärft** je kind (Server-Stand trägt Name **und** Auslöser; neu: nach Neuladen steht der Schalter weiter auf dem gesetzten Wert) | Umbenennen im Kopf = „fremdes Speichern"; Kopf-PUT = `{name}` |

### `compare-editor-autosave.spec.ts` (gelöscht)

| Alt | Neu | Anmerkung |
|---|---|---|
| AC-5 Ort abwählen speichert, ein PUT, Körper `location_ids` | **GG-4** je kind (Punkte-Geste ohne Speichern-Klick: genau ein PUT, Körper trägt das Punkte-Teilfeld, nicht `name`) | zusätzlich `hub-save-chip` SC-2 (Chip, Server-Stand, Neuladen) |
| AC-6 zwei Aktionen (Ort + Versand-Zeit) ⇒ genau zwei PUTs, beide persistent | **GG-5** je kind (Punkte-Geste + Versand-Uhrzeit ⇒ genau zwei PUTs, beide im Stand) | VS-5 deckt nur die Versand-Hälfte |
| F001 Re-Armierung während laufendem Autosave | **GG-3** je kind (PUT künstlich verzögert, zweite Geste während der erste PUT läuft, beide landen) | im Hub trägt `hubPutQueue` (kein Merge) die Zusicherung |
| AC-7 Editor öffnen ohne Geste, wegnavigieren ⇒ 0 PUT | **GG-1** je kind (alle Reiter, Stabilitätsfenster, danach Navigation) | war nur für Orte; jetzt Punkte-, Alarme-, Wertebereiche-, Wetter-Metriken-Reiter |
| AC-8 Änderung + sofortige Navigation ⇒ kein Datenverlust | **GG-2** je kind (Punkte-Geste, sofort zur Liste, Server-Stand per `expect.poll`) | |
| AC-9 Chip „wird gespeichert" → „gespeichert" | `hub-save-chip` **SC-2** je kind (strenger: verzögerter PUT macht `saving` beobachtbar, Zeitstempel, Neuladen) | schon gedeckt |
| AC-10 Autospeichern schließt ohne Fehler ab, persistiert | SC-2 (idle, Persistenz) + SC-4 (Fehlerzustand nur bei PUT-Fehler) | schon gedeckt |
| AC-14 Markieren-Toggle im Wertebereich speichert automatisch | **WS-8** je kind (`corridor-row-<zeile>` · „Markieren" umlegen ⇒ ein PUT, Stand `mark` umgekehrt) | |
| AC-1 (#1371) kein „Warnen"-Bedienelement in der Wertebereich-Zeile | **WS-8** je kind (zusätzlich: kein Knopf „Warnen", „Markieren" und „✕ entfernen" sichtbar) | Trip-Seite zusätzlich `issue-953-alerts-autosave-tabswitch` |
| F003 Slider-Griff ziehen speichert (echter Maus-Drag) | `hub-wertebereiche-speichert-selbst` **WS-2** je kind (Griff ziehen, über dem Reiterkopf loslassen) + `hub-wertebereiche-wertprops` WW-2/WW-3c | schon gedeckt |

### `compare-metric-order.spec.ts` (gelöscht)

| Alt | Neu | Anmerkung |
|---|---|---|
| AC-3 Ziehen speichert (PUT feuert, Körper trägt neue Reihenfolge, Server behält sie, Neuladen zeigt sie) | **RO-1** je kind | Zielfeld je kind im RED messen (Entscheidung 8); veraltete Vorbedingung `wm2-aus-gruppe` = 0 entfällt (Entscheidung 7) |
| AC-6 „Amtliche Warnungen" ist keine ziehbare Zeile, aber erklärt | **RO-2**: Zeilenprüfung je kind, Hinweis nur vergleich | der Hinweis ist Compare-eigen (Kind-Kontraste) |

### `feat-1395-s4-conflict-retry.staging.spec.ts` (+ `.setup.ts`, Config, gelöscht)

| Alt | Neu | Anmerkung |
|---|---|---|
| 412 beim Auslöser-Speichern ⇒ Chip `conflict` ⇒ „Nochmal speichern" ⇒ Retry 200 ⇒ `idle` | KS-1 (route, Reiter Alarme) im CI-Stack, zusätzlich WS-4/MS-5/VS-2 | schon gedeckt (S3c) |
| Refresh-GET geht **vor** dem Retry-PUT hinaus | **KS-1 geschärft** (AC-12) | neu |
| Retry-PUT trägt frischen `If-Match` | **KS-1 geschärft** (AC-12): `If-Match` des Retry gesetzt **und** ≠ dem des abgelehnten PUT | neu |
| Aufräum-Kontrolle | `finally` mit `hub.aufraeumen()` + `global.teardown.ts` | Prozessregel AC-15 |
| (Kern) Race beim Refresh, generische Fehler, ohne `tripId` | `saveStatusConflictRetry.test.ts` (Kerntest, war schon so) | unverändert |

### Köpfe statt Löschung (keine Zusicherung verschiebt sich)

`compare-stundenverlauf-wertprops` (4 Fälle), `compare-hourly-metric-order` (3), `issue-682-compare-editor-mobile` (6), `compare-hub-inline-edit` (3) und die acht `.staging`-Specs bleiben mit allen Fällen; sie erhalten nur den Kopf (und bei `compare-hourly-metric-order` die Bereinigung der toten Vorbedingung, AC-10). Der Gegenprobe-Vermerk: die zugehörigen Bestandstests (`compare_stundenverlauf_wertprops.test.ts`, `context_herkunft_baseline_ausserhalb_shared.test.ts`) verweisen weiter auf die bleibende Stundenverlauf-Spec.

## Köpfe (`gz-eigenstaendig:`, erste 30 Zeilen, ≥ 15 Zeichen, **wahre** Begründung)

Der Kopf steht als eigene Kommentarzeile ganz oben in der Datei (Zeile 1 oder 2), Form `// gz-eigenstaendig: <Begründung>`. Begründungen (Wortlaut sinngemäß, in /50 in eine Zeile fassen); Pendant-Bezug jeweils benannt:

| Datei | Begründung | Trip-Pendant / Beleg |
|---|---|---|
| `compare-stundenverlauf-wertprops.spec.ts` | Stundenverlauf-Steuerung existiert nur im Ortsvergleich (`COMPARE_ONLY_SECTIONS`, #2346 S3: beim Trip ist die Mail-Haupttabelle die Stundentabelle) | `weatherMetricsTabSections.ts`, `WeatherMetricsTab.svelte:1579` |
| `compare-hourly-metric-order.spec.ts` | wie oben; zusätzlich Anlege-Seite `/compare/new` (Alt-Editor) | wie oben |
| `issue-682-compare-editor-mobile.spec.ts` | Mobil-Shell des alten Compare-Anlege-Editors (`cm-mobile-*`, `CompareEditor`/Wizard, fällt mit P7 ersatzlos); Trip-Pendant ist die Mobil-Spec des Trip-Anlegens | `issue-661-trip-new-mobile.spec.ts`; Mandantentrennung AC-5 kind-übergreifend in `hub-cross-user-write-block` |
| `compare-hub-inline-edit.spec.ts` | nur der Orte-Tab (Drag, Hinzufügen-Panel, Entfernen) ist übrig — erlaubte Compare-Eigenheit; der Wertebereich-Teil lebt kind-parametrisiert in `hub-wertebereiche-wertprops` WW-3a/b/c | Etappen-Pendant: `hub-save-chip` SC-2, `etappen-strip-sortieren.spec.ts` |
| `compare-active-metrics-format.staging.spec.ts` | Speicherformat `display_config.active_metrics` (`{metric_id, aggregation}`, #1373) ist Vergleichs-eigen; der Trip speichert `display_config.metrics[]` | kind-neutrale Teile: MS-1/MS-6/MS-7 |
| `compare-neu-kanal-anlegen.staging.spec.ts` | Anlege-Seite `/compare/new` mit POST-Weg und `channel_active_metrics` der transponierten Vergleichs-Übersicht (Orte = Spalten) | Trip-Kanal-Reiter: `layout-tab-route.spec.ts`, `kanal-abwahl-bleibt-reversibel.staging.spec.ts` |
| `compare-outlook-metric-selection.staging.spec.ts` | Ausblick-Auswahl des Ortsvergleichs im Hub: Vergleichs-Katalog `/api/compare/metrics` (26 Zeilen zu 24 Größen), Paar-Altform-Normalisierung, Speicher über Hub-Commit; der Trip koppelt den Ausblick an `buckets.primary` mit Trip-Auto-Save (`WeatherMetricsTab.svelte:2008-2014`) | `trip-outlook-metric-selection.staging.spec.ts`, `ausblick-erbt-grundauswahl.staging.spec.ts` |
| `compare-uebersicht-kanal-bedienung.staging.spec.ts` | Kanal-Reiter der transponierten Vergleichs-Übersicht (E-Mail/Telegram 7 Zeilen/SMS 153) — erlaubte Compare-Eigenheit | `kanal-grenzen-und-hinweise.staging.spec.ts` (Trip) |
| `compare-uebersicht-kanal-persistenz.staging.spec.ts` | `channel_active_metrics` der Vergleichs-Übersicht (Go-Merge ersetzt das Ganze), Hub-Mount `CompareTabs.svelte` | `kanal-abwahl-bleibt-reversibel.staging.spec.ts` (Trip) |
| `fix-1350-compare-metric-select.staging.spec.ts` | Quelle der Vergleichs-Auswahlliste ist `GET /api/compare/metrics`; der Trip liest `GET /api/metrics` | Pool je kind: `hub-wertebereiche-speichert-selbst` |
| `fix-1350t3-compare-threshold-source.staging.spec.ts` | Quelle des Vergleichs-Schwellen-Pools ist `GET /api/compare/metrics` (`CompareMetricDef`); der Trip nutzt das Metrik-Register | wie oben |
| `kanal-grenzen-ortsvergleich.staging.spec.ts` | SMS-Grenzen sind wegabhängig: Vergleichs-Briefing 153, Trip-Briefing 160, Alarm 140 (`channel_layout.py:48`, `trip_report.py:446`, `alert/render.py:621`), dazu Abwahl-Hinweis je Kanal-Reiter der Vergleichs-Übersicht (#2438) | Trip: `kanal-grenzen-und-hinweise.staging.spec.ts` |

## Estimated Scope

- **LoC (Testcode, netto):** ca. +560 (GG ≈ 270, RO ≈ 140, AW-2b/WS-8/KS-Schärfung ≈ 110, Köpfe + Bereinigungen ≈ 40) / −ca. 1250 (radar 150 + autosave 479 + metric-order 249 + feat-1395-s4 215 + Setup/Configs ≈ 150). Ob Testdateien ins LoC-Limit 250 zählen, liefert `workflow.py status`; zählen sie, `loc_limit_override` auf 500.
- **Files:** ca. 28 (2 neu, 3 erweitert, 1 geschärft, 12 Köpfe, 8 gelöscht inkl. Setups/Configs, Wächter, Struktur-Test, 1273-Config, Ratsche, `ci.yml`, Kommentar-Zeiger).
- **Effort:** high (Trip-Fälle erstmals gemessen, DnD-Fälle, Mutations-Gegenprobe je kind, Ratschen-Nachmessung). **Risiko:** MEDIUM — (1) Trip-Fälle (RO, GG) können rot sein (AC-16), (2) Pointer-Drag in CI kann flackern (Filter B 3×), (3) `ci_e2e_specs.txt`/`ci.yml` sind Konfliktpunkte: vor Commit `git merge --ff-only origin/main` bzw. Rebase prüfen.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `frontend/e2e/helpers.ts` (`HUB_KINDS`, `HUB_SEL`, `seedHub`, `openHub`, `hubApiPath`, `dragDndZoneItem`, `createTestLocation`) | module | Basis |
| `hub-save-chip.spec.ts` (SC-2 Auslöser-Muster), `hub-alarme-wertprops.spec.ts` (`AW_SEL`), `hub-wertebereiche-speichert-selbst.spec.ts` (`WS_SEL`), `hub-konfliktschutz-zwei-kontexte.spec.ts` (`KS_REITER`, `kontextB`), `hub-wetter-metriken-speichert-selbst.spec.ts`, `hub-versand-*` | module | Vorbilder und Selektor-/Feldpfad-Quellen je kind |
| `layout-tab-route.spec.ts` (Trip-Seed und Drag-Selektoren der Reihenfolge-Karte) | module | Vorlage für RO (route) — wird **nicht** geändert |
| `WeatherMetricsTab.svelte`, `WeatherV2Reihenfolge.svelte`, `weatherMetricsTabSections.ts`, `AlarmeTab.svelte`, `saveStatusStore.svelte.ts` (`retryConflict`) | module | geprüfte Bausteine (unverändert, außer AC-16) |
| `.github/ci_e2e_specs.txt`, `ci.yml` (Job `e2e`), `e2e_gate.py`, `tests/unit/test_e2e_positivliste_ratschen_bindung.py` | CI | Positivliste, `E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT` |
| `tests/unit/test_e2e_compare_paritaet_waechter.py`, `tests/tdd/test_compare_e2e_storagestate_migration.py`, `frontend/playwright.1273-s4c.staging.config.ts` | test/config | `ALTLAST`/`ALTLAST_MAX`, `MIGRATED_FILES`, storageState-Projekt |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/hub-editor-autosave-gesten-gate.spec.ts` | CREATE | GG-1 bis GG-5 je kind (Gesten-Gate, Navigation, Re-Armierung, Punkte-Geste, zwei Aktionen) |
| `frontend/e2e/hub-metrik-reihenfolge-ziehen.spec.ts` | CREATE | RO-1 (Ziehen speichert, überlebt Neuladen) je kind, RO-2 (keine ziehbare Zeile „Amtliche Warnungen"; Hinweis nur vergleich) |
| `frontend/e2e/hub-alarme-wertprops.spec.ts` | MODIFY | AW-2b je kind (Vorgabe bei fehlendem Feld); Kopfkommentar-Zuordnung fortschreiben |
| `frontend/e2e/hub-wertebereiche-speichert-selbst.spec.ts` | MODIFY | WS-8 je kind (Markieren-Toggle, kein „Warnen") |
| `frontend/e2e/hub-konfliktschutz-zwei-kontexte.spec.ts` | MODIFY | KS-2: Anzeige nach Umbenennen + Neuladen; KS-1: Refresh-GET vor Retry-PUT, frischer `If-Match` |
| `frontend/e2e/compare-radar-toggle.spec.ts` | DELETE | erst nach grünem Lauf von AW-2b, KS-2 |
| `frontend/e2e/compare-editor-autosave.spec.ts` | DELETE | erst nach grünem Lauf von GG, WS-8 |
| `frontend/e2e/compare-metric-order.spec.ts` + `compare-metric-order.staging.setup.ts` + `frontend/playwright.compare-metric-order.staging.config.ts` | DELETE | erst nach grünem Lauf von RO |
| `frontend/e2e/feat-1395-s4-conflict-retry.staging.spec.ts` + `.staging.setup.ts` + `frontend/e2e/playwright.feat-1395-s4.staging.config.ts` | DELETE | erst nach grünem Lauf des geschärften KS-1 |
| 12 Specs laut Tabelle „Köpfe" | MODIFY | `gz-eigenstaendig:`-Kopf; `compare-hourly-metric-order` zusätzlich tote Vorbedingung entfernen |
| `tests/unit/test_e2e_compare_paritaet_waechter.py` | MODIFY | 15 Einträge raus, `ALTLAST_MAX` Literal 14, Docstring-Messzeile (S3d), Prüfdatum 2027-01-24 unverändert |
| `tests/tdd/test_compare_e2e_storagestate_migration.py` | MODIFY | `compare-radar-toggle.spec.ts` aus `MIGRATED_FILES` (Kommentar wie S3b), Docstring „vier" |
| `frontend/playwright.1273-s4c.staging.config.ts` | MODIFY | Einträge `compare-editor-autosave` und `compare-radar-toggle` entfernen |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` | MODIFY | Zeile `compare-radar-toggle` raus, GG und RO rein (alphabetisch), `E2E_MIN_SPECS` exakt, `E2E_MIN_EXECUTED_HAUPT` gemessen, Begründungen fortgeschrieben |
| `compare-layout-tab-dissolution.spec.ts:39`, `playwright.compare-layout-tab-dissolution.staging.config.ts:5`, `save-status-indicator-honesty.spec.ts:12`, `hub-versand-speichert-selbst.spec.ts:8,467` | MODIFY (Kommentar) | Zeiger umhängen |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Zahl „S3d: 14" |

## Implementation Details

Alle neuen Fälle: `for (const kind of HUB_KINDS) test(\`XX-n (${kind}): …\`)`. Setup `seedHub(request, kind, { extra })`; Öffnen `openHub(page, kind, id, { tab })`; Warten nur `expect.poll`, `toHaveAttribute`, `toHaveCount`, `toBeVisible` und das Stabilitätsfenster `bleibtBei(lies, soll, ms, message)` (Muster `hub-alarme-wertprops`) — **kein** `waitForTimeout`, kein `skip`/`test.fixme`, kein UI-`login()`, kein fester `storageState`-Pfad, kein `__dirname`, kein `page.screenshot({path})`. Erwartungswerte stehen im Test fest, nie aus dem gerenderten Produkt gelesen. `finally`: `hub.aufraeumen()`. kind-Zweige nur laut Tabelle „Kind-Kontraste", jeder mit Begründungskommentar.

**Ersatz für feste Schlafzeiten der Altfälle:**
- Altes „1500 ms warten" (AC-7): `bleibtBei(() => puts.length, 0, 2_000, …)` je Reiter.
- Altes „900 ms warten, dann zweite Geste" (F001): `page.route` verzögert PUTs auf das Objekt (800–900 ms, Muster `hub-save-chip` `verzoegerePuts`); die zweite Geste startet erst nach `await page.waitForRequest(ersterPut)` — kausal, nicht geraten.
- Altes „4000 ms abwarten" (F001): `expect.poll` auf den Server-Stand beider Änderungen.

### Fälle

**`hub-alarme-wertprops.spec.ts` (Erweiterung)**
- **AW-2b (je kind):** Seed **ohne** Auslöser-Feld (`seedHub` ohne `official_warnings` bzw. `radar_alert_enabled`). Reiter Alarme öffnen ⇒ Auslöser zeigt die kind-Vorgabe (route: **an**, vergleich: **aus**, Tabelle „Kind-Kontraste"); `zaehlePuts` bleibt über das Stabilitätsfenster bei 0 (Öffnen speichert nichts); Server-Stand trägt das Feld weiterhin **nicht**.

**`hub-konfliktschutz-zwei-kontexte.spec.ts` (Schärfung, S3c-Zusicherungen bleiben)**
- **KS-2 (je kind):** nach dem Kopf-Umbenennen zusätzlich `page.reload()`, Reiter Alarme öffnen, Auslöser steht auf `AW_SEL[kind].ausloeserNeu` (Anzeige, nicht nur Server-Stand).
- **KS-1 (je kind, je Reiter):** vor „Nochmal speichern" Protokoll der Anfragen auf B starten; danach: (a) der erste Wiederholungs-PUT wurde **nach** einem GET auf `hubApiPath(kind, id)` abgeschickt (Reihenfolge per `request`-Ereignis, Zeitstempel/Index), (b) sein `If-Match` ist gesetzt **und** ungleich dem `If-Match` des abgelehnten ersten PUT.

**`hub-wertebereiche-speichert-selbst.spec.ts` (Erweiterung)**
- **WS-8 (je kind):** `corridor-row-<WS_SEL.zeile>` · Knopf „Markieren" umlegen ⇒ genau ein PUT (`bleibtBei`), Stand `mark` umgekehrt zum Seed, überlebt Neuladen; zusätzlich: in der Zeile **kein** Knopf „Warnen", „Markieren" und „✕ entfernen" sichtbar (#1371).

**`hub-editor-autosave-gesten-gate.spec.ts` (GG, neu)**
- **GG-1 (je kind):** Hub je Reiter öffnen (Punkte-Reiter, Alarme, Wertebereiche, Wetter-Metriken) **ohne jede Geste**; über das Stabilitätsfenster 0 PUT auf `hubApiPath(kind, id)` (und kein PUT auf `…/weather-config` beim Trip); danach auf die Liste navigieren, weiterhin 0 PUT; Server-Stand unverändert (`updated_at`/`etag` gleich).
- **GG-2 (je kind):** Punkte-Geste (Trip: Etappen-Datum + blur; Vergleich: Ort entfernen) und **sofort** `page.goto(HUB_SEL[kind].liste.url)` ohne Warten auf den PUT; `expect.poll` auf den Server-Stand ⇒ Änderung angekommen (kein Datenverlust).
- **GG-3 (je kind):** PUTs auf das Objekt per `page.route` um ~900 ms verzögern; erste Punkte-Geste ausführen, `page.waitForRequest` auf deren PUT, dann **zweite** unabhängige Geste im selben Reiter (Trip: Datum der zweiten Etappe; Vergleich: zweiten von drei Orten entfernen); `expect.poll` ⇒ der Stand trägt **beide** Änderungen (Fehlertext „zweite Änderung während laufendem Speichern ging verloren").
- **GG-4 (je kind):** Punkte-Geste ohne Speichern-Klick ⇒ `waitForResponse` auf den PUT (200), genau ein PUT, Körper enthält **nicht** `name`, trägt das Punkte-Teilfeld (Vergleich `{ location_ids: [verbleibender Ort] }`, Trip `stages` mit neuem Datum — Körperform im RED messen), Stand stimmt.
- **GG-5 (je kind):** Punkte-Geste, danach Reiter Wetter-Metriken · `report-morning-time` 06:00 ⇒ 05:00; nach `bleibtBei` genau **zwei** PUTs insgesamt (kein Doppel-Feuer, `hubPutQueue`); Stand trägt beide Änderungen.

**`hub-metrik-reihenfolge-ziehen.spec.ts` (RO, neu)**
- **RO-1 (je kind):** Seed mit drei aktiven Metriken in fester Reihenfolge (Kennungen laut Tabelle); Reiter Wetter-Metriken, Reihenfolge-Karte (`weather-metrics-vergleich-reihenfolge` bzw. `weather-metrics-kanal-reihenfolge`); `dragDndZoneItem` zieht die dritte Zeile vor die erste (nur ziehen, keine Metrik an-/abwählen); `waitForResponse` auf den PUT (kausal, nicht DOM-Optik), Server-Stand trägt die neue Reihenfolge (Feld je kind im RED gemessen, Entscheidung 8), Neuladen zeigt sie.
- **RO-2 (je kind):** keine Zeile der Reihenfolge-Karte trägt eine Kennung mit `official`/`warn`; nur vergleich: sichtbarer Hinweis `weather-metrics-vergleich-warn-hint` (Text „Amtliche Warnungen … immer an erster Stelle"). Der Trip-Zweig prüft **nur** die Zeilenaussage.

### Löschreihenfolge in /50

1. Neue/erweiterte Specs schreiben; Trip-Fälle im CI-Stack messen (rot ⇒ Produktlücke, AC-16).
2. Dreimal grün (Filter B, Zielverbund), `--list`-Fallzahl gegen Zuordnung abgleichen (AW-2b 2, WS-8 2, GG 10, RO 4 = 18 neue Fälle; Altfälle radar 3).
3. Mutations-Gegenprobe je kind (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`).
4. Erst bei Grün löschen: radar-toggle, editor-autosave, metric-order (+ Setup/Config), feat-1395-s4 (+ Setup/Config); im **selben Commit** `MIGRATED_FILES`, 1273-Config, Wächter, Ratsche.
5. Köpfe setzen (G2/G3), Kommentar-Zeiger umhängen (G4), ALTLAST + `ALTLAST_MAX` gemeinsam 29 → 14.

### Wächter, Ratsche, CI

- **Wächter:** aus `ALTLAST` entfernen (15): `compare-active-metrics-format.staging`, `compare-editor-autosave`, `compare-hourly-metric-order`, `compare-hub-inline-edit`, `compare-metric-order`, `compare-neu-kanal-anlegen.staging`, `compare-outlook-metric-selection.staging`, `compare-radar-toggle`, `compare-stundenverlauf-wertprops`, `compare-uebersicht-kanal-bedienung.staging`, `compare-uebersicht-kanal-persistenz.staging`, `fix-1350-compare-metric-select.staging`, `fix-1350t3-compare-threshold-source.staging`, `issue-682-compare-editor-mobile`, `kanal-grenzen-ortsvergleich.staging`. Übrig 14 (Befund 1). `ALTLAST_MAX` Literal **14** im selben Zug (Wächter prüft `len(ALTLAST) == ALTLAST_MAX`). Selbst-Prüfung: Ein Kopf-Eintrag, der noch in `ALTLAST` steht, ist „inzwischen konform" ⇒ rot (so erzwingt der Wächter die vollständige Streichung).
- **Ratsche (`ci_e2e_specs.txt`):** `e2e/compare-radar-toggle.spec.ts` raus; `e2e/hub-editor-autosave-gesten-gate.spec.ts` und `e2e/hub-metrik-reihenfolge-ziehen.spec.ts` rein (alphabetisch, Aufnahme-Kommentar mit Filter-B-Beleg und #2347 S3d). `E2E_MIN_SPECS` = Ergebnis von `grep -c '^e2e/' .github/ci_e2e_specs.txt` — **erwartet 73** (72 − 1 + 2); verbindlich ist die Zählung. `E2E_MIN_EXECUTED_HAUPT` wird am Endstand per `npx playwright test --list` über die Hauptlauf-Auswahl (Positivliste ohne `bug-703`) **gemessen** (Erwartung nur grob 535 − 3 + 18 = 550, `Total: … tests in 74 files` inkl. `global.setup`); **nie addiert**. Begründungszeile in `ci.yml` um S3d fortschreiben.
- **Hinweis Filter A/B:** Neue Positivlisten-Specs enthalten kein `waitForTimeout`/`skip`/`__dirname`/`.staging`; die Nachweise stehen im Aufnahme-Kommentar.
- **Verweis-Hygiene:** siehe AC-18.

## Expected Behavior

- **Input:** CI-Lauf `e2e` gegen den isolierten Stack; Unit-Läufe des Wächters, der Ratschen-Bindung und des Struktur-Tests.
- **Output:** Autosave-Gesten-Gate, Navigation ohne Datenverlust, Re-Armierung, Punkte-Geste, Wertebereich-Markieren, Metrik-Reihenfolge und Vorgabe des Alarm-Auslösers werden für Trip UND Ortsvergleich durch dieselben Specs geprüft und von der CI bewacht. Compare-eigene Specs tragen einen Kopf mit wahrer Begründung. ALTLAST 14.
- **Side effects:** Wegwerf-Daten `E2E-GZ-…` (Aufräumen im `finally`, Sicherheitsnetz `global.teardown.ts`); keine Registrierung, kein Versand.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Test 1: GIVEN ein Trip bzw. Ortsvergleich ohne gesetzten Alarm-Auslöser WHEN der Reiter Alarme geöffnet wird THEN steht die kind-Vorgabe da und es wird nichts gespeichert (AW-2b).
- [ ] Test 2: GIVEN ein Hub WHEN der Name im Kopf geändert und neu geladen wird THEN steht der Auslöser weiter auf dem gesetzten Wert (KS-2 geschärft).
- [ ] Test 3: GIVEN ein Korridor WHEN „Markieren" umgelegt wird THEN genau ein PUT, Stand umgekehrt, kein „Warnen" (WS-8).
- [ ] Test 4: GIVEN ein Hub WHEN er ohne Geste geöffnet und verlassen wird THEN null PUT (GG-1); WHEN eine Geste und sofort Navigation THEN kein Datenverlust (GG-2); WHEN zwei Gesten bei langsamem Speichern THEN beide landen (GG-3); WHEN Punkte-Geste THEN ein Teilfeld-PUT (GG-4); WHEN zwei Aktionen THEN genau zwei PUTs (GG-5).
- [ ] Test 5: GIVEN drei aktive Metriken WHEN eine gezogen wird THEN speichert der Hub die neue Reihenfolge und sie überlebt das Neuladen, je kind (RO-1/RO-2).
- [ ] Test 6: GIVEN die geschärfte KS-1 WHEN der Wiederholungs-PUT läuft THEN ging ein GET voraus und `If-Match` ist frisch.
- [ ] Test 7: GIVEN der Wächter WHEN er läuft THEN hat `ALTLAST` 14 Einträge und `ALTLAST_MAX` ist 14.
- [ ] Test 8: GIVEN die Positivliste WHEN der Bindungstest läuft THEN entspricht `E2E_MIN_SPECS` der Listenlänge.
- [ ] Test 9: GIVEN der Struktur-Test WHEN er läuft THEN ist er grün ohne `compare-radar-toggle`.

## Acceptance Criteria

- **AC-1:** (G1, Vorgabe des Alarm-Auslösers) Given ein Wegwerf-Trip und ein Wegwerf-Ortsvergleich, beide **ohne** gesetztes Auslöser-Feld (Amtliche Warnungen bzw. Radar-Alarm) / When der Reiter Alarme geöffnet wird / Then zeigt der Trip den Auslöser „Amtliche Warnungen" **an** und der Ortsvergleich den Radar-Alarm **aus**, das Öffnen löst keinen Speicher-Aufruf aus, und der gespeicherte Stand enthält das Feld weiterhin nicht — für Trip UND Ortsvergleich.
  - Test: `hub-alarme-wertprops.spec.ts` (AW-2b, 2 Fälle).
  - Mutation (je kind getrennt): Vorgabe im Reiter umdrehen (Trip `?? true` auf `?? false` in `AlarmeTab.svelte:218-220`; Vergleich Radar-Vorgabe auf an) → AW-2b des kind rot; Reiter speichert beim Öffnen → AW-2b rot (PUT-Zähler > 0).
- **AC-2:** (G1, Anzeige nach fremdem Speichern) Given ein Hub, in dem der Alarm-Auslöser per Geste umgelegt und gespeichert wurde / When anschließend nur der Name im Kopf geändert und die Seite neu geladen wird / Then trägt der Kopf-Aufruf genau `{ name }`, der Server-Stand den neuen Namen **und** den umgelegten Auslöser, und der Schalter im Reiter Alarme zeigt nach dem Neuladen den umgelegten Wert — für Trip UND Ortsvergleich. Die Datei `compare-radar-toggle.spec.ts` wird erst nach grünem Lauf gelöscht und alle drei Altfälle sind laut Zuordnung gedeckt.
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-2 geschärft, 2 Fälle), `hub-alarme-wertprops.spec.ts` (AW-2).
  - Mutation: Kopf-Edit sendet das Vollobjekt aus der alten Baseline (Auslöser zurückgesetzt) → KS-2 des kind rot; Reiter liest nach dem Neuladen den Vorgabewert statt des Standes → KS-2 des kind rot (Anzeige).
- **AC-3:** (G1, Markieren im Wertebereich) Given ein Trip und ein Ortsvergleich mit je einer Wertebereich-Zeile / When „Markieren" umgelegt wird / Then entsteht genau ein Speicher-Aufruf, der Stand trägt `mark` umgekehrt zum Ausgangswert und überlebt das Neuladen, in der Zeile gibt es **keinen** Knopf „Warnen", „Markieren" und „✕ entfernen" sind sichtbar — für Trip UND Ortsvergleich.
  - Test: `hub-wertebereiche-speichert-selbst.spec.ts` (WS-8, 2 Fälle).
  - Mutation: Rückruf `onChange` des Markieren-Knopfs am Mount weglassen → WS-8 des kind rot (kein PUT); „Warnen"-Knopf wieder einblenden → WS-8 rot.
- **AC-4:** (G1, Gesten-Gate) Given ein Trip und ein Ortsvergleich / When der Hub nacheinander in allen Reitern (Etappen bzw. Orte, Alarme, Wertebereiche, Wetter-Metriken) **ohne jede Geste** geöffnet und danach zur Liste verlassen wird / Then geht in der gesamten Zeit (Stabilitätsfenster, kein fester Schlaf) kein Speicher-Aufruf auf das Objekt (beim Trip auch nicht auf `…/weather-config`) hinaus, und der gespeicherte Stand bleibt unverändert.
  - Test: `hub-editor-autosave-gesten-gate.spec.ts` (GG-1, 2 Fälle).
  - Mutation (je kind getrennt): Hydrations-Effekt eines geteilten Reiters speichert ohne Nutzergeste (Gesten-Gate entfernen bzw. Dual-Write im `CorridorEditor` provozieren) → GG-1 des kind rot (PUT ohne Geste).
- **AC-5:** (G1, Navigation ohne Datenverlust) Given ein Trip und ein Ortsvergleich / When eine Punkte-Geste (Etappen-Datum + blur bzw. Ort entfernen) ausgeführt und **sofort** zur Liste navigiert wird, ohne auf den Speicher-Aufruf zu warten / Then steht die Änderung kurz danach auf dem Server (Polling), nichts geht verloren — für Trip UND Ortsvergleich.
  - Test: `hub-editor-autosave-gesten-gate.spec.ts` (GG-2, 2 Fälle).
  - Mutation: Navigation bricht den laufenden Speichervorgang ab bzw. das Flush vor dem Verlassen entfällt → GG-2 des kind rot.
- **AC-6:** (G1, Änderung während laufendem Speichern) Given ein Trip mit zwei Etappen und ein Ortsvergleich mit drei Orten, deren Speicher-Aufrufe künstlich um ca. 900 ms verzögert sind / When eine Punkte-Geste ausgeführt und, sobald ihr Speicher-Aufruf unterwegs ist, eine zweite unabhängige Geste im selben Reiter ausgeführt wird / Then landen **beide** Änderungen auf dem Server (kein stilles Verlieren der zweiten, Lehre F001) — für Trip UND Ortsvergleich.
  - Test: `hub-editor-autosave-gesten-gate.spec.ts` (GG-3, 2 Fälle).
  - Mutation: die Schreib-Warteschlange `hubPutQueue` verwirft einen zweiten Auftrag, solange der erste läuft → GG-3 des kind rot.
- **AC-7:** (G1, Punkte-Geste und zwei Aktionen) Given ein Trip und ein Ortsvergleich / When eine Punkte-Geste ohne Speichern-Klick ausgeführt wird / Then antwortet genau ein Speicher-Aufruf mit 200, dessen Körper kein `name` und das Punkte-Teilfeld trägt (Vergleich `{ location_ids }`, Trip `stages`), und der Stand stimmt; wenn danach im Reiter Wetter-Metriken die Morgen-Uhrzeit 06:00 → 05:00 geändert wird / Then sind es insgesamt **genau zwei** Speicher-Aufrufe (kein Doppel-Feuer) und der Stand trägt beide Änderungen — für Trip UND Ortsvergleich.
  - Test: `hub-editor-autosave-gesten-gate.spec.ts` (GG-4 und GG-5, 4 Fälle).
  - Mutation: Punkte-Gesten senden das Vollobjekt → GG-4 des kind rot (Körper trägt `name`); jede Geste feuert zweimal → GG-5 des kind rot (Zähler 3 statt 2).
- **AC-8:** (G1, Metrik-Reihenfolge) Given ein Trip und ein Ortsvergleich mit drei aktiven Metriken in fester Reihenfolge / When im Reiter Wetter-Metriken eine Zeile per Ziehen an eine andere Position gesetzt wird (keine Metrik an- oder abgewählt) / Then speichert der Hub (ein Speicher-Aufruf, abgewartet über die Antwort, nicht über die Bildschirm-Optik), der Server trägt die neue Reihenfolge im kind-eigenen Feld, und nach dem Neuladen zeigt die Karte sie unverändert; keine der Zeilen ist eine Kennung für „Amtliche Warnungen", und im Ortsvergleich erklärt der Hinweis, dass Amtliche Warnungen immer zuerst kommen — für Trip UND Ortsvergleich (Hinweis nur Vergleich, Begründung in „Kind-Kontraste"). Die veraltete Vorbedingung „keine Aus-Gruppe im Ortsvergleich" entfällt (Entscheidung 7).
  - Test: `hub-metrik-reihenfolge-ziehen.spec.ts` (RO-1 und RO-2, 4 Fälle).
  - Mutation (je kind getrennt): Ziehen ruft den Speicherweg nicht auf (Trip `scheduleAutoSave` in `onDndReorder` entfernen; Vergleich `onCompareDndReorder` ohne Commit, bzw. Diff-Guard wertet reine Umsortierung als „keine Änderung") → RO-1 des kind rot; Server speichert die alte Reihenfolge → RO-1 rot (Reload).
- **AC-9:** (G1, Löschungen im selben Commit) Given grüne Specs aus AC-1 bis AC-8 / When `compare-radar-toggle.spec.ts`, `compare-editor-autosave.spec.ts` und `compare-metric-order.spec.ts` samt `compare-metric-order.staging.setup.ts` und `playwright.compare-metric-order.staging.config.ts` gelöscht werden / Then stehen im **selben** Commit: `compare-radar-toggle.spec.ts` ist aus `MIGRATED_FILES` entfernt (Kommentar nach Muster S3b), die Einträge `compare-editor-autosave` und `compare-radar-toggle` sind aus `playwright.1273-s4c.staging.config.ts` entfernt, die Positivliste ist angepasst, und `tests/tdd/test_compare_e2e_storagestate_migration.py` ist grün; jede Zeile der Zuordnungstabellen ist durch einen laufenden Fall belegt.
  - Test: `tests/tdd/test_compare_e2e_storagestate_migration.py` (benannte Datei), Zuordnungs-Abgleich im Adversary-Protokoll.
  - Mutation: `compare-radar-toggle` in `MIGRATED_FILES` stehen lassen → Struktur-Test rot (Datei fehlt); Config-Eintrag stehen lassen → Struktur-Test bzw. Config-Prüfung rot.
- **AC-10:** (G2, Köpfe auf Specs mit Positivlisten- oder Hub-Bezug) Given `compare-stundenverlauf-wertprops`, `compare-hourly-metric-order`, `issue-682-compare-editor-mobile` und `compare-hub-inline-edit` / When der Wächter läuft / Then trägt jede Datei in den ersten 30 Zeilen `gz-eigenstaendig:` mit einer Begründung von mindestens 15 Zeichen, die laut Tabelle „Köpfe" **wahr** ist (Stundenverlauf nur im Vergleich laut `COMPARE_ONLY_SECTIONS`; Mobil-Shell des Alt-Editors mit Trip-Pendant `issue-661-trip-new-mobile`; nur Orte-Tab übrig); alle ihre Fälle bleiben unverändert erhalten und die drei Dateien auf der Positivliste bleiben dort. In `compare-hourly-metric-order.spec.ts` wird die tote Vorbedingung `wm2-aus-gruppe` = 0 (seit #1703 S8 gilt „Aus ist ein Zustand" auch im Vergleich) entfernt; die Fälle behalten ihre Zeilenprüfung im Stundenverlauf-Block.
  - Test: Wächter `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei); `--list` zeigt unveränderte Fallzahlen (4, 3, 6, 3).
  - Mutation: Kopf entfernen → Wächter rot (Regel 1); Begründung auf weniger als 15 Zeichen kürzen → Wächter rot („Zeichen Begruendung").
- **AC-11:** (G3, Köpfe auf `.staging`-Specs) Given die acht `.staging`-Specs `compare-active-metrics-format`, `compare-neu-kanal-anlegen`, `compare-outlook-metric-selection`, `compare-uebersicht-kanal-bedienung`, `compare-uebersicht-kanal-persistenz`, `fix-1350-compare-metric-select`, `fix-1350t3-compare-threshold-source`, `kanal-grenzen-ortsvergleich` / When der Wächter läuft / Then trägt jede einen `gz-eigenstaendig:`-Kopf mit wahrer Begründung und benanntem Trip-Pendant laut Tabelle „Köpfe" („läuft nur auf Staging" ist kein zulässiger Grund); `kanal-grenzen-ortsvergleich` nennt die drei SMS-Grenzen (Vergleichs-Briefing 153, Trip-Briefing 160, Alarm 140) mit Fundstellen; **keine** der acht wird gelöscht, weil die Zuordnung nicht vollständig ist (Entscheidung 6).
  - Test: Wächter (benannte Datei); manueller Abgleich der Begründungen mit den Fundstellen im Adversary-Protokoll.
  - Mutation: Kopf von `kanal-grenzen-ortsvergleich` entfernen → Wächter rot (Regel 2); Kopf von `compare-outlook-metric-selection.staging.spec.ts` entfernen → Wächter rot (Regel 1).
- **AC-12:** (G3, Trip-412-Retry ohne Staging-Spec) Given der Trip im Reiter Alarme in zwei Kontexten / When A den Namen ändert, B danach speichert (412) und „Nochmal speichern" wählt / Then geht dem Wiederholungs-Aufruf von B ein GET auf das Objekt voraus, der Wiederholungs-Aufruf trägt einen `If-Match`, der gesetzt und vom `If-Match` des abgelehnten Aufrufs verschieden ist, und die übrigen Zusicherungen aus S3c (Chip `conflict`, Wiederholung 200, kein `name` im Körper, Name von A bleibt) gelten unverändert — für Trip UND Ortsvergleich. Danach werden `feat-1395-s4-conflict-retry.staging.spec.ts`, ihr `.staging.setup.ts` und `e2e/playwright.feat-1395-s4.staging.config.ts` gelöscht.
  - Test: `hub-konfliktschutz-zwei-kontexte.spec.ts` (KS-1 geschärft, 8 Fälle), Kerntest `saveStatusConflictRetry.test.ts` (unverändert).
  - Mutation: „Nochmal speichern" wiederholt ohne vorherigen GET und mit dem alten Stempel → KS-1 des kind rot (Wiederholung bleibt 412 bzw. `If-Match` gleich); Refresh nach dem Retry statt davor → KS-1 rot (Reihenfolge).
- **AC-13:** (G4, Wächter) Given der Paritäts-Wächter / When der Unit-Test läuft / Then enthält `ALTLAST` **14** Einträge (die 15 S3d-Einträge der Liste unter „Wächter" entfernt; weder neue Dateien noch Kopf-Dateien stehen drin), `ALTLAST_MAX` ist das Literal **14**, die Docstring-Messzeile nennt S3d, und die Selbsttests bleiben grün.
  - Test: `tests/unit/test_e2e_compare_paritaet_waechter.py` (benannte Datei).
  - Mutation: gelöschten Dateinamen in `ALTLAST` stehen lassen → „zeigt auf keine Datei mehr" rot; Kopf-Datei in `ALTLAST` lassen → „inzwischen konform" rot; `ALTLAST_MAX` auf 29 lassen → rot.
- **AC-14:** (G4, Ratsche) Given die CI-Ampel / When die Ratsche geprüft wird / Then enthält `.github/ci_e2e_specs.txt` `hub-editor-autosave-gesten-gate` und `hub-metrik-reihenfolge-ziehen` und nicht mehr `compare-radar-toggle`, `E2E_MIN_SPECS` entspricht **exakt** dem Ergebnis von `grep -c '^e2e/' .github/ci_e2e_specs.txt` (erwartet 73, nicht errechnet), `E2E_MIN_EXECUTED_HAUPT` ist der am Endstand per `npx playwright test --list` über die Hauptlauf-Auswahl gemessene Wert (Erwartung ca. 550, nie addiert) mit fortgeschriebener Begründung, jede Listenzeile verweist auf eine vorhandene Datei.
  - Test: `tests/unit/test_e2e_positivliste_ratschen_bindung.py`, CI-Job `e2e` (`e2e_gate.py`).
  - Mutation: Zeile auf nicht existierende Datei → Existenzprüfung rot; `E2E_MIN_SPECS` um 1 verfälschen → Kern-Test rot; `E2E_MIN_EXECUTED_HAUPT` um 1 verändern → `e2e_gate.py` rot.
- **AC-15:** (Qualität der neuen Specs) Given die zwei neuen und die erweiterten Specs / When sie im Zielverbund (Hauptlauf ohne `bug-703`) dreimal hintereinander laufen / Then sind alle drei Läufe grün (Filter B, im Aufnahme-Kommentar belegt); die Specs enthalten kein `waitForTimeout`, kein `skip`/`test.fixme`, kein `page.screenshot({path})`, keinen Hauptrepo-Pfad, kein `__dirname`, keinen festen `storageState`-Pfad und kein UI-`login()`; es gibt keine Registrierung (Bremse 5/h/IP unberührt), jeder Fall räumt sein Objekt auf (`finally`), höchstens ein aktiver Vergleich je Fall (kein 409), `global.teardown.ts` meldet keinen Restbestand `E2E-GZ-`.
  - Test: Filter B (3 Zyklen) + `grep -c "waitForTimeout\|\.skip(\|test\.fixme\|__dirname" frontend/e2e/hub-editor-autosave-gesten-gate.spec.ts frontend/e2e/hub-metrik-reihenfolge-ziehen.spec.ts` = 0.
  - Mutation: `waitForTimeout` einfügen → Filter-A-Prüfung rot; `finally`-Aufräumen entfernen → Folgefall scheitert mit 409.
- **AC-16:** (Produktlücke im selben Ticket) Given ein Fall der neuen Specs (GG, RO, WS-8, AW-2b, geschärfte KS) wird für den Trip rot, obwohl er für den Ortsvergleich grün ist / When die Ursache untersucht wird / Then wird die Produktlücke im **selben** Ticket (#2347) behoben und der Test bleibt streng; Abschwächen, `test.skip`, ein kind-Zweig, der nur eine Art prüft, oder ein „bekannte Abweichung"-Vermerk sind unzulässig. Berührte Produktdateien werden in diese Spec nachgetragen, das LoC-Limit wird bei Bedarf per `loc_limit_override` angehoben. Erwartete Messpunkte: Zielfeld und Schreibweg des Ziehens beim Trip (RO-1), Teilfeld-Körper der Etappen-Geste (GG-4), Verzögerungs-Verhalten der Schreib-Warteschlange (GG-3).
  - Test: Prozess-AC; Beleg im Adversary-Protokoll („rot beim Zusammenführen: ja/nein, wenn ja: Fix-Commit").
  - Mutation: keine (Regel).
- **AC-17:** (Mutations-Gegenprobe, übergreifend) Given jedes zusammengeführte oder neue Verhalten aus AC-1 bis AC-8 und AC-12 / When die Implementierung gezielt verfälscht wird (Sicherungskopie extern, nur String-Ersetzung, nie `git checkout/stash/reset`) / Then wird für **jedes** Verhalten und **beide** kinds der jeweils betroffene Fall rot, und protokolliert wird, **welcher** Test rot wurde (nicht nur, dass einer rot wurde); eine Verfälschung, die kein Test fängt, ist ein Finding; eine kind-spezifische Verfälschung macht nur den Fall dieser Art rot. Zusätzlich die Ausfallprobe der Zuordnung: ein weggelassener Fall wird vom `--list`-Abgleich (AW-2b 2 + WS-8 2 + GG 10 + RO 4 = 18 neue Fälle gegen die Zuordnungstabellen) gemeldet, und keine Altdatei wird vor dem grünen Lauf gelöscht.
  - Test: Adversary-Dialog in `/50` (Familien: Vorgabe-Wert, Gesten-Gate, Navigation/Flush, Schreib-Warteschlange, Teilfeld-Körper, Zähler, Selektor je kind, Ziehen-Speicherweg, Stempel/Reihenfolge).
  - Mutation: siehe die Mutationszeilen in AC-1 bis AC-12.
- **AC-18:** (Verweis-Hygiene) Given alle gelöschten Dateien / When `grep -rn` über `frontend`, `.github`, `tests`, `scripts` nach `compare-radar-toggle`, `compare-editor-autosave`, `compare-metric-order`, `feat-1395-s4-conflict-retry`, `playwright.feat-1395-s4` läuft / Then bleibt kein Treffer außer Historie in `docs/` und in der Positivlisten-Historie; Kommentar-Zeiger (`compare-layout-tab-dissolution.spec.ts:39`, `playwright.compare-layout-tab-dissolution.staging.config.ts:5`, `save-status-indicator-honesty.spec.ts:12`, `hub-versand-speichert-selbst.spec.ts:8,467`, Kommentare in `ci_e2e_specs.txt`) sind auf die ersetzenden Specs umgehängt, nicht gelöscht; `docs/reference/gates_und_ratschen.md` nennt „S3d: 14".
  - Test: `grep`-Prüfung im Adversary-Protokoll; Struktur-Tests (AC-9, AC-13, AC-14).
  - Mutation: einen Zeiger auf eine gelöschte Datei in einer Positivlisten-Zeile lassen → Existenzprüfung rot.

## Definition of Done

- [ ] AC-1 bis AC-18 per Test und Mutations-Gegenprobe belegt (je Mutation protokolliert, welcher Test rot wurde)
- [ ] Neue/erweiterte Specs dreimal grün gegen den CI-Stack; Altdateien erst danach gelöscht
- [ ] Zuordnungstabellen gegen `--list` der Altdateien vollständig (radar 3, autosave 10, metric-order 2, feat-1395-s4 2)
- [ ] Zwölf Köpfe gesetzt, Begründungen gegen Fundstellen geprüft; `compare-hourly-metric-order` ohne tote Vorbedingung
- [ ] `ALTLAST`/`ALTLAST_MAX` auf 14, Wächter-Test grün
- [ ] `E2E_MIN_SPECS` per Zählung, `E2E_MIN_EXECUTED_HAUPT` per `--list` gemessen, Positivliste konsistent
- [ ] Struktur-Test, 1273-Config, Kommentar-Zeiger bereinigt
- [ ] CI-Ampel (6 Checks) grün, kein Produktcode geändert (oder Produktlücke nach AC-16 dokumentiert)

## Known Limitations

- Zielfeld und Schreibweg des Ziehens beim Trip (`display_config.metrics[].order` vs. kanal-eigener Eintrag, PUT `…/weather-config`) sowie der Körper der Etappen-Geste sind erst im RED messbar; die Spec legt die Zusicherung fest, nicht das Messergebnis.
- Pointer-Drag (RO-1) kann in CI flackern; er wird über die abgewartete Antwort und nicht über DOM-Optik abgesichert. Bleibt er trotz Härtung nicht dreimal grün, wird die Ursache behoben (AC-16), nicht der Fall aus der Positivliste gelassen.
- Die acht `.staging`-Specs laufen weiterhin nur gegen Staging (Basic-Auth, Admin-/Datenzugriffs-Fallen); ihre Mutations-Gegenprobe ist im CI-Stack nicht prüfbar. Ihr Kopf dokumentiert den Pendant-Befund und ist keine Aussage über deren Lauffähigkeit.
- `compare-hourly-metric-order` und `compare-stundenverlauf-wertprops` bleiben compare-eigen, solange die Stundenverlauf-Steuerung nur im Ortsvergleich existiert (Produktentscheidung #2346 S3). Ändert sich diese Entscheidung, ist eine kind-Schleife neu zu spezifizieren.
- Die Mobil-Spec 682 und die Anlege-Seiten-Specs hängen am Alt-Editor `/compare/new`, der mit Etappe P7 ersatzlos fällt; die Köpfe sagen das, die Specs werden in P7 mit ihm entfernt bzw. auf die neue Anlege-Seite umgestellt.
- `E2E_MIN_EXECUTED_HAUPT` ist erst am Endstand messbar; die Rechnung 550 ist nur Erwartung.
- `feat-1395-s3-etag-ifmatch.staging.spec.ts` (Trip) ist nicht Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testschicht-Konsolidierung nach bestehender Vorgabe (Trip/Ortsvergleich-Code-Teilung, Epic #2345 P6); keine neue Entscheidungsfläche.

## Changelog

- 2026-10-29: Initial spec created (S3d, compare-eigener Rest). Entscheidungen am Code: Übersichts-Metrik-Reihenfolge ist geteilt (`WeatherV2Reihenfolge`, beide Kontexte) ⇒ kind-parametrisiert (RO) statt Kopf; Stundenverlauf ist Vergleich-only (`COMPARE_ONLY_SECTIONS`) ⇒ Köpfe, und `compare-stundenverlauf-wertprops` wird **nicht** gelöscht (kein MS-Fall deckt `hourly_metrics`); Radar-Fälle ⇒ AW-2b (Vorgabe) + KS-2 geschärft; Autosave-Fälle ⇒ GG (Trip-Entsprechung Etappen-Reiter) + WS-8; `feat-1395-s4` ⇒ KS-1 geschärft (GET vor Retry, frischer `If-Match`), dann gelöscht; acht `.staging`-Specs ⇒ Köpfe mit wahrer Begründung; veraltete Vorbedingung `wm2-aus-gruppe` = 0 entfernt; ALTLAST 29 → 14, `E2E_MIN_SPECS` erwartet 73 (per Zählung), HAUPT per `--list`.
