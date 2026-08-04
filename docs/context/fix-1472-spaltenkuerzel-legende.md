# Context: fix-1472-spaltenkuerzel-legende

Issue: [#1472](https://github.com/henemm/gregor_zwanzig/issues/1472) — Vergleichs-Mail: die
englischen Spaltenkürzel sind unterwegs nirgends auflösbar (ADR-0042-Bedingung).
Labels: `bug`, `area:reports`, `area:compare`, `session:unity`. Track: **Standard** (Score 3).

## Request Summary

**ADR-0042** erlaubt englische Kurzformen in Spaltenköpfen **unter der Bedingung**, dass die
Auflösung auffindbar ist. Umgesetzt ist das nur im Editor — gelesen wird die Mail aber unterwegs.
Dort stehen bis zu 22 Kürzel (`Thdr`, `Visib`, `Feels`, `Dew`, `Press`, `CldMid`) ohne jede
Auflösung. Die Bedingung der ADR ist an der Stelle nicht erfüllt, an der sie gebraucht wird.

## PO-Entscheidung 2026-08-04

**Nur die in dieser Mail sichtbaren Kürzel** — keine feste Legende aller 22. Freigegebene
Vorschau (zweite Vorlage, nach der Messung unten):

```
Einheiten: Temp, Feels °C · Wind km/h
Spalten: Temp = Temperatur · Feels = Gefühlte Temperatur · Thdr = Gewitter · Visib = Sichtweite
```

`Wind` fällt weg, weil Kürzel und Name identisch sind.

**Abgrenzungsregel — erste Fassung GEMESSEN und VERWORFEN.**
Vorgeschlagen war: erklären, wenn das Kürzel nicht Präfix des Langnamens ist. Am echten Katalog
gemessen (`derive_row_labels(CV2_METRICS, "short")` gegen `"long"`, 27 Einträge) trifft sie
**24 von 27** — also praktisch alles. Grund ist strukturell und per ADR-0042 gewollt: Kurzform
**englisch**, Langname **deutsch** ⇒ zwischen `Rain` und `Niederschlag` besteht nie eine
Präfix-Beziehung. Nur `Wind`, `UV`, `Amtliche Warnungen` fielen weg.

**Geltende Regel (PO-Entscheidung 2026-08-04, zweite Vorlage):**
> Jedes **sichtbare** Kürzel wird aufgelöst — **außer** Kürzel und ausgeschriebener Name sind
> identisch (Vergleich ohne Groß-/Kleinschreibung). Keine Pflegeliste, keine Geschmacksgrenze.

Gemessene Wirkung: `Wind`, `UV`, `Amtliche Warnungen` fallen weg; die übrigen 24 werden erklärt,
**soweit sie in der jeweiligen Mail sichtbar sind**. Bei üblicher Auswahl (5–8 Spalten) entspricht
das der vom PO freigegebenen Vorschau-Länge; die volle Länge entsteht nur, wenn jemand alle 22
Größen anhakt.

**Verworfen wurde ausdrücklich** eine feste Liste „selbsterklärender" Kürzel — Begründung des PO
mitgetragen: solche Listen veralten unbemerkt, und eine vergessene neue Größe bliebe unerklärt,
ohne dass es auffällt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/output/renderers/email/helpers.py:344` `format_units_legend()` | **Die gemeinsame Wurzel** (#1237): baut `Einheiten: Temp, Feels °C · Wind km/h`. Trip **und** Vergleich rufen sie auf |
| `src/output/renderers/email/helpers.py:467` `build_units_legend(rows)` | Trip-Weg: `visible_cols(rows)` → `get_metric_by_col_key()` → `format_units_legend()` |
| `src/output/renderers/email/html.py:1565` | Trip **HTML** ruft `build_units_legend(all_rows)` |
| `src/output/renderers/email/plain.py:315` | Trip **Klartext** ruft dieselbe Funktion |
| `src/output/renderers/email/compare_html.py:1224-1241` | Vergleich **HTML**: `_units_legend_text(_visible_hour_metrics(...))` → `format_units_legend()` |
| `src/output/renderers/email/compare_html.py:441` `derive_row_labels(rows, form)` | **Die einzige Namensquelle**: `form="short"` = englische `col_label`, `form="long"` = deutscher `label_de`. Beide Formen aus derselben Ableitung — genau was die Legende braucht |
| `src/output/renderers/comparison.py:221` | Vergleich **Klartext** — nutzt `derive_row_labels(form="long")` für die Übersicht |

## 🔴 Befund: der Vergleichs-Klartext hat noch gar keine Einheiten-Zeile

`grep -n "Einheiten\|units\|legend" src/output/renderers/comparison.py` → **0 Treffer**. Die
Stundentabelle wird dort gerendert (ab ~Zeile 235), aber ohne Einheiten-Legende. Das Issue sagt
„der Klartext-Zwilling braucht dieselbe Zeile" und unterstellt, dass die Einheiten-Zeile dort
existiert — sie existiert nicht. Dort entsteht die Legende **neu**, nicht ergänzt.
Deckt sich mit `reference_compare_mail_plaintext_blind_spot`.

## Dependencies

- **Upstream:** zentrales Wetter-Namensregister (`col_label`, `label_de`) über `derive_row_labels`
  bzw. `get_metric_by_col_key()`. **Keine zweite Namensquelle anlegen** — sonst fällt die Arbeit
  aus #1453/#1435 wieder auseinander (ausdrücklich im Issue gefordert).
- **Downstream:** vier Ausgaben — Trip HTML/Klartext, Vergleich HTML/Klartext.

## ⚠️ Gates, die diese Änderung auslöst

1. **Renderer-Commit-Gate #811 (un-überspringbar):** Betroffen sind
   `src/output/renderers/email/*.py` (helpers, html, plain, compare_html) und
   `src/output/renderers/trip_report.py`-Nachbarn. Der Commit blockt, bis im aktiven Workflow
   **beide** frisch vorliegen: `tests/tdd/test_issue_811_mode_matrix.py` grün **und** ein
   erfolgreicher `briefing_mail_validator.py`-Lauf. Einplanen, nicht überraschen lassen.
2. **Zwei Mail-Validatoren, zwei Pfade** (CLAUDE.md-Dispatch): Trip-Briefing →
   `briefing_mail_validator.py`; Orts-Vergleich → `email_spec_validator.py`. Beide gegen eine
   **echt zugestellte** Staging-Mail.
3. **`email_spec_validator.py` liegt im geschützten Bereich und braucht bei
   Beschriftungsänderungen PO-`override`** (belegt in #1453). Rechtzeitig ankündigen.

## Nebenpunkt aus dem Issue (mitliefern)

Der #1453-AC-7-Nachweis („drei Namensformen in allen vier Editoren") ist heute ein
**Quelltext-Test**: er prüft mit dem Svelte-Compiler, ob `label`, `col_label` und `sms_code` in den
Komponenten **vorkommen** — nicht, ob ein Nutzer sie sieht. Nach der Lehre aus #1436 (Tabelle galt
als vorhanden, war am Handy unsichtbar) gehört ein Blick auf den echten Bildschirm dazu.

## Risks & Considerations

1. **Länge im Klartext:** Bei vielen angehakten Größen wird die Zeile lang. Umbruchverhalten in
   der Klartext-Fassung prüfen (Zeilenlänge), nicht nur im HTML.
2. **Doppelung vermeiden:** Einheiten-Zeile und Spalten-Zeile nennen teils dieselben Kürzel.
   Prüfen, ob eine zusammengeführte Zeile lesbarer ist als zwei — Entscheidung gehört in die Spec.
3. **Vier Ausgaben müssen gleich lauten** — sonst entsteht genau die Drift, die #1453 beseitigt hat.
   Ein Test sollte das als Wirkung prüfen, nicht als „beide rufen dieselbe Funktion".
4. **Erledigt:** Die Abgrenzungsregel wurde gegen den echten Katalog gemessen (s.o.) — die erste
   Fassung war untauglich, die geltende ist gemessen. Bei neuen Wettergrößen bleibt sie gültig,
   weil sie nur Kürzel und Name vergleicht und keine Liste führt.
   Die Gegenprobe an der **Trip**-Seite (anderer Weg: `visible_cols()`/`get_metric_by_col_key()`
   statt `derive_row_labels`) ist ebenfalls erfolgt — siehe Analyse-Tabelle: gleiches Verhalten,
   dort fällt nur `Wind` weg.
5. **Kein Emoji, kein Farbträger** — Design-Leitprinzip: Lesbarkeit unter Zeitdruck.

---

# Analysis

**Type:** Bug (nicht erfüllte ADR-Bedingung, nutzersichtbar unterwegs).

## Die Regel — auf beiden Seiten gemessen

| Seite | Quelle | Paare | davon identisch (fallen weg) |
|---|---|---|---|
| Ortsvergleich | `derive_row_labels(CV2_METRICS, "short"/"long")` | 27 | **2** — `Wind`, `Amtliche Warnungen` |
| Trip | `metric_catalog` (`col_label` / `label_de`) | 26 | **1** — `Wind` |

⚠️ Nicht mit der verworfenen Präfix-Regel verwechseln: `UV` → `UV-Index` ist ein Präfix, aber
**nicht identisch** — `UV` wird also aufgelöst (`UV = UV-Index`).

Die Regel „auflösen außer Kürzel == Name" verhält sich auf beiden Seiten gleich und braucht keine
Pflegeliste. **Ehrlich benannt:** Sie erzeugt vereinzelt redundante Paare (`UV = UV-Index`,
`Temp max = Temperatur Maximum`). Das ist der Preis dafür, dass niemand eine Grenze pflegen muss —
und harmlos, weil die Zeile ohnehin nur die sichtbaren Spalten führt.

## Vier Ausgabestellen, zwei Wege

| Ausgabe | Weg heute | Änderung |
|---|---|---|
| Trip HTML (`html.py:1565`) | `build_units_legend(all_rows)` → `format_units_legend()` | Legende erweitern |
| Trip Klartext (`plain.py:315`) | dieselbe Funktion | folgt automatisch |
| Vergleich HTML (`compare_html.py:1241`) | `_units_legend_text()` → `format_units_legend()` | Legende erweitern |
| **Vergleich Klartext** (`comparison.py`) | **keine Legende vorhanden** | **neu anlegen** |

🔴 **Korrigiert nach dem RED-Lauf:** Die frühere Annahme „drei der vier folgen automatisch" ist
**falsch**. `format_units_legend(label_units)` bekommt `(Kürzel, Einheit)`-Paare und sieht den
ausgeschriebenen Namen nie — die Auflösung kann dort nicht entstehen. Es braucht einen eigenen
Formatierer plus **vier** eigene Verdrahtungen (Trip HTML, Trip Klartext, Vergleich HTML,
Vergleich Klartext). Der Aufwand liegt entsprechend höher als zunächst geschätzt.

Zweite Korrektur aus demselben Lauf: Das **Kürzel** der Legende muss aus derselben Ableitung
stammen wie der Spaltenkopf (`derive_row_labels` bzw. `visible_cols`), nicht aus dem Register —
sonst erklärt die Legende bei kollidierenden Kurzformen `Temp`, während im Kopf `Temp max` steht.
Dafür ist AC-8 ergänzt.

## Scope Assessment

| | |
|---|---|
| Dateien | `helpers.py` (Kern) · `compare_html.py` (Anschluss) · `comparison.py` (neue Zeile) · ggf. `html.py`/`plain.py` (nur falls Aufrufsignatur wächst) · Tests |
| Geschätzt | ~90–140 LoC |
| Risiko | MEDIUM-HIGH — jede Briefing-Mail betroffen; Renderer-Gate #811 und zwei Mail-Validatoren greifen |

## Technical Approach

Die Auflösung entsteht **an derselben Stelle wie die Einheiten-Zeile** (`format_units_legend`),
gespeist aus denselben (Kurzform, Langname)-Paaren, die die Aufrufer ohnehin ermitteln. Keine
zweite Namensquelle, kein zweiter Sichtbarkeits-Filter — beides existiert bereits
(`visible_cols()` bzw. `_visible_hour_metrics()`).

## Open Questions

- [ ] Eine Zeile oder zwei? („Einheiten: …" + „Spalten: …" getrennt, oder zusammengeführt.)
      Vorschlag: **zwei Zeilen** — Einheiten und Bedeutungen beantworten verschiedene Fragen, und
      die Einheiten-Zeile ist etabliert. Entscheidung gehört in die Spec, nicht zum PO.
