---
entity_id: feat_1848_b_einheiten_register
type: refactor
created: 2026-08-18
updated: 2026-08-18
status: draft
version: "1.0"
workflow: feat-1848-b-einheiten-register
tags: [compare, mail, metric-catalog, refactor, issue-1848, epic-1435]
---

# Eine Quelle für Einheit und Nachkommastellen in der Ortsvergleichs-Übersicht (Issue #1848, Scheibe B)

## Approval

- [x] Approved — PO-Freigabe Henning, 2026-08-18

## Purpose

Die Übersichtstabelle der Ortsvergleichs-Mail (`CV2_METRICS`,
`src/output/renderers/email/compare_html.py:314-380`) tippt für 22 von 26
Zeilen eine `"unit"` und für 2 Zeilen zusätzlich `"decimals"` fest ein —
obwohl das zentrale Wetter-Register `src/app/metric_catalog.py` beide Werte
pro `MetricDefinition` bereits führt (`unit`, `decimals`). Das ist dieselbe
Klasse Dopplung, die #1401 Scheibe A2b bereits für das Feld `"label"` beendet
hat: eine zweite, unabhängig gepflegte Kopie derselben Fachinformation, die
künftig auseinanderlaufen könnte, ohne dass ein Test es bemerkt. Diese
Scheibe leitet `unit`/`decimals` zur Renderzeit aus dem Register ab, statt
sie einzutippen. Für den Nutzer ändert sich **nichts sichtbar** — gemessen
0 Einheiten-Abweichungen über alle 22 Zeilen, `decimals=1` stimmt für beide
betroffenen Zeilen (`precip_sum`, `sunny_hours`) mit dem Register überein.

## Source

- **File:** `src/output/renderers/email/compare_html.py:472-533` —
  `derive_row_labels(rows, form)`. Bestehende Funktion (#1401 A2b), die
  Zeilen-**Kopien** mit einem aus `get_metric(metric_id)` abgeleiteten
  `"label"` zurückgibt. **Wird erweitert:** dieselbe Ableitung hängt jetzt
  zusätzlich `"unit"` und `"decimals"` an die Kopie an — für Zeilen mit
  `metric_id` und wenn die Zeile das Feld nicht bereits über ein eigenes
  `"fmt"` umgeht (s. unten).
  - `_base()` (Zeile 517-521) liefert bereits das `MetricDefinition`-Objekt
    über `get_metric(row["metric_id"])`, wenn `row.get("metric_id")` gesetzt
    ist — dieselbe Stelle liest zusätzlich `metric.unit` und
    `metric.decimals`.
  - Die Rückgabe-Zeile (532: `out.append({**row, "label": label})`) wird zu
    `out.append({**row, "label": label, **derived_unit_decimals})` bzw.
    äquivalent — weiterhin eine **Kopie** über `{**row, ...}`, `CV2_METRICS`
    bleibt unangetastet (identisches Prinzip wie das bestehende `"label"`).
  - Zeilen ohne `metric_id` (Warn-Zeile, `key="warn"`) behalten ihr
    bisheriges Verhalten unverändert — sie tragen ohnehin kein `"unit"`.
  - Zeilen mit eigenem `"fmt"` (`thunder_max`, `visibility_min`,
    `precip_type`) tragen im Modul-Dict schon heute kein `"unit"`; die
    Ableitung darf dort nichts anhängen, was `_fmt_metric` nie liest (ihr
    `fmt`-Zweig in `_render_overview_row:763-764` ruft `_fmt_metric` gar
    nicht auf) — funktional wirkungslos, aber zur Klarheit: kein neues Feld
    für diese 3 Zeilen einführen, das dort nie gelesen wird.
- **File:** `src/output/renderers/email/compare_html.py:314-380` —
  `CV2_METRICS`. 22 Einträge verlieren das getippte `"unit"`, die 2 Einträge
  `precip_sum` (Zeile 320-321) und `sunny_hours` (Zeile 326-327) zusätzlich
  `"decimals"`. Die 3 `"fmt"`-Zeilen, die Warn-Zeile und alle übrigen Felder
  (`"key"`, `"metric_id"`, `"aggregation"`, `"sev"`) bleiben unverändert.
  Der erklärende Kommentarblock direkt darüber (Zeile 299-313) wird auf den
  neuen Stand gebracht (analog zur A2b-Ergänzung in Zeile 310-313).
- **File:** `src/output/renderers/email/compare_html.py:713-719` —
  `_fmt_metric(value, decimals, unit)`. **Unverändert.** Bleibt die einzige
  Formatierfunktion für die Zeilen ohne eigenes `"fmt"`.
- **File:** `src/output/renderers/email/compare_html.py:766` — einzige
  Leseseite: `text = _fmt_metric(value, m.get("decimals"), m.get("unit",
  ""))` innerhalb `_render_overview_row()`. **Unverändert.** `m` ist hier
  bereits eine von `derive_row_labels()` zurückgegebene Kopie (Aufrufkette:
  `_visible_metrics()` Zeile 797/800 → `derive_row_labels(..., form="long")`
  → `_render_overview_table()` Zeile 833 `for m in visible` →
  `_render_overview_row(m, ...)`), trägt die neuen Felder also bereits, ohne
  dass diese Zeile etwas davon wissen muss.

> **Schicht-Hinweis:** Reiner Python-Core-Umbau
> (`src/output/renderers/email/`). Keine Änderung an `frontend/`,
> `internal/`, `cmd/` oder `comparison.py` (Klartext-Zweig, s. „Out of
> Scope").

## Estimated Scope

- **LoC:** ca. −15 bis +30 Produktiv (`compare_html.py`), überwiegend
  Entfernungen in `CV2_METRICS` gegen eine kleine Ergänzung in
  `derive_row_labels()`. Deutlich unter dem Workflow-Limit 250.
- **Files:** 1 Produktionsdatei geändert, 1 neue Testdatei, 1 Spec.
- **Effort:** low — reine Ableitung an bereits vorhandener Stelle, kein neues
  Fachverhalten; das Risiko liegt in der Gedankenstrich-Falle (s.
  „Verworfene Alternativen") und im Kopie-vs.-Mutation-Prinzip.

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.metric_catalog.get_metric` | reused, unverändert | Liefert `MetricDefinition.unit`/`.decimals` — bereits von `derive_row_labels()` für `.label_de`/`.col_label` genutzt |
| `output.renderers.email.compare_html.derive_row_labels` | erweitert | Bestehende Ableitungsfunktion (#1401 A2b), bekommt zwei zusätzliche Felder in der Rückgabe-Kopie |
| `output.renderers.email.compare_html._fmt_metric` | upstream, unverändert | Formatiert weiterhin `(value, decimals, unit)` — liest nur, woher die Werte kommen ist ihr egal |
| `output.renderers.comparison._CV2_BY_KEY`/`derive_row_labels`-Aufruf (Zeile 124, 240-242) | upstream, unverändert | Klartext-Zweig ruft dieselbe Funktion, liest aber nur `row["label"]` — die neuen Felder sind additiv und werden dort nicht gelesen |
| `output.metric_format.format_value` | explizit NICHT eingemeindet | Der geteilte, katalog-getriebene Formatierer — bewusst NICHT Ersatz für `_fmt_metric` in dieser Scheibe, s. „Verworfene Alternativen" |
| `docs/specs/modules/feat_1373_s2_ein_katalog.md` | Kontext | Hält fest, dass `COMPARE_METRIC_CATALOG` (ein anderes Objekt als `CV2_METRICS`) kuratiert bleibt — betrifft diese Scheibe nicht, s. Analyse im Kontext-Dokument |

## Implementation Details

```
derive_row_labels(rows, form):
    for row in rows:
        if not row.get("metric_id"):
            copy = {**row, "label": <bestehende Logik>}
        else:
            metric = get_metric(row["metric_id"])
            copy = {
                **row,
                "label": <bestehende Logik>,
                "unit": metric.unit,
                "decimals": metric.decimals,
            }
        out.append(copy)
    return out
```

1. **Kopie, nicht Mutation.** Wie beim bestehenden `"label"` gilt
   `{**row, ...}` — `row` selbst (ein Element aus `CV2_METRICS`) wird nicht
   verändert. Das ist die zentrale Zusicherung dieser Scheibe: ein zweiter
   Renderpfad, der auf demselben Modul-Dict aufsetzt (aktuell:
   `comparison.py`, potenziell künftig weitere), darf niemals mutierte
   Daten vorfinden.
2. **`metric.unit`/`metric.decimals` überschreiben, nicht ergänzen.** Für
   Zeilen mit `metric_id` ersetzt die Ableitung ein eventuell noch im
   Quell-Dict vorhandenes `"unit"`/`"decimals"` vollständig durch den
   Register-Wert — nach dieser Scheibe steht in `CV2_METRICS` selbst aber
   ohnehin keines dieser Felder mehr (sie werden entfernt, nicht nur
   überschrieben).
3. **`decimals=None` bleibt `None`.** Für die 20 Zeilen, die im Register
   kein `decimals` führen (`MetricDefinition.decimals: Optional[int] =
   None`), liefert die Ableitung `None` — `_fmt_metric` behandelt das bereits
   heute wie `0` (Zeile 716: `decimals if decimals is not None else 0`).
   Keine Verhaltensänderung.
4. **Zeilen mit eigenem `"fmt"` unangetastet lassen.** `thunder_max`,
   `visibility_min`, `precip_type` haben `metric_id` gesetzt (für die
   Verknüpfungsprüfung, `test_compare_mail_metric_link_completeness.py`),
   ihr `fmt`-Zweig in `_render_overview_row()` ruft aber `_fmt_metric`
   nicht auf (Zeile 763-764: `elif fmt_fn: text = fmt_fn(value)`) — ob die
   Ableitung ihnen `unit`/`decimals` anhängt oder nicht, ist ohne
   beobachtbare Wirkung. Die Implementierung hängt sie aus Konsistenz
   trotzdem an (dieselbe unbedingte Logik für alle Zeilen mit `metric_id`),
   ein Test darf sich aber NICHT darauf verlassen, dass diese 3 Zeilen ein
   bestimmtes `unit`/`decimals` zeigen — sie zeigen weiterhin, was ihr
   `fmt`-Zweig produziert.
5. **`form="short"`-Aufrufe (Stundentabelle, Zeile 938/942/1396) bleiben
   unberührt.** Sie iterieren über `HOUR_METRICS`, nicht über `CV2_METRICS`
   — die Erweiterung greift nur dort, wo `row.get("metric_id")` gesetzt ist,
   unabhängig von `form`, ändert aber nichts an Zeilen, die dort ohnehin
   schon `unit`/`decimals` über einen anderen Mechanismus lösen
   (`format_value(..., style="bare")`, s. Kontext-Dokument „Existing
   Patterns").
6. **Kommentarblock aktualisieren.** Zeile 299-313 beschreibt den heutigen
   Stand von `CV2_METRICS` inklusive `"unit"`/`"decimals"` — wird auf den
   neuen Stand gebracht, analog zur A2b-Ergänzung.

## Expected Behavior

- **Input:** `CV2_METRICS`-Zeilen (mit oder ohne `metric_id`), `form` wie
  bisher (`"short"`/`"long"`).
- **Output:** `derive_row_labels()` liefert für jede Zeile mit `metric_id`
  eine Kopie mit `"unit"` = `get_metric(metric_id).unit` und `"decimals"` =
  `get_metric(metric_id).decimals`, zusätzlich zum bestehenden `"label"`.
  Zeilen ohne `metric_id` unverändert. `CV2_METRICS` selbst bleibt nach dem
  Aufruf identisch zum Zustand davor (keine `"unit"`/`"decimals"`-Schlüssel
  mehr, weder vorher noch nachher, da entfernt).
- **Side effects:** keine — reine Funktion, kein I/O, keine Mutation der
  Eingabe (identisch zum heutigen Verhalten für `"label"`).

## Acceptance Criteria

- **AC-1:** Given eine gerenderte Ortsvergleichs-Übersichtstabelle (HTML)
  für eine Zeile ohne eigenes `"fmt"` (z. B. `wind_max`), When die Mail für
  Orte mit einem konkreten Windwert gerendert wird, Then zeigt die Zelle
  dieselbe Einheit wie vor dieser Änderung (`"km/h"`, mit Leerzeichen vor der
  Einheit gemäß `_fmt_metric:719`) — geprüft an der gerenderten Mail, nicht
  am Rückgabewert von `derive_row_labels()` allein.
  - Test: `tests/unit/test_compare_mail_metric_format_from_register.py`,
    HTML-String der gerenderten Übersichtstabelle nach `"km/h"` in der
    `wind_max`-Zeile durchsucht.

- **AC-2:** Given die Zeilen `precip_sum` und `sunny_hours`, deren einziges
  Registermerkmal `decimals=1` war, When die Mail mit Werten gerendert wird,
  die eine Nachkommastelle sichtbar machen (z. B. `precip_sum_mm=12.34`),
  Then zeigt die gerenderte Zelle `"12.3 mm"` — nicht `"12 mm"` — die
  Nachkommastelle bleibt exakt so erhalten wie vor der Ableitung.
  - Test: derselbe Testfile, `precip_sum`- und `sunny_hours`-Zeile je mit
    einem Wert mit erkennbarer Nachkommastelle geprüft.

- **AC-3:** Given ein Ort ohne Wert für eine numerische Zeile ohne eigenes
  `"fmt"` (z. B. `value is None`), When die Übersichtszelle gerendert wird,
  Then zeigt sie exakt das EM-DASH-Zeichen `"—"` (U+2014) — nicht `"–"`
  (U+2013, EN DASH) und nicht `"-"` (ASCII-Bindestrich) — geprüft per
  Codepoint-Vergleich am gerenderten HTML, nicht per Sichtprüfung.
  - Test: derselbe Testfile, `ord()`-Prüfung auf den Platzhalter in der
    Zelle; zusätzlich eine Negativ-Prüfung, dass `"–"` (U+2013) NICHT in der
    betroffenen Zelle vorkommt.

- **AC-4:** Given der Aufruf `derive_row_labels(CV2_METRICS, form="long")`
  wurde bereits einmal ausgeführt (z. B. durch das Rendern einer Mail),
  When anschließend direkt auf die Modul-Konstante `CV2_METRICS`
  zugegriffen wird, Then trägt kein Element von `CV2_METRICS` einen
  `"unit"`- oder `"decimals"`-Schlüssel — die Ableitung hat ausschließlich
  auf der zurückgegebenen Kopie gearbeitet, die Modul-Konstante ist
  unverändert.
  - Test: derselbe Testfile, nach einem `derive_row_labels()`-Aufruf wird
    für jede Zeile aus `CV2_METRICS` mit `metric_id` geprüft, dass
    `"unit" not in row` und `"decimals" not in row` gilt.

- **AC-5:** Given die drei Zeilen mit eigenem `"fmt"` (`thunder_max`,
  `visibility_min`, `precip_type`) und die Warn-Zeile (`key="warn"`), When
  die Übersichtstabelle für Orte mit Werten in diesen Zeilen gerendert wird,
  Then zeigen die Zellen exakt dieselbe Ausgabe wie vor dieser Änderung —
  ihr jeweiliger `fmt`-Zweig (`_fmt_thunder`, `_fmt_visibility_overview`,
  `_fmt_precip_type`, `_render_warn_cell`) bleibt der alleinige Formatierer,
  unbeeinflusst von der neuen Ableitung.
  - Test: derselbe Testfile, für alle vier Zeilen ein Vorher/Nachher-
    Vergleich (Referenzwert fest im Test hinterlegt, aus dem aktuellen
    Verhalten übernommen) am gerenderten HTML.

- **AC-6:** Given der Klartext-Zweig der Ortsvergleichs-Mail
  (`comparison.py`, ruft `derive_row_labels(..., form="long")` über
  dieselbe Funktion auf, Zeile 240-242), When die Mail als Klartext
  gerendert wird, Then läuft der Aufruf ohne Fehler durch und die Zeile
  zeigt weiterhin `row["label"]` — die zusätzlichen Felder `"unit"`/
  `"decimals"` in der Rückgabe-Kopie werden vom Klartext-Zweig nicht
  gelesen und brechen ihn nicht.
  - Test: bestehender Paritäts-Test
    `test_compare_mail_plaintext_html_label_parity.py` läuft nach dem Umbau
    unverändert grün (kein Diff an seinen Assertions); zusätzlich ein Fall
    im neuen Wächter, der den Klartext-Renderer direkt aufruft und auf
    Fehlerfreiheit sowie unveränderten Zellinhalt prüft.

- **AC-7:** Given eine Vollständigkeits-Prüfung über alle Zeilen aus
  `CV2_METRICS` mit gesetztem `metric_id`, When jede dieser Zeilen einzeln
  mit einem Wert gerendert wird, der eine Nachkommastelle sichtbar machen
  würde, Then stimmt für jede Zeile die gerenderte Einheit und
  Nachkommastellen-Darstellung exakt mit dem Verhalten überein, das
  `_fmt_metric` vor dieser Änderung mit dem seinerzeit getippten
  `"unit"`/`"decimals"` erzeugt hätte (feste Erwartungswerte im Test,
  entnommen aus dem heutigen `CV2_METRICS`-Stand, nicht aus dem Prüfling
  selbst abgeleitet).
  - Test: `tests/unit/test_compare_mail_metric_format_from_register.py`,
    parametrisiert über alle 22 Zeilen mit `metric_id` und ohne eigenes
    `"fmt"`, echte `ForecastDataPoint`/`LocationResult`-Fixtures (kein
    Mock), Vorbild `test_compare_mail_label_source_catalog.py`.

## Verworfene Alternativen

**Variante B — Leseseite (Zeile 766) direkt auf
`format_value(metric_id, value, style="plain")` umstellen, `_fmt_metric`
entfällt.** Wurde geprüft und verworfen:

- Sie bringt die **Gedankenstrich-Änderung** ungefragt ins Spiel:
  `format_value` liefert bei fehlendem Wert `"–"` (U+2013 EN DASH,
  `src/output/metric_format.py:65`, `_NO_VALUE`), `_fmt_metric` dagegen
  `"—"` (U+2014 EM DASH, verifiziert per Hexdump: `e2 80 94` vs. `e2 80
  93`). `"—"` ist in `compare_html.py` das **durchgängige**
  Platzhalter-Zeichen — nicht nur in `_fmt_metric:715`, sondern auch in
  `_fmt_thunder` (Zeile 232/234), `_fmt_precip_type` (271/273),
  `_fmt_visibility_overview` (285), weiteren Helfern (179/183/191/195/201),
  der Warn-Zelle (736) und dem Fallback (1466). Variante B mischte erstmals
  **zwei verschiedene Striche innerhalb derselben Tabelle**, obwohl der
  Auftrag „für Nutzer ändert sich nichts sichtbar" lautet.
- Sie erzeugte eine **Teil-Migration**: 19 von 22 Zeilen liefen über
  `format_value`, 3 (`thunder_max`, `visibility_min`, `precip_type`) blieben
  bei ihrem eigenen `fmt` — eine Asymmetrie im Code ohne Gegenwert, weil
  diese drei Zeilen ohnehin nie über `_fmt_metric` liefen.
- Die vollständige Ablösung von `_fmt_metric` durch `format_value` ist ein
  eigenes, größeres Vorhaben (u. a. `display_unit`-Konvertierung für
  `visibility`, die `format_value` beherrscht, `_fmt_visibility_overview`
  aber eigenständig löst) und verdient eine eigene Spec, keinen
  Nebeneffekt dieser Scheibe.

**Entschieden: Variante A.** `derive_row_labels()` wird um `unit`/`decimals`
erweitert, `_fmt_metric` und die Leseseite (Zeile 766) bleiben unverändert.
Damit stellt sich die Gedankenstrich-Frage in dieser Scheibe praktisch nicht
— sie wird trotzdem hier festgehalten, damit eine künftige Migration sie
nicht stillschweigend falsch entscheidet (s. AC-3, Test Plan Mutation 3).

## Test Plan

Neue Testdatei `tests/unit/test_compare_mail_metric_format_from_register.py`.
**Pflicht:** alle Wächter prüfen an der **gerenderten Mail** (HTML-String
bzw. Klartext-Zeile), nicht an `derive_row_labels(...)[i]["unit"]` allein —
ein Test, der nur die zurückgegebene Kopie liest, beweist nicht, dass Zeile
766 sie tatsächlich verwendet, sondern nur, dass die Kopie existiert.

**Mutations-Gegenprobe (Pflicht für die TDD-Phase, aus der Analyse
übernommen):**

1. **Nachkommastellen** — Ableitung liefert immer `0` statt
   `metric.decimals`: `precip_sum_mm=12.34` muss in der Mail `12.3 mm`
   zeigen; die Mutation erzeugt `12 mm`. *Wichtigster Fall* — ein Test, der
   nur die Kopie prüft, fängt ihn NICHT, falls Zeile 766 die Kopie am Ende
   gar nicht liest. → AC-2, AC-7.
2. **Einheit vertauscht** — `wind` bekommt `"°C"` statt `"km/h"`
   zurückgeliefert: die gerenderte Mail muss weiterhin `"km/h"` zeigen
   (z. B. `"42 km/h"`), nicht `"42°C"`. → AC-1, AC-7.
3. **Gedankenstrich-Regression** — bei fehlendem Wert wird `"–"` (EN DASH)
   statt `"—"` (EM DASH) zurückgegeben: Prüfung am HTML per Codepoint (`—`
   vorhanden, `–` nicht), nicht „irgendein Strich". → AC-3.
4. **In-place statt Kopie** — die Ableitung schreibt `unit`/`decimals` in
   die Modul-Konstante statt in eine Kopie: `CV2_METRICS[i].get("unit") is
   None` muss nach einem `derive_row_labels()`-Aufruf noch gelten, sonst
   arbeitet ein zweiter Zweig derselben Mail (aktuell: `comparison.py`, das
   dieselbe `CV2_METRICS`-Referenz importiert) mit mutierten Daten. → AC-4.

Zusätzlich ein Vollständigkeits-Nachweis über **alle** Zeilen mit
`metric_id` mit echten `ForecastDataPoint`/`LocationResult`-Fixtures (Vorbild
`test_compare_mail_label_source_catalog.py`), keine Mocks — deckt AC-7.

**Renderer-Commit-Gate:** `compare_html.py` ist eine Mail-Inhalts-Datei —
Commit blockt, bis der Modus-Matrix-Test und
`uv run python3 .claude/hooks/email_spec_validator.py` (Marker
`X-GZ-Mail-Type: compare`) frisch grün sind, gegen echt zugestellte
Staging-Mail (`gregor-test@henemm.com`), kein Mock.

**Bestandstests, die grün bleiben müssen (kein Assertion-Diff):**
- `test_compare_mail_plaintext_html_label_parity.py`
- `test_compare_mail_metric_link_completeness.py`
- alle Tests, die `CV2_METRICS` direkt indizieren — vor der Implementierung
  auf `["unit"]`/`["decimals"]`-Zugriffe durchsuchen (Risiko aus der
  Analyse: sie könnten nach dem Entfernen der Felder still `None`/
  `KeyError` bekommen statt eines Testfehlers am richtigen Ort).

## Out of Scope

- **`comparison.py` (Klartext-Zweig) wird NICHT umgebaut.** Er liest
  `row["label"]` aus derselben `derive_row_labels()`-Rückgabe, formatiert
  Werte aber über eigene Lambdas in `_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` und
  griff schon vor dieser Scheibe nie auf `unit`/`decimals` aus
  `CV2_METRICS` zu (s. AC-6).
- **`compare_metric_catalog.py` (`COMPARE_METRIC_CATALOG`) bleibt
  unverändert.** Anderes Objekt, dient dem Frontend-Editor, bleibt laut
  `feat_1373_s2_ein_katalog.md` kuratiert.
- **`_fmt_metric` wird NICHT durch `format_value` ersetzt** — s.
  „Verworfene Alternativen".
- **Kein neues Speicherformat, keine Migration.** Reiner Code-Umbau ohne
  Persistenz-Änderung.
- **Die Zeilenliste selbst** (welche Zeilen existieren, `metric_id`/
  `aggregation`, `sev`, `kind`, Reihenfolge) bleibt unverändert kuratiert.

## Known Limitations

- 🔴 **Drei verschiedene „kein Wert"-Zeichen in derselben Mail (Nebenbefund,
  NICHT Teil dieser Lieferung).** HTML nutzt EM DASH `"—"` (U+2014,
  `_fmt_metric:715` u. a.), der Klartext-Zweig einen dritten Platzhalter,
  den ASCII-Bindestrich `"-"` (`comparison.py:239-248` fängt `None` vor dem
  Formatierer ab), und das SMS-Modul ersetzt EM DASH aktiv durch `"-"`
  (GSM-7, `comparison.py:606-611`). HTML und Klartext derselben Mail zeigen
  also bereits heute unterschiedliche Zeichen für „kein Wert" — diese
  Scheibe ändert daran nichts, hält den Ist-Zustand nur nicht fälschlich für
  behoben. → Sammel-Issue #1199.
- Der Wächter dieser Scheibe fängt eine falsche Ableitung, aber keine
  künftige dritte Kopie von `unit`/`decimals` an ganz anderer Stelle im
  Code (z. B. in einem neuen Renderer) — analog zur bekannten Grenze aus
  Scheibe A dieser Reihe: Divergenz wird gefangen, eine strukturell neue,
  aber konsistente Dopplung nicht.
- `visibility` bleibt die einzige Größe mit `display_unit` (m→km,
  `metric_catalog.py:560`) — sie geht weiterhin über ihr eigenes `fmt`
  (`_fmt_visibility_overview`), die `unit`/`decimals`-Ableitung dieser
  Scheibe wirkt dort nicht, weil `_render_overview_row()` für Zeilen mit
  `fmt_fn` `_fmt_metric` gar nicht aufruft (s. Implementation Details
  Punkt 4).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue.
- **Rationale:** Diese Scheibe entfernt eine redundante Datenkopie
  zugunsten der bereits etablierten Ableitung aus dem zentralen
  Metrik-Register — kein neuer Trade-off, keine Änderung einer
  Grundsatzentscheidung. Sie folgt demselben Muster wie #1401 Scheibe A2b
  (Labels) und #1406 Scheibe B (Stundenspalten), für die ebenfalls kein
  eigenes ADR angelegt wurde.

## Changelog

- 2026-08-18: Initial spec created
