---
entity_id: fix_1648_radar_dpc_entfernen
type: bugfix
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [providers, radar, nowcast, italy, issue-1648, cleanup, egress]
---

# Radar-DPC (Protezione Civile) als NowCast-Quelle ersatzlos entfernen (Issue #1648)

## Approval

- [ ] Approved

## Purpose

`src/providers/radar_dpc.py` liefert für den italienischen Radar-NowCast-Zweig **immer genau
ein** Bild (eine SRI-Momentaufnahme, keine Zeitreihe). Weil die Fenster-Prüfung in
`_derive_result` nur Frames mit `timestamp >= now` zählt, wird dieses eine — stets in der
Vergangenheit liegende — Bild **strukturell immer verworfen**: der Italien-Zweig liefert dadurch
faktisch nie einen Alarm, obwohl direkt darunter mit ARPAE ICON-2I (Open-Meteo, seit #1186) eine
echte Vorhersage-Quelle bereitsteht, die wegen der `if frames: return ...`-Bedingung nie erreicht
wird (DPC liefert ja immer `frames`). Diese Spec entfernt Radar-DPC als NowCast-Quelle **ersatzlos**
(PO-Entscheid, mehrfach bekräftigt, zuletzt 2026-08-10) und lässt den Italien-Zweig direkt auf
ARPAE ICON-2I laufen — eine Quelle, die die Frage "was kommt in den nächsten Stunden" tatsächlich
beantworten kann.

**Nicht Gegenstand:** die amtlichen italienischen Warnungen (`DpcSource`,
`src/services/official_alerts/dpc.py`) — andere Datenquelle, anderer Host, bleibt unverändert
funktionsfähig (s. AC-3, „Nicht in dieser Scheibe").

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `RadarNowcastService._fetch_frames_with_fallback` (Italien-Zweig),
  `RadarNowcastService._fetch_radar_dpc` (entfällt), `_within_dpc`/`_DPC_LAT_MIN` u.a.
  (werden umbenannt, s. Implementation Details)
- **Nebendateien:** `src/providers/radar_dpc.py` (Datei entfällt komplett), `src/providers/base.py`
  (Registrierung entfällt), `src/app/egress_guard.py` + `internal/egress/inventory.go`
  (Egress-Allowlist-Eintrag entfällt), `src/services/official_alerts/dpc.py` (übernimmt
  umbenannte Bbox-Konstanten aus `radar_service.py`, s. u.)
- **Schicht:** ausschließlich Python-Core (`src/providers/`, `src/services/`) + ein
  Egress-Allowlist-Eintrag im Go-Dienst (`internal/egress/inventory.go`). Kein Frontend, kein
  Go-Domänencode.

> **Wichtiger Fund während der Recherche (nicht im ursprünglichen Auftrag genannt):**
> `src/services/official_alerts/dpc.py:37-39` importiert `_DPC_LAT_MIN`/`_DPC_LAT_MAX`/
> `_DPC_LON_MIN`/`_DPC_LON_MAX` **aus `radar_service.py`** und nutzt sie in `DpcSource.covers()`
> (Zeile 231) als groben Italien-Bbox-Vorfilter für die amtlichen Warnungen. Eine Umbenennung
> dieser Konstanten in `radar_service.py` **muss** den Import in `official_alerts/dpc.py`
> mitziehen — sonst bricht `ImportError` den amtlichen Warnpfad, den diese Spec ausdrücklich
> unberührt lassen soll.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService._fetch_italy_arpae` (#1186, live) | internal, bereits produktiv | wird zur alleinigen Italien-Quelle; keine Änderung an dieser Methode selbst |
| `services.official_alerts.dpc.DpcSource` (#1427) | internal, cross-module | importiert die umzubenennenden Bbox-Konstanten aus `radar_service.py` — Kopplung, keine Duplikation gewünscht |
| `src/app/egress_guard.py::INVENTORY` / `internal/egress/inventory.go::Inventory` | internal, geteiltes Paar | `tests/test_egress_inventory_drift.py` erzwingt Deckungsgleichheit — Entfernung muss in BEIDEN Listen erfolgen |
| `providers.base.register_provider` | internal factory | `register_provider("radar_dpc", RadarDPCProvider)` entfällt; kein anderer Aufrufer nutzt `get_provider("radar_dpc")` (geprüft, keine Treffer) |
| `pyproject.toml` (`rasterio`, `tenacity`) | external libs | **bleiben** — beide werden von anderen Providern weiterverwendet (`rasterio` von `providers/dwd.py` für GRIB2-Punktextraktion, `tenacity` von `providers/geosphere.py`) — keine Dependency-Entfernung in dieser Scheibe |
| ADR-0029 (Open-Meteo Standard-Provider) | decision | Satz „`radar_dpc` dem Nowcast Italien" wird faktisch falsch und muss korrigiert werden (kein neues ADR, s. „Architektur-Entscheidung" unten) |

## Estimated Scope

- **Produktivcode:** 6 Dateien geändert (`radar_service.py`, `base.py`, `egress_guard.py`,
  `inventory.go`, `official_alerts/dpc.py`) + 1 Datei komplett gelöscht (`radar_dpc.py`,
  149 Zeilen). Netto ca. **-185 bis -210 Zeilen** Produktivcode.
- **Tests:** 1 Datei komplett gelöscht (`test_issue_1162_radar_dpc.py`, 248 Zeilen), 4 Dateien
  angepasst (`test_feature_1186_arpae_it_fallback.py`, `test_radar_offline_fixture_mode.py`,
  `test_feature_734_arome_france_nowcast.py`, `test_isolation_warn_services.py`), 1 Datei
  optional (Docstring-Referenz in `test_radar_nowcast_cache_sharing.py`). Netto ca.
  **-380 bis -450 Zeilen**.
- **Docs (zählen laut CLAUDE.md nicht gegen das LoC-Limit):** `decision_matrix.md`,
  `api_contract.md`, `docs/adr/0029-openmeteo-standard-provider.md`,
  `docs/specs/_archive/modules/issue_1162_radar_dpc.md`,
  `docs/specs/modules/radar_nowcast_italy_arpae_fallback.md`,
  `docs/specs/modules/radar_nowcast.md` (Changelog).
- **🔴 LoC-Warnung:** Zwei Volllöschungen (149 + 248 Zeilen) allein ergeben bereits ~400 Zeilen.
  In Summe (Produktivcode + Tests, git-diff-Stil addiert+entfernt) liegt der Workflow bei grob
  **700-850 berührten Zeilen** — deutlich über dem 250-Zeilen-Default. Vor der Implementierung
  voraussichtlich nötig: `python3 .claude/hooks/workflow.py set-field loc_limit_override 900`
  (oder Aufteilung in Teil-Commits, falls das Gate das zulässt). Bitte vor `/40-tdd-red` klären.
- **Effort:** medium — kein neuer Code, überwiegend Löschung/Vereinfachung, aber viele
  Fundstellen über Produktiv-, Test- und Doku-Ebene verteilt.

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/providers/radar_dpc.py` | DELETE | kompletter Provider (149 Zeilen) |
| `src/services/radar_service.py` | MODIFY | Italien-Zweig vereinfacht, `_fetch_radar_dpc` entfernt, Bbox-Konstanten/`_within_dpc`/Region-Bucket umbenannt, `"DPC"`-Label entfernt, Docstrings korrigiert |
| `src/providers/base.py` | MODIFY | Registrierungsblock `register_provider("radar_dpc", ...)` entfernt |
| `src/app/egress_guard.py` | MODIFY | Eintrag `radar-api.protezionecivile.it` entfernt |
| `internal/egress/inventory.go` | MODIFY | Eintrag `radar-api.protezionecivile.it` entfernt (Zwillingsliste) |
| `src/services/official_alerts/dpc.py` | MODIFY | Import der umbenannten Bbox-Konstanten nachgezogen — sonst `ImportError` im amtlichen Warnpfad |
| `tests/tdd/test_issue_1162_radar_dpc.py` | DELETE | komplette Testdatei (248 Zeilen), alle ACs betrafen nur den entfernten Provider |
| `tests/tdd/test_feature_1186_arpae_it_fallback.py` | MODIFY (ggf. Rename) | DPC-Fallback-Prämisse entfällt, ARPAE ist jetzt direkte Quelle statt Rückfall |
| `tests/unit/test_radar_offline_fixture_mode.py` | MODIFY | DPC-Tripwire/Parametrize-Fall entfernt |
| `tests/tdd/test_feature_734_arome_france_nowcast.py` | MODIFY | Korsika-Erwartung `"DPC"` → `"ARPAE-2I"` |
| `tests/tdd/test_isolation_warn_services.py` | MODIFY | Host aus `WEATHER_RADAR_HOSTS` entfernt |
| `tests/unit/test_radar_nowcast_cache_sharing.py` | MODIFY (optional) | veraltete Docstring-Referenz auf gelöschte Testdatei |
| `docs/reference/decision_matrix.md` | MODIFY | Zeile 29 (`radar_dpc`-Provider-Eintrag) entfernen/korrigieren |
| `docs/reference/api_contract.md` | MODIFY | `radar_dpc` aus der Provider-Ist-Stand-Aufzählung entfernen |
| `docs/adr/0029-openmeteo-standard-provider.md` | MODIFY | Satz zu `radar_dpc` faktisch korrigieren (kein Statuswechsel) |
| `docs/specs/_archive/modules/issue_1162_radar_dpc.md` | MODIFY | Superseded-Vermerk (Verweis auf diese Spec) |
| `docs/specs/modules/radar_nowcast_italy_arpae_fallback.md` | MODIFY | Superseded-Vermerk — Architektur „ARPAE unter DPC" existiert nicht mehr |
| `docs/specs/modules/radar_nowcast.md` | MODIFY | Changelog-Eintrag ergänzt |

## Nicht in dieser Scheibe

- **`src/services/official_alerts/dpc.py` (amtliche Warnungen, `DpcSource`) bleibt inhaltlich
  unverändert.** Einzige Berührung: der Import der umbenannten Bbox-Konstanten (mechanisch, s.
  AC-3). Kein Verhalten, kein Bulletin-Abruf, kein Host ändert sich.
- **`pyproject.toml` bleibt unverändert.** `rasterio` und `tenacity` werden weiterhin von
  `providers/dwd.py` bzw. `providers/geosphere.py` gebraucht — keine verwaiste Dependency.
- **Kein neuer Fallback-/Retry-Mechanismus für ARPAE.** `_fetch_italy_arpae` bleibt exakt wie in
  #1186 implementiert (fail-soft über den gemeinsamen `_fetch_openmeteo_15`-Funnel).
- **Issue #1174** ("Radar-DPC: natives Gewitter/Hagel-Signal für Italien") wird durch diese
  Änderung **gegenstandslos** (die Quelle, für die ein natives Signal entwickelt werden sollte,
  existiert nicht mehr). Diese Spec dokumentiert das nur als Feststellung — Schließen/Verlinken
  von #1174 ist Sache des Orchestrators, nicht Teil des Codescopes hier.
- **`docs/features/epic-1073-alerts-at-it.md` wird NICHT zwingend editiert.** Es ist ein
  historischer Entscheidungs-Log (Changelog-Charakter); die dort dokumentierten
  PO-Entscheidungen vom 2026-07-09 bleiben als Historie gültig, auch wenn der Code sich seither
  weiterentwickelt hat. Optionale Ergänzung möglich, kein Blocker.
- **Keine Änderung an den vier Alarm-Konsumenten** (`trip_alert.py`, `compare_radar_alert.py`,
  `trip_command_processor.py`, `trip_report_scheduler.py`). Sie konsumieren die Quellenkette
  ausschließlich über `RadarNowcastService.get_nowcast()`/`format_now_text()` — kein
  DPC-spezifischer Code dort (geprüft, keine Treffer). Ihr Verhalten verbessert sich automatisch
  durch die Kettenänderung, ohne dass eine Zeile in diesen Dateien geändert werden muss.
- **Keine Umbenennung von `_region_bucket`s anderen Werten** (`"radolan"`, `"inca"`,
  `"arome_france"`, `"icon_d2"`, `"global"`) — nur der DPC-spezifische Wert `"dpc"` ändert sich.

## Implementation Details

### 1. `src/providers/radar_dpc.py` — Datei löschen

Komplett entfernen (149 Zeilen: `RadarDPCProvider`, `_is_retryable_error`, alle Konstanten).

### 2. `src/services/radar_service.py`

- **Modul-Docstring** (Zeilen 7-12): Zeile 10 „Radar-DPC (Protezione Civile) for Italy (incl.
  Corsica coverage)" → „ARPAE ICON-2I (via Open-Meteo) for Italy (incl. Corsica coverage)".
- **Bbox-Konstanten** (Zeilen 47-51, gemessen — deckt sich mit Auftrag): `_DPC_LAT_MIN/_MAX`,
  `_DPC_LON_MIN/_MAX` → `_ITALY_RADAR_LAT_MIN/_MAX`, `_ITALY_RADAR_LON_MIN/_MAX`. Werte
  unverändert (36.0-47.5 / 6.5-19.0). Namensbegründung: die Box beschreibt eine geografische
  Zuständigkeit ("Italien-Radar-Gebiet"), nicht mehr einen bestimmten Anbieter — genau die
  Verwechslung (Konstantenname = Anbietername, der austauschbar ist) hat diesen Bug erst
  ermöglicht.
- **`_within_dpc`** (Zeilen 618-622, gemessen) → `_within_italy_radar`. Logik unverändert.
- **`_region_bucket`** (Zeilen 662-663, gemessen): Aufruf auf `_within_italy_radar` umstellen,
  Rückgabewert `"dpc"` → `"italy_radar"`. Geprüft: dieser String wird NICHT persistiert, nicht
  geloggt, nicht von Frontend/Tests auf den Literalwert `"dpc"` geprüft (nur als interner
  Cache-Schlüsselbestandteil in `radar_cache.py` verwendet, TTL 300s, rein prozessintern) —
  Umbenennung ist ein reines Implementierungsdetail, kein Datenformat-Bruch.
- **`_SOURCE_LABELS`** (Zeile 218, gemessen): Eintrag `"DPC": "Radar-DPC (Protezione Civile IT)"`
  entfernen.
- **Italien-Zweig in `_fetch_frames_with_fallback`** (Zeilen 312-318, gemessen — exakt wie im
  Auftrag angegeben):

  ```python
  if _within_italy_radar(lat, lon):
      frames = self._fetch_italy_arpae(lat, lon)
      if frames:
          return frames, "ARPAE-2I"
  ```

  (ersetzt den DPC-Versuch samt `if frames: return frames, "DPC"`-Zweig davor).
- **`_fetch_radar_dpc`** (Zeilen 387-408, gemessen — Auftrag nannte 387-407, Methode ist 22
  Zeilen inkl. Docstring) komplett entfernen.
- **Sidecar-Funnel-Docstring** (Zeile 432, gemessen — Auftrag nannte 431-432): „beide
  Sidecar-Aufrufe aus `_fetch_geosphere_inca`/`_fetch_radar_dpc`" → „der INCA-Sidecar-Aufruf aus
  `_fetch_geosphere_inca`" (nur noch ein Sidecar-Aufrufer, nicht mehr zwei).

### 3. `src/providers/base.py`

`_load_providers()`, Zeilen 286-290 (gemessen, exakt wie Auftrag): den
`try: from providers.radar_dpc import RadarDPCProvider; register_provider("radar_dpc", ...)`
-Block entfernen.

### 4. Egress-Allowlist (zwei Dateien, müssen synchron bleiben)

- `src/app/egress_guard.py:42` (gemessen): Zeile `"radar-api.protezionecivile.it":
  IsolationKind.TEST_ACCESS,` entfernen.
- `internal/egress/inventory.go:33` (gemessen): Zeile `"radar-api.protezionecivile.it":
  TestAccess,` entfernen.
- `tests/test_egress_inventory_drift.py` prüft beide Listen auf Deckungsgleichheit — bleibt nach
  beiden Löschungen automatisch grün, KEINE Änderung an diesem Test nötig.
- Der amtliche DPC-Warn-Host ist ein **anderer** Host
  (`raw.githubusercontent.com/pcm-dpc/...`, `DPC_ZIP_URL` in `official_alerts/dpc.py:43-45`) und
  taucht in keiner der beiden Egress-Listen unter dem Namen „protezionecivile" auf — nichts zu
  tun, nur zur Klarheit dokumentiert (die Aufgabenstellung verlangte diese Prüfung explizit).

### 5. `src/services/official_alerts/dpc.py`

Zeilen 37-39 (Import) und 231 (Nutzung) von `_DPC_LAT_MIN/_MAX/_DPC_LON_MIN/_MAX` auf
`_ITALY_RADAR_LAT_MIN/_MAX/_ITALY_RADAR_LON_MIN/_MAX` umstellen. Reine Umbenennung, `covers()`
liefert für dieselben Koordinaten dasselbe Ergebnis wie vorher (s. AC-3).

## Expected Behavior

- **Input:** unverändert — Koordinaten (`lat`, `lon`) an `RadarNowcastService.get_nowcast()`.
- **Output:** für Koordinaten im bisherigen DPC-Gebiet liefert die Kette jetzt `source ==
  "ARPAE-2I"` statt `"DPC"` (oder fällt bei ARPAE-Ausfall fail-soft weiter auf AROME-FR/ICON-D2/
  `minutely_15`, unverändert zu #1186). Frames liegen dadurch strukturell in der Zukunft
  (Open-Meteo `minutely_15`-Vorhersage, ~5-6h Horizont) statt einer einzelnen
  Vergangenheits-Beobachtung — ein Radar-Alarm kann in diesem Gebiet jetzt überhaupt auslösen.
- **Side effects:** ein Sidecar-HTTP-Aufruf pro betroffener Anfrage entfällt (DPC-eigener
  GeoTIFF-Download-Flow, 3 Requests: `findLastProductByType` → `downloadProduct` → S3-GeoTIFF) —
  weniger Netzlast, kein zusätzlicher Open-Meteo-Kontingentverbrauch (ARPAE lief bereits vorher
  über denselben `_fetch_openmeteo_15`-Funnel wie alle anderen Modell-Zweige).

## Test Plan

Test-Politik dieses Hauses (zwei Schichten): Kern deterministisch und netzfrei, Live-Schicht
(Marker `live`) mit echten HTTP-Calls. Pfadregel: Tests lösen den Prüfling relativ zur eigenen
Testdatei auf (`Path(__file__).resolve().parents[2]`), nie über einen festen
Hauptrepo-Pfad. Namensregel: neue/umbenannte Testdateien nach Verhalten benennen, nicht nach
Issue-Nummer.

### Kern-Schicht (deterministisch, kein `live`-Marker)

- [ ] **AC-3 (Regression):** `DpcSource.covers()` liefert für eine feste Auswahl Koordinaten
  (innerhalb/außerhalb der Box, inkl. Grenzwerte) exakt dieselben Wahrheitswerte wie vor der
  Umbenennung — Pure-Function-Test, kein Netz. GIVEN eine Koordinate knapp innerhalb/außerhalb
  der bisherigen `_DPC_LAT_MIN/MAX`-Grenzen, WHEN `DpcSource().covers(lat, lon)` aufgerufen wird,
  THEN bleibt das Ergebnis identisch zum dokumentierten Vorher-Wert.
- [ ] **AC-5 (Code-Abwesenheit, Verhaltenstest statt Dateiinhalt-Check):** GIVEN der gemergte
  Stand, WHEN `import providers.radar_dpc` versucht wird, THEN wirft es `ModuleNotFoundError` —
  UND `"radar_dpc" not in providers.base.available_providers()`.
- [ ] **`_within_italy_radar`-Bbox (Pure-Function, Muster `test_ac2_within_arome_france_bbox`):**
  GIVEN die bekannten Eckkoordinaten (Vizzavona 42.1244/9.1339 innerhalb, KHW-Punkt 46.20/12.85
  innerhalb, Marseille 43.2965/5.3698 außerhalb — lon < 6.5), WHEN `_within_italy_radar`
  aufgerufen wird, THEN stimmen die Wahrheitswerte mit den vorherigen `_within_dpc`-Werten
  überein.
- [ ] **`tests/unit/test_radar_offline_fixture_mode.py` (angepasst):** `RadarDPCProvider`-
  Tripwire, `_DPC_ONLY_LAT/_LON`-Fall aus dem AC-11-Parametrize sowie `"DPC"` aus der
  `result.source not in (...)`-Assertion entfernen. Bestehende Offline-Fixture-Garantie
  (`GZ_TEST_FIXTURE_DIR` gesetzt → kein echter Netzaufruf) bleibt für RADOLAN/INCA unverändert
  bestehen; der Italien-Zweig läuft ohnehin über den bereits fixture-gestützten
  `_fetch_openmeteo_15`-Funnel und brauchte nie eine eigene Tripwire-Provider-Klasse.
- [ ] **`tests/unit/test_radar_nowcast_cache_sharing.py`:** bleibt funktional unverändert grün
  (Region-Bucket-Rename ist intern); Docstring-Zeile 345 (Referenz auf die gelöschte
  `test_issue_1162_radar_dpc.py`) optional auf verbleibende Pattern-Datei
  (`test_issue_1161_inca_convective.py`) kürzen.
- [ ] **`tests/tdd/test_isolation_warn_services.py` (angepasst):** `"radar-api.protezionecivile.it"`
  aus `WEATHER_RADAR_HOSTS` (Zeilen 65-69) entfernen — sonst `KeyError` beim
  `INVENTORY[host]`-Zugriff, da der Host nicht mehr in `INVENTORY` steht.

### Live-Schicht (Marker `live`, echte HTTP-Calls gegen Open-Meteo)

- [ ] **AC-1 (Wirkung, GR20):** GIVEN die reale Koordinate Vizzavona (42.1244/9.1339, GR20,
  liegt sowohl im bisherigen DPC- als auch im AROME-FR-Gebiet), WHEN `get_nowcast()` ohne DI
  aufgerufen wird, THEN ist `result.source == "ARPAE-2I"`, `len(result.frames) >= 1`, und
  mindestens ein Frame hat `timestamp >= now` (echter Vorhersage-Horizont statt
  Vergangenheits-Beobachtung).
- [ ] **AC-2 (Wirkung, KHW-Fallback):** GIVEN eine Koordinate im INCA/Italien-Überlappungsgebiet
  (z.B. 46.20/12.85), bei der `_fetch_geosphere_inca` künstlich `[]` liefert (Instanzmethoden-
  Ersatz, kein Mock), WHEN `get_nowcast()` aufgerufen wird, THEN fällt die Kette auf
  `source == "ARPAE-2I"` zurück (nicht mehr auf eine einzelne Vergangenheits-Beobachtung) und
  liefert mindestens einen Frame mit `timestamp >= now`.
- [ ] **`tests/tdd/test_feature_1186_arpae_it_fallback.py` (überarbeitet, ggf. umbenannt nach
  Namensregel z.B. `test_radar_nowcast_italy_arpae_only.py` — Datei wird ohnehin komplett
  angefasst):** bisheriges AC-1 (DPC-Ausfall → ARPAE) vereinfacht sich zu „ARPAE wird direkt ohne
  Umweg erreicht" (kein DPC-Stub mehr nötig). Bisheriges AC-2 („DPC behält Vorrang vor ARPAE")
  entfällt ersatzlos — der Fall existiert nicht mehr. Bisheriges AC-3 vereinfacht sich zu „ARPAE
  fällt bei Fehlschlag fail-soft auf `minutely_15` zurück" (nur noch ein Stub statt zwei).
  Bisheriges AC-4 (Label „ARPAE"+„Italien") bleibt unverändert.
- [ ] **`tests/tdd/test_feature_734_arome_france_nowcast.py` (angepasst):**
  `test_ac1_arome_france_real_fetch_returns_arome_source` und
  `test_ac2_chain_routing_berlin_radar_atlantic_global` erwarten für Korsika (42.18/9.0) heute
  `source == "DPC"` — muss auf `source == "ARPAE-2I"` geändert werden (Docstrings entsprechend:
  „DPC-Box" → „Italien-Radar-Box", Begründung „reale Radarbeobachtung" entfällt).
- [ ] **`tests/tdd/test_issue_1162_radar_dpc.py`:** komplett löschen (alle 5 ACs betrafen
  ausschließlich den entfernten DPC-Provider).

## Acceptance Criteria

- **AC-1:** Given die reale GR20-Koordinate Vizzavona (42.1244/9.1339, liegt im bisherigen
  Radar-DPC-Gebiet), When `RadarNowcastService.get_nowcast()` ohne Dependency-Injection
  aufgerufen wird, Then liefert die Kette `source == "ARPAE-2I"` mit mindestens einem Frame,
  dessen `timestamp` in der Zukunft liegt (`>= now`) — ein Radar-Alarm kann an diesem Ort
  strukturell wieder auslösen, statt durch eine reine Vergangenheits-Beobachtung dauerhaft
  blockiert zu sein.
  - Test: `test_ac1_...` (live) in der überarbeiteten `test_feature_1186_...`-Datei, prüft
    `result.source` und `any(f.timestamp >= now for f in result.frames)`.

- **AC-2:** Given eine Koordinate im Überlappungsgebiet von INCA und Italien-Radar-Box (Karnischer
  Höhenweg, 46.20/12.85), bei der GeoSphere INCA künstlich leer liefert (echter Methodenaustausch,
  kein Mock), When `get_nowcast()` aufgerufen wird, Then fällt die Kette auf ARPAE ICON-2I zurück
  (`source == "ARPAE-2I"`, mindestens ein Frame in der Zukunft) statt — wie vor dieser Änderung —
  auf eine einzelne, nutzlose DPC-Vergangenheits-Beobachtung, die faktisch nie einen Alarm
  ermöglicht hätte.
  - Test: neuer Live-Test, `_fetch_geosphere_inca` durch `[]`-liefernde Methode ersetzt, echter
    ARPAE-Call.

- **AC-3:** Given eine italienische Koordinate, When `DpcSource.covers()` bzw. `DpcSource.fetch()`
  (amtliche Warnungen, `src/services/official_alerts/dpc.py`) aufgerufen wird, Then bleibt das
  Verhalten identisch zum Stand vor dieser Änderung — gleiche Bounding-Box-Werte unter
  umbenannten Konstanten, gleicher Bulletin-Host (`raw.githubusercontent.com`), unverändert vom
  Radar-Rückbau.
  - Test: bestehende `tests/tdd/test_dpc_bulletin_source.py`-Suite bleibt grün + neuer
    Pure-Function-Test auf `covers()` mit festen Koordinaten (Kern-Schicht).

- **AC-4:** Given ein Frame mit `timestamp < now`, When `_derive_result()` das Nowcast-Fenster
  filtert, Then bleibt die Bedingung `f.timestamp >= now and f.timestamp <= horizon`
  (`radar_service.py:551-554`) exakt unverändert — sie war nie der Fehler, sondern die Stelle, an
  der sichtbar wurde, dass Radar-DPC den Vertrag der NowCast-Kette ("was kommt in den nächsten
  Stunden") strukturell nicht erfüllen kann.
  - Test: bestehende Abdeckung von `_derive_result` (u.a. in `test_feature_734_...` AC-4) bleibt
    unverändert grün; kein neuer Test nötig, nur Bestandsschutz.

- **AC-5:** Given der gemergte Stand, When im Python-Quellcode (`src/`) nach `radar_dpc`,
  `RadarDPCProvider`, `_fetch_radar_dpc` und dem Quellen-Label `"DPC"` gesucht wird, Then gibt es
  keine Fundstellen mehr außerhalb der amtlichen Warnquelle `DpcSource` (deren interne
  `source="dpc"`-Strings unverändert bleiben, s. AC-3) — kein Import, keine Registrierung, kein
  Renderer/Text nennt „DPC" mehr als Radarquelle.
  - Test: `import providers.radar_dpc` wirft `ModuleNotFoundError`;
    `"radar_dpc" not in providers.base.available_providers()`.

- **AC-6:** Given die beiden Egress-Inventare (`src/app/egress_guard.py::INVENTORY`,
  `internal/egress/inventory.go::Inventory`), When nach dem Host
  `radar-api.protezionecivile.it` gesucht wird, Then ist er aus beiden Listen entfernt,
  `tests/test_egress_inventory_drift.py` bleibt grün, und der amtliche DPC-Warn-Host
  (`raw.githubusercontent.com`) ist von dieser Änderung unberührt.
  - Test: bestehender Drift-Test + angepasster `test_isolation_warn_services.py`
    (`WEATHER_RADAR_HOSTS`-Liste ohne den entfernten Host).

## Known Limitations

- **ARPAE ICON-2I ist Modell-Downscaling, kein reales Radar.** Der fachliche Tausch ist bewusst:
  eine funktionierende Vorhersage schlägt eine nicht funktionsfähige Beobachtung. Sollte künftig
  eine echte italienische Radar-Zeitreihe (mehrere Frames, nicht nur eine Momentaufnahme)
  verfügbar werden, wäre das ein neues, eigenes Issue — keine Wiedereinführung von Radar-DPC in
  der bisherigen Form.
- **Kein natives Gewitter-/Hagel-Signal für Italien mehr in Aussicht** (vormals #1174-Zielbild
  „Radar-DPC natives Signal") — Italien nutzt wie AROME-FR/ICON-D2 weiterhin ausschließlich den
  Open-Meteo-Weathercode-Sidecar (WMO 95/96/99) für `is_convective`.
- **BBox-Grenzen bleiben approximativ** (unverändert aus #1162 übernommen, lat 36.0-47.5 / lon
  6.5-19.0) — keine empirische Neuvermessung ist Teil dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0029 (Open-Meteo als Standard-Wetterdaten-Provider) — **kein neues ADR**.
- **Rationale:** ADR-0029 bleibt in seiner Kernentscheidung ("Open-Meteo ist der
  Standard-Provider, Cross-Provider-Fallback für AT/DE/FR bei Totalausfall") unverändert gültig.
  Diese Scheibe korrigiert lediglich einen mittlerweile faktisch falschen Detailsatz im
  "Entscheidung"-Abschnitt: „`brightsky` (DWD) dient dem Radar-Pfad, `radar_dpc` dem Nowcast
  Italien." → der zweite Halbsatz muss auf „für Italien läuft der Radar-Pfad seit #1648 über
  ARPAE ICON-2I (Open-Meteo selbst, kein separater Provider)" korrigiert werden. Das ist eine
  Tatsachenkorrektur an einer bereits akzeptierten Entscheidung, keine Rücknahme oder neue
  Grundsatzentscheidung — daher kein Statuswechsel auf „Abgelöst durch".
- **Zusätzlich (Doku, nicht ADR):** `docs/specs/modules/radar_nowcast_italy_arpae_fallback.md`
  (Spec zu #1186, Status weiterhin `draft`/nie freigegeben) beschreibt ARPAE explizit als
  „Rückfall UNTER Radar-DPC" — diese Architektur existiert nach dieser Scheibe nicht mehr. Die
  Spec sollte einen Superseded-Vermerk (Verweis auf diese Spec) erhalten, analog zum bereits
  archivierten `docs/specs/_archive/modules/issue_1162_radar_dpc.md`.

## Changelog

- 2026-08-11: Initial spec created (Issue #1648), Zeilennummern gegen `origin/main`-Stand
  05:XX UTC verifiziert (radar_service.py deckt sich mit den im Auftrag genannten Werten fast
  exakt; die vier Alarm-Konsumenten-Dateien sind seit der letzten Messung spürbar verschoben —
  keiner davon benötigt aber einen Code-Eingriff in dieser Scheibe).
