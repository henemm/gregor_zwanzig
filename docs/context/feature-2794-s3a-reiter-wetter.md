# Context: feature-2794-s3a-reiter-wetter (Epic #2791, Scheibe S3a)

## Request Summary
Der Hub von Trip und Orten bekommt nach ADR-0109 die Reiter Übersicht · Etappen/Orte · Wetter · Zustellung. S3a baut den Reiter **Wetter** (Vorlage-Karte, Speichern-Dialog, „Alarm ab für alle“, Metrik-Zeilen mit Ampel-Leiste und „Grenzen ändern“, „Nicht im Briefing“, Amtliche Warnungen & Radar, Anpassen/Tagesfenster) und die Reiterleiste nach Atomic-Design-Soll, entfernt Wertebereiche/Alarme/Layout, leitet alte Links um. Ohne „Inhalt je Kanal und Fläche“ (S3b).
Quellen: Issue #2794 (Umfang 1–12, Abgleich-Tabelle mit PO-Entscheidungen), `docs/context/einstellungen_neu.md` §4–§8, Mockup `docs/context/einstellungen_neu/seiten/mockup-hub-fassung3.html`.

## Ist-Lage (gemessen gegen `origin/main` @ b48afb378, 2026-11-08)

**Korrekturen an Annahmen im Issue:**
- Einen Reiter „Layout“ gibt es nicht mehr. Heutige Reiter: `uebersicht`, `etappen`|`orte`, `wetter-metriken`, `wertebereiche`, `alarme`. Der Versand steht unten im Reiter Wetter-Metriken (`#versand`); Layout (`layout-tab/LayoutTab.svelte`) ist in `shared/WeatherMetricsTab.svelte:46,1553` eingebettet.
- `AlertsTab`, `AlertPresetSelector`, `AlertCard` sind schon entfernt (#1895 S4). Der Ordner `alerts-tab/` ist **nicht** tot: `AlertPreviewCard`, `AlertMetricLevelTable`, `AlertMetricChannelsBlock`, `AlertCooldownCard`, `AlertQuietHoursCard` werden von `AlarmeTab` importiert.
- `CorridorEditor` ist seit #2792 S1c-3 fest „nur lesen“ (`CorridorEditor.svelte:287,428`).
- Kein UI-Element schreibt heute `alarm_ab`; der Frontend-Typ kennt `ampel` nur als `Record<string, unknown>` (`frontend/src/lib/types.ts:369`), `DisplayConfig` (:327) hat kein `ampel`-Feld.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts:39-61,82,87,115-126,134,166` | EINZIGE Reiter-Definition (`REITER_DEFINITION`), Hub-Leiste UND Anlege-Kette (/trips/new, /compare/new), `LEGACY`-Umleitungen, `resolveTab`, `bereinigteTabAdresse` |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:60-66,93-95,115-119,164,176,191-220` | Trip-Hub: Badges (etappen, wertebereiche = aktive `alert_rules`), `?tab=`, Speicher-Schutz, Panels |
| `frontend/src/lib/components/compare/CompareTabs.svelte:131-158,187,679,778,807-837` | Vergleichs-Hub, Badge orte, Panels |
| `frontend/src/routes/compare/[id]/+page.svelte:211` | reicht `?tab` durch |
| `frontend/src/lib/components/mobile/MTabBar.svelte:82,101` | Reiterleiste Desktop+mobil, `data-slot="segmented"`/`segmented-badge` → erbt `app.css:502-528` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (1014-1018, 1136, 1428, 1467ff, 1597, 1714, 1815, 2049, 1672) | heutiger Reiter Wetter-Metriken: Speichern (PUT `/api/trips/{id}/weather-config`, dann PUT `/api/trips/{id}`), Amtl.-Warnungen-Bericht-Schalter, Vergleichszweig ohne Vorlagen, DayWindowCard, `WeatherV2PresetBar` nur Trip |
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte:53,54,119,122,135,205-223` | Name, Beschreibung, Zusammenfassung, Zeithorizonte, `is_default`, POST `/api/metric-presets`, `name_exists`; schickt **keine** `ampel` |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsSavePayload.ts:98` | `ampelBeimAnwenden` |
| `frontend/src/lib/components/shared/weather-metrics-tab/DayWindowCard.svelte`, `versand-tab/dayWindowClamp.ts` | Tagesfenster (ADR-0035) |
| `frontend/src/lib/components/shared/corridor-editor/` | Reiter Wertebereiche (entfällt) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte:34-38,514-522,605,608`, `alarme-tab/alarmeTabSections.ts`, `alarme-tab/alarmeDeliveryPayload.ts:85-128`, `shared/alarmeVergleichSpeicherung.ts:144ff`, `trip-detail/AlarmeScheduleTab.svelte` | Reiter Alarme (entfällt): Abschnitte official-warnings, radar (nur Vergleich), metric-levels, channels, cooldown, quiet-hours, sample |
| `frontend/src/lib/components/shared/hub-uebersicht/hubUebersichtModell.ts:131,252-260`, `HubUebersicht.svelte:140,163`, `trip-detail/HubOverview.svelte:150` | Übersicht: Karte Wertebereiche (U3), „Alarm bei Δ“ (U4) |
| `frontend/src/lib/components/shared/subscriptionActions.ts:18,40,74,78`, `routes/trips/+page.svelte:109`, `routes/compare/+page.svelte:125`, `routes/+page.svelte:367,470`, `shared/infoboxKeys.ts`, `routes/hilfe/+page.svelte:43-45` | Listen-Eintrag „Alarme“, Sprünge auf alte Reiter (K17, X1) |
| `frontend/src/lib/i18n/messages/{de,en}/*.json` (layout.json:20, hilfe.json:5-7, alarme.json:31, bausteine.json:4-7,15,20,101, vergleich.json:110-111,120, trip.json:174,270-272, aktionen.json:12,27) | Texte mit Verweisen auf alte Reiter; Reiternamen |
| `docs/reference/i18n_glossar.md:17-19` | Glossar (Wertebereiche = target ranges) |
| `src/app/ampel.py:26-33,92,142-151,176,245,260` | Ampel-Modell: validate, Rückfallkette template→preset_name→profil→allgemein, resolve, `deviation_count` (zählt `alarm_ab`/`enabled` NICHT), `thunder_color` |
| `src/app/ampel_templates.py:24-183,202` | 7 Vorlagen mit Grenzen (nur Python), Windrichtung :33 offen/never, Gewitter :182-183 |
| `api/routers/config.py:25-36,110-168` | `/api/templates`, `/api/metrics` (liefert unit, category, aggregations; KEIN `is_precursor`, keine Gruppe, kein „nur Anzeige“) |
| `src/app/metric_catalog.py:29-100,92,515,1296` | `MetricDefinition` (category nur temperature/wind/precipitation/atmosphere/winter, `is_precursor`, `alert_metrics`), CAPE, alte `WEATHER_TEMPLATES` |
| `internal/handler/ampel.go:13-20,93` + Aufrufer `trip.go:199,379`, `weather_config.go:98`, `metric_preset.go:152,274`, `briefing_subscription.go:262` | Go-Validierung der Ampel |
| `internal/model/metric_preset.go:5-21,31-42`, `internal/store/metric_preset.go:16`, `internal/router/router.go:235,238,287-290` | eigene Vorlagen, Store `data/users/<id>/metric_presets.json`, `horizons` je Metrik |
| `internal/model/compare_preset.go:26,60,151` | `profil`, `radar_alert_enabled`, Tagesfenster Vergleich |
| `scripts/migrate_2793_alarm_ab.py` | S2-Migration `alarm_ab` |
| `frontend/src/lib/components/molecules/HorizonChips.svelte`, `trip-detail/MetricCheckbox.svelte` | tot (nur Barrel-Exporte + Prüfstand-Tests) |

## Existing Patterns
- Eine Reiter-Quelle (`REITER_DEFINITION`) für Hub und Anlege-Kette; Umleitung alter Kennungen über `LEGACY` + `bereinigteTabAdresse` (Test `hub-reiter-alt-kennungen-umleitung`).
- Trip/Vergleich teilen Komponenten mit `context="route"|"vergleich"` (`shared/`), Pflicht nach CLAUDE.md (#1170).
- Ampel-Daten: Abo speichert nur Abweichungen in `display_config.ampel.metrics`, Rest kommt aus der Vorlage (`resolve`).
- Texte nur über `$t`/`tr`, Wächter `keine_hartkodierten_nutzertexte.test.ts`.

## Dependencies
- Upstream: S1 (#2792, geschlossen, Ampel-Modell), **S2 (#2793, offen)**: `alarm_ab`; Auslieferung S2b läuft in Sitzung `deliver-2860-alarm-ab-migration` (Phase 6b). Migration Staging+Prod ist gelaufen.
- Downstream: S3b (#2795, Zustellung + Inhalt je Kanal), S4 (#2796), S7 (#2799), S8 (#2800, Radar-Trip-Schalter im Reiter Wetter).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md`, `feat_2793_s2_alarm_stufenwechsel.md`
- `docs/specs/modules/mobile_tab_leisten_mtabbar.md` (mobile Pill-Leiste bleibt)
- `docs/specs/modules/feat_1743_reiter_aufraeumen.md` (letzter Reiter-Umbau)
- ADR-0106 (akzeptiert), ADR-0109 (**Vorgeschlagen**), ADR-0097 Punkt 1, ADR-0035, ADR-0104

## Risks & Considerations
1. **Schnitt-Lücke Alarme/Versand ↔ Zustellung (S3b):** S3a entfernt den Reiter Alarme, aber Kanäle, Dringlichkeit je Kanal, Stille Stunden, Cooldown, Test-Alarm und der Versand (heute in Wetter-Metriken) landen erst mit S3b im Reiter Zustellung. Umleitung `?tab=alarme`/`versand` → Zustellung setzt einen Reiter Zustellung voraus. Analyse muss klären: Zustellung in S3a als Übergangsreiter mit den heutigen Bausteinen (Alarm-Kanäle, Cooldown, Stille Stunden, Versand) oder Alarme-Reiter bis S3b behalten. Kein Bedienelement darf zwischen S3a und S3b verschwinden (Abgleich-Inventar).
2. **ADR-0109 nur „Vorgeschlagen“:** laut Epic vor S3a mit dem PO annehmen (AskUserQuestion).
3. **S2 noch nicht ausgeliefert:** Implementierung erst nach Merge S2b (Rebase-Gate). Offene Frage aus #2794-Kommentar: Gate „aktive Alarmquelle“ (`trip_alert.py:686-700`, `:1187-1219`) prüft weiter `metric_alert_levels`/Preset/Regeln; ein Abo nur mit `alarm_ab` wird übersprungen. Wenn das UI künftig nur `alarm_ab` schreibt, muss das Gate `alarm_ab` als Alarmquelle anerkennen, sonst stellt die neue Oberfläche Alarme ein, die nie kommen.
4. **Katalog-Lücke:** Gruppe (5 UI-Gruppen), alarmfähig, Vorbote, erlaubte Seiten, „nur Anzeige“ stehen nicht im API-Katalog; Gruppen nur im Konzept-Dokument. Braucht Backend-Erweiterung (`/api/metrics` oder `/api/templates`), keine Frontend-Kopie (SSOT).
5. **Abweichungs-Zähler:** `deviation_count` zählt `alarm_ab` und `enabled` nicht; Issue verlangt, dass −, +, Grenze, Alarm ab, Gewitterfarbe zählen. Python-Logik oder neue Zählung nötig, eine Quelle für Picker und Dialog.
6. **Eigene Vorlagen:** Dialog schickt keine `ampel`; Vergleich hat gar keine Vorlagen (WV4 neu). Duplikat-Prüfung muss auch gegen die 7 Systemvorlagen und ohne Groß-/Kleinschreibung laufen (Go-Handler). `horizons`-Altwerte: Migration auf „alle Tage“ ist laut W5b PO-Entscheidung → Daten-Schema-Rework mit Pre-Snapshot, Read-Modify-Write.
7. **Amtliche Warnungen zusammenlegen:** zwei Felder (`official_alerts_enabled` Bericht, `official_warnings.enabled` Alarm) → ein Schalter; Semantik beim Lesen alter, auseinanderlaufender Werte festlegen.
8. **Testlast:** ~54 Node-Testdateien und ~38 Playwright-Dateien nennen die alten Reiter; Anlege-Kette (/trips/new, /compare/new) hängt an derselben Definition.
9. **Größe:** Umfang sprengt einen PR deutlich → Schnitt in Teil-PRs (z. B. Backend-Katalog+Zähler, Reiterleiste+Umleitungen, Reiter Wetter, Entfernen+Texte).
10. Multi-User: Vorlagen-Endpunkte und Abo-Schreibpfade mit zwei Nutzern testen; Ampel-Schreibpfad ist Read-Modify-Write (ADR-0101).

## Analysis

### Type
Feature (Epic #2791, Scheibe S3a)

### Befunde der Analyse (2026-11-08, gegen origin/main @ b48afb378 und PR #2862)
- **alarm_ab hat auf main keinen Leser**; S2b (PR #2862, offen) liefert Auslösung nach Ampel (`src/services/ampel_alarm.py`, DeviationAlertEngine Trip+Vergleich) und Migration `metric_alert_levels`→`alarm_ab`. PR #2862 ändert das **Gate „aktive Alarmquelle“ NICHT** (`trip_alert.py:685-706`, `:1187-1219`: alert_preset, metric_alert_levels, alert_rules, alert_on_changes, `_official_trigger_possible`; `compare_alert.py` ohne ampel). ⇒ S3a erweitert das Gate um „mindestens eine Metrik mit `enabled` und `alarm_ab != never` in der aufgelösten Ampel“ (Trip und Vergleich), sonst stellt die neue Oberfläche Alarme ein, die nie kommen. Beim Rebase auf S2b erneut prüfen.
- `deviation_count` (`src/app/ampel.py:245-257`) zählt nur lower/upper und thunder, nicht `enabled`/`alarm_ab`/Metrik +/−; **kein Produktiv-Aufrufer**.
- `/api/metrics` (`api/routers/config.py:110-171`) liefert `category` (5 Altkategorien), `cmp`, `aggregations[].alert_metric`; es fehlen UI-Gruppe (5 Konzept-Gruppen), `alertable`, `is_precursor` (nur humidity, rain_probability gesetzt), `allowed_sides`, `display_only` (wind_direction: kein cmp/alert_metric). In Vorlagen heißt `None` = „offen“, nicht „Seite verboten“.
- Eigene Vorlagen (Go `internal/model/metric_preset.go:18-41`, `internal/handler/metric_preset.go`): Duplikat case-insensitiv nur gegen eigene (163-170), **nicht gegen die 7 Systemvorlagen**, PATCH (279-281) ganz ohne Prüfung; kein Kontext-Typ (Trip/Orte); `is_default` wird **nirgends** bei Neuanlage angewandt; Dialog schickt keine `ampel`; `summary` existiert am Go-Modell nicht.
- Amtliche Warnungen: `official_alerts_enabled` (Bericht, nil = an) und `official_warnings.enabled` (Alarm, Neuanlage false, Bestand ohne Schlüssel → Fallback `official_alert_triggers_enabled`, Default an), je Trip und ComparePreset, Python+Go.
- Tagesfenster: Trip `report_config.day_window_*_hour`, Vergleich top-level; `DayWindowCard` wiederverwendbar.
- Anlege-Ketten hängen an `REITER_DEFINITION`: `/trips/new` = route, etappen, wegpunkte, wetter-metriken (inkl. Versand), wertebereiche, alarme; `/compare/new` = vergleich, orte, wetter-metriken, wertebereiche, alarme.
- **Inventar Alarme/Versand → Ziel:** official-warnings, radar (nur Orte), Alarmstufe je Metrik → Wetter. Alarm-Kanäle + Dringlichkeit je Kanal, Kanal je Wettergröße (`alert_metric_channels`, im Abgleich NICHT zugeordnet), Telegram-Kurzstil, Cooldown, Stille Stunden, Briefing-Kanäle, Morgen/Abend + Uhrzeit, Mehrtages-Trend, Laufzeit, Aktivieren, Mail-Inhalt, Layout je Kanal (`channel_layouts`), 3-Tages-Ausblick, Nacht-Block, Stundenverlauf → erst S3b. Beispiel-Warnung entfällt (Test schicken kommt mit S3b).
- Testlast: Kennungen in ~53 (wertebereiche), 66 (alarme), 93 (wetter-metriken), 43 (versand) Test-Dateien; zugehörige Specs alle `implemented` (rework_2276_s2..s6*, layout_tab_route, versand_tab_*, feat_2287_tab_kennungen, mobile_tab_leisten_mtabbar).
- Design-Tokens `--g-rule`, `--g-accent`, `--g-paper-deep`, `--g-ink-3` existieren in `frontend/src/app.css:99-205`; Soll in `claude-code-handoff/current/jsx/{atoms,molecules,screen-trip-detail}.jsx`.

### Variantenvergleich Schnitt S3a ↔ S3b
| Variante | Anlege-Kette | „Kein Element verschwindet“ | AC-1/AC-4 erfüllbar | Aufwand/Risiko |
|---|---|---|---|---|
| (a) Übergangsreiter „Zustellung“ nimmt die heutigen Alarm-Kanal-/Ruhe-/Cooldown-Bausteine und den Versand-Abschnitt unverändert auf; S3b baut ihn um | Kanal-Schritt bleibt (neuer Name) | ja | ja | mittel, nur Verschieben |
| (b) Alarme + Versand bleiben bis S3b | unverändert | ja | nein (5 Reiter, Umleitung ins Leere) | niedrig, Auftrag verfehlt |
| (c) Alarm-Bausteine vorübergehend in Wetter | Kanal-Schritt in Wetter | ja | teilweise | hoch, Wegwerf-Code im >2000-Zeilen-Reiter |

**Entscheidung (Tech Lead): Variante (a).** Folgt der bestehenden PO-Regel „kein Bedienelement verschwindet“ und ADR-0109.

### Technical Approach
1. **Reiter-Kennung `wetter`** (neu) mit `wetter-metriken`, `wertebereiche`, `layout` als LEGACY-Alias → `wetter`; `alarme`, `versand` → `zustellung`. Sauberer als nur das Label zu tauschen (Adresse ist nutzersichtbar, ADR-0109); Testumzug wird in Kauf genommen.
2. **Anlege-Ketten:** `/trips/new` = route, etappen, wegpunkte, wetter, zustellung; `/compare/new` = vergleich, orte, wetter, zustellung (eine Definition, `ANLEGE_SCHWANZ_HINWEIS` anpassen).
3. **Übergangsreiter Zustellung** (shared, `context`): bestehende Bausteine (AlertChannelPicker, AlertMetricChannelsBlock, AlertCooldownCard, AlertQuietHoursCard, Telegram-Kurzstil, Versand-Abschnitt inkl. Layout/Ausblick/Nacht/Stundenverlauf/Mail-Inhalt) mit ihren heutigen Speicherwegen und Ownern; keine neue Speichermechanik.
4. **Reiter Wetter** (shared, `context`): Vorlage-Karte mit Picker/Wechsel-Rückfrage/Zurücksetzen, „Alarm ab für alle“, gruppierte Metrik-Zeilen mit Ampel-Leiste, „Grenzen ändern“, Erklärsätzen (abgeglichen mit S2b-Katalog `alarm.ampel.*`), „Nicht im Briefing“, Karte Amtliche Warnungen & Radar, Karte Anpassen (Tagesfenster). Schreibt `display_config.ampel` (nur Abweichungen, Read-Modify-Write, ADR-0101).
5. **Backend:** `/api/metrics` um `group`, `alertable`, `is_precursor`, `allowed_sides`, `display_only` aus `metric_catalog.py` (SSOT); Vorlagen-Zahlen (Metrikzahl, Kurzbeschreibung) aus den Daten. Abweichungszähler: Python-Referenz (`ampel.py`) erweitert um `enabled`, `alarm_ab`, Metrik +/−, Gewitterfarbe; Frontend-Spiegel für sofortiges Zählen beim Bearbeiten, Parität über gemeinsame JSON-Fixtures in beiden Testschichten. Alarmquellen-Gate Trip+Vergleich erkennt `alarm_ab`.
6. **Eigene Vorlagen (Go):** Duplikat ohne Groß-/Kleinschreibung auch gegen die 7 Systemvorlagen, auch im PATCH; Dialog speichert `ampel`; „Als Standard für neue“ wird bei Neuanlage angewandt (PO W5b: Schalter bleibt, also muss er wirken); `horizons`-Altwerte per Migration auf „alle Tage“ (Pre-Snapshot, Read-Modify-Write); Kontext-Trennung nach PO-Antwort.
7. **Amtliche Warnungen:** ein Schalter, schreibt beide Felder gleich (Renderer und Alarm-Engine bleiben unverändert); Lese-Regel bei divergierenden Altwerten nach PO-Antwort.
8. **Reiterleiste** nach Soll (Grundlinie, 2px-Unterstrich, neutrale Mono-Badges), `data-slot="segmented"` entfernen, mobil bleibt Pill-Leiste.
9. **Entfernen:** `corridor-editor/`, `AlarmeTab` (Bausteine leben in Zustellung weiter), `HorizonChips`, `MetricCheckbox`; Ordner `alerts-tab/` bleibt (lebende Bausteine; Issue-Punkt 10 ist hier falsch). Übersicht U3/U4, Hilfe-/Onboarding-Texte X1, Glossar zuerst.

### Schnitt in Teil-PRs (eine Spec, Lieferung in Reihenfolge)
1. Backend: Katalog-Felder, Zähler, Vorlagen (Duplikat, ampel, is_default, Kontext), `horizons`-Migration; Zwei-Nutzer-Tests. Gate-Teil erst nach Rebase auf S2b.
2. Reiterleiste nach Soll + Kennungen/Umleitungen + Übergangsreiter Zustellung + Anlege-Ketten.
3. Reiter Wetter (Hauptteil), **erst nach Merge von PR #2862** (sonst schreibt die Oberfläche `alarm_ab` ohne Wirkung).
4. Entfernen, Testumzug, Übersicht, Hilfe-Texte, Fresh-Eyes gegen Mockup.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/shared/subscriptionTabs.ts` | MODIFY | Reiter wetter/zustellung, LEGACY, Anlege-Ketten |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte`, `compare/CompareTabs.svelte` | MODIFY | Panels, Badges, Speicher-Schutz |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte`, `compare-new/CompareNewEditor.svelte` | MODIFY | Anlege-Schritte |
| `frontend/src/lib/components/mobile/MTabBar.svelte`, `frontend/src/app.css` | MODIFY | Reiterleiste nach Soll |
| `frontend/src/lib/components/shared/wetter-tab/*` | CREATE | Reiter Wetter (Vorlage-Karte, Metrik-Zeile, Ampel-Leiste, Grenzen-Editor, Alarm-ab-Kopf, Nicht-im-Briefing, Warnungen & Radar, Anpassen) |
| `frontend/src/lib/components/shared/zustellung-tab/*` | CREATE | Übergangsreiter aus vorhandenen Bausteinen |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `AlarmeTab.svelte`, `alarme-tab/*`, `trip-detail/AlarmeScheduleTab.svelte` | MODIFY/DELETE | Bausteine umziehen, Reste entfernen |
| `frontend/src/lib/components/shared/corridor-editor/`, `molecules/HorizonChips.svelte`, `trip-detail/MetricCheckbox.svelte` | DELETE | entfallen |
| `frontend/src/lib/components/shared/weather-metrics-tab/SavePresetDialog.svelte` | MODIFY | ohne Zeithorizonte/Zusammenfassung, mit ampel, Duplikat-Text |
| `shared/hub-uebersicht/*`, `trip-detail/HubOverview.svelte`, `shared/subscriptionActions.ts`, Listen-Seiten, `routes/hilfe` | MODIFY | U3, U4, K17, X1 |
| `frontend/src/lib/i18n/messages/{de,en}/*.json`, `docs/reference/i18n_glossar.md` | MODIFY | Texte, Glossar zuerst |
| `api/routers/config.py`, `src/app/metric_catalog.py` | MODIFY | Katalog-Felder |
| `src/app/ampel.py` | MODIFY | Abweichungszähler vollständig |
| `src/services/trip_alert.py`, `src/services/compare_alert.py` | MODIFY | Gate erkennt `alarm_ab` |
| `internal/handler/metric_preset.go`, `internal/model/metric_preset.go`, `internal/store/metric_preset.go`, Anlege-Handler trip/compare | MODIFY | Duplikat, Kontext, is_default |
| `scripts/migrate_2794_preset_horizons.py` | CREATE | horizons → alle Tage |
| Tests Node/Playwright/pytest/go | CREATE/MODIFY | neue ACs, Umzug ~150 Dateien mit alten Kennungen |

### Scope Assessment
- Files: ca. 60–90 Produktiv- plus ~150 Test-Dateien (Umzug)
- Estimated LoC: +3000–4500 / −2500 (inkl. Tests)
- Risk Level: HIGH (zentrale Reiterdefinition für Hub und Anlegen, Alarm-Gate, Daten-Migration)

### Dependencies
- Upstream: S2b PR #2862 (Merge vor Teil-PR 3; Gate-Erweiterung nach Rebase prüfen), ADR-0109-Annahme durch PO.
- Downstream: S3b #2795 baut den Übergangsreiter Zustellung zur Kanal-Tabelle um und nimmt Layout/Ausblick/Stundenverlauf in „Inhalt je Kanal“; S8 #2800 Radar-Schalter Trip.

### PO-Entscheidungen (2026-11-08, AskUserQuestion)
- [x] **ADR-0109 angenommen** (Status „Akzeptiert“ in ADR und Index). Übergangsreiter Zustellung bis S3b ist damit bestätigt.
- [x] **Amtliche Warnungen, ein Schalter:** Lese-Regel „an, wenn Bericht ODER Alarm an war“ (wirksamer Wert: `official_alerts_enabled` nil/true bzw. `official_warnings.enabled` true bzw. bei fehlendem Schlüssel Fallback `official_alert_triggers_enabled`). Speichern setzt beide Felder gleich.
- [x] **Eigene Vorlagen getrennt je Art:** Feld `kind` (`route`|`vergleich`) am MetricPreset; Bestandsvorlagen ohne `kind` gehören zu Trip (Migration bzw. Lese-Default `route`); „Als Standard für neue“ exklusiv je Art; Duplikat-Prüfung je Art plus gegen die 7 Systemvorlagen.

### Open Questions
- keine (technische Punkte entschieden, siehe Technical Approach)
