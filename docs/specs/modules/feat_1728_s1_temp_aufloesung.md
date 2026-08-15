---
entity_id: feat_1728_s1_temp_aufloesung
type: module
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [metrics, sms, briefing, editor, aggregation]
---

<!-- Issue #1728 Scheibe 1 (Backend) — Tages-Tief/Tages-Hoch als eigene
     waehlbare Groessen, gemessen UND gefuehlt. Folge aus #1484/#1660A. -->

# Temperatur-Auflösung: Tages-Tief/Tages-Hoch als eigene wählbare Größen (Backend)

## Approval

- [x] Approved (PO „freigabe" 2026-08-15)

## Purpose

Die Katalog-Größen „Temperatur" und „Gefühlte Temperatur" tragen heute je zwei
SMS-Token (`K`/`D` bzw. `FK`/`FD`), deren Sichtbarkeit über eine gemeinsame,
kanalübergreifende Auswertungswahl (`MetricConfig.aggregations`) gesteuert
wird — ein Bedienkonzept, das nur an einer von vier tatsächlichen
Ausgabestellen (SMS-Gate) überhaupt wirkt und an den drei E-Mail-Pillen
unbewacht ins Leere läuft (`reference_pruefort_muss_dem_wirkort_entsprechen`).
PO-Entscheidung #1728 (2026-08-11): Tages-Tief und Tages-Hoch werden — nach
dem bereits etablierten Muster `temperature_night`/`wind_chill_night`
(#1484/#1660 A) — je eigene, einzeln wählbare Katalog-Größen. Die
Vollmail-Überblick-Pillen zeigen künftig unbedingt die Spanne und sind kein
Bedienelement mehr. Diese Scheibe liefert den Backend-Anteil; der Wegfall des
Bedienabschnitts „05 — Auswertungen" im Editor ist Scheibe 2, die Entfernung
von `MetricConfig.aggregations` aus Modell/Loader/API ist Scheibe 3.

## Source

Schicht: **Python-Core / Domain-Backend** (`src/app/`, `src/output/`). Weder
Frontend (`frontend/src/`, Scheibe 2) noch Go-API (`internal/`, nicht betroffen —
kein Pendant zu `MetricConfig.aggregations`).

- **File:** `src/app/metric_catalog.py` — **Identifier:** `_METRICS`,
  `SMS_MULTI_SYMBOLS_BY_METRIC`, `COMPACT_LABEL_EXCEPTIONS` (tragend)
- **File:** `src/app/loader.py` — **Identifier:** Ableitungsblöcke im Ladepfad
  (`:803-834` als Vorbild), Speicherfilter `:1324-1325`/`:1529-1530` (tragend)
- **File:** `src/output/renderers/trip_report.py` — **Identifier:** `_AGG_GATE_SYMBOLS`
  (`:415-437`, entfällt)
- **File:** `src/output/renderers/sms_trip.py` — **Identifier:** Token-Bindung
- **File:** `src/output/renderers/email/html.py` — **Identifier:** Pillen-Wirkort `:1446`
- **File:** `src/output/renderers/email/plain.py` — **Identifier:** Pillen-Wirkort `:204`
- **File:** `src/output/renderers/email/compact.py` — **Identifier:** Pillen-Wirkort `:174`
- **File:** `src/output/renderers/email/helpers.py` — **Identifier:**
  `_AGGREGATION_PILL_METRICS`, `_resolve_pill_aggregations`
- **File:** `src/output/renderers/channel_layout.py` — **Identifier:** `METRIC_PRIORITY` `:61-62`
- **File:** `src/output/renderers/compare_hourly_metric_ids.py` — **Identifier:**
  Stundenverlauf-Ausschluss
- **File:** `src/output/renderers/narrow.py` — **Identifier:** `_overview_line` (PRÜFEN,
  s. Known Limitations)

## Implementation Details

### 1. Vier neue Katalogeinträge (`src/app/metric_catalog.py`)

Direkt hinter `temperature_night` (heute Zeilen 139–150) zwei neue
`MetricDefinition`-Einträge, direkt hinter `wind_chill_night` (heute Zeilen
185–~206) zwei weitere — beide Paare **ohne** `summary_fields` (reine
Sichtbarkeits-Gates, exakt wie `temperature_night`, DEC-2) und **ohne**
`alert_metrics`/`risk_thresholds`/`cmp` (keine eigene Alarmfunktion, DEC-2):

| id | label_de | dp_field | sms_code | col_key | trip_default_rank |
|---|---|---|---|---|---|
| `temperature_day_low` | „Tages-Tiefsttemperatur (Gehzeit)" | `t2m_c` | `K` | `temp_day_low` | 8 |
| `temperature_day_high` | „Tages-Höchsttemperatur (Gehzeit)" | `t2m_c` | `TD` (s. DEC-8) | `temp_day_high` | 9 |
| `wind_chill_day_low` | „Gefühlte Tages-Tiefsttemperatur (Gehzeit)" | `wind_chill_c` | `FK` | `felt_day_low` | — |
| `wind_chill_day_high` | „Gefühlte Tages-Höchsttemperatur (Gehzeit)" | `wind_chill_c` | `FD` | `felt_day_high` | — |

`category="temperature"` für alle vier (Editor-Gruppierung neben Eltern,
Vorbild `test_api_metrics_exposes_felt_night_next_to_wind_chill`).
`default_aggregations=("min",)` bzw. `("max",)` — inert (kein
`summary_fields`), rein dokumentarisch wie beim Nacht-Vorbild.
`compact_label` NICHT manuell setzen: die Register-Ableitung
(`_kurzform_kuerzel`, `:738–767`) liest `SMS_MULTI_SYMBOLS_BY_METRIC` zuerst
und überschreibt jeden deklarierten Wert automatisch mit `K`/`D`/`FK`/`FD`
(exakt das Verhalten, das `temperature_night`s deklariertes `"TN"` zur
Laufzeit zu `"N"` macht — kein Sonderfall dieser Scheibe).

**🔴 Katalog-Kommentar-Pflicht:** Jeder der vier Einträge braucht einen
Kommentar, der ausdrücklich sagt: *„Gehzeit-Fensterung
(`_collect_hiking_window_dps()`), NICHT das Tagesfenster 04–19 von
`temperature_min`/`temperature_max` (Alarm-Vokabular,
`models.py:1123-1124`)."* Ohne diesen Satz wird die Begriffsfalle aus dem
Kontext-Dokument real — zwei fachlich verschiedene Dinge mit ähnlichem Namen,
in getrennten Namensräumen, ohne Fehler beim Ausführen.

### 2. DEC-1 — `temperature`/`wind_chill` bleiben bestehen

Stundentabelle und Telegram-Zelle lösen ihre Spalte ausschließlich über
`dc.metrics` → `get_metric(mc.metric_id).dp_field/col_key`
(`email/helpers.py:103-124`, `dp_to_row()`); `COMPACT_LABEL_EXCEPTIONS`
(`metric_catalog.py:723-735`) begründet die Telegram-Ausnahme für
`temperature`/`wind_chill` wörtlich mit dem Stundenwert. Die Elterngrößen
bleiben deshalb unverändert im Katalog, inklusive ihrer `summary_fields`
(`:100`, `:157`) als einziger Quelle eines Tageswerts (Kachel-Text,
Ampel-Färbung, Korridor-Alarme). **Kein Code-Change an den Einträgen
`temperature`/`wind_chill` selbst** außer der Kürzel-Umhängung (DEC-3).

### 3. DEC-2 — Die vier neuen Größen sind reine Sichtbarkeits-Gates

Kein `summary_fields` ⇒ `available_aggregations()` liefert für sie `[]`
(`:830-840`, liest ausschließlich `summary_fields`) ⇒ `GET /api/metrics`
zeigt `"aggregations": []` (`config.py:112-119`, unverändert generisch —
kein Code-Change im Router nötig, der Serializer iteriert bereits über
`get_all_metrics()`). Zuordnung Kennung → gelesenes Feld der Elterngröße:

| Kennung | liest (indirekt, über die SMS-Tagesaggregation) |
|---|---|
| `temperature_day_low` | `temperature.summary_fields["min"]` (`temp_min_c`) |
| `temperature_day_high` | `temperature.summary_fields["max"]` (`temp_max_c`) |
| `wind_chill_day_low` | `wind_chill.summary_fields["min"]` (`wind_chill_min_c`) |
| `wind_chill_day_high` | `wind_chill.summary_fields["max"]` (`wind_chill_max_c`) |

Der tatsächliche Zahlenwert kommt unverändert aus `sms_trip.py:254-271`
(Gehzeit-Aggregation `day_min`/`day_max`/`felt_min`/`felt_max`, gefüttert in
`DailyForecast` `:455-458`) — **keine Änderung** an dieser Stelle, nur die
**Sichtbarkeit** der vier Tages-Token wird jetzt über die vier neuen IDs
statt über `aggregations` gesteuert.

### 4. DEC-3 — `SMS_MULTI_SYMBOLS_BY_METRIC` umhängen (`:710-716`)

```
SMS_MULTI_SYMBOLS_BY_METRIC: dict[str, tuple[str, ...]] = {
    "temperature_day_low": ("K",),
    "temperature_day_high": ("D",),
    "temperature_night": ("N",),
    "wind_chill_day_low": ("FK",),
    "wind_chill_day_high": ("FD",),
    "wind_chill": ("WC",),
    "wind_chill_night": ("FN",),
    "thunder": ("TH:", "TH+:"),
}
```

`"temperature"` und `"wind_chill"` (bisherige Mehrfach-Einträge mit
`("K","D")` bzw. `("FK","FD","WC")`) verschwinden aus diesem Dict; `WC`
bleibt — als eigener, unveränderter Ein-Symbol-Eintrag — an `"wind_chill"`
(**E3, PO: „WC soll bleiben"**). Die Gate-Schleife in `trip_report.py:412`
(`for metric_id, syms in SMS_MULTI_SYMBOLS_BY_METRIC.items()`) braucht
**keine** Änderung — sie iteriert bereits generisch über das Dict und liest
`metric_id in active_metric_ids`; mit der neuen Zuordnung prüft sie jetzt
automatisch `temperature_day_low`/`temperature_day_high` statt
`temperature`, exakt das Muster, das `temperature_night`/`wind_chill_night`
schon heute durchlaufen.

### 5. DEC-4 — `_AGG_GATE_SYMBOLS` entfällt (`trip_report.py:415-437`)

Der komplette Block (`_AGG_GATE_SYMBOLS`-Dict + die daraus gebaute
`_disabled_sms_specs`-Erweiterung, `:427-437`) wird **ersatzlos entfernt**.
Zwei parallele Gating-Mechanismen (SMS_MULTI_SYMBOLS_BY_METRIC-Zugehörigkeit
**und** ein zusätzliches Auswertungs-Gate) wären der Fehler, den DEC-1 des
Kontext-Dokuments ausdrücklich vermeiden will. Die Menge `active_metric_ids`
(`:368`, aus `_dc_uncollapsed.get_metrics_for_channel("sms", report_type)`,
`:328-329`) muss die vier neuen IDs korrekt führen — das liefert die
Bestands-Ableitung in `loader.py` (DEC-6), zusammen mit dem bereits
bestehenden Kaskaden-Mechanismus (ADR-0050, AC-13 unten).

### 6. DEC-5 — Die drei Pillen-Wirkorte zeigen unbedingt die Spanne

`_AGGREGATION_PILL_METRICS` (`email/helpers.py:1408-1411`) bleibt bestehen
(weiterhin nur `"temperature"`/`"wind_chill"` — die Pille hängt an der
Elterngröße, DEC-1). `_pill_for_metric()` (`:1580-1601`) ruft für diese
beiden IDs künftig `_aggregation_pill_text(vals_ts, ["min", "max"], …)`
**direkt** auf, ohne den Umweg über `_resolve_pill_aggregations(metric_id,
chosen_aggregations)`. Der Parameter `chosen_aggregations` entfällt aus der
Signatur; `_resolve_pill_aggregations()` und `pill_aggregation_choices()`
werden ungenutzt und **gelöscht** (nicht nur deaktiviert — toter Code, der
eine gespeicherte Auswertungswahl liest, wäre ein Rückfallpfad, der die
PO-Vorgabe „kein Bedienelement" unterläuft, sobald ihn jemand versehentlich
wieder verdrahtet). Die drei Aufrufer bauen `_pill_aggregations` /
`metric_aggregations` nicht mehr:

- `email/html.py:1443-1447` — Block entfällt, Aufruf `:1448-1454` ohne
  `metric_aggregations=`.
- `email/plain.py:202-205` — Block entfällt, Aufruf `:206-212` ohne
  `metric_aggregations=`.
- `email/compact.py:172-175` — Block entfällt, Aufruf `:176-182` ohne
  `metric_aggregations=`.

`mc.aggregations` wird an diesen drei Stellen **nicht mehr gelesen** — exakt
die Vorgabe aus dem Auftrag. `avg` verschwindet damit als Konsument komplett
(der `elif "avg" in aggregations`-Zweig in `_aggregation_pill_text()`
`:1530-1531` wird mit festem `["min","max"]` nie mehr erreicht; er bleibt im
Code stehen, weil die Funktion mit anderen `aggregations`-Werten weiterhin
korrekt sein muss — kein toter Zweig, nur ein nie mehr erreichter Aufrufpfad
für diese zwei Metriken).

### 7. DEC-6 — Bestandsdaten-Ableitung im Loader (`src/app/loader.py`)

Vier neue Ableitungsblöcke, wörtlich nach dem Muster `:803-834`
(`derived=True`, `aggregations=[]`, `bucket="secondary"`, nur wenn ein
Eltern-Eintrag existiert, kein Rückschreiben — Filter `:1324-1325`/
`:1529-1530`), aber mit einer Erweiterung gegenüber dem reinen
`enabled`-Erbe von `temperature_night`: die **gespeicherte
Auswertungswahl der Elterngröße** entscheidet zusätzlich, welche der beiden
Tagesrichtungen an ist.

> `temperature_day_low.enabled = <ein "temperature"-Eintrag existiert UND
> ist enabled> AND "min" in <Vereinigung aller "temperature".aggregations>`
> `temperature_day_high.enabled` analog mit `"max"`. Für
> `wind_chill_day_low`/`wind_chill_day_high` dieselbe Regel auf
> `"wind_chill"`.

Konkret (Beispiel für `temperature_day_low`, `wind_chill`-Paar analog):

```python
_temp_entries = [mc for mc in metrics if mc.metric_id == "temperature"]
if _temp_entries and not any(mc.metric_id == "temperature_day_low" for mc in metrics):
    _agg = {a for mc in _temp_entries for a in mc.aggregations}
    metrics.append(MetricConfig(
        metric_id="temperature_day_low",
        enabled=any(mc.enabled for mc in _temp_entries) and "min" in _agg,
        aggregations=[], bucket="secondary", derived=True,
    ))
```

Daraus folgt exakt die im Auftrag geforderte Tabelle: gespeichertes
`["min"]` ⇒ nur `temperature_day_low` an; `["min","max"]` (Default,
`loader.py:790`, betrifft 16 von 17 Bestandstrips) ⇒ beide an;
`["min","max","avg"]` ⇒ beide an, `avg` fällt ersatzlos aus der Ableitung
(kein drittes Tagesglied existiert). Eine leere `metrics`-Liste bleibt leer
(Altbestand Fall A, Roundtrip-Invarianz — Snow-AC-10-Muster aus #1484).

### 8. DEC-7 — Vorbelegung neuer Trips

`build_default_display_config()` (`metric_catalog.py:891-910`) materialisiert
für **jeden** Katalogeintrag `enabled=m.default_enabled` — der Dataclass-
Default ist `True` und wird für keinen der vier neuen Einträge überschrieben.
Ein frisch angelegter Trip hat damit **automatisch** alle vier Größen aktiv,
ohne Codeänderung an dieser Funktion (E2, PO: „an").

Getrennt davon steuert `trip_default_rank` **nicht** diese Materialisierung,
sondern zwei andere Stellen: `DEFAULT_TRIP_METRIC_IDS`
(`trip_metric_ids.py:29-34`, Fallback-Liste für die E-Mail-Pillen bei
komplett leerem `dc.metrics`, Fall A) und `trip_default_enabled` in
`GET /api/metrics` (`config.py:91`, `m.trip_default_rank is not None` —
speist die Scheibe-2-Vorbelegungslogik im Anlege-Editor). Rang 1–7 sind an
sieben Bestandsgrößen vergeben (`:114,244,265,298,349,493,559`); `wind_chill`
selbst trägt **keinen** Rang. Für diese Scheibe:

- `temperature_day_low`: `trip_default_rank=8`, `temperature_day_high`:
  `trip_default_rank=9` — neue Rangstufen ANGEHÄNGT, keine Umnummerierung
  der bestehenden Sieben (kein unbeteiligtes Regressionsrisiko).
- `wind_chill_day_low`/`wind_chill_day_high`: **kein** Rang — folgt exakt
  der heutigen Lage von `wind_chill` (kein Rang trotz `default_enabled=True`).

**Effekt in dieser Scheibe:** `trip_default_enabled` wird für die beiden
gemessenen Größen `true`, für die beiden gefühlten `false` — reine
Katalog-/API-Wirkung; die eigentliche Anlege-Oberfläche, die dieses Feld
liest, ist Scheibe 2.

### 9. DEC-8 (neuer Fund) — `sms_code`-Kollision bei `temperature_day_high`

`sms_code` muss laut Registerkonvention (`metric_catalog.py:69`,
„kollisionsfrei") global eindeutig sein — durchgesetzt von
`tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes::
test_all_sms_codes_globally_unique` (`:507-513`, `len(codes) ==
len(set(codes))` über **alle** gesetzten `sms_code`-Werte in `_METRICS`).
Der naheliegende Wert `"D"` für `temperature_day_high` ist **bereits von
`temperature` selbst belegt** (`:113`, `sms_code="D"`, seit #914 — dieses
Feld ist für `temperature` funktional inert, weil `temperature` nicht in
`_SMS_SYMBOL_METRIC_IDS` steht und die Compact-Label-Ableitung wegen des
`SMS_MULTI_SYMBOLS_BY_METRIC`-Treffers ohnehin nicht bei ihm ankommt — die
Ratsche unterscheidet das aber nicht). Ohne Gegenmaßnahme bricht die
Ratsche bei jedem Testlauf, der die vier neuen Einträge einführt.
**Ersatzkürzel `"TD"`** (kollisionsfrei geprüft gegen alle heutigen 26
`sms_code`-Werte, s. Grep-Nachweis) — exakt dasselbe Muster wie
`temperature_night`s `"TN"` (dort war `"N"` durch `temperature_cold`
belegt, `:127`). `"K"`/`"FK"`/`"FD"` sind unbelegt und werden unverändert
übernommen. Der **gerenderte SMS-Token** bleibt in jedem Fall `"D"`
(kommt aus `SMS_MULTI_SYMBOLS_BY_METRIC`, nicht aus `sms_code`) — nur das
Register-Metadatenfeld weicht ab, exakt wie beim Nacht-Vorbild.

### 10. Sichtbarkeits-Ausschluss aus Stundentabelle und Spaltenlayout

Alle vier neuen IDs sind Sichtbarkeits-Gates ohne eigenen Stundenwert (DEC-2)
— ohne explizite Ausnahme würden sie sonst als (mit der Elterngröße
kollidierende) Tabellenspalte oder Detail-Zeile erscheinen, sobald sie
`enabled=True` sind (Dataclass-Default `bucket="primary"` bei neu angelegten
Trips, DEC-7). Drei Stellen, exakt das Muster der Nachtfenster-Skalare:

- `src/output/renderers/email/helpers.py:98-100` —
  `NO_HOURLY_COLUMN_METRIC_IDS` um alle vier neuen IDs erweitern.
- `src/output/renderers/channel_layout.py:94-95` — die Menge
  `_NIGHT_SCALAR_IDS` (Filter vor der `primary`/`secondary`-Sortierung)
  umbenennen/erweitern auf alle sechs Sichtbarkeits-Gate-IDs (zwei
  Nachtfenster-Skalare + vier neue Tages-Gates). **Kein** Eintrag in
  `METRIC_PRIORITY` (`:60-67`) — die Auto-Verteilungs-Heuristik sieht diese
  IDs dank des Filters gar nicht erst.
- `src/output/renderers/compare_hourly_metric_ids.py:59-61` (Menge) und
  `:66-80` (`HOURLY_EXCLUSION_REASON`, begründeter Text je ID) — Ausschluss
  aus dem Ortsvergleich-Stundenverlauf, analog der bestehenden Einträge für
  `temperature_night`/`wind_chill_night`.

### 11. Unverändert (geprüft, kein Code-Change)

- `src/output/tokens/builder.py:264-289,319-330` — der Symbol-keyed
  `by_sym`-Mechanismus (`K`/`D`/`FK`/`FD`/`N`/`FN`/`WC`) liest ausschließlich
  `MetricSpec.enabled` je Symbol, kennt keine Metrik-IDs. Unverändert.
- `src/output/renderers/sms_trip.py` — re-exportiert
  `SMS_MULTI_SYMBOLS_BY_METRIC` nur (`:22-24`); die Tagesaggregation
  `day_min`/`day_max`/`felt_min`/`felt_max` (`:254-271`) und das Befüllen
  von `DailyForecast` (`:455-460`) bleiben unverändert (DEC-2).
- `api/routers/config.py` — der Serializer iteriert generisch über
  `get_all_metrics()`; die vier neuen Einträge erscheinen automatisch mit
  `"aggregations": []`, kein Code-Change.
- `src/app/metric_catalog.py:922-974` (`WEATHER_TEMPLATES`) — referenziert
  weiterhin gültige Katalog-IDs (`"temperature"`, `"wind_chill"` als
  Kategorie-Repräsentanten); kein Aktualisierungsbedarf.
- `src/output/renderers/narrow.py:499-522,749-758` — nennt `temperature`/
  `wind_chill` literal, zeigt aber bereits heute unbedingt die Spanne
  (Telegram-Abendübersicht). **Zu verifizieren, nicht vorab zu ändern** —
  bleibt in der Implementierung ein PRÜFEN-Punkt.

## Estimated Scope

- **LoC produktiv:** ~165–200 (Budget 250) — Katalogeinträge ~60,
  `SMS_MULTI_SYMBOLS_BY_METRIC`-Umhängen ~8, `_AGG_GATE_SYMBOLS`-Entfernen
  ~-20, Loader-Ableitung ~45, Pillen-Vereinfachung (3 Aufrufer + Helper)
  ~-20/+15, drei Sichtbarkeits-Ausschluss-Stellen ~15
- **Files produktiv:** 9 (`metric_catalog.py`, `loader.py` tragend;
  `trip_report.py`, `email/{html,plain,compact,helpers}.py`,
  `channel_layout.py`, `compare_hourly_metric_ids.py`); `sms_trip.py`,
  `narrow.py`, `config.py`, `builder.py` nur geprüft, keine Änderung
  erwartet
- **Test-LoC:** realistisch **> 500** (16 ACs, zwei Ableitungsrichtungen für
  zwei Größenpaare, drei Pillen-Wirkorte, Kaskaden-AC, Zwei-Nutzer-Fall,
  Bestandsdatei-Roundtrip) — **`workflow.py set-field loc_limit_override
  500` wird vorab benötigt**, vor Blockade beim PO einzuholen
  (CLAUDE.md-Pflicht)
- **Effort:** high — SSoT-Katalog, Persistenz-Ableitung, vier Kanäle,
  eine bereits gemessene Registerkollision (DEC-8)
- **Risiko:** HIGH

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1484_night_temp_metric` | Spec | Ableitungs-Muster (Loader-Block, Roundtrip-Invarianz), Rang-Mechanismus |
| `fix_1660a_temp_trennung` | Spec | Zweites Vorbild (Nacht-Abspaltung gefühlt), Abgrenzung 1 (`WC` bleibt bei `wind_chill`, hier fortgeschrieben als E3) |
| `fix_1719_s2_kaskade_verfeinerung` | Spec | Kaskaden-Modell (ADR-0050), AC-12 als Vorlage für „abgeleitete Größe im Kanal-Schnitt" |
| `sms_daywindow_aggregation` | Spec | Bindend: `K`/`D` bleiben auf die Gehzeit gefenstert, nicht das Tagesfenster 04–19 |
| `night_temp_evening_only` | Spec | Abgrenzung „Nacht ≠ Tages-Tief" bleibt unberührt stehen |
| `trip_aggregation_selection` (#1357) | Spec | Quelle der heutigen Auswertungswahl, die diese Scheibe an den drei Pillen-Wirkorten abschafft (DEC-5) |
| Kanal-Kaskade #429/#434/#1575/#1719 | Feature | liefert `active_metric_ids` für die SMS-Kette (`get_metrics_for_channel`) |
| `sms_format` | Spec | Token-Grammatik v2.x, unverändert |

## Bestandsdaten (PFLICHT-Regel aus CLAUDE.md)

Drei getrennte Bestandsfragen, alle **ohne Migrationslauf, ohne Replace**:

1. **Die vier neuen IDs fehlen im gespeicherten Config** (praktisch **alle**
   17 Bestandstrips) ⇒ Ableitung nach DEC-6 aus der Elterngröße —
   `["min","max"]`-Default ⇒ beide Tagesrichtungen an, unverändert gegenüber
   dem heutigen SMS-Verhalten (heute zeigt die SMS ohnehin immer `K`+`D` bzw.
   `FK`+`FD`, weil `_AGG_GATE_SYMBOLS` nur bei explizit **abweichender**
   Auswahl griff).
2. **`gr221-mallorca.json`** (einziger Bestandstrip mit abweichender
   Auswertung: `temperature: ["min","max","avg"]`, `wind_chill: ["min"]`) ⇒
   nach DEC-6: `temperature_day_low`+`temperature_day_high` beide an
   (`avg` beeinflusst die Ableitung nicht, fällt ersatzlos weg — **E1, PO:
   „ja"**), `wind_chill_day_low` an, `wind_chill_day_high` AUS. Der Trip
   verliert dadurch **kein** Tief/Hoch gegenüber dem heutigen SMS-Rendering.
3. **Trips ganz ohne `display_config`** brauchen keine Sonderbehandlung:
   `build_default_display_config[_for_profile]()` führt alle vier neuen
   Einträge über `default_enabled=True` bereits mit (DEC-7).

Erst ein bewusster Editor-Save (Scheibe 2) materialisiert einen expliziten
Eintrag für die vier neuen IDs — über den bestehenden Merge-Pfad, nie
Replace. Abgeleitete Einträge (`derived=True`) werden beim Speichern
herausgefiltert (`loader.py:1324-1325`/`:1529-1530`, generischer Filter,
keine Änderung nötig).

## Abgrenzungen (bewusst NICHT in dieser Scheibe)

1. **Der Bedienabschnitt „05 — Auswertungen" im Editor** — Scheibe 2. **Bis
   dahin entsteht eine sichtbare Zwischenlücke:** der Editor zeigt für
   „Temperatur"/„Gefühlte Temperatur" weiterhin die alte Auswertungswahl
   (Spanne/Tiefst/Höchst/Mittel), die nach dieser Scheibe **nirgends mehr
   wirkt** (`mc.aggregations` wird an keinem Wirkort mehr gelesen, DEC-5).
   Das ist eine bewusst in Kauf genommene Übergangslücke, kein Fehler dieser
   Scheibe.
2. **Entfernen von `MetricConfig.aggregations` aus Modell/Loader/
   `GET /api/metrics`** — Scheibe 3. Das Feld bleibt bestehen, wird aber ab
   dieser Scheibe an keinem Trip-Wirkort mehr gelesen.
3. **Zusammenführung von Ortsvergleich-Katalog und 3-Tages-Ausblick auf
   dieselben Kennungen** (E4). Der PO hat die Richtung entschieden — „das
   Fundament sind die eigenen Katalog-Kennungen, nicht die Paare" — die
   Umsetzung ist Arbeit an fremden Flächen (`compare_metric_catalog.py:
   101-136`, `compare_outlook_metric_ids.py:105-141`, Nachbildung der
   Kaskade `:78-102`) und sprengt das Budget dieser Scheibe. Wird als
   eigenes Issue mit Rückverweis auf #1728 angelegt, nicht in dieser Spec
   vergraben.
4. **Go (`internal/`)** — kein Pendant zu `MetricConfig.aggregations`;
   `trip_default_enabled`/`default_enabled` sind bereits generisch aus der
   API gelesene Booleans, keine Go-Änderung nötig.
5. **Alarm-Pfad, Stundentabelle (jenseits des Ausschlusses aus Punkt 10),
   Nacht-Block, 3-Tages-Ausblick** bleiben unberührt.
6. **Keine neue Bedienfläche** in dieser Scheibe (Muster #1660 A).

## Expected Behavior

- **Input:** Vier neue An/Aus-Größen in der Temperatur-Kategorie des
  Katalogs — `temperature_day_low`, `temperature_day_high`,
  `wind_chill_day_low`, `wind_chill_day_high` — parallel zu `temperature`,
  `wind_chill`, `temperature_night`, `wind_chill_night`. Materialisiert wird
  die Auswahl erst mit Scheibe 2; in dieser Scheibe wirkt die Bestands-
  Ableitung (DEC-6) und ein direkt konstruiertes `MetricConfig` (Tests).
- **Output:** SMS/Premium-SMS zeigen `K`/`D`/`FK`/`FD` unabhängig
  voneinander, gesteuert über die vier neuen IDs statt über
  `MetricConfig.aggregations`; `WC` bleibt an `wind_chill` gebunden. Die
  drei E-Mail-Pillen für „Temperatur"/„Gefühlte Temperatur" zeigen unbedingt
  die Spanne, unabhängig vom Zustand der vier neuen IDs. Stundentabelle,
  Telegram-Zelle, Ortsvergleich-Stundenverlauf bleiben unverändert (Elternwert,
  DEC-1) und zeigen die vier neuen IDs nirgends als eigene Spalte.
- **Side effects:** keine neuen Datenabrufe — die Gehzeit-Aggregation
  (`sms_trip.py:254-271`) läuft unverändert für jedes Briefing.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit aktivierter „Temperatur", `temperature_day_low` AUS und `temperature_day_high` AN / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `D`, aber kein `K`-Token.
  - Test: `TripReportFormatter().format_email().sms_text` (nicht `build_metrics_summary_pills()` direkt), realistisches Forecast-Fixture, Assertion auf Token-Menge.

- **AC-2:** Given dieselbe Ausgangslage umgekehrt (`temperature_day_low` AN, `temperature_day_high` AUS) / When das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `K`, aber kein `D`-Token.
  - Test: wie AC-1, gegenläufige Konfiguration.

- **AC-3:** Given ein Trip mit aktivierter „Gefühlter Temperatur", `wind_chill_day_low` AN und `wind_chill_day_high` AUS / When das Briefing als SMS erzeugt wird / Then enthält die SMS `FK` und `WC`, aber kein `FD`-Token — die Abwahl von `wind_chill_day_high` lässt `WC` unverändert stehen.
  - Test: `format_email().sms_text`, Fixture mit unterschiedlichem Tiefst-/Höchstwert; das ist die WC-Gegenprobe (E3) in Abwahlrichtung „nur eine Tagesrichtung ab".

- **AC-4:** Given ein Trip mit **abgewählter** „Gefühlter Temperatur" (`wind_chill` selbst AUS) und `wind_chill_day_high` explizit AN gesetzt (Konstruktionsfall, wie er über die Ableitung nie entstünde, aber im Editor denkbar ist) / When das Briefing als SMS erzeugt wird / Then fehlen `FD` **und** `WC` beide — die Abwahl der Elterngröße entfernt `WC`, nicht die Abwahl der Tagesrichtung.
  - Test: `format_email().sms_text`, direkt konstruiertes `MetricConfig`; Gegenstück zu AC-3, misst denselben Fakt (E3) aus der anderen Richtung.

- **AC-5:** Given ein Trip mit aktivierter „Temperatur", `temperature_day_low` AUS / When die Abend-E-Mail (HTML) erzeugt wird / Then zeigt die Metriken-Überblick-Kachel für Temperatur dennoch die volle Min–Max-Spanne, nicht nur den Höchstwert.
  - Test: `TripReportFormatter().format_email().email_html`, Parsing der Kachel-Zeile; das ist der Wirkort-Nachweis für DEC-5 (nicht `build_metrics_summary_pills()` direkt aufrufen).

- **AC-6:** Given ein Trip mit aktivierter „Temperatur", `temperature_day_low` AUS / When die Abend-E-Mail als Klartext erzeugt wird / Then zeigt die Metriken-Überblick-Kachel für Temperatur dennoch die volle Min–Max-Spanne, nicht nur den Höchstwert.
  - Test: `TripReportFormatter().format_email().email_plain`, Parsing der Kachel-Zeile; zweiter der drei Wirkort-Nachweise für DEC-5 (nicht `build_metrics_summary_pills()` direkt aufrufen).

- **AC-7:** Given ein Trip mit aktivierter „Temperatur", `temperature_day_low` AUS / When die Abend-E-Mail in der Kompaktform erzeugt wird / Then zeigt die Metriken-Überblick-Kachel für Temperatur dennoch die volle Min–Max-Spanne, nicht nur den Höchstwert.
  - Test: `TripReportFormatter().format_email().email_compact`, Parsing der Kachel-Zeile; dritter der drei Wirkort-Nachweise für DEC-5 (nicht `build_metrics_summary_pills()` direkt aufrufen).

- **AC-8:** Given ein gespeicherter Bestands-Trip mit `temperature: {enabled: true, aggregations: ["min"]}` und **ohne** explizite Einträge für `temperature_day_low`/`temperature_day_high` / When der Trip geladen und das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `K`, aber kein `D` — die Bestands-Ableitung wirkt im Ladepfad (`loader.py`), nicht nur im Katalog-Default.
  - Test: Roundtrip mit echtem Bestands-JSON-Fixture (Format wie `data/users/<uid>/trips/*.json`), Rendering-Assertion.

- **AC-9:** Given ein gespeicherter Bestands-Trip mit `wind_chill: {enabled: true}` (impliziter Default `["min","max"]`) und ohne explizite Tagesrichtungs-Einträge / When der Trip geladen und das Briefing erzeugt wird / Then enthält die SMS `FK` **und** `FD` — der Default-Fall (16 von 17 Bestandstrips) verliert keine Tagesrichtung.
  - Test: wie AC-8, Default-Fall statt Einzelauswahl.

- **AC-10:** Given ein geladener Bestands-Trip ohne explizite Tagesrichtungs-Einträge / When der Trip ohne inhaltliche Änderung erneut gespeichert wird / Then enthält die gespeicherte Datei weiterhin **keine** expliziten Einträge für die vier neuen IDs, und alle übrigen `display_config`-Felder bleiben unverändert (Merge, kein Replace, kein Zurückschreiben abgeleiteter Einträge).
  - Test: Load → Save-Roundtrip gegen ein Fixture-Verzeichnis, Diff der gespeicherten JSON gegen das Original abzüglich absichtlicher Änderungen.

- **AC-11:** Given `data/users/default/trips/gr221-mallorca.json` (`temperature: ["min","max","avg"]`, `wind_chill: ["min"]`) / When der Trip geladen und das Abend-Briefing als SMS erzeugt wird / Then enthält die SMS `K` **und** `D` (der entfallende Mittelwert kostet keine Tagesrichtung) sowie `FK`, aber **nicht** `FD`.
  - Test: Rendering direkt gegen die reale Bestandsdatei (kein synthetisches Fixture), vollständige Token-Assertion für alle sechs Temperatur-Symbole (inkl. `N`/`FN`/`WC` unverändert).

- **AC-12:** Given zwei verschiedene Nutzer mit entgegengesetzter Auswahl (Nutzer A: nur `temperature_day_high` und `wind_chill_day_low`; Nutzer B: nur `temperature_day_low` und `wind_chill_day_high`) / When beide ihr Abend-Briefing erzeugen / Then wirkt jeweils nur die eigene Auswahl — keine Vermischung über `user_id`-Grenzen.
  - Test: zwei User-Verzeichnisse unter `data/users/<uid>/`, zwei Renderings im selben Prozess, gegenläufige Assertions auf allen vier Token.

- **AC-13:** Given die globale Metrikliste enthält einen `"temperature"`-Eintrag (`enabled: true, aggregations: ["min","max"]`), sodass der Loader `temperature_day_low`/`temperature_day_high` ableitet und an `self.metrics` anhängt, UND eine SMS-Kanal-Ebene führt **keinen** eigenen Eintrag für diese beiden neuen IDs / When `get_metrics_for_channel("sms", …)` läuft / Then bleiben `temperature_day_low`/`temperature_day_high` im SMS-Ergebnis erhalten — der Kaskaden-Schnitt (ADR-0050) erkennt die abgeleiteten Größen korrekt, kein stiller Ausfall bei kanal-konfigurierten Trips.
  - Test: Vorbild `fix_1719_s2_kaskade_verfeinerung.md` AC-12 (`test_kaskade_*`-Muster), Fixture mit befülltem `channel_layouts.sms` ohne die neuen IDs.

- **AC-14:** Given der Metrik-Katalog nach dieser Scheibe / When alle `sms_code`-Werte aus `_METRICS` gesammelt werden / Then sind sie weiterhin global eindeutig (`temperature_day_high` trägt `"TD"`, nicht `"D"`).
  - Test: bestehende Ratsche `tests/tdd/test_issue_917_alert_renderer.py::TestAC6CatalogSmsCodes::test_all_sms_codes_globally_unique` bleibt ohne Anpassung grün.

- **AC-15:** Given der Metrik-Katalog / When `GET /api/metrics` abgerufen wird / Then enthält die Antwort alle vier neuen IDs in der Kategorie „temperature" mit `"aggregations": []`, `temperature_day_low`/`temperature_day_high` mit `"trip_default_enabled": true`, `wind_chill_day_low`/`wind_chill_day_high` mit `"trip_default_enabled": false`.
  - Test: API-Test gegen den Router (FastAPI TestClient), Assertion auf alle vier IDs und die beiden Felder.

- **AC-16:** Given ein Trip mit aktivierten `temperature_day_low`/`temperature_day_high` / When `render_for_channel("email", dc, "evening")` läuft / Then erscheint keine der vier neuen IDs als `table_columns`- oder `detail_metrics`-Eintrag (weder `primary`- noch `secondary`-Bucket) — analog dem bestehenden Filter für die beiden Nachtfenster-Skalare.
  - Test: direkter Aufruf von `render_for_channel()` mit konstruiertem `UnifiedWeatherDisplayConfig`, Assertion auf Abwesenheit in beiden Listen (Vorbild `test_render_for_channel_never_places_felt_night_in_a_bucket`).

## Known Limitations

- **Sichtbare Zwischenlücke bis Scheibe 2** (Abgrenzung 1): der Editor zeigt
  für „Temperatur"/„Gefühlte Temperatur" weiterhin die alte Auswertungswahl,
  die nach dieser Scheibe nirgends mehr wirkt. Kein Fehler, bewusste
  Zwischenstufe.
- **`MetricConfig.aggregations` bleibt im Modell** (Scheibe 3) — inklusive
  seiner API-Exposition in `GET /api/metrics` für `temperature`/`wind_chill`
  selbst. Die vier neuen IDs zeigen dort korrekt `[]`.
- **`trip_default_rank` wirkt in dieser Scheibe nur auf Katalog/API**
  (`trip_default_enabled`, `DEFAULT_TRIP_METRIC_IDS`-Fallback für
  Alt-Trips ohne jede `display_config`) — die eigentliche
  Anlege-Vorbelegungs-Oberfläche ist Scheibe 2.
- **`narrow.py` bleibt ein PRÜFEN-Punkt** — die Telegram-Abendübersicht
  nennt `temperature`/`wind_chill` literal, zeigt aber bereits heute
  unbedingt die Spanne; ein Code-Change ist nicht vorab angenommen, sondern
  in der Implementierung zu bestätigen.
- **Ortsvergleich/3-Tages-Ausblick bleiben auf eigenem Vokabular**
  (`{metric_id, aggregation}`-Paare) — Zusammenführung ist E4, eigenes
  Issue, nicht Teil dieser Scheibe.
- **`compact_label` der vier neuen IDs ist ein reiner Platzhalter** in der
  Deklaration — der tatsächliche Wert entsteht zur Ladezeit über die
  Register-Ableitung (`_kurzform_kuerzel`) aus `SMS_MULTI_SYMBOLS_BY_METRIC`
  und weicht vom deklarierten Literal ab (exakt wie bei
  `temperature_night`/`wind_chill_night`).
- **Bestehende Ratschen über alle Katalog-IDs** (z. B. golden Listen in
  Editor-/Alarm-Mapping-Tests) können bei vier neuen Einträgen mitreagieren
  — regulärer Umfang dieser Scheibe, kein gesonderter Befund.

## Prüfhinweis für den Adversary

Leitfrage aus CLAUDE.md: **Ist die Zusicherung dort geprüft, wo sie WIRKT —
oder nur dort, wo der Code steht?** Vier Stellen mit erhöhtem Risiko für
einen grünen, aber wirkungslosen Test:

1. **AC-1/AC-2 (SMS-Gate).** Ein Test, der `SMS_MULTI_SYMBOLS_BY_METRIC`
   direkt inspiziert statt `format_email().sms_text` zu rendern, beweist
   nichts — genau der Fehler, den das Kontext-Dokument für die
   Pillen-Wirkorte beschreibt, kann sich hier am Gate wiederholen.
2. **AC-5/AC-6/AC-7 (Pillen-Wirkorte).** Jeder dieser drei ACs MUSS über
   `TripReportFormatter().format_email()` laufen, NIE über
   `build_metrics_summary_pills()` direkt (🔴-Regel des Auftrags). Ein Test,
   der die Helper-Funktion direkt aufruft, ist ein Spec-Fehler.
3. **AC-8/AC-9/AC-11 (Ableitung im Ladepfad).** Prüfen, dass die Ableitung
   in `loader.py` wirkt, nicht nur im Katalog-Default — ein Test, der
   `MetricConfig` von Hand mit den vier neuen IDs vorbelegt, umgeht genau
   die Stelle, die AC-8/AC-9/AC-11 beweisen sollen.
4. **AC-13 (Kaskade).** Ein Test ohne befülltes `channel_layouts.sms` im
   Fixture ist grün, egal ob die Ableitung mit der Kaskade zusammenspielt
   oder nicht — erst das befüllte Kanal-Layout trennt richtig von falsch
   (Vorbild-Fund aus `fix_1719_s2_kaskade_verfeinerung.md` AC-12).

**Mutations-Gegenproben (Pflicht, per String-Ersetzung mit externer
Sicherungskopie — nie `git checkout/stash/reset`):**

- `SMS_MULTI_SYMBOLS_BY_METRIC["wind_chill"]` zurück auf `("FK","FD","WC")`
  drehen (alte Form wiederherstellen) — welcher Test wird rot? (muss AC-1/
  AC-2/AC-3 treffen)
- Im Loader-Ableitungsblock `"min"` und `"max"` vertauschen (Tief bekommt
  die max-Prüfung) — fängt das ein Test, oder prüfen alle nur „ein Token
  weniger, egal welches"?
- `wind_chill_day_high` versehentlich `sms_code="D"` statt `"TD"` geben —
  muss AC-14 rot werden lassen.
- Den Pillen-Aufruf in `html.py`/`plain.py`/`compact.py` auf `["min"]` statt
  `["min","max"]` fest verdrahten (statt die Spanne) — muss AC-5/AC-6/AC-7
  rot werden lassen, nicht nur „ein Wert weniger" unbemerkt durchlassen.
- `channel_layout.py`s Sichtbarkeits-Ausschluss-Menge um die vier neuen IDs
  NICHT erweitern — entsteht eine Geisterspalte, die AC-16 fängt, oder
  bleibt sie unbemerkt?
- Im Kaskaden-Test (AC-13) das befüllte `channel_layouts.sms` durch ein
  leeres ersetzen — AC-13 muss dabei grün BLEIBEN aus einem anderen Grund
  (Fallback auf global), nicht zufällig durch denselben Pfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe folgt zwei bereits getroffenen
  Architektur-Entscheidungen — der Nachtgrößen-Abspaltung (#1484, #1660 A)
  und der Kanal-Kaskade (ADR-0050, #1719) — und überträgt deren Muster
  unverändert auf die Tages-Tief/Hoch-Achse. Sie schafft keine neue
  Entscheidungsfläche: die vier PO-Entscheide (E1–E4) sind bereits im
  Kontext-Dokument dokumentiert und in DEC-1 bis DEC-8 dieser Spec
  operationalisiert. E4 (gemeinsames Fundament Ortsvergleich/Ausblick) ist
  eine Richtungsentscheidung ohne Umsetzung in dieser Scheibe — kein
  eigenes ADR nötig, solange sie nicht umgesetzt wird.

## Changelog

- 2026-08-14: Initial spec created (Issue #1728 Scheibe 1)
