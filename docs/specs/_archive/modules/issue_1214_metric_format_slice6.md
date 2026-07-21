---
entity_id: issue_1214_metric_format_slice6
type: module
created: 2026-07-12
updated: 2026-07-12
status: draft
version: "1.0"
tags: [metric-format, cloud-scale, thunder-ordinal, konsolidierung, issue-1214]
---

# Metric-Format-Konsolidierung — Scheibe 6 (Wolken-Skala + Thunder-Ordinal, letzte Scheibe)

## Approval

- [ ] Approved

## Purpose

Issue #1214 Scheibe 6 schließt die Konsolidierung ab: (1) die drei lebenden Wolken-Emoji-Skalen (`email/helpers.py`, `compact_summary.py`, `weather_metrics.py`) werden auf eine kanonische `cloud_emoji()`-Funktion in `src/output/metric_format.py` vereinheitlicht (PO-Entscheidung 2026-07-12: die Mail-Skala ≤10/30/70/90 wird produktweite Wahrheit), (2) die tote Kopie `narrow.py::_cloud_emoji` wird gelöscht, (3) die sieben (nicht sechs — Korrektur, s. Implementation Details) lebenden Kopien der Thunder-Ordinal-Logik werden auf eine kanonische `thunder_ordinal()`/`max_thunder()`-Quelle dedupliziert, und (4) als Beifang bekommt der Katalog-Eintrag `sunshine` ein `decimals=1`, womit die in Scheibe 5 dokumentierte Ausnahme (`comparison.py`-Sonne-Zeile) migrierbar wird. Dies existiert, um die in Scheibe 1–5 begonnene Konsolidierung ohne weitere Duplikat-Skalen abzuschließen und eine seit Langem bestehende Skalen-Divergenz (Mail vs. Kompakt-Zusammenfassung) durch eine bewusste PO-Entscheidung aufzulösen, statt sie weiter stillschweigend bestehen zu lassen.

## Source

- **File:** `src/output/metric_format.py` (neue `cloud_emoji()`, `thunder_ordinal()`, `max_thunder()`), `src/output/renderers/email/helpers.py`, `src/output/renderers/compact_summary.py`, `src/services/weather_metrics.py`, `src/output/renderers/narrow.py`, `src/output/renderers/trip_report.py`, `src/services/day_comparison.py`, `src/app/metric_catalog.py`, `src/output/renderers/comparison.py`
- **Identifier:** `cloud_emoji()`, `thunder_ordinal()`, `max_thunder()` (neu in `metric_format.py`); `fmt_val()`, `_format_clouds()`, `_cloud_pct_emoji()`, `_thunder_severity()`, `render_comparison_text()`

**Schicht:** Python-Core/Domain-Backend (`src/output/`, `src/services/`, `src/app/`) — kein Frontend, keine Go-API betroffen.

## Estimated Scope

- **LoC:** `metric_format.py` ~50-60 LoC neu (zwei Funktionen + Skalen-/Ordnungs-Konstanten + Docstrings); je Konsumenten-Datei 2-15 LoC Diff (Delegation statt Hartcodierung); `narrow.py` ~-13 LoC (Löschung); `metric_catalog.py` +1 LoC (`decimals=1`); `comparison.py` ~5 LoC Diff. Test-Korpus: ~80-120 LoC neu/geändert (neue `cloud_emoji`/`thunder_ordinal`-Tests, 4 korrigierte Boundary-Assertions in `test_dead_code_scheibe1.py`, 3 neue Delta-Zonen-Assertions in `test_compact_summary.py`, AC-2-Anpassung in `test_metric_format_slice5_comparison.py`).
- **Files:** 9 Quelldateien + bis zu 5 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/metric_format.py` (`format_value`, `severity_for`, `label`) | module | Scheibe-1-3-Modul — bleibt strukturell erhalten, bekommt zwei additive Funktionen (`cloud_emoji`, `thunder_ordinal`/`max_thunder`); kein Eingriff in bestehende Funktionen |
| `src/app/models.py` (`ThunderLevel`) | model | str-Enum OHNE Ordnung (Zeile 33-37) — `thunder_ordinal` bildet die einzige kanonische Ordnungsquelle; NICHT zu `IntEnum` umbauen (persistierte str-Werte, Schema-Risiko) |
| `src/app/metric_catalog.py` (`MetricDefinition`, `sunshine`-Eintrag Zeile 352-365) | module | bekommt `decimals=1`; `format_value("sunshine", …)` hat heute verifiziert KEINEN Aufrufer (`grep` leer) — Änderung ist additiv ohne Kollateralschaden |
| `src/output/renderers/email/helpers.py` (`fmt_val` Zeile 558-571 Cloud-Zweig, Zeile 164 + 1091 Thunder-Ordinal) | module | Gate-Datei (#811) — Cloud-Zweig delegiert, KEINE sichtbare Änderung (Skala bereits identisch); zwei Thunder-Stellen delegieren |
| `src/output/renderers/compact_summary.py` (`_format_clouds` Zeile 150-165) | module | Gate-Datei (#811) — delegiert, GEWOLLTE sichtbare Änderung (PO-Entscheidung) |
| `src/services/weather_metrics.py` (`_cloud_pct_emoji` Zeile 111-123, Thunder-Ordering Zeile 617-618 + 1032-1039) | module | `_cloud_pct_emoji` delegiert (eigener None-Guard bleibt, s. Implementation Details); `_night_emoji`/`_dni_emoji` bleiben UNVERÄNDERT (eigene Konzepte) |
| `src/output/renderers/narrow.py` (`_cloud_emoji` Zeile 158-170 tot, `_thunder_severity` Zeile 173-175) | module | tote `_cloud_emoji` wird gelöscht (verifiziert: kein Aufrufer außer der eigenen Definition); `_thunder_severity` bleibt als Wrapper bestehen (2 lebende Aufrufer Zeile 193, 336) und delegiert intern |
| `src/output/renderers/trip_report.py` (Thunder-Ordering Zeile 359) | module | Gate-Datei (#811) — reine Ordinal-Dict-Ersetzung, kein Verhaltenswechsel |
| `src/services/day_comparison.py` (`_THUNDER_ORDINAL` Zeile 19, `_thunder_delta` Zeile 339-348) | module | str-gekeytes Dict (bewusst, um `ThunderLevel`-Import zur Laufzeit zu vermeiden — nur `TYPE_CHECKING`-Import Zeile 16) — bleibt strukturell, Ordinal-Quelle wechselt auf `thunder_ordinal` (Details s.u.) |
| `src/output/renderers/comparison.py` (Sonne-Zeile 95-102, Scheibe-5-Ausnahme) | module | migriert auf `format_value("sunshine", v, style="bare") + "h"`, sobald `decimals=1` gesetzt ist — Golden-Output beweisbar identisch |
| `src/output/renderers/sms_trip.py` (`_TH_VAL` Zeile 217, Bug #874) | module | **UNVERÄNDERT** — eigene SMS-Builder-Level-Kodierung (`NONE=0, MED=2, HIGH=3`), kein Abweichler desselben Konzepts; bekommt ggf. einen ergänzenden Klassifikations-Kommentar-Verweis auf `metric_format.thunder_ordinal`, falls beim Implementieren noch nicht vorhanden |
| `tests/unit/test_weather_metrics_ux.py::TestCloudEmojiFormatting` | test | Mail-Skala-Anker (Boundary 10/11/70/91) — MUSS ohne Anpassung grün bleiben, da Katalog-Skala == bisherige `helpers.py`-Skala |
| `tests/tdd/test_bug_874_th_plus_sms.py` | test | SMS-Kodierungs-Anker — MUSS ohne Anpassung grün bleiben |
| `tests/refactor/test_dead_code_scheibe1.py::TestCloudPctEmoji` | test | **MUSS angepasst werden** (Korrektur, s. Implementation Details) — testet aktuell die alte `weather_metrics.py`-Skala (20/40/70/90), vier von fünf Boundary-Werten ändern sich |
| `tests/integration/test_compact_summary.py` | test | bekommt neue Assertions für die Delta-Zonen-Beispiele (15%/35%/85%) |
| `tests/tdd/test_metric_format_slice5_comparison.py` | test | `test_overview_lines_use_format_value` (AC-2) zählt bislang 4 `format_value(`-Aufrufe in `render_comparison_text` — wird nach der Sonne-Zeilen-Migration auf 5 angepasst; Golden-String (AC-1) bleibt identisch |
| `.claude/hooks/renderer_mail_gate.py` | gate | Greift ECHT bei `helpers.py`, `compact_summary.py`, `trip_report.py`, `sms_trip.py` (alle vier in der Gate-Liste #811) — Matrix + `briefing_mail_validator.py`-Nachweis vor Commit (Implementierungsdetail, kein AC) |

## Implementation Details

### 1. Kanonische `cloud_emoji(pct: Optional[float]) -> str` in `metric_format.py`

Neue Funktion mit der PO-entschiedenen Mail-Skala als produktweiter Wahrheit:

| Bedingung | Emoji |
|---|---|
| `pct is None` | `"–"` (bestehendes `_NO_VALUE`-Sentinel des Moduls) |
| `pct <= 10` | ☀️ |
| `10 < pct <= 30` | 🌤️ |
| `30 < pct <= 70` | ⛅ |
| `70 < pct <= 90` | 🌥️ |
| `pct > 90` | ☁️ |

None-Handling-Entscheidung (Tech-Lead, da im Auftrag offen gelassen): `cloud_emoji(None)` liefert `_NO_VALUE` ("–"), konsistent mit `format_value`s bestehender None-Konvention im selben Modul. `weather_metrics._cloud_pct_emoji` hat einen davon abweichenden, historisch gewachsenen und getesteten None-Rückgabewert (`"?"`, s. AC-7) — dieser bleibt als **eigener Guard VOR der Delegation** bestehen (die Funktion prüft `if cloud_pct is None: return "?"` weiterhin selbst und ruft `cloud_emoji()` nur für den Nicht-None-Fall auf). Kein Widerspruch: `cloud_emoji` selbst entscheidet nur, was *sie* bei `None` liefert; Aufrufer mit abweichender Alt-Semantik behalten ihren eigenen Guard.

**Konsumenten:**

- **`email/helpers.py:558-571`** (`fmt_val`, Cloud-Zweig): `val` ist an dieser Stelle bereits garantiert nicht `None` (früher Return bei `val is None`, Zeile 486) und die Skala ist bereits identisch zur neuen kanonischen Skala (≤10/30/70/90) — reine Delegation `cloud_emoji(val)` statt der lokalen `if/elif`-Kette. **Keine sichtbare Änderung**, Boundary-Tests (`test_weather_metrics_ux.py::TestCloudEmojiFormatting`, inkl. 10/11/70/91) bleiben ohne Anpassung grün.

- **`compact_summary.py:150-165`** (`_format_clouds`, friendly-Zweig): delegiert an `cloud_emoji(pct)` statt der lokalen `<20/40/60/80`-Skala. **GEWOLLTE sichtbare Änderung.** Verifizierte Delta-Zonen (alle anderen Prozentbereiche liefern identisches Emoji vor/nach der Migration):

  | Prozentbereich | Alt (Kompakt, `<20/40/60/80`) | Neu (kanonisch, `≤10/30/70/90`) |
  |---|---|---|
  | 11–19 % | ☀️ | 🌤️ |
  | 31–39 % | 🌤️ | ⛅ |
  | 60–70 % | 🌥️ | ⛅ |
  | 80–90 % | ☁️ | 🌥️ |

  Konkrete Beispiele für die Spec-Freigabe: **15 %** → bisher ☀️, künftig 🌤️. **35 %** → bisher 🌤️, künftig ⛅. **85 %** → bisher ☁️, künftig 🌥️ (weniger dramatisch als vorher dargestellt, keine Verschlechterung). Alle Prozentwerte außerhalb der vier Delta-Zonen (0–10, 20–30, 40–59, 71–79, 91–100) liefern identisches Emoji vor/nach der Migration.

- **`weather_metrics.py:111-123`** (`_cloud_pct_emoji`, Fallback-Pfad wenn weder DNI noch WMO-Code vorliegen): behält den eigenen `if cloud_pct is None: return "?"`-Guard, delegiert den Nicht-None-Fall an `cloud_emoji(cloud_pct)` statt der lokalen `_CLOUD_*`-Konstanten (20/40/70/90 — **abweichend von der Kompakt-Skala**, eigene dritte Variante). Verifizierte Delta-Zonen dieser Skala gegen die neue kanonische Skala: **11–19 %, 31–39 %, exakt 70 %, exakt 90 %** (bei 70/90 kippt `<`-vs-`<=` an den Katalog-Grenzwerten). `_night_emoji` (Zeile 89-95, Schwellen 40/80) und `_dni_emoji` (Zeile 98-108, DNI-basiert) bleiben **UNVERÄNDERT** — eigene Konzepte, nicht Teil der Wolken-Prozent-Skala.

### 2. Löschung `narrow.py:158-170::_cloud_emoji`

Verifiziert (`grep -rn "_cloud_emoji\b" src/ tests/`): einziger Treffer ist die eigene `def`-Zeile. Kein Aufrufer, keine Testabdeckung. Ersatzlose Löschung.

### 3. Kanonische Thunder-Ordnung — **7 Stellen, nicht 6 (Korrektur ggü. Analyse)**

`ThunderLevel` ist ein `str`-Enum ohne Ordnung (`app/models.py:33-37`) — nacktes `max(values)` wäre alphabetisch falsch (`"NONE" > "MED" > "HIGH"`). Neue Funktionen in `metric_format.py`:

```
_THUNDER_ORDER = {ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}

def thunder_ordinal(level: Optional[ThunderLevel]) -> int:
    ...  # None -> 0, unbekannt -> 0, sonst Ordinal

def max_thunder(levels) -> ThunderLevel:
    return max(levels, key=thunder_ordinal)
```

Da `ThunderLevel(str, Enum)` ist, hashen/vergleichen Enum-Member identisch zu ihrem reinen String-Wert (`ThunderLevel.MED == "MED"`, `hash(ThunderLevel.MED) == hash("MED")`) — `thunder_ordinal`/das interne Dict funktionieren also transparent sowohl mit `ThunderLevel`-Instanzen als auch mit rohen `"NONE"/"MED"/"HIGH"`-Strings. Das macht die Konsolidierung von `day_comparison.py` (str-gekeytes Dict, s.u.) ohne Normalisierungs-Umweg möglich.

Alle 7 Stellen, Ersetzung des lokalen Dict-Literals `{ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2}` bzw. seiner Verwendung durch `thunder_ordinal`/`max_thunder`, reine Deduplizierung ohne Verhaltensänderung:

| # | Stelle | Bisheriges Muster | Ersetzung |
|---|---|---|---|
| 1 | `trip_report.py:359` | lokales Dict + `max(values, key=lambda v: severity.get(v,0))` | `max_thunder(values)` |
| 2 | `narrow.py:173-175` (`_thunder_severity`) | lokales Dict + `.get(level,0) if level is not None else 0` | Funktionskörper delegiert: `return thunder_ordinal(level)`; Wrapper selbst bleibt (2 lebende Aufrufer Zeile 193, 336) |
| 3 | `email/helpers.py:164` | lokales Dict + `max(values, key=lambda v: severity.get(v,0))` | `max_thunder(values)` |
| 4 | `email/helpers.py:1091` | lokales Dict, genutzt Zeile 1260 + 1262 (`severity.get(lvl,0)`) | **Korrektur:** Kontext-Dokument vermutete toten Local (F841-Verdacht) — verifiziert FALSCH: aktiv genutzt in `_pill_for_metric`s `thunder`-Zweig (Zeile 1252-1270, Ereignis-Pill „Gewitter ab HH:00"). Wird migriert, nicht gelöscht: `severity.get(lvl,0)` → `thunder_ordinal(lvl)` an beiden Stellen |
| 5 | `weather_metrics.py:617-618` | lokales Dict + `max(levels, key=lambda x: ordering[x])` | `max_thunder(levels)` |
| 6 | `weather_metrics.py:1032-1039` | kombiniertes Dict `_ENUM_ORDER` für **ThunderLevel UND PrecipType** in einer generischen `max`-Aggregation (`agg_rule == "max"` über beliebige Enum-Felder) | **Sonderfall:** kann NICHT 1:1 durch `max_thunder` ersetzt werden, da `values` je nach `field_name` entweder `ThunderLevel`- oder `PrecipType`-Werte enthält. Ersetzung: `_ENUM_ORDER = {**{lvl: thunder_ordinal(lvl) for lvl in ThunderLevel}, PrecipType.RAIN: 0, PrecipType.SNOW: 1, PrecipType.MIXED: 2}` — nur der ThunderLevel-Anteil wird kanonisch bezogen, der `PrecipType`-Anteil (kein Teil dieser Scheibe) bleibt lokal unverändert |
| 7 | `day_comparison.py:19` (`_THUNDER_ORDINAL`, str-gekeytes Dict) + `:345-346` (`_thunder_delta`) | eigenes Dict `{"NONE":0,"MED":1,"HIGH":2}`, bewusst str-gekeyt um den Laufzeit-Import von `ThunderLevel` zu vermeiden (nur `TYPE_CHECKING`-Import Zeile 16, Zirkularitäts-Vermeidung) | `_THUNDER_ORDINAL`-Dict entfällt, `_thunder_delta` importiert `thunder_ordinal` aus `metric_format` (kein Zirkularitäts-Risiko: `metric_format.py` importiert nur aus `app.metric_catalog`/`app.models`/`design_tokens`, nicht aus `services.day_comparison`) und ruft es mit dem bestehenden `.value if hasattr(...) else ...`-Ausdruck auf — funktioniert dank der str-Enum-Hash-Äquivalenz unverändert, defensive Normalisierung bleibt unangetastet (kein Scope-Kriechen) |

`helpers.py:1091`s ursprünglicher Analyse-Verdacht „toter Local" ist damit widerlegt und durch die Implementierung zu korrigieren (Live-Verifikation: `awk` über den vollen Funktionskörper zeigt zwei echte Nutzungsstellen).

### 4. Beifang: `sunshine.decimals=1` + Sonne-Zeilen-Migration

`src/app/metric_catalog.py:352-365`, `sunshine`-`MetricDefinition` bekommt `decimals=1` (aktuell nicht gesetzt, Default 0). Verifiziert: `format_value("sunshine", …)` hat aktuell keinen Aufrufer (`grep` leer) — additiv, keine Kollateralwirkung auf `email/helpers.py:579` (eigenes `.1f`) oder `compare_html` (lokales `decimals=1`), die beide unverändert bleiben.

`src/output/renderers/comparison.py:95-102` (Scheibe-5-Ausnahme, Adversary-F001): `lines.append(f"   Sonne: {sunny_h}h" ...)` → `lines.append(f"   Sonne: {format_value('sunshine', sunny_h, style='bare')}h" ...)`. Identitätsbeweis (bereits in Scheibe-5-Spec dokumentiert): `calculate_sunny_hours()` liefert immer `round(x,1)` als float, also `str(4.7) == "4.7" == f"{4.7:.1f}"` — Output zeichen-identisch. `tests/tdd/test_metric_format_slice5_comparison.py::test_overview_lines_use_format_value` (AC-2) zählt aktuell 4 `format_value(`-Aufrufe in `render_comparison_text`; wird auf 5 angepasst (der Golden-String aus AC-1 bleibt unverändert, da der Output identisch ist).

## Expected Behavior

- **Input:** Wolken-Prozentwerte (0-100, inkl. `None`) an allen drei migrierten Konsumenten; Listen von `ThunderLevel`-Werten an allen sieben migrierten Ordinal-Stellen; `sunny_hours`-Float-Werte in `comparison.py`.
- **Output:** `email/helpers.py`-Mail-Tabellen liefern zeichen-identische Wolken-Emojis wie vor der Migration. `compact_summary.py` liefert an den vier Delta-Zonen (11-19/31-39/60-70/80-90 %) NEUE Emojis (PO-gewollt), sonst identisch. `weather_metrics.py::_cloud_pct_emoji` liefert an den vier Delta-Punkten (11-19/31-39/70/90 %) neue Emojis (seltener DNI/WMO-loser Fallback), sonst identisch, `None` weiterhin `"?"`. Alle sieben Thunder-Ordinal-Stellen liefern für identische Eingaben identische Ausgaben (reine Deduplizierung). `narrow.py` verliert eine tote Funktion, kein Laufzeitunterschied. `comparison.py`s Sonne-Zeile liefert zeichen-identischen Output.
- **Side effects:** Keine — reine Formatierungs-/Sortierfunktionen ohne I/O, State oder Netzwerkzugriff.

## Acceptance Criteria

- **AC-1:** Given `cloud_emoji(pct)` in `metric_format.py` / When es für die Grenzwerte 10/11/30/31/70/71/90/91 sowie `None` aufgerufen wird / Then liefert es exakt ☀️/🌤️/🌤️/⛅/⛅/🌥️/🌥️/☁️ bzw. `"–"` für `None`.
  - Test: neue Tests in `tests/tdd/test_metric_format.py` (oder neue Datei `test_metric_format_slice6_cloud_scale.py`) prüfen alle acht Grenzwerte plus `None` explizit.

- **AC-2:** Given `email/helpers.py::fmt_val` (Cloud-Zweig) nach der Migration auf `cloud_emoji` / When die bestehenden Grenzwert-Tests (10/11/70/91) sowie die Basis-Fälle (5/25/50/85/95) erneut ausgeführt werden / Then bleiben alle Ergebnisse zeichen-identisch zum Stand vor dieser Scheibe.
  - Test: `tests/unit/test_weather_metrics_ux.py::TestCloudEmojiFormatting` läuft grün OHNE Anpassung der erwarteten Werte.

- **AC-3:** Given `compact_summary.py::_format_clouds` nach der Migration / When es mit 15 %, 35 % und 85 % (jeweils repräsentativ für die Delta-Zonen 11-19/31-39/80-90) aufgerufen wird / Then liefert es 🌤️ (statt bisher ☀️), ⛅ (statt bisher 🌤️) bzw. 🌥️ (statt bisher ☁️); Werte außerhalb der vier Delta-Zonen (z.B. 5 %, 25 %, 50 %, 95 %) bleiben unverändert.
  - Test: neue Assertions in `tests/integration/test_compact_summary.py` für die drei Delta-Fälle plus mindestens einen unveränderten Kontrollfall.

- **AC-4:** Given die sieben Thunder-Ordinal-Stellen (`trip_report.py:359`, `narrow.py:173-175`, `helpers.py:164`, `helpers.py:1091`, `weather_metrics.py:617-618`, `weather_metrics.py:1032-1039`, `day_comparison.py:19+345-346`) / When der Quellcode nach lokalen `{ThunderLevel.NONE: 0, ...}`-Dict-Literalen durchsucht wird / Then existiert außerhalb von `metric_format.py` kein solches Literal mehr (mit Ausnahme des dokumentiert hybriden `_ENUM_ORDER` in `weather_metrics.py:1032-1039`, dessen ThunderLevel-Anteil aus `thunder_ordinal` bezogen wird); Aggregationsverhalten ist identisch (`max(NONE,MED,HIGH) == HIGH` etc.) und die SMS-Kodierung (`sms_trip.py:217`, `_TH_VAL {0,2,3}`) bleibt unverändert.
  - Test: `grep -rn "ThunderLevel.NONE: 0, ThunderLevel.MED: 1, ThunderLevel.HIGH: 2" src/` liefert außer in `metric_format.py` keine Treffer mehr; `tests/tdd/test_bug_874_th_plus_sms.py` läuft grün OHNE Anpassung; bestehende Thunder-Aggregations-Tests (u.a. in `test_day_comparison_integration.py`, Tests rund um `trip_report.py`/`narrow.py`-Tagesaggregation) laufen grün ohne Anpassung der erwarteten Werte.

- **AC-5:** Given `narrow.py` nach dieser Scheibe / When die Datei nach `_cloud_emoji` durchsucht wird / Then existiert die Funktion nicht mehr, und `grep -rn "_cloud_emoji\b" src/ tests/` liefert keinen Treffer.
  - Test: statischer Grep-Check + vollständiger Lauf der `narrow.py`-Testsuite ohne Regression.

- **AC-6:** Given `metric_catalog.py`s `sunshine`-Eintrag mit `decimals=1` / When `comparison.py::render_comparison_text` (Sonne-Zeile) vor und nach der Migration auf `format_value("sunshine", …, style="bare")` mit identischem `ComparisonResult`-Input aufgerufen wird / Then ist der zurückgegebene String zeichen-identisch (Golden-Vergleich), inklusive Werten mit Nachkommastelle (z.B. `sunny_hours=4.7` → `"Sonne: 4.7h"`).
  - Test: `tests/tdd/test_metric_format_slice5_comparison.py::test_comparison_text_matches_golden` bleibt grün (Golden-String unverändert), `test_overview_lines_use_format_value` wird auf 5 erwartete `format_value(`-Aufrufe angepasst.

- **AC-7:** Given `_night_emoji` und `_dni_emoji` (`weather_metrics.py:89-108`) sowie `weather_metrics.py::_cloud_pct_emoji`s pre-existierender Boundary-Test-Korpus / When diese Scheibe abgeschlossen ist / Then bleiben `_night_emoji`/`_dni_emoji` unverändert (kein Diff), UND `tests/refactor/test_dead_code_scheibe1.py::TestCloudPctEmoji` wird korrigiert (nicht unverändert gelassen — Korrektur ggü. ursprünglicher Analyse-Annahme): `test_clear` (Wert 19), `test_mostly_clear` (Wert 39), `test_mostly_cloudy` (Wert 70), `test_overcast` (Wert 90) ändern ihr erwartetes Emoji gemäß der neuen kanonischen Skala; `test_none` (`_cloud_pct_emoji(None) == "?"`) bleibt unverändert grün.
  - Test: `git diff` zeigt keine Änderung an `_night_emoji`/`_dni_emoji`; `tests/refactor/test_dead_code_scheibe1.py::TestCloudPctEmoji` läuft grün mit den vier angepassten und einer unveränderten Assertion; `tests/tdd/test_weather_emoji_dni.py` (Integrationstest über `get_weather_emoji`, dessen bisherige Fallback-Werte 55/60/80/95 verifiziert außerhalb aller Delta-Zonen liegen) läuft grün OHNE Anpassung.

## Known Limitations

- `_night_emoji` (`<40/<80`, Nacht-Mond-Emoji) und `_dni_emoji` (Direct-Normal-Irradiance-basiert) sind eigene Konzepte, ausdrücklich NICHT Teil der Wolken-Prozent-Skala — bleiben in dieser Scheibe unangetastet.
- `sms_trip.py:217`s `_TH_VAL {NONE:0, MED:2, HIGH:3}` ist die dokumentierte SMS-Builder-Level-Kodierung (Bug #874: „1=L, 2=M, 3=H"), kein Abweichler der Thunder-Ordnung — bewusst NICHT auf `thunder_ordinal` umgestellt, da andere Wertebedeutung (Builder-Level statt Sortier-Ordinal).
- Die sichtbare Skalen-Änderung in `compact_summary.py` (vier Delta-Zonen) sowie im seltenen `weather_metrics.py::_cloud_pct_emoji`-Fallback (DNI/WMO-Code fehlen) ist PO-gewollt (Entscheidung 2026-07-12) — kein Bug, keine Regression.
- `weather_metrics.py:1032-1039`s `_ENUM_ORDER` bleibt ein lokales Hybrid-Dict (ThunderLevel-Anteil kanonisch, PrecipType-Anteil lokal) statt vollständig auf `max_thunder` zu wechseln — eine generische Migration beider Enum-Typen ist nicht Teil dieser Scheibe (PrecipType-Ordnung wurde nie als Duplikat identifiziert).
- `day_comparison.py`s defensive `.value if hasattr(...) else ...`-Normalisierung vor dem `thunder_ordinal`-Aufruf ist durch die str-Enum-Hash-Äquivalenz technisch redundant geworden, wird aber aus Minimal-Diff-Gründen nicht entfernt (verhaltensneutral in beide Richtungen, kein Scope-Kriechen).
- Korrektur ggü. dem ursprünglichen Analyse-Auftrag: `helpers.py:1091` ist entgegen dem dortigen „toter Local"-Verdacht (F841) aktiv genutzt (7. Thunder-Stelle statt Löschkandidat); `tests/refactor/test_dead_code_scheibe1.py::TestCloudPctEmoji` bleibt entgegen der ursprünglichen Annahme „Boundary-Tests bleiben grün" NICHT unverändert, da diese Datei die alte `weather_metrics.py`-eigene Skala testet, nicht die Mail-Skala.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Die Wolken-Skalen-Vereinheitlichung ist eine PO-Produktentscheidung (visuelle Konsistenz über Kanäle), keine Architekturentscheidung — die Mechanik folgt exakt dem in Scheibe 1-5 etablierten Koexistenz-Muster (additive Funktionen in `metric_format.py`, Delegation an den Aufrufstellen, keine neue Abstraktion, kein Bruch bestehender Signaturen). Die Thunder-Ordinal-Konsolidierung ist reine Deduplizierung ohne Verhaltensänderung. Keine neue externe Abhängigkeit, keine Schema-/Persistenzänderung (ThunderLevel bleibt str-Enum), keine API-Vertragsänderung. Kein architekturrelevanter Entscheidungsbedarf über die bereits getroffene PO-Entscheidung zur Skala hinaus.

## Changelog

- 2026-07-12: Initial spec created
- 2026-07-12: Drei Fakten-Korrekturen gegenüber dem Analyse-Dokument (Code-Abgleich beim Spec-Schreiben): (1) Thunder-Ordinal-Stellen 6→7 — `helpers.py:1091` ist NICHT tot, sondern aktiv genutzt in der Thunder-Pill (Zeilen 1260/1262) und wird migriert statt gelöscht; (2) `weather_metrics._cloud_pct_emoji` nutzt eine DRITTE Skala (20/40/70/90); (3) deren Boundary-Test `tests/refactor/test_dead_code_scheibe1.py::TestCloudPctEmoji` verankert die alte Skala und wird ANGEPASST (4 von 5 Werten), nicht unverändert grün erwartet.
- 2026-07-12 (Adversary-Runde 1, F001 CRITICAL): Impact-Analyse-Lücke — die Kompakt-Zusammenfassung rendert per Default als eingebetteter Satz in JEDER Trip-Briefing-Mail (trip_report.py:126 → _generate_compact_summary → CompactSummaryFormatter), nicht nur im separaten compact-Format; die AC-3-Skalen-Änderung schlägt daher in 8 Golden-Mail-Fixtures durch (tests/golden/email/, je exakt 1 Emoji-Zeile). **PO-Rückfrage 2026-07-12 mit explizitem Go: Skala gilt überall konsequent, Golden-Fixtures werden neu eingefroren** (Diff-Beweis: ausschließlich die Emoji-Zeile ändert sich). F002 (MEDIUM): Spec-Behauptung „calculate_sunny_hours liefert immer float" war unpräzise — leerer-Daten-Zweig lieferte `int 0` (nicht live erreichbar, beide Aufrufer guard-geschützt); wird auf `0.0` korrigiert.
- 2026-07-12 (Implementierung): Drei weitere Fakten-Korrekturen: (1) `TestCloudPctEmoji` liegt tatsächlich in `tests/tdd/test_weather_emoji_dni.py` (nicht `tests/refactor/test_dead_code_scheibe1.py` — Spec-Pfadfehler); (2) ACHTE lebende Thunder-Ordinal-Kopie gefunden (`src/services/weather_change_detection.py:35`, Nutzungen 544/545/609) — wird mit-migriert (Issue-Ziel „existiert genau einmal"), Stellen-Zählung 7→8; (3) AC-5-Testmechanik von Datei-Read auf Modul-Introspektion (`hasattr`) umgestellt, da das #765-Hygiene-Gate Produkt-Quelltext-Reads in Tests verbietet — gleiches gilt rückwirkend für den Scheibe-5-AC-4-Kommentar-Wächter (ersatzlos entfernt, s. slice5-Changelog) und `test_issue_778_dead_code.py` (auf hasattr umgestellt, macht einen Alt-#765-Offender grün).
