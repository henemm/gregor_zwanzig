---
entity_id: compare_forecast_horizon
type: module
created: 2026-07-18
updated: 2026-07-18
status: draft
version: "1.0"
tags: [compare, forecast, horizon, email]
---

<!-- Issue #1305 — Scheibe A4 von Epic #1301 -->

# Compare Forecast Horizon (A4 — „Horizont ehrlich")

## Approval

- [ ] Approved

## Purpose

Der Ortsvergleich holt seit A2 (#1303) alle Wetterdaten über OpenMeteo (bis zu
15 Tage im Voraus), fordert aber Versand und Vorschau weiterhin fest mit
`forecast_hours=48` an. A4 hebt diesen Horizont auf **96 Stunden (4 Tage)** an
— synchron über eine geteilte Konstante, damit Versand und Vorschau nie
auseinanderlaufen können (Fehlerklasse #1297). Die hartkodierte Kopf-Kachel
`"+48h"` in der Vergleichs-Mail entfällt ersatzlos, weil sie den neuen Wert
nicht mehr korrekt abbilden würde und (analog #1268) keinen Informationswert
für den Nutzer hat.

## Source

- **File:** `src/services/comparison_engine.py` — neue Modul-Konstante
  `COMPARE_FORECAST_HOURS = 96`, Defaults `ComparisonEngine.run` und
  `fetch_forecast_for_location` beziehen sich darauf
- **Identifier:** `COMPARE_FORECAST_HOURS`, `ComparisonEngine.run`,
  `fetch_forecast_for_location`

## Estimated Scope

- **LoC:** ~40-60 (Konstante + 4 Bezugsstellen + Kachel-Entfall + 4 Testdateien)
- **Files:** 5 Quelldateien, 4 Testdateien
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/scheduler_dispatch_service.py:351` | intern | Versandpfad — `forecast_hours=48` fest, wird auf `COMPARE_FORECAST_HOURS` umgestellt |
| `src/services/compare_preview_service.py:152` | intern | Vorschaupfad — `forecast_hours=48` fest, Kommentar `:141-147` verlangt Gleichheit mit Versand; wird ebenfalls auf `COMPARE_FORECAST_HOURS` umgestellt |
| `src/services/comparison_engine.py:45` | intern | Default `forecast_hours: int = 48` in `ComparisonEngine.run` → `COMPARE_FORECAST_HOURS` |
| `src/services/comparison_engine.py:308` | intern | Default `hours: int = 48` in `fetch_forecast_for_location` → `COMPARE_FORECAST_HOURS` |
| `src/output/renderers/email/compare_html.py:686` | intern | `horizont_val = "+48h"` — Kachel entfällt, Desktop-Tabelle 4→3 Zellen, Mobile-Zeile 2 nur noch „Erstellt" |
| `src/providers/openmeteo.py:156` | intern | `OPENMETEO_MAX_FORECAST_DAYS = 15` — API-Obergrenze, 96 h bleibt weit darunter, kein Konflikt |
| `src/services/forecast.py` (`ForecastService.get_forecast`) | intern | `end = now + timedelta(hours=hours_ahead)` — Stunden werden 1:1 zum Abruffenster, unverändert |

## Implementation Details

```python
# src/services/comparison_engine.py

# Issue #1305 (Scheibe A4 von Epic #1301): Vorhersagehorizont fuer den
# Ortsvergleich. Seit A2 (#1303) liefert OpenMeteo bis zu
# OPENMETEO_MAX_FORECAST_DAYS=15 Tage; 96h (4 Tage) deckt den spaeteren
# 3-Tage-Ausblick (Scheibe B4) ab und bleibt weit unter der API-Grenze.
# EINE Konstante fuer Versand + Vorschau + beide Engine-Defaults verhindert
# Drift zwischen den Pfaden (Fehlerklasse #1297).
COMPARE_FORECAST_HOURS = 96


class ComparisonEngine:
    @staticmethod
    def run(
        locations: List[SavedLocation],
        time_window: tuple[int, int],
        target_date: "date",
        forecast_hours: int = COMPARE_FORECAST_HOURS,
        ...
    ) -> ComparisonResult:
        ...


def fetch_forecast_for_location(
    loc: SavedLocation,
    hours: int = COMPARE_FORECAST_HOURS,
    settings: Optional["Settings"] = None,
) -> Dict[str, Any]:
    ...
```

```python
# src/services/scheduler_dispatch_service.py (Versand, um Zeile 351)
from services.comparison_engine import COMPARE_FORECAST_HOURS
...
result = ComparisonEngine.run(
    locations=locations,
    time_window=(0, 23),
    target_date=target_date,
    forecast_hours=COMPARE_FORECAST_HOURS,  # Issue #1305: geteilte Konstante statt 48 fest
    ...
)
```

```python
# src/services/compare_preview_service.py (Vorschau, um Zeile 152)
# Issue #1305 (ex #1268 AC-11): Vorschau MUSS denselben Horizont anfordern
# wie der echte Versand (scheduler_dispatch_service.py). Der geteilte Bezug
# auf COMPARE_FORECAST_HOURS ersetzt den bisherigen Kommentar-Appell durch
# Struktur — Divergenz ist strukturell ausgeschlossen (#1297).
result = ComparisonEngine.run(
    locations=locations,
    time_window=(0, 23),
    target_date=resolved_date,
    forecast_hours=COMPARE_FORECAST_HOURS,
    ...
)
```

```python
# src/output/renderers/email/compare_html.py (Kopf-Kachel, um Zeile 684-717)
profil_val = _html.escape(sig.eyebrow)
orte_val = str(len(result.locations))
erstellt_val = datetime.now().strftime("%H:%M")
# Issue #1305: keine Horizont-Kachel mehr — analog #1268 (Zeitfenster-Zeile
# entfiel ersatzlos). Der Wert ist kein Nutzer-relevanter Datenpunkt.

desktop_cells = (
    _cell("Profil", profil_val, "33%")
    + _cell("Orte", orte_val, "33%")
    + _cell("Erstellt", erstellt_val, "34%")
)
...
mobile_row1 = _cell("Profil", profil_val, "50%") + _cell("Orte", orte_val, "50%")
mobile_row2 = _cell("Erstellt", erstellt_val, "100%")
```

Betroffene Bestandstests (werden im selben Commit angepasst, sonst rot):

| Test | Anpassung |
|------|-----------|
| `tests/tdd/test_compare_html_email.py:384-406` (`test_ac6_header_zeigt_48h_horizont`) | Prüfung auf `"+48h" in html` (altes #1268 AC-6) wird zu „keine Horizont-Kachel mehr vorhanden" (weder „Horizont" noch „+48h"/„+96h" im HTML) |
| `tests/tdd/test_compare_dispatch_fixed_window.py` | `forecast_hours == 48`-Assertions → `== 96` bzw. `== COMPARE_FORECAST_HOURS` |
| `tests/tdd/test_compare_preview_service.py:365` | Vorschau-Assertion `forecast_hours == 48` → `== 96` bzw. `== COMPARE_FORECAST_HOURS` |
| `tests/tdd/test_issue_764_compare_forecast_hours_consume.py` | Dispatch-Assertions unter allen Preset-Varianten `== 48` → `== 96` bzw. `== COMPARE_FORECAST_HOURS` |

## Expected Behavior

- **Input:** Versand oder Vorschau eines Ortsvergleichs-Presets (beliebiger
  Alt-Wert in den deprecateten Preset-Feldern `forecast_hours`/`hour_from`/
  `hour_to` — diese werden weiterhin nicht gelesen, siehe #1268 AC-11)
- **Output:** `ComparisonEngine.run` bzw. `fetch_forecast_for_location` fordern
  96 h Vorhersagedaten an (statt 48 h); die Zieltag-Auswertung (Filter auf
  `target_date` + Tagesfenster `(0, 23)`) bleibt inhaltlich unverändert, da
  mehr Stunden nur den abgedeckten Datumsbereich erweitern, nicht die
  Auswertungslogik. Die Vergleichs-Mail-Kopfzeile zeigt nur noch Profil, Orte,
  Erstellt (keine Horizont-Kachel)
- **Side effects:** Vorschau mit Zieldatum bis heute+3 Tage liefert nun eine
  befüllte Auswertung statt leer (vorher außerhalb des 48h-Fensters);
  Gewitter-Ausblick (#1297-Fix) bezieht sich aus derselben erweiterten Quelle
  und profitiert mit

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleichs-Preset mit beliebigem (auch veraltetem)
  Preset-Wert in `forecast_hours` / When der reguläre Versand ausgelöst wird /
  Then fordert der Versandpfad unabhängig vom Preset-Altwert einen Vorhersage-
  Horizont von 96 Stunden an.
  - Test: Dispatch mit mehreren unterschiedlichen Preset-Varianten (inkl.
    Alt-Wert 0/48) prüfen, dass der tatsächlich abgerufene Horizont in jedem
    Fall 96 h beträgt.

- **AC-2:** Given ein Ortsvergleichs-Preset / When die Live-Vorschau desselben
  Presets aufgerufen wird / Then fordert die Vorschau exakt denselben
  Vorhersage-Horizont an wie der reguläre Versand für dasselbe Preset.
  - Test: Versand und Vorschau desselben Presets gegenüberstellen und den
    angeforderten Horizont beider Pfade auf Gleichheit prüfen (Anti-#1297).

- **AC-3:** Given ein Ortsvergleichs-Preset mit einem Zieldatum von heute+3
  Tagen / When die Vorschau aufgerufen wird / Then liefert die Auswertung
  befüllte Ortsergebnisse (nicht leer), weil das Zieldatum innerhalb des neuen
  Horizonts liegt.
  - Test: Vorschau mit Zieldatum heute+3 aufrufen und prüfen, dass mindestens
    ein Ort mit Wetterdaten im Ergebnis erscheint (vorher außerhalb des
    48h-Fensters und damit leer).

- **AC-4:** Given eine versendete oder in der Vorschau gerenderte Vergleichs-
  Mail / When der Mail-Kopf gerendert wird / Then enthält der Kopfbereich
  weder das Wort „Horizont" noch einen Wert wie „+48h" oder „+96h"; Profil,
  Orte und Erstellt bleiben als Kacheln sichtbar.
  - Test: Gerenderte Vergleichs-Mail (Desktop- und Mobile-Tabelle) auf Abwesenheit
    von „Horizont"/„+48h"/„+96h" sowie Anwesenheit von Profil/Orte/Erstellt prüfen.

- **AC-5:** Given ein Ortsvergleich mit Zieldatum heute oder morgen (innerhalb
  des alten wie neuen Horizonts) / When Versand oder Vorschau laufen / Then
  bleibt die inhaltliche Zieltag-Auswertung (Metrik-Werte pro Ort für den
  gewählten Tag) identisch zum bisherigen Verhalten.
  - Test: Bestehenden Regressionstest für heute/morgen-Zieldatum weiterlaufen
    lassen und prüfen, dass sich die berechneten Metrik-Werte gegenüber dem
    48h-Stand nicht ändern.

## Known Limitations

- `forecast_hours` bleibt bewusst kein Editor-Feld (Fortsetzung #1268/#1268-
  C2-Datenerhalt); persistierte Alt-Werte in Presets bleiben weiterhin
  ignoriert. A4 ändert ausschließlich den festen Wert von 48 auf 96.
- 96 h statt 48 h bedeutet etwa doppeltes Antwortvolumen pro Ort von
  OpenMeteo — bei OpenMeteo kostenlos, Anzahl der API-Calls unverändert;
  unkritisch.
- Löst das alte #1268-AC-6 („Kopf-Kachel zeigt +48h") bewusst ab: Diese
  Acceptance Criterion galt für den damaligen festen 48h-Wert und wird durch
  A4 ersetzt — die Kachel entfällt komplett statt einen neuen Wert zu zeigen.
- `email_spec_validator.py` prüft die Horizont-Kachel nicht (verifiziert) —
  kein Validator-Konflikt zu erwarten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — kein Architekturentscheid, reine Wertänderung
  (48 → 96 Stunden über eine bereits etablierte Konstanten-Struktur, Vorbild
  `OPENMETEO_MAX_FORECAST_DAYS`) plus ersatzloser Kachel-Entfall analog #1268.
- **Rationale:** Es wird kein neues strukturelles Muster eingeführt, sondern
  ein bestehendes (Modul-Konstante statt verstreuter Literale) auf einen
  weiteren Fall angewendet, um eine bekannte Fehlerklasse (#1297, Divergenz
  Versand/Vorschau) strukturell auszuschließen.

## Changelog

- 2026-07-18: Initial spec erstellt — Issue #1305, Scheibe A4 von Epic #1301
