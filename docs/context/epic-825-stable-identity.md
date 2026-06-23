# Context: Epic #825 + Bug #824 — Stabile Identitätsschicht

## Request Summary

Mehrere Bugs (#823, #824) haben dieselbe Wurzel: Entitäten (Trips, Etappen, Segmente)
werden über Position oder Datum *identifiziert*, statt über eine vergebene, stabile ID
*referenziert*. Epic #825 beschreibt die architektonische Lösung; #824 ist das erste
konkrete Symptom und dient als Akzeptanz-Beweis.

---

## Ist-Zustand pro Ebene

### 1. Trip-ID — Frontend-vergeben (Kollisionsrisiko)

| Datei | Zeile | Befund |
|---|---|---|
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | 104 | `crypto.randomUUID().slice(0, 8)` — Trip-ID wird im Browser erzeugt |
| `frontend/src/lib/components/edit/EditRouteSection.svelte` | 16 | `crypto.randomUUID().slice(0, 8)` — neue Etappen-ID ebenfalls im Frontend |
| `internal/handler/trip.go` | 59–61 | Backend akzeptiert jede nicht-leere ID; erzeugt keine |
| `internal/handler/trip.go` | 79–95 | `randomShortID()` nur für **Etappen** (ensureStageIDs), nie für den Trip selbst |

**Problem:** Zwei Browser-Sessions oder zwei Nutzern könnten durch Zufall dieselbe
8-Zeichen-ID vergeben. Außerdem gibt es keinen Autoritätspunkt — wer hat die „echte" ID?

### 2. Stage-ID — existiert, aber nicht stabil über Updates

| Datei | Zeile | Befund |
|---|---|---|
| `internal/handler/trip.go` | 88–95 | `ensureStageIDs` füllt **nur leere** Stage-IDs auf |
| `internal/handler/trip.go` | 111, 189 | Wird bei CREATE und UPDATE aufgerufen |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | 107 | Frontend erzeugt Etappen-IDs ebenfalls via `crypto.randomUUID().slice(0, 8)` |

**Problem:** Schickt das Frontend bei einem PUT die Stage ohne ihre ursprüngliche ID
zurück, erzeugt `ensureStageIDs` eine *neue* ID. Etappen-IDs sind faktisch temporär —
nach einem missglückten Roundtrip (z.B. Edit-UI liest ID nicht korrekt zurück) zeigt
die Alert-State-Referenz auf eine nicht mehr existierende Stage-ID.

Echte Bestandsdaten zeigen 8-Zeichen-Hex-IDs: `2d108fe0`, `9304b7c5`, etc.

### 3. Segment-ID — nur positional (1-basiert)

| Datei | Zeile | Befund |
|---|---|---|
| `src/app/models.py` | 317 | `segment_id: int \| str  # 1-based, or "Ziel" for destination` |
| `src/services/weather_change_detection.py` | 370, 436, 477 | Alert-State-Key = `"metric:segment_id"` z.B. `temp_min_c:1` |

**Problem:** Segment-Position ist relativ zum Tag. Nach Abend-Briefing (Snapshot für
„morgen") und neuem Morgen-Alert kann dieselbe Position `1` eine andere physische
Stelle auf der Route meinen → #823 (Alert vergleicht gegen falsche Etappe).

### 4. Archived-At-Filterung — fehlt in Python

| Datei | Zeile | Befund |
|---|---|---|
| `src/app/trip.py` | 199 | `archived_at: Optional[str] = None` — **Feld existiert** ✓ |
| `src/app/loader.py` | 944–968 | `load_all_trips` lädt **alle** Trips, kein `archived_at`-Filter |
| `src/services/inbound_telegram_reader.py` | 277–298 | `_find_active_trip` — kein `archived_at`-Filter |
| `src/services/trip_report_scheduler.py` | 262–302 | `_get_active_trips` — kein `archived_at`-Filter |
| `src/services/trip_alert.py` | 273, 610 | `load_all_trips` ohne Filter → archivierte Trips erhalten Alert-Checks |

**Folge:** Archivieren setzt `archived_at` im Go-Backend, aber alle Python-Pfade
ignorieren das Feld → archivierte Trips bekommen weiterhin Briefings, Alert-Checks
und Telegram-Antworten.

### 5. Mehrere gleichzeitig aktive Trips — nicht deterministisch

`_find_active_trip` gibt den **ersten** Trip mit Datum-Overlap zurück
(abhängig von `glob("*.json")`-Reihenfolge = undefiniertes Dateisystem-Verhalten).
PO-Entscheidung (#825): Zwei aktive Trips gleichzeitig sind Normalfall, kein Fehler.

### 6. Inbound-Routing — kein Trip-Kontext mitgeführt

| Datei | Befund |
|---|---|
| `src/services/inbound_telegram_reader.py` | `_find_active_trip` → Datum-Raten |
| `src/services/inbound_email_reader.py:238` | `default`-Fallback bei unbekanntem Absender (Cross-User-Leck) |
| `src/app/trip.py` | `shortcode: str = ""` — GZ#-Code existiert, wird aber nicht fürs Telegram-Routing genutzt |

---

## Related Files

| Datei | Relevanz |
|---|---|
| `internal/handler/trip.go` | Trip-CREATE (kein serverseitiger ID-Generator), ensureStageIDs |
| `internal/model/trip.go` | Go-Trip-Struct: `ID`, `ArchivedAt`, `Shortcode` |
| `src/app/trip.py` | Python-Trip-Datenklasse: `id`, `archived_at`, `shortcode` |
| `src/app/loader.py` | `load_all_trips` (kein archived-Filter), `load_trip`, `save_trip` |
| `src/app/models.py` | `TripSegment.segment_id` (1-basiert), `SegmentWeatherSummary` |
| `src/services/inbound_telegram_reader.py` | `_find_active_trip` (Datum-Raten, kein archived-Filter) |
| `src/services/trip_report_scheduler.py` | `_get_active_trips` (kein archived-Filter) |
| `src/services/trip_alert.py` | Alert-Check-Loop: `load_all_trips` kein Filter, `end_date`-Check aber kein `archived_at` |
| `src/services/weather_change_detection.py` | Alert-State-Keys: `metric:segment_id` (positional) |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts` | `newId()` → `crypto.randomUUID().slice(0,8)` |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Etappen-ID ebenfalls Frontend-seitig |

---

## Existierende Specs (relevant)

| Spec | Status | Relevanz |
|---|---|---|
| `docs/specs/modules/inbound_telegram_reader.md` | deprecated → `telegram_webhook_inbound` | Inbound-Architektur |
| `docs/specs/modules/trip_shortcode_routing.md` | approved, 2026-06-12 | GZ#-Shortcode als Routing-Key für E-Mail Inbound; Telegram noch nicht |
| `docs/specs/modules/go_trip_crud.md` | — | Trip-CRUD-Vertrag |
| `docs/specs/modules/issue_243_empty_stage_ids.md` | closed | ensureStageIDs (Backend-Fallback, nicht vollständige Lösung) |
| `docs/specs/modules/bug_663_trip_command_user_isolation.md` | closed | Multi-User Isolation im Command-Processor |

---

## Abhängigkeiten

**Upstream (was unser Code nutzt):**
- `load_all_trips` → wird von Telegram-Reader, Scheduler, Alert-Service, Command-Processor verwendet
- Go `SaveTrip` → persistiert Trip-JSON unter `data/users/<uid>/trips/<id>.json`
- Bestandsdaten: echte Trips mit vorhandenen IDs müssen migriert werden (Schema-Rework-Pflicht)

**Downstream (was unseren Code nutzt):**
- `_find_active_trip` → verwendet von Telegram-Inbound (2 Stellen)
- `_get_active_trips` → Scheduler-Haupt-Loop
- Alert-State-Keys (`metric:segment_id`) → persistiert in `data/users/*/alert_state/`
- `load_all_trips` → shortcode.py, trip_command_processor.py, inbound_email_reader.py

---

## Scope-Abgrenzung: Was ist #824, was ist #825?

### #824 (Bug — kurzfristig behebbar, isoliert)
1. `_find_active_trip`: archivierte Trips ausfiltern (`if trip.archived_at: continue`)
2. `_get_active_trips` im Scheduler: archivierte Trips ausfiltern
3. `trip_alert.py` Alert-Check-Loop: archivierte Trips ausfiltern
4. Determinismus bei 2+ aktiven Trips: letztmodifizierter gewinnt (statt Dateisystem-Reihenfolge)

**Dateien:** `inbound_telegram_reader.py`, `trip_report_scheduler.py`, `trip_alert.py`
**LoC-Schätzung:** ~20–40 LoC, 3–4 Dateien

### #825 (Epic — breitere Architektur)
- Trip-ID serverseitig vergeben (Go-Handler)
- Stage-ID dauerhaft stabil über Updates (Merge-Strategie statt Array-Replace)
- Segment-Komposit-ID (stage_id + Position) für Alert-State-Keys
- Context-basiertes Telegram-Routing (Shortcode statt Datum-Raten)
- E-Mail-Inbound: `default`-Fallback ablösen

**Dateien:** +Go-Handler, +Frontend-ID-Vergabe, +Alert-State-Schlüssel
**LoC-Schätzung:** ~150–300 LoC, 8–12 Dateien

---

## Analysis

### Type
Bug (#824) + Epic (#825)

### Betroffene Dateien

**Scope #824 — archived-at Filter (Bug):**

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/app/loader.py` | MODIFY | `load_all_trips()` → Parameter `include_archived=False` oder neuer `load_active_trips()`-Wrapper |
| `src/services/inbound_telegram_reader.py` | MODIFY | `_find_active_trip()` — archivierte Trips filtern |
| `src/services/trip_report_scheduler.py` | MODIFY | `_get_active_trips()` — archivierte Trips filtern |
| `src/services/trip_alert.py` | MODIFY | 2 Stellen: `check_all()` + `run_radar_monitoring()` |
| `src/services/trip_command_processor.py` | MODIFY | `_find_trip()` (Zeile 360) — ebenfalls filtern |
| `src/services/inbound_email_reader.py` | MODIFY | `_find_trip_id()` (Zeile 243) — archivierte ausschließen |

**Scope #825a — Stage-ID-Stabilität (Epic, Minimum-Slice):**

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | VERIFY/MODIFY | Stage-ID-Roundtrip beim PUT prüfen — werden IDs beim Speichern mitgeschickt? |

**Scope #825b — Segment-ID Komposit (Epic, separates Ticket empfohlen):**

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/app/models.py` | MODIFY | `TripSegment.segment_id` → Komposit `stage_id:position` |
| `src/services/weather_change_detection.py` | MODIFY | Alert-State-Keys migrieren |

**Scope #825c — Telegram-Shortcode-Routing (later):**
*Email-Inbound nutzt Shortcode bereits (`trip_shortcode_routing.md`, approved 2026-06-12). Telegram fehlt noch.*

### Scope-Bewertung

| Scope | Dateien | LoC | Deploybar ohne andere |
|---|---|---|---|
| #824 (archived-Filter) | 6 Python | ~35 | ✅ ja |
| #825a (Stage-ID-Stabilität) | 1–2 Frontend | ~30–50 | ✅ ja |
| #825b (Segment-Komposit) | 2 Python + Datenmigration | ~100 | Erst nach #825a |
| #825c (Telegram-Shortcode) | 1 Python | ~20 | ✅ unabhängig |

### Technischer Ansatz

**#824:** Zentraler `include_archived=False`-Parameter in `load_all_trips()` als Opt-In. Alle aktiven Pfade (Telegram, Scheduler, Alert, CommandProcessor) übergeben `include_archived=False` und erhalten damit automatisch nur nicht-archivierte Trips. Kein Breaking Change für bestehende Caller.

**#825a:** Prüfen ob `EditStagesPanelNew.svelte` beim PUT die Stage-IDs aus dem Store roundtripped. Wenn ja: kein Code-Fix nötig, nur Test. Wenn nein: State-Binding korrigieren.

**#825b:** Schema-Migration nötig (Alert-State-Keys) → eigenständiges Risiko, eigener Workflow.

### Offene Fragen

- [x] Ist `archived_at` im Python-Modell vorhanden? → **Ja**, seit #805 (`trip.py:199`)
- [x] Nutzt E-Mail-Inbound bereits Shortcode? → **Ja**, `trip_shortcode_routing.md` approved
- [ ] Roundtripped `EditStagesPanelNew.svelte` Stage-IDs beim PUT korrekt? → Muss geprüft werden

---

## Risiken & Überlegungen

1. **Schema-Rework-Pflicht:** Wenn Stage-IDs sich ändern (z.B. durch neue Vergabe-Strategie),
   müssen Bestandsdaten migriert werden. Alert-State-Keys referenzieren aktuell
   `metric:positional_segment_id` — eine Änderung des Schlüsselformats entwertete
   alle persistierten Alert-States (→ Stale-Alert-Problem).

2. **Schrittweise vs. Big-Bang:** PO will keine Quick-Fixes, aber die Architektur breit
   aufzuziehen erhöht Implementierungsrisiko. Empfehlung für Analyse: #824 zuerst als
   separaten Scope definieren (archiviert-Filter), #825 dann schrittweise (zuerst
   Server-IDs, dann Segment-Komposit).

3. **Frontend-IDs sind nicht sofort portierbar:** Wenn der Go-Handler Trip-IDs
   serverseitig erzeugt (z.B. via `randomShortID()`), muss das Frontend die
   zurückgelieferte ID aus dem 201-Response übernehmen. Sveltekit-Store muss angepasst werden.

4. **Alert-State-Key-Migration:** Wenn `segment_id` von positional auf
   stage-ID-komposit wechselt, verliert das System alle bisherigen Referenzwerte →
   erste Stunde nach Deploy keine Δ-Alerts. Akzeptabel, muss kommuniziert werden.

5. **`load_all_trips` kein archived-Filter:** Mehrere Aufrufstellen; ein
   zentraler Filter in `load_all_trips` selbst (opt-in `include_archived=False`) wäre
   sicher und wartbar ohne alle Callsites zu ändern.
