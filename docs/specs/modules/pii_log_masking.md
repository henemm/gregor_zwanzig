---
entity_id: pii_log_masking
type: module
created: 2026-09-27
updated: 2026-09-27
status: draft
version: "1.0"
tags: [pii, logging, datenschutz, multi-user]
---

# PII-Log-Maskierung (Issue #2157, Epic #2138)

## Approval

- [ ] Approved

## Purpose

Mit echten Fremdnutzern liegen deren E-Mail-Adressen und Telegram-`chat_id`s im
Klartext im journald aller drei Services (Python-Core, `gregor-api`) sowie
persistent in `briefing_log.json`. Diese Spec verdrahtet die bereits
vorhandenen Domain-/Endziffern-Maskierer (`_mask_addr_for_log()`,
`maskAddrForLog()`, `mask_number()`) an den bislang unmaskierten Fundstellen —
unter Beibehaltung der PO-freigegebenen Diagnose-Fähigkeit aus #1847, die auf
Klartext bei genau zwei bekannten Betriebs-Testadressen angewiesen ist.

## Zentraler Zielkonflikt und seine Auflösung (verbindlich für diese Spec)

Issue #2157 verlangt Maskierung an denselben Codestellen, an denen Issue #1847
(Fast-Track, PO-Freigabe 2026-08-15, `docs/specs/fast/fix-1847-briefing-empfaenger-log.md`)
bewusst und ausdrücklich **unmaskiert** festgelegt hat — Begründung dort:
`gregor-test@henemm.com` und `gregor-staging@henemm.com` liegen unter
derselben Domain (`henemm.com`), eine reine Domain-Maskierung (`***@henemm.com`)
würde beide ununterscheidbar machen und exakt die Diagnose-Falle
reproduzieren, die #1847 gerade geschlossen hat (vierte Wiederholung: #1351,
#1403, #1782, #1847).

**Auflösung:** eine neue, statische Positivliste mit genau zwei Einträgen
(`gregor-test@henemm.com`, `gregor-staging@henemm.com`) — **explizit nicht**
`henning@henemm.com` (persönliches Konto). Eine Adresse auf dieser Liste
bleibt an jeder Stelle, an der sie protokolliert wird, im Klartext; jede
andere Adresse (= eine echte Nutzeradresse) wird domain-maskiert. Damit bleibt
die #1847-Diagnosezeit von rund einer Minute für die beiden bekannten
Betriebspostfächer erhalten, und echte Nutzeradressen sind erstmals
geschützt.

**Status #1847:** wird durch diese Spec **abgelöst, nicht stillschweigend
zurückgenommen**. Der Satz „Der Empfänger wird nicht maskiert" (bedingungslos)
in `docs/specs/fast/fix-1847-briefing-empfaenger-log.md` wird zu „… außer es
ist erwiesen keine bekannte Betriebs-/Test-Mailbox". Die Implementierung trägt
in dieser Datei eine Status-Zeile „Abgelöst durch #2157 (verengt auf bekannte
Betriebsadressen)" nach — CLAUDE.md-Pflicht: eine dokumentierte Entscheidung
wird nie still rückgängig gemacht.

**Ticket-Korrektur (`briefing_log.json.mail_to`):** Das Ticket verlangt dort
wörtlich einen Hash statt der Adresse. Tech-Lead-Korrektur: bei einem kleinen,
geschlossenen Adressraum (die eigene, bekannte Nutzerliste) ist ein Hash keine
echte Anonymisierung, sondern nur Pseudonymisierung — jeder mit
Datei-/journald-Zugriff kann jede Kandidatenadresse selbst hashen und den
Treffer zurückrechnen. Diese Spec verwendet stattdessen **denselben
Mechanismus** (Positivliste + Domain-Maskierung) auch für `mail_to` im
`briefing_log.json` — ein Mechanismus für Log-Zeile und JSON-Feld, kein
zweiter Code-Pfad.

## Source

- **Python-Core, neue Funktion:** `src/output/channels/email.py` — Konstante
  `_KNOWN_OPS_MAILBOXES` und Funktion `mask_addr_for_pii_log()`, direkt neben
  der bestehenden `_mask_addr_for_log()` (`:306-312`).
- **Go-API, neue Funktion:** `internal/mail/sender.go` — exportierter Wrapper
  `MaskAddrForLog()`, direkt neben der bestehenden privaten `maskAddrForLog()`
  (`:251-260`).

> **PFLICHT — Schicht-Hinweis:** Diese Spec berührt ausschließlich Backend
> (Python-Core `src/services/`, `src/output/channels/` und Go-API
> `internal/handler/`, `internal/mail/`). Kein Frontend-Anteil.

## Scope — Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/channels/email.py` | MODIFY | neu: `_KNOWN_OPS_MAILBOXES` + `mask_addr_for_pii_log()` neben `_mask_addr_for_log()` (`:306-312`) |
| `src/services/trip_report_scheduler.py:1674-1687,2095-2096` | MODIFY | Erfolgszeile + `_append_briefing_log()`-Aufruf: bekannte Ops-Mailbox unverändert, sonst Domain-Maskierung |
| `src/services/scheduler_dispatch_service.py:687` | MODIFY | Ortsvergleich-Erfolgszeile, dieselbe Regel |
| `src/services/notification_service.py:1999,2018,2041,2057,2072` | MODIFY | `chat_id`/`callback_query_id` per `mask_number()` maskiert (fünf Stellen) |
| `src/services/inbound_telegram_reader.py:594` | MODIFY | Registrierungs-Log: `chat_id` maskiert |
| `src/services/inbound_email_reader.py:195,299,303,306` | MODIFY | Absenderadresse per `mask_addr_for_pii_log()` maskiert |
| `internal/mail/sender.go` | MODIFY | neu: exportierter Wrapper `MaskAddrForLog()` neben der privaten `maskAddrForLog()` (`:251-260`) — s. „Technische Korrektur" |
| `internal/handler/auth_magic.go:89,109,112` | MODIFY | E-Mail in Magic-Link-Logs via `mail.MaskAddrForLog()` |
| `docs/specs/fast/fix-1847-briefing-empfaenger-log.md` | MODIFY | Status-Zeile „Abgelöst durch #2157 (verengt auf bekannte Betriebsadressen)" |
| `tests/unit/test_briefing_recipient_logging.py` | MODIFY | neuer Test: Fremdadresse wird maskiert (AC-b); bestehender AC-1-Test (#1847) bleibt unverändert grün (AC-a) |
| `tests/test_pii_log_guard.py` | CREATE | AST-Struktur-Ratsche (Python, Scope `src/`) — AC-f |
| `internal/handler/pii_log_guard_test.go` oder gleichwertiger Log-Capture-Test | CREATE | Verhaltensnachweis Magic-Link-Maskierung — AC-e (kein Go-AST-Pendant, s. Known Limitations) |
| `scripts/migrate_briefing_log_mail_to_mask.py` | CREATE | einmalige Bestandsmigration, Dry-Run-Flag, `.bak` — AC-g |
| `src/app/loader.py:1425` | MODIFY | Nachtrag RED-Phase: `chat_id`-Mehrdeutigkeits-Fehlerzeile, per `mask_number()` |
| `src/output/channels/telegram.py:210` | MODIFY | Nachtrag RED-Phase: Herkunftssperre-Warnung (#1476), `chat_id` per `mask_number()` |
| `src/services/inbound_telegram_reader.py:608` | MODIFY | Nachtrag RED-Phase: 409-Konflikt-Zeile, `chat_id` per `mask_number()` |

## Estimated Scope

- **LoC:** ~90-140 (Kern-Fix Python-Logging-Stellen + neue Funktion ~30-40;
  Go-Export-Wrapper + Fund-Fix ~10; Tests ~50-70; Migrationsscript ~15-25
  ohne Tests). Nahe dem 250-LoC-Workflow-Limit — `workflow.py status` vor
  Implementierungsbeginn prüfen, `loc_limit_override` ggf. nötig.
- **Files:** 12 (2 neu: Migrationsscript, Python-Guard-Test; 1 neu: Go-Guard-Test)
- **Effort:** medium — kein neuer Datenvertrag, aber Eingriff in eine
  PO-freigegebene Spec (#1847); Fehlerquelle bei falscher Maskierung wäre
  erneuter Diagnoseverlust, nicht Datenverlust.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.channels.email._mask_addr_for_log()` (Python, `:306-312`) | Funktion | Bestehender Domain-Maskierer (Issue #1219 AC-6) — wird von `mask_addr_for_pii_log()` intern für den Nicht-Ops-Fall aufgerufen, nicht dupliziert |
| `output.channels.email._extract_addr()` (Python, `:93-96`) | Funktion | Reduziert `"Name" <addr>`-Form auf die reine Adresse — Basis für den Positivlisten-Vergleich |
| `output.channels.seven_io_base.mask_number()` (Python, `:36-44`) | Funktion | Bestehende Endziffern-Maskierung für Rufnummern — wird für `chat_id`/`callback_query_id` wiederverwendet |
| `internal/mail.maskAddrForLog()` (Go, `:251-260`) | Funktion | Bestehender, aber **paketprivater** Domain-Maskierer — s. Technische Korrektur unten |

## Technische Korrektur gegenüber der Analyse — Go-Sichtbarkeit

Die Analyse (`docs/context/feature-2157-pii-log-maskierung.md`) empfiehlt für
`internal/handler/auth_magic.go`, „das bereits vorhandene `maskAddrForLog()`"
zu nutzen. Das ist am Code **nicht direkt möglich**: `maskAddrForLog` ist in
Kleinschreibung deklariert (`internal/mail/sender.go:251`) und damit
**paketprivat** — `auth_magic.go` liegt in `package handler`, einem anderen
Package, und kann die Funktion nicht importieren.

**Lösung:** ein neuer, minimaler exportierter Wrapper in `internal/mail/sender.go`:

```go
// MaskAddrForLog exportiert maskAddrForLog fuer Aufrufer ausserhalb dieses
// Pakets (#2157) -- die private Funktion selbst bleibt unveraendert, damit
// die Guard-Region-Namensliste in recipient_parity_test.go (":353") nicht
// beruehrt wird.
func MaskAddrForLog(raw string) string {
	return maskAddrForLog(raw)
}
```

Bewusst **kein** Umbenennen/Exportieren der bestehenden `maskAddrForLog()`
selbst: `internal/mail/recipient_parity_test.go:346-353` führt eine feste
Namensliste `guardRegionFuncs`, die per Textsuche (`extractFuncBody`) nach
`func maskAddrForLog(` sucht, um die Anzahl der Entscheidungspunkte in der
Guard-Region gegen eine Fixture-Zahl zu ratschen (`VerzweigungenGo`). Ein
Rename würde diesen Test hart brechen (`fehlend=[maskAddrForLog]`) und eine
Anpassung dieser Namensliste erzwingen — unnötiges Risiko für einen reinen
Sichtbarkeits-Fix. Der neue Wrapper hat selbst keine Verzweigung (0
Entscheidungspunkte) und liegt außerhalb der Guard-Region, verändert die
Ratschen-Zahl also nicht.

`auth_magic.go` ruft dann `mail.MaskAddrForLog(...)` (das Package ist dort
bereits als `mail` importiert, `internal/handler/auth_magic.go:29`).

## Implementation Details

### Python — neue Positivliste + Wrapper (`src/output/channels/email.py`)

```python
_KNOWN_OPS_MAILBOXES = frozenset({
    "gregor-test@henemm.com",
    "gregor-staging@henemm.com",
})


def mask_addr_for_pii_log(raw: str) -> str:
    """PII-Maskierung fuer echte Nutzeradressen (#2157) -- bekannte
    Betriebs-/Test-Postfaecher bleiben unmaskiert, damit die #1847-Diagnose
    (gregor-test@ vs. gregor-staging@, gleiche Domain) erhalten bleibt."""
    addr = _extract_addr(raw).strip().lower()
    if addr in _KNOWN_OPS_MAILBOXES:
        return raw
    return _mask_addr_for_log(raw)
```

`mask_addr_for_pii_log()` ist bewusst **öffentlich** (kein führender
Unterstrich) — anders als `_mask_addr_for_log()` (Issue #1219, nur für
Fehlermeldungen innerhalb `email.py` gedacht) wird sie modulübergreifend aus
`trip_report_scheduler.py`, `scheduler_dispatch_service.py` und
`inbound_email_reader.py` importiert.

### Fundstelle 1+2 — `src/services/trip_report_scheduler.py:1674-1687, 2095-2096`

Die Erfolgszeile und der `briefing_log.json`-Eintrag verwenden dieselbe
Variable `mail_empfaenger`. Sie wird unmittelbar nach der Zuweisung (`:1674-1676`)
für Protokollzwecke maskiert; die tatsächliche Zustellung ist zu diesem
Zeitpunkt bereits über `self._settings.mail_to` abgeschlossen, diese Variable
dient nur noch Log-Zeile und `briefing_log`-Eintrag:

```python
mail_empfaenger = (
    self._settings.mail_to if "email" in result.sent_channels else None
)
mail_empfaenger_fuer_log = (
    mask_addr_for_pii_log(mail_empfaenger) if mail_empfaenger else None
)
self._append_briefing_log(
    trip.id, report_type, result.sent_channels,
    angefordert=angefordert, mail_empfaenger=mail_empfaenger_fuer_log,
)
logger.info(
    "Trip report sent: %s (%s) via %s%s",
    trip.name, report_type, ",".join(result.sent_channels),
    f" to {mail_empfaenger_fuer_log}" if mail_empfaenger_fuer_log else "",
)
```

`_append_briefing_log()` selbst (`:2085-2102`) bleibt unverändert — sie
schreibt weiterhin unter dem Schlüssel `mail_to`, was hineingegeben wird, jetzt
eben den bereits maskierten Wert. Neuer Import am Kopf der Datei:
`from output.channels.email import mask_addr_for_pii_log`.

### Fundstelle 3 — `src/services/scheduler_dispatch_service.py:687`

```python
logger.info(
    "Compare preset %s sent to %s (top_ort=%s)",
    preset_id, mask_addr_for_pii_log(empfaenger) if empfaenger else empfaenger,
    top_ort,
)
```

Neuer Import: `from output.channels.email import mask_addr_for_pii_log`.

### Fundstelle 4 — `src/services/notification_service.py:1999,2018,2041,2057,2072`

`chat_id` (vier Stellen) und `callback_query_id` (eine Stelle) sind Telegram-
Kennungen, keine E-Mail-Adressen — Endziffern-Maskierung nach dem Vorbild
`seven_io_base.mask_number()`:

```python
logger.error(f"Telegram command reply failed for {mask_number(chat_id)}: {e}")   # :1999
logger.error(f"Telegram message failed for {mask_number(chat_id)}: {e}")          # :2018
logger.error(f"Telegram edit_message_text failed for {mask_number(chat_id)}/{message_id}: {e}")   # :2041
logger.error(f"Telegram delete_message failed for {mask_number(chat_id)}/{message_id}: {e}")      # :2057
logger.error(f"Telegram answer_callback_query failed for {mask_number(callback_query_id)}: {e}")  # :2072
```

`message_id` bleibt unmaskiert (kein PII, nur eine Nachrichten-Sequenznummer).
Neuer Import: `from output.channels.seven_io_base import mask_number`.

### Fundstelle 5 — `src/services/inbound_telegram_reader.py:594`

```python
logger.info(f"Telegram chat_id {mask_number(chat_id)} via token registriert")
```

Neuer Import: `from output.channels.seven_io_base import mask_number`.

### Fundstelle 6 — `src/services/inbound_email_reader.py:195,299,303,306`

Absenderadressen unbekannter/nicht-verifizierter Absender — hier gilt
**dieselbe** Positivliste+Domain-Regel wie oben (kein separater Mechanismus;
sollte je zufällig `gregor-test@`/`gregor-staging@` als Absender auftauchen,
verhält sich das konsistent zu allen anderen Stellen):

```python
logger.warning(f"Unresolved/ambiguous sender: {mask_addr_for_pii_log(from_addr)!r}")   # :195
logger.debug(f"Ignoring email from: {mask_addr_for_pii_log(sender)!r}")                # :299
logger.warning(f"Sender not verified: {mask_addr_for_pii_log(sender)!r}")              # :303
logger.warning(f"SPF/DKIM check failed: {mask_addr_for_pii_log(sender)!r}")            # :306
```

Neuer Import: `from output.channels.email import mask_addr_for_pii_log`.

### Fundstelle 7 — `internal/handler/auth_magic.go:89,109,112`

Einziger bestätigter Go-Fund (`auth.go`/`auth_oauth.go` loggen ausschließlich
die interne `userId`, keine E-Mail-Adresse — bestätigt über
`internal/store/user.go:134`, kein Scope). Kein #1847-Konflikt (reiner
Auth-Vorgang, keine Test/Staging-Unterscheidung nötig) — hier reicht die
uneingeschränkte Maskierung:

```go
log.Printf("magic-link: SMTP not configured, skipping email to %s", mail.MaskAddrForLog(normalizedEmail))  // :89
...
log.Printf("magic-link: mail send failed for %s: %v", mail.MaskAddrForLog(to), err)                         // :109
...
log.Printf("magic-link: mail send timeout (20s) for %s", mail.MaskAddrForLog(to))                           // :112
```

## Migration von `briefing_log.json`-Bestandsdaten

`_append_briefing_log()` hat keine Rotation — bestehende Klartext-`mail_to`-
Werte blieben ohne Migration dauerhaft auf Prod-Disk. Neues, einmaliges
Script `scripts/migrate_briefing_log_mail_to_mask.py`:

- Iteriert `data/users/<user_id>/briefing_log.json` für jeden Nutzer.
- **Read-Modify-Write, kein Replace** (CLAUDE.md-Pflicht „Daten-Schema-Reworks"):
  lädt die Datei vollständig, ersetzt ausschließlich `entries[].mail_to` über
  `mask_addr_for_pii_log()`, alle anderen Felder unverändert.
- Legt **selbst** ein `.bak` neben der Zieldatei an, bevor geschrieben wird —
  `data_schema_backup.py` greift hier **nicht** (`SCHEMA_PATHS` enthält weder
  `trip_report_scheduler.py` noch die Datendatei selbst).
- `--dry-run`-Flag: zeigt die Änderungen an, schreibt nichts.
- Gibt am Ende einen Zähler aus: `N Einträge maskiert, M unverändert
  (bereits Ops-Adresse oder kein mail_to-Feld)`.

**Messbarkeits-Klausel (PFLICHT):** Staging-Datenbestand ist für `hem` nicht
lesbar, Prod-Daten liegen unter `/var/lib/gregor`. Der Migrationserfolg wird
**nicht** durch Werteinsicht nachgewiesen, sondern durch einen
Vorher/Nachher-Zählervergleich: Das Script wird auf Prod im Rahmen des
Deploy-Schritts einmal mit `--dry-run` (zeigt N erwartete Änderungen) und
danach ohne `--dry-run` (meldet N tatsächlich durchgeführte Änderungen)
ausgeführt; beide Zahlen müssen übereinstimmen. Ohne diesen Abgleich bleibt
der Nachweis bei `NOT_MEASURABLE_ON_STAGING`.

**Abgrenzung:** Die fehlende Rotation/Obergrenze der Datei selbst ist ein
separates Retention-Thema und **nicht** Teil dieser Spec (siehe Known
Limitations).

## Expected Behavior

- **Input:** Eine E-Mail-Adresse oder Telegram-`chat_id`/`callback_query_id`,
  die an einer der sieben Fundstellen protokolliert würde.
- **Output:** Bekannte Betriebs-/Test-Mailboxen (`gregor-test@henemm.com`,
  `gregor-staging@henemm.com`) erscheinen unverändert im Klartext. Jede
  andere E-Mail-Adresse erscheint als `***@domain.tld`. Telegram-Kennungen
  erscheinen als `…` + letzte drei Ziffern (bzw. `<leer>` bei leerem Wert,
  bestehendes `mask_number()`-Verhalten).
- **Side effects:** `briefing_log.json` speichert ab sofort den maskierten
  Wert unter `mail_to`, nicht mehr die volle Adresse (außer bei
  Ops-Mailboxen). Bestandseinträge werden durch das Migrationsscript separat
  bereinigt (kein automatischer Effekt dieser Code-Änderung allein).

## Acceptance Criteria

- **AC-a:** Given ein Trip mit `mail_to = "gregor-test@henemm.com"` (bekannte
  Ops-Adresse) / When das Briefing erfolgreich versendet wird / Then enthält
  sowohl die Erfolgszeile als auch der `briefing_log.json`-Eintrag die
  Adresse `gregor-test@henemm.com` unmaskiert im Klartext.
  - Test: `tests/unit/test_briefing_recipient_logging.py`,
    `test_erfolgszeile_enthaelt_die_empfaengeradresse` (bestehend, #1847) —
    bleibt unter dieser Spec unverändert grün.

- **AC-b:** Given ein Trip mit `mail_to = "finder@example.org"` (echte,
  unbekannte Fremdadresse) / When das Briefing erfolgreich versendet wird /
  Then enthält weder die Erfolgszeile noch der `briefing_log.json`-Eintrag
  die volle Adresse — beide zeigen `***@example.org`.
  - Test: neuer Test in `tests/unit/test_briefing_recipient_logging.py`
    (`caplog` + gelesene `briefing_log.json`, echter Versandpfad wie im
    Bestandstest, nur `EMPFAENGER = "finder@example.org"`).

- **AC-c:** Given ein Telegram-Sendefehler oder eine Registrierung mit
  `chat_id = "123456789"` / When die entsprechende Fehler- bzw.
  Registrierungszeile protokolliert wird / Then enthält die Zeile nicht die
  volle `chat_id`, sondern nur die letzten drei Ziffern mit `…`-Präfix.
  - Test: `caplog`-Nachweis gegen `notification_service.send_telegram_message`
    (bzw. eine der vier anderen betroffenen Methoden) und gegen
    `inbound_telegram_reader`s Registrierungspfad — jeweils mit einer
    künstlich fehlschlagenden/erfolgreichen Telegram-Antwort, kein Mock der
    Maskierungsfunktion selbst.

- **AC-d:** Given eine E-Mail von einer nicht autorisierten oder nicht
  verifizierten Absenderadresse / When `inbound_email_reader` die Nachricht
  verarbeitet und ablehnt / Then nennt die resultierende `warning`/`debug`-
  Zeile die Absenderadresse nur maskiert (`***@domain.tld`).
  - Test: neuer `caplog`-Nachweis in einer bestehenden oder neuen Testdatei
    für `inbound_email_reader._authorize()`/`_resolve_settings_for_sender()`
    mit einer echten Fremdadresse als Absender.

- **AC-e:** Given ein Magic-Link-Login-Versuch (SMTP nicht konfiguriert,
  Versand fehlgeschlagen, oder Versand-Timeout) / When `auth_magic.go` die
  jeweilige Zeile protokolliert / Then erscheint die E-Mail-Adresse nur als
  `***@domain.tld`.
  - Test: `internal/handler`-Testfall, der `log.Printf`-Ausgabe abfängt
    (Vorbild: bestehende Log-Capture-Muster in `internal/handler`, sonst
    `os.Pipe`-Redirect um `log.SetOutput` für die Testlaufzeit) und die
    Abwesenheit der vollen Adresse in der Ausgabe nachweist, für mindestens
    den Zeitüberschreitungs- oder Fehlerfall (:109/:112).

- **AC-f:** Given der bestehende Code-Bestand nach Umsetzung dieser Spec /
  When der AST-Struktur-Wächter über `src/` läuft / Then meldet er keine
  Fundstelle. Given danach eine neue, unmaskierte `logger.*`-Zeile mit einem
  bare `chat_id`- oder `empfaenger`-Argument künstlich in einen isolierten
  Testbaum gepflanzt wird / When derselbe Wächter darüber läuft / Then wird
  genau diese Stelle benannt gemeldet.
  - Test: `tests/test_pii_log_guard.py`, zwei Fälle wie im Vorbild
    `tests/test_user_id_default_guard.py` (`test_ac9_...`-Empfindlichkeitstest
    gegen einen gepflanzten `tmp_path`-Baum, plus ein Ist-Stand-Test gegen
    `src/`).

- **AC-g:** Given `briefing_log.json`-Bestandsdateien mit Klartext-`mail_to`
  aus der Zeit vor dieser Spec / When `scripts/migrate_briefing_log_mail_to_mask.py`
  zuerst mit `--dry-run` und danach ohne `--dry-run` läuft / Then meldet der
  Dry-Run dieselbe Anzahl zu ändernder Einträge wie der echte Lauf tatsächlich
  ändert, eine `.bak`-Kopie existiert vor dem Schreiben, und alle Felder außer
  `mail_to` bleiben in jedem Eintrag unverändert.
  - Test: neuer Test auf einem in `tmp_path` präparierten
    `briefing_log.json` mit gemischten Einträgen (Ops-Adresse, Fremdadresse,
    kein `mail_to`-Feld) — Zähler-Vergleich Dry-Run vs. echter Lauf,
    `.bak`-Existenz, Roundtrip der unveränderten Felder.

## Mutations-Gegenprobe (PFLICHT-Bestandteil, für Phase 5 Adversary)

Drei benannte Verfälschungen, die die Implementierung aktiv brechen müssen:

1. **Positivlisten-Check entfernen** (`if addr in _KNOWN_OPS_MAILBOXES: return raw` streichen) →
   AC-a muss rot werden (`gregor-test@henemm.com` erscheint plötzlich maskiert,
   #1847-Diagnose bricht wieder).
2. **Alles maskieren, auch Listeneinträge** (Positivlisten-Prüfung durch
   `False` ersetzen) → der bestehende `test_erfolgszeile_enthaelt_die_empfaengeradresse`
   (#1847, AC-1) muss rot werden.
3. **Nichts maskieren** (`mask_addr_for_pii_log()`/`mask_number()`/
   `MaskAddrForLog()` durch Identitätsfunktion ersetzen) → der neue
   AC-b-Gegentest (Fremdadresse) muss rot werden.

Jede dieser drei Mutationen muss vom `implementation-validator` tatsächlich
eingespielt und das Testergebnis dokumentiert werden — ein grüner Lauf ohne
diese Gegenprobe beweist nur, dass die Tests durchlaufen, nicht dass sie die
Zusicherung bewachen.

## Regel-Budget (CLAUDE.md-Pflicht)

`tests/test_pii_log_guard.py` (und sein Go-Pendant, s. Known Limitations) ist
ein **neues Gate** — es ersetzt keine bestehende Regel. **Prüfdatum:
2026-12-26** (+90 Tage ab Spec-Erstellung). Am Prüfdatum: kein nachweisbarer
Fang seit Einführung (keine neue unmaskierte Fundstelle wurde je vom Wächter
verhindert) → Rückbau prüfen, Eintrag in die Prüfdaten-Tabelle
(`docs/reference/gates_und_ratschen.md`).

## Nachtrag (RED-Phase, 2026-09-27) — drei zusätzliche Fundstellen

Der AST-Wächter (AC-f) lief im RED-Schritt bereits gegen den Ist-Stand von `src/`
und meldete drei unmaskierte `chat_id`-Fundstellen, die in der ursprünglichen
Analyse nicht erfasst waren: `src/app/loader.py:1425` (Mehrdeutigkeits-Fehler,
Issue #2141), `src/output/channels/telegram.py:210` (Herkunftssperre-Warnung,
Issue #1476), `src/services/inbound_telegram_reader.py:608` (409-Konflikt,
Issue #2141). Alle drei sind reine Telegram-`chat_id`-Werte (kein E-Mail-Bezug,
keine Berührung des #1847-Konflikts) und werden mit derselben, bereits
freigegebenen `mask_number()`-Regel behoben wie die übrigen `chat_id`-Stellen.
Das ist eine Vervollständigung der bereits freigegebenen Zusicherung AC-f
(„Wächter über den gesamten `src/`-Baum meldet keine Fundstelle") um die drei
oben in „Scope — Affected Files" nachgetragenen Zeilen — keine neue
Grundsatzentscheidung, daher keine erneute PO-Freigabe nötig.

## Known Limitations

- **Namensbasierter Wächter fängt keine Aliase.** `tests/test_pii_log_guard.py`
  erkennt nur die exakten Bezeichner `mail_to`, `empfaenger`, `chat_id` als
  direktes, unverpacktes Argument eines `logger.*`-Aufrufs. Ein Alias
  (`addr = trip.mail_to; logger.info(addr)`) oder eine andere Variablen-
  benennung (wie `from_addr`, `sender`, `mail_empfaenger`, `to`,
  `normalizedEmail`, `callback_query_id` — alle in dieser Spec bereits fix
  code-review-geprüft) entgeht dem Wächter strukturell. Der tatsächliche
  Schutz für die sieben in dieser Spec behobenen Fundstellen kommt aus dem
  Code selbst plus den Verhaltenstests (AC-b bis AC-e), nicht aus dem
  Namens-Wächter — der Wächter ist ausschließlich eine Regression-Bremse für
  **künftigen** Code, der diese drei kanonischen Namen wieder unmaskiert
  verwendet.
- **Go-Struktur-Wächter ist ein einzelner, gezielter Test, kein generisches
  AST-Werkzeug.** Für `internal/handler/auth_magic.go` gibt es keinen im
  Projekt etablierten Go-AST-Scanner (das Python-Vorbild `ast`-Modul kann kein
  Go parsen). Diese Spec deckt die drei bekannten Zeilen über den
  Verhaltenstest AC-e ab; ein strukturelles Pendant zum Python-Wächter für
  künftige neue Go-Fundstellen ist **nicht** Teil dieser Spec (Scope wäre ein
  eigenständiges Werkzeug über `go/parser`/`go/ast`) — bei Bedarf eigenes
  Ticket, kein Blocker hier, da `auth_magic.go` der einzige bestätigte
  Go-Fund ist und nach dieser Spec behoben wird.
- **SMS-/Premium-SMS-Rufnummern nicht Teil dieser Spec.** Ob sich
  Test- und Prod-Rufnummer in den letzten drei Ziffern (`mask_number()`)
  unterscheiden, war ohne Ausgabe echter Nummern nicht zu klären. Telegram-
  `chat_id` ist rein numerisch mit großem Namensraum (Kollisionsrisiko
  vernachlässigbar) und daher unkritisch für diese Spec. Sollte sich
  herausstellen, dass SMS-Test-/Prod-Nummern sich in den letzten drei Ziffern
  nicht unterscheiden, gilt dieselbe #1847-Diagnosefalle auch dort — eigenes
  Folge-Ticket, kein Teil dieser Spec.
- **Retention/Rotation von `briefing_log.json`** (Datei wächst unbegrenzt) ist
  ein separates Aufbewahrungsthema und nicht Teil dieser Spec — sie bereinigt
  nur den Inhalt (Klartext → maskiert), nicht die Dateigröße.
- **Zwei parallele Telefonnummer-Maskierer** (`seven_io_base.mask_number()`
  vs. `inbound_sms_reader._mask()`) bleiben unkonsolidiert — Konsolidierung
  ist Scope-Erweiterung, nicht Teil dieses Tickets.
- **`internal/handler/data_export_test.go`** prüft weiterhin nur
  Feld-Vorhandensein in `user.json` (eigenes `mail_to`-Profilfeld,
  Datenexport #2270), nicht den hier geänderten `briefing_log.json`-Inhalt —
  unberührt von dieser Spec.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer Architekturentscheid — diese Spec verdrahtet
  bestehende Maskierungsbausteine konsequenter, ohne einen neuen
  Kanal-, Provider-, Daten- oder Auth-Vertrag einzuführen. Die einzige
  grundsätzliche Entscheidung (Positivliste statt Hash, Auflösung des
  #1847-Konflikts) ist auf Spec-Ebene dokumentiert und markiert #1847 explizit
  als „abgelöst durch #2157" — ein separates ADR wäre laut CLAUDE.md nur für
  Entscheidungsflächen wie Kanäle/Provider/Datenmodell/Auth Pflicht, eine
  Log-Maskierungsregel ist Spec-Ebene.

## Changelog

- 2026-09-27: Initial spec created
