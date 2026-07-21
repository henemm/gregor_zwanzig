---
entity_id: epic_1073_trip_official_alerts
type: feature
created: 2026-07-07
updated: 2026-07-07
status: draft
version: "1.0"
tags: [trip-briefing, alerts, official-alerts, epic-1073, shared-renderer]
workflow: 1087-trip-official-alerts
---

# Amtliche Warnungen in Trip-Briefings (Epic #1073 Slice 3)

## Approval

- [x] Approved (PO, 2026-07-07)

## Purpose

Amtliche Warnungen (Official Alerts — Vigilance, Météo des forêts, Massiv-Sperren aus #1033)
erscheinen heute **nur** im Orts-Vergleich. Dieses Slice macht sie querschnittlich auch in
Trip-Briefing-Mails (E-Mail, alle drei Formate) verfügbar, führt dafür **eine gemeinsame
Warn-Render-Komponente** für Compare UND Trip ein (kein Copy-Paste, Epic #1073 Punkt 6) und
ergänzt einen Trip-Toggle `official_alerts_enabled` (Default `true`, Pointer-Muster, analog
#1040), mit dem ein Nutzer die Warnungen pro Trip strukturell abschalten kann.

## Source

- **File:** `src/output/renderers/alert/official_alerts.py` (neu), `src/app/models.py`,
  `src/services/trip_report_scheduler.py`
- **Identifier:** `render_official_alerts_html()`, `render_official_alerts_plain()`,
  `collect_trip_alert_entries()`, `SegmentWeatherData.official_alerts`, `Trip.official_alerts_enabled`

> **Schicht-Hinweis:** Betroffen sind alle drei Schichten — Python-Core (`src/app/`,
> `src/services/`, `src/output/renderers/`), Go-API (`internal/model/trip.go`,
> `internal/handler/trip.go`) und Frontend (`frontend/src/lib/...`). Verifiziert per Grep auf
> `official_alerts`/`OfficialAlert` in allen drei Bäumen vor Implementierungsbeginn.

## Estimated Scope

- **LoC:** ~150–170 src (unter dem 250-Limit); Tests separat, könnten das Gesamtdelta an die
  Grenze bringen (siehe Known Limitations zu Split-Option)
- **Files:** 14 (1 CREATE, 13 MODIFY), 3 Sprachen (Python, Go, Svelte)
- **Effort:** high (Mail-Renderer-Gate #811, Multi-Format-Parität, Cross-Domain-Refactoring
  Compare↔Trip)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/official_alerts/base.py::get_official_alerts_for_location()` (#1033/#1034) | Upstream, unverändert | Reine Fkt Koordinaten→Warnliste, fail-soft pro Quelle, wirft nie; Registry deckt automatisch auch kommende AT/IT-Quellen (#1085/#1086) ab |
| `src/services/official_alerts/models.py::OfficialAlert` | Upstream, unverändert | Frozen DTO: `source, hazard, level, label, valid_from, valid_to, url, region_label` |
| `src/app/user.py::LocationResult.official_alerts` (#1034) | Muster-Referenz | Compare-seitiges Vorbild-Feld, bleibt unverändert bestehen |
| `src/output/renderers/email/compare_html.py::_render_official_alerts_block()` | Wird extrahiert | HTML-Rumpf wird verbatim in die neue Shared-Komponente verschoben, hier bleibt ein Thin-Wrapper |
| `src/output/renderers/comparison.py:418-420` | Muster-Referenz | Plain-Format-Vorlage `⚠️ Amtliche Warnung: {label}` — muss exakt reproduziert werden |
| `internal/model/compare_preset.go::OfficialAlertsEnabled *bool` (#1040) | Muster-Referenz | Pointer-Bool-Toggle-Pattern für `internal/model/trip.go` |
| `internal/handler/compare_preset.go` Merge-Block (#1040) | Muster-Referenz | `if req.X != nil`-Merge-Pattern für `internal/handler/trip.go::UpdateTripHandler` |
| `src/services/comparison_engine.py:187-200` | Muster-Referenz | Fetch-Gating-Pattern (`if enabled: fetch else []`) für Scheduler-Fetch |
| `frontend/src/lib/components/trip-wizard/steps/ChannelToggle.svelte` | Wiederverwendung | Bestehende Toggle-UI-Komponente, direkter Import in `AlertsTab.svelte` |
| `tests/tdd/test_issue_1040_alerts_toggle.py` | Test-Vorbild | Mock-freies Fake-Quelle-Pattern (`register_official_alert_source`, Call-Counter) |

## Implementation Details

**(1) Shared Renderer — neues Modul, gate-relevant:**

```python
# src/output/renderers/alert/official_alerts.py (NEU)
def render_official_alerts_html(entries: list[tuple[str, list[OfficialAlert]]]) -> str:
    """Verbatim-Move des Rumpfs aus compare_html.py:151-169 (Level->Farbe
    identisch: 1-2 G_SUCCESS, 3 G_WARNING, 4+ G_DANGER). entries = Liste aus
    (label, alerts) statt (LocationResult) -> generischer Eingang, den sowohl
    Compare (ein Eintrag je Ort) als auch Trip (ein Eintrag je region_label)
    fuellen koennen."""

def render_official_alerts_plain(entries: list[tuple[str, list[OfficialAlert]]]) -> list[str]:
    """Reproduziert comparison.py:418-420 Format exakt: eine Zeile je Alert,
    "Amtliche Warnung: {label}" (Compare haengt Ortsnamen selbst davor)."""

def collect_trip_alert_entries(
    segments: list["SegmentWeatherData"],
) -> list[tuple[str, list[OfficialAlert]]]:
    """Dedupe-Helper NUR fuer den Trip-Pfad: gruppiert alle
    seg.official_alerts nach OfficialAlert.region_label, liefert EIN
    (region_label, alerts)-Paar je eindeutigem Label -> EIN Block pro
    Briefing statt Wiederholung pro Etappe."""
```

**(2) Compare umstellen (Thin-Wrapper, Byte-Gleichheit):**

```python
# src/output/renderers/email/compare_html.py
def _render_official_alerts_block(locations: list[LocationResult]) -> str:
    entries = [(loc.location.name, loc.official_alerts) for loc in locations]
    return render_official_alerts_html(entries)
```

```python
# src/output/renderers/comparison.py:418-420 -> Shared-Call
for alert in loc_result.official_alerts:
    lines.append(f"   ⚠️ Amtliche Warnung: {alert.label}")
# wird zu:
for line in render_official_alerts_plain([(loc_result.location.name, loc_result.official_alerts)]):
    lines.append(f"   ⚠️ {line}")
```

**(3) Datenfeld heben — additiv, nicht-frozen:**

```python
# src/app/models.py:386 SegmentWeatherData
official_alerts: list["OfficialAlert"] = field(default_factory=list)
```

**(4) Trip-Fetch — Scheduler, nach `_fetch_weather` (:608), Toggle-Gate:**

```python
# src/services/trip_report_scheduler.py, nach segment_weather = self._fetch_weather(segments)
if trip.official_alerts_enabled is not False:  # strukturell kein Fetch bei explizit False
    seen: set[tuple[float, float]] = set()
    for sw in segment_weather:
        if sw.has_error:
            continue
        coord = (round(sw.segment.start_point.lat, 3), round(sw.segment.start_point.lon, 3))
        if coord in seen:
            continue
        seen.add(coord)
        try:
            from services.official_alerts import get_official_alerts_for_location
            sw.official_alerts = get_official_alerts_for_location(*coord)
        except Exception:
            logger.warning("trip_report_scheduler: official_alerts nicht ladbar", exc_info=True)
            sw.official_alerts = []
```

**(5) Trip-Renderer binden Shared-Komponente ein:**

```python
# src/output/renderers/email/html.py — Body-Assemblierung :1489-1508
entries = collect_trip_alert_entries(segments)
official_alerts_html = render_official_alerts_html(entries) if entries else ""
# Platzhalter zwischen {changes_html} und {segments_html}
```

```python
# src/output/renderers/email/plain.py — analog, render_official_alerts_plain(entries)
# src/output/renderers/email/compact.py — kurze Textzeile je Eintrag (Sicherheitsrelevanz)
```

**(6) Toggle Full-Stack (Pointer-Muster #1040):**

```go
// internal/model/trip.go, nach :105
OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
```

```go
// internal/handler/trip.go::tripUpdateRequest + UpdateTripHandler-Merge
OfficialAlertsEnabled *bool `json:"official_alerts_enabled,omitempty"`
// ...
if req.OfficialAlertsEnabled != nil {
    existing.OfficialAlertsEnabled = req.OfficialAlertsEnabled
}
```

```python
# src/app/trip.py Trip-Dataclass
official_alerts_enabled: Optional[bool] = None

# src/app/loader.py — load: data.get("official_alerts_enabled")
# save: nur schreiben wenn "is not None" (False muss persistieren, nicht wie 0 wegfallen)
```

```typescript
// frontend/src/lib/types.ts Trip-Interface
official_alerts_enabled?: boolean;
```

```svelte
<!-- frontend/src/lib/components/alerts-tab/AlertsTab.svelte -->
<!-- WICHTIG: AlertsTab nutzt Auto-Save ueber saveController.schedule(buildSaveFn()),
     NICHT den expliziten Save-Button-Pfad aus Step5Versand.svelte. Die ChannelToggle-
     Komponente (UI) wird 1:1 uebernommen, der Save-Mechanismus folgt aber dem
     bestehenden AlertsTab-Pattern (siehe saveController-Referenz-Datei
     reference_savecontroller_always_set.md). -->
<ChannelToggle
  label="Amtliche Warnungen"
  checked={officialAlertsEnabled}
  onchange={(checked) => { officialAlertsEnabled = checked; saveController?.schedule(buildToggleSaveFn()); }}
  testid="alerts-tab-official-alerts-toggle"
/>
```

## Expected Behavior

- **Input:** Trip mit mindestens einer Etappe, deren Start-Koordinate in einer Region mit aktiver
  amtlicher Warnung liegt (FR: Vigilance/Waldbrand/Massiv-Sperre aus #1033); `Trip.official_alerts_enabled`
  (Bool oder fehlend/`null`).
- **Output:** Ist der Toggle `true` oder fehlt er (Default), enthält die generierte Briefing-Mail
  (full HTML, full Plain, compact) einen gruppierten, deduplizierten Warn-Block (ein Eintrag je
  `region_label`) mit denselben Badges/Zeilen wie im Orts-Vergleich. Ist der Toggle explizit
  `false`, findet **kein Fetch** statt (Call-Counter der Quelle = 0) und kein Warn-Block erscheint.
  Die SMS-Trip-Mail (`sms_trip.py`) bleibt bewusst ohne Warn-Block (160-Zeichen-Limit).
- **Side effects:** Bei `false` entfällt der zusätzliche HTTP-Call an die registrierten
  Official-Alert-Quellen für diesen Trip-Versand; bei Quellenausfall (Exception) wird das
  Briefing dennoch vollständig generiert (fail-soft, kein Crash).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit einer Etappe, deren Startpunkt in Frankreich liegt und für die eine
  aktive #1033-Warnung existiert (Vigilance, Météo des forêts oder Massiv-Sperre) und
  `official_alerts_enabled` nicht auf `false` gesetzt ist, When der Scheduler ein Briefing für
  diesen Trip generiert und über den echten Mail-Pfad an `gregor-test@henemm.com` versendet, Then
  enthält die tatsächlich zugestellte, per IMAP abgerufene Mail die Warnung (Label sichtbar im
  Mail-Body).
  - Test: Echter Scheduler-Lauf (`TripReportScheduler`) gegen einen Trip mit realer FR-Koordinate,
    echter Aufruf der registrierten #1033-Quellen (kein Mock), Versand über Stalwart an
    `gregor-test@henemm.com`, IMAP-Abruf + Prüfung des sichtbaren Warnung-Labels im Mail-Body
    (kein `assert 'x' in file.read_text()` — echte zugestellte Mail).

- **AC-2:** Given der Orts-Vergleich UND das Trip-Briefing rendern beide amtliche Warnungen, When
  beide Render-Pfade ausgeführt werden, Then rufen beide **nachweislich denselben** Funktions-Code
  in `src/output/renderers/alert/official_alerts.py` auf (kein zweiter, eigenständiger
  Warn-Render-Code), und die Compare-Badge-Ausgabe (`render_compare_html()`) ist byte-identisch
  zum Zustand vor der Extraktion (Regression-Schutz).
  - Test: Golden-Test — `render_compare_html()` vor und nach der Extraktion mit identischem
    `ComparisonResult`-Input auf String-Gleichheit prüfen (Byte-Diff = leer). Zusätzlich ein
    Coverage-/Introspektions-Test, der beweist, dass sowohl `compare_html.py` als auch
    `html.py`/`plain.py`/`compact.py` (Trip) `render_official_alerts_html`/`_plain` aus demselben
    Modul importieren (kein Duplikat-Fund per Grep auf `for alert in .*official_alerts` außerhalb
    des Shared-Moduls).

- **AC-3:** Given ein Trip von Nutzer A mit `official_alerts_enabled=false` und eine registrierte
  Test-Fake-Quelle mit Aufruf-Zähler, die bei Aufruf einen Treffer für die Trip-Koordinate liefern
  würde, When der Scheduler ein Briefing für diesen Trip generiert, Then wird die Fake-Quelle
  nachweislich **nicht** aufgerufen (Call-Counter = 0) und kein Warn-Block erscheint im Briefing.
  Wird derselbe Trip anschließend per `PUT /api/trips/{id}` gespeichert — mit einem geänderten,
  aber `official_alerts_enabled` **nicht** enthaltenden Request-Body (z.B. nur `name` geändert) —
  bleibt der zuvor gesetzte Wert `false` erhalten (Merge, kein Zurückfallen auf Default) UND alle
  anderen unveränderten Trip-Felder (z.B. `stages`, `alert_rules`) sind byte-identisch zum Zustand
  vor dem Save (Read-Modify-Write, kein Datenverlust — BUG-DATALOSS-GR221). Der identische
  Testablauf wird zusätzlich für einen unabhängigen Trip von Nutzer B wiederholt, um
  Cross-User-Datenlecks im Handler auszuschließen.
  - Test: Test-Fake-Quelle mit Call-Counter über `register_official_alert_source()` registrieren,
    echten Scheduler-Lauf mit `official_alerts_enabled=False` durchführen, Call-Counter=0 und
    Abwesenheit der Warnung im Briefing prüfen. Danach echter `PUT /api/trips/{id}`-Call (Go-Handler)
    mit Body ohne das Feld, gespeicherten Trip laden, `OfficialAlertsEnabled` weiterhin `false` und
    übrige Felder unverändert prüfen. Gesamter Ablauf für zwei getrennte `user_id`-Verzeichnisse
    wiederholt (Pattern: `tests/tdd/test_issue_1040_alerts_toggle.py`-Fake-Quelle +
    Zwei-Nutzer-Isolation).

- **AC-4:** Given eine der registrierten #1033-Quellen wirft beim Fetch eine Exception (simulierter
  Quellenausfall über eine echte, strukturell fehlerhafte Test-Quelle — kein Mock), When der
  Scheduler ein Briefing für einen betroffenen Trip generiert, Then wird das Briefing dennoch
  vollständig generiert und versendet (kein Crash, kein `no_weather`-Abbruch allein wegen des
  Alert-Fetches), lediglich ohne Warn-Block für die betroffene Koordinate.
  - Test: Echte Test-Quelle registrieren, deren `fetch()` eine `RuntimeError` wirft; Scheduler-Lauf
    beobachten, Outcome-Status prüfen (`sent`, nicht `no_weather`/Exception-Propagation), Mail-Inhalt
    auf Vollständigkeit der übrigen Sektionen (Wetter-Tabellen etc.) prüfen.

- **AC-5:** Given ein Trip-Briefing im `email_format=compact`, When eine aktive Warnung für eine
  Etappe existiert, Then enthält der `render_compact()`-Text eine kurze, für die Warnung
  spezifische Textzeile (nicht nur in `full`).
  - Test: Echter Scheduler-Lauf mit `report_config.email_format="compact"` und aktiver Test-Quelle,
    IMAP-Abruf der zugestellten Mail, Prüfung, dass das Warnungs-Label im kompakten Textkörper
    sichtbar ist.

- **AC-6:** Given ein Trip-Briefing, das per SMS versendet wird (`sms_trip.py`), When eine aktive
  Warnung existiert, Then enthält die SMS **keinen** Warn-Block (dokumentierte, bewusste
  Nicht-Parität wegen 160-Zeichen-Limit) — kein Absturz, keine Kürzung des restlichen Inhalts durch
  Alert-Text.
  - Test: Echter SMS-Renderer-Aufruf mit `segments`, die `official_alerts` enthalten; Prüfung, dass
    die erzeugte SMS-Zeichenkette unverändert zum Zustand ohne Alerts bleibt (kein Alert-Fragment
    im Text) und das 160-Zeichen-Limit weiterhin eingehalten wird.

## Known Limitations

- **LoC-Grenze:** Tests (insbesondere AC-1/AC-3 mit echten Scheduler-Läufen + IMAP-Roundtrips) sind
  umfangreich; falls das Gesamtdelta die 250-LoC-Grenze überschreitet, ist ein Split in Slice 3a
  (Shared Renderer + Compare-Migration + Datenfeld + Fetch, AC-1/AC-2/AC-4/AC-5/AC-6) und Slice 3b
  (Toggle Full-Stack, AC-3) zu erwägen — Entscheidung erst nach TDD-RED-Umfang treffen, nicht
  vorab.
- **Legacy-Pfade unverändert:** `CompareSubscription` (#456) und die Ad-hoc-Compare-API
  (`api/routers/compare.py`) sind bereits laut #1040 Out-of-Scope und bleiben es auch hier —
  keine Berührung durch dieses Slice.
- **Ein Block je Briefing:** Bei mehreren Etappen mit derselben `region_label` erscheint die
  Warnung genau einmal (Dedupe über `region_label`), nicht pro Etappe wiederholt. Unterschiedliche
  `region_label`-Werte für verschiedene Etappen erzeugen mehrere Blöcke.
- **SMS bewusst ohne Parität:** Dokumentierte Entscheidung (d) aus der Analyse — keine
  Nachbesserung in diesem Slice.

## Out of Scope

- **AT/IT-Quellen (#1085/#1086):** Werden automatisch mit-verfügbar, sobald sie in der Registry
  registriert sind — keine expliziten Tests für diese Quellen in diesem Slice.
- **Granularität pro Alert-Quelle:** Der Toggle schaltet ALLE Official-Alert-Quellen gemeinsam
  ein/aus, keine Auswahl einzelner Quellen.
- **`CompareSubscription`-Legacy-Pfad (#456) und Ad-hoc-Compare-API:** Analog #1040 unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Folgt vollständig etablierten, bereits per ADR-0016 (#1034) legitimierten Mustern
  (Pointer-Bool-Toggle, Fetch-Gating, Read-Modify-Write-Merge) sowie der expliziten
  Architektur-Leitplanke aus Epic #1073 Punkt 6 (ein gemeinsamer Renderer statt Kopie, bereits in
  `7f99801d docs(#1073): Architektur-Leitplanke Slice 3` dokumentiert) — keine neue
  Architekturentscheidung nötig, sondern deren direkte Umsetzung.

## Changelog

- 2026-07-07: Initial spec created (Epic #1073 Slice 3, Issue #1087).
