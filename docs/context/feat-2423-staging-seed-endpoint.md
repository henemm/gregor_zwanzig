# Context: feat-2423-staging-seed-endpoint

## Request Summary
Staging-only Endpoint, der für den **eingeloggten** Test-Nutzer den Tarif (`tier`) und/oder den SMS-/Premium-SMS-Tageszählerstand setzt. Grund: #2412 (S4b) AC-1..AC-3 waren auf Staging nicht messbar, AC-4 nur schwach belegt. Blockiert den Prod-Deploy von #2412 (PO 2026-09-25).

## Related Files
| File | Relevanz |
|------|----------|
| `internal/router/router.go:82-111` | Registrierungsmuster `if os.Getenv("GZ_ENV") == "staging" { r.Post(...) }` (verify-email/staging-token, sms/staging-code) |
| `internal/handler/staging_sms_code.go` | Vorbild: ignoriert den Rumpf, arbeitet nur auf `middleware.UserIDFromContext` — kein Fremdkonto |
| `internal/handler/staging_verify_token.go` | Älteres Vorbild (nimmt `username` aus Rumpf — bewusst NICHT übernehmen) |
| `internal/handler/staging_verify_token_test.go`, `sms_staging_code_test.go` | Testmuster: echter Router, Positivkontrolle GZ_ENV=staging vs. 404 in Prod, Anmeldepflicht |
| `internal/store/user.go:48-95` | `UserDir`, `LoadUser`, `SaveUser` (Tarif liegt in `model.User.Tier`) |
| `internal/model/tier.go` | `EffectiveTier` — nur free/standard/premium gültig |
| `src/services/sms_daily_limit.py` | Zählerformat `sms_daily_count.json` = `{"date":"YYYY-MM-DD","sms":N,"premium_sms":M}`; Tageswechsel = Nullstand; atomares Schreiben + Sidecar-Lock |
| `api/routers/internal.py:203` | `GET /api/_internal/sms/daily-usage` — Leseweg der Anzeige (Python) |
| `internal/handler/sms_daily_usage.go` | Go-Proxy der Anzeige für /account |
| `api/main.py:116` | Python-Muster für staging-only Router (`GZ_ENV == "staging"`) |

## Existing Patterns
- Staging-Sperre = Route wird nur bei `GZ_ENV=staging` registriert (sonst 404), Pfad unter `/api/auth/...` (nicht `/api/debug/`, das ist pauschal öffentlich → Anmeldepflicht bliebe sonst aus).
- Nutzerkennung ausschließlich aus dem Auth-Kontext, Rumpf-Nutzerfeld ignorieren.
- Tests gegen den echten Router mit Positivkontrolle.

## Designfrage für die Analyse
Tarif liegt im Go-Store, Zähler in Python-Datendatei. Zwei Wege: (a) Go schreibt `sms_daily_count.json` selbst ins Nutzerverzeichnis (Format-Duplikat), (b) Go ruft einen staging-only Python-Internal-Endpoint, der über `sms_daily_limit` schreibt (kein Format-Duplikat, aber Core-Auth + zweiter Prozess). Zu prüfen: teilen Go und Python dasselbe Datenverzeichnis auf Staging (Datenbestand für `hem` nicht lesbar).

## Dependencies
- Upstream: Auth-Middleware, `store.SaveUser`, `sms_daily_limit`-Zählerformat
- Downstream: `staging-validator`-Läufe für #2412 (AC-1..AC-4), Account-Seite

## Existing Specs
- `docs/specs/modules/sms_daily_limit.md` (AC-1..AC-10), `docs/specs/modules/sms_nummer_verifikation.md` §5 (Staging-Testweg-Muster)

## Risks & Considerations
- **Blast Radius:** falsch registriert = Rechte-Eskalation auf Prod (Tarifwechsel ohne Admin-Freigabe). Test: Prod-Lage → 404, mit Positivkontrolle.
- **Mandantentrennung:** nur eigenes Konto; Test mit zwei Nutzern (Nutzer B bleibt unverändert).
- **Merge statt Replace:** `SaveUser` auf geladenem Objekt, nur `Tier` ändern (Client-unbekannte Felder erhalten).
- Eingabevalidierung: `tier` ∈ free/standard/premium, Zähler nichtnegative Ganzzahlen, Obergrenze sinnvoll.
- Staging-Datenbestand nicht lesbar → Verifikation nur über API/UI, nicht per Dateizugriff.

## Analysis

### Type
Feature (Test-Infrastruktur, nur Staging)

### Befund zur Designfrage
Go und Python teilen auf Staging dasselbe Datenverzeichnis (`GZ_DATA_DIR=/var/lib/gregor-staging` in beiden `1595-datenwurzel.conf`). Beide Wege sind also technisch möglich.
**Empfehlung: Weg (b).** Go schreibt `Tier` selbst (`LoadUser` → `Tier` ändern → `SaveUser`, Merge statt Replace). Den Zähler schreibt der Python-Core über eine neue Funktion in `sms_daily_limit.py`. Das vermeidet ein zweites Format-Duplikat des Zählers. Sie nutzt `_write`, den Sidecar-Lock und `_tagesstand`, also dieselbe Tageswechsel-Regel wie Lesen und Reservieren.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/staging_seed.go` | CREATE | `StagingSeedHandler(store, cfg)`: Rumpf `{tier?, sms?, premium_sms?}`; Nutzer NUR aus `UserIDFromContext`, Nutzerfelder im Rumpf ignoriert; Validierung tier ∈ free/standard/premium, Zähler Ganzzahl 0..1000; Zähler-Teil per Proxy an Python (Muster `sms_daily_usage.go`, Fail = 502, kein stilles OK) |
| `internal/router/router.go` | MODIFY | `if GZ_ENV=="staging" { r.Post("/api/auth/staging-seed", ...) }` (unter `/api/auth/`, anmeldepflichtig, NICHT `/api/debug/`) |
| `src/services/sms_daily_limit.py` | MODIFY | `seed_daily_usage(user_id, sms, premium_sms, now)`: Lock + `_write` mit `{"date": heute, "sms": N, "premium_sms": M}` |
| `api/routers/internal.py` | MODIFY | `POST /api/_internal/sms/seed-daily-usage`, nur bei `GZ_ENV=="staging"` (sonst 404). Core-Auth-Header greift automatisch (#2142) |
| `internal/handler/staging_seed_test.go` | CREATE | echter Router: Prod-Lage → 404 mit Positivkontrolle; ohne Login → 401; zwei Nutzer, B bleibt unverändert; Tier-Merge erhält Fremdfelder; ungültiger tier → 400 |
| `tests/tdd/test_sms_daily_seed.py` (Name nach Verhalten) | CREATE | Schreib-/Lese-Roundtrip über `get_daily_usage`, Tageswechsel, Nutzer-Isolation, Prod-Sperre der Route |
| `docs/reference/api_contract.md`, `docs/specs/modules/…` | MODIFY | Endpoint-Vertrag, Spec |

### Scope Assessment
- Files: 4 produktiv + 2 Tests (+ Doku)
- Estimated LoC: ca. +150 produktiv / +200 Tests
- Risk Level: MITTEL — auf Staging harmlos, aber eine falsch registrierte Route wäre auf Prod eine Rechte-Eskalation (Tarifwechsel ohne Admin-Freigabe). Deshalb Doppelsperre (Go UND Python) und Test „Prod → 404".

### Technical Approach
1. Python: `seed_daily_usage` + Internal-Route (nur `GZ_ENV=staging`).
2. Go: Handler + Registrierung nur bei `GZ_ENV=staging`. Reihenfolge: erst validieren, dann Zähler (Python), dann Tier — bei Fehler kein halber Zustand ohne Meldung. Antwort: gesetzter Stand (`tier`, `sms`, `premium_sms`).
3. Nachweis der Wirkung: danach `GET /api/auth/sms-daily-usage` (Leseweg von #2412) liefert die gesetzten Werte — das ist die Brücke zu #2412 AC-1..AC-4.
4. Nutzerkennung ausschließlich aus dem Auth-Kontext, nie `"default"`.

### Dependencies
- Upstream: Auth-Middleware, `store.SaveUser`, Core-Auth (#2142), `sms_daily_limit`-Zählerformat, `user_tier.daily_*_limit`.
- Downstream: `staging-validator`-Läufe für #2412; Prod-Deploy von #2412 ist bis dahin blockiert.

### Open Questions
- [ ] Obergrenze für Zählerwerte: Vorschlag 1000 (deckt Reply-Overshoot-Fall „15 von 15 (+2)" ab) — Tech-Entscheid, kein PO-Thema.
- [ ] Soll ein Aufruf ohne Rumpffelder ein No-op mit 400 sein? Vorschlag: ja, 400 `nothing_to_set`.
