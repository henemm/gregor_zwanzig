---
entity_id: security_haertung_2026_11_premium_sms_rueckkanal
type: module
created: 2026-11-13
updated: 2026-11-13
status: approved
version: "1.0"
tags: [premium-sms, garmin, inbound, security, mandantentrennung, kontingent]
---

<!-- Issue #2961, Welle 2, Paket „Premium-SMS-Rückkanal" (Review-Befund GC7 a, b, d, e, f). -->

# Sicherheits-Härtung 2026-11: Premium-SMS-Rückkanal

## Approval

- [x] Approved — Behebung aller Befunde vom Product Owner beauftragt (Issue #2961);
  Entscheidungen „kein PIN, stattdessen Mitteilung" und „Code ohne Ablauf" sind bewusst und in
  ADR-0116 begründet.

## Purpose

Premium-SMS-Nachrichten (Garmin inReach) werden zuverlässig dem richtigen Konto zugeordnet, auch
wenn Garmin eine Absendernummer an ein anderes Gerät weitergibt; fremde Änderungen über diesen
Kanal werden sichtbar; Antworten verbrauchen kein Alarm-Kontingent; ein Gerät lässt sich trennen.

## Source

- **Go:** `internal/handler/premium_sms_connect.go` (`resolvePremiumSmsTarget`,
  `resolveByLinkCode`), `internal/handler/premium_sms_ratelimit.go`,
  `internal/handler/premium_sms_link_code.go` (Code-Gestalt, `DeletePremiumSmsReplyHandler`),
  `internal/store/premium_sms_reply.go` (`LearnPremiumSmsReplyTo`, `ClearPremiumSmsReply`),
  `internal/router/router.go`
- **Python:** `src/services/inbound_sms_reader.py` (`_LINK_CODE_PATTERN`, Journal-Hinweis,
  Mitteilung), `src/services/premium_sms_aenderungshinweis.py` (neu),
  `src/services/sms_daily_limit.py`, `src/services/user_tier.py`,
  `src/services/notification_service.py` (`send_premium_sms_change_notice`, Antwort-Kontingent),
  `src/output/channels/recipient.py` (`PremiumSmsRecipient.for_user`), Katalog
  `src/i18n/messages/{de,en}/inbound.json`
- **Frontend:** `frontend/src/lib/components/account/PremiumSmsLinkCard.svelte`,
  `frontend/src/lib/utils/premiumSmsLinkCodeHelpers.ts`, Einbindung in
  `frontend/src/routes/account/+page.svelte`, Katalog `konto.json`

> Querschnitt: Mandantentrennung — jeder datenbewegende Weg wird mit zwei Konten getestet,
> `user_id` nur aus dem Auth-Kontext bzw. der Lern-Antwort. Kanäle — die Mitteilung nutzt E-Mail
> und Telegram als „andere" Kanäle; SMS bleibt aus Kostengründen außen vor. Keine Trip/Vergleich-
> Pendant-Frage (Konto-Komponente).

## Estimated Scope

- **LoC:** ~350 Produktivcode, ~600 Tests (über dem 250-LoC-Richtwert; sechs zusammengehörige
  Befunde in einem Paket, vom Orchestrator so geschnitten)
- **Files:** ~14 Produktivdateien, ~14 Testdateien, 6 Doku-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| ADR-0049 | ADR | Premium-SMS als vierter Kanal |
| ADR-0095 | ADR | Kanal-Parität |
| ADR-0087 | ADR | Empfängerschutz (Versandwege der Mitteilung) |
| fix_2154 / fix_2328 | Spec | Verknüpfungscode, Kollisionserkennung (AC-2 teilweise abgelöst) |
| sms_daily_limit | Spec | Tageskontingent (Antworten jetzt getrennt) |

## Implementation Details

```
Lernen (Go):
  Code vorhanden -> Bremse (je Absender 3/h, gesamt 30/h) -> bcrypt je Premium-Kandidat
     genau 1 Treffer -> Ziel (schlaegt frischen Treffer eines anderen Kontos)
     sonst Fehlversuch zaehlen
  sonst/danach: genau 1 frischer gespeicherter Treffer -> Ziel
  sonst: Grund (ungueltig | Bremse | mehrdeutig | Code noetig), nie "default"
  Ziel gefunden -> store.LearnPremiumSmsReplyTo: Nummer bei allen anderen Konten entfernen,
     dann beim Ziel setzen (Merge, nur zwei Felder)
Code: "XX" + 5 aus 23 Buchstaben + 3 aus 8 Ziffern; Eingang erkennt 3 und 5 Buchstaben
Senden (Python): PremiumSmsRecipient.for_user sperrt, wenn ein anderes Konto dieselbe Nummer traegt
Befehl (Python): nach der Antwort melde_aenderung(): nur erfolgreiche aendernde Befehle,
   Tageszaehler premium_sms_change_notice <= 10, E-Mail (bestaetigt) + Telegram (verbunden)
Kontingent: purpose="reply" -> Zaehler premium_sms_reply, eigene Grenze (Premium 15)
Trennen: DELETE /api/auth/premium-sms-reply -> ClearPremiumSmsReply(user aus Auth-Kontext)
Journal: limit=100; volle Seite ohne Ueberlappung mit Lesezeiger -> Warnung
```

## Expected Behavior

- **Input:** Garmin-Nachrichten im seven.io-Journal; Konto-Aktion „Verbindung trennen".
- **Output:** Zuordnung zum richtigen Konto; Befehlsantwort per Premium-SMS; bei Änderungen eine
  Mitteilung per E-Mail/Telegram.
- **Side effects:** Rückadresse wird bei anderen Konten entfernt; neue Zählerfelder
  `premium_sms_reply` und `premium_sms_change_notice` in `sms_daily_count.json`.

## Acceptance Criteria

**AC-1:** Given Konto B hält die Nummer N frisch als Rückadresse und Konto A hat einen gültigen Verknüpfungscode / When eine Nachricht von N mit A's Code eintrifft / Then wird sie Konto A zugeordnet, A lernt N und B verliert N.
  - Test: `TestLearnValidCodeWinsOverForeignFreshStoredMatch`

**AC-2:** Given mehrere Konten (auch veraltete, auch ohne Premium-Tarif) tragen die Nummer N und ein Konto trägt eine andere Nummer / When Konto A die Nummer N lernt / Then ist N bei allen anderen Konten samt Zeitstempel entfernt, deren übrige Felder bleiben unverändert und das Konto mit anderer Nummer bleibt byte-gleich.
  - Test: `TestLearnRemovesReplyAddressFromAllOtherAccounts`, `TestLearnResolvesAmbiguousCollisionWithValidCode` (fix_2328 AC-2, angepasst)

**AC-3:** Given Konto A ist N eindeutig und frisch zugeordnet / When von N eine Nachricht mit falschem Code eintrifft / Then bleibt sie Konto A zugeordnet und kein anderes Konto lernt etwas.
  - Test: `TestLearnWrongCodeKeepsOwnFreshStoredMatch`

**AC-4:** Given ein neu erzeugter Verknüpfungscode / When er angezeigt wird / Then hat er die Gestalt `XX` + 5 Buchstaben ohne I/L/O + 3 Ziffern ohne 0/1 und der Schlüsselraum beträgt mindestens 10^9; ein Bestandscode im alten Format verknüpft weiterhin.
  - Test: `TestLinkCodeShapeHoldsAcrossManyGenerations`, `TestLinkCodeKeySpaceAtLeastOneBillion`, `TestLearnAcceptsLegacyShortLinkCode`, Router-Test `TestPremiumSmsLinkCodeRouteIstVerdrahtetUndAnmeldepflichtig`

**AC-5:** Given zwei Konten tragen (Bestandsdaten) dieselbe Rückadresse / When an eines von ihnen eine Premium-SMS gehen soll / Then wird der Versand an beide gesperrt, während ein Konto mit eigener Nummer weiter bedient wird.
  - Test: `test_rueckadresse_zweier_konten_wird_nicht_bedient`, `test_rueckadresse_eines_einzigen_kontos_wird_bedient`

**AC-6:** Given ein Absender hat in der laufenden Stunde drei falsche Codes geschickt / When er einen weiteren Code schickt / Then wird nicht mehr verglichen (429), das globale Budget ist nur um drei gesunken, ein anderer Absender verknüpft ungehindert und nach Ablauf der Stunde darf der erste wieder; global gelten 30 Fehlversuche je Stunde.
  - Test: `TestPremiumSmsRatebremse_JeAbsenderSchontGlobalesBudget`, `TestPremiumSmsRatebremse_Grenzwerte`, `TestPremiumSmsRatebremse_GleitendesStundenfenster`

**AC-7:** Given das Premium-SMS-Alarm-Kontingent eines Nutzers ist erschöpft / When er Befehle per Premium-SMS schickt / Then gehen die Antworten trotzdem raus und zählen in den eigenen Antwort-Zähler, der Alarm-Zähler bleibt unverändert.
  - Test: `test_ac4_garmin_antwort_verbraucht_nie_das_alarm_kontingent`

**AC-8:** Given das Antwort-Kontingent ist erschöpft und das Alarm-Kontingent leer / When eine weitere Antwort und danach ein Alarm ausgelöst werden / Then ist die Antwort gesperrt und der Alarm geht raus; eine Zählerdatei im alten Format bleibt lesbar und wird ohne Verlust weitergeführt.
  - Test: `test_ac4b_erschoepftes_antwort_kontingent_sperrt_keine_alarme`, `test_ac4c_bestehende_zaehlerdatei_ohne_antwortfeld_bleibt_lesbar`, `test_get_daily_usage_zeigt_antwort_zaehler_getrennt`

**AC-9:** Given Konto A hat eine bestätigte E-Mail-Adresse und Telegram verbunden, Konto B ebenfalls / When A per Premium-SMS „pause 2d" schickt / Then bekommt A die Premium-SMS-Antwort sowie je eine Mitteilung per E-Mail und Telegram mit Befehl, Zeitpunkt, Kanal und Rückweg; B bekommt nichts.
  - Test: `test_pause_meldet_auf_email_und_telegram_nur_dem_eigenen_konto`

**AC-10:** Given ein Nutzer mit eingerichteten Kanälen / When er per Premium-SMS einen lesenden Befehl wie „status" schickt / Then geht nur die Premium-SMS-Antwort raus, keine Mitteilung; jeder Befehlsschlüssel des Verarbeiters ist als ändernd oder lesend eingestuft.
  - Test: `test_lesender_befehl_loest_keine_mitteilung_aus`, `test_jeder_befehl_ist_als_aendernd_oder_lesend_eingestuft`

**AC-11:** Given die E-Mail-Adresse eines Nutzers ist nicht bestätigt / When eine Änderung per Premium-SMS ausgeführt wird / Then geht keine Mail raus, Telegram wird weiterhin benachrichtigt.
  - Test: `test_unbestaetigte_adresse_bekommt_keine_mail`

**AC-12:** Given ein Nutzer hat heute schon zehn Mitteilungen bekommen / When eine weitere Änderung per Premium-SMS ausgeführt wird / Then kommt keine elfte Mitteilung, der Befehl und seine Antwort laufen weiter und ein zweites Konto hat sein eigenes Tageskontingent.
  - Test: `test_hoechstens_zehn_mitteilungen_je_tag`

**AC-13:** Given Konto A ist angemeldet und hat eine Rückadresse, Konto B ebenfalls / When A „Verbindung trennen" bestätigt (DELETE /api/auth/premium-sms-reply) / Then sind Rückadresse und Zeitstempel von A gelöscht, A's Verknüpfungscode und übrige Felder bleiben, B bleibt unverändert, und eine Nachricht von der alten Nummer ohne Code wird A nicht mehr zugeordnet.
  - Test: `TestPremiumSmsDisconnectClearsOnlyOwnReplyAddress`, `TestPremiumSmsDisconnectRouteTrenntNurDasEigeneKonto`

**AC-14:** Given kein Auth-Kontext / When DELETE /api/auth/premium-sms-reply aufgerufen wird / Then antwortet der Dienst mit 401 und verändert kein Konto, auch nicht „default".
  - Test: `TestPremiumSmsDisconnectWithoutAuthContextNeverTouchesDefault`, `TestPremiumSmsDisconnectRouteWeistAnonymeAufrufeAb`

**AC-15:** Given ein Premium-Konto mit gelernter Rückadresse / When die Konto-Seite die Premium-SMS-Karte zeigt / Then gibt es „Verbindung trennen" mit Rückfrage, die sagt, dass der Verknüpfungscode gültig bleibt; ohne Rückadresse fehlt der Knopf.
  - Test: `premium_sms_link_card_render.test.ts` („Verbindung trennen"), `premiumSmsLinkCodeHelpers.test.ts`

**AC-16:** Given das Journal liefert eine volle Seite (100 Einträge), die nicht mit dem Lesezeiger überlappt / When der Poll läuft / Then steht eine Warnung „möglicherweise abgeschnitten" im Log; bei Überlappung oder kleinerer Seite nicht.
  - Test: `test_journal_volle_seite_ohne_ueberlappung_warnt`, `test_journal_volle_seite_mit_ueberlappung_warnt_nicht`, `test_journal_unvolle_seite_warnt_nicht`

## Known Limitations

- Ein Angreifer, der eine Nummer aus dem Garmin-Pool erhält, die einem Konto noch frisch
  zugeordnet ist, kann bis zur nächsten Nachricht des Inhabers mit Code oder bis zum Trennen
  Befehle für dieses Konto senden; die Mitteilung macht das sichtbar und nennt den Rückweg.
- Bestandscodes (6,2 Mio.) sind bei der globalen Bremse von 30/h schwächer geschützt als neue
  Codes; kein Zwangstausch (Empfehlung: erneuern).
- Ob die seven.io-Journal-Schnittstelle Blättern anbietet, war aus der Sandbox nicht prüfbar
  (keine Verbindung zur Dokumentation); daher nur die Warnung.
- Die Kontoanzeige des Tageskontingents zeigt das Antwort-Kontingent (`reply_used`/`reply_limit`)
  noch nicht an; die Anzeige des Alarm-Kontingents bleibt korrekt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0116
- **Rationale:** Zuordnung, Code-Lebensdauer, Ersatz eines PIN durch Mitteilungen und getrennte
  Kontingente sind Entscheidungen über Kanal-Sicherheit und Bedienbarkeit unterwegs.

## Changelog

- 2026-11-13: v1.0 angelegt und umgesetzt (Issue #2961 Welle 2).
