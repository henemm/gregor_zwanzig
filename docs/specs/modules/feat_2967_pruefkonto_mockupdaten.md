---
entity_id: feat_2967_pruefkonto_mockupdaten
type: feature
created: 2026-11-18
updated: 2026-11-19
status: draft
version: "1.2"
tags: [einstellungen-neu, elementliste, abgleich, staging, seed, epic-2913, issue-2967, issue-3145, issue-3151]
workflow: feat-2967-pruefkonto-mockupdaten
---

# Staging-Prüfkonto mit den Mockup-Beispieldaten

## Approval

- [ ] Approved

## Purpose

Der Staging-Elementlisten-Abgleich (#2913) vergleicht das Mockup (`mockup-hub-fassung4.html`) mit einem Prüfkonto, dessen Daten nicht zum Mockup-Beispiel passen, und meldet deshalb 247 Scheinabweichungen (Besitzer `#2967`). Diese Spec liefert ein idempotentes Seed-Skript, das im eigenen Staging-Prüfkonto den Trip „GR221 Mallorca“, die eigene Vorlage „Mallorca Frühling“, den Orts-Vergleich „Münsterland“ **und alle vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) mit den Mockup-Beispielwerten** anlegt bzw. verbindet. Das Auflösen der 247 Besitzer-Einträge und das Schließen von #3145 erledigt Kind-Issue #3151 nach dem Live-Lauf (PO-Entscheid 2026-11-19).

## Source

- **File:** `scripts/staging_pruefkonto_mockupdaten.py` (neu), `tests/tdd/test_staging_pruefkonto_mockupdaten.py` (neu)
- **Identifier:** `main(argv=None, *, transport=None)`, feste Prüfkonto-IDs für Trip, Orte, Vergleich und Vorlage, feste fiktive Kanalwerte des Prüfkontos
- **Schicht:** Prüfwerkzeug (`scripts/`, `tests/`) und Runbook. Kein Go-API-, kein Python-Core-Produktcode; das Skript spricht nur die bestehende Go-API auf Staging an (öffentliche Routen über die Staging-URL, interne Routen direkt über `http://localhost:8091`).

> **Querschnitts-Prüfpunkte:**
> - **Trip/Orts-Vergleich-Teilung:** n/a. Es entsteht kein UI-Baustein, sondern ein Prüfwerkzeug, das beide Kontexte (Trip und Orts-Vergleich) mit Daten füllt.
> - **Mandantentrennung:** Das Skript schreibt nur über die Anmeldung des eigenen Staging-Prüfkontos (`u-89f9fe2f`, Zugang `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS` aus der Staging-`.env`) und nur auf eigene feste IDs; `user_id` kommt aus dem Auth-Kontext der API, nie `"default"`. Auch die internen Verbindungsaufrufe (Telegram, Premium-SMS) laufen nur mit Token bzw. Code, die der eingeloggte Nutzer selbst erzeugt hat; eine Chat-ID, die einem anderen Nutzer gehört, führt zum Abbruch (409), nie zum Überschreiben. Der Kern-Test prüft das mit zwei Nutzern im Fake-Server (AC-10, AC-15).
> - **Kanäle:** Kein Briefing- oder Alarm-Inhalt ändert sich. Das Skript verbindet im Prüfkonto E-Mail, Telegram, SMS und Premium-SMS, damit der Abgleich den Zustand „alles eingerichtet“ des Mockups sieht. Gesendet wird nichts: SMS-Code kommt über die Staging-Route `staging-code` (kein Versand), Telegram und Premium-SMS verbinden mit fiktiven Werten (kein Versand an echte Geräte).

## Estimated Scope

- **LoC:** ca. +760 (Skript ~440, Test ~310, Runbook ~10)
- **Files:** 4
- **Effort:** medium (Risiko niedrig bis mittel: nur Staging-Testkonto, zwei Schutzschichten gegen Produktion, Core-Secret nur im Speicher, keine Produktlogik)

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| scripts/staging_pruefkonto_mockupdaten.py | CREATE | Idempotenter HTTP-Seed (Muster `staging_e2e_user_en.py`): Login mit `GZ_PRUEFKONTO_*` aus der Staging-`.env`, Prod-Schutz, feste IDs, GET dann POST bzw. Read-Modify-Write-PUT nur auf eigenen IDs. Kanal-Abschnitt (E-Mail, SMS-Bestätigung, Tarif/Zähler, Telegram-Loopback, Premium-SMS-Loopback) mit Core-Auth-Header aus der Staging-`.env`. Exit 0/1/2, gibt Trip- und Orte-ID aus |
| tests/tdd/test_staging_pruefkonto_mockupdaten.py | CREATE | Kern-Test mit injizierbarem Transport gegen einen zustandsbehafteten Fake-Server, der auch die Kanalrouten (inkl. `requireLocalOnly`-Verhalten, Core-Auth-Header, 409 bei fremder Chat-ID, Trockenlauf) nachbildet (kein Mock-Theater) |
| frontend/e2e/elementliste-abgleich.staging.spec.ts | MODIFY (klein) | nur Kopfkommentar mit Hinweis auf den Seed; Abgleich bleibt lesend |
| docs/runbooks/staging_pruefkonto_seed.md | CREATE | kurzer Aufruf (Seed, dann Abgleich mit `ELEMENTLISTE_TRIP_ID`/`ELEMENTLISTE_ORTE_ID`), Zugang `GZ_PRUEFKONTO_*` (eigenes Prüfkonto, nicht `GZ_AUTH_*`, siehe Dependencies), Hinweis auf Loopback-Port 8091 und Core-Secret aus der Staging-`.env` |

Besitzerliste (`elementliste_besitzer.json`) und deren Zählwächter-Tests sind nicht mehr Teil dieser Spec; sie gehen nach #3151 (PO-Entscheid 2026-11-19).

### Nicht-Ziele

- Der Abgleich selbst schreibt weiterhin nie; Schreiben gibt es nur im separaten Seed-Skript.
- Keine Änderung an Produktcode, Katalog-Vorlagen oder Ampel-Schwellen. Kein neuer Staging-Endpunkt, keine Lockerung von `requireLocalOnly` oder `coreAuth`.
- Bekannte echte Code-Abweichungen werden **nicht** im Seed weggedrückt (siehe Known Limitations); sie bekommen Kind-Issues.
- Kein Versand an echte Geräte, keine echten Telefonnummern oder Chat-IDs; nur fiktive, eindeutige Testwerte.
- Das Trip-Datum (Feb. 2026, Vergangenheit, Status „fertig“ wie im Mockup) wird nicht verbogen.
- Live-Abgleich gegen Staging, Besitzerliste, Zählwächter und das Schließen von #3145: Kind-Issue #3151.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `scripts/staging_e2e_user_en.py` | Muster | HTTP gegen Staging, Login, idempotent, injizierbarer Transport, Exit 0/1/2 |
| `tests/tdd/test_staging_e2e_nutzer_en.py` | Muster | Aufbau des Kern-Tests mit Transport-Injektion |
| `scripts/setup_staging_validator_trip.py` | Muster | Read-Modify-Write auf eigenen Datensätzen |
| Go-API Staging (`POST/GET/PUT /api/trips`, `PUT /api/trips/{id}/weather-config` mit ETag, `POST /api/locations`, `POST/PUT /api/compare/presets`, `/api/metric-presets`) | Betrieb | Ziel der Schreibzugriffe |
| Go-API Staging Kanalrouten: `PUT /api/auth/profile`, `POST /api/auth/sms/staging-code`, `POST /api/auth/sms/verify`, `POST /api/auth/staging-seed`, `GET /api/auth/telegram-link`, `POST /api/auth/premium-sms-link-code` | Betrieb | Kanäle des Prüfkontos verbinden (öffentliche Routen über die Staging-URL) |
| Staging-Go-API direkt auf `http://localhost:8091` (`gregor-api-staging`, `GZ_PORT=8091`): `POST /api/internal/telegram-connect`, `POST /api/internal/premium-sms-learn` | Betrieb | Interne Routen; `requireLocalOnly` (`internal/handler/localhost_guard.go`) verlangt Aufruf ohne `X-Forwarded-*`/`X-Real-IP`, also direkt am Port, nicht über nginx |
| `coreAuth` (`internal/router/router.go:199`, `deps.Config.CoreSharedSecret`), Header `X-GZ-Core-Auth` (`internal/coreauth/transport.go`, `HeaderName`) | Betrieb | Pflicht-Header der internen Routen; Wert aus der Staging-`.env` (`/home/hem/gregor_zwanzig_staging/.env`), nur im Speicher, nie ausgegeben oder protokolliert |
| `internal/handler/telegram_connect.go` (ab Z. 305), `internal/handler/premium_sms_connect.go`, `internal/handler/staging_seed.go` | Quelle | Verhalten der Verbindungsrouten (409 `chat_id_already_linked`, `dry_run`, Ratebremse, `tier`/`sms`/`premium_sms`) |
| Staging-`.env` (`GZ_PRUEFKONTO_USER`, `GZ_PRUEFKONTO_PASS`, Core-Secret) | Betrieb | Anmeldung des eigenen Staging-Prüfkontos (`u-89f9fe2f`) und Core-Auth für die internen Routen. `GZ_AUTH_USER` wird bewusst **nicht** verwendet: es ist das Konto „default“, das der Seed zu Recht ablehnt (Mandantentrennung) und das rund 50 andere Staging-E2E-Tests nutzen (Tech-Lead-Entscheid 2026-11-19) |
| `docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html` | Quelle | Soll-Daten (`TRIP_METRICS`, `TRIP_OFF`, `ORTE_METRICS`, Z.347-357, 667-703; Kanalzustand `konto()` Z.365-370) |
| `src/app/metric_catalog.py` (`WEATHER_TEMPLATES`, `_REITER_WETTER`) | Referenz | Vorlage `alpen-trekking`; Reihenfolge kommt aus dem Katalograng, nicht aus gespeicherter Liste |
| Kind-Issue #3151 (Epic #2913) | Folgearbeit | Besitzerliste `elementliste_besitzer.json`, Zählwächter, Abgleich-Lauf gegen Staging, Schließen von #3145 |
| Issues #3122, #3111 | Prüfung | Dublettenprüfung vor neuen Kind-Issues |
| `docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md`, `feat_2966_abgleich_haken.md`, `feat_2913_abgleich_ganzseite.md` | Spec | Abgleich-Regeln (liest nur, nie still übersprungen) |

## Implementation Details

Das Skript folgt dem Muster von `staging_e2e_user_en.py`: Basis-URL und Zugangsdaten aus der Staging-`.env`, ein Transport (Standard HTTP, im Test ein Fake-Server-Zustand), Exit-Codes 0/1/2.

1. **Prod-Schutz zuerst.** Vor jedem Netzaufruf wird die Basis-URL geprüft (Pendant zu `assertNotProdBaseURL`): Produktions-Host (`gregor20.henemm.com` ohne `staging.`) oder unbekannter Host ⇒ Abbruch mit Exit 2, kein Login, kein Schreibzugriff. Dieselbe Prüfung gilt für den Loopback-Ziel-URL der internen Routen: erlaubt ist ausschließlich `http://localhost:8091` bzw. `http://127.0.0.1:8091`; der Prod-Port und jede andere Adresse ⇒ Exit 2.
2. **Login** mit dem eigenen Prüfkonto über `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS` (nie `GZ_AUTH_*`). Alle weiteren öffentlichen Aufrufe laufen unter dieser Sitzung.
3. **Trip „GR221 Mallorca“** mit fester ID: GET; fehlt er ⇒ `POST /api/trips`, vorhanden (409 oder GET-Treffer) ⇒ geladenes Objekt laden, nur Soll-Felder überschreiben, `PUT` (Read-Modify-Write). Inhalt: Region Mallorca, 23.–26.02.2026, 4 Etappen mit Wegpunkten (E1 Port d'Andratx → Estellencs 7,8 km ↑520; E2 Estellencs → Esporles 8,4 km ↑610, 24.02.; E3 Esporles → Valldemossa 6,9 km ↑380; E4 Valldemossa → Deià 8,4 km ↑227; Summe 31,5 km ↑1.737 m), Tempo 4,0 km/h, 300 Hm/h, zu Fuß.
4. **Wetterkonfiguration** `PUT /api/trips/{id}/weather-config` mit If-Match (ETag): `ampel.template=alpen-trekking`; Metrik-Flags wie Mockup in `metrics[].enabled` und parallel `ampel.metrics[].enabled`. An: temperature, temperature_night, wind_chill, wind, gust, precipitation, thunder, rain_probability, visibility, cloud_low, uv_index, freezing_level, snowfall_limit; wind_direction aus bzw. nur Anzeige (wie `TRIP_METRICS`); aus: cloud_total, sunshine, fresh_snow, snow_depth, dewpoint, humidity, pressure (`TRIP_OFF`).
5. **Eigene Vorlage „Mallorca Frühling“** über `/api/metric-presets`, gespeichert aus dem GR221-Stand (deckt die vier `vorlage-auswahl`-Einträge); GET vor POST, kein zweites Anlegen.
6. **Orte** Münster (60 m), Telgte (52 m), Tecklenburg (235 m) über `POST /api/locations` mit festen IDs; dann Orts-Vergleich „Münsterland“ über `POST/PUT /api/compare/presets`: Vorlage Allgemein, Morgen-Briefing 07:00, `active_metrics` in Objektform entsprechend `ORTE_METRICS`. Die Region heißt „Westfalen“, falls „Münsterland“ die Textsuche des Abgleichs kollidieren ließe (Kommentar in `elementliste-abgleich.staging.spec.ts`).
7. **Kanäle verbinden (Sollzustand = `konto()` im Modus „normal“ des Mockups).** Das Seed-Skript läuft auf demselben Host wie Staging und erreicht die Staging-Go-API direkt auf `http://localhost:8091`. Ein direkter Aufruf ohne nginx trägt keine `X-Forwarded-*`/`X-Real-IP`-Header und besteht daher `requireLocalOnly`. Die internen Routen verlangen zusätzlich `coreAuth`: Header `X-GZ-Core-Auth` mit dem Core-Secret aus der Staging-`.env`. Das Secret wird nur im Speicher gehalten und taucht in keiner Ausgabe, keinem Log, keiner Fehlermeldung und keinem Testprotokoll auf (Fehlertexte werden vor der Ausgabe bereinigt). Jeder Kanal wird zuerst gelesen (`GET /api/auth/profile`); ist der Sollzustand schon erreicht, passiert kein Schreibzugriff.
   - **E-Mail** (Mockup: „bestätigt · henning@… · +1 Empfänger“, Menü „an 2 Empfänger“): Die Konto-Adresse `mail_to` des Prüfkontos bleibt unverändert (sie liefert die Staging-Prüfmails ins Test-Postfach; eine Adressänderung verlangt außerdem Re-Auth). Die zwei Empfänger stehen im Orts-Vergleich (`empfaenger`): Konto-Adresse plus eine fiktive Adresse auf einer Testdomain (`.invalid`); fehlt die Konto-Adresse ⇒ Exit 1 vor jedem Schreibzugriff. Die Bestätigung der Konto-Adresse wird nur geprüft, nicht hergestellt (auf Staging gibt es keinen versandfreien Bestätigungsweg): `email_verified` im Profil nicht `true` ⇒ Exit 1 mit Meldung „E-Mail des Prüfkontos nicht bestätigt …“ direkt nach dem Login, vor jedem Schreibzugriff.
   - **SMS** (Mockup: „bestätigt · +49 171 …“): `PUT /api/auth/profile` (`sms_to` = fiktive, eindeutige Testnummer) → `POST /api/auth/sms/staging-code` (liefert den Code ohne Versand) → `POST /api/auth/sms/verify`.
   - **Tarif und Zähler:** `POST /api/auth/staging-seed` mit `tier=premium` (Voraussetzung dafür, dass Premium-SMS-Kandidat ist). Das Mockup zeigt im Reiter Zustellung keinen Zählerstand; die Zähler `sms` und `premium_sms` werden deshalb auf 0 gesetzt, damit der Abgleich einen deterministischen Stand sieht (Obergrenze der Route 1000).
   - **Telegram** (Mockup: „verbunden · @henning“): `GET /api/auth/telegram-link` liefert den Token; danach `POST http://localhost:8091/api/internal/telegram-connect` mit `{token, chat_id}` und Core-Auth (`internal/handler/telegram_connect.go`, ab Z. 305). `chat_id` ist eine fiktive, eindeutige Zahl des Prüfkontos. Antwort 409 `chat_id_already_linked` bei einem anderen Nutzer ⇒ Abbruch mit Exit 1, nichts überschrieben. Re-Connect desselben Nutzers ist idempotent; ist Telegram schon mit dieser Chat-ID verbunden, wird gar nicht erneut verbunden.
   - **Premium-SMS** (Mockup: „inReach · Rückadresse gelernt“): `POST /api/auth/premium-sms-link-code` erzeugt den Verknüpfungscode; danach zuerst `POST http://localhost:8091/api/internal/premium-sms-learn` mit `{from, code, dry_run:true}` und Core-Auth. Nur bei `outcome=would_learn` und passender `user_id` folgt derselbe Aufruf ohne `dry_run`. `from` ist eine fiktive inReach-Absendernummer. Die Ratebremse wird nicht ausgelöst: höchstens ein scharfer Aufruf je Lauf, kein Wiederholen bei 429 (Exit 1 mit klarer Meldung), und kein scharfer Aufruf, wenn das Profil die Rückadresse bereits als `fresh` mit dieser Nummer zeigt.
   - **Datenlage inReach/Zähler im Code:** Rückadresse und Zeitpunkt liegen am Nutzer (`User.PremiumSmsReplyTo`, `User.PremiumSmsReplyAt`, Zustand `none`/`stale`/`fresh` über `model.DerivePremiumSmsReplyState`, Frist 30 Tage, `internal/model/premium_sms.go`); der Verknüpfungscode liegt je Nutzer in `premium_sms_link.json`; Tarif und Nutzungszähler (`sms`, `premium_sms`) setzt `staging-seed`.
8. **Ausgabe:** zwei Zeilen `ELEMENTLISTE_TRIP_ID=<id>` und `ELEMENTLISTE_ORTE_ID=<id>` auf stdout, direkt als Umgebung für den Abgleich nutzbar.
9. **Exit-Codes:** 0 = Soll-Zustand erreicht bzw. bereits vorhanden; 1 = Fehler der API oder Daten (Login, Statuscode, ETag-Konflikt nach Wiederholung, 409 fremde Chat-ID, 429 Ratebremse); 2 = Aufruf- oder Schutzfehler (Prod-URL, unzulässiges Loopback-Ziel, fehlende `.env`-Schlüssel inklusive Core-Secret und fehlender `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS`; Exit 2 erfolgt vor jedem Aufruf, auch wenn `GZ_AUTH_*` gesetzt ist).
10. **Danach (Hand-Arbeit):** Abgleich-Lauf gegen Staging, Auflösen oder Umhängen der `#2967`-Einträge, Zählwächter und Schließen von #3145 ⇒ Kind-Issue #3151.

## Expected Behavior

- **Input:** Staging-Basis-URL, Prüfkonto-Zugang (`GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS`) und Core-Secret aus der Staging-`.env`; Aufruf `uv run python scripts/staging_pruefkonto_mockupdaten.py` auf dem Staging-Host.
- **Output:** Prüfkonto enthält Trip, Vorlage, Orte, Vergleich und vier verbundene Kanäle mit Mockup-Daten; stdout nennt die zwei IDs; Exit 0; das Core-Secret erscheint nirgends.
- **Side effects:** Schreibzugriffe nur auf die festen eigenen IDs und das eigene Profil im Staging-Prüfkonto.

## Acceptance Criteria

- **AC-1:** Given ein leeres Prüfkonto auf Staging / When das Seed-Skript läuft / Then enthält das Konto den Trip „GR221 Mallorca“ mit den vier Mockup-Etappen (Namen, 7,8/8,4/6,9/8,4 km, 23.–26.02.2026), der Vorlage `alpen-trekking` und den Metrik-Ein/Aus-Flags des Mockups (cloud_total, sunshine, fresh_snow, snow_depth, dewpoint, humidity, pressure aus; wind_direction nicht im Briefing; die übrigen 13 an) in `metrics` und `ampel.metrics`.
  - Test: Kern-Test gegen Fake-Server-Zustand liest den Trip und die Wetterkonfiguration nach dem Lauf und vergleicht Etappen, Summen, Vorlage und jedes Flag mit den Mockup-Werten.

- **AC-2:** Given das Seed-Skript hat gelaufen / When die eigenen Vorlagen des Prüfkontos gelistet werden / Then gibt es genau eine eigene Vorlage „Mallorca Frühling“, die den Metrik-Stand des GR221-Trips trägt.
  - Test: Kern-Test listet die Vorlagen im Fake-Server und prüft Name, Anzahl und Inhalt.

- **AC-3:** Given ein leeres Prüfkonto / When das Seed-Skript läuft / Then gibt es den Orts-Vergleich „Münsterland“ mit den drei Orten Münster (60 m), Telgte (52 m) und Tecklenburg (235 m), Vorlage Allgemein und Morgen-Briefing 07:00, und `active_metrics` ist in Objektform gespeichert.
  - Test: Kern-Test liest Orte und Vergleich aus dem Fake-Server und prüft Namen, Höhen, Vorlage, Uhrzeit und Objektform.

- **AC-4:** Given das Seed-Skript ist bereits einmal erfolgreich gelaufen / When es ein zweites Mal läuft / Then bleibt der Zustand des Kontos unverändert (keine Dubletten, kein neuer Schreibzugriff mit anderem Ergebnis) und der Exit-Code ist 0.
  - Test: Kern-Test fährt den Lauf zweimal, vergleicht den Fake-Server-Zustand byte-gleich und zählt Datensätze je Art (genau 1 Trip, 1 Vergleich, 3 Orte, 1 Vorlage).

- **AC-5:** Given das Konto enthält zusätzlich fremde Datensätze (weitere Trips, Orte, Vergleiche, Vorlagen) und ein Datensatz mit einer Seed-ID hat bereits abweichende Zusatzfelder / When das Seed-Skript läuft / Then bleiben alle fremden Datensätze unverändert, und beim Seed-Datensatz werden nur die Soll-Felder überschrieben, die übrigen Felder bleiben erhalten (Read-Modify-Write, nie Replace).
  - Test: Kern-Test legt fremde Datensätze und einen Seed-Trip mit Zusatzfeld vorab in den Fake-Server und prüft nach dem Lauf, dass fremde Datensätze identisch sind und das Zusatzfeld erhalten blieb.

- **AC-6:** Given die konfigurierte Basis-URL zeigt auf Produktion oder einen unbekannten Host / When das Seed-Skript startet / Then bricht es mit Exit-Code ungleich 0 (2) ab, bevor es sich anmeldet, und es erfolgt kein einziger Schreibzugriff.
  - Test: Kern-Test mit Produktions-URL und mit unbekannter URL; der Fake-Transport zählt null Aufrufe, Exit ist 2.

- **AC-7:** Given verschiedene Ausgangslagen / When das Seed-Skript endet / Then ist der Exit-Code 0 bei erreichtem Soll-Zustand, 1 bei API-/Datenfehler (z. B. Login abgelehnt, 5xx) und 2 bei Schutz- oder Aufruffehler (Prod-URL, fehlende `.env`-Schlüssel, fehlender Prüfkonto-Schlüssel (auch wenn GZ_AUTH_* gesetzt ist)), und bei Exit 0 stehen `ELEMENTLISTE_TRIP_ID=` und `ELEMENTLISTE_ORTE_ID=` mit den echten IDs auf stdout.
  - Test: Kern-Test je Fall (Erfolg, Login-Fehler, 500 beim Anlegen, fehlender `.env`-Schlüssel, fehlender `GZ_PRUEFKONTO_USER` bzw. `GZ_PRUEFKONTO_PASS` bei gesetztem `GZ_AUTH_*`, Prod-URL) prüft Exit-Code und die beiden Ausgabezeilen; im Fall fehlender Prüfkonto-Schlüssel zählt der Fake-Transport null Aufrufe; die ausgegebenen IDs existieren im Fake-Server.

- AC-8, AC-9: verschoben nach #3151 (Live-Abgleich gegen Staging, Besitzerliste, Zählwächter; PO-Entscheid 2026-11-19).

- **AC-10:** Given der Fake-Server hält zwei Nutzerkonten mit eigenen Daten / When das Seed-Skript mit dem Login des Prüfkontos läuft / Then entstehen die Datensätze nur im Konto des eingeloggten Nutzers, und der zweite Nutzer behält seine Daten unverändert (nichts unter `"default"`).
  - Test: Kern-Test mit zwei Nutzern im Fake-Server; nach dem Lauf Vergleich beider Datenbestände, zweiter Nutzer identisch.

- **AC-11:** Given ein Prüfkonto ohne verbundene Kanäle und eine erreichbare Staging-Go-API auf dem Loopback-Port 8091 / When das Seed-Skript läuft / Then sind alle vier Kanäle wie im Mockup verbunden: E-Mail bestätigt mit zwei Empfängern, SMS bestätigt mit der fiktiven Testnummer, Telegram verbunden mit der fiktiven Chat-ID, Premium-SMS mit gelernter inReach-Rückadresse im Zustand „frisch“, der Tarif ist Premium und die Zähler `sms` und `premium_sms` stehen auf 0.
  - Test: Kern-Test liest das Profil im Fake-Server nach dem Lauf (Kanalstatus je Kanal, Empfängerzahl, Tarif, Zähler, Zustand der Rückadresse) und vergleicht mit den Mockup-Sollwerten aus `konto()`; zusätzlich prüft er, dass die interne Telegram- und Premium-SMS-Route den Core-Auth-Header trugen und ohne `X-Forwarded-*`/`X-Real-IP`-Header ankamen.

- **AC-12:** Given die konfigurierte Basis-URL zeigt auf Staging, aber das Ziel der internen Aufrufe ist der Prod-Port, die Prod-URL oder eine andere Adresse als `localhost:8091` / When das Seed-Skript startet / Then bricht es mit Exit 2 ab, bevor irgendein Kanal-Aufruf (auch Trockenlauf) gesendet wird, und der Fake-Transport verzeichnet keinen Aufruf an diese Ziele.
  - Test: Kern-Test mit Prod-Port, Prod-URL und fremdem Host als Loopback-Ziel; der Fake-Transport zählt null Aufrufe, Exit ist 2.

- **AC-13:** Given das Core-Secret steht in der Staging-`.env` / When das Seed-Skript läuft, auch bei einem Fehler wie 401, 409 oder 500 auf einer internen Route / Then erscheint das Secret weder auf stdout noch auf stderr, in keiner Fehlermeldung und in keinem Log; fehlt es in der `.env`, endet der Lauf mit Exit 2 vor dem ersten internen Aufruf.
  - Test: Kern-Test setzt ein erkennbares Testsecret, lässt Erfolg und Fehlerfälle laufen, sucht in stdout, stderr und Logs nach dem Wert (nie gefunden); Fall „Secret fehlt“ liefert Exit 2 ohne internen Aufruf.

- **AC-14:** Given die Kanäle sind bereits verbunden / When das Seed-Skript ein zweites Mal läuft / Then bleibt der Kanalzustand byte-gleich, es erfolgt kein erneutes Verbinden von Telegram, kein scharfer Premium-SMS-Aufruf und keine neue SMS-Bestätigung, und der Exit-Code ist 0; ein zweiter Lauf löst die Ratebremse der Premium-SMS-Verknüpfung nicht aus.
  - Test: Kern-Test fährt den Lauf zweimal, vergleicht den Nutzerzustand und zählt die scharfen Aufrufe auf `telegram-connect`, `premium-sms-learn` (ohne `dry_run`) und `sms/verify` im zweiten Lauf (0); der Zähler der Ratebremse im Fake bleibt unverändert.

- **AC-15:** Given der Fake-Server hält einen zweiten Nutzer, dessen Telegram-Chat-ID der des Prüfkontos entspricht, bzw. einen zweiten Nutzer mit eigener Premium-SMS-Rückadresse und eigenem Kanalzustand / When das Seed-Skript als Prüfkonto läuft / Then bleibt der zweite Nutzer mit allen Kanälen unverbunden bzw. unverändert, bei der Chat-ID-Kollision (409 `chat_id_already_linked`) endet der Lauf mit Exit 1, und im Konto des anderen Nutzers wird nichts überschrieben.
  - Test: Kern-Test mit zwei Nutzern im Fake-Server: (a) zweiter Nutzer ohne Kanäle bleibt nach dem Lauf unverbunden und unverändert, (b) Chat-ID-Kollision liefert Exit 1, beide Nutzerdatensätze sind danach identisch zum Vorzustand.

## Definition of Done

- Seed-Skript und Kern-Test liegen vor; alle Kern-Tests grün (AC-1 bis AC-7, AC-10 bis AC-15).
- Seed lief zweimal hintereinander gegen Staging mit Exit 0, der zweite Lauf hat nichts geändert (Wetter und Kanäle).
- Runbook für Seed und Abgleich liegt vor.
- Abgleich-Lauf, Besitzerliste, Zählwächter und Schließen von #3145 sind nicht Teil dieser Spec ⇒ #3151.

## Test Plan

### Automated Tests (TDD RED)

- [ ] GIVEN leerer Fake-Server WHEN Seed läuft THEN Trip, Etappen, Flags, Vorlage `alpen-trekking`, „Mallorca Frühling“, Orte und „Münsterland“ entsprechen den Mockup-Werten (AC-1 bis AC-3).
- [ ] GIVEN Seed lief schon WHEN zweiter Lauf THEN Zustand identisch, Datensatzzahlen je Art unverändert (AC-4).
- [ ] GIVEN fremde Datensätze und Seed-Trip mit Zusatzfeld WHEN Seed läuft THEN fremde unberührt, Zusatzfeld erhalten (AC-5).
- [ ] GIVEN Produktions- oder unbekannte URL WHEN Seed startet THEN Exit 2 und null Transportaufrufe (AC-6).
- [ ] GIVEN Erfolg, Login-Fehler, 500, fehlender `.env`-Schlüssel, fehlender `GZ_PRUEFKONTO_*`-Schlüssel bei gesetztem `GZ_AUTH_*` WHEN Seed endet THEN Exit 0/1/1/2/2 und IDs-Ausgabe nur bei Erfolg (AC-7).
- [ ] GIVEN zwei Nutzer im Fake-Server WHEN Seed als Nutzer A läuft THEN Nutzer B unverändert (AC-10).
- [ ] GIVEN Prüfkonto ohne Kanäle WHEN Seed läuft THEN E-Mail (2 Empfänger), SMS bestätigt, Telegram verbunden, Premium-SMS frisch, Tarif Premium, Zähler 0; interne Routen mit Core-Auth-Header und ohne Proxy-Header aufgerufen (AC-11).
- [ ] GIVEN Prod-Port, Prod-URL oder fremder Host als Loopback-Ziel WHEN Seed startet THEN Exit 2 und null Aufrufe (AC-12).
- [ ] GIVEN erkennbares Testsecret WHEN Erfolg und Fehlerfälle (401/409/500) THEN Secret nirgends in stdout/stderr/Log; Secret fehlt ⇒ Exit 2 (AC-13).
- [ ] GIVEN Kanäle schon verbunden WHEN zweiter Lauf THEN Zustand identisch, null scharfe Kanalaufrufe, Ratebremse unberührt (AC-14).
- [ ] GIVEN zweiter Nutzer unverbunden bzw. mit kollidierender Chat-ID WHEN Seed läuft THEN zweiter Nutzer unverändert; Kollision ⇒ Exit 1, nichts überschrieben (AC-15).

### Live-Lauf (E2E-Phase, nur Staging)

- [ ] Seed gegen Staging auf dem Staging-Host, Exit 0, zweimal hintereinander (Idempotenz), IDs notieren; Kanalstatus im Prüfkonto per Profilabruf kontrollieren (AC-11, AC-14).
- Abgleich-Lauf, Besitzerliste und Zählwächter: ⇒ #3151.

## Known Limitations

- **Echte Code-Abweichungen stehen bewusst weiter im Befund und werden nicht im Seed kaschiert:**
  - Reihenfolge „Nicht im Briefing“: Trip Luftfeuchte vor Taupunkt und Luftdruck nach Sonnenstunden (Rang `_REITER_WETTER`, `ampelModell.ts`), Orte: Gefühlte Temperatur zuerst.
  - Widerspruch Vorlage „allgemein“ (`temperature_night`/`thunder` in `metric_catalog.py` gegen `ampel_templates.py`).
  - Katalog-Vorlage `alpen-trekking` weicht vom Mockup ab (cloud_total aktiv, wind_direction fehlt); das sind keine Kontodaten.
  Jede bestätigte Abweichung bekommt nach Dublettenprüfung (#3122, #3111) ein Kind-Issue von #2913 (Zuordnung im Live-Abgleich: #3151).
- **Bewusst nicht auf die festen Mockup-Tage gesetzt:** Die Datumsangaben im Mockup-Text der Premium-SMS („Rückadresse gelernt 28.10. · zuletzt gemeldet 1.11. 18:04“) sind Beispielwerte. Ein fest eingetragenes Datum würde nach der 30-Tage-Frist (`internal/model/premium_sms.go`) den Zustand von „frisch“ auf „veraltet“ kippen lassen, das Prüfkonto wäre dann nicht mehr mockup-gleich. Der Seed lernt die Rückadresse deshalb bei jedem Lauf über den echten Weg (`premium-sms-learn`, Stempel = Laufzeitpunkt) und erreicht so verlässlich „gelernt, frisch“. Die Datumsstellen gehören nach Dublettenprüfung einem neuen Kind-Issue von #2913 („Mockup-Beispieldatum der Rückadresse ist dynamischer Wert, Abgleich soll Format statt Datum prüfen“). Das Mockup zeigt im Reiter Zustellung keinen Zählerstand; der Seed setzt die Zähler auf 0.
- Die Mockup-Adressen sind gekürzt („henning@…“, „+49 171 …“, „@henning“); der Seed nutzt fiktive, eindeutige Testwerte mit gleicher Form, die Kürzung entsteht in der Anzeige.
- Das Skript funktioniert nur auf dem Staging-Host (Loopback-Zugriff und `.env` mit Core-Secret und `GZ_PRUEFKONTO_*`); von einem anderen Rechner scheitert es bewusst vor dem ersten Schreibzugriff.
- Das Trip-Datum liegt in der Vergangenheit (Status „fertig“ wie im Mockup); zeigen Wetter- oder Zustellteile dann Zusatzhinweise, wird das als Abweichung zugeordnet, das Datum nicht verbogen.
- Das Skript ist ein Handwerkzeug für Staging und läuft nie in Produktion.

## Kein Cron, kein Heartbeat

Das Skript wird nur von Hand vor einem Abgleich-Lauf gestartet und ist nicht geplant. Es gibt keinen Cronjob und keinen Dauerdienst, daher keinen Heartbeat (Heartbeat-Pflicht gilt für Cronjobs/Scripts mit regelmäßigem Lauf).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Prüfwerkzeug für Staging-Testdaten; berührt keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Editor-Paradigma). Die Loopback-Aufrufe nutzen die bestehenden Schutzmechanismen (`requireLocalOnly`, `coreAuth`) unverändert und lockern sie nicht. Die Regel „Abgleich liest nur“ bleibt bestehen, Schreiben liegt im getrennten Seed-Skript.

## Changelog

- 2026-11-18: Initial spec created
- 2026-11-18: Kanäle zurück in den Umfang: #3145 in #2967 aufgenommen; Seed verbindet E-Mail, SMS, Telegram, Premium-SMS und setzt Tarif/Zähler per Loopback (localhost:8091, Core-Auth); neue AC-11 bis AC-15; AC-9, Definition of Done, Scope, Test Plan und Known Limitations angepasst
- 2026-11-19 (v1.2): PO-Entscheid: Live-Teil (AC-8, AC-9, Besitzerliste/Zählwächter, Schließen von #3145) als Kind-Issue #3151 von Epic #2913 abgespalten; Scope, Dependencies, Implementation Details, Definition of Done und Test Plan entsprechend gekürzt. Tech-Lead-Entscheid: Seed nutzt das eigene Staging-Prüfkonto `u-89f9fe2f` mit Zugang `GZ_PRUEFKONTO_USER`/`GZ_PRUEFKONTO_PASS` (nicht `GZ_AUTH_*`, das ist das Konto „default“); fehlt ein Schlüssel ⇒ Exit 2 vor jedem Aufruf (AC-7 ergänzt)
