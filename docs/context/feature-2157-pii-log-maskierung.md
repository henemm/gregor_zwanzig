# Context: feature-2157-pii-log-maskierung

## Request Summary

Issue #2157 (Teil von Epic #2138, Multi-User-Readiness, Schwere Hoch): Empfängeradressen,
Telegram-`chat_id`s und Absenderadressen landen an mehreren Stellen im Klartext im
Prozess-Journal (journald) und einmal persistent in `briefing_log.json`. Erwartung des
Tickets: überall maskieren (Domain- bzw. Endziffern-Maskierung), `briefing_log.json` einen
Hash statt der Adresse speichern lassen, dazu ein Wächter-Test gegen künftige unmaskierte
`logger.*`-Aufrufe.

## 🔴 Zentraler Zielkonflikt — MUSS in Analyse/Spec aufgelöst werden

**#2157 verlangt genau die Maskierung, die #1847 (Fast Track, PO-freigegeben 2026-08-15)
bewusst und ausdrücklich ABGELEHNT hat — für dieselben Codestellen.**

- `trip_report_scheduler.py` (Erfolgszeile `Trip report sent: … via … to <adresse>` +
  `briefing_log.json`-Eintrag `mail_to`) trägt einen Kommentar, der wörtlich sagt: „Bewusst
  UNMASKIERT — eine Maskierung machte gregor-test@ und gregor-staging@ ununterscheidbar und
  verfehlte genau den Zweck." Das ist keine Altlast, sondern die dokumentierte Begründung
  einer freigegebenen Spec: `docs/specs/fast/fix-1847-briefing-empfaenger-log.md`, Abschnitt
  „Was darf sich nicht ändern": „**Der Empfänger wird nicht maskiert.** Bewusste
  Entscheidung … Der Compare-Pfad protokolliert ebenfalls unmaskiert."
- Vorgeschichte: **vierte Wiederholung derselben Falle** (#1351, #1403, #1782, #1847) — ohne
  den Klartext-Empfänger in der Log-Zeile dauerte „Versand gemeldet, Postfach leer" jedes
  Mal wieder eine Stunde Diagnose statt einer Minute.
- **Die im Ticket vorgeschlagene Domain-Maskierung würde das Problem nicht lösen, sondern
  exakt reproduzieren:** `gregor-test@henemm.com` und `gregor-staging@henemm.com` (aus
  `docs/reference/operations_playbook.md:639`) unterscheiden sich NUR im Local-Part, nicht
  in der Domain. Beide würden zu `***@henemm.com`. Die Erwartung „Domain reicht" ist am
  Bestand nachweislich falsch — beide Betriebs-Testadressen liegen unter derselben Domain.
- `briefing_log.json.mail_to` wird von Go (`internal/store/log.go:10-15`) **nicht** geparst
  (`BriefingLogEntry`-Struct kennt das Feld nicht, unbekannte JSON-Felder werden beim
  Unmarshal ignoriert) — das Feld hat **keinen** Frontend-Konsument. Es ist ausschließlich
  für die menschliche Diagnose auf Staging/Prod gedacht (siehe #1847-Spec, „Reihenfolge, die
  in einer Minute entscheidet" in `operations_playbook.md:642-651`). Ein Hash macht diese
  Diagnose wieder unmöglich, ohne dass irgendwer davon profitiert (kein UI zeigt den Wert an).

**Was das für die Analyse-Phase bedeutet:** Eine 1:1-Umsetzung der Ticket-„Erwartung" würde
eine PO-freigegebene, mehrfach begründete Entscheidung stillschweigend rückgängig machen
(CLAUDE.md: „Eine dokumentierte Entscheidung wird nie still rückgängig gemacht"). Eine
denkbare Auflösung (nicht vorentschieden, gehört in die Spec): zwischen **echten
Nutzeradressen** (maskierungspflichtig — das ist der eigentliche Zweck von #2157, siehe
„Mit fremden Nutzern liegen deren Adressen … im journald aller drei Services") und einer
**kleinen, festen Liste bekannter Betriebs-/Testadressen** unterscheiden, die unmaskiert
bleiben (Vorbild: die Positivliste `admin`, `default`, `henning`, `steffi` aus
`operations_playbook.md:505-506`, dort für #1133 bereits als Konzept etabliert — dort aber
ein Cleanup-Script, kein wiederverwendbarer Helfer im Kernpfad). Alternative: Local-Part
zusätzlich zur Domain teilmaskiert ausgeben (z. B. erste 3 Zeichen + Länge), was
`gregor-test@` von `gregor-staging@` unterscheidbar hielte, ohne die volle Adresse zu zeigen.
**Diese Entscheidung braucht eine explizite PO-Freigabe in der Spec-Phase**, weil sie eine
frühere Freigabe berührt.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:1665-1687, 2049-2103` | Erfolgszeile + `_append_briefing_log()` — bewusst unmaskiert seit #1847, Kernkonflikt oben |
| `src/services/scheduler_dispatch_service.py:687` | `logger.info("Compare preset %s sent to %s (top_ort=%s)", …)` — Vorbild-Zeile, auf die #1847 sich beruft; ebenfalls unmaskiert |
| `src/services/notification_service.py:1999,2018,2041,2057,2072` | Telegram-Fehlerzeilen mit rohem `chat_id`/`callback_query_id` |
| `src/services/inbound_telegram_reader.py:594` | `logger.info(f"Telegram chat_id {chat_id} via token registriert")` — roh |
| `src/services/inbound_email_reader.py:195,299,303,306` | `from_addr`/`sender` roh in warning/debug (`Unresolved/ambiguous sender`, `Ignoring email from`, `Sender not verified`, `SPF/DKIM check failed`) |
| `src/output/channels/email.py:306-312` | `_mask_addr_for_log()` — vorhandener Domain-Maskierer (Issue #1219 AC-6), aber nur für Fehlermeldungen im Sendepfad genutzt, nicht für die o.g. Stellen |
| `src/output/channels/seven_io_base.py:36-44` | `mask_number()` — Rufnummer auf letzte 3 Stellen, Vorbild für SMS/Premium-SMS |
| `src/services/inbound_sms_reader.py:484-488` | `_mask()` — eigene, leicht abweichende Zahlen-Maskierung (Sternchen statt `…`) — zweite Implementierung desselben Zwecks, evtl. Konsolidierungskandidat, aber nicht Teil des Tickets |
| `docs/specs/fast/fix-1847-briefing-empfaenger-log.md` | PO-freigegebene Spec, die die aktuelle Unmaskierung begründet — zentrale Gegenprobe für die neue Spec |
| `docs/reference/operations_playbook.md:499-506, 636-666` | Positivliste (#1133) + die drei Postfächer `gregor-test@`/`gregor-staging@`/lokal, alle unter `henemm.com` |
| `internal/store/log.go:9-43` | Go-seitiger Lesepfad von `briefing_log.json` — `mail_to` wird nicht geparst, kein Frontend-Konsument |
| `internal/handler/data_export_test.go:182,282` | `briefing_log.json` fließt roh in den Datenexport (#2270) — das ist das Exportieren der EIGENEN Daten des Nutzers, kein Cross-User-Leck; ein Hash statt Adresse würde dort nur den Eigenwert des Exports schmälern |

## Existing Patterns

- **Domain-Maskierung:** `email.py:_mask_addr_for_log()` — `***@domain.tld`. Bereits Vorbild
  im Ticket genannt, aber nicht an den Fundstellen verdrahtet.
- **Endziffern-Maskierung (Rufnummern):** zwei leicht abweichende Implementierungen
  (`seven_io_base.py:mask_number` mit `…`-Präfix, `inbound_sms_reader.py:_mask` mit
  `*`-Präfix) — beide zeigen die letzten 3 Stellen.
- **Wächter-Tests per AST-Scan** (nicht Regex/Textsuche) sind der etablierte Stil für
  „keine neue Fundstelle darf entstehen"-Zusicherungen: `tests/test_user_id_default_guard.py`
  (Vorbild `test_output_timezone_guard.py`) mit fester Ratschen-Menge (`_SRC_BESTAND`), die
  nur schrumpfen darf. Für #2157 passt dasselbe Muster: eine Ratsche für bereits bekannte,
  bewusst unmaskierte Stellen (die im Ticket selbst benannten, sofern die Spec sie als
  Ausnahme freigibt) plus Vollsperre für alles Neue.
- **`# doc-compliance-test`-Marker** kennzeichnet Wächter, die den Quelltext selbst
  durchsuchen (erlaubte Ausnahme vom Verbot reiner Dateiinhalt-Checks, CLAUDE.md).

## Dependencies

- **Upstream:** keine — reine Protokollierungs-/Persistenz-Änderung, kein neuer Provider-
  oder API-Vertrag.
- **Downstream:**
  - `internal/store/log.go` liest `briefing_log.json`, aber ignoriert `mail_to` bereits —
    ein Hash statt Klartext bricht dort nichts.
  - `internal/handler/data_export_test.go` / Datenexport (#2270) liest die Datei roh für den
    Export der eigenen Nutzerdaten weiter — unkritisch, aber als Nebenwirkung zu nennen.
  - Menschliche Diagnose auf Staging/Prod (`operations_playbook.md`, #1847-Workflow) — DAS
    ist die eigentliche Downstream-Abhängigkeit, die eine naive Maskierung bricht.

## Existing Specs

- `docs/specs/fast/fix-1847-briefing-empfaenger-log.md` — direkter Gegenspieler, siehe oben.
- `docs/specs/fast/fix-1535-env-snapshot-maskieren.md` — anderer Maskierungs-Kontext
  (ENV-Snapshot/Secrets), evtl. Stil-Vorbild, aber anderer Anwendungsfall (Secrets, nicht
  PII von Endnutzern).
- Kein bestehendes ADR zu Log-PII; #2157 wäre die erste Grundsatzentscheidung dazu — ADR-
  Pflicht besteht laut CLAUDE.md nur für Entscheidungsflächen wie Kanäle/Provider/Datenmodell,
  eine Log-Maskierungsregel ist eher Spec- als ADR-Ebene, sollte aber in der Spec explizit
  gegen die #1847-Spec abgegrenzt werden (Status "abgelöst durch" oder "bewusste Ausnahme
  bestätigt").

## Risks & Considerations

1. **Zentraler Konflikt** siehe oben — das größte Risiko, weil eine naive Umsetzung sowohl
   das Ticket verfehlt (Domain maskiert nicht test/staging) als auch eine frühere Freigabe
   bricht.
2. **Zwei parallele Telefonnummer-Maskierer** (`mask_number` vs. `_mask`) — Konsolidierung
   wäre Scope-Erweiterung, nicht Teil des Tickets; nur vermeiden, dass eine dritte Variante
   für E-Mail/`chat_id` entsteht, wo eine der beiden Signaturen wiederverwendbar wäre.
3. **`briefing_log.json` ist Bestandsdatei** — bestehende Einträge tragen bereits Klartext-
   `mail_to`. Laut CLAUDE.md-Regel „Daten-Schema-Reworks" ist das kein Feld-Wegfall, sondern
   eine Änderung des Inhalts eines bestehenden Feldes; Bestandseinträge müssen nicht migriert
   werden (kein Datenverlust-Risiko wie bei Trip-Modellen), sollten aber in der Spec kurz
   erwähnt werden (alte Klartext-Einträge bleiben, bis sie aus dem Fenster fallen — Go filtert
   ohnehin nicht danach).
4. **Wächter-Testumfang:** Ticket verlangt „kein `logger.*` mit `mail_to`, `empfaenger`,
   `chat_id` als rohem Argument in `src/`" — das ist eine Positiv-Textsuche auf Parameter-
   Namen, keine Aussage über den tatsächlich geloggten WERT. Ein AST-Scan auf verbotene
   Bezeichner in `logger.*`-Aufrufen (wie `test_user_id_default_guard.py`) trifft nur
   Variablen mit genau diesem Namen — ein Alias (`addr = trip.mail_to; logger.info(addr)`)
   entginge. Die Spec sollte festlegen, ob der Wächter strukturell (AST, Namens-Traversal)
   oder als Verhaltenstest (caplog gegen echte Adressmuster, `@`-haltige Strings) läuft —
   Letzteres ist robuster gegen Umbenennung, aber aufwändiger.
5. **Live-Nachweis nötig, kein Mock:** Die eigentliche Zusicherung wirkt im `logging`-Modul
   zur Laufzeit, nicht im Quelltext — ein reiner Dateiinhalt-Check wäre laut Testpolitik
   verbotenes „Mock-Theater"/Textsuche als Verhaltensnachweis (Ausnahme nur mit
   `# doc-compliance-test`, und dann nur für den STRUKTUR-Wächter, nicht für den
   Verhaltensnachweis „wird tatsächlich maskiert geloggt").

## Analysis

### Type

Bug (Label `bug`, Schwere Hoch/Datenschutz) mit Feature-Charakter — kein defektes Verhalten
im Sinne „funktioniert nicht wie spezifiziert", sondern eine neue, quer über drei Services
verdrahtete Maskierungsregel, die eine frühere, PO-freigegebene Spec (#1847) gezielt verengt.

### Zentraler Konflikt — Auflösung (Tech-Lead-Empfehlung, kein Vorentscheid)

Alle unten genannten Zeilennummern sind auf HEAD dieses Worktrees frisch verifiziert.

**Der Konflikt löst sich vollständig auf, wenn zwischen bekannten Betriebs-/Testadressen und
echten Fremdnutzer-Adressen unterschieden wird — und diese Unterscheidung existiert im Code
bereits, wird nur an den PII-Stellen nicht genutzt:**

- **Korrektur nach Gegenprobe (Plan-Agent):** `internal/mail/sender.go:loadResendAllowlist()`
  (:189-245) ist NICHT wiederverwendbar — das ist eine dynamische, pro Nutzer aus
  `user.json`-Profilen aufgebaute Versand-Berechtigungsliste (Frage: „wer darf als
  verifizierter Empfänger gelten"), keine statische „diese Adresse ist ein bekanntes
  Systempostfach"-Liste. `rawContainsTestMailbox()`/`isReservedTestDomain()` (:145,:282)
  dienen demselben engen Fangnetz-Zweck (Resend-Guard) und sind ebenfalls nicht der
  richtige Ort, um eine Logging-Entscheidung von abhängig zu machen — andere
  Änderungs-/Testverantwortung.
- **Empfehlung (korrigiert):** eine **neue, sehr kleine, statische Konstante** (2 Einträge:
  `gregor-test@henemm.com`, `gregor-staging@henemm.com`) — explizit **nicht**
  `henning@henemm.com` (persönliches Konto, gehört nicht auf eine „darf im Log/JSON im
  Klartext stehen"-Liste). An den #1847-Konfliktstellen (Trip-Briefing- und
  Ortsvergleich-Erfolgszeile, `briefing_log.json`) gilt: Adresse auf dieser Liste →
  **weiterhin voll geloggt** (erhält die #1847-Diagnosezeit von ~1 Minute unverändert);
  jede andere (= echte Nutzer-)Adresse → Domain-Maskierung über die bereits vorhandenen
  `_mask_addr_for_log()` (Python, `email.py:306-312`) bzw. `maskAddrForLog()` (Go,
  `internal/mail/sender.go:251-260`). Domain-only genügt für die Unterscheidung zwischen
  zwei ECHTEN Nutzern, weil `user_id`/Trip-ID bereits im selben Logeintrag stehen.
- **Ticket-Vorgabe „Hash statt Adresse" für `briefing_log.json` — Tech-Lead-Korrektur:**
  ein Hash ist hier keine echte Anonymisierung, sondern nur Pseudonymisierung: bei einem
  kleinen, geschlossenen Adressraum (die eigene Nutzerliste) kann jeder mit Datei-/
  journald-Zugriff jede Kandidatenadresse selbst hashen und den Treffer zurückrechnen —
  das DSGVO-Schutzziel wird verfehlt, bei zusätzlichem Implementierungsaufwand. Empfehlung:
  **dieselbe Positivliste + Domain-Maskierung** auch für `briefing_log.json.mail_to`
  verwenden statt eines separaten Hash-Mechanismus — ein Mechanismus für Log-Zeile UND
  JSON-Feld, kein zusätzlicher Code-Pfad. Diese Abweichung von der Ticket-Formulierung
  gehört explizit benannt in die Spec (technische Begründung, keine PO-Frage).
- **Wichtiger Nebeneffekt:** `tests/unit/test_briefing_recipient_logging.py:207`
  (`test_erfolgszeile_enthaelt_die_empfaengeradresse`) nutzt als Testadresse
  `EMPFAENGER = "gregor-test@henemm.com"` (:57) — das ist selbst eine bekannte
  Betriebs-Mailbox. Der Test bliebe unter diesem Schema **unverändert grün**, weil
  `gregor-test@` auf der Erkennungsliste steht und weiterhin unmaskiert erscheint. Nötig ist
  trotzdem ein **neuer** Test, der eine echte Fremdadresse (z. B. `finder@example.org`)
  durch denselben Pfad schickt und die Domain-Maskierung nachweist — sonst bliebe die
  eigentliche Zusicherung des Tickets unbewacht.
- **Was sich an #1847 ändert (muss in der Spec explizit als „abgelöst durch #2157"
  markiert werden):** der Satz „Der Empfänger wird nicht maskiert" (bedingungslos) wird zu
  „… außer es ist erwiesen keine bekannte Betriebs-/Test-Mailbox". Keine stille Rücknahme,
  weil die Spec das Wort „abgelöst durch" trägt (CLAUDE.md-Pflicht).
- `docs/reference/operations_playbook.md:647` (Diagnose-Rezept, zeigt
  `... to gregor-test@henemm.com` in der Log-Zeile) bleibt **unverändert korrekt**, weil
  `gregor-test@` unmaskiert bleibt — keine Doku-Anpassung nötig, nur als Gegenprobe in der
  Spec erwähnen.
- **Offene technische Frage für die Spec-Phase (Plan-Agent, nicht abschließend geklärt):**
  Der Ticket-Titel nennt auch „Chat-IDs und Absender" — betrifft SMS/Premium-SMS
  (`mask_number()` in `seven_io_base.py:36-44`, `_mask()` in `inbound_sms_reader.py`, beide
  zeigen nur die letzten 3 Ziffern). Ob Test- und Prod-Rufnummer sich in den letzten 3
  Ziffern unterscheiden, war ohne Ausgabe echter Nummern nicht zu klären. Falls nein, gilt
  dasselbe #1847-Diagnoseproblem auch für SMS, und die Positivliste müsste kanalübergreifend
  gedacht werden (Rufnummern statt/zusätzlich zu E-Mail-Adressen). Telegram-`chat_id` ist rein
  numerisch mit großem Namensraum — dort ist das Kollisionsrisiko vernachlässigbar.

### Neuer Befund — Scope-Erweiterung nötig (im Ticket-Text NICHT enthalten)

`internal/handler/auth_magic.go:89,109,112` loggt beim Magic-Link-Login über `log.Printf`
die volle Klartext-E-Mail-Adresse (`normalizedEmail`/`to`) echter Nutzer. **Korrektur nach
Gegenprobe:** dies ist der EINZIGE echte E-Mail-PII-Fund auf der Go-Seite — die zunächst
vermuteten ~20 weiteren Stellen in `auth.go`/`auth_oauth.go` (Passwort-Reset,
E-Mail-Verifikation, OAuth, Tier-Change) loggen durchweg `req.Username`/`userId`, was in
diesem Codebase die **interne Nutzer-ID** ist, keine E-Mail-Adresse (bestätigt über
`internal/store/user.go:134`, Signatur `SaveResetToken(userId string, …)` — `req.Username`
wird dort 1:1 als `userId` übergeben). Diese Stellen sind aus dem Scope zu streichen. Das
Ticket nennt nur Python-Dateien, aber der Zweck des Tickets („im journald aller drei
Services") trifft auf `auth_magic.go` exakt zu — `gregor-api` ist einer der drei Services.
Diese drei Zeilen haben **keinen** #1847-Diagnosekonflikt (reiner Auth-Vorgang, keine
Test/Staging-Unterscheidung nötig) — hier genügt das bereits vorhandene `maskAddrForLog()`.
**Empfehlung: in dieser Spec mit adressieren** (3 Zeilen, kleiner Zusatzaufwand), nicht als
Sammel-Issue-Nebenbefund — lückenhafte Bestandsaufnahme desselben gemeldeten Problems.

### Migration von `briefing_log.json`-Bestandsdaten

`_append_briefing_log()` (`src/services/trip_report_scheduler.py:2049-2102`) hat **keine
Rotation/Obergrenze** — die Datei wächst unbegrenzt. Ohne Migration blieben bestehende
Klartext-`mail_to`-Werte alter Einträge dauerhaft auf Prod-Disk, für jeden Nutzer mit
Mail-Historie — das widerspricht dem in Schwere „Hoch (Datenschutz)" erklärten Ticketziel.
**Empfehlung:** einmaliges Migrationsscript (Dry-Run zuerst), Read-Modify-Write pro
`data/users/<user_id>/briefing_log.json`, ersetzt `mail_to` nach derselben Positivliste+
Domain-Regel wie oben (nicht per Hash, siehe Korrektur im Abschnitt „Zentraler Konflikt");
alle anderen Felder unverändert. `data_schema_backup.py` triggert hier NICHT
(`SCHEMA_PATHS` enthält weder `trip_report_scheduler.py` noch die Datendatei) — das Script
muss selbst ein `.bak` vor dem Schreiben anlegen. `internal/handler/data_export_test.go:515`
prüft nur Feld-VORHANDENSEIN in einer anderen Datei (`user.json`-Profilexport, eigenes
`mail_to`-Profilfeld) — von der Migration nicht betroffen.

**Messbarkeits-Klausel (Plan-Agent, PFLICHT für die Spec):** Staging-Datenbestand ist für
`hem` nicht lesbar, Prod liegt unter `/var/lib/gregor` — die Spec muss VOR der Umsetzung
festlegen, wie der Migrationserfolg nachgewiesen wird (z. B. Script gibt einen Zähler
„N Einträge maskiert/unverändert" aus; Verifikation auf Prod als Teil des Deploy-Schritts
durch einen Zähler-Vorher/Nachher-Abgleich statt durch Werteinsicht), sonst endet der
Nachweis bei `NOT_MEASURABLE_ON_STAGING`.

**Abgrenzung (Plan-Agent):** Die fehlende Rotation selbst (Datei wächst unbegrenzt) ist ein
separates Aufbewahrungs-/Retention-Problem und gehört **nicht** in diese Spec — eigenes
Ticket wert, sonst bläht es #2157 unnötig auf. #2157 bereinigt nur den INHALT (Klartext →
maskiert), nicht die Größe der Datei.

### Wächter-Test-Bauart

Empfehlung: **beide** Ebenen, nicht nur eine — (1) AST-Scan nach Vorbild
`tests/test_user_id_default_guard.py` gegen benannte Parameter (`mail_to`, `empfaenger`,
`chat_id`) in `logger.*`/`log.Printf`-Aufrufen als Struktur-Ratsche, **plus** (2) ein
Verhaltenstest (`caplog`), der eine echte, unbekannte Adresse durch den Sendepfad schickt
und die tatsächliche Domain-Maskierung im Log-Output nachweist. Reiner AST-Scan träfe nur
den exakten Parameternamen und entginge einem Alias (`addr = trip.mail_to; logger.info(addr)`);
reiner Verhaltenstest deckt nicht jede zukünftige neue Fundstelle ab. Guard-Scope: nicht nur
`src/` (wie im Ticket-Wortlaut), sondern zusätzlich `internal/handler/auth_magic.go` (der
einzige bestätigte Go-Fund). `api/` wurde durchsucht und ist frei von PII-Logging (valides
Negativergebnis) — eine Aufnahme in den Guard wäre günstige Zukunftsabsicherung, aber kein
bekannter Verstoß, den es zu schließen gilt.

**Mutations-Gegenprobe (Plan-Agent, PFLICHT-Bestandteil der Spec/Adversary-Prüfung):** die
Spec muss mindestens diese drei Verfälschungen benennen und je einen Test dagegen zeigen:
(1) Positivlisten-Check entfernen → Gegentest mit Fremdadresse wird rot; (2) alles maskieren
(auch Listeneinträge) → der bestehende `test_erfolgszeile_enthaelt_die_empfaengeradresse`
wird rot; (3) nichts maskieren → der neue Gegentest wird rot.

**Regel-Budget (CLAUDE.md-Pflicht):** Der neue Wächter-Test ist ein neues Gate — braucht
beim Einführen entweder ein Prüfdatum (+90 Tage) oder muss eine bestehende Regel ersetzen.
Muss in der Spec stehen, sonst fehlt ein Pflichtfeld.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/trip_report_scheduler.py:1682,2096` | MODIFY | Erfolgszeile + `_append_briefing_log()`: bekannte Ops-Mailbox unverändert, sonst Domain-Maskierung |
| `src/services/scheduler_dispatch_service.py:687` | MODIFY | Ortsvergleich-Erfolgszeile, dieselbe Regel |
| `src/services/notification_service.py:1999,2018,2041,2057,2072` | MODIFY | Telegram-Fehlerzeilen: `chat_id`/`callback_query_id` maskieren (Endziffern, Vorbild `seven_io_base.mask_number`) — fünf Stellen, nicht vier |
| `src/services/inbound_telegram_reader.py:594` | MODIFY | Registrierungs-Log: `chat_id` maskiert |
| `src/services/inbound_email_reader.py:195,299,303,306` | MODIFY | Absenderadresse maskiert (Domain-Regel) |
| `internal/handler/auth_magic.go:89,109,112` | MODIFY | E-Mail in Magic-Link-Logs via `maskAddrForLog()` — einziger Go-Fund, `auth.go`/`auth_oauth.go` loggen nur interne `userId`, kein Scope |
| `docs/specs/fast/fix-1847-briefing-empfaenger-log.md` | MODIFY | Status-Zeile „abgelöst durch #2157 (verengt auf bekannte Betriebsadressen)" |
| `tests/unit/test_briefing_recipient_logging.py` | MODIFY (ergänzen) | neuer Test: Fremdadresse wird maskiert; bestehender AC-1-Test bleibt grün |
| `tests/test_pii_log_guard.py` (neu) | CREATE | AST-Struktur-Ratsche, Scope `src/`+`internal/handler/auth_magic.go` |
| `scripts/migrate_briefing_log_mail_to_hash.py` (neu) | CREATE | einmalige Bestandsmigration, Dry-Run-Flag |

### Scope Assessment

- Dateien: ~11-13 (davon 2 neu)
- Geschätzte LoC: Kern-Fix (Python-Logging-Stellen + Tests) ~80-150; Go-Fund
  (`auth_magic.go`, 3 Zeilen + Test) ~15-25; Migrationsscript + Test ~70-100 → Summe
  vermutlich nahe oder leicht über dem 250-LoC-Workflow-Limit, `loc_limit_override`
  in der Implementierungsphase ggf. nötig (vorher `workflow.py status` prüfen).
- Risk Level: **MEDIUM** — kein neuer Datenvertrag, aber Eingriff in eine PO-freigegebene
  Spec (#1847); Fehlerquelle bei falscher Maskierung wäre erneuter Diagnoseverlust
  (Rückfall in die #1847-Falle), nicht Datenverlust.

### Technical Approach

Wiederverwendung bestehender Bausteine statt neuer Maskierungslogik: bekannte
Betriebs-/Test-Mailbox-Erkennung (Go: `isReservedTestDomain`/`rawContainsTestMailbox` aus
`internal/mail/sender.go`; Python-Pendant) entscheidet „unmaskiert loggen ja/nein"; für den
maskierten Fall greifen die bereits vorhandenen `_mask_addr_for_log()`/`maskAddrForLog()`.
Telefonnummern/`chat_id` nutzen die bestehende Endziffern-Maskierung
(`seven_io_base.mask_number`-Muster). `briefing_log.json.mail_to` wird durch denselben Hash
ersetzt, den auch die Migration für Bestandsdaten nutzt. Scope umfasst zusätzlich den einen
bestätigten Go-Fund (`auth_magic.go:89,109,112`), da er dieselbe Ticket-Zusicherung („kein
Klartext in journald aller drei Services") berührt; `auth.go`/`auth_oauth.go` sind nach
Gegenprobe kein PII-Fund (loggen nur die interne `userId`) und bleiben außen vor.

### Dependencies

- Upstream: keine neuen Provider-/API-Verträge.
- Downstream: `internal/store/log.go` ignoriert `mail_to` bereits (kein Bruch);
  `data_export_test.go:515` prüft nur Feldnamen, nicht Wert (kein Bruch); menschliche
  Diagnose auf Staging/Prod bleibt funktionsfähig, weil bekannte Betriebsadressen unmaskiert
  bleiben.

### Open Questions

- Keine PO-Entscheidung außerhalb der regulären Spec-Freigabe nötig — die #1847-Verengung
  ist eine technische Auflösung (Tech-Lead-Entscheidung), keine neue Grundsatzfrage; die
  Spec markiert #1847 explizit als „abgelöst durch #2157", damit nichts still rückgängig
  gemacht wird.
