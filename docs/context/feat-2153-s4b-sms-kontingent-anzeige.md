# Context: feat-2153-s4b-sms-kontingent-anzeige

## Request Summary
S4b von #2153/#2412: Das in S4a (live seit `fc6afefd`) durchgesetzte Tages-SMS-Kontingent
(getrennt SMS/Premium-SMS, UTC-Tag) soll dem Nutzer auf `/account` als Zählerstand sichtbar
werden ("3 von 10"). S4a lieferte nur Durchsetzung + Log, keine Sichtbarkeit.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/sms_daily_limit.py:1-253` | Zähler-Schreibpfad aus S4a. `check_and_reserve()` (Z.119), `release_reservation()` (Z.200). **Keine Lesefunktion vorhanden** — `_load()` (Z.50) und `_zaehlerwert()` (Z.64) sind interne Helfer, nicht exportiert. Für S4b muss eine neue Lesefunktion ergänzt werden (z.B. `usage(user_id, now)`). Datenfile: `<get_data_dir(user_id)>/sms_daily_count.json`, Schema `{"date": "YYYY-MM-DD", "sms": N, "premium_sms": M}`. |
| `src/services/user_tier.py:16-17,48,68,73` | Limitwerte: `_DAILY_SMS_LIMIT = {"free":0,"standard":10,"premium":10}`, `_DAILY_PREMIUM_SMS_LIMIT = {"free":0,"standard":0,"premium":15}`. Öffentliche Getter `daily_sms_limit(user_id)` (Z.68), `daily_premium_sms_limit(user_id)` (Z.73) — das sind die "Y"-Werte für "X von Y". Reserven (`SMS_ALARM_RESERVE=2`, `PREMIUM_SMS_ALARM_RESERVE=3`, `PREMIUM_SMS_REPLY_OVERSHOOT=3`, Z.12-14) sind separate Konstanten, nicht im Grundlimit enthalten. |
| `api/routers/internal.py` | Alle Routen hinter `X-GZ-Core-Auth` (Middleware `api/main.py:149ff`, fail-closed). Muster für `user_id` als Pflicht-Query-Param ohne Default: `loaded_trip` (Z.47-48), `stages_weather` (Z.73-77) — Kommentar Z.137-139 begründet explizit KEIN `"default"`-Fallback (Cross-User-Risiko). `POST /api/_internal/sms/verification-code` (Z.166-198, S3-Vorbild). **`GET /api/_internal/sms/daily-usage` existiert noch nicht** — im S4a-Spec (Z.74) bereits als künftiger Name vermerkt. |
| `internal/handler/auth.go:717-844` | `profileResponse`-Struct (Z.717-767) hat bereits `SmsAllowed`/`PremiumSmsAllowed` (Z.726, 750) — rein lokal aus Tier abgeleitet (`toProfileResponse`, Z.780-829), **kein Python-Roundtrip** bisher. `GetProfileHandler` (Z.831-844) lädt nur aus `store.Store`, ruft aktuell keinen externen Service. Für den Zähler muss hier ein neuer synchroner HTTP-Call an Python ergänzt werden. |
| `internal/handler/sms_verify.go:96-131` | Bestes Vorbild für Go→Python-Call: `http.Client{Timeout: 10s}`, `client.Post(cfg.PythonCoreURL+"/api/_internal/sms/verification-code", ...)`. Auth-Header `X-GZ-Core-Auth` wird automatisch über `internal/coreauth/transport.go` (via `http.DefaultTransport`) angehängt, solange kein eigener `Transport` gesetzt wird. |
| `internal/handler/telegram_webhook.go:37-73` | Alternatives Proxy-Muster: `pythonCoreURL` als Parameter, Timeout 5s, Fehler beim Forward werden nur geloggt (fail-soft). Basis-URL kommt aus `internal/config/config.go:29` (`PYTHON_CORE_URL`, Default `http://localhost:8000`). |
| `internal/model/tier.go:8-40` | `SmsAllowed(tier)`, `PremiumSmsAllowed(tier)` (bewusst KEINE Delegation aneinander, ADR-0049 Punkt 5), `EffectiveTier(tier)` als einzige Normalisierungsstelle. Kein Zähler-Feld im `User`-Struct (`user.go:10-68`) — Zähler bleibt Python-seitige Single Source of Truth, wird live geholt, nicht im Go-Modell gespiegelt. |
| `frontend/src/routes/account/+page.svelte` | `data.profile?.sms_to/sms_verified/pending_sms_to` (Z.30, 227) bereits konsumiert. "Zähler"-Block (Z.1065-1079) ist bestehendes UI-Muster für einfache Label/Wert-Zeilen (`Aktive Trips: {data.trips.length}`), **kein "X von Y"-Format, kein Fortschrittsbalken** im Projekt vorhanden (`frontend/src/lib/components/ui` hat keine Progress-Komponente). Naheliegende Einfügestelle: im "Dein Account"-Card (`data-testid="account-section"`) neben `data-testid="channels"` (Z.1082). |
| `docs/specs/modules/sms_daily_limit.md` | S4a-Spec (`status: draft`, `workflow: feat-2153-s4-sms-tageslimit`). Grenzt S4b explizit aus (Z.72-79, Z.301-303): "`GET /api/_internal/sms/daily-usage`, Go-Anbindung und Frontend-Anzeige sind NICHT Teil dieser Spec — eigener Folge-Workflow." Cap-Tabelle je Tier/Kanal/Zweck: Z.157-166 (relevant für die Frage, welches Limit angezeigt wird — Grundlimit vs. Cap je Zweck). |
| `docs/adr/0049-premium-sms-vierter-kanal.md` | Punkt 5: eigenes Tier-Gate für Premium-SMS, keine Ableitung aus SMS-Gate — gilt unverändert, S4b ändert daran nichts, zeigt nur bestehende Werte an. |
| `tests/tdd/test_sms_tageslimit.py:195-228` | Test-Helfer bestätigen Zähler-Schema 1:1. Mandanten-Testmuster: `_kennung(praefix)` erzeugt eindeutige `user_id` je Test via `uuid.uuid4().hex[:8]` (bewusst ohne "test"-Präfix). `test_ac6_mandantentrennung_zwischen_zwei_nutzern` (Z.590) als Vorbild für den in CLAUDE.md geforderten Zwei-Nutzer-Test. |

## Existing Patterns

- **Go→Python interner Call:** `internal/handler/sms_verify.go` (POST) und `internal/handler/telegram_webhook.go` (GET-Proxy) sind die zwei etablierten Varianten. Für einen einfachen Read-Only-Endpunkt (`daily-usage`) ist ein direkter Handler wie in `sms_verify.go`/`GetProfileHandler` naheliegender als ein generischer `ProxyHandler`, weil das Ergebnis in `profileResponse` eingebettet werden könnte ODER als eigenständiger Endpoint bestehen bleibt (siehe Issue-Empfehlung: eigenständiger Endpoint, damit `/account` auch lädt, wenn Python nicht erreichbar ist).
- **Interne FastAPI-Routen:** Pflicht-`user_id`-Query-Parameter ohne Default, Auth über `X-GZ-Core-Auth`-Header (Middleware, nicht pro Route).
- **Zähler-Datei-Zugriff:** `_load()`/`_zaehlerwert()` in `sms_daily_limit.py` sind bereits fail-open bei kaputten Daten — eine neue Lesefunktion sollte dieselbe Fail-Open-Robustheit übernehmen.
- **Frontend Label/Wert-Zeile:** bestehender "Zähler"-Block als Formvorbild, aber ohne "X von Y"-Semantik — das ist für S4b neu.

## Dependencies

- **Upstream (was S4b braucht):** `sms_daily_limit.py` (Zählerdatei + Cap-Konstanten aus `user_tier.py`), Auth-Middleware `api/main.py`, Go `profileResponse`/`GetProfileHandler`, Go-Session-Kontext (`middleware.UserIDFromContext`).
- **Downstream (was auf S4b aufbaut):** nichts Bekanntes — reine Anzeige, keine weiteren Konsumenten.

## Existing Specs

- `docs/specs/modules/sms_daily_limit.md` — S4a-Spec, S4b-Anforderungen explizit als "nicht Teil dieser Spec" benannt, liefert aber das Datenschema und die Cap-Tabelle, auf der S4b aufbaut. S4b braucht eine eigene neue Spec-Datei (z.B. `docs/specs/modules/sms_daily_usage_anzeige.md` oder Ergänzung der bestehenden Datei — Entscheidung gehört in `/20-analyse`/`/30-write-spec`).

## Risks & Considerations

- **Welches Limit wird angezeigt?** Grundlimit (`daily_sms_limit`/`daily_premium_sms_limit`) vs. tatsächlich nutzbares Kontingent nach Abzug der Alarm-Reserve — unterschiedliche Zahlen möglich, Klärung nötig (offene Frage aus dem Explore-Fund, betrifft AC-Formulierung).
- **Python nicht erreichbar:** Issue-Empfehlung fordert, dass `/account` trotzdem lädt (kein Hard-Fail bei Profile-Load, wenn Zähler-Call scheitert) — muss als eigene AC in die Spec.
- **Mandantentrennung (CLAUDE.md-Pflicht):** `user_id` muss aus dem authentifizierten Session-Kontext kommen (`middleware.UserIDFromContext`), niemals vom Client. Zwei-Nutzer-Test ist Pflicht (Vorbild: `test_ad6_mandantentrennung_zwischen_zwei_nutzern`).
- **Keine Lesefunktion im Python-Modul:** muss neu geschrieben werden, sollte dieselbe Fail-Open-Robustheit wie `_load()` erben, damit ein defektes Zählerfile die Kontoseite nicht zum Absturz bringt.
- **UI ohne Fortschrittsbalken-Baustein:** Entscheidung nötig, ob reiner Text ("3 von 10") reicht oder eine neue Komponente sinnvoll ist — Design-Leitprinzip Lesbarkeit (CLAUDE.md) spricht eher für klaren Text als für neue visuelle Bausteine ohne Not.
- **Premium-SMS Sichtbarkeit nur bei Premium-Tier:** analog zu `shouldShowPremiumSmsLinkCard` sollte der Premium-SMS-Zähler wohl nur angezeigt werden, wenn der Kanal für den Nutzer überhaupt relevant ist (Tier-abhängig).

## Analysis

### Type
Feature

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/sms_daily_limit.py` | MODIFY | Rollover-/Fail-Open-Logik aus `check_and_reserve()` (Z.173-176) in gemeinsamen Helfer extrahieren (z.B. `_tagesstand(data, today)`); neue Lesefunktion `get_daily_usage(user_id, now)` darauf aufbauend, liefert `used/limit/reserve/reply_overshoot` je Kanal (SMS, Premium-SMS) aus `user_tier`-Konstanten |
| `api/routers/internal.py` | CREATE | `GET /api/_internal/sms/daily-usage?user_id=<auth>` — Pflicht-Query-Param ohne Default, hinter `X-GZ-Core-Auth` (Middleware, ADR-0062) |
| `internal/handler/` (neue Datei, Muster `sms_verify.go`) | CREATE | Dedizierter Go-Handler — **kein** bare `ProxyHandler` (der reicht `RawQuery` ungeprüft durch, Mandantentrennungs-Risiko). `user_id` serverseitig aus `middleware.UserIDFromContext`, Timeout 1-2s (nicht Proxy-Standard 10s), `X-GZ-Core-Auth` via `coreauth.Install` |
| `internal/router.go` | MODIFY | neue Route registrieren (Z.40 AuthMiddleware gilt bereits global) |
| `frontend/src/routes/account/+page.server.ts` | MODIFY | zusätzlicher Fetch im bestehenden `Promise.all([...])` (Z.17-42), `.catch(() => null)` — bestehende Fail-Soft-Konvention, kein neuer Mechanismus nötig |
| `frontend/src/lib/types.ts` | MODIFY | DTO-Typ für `used/limit/reserve/reply_overshoot` je Kanal |
| `frontend/src/routes/account/+page.svelte` (nahe Z.1065-1079) | MODIFY | neuer Zähler-Block "X von Y" mit Sub-Label (Reserve-Hinweis); Premium-SMS-Zeile nur bei `limit > 0` |
| `docs/reference/api_contract.md` | MODIFY | neuer interner Endpoint dokumentieren (SSOT, Format-Vorbild `/api/_internal/trips/{trip_id}/stages-weather`) |
| `docs/specs/modules/` (neue Spec-Datei) | CREATE | eigene Spec für S4b — gehört in `/30-write-spec`, hier nur benannt |
| Tests: Python (Zwei-Nutzer, Vorbild `tests/test_sms_verification_code_endpoint.py:98-108`), Go-Handler-Test | CREATE | Pflicht laut CLAUDE.md (jeder nutzerbezogene Endpoint mit zwei Nutzern) |

### Scope Assessment
- Files: 9 (production) + 1 neue Spec-Datei + Tests
- Estimated LoC: production ca. +140 (Python ~50, Go ~50, Frontend ~40), Tests separat ca. +120 (zählen laut CLAUDE.md-Konvention nicht gegen das 250-LoC-Budget, aber Produktiv+Test zusammen liegen nah am Budget — `workflow.py status` vor `/50-implement` prüfen, ggf. `loc_limit_override`)
- Risk Level: MEDIUM — kein einzelner Bereich riskant, aber 3 Sprachen/Schichten (Python/Go/Frontend) plus Mandantentrennungs-Pflicht plus Rollover-Logik, die dupliziert werden könnte

### Technical Approach
**Empfehlung (Plan/Sonnet-Bewertung):**
- **Architektur:** dedizierter Go-Endpoint, NICHT Einbettung in `profileResponse`/`GetProfileHandler`. Begründung: `/api/auth/profile` wird zusätzlich in `+layout.server.ts` auf JEDER Seite geladen — eine Einbettung würde einen neuen Python-Roundtrip in diesen global gecachten Pfad einführen (Latenz + neue Fehlerquelle auf jeder Seite). Ein separater, nur von `/account` aufgerufener Endpoint fügt sich ins bestehende `Promise.all(...).catch(() => null)`-Muster ein (Fail-Soft ist dort bereits Konvention).
- **Kein bare `ProxyHandler`:** der generische Proxy (`router.go:187`, `proxy.go:49`) reicht `r.URL.RawQuery` ungeprüft durch — Mandantentrennungs-Risiko (Client könnte fremde `user_id` mitschicken). Vorbild ist `CompareProxyHandler` (serverseitiges `user_id`-Anhängen) oder ein dedizierter Handler nach Muster `sms_verify.go:96-131`.
- **Angezeigtes Y = Grundlimit** (10 SMS / 15 Premium-SMS), NICHT der briefing-Cap (8/12). Begründung: Y=briefing-Cap würde bei "8 von 8" fälschlich "keine SMS mehr möglich" suggerieren, obwohl noch eine Alarm-SMS gesendet werden kann — in einer sicherheitsrelevanten Wetter-Alarm-App der gefährlichere Fehleindruck. Stattdessen Y=Grundlimit mit erklärendem Sub-Label ("davon max. 8 Briefings, 2 Alarm-Reserve"), das genau das vom PO-Kontext befürchtete Missverständnis ("3 von 10" wirkt großzügiger als real nutzbar) auflöst, ohne den gefährlicheren Eindruck zu erzeugen.
- **Premium-SMS Reply-Overshoot:** kann den Grundlimit-Cap überschreiten (18 > 15) — Anzeige explizit als Zusatz kennzeichnen (z.B. "15 von 15 (+2 Antworten)"), nicht stillschweigend clampen.
- **DTO liefert `used/limit/reserve/reply_overshoot` direkt aus `user_tier`-Konstanten**, damit das Sub-Label nicht im Frontend gepflegt wird und driften kann.
- **Reihenfolge:** (1) gemeinsamer Rollover-Helfer in `sms_daily_limit.py` → (2) neue Lesefunktion → (3) Python-Internal-Endpoint → (4) dedizierter Go-Handler → (5) Frontend Typ+UI.

### Dependencies
- **Upstream:** `sms_daily_limit.py` (Zählerdatei + Rollover-Logik), `user_tier.py` (Cap-Konstanten), Auth-Middleware `api/main.py` (X-GZ-Core-Auth), Go-Session-Kontext (`middleware.UserIDFromContext`), bestehendes Fail-Soft-Muster in `+page.server.ts`
- **Downstream:** keine bekannten Konsumenten — reine Anzeige

### Open Questions
- [x] Welches Limit wird angezeigt? → Grundlimit + Sub-Label (siehe Technical Approach) — Empfehlung für Spec-Freigabe
- [x] Python nicht erreichbar? → Fail-Soft über bestehendes `.catch(() => null)`-Muster in `+page.server.ts`, keine neue Mechanik nötig
- [ ] Genaue UI-Formulierung des Sub-Labels und Darstellung des Reply-Overshoot — gehört in `/30-write-spec`
- [ ] Name/Route des neuen Go-Endpoints (`GET /api/auth/sms-daily-usage` vorgeschlagen) — Bestätigung in Spec
