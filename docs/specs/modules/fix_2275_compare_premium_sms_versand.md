---
entity_id: fix_2275_compare_premium_sms_versand
type: module
created: 2026-09-26
updated: 2026-09-26
status: draft
version: "1.0"
tags: [premium-sms, garmin, ortsvergleich, briefing, verdrahtung, bugfix]
---

# Premium-SMS im Ortsvergleich-Briefing verdrahten (#2275)

## Approval

- [ ] Approved

## Purpose

Im Versand-Reiter eines Ortsvergleichs gibt es einen Premium-SMS-Schalter. Er wird beim
Briefing korrekt aufgelöst (`premium_sms` landet in `effective_channels`), aber
`send_compare_report` hat keinen Zweig dafür: der Kanal wird still übergangen, der Nutzer sieht
einen aktiven Schalter ohne Wirkung. Diese Spec verdrahtet den Kanal (Entscheid Tech Lead im
PO-Mandat, 09.09.) und macht jeden Fehlschlag sichtbar. Damit gilt auch im Ortsvergleich, was
für Trip-Briefing und Alarme schon gilt: jeder gewählte Kanal wird bedient oder der Grund für
sein Ausbleiben wird maschinenlesbar gebucht.

## Source

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/services/`). Frontend, Go-API,
> Persistenz und Hydrierung des Schalters existieren bereits und bleiben unverändert.

- **File:** `src/services/notification_service.py`
- **Identifier:** `NotificationService.send_compare_report` (ab ~Z.1231)
- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `send_one_compare_preset` (Aufruf ab ~Z.630, Sink-Parameter ab ~Z.438)

## Estimated Scope

- **LoC:** ca. +90/-5 produktiv, ca. +120 Test (unter LoC-Limit 250; Tests zählen mit, knapp)
- **Files:** 3 Code/Test + 1 Doku (`CLAUDE.md`)
- **Effort:** low-medium

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/notification_service.py` | MODIFY | `premium_sms`-Zweig in `send_compare_report`, neuer Parameter `premium_sms_sink`, `failed_channels` im Ergebnis |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `premium_sms_sink` durchreichen, `failed_channels`/`blocked_channels` auswerten (Log-Warnung) |
| `tests/tdd/test_compare_premium_sms_versand.py` | CREATE | Kernschicht AC-1..AC-7 (Fake am Transport, kein Netz) |
| `CLAUDE.md` | MODIFY (Doku) | Zeile „Premium-SMS-Reichweite" korrigieren |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `PremiumSmsOutput` (`src/output/channels/premium_sms.py`) | module | Transport; prüft Rückadresse-Pflicht und 30-Tage-Frist selbst |
| `sms_daily_limit` / `_sms_gate_reserve` | module/method | Tageslimit reservieren und bei Fehler freigeben |
| `_record_block_reason_code` | function | maschinenlesbarer Sperrgrund |
| `effective_compare_briefing_channels` (`compare_alert_channels.py`) | function | löst `premium_sms` auf (Opt-in `send_premium_sms` UND `premium_sms_allowed(user_id)`) — unverändert |
| `render_compare_sms` (`renderers/comparison.py`) | function | liefert die Vergleichs-Kurzform (153 Zeichen GSM-7), unverändert |
| `alert_channels._ALL_CHANNELS` | constant | Anknüpfungspunkt des Vollständigkeits-Wächters |
| Vorbedingung #2279 | issue | seit 17.09. geschlossen |

## Implementation Details

**1. Zweig in `send_compare_report`** — direkt nach dem `sms`-Zweig, nach Vorlage
Trip-Briefing (~Z.642) und Alarm-Zweig (~Z.1201):

- Bedingung: `"premium_sms" in effective_channels`. **Kein `can_send_*()` davor** (D2 aus #1701:
  die Freigabe steckt im Auflöser, Rückadresse/Frist prüft `PremiumSmsOutput`).
- `_sms_gate_reserve("premium_sms", "briefing", now, blocked_channels, blocked_reason_codes)`.
  Verweigert das Gate (Tageslimit), wird der Grund dort bereits gebucht; nichts wird gesendet.
- Senden: `premium_sms_sink(sms_text)` wenn gesetzt, sonst
  `PremiumSmsOutput(self._settings).send(...)` mit dem **bereits übergebenen `sms_text`**
  (Vergleichs-Kurzform). Kein neuer Renderer.
- Erfolg: `sent_channels.append("premium_sms")`.
- Exception: `sms_daily_limit.release_reservation(user, "premium_sms", now)`,
  `blocked_channels["premium_sms"] = str(e)`, `_record_block_reason_code(...)`,
  `failed_channels.append("premium_sms")`, `logger.error(...)` mit Preset-Betreff.

**2. Fehlersemantik (entschieden: fail-soft).** Ein gescheiterter Premium-SMS-Versand lässt den
Preset-Versand nicht als Ganzes scheitern; ein E-Mail-Erfolg bleibt gültig (der Ortsvergleich
hat keinen Nachhol-Mechanismus, ein Abbruch würde den E-Mail-Erfolg entwerten). Er ist aber
sichtbar: `failed_channels`, `blocked_channels` + Reason-Code und Log. Sperrgründe
(Tageslimit, Rückadresse fehlt/veraltet) landen als Wert in `blocked_channels` + Reason-Code,
nicht als Exception nach außen. `NotificationResult` (Feld `failed_channels` existiert im
Ergebnistyp bereits) wird von `send_compare_report` jetzt befüllt und zurückgegeben.

**3. Aufrufer `send_one_compare_preset`.** `premium_sms_sink=None` als Parameter ergänzen (wie
`mail_sink`/`sms_sink`) und 1:1 an `send_compare_report` durchreichen. Nach dem Versand:
enthält `send_result.failed_channels` oder `blocked_channels` Einträge, eine Log-Warnung mit
Preset-ID, Kanal und Reason-Code; der Rückgabepfad (Anker, Erfolg über `.sent`) bleibt
unverändert. `user_id` wird wie bisher aus dem Aufruf durchgereicht, nie `"default"`.

**4. Abgrenzung / Begründung des Schnitts.** Es gibt bereits mehrere Kopien des Premium-SMS-
Zweigs (Trip-Briefing ~Z.642 und ~Z.800, Alarm ~Z.1201). Das Issue-Zielbild „gemeinsame
Kanal-Schleife" (#1412) wird bewusst NICHT umgesetzt: es würde die Trip-Zweige anfassen,
sprengt das LoC-Limit 250 und riskiert Regressionen im kostenpflichtigen Trip-Versand. Diese
Lieferung ergänzt nur den Vergleichs-Zweig (nach dem Muster der Vorlagen); Trip-Zweige
bleiben unangetastet. Konsolidierung der Kopien: Sammel-Issue #1199. Der
Vollständigkeits-Wächter (AC-4) fängt in der Zwischenzeit ab, dass ein Pfad einen
auflösbaren Kanal nicht bedient.

**5. Doku.** `CLAUDE.md`, Zeile „Premium-SMS-Reichweite": „Versandkanal nur im Trip-Briefing"
wird zu „Versandkanal im Trip-Briefing UND im Ortsvergleich-Briefing"; Alarm-Aussage bleibt.

## Expected Behavior

- **Input:** `send_compare_report(..., effective_channels={"email","premium_sms"}, sms_text=..., premium_sms_sink=...)`.
- **Output:** `NotificationResult` mit `sent_channels` (enthält `premium_sms` bei Erfolg),
  `failed_channels`, `blocked_channels`, `blocked_reason_codes`.
- **Side effects:** Tageslimit-Zähler des Nutzers +1 bei Erfolg, unverändert bei Fehler/Sperre;
  Log-Zeile bei Fehler. Echter Versand kostet Geld (nur im Live-Nachweis, s. u.).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich mit aktivem Premium-SMS-Schalter und Tier-Freigabe / When das Briefing versendet wird / Then geht die Vergleichs-Kurzform über den Premium-SMS-Transport, `premium_sms` steht in `sent_channels` und der Tageslimit-Zähler des Nutzers steigt um genau 1.
  - Test: Fake am Transport `output.channels.premium_sms` (Muster `tests/tdd/test_sms_tageslimit.py` ab Z.100) bzw. `premium_sms_sink`; Zähler vor/nach lesen; Text ist der übergebene `sms_text`.

- **AC-2:** Given der Premium-SMS-Kanal ist nicht sendebereit oder der Transport wirft einen Fehler / When das Briefing versendet wird / Then steht `premium_sms` in `failed_channels` UND in `blocked_channels` mit Reason-Code, die Tageslimit-Reservierung ist freigegeben (Zähler wieder auf altem Stand), ein Log-Eintrag existiert und der E-Mail-Versand desselben Laufs ist unberührt (`email` in `sent_channels`, kein Fehler nach außen).
  - Test: Fake wirft; Ergebnisfelder, Zähler, `caplog` (`logger.error`) und E-Mail-Sink-Aufruf prüfen.

- **AC-3:** Given die Rückadresse des Nutzers fehlt oder ist veraltet (Sperrgrund von `PremiumSmsOutput`) / When das Briefing versendet wird / Then wird nichts über Premium-SMS gesendet, der Grund steht maschinenlesbar in `blocked_reason_codes` (und, weil `PremiumSmsOutput` ihn als Ausnahme meldet, wie in AC-2 zusätzlich in `blocked_channels` und `failed_channels`); nur die Tageslimit-Sperre vor dem Senden (`_sms_gate_reserve`) steht ausschließlich in `blocked_channels`/`blocked_reason_codes`. In beiden Fällen wird der Kanal nie stillschweigend übergangen.
  - Test: Nutzer ohne Rückadresse; Transport-Fake nicht erreicht; Reason-Code für `premium_sms` gesetzt; Sperre als Ergebnis, nicht als Exception nach außen.

- **AC-4:** Given der Kanal-Auflöser kann für Vergleich UND Trip jeden Kanal aus `alert_channels._ALL_CHANNELS` liefern / When der jeweilige Versandpfad (Vergleichs-Briefing und Trip-Briefing) mit genau diesem Kanal aufgerufen wird / Then wird der Kanal bedient (Sink gerufen) oder ein Sperrgrund gebucht — kein aufgelöster Kanal wird still verschluckt.
  - Test: parametrisiert über `_ALL_CHANNELS`; Mutationsprobe „`premium_sms`-Zweig aus `send_compare_report` entfernen" macht genau diesen Test rot.

- **AC-5:** Given ein Preset-Versand über `send_one_compare_preset` (Scheduler oder Handversand) mit gewähltem Premium-SMS / When der Premium-SMS-Transport scheitert / Then wird der übergebene `premium_sms_sink` bis `send_compare_report` durchgereicht, der Aufrufer schreibt eine Log-Warnung mit Kanal und Reason-Code, und der Preset-Versand gilt weiter als erfolgreich (E-Mail-Erfolg zählt).
  - Test: `send_one_compare_preset` mit Sinks aufrufen (Sink erreicht den Zweig); scheiternder Fake; `caplog` enthält Warnung; kein Raise, Anker wird wie bei Erfolg gesetzt.

- **AC-6:** Given zwei verschiedene Nutzer mit je aktivem Premium-SMS im Ortsvergleich / When beide versenden und beim einen das Tageslimit erreicht oder eine Reservierung freigegeben wird / Then beeinflusst das den anderen nicht, und jeder Zähler läuft unter seiner eigenen `user_id` (nie `"default"`).
  - Test: zwei `user_id`s in getrennten Datenwurzeln; Zähler A ausgereizt, B sendet weiterhin; kein Zählereintrag unter `default`.

- **AC-7:** Given ein Ortsvergleich ohne Opt-in (`send_premium_sms=false`) oder ein Nutzer ohne Tier-Freigabe für Premium-SMS / When das Briefing versendet wird / Then wird über Premium-SMS nichts gesendet und der Zähler bleibt unverändert.
  - Test: Ende-zu-Ende über `effective_compare_briefing_channels` + `send_compare_report` mit Fake; beide Konstellationen (kein Opt-in, keine Freigabe) einzeln.

- **AC-8:** Given die Projektdoku beschreibt die Premium-SMS-Reichweite / When die Lieferung abgeschlossen ist / Then steht in `CLAUDE.md`, dass Premium-SMS Versandkanal im Trip-Briefing UND im Ortsvergleich-Briefing ist (nicht mehr „nur Trip-Briefing").
  - Test: `# doc-compliance-test` — Textprüfung der Zeile „Premium-SMS-Reichweite" in `CLAUDE.md` (zulässig als Doku-Ausnahme).

**Hinweis AC-4 des Issues (Schalter im UI ausblenden):** entfällt — der Schalter bleibt und
wirkt jetzt. Frontend unverändert.

## Test Plan

Kernschicht (deterministisch, ohne Netz): `tests/tdd/test_compare_premium_sms_versand.py`,
nach Verhalten benannt. Fake am Transport `output.channels.premium_sms` (kein Mock-Theater:
der Zähler und die Reservierung laufen echt, nur der Versand ist ersetzt). Ausführung nur mit
benannter Testdatei (`uv run pytest tests/tdd/test_compare_premium_sms_versand.py`).
Zusätzlich prüfen: `tests/test_success_status_guard.py` (Erfolgs-Ratsche), ob
`send_compare_report` betroffen ist, und die bestehenden Compare-Versandtests.

Adversary-Mutationsprobe (Pflicht): (a) Zweig entfernen, (b) `release_reservation` im
Fehlerpfad entfernen, (c) `failed_channels.append` entfernen, (d) `premium_sms_sink` im
Aufrufer nicht durchreichen — jede Verfälschung muss einen benannten Test rot machen.

**Live-Nachweis (eigener Punkt, kein AC-Ersatz):** Staging (`https://staging.gregor20.henemm.com`),
Test-Preset, Versand an die Test-Empfänger, **zweite seven.io-Nummer als Empfangsgerät**
(sendet und empfängt); Ankunft und Kurzform-Text am Gerät prüfen. Nie Sammelversand über alle
Presets, nie Produktiv-Empfänger.

### Live-Nachweis (durchgeführt 2026-09-26, Merge 5de80678)

- **Staging** (Validator-Konto, 1 Test-Preset mit 3 Orten): Einzelversand HTTP 200, Premium-Tageszähler 0→1, Compare-Mail-Validator Exit 0. Physische Zustellung dort `NOT_MEASURABLE_ON_STAGING` (nur Sandbox-Key).
- **Produktion** (temporäres Test-Konto, 1 Test-Preset, Einzelversand): seven.io-Journal `dlr=DELIVERED` an der zweiten Nummer; Text 128 Zeichen, 1 Segment, GSM-7 (`Vergleich 26.09.: T1 Garmisch … +1 Orte`); Prod-Log „premium_sms … über seven.io gesendet" in derselben Sekunde.
- **Fehlerpfad live:** ungültige Rückadresse → seven.io-Code 202 → Reservierung freigegeben, Warnzeile `reason_code=premium_sms_send_failed`, Versand lief weiter (fail-soft).
- Testkonto, Preset, Orte und gelernte Rückadresse danach vollständig entfernt.
- Nebenbefunde (nicht Teil dieser Spec, gebucht in #1199): Ortsvergleich-Versand bricht bei fehlgeschlagener E-Mail mit HTTP 500 ab, bevor Premium-SMS drankommt; Plus-Adressen scheitern an der Resend-Allowlist; numerischer seven.io-`from` wird zu „InfoSMS".

## Known Limitations

- Konsolidierung der Premium-SMS-Zweig-Kopien (Trip ~Z.642/~Z.800, Alarm ~Z.1201,
  Vergleich neu) und die „gemeinsame Kanal-Schleife" (#1412) sind bewusst nicht Teil dieser
  Lieferung (LoC-Limit 250, Regressionsrisiko im Trip-Versand) — Sammel-Issue #1199.
- Kein Nachhol-Mechanismus für gescheiterte Premium-SMS im Ortsvergleich (fail-soft, nur
  sichtbar); Kostenstelle/Kontingente je Kanal bleibt #1702.
- Die Kurzform ist `render_compare_sms` (153 Zeichen GSM-7); ein eigener Garmin-Renderer
  existiert nicht.
- Dass die SMS physisch am Garmin-Gerät ankommt, ist nur über den Live-Nachweis mit der
  zweiten seven.io-Nummer belegbar, nicht im Kern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; berührt ADR-0049 (Premium-SMS) nur nachvollziehend.
- **Rationale:** Verdrahtung eines bereits beschlossenen Kanals in einem weiteren Versandpfad,
  keine neue Entscheidungsfläche.

## Changelog

- 2026-09-26: Initial spec created (Issue #2275, Workflow fix-2275-compare-premium-sms)
