# Context: #1719 Scheibe S4 — Legende der Kürzel im Bereich „Reihenfolge"

Erstellt: 2026-08-12 · Workflow: `feat-1719-s4-kuerzel-legende` · Track: Standard

## Request Summary

Der Editor soll die Kürzel auflösen, die in den zugestellten Ausgaben stehen — damit ein
Nutzer, der in einer SMS `N13` oder in einer Telegram-Tabelle `TF` liest, im Editor
nachschlagen kann, welche Größe das ist.

## 🔴 Die Issue-Beschreibung ist an zwei Punkten überholt (gemessen 2026-08-12)

Der Issue-Text sagt: *„Backend liefert heute keinen Klartext je Kürzel (`/api/metrics` hat
`sms_code`, aber kein Beschreibungsfeld — `api/routers/config.py:83-120`)."* Beides trifft
so nicht mehr zu:

1. **`/api/metrics` liefert Klartext** — `label` (= `label_de`), zusätzlich `col_label` und
   `sms_code` (`api/routers/config.py:85-97`).
2. **Eine Legende existiert bereits** — `WeatherV2Reihenfolge.svelte:97-113` zeigt seit
   #1453 (AC-7) drei Namensformen je Zeile: deutscher Name · `col_label` („Kurzform in der
   Mail-Stundentabelle") · `sms_code` („Kürzel in der SMS").

**Der eigentliche Defekt ist ein anderer und schwerer:** das als „Kürzel in der SMS"
beschriftete Badge zeigt bei 5 von 25 Größen ein Kürzel, das in der **Trip**-Kurzform
nie vorkommt — und die **Telegram**-Kürzelfamilie fehlt vollständig.

## Der gemessene Befund

`sms_code` ist laut Katalog-Kommentar (`api/routers/config.py:97`, Issue #914 Slice 1)
Teil der **Alarm**-Render-Stammdaten. Die Trip-Kurzform verwendet eine eigene Tabelle mit
Grammatik-Ausnahmen und Mehrfachkürzeln (`src/output/renderers/sms_trip.py:105-190`).

| metric_id | Editor-Badge („SMS …") | Trip-SMS sendet tatsächlich |
|---|---|---|
| `temperature` | `D` | `K` `D` |
| `temperature_night` | `TN` | **`N`** |
| `wind_chill` | `TF` | `FK` `FD` `WC` |
| `thunder` | `TH` | `TH` `TH+` |
| `fresh_snow` | `NS` | `NS24+` |

`temperature_night` ist der härteste Fall: das Badge nennt ein Kürzel (`TN`), das in
keiner Trip-SMS auftaucht, während das gesendete `N` im gesamten Editor nirgends erklärt
wird. Die übrigen 20 Größen stimmen.

Gerechnet mit `scratchpad/kuerzel_matrix.py` gegen `get_all_metrics()` +
`SMS_MULTI_SYMBOLS_BY_METRIC` / `SMS_SYMBOL_BY_METRIC` — nicht abgetippt.

## Vier Kürzel-Familien, nicht drei

| Ausgabeweg | Quelle im Code | `wind_chill` | im Editor sichtbar? |
|---|---|---|---|
| Mail-Stundentabelle (Trip + Vergleich) | `MetricDefinition.col_label` (`email/helpers.py:542`, `email/compare_html.py:498`) | `Feels` | ✅ |
| **Telegram-Kompaktform (nur Trip)** | `MetricDefinition.compact_label` (`narrow.py:70-148`) | `TF` | ❌ **fehlt** |
| **Trip-SMS / Premium-SMS** | `SMS_MULTI_SYMBOLS_BY_METRIC` → sonst `SMS_SYMBOL_BY_METRIC` (`sms_trip.py:116-190`) | `FK` `FD` `WC` | ❌ **falsch** (zeigt `sms_code`) |
| Vergleichs-SMS | `get_sms_code()` = `sms_code` (`comparison.py:625`) | `TF` | ✅ korrekt |
| Alarm-SMS | `sms_code` | `TF` | (kein eigener Ausweis) |

**Folge für den Zuschnitt:** dasselbe Badge ist im **Vergleichs**-Editor richtig und im
**Touren**-Editor falsch — die beiden Flächen senden aus verschiedenen Tabellen. Eine
kontextlose Korrektur würde den Vergleich kaputt machen.

## Related Files

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte:82-113` | Die Badge-Zeile. Einziger Ort, der die Kürzel rendert. Kennt `activeChannel` — der Kanal-Bezug wäre also verfügbar |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:170-173, 449-454` | Lädt `/api/sms-symbols` bereits und hält `smsSymbolsByMetric` (metric_id → Kürzel-Liste) — heute nur für die Gefahren-Legende genutzt |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:1080-1095` | Vorbild-Legende (Gefahren, #1318/#1332): Markup, Testid, Quellendisziplin |
| `api/routers/config.py:29-70` | `/api/sms-symbols` — `_symbols_for()` bildet exakt die Trip-SMS-Logik ab (MULTI hat Vorrang, `.rstrip(":")`) |
| `api/routers/config.py:72-120` | `/api/metrics` — liefert `label`/`col_label`/`sms_code`, **kein** `compact_label` |
| `src/app/metric_catalog.py:36-69` | Feldherkunft: `compact_label`, `col_label`, `sms_code` |
| `src/output/renderers/sms_trip.py:105-190` | Wahrheit der Trip-SMS-Kürzel inkl. Grammatik-Ausnahmen |
| `src/output/renderers/narrow.py:70-148` | Wahrheit der Telegram-Kompaktform (`compact_label`) |
| `src/output/renderers/comparison.py:605-625` | Wahrheit der Vergleichs-SMS (`get_sms_code`) |
| `src/output/renderers/compare_metric_catalog.py:300-312` | Reicht `col_label`/`sms_code` an die drei Vergleichs-Editoren durch |

## Vier Einbettungen des Bausteins (alle betroffen)

1. Touren-Editor — `WeatherMetricsTab.svelte:1191` (context `route`)
2. Vergleichs-Übersicht — `WeatherMetricsTab.svelte:1338` (context `vergleich`)
3. Vergleichs-Stundenverlauf — `CompareHourlyLayoutControls.svelte:221`
4. Vergleichs-Ausblick — `CompareOutlookLayoutControls.svelte:154`

## Existing Patterns

- **Legende aus Backend-Katalog, nie zweitgetippt** — die Gefahren-Legende (#1318 AC-9)
  zieht alle Kürzel aus `/api/sms-symbols`, ausdrücklich damit die Anzeige nicht von der
  versendeten SMS abweichen kann. Genau das Muster fehlt hier für Metriken.
- **Kein fünfter Vokabular-Ort** (`compare_metric_catalog.py:295-305`): zusätzliche
  Namensformen reisen aus dem Register mit, statt im Browser neu getippt zu werden.
- **Playwright-Tripel** aus S2/S3: `<name>.staging.setup.ts` + `.staging.spec.ts` +
  `playwright.<name>.staging.config.ts` (Vorbild: `metrik-grundauswahl-schneidet-kanal.*`).

## Existing Specs

- `docs/adr/` ADR-0050 — Kaskade Grundauswahl/Kanal (S1)
- `docs/specs/modules/fix_1453_namensformen.md` — AC-7, führte die heutigen Badges ein
- `docs/specs/modules/fix_1719_s3_aus_ist_ein_zustand.md` — S3, gleicher Baustein
- `docs/specs/modules/fix_1719_s2_kaskade_verfeinerung.md` — S2, Lesepfad-Schnitt

## Dependencies

- **Upstream:** `/api/metrics` und `/api/sms-symbols`; Katalog `metric_catalog.py`;
  Kürzel-Tabellen in `sms_trip.py` / `narrow.py` / `comparison.py`
- **Downstream:** vier Editor-Einbettungen; `weather_metric_name_forms_visible.test.ts`
  (#1453 AC-7) prüft die **Anwesenheit** von `label`/`col_label`/`sms_code` im AST aller
  vier Editoren — ein Ersetzen von `sms_code` bricht diesen Wächter

## 🔴 PO-Entscheid 2026-08-12 (mitten in der Analyse): kein eigenes Telegram-Kürzel

PO wörtlich: *„Warum gibt es ein extra Telegram Kürzel? Das will ich nicht!"*

Damit dreht sich der Zuschnitt: **erst die Kürzelsysteme zusammenführen, dann erklären.**
Eine Legende für drei Systeme zu bauen hieße, den Zustand zu dokumentieren, den wir
gerade abschaffen.

### Gemessener Ist-Stand (`scratchpad/tg_vs_sms.py`)

| Verhältnis Telegram (`compact_label`) ↔ Register (`sms_code`) | Anzahl |
|---|---|
| identisch | 11 |
| abweichend ohne fachlichen Grund | 11 |
| SMS sendet mehrere Token, Telegram genau eines | 3 |

Abweichend: Nacht-Tiefst `TN`/`N` · Gefühlte Nacht `TFN`/`FN` · Luftfeuchte `H`/`HU` ·
Regenwahrsch. `P%`/`PR` · Schneefallgrenze `SG`/`SL` · Bewölkung `C`/`CT` · Sicht `V`/`VS` ·
Sonnenstunden `☀`/`SU` · Luftdruck `P`/`HP` · Nullgradgrenze `0G`/`NL` · Neuschnee `NS`/`NS24+`

Luftdruck (`P`) und Regenwahrscheinlichkeit (`P%`) unterscheiden sich in Telegram um ein
Zeichen — im Register heißen sie `HP` und `PR`.

### Die Systeme sind schon heute in derselben Nachricht gemischt

`sms_trip.py:811` baut die Änderungs-Token der **SMS** über
`get_compact_label_for_field()` — also aus `compact_label`. Eine SMS enthält damit
Token aus beiden Systemen nebeneinander.

### Abgeleitete Regel (Spec-Vorschlag)

**Telegram übernimmt das Register-Kürzel — außer wo das Register-Kürzel eine
Tagesauswertung bezeichnet statt der Größe.**

- **12 Ersetzungen** (die 11 oben + Gewitter `⚡`→`TH`): das Register-Kürzel benennt dort
  die Größe, nicht ihre Auswertung. Reine Vereinheitlichung.
- **2 begründete Ausnahmen:** `temperature` (`T`, Register `D` = Tageshöchst, `K` =
  Tagestiefst) und `wind_chill` (`TF`, Register-Trio `FK`/`FD`/`WC`). Die Telegram-Tabelle
  zeigt je Zelle einen **Stundenwert** — ein Kürzel, das „Tageshöchst" bedeutet, wäre dort
  eine falsche Aussage. Diese beiden behalten ihr Größen-Kürzel.

### Wirkorte von `compact_label` (vollständig)

| Ort | Wirkung |
|---|---|
| `narrow.py:148` | Spaltenköpfe der Telegram-Stundentabelle |
| `narrow.py:119` | Detailzeile (laut #1741 ohne Aufrufstelle — toter Pfad) |
| `narrow.py:493, 748, 757` | Kurzübersicht + Nacht-Zeile |
| `sms_trip.py:811` via `metric_catalog.py:876` | Änderungs-Token der **SMS** |
| `metric_format.py:199` | Style-Schalter `style="compact_label"` |

Festgenagelt von 8 Testdateien (`test_issue_635_telegram_weather.py`,
`test_issue_1001_telegram_bubbles.py`, `test_metric_catalog.py`, `test_channel_metric_matrix.py` u.a.) —
alle müssen mitgezogen werden.

## Risks & Considerations

1. **Der bestehende Wächter prüft Anwesenheit, nicht Wahrheit.** `weather_metric_name_forms_visible.test.ts`
   war beim Bau von #1453 grün und hat den falschen Kürzel-Wert nie sehen können — der
   Test nimmt an, `sms_code` *sei* das SMS-Kürzel. Wird das Feld ausgetauscht, muss dieser
   Test mitgezogen werden, sonst blockiert er den Fix.
2. **Kontextabhängigkeit ist Pflicht, keine Kür.** Vergleich sendet `sms_code`, Trip sendet
   aus `SMS_*_BY_METRIC`. Eine globale Korrektur macht den Vergleich falsch.
3. **`compact_label` liegt nicht an `/api/metrics` an** — soll die Telegram-Familie
   erscheinen, braucht der Endpoint ein zusätzliches Feld (additiv, unkritisch), und
   `compare_metric_catalog.py` müsste es mitreisen lassen.
4. **Geteilter Baustein, S3-Vorgeschichte.** In genau dieser Datei hat S3 die Ziehgeste
   lautlos zerbrochen (neue Array-Referenz im Markup). Jede Änderung am Zeilen-Markup
   braucht den Klickpfad-Nachweis, nicht nur Unit-Tests.
5. **#1771: kein Playwright-Spec läuft in der CI-Ampel.** Der Klickpfad muss in diesem
   Workflow von Hand gefahren werden; er bewacht danach nichts automatisch.
6. **Premium-SMS** hat keinen eigenen Reiter (erbt SMS transitiv, ADR-0049) — die
   SMS-Kürzel gelten dort mit.
7. **Nicht-selektierbare Größen** (`cape` u.a., #1585) tauchen in alten Trip-Daten auf;
   die Legende darf daran nicht scheitern.
