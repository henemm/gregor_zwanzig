# Context: fix-1412-s2-regelwerk-paritaet

Issue: [#1412](https://github.com/henemm/gregor_zwanzig/issues/1412) Scheibe **S2**.
Vorarbeit: `docs/context/fix-1412-versandweg-basis.md` (Bestandsaufnahme aller 26 Versandwege, Analyse, Scheibenschnitt). S1 ist live (`1e4cc6b7`).

## Request Summary

Python und Go beurteilen denselben Empfänger heute mit zwei getrennten, handgepflegten Regelwerken — nachweislich mit unterschiedlichem Ergebnis. S2 baut den Mechanismus, der beide Seiten zwingt, dieselbe Adresse gleich zu beurteilen, und löst die gemessenen Abweichungen auf.

## Betroffenheit heute: keine

Beide Profile mit bestätigter Adresse (`henning`, `steffi`) tragen eine **schlichte** `mail_to` bei gmail.com — kein Komma, kein Pluszeichen, keine Randzeichen, kein Mehrfach-`@`. **Keine der gefundenen Abweichungen trifft aktuell einen echten Nutzer.** S2 ist vorbeugende Härtung plus Mechanismus, kein Fix eines laufenden Schadens.

Prospektiv sind zwei davon nutzersichtbar: wer seinen Namen mit Komma einträgt (D2) oder eine Plus-Adresse bestätigt (D5), bekommt keine Post.

## Ist-Zustand — beide Regelwerke (Zeilennummern nach S1)

### Python `src/output/channels/email.py` (662 Zeilen)
| Baustein | Zeile | Regel |
|---|---|---|
| `LOCAL_MAIL_DOMAINS` | :40 | `{"henemm.com"}` |
| `_CONTROL_CHARS_RE` / `_TEST_MAILBOX_RAW_PATTERN` | :48 / :49-51 | `[\r\n\x0b\x0c\x00]` · `(?:gregor-test\|gregor-staging)(?:\+[^@]*)?@henemm\.com`, IGNORECASE |
| `_RESERVED_TEST_DOMAINS` / `_TLDS` / `_BARE_TLDS` | :143 / :144 / :145 | `example.com/.net/.org` · `.test .invalid .localhost .example` · bare TLDs |
| `_extract_addr` | :54-57 | `parseaddr()`, Fallback Rohstring |
| `_normalize_addr_for_guard` | :60-68 | lower → `partition("@")` (**erstes** `@`) → Local-Part am ersten `+` gekappt. **Kein** Trailing-Dot-Strip, **kein** Trim |
| `_normalized_addrs_for_guard` | :71-122 | **Union** aus `getaddresses()` (:105-107) und Split an `[,;]` (:109 ff.). Liefert Duplikate und Fragmente ohne `@` |
| `_raw_contains_test_mailbox` | :125-140 | Steuerzeichen strippen, dann Regex |
| `_is_reserved_test_domain` | :148-166 | `rpartition("@")` (**letztes** `@`) → `rstrip(".")` → exakt + `endswith`-TLDs. **Keine Subdomain-Suffixe** |
| `_is_local_mail_domain` | :169-176 | `rpartition`, `rstrip(".")`, exakt gegen `LOCAL_MAIL_DOMAINS` |
| `_load_resend_allowlist` | :179-225 | `<data_dir>/users/*/user.json`, nur mit `email_verified_at`; Eintrag = `_extract_addr().strip().lower()` (:222) **ohne** Plus-Kappung; reservierte Domains raus (:223) |
| `_fallback_recipients_blocked` (S1) | :369-387 | Allowlist ∪ lokal, reservierte immer blockiert |
| Guard Resend-Zweig | :448-495 | Bedingung `"resend" in host` (:448); blockt: keine `@`-Kandidaten · nicht in Allowlist · reserviert · Rohstring-Fangnetz |
| Guard Nicht-Resend-Zweig (#1235) | :496-534 | blockt: keine `@`-Kandidaten · reserviert · **nicht lokal**. Bewusst **ohne** Fangnetz (Kommentar :504-507) |

### Go `internal/mail/sender.go` (565 Zeilen)
| Baustein | Zeile | Regel |
|---|---|---|
| `ErrGuardBlocked` (S1) | :32 | Sentinel |
| `reservedTestDomains` / **`reservedTestDomainSuffixes`** / TLDs | :112-116 / **:122** / :123-129 | **Die Suffix-Liste (`.example.com` u.a.) hat Python nicht** |
| `controlCharsRe` / `testMailboxRawRe` | :256 / :257 | identisch zu Python |
| `normalizedAddrForGuard` | :278-291 | lower+trim → `ParseAddress` auf dem **ungetrimmten** Original (:280) → `Cut(lower,"@")` (**erstes** `@`) → `+`-Kappung |
| `isReservedTestDomain` | :145-166 | ruft **erst** `normalizedAddrForGuard` (:146, Python nicht) → `Cut` (**erstes** `@`) → `TrimRight(".")` → exakt + **Suffix-Schleife** (:155-159) + TLDs |
| `loadResendAllowlist` | :193-232 | wie Python; Eintrag = `ParseAddress` sonst Rohstring (:220-223), lower+trim (:224), reservierte raus (:225) |
| `resendAllowlistDataDir` | :171-176 | `GZ_DATA_DIR`, sonst `"data"` (Python: `get_data_root()`) |
| `splitRecipientField` | :303-327 | `FieldsFunc` an `,`/`;` → `TrimSpace` → `ParseAddress` ok? übernehmen : `Fields` mit `@`-Filter : Roh-Fragment. **Keine `getaddresses`-Strategie, keine Union** |
| `recipientBlocked` | :340-376 | **Host-Gate `"resend"` (:341), sonst `nil`.** Fangnetz (:347) · Allowlist (:356) · pro Teil normalisieren+prüfen (:360-361) · `len(parts)==0` blockt (:365). **Kein `@`-Filter auf den Kandidaten** |
| `recipientBlockedForVerification` | :472-515 | hostunabhängig; Fangnetz · `unicode.IsControl/IsSpace/Cf`-Scan (:483-494) · `ParseAddress` muss gelingen (:496) · `EqualFold(addr.Address, trimmed)` (:502) · reservierte Domain (:509). **Kein Python-Pendant** |

**In Go existiert weder `LOCAL_MAIL_DOMAINS` noch irgendein Nicht-Resend-Guard** (verifiziert per grep).

## Die Abweichungen — alle gemessen, nicht gelesen

Beide Seiten liefen gegen **dasselbe** Datenverzeichnis; Python über den echten `send()`-Pfad (nur `smtplib.SMTP` durch eine Sentinel-Exception ersetzt), Go über eine verbatim-Kopie von `sender.go` im Scratchpad.

| # | Fall | Python | Go | Leck bei |
|---|---|---|---|---|
| **D1** | `fremd@gmail.com` über `mail.henemm.com` | BLOCKIERT (:516) | **ERLAUBT** (:341) | Go — auf dem Stalwart-Pfad prüft dort **niemand** den Empfänger |
| **D2** | `"Emmrich, Henning" <henning@henemm.com>`, Adresse in beiden Allowlists | ERLAUBT | **BLOCKIERT** | Go — `splitRecipientField` liefert `["\"Emmrich", "<henning@…>"]`, `recipientBlocked:359-363` prüft **jeden** Teil ohne `@`-Filter. Nutzersichtbar |
| **D3** | verifiziertes Profil `x@sub.example.com`, Versand dorthin über Resend | **ERLAUBT** | BLOCKIERT | **Python** — `email.py:223` schließt die reservierte Subdomain nicht aus, `sender.go:225` schon. Python würde über Resend an eine RFC-2606-Adresse zustellen |
| **D4** | verifiziertes Profil `a@b@example.com` | BLOCKIERT | **ERLAUBT** | **Go** — `Cut` nimmt das **erste** `@`, „Domain" wird `b@example.com`, passt auf keinen Suffix |
| **D5** | verifiziertes Profil `name+gz@gmail.com`, Versand dorthin | BLOCKIERT | BLOCKIERT | **beide** — Eintrag ungekappt gespeichert, Empfänger plus-gekappt normalisiert. Nutzersichtbar, keine Divergenz |

**D3 und D4 lecken in entgegengesetzte Richtungen** — zwei komplementäre Löcher, nicht ein einseitiger Rückstand.

### Neu gefunden
- **N1 — Trailing-NBSP:** `"henning@henemm.com\xa0"` am Resend-Host → **Python BLOCKIERT, Go ERLAUBT.** Pythons `getaddresses`-Strategie liefert den Kandidaten **mit** NBSP, die Split-Strategie sauber; die **Union** enthält beide, `any(a not in allowlist)` (:474) kippt am schmutzigen. Go `TrimSpace` (:306) entfernt U+00A0. Falsch-Positiv bei Python.
- **N2 — Trailing-Dot-FQDN:** `henning@henemm.com.` → am Resend-Host **beide BLOCKIERT** (Normalisierung strippt den Punkt nicht), am Stalwart-Host Python ERLAUBT (`_is_local_mail_domain:175` strippt ihn). Der Punkt wird in den Domain-Prüfern gestrippt, in den **Normalisierern** nicht — auf **beiden** Seiten. Sichtbar nur, wenn der Läufer die **Gesamtentscheidung** vergleicht.
- **N3 — Mehrfach-Adresse in einem Profilfeld:** `email: "a@b.de, c@d.de"` wird auf **beiden** Seiten als **ein** Allowlist-Eintrag aufgenommen (Python `_extract_addr:57` fällt auf den Rohstring zurück, Go `sender.go:220` ebenso). Toter Eintrag, matcht nie. Kein Divergenz-, sondern ein gemeinsamer Fehler.
- **Python-intern inkonsistent:** `_normalize_addr_for_guard:65` nutzt `partition` (erstes `@`), `_is_reserved_test_domain:160`/`_is_local_mail_domain:174` nutzen `rpartition` (letztes `@`).

### Geprüft und **nicht** divergent
Groß-/Kleinschreibung · ASCII-Randleerzeichen · semikolongetrennte Doppel-Empfänger · gemischt erlaubt+verboten · leerer Empfänger · Fragment ohne `@` · `<addr>`-Form · CRLF-Injection · IDN/Punycode (**gemeinsame** Lücke: keine Seite konvertiert).

## Existing Patterns — Vorbild `tests/test_egress_inventory_drift.py` (119 Zeilen)

- **Pfadauflösung** :25-26 — `Path(__file__).resolve().parents[1]`, relativ zur Testdatei (erfüllt Pfadregel #1409).
- **Bewusste Asymmetrie** :11-13 — Go-Seite als **Text** gelesen, Python-Seite über den **echten Import**; so kann die Python-Liste nicht durch einen Parser-Fehler still falsch gelesen werden.
- **Parsing** :29 — ein Regex je Zeilenform.
- **Auskommentierte Zeilen** :47-51 — Schnitt am **ersten** `//`, geprüft wird nur der Teil davor.
- **Existenz-Vorbedingung** :56-61 — fehlende Datei und leeres Parse-Ergebnis sind eigene, benannte Assertions (kein stilles Grün).
- **Drei Mengen** :72-82 — `only_python`, `only_go`, `different`, je eigene Assertion mit Namensnennung.
- **Parser-Selbsttest** :85-104 — synthetischer Go-Text beweist, dass die Kommentar-Regel greift. Ohne den bliebe der Drift-Test grün, wenn der Regex kaputtgeht.

**Grenze des Vorbilds:** es vergleicht **Listen**. Text-Parsing trägt hier nur für die Konstanten (reservierte Domains/TLDs/Suffixe, `LOCAL_MAIL_DOMAINS`, die zwei Regexe) — **nicht** für die Logik. D1, D2 und N1 sind reine Logik-Divergenzen und mit Text-Parsing unsichtbar.

**Geteilte Fixtures, die beide Sprachen lesen, gibt es im Repo bisher nicht.** `tests/fixtures/` wird nur python-seitig gelesen; Go erzeugt Fixtures zur Laufzeit (`internal/provider/fixture/provider_test.go:22`, `t.TempDir()`). Der einzige `tests/fixtures`-Treffer in Go (`internal/egress/guard_test.go:190`) ist ein nicht-leerer Platzhalter-String, keine Datei. Ein geteiltes Fixture-Format wäre ein Novum.

## Bestandstests, die den Ist-Zustand festschreiben

**Zu D1 — ein direktes Widerspruchspaar, das eine PO-Entscheidung erzwingt:**
- `internal/mail/sender_allowlist_test.go:141` `TestRecipientBlocked_StalwartHostGuardInactive` — verlangt, dass `recipientBlocked("mail.henemm.com", "unbekannt@example.com")` **nil** liefert.
- `tests/tdd/test_stalwart_recipient_guard.py:87` `test_external_real_domain_blocked_on_stalwart` — verlangt, dass `user@gmail.com` auf Stalwart **blockt** (AC-2, #1235).
- Weitere Go-Seite: `recipient_guard_test.go:102`, `resend_guard_test.go:100`.

**Zu D2:** `recipient_guard_test.go:194` schreibt die Block-Richtung für das Test-Postfach fest (Kommentar :189-192 nennt ausdrücklich die Python/Go-Asymmetrie), deckt aber **nicht** den legitimen Empfänger ab — genau dort klafft die Lücke. Python-Gegenstück `test_issue_1147_resend_recipient_invariant.py:426` hält nur die Fehler-*Formulierung* fest, nicht die Erlaubnis.
**Zu D3:** `verify_send_test.go:178` verlangt Go-Verhalten; Python hat **kein** Gegenstück (`test_resend_verified_allowlist.py:400-425` listet keine Subdomain) ⇒ Angleichen Richtung Go **ohne** Testbruch.
**Zu D4, D5, N1:** kein Test auf keiner Seite ⇒ freie Bahn.

## Dependencies

**Upstream:** `data/users/<id>/user.json` (`email_verified_at`, `mail_to`, `email`) · `src/app/loader.py::get_data_root` · `GZ_DATA_DIR`.
**Downstream:** `src/output/channels/email.py` (alle Mail-Versandwege) · `internal/mail/sender.go` (Passwort-Reset `internal/handler/auth.go:282`, Verifikation `:689`, Level-Antrag `:848`, Magic-Link `internal/handler/auth_magic.go:114`).

## Risks & Considerations

- **D1 ist in dieser Scheibe nicht lösbar.** Ein Empfänger-Guard für Go auf Nicht-Resend-Hosts bräuchte die Regel „verifizierte Allowlist **oder** Zweck `verification`/`operator`". Den **Zweck-Begriff gibt es erst mit S4**. Ohne ihn würde ein Go-Guard auf Stalwart Passwort-Reset und Anmeldelink an unbestätigte Adressen abschneiden — die teuerste Fehlerart. **D1 bleibt bei S5**, im Läufer als datierte, benannte Ausnahme geführt (nicht als „erwartetes Verhalten").
- **Produktiv läuft der Resend-Zweig** (`GZ_SMTP_HOST=smtp.resend.com` in `/etc/gregor/mail-prod.env`) — der Go-Stalwart-Pfad ist heute nicht im Einsatz. D1 ist strukturell, kein laufendes Leck.
- **Der Läufer muss die Gesamtentscheidung vergleichen**, nicht einzelne Hilfsfunktionen — N2 und D2 entstehen erst im Zusammenspiel.
- **Beide Hosts gehören in die Achse** (Resend **und** Stalwart), sonst bleibt D1 unsichtbar.
- **Das Fixture muss ein Datenverzeichnis sein**, nicht nur eine Adressliste — D3, D4 und D5 sitzen in der Allowlist-**Befüllung**, nicht in der Prüfung.
- **Sollwerte statt nur „Python == Go"** — sonst gehen die gemeinsamen Fehler (D5, N3, Punycode) als „paritätisch grün" durch.
- **Renderer-Commit-Gate #811** greift, sobald `email.py` gestaged wird.
- **LoC:** Harness + fünf Korrekturen zusammen sprengen 250. Schnitt in **S2a (Harness, Divergenzen als benannte Ausnahmen)** und **S2b (Ausnahmen einzeln auflösen)** vorbereiten.

---

# Analysis (S2a)

## PO-Entscheidungen 2026-07-30
- **Schnitt:** S2a = nur das Prüfwerkzeug, alle bekannten Divergenzen als benannte Ausnahmen festgenagelt. S2b löst sie einzeln auf.
- **Sollwerte D5 und N1: `allow`.** Eine bestätigte Plus-Adresse bekommt künftig Post (heute nie); ein unsichtbares Randzeichen blockiert nicht mehr. Beides ist dieselbe bestätigte Adresse — heute scheitert sie an einem Formfehler der Prüfung.
- **LoC-Override 500** erteilt (Begründung: zwei vollständige Läufer in zwei Sprachen; **keine** Produktivzeile geändert).

## Ehrliche Korrektur zum Mechanismus

**Keiner der geprüften Kandidaten macht bei einer einseitigen Regeländerung beide Suiten rot.** Konstanten-Parität und Verzweigungs-Ratsche messen je **eine** Seite; die Entscheidungs-Parität macht die **geänderte** Seite rot, die andere merkt nichts, solange die Falltabelle unangetastet bleibt.

Was tatsächlich beide erwischt, ist ein **Deckel auf die Zahl der Ausnahmen** (`ausnahmen_hoechstzahl`), den **beide** Läufer aus derselben Datei lesen. Eine neue, unaufgelöste Divergenz lässt sich nur grün bekommen durch (i) Nachziehen der anderen Seite = Ziel erreicht, oder (ii) eine neue Ausnahme — dann reißt der Deckel beidseitig. Den Deckel zu erhöhen ist ein sichtbarer, begründungspflichtiger Akt in einer versionierten Datei.

**Das richtige Erfolgskriterium ist nicht „beide rot", sondern „die Änderung landet nicht, und die Meldung nennt die Pflicht"** — eine rote Suite blockiert genauso gut wie zwei.

## Gewählter Mechanismus

| Baustein | Was er fängt | Wo |
|---|---|---|
| **Entscheidungs-Parität** (Kern) | jede Logikänderung, die einen abgedeckten Fall kippt — inkl. der Zusammenspiel-Fälle D2 und N2, die keine Einzelfunktion zeigt | beide Läufer |
| **Ausnahmen-Deckel** | neue, unaufgelöste Divergenz ⇒ beidseitig rot | beide Läufer |
| **Konstanten-Parität** (Textvergleich, Vorbild `test_egress_inventory_drift.py:11-13`) | Drift in reservierten Domains/TLDs/Suffixen, `LOCAL_MAIL_DOMAINS`, den zwei Regexen | nur Python-Läufer (Go-Seite als Text) |
| **Verzweigungs-Ratsche** je Seite | neue Regel in der Guard-Region, auch ohne abdeckenden Fall | je Läufer, gegen eigene Zahl |

**Verworfen: Regel-ID-Register.** Fängt eine Regel *ohne* ID nicht — und würde als einziger Baustein einen Edit an `email.py` erzwingen, was das **#811-Gate** (`renderer_mail_gate.py:45`) auslöst: frischer Validator-Lauf gegen eine echt zugestellte Staging-Mail, für ein Werkzeug ohne Produktivänderung. Absurder Preis.

**Falle bei der Konstanten-Parität:** die Regexe sind textuell verschieden, semantisch identisch — `[\r\n\x0b\x0c\x00]` (email.py:48) vs. `[\r\n\v\f\x00]` (sender.go:256); `re.IGNORECASE`-Flag vs. Inline-`(?i)` (email.py:49-51 / sender.go:257). Ohne Normalisierung (Escapes zu Codepunkten, `(?i)` abschneiden + Flag separat verlangen, ~12 Zeilen) ist der Vergleich an Tag eins rot und wird prompt entschärft — der klassische Erosionsweg.

**Verzweigungs-Ratsche, gemessen:** Python-Guard-Region 25 Verzweigungen, Go `recipientBlocked`+Helfer 55. Die Zahlen sind **nicht** vergleichbar (verschiedene Zählregeln je Sprache) — jede Seite ratscht gegen ihre eigene, in der geteilten Datei hinterlegte Zahl. Die Python-Region wird per **AST** bestimmt („die `If`-Anweisung im Rumpf von `send()`, deren Bedingung das Literal `resend` enthält") — nicht über Zeilennummern, nicht über Marker-Kommentare, also ohne Zeichenwechsel an der geschützten Datei. Lärm-Empirie aus 12 Monaten Historie: von 11 Go- und 8 Python-Commits berührten nur Regel-Commits (#1122, #1147, #1219, #1235, #1412 S1) die Region ⇒ **null erwartete Fehlalarme**. Auf ganze Dateien geratscht wären es 4 von 8 gewesen.

## Falltabelle

`tests/fixtures/mail_recipient_parity/faelle.json`, ein Fall je Zeile. **JSON**, weil die Fälle NBSP, eingebettete Anführungszeichen und Trailing-Dots enthalten — `json`/`encoding/json` lesen die Escapes bitgleich; jedes andere Format wäre selbst die erste Divergenzquelle.

Fall: `{"id", "host", "to", "soll"}`. **`host` literal**, nicht als Rolle — eine Rolle müsste jede Seite selbst auf einen Host abbilden, und genau diese Abbildung könnte auseinanderlaufen. **Fiktive** Hosts (`smtp.resend-fixture.test`, `mail.henemm.com`), weil `prod_send_gate.py` beim Literal des echten Resend-Hosts anschlägt; die Guard-Bedingung ist eine Teilzeichenketten-Prüfung, der Fixture-Host trifft denselben Zweig.

**Profil-Fixture: wörtlicher `user.json`-Inhalt je Nutzer** unter `"profile"`. Jeder Läufer schreibt den Wert **unverändert** nach `<tmp>/users/<id>/user.json`. Kein Feld-Mapping, keine Default-Regel, keine Frage, ob ein fehlendes `email_verified_at` als `""` oder als fehlender Schlüssel ankommt — beides ist wörtlich darstellbar. Nötig, weil D3/D4/D5 in der Allowlist-**Befüllung** sitzen, nicht in der Prüfung.

**Ausnahmen** als eigener Top-Level-Schlüssel, damit `soll` nie kontaminiert wird:
`{"fall", "seite", "ist", "scheibe", "frist", "grund"}`. Vier Eigenschaften:
1. **Festgenagelt, nicht übersprungen** — geprüft wird `gemessen == ausnahme.ist`. Wer die Divergenz versehentlich behebt, wird rot und liest „aufgelöst, Ausnahme entfernen". Tugend des `# gz-main-path:`-Musters: die Ausnahme ist eine Behauptung über die Wirklichkeit, keine Abschaltung.
2. **Begründungspflicht** mit Mindestlänge (Vorbild `test_repo_path_hardcoding_ratchet.py:351`, `_MIN_BEGRUENDUNG = 15`).
3. **Eigene Frist** — läuft sie ab, wird der Läufer rot. Stundung, kein Freibrief; verhindert, dass S2b sich stillschweigend auflöst.
4. **Auflösung in S2b = eine gelöschte Zeile** plus Deckel um eins gesenkt (= Fortschrittsnachweis). `soll` steht bereits richtig und wird nicht angefasst.

Startbestand **6 Ausnahmen**: D1 (go), D2 (go), D3 (python), D4 (go), D5 (beide), N1 (go).

## Wie jede Seite an ihre Entscheidung kommt

**Python — `EmailOutput.send()` mit Sentinel am Transport. Gemessen: 10 Fälle in 4 ms.** Die vermutete Kostenfrage trifft nicht zu: eine Sentinel-Ausnahme, die **weder** von `smtplib.SMTPException` **noch** von `OSError` erbt, fällt durch alle `except`-Zweige der Retry-Schleife (email.py:575-661) und verlässt `send()` beim ersten Versuch — keine Wiederholung, kein `sleep`. Die ehrlichste Variante ist zugleich die billigste.

Zwei zwingende Konstruktionsdetails:
1. **Objekt nicht über `Settings` bauen.** `_resend_default_deny` (config.py:195-215) lenkt unter pytest **jeden** Resend-Host auf Stalwart um — der Läufer würde still den falschen Zweig messen und wäre grün, ohne die Resend-Regel je gesehen zu haben (Python-Entsprechung der `testing.Testing()`-Falle in Go). Stattdessen `__new__` + die acht Attribute direkt setzen. `send()` liest für die Guard-Entscheidung ausschließlich `self._host` (email.py:448).
2. **Datenwurzel über `app.loader._DATA_ROOT`, nicht `GZ_DATA_DIR`.** `_DATA_ROOT` hat Vorrang (`loader.py:1054`), und `tests/conftest.py:91-97` setzt es bereits per autouse — wer nur `GZ_DATA_DIR` setzte, würde überstimmt und läse eine leere Wurzel.

**Go — `recipientBlocked(host, to)` allein genügt.** `Send()` (sender.go:439-447) kettet `recipientBlocked` → `resendBlocked` → `dialAndSend`; die letzten beiden sind Host-Policies mit Python-Entsprechungen **außerhalb** der Guard-Region (`config.py:195-215`, `src/app/egress_guard.py`) und gehören symmetrisch nicht in die Achse. **Damit löst sich die `resendBlocked`-Falle von selbst: der Läufer ruft `Send()` gar nicht.** Kein Testflag, kein Seam, kein Build-Tag — jede dieser Varianten wäre eine Aufweichung von #1122. Datenverzeichnis über `t.Setenv("GZ_DATA_DIR", …)` → `resendAllowlistDataDir()` (sender.go:171-176).

**Go-Pfadanker gemessen, nicht geraten:** `runtime.Caller(0)` liefert unter `-trimpath` einen **modulrelativen** Pfad und bricht still; `os.Getwd()` bleibt in allen geprüften Varianten das Paketverzeichnis. Also: von `os.Getwd()` aufwärts bis zum Verzeichnis mit `go.mod` (genau eine im Repo, geprüft), Obergrenze ~6 Ebenen, dann Existenz der Falltabelle prüfen und sonst **laut** abbrechen.

**Entscheidungsvokabular `allow`/`block`, Verwechslungsschutz je Seite verschieden:**
- **Go: konstruktiv ausgeschlossen** — genau eine Funktion wird gerufen. `errors.Is(err, ErrGuardBlocked)` taugt hier **nicht** zur Unterscheidung, weil `resendBlocked` denselben Sentinel wrappt (sender.go:32, 79, 84); die Trennschärfe kommt aus dem Aufrufpunkt.
- **Python: muss aktiv abgesichert werden.** Sentinel gefangen ⇒ `allow` (und **nur** dann; Durchlauf ohne Sentinel ist ein Läuferfehler, kein `allow`). `OutputConfigError` **mit** Guard-Marker im Text (`#1147/#1219` bzw. `#1235`, email.py:490/530) ⇒ `block`. Alles andere ⇒ lauter Abbruch mit Typnennung, **niemals** still als `block` gebucht — sonst wird jeder künftige Konfigurationsfehler als „blockiert" verbucht und der Läufer ist grün, während er nichts mehr prüft.

## Nachweis, dass der Läufer selbst funktioniert

Vier Stellen, an denen stilles Grün droht, je ein Gegenbeweis:
1. **Kommt die Fixture-Datenwurzel an?** Ein Fall mit einer Adresse, die es **nur im Fixture** gibt (`paritaet-fixture@henemm.com`, `soll: allow` am Resend-Host) — kann nur grün werden, wenn die Fixture-Allowlist geladen wurde. Direktes Äquivalent zum Parser-Selbsttest des Vorbilds.
2. **Erreicht der Python-Läufer den Transport?** `allow` nur bei gefangenem Sentinel; zusätzlich muss der Gesamtlauf mindestens ein `allow` **und** ein `block` enthalten.
3. **Existieren Datei und Fälle?** Eigene benannte Assertions (Vorbild `test_egress_inventory_drift.py:56-61`) — nicht „0 Fälle geprüft, alles grün".
4. **Findet der Konstanten-Parser noch etwas?** Synthetischer Go-Text mit auskommentierter und echter Zeile; für die Ratsche eine Assertion, dass die Region in `email.py` überhaupt **gefunden** wurde.

## Scope

| Datei | Art | LoC |
|---|---|---|
| `tests/fixtures/mail_recipient_parity/faelle.json` | CREATE | ~55 |
| `tests/test_mail_recipient_parity.py` | CREATE | ~135 |
| `internal/mail/recipient_parity_test.go` | CREATE | ~135 |
| `docs/specs/modules/fix_1412_s2a_regelwerk_paritaet.md` | CREATE | ~85 |
| **Summe** | | **~410** (Override 500 erteilt) |

**Keine Zeile an `src/output/channels/email.py` oder `internal/mail/sender.go`** — bewusste Entwurfsvorgabe, hält das #811-Gate draußen.

**Bestandstests: keiner wird rot.** S2a ändert keine Produktivzeile. Go-Baseline gemessen (`go test ./internal/mail/ -count=1` → ok, 0,017 s); alle 8 Bestands-Testdateien im Paket nutzen `t.Setenv` (auto-restore), kein `os.Setenv`-Rest, kein `os.Chdir` unter `internal/` ⇒ eine neunte Datei kollidiert nicht. Namens-Gate und Pfad-Ratsche lassen beide neuen Dateien durch.

**Ablauf-Hinweis:** die neue Go-Testdatei liegt **co-located** neben `sender.go` — in der RED-Phase blockt das Gate `.go`-Edits (bekannt aus S1). Go-Test und -Nachweis wandern in Phase 6.

## Known Limitations (gehören in die Spec)

1. **Semantik-Tausch ohne Verzweigungs- oder Konstantenänderung** — z.B. `partition` → `rpartition` (email.py:65) ändert weder Zählung noch Liste. Nur ein abdeckender Fall sieht das; D4 deckt genau einen ab, verwandte Formen bleiben blind.
2. **Regeln außerhalb der beobachteten Region** — ein neuer Empfänger-Filter in `notification_service.py` oder `internal/handler/auth.go` ist für alle Bausteine unsichtbar.
3. **Gemeinsame Fehler** — beide Seiten identisch falsch ⇒ Parität grün, außer der `soll`-Wert widerspricht. Punycode/IDN bleibt auf beiden Seiten ungeprüft (bewusst S2a-fremd).
4. **`recipientBlockedForVerification`** (sender.go:472-515) ist nicht in der Achse — anderer Zweck, kein Python-Pendant, gehört zu S4.
5. **`resendBlocked` / `_resend_default_deny`** sind Host-Policies, nicht in der Achse — symmetrischer Ausschluss.
6. **Der Host-Vergleich selbst** — beide Seiten prüfen `"resend"` als Teilzeichenkette (email.py:448, sender.go:341). Stellte jemand eine Seite auf exakten Vergleich um, bliebe der Läufer grün.
7. **N2b ist heute nur scheinbar paritätisch** — Go sagt `allow`, weil auf dem Stalwart-Pfad **gar kein** Guard läuft (D1), nicht weil es dieselbe Entscheidung getroffen hätte. Mit der Auflösung von D1 in S5 kippt N2b in eine echte Divergenz.
8. **N3** (Mehrfach-Adresse im Profilfeld) wird als Fall mit `soll: block` plus Ausnahme festgenagelt, **nicht** aufgelöst — Auftrennen erweitert die erlaubte Menge und ist eine Produktentscheidung, die nicht ins Prüfwerkzeug gehört.

**Regel-Budget:** ersetzt keine bestehende Regel ⇒ **Prüfdatum 2026-10-28**. Bauform wie `test_repo_path_hardcoding_ratchet.py:339` (`EXPIRY`-Konstante, per Assertion gebunden). Der Läufer läuft am Prüfdatum nicht von selbst rot — nur maschinell auffindbar. Jede **einzelne Ausnahme** trägt zusätzlich eine eigene Frist.

## Offener Punkt
- Die sechs `soll`-Werte sind Produktentscheidungen, keine Messungen — sie gehören mit den ACs freigegeben, sonst schreibt das Prüfwerkzeug die Politik. D5 und N1 sind bereits entschieden (`allow`).
