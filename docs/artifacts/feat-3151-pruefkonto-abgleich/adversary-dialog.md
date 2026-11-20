# Adversary Dialog — feat-3151-pruefkonto-abgleich
Spec: docs/specs/modules/feat_3151_pruefkonto_abgleich.md
Datum: 2026-11-20 09:13

## Checkliste
- [x] **Input:** Aufruf des Seeds auf dem Staging-Host mit Prüfkonto-Zugang; danach Abgleich DE+EN.
- [x] **Output:** Trip und Vergleich zeigen Briefing E-Mail+Telegram, Alarme alle vier Kanäle mit Schwellen LOW/LOW/MODERATE/HIGH; `elementliste_besitzer.json` enthält keinen `#2967`-Eintrag mehr.
- [x] **Side effects:** Schreibzugriffe nur auf eigene Seed-Datensätze des Prüfkontos; kein Versand an echte Geräte oder Adressen.
- [x] **AC-1:** Given der Seed-Code / When die Soll-Funktionen für Trip und Vergleich ausgewertet werden und der Seed gegen den Fake-Server läuft / Then stehen am Trip `report_config` mit `send_email`/`send_telegram` true und `send_sms`/`send_premium_sms` false, `alert_channels` alle vier true und Schwellen email/telegram `LOW`, sms `MODERATE`, premium_sms `HIGH`, und am Vergleich dieselben Werte als `send_*`, explizites `alert_channels` und `alert_channel_thresholds` (Mockup Z.373-374).
- [x] **AC-2:** Given Trip und Vergleich haben im Konto Fremdfelder und einen weiteren Kanalschlüssel mit eigenem Wert / When der Seed läuft / Then werden nur die Soll-Teilobjekte der Kanalauswahl gesendet und gemerged, alle Fremdfelder bleiben erhalten (Read-Modify-Write, nie Replace).
- [x] **AC-3:** Given der Seed ist einmal gelaufen und Go normalisiert bzw. leitet `alert_channels` ab (im Fake nachgebildet) / When er ein zweites Mal läuft / Then erfolgt kein Daten-Schreibzugriff auf Trip und Vergleich, der Zustand ist byte-gleich und der Exit-Code 0.
- [x] **AC-4:** Given zwei Nutzer mit eigenen Trips und Vergleichen im Fake-Server / When der Seed als Prüfkonto läuft / Then ändert er nur dessen Datensätze, der zweite Nutzer bleibt mit allen neuen Feldern unverändert.
- [x] **AC-5:** Given der Seed setzt Alarm-Kanäle auf alle vier und der Vergleich läuft täglich / When der Staging-Scheduler läuft / Then geht nichts an echte Geräte oder Adressen: SMS über die Sandbox, Telegram über den Test-Bot, Ziele fiktiv oder im Test-Postfach; ist das nicht belegbar, steht der Vergleich auf `schedule: manual`.
- [x] **AC-6:** Given der Seed ist auf Staging deployt / When er zweimal läuft und danach der Abgleich DE und EN / Then enden alle Läufe mit Exit 0, Lauf 2 des Seeds schreibt nichts, fehlender GR221-Trip, Münsterland und Orte sind wiederhergestellt und der Schreib-Tripwire des Abgleichs meldet 0.
- [x] **AC-7:** Given die frischen Abgleich-Berichte / When die 247 `#2967`-Einträge neu klassifiziert werden / Then sind aufgelöste Einträge entfernt, bestätigte Abweichungen auf #2799/#2867, #3122, #3194 oder neue Kind-Issues von Epic #2913 umgehängt, es bleibt kein Eintrag an `#2967` oder `#3145`, die Klassifizierung je Klasse steht als Kommentar in #3151 und der Zählwächter stimmt inklusive der neuen Verweise.
- [x] **AC-8:** Given Issue-Kommentare und Issue-Texte dieser Arbeit / When sie veröffentlicht werden / Then enthalten sie kein bares At-Handle; Telegram- und Mockup-Namen stehen in Backticks.

## Dialog

### Runde 1
**Adversary:** Tests (3 Python-Dateien) alle gruen, Frontend elementliste*: 354 pass, 0 fail, 0 skipped. Mutations-Gegenprobe per String-Ersetzung (Sicherung im Scratchpad, sha256 vorher = nachher 50063e06...): sms MODERATE->LOW, send_telegram False, premium_sms fehlt, _merge ersetzt statt merged, Vergleich ohne explizite alert_channels, _enthaelt immer ungleich (zweiter Lauf schreibt), Trip ohne Kanalauswahl gesendet, Vergleich ohne _merge: alle 8 von den Tests gefangen. Besitzerliste: 871 vorher, 692 nachher; 179 entfernt, 68 umgehaengt (23/19/10/8/4/4), 0 hinzugefuegt: 247-179-68=0. Alle 74 entfernten element-Eintraege sind in abgleich-de.json und -en.json gefunden; alle 105 entfernten zusaetzlich-Eintraege treffen mit Text+ctx+reiter in keinem Bericht. Issues 3202-3205 und neuer Kommentar: kein bares At-Handle; die vier Issues sind Sub-Issues von Epic 2913. Artefakte: keine E-Mail-Adresse, kein Prueefkonto-Name, keine Secrets.
Befund (AC-5): kein eigener neuer Test fuer Versandsicherheit des taeglichen Vergleichs; Beleg nur Runbook und bestehender Test ac11_fl5 plus pruefe_kein_live_versand (LOW, F001). Alte 3151-Kommentare (19.11., nicht aus dieser Arbeit) enthalten ein bares At-Handle in einem Entschuldigungskommentar: nicht Teil dieser Arbeit (F002, LOW, informativ).
**Implementierer:** n/a

### Runde 2
**Adversary:** Zweite Runde: Zaehlwaechter test_2913_c2_besitzerliste.py:129-136 stimmt mit tatsaechlicher Verteilung ueberein (#3194 100->108 = 2+6, #3122 10->14, Summe der Neu-Verweise 56+12). Seed-Lauf-2 (seed-lauf-2.txt): 0 Daten-Schreibaufrufe, nur staging-seed. Vergleich schedule daily: Guards in telegram.py:273/291 und seven_io_base.py:134 und config.py for_testing existieren (Belegstellen im Runbook korrekt). Keine Regression: _merge ersetzt nur die Zuweisung in sichere_datensatz und sichere_vergleich, Fremdfelder bleiben (ac2-Test).
**Implementierer:** keine Gegenrede noetig.

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Verdict

Finding:
  ID: F001
  Severity: LOW
  Category: edge_case
  Code reference: tests/tdd/test_staging_pruefkonto_mockupdaten.py:1109
  Description: Es gibt keinen eigenen 3151-Test, der den Vergleich auf manual oder die Sandbox-Belege prueft; nur der bestehende fiktive-Kanalwerte-Test.
  Spec requirement: AC-5 — Kern-Test prueft fiktive Ziele und manual bei fehlendem Beleg
  Conflict: Beleg (Guards) ist dokumentiert, aber nicht neu getestet; Beleg wird erbracht, daher kein Blocker.
  Remediation: optional Test, der soll_vergleich()["schedule"] und Ziele fixiert.

Confirmation:
  AC: AC-1
  Code reference: scripts/staging_pruefkonto_mockupdaten.py:237
  Evidence: Soll-Funktionen exakt wie Spec; Tests ac1 gruen, 3 Mutationen gefangen.
  Status: CONFIRMED

Confirmation:
  AC: AC-2
  Code reference: scripts/staging_pruefkonto_mockupdaten.py:200
  Evidence: _merge je Kanalschluessel; Mutation Replace faellt im Test auf.
  Status: CONFIRMED

Confirmation:
  AC: AC-3
  Code reference: scripts/staging_pruefkonto_mockupdaten.py:187
  Evidence: _enthaelt-Vergleich; Mutation immer-ungleich gefangen; seed-lauf-2 0 Daten-Schreibaufrufe.
  Status: CONFIRMED

Confirmation:
  AC: AC-4
  Code reference: tests/tdd/test_staging_pruefkonto_mockupdaten.py:1273
  Evidence: Zweitnutzer und default byte-gleich nach Lauf.
  Status: CONFIRMED

Confirmation:
  AC: AC-5
  Code reference: scripts/staging_pruefkonto_mockupdaten.py:282
  Evidence: Guards in src/app/config.py:365 for_testing, telegram.py:273, seven_io_base.py:134 existieren; Runbook docs/runbooks/staging_pruefkonto_seed.md nennt sie; pruefe_kein_live_versand Z.176.
  Status: CONFIRMED

Confirmation:
  AC: AC-6
  Code reference: docs/runbooks/staging_pruefkonto_seed.md:1
  Evidence: seed-lauf-1/-2 exit=0, Lauf 2 DATEN-SCHREIBAUFRUFE 0; Abgleich DE/EN laut Kommentar Exit 0, Tripwire 0.
  Status: CONFIRMED

Confirmation:
  AC: AC-7
  Code reference: docs/context/einstellungen_neu/elementliste_besitzer.json:1
  Evidence: 0 Eintraege #2967/#3145, Bilanz 247=179+68, Stichprobe gegen Berichte voll bestaetigt, Zaehlwaechter tests/test_2913_c2_besitzerliste.py:129 gruen.
  Status: CONFIRMED

Confirmation:
  AC: AC-8
  Code reference: tests/test_2913_c2_besitzerliste.py:129
  Evidence: Issues 3202-3205 und neuer Kommentar ohne bares At-Handle (Muster ausserhalb Backticks).
  Status: CONFIRMED

Tests: alle gruen (Python 3 Dateien, Frontend 354 pass, 0 fail, 0 skipped)

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════

## Geprüfte Dateien

- sha256:5e931def534d7f958b4c8620d035fb11a8bf04c25dfccd12bb9a1d489a307ae9  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:22d11abe0d2d5d4968beb32cd5340bd367669278ac68f6ec19dabea022488fc1  docs/runbooks/staging_pruefkonto_seed.md
- sha256:50063e069d0b4ff486e295928f76bf59bf8cd546fe8887281c7ac658af1d3956  scripts/staging_pruefkonto_mockupdaten.py
- sha256:d0f6a9b6f5776543a5b5d83f55ce79cd628cf4368ecb98399709b5f4899e0fef  tests/tdd/test_staging_pruefkonto_mockupdaten.py
- sha256:aa29751a6404374edaa3e9bcd1af0d4a05831221a5b90d4b85320059930a6b7f  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 04625e2fdb2cac1a7ab3f65cd835695b7a612cff
- blob:b5b36ca2b751bea43da532c185d4485b3dade85e  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:75aab3f87018a0d4191ba20273eff5d8f7cbc3b0  docs/runbooks/staging_pruefkonto_seed.md
- blob:9e5fea09d2dbbddba135a0dce2603e7d523041fc  scripts/staging_pruefkonto_mockupdaten.py
- blob:320af2bb05d73ac318bfc255a7df99642932129e  tests/tdd/test_staging_pruefkonto_mockupdaten.py
- blob:2f1c80d9306074c68defddc5ada1829b0c8f7909  tests/test_2913_c2_besitzerliste.py

## Geprüfte Dateien

- sha256:5e931def534d7f958b4c8620d035fb11a8bf04c25dfccd12bb9a1d489a307ae9  docs/context/einstellungen_neu/elementliste_besitzer.json
- sha256:22d11abe0d2d5d4968beb32cd5340bd367669278ac68f6ec19dabea022488fc1  docs/runbooks/staging_pruefkonto_seed.md
- sha256:50063e069d0b4ff486e295928f76bf59bf8cd546fe8887281c7ac658af1d3956  scripts/staging_pruefkonto_mockupdaten.py
- sha256:d0f6a9b6f5776543a5b5d83f55ce79cd628cf4368ecb98399709b5f4899e0fef  tests/tdd/test_staging_pruefkonto_mockupdaten.py
- sha256:aa29751a6404374edaa3e9bcd1af0d4a05831221a5b90d4b85320059930a6b7f  tests/test_2913_c2_besitzerliste.py

## Prüfbasis

- base: 04625e2fdb2cac1a7ab3f65cd835695b7a612cff
- blob:b5b36ca2b751bea43da532c185d4485b3dade85e  docs/context/einstellungen_neu/elementliste_besitzer.json
- blob:75aab3f87018a0d4191ba20273eff5d8f7cbc3b0  docs/runbooks/staging_pruefkonto_seed.md
- blob:9e5fea09d2dbbddba135a0dce2603e7d523041fc  scripts/staging_pruefkonto_mockupdaten.py
- blob:320af2bb05d73ac318bfc255a7df99642932129e  tests/tdd/test_staging_pruefkonto_mockupdaten.py
- blob:2f1c80d9306074c68defddc5ada1829b0c8f7909  tests/test_2913_c2_besitzerliste.py
