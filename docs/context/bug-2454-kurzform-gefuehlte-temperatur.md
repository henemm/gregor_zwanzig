# Kontext: bug-2454-kurzform-gefuehlte-temperatur

Issue: #2454, „Kurzform zeigt die gewählte gefühlte Temperatur nie an (Premium-SMS, SMS, Telegram-Kurzform)“
Refs: #2417 (PO-Handytest), #1728 (DEC-6/6b/7), #1887 E6

## Analysis

### Type
Bug

### Symptom (PO-Befund 27./28.09.)
Premium-SMS `Tomorrow` auf KHW 403 → `E6: W- WD:S G- R- PR- TH:- TH+:- SU10`, ohne FD/FL, obwohl „Gefühlte Temperatur“ gewählt ist.

### Root Cause (am Prod-Datenbestand beobachtet, 28.09.)
- `/var/lib/gregor/users/henning/briefings/5f534011.json` (KHW 403, mtime 26.09. 06:13): `wind_chill` ist enabled:true (primary, order 12). `wind_chill_day_low`/`_day_high`/`_night` stehen **explizit** auf enabled:false (kein bucket, order 0), global UND in `channel_layouts.sms` (ebenso in den übrigen Kanal-Listen).
- Die Kurzform erzeugt FL/FD/FN nur aus den Untergrößen (`src/output/tokens/builder.py:344-392`, `src/output/renderers/trip_report.py:425-432`). `wind_chill` selbst hat seit #1887 E6 kein Kurzform-Kürzel.
- Die Ableitung Kind←Elter (`src/app/loader.py:861-903`, `_append_derived_metrics`, #1728 DEC-6b) greift nur, wenn **kein** Kind-Eintrag existiert.
- Einfrier-Mechanismus: Die Ableitung existiert nur im Python-Loader, `internal/` (Go) kennt keine. Der Editor bekommt Rohdaten: `WeatherMetricsTab.svelte:446-476 initFromTrip()` sortiert fehlende Kinder in `off`. `metricsEditor.ts:~324-392 buildWeatherConfigMetrics` schreibt beim Speichern jede Katalog-ID, abgewählte als `enabled:false`. Die erste Speicherung friert die Abwahl damit ein.
- Umfang Prod: Alle Trips aller Nutzer wurden gescannt. **Nur KHW 403** zeigt das Muster, und zwar nur bei `wind_chill`. Bei `temperature` ist KHW komplett aus, deshalb kein L/D/N-Fall. Staging ist nicht lesbar und ungeprüft.

### Semantik laut Specs
- `docs/specs/…/feat_1728_s1_temp_aufloesung.md:232-283`: Die Kinder werden standardmäßig vom Elter abgeleitet (DEC-6b). DEC-7: `wind_chill` ist wählbar, bei neuen Trips aber nicht vorbelegt.
- `feat_1728_s2_editor.md` DEC-6 (Z.165-184): Die Kinder sind im Editor **eigenständig abwählbare** Zeilen.
- Folgerung: Eine echte Nutzer-Abwahl eines Kindes muss respektiert bleiben.

### Nebenwirkung E-Mail / Telegram-Standard: keine
Die Kinder haben keine `summary_fields` (metric_catalog.py:298-319). Sie stehen in `NO_HOURLY_COLUMN_METRIC_IDS` (email/helpers.py:104-107) und `VISIBILITY_GATE_IDS` (channel_layout.py:76-79). Die Vollmail-Kachel zeigt die Spanne von `wind_chill` unbedingt (email/helpers.py:1596-1600). Die Telegram-Nachtzeile `wind_chill_night` ist bei aktivem Elter selbst-gegated (narrow.py:791-792). **Einziger Leser** der Kind-Flags ist der Kurzform-Token-Builder. Setzt man die Kinder auf „an“, ändert sich die E-Mail nicht.

### Optionen
- **A (empfohlen):** (1) Der Editor spiegelt die Elter→Kind-Ableitung beim Laden, **nur für fehlende Kind-Einträge** (dieselbe Regel wie `_DERIVED_METRIC_RULES`), global und je Kanal-Layout. Der Editor zeigt die Kinder dann „an“, und ein Save friert nichts mehr ein. (2) Einmalige Datenmigration: Die drei eingefrorenen `wind_chill_*`-Einträge werden für Trips mit dem Muster „Elter an + alle drei Kinder explizit false ohne bucket“ entfernt. Danach greift wieder die Loader-Ableitung. Das Skript hat Dry-Run als Default, `--execute`, Backup und Read-Modify-Write (Vorbild `scripts/migrate_1244_null_lists.py`).
  - Korrektur gegenüber dem Plan-Agenten: Der Editor darf **nicht** zusätzlich „explizit false ohne bucket“ als ungesetzt deuten. Dieser Fingerabdruck ist identisch mit einer echten Abwahl. Den Bestand löst allein die Migration.
- **B (verworfen):** Der Elter erzeugt in der Kurzform selbst FL/FD/FN. Das macht eine echte Kind-Abwahl unmöglich (DEC-6) und ergibt Doppel-Tokens.
- **C (verworfen):** Der Loader deutet „explizit false“ um. Gleiches Unterscheidbarkeitsproblem wie B, und global größerer Blast-Radius.

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| frontend/src/lib/components/shared/WeatherMetricsTab.svelte | MODIFY | `initFromTrip()` + Kanal-Buckets: fehlende Kinder vom Elter ableiten |
| frontend/src/lib/components/trip-detail/metricsEditor.ts | MODIFY | gemeinsame Ableitungs-Hilfsfunktion (Regeltabelle gespiegelt aus loader.py) |
| scripts/migrate_2454_wind_chill_children.py | CREATE | einmalige Bereinigung des eingefrorenen Musters |
| Tests (Frontend `node --test` + pytest Kurzform-Kette + Migration) | CREATE | Bug-Reproduktion aus Nutzersicht |

### Scope Assessment
- Dateien: 3 produktiv + Tests
- LoC: ca. +150 produktiv (Migration ~90, Editor ~50)
- Risk Level: MEDIUM. Die Editor-Initialisierung ist geteilter Code (Trip + Ortsvergleich, `context=`). Der Ortsvergleich nutzt eigenen Katalog (`compare_metric_catalog.py`) und liest die Trip-Kinder nicht, er darf aber durch die Ableitung keine Einträge erfinden (mit `context="vergleich"` gegenprüfen).
- Die Migration läuft auf Prod-Daten (`/var/lib/gregor`, Eigentümer `claude-gregor`) und braucht einen Ausführungsweg mit Backup. Sie ändert an KHW 403 ausschließlich die drei eingefrorenen Einträge. PO-Regel „Finger weg von der Trip-Konfiguration“: Das muss in der Spec explizit stehen und vom PO freigegeben werden.

### Tests (ohne Mocks)
1. Kurzform-Reproduktion: Trip-JSON mit eingefrorenem Muster → migriert → Loader → Kurzform-Text enthält FD/FL (vor Migration: nicht).
2. Guard: Echte Abwahl (Elter an, Kind explizit false, mit bewusst abweichendem Muster, z. B. nur ein Kind false) bleibt unangetastet, ohne FD.
3. Editor-Ladepfad: Elter an + Kind fehlt → Save-Payload enthält Kind `enabled:true`. Elter an + Kind explizit false → bleibt false.
4. Migration ist idempotent, Dry-Run schreibt nichts, fremde Felder bleiben erhalten.

### Open Questions (für die Spec, keine PO-Technikfragen)
- Soll die Migration nur „alle drei Kinder false“ erfassen oder jedes einzelne false-Kind? Empfehlung: nur das vollständige Muster (alle drei false, kein bucket, order 0, Elter an). Ein einzeln abgewähltes Kind ist eher eine echte Wahl.
- Der Nebenbefund `TF` in der CODES-Antwort ist **nicht** Teil dieses Fixes. `TF` ist im Ortsvergleich real (`kurzform_kuerzel("wind_chill")`, comparison.py:636) und im Trip tot. `_show_codes()` ist kontextblind (trip_command_processor.py:356, 391-392, 1258-1264). Das kommt als Eintrag in #1199 oder in ein eigenes Ticket.
- Der Nebenbefund Telegram-Kurzform nutzt die `sms`-Auswahl (`trip_report.py:345`): Er ist nicht Teil dieses Fixes und wird separat geprüft.
