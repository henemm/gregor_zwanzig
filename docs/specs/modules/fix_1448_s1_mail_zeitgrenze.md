---
entity_id: fix_1448_s1_mail_zeitgrenze
type: bugfix
created: 2026-08-01
updated: 2026-08-01
status: draft
version: "1.0"
tags: [smtp, versand, zeitbudget, alerts]
---

# Fix #1448 Scheibe S1 — E-Mail-Versand bekommt Verbindungs-Timeout + Gesamtbudget

## Approval

- [ ] Approved

## Purpose

`EmailOutput.send()` baut die SMTP-Verbindung heute ohne `timeout=` auf
(`smtplib.SMTP(host, port)`, `email.py:433`). Ein hängender Verbindungsaufbau
zum Postausgang — egal ob bei `connect`, `starttls()`, `login()` oder
`sendmail()` — blockiert dadurch **unbegrenzt**, und die vier Wiederhol-
versuche mit fester Wartezeit (5/15/30 s = 50 s reiner Schlaf) laufen
ebenfalls ohne jede Obergrenze für die Gesamtoperation. Nutzersichtbar
bedeutet das: eine Wetterwarnung kann unbegrenzt verzögert werden, weil ein
einzelner Versandversuch nie aufgibt.

Diese Scheibe gibt dem Versand eine harte, im Test schrumpfbare Grenze —
sowohl je Socket-Operation als auch für die Gesamtoperation `send()` — nach
dem Vorbild von `FETCH_DEADLINE_SECONDS` in `src/providers/meteofrance.py`/
`dwd.py`. Anders als dort muss die Grenze zusätzlich dem bestehenden
Ersatz-Postausgang (Stalwart, `docs/specs/modules/smtp_fallback.md`) genug
garantierte Restzeit lassen, statt ihn durch ein hartes Gesamt-Cutoff
mitabzuschneiden — PO-Entscheidung 2026-08-01: der Ersatzweg hat Vorrang,
dafür werden die Wartepausen der Primär-Schleife verkürzt.

## Source

- **Datei:** `src/output/channels/email.py`, Klasse `EmailOutput`,
  Methoden `_dial_and_send()` (`:410-448`) und `send()` (`:450-736`)

> **Schicht-Hinweis:** Reine Python-Core-Änderung (`src/output/channels/`).
> Keine Go-Änderung (der Go-Versandweg `internal/mail/sender.go` läuft
> bereits unter einer 20-s-Schranke seiner Aufrufer, s. Analyse-Kontext) und
> kein Frontend-Anteil in dieser Scheibe.

## Estimated Scope

- **LoC:** ~130 hinzugefügt / ~20 gelöscht in `email.py` + neuer Testdatei
  (Kontext-Schätzung); Doku-Folgeänderung an `smtp_fallback.md` kommt in
  derselben Implementierungsphase dazu, ist aber klein (wenige Zeilen,
  s. u.). Bleibt unter dem Workflow-Limit von 250, sollte aber nicht ohne
  Not überschritten werden.
- **Files:** 1 Quelldatei modifiziert, 1 neue Testdatei, 1 bestehende
  Spec-Datei modifiziert (`smtp_fallback.md`), 4 Bestandstests mit
  Zeilenwert-Pflege (s. „Betroffene Bestandstests")
- **Effort:** medium — klar umrissener Mechanismus nach etabliertem
  Vorbild, aber mit einer echten Wechselwirkung mit einer bestehenden
  Zusage (`smtp_fallback.md` AC-1) und dem Renderer-Commit-Gate #811 auf
  der geänderten Datei.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `providers.meteofrance.FETCH_DEADLINE_SECONDS` / `dwd.py`-Muster | Referenz-Pattern (nicht importiert) | Monotone Uhr, Prüfung vor jeder Phase, sichtbarer Fehler statt stillem unbegrenztem Warten — hier auf Verbindungs- statt Provider-Ebene übertragen |
| `src/services/trip_alert.py::ALERT_RUN_DEADLINE_SECONDS` (#1447 S1) | Konstante (nicht importiert) | Äußere Job-Lauf-Grenze (90 s) des Alarm-Laufs, von der diese Scheibe bewusst **nicht** abhängt — s. „Known Limitations" |
| `docs/specs/modules/smtp_fallback.md` | Spec (bestehend) | Zusage zum Ersatz-Postausgang, deren AC-1 und Known-Limitations-Eintrag diese Scheibe präzisiert (Folgeänderung, s. u. — nicht Teil dieses Commits selbst) |
| `_fallback_recipients_blocked()` (`:673`/`:719`, #1412 S1) | Python-Methode | Bleibt unverändert genutzt, Guard-Reihenfolge unangetastet |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/channels/email.py` | MODIFY | Vier Modulkonstanten (s. Implementation Details); `_dial_and_send()` bekommt Parameter `deadline_at` und setzt `server.sock.settimeout(...)` vor jeder Phase; `send()`-Schleife prüft Restzeit vor jedem weiteren Versuch/jeder Wartepause, kürzere Backoff-Werte, Ersatzweg mit eigener Deadline |
| `tests/tdd/test_mail_send_deadline.py` | CREATE | Nachweis aller ACs, echte lokale Server, keine Mocks |
| `docs/specs/modules/smtp_fallback.md` | MODIFY | AC-1 und Known-Limitations-Eintrag präzisieren (Details s. „Folgeänderung an smtp_fallback.md") |

### Estimated Changes

- Files: 3 (1 Quelldatei, 1 neue Testdatei, 1 bestehende Spec)
- LoC: +130/-20 (Kontext-Schätzung, s. „Estimated Scope")

## Implementation Details

### Modulkonstanten (analog `FETCH_DEADLINE_SECONDS`)

| Konstante | Wert | Bedeutung |
|---|---|---|
| `SMTP_OP_TIMEOUT_SECONDS` | `10.0` | Grenze je Socket-Operation; geht als `timeout=` an `smtplib.SMTP` bzw. als `server.sock.settimeout(...)` vor jeder Phase |
| `SEND_BUDGET_SECONDS` | `50.0` | Gesamtbudget einer `send()`-Operation, gemessen mit `time.monotonic()` |
| `FALLBACK_RESERVE_SECONDS` | `12.0` | Restzeit, die dem Ersatz-Postausgang garantiert bleibt, unabhängig davon, wie viel vom Primärbudget bereits verbraucht ist |
| Backoff | `backoff_base = 2`, `wait_multiplier = [1, 2, 4]` (2 s / 4 s / 8 s statt bisher 5 s / 15 s / 30 s) | Kürzere Wartepausen, damit realistisch mehrere Versuche plus Ersatzweg ins Budget passen |
| `FALLBACK_SMTP_PORT` | `587` | Port des Ersatz-Postausgangs. **Nachtrag 2026-08-01:** steht heute als nackte Zahl zweimal im Code (`:677`, `:723`); wird durch diese Konstante ersetzt. Verhalten identisch |

**Warum `FALLBACK_SMTP_PORT` dazugehört (Fund aus der RED-Phase):** Solange die
`587` hart im Code steht, ist AC-3 auf diesem Host nicht echt nachweisbar — auf
`0.0.0.0:587` lauscht der produktive Stalwart, und ein Test-Bind als
unprivilegierter Nutzer scheitert mit `PermissionError`. Ohne die Konstante
bliebe für AC-3 nur eine Attrappe am SMTP-Objekt oder ein Live-Test gegen den
Produktiv-Mailserver — beides unerwünscht. Die Konstante beseitigt zugleich eine
doppelte Magic Number. Zwei Zeilen, kein Verhaltensunterschied.

### `_dial_and_send()` — Restzeit je Phase

Bekommt einen neuen Pflichtparameter `deadline_at: float` (`time.monotonic()`-
Zeitpunkt). Vor `starttls()`, vor `login()` und vor jedem `sendmail()`-Aufruf
wird die Restzeit berechnet (`deadline_at - time.monotonic()`) und darauf
`server.sock.settimeout(min(SMTP_OP_TIMEOUT_SECONDS, restzeit))` gesetzt.

**Wichtiger Randfall:** Ist die Restzeit bei Erreichen einer Phase bereits
`<= 0`, darf **nicht** `settimeout(0)` aufgerufen werden — das schaltet den
Socket laut `socket`-Doku in den *nicht-blockierenden* Modus, nicht in
„sofort abbrechen". Stattdessen wird in diesem Fall direkt ein
`TimeoutError` geworfen, ohne die Phase überhaupt zu versuchen.
`TimeoutError` ist Unterklasse von `OSError` und fügt sich damit ohne neuen
Fehlerzweig in die bestehende Behandlung in `send()` (`:702`) ein.

### `send()` — Schleife mit Gesamtbudget und Reserve

Vor der Schleife: `deadline_at = time.monotonic() + SEND_BUDGET_SECONDS`
(einmalig, wie bei `ALERT_RUN_DEADLINE_SECONDS` in #1447 S1).

Nach jedem gescheiterten Versuch (sowohl im `SMTPResponseException`-4xx-Zweig
`:660-668` als auch im `OSError`-Zweig `:704-713`):

1. Restzeit berechnen: `restzeit = deadline_at - time.monotonic()`.
2. **Weiterer Primärversuch nur, wenn** `restzeit > SMTP_OP_TIMEOUT_SECONDS +
   FALLBACK_RESERVE_SECONDS` — sonst wird die Schleife **sofort** verlassen
   (kein weiterer Versuch, keine weitere Wartepause) und direkt zum
   Ersatzweg gesprungen.
3. Ist ein weiterer Versuch zulässig, wird die nominale Wartepause
   zusätzlich gekappt: `wait = min(nominale_wartepause, restzeit -
   FALLBACK_RESERVE_SECONDS)`, mindestens `0`. Damit kann die Wartepause
   selbst die Reserve nicht aufzehren.

### Ersatzweg mit eigener Deadline

Beide bestehenden Ersatzweg-Aufrufe (`:673-691`, `:719-734`) rufen
`_dial_and_send(...)` fortan mit einer **eigenen**, garantierten Deadline
`time.monotonic() + FALLBACK_RESERVE_SECONDS` auf — nicht mit dem
(möglicherweise bereits aufgebrauchten) Rest des Primärbudgets. Die
Guard-Aufrufe `_fallback_recipients_blocked(recipients)` davor bleiben
unverändert an derselben Stelle.

### Belegrechnung (aus der Analyse übernommen, Grundlage der Konstantenwahl)

- **Hängender Primärhost:** Versuch 1 hängt 10 s (Timeout) → Wartepause 2 s
  → Versuch 2 hängt 10 s → Wartepause 4 s → Versuch 3 hängt 10 s = **36 s
  verbraucht**, Restzeit `50 - 36 = 14 s`. Prüfung vor Versuch 4:
  `14 > 10 + 12 = 22`? Nein → Versuch 4 und Wartepause 8 s entfallen, sofort
  Ersatzweg mit eigener Reserve 12 s → **Gesamtlaufzeit 48 s ≤
  SEND_BUDGET_SECONDS (50 s)**.
- **Schnell scheiternder Primärhost** (z. B. Verbindung sofort abgelehnt,
  keine Hänger): alle vier Versuche laufen wie bisher durch, nur die
  Wartepausen sind kürzer (2 + 4 + 8 = 14 s statt 50 s) — die bestehende
  Ausfall-Absicherung aus `smtp_fallback.md` (Ersatzweg erst nach
  erschöpften Versuchen) bleibt für diesen, den ursprünglich vorgesehenen
  Fall, unverändert erhalten.

## Expected Behavior

- **Input:** unverändert — `EmailOutput.send(subject, body, ...)`.
- **Output (Erfolg, Primärweg):** unverändert, keine Verhaltensänderung
  gegenüber heute.
- **Output (Primärweg hängt, Ersatzweg funktioniert):** Mail wird trotzdem
  zugestellt, über den Ersatz-Postausgang, innerhalb von
  `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` statt unbegrenzt zu
  warten.
- **Output (beide Wege hängen/scheitern):** `OutputError` wird spätestens
  nach `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` geworfen, statt
  nie zurückzukehren.
- **Side effects:** keine neuen Log-Formate; bestehende Log-Zeilen
  (`[SMTP-FALLBACK] sent via fallback SMTP`, Warnungen bei 4xx/OSError)
  bleiben inhaltlich unverändert.

## Was sich zusätzlich ändert (Nachträge aus der Implementierung, 2026-08-01)

Zwei Punkte, die die Spec vorher nicht kannte und die beim Grünmachen
zwingend wurden. Beide sind bewusst freigegeben, nicht stillschweigend
mitgenommen:

**1. Verbindungsabbruch wird jetzt wiederholt (`SMTPServerDisconnected`).**
`smtplib.getreply()` fängt jedes `OSError` beim Lesen ab und wirft
stattdessen `smtplib.SMTPServerDisconnected` — eine `SMTPException`-, aber
**keine** `OSError`-Unterklasse. Ohne eigene Behandlung landet der neu
eingeführte Verbindungs-Timeout also im generischen „kein Retry"-Zweig, und
AC-3/AC-4 wären strukturell unerfüllbar (der Ersatzweg würde nie erreicht).
Lösung: ein schmaler `except smtplib.SMTPServerDisconnected`-Zweig **vor**
dem generischen `smtplib.SMTPException`-Zweig; der bestehende
`OSError`-Zweig bleibt an seiner Position dahinter; beide rufen denselben
Helper `_handle_transient_dial_failure()`.

*Das ist eine Verhaltensänderung für einen vorher schon erreichbaren Fall:*
Ein Postausgang, der die Verbindung abbricht, führte bisher sofort zum
Aufgeben — ohne Wiederholung, ohne Ersatzweg. Jetzt wird wiederholt. Fachlich
richtig (ein Verbindungsabbruch ist eine vorübergehende Störung wie jede
andere) und durch `SEND_BUDGET_SECONDS` gedeckelt.

**Falle, die dabei auffiel:** `smtplib.SMTPException` erbt in CPython von
`OSError`. Ein naives `except (SMTPServerDisconnected, OSError)` vor dem
generischen Zweig hätte deshalb auch `SMTPRecipientsRefused` zu einem
Wiederholfall gemacht — gefangen von
`test_issue_766_smtp_retry.py::test_recipients_refused_is_not_retried`.

**2. Der Schutz der Reserve ist strukturell, nicht geschätzt.**
Die ursprünglich spezifizierte Gate-Bedingung
`restzeit > SMTP_OP_TIMEOUT_SECONDS + FALLBACK_RESERVE_SECONDS` ist bei
geschrumpften Testkonstanten nie erfüllbar (AC-5 patcht
`SEND_BUDGET_SECONDS` auf 0.3 s, lässt `SMTP_OP_TIMEOUT_SECONDS` bei 10 s —
die Restzeit kann das Budget nie überschreiten). Eine Schätzung aus der
gemessenen Dauer des letzten Versuchs wäre die naheliegende Korrektur, hat
aber ein Loch: mehrere schnell scheiternde Versuche lassen die Schätzung
klein werden, ein danach begonnener hängender Versuch frisst die Reserve
doch auf.

Stattdessen bekommen die **Primärversuche eine eigene, härtere Frist**:

```
primaer_deadline = deadline_at - FALLBACK_RESERVE_SECONDS
if primaer_deadline <= time.monotonic():          # nur wenn RESERVE >= BUDGET
    primaer_deadline = time.monotonic() + SMTP_OP_TIMEOUT_SECONDS
```

Der Primärweg kann die Reserve damit gar nicht mehr erreichen, unabhängig
von jeder Schätzung. Das Gate ist dadurch nur noch Optimierung („keinen
aussichtslosen Versuch mehr starten") und darf die gemessene Versuchsdauer
verwenden. Der Ersatzweg bekommt unverändert `time.monotonic() +
FALLBACK_RESERVE_SECONDS`.

*Der Randfall-Guard muss gegen `jetzt` prüfen, nicht gegen
`jetzt + SMTP_OP_TIMEOUT_SECONDS`* — sonst greift er in geschrumpften
Testkonfigurationen immer und bläht die Frist auf die ungepatchte Konstante
auf (in der Implementierung einmal passiert, AC-5 wurde davon rot).

## Was sich NICHT ändert

- **Empfänger-Guards** (`:509-607`, Resend-Allowlist und Lokal-Guard) —
  laufen unverändert **vor** der Schleife, werden von dieser Scheibe nicht
  berührt.
- **Reihenfolge der Fehlerzweige** — `SMTPAuthenticationError` wird
  weiterhin **vor** `SMTPResponseException` gefangen (`:645` vor `:651`),
  bleibt permanent und löst nie einen Ersatzweg-Versuch aus.
- **Kein Ersatzweg bei Auth-535 oder 5xx** — unverändert (`:649`, `:654-658`).
- **`isolate_per_recipient`-Asymmetrie** — Primärweg fasst weiterhin jeden
  Empfänger einzeln ein, beide Ersatzwege brechen weiterhin beim ersten
  abgelehnten Empfänger ab (#1412 S3a, Entscheidung E2). Der zusammengesetzte
  Defekt dahinter bleibt als **#1426 offen**, nicht Teil dieser Scheibe.
- **Der Go-Versandweg** (`internal/mail/sender.go`) — unangetastet, läuft
  bereits unter der 20-s-Schranke seiner Aufrufer (`internal/handler/
  auth.go`/`auth_magic.go`).

## Folgeänderung an `docs/specs/modules/smtp_fallback.md`

Wird im selben Implementierungsschritt an der bestehenden Spec-Datei
vorgenommen (hier nur beschrieben, nicht durch diese Datei selbst
geändert):

- **AC-1 (`:110`)** — Wortlaut „nach erschöpften Versuchen" ist nach dieser
  Scheibe nicht mehr vollständig: der Ersatzweg kann jetzt auch **vor** dem
  vierten Versuch greifen, wenn die Restzeit knapp wird. Neuer Wortlaut
  sinngemäß: „…und alle Resend-Versuche entweder erschöpft sind **oder**
  wegen knapper Restzeit vorzeitig übersprungen wurden…".
- **Known Limitations (`:131`)** — Der Satz „Bei komplettem Ausfall beider
  SMTP-Server verlängert sich der Timeout entsprechend." beschreibt einen
  bislang unbegrenzten Fall. Nach dieser Scheibe gibt es eine feste
  Obergrenze; der Satz wird ersetzt durch einen Verweis auf
  `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` als neue, garantierte
  Obergrenze, mit Verweis auf diese Spec (`fix_1448_s1_mail_zeitgrenze.md`).

## Betroffene Bestandstests

Die folgenden Tests erwarten aktuelles Verhalten (v. a. die alten
Backoff-Werte 5/15/30 s) und müssen im selben Schritt nachziehen:

- `tests/tdd/test_issue_766_smtp_retry.py` — erwartet die bisherigen
  Wartepausen; muss auf 2/4/8 s umgestellt werden.
- `tests/tdd/test_927_smtp_fallback.py` — Ersatzweg-Timing, geprüft gegen
  echten Stalwart-Fallback; muss mit den neuen, kürzeren Budgets weiterhin
  bestehen.
- `tests/tdd/test_mail_transport_dial_behaviour.py` — kapselt
  `_dial_and_send()` (#1412 S3a); muss den neuen `deadline_at`-Parameter
  mitführen.
- `tests/test_outputs.py` — allgemeine Output-Tests, Zeilenwert-Pflege bei
  Bedarf.
- `tests/tdd/test_mail_fallback_guard.py` — **Nachtrag 2026-08-01, in der
  Spec zunächst übersehen.** Die Attrappe `_FakeSMTPConnection` kennt kein
  `.sock`; ohne Ergänzung bricht sie an der neuen Socket-Zeitgrenze.

**Art der Anpassung (alle drei Attrappen-Dateien):** ausschliesslich
Signatur-Kompatibilität — ein entgegengenommenes, ignoriertes
`timeout=`-Argument und ein `.sock` mit wirkungsloser `settimeout()`. Keine
geprüfte Zusicherung wird inhaltlich verändert. Das ist Pflege an
Test-Attrappen, die der Wirklichkeit nachziehen: der echte Transport hat ab
dieser Scheibe beides.

**Nicht nötig war:** `tests/tdd/test_issue_766_smtp_retry.py` prüft
`call_count`, keine Zeitwerte — die Datei ist ohne jede Änderung grün
geblieben. Die oben zunächst angenommene Umstellung auf 2/4/8 s entfiel.

## Gate-Hinweis

`src/output/channels/email.py` löst das **Renderer-Commit-Gate #811** aus:
der Commit blockt, bis `tests/tdd/test_issue_811_mode_matrix.py` grün ist
**und** ein frischer `briefing_mail_validator.py`-Lauf gegen eine echt
zugestellte Staging-Mail vorliegt (Marker-Header `X-GZ-Mail-Type:
trip-briefing`).

## Test-Plan / Test-Politik

Kein Mock-Theater. Vorbild `tests/tdd/test_meteofrance_direct_fallback.py:476-517`:
ein echter, absichtlich langsamer/hängender lokaler Socket-Server, die
Konstanten per `monkeypatch` auf Millisekunden geschrumpft, Erwartung ist
ein sichtbarer Fehler bzw. eine gemessene Obergrenze statt unbegrenztem
Warten. `pytest-timeout` steht global auf 30 s (`pyproject.toml:63`) — alle
Tests bleiben mit geschrumpften Konstanten deutlich darunter.

Alle Tests in `tests/tdd/test_mail_send_deadline.py`, Namensregel nach
Verhalten (keine Issue-Nummer im Dateinamen). Pfadregel #1409: Prüfling
relativ zur eigenen Testdatei auflösen (`Path(__file__).resolve().parents[2]`).

## Acceptance Criteria

- **AC-1:** Given der Primär-Postausgang antwortet nicht (der Socket nimmt
  die Verbindung an, sendet aber nie eine Antwort) / When `_dial_and_send()`
  eine ihrer Phasen (`starttls`/`login`/`sendmail`) ausführt / Then wird der
  Aufruf spätestens nach `SMTP_OP_TIMEOUT_SECONDS` mit einem Fehler
  abgebrochen statt unbegrenzt zu blockieren.
  - Test: `test_dial_and_send_times_out_when_socket_hangs` — echter
    lokaler TCP-Server, der Verbindungen annimmt, aber nie antwortet;
    `SMTP_OP_TIMEOUT_SECONDS` per `monkeypatch` auf Millisekunden
    geschrumpft; erwartet `TimeoutError`/`OSError` statt Hängenbleiben.

- **AC-2:** Given die verbleibende Zeit bis `SEND_BUDGET_SECONDS` reicht
  nach einem gescheiterten Versuch nicht mehr für einen weiteren Versuch
  plus die garantierte `FALLBACK_RESERVE_SECONDS` / When die
  Wiederhol-Schleife nach diesem Versuch prüft, ob sich ein weiterer
  Primärversuch noch lohnt / Then wird kein weiterer Primärversuch mehr
  gestartet, die Schleife wird direkt zugunsten des Ersatz-Postausgangs
  verlassen.
  - Test: `test_retry_loop_skips_remaining_primary_attempts_when_reserve_at_risk`
    — mehrere hängende Primärversuche mit geschrumpften Konstanten; die
    gezählte Anzahl tatsächlicher Verbindungsversuche gegen den
    Primär-Host bleibt nachweislich unter `max_attempts`.

- **AC-3:** Given der Primär-Postausgang hängt bei jedem
  Verbindungsversuch UND ein erreichbarer Ersatz-Postausgang ist
  konfiguriert / When `send()` aufgerufen wird / Then wird der
  Ersatz-Postausgang innerhalb von `SEND_BUDGET_SECONDS` überhaupt noch
  angewählt — die Reserve wird also nicht vorher in Wiederholversuchen
  gegen den Primärhost verbrannt.
  - Test: `test_send_reaches_fallback_within_budget_when_primary_hangs` —
    zwei echte lokale Server (Primär hängt dauerhaft, Ersatz nimmt die
    Verbindung an), `FALLBACK_SMTP_PORT` und die Budget-Konstanten per
    `monkeypatch` umgebogen bzw. geschrumpft; der Ersatzserver verzeichnet
    nachweislich eine eingehende Verbindung, und der Zeitpunkt liegt
    innerhalb der erwarteten Obergrenze.

  **Abgrenzung (Nachtrag 2026-08-01, aus der RED-Phase):** Der Test weist
  nach, dass der Ersatzweg *rechtzeitig erreicht* wird — **nicht**, dass er
  zustellt. Ein echter Erfolgspfad wäre gegen einen selbstgebauten Server
  nicht ehrlich herstellbar: `_dial_and_send` ruft `server.starttls()` ohne
  eigenen Kontext, verlangt also ein vertrauenswürdiges Zertifikat für
  `localhost`; was man dafür bauen müsste, wäre selbst die Attrappe, die die
  Testpolitik ausschliesst. Die **Zustellung** über den Ersatzweg ist
  unverändert durch `tests/tdd/test_927_smtp_fallback.py` abgedeckt (echter
  Stalwart + IMAP-Abholung) — dieser Pfad wird von S1 nicht verändert, der
  Nachweis also nicht dupliziert.

- **AC-4:** Given weder Primär- noch Ersatz-Postausgang antworten (beide
  hängen) / When `send()` aufgerufen wird / Then wirft der Aufruf
  spätestens nach `SEND_BUDGET_SECONDS + FALLBACK_RESERVE_SECONDS` eine
  `OutputError`, statt unbegrenzt zu blockieren.
  - Test: `test_send_raises_bounded_error_when_primary_and_fallback_both_hang`
    — zwei hängende lokale Server, geschrumpfte Konstanten; gemessene
    Gesamtlaufzeit liegt innerhalb der erwarteten Obergrenze plus geringer
    Toleranz, `OutputError` wird geworfen.

- **AC-5:** Given ein Primärversuch schlägt fehl, während noch ausreichend
  Restzeit für einen weiteren Versuch vorhanden ist / When die Wartepause
  vor dem nächsten Versuch berechnet wird / Then wird sie zusätzlich auf
  die verbleibende Zeit minus `FALLBACK_RESERVE_SECONDS` gekappt, sodass
  die Wartepause allein die Reserve nicht aufzehren kann.
  - Test: `test_backoff_wait_is_capped_by_remaining_reserve` — `time.sleep`
    per `monkeypatch` als Spion belauscht, geschrumpfte Restzeit-Konstanten;
    die tatsächlich angeforderte Schlafdauer überschreitet nachweislich nie
    die verbleibende Zeit minus Reserve.

## Known Limitations

- **Mögliches Duplikat statt stillem Totalverlust bei mehreren Empfängern**
  (Nebenbeobachtung aus Adversary Runde 3, 2026-08-01, bewusst kein eigener
  Befund). Bricht der Transport mitten in der Empfänger-Schleife ab, wird der
  Fehler seit dem F001-Fix durchgereicht; der folgende Wiederholversuch sendet
  die **gesamte** Empfängerliste erneut, sodass bereits bediente Empfänger die
  Mail ein zweites Mal bekommen können. Das ist vorbestehendes, in **#1426**
  erfasstes Verhalten (`send()` kennt keinen Teil-Zustellstand) und wird durch
  diese Scheibe **nicht verändert** — es wird für diesen einen Fall nur
  erstmals sichtbar, statt hinter einem verschluckten Fehler zu verschwinden.
  Der Tausch ist gewollt: eine doppelte Warnung ist harmloser als eine
  stillschweigend verlorene.

- **Kein durchgereichtes Restbudget des Alarm-Laufs.** Das Gesamtbudget
  dieser Scheibe (`SEND_BUDGET_SECONDS = 50.0`) ist eine feste Zahl,
  unabhängig von `ALERT_RUN_DEADLINE_SECONDS = 90.0`
  (`src/services/trip_alert.py:40`, #1447 S1). Hängen zwei Mails
  innerhalb eines Alarm-Laufs nacheinander, kann der Lauf dadurch rund
  `2 × 48 s ≈ 96 s` brauchen, bevor er von der Lauf-Grenze aus #1447 S1
  abgeschnitten wird — knapp über deren 90 s. Das ist eine bewusst in Kauf
  genommene Grenze dieser Scheibe, kein übersehener Fehler: ein
  gemeinsames Budget über beide Ebenen wurde in der Analyse geprüft und
  verworfen (mehr bewegliche Teile ohne fachlichen Gewinn, PO-Entscheidung
  2026-08-01).
- **`isolate_per_recipient`-Asymmetrie (#1426) bleibt offen** — unverändert
  durch diese Scheibe, s. „Was sich NICHT ändert".
- **Kein Fallback-Retry.** Der Ersatzweg läuft weiterhin einmalig ohne
  eigene Wiederholungslogik (unverändert gegenüber `smtp_fallback.md`,
  Known Limitations) — nur seine Deadline ist jetzt explizit garantiert.
- **`SEND_BUDGET_SECONDS`/`FALLBACK_RESERVE_SECONDS` sind konservative,
  aus der Belegrechnung hergeleitete erste Werte**, keine empirisch in
  Produktion gehärteten Zahlen — analog zur Einordnung von
  `ALERT_RUN_DEADLINE_SECONDS` in #1447 S1.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer architektureller Grundsatz. Diese Scheibe
  wendet ein bereits etabliertes Muster (Socket-Timeout + monotone
  Wall-Clock-Deadline, Vorbild `FETCH_DEADLINE_SECONDS`) auf den
  E-Mail-Versandpfad an. ADR-0038 (Zeitgrenze je Job-Lauf) schließt diese
  Klasse von Änderungen — „einzelne in sich unbegrenzt blockierende
  Schritte (SMTP ohne Timeout …)" — ausdrücklich aus seinem
  Geltungsbereich aus und benennt Issue #1448 als die Stelle, an der sie
  gesondert behandelt wird (`docs/adr/0038-…md:92-94`). Diese Spec ist
  genau diese gesonderte Behandlung, kein Widerspruch zu ADR-0038 und
  keine neue Grundsatzentscheidung, die ein eigenes ADR rechtfertigen
  würde.

## Changelog

- 2026-08-01: Initial spec created
