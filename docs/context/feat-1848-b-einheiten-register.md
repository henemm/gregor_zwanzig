# Context: feat-1848-b-einheiten-register

Issue #1848 Scheibe B (Zuschnitt geändert, PO-Entscheid 2026-08-18 —
s. Issue-Kommentar `#issuecomment-5329322032`).

## Request Summary

Die Übersichtstabelle der Ortsvergleichs-Mail tippt Einheiten und
Nachkommastellen ein zweites Mal (`CV2_METRICS` in `compare_html.py`), obwohl
das zentrale Wetter-Register (`src/app/metric_catalog.py`) beide bereits führt.
Diese Lieferung leitet sie von dort ab. Für Nutzer ändert sich nichts sichtbar.

## Warum der Zuschnitt geändert wurde

Der ursprüngliche Wortlaut von Scheibe B („Compare-Katalog auf die
Trip-Kennungen zurückführen, Übersetzungstabellen schrumpfen") ist überholt:

| Versprechen | Ist-Stand, gemessen |
|---|---|
| Katalog an Trip-Kennungen koppeln | erledigt durch **#1373 S2 A** — alle 26 Einträge tragen `metric_id` + `aggregation`, Drift-Wächter existiert |
| Speicherformat auf Paare | erledigt durch **#1373 S2 B** (`4d8fafae`) |
| Getippte Labels beseitigen | erledigt durch **#1401 A2b** (`derive_row_labels()`) |
| Übersetzungstabellen schrumpfen | **findet nicht statt** — `FRONTEND_TO_RENDERER_METRIC_ID` übersetzt Vokabular 3→2 (Frontend-Key → Renderer-Feld), nicht Compare→Trip, und bleibt nötig, solange `Corridor.metric` String-basiert ist |

Zusätzlich blockiert ein fachlicher Befund die Vokabular-Zusammenführung:
`tests/unit/test_compare_catalog_derives_from_central_catalog.py:72-77` nennt
#1848 namentlich als Rückbaupfad und warnt, dass `temperature_day_low/_high`
und `wind_chill_day_low/_high` über die **Gehzeit einer Etappe** fenstern, ihre
Compare-Pendants dagegen über ein **konfiguriertes Tagesfenster (04–19)** —
verschiedene Zahlen, nachgemessen widerlegt. Das ist eine PO-Entscheidung, kein
Refactoring, und gehört in Epic #1435.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/compare_html.py:314-386` | `CV2_METRICS` — 26 Zeilen, 22 davon mit getippter `unit`, 2 mit getippter `decimals`. **Zieldatei.** |
| `src/output/renderers/email/compare_html.py:713-719` | `_fmt_metric(value, decimals, unit)` — der zu ersetzende Formatierer |
| `src/output/renderers/email/compare_html.py:766` | **Einzige** Leseseite von `unit`/`decimals` |
| `src/output/metric_format.py:77-128` | `format_value(metric_id, value, style)` — der geteilte, katalog-getriebene Ersatz |
| `src/output/metric_format.py:65` | `_NO_VALUE = "–"` (U+2013 EN DASH) — **weicht ab**, s. Risiken |
| `src/app/metric_catalog.py` | Zentrales Register; `MetricDefinition.unit`, `.decimals`, `.display_unit` |
| `src/output/renderers/email/compare_html.py:472-507` | `derive_row_labels()` — **Vorbild-Muster** (#1401 A2b) |
| `src/output/renderers/comparison.py:31,124` | Klartext-Zweig, baut `_CV2_BY_KEY` aus `CV2_METRICS` |

## Messung: getippte Einheiten gegen Register (2026-08-18)

Alle 26 Zeilen ausgezählt (`PYTHONPATH=src uv run python3`, Katalog-Import):

- **Einheiten-Abweichungen: 0.** Alle 22 getippten `unit` stimmen exakt mit
  `get_metric(metric_id).unit` überein.
- **Nachkommastellen:** nur `precip_sum` und `sunny_hours` tippen `decimals=1` —
  das Register führt für beide ebenfalls `1`. Alle übrigen tippen nichts;
  `_fmt_metric` behandelt `None` als `0`, `format_value` ebenso. Identisch.
- **3 Zeilen umgehen `_fmt_metric` über eigenes `fmt`:** `thunder_max`
  (`_fmt_thunder`), `visibility_min` (`_fmt_visibility_overview`),
  `precip_type`. Sie tragen gar keine `unit` und bleiben unberührt.
- `visibility` ist die einzige Größe mit `display_unit` (m→km) — sie geht über
  ihr eigenes `fmt`, die Konvertierung in `format_value` wird also nicht
  wirksam.

**Folge:** Die Ableitung ist für Einheiten und Nachkommastellen verlustfrei.

## Existing Patterns

- **#1401 A2b** — `derive_row_labels()`: Beschriftungen wurden aus
  `CV2_METRICS` entfernt und zur Renderzeit aus dem Register abgeleitet. Zeilen
  ohne `metric_id` (Warn-Zeile) behalten festen Text. Rückgabe sind **Kopien**,
  die Modul-Konstante bleibt unberührt. Unbekannter Parameter ⇒ `ValueError`,
  kein stiller Rückfall.
- **#1406 Scheibe B** — Stundenspalten werden aus dem Register abgeleitet
  (`hourly_selectable_metric_ids()`) statt getippt.
- **`format_value(..., style="bare")`** — bereits im Einsatz für die
  Stundentabelle, wo die Einheit in der Spaltenüberschrift steht.

## Dependencies

- **Upstream:** `app.metric_catalog.get_metric()`, `output.metric_format`
- **Downstream:** `comparison.py` (Klartext), `compare_html.py` (HTML) —
  beide speisen dieselbe Ortsvergleichs-Mail (HTML + Klartext + Telegram)

## Existing Specs

- `docs/specs/modules/feat_1373_s2_ein_katalog.md` — Compare-Katalog ↔ zentrales
  Register; hält die PO-Entscheidung 2026-07-26 fest (Tabelle bleibt
  **kuratiert**, wird NICHT erzeugt — Labels/Wertebereiche sind redaktionell)
- `docs/specs/modules/feat_1373_s2b_metrik_speicherformat.md` — Speicherformat
- `docs/specs/modules/feat_1848_a_kaskade_eine_quelle.md` — Scheibe A dieser Reihe
- ADR-0050 (Kaskade), ADR-0053 (kanal-eigene Metrikauswahl Ortsvergleich)

## Risks & Considerations

1. **🔴 Gedankenstrich-Falle (nutzersichtbar).** `_fmt_metric` liefert bei
   fehlendem Wert `"—"` (U+2014 EM DASH, per hexdump verifiziert:
   `e2 80 94`), `format_value` dagegen `"–"` (U+2013 EN DASH, `e2 80 93`).
   Ein blindes Umstellen ändert den Platzhalter in der Mail. Da der Auftrag
   „für Nutzer ändert sich nichts sichtbar" lautet, muss die Spec festlegen,
   dass der bisherige Platzhalter erhalten bleibt — und ein Test muss das
   bewachen.
2. **Renderer-Commit-Gate.** `compare_html.py` ist eine Mail-Inhalts-Datei;
   Commits blocken, bis Modus-Matrix-Test und
   `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`) frisch grün sind.
3. **Zwei Ausgabezweige.** HTML (`compare_html.py`) und Klartext
   (`comparison.py`) lesen dieselbe Konstante. Eine Änderung an `CV2_METRICS`
   wirkt auf beide — Paritäts-Tests bestehen bereits
   (`test_compare_mail_plaintext_html_label_parity.py`).
4. **Der Gewinn ist Entdopplung, nicht Divergenz-Schutz.** Wie bei Scheibe A
   gilt: ein Wächter, der beide Seiten vergleicht, fängt Auseinanderlaufen,
   aber nicht das erneute Antippen einer dritten Kopie.
5. **Bestandsdaten unberührt.** Es ändert sich kein Speicherformat, keine
   Migration nötig.

## Offene Fragen für die Analyse-Phase

- Sollen die getippten `unit`/`decimals` **ersatzlos entfallen** (wie die Labels
  bei #1401 A2b) oder als bewusste Übersteuerung erlaubt bleiben?
- Reicht der Austausch von `_fmt_metric` gegen `format_value` an der einen
  Leseseite (Zeile 766), oder braucht es eine Ableitungsfunktion analog
  `derive_row_labels()`?

---

## Analysis

*(Phase 2, 2026-08-18 — 3 parallele Explore-Agenten + strategische Bewertung)*

### Type

**Feature** (Refactor ohne sichtbare Wirkung) — kein Bug.

### Der Spec-Einwand ist geprüft und trägt nicht

Zwei Stellen schienen entgegenzustehen. Beide betreffen etwas anderes:

1. **„bleibt kuratiert, wird nicht generiert"**
   (`feat_1373_s2_ein_katalog.md:116-117`) bezieht sich auf
   **`COMPARE_METRIC_CATALOG`** in `compare_metric_catalog.py` — den
   Endpunkt-Katalog für den Frontend-Editor. Das ist ein **anderes Objekt** als
   `CV2_METRICS` in `compare_html.py`. Die drei dort genannten Begründungen
   (redaktionell abweichende Labels, nur dort existierende Wertebereiche, drei
   Größen ohne zentrales Tages-Auswertungsfeld) treffen auf `unit`/`decimals`
   **nicht** zu — gemessen 0 Abweichungen.
2. **„Kein Umbau von `CV2_METRICS`/`HOUR_METRICS` — S3/S5"**
   (`feat_1373_s2_ein_katalog.md:292-295`, `feat_1373_s2b:317`) war eine
   **Scope-Grenze der damaligen Lieferung**, kein Denkverbot. Die drei
   benannten Tickets sind geschlossen und behandelten anderes: **#1366**
   (leere Auswahl zeigt alle Zeilen), **#1378** (Stundentabelle in Server-
   statt Ortszeit), **#1377** (sechs Ampel-Schwellenquellen). Keines
   adressiert `unit`/`decimals`.

**Präzedenzfall:** `derive_row_labels()` (#1401 A2b) hat `CV2_METRICS`
**nach** dieser Notiz angefasst und genau ein getipptes Formatierungsfeld
(`label`) durch Register-Ableitung ersetzt — unbeanstandet, weil die
*Zeilenliste* kuratiert blieb. Ebenso wurde `HOUR_METRICS` durch #1406 B
bereits auf `format_value(...)` umgestellt. Dieses Vorhaben ist strukturell
identisch: zwei redundante Felder pro Zeile entfallen, die Zeilenliste
(welche Zeilen, `metric_id`/`aggregation`, `sev`, `kind`) bleibt unberührt.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `CV2_METRICS`: 22 Einträge verlieren `"unit"`, 2 zusätzlich `"decimals"`. `derive_row_labels()` hängt beide aus `get_metric()` an die Kopien. Kommentarblock `:299-313` aktualisieren. |
| `tests/unit/test_compare_mail_metric_format_from_register.py` | CREATE | Wächter an der gerenderten Mail (s. Mutations-Gegenprobe) |
| `docs/specs/modules/feat_1848_b_einheiten_register.md` | CREATE | Spec dieser Lieferung |

**Nicht betroffen:** `comparison.py` (Klartext) formatiert die Übersicht über
eigene Lambdas in `_PLAIN_ROWS`/`_DAILY_PLAIN_ROWS` und liest `unit`/`decimals`
aus `CV2_METRICS` heute schon nicht. `compare_metric_catalog.py` bleibt
unberührt.

### Scope Assessment

- Dateien: **1 Produktivdatei**, 1 neue Testdatei, 1 Spec
- Geschätzte LoC: **netto ca. −15 bis +30** produktiv (überwiegend Entfernungen)
  — deutlich unter dem Workflow-Limit 250
- Risk Level: **LOW** fachlich (Ableitung gemessen verlustfrei),
  **MEDIUM** prozessual (Renderer-Commit-Gate)

### Technical Approach — Variante A (entschieden)

`derive_row_labels()` wird um `unit`/`decimals` erweitert; `_fmt_metric`
(Zeile 713-719) und die Leseseite (Zeile 766) bleiben **unverändert**.

Verworfen wurde Variante B (Leseseite auf `format_value(..., style="plain")`
umstellen, `_fmt_metric` entfällt):

- Sie brächte die **Gedankenstrich-Änderung** ins Spiel, ohne dass die Aufgabe
  („zwei redundante Felder entfernen") das verlangt.
- Sie erzeugte eine **Teil-Migration**: 19 von 22 Zeilen auf `format_value`,
  3 weiter auf ihren eigenen `fmt` — eine Asymmetrie im Code ohne Gegenwert.
- Die vollständige Ablösung von `_fmt_metric` ist ein eigenes, größeres
  Vorhaben mit eigener Spec.

Variante A folgt exakt dem etablierten Muster: **Kopien** zurückgeben,
Modul-Konstante unberührt, Zeilen ohne `metric_id` (Warn-Zeile) unangetastet,
lautes Scheitern statt stillem Rückfall.

### Entscheidung: Gedankenstrich bleibt EM DASH

`"—"` (U+2014) ist in `compare_html.py` bereits das **durchgängige**
Platzhalter-Zeichen: `_fmt_metric:715`, `_fmt_thunder:232/234`,
`_fmt_precip_type:271/273`, `_fmt_visibility_overview:285`, weitere Helfer
`:179/183/191/195/201`, Warn-Zelle `:736`, Fallback `:1466`. Ein Wechsel nur an
Zeile 766 mischte erstmals **zwei verschiedene Striche innerhalb derselben
Tabelle**. Mit Variante A stellt sich die Frage praktisch nicht — sie wird
trotzdem in Spec und Test festgehalten, damit eine künftige Migration sie
nicht stillschweigend falsch entscheidet.

**Nebenbefund (nicht Teil dieser Lieferung):** Der Klartext-Zweig nutzt einen
**dritten** Platzhalter, den ASCII-Bindestrich `"-"` (`comparison.py:239-248`
fängt `None` vor dem Formatierer ab); das SMS-Modul ersetzt EM DASH aktiv durch
`"-"` (GSM-7, `comparison.py:606-611`). HTML und Klartext derselben Mail
zeigen also heute schon verschiedene Zeichen für „kein Wert". → #1199.

### Mutations-Gegenprobe (Pflicht für die TDD-Phase)

Alle Wächter prüfen an der **gerenderten Mail**, nicht an `CV2_METRICS[i]["unit"]` —
sonst belegt der Test nur die Existenz eines Dict-Schlüssels, nicht die Zahl in
der Mail.

1. **Nachkommastellen** — Ableitung liefert immer `0` statt `metric.decimals`:
   `precip_sum_mm=12.34` muss in der Mail `12.3 mm` zeigen, die Mutation
   erzeugte `12 mm`. *Wichtigster Fall — ein Test, der nur die Kopie prüft,
   fängt ihn NICHT, falls Zeile 766 die Kopie am Ende ignoriert.*
2. **Einheit vertauscht** — `wind` bekommt `"°C"` statt `"km/h"`: gerenderte
   Mail muss `42 km/h` zeigen.
3. **Gedankenstrich-Regression** — bei fehlendem Wert `"–"` statt `"—"`:
   Prüfung am HTML per Codepoint (`—` vorhanden, `–` nicht), nicht
   „irgendein Strich".
4. **In-place statt Kopie** — Ableitung schreibt in die Modul-Konstante:
   `CV2_METRICS[i].get("unit") is None` muss nach dem Aufruf noch gelten,
   sonst arbeitet der zweite Zweig derselben Mail mit mutierten Daten.

Zusätzlich ein Vollständigkeits-Nachweis über **alle** Zeilen mit `metric_id`
mit echten `ForecastDataPoint`-Fixtures (Vorbild
`test_compare_mail_label_source_catalog.py`), keine Mocks.

### Risks

- **Renderer-Commit-Gate:** `compare_html.py` ist Mail-Inhalts-Datei — Commit
  blockt, bis Modus-Matrix-Test und Mail-Validator frisch grün sind.
- Tests, die direkt auf `["unit"]`/`["decimals"]` im Modul-Dict zugreifen,
  könnten still `None` bekommen — vor der Implementierung suchen.
- `derive_row_labels()` wird auch vom Klartext-Zweig gerufen
  (`comparison.py:242`); die neuen Felder sind additiv und dürfen dort
  keinen bestehenden Leser brechen.

### Open Questions

Keine offenen Fragen für die Spec-Phase — Variante und Zeichen-Vertrag sind
entschieden. Die Acceptance Criteria gehen dem PO zur Freigabe.
