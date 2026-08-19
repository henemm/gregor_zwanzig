# Context: feat-1848-a1-tagesfenster-kennungen

Scheibe A1 von #1848 Teil A. Erstellt 2026-08-19, Phase 1.

> 🔴 **ZUSCHNITT GEAENDERT nach der Analyse (PO-Entscheid 2026-08-19, Phase 2).**
> **Scheibe A1 entfaellt ersatzlos — es kommen KEINE neuen Registerkennungen.**
> Workflow-Name und Dateiname bleiben aus technischen Gruenden stehen (aktiver
> Workflow-State); der Branch heisst `feat-1848-a-ausblick-kanal-modul`.
> Was stattdessen gilt, steht unten unter „Analysis". Alles ab „Related Files" bis
> „Risks" ist als **Recherche-Fundus** weiter gueltig, die Zielsetzung nicht.

## Request Summary

Tages-Tief und Tages-Hoch sollen im 3-Tages-Ausblick **getrennte, einzeln waehlbare
Zeilen** werden — als reine Register-Kennungen, nicht als `{metric_id, aggregation}`-Paare.
PO-Vorgabe 2026-08-19: „Temperatur und Gefuehlte Temperatur wird doch heute schon in der
SMS als Hoch/Tief angezeigt. Genauso soll es hier auch ausgegeben werden."

A1 legt dafuer das Fundament im Zentralregister. A2 stellt das Speicherformat um,
A3 gibt dem Ausblick das geteilte Kanal-Modul.

## 🔴 Befund, der den Zuschnitt aendert

Die urspruengliche Annahme war: der Ortsvergleich braucht **eigene Tagesfenster-Kennungen**,
weil ihm die Gehzeit fehlt. **Am Code gemessen ist das nicht noetig** — die Fensterung
haengt gar nicht an der Kennung, sondern an der Flaeche:

| Flaeche | wer fenstert | Beleg |
|---|---|---|
| Trip | `segment_weather.py:266-276` schneidet auf die **Etappengrenzen** (Gehzeiten), bevor `weather_metrics.py` rechnet | `segment_weather.py:300-301` sagt das ausdruecklich |
| Ortsvergleich | `comparison_engine._filter_by_target_date_and_window()` schneidet auf **`target_date` + Tagesfenster** | `comparison_engine.py:43-86`, Werte ab `:199-211` |

Beide fuellen anschliessend **dieselben Feldnamen** (`temp_min_c`, `temp_max_c`,
`wind_chill_min_c`, `wind_chill_max_c`) — mit flaechen-eigener Bedeutung. Genau das ist
die im Repo schon benannte Regel **„bedeutungsgleich, nicht wertgleich"**
(`tests/unit/test_compare_catalog_derives_from_central_catalog.py:62-71`, Adversary-Nachtrag
in Commit `c18f8eb7`).

**Folge:** Zwei neue Kennungen mit `summary_fields={"min": "temp_min_c"}` bzw.
`{"max": "temp_max_c"}` funktionieren in **beiden** Flaechen automatisch richtig — jede
Flaeche liefert ihre eigene Fensterung. Es braucht **kein** Ortsvergleich-Sonderpaar.

⚠️ Offene Designfrage fuer Phase 2: Im Trip existierten dann
`temperature_day_high` (Gehzeit, nur SMS-Token) **und** eine neue Tabellen-Kennung fuer
Tages-Hoch. Zwei aehnlich benannte Dinge — exakt die Verwechslungsgefahr, vor der
`metric_catalog.py:180-183` warnt. Namensgebung und Abgrenzung sind zu klaeren.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/app/metric_catalog.py:111-688` | Zentralregister `_METRICS`, 32 Eintraege / 29 waehlbar. Hier entstehen die neuen Kennungen |
| `src/app/metric_catalog.py:775-783` | `SMS_MULTI_SYMBOLS_BY_METRIC` — abgeleitet, nicht danebengepflegt |
| `src/app/metric_catalog.py:899-910` | `summary_field_for()` — liefert `None` ohne `summary_fields`, **kein Fallback** |
| `src/app/loader.py:751-767` | `_DERIVED_METRIC_RULES` + `_append_derived_metrics()` — Muster fuer Bestandsableitung (`derived=True`) |
| `src/app/loader.py:854, 895, 931` | Ableitung wirkt auch auf Kanal- und Report-Ebene (DEC-6b aus #1728) |
| `src/output/renderers/compare_outlook_metric_ids.py:56-68, 128-134` | Ausblick **verwirft** jeden Eintrag ohne `summary_fields` — zentrale Einschraenkung |
| `src/output/renderers/compare_metric_catalog.py:76-162` | Compare-Katalog ist **kuratierte Literal-Liste** (26 Eintraege), nur Anzeigenamen kommen live aus dem Register |
| `src/output/renderers/channel_layout.py:72-78` | `VISIBILITY_GATE_IDS` — Liste, die bei neuen Sichtbarkeits-Gates nachzuziehen ist |
| `src/output/renderers/compare_hourly_metric_ids.py:59-65` | `HOURLY_EXCLUDED_METRIC_IDS` — dito |
| `src/services/comparison_engine.py:43-86, 199-211` | Tagesfenster-Fensterung im Ortsvergleich |
| `src/services/segment_weather.py:266-276, 300-301` | Etappen-Fensterung im Trip |
| `src/services/weather_metrics.py:474-476, 525-540, 944-946, 1024-1037` | Befuellung der `temp_*`/`wind_chill_*`-Felder |
| `src/app/day_window.py:20-21, 24-54` | `DAY_WINDOW_START_HOUR=4`, `END=19`, `resolve_configured_window()` |

## Existing Patterns

**Das Vorbild ist #1728 Scheibe 1** (`c18f8eb7`, Nachzuege `e0b279ff`, `ac8501f5`,
`5c4e435d`) — es hat exakt diese Aufgabe schon einmal geloest, fuer die Gehzeit-Groessen.
Aenderungs-Checkliste daraus:

1. Registereintraege in `metric_catalog.py` (+ `trip_default_rank`, falls Anlege-Standard)
2. `SMS_MULTI_SYMBOLS_BY_METRIC` — Symbole wandern von der Elterngroesse zur neuen Kennung
3. `loader.py`: `_DERIVED_METRIC_RULES` fuer Bestandsableitung, **auf allen drei Ebenen**
   (global, `per_channel_layouts`, `per_report_layouts`)
4. Serialisierungsfilter `if not getattr(mc, "derived", False)` beim Speichern
5. `VISIBILITY_GATE_IDS` und `HOURLY_EXCLUDED_METRIC_IDS` nachziehen
6. Renderer-Pillen / MetricSpec-Gates
7. Doku: `sms_format.md`, `api_contract.md`, `metric_output_matrix.md`
8. Tests: eigene TDD-Datei je Verhalten + Bestandsableitungs-Test

🔴 **Lehre aus #1856 E7 (`5c4e435d`):** #1728 S1 hatte **drei Listen nicht nachgezogen**
(`_DERIVED_METRIC_RULES[0]/[1]`, `VISIBILITY_GATE_IDS`, `METRIC_PRIORITY`). Ein
Listen-Waechter fing das erst nachtraeglich. Diese Listen sind die bekannte Fehlerquelle.

## Dependencies

- **Upstream:** `metric_catalog` (Register), `day_window` (Fensterung), `SegmentWeatherSummary`-Felder
- **Downstream:** Ausblick-Renderer, Compare-Katalog, SMS-Token-Builder, Loader/Persistenz,
  Frontend `WeatherMetricsTab.svelte` + `CompareOutlookLayoutControls.svelte`

## Existing Specs

- `docs/specs/modules/feat_1848_a_kaskade_eine_quelle.md` — Haelfte 1 von Teil A (geliefert)
- `docs/context/feat-1848-ausblick-vokabular.md` — Analyse 2026-08-18, Risiken R1-R6, PO-Entscheid
- `docs/specs/modules/feat_1848_c_waechter_gehzeit_trip_exklusiv.md` — Scheibe C
- `docs/specs/modules/issue_1361_1368_ausblick_konfigurierbar.md` — Ursprung des Paar-Vokabulars
- `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md` — AC-14/15/16 zur Kaskade

## Risks & Considerations

**R-A1-1 — Waechter aus Scheibe C wird faelschlich rot.**
`tests/unit/test_gehzeit_metriken_bleiben_trip_exklusiv.py:415-416` sammelt alle
Registereintraege, deren `label_de` den Substring `"(Gehzeit)"` traegt, und verlangt
Mengengleichheit mit dem Literal `GEHZEIT_METRIC_IDS` (Zeile 53-56). Zusaetzlich prueft
`:519-526` die Endpoint-Antwort auf `"(Gehzeit)"` im `label`.
**Mitigation:** Die neuen Labels duerfen den Zusatz `"(Gehzeit)"` **nicht** tragen.

**R-A1-2 — Derselbe Waechter ist blind fuer Werte-Semantik.**
Er prueft ausschliesslich Katalog-/Endpoint-**Mitgliedschaft**, nie **Werte**. Wuerde A1
die Bedeutung der bestehenden vier Kennungen verschieben (oder fuer die neuen doch
`collect_hiking_window_points()` verwenden), faellt das nicht auf. Der einzige Vermerk
dazu ist ein Doku-Kommentar, kein Test.

**R-A1-3 — Ohne `summary_fields` gibt es im Ausblick keinen Wert.**
`compare_outlook_metric_ids.py:56-68, 128-134` verwirft solche Eintraege ersatzlos; einen
Ausweichweg wie bei SMS (hart verdrahtete Symbol→Feld-Bindung, `builder.py:324-330`) gibt
es im Ausblick nicht. Die neuen Kennungen **muessen** `summary_fields` tragen.

**R-A1-4 — Namensverwechslung im Trip.** Siehe offene Designfrage oben.

**R-A1-5 — Der Compare-Katalog ist Handarbeit.** `compare_metric_catalog.py:76-162` ist
eine kuratierte Literal-Liste. Neue Kennungen erscheinen dort **nicht automatisch** —
Eintrag plus Pflege von `CENTRAL_METRICS_COVERED_ELSEWHERE`
(`tests/unit/test_compare_catalog_derives_from_central_catalog.py:44-88`) noetig.

**R-A1-6 — Keine Bestandsdaten, aber Drei-Werte-Semantik bleibt heikel.**
Auf Produktion und Staging ist keine einzige `outlook_metrics`-Auswahl gespeichert
(Messung 2026-08-18). Die `None`/`[]`/gefuellt-Semantik traegt trotzdem weiter und darf
nicht durch unbedachtes Schreiben kippen (BUG-DATALOSS-GR221, #102).

---

# Analysis (Phase 2, 2026-08-19)

## Type

Feature.

## 🟢 PO-Entscheid, der den Zuschnitt festlegt

Vorgelegt wurde die Frage, ob Tief und Hoch im Ausblick einzeln **waehlbar** sein sollen
oder nur gemeinsam **angezeigt**. Entscheid: **gemeinsam angezeigt, eine Zeile.**

> Der Nutzer waehlt im Ausblick „Temperatur" — eine Zeile, wie bei den Kanaelen — und
> sieht Tief UND Hoch als Spanne (`8–19°`). Nur-das-Hoch-Zeigen entfaellt.

**Folge: Scheibe A1 (neue Registerkennungen) entfaellt vollstaendig.** Damit fallen auch
alle daran haengenden Probleme weg:

| Problem aus der Analyse | Status |
|---|---|
| Doppelte Spalten — neue Kennung und `temperature` zeigen dasselbe Feld; **keine Dedup-Logik** in `resolve_metric_col_order()` (`email/helpers.py:311-324`), nur `col_key`-Eindeutigkeit je Kennung | entfaellt |
| Namensverwechslung „Tages-Hoch" vs. „Tages-Hoch (Gehzeit)" | entfaellt |
| 54 register-abhaengige Listen im Repo, davon **2 mechanisch erzwungen** (`METRIC_PRIORITY` via `soll_vollstaendig`; `COMPARE_METRIC_CATALOG`/`CENTRAL_METRICS_COVERED_ELSEWHERE` via `test_every_selectable_central_metric_has_a_compare_entry`) und ~15 „kommt drauf an" | entfaellt |
| Bruch von `test_kaskade_ac9_fixture_carries_full_catalog_width` (`tests/tdd/test_channel_metric_matrix.py:1088-1106`) — eingefrorene Fixture gegen dynamisch gezaehlte Katalogbreite | entfaellt |
| R-A1-1 (Waechter aus Scheibe C wird faelschlich rot) und R-A1-4 | entfallen |

**Weiter gueltig bleiben** R-A1-3 (ohne `summary_fields` kein Ausblick-Wert — betrifft jetzt
die Frage, wie eine Kennung ohne Paar ihre Spalte bekommt) und R-A1-6 (Drei-Werte-Semantik).

## Was stattdessen zu tun ist

| Scheibe | Inhalt |
|---|---|
| **A2 — Backend** | `outlook_metrics` speichert **reine Kennungen** statt `{metric_id, aggregation}`-Paare · Bestandsableitung Paar→Kennung, **dedupliziert** (`{temperature,min}` + `{temperature,max}` ⇒ ein `temperature`) · `outlook_columns()` rendert fuer eine Kennung mit mehreren Auswertungen **eine Spalte als Spanne** statt zwei Spalten |
| **A3 — Frontend** | `CompareOutlookLayoutControls.svelte` bekommt das Kanal-Modul-Verhalten: **nur abwaehlbar** aus der Grundauswahl statt freier Katalog-Checkbox-Liste · sichtbare „Aus"-Gruppe mit Zurueckholen · gleiche Beschriftungsquelle wie die Kanaele · **beide Flaechen** (Trip + Ortsvergleich) |

## Affected Files (Scheibe A2)

| Datei | Change | Beschreibung |
|---|---|---|
| `src/app/models.py:844` | MODIFY | `outlook_metrics: Optional[list[dict]]` → Kennungsliste |
| `src/app/loader.py:948, 1558-1561` | MODIFY | Lese-/Schreibpfad; Paar→Kennung ableiten, Drei-Werte-Semantik (`None`/`[]`/gefuellt) erhalten |
| `src/output/renderers/compare_outlook_metric_ids.py:45-149` | MODIFY | `resolve_outlook_metrics()` auf Kennungen; `outlook_columns()` Spanne statt Doppelspalte |
| `src/services/report_config_resolver.py:249, 291` | MODIFY | Aufrufer nachziehen |
| `frontend/src/lib/types.ts:299` | MODIFY | Typ auf Kennungsliste |
| Tests | CREATE/MODIFY | u.a. `tests/tdd/test_compare_outlook_metric_selection.py`, `test_trip_outlook_metrics_persistence.py`, `test_trip_outlook_metric_selection.py` |

## Scope Assessment

- Dateien: ~8 (A2), ~6 (A3)
- Risk Level: **MEDIUM** — nutzersichtbare Ausgabe aendert sich (zwei Spalten → eine Spanne)
- Erleichterung: **keine Bestandsdaten** — auf Produktion und Staging ist keine einzige
  `outlook_metrics`-Auswahl gespeichert (Messung 2026-08-18, positive Gegenprobe ueber
  `display_config`). Die Ableitung ist trotzdem zu bauen (Drei-Werte-Semantik, kuenftige
  Bestaende), aber ohne Migrationsdruck.

## Technical Approach

Der Ausblick verliert sein eigenes Vokabular und wird eine **weitere Flaeche derselben
Metrik-Kaskade** — Grundauswahl als Maximum, die Flaeche darf nur abwaehlen und ordnen.
Die Kaskadenregel dafuer existiert bereits an genau einer Stelle
(`allowed_metric_ids_for_report_type()`, seit #1848 Scheibe A) und muss nicht erweitert
werden — `resolve_trip_outlook_metrics()` ruft sie schon auf.

Die Fensterung bleibt flaechen-eigen (Trip: Etappengrenzen, Ortsvergleich: Tagesfenster).
Die Kennung transportiert sie nicht — das ist bestehende, dokumentierte Bauart
(„bedeutungsgleich, nicht wertgleich", `test_compare_catalog_derives_from_central_catalog.py:62-71`).

## Open Questions (gehen mit der Spec an den PO)

- [ ] **Schreibweise der Spanne** — `8–19°` in einer Zelle? Der PO hat diesen Entwurf in
      der Entscheidungsvorlage gesehen und gewaehlt; Trennzeichen und Einheiten-Wiederholung
      gehoeren als AC festgeschrieben.
- [ ] **`wind_chill`** verhaelt sich wie `temperature` (min/max) — gleiche Behandlung,
      in den ACs mit abdecken.
- [ ] **`avg` bei `temperature`** — der Mittelwert ist heute als eigenes Paar waehlbar.
      Faellt er im Ausblick weg, oder erscheint er zusaetzlich? **Braucht PO-Entscheid.**
