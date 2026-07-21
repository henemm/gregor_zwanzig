# Spec: #1124 Teil B — Compare-Validator sucht Mail per Header + BODY.PEEK

- **Issue:** #1124 (Teil B — Validator). Teil A (Produktiv-Header) ist bereits live.
- **Created:** 2026-07-15
- **Track:** Standard (Gate-Werkzeug)
- **ADR-Nr.:** keine
- **Betroffene Datei:** `.claude/hooks/email_spec_validator.py` (Funktion `_fetch_latest_message`)

## Kontext / Problem

`email_spec_validator.py` ist der Pflicht-Validator für den Compare-Mail-Pfad
(`X-GZ-Mail-Type: compare`). Sein IMAP-Helper `_fetch_latest_message()` hat zwei Defekte:

1. **Blinde Auswahl:** Er nimmt `all_ids[-1]` — die schlicht **neueste** Mail im Postfach,
   ohne den Marker-Header zu prüfen. Lag eine Warn-/Briefing-Mail obenauf, schlug der
   Prüfer an der falschen Mail an (real passiert bei der E2E von #1237, je ein kompletter
   Versand-Zyklus verloren). Erst durch Teil A tragen Compare-Mails überhaupt zuverlässig
   den Header — Teil B nutzt ihn zur korrekten Auswahl.
2. **`RFC822` statt `BODY.PEEK`:** Der Fetch markiert die geprüfte Mail als **gelesen**
   (`\Seen`), was Folgeläufe verfälscht.

`_fetch_latest_message()` ist **nicht** geteilt (nur innerhalb dieser Datei genutzt) — der
Briefing-Validator hat seinen eigenen Fetch. Scope bleibt auf diese eine Datei beschränkt.

## Ziel

Der Validator prüft **die neueste Mail mit `X-GZ-Mail-Type: compare`**, ohne eine Mail als
gelesen zu markieren. Fehlt eine solche Mail, schlägt er **laut** fehl (statt still die
falsche Mail zu prüfen).

## Acceptance Criteria

**AC-1:** Given ein Postfach, in dem die neueste Mail KEINEN `X-GZ-Mail-Type: compare`-Header
trägt (z. B. eine Warn-Mail obenauf), aber eine ältere Mail den Header `compare` trägt,
When der Validator die zu prüfende Mail auswählt, Then wählt er die neueste Mail **mit**
`X-GZ-Mail-Type: compare` und NICHT die (neuere) Nicht-Compare-Mail.

**AC-2:** Given mehrere Mails mit `X-GZ-Mail-Type: compare` im Postfach,
When der Validator auswählt, Then wählt er die **neueste** davon (höchste/ jüngste UID
zuerst, nicht eine ältere Compare-Mail).

**AC-3:** Given ein Postfach OHNE jede Mail mit `X-GZ-Mail-Type: compare`,
When der Validator die Mail zu holen versucht, Then bricht er mit einem klaren Fehler ab
(Meldung nennt „keine Compare-Mail (X-GZ-Mail-Type: compare)"), statt still eine
Nicht-Compare-Mail zu prüfen und fälschlich Erfolg/Misserfolg zu melden.

**AC-4:** Given der Validator holt eine Mail zur Prüfung,
When er sie per IMAP fetcht, Then verwendet er `BODY.PEEK[...]` und setzt dadurch das
`\Seen`-Flag der geprüften Mail NICHT (der ungelesen/gelesen-Zustand der Mail bleibt vor
und nach dem Lauf unverändert).

## Design-Entscheidungen

- **Auswahl newest-first mit Früh-Abbruch (kein festes Fenster):** Postfach kann groß sein
  (>10 000 Mails) und ist zudem **geteilt** (mehrere Validatoren/Test-Trips nutzen
  gregor-test@henemm.com). Der Validator scannt die Kandidaten von neu nach alt und prüft
  je Kandidat nur den Header (leichter `BODY.PEEK[HEADER]`-Fetch), **stoppt beim ersten
  `compare`-Treffer**. Im Normalfall (frisch versandte Compare-Mail ist die jüngste)
  endet der Scan nach 1 Fetch. Eine echte Compare-Mail wird so **nie verpasst** — egal
  wie viele Fremd-Mails obenauf liegen (behebt Adversary-Befund F001: ein festes Fenster
  hätte eine reale, aber tief liegende Compare-Mail übersehen und fälschlich AC-3
  gemeldet). Nur wenn im **gesamten** Postfach keine Compare-Mail existiert, wird der
  AC-3-Fehler erhoben.
- **Voll-Fetch nur der Treffer-Mail** ebenfalls per `BODY.PEEK[]` (kein `\Seen`).
- **Testbarkeit:** Die reine Auswahl-Logik (welche UID gewinnt bei gegebener
  UID→Header-Zuordnung) wird als separat testbare Funktion herausgelöst, sodass AC-1/AC-2/
  AC-3 deterministisch mit aufgezeichneten Header-Fixtures geprüft werden können — ohne
  Live-IMAP. AC-4 (`\Seen` unberührt) wird über einen Duck-typed IMAP-Fake geprüft, der
  die verwendeten Fetch-Kommandos aufzeichnet (Assertion: nur `BODY.PEEK`, nie `RFC822`).

## Was darf sich NICHT ändern

- Der öffentliche Vertrag `fetch_latest_email()` / `_extract_html_body()` und alle
  Plausibilitäts-Prüfungen (`validate_structure` etc.) bleiben unverändert.
- Der Briefing-Validator (`briefing_mail_validator.py`) wird nicht angefasst.
- Die Test-Postfach-Credential-Priorisierung (#972) bleibt erhalten.

## Manuelle Verifikation (Live-Schicht)

Auf Staging: (1) eine Nicht-Compare-Mail zustellen, danach (2) eine Compare-Mail auslösen,
dann eine dritte Nicht-Compare-Mail obenauf legen; Validator läuft → wählt die Compare-Mail
(2), nicht (3); Compare-Mail bleibt nach dem Lauf im selben Gelesen-Zustand.
