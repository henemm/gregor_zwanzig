---
entity_id: staging_seed_endpoint
type: feature
created: 2026-09-25
updated: 2026-09-25
status: draft
workflow: feat-2423-staging-seed-endpoint
version: "1.0"
tags: [staging, test-infrastruktur, tiers, sms, epic-2138]
---

# Staging-only Seed-Endpoint fuer Tarif und SMS-Tageszaehler (#2423)

## Approval

- [ ] Approved

## Purpose

Auf Staging gibt es keinen Self-Service-Weg, ein Testkonto auf `standard`/`premium` zu setzen
(Tarifwechsel verlangt Admin-Freigabe per Mail) und keinen Weg, einen SMS-/Premium-SMS-Tageszaehlerstand
vorzugeben (Datenbestand fuer den Server-User nicht lesbar). Dadurch waren die Kontingent-Anzeige-ACs
von #2412 (S4b) auf echtem Staging-DOM nicht messbar. Diese Spec fuehrt einen Endpoint ein, der **nur auf
Staging** und **nur fuer das eingeloggte Konto** Tarif und/oder Tageszaehler setzt. Er ist reine
Test-Infrastruktur; auf Produktion darf er weder erreichbar noch registriert sein (eine Fehlregistrierung waere dort
eine Rechte-Eskalation: Tarifwechsel ohne Admin-Freigabe).

## Entscheidungen (Tech-Lead, verbindlich)

| # | Frage | Entscheidung |
|---|---|---|
| E1 | Wer schreibt den Zaehler? | Weg (b): der Python-Core ueber eine neue Funktion in `sms_daily_limit.py` (kein Format-Duplikat in Go). Go schreibt nur den Tarif. |
| E2 | Obergrenze Zaehlerwerte | 0..1000 (deckt den Overshoot-Fall "15 von 15 (+2)" ab). |
| E3 | Leerer Rumpf | 400 `nothing_to_set`. |
| E4 | Ungueltiger Tarif / Zaehler | 400 `validation_error`. |
| E5 | Sperre | Doppelsperre: Go-Route nur bei `GZ_ENV=staging` registriert (sonst 404) UND Python-Internal-Route nur bei `GZ_ENV=staging` (sonst 404). |
| E6 | Nutzerkennung | Ausschliesslich aus dem Auth-Kontext (`middleware.UserIDFromContext`); Nutzerfelder im Rumpf werden ignoriert. Nie `"default"`. |
| E7 | Reihenfolge / Fehler | Erst validieren, dann Zaehler (Python), dann Tarif (Go). Python-Fehler = 502, kein stilles OK. |

## Source

- **File:** `internal/handler/staging_seed.go` (neu), `internal/router/router.go`, `src/services/sms_daily_limit.py`, `api/routers/internal.py`
- **Identifier:** `StagingSeedHandler`, `seed_daily_usage(user_id, sms, premium_sms, now)`, Route `POST /api/auth/staging-seed`, Route `POST /api/_internal/sms/seed-daily-usage`

> **Schicht-Hinweis:** Go-API (`internal/`) fuer Anmeldepflicht, Tarif-Persistenz und Sperre; Python-Core
> (`api/`, `src/services/`) fuer den Zaehler, weil Format, Lock und Tageswechsel-Regel dort leben.
> Keine Frontend-Aenderung. Route liegt bewusst unter `/api/auth/` (anmeldepflichtig), NICHT unter
> `/api/debug/` (pauschal oeffentlich).

## Estimated Scope

- **LoC:** ca. 150 produktiv (Tests und Doku zaehlen nicht)
- **Files:** 4 produktiv + 2 Testdateien + Doku-Nachtrag (`docs/reference/api_contract.md`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/staging_sms_code.go`, `internal/router/router.go:82-111` | pattern | Vorbild: Registrierung nur bei `GZ_ENV=staging`, Nutzer nur aus Auth-Kontext, Rumpf-Nutzerfeld ignoriert |
| `internal/handler/sms_daily_usage.go` | pattern | Go-Proxy zum Python-Core (Core-Auth-Header automatisch, #2142) |
| `internal/store/user.go` (`LoadUser`, `SaveUser`) | module | Tarif laden/speichern (Merge) |
| `internal/model/tier.go` | module | Gueltige Tarife: `free`, `standard`, `premium` |
| `src/services/sms_daily_limit.py` (`_path`, `_today`, `_tagesstand`, `_write`, Sidecar-Lock) | module | Zaehlerformat `{"date":"YYYY-MM-DD","sms":N,"premium_sms":M}`, Tageswechsel = Nullstand |
| `api/main.py:116` | pattern | Python-Muster fuer staging-only Router (`GZ_ENV == "staging"`) |
| `GET /api/auth/sms-daily-usage` (#2412) | module | Leseweg; dient als Nachweis-Bruecke der Wirkung |

## Implementation Details

```
POST /api/auth/staging-seed        (Go; nur registriert wenn GZ_ENV=="staging"; hinter Auth)
  Rumpf: {"tier"?: "free|standard|premium", "sms"?: int 0..1000, "premium_sms"?: int 0..1000}
  1. user_id = middleware.UserIDFromContext(ctx)   # 401 durch Auth-Middleware ohne Login
  2. Rumpf lesen; unbekannte Felder (auch user_id/username) ignorieren
  3. Validieren: keines der drei Felder gesetzt -> 400 nothing_to_set;
     tier ausserhalb der drei Werte -> 400 validation_error;
     sms/premium_sms keine Ganzzahl oder ausserhalb 0..1000 -> 400 validation_error
  4. Zaehler gesetzt? -> POST Python /api/_internal/sms/seed-daily-usage
     {user_id, sms?, premium_sms?}; Fehler/Nicht-2xx/Timeout -> 502 core_unavailable
  5. tier gesetzt? -> u = store.LoadUser(user_id); u.Tier = tier; store.SaveUser(u)  (Merge)
  6. Antwort 200: {"tier": <effektiver Tarif>, "sms": <Stand>, "premium_sms": <Stand>}

POST /api/_internal/sms/seed-daily-usage   (Python; nur bei GZ_ENV=="staging", sonst 404)
  seed_daily_usage(user_id, sms, premium_sms, now):
    Lock (Sidecar) -> _load -> _tagesstand(heute) -> gesetzte Felder ueberschreiben,
    nicht gesetzte behalten -> _write({"date": heute(UTC), "sms": N, "premium_sms": M})
    Rueckgabe: neuer Stand {"sms": N, "premium_sms": M}
```

Ein nicht gesetztes Zaehlerfeld bleibt auf dem heutigen Stand (nach Tageswechsel-Regel 0). Der
Zaehlerwert darf das Tageslimit des Tarifs uebersteigen (Overshoot-Fall, z.B. `sms` 12 bei Limit 10);
er wird nicht auf das Limit gekappt. Wenn nur `tier` gesetzt ist, wird der Python-Core nicht aufgerufen;
die Antwort liest dann den aktuellen Zaehlerstand ueber den Leseweg. Ist Python beim reinen
Tarif-Aufruf nicht erreichbar, bleibt der Tarif trotzdem gesetzt und die Antwort weist `sms`/`premium_sms`
nicht aus (Felder fehlen), ohne Fehler.

## Expected Behavior

- **Input:** angemeldeter Aufruf mit JSON-Rumpf, mindestens eines von `tier`, `sms`, `premium_sms`.
- **Output:** 200 mit gesetztem Stand; 400 `nothing_to_set` / `validation_error`; 401 ohne Login; 404 ausserhalb Staging; 502 bei Core-Fehler.
- **Side effects:** `tier` im Nutzerobjekt des eingeloggten Kontos und/oder `sms_daily_count.json` desselben Kontos. Kein anderes Konto wird beruehrt.

## Acceptance Criteria

- **AC-1:** Given der Server laeuft in Produktionslage (`GZ_ENV` nicht `staging`) / When ein eingeloggter Nutzer `POST /api/auth/staging-seed` aufruft / Then antwortet die API mit 404 und weder Tarif noch Zaehler des Nutzers aendern sich; die Gegenprobe mit `GZ_ENV=staging` am selben echten Router liefert fuer denselben Aufruf 200 (Positivkontrolle).
  - Test: Go-Test gegen den echten Router in beiden Umgebungslagen; nach dem 404 wird der Tarif des Nutzers aus dem Store gelesen und ist unveraendert.

- **AC-2:** Given Staging-Lage ohne gueltige Anmeldung / When `POST /api/auth/staging-seed` mit gueltigem Rumpf aufgerufen wird / Then antwortet die API mit 401 und es wird nichts geschrieben.
  - Test: Go-Test gegen den echten Router ohne Session-Cookie; Tarif und Zaehler unveraendert.

- **AC-3:** Given zwei angemeldete Nutzer A und B, B auf `free` mit Zaehler 0 / When Nutzer A `tier=premium` sowie `sms=3` sendet und der Rumpf zusaetzlich `user_id`/`username` von B enthaelt / Then aendert sich nur das Konto von A, und Nutzer B behaelt Tarif `free` und Zaehlerstand 0 (Rumpf-Nutzerfelder werden ignoriert).
  - Test: Go-Test mit zwei Nutzern; B wird danach ueber Store und Leseweg `GET /api/auth/sms-daily-usage` gelesen und ist unveraendert.

- **AC-4:** Given ein Nutzer mit gespeichertem Tarif `free` und einem Client-unbekannten Zusatzfeld im Nutzerobjekt / When er `tier=standard` setzt / Then hat er danach Tarif `standard` und alle uebrigen Felder des Nutzerobjekts (auch das Zusatzfeld) sind unveraendert erhalten (Merge, kein Replace).
  - Test: Go-Test mit vorbefuelltem Nutzerobjekt inkl. Fremdfeld; nach dem Aufruf `LoadUser` und Feldvergleich.

- **AC-5:** Given ein angemeldeter Nutzer in Staging-Lage / When er einen leeren Rumpf `{}`, einen ungueltigen Tarif (`gold`), einen negativen Zaehler (`sms=-1`), einen Zaehler ueber der Obergrenze (`sms=1001`) oder einen Nicht-Ganzzahl-Wert (`premium_sms=2.5`) sendet / Then antwortet die API mit 400 (`nothing_to_set` fuer den leeren Rumpf, sonst `validation_error`) und schreibt weder Tarif noch Zaehler; auch bei gueltigem `tier` neben einem ungueltigen Zaehler bleibt der Tarif unveraendert.
  - Test: Go-Test mit Tabelle der Fehlfaelle; danach Tarif und Zaehler unveraendert. Gueltige Grenzwerte `sms=0` und `sms=1000` liefern 200.

- **AC-6:** Given ein Nutzer im Tarif `standard` (Limit 10 SMS) / When er `sms=3` setzt / Then liefert `GET /api/auth/sms-daily-usage` danach `sms.used = 3`, `sms.limit = 10` und `premium_sms.used = 0`, und die Antwort des Seed-Aufrufs nennt `tier`, `sms` und `premium_sms` mit denselben Werten.
  - Test: Roundtrip ueber den echten Leseweg (Go-Proxy und Python-Lesefunktion `get_daily_usage`), nicht ueber Dateiinhalt.

- **AC-7:** Given ein Nutzer im Tarif `premium` (Limit 15 Premium-SMS) / When er `tier=premium` und `premium_sms=17` (Reply-Overshoot ueber dem Limit) setzt / Then liefert der Leseweg `premium_sms.used = 17` bei `limit = 15` (nicht auf das Limit gekappt), sodass die Anzeige "15 von 15 (+2 Antworten)" auf Staging messbar wird.
  - Test: Python-Test `seed_daily_usage` + `get_daily_usage` mit Wert ueber dem Limit; zusaetzlich Go-Roundtrip ueber den Leseweg.

- **AC-8:** Given ein per Seed gesetzter Zaehlerstand mit dem Datum von heute (UTC) / When der Tag wechselt (Lesen mit `now` am Folgetag) / Then zeigt der Leseweg wieder `used = 0` fuer beide Zaehler; und Given eine Zaehlerdatei mit gestrigem Datum / When ein Seed nur `sms=4` setzt / Then steht danach `sms = 4`, `premium_sms = 0` und das Datum ist heute.
  - Test: Python-Test mit fixierten `now`-Werten ueber Schreib- und Leseweg (`seed_daily_usage`, `get_daily_usage`).

- **AC-9:** Given zwei Nutzer im Python-Core / When `seed_daily_usage` fuer Nutzer A aufgerufen wird / Then aendert sich die Zaehlerdatei von Nutzer B nicht, und der Aufruf hinterlaesst eine atomar geschriebene, gueltige Zaehlerdatei (Lock-gesichert wie `check_and_reserve`).
  - Test: Python-Test mit zwei `user_id`-Werten; Lesen ueber `get_daily_usage`; parallele Reservierung und Seed erzeugen keine kaputte Datei.

- **AC-10:** Given der Python-Core laeuft in Produktionslage (`GZ_ENV` nicht `staging`) / When `POST /api/_internal/sms/seed-daily-usage` aufgerufen wird (auch mit gueltigem Core-Auth-Header) / Then antwortet er mit 404 und der Zaehler des Nutzers bleibt unveraendert; mit `GZ_ENV=staging` liefert derselbe Aufruf 200 (Positivkontrolle).
  - Test: Python-Test gegen die echte FastAPI-App in beiden Umgebungslagen; Zaehler danach ueber `get_daily_usage` gelesen.

- **AC-11:** Given Staging-Lage und der Python-Core ist nicht erreichbar oder antwortet mit Fehler / When ein Nutzer `sms=3` (mit oder ohne `tier`) sendet / Then antwortet die Go-API mit 502 und meldet den Fehler (kein stilles 200), und der Tarif wird in diesem Aufruf nicht geaendert (Zaehler wird vor dem Tarif geschrieben).
  - Test: Go-Test mit auf einen toten Port zeigendem Core-Endpunkt; nach dem 502 Tarif aus dem Store unveraendert.

- **AC-12:** Given ein Nutzer ohne Fremdkonto-Kenntnis / When der Aufruf ohne jedes Nutzerfeld im Rumpf (nur `{"tier":"standard"}`) gesendet wird / Then wirkt er auf das eingeloggte Konto (die Nutzerkennung stammt aus dem Auth-Kontext, nie `"default"`), und es entsteht kein Nutzerverzeichnis `default`.
  - Test: Go-Test mit Nutzer ungleich `default`; danach Tarif dieses Nutzers gesetzt und kein Datenordner `default` angelegt.

## Known Limitations

- Nur ein Testwerkzeug fuer Staging; auf Produktion existiert weder Route noch Funktion im Aufrufweg.
- Setzt keine Zaehler fuer andere Konten und keinen Tarif fuer andere Konten (bewusst, Mandantentrennung).
- Kein Ruecksetzen auf den Ausgangszustand vorgesehen; Testkonten setzen die Werte per erneutem Aufruf zurueck (`free`, `0`).
- Reiner Tarif-Aufruf bei Core-Ausfall liefert 200 ohne Zaehlerfelder (siehe Implementation Details).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Test-Infrastruktur nach etabliertem Muster (`GZ_ENV=staging`-Registrierung, wie `sms/staging-code`); keine Aenderung an Kanaelen, Datenmodell oder Auth-Paradigma. Der Zaehler wird ueber die bestehende Funktionsfamilie in `sms_daily_limit.py` geschrieben, um kein zweites Format in Go zu duplizieren.

## Changelog

- 2026-09-25: Initial spec created (Issue #2423)
