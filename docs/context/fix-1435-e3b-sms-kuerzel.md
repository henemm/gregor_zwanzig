# Context: fix-1435-e3b-sms-kuerzel

Etappe **E3b** von #1435 („Register hält nur Namen"). Vorgänger: E1a-1, E1a-2, E1b, E3a
— alle live. Der E3-Zuschnitt steht in `docs/context/fix-1435-e3-namensfehler.md`
(Befund C); die Befunde A und B jener Etappe sind mit E3a erledigt.

## Request Summary

Die Touren-SMS benennt zwei Wettergrößen mit anderen Kürzeln als das zentrale Register:
Schneehöhe heißt dort `SN` statt `SD`, Schneefallgrenze `SFL` statt `SL`. Beides wird
auf die Registerkürzel vereinheitlicht. Damit endet die Doppelbedeutung von `SN`, das
in derselben SMS auch die amtliche Schneewarnung bezeichnet.

## Ausgangslage: drei Vokabulare, ein Ausgabekanal

| Kennung | Touren-SMS heute | Register `sms_code` | Bewertung |
|---|---|---|---|
| `precipitation`, `rain_probability`, `wind`, `gust` | `R`, `PR`, `W`, `G` | identisch | kein Konflikt |
| `thunder` | `TH:` | `TH` | Doppelpunkt ist Grammatik (`builder.py:16`), `/api/sms-symbols` entfernt ihn |
| `snow_depth` | **`SN`** | **`SD`** | **echter Konflikt** |
| `snowfall_limit` (Schneefallgrenze) | **`SFL`** | **`SL`** | **echter Konflikt** |
| `fresh_snow` (Neuschnee) | **`SN24+`** | **`NS`** | **echter Konflikt** — PO-Entscheid 2026-08-01: zieht mit zu `NS24+` |
| `wind_chill` | `FN`/`FK`/`FD` + `WC` | `TF` | strukturell unauflösbar (vier Kürzel, eine Größe) — bleibt |
| Lawinenstufe | `AV` | *kein Registereintrag* | bleibt |

Beispiel einer heute ausgelieferten Zeile
(`tests/golden/sms/arlberg-winter-morning.txt:1`):

```
Arlberg: K-12 D-4 R- PR- W45@8(75@13) G70@8(110@13) TH:- TH+:- SN180 SN24+25 SFL1800 AV3 WC-22
```

**Das Nutzer-Argument:** `HAZARD_SMS_SYMBOLS["snow"] = "SN"` (`hazard_symbols.py:20`,
amtliche Schneewarnung, Form `!SN:H@14`) gegen `SN180` = Schneehöhe 180 cm. Nur die
Position im Format trennt die beiden, nicht die Bedeutung.

Der Registerwert `NS` für Neuschnee ist selbst schon Folge dieser Kollision:
PO-Korrektur 2026-07-29 (Adversary-Fund #1362 S5b), dokumentiert als Kommentar in
`metric_catalog.py:512-517`.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/sms_trip.py:55-63` | `SMS_SYMBOL_BY_METRIC` — Kern des Trip-Vokabulars, Quelle für Schwellwert-Filter (#624) und Abwahl (#944) |
| `src/output/tokens/builder.py:37-47` | `PRIORITY` — Kürzungsrang; wird in `_wintersport()` **ungeschützt** gelesen (`:204`), fehlender Schlüssel ⇒ Absturz |
| `src/output/tokens/builder.py:60-75` | `POSITIONAL` — Reihenfolge im Wire-Format, Tupel `(Symbol, Kategorie)` |
| `src/output/tokens/builder.py:183-205` | `_wintersport()` — erzeugt die Token; `:198` enthält die **inverse** Schwellwertlogik `if sym == "SFL"` (#873) |
| `src/output/tokens/render.py:10` | `DROP_ORDER` — Reihenfolge beim Kürzen zu langer SMS |
| `src/output/adapters/trip_result.py:200-210` | `_wintersport_default_config()` — `MetricSpec(symbol=…)` für den CLI-Pfad |
| `src/output/renderers/trip_report.py:263-287` | verbindet Nutzereinstellung (metric_id) mit Symbol: Schwellwerte + Abwahl |
| `src/output/tokens/hazard_symbols.py:20` | `"snow": "SN"` — **amtliche Warnung, bleibt unverändert** |
| `src/app/metric_catalog.py:327, 500, 518` | `sms_code` `SL`/`SD`/`NS` — die Zielwerte |
| `api/routers/config.py:30-56` | `/api/sms-symbols` serialisiert `SMS_SYMBOL_BY_METRIC` zur Laufzeit ans Frontend |

## Existing Patterns

- **Register als Quelle:** `alert/render.py:12,90` und `comparison.py:23,519` lesen die
  Kürzel bereits über `metric_catalog.get_sms_code()`. Der Trip-SMS-Pfad ist der letzte
  mit eigenem hartkodiertem Vokabular.
- **E3a-Muster:** eine Fläche hört auf, eigene Namen zu führen, und benennt stattdessen
  den vom Backend aufgelösten Zustand. Hier analog: das Trip-Vokabular hört auf,
  eigene Kürzel zu erfinden.
- **Golden-Tests** frieren die ausgelieferte Zeile wörtlich ein
  (`tests/golden/sms/`, `tests/golden/text_report/`).

## Dependencies

**Upstream** (liefert Symbole): `SMS_SYMBOL_BY_METRIC`, `_wintersport_default_config()`,
`metric_catalog.sms_code`.

**Downstream** (verbraucht Symbole als String-Schlüssel):

| Station | Ort | Vergleicht String? |
|---|---|---|
| Schwellwerte (#624) | `trip_report.py:263-267` | ja, Dict-Lookup |
| Abwahl (#944) | `trip_report.py:270-276` | ja |
| Token-Bau | `builder.py:224` `by_sym` | ja, Dict-Schlüssel |
| Wintersport-Schwelle (#873) | `builder.py:198` `sym == "SFL"` | **ja, hartes Literal** |
| Reihenfolge | `builder.py:75` `POS_INDEX` | ja, Tupel |
| Kürzungsrang | `builder.py:204` `PRIORITY[sym]` | ja, **ungeschützt** |
| Kürzen | `render.py:41-64` `DROP_ORDER` | ja |
| Frontend | `/api/sms-symbols` → `WeatherMetricsTab.svelte:153-156` | nein, zieht automatisch nach |
| Go | — | kennt nur `metric_id`, keine Symbole |

## Existing Specs

- `docs/reference/sms_format.md` — Wire-Format der Touren-SMS (Zeilen 45, 60, 203,
  292-294, 331, 365). **Muss mitgezogen werden**, ist die Referenz des Formats.
- `docs/specs/modules/output_token_builder.md`, `docs/specs/wintersport_extension.md`,
  `docs/specs/modules/feat_873_snow_thresholds.md` — enthalten die Kürzel wörtlich.
- `docs/specs/_archive/modules/issue_917_alert_renderer.md:173` — **AC-9 friert `SFL`
  ausdrücklich ein.** Diese Festlegung wird durch E3b aufgehoben.
- `docs/adr/0011-alert-render-single-backend-renderer.md` — ADR, dessen Ziel 3
  („doppelte Zuordnungen entfernen") 2026-06-30 für die Briefing-SMS ausgenommen wurde.

## Risks & Considerations

1. **Nutzerdaten sind nicht betroffen — geprüft.** In `data/` existiert kein
   gespeichertes `"SN"`/`"SFL"`; Einstellungen werden durchweg per `metric_id`
   abgelegt (`display_config.metrics[].metric_id`), das Symbol entsteht erst zur
   Renderzeit. Keine Migration nötig, keine Entwertung.
2. **Das ausgelieferte SMS-Format ändert sich zu einem Stichtag.** Wer `SN180` gelesen
   hat, liest künftig `SD180`. Keine Übergangsphase möglich — die SMS hat kein Feld
   für Erklärungen.
3. **Atomare Änderung erforderlich.** `SMS_SYMBOL_BY_METRIC`, `PRIORITY`, `POSITIONAL`,
   `DROP_ORDER`, `_wintersport()`-Paare, das `sym == "SFL"`-Literal und
   `trip_result.py` müssen gemeinsam ziehen. Zieht eine Stelle nicht mit, greifen
   Schwellwert-Filter und Abwahl **lautlos** nicht mehr — kein Fehler, nur falsche
   Ausgabe. Das ist die Hauptgefahr dieser Etappe.
4. **`PRIORITY[sym]` in `builder.py:204` ist ungeschützt** — ein vergessener
   Schlüssel bricht die SMS-Erzeugung mit einem Absturz statt mit einer Auslassung.
   Zugleich der einzige Punkt, der bei Unvollständigkeit *laut* scheitert.
5. **Aufhebung einer dokumentierten Festlegung.** AC-9 aus #917 und die PO-Präzisierung
   vom 2026-06-30 werden überschrieben. Nach ADR-Regel („Abweichung ⇒ neues ADR") muss
   das ausdrücklich festgehalten werden, sonst ist es ein stiller Rückgängig-Macher.
6. **Vollständige Registerherrschaft ist in E3b nicht erreichbar** — `wind_chill` mit
   vier Kürzeln und `AV` ohne Registereintrag bleiben Sonderfälle. E3b beseitigt die
   *Widersprüche*, nicht die Zweigleisigkeit. Die bleibt späteren Etappen.
7. **Nachweis nur über eine echt zugestellte SMS-Zeile.** Die SMS-Zeile steht nicht in
   der Mail; belegbar ist sie über den Telegram-Kurzstil
   (s. Memory `reference_telegram_kurzstil_proves_sms_line`).

## Technischer Ansatz (Analyse)

Die naheliegende Lösung „alle Kürzel aus dem Register ableiten" geht nur zur Hälfte —
und der Grund dafür ist eine bewusste Schichtgrenze, keine Nachlässigkeit:

- `src/output/tokens/` importiert **nichts** aus `src/app/` (geprüft: nur `utils`,
  `dto`, `metrics`). Es ist die app-freie Formatschicht. Ein Import von
  `metric_catalog` dort wäre eine neue Abhängigkeit nach oben und würde die
  Token-Erzeugung an die Registerladung koppeln.
- `src/output/renderers/` darf das Register lesen und tut es bereits
  (`alert/render.py:12`, `comparison.py:23`).

Daraus folgt der Zuschnitt:

| Ort | Vorgehen |
|---|---|
| `sms_trip.py::SMS_SYMBOL_BY_METRIC` | **aus dem Register ableiten** (`get_sms_code()`), mit benannter Ausnahme für die Grammatikform `TH:`. Danach kann diese Tabelle nicht mehr abdriften — sie ist keine Liste mehr. |
| `builder.py`, `render.py`, `trip_result.py` | Literale umschreiben. Ableitung dort ist ausgeschlossen (Schichtgrenze). |
| **Ratsche** | Ein Test in `tests/` — die Testschicht darf beides importieren — vergleicht die in `builder.py`/`render.py`/`trip_result.py` verwendeten Symbole gegen das Register und meldet jede Abweichung beim Namen. Ausnahmen (`AV` ohne Registereintrag, `WC`/`FN`/`FK`/`FD` als Vier-Kürzel-Sonderfall, `TH:`-Grammatik) stehen als ausdrückliche Liste im Test, nicht als stille Auslassung. |

**Pflicht für die Ratsche** (Erfahrung aus E3a, zwei grüne Wächter, die nichts prüften):
Der Test gilt erst als geliefert, wenn eines der Symbole absichtlich verfälscht wurde
und der Test daraufhin nachweislich rot war. Regel-Budget: Prüfdatum **2026-10-30**.

## Entschieden (PO, 2026-08-01)

**Neuschnee `SN24+` zieht mit → `NS24+`.** Begründung: das Register führt für Neuschnee
bereits `NS`, gesetzt durch PO-Korrektur 2026-07-29 genau wegen dieser Kollision. Bliebe
`SN24+` stehen, wäre er nach der Umstellung der einzige verbliebene `SN…`-Token neben
der amtlichen Warnung `!SN:` — die Doppeldeutigkeit bliebe zur Hälfte bestehen. Kostet
keine zusätzliche Fläche: dieselben Dateien, dieselben Stationen.

Zielzeile nach E3b:

```
Arlberg: K-12 D-4 R- PR- W45@8(75@13) G70@8(110@13) TH:- TH+:- SD180 NS24+25 SL1800 AV3 WC-22
```
