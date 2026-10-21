# Context: feat-2439-staging-messtreiber

## Request Summary
Issue #2439 ist bis auf Messbelege fertig. Offen laut Kommentar 21.10.: die **Staging-Serien echter
Wetterbefehle** (Antwortzeit-AC-3/4/5/12 bzw. Prod-scharf-AC-12/AC-15). Die Live-Tests in
`tests/e2e/test_push_eingang_befehle_staging.py` werten nur das Staging-Journal aus und verlangen
einen **Treiber**, der die Befehlsserien auslöst und `GZ_STAGING_MESSLAUF_SEIT`,
`GZ_STAGING_TRIP_DE`, `GZ_STAGING_TRIP_KORSIKA` exportiert. Diesen Treiber gibt es nicht
(`grep GZ_STAGING_MESSLAUF_SEIT` trifft nur den Test selbst) — er ist Gegenstand dieses Workflows.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/e2e/test_push_eingang_befehle_staging.py` | Konsument des Treibers. Erwartet: ≥5 HELP/CODES/STATUS je Eingang E-Mail **und Telegram** (AC-3), ≥5 kalte HEUTE/MORGEN DE-Route mit mind. einem E-Mail-Lauf (AC-4), ≥3 kalte HEUTE/MORGEN Korsika (AC-5), HEUTE→HELP-Paar über E-Mail (AC-12), kein EOF (AC-14). Konstanten Z. 167–180. Env-Vertrag Z. 191–197, 256, 285. |
| `.claude/tools/staging_befehl_pruefen.py` (589 Z., #2542) | Vorhandener Baustein: Wegwerf-Nutzer `gregor-test+<tag>` registrieren, Test-Trip anlegen/löschen, Befehlsmail über Port 25 an `gregor-staging@henemm.com` einliefern, Antwort per IMAP finden, Poll auslösen (`loese_poll_aus`), Aufräumen. Szenarien `status|heute|verschiebung|alle`. Wiederverwendbare Funktionen: `baue_trip`, `baue_befehlsmail`, `liefere_ein`, `finde_antwort`, `_fahre_befehl`, `Api`-Klasse, `http_transport`. |
| `.claude/tools/befehl_messlogik.py` (111 Z.) | Reine Auswertung: `dauerzeilen`, `kalt_laeufe(quellen=…)`, `paare_heute_help`, `messung_ueberholt`. Treiber sollte **nicht** selbst auswerten, sondern das dem Test überlassen. |
| `.claude/tools/befehl_antwortzeit.py` (229 Z.) | Prod-Lese-Werkzeug (nur lesend) — Vorbild für Ausgabeform, nicht für Auslösen. |
| `docs/specs/modules/feat_2439_befehle_antwortzeit.md` | Zielgrößen AC-3/4/5/12/14; AC-4-Methode „kalt": Neustart `gregor-python-staging` **oder** Trip mit noch nie abgerufenem Datum. |
| `docs/specs/modules/feat_2439_push_eingang_prod_scharf.md` | AC-11/12/13/15, §9 Telegram-Festlegung (Telegram HEUTE/MORGEN auf Staging NOT_MEASURABLE, verwaistes Konto `e2ek71785826879`). |
| `src/providers/dwd.py`, `src/providers/meteofrance.py` | Schreiben die Kalt-Marker `dwd_fenster … downloads=N` bzw. `fr_direct_fenster … downloads=N`, an denen „kalt" erkannt wird. Cache-Schlüssel bestimmen, wie man Kälte ohne Neustart herbeiführt. |
| `scripts/telegram_set_webhook.sh`, Go `/api/webhooks/telegram/{secret}` | Möglicher Weg für Telegram-Befehle auf Staging (AC-3 verlangt Telegram ≥5). |

## Existing Patterns
- Staging-Prüfwerkzeuge liegen unter `.claude/tools/`, sind Python-Stdlib-only, CLI mit `argparse`,
  Exit 0/1/2 (bestanden / Befund / Umgebungsfehler), injizierbare Fabriken (`smtp_factory`,
  `imap_factory`, `transport`) für Kern-Tests ohne Netz.
- Mail-Befehle auf Staging nur über Wegwerf-Nutzer `gregor-test+…` (Memory: Hauptkonto schickt an
  gregor-staging@); Trips `gzp-<tag>-<szenario>`; Aufräumen am Ende.
- Kern-Tests des Werkzeugs: `tests/test_staging_befehl_pruefweg*.py` (Fabriken statt Mocks).

## Dependencies
- Upstream: Staging-API (Registrierung, Trip-Anlage), Kern-Port 8001 + `X-GZ-Core-Auth` für Poll-Auslöser,
  Stalwart Port 25 / IMAP (`GZ_IMAP_*`), Staging-`.env` unter `/home/hem/gregor_zwanzig_staging/.env`,
  `journalctl -u gregor-python-staging` (für `hem` lesbar, geprüft 21.10.).
- Downstream: die Live-Tests (`/e2e-verify`) und der Issue-Close von #2439.

## Existing Specs
- `docs/specs/modules/fix_2542_staging_befehl_pruefweg.md` — Prüfweg, den der Treiber erweitert
- die beiden 2439-Specs oben

## Risks & Considerations
- **Kälte ohne Neustart:** `hem` darf `gregor-python-staging` **nicht** neu starten (sudo nur nginx,
  `gregor_zwanzig`, `claude-mq`). Kalte Läufe müssen über neue Orte/Daten entstehen — Cache-Schlüssel der
  DWD-/fr_direct-Fenster klären (Koordinaten? Kalendertag?). Ohne das bleiben AC-4/AC-5 „nicht belegt".
- **Telegram auf Staging:** AC-3 fordert Telegram ≥5 je Befehl; Weg ist offen (Webhook-Update mit Secret
  an Staging simulieren? verwaistes Konto aus §9). In /20 klären, sonst ist der Test strukturell rot.
- **Keine Sammelläufe über fremde Trips**, nur eigene Test-Trips; Wegwerf-Nutzer am Ende löschen.
- 5×HEUTE + 5×MORGEN DE + 3+3 Korsika + 15 E-Mail-Kurzbefehle + Paar: Laufzeit und DWD-Last; Befehle
  seriell (Poll-Lock je Kanal, AC-12).
- Werkzeug unter `.claude/` ⇒ Tooling-Änderung, Deploy-Ausnahme greift; trotzdem Kern-Test für die
  Ablauflogik (Fabriken, kein Mock-Theater).

## Analysis

### Type
Feature (Tooling, `.claude/tools/` — Deploy-Ausnahme für reine Tooling-Änderungen greift).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/tools/staging_messlauf.py` | CREATE | Messtreiber: löst die Befehlsserien auf Staging aus, gibt am Ende `GZ_STAGING_MESSLAUF_SEIT`/`GZ_STAGING_TRIP_DE`/`GZ_STAGING_TRIP_KORSIKA` aus, wertet NICHT selbst aus. Stdlib-only, argparse, Exit 0/1/2. |
| `.claude/tools/staging_befehl_pruefen.py` | MODIFY (klein) | `baue_trip` rückwärtskompatibel um Ort/Region parametrisieren (heute fest 47.10/11.00); sonst nur Wiederverwendung (`StagingApi`, `baue_befehlsmail`, `liefere_ein`, `finde_antwort`, `_fahre_befehl`, `loese_poll_aus`). |
| `tests/tdd/test_staging_messlauf.py` | CREATE | Kern-Test der Ablauflogik mit Ersatzklassen/Fabriken nach Vorbild `tests/tdd/test_staging_befehl_pruefweg.py` (kein `Mock()`). |
| `docs/…` Runbook-Abschnitt #2439 | MODIFY | Aufruf, Laufzeit, Messvorbehalt Telegram. |

`tests/e2e/test_push_eingang_befehle_staging.py` bleibt unverändert (Konsument).

### Gesicherte Fakten (mit Beleg)
- **Dauerzeile:** `befehl=%s kanal=%s trip=%s dauer_ms=%d`, `trip` = **Trip-ID** (`src/services/trip_command_processor.py:1050-1054`) ⇒ Export der Trip-ID passt zum Test-Filter.
- **Testvertrag** (`tests/e2e/test_push_eingang_befehle_staging.py`): Gate `GZ_STAGING_E2E=1`; Pflicht-Env `GZ_STAGING_STATUS_TOKEN`, `GZ_STAGING_MESSLAUF_SEIT` (ISO UTC → `journalctl --since`), `GZ_STAGING_TRIP_KORSIKA`; optional `GZ_STAGING_TRIP_DE`. Schwellen Z. 172-180 (30 s / 60 s / Median 45 s / ≥5 / ≥5 / ≥3 / HELP ≤30 s nach HEUTE / Paar-Fenster 300 s).
- **AC-3** verlangt ≥5 HELP/CODES/STATUS je Eingang **email UND telegram** (Z. 230-244); premium_sms NOT_MEASURABLE. **AC-4** Telegram HEUTE/MORGEN NOT_MEASURABLE (Spec §9), E-Mail Pflicht mind. 1 kalter Lauf.
- **„kalt“** = `dwd_fenster|fr_direct_fenster … downloads>0` im Befehlsfenster (`.claude/tools/befehl_messlogik.py:70-86`).
- **DWD-Cache** (`src/providers/dwd.py` ~318-460, Limits 332-334): prozessweit RAM, LRU, keine TTL, Schlüssel URL (Lauf+Parameter+Zeitschritt), Ausschnitte 41×41 px ≈ 90 km. Neuer Ort außerhalb aller Ausschnitte ⇒ Download.
- **Météo-France-Cache** (`thunder_window_cache.py`): TTL 600 s, Schlüssel bbox auf 2°-Kachel (`meteofrance.py:179`). Korsika ≈ eine Kachel ⇒ Kälte nur über >600 s Abstand.
- **Neustart von `gregor-python-staging` ist für `hem` nicht erlaubt.**
- **Trip-Kontingent free=3** je Nutzer.
- **Staging-Ports:** Go-API **8091** (`gregor-api-staging`, `GZ_PORT=8091`), Kern **8001**. **8090 = Prod — niemals ansprechen.**
- **Telegram-Eingang:** nur Webhook (Polling entfernt #1369). Go `internal/handler/telegram_webhook.go:42-91` prüft Header `X-Telegram-Bot-Api-Secret-Token` gegen `TELEGRAM_WEBHOOK_SECRET` (in Staging-`.env` vorhanden), Python `api/routers/webhook.py:72-90` prüft erneut und dedupliziert nach `update_id`. Unbekannte `chat_id` ⇒ nur Registrierungs-Hinweis, **keine** Dauerzeile. Chat-ID-Verknüpfung: Link-Token (`GetTelegramLinkHandler`, router.go:152, Nutzer-Session) + `POST /api/internal/telegram-connect` (router.go:155: `coreAuth` **und** `requireLocalOnly`, d. h. direkt `127.0.0.1:8091` ohne Proxy-Header, mit `X-GZ-Core-Auth`) — alternativ `/start TOKEN` als simuliertes Update. Antwortversand an echte Telegram-API, Fehler verschluckt (`notification_service.py:2172-2189`).
- **Simulierte Webhook-Updates sind im Projekt etabliertes Muster** (`tests/tdd/_befehl_e2e_fixtures.py:155ff`: Webhook-Post mit eigener `telegram_chat_id` je Fixture-Nutzer). Einen anderen „echten“ Eingang gibt es nicht — auch in Produktion postet Telegram genau diesen Webhook.

### Scope Assessment
- Files: 3 Code/Test + 1 Doku
- Estimated LoC: +600…700 (Werkzeug ~400, Test ~250, `baue_trip` ~20) ⇒ **`loc_limit_override 700` in der Spec ankündigen**
- Risk Level: **MEDIUM** — kein Produktcode, aber Live-Lauf gegen Staging (Last, Aufräumen, Kontingent) und zwei unverifizierte Annahmen (Telegram-Verknüpfung, Kälte bei HEUTE/MORGEN).

### Technical Approach (Empfehlung)
Neues Werkzeug `.claude/tools/staging_messlauf.py`, importiert `staging_befehl_pruefen.py`. Ein Wegwerf-Nutzer `gzp-<tag>`, genau **zwei Trips** (DE, Korsika) — Kontingent 2/3. Alles seriell.

| Variante Kälte DE | Laufzeit | Zuverlässigkeit | Bewertung |
|---|---|---|---|
| **A: ein Trip, vor jedem Lauf per Read-Modify-Write (`PUT /api/trips/{id}`) die Etappen für heute UND morgen auf einen neuen DE/Alpen-Ort setzen; 10 Orte paarweise ≥120 km, alle im `dwd_fenster`-Gebiet** | ~10 × 1-3 min | hoch | **empfohlen** |
| B: auf neuen 3h-Modelllauf warten | bis 30 h | mittel | unpraktikabel |
| C: 10 Trips | – | – | scheitert am Kontingent 3 |
| D: Neustart Kern | Sekunden | sehr hoch | für `hem` verboten |

Korsika: Variante E — gleicher Trip, Abstand >600 s zwischen den Läufen, 6 Läufe ≈ 70 min.

Ablauf:
1. **Probelauf (eigene AC, vor der Serie):** je 1× HEUTE + 1× MORGEN DE und 1× Korsika, dann Journal auf `downloads>0` prüfen. Bleibt ein Lauf warm ⇒ Abbruch mit Befund (Exit 1), keine Serie.
2. E-Mail-Kurzbefehle: 5× HELP/CODES/STATUS.
3. Telegram-Kurzbefehle: Verknüpfung über erkennbar ungültige, eindeutige `chat_id` (kein Zufallswert, der einen echten Kontakt treffen kann), eindeutige `update_id`s; 5× HELP/CODES/STATUS als simulierte Webhook-Updates. **Messvorbehalt** dokumentieren: gemessen wird Verarbeitung + schneller Sendefehler statt echter Zustellung.
4. DE kalt: 5× HEUTE + 5× MORGEN, mind. einer per E-Mail (praktisch alle per E-Mail, Telegram HEUTE/MORGEN zählt dort nicht).
5. Korsika: 3× HEUTE + 3× MORGEN mit >600 s Abstand.
6. AC-12-Paar: HELP-Mail wird **eingeliefert, solange HEUTE noch läuft** (nicht erst nach der HEUTE-Antwort warten), gleicher Kanal E-Mail.
7. Ausgabe der drei Env-Werte; Aufräumen im `finally` (beide Trips + Nutzer, auch bei Abbruch; der bestehende Prüfweg löscht Trips nicht im `finally` — hier korrigieren).

### Dependencies
Upstream: Staging-API (8091 / öffentliche URL), Kern 8001 + `X-GZ-Core-Auth`, Stalwart Port 25 + IMAP (`GZ_TEST_IMAP_*`), Staging-`.env` (`TELEGRAM_WEBHOOK_SECRET`, `GZ_CORE_SHARED_SECRET`), `GZ_AUTH_USER/PASS` (Helfer-Konto für Registrierung). Downstream: `tests/e2e/test_push_eingang_befehle_staging.py`, `/e2e-verify`, Close von #2439.

### Risiken & Spikes (technisch, keine PO-Frage)
- **Telegram-Verknüpfung** (Link-Token + `telegram-connect` auf 8091 bzw. `/start TOKEN`) ist nur aus dem Code gelesen ⇒ Spike in /50; scheitert er, bleibt AC-3-Telegram mit Begründung offen (ehrlich im Issue, nicht schöngefärbt).
- **Kälte HEUTE/MORGEN:** Welche Etappe MORGEN lädt und ob sich Zeitschritte mit HEUTE überschneiden, ist unverifiziert ⇒ Probelauf (Schritt 1) ist Pflicht.
- **Fremdlast auf Staging** kann Orte ungewollt wärmen ⇒ Orte abseits der Staging-Test-Trips wählen; Probelauf zeigt es.
- **Laufzeit 2-2,5 h:** Start so legen, dass Ortszeit-Sperre 23:45-00:15 (Europe/Vienna) und ein Tageswechsel am Trip-Ort nicht hineinfallen; Werkzeug prüft das vor dem Start.
- **DWD-Last:** ~415 Dateien je kaltem Lauf ⇒ strikt seriell.

### Open Questions
- keine an den PO; technische Spikes oben gehen in Spec (ACs) bzw. /50.

## Übergabe aus /40 (TDD RED, 2026-10-21) — Pflichtlektüre für /50

Vertrag steht im Docstring von `tests/tdd/test_staging_messlauf.py` (`main(argv, *, env, transport, helfer_transport, smtp_factory, imap_factory, journal_quelle, uhr, schlaf, laufzeit)`; `baue_trip(..., *, ort=(lat, lon))`; `CHAT_ID_PRAEFIX="gzp-ungueltig-"`).

Aus dem Code ermittelte Randbedingungen:
- Kalt-Marker: `dwd_fenster fenster_s=… downloads=N cache_treffer=…` (`src/providers/dwd.py:893`), `fr_direct_fenster …` (`src/providers/meteofrance.py:704`). DWD-Gebiet = `thunder_routing.py:73-76` (erster Treffer DE_ALPEN, FR-Rechteck ausgenommen); Tests prüfen `thunder_provider_for(...)`.
- Dauerzeile `trip=` trägt die Trip-ID (`trip_command_processor.py:1053/1108`).
- Webhook `POST /api/webhooks/telegram/{secret}` — nur Header geprüft, Go antwortet immer 200; Dedup nach `update_id` (`api/routers/webhook.py:82`); `chat_id` als String gelesen.
- `telegram-connect` nur lokal (403 über Proxy, `localhost_guard.go:38-46`) ⇒ über öffentliche URL nur `/start TOKEN`; Bestätigung über `GET /api/auth/telegram-status` (`connected`).
- `chat_id` bewusst nicht-numerisch (negative IDs = echte Telegram-Gruppen).
- Trip ändern: `GET /api/trips/{id}` + `PUT` (PUT ersetzt `stages` komplett) ⇒ Read-Modify-Write über ganze Etappenliste.
- Poll läuft synchron unter Lock (`api/routers/scheduler.py:197-215`) ⇒ AC-7-HELP VOR dem Poll für HEUTE einliefern.
- Fortschritt nach **stderr** (AC-9/AC-16); Bestands-Helfer `_fahre_befehl`/`_fahre_szenario`/`_raeume_auf` drucken nach stdout — nicht ungeändert nutzen.
- Abgeleitete Regel: außer dem AC-7-Paar folgt auf ein E-Mail-HEUTE nie direkt ein E-Mail-HELP (`paare_heute_help` paart ohne Trip-Filter); Test verlangt genau ein Paar auf dem DE-Trip.
- AC-11: 22:30 bei 2–2,5 h Laufzeit gesperrt (AC-Text vor Testplan-Beispiel).
- Bekannte Testgrenze: Mutation 600→599 s wird nicht gefangen (keine Obergrenze in der Spec) ⇒ Adversary-Punkt.
