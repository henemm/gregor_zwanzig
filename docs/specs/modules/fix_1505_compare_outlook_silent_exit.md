---
entity_id: fix_1505_compare_outlook_silent_exit
type: module
created: 2026-08-08
updated: 2026-08-08
status: implemented
version: "1.0"
tags: [compare, email-rendering, outlook, logging, bugfix]
extends: fix_1486_outlook_silent_exit, outlook_state_hint, comparison_engine
---

# Fix #1505: Orts-Vergleich, Ausblick-Zeile verschwindet still

## Approval

- [x] Approved

## Purpose

Der 3-Tages-Ausblick im Orts-Vergleich verschwindet heute an drei unabhängigen Stellen wortlos
(`_render_location_outlook()` in `compare_html.py`, der Klartext-Ausblick-Block in `comparison.py`)
— für den Empfänger ist ein Fehler, fehlende Rohdaten und eine leere Zeilenbildung nach Filterung
ununterscheidbar von einer normalen leeren Stelle. Dieser Fix ersetzt das stille Verwerfen im
HTML- und Klartext-Ausblick durch einen sichtbaren Zustandstext (Wiederverwendung von
`OutlookState.UNAVAILABLE` aus #1486) und protokolliert die zugrundeliegenden Ursachen in
`comparison_engine.py` als WARNING, wo sie bisher unprotokolliert blieben. Compare-Pendant zu
#1486 (Trip-Pfad, bereits geliefert) mit strukturell anderem Datenpfad und bewusst vereinfachtem
Zwei-Zustands-Modell statt Trips Vier-Zustands-Modell.

## Source

- **File:** `src/output/renderers/email/compare_html.py`
- **Identifier:** `_render_location_outlook` (Zeilen 1115-1147)

> Python-Core (`src/output/renderers/`, `src/services/`) — Domain-Backend, nicht Go/Frontend.

## Estimated Scope

- **LoC:** ~60-100 (Produktivcode ~30-50, Tests ~40-60) — innerhalb des 250-LoC-Budgets, kein
  `loc_limit_override` nötig.
- **Files:** 3 Produktiv-Änderungen (kein neues Produktivmodul) + 1 neue Testdatei + 1 neue Spec.
- **Effort:** medium (zwei unabhängige Renderer müssen konsistent geändert werden;
  Renderer-Commit-Gate #811 greift auf `compare_html.py`).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/outlook_state_hint.py` | module (unverändert, aus #1486) | `OutlookState`-Enum, `render_outlook_state_html`/`render_outlook_state_plain`, `outlook_state_should_warn` — bewusst generisch gehalten, für Compare vorgesehen, keine Compare-eigene Kopie |
| `src/app/models.py` | module | `OutlookState`(Enum) — Domänenschicht, hier liegt die Zustandslogik, wird von `outlook_state_hint.py` re-exportiert |
| `src/services/comparison_engine.py` | module | einzige Quelle für `LocationResult.error`/`outlook_hourly_data`; hier kommen die neuen WARNING-Logs hinzu |
| `src/output/renderers/comparison.py` | module | Klartext-Renderer (`render_comparison_text`), `render_compare_email()` als gemeinsamer Einstiegspunkt für HTML+Klartext |
| `docs/specs/modules/fix_1486_outlook_silent_exit.md` | spec (v1.0, Trip-Pfad) | Vorbild-Spec, Known Limitations dort benennen den Compare-Bug bereits ausdrücklich als eigenständig |
| `.claude/hooks/email_spec_validator.py` | tool (Marker `X-GZ-Mail-Type: compare`) | Pflicht-Validator vor „E2E bestanden" — prüft NUR den HTML-Body |
| Renderer-Commit-Gate #811 | gate | greift auf `compare_html.py`, verlangt vor Commit `email_spec_validator.py` grün |
| Pendant-Sperre #1481 B | gate | keine neue Datei in `frontend/.../compare*` bzw. Renderer mit `compare_`-Präfix nötig — Wiederverwendung von `outlook_state_hint.py`, kein Nachbau |

## Implementation Details

### 1. Zwei-Zustands-Modell statt Trips Vier-Zustands-Modell (bewusste Vereinfachung)

Compare hat kein „Tour zu Ende"-Konzept (kein `NO_STAGES`-Äquivalent aus #1486) und `target_date`
ist bei Scheduler-Versand `date.today()` mit festem 96h-Fetch-Fenster (`COMPARE_FORECAST_HOURS`,
`comparison_engine.py:40`) — ein `BEYOND_HORIZON`-Fall ist im Regelbetrieb praktisch ausgeschlossen
(nur im interaktiven Preview-Pfad mit frei wählbarem `target_date` theoretisch möglich, dort aber
nicht Teil dieses Fixes). Alle drei bestehenden stillen Ursachen werden deshalb einheitlich als
`OutlookState.UNAVAILABLE` behandelt:

1. `loc.error is not None` (Fetch-Fehler oder Exception in `comparison_engine.py`).
2. `not loc.outlook_hourly_data` (Fetch erfolgreich, aber kein Datenpunkt in den drei
   Ausblick-Kalendertagen — z.B. Vorhersagehorizont erschöpft).
3. `not rows` nach `_build_location_outlook_rows()` (Rohdaten vorhanden, aber Zeilenbildung liefert
   nichts — z.B. Metrik-Filterung, `compare_html.py:1095-1096`).

**KEINE neuen `OutlookState`-Werte, KEIN neues Produktivmodul, KEINE Compare-eigene Kopie von
`outlook_state_hint.py`** (Pendant-Sperre #1481 B: Wiederverwendung ist der Ausweg, keine neue
Datei in einem einseitigen Verzeichnis).

### 2. `compare_html.py::_render_location_outlook()` (Zeilen 1115-1147)

Die zwei bestehenden stillen `return ""`-Ausstiege werden zu einem Zustands-Check
zusammengeführt:

```python
if loc.error is not None or not loc.outlook_hourly_data:
    return _render_outlook_unavailable(index, with_location, loc)
rows = _build_location_outlook_rows(loc, outlook_metrics)
if not rows:
    return _render_outlook_unavailable(index, with_location, loc)
```

Der Zustandstext ersetzt `""` und nutzt `render_outlook_state_html(OutlookState.UNAVAILABLE)` aus
`outlook_state_hint.py`, eingebettet in denselben Block-Wrapper (`padding`-`div`), den die
Erfolgstabelle heute verwendet, damit die Danger-Box denselben Sektionsrahmen bekommt wie die
Tabelle. Ob der Ortsname bei `with_location=True` vor dem Zustandstext erscheint (analog zum
Erfolgsfall) ist eine Implementierungs-Detailfrage, keine AC-relevante Entscheidung — Konsistenz
mit dem `header`-Aufbau der Erfolgstabelle ist der Leitfaden.

### 3. `comparison.py::render_comparison_text()` — Klartext-Ausblick-Block (Zeilen 280-284)

Dieselbe Zusammenführung, ABER NUR für den Fall `loc_result.error is None` — Zeile 275
(`if loc_result.error is not None: continue`) bleibt UNVERÄNDERT (s. „Known Limitations" und
PO-Scope-Entscheidung unten):

```python
if loc_result.error is None:
    if outlook_enabled:
        outlook_rows = (
            _build_location_outlook_rows(loc_result, outlook_metrics)
            if loc_result.outlook_hourly_data else []
        )
        if not outlook_rows:
            # UNAVAILABLE: weder outlook_hourly_data noch rows vorhanden
            outlook_state_text = render_outlook_state_plain(OutlookState.UNAVAILABLE)
        else:
            outlook_state_text = None
    else:
        outlook_rows, outlook_state_text = [], None
```

Der `if not have_hourly and not outlook_rows: continue`-Ausstieg (Zeile 284) muss angepasst werden,
damit ein Ort mit `outlook_state_text` gesetzt (aber leerem `outlook_rows`) NICHT übersprungen wird
— sonst würde der neue Zustandstext nie erscheinen, weil der Ort vorher aus der Mail fällt.
`outlook_state_text` wird analog zu `outlook_rows` in `section_lines` geschrieben (Zeile ~324-334,
im `if outlook_rows:`-Zweig ergänzt um einen `elif outlook_state_text:`-Zweig).

### 4. `comparison_engine.py::run()` — zwei neue WARNING-Logs

Logger existiert bereits: `logger = logging.getLogger("comparison_engine")` (Zeile 32).

- **(a) Fehlerfall** — aktuell komplett unprotokolliert an zwei Stellen:
  - Zeile 132-137 (`raw_result.get("error")` → `LocationResult(error=...)`, Fetch liefert
    strukturierten Fehler statt Exception).
  - Zeile 349-353 (`except Exception as e` → `LocationResult(error=str(e))`).

  Beide bekommen `logger.warning("Ort %s: Ausblick nicht verfügbar (Fetch-Fehler: %s)", loc.name, ...)`
  unmittelbar vor bzw. beim Anhängen des fehlerhaften `LocationResult`.

- **(b) Leere `outlook_hourly_data` nach erfolgreichem Fetch** — Zeile 167-169
  (`outlook_hourly_data = [dp for dp, d in _by_local_day if d in _outlook_days]`): wenn das
  Ergebnis leer ist, `logger.warning("Ort %s: kein Ausblick — keine Daten in den naechsten 3 Tagen", loc.name)`.

**WICHTIG — Single-Source-Logging:** Die Logs kommen NUR hierher (Datenschicht, läuft genau
einmal pro Ort und Vergleichslauf), NICHT in die Renderer. `render_compare_email()`
(`comparison.py:375-`) ruft HTML- und Klartext-Renderer für dasselbe `ComparisonResult` in einem
Aufruf (Zeile 410 ff.) — ein Log in beiden Renderern würde pro Lauf doppelt loggen.

### 5. Fall „`rows` leer trotz vorhandenem `outlook_hourly_data`" — kein Log in `comparison_engine.py`

Dieser dritte Ausstieg (Zeilenbildung nach Metrik-Filterung liefert nichts,
`compare_html.py:1131`/`comparison.py:_build_location_outlook_rows`) entsteht erst im
Renderer, NICHT in `comparison_engine.py` — `comparison_engine.py` kennt zu diesem Zeitpunkt
weder `outlook_metrics` noch das Filterungsergebnis. Für diesen Fall gibt es bewusst KEIN
WARNING-Log (Renderer sollen laut Punkt 4 nicht loggen); der sichtbare Zustandstext im
HTML/Klartext ist hier der einzige Nutzer-Hinweis. Das ist eine Abweichung von AC-2/AC-3 in
#1486 (dort loggt der Scheduler auch die Zeilenbau-Leere) — dort läuft die Zeilenbildung
VOR der Rückgabe aus `_build_stage_trend()`, hier ist sie strukturell in den Renderern
verortet.

## Expected Behavior

- **Input:** Ein Orts-Vergleich mit 1-N Orten, je Ort mit/ohne Fetch-Fehler, mit/ohne
  Ausblicks-Rohdaten (`outlook_hourly_data`), mit/ohne nach Metrik-Filterung übrig bleibende Zeilen.
- **Output:** HTML- UND Klartext-Ausblick zeigen JE ORT entweder die Ausblick-Tabelle (Daten
  vorhanden) ODER den Zustandstext „Vorhersage derzeit nicht abrufbar." — nie mehr eine unerklärte
  Leerstelle, sofern der Ort im jeweiligen Kanal überhaupt erscheint (Klartext-Fehlerfall bleibt
  Ausnahme, s. Known Limitations).
- **Side effects:** WARNING-Log-Einträge in `comparison_engine.py` für Fehlerfälle und leere
  `outlook_hourly_data` (vorher keine); kein zusätzliches Logging in den Renderern.

## Acceptance Criteria

- **AC-1 (HTML — Fehlerfall):** Given ein Ort mit `LocationResult.error != None` / When
  `render_compare_html()` den Ausblick-Block für diesen Ort rendert / Then erscheint der
  Zustandstext „Vorhersage derzeit nicht abrufbar." (Danger-Styling, analog #1486 `UNAVAILABLE`)
  statt eines leeren Strings, UND `comparison_engine.py::run()` erzeugt für diesen Ort GENAU EINEN
  WARNING-Log-Eintrag.
  - Test: `ComparisonEngine.run()` mit einer gemockten Fetch-Antwort, die `error` setzt bzw. eine
    Exception wirft; prüfe den gerenderten HTML-Ausblick-Block auf den Zustandstext UND per
    `caplog` auf genau einen WARNING-Eintrag mit Ortsbezug.

- **AC-2 (HTML — leeres `outlook_hourly_data`):** Given ein Ort mit erfolgreichem Fetch, aber
  `outlook_hourly_data == []` (z.B. Vorhersagehorizont innerhalb der 96h-Fetch-Antwort ohne
  Datenpunkte in den drei Ausblickstagen) / When der HTML-Ausblick-Block gerendert wird / Then
  erscheint derselbe Zustandstext, UND ein WARNING-Log-Eintrag entsteht.
  - Test: Fixture mit `raw_data`, deren Zeitstempel alle innerhalb von `_last_detail_day` liegen
    (keine Tage danach); prüfe gerenderten HTML-Block auf Zustandstext UND `caplog` auf WARNING.

- **AC-3 (HTML — leere `rows` trotz vorhandenem `outlook_hourly_data`):** Given ein Ort mit
  nicht-leerem `outlook_hourly_data`, aber `_build_location_outlook_rows()` liefert eine leere
  Liste (z.B. durch eine leere `outlook_metrics`-Auswahl, Issue #1361/#1368-Pfad,
  `compare_html.py:1095-1096`) / When der HTML-Ausblick-Block gerendert wird / Then erscheint
  derselbe Zustandstext wie in AC-1/AC-2 (kein separater Text nötig — es ist derselbe
  UNAVAILABLE-Zustand), UND es entsteht KEIN zusätzliches WARNING-Log in `comparison_engine.py`
  (s. Implementation Details §5 — dieser Pfad ist Renderer-intern).
  - Test: Ruft `_render_location_outlook()` direkt mit einem `LocationResult`, dessen
    `outlook_hourly_data` gesetzt ist, aber `outlook_metrics=[]` übergeben wird; prüft den
    Rückgabewert auf den Zustandstext UND per `caplog`, dass `comparison_engine` NICHT geloggt hat
    (dieser Testfall ruft `comparison_engine.run()` gar nicht auf).

- **AC-4 (Klartext — dieselben zwei Ursachen, Fehlerfall ausgenommen):** Given ein Ort mit
  `loc_result.error is None`, aber leerem `outlook_hourly_data` ODER leeren `outlook_rows` nach
  Filterung / When `render_comparison_text()` den Klartext-Ausblick für diesen Ort rendert / Then
  erscheint der Zustandstext im Klartext-Ausblick-Abschnitt statt eines fehlenden Abschnitts, UND
  der Ort bleibt in der Mail sichtbar (nicht `continue`-übersprungen).
  - Test: `render_comparison_text()` mit einem `ComparisonResult`, dessen einziger Ort `error=None`
    und `outlook_hourly_data=[]` hat; prüft den Klartext-Body auf Vorhandensein des Ortsnamens UND
    des Zustandstexts.

- **AC-5 (Normalfall unverändert — Regressionstest):** Given ein Ort mit erfolgreichem Fetch,
  nicht-leerem `outlook_hourly_data` und nicht-leeren `rows` / When HTML UND Klartext gerendert
  werden / Then erscheint unverändert die Ausblick-Tabelle (kein neuer Zustandstext), UND es
  entsteht KEIN WARNING-Log-Eintrag für diesen Ort.
  - Test: Bestehende Golden-Fixture mit vollständigen Ausblicksdaten durch beide Renderer laufen
    lassen; prüft Tabellen-Marker (z.B. `OUTLOOK_HEADING` im Output) UND per `caplog`, dass kein
    WARNING mit Ortsbezug für den Ausblick entsteht.

- **AC-6 (kein Doppel-Logging):** Given ein Vergleichslauf mit einem Ort, dessen Fetch fehlschlägt
  / When `ComparisonEngine.run()` einmal aufgerufen und anschließend
  `render_compare_email()` (HTML + Klartext in einem Aufruf) auf dem Ergebnis ausgeführt wird /
  Then entsteht GENAU EIN WARNING-Log-Eintrag für diesen Ort — nicht zwei, obwohl beide Renderer
  über den Zustand entscheiden.
  - Test: `caplog`-Zähler auf WARNING-Records mit dem betroffenen Ortsnamen nach dem vollständigen
    Lauf (`run()` gefolgt von `render_compare_email()`), Assertion `== 1`. Test hängt direkt an
    `comparison_engine.py`, nicht an den Renderern (Log entsteht dort, nicht in ihnen).

- **AC-7 (Mehrort-Fall — keine falsche Ganz-Auslassung im HTML):** Given ein Vergleich mit 3 Orten:
  Ort A (`FOUND`, Ausblick vorhanden), Ort B (`error != None`), Ort C (`error=None`, leeres
  `outlook_hourly_data`) / When `render_compare_html()` gerendert wird / Then erscheinen alle drei
  Orte mit ihrem jeweils korrekten Zustand (A: Tabelle, B und C: Zustandstext) — kein Ort
  verschwindet komplett aus der HTML-Mail. Im Klartext fällt Ort B (Fehlerfall) laut Scope-Grenze
  weiterhin aus dem Stundenverlauf-/Ausblick-Abschnitt heraus (Zeile 275, s. Known Limitations,
  Korrektur 2026-08-08) — der Ortsname selbst bleibt dort im vorbestehenden Übersichtsblock mit
  eigener Fehlerzeile sichtbar (`comparison.py:216-222`, unverändert); A und C erscheinen im
  Stundenverlauf-/Ausblick-Abschnitt mit Tabelle bzw. Zustandstext.
  - Test: `ComparisonResult` mit drei `LocationResult`-Einträgen wie beschrieben; prüft im
    gerenderten HTML alle drei Ortsnamen UND je Ort den korrekten Ausblick-Zustand; prüft im
    Klartext, dass Ort A und C erscheinen und dass im Stundenverlauf-/Ausblick-Abschnitt (nicht im
    gesamten Mail-Body) weder Tabelle noch Zustandstext für Ort B vorkommen.

## Known Limitations

- **Scope-Grenze Klartext-Fehlerfall (PO-Entscheidung 2026-08-08, bewusst NICHT Teil dieses
  Fixes; Formulierung präzisiert 2026-08-08 nach Befund aus der Implementierung):**
  `comparison.py:275` (`if loc_result.error is not None: continue`) bleibt unverändert. Ein Ort,
  der komplett fehlschlägt, fällt im Klartext-Teil weiterhin GANZ aus dem
  Stundenverlauf-/Ausblick-Abschnitt heraus (weder Tabelle noch Zustandstext, für keinen der
  beiden Bausteine). **Korrektur:** anders als ursprünglich hier formuliert verschwindet der Ort
  dadurch NICHT aus der gesamten Mail — sein Name bleibt im vorbestehenden Übersichtsblock
  (`comparison.py:216-222`, unverändert, jeder Ort inkl. Fehlerzeile) sichtbar; nur der
  Stundenverlauf-/Ausblick-Teil fehlt ihm. Das ist breiter als der Ausblick-Bug dieses Fixes und
  geht als Nebenbefund-Eintrag nach #1199 (Laufender Sammel-Issue,
  kein eigenes Issue laut Nebenbefund-Triage) statt hier mitgefixt zu werden.
- **Kein Compare-Äquivalent zu `NO_STAGES`/`BEYOND_HORIZON`:** Anders als #1486 (Trip, vier
  Zustände) verwendet dieser Fix nur `FOUND`/`UNAVAILABLE`. Ein theoretischer
  `BEYOND_HORIZON`-Fall im interaktiven Preview-Pfad (frei wählbares `target_date`, s.
  `compare_preview_service.py`) wird NICHT gesondert behandelt — er fällt unter `UNAVAILABLE` mit
  identischem Text. Das ist als bewusste Vereinfachung dokumentiert, keine übersehene Lücke.
- **`_build_location_outlook_rows()`-Leere (dritte Ursache) erzeugt kein Log in
  `comparison_engine.py`:** Dieser Pfad ist strukturell im Renderer verortet (Metrik-Filterung
  findet erst dort statt, `comparison_engine.py` kennt `outlook_metrics` nicht). Der sichtbare
  Zustandstext ist hier der einzige Nutzer-Hinweis, kein WARNING-Log begleitet ihn — Abweichung
  vom Trip-Pfad (#1486), wo derselbe Fall noch im Scheduler geloggt wird, weil dort die
  Zeilenbildung vor dem Rückgabewert von `_build_stage_trend()` liegt.
- **Klartext-Validator-Blindfleck:** `email_spec_validator.py` (Pflicht-Validator, Marker
  `X-GZ-Mail-Type: compare`) liest NUR den HTML-Body. Der Klartext-Nachweis (AC-4, AC-7 Klartext-
  Teil) muss zusätzlich manuell bzw. testseitig geführt werden — bekannter, vorbestehender
  blinder Fleck (s. Memory `reference_compare_mail_plaintext_blind_spot`), nicht Teil dieses Fixes.
- **`render_compare_telegram`/`render_compare_sms` unverändert:** Kein Ausblick-Feature in diesen
  Kanälen (geprüft: keine `outlook_*`-Parameter vorhanden) — dieser Fix betrifft ausschließlich
  die E-Mail (HTML + Klartext).
- **#1563 (Vertretungshinweis fehlt) ist ein anderer Bug** in derselben Datei
  (`compare_html.py`), andere Zeilen — nicht Teil dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine.
- **Rationale:** Dieser Fix führt keine neue Systementscheidung ein, sondern wendet das in #1486
  etablierte Muster (`OutlookState`, geteilter Rendering-Baustein `outlook_state_hint.py`) additiv
  auf einen zweiten, bereits vorgesehenen Konsumenten an (`outlook_state_hint.py` war laut #1486
  „bewusst generisch gehalten... damit derselbe Baustein später auch der Ortsvergleich nutzen
  kann"). Die Reduktion auf zwei statt vier Zustände ist eine lokale, auf Compare beschränkte
  Design-Wahl (kein `NO_STAGES`-Äquivalent, `BEYOND_HORIZON` praktisch ausgeschlossen im
  Regelbetrieb) ohne Rückwirkung auf den Trip-Pfad oder andere Konsumenten von `OutlookState`.

## Changelog

- 2026-08-08: Initial spec created (Fix #1505, Compare-Pendant zu #1486; PO-Scope-Entscheidung zur
  Ausklammerung von `comparison.py:275` dokumentiert).
- 2026-08-08: TDD-GREEN-Befund eingearbeitet (AC-7, Known Limitations): die ursprüngliche
  Formulierung „Ort verschwindet GANZ aus der Mail" war unpräzise — gemessen am unveränderten
  Basis-Stand bleibt der Ortsname eines Fehler-Orts im Klartext-Übersichtsblock
  (`comparison.py:216-222`) sichtbar; die Scope-Grenze betrifft nur den
  Stundenverlauf-/Ausblick-Abschnitt. Keine Scope-Änderung, nur Präzisierung der Beschreibung.
