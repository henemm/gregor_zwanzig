# Context: Scheibe S3 — Kanal-Spalte je Metrik im Alarme-Reiter (#1895)

> Workflow `feat-1895-s3-kanal-spalte` · Issue #1895 · Epic #2345 (#1230 geschlossen)
> Erhoben 2026-11-03, Stand `origin/main` = `217d3b762`.
> Vorgänger: S1 (`dfc13d9d`, PR #2402, Feld + Persistenz), S2 (`7adc916e`, PR #2409, Leser + Migration).
> Grundlagen-Kontext (weiter gültig): `docs/context/feat-1895-kanalzuordnung-je-metrik.md`,
> `docs/context/feat-1895-s2-kanal-leser.md`. Spec: `docs/specs/modules/alert_metric_channels.md`.

## Request Summary

Die metrik-genaue Kanalzuordnung `alert_metric_channels` wird seit S2 beim Alarm-Versand gelesen und
wirkt — der Nutzer kann sie aber nirgends sehen oder ändern. S3 baut die Bedienfläche: eine
Kanal-Spalte je Metrik direkt neben der Empfindlichkeitsstufe im geteilten Alarme-Reiter (Trip UND
Ortsvergleich), und legt laut ADR-0077 Punkt 3 die **verbindliche, validierte Schlüsselmenge** samt
**Bestandsdaten-Prüfung** fest.

## 🔴 Kernbefund 1: Zeilen-Vokabular ≠ Speicher-Vokabular (zentrale Designfrage)

Die Zeilen der Stufen-Tabelle sind **`AlertMetric`-Kennungen** (`wind_gust`, `temperature_min`, …,
`frontend/src/lib/types.ts:75-94`, Reihenfolge `ALERTABLE_METRICS`
`alerts-tab/alertMetricTable.ts:197-214`, 15 Zeilen). `metric_alert_levels` ist ebenfalls nach
`AlertMetric` geschlüsselt.

`alert_metric_channels` dagegen ist nach **Katalog-`metric_id`** geschlüsselt (`gust`, `temperature`,
…) — so liest es der S2-Leser (`src/services/alert_channels.py:187-202`, `_metric_channel_sets` →
`_metric_id_for_summary_key` → `metric_catalog.metric_and_aggregation_for_field`) und so schreibt es
die S2-Migration (`src/app/loader.py:832-883`, `_katalog_ids_fuer_alarm_metrik`).

Die Abbildung ist **viele-zu-eins** (`src/services/weather_change_detection.py:96-118`, Tie-Break
„wählbar gewinnt"):

| Katalog-`metric_id` | Zeilen (`AlertMetric`), die darauf fallen |
|---|---|
| `temperature` | `temperature_min`, `temperature_max`, `temperature_change` (**3 Zeilen**) |
| `precipitation` | `precipitation_sum`, `precipitation_change`, `precipitation_heavy_onset` (**3**) |
| `thunder` | `thunder_level`, `thunder_onset` (**2**) |
| `freezing_level` | `freezing_level` (+ Legacy `snow_line`, das zusätzlich `snowfall_limit` erzeugt) |
| `gust` · `wind` · `fresh_snow` · `cape` · `visibility` | je genau eine Zeile (`wind_gust`, `wind_change`, …) |
| — | `humidity` (keine Alarm-Identität, ADR-0010) |

**Folge:** Eine Kanalwahl „je Zeile" ist mit dem heutigen Schlüssel nicht abbildbar — wer bei
„Tiefsttemperatur" nur SMS wählt, ändert zwangsläufig auch „Höchsttemperatur" und
„Temperaturänderung". Und: Schreibt die Spalte `AlertMetric`-Schlüssel (`wind_gust`), findet der
S2-Leser sie **nie** (er sucht `gust`) — eine Konfigurationsfläche ohne Wirkung, genau das, was
ADR-0043 verbietet und #1895 aufräumt. Das ist die Hauptgefahr dieser Scheibe.

Optionen für `/20-analyse` (Entscheidung, keine PO-Frage, solange ADR-0077 eingehalten wird):
- **(a) Spalte je Zeile, Schreiben auf die Katalog-ID, Geschwisterzeilen spiegeln** — ehrlich, aber
  die Kopplung muss sichtbar sein (gleiche Werte in 3 Zeilen, Änderung an einer ändert alle).
- **(b) Zuordnung je Katalog-Größe gruppiert** (eine Kanalzelle je `metric_id`, die mehrere
  Stufen-Zeilen überspannt) — entspricht der Speicherform 1:1.
- **(c) Schlüssel auf `AlertMetric` umstellen** — widerspricht ADR-0077/S2-Lesevokabular, braucht
  neues ADR + Leser-/Migrationsumbau; nur mit starker Begründung.

**Leseseite gemessen (2026-11-03, `_metric_id_for_summary_key` je Katalog-`summary_field`):**

| Summary-Key (`WeatherChange.metric`) | liest Leser als |
|---|---|
| `temp_min_c`, `temp_max_c`, `temp_avg_c` | `temperature` (auch für `temperature_cold`, Tie-Break) |
| `wind_max_kmh` | `wind` |
| `gust_max_kmh` | `gust` |
| `precip_sum_mm`, `precip_heavy_onset_utc` | `precipitation` |
| `thunder_level_max`, `thunder_onset_utc` | `thunder` |
| `cape_max_jkg` | `cape` (Größe `selectable=False`, aber einziger Kandidat) |
| `snowfall_limit_m` · `freezing_level_m` · `visibility_min_m` · `snow_new_sum_cm` | `snowfall_limit` · `freezing_level` · `visibility` · `fresh_snow` |

Kein Summary-Key löst auf `None` auf; Schreib- (Migration) und Leseseite stimmen für alle 15 Zeilen
überein — die Onset- und `*_change`-Zeilen landen auf derselben Größe wie ihre Geschwister. Offen für
`/20-analyse`: stichprobenartig bestätigen, dass die Detektoren (Deviation-Engine, Onset-Detektor)
wirklich genau diese `summary_fields` als `WeatherChange.metric` ausgeben (Probe-Skript lag im
Scratchpad, rein lesend gegen `metric_catalog._METRICS`).

Die Summary-Key-Auflösung des Lesers ist ebenfalls grob: Ein Änderungsalarm auf `temp_max_c` landet
auf `temperature` — die Trennung min/max/Änderung existiert im Lesepfad gar nicht. Auch das spricht
gegen eine scheinbar feinere Zeilen-Granularität in der Oberfläche.

## Kernbefund 2: Der Editor-Ort ist eindeutig und geteilt

- Geteilter Reiter `frontend/src/lib/components/shared/AlarmeTab.svelte` (635 Z.), Abschnitt
  `metric-levels` (`:500-523`) mountet `alerts-tab/AlertMetricLevelTable.svelte` (Kopf
  „Metrik / Empfindlichkeit / Schwellwert", `:79-85`) → `alerts-tab/AlertMetricLevelRow.svelte`
  (`<tr>` mit Label · Segmented-Control 4 Stufen · Schwellwert; `data-testid="alert-metric-row-{metric}"`).
- Mounts: Trip `trip-detail/AlarmeScheduleTab.svelte` (über `TripTabs.svelte`); Ortsvergleich
  `compare/CompareTabs.svelte` und `compare-new/CompareNewEditor.svelte` (Desktop + Mobile);
  Trip-Anlegen `trip-new/TripNewEditor.svelte`. Eine Änderung an Table/Row gilt damit automatisch für
  alle Flächen — Pflicht laut CLAUDE.md (Trip/Ortsvergleich-Code-Teilung); eine Compare-eigene
  Fassung wäre ein Verstoß.
- Abo-weite Kanäle sitzen im eigenen Abschnitt `channels` (`AlarmeTab.svelte:525-548`,
  `shared/AlertChannelPicker.svelte`, mit Kanal-Schwelle ADR-0046 und `disabledChannels`).
  Wiederverwendbare Bausteine für eine Kanalzelle: `shared/ChannelToggle.svelte`,
  `AlertChannelPicker.svelte`, Gate `alarme-tab/premiumSmsAlarmGate.ts`.
- Zwei Altzweige nicht verwechseln: `alerts-tab/AlertMetricRow.svelte`/`AlertMetricTable.svelte`
  sind tot (0 Importeure außerhalb des Ordners, #1199); `alert-rules-editor/` (Regel-Chips je Regel)
  ist nur noch im Anlege-Wizard montiert und Rückbau-Gegenstand von S4.

## Kernbefund 3: Zwei getrennte Speicherwege — beide müssen das Feld tragen

| Zweig | Speicherweg | Heute im Payload |
|---|---|---|
| Trip (`trip` gesetzt) | `buildAlarmeSaveFn` (`AlarmeTab.svelte:~400`) → `alarme-tab/alarmeDeliveryPayload.ts` → `shared/tripSpeicherung.ts` (PUT) ; Dirty-Check-JSON `:420-445` | Kanäle, Kanal-Schwellen, Stufen, Cooldown, Ruhezeit — **kein** `alert_metric_channels` |
| Ortsvergleich | `alarmZustandsBruecke` + `shared/alarmeVergleichSpeicherung.ts` (Wertprops, `onAlarmFeldSetzen`, Rollback) ; Props aus `compare/alarmePropsAus.ts` | ebenso **kein** `alert_metric_channels` |
| Anlegen | Trip-Wizard bzw. `CompareNewEditor` (kein Auto-Save, `createMode`) | — |

Server-Seite ist fertig (S1): Go `internal/handler/trip.go:300` (`*map[string]interface{}`,
Teil-PUT mergt **eine Ebene tief** je Metrik-Schlüssel, ADR-0077 Punkt 2), `internal/model/trip.go:171`,
`internal/model/compare_preset.go:123`; Python `src/app/models.py:1380` (Compare), Trip-Dataclass +
`loader.py:305,658,744,1814`. Eintragsform ist `{kanal: bool}` (`alert_channels.py:158-169` liest
auch Listen).

**Merge-Folge für den Editor:** Je Metrik-Schlüssel wird der Wert **komplett ersetzt**. Die Spalte
muss also je geänderter Metrik den vollständigen Eintrag (alle vier Kanäle) senden; ein Senden der
ganzen Map ist erlaubt, aber nicht nötig.

**„Wieder erben" — gemessen statt vermutet:** `mergeConfigMap` (`internal/handler/config_merge.go:11-22`)
macht `dst[k] = v` auch für `v == nil` — ein gesendetes `"gust": null` wird also als `null`
**persistiert**, nicht gelöscht. Python liest `_entry_channels(None)` → leere Menge → „erbt". Und die
S2-Migration nutzt `setdefault` (`loader.py:~880`): ein vorhandener `null`-Schlüssel blockiert die
Rück-Migration der Regel-Kanäle. `null` ist damit ein brauchbares, explizites „erbt"-Signal (stärker
als „Schlüssel fehlt", weil es die Regel-Union aus Kernbefund 6 ausschaltet). Zu prüfen in der
Analyse: Go-`omitempty` auf der Map entfernt `null`-Einträge **nicht**; Go-LoadTrip/Python-Save
bewahren den `null`-Wert (Roundtrip-Test). Der Trip-Pfad ist `handler/trip.go:375-378`; am
Ortsvergleich taucht das Feld in `handler/compare_preset.go`/`briefing_subscription.go` nicht
namentlich auf — dort läuft es über den generischen Briefing-Patch (S1 hat Teil-PUT-Merge für beide
Arten auf Staging belegt); `null`-Verhalten dort separat messen.

## Kernbefund 4: Semantik, die die Spalte darstellen muss

Auflösung (`resolve_alert_channels`, `alert_channels.py:66-93`):
1. Abo-Satz (Override `alert_channels` bzw. geerbte Briefing-Kanäle) → 2. Regel-Union (`alert_rules`,
   bis S4) → 3. **Metrik-Arm:** Union der Einträge der auslösenden Metriken; eine auslösende Metrik
   **ohne** Eintrag trägt den Abo-Satz bei; ist das Ergebnis leer, bleibt der Abo-Satz (AC-12, ein
   Alarm erreicht nie niemanden) → 4. Tier-Gates (`sms`, `premium_sms`) ganz am Ende →
   danach Kanal-Schwelle `split_by_threshold` (ADR-0046).

Was die Oberfläche daraus ehrlich zeigen muss:
- **„erbt"** (kein Eintrag) ist ein eigener, sichtbarer Zustand — nicht dasselbe wie „alle Kanäle an".
- **Ein Metrik-Kanal, den das Abo nicht trägt, wird trotzdem bedient** (Metrik-Arm ersetzt den
  Abo-Satz, er schneidet ihn nicht). Ist das gewollt oder muss die Spalte auf die Abo-Kanäle begrenzt
  sein? Gegenprobe: die Kanal-Ebene darf nie über das *Ob* entscheiden (ADR-0043/0046, #1701) — sie
  tut es hier auch nicht, sie erweitert nur den Weg. Analyse muss das als Entscheidung festhalten.
- **Leere Auswahl** (alle Kanäle abgewählt) wirkt wie „erbt" (`_entry_channels` → leere Menge). Die
  UI darf keinen Zustand anbieten, der etwas anderes verspricht (ADR-0043).
- **Tier-Gates:** SMS/Premium-SMS ohne Tarif werden am Ende gestrichen; die Spalte muss dieselbe
  Sperr-/Hinweislogik wie `AlertChannelPicker` (`disabledChannels`, `premiumSmsAlarmGate.ts`) zeigen.
- **Alle vier Kanäle** (E-Mail, Telegram, SMS, Premium-SMS) gleichrangig (ADR-0049, #1701) — der
  abgelöste Regel-Editor kannte nur drei.
- **Metrikfreie Alarme** (Radar, amtliche Warnungen) ignorieren die Spalte bauartbedingt (S2 AC-13).
  Wer bei „Gewitter" nur Telegram wählt, bekommt die **amtliche** Gewitterwarnung trotzdem über den
  Abo-Satz. Muss in der Oberfläche benannt werden, sonst ist es ein neues Falschversprechen.

## 🔴 Kernbefund 6: „erbt" in der Anzeige ≠ „erbt" im Versand (bis S4)

Der Satz, den eine Metrik ohne Eintrag erbt, ist **nicht** der Abo-Satz, den der Editor zeigt:
- **Regel-Union:** bis S4 geht `alert_rules[].channels` (Schritt 2 der Auflösung) in den geerbten
  Satz ein. Der Alarme-Reiter sieht nur `alert_channels`/`report_config`
  (`alarme-tab/tripChannelReconstruction.ts`), nicht die Regel-Kanäle.
- **Migrationsort:** die S2-Migration läuft beim **Laden in Python**; GET liefert **Go**. Ein Trip, den
  Python seit S2 nicht gespeichert hat, trägt die migrierten Schlüssel nicht auf der Platte → der
  Editor zeigt „erbt", der Versand nutzt aber die migrierten Regel-Kanäle.

Folge: Ohne Gegenmaßnahme zeigt die Spalte für Bestandstrips etwas anderes, als verschickt wird.
Optionen für die Analyse: Migration vor S3 persistieren (Skript im Muster `migrate_1231_corridors.py`),
Go-seitig gleich migrieren, oder die Anzeige aus `alert_rules` mitrekonstruieren.

**Bestandsmessung (Pflicht in `/20-analyse`, Prod lesend per `sudo -n -u claude-gregor`):** je
`data/users/*/briefings/*.json` zählen (a) Briefings mit nicht-leerem `alert_rules[].channels` auf
aktivierten Regeln, aber **ohne** `alert_metric_channels` auf der Platte; (b) Schlüssel in
`alert_metric_channels` außerhalb der gültigen Menge (Kernbefund 5); (c) `kind` je Treffer.

## Kernbefund 5: Schlüsselmenge & Bestandsdaten-Prüfung (ADR-0077-Folgepflicht)

- Gültige Menge = Katalog-`metric_id`s, die als Ziel einer `AlertMetric` vorkommen und wählbar sind:
  `gust, wind, precipitation, temperature, thunder, freezing_level, fresh_snow, cape, visibility`
  (+ `snowfall_limit` nur aus Legacy-`snow_line`). Genau ableiten in `/20-analyse` aus
  `_ALERT_METRIC_TO_CATALOG_ID` + Wählbarkeit — **keine** zweite handgeschriebene Liste (Muster #1257,
  Wächter #1480 gegen Kopien).
- Go validiert heute **keine** Metrik-Schlüssel. Ob S3 serverseitig validiert (Ablehnung vs.
  stilles Ignorieren unbekannter Schlüssel) ist Analyse-Entscheidung; ADR-0077 warnt: eine harte
  Validierung bricht Bestandsdaten mit abgelösten Schlüsseln (`snow_line`).
- Bestandsdaten-Prüfung: Prod-Bestand per `sudo -n -u claude-gregor` lesen (Memory
  `reference_prod_daten_per_sudo_claude_gregor_erreichbar`), `data/users/<id>/briefings/*.json`
  auf `alert_metric_channels`-Schlüssel außerhalb der gültigen Menge prüfen. Erwartung: nur aus der
  S2-Migration entstandene Katalog-IDs; die Messung ist trotzdem Pflicht.
- Frontend kennt die Abbildung `AlertMetric → metric_id` bereits indirekt über den Katalog
  (`alarme-tab/tripAlertMetricsFromCatalog.ts:28-38`, `aggregations[].alert_metric` +
  `change_alert_metric`) — Kandidat für die Rückabbildung Zeile → Speicherschlüssel ohne neue Tabelle.
  Der Vergleichs-Pfad rechnet auf Auswahl-Schlüsseln (`activeAlertMetricsFromCatalog.ts`), nicht auf
  nackten Kennungen — Falle 2 aus #1544.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelTable.svelte` | Tabellenkopf + Zeilen-Schleife — Spalte andocken |
| `frontend/src/lib/components/alerts-tab/AlertMetricLevelRow.svelte` | `<tr>` je Metrik — neue Kanalzelle |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Verdrahtung, Trip-Save (`buildAlarmeSaveFn`, Dirty-JSON), Vergleichs-Brücke |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | Trip-PUT-Payload — Feld ergänzen |
| `frontend/src/lib/components/shared/alarmeVergleichSpeicherung.ts` | Vergleichs-Speicherweg, Snapshot/Rollback |
| `frontend/src/lib/components/compare/alarmePropsAus.ts`, `compare/CompareTabs.svelte`, `compare-new/CompareNewEditor.svelte` | Compare-Props/Mounts |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte`, `trip-new/TripNewEditor.svelte` | Trip-Mounts |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte`, `ChannelToggle.svelte`, `alarme-tab/premiumSmsAlarmGate.ts` | Kanal-Bausteine + Tarif-Gate zum Wiederverwenden |
| `frontend/src/lib/types.ts` | `Trip`/`ComparePreset` — Typ `alert_metric_channels` ergänzen |
| `frontend/src/lib/i18n/messages/*` | neue Texte DE/EN nur über den Katalog (ADR-0104) |
| `src/services/alert_channels.py` | Leser (Wirkstelle) — Referenz für Semantik, voraussichtlich unverändert |
| `src/services/weather_change_detection.py:96-140` | `_ALERT_METRIC_TO_CATALOG_ID` — Quelle der Schlüsselmenge |
| `src/app/loader.py:832-883` | S2-Migration + Tie-Break |
| `internal/handler/trip.go:300`, `internal/handler/compare_preset.go`, `internal/handler/briefing_subscription.go`, `internal/handler/config_merge.go` | Teil-PUT-Merge (eine Ebene), ggf. Validierung/Löschsignal |
| `docs/specs/modules/alert_metric_channels.md` | S1/S2-Spec — S3 als weiteren Abschnitt ergänzen |
| `docs/adr/0077-…md`, `0043`, `0046`, `0049` | harte Grenzen |
| `docs/reference/api_contract.md` | DTO-Doku `alert_metric_channels` nachziehen |

## Existing Patterns

- **Kanal-Schwelle je Kanal** (#1461 S3b-2a/2b): route = lokaler `$state` + Dirty-JSON im
  konsolidierten Save; vergleich = Wertprop + `onXChange`-Callback → `onAlarmFeldSetzen`. Exakt dieses
  Doppelmuster für die neue Map übernehmen (Kommentar `AlarmeTab.svelte:318-350`).
- **Stufen je Metrik**: `routeMetricLevels`/`metricAlertLevels` — gleiche Form (Map je Metrik).
- **EIN Save-`$effect`** für alle Alarmfelder (F001-Lehre: zweiter `schedule()` verwirft Änderungen).
- **Ratsche** `context_herkunft_zweige_eingefroren.test.ts`: keine neuen `context===`-Zweige;
  Diskriminator ist `trip`.
- Frontend-Tests laufen über `node --test` (kein Vitest).

## Dependencies

- Upstream: Metrik-Katalog (`/api/metrics`, `aggregations[].alert_metric`), Abo-Kanalstand
  (`displayChannelState`), Tarif-Gates, Go-Merge.
- Downstream: S2-Leser im Alarm-Versand (Trip `trip_alert.py:2509`, Vergleich `compare_alert.py:601`),
  S4 (Rückbau `alert_rules`, setzt S3 voraus — erst dann gibt es eine sichtbare Ersatzfläche).

## Existing Specs

- `docs/specs/modules/alert_metric_channels.md` — S1/S2, Scheibenschnitt S3/S4 (`:491-540`)
- `docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md` — welche Zeilen der Reiter zeigt
- Spec #1461 (Kanal-Schwellen) — Vorbild für die Doppelverdrahtung
- Nicht verwechseln: `fix_1575_channel_metric_selection.md` / ADR-0050 = Briefing-Metrik×Kanal-Matrix
  (welche Wettergröße in welchem Briefing-Kanal) — andere Matrix, gleiche Achsen. Benennung im UI
  trennscharf halten.

## Risks & Considerations

- **R1 Wirkungslose Fläche (ADR-0043):** falscher Schlüssel (`AlertMetric` statt `metric_id`) →
  Spalte ohne Wirkung. Mutations-Gegenprobe muss am Leser beweisen, dass ein im Editor gesetzter Wert
  den Versandkanal ändert (Wirkstelle, nicht nur Payload).
- **R2 Kopplung Geschwisterzeilen:** viele-zu-eins (Kernbefund 1) — wird sie versteckt, ist es ein
  neues stilles Falschversprechen.
- **R3 Datenverlust:** Teil-PUT ersetzt je Metrik-Schlüssel; Payload muss vollständigen Eintrag
  senden, nie `{}` für eine nicht angefasste Metrik (würde „erbt" in einen leeren Eintrag
  verwandeln). Read-Modify-Write, Bestandseinträge unbekannter Schlüssel überleben.
- **R4 „Erben" wiederherstellen** ist mit dem eine-Ebene-Merge nicht ausdrückbar (Kernbefund 3).
- **R5 Parität:** Trip + Ortsvergleich + beide Anlegemasken; Staging-Nachweis auf `.tn-mobile` UND
  `.tn-desktop` (Lücke aus Schritt 2, #1895-Kommentar 21.09.).
- **R5b 🔴 Alarm erreicht NIEMANDEN:** Die Tier-Gates laufen **nach** dem Metrik-Arm, und S2 lässt
  absichtlich zu, dass ein nicht-leerer Metrik-Arm danach leer wird
  (`test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren`). Ein Eintrag „nur SMS"
  bei einem Nutzer ohne SMS-Tarif — oder ein Kanal ohne konfigurierten Empfänger — heißt: der Alarm
  geht an niemanden. Die Spalte muss solche Einträge **verhindern**, ein Hinweis reicht nicht
  (ADR-0043/0046, #1701). Gehört als AC in die Spec.
- **R6 Metrikfreie Alarme** werden von der Spalte nicht gesteuert — benennen.
- **R7 Mandantentrennung:** jeder datenbewegende Pfad mit zwei Nutzern (Staging-Login liefert nur
  `default`, zweiter Nutzer im Kern bzw. per Staging-Rezept).
- **R8 Mobile-Platz:** Tabelle hat schon 3 Spalten mit Kurzlabels; vier Kanal-Chips je Zeile auf
  Mobile → Layout-Entscheid (Kontrast/Lesbarkeit vor Optik, WCAG-AA).
- **R9 i18n:** neue Texte DE/EN über den Katalog; Kanal-Kürzel sind Nutzertext, keine Protokoll-Token.
- **R10 Grid-Altfehler** `AlertRuleRow.svelte` (≥2 Kanäle bricht um) liegt im Regel-Editor, nicht hier
  — nicht mitnehmen.

## Offene Designfragen für /20-analyse

1. Granularität der Spalte: je Zeile mit Spiegelung, gruppiert je Katalog-Größe, oder Schlüsselwechsel
   (Kernbefund 1)?
2. Darstellung „erbt" vs. eigene Auswahl; wie kehrt der Nutzer zu „erbt" zurück (Löschsignal im Merge)?
3. Dürfen Metrik-Kanäle über den Abo-Satz hinausgehen, oder nur aus ihm wählen?
4. Serverseitige Validierung der Schlüsselmenge ja/nein, und Verhalten bei unbekannten Bestandsschlüsseln.
5. Wo stehen Hinweise zu metrikfreien Alarmen und Tarif-Sperren?
6. Anlege-Masken: Spalte schon beim Anlegen oder erst im Detail?
7. Wie wird die Anzeige für Bestandstrips ehrlich (Kernbefund 6): persistierende Migration vor/mit S3,
   Go-Migration, oder Rekonstruktion aus `alert_rules`?
8. Wie verhindert die Spalte Einträge, die nach Tarif-Gate/fehlendem Empfänger niemanden erreichen (R5b)?

## Analysis

> `/20-analyse` 2026-11-03. Quellen: 3 Explore-Läufe (Go/Python-Roundtrip, Detektor-Schlüssel,
> Frontend-Bausteine), Plan-Bewertung (Sonnet), eigene Prod-Messung, Advisor-Gegenprüfung.

### Type
Feature (Scheibe S3 von #1895, Epic #2345).

### Messergebnisse (neu, belegt)

- **Prod-Bestand** (`/var/lib/gregor/users`, 4 Nutzer, lesend per `sudo -n -u claude-gregor`):
  0 Briefings mit `alert_metric_channels`; 0 Regeln mit `alert_rules[].channels` (alle
  „channels"-Treffer sind `display_config.channels`/`alert_channels`). ⇒ (a) = 0, (b) = 0.
- **Kernbefund 6 geschlossen:** Kein Schreiber für Regel-Kanäle mehr — der Regel-Editor existiert im
  Frontend nicht mehr (`alert-rules-editor/` fehlt, `AlertMetricTable.svelte` tot), Go `AlertRule.Channels`
  (`internal/model/trip.go:66`) wird nirgends gesetzt. „erbt" in der Anzeige = „erbt" im Versand;
  **keine Persistier-Migration nötig.**
- **Leseseite:** Detektoren emittieren nur Summary-Keys (`weather_change_detection.py:880,941,1049,1090`),
  jeder löst über `_metric_id_for_summary_key` auf eine Katalog-ID auf, keiner auf `None`.
  `snow_line`-Regeln laufen als `freezing_level_m` ⇒ Leser liest `freezing_level`; die Migration
  schreibt bei `SNOW_LINE` aber **beide** Schlüssel (`snowfall_limit` + `freezing_level`,
  `loader.py:832-850`). `cape` ist `selectable=False`, wird aber gelesen und migriert.
- **Null/Löschen:** `{"gust": null}` wird in Trip und Ortsvergleich als `null` persistiert
  (`config_merge.go:18-20`); Leser: null = erbt; Migration `setdefault` respektiert null. Kein Weg zum
  Löschen eines Schlüssels. **Asymmetrie:** Top-Level `"alert_metric_channels": null` ist beim Trip No-Op
  (`handler/trip.go:375`), beim Ortsvergleich **löscht es die ganze Map**
  (`briefing_subscription.go:200`, kein Restore in `compare_preset.go:320-327`).
- **Frontend:** Feld fehlt in `types.ts`; Sperre nur `premium_sms` (`premiumSmsAlarmGate.ts:40-50`),
  SMS-Tarif und fehlende Empfänger kennt das Frontend nicht. Keine Funktion Zeile → `metric_id`;
  `CATALOG_TO_ALERT_METRICS` (`alertMetricTable.ts:309-334`, nicht exportiert) enthält als einzige
  Quelle auch Onset- und `*_change`-Zeilen; `/api/metrics` liefert Onset nie in `aggregations[]`.
  Geschwisterzeilen stehen in `ALERTABLE_METRICS` **nicht** benachbart.
- **Nebenbefund (#1199):** `compare_alert.py:70-80` bildet `temp_min_c` → `temperature_cold`,
  `alert_channels.py` → `temperature` (nur Deaktivieren-Filter betroffen, nicht die Kanal-Map).

### Entscheidungen (technisch, ADR-konform — keine PO-Fragen)

| # | Frage | Varianten | Entscheidung | Begründung |
|---|---|---|---|---|
| E1 | Granularität | (a) Zelle je Zeile gespiegelt · (b) eigener Block je Katalog-Größe · (c) Tabelle umgruppieren · (d) Schlüssel auf AlertMetric | **(b)** Block „Kanäle je Wettergröße" unter der Stufen-Tabelle, eine Zeile je aktiver Katalog-`metric_id` | 1:1 zu Speicher/Leser/Migration; kein verstecktes Spiegeln (R2); Mobile einfach; (c) gefährdet Stufen/Schwellen, (d) bricht S1/S2 + neues ADR |
| E2 | Abbildung Zeile → Schlüssel | zweite Handliste · `CATALOG_TO_ALERT_METRICS` (Frontend) invertieren · **API als einzige Quelle** | **API als einzige Quelle (bevorzugt):** die Katalog-`entry.id` aus `/api/metrics` IST bereits die `metric_id`; einzige Lücke ist, dass Onset-Zeilen nie in `aggregations[]` erscheinen (`metric_catalog.available_aggregations` filtert min/max/avg/sum). Lücke im Backend schließen (Onset-`alert_metric` mit ausliefern, `src/app/metric_catalog.py` + `api/routers/config.py:130-152`), Frontend leitet Zeile → `entry.id` aus der Antwort ab. Rückfallvariante: Frontend-Liste invertieren. `humidity` ohne Identität aus; `snowfall_limit` nie anbieten | keine Kopie (Wächter #1480); ein Python-Test, der `alertMetricTable.ts` einliest, wäre ein verbotener Dateiinhalt-Check |
| E3 | Schlüsselmenge „verbindlich, validiert" (ADR-0077 P.3) | Go-Validierung · keine · Ein-Ort-Definition + Wirk-Test | **Python als einzige Definition** (aus `_ALERT_METRIC_TO_CATALOG_ID` mit Migrations-Tie-Break; Annahme-Menge inkl. `cape`, `snowfall_limit`, weil die Migration sie schreibt). **Prüfung zeilenweise auf Gleichheit, nicht als Teilmengen-Kette:** Kern-Test (reines Python) je Alarm-Zeile — Schlüssel, den die API für die Zeile anbietet == Schlüssel, den der Leser für den Summary-Key liefert, den der Detektor für diese Zeile emittiert. (Eine ⊆-Kette bliebe grün, obwohl z. B. `snowfall_limit` im Trip-Pfad nie ausgelöst wird.) **Keine Go-Schreibvalidierung** | Go hat keinen Katalog (Kopie = Drift); ADR-0077 P.3 warnt vor Bestandsbruch; Leser ist fail-soft; Bestandsprüfung erledigt (0/0) |
| E4 | „erbt" / Rücksetzen | null-Eintrag · Go: null löscht | **null-Eintrag = erbt** (UI sendet `{id: null}`); „erbt" ist sichtbarer eigener Zustand | kein Eingriff in `mergeConfigMap` (wirkt auf alle Maps); Bestand 0 |
| E5 | Leere Auswahl | erlauben · verhindern | alle Kanäle abwählen ⇒ wird als „erbt" gespeichert/angezeigt, nie als `{}` oder alle-false | Leser behandelt beides als erbt; UI darf nichts anderes versprechen (ADR-0043) |
| E6 | Kanalauswahl | frei aus 4 · nur aus Abo-Satz | **frei aus allen vier**, `premium_sms` mit vorhandenem Tarif-Gate; sichtbarer Hinweis, wenn ein gewählter Kanal nicht im Abo-Satz aktiv ist | Metrik-Arm ersetzt bewusst (S2); Abo-Begrenzung bräche gespeicherte Einträge bei Schrumpfung; ADR-0049 Kanal-Parität |
| E7 | R5b „Alarm erreicht niemanden" | (i) nur UI · (ii) Leser-Rückfall · (iii) beides | **(iii)**, eng geschnitten: **Leser-Rückfall nur für den Metrik-Arm** — ist der Metrik-Arm **nach den Tier-Gates** leer, gilt der Satz ohne Metrik-Arm (ebenfalls nach Gates). Tier-Gates selbst bleiben unverändert (vereinbar mit #2279 S1 AC-4: SMS/Premium-SMS ohne Tarif bleiben gestrichen). UI-Sperren (Premium-SMS-Gate) nur Komfort | UI kennt SMS-Tarif nicht; Garantie muss in den Leser. Kehrt S2-Test `test_ac12_tier_gate_darf_nach_nicht_leerem_metrik_arm_auf_leer_fuehren` und den Docstring-Satz „kein Fall für den Rückfall" (`alert_channels.py:60-64`) für den Metrik-Arm um ⇒ **ADR-0077-Nachtrag Pflicht** |
| E7b | Was der Rückfall **nicht** abdeckt (benannte Restrisiken) | — | (1) **Fehlender Empfänger** (z. B. Telegram ohne verknüpften Chat): `resolve_alert_channels` kennt Empfänger nicht. (2) **Kanal-Schwelle** (`split_by_threshold`, ADR-0046, läuft nach der Auflösung): Metrik-Arm `{sms}` + SMS-Schwelle „hoch" unterdrückt eine niedrigere Warnung, auch wenn die Abo-E-Mail sie bekommen hätte. Beides gilt **heute schon gleich für den Abo-Satz** — S3 macht es nicht schlechter, aber pro Metrik häufiger. In `/30-write-spec` je eine AC: Kanalblock zeigt Hinweis bei Kanal ohne Empfänger und bei Kanal mit Schwelle über der Metrik-Stufe; Entscheidung, ob der Rückfall hinter `split_by_threshold` gezogen wird, dort treffen (Prüfauftrag: Aufrufer `trip_alert.py`, `compare_alert.py`) | Ehrlich benennen statt mehr versprechen, als der Rückfall leistet |
| E8 | Datenverlust Ortsvergleich (Top-Level null) | Go angleichen · nur Frontend-Test | **Go angleichen, aber NUR für das Feld `alert_metric_channels`**: Top-Level `null` = No-Op wie beim Trip, + Go-Test. Keine allgemeine „null = No-Op"-Regel: `briefing_subscription.go:200` setzt `base[k] = v` für alle Top-Level-Felder, und andere Felder nutzen `null` bewusst als Zurücksetzen (z. B. `end_date`, Defaults in `compareEditorSave.ts:612-644`). Zusätzlich Frontend-Test, dass Snapshot/Rollback (`alarmeVergleichSpeicherung.ts`) und die Nachbar-Schreiber (`wertebereicheVergleichSpeicherung.ts`, `versandVergleichSpeicherung.ts`) das Feld erhalten | Quelle beseitigen statt alle Schreiber beweisen, ohne bestehende Rücksetz-Semantik zu brechen |
| E9 | Metrikfreie Alarme | — | Hinweistext im Block: Radar und amtliche Warnungen gehen immer über die Abo-Kanäle | sonst neues Falschversprechen (R6) |
| E10 | Anlegemasken | sofort · erst im Detail | **sofort** — geteilter AlarmeTab ist in `TripNewEditor`/`CompareNewEditor` montiert; Payload dort mitführen | Code-Teilung Pflicht; Anlegen = Bearbeiten |

### Affected Files (with changes)

| File | Change Type | Description |
|---|---|---|
| `src/services/alert_channels.py` | MODIFY | Leser-Rückfall nach Tier-Gates (E7); gültige Schlüsselmenge (E3) hier oder in `weather_change_detection.py` |
| bestehender S2-Test mit `test_ac12_tier_gate_…` | MODIFY | AC-12-Test umkehren (E7) |
| `src/app/metric_catalog.py`, `api/routers/config.py` | MODIFY | Onset-`alert_metric` in `/api/metrics` ausliefern (E2) |
| `tests/test_alert_metric_channel_keys_*.py` | CREATE | zeilenweiser Wirk-Test API-Schlüssel == Leser(Detektor-Key) (E3) |
| `internal/handler/briefing_subscription.go`, `compare_preset.go` | MODIFY | Top-Level null = No-Op (E8) |
| `internal/handler/*_test.go` | CREATE/MODIFY | Null-Asymmetrie-Test |
| `docs/adr/0077-metrik-genaue-kanal-schicht-als-top-level-map.md` | MODIFY | Nachtrag S3: Schlüsselmenge, Rückfall, null = erbt |
| `frontend/src/lib/components/alerts-tab/alertMetricTable.ts` | MODIFY | Export + Invertierung Zeile → Schlüssel |
| `frontend/src/lib/components/alerts-tab/<Kanal-Block>.svelte` (Name in Spec) | CREATE | Block „Kanäle je Wettergröße" (4 Kanäle + „erbt", Gate, Hinweise) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | MODIFY | Mount, route-`$state` + Dirty-JSON, Vergleichs-Wertprop |
| `shared/alarme-tab/alarmeDeliveryPayload.ts` | MODIFY | Trip-PUT-Feld |
| `trip-new/tripNewLogic.ts`, `TripNewEditor.svelte`, `trip-detail/AlarmeScheduleTab.svelte` | MODIFY | Trip-Durchreichung inkl. Anlegen |
| `compare/compareHubHydration.ts`, `compareEditorSave.ts`, `alarmePropsAus.ts`, `shared/alarmeVergleichSpeicherung.ts`, `compare-new/CompareNewEditor.svelte` | MODIFY | Vergleich-Durchreichung, Snapshot/Rollback |
| `frontend/src/lib/types.ts` | MODIFY | Typ `alert_metric_channels` an Trip/Preset |
| `frontend/src/lib/i18n/messages/*` | MODIFY | DE/EN-Texte (ADR-0104) |
| Frontend-Tests (`node --test`) + Playwright-E2E | CREATE | Abbildung, Payload, Erhalt; `.tn-mobile`/`.tn-desktop` |
| `docs/reference/api_contract.md`, `docs/specs/modules/alert_metric_channels.md` | MODIFY | DTO-Doku, S3-Abschnitt |

### Scope Assessment
- Dateien: ~20 (davon ~14 Produktion)
- Geschätzte Produktions-LoC: S3a Backend ~60–80 · S3b UI ~220–250 (Komponente+Abbildung ~110, Trip ~60, Vergleich ~60–80)
- Risiko: **MITTEL-HOCH** — ändert die Versand-Auflösung (Rückfall) und berührt beide Speicherwege inkl. Snapshot/Rollback.
- **LoC-Limit gemessen:** 250 je Workflow (`docs/reference/workflow_und_agenten.md:49`; nur `docs/`/`*.md` zählen nicht). S3 gesamt liegt mit ~300 Produktions-LoC plus Tests klar darüber.
- **Zuschnitt-Empfehlung:** Lieferung in zwei Teilen, Reihenfolge Pflicht: **S3a** (Leser-Rückfall + ADR-Nachtrag + Go-Angleichung `alert_metric_channels` + Onset-Lücke in `/api/metrics` + zeilenweiser Wirk-Test) **vor** **S3b** (UI). Reißt S3b das Limit: S3b1 Komponente + Trip, S3b2 Vergleich + Anlegemasken. Festlegung (ein Workflow mit `loc_limit_override` vs. getrennte Workflows) in `/30-write-spec`; Empfehlung: getrennte Workflows, dieser hier = S3a.

### Technical Approach
1. S3a zuerst: der Metrik-Arm kann nach Tarif-Gates nicht mehr ins Leere laufen (Leser-Rückfall); Restrisiken fehlender Empfänger und Kanal-Schwelle sind benannt (E7b) und bekommen eigene ACs.
2. Schlüsselmenge an genau einer Stelle (Python); `/api/metrics` liefert die Zeile → Schlüssel-Zuordnung vollständig (inkl. Onset); zeilenweiser Wirk-Test in Python.
3. UI als eigener Block je Katalog-Größe im geteilten AlarmeTab, Doppelmuster wie Kanal-Schwellen (#1461): route = `$state` + Dirty-JSON im EINEN Save-`$effect`; vergleich = Wertprop + `onAlarmFeldSetzen`. Teil-PUT sendet je geänderter Größe den vollständigen Eintrag bzw. `null`.
4. Mutations-Gegenprobe an der Wirkstelle: ein im Editor gesetzter Kanal ändert den Versandkanal im Leser (R1).

### Dependencies
- Upstream: `_ALERT_METRIC_TO_CATALOG_ID`, Katalog `/api/metrics`, Tarif-Gate, Go `mergeConfigMap`.
- Downstream: Trip-Versand `trip_alert.py:2509`, Vergleich `compare_alert.py:601`; S4 (Rückbau `alert_rules`) setzt S3 voraus.

### Open Questions
- Keine PO-Fragen (alle Punkte technisch, ADR-konform entschieden; E7 als ADR-Nachtrag dokumentieren).
- Für `/30-write-spec`: Zuschnitt S3a/S3b in einer Spec oder zwei Workflows; Komponenten-Name; Hinweistexte DE/EN.
