---
entity_id: issue_830_radar_alert_validator
type: module
created: 2026-06-15
updated: 2026-06-15
status: draft
version: "1.0"
tags: [tooling, gate, radar, alert, mail, validator, staging, debug-endpoint]
---

# Issue #830 — Radar-Alert-Mail testbar machen

## Approval

- [ ] Approved

## Purpose

Schließt die letzte Prüflücke des Radar-Alert-Pfads: Obwohl #822 Logik und Adversary-Tests
lieferte, wurde der **Mail-Inhalt** (HTML-Struktur, Segment-Label, Onset-TZ, Cooldown-Zeile,
Intensitätsstufe) nie gegen einen formalen Validator geprüft — weil der Radar-Alert-Body weder
über API auslösbar noch durch einen dedizierten IMAP-basierten Validator prüfbar war. Dieses
Issue ergänzt drei zusammenhängende Teile: (1) einen Staging-Only-Trigger-Endpoint der denselben
Code-Pfad wie echter Regen durchläuft, (2) einen `radar_alert_mail_validator.py` analog zu den
bestehenden Briefing- und Compare-Validatoren, und (3) eine Erweiterung des `renderer_mail_gate.py`
um den Radar-Alert-Renderer, damit künftige Änderungen an diesem Pfad vor dem Commit verifiziert
sein müssen.

## Source

- **Datei (neu):** `api/routers/debug.py` — Staging-Only Trigger-Endpoint `POST /api/debug/trigger-radar-alert`
- **Datei (Änderung):** `api/main.py` — neuen Router einbinden (bedingt auf `GZ_ENV=staging`)
- **Datei (neu):** `src/outputs/radar_alert.py` — pure functions `build_radar_alert_body()` + `build_radar_alert_subject()` (aus `trip_alert.py` extrahiert)
- **Datei (Änderung):** `src/services/trip_alert.py` — ruft `build_radar_alert_body/subject` auf + übergibt `mail_type="radar-alert"` an `EmailOutput.send()`
- **Datei (Änderung):** `src/app/config.py` — `env: str = "production"` ergänzen (liest `GZ_ENV`)
- **Datei (neu):** `.claude/hooks/radar_alert_mail_validator.py` — IMAP-Fetch, Header-Filter `X-GZ-Mail-Type: radar-alert`, Plausibilitätsprüfungen, YAML-Log, Exit 0/1
- **Datei (Änderung):** `.claude/hooks/renderer_mail_gate.py` — `_MAIL_PATTERNS` um `src/outputs/radar_alert.py` + `src/formatters/radar.*\.py` erweitern; Gate prüft zusätzlich `*_radar_alert_validation.yaml`

> **Schicht-Hinweis:** `api/routers/debug.py` und `api/main.py` sind Go-API-Dateien
> (`api/`, Port 8090). `src/outputs/radar_alert.py`, `src/services/trip_alert.py` und
> `src/app/config.py` sind Python-Backend-Dateien. `.claude/hooks/` ist reines Tooling.
> `frontend/` bleibt unberührt.

## Estimated Scope

- **LoC:** ~280–350 (Trigger-Endpoint ~60, Body-Extraktion ~60, Config ~10, Validator ~120, Gate-Erweiterung ~30, Tests ~80)
- **Files:** 3 neu, 4 geändert
- **Effort:** medium — loc_limit_override 400

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/services/trip_alert.py` — `check_radar_alerts()` | upstream (Refactor) | Radar-Alert-Body-Aufbau wird in `src/outputs/radar_alert.py` extrahiert; hier verbleiben nur Orchestrierung, Throttle, Versand |
| `src/services/trip_alert.py` — `EmailOutput.send()` Aufruf (Z. 675) | upstream (Änderung) | muss `mail_type="radar-alert"` erhalten damit der Marker-Header `X-GZ-Mail-Type: radar-alert` gesetzt wird |
| `src/outputs/email.py` — `EmailOutput` | upstream | Versand; `mail_type`-Parameter muss Header setzen analog zu `trip-briefing` |
| `src/app/config.py` — `Settings` | upstream (Änderung) | neues Feld `env: str = "production"` liest `GZ_ENV`-ENV-Variable |
| `src/services/trip_segments.py` — `convert_trip_to_segments()` | upstream | Segment-Ableitung im Trigger-Endpoint für ersten Trip des Users |
| `src/services/radar_service.py` — `RadarNowcastService.get_nowcast()`, `format_now_text()`, `radar_alert_due()` | upstream | Nowcast-Abruf für Trigger-Endpoint (echter Code-Pfad, kein Mock) |
| `.claude/hooks/briefing_mail_validator.py` | Referenz (Vorbild) | IMAP-Fetch-Muster, Header-Filter, YAML-Log-Format, Exit-Codes 0/1/2 |
| `.claude/hooks/renderer_mail_gate.py` | downstream (Änderung) | Gate-Patterns und Nachweis-Prüfung erweitern |
| `GZ_IMAP_*` ENV-Variablen | Konfiguration | IMAP-Zugang Stalwart (`gregor-test@henemm.com`) — nie im Klartext |
| Issue #811 — `renderer_mail_gate.py` | Vorarbeit | Gate-Mechanismus (Hash/mtime-Bindung, Anti-Stale) auf dem dieser Slice aufbaut |
| Issue #822 — Segment-bewusster Radar-Alert | Vorarbeit | Mail-Inhalt (Segment-Label, Onset-TZ, Cooldown) der vom Validator geprüft wird |
| Issue #733 — `briefing_mail_validator.py` | Referenz | kanonisches Validator-Muster für diesen Slice |

## Implementation Details

### Teil 1 — Radar-Alert-Body extrahieren (`src/outputs/radar_alert.py`)

Der Radar-Alert-Body wird aktuell inline in `check_radar_alerts()` (`trip_alert.py:644–665`)
gebaut. Er wird als pure functions in ein neues Modul extrahiert:

```
build_radar_alert_subject(trip_name, result, label) -> str
    Konvektiv (result.is_convective == True): "[<trip_name>] ⚠️ Gewitter – <label>"
    Nicht konvektiv: "[<trip_name>] Regen zieht auf – <label>"

build_radar_alert_body(onset_text, segment_label, cooldown_display, source) -> str
    Produziert den reinen Text-Body (analog zu bisherigem Inline-Aufbau).
    Alle Parameter werden übergeben — keine Seiteneffekte, kein I/O.
```

`check_radar_alerts()` ruft diese Funktionen auf und übergibt das Ergebnis an
`EmailOutput.send(..., mail_type="radar-alert")`.

`EmailOutput.send()` muss `mail_type` als `X-GZ-Mail-Type`-Header setzen — Prüfen ob das
bereits für `trip-briefing` implementiert ist und analog einbauen.

### Teil 2 — `env`-Feld in `src/app/config.py`

```python
env: str = Field(default="production", env="GZ_ENV")
```

`GZ_ENV=staging` ist in `/home/hem/gregor_zwanzig_staging/.env` gesetzt.
Produktion hat kein `GZ_ENV` → Default `"production"`.

### Teil 3 — Trigger-Endpoint (`api/routers/debug.py`)

```
POST /api/debug/trigger-radar-alert
Query-Param: user_id (str, Default: "default")

Ablauf:
1. Prüft Settings().env == "staging" → sonst HTTP 404
2. Lädt alle Trips für user_id (LoadAllTrips aus Store)
3. Falls keine Trips: Response {"status": "no_trips"}
4. Ersten Trip nehmen, convert_trip_to_segments() aufrufen
5. Aktives/nächstes Segment ableiten (dieselbe Logik wie check_radar_alerts)
6. Falls kein Segment: Response {"status": "no_segment"}
7. get_nowcast(lat, lon) aufrufen — echter Call, kein Mock
8. build_radar_alert_body/subject aufrufen mit echten Werten
9. EmailOutput.send() an gregor-test@henemm.com (Override des normalen Recipients),
   mail_type="radar-alert"
10. Response: {"status": "sent", "trip_id": "...", "segment": "<segment_id>"}

Kein radar_alert_due()-Check im Trigger (damit Staging-Test auch bei keinem Regen funktioniert).
Kein Throttle-Eintrag — der Endpoint ist ein reiner Test-Seam, kein echter Alert.
```

Der Router wird in `api/main.go` nur eingebunden wenn `os.Getenv("GZ_ENV") == "staging"`.
Der Router muss in Go implementiert sein (api/ ist Go), wobei der eigentliche Python-Code
über den internen HTTP-Call an den Python-FastAPI-Port aufgerufen werden kann — oder der
Endpoint liegt direkt im Python-FastAPI-Teil (unter `/api/debug/` in `src/`). Developer
Agent entscheidet anhand der bestehenden Debug-/Trigger-Endpoint-Muster im Projekt.

### Teil 4 — `radar_alert_mail_validator.py` (`.claude/hooks/`)

Analog zu `briefing_mail_validator.py`:

```
Liest echte zugestellte Mail aus Stalwart-IMAP (gregor-test@henemm.com).
Filtert nach X-GZ-Mail-Type: radar-alert (Header).
Fehlender Header → Exit 2 (falscher Validator für diesen Pfad — sauberes No-Op).

Plausibilitätsprüfungen (nicht nur String-Presence):
  P-1: Segment-Name vorhanden (z.B. "Etappe N" oder "km X–Y") — nicht leer
  P-2: Onset-Zeitstempel im erwarteten TZ-Format vorhanden (HH:MM, kein "None", kein UTC-Rohwert)
  P-3: Intensitätsstufe 1–5 implizit aus Onset-Text oder Body erkennbar
       (eines der bekannten Intensitäts-Label: "Leichter Regen", "Mäßiger Regen",
        "Starker Regen", "Starker Hagel/Gewitter" oder Variante davon)
  P-4: Cooldown-Hinweis vorhanden ("höchstens einmal in")

Alle P bestehen → Exit 0 + YAML-Log schreiben
Mindestens ein P schlägt fehl → Exit 1 + Fehlerdetail auf stderr + YAML-Log (failed)
```

YAML-Log: `.claude/workflows/_log/<workflow_id>_radar_alert_validation.yaml`
Format analog zu `*_briefing_validation.yaml` (Felder: `passed`, `validated_at`,
`workflow_id`, `findings` pro Prüfung).

### Teil 5 — Gate-Erweiterung (`renderer_mail_gate.py`)

`_MAIL_PATTERNS` erhält zwei neue Einträge:
```python
r"src/outputs/radar_alert\.py$",
r"src/formatters/radar.*\.py$",
```

Nachweis-Prüfung: Gate sucht zusätzlich nach `*_radar_alert_validation.yaml` (neben
`*_briefing_validation.yaml`) wenn eine der Radar-Alert-Dateien gestaged ist. Bei
Radar-Alert-Dateien in Stage und fehlendem/stale Radar-Alert-Nachweis → Exit 2.

Anti-Stale: sha256 der Radar-Alert-Renderer-Dateien analog zu Briefing-Nachweis.

## Expected Behavior

- **Input (Trigger):** `POST /api/debug/trigger-radar-alert?user_id=default` auf Staging
- **Output (Trigger):** HTTP 200 mit `{"status": "sent", "trip_id": "...", "segment": "..."}` + Mail in `gregor-test@henemm.com` innerhalb 60s; auf Produktion HTTP 404
- **Input (Validator):** läuft nach Trigger gegen IMAP
- **Output (Validator):** Exit 0 wenn alle Plausibilitätsprüfungen bestehen; Exit 1 mit Fehlerdetail wenn eine Prüfung scheitert; YAML-Log in jedem Fall
- **Input (Gate):** `git commit` mit gestagten Radar-Alert-Renderer-Dateien
- **Output (Gate):** blockiert Commit (Exit 2) bis frischer `*_radar_alert_validation.yaml`-Nachweis vorliegt
- **Side effects:** YAML-Log in `.claude/workflows/_log/`, kein Throttle-Eintrag durch Trigger

## Acceptance Criteria

**AC-1:** Given ein Staging-System (`GZ_ENV=staging`) mit mindestens einem Trip und Segment für den User `default` / When `POST /api/debug/trigger-radar-alert` aufgerufen wird / Then antwortet der Endpoint mit HTTP 200 und `{"status": "sent", "trip_id": "...", "segment": "..."}` und eine Radar-Alert-Mail ist im Postfach `gregor-test@henemm.com` innerhalb von 60 Sekunden zugestellt. Der Email-Versand läuft über denselben Code-Pfad wie ein echter Alert (kein Mock der Radar-Alert-Logik). Test: echter HTTP POST gegen Staging-URL, IMAP-Abruf danach.

**AC-2:** Given eine zugestellte Radar-Alert-Mail mit Header `X-GZ-Mail-Type: radar-alert` im Postfach `gregor-test@henemm.com` / When `radar_alert_mail_validator.py` ausgeführt wird / Then ist Exit 0 wenn alle vier Plausibilitätsprüfungen bestehen (Segment-Name, Onset-Zeit im TZ-Format, Intensitäts-Label, Cooldown-Hinweis), sonst Exit 1 mit Fehlerdetail auf stderr. Eine Mail ohne `X-GZ-Mail-Type: radar-alert` ergibt Exit 2 (falscher Validator, sauberes No-Op). Test: echte IMAP-Mail nach AC-1-Trigger, kein Mail-Mock.

**AC-3:** Given eine Änderung an `src/outputs/radar_alert.py` oder einem `src/formatters/radar*.py` ist gestaged / When `git commit` ausgeführt wird / Then blockiert `renderer_mail_gate.py` den Commit mit Exit 2 und einer handlungsleitenden Meldung, bis ein frischer `*_radar_alert_validation.yaml`-Nachweis (sha256/validated_at) im aktiven Workflow hinterlegt ist. Nach erfolgreichem Validator-Lauf und Nachweis-Eintrag lässt das Gate den Commit durch. Test: Temp-Git-Repo, Radar-Alert-Datei stagen, Gate als Subprozess → Exit 2; Nachweis hinterlegen → Exit 0.

**AC-4:** Given ein Produktionssystem (`GZ_ENV` nicht gesetzt oder `"production"`) / When `GET` oder `POST /api/debug/trigger-radar-alert` aufgerufen wird / Then antwortet der Endpoint mit HTTP 404 — der Endpoint existiert auf Produktion nicht. Test: HTTP-Call gegen Production-URL `https://gregor20.henemm.com/api/debug/trigger-radar-alert` → HTTP 404.

## Known Limitations

- **Kein echter Radar-Alert-Due-Check im Trigger:** Der Endpoint sendet die Mail unabhängig davon ob `radar_alert_due()` True wäre — er ist ein Test-Seam, kein Produktions-Ablauf. Kein Throttle-Eintrag, damit wiederholte Staging-Tests nicht geblockt werden.
- **Erster Trip des Users:** Der Trigger wählt den ersten verfügbaren Trip für den angegebenen `user_id`. Bei Users mit mehreren Trips ist der gewählte Trip nicht deterministisch (Reihenfolge aus Store). Für den Staging-Test ist ein einziger Test-Trip vorhanden.
- **Intensitätsstufe aus Body, nicht aus Metadaten:** Der Validator erkennt die Stufe über Schlüsselwörter im Mail-Body. Wenn der Body-Text sich ändert (Übersetzung, Formatierung), muss der Validator angepasst werden.
- **Staging-abhängig:** AC-1 und AC-2 setzen einen laufenden Staging-Server mit `GZ_ENV=staging` voraus. Sie können nicht lokal ohne Staging-Infrastruktur ausgeführt werden.

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion / Prüfmethode |
|----|---------------------------|
| AC-1 | `test_ac1_trigger_endpoint_sends_mail` — echter HTTP POST gegen Staging, IMAP-Abruf |
| AC-2 | `test_ac2_validator_exit_codes` — nach AC-1-Trigger: validator.py als Subprozess, Exit 0; Mail ohne Header: Exit 2; Mail mit fehlenden Feldern: Exit 1 |
| AC-3 | `test_ac3_gate_blocks_without_nachweis` — Temp-Git-Repo, Radar-Alert-Datei stagen, Gate-Subprozess Exit 2; Nachweis eintragen → Exit 0 |
| AC-4 | `test_ac4_production_endpoint_returns_404` — HTTP GET/POST gegen Production-URL → 404 |

Testdatei: `tests/tdd/test_issue_830_radar_alert_validator.py` (mock-frei; AC-1/AC-2 echte IMAP-Verbindung).

## Referenzen

- **#822** — Radar-/Regen-Nowcast-Alert segmentbewusst machen (Vorarbeit: Segment-Label, Onset-TZ, Cooldown-Text in Mail)
- **#811** — Briefing-Mail-Qualität erzwingen (Vorarbeit: `renderer_mail_gate.py`, Anti-Stale-Mechanik, Hash-Bindung)
- **#733** — kanonischer `briefing_mail_validator.py` (Referenz-Implementierung: IMAP-Fetch, Header-Filter, YAML-Log, Exit-Codes)

## Changelog

- 2026-06-15: v1.0 Initial spec created (Issue #830). Radar-Alert-Mail testbar machen: Staging-Trigger-Endpoint, Body-Extraktion in src/outputs/radar_alert.py, radar_alert_mail_validator.py, renderer_mail_gate.py-Erweiterung.
