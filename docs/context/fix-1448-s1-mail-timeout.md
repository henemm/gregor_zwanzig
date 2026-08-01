# Kontext & Analyse: #1448 Scheibe S1 — E-Mail-Versand ohne Zeitgrenze

**Workflow:** `fix-1448-s1-mail-timeout` · **Typ:** Bug · **Issue:** #1448 (Blockierer B1)
**Erstellt:** 2026-08-01 · **Vorgeschichte:** `docs/context/fix-1447-alarm-timeout.md`

## Zuschnitt von #1448 (PO-Entscheidung 2026-08-01)

Drei Scheiben nacheinander, jede mit eigenem Nachweis und eigenem Deploy:

| Scheibe | Inhalt | Stand |
|---|---|---|
| **S1** | E-Mail-Versand: Grenze je Verbindung + Gesamtbudget über die Wiederhol-Schleife | **diese** |
| S2 | Die drei Dateisperren (`forecast_budget.py:178`, `throttle_store.py:115`, `meteoalarm_budget.py:231`) | offen |
| S3 | Telegram-Bremse `_reserve_send_slot` + fehlende Gesamt-Zeitgrenze in `openmeteo.py` | offen |

## Type

Bug — nutzersichtbares Fehlverhalten: ein hängender Verbindungsaufbau zum Postausgang
kann einen Alarm-Lauf unbegrenzt anhalten und damit eine Wetterwarnung verzögern.

## Befund (verifiziert am Code, Stand `94f4d200`)

### Der Versandweg heute

`src/output/channels/email.py`:

- `:433` — `with smtplib.SMTP(host, port) as server:` **ohne `timeout=`**. Fällt damit auf
  `socket._GLOBAL_DEFAULT_TIMEOUT` zurück; `socket.setdefaulttimeout` wird repoweit nirgends
  gesetzt ⇒ blockierender Socket ohne jede Grenze. Betrifft `connect`, `starttls()` (`:434`),
  `login()` (`:435`) und `sendmail()` (`:437`/`:441`/`:447`).
- `:624-736` — Wiederhol-Schleife: `max_attempts = 4`, `backoff_base = 5`,
  Wartemuster `[1, 3, 6] × 5 s` = **50 s reiner Schlaf** (`time.sleep` `:668` für 4xx,
  `:713` für `OSError`).
- `:673-691` / `:719-734` — Ersatz-Postausgang (Stalwart) nach dem letzten Versuch, erneut
  über `_dial_and_send` ⇒ ebenfalls ohne Grenze.

**Obergrenze: keine.**

### Verschärfung 1 — eine Grenze je Verbindung reicht nicht

Der `timeout=`-Parameter von `smtplib.SMTP` ist ein **Socket-Timeout je Einzeloperation**,
kein Sitzungsbudget. Eine Sitzung besteht aus `connect` + `ehlo` + `starttls` + `ehlo` +
`login` + je Empfänger ein `sendmail` (der Primärweg fasst jeden Empfänger einzeln ein,
`isolate_per_recipient=True`, `:437-447`). Bei drei Empfängern sind das rund zwölf
Operationen; mit 10 s je Operation ergäbe das im pathologischen Fall ~120 s für **einen**
Versuch — und das Gesamtbudget der Schleife würde erst danach wieder geprüft.

⇒ Nötig ist **beides**: ein Socket-Timeout *und* eine mitgeführte Wall-Clock-Schranke, die
auch **innerhalb** von `_dial_and_send` vor jeder Phase greift
(`server.sock.settimeout(min(basis, restzeit))`).

### Verschärfung 2 — Zielkonflikt mit einer bestehenden Zusage

`docs/specs/modules/smtp_fallback.md` sichert zu (AC-1, `:110`; Test
`tests/tdd/test_927_smtp_fallback.py`): Fällt Resend aus, geht die Mail nach den vier
Versuchen über den Ersatz-Postausgang **trotzdem** raus. Die Spec kennt die Folge und nennt
sie ausdrücklich (`:131`): „Der Python-Fallback erhöht die maximale Gesamtwartezeit […]
Bei komplettem Ausfall beider SMTP-Server verlängert sich der Timeout entsprechend."

Diese 50 s Wartepausen sind aber allein schon mehr als die Hälfte des Budgets, das der
Alarm-Lauf insgesamt hat (`ALERT_RUN_DEADLINE_SECONDS = 90.0`, `src/services/trip_alert.py:40`,
aus #1447 S1). Ein einfaches hartes Abschneiden würde die Ausfall-Absicherung aus
`smtp_fallback.md` im Alarmfall faktisch abschalten.

**PO-Entscheidung 2026-08-01:** Der Ersatzweg hat Vorrang. Wird die Zeit knapp, werden die
restlichen Primärversuche **übersprungen** und sofort der Ersatz-Postausgang genommen.
Dafür werden die Wartepausen verkürzt. Kein getrenntes Budget für Alarm vs. Briefing
(Option „zwei Budgets" verworfen — mehr bewegliche Teile ohne fachlichen Gewinn).

## Entwarnung bei zwei naheliegenden Sorgen

- **Nutzlast:** Die Mails enthalten ausschließlich `MIMEText` (plain + html), keine Bilder,
  keine Anhänge (`email.py:306-307`). Eine knappe Zeitgrenze schneidet keine große Nutzlast ab.
- **Go-Seite:** `internal/mail/sender.go:474` (`smtp.SendMail`) hat zwar ebenfalls keinen
  Verbindungs-Timeout, läuft aber nebenläufig unter einer 20-s-Schranke
  (`internal/handler/auth.go:288`, `:682`, `:848`, `auth_magic.go:114`) und antwortet dem
  Nutzer sofort. **Kein Handlungsbedarf, nicht in S1.**
- **Empfänger-Guard:** fällt einmal **vor** der Schleife (`:428`/`:476`, Schleife ab `:627`).
  Ein früherer Sprung zum Ersatzweg umgeht ihn nicht — der Ersatzweg prüft zusätzlich selbst
  (`_fallback_recipients_blocked`, `:673`/`:719`, #1412 S1).

## Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/output/channels/email.py` | MODIFY | Socket-Timeout, mitgeführte Restzeit in `_dial_and_send`, Budget + Reserve in der Wiederhol-Schleife, kürzere Wartepausen |
| `docs/specs/modules/smtp_fallback.md` | MODIFY | AC-1 präzisieren: Ersatzweg greift nach erschöpften Versuchen **oder** bei knapper Restzeit; `:131` bekommt die nun existierende Obergrenze |
| `docs/specs/modules/fix_1448_s1_mail_zeitgrenze.md` | CREATE | Spec dieser Scheibe |
| `tests/tdd/test_mail_send_deadline.py` | CREATE | Nachweis (Verhaltensname, keine Issue-Nummer) |

## Scope Assessment

- Dateien: 1 Quelldatei, 1 neue Testdatei, 2 Spec-Dateien
- Geschätzt: ~+130/-20 Zeilen Code+Test (Doku zählt beim LoC-Gate mit — Budget 250 im Blick behalten)
- Risiko: **MITTEL-HOCH** — kritischer Versandpfad aller Nutzer und aller Kanäle-über-Mail.
  `src/output/channels/email.py` löst das **Renderer-Commit-Gate #811** aus: der Commit
  blockt, bis `tests/tdd/test_issue_811_mode_matrix.py` grün ist **und** ein frischer
  `briefing_mail_validator.py`-Lauf gegen eine echt zugestellte Staging-Mail vorliegt.

## Technischer Ansatz (Empfehlung)

Vorbild ist `FETCH_DEADLINE_SECONDS` in `src/providers/dwd.py:69` / `meteofrance.py:85`
(180 s, Muster aus Adversary #1143 F004) — hier aber mit Reserve für den Ersatzweg:

1. **Modulkonstanten** in `email.py`, analog benannt und kommentiert:
   - `SMTP_OP_TIMEOUT_SECONDS` — Grenze je Socket-Operation, an `smtplib.SMTP(..., timeout=)`.
   - `SEND_DEADLINE_SECONDS` — Gesamtbudget einer `send()`-Operation, unter den 90 s des
     Alarm-Laufs.
   - `FALLBACK_RESERVE_SECONDS` — Restzeit, die dem Ersatz-Postausgang garantiert bleibt.
2. **`_dial_and_send` bekommt `deadline_at`** und setzt vor jeder Phase
   `server.sock.settimeout(min(SMTP_OP_TIMEOUT_SECONDS, restzeit))`; ist die Restzeit
   aufgebraucht, wird ein `TimeoutError` geworfen. `TimeoutError` ist Unterklasse von
   `OSError` ⇒ fügt sich ohne neuen Zweig in die bestehende Fehlerbehandlung (`:702`).
3. **Schleife:** vor jedem weiteren Primärversuch *und* vor jedem Schlaf prüfen, ob
   `restzeit > FALLBACK_RESERVE_SECONDS`. Wenn nicht → Schleife verlassen und direkt zum
   Ersatzweg. Wartepausen zusätzlich auf die verbleibende Zeit kappen.
4. **Wartepausen verkürzen**, damit die vier Versuche realistisch ins Budget passen
   (heute 5/15/30 = 50 s). Konkrete Werte in der Spec.
5. **Ersatzweg** läuft mit eigener, garantierter Restzeit — nicht mit dem Rest des
   aufgebrauchten Budgets.

## Nachweis (Muster)

`tests/tdd/test_meteofrance_direct_fallback.py:476-517` — echter langsamer lokaler Server,
Grenze per `monkeypatch` auf Millisekunden geschrumpft, Erwartung ist ein sichtbarer Fehler
statt unbegrenztem Warten. **Kein Mock.** `pytest-timeout` steht global auf 30 s
(`pyproject.toml:63`), der Test muss also deutlich darunter bleiben.

Zusätzlich muss ein Test belegen, dass die PO-Entscheidung trägt: **hängender Primärhost ⇒
der Ersatz-Postausgang wird trotzdem erreicht**, und zwar innerhalb des Budgets.

## Bestehende Tests im Wirkungsbereich

`tests/tdd/test_issue_766_smtp_retry.py` (Retry-Verhalten, 4xx/5xx-Unterscheidung),
`tests/tdd/test_927_smtp_fallback.py` (Ersatzweg, echter Stalwart + IMAP),
`tests/tdd/test_mail_transport_dial_behaviour.py` (`_dial_and_send`-Kapselung, #1412 S3a),
`tests/tdd/test_mail_fallback_guard.py`, `tests/test_outputs.py`.
Die Backoff-Werte sind in `test_issue_766_smtp_retry.py` erwartet — Änderung zieht dort nach.

## Open Questions

- [x] Zielkonflikt Ersatzweg vs. Zeitgrenze → PO 2026-08-01: Ersatzweg hat Vorrang, Wartepausen kürzen.
- [ ] Konkrete Sekundenwerte — werden in der Spec mit Rechnung vorgelegt.
