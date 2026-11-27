---
entity_id: fix_3219_selftest_botmenue_timeout
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
issue: 3219
workflow: fix-3219-selftest-botmenue-timeout
tags: [gate, deploy, selftest, honesty, telegram]
---

# Fix #3219 — Prod-Selbsttest: Bot-Menü-Prüfung tolerant gegen Telegram-Hänger

## Approval

- [ ] Approved

## Purpose

Der Prod-Selbsttest (`prod_selftest.py`) prüft nach dem Deploy, ob das Telegram-Bot-Menü in Produktion zum Soll passt. Dafür gibt es heute genau einen Abruf mit 8 Sekunden Zeitlimit. Hängt Telegram einmal kurz, meldet der Selbsttest "Regression in Produktion", Exit 1, und das Ticket lässt sich nicht schließen, obwohl Produktion intakt ist (Vorfall 2026-11-20, zwei Folgeläufe waren grün).

Der Fix gibt dem Menü-Abruf ein eigenes, großzügigeres Zeitlimit und bis zu drei Versuche. Bleibt Telegram trotzdem stumm, gilt das Menü als "nicht belegt" (eigener Status `UNREACHABLE`), nie als bestanden und nie als Regression. Ein tatsächlich falsches Menü bleibt ein Fehlschlag, ohne Wiederholung.

## Source

- **File:** `.claude/hooks/prod_selftest.py`
- **Identifier:** `check_bot_menu`, `_http_get`, `main` (Phase 4, Verdict und Fazit-Text)

> Schicht: reines Deploy-Werkzeug (`.claude/hooks/`), keine Produktlaufzeit. Kein Frontend, keine Go-API, kein Python-Core. Keine Nutzerdaten bewegt, keine Kanal-Inhalte geändert.

## Scope

**In Scope:**
- Menü-Abruf im Prod-Selbsttest: eigenes Zeitlimit (12 s), bis zu 3 Versuche mit Pause (2 s, 4 s), nur bei Zeitüberschreitung/Netzfehler und HTTP 429/5xx.
- Auswertung des HTTP-Status beim Menü-Abruf (429/5xx kein falsches inhaltliches FAIL mehr).
- Neuer Menü-Status `UNREACHABLE` mit eigener Fazit-Zeile, nicht blockierend, nie PASS.

**Out of Scope:**
- Zeitlimit und Verhalten der übrigen Prod-Proben (`PROBE_TIMEOUT = 8` bleibt).
- Strengere Regeln für Issues, die das Bot-Menü selbst ändern (eigene Policy-Frage, nicht Teil dieses Fixes).
- Wechsel der HTTP-Bibliothek (Messung zeigt keinen Python-seitigen Langsamkeitsgrund).

## Estimated Scope

- **LoC:** ~+60 / -5 (Quelldatei), ~+150 (Test)
- **Files:** 1 Quelldatei + 1 Testdatei
- **Effort:** low bis medium (Deploy-Gate, daher Adversary-Risiko hoch)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/prod_selftest.py::_http_get` | Funktion | Bekommt optionalen `timeout`-Parameter; `None` = `PROBE_TIMEOUT` |
| `.claude/hooks/prod_selftest.py::check_bot_menu` | Funktion | Abruf-Schleife, Statusbildung |
| `.claude/hooks/prod_selftest.py::main` | Funktion | Verdict und Fazit-Zeilen, Exit-Code |
| `.claude/hooks/prod_selftest.py::_check_bot_menu_prod` | Funktion | Aufrufer, Signatur bleibt kompatibel |
| `docs/specs/modules/fix_1367_selftest_auth_required.md` | Vorgänger | Muster: nicht Belegbares bekommt eigenen Status statt FAIL (`SKIPPED_AUTH`) |
| `docs/specs/modules/gate_honesty_mail_selftest.md` | Vorgänger | Gate-Ehrlichkeit: nicht Nachweisbares ist kein PASS |
| `tests/tdd/test_issue_685_selftest_menu_gate.py` | Testmuster | Lokaler HTTP-Socket-Server, bleibt grün |
| `tests/tdd/test_selftest_auth_redirect.py`, `test_selftest_auth_required.py`, `test_issue_671_bot_menu_autoset.py`, `test_prod_selftest_1708c_dead_trips_guard.py` | Bestandstests | Müssen grün bleiben |
| `/70-deploy` | Konsument | Exit 0 des Selbsttests ist die Freigabe für den Issue-Close |

## Implementation Details

Entscheidung (Tech Lead, Variante b): Nach Wiederholung weiter stumm = `UNREACHABLE`, Exit 0, eigene Fazit-Zeile. Begründung: Ein Telegram-Ausfall ist keine Deploy-Regression; derselbe Ansatz wie bei `SKIPPED_AUTH` (#1353/#1367). Kein PASS, damit die Ehrlichkeit bleibt.

Konstanten (per monkeypatch testbar): `MENU_TIMEOUT = 12`, `MENU_ATTEMPTS = 3`, `MENU_RETRY_PAUSE = 2` (Pause verdoppelt sich: 2 s, dann 4 s). `PROBE_TIMEOUT = 8` bleibt für alle anderen Proben.

Ablauf in `check_bot_menu` (Schleife nur um den Abruf):

| Antwort von Telegram | Wiederholen? | Ergebnis nach letztem Versuch |
|---|---|---|
| Zeitüberschreitung oder Netzfehler (`OSError`) | ja | `UNREACHABLE` |
| HTTP 429 oder 5xx | ja | `UNREACHABLE` |
| HTTP 200, Menü passt | nein | `PASS` |
| HTTP 200, Menü weicht ab | nein | `FAIL` |
| HTTP 200, Body nicht lesbar oder `ok:false` | nein | `FAIL` |
| HTTP 401 oder 404 (ungültiger Token) | nein | `FAIL` |

Ein Treffer in einem späteren Versuch (200 mit richtigem Menü) ergibt `PASS`. Das Detail von `UNREACHABLE` nennt Versuchszahl und letzte Ursache und enthält "nicht erreichbar".

`main`: `UNREACHABLE` setzt das Verdict nicht auf FAIL und ändert den Exit-Code nicht. Der Berichtsabschnitt Bot-Menü zeigt den Status. Eine zusätzliche Fazit-Zeile, unabhängig vom Verdict: "Telegram nicht erreichbar (nach 3 Versuchen) – Bot-Menü nicht belegt, keine Regression belegt". Das Fazit enthält in diesem Fall nicht "Regression in Produktion", außer andere Proben sind tatsächlich fehlgeschlagen.

Laufzeit im schlimmsten Fall: 3 × 12 s + 2 s + 4 s = 42 s.

Testansatz: echter lokaler HTTP-Socket-Server (Muster `test_issue_685_selftest_menu_gate.py`) mit verzögerndem oder skriptbarem Handler, der Anfragen zählt. `MENU_TIMEOUT`, `MENU_ATTEMPTS`, `MENU_RETRY_PAUSE` werden per monkeypatch klein gesetzt. Keine Mocks.

## Expected Behavior

- **Input:** Telegram-Antworten auf den Menü-Abruf (`getMyCommands`), Soll-Menü aus `src/output/channels/telegram.py`.
- **Output:** Menü-Status `PASS`, `FAIL`, `UNREACHABLE` oder (ohne Token) `SKIPPED`; Verdict, Bericht und Exit-Code entsprechend.
- **Side effects:** Keine. Der Selbsttest schreibt nur den Bericht.

## Acceptance Criteria

- **AC-1:** Given Telegram hängt beim ersten Menü-Abruf einmalig und liefert beim zweiten Abruf das richtige Menü / When der Prod-Selbsttest die Bot-Menü-Prüfung ausführt / Then gilt die Menü-Prüfung als bestanden, der Selbsttest kann das Ticket abschließen (Exit 0) und es gab genau zwei Abrufe.
  - Test: Lokaler Server lässt den ersten Request über das Zeitlimit hinaus hängen, antwortet beim zweiten mit dem Soll-Menü; Status PASS, Exit-Mapping 0, Request-Zähler = 2.

- **AC-2:** Given Telegram antwortet in allen drei Versuchen nicht (Zeitüberschreitung) / When die Bot-Menü-Prüfung ausgeführt und der Bericht geschrieben wird / Then lautet der Status "nicht erreichbar" (niemals bestanden), der Bericht sagt "Telegram nicht erreichbar … Bot-Menü nicht belegt, keine Regression belegt", das Fazit enthält nicht "Regression in Produktion" und der Exit-Code wird dadurch nicht 1.
  - Test: Lokaler Server hängt bei jedem Request; Status UNREACHABLE (nicht PASS), Request-Zähler = 3, Fazit-Text enthält die Nicht-erreichbar-Zeile und nicht "Regression in Produktion", Exit-Mapping 0.

- **AC-3:** Given Telegram liefert dauerhaft 429 oder 5xx / When die Bot-Menü-Prüfung ausgeführt wird / Then lautet der Status "nicht erreichbar" wie in AC-2; liefert Telegram erst 502 und dann 200 mit dem richtigen Menü, gilt die Prüfung als bestanden.
  - Test: Lokaler Server antwortet dauerhaft 503 (und separat 429): UNREACHABLE. Zweiter Server: 502, dann 200 mit Soll-Menü: PASS, zwei Abrufe.

- **AC-4:** Given Telegram antwortet sofort mit 200 und einem vom Soll abweichenden Menü / When die Bot-Menü-Prüfung ausgeführt wird / Then ist das Ergebnis wie bisher ein Fehlschlag, es gibt keinen Wiederholversuch (genau ein Abruf) und der Selbsttest endet mit Exit 1.
  - Test: Lokaler Server liefert 200 mit falschem Menü; Status FAIL, Request-Zähler = 1, Exit-Mapping 1, Fazit nennt weiterhin die Regression.

- **AC-5:** Given Telegram meldet einen ungültigen Token (401 oder 404) oder liefert einen unlesbaren Body oder `ok:false` / When die Bot-Menü-Prüfung ausgeführt wird / Then ist das Ergebnis ein Fehlschlag ohne Wiederholung, weil ein echter Konfigurationsfehler nicht als Telegram-Ausfall durchgehen darf.
  - Test: Lokaler Server liefert nacheinander in getrennten Läufen 401, 404, Müll-Body und `{"ok":false}`; jeweils Status FAIL und Request-Zähler = 1.

- **AC-6:** Given der Selbsttest probt Acceptance Criteria an Produktion oder es ist kein Telegram-Token hinterlegt / When der Selbsttest läuft / Then gilt für die AC-Proben weiter das Zeitlimit von 8 Sekunden unverändert, und ohne Token bleibt das bisherige Verhalten (Menü-Prüfung übersprungen) bestehen.
  - Test: `PROBE_TIMEOUT` ist weiterhin 8 und `_http_get` ohne `timeout` nutzt es (Probe gegen verzögernden lokalen Server bricht nach `PROBE_TIMEOUT` ab); ohne Token liefert die Menü-Prüfung weiterhin den Status SKIPPED, Exit 0. Bestandstests `test_issue_685_selftest_menu_gate.py` und `test_selftest_auth_redirect.py` bleiben grün.

- **AC-7:** Given Telegram bleibt im schlimmsten Fall stumm / When die Bot-Menü-Prüfung alle Versuche ausschöpft / Then dauert sie höchstens 3 × 12 s Zeitlimit plus 2 s und 4 s Pausen (insgesamt 42 s), nicht länger.
  - Test: Mit den echten Standardwerten sind `MENU_ATTEMPTS * MENU_TIMEOUT + Pausensumme` höchstens 42; mit klein gepatchten Konstanten (z. B. Zeitlimit 0,3 s, Pause 0,1 s) bleibt die gemessene Gesamtdauer des Dauer-Hänger-Falls unter 3 × Zeitlimit + Pausen + Toleranz.

## Test Plan

Neue Datei `tests/tdd/test_selftest_bot_menu_retry.py`, echter lokaler HTTP-Socket-Server mit zählendem, skriptbarem Handler, Konstanten per monkeypatch klein:
- AC-1: erster Abruf hängt > Zeitlimit, zweiter liefert richtiges Menü → PASS, genau 2 Anfragen.
- AC-2: alle Abrufe hängen → UNREACHABLE, Fazit-Zeile „nicht erreichbar“, kein „Regression in Produktion“, Exit-Mapping 0.
- AC-3: dauerhaft 503/429 → UNREACHABLE; 502 dann 200 → PASS.
- AC-4: 200 mit abweichendem Menü → FAIL, genau 1 Anfrage.
- AC-5: 401/404/unlesbarer Body/`ok:false` → FAIL, je 1 Anfrage.
- AC-6: `_http_get` ohne `timeout` bricht nach `PROBE_TIMEOUT` ab; ohne Token SKIPPED.
- AC-7: gemessene Gesamtdauer im Dauer-Hänger-Fall ≤ Summe aus Zeitlimits und Pausen + Toleranz.
Bestandstests: `test_issue_685_selftest_menu_gate.py`, `test_selftest_auth_redirect.py`, `test_selftest_auth_required.py`, `test_issue_671_bot_menu_autoset.py`, `test_prod_selftest_1708c_dead_trips_guard.py` bleiben grün.

## Definition of Done

- [ ] Alle AC-Tests der neuen Datei vor der Umsetzung rot, danach grün.
- [ ] Bestandstests zum Selbsttest grün.
- [ ] Adversary-Prüfung mit Mutations-Gegenprobe ohne offenes Finding.
- [ ] Nach dem nächsten Prod-Deploy zeigt der Bericht den Menü-Abschnitt mit Status und passender Fazit-Zeile.

## Known Limitations

- Ein echter Menü-Defekt bei gleichzeitigem Telegram-Ausfall bleibt im Selbsttest unbemerkt. Abdeckung: die sichtbare "nicht erreichbar"-Zeile im Bericht macht die Lücke ablesbar; `UNREACHABLE` ist nie PASS.
- Im Störfall verlängert sich der Selbsttest um bis zu 42 s.
- Die Ursache des Hängers vom 2026-11-20 liegt bei Telegram oder im Netz (Messung 2026-11-27: Verbindung zu `api.telegram.org` aktuell in unter 0,1 s); eine andere HTTP-Bibliothek würde nichts ändern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Werkzeug-Entscheidung im Rahmen der bestehenden Linie "nicht Belegbares bekommt einen eigenen Status statt eines Fehlschlags" (#1353/#1367). Keine Grundsatzentscheidung berührt.

## Changelog

- 2026-11-27: Initial spec created (Issue #3219), Variante (b) vom Tech Lead gewählt
