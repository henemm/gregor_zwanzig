---
issue: 1888
epic: 1435
etappe: E6
scheibe: B
schliesst: 1857
voraussetzung: 1887
created: 2026-08-16
workflow: fix-1888-e6b-kuerzel-legende
track: standard
---

# Context: fix-1888-e6b-kuerzel-legende

## Request Summary

Die Oberfläche zeigt SMS-Kürzel bei Wettergrößen bereits an (`K`, `D`, `FK`, `FD`, `N`, `FN`, …),
erklärt aber nirgends, was sie bedeuten. Diese Scheibe ergänzt im Reiter „Wetter-Metriken" eine
Legende, die Kürzel und Bedeutung aus **derselben Quelle wie die Marken** bezieht — als **ein**
geteilter Baustein für Trip- **und** Ortsvergleich-Editor. Vorbild ist die bereits arbeitende
Legende für amtliche Warnungen im selben Reiter.

## Ausgangslage nach Scheibe A (#1887, gemerged in `8adc88d4`)

Scheibe A hat die Trip-Kürzel ins Register geholt und die Tagesrichtungs-Kollision aufgelöst.
**Folge für diese Scheibe: die Klartext-Bedeutungen existieren bereits** — es muss kein einziger
Erklärtext neu erfunden werden.

| Kürzel | metric_id | `label_de` (Registerwert) |
|---|---|---|
| `N` | `temperature_night` | Nacht-Tiefsttemperatur |
| `K` | `temperature_day_low` | Tages-Tiefsttemperatur (Gehzeit) |
| `D` | `temperature_day_high` | Tages-Höchsttemperatur (Gehzeit) |
| `FN` | `wind_chill_night` | Gefühlte Nacht-Tiefsttemperatur |
| `FK` | `wind_chill_day_low` | Gefühlte Tages-Tiefsttemperatur (Gehzeit) |
| `FD` | `wind_chill_day_high` | Gefühlte Tages-Höchsttemperatur (Gehzeit) |

Gemessen aus `src/app/metric_catalog.py` (Feld `sms_multi_symbols`, eingeführt `:76`).
Damit beantwortet sich **AC-2** („warum drei Kürzel?") direkt aus vorhandenen Registerdaten.

## Related Files

### Frontend — Zielort

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | **Zielkomponente.** Liegt bereits unter `shared/`, `context: 'route' \| 'vergleich'` (`:169`). Vorbild-Legende `:1210-1224` im Snippet `officialAlertsToggle` `:1189-1232` |
| `.../shared/weather-metrics-tab/WeatherV2Reihenfolge.svelte` | Kürzel-Marke „Kurzform" je Metrik-Zeile; Prop `kuerzelById` `:54`, Nutzung `:87`/`:157`, Label-Render `:98` |
| `.../shared/weather-metrics-tab/ThresholdMetricRow.svelte` | `<code>`-Kürzel, Prop `smsSymbol` `:21`, Render `:37` |
| `.../shared/weather-metrics-tab/MultiSymbolMetricRow.svelte` | Mehrfach-Kürzel, Prop `symbols` `:11`, Render `:20-22` |
| `.../shared/weather-metrics-tab/compareMetricSelection.ts` | Typ `CompareSelectionEntry` `:7-30` — trägt `label` **und** `sms_code` |
| `.../shared/weather-metrics-tab/weatherMetricsTabSections.ts` | Abschnitts-Reihenfolge je Kontext |
| `frontend/src/lib/types.ts` | `MetricEntry` `:159-165`/`:180-185` (`label` = `label_de`, `col_label`, `sms_code`) |

### Frontend — Datenquellen im Scope der Zielkomponente

| Kontext | Kürzel | Bedeutung/Label | Zeilen |
|---|---|---|---|
| `route` | `metricSymbols` (aus `/api/sms-symbols`) | `metricById` (aus `/api/metrics`, Feld `label`) | `:182-186` bzw. `:331-335` |
| `vergleich` | `compareKuerzelById` | `compareMetricById` (Feld `label`) | `:1102-1106` bzw. `:1082-1096` |

**Beide Paare liegen bereits im selben Scope und werden bereits gemeinsam an denselben
Reihenfolge-Block gereicht** (`:1492-1502` route, `:1339` vergleich). Eine Legende dort braucht
keine neue Ladelogik.

### Backend — Quellen

| Datei | Relevanz |
|---|---|
| `api/routers/config.py:30-69` | `/api/sms-symbols`; `metrics`-Eintrag = `{metric_id, sms_symbols}` — **kein `label`**; `hazards`-Eintrag hat `label` (`:66`) |
| `api/routers/config.py:72+` | `/api/metrics`, serialisiert `label_de` als `label` (`:85`), filtert auf `selectable=true` |
| `src/app/metric_catalog.py` | Register; `sms_multi_symbols` `:76`, `sms_code` `:69` |
| `src/output/renderers/compare_metric_catalog.py:251-315` | `/api/compare/metrics`; `label` aus `get_metric(...).label_de` (`:286`/`:308`), `sms_code` (`:310`) |

## Existing Patterns

1. **Fail-soft-Legende** — `{#if smsSymbols}` … `{#each}` … `<code>Kürzel</code> Bedeutung`
   (`WeatherMetricsTab.svelte:1210-1224`). Kein Kontext-Guard: die Warnungs-Legende erscheint in
   **beiden** Kontexten. Genau dieses Muster verlangt AC-4 und AC-5.
2. **Read-only-Serialisierung als eigener Endpunkt** — `/api/sms-symbols` wurde in #1318 AC-9
   bewusst getrennt angelegt, damit Gefahrenarten nicht als wählbare Metriken missverstanden
   werden (Docstring `api/routers/config.py:32-41`).
3. **Kein zweites Vokabular im Frontend** — bereits durch einen Wächter erzwungen, siehe R3.

## Dependencies

- **Upstream:** `/api/sms-symbols`, `/api/metrics`, `/api/compare/metrics`; Register
  `src/app/metric_catalog.py`. Alle drei Endpunkte werden von der Zielkomponente **heute schon**
  geladen (`:461-466`, `:470`, `:499-527`).
- **Downstream:** Sieben Mount-Punkte der Zielkomponente — `TripNewEditor` (2×),
  `TripEditView`, `TripTabs`, `CompareTabs` (2×), `CompareNewEditor` (2×). Eine additive Legende
  in der geteilten Komponente erreicht alle, ohne dass ein Mount angefasst wird.

## Existing Specs

- `docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md` — Scheibe A. Grenze ausdrücklich:
  „**Keine Legende in der Oberfläche.** Das ist Scheibe B (#1888)" (`:481-485`).
- `docs/specs/modules/fix_1435_e3b_sms_kuerzel.md` — E3b, Herkunft von `/api/sms-symbols`.
- `docs/context/fix-1857-e6-temp-register.md` — Analyse und Messbelege der Gesamt-Etappe,
  Scheiben-Zuschnitt `:334-339`, Scope-Schätzung Scheibe B `:346`.

## Bestehende Tests (Ausgangspunkt und Wächter)

| Datei | Was sie prüft | Art |
|---|---|---|
| `frontend/src/lib/components/shared/__tests__/officialAlertLegend.test.ts` | Struktur der Vorbild-Legende `:81-126`; Legende in **beiden** Kontexten `:213-292`; Ladepfad im Vergleich `:294-360`; **„keine zweite Liste"-Wächter** `:365-425` | Quelltext-/AST-Analyse, **kein DOM, kein Browser** |
| `.../shared/__tests__/weather_metric_kuerzel_marken.test.ts` | Marken je Kontext aus der jeweiligen Registerquelle `:381-400`, `:443-490` | Quelltext-/AST-Analyse |
| `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts` | holt `/api/sms-symbols` (`:164`) und vergleicht mit den **gerenderten** Marken (`:417`ff) | Playwright, echter Browser |
| `frontend/e2e/weather-metrics-editor-day-range-kuerzel.spec.ts:110-135` | Kürzel-Badges in „04 — Schwellwerte" | Playwright, echter Browser |

## Risks & Considerations

### R1 — Die Kürzel-Mengen sind je Kontext VERSCHIEDEN 🔴

Nicht nur die Quelle unterscheidet sich, sondern der Inhalt:

| | Trip (`/api/sms-symbols`) | Vergleich (`/api/compare/metrics`) |
|---|---|---|
| Schlüssel | `metric_id` | Compare-Key = Paar (metric_id, Auswertung) |
| Kardinalität | mehrere Kürzel je Größe möglich (`thunder` → `TH`, `TH+`) | 0..1 Kürzel je Zeile, dafür **mehrere Zeilen mit demselben Kürzel** |
| `N/K/D/FN/FK/FD` | vorhanden | **kommen dort gar nicht vor** |
| `TF` | nicht vorhanden | vorhanden |

**Folge für AC-2:** Die Zusicherung „der Nutzer erkennt, dass `FK`/`FD`/`FN` dieselbe Größe in
verschiedenen Tagesrichtungen bezeichnen" ist **nur im Trip-Kontext einlösbar** — im Ortsvergleich
existieren diese Kürzel nicht. AC-5 (Legende in beiden Flächen) bleibt gültig, aber mit je
kontexteigenem **Inhalt**. Eine gemeinsame, fest verdrahtete Liste wäre in beiden Kontexten falsch.

### R2 — Vorbestehende Kürzel-Kollision im Ortsvergleich 🔴

`/api/compare/metrics` liefert `sms_code="D"` für **zwei** Zeilen (`temperature_max` und
`temperature_min`) und `TF` für zwei weitere (`wind_chill` min/max). Gemessen und dokumentiert in
`docs/context/fix-1857-e6-temp-register.md:260-261` (G4); Scheibe A hat das ausdrücklich **nicht**
behoben (`fix_1887_e6a_sms_kuerzel_register.md:502-504`).

Eine Legende, die pflichtgemäß dieselbe Quelle wie die Marken benutzt (AC-3), zeigt dort also
`D` zweimal mit widersprüchlicher Bedeutung. **Entscheidungspunkt für die Spec** (Optionen in der
Analyse-Phase zu bewerten, nicht hier vorwegzunehmen). Wichtig: Die Kollision ist nutzersichtbar
falsch und damit nach der Nebenbefund-Triage (a) ein **eigenes Issue** wert — sie in dieser
Scheibe mitzubeheben wäre Scope-Ausweitung.

### R3 — Der „keine zweite Liste"-Wächter trifft diese Arbeit direkt

`officialAlertLegend.test.ts:365-425` scannt **alle** Quellen unter `frontend/src` auf hartkodierte
Kürzel-Zuordnungen. Eine Legende mit eigener Bedeutungstabelle im Frontend würde ihn rot machen.
Das ist ein Verbündeter für AC-3, kein Hindernis — aber die Umsetzung muss von Anfang an über die
vorhandenen `label`-Felder joinen.

### R4 — `cape`/`CP` hat im Trip-Pfad kein erreichbares Label

`/api/sms-symbols` führt `cape` mit Kürzel `CP`; `/api/metrics` filtert auf `selectable=true` und
lässt `cape` weg (`src/app/metric_catalog.py:949-957`). Ein Join `metricSymbols × metricById` deckt
damit 27 von 28 Kürzel-Größen ab.

**Zu messen, nicht zu raten:** Wird `CP` überhaupt als Marke gerendert? Wenn nein, ist die Lücke
folgenlos. Wenn ja, zeigt die Oberfläche ein Kürzel ohne Erklärung — dann verlangt AC-1 eine
Lösung, und die saubere wäre ein `label`-Feld in `/api/sms-symbols` analog zu `hazards[].label`
(`api/routers/config.py:66`). Das wären ~2 Zeilen Backend und bliebe im Sinne von AC-3
**eine** Quelle. Der Ticket-Text schließt „Register- und Backend-Änderungen" aus — gemeint ist
dort das Register (#1887); eine Serialisierungs-Ergänzung am Legenden-Datenpfad ist davon zu
unterscheiden und in der Spec explizit zu entscheiden.

### R5 — Nachweis-Schicht: der Vorbild-Test taugt nicht als Vorbild

Die bestehende Legenden-Prüfung ist Quelltext-Analyse. AC-6 (Handy 320–899 px, vollständig
lesbar) und AC-7 (Kontrast ≥ 4.5:1) sind so **nicht** belegbar — Präzedenzfall #1446: eine Tabelle
mit `display:none` meldet per DOM-Abfrage fälschlich „sichtbar". Für diese beiden ACs ist ein
echter Browser Pflicht; Muster liefert `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`.
Erfahrungswert: der Nachweis kostet mehr als der Mechanismus — beim LoC-Budget doppelt ansetzen.

### R6 — Platzierung muss beide Kontexte treffen

Der einzige Block, den beide Kontexte teilen **und** der die Kürzel bereits erhält, ist der
Reihenfolge-Block (`:1479-1512` route, `:1313-1345` vergleich). Die Kürzel-Marken erscheinen
im Trip-Kontext zusätzlich in „04 — Schwellwerte" (`:1559-1730`), den es im Vergleich nicht gibt.
Eine Legende am Reihenfolge-Block erreicht beide Flächen mit einem Baustein; ob sie damit nah
genug an den Schwellwert-Marken steht, ist eine Design-Frage für die Spec.

### R7 — Additiv in einer Komponente mit sieben Mount-Punkten

`WeatherMetricsTab.svelte` ist 1991 Zeilen lang und wird siebenfach gemountet. Die Änderung ist
rein additiv und fail-soft, aber ein Fehler wirkt überall. Regression-Absicherung der
bestehenden Reiter gehört in die Testliste.

## Scope Assessment (Intake: Standard Track, Summe 1)

| | Schätzung |
|---|---|
| Produktiv-Dateien | 1 sicher (`WeatherMetricsTab.svelte`), +1 bedingt (`api/routers/config.py`, nur falls R4 greift) |
| Produktiv-LoC | ~40–80 |
| Test-Dateien | ~2–3 (Vitest-Struktur + Playwright für AC-6/AC-7) |
| Test-LoC | ~120–180 |
| Risiko | LOW–MEDIUM — reine Anzeige, aber zwei Kontexte mit verschiedenen Vokabularen |

## Open Questions (in die Analyse-Phase, nicht hier entscheiden)

- [ ] **F1:** Wird `CP` als Marke gerendert? (entscheidet R4 — Backend-Zeile ja/nein)
- [ ] **F2:** Wie geht die Legende im Ortsvergleich mit doppelten Kürzeln um (R2)?
- [ ] **F3:** Platzierung — nur am Reihenfolge-Block, oder zusätzlich bei „04 — Schwellwerte"? (R6)

---

# Analysis (Phase 2, 2026-08-16)

## Type

Feature-Ergänzung in der Oberfläche (Anzeige), rein additiv, fail-soft. Kein Schreibpfad,
kein Versandpfad, keine Persistenz, keine Auth.

## Was gemessen wurde (nicht gelesen)

### M1 — `CP` ist die einzige Lücke, und sie ist folgenlos → **kein Backend-Anteil** ✅

Auszählung über das Register (`_METRICS` × `SMS_SYMBOL_BY_METRIC`/`SMS_MULTI_SYMBOLS_BY_METRIC`):

```
Kuerzel-Groessen gesamt: 28
davon NICHT in /api/metrics (selectable=False): 1
   ('cape', ['CP'], 'Gewitterenergie (CAPE)')
```

Gegenprobe im Frontend: `grep -n "cape\|CP" WeatherMetricsTab.svelte weather-metrics-tab/*` →
**keine Fundstelle**. `cape` hat im Reiter keine Zeile (die Zeilen stammen aus `/api/metrics`,
das `selectable=False` herausfiltert) und erscheint deshalb auch nicht als Marke.

**Folge:** Wird die Legende aus der Menge der **gerenderten** Größen gespeist statt aus dem rohen
Kürzel-Katalog, entsteht kein Eintrag ohne Bedeutung. R4 entfällt, `/api/sms-symbols` bleibt
unangetastet, die Scheibe bleibt **reines Frontend** — im Einklang mit der Ticket-Grenze
„Register- und Backend-Änderungen sind #1887".

Umgekehrt gilt: Eine Legende, die naiv über `smsSymbols.metrics` iteriert, produziert genau **einen**
Eintrag `CP` ohne Label. Das ist die zu vermeidende Umsetzung und gehört als Zusicherung bewacht.

### M2 — Die Kollision im Ortsvergleich löst sich über die Auswertung auf ✅

Auszählung über `get_compare_metric_catalog()`:

```
Compare-Zeilen gesamt: 25 | mit sms_code: 25 | verschiedene Kuerzel: 23
  D   -> ('temp_max_c', 'Temperatur', 'Maximum') / ('temp_min_c', 'Temperatur', 'Minimum')
  TF  -> ('wind_chill_min_c', 'Gefühlte Temperatur', 'Minimum') / ('wind_chill_max_c', ..., 'Maximum')
```

Entscheidend: Der Compare-Katalog liefert **`label` UND `aggregation_label`** in derselben Antwort
(`CompareSelectionEntry`, `compareMetricSelection.ts:7-30`). Eine Legende der Form
`Kürzel — Label (Auswertung)` ist damit **eindeutig lesbar**, obwohl das Kürzel doppelt vorkommt:

```
D   Temperatur (Maximum)
D   Temperatur (Minimum)
```

**Auflösung von F2:** Die Legende zeigt **beide** Zeilen, statt zu entdoppeln. Das ist die einzige
Variante, die AC-3 einhält (dieselbe Quelle wie die Marken — und die Marken zeigen das Kürzel
tatsächlich an beiden Zeilen). Sie macht die vorbestehende Doppelbelegung sichtbar, statt sie zu
kaschieren.

### M2b — Nachmessung: die **zugestellte** Vergleichs-SMS ist NICHT mehrdeutig ✅ Korrektur zu R2

Die zunächst naheliegende Sorge („in der Vergleichs-SMS trägt `D` zwei verschiedene Werte") ist
**falsch**. Gemessen in `src/output/renderers/comparison.py:647-650`:

```python
code = get_sms_code(catalog_id) if catalog_id else ""
...
code = f"{code}{_sms_aggregation_sign(metric_id)}"
```

Die Vergleichs-SMS hängt das Auswertungszeichen an: Temperatur-Maximum wird `D+`, Minimum `D-`.
Die Doppelbelegung des rohen `sms_code` ist damit ein Merkmal des Katalogfeldes, **nicht** ein
Defekt der Ausgabe. Kein eigenes Issue aus diesem Grund.

**Aber:** Die Marken in der Oberfläche zeigen den rohen `sms_code` ohne Zeichen
(`compareKuerzelById`, `:1102-1106`) — der Nutzer liest im Editor `D`, in seiner SMS aber `D+`.
Das ist eine kleine, echte Lücke zwischen Anzeige und Zustellung, aber **nicht Gegenstand dieser
Scheibe** (sie beträfe die Marken, nicht die Legende). Einordnung: Sammel-Eintrag in #1199 nach
der Auslieferung, kein eigenes Issue.

**Folge für die Legende:** Sie bleibt bei der Form der Marken (`D`, ohne Zeichen) — AC-3 verlangt
dieselbe Quelle wie die Marken. Die Eindeutigkeit stellt der Text her: `D — Temperatur (Maximum)`.

### M3 — AC-2 ist im Ortsvergleich strukturell nicht einlösbar 🔴 Ticket-Prämisse zu eng

`N/K/D/FN/FK/FD` gehören zu den Größen `temperature_night`/`_day_low`/`_day_high` und
`wind_chill_night`/`_day_low`/`_day_high`. Diese existieren **nur** im Trip-Pfad; der
Compare-Katalog kennt stattdessen `temp_min_c`/`temp_max_c` und `wind_chill_min_c`/`_max_c`
mit den Kürzeln `D` und `TF`.

AC-2 („der Nutzer erkennt, dass `FK`/`FD`/`FN` dieselbe Größe in verschiedenen Tagesrichtungen
bezeichnen") ist deshalb eine Zusicherung über den **Trip-Editor**. Im Ortsvergleich gäbe es
nichts zu erkennen. AC-5 (Legende in beiden Flächen) bleibt unberührt gültig — nur der **Inhalt**
ist je Kontext ein anderer. Das ist in der Spec zu präzisieren, sonst entsteht ein strukturell
nie erfüllbares Kriterium.

## Technical Approach (Empfehlung)

### Ein Baustein, zwei Speisungen

Die Legende entsteht als **ein** Snippet/eine Komponente in
`frontend/src/lib/components/shared/WeatherMetricsTab.svelte` — der Datei, die beide Kontexte
bereits teilen und die alle sieben Mount-Punkte versorgt. AC-5 ist damit strukturell erfüllt,
ohne dass ein Mount angefasst wird.

Gespeist wird sie je Kontext aus dem Paar, das im selben Scope **bereits** nebeneinanderliegt und
schon heute gemeinsam an den Reihenfolge-Block gereicht wird:

| Kontext | Kürzel | Bedeutung |
|---|---|---|
| `route` | `metricSymbols` (`:182-186`) | `metricById[...].label` (`:331-335`) |
| `vergleich` | `compareKuerzelById` (`:1102-1106`) | `compareMetricById[...].label` + `.aggregation_label` (`:1082-1096`) |

Keine neue Ladelogik, kein neuer Endpunkt, keine zweite Liste — damit hält AC-3 und der
vorhandene Wächter `officialAlertLegend.test.ts:365-425` bleibt grün.

### Platzierung

Unmittelbar am **Reihenfolge-Block** (`:1479-1512` route, `:1313-1345` vergleich). Begründung:
Es ist der einzige Block, den beide Kontexte teilen, er zeigt **alle** Größen (auch die
abgewählten, Aus-Gruppe `WeatherV2Reihenfolge.svelte:174-178`) und er erhält `kuerzelById`
bereits. Die zusätzlichen Marken in „04 — Schwellwerte" (nur `route`) sind eine Teilmenge und
werden von derselben Legende miterklärt — AC-1 verlangt „dort im Reiter", nicht „neben jeder
einzelnen Marke".

### Fail-soft

Muster der Warnungs-Legende: Guard auf die geladenen Daten (`{#if ...}`), kein Kontext-Guard.
Fehlt die Quelle, entfällt die Legende still, der Reiter bleibt bedienbar (AC-4).

## Nachweis-Strategie

| AC | Schicht | Warum |
|---|---|---|
| AC-1, AC-2, AC-3, AC-5 | Kern (Vitest, Struktur/Datenfluss) | Zusicherung über Datenherkunft und Vorkommen in beiden Kontexten |
| AC-4 | Kern | Guard-Verhalten bei fehlender Quelle |
| **AC-6, AC-7** | **Live (Playwright, echter Browser)** | Sichtbarkeit bei 320–899 px und Kontrast sind per DOM-Abfrage nicht belegbar — Präzedenzfall #1446 |

Zusätzlich als Mutations-Gegenprobe vorzusehen: Legende naiv über `smsSymbols.metrics` speisen
(muss `CP` ohne Label erzeugen und rot werden, s. M1) sowie im Vergleichs-Kontext entdoppeln
(muss rot werden, s. M2).

## Auflösung der offenen Fragen

- **F1 — beantwortet:** `CP` wird nicht als Marke gerendert; Legende aus der gerenderten Menge
  speisen ⇒ **kein Backend-Anteil**, Scheibe bleibt reines Frontend.
- **F2 — beantwortet:** Beide Zeilen zeigen, `Kürzel — Label (Auswertung)`; die vorbestehende
  Doppelbelegung wird sichtbar gemacht, nicht behoben (eigenes Issue).
- **F3 — beantwortet:** Am Reihenfolge-Block, dem einzigen von beiden Kontexten geteilten Ort mit
  vollständiger Größen-Liste.

## Neue offene Frage an den PO

- [ ] **F4:** AC-2 gilt nach M3 nur für den Trip-Editor. Vorschlag: AC-2 ausdrücklich auf den
      Trip-Editor beziehen und für den Ortsvergleich ein eigenes, dort erfüllbares Kriterium
      formulieren (Kürzel + Größe + Auswertung sind ablesbar). Freigabe erfolgt mit der Spec.
