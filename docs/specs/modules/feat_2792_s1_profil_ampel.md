---
entity_id: feat_2792_s1_profil_ampel
type: module
created: 2026-11-04
updated: 2026-11-07
status: draft
version: "1.6"
tags: [ampel, profil, vorlagen, migration, renderer, sms, telegram, mail, i18n, epic-2791]
---

# Beidseitige Profil-Ampel im Datenmodell, in allen Renderern und per Migration (S1, #2792)

## Approval

- [x] Approved (PO-Freigabe 2026-11-04 per Rückfrage: „Freigabe“)
- [x] Approved v1.4, automatisch freigegeben am 2026-11-06 im Lauf `feat-2792-s1c4-umschalten` (Ampel grün im PO-Briefing, gebunden an spec_sha256 `66dc858d…`) (S1c-Ergänzungen v1.1: Schnitt in vier PRs, Migrations-Nachtrag AC-23, AC-19 (d), Pfadkorrekturen; v1.2: Schlüsselnamen `wind_chill_*_c` korrigiert, Schlüsselliste vollständig, Ratsche; v1.3: Nachtrag S1c-3, Umfang der Sperre, Hinweis-Positionen, Datenerhalt; v1.4: Nachtrag S1c-4, Schnitt 4a/4b, AC-19 (e)/(f), AC-15 Label-Quelle, Leser-Pflichten, AC-25 bis AC-27, Prod-Wirkung)
- [x] Approved v1.5, automatisch freigegeben am 2026-11-06 im Lauf `feat-2792-s1c4b-umschalten` (Ampel grün im PO-Briefing) (Nachtrag S1c-4b: Korrektur der Trip-ohne-`display_config`-Zusage in §5 Punkt 1 und AC-25, Präzisierungen zum Umschalten, RED-Pflichten aus dem 4a-Lauf)
- [x] v1.6: PO-Entscheid 2026-11-07 (Temperatur färbt in der Trip-Stundentabelle nach der Ampel wie jede andere Metrik)

## Purpose

Heute bewertet eine globale, nur teils beidseitige Ampel (`display_thresholds`, 10 Metriken, für alle Nutzer gleich) das Briefing, während SMS/Premium-SMS/Telegram eine zweite Bewertung (`sms_threshold`) und der Wertebereich (`corridors`) eine dritte lesen. S1 führt die **Profil-Ampel** aus ADR-0106 ein: eine beidseitige Vier-Stufen-Ampel je Metrik, die aus einer der 7 Vorlagen kommt, je Trip/Ort änderbar ist und von **allen** Lesern (Mail HTML/Plain/Compact, Ausblick, Vergleich, Alarm-Stunden, SMS, Premium-SMS, Telegram) gelesen wird. Bestandsdaten werden per Batch-Migration übernommen, nichts geht verloren.

Entscheidungsgrundlage: ADR-0106 (Akzeptiert 2026-11-04) mit P1 (CAPE geht wie heute in die Gewitterstufe ein, keine eigene Farbe), P2 (Gewitter „leicht“ fest gelb), P3 (Altstufen, gehört zu S2); PO-Entscheidungen E1 (SMS-Schwellwerte werden nicht übernommen, SMS hebt ab Gelb der Ampel hervor) und E2 (alte Felder bis S3a gesperrt, nicht still wirkungslos); Fachdaten `docs/context/einstellungen_neu.md` §4.4; Code-Befunde `docs/context/feat-2792-s1-profil-ampel.md`.

**Nicht Teil von S1:** Alarm-Logik (S2 #2793, `alarm_ab` wird nur gespeichert), neue Bedienoberfläche (S3a/S3b), relative Höhen und weitere Metriken (S7 #2799).

## Source

- **Files:** `src/app/ampel.py` (neu), `src/app/ampel_templates.py` (neu), `src/app/models.py`, `src/app/loader.py`, `src/app/metric_catalog.py`, `src/output/metric_format.py`, `src/output/renderers/**`, `src/output/tokens/**`, `src/output/renderers/alert/**`, `scripts/migrate_2792_profil_ampel.py` (neu), `internal/model/metric_preset.go`, `internal/handler/**`
- **Identifier:** `ampel_for(subscription)`, `validate_ampel(ampel)`, `thunder_color(level, resolved)`, `deviation_count(ampel)`

> **Schicht-Hinweis:** Python-Core (Wetter-Domäne, alle Renderer, Migration), Go-API (nur `MetricPreset`-Feld, Validierung beim Speichern, Fehlertext), Frontend (nur Sperre der Altfelder und Hinweistext, kein neuer Editor). Go-Modelle `Trip`/`ComparePreset` bleiben unverändert: die Ampel liegt **unter `display_config`** (Go reicht `DisplayConfig map[string]interface{}` durch).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Datenmodell, Auflösung `ampel_for` und Validierung sind **ein** Code für beide Kontexte. Die Sperre der Altfelder liegt in den geteilten Komponenten unter `frontend/src/lib/components/shared/` (Parameter `context="route"|"vergleich"`), keine neue Compare-Komponente. Compare-eigen ist nur das Bauen der Listen je Render im Compare-Mail-Template.
> - **Mandantentrennung:** Migration und Speichern laufen je Nutzer unter `data/users/<user_id>/`; getestet mit zwei verschiedenen Nutzern, nie Fallback `"default"`.
> - **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS lesen dieselbe Ampel (ADR-0095); Alarm-Mail und Alarm-Telegram nutzen sie für die Stundenfärbung.

## Estimated Scope

Lieferung in **Teilschritten, je eigener PR mit allen 6 CI-Checks** (`test` · `lint` · `go-test` · `svelte-check` · `frontend-test` · `e2e`), unter dieser einen Spec. Reihenfolge laut Playbook: erst Lese-Code (S1a), dann Migration (S1b), dann Umschalten der Leser (S1c, selbst in fünf PRs geschnitten: S1c-1, S1c-2, S1c-3, S1c-4a, S1c-4b).

| Schritt | Inhalt | LoC (grob, inkl. Tests, Skript, Datentabellen) | ACs |
|---|---|---|---|
| **S1a** | Datenmodell, Vorlagen-Grenzen, Validierung, `ampel_for`, Go-`MetricPreset`, Compare-Profil-Zuordnung. Ausgabe unverändert (noch liest niemand `ampel_for`). | ca. 450 | AC-13, AC-14, AC-15 (nur Auflösung `profil` → Vorlage), AC-16, AC-18 |
| **S1b** | Migrationsskript (Probelauf, `--execute`, Sicherung, wiederholbar). | ca. 400 | AC-8 bis AC-12, AC-17 |
| **S1c-1** „Durchreichen, Ausgabe unverändert“ | Ampel-Objekt als keyword-only Pflichtparameter ohne Default bis an jede Farbentscheidung; Compare-Listen je Rendern; `AlertMessage` trägt die Ampel; Hervorhebung per Prädikat vorbereitet; Ratsche gegen `display_thresholds`-Zugriffe in `src/output/**`. Die Einstiege übergeben noch `resolve_ampel(None)` ⇒ Ausgabe byte-gleich. | ca. 450 | AC-20 (Struktur), Ratsche |
| **S1c-2** „Migration nachziehen“ | `_ZUORDNUNG` ergänzen (§4 Nachtrag), Test, Nachlauf auf Staging und Prod. | ca. 120 | AC-23 |
| **S1c-3** „Altfelder sperren (E2)“ | Frontend: Wertebereiche-Reiter und SMS-Schwellwert-Regler nur lesbar. Darf vor S1c-4 live gehen. | ca. 150 | AC-22, AC-24 |
| **S1c-4a** „Vorbau, byte-gleich“ | Prädikat-Funktionen in `ampel.py` (noch ohne Leser); `hiking_field_min_max_ts` als Schwesterfunktion (die alte Funktion delegiert, Tupelform unverändert); Plumbing der Signaturlücken: `render_compare_email(preset=)`, `render_comparison_text`, beide Multi-Location-Alarme (`send_multi_location_deviation_alert`, `send_multi_location_radar_alert`) samt Wrapper `notification_service.py:1171` (Parameter wird durchgereicht, aufgelöst wird weiter `None`); expliziter Zweig-Parameter in `outlook.py`; Katalogschlüssel `mail.vorlage.<template_id>` DE/EN. **Prüfstein:** keine Golden-Datei kippt, Modus-Matrix unverändert, Übergangstests `test_profil_ampel_kette.py:656/:779/:905` bleiben grün, kein neuer `resolve_ampel`-Aufrufer. | ca. 350 | AC-26 |
| **S1c-4b** „Umschalten, alle vier Kanäle gleichzeitig“ | 16 Einstiege lösen das Abo auf, CAPE ohne Farbe, Gewitter zentral, Wertebereich-Markierung aus, `sms_threshold`/`DEFAULTS` ohne Wirkung, ein Prädikat „gelb oder schlechter“ für Kurzkanäle und Mail-Erwähnungen, Temperatur mit Stunde, Kopfzelle „Profil“ mit Vorlagen-Label, Übergangstests umkehren, Wirkungstests je Einstieg, Goldens neu, Doku. | ca. 800 | AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19, AC-21, AC-25, AC-27 |

- **S1c: fünf Teilschritte, je eigener PR und eigener Workflow-Lauf unter dieser Spec und Issue #2792.** Der Lauf `feat-2792-s1c-leser` liefert S1c-1; die übrigen folgen als eigene Läufe (S1c-4a und S1c-4b im Lauf `feat-2792-s1c4-umschalten`, nacheinander). Issue #2792 wird erst nach S1c-4b und Selftest geschlossen.
- **Reihenfolge:** S1c-1, S1c-2 und S1c-3 in beliebiger Reihenfolge, danach S1c-4a, S1c-4b zuletzt. Grund: Es gibt keinen Zeitpunkt, an dem die Kanäle unterschiedlich bewerten (ADR-0095), und die Altfelder sind nie still wirkungslos (E2).
- **Warum 4a/4b und nicht „Umschalten / Temperatur mit Stunde“ (v1.4, Paritätsbegründung):** Ein Schnitt nach Temperatur ist verworfen. Die Temperatur-Hervorhebung in den Kurzkanälen hängt nach AC-1 an der Ampel, ist also **Bewertung**, nicht bloße Anzeige. Nach einem solchen Schnitt wäre +9 °C beim Skitouren-Abo in der Mail orange, in SMS, Premium-SMS und Telegram aber nicht hervorgehoben: ein Zeitpunkt mit unterschiedlicher Bewertung der Kanäle (ADR-0095). Der Vorbau 4a verändert dagegen keine Ausgabe (gleiches Muster wie S1c-1) und senkt nur das Diff-Volumen von 4b. **Fallback:** Fällt 4a kleiner aus als erwartet, darf die Umsetzung auf **einen** PR mit `loc_limit_override` ca. 1200 zurückfallen (ebenfalls paritätstreu). Einen dritten Weg gibt es nicht.
- **Reihenfolge-Gate (prüfbar):** Vor dem Prod-Deploy von S1c-4b (bzw. des Einzel-PR im Fallback) muss auf Prod der Probelauf `scripts/migrate_2792_profil_ampel.py` (ohne `--execute`) für alle Nutzer „nichts zu tun“ melden, und der Migrationsbericht muss im Issue stehen. Dieser Probelauf ist Pflicht-Vorbedingung im `/70-deploy` von S1c-4b.
- **Gesamt:** ca. 2900 LoC (S1a 450 + S1b 400 + S1c ca. 2050), ca. 60 Dateien. **Effort:** high.
- **loc_limit_override:** in jedem Schritt erwartet (Limit 250; Tests, Datentabellen und `scripts/` zählen mit). Vor `/50` je Lauf mit `workflow.py status` gegenlesen und `loc_limit_override` setzen (Richtwerte S1a 500, S1b 450, S1c-1 450, S1c-2 120, S1c-3 150, S1c-4a 400, S1c-4b 900, Fallback Einzel-PR 1200; `*.md` zählt nicht).
- **Schema-Hook:** Edits an `internal/model/`, `src/app/models.py`, `src/app/loader.py` lösen `data_schema_backup.py` aus (erwartet, kein Fehler).

## Affected Files

### Python-Core

| File | Change | Beschreibung | Schritt |
|---|---|---|---|
| `src/app/ampel_templates.py` | CREATE | Grenzen der 7 Vorlagen (Datenstruktur, Quelle `einstellungen_neu.md` §4.4) | S1a |
| `src/app/ampel.py` | CREATE | `validate_ampel`, `ampel_for`, `deviation_count`, `thunder_color`, Profil-Zuordnung | S1a |
| `src/app/ampel.py` | MODIFY | Prädikat-Funktionen „gelb oder schlechter“ (beidseitig) und Gewitter-Prädikat (4a, ohne Leser); CAPE-Brücke `:203-219` entfernen, `{}`-Ampel scheitert laut (4b) | S1c-4a/S1c-4b |
| `src/app/models.py` | MODIFY | `UnifiedWeatherDisplayConfig.ampel: Optional[dict]` | S1a |
| `src/app/loader.py` | MODIFY | Ampel lesen/schreiben (Muster `loader.py:1839`), ungültige Ampel loggen und verwerfen, merge-sicher | S1a |
| `src/app/metric_catalog.py` | MODIFY | `display_thresholds` liefert danach nur Vorgaben der Vorlage „allgemein“; CAPE-Schwellen entfallen | S1a/S1c-4b |
| `api/routers/config.py` | MODIFY | `GET /templates` liefert zusätzlich `ampel` je Vorlage | S1a |
| `scripts/migrate_2792_profil_ampel.py` | CREATE | Batch-Migration | S1b |
| `scripts/migrate_2792_profil_ampel.py` | MODIFY | `_ZUORDNUNG` um Vergleichsschlüssel ergänzen (§4 Nachtrag) | S1c-2 |
| `src/output/metric_format.py` | MODIFY | `severity_for` nimmt Ampel-Dict statt Katalog; `thunder_ampel_band` wird die zentrale Gewitter-Abbildung | S1c-1/S1c-4b |
| `src/output/renderers/email/{html,plain,compact,helpers,outlook,compare_html}.py`, `src/output/renderers/comparison.py` | MODIFY | Ampel durchreichen (S1c-1), Signaturlücken und Zweig-Parameter (S1c-4a), Leser umschalten (Abschnitt 5, S1c-4b) | S1c-1/S1c-4a/S1c-4b |
| `src/output/renderers/email/corridor_mark.py` | DELETE | Wertebereich-Markierung entfällt; `corridors=` wird als ignoriertes Argument angenommen, Daten bleiben (AC-24) | S1c-4b |
| `src/output/tokens/{builder,metrics,dto}.py`, `src/output/renderers/{sms_trip,narrow,day_window,compact_summary}.py` | MODIFY | Hervorhebung „@14“ aus Ampel statt `sms_threshold`/`DEFAULTS`; Temperatur mit Stunde über `hiking_field_min_max_ts` (Schwesterfunktion, 4a), Verdrahtung in 4b | S1c-1/S1c-4a/S1c-4b |
| `src/output/renderers/alert/{hours,project,model,render}.py`, `src/services/notification_service.py`, `src/services/validator_render_service.py` | MODIFY | Stunden-Staging mit Ampel des Abos; `AlertMessage` trägt die Ampel; Aufrufer reichen den Trip durch | S1c-1/S1c-4b |
| `src/services/{radar_alert_service,compare_alert_preview_service,compare_alert,compare_radar_alert,compare_preview_service,scheduler_dispatch_service}.py` | MODIFY | Preset bzw. Trip an die Einstiege reichen (Signaturlücken 4a, Auflösung 4b) | S1c-4a/S1c-4b |
| `src/output/renderers/trip_report.py`, `src/services/trip_report_scheduler.py` | MODIFY | Auflösung am Einstieg; `build_outlook_row` bekommt die Ampel des jeweiligen Trips; `_sms_thr`/`sms_threshold` wirken nicht mehr | S1c-1/S1c-4b |
| `src/services/trip_command_processor.py` | MODIFY | Gewitter-Dublette `_BAND_EMOJI` über `thunder_color` mit Trip-Ampel | S1c-4b |
| `src/i18n/messages/{de,en}/mail.json` | MODIFY | Vorlagen-Labels `mail.vorlage.<template_id>` (7 Vorlagen) | S1c-4a |
| Tests (Abschnitt Test Plan) | CREATE/MODIFY | | S1a bis S1c-4b |

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
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`, `weather-metrics-tab/weatherMetricsSavePayload.ts` | MODIFY | SMS-Schwellwert-Regler (Sensibel/Standard/Robust) nur lesbar + Hinweis; Speicher-Payload reicht Bestandswerte `sms_threshold` unverändert durch (nie weglassen, nie leeren) | S1c-3 |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`, `CorridorEditorMobile.svelte`, `wertebereicheVergleichSpeicherung.ts` | MODIFY | Korridor-Zeilen des Reiters Wertebereiche nur lesbar + Hinweis (Eingaben, Setzen/×, Ordinal-Buttons, Markieren, Entfernen, Hinzufügen gesperrt; `patch/add/remove` zusätzlich als No-op-Guard), `context="route"\|"vergleich"`, Desktop und Mobil; `corridors` unverändert durchreichen (nie leeren). Die Tabelle „Alarm-Empfindlichkeit“ (`metric_alert_levels`) im selben Reiter bleibt editierbar (S2) | S1c-3 |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` (SMS-Hinweis ggf. `trip.json`) | MODIFY | Hinweistext | S1c-3 |
| `frontend/src/lib/i18n/__tests__/**`, Komponententests | MODIFY | Paritätstest bleibt grün; Test der Sperre | S1c-3 |

### Dokumentation

| File | Change | Beschreibung |
|---|---|---|
| `docs/reference/api_contract.md` | MODIFY | SSOT: `display_config.ampel` (MetricConfig/Weather Config §11, Trip §10.5, ComparePreset §16), MetricPreset §15.5 (neues Feld), `GET /templates`, Fehlercode `ampel_ungueltig`; Corridor §24 und `sms_threshold` als „ohne Wirkung, erhalten“ vermerkt |
| `docs/reference/sms_format.md`, `telegram_format.md`, `premium_sms_format.md` | MODIFY | Hervorhebung „@14“ = erste Stunde gelb oder schlechter laut Ampel; Temperatur mit `@h` (S1c-4b) |

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
| `docs/context/feat-2792-s1c4-umschalten.md` | Analyse | Einstiege, Signaturlücken, Befunde zu S1c-4 |
| `docs/reference/i18n_konventionen.md` | Regeln | Katalog, Protokoll-Token nie übersetzen |
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

Der Compare erhält Vorlagen (Datenteil): `display_config.ampel.template` des `ComparePreset`. Fehlt es, bestimmt `profil` die Vorlage (`ampel.py`, case-insensitive): `summer_trekking` → `alpen-trekking`; `wandern`, `wintersport`, `allgemein` gleichnamig; weitere eingebaute Vorlagen-IDs werden direkt akzeptiert; unbekannter Wert → `allgemein`, Warnung ins Log. Die Zelle „Profil“ im Compare-Mail-Kopf (`profile_signature`, `compare_html.py:1746`) zeigt das Label der aufgelösten Vorlage (siehe Nachtrag v1.4 unten für die Label-Quelle). Das Scoring (`calculate_score`) bleibt an `profil` gebunden.

#### Nachtrag S1c-4 (v1.4): Label-Quelle und Geltungsbereich der Kopfzelle

- **Label-Quelle:** Katalogschlüssel `mail.vorlage.<template_id>` für die 7 eingebauten Vorlagen (`alpen-trekking`, `wandern`, `skitouren`, `wintersport`, `radtour`, `wassersport`, `allgemein`). DE ist wortgleich zu `WEATHER_TEMPLATES[...].label` in `metric_catalog.py:1296` (kein sichtbarer DE-Sprung gegenüber dem Plan), EN ist neu (ADR-0104, Platzhaltermengen gleich, Paritätstest der Kataloge bleibt grün). Die bestehenden Schlüssel `mail.profil.*` bleiben unberührt: das sind **Profil-IDs** (`summer_trekking` usw.), keine Vorlagen-IDs. Vorlagen-IDs selbst sind Protokoll-Token und werden nie übersetzt, nur das Label.
- **Ersatz des bisherigen Zellwerts:** Die Zelle „Profil“ (Katalogschlüssel `vergleich.kopf.profil`, `compare_html.py:1439/1468-1483`) zeigt heute `profile_signature(profile, lang).eyebrow`; künftig das Vorlagen-Label. Titel und Eyebrow-Kopf der Signatur bleiben unverändert. Der Zellwert ändert sich auch bei „allgemein“ sichtbar (AC-19 (f)).
- **Nur im Mail-Kopf, nicht in Vergleichs-SMS und -Telegram:** `render_compare_sms` und `render_compare_telegram` zeigen kein Profil. Das ist paritätskonform (ADR-0095), weil das Profil-Label ein **Metadatum** ist und keine Bewertung: Alle Kanäle liefern dieselbe Bewertung (Ampel), ein Kanal ohne Platz für eine Kopfzeile verliert keine Antwort auf eine Frage.

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

#### Nachtrag S1c-2: Vergleichsschlüssel

Der Migrationsbericht vom 2026-11-04 (Kommentar in #2792) nennt Vergleichs-Wertebereiche als „nicht zuordenbar“, die nach dem Umschalten sichtbar fehlen würden (Prod: `henning/5f534011`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`). Deshalb wird `_ZUORDNUNG` (`scripts/migrate_2792_profil_ampel.py`) ergänzt. Die Einheiten sind geprüft (Einheit des Katalogs = Einheit des Schlüssels).

| Vergleichsschlüssel | Ampel-Metrik | Übernommene Seite | Bemerkung |
|---|---|---|---|
| `wind_max_kmh` | `wind` | `bis` | km/h |
| `visibility_min_m` | `visibility` | `von` | m; wirkt auf der unteren Seite (Katalog `*_lt`); falsche Seite würde die Sichtweiten-Ampel invertieren |
| `precip_sum_mm` | `precipitation` | `bis` | mm; die Vergleichs-Übersicht färbt die Summe schon heute mit `precipitation` |
| `pop_max_pct` | `rain_probability` | `bis` | % |
| `snow_new_sum_cm` | `fresh_snow` | `bis` | cm |
| `wind_chill_min_c` | `wind_chill` | `von` | °C. **Korrektur v1.2:** v1.1 nannte `wind_chill_min`; das ist die Renderer-ID, der echte Vergleichsschlüssel heißt `wind_chill_min_c` (sonst bliebe die Zuordnung wirkungslos) |
| `wind_chill_max_c` | `wind_chill` | `bis` | °C, Korrektur wie oben |
| `uv_index_max` | `uv_index` | `bis` | Indexwert |
| `temp_min_c` | `temperature` | `von` | °C. Sind `temp_min_c` und `temp_max_c` beide vorhanden, gilt für die untere Seite `temp_min_c` (Vorrang, unabhängig von der Reihenfolge der Auswertung); `temp_max_c` liefert dann nur `bis` |
| `sunny_hours_h` | `sunshine` | `von` | nur Daten (in S1 kein Leser) |
| `cloud_avg_pct` | `cloud_total` | `bis` | nur Daten |
| `cloud_low_avg_pct` | `cloud_low` | `bis` | **neu in v1.2**; nur Daten |
| `humidity_avg_pct` | `humidity` | beide | nur Daten |
| `dewpoint_avg_c` | `dewpoint` | `bis` | nur Daten |
| `freezing_level_m` | `freezing_level` | `von` | nur Daten |
| `snowfall_limit_m` | `snowfall_limit` | `von` | nur Daten |
| `snow_depth_cm` | `snow_depth` | beide | **neu in v1.2**; nur Daten |
| `thunder_level_max`, `cape_max_jkg` | nicht zuordenbar | – | Gewitter hat keine Zahlengrenzen, CAPE keine Farbe (P1). Der Bericht nennt diese Begründung |
| `wind_direction_deg`, `cloud_mid_avg_pct`, `cloud_high_avg_pct`, `pressure_avg_hpa`, `precip_type_dominant` | nicht zuordenbar | – | **neu in v1.2**; keine Ampel-Metrik bzw. keine Zahlengrenzen. Bericht nennt sie mit Begründung, Altdaten bleiben erhalten |

- **Vollständige Schlüsselliste (v1.2, aus dem Code gezogen):** maßgeblich ist `FRONTEND_TO_RENDERER_METRIC_ID` (`src/output/renderers/compare_metric_ids.py`). **Ratsche:** ein Test zieht diese Schlüsselmenge; jeder Schlüssel ist entweder zugeordnet oder ausdrücklich „nicht zuordenbar“, sonst ist der Test rot. Jede zugeordnete Ampel-Metrik muss in `AMPEL_TEMPLATES` existieren. Bereits aus S1b bleiben `temp_max_c`, `gust_max_kmh` (beide Seiten).
- **Offen für `/40`:** Welche Schlüssel auf Prod tatsächlich genutzt werden, liefert der Probelauf auf Prod (`sudo -n -u claude-gregor`, außerhalb des Worktree-Wächters); ob die heutige Wertebereich-Markierung `thunder_level_max`/`cape_max_jkg` sichtbar färbt, wird dort mitgeprüft.
- **Bestand aus S1b bleibt:** `temp_max_c` → `temperature` und `gust_max_kmh` → `gust` übernehmen schon beide Seiten des Bands (`_BEIDE`); das gilt weiter, nur die Vorrang-Regel für `temp_min_c` (Tabelle) kommt hinzu.
- **Abbildungsregel** wie für Trips: `von`/`bis` mit `Schritt`, Klemm-Regel, Metrik wird bei verletzter Validierung übersprungen.
- **Wiederholbarkeit:** Ein erneuter `--execute` ergänzt fehlende Metriken in einer vorhandenen Ampel und überschreibt keine.
- **Ablauf je Umgebung (Staging, danach Prod):** Probelauf → `--execute` (mit `tar.gz`) → zweiter `--execute` mit „nichts zu tun“ → Bericht im Issue.

### 5. Leser umschalten (S1c)

Alle Leser aus Context §3 nutzen `ampel_for(subscription)`; danach liest kein Leser `display_thresholds` als Nutzer-Bewertung:

- **Trip-Mail:** HTML, Plain, Compact einschließlich Kacheln (`build_metrics_summary_pills`, `_pill_for_metric`, `tone_symbol`), Stundentabelle (`fmt_val`, `_render_html_table`), Zeilen-Risiko `_row_risk`. Die Highlights (`_compute_highlights`) lesen `highlight_threshold`, keine Farbschwelle, und bleiben unberührt.
- **Träger:** Die Auflösung geschieht einmal am Einstieg (`resolve_ampel(sub)`, ohne Abo `resolve_ampel(None)` = „allgemein“); die Schwellen kommen per `ampel_for`. Das aufgelöste Objekt wird als keyword-only Pflichtparameter ohne Default durch alle internen Funktionen gereicht. Es gibt kein `ContextVar`. Gründe: versteckter Zustand, `copy_context` im Scheduler (`parallel_fetch.py`), und vergessene Stellen blieben unsichtbar. Ein Default „allgemein“ würde ein vergessenes Durchreichen gerade bei Skitouren und Wassersport verdecken. `build_outlook_row` im Scheduler bekommt die Ampel des jeweiligen Trips.
- **3-Tages-Ausblick** (`render_outlook_table`, Trip und Vergleich): nutzt die Ampel des Abos statt `_catalog_thresholds`; Temperatur wird beidseitig gefärbt.
- **Vergleichs-Mail:** Übersicht (`CV2_METRICS`) und Stundenverlauf (`HOUR_METRICS`, `_make_hour_sev`) sind statische Modul-Listen und werden **je Rendern** mit der Ampel des Presets gebaut.
- **Alarm-Mail und Alarm-Telegram:** `alert/hours.py` (`_stage`, `_is_affected`, `format_cell`) bekommt die Ampel des Abos beim Projizieren (`AlertMessage` trägt sie); die getrennte Skala `risk_thresholds` (Etappen-Risiko) bleibt unberührt.
- **SMS, Premium-SMS, Telegram „@14“:** `sms_threshold` und `DEFAULTS` wirken nicht mehr (E1). Hervorhebung = erste Stunde, in der die Metrik **gelb oder schlechter** ist, **beidseitig** (auch Unterschreiten der unteren Grenze); sonst „-“. `render_threshold_peak_value` und `_sms_mention_threshold` lesen die Ampel. Protokoll-Token (`sms_code`, `compact_label`) bleiben unverändert (`tests/test_metric_tokens_eingefroren.py`).
- **Gewitter zentral (P2):** `thunder_color(level, resolved)`: „keins“ grün, „leicht“ fest gelb, „mittel“/„hoch“ nach `ampel.thunder`. Die Funktion nimmt das aufgelöste Objekt (`resolve_ampel(sub)`), damit bei einem Trip ohne gespeicherte Ampel die Vorlage aus `preset_name`/`profil` greift (z. B. Wassersport „mittel“ = rot, AC-5). Die Dubletten `outlook._THUNDER_LEVEL_BG`, `outlook._metric_column_bg`, `html._thunder_risk_level`, `compare_html._sev_thunder` und `trip_command_processor._BAND_EMOJI` werden entfernt oder rufen diese eine Abbildung. **CAPE (P1):** keine eigene Farbe (`_ampel_dot_severity("cape")` entfällt); die Fusion zur Gewitterstufe (`thunder_level_from_signals`, `_fuse_thunder_levels`) bleibt unverändert.
- **Wertebereich-Markierung entfällt:** Die Markierung nach `corridors` (`corridor_mark.py`, Leser in `html.py`, `compare_html.py`, `design_tokens.py`) wird mit S1c-4b abgeschaltet. Nach ADR-0106 ist die Ampel die einzige Bewertung; die markierten Bereiche sind per Migration in die Ampel übernommen. Die Daten bleiben gespeichert.
- **Temperatur in Kurzkanälen (AC-1):** Token-Form:
  - Einzelform `D9@14` bzw. `L-17@6` (Stunde des Werts), nur wenn der Wert gelb oder schlechter ist; sonst wie heute `D9`.
  - Bereichs-Token: jede Hälfte trägt ihr `@h` unabhängig, z. B. `D-2/9@14` oder `D-17@6/9@14`. `/` trennt die Hälften, `@` gehört zur Hälfte davor (eindeutig lesbar, GSM-7-sicher).
  - Die Stunde kommt aus `hiking_field_min_max` (`day_window.py`): `max_ts` besteht, `min_ts` wird ergänzt. Gilt für D/L/FD/FL; N/FN bleiben unverändert. **v1.4:** Die Ergänzung geschieht über die neue Schwesterfunktion `hiking_field_min_max_ts` (liefert zusätzlich `min_ts`); `hiking_field_min_max` bleibt mit unveränderter Tupelform bestehen und delegiert, damit die 7 Aufrufstellen in 4 Dateien (`sms_trip.py`, `compact_summary.py`, `narrow.py`, `email/outlook.py`) nicht umgebaut werden müssen. Nur die Temperatur-Token der Kurzkanäle rufen die neue Funktion.
  - Bei Überlänge gilt unverändert die bestehende Kürzungsreihenfolge (Temperatur hat die niedrigste Priorität), kein neuer Mechanismus.
  - Kürzel `sms_code`/`compact_label` bleiben unverändert (`tests/test_metric_tokens_eingefroren.py`).
  - Luftfeuchte (`_sms_mention_threshold`, Wert 90) bleibt ohne Ampel-Leser; die Sicht 2,0 km kommt aus der Ampel. **v1.4:** Die 90 wird zur benannten Konstante (Name im Code, kein freies Literal mehr), bleibt aber fest.
  - Premium-SMS nutzt keinen eigenen Builder: sie sendet den SMS-Text unverändert (`premium_sms_format.md`, Kanal `premium_sms` ist Kurzform-Kanal mit demselben Token-Vertrag). Die Token-Änderung gilt dadurch für SMS und Premium-SMS in einem Zug; Telegram nutzt den Pfad `src/output/renderers/narrow.py`.
- **Altfelder sperren (E2):** Reiter „Wertebereiche“ und die SMS-Schwellwert-Regler sind nur lesbar mit Hinweis aus dem Katalog: DE „Wird gerade umgebaut – deine Werte sind übernommen.“, EN „Being rebuilt – your values have been carried over.“ Werte werden angezeigt, aber nicht mehr geschrieben.

#### Nachtrag S1c-4 (v1.4): Pflichten beim Umschalten

Diese Punkte präzisieren den Abschnitt oben; sie ändern keine Entscheidung aus ADR-0106. Die Einordnung in 4a (Vorbau, Ausgabe byte-gleich) und 4b (Umschalten) steht jeweils dabei.

1. **Kein Einstieg fällt still auf `None` (4b).** Alle 16 Einstiege, die heute `resolve_ampel(None)` aufrufen (Liste in `docs/context/feat-2792-s1c4-umschalten.md`), lösen das Abo auf. Wo der Einstieg heute nur `dc` (die `display_config`) kennt und `dc` fehlen kann, wird das **Trip-Objekt** statt `dc` übergeben. **Korrektur v1.5:** Die frühere Begründung „damit ein Trip ohne `display_config` über `preset_name` seine Vorlage behält“ trifft nicht zu: `Trip` (`src/app/trip.py`) hat kein eigenes `preset_name`, die Vorlage liegt nur in `display_config` (`preset_name`, `ampel`). Ein Trip ohne `display_config` hat keine gespeicherte Vorlage und wird deshalb nach „allgemein“ bewertet. Das ist kein stiller Rückfall, sondern der einzig mögliche Stand. Verboten bleibt, ein **vorhandenes** Abo (`dc` mit `preset_name` oder `ampel`) unterwegs zu verlieren. Die vier Einstiege ohne Abo im Scope (`render_comparison_text`, beide Multi-Location-Alarme, `render_compare_email`) bekommen dafür in **4a** einen neuen Parameter (Preset bzw. Ampel), den die Aufrufer (`compare_alert.py:476`, `compare_radar_alert.py:426`, `compare_preview_service.py:162`, `scheduler_dispatch_service.py:971`, Wrapper `notification_service.py:1171`) in 4a durchreichen; aufgelöst wird dort noch `None`, erst 4b löst auf.
2. **`build_outlook_row` (4a/4b).** `ampel=` wird Pflichtparameter **ohne Default**. Die Wahl zwischen Trip- und Ortsvergleichs-Zweig hängt heute an derselben `None`-Prüfung wie die Ampel (`dc is None`, `outlook.py:647/653/799`); sie bekommt in **4a** einen **expliziten Zweig-Parameter**, damit ein fehlendes `dc` nicht den falschen Zweig wählt. Der einzige Aufrufer `trip_report_scheduler.py` übergibt je `stage_trip` dessen Ampel.
3. **`render_compare_html(preset=None)` wird abgeschafft (4b):** `preset` ist Pflicht; wer kein Preset hat, übergibt bewusst die Ampel „allgemein“.
4. **Leere Ampel scheitert laut (4b).** `schwellen_aus_ampel({}, …)` liefert nicht mehr still `{}`, sondern löst einen Fehler aus (Test); eine `{}`-Ampel ist ein Programmierfehler, kein gültiger Zustand.
5. **Sicht und Luftfeuchte (4b).** Die Sicht-Erwähnung liest die Ampel (`visibility`, untere Seite); die Luftfeuchte 90 bleibt fest als benannte Konstante.
6. **CAPE-Brücke entfernen (4b, AC-6).** `ampel.py:203-219` (Katalog-Schwellen für CAPE in `hat_ampel`/`schwellen_aus_ampel`) entfällt; CAPE trägt keine Farbe. Die Fusion zur Gewitterstufe bleibt unverändert.
7. **Gewitter-Dubletten (4b).** `outlook.py:257` (`_THUNDER_LEVEL_BG`) und `:444` (`_metric_column_bg`, Ordinal-Zweig), `compare_html.py:245` (`_sev_thunder`) und `trip_command_processor.py:578` (`_BAND_EMOJI`) rufen `thunder_color(level, resolved)` mit dem aufgelösten Objekt. `html.py:166` (`_thunder_risk_level`) wird nur angefasst, falls es eine Farbe entscheidet (es liefert heute nur das Zeilen-Risiko).
8. **Wertebereich-Markierung aus (4b, AC-24).** `corridor_mark.py` entfällt; der Parameter `corridors=` bleibt an `render_html` und `render_compare_html` als ignoriertes Argument; die gespeicherten Daten bleiben unangetastet.
9. **Ein gemeinsames Prädikat (4a vorbereitet, 4b verdrahtet).** Ein Prädikat „gelb oder schlechter“ gilt **beidseitig** (auch Unterschreiten der unteren Grenze, z. B. Wassersport-Wind unter 8 km/h) und wird von den Kurzkanälen (Spitzenwert-Hervorhebung) **und** den Mail-Erwähnungen (`_sms_mention_threshold`, 6 Aufrufstellen in `email/helpers.py`; Quelle bisher `mc.sms_threshold` in `html.py`, `compact.py`, `plain.py`) gemeinsam genutzt. Gewitter ist ordinal: Schwelle „≥ leicht“ (entspricht der bisherigen Schwelle 1,0 und ist wegen P2 dieselbe Menge wie „gelb oder schlechter“). `render_threshold_peak_value(ampel_stufe=)` bekommt seinen ersten Aufrufer; `_mk_metric` (`tokens/builder.py`) nutzt weder `spec.threshold` noch `DEFAULTS` für die Hervorhebung. Auch `TripReportFormatter.format_sms` (bisher `thresholds=` aus `sms_threshold`) bekommt die Ampel statt der Schwellen.
10. **Vergleichs-SMS und -Telegram.** `render_compare_sms` und `render_compare_telegram` haben keinen Farb- oder Hervorhebungsleser (gemessen); sie bleiben unverändert und gelten als paritätskonform, weil die Vergleichsbewertung dort nicht über Farben geführt wird.

#### Nachtrag S1c-4b (v1.5): Präzisierungen zum Umschalten

Gemessen gegen `origin/main` @ `4f3309cd4` (nach 4a). Diese Punkte ändern keine Entscheidung aus ADR-0106 und keinen Punkt 1–10 außer der Korrektur in Punkt 1.

1. **Trip-Renderer lösen ihre `dc` auf.** `render_html`, `render_plain`, `render_compact` und `render_telegram_bubbles` rufen `resolve_ampel(dc)` mit der `display_config`, die sie ohnehin bekommen; einen neuen Parameter gibt es nicht. `TripReportFormatter.format_email` setzt bei fehlender `dc` `build_default_display_config()` ein (ohne `preset_name`/`ampel`, also „allgemein“, siehe Korrektur in Punkt 1).
2. **Vorschau und Versand haben dieselbe Quelle** (`trip.display_config`, Versand über `TripReportRequest.display_config`, Vorschau `preview_service.py`). Abgeleitete Kopien per `dataclasses.replace(dc, metrics=…)` (`trip_report.py`, auch `_dc_telegram`) müssen `ampel` und `preset_name` behalten.
3. **Ausblick: Auflösung im Scheduler.** `build_outlook_row` löst nicht mehr selbst auf; `ampel=` ist Pflicht ohne Default, der Aufruf `resolve_ampel(None)` in `outlook.py` entfällt. `trip_report_scheduler.py` übergibt je `stage_trip` `ampel=resolve_ampel(stage_trip)` (Import aus `app.ampel`; die Wache gegen `output.*`-Importe im Scheduler bleibt unberührt). **AST-Wachen:** `build_outlook_row` wandert in `test_profil_ampel_kette.py` aus der Soll-Liste „löst auf“ in eine neue Soll-Liste „nimmt `ampel` als Pflichtparameter ohne Default“; die Scheduler-Funktion kommt neu in `DIENST_EINSTIEGE`. Damit bleibt jeder der 16 Wege bewacht, die Prüfung sitzt dort, wo aufgelöst wird; die Zähl-Ratschen werden in `/40` neu gemessen und nur erweitert.
4. **SMS aus derselben `dc` wie die Mail.** `format_sms(thresholds=)` hat einen Aufrufer (`trip_report.py`, `SMSTripFormatter().format_sms`); er bekommt `resolve_ampel(dc)` statt `_sms_thr`, und `_sms_thr` sowie `sms_thresholds=` im Scheduler entfallen. `_sms_threshold`/`alert_channel_thresholds` (amtliche Warnstufe der SMS, #1461) ist etwas anderes und bleibt unverändert.
5. **Eingabe von `resolve_ampel`.** Die Funktion nimmt unverändert ein Trip-Objekt, eine `display_config` oder ein Compare-Preset (Dict oder Objekt) und sucht die Vorlage in dieser Reihenfolge: `display_config.ampel.template`, dann `display_config.preset_name`, dann `profil` (Compare), sonst „allgemein“. Ob der Einstieg das Trip-Objekt oder dessen `display_config` übergibt, ist für das Ergebnis gleich. `None` übergibt kein Einstieg mehr.
6. **Ein-Ort-Alarm.** `send_location_deviation_alert` ist kein 17. Einstieg, sondern ein Durchreiche-Wrapper vor `send_multi_location_deviation_alert`; er löst nicht selbst auf, ist aber mit eigenem Wirkungstest bewacht (Testplan, F002).
7. **Gleichstand im Minimum.** `hiking_field_min_max_ts` liefert `min_ts` bei gleichen Minimalwerten deterministisch die **früheste Stunde**, unabhängig von der Reihenfolge der Eingabepunkte (bisher hing das am ersten Vorkommen). Das wird sichtbar, sobald `min_ts` im Temperatur-Token (`L-17@6`) erscheint.

### Neue Nutzertexte (ADR-0104)

Alle neuen Nutzertexte in DE und EN über die Kataloge, Platzhaltermengen gleich: Hinweis „Wird gerade umgebaut …“ (Frontend), Fehler `fach.fehler.ampel_ungueltig` (Go; DE „Die Ampel ist ungültig: Die Grenzen müssen oben aufsteigend und unten absteigend angeordnet sein.“, EN „The traffic light is invalid: limits must increase on the upper side and decrease on the lower side.“), Vorlagen-Label im Compare-Kopf: **ab v1.4 neu** `mail.vorlage.<template_id>` in `src/i18n/messages/{de,en}/mail.json` (7 Schlüssel; DE wortgleich zu `WEATHER_TEMPLATES`, EN neu; v1.3 ging fälschlich davon aus, die Labels lägen zweisprachig vor). Protokoll-Token (`sms_code`, `compact_label`, `alarm_ab`-Werte, Vorlagen-IDs) werden nie übersetzt. Deutsche Golden-Ausgaben bleiben byte-gleich, außer den in AC-19 benannten Abweichungen.

## Test Plan

Farben werden **am Entstehungsort** getestet (Renderer-Ausgabe, `ampel_for`, `thunder_color`), denn **kein Mail-Validator prüft Farben**. Validatoren bleiben unverändert: Trip-Mail `.claude/hooks/briefing_mail_validator.py`, Vergleichs-Mail `.claude/hooks/email_spec_validator.py` (beide gegen echt zugestellte Staging-Mail in `/e2e-verify`, Staging-Nutzer `de` und `en`). Das Renderer-Commit-Gate verlangt für S1c frisch grün: `tests/tdd/test_issue_811_mode_matrix.py` (Erwartungen von globalen Gelb-Schwellen auf Vorlage „allgemein“ umgestellt) und `briefing_mail_validator.py`; für die Vergleichs-Mail zusätzlich `email_spec_validator.py`.

### Automated Tests (TDD RED, Testnamen nach Verhalten)

- [ ] `tests/tdd/test_ampel_modell_und_aufloesung.py` (S1a): Validierung gültig/ungültig, Teilmenge, Abweichungszahl, Rückfallkette, „allgemein“ == heutiges `display_thresholds` ohne CAPE, Compare-Profil-Zuordnung inkl. unbekannt, Loader behält andere Felder.
- [ ] `internal/handler/ampel_validierung_test.go`, `internal/model/metric_preset_ampel_test.go` (S1a): Ablehnung `ampel_ungueltig` DE/EN, eigene Vorlage speichert/lädt Ampel+`alarm_ab` ohne Zustellung, zwei Nutzer isoliert.
- [ ] `tests/tdd/test_migration_2792_profil_ampel.py` (S1b): Probelauf, `--execute`, Wiederholung, Sicherung, zwei Nutzer, Δ-Bereich, `sms_threshold`, `horizons`, CAPE, byte-gleiche Restfelder, Klemm-Regel; Nachtrag Vergleichsschlüssel (AC-23, S1c-2).
- [ ] `tests/tdd/test_profil_ampel_leser.py` (S1c): Farben je Leser (HTML-Tabelle, Kachel, Plain, Compact, Ausblick, Vergleichs-Übersicht, Vergleichs-Stundenverlauf, Alarm-Stunden) mit Skitouren-/Wassersport-/Allgemein-Ampel; zwei Presets nacheinander im selben Prozess.
- [ ] `tests/tdd/test_kein_leser_liest_display_thresholds.py` (S1c-1): Ratsche gegen `display_thresholds`-Zugriffe und `severity_for(` ohne Schwellen in `src/output/**` (inkl. `renderers/alert/**`); die Whitelist darf nur schrumpfen.
- [ ] Mutationsgegenprobe je Leser (Ampel durch Katalog ersetzt) mit Skitouren- oder Wassersport-Abo, denn bei „allgemein“ bleibt sie unsichtbar; `build_outlook_row` mit zwei Trips nacheinander.
- [ ] Alarm-Mail-Validator `.claude/hooks/radar_alert_mail_validator.py` gehört in den E2E-Umfang von S1c-4b (die Alarm-Mail wird angefasst); `official_alert_mail_validator.py` zusätzlich, falls die amtliche Warnung berührt wird.
- [ ] `tests/tdd/test_sms_hervorhebung_aus_ampel.py` (S1c): SMS, Premium-SMS, Telegram, beidseitig.
- [ ] `tests/tdd/test_gewitter_zentrale_abbildung.py` (S1c): alle Vorlagen, CAPE ohne Farbe.
- [ ] `frontend/src/lib/components/shared/__tests__/altfelder_gesperrt.test.ts` (S1c): beide Kontexte, DE/EN.
- [ ] Anpassung bestehender Tests (Context §3, 34 Dateien), u. a. `tests/test_ampel_schwellen_katalog.py`, `tests/tdd/test_compare_katalog_schwellen.py`, `tests/tdd/test_renderer_katalog_schwellen.py`, `tests/test_chip_ampel_farben.py`, `tests/test_ampel_farbabstufung.py`, `tests/tdd/test_metric_format.py`, `tests/unit/test_cape_ampel_thresholds.py`, `tests/tdd/test_outlook_metric_ampelfarben.py`, `tests/tdd/test_thunder_column_ampel.py`, `tests/tdd/test_gewitter_ampel_bandtreu.py`, `tests/tdd/test_issue_811_mode_matrix.py`: Erwartungen mit globalen Werten werden auf Vorlage „allgemein“ umgestellt; CAPE-Erwartungen entfallen mit Begründung (P1). **Keine Ratsche wird abgeschwächt**; die Paritäts-Ratsche prüft künftig Katalog-Vorgabe == Vorlage „allgemein“.

#### Nachtrag S1c-4 (v1.4): Testplan

- [ ] **Wirkungstest je Einstieg (4b, `tests/tdd/test_s1c4_*.py`, neu):** für **jeden der 16 Einstiege** aus der Context-Tabelle (`render_html`, `render_plain`, `render_compact`, `render_telegram_bubbles`, `build_outlook_row`, `render_compare_html`, `render_comparison_text`, `build_onset_alert_message`, `render_alert_preview`, `_deviation_preview_message`, `_deviation` und `_onset` im `compare_alert_preview_service`, `send_deviation_alert`, `send_multi_location_deviation_alert`, `send_multi_location_radar_alert`, `send_radar_alert`) je ein Test „Skitouren-Abo färbt bzw. markiert anders als Allgemein-Abo“ (z. B. +9 °C, Böen 52 km/h). Ein Test mit „allgemein“ allein würde eine Mutation (`None` statt Abo) nicht sehen.
- [ ] **Zwei Abos nacheinander in beiden Reihenfolgen** im selben Prozess (AC-2/AC-20): Skitouren dann Allgemein und Allgemein dann Skitouren, für Mail, Vergleich, Ausblick (`build_outlook_row` mit zwei Trips) und Alarm; Mandantentrennung mit zwei Nutzern.
- [ ] **Übergangstests umkehren, nicht löschen (4b):** `tests/tdd/test_profil_ampel_kette.py::test_jeder_einstieg_loest_in_s1c1_genau_allgemein_auf` (:905), `::test_ausblick_einstieg_faerbt_in_s1c1_nach_allgemein` (:656) und `::test_cape_traegt_in_s1c1_noch_eine_farbe` (:779) bleiben in **4a grün** und werden in **4b** absichtlich rot und zu Zusicherungen umgeschrieben („jeder Einstieg löst das Abo auf, nie still `None`“, „der Ausblick färbt nach der Abo-Ampel“, „CAPE trägt keine Farbe“). Die AST-Soll-Listen (`EINSTIEGE` :796, `DIENST_EINSTIEGE` :853) und die Zähl-Ratschen (:872/:876) werden **erweitert**, wenn ein neuer Helfer `resolve_ampel` aufruft (neue Einstiege eintragen, nie abschwächen).
- [ ] **`render_comparison_text`-Tests** `tests/test_wind_chill_max_selectable.py:185` und `tests/test_selection_conservation_rendered.py:131` rufen die Funktion heute ohne Preset und werden mit dem neuen Pflichtparameter rot (4a); sie werden umgestellt (Preset mit Ampel übergeben), der Prüfinhalt bleibt.
- [ ] **Weitere Bestandstests umstellen (4b), Liste aus `docs/context/feat-2792-s1c4-umschalten.md`:** Corridor-Mark-Tests (`tests/tdd/test_*corridor_mark.py`), `test_thunder_column_ampel.py`, `test_gewitter_ampel_bandtreu.py`, `test_outlook_metric_ampelfarben.py`, `tests/unit/test_cape_ampel_thresholds.py`, `test_ampel_schwellen_katalog.py`, `test_compare_katalog_schwellen.py`, `test_thunder_mention_threshold_shared.py`, `test_issue_872_threshold_ux.py`, `test_mail_pillen_schwelle_bei_eigenem_layout.py`, `test_thunder_pill_*`, `test_issue_624_metric_thresholds.py`, `test_th_plus_follows_thunder_metric_and_gap.py`, `test_sms_user_metric_order.py`: globale bzw. `sms_threshold`-Erwartungen werden auf Ampel umgestellt (umkehren, nicht löschen); keine Ratsche wird abgeschwächt.
- [ ] **4a-Prüfstein als Test:** Golden-Lauf vor und nach 4a ohne Abweichung, `test_issue_811_mode_matrix.py` unverändert grün, die drei Übergangstests grün, kein neuer `resolve_ampel`-Aufrufer (Zähl-Ratschen unverändert).
- [ ] **Gewitter und CAPE (4b):** `thunder_color` über alle Vorlagen und alle vier Orte (Ausblick, Tabelle, Vergleich, Telegram-Emoji) mit dem aufgelösten Objekt; CAPE-Zelle neutral; `{}`-Ampel löst im Test den erwarteten Fehler aus.
- [ ] **Kurzkanäle (4b):** Spitzenwert-Hervorhebung beidseitig (Wassersport-Untergrenze), Gewitter „≥ leicht“, Temperatur-Token mit `@h` je Hälfte, Luftfeuchte 90 fest, Sicht aus der Ampel, `tests/test_metric_tokens_eingefroren.py` unverändert grün; dieselben Erwähnungsschwellen in der Mail.
- [ ] **Goldens (4b):** Golden-Lauf vor und nach; Kandidaten unter `tests/golden/`: `email/`, `vergleichs_mail/`, `f5_wertebereiche/`, `f8_layout_korridor/`, `f10_vergleich_flaechen/`, `abweichungs_radar_alarm/`, `text_report/` und die Kurzkanal-Goldens `sms/`, `telegram_briefing/` (Premium-SMS sendet den SMS-Text). **Welche Dateien tatsächlich kippen, misst /40**; jede Abweichung wird einzeln dem Buchstaben (a) bis (f) aus AC-19 zugeordnet, nicht zugeordnete Abweichungen sind ein Fehler.
- [ ] **Renderer-Commit-Gate und Mail-Validatoren (4b, in `/e2e-verify`, DE und EN):** `test_issue_811_mode_matrix.py` frisch grün; `briefing_mail_validator.py` (Trip), `email_spec_validator.py` (Vergleich), `radar_alert_mail_validator.py` (Radar-/Regen-Alarm), `official_alert_mail_validator.py` falls berührt; Exit 0.
- [ ] **Reihenfolge-Gate `/70` (kein automatischer Test):** Probelauf `migrate_2792_profil_ampel.py` auf Prod meldet „nichts zu tun“, Bericht im Issue, **vor** dem Prod-Deploy von 4b.

#### Nachtrag S1c-4b (v1.5): zusätzliche RED-Pflichten aus dem 4a-Lauf

- [ ] **Zweig im produktiven Aufrufer (F001):** Verhaltenstest nah am Scheduler mit einem Trip **mit** und einem **ohne** `display_config` und einer Gewitterstunde **nachts** (Tagesfenster #1841); ein Vertauschen von `context="route"`/`"vergleich"` im Scheduler oder in `compare_html.py` muss rot werden (bisher nur per AST bewacht).
- [ ] **Ein-Ort-Alarm (F002):** Wirkungstest Skitouren ≠ Allgemein über genau den Wrapper `send_location_deviation_alert`, damit ein verlorenes `preset` beim Durchreichen rot wird.
- [ ] **Vier Kanäle aus einer `dc`:** ein Test über `format_email` mit Skitouren-`dc` zeigt in HTML, Plain, Compact **und** Telegram-Blasen die Skitouren-Bewertung; er fängt eine Mutation, die beim `dataclasses.replace` die Ampel verliert. Dazu SMS über `TripReportFormatter.format_sms` mit derselben `dc`.
- [ ] **Gleichstand im Minimum:** `hiking_field_min_max_ts` mit unsortierten Punkten und gleichem Minimum liefert die früheste Stunde.
- [ ] **`render_comparison_text`-Tests mit Ampel:** `tests/test_wind_chill_max_selectable.py` und `tests/test_selection_conservation_rendered.py` übergeben nach 4b ein Preset mit Vorlage ≠ allgemein (in 4a vorläufig ohne Ampel umgestellt), damit sie nicht nur „allgemein“ prüfen.
- [ ] **Vorbestehend rot:** Der Telegram-Live-Test `test_ac4` („heute/morgen“) war vor und nach 4a rot (Nebenbefund #1199); in `/e2e-verify` gegen den Vorher-Stand vergleichen, nicht als Regression werten.
- [ ] **Adversary nach Test-Umstellungen:** Am Ende von `/50` läuft ein neuer Adversary-Dialog über die umgestellten Bestandstests (Lehre aus S1c-3).

#### Umsetzungsstand S1c-4b (2026-11-07)

- Die oben genannten Dateinamen `test_profil_ampel_leser.py`, `test_sms_hervorhebung_aus_ampel.py`, `test_gewitter_zentrale_abbildung.py` und `test_s1c4_*.py` sind als `tests/tdd/test_s1c4b_*.py` umgesetzt.
- [x] `tests/tdd/test_s1c4b_cape_zelle_zeigt_zahl.py` (Fix-Loop `/60-validate`): CAPE-Zelle im Einfach-HTML und in der Alarm-Mail zeigt die nackte Zahl statt „–“.
- [x] `tests/tdd/test_s1c4b_cape_alarm_stunden_nach_schwelle.py` (Fix-Loop `/60-validate`): Die Stundenauswahl von CAPE-Alarmen läuft über die Schwelle (`alert/hours.py` `_LEVEL_METRICS`).

## Scope

- **Im Umfang des laufenden Teilschritts S1c-4 (v1.4):** S1c-4a „Vorbau, byte-gleich“ und S1c-4b „Umschalten, alle vier Kanäle gleichzeitig“, wie in „Estimated Scope“ (Schnitt-Tabelle) und „Affected Files“ beschrieben; ACs AC-1 bis AC-7, AC-15 (Mail-Kopf), AC-19, AC-21, AC-25, AC-26, AC-27.
- **Bereits geliefert (nicht erneut Umfang):** S1a, S1b, S1c-1, S1c-2, S1c-3 (live bis `5fb07bbc8`).
- **Nicht im Umfang:** Alarm-Logik (S2 #2793), neue Bedienoberfläche (S3a/S3b), relative Höhen und weitere Metriken (S7 #2799), Löschen der gespeicherten Altfelder `sms_threshold`/`corridors` (bleiben erhalten, AC-24), Highlights (`highlight_threshold`).

## Definition of Done

- [ ] S1c-4a gemergt mit allen 6 CI-Checks grün; Golden-Lauf ohne Abweichung, Modus-Matrix und Übergangstests unverändert grün (AC-26).
- [ ] S1c-4b gemergt mit allen 6 CI-Checks grün; alle 16 Einstiege lösen das Abo auf, Wirkungstest je Einstieg in beiden Reihenfolgen grün (AC-25).
- [ ] Jede Golden-Abweichung von 4b ist einem der Buchstaben (a) bis (f) aus AC-19 zugeordnet und im PR einzeln benannt.
- [ ] `/e2e-verify` auf Staging: `briefing_mail_validator.py`, `email_spec_validator.py`, `radar_alert_mail_validator.py` (und `official_alert_mail_validator.py`, falls berührt) in DE und EN mit Exit 0.
- [ ] Reihenfolge-Gate erfüllt: Prod-Probelauf der Migration meldet „nichts zu tun“, Bericht im Issue, vor dem Prod-Deploy von 4b.
- [ ] Prod-Deploy und `prod_selftest.py` mit Exit 0; Doku `sms_format.md`, `telegram_format.md`, `premium_sms_format.md`, `api_contract.md` aktualisiert; danach Issue #2792 geschlossen.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Vorlage Skitouren und ein Trip mit Vorlage Allgemein, beide mit Tageshöchsttemperatur +9 °C / When das Briefing als E-Mail, Telegram, SMS und Premium-SMS gerendert wird / Then ist +9 °C beim Skitouren-Trip in der E-Mail orange (Skitouren orange ab 8 °C) und in Telegram, SMS und Premium-SMS als Spitzenwert mit Stunde hervorgehoben (gelb oder schlechter); beim Allgemein-Trip ist +9 °C in der E-Mail grün und in den drei Kurzkanälen nicht hervorgehoben (gelb erst ab 28 °C)
  - Test: Render je Kanal mit beiden Abos, Farbe bzw. Hervorhebung am Entstehungsort geprüft (`test_profil_ampel_leser.py`, `test_sms_hervorhebung_aus_ampel.py`)
- **AC-2:** Given zwei Nutzer A und B mit Vorlage Skitouren (Böen gelb ab 40 km/h) / When Nutzer A die Böen-Gelbgrenze auf 42 km/h setzt und beide Briefings mit 41 km/h Böen gerendert werden / Then ist 41 km/h bei A grün, bei B gelb, und bei 42 km/h ist es auch bei A gelb
  - Test: zwei Nutzer, Speichern über Go-API, Render beider Briefings; B bleibt unverändert (Mandantentrennung)
- **AC-3:** Given ein Abo mit Vorlage Wassersport (Wind unten orange unter 4, gelb unter 8 km/h) / When Mittelwind 3 km/h bzw. 6 km/h bzw. 15 km/h gerendert wird / Then ist 3 km/h orange, 6 km/h gelb und 15 km/h grün
  - Test: beidseitige Auswertung der unteren Seite in Mail-Stundentabelle und Kachel
- **AC-4:** Given ein Abo mit Vorlage Skitouren (Temperatur oben rot ab 15 °C, unten rot unter -30 °C) / When die Temperatur +16 °C bzw. -31 °C beträgt / Then wird beides rot dargestellt, +10 °C orange und -17 °C gelb
  - Test: beide Seiten derselben Metrik in Stundentabelle, Kachel und 3-Tages-Ausblick; die Temperatur färbt dort wie jede andere Metrik nach der Ampel, auch bei „allgemein“ (v1.6, PO-Entscheid 2026-11-07, siehe Known Limitations)
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
  - **Nachtrag v1.4:** Das Label kommt aus dem Katalogschlüssel `mail.vorlage.<template_id>` (7 Vorlagen; DE wortgleich zu `WEATHER_TEMPLATES`, EN neu) und erscheint in der Sprache des Nutzers: bei Sprache Englisch zeigt die Zelle das englische Label, bei Deutsch das bisherige deutsche. Die Zelle gibt es nur im Mail-Kopf; Vergleichs-SMS und -Telegram zeigen kein Profil (Metadatum, keine Bewertung, daher paritätskonform nach ADR-0095). Der Katalog-Schlüssel wird in S1c-4a angelegt, die Zelle in S1c-4b umgestellt. Test: Kopfzeile für drei Profile in DE und EN; Paritätstest der Kataloge grün
- **AC-16:** Given eine Ampel mit Böen `upper.yellow` 50 und `upper.orange` 45 / When sie über die Go-API gespeichert wird / Then lehnt die API mit Code `ampel_ungueltig` ab, die Meldung steht in der Anfragesprache (DE „Die Ampel ist ungültig …“ bzw. EN „The traffic light is invalid …“) und die gespeicherte Ampel bleibt unverändert; ebenso abgelehnt wird eine untere Gelbgrenze über der oberen
  - Test: PUT Trip, Compare und Eigene Vorlage mit `Accept-Language` de und en
- **AC-17:** Given ein Trip mit `preset_name` „skitouren“ und ein Compare-Preset mit Profil „wintersport“ / When die Migration läuft / Then tragen beide `display_config.ampel.template` (`skitouren` bzw. `wintersport`), die Auflösung ergibt dieselben Grenzen wie die Vorlage, und `metric_alert_levels` und `alert_rules` sind unverändert
  - Test: Datei vor/nach für Alarmfelder, `ampel_for` nach Migration
- **AC-18:** Given die Vorlage „allgemein“ in `ampel_templates.py` / When sie mit dem bisherigen `display_thresholds` verglichen wird / Then sind alle Grenzen der 10 bisherigen Metriken gleich, mit Ausnahme der CAPE-Grenzen, die entfallen
  - Test: Paritäts-Ratsche Katalog-Vorgabe == Vorlage „allgemein“
- **AC-19:** Given Trip-Briefing, Vergleichs-Mail und Alarm-Mail eines Abos mit Vorlage Allgemein und Werten aus den bisherigen Golden-Fixtures / When gerendert wird / Then ist die Ausgabe byte-gleich zu vorher, außer den vier bewusst vereinheitlichten Stellen: (a) die CAPE-Farbe entfällt (P1), (b) die Temperatur im 3-Tages-Ausblick wird nach der Ampel gefärbt (bisher nie), (c) die Gewitterfarbe der früheren Dubletten folgt der zentralen Abbildung (z.B. eigenes Hellgelb im Ausblick, „keins“ im Vergleich jetzt grün), (d) die Markierung nach gespeicherten Wertebereichen entfällt (ihre Werte stehen jetzt in der Ampel); jede dieser Abweichungen ist im Golden-Vergleich einzeln benannt
  - Test: Golden-Vergleich vor/nach (die nach der Ampel gefärbte Temperaturzelle der Trip-Stundentabelle ist eine zulässige, PO-entschiedene Abweichung, v1.6), zusätzlich `test_issue_811_mode_matrix.py` und die Validatoren für Trip und Compare in `/e2e-verify` mit Exit 0
  - **Nachtrag v1.4 (zwei weitere Abweichungen, auch bei „allgemein“):** (e) Die Schwellen, ab denen Mail und Kurzkanäle (SMS, Premium-SMS, Telegram) einen Wert erwähnen bzw. als Spitzenwert hervorheben, folgen der Ampel (gelb oder schlechter, beidseitig) statt `sms_threshold`/`DEFAULTS`/`_sms_mention_threshold`; z. B. erscheint Wind in der Erwähnung erst ab 30 km/h statt ab 10 km/h. (f) Die Kopfzelle „Profil“ im Vergleichs-Mail-Kopf zeigt das Vorlagen-Label (z. B. „Allgemein“) statt des bisherigen Eyebrow-Werts. Betroffene Golden-Dateien: neben den Mail-Goldens auch die Kurzkanal-Goldens (`tests/golden/sms/`, `tests/golden/telegram_briefing/`, Premium-SMS über den SMS-Text). Welche Dateien tatsächlich kippen, misst `/40` im Golden-Lauf vor und nach; **jede einzelne Abweichung wird einem der Buchstaben (a) bis (f) zugeordnet**, eine nicht zuordenbare Abweichung ist ein Fehler. Gilt für S1c-4b; S1c-4a ist byte-gleich (AC-26)
- **AC-20:** Given zwei Compare-Presets mit Vorlage Skitouren und Allgemein, nacheinander im selben Prozess gerendert, Temperatur +9 °C / When Übersicht und Stundenverlauf gerendert werden / Then ist +9 °C beim Skitouren-Preset orange und beim Allgemein-Preset grün, unabhängig von der Reihenfolge
  - Test: Rendern in beiden Reihenfolgen, keine Zustandsübernahme der Modul-Listen
- **AC-21:** Given eine Alarm-Mail und ein Alarm-Telegram für ein Abo mit Vorlage Skitouren und eines mit Vorlage Allgemein, jeweils mit Böen 52 km/h / When die Stundenzeilen erzeugt werden / Then ist 52 km/h beim Skitouren-Abo gelb (Skitouren orange erst ab 55) und beim Allgemein-Abo orange (orange ab 45), jeweils nach Abo-Ampel statt globalem Katalog
  - Test: Projektion und Rendern beider Kanäle mit beiden Abos
- **AC-22:** Given ein Nutzer öffnet den Reiter Wertebereiche und die SMS-Schwellwerte im Reiter Wetter, in Trip und Vergleich / When die Seite in Deutsch bzw. Englisch angezeigt wird / Then sind die Felder nur lesbar, zeigen die gespeicherten Werte, und der Hinweis lautet DE „Wird gerade umgebaut – deine Werte sind übernommen.“ bzw. EN „Being rebuilt – your values have been carried over.“
  - Test: Komponententest für beide Kontexte und beide Sprachen; Paritätstest der Kataloge grün
- **AC-23:** Given zwei Nutzer mit je einem Compare-Preset mit Wertebereichen für `wind_max_kmh`, `visibility_min_m` und `precip_sum_mm` (mark=True) und einem bereits migrierten Preset mit vorhandener Ampel / When der Migrations-Nachlauf mit `--execute` und danach ein zweites Mal läuft / Then trägt jedes Preset die Werte als Ampel-Grenzen für `wind`, `visibility` (untere Seite) und `precipitation`, vorhandene Ampel-Metriken sind nicht überschrieben, der zweite Lauf ändert keine Datei, `thunder_level_max`/`cape_max_jkg` stehen als nicht zuordenbar im Bericht, jeder Schlüssel aus `FRONTEND_TO_RENDERER_METRIC_ID` ist zugeordnet oder ausdrücklich nicht zuordenbar (Ratsche), `temp_min_c` bestimmt die untere Temperatur-Seite auch bei vorhandenem `temp_max_c`, und vor dem Prod-Deploy von S1c-4 meldet der Probelauf auf Prod „nichts zu tun“
  - Test: Migration auf Kopie, zwei Nutzer, Prüfsummen, Bericht; Ratsche auf die Schlüsselmenge aus `FRONTEND_TO_RENDERER_METRIC_ID`; Vorrang `temp_min_c` bei vorhandenem `temp_max_c` in beiden Reihenfolgen. Der Prod-Probelauf ist Deploy-Vorbedingung (Reihenfolge-Gate), kein automatischer Test

- **AC-24:** Given ein Trip und ein Vergleich mit gespeicherten `sms_threshold`-Werten und `corridors`, im Anlegen- und im Bearbeiten-Modus, Desktop und Mobil / When der Nutzer andere Einstellungen ändert und speichert (auch wenn der Regler-Zustand leer ist) / Then stehen `sms_threshold` und `corridors` danach unverändert in der gespeicherten Datei, kein Regler und keine Korridor-Eingabe löst ein Speichern aus, und die Alarm-Empfindlichkeit bleibt bearbeitbar
  - Test: Funktionstest `buildGlobalMetricsForSave` (Bestand rein → identisch raus, auch bei leerem `smsThresholds`), Komponenten-Test der gesperrten Eingaben in beiden Kontexten, Zwei-Nutzer-Prüfung der gespeicherten Datei in `/e2e-verify`
- **AC-25:** Given zwei Abos, eines mit Vorlage Skitouren und eines mit Vorlage Allgemein, mit Temperatur +9 °C und Böen 52 km/h / When für jeden der 16 Einstiege (Trip-Mail HTML, Plain und Compact, Telegram-Briefing, Trip-Ausblick, Vergleichs-Mail, Vergleichs-Text, Radar- und Abweichungs-Alarm für Trip und Vergleich, Alarm-Vorschauen, Alarm-Versand) gerendert wird, auch in der Reihenfolge Allgemein vor Skitouren / Then färbt bzw. markiert jeder Einstieg das Skitouren-Abo anders als das Allgemein-Abo (Skitouren: +9 °C orange, Böen 52 km/h gelb; Allgemein: +9 °C grün, Böen 52 km/h orange), kein Einstieg verliert ein vorhandenes Abo (Rückfall auf „allgemein“ nur, wenn gar keine Vorlage gespeichert ist), und ein Trip, dessen `display_config` nur `preset_name` „skitouren“ ohne gespeicherte Ampel trägt, wird in allen vier Kanälen nach Skitouren bewertet (ein Trip ganz ohne `display_config` hat keine Vorlage und wird nach „allgemein“ bewertet, Korrektur v1.5)
  - Test: ein Wirkungstest je Einstieg mit beiden Abos in beiden Reihenfolgen (`tests/tdd/test_s1c4_*.py`); bei nur „allgemein“ bliebe eine Verfälschung unsichtbar; die drei Übergangstests in `test_profil_ampel_kette.py` sind zu Zusicherungen umgekehrt
- **AC-26:** Given der Vorbau S1c-4a mit Prädikat-Funktionen, `hiking_field_min_max_ts`, durchgereichten Preset-Parametern, explizitem Zweig-Parameter in `outlook.py` und den Katalogschlüsseln `mail.vorlage.<template_id>` / When alle Golden-Fixtures, die Modus-Matrix und die Übergangstests nach dem Vorbau laufen / Then ist jede Ausgabe in jedem Kanal byte-gleich zu vorher, die drei Übergangstests sind unverändert grün, es gibt keinen neuen `resolve_ampel`-Aufrufer, und `hiking_field_min_max` liefert für seine 7 Aufrufstellen unverändert dieselbe Tupelform
  - Test: Golden-Lauf vor/nach ohne Abweichung, `test_issue_811_mode_matrix.py` grün, Zähl-Ratschen in `test_profil_ampel_kette.py` unverändert, Aufruf von `hiking_field_min_max` und `hiking_field_min_max_ts` auf demselben Tag (`max_ts` gleich)
- **AC-27:** Given ein Aufruf der Schwellen-Auflösung mit einer leeren Ampel `{}` und ein Aufruf von `build_outlook_row` ohne Ampel / When der Aufruf erfolgt / Then schlägt er laut fehl (Fehler statt stiller Ersatz-Ausgabe), und die Kurzkanäle und Mail-Erwähnungen verwenden dasselbe Prädikat „gelb oder schlechter“ (beidseitig, Gewitter ab „leicht“), sodass Mail und Kurzkanal bei jedem Wert dieselbe Erwähnung entscheiden
  - Test: `schwellen_aus_ampel({}, "gust")` und `build_outlook_row` ohne `ampel=` werfen; Gleichheitstest Kurzkanal- und Mail-Erwähnung über Werte um die Grenzen (Wind 29/31, Wassersport-Wind 7/9, Gewitter keins/leicht)

## Prod-Wirkung (Info, gemessen 2026-11-06)

Nur lesend gemessen (`sudo -n -u claude-gregor`, `/var/lib/gregor/users/*/briefings/*.json`): **12 Abos**, **alle tragen bereits `ampel`** (aus Migration S1b/S1c-2), davon **11× Vorlage „allgemein“** und **1× „wintersport“** (`henning/zillertal`). Verteilung: Nutzer henning 11, steffi 1, dazu die Altdatei `default`; die Testabos `validator-issue110` (8 Dateien) haben keine Ampel und lösen zu „allgemein“ auf. Folge nach dem Umschalten: Sichtbar nach Vorlage ändert sich vor allem `zillertal`; bei allen übrigen wirken die Vereinheitlichungen aus AC-19 (e)/(f) sowie die aus `sms_threshold`/`corridors` migrierten eigenen Grenzen (`5f534011`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`). Der Hinweis dient der Abnahme in `/e2e-verify`; die Trip-Konfiguration des PO wird dafür nicht verändert.

## Known Limitations

- **Nachtrag S1c-3 (v1.3):** (1) Gesperrt wird alles, was Wertebereiche (`corridors`) oder `sms_threshold` schreibt; die Alarm-Empfindlichkeit (`metric_alert_levels`) bleibt bis S2 bearbeitbar, weil sie nicht zu den Altfeldern aus E2 gehört. (2) Der Hinweis erscheint einmal oben im Reiter Wertebereiche und einmal im SMS-Schwellwert-Block, je ein Katalogschlüssel mit demselben Wortlaut aus AC-22. (3) Datenerhalt: `buildGlobalMetricsForSave` löscht `sms_threshold` nie mehr, der Bestandswert wird unverändert gespeichert (auch bei leerem Regler-Zustand); `corridors` laufen in Trip und Vergleich, auch im Anlegen-Modus, unverändert durch; die Vorbelegung im Anlegen-Modus bleibt funktionsfähig. (4) Es gibt keinen Weg mehr, die Altfelder zu ändern; vor S1c-4 wirken sie unverändert weiter (nie still wirkungslos).
- **Nachtrag S1c-4 (v1.4):** (1) Die Wirkung von `sms_threshold` und `corridors` endet mit dem Deploy von S1c-4b; die Daten bleiben gespeichert (AC-24). (2) Die Kopfzelle „Profil“ gibt es nur im Mail-Kopf (Metadatum). (3) Bei Rückfall auf einen Einzel-PR gelten alle 4a- und 4b-Zusicherungen gemeinsam in einem PR.
- **Nachtrag v1.6 (PO-Entscheid 2026-11-07):** Die Temperatur färbt sich nach denselben Regeln wie jede andere Metrik, so wie der Nutzer die Ampel einstellt (Vorlage als Voreinstellung, Abweichung an derselben Stelle konfigurierbar wie bei anderen Metriken). Das gilt auch für die Temperaturzelle der Trip-Stundentabelle, bei allen Profilen einschließlich „allgemein“ (z. B. −5 °C gelb). Diese Golden-Abweichung ist zulässig und wird in der Zuordnung als „Temperatur Stundentabelle (v1.6)“ geführt; sie ergänzt die Liste AC-19 (a)–(f). Anlass: AC-1/AC-4 verlangten die Färbung, AC-19 (a)–(f) nannte sie nicht.
- **Nachtrag S1c-4b (Umsetzungsstand 2026-11-07):**
  (a) Der tote Eintrag `"cape": "cape"` in `_COL_KEY_TO_METRIC_ID` (`src/output/renderers/email/html.py:563`) bleibt und wirkt nicht (es gibt keine CAPE-Schwellen mehr); die Zelle ist bewacht durch `tests/tdd/test_s1c4b_cape_zelle_zeigt_zahl.py` (Adversary F002, LOW, akzeptiert).
  (b) `compact_summary.py` steht in der Affected-Files-Zeile, bleibt aber bewusst unverändert: es erzeugt nur den Fließtext („Temperatur 12–18 °C“) ohne Stunden-Kürzel und behält `hiking_field_min_max` (siehe Implementation Details v1.4).
  (c) Zusätzlich geänderte Dateien ohne eigene Zeile in Affected Files: `scripts/send_gate_test_mails.py` (`render_compare_email(preset=)` jetzt Pflicht, Gate-Testmail nutzt Vorlage „allgemein“), `src/i18n/messages/{de,en}/mail.json` (Schlüssel `mail.pille.wind_ereignis_unten` für die beidseitige Ampel), `src/app/cli.py` (`ampel=resolve_ampel(trip)` am Trip-Report-Aufruf), `src/output/renderers/email/design_tokens.py` (nur Kommentar); `corridor_mark.py` ist gelöscht (wie in der Spec als DELETE vorgesehen).
  (d) LoC-Begründung: Produktionscode +606/−591 in 28 Dateien (netto +15), Limit-Override 1300 / Tests 6500, weil das Umschalten 16 Einstiege in vier Kanälen gleichzeitig umstellen muss (kein halbes Umschalten möglich, AC-25) und Goldens/Bestandstests umgekehrt statt gelöscht werden.
  (e) Teilbelege: AC-2 „Speichern über die Go-API“ ist S1a-Umfang; AC-3 Einzelwerte 6/15 km/h sind im 4b-Test nicht separat belegt; AC-26 Byte-Gleichheit war der 4a-Prüfstein.
  (f) Fix-Loop aus `/60-validate` (Commit `4f2b10f42`): Die CAPE-Zelle zeigt im Einfach-HTML und in der Alarm-Mail die nackte Zahl statt „–“; `"cape"` ist aus `_AMPEL_CAPABLE_METRIC_IDS` entfernt, die Stundenauswahl von CAPE-Alarmen läuft dadurch über die Schwelle (`alert/hours.py` `_LEVEL_METRICS`).
- **Alarm-Logik unverändert** (S2): `alarm_ab` wird gespeichert, aber nicht gelesen; Alarm-Trigger, `metric_alert_levels`, `alert_rules` und CAPE-Δ-Alarm bleiben bis S2 wie heute.
- **Neue Bedienoberfläche** (S3a/S3b): in S1 nur Sperre der Altfelder; die Ampel ist noch nicht im Editor bearbeitbar (Änderungen laufen über API und Migration).
- **Relative Höhen und weitere Metriken** (S7): Nullgradgrenze, Schneefallgrenze (relativ), Taupunkt, Sonnenstunden, Schneehöhe, Bewölkung u. a. liegen in den Vorlagendaten, haben in S1 aber keinen Leser.
- **Highlights bleiben an `highlight_threshold`:** `_compute_highlights` liest keine Farbschwelle und ist nicht Teil der Ampel-Umstellung.
- **E1-Folge:** schwache Werte unter Gelb (Wind 25 bei Gelb 30) erscheinen in SMS/Telegram nicht mehr als Spitzenwert, bewusst; dasselbe gilt für die Erwähnungen in der Mail (AC-19 (e)).
- **Sichtbare Vereinheitlichung für alle Nutzer** (auch Vorlage Allgemein): CAPE ohne Farbe, Temperatur im 3-Tages-Ausblick gefärbt, eine Gewitterfarbe überall, Erwähnungs- und Spitzenwertschwellen aus der Ampel, Vorlagen-Label im Vergleichs-Kopf (AC-19).
- **Klemm-Regel und `Schritt`** der Migration sind Näherungen; nicht abbildbare Metriken bleiben mit ihrem Altwert erhalten und stehen im Bericht.
- **Go-Top-Level-Felder** von `Trip`/`ComparePreset` bleiben unverändert; neue Daten nur unter `display_config` (Pass-through) und im `MetricPreset`.
- **Scoring** im Compare bleibt an `profil` gebunden; die uneinheitlichen Profil-Wertebereiche (Python 4, Go 4, Vorlagen 7) werden nicht vereinheitlicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0106 (Akzeptiert 2026-11-04)
- **Rationale:** S1 setzt die Entscheidung um (eine Ampel je Metrik, Vorlage → Abo → Leser); keine weitere Grundsatzentscheidung nötig. Die hier festgelegten Umsetzungsdetails (Speichern als ganzer Unterbaum, Migrationsregeln, Schnitt 4a/4b) ändern nichts an ADR-0106.

## Changelog

- 2026-11-04: Initial spec created (Issue #2792, Epic #2791, Scheibe S1)
- 2026-11-04: PO-Freigabe (approved)
- 2026-11-04: Review Tech Lead: AC-1 Kurzkanäle als Hervorhebung, Temperatur-Zuordnung der Migration eindeutig, AC-19 Ausnahmen ehrlich benannt
- 2026-11-04: v1.1 S1c-Ergänzungen (Schnitt S1c-1…S1c-4 mit Reihenfolge-Gate Migration vor Umschalt-Deploy, AC-23 Migrations-Nachtrag Vergleichsschlüssel, AC-19 (d) Wertebereich-Markierung entfällt, Pfadkorrekturen Alarm/Telegram, `thunder_color` nimmt das aufgelöste Objekt, Highlights unberührt, Temperatur-Token mit Stunde) — Freigabe ausstehend
- 2026-11-05: v1.2 Nachtrag S1c-2 korrigiert: Vergleichsschlüssel `wind_chill_min_c`/`wind_chill_max_c` statt `wind_chill_min`/`_max`, sieben fehlende Schlüssel ergänzt (`cloud_low_avg_pct`, `snow_depth_cm`, nicht zuordenbar: `wind_direction_deg`, `cloud_mid_avg_pct`, `cloud_high_avg_pct`, `pressure_avg_hpa`, `precip_type_dominant`), Seitenspalte, Vorrang `temp_min_c`, Ratsche gegen Schlüssel-Drift — Freigabe ausstehend
- 2026-11-05: v1.3 Nachtrag S1c-3: Sperre umfasst Korridor-Zeilen und SMS-Regler, Alarm-Empfindlichkeit bleibt bearbeitbar (S2), Hinweis oben im Reiter und im SMS-Block, Datenerhalt `sms_threshold`/`corridors` — Freigabe ausstehend
- 2026-11-06: v1.4 Nachtrag S1c-4: Schnitt S1c-4 in 4a (Vorbau, byte-gleich, ca. 350 LoC) und 4b (Umschalten, ca. 800 LoC) mit Paritätsbegründung (Schnitt nach Temperatur verworfen) und Fallback Einzel-PR (loc_limit_override ca. 1200); AC-19 um (e) Erwähnungs-/Spitzenwertschwellen aus der Ampel und (f) Vorlagen-Label in der Kopfzelle erweitert, Kurzkanal-Goldens benannt; AC-15 Label-Quelle `mail.vorlage.<template_id>` (nur Mail-Kopf); §5 Pflichten beim Umschalten (kein stilles `None`, `build_outlook_row(ampel=)` Pflicht mit Zweig-Parameter, `render_compare_html(preset=None)` abgeschafft, `{}`-Ampel scheitert laut, Luftfeuchte-Konstante, `hiking_field_min_max_ts`, CAPE-Brücke raus, Gewitter-Dubletten, Markierung aus, ein gemeinsames Prädikat); Testplan (Wirkungstest je Einstieg, beide Reihenfolgen, Umkehr der Übergangstests, Reihenfolge-Gate /70); neue AC-25 bis AC-27; Prod-Wirkung (12 Abos, 11× allgemein, 1× wintersport) — automatisch freigegeben 2026-11-06 (Ampel grün, Lauf `feat-2792-s1c4-umschalten`)
- 2026-11-06: v1.5 Nachtrag S1c-4b: Korrektur §5 Punkt 1 und AC-25 (ein `Trip` hat kein eigenes `preset_name`, ohne `display_config` gilt „allgemein“); Präzisierungen (Trip-Renderer lösen `dc` auf, Ausblick-Auflösung im Scheduler mit neuer AST-Soll-Liste „Pflichtparameter ohne Default“, SMS aus derselben `dc`, Gleichstand im Minimum deterministisch); RED-Pflichten F001/F002 und Hinweise aus dem 4a-Lauf — automatisch freigegeben 2026-11-06 (Ampel grün, Lauf `feat-2792-s1c4b-umschalten`)
- 2026-11-07: v1.6 PO-Entscheid im Lauf `feat-2792-s1c4b-umschalten` (erste Antwort „ungefärbt“ vom PO selbst korrigiert): Temperatur färbt wie jede andere Metrik nach der Ampel, auch in der Trip-Stundentabelle und bei „allgemein“; zulässige Golden-Abweichung zusätzlich zu AC-19 (a)–(f) (Auflösung des Widerspruchs AC-1/AC-4 zu AC-19)
- 2026-11-07: S1c-4b umgesetzt; Fix-Loop CAPE-Zelle/Alarmstunden aus /60-validate (Commit `4f2b10f42`): CAPE-Zelle zeigt die Zahl statt „–“, `"cape"` aus `_AMPEL_CAPABLE_METRIC_IDS` entfernt, CAPE-Alarmstunden nach Schwelle; Known Limitations und Test Plan nachgeführt
