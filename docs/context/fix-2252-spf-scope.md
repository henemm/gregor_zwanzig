# Context: fix-2252-spf-scope

## Request Summary
Issue #2252 (F006, Folge von #2143): `parse_authentication_results()` legt alle
`method=result`-Paare in ein flaches Dict. Liefert Stalwart zwei `spf=`-Segmente
(Scope `smtp.helo` und Scope `smtp.mailfrom`), gewinnt das zuletzt genannte. Für die
Absenderprüfung von Trip-Befehlen per Mail zählt aber allein das MAILFROM-Ergebnis.
Die Reihenfolge ist durch RFC 8601 nicht festgelegt; heute stimmt das Ergebnis nur zufällig.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/inbound_email_reader.py:42-62` | `parse_authentication_results()`: flaches Dict, die letzte Zuweisung je Methode gewinnt |
| `src/services/inbound_email_reader.py:367-383` | `_spf_dkim_pass()`: einziger Aufrufer; verlangt `spf == pass` UND (`dkim == pass` ODER `dmarc == pass`) |
| `tests/fixtures/authentication_results_fixtures.py` | Versionierte Header-Fixtures; alle haben je EIN `spf=`-Segment mit `smtp.mailfrom` UND `smtp.helo` als Parameter im selben Segment. Eine Fixture mit zwei Scopes fehlt |
| `tests/tdd/test_authentication_results_parsing.py` | Parser- und `_spf_dkim_pass`-Tests (#2143, AC-5) |
| `tests/tdd/test_inbound_email_sender_authentication.py` | Integrationstests für die Absender-Autorisierung (AC-1..AC-6) |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py:461ff` | Live-E2E-Test gegen die echte anonyme Stalwart-Pipeline (hat F006 aufgedeckt) |
| `docs/specs/modules/inbound_command_channels.md` §5 (ab Z. 297), AC-1..AC-6 (Z. 591ff) | Spec der Transport-Authentifizierung |

## Echter Header (aus dem Issue, Stalwart, anonyme Zustellung)
```
mail.henemm.com;
    spf=temperror (...) smtp.helo=[127.0.1.1];
    spf=pass (... designates 178.104.143.19 as permitted sender) smtp.mailfrom=tdd-...@henemm.com;
    iprev=pass ...;
    dmarc=pass header.from=henemm.com policy.dmarc=quarantine
```
Hinweis: Hier steht ein Kommentar in Klammern zwischen Ergebnis und Parametern (`spf=pass (… ) smtp.mailfrom=…`).
Der Kommentar kann `;` enthalten? Laut RFC 8601 sind Kommentare (CFWS) überall erlaubt, und `;` in einem Kommentar
würde das heutige `split(";")` zerbrechen. Das ist in der Analyse zu prüfen.

## Existing Patterns
- Fail-closed: fehlender Header, fremde `authserv-id` oder ein Ergebnis ≠ `pass` ⇒ Ablehnung, SEEN, kein Reply, WARNING-Log.
- Nur der ERSTE `Authentication-Results`-Header zählt (`msg.get`, nie `get_all`, AC-5).
- Die Tests nutzen echte Header-Strings als Fixtures, kein Mock.

## Dependencies
- Upstream: nur die stdlib (`email`). Settings `mail_server_hostname` = erwartete authserv-id.
- Downstream: `_spf_dkim_pass()` ist der einzige Produktiv-Aufrufer des Parsers. Die Tests importieren den Parser direkt
  und prüfen `results.get("spf")` usw.; dieser Vertrag (`dict[str, str]`) sollte für `dkim`/`dmarc` stabil bleiben.

## Existing Specs
- `docs/specs/modules/inbound_command_channels.md` v1.5 — §5 Transport-Authentifizierung, AC-5.

## Risks & Considerations
- **Sicherheitsrichtung:** Ein `spf=pass` aus dem HELO-Scope darf ein fehlgeschlagenes MAILFROM-Ergebnis nicht
  verdecken. Gewollt ist: SPF zählt nur mit `smtp.mailfrom`-Scope. Was gilt bei einem `spf=`-Segment ganz ohne Scope-Parameter? → Analyse
  (Abwägung: fail-closed vs. Kompatibilität mit den bestehenden Fixtures, die beide Parameter in einem Segment tragen).
- **Gleiches Muster bei DKIM:** Bei mehreren Signaturen gibt es mehrere `dkim=`-Segmente, und auch hier gewinnt das letzte. Semantik
  „irgendeine Signatur pass“ oder „letzte“? Das ist in der Analyse zu entscheiden; mindestens dokumentieren.
- Mehrere `spf=mailfrom`-Segmente mit widersprüchlichem Ergebnis ⇒ fail-closed.
- Blast Radius: Ein zu strenger Parser sperrt legitime Befehle per Mail für alle Nutzer. Deshalb gehört der Live-E2E-Test
  (`test_live_authorized_sender_over_real_anonymous_pipeline_is_processed`) als Regressionsnachweis in `/e2e-verify`.

## Analysis

### Type
Bug, **Security, HIGH, heute ausnutzbar** (Einstufung im Issue korrigiert, 2.11.2026). Das Repo ist **öffentlich**: Die Angriffswege
stehen nur hier und in den Test-Fixtures, die erst mit dem Fix-PR öffentlich werden. Ins Issue kommen sie nicht.

### Empirische Belege (2.11.2026, Prod-Stalwart, anonym über Port 25 an das Test-Postfach, Probe-Mails danach gelöscht)
Skript: Scratchpad `probe_ar.py` / `probe_ar2.py` (nutzt die Helfer aus `test_issue_1009_1019_inbound_robustness.py`).
Die Header sind wörtlich (Python-repr) übernommen und **als Fixtures vorgesehen**.

**H1 normal** (Envelope `probe2252-…@henemm.com`, unsigniert ⇒ kein `dkim`-Segment):
```
'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=pass (mail.henemm.com: domain of probe2252-b5877b3d@henemm.com designates 178.104.143.19 as permitted sender) smtp.mailfrom=probe2252-b5877b3d@henemm.com;\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=pass header.from=henemm.com policy.dmarc=quarantine'
```
**H2 Injection** über einen quoted Local-Part im `MAIL FROM` (`"x;dkim=pass;spf=pass smtp.mailfrom=a"@spoofer-domain.invalid`):
```
'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=none (mail.henemm.com: no SPF records found for xdkimpassspfpasssmtp.mailfroma@spoofer-domain.invalid) smtp.mailfrom="x;dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid";\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=fail (policy not aligned) header.from=henemm.com policy.dmarc=quarantine'
```
Heute geparst: `{'spf': 'pass', 'dkim': 'pass', 'iprev': 'pass', 'dmarc': 'fail'}` ⇒ `_spf_dkim_pass(...) == True` (verifiziert).
**Folge:** Wer die `mail_to` eines verifizierten Nutzers kennt, setzt `From:` auf diese Adresse und kann zustandsändernde
Trip-Befehle auslösen (`stop`, `pause`, `skip`, `startdatum`, `strecke` …).

**H3 escaped quote** (`"x\";dkim=pass;spf=pass smtp.mailfrom=a"@spoofer-domain.invalid`):
```
'mail.henemm.com;\r\n\tspf=permerror (mail.henemm.com: unable to verify SPF record for postmaster@[127.0.1.1]) smtp.helo=[127.0.1.1];\r\n\tspf=none (mail.henemm.com: no SPF records found for xdkimpassspfpasssmtp.mailfroma@spoofer-domain.invalid) smtp.mailfrom="x\\";dkim=pass;spf=pass smtp.mailfrom=a@spoofer-domain.invalid";\r\n\tiprev=pass policy.iprev=178.104.143.19;\r\n\tdmarc=fail (policy not aligned) header.from=henemm.com policy.dmarc=quarantine'
```
Heute geparst ebenfalls `spf=pass, dkim=pass`.

Erkenntnisse zu Stalwart:
- Den Wert von `smtp.mailfrom` übernimmt Stalwart als quoted-string **roh mit Backslash-Escapes**, setzt aber selbst keine Escapes ein.
  Ein Parser, der quoted-strings mit `\`-Escapes nach RFC 8601/5322 korrekt behandelt, ordnet H2/H3 richtig zu.
- Kommentare in Klammern bereinigt Stalwart: Sonderzeichen werden entfernt (`xdkimpass…`). Ein `;` taucht dort nicht auf.
- EHLO-Namen mit `;`, `"` oder `(` lehnt Stalwart mit 550 ab. `smtp.helo` ist damit kein Injektionsweg (Probe 2).
- Reihenfolge heute: zuerst `spf` (helo), dann `spf` (mailfrom), dann `iprev`, dann `dmarc`. Bei signierter Mail kommt `dkim` dazu.

**Lücke 2, parser-unabhängig:** `_spf_dkim_pass` vergleicht keine Domain mit dem `From:`-Header. Synthetisch verifiziert:
`'mail.henemm.com; spf=pass smtp.mailfrom=a@attacker.example; dkim=pass header.d=attacker.example; dmarc=fail header.from=opfer.example'`
⇒ `True`. Ein Angreifer mit eigener Domain (SPF und eigene DKIM-Signatur) kommt mit `From: opfer@…` durch. Die Regel aus Spec §5
(„spf=pass UND (dkim=pass ODER dmarc=pass)“) reicht also selbst nicht aus. Die Fixtures nutzen durchgehend `henemm.com`, deshalb hat
das kein Test gesehen.

### Meldungen
- Issue #2252: Kommentar „HIGH, ausnutzbar, Details nicht öffentlich“ (ohne Angriffsweg).
- MQ-Alarm an `security` (id 102649), ohne Angriffsweg.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/inbound_email_reader.py` | MODIFY | RFC-8601-Tokenizer (Segmente mit Properties), Quote-Sperre, SPF nur aus `smtp.mailfrom`, Ausrichtungsregel; `_spf_dkim_pass(msg, authserv_id, from_domain)`; `_authorize` übergibt die Domain aus `sender`; Docstring „nur erster Token zählt“ entfällt |
| `tests/fixtures/authentication_results_fixtures.py` | MODIFY | H1–H3 wörtlich als Fixtures; Header mit fremder Domain (Lücke 2); Header mit zwei mailfrom-Segmenten, mit MAILFROM vor HELO, ohne Scope, mit unbalancierten Quotes/Klammern |
| `tests/tdd/test_authentication_results_parsing.py` | MODIFY | Tokenizer- und Regel-Tests; Z. ~118 (`spf=pass` ohne Scope) wird Reject |
| `tests/tdd/test_inbound_email_sender_authentication.py` | MODIFY | Integration über `_authorize`: H2/H3 und Lücke 2 werden abgelehnt, H1 geht durch; zwei Nutzer |
| `tests/tdd/test_issue_1009_1019_inbound_robustness.py` | MODIFY | Live-Negativtest „Injection über quoted Local-Part wird abgelehnt“ neben dem bestehenden Positiv-/Spoof-Test |
| `docs/specs/modules/inbound_command_channels.md` | MODIFY | §5 Regel 3 neu (Ausrichtung), fail-closed-Katalog, ACs |

### Scope Assessment
- Files: 6 (1 src, 4 Tests/Fixtures, 1 Spec)
- Estimated LoC: src +90/−20, Tests ca. +150
- Risk Level: **MEDIUM**. Die Änderung sitzt an der Sicherheitsgrenze. Ist sie zu streng, sperrt sie legitime Mail-Befehle aller Nutzer. Telegram, SMS und Premium-SMS bleiben unberührt (`_authorize` gehört nur zum Mail-Pfad).

### Technical Approach (Empfehlung Plan-Agent, übernommen)
1. **Tokenizer** als Zustandsautomat: `;` trennt nur auf oberster Ebene, also außerhalb von quoted-strings (mit `\`-Escape) und außerhalb verschachtelter Kommentare. Pro Segment gibt er `method`, `result` und die Properties `ptype.property=value` aus. Unbalancierte Quotes oder Klammern ⇒ `None` ⇒ fail-closed.
2. **Quote-Sperre (Defense in depth):** Jedes `"` im ersten `Authentication-Results`-Header ⇒ fail-closed. So kann ein Unterschied zwischen dem Escaping von Stalwart und dem Parser nie ein `pass` erzeugen. Legitime Absender haben praktisch nie einen quoted Local-Part.
3. **SPF-Scope:** SPF zählt nur aus Segmenten mit `smtp.mailfrom`, und es muss genau eines geben. Keines oder mehrere ⇒ fail. Reine `smtp.helo`-Segmente werden ignoriert, auch ihr `permerror`, der der Normalfall ist (H1). Ein `spf`-Segment ohne Scope zählt nicht. `dkim` zählt nur mit `header.d`, `dmarc` nur mit `header.from`.
4. **Ausrichtung (Variante V3 = DMARC-Logik):** Akzeptiert wird, wenn `dmarc=pass` und `header.from` zur From-Domain passt, ODER `spf=pass` (mailfrom) und die mailfrom-Domain passt, ODER `dkim=pass` und `header.d` passt. „Passt“ heißt: gleich der From-Domain oder deren Subdomain. Die Gegenrichtung (Org-Domain-Relaxation) ist nicht erlaubt, denn ohne Public-Suffix-Liste gilt fail-closed. Die From-Domain kommt aus dem bereits geparsten `sender`.
   - Verglichene Varianten: V1 = nur dmarc=pass, ausgerichtet; sperrt eigene Domains ohne DMARC-Record. V2 = spf ausgerichtet UND (dkim ausgerichtet ODER dmarc=pass); doppelt streng, sperrt Domains ohne DKIM. V3 folgt dem Standard und ist am wenigsten sperrend, ohne unsicher zu sein.
5. **Schnittstelle:** neue Funktion für die Segmentliste. `parse_authentication_results()` bleibt als dünner Wrapper (authserv-id und Dict). Für Methoden mit mehreren widersprüchlichen Segmenten darf er nie „das letzte gewinnt“ liefern. Einziger Aufrufer im Produktivcode ist `_spf_dkim_pass`.
6. **Reihenfolge:** ein Ticket, zwei Commits. A = Tokenizer, Quote-Sperre und SPF-Scope (schließt H2/H3). B = Ausrichtung (schließt Lücke 2). Lücke 2 gehört ins selbe Ticket, denn ohne sie bleibt der Bypass für jeden mit eigener Domain offen.

### Dependencies
- Nur die stdlib. In `pyproject.toml` gibt es keine Public-Suffix-Bibliothek, deshalb bewusst keine Org-Domain-Relaxation.
- `AR_PASS` und Co. werden in ca. 8 Testdateien geteilt. Fixture-Änderungen können eine Kaskade auslösen; in TDD-RED prüfen, welche From-Adressen die Tests verwenden.

### Notabschaltung bis zum Fix
Es gibt keinen Schalter für Mail-Befehle; der Go-Scheduler ruft `POST /api/scheduler/inbound-commands` auf. Vor #2143 gab es gar keine Prüfung, das Risiko ist also nicht neu. Entscheidung (Tech Lead): keine Notabschaltung, stattdessen den Fix mit Vorrang durchziehen.

### Open Questions (für /30-write-spec, technisch, kein PO-Entscheid)
- [ ] **Format des `dkim`-Segments bei signierter Fremdmail ist nicht empirisch belegt.** Alle Proben waren unsigniert, und eine signierte Mail über Port 25 ließ sich in dieser Sitzung nicht erzeugen (Stalwart-Submission verweigert fremde Absender). Für Gmail, GMX und web.de greift ohnehin der Pfad über `dmarc=pass` (deren Domains publizieren DMARC). Der `header.d`-Pfad betrifft nur Domains ohne DMARC. Vor TDD-RED einen echten signierten Header beschaffen, etwa aus einem Prod-Postfach per `sudo -n -u claude-gregor` oder einer Mail von außen. Andernfalls den `dkim`-Pfad nach RFC 8601 bauen und die Lücke in der Spec vermerken.
- [ ] Mehrere `From:`-Header: `msg.get("From")` nimmt den ersten. Prüfen, ob Stalwart doppelte From-Header ablehnt, sonst als fail-closed-Regel aufnehmen.
- [ ] Live-Regressionsnachweis in `/e2e-verify`: Der Positivtest (H1) muss grün bleiben. Ein neuer Negativtest mit dem Injection-Envelope (H2) muss abgelehnt werden.
