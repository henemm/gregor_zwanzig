---
entity_id: thunder_threshold_katalog
type: feature
created: 2026-08-20
updated: 2026-08-20
status: draft
version: "1.0"
tags: [thunder, compare, metrics, frontend, backend, ssot]
workflow: fix-1911-thunder-katalog
---

# Gewitter-Schwellenliste: Ableitung statt Doppel-Kopie (#1911)

## Approval

- [ ] Approved

## Purpose

Die Alarmschwellenliste (leicht/mittel/hoch) im Gewitter-Block des Wetter-Metriken-Reiters
(`WeatherMetricsTab.svelte`) ist heute ein hart codiertes Frontend-Literal. Sie soll stattdessen
aus dem Backend-Katalog abgeleitet werden. Der Backend-Katalog selbst
(`compare_metric_catalog.py::ordinalLabels`) ist dabei aber ebenfalls nur ein handgepflegtes
Literal — er muss zuerst seinerseits aus der kanonischen Stufenquelle `THUNDER_LABEL_DE`
abgeleitet werden, sonst wandert die Kopie lediglich vom Frontend ins Backend, statt zu
verschwinden. Beide Ableitungen zusammen schließen die Kette: kanonische Quelle →
Backend-Katalog → Frontend-Auswahlliste, mit genau einer Stelle, an der die vier Gewitter-Wörter
gepflegt werden.

## Source

- **File:** `src/output/renderers/compare_metric_catalog.py` (Backend-Ableitung),
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (Frontend-Verdrahtung)
- **Identifier:** `COMPARE_METRIC_CATALOG`-Eintrag `thunder_level_max` (`compare_metric_catalog.py:104-112`),
  Level-Literal `{ id: 'leicht'|'mittel'|'hoch', label, float }` (`WeatherMetricsTab.svelte:1634-1638`)

> Schicht-Hinweis: **Python-Core** (`src/output/renderers/compare_metric_catalog.py`,
> `src/output/metric_format.py`, `src/app/thunder_scale.py`) für die Backend-Ableitung;
> **Frontend** (`frontend/src/lib/components/shared/...`, SvelteKit) für Durchreichung und
> Verdrahtung. Kein Go-Touch — der Proxy ist reines Byte-Passthrough.

## Estimated Scope

- **LoC:** ~70-90 (siehe Betroffene Dateien) — unterhalb des 250-LoC-Limits, kein Override nötig.
- **Files:** 5 (4 MODIFY Frontend/Backend, 1 MODIFY Test)
- **Effort:** medium — nicht wegen Umfang, sondern wegen des Bestandsdaten-Risikos
  (gespeicherte `float`-Schwellen dürfen sich nicht um eine Stufe verschieben).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `THUNDER_LABEL_DE` (`src/output/metric_format.py:283-288`) | module | kanonische deutsche Beschriftung je `ThunderLevel` — neue Quelle für `ordinalLabels` |
| `thunder_ordinal()` (`src/app/thunder_scale.py:47-57`) | function | kanonische Sortier-/Zählreferenz für die Stufenreihenfolge, re-exportiert über `metric_format.py` |
| `GET /api/compare/metrics` (`api/routers/compare.py:11-24`) | backend endpoint | einziger Endpoint, der `ordinalLabels` trägt; Antwort bleibt wertgleich |
| `compareMetricSelection.ts::toCompareSelectionEntries` | frontend module | Mapper Endpoint-Antwort → `CompareSelectionEntry[]`, muss `ordinalLabels` künftig durchreichen |
| `compareMetricCatalogLoader.ts` | frontend module | Ladepfad + Promise-Cache für `compareCatalog`, bekommt neue Exportfunktion `deriveThunderThresholdLevels` |
| `ThresholdMetricRow.svelte` | frontend component | Verbraucher der `Level[]`-Form (`id`/`label`/`float`), unverändert |
| `email/helpers.py::sms_threshold_thunder`, `src/output/tokens/metrics.py:52` | module | Backend-Interpretation des gespeicherten `float`-Werts — Zielwerte 1.0/2.0/3.0 müssen exakt erhalten bleiben |

## Implementation Details

**1. Backend-Ableitung (`compare_metric_catalog.py:104-112`).** `ordinalLabels` wird nicht mehr
als Literal-Liste geschrieben, sondern aus `THUNDER_LABEL_DE` gebaut, sortiert über
`thunder_ordinal()` — nicht über die Dict-Einfügereihenfolge (impliziter, nicht erzwungener
Vertrag):

```
_THUNDER_ORDINAL_LABELS = [
    THUNDER_LABEL_DE[lvl] for lvl in sorted(ThunderLevel, key=thunder_ordinal)
]
```

Ergebnis bleibt exakt `["kein", "leicht", "mittel", "hoch"]` — die Endpoint-Antwort ändert sich
nicht, nur ihre Herkunft. Zyklenfrei: `metric_format.py` importiert nur aus `app.*`, nie aus
`output.renderers.*` (Präzedenz: `renderers/narrow.py:36`, `renderers/comparison.py:48`).

**2. Durchreichung (`compareMetricSelection.ts`).** `toCompareSelectionEntries()` reicht
`ordinalLabels` aus der Endpoint-Antwort in `CompareSelectionEntry` durch (additiv, Muster wie
`sms_code`) — heute geht die Information hier verloren, `compareCatalog` im Trip-Kontext trägt sie
noch nicht.

**3. Ableitungsfunktion (`compareMetricCatalogLoader.ts`).** Neue Exportfunktion
`deriveThunderThresholdLevels(ordinalLabels: string[]): Level[]`: verwirft Index 0 (die
Nullstufe `kein`), bildet die verbleibenden Einträge auf `{ id, label, float }` ab mit
`float = Ordinalindex` (1/2/3 für leicht/mittel/hoch) — wertgleich zum heutigen Literal. Reine,
testbare Funktion ohne Svelte-Import.

**4. Verdrahtung (`WeatherMetricsTab.svelte:1634-1638`).** Das Literal wird durch einen Aufruf von
`deriveThunderThresholdLevels(compareCatalog-Eintrag für thunder_level_max)` ersetzt. Solange
`compareCatalog` noch nicht geladen ist (`compareCatalogLoaded === false`) oder das Laden
fehlschlug (`compareCatalogError` gesetzt), rendert der Block einen definierten Leer-/
Fehlerzustand statt eine leere oder kaputte Liste zu zeigen — kein Absturz, keine unwählbare
Schwelle.

**Reihenfolge (kein deploybarer Zwischenzustand mit verschobenen Schwellen):**
1. Backend auf Ableitung umstellen (wertgleich, Frontend unberührt).
2. `ordinalLabels`-Durchreichung in `compareMetricSelection.ts` (additiv).
3. Ableitungsfunktion schreiben, vor der Verdrahtung gegen den umgebauten Test nachweisen, dass
   sie 1.0/2.0/3.0 liefert.
4. Erst dann `WeatherMetricsTab.svelte:1634-1638` umstellen.

## Expected Behavior

- **Input:** Öffnen des Gewitter-Schwellenreglers im Wetter-Metriken-Reiter (Trip- oder
  Compare-Kontext).
- **Output:** genau drei wählbare Stufen (leicht/mittel/hoch) mit denselben Labels und
  denselben `float`-Werten (1.0/2.0/3.0) wie vor der Umstellung; die Labels stammen aus dem
  Backend-Katalog, der seinerseits aus `THUNDER_LABEL_DE` abgeleitet ist.
- **Side effects:** keine neuen Netzwerk-Requests (nutzt den bereits vorhandenen
  `/api/compare/metrics`-Fetch/Cache); keine Änderung an gespeicherten Trip-Daten für
  unveränderte Nutzereingaben.

## Acceptance Criteria

- **AC-1:** Given der Gewitter-Schwellenregler im Wetter-Metriken-Reiter ist geladen / When die
  Optionsliste gerendert wird / Then zeigt sie genau drei Einträge (leicht/mittel/hoch) und die
  Nullstufe „kein" erscheint NICHT als wählbare Alarmschwelle.
  - Test: umgebauter `thunderThresholdLevels.test.ts` ruft `deriveThunderThresholdLevels()` mit
    der echten Vier-Stufen-Antwort auf und prüft Länge 3 sowie Abwesenheit von `kein`
    (Verhaltenstest der Ableitungsfunktion, kein Regex-Parsing des Frontend-Literals mehr).

- **AC-2:** Given ein Bestandstrip mit gespeicherter Alarmschwelle „hoch" (`float=3.0`) / When der
  Reiter nach der Umstellung neu geöffnet und die Schwelle unverändert gespeichert wird / Then
  bleibt der gespeicherte Zahlenwert exakt `3.0` — keine Verschiebung auf `2.0` oder einen anderen
  Wert; dieselbe Prüfung gilt analog für „leicht" (`1.0`) und „mittel" (`2.0`).
  - Test: Kern-Test ruft `deriveThunderThresholdLevels(["kein","leicht","mittel","hoch"])` auf und
    vergleicht die drei zurückgegebenen `float`-Werte Feld für Feld gegen `1.0`/`2.0`/`3.0`;
    ergänzt um einen Backend-Test, der `sms_threshold_thunder`/`src/output/tokens/metrics.py:52`
    mit denselben drei Werten gegen die heutige Interpretation absichert.

- **AC-3:** Given die Beschriftungen im Schwellenregler / When Backend und Frontend verglichen
  werden / Then stammen die drei Label-Texte nachweislich aus `THUNDER_LABEL_DE` und stehen an
  keiner Stelle mehr als eigenständiges Frontend-Literal im Quelltext von `WeatherMetricsTab.svelte`.
  - **Zulässige Abweichung: allein die Groß-/Kleinschreibung des Anfangsbuchstabens.** Der Katalog
    führt `leicht`/`mittel`/`hoch` klein, die Schaltflächen zeigen heute `Leicht`/`Mittel`/`Hoch`.
    Diese Anzeigeform bleibt unverändert — die Ableitung stellt den Anfangsbuchstaben groß. Der
    Vergleich erfolgt daher gegen die normalisierte Form; jede andere Abweichung ist ein Verstoß.
  - Test: `compareMetricCatalogParity.test.ts`-artiger Live-Read gegen `THUNDER_LABEL_DE`
    (`execFileSync('uv', …)`) plus statischer Nachweis (Test oder Grep-Assertion mit
    `# doc-compliance-test`-Kennzeichnung), dass das alte `{ id: 'leicht', label: 'Leicht', ... }`-
    Literal aus `WeatherMetricsTab.svelte` entfernt ist.

- **AC-4:** Given `src/output/renderers/compare_metric_catalog.py` / When der Eintrag
  `thunder_level_max` inspiziert wird / Then wird sein `ordinalLabels`-Feld aus `THUNDER_LABEL_DE`
  abgeleitet (nicht als Literal geschrieben) und die Antwort von `GET /api/compare/metrics` bleibt
  dabei wertgleich zu heute (`["kein", "leicht", "mittel", "hoch"]`).
  - Test: bestehender `test_compare_metric_catalog_endpoint.py` bleibt grün (Wertevergleich der
    Endpoint-Antwort); neuer Kern-Test importiert `THUNDER_LABEL_DE` und prüft, dass sich eine
    Änderung an `THUNDER_LABEL_DE` unmittelbar in `COMPARE_METRIC_CATALOG['thunder_level_max']
    ['ordinalLabels']` niederschlägt (Ableitungsnachweis, nicht nur Wertegleichheit).

- **AC-5:** Given die vier `ThunderLevel`-Werte in `THUNDER_LABEL_DE` / When die Reihenfolge der
  abgeleiteten `ordinalLabels` bestimmt wird / Then entsteht sie über `thunder_ordinal()`
  (NONE=0 < LOW=1 < MED=2 < HIGH=3), nicht über die Einfügereihenfolge des Dicts.
  - Test: Kern-Test baut eine `THUNDER_LABEL_DE`-Kopie mit absichtlich vertauschter
    Einfügereihenfolge und prüft, dass die Ableitung trotzdem die korrekte, über
    `thunder_ordinal()` sortierte Reihenfolge liefert.

- **AC-6:** Given eine fünfte, hypothetische Gewitterstufe würde `ThunderLevel`, `THUNDER_LABEL_DE`
  und `thunder_ordinal()` backendseitig hinzugefügt / When der Schwellenregler ohne jede
  Frontend-Codeänderung neu geladen wird / Then erscheint die neue Stufe automatisch in der
  Optionsliste (abzüglich der weiterhin verworfenen Nullstufe).
  - Test: Kern-Test ruft `deriveThunderThresholdLevels()` mit einer synthetischen
    Fünf-Stufen-Fixture (`["kein","leicht","mittel","hoch","extrem"]`) auf und prüft vier
    zurückgegebene Einträge mit `float`-Werten 1.0-4.0 — ohne Änderung an der
    Ableitungsfunktion selbst.

- **AC-7:** Given `compareCatalog` ist noch nicht geladen (`compareCatalogLoaded === false`) oder
  das Laden ist fehlgeschlagen (`compareCatalogError` gesetzt) / When der Wetter-Metriken-Reiter
  gerendert wird / Then wirft der Gewitter-Block keinen Laufzeitfehler und zeigt einen definierten
  Lade- bzw. Fehlerzustand statt einer leeren oder kaputten Optionsliste.
  - Test: Component-Test rendert `WeatherMetricsTab` mit `compareCatalogLoaded=false` bzw. mit
    gesetztem `compareCatalogError` und prüft Abwesenheit eines Exceptions/Absturzes sowie
    Präsenz des definierten Platzhalter-Testids.

## Nicht-Ziele

- Der generische Wächter gegen lokale Stufen-Kopien (Issue #1480) wird hier **nicht** gebaut —
  diese Spec liefert nur den gezielten Test für den Gewitter-Sonderfall, der breitere Wächter
  bleibt ein eigener, späterer Workflow.
- Das Aufräumen von totem Code (`TripEditView.svelte`, `AlertsPreviewCard.svelte`) gehört
  **nicht** in diesen Scope — es ist ein unabhängiger Nebenbefund, kein Teil der
  Katalog-Ableitung.
- Die sechs übrigen Metrik-Schwellenlisten in `WeatherMetricsTab.svelte` (wind, gust,
  precipitation, rain_probability, snow_depth, snowfall_limit) bleiben **unverändert** — sie sind
  keine Ordinal-Skalen mit Backend-`ordinalLabels` und daher nicht Teil dieser Ableitung.
- Keine Änderung am Persistenzformat des Trips (`sms_threshold`/`metric_alert_levels`) — nur die
  Herkunft der im UI angebotenen Auswahlwerte ändert sich, nicht ihr gespeichertes Format.

## Betroffene Dateien

| Datei | Typ | Beschreibung | LoC |
|---|---|---|---|
| `src/output/renderers/compare_metric_catalog.py` | MODIFY | Literal Z.111 → Ableitung aus `THUNDER_LABEL_DE` | +8/-3 |
| `frontend/src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts` | MODIFY | `ordinalLabels`-Durchreichung (Interface Z.7-30 + Mapping Z.60ff.) | +3 |
| `frontend/src/lib/components/shared/corridor-editor/compareMetricCatalogLoader.ts` | MODIFY | neue Exportfunktion `deriveThunderThresholdLevels` | +10 |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | MODIFY | Z.1634-1638 Literal → Funktionsaufruf inkl. Lade-/Fehlerzustand (AC-7) | +2/-5 |
| `frontend/.../__tests__/thunderThresholdLevels.test.ts` | MODIFY | Regex-Parsing → echte Funktion gegen Live-Backend-Antwort | +40/-60 |

## Testnachweis

Mutations-Gegenprobe (CLAUDE.md, Adversary Verification, Sektion „Mutations-Gegenprobe ist
PFLICHT"):

| Verfälschung | muss rot machen |
|---|---|
| Nullstufe nicht verworfen | umgebauter `thunderThresholdLevels.test.ts` — „genau 3 Stufen" (AC-1) |
| `float`-Offset um 1 verschoben | derselbe Test — Zuordnung Label↔float (AC-2) |
| Reihenfolge umgedreht | derselbe Test (AC-1/AC-5) |
| Backend-Ableitung wieder durch Literal ersetzt | 🔴 **kein bestehender Test fängt das heute** — `compareMetricCatalogParity.test.ts` vergleicht nur den *Wert* der Endpoint-Antwort, nicht ihre *Herkunft*. Dieser Test entsteht **neu** in der TDD-Phase dieser Spec (AC-4-Test: Änderung an `THUNDER_LABEL_DE` muss sich in der Katalog-Antwort niederschlagen) — ohne ihn driftet Befund B2 aus der Analyse lautlos erneut. |

## Known Limitations

- Der Backend-Katalog bleibt weiterhin die einzige Quelle für den Frontend-Reiter; fällt
  `GET /api/compare/metrics` dauerhaft aus, zeigt der Gewitter-Block den in AC-7 geforderten
  Fehlerzustand statt einer Auswahlliste — es gibt bewusst keinen stillen Fallback auf ein
  Frontend-Literal, das nach dieser Umstellung nicht mehr existiert.
- `WeatherMetricsTab.svelte` lädt `compareCatalog` bereits heute für andere Metriken; diese Spec
  fügt keinen zusätzlichen Request hinzu, sondern nutzt den bestehenden Ladepfad/Cache mit.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Ableitungs-/Wartbarkeitsänderung entlang einer bereits etablierten
  Migrationsrichtung (Backend-Katalog als autoritative Quelle für Compare-/Trip-Metrik-Präsentation,
  vgl. `docs/specs/modules/compare_metric_ssot_final.md`). Keine neue Entscheidungsfläche (Kanäle,
  Provider, Datenmodell, Auth, Editor-Paradigma, Test-/Deploy-Strategie) — das Persistenzformat der
  gespeicherten Schwellen bleibt unverändert (AC-2).

## Changelog

- 2026-08-20: Initial spec created (Issue #1911, Frontend- + Backend-Ableitung der
  Gewitter-Schwellenliste)
