---
entity_id: issue_1200_alert_segment_reference
type: feature
created: 2026-07-09
updated: 2026-07-10
status: implemented
version: "1.0"
workflow: issue-1200-alert-segment-bezug
tags: [alerts, official-alerts, notification, segment-reference]
---

# Amtliche-Warnung-Mail: Etappen-/Segment-Bezug

## Approval

- [x] Approved

## Purpose

Die amtliche Warnungs-Mail (#1172, live seit Commit `8ac3b400`) zeigt pro
Warnung Schwere, Region und Gültigkeitszeitraum, aber nicht, welche
Segmente/Etappen des Trips konkret betroffen sind. Bei mehrtägigen Touren mit
mehreren Etappen in derselben Warnregion ist für den Nutzer unterwegs unklar,
ob die Warnung heute, morgen oder erst in fünf Tagen relevant wird. Diese Spec
ergänzt einen kompakten Segment-Bezug (Range/Aufzählung/Verdichtung/
Ziel-Sonderfall) ausschließlich im Standalone-Alert-Renderer.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py`
- **Identifier:** `def dedupe_official_alerts`, `def render_official_alert_notice_plain`, neue Funktion `def format_segment_reference`

> **Schicht-Bestätigung:** reine Python-Core-Änderung (`src/services/`,
> `src/output/renderers/`) — kein Go-API-, kein Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~60 neu / ~10 geändert
- **Files:** 3 Produktionsdateien + 2 Testdateien (1 modifiziert, 1 neu)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/models.py::OfficialAlert` | module (dataclass) | Alert-Datenmodell — bleibt UNVERÄNDERT (PO-Vorgabe: kein neues Feld) |
| `src/app/models.py::SegmentWeatherData.official_alerts` | module (field) | Quelle der Segment-Zuordnung: pro Segment bereits mit `official_alerts`-Liste befüllt |
| `src/output/renderers/email/helpers.py::build_segment_label` | function | Formatierungs-Konvention (Ziel-Sonderfall `"🏁 Ziel"`), Referenz für Stil — NICHT direkt wiederverwendbar (arbeitet auf Einzel-Segment, nicht auf Sets/Ranges) |
| `src/services/trip_alert.py::check_official_alert_triggers` | function | Aufrufer, der die Coord→Segment-Zuordnung vor dem Coord-Dedup aufbauen muss |
| `src/services/notification_service.py::send_official_alert` / `_dispatch_alert_message` | function | Pass-Through der Segment-Begleitstruktur bis zum Renderer |
| `services.alert_state.AlertStateService` | module | Dedupe-State über Zeit (Key `official_alert:{region_label}:{hazard}`) — bleibt segmentunabhängig, keine Migration nötig |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `dedupe_official_alerts()` (Zeile 88-102): Merge vereinigt zusätzlich Segment-ID-Sets statt nur Level zu vergleichen. `render_official_alert_notice_plain()` (105-132): neue Zeile `"Region: X — Segment N–M"` einfügen, nur wenn Segment-IDs vorhanden sind. Neue Helper-Funktion `format_segment_reference(segment_ids: list[str]) -> str` (Range/Aufzählung/Verdichtung/Ziel-Sonderfall) |
| `src/services/trip_alert.py` | MODIFY | `check_official_alert_triggers()` (920-962): Coord→Segment-Mapping (`coord_to_segments: dict[tuple, list[str]]`) VOR dem bestehenden Coord-Dedup (938-946, `seen`-Set) aufbauen, damit die Segment-Info nicht vor dem Alert-Abruf verloren geht. Rückgabetyp wechselt von `list[OfficialAlert]` zu `list[tuple[OfficialAlert, list[str]]]`. `_send_official_alert_only()` (978-1008): reicht die Begleitstruktur nur durch |
| `src/services/notification_service.py` | MODIFY | `send_official_alert()` (407-457) und `_dispatch_alert_message()` (498ff, `official_notices`-Parameter): Signatur/Datenfluss anpassen, damit die Segment-Begleitstruktur pass-through bis `render_official_alert_notice_plain()` gelangt — kein eigenes Segment-Wissen nötig |
| `tests/tdd/test_issue_1172_official_alert_dedup_info.py` | MODIFY | Bestehende Format-Assertions um die neue Segment-Zeile ergänzen; `test_shared_plain_renderer_unchanged` MUSS unverändert grün bleiben (beweist Compare-Pfad unangetastet) |
| `tests/tdd/test_alert_segment_reference.py` | CREATE | Neue Tests für Range/Aufzählung/Verdichtung/Ziel-Sonderfall (Namensregel: Verhalten statt Issue-Nummer) |

### Estimated Changes
- Files: 5 (3 Produktions-, 2 Testdateien)
- LoC: +60/-10

## Implementation Details

**1. Kein neues Feld auf `OfficialAlert` (PO-Vorgabe, final).** Die
Segment-Zuordnung läuft als separate Begleitstruktur `list[tuple[OfficialAlert,
list[str]]]` durch die Pipeline — `check_official_alert_triggers()` gibt
künftig diesen Typ zurück statt einer reinen `list[OfficialAlert]`.

**2. Coord→Segment-Mapping vor dem Coord-Dedup.** In
`check_official_alert_triggers()` wird aus `cached` (`list[SegmentWeatherData]`)
zuerst `coord_to_segments: dict[tuple[float, float], list[str]]` aufgebaut.
Beim bestehenden `get_official_alerts_for_location(*coord)`-Aufruf werden die
gefundenen Alerts mit den zugehörigen Segment-IDs getaggt (Tupel), BEVOR das
`seen`-Set die Koordinate verwirft — sonst geht die Segment-Info verloren,
wenn zwei Segmente dieselbe Koordinate teilen.

**3. `dedupe_official_alerts()` erweitert.** Merge nach `(region_label,
hazard)` vereinigt zusätzlich die Segment-ID-Mengen aller zur Gruppe
gehörenden Rohalerts (nicht nur Level-Vergleich wie bisher).

**4. Neue Helper-Funktion `format_segment_reference(segment_ids: list[str]) ->
str`** in `official_alerts.py` (bewusst nicht in `helpers.py`, um Kopplung zum
Compare-Pfad zu vermeiden):
- Numerische IDs werden sortiert und auf zusammenhängende Läufe geprüft.
- Zusammenhängender Lauf (z.B. `["3","4","5"]`) → `"Segment 3–5"`.
- Nicht zusammenhängend (z.B. `["3","5"]`) → `"Segment 3, 5"`.
- Mehr als 4 betroffene Segmente insgesamt → Verdichtung `"N Segmente"`
  (z.B. `"5 Segmente"`) — Begriff bewusst "Segmente", nicht "Etappen"
  (struktureller Bezug ist immer auf Segmente).
- `segment_id == "Ziel"` wird NIE in die numerische Range/Aufzählung gemischt,
  sondern immer als eigenes Element `"🏁 Ziel"` angehängt. Gemischtes Beispiel
  (PO-bestätigt): `"Segment 3–5, 🏁 Ziel"`.

**5. `render_official_alert_notice_plain()` erweitert.** Signatur wechselt von
`list["OfficialAlert"]` zu `list[tuple["OfficialAlert", list[str]]]`. Neue
Zeile nach der Region-Zeile: `f"Region: {a.region_label or 'unbekannt'} — "
f"{format_segment_reference(segment_ids)}"`, nur wenn `segment_ids`
nicht-leer ist. PO-bestätigtes Format-Beispiel:

```
🟠 ORANGE — Hitze
Region: Haute-Corse — Segment 3–5
Gültig: Sat 11.07. 14:00 – Sun 12.07. 22:00
```

**6. Pass-Through in `notification_service.py`.** `send_official_alert()` und
`_dispatch_alert_message()` reichen die Tupel-Liste unverändert an
`render_official_alert_notice_plain()` durch, ohne eigenes Segment-Wissen.

**7. Compare-/Briefing-Pfad bewusst unangetastet.**
`render_official_alerts_plain()`/`_html()` (dieselbe Datei) bekommen KEINEN
Segment-Bezug — dort existiert kein Trip-Segment-Kontext (Orts-Vergleich hat
keine Etappen). `test_shared_plain_renderer_unchanged` sichert das ab.

## Expected Behavior

- **Input:** `list[tuple[OfficialAlert, list[str]]]` (Alert + zugehörige
  Segment-IDs, IDs als Strings inkl. Sonderwert `"Ziel"`) an
  `render_official_alert_notice_plain()`.
- **Output:** Plain-Text-Zeilenliste, pro dedupliziertem Alert ein Block mit
  Schwere-Zeile, `"Region: X — Segment-Referenz"`-Zeile und Gültigkeits-Zeile.
- **Side effects:** keine — reine Formatierungs-/Datenfluss-Änderung, kein
  neuer I/O, kein neuer State.

## Acceptance Criteria

- **AC-1:** Given eine amtliche Warnung betrifft genau ein Segment (z.B.
  Segment 3) / When die Standalone-Alert-Mail gerendert wird / Then zeigt die
  Region-Zeile `"Region: Haute-Corse — Segment 3"`.
  - Test: `render_official_alert_notice_plain()` mit einem Alert-Tupel
    `(alert, ["3"])` aufrufen und die konkrete Textzeile im Rückgabewert
    prüfen — beweist reales Rendering-Verhalten, kein Dateiinhalt-Check.

- **AC-2:** Given eine Warnung betrifft die zusammenhängenden Segmente 3, 4
  und 5 / When die Segment-Referenz für diese Alert-Zeile gerendert wird /
  Then erscheint `"Segment 3–5"` als Range, nicht als Aufzählung.
  - Test: `format_segment_reference(["3","4","5"])` liefert `"3–5"`
    (bzw. der volle Zeilentest über `render_official_alert_notice_plain()`
    mit `segment_ids=["3","4","5"]`), verifiziert am zurückgegebenen String.

- **AC-3:** Given eine Warnung betrifft die nicht zusammenhängenden Segmente
  3 und 5 (Segment 4 nicht betroffen) / When die Segment-Referenz für diese
  Alert-Zeile gerendert wird / Then erscheint `"Segment 3, 5"` als Aufzählung
  mit Komma, nicht als Range mit Bindestrich.
  - Test: `format_segment_reference(["3","5"])` liefert `"3, 5"` — Test prüft
    explizit, dass KEIN `"–"` im Ergebnis vorkommt.

- **AC-4:** Given eine Warnung betrifft mehr als vier Segmente (z.B. 3, 4, 5,
  6, 7) / When die Segment-Referenz für diese Alert-Zeile gerendert wird /
  Then wird zur Anzahl verdichtet: `"5 Segmente"` (mit korrekter Zahl,
  Begriff "Segmente" nicht "Etappen").
  - Test: `format_segment_reference(["3","4","5","6","7"])` liefert
    `"5 Segmente"`; zusätzlicher Test mit 5 nicht-zusammenhängenden IDs
    beweist, dass die Verdichtung unabhängig von Range/Aufzählung greift.

- **AC-5:** Given eine Warnung betrifft ausschließlich das Ziel-Segment
  (`segment_id == "Ziel"`, kein weiteres Segment) / When die Segment-Referenz
  für diese Alert-Zeile gerendert wird / Then erscheint ausschließlich
  `"🏁 Ziel"` ohne "Segment"-Präfix und ohne numerische Range.
  - Test: `format_segment_reference(["Ziel"])` liefert exakt `"🏁 Ziel"`.

- **AC-6:** Given eine Warnung betrifft die Segmente 3, 4, 5 UND das Ziel /
  When die Segment-Referenz für diese Alert-Zeile gerendert wird / Then
  erscheint der gemischte Fall als `"Segment 3–5, 🏁 Ziel"` — Ziel wird NIE in
  die numerische Range gemischt.
  - Test: `format_segment_reference(["3","4","5","Ziel"])` liefert exakt
    `"3–5, 🏁 Ziel"` (Reihenfolge: numerischer Teil zuerst, Ziel danach).

- **AC-7:** Given der Orts-Vergleich (Compare-Pfad) rendert dieselben
  amtlichen Warnungen über `render_official_alerts_plain()`/`_html()` / When
  diese Funktionen aufgerufen werden / Then bleibt ihre Ausgabe exakt wie vor
  dieser Änderung — kein Segment-Bezug, keine Signaturänderung.
  - Test: bestehender Test `test_shared_plain_renderer_unchanged`
    (`tests/tdd/test_issue_1172_official_alert_dedup_info.py`) bleibt
    UNVERÄNDERT grün — beweist, dass der Compare-Pfad nicht angefasst wurde.

## Known Limitations

- **Race-Condition-Historie:** Eine frühere #1172-Session hatte einen
  Etappen-Bezug bereits vollständig implementiert und mit 7 E2E-Tests
  abgesichert. Diese Implementierung wurde verworfen, weil eine parallele
  Session mit einem einfacheren Format zuerst deployt hat (Commit
  `8ac3b400`). Der alte Code existiert nicht mehr — diese Spec baut den
  Segment-Bezug NEU gegen den aktuell deployten Stand, nicht als
  Wiederherstellung des alten Codes. Wortlaut/Ranges/Verdichtungsregel
  unterscheiden sich bewusst vom verworfenen Vorgänger (PO-Format ist final
  in dieser Spec).
- Der Compare-/Briefing-Pfad (`render_official_alerts_plain`/`_html`) bleibt
  ohne Segment-Bezug, da dort kein Trip-Segment-Kontext existiert (Orts-
  Vergleich vergleicht Orte, keine Etappen). Das ist kein Bug, sondern
  bewusster Scope-Schnitt.
- Die Verdichtungsschwelle (>4 Segmente) ist ein fixer PO-Wert, keine
  konfigurierbare Einstellung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Formatierungs- und Datenfluss-Erweiterung innerhalb
  einer bestehenden, bereits deployten Alert-Pipeline (#1172/#1088). Es wird
  kein neues Datenmodell-Feld eingeführt (PO-Vorgabe), keine neue externe
  Schnittstelle, kein neuer Persistenz-Mechanismus und keine neue
  Architektur-Schicht berührt — die Änderung bleibt innerhalb der
  bestehenden Pass-Through-Struktur (`trip_alert.py` →
  `notification_service.py` → `official_alerts.py`-Renderer). Eine
  ADR-pflichtige Architekturentscheidung liegt daher nicht vor.

## Changelog

- 2026-07-09: Initial spec created (Issue #1200)
- 2026-07-10: Implementiert, Adversary VERIFIED, Validation PASS
