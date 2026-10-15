# Runbook — Push-Eingang für Befehle (SMS + E-Mail), Issue #2439

„Webhook = Weckruf“ (ADR-0088): seven.io bzw. Stalwart melden einen Eingang, Go prüft und stößt den
bestehenden Poll-Job sofort an. Der `*/5`-Poll bleibt Fallback und Wahrheit.

```
seven.io / Stalwart --POST--> Nginx --> Go  /api/webhooks/sms/{secret}
                                            /api/webhooks/mail/{secret}
                                        Prüfung -> 200 sofort -> Scheduler.Kick
                                        -> POST /api/scheduler/inbound-sms | inbound-commands (Python, flock)
```

## Umgebungsvariablen (Go-Prozess; Prod und Staging getrennt)

| ENV | Zweck | Fehlt ⇒ |
|-----|-------|---------|
| `SEVEN_WEBHOOK_PATH_SECRET` | geheimes letztes Pfadsegment der SMS-URL | 503 |
| `SEVEN_WEBHOOK_SIGNING_KEY` | seven.io-Account-Signing-Key (HMAC) | 503 |
| `STALWART_WEBHOOK_PATH_SECRET` | geheimes letztes Pfadsegment der Mail-URL | 503 |
| `STALWART_WEBHOOK_SECRET` | Bearer-Token des Stalwart-Hooks | 503 |
| `PUBLIC_HOST` | Basis der signierten URL (nie Host-Header) | Default Prod-Host |

Die signierte URL ist `PUBLIC_HOST + /api/webhooks/sms/ + SEVEN_WEBHOOK_PATH_SECRET`. Auf Staging
muss `PUBLIC_HOST` die Staging-Adresse sein, sonst stimmt die Signatur nicht.

## seven.io registrieren

```
POST https://gateway.seven.io/api/hooks
  target_url   = https://<host>/api/webhooks/sms/<SEVEN_WEBHOOK_PATH_SECRET>
  event_type   = sms_mo
  event_filter = <Service-Nummer ohne „+“>
  request_method = POST
```

Der Signing-Key kommt aus dem seven.io-Dashboard (Env `SEVEN_WEBHOOK_SIGNING_KEY`, nie ins Repo).
**Signaturverfahren** (gegen die echte seven.io-Gegenseite belegt, Nachweis
`docs/artifacts/feat-2439-befehle-push-eingang/seven-signatur-nachweis.md`):

```
string_to_sign = X-Timestamp \n X-Nonce \n METHODE \n volle URL \n md5_hex(roher Body)
X-Signature    = hex(HMAC-SHA256(signing_key, string_to_sign))   # kein abschliessender Zeilenumbruch
```

Die Test-Fixture `internal/handler/testdata/seven_sms_mo.json` ist ein Testvektor nach genau
diesem Verfahren (Test-Schluessel, Fantasienummern), kein Mitschnitt.

**IP-Allowlist (Abweichung von der Spec):** Die Spec nannte einen IP-Filter faelschlich „nicht
moeglich“. seven.io sendet Webhooks von festen Adressen `195.201.160.143` und
`2a01:4f8:13a:8e7::2`. Die Nginx-Location `/api/webhooks/sms/` erlaubt nur diese (`allow` ...,
`deny all`) -- zusaetzlich zu Pfad-Secret, Signatur und `limit_req`.

## Stalwart registrieren

Webhook im Stalwart-Admin (v0.16.26) mit Ziel `https://<host>/api/webhooks/mail/<STALWART_WEBHOOK_PATH_SECRET>`,
Authentifizierung „Bearer“ mit `STALWART_WEBHOOK_SECRET`. Eventname: **vor Registrierung an v0.16.26
verifizieren** (Doku nennt `message-ingest.ham`, ein Beispiel `store.ingest`). Ein falscher Name ist
stille Nicht-Zustellung — sichtbar nur über ausbleibendes `push.last_received`. Netzpfad: Der
Container erreicht Go nur über den öffentlichen Nginx-Pfad (Hairpin); Go bindet `127.0.0.1:8090`.

## Nginx (henemm-infra)

Locations `/api/webhooks/sms/` und `/api/webhooks/mail/` an die Go-API (prod + staging), `limit_req`,
auf Staging Basic-Auth-Ausnahme nur für diese Pfade (analog Telegram). `/api/webhooks/sms/` zusätzlich mit IP-Allowlist (siehe oben).

## Rotation

Neues Secret erzeugen, Env in Go-Prozess setzen, Hook beim Anbieter (seven.io: Hook neu anlegen
mit neuem Pfad; Stalwart: Webhook-Konfiguration) aktualisieren, Go neu starten (Deploy-Script).
Zwischen Env-Wechsel und Hook-Update antwortet der Endpunkt 403; der Fallback-Poll deckt die Lücke.

## Beobachtung

`GET /api/scheduler/status` (Header `X-GZ-Status-Token`): je Job `premium_sms_poll` und
`inbound_command_poll` das Feld `push` mit `last_received`, `received_total`, `rejected_total`,
`kicks_coalesced`, `missed_total`, `last_missed`. Steigender `missed_total` heißt: der Sofort-Weg ist
ausgefallen (Befehl wurde erst vom Fallback-Poll verarbeitet).

## Go→Core-Verbindung ohne Keep-Alive (2026-10-15, Nachbesserung #2439)

Der geteilte Go-HTTP-Client zum Python-Core (`newCoreClient`, `internal/scheduler/scheduler.go`)
nutzt kein Keep-Alive: `closeConnTransport` setzt `req.Close=true` auf einem Request-Klon und
delegiert an das zur Aufrufzeit gültige `http.DefaultTransport` (coreauth- und egress-Wrapper bleiben
erhalten). Ursache: Der Core schließt Idle-Verbindungen; ein späterer POST (z. B. SMS-Nachversuch nach
3 s/8 s, AC-7) lief auf eine bereits geschlossene, wiederverwendete Verbindung und scheiterte mit
`EOF` — Go wiederholt POST nicht. Wächter: Go-Kerntest
`internal/scheduler/core_verbindung_wiederverwendung_test.go`.

**Grenze:** Der Staging-Test (`tests/e2e/test_push_eingang_befehle_staging.py`) prüft
`last_run.status == "ok"`. Da `kickRound` bei Fehlern weiterversucht, bliebe ein EOF im ersten Versuch
mit erfolgreichem Nachversuch dort unsichtbar; die Verbindungsebene ist nur im Go-Kerntest bewacht.

## Reihenfolge bei der Inbetriebnahme

1. **Staging: `PUBLIC_HOST` auf den Staging-Host setzen.** Der Default ist der Prod-Host; sonst stimmt
   die signierte URL nicht und seven.io-Aufrufe enden dauerhaft in 403.
2. **Basic-Auth-Ausnahme auf Staging** ist nur durch eine echte seven.io-Zustellung belegbar. Aufrufe
   vom Server selbst umgehen Basic-Auth (infra#229) und beweisen die Ausnahme nicht.
3. **`missed_total`-Auswertung** in `henemm-infra` `check-gregor20.sh` erst scharf schalten, wenn die
   Hooks registriert sind und `push.last_received` sichtbar ist. Fehlendes Feld = 0. Die Zähler leben im
   Speicher: nach einem Go-Restart neu baselinen, nicht als Fehler werten.
4. **Stalwart-Eventname** bei der Registrierung gegen v0.16.26 per Admin-API verifizieren und hier
   eintragen: _noch offen — Eintrag nach Verifikation_.

## Staging-Beleg

- **SMS:** das Konto hat nur die Service-Nummer, keine zweite. Beleg deshalb über einen zweiten Hook
  auf dieselbe Service-Nummer mit Ziel Staging. Der Staging-Poll läuft dort wegen der Herkunftssperre
  leer; der Beleg ist allein `push.last_received` gefolgt von einem `last_run` des Jobs wenige
  Sekunden später (nicht am 5-Minuten-Raster).
- **Mail:** Staging-Stalwart-Hook, Befehlsmail an `gregor-test@`; IMAP-Beleg der Antwort und
  `last_run` abseits des 5-Minuten-Rasters.
