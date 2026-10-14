# ADR-0087: Empfängerschutz — Fremdadressen nur über Resend an verifizierte Profile, jeder andere Postausgang nur die eigene Domain

- **Status:** Akzeptiert
- **Datum:** 2026-10-14
- **Bezug:** GitHub-Issue #1412 (Scheiben S1, S2a, S2b, S4a, S5), Spec
  `docs/specs/modules/fix_1412_s5_go_empfaengerschutz.md`; Vorgänger-Specs
  `fix_1412_s1_guard_am_echten_postausgang.md`, `fix_1412_s2a_regelwerk_paritaet.md`,
  `fix_1412_s2b_divergenzen_aufloesen.md`, `fix_1412_s4a_empfaengervertrag_telegram.md`; baut auf #1122 (Resend
  Default-Deny), #1147/#1219 (Resend-Allowlist) und #1235 (Lokal-Guard Python) auf

## Kontext

Der Empfängerschutz ist über mehrere Scheiben gewachsen und gilt in zwei Sprachen (Python-Core
und Go-API) und über mehrere Postausgänge (Resend, das lokale Mail-Relay Stalwart
`mail.henemm.com`, der Google-SMTP-Weg für Test-Konten). Bis S5 schützte Go Empfänger nur auf
dem Resend-Postausgang; über Stalwart ließ Go jede Adresse durch, Python dagegen nur
`@henemm.com` (Divergenz D1, letzte Ausnahme im Paritäts-Prüfwerkzeug). Außerdem sahen der
Python-Guard und der Postausgang in Randfällen nicht dieselbe Empfängerliste (Nebenbefund C3-20).
Ohne festgehaltene Grundsatzregel kann jede dieser Linien still wieder gelockert werden.

## Entscheidung

- **(a) Grundsatz.** Fremdadressen (alles außer der eigenen Domain) gehen ausschließlich über
  **Resend** und nur an Adressen aus der **Allowlist verifizierter Profile**
  (`email_verified_at` gesetzt) plus die konfigurierte Betreiber-Adresse. **Jeder andere
  Postausgang** (Stalwart, Google, jeder künftige) erreicht nur die **eigene Domain**
  `henemm.com` (Domain nach dem letzten `@`, ohne Groß-/Kleinschreibung, abschließende Punkte
  egal). **Reservierte Test-Domains** (RFC 2606: `example.*`, `.test`, `.invalid`, `.localhost`,
  `.example`) sind immer gesperrt. Entschieden wird am **tatsächlich benutzten** Postausgang
  (S1): ein Block heißt `ErrGuardBlocked` (Go) bzw. `OutputConfigError` (Python) und löst
  **keinen** Fallback-Versuch aus. Keine Host-Ausnahme (auch nicht für Google) — unbekannte
  Hosts bekommen die strengste Regel (fail-closed). Dieser Grundsatz gilt für die Zwecke
  `user_profile` und `inbound_reply` (Go: `Send`/`SendWithFallback`). Der Zweck `verification`
  folgt seiner eigenen, host-unabhängigen Regel aus (b) — dort ist eine Fremdadresse auch auf
  einem Nicht-Resend-Postausgang zulässig, weil die Mail die Adresse erst bestätigen soll.
- **(b) Zwecke.** `user_profile` (Briefings, Alarme, Reset — Allowlist bzw. Lokalregel),
  `inbound_reply` (Antworten auf eingehende Befehle — dieselbe Regel) und `verification`
  (Bestätigungs-, Magic-Link-, Google-Hinweis-, Lösch-Code-Mail). `verification` ist in Go
  faktisch über `recipientBlockedForVerification` umgesetzt: host-unabhängig, genau eine nackte
  Adresse, Test-Postfach-Fangnetz und reservierte Domains gesperrt, aber **ohne** Allowlist
  (die Adresse ist per Definition noch nicht verifiziert).
- **(c) Fangnetz Test-Postfach nur auf Resend.** Der parser-unabhängige Rohstring-Scan auf
  `gregor-test@`/`gregor-staging@henemm.com` (plus-tolerant) gilt auf dem Resend-Postausgang
  (und im Verifikationspfad). Auf jedem anderen Postausgang ist er **bewusst aus** — nur so
  erreicht ein Wegwerf-Konto `gregor-test+…@henemm.com` das Stalwart-Testpostfach.
- **(d) C3-20-Sollwerte (beide Sprachen, beide Host-Klassen).**
  `a@henemm.com, garbage` ⇒ block/block; `a@henemm.com garbage` ⇒ block/block (so liest auch
  der Postausgang das Feld); `"x y"@henemm.com` ⇒ Resend block, lokal allow;
  `Nachname, Vorname <a@henemm.com>` (ungequotet) ⇒ block/block;
  `"Nachname, Vorname" <a@henemm.com>` (gequotet) ⇒ allow/allow. Python bewertet dazu die
  quote-bewusste Hauptliste (`getaddresses([recipient])`): ein nicht-leerer Eintrag ohne `@`
  blockt den gesamten Versand. Go behält im Whitespace-Fallback das ganze Fragment als
  Kandidaten, sobald außerhalb gequoteter Anzeigenamen ein Feld ohne `@` steht.
- **(e) Telegram-`chat_id` nur über den Einmal-Token-Flow.** Seit #2141 übernimmt
  `PUT /api/auth/profile` für `telegram_chat_id` nur den Leerstring („trennen“); gesetzt wird
  die `chat_id` ausschließlich über `/start TOKEN` → `PostTelegramConnectHandler`. Damit ist
  „Chat ∈ Profil“ ein Herkunftsbeleg für den Telegram-Empfängervertrag (S4a).
- **(f) Go versendet keine Briefings und keine Alarme.** Go-seitige Mails sind nur
  Passwort-Reset, Tarif-Antrag (an die Betreiber-Adresse) und die vier Verifikations-Mails.
  Ein Reset-Block bleibt nach außen `{"status":"ok"}` (Anti-Enumeration) und ist nur über
  eine eigene Logzeile ohne Empfänger und ohne Benutzernamen sichtbar.
- **(g) Paritäts-Prüfwerkzeug als Wächter.** Python und Go laufen gegen dieselbe Falltabelle
  `tests/fixtures/mail_recipient_parity/faelle.json` mit gemeinsamen Sollwerten
  (`tests/test_mail_recipient_parity.py`, `internal/mail/recipient_parity_test.go`).
  Abweichungen sind nur als Ausnahme mit Frist und Begründung zulässig; die Höchstzahl steht
  auf **0**. Verzweigungsratschen je Sprache zählen die Entscheidungspunkte der Guard-Region,
  damit neue Bedingungen nicht ohne abdeckenden Fall entstehen.

## Verworfene Alternativen

- **Google-Ausnahme** (Host enthält `google` ⇒ Fremdadressen erlaubt): kein belegter Bedarf,
  Hostname-Raten wäre eine ungeprüfte Lockerung und eine Go-only-Divergenz; auf Staging ist der
  Google-Weg per Egress-Wächter ohnehin gesperrt.
- **Empfängerliste vor dem Versand neu schreiben** (Guard und Postausgang auf exakt dieselbe
  Liste umbauen): deutlich größere Wirkfläche, jeder Aufrufer müsste mitgeprüft werden. Das
  Blocken bei Abweichung erreicht dasselbe Schutzziel.
- **Fall B erlauben** (`a@henemm.com garbage` zerlegen): hätte den Python-Guard lockern müssen
  und genau den Unterschied zwischen Guard und Postausgang wieder geöffnet.

## Konsequenzen

- Auf Staging (Primärweg Stalwart) werden Reset-Mails an Fremdadressen geblockt — gewollt;
  echte Reset-Mails auf Staging nur über Wegwerf-Konten `gregor-test+…@henemm.com`.
- Prod bleibt im Normalbetrieb unverändert, solange Resend der Primärweg und kein
  Stalwart-Fallback gesetzt ist.
- Empfängerfelder mit `@`-losen Resten oder ungequoteten Namen ohne `<>` werden geblockt statt
  still teilweise zugestellt; ein Block erzeugt immer eine Logzeile.
- Eine Lockerung einer dieser Regeln braucht ein neues ADR, das dieses ablöst.
