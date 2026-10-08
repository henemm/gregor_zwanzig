---
entity_id: fix_2124_versand_nginx_timeout
type: module
created: 2026-10-07
updated: 2026-10-07
status: draft
version: "1.0"
tags: [bug, versand, nginx, timeout, mandantenfaehigkeit, trip-compare-teilung]
---

# Trip-/Ortsvergleich-Versand ohne 60-s-Abbruch durch nginx (Issue #2124)

## Approval

- [ ] Approved

## Purpose

Der manuelle Versand (Trip-Briefing und Ortsvergleich-Briefing) dauert bis zu mehreren Minuten. nginx bricht
nach seinem Default von 60 s ab, die Go-API meldet 502, die Oberflaeche zeigt "Versand fehlgeschlagen" —
obwohl der Python-Core das Briefing vollstaendig zustellt. Diese Spec bringt die Zeitgrenzen aller Schichten
in eine widerspruchsfreie Reihenfolge (Python-Lauf < Go-Client 300 s < nginx 330 s), entkoppelt den
Upstream-Request vom Client-Abbruch, schuetzt den Ortsvergleich-Versand wie den Trip-Versand mit einem
Lauf-Lock und sorgt dafuer, dass die Oberflaeche bei Zeitueberschreitung nie "fehlgeschlagen" behauptet,
wenn das Ergebnis tatsaechlich unklar ist.

## Hintergrund (Beweislage)

Gelesen am 2026-10-07 aus Prod-Logs und `briefing_log.json`, Details in
`docs/context/fix-2124-versand-nginx-timeout.md`.

- Fall Prod 30.08.2026 (KHW 403): ein einziger `POST /api/trips/5f534011/send?report_type=evening` aus der
  GUI (19:31:45, nach 60,04 s mit 502 beantwortet); Python hat genau einmal erzeugt und einmal zugestellt
  (19:34:57, vier Kanaele, Dauer 3 min 12 s).
- Der im Issue behauptete **Doppelversand "durch Nachdruecken" ist fuer den 30.08. NICHT belegt**: die GUI
  loeste genau einen Versand aus, es gab kein Nachdruecken und kein 409. Zwei weitere `briefing_log`-Eintraege
  (19:33:23 `["email"]`, 19:36:37 `["email","telegram"]`) haben keine Entsprechung im `gregor-python`-Journal;
  ihre Herkunft ist ungeklaert (wahrscheinlich, aber nicht belegt: parallele Einmal-Versaende einer anderen
  Sitzung). Der Nebenbefund "briefing_log nur `["email"]`" ist **nicht Teil dieses Fixes** (gebucht in #1199).
- Der Doppelversand bleibt daher ein **strukturelles Risiko**: die Fehleranzeige verleitet zum Nachdruecken,
  Trip-Liste und Dialog haben keinen Laufzustands-Schutz, der Compare-Versand hat keinen Lock.
- Zusatzbefund: `GET .../stages/weather` 19:22:26 -> 502 nach 60,0 s (Go-Client 60 s == nginx 60 s).
- Kein CDN/Zwischenproxy: beide Hosts loesen direkt auf den Server auf.

## Entscheidung (kein ADR)

**Synchron bleiben (Option A), Linie von #1756** (`docs/specs/modules/fix_1756_send_idempotenz_lock.md`:
Async/Poll "Option B" abgelehnt, nginx-Anhebung als Follow-up empfohlen und nie umgesetzt). Async mit
Job-Store, Status-Poll und Mandanten-Isolation braeuchte ADR und >= 500 LoC und brachte fuer AC-1..3
keinen Mehrwert. Keine der in CLAUDE.md gelisteten Entscheidungsflaechen wird geaendert. Die ADR-Pruefung
(`docs/adr/README.md`) ist damit abgeschlossen: Abweichung von keinem ADR.

## Source

- **File:** `internal/handler/proxy.go`, `internal/handler/compare_preset.go`, `src/services/scheduler_dispatch_service.py`, `frontend/src/lib/utils/sendOutcome.ts` (neu), `/home/hem/henemm-infra/nginx/*.conf`
- **Identifier:** `SendTripReportProxyHandler`, `SendComparePresetHandler`, `send_compare_preset`, `classifySendResponse`

> **Schicht-Hinweis:** Alle vier Schichten betroffen.
> - **Infra (henemm-infra)** -> `nginx/gregor20.henemm.com.conf`, `nginx/staging.gregor20.henemm.com.conf`
> - **Go-API** -> `internal/handler/proxy.go`, `internal/handler/compare_preset.go`
> - **Python-Core** -> `src/services/send_lock.py` (neu, geteilter Helfer), `src/services/trip_report_scheduler.py`, `src/services/scheduler_dispatch_service.py`, `api/routers/scheduler.py`
> - **Frontend** -> `frontend/src/lib/utils/sendOutcome.ts` (neu), sechs Auslöser (siehe Scope)

## Estimated Scope

- **LoC:** ca. +230/-40 im Gregor-Repo (`loc_limit_override 500` gesetzt), plus 2 Zeilen je vhost in henemm-infra
- **Files:** ca. 12 im Gregor-Repo (inkl. Tests), 2 in henemm-infra
- **Effort:** medium
- **Nicht in Scheiben aufteilen:** Trip/Compare-Paritaet gehoert in dieses Ticket.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| nginx (henemm-infra, `location /api/`) | infra | Reverse-Proxy vor der Go-API; muss laenger warten als der laengste Go-Sende-Timeout |
| `context.WithoutCancel` (Go 1.21+, Projekt auf Go 1.25) | stdlib | Upstream-Request vom Client-Abbruch entkoppeln |
| `http.Client.Timeout` | stdlib | bleibt als obere Grenze bestehen; `WithoutCancel` ist nicht "unbegrenzt" |
| `threading.Lock` | stdlib | Prozess-lokaler Lock-Guard im neuen geteilten Helfer |
| `src/services/trip_report_scheduler.py:397-416` | internal | Bestehender #1756-Lock; wird in den geteilten Helfer ausgelagert (Namen bleiben importierbar) |
| `src/services/scheduler_dispatch_service.send_compare_preset` | internal | Compare-Versand, bekommt den Lock |
| `api/routers/scheduler.py` (`manual_send_compare_preset`) | internal | 409-Mapping fuer Compare |
| `frontend/src/lib/utils/tripStatus.ts`, `frontend/src/routes/trips/tripListSend.ts` | internal | Bestehender Nachbar des neuen Moduls bzw. Trip-Listen-Versand; `tripListSend.ts` wird auf das geteilte Modul umgestellt |
| `fix_1756_send_idempotenz_lock` | spec | Vorlage fuer Lock, 409 und Timeout-Linie |
| `.claude/hooks/briefing_mail_validator.py` | tooling | Mail-Pruefung des Staging-Beweises |

## Implementation Details

### 1. nginx (henemm-infra, ZUERST ausrollen)

In `location /api/` beider vhosts (`nginx/gregor20.henemm.com.conf`, `nginx/staging.gregor20.henemm.com.conf`):
`proxy_read_timeout 330s;` und `proxy_send_timeout 330s;`, mit Kommentar, der auf die Go-Konstante
`sendProxyTimeout` (300 s, `internal/handler/proxy.go`) verweist (330 s = 300 s + 30 s Puffer). Global auf
`/api/` statt Einzelrouten: deckt auch `stages/weather` und `notify/test` ab; jede Route ist ohnehin durch ihren
Go-Client-Timeout begrenzt.

**Ausrollweg (verbindlich):** `/etc/nginx/sites-enabled/*` sind Symlinks auf `/etc/nginx/sites-available/`,
NICHT auf henemm-infra; `auto-deploy-infra.sh` rollt nginx NICHT aus. Die Sitzung hat passwortloses sudo fuer
`nginx` und `systemctl reload nginx` und fuehrt selbst aus (kein PO-Handgriff):

1. Quelle in henemm-infra auf eigenem Branch aendern (nicht im Arbeitsbaum von `main` — dort sofort live).
2. Staging: alte `sites-available/staging.gregor20.henemm.com.conf` sichern (Kopie mit Zeitstempel im
   Scratchpad), neue Datei nach `sites-available` uebernehmen, `sudo nginx -t`, `sudo systemctl reload nginx`,
   Smoke (`/` -> 200/302, `/api/health` -> 200).
3. Danach Prod gleich (`gregor20.henemm.com.conf`), gleiche Schritte.
4. Infra-PR: `gh pr create -R henemm/henemm-infra`. **Merge des Infra-PR macht der PO per Einmal-Skript**
   (der Auto-Mode-Klassifikator lasst einen Infra-Merge aus einer Gregor-Sitzung nicht zu).
5. **Reihenfolge:** nginx/infra zuerst, dann der Gregor-PR.
6. **Rollback:** gesicherte alte Datei zurueck nach `sites-available`, `sudo nginx -t`, `sudo systemctl reload nginx`.

### 2. Go (`internal/handler/proxy.go`, `internal/handler/compare_preset.go`)

- Eine gemeinsame Konstante `sendProxyTimeout = 300 * time.Second` (Compare: 120 s -> 300 s) und eine
  dokumentierte Konstante `nginxProxyReadTimeout = 330 * time.Second` (Spiegel der vhost-Zeile, Kommentar
  verweist auf henemm-infra).
- `SendTripReportProxyHandler` und `SendComparePresetHandler` bauen den Upstream-Request mit
  `http.NewRequestWithContext(context.WithoutCancel(r.Context()), ...)`. Ein Abbruch durch Browser, nginx
  oder Tab-Schliessen verwandelt den Versand dadurch nicht mehr in ein 502; der begrenzte `http.Client.Timeout`
  bleibt die obere Grenze.
- **Wetterabruf (`StagesWeatherProxyHandler`, `GET /api/trips/{id}/stages/weather`):** das Issue nennt ihn
  ausdruecklich als betroffen (30.08.: 502 nach 60,0 s). Nach der nginx-Aenderung waere sein eigener
  Go-Client-Timeout von 60 s die naechste Wand. Er wird daher auf eine benannte Konstante
  `stagesWeatherProxyTimeout = 120 * time.Second` angehoben (gleiches Niveau wie die uebrigen 120-s-Proxies,
  deutlich unter der nginx-Grenze). Der Aufruf bleibt ein Lesezugriff ohne Seiteneffekt; eine Entkopplung vom
  Client-Context ist dort nicht noetig.
- Die uebrigen Proxy-Timeouts (60 s / 120 s / 300 s) bleiben unveraendert; ein Test haelt sie unter der
  nginx-Grenze.

### 3. Python: geteilter Lock-Helfer

- Neues Modul `src/services/send_lock.py`: `try_acquire_send_lock(*key_parts)`, `release_send_lock(*key_parts)`
  (modulweites Register + Guard, identische Semantik wie #1756). Der Schluessel enthaelt IMMER `user_id`
  als erstes Element.
- `trip_report_scheduler.py` importiert den Helfer; die Namen `_try_acquire_send_lock`/`_release_send_lock`
  bleiben als duenne Huellen erhalten (bestehende Tests aus #1756 bleiben gueltig). Keine Kopie der Logik.
- `scheduler_dispatch_service.send_compare_preset` klammert den Versand mit Schluessel
  `("compare", user_id, preset_id)`, Freigabe in `finally`. Kollision -> Outcome `already_in_progress`;
  `api/routers/scheduler.py` (`manual_send_compare_preset`) mappt auf HTTP 409 mit sprechendem Detail.
  Wirkt nur im Einzelprozess (wie #1756, Known Limitations dort gelten unveraendert).

### 4. Frontend: EIN geteiltes Modul

Neu: `frontend/src/lib/utils/sendOutcome.ts` (neben `tripStatus.ts`; reine Logik, per `node --test`
pruefbar). Es liefert
(a) einen Laufzustand je Schluessel (z. B. `trip:<id>`, `compare:<id>`) als kleinen Store: `beginSend(key)` gibt
`false` zurueck, wenn fuer diesen Schluessel schon ein Versand laeuft; `endSend(key)`;
(b) `classifySendResponse(status | Netzfehler)` mit festen Texten (sachlich, nur Daten, keine Handlungsempfehlung
ausser dem Hinweis auf den laufenden Zustand):

| Eingang | Klasse | Anzeige |
|---|---|---|
| 2xx | `ok` | tatsaechliches Ergebnis des Versands |
| 409 | `already_running` | "Versand laeuft bereits" |
| 502 / 503 / 504 / Netzfehler | `unclear` | "Ergebnis unklar — Versand kann noch laufen, nicht erneut senden" (504 kommt von nginx, solange nginx noch nicht ausgerollt ist) |
| uebrige 4xx | `rejected` | bestehende Backend-`detail`-Meldung |
| uebrige 5xx | `failed` | bestehende generische Fehlermeldung |

**Alle** Ausloeser nutzen dieses Modul — keine Compare-eigene Kopie (Trip/Compare-Teilung):
`routes/trips/[id]/+page.svelte` (`handleTestBriefing`), `routes/trips/+page.svelte` + `trips/tripListSend.ts`,
`lib/components/molecules/TestReportDialog.svelte`, `lib/components/compare/CompareTabs.svelte`,
`routes/compare/[id]/+page.svelte`, `routes/compare/+page.svelte`.

**Kein neuer Client-Timeout und kein `AbortController` unter 330 s** (der Vorschlag "30 s Hard-Timeout" ist
verworfen).

**TestReportDialog (Entscheidung):** Der Dialog bleibt waehrend `running` schliessbar, aber der Ausloeser fuer
denselben Trip bleibt gesperrt (ueber den geteilten Laufzustand, auch nach erneutem Oeffnen und aus der
Trip-Liste), solange der Versand laeuft. Ein bewusster zweiter Versand NACH Abschluss bleibt erlaubt.

## Expected Behavior

- **Input:** manueller Versand (Trip oder Ortsvergleich), Dauer 60 s bis 300 s.
- **Output:** die Oberflaeche zeigt das tatsaechliche Ergebnis (2xx) statt "fehlgeschlagen"; es wird genau
  ein Briefing zugestellt.
- **Side effects:** nginx wartet bis 330 s; ein Client-Abbruch bricht den Upstream-Lauf nicht ab; waehrend
  eines laufenden Versands liefert ein zweiter Versuch fuer denselben Nutzer + Trip/Preset 409 bzw. wird
  in der Oberflaeche gar nicht erst abgeschickt.

## Acceptance Criteria

Mapping: AC-1 und AC-2 decken Issue-AC-1; AC-3 bis AC-5 decken Issue-AC-2 (kein Doppelversand);
AC-6, AC-7 und AC-9 decken Issue-AC-3 (Zeitgrenzen widersprechen sich nicht; AC-9 = im Issue genannter
Wetterabruf); AC-8 ist die Mandantentrennung.

- **AC-1 (Issue-AC-1):** Given der Browser oder nginx bricht die Verbindung ab, waehrend der Python-Upstream eines Trip- oder Ortsvergleich-Versands noch laeuft / When der Go-Handler den Upstream-Request ausfuehrt / Then wird der Upstream-Request nicht abgebrochen und laeuft zu Ende, statt in ein 502 `upstream unreachable` zu muenden.
  - Test: Go-Test mit echtem `httptest`-Upstream, der verzoegert antwortet und einen Abschluss-Marker setzt; der Client-Context wird mitten im Lauf abgebrochen; Marker muss gesetzt werden und der Upstream-Request-Context darf nicht `Canceled` sein. Fuer beide Handler (Trip und Compare). RED vor Fix: Request wird abgebrochen.

- **AC-2 (Issue-AC-1):** Given der Versand dauert laenger als 60 s und der Server antwortet mit 2xx / When die Oberflaeche die Antwort verarbeitet / Then zeigt sie das tatsaechliche Ergebnis und keine Fehlermeldung; bei 502, 503, 504 oder Netzfehler zeigt sie "Ergebnis unklar — Versand kann noch laufen, nicht erneut senden" statt "fehlgeschlagen".
  - Test: `node --test` fuer `sendOutcome.ts` mit den Eingaengen 200, 409, 502, 503, 504, Netzfehler, 422, 500; Tabelle aus "Implementation Details" ist die Erwartung. RED vor Fix: Modul existiert nicht, Trip-Detail zeigt bei 5xx "fehlgeschlagen".

- **AC-3 (Issue-AC-2):** Given ein Trip-Versand oder Ortsvergleich-Versand laeuft in der Oberflaeche / When der Nutzer denselben Versand aus irgendeinem Ausloeser (Trip-Detail, Trip-Liste, Dialog, drei Compare-Stellen) erneut anstossen will / Then wird kein zweiter Request abgeschickt, solange der erste laeuft; nach Abschluss ist ein bewusster neuer Versand wieder moeglich.
  - Test: `node --test` fuer den Laufzustand in `sendOutcome.ts` (`beginSend` zweimal -> zweites `false`; nach `endSend` wieder `true`; zwei verschiedene Schluessel blockieren einander nicht); zusaetzlich Verdrahtungsnachweis, dass jeder der sechs Ausloeser das Modul tatsaechlich nutzt (SSR-/Komponententest bzw. Playwright als Zusatz, nicht einziger Beweis, da E2E nicht in der CI-Ampel ist).

- **AC-4 (Issue-AC-2):** Given der Dialog "Testbriefing" ist waehrend eines laufenden Versands geschlossen und wieder geoeffnet / When der Nutzer fuer denselben Trip erneut "senden" ausloest / Then bleibt der Ausloeser gesperrt, bis der erste Versand beendet ist; der Dialog selbst bleibt waehrend des Laufs schliessbar.
  - Test: Frontend-Test auf Zustandsebene (`node --test`): Laufzustand ueberlebt Schliessen/Oeffnen des Dialogs, weil er im geteilten Modul und nicht in der Dialog-Instanz liegt.

- **AC-5 (Issue-AC-2):** Given ein Ortsvergleich-Versand fuer Nutzer X und Preset P laeuft bereits / When ein zweiter Versand fuer X und P eintrifft / Then liefert der Python-Core HTTP 409 mit sprechendem Detail, ohne einen zweiten Versand auszuloesen; nach Abschluss (auch nach Exception) ist ein neuer Versand wieder moeglich.
  - Test: pytest gegen `send_compare_preset` und den Router (Versandschicht als Zaehler, keine Selbstbestaetigungs-Mocks): zweiter Aufruf waehrend des ersten -> 409, Zaehler = 1; nach Exception im ersten Aufruf ist der Lock frei. Dateiname nach Verhalten, z. B. `tests/tdd/test_compare_send_lock.py`. Geteilter Helfer: ein Test belegt, dass Trip- und Compare-Lock dasselbe Modul `send_lock` nutzen (Schluesselraeume getrennt).

- **AC-6 (Issue-AC-3):** Given alle Go-Proxy-Handler mit `http.Client.Timeout` / When die Timeout-Konstanten gegen die dokumentierte nginx-Grenze (330 s, eigene Konstante) geprueft werden / Then ist jeder Proxy-Timeout kleiner als die nginx-Grenze, und der Trip- und der Compare-Sende-Handler verwenden dieselbe Konstante 300 s.
  - Test: Go-Test, der die Timeouts aller Handler (ueber die Konstanten bzw. ueber Handler-Aufruf mit Upstream-Verzoegerung) gegen `nginxProxyReadTimeout` prueft. **Ehrlich:** dieser Test schuetzt nur die Go-Seite — eine geloeschte vhost-Zeile macht ihn nicht rot. Den echten Beweis liefert AC-7.

- **AC-7 (Issue-AC-3):** Given nginx ist mit `proxy_read_timeout 330s` ausgerollt / When auf Staging ein echter Trip-Versand ueber `https://staging.gregor20.henemm.com` laenger als 60 s dauert / Then antwortet er mit 200 (Go-Access-Log) statt 502/504 und es wird genau eine Mail zugestellt.
  - Test: Staging-Verifikation, zwei Teile. (a) Konfig-Nachweis: `sudo nginx -T | grep -E "proxy_(read|send)_timeout"` zeigt je vhost 330 s in `location /api/`. (b) Verhalten: Wegwerf-Nutzer `gregor-test+…` mit einem Trip aus vielen Etappen und Mehrtages-Ausblick (Versandlaufzeit nach Erfahrung 20–84 s regulaer, 3 min 12 s im Fall 30.08.; Ziel: verlaesslich > 60 s); Versand ueber die Staging-Domain, Dauer und Statuscode aus dem Go-Access-Log, zugestellte Mail mit `briefing_mail_validator.py` (Exit 0). Dauert der Versand < 60 s, lautet das Ergebnis `NOT_MEASURABLE`, niemals PASS.

- **AC-8 (Mandantentrennung):** Given zwei verschiedene Nutzer senden gleichzeitig mit derselben Preset-ID einen Ortsvergleich-Versand / When beide Versaende parallel laufen / Then bekommt keiner von beiden 409 und beide werden zugestellt (Lock-Schluessel enthaelt die `user_id`).
  - Test: pytest mit zwei Nutzern (`user_x`, `user_y`), identischer `preset_id`, beide Aufrufe verschraenkt (Barriere im Versandzaehler); beide liefern ihr eigenes Ergebnis, kein `already_in_progress`. Analog zu AC-5 aus #1756. Pflicht-Zwei-Nutzer-Test laut CLAUDE.md.

- **AC-9 (Issue-AC-3, Wetterabruf):** Given der Python-Upstream fuer `GET /api/trips/{id}/stages/weather` braucht laenger als 60 s, aber weniger als 120 s / When die Go-API den Abruf weiterleitet / Then wartet sie bis zu 120 s auf die Antwort statt nach 60 s mit 502 abzubrechen, und diese Grenze liegt unter der nginx-Grenze von 330 s.
  - Test: Go-Test im selben Timeout-Ketten-Test wie AC-6: `StagesWeatherProxyHandler` nutzt die Konstante `stagesWeatherProxyTimeout`, die > 60 s (alte nginx-Standardgrenze) und < `nginxProxyReadTimeout` ist; RED vor Fix: Handler nutzt 60 s. Verhaltensnachweis mit echter Verzoegerung > 60 s ist im Kerntest zu langsam und entfaellt dort bewusst; auf Staging nachrangig (Abruf ist meist < 10 s), nicht Teil des AC-7-Nachweises.

## Test Plan

- Go: `internal/handler/*_test.go` (AC-1, AC-6, AC-9) — Dateien nach Verhalten benannt, z. B. `send_proxy_context_test.go`, `proxy_timeout_chain_test.go`.
- Python: `tests/tdd/test_compare_send_lock.py` (AC-5, AC-8) plus Weiterlaufen der bestehenden `tests/tdd/test_send_idempotenz_lock.py` (Namen bleiben importierbar). Aufruf nur mit benannten Testdateien.
- Frontend: `frontend/src/lib/utils/sendOutcome.test.ts` ueber `node --test` (AC-2, AC-3, AC-4). Kein Vitest. Playwright nur als Zusatz.
- Staging: AC-7 (Konfig + Verhalten), danach Prod-Deploy und Post-Deploy-Selftest nach Standardablauf.
- Mutations-Gegenprobe (Adversary): `WithoutCancel` durch `r.Context()` ersetzen -> AC-1 muss rot werden; Lock-Schluessel ohne `user_id` -> AC-8 rot; `502`-Zweig im Klassifikator auf `failed` -> AC-2 rot; ein Ausloeser ohne `beginSend` -> Verdrahtungstest rot.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `/home/hem/henemm-infra/nginx/gregor20.henemm.com.conf` | MODIFY | `proxy_read_timeout`/`proxy_send_timeout` 330 s in `location /api/` |
| `/home/hem/henemm-infra/nginx/staging.gregor20.henemm.com.conf` | MODIFY | dito |
| `internal/handler/proxy.go` | MODIFY | Konstanten, `WithoutCancel` im Trip-Sende-Handler, Wetterabruf-Timeout 60 -> 120 s |
| `internal/handler/compare_preset.go` | MODIFY | `WithoutCancel`, Timeout 120 -> 300 s ueber gemeinsame Konstante |
| `internal/handler/*_test.go` | CREATE | AC-1, AC-6 |
| `src/services/send_lock.py` | CREATE | geteilter Lock-Helfer |
| `src/services/trip_report_scheduler.py` | MODIFY | Lock-Logik auf geteilten Helfer umgestellt |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Lock um `send_compare_preset` |
| `api/routers/scheduler.py` | MODIFY | 409 fuer Compare |
| `tests/tdd/test_compare_send_lock.py` | CREATE | AC-5, AC-8 |
| `frontend/src/lib/utils/sendOutcome.ts` (+ `.test.ts`) | CREATE | Laufzustand + Klassifikation |
| `frontend/src/routes/trips/[id]/+page.svelte`, `routes/trips/+page.svelte`, `routes/trips/tripListSend.ts`, `molecules/TestReportDialog.svelte`, `compare/CompareTabs.svelte`, `routes/compare/[id]/+page.svelte`, `routes/compare/+page.svelte` | MODIFY | auf geteiltes Modul umgestellt |

### Estimated Changes

- Files: ca. 12 im Gregor-Repo + 2 in henemm-infra
- LoC: +230/-40

## Known Limitations

- Der Lock wirkt wie in #1756 nur pro Python-Prozess (ein uvicorn-Prozess je Umgebung); bei Multi-Worker waere er neu zu bewerten.
- Nach Abschluss eines Versands gibt es keine Deduplizierung gegen `briefing_log`; ein bewusster zweiter Versand bleibt erlaubt.
- Die Oberflaeche kennt bei "Ergebnis unklar" den tatsaechlichen Ausgang nicht; Klarheit liefert das Versandprotokoll. Ein Status-Poll ist bewusst nicht Teil dieser Spec (Option B abgelehnt).
- Der Go-Konstanten-Test (AC-6) kann die vhost-Datei nicht pruefen (CI hat kein nginx); der Nachweis liegt auf Staging (AC-7).
- Nebenbefund `briefing_log` `["email"]` und die zwei Fremdeintraege vom 30.08. sind nicht Teil dieses Fixes (#1199).
- Renderer-Commit-Gate (#811): nicht betroffen (keine Mail-Renderer-Dateien). Pendant-Gate: neue Frontend-Datei liegt in `lib/utils/`, geteilt fuer Trip und Compare.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Konfigurations- und Robustheitsfix innerhalb des bestehenden synchronen Sendepfads (Linie #1756); keine Entscheidungsflaeche aus CLAUDE.md wird geaendert, kein bestehendes ADR still rueckgaengig gemacht.

## Changelog

- 2026-10-07: Initial spec created (Issue #2124)
- 2026-10-07: AC-9 ergaenzt — im Issue genannter Wetterabruf (`stages/weather`) bekommt 120 s statt 60 s Go-Timeout
