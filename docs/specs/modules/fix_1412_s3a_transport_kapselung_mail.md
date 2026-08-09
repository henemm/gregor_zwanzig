---
entity_id: fix_1412_s3a_transport_kapselung_mail
type: module
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [mail, egress, struktur-test, 1412]
---

# Fix #1412 Scheibe S3a — Transport-Kapselung E-Mail (`_dial_and_send`)

## Approval

- [ ] Approved

## Purpose

Der E-Mail-Kanal öffnet heute an drei Stellen eine SMTP-Verbindung (Primärweg
`email.py:589`, zwei Ersatzwege `:638`/`:682`) — dieselbe Aufrufform, aber
dreifach abgeschrieben statt geteilt. Ein vierter, ungeschützter Sendeweg
existiert daneben in `src/app/core.py` und wird von keinem Produktivcode mehr
gerufen. S3a führt `EmailOutput._dial_and_send` als den **einen** Ort ein, an
dem eine SMTP-Verbindung entsteht, entfernt den toten Sendeweg ersatzlos und
sichert beides durch einen AST-Struktur-Test ab, der jede weitere
`smtplib`-Verbindung in `src/`+`api/` verbietet. Diese Scheibe ändert **kein**
Nutzerverhalten — sie ist reine Kapselung des bestehenden Transports.

## Source

- **File:** `src/output/channels/email.py` — Klasse `EmailOutput`, Methode
  `send()`, drei Dial-Blöcke (`:589-606` Primär, `:638-652` Ersatz 4xx,
  `:682-693` Ersatz OSError)
- **Datei (Löschung):** `src/app/core.py` — Funktion `send_mail()`

> **Schicht-Hinweis:** Python-Core (`src/output/channels/`, `src/app/`) —
> kein Go-, kein Frontend-Anteil in dieser Scheibe.

## Estimated Scope

- **LoC:** ~221 (added+deleted), Workflow-Limit 250 — **kein Override
  nötig**. Dokumentation zählt nicht mit.
- **Files:** 4 Code-/Testdateien (`email.py` modifiziert, `core.py` +
  `test_core.py` gelöscht, ein neuer Struktur-Test) + 3 Doku-Dateien
  (`smtp_mailer.md` archiviert, `cli.md`, `tests/INDEX.md` bereinigt, zählen
  nicht auf das Budget)
- **Effort:** medium (kleine Umformung, aber produktiver Sicherheitspfad,
  Gate #811 greift)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `smtplib.SMTP` | stdlib | Transport, den `_dial_and_send` kapselt — Aufrufform bleibt exakt `SMTP(host, port)`, zwei positionelle Angaben |
| `EmailOutput.send` — Guard-Region (`:456-567`) | Methode | bleibt **unverändert und außerhalb** von `_dial_and_send` (E1) |
| `self._fallback_recipients_blocked` (`:389-408`) | Methode | unverändert, läuft weiterhin vor beiden Ersatzwegen |
| `tests/test_mail_recipient_parity.py::_finde_guard_if` (`:562-576`) | Test-Werkzeug | sucht die Guard-`If`-Anweisung in der **obersten Ebene** von `EmailOutput.send()` — bricht, falls die Prüfung dort verschwindet |
| `tests/fixtures/mail_recipient_parity/faelle.json::verzweigungen_python` (`:131`, Wert 15) | Fixture | gilt für dieselbe Guard-Region, darf sich durch S3a nicht ändern |
| `tests/test_outputs.py::test_email_send` (`:106-120`) | Test | bindet `smtplib.SMTP(self._host, self._port)` auf genau zwei positionelle Argumente |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | Vorbild | Bauform für AST-Scan, Repo-Wurzel-Auflösung, Prüfdatum-Konstante |
| `tests/test_mail_recipient_parity.py` (`:69-145`) | Vorbild | Bauform für Ausnahmen-Deckel + Frist + Begründungspflicht |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | Gate | blockiert den Commit, sobald `email.py` gestaged wird |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/channels/email.py` | MODIFY | `_dial_and_send(host, port, user, password, recipients, msg, from_addr, isolate_per_recipient)` einführen; Primärweg und beide Ersatzwege rufen sie auf, Guard-Region bleibt unverändert in `send()` |
| `src/app/core.py` | DELETE | toter Sendeweg, nachweislich ohne Aufrufer außerhalb von `tests/test_core.py` |
| `tests/test_core.py` | DELETE | einziger Aufrufer von `core.send_mail` |
| `tests/tdd/test_egress_single_dial_point.py` | CREATE | AST-Struktur-Test, `smtplib`-Teil (S3b ergänzt später den `httpx`-Teil additiv) |
| `docs/specs/modules/smtp_mailer.md` | MOVE → `docs/specs/_archive/modules/smtp_mailer.md` | Spec der gelöschten `core.py` |
| `docs/specs/modules/cli.md` | MODIFY | Abhängigkeitszeile `:31` (`send_mail` — E-Mail-Versand) entfernen, `cli.py` nutzt diesen Weg nicht |
| `tests/INDEX.md` | MODIFY | Zeilen `:11` (Verweis auf `test_core.py`), `:28` (Beispielaufruf `pytest tests/test_core.py`) entfernen |

**Nicht in dieser Scheibe** (S3b, eigener Workflow): `src/output/channels/telegram.py`, `src/output/channels/sms.py`, der `httpx.post`-Teil von `test_egress_single_dial_point.py`.

### Estimated Changes
- Files: 4 Code-/Testdateien + 3 Doku-Dateien (zählen nicht)
- LoC: ~221 (added+deleted)

## Implementation Details

### `_dial_and_send` — reiner Transport (Entscheidung E1)

```
def _dial_and_send(self, host, port, user, password, recipients, msg,
                    from_addr, isolate_per_recipient):
    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        if len(recipients) == 1:
            server.sendmail(from_addr, recipients, msg.as_string())
        else:
            for recipient in recipients:
                if isolate_per_recipient:
                    try:
                        server.sendmail(from_addr, [recipient], msg.as_string())
                    except smtplib.SMTPException as exc:
                        logger.error("SMTP-Fehler für Empfänger %s: %s", recipient, exc)
                else:
                    server.sendmail(from_addr, [recipient], msg.as_string())
```

Drei Aufrufstellen in `send()`:

- **Primärweg** (ersetzt `:589-601`): `self._dial_and_send(self._host, self._port, self._user, self._password, recipients, msg, from_addr, isolate_per_recipient=True)`. Der Erfolgs-Log (`if attempt > 0: ...`, `:604`) bleibt **im Aufrufer**, direkt nach dem Aufruf — das entspricht exakt „außerhalb des `with`-Blocks", weil `_dial_and_send` den Kontextmanager beim normalen Rückkehren bereits geschlossen hat.
- **Ersatzweg 1 / 4xx** (ersetzt `:638-645`): `self._dial_and_send(self._fallback_host, 587, self._fallback_user, self._fallback_pass, recipients, msg, from_addr, isolate_per_recipient=False)`. Erfolgs-Log `[SMTP-FALLBACK] sent via fallback SMTP` bleibt im Aufrufer, unbedingt.
- **Ersatzweg 2 / OSError** (ersetzt `:682-689`): identischer Aufruf wie Ersatzweg 1.

**Was ausdrücklich NICHT in `_dial_and_send` wandert:**

- Die Empfänger-Guard-Verzweigung (`:456-567`, Resend-Allowlist / Lokal-Regel) bleibt in `send()`, vor der Retry-Schleife. Begründung (Entscheidung E1, muss beim Review sichtbar bleiben): `_dial_and_send` hat genau einen Aufrufer-Kontext (`send()`), der bereits einmal vor der gesamten Schleife prüft — eine Prüfung gehört nur dann in den geteilten Weg, wenn mehrere unabhängige Aufrufer sie vergessen könnten. Das ist bei Telegram (`_post`, sieben Aufrufer, S3b) der Fall, bei E-Mail nicht. S1 hat empirisch belegt, dass die Prüfung vor der Schleife ausreicht (der als ROT geplante AC-1-Test war grün, über alle Host×Bestätigungs-Kombinationen). Eine Verlagerung hätte zwei Kosten ohne belegten Nutzen: das S2a/S2b-Prüfwerkzeug (`tests/test_mail_recipient_parity.py:562-576`, `_finde_guard_if`) sucht die Guard-`If`-Anweisung ausschließlich in der **obersten Ebene** von `EmailOutput.send()` (`for anweisung in methode.body`, kein `ast.walk`) — wanderte die Prüfung nach `_dial_and_send`, meldete der Läufer „Region verloren, die Ratsche prüft nichts mehr"; und die Allowlist würde bis zu 4× pro Versand von der Platte gelesen (S1-Spec, Known Limitations).
- „Prüfung im gemeinsamen Weg" und „genau ein Ort, an dem Netzverkehr entsteht" sind **zwei** getrennte Ziele. S3a liefert ausschließlich das zweite. Das erste liefert S3b für Telegram (dort rechtfertigt die Aufruferzahl die Verlagerung) und S4 in voller Schärfe für alle Kanäle.
- Die Retry-/Backoff-Logik (vier Versuche, `SMTPAuthenticationError`/5xx brechen sofort ab, Backoff 5s/15s/30s) bleibt vollständig in `send()` — `_dial_and_send` wird von dort aus je Versuch aufgerufen, genau wie der Inline-Code es heute tut.

### Verhaltensneutralität — die Asymmetrie bleibt erhalten (Entscheidung E2)

Heute fasst nur der Primärweg jeden Empfänger bei mehr als einem einzeln in
ein eigenes `try/except smtplib.SMTPException` (`:596-601`) — ein abgelehnter
Empfänger blockiert die übrigen nicht. Beide Ersatzwege haben keine
Einfassung — eine Ablehnung reißt den gesamten Ersatzversand ab. Der
Parameter `isolate_per_recipient` konserviert genau diese Asymmetrie
(`True` am Primärweg, `False` an beiden Ersatzwegen).

**PO-Entscheidung 2026-07-30: S3a ändert kein Nutzerverhalten.** Die
naheliegende Vereinheitlichung („Einfassung überall übernehmen") wäre
**keine** Verbesserung: der Primärweg hat einen blinden Fleck — werden
**alle** Empfänger abgelehnt, protokolliert die Schleife jede Ablehnung
einzeln und die Funktion kehrt danach **normal zurück** (`:606`), meldet
also Erfolg für einen Versand, der niemanden erreicht hat. Die
Vereinheitlichung würde diesen blinden Fleck auf die Ersatzwege
ausbreiten. Der zusammengesetzte Defekt (Ersatzweg alles-oder-nichts
**plus** stiller Erfolg bei Totalablehnung) ist als **#1426** angelegt und
wird **nach** S3a behoben, sobald `_dial_and_send` als gemeinsamer Ort
existiert.

### Was byteweise gleich bleiben muss (Entscheidung E3)

- **Aufrufform:** `smtplib.SMTP(host, port)` — genau zwei positionelle
  Angaben, keine Schlüsselwörter, kein Timeout (`tests/test_outputs.py:117`
  bindet das hart).
- **Reihenfolge im Block:** `starttls()` → `login(user, password)` →
  `sendmail(...)`.
- **Port-Belegung:** Primärweg `self._port`, beide Ersatzwege hart `587`
  (Bestandsverhalten, nicht Teil dieser Scheibe).
- **Zugangsdaten:** Primär `self._user`/`self._password`, Ersatz
  `self._fallback_user`/`self._fallback_pass`.
- **Alle Fehlertexte wortgleich**, insbesondere die Marker `#1147/#1219` und
  `#1235` in den `OutputConfigError`-Texten (`tests/test_mail_recipient_parity.py:61`
  prüft sie als Teilzeichenkette) sowie die sechs `OutputError`-Texte
  (Auth-Fehler `:612`, 4xx-Fehlertexte `:618-621`/`:649-652`/`:653-657`,
  SMTPException `:661`, OSError-Fehlertexte `:693`/`:694`).
- **Erfolgs-Protokoll:** Primärweg nur wenn `attempt > 0`, außerhalb des
  Verbindungsaufbaus; Ersatzwege unbedingt mit dem Text
  `[SMTP-FALLBACK] sent via fallback SMTP`.
- **Retry- und Ausweich-Logik unberührt:** vier Versuche, Rückfall nur beim
  letzten Versuch, `SMTPAuthenticationError`/5xx brechen sofort ab (kein
  Ersatzweg), `_fallback_recipients_blocked` bleibt an seiner heutigen
  Stelle (`:636`, `:680`).
- **Die S2a/S2b-Ratsche bleibt grün:** `verzweigungen_python` bleibt **15**
  (`tests/fixtures/mail_recipient_parity/faelle.json:131`). Verändert der
  Umbau diese Zahl doch, ist das ein **Befund**, der in dieser Spec als
  Risiko benannt bleibt — die Fixture-Zahl darf nicht stillschweigend
  nachgezogen werden.

### Löschung `src/app/core.py` + `tests/test_core.py`

Nachweislich tot (Kontext-Recherche, nicht angenommen): `send_mail` ist der
einzige definierte Name in `core.py`, repo-weite Suche über alle
Dateiformate findet als Aufrufer ausschließlich `tests/test_core.py:7`, kein
dynamischer Import, kein Gate/Hook hängt an der Existenz. Beide Dateien
werden ersatzlos gelöscht.

**Doku-Nachzug (zählt nicht auf das LoC-Budget):**

- `docs/specs/modules/smtp_mailer.md` → `docs/specs/_archive/modules/smtp_mailer.md` (Spec der gelöschten `core.py`, Status bleibt „implemented" als historischer Stand, kein inhaltliches Update nötig).
- `docs/specs/modules/cli.md:31` — Abhängigkeitszeile `send_mail | function | E-Mail-Versand` entfernen (`cli.py` ruft diesen Weg tatsächlich nie).
- `tests/INDEX.md:11,28` — Verweis auf `test_core.py` und den Beispielaufruf `pytest tests/test_core.py` entfernen.

### Struktur-Test `tests/tdd/test_egress_single_dial_point.py`

**Zusicherung:** In `src/` und `api/` entsteht eine SMTP-Verbindung
ausschließlich innerhalb von `EmailOutput._dial_and_send`.

- **Erkennung per AST**, nicht per Textsuche. Erfasst jede Form:
  `smtplib.SMTP(`, `smtplib.SMTP_SSL(`, `smtplib.LMTP(` — auch über
  Modul-Alias (`import smtplib as s`) oder direkten Import
  (`from smtplib import SMTP`). Begründung: eine reine Textsuche nach
  `smtplib.SMTP(` ist in einer Zeile umgangen; heute gibt es null
  Vorkommen der anderen Formen (nachgeprüft), deshalb kostet die
  Vollständigkeit nichts.
- **Erkannt wird ausschließlich der Verbindungsaufbau, nicht jede Erwähnung
  von `smtplib`.** `send()` behält seine Ausnahme-Zweige
  (`except smtplib.SMTPAuthenticationError`, `smtplib.SMTPResponseException`,
  `smtplib.SMTPException`) und `_dial_and_send` fängt beim Einfassen je
  Empfänger ebenfalls `smtplib.SMTPException` — diese Verweise sind **keine**
  Fundstellen. Ein Test, der sie mitzählt, wäre am ersten Tag rot und würde
  prompt entschärft; das ist der bekannte Erosionsweg (S2a, Baustein 3).
- **Repo-Wurzel zwingend** `Path(__file__).resolve().parents[N]` relativ zur
  Testdatei — **nie** ein fest kodierter Hauptrepo-Pfad (Pfadregel #1409,
  durchgesetzt von `tests/tdd/test_repo_path_hardcoding_ratchet.py`). Sonst
  prüft der Test aus einem Worktree die unveränderte Hauptrepo-Kopie und
  meldet falsches Grün.
- **Prüfdatum `2026-10-28`** (+90 Tage, Regel-Budget), als Modul-Konstante
  (`EXPIRY = date(2026, 10, 28)`) **und** als Text maschinell auffindbar —
  Vorbild `tests/tdd/test_repo_path_hardcoding_ratchet.py:339` +
  Selbstnachweis-Test `:209-218`.
- **Ausnahmen-Mechanik** nach Vorbild `tests/test_mail_recipient_parity.py:69-145`:
  Liste mit je Eintrag Fundstelle, Begründung (≥15 sinnvolle Zeichen, gleiche
  Zählregel wie `_MIN_BEGRUENDUNG`) und Frist, plus Höchstzahl
  (`AUSNAHMEN_HOECHSTZAHL`). **S3a braucht null Ausnahmen** — nach dem
  Löschen von `core.py` ist `email.py` die einzige Stelle mit `smtplib` in
  `src/`+`api/`. Die Höchstzahl steht auf **0**, die Liste ist leer. Die
  Mechanik wird trotzdem vollständig gebaut und über einen Selbstnachweis
  geprüft, damit S3b den `httpx`-Teil rein additiv ergänzen kann (dort
  werden zwei Ausnahmen gebraucht: `src/lib/mq_notify.py:45` und
  `src/services/inbound_telegram_reader.py:397`, beide localhost ohne
  Endnutzer-Empfänger — **nicht** Teil dieser Scheibe, nur als Begründung
  für die Mechanik erwähnt).
- **Selbstnachweis-Tests** (das Werkzeug muss beweisen, dass es etwas
  fängt):
  1. eine künstlich in eine Test-Attrappe eingefügte Verbindungsstelle
     außerhalb von `_dial_and_send` wird gefunden und namentlich gemeldet;
  2. eine Ausnahme über der Höchstzahl (bei künstlich erhöhter Zahl von
     Fundstellen in der Attrappe) schlägt fehl;
  3. eine abgelaufene Frist in einem Ausnahme-Eintrag schlägt fehl;
  4. das Prüfdatum `2026-10-28` ist als Text in der Testdatei auffindbar;
  5. der Test misst nachweislich den eigenen Worktree (Repo-Wurzel über
     `Path(__file__).resolve().parents[N]`), nicht das Hauptrepo — analog
     dem Selbstnachweis in `test_repo_path_hardcoding_ratchet.py`.
- **Bewusst NICHT im Zuschnitt** (Abgrenzung, gilt für S3b): `httpx.get`
  bleibt außen vor — Daten werden per GET geholt (20+ Provider-Dateien),
  gesendet wird per POST. Ein weiter gefasster Test bräuchte eine
  Ausnahmeliste in Dutzendgröße und würde sich selbst erodieren.

## Expected Behavior

- **Input:** ein Sendeversuch über `EmailOutput.send()` — normaler
  Primärversand, Ausweichen auf einen Ersatz-Postausgang nach 4xx-Fehler,
  Ausweichen nach Netzwerkfehler (OSError).
- **Output:** identisch zum heutigen Stand in jedem der drei Fälle —
  gleicher Verbindungsaufbau, gleiche Fehlertexte, gleiches
  Einfassungsverhalten je Weg, gleiche Guard-Entscheidung. Zusätzlich:
  `src/app/core.py` existiert nicht mehr, kein Restaufrufer.
- **Side effects:** keine — diese Scheibe ändert kein beobachtbares
  Verhalten am Mail-Versand, nur seine interne Struktur. Der Struktur-Test
  ist neu und schlägt künftig an, sobald eine vierte SMTP-Verbindungsstelle
  außerhalb von `_dial_and_send` entsteht.

## Acceptance Criteria

- **AC-1:** Given ein regulärer Versand an einen Empfänger über den
  Primär-Postausgang / When der Versand erfolgreich läuft / Then entsteht
  die Verbindung zum konfigurierten Postausgang mit unverändertem Host,
  unverändertem Port und unveränderter Reihenfolge (STARTTLS, Anmeldung,
  Versand) — wie vor dieser Scheibe.
  - Test: bestehender Bestandstest (`tests/test_outputs.py::test_email_send`)
    bleibt unverändert grün — er bindet die Aufrufform hart.

- **AC-2:** Given ein Versand über den Primärweg an mehrere Empfänger, bei
  dem genau einer abgelehnt wird / When der Versand läuft / Then bekommen
  die übrigen Empfänger die Mail trotzdem — die heutige Duldsamkeit des
  Primärwegs bleibt erhalten.
  - Test: Sink am Transportrand (`smtplib.SMTP`) zeichnet Zustellversuche
    für die nicht abgelehnten Empfänger auf, während der abgelehnte
    Empfänger nur protokolliert, aber nicht gesendet wird.

- **AC-3:** Given ein Versand über einen der beiden Ersatzwege an mehrere
  Empfänger, bei dem genau einer scheitert / When der Ersatzversand läuft /
  Then bricht der **gesamte** Ersatzversand ab, kein weiterer Empfänger auf
  diesem Weg bekommt die Mail — die heutige Strenge der Ersatzwege bleibt
  erhalten, wird nicht auf den Primärweg-Stil aufgeweicht.
  - Test: Sink am Transportrand zeigt für den Ersatzweg keinen
    Zustellversuch nach dem scheiternden Empfänger.

- **AC-4:** Given `src/app/core.py` ist gelöscht / When das Projekt gebaut
  oder getestet wird / Then existiert kein Aufrufer mehr, der diesen Weg
  braucht, und kein anderer Programmteil bricht dadurch.
  - Test: gezielter Lauf der mail-nahen Suiten (`tests/test_outputs.py`,
    `tests/test_mail_recipient_parity.py`, `tests/tdd/test_*recipient*`,
    `tests/tdd/test_stalwart_recipient_guard.py`) bleibt grün, **plus**
    ein Import-Nachweis: das Einlesen aller Module unter `src/` und `api/`
    wirft keinen `ModuleNotFoundError` für `app.core`. **Keine Vollsuite** —
    Projektregel „Regression gezielt, nicht Vollsuite"; ein Sammelfehler
    beim Einlesen einer fremden Datei würde das Ergebnis sonst verfälschen.

- **AC-5:** Given der Struktur-Test läuft gegen den ausgelieferten Stand /
  When er `src/` und `api/` nach SMTP-Verbindungsstellen durchsucht / Then
  findet er genau eine erlaubte Stelle (`_dial_and_send`) und keine
  unerlaubte — ohne dass eine Ausnahme dafür nötig ist.
  - Test: `tests/tdd/test_egress_single_dial_point.py` (`smtplib`-Teil),
    Ausnahmenliste bleibt leer, Höchstzahl 0.

- **AC-6:** Given eine künstlich in eine Test-Attrappe eingefügte
  SMTP-Verbindungsstelle außerhalb der erlaubten Methode / When der
  Struktur-Test gegen diese Attrappe läuft / Then meldet er den Fund
  namentlich — das Werkzeug beweist, dass es tatsächlich etwas fängt, statt
  nur nie rot zu werden.
  - Test: Selbstnachweis-Fall (a) im Struktur-Test.

- **AC-7:** Given das Empfänger-Regelwerk aus S2a/S2b (Python-Seite) läuft
  unverändert gegen den Stand nach dieser Scheibe / When sein Läufer
  ausgeführt wird / Then bleibt die Guard-Region in `EmailOutput.send()`
  auffindbar und ihre Verzweigungszahl unverändert bei 15 — die Verlagerung
  des Transports hat die Empfänger-Prüfung nicht berührt.
  - Test: `tests/test_mail_recipient_parity.py::test_verzweigungsratsche_python_region_gefunden_und_zahl_stimmt`
    bleibt unverändert grün, ohne Fixture-Anpassung.

- **AC-8:** Given ein Nutzer sendet über den Ersatzweg an einen Empfänger,
  der auf dem Ersatzweg gesperrt ist / When der Versand versucht wird /
  Then bleibt er blockiert, exakt wie vor dieser Scheibe — der Umbau des
  Transports ändert nichts an der Empfänger-Zulässigkeit.
  - Test: bestehende Guard-Bestandstests (s. „Betroffene Bestandstests")
    bleiben unverändert grün, ohne Anpassung an einen neuen Aufrufpunkt.

- **AC-9:** Given ein Sendeversuch scheitert — durch Anmeldefehler, durch
  dauerhafte Ablehnung (5xx), durch vorübergehende Ablehnung (4xx) nach
  allen Versuchen, oder durch Netzwerkfehler, jeweils mit und ohne
  zusätzlich gescheiterten Ersatzweg / When der Fehler nach oben gereicht
  wird / Then lautet die Meldung **wortgleich** wie vor dieser Scheibe.
  - Test: je Fehlerart ein Fall, der den erzeugten Meldungstext gegen den
    festgehaltenen Wortlaut prüft. **Begründung, warum das eine eigene AC
    braucht:** eine repo-weite Suche (S1) hat gezeigt, dass **kein**
    bestehender Test diese sechs Meldungstexte prüft — eine versehentliche
    Umformulierung beim Umbau bliebe sonst unbemerkt, obwohl die Meldung
    das ist, was im Betrieb gelesen wird.

## Known Limitations

- Die naheliegende Vereinheitlichung der Fehlerbehandlung zwischen
  Primär- und Ersatzweg wird **bewusst nicht** vorgenommen (Entscheidung
  E2) — der zusammengesetzte Defekt (Ersatzweg alles-oder-nichts plus
  stiller Erfolg bei Totalablehnung am Primärweg) ist als **#1426** erfasst
  worden und wurde nach dieser Scheibe behoben (Status: `done`; siehe
  `docs/specs/bugfix/collect_send_recipient_isolation.md`).
- Die Guard-Prüfung wird durch S3a **nicht** in den Transport verlegt
  (Entscheidung, R-A/R-B in der Analyse) — die strengere Form (Prüfung
  immer im gemeinsamen Weg) ist Sache von S4, wo der Empfängervertrag über
  beide Sprachen scharf geschaltet wird.
- Der Struktur-Test deckt bewusst nicht `httpx` ab — das folgt additiv mit
  S3b. Ebenso bleiben `telegram.py`/`sms.py` unangetastet.
- Der Fallback-Port bleibt hart auf `587` (Bestandsverhalten, S1 schon so
  dokumentiert) — keine Konfigurierbarkeit, nicht Teil dieser Scheibe.

## Betroffene Bestandstests

**Bleiben unverändert grün, weil die Aufrufform/Guard-Region unangetastet
bleibt:**

- `tests/test_outputs.py::test_email_send` — bindet
  `smtplib.SMTP(self._host, self._port)` auf genau zwei positionelle
  Argumente; `_dial_and_send` ändert daran nichts.
- `tests/test_mail_recipient_parity.py` (alle Fälle inkl.
  `test_verzweigungsratsche_python_region_gefunden_und_zahl_stimmt`) — die
  Guard-Region liegt weiterhin unverändert in `send()`.
- `tests/tdd/test_stalwart_recipient_guard.py`,
  `tests/tdd/test_resend_recipient_allowlist.py`,
  `tests/tdd/test_resend_verified_allowlist.py`,
  `tests/tdd/test_issue_1147_resend_recipient_invariant.py`,
  `tests/unit/test_no_resend_for_tests.py` — rufen ausschließlich die
  öffentliche `EmailOutput.send()`-Methode auf, nicht interne
  Guard-Funktionen gegen einen fest kodierten Aufrufpunkt.
- `tests/tdd/test_telegram_test_mode_guard.py`,
  `tests/tdd/test_compare_dispatch_failed_tally.py` (`_install_smtp_sink`)
  — patchen `smtplib.SMTP` global, nicht die Kanal-Methode; bleiben blind
  gegenüber der internen Umformung, solange der Guard vor dem Netzzugriff
  feuert (unverändert der Fall).

**Müssen geändert/entfernt werden:**

- `tests/test_core.py` — gelöscht (Prüfling entfällt).
- `docs/specs/modules/smtp_mailer.md`, `docs/specs/modules/cli.md:31`,
  `tests/INDEX.md:11,28` — Doku-Nachzug, s. Implementation Details.

**Neu:**

- `tests/tdd/test_egress_single_dial_point.py` — Struktur-Test (`smtplib`-Teil) inkl. Selbstnachweisen.

## Randbedingungen

- **Renderer-Commit-Gate #811:** greift, sobald `src/output/channels/email.py`
  gestaged wird. Vor dem Commit: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py`
  grün **und** ein frischer, erfolgreicher `briefing_mail_validator.py`-Lauf
  gegen Staging. Reihenfolge: erst stagen, dann Nachweise, mit gesetzter
  Workflow-Kennung in der Umgebung.
- **LoC-Ziel:** ~221 (added+deleted), Limit 250, kein Override nötig. Doku
  zählt nicht.
- **Risiko: HOCH.** Produktiver Sicherheitspfad, alle drei bestehenden
  E-Mail-Sendewege gleichzeitig umgeformt. Staging-Nachweis mit **einem**
  echten Briefing-Versand an ausschließlich den Test-Trip (Kontingent!),
  danach IMAP-Prüfung per `briefing_mail_validator.py`.
- **Nachweisform (Test-Politik Kern-Schicht):** Sink am Transportrand, kein
  Mock-Theater. Vorbilder: `tests/tdd/test_telegram_test_mode_guard.py:278-303`
  (Fake-SMTP-Klasse), `tests/test_mail_recipient_parity.py:185-194`
  (Sentinel, der bewusst durch alle `except`-Zweige fällt).
- **Testdatei-Benennung nach Verhalten**, nicht nach Issue-Nummer
  (`tests/tdd/test_naming_gate.py` durchgesetzt) —
  `test_egress_single_dial_point.py` beschreibt das geprüfte Verhalten,
  nicht die Issue-Nummer.
- **Pfadregel #1409:** der neue Struktur-Test löst seinen Prüfling relativ
  zur eigenen Testdatei auf (`Path(__file__).resolve().parents[N]`), nie
  über einen festen Hauptrepo-Pfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine strukturelle Kapselung eines bestehenden,
  unveränderten Transportpfads — kein neues Architekturmuster, keine neue
  Entscheidungsfläche (Kanäle/Provider/Datenmodell/Auth bleiben unberührt).
  ADR-0006 (Sink statt Mock, E2E gegen Staging) und ADR-0015 (Dual-Stack
  Go+Python, kein gemeinsamer Code) werden bestätigt, nicht verändert.

## Changelog

- 2026-07-30: Initial spec created (S3a, aus `docs/context/fix-1412-s3-transport-kapselung.md`)
