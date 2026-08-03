# Mini-Spec: Versandwege erkennen selbst, dass sie aus einem Testlauf kommen

**Issue #1476.** Wiederholungsfall: Ein Testlauf hat dem PO eine echte
Telegram-Nachricht geschickt. Vorgeschichte: #1219 (Mail), #1288, #1363 (Telegram) —
drei Anläufe, das Problem besteht fort.

## Warum die bestehenden Wächter nicht greifen

`src/output/channels/telegram.py` hat drei Wächter. **Alle drei beginnen mit:**

```python
if not self._settings.is_test_mode:
    return
```

`is_test_mode` setzt nur `Settings.for_testing()` / `with_user_profile()`. Ein Skript,
das `Settings()` **normal** lädt — der typische Fall, wenn ein Agent schnell etwas
nachstellt — läuft mit `is_test_mode=False`, `env="production"`, **auch aus einem
Arbeitsordner**. Damit schalten sich alle drei Wächter ab.

**Der gefährliche Fall ist genau der, der den Schalter nicht setzt.** Jede weitere
Verschärfung *innerhalb* der Wächter ist wirkungslos — das belegt die Historie.

Gemessen am 2026-08-03: ein Diagnose-Skript in `worktrees/intake-1394` meldete
`Testmodus: False | Umgebung: production`.

## Die Regel

Der Schutz hängt ab jetzt am **Ort, von dem der Code läuft** — nicht an einem Schalter:

| Herkunft des laufenden Codes | Einstufung |
|---|---|
| `/home/hem/gregor_zwanzig/src/...` | Produktionsdienst |
| `/home/hem/gregor_zwanzig_staging/src/...` | Staging-Dienst |
| **alles andere** (Arbeitsordner, Klon, beliebiger Pfad) | **Testlauf** |

Ableitung über `Path(__file__).resolve()` — von einem aufrufenden Skript nicht
abschaltbar, unabhängig von `.env`, `is_test_mode` und `env`.

**Bei Einstufung „Testlauf":** Der Prod-Chat und der Prod-Bot sind unzulässig. Ist eine
Test-Chat-ID konfiguriert, wird **darauf umgeschaltet** (mit Protokollzeile). Fehlt sie,
harter Fehler mit klarer Meldung. **Nicht** pauschal blockieren — Telegram-Tests sollen
ausdrücklich möglich bleiben (PO-Vorgabe 2026-08-03: „Es sollen ja auch Telegram-Tests
durchgeführt werden. Aber mit der Staging-Umgebung.").

Die drei bestehenden Wächter bleiben unverändert bestehen — sie sind nicht falsch, nur
unvollständig. Der neue Schutz liegt **davor** und greift unabhängig von ihnen.

## Acceptance Criteria

- **AC-1:** Given Code, der aus einem Arbeitsordner läuft, und eine normal geladene
  Konfiguration (`Settings()`, `is_test_mode=False`, `env="production"`) / When eine
  Telegram-Nachricht an die Produktions-Chat-ID abgeschickt wird / Then geht **keine**
  Nachricht an diese ID — es wird auf die Test-Chat-ID umgeschaltet. **Das ist der
  Aufruf, der heute durchgeht.**
- **AC-2:** Given dieselbe Lage, aber **keine** Test-Chat-ID konfiguriert / When
  gesendet wird / Then bricht der Versand mit einer verständlichen Meldung ab, die den
  Grund nennt (Herkunft = Testlauf) — statt still an den echten Empfänger zu senden.
- **AC-3:** Given der echte Produktionsdienst (Code unter `/home/hem/gregor_zwanzig/`) /
  When eine Nachricht an die Produktions-Chat-ID geht / Then wird sie **unverändert**
  zugestellt. Der Schutz darf den Produktivbetrieb nicht antasten.
- **AC-4:** Given der Staging-Dienst (Code unter `/home/hem/gregor_zwanzig_staging/`) /
  When gesendet wird / Then bleibt das heutige Verhalten unverändert (eigener Bot,
  Test-Chat-ID).
- **AC-5:** Given eine Umschaltung hat stattgefunden / When das Protokoll gelesen wird /
  Then steht dort **einmal** eine Zeile mit dem Grund und der Ziel-Chat-ID — eine
  stille Umleitung wäre wieder ein blinder Fleck.
- **AC-6:** Given der E-Mail-Versandweg (`src/output/channels/email.py`) und der
  SMS-Weg / When dieselbe Prüfung angelegt wird / Then gilt dort dieselbe Regel.
  **Vorher messen**, ob die Lücke dort tatsächlich besteht (`is_test_mode`-Abhängigkeit
  prüfen) — und das Messergebnis berichten, statt es anzunehmen.

## Was sich nicht ändern darf

- **Der Produktivbetrieb.** Die täglichen Briefings und Alarme laufen weiter wie bisher.
- Die drei bestehenden Wächter bleiben. Kein Umbau von `Settings`, kein neues Flag.
- Keine Änderung an der Sperrliste `egress_guard.py`.

## Gegenprobe (Mutations-Pflicht)

1. Herkunftsprüfung entfernen → **AC-1-Test muss rot werden.**
2. Umschaltung auf die Test-ID entfernen (nur protokollieren) → AC-1 muss rot werden.
3. Prüfung so verdrehen, dass sie den Produktionspfad als Testlauf einstuft → **AC-3
   muss rot werden** (der Produktivbetrieb darf nicht kaputtgehen).

## Manuelle Bestätigung

Ein kleines Skript im Arbeitsordner, das `Settings()` normal lädt und an die
Produktions-Chat-ID zu senden versucht, darf **keine** Nachricht beim PO auslösen.
Genau dieser Aufruf hat heute eine ausgelöst.
