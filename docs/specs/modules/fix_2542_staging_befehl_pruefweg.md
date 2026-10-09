---
entity_id: fix_2542_staging_befehl_pruefweg
type: module
created: 2026-10-09
updated: 2026-10-09
status: draft
version: "1.0"
tags: [tooling, staging, befehle, email, e2e-verify, tests]
---

# Staging-Prüfweg für Befehle über den echten E-Mail-Eingang (#2542)

## Approval

- [ ] Approved

## Purpose

Auf Staging lässt sich bisher nicht prüfen, was das System auf `status`, `heute` und die Verschiebe-Befehle (Ruhetag, Startdatum) tatsächlich antwortet: Die Testmails zu #2441 kamen über die angemeldete Einlieferung (Port 587), die strukturell nie den Absender-Echtheitsvermerk (`Authentication-Results`) trägt, und wurden vom Eingang zu Recht verworfen (#2143). Diese Spec liefert ein Prüfwerkzeug, das Befehle über den **echten, anonymen Zustellweg** (Port 25, SPF und DMARC bestehen legitim, weil der eigene Server für `henemm.com` sendeberechtigt ist) an den laufenden Staging-Eingang schickt und die Antwortmail auswertet. Es ändert **keinen Produktcode** und umgeht die Absenderprüfung nicht. Damit wird #2441 auf Staging neu verifiziert und ausgeliefert; erst dann ist #2542 erledigt.

## Source

- **Files:**
  - `.claude/tools/staging_befehl_pruefen.py` (neu, Kommandozeilenwerkzeug)
  - `tests/tdd/test_staging_befehl_pruefweg.py` (neu, deterministische Kern-Tests)
  - `.claude/commands/e2e-verify.md` (Rezept)
- **Identifier:** `main()` im Werkzeug; reine Funktionen `baue_tag`, `baue_plus_adresse`, `pruefe_empfaenger`, `baue_befehlsmail`, `baue_etappen`, `finde_antwort`, `werte_aus`.

> Schicht-Hinweis: Reines Werkzeug und Test-Schicht (`.claude/`, `tests/`, Doku). `src/`, `api/`, `internal/`, `frontend/` bleiben unverändert. Die Prüfung `_spf_dkim_pass` in `src/services/inbound_email_reader.py` bleibt unangetastet, es gibt keinen Test-Eingang, der sie umgeht.

## Estimated Scope

- **LoC:** Werkzeug ca. +240, Kern-Tests ca. +120, Doku (`e2e-verify.md`) ca. +50. Gesamt ca. +360. Ob `.claude/tools/*.py` zum Limit von 250 zählt, ist nicht sicher; vor `/50` mit `workflow.py status` gegenlesen und bei Bedarf `workflow.py set-field loc_limit_override 500` setzen (`*.md` zählt nicht).
- **Files:** 3 (2 CREATE, 1 MODIFY)
  - CREATE `.claude/tools/staging_befehl_pruefen.py` — Prüfwerkzeug (ca. +240)
  - CREATE `tests/tdd/test_staging_befehl_pruefweg.py` — Kern- und live/staging-Tests (ca. +120)
  - MODIFY `.claude/commands/e2e-verify.md` — Rezept „Befehl per echtem Mail-Eingang auf Staging“ (ca. +50)
- **Effort:** medium (operativ mittleres Risiko wegen echter Einlieferung in geteilte Postfächer, für Produktion kein Risiko)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Stalwart Port 25 an `mail.henemm.com` (178.104.143.19) | Upstream | setzt bei anonymer Einlieferung den echten `Authentication-Results`-Header (gemessen 2026-10-08: spf, iprev, dmarc = pass) |
| DNS-SPF/DMARC von `henemm.com` | Upstream | `a:mail.henemm.com` macht den eigenen Server legitim sendeberechtigt |
| `InboundEmailReader._authorize` / `_spf_dkim_pass` | Upstream | bleibt unverändert; Absender muss exakt der `mail_to` des Nutzers sein |
| Staging-Go-API: `/api/auth/register`, `/api/auth/login`, `/api/trips`, `/api/auth/verify-email/staging-token`, `/api/auth/verify-email`, `POST /api/auth/account/delete` | Upstream | Wegwerf-Nutzer und Trip anlegen, verifizieren, aufräumen |
| Staging-Kern Port 8001 `POST /api/scheduler/inbound-commands` + `X-GZ-Core-Auth` | Upstream | stößt den Poll sofort an (Go-Weg ist nur für Admins; Staging hat keinen Admin) |
| `/home/hem/gregor_zwanzig_staging/.env` | Upstream | Staging-Adresse, Core-Secret und Zugangsdaten (nie im Klartext ausgeben) |
| Test-Postfach `gregor-test@henemm.com` (IMAP, `GZ_TEST_IMAP_*`) | Upstream | Antwortmails des Nutzers kommen dort an (Plus-Adresse landet im Basispostfach) |
| `trip_command_processor.py` (`_show_status`, `_apply_ruhetag`, `_shift_start`, `numbered_stage_label`) | Upstream (nur lesen) | Antwortformate, gegen die ausgewertet wird |
| `fix_2441_etappennummer_status.md` | Downstream | liefert die zu prüfenden ACs 1, 2, 3, 4, 9 |
| `/e2e-verify`, `/70-deploy #2441` | Downstream | nutzen das Werkzeug; Abschlussbedingung dieser Spec |
| `tests/tdd/test_befehle_email_live.py`, `tests/tdd/test_issue_1009_1019_inbound_robustness.py` (`_deliver_mail_anonymous`) | Vorbild | Port-25-Einlieferung und IMAP-Muster (siehe „Wiederverwendung") |

## Wiederverwendung statt Duplikat

Die geprüften Altfunktionen sind nicht 1:1 nutzbar: `_deliver_mail_anonymous` (#1009) und `_deliver_apple_html_mail_anonymous` (#2417) tragen das Test-Postfach als festen Empfänger und die Test-Umgebung (`GZ_TEST_*`) fest verdrahtet; die IMAP-Helfer (`_find_reply_by_subject`, `_hoechste_uid`) suchen nach Betreff statt nach Empfänger-Header. Das Werkzeug braucht Empfänger `gregor-staging@`, Absender gleich Plus-Adresse und Suche über den `To:`-Header. Deshalb entsteht **eine** neue, parametrisierte Einlieferungs- und Suchfunktion im Werkzeug (Quelle der Wahrheit für Staging-Prüfungen), die das Muster der Altfunktionen übernimmt, ohne sie zu ändern. Ein Heben der Altkopien in ein gemeinsames Modul wäre ein Umbau fremder, gate-geschützter Tests und ist ausdrücklich Out of Scope (Sammel-Eintrag #1199).

## Implementation Details

Ablauf eines Laufs (ein Aufruf, `--szenario status|heute|verschiebung|alle`):

```
1. tag          = baue_tag()                       # eindeutig je Lauf (Zeit + Zufall)
2. plus_adresse = gregor-test+<tag>@henemm.com     # pruefe_empfaenger(): nur @henemm.com
3. Wegwerf-Nutzer registrieren (mail_to = plus_adresse, id Pflicht), anmelden
4. staging-token holen -> POST /api/auth/verify-email   (email_verified_at echt gesetzt)
5. Trips mit gezielt gebauten Etappen anlegen (baue_etappen, Namen enthalten <tag>)
6. Befehlsmail per Port 25 einliefern:
     Envelope-MAIL-FROM = Header-From = plus_adresse
     To = gregor-staging@henemm.com (Staging-Eingang, Empfaenger im Umschlag ebenso)
     Betreff "[<Trip-Name>] <wort>", Befehl in der ersten Textzeile
7. Poll ausloesen (Kern 8001 + X-GZ-Core-Auth); schlaegt das fehl: Cron */5 abwarten
8. Antwort per IMAP aus gregor-test lesen: Header-To == plus_adresse, UID neu seit Start,
   Abruf nur mit BODY.PEEK (nie flaechig Seen setzen)
9. werte_aus(): Antworttext gegen Erwartung aus der Trip-Position pruefen
10. finally: Trips und Nutzer loeschen (account/delete); gelingt das nicht, Befund mit
    Nutzer-Kennung ausgeben (nie still)
```

**Erfolgssignal** ist die Antwortmail innerhalb des Zeitlimits (Standard 360 s, deckt einen Cron-Takt ab), **nicht** der Zähler des Poll-Aufrufs: Hat der Cron die Mail schon verarbeitet, meldet der Trigger `count=0`, obwohl alles funktioniert. `count` wird nur als Diagnose ausgegeben. Bleibt die Antwort aus, ist der Exit-Code ungleich 0 (verworfene Mails werden vom Eingang still als gelesen markiert, „leer" darf nie als Erfolg gelten).

**Warum die Plus-Adresse:** Pro Nutzer gilt auf Staging `for_testing()` (`mail_from` und Inbound-Adresse = `gregor-test@henemm.com`); `_authorize` verwirft Mails, deren Absender gleich dem System-Absender ist. Die Absenderzuordnung vergleicht exakt (kein Plus-Entfernen) und liefert bei zwei Nutzern mit gleicher Adresse nichts. Deshalb: eindeutiger Tag je Lauf, `From` exakt gleich `mail_to`.

**Szenarien für #2441** (jedes ein eigener Trip, damit sich die Läufe nicht gegenseitig verändern):

| Szenario | Trip-Aufbau | Befehle (je eine Mail) | Prüft |
|---|---|---|---|
| A (AC-1) | 5 Etappen, die vierte heißt „02: Obstansersee-Hütte nach Porzehütte" und hat als Datum den Ortstag von heute (Etappen 1 bis 3 liegen davor) | `status`, dann `heute` | beide nennen für diese Etappe die Zahl 4 („Etappe 4: …" bzw. „E4") |
| B (AC-2, AC-3) | Etappennamen „02: X", „02 – X", „2 Seen Runde", „1.5 km Runde", „1. Pass", „2. X", „03:" ; alle Daten heute oder später | `status` | je Zeile „Etappe N: Rest" bzw. bei „03:" nur „Etappe N"; Zahl aus dem Namen erscheint nicht zusätzlich |
| C (AC-9) | 4 Etappen mit Namenszahlen, die nicht zur Reihenfolge passen, in vertauschter Listenreihenfolge angelegt | `status` | Nummern entsprechen der Reihenfolge nach Datum |
| D (AC-4) | wie B, Startdatum liegt in der Zukunft | `### ruhetag: 1` und danach (anderer Trip D2 mit gleichem Aufbau) `### startdatum: <neues Datum>` | beide Bestätigungen nennen je Etappe „Etappe N: Rest" mit derselben Nummer wie `status` |

**Format der Verschiebe-Antworten (aus `trip_command_processor.py` abgelesen, kein PO-Thema):** Es gibt **keinen** Dialog in zwei Schritten (Vorschau, dann Bestätigung). „Vorschau und Bestätigung" in #2441 AC-4 meint die zwei vorhandenen Ausgaben der zwei Befehle: Ruhetag (Betreff „[<Trip>] Ruhetag bestaetigt", Zeilen `  <Etappenbezeichnung>: TT.MM.JJJJ -> TT.MM.JJJJ`, `_apply_ruhetag` Z. 2448-2451) und Startdatum (Betreff „[<Trip>] Startdatum geaendert", Zeile „Startdatum verschoben: … -> …", dann „Neue Etappen-Daten:" mit `  <Etappenbezeichnung>: TT.MM.JJJJ`, `_shift_start` Z. 2530-2533). Beide Befehle wirken sofort und einmalig; das Werkzeug sendet deshalb je Befehl **eine** Mail an einen eigenen Trip und wertet **eine** Antwort aus. Der in der Analyse vermutete zweite Schritt entfällt. Ruhetag ist je Trip und Tag nur einmal erlaubt (Idempotenz-Sperre), daher die getrennten Trips D und D2.

**Datierung:** „Heute" ist der Ortstag des Trips (ADR-0044), nicht der Tag des Servers. Das Werkzeug berechnet das Datum aus der Zeitzone der Etappen-Koordinaten (Alpenraum, `Europe/Vienna`) und bricht mit klarer Meldung ab, wenn der Lauf in das Zeitfenster um Mitternacht Ortszeit fällt, in dem die Zuordnung der Etappe zu „heute" nicht eindeutig wäre.

**Sicherheits-Leitplanken (im Code, nicht nur in der Doku):** (1) `pruefe_empfaenger()` lässt für die Port-25-Einlieferung ausschließlich Adressen auf `@henemm.com` zu, alles andere bricht vor dem Verbindungsaufbau mit Exit 2 ab (kein Relay-Versuch gegen fremde Server). (2) Der IMAP-Abruf zeigt nur Mails, deren `To:`-Header genau die Plus-Adresse dieses Laufs ist, und liest per `BODY.PEEK`. (3) Ausgaben enthalten weder Passwörter noch Token noch das Core-Secret; Zugangsdaten werden nur aus der Staging-`.env` bzw. Umgebung gelesen. (4) Das Werkzeug fasst keine Daten bestehender Nutzer an und sendet nie an Produktiv-Empfänger.

## Expected Behavior

- **Input:** Aufruf `python3 .claude/tools/staging_befehl_pruefen.py --szenario <name|alle>` (optional `--timeout`, `--ohne-cleanup` nur zur Fehlersuche).
- **Output:** je Szenario eine Zeile `PASS`/`FAIL` mit der gefundenen und der erwarteten Etappenzeile (Etappennamen sind Testdaten, keine Geheimnisse); Gesamt-Exit 0 nur wenn alle gewählten Szenarien bestehen. Exit 1 = Antwort ausgeblieben oder Inhalt falsch, Exit 2 = Aufruf-/Umgebungsfehler (z. B. Relay-Sperre, fehlende Zugangsdaten, Registrierung abgelehnt).
- **Side effects:** legt auf Staging einen Wegwerf-Nutzer samt Trips an, liefert Mails an `gregor-staging@henemm.com` ein, erzeugt Antwortmails im Test-Postfach (werden per `BODY.PEEK` gelesen und danach, nur die eigenen, gelöscht), räumt alles im `finally` weg.

## Acceptance Criteria

- **AC-1:** Given ein frischer Wegwerf-Nutzer auf Staging, dessen Mail-Adresse eine eindeutige Plus-Adresse von `gregor-test@henemm.com` ist / When das Werkzeug einen Befehl wie `status` über Port 25 an den Staging-Eingang schickt, mit Absender gleich dieser Plus-Adresse / Then kommt innerhalb des Zeitlimits eine Antwortmail an diese Plus-Adresse im Test-Postfach an, ohne dass die Absenderprüfung des Systems verändert oder umgangen wurde.
  - Test: live/staging-Marker, `test_staging_befehl_pruefweg.py::test_gesamtlauf_status_auf_staging` (nur in `/e2e-verify`, wird ohne Zugangsdaten übersprungen); zusätzlich Kernprüfung, dass `src/services/inbound_email_reader.py` im Diff unverändert ist (Review-Punkt des Adversary).

- **AC-2:** Given Tag, Staging-Eingang und Nutzer-Adresse / When das Werkzeug Adresse und Mail zusammenbaut / Then ist die Plus-Adresse `gregor-test+<tag>@henemm.com`, `From` und Umschlag-Absender sind exakt dieselbe Adresse, `To` ist `gregor-staging@henemm.com`, der Betreff lautet `[<Trip-Name>] <Befehl>`, und zwei Läufe erzeugen nie denselben Tag.
  - Test: Kern, `test_adressen_und_header_werden_exakt_gebaut`, `test_tags_sind_je_lauf_eindeutig` (reine Funktionen, ohne Netz).

- **AC-3:** Given eine Empfängeradresse, die nicht auf `@henemm.com` endet (auch getarnte Formen wie `x@henemm.com.evil.de` oder `henemm.com@evil.de`) / When das Werkzeug sie als Empfänger für die Port-25-Einlieferung prüft / Then wird sie vor jedem Verbindungsaufbau abgelehnt (Exit 2), und nur genau `@henemm.com`-Adressen werden akzeptiert.
  - Test: Kern, `test_relay_sperre_lehnt_fremde_domains_ab` (parametrisiert über erlaubte und verbotene Adressen).

- **AC-4:** Given eine Antwort bleibt aus (nach dem Zeitlimit ist keine passende Mail im Postfach) / When das Werkzeug auswertet / Then ist der Exit-Code ungleich 0 und die Meldung nennt, dass die Mail vermutlich verworfen wurde; ist die Antwort dagegen da, gilt der Lauf als erfolgreich, auch wenn der Poll-Aufruf selbst `count=0` meldete (weil der Cron schneller war).
  - Test: Kern, `test_ausbleibende_antwort_ist_exit_ungleich_null` und `test_antwort_da_trotz_count_null_ist_erfolg` (konstruierte Mail-Bytes, Zähler nur Diagnose).

- **AC-5:** Given das geteilte Test-Postfach enthält fremde Mails, Mails anderer Läufe und die richtige Antwort / When das Werkzeug die Antwort sucht / Then findet es genau die Mail, deren `To:`-Header die Plus-Adresse dieses Laufs ist und die neu seit Laufbeginn ist, ignoriert alle anderen und setzt bei fremden Mails keine Gelesen-Markierung.
  - Test: Kern, `test_antwortsuche_nimmt_nur_die_eigene_mail`, `test_antwortsuche_markiert_fremde_mails_nicht` (Sammlung aus konstruierten Mails; Abruf erfolgt über `BODY.PEEK`, geprüft am aufgezeichneten Abrufbefehl eines Test-IMAP-Servers ohne Netz).

- **AC-6:** Given die Szenarien A bis D / When das Werkzeug die Trips baut / Then liegt in Szenario A die Etappe „02: Obstansersee-Hütte nach Porzehütte" an Position 4 und hat den Ortstag von heute als Datum, Szenario B enthält alle sieben genannten Namen („02: X", „02 – X", „2 Seen Runde", „1.5 km Runde", „1. Pass", „2. X", „03:"), Szenario C stellt die Etappen in vertauschter Listenreihenfolge ein, und alle Trip-Namen enthalten den Lauf-Tag.
  - Test: Kern, `test_szenarien_bauen_die_vorgesehenen_etappen` (prüft Name, Position, Datum der gebauten Etappen).

- **AC-7:** Given konstruierte Antwortmails im Format des Systems (`status`-Liste, `heute`-Antwort mit `E4`) / When das Werkzeug sie auswertet / Then erkennt es richtig, wenn `status` und `heute` dieselbe Zahl nennen, wenn „02: X" zu „Etappe N: X" wird (und die „02" nicht zusätzlich dasteht), wenn „03:" zu „Etappe N" ohne Doppelpunkt wird, und wenn die Nummern bei vertauschter Reihenfolge der Datumsfolge entsprechen; falsche Antworten (z. B. „Etappe 4: 02: X" oder abweichende Zahl) werden als Fehler gemeldet.
  - Test: Kern, `test_auswertung_status_heute_zahl`, `test_auswertung_praefix_und_randfaelle`, `test_auswertung_chronologische_zaehlung`, jeweils mit Positiv- und Negativfall; die erwartete Zahl wird aus Position bzw. Datum der gebauten Etappen berechnet, nicht als Zahl in den Testaufbau geschrieben.

- **AC-8:** Given die Antwortmails von Ruhetag (Betreff „… Ruhetag bestaetigt") und Startdatum (Betreff „… Startdatum geaendert") im abgelesenen Format / When das Werkzeug sie auswertet / Then prüft es, dass jede Etappenzeile die Form „Etappe N: Rest" mit derselben Nummer wie `status` hat und der Datumsteil unverändert erwartungsgemäß verschoben ist; bei abweichender Nummer oder fehlendem Datum meldet es einen Fehler.
  - Test: Kern, `test_auswertung_ruhetag_bestaetigung`, `test_auswertung_startdatum_bestaetigung` (Positiv- und Negativfall); live/staging-Marker als Teil des Gesamtlaufs mit Szenario D.

- **AC-9:** Given ein Lauf endet erfolgreich, mit Fehler oder durch Abbruch mittendrin / When das Werkzeug beendet wird / Then wurden Wegwerf-Nutzer und Trips gelöscht (oder, falls das scheitert, die Kennung des übrig gebliebenen Nutzers ausdrücklich ausgegeben), und in keiner Ausgabe stehen Passwörter, Token oder das Core-Secret.
  - Test: Kern, `test_cleanup_laeuft_auch_bei_fehler` (Aufräumschritt wird bei ausgelöster Ausnahme ausgeführt, geprüft an der Reihenfolge der Schritte einer Ersatz-Staging-Schnittstelle am Netzrand) und `test_ausgaben_enthalten_keine_geheimnisse` (Ausgabe eines Laufs mit Platzhalter-Secrets wird nach diesen Werten durchsucht).

- **AC-10:** Given ein Mitarbeiter führt `/e2e-verify` für einen Befehls-Fix aus / When er das Rezept „Befehl per echtem Mail-Eingang auf Staging" in `.claude/commands/e2e-verify.md` liest / Then findet er Aufruf, Szenario-Auswahl, Exit-Code-Bedeutung, Hinweis „Erfolg = Antwortmail, nicht count" und den Hinweis, dass SMS, Premium-SMS und Telegram (#2441 AC-6, AC-7) nicht über dieses Werkzeug, sondern über Kern-Tests mit echtem Eingang, Staging-Vorschau und Handy-Nachtest nach dem Prod-Deploy geprüft werden.
  - Test: `# doc-compliance-test` in `test_staging_befehl_pruefweg.py::test_rezept_in_e2e_verify_vorhanden` (Pflicht-Stichworte im Rezept; ausdrücklich keine Verhaltensprüfung).

- **AC-11:** Given #2441 mit den offenen ACs 1, 2, 3, 4, 9 / When das Werkzeug alle vier Szenarien gegen Staging fährt, nachdem der Stand von #2441 dort ausgeliefert ist / Then endet es mit Exit 0, und #2441 wird danach per `/70-deploy #2441` nach Produktion gebracht, der Post-Deploy-Selftest endet mit Exit 0 (Voraussetzung für das Schließen von #2441 und #2542).
  - Test: live/staging-Marker, `test_staging_befehl_pruefweg.py::test_gesamtlauf_alle_szenarien_auf_staging`; Nachweis im Staging-Verdict von `/e2e-verify` und `prod_selftest.py` Exit 0.

## Test Plan

Alle Tests in `tests/tdd/test_staging_befehl_pruefweg.py`; der Prüfling wird relativ zur Testdatei aufgelöst.

**Kern (deterministisch, ohne Netz, Commit-Gate):**
- `test_adressen_und_header_werden_exakt_gebaut`, `test_tags_sind_je_lauf_eindeutig` → AC-2
- `test_relay_sperre_lehnt_fremde_domains_ab` → AC-3
- `test_ausbleibende_antwort_ist_exit_ungleich_null`, `test_antwort_da_trotz_count_null_ist_erfolg` → AC-4
- `test_antwortsuche_nimmt_nur_die_eigene_mail`, `test_antwortsuche_markiert_fremde_mails_nicht` → AC-5
- `test_szenarien_bauen_die_vorgesehenen_etappen` → AC-6
- `test_auswertung_status_heute_zahl`, `test_auswertung_praefix_und_randfaelle`, `test_auswertung_chronologische_zaehlung` → AC-7
- `test_auswertung_ruhetag_bestaetigung`, `test_auswertung_startdatum_bestaetigung` → AC-8
- `test_cleanup_laeuft_auch_bei_fehler`, `test_ausgaben_enthalten_keine_geheimnisse` → AC-9
- `test_rezept_in_e2e_verify_vorhanden` (`# doc-compliance-test`) → AC-10

**Live/Staging (Marker `live` + `staging`, nur in `/e2e-verify`, ohne Zugangsdaten übersprungen):**
- `test_gesamtlauf_status_auf_staging` → AC-1
- `test_gesamtlauf_alle_szenarien_auf_staging` → AC-8 (live-Teil), AC-11

**Review-Punkte (Adversary):** `src/services/inbound_email_reader.py` und die übrigen Produktdateien sind im Diff unverändert (AC-1); Mutations-Gegenprobe an Relay-Sperre, To-Filter und Exit-Code-Ableitung.

## Out of Scope

- **Kein Prüfweg für SMS, Premium-SMS und Telegram (#2441 AC-6, AC-7).** PO-Entscheid 2026-10-08 („Wie bei #2417"): Diese Kanäle werden über Kern-Tests mit echtem Eingang, die Staging-Vorschau und einen Handy-Nachtest nach dem Prod-Deploy abgedeckt. Begründung: Der Premium-SMS-Befehlsweg ist auf Staging durch die Herkunftssperre bewusst abgeschaltet, und Telegram-Antworten landen im Chat des Bots und sind nicht abgreifbar. Ein eigener Prüfweg dafür wäre ein Vielfaches des Umfangs ohne Mehrwert gegenüber dem bewährten Verfahren.
- Änderungen an Produktcode, an der Absender-/SPF-Prüfung (#2143) oder ein „gesicherter Test-Eingang".
- Heben der vorhandenen Einlieferungs-/IMAP-Helfer aus `test_befehle_email_live.py` und `test_issue_1009_1019_inbound_robustness.py` in ein gemeinsames Modul (Sammel-Eintrag #1199).
- Dauerhafter Cron-Lauf des Werkzeugs; es läuft nur im Rahmen von `/e2e-verify`.

## Known Limitations

- Der Lauf braucht Zeit, weil Staging nur per Cron (alle 5 Minuten) oder über den direkten Kern-Trigger pollt; ohne Kern-Secret wird bis zu 6 Minuten gewartet.
- Registrierung ist ohne Einladung offen (`internal/handler/auth.go`: `invite` optional), aber auf **5 Versuche pro IP und Stunde** begrenzt (`internal/router/router.go:60`, #117). Das Werkzeug legt deshalb **einen** Wegwerf-Nutzer pro Lauf an und alle Szenario-Trips unter diesem Nutzer; 429 oder eine andere Ablehnung ⇒ Exit 2 mit klarer Meldung, kein Wiederholungsversuch.
- Das geteilte Postfach `gregor-test` bleibt geteilt; parallele Läufe sind durch Tag und `To:`-Filter getrennt, aber die Löschung der eigenen Antworten betrifft nur Mails mit der eigenen Plus-Adresse.
- Das Werkzeug kann Antwortinhalt nur prüfen, nicht die Zustellqualität des Mail-Programms beim Nutzer.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reines Prüfwerkzeug in der bestehenden Test-/Deploy-Strategie (Staging-Verifikation vor Prod, ADR-Index unverändert). Es wird weder ein Kanal noch ein Provider, das Datenmodell, die Authentifizierung noch das Editor-Paradigma geändert, und die Absenderprüfung aus #2143 bleibt wie beschlossen bestehen.

## Changelog

- 2026-10-09: Initial spec created (Issue #2542). Korrektur gegenüber der Analyse: Der Verschiebe-Befehl hat keinen Zwei-Schritt-Dialog; „Vorschau und Bestätigung" sind die zwei Ausgaben von Ruhetag und Startdatum, je eine Mail genügt.
