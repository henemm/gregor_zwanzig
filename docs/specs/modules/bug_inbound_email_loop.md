# Spec: Bug Fix — Inbound Email Reader Feedback Loop

## Changelog
- 2026-06-09: Erstellt (Bug-Fix, Issue: Feedback-Loop durch mail_from in _authorize)

## Problem

Der `InboundEmailReader` verarbeitete ausgehende System-E-Mails als eingehende Nutzerbefehle.

**Ursache:** `_authorize()` erlaubt `settings.mail_from` als Absender. `settings.mail_from` ist die System-Sendeadresse (`gregor_zwanzig@henemm.com`). Stalwart kopiert gesendete E-Mails zurück in den Posteingang → Reader liest sie → sendet "Trip nicht gefunden" → auch diese landen im Inbox → endloser Loop.

## Lösung

`mail_from` aus der erlaubten-Absender-Menge in `_authorize()` entfernen. Nur `mail_to` (die Nutzer-Empfangsadresse) und `inbound_address` (optionale Plus-Adresse) sind legitime Befehlsgeber.

## Affected Files

- `src/services/inbound_email_reader.py` — `_authorize()` Methode

## Acceptance Criteria

**AC-1:** Given der Inbound Reader empfängt eine E-Mail, deren Absender mit `settings.mail_from` übereinstimmt (System-Sendeadresse) / When `_authorize()` aufgerufen wird / Then gibt die Methode `False` zurück und die E-Mail wird nicht verarbeitet.

**AC-2:** Given der Inbound Reader empfängt eine E-Mail von der Nutzer-Adresse (`settings.mail_to`) / When `_authorize()` aufgerufen wird / Then gibt die Methode `True` zurück und die E-Mail wird verarbeitet.

**AC-3:** Given der Inbound Reader empfängt eine E-Mail von einer unbekannten Adresse (weder `mail_to` noch `inbound_address`) / When `_authorize()` aufgerufen wird / Then gibt die Methode `False` zurück.

**AC-4:** Given `inbound_address` ist konfiguriert und eine E-Mail kommt von dieser Adresse / When `_authorize()` aufgerufen wird / Then gibt die Methode `True` zurück (bestehende Funktion, keine Regression).
