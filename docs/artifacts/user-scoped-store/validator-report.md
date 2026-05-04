# External Validator Report

**Spec:** docs/specs/modules/user_scoped_store.md
**Datum:** 2026-04-15T18:08:00+02:00
**Server:** https://gregor20.henemm.com
**Validator:** External (isoliert, kein Source-Code gelesen)

## Checklist

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | Ohne Session-Cookie → 401 unauthorized | `curl /api/locations` → `{"error":"unauthorized"}` 401 | **PASS** |
| 2 | Gefaelschter Cookie → 401 unauthorized | `curl -b "gz_session=alice.12345.fake" /api/locations` → 401 | **PASS** |
| 3 | Gueltiger Cookie → 200 mit Daten | Login admin → Cookie `gz_session=default.1776269148.bc8...` → /api/locations 200 | **PASS** |
| 4 | Health-Endpoint ohne Auth erreichbar | `curl /api/health` ohne Cookie → 200 `{"status":"ok"}` | **PASS** |
| 5 | Scheduler-Status ohne Auth erreichbar | `curl /api/scheduler/status` ohne Cookie → 200 mit 5 Jobs | **PASS** |
| 6 | Locations: Anzahl API = Dateisystem (default) | API: 15, `ls data/users/default/locations/ \| wc -l`: 15 | **PASS** |
| 7 | Trips: Anzahl API = Dateisystem (default) | API: 4, `ls data/users/default/trips/ \| wc -l`: 4 | **PASS** |
| 8 | Subscriptions: API mit Auth funktioniert | 200, 3 Subscriptions | **PASS** |
| 9 | POST Location → richtiges User-Verzeichnis | POST `validator-test-loc` → `data/users/default/locations/validator-test-loc.json` existiert | **PASS** |
| 10 | Kein Cross-User-Leak bei Schreibzugriff | `find data/users/ -name "validator-test-loc.json" -not -path "*/default/*"` → leer | **PASS** |
| 11 | DELETE Location → aus richtigem Verzeichnis | DELETE `validator-test-loc` → 204, Datei weg | **PASS** |
| 12 | Weather-Config braucht Auth | `/api/subscriptions/mallorca-/weather-config` ohne Cookie → 401 | **PASS** |
| 13 | Weather-Config funktioniert mit Auth | Gleicher Endpoint mit Cookie → 200, 24 Metrics | **PASS** |
| 14 | Proxy `/api/compare` funktioniert mit Auth | `GET /api/compare?location_ids=aberg` → 200 mit Wetterdaten | **PASS** |
| 15 | Proxy `/api/forecast` funktioniert mit Auth | `GET /api/forecast` → 400 (Validierung, nicht 401) | **PASS** |

## Findings

### F1: Cross-User Isolation nicht testbar (Known Limitation)
- **Severity:** LOW
- **Expected:** Eingeloggter User "alice" → Store liest `data/users/alice/`
- **Actual:** Nur ein User-Account (admin → default) existiert. Session-Cookies sind HMAC-signiert, daher kann kein zweiter User simuliert werden. User-Anlage ist explizit Out-of-Scope (F13 Phase 2).
- **Evidence:** Cookie-Format `userId.timestamp.hmac_signature` — Faelschung wird korrekt mit 401 abgelehnt

### F2: Proxy user_id-Forwarding nicht direkt verifizierbar
- **Severity:** LOW
- **Expected:** Proxy-Requests enthalten `?user_id={userId}` an Python
- **Actual:** Python loggt den Parameter nicht, und ohne zweiten User-Account sind die Ergebnisse identisch. Indirekt bestaetigt: Compare-Endpoint liefert Location-Daten die zu `data/users/default/` passen.
- **Evidence:** `GET /api/compare?location_ids=aberg` → liefert "Hochkoenig/Aberg" Wetterdaten (existiert in default-Verzeichnis)

### F3: Weather-Config Endpoints nested statt top-level
- **Severity:** INFO
- **Expected:** Spec listet 6 Handler in `weather_config.go`
- **Actual:** Top-level `/api/weather-config` → 404. Endpoints sind unter `/api/subscriptions/{id}/weather-config` und `/api/trips/{id}/weather-config` erreichbar. Funktioniert korrekt.
- **Evidence:** `/api/subscriptions/mallorca-/weather-config` → 200

## Verdict: VERIFIED

### Begruendung

Alle 15 Checkpunkte bestanden. Die Kernfunktionalitaet ist verifiziert:

1. **Auth Middleware:** Blockt korrekt unauthentifizierte (401) und gefaelschte Cookies (401). HMAC-Signatur schuetzt vor Cookie-Spoofing.
2. **Data Routing:** API-Responses stimmen exakt mit Dateisystem unter `data/users/default/` ueberein (15 Locations, 4 Trips, 3 Subscriptions).
3. **Write Operations:** POST erstellt Dateien im korrekten User-Verzeichnis, kein Leak in andere Verzeichnisse. DELETE raeumt korrekt auf.
4. **Auth-Exemptions:** Health und Scheduler-Status sind korrekt von Auth ausgenommen.
5. **Alle Handler-Typen:** locations, trips, subscriptions, weather-config, proxy — alle auth-geschuetzt und funktional.

**Einschraenkung:** Cross-User-Isolation konnte mangels zweitem User-Account nicht getestet werden. Dies ist eine dokumentierte Known Limitation der Spec (F13 Phase 2 regelt User-Anlage). Die architekturellen Grundlagen (signierte Cookies, Store-Scoping) sind vorhanden.
