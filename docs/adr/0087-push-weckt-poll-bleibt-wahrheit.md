# ADR-0087: Push weckt, Poll bleibt Wahrheit — Webhook stößt nur den bestehenden Poll-Job an

- **Status:** Akzeptiert
- **Datum:** 2026-10-14
- **Bezug:** GitHub-Issue #2439 Scheibe (a), Spec
  `docs/specs/modules/feat_2439_befehle_push_eingang.md`; Runbook
  `docs/runbooks/inbound-webhooks.md`

## Kontext

Befehle per Premium-SMS (seven.io) und E-Mail (Stalwart) wurden erst beim nächsten
5-Minuten-Poll verarbeitet (PO-Befund 28.09.: `CODES` nach 4:28 min beantwortet, Rechnen unter
1 s). Telegram hat bereits einen Push-Eingang. Für SMS und E-Mail gab es bislang keine
Entscheidung Poll vs. Push; „kein Webhook“ in älteren Kontextdokumenten war Ist-Beschreibung,
keine Begründung.

## Entscheidung

- **Der Webhook verarbeitet nichts selbst.** Er prüft die Echtheit und stößt den BESTEHENDEN
  Poll-Job des Kanals (`premium_sms_poll`, `inbound_command_poll`) sofort an
  (`Scheduler.Kick`). Journal-Abruf, Lern-Aufruf, `last_seen_id`, IMAP-`UNSEEN` und die
  Nutzerzuordnung bleiben unverändert. Es gibt genau EINEN Verarbeiter je Kanal — damit keine
  doppelte, kostenpflichtige Antwort-SMS.
- **Prüfung und Coalescing liegen in Go.** Pfad-Secret (konstantzeitig) plus Signatur bzw.
  Bearer; fehlendes Secret ⇒ 503 (fail-closed), Fehlschlag ⇒ 403 ohne Kick, Erfolg ⇒ sofort 200.
  Mehrere Weckrufe verschmelzen: je Job höchstens eine Kick-Goroutine, ein Kick während des
  Laufs setzt nur `pending`. Der Cron-Tick bleibt `TryLock`, der Kick wartet auf denselben
  `jobLock`.
- **Python-flock als zweite Schranke.** `/inbound-sms` und `/inbound-commands` nehmen einen
  nicht-blockierenden `flock`; belegt ⇒ `{"status":"busy"}`, Go setzt den Weckruf erneut auf
  `pending`. Das schließt auch den Admin-Proxy, der den Go-Lock umgeht.
- **Nachversuche gegen Journal-Verzögerung.** SMS: Läufe bei 0/3/8 s, Abbruch bei
  `processed>0`; Mail: ein Nachversuch nach ~2 s. Nachversuche rufen nur Journal/IMAP ab.
- **Der Poll bleibt Fallback und alleinige Wahrheit** (`*/5` unverändert). Ein ausgefallener
  Sofort-Weg bleibt nicht unbemerkt: `push.last_received` fehlt, und ein Cron-Lauf mit
  verarbeiteten Befehlen ohne Webhook in den letzten 5 min zählt `push.missed_total`.

## Verworfene Alternativen

- **Variante B (Einzelnachricht-Pfad wie Telegram):** zwei Verarbeiter ⇒ Doppelverarbeitung
  kostenpflichtiger SMS, Abhängigkeit vom undokumentierten `sms_mo`-Payload, ~450+ LoC.
- **IMAP IDLE:** langlebige Verbindung, in Stalwart 0.16.x fehlt das EXISTS-Ereignis.
- **Poll-Intervall senken statt Push:** mehr Last und Journal-Aufrufe, keine Sekunden-Latenz.

## Konsequenzen

- **Positiv:** Antwort in Sekunden statt Minuten; Verarbeitungslogik unverändert.
- **Negativ / Preis:** neuer öffentlicher Eingang (Schutz: Pfad-Secret + Signatur + Nginx
  `limit_req`; fuer `/api/webhooks/sms/` zusaetzlich IP-Allowlist der festen seven.io-Absender
  `195.201.160.143`, `2a01:4f8:13a:8e7::2` -- Abweichung: die Spec nannte einen IP-Filter
  faelschlich „nicht moeglich“); die Kick-Goroutine kann bis zu einem Lauf lang
  auf den laufenden Job warten; Fallback-Poll bleibt vorerst `*/5`.
- **Folgepflichten:** neue Eingangskanäle dieser Art folgen „Push weckt, Poll bleibt Wahrheit“;
  eine spätere Absenkung des Poll-Intervalls ist eine eigene Entscheidung nach Prod-Beleg.
