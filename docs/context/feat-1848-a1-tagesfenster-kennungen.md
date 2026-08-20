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

---

# 🔴 KORREKTUR des Zuschnitts (PO, 2026-08-20)

**Der Abschnitt „Analysis" oben ist in seiner Schlussfolgerung ueberholt. Scheibe A1
entfaellt NICHT.** Grund: Die Entscheidungsvorlage, auf der „A1 entfaellt" beruhte, hat das
SMS-Ist-Verhalten falsch wiedergegeben. Der PO hat richtiggestellt: „exakt so wie
Temperatur bei SMS heute."

## Das SMS-Ist-Verhalten, nachgelesen (Issue #1824, `docs/reference/sms_format.md:67, 136-139`)

| Fall | Ausgabe |
|---|---|
| Tief **und** Hoch gewaehlt | **ein** Bereichs-Token unter dem Hoch-Kuerzel: `D13/27` |
| nur Tief gewaehlt | `L13` |
| nur Hoch gewaehlt | `D27` |

🔴 **Trennzeichen ist ein Schraegstrich, NICHT ein Bindestrich.** Begruendung im Doku-Text:
bei Minusgraden waere der Bindestrich zugleich Trenner und Vorzeichen (nicht eindeutig
parsbar); der Schraegstrich ist GSM-7-sicher. Beispiele aus der Doku: `D13/27`, `D-12/-4`,
`D13/-`. Jede Haelfte kann unabhaengig Wert, Null-Form oder Lueckenform sein.

**Die frueher hier vorgeschlagene Schreibweise mit Bindestrich und Gradzeichen ist damit
falsch** und darf nicht in die ACs.

## Was das fuer den Zuschnitt heisst

Getrennte Waehlbarkeit von Tief und Hoch braucht **eigene Kennungen** — das Kanal-Modul
kennt nur Kennungen, keine Paare aus Kennung und Auswertung. Also lebt A1.

Das frueher als Blocker notierte **Doppelspalten-Problem ist keiner**: #1728 hat es fuer die
SMS bereits geloest, indem die Kuerzel zu den neuen Kennungen wanderten und
`temperature`/`wind_chill` „nur noch den Stundenwert fuer Stundentabelle und Telegram-Zelle"
liefern (`sms_format.md:94`). Dasselbe Muster traegt hier.

## 🟢 PO-Entscheid 2026-08-20 — welche Groessen der Trip-Ausblick benutzt

> **Der Trip-Ausblick benutzt dieselben Groessen wie die SMS** — die vier bestehenden
> Gehzeit-Kennungen. Eine Groesse, ein Wert, kanaluebergreifend gleich.
> Fuer den Ortsvergleich (keine Route, keine Gehzeit) kommen eigene Tief/Hoch-Groessen
> ueber das Tagesfenster dazu.

Damit bleibt der Waechter aus Scheibe C unveraendert gueltig: die Gehzeit-Groessen bleiben
trip-exklusiv, die neuen Tagesfenster-Groessen sind ein **separates** Paar.

## 🔴 Offener technischer Kernpunkt fuer die A1-Spec

Die vier Gehzeit-Kennungen tragen heute **keine** `summary_fields` — im Ausblick entsteht
fuer sie deshalb **keine Spalte** (`compare_outlook_metric_ids.py:56-68, 128-134` verwerfen
sie ersatzlos, `summary_field_for()` hat keinen Fallback). Ein Tabellenwert muss erst
nutzbar gemacht werden.

⚠️ **Dabei nicht annehmen, dass `temp_min_c` der gesuchte Wert ist.** Gemessen:

| Wert | Fensterung | Quelle |
|---|---|---|
| `SegmentWeatherSummary.temp_min_c` | **Etappengrenzen** (Segment-Start bis -Ende) | `segment_weather.py:266-276` → `weather_metrics.py:525-540` |
| SMS-Token `L`/`D` | **Gehzeit** — enger als die Etappengrenzen | `collect_hiking_window_points()` → `hiking_field_min_max()`, `sms_trip.py:238-258` |

Beide sind aehnlich, aber **nicht nachweislich gleich**. Die Spec muss festlegen, welcher
Wert im Ausblick erscheint — und wenn es der Gehzeit-Wert sein soll (PO-Entscheid: „dieselben
wie die SMS"), muss der Weg dorthin gebaut werden. **Vor der Umsetzung ist auszumessen, in
wie vielen Faellen die beiden Werte ueberhaupt auseinanderliegen** — sonst ist jeder
Gleichheitsbefund trivial wahr.

---

# 🔴 IST-ZUSTAND GEMESSEN (2026-08-20) — die Anzeige-Praemisse von A1 traegt nicht

Alles unten per **echtem Funktionsaufruf** belegt, nicht aus dem Code abgeleitet.

## Es gibt ZWEI Ausblick-Formen, beide in Trip UND Ortsvergleich

| Form | Wann | Temperatur-Darstellung |
|---|---|---|
| **A) Feste 7-Spalten-Form** (Altbestand, `metrics=None`) | keine Auswahl gespeichert | HTML: **zwei** Spalten `N`/`D`, je eine Zahl (`outlook.py:258-259`). Klartext: **ein Spannen-Token** `8–16°C` (`helpers.py:940-947`) |
| **B) Konfigurierbare Spaltenauswahl** (#1361/#1368/#1373) | `metrics` gesetzt | jede Spalte **immer genau ein Wert**, nie eine Spanne |

Form B ist der Pfad, den das Frontend-Bedienteil bedient (`CompareOutlookLayoutControls.svelte`,
eingebunden ueber das geteilte `WeatherMetricsTab.svelte`). Trip via
`resolve_trip_outlook_metrics()` (`trip_report.py:209`), Compare via `resolve_outlook_metrics()`
(`report_config_resolver.py:249/291`).

## 🔴 Tief und Hoch sind im Ausblick HEUTE SCHON getrennt waehlbar

```
outlook_columns([{"metric_id":"temperature","aggregation":"max"},
                 {"metric_id":"temperature","aggregation":"min"}])
→ [{'label': 'Temperatur Maximum', 'field': 'temp_max_c', 'unit': '°C', 'decimals': 0},
   {'label': 'Temperatur Minimum', 'field': 'temp_min_c', 'unit': '°C', 'decimals': 0}]
format_outlook_value(27.3, max) → '27 °C'   ·   format_outlook_value(8.9, min) → '9 °C'
```

Label-Kollisionsaufloesung haengt „Minimum"/„Maximum" an (`compare_outlook_metric_ids.py:144-148`).
Frontend bestaetigt es woertlich: „Groessen mit mehreren Auswertungen (Temperatur, gefuehlte
Temperatur) bekommen je Auswertung ein unabhaengiges Kaestchen"
(`CompareOutlookLayoutControls.svelte:146-148`).

**Folge fuer den Zuschnitt:** Die Begruendung „getrennte Waehlbarkeit braucht eigene Kennungen"
gilt **nicht fuer die Anzeige** — die kann es schon. Sie gilt nur fuer die **Speicherform**,
weil das Kanal-Modul ausschliesslich Kennungen kennt und keine Paare aus Kennung+Auswertung.
Das ist exakt die Naht zu **Scheibe A2**, nicht zu A1.

## Praezedenzfall Spannen-Zelle

Der einzige Beleg im Ausblick ist der Klartext der **Alt-Form**: `f"{tl}–{th}°C"`
(`helpers.py:943`, Halbgeviertstrich, EIN Einheiten-Suffix). Tests mit echten Zahlen:
`test_compare_outlook.py:205` (`"9–20°C"`), `test_compare_outlook_metric_selection.py:265-267`
(nennt es „festen Temperatur-Spannen-Token").

🔴 **Zwei verschiedene Ist-Schreibweisen fuer dieselbe Sache:** SMS nutzt den **Schraegstrich**
(`D13/27`, minusfest), der Ausblick-Klartext den **Halbgeviertstrich** (`8–16°C`). „Exakt wie
die SMS" muss entscheiden, welche im Ausblick gilt — im HTML gibt es heute **gar keine**
Spannen-Zelle.

## `summary_fields` → Spalte, und warum die Gehzeit-Kennungen rausfallen

Weg: `MetricDefinition.summary_fields` (`metric_catalog.py:42`) → `summary_field_for()`
(`metric_catalog.py:899-910`, liefert `None` bei `selectable=False` oder fehlendem Key) →
`_summary_field()` (`compare_outlook_metric_ids.py:34-42`) → Drop-Bedingungen Zeile **62**
und **133**.

**Bestaetigt per Ausfuehrung** — die vier Gehzeit-Kennungen werden ersatzlos verworfen:
```
resolve_outlook_metrics([{"metric_id":"temperature_day_low",  "aggregation":"min"},
                         {"metric_id":"wind_chill_day_high", "aggregation":"max"}])
WARNING: ... ohne Katalog-Entsprechung — Eintrag wird verworfen (vgl. #1361 Befund 3)
→ []
```
Mehrfach-`summary_fields` gibt es: `temperature` traegt **drei** (`min`/`max`/`avg`,
`metric_catalog.py:119`), `wind_chill` zwei (`:218`). Das erzeugt aber **keine** Spannen-Zelle,
sondern mehrere separate waehlbare Spalten.

## `avg` ist im Ausblick heute NICHT waehlbar

Zentral vorhanden, im Compare-Katalog fehlend — `COMPARE_METRIC_CATALOG`
(`compare_metric_catalog.py:76-162`) hat fuer `temperature` nur `temp_max_c` (`:101-103`) und
`temp_min_c` (`:113-115`), **keine** `avg`-Zeile:
```
summary_field_for("temperature", "avg")                            → 'temp_avg_c'
resolve_outlook_metrics([{"metric_id":"temperature","aggregation":"avg"}])  → []
```
Die Picker-Liste zeigt fuer Temperatur daher nur zwei Kaestchen. **Die Open Question
„faellt avg weg oder kommt er dazu?" ist damit falsch gestellt** — er ist heute schon nicht da;
die Frage lautet, ob er neu dazukommen soll. → **Nicht in A1.** Das Zielbild „Grundauswahl ist
das MAXIMUM, der Kanal darf nur abwaehlen" macht das zu einem Punkt fuer **A3** (Kanal-Modul
im Ausblick), nicht zu einer A1-Aenderung am Katalog.

---

# 🔴 WERT-MESSUNG (2026-08-20): Etappenwert vs. Gehzeit-Wert

Messkript (Wegwerf, Scratchpad): `measure_ausblick_vs_gehzeit.py`.

## Mechanik der Abweichung

| Pfad | Fensterung | Fundstelle |
|---|---|---|
| Ausblick heute | `[start_floor, end_floor)` je Segment — **Endstunde EXKLUSIV** | `segment_weather.py:266-273`, gelesen ueber `aggregate_stage()` in `trip_report_scheduler.py:2286` → `outlook.py:503-504` |
| SMS `L`/`D` | wie oben, **ausser beim letzten Segment: Ankunftsstunde INKLUSIV** | `day_window.py:210-229` → `hiking_field_min_max()`, `sms_trip.py:238-239` |

Die Abweichung ist also die **Randbehandlung der Ankunftsstunde**, kein Rundungs- oder
Aggregationsunterschied.

## Messwerte (Varianz ausgewiesen, nicht nur Trefferzahl)

| Block | Fenster verschieden | Werte verschieden | Δ |
|---|---|---|---|
| 6 bestehende #1417-Konstellationen (`tests/tdd/_hiking_window_fixtures.py`) | **3/6** | 3 | bis **-9,0 °C** (adversarisch konstruiert) |
| Sweep 60 Kombis (Segmente 1-3 × Start 6-9 × Ankunft 13-20, glatter Tagesgang) | **60/60** strukturell | **24/60** | Median **1,23 °C**, Max **1,66 °C** |

Die 36 deckungsgleichen Faelle sind **zufaellig** gleich (Ankunftsstunde traegt dort nicht das
Extremum) — nicht Beleg fuer Gleichheit.

**Gerichtet:** `Etappe - Gehzeit <= 0` in **allen 84** Faellen. Die Etappen-Fensterung kann der
Gehzeit-Fensterung nur einen Datenpunkt VORENTHALTEN, nie einen hinzugewinnen. ⇒ **Der Ausblick
zeigt systematisch ein zu kuehles Hoch.** Beim Tief 0/84 — die Ankunft liegt in realistischen
Etappenzeiten nie am Tagestiefpunkt (strukturell moeglich, praktisch selten).

## 🔴 Das ist ein Nachzug zu #1417, keine Feature-Luecke

**#1417 („Mail und Kurznachricht zeigen fuer dieselbe Etappe verschiedene Temperaturen") ist
CLOSED.** Der Fix hat SMS, Telegram-Kurzuebersicht und E-Mail-Kurzzusammenfassung auf
`collect_hiking_window_points()` umgestellt — **der 3-Tages-Ausblick war nicht dabei** und liest
weiter `summary.temp_min_c`/`temp_max_c`. Dieselbe Ursache (exklusive Ankunftsstunde), dieselbe
Richtung, eine uebersehene Flaeche.

`segment_weather.py` bleibt dabei bewusst unveraendert (#1329: rein pro Segment, darf nicht
wissen, an welcher Stelle des Berichts es steht) — deshalb wurde schon #1146 nicht dort behoben.

## Naht fuer den Fix (~20-25 LoC)

`trip_report_scheduler.py:2286-2338` hat `seg_weather` bereits vorliegen — dort zusaetzlich
`collect_hiking_window_points()` + `hiking_field_min_max(..., "t2m_c")` aufrufen (dieselben
Funktionen, die `sms_trip.py` nutzt) und als optionale Parameter an `build_outlook_row()`
durchreichen; in `outlook.py:503-504` `temp_lo`/`temp_hi` daraus ableiten, **fail-soft** zurueck
auf `summary.temp_*`. Diskriminator `trip_display_config is not None`, analog dem bestehenden
#1841-Muster fuer die Gewitterspalte (`outlook.py:~612-639`).

---

# 🟢 PO-ENTSCHEID 2026-08-20 — Darstellung im Ausblick

**Gewaehlt: EINE Zelle mit SCHRAEGSTRICH** (die SMS-Schreibweise), wenn Tief und Hoch beide
gewaehlt sind.

```
Temperatur          Minusgrade eindeutig      nur eine Haelfte
9/27                -12/-4                    13/-
```

Der PO hat mit dem ausdruecklichen Hinweis gewaehlt, dass der Ausblick-**Klartext** heute die
andere Schreibweise fuehrt (`9–20°C`, Halbgeviertstrich, `helpers.py:943`) und **mit angeglichen
werden muss** — sonst stehen zwei Schreibweisen fuer dieselbe Sache nebeneinander.

⚠️ Zu klaeren beim Zuschnitt: die Halbgeviertstrich-Schreibweise sitzt in der **festen
7-Spalten-Altform**. Ob deren Klartext mit angeglichen wird oder nur der konfigurierbare Pfad,
haengt an den Golden-Fixtures (`test_compare_outlook.py:205` erwartet `"9–20°C"`) — technischer
Zuschnitt, keine PO-Frage.
