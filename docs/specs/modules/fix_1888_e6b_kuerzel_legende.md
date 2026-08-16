---
entity_id: fix_1888_e6b_kuerzel_legende
type: feature
created: 2026-08-16
updated: 2026-08-16
status: approved
version: "1.1"
tags: [frontend, weather-metrics-tab, sms, legende, compare, trip]
workflow: fix-1888-e6b-kuerzel-legende
---

# Fix #1888 — Etappe E6 Scheibe B: Legende für SMS-Kürzel im Reiter „Wetter-Metriken"

## Approval

- [x] Approved — PO, 2026-08-16 („go"). Freigegeben wurde ausdrücklich auch
  die Teilung von AC-2 (Trip-Editor) und AC-2a (Ortsvergleich) gegenüber dem
  Ticket-Text, begründet durch Messung M3 im Kontext-Dokument.

## Purpose

Der Reiter „Wetter-Metriken" zeigt SMS-Kürzel (`K`, `D`, `FK`, `FD`, `N`, `FN`, …)
neben jeder Größe an, erklärt aber nirgends, was sie bedeuten. Diese Scheibe
ergänzt eine Legende, die Kürzel und Bedeutung aus **derselben Quelle wie die
Marken selbst** bezieht — als **ein** geteilter Baustein für Trip- **und**
Ortsvergleich-Editor, nach dem Vorbild der bereits arbeitenden Legende für
amtliche Warnungen im selben Reiter (`officialAlertsToggle`,
`WeatherMetricsTab.svelte:1210-1224`).

## Source

- **File:** `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`
- **Identifier:** Snippet `officialAlertsToggle` (`:1189-1226`, Vorbild-Legende
  `:1210-1224`); Reihenfolge-Block route (`:1479-1507`, `<LayoutTab context="route">`);
  Reihenfolge-Block vergleich (`:1313-1344`, `<LayoutTab context="vergleich">`)

> **Schicht-Hinweis:** ausschließlich Frontend (SvelteKit). Kein Go-API-, kein
> Python-Core-Anteil — Messung M1 (Kontext-Dokument) belegt, dass
> `/api/sms-symbols` NICHT um ein `label`-Feld erweitert werden muss, weil die
> einzige Lücke (`cape`/`CP`) im Reiter nie als Marke gerendert wird und die
> Legende deshalb aus der Menge der **gerenderten** Größen gespeist wird, nicht
> aus dem rohen Kürzel-Katalog.

## Estimated Scope

- **LoC:** ~40–80 Produktivcode (ein Snippet + zwei Aufrufstellen in derselben
  Datei), ~120–180 Testcode (Vitest-Struktur für AC-1–AC-5 + Playwright für
  AC-6/AC-7).
- **Files:** 1 Produktivdatei geändert (`WeatherMetricsTab.svelte`), 0 neu;
  ~2–3 Testdateien (1 Vitest-Struktur-/Datenfluss-Test, 1 Playwright-Test
  gegen Staging, optional Erweiterung des bestehenden Sichtbarkeits-Tests).
- **Effort:** low–medium. Der Produktivcode-Kern ist klein und additiv
  (fail-soft, kein neuer State, keine neue Ladelogik); der Aufwand liegt im
  Nachweis für zwei Kontexte mit unterschiedlichem Kürzel-Vokabular und in
  der Live-Schicht für Sichtbarkeit/Kontrast. **Erfahrungswert (R5/#1446):
  der Nachweis kostet mehr als der Mechanismus** — beim 250-Zeilen-LoC-Limit
  des Workflows das Testbudget doppelt ansetzen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherMetricsTab.svelte::metricSymbols` (`:182-186`) | READ (unverändert) | Kürzel-Quelle für Kontext `route`, aus `/api/sms-symbols` |
| `WeatherMetricsTab.svelte::metricById` (`:331-335`) | READ (unverändert) | Bedeutungs-Quelle für Kontext `route`, Feld `label` aus `/api/metrics` |
| `WeatherMetricsTab.svelte::compareKuerzelById` (`:1102-1106`) | READ (unverändert) | Kürzel-Quelle für Kontext `vergleich`, aus `/api/compare/metrics` |
| `WeatherMetricsTab.svelte::compareMetricById` (`:1082-1096`) | READ (unverändert) | Bedeutungs-Quelle für Kontext `vergleich`, Felder `label` + `aggregation_label` |
| `LayoutTab context="route"` Reihenfolge-Block (`:1479-1507`) | MODIFY (additiv) | Einbindungsort route — einzige Stelle mit vollständiger Größen-Liste (inkl. abgewählter) |
| `LayoutTab context="vergleich"` Reihenfolge-Block (`:1313-1344`) | MODIFY (additiv) | Einbindungsort vergleich, analog |
| `officialAlertLegend.test.ts::AC-9 „keine zweite Liste"` (`:365-425`) | READ (Wächter, muss grün bleiben) | Verbündeter gegen eine handgetippte Kürzel-Zuordnung im Frontend |
| `/api/sms-symbols`, `/api/metrics`, `/api/compare/metrics` | READ (unverändert) | alle drei werden von der Zielkomponente heute bereits geladen — keine neue Ladelogik nötig |
| `src/output/renderers/comparison.py:647-650` (`_sms_aggregation_sign`) | READ (unverändert, Python-Core) | erklärt, warum die zugestellte Vergleichs-SMS trotz doppeltem `sms_code` eindeutig ist (M2b) — kein Anteil dieser Scheibe, nur Kontext für die Legenden-Darstellung |

## Implementation Details

### Ein Baustein, zwei Speisungen

Die Legende entsteht als **ein** Svelte-Snippet in `WeatherMetricsTab.svelte`
— der Datei, die beide Kontexte bereits teilen und die alle sieben
Mount-Punkte versorgt (`TripNewEditor` 2×, `TripEditView`, `TripTabs`,
`CompareTabs` 2×, `CompareNewEditor` 2×). Kein neuer Endpunkt, keine neue
Ladelogik, keine zweite Liste im Frontend.

Gespeist wird sie je Kontext aus dem Paar, das im selben Scope **bereits**
nebeneinanderliegt und schon heute gemeinsam an den jeweiligen
Reihenfolge-Block gereicht wird (Prop `kuerzelById`, `:1502` route /
`:1339` vergleich):

| Kontext | Kürzel-Quelle | Bedeutungs-Quelle | Darstellung |
|---|---|---|---|
| `route` | `metricSymbols` (`:182-186`) | `metricById[...].label` (`:331-335`) | `Kürzel — Label` |
| `vergleich` | `compareKuerzelById` (`:1102-1106`) | `compareMetricById[...].label` + `.aggregation_label` (`:1082-1096`) | `Kürzel — Label (Auswertung)` |

Der Datenfluss iteriert je Kontext über die **gerenderten** Größen der
Reihenfolge-Liste (route: `Object.values(catalog)` bzw. die dort bereits
aufbereitete Metrik-Menge; vergleich: `compareCatalog`) — **nicht** über den
rohen `smsSymbols.metrics`-Katalog. Das ist die entscheidende Zusicherung
aus M1: `cape` (Kürzel `CP`, `selectable=False`) steht zwar in
`smsSymbols.metrics`, wird aber nirgends im Reiter als Marke gerendert
(`/api/metrics` filtert `selectable=true`). Eine Legende, die naiv über
`smsSymbols.metrics` iteriert, erzeugt einen Eintrag `CP` ohne Bedeutung —
das ist die zu vermeidende Umsetzung (s. „Mutations-Gegenprobe").

### Platzierung

Unmittelbar am **Reihenfolge-Block** (`:1479-1507` route, `:1313-1344`
vergleich), analog zur Warnungs-Legende im selben Snippet-Muster. Begründung:
es ist der einzige Block, den beide Kontexte teilen, er zeigt **alle**
Größen inklusive der abgewählten (Aus-Gruppe,
`WeatherV2Reihenfolge.svelte:174-178`), und er erhält `kuerzelById` bereits
als Prop. Die zusätzlichen Marken in „04 — Schwellwerte" (nur `route`) sind
eine Teilmenge und werden von derselben Legende miterklärt.

### Fail-soft

Muster der Warnungs-Legende (`{#if smsSymbols}` ohne Kontext-Guard,
`:1210-1224`): Guard nur auf die geladenen Daten der jeweiligen Quelle
(`route`: `metricSymbols`/`metricById` vorhanden; `vergleich`:
`compareKuerzelById`/`compareMetricById` vorhanden). **Kein**
`{#if context === ...}`-Guard — fehlt die Quelle, entfällt die Legende
still, der Reiter bleibt bedienbar.

### Doppelte Kürzel im Ortsvergleich — bewusst NICHT entdoppeln

Gemessen (M2, Kontext-Dokument): 25 Compare-Zeilen, 23 verschiedene Kürzel.
`D` steht auf zwei Zeilen (`temp_max_c`/„Maximum" und `temp_min_c`/„Minimum"),
`TF` ebenso (`wind_chill_min_c`/„Minimum" und `wind_chill_max_c`/„Maximum").
Die Legende zeigt im Kontext `vergleich` **beide** Zeilen in der Form
`Kürzel — Label (Auswertung)`:

```
D   Temperatur (Maximum)
D   Temperatur (Minimum)
```

Das ist die einzige Variante, die die Zusicherung „dieselbe Quelle wie die
Marken" einhält — die Marken zeigen das Kürzel tatsächlich an beiden Zeilen
(rohes `sms_code`, ohne Auswertungszeichen; s. `compareKuerzelById`,
`:1102-1106`). Eine Entdopplung nach Kürzel würde diese Zusicherung brechen.

**Nachmessung M2b (Kontext-Dokument):** Die vorbestehende Doppelbelegung des
rohen `sms_code` ist **kein Defekt der zugestellten Ausgabe**. Die
Vergleichs-SMS hängt in `src/output/renderers/comparison.py:647-650` ein
Auswertungszeichen an (`code = f"{code}{_sms_aggregation_sign(metric_id)}"`)
— Temperatur-Maximum wird `D+`, Minimum `D-`. Die zugestellte SMS ist damit
eindeutig; die Doppelbelegung ist ein Merkmal des rohen Katalogfeldes, kein
nutzersichtbarer Fehler. **Kein eigenes Issue** aus diesem Grund (Korrektur
gegenüber einer früheren Einschätzung dieser Scheibe).

Die Legende bildet bewusst das **Editor-Vokabular** ab, nicht das
SMS-Vokabular: sie zeigt das Kürzel **ohne** `+`/`-` — genauso, wie die
Marken es im Editor tun. Die Eindeutigkeit stellt dort die mitgezeigte
Auswertung her (`D — Temperatur (Maximum)` vs. `D — Temperatur (Minimum)`),
nicht das Vorzeichen. Diese Lücke zwischen Editor-Anzeige (`D`) und
zugestellter SMS (`D+`/`D-`) betrifft die **Marken**, nicht die Legende, und
wird in dieser Scheibe nicht angefasst (s. „Bewusste Grenzen").

## Expected Behavior

- **Input:** Ein Nutzer öffnet den Reiter „Wetter-Metriken" im Trip-Editor
  oder im Ortsvergleich-Editor, mit mindestens einer aktivierten
  SMS-kürzeltragenden Größe.
- **Output:** Am Reihenfolge-Block erscheint eine Legende, die zu jeder
  dort gelisteten Größe (inklusive abgewählter) ihr Kürzel und ihre
  Bedeutung nennt — im Trip-Kontext `Kürzel — Label`, im
  Ortsvergleich-Kontext `Kürzel — Label (Auswertung)`. Für Größen ohne
  Kürzel entsteht kein Eintrag. Die Legende erscheint in **beiden**
  Kontexten mit demselben Markup, aber je kontexteigenem Inhalt.
- **Side effects:** Keine — reine Anzeige, kein Schreibpfad, keine
  Persistenz, kein neuer Netzwerk-Call. Fehlt die Quelle (Ladefehler,
  Katalog leer), entfällt die Legende still.

## Acceptance Criteria

- **AC-1:** Given der Reiter „Wetter-Metriken" im Trip- oder
  Ortsvergleich-Editor mit geladenem Metrik-Katalog / When der Nutzer den
  Reiter öffnet / Then zeigt eine Legende am Reihenfolge-Block zu jeder dort
  gerenderten kürzeltragenden Größe ihr Kürzel und ihre Bedeutung im Klartext
  an — keine Marke ohne zugehörigen Erklärtext bleibt unerklärt stehen.
  - Test: Vitest-Struktur-/Datenfluss-Test prüft, dass jedes Kürzel aus
    `metricSymbols`/`compareKuerzelById`, das tatsächlich im
    Reihenfolge-Block landet, in der Legende mit einem nichtleeren Label
    erscheint (`weather_metric_kuerzel_marken.test.ts`-Muster).

- **AC-2:** Given im Trip-Editor die drei Kürzel-Paare `K`/`D`/`N` und
  `FK`/`FD`/`FN` / When der Nutzer die Legende liest / Then
  erkennt er anhand der Klartext-Bedeutungen (z. B. „Tages-Tiefsttemperatur
  (Gehzeit)" für `K`, „Gefühlte Tages-Tiefsttemperatur (Gehzeit)" für `FK`),
  dass `FK`/`FD`/`FN` dieselben drei Größen wie `K`/`D`/`N` in gefühlter
  statt gemessener Form bezeichnen. **Diese Zusicherung gilt ausschließlich
  für den Trip-Editor** — die Größen `temperature_night`/`_day_low`/`_day_high`
  und `wind_chill_night`/`_day_low`/`_day_high` existieren strukturell nur im
  Trip-Katalog (Messung M3, Kontext-Dokument); der Compare-Katalog kennt
  stattdessen `temp_min_c`/`temp_max_c`/`wind_chill_min_c`/`wind_chill_max_c`
  mit den Kürzeln `D`/`TF`. Ein entsprechendes Kriterium für den
  Ortsvergleich steht in AC-2a.
  - Test: Vitest-Test lädt die sechs Register-Labels aus `metricById` für
    genau diese sechs `metric_id`s und prüft, dass die Legende sie allen
    sechs zugehörigen Kürzeln zuordnet (Muster:
    `weather_metric_kuerzel_marken.test.ts:381-400`).

- **AC-2a:** Given der Ortsvergleich-Editor mit den Kürzeln
  `D` (zwei Zeilen: Maximum/Minimum) und `TF` (zwei Zeilen: Minimum/Maximum)
  / When der Nutzer die Legende liest / Then sind Kürzel, Größenname
  (`label`) und Auswertung (`aggregation_label`) für jede der vier Zeilen
  gemeinsam ablesbar — die Legende entdoppelt nicht nach Kürzel, sondern
  zeigt beide Zeilen getrennt (`D — Temperatur (Maximum)` und
  `D — Temperatur (Minimum)`), und zeigt das Kürzel dabei ohne
  Auswertungszeichen (`D`, nicht `D+`/`D-`) — deckungsgleich mit der
  Darstellung der Marken im selben Editor (s. M2b).
  - Test: Vitest-Test prüft für den Kontext `vergleich`, dass die Legende
    für `D` und `TF` je zwei Einträge mit unterschiedlicher Auswertung
    enthält (nicht einen entdoppelten) und dass kein Eintrag ein
    Auswertungszeichen (`+`/`-`) am Kürzel trägt.

- **AC-3:** Given die Kürzel-Legende in beiden Kontexten / When ihre
  Datenquelle geprüft wird / Then bezieht sie Kürzel UND Bedeutung
  ausschließlich aus denselben Katalog-Objekten, die auch die Marken am
  Reihenfolge-Block speisen (`metricSymbols`/`metricById` bzw.
  `compareKuerzelById`/`compareMetricById`) — keine zweite, im Frontend
  hartkodierte Zuordnung.
  - Test: der bestehende Wächter `officialAlertLegend.test.ts:365-425`
    („keine zweite Liste") bleibt grün, ohne angepasst zu werden; ergänzend
    ein spezifischer Test, dass die neue Legende keinen Kürzel-String-Literal
    außerhalb der beiden genannten Katalog-Objekte referenziert.

- **AC-4:** Given eine der beiden Datenquellen (`metricSymbols`/`metricById`
  bzw. `compareKuerzelById`/`compareMetricById`) ist nicht geladen (Ladefehler
  oder leerer Katalog) / When der Reiter gerendert wird / Then entfällt die
  Legende für den betroffenen Kontext still, ohne Fehlermeldung und ohne den
  Reiter unbedienbar zu machen — analog zum Guard-Verhalten der
  Warnungs-Legende (`{#if smsSymbols}`, kein Kontext-Guard).
  - Test: Vitest-Test setzt die jeweilige Quelle auf `null`/leer und prüft,
    dass kein Legenden-Markup gerendert wird, während der übrige Reiter
    (Reihenfolge-Block selbst) weiterhin erscheint.

- **AC-5:** Given die Legende ist als ein Snippet in `WeatherMetricsTab.svelte`
  implementiert / When sie in beiden Kontexten (`route` und `vergleich`)
  aufgerufen wird / Then teilen sich beide Aufrufstellen dasselbe Markup und
  denselben Rendering-Code — es gibt keine zweite, kontexteigene
  Legenden-Komponente oder -Implementierung.
  - Test: Vitest-Test prüft strukturell (AST oder Quelltext-Scan), dass genau
    ein Legenden-Snippet definiert und an beiden Reihenfolge-Blöcken
    referenziert wird (Muster: `officialAlertLegend.test.ts:213-292`,
    „Legende in beiden Kontexten").

- **AC-6:** Given ein Bildschirm zwischen 320 px und 899 px Breite (Handy)
  / When der Nutzer die Legende am Reihenfolge-Block aufruft / Then ist der
  vollständige Legenden-Text jeder Zeile lesbar, ohne dass Kürzel oder
  Bedeutung durch Layout-Überlauf, `display:none` oder horizontales
  Abschneiden verdeckt werden.
  - Test: **Playwright gegen Staging**, echter Browser bei Viewport-Breiten
    zwischen 320 px und 899 px — DOM-Sichtbarkeit ist per Quelltext-Scan
    nicht belegbar (Präzedenzfall #1446: eine Tabelle mit `display:none`
    meldet per DOM-Abfrage fälschlich „sichtbar"). Muster:
    `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`.

- **AC-7:** Given die Legenden-Zeilen (Kürzel + Bedeutung) / When ihr
  Text-Hintergrund-Kontrast gemessen wird / Then liegt er bei mindestens
  WCAG-AA 4.5:1 — `--g-ink-4` darf für Kürzel, Labels oder Auswertung nicht
  verwendet werden (Design-Leitprinzip, nur für Placeholder/Disabled
  zulässig).
  - Test: **Playwright gegen Staging**, echter Browser mit
    Kontrast-Berechnung aus berechneten Style-Werten (`getComputedStyle`)
    an den gerenderten Legenden-Zeilen. Auch dieser Nachweis ist im Kern
    (Vitest, kein DOM) nicht führbar.

## Known Limitations

- **Die rohe Kürzel-Doppelbelegung im Ortsvergleich (`D`/`TF`, s. M2)
  bleibt bestehen und wird nicht angefasst.** Gemessen (M2b) unschädlich
  für die Zustellung — die Vergleichs-SMS hängt ein Auswertungszeichen an
  (`comparison.py:647-650`) und ist eindeutig. Die Legende zeigt beide
  Zeilen mit Auswertung, macht die Doppelbelegung des Katalogfelds damit
  sichtbar, ohne dass darin ein zu behebender Fehler steckt.
- **Lücke zwischen Marken-Anzeige und zugestellter SMS im Ortsvergleich
  (neuer Nebenbefund, außerhalb dieser Scheibe):** Die Marken am
  Reihenfolge-Block zeigen den rohen `sms_code` ohne Auswertungszeichen
  (`compareKuerzelById`, `WeatherMetricsTab.svelte:1102-1106`) — der Nutzer
  liest im Editor `D`, in seiner zugestellten SMS aber `D+`/`D-`. Betrifft
  die Marken, nicht die neue Legende (die dasselbe Vokabular abbildet).
  Einordnung nach Nebenbefund-Triage: Sammel-Eintrag in #1199 nach der
  Auslieferung dieser Scheibe, kein eigenes Issue, nicht Teil dieses Scopes.
- **`cape`/`CP` bleibt ohne Legenden-Eintrag**, weil die Größe im Reiter
  nirgends als Marke gerendert wird (`selectable=False`, gefiltert durch
  `/api/metrics`). Das ist gewollt (M1), keine Lücke.
- **AC-6 und AC-7 sind nur gegen den Zielstand nach Merge (Staging) belegbar**
  — vor Push existiert keine URL, gegen die Playwright laufen kann.

## Zu messen, nicht zu raten

Diese Spec übernimmt die Messungen M1–M3 und die Nachmessung M2b aus
`docs/context/fix-1888-e6b-kuerzel-legende.md` unverändert. Vor der
RED-Phase erneut zu verifizieren, nicht blind zu übernehmen:

1. **`CP`-Nichtvorkommen (M1):** erneut per `grep -n "cape\|CP"` gegen den
   dann aktuellen Stand von `WeatherMetricsTab.svelte` und
   `weather-metrics-tab/*` prüfen — sollte zwischenzeitlich doch eine
   `CP`-Marke gerendert werden, ist die Legenden-Quelle entsprechend zu
   erweitern (Backend-Ergänzung, s. R4 im Kontext-Dokument), nicht diese
   Spec blind umzusetzen.
2. **Kürzel-Kardinalität im Ortsvergleich (M2):** erneut gegen
   `get_compare_metric_catalog()` auszählen, ob weiterhin genau `D` und `TF`
   doppelt vorkommen und keine dritte Kollision hinzugekommen ist.
3. **Kürzel-Trennschärfe Trip/Vergleich (M3):** erneut prüfen, dass
   `N/K/D/FN/FK/FD` weiterhin ausschließlich im Trip-Katalog existieren und
   im Compare-Katalog nicht vorkommen — sonst wäre AC-2a hinfällig und AC-2
   müsste neu gefasst werden.
4. **Auswertungszeichen in der zugestellten SMS (M2b):** erneut prüfen,
   dass `comparison.py` weiterhin ein Auswertungszeichen an `sms_code`
   anhängt, bevor „die zugestellte Ausgabe ist eindeutig" als Begründung für
   „Legende zeigt beide Zeilen, aber ohne eigenes Issue" trägt.

## Bewusste Grenzen

- **Kein Backend-Anteil.** `/api/sms-symbols` wird nicht um ein `label`-Feld
  erweitert (anders als in R4 des Kontext-Dokuments erwogen) — Messung M1
  zeigt, dass die einzige Lücke (`CP`) folgenlos bleibt, solange die Legende
  aus den gerenderten Größen statt aus dem rohen Kürzel-Katalog speist.
- **Keine Entdopplung der Ortsvergleich-Kürzel.** Bewusste Entscheidung
  (M2/F2) — Entdopplung würde die Zusicherung „gleiche Quelle wie die
  Marken" brechen. Die rohe Doppelbelegung des Katalogfelds `sms_code`
  bleibt unangetastet — gemessen unschädlich für die zugestellte Ausgabe
  (M2b), kein eigenes Issue.
- **Kein Angleich der Marken-Anzeige an die zugestellte SMS.** Die Lücke
  „Editor zeigt `D`, SMS zeigt `D+`/`D-`" ist ein eigenständiger, in dieser
  Scheibe nicht zu behebender Befund (s. „Known Limitations").
- **Keine zweite Legende bei „04 — Schwellwerte".** Nur der
  Reihenfolge-Block bekommt die Legende — er ist der einzige von beiden
  Kontexten geteilte Ort mit vollständiger Größen-Liste; „04 — Schwellwerte"
  existiert nur im Trip-Kontext und zeigt eine Teilmenge, die von derselben
  Legende bereits miterklärt wird.
- **Register- und Katalog-Änderungen sind Scheibe A (#1887), bereits
  gemerged.** Diese Scheibe fasst `metric_catalog.py` und verwandte
  Python-Dateien nicht an.

## Mutations-Gegenprobe

Für jede neu bewachte Zusicherung mindestens eine gezielte Verfälschung, die
ein Test fangen MUSS:

1. **AC-1/AC-3:** Legende testweise über den rohen `smsSymbols.metrics`
   speisen statt über die gerenderten Größen (`metricById`/`compareCatalog`)
   → muss einen Legenden-Eintrag `CP` ohne zugehöriges Label erzeugen; der
   AC-1-Test (jedes Kürzel hat ein nichtleeres Label) muss rot werden.
2. **AC-2a:** Im Vergleichs-Kontext nach Kürzel entdoppeln (nur einen
   `D`-Eintrag statt zwei rendern) → der AC-2a-Test (zwei Zeilen für `D` mit
   unterschiedlicher Auswertung) muss rot werden.
3. **AC-5:** Eine zweite, kontexteigene Legenden-Implementierung im
   `vergleich`-Zweig einfügen (Copy-Paste statt Wiederverwendung des
   Snippets) → der AC-5-Struktur-Test (genau ein Snippet, zweimal
   referenziert) muss rot werden.
4. **AC-4:** Den Fail-soft-Guard entfernen (Legende ohne `{#if}` immer
   rendern) → der AC-4-Test (Legende entfällt bei fehlender Quelle) muss rot
   werden, weil dann auch bei leerer Quelle ein (leeres/fehlerhaftes)
   Legenden-Markup erscheint.

## Betroffene Tests

**Kern (Vitest, deterministisch) — AC-1 bis AC-5:**

- `frontend/src/lib/components/shared/__tests__/weather_metric_kuerzel_legende.test.ts`
  (neu) — Struktur- und Datenfluss-Test nach dem Muster von
  `weather_metric_kuerzel_marken.test.ts:381-400,443-490`: prüft AC-1
  (jedes gerenderte Kürzel hat ein Label), AC-2/AC-2a (Trip-Sechsergruppe
  bzw. Vergleichs-Doppelzeilen ohne Auswertungszeichen), AC-3 (Quelle =
  Marken-Quelle, kein Literal), AC-4 (Fail-soft-Guard), AC-5 (ein Snippet,
  zwei Aufrufstellen).
- `frontend/src/lib/components/shared/__tests__/officialAlertLegend.test.ts:365-425`
  (bestehend, unverändert) — „keine zweite Liste"-Wächter muss grün bleiben;
  ergänzend eine analoge Prüfung für die neue Legende in derselben oder
  einer neuen Testdatei, falls der bestehende Scanner die neue Legende nicht
  automatisch mit abdeckt (in der RED-Phase am Code zu verifizieren, nicht
  hier zu behaupten).

**Live (Playwright, echter Browser gegen Staging) — AC-6, AC-7:**

- `frontend/e2e/kuerzel-legende-lesbar.staging.spec.ts` (neu, Muster:
  `frontend/e2e/kuerzel-marken-sichtbar.staging.spec.ts`) — Viewport
  320–899 px, vollständige Sichtbarkeit der Legenden-Zeilen (AC-6);
  Kontrast-Berechnung an den gerenderten Legenden-Zeilen gegen WCAG-AA
  4.5:1, `--g-ink-4` ausgeschlossen (AC-7).

**Regression:**

- `frontend/e2e/weather-metrics-editor-day-range-kuerzel.spec.ts:110-135` —
  bestehender Kürzel-Badge-Test in „04 — Schwellwerte" muss unverändert
  grün bleiben (additive Änderung darf ihn nicht berühren).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Kein neuer Architektur-Grundsatz. Die Wiederverwendung
  eines geteilten Snippets für Trip- und Ortsvergleich-Editor folgt der
  bestehenden, PO-bekräftigten Trip/Ortsvergleich-Code-Teilung
  (`CLAUDE.md`, Epic #1230) und dem bereits etablierten Muster der
  Warnungs-Legende — keine Abweichung, kein neues ADR nötig.

## Changelog

- 2026-08-16: Initial spec created. Übernimmt Messungen M1–M3 und die
  Auflösung von F1–F3 aus `docs/context/fix-1888-e6b-kuerzel-legende.md`
  unverändert. AC-2 auf den Trip-Editor präzisiert (Messung M3 zeigt
  strukturelle Nichterfüllbarkeit im Ortsvergleich), AC-2a neu als
  eigenständiges, im Ortsvergleich erfüllbares Kriterium ergänzt.
- 2026-08-16 (Korrektur nach Nachmessung M2b): Frühere Fassung hatte die
  Kürzel-Doppelbelegung im Ortsvergleich als „nutzersichtbar falsch" und
  eigenes Issue wert eingestuft. Widerlegt durch Nachmessung in
  `src/output/renderers/comparison.py:647-650` — die zugestellte
  Vergleichs-SMS hängt ein Auswertungszeichen an (`D+`/`D-`) und ist
  eindeutig; die Doppelbelegung ist ein Merkmal des rohen Katalogfelds, kein
  Defekt der Ausgabe. Entsprechend angepasst: kein eigenes Issue mehr in
  „Betroffene Tests"/Implementation Details; AC-2a und die Legenden-Regel
  präzisiert (Kürzel ohne Auswertungszeichen, wie die Marken); neuer
  Nebenbefund „Lücke zwischen Marken-Anzeige und zugestellter SMS" als
  Sammel-Eintrag (#1199, nach Auslieferung) statt eigenem Issue in „Known
  Limitations"/„Bewusste Grenzen" ergänzt.
