---
entity_id: fix_2098_ausblick_acc_und_sonnenstunden
type: bugfix
created: 2026-08-23
updated: 2026-08-23
status: draft
version: "1.0"
tags: [ausblick, acc, sonnenstunden, trip-briefing, issue-2098]
workflow: fix-2098-ausblick-acc-und-sonnenstunden
---

# #2098 — Ausblick zeigt ACC nicht mehr und Sonnenstunden bleiben `–`

## Approval

- [x] Approved — PO Henning, 2026-08-23, „go" (alle 14 ACs inkl. Befund C)

## Purpose

In der 3-Tages-Vorschau der Trip-Briefing-E-Mail sind zwei Anzeigefehler aufgetreten: die
Spalte **ACC** (Prognose-Genauigkeit) ist verschwunden, und die Spalte **Sonnenstunden**
zeigt in allen Zeilen `–`, obwohl beide Werte tatsächlich vorhanden sind. Diese Spec legt
fest, wie beide Werte wieder zuverlässig in der Mail erscheinen, ohne die Trip/Compare-
Teilungs-Invariante zu verletzen und ohne die #710-Regel (ACC keine wählbare Metrik) zu
berühren.

## Source

- **File:** `src/output/renderers/email/outlook.py`
- **Identifier:** `render_outlook_table()` (`:45`), `render_outlook_plain()` (`:263`) — der
  konfigurierbare Zweig (`metrics is not None`) beider Funktionen kennt `show_acc` nicht
- **File:** `src/services/weather_metrics.py`
- **Identifier:** `summarize_points()` (`:534-568`) — `aggregation_config`-Dict ohne Regel
  für `sunny_hours`

> **Schicht-Hinweis:** Python-Core/Domain-Backend (`src/services/`,
> `src/output/renderers/email/`). Kein Frontend-, Go- oder API-Vertrag betroffen.

## Estimated Scope

- **LoC:** ~60–100 (Fix ~15, Tests ~60–80, Doku ~10)
- **Files:** 5–6 (4 MODIFY, 1 CREATE, 1 Doku-MODIFY)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_outlook_table()` / `render_outlook_plain()` (`outlook.py:45,263`) | Funktion | geteilter Renderer Trip+Compare, hier liegt die Wurzel beider Befunde |
| `build_outlook_row()` (`outlook.py`) | Funktion | schreibt `confidence_pct` bereits ins Row-Dict, unverändert wiederverwendbar |
| `aggregate_stage()` (`src/services/weather_metrics.py:1352`) | Funktion | Etappen-Aggregation; baut Ergebnis ausschließlich aus Feldern mit Regel in `aggregation_config` |
| `summarize_points()` (`src/services/weather_metrics.py:534-568`) | Funktion | Segment-Aggregation, Quelle des `aggregation_config`-Dicts, das `aggregate_stage()` weiterverwendet |
| `metric_catalog.py:604` (`sunshine`-Definition) | Katalog-Eintrag | `summary_fields={"sum": "sunny_hours"}` — Zielfeld, das die Aggregationsregel treffen muss |
| `metric_catalog.py:418-423` (`confidence`, `selectable=False`) | Katalog-Eintrag | ADR-0005/#710 — ACC darf nie als wählbare Metrik erscheinen, bleibt unverändert |
| `outlook_columns()` (`compare_outlook_metric_ids.py:298`) | Funktion | Kopfzeilen-Quelle des konfigurierbaren Zweigs; ACC wird NICHT über diesen Pfad angehängt |
| `compare_html.py:1257` (`show_acc=False`) | Aufrufstelle | Ortsvergleich — muss ohne ACC-Spalte bleiben |
| `html.py:1403` (`show_acc=True`) | Aufrufstelle | Trip — muss die ACC-Spalte wieder tragen |
| `tests/tdd/test_trip_outlook_dispatch_mail.py:552` | Test | verankert aktuell das Gegenteil (kein ACC), muss angepasst werden |
| `tests/tdd/test_trip_outlook_metric_selection.py:310-355` | Test | bewacht die #710-Invariante (ACC nicht wählbar), muss grün bleiben |

## Implementation Details

```
Befund A — Sonnenstunden:
  summarize_points() setzt sunny_hours (weather_metrics.py:534), aber die
  aggregation_config im selben Summary-Objekt (:553-568) trägt dafür keine
  Regel. aggregate_stage() iteriert ausschließlich Felder mit Regel und
  überschreibt sunny_hours dadurch mit dem Dataclass-Default None.
  Fix: "sunny_hours": "sum" ergänzen — Ergebnis ist stets Mehrsegment,
  weil aggregate_stage() nur bei >1 Segment aufgerufen wird
  (compact_summary.py:265-268); bei Einzelsegment-Etappen läuft der Wert
  unbeschädigt durch (kein Fehler, aber auch kein Testnachweis für den Fix).

Befund B — ACC:
  render_outlook_table()/render_outlook_plain() lesen show_acc NUR im
  Altform-Zweig (metrics is None). Seit #1848 A3 liefert
  resolve_trip_outlook_metrics() für den Trip fast immer eine Metrikliste
  -> Trip läuft praktisch immer über den konfigurierbaren Zweig, der ACC
  nicht kennt.
  Fix: show_acc im konfigurierbaren Zweig auswerten, ACC-Spalte fest HINTER
  den gewählten Metriken anhängen -- außerhalb outlook_columns()/cells,
  damit die #710-Invariante (ACC nie wählbare Metrik) strukturell
  unberührt bleibt. confidence_pct steht bereits im Row-Dict
  (build_outlook_row(), VOR dem metrics-Zweig geschrieben).

Befund C (Erweiterung) — ACC im Klartext:
  render_outlook_plain() gab ACC noch nie aus, auch nicht im Altform-Zweig
  vor #1848/#2049. Im HTML ist ACC ein reiner Farbpunkt (_acc_dot(), vier
  Stufen >=80/>=60/>=40/<40) -- für Klartext-Leser unsichtbar. Ein
  vierstufiges deutsches Wort schließt die Lücke gemäß Projektregel
  "HTML=Normalfassung, Farbe im HTML -> Wort im Klartext".
```

## Expected Behavior

- **Input:** Trip-Briefing-Versand (E-Mail, Modus `full` oder `compact`) mit mehrsegmentigen
  Etappen im 3-Tages-Ausblick, konfigurierte Ausblick-Metriken (Grundauswahl oder
  Nutzerauswahl gemäß #1848 A3)
- **Output:** In der HTML-Fassung erscheint hinter den gewählten Metriken eine ACC-Spalte mit
  dem bekannten 4-stufigen Farbpunkt; in der Klartext-Fassung erscheint ein 4-stufiges
  ACC-Wort; die Sonnenstunden-Spalte zeigt einen Zahlenwert statt `–`, sobald die Etappe
  mehr als ein Segment hat
- **Side effects:** keine — reine Renderer-/Aggregations-Korrektur, keine Persistenz- oder
  API-Änderung. Der Ortsvergleich (`show_acc=False`) bleibt unverändert ohne ACC-Spalte.

## Acceptance Criteria

### Befund A — Sonnenstunden

- **AC-1:** Given eine Trip-Etappe mit mehr als einem Segment und unterschiedlichen
  Sonnenstunden-Werten je Segment / When das Trip-Briefing gerendert wird / Then zeigt die
  Sonnenstunden-Spalte im 3-Tages-Ausblick einen konkreten Zahlenwert (z. B. `6.5`) statt `–`.

- **AC-2:** Given dieselbe Mehrsegment-Etappe / When die Sonnenstunden-Spalte geprüft wird /
  Then entspricht der angezeigte Wert der Summe der Segment-Sonnenstunden (Aggregationsregel
  `sum`, analog zur Katalog-Definition `summary_fields={"sum": "sunny_hours"}`) und nicht
  einem beliebigen Platzhalter oder dem Wert nur eines Segments.

- **AC-3:** Given dieselbe Etappe einmal als ein Segment und einmal auf mehrere Segmente
  verteilt / When beide Fassungen im Ausblick gerendert werden / Then zeigen beide einen
  Sonnenstunden-Wert, und die mehrteilige Fassung zeigt die Summe ihrer Segmente statt `–` —
  der Nachweis MUSS über die mehrteilige Fassung geführt werden, weil nur sie den Verlust
  sichtbar macht.

  > **Richtigstellung (RED-Phase, 2026-08-23):** Die ursprüngliche Begründung („Einzelsegment
  > war nie betroffen") gilt nur für die Kompaktzeile — dort bremst
  > `compact_summary.py:262-268` die Aggregation bei einem Segment ab. Der **Ausblick** ruft
  > `aggregate_stage()` bedingungslos (`trip_report_scheduler.py:2422`) und verliert die
  > Sonnenstunden daher auch bei Einzelsegment-Etappen. Die Zusicherung bleibt inhaltlich
  > gleich scharf, die Begründung ist korrigiert.

- **AC-4:** Given den vollständigen Metrik-Katalog mit `summary_fields` / When alle Felder von
  `SegmentWeatherSummary` gegen die `aggregation_config` von `summarize_points()` abgeglichen
  werden / Then trägt außer der behobenen Regel für `sunny_hours` keine weitere Metrik eine
  fehlende Aggregationsregel (Invariante: dieser Fix bleibt die einzige Änderung an
  `aggregation_config`, keine zweite Metrik wird angefasst).

### Befund B — ACC-Spalte im Trip-Ausblick

- **AC-5:** Given ein Trip mit konfigurierten Ausblick-Metriken (der heute übliche,
  konfigurierbare Renderer-Zweig, `metrics` gesetzt) / When das Trip-Briefing als HTML-Mail
  gerendert wird / Then erscheint eine ACC-Spalte mit dem bekannten 4-stufigen Farbpunkt
  hinter den gewählten Metrik-Spalten, unabhängig davon, welche Metriken der Nutzer gewählt
  hat.

- **AC-6:** *(gehört zur Erweiterung Befund C — entfällt vollständig, wenn Befund C
  gestrichen wird)* Given denselben konfigurierbaren Renderer-Zweig / When der Ausblick als
  Klartext-Mail gerendert wird / Then erscheint eine ACC-Spalte mit einem 4-stufigen
  deutschen Wort (analog zu den HTML-Farbstufen) hinter den gewählten Metrik-Spalten.

- **AC-7:** Given einen Prognose-Genauigkeits-Wert von 85 % (hohe Stufe) und einen zweiten
  Wert von 35 % (niedrigste Stufe) / When beide Etappen im selben Ausblick gerendert werden /
  Then unterscheiden sich die HTML-Farbpunkte beider Zeilen sichtbar (Gegenprobe mit einem
  plausibel falschen Wert, nicht nur mit `None`) — und, sofern Befund C umgesetzt wird,
  ebenso die Klartext-Wörter.

- **AC-8:** Given einen Ortsvergleich-Ausblick (`show_acc=False`) / When er im
  konfigurierbaren Zweig als HTML- und als Klartext-Mail gerendert wird / Then erscheint
  weder eine ACC-Spalte in der Kopfzeile noch eine ACC-Zelle in den Datenzeilen — der Fix
  darf die Compare-Fläche nicht verändern.

- **AC-9:** Given die Metrik-Auswahlfläche im Frontend (Backend-Auflösung
  `available_aggregations`/`derived_aggregations`) / When nach der Behebung geprüft wird,
  welche Metriken auswählbar sind / Then taucht `confidence`/ACC weiterhin **nicht** in der
  Liste der wählbaren Ausblick-Metriken auf (ADR-0005/#710 bleibt unberührt, die ACC-Spalte
  entsteht ausschließlich als fest angehängte Zusatzspalte außerhalb der Auswahl).

- **AC-10:** Given eine Kopfzeile und eine Datenzeile desselben Ausblicks / When beide
  gerendert werden / Then steht die ACC-Spalte an derselben Position relativ zu den übrigen
  Spalten in Kopf- und Datenzeile (kein Auseinanderlaufen von Beschriftung und Wert).

### Befund C — ACC-Wort im Klartext (Erweiterung über den gemeldeten Fehler hinaus)

> Dieser Block erweitert den gemeldeten Fehler: die Klartext-Fassung hat ACC auch vor #2098
> nie gezeigt. Der PO kann diesen Block bei der Freigabe gezielt streichen, ohne Befund A
> oder B zu beeinträchtigen.

- **AC-11:** Given die vier HTML-Farbstufen (`_acc_dot()`: ≥80 / ≥60 / ≥40 / <40) / When das
  entsprechende deutsche Klartext-Wort für jede Stufe festgelegt wird / Then ist jede Stufe
  durch ein eindeutiges, unterscheidbares Wort ohne Handlungsempfehlung repräsentiert (reine
  Zustandsbeschreibung, ADR-0007) — z. B. „hoch" / „mittel" / „niedrig" / „sehr niedrig", exakte
  Wortwahl liegt beim Implementierer.

- **AC-12:** Given einen fehlenden `confidence_pct`-Wert (`None`) / When die Klartext-Zeile
  gerendert wird / Then erscheint für ACC weiterhin `–` wie im HTML-Fall — kein Absturz, kein
  leeres Feld.

### Abgelöste Entscheidung — #1848 A3 / Test `test_trip_outlook_dispatch_mail.py:552`

- **AC-13:** Given den bestehenden Test `tests/tdd/test_trip_outlook_dispatch_mail.py:552`
  (prüft aktuell `kopf[1:] != [..., "ACC"]`, Kommentar „#1848 A3, AC-3", PO-Freigabe
  2026-08-21) / When der Test nach der Behebung läuft / Then ist die Prüfung so angepasst,
  dass sie das **neue** Verhalten (ACC-Spalte vorhanden) verifiziert, statt weiterhin ihre
  Abwesenheit zu verlangen. Die übrige #1848-A3-Absicht — Grundauswahl statt fester
  Sieben-Spalten-Liste — bleibt unverändert gültig; ACC kommt nicht als achte feste
  Katalog-Spalte zurück, sondern als fest angehängte Zusatzspalte hinter der Grundauswahl.

### Testlücke — produktiver Zweig statt totem Altform-Zweig

- **AC-14:** Given die bestehenden ACC-Wächter (`test_shared_outlook_renderer.py:132-199`,
  `test_trip_outlook_parity.py:94-122`), die ohne `metrics=`-Parameter aufrufen und damit den
  inzwischen für den Trip toten Altform-Zweig prüfen / When die neuen bzw. angepassten Tests
  für diese Spec geschrieben werden / Then rufen sie `render_outlook_table()` /
  `render_outlook_plain()` ausdrücklich **mit** `metrics` auf (dem produktiven, seit #1848 A3
  im Trip aktiven Zweig) — ein Test, der nur den Altform-Zweig träfe, gilt als nicht
  aussagekräftig für diese Spec.

## Known Limitations

- **Nur `sunny_hours` betroffen.** Das Audit über alle 26 `MetricDefinition`s mit
  `summary_fields` (inkl. aller `OUTLOOK_FRIENDLY_CAPABLE`- und Grundauswahl-Metriken) hat
  ergeben, dass `sunny_hours` die einzige Lücke in `aggregation_config` ist. Keine weitere
  Metrik wird im Rahmen dieser Spec angefasst (AC-4).
- **Nur Trip betroffen, Sonnenstunden.** `aggregate_stage()` läuft ausschließlich im
  Trip-Pfad; der Ortsvergleich nutzt `summarize_points()`/`comparison_engine.py` ohne den
  `aggregation_config`-Rebuild und zeigt Sonnenstunden bereits korrekt.
- **ACC bleibt für den Ortsvergleich unsichtbar** — bewusst, `show_acc=False` bleibt
  unverändert (AC-8), Confidence ist keine per-Ort-Metrik (#710).
- **Reihenfolge-Kopplung entwarnt:** Kopf und Zellen entstehen im konfigurierbaren Zweig
  bereits aus je einer zusammenhängenden Editierstelle pro Funktion; eine fest angehängte
  ACC-Spalte führt zu keinem neuen Indexrisiko.
- **Keine Frontend-, Go- oder API-Änderung.** Reine Renderer-/Aggregations-Korrektur im
  Python-Core.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — wendet ADR-0005/#710 (Confidence nicht wählbar) unverändert an
- **Rationale:** Diese Spec stellt ein Anzeigeverhalten wieder her, das vor #1848 A2/A3
  bestand, ohne eine dokumentierte Entscheidung zu ändern. #710 bleibt vollständig in Kraft:
  ACC entsteht strukturell außerhalb des Metrik-Auswahlsystems (fest angehängt, nicht über
  `outlook_columns()`/Katalog), kann also nie als wählbare Spalte erscheinen. Die
  #1848-A3-Entscheidung (Grundauswahl statt feste Sieben-Spalten-Liste) bleibt in ihrem Kern
  gültig — siehe „Abgelöste Entscheidung" oben für die eine bewusst zurückgenommene
  Nebenfolge.

## Changelog

- 2026-08-23: Initial spec created
