---
entity_id: feat_1848_a_kaskade_eine_quelle
type: refactor
created: 2026-08-18
updated: 2026-08-18
status: draft
version: "1.0"
workflow: feat-1848-ausblick-vokabular
tags: [trip, kaskade, adr-0050, refactor, issue-1848, epic-1435]
---

# Eine Quelle für die Trip-Kaskade: Kanal-Layout und Ausblick teilen sich die Schnittmenge (Issue #1848, Scheibe A)

## Approval

- [ ] Approved

## Purpose

Die Kaskadenregel aus ADR-0050 (Grundauswahl ist das Maximum, nachgelagerte
Ebenen dürfen nur abwählen) ist für den Trip heute **zweimal** implementiert:
einmal für das Kanal-Layout (`models.py::_clip_to_global_maximum()`), einmal
für den 3-Tages-Ausblick (`compare_outlook_metric_ids.py::
resolve_trip_outlook_metrics()`, die sich im eigenen Docstring als
„Nachbildung" bezeichnet). Beide Umsetzungen sind verhaltensgleich, aber
unabhängig gepflegt — eine künftige Änderung an einer Regel (z. B. eine neue
Sonderfall-Behandlung von D4) müsste an zwei Stellen nachgezogen werden und
könnte auseinanderlaufen, ohne dass ein Test das bemerkt. Diese Scheibe führt
die erlaubte Kennungsmenge auf **eine** Quelle zurück, die beide Stellen
aufrufen. Für den Nutzer ändert sich **nichts** — keine andere Auswahl, keine
andere Ausgabe, kein anderes Speicherformat.

## Source

- **File:** `src/app/models.py:833-921` — `UnifiedWeatherDisplayConfig`.
  - `get_metrics_for_report_type()` (Zeile 833-842) — bestehend, unverändert:
    liefert die report-typ-gefilterte Grundauswahl, bereits inklusive
    `morning_enabled`/`evening_enabled`-Override und `selectable`-Gate
    (`_filter_metrics_by_report_type()` → `_is_selectable()`, Zeile 683-710).
  - **Neu:** `allowed_metric_ids_for_report_type(self, report_type: str) ->
    set[str] | None` — direkt nach `get_metrics_for_report_type()` eingefügt.
    `None`, wenn `self.metrics` leer ist (D4 — kein Maximum definiert, NICHT
    die leere Menge). Sonst die Menge der `metric_id` aus
    `self.get_metrics_for_report_type(report_type)`.
  - `_clip_to_global_maximum()` (Zeile 898-921) — Rumpf wird durch einen
    Aufruf der neuen Methode ersetzt: `allowed = self.
    allowed_metric_ids_for_report_type(report_type)`; `allowed is None` ⇒
    unverändert zurückgeben (D4), sonst auf `allowed` filtern. Signatur,
    Docstring-Zusage und Aufrufstellen (`get_metrics_for_channel()`,
    Zeile 886/893) bleiben unverändert.
- **File:** `src/output/renderers/compare_outlook_metric_ids.py:78-102` —
  `resolve_trip_outlook_metrics(dc, report_type)`. Der Schnitt
  (Zeile 99-102, `if not resolved or not getattr(dc, "metrics", None): return
  resolved` / `allowed = {mc.metric_id for mc in
  dc.get_metrics_for_report_type(report_type)}`) wird durch einen Aufruf von
  `dc.allowed_metric_ids_for_report_type(report_type)` ersetzt: `allowed is
  None` ⇒ `resolved` unverändert zurückgeben, sonst auf `allowed` filtern.
  Funktionssignatur, die vorgelagerte Auflösung über
  `resolve_outlook_metrics()` (Zeile 98) und die Drei-Werte-Semantik des
  Rückgabewerts (`None`/`[]`/gefüllt) bleiben unverändert — der Schnitt
  wirkt ausschließlich auf den bereits aufgelösten `resolved`, wie heute.

> **Schicht-Hinweis:** Reiner Python-Core-Umbau (`src/app/`,
> `src/output/renderers/`). Keine Änderung an `frontend/`, `internal/` oder
> `cmd/` — `display_config` bleibt für Go weiterhin `map[string]interface{}`.

## Estimated Scope

- **LoC:** ~25-35 Produktiv (`models.py`: neue Methode ~10 Zeilen,
  `_clip_to_global_maximum()`-Rumpf ~4 Zeilen kürzer/geändert;
  `compare_outlook_metric_ids.py`: `resolve_trip_outlook_metrics()`-Rumpf
  ~4 Zeilen geändert). Getrennt davon Test-LoC (eigenes Budget).
- **Files:** 2 Produktionsdateien geändert, 0 neu.
- **Effort:** low-medium — reine Umleitung auf eine gemeinsame Quelle, keine
  neue Fachregel; das Risiko liegt ausschließlich darin, D4 beim Umbau zu
  einer leeren Menge statt `None` zu verflachen (s. „Implementation
  Details" Punkt 2).

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `app.models.UnifiedWeatherDisplayConfig.get_metrics_for_report_type` | reused, unverändert | Liefert bereits report-typ-gefilterte, selectable-gegatete Metriken — die neue Methode baut nur noch die ID-Menge daraus |
| `app.models.UnifiedWeatherDisplayConfig.get_metrics_for_channel` | upstream, unverändert | Ruft `_clip_to_global_maximum()` (Zeile 886/893) — Aufrufstelle bleibt unverändert, nur der Rumpf der aufgerufenen Methode ändert sich |
| `output.renderers.compare_outlook_metric_ids.resolve_outlook_metrics` | upstream, unverändert | Liefert das `resolved` (`None`/`[]`/gefüllt), auf dem der neue Schnitt aufsetzt |
| `output.renderers.compare_metric_ids.resolve_channel_enabled_metrics` | explizit NICHT eingemeindet | Dritte Umsetzung derselben ADR-0050-Regel für den Ortsvergleich, mit bewusst anderer `[]`-Semantik (#1366) — bleibt unangetastet, s. „Out of Scope" |
| `docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md` | governs | Regeln D1-D4, deren einzige Umsetzung nach dieser Scheibe die neue Methode ist |

## Implementation Details

1. **Neue öffentliche Methode statt zwei privater Kopien.**
   `allowed_metric_ids_for_report_type()` wird Teil der öffentlichen
   Schnittstelle von `UnifiedWeatherDisplayConfig` (kein führender
   Unterstrich) — sie wird jetzt von einem anderen Modul
   (`compare_outlook_metric_ids.py`) aufgerufen, nicht mehr nur intern.
   `_clip_to_global_maximum()` bleibt als schmaler Adapter bestehen (er
   filtert `list[MetricConfig]` statt `list[dict]`), enthält aber selbst
   keine Regel-Logik mehr — nur noch den Aufruf plus die typspezifische
   Filterung.

2. **D4 als eigener Rückgabewert, nicht als leere Menge — die zentrale
   Falle dieser Scheibe.** `allowed_metric_ids_for_report_type()` gibt
   `None` zurück, wenn `self.metrics` leer ist. Ein Aufrufer, der `None`
   nicht von `set()` unterscheidet (z. B. `allowed = ... or set()`) und
   anschließend unbedingt filtert, verwandelt „kein Maximum definiert" in
   „nichts erlaubt" — beide bestehenden ACs (AC-16 aus #1720 S1, das
   Kanal-Pendant in `_clip_to_global_maximum()`) verlangen ausdrücklich das
   Gegenteil: bei leerer Grundauswahl wird **nicht** geschnitten.

3. **Kein neuer Import-Zyklus.** `compare_outlook_metric_ids.py` bekommt
   `dc` bereits als Parameter übergeben (kein neuer Import in Richtung
   `models.py` nötig) — die Methode wird auf dem übergebenen Objekt
   aufgerufen, nicht das Modul importiert.

4. **Beide Aufrufer bleiben bei ihrem eigenen Trägertyp.**
   `_clip_to_global_maximum()` filtert weiterhin `list[MetricConfig]` über
   `mc.metric_id`, `resolve_trip_outlook_metrics()` weiterhin `list[dict]`
   über `e["metric_id"]`. Die neue Methode liefert nur die Kennungsmenge —
   sie kennt keinen der beiden Trägertypen und muss keinen kennen.

5. **`report_type`-Weiterleitung unverändert.** Beide Aufrufer reichen den
   `report_type` weiter, den sie ohnehin schon erhalten
   (`_clip_to_global_maximum(metrics, report_type)`,
   `resolve_trip_outlook_metrics(dc, report_type)`) — kein neuer Parameter
   an bestehenden öffentlichen Signaturen.

## Expected Behavior

- **Input:** ein `UnifiedWeatherDisplayConfig`-Objekt und ein `report_type`
  (`"morning"`/`"evening"`/anderer).
- **Output:** `allowed_metric_ids_for_report_type()` liefert entweder `None`
  (kein Maximum definiert, `self.metrics` leer) oder die Menge der
  erlaubten `metric_id`-Strings für diesen `report_type`, inklusive
  `selectable`-Gate und Morgen-/Abend-Override.
- **Side effects:** keine — reine Funktion, kein I/O, keine Mutation der
  Eingaben (identisch zum heutigen Verhalten beider Aufrufer).

## Acceptance Criteria

- **AC-1:** Given dieselbe Trip-Konfiguration mit einer Grundauswahl, in der
  eine Größe bewusst abgewählt ist, When sowohl das Kanal-Layout
  (`_clip_to_global_maximum()` über `get_metrics_for_channel()`) als auch
  der Ausblick (`resolve_trip_outlook_metrics()`) für denselben `report_type`
  geprüft werden, Then schneiden beide Flächen die abgewählte Größe
  identisch heraus — keine Fläche zeigt sie, keine Fläche behält sie.
  - Test: `tests/unit/test_trip_metric_cascade_single_source.py`, ein
    Kaskaden-Fall (Grundauswahl mit einer bewusst abgewählten Größe) wird
    durch beide Aufrufer geschickt, die Ergebnismengen werden auf
    Übereinstimmung geprüft — feste Erwartungswerte im Test, nicht aus dem
    Prüfling abgeleitet.

- **AC-2:** Given eine Trip-Konfiguration OHNE gespeicherte Grundauswahl
  (`display_config.metrics == []`, Altbestand), When
  `allowed_metric_ids_for_report_type()` für einen beliebigen `report_type`
  aufgerufen wird, Then liefert sie `None` — nicht `set()` und nicht `[]` —
  und sowohl `_clip_to_global_maximum()` als auch
  `resolve_trip_outlook_metrics()` schneiden in diesem Fall **nicht**,
  sondern geben ihre Eingabe unverändert zurück (Regel D4).
  - Test: derselbe Fall wird für beide Aufrufer geprüft: eine
    Kanal-Layout-Liste bzw. eine Ausblick-Auswahl mit mehreren Einträgen
    bleibt bei leerer Grundauswahl vollständig erhalten, Länge und Inhalt
    unverändert gegen die Eingabe geprüft.

- **AC-3:** Given eine Trip-Konfiguration mit einer Größe, die zentral als
  `selectable=False` markiert ist (z. B. `confidence`), aber in einem
  Bestandstrip noch `enabled=True` gespeichert ist, When beide Flächen für
  denselben `report_type` geprüft werden, Then erscheint diese Größe in
  keiner der beiden Flächen — das `selectable`-Gate (#1585) wirkt über
  `get_metrics_for_report_type()` unverändert in beiden Aufrufern.
  - Test: `tests/unit/test_trip_metric_cascade_single_source.py`, eine
    `selectable=False`-Größe wird in Kanal-Layout UND Ausblick-Auswahl
    eingetragen, beide gerenderten/aufgelösten Ergebnisse werden auf
    Abwesenheit dieser Größe geprüft.

- **AC-4:** Given eine Trip-Konfiguration mit einem
  `morning_enabled`/`evening_enabled`-Override, der eine Größe für
  `report_type="morning"` ausschließt, obwohl sie global aktiv ist, When
  beide Flächen für `report_type="morning"` geprüft werden, Then schließen
  beide Flächen die Größe konsistent aus — der Override wirkt über
  `get_metrics_for_report_type()` in beiden Aufrufern identisch, nicht nur
  in einer Fläche.
  - Test: derselbe Fall (Override + zwei Flächen) im Wächter geprüft,
    Erwartungswert fest im Test hinterlegt.

- **AC-5:** Given ein Trip mit gesetzter Grundauswahl und einer
  Ausblick-Auswahl, deren Feld `outlook_metrics` NICHT gesetzt ist (`None`,
  Altbestand), When `resolve_trip_outlook_metrics()` aufgerufen wird, Then
  bleibt der Rückgabewert `None` — die Drei-Werte-Semantik (`None`/`[]`/
  gefüllt) aus `resolve_outlook_metrics()` bleibt durch den Umbau
  unverändert erhalten, der neue Schnitt greift nur, wenn tatsächlich eine
  aufgelöste Liste vorliegt.
  - Test: `outlook_metrics=None` gesetzt, Rückgabewert von
    `resolve_trip_outlook_metrics()` explizit auf `is None` geprüft (nicht
    nur auf Falsy), damit eine Verwechslung mit `[]` sichtbar würde.

- **AC-6:** Given ein Trip mit gesetzter Grundauswahl und einer bewusst
  geleerten Ausblick-Auswahl (`outlook_metrics = []`), When
  `resolve_trip_outlook_metrics()` aufgerufen wird, Then bleibt der
  Rückgabewert `[]` — eine bewusste Leerung wird vom neuen Schnitt nicht in
  `None` oder eine gefüllte Liste verwandelt.
  - Test: `outlook_metrics=[]` gesetzt, Rückgabewert explizit auf `== []`
    (nicht nur auf Falsy) geprüft, getrennt vom `None`-Fall aus AC-5.

- **AC-7:** Given die freigegebenen Zusagen AC-14, AC-15 und AC-16 aus
  `docs/specs/modules/feat_1720_s1_trip_ausblick_metriken.md`, When der
  bestehende Test `tests/tdd/test_trip_outlook_metric_selection.py`
  (Funktionen `test_ac14_*`, `test_ac16_leere_grundauswahl_schneidet_die_
  vorschau_nicht`) nach dem Umbau erneut läuft, Then bleibt er grün OHNE
  Anpassung seiner Erwartungswerte — der Umbau ändert das beobachtbare
  Verhalten des Ausblicks nicht.
  - Test: bestehende Testdatei unverändert erneut ausgeführt; kein Diff an
    ihren Assertions im Änderungssatz dieser Scheibe.

- **AC-8:** Given `src/output/renderers/compare_metric_ids.py::
  resolve_channel_enabled_metrics()` (die Ortsvergleich-Umsetzung derselben
  ADR-0050-Regel mit abweichender `[]`-Semantik, #1366), When der Umbau
  dieser Scheibe abgeschlossen ist, Then ruft diese Funktion die neue
  Methode `allowed_metric_ids_for_report_type()` NICHT auf und ihr
  Verhalten bei `global_metrics == []` (Schnitt auf leer) bleibt
  unverändert — der Ortsvergleich-Pfad wird durch diese Scheibe nicht
  angefasst.
  - Test: bestehender Test
    `tests/unit/test_compare_channel_metric_cascade.py::
    test_global_leere_liste_ist_ein_maximum_und_schneidet_den_kanal_leer`
    läuft nach dem Umbau unverändert grün; zusätzlich ein neuer Fall im
    Wächter, der `global_metrics=[]` an `resolve_channel_enabled_metrics()`
    übergibt und auf `[]` prüft — bewusster Kontrast zu AC-2, wo dieselbe
    leere Eingabe beim Trip NICHT schneidet.

- **AC-9:** Given jemand führt künftig eine zweite, unabhängige
  ID-Filterung für Kanal-Layout ODER Ausblick ein (z. B. eine Kopie der
  D1-D4-Regel statt eines Aufrufs von
  `allowed_metric_ids_for_report_type()`), When derselbe Kaskaden-Fall aus
  AC-1 (bewusst abgewählte Größe) erneut durch den Wächter läuft, Then
  wird der Wächter rot, sobald die beiden Flächen für denselben Fall
  unterschiedliche Ergebnismengen liefern — der Wächter prüft
  Verhaltensgleichheit, nicht Dateiinhalt, und fängt damit auch ein
  Auseinanderlaufen künftiger Änderungen an nur einer Fläche.
  - Test: `tests/unit/test_trip_metric_cascade_single_source.py` enthält
    mindestens eine Prüfung, die beide Flächen mit identischen
    Eingabedaten aufruft und die Ergebnismengen direkt gegeneinander
    vergleicht (nicht nur je Fläche gegen einen festen Erwartungswert) —
    eine künftige Divergenz zwischen den Flächen wird dadurch unabhängig
    vom konkreten Regelinhalt sichtbar.

## Mutations-Gegenproben

Drei Verfälschungen, die der Adversary gezielt gegenprüfen muss:

1. `allowed_metric_ids_for_report_type()` gibt bei leerem `self.metrics`
   `set()` statt `None` zurück ⇒ **AC-2** muss rot werden (D4 kippt in
   „nichts erlaubt").
2. `_clip_to_global_maximum()` oder `resolve_trip_outlook_metrics()`
   verwendet weiterhin eine eigene, direkt aus `get_metrics_for_report_
   type()` gebaute Menge statt die neue Methode aufzurufen (die
   Eingemeindung bleibt nur behauptet, nicht real) ⇒ **AC-9** muss rot
   werden, sobald der Wächter die beiden Flächen absichtlich mit
   unterschiedlichen `report_type`-Overrides konfrontiert, die nur bei
   echter gemeinsamer Quelle konsistent aufgelöst werden.
3. Der Umbau zieht versehentlich `resolve_channel_enabled_metrics()` auf
   die neue Methode um (Eingemeindung der dritten Umsetzung) ⇒ **AC-8**
   muss rot werden, weil `global_metrics == []` dann nicht mehr auf `[]`
   schneidet, sondern der Trip-Semantik (nicht schneiden) folgt.

## Out of Scope

- **`resolve_channel_enabled_metrics()` (Ortsvergleich-Kanal-Auswahl,
  `compare_metric_ids.py:200-243`) wird NICHT auf die neue Methode
  umgestellt.** Bewusst andere `[]`-Semantik (#1366) — eine Eingemeindung
  bräche AC-8/#1366. Eigenes, noch offenes Thema für eine spätere,
  gesondert zu entscheidende Vereinheitlichung.
- **Kein neues Speicherformat für `outlook_metrics`.** Bleibt
  `{metric_id, aggregation}`-Paare, keine Umstellung auf reine
  Katalog-Kennungen (das ist Scheibe B / eigenes Epic-1435-Ticket).
- **Keine neuen Katalog-Kennungen.**
- **Keine Migration bestehender Daten** — reiner Code-Umbau ohne
  Persistenz-Änderung.
- **Frontend, API-Vertrag und gespeicherte Daten unverändert.**

## Known Limitations

- Die neue Methode löst ausschließlich die **Kanal-neutrale** Kaskade
  (Grundauswahl ↔ Ausblick/Kanal-Layout) zusammen. Sie ersetzt nicht die
  kanal-spezifische Ebenen-Erkennung (`_cascade_source_for_channel()`,
  Zeile 878) — die bleibt unverändert, da sie eine andere Frage
  beantwortet (welche Ebene liefert die Rohliste, nicht welche IDs davon
  erlaubt sind).
- 🔴 **Der Wächter fängt Divergenz, nicht Dopplung.** AC-9 wird rot, sobald
  die beiden Flächen für denselben Fall unterschiedlich entscheiden. Führt
  jemand eine zweite Umsetzung ein, die sich in allen geprüften Fällen
  **gleich** verhält, bleibt der Wächter grün — die Doppelpflege wäre wieder
  da, ohne dass ein Test anschlägt. Ein Wächter, der Dopplung als solche
  fängt, müsste die Codestruktur prüfen (z. B. AST-Suche nach einer zweiten
  ID-Mengen-Filterung); das ist bewusst NICHT Teil dieser Scheibe, weil ein
  Struktur-Wächter hier ohne belegten Fang eingeführt würde (Regel-Budget,
  s. CLAUDE.md). Der praktische Schutz liegt darin, dass eine zweite
  Umsetzung erfahrungsgemäß genau an den Randfällen (D4, `selectable`,
  Report-Typ-Overrides) auseinanderläuft — und die prüft AC-2/3/4.
- Die Divergenz zwischen Trip- und Ortsvergleich-Semantik bei leerer
  Grundauswahl (D4 vs. #1366, dokumentiert in
  `feat_1720_s1_trip_ausblick_metriken.md` unter „Known Limitations")
  bleibt nach dieser Scheibe unverändert bestehen — sie wird durch diese
  Scheibe nicht aufgelöst, nur die Trip-interne Doppelpflege.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — diese Scheibe setzt ADR-0050 (Regeln D1-D4) um,
  ohne eine Entscheidung zu ändern oder eine bestehende Zusage
  zurückzunehmen. Kein neues ADR nötig.
- **Rationale:** ADR-0050 legt fest, DASS die Kaskade als Verfeinerung
  gilt; diese Scheibe ändert nur, WO im Code diese Regel steht (eine
  Quelle statt zwei), nicht WAS sie besagt. Kein Trade-off, der eine
  Grundsatzentscheidung berührt.

## Changelog

- 2026-08-18: Initial spec created
