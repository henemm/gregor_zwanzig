---
entity_id: fix_1472_spaltenkuerzel_legende
type: bugfix
created: 2026-08-04
updated: 2026-08-04
status: draft
version: "1.0"
tags: [reports, compare, email, adr-0042]
---

# Fix #1472: Spaltenkürzel-Legende (ADR-0042-Bedingung erfüllen)

## Approval

- [ ] Approved

## Purpose

ADR-0042 erlaubt englische Kurzformen (`Thdr`, `Visib`, `Feels`, ...) in Spaltenköpfen **unter der
Bedingung**, dass die Auflösung auffindbar ist. Diese Bedingung ist bislang nur im Editor erfüllt.
In der Mail — dort, wo unterwegs tatsächlich gelesen wird — stehen bis zu 22 Kürzel ohne jede
Auflösung. Diese Spec ergänzt eine zweite Legenden-Zeile ("Spalten: Thdr = Gewitter · ...") an
allen vier Ausgabestellen, damit die ADR-Bedingung dort gilt, wo sie wirkt.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `format_units_legend()` (Zeile 344), `build_units_legend()` (Zeile 467)

> Python-Core / Domain-Backend (`src/output/renderers/email/`, `src/output/renderers/`).

## Estimated Scope

- **LoC:** ~90–140
- **Files:** 4 Produktionsdateien + 1–2 Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `format_units_legend()` (`helpers.py:344`) | function | Vorbild für Gruppierungs-/Join-Logik der neuen `format_column_legend()` |
| `derive_row_labels(rows, form)` (`compare_html.py:441`) | function | Einzige Namensquelle Vergleich: `form="short"` = `col_label`, `form="long"` = `label_de` |
| `get_metric_by_col_key()` / `get_metric()` (`app/metric_catalog.py`) | function | Einzige Namensquelle Trip: `MetricDefinition.col_label` / `.label_de` |
| `visible_cols(rows)` (`helpers.py:231`) | function | Sichtbarkeits-Filter Trip (bestehend, unverändert) |
| `_visible_hour_metrics(hourly_metrics)` (`compare_html.py:830`) | function | Sichtbarkeits-Filter Vergleich (bestehend, unverändert) |
| ADR-0042 (`docs/adr/0042-namensform-folgt-der-platzgrenze.md`) | ADR | Erlaubt Kurzformen unter Auflösbarkeits-Bedingung — diese Spec erfüllt die Bedingung |

## Implementation Details

### Eine Zeile oder zwei? — Entscheidung: **zwei**

Die Spec entscheidet sich für **zwei getrennte Zeilen** ("Einheiten: …" und "Spalten: …" statt
einer zusammengeführten Zeile):

1. **Verschiedene Fragen:** "Einheiten" beantwortet *in welcher Maßeinheit steht die Zahl*,
   "Spalten" beantwortet *was bedeutet das Kürzel*. Eine Person, die die Kürzel schon kennt, liest
   nur die erste Zeile; eine Person unterwegs mit ADR-0042-Bedarf nur die zweite.
2. **Die Einheiten-Zeile ist etabliert** (#1237, seit langem live in allen vier Ausgaben in ihrer
   heutigen Form) — sie umzubauen, um Bedeutungen einzuweben, wäre eine unnötige Verhaltensänderung
   an einer Stelle, die niemand als kaputt gemeldet hat.
3. **Eine zusammengeführte Zeile würde bei voller Metrik-Auswahl (22 Spalten) sehr lang** — getrennt
   bleibt wenigstens die Einheiten-Zeile kurz, auch wenn die Spalten-Zeile wächst.

### Neuer gemeinsamer Formatierer (Kern-Analogie zu `format_units_legend`)

`helpers.py`, direkt neben `format_units_legend()`:

```python
def format_column_legend(label_pairs: list[tuple[str, str]]) -> str:
    """Analog format_units_legend: 'Spalten: Thdr = Gewitter · Visib = Sichtweite'.
    Paare mit identischem Kuerzel/Name (case-insensitive) entfallen. Reihenfolge
    = Eingabereihenfolge (= Sichtbarkeits-Reihenfolge der Aufrufer)."""
```

Filterregel (PO-Entscheidung 2026-08-04, gemessen — siehe "Verworfene Alternative" unten):
auflösen, **außer** Kürzel und Name sind identisch (`short.strip().lower() == long.strip().lower()`).
Keine Pflegeliste, keine Präfix-Heuristik.

### Vier Ausgabestellen — zwei Wege, ein Kern

| Ausgabe | Bestehender Weg | Änderung |
|---|---|---|
| Trip HTML (`html.py:1565`) | `build_units_legend(all_rows)` | + `build_column_legend(all_rows)` (neu, `helpers.py`, neben `build_units_legend`), Ergebnis analog `legend_text` in `_render_footer()` (Parameter bei Zeile 468) rendern |
| Trip Klartext (`plain.py:315`) | `build_units_legend(all_rows)` | + `build_column_legend(all_rows)`, als zweite Zeile nach der bestehenden `legend_text`-Zeile (Zeile 316–317) |
| Vergleich HTML (`compare_html.py:1241`) | `_units_legend_text(...)` in `_render_units_legend()` | neue `_column_legend_text(visible)` (neben `_units_legend_text`, Zeile 1221) und zweiter `<div>` in `_render_units_legend()` bzw. `_render_legend()` (Zeile 1259 `units`-Variable erweitern) |
| **Vergleich Klartext** (`comparison.py`) | **keine Legende vorhanden** | **neu:** `_units_legend_text` und `_column_legend_text` aus `compare_html` importieren (Import-Block Zeile 30–35 erweitern) und mit `_visible_hour_metrics(hourly_metrics)` aufrufen — Ergebnis als zwei Zeilen nach dem Stundenverlauf-Block einfügen (vor der `"---"`-Fußzeile, Zeile 316) |

🔴 **Korrektur nach dem RED-Lauf (2026-08-04): Das Kürzel der Legende MUSS aus derselben
Ableitung stammen wie der Spaltenkopf — nicht aus dem Katalog.**

`derive_row_labels()` hängt bei gleichlautender Kurzform einen Auswertungs-Zusatz an
(`compare_html.py:493-500`: `mehrfach` → `row["aggregation"]`), und **genau daraus entsteht die
Spaltenüberschrift** (`compare_html.py:356-357`). Nähme die Legende stattdessen `col_label` direkt
aus dem Register, stünde bei zwei Temperatur-Auswertungen `Temp max` im Kopf, aber `Temp =
Temperatur` in der Legende — sie erklärte ein Kürzel, das in der Tabelle nicht vorkommt, und
verfehlte damit ihren Zweck.

- **Vergleich:** `_column_legend_text(visible)` bildet die Paare aus
  `derive_row_labels(visible, form="short")` **und** `derive_row_labels(visible, form="long")` —
  positionsgleich gezippt. Bei Kollision ergibt das korrekt
  `Temp max = Temperatur Maximum` (die Langform trägt denselben Zusatz, `aggregation_label_de`).
- **Trip:** `build_column_legend(rows)` nimmt das **`label` aus `visible_cols(rows)`** als Kürzel
  (das ist der gerenderte Spaltenkopf, `helpers.py:231-237`) und
  `get_metric_by_col_key(col_key).label_de` als Namen.

**Keine zweite Namensquelle:** beide Wege lesen `col_label`/`label_de` aus derselben
`MetricDefinition` im zentralen Register (`app/metric_catalog.py`) — nichts wird neu getippt. Neu
ist nur, dass das **Kürzel** dem Kopf entnommen wird statt dem Register, damit beide
deckungsgleich sind.

### Verworfene Alternative (nicht erneut vorschlagen)

Erste Fassung der Abgrenzungsregel: "auflösen, wenn das Kürzel **kein Präfix** des Langnamens
ist." Gemessen an `derive_row_labels(CV2_METRICS, "short")` vs. `"long"` (27 Einträge): trifft
**24 von 27** — praktisch alles, weil Kurzform englisch und Langname deutsch sind (zwischen `Rain`
und `Niederschlag` besteht nie eine Präfix-Beziehung). Verworfen zugunsten der Identitäts-Regel.

## Expected Behavior

- **Input:** dieselben Zeilen-/Metrik-Listen, die die bestehende Einheiten-Zeile bereits erhält
  (`all_rows` bzw. `_visible_hour_metrics(hourly_metrics)`) — keine neue Eingabe.
- **Output:** eine zusätzliche Zeile `Spalten: <Kürzel> = <Name> · ...` unmittelbar unter/neben der
  bestehenden Einheiten-Zeile, in allen vier Ausgaben inhaltsgleich für dieselbe Metrik-Auswahl.
  Leer (keine Zeile), wenn nach Filterung nichts übrig bleibt (z. B. nur `Wind` sichtbar).
- **Side effects:** keine — reine Anzeige-Ergänzung, keine Datenmodell-Änderung.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit sichtbaren Stunden-Spalten `Thdr` und `Visib` / When die
  HTML-Vergleichsmail gerendert wird / Then enthält sie die Zeile `Spalten: Thdr = Gewitter ·
  Visib = Sichtweite` unter der Einheiten-Zeile.
  - Test: gerenderte HTML-Ausgabe von `render_compare_html(...)` (bzw. echte Staging-Mail über
    `email_spec_validator.py`) auf das sichtbare Textfragment prüfen — kein Quelltext-Grep.

- **AC-2:** Given dieselbe Ortsvergleichs-Konstellation wie AC-1 / When der **Klartext**-Teil
  derselben Mail gerendert wird / Then enthält er dieselben zwei Zeilen (`Einheiten:` und
  `Spalten:`) mit denselben Paaren wie der HTML-Teil — heute existiert dort noch keine Zeile.
  - Test: gerenderter Rückgabewert von `render_compare_email(...)[1]` (Plain-Text-Teil) auf beide
    Zeilen prüfen.

- **AC-3:** Given ein Trip-Briefing (voll oder kompakt) mit sichtbaren Spalten `Feels` und `Dew` /
  When HTML **und** Klartext gerendert werden / Then enthalten beide dieselbe Zeile `Spalten:
  Feels = Gefühlte Temperatur · Dew = Taupunkt`.
  - Test: gerenderte Ausgabe beider Trip-Renderer-Pfade (`html.py`, `plain.py`) auf das
    Textfragment prüfen; entspricht dem A/B-Vergleich, den #1453 bereits für die Namensformen
    etabliert hat.

- **AC-4:** Given eine Metrik-Auswahl, in der `Wind` sichtbar ist (Kürzel `Wind`, Name `Wind`) /
  When die Legende gerendert wird / Then erscheint `Wind` **nicht** im `Spalten:`-Teil (weder in
  Trip- noch in Vergleichs-Ausgabe) — Kürzel und Name sind identisch.
  - Test: gerenderte Ausgabe auf Abwesenheit von `Wind =` im `Spalten:`-Segment prüfen, bei
    gleichzeitiger Anwesenheit von `Wind` in der `Einheiten:`-Zeile (die bleibt unverändert).

- **AC-5:** Given zwei Renderläufe derselben Mail mit unterschiedlicher Metrik-Auswahl (Lauf A:
  `Thdr` sichtbar, Lauf B: `Thdr` abgewählt) / When beide gerendert werden / Then enthält nur
  Lauf A die Auflösung `Thdr = Gewitter`; in Lauf B fehlt sie vollständig, auch wenn `Thdr`
  weiterhin Teil des zentralen Katalogs ist.
  - Test: zwei Renderläufe mit unterschiedlichen `hourly_metrics`/`enabled_metrics` vergleichen,
    nicht nur einen Lauf gegen eine feste Erwartung prüfen (Wirkungsnachweis, kein Fähigkeitstest).

- **AC-6:** Given ein Register-Eintrag mit geändertem `label_de` (z. B. testweise
  `"Gewitter"` → `"Gewittergefahr"`) / When dieselbe Mail erneut gerendert wird / Then ändert sich
  die `Spalten:`-Zeile entsprechend, ohne dass eine zweite, separat gepflegte Namensliste
  angefasst wird.
  - Test: Katalog-Eintrag zur Laufzeit patchen (Fixture, kein Mock-Theater — reale
    `MetricDefinition`-Instanz mit geändertem Feld), Rendern, Textfragment vergleichen. Beweist
    "keine zweite Namensquelle" als Wirkung, nicht als Mechanismus-Behauptung.

- **AC-7:** Given dieselbe Metrik-Auswahl in allen vier Ausgabestellen (Trip HTML, Trip Klartext,
  Vergleich HTML, Vergleich Klartext) / When alle vier gerendert werden / Then nennen alle vier
  exakt dieselben Kürzel-Name-Paare in derselben Reihenfolge — keine Drift zwischen den Pfaden.
  - Test: vier Renderläufe mit identischer Eingabe, Textfragmente paarweise vergleichen
    (A/B-Vergleich der Ausgaben, nicht Vergleich der aufgerufenen Funktionsnamen).

- **AC-8 (ergänzt 2026-08-04 nach dem RED-Lauf):** Given eine Metrik-Auswahl mit **zwei
  Auswertungen derselben Größe** (z. B. Temperatur Maximum **und** Minimum), sodass der
  Spaltenkopf den Auswertungs-Zusatz trägt (`Temp max` / `Temp min`) / When die Legende gerendert
  wird / Then nennt sie **exakt diese** Kürzel (`Temp max = Temperatur Maximum`) — nicht die
  zusatzlose Registerform. Kein Kürzel steht in der Legende, das im Tabellenkopf fehlt, und
  umgekehrt.
  - Test: Auswahl mit kollidierender Kurzform rendern, die Kürzel aus **Tabellenkopf** und aus
    **Legende** einsammeln und als Mengen vergleichen — Gleichheit behaupten, nicht Teilmenge.
    Trefferzahl > 0 mitbehaupten, sonst ist die Aussage bei leerer Auswahl wahr.
  - Begründung: Ohne diesen AC erklärt die Legende ein Kürzel, das es in der Tabelle nicht gibt —
    der Zweck der ADR-0042-Bedingung wäre verfehlt. Gefunden vom RED-Lauf, bevor Code entstand.

## Was sich NICHT ändert

- **Spaltenköpfe bleiben englisch** — ADR-0042 bestätigt (#862, #849). Diese Spec löst die
  Auflösungs-Pflicht über eine zusätzliche Legenden-Zeile, nicht über deutsche Spaltenköpfe.
- **Die Einheiten-Zeile behält ihre bisherige Form** (`Einheiten: Temp, Feels °C · Wind km/h`) —
  keine Umbau, keine Zusammenlegung mit der neuen Zeile.
- **Kein Emoji, keine Farbe als alleiniger Bedeutungsträger** (Design-Leitprinzip Lesbarkeit) — die
  neue Zeile ist reiner Text, analog der bestehenden Einheiten-Zeile.

## Known Limitations

- **Klartext-Zeilenlänge:** Bei voller Metrik-Auswahl (bis zu 22 Spalten) wird die `Spalten:`-Zeile
  im Klartext lang und bricht ggf. ungünstig um. Kein Umbruch-Mechanismus in dieser Spec — bei
  üblicher Auswahl (5–8 Spalten, PO-Vorschau) unproblematisch; Nachbesserung wäre ein eigenes
  Follow-up, kein Blocker hier.
- **Redundante Paare bewusst in Kauf genommen:** Die Identitäts-Regel erzeugt vereinzelt Paare, bei
  denen Kürzel und Name sich stark ähneln, aber nicht identisch sind (`UV = UV-Index`, `Temp max =
  Temperatur Maximum`). Das ist der gemessene, akzeptierte Preis dafür, dass keine Pflegeliste
  entsteht (siehe "Verworfene Alternative").
- **Einheitenlose Größen erscheinen nur in der Spalten-Zeile** (`Thdr` hat keine Einheit und fehlt
  daher in `Einheiten:`, steht aber in `Spalten:`). Das entspricht der freigegebenen Vorschau, war
  aber nirgends als Regel notiert — hiermit festgehalten.
- **AC-4 „die Einheiten-Zeile bleibt unverändert" gilt nur für Trip und Vergleich-HTML.** Im
  Vergleichs-**Klartext** gibt es heute keine Zeile, die bleiben könnte; dort entsteht sie neu
  (AC-2). Kein Bestandsschutz, sondern Neubau.
- **#1453-AC-7-Nachweis ist ein Quelltext-Test:** Der bestehende Nachweis, dass alle drei
  Namensformen (`label`, `col_label`, `sms_code`) in den vier Compare-Editoren vorkommen, prüft nur
  *Vorkommen im Code* (Svelte-Compiler-Scan), nicht *Sichtbarkeit am Bildschirm* — nach der Lehre
  aus #1436 (Tabelle "vorhanden", am Handy real unsichtbar) ist das eine bekannte Lücke. Diese Spec
  behebt sie nicht, benennt sie aber als Pflichtpunkt der **Staging-Verifikation**: bei der
  E2E-Verifikation dieser Lieferung ist ein Blick auf die real gerenderte Mail (nicht nur der
  automatisierte Validator-Lauf) Teil des Nachweises für AC-1 bis AC-3.

## Gates

- **Renderer-Commit-Gate #811 (un-überspringbar):** Diese Änderung staged
  `src/output/renderers/email/helpers.py`, `html.py`, `plain.py`, `compare_html.py` und
  `src/output/renderers/comparison.py` — alle im Gate-Perimeter. Der Commit blockt, bis im aktiven
  Workflow **beide** frisch vorliegen: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py`
  grün **und** ein erfolgreicher `briefing_mail_validator.py`-Lauf.
- **Zwei Mail-Validatoren, zwei Pfade** (CLAUDE.md-Dispatch):
  - Trip-Briefing (`X-GZ-Mail-Type: trip-briefing`) → `uv run python3
    .claude/hooks/briefing_mail_validator.py`
  - Ortsvergleich (`X-GZ-Mail-Type: compare`) → `uv run python3
    .claude/hooks/email_spec_validator.py`
  Beide gegen eine **echt zugestellte** Staging-Mail (`gregor-test@henemm.com`), kein Mock.
- **`email_spec_validator.py` braucht bei Beschriftungsänderungen PO-`override`** (belegt in
  #1453) — die neue `Spalten:`-Zeile ist eine Beschriftungsänderung; rechtzeitig ankündigen, bevor
  der Validator-Lauf ansteht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0042 (bestehend, keine neue ADR nötig)
- **Rationale:** ADR-0042 erlaubt englische Kurzformen unter der Bedingung auffindbarer Auflösung.
  Diese Spec erfüllt exakt diese Bedingung an der Stelle, an der sie bislang unerfüllt war (Mail
  statt nur Editor) — sie ändert die Grundsatzentscheidung (Kurzform in Spaltenköpfen) nicht,
  sondern schließt die Lücke in ihrer Umsetzung.

## Changelog

- 2026-08-04: Initial spec created
