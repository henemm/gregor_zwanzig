---
entity_id: feat_2792_s1_profil_ampel
type: module
created: 2026-11-04
updated: 2026-11-04
status: approved
version: "1.0"
tags: [ampel, profil, vorlagen, migration, renderer, sms, telegram, mail, i18n, epic-2791]
---

# Beidseitige Profil-Ampel im Datenmodell, in allen Renderern und per Migration (S1, #2792)

## Approval

- [x] Approved (PO-Freigabe 2026-11-04 per Rückfrage: „Freigabe“)

## Purpose

Heute bewertet eine globale, nur teils beidseitige Ampel (`display_thresholds`, 10 Metriken, für alle Nutzer gleich) das Briefing, während SMS/Premium-SMS/Telegram eine zweite Bewertung (`sms_threshold`) und der Wertebereich (`corridors`) eine dritte lesen. S1 führt die **Profil-Ampel** aus ADR-0106 ein: eine beidseitige Vier-Stufen-Ampel je Metrik, die aus einer der 7 Vorlagen kommt, je Trip/Ort änderbar ist und von **allen** Lesern (Mail HTML/Plain/Compact, Ausblick, Vergleich, Alarm-Stunden, SMS, Premium-SMS, Telegram) gelesen wird. Bestandsdaten werden per Batch-Migration übernommen, nichts geht verloren.

Entscheidungsgrundlage: ADR-0106 (Akzeptiert 2026-11-04) mit P1 (CAPE geht wie heute in die Gewitterstufe ein, keine eigene Farbe), P2 (Gewitter „leicht“ fest gelb), P3 (Altstufen, gehört zu S2); PO-Entscheidungen E1 (SMS-Schwellwerte werden nicht übernommen, SMS hebt ab Gelb der Ampel hervor) und E2 (alte Felder bis S3a gesperrt, nicht still wirkungslos); Fachdaten `docs/context/einstellungen_neu.md` §4.4; Code-Befunde `docs/context/feat-2792-s1-profil-ampel.md`.

**Nicht Teil von S1:** Alarm-Logik (S2 #2793, `alarm_ab` wird nur gespeichert), neue Bedienoberfläche (S3a/S3b), relative Höhen und weitere Metriken (S7 #2799).

## Source

- **Files:** `src/app/ampel.py` (neu), `src/app/ampel_templates.py` (neu), `src/app/models.py`, `src/app/loader.py`, `src/app/metric_catalog.py`, `src/output/metric_format.py`, `src/output/renderers/**`, `src/output/tokens/**`, `src/services/alert/**`, `scripts/migrate_2792_profil_ampel.py` (neu), `internal/model/metric_preset.go`, `internal/handler/**`
- **Identifier:** `ampel_for(subscription)`, `validate_ampel(ampel)`, `thunder_color(level, ampel)`, `deviation_count(ampel)`

> **Schicht-Hinweis:** Python-Core (Wetter-Domäne, alle Renderer, Migration), Go-API (nur `MetricPreset`-Feld, Validierung beim Speichern, Fehlertext), Frontend (nur Sperre der Altfelder und Hinweistext, kein neuer Editor). Go-Modelle `Trip`/`ComparePreset` bleiben unverändert: die Ampel liegt **unter `display_config`** (Go reicht `DisplayConfig map[string]interface{}` durch).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Datenmodell, Auflösung `ampel_for` und Validierung sind **ein** Code für beide Kontexte. Die Sperre der Altfelder liegt in den geteilten Komponenten unter `frontend/src/lib/components/shared/` (Parameter `context="route"|"vergleich"`), keine neue Compare-Komponente. Compare-eigen ist nur das Bauen der Listen je Render im Compare-Mail-Template.
> - **Mandantentrennung:** Migration und Speichern laufen je Nutzer unter `data/users/<user_id>/`; getestet mit zwei verschiedenen Nutzern, nie Fallback `"default"`.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS lesen dieselbe Ampel (ADR-0095); Alarm-Mail und Alarm-Telegram nutzen sie für die Stundenfärbung.

## Estimated Scope

Lieferung in **drei Schritten, je eigener PR mit allen 6 CI-Checks** (`test` · `lint` · `go-test` · `svelte-check` · `frontend-test` · `e2e`), unter dieser einen Spec. Reihenfolge laut Playbook: erst Lese-Code (S1a), dann Migration (S1b), dann Umschalten der Leser (S1c).

| Schritt | Inhalt | LoC (grob, inkl. Tests, Skript, Datentabellen) | ACs |
|---|---|---|---|
| **S1a** | Datenmodell, Vorlagen-Grenzen, Validierung, `ampel_for`, Go-`MetricPreset`, Compare-Profil-Zuordnung. Ausgabe unverändert (noch liest niemand `ampel_for`). | ca. 450 | AC-13, AC-14, AC-15 (nur Auflösung `profil` → Vorlage), AC-16, AC-18 |
| **S1b** | Migrationsskript (Probelauf, `--execute`, Sicherung, wiederholbar). | ca. 400 | AC-8 bis AC-12, AC-17 |
| **S1c** | Alle Leser auf `ampel_for`, Gewitter zentral, CAPE-Farbe entfernt, SMS-Hervorhebung aus Ampel, Sperre der Altfelder, Tests umgestellt. | ca. 650 | AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19 bis AC-22 |

- **Gesamt:** ca. 1500 LoC, ca. 35 Dateien. **Effort:** high.
- **loc_limit_override:** in jedem der drei Schritte erwartet (Limit 250; Tests, Datentabellen und `scripts/` zählen mit). Vor `/50` je Schritt mit `workflow.py status` gegenlesen und `loc_limit_override` setzen (Richtwerte S1a 500, S1b 450, S1c 700; `*.md` zählt nicht).
- **Schema-Hook:** Edits an `internal/model/`, `src/app/models.py`, `src/app/loader.py` lösen `data_schema_backup.py` aus (erwartet, kein Fehler).

## Affected Files

### Python-Core

| File | Change | Beschreibung | Schritt |
|---|---|---|---|
| `src/app/ampel_templates.py` | CREATE | Grenzen der 7 Vorlagen (Datenstruktur, Quelle `einstellungen_neu.md` §4.4) | S1a |
| `src/app/ampel.py` | CREATE | `validate_ampel`, `ampel_for`, `deviation_count`, `thunder_color`, Profil-Zuordnung | S1a |
| `src/app/models.py` | MODIFY | `UnifiedWeatherDisplayConfig.ampel: Optional[dict]` | S1a |
| `src/app/loader.py` | MODIFY | Ampel lesen/schreiben (Muster `loader.py:1839`), ungültige Ampel loggen und verwerfen, merge-sicher | S1a |
| `src/app/metric_catalog.py` | MODIFY | `display_thresholds` liefert danach nur Vorgaben der Vorlage „allgemein“; CAPE-Schwellen entfallen | S1a/S1c |
| `api/routers/config.py` | MODIFY | `GET /templates` liefert zusätzlich `ampel` je Vorlage | S1a |
| `scripts/migrate_2792_profil_ampel.py` | CREATE | Batch-Migration | S1b |
| `src/output/metric_format.py` | MODIFY | `severity_for` nimmt Ampel-Dict statt Katalog; `thunder_ampel_band` wird die zentrale Gewitter-Abbildung | S1c |
| `src/output/renderers/email/{html,plain,compact,helpers,outlook,compare_html}.py`, `src/output/renderers/comparison.py` | MODIFY | Leser umschalten (Abschnitt 5) | S1c |
| `src/output/tokens/{builder,metrics}.py`, `src/output/renderers/sms_trip.py`, `src/output/renderers/telegram/narrow.py` | MODIFY | Hervorhebung „@14“ aus Ampel statt `sms_threshold` | S1c |
| `src/services/alert/{hours,project,render}.py` | MODIFY | Stunden-Staging mit Ampel des Abos; `AlertMessage` trägt die Ampel | S1c |
| `src/services/trip_command_processor.py` | MODIFY | Gewitter-Dublette `_BAND_EMOJI` über zentrale Abbildung | S1c |
| Tests (Abschnitt Test Plan) | CREATE/MODIFY | | S1a-c |

### Go-API

| File | Change | Beschreibung | Schritt |
|---|---|---|---|
| `internal/model/metric_preset.go` | MODIFY | neues Feld `Ampel map[string]interface{}` (enthält Grenzen, Gewitter und `alarm_ab` je Metrik); Read-Modify-Write-Merge beim Speichern | S1a |
| `internal/handler/` (MetricPreset-Handler, Trip-/Compare-PUT) | MODIFY | `validateAmpel` beim Speichern; Fehlercode `ampel_ungueltig` | S1a |
| `internal/i18n/messages/{de,en}/fach.json` | MODIFY | Fehlertext `fach.fehler.ampel_ungueltig` DE+EN | S1a |
| `internal/model/trip_schema_drift_test.go`, `tests/test_trip_schema_drift.py` | MODIFY | Drift-Gate kennt `display_config.ampel` | S1a |

### Frontend (nur Sperre der Altfelder, E2)

| File | Change | Beschreibung | Schritt |
|---|---|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | SMS-Schwellwert-Regler (Sensibel/Standard/Robust) nur lesbar + Hinweis | S1c |
| geteilter Wertebereiche-Tab unter `frontend/src/lib/components/shared/` | MODIFY | gesamter Reiter nur lesbar + Hinweis, `context="route"\|"vergleich"` | S1c |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` (SMS-Hinweis ggf. `trip.json`) | MODIFY | Hinweistext | S1c |
| `frontend/src/lib/i18n/__tests__/**`, Komponententests | MODIFY | Paritätstest bleibt grün; Test der Sperre | S1c |

### Dokumentation

| File | Change | Beschreibung |
|---|---|---|
| `docs/reference/api_contract.md` | MODIFY | SSOT: `display_config.ampel` (MetricConfig/Weather Config §11, Trip §10.5, ComparePreset §16), MetricPreset §15.5 (neues Feld), `GET /templates`, Fehlercode `ampel_ungueltig`; Corridor §24 und `sms_threshold` als „ohne Wirkung, erhalten“ vermerkt |
| `docs/reference/sms_format.md`, `telegram_format.md`, `premium_sms_format.md` | MODIFY | Hervorhebung „@14“ = erste Stunde gelb oder schlechter laut Ampel |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0106 | Entscheidung | Ampel als einzige Bewertung; P1, P2, P3 |
| ADR-0104 | Entscheidung | Zweisprachigkeit, Texte nur über Katalog |
| ADR-0095 | Entscheidung | Kanal-Parität, alle vier Kanäle |
| ADR-0101 / ADR-0083 | Entscheidung | Daten-Schema-Rework: Read-Modify-Write mit Merge |
| ADR-0025, ADR-0057 | Entscheidung | Eine Gewitter-Quelle; CAPE geht über die geeichte Leiter in die Gewitterstufe |
| `severity_from_thresholds` (`src/output/metric_format.py:152`) | Funktion | Bleibt der einzige Vergleichs-Kern, beidseitig, Form `yellow/orange/red` + `*_lt` |
| `scripts/migrate_1231_corridors.py`, `migrate_2454_derived_children.py` | Vorbild | Muster Probelauf, `--execute`, tar.gz-Sicherung |
| `docs/context/einstellungen_neu.md` §4.4 | Fachdaten | Grenzen aller 7 Vorlagen (SSOT für `ampel_templates.py`) |
| #2793 (S2), S3a/S3b, #2799 (S7) | Folgearbeit | lesen `alarm_ab`, bauen Oberfläche, ergänzen Metriken |

## Implementation Details

### 1. Datenmodell

`display_config.ampel` (Trip und Compare identisch; Trip parst in `UnifiedWeatherDisplayConfig.ampel`, Compare bleibt Dict):

```
ampel = {
  template: "<vorlagen-id>",     # alpen-trekking|wandern|skitouren|wintersport|radtour|wassersport|allgemein|<eigene>
  metrics: { "<metric_id>": {
      enabled: bool,
      lower: {red: n|null, orange: n|null, yellow: n|null},   # rot < orange < gelb
      upper: {yellow: n|null, orange: n|null, red: n|null},   # gelb < orange < rot
      alarm_ab: "never"|"yellow"|"orange"|"red" } },
  thunder: { mittel: "yellow"|"orange"|"red", hoch: "orange"|"red" }
}
```

- `null` = offene Seite bzw. offene Grenze. `alarm_ab` wird in S1 nur gespeichert und durchgereicht (Leser kommt in S2); die Werte sind Protokoll-Token und werden nie übersetzt.
- **Teilmenge erlaubt:** eine Abo-Ampel darf nur abweichende Metriken enthalten; fehlende Metriken lösen sich über die Vorlage auf. **Abweichungszahl** = Anzahl der Metriken (plus Gewitter), deren `lower`/`upper`/`thunder` von der Vorlage abweichen (`deviation_count`, abgeleitet, nicht gespeichert).
- **Validierung** (`validate_ampel`, gleiche Regeln in Python und Go): unten `red < orange < yellow`, oben `yellow < orange < red` (jeweils über die gesetzten Werte), `lower.yellow <= upper.yellow` (untere Grenzen nie über den oberen), `alarm_ab` aus der Menge, Gewitter `hoch` nie gelb und nie schwächer als `mittel`. Ein ungültiges Objekt wird beim Speichern mit Code `ampel_ungueltig` und Meldung in der Anfragesprache abgelehnt (Go); beim Laden wird eine ungültige Ampel protokolliert (`# i18n-log`) und durch die Vorlage ersetzt.
- **Speichern:** Die Ampel wird als **ganzer Unterbaum** ersetzt (der Client sendet die vollständige Ampel). Grund: `mergeConfigMap` (`config_merge.go:11`) ist nur eine Ebene tief, ein Teil-PUT würde den Unterbaum ohnehin ersetzen; ein tiefer Merge würde gelöschte Grenzen wiederbeleben. Alle übrigen `display_config`-Felder bleiben per Read-Modify-Write erhalten; Python schreibt die Ampel beim Speichern mit (Muster `loader.py:1839`), sonst löscht ein Python-Speichern sie (ADR-0083).

### 2. Vorlagen und eigene Vorlagen

- `src/app/ampel_templates.py` hält je Vorlage dieselbe Struktur wie `ampel.metrics`/`thunder`, gespeist aus `einstellungen_neu.md` §4.4 (Tabellen je Vorlage; **nicht** hier dupliziert). Beispielzeilen:
  - Allgemein, `gust`: `upper {yellow: 30, orange: 45, red: 60}`, `lower` offen, `alarm_ab: "orange"`.
  - Skitouren, `temperature`: `lower {red: -30, orange: -20, yellow: -15}`, `upper {yellow: 3, orange: 8, red: 15}`, `alarm_ab: "orange"`.
  - Wassersport, `wind`: `lower {red: null, orange: 4, yellow: 8}`, `upper {yellow: 30, orange: 40, red: 50}`; `thunder {mittel: "red", hoch: "red"}`.
- **Vergleichsoperatoren bleiben wie heute** (`severity_from_thresholds`): oben `Wert >= Grenze`, unten `Wert < Grenze`. Die Tabellenköpfe „gelb >“ in §4.4 meinen dieselbe Grenze in dieser Form; nur so bleibt „Allgemein“ byte-gleich.
- **Vorlage „allgemein“ = heutiges `display_thresholds`:** Temperatur 28/31/34 und -15/-5/0, Wind 30/50/70, Böen 30/45/60, Niederschlag 1/5/10, Regenwahrscheinlichkeit 30/60/80, Sichtweite 2000/1000/500, UV 3/6/8, Neuschnee 10/20/30, gefühlte Temperatur wie Temperatur, Gewitter mittel=orange, hoch=rot. Ein Test erzwingt die Gleichheit (Ratsche, nie lockern). **Einzige Ausnahme:** die CAPE-Farbe entfällt (P1).
- **Zeilen ohne heutigen Leser** (z. B. Bewölkung, Taupunkt, Sonnenstunden, Nullgradgrenze, Schneehöhe, Tiefsttemperatur Nacht) werden in den Daten gehalten, aber in S1 von **keinem** Renderer gelesen; sonst wäre die Ausgabe für „Allgemein“ nicht byte-gleich. Sie werden in S7 aktiviert.
- **`enabled` in der Ampel** spiegelt die Briefing-Auswahl der Vorlage (Datenhaltung für eigene Vorlagen); in S1 bleibt `MetricConfig.enabled` die wirksame Auswahl.
- **Auflösung `ampel_for(subscription)`** liefert je Metrik das Schwellen-Dict in der Form von `severity_from_thresholds` (`yellow/orange/red`, `yellow_lt/orange_lt/red_lt`): (1) Ampel des Abos, sonst (2) Vorlage `ampel.template` bzw. Trip `display_config.preset_name`, sonst (3) Vorlage „allgemein“. Unbekannte Vorlage-ID: „allgemein“, Warnung ins Log. Eigene Vorlagen (Go) werden beim Anwenden als Ampel ins Abo kopiert; `ampel_for` kennt nur Abo und eingebaute Vorlagen.
- **Eigene Vorlagen (Go `MetricPreset`, `data/users/<uid>/metric_presets.json`):** speichern zusätzlich die Ampel samt `alarm_ab` je Metrik, neben der bisherigen Auswahl. Sie speichern **nicht** Zustellung, Etappen, Orte. Anwenden kopiert Auswahl + Ampel + `alarm_ab` ins Abo und lässt Zustellung und Etappen unverändert. Bestehende Presets ohne Ampel laden unverändert (kein Feld = Vorlage „allgemein“); Speichern per Read-Modify-Write mit Merge. `SavePresetDialog.svelte` bleibt in S1 unverändert; die Bedienung folgt in S3.

### 3. Compare-Vorlage

Der Compare erhält Vorlagen (Datenteil): `display_config.ampel.template` des `ComparePreset`. Fehlt es, bestimmt `profil` die Vorlage (`ampel.py`, case-insensitive): `summer_trekking` → `alpen-trekking`; `wandern`, `wintersport`, `allgemein` gleichnamig; weitere eingebaute Vorlagen-IDs werden direkt akzeptiert; unbekannter Wert → `allgemein`, Warnung ins Log. Die Zelle „Profil“ im Compare-Mail-Kopf (`profile_signature`, `compare_html.py:1746`) zeigt das Label der aufgelösten Vorlage (`WEATHER_TEMPLATES[...].label`). Das Scoring (`calculate_score`) bleibt an `profil` gebunden.

### 4. Migration (S1b) — `scripts/migrate_2792_profil_ampel.py`

- **Ablauf:** Standard = Probelauf (schreibt nichts, Bericht je Nutzer); `--execute` schreibt. Vor dem Schreiben je Nutzer ein `tar.gz` der betroffenen Dateien (Trips, Compare-Presets, `metric_presets.json`). **Wiederholbar:** ein zweiter Lauf ändert nichts (vorhandene Ampel wird nie überschrieben, fehlende Teile werden ergänzt). Alle anderen Felder bleiben **byte-gleich** (Read-Modify-Write mit Merge, nie Replace).
- **Vorlage bestimmen:** Trip: `display_config.preset_name`; Compare: `profil` (Abschnitt 3); sonst `allgemein`.
- **Wertebereiche `corridors` mit `mark=True`** (Band `[von, bis]`) → grünes Fenster der Ampel:
  - `von` → `lower.yellow = von` (die Ampel prüft `Wert < yellow_lt`; `von` bleibt grün, wie im inklusiven Band).
  - `bis` → `upper.yellow = bis + Schritt` mit `Schritt` = kleinste angezeigte Stelle der Metrik (Temperatur 0,1; km/h und % 1; mm 0,1). Die Ampel prüft `Wert >= yellow`; der alte Randwert `bis` bleibt grün. Beispiel Temperatur `[0, 20]` → `lower.yellow = 0`, `upper.yellow = 20,1`.
  - Fehlt eine Seite (`null`), bleibt dort die Vorlage. `orange`/`red` kommen aus der Vorlage.
  - **Klemm-Regel:** wird die Reihenfolge verletzt (z. B. neues `yellow` ≥ Vorlagen-`orange`), wird die **ganze Seite** (orange und rot) um denselben Betrag verschoben, um den `yellow` von der Vorlage abweicht, bis die Reihenfolge stimmt; der Bericht nennt die Verschiebung. Bleibt die Validierung verletzt, wird die Metrik **nicht** migriert (Altdaten erhalten, Bericht „übersprungen: Grund“).
  - **Metrik-Zuordnung:** Trip `wind_gust`→`gust`, `precipitation_sum`→`precipitation`, `temperature_max`→`temperature` (nur `bis` → `upper.yellow`), `temperature_min`→`temperature` (nur `von` → `lower.yellow`; die jeweils andere Seite wird nicht übernommen und steht im Bericht), `snow_line`→`snowfall_limit` (nur Daten); Compare `temp_max_c`→`temperature`, `gust_max_kmh`→`gust`. Nicht zuordenbare Schlüssel: nicht migriert, Bericht.
- **`corridors` mit `notify=True, mark=False`** tragen Δ-Werte aus `alert_rules` und werden **nicht** abgebildet: unverändert erhalten und im Bericht protokolliert (Zuständigkeit S2).
- **`ideal_ranges`** nur als Rückfall, wenn für die Metrik kein `corridor` existiert; gleiche Abbildungsregel.
- **`sms_threshold`** wird **nicht** abgebildet (E1): bleibt in `metrics[]`, `channel_layouts` und `report_layouts` gespeichert und wird protokolliert (Metrik, Wert, Ort).
- **`horizons`** → alle Tage: in `metrics[]`, `channel_layouts`, `report_layouts` wird der Filter entfernt bzw. auf `{"today": true, "tomorrow": true, "day_after": true}` gesetzt.
- **CAPE:** eine gespeicherte Auswahl `cape` bzw. Compare `cape_max_jkg` → Metrik `thunder` aktiv (bestehende Einstellungen bleiben).
- **Unangetastet:** `metric_alert_levels`, `alert_rules`, `alert_preset` (S2). Eigene Vorlagen ohne Ampel bleiben unverändert (Bericht nennt sie).

### 5. Leser umschalten (S1c)

Alle Leser aus Context §3 nutzen `ampel_for(subscription)`; danach liest kein Leser `display_thresholds` als Nutzer-Bewertung:

- **Trip-Mail:** HTML, Plain, Compact einschließlich Kacheln (`build_metrics_summary_pills`, `_pill_for_metric`, `tone_symbol`), Stundentabelle (`fmt_val`, `_render_html_table`), Zeilen-Risiko `_row_risk`, Highlights `_compute_highlights`.
- **3-Tages-Ausblick** (`render_outlook_table`, Trip und Vergleich): nutzt die Ampel des Abos statt `_catalog_thresholds`; Temperatur wird beidseitig gefärbt.
- **Vergleichs-Mail:** Übersicht (`CV2_METRICS`) und Stundenverlauf (`HOUR_METRICS`, `_make_hour_sev`) sind statische Modul-Listen und werden **je Rendern** mit der Ampel des Presets gebaut.
- **Alarm-Mail und Alarm-Telegram:** `alert/hours.py` (`_stage`, `_is_affected`, `format_cell`) bekommt die Ampel des Abos beim Projizieren (`AlertMessage` trägt sie); die getrennte Skala `risk_thresholds` (Etappen-Risiko) bleibt unberührt.
- **SMS, Premium-SMS, Telegram „@14“:** `sms_threshold` und `DEFAULTS` wirken nicht mehr (E1). Hervorhebung = erste Stunde, in der die Metrik **gelb oder schlechter** ist, **beidseitig** (auch Unterschreiten der unteren Grenze); sonst „-“. `render_threshold_peak_value` und `_sms_mention_threshold` lesen die Ampel. Protokoll-Token (`sms_code`, `compact_label`) bleiben unverändert (`tests/test_metric_tokens_eingefroren.py`).
- **Gewitter zentral (P2):** `thunder_color(level, ampel)`: „keins“ grün, „leicht“ fest gelb, „mittel“/„hoch“ nach `ampel.thunder`. Die Dubletten `outlook._THUNDER_LEVEL_BG`, `outlook._metric_column_bg`, `html._thunder_risk_level`, `compare_html._sev_thunder` und `trip_command_processor._BAND_EMOJI` werden entfernt oder rufen diese eine Abbildung. **CAPE (P1):** keine eigene Farbe (`_ampel_dot_severity("cape")` entfällt); die Fusion zur Gewitterstufe (`thunder_level_from_signals`, `_fuse_thunder_levels`) bleibt unverändert.
- **Altfelder sperren (E2):** Reiter „Wertebereiche“ und die SMS-Schwellwert-Regler sind nur lesbar mit Hinweis aus dem Katalog: DE „Wird gerade umgebaut – deine Werte sind übernommen.“, EN „Being rebuilt – your values have been carried over.“ Werte werden angezeigt, aber nicht mehr geschrieben.

### Neue Nutzertexte (ADR-0104)

Alle neuen Nutzertexte in DE und EN über die Kataloge, Platzhaltermengen gleich: Hinweis „Wird gerade umgebaut …“ (Frontend), Fehler `fach.fehler.ampel_ungueltig` (Go; DE „Die Ampel ist ungültig: Die Grenzen müssen oben aufsteigend und unten absteigend angeordnet sein.“, EN „The traffic light is invalid: limits must increase on the upper side and decrease on the lower side.“), Vorlagen-Label im Compare-Kopf aus `WEATHER_TEMPLATES` (besteht). Protokoll-Token (`sms_code`, `compact_label`, `alarm_ab`-Werte, Vorlagen-IDs) werden nie übersetzt. Deutsche Golden-Ausgaben bleiben byte-gleich.

## Test Plan

Farben werden **am Entstehungsort** getestet (Renderer-Ausgabe, `ampel_for`, `thunder_color`), denn **kein Mail-Validator prüft Farben**. Validatoren bleiben unverändert: Trip-Mail `.claude/hooks/briefing_mail_validator.py`, Vergleichs-Mail `.claude/hooks/email_spec_validator.py` (beide gegen echt zugestellte Staging-Mail in `/e2e-verify`, Staging-Nutzer `de` und `en`). Das Renderer-Commit-Gate verlangt für S1c frisch grün: `tests/tdd/test_issue_811_mode_matrix.py` (Erwartungen von globalen Gelb-Schwellen auf Vorlage „allgemein“ umgestellt) und `briefing_mail_validator.py`; für die Vergleichs-Mail zusätzlich `email_spec_validator.py`.

### Automated Tests (TDD RED, Testnamen nach Verhalten)

- [ ] `tests/tdd/test_ampel_modell_und_aufloesung.py` (S1a): Validierung gültig/ungültig, Teilmenge, Abweichungszahl, Rückfallkette, „allgemein“ == heutiges `display_thresholds` ohne CAPE, Compare-Profil-Zuordnung inkl. unbekannt, Loader behält andere Felder.
- [ ] `internal/handler/ampel_validierung_test.go`, `internal/model/metric_preset_ampel_test.go` (S1a): Ablehnung `ampel_ungueltig` DE/EN, eigene Vorlage speichert/lädt Ampel+`alarm_ab` ohne Zustellung, zwei Nutzer isoliert.
- [ ] `tests/tdd/test_migration_2792_profil_ampel.py` (S1b): Probelauf, `--execute`, Wiederholung, Sicherung, zwei Nutzer, Δ-Bereich, `sms_threshold`, `horizons`, CAPE, byte-gleiche Restfelder, Klemm-Regel.
- [ ] `tests/tdd/test_profil_ampel_leser.py` (S1c): Farben je Leser (HTML-Tabelle, Kachel, Plain, Compact, Ausblick, Vergleichs-Übersicht, Vergleichs-Stundenverlauf, Alarm-Stunden) mit Skitouren-/Wassersport-/Allgemein-Ampel; zwei Presets nacheinander im selben Prozess.
- [ ] `tests/tdd/test_sms_hervorhebung_aus_ampel.py` (S1c): SMS, Premium-SMS, Telegram, beidseitig.
- [ ] `tests/tdd/test_gewitter_zentrale_abbildung.py` (S1c): alle Vorlagen, CAPE ohne Farbe.
- [ ] `frontend/src/lib/components/shared/__tests__/altfelder_gesperrt.test.ts` (S1c): beide Kontexte, DE/EN.
- [ ] Anpassung bestehender Tests (Context §3, 34 Dateien), u. a. `tests/test_ampel_schwellen_katalog.py`, `tests/tdd/test_compare_katalog_schwellen.py`, `tests/tdd/test_renderer_katalog_schwellen.py`, `tests/test_chip_ampel_farben.py`, `tests/test_ampel_farbabstufung.py`, `tests/tdd/test_metric_format.py`, `tests/unit/test_cape_ampel_thresholds.py`, `tests/tdd/test_outlook_metric_ampelfarben.py`, `tests/tdd/test_thunder_column_ampel.py`, `tests/tdd/test_gewitter_ampel_bandtreu.py`, `tests/tdd/test_issue_811_mode_matrix.py`: Erwartungen mit globalen Werten werden auf Vorlage „allgemein“ umgestellt; CAPE-Erwartungen entfallen mit Begründung (P1). **Keine Ratsche wird abgeschwächt**; die Paritäts-Ratsche prüft künftig Katalog-Vorgabe == Vorlage „allgemein“.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Vorlage Skitouren und ein Trip mit Vorlage Allgemein, beide mit Tageshöchsttemperatur +9 °C / When das Briefing als E-Mail, Telegram, SMS und Premium-SMS gerendert wird / Then ist +9 °C beim Skitouren-Trip in der E-Mail orange (Skitouren orange ab 8 °C) und in Telegram, SMS und Premium-SMS als Spitzenwert mit Stunde hervorgehoben (gelb oder schlechter); beim Allgemein-Trip ist +9 °C in der E-Mail grün und in den drei Kurzkanälen nicht hervorgehoben (gelb erst ab 28 °C)
  - Test: Render je Kanal mit beiden Abos, Farbe bzw. Hervorhebung am Entstehungsort geprüft (`test_profil_ampel_leser.py`, `test_sms_hervorhebung_aus_ampel.py`)
- **AC-2:** Given zwei Nutzer A und B mit Vorlage Skitouren (Böen gelb ab 40 km/h) / When Nutzer A die Böen-Gelbgrenze auf 42 km/h setzt und beide Briefings mit 41 km/h Böen gerendert werden / Then ist 41 km/h bei A grün, bei B gelb, und bei 42 km/h ist es auch bei A gelb
  - Test: zwei Nutzer, Speichern über Go-API, Render beider Briefings; B bleibt unverändert (Mandantentrennung)
- **AC-3:** Given ein Abo mit Vorlage Wassersport (Wind unten orange unter 4, gelb unter 8 km/h) / When Mittelwind 3 km/h bzw. 6 km/h bzw. 15 km/h gerendert wird / Then ist 3 km/h orange, 6 km/h gelb und 15 km/h grün
  - Test: beidseitige Auswertung der unteren Seite in Mail-Stundentabelle und Kachel
- **AC-4:** Given ein Abo mit Vorlage Skitouren (Temperatur oben rot ab 15 °C, unten rot unter -30 °C) / When die Temperatur +16 °C bzw. -31 °C beträgt / Then wird beides rot dargestellt, +10 °C orange und -17 °C gelb
  - Test: beide Seiten derselben Metrik in Stundentabelle, Kachel und 3-Tages-Ausblick
- **AC-5:** Given Abos mit jeder der 7 Vorlagen und die Gewitterstufen keins, leicht, mittel, hoch / When gerendert wird / Then ist „keins“ grün, „leicht“ in jeder Vorlage gelb, „mittel“ in Wassersport rot und in Allgemein orange, „hoch“ nach Vorlage orange oder rot, und alle früheren Gewitter-Dubletten (Ausblick, Tabelle, Vergleich, Telegram-Emoji) liefern dieselbe Farbe
  - Test: ein Test über alle Vorlagen und alle Orte der Gewitterfarbe, Telegram-Emoji gegen Mail-Farbe
- **AC-6:** Given ein Trip mit CAPE 1600 J/kg und gespeicherter CAPE-Auswahl / When Mail und Vergleich gerendert werden / Then trägt der CAPE-Wert keine eigene Farbe (kein Punkt, kein Hintergrund), und die Gewitterstufe wird weiter über die geeichte Fusion (`thunder_level_from_signals`) berechnet und gefärbt
  - Test: CAPE-Zelle neutral, Gewitterzeile unverändert zu vorher
- **AC-7:** Given ein Abo mit Wind-Gelbgrenze 30 km/h, früher gespeichertem `sms_threshold` 20 und stündlichen Windwerten / When der höchste Wert 25 km/h beträgt / Then zeigen SMS, Premium-SMS und Telegram keinen Spitzenwert („-“); bei 31 km/h um 14 Uhr erscheint der Wert mit Stunde „@14“; ebenso erscheint bei Vorlage Wassersport Wind 3 km/h (unter der unteren Gelbgrenze 8) als Spitzenwert mit Stunde
  - Test: Render der drei Kanäle, `sms_threshold` bleibt gespeichert und wirkt nicht mehr (E1), beide Seiten geprüft
- **AC-8:** Given ein Trip mit Wertebereich Temperatur `[0, 20]` (`mark=True`) und Vorlage Wandern / When die Migration mit `--execute` läuft / Then enthält die Ampel für Temperatur `lower.yellow = 0` und `upper.yellow = 20,1` (20,0 °C bleibt grün, 20,1 °C ist gelb), `orange` und `red` kommen aus der Vorlage Wandern, und bei verletzter Reihenfolge wird die Seite verschoben und der Bericht nennt die Verschiebung
  - Test: Migrationslauf auf einer Kopie, anschließend Render mit 20,0 und 20,1 °C
- **AC-9:** Given ein Trip mit Bereich `notify=True, mark=False` (Δ-Wert 5 für Böen) / When die Migration läuft / Then bleibt dieser Bereich unverändert im Trip erhalten, wird keine Ampel-Grenze daraus, und der Bericht nennt Metrik und Wert
  - Test: Datei vor/nach, Berichtseintrag
- **AC-10:** Given Metriken mit gespeichertem `sms_threshold` (Wind 20) in `metrics`, `channel_layouts` und `report_layouts` / When die Migration läuft / Then bleiben alle drei Werte erhalten, der Bericht listet jeden mit Metrik und Ort, und die Ampelgrenze für Wind bleibt die der Vorlage
  - Test: Datei vor/nach, Bericht
- **AC-11:** Given Trips und Compare-Presets mit `horizons` `{"today": true, "tomorrow": false, "day_after": false}` in `metrics`, `channel_layouts` und `report_layouts` sowie eine CAPE-Auswahl / When die Migration läuft / Then sind danach alle drei Tage aktiv bzw. der Filter entfernt, die Metrik Gewitter ist aktiv, und das Briefing zeigt alle drei Tage
  - Test: Migration auf Kopie, Render der Stundentabelle für alle Tage
- **AC-12:** Given zwei Nutzer mit je mehreren Trips und einem Compare-Preset (Profil `summer_trekking`) / When die Migration im Probelauf, danach mit `--execute` und ein zweites Mal mit `--execute` läuft / Then schreibt der Probelauf keine Datei (Prüfsummen gleich), der erste `--execute` legt vorab ein `tar.gz` je Nutzer an und liefert je Nutzer einen Bericht, der zweite `--execute` ändert keine Datei, und alle nicht genannten Felder sind byte-gleich zu vorher
  - Test: Prüfsummenvergleich über beide Nutzerverzeichnisse, Sicherung entpackbar
- **AC-13:** Given ein Trip ohne `display_config.ampel` und mit `preset_name` `skitouren` / When `ampel_for` aufgerufen wird / Then liefert sie die Skitouren-Grenzen (Böen gelb 40); fehlt auch der Name, die Grenzen der Vorlage Allgemein (Böen gelb 30), und bei einer unbekannten Vorlage ebenfalls Allgemein mit einer Warnung im Log
  - Test: reine Funktion, drei Stufen der Rückfallkette
- **AC-14:** Given eine eigene Vorlage „Mein Gipfel“ aus Auswahl, Ampel (Wind gelb 25) und `alarm_ab` „yellow“ / When sie gespeichert und auf einen anderen Trip angewendet wird / Then trägt der Ziel-Trip Auswahl, Ampel und `alarm_ab` der Vorlage, seine Zustellung (Empfänger, Kanäle) und seine Etappen bleiben unverändert, und eine zuvor vorhandene eigene Vorlage ohne Ampel lädt weiter fehlerfrei
  - Test: Go-Handler Speichern/Anwenden, Vorher-/Nachher-Vergleich der Zustellungsfelder
- **AC-15:** Given ein Compare-Preset mit `profil` „summer_trekking“ ohne gespeicherte Vorlage / When die Vergleichs-Mail gerendert wird / Then ist die aufgelöste Vorlage `alpen-trekking` und die Zelle „Profil“ im Mail-Kopf zeigt deren Label; ein Preset mit `profil` „WANDERN“ ergibt `wandern` (Groß-/Kleinschreibung egal), ein unbekanntes Profil ergibt `allgemein`
  - Test: Rendern der Mail-Kopfzeile für drei Profile
- **AC-16:** Given eine Ampel mit Böen `upper.yellow` 50 und `upper.orange` 45 / When sie über die Go-API gespeichert wird / Then lehnt die API mit Code `ampel_ungueltig` ab, die Meldung steht in der Anfragesprache (DE „Die Ampel ist ungültig …“ bzw. EN „The traffic light is invalid …“) und die gespeicherte Ampel bleibt unverändert; ebenso abgelehnt wird eine untere Gelbgrenze über der oberen
  - Test: PUT Trip, Compare und Eigene Vorlage mit `Accept-Language` de und en
- **AC-17:** Given ein Trip mit `preset_name` „skitouren“ und ein Compare-Preset mit Profil „wintersport“ / When die Migration läuft / Then tragen beide `display_config.ampel.template` (`skitouren` bzw. `wintersport`), die Auflösung ergibt dieselben Grenzen wie die Vorlage, und `metric_alert_levels` und `alert_rules` sind unverändert
  - Test: Datei vor/nach für Alarmfelder, `ampel_for` nach Migration
- **AC-18:** Given die Vorlage „allgemein“ in `ampel_templates.py` / When sie mit dem bisherigen `display_thresholds` verglichen wird / Then sind alle Grenzen der 10 bisherigen Metriken gleich, mit Ausnahme der CAPE-Grenzen, die entfallen
  - Test: Paritäts-Ratsche Katalog-Vorgabe == Vorlage „allgemein“
- **AC-19:** Given Trip-Briefing, Vergleichs-Mail und Alarm-Mail eines Abos mit Vorlage Allgemein und Werten aus den bisherigen Golden-Fixtures / When gerendert wird / Then ist die Ausgabe byte-gleich zu vorher, außer den drei bewusst vereinheitlichten Stellen: (a) die CAPE-Farbe entfällt (P1), (b) die Temperatur im 3-Tages-Ausblick wird nach der Ampel gefärbt (bisher nie), (c) die Gewitterfarbe der früheren Dubletten folgt der zentralen Abbildung (z.B. eigenes Hellgelb im Ausblick, „keins“ im Vergleich jetzt grün); jede dieser Abweichungen ist im Golden-Vergleich einzeln benannt
  - Test: Golden-Vergleich vor/nach, zusätzlich `test_issue_811_mode_matrix.py` und die Validatoren für Trip und Compare in `/e2e-verify` mit Exit 0
- **AC-20:** Given zwei Compare-Presets mit Vorlage Skitouren und Allgemein, nacheinander im selben Prozess gerendert, Temperatur +9 °C / When Übersicht und Stundenverlauf gerendert werden / Then ist +9 °C beim Skitouren-Preset orange und beim Allgemein-Preset grün, unabhängig von der Reihenfolge
  - Test: Rendern in beiden Reihenfolgen, keine Zustandsübernahme der Modul-Listen
- **AC-21:** Given eine Alarm-Mail und ein Alarm-Telegram für ein Abo mit Vorlage Skitouren und eines mit Vorlage Allgemein, jeweils mit Böen 52 km/h / When die Stundenzeilen erzeugt werden / Then ist 52 km/h beim Skitouren-Abo gelb (Skitouren orange erst ab 55) und beim Allgemein-Abo orange (orange ab 45), jeweils nach Abo-Ampel statt globalem Katalog
  - Test: Projektion und Rendern beider Kanäle mit beiden Abos
- **AC-22:** Given ein Nutzer öffnet den Reiter Wertebereiche und die SMS-Schwellwerte im Reiter Wetter, in Trip und Vergleich / When die Seite in Deutsch bzw. Englisch angezeigt wird / Then sind die Felder nur lesbar, zeigen die gespeicherten Werte, und der Hinweis lautet DE „Wird gerade umgebaut – deine Werte sind übernommen.“ bzw. EN „Being rebuilt – your values have been carried over.“
  - Test: Komponententest für beide Kontexte und beide Sprachen; Paritätstest der Kataloge grün

## Known Limitations

- **Alarm-Logik unverändert** (S2): `alarm_ab` wird gespeichert, aber nicht gelesen; Alarm-Trigger, `metric_alert_levels`, `alert_rules` und CAPE-Δ-Alarm bleiben bis S2 wie heute.
- **Neue Bedienoberfläche** (S3a/S3b): in S1 nur Sperre der Altfelder; die Ampel ist noch nicht im Editor bearbeitbar (Änderungen laufen über API und Migration).
- **Relative Höhen und weitere Metriken** (S7): Nullgradgrenze, Schneefallgrenze (relativ), Taupunkt, Sonnenstunden, Schneehöhe, Bewölkung u. a. liegen in den Vorlagendaten, haben in S1 aber keinen Leser.
- **E1-Folge:** schwache Werte unter Gelb (Wind 25 bei Gelb 30) erscheinen in SMS/Telegram nicht mehr als Spitzenwert, bewusst.
- **Sichtbare Vereinheitlichung für alle Nutzer** (auch Vorlage Allgemein): CAPE ohne Farbe, Temperatur im 3-Tages-Ausblick gefärbt, eine Gewitterfarbe überall (AC-19).
- **Klemm-Regel und `Schritt`** der Migration sind Näherungen; nicht abbildbare Metriken bleiben mit ihrem Altwert erhalten und stehen im Bericht.
- **Go-Top-Level-Felder** von `Trip`/`ComparePreset` bleiben unverändert; neue Daten nur unter `display_config` (Pass-through) und im `MetricPreset`.
- **Scoring** im Compare bleibt an `profil` gebunden; die uneinheitlichen Profil-Wertebereiche (Python 4, Go 4, Vorlagen 7) werden nicht vereinheitlicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0106 (Akzeptiert 2026-11-04)
- **Rationale:** S1 setzt die Entscheidung um (eine Ampel je Metrik, Vorlage → Abo → Leser); keine weitere Grundsatzentscheidung nötig. Die hier festgelegten Umsetzungsdetails (Speichern als ganzer Unterbaum, Migrationsregeln) ändern nichts an ADR-0106.

## Changelog

- 2026-11-04: Initial spec created (Issue #2792, Epic #2791, Scheibe S1)
- 2026-11-04: PO-Freigabe (approved)
- 2026-11-04: Review Tech Lead: AC-1 Kurzkanäle als Hervorhebung, Temperatur-Zuordnung der Migration eindeutig, AC-19 Ausnahmen ehrlich benannt
