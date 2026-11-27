---
entity_id: chk_3181_premium_orte_nachkontrolle
type: feature
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: chk-3181-premium-orte
tags: [nachkontrolle, prod, premium-sms, orte, seven-io, pruefung]
---

# Nachkontrolle Prod: Orte-Kurzform per Premium-SMS echt zugestellt (Issue #3181, aus #3172)

## Approval

- [ ] Approved

## Purpose

Nach #3172 schreibt die Orte-SMS je Ort eine Token-Zeile (`O1 … O2 …`, ohne Ortsnamen). Zugestellt geprüft sind Telegram, SMS und Mail, der Empfang der Premium-SMS nicht, weil Staging nur den Sandbox-Schlüssel hat. Diese Prüfung belegt auf Produktion mit zwei echten Premium-SMS (1 Ort, 3 Orte), dass die Kurzform ankommt, höchstens 153 Zeichen lang und GSM-7 ist und keinen Ortsnamen trägt. Es ist eine reine Prüfung ohne Produktcode-Änderung; das Ergebnis ist ein Nachweis im Issue #3181.

## Source

- **File:** keine Codeänderung. Geprüft wird `src/output/renderers/comparison.py` (`render_compare_sms`, Premium-Neukürzung auf 153) über den Versandweg `api/routers/briefings_send.py` (`POST /api/briefings/{id}/send?kind=vergleich&channel=premium_sms`) und `src/services/notification_service.py` (`send_premium_sms`).
- **Identifier:** Nachweis über `.claude/tools/seven_journal.py outbound` (seven.io-Ausgangsjournal) und das Prod-Log.

> **Schicht-Hinweis:** Python-Core (Prod-Core-Prozess, FastAPI intern Port 8000). Kein Go-Code, kein Frontend. Es wird nichts in `src/`, `api/`, `internal/` oder `frontend/` geändert.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht berührt (keine neue Komponente).
> - **Mandantentrennung:** Das Testkonto hat eine eigene, nur für diese Prüfung vergebene Konto-ID, nie `default`. Echte Konten (`default`, `henning`, `steffi`, `validator-issue110`) werden nicht gelesen oder verändert. Die Kontenliste wird vor und nach dem Lauf verglichen.
> - **Kanäle:** Geprüft wird der Kanal Premium-SMS; E-Mail, Telegram und SMS sind in #3172 belegt.

## Scope

**In Scope:** Ein Orts-Vergleich mit 1 Ort und einer mit 3 Orten werden in Produktion über ein temporäres Testkonto per Premium-SMS an die zweite seven.io-Testnummer gesendet; Zustellung und Form (≤153 Zeichen, `O1 …`, keine Ortsnamen, GSM-7, 1 Segment) werden im seven.io-Ausgangsjournal und im Prod-Log nachgewiesen; danach wird das Testkonto vollständig entfernt.

**Nicht im Scope:** Änderungen an Produktcode, Tests oder Formdoku; Reparatur bei Fehlschlag (dann eigenes Bug-Issue).

## Estimated Scope

- **LoC:** 0 im Produktcode
- **Files:** 1 neue Spec; temporäre Prod-Daten eines Testkontos (angelegt und vollständig entfernt)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `docs/specs/modules/chk_3181_premium_orte_nachkontrolle.md` | CREATE | diese Spec |
| `docs/context/chk-3181-premium-orte.md` | CREATE | Kontext und Analyse |
| Prod-Daten eines temporären Testkontos | CREATE, dann DELETE | Konto, 3 Orte, 2 Orte-Vergleiche; nur für den Lauf |

Kein Produktcode, kein Kern-Test, keine Doku-Änderung außer dem Nachweis im Issue.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Prod-Core (FastAPI, Port 8000) | service | Einziger Prozess, der echt über seven.io sendet (Herkunftssperre `seven_io_base.py`) |
| seven.io Prod-Schlüssel (`GZ_SEVEN_API_KEY`, nur Prod-`.env`) | secret | Echtversand; wird nie ausgegeben |
| zweite seven.io-Nummer | config | Empfänger (Rückadresse des Testkontos); Nummer nie in Doku oder Issue |
| `.claude/tools/seven_journal.py` | tool | Lesen des Ausgangsjournals (`outbound --since`, Nummern gekürzt) |
| `src/output/channels/recipient.py` (`PremiumSmsRecipient.for_user`) | module | Empfänger aus `premium_sms_reply_to`, Rückadresse eindeutig, Frist 30 Tage |
| `src/output/renderers/comparison.py` | module | Orte-Token-Zeile, Premium-Grenze 153 |
| `feat_3172_orte_sms_token_zeile.md`, ADR-0125 | spec | Soll-Form |
| #2275 (Kommentar 26.09.2026) | issue | Vorbild für den Nachweis auf Prod |

## Implementation Details

Ablauf (jeder Schritt bricht bei Fehler ab; kein Wiederholen):

1. **Rückadresse prüfen.** Über alle Prod-`user.json` maskiert prüfen, dass die zweite Nummer nirgends als `premium_sms_reply_to` mit gültiger Frist steht (Eindeutigkeitsprüfung `_check_reply_address_unique`). Steht sie an einem anderen Konto, stoppen und klären; am Konto eines echten Nutzers wird nichts geändert.
2. **Kostenloser Vorab-Render** im Worktree, ohne Versand: Kurzform für 1 Ort und 3 Orte, Länge ≤ 153, GSM-7, kein Ortsname.
3. **Testkonto anlegen** als `claude-gregor` unter `/var/lib/gregor/users/<eigene Prüf-ID>/`: `user.json` mit Tarif Premium, `premium_sms_reply_to` = zweite Nummer, `premium_sms_reply_at` = jetzt minus 1 Minute (RFC3339 UTC, Frist 30 Tage). **Kein `is_test_user`** (würde auf den Sandbox-Schlüssel umlenken, `config.py`, Guard `seven_io_base.py`). Dazu 3 Orte und 2 Orte-Vergleiche (Kanal Premium-SMS, 1 Ort bzw. 3 Orte, Tagesfenster 6–18). Die Kontenliste vorher festhalten.
4. **Versand im Prod-Core-Prozess** (Herkunftssperre: Worktree-Skripte senden nie echt): je Vergleich ein Aufruf von `127.0.0.1:8000/api/briefings/<id>/send?user_id=<Prüf-ID>&kind=vergleich&channel=premium_sms` mit Pflicht-Header `X-GZ-Core-Auth` (Secret aus der Prod-`.env`, nie ausgegeben). Erwartet `sent_channels:["premium_sms"]`. Genau 2 SMS.
5. **Nachweis erheben:** seven.io-Ausgangsjournal für heute (2 Einträge an der zweiten Nummer, `dlr=DELIVERED`, Text, Länge, Segmente) und Prod-Logzeile „premium_sms … über seven.io gesendet“ in derselben Minute.
6. **Aufräumen:** Konto-Ordner vollständig entfernen, Suche nach der Prüf-ID liefert nichts, Kontenliste nachher gleich vorher.
7. **Ergebnis als Kommentar in #3181** (ohne Nummern, Konto-IDs, Schlüssel; öffentliches Repo). Bei Erfolg Issue schließen; bei Misserfolg neues Bug-Issue mit Befund (keine Reparatur in diesem Workflow).

## Expected Behavior

- **Input:** temporäres Prod-Testkonto mit Premium-Tarif, zwei Orte-Vergleichen (1 Ort, 3 Orte), zweite seven.io-Nummer als Empfänger.
- **Output:** zwei zugestellte Premium-SMS, Form `O1 …` bzw. `O1 … O2 … O3 …`, je ≤ 153 Zeichen, GSM-7, 1 Segment, ohne Ortsnamen. Der Inhalt (Werte) ist wetterabhängig; geprüft werden Form und Zustellung, nicht konkrete Werte.
- **Side effects:** genau 2 kostenpflichtige Premium-SMS; Testdaten auf Prod, danach vollständig entfernt. Wird die Kürzung nötig, stehen mindestens `O1` und `O2` und der Hinweis ` +k Orte`.

## Acceptance Criteria

- **AC-1:** Given das Prod-Testkonto mit Premium-Tarif, gültiger Rückadresse (zweite Nummer) und einem Orte-Vergleich mit genau einem Ort / When der Handversand für Kanal Premium-SMS im Prod-Core ausgelöst wird / Then ist die SMS an der zweiten Nummer zugestellt (Ausgangsjournal `dlr=DELIVERED`), beginnt mit `O1 `, ist höchstens 153 Zeichen lang, reines GSM-7, ein Segment und enthält keinen Ortsnamen.
  - Test: Live-Lauf auf Prod; Nachweis im seven.io-Ausgangsjournal (Status, Text, Länge, Segment), ergänzt durch den kostenlosen Vorab-Render derselben Form.

- **AC-2:** Given das Testkonto ohne `is_test_user`, mit eindeutiger Rückadresse nicht älter als 30 Tage und der Versand ausgelöst im Prod-Core-Prozess mit gültigem Secret-Header / When der Handversand antwortet / Then lautet die Antwort `sent_channels:["premium_sms"]`, und es gehen insgesamt genau zwei SMS hinaus (keine über die zwei Versuche hinaus).
  - Test: Antwort des Handversands und Anzahl der Journal-Einträge des Laufs gleich 2.

- **AC-3:** Given dasselbe Testkonto mit einem Orte-Vergleich über drei Orte / When der Handversand für Kanal Premium-SMS ausgelöst wird / Then ist die SMS zugestellt (`dlr=DELIVERED`), beginnt mit `O1 `, enthält `O1`, `O2` und `O3` (bei Kürzung mindestens `O1` und `O2` und den Hinweis ` +k Orte`), ist höchstens 153 Zeichen lang, GSM-7, ein Segment und ohne Ortsnamen.
  - Test: Live-Lauf auf Prod; Nachweis im seven.io-Ausgangsjournal, Text gegen die Form `O1 … O2 … O3 …` geprüft.

- **AC-4:** Given die beiden ausgelösten Versände / When das Prod-Log der Versandminute gelesen wird / Then zeigt es für das Testkonto je einen Versand über seven.io („premium_sms … über seven.io gesendet“) in derselben Minute wie den Journal-Eintrag.
  - Test: Prod-Log (Dienst `gregor-python`) gegen den Zeitstempel des Journal-Eintrags.

- **AC-5:** Given der Lauf ist beendet, egal ob erfolgreich oder abgebrochen / When aufgeräumt wird / Then ist das Testkonto mit allen Dateien (Konto, Orte, Orte-Vergleiche, Rückadresse) entfernt, die Suche nach der Prüf-ID findet nichts, die Kontenliste ist nachher gleich vorher und die echten Konten sind unverändert.
  - Test: Verzeichnisvergleich der Konten vor und nach dem Lauf plus leere Suche nach der Prüf-ID.

- **AC-6:** Given der Nachweis liegt vor / When er als Kommentar in Issue #3181 eingetragen wird / Then enthält er Zustellstatus, Länge, Segmente, Form und Logbeleg beider SMS, aber keine Telefonnummern, keine Konto-IDs und keine Schlüssel.
  - Test: Durchsicht des Kommentars auf Nummern, Konto-IDs und Schlüssel vor dem Absenden (öffentliches Repo).

- **AC-7:** Given eine der beiden SMS wird nicht zugestellt oder ist formwidrig (länger als 153 Zeichen, Ortsname, Nicht-GSM-7, mehr als ein Segment) / When der Befund feststeht / Then wird nicht über die zwei SMS hinaus wiederholt, das Testkonto wird trotzdem vollständig aufgeräumt, und es entsteht ein neues Bug-Issue mit dem Befund (ohne Nummern, Konto-IDs, Schlüssel); #3181 wird nicht geschlossen.
  - Test: Fehlschlagpfad beim Lauf; neues Bug-Issue mit Befund, Zahl der Journal-Einträge weiterhin höchstens 2.

## Test Plan

### Automated Tests (TDD RED)

- Kein neuer Kern-Test: Die Form ist durch `tests/tdd/test_3172_orte_sms_token_zeile.py` (AC-1 bis AC-8 aus #3172) bereits in der Kern-Schicht belegt; diese Prüfung ändert keinen Code.
- Kostenloser Vorab-Render (Scratchpad, nicht ausgeliefert): Kurzform für 1 Ort und 3 Orte ohne Versand, Länge ≤ 153, GSM-7, keine Ortsnamen. Er ist Vorprüfung, kein Ersatz für den Live-Nachweis.

### Live-Nachweis (Prod)

- seven.io-Ausgangsjournal (`seven_journal.py outbound --since <heute>`): zwei Einträge, `dlr=DELIVERED`, Text, Länge, Segment.
- Prod-Log: Versand über seven.io für das Testkonto in derselben Minute.

## Definition of Done

- AC-1 bis AC-6 mit Live-Nachweis belegt (Journal-Einträge, Prod-Log, Kontenliste vorher = nachher).
- Genau 2 Premium-SMS versendet, keine weitere.
- Testkonto und alle seine Dateien in Produktion entfernt.
- Nachweis-Kommentar in #3181 ohne Telefonnummern, Konto-IDs, Schlüssel; #3181 geschlossen.
- Bei Fehlschlag (AC-7): Bug-Issue angelegt und einsortiert, #3181 bleibt offen.

## Known Limitations

- Der Inhalt der Token ist wetterabhängig; geprüft wird Form und Zustellung, nicht konkrete Werte.
- Genau 2 Premium-SMS Kosten; ohne Befund wird nicht wiederholt.
- Das Auto-Mode-Klassifizierungsverfahren kann Prod-Schreibzugriffe blocken; dann wird der PO in Alltagssprache um Freigabe gebeten, nicht umgangen.
- Worktree-Skripte können nie echt senden (Herkunftssperre); der Versand läuft ausschließlich im Prod-Core.

## Out of Scope

- Reparatur bei Fehlschlag (eigenes Bug-Issue).
- Trip-Premium-SMS, Mail, Telegram, SMS (in #3172 geprüft).
- Änderungen an Konten, Trips oder Orten des PO.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Nachkontrolle ohne Entscheidung; die Form folgt ADR-0125.

## Changelog

- 2026-11-27: Initial spec created (Issue #3181, Nachkontrolle zu #3172)
