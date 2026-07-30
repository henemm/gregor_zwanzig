---
entity_id: fix_1412_s1_guard_am_echten_postausgang
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [mail, empfaengerschutz, sicherheitspfad]
---

# Fix #1412 Scheibe S1 — Empfänger-Guard am tatsächlich benutzten Postausgang

## Approval

- [x] Approved — PO-go 2026-07-30 (sechs Zusicherungen freigegeben; Ausweichweg-Regel „bestätigte Profil-Adresse ODER lokal zustellbar" ausdrücklich mit entschieden)

## Purpose

Wenn eine Mail nicht über den geplanten Postausgang geht, sondern auf einen
Ersatzweg ausweicht (Python: Stalwart-Fallback nach gescheitertem
Resend-Versuch; Go: `SendWithFallback`), muss die Prüfung „darf dieser
Empfänger diese Mail bekommen?" für **den Postausgang gelten, der tatsächlich
benutzt wird** — nicht für den ursprünglich geplanten. Heute ist das nicht
so: die Guard-Entscheidung hängt an einem Host, der beim Ausweichen nicht
mehr stimmt. In Python ist das eine **live** Sicherheitslücke (beide echten
Nutzer haben `mail_to` auf gmail.com, eine Resend-Störung schickt ihre
Briefings ungeprüft über Stalwart hinaus). In Go ist derselbe Fehlerpfad
strukturell vorhanden, aber mangels konfiguriertem Fallback-Host aktuell
inert. Diese Scheibe schließt beide Ausprägungen, ohne den Empfängerschutz
sonst zu verändern.

## Source

- **Datei:** `src/output/channels/email.py` — Klasse `EmailOutput`, Methode
  `send()` (Guard-Verzweigung `:428`/`:476`, Primär-Dial `:536`,
  Fallback-Dials `:580-596` und `:622-635`)
- **Datei:** `internal/mail/sender.go` — Funktionen `recipientBlocked`
  (`:331`), `resendBlocked` (`:64`), `SendWithFallback` (`:529-547`)

> **Schicht-Hinweis:** Beide Dateien sind Backend — `email.py` ist
> Python-Core (`src/output/channels/`), `sender.go` ist Go-API
> (`internal/mail/`). Kein Frontend-Anteil in dieser Scheibe.

## Estimated Scope

- **LoC:** ~120 (added+deleted)
- **Files:** 2 Quelldateien + 1 bestehende Testdatei (Inversion eines
  einzelnen Tests) + 2 neue Testdateien
- **Effort:** medium (kleiner Schnitt, aber produktiver Sicherheitspfad →
  hohes Risiko, sorgfältige Nachweise nötig)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.channels.base.OutputConfigError` | Python-Exception | Guard-Block wird weiterhin darüber signalisiert — keine neue Exception-Klasse nötig |
| `app.loader.get_data_root()` | Python-Funktion | Auflösung des `data_dir` für `_load_resend_allowlist()` — bleibt unverändert, wird aber jetzt ggf. mehrfach pro `send()`-Aufruf aufgerufen (s. Known Limitations) |
| `internal/egress.SMTPAllowed` | Go-Funktion | Erste Prüfung in `dialAndSend` (Egress-Linie #1337) — bleibt unberührt, läuft weiterhin vor jedem Dial |
| `internal/mail.recipientBlocked` / `resendBlocked` | Go-Funktionen | Liefern künftig einen unterscheidbaren Fehlertyp statt nur eines Fehlertexts |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/channels/email.py` | MODIFY | Guard-Verzweigung (`:415-514`) wandert aus `send()` in eine neue `_dial_and_send(host, user, password, recipients, msg, from_addr)`; Primärschleife (`:536`) und beide Fallback-Zweige (`:580-596`, `:622-635`) rufen sie auf, jeweils mit dem Host, der tatsächlich gewählt ist |
| `internal/mail/sender.go` | MODIFY | `recipientBlocked`/`resendBlocked` liefern einen als solchen erkennbaren Guard-Fehler (Typ/Sentinel, `errors.Is`-fähig); `SendWithFallback` (`:529-547`) bricht bei diesem Typ ohne zweiten Sendeversuch ab — zusätzlich zum bestehenden `535`-Text-Check für echte Auth-Fehler (der unverändert bleibt) |
| `internal/mail/recipient_guard_test.go` | MODIFY | `TestSendWithFallback_RecipientGuardTriggersFallbackAttempt` (`:282-295`) beschreibt heute wörtlich das R1-Fehlverhalten als gewollt — wird invertiert: Guard-Block darf keinen zweiten Sendeversuch mehr auslösen |
| `tests/tdd/test_mail_fallback_guard.py` | CREATE | Python-Nachweis AC-1/AC-2/AC-6 (Sink am Transportrand) |
| `internal/mail/fallback_guard_test.go` | CREATE | Go-Nachweis AC-3/AC-4 (Versuchszähler + Fehler-vor-Dial) |

### Estimated Changes
- Files: 5 (2 Quelldateien modifiziert, 1 Bestandstest modifiziert, 2 neue Testdateien)
- LoC: +~90/-~30 (grobe Schätzung, Ziel Gesamtbudget ~120 added+deleted)

## Scope-Korrektur nach RED (2026-07-30)

Die RED-Phase hat einen Fehler in der Analyse aufgedeckt. **Die Python-Seite hat
unter der freigegebenen Ausweichweg-Regel keinen erreichbaren Defekt:**

Der Guard läuft in `send()` **einmal, vor der gesamten Retry-/Fallback-Schleife**
(Guard `:428`/`:476`, Schleifenbeginn `:534`). Ein Empfänger, der ihn nicht
besteht, erreicht **keinen** Dial — weder primär noch Fallback. Über den
Ausweichweg gehen also ausschließlich Empfänger, die die Prüfung des primären
Hosts bestanden haben.

Die freigegebene Fallback-Regel ist `allowlist ∪ local`, die Primär-Regel je nach
Host `allowlist` **oder** `local` — in beiden Fällen eine **Teilmenge** der
Fallback-Regel. Es kann daher keinen Empfänger geben, der primär durchkommt und
auf dem Ersatzweg scheitern müsste. Empirisch bestätigt: der als RED geplante
AC-1-Test ist grün, über alle durchgespielten Kombinationen
(resend/nicht-resend Primärhost × verifiziert/lokal/keins).

**Folge für den Zuschnitt:**
- Der vollständige `_dial_and_send`-Umbau (~60 LoC Umstrukturierung im
  produktiven Sicherheitspfad, **null** Verhaltensänderung heute) wandert nach
  **S3**, wo er die Transport-Kapselung trägt und damit einen Zweck hat.
- In S1 bleibt eine **minimale** Absicherung: vor jedem der beiden Fallback-Dials
  (`:582`, `:624`) wird die Empfänger-Regel gegen den **Fallback-Host** erneut
  ausgewertet (`allowlist ∪ local`). Heute verhaltensneutral; sie schließt die
  Lücke dauerhaft für den Fall, dass `_fallback_host` (= `settings.imap_host`,
  `:360`) je auf einen externen Relay zeigt. ~10-15 LoC statt ~60.
- Die vier Python-Tests bleiben als **Regressionsschutz** bestehen — sie halten
  die heute schon geltende Zusicherung fest, damit sie nicht verlorengeht.
- **Der Verhaltensfix dieser Scheibe ist die Go-Seite** (R1), zweifach rot
  reproduziert.

Die sechs freigegebenen ACs bleiben unverändert gültig; AC-1, AC-2b und AC-6
sind heute bereits erfüllt und werden abgesichert statt hergestellt.

## Implementation Details

### Python — minimale Fallback-Prüfung (statt `_dial_and_send`-Umbau, s. Scope-Korrektur)

Vor jedem der beiden Fallback-Dials (`:582`, `:624`) wird die Empfänger-Regel
gegen `self._fallback_host` erneut ausgewertet: erlaubt ist, wer in der
Allowlist der bestätigten Profil-Adressen steht **oder** lokal zustellbar ist.
Reservierte Test-Domains bleiben gesperrt. Bei Ablehnung wird der Fallback nicht
versucht, sondern der bestehende Fehler durchgereicht.

Die untenstehende `_dial_and_send`-Beschreibung gilt für **S3**, nicht für S1 —
sie bleibt als Vorlage stehen.

### (S3, nicht S1) Python — `_dial_and_send` kapselt Guard + Dial

Die heutige Guard-Verzweigung prüft `self._host` **einmalig**, bevor die
Retry-Schleife beginnt (`send():415-514`). Sie zieht in eine neue Methode
`_dial_and_send(self, host, user, password, recipients, msg, from_addr)`,
die für jeden tatsächlichen Verbindungsversuch aufgerufen wird:

- Primärschleife (`:536`, `smtplib.SMTP(self._host, self._port)`) ruft sie
  mit `host=self._host`.
- 4xx-Fallback-Zweig (`:580-596`) ruft sie mit `host=self._fallback_host`.
- OSError-Fallback-Zweig (`:622-635`) ruft sie mit `host=self._fallback_host`.

Die Guard-Logik entscheidet jetzt gegen den übergebenen `host`-Parameter statt
gegen `self._host`. Bewusst **nicht** anfassen: der Lokal-Zweig prüft
`_raw_contains_test_mailbox` absichtlich nicht (`:484-487`, Begründung im
bestehenden Kommentar) — diese Entscheidung wird beim Verschieben 1:1
mitgenommen, nicht stillschweigend umgedreht.

#### Regel auf dem Ersatz-Postausgang (PO-Entscheidung 2026-07-29)

Der Lokal-Zweig (`else`, heute `_is_local_mail_domain` — nur `@henemm.com`)
beruht auf der Annahme, der eigene Mailserver stelle ausschließlich lokal zu.
Diese Annahme ist falsch: Stalwart relayt externe Empfänger weiter
(infra#114). Würde die heutige Regel unverändert an den Ersatz-Postausgang
gebunden, wäre der Ausweichweg für **beide realen Nutzer** wirkungslos — ihre
`mail_to` liegen bei einem externen Anbieter. Eine Störung des primären
Postausgangs hieße dann: gar keine Zustellung.

**Festlegung:** Auf dem Ersatz-Postausgang ist ein Empfänger erlaubt, wenn er
**entweder** in der Allowlist der bestätigten Profil-Adressen steht
(`_load_resend_allowlist()`, Kriterium `email_verified_at` — dieselbe Quelle
wie auf dem primären Weg) **oder** lokal zustellbar ist
(`_is_local_mail_domain`, heutiges Verhalten). Alles andere wird geblockt.
Reservierte Test-Domains bleiben auf beiden Wegen bedingungslos gesperrt.

Damit gilt auf dem Ausweichweg dieselbe Zulässigkeitsfrage wie auf dem
Hauptweg — der Ausweichweg bleibt für berechtigte Empfänger nutzbar, und ein
Empfänger, der nirgends bestätigt ist, kommt auf keinem Weg durch. Die
Vereinigung (statt Ersetzung) erhält das heutige Lokal-Verhalten unverändert,
insbesondere die gewollte Zustellung an `gregor-test@`/`gregor-staging@`.

Konsequenz, bewusst in Kauf genommen: die Guard-Prüfung (inkl. Laden der
Allowlist über `_load_resend_allowlist()`) läuft jetzt bei jedem
Retry-Versuch der Primärschleife erneut, nicht mehr nur einmal vor der
Schleife. Das Ergebnis ist deterministisch identisch (gleicher Host, gleiche
Empfänger), nur die Häufigkeit der Dateisystem-Lesevorgänge steigt bei
tatsächlichen Retries — siehe Known Limitations.

Der Fallback-Port bleibt wie heute hart auf `587` (`:582`, `:624`) — das ist
Bestandsverhalten und nicht Teil dieser Scheibe.

### Go — Guard-Fehlertyp statt Textvergleich

`recipientBlocked`/`resendBlocked` liefern heute einen normalen
`fmt.Errorf(...)`-Fehler ohne erkennbaren Typ. `SendWithFallback` (`:529-547`)
unterscheidet nur per `strings.Contains(err.Error(), "535")` zwischen
„permanent, kein Fallback" und „vorübergehend, Fallback versuchen". Ein
Guard-Block enthält kein „535" → er zählt heute fälschlich als vorübergehend
→ `Send(fallbackCfg, …)` wird versucht → da der Fallback-Host typischerweise
kein „resend" enthält, greift `recipientBlocked` dort nicht (`:332`) → die
bewusst blockierte Mail geht über den Fallback-Weg raus (R1).

Fix: `recipientBlocked`/`resendBlocked` wrappen ihre bestehenden
Fehlermeldungen (Text bleibt für die bestehenden String-Assertions
unverändert, z. B. `"1219"`, `"1147"`, `"GZ_RESEND_ALLOWED"`) in einen
gemeinsamen, mit `errors.Is`/`errors.As` erkennbaren Guard-Fehlertyp.
`SendWithFallback` prüft **zuerst** auf diesen Typ (→ sofortiger Abbruch,
kein zweiter Sendeversuch) und **danach weiterhin** auf den `535`-Text
(→ ebenfalls sofortiger Abbruch, für echte SMTP-Auth-Fehler, die aus
`dialAndSend`/`net/smtp` kommen und keinen Guard-Typ tragen). Jeder andere
Fehler (Netzwerk-/Zeitfehler aus `dialAndSend`) bleibt wie bisher
fallback-auslösend.

`egress.SMTPAllowed` (`internal/egress/guard.go:98`, aufgerufen als erste
Anweisung in `dialAndSend`, `:379`) bleibt unberührt — sie ist bereits eine
eigene Linie vor dem Dial und nicht Teil dieser Guard-Typisierung.

## Expected Behavior

- **Input:** Ein Sendeversuch (Python: `EmailOutput.send()`; Go:
  `mail.SendWithFallback()`), bei dem der primäre Postausgang scheitert und
  auf einen Ersatzweg ausgewichen wird.
- **Output:** Die Empfänger-Zulässigkeit wird gegen den Postausgang
  entschieden, der für den jeweiligen Versuch tatsächlich gewählt ist. Ein
  bewusst blockierter Empfänger bleibt auf **jedem** Weg blockiert; ein auf
  beiden Wegen erlaubter Empfänger kommt weiterhin durch.
- **Side effects:** Keine Änderung an Retry-Anzahl, Wartezeiten oder
  sonstigem Fehlerverhalten (Netzwerkfehler, Zeitüberschreitung,
  Auth-Fehler) — nur die Guard-Bindung ändert sich.

## Acceptance Criteria

- **AC-1:** Given eine Mail weicht nach einem Ausfall des primären
  Postausgangs auf den Ersatz-Postausgang aus, und der Empfänger ist in
  keinem Nutzerprofil als bestätigte Adresse hinterlegt und auch nicht lokal
  zustellbar / When der Versand über den Ersatzweg versucht wird / Then wird
  die Mail auf dem Ersatzweg geblockt und nicht zugestellt — heute geht sie
  ungeprüft durch.
  - Test: Sink am Transportrand (`smtplib.SMTP`) bleibt für den Ersatzweg
    stumm — es findet kein Verbindungsversuch statt.

- **AC-2:** Given derselbe Ausweich-Fall, aber der Empfänger ist eine im
  Nutzerprofil hinterlegte **bestätigte** Adresse bei einem externen Anbieter
  (der Regelfall der realen Nutzer) / When der Versand über den Ersatzweg
  läuft / Then kommt die Mail zu — der Ausweichweg bleibt für berechtigte
  Empfänger nutzbar, eine Störung des primären Postausgangs führt nicht zum
  Ausfall der Zustellung.
  - Test: Sink am Transportrand zeichnet einen tatsächlichen Zustellversuch
    mit genau diesem Empfänger auf.

- **AC-2b:** Given ein Empfänger der eigenen Domain (lokal zustellbar), der
  in keinem Profil bestätigt ist / When der Versand über den Ersatzweg läuft
  / Then kommt die Mail weiterhin zu — das heutige Lokal-Verhalten bleibt
  unverändert erhalten, insbesondere für die Test-Postfächer.
  - Test: Sink zeichnet den Zustellversuch auf.

- **AC-3:** Given eine Mail wird bewusst wegen des Empfängers auf dem
  primären Weg abgelehnt / When der Versand mit Ersatzweg-Logik aufgerufen
  wird / Then löst das **keinen** zweiten Sendeversuch über den Ersatzweg
  aus.
  - Test: Versuchszähler zeigt genau einen Sendeversuch; der Ersatzweg
    zeigt keine Aktivität.

- **AC-4:** Given der primäre Versand scheitert an einem echten
  Netzwerk- oder Zeitfehler (kein Empfänger-Grund) / When der Versand mit
  Ersatzweg-Logik läuft / Then wird der Ersatzweg weiterhin versucht — dieses
  Verhalten darf nicht verlorengehen.
  - Test: Primärer Weg ist absichtlich unerreichbar (Verbindungsfehler),
    Fehlermeldung belegt einen tatsächlichen zweiten Versuch über den
    Ersatzweg.

- **AC-5:** Given der primäre Versand scheitert an falschen Zugangsdaten
  (Authentifizierungsfehler) / When der Versand mit Ersatzweg-Logik läuft /
  Then bricht der Versand sofort ab, ohne den Ersatzweg zu versuchen — wie
  bisher.
  - Test: Bestehender Nachweis (Live-Schicht, Stalwart-Auth-Fehler)
    bleibt unverändert grün; keine neue Kern-Schicht-Prüfung nötig, da der
    zugrundeliegende Mechanismus (Text-Erkennung des Auth-Fehlers) in dieser
    Scheibe nicht angefasst wird.

- **AC-6:** Given der produktive Sendeweg im Normalbetrieb (primärer
  Postausgang funktioniert, kein Ausweichen nötig) / When eine reguläre
  Mail an einen erlaubten Empfänger gesendet wird / Then verhält sich der
  Versand unverändert zum heutigen Stand — keine neue Blockade, keine neue
  Verzögerung.
  - Test: Bestehende Bestandstests, die ausschließlich den Primärweg
    prüfen, bleiben unverändert grün (s. „Betroffene Bestandstests").

## Invarianten / Was sich nicht ändern darf

- **Kein Kollateralschaden.** Kein Empfänger, der heute durchkommt und auf
  beiden Postausgängen erlaubt ist, darf nach diesem Umbau hängenbleiben —
  „Mails gehen nicht mehr raus" ist die teuerste Fehlerart in diesem
  Sicherheitspfad.
- **Retry-Verhalten unverändert.** Anzahl der Versuche, Backoff-Zeiten
  (5s/15s/30s) und die Unterscheidung 4xx (temporär) vs. 5xx (permanent)
  bleiben exakt wie heute — diese Scheibe ändert ausschließlich, **gegen
  welchen Host** die Empfänger-Prüfung läuft, nicht das Retry-Timing.
- **Der Ausweichweg bleibt für bestätigte Empfänger nutzbar.** Eine Störung
  des primären Postausgangs darf nicht dazu führen, dass berechtigte Nutzer
  keine Briefings mehr bekommen (PO-Entscheidung 2026-07-29). Die Prüfung auf
  dem Ersatzweg erlaubt bestätigte Profil-Adressen **oder** lokale
  Zustellung — sie ersetzt die Lokal-Regel nicht, sondern erweitert sie.
- **Lokal-Guard-Ausnahme bleibt dokumentiert bestehen.** Der Nicht-Resend-
  Zweig prüft bewusst nicht gegen `_raw_contains_test_mailbox` (`email.py:
  484-487`) — sonst würde die gewollte lokale Zustellung an
  `gregor-test@`/`gregor-staging@henemm.com` blockiert. Diese Begründung
  wird beim Verschieben in `_dial_and_send` unverändert übernommen.
- **`535`-Text-Erkennung bleibt für echte Auth-Fehler bestehen.** Der neue
  Guard-Fehlertyp in Go **ergänzt** die bestehende Prüfung, ersetzt sie nicht.

## Nachweisplan (Test-Politik: Kern-Schicht)

- **Python (AC-1/AC-2):** Sink am Transportrand auf `smtplib.SMTP` (Vorbild:
  `tests/tdd/test_telegram_test_mode_guard.py:278-303` — Fake-Klasse statt
  echter Verbindung, zeichnet Zustellversuche auf; kombiniert mit dem
  Sentinel-Prinzip aus `tests/tdd/test_telegram_test_isolation.py:78-89` für
  den Blockade-Nachweis: bleibt der Sink stumm, hat der Guard **vor** dem
  Dial entschieden). Aufbau: `EmailOutput` mit echtem `_fallback_host`
  (Stalwart-artig, kein „resend"), Primärhost `self._host` wird künstlich
  zum Scheitern gebracht (z. B. unerreichbarer Primärhost oder erzwungener
  4xx/OSError-Pfad), Empfänger einmal auf dem Fallback-Host unerlaubt
  (AC-1) und einmal auf beiden Wegen erlaubt (AC-2). Kein Mock-Theater,
  keine Dateiinhalt-Checks.
- **Go (AC-3):** Kein Transport-Sink möglich (`net/smtp` nicht patchbar).
  Nachweis über einen minimalen Test-Seam (paketinternes, austauschbares
  Funktions-Handle um den eigentlichen Dial, ausschließlich zu
  Testzwecken) plus Fehlertext-Prüfung — Vorbild für „Fehler kam vor dem
  Dial zurück": `internal/mail/sender_egress_test.go:28-44`. Zusätzlich der
  von der Analyse geforderte **Versuchszähler**: der Seam zählt, wie oft
  tatsächlich zu dialen versucht wurde; AC-3 verlangt exakt 1 (nur der
  primäre, blockierte Versuch), nicht 2.
- **Go (AC-4):** Bestehendes, deterministisches Muster (kein echtes Netz
  nötig): Primär- **und** Fallback-Konfiguration zeigen auf unerreichbare
  lokale Adressen (`127.0.0.1:1` / `127.0.0.1:2`, sofortiger
  Verbindungsfehler, kein Guard-Grund) — die zurückgegebene Fehlermeldung
  muss belegen, dass **beide** Versuche liefen (heutiges Verhalten, Vorbild:
  bestehende `127.0.0.1:1`-Tests in `resend_guard_test.go`/
  `recipient_guard_test.go`).
- **Go (AC-5):** Keine neue Kern-Schicht-Prüfung — der bestehende
  `535`-Textvergleich wird nicht verändert, sein einziger heutiger Nachweis
  bleibt der Live-/Integrationstest `sender_integration_test.go:93-144`
  (Build-Tag `integration`, braucht echte Stalwart-Zugangsdaten). Das ist
  Bestandsverhalten, kein neuer Nachweisbedarf durch diese Scheibe.
- **Namensregel:** neue Dateien nach Verhalten benannt
  (`test_mail_fallback_guard.py`, `fallback_guard_test.go`), nicht nach
  Issue-Nummer.
- **Pfadregel #1409:** Beide neuen Testdateien lösen ihren Prüfling relativ
  zur eigenen Testdatei auf (`Path(__file__).resolve().parents[2]` bzw.
  Go-Standardimport innerhalb desselben Pakets), nie über einen festen
  Hauptrepo-Pfad.

## Betroffene Bestandstests

Geprüft wurde, ob die fünf in der Analyse genannten Python-Guard-Tests
tatsächlich isoliert gegen interne Guard-Funktionen prüfen (dann bräuchten
sie eine Umstellung auf den neuen Aufrufpunkt) — Ergebnis: **alle fünf rufen
ausschließlich die öffentliche `EmailOutput.send()`-Methode auf**, nicht
interne Guard-Funktionen direkt gegen einen fest kodierten Host. Da der
**Primärweg** (`send()` → `_dial_and_send(self._host, …)`) inhaltlich
dieselbe Guard-Entscheidung gegen denselben Host trifft wie heute, bleiben
diese Tests **unverändert grün**, ohne Anpassung:

- `tests/tdd/test_stalwart_recipient_guard.py`
- `tests/tdd/test_resend_recipient_allowlist.py`
- `tests/tdd/test_resend_verified_allowlist.py`
- `tests/tdd/test_issue_1147_resend_recipient_invariant.py`
- `tests/unit/test_no_resend_for_tests.py`

`tests/tdd/test_email_routing_stalwart.py` gehört entgegen der ersten
Einschätzung **nicht** zu den Guard-Tests — die Datei prüft ausschließlich
`Settings.for_testing()`-Feldverhalten, berührt keine Guard-Logik und bleibt
unberührt.

**Tatsächlich betroffen und MUSS geändert werden:**
`internal/mail/recipient_guard_test.go:282-295`
(`TestSendWithFallback_RecipientGuardTriggersFallbackAttempt`) — dieser Test
schreibt das heutige R1-Fehlverhalten wörtlich als gewolltes Verhalten fest
(„daher versucht SendWithFallback automatisch die Fallback-Config"). Er wird
invertiert: neuer Name und neue Assertion, dass **kein** Fallback-Versuch
stattfindet und der zurückgegebene Fehler der reine Guard-Fehler ist.

Alle anderen Go-Tests, die `recipientBlocked`/`resendBlocked`/`Send()`
direkt prüfen (`sender_allowlist_test.go`, `resend_guard_test.go`,
`sender_egress_test.go`), bleiben unverändert grün — sie prüfen die
Guard-Funktionen selbst oder `Send()` für eine einzelne Konfiguration, nicht
`SendWithFallback`s Retry-Entscheidung.

## Randbedingungen

- **Renderer-Commit-Gate #811:** Greift, sobald `src/output/channels/email.py`
  gestaged wird. Vor dem Commit: `uv run pytest
  tests/tdd/test_issue_811_mode_matrix.py` grün **und** ein frischer,
  erfolgreicher `briefing_mail_validator.py`-Lauf gegen Staging.
- **LoC-Ziel:** ~120 (added+deleted), Workflow-Limit 250.
- **Risiko: HOCH.** Produktiver Sicherheitspfad, live genutzter
  Fallback-Weg (Python). Staging-Nachweis vor Prod-Deploy ist Pflicht — ein
  echter Sendeversuch, der bewusst auf den Ersatzweg ausweicht und dort
  einen gesperrten Empfänger korrekt blockiert.

## Known Limitations

- Die Python-Guard-Prüfung liest die Resend-Allowlist jetzt bis zu 4× pro
  `send()`-Aufruf (einmal je Retry-Versuch der Primärschleife) statt einmal
  vorab — nur bei tatsächlichen Wiederholungen relevant, deterministisch im
  Ergebnis, geringfügiger Mehraufwand beim Dateisystemzugriff.
- AC-5 (Go, Auth-Fehler bricht ohne Fallback ab) hat weiterhin nur einen
  Live-/Integrationstest als Nachweis (Build-Tag `integration`,
  Stalwart-Zugangsdaten nötig) — das ist Bestandslage, keine neue Lücke
  durch diese Scheibe.
- S2 (Fall-Tabelle/Parität), S3 (Transport-Kapselung Telegram/SMS), S4
  (Empfängervertrag scharf) und S5 (Go zieht Vertrag nach, ADR) sind
  ausdrücklich nicht Teil dieser Scheibe — sie bekommen eigene Workflows.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neuer Architekturentscheid. Diese Scheibe setzt
  bestehende Entscheidungen konsequent um — ADR-0006 (keine Mocks, Sink
  statt Mock, E2E gegen Staging) und ADR-0015 (Dual-Stack Go+Python bleibt
  bestehen, kein gemeinsamer Code) werden bestätigt, nicht verändert. Ein
  ADR „Empfängerschutz" fehlt zwar grundsätzlich im Bestand, wird aber laut
  Analyse erst mit Scheibe S5 nachgetragen (dort ist der Vertrag über beide
  Sprachen hinweg vollständig).

## Changelog

- 2026-07-29: Initial spec created
