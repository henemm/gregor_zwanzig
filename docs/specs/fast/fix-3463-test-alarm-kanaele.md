---
created: 2026-11-27
issue: 3463
status: draft
---
# Mini-Spec: fix-3463-test-alarm-kanaele

Issue #3463 (Befund aus der Staging-Abnahme von #3441, Nebenbefund aus #3458; Epic #2913).
Reine Änderung an der Staging-Abnahme `frontend/e2e/hub-test-alarm.staging.spec.ts`, kein Produktionscode.

## Was ändert sich
- AC-2/AC-8/AC-17 (echter Versand): Die Kanalerwartung prüft nicht mehr „genau E-Mail und Telegram“, sondern
  „enthält mindestens `email` und `telegram`“ (`expect.arrayContaining`). Das Prüfkonto auf Staging hat alle vier
  Kanäle (SMS/Premium-SMS über Sandbox-Schlüssel, ohne Kosten); das Produkt meldet sie korrekt.
- Die Rückmeldung wird gegen die tatsächlich gemeldeten Kanäle geprüft: jeder Kanal aus `sent_channels`
  erscheint als „{Kanal} ✓“ in der Rückmeldung, E-Mail und Telegram immer.
- Alle Fälle (AC-1 Menü, AC-2/8/17 Versand, AC-7 Leer-Text) laufen einmal in **DE** und einmal in **EN**.
  Die Sprache wird am Prüfkonto per `PUT /api/auth/profile {language}` umgestellt und am Ende auf den
  vorherigen Wert zurückgesetzt (Muster aus `hub-kebab-rueckfragen.staging.spec.ts`). Erwartete Texte kommen
  aus den Katalogen `messages/{de,en}/test_schicken.json` und `zustellung.kanal.*` (DE „E-Mail“, EN „Email“).
- Kopfkommentar der Datei: „Echter Versand nur E-Mail und Telegram“ wird korrigiert (alle eingerichteten
  Alarm-Kanäle des Prüfkontos, SMS-Wege über Sandbox).

## Was darf sich nicht ändern
- Kein Produktionscode, keine Katalogtexte.
- Doppelklick = genau ein Request, Rückmeldung verschwindet nach ~5 s, HTTP 200 bleiben geprüft.
- Läuft weiter nur in /e2e-verify gegen Staging, nie gegen Produktion (`assertNotProdBaseURL`).
- Prüfkonto-Sprache steht nach dem Lauf wieder auf dem Ausgangswert.

## Acceptance Criteria
**AC-1:** Given das Prüfkonto auf Staging mit vier Alarm-Kanälen, When die Abnahme des Test-Alarms in DE läuft, Then ist der Versandfall grün, weil `sent_channels` E-Mail und Telegram enthält (zusätzliche Kanäle sind erlaubt).
**AC-2:** Given dasselbe Prüfkonto mit Sprache EN, When die Abnahme läuft, Then sind Menüzeile („Test alert“ nach „All set-up channels“ mit englischem Untertitel), Versand-Rückmeldung („Test alert sent: Email ✓ · Telegram ✓ …“) und Leer-Text englisch und grün.
**AC-3:** Given eine Antwort, in der `email` oder `telegram` in `sent_channels` fehlt, When der Versandfall prüft, Then wird er rot (Gegenprobe per Mutation der Erwartungsliste bzw. der Antwort).
**AC-4:** Given ein abgeschlossener Lauf, When die Sprache des Prüfkontos abgefragt wird, Then steht sie auf dem Wert vor dem Lauf.

## Manuelle Test-Schritte
1. Nach Staging-Deploy: `cd frontend && npx playwright test --config playwright.3441-test-alarm.staging.config.ts` → alle Fälle DE und EN grün.
2. Gegenprobe: in einer Kopie die Erwartung auf `['email','telegram','xyz']` erweitern → Versandfall rot; zurück.
3. Danach `GET /api/auth/profile` → `language` wie vorher.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `frontend/e2e/hub-test-alarm.staging.spec.ts` (DE/EN-Schleife, Mindestmenge der Kanäle)
