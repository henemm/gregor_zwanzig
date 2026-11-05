# Context: feat-2792-s1c2-migration (S1c-2 „Migration nachziehen“)

## Request Summary
Teilpaket S1c-2 von Issue #2792 (Epic #2791): Das Migrationsskript der Profil-Ampel kennt die Vergleichs-Wertebereich-Schlüssel (`wind_max_kmh`, `visibility_min_m`, `precip_sum_mm` …) noch nicht. Ohne Nachtrag würden diese Grenzen nach dem Umschalten der Leser (S1c-4) sichtbar fehlen. Das Skript wird ergänzt, getestet und auf Staging und Prod nachgezogen. AC-23 der freigegebenen Spec; **Reihenfolge-Gate: Migration vor Prod-Deploy von S1c-4.**

## Related Files
| File | Relevance |
|------|-----------|
| `scripts/migrate_2792_profil_ampel.py:39` | `_ZUORDNUNG` (Schlüssel → Ampel-Metrik + Seiten); hier kommen die Vergleichsschlüssel hinzu. `_DIREKT` (Z. 46) deckt Schlüssel ab, die selbst Ampel-Metrik-IDs sind |
| `scripts/migrate_2792_profil_ampel.py:98` | `_band_eintragen`: Zuordnung, Seitenprüfung, „schon belegt“ → Bericht. `von`/`bis` je Seite einzeln |
| `scripts/migrate_2792_profil_ampel.py:140` | `_ampel_planen`: vorhandene Metrik wird nie überschrieben, fehlende werden ergänzt (⇒ Wiederholbarkeit, zweiter Lauf „nichts zu tun“) |
| `tests/tdd/test_migration_2792_profil_ampel.py` | bestehende S1b-Tests (Subprozess, echter Datenbaum in `tmp_path`, Helfer `_cmp`, `_band`, `_trip`); Nachtrag-Tests kommen hierher |
| `docs/specs/modules/feat_2792_s1_profil_ampel.md` §4 „Nachtrag S1c-2“ (Z. 176), AC-23 (Z. 289) | freigegebene Spec v1.1 |
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` = **maßgebliche Liste der Vergleichsschlüssel** |
| `src/app/ampel_templates.py` | Ampel-Metrik-IDs (20): u. a. `visibility`, `rain_probability`, `fresh_snow`, `uv_index`, `wind_chill`, `sunshine`, `cloud_total`, `humidity`, `dewpoint`, `freezing_level`, `snowfall_limit` |

## Befund: Schlüsselliste weicht von der Spec-Tabelle ab (für /20-analyse)
Die Spec verlangt, die Schlüsselliste „vor /40 aus dem Code zu ziehen, nicht nur aus dem Kommentar“. Abgleich mit `FRONTEND_TO_RENDERER_METRIC_ID`:
- **Namensabweichung:** Spec-Tabelle nennt `wind_chill_min` / `wind_chill_max`; der echte Vergleichsschlüssel heißt `wind_chill_min_c` / `wind_chill_max_c`. Die Tabelle muss korrigiert werden, sonst bleibt die Zuordnung wirkungslos.
- **Weitere Schlüssel, die in der Spec-Tabelle fehlen** und keine Ampel-Metrik haben (⇒ „nicht zuordenbar“ im Bericht): `snow_depth_cm` (Ampel hat `snow_depth` – Zuordnung prüfen), `wind_direction_deg` (Ampel `wind_direction`, ohne Ampel-Seiten), `cloud_low_avg_pct` (Ampel `cloud_low`), `cloud_mid_avg_pct`, `cloud_high_avg_pct`, `pressure_avg_hpa`, `precip_type_dominant`.
- Schon in S1b gemappt: `temp_max_c`, `gust_max_kmh`. Hinzu kommt `temp_min_c` mit Vorrang-Regel (nur `von` → `lower.yellow`).
- Nicht zuordenbar laut Spec: `thunder_level_max`, `cape_max_jkg` (Gewitter ohne Zahlengrenzen, CAPE ohne Farbe).
- Prod-Daten (Probelauf) konnten in dieser Sitzung nicht direkt gelesen werden (Worktree-Sperre für `sudo`); die tatsächlich genutzten Schlüssel liefert der Probelauf auf Prod, Spec nennt als betroffen `henning/5f534011`, `cp-ac57aa1e29c65649`, `cp-eb6ba0b239d90e37`, `zillertal-t-glich`.

## Existing Patterns
- Zweiphasig: erst planen (Bericht), dann je Nutzer `tar.gz`-Sicherung, dann Read-Modify-Write mit Merge (#102), Sperre `exclusive_lock` (ADR-0083); unveränderte Dateien werden nicht geschrieben.
- Klemm-Regel in `_seite`: Verletzt das neue Gelb die Reihenfolge, wird die ganze Seite verschoben; unheilbare Fälle werden übersprungen, Altdaten bleiben.
- Seitenregel über Tupel in `_ZUORDNUNG`: `("von",)` nur untere, `("bis",)` nur obere, `_BEIDE` beides. Obere Seite: Gelb = `bis` + Schritt (`_schritt`: °C/mm 0,1, sonst 1).
- Vorbild `scripts/migrate_1231_corridors.py`.

## Dependencies
- Upstream: `app.ampel` (`template_id_for`, `validate_ampel`), `app.ampel_templates`, `app.metric_catalog.get_metric`, `services.file_lock`.
- Downstream: S1c-4 (Umschalten aller vier Kanäle) liest die migrierten Grenzen; S1c-3 (Altfelder nur lesbar) unabhängig. Vergleichs-Mails färben später nach der Ampel des Abos (`ComparePreset.display_config.ampel`).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (v1.1, S1c-Ergänzungen; Freigabe laut Kopfzeile noch als „ausstehend“ im Änderungsprotokoll vermerkt – in `/20-analyse` bzw. `/30` gegenlesen)
- Frühere Kontexte: `docs/context/feat-2792-s1-profil-ampel.md`, `docs/context/feat-2792-s1c-leser.md`

## Risks & Considerations
- **Wirkungslose Zuordnung durch falsche Schlüsselnamen** (`wind_chill_*_c`) – Test muss mit echten Schlüsseln aus `FRONTEND_TO_RENDERER_METRIC_ID` arbeiten (Ratsche gegen Drift der Schlüsselmenge erwägen).
- **Einheiten:** `visibility_min_m` wirkt auf die untere Seite (`von`, Katalog `*_lt`); falsche Seite würde die Sichtweiten-Ampel invertieren.
- **Vorrang `temp_min_c` vs. `temp_max_c`:** beide auf `temperature`; untere Seite kommt aus `temp_min_c`, `_band_eintragen` meldet sonst „schon belegt“.
- **Mandantentrennung:** Test mit zwei Nutzern (kein Fallback `default`).
- **Datenschutz der Bestandsdaten:** Prod-Lauf nur Probelauf → `--execute` mit Sicherung → zweiter Lauf „nichts zu tun“; Pre-Snapshot-Hook `data_schema_backup.py` beachten; Prod-Daten per `sudo -n -u claude-gregor` (außerhalb des Worktree-Wächters ausführen).
- **LoC:** Richtwert 120, `loc_limit_override` vor `/50` setzen.
- Zweisprachigkeit: Berichtszeilen des Skripts sind Betriebsausgabe, keine Nutzertexte (keine Katalogpflicht).

## Analysis

### Type
Feature (Teilpaket S1c-2, Betriebsskript-Erweiterung, kein Nutzertext).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/migrate_2792_profil_ampel.py` | MODIFY | `_ZUORDNUNG` um Vergleichsschlüssel ergänzen; Vorrang `temp_min_c` (untere Seite) vor `temp_max_c` |
| `tests/tdd/test_migration_2792_profil_ampel.py` | MODIFY | Nachtrag-Tests mit echten Schlüsseln, zwei Nutzer, Wiederholbarkeit |
| `docs/specs/modules/feat_2792_s1_profil_ampel.md` | MODIFY | Tabelle §4 „Nachtrag S1c-2“ korrigieren (`wind_chill_*_c`, Zusatzschlüssel) |

### Scope Assessment
- Files: 3 (Skript, Test, Spec); Skript ca. +25 LoC, Tests ca. +90
- Risk Level: LOW (zweiphasig, Sicherung, Altdaten bleiben erhalten; nie Replace)

### Technical Approach
1. **Zuordnung** (Seite = einseitig, wo der Katalog nur eine Richtung kennt):
   `wind_max_kmh`→wind (bis) · `visibility_min_m`→visibility (von) · `precip_sum_mm`→precipitation (bis) · `pop_max_pct`→rain_probability (bis) · `snow_new_sum_cm`→fresh_snow (bis) · `wind_chill_min_c`→wind_chill (von) · `wind_chill_max_c`→wind_chill (bis) · `uv_index_max`→uv_index (bis) · `temp_min_c`→temperature (von) · `sunny_hours_h`→sunshine (von) · `cloud_avg_pct`→cloud_total (bis) · `humidity_avg_pct`→humidity · `dewpoint_avg_c`→dewpoint (bis) · `freezing_level_m`→freezing_level (von) · `snowfall_limit_m`→snowfall_limit (von) · zusätzlich `cloud_low_avg_pct`→cloud_low (bis) und `snow_depth_cm`→snow_depth.
   Die Seiten ergeben sich aus der Vorlage (welche Seite hat Zahlen); Ratsche: jede zugeordnete Ampel-Metrik muss in `AMPEL_TEMPLATES` existieren.
2. **Vorrang `temp_min_c`**: `temp_max_c` ist `_BEIDE`; liefert es zuerst `von`, blockiert es `temp_min_c` („schon belegt“). Lösung: `von` aus `temp_min_c` gewinnt (Reihenfolge der Auswertung oder `temp_max_c` nur `bis`, wenn `temp_min_c` im selben Abo vorhanden ist).
3. **Nicht zuordenbar (Bericht mit Begründung)**: `thunder_level_max` (keine Zahlengrenzen), `cape_max_jkg` (keine Farbe), `wind_direction_deg`, `cloud_mid_avg_pct`, `cloud_high_avg_pct`, `pressure_avg_hpa`, `precip_type_dominant` (keine Ampel-Metrik bzw. keine Seiten).
4. **Ratsche gegen Drift**: Test zieht die Schlüsselmenge aus `FRONTEND_TO_RENDERER_METRIC_ID`; jeder Schlüssel ist entweder zugeordnet oder ausdrücklich „nicht zuordenbar“, sonst rot.
5. **Rollout**: Probelauf → `--execute` (tar.gz) → zweiter Lauf „nichts zu tun“, erst Staging, dann Prod (`sudo -n -u claude-gregor`); Bericht ins Issue. Reihenfolge-Gate: vor Prod-Deploy von S1c-4.

### Dependencies
Upstream `app.ampel`, `app.ampel_templates`, `app.metric_catalog`, `services.file_lock`. Downstream S1c-4 (Leser). Unabhängig von S1c-3.

### Befund gegen den Plan
Spec-Tabelle ist unvollständig/falsch: `wind_chill_min/max` müssen `wind_chill_min_c/max_c` heißen (sonst wirkungslos); sieben Schlüssel fehlen. Spec-Korrektur ist Teil von /30.

### Open Questions
- [ ] Wirkt die heutige Wertebereich-Markierung auf `thunder_level_max`/`cape_max_jkg` sichtbar? (Spec verlangt Prüfung vor /40; Antwort aus Probelauf Prod.)
- [ ] Tatsächlich genutzte Schlüssel auf Prod: Probelauf nötig (Worktree-Sperre verhinderte Lesen). Wird in /40 per `sudo -n -u claude-gregor` außerhalb des Wächters geholt.
- [ ] `loc_limit_override` vor /50 setzen.
