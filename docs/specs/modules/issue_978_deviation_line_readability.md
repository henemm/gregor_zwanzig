---
entity_id: issue_978_deviation_line_readability
type: module
created: 2026-07-02
updated: 2026-07-02
status: draft
version: "1.0"
tags: [alert, email, telegram, readability]
---

# Deviation-Alert: Lesbare Multi-Metrik-Zeile (Issue #978)

## Approval

- [x] Approved (PO 'go', 2026-07-02)

## Purpose

Die Multi-Metrik-Zeile des Deviation-Alerts (E-Mail-Datenblock, Betreff-Top-3, Telegram-Zweitzeile)
wiederholt die Einheit bis zu dreimal pro Zeile und zeigt „,0"-Rauschen bei glatten Werten
(`Niedersch · Schwelle 10,0 mm 6,0 mm ↑ 14,0 mm über`). Der PO musste nachfragen, was die Zeile
bedeutet. Diese Spec bringt die Multi-Metrik-Ausgabe auf das Format der Design-Vorlage: Einheit
genau einmal, Schwelle ohne Einheit, glatte Werte ganzzahlig.

## Source

- **File:** `src/output/renderers/alert/render.py`
- **Identifier:** `_email_line()`, `render_email()` (Multi-Zweig `data_rows`), `render_subject()`
  (Multi-Zweig `top3`), `render_telegram()` (nutzt `_email_line()` für Zeile 2+)

> **Schicht:** Python-Backend (`src/output/renderers/...`), kein Frontend-/Go-API-Code betroffen.
> Der Deviation-Alert wird ausschließlich serverseitig gerendert (E-Mail/Telegram/SMS-Versand).

## Estimated Scope

- **LoC:** ~+60/−25
- **Files:** 1 Produktionsdatei (`render.py`) + 4 Testdateien (1 neu, 3 Bestand angepasst)
- **Effort:** medium (Versandpfad, aber eng umrissen; bestehende Wächter-Tests vorhanden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/app/metric_catalog.py` (`format_metric_value`, `get_decimals`, `get_metric`, `get_alert_label`, `get_sms_code`) | Katalog | Liefert Einheit/Dezimalstellen/Kürzel je Metrik — **`format_metric_value()` bleibt unverändert** (geteilt mit `format_change_line`, #952 Finding F001) |
| `src/output/renderers/alert/model.py` (`arrow`, `side_label`, `over_thr`, `severity`) | Renderer-Model | Richtung/Status je `AlertEvent` — unverändert |
| `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html` (Zeilen 200–290) | Design-Vorlage | SOLL-Referenz für E-Mail-Datenblock, Betreff, Telegram-Zeile 2 |

## Implementation Details

### SOLL (aus Design-Vorlage, exakte Referenzzeilen)

E-Mail-Datenblock (`Gregor 20 - Alert Mail Vorschläge.html:220-233`):
```
<span class="k">Böen <span ...>· Schwelle 50</span></span>
<span class="v">35 <span ...>↑</span> 52 km/h <span class="delta" ...>über</span></span>

<span class="k">Gewitter <span ...>· Schwelle 40 %</span></span>
<span class="v">30 <span ...>↑</span> 55 % <span class="delta" ...>über</span></span>

<span class="k">Niedersch <span ...>· Schwelle 10</span></span>
<span class="v">6 <span ...>↑</span> 14 mm/h <span class="delta" ...>über</span></span>

<span class="k" style="color:var(--g-ink-3)">Regen% <span ...>· unter Schwelle</span></span>
<span class="v" ...>70 → 90 %</span>
```
→ Prinzip: links `{Kürzel} · Schwelle {Zahl}` (Schwelle **ohne** Einheit, außer bei `%`, wo sie
zur Unterscheidung mitgeführt wird — vgl. `Schwelle 40 %`), rechts `{von} {Pfeil} {bis} {Einheit}`
(Einheit **genau einmal**, am letzten Wert) + `über`/`unter`-Kennzeichnung (farbig bei „über",
gedämpft bei „unter").

Betreff-Top-3 (`Gregor 20 - Alert Mail Vorschläge.html:208,277`):
```
[KHW 403] km 0–4 · ↑ 3 über Schwelle: Niedersch 14, Gewitter 55%, Böen 52
```
→ nur die Zahl je Metrik; `%` klebt direkt am Wert (kein Leerzeichen), alle anderen Einheiten
entfallen im Betreff komplett.

Telegram-Zeile 2 (`Gregor 20 - Alert Mail Vorschläge.html:281`):
```
<b>KHW 403 · km 0–4 · ↑ 3 über Schwelle</b>
Niedersch 6→14 · Gewitter 30→55% · Böen 35→52
```
→ `{Kürzel} {von}→{bis}` je Metrik, durch ` · ` getrennt; keine Einheiten außer `%` (klebt am
Wert); kein Schwellen-Text pro Metrik-Zeile — der Schwellen-Bezug steht bereits in der fetten
Kopfzeile (`N über Schwelle`).

Rundung (Design-Dokument, Hebel 05: „Zahlen runden — `1230` statt `1230.0`"): glatte Werte
ganzzahlig ohne Nachkommastellen (`10` statt `10,0`), echte Dezimalwerte (z. B. `0,4 mm`
Niederschlag) behalten 1 Nachkommastelle mit Komma. Tausender-Punkt bleibt erhalten (`1.230`).

### IST-Ursache (code-verifiziert, Zeilen aktueller Stand)

`src/output/renderers/alert/render.py`:
- `_val()` (Z. 31–45): hängt bei „gehandhabten" Einheiten (`_HANDLED_UNITS`, Z. 28) über
  `format_metric_value()` **immer** die Einheit an — auch wenn dieselbe Einheit in derselben
  Textzeile mehrfach vorkommt.
- `_email_line()` (Z. 174–179): `{_label(e)} · Schwelle {_val(e, e.threshold)} · {_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)} · {side_label(e)}`
  → 3× `_val()` = 3× Einheit in einer Zeile. Diese Funktion wird sowohl von `render_telegram()`
  (Z. 292, Zeile 2+ je Event) als auch — historisch — konzeptionell dupliziert im Multi-Zweig von
  `render_email()` verwendet.
- `render_email()` Multi-Zweig `data_rows` (Z. 236–240): baut die Zeile inline analog zu
  `_email_line()` (nicht über die Funktion selbst, aber mit demselben 3×`_val()`-Muster) —
  `f"{_label(e)} · Schwelle {_val(e, e.threshold)}"` / `f"{_val(e, e.value_from)} {arrow(e)} {_val(e, e.value_to)} {side_label(e)}"`.
- `render_subject()` Multi-Zweig `top3` (Z. 159–161): `f"{_label(e)} {_val(e, e.value_to)}"` →
  liefert z. B. „Niedersch 14,0 mm" statt „Niedersch 14".
- `_val()` ruft für mm/°C `format_metric_value()` auf (`metric_catalog.py:693-716`), die für
  diese Einheiten **immer** 1 Nachkommastelle mit Komma erzwingt (`"10,0 mm"` auch bei glatten
  Werten) — Designentscheidung der Katalogfunktion für andere Aufrufer (z. B. `format_change_line`),
  hier aber die Rausch-Quelle.

### Lösungsansatz

Neuer lokaler Helper `_num()` in `render.py` (Alert-Renderer-Modul, **nicht** in
`metric_catalog.py`): gibt die Zahl **ohne Einheit** zurück, unter Nutzung von
`get_decimals(e.metric_id)` und `_format_de_thousand`-Logik (Tausender-Punkt), mit
integer-Display wenn der gerundete Wert glatt ist, sonst 1 Nachkommastelle mit Komma. Das ist
dieselbe Rundungslogik wie `_val()` bereits nutzt (Z. 40–45, `formatted = str(int(rounded)) if
float(rounded).is_integer() else str(rounded)` für nicht-gehandhabte Einheiten) — `_num()`
verallgemeinert dieses Muster auf **alle** Einheiten, inklusive der von `format_metric_value()`
gehandhabten (mm, °C, km/h, %, m, km, hPa), ohne diese Katalogfunktion selbst anzufassen.

Betroffene Callsites bauen die Zeile künftig so, dass die Einheit **einmal** angehängt wird
(am letzten/aktuellen Wert bzw. bei der Schwelle nur wenn nötig zur Unterscheidung wie bei `%`):
- `_email_line()` (E-Mail-Multi-Datenblock + Telegram Zeile 2+): `{Kürzel} · Schwelle {_num(thr)}`
  links, `{_num(from)} {Pfeil} {_num(to)} {Einheit}` + über/unter-Kennzeichnung rechts.
- `render_subject()` Top-3: `{Kürzel} {_num(to)}{"%" if unit=="%" else ""}`.
- `render_telegram()` Multi-Zeile: `{Kürzel} {_num(from)}→{_num(to)}{"%" if unit=="%" else ""}`,
  Zeilen mit ` · ` verbunden — **kein** Aufruf mehr von `_email_line()` für den Multi-Telegram-Fall
  (die Struktur unterscheidet sich vom E-Mail-Datenblock: kein „Schwelle"-Text, andere Trennung),
  daher eigener Zeilenaufbau statt Wiederverwendung.

**`format_metric_value()` bleibt unverändert** — sie wird weiterhin von `format_change_line` und
allen Nicht-Alert-Aufrufern genutzt; `_num()` ist ein separater, lokal im Alert-Renderer
gehaltener Pfad (analog zur bestehenden Begründung in `_val()`s Docstring, Z. 34–39).

## Expected Behavior

- **Input:** `AlertMessage` mit ≥2 `AlertEvent`s (Multi-Metrik-Zweig von `render_subject`,
  `render_email`, `render_telegram`).
- **Output:**
  - E-Mail-Datenblock-Zeile: `Böen · Schwelle 50` / `35 ↑ 52 km/h · über` (Einheit genau einmal,
    Schwelle ohne Einheit außer bei `%`).
  - Betreff-Top-3: `Niedersch 14, Gewitter 55%, Böen 52` (nur Zahl, `%` klebt am Wert).
  - Telegram-Zeile 2+: `Niedersch 6→14 · Gewitter 30→55% · Böen 35→52` (kein Einheiten-Text außer
    `%`, kein „Schwelle"-Wort pro Zeile).
  - Glatte Werte ganzzahlig (`10` statt `10,0`), echte Dezimalwerte mit 1 NK und Komma (`0,4`),
    Tausender-Punkt bleibt (`1.230`).
- **Side effects:** keine — reine Rendering-Änderung, kein Persistenz-/Schema-Einfluss.
- **Unverändert:** Einzel-Metrik-Betreff/-Datenblock (`_datablock_single`)/-Verdikt, Onset-Zweig,
  `format_metric_value()` für alle anderen Aufrufer, SMS-Renderer (`render_sms`/`_sms_token`,
  bereits einheitenlos über SMS-Codes).

## Acceptance Criteria

- **AC-1:** Given ein Deviation-Alert mit ≥2 Events (z. B. Böen 35→52 km/h, Schwelle 50) /
  When `render_email()` die Multi-Metrik-Datenblock-Zeile für dieses Event baut / Then lautet die
  Zeile links `Böen · Schwelle 50` (ohne Einheit) und rechts `35 ↑ 52 km/h · über` (Einheit genau
  einmal, am letzten Wert, plus über/unter-Kennzeichnung) — exaktes Vorbild:
  `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html:220-221`.
  - Test: `render_email()` mit Fixture analog `_multi_event_msg()` aufrufen (echter Renderer-Call,
    kein Mock), HTML/Plain-Text auf exakte Teilstrings `"Böen · Schwelle 50"` und
    `"35 ↑ 52 km/h"` bzw. `"über"` prüfen; Einheit `"km/h"` darf in dieser Zeile nur 1× vorkommen.

- **AC-2:** Given ein Event mit glattem Wert (z. B. Niederschlag-Schwelle 10 mm, kein Rest) und
  ein Event mit echtem Dezimalwert (z. B. 0,4 mm) / When die Multi-Metrik-Zeile bzw. der
  Betreff gerendert wird / Then erscheint der glatte Wert ganzzahlig ohne `,0` (`10` statt
  `10,0 mm`), der echte Dezimalwert behält 1 Nachkommastelle mit Komma (`0,4`), und
  Tausender-Werte behalten den Punkt-Trenner (`1.230`).
  - Test: zwei Renderer-Aufrufe mit je einer Fixture (glatter Wert / Dezimalwert), Assertion
    `"10,0" not in output` bei glattem Wert und `"0,4" in output` bei Dezimalwert; zusätzlich
    `format_metric_value("mm", 1230.0)`-Pfad über ein CAPE-artiges Tausender-Fixture auf
    `"1.230"` prüfen.

- **AC-3:** Given ein Deviation-Alert mit 3 Events (Böen 52 km/h, Gewitter 55 %, Niederschlag
  14 mm, alle über Schwelle) / When `render_subject()` den Betreff für ≥2 Events baut / Then
  lautet der Top-3-Teil exakt `Niedersch 14, Gewitter 55%, Böen 52` — nur Zahl, `%` klebt ohne
  Leerzeichen am Wert, `km/h`/`mm` entfallen im Betreff. Vorbild:
  `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html:208`.
  - Test: `render_subject()` mit 3-Event-Fixture (Werte wie oben) aufrufen, Betreff-String auf
    exakten Teilstring `"Niedersch 14, Gewitter 55%, Böen 52"` prüfen.

- **AC-4:** Given dieselbe 3-Event-Nachricht / When `render_telegram()` die Zeile(n) nach der
  fetten Kopfzeile baut / Then lautet die Multi-Zeile im Stil
  `Niedersch 6→14 · Gewitter 30→55% · Böen 35→52` — keine Einheiten außer `%`, kein
  „Schwelle"-Text pro Metrik-Zeile (der Schwellen-Bezug steht in der fetten Kopfzeile
  `N über Schwelle`). Vorbild:
  `docs/design-requests/alert-mail-vorschlaege/Gregor 20 - Alert Mail Vorschläge.html:281`.
  - Test: `render_telegram()` mit 3-Event-Fixture aufrufen, Ausgabe auf exakten Teilstring
    `"Niedersch 6→14 · Gewitter 30→55% · Böen 35→52"` prüfen; sicherstellen, dass `"Schwelle"`
    in dieser Zeile (nicht der fetten Kopfzeile) nicht vorkommt.

- **AC-5:** Given ein Einzel-Metrik-Deviation-Alert bzw. ein Onset-Alert / When
  `render_subject()`/`render_email()`/`render_telegram()`/`render_sms()` dafür aufgerufen werden /
  Then bleiben Betreff, Datenblock (`_datablock_single`), Verdikt und Onset-Ausgabe exakt wie vor
  dieser Änderung (`format_metric_value()` unverändert für alle Aufrufer außer dem neuen
  Multi-Metrik-Pfad in `render.py`).
  - Test: bestehende Suiten `tests/tdd/test_952_alert_mail_design_fidelity.py`,
    `tests/tdd/test_952_onset_alert_fidelity.py::TestAC8RendererParity` und die
    Einzel-Metrik-Klassen in `tests/tdd/test_957_alert_mail_literal_structure.py`
    (`TestSingleEventVerdictAndDatablock`) bleiben grün ohne inhaltliche Anpassung.

- **AC-6:** Given eine Multi-Metrik-Nachricht mit 3 Events / When `render_email()` sowohl den
  HTML- als auch den Plain-Text-Teil baut / Then sind beide strukturgleich: dieselbe Reihenfolge
  Kürzel→Schwelle→Werte, dieselbe Einheit-einmal-Regel, keine HTML-Tags im Plain-Text.
  - Test: `render_email()`-Rückgabe `(html, plain)` beide auf denselben Zahlen-/Kürzel-Inhalt
    prüfen (z. B. `"Böen · Schwelle 50"` in `html` UND in `plain`), `plain` zusätzlich auf
    Abwesenheit von `"<"`/`">"` prüfen (Regressionsschutz analog `test_plain_text_has_no_html_tags`
    aus `test_952_alert_mail_design_fidelity.py`).

## Test-Plan

| Datei | Änderung | Zweck |
|---|---|---|
| `tests/tdd/test_978_deviation_line_readability.py` | CREATE | RED-Tests für AC-1 bis AC-4 und AC-6 (neues Multi-Metrik-Format, echte Renderer-Calls, keine Mocks) |
| `tests/tdd/test_952_alert_mail_design_fidelity.py` | bleibt grün, **keine Änderung erwartet** | Nutzt ausschließlich Einzel-Event-Fixtures (`_cape_msg()`); testet nicht den Multi-Zweig. AC-5-Regressionsanker. |
| `tests/tdd/test_952_onset_alert_fidelity.py::TestAC8RendererParity` | bleibt grün, **keine Änderung erwartet** | Prüft nur Nicht-Leerheit/Struktur (`KM_RE`), keine Werte-Literale. AC-5-Regressionsanker. |
| `tests/tdd/test_957_alert_mail_literal_structure.py` | MODIFY (gezielt, nur betroffene Assertions) | `TestMultiEventVerdictAndDatablock` prüft aktuell nur Struktur (`"3 über Schwelle"`, Zeilenanzahl, Farb-Token) — bleibt vermutlich grün; **falls** eine Assertion versehentlich altes Einheit-Wiederholungsmuster voraussetzt, wird sie auf das neue SOLL nachgezogen (kein Abschwächen, gleich strenge neue Assertion). `TestSingleEventVerdictAndDatablock` (Einzel-Metrik) bleibt unverändert — AC-5-Regressionsanker. |
| `tests/tdd/test_issue_917_alert_renderer.py::test_3events_n_ueber_schwelle_format` | bleibt grün, **keine Änderung erwartet** | Prüft nur Kürzel-Präsenz (`get_alert_label`) und `"Schwelle"`-Text, keine Werte-Literale mit Einheit. |

**Vorgehen:** Neue Testdatei zuerst schreiben (RED gegen aktuelles Verhalten), dann Renderer
implementieren (GREEN), danach alle vier Bestandssuiten vollständig laufen lassen — bei
unerwarteten Fails (altes Format hart codiert) Assertion auf neues SOLL ziehen, niemals
Schwelle/Erwartung lockern.

## Known Limitations

- Der Multi-Metrik-Betreff kürzt weiterhin hart auf Top-3 (`evs[:3]`, unverändert) — bei >3
  Events werden weitere Metriken im Betreff nicht genannt (bestehendes, nicht Teil dieses Fixes).
- `%`-Sonderfall (Einheit klebt am Wert ohne Leerzeichen) ist vorlagengetreu, aber eine
  Sonderregel gegenüber allen anderen Einheiten (die mit Leerzeichen angehängt werden) — bewusst
  aus der Design-Vorlage übernommen, nicht verallgemeinerbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Rendering-/Format-Änderung innerhalb eines bestehenden, bereits durch
  ADR-0011 (#914-Renderer-Konsolidierung) etablierten Moduls — kein neuer Architektur-Grenzfall,
  keine neue Abhängigkeit, keine Schema-/API-Änderung. Der neue `_num()`-Helper folgt demselben
  Muster wie das bereits etablierte `_val()` (lokal gehaltener Alert-Renderer-Pfad statt
  Erweiterung der geteilten `metric_catalog.format_metric_value()`).


## Nachtrag (PO-Entscheidung 2026-07-02, Adversary-Finding F001)

Die Design-Vorlage widerspricht sich (Mockup-Reihenfolge vs. Annotation „Reihenfolge =
Schwere / Im Body führt die kritischste Metrik"). **PO-Entscheidung: Kritischster zuerst,
einheitlich in ALLEN drei Kanälen** (Betreff-Top3, E-Mail-Datenblock, Telegram-Zeile) —
severity-absteigend via bestehendem `_sorted()`; unter-Schwelle-Events bleiben gedämpft
zuletzt. Die AC-3/AC-4-Literale oben wurden entsprechend aktualisiert (PO-approved via
AskUserQuestion mit Vorschau). Zusätzlich F002: `_num()` muss den Tausender-Punkt auch im
Dezimal-Zweig setzen (`1.234,5`).

## Changelog

- 2026-07-02: Initial spec created (Issue #978)
