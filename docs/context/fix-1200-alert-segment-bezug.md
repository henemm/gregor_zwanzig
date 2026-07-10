# Context: fix-1200-alert-segment-bezug

## Request Summary
Die deployte amtliche-Warnung-Mail (#1172, Commit `8ac3b400`) zeigt pro Warnung
Schwere/Region/Gültigkeit, aber nicht, welche Etappe(n) des Trips betroffen sind.
#1200 ergänzt einen Segment-/Etappen-Bezug (Range/Aufzählung/Ziel-Sonderfall),
analog zur bestehenden `build_segment_label()`-Konvention.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/official_alerts.py` | `dedupe_official_alerts()` (Zeile 88-102, dedupliziert nach `(region_label, hazard)`, behält höchstes Level) und `render_official_alert_notice_plain()` (105-132, baut die Standalone-Alert-Zeilen). Hier muss die Segment-Zeile ergänzt werden. |
| `src/output/renderers/email/helpers.py` | `build_segment_label()` (Zeile 768-802) — bestehende Konvention für "Segment N"/"🏁 Ziel"/km-Range. Referenz für Formatierungsstil, aber nicht direkt wiederverwendbar (arbeitet auf `change.segment_id` einzeln, nicht auf Sets/Ranges). |
| `src/services/trip_alert.py` | `check_official_alert_triggers()` (920-962) sammelt Alerts pro **Koordinate** (nicht pro Segment!) — dedupliziert Koordinaten via `seen`-Set VOR dem Abruf. Segment-Zuordnung geht hier bereits verloren, wenn zwei Segmente dieselbe Koordinate teilen. `_send_official_alert_only()` (978-1008) und `_check_and_send_official_alerts`-Aufrufer (Zeile 325-337) haben Zugriff auf `cached: list[SegmentWeatherData]`. |
| `src/services/notification_service.py` | `send_official_alert()` (407-457, Standalone-Pfad #1088) und `_dispatch_alert_message()` (498ff, kombinierter Wetter-Delta+Alert-Pfad, `official_notices`-Parameter ab Zeile 507/521) rufen beide `render_official_alert_notice_plain()` auf. |
| `src/services/official_alerts/models.py` | `OfficialAlert`-Dataclass (Zeile 15-27): `source, hazard, level, label, valid_from, valid_to, url, region_label` — **kein** Segment-Feld, soll laut Issue auch keins bekommen. |
| `src/app/models.py:405-406` | `SegmentWeatherData.official_alerts: List[OfficialAlert]` — bereits pro Segment befüllt, ist die Quelle für die Segment-Zuordnung. |

## Existing Patterns

- **`build_segment_label()`**: Formatiert ein Segment als `"Segment N (HH:MM–HH:MM)"`, `"Segment N, km X–Y, ..."` oder `"🏁 Ziel (HH:MM)"` — Ziel-Sonderfall ohne "Segment"-Präfix. Vorbild für Formatierungsregeln, muss aber für Ranges/Aufzählungen (`"Segment 3–5"`, `"Segment 3, 5"`, `">4 → mehrere Etappen"`) neu geschrieben werden — die bestehende Funktion behandelt nur ein einzelnes Segment.
- **`dedupe_official_alerts()`**: Gruppiert nach `(region_label, hazard)`, behält höchstes Level. Jede Merge-Operation, die mehrere Rohalerts zu einem Repräsentanten kollabiert, verliert dabei implizit die Info, aus welchen Koordinaten/Segmenten die Gruppe stammt — muss um eine parallele Segment-Set-Vereinigung erweitert werden.
- **Geteilter Renderer-Grundsatz (Epic #1073 Punkt 6, `helpers.py` Docstring)**: ein gemeinsamer Renderer statt Kopien. Der Compare-/Briefing-Pfad (`render_official_alerts_plain`/`_html`) bleibt laut Issue **bewusst unverändert** (kein Trip-Segment-Kontext dort) — nur der Standalone-Renderer (`render_official_alert_notice_plain`, #1172) bekommt den Segment-Bezug.

## Dependencies

- **Upstream:** `check_official_alert_triggers()` konsumiert `get_official_alerts_for_location()` (pro Koordinate) und `AlertStateService` (Dedupe-State über Zeit, key `official_alert:{region_label}:{hazard}` — segmentunabhängig, bleibt so).
- **Downstream:** `_send_official_alert_only()` → `NotificationService.send_official_alert()` → `render_official_alert_notice_plain()`. Zweiter Pfad: `check_and_send_alerts()` → `_dispatch_alert_message(official_notices=...)` → dieselbe Render-Funktion.
- **Datenfluss-Lücke:** Der Koordinaten-Dedup in `check_official_alert_triggers()` (Zeile 938-946, `seen`-Set) verwirft die Segment-Zuordnung bereits VOR dem eigentlichen `dedupe_official_alerts()`-Aufruf. Für einen korrekten Segment-Bezug muss die Coord→Segment-Zuordnung VOR diesem Verwerfen mitgeführt werden (z.B. `coord → [segment_id, ...]`), dann bei jedem Alert-Fund mitgetaggt, und durch `dedupe_official_alerts()` hindurch als Segment-Set weitergereicht (Merge = Vereinigung der Segment-Sets, nicht nur Level-Vergleich).

## Existing Specs

- Kein dediziertes Spec-Dokument zu #1172/#1088 in `docs/specs/modules/` gefunden (Suche ohne Treffer) — Kontext kommt primär aus Issue-Historie und Code-Kommentaren (`Issue #1088`, `Issue #1172` Referenzen im Code).

## Risks & Considerations

- **Kein neues Feld auf `OfficialAlert`** (PO-Vorgabe im Issue) → Segment-Zuordnung muss als separate Begleitstruktur durch die Pipeline laufen (z.B. `list[tuple[OfficialAlert, list[str]]]` oder paralleles Dict `alert_key -> segment_ids`). Das ändert die Signatur von `check_official_alert_triggers()`, `dedupe_official_alerts()`, `render_official_alert_notice_plain()`, `send_official_alert()`, `_dispatch_alert_message()` — **5 Funktionen in 3 Dateien**, nicht nur eine Formatierungs-Änderung.
- **Race-Condition-Historie:** Eine frühere #1172-Session hatte diesen Etappen-Bezug bereits vollständig implementiert + mit 7 E2E-Tests abgesichert, wurde aber verworfen, weil eine parallele Session mit einfacherem Format zuerst deployt hat. Diese alte Implementierung existiert nicht mehr im Code (verworfen) — muss gegen den JETZT aktuellen Code (Commit `8ac3b400`) neu gebaut werden, nicht wiederhergestellt.
- **Bestehende Tests** (`tests/tdd/test_issue_1172_official_alert_dedup_info.py`, 341 Zeilen, u.a. `test_dedupe_keeps_max_level_and_separates_hazards`, `test_render_notice_plain_*`, `test_shared_plain_renderer_unchanged`) prüfen exakte Zeilenformate — Änderungen an `dedupe_official_alerts()`/`render_official_alert_notice_plain()` müssen diese Tests weiter erfüllen oder bewusst (mit Begründung) anpassen. `test_shared_plain_renderer_unchanged` ist ein Signal, dass der Compare-/Briefing-Pfad NICHT angefasst werden darf.
- **Verdichtungsregel `>4 Segmente → "mehrere Etappen"`** braucht eine klare Schwellen-Definition für die Spec-Phase (z.B. Zusammenhang: "range wenn lückenlos aufsteigend", sonst Aufzählung, sonst ab 5 verdichten).
- **Ziel-Sonderfall:** `segment_id == "Ziel"` (String, kein numerischer Index) muss beim Range-/Sortier-Vergleich mit numerischen Segment-IDs speziell behandelt werden (kann nicht einfach in eine numerische Range gemischt werden).

## Analysis

### Type
Feature (Ergänzung eines bestehenden, deployten Formats — kein Bugfix).

### Blast-Radius-Bestätigung (Explore-Agent, 2026-07-09)
- `dedupe_official_alerts()` und `render_official_alert_notice_plain()` werden **ausschließlich** von `trip_alert.py` und `notification_service.py` aufgerufen (plus der Definitionsdatei selbst) — keine weiteren Aufrufer in `src/`.
- **Keine wiederverwendbare Range-Utility** im Code vorhanden (`_range_pill` in `helpers.py:1026` ist HTML-Pill für einen Min/Max-Wert, keine Liste-zu-Range-Kompression für IDs) — die Range-/Aufzählungs-/Verdichtungs-Logik muss neu geschrieben werden.
- Nur die zwei bekannten Testdateien (`test_issue_1088_...`, `test_issue_1172_...`) berühren die betroffenen Funktionen.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_alert.py` | MODIFY | `check_official_alert_triggers()`: Coord→Segment-Zuordnung VOR dem Coord-Dedup (Zeile 938-946) mitführen, Alerts mit Segment-IDs taggen statt bloße `OfficialAlert`-Liste zurückzugeben |
| `src/output/renderers/alert/official_alerts.py` | MODIFY | `dedupe_official_alerts()`: Merge muss Segment-ID-Sets vereinigen statt nur Level vergleichen. `render_official_alert_notice_plain()`: neue Zeile "Region: X — Segment N–M" einfügen. Neue kleine Helper-Funktion für Range/Aufzählung/Verdichtung + Ziel-Sonderfall |
| `src/services/notification_service.py` | MODIFY | `send_official_alert()` / `_dispatch_alert_message()`: Signatur/Datenfluss anpassen, damit die Segment-Begleitstruktur bis zum Renderer durchgereicht wird |
| `tests/tdd/test_issue_1172_official_alert_dedup_info.py` | MODIFY | Bestehende Format-Assertions anpassen (neue Zeile), `test_shared_plain_renderer_unchanged` bleibt unverändert (Compare-Pfad!) |
| `tests/tdd/test_alert_segment_reference.py` (oder ähnlich, Namensregel CLAUDE.md) | CREATE | Neue Tests für Range/Aufzählung/Verdichtung/Ziel-Sonderfall |

### Scope Assessment
- Files: 3 Produktionsdateien + 1-2 Testdateien
- Estimated LoC: +60/-10 (neue Helper-Funktion für Range/Enum/Verdichtung ~30 LoC, Datenfluss-Anpassungen in 3 Funktionen ~20 LoC, Tests separat)
- Risk Level: MEDIUM — kein Infra-/Auth-Pfad, aber ändert real versendete Nutzer-Mail-Inhalte; bestehende Tests mit exakten Zeilenformaten müssen bewusst angepasst werden

### Technical Approach (Empfehlung)
1. **Begleitstruktur statt neues Datenmodell-Feld** (PO-Vorgabe): `check_official_alert_triggers()` gibt künftig `list[tuple[OfficialAlert, list[str]]]` zurück (Alert + zugehörige Segment-IDs), statt bloßer `list[OfficialAlert]`. Das hält `OfficialAlert` unverändert und minimiert die Kopplung.
2. **Coord→Segment-Mapping vor dem Coord-Dedup bauen**: in `check_official_alert_triggers()` zuerst `coord_to_segments: dict[tuple, list[str]]` aus `cached` aufbauen, dann beim `get_official_alerts_for_location(*coord)`-Aufruf die zugehörigen Segment-IDs an jeden gefundenen Alert anhängen (als Tupel).
3. **`dedupe_official_alerts()` erweitern** (neuer Parametername oder neue Funktion `dedupe_official_alerts_with_segments()`, um den bestehenden Aufrufer-Vertrag mit reiner `list[OfficialAlert]` nicht zu brechen, falls andere Stellen die einfache Signatur brauchen — aktuell laut Explore-Check aber keine): Merge-Logik vereinigt zusätzlich die Segment-ID-Listen der Gruppe.
4. **Neue Helper-Funktion `format_segment_reference(segment_ids: list[str]) -> str`** in `official_alerts.py` (nicht `helpers.py`, um Kopplung zum Compare-Pfad zu vermeiden): sortiert numerische IDs, erkennt zusammenhängende Läufe → Range (`"3–5"`), sonst Aufzählung (`"3, 5"`), bei >4 betroffenen Segmenten → `"mehrere Etappen"`. `"Ziel"` immer separat als `"🏁 Ziel"` angehängt (nicht in die numerische Range gemischt).
5. **`render_official_alert_notice_plain()`**: Region-Zeile um `" — " + format_segment_reference(...)` erweitern, nur wenn Segment-IDs vorhanden sind (Standalone-Pfad hat immer welche; Compare-Pfad ruft diese Funktion ohnehin nicht auf).
6. **Datenfluss bis zum Versand**: `_send_official_alert_only()` und `check_and_send_alerts()`/`_dispatch_alert_message()` reichen die Tupel-Liste unverändert durch (kein eigenes Wissen über Segmente nötig, nur Pass-Through).

### Dependencies
- Reihenfolge: zuerst `official_alerts.py` (Helper + Renderer + Dedupe-Erweiterung, TDD-fähig isoliert testbar), danach `trip_alert.py` (Coord→Segment-Mapping), zuletzt `notification_service.py` (reiner Pass-Through, geringstes Risiko).
- `AlertStateService`-Dedupe-Key (`official_alert:{region_label}:{hazard}`) bleibt unverändert — segmentunabhängig, keine Migration nötig.

### Open Questions — PO-Klärung 2026-07-09
- **Verdichtung bei >4 Segmenten:** mit Anzahl, aber Begriff **"Segmente"** statt "Etappen" (PO-Begründung: der Bezug ist strukturell immer auf Segmente, nie auf Etappen/Tage — "Etappen" wäre fachlich falsch). Format: `"N Segmente"`, z.B. `"5 Segmente"`.
- **Gemischte Ranges + Ziel:** Beispiel-Format vom PO bestätigt: `"Segment 3–5, 🏁 Ziel"` (Ziel immer als eigenes Element angehängt, nie in die numerische Range gemischt).
