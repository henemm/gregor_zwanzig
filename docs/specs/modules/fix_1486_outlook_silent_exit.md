---
entity_id: fix_1486_outlook_silent_exit
type: module
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [trip-reports, email-rendering, telegram, outlook, logging, bugfix]
extends: multi_day_trend, trip_report_scheduler, output_channel_renderers, warn_unavailable_hint
---

# Fix #1486: Ausblick benennt seinen Zustand statt zu schweigen

## Approval

- [ ] Approved

## Purpose

Der Mehrtages-Ausblick-Block ("Nächste Etappen") im Trip-Briefing verschwindet heute an fünf
Stellen in `_build_stage_trend()` wortlos — für den Empfänger sind alle fünf identisch: eine leere
Stelle im Briefing. Dieser Fix ersetzt das stille Verwerfen durch einen sichtbaren, nach Ursache
unterscheidbaren Zustand (normaler Tourabschluss / außerhalb Vorhersagehorizont / Störung) über
alle vier Ausgabewege (HTML-, Klartext-, Compact-Mail, Telegram), und protokolliert die beiden
Störfälle als WARNING statt bisher DEBUG.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `TripReportScheduler._build_stage_trend` (Zeilen 1370-1467)

> Python-Core (`src/services/`) — Domain-Backend, nicht Go/Frontend.

## Estimated Scope

- **LoC:** ~280-330 (Produktivcode ~150-180, Tests ~130-150) — überschreitet das
  Default-LoC-Budget von 250/Workflow voraussichtlich; `workflow.py set-field loc_limit_override 500`
  ist bei diesem Full-Process-Workflow einzuplanen, kein Fast-Track-Zuschnitt.
- **Files:** 10 Produktivdateien (1 neu) + 2-3 Testdateien (1 neu, 2 angepasst) + 1 Spec-Update
  (`multi_day_trend.md` → v5.0)
- **Effort:** medium-high (Rückgabetyp-Änderung berührt zwei Aufrufer + einen Reuse-Pfad + vier
  Renderer; Renderer-Commit-Gate #811 greift)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/unavailable_hint.py` | module (Vorbild, #1348/#1349) | Muster für Flag-Auswertung + Danger-Box + Plain/ASCII-Varianten — DRY-Pflicht #1481 |
| `src/output/renderers/email/outlook.py` | module (geteilt, Epic #1301 B4) | `build_outlook_row`, `render_outlook_table`, `render_outlook_plain` — Trip/Compare-Teilungsbaustein, unverändert |
| `src/providers/openmeteo.py` | module | `is_within_forecast_horizon`, `OPENMETEO_MAX_FORECAST_DAYS` — liefert `N` für Klasse-B-Text |
| `src/services/preview_service.py` | module | zweiter Aufrufer von `_build_stage_trend`; MUSS zeichengleich bleiben (ADR-0025/#1297) |
| `docs/specs/modules/multi_day_trend.md` | spec (v4.0→v5.0) | AC-3/C5/Edge-Cases widersprechen heute diesem Fix — wird in diesem Workflow mitgeändert |
| `docs/specs/modules/warn_unavailable_hint.md` | spec | Vorbild-Spec für den neuen Hinweis-Baustein |
| Epic #1374, Invariante 2 | Grundsatz | „kein stilles Verwerfen" |
| Issue #1275 (`_build_thunder_forecast_from_trend_or_fetch`) | Reuse-Pfad | liest Trend-Zeilen per Datum wieder — Rückgabetyp-Änderung darf ihn nicht brechen |
| Issue #1388 (Testlücke) | Vorarbeit | Morgen-Briefing-Ausblick war ungetestet — wird mit AC-8 geschlossen |

## Implementation Details

### 1. Neuer Zustandstyp statt binärem `Optional[list[dict]]`

`_build_stage_trend()` gibt heute `None` zurück, wenn der Ausblick aus irgendeinem der fünf Gründe
entfällt. Damit lässt sich Grund NICHT rekonstruieren — genau das ist der Bug. Eine reine
Typänderung des bestehenden Rückgabewerts (z.B. `list[dict] | ErrorCode` statt `list[dict] | None`)
würde jedoch zwei bestehende Konsumenten brechen, die exakt `Optional[list[dict]]` erwarten:

1. `_build_thunder_forecast_from_trend_or_fetch()` (`trip_report_scheduler.py:1469-1539`) iteriert
   `for row in (multi_day_trend or [])` und liest `row["date"]` — erwartet eine reine Liste.
2. `preview_service.py:190-192` MUSS laut ADR-0025/#1297 exakt dieselben Bytes erzeugen wie der
   Versandpfad — jede Formänderung des durchgereichten Werts riskiert Divergenz.

**Design-Entscheidung:** `_build_stage_trend()` gibt neu ein `TrendResult`-Objekt
(`@dataclass(frozen=True)`, definiert in `src/output/renderers/email/outlook_state_hint.py`) mit
zwei Feldern zurück:

```python
@dataclass(frozen=True)
class TrendResult:
    rows: Optional[list[dict]]   # UNVERAENDERTE Form — identisch zum bisherigen Rückgabewert
    state: OutlookState          # FOUND | NO_STAGES | BEYOND_HORIZON | UNAVAILABLE
    horizon_days: Optional[int] = None  # nur gesetzt bei BEYOND_HORIZON
```

`rows` behält exakt die bisherige Form (`list[dict]` mit `>=1` Eintrag oder `None` bei leer) — der
Thunder-Reuse-Pfad (`_build_thunder_forecast_from_trend_or_fetch`) und der Vorschau-Vergleich
(ADR-0025) lesen **weiterhin nur `result.rows`** und bleiben dadurch unverändert. Die beiden
direkten Aufrufer (`trip_report_scheduler.py:879-880`, `preview_service.py:190-192`) werden auf
Entpacken umgestellt:

```python
trend_result = self._build_stage_trend(trip, target_date, tz=trip_tz)
multi_day_trend = trend_result.rows       # unveraendert an Thunder-Reuse + Renderer weitergereicht
outlook_state = trend_result.state        # NEU, additiv an Renderer weitergereicht
outlook_horizon_days = trend_result.horizon_days
```

Diese Entscheidung ist additiv: kein bestehender Aufrufer, der nur `.rows`-Form kennt, muss
angepasst werden — nur die beiden Stellen, die `_build_stage_trend()` direkt aufrufen.

### 2. `OutlookState`-Enum und Text/Render-Bausteine (neues Modul)

`src/output/renderers/email/outlook_state_hint.py` (analog `unavailable_hint.py`, DRY-Pflicht
#1481):

```python
class OutlookState(Enum):
    FOUND = "found"              # Trend vorhanden — Standard-Tabelle rendern
    NO_STAGES = "no_stages"      # Klasse A — Zeile :1390 (heute :1381 im Kontext-Dokument)
    BEYOND_HORIZON = "beyond_horizon"  # Klasse B — Zeile :1396 (Horizont-Check)
    UNAVAILABLE = "unavailable"  # Klasse C — Zeilen :1404, :1408, :1463 (alle drei Ursachen)

_OUTLOOK_STATE_TEXT = {
    OutlookState.NO_STAGES: "Keine weiteren Etappen — kein Ausblick.",
    OutlookState.BEYOND_HORIZON: "Nächste Etappe liegt zu weit voraus (max. {n} Tage).",
    OutlookState.UNAVAILABLE: "Vorhersage derzeit nicht abrufbar.",
}

def outlook_state_should_warn(state: OutlookState) -> bool:
    """Klasse A (NO_STAGES) ist kein Logging-wuerdiges Ereignis — normaler
    Tourabschluss. B und C bekommen ein WARNING (vorher DEBUG bzw. teilweise
    schon WARNING bei der Exception-Ursache)."""
    return state in (OutlookState.BEYOND_HORIZON, OutlookState.UNAVAILABLE)

def render_outlook_state_html(state: OutlookState, horizon_days: Optional[int] = None) -> str: ...
def render_outlook_state_plain(state: OutlookState, horizon_days: Optional[int] = None, *, ascii_safe: bool = False) -> str: ...
```

**Styling-Unterschied zum Vorbild `unavailable_hint.py` (bewusst, s. Issue-Kontext):**
- `FOUND` → kein Text, Standard-Tabelle wie bisher.
- `NO_STAGES` (Klasse A) → schlichter Fließtext, `G_INK_MUTED` (NICHT `G_INK_FAINT` —
  Design-Leitprinzip Lesbarkeit; NICHT `G_INK_FAINT`, weil das laut CLAUDE.md strikt nur für
  Placeholder/Disabled reserviert ist), kein Rahmen, kein Icon — ein normaler Tourabschluss ist
  keine Warnung.
- `BEYOND_HORIZON` (Klasse B) → gleiche neutrale Optik wie A (Fließtext, `G_INK_MUTED`), reine
  Information, kein Alarm-Ton — auch wenn dieser Fall neu ein WARNING-Log auslöst, ist er für den
  Empfänger keine Störung.
- `UNAVAILABLE` (Klasse C) → Danger-Box wie `unavailable_hint.py`
  (`G_BOX_DANGER_BG`/`G_DANGER`), `⚠️` (plain) bzw. `!!` (ascii_safe/compact) — das ist der einzige
  Fall, der wie eine Störung aussehen soll.

### 3. Protokollierung (Klasse B und C → WARNING)

- Zeile `:1396` (Horizont-Check, Klasse B): `logger.debug(...)` → `logger.warning(...)`, Text
  bleibt inhaltlich gleich (Stage-ID, Datum, Horizont-Tage).
- Zeile `:1404` (keine Segmente) und `:1408` (keine Wetterdaten, Klasse C): bisher **kein** Log —
  NEU `logger.warning("Stage %s (%s): kein Ausblick — <Ursache>", stage.id, stage.date)`.
- Zeile `:1463` (Exception, Klasse C): bleibt `logger.warning(...)`, unverändert (war schon
  WARNING).
- Bekannter, separater Prüfpunkt (Known Limitations): ob das WARNING überhaupt irgendwo ankommt,
  ist wegen des dokumentierten Python-Kern-Logging-Blindflecks offen — s.u.

### 4. Durchreichung an die vier Renderer

`outlook_state` (und ggf. `outlook_horizon_days`) wird als additiver, defaultender Parameter durch
dieselbe Kette gereicht, die heute `multi_day_trend` transportiert:

`trip_report_scheduler.py` → `trip_report.py:156` (`effective_trend` bleibt unverändert; neues
`effective_outlook_state` daneben) → `email/__init__.py::render_email()` (zwei neue optionale
kwargs `outlook_state: Optional[OutlookState] = None`, `outlook_horizon_days: Optional[int] =
None`) → `html.py`, `plain.py`, `compact.py`. `narrow.py` (Telegram) bekommt den Zustand über den
bestehenden Trip-Report-Adapter-Pfad, nicht über `render_email()`.

Jeder der vier Renderer ersetzt sein bisheriges `if multi_day_trend: <Tabelle>` durch:

```python
if multi_day_trend:
    <bestehende Tabelle, unveraendert>
elif outlook_state is not None and outlook_state != OutlookState.FOUND:
    <neuer Zustandstext ueber outlook_state_hint.py>
# sonst (outlook_state None, z.B. show_outlook=False oder aeltere Aufrufer): Block entfaellt wie bisher
```

Das `elif outlook_state is not None` schützt bestehende Test-/Vorschau-Aufrufer, die `render_email`
ohne den neuen Parameter aufrufen (Default `None`) — für sie ändert sich das Verhalten NICHT
(Block entfällt weiterhin lautlos, wie vor diesem Fix). Das ist bewusst so gewählt, um den
Blast-Radius auf den tatsächlichen Versand-/Vorschau-Pfad zu begrenzen, der `outlook_state` künftig
immer setzt.

### 5. Konfliktauflösung mit `multi_day_trend.md` (separate Datei, s. Auftrag)

`docs/specs/modules/multi_day_trend.md` wird in diesem Workflow zusätzlich auf Version 5.0
gehoben: AC-3, C5 und die Edge-Case-Zeile werden umgekehrt (PO-Entscheidung 2026-08-04, s.
Changelog dort).

## Expected Behavior

- **Input:** Trip mit/ohne Folge-Etappen, mit Etappen innerhalb/außerhalb des
  Vorhersagehorizonts, mit/ohne auflösbare Segmente, mit/ohne Wetterdaten.
- **Output:** Vier Ausgabewege (HTML-Mail, Klartext-Mail, Compact-Mail, Telegram) zeigen JEWEILS
  entweder die Ausblick-Tabelle (Trend vorhanden) ODER einen der drei unterscheidbaren
  Zustandstexte (Klasse A/B/C) — nie mehr eine unerklärte Leerstelle, wenn `outlook_state` gesetzt
  ist.
- **Side effects:** WARNING-Log-Einträge für Klasse B und C (vorher DEBUG bzw. teilweise gar
  keiner).

## Acceptance Criteria

**AC-1 (Klasse A — normaler Tourabschluss):** Given eine Tour ohne weitere Etappen nach dem
Zieldatum / When das Briefing (gleich welcher Kanal) gerendert wird / Then erscheint der Satz
„Keine weiteren Etappen — kein Ausblick." ohne Warn-/Danger-Styling (kein Rahmen, kein `⚠️`), UND
es entsteht KEIN WARNING-Log-Eintrag.
- Test: Rendere ein Briefing für einen Trip, dessen letzte Etappe das Zieldatum ist; prüfe den
  sichtbaren Mail-/Telegram-Text auf den exakten Satz UND prüfe (per `caplog`), dass kein
  WARNING mit Bezug zu diesem Trend entsteht.

**AC-2 (Klasse B — außerhalb Vorhersagehorizont):** Given eine Folge-Etappe jenseits von
`OPENMETEO_MAX_FORECAST_DAYS` Tagen / When das Briefing gerendert wird / Then erscheint der Satz
„Nächste Etappe liegt zu weit voraus (max. N Tage)." mit dem echten, aktuell konfigurierten `N` UND
ein WARNING-Log-Eintrag entsteht (vorher `logger.debug`).
- Test: Fixture-Etappe mit Datum `today + OPENMETEO_MAX_FORECAST_DAYS + 5`; prüfe gerenderten Text
  enthält die korrekte Zahl UND `caplog` enthält einen WARNING-Satz zu dieser Stage.

**AC-3 (Klasse C — alle drei Ursachen gegenüberstellen):** Given fehlende Segmente ODER fehlende
Wetterdaten ODER ein Fehler beim Zeilenbau (drei separate Testfälle im selben Modul) / When das
Briefing gerendert wird / Then erscheint in allen drei Fällen „Vorhersage derzeit nicht abrufbar."
mit Danger-Styling (Rahmen/`⚠️` bzw. `!!`), UND jeweils ein WARNING-Log-Eintrag entsteht.
- Test: Drei parametrisierte Fälle (leere Segmentliste, leere Wetterliste, patch-freie
  Exception-Provokation z.B. via kaputtes Aggregat) im selben Testmodul; jeder prüft Text +
  Styling-Marker (Rahmenfarbe/Symbol) + `caplog`.

**AC-4 (Unterscheidbarkeit — Kern des Issues):** Given zwei Renderläufe, einer mit Klasse A und
einer mit Klasse B bzw. C / When die gerenderten Texte verglichen werden / Then sind sie eindeutig
unterschiedliche Zeichenketten (nicht dieselbe generische Phrase) — „für den Empfänger sehen alle
fünf identisch aus" gilt nach dem Fix nicht mehr.
- Test: Rendere alle vier Zustände (FOUND-Tabelle ausgenommen: A, B, C) nacheinander und prüfe per
  Assertion, dass sich je zwei der drei Texte unterscheiden (`assert text_a != text_b != text_c`,
  paarweise).

**AC-5 (vier Ausgabewege inkl. Telegram):** Given Klasse C tritt ein / When das Briefing über
HTML-Mail, Klartext-Mail, Compact-Mail UND Telegram (`narrow.py`) gerendert wird / Then zeigt JEDER
der vier Kanäle den Hinweis „Vorhersage derzeit nicht abrufbar." (bzw. seine Kanal-Fassung: HTML
Danger-Box, Plain `⚠️`, Compact `!!`, Telegram-Bubble-Text).
- Test: Ein Testfall pro Kanal (4 Assertions in einem oder vier Tests), jeweils gegen den echten
  Renderer-Aufruf, nicht gegen eine Zwischenrepräsentation.

**AC-6 (Vorschau bleibt zeichengleich, ADR-0025/#1297):** Given identische Eingabedaten / When
sowohl der Versandpfad (`trip_report_scheduler.py:879`) als auch der Vorschau-Pfad
(`preview_service.py:190-192`) denselben Trend-Zustand erzeugen / Then ist das gerenderte Ergebnis
byte-identisch — die `TrendResult`-Einführung darf die Vorschau nicht divergieren lassen.
- Test: Rendere denselben Trip/dasselbe Zieldatum einmal über den Versandpfad-Aufbau und einmal
  über `preview_service`, vergleiche die erzeugten Mail-Strings zeichenweise (bestehendes
  ADR-0025-Testmuster erweitern, nicht neu erfinden).

**AC-7 (Thunder-Reuse-Pfad #1275 bleibt unversehrt):** Given
`_build_thunder_forecast_from_trend_or_fetch()` liest Trend-Zeilen per Datum wieder
(`trip_report_scheduler.py:1493`ff.) / When `_build_stage_trend()` neu ein `TrendResult` statt
`Optional[list[dict]]` zurückgibt / Then funktioniert der Thunder-Forecast-Reuse unverändert (kein
`KeyError`, keine falsche `TH+:`-Ableitung).
- Test: Bestehende Suiten `tests/tdd/test_th_plus_follows_thunder_metric_and_gap.py` und die
  #874-Bestandssuite laufen unverändert grün gegen den neuen Rückgabetyp (Regressionslauf, keine
  neuen Assertions nötig — der Beweis ist, dass nichts bricht).

**AC-8 (Morgen-Briefing-Testlücke aus #1388 schließen):** Given
`multi_day_trend_reports=["morning"]` konfiguriert und ein Trend vorhanden / When das
Morgen-Briefing gerendert wird / Then erscheint der Ausblick-Block genauso wie im
Abend-Briefing — bisher deckten nur Golden-Mails den Abend ab.
- Test: Neuer oder erweiterter Testfall, der `report_type="morning"` UND
  `multi_day_trend_reports=["morning"]` setzt und den gerenderten Ausblick-Block auf Vorhandensein
  UND korrekten Inhalt prüft (nicht nur "kein Crash").

## Known Limitations

- **Compare-Teilungsprüfung (Pflicht, s. CLAUDE.md „Trip/Ortsvergleich-Code-Teilung"):** Der
  Ortsvergleich hat einen STRUKTURELL ANDEREN, aber ANALOGEN Bug: `compare_html.py::
  _render_location_outlook()` (Zeile 1083) verwirft ebenfalls still (`return ""`) bei
  `loc.error is not None or not loc.outlook_hourly_data`. Er lädt jedoch NICHT über
  `_build_stage_trend()`, sondern über `comparison_engine.py`s eigene
  `outlook_hourly_data`-Erzeugung — die Fünf-Ursachen-Unterscheidung aus #1486 passt dort nicht
  1:1 (nur EINE Bedingung statt fünf). Issue #1486 zitiert explizit nur `_build_stage_trend()`
  (Trip-Pfad) als Scope. **Entscheidung dieses Workflows:** `outlook_state_hint.py` wird bewusst
  generisch gehalten (nimmt `OutlookState` + optionalen `horizon_days` entgegen, keine
  Trip-spezifischen Typen in der Signatur) und ist damit für einen künftigen Compare-Fix
  wiederverwendbar — `comparison_engine.py`/`compare_html.py` werden in DIESEM Workflow jedoch
  NICHT angefasst (Scope-Treue zu #1486, LoC-Budget). Der Compare-Bug ist nutzersichtbares
  Fehlverhalten und bekommt laut Nebenbefund-Triage ein eigenes Issue — nicht Teil dieses Fixes.
- **`tests/test_output_timezone_guard.py:517-518`:** Nennt `_build_stage_trend` mit
  Zeilennummern-Historie in Ausnahme-Schlüsseln. Die Rückgabetyp-Änderung selbst berührt diesen
  Wächter nicht (er prüft Zeitzonen-Handling, nicht den Rückgabetyp), aber die
  Zeilennummern-Verschiebung durch neue Log-Zeilen kann seine Schlüssel entwerten — als Prüfpunkt
  vermerkt, nicht als eigenes AC (der Wächter hat eine andere Zusicherung).
- **Protokoll-Blindfleck (bekanntes, separates Problem):** Laut Memory-Befund landet
  INFO/DEBUG/WARNING aus dem Python-Kern aktuell nirgends beobachtbar (kein zentrales Log-Sink
  verifiziert). Ob das neue WARNING für Klasse B/C wirklich irgendwo ankommt (Betriebssicht), ist
  ein offener, separater Prüfpunkt — dieser Fix stellt nur sicher, dass das Log-Statement im Code
  korrekt abgesetzt wird (per `caplog` in AC-2/AC-3 bewiesen), nicht dass es operativ sichtbar ist.
- **`elif outlook_state is not None`-Wächter (s. Implementation Details §4):** Bestandsaufrufer von
  `render_email()`, die den neuen Parameter nicht setzen, behalten das alte stille Verhalten
  (Block entfällt kommentarlos). Das ist beabsichtigt (Blast-Radius-Begrenzung auf den echten
  Versand-/Vorschau-Pfad), bedeutet aber: Test- oder Drittintegrationen, die `render_email()` ohne
  `outlook_state` aufrufen, profitieren NICHT automatisch vom Fix.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-Kandidat, kein eigenes Dokument in diesem Workflow — PO entscheidet bei
  Freigabe, ob ein eigenes ADR folgt.
- **Rationale:** Die Rückgabetyp-Änderung von `_build_stage_trend()` (`Optional[list[dict]]` →
  `TrendResult`-Dataclass) ist eine Datenmodell-Entscheidung, die zwei Aufrufer und einen
  Reuse-Pfad (#1275) betrifft und einen wiederkehrenden Musterfall darstellt (binäres
  Vorhanden/Fehlt vs. mehrwertiger Zustand mit Begründung) — ähnlich gelagert wie die
  ADR-0025-Entscheidung zur Vorschau-Byte-Gleichheit. Kein eigenständiges ADR-Dokument, weil die
  Entscheidung additiv und lokal auf diesen einen Rückgabewert beschränkt ist (kein neuer
  Systemgrundsatz), aber die konkrete Design-Wahl ist hier dokumentiert und bindend für die
  Implementierung.

## Changelog

- 2026-08-04: Initial spec created (Fix #1486, PO-Entscheidung zur Umkehrung von
  `multi_day_trend.md` AC-3/C5 dokumentiert, s. dortiger Changelog-Eintrag v5.0)
