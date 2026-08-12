# Context: feat-1680-thunder-herkunft

**Issue:** #1680 — Gewitter: Herkunft der Stufe sichtbar machen (welches Signal trägt die Einstufung)
**Bezug:** #1419 (Epic, Rang 4), Entscheidung **E1** (PO 2026-08-08), Gesamtkonzept Abschnitt 4.5 Option (c)
**Track:** Full Process · erstellt 2026-08-11

## Request Summary

Die fusionierte Gewitterstufe (`kein/leicht/mittel/hoch`) entsteht nach dem Prinzip „das schärfste
Signal gewinnt" aus mehreren Zutaten, gibt aber nur die Stufe zurück — **nicht, welche Zutat sie
ausgelöst hat**. Ziel: Die Stufe trägt ihre Herkunft sichtbar mit, damit im **Ortsvergleich**
erkennbar wird, dass Korsika und die Alpen auf verschiedenen Größen fußen.

---

## Wo die Herkunft heute verloren geht — ZWEI Stellen

| # | Ort | Code |
|---|---|---|
| **1** | Fusion über die Zutaten | `src/output/metric_format.py:401-432` — `signals: list[ThunderLevel]` ist **flach und namenlos**; `return max_thunder(signals)` |
| **2** | Maximum über die Stunden | `src/services/weather_metrics.py:590-609` — `_compute_thunder_level` maximiert erneut, ebenfalls namenlos → `SegmentWeatherSummary.thunder_level_max` (`models.py:458`) bräuchte ein Parallelfeld |

Wer nur Stelle 1 löst, hat die Herkunft am Datenpunkt, aber **nicht** am Tageswert — und der
Tageswert ist genau das, was der Ortsvergleich zeigt (`compare_html.py:593-596`:
`_DAILY_AGGREGATE_FIELD["thunder_max"] = "thunder_level_max"`).

## Die Zutaten der Fusion — VIER, nicht fünf

`thunder_level_from_signals()` (`metric_format.py:344-432`), einziger Produktiv-Aufrufer
`src/providers/thunder_enrichment.py:135`:

| Zutat | Feld | Schwellen | Verfügbar |
|---|---|---|---|
| WMO-Wettercode | `wmo_code` → 95/96/99 ⇒ **HIGH**, sonst NONE | fest | **überall** |
| Blitzdichte | `lightning_density_per_km2_3h` | fest 0,003/0,015/0,075 (`metric_format.py:280-282`) | **nur FR** (inkl. Korsika) |
| CAPE, gedämpft durch CIN | `cape_jkg` + `convective_inhibition_jkg` | `model_registry.cape_ladder_thresholds_jkg()` (11 Einträge Modell×Gebiet) | überall, wo CAPE kommt |
| Blitzpotenzial LPI | `lightning_potential_lpi_jkg` | DE_ALPEN 1/30/50 · EU_REST 5/20/50 (**Interim, unbelegt**, `model_registry.py:149-151`) | DWD-Gebiete, **nicht FR** |

🔴 **`sdi_2` (Superzellen) ist NICHT in der Fusion** (`models.py:172` befüllt, nirgends gelesen).
Das Beispiel aus dem Issue-Text und Konzept 4.5 („hoch, Blitzpotenzial**+Superzelle**") beschreibt
damit einen Zustand, den der Code nicht hat. Ebenso wenig fließt der Radar-Nowcast ein (E3, offen).
Gebietszuordnung: `src/providers/thunder_routing.py:63-67` (FR → DE_ALPEN → EU_REST, first-match).

---

## 🔴 Zwei Befunde, die die Aufgabe verändern

### A) Die Gleichstands-Reihenfolge wird plötzlich nach außen sichtbar

`max_thunder()` (`metric_format.py:268-273`) ist `max(levels, key=thunder_ordinal)` — Python-`max`
behält **das erste** Element bei Gleichstand. Damit gilt heute implizit die Priorität
**Wettercode > Blitzdichte > CAPE > LPI**, allein aus der Reihenfolge der `if`-Blöcke. Das ist
nirgends dokumentiert und durch keinen Test bewacht — ein Implementierungsartefakt. Sobald die
Herkunft ausgewiesen wird, ist diese Reihenfolge eine **Produktaussage** und braucht eine bewusste
Entscheidung (inkl. der Frage: was, wenn zwei Zutaten dieselbe Stufe tragen — erste, alle, oder
eine Rangfolge?).

### B) ~~Bei „hoch" gewinnt fast immer der Wettercode~~ — **NACHGEMESSEN und im Kern WIDERLEGT**

🔴 **Diese Vermutung stand hier zuerst als Befund. Die Messung an echten Feldern hat sie in der
entscheidenden Aussage widerlegt.** Der ursprüngliche Wortlaut steht unten durchgestrichen, damit
niemand die verworfene Fassung erneut als Grundlage nimmt.

**Gemessen (2026-08-11, offline, echte Felder — keine Synthetik):**

| Datensatz | Ergebnis |
|---|---|
| ICON-D2 Alpen, Lauf 2026-08-11 03Z +12 h, **906 390 Gitterpunkte** (`cape_ml`+`cin_ml`+`lpi_max`, gepaartes Gitter) | HIGH bei **3,18 %** (28 866 Punkte) — **ganz ohne Wettercode-Signal**. Träger: CAPE 28 737, LPI 137 |
| AROME Korsika `litota3`, 2026-08-02, **21 901 Gitterpunkte** | Blitzdichte-HIGH bei **2,2 %** (479 Punkte). Maximum 21,2 = das 283-fache der HIGH-Schwelle |
| ICON-EU Abruzzen `lpi_con_max` | HIGH bei 0,5 % (4 167 Punkte) |
| Snapshot Mallorca (`data/users/default/weather_snapshots/gr221-mallorca.json`, 96 echte Stunden) | `wmo_code` **96/96 vorhanden, 0× fehlend**; Codes nur 0–3 ⇒ kein Gewitter, HIGH kam nicht vor — an diesem Satz nicht prüfbar |

⇒ **Eine Herkunfts-Kennzeichnung zeigt sehr wohl Unterschiedliches:** Alpen → CAPE (99,6 % der
HIGH-Fälle) bzw. LPI, Korsika → Blitzdichte. Auslegung (i) beantwortet die Vergleichsfrage also
doch — die Sorge war unbegründet.

**Was von der Vermutung bleibt (am Code belegt, nicht messbar):** Der Wettercode ist **binär**
(`openmeteo.py:679-683`: 95/96/99 ⇒ HIGH, sonst NONE) und wird als **erstes** in `signals` gelegt
(`metric_format.py:400`). Er kann deshalb *nur* auf HIGH gewinnen, nie auf LOW/MED — und **wo
Open-Meteo 95/96/99 meldet, verdeckt die Reihenfolge eine gleichzeitig vorhandene Blitz-/CAPE-
Evidenz.** Die **Ko-Auftretensrate** („Wettercode 95/96/99 UND ein anderes Signal auf HIGH") ist
mit Bordmitteln **nicht messbar** — kein Fixture führt Wettercode und Blitzdichte/LPI am selben
Ort und Zeitpunkt. Dafür bräuchte es eine Aufzeichnung aus dem Produktivpfad `enrich_thunder()`
einer Korsika-/Alpen-Tour in einer Gewitterlage.

<details><summary>Verworfene Erstfassung (nicht mehr gültig)</summary>

### ~~B) Bei „hoch" gewinnt fast immer der Wettercode — die Zielfrage bliebe unbeantwortet~~

Der Wettercode setzt bei 95/96/99 direkt **HIGH** (die höchste mögliche Stufe) und wird als erstes
geprüft. Folge: Auf der Stufe **„hoch" ist der Gewinner nahezu immer der Wettercode — in Korsika
wie in den Alpen.** Ein Etikett „hoch · Wettercode" auf beiden Seiten des Ortsvergleichs zeigt
gerade **nicht**, dass verschiedene Größen dahinterstehen; es unterschlägt, dass in den Alpen
zusätzlich LPI/CAPE mitreden und auf Korsika nicht. Erst bei „leicht/mittel" trennen sich
Blitzdichte (FR) und Blitzpotenzial (Alpen).

⇒ ~~Nur (ii)/(iii) beantworten die im Issue genannte Vergleichbarkeitsfrage.~~ **Widerlegt, s.o.**

</details>

Für die Spec-Phase bleibt offen, ob „Herkunft" heißt: **(i)** die eine auslösende Zutat,
**(ii)** alle Zutaten, die diese Stufe tragen, oder **(iii)** der Korb der überhaupt am Ort
verfügbaren Signale.

---

## Vorhandene Muster, an denen sich das anlehnen kann

| Muster | Wo | Taugt als Vorbild für |
|---|---|---|
| **Hagel-Suffix** `f"{label} · {note}"` | `email/compare_html.py:219`, `email/helpers.py:753-754`, `:1746-1751` | **Direktester Präzedenzfall** — additiver Zusatz an der Stufe, Platz im Ortsvergleich bereits erwiesen |
| **Label-Katalog + `source_label()`** | `alert/official_alerts.py:91-113` (`_SOURCE_LABELS`), `services/radar_service.py:214-224` | Signalname → deutsches Label, Exakt-Treffer vor Heuristik, nie ein erfundener Wert |
| **Mehrere Quellen bei Bündelung** | `alert/render.py:185` `· Quelle: {_distinct_source_labels(msg)}` | Fall (ii): mehrere beitragende Signale in einer Zeile |
| **`fallback_model`/`fallback_reason`** | `app/models.py:90-95`, gesetzt `thunder_enrichment.py:350-359` | Merge-Schutz-Idee — aber **falsche Granularität** (je Reihe, nicht je Stunde) |
| **`_SIGNAL_ZU_FELD`** | `thunder_enrichment.py:36` | Signalname↔Feld existiert bereits upstream |

⚠️ **Nicht verwechseln:** ADR-0034 („Herkunfts-Fußzeile zeigt reale Datenquelle") behandelt eine
**andere** Dimension — welcher *Provider/Modell* die Daten lieferte (`build_origin_footer(source=)`).
#1680 fragt nach dem *auslösenden Signal innerhalb der Fusion*. Beide heißen „Herkunft".

---

## Ausgabeorte — neun, mit sehr ungleichem Platz

`docs/features/gewitter-gesamtkonzept.md:684-703` · generische Matrix `docs/reference/metric_output_matrix.md`

| # | Ort | Renderer | Platz für Zusatz |
|---|---|---|---|
| 1 | E-Mail-Pill | `email/helpers.py:1713-1757` | ✅ (Hagel-Suffix vorhanden) |
| 2 | Trip-Stundentabelle | `email/helpers.py:732-757`, Tagesaggregat `:188-191` | ✅ |
| 3 | Nachtblock | `email/helpers.py:996-1011` | eng |
| 4 | Kurzzusammenfassung | `compact_summary.py:567-600` | eng |
| 5 | SMS-Token | `sms_trip.py:114,185,415` → `tokens/metrics.py:29,42` | ❌ Token `TH:M@14`, 153 Zeichen |
| 6 | Telegram-Kurzübersicht | `narrow.py:189-211, 264-283, 528-550` | begrenzt (8 Spalten) |
| 7 | GEWITTER-Kommando/Drilldown | `services/trip_command_processor.py:135-142, 166-180, 872-881` | ✅ |
| 8 | **Ortsvergleich** | `email/compare_html.py:204, 294-302, 670-720, 937-940`; Klartext/Telegram/SMS `renderers/comparison.py:73, 327, 503-515` | ✅ HTML-Zelle; ⚠️ SMS s.u. |
| 9 | Mehrtages-Ausblick | `email/outlook.py:43, 195-247, 359-390` | ✅ |

**Platzbudget** `src/output/renderers/channel_layout.py:45-56`: E-Mail unbegrenzt · Telegram 8
Spalten/4096 Zeichen · **SMS und Premium-SMS 0 Spalten / 153 Zeichen** (Trip-SMS zusätzlich hart
`trip_report.py:446` `max_length=160`). Frontend-Pendant `metricsEditor.ts` `CHANNEL_COL_BUDGET`.

⚠️ **GSM-7-Filter** `comparison.py:585-591` ersetzt `·` durch `-` — ein Mittelpunkt-Suffix
überlebt den SMS-Weg nicht unverändert.

🔴 **KORREKTUR (2026-08-11, in der Analyse nachgemessen):** Oben stand zunächst „Compare-SMS zeigt
Gewitter gar nicht" mit Verweis auf `comparison.py:487-495`. **Das ist falsch.** `_CHANNEL_METRICS`
dort ist nur eine **Rangliste**, keine Auswahl. `comparison.py:629` baut die SMS-Zelle über
`_sms_gsm7_safe(_fmt_overview_cell(fmt, value, loc_result))` — Gewitter **erscheint** in der
Compare-SMS, sobald der Nutzer die Metrik gewählt hat. Folge für #1680: Ein Suffix am
Gewitter-Label **leckt automatisch in die SMS**, wird dort per `·` → `-` entstellt und verdrängt
über den `+N`-Mechanismus (`_sms_location_part`) hintere Metriken. Die Spec muss den SMS-Weg
**ausdrücklich abwählen**, sonst entsteht stiller Informationsverlust.

### Fünf parallele Label-Vokabulare

Geteilt: `metric_format.py:236-241` `THUNDER_LABEL_DE` (kein/leicht/mittel/hoch) + Ampel `:246-255`.
Abweichend lokal: `email/helpers.py:857-887` `_THUNDER_MAP` (word/plain/sms/Farben) ·
`compare_html.py:165-170` (NONE → „—") · `outlook.py:195-204` (+ Hintergründe) ·
`trip_command_processor.py:135-142, 175-178` (Emoji, „mäßig" statt „mittel") ·
`tokens/metrics.py:42` (`-/L/M/H`). **Eine Herkunfts-Beschriftung an nur einer Stelle einzubauen
erzeugt garantiert Drift.**

---

## Datenmodell & Abhängigkeiten

- **Upstream:** `ThunderLevel` (`app/models.py:35-44`, `str`-Enum NONE/LOW/MED/HIGH), Ordnung in
  `app/thunder_scale.py:34-43`; Schwellen aus `app/model_registry.py:120-223`; Gebiet aus
  `thunder_routing.py`.
- **Downstream:** `dp.thunder_level` (Datenpunkt) → `thunder_level_max` (Segment,
  `weather_metrics.py:458`) → ~21 Nicht-Test-Dateien, u.a. `risk_engine.py`, `trip_alert.py`,
  `weather_change_detection.py`, `day_comparison.py:408`, alle Renderer.
- **Go-Grenze:** `internal/model/segment.go:15` `ThunderLevelMax ThunderLevel` — ein neues
  Segmentfeld überquert die Python→Go-DTO-Grenze, wenn das Frontend es sehen soll.
- **Frontend:** `frontend/src/lib/types.ts:77, 403, 431`. **Kein Frontend-Ort rendert heute eine
  Gewitter-Stufenbeschriftung** — nur Metrik-Auswahl/Layout. Frontend ist also optional im Scope.
- **Metrik-Katalog:** `src/app/metric_catalog.py:332-350` (`id="thunder"`, `col_label="Thdr"`,
  `sms_code="TH"`, `summary_fields={"max":"thunder_level_max"}`).

## Bestehende Specs & ADRs

Specs: `feat_1474_gewitter_befund_stufen.md` (Ursprung der Fusion) ·
`feat_1474c_blitzpotenzial_stufen.md` · `feat_1679_cin_paarung_cape_leiter.md` +
`feat_1679_lpi_schwellen_region_tabelle.md` (aktuellster Stand der Leitern) ·
`fix_1592_s1_cape_modellschwelle.md` · `feat_1585_cape_selectable_false.md` ·
`feat_1492_s2a_thunder_vertretung.md` · `feat_1531_s1_dwd_gewittergroessen.md`.

ADRs (alle „Akzeptiert"): **0007** Daten statt Empfehlungen · **0034** Herkunfts-Fußzeile
(*andere* Dimension, s.o.) · **0047** Gewitter-Vertretung · **0048** modellabhängige Schwellen,
unbekannte Herkunft = „keine Aussage" · **0050** Metrik-Kaskade = Verfeinerung · **0025** eine
Gewitter-Quelle für alle Briefing-Kanäle.

**Tests, die die Fusion berühren — 11 Dateien:** `tests/integration/test_cape_no_double_count.py`;
`tests/tdd/`: `test_cape_cin_pairing.py`, `test_cape_model_threshold.py`,
`test_cape_not_selectable.py`, `test_hail_flag_wmo_signal.py`,
`test_hail_no_advice_text_and_thunder_level_guard.py`, `test_lpi_threshold_region_table.py`,
`test_thunder_enrichment_fuses_level_shared_path.py`, `test_thunder_ladder_shared_across_signals.py`,
`test_thunder_level_from_signals_fusion.py`, `test_thunder_potential_level_classification.py`.

---

## Risiken & Vorbehalte

1. **Rückgabetyp-Änderung ist ein Breaking Change** — `thunder_level_from_signals()` liefert heute
   `Optional[ThunderLevel]`; alle 11 Testdateien und der eine Aufrufer hängen daran. Additive
   Variante (zweite Funktion / optionales Out-Parameter) prüfen, bevor die Signatur bricht.
2. **Zwei Verlustpunkte** (Fusion *und* Stundenmaximum) — wer nur einen löst, liefert im
   Ortsvergleich nichts. Prüfort muss der Wirkort sein: der Nachweis gehört an die **zugestellte**
   Compare-Mail, nicht an einen Unit-Test der Fusion.
3. **Fünf Label-Vokabulare** → Beschriftung zentral ableiten, nicht je Renderer erfinden.
4. **SMS/Premium-SMS haben kein Budget** (0 Spalten, 153 Zeichen) und Compare-SMS zeigt Gewitter
   gar nicht. Alle vier Kanäle sind gleichrangig — die Spec muss je Kanal **entscheiden**, nicht
   stillschweigend auslassen.
5. **Gleichstands-Reihenfolge** (Befund A) wird zur Produktaussage.
6. **EU_REST-LPI ist ausgewiesener Interim-Wert** — eine Stufe dort als „Blitzpotenzial" zu
   etikettieren behauptet mehr Belastbarkeit, als die Schwelle hat.
7. **E8 (Superzellen bleiben unsichtbare Zutat)** kollidiert dem Wortlaut nach mit dem
   Issue-Beispiel; praktisch moot, weil `sdi_2` nicht in der Fusion ist — aber die Spec darf das
   Beispiel nicht unbesehen übernehmen.
8. **ADR-0007** (Daten statt Empfehlungen): Ein Signalname ist Beschreibung, keine Bewertung —
   unkritisch, solange kein Ratschlag daraus wird.

---

## Analysis (Phase 2, 2026-08-11)

### Type
**Feature** (Label `enhancement`, Rang 4 aus #1419, Entscheidung E1 bereits getroffen).

### Der additive Weg kostet null Testanpassungen

`thunder_level_from_signals()` hat **genau einen** Produktiv-Aufrufer (`thunder_enrichment.py:135`,
verifiziert über `src/`, `api/`, `scripts/`, `tools/`). Die Signatur muss **nicht** brechen: den
`if`-Block `metric_format.py:401-432` in eine private Hilfe `_signal_levels(...) -> dict[str,
ThunderLevel]` herausziehen, die öffentliche Funktion bleibt zeichengleich
(`return max_thunder(werte.values())`), daneben eine zweite öffentliche Funktion mit Herkunft.

Zum Vergleich der **Breaking-Weg, gezählt:** 11 Testdateien, 40 Aufrufstellen, 143 `assert`-Zeilen,
davon ~27 direkt auf dem Rückgabewert; dazu drei Aufruf-Wrapper
(`test_thunder_level_from_signals_fusion.py:37`, `test_cape_cin_pairing.py:42`,
`test_lpi_threshold_region_table.py:45`), die alle brächen.

🔴 **Kein „verhält sich wie ein ThunderLevel"-Trick:** `ThunderLevel` ist ein `str`-Enum mit
Membern (`models.py:35-44`) — nicht unterklassifizierbar; ein NamedTuple bräche jedes `== MED`.

### Persistenz — kompatibel, aber mit zwei scharfen Kanten

`SegmentWeatherSummary` **wird** persistiert (`src/services/weather_snapshot.py:4, 76-83`; reale
Datei `data/users/default/weather_snapshots/gr221-mallorca_2026-02-23.json` enthält
`"thunder_level_max": "NONE"`), `ForecastDataPoint` ebenfalls (`:287-296`).

Eine **Migration ist nicht nötig**: Serialisierung generisch über `vars()` (`:232`, `:288`),
Deserialisierung des Summary filtert unbekannte Schlüssel (`:252-257`) — vorwärts- und
rückwärtskompatibel. Aber:

1. `_deserialize_timeseries` filtert **nicht** (`:311-319`, `ForecastDataPoint(ts=..., **kwargs)`)
   ⇒ Hinzufügen ist sicher, späteres **Entfernen** nicht.
2. `isinstance(value, Enum)` behandelt nur **skalare** Enums (`:239`, `:291`). Ein `set` oder eine
   Liste von Enums bricht `json.dumps` — und der Fehler wird **still geschluckt** (`:85`, `:113`,
   nur `logger.warning`, Snapshot verloren). 🔴 **Ein neues Feld MUSS `str` oder `list[str]` sein.**

`LocationResult` (`src/app/user.py:117`, mit `lat`/`lon` `:56-57` und `hourly_data` `:152`) steht
**nicht** in der Schema-Hook-Liste — der Compare-Weg löst den Daten-Backup-Hook nicht aus.

### Die drei Auslegungen im Vergleich

| | (i) Auslöser | (ii) Träger | (iii) Korb |
|---|---|---|---|
| Aussage | die eine Zutat, die gesetzt hat | **alle** Zutaten, die die Stufe erreichen | welche Signale am Ort überhaupt verfügbar sind |
| Beantwortet „worauf beruht die Stufe" (Issue-Wortlaut) | ✅ | ✅ | ❌ (nur die Datenlage) |
| Varianz | je Zelle | je Zelle | **konstant je Ort** (Gebiet+Modell) |
| Wettercode-Verdeckung (Befund B, Restrisiko) | 🔴 betroffen | ✅ umgangen | ✅ umgangen |
| Gleichstands-Reihenfolge (Befund A) | 🔴 wird Produktaussage | ✅ **entfällt** — es wird nicht gekürt | ✅ entfällt |
| Eingriff in die Fusion | ja | ja | **keiner** — ableitbar aus `thunder_routing.thunder_region_for()` + `model_registry.lpi_thresholds_jkg()`/`cape_ladder_thresholds_jkg()` + Feldpräsenz |
| Neues Modellfeld | ja (Punkt **und** Tag) | ja (Punkt **und** Tag) | nein |

### Technical Approach — Empfehlung

**(ii) Träger, zuerst im Ortsvergleich.** Begründung:

- Der Issue-Wortlaut verlangt „die Stufe trägt sichtbar, **worauf sie beruht**" — das ist (i)/(ii),
  nicht (iii). (iii) beantwortet die *Motivation* (Vergleichbarkeit), nicht die *gestellte Frage*,
  und wäre je Ort konstant, also in jeder Zelle Rauschen statt Information.
- (ii) **löst Befund A auf, statt ihn zu zementieren**: Wenn alle tragenden Zutaten genannt werden,
  muss keine Gewinner-Reihenfolge zur Produktaussage werden.
- (ii) umgeht das verbliebene Restrisiko aus Befund B (Wettercode verdeckt Mit-Evidenz bei 95/96/99)
  — dessen Häufigkeit ist mit Bordmitteln nicht messbar, also nicht kalkulierbar.
- Kosten gegenüber (i) praktisch null: derselbe Eingriff, nur `alle` statt `erster`.

**Renderweg = das Hagel-Muster**, nicht neu erfunden: `_fmt_thunder(v, hail=None)`
(`compare_html.py:204-219`) bekommt einen dritten optionalen Parameter, `_fmt_overview_cell`
(`comparison.py:503-515`) ist *die eine* Stelle für Klartext/Telegram/SMS. Beschriftung **genau
einmal** neben `THUNDER_LABEL_DE` (`metric_format.py:236-241`) als Signalname→Label-Katalog nach
dem Muster `official_alerts.py:91-113` (Exakt-Treffer vor Heuristik, nie ein erfundener Wert).

### Affected Files (Vorschlag S1 — Ortsvergleich)

| Datei | Änderung | Was |
|---|---|---|
| `src/output/metric_format.py` | MODIFY | `_signal_levels()` herausziehen, zweite öffentliche Funktion mit Trägern, Label-Katalog |
| `src/providers/thunder_enrichment.py` | MODIFY | Träger am Datenpunkt mitschreiben (`list[str]`) |
| `src/app/models.py` | MODIFY | Feld am Datenpunkt **und** am Tagesaggregat, beides `list[str]` |
| `src/services/weather_metrics.py` | MODIFY | Träger der Stunden, die das Tagesmaximum stellen (argmax statt max) |
| `src/output/renderers/email/compare_html.py` | MODIFY | Suffix an `_fmt_thunder` (Hagel-Muster) |
| `src/output/renderers/comparison.py` | MODIFY | `_fmt_overview_cell` + **SMS ausdrücklich abwählen** |
| Tests | CREATE | Wirkungstest an der **zugestellten** Compare-Mail, nicht am Unit der Fusion |

### Scope Assessment
- Dateien: 6 Quell- + Testdateien · geschätzt **~200–250 LoC** (Limit 250 je Workflow — **knapp**)
- Risiko: **MEDIUM** — additiv, keine Migration; Hauptrisiken sind der SMS-Leck-Pfad und die
  Persistenz-Kante `list[str]`
- Nicht in dieser Scheibe: Trip-Mail-Pill, Ausblick, GEWITTER-Kommando, Go-DTO, Frontend

### ✅ PO-Entscheidungen (2026-08-11, Ende Phase 2)

| Frage | **Entscheidung** |
|---|---|
| Auslegung | **(ii) Alle tragenden Signale.** Genannt wird jede Zutat, die die gezeigte Stufe erreicht — z. B. „hoch · CAPE, Blitzpotenzial". Damit wird **keine** Gewinner-Rangfolge zur Produktaussage (Befund A entfällt) und der Wettercode kann keine Mit-Evidenz verdecken (Restrisiko Befund B entfällt) |
| Kanäle | **E-Mail + Telegram ja · SMS und Premium-SMS bewusst OHNE Herkunft.** Die Stufe selbst bleibt dort unverändert sichtbar. Grund: 153 Zeichen, kein Spaltenbudget, GSM-7 entstellt `·` zu `-`, und der `+N`-Mechanismus verdrängte hintere Metriken. **Ausdrückliche Entscheidung, kein stilles Auslassen** — der SMS-Zweig muss aktiv abgewählt werden (`fmt is _fmt_thunder` in `comparison.py`), sonst leckt der Zusatz automatisch dorthin |
| Reihenfolge | **#1760 zuerst.** Dieser Workflow ist ab 2026-08-11 **geparkt** in Phase 3 (Spec noch nicht geschrieben) |

### 🅿️ Parkzustand — was beim Wiederaufnehmen gilt

- Branch `feat-1680-thunder-herkunft` (auf `origin/main` 37b690fa), enthält nur Doku.
- Nächster Schritt: `/30-write-spec` mit Auslegung (ii), Scheibe = **Ortsvergleich**, Kanäle
  E-Mail + Telegram.
- ⚠️ **Vor Wiederaufnahme prüfen, ob #1760 die Fusion verändert hat** — der Fix dort fasst
  `metric_format.py` bzw. `dwd.py`/`dwd_eu.py` an. Die Aussagen dieses Dokuments über
  `_gedaempft_durch_cin()` und die CAPE-Zutat können danach veraltet sein.
- ⚠️ Die Messwerte in Befund B (CAPE trägt 99,6 % der Alpen-HIGH-Fälle) sind **mit** dem defekten
  CIN-Pfad entstanden. Nach dem #1760-Fix fällt CAPE-HIGH von 3,88 % auf 1,44 % — die Verteilung
  der Träger verschiebt sich, die **Kernaussage** (Alpen → CAPE/LPI, Korsika → Blitzdichte) bleibt.
