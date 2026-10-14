---
entity_id: fix_1412_s5_go_empfaengerschutz
type: bugfix
created: 2026-10-14
updated: 2026-10-14
status: draft
version: "1.0"
tags: [mail, guard, parity, adr, 1412]
---

# Go zieht den Empfängerschutz nach (S5 — Divergenz D1, Sollwerte C3-20, ADR „Empfängerschutz“)

## Approval

- [ ] Approved

## Purpose

Die Go-API schützt Empfänger heute nur, wenn der Postausgang Resend ist. Läuft derselbe Versand über das lokale Mail-Relay (Stalwart), lässt Go **jede** Adresse durch — Python lässt dort nur `@henemm.com` durch. Das ist die letzte offene Ausnahme (**D1**) im Paritäts-Prüfwerkzeug; ihre Frist läuft am **2026-10-28** ab, danach werden beide Läufer rot. S5 gibt Go auf jedem Nicht-Resend-Postausgang dieselbe Lokalregel wie Python, legt die offenen Sollwerte aus Nebenbefund **C3-20** fest (Python-Guard und Postausgang sehen künftig dieselbe Empfängerliste) und hält die Grundsatzentscheidung als **ADR-0087 „Empfängerschutz“** fest. Für den Betrieb heißt das: Mails an Fremdadressen gehen ausschließlich über Resend an verifizierte Profile; jeder andere Postausgang erreicht nur die eigene Domain.

## Source

| File | Identifier |
|---|---|
| `internal/mail/sender.go` | `recipientBlocked` (D1, Host-Weiche `:387-390`), `splitRecipientField` (C3-20 B), Kommentar bei `SendVerificationMail` (`:579-580`) |
| `internal/handler/auth.go` | Passwort-Reset-Goroutine (`:521-535`, `sendResetMailFn`) |
| `src/output/channels/email.py` | `_normalized_addrs_for_guard` (`:121-174`), Guard-Zweige in `EmailOutput.send` (Resend `:746-805`, Nicht-Resend `:806-844`) |
| `tests/fixtures/mail_recipient_parity/faelle.json` | Ausnahme D1, `ausnahmen_hoechstzahl`, `verzweigungen_go`, neue C3-20-Fälle |
| `docs/adr/0087-empfaengerschutz.md`, `docs/adr/README.md` | neues ADR + Index |

> **Schicht-Hinweis:** Go-API (`internal/`) und Python-Core (`src/output/channels/`). Kein Frontend. Go versendet weder Briefings noch Alerts — betroffen sind nur Passwort-Reset und Tarif-Antrag (beide `Send`/`SendWithFallback`).

## Estimated Scope

- **LoC:** produktiv ca. 60–90 (`sender.go` ~35, `auth.go` ~10, `email.py` ~25, plus Kommentarkorrektur); Tests/Fixtures ca. 100–150; Docs (ADR, Spec-Korrektur, Testköpfe) zählen nicht.
- **Files:** 3 produktive Dateien, `faelle.json`, ca. 6 Go-Bestandstestdateien + 2 neue Testdateien, ADR + Index, S4a-Spec.
- **Effort:** medium. Renderer-Commit-Gate #811 greift, weil `email.py` gestaged wird.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/mail/sender.go::SendWithFallback` / `ErrGuardBlocked` | function | S1: Guard-Block ⇒ kein Fallback; S5 baut darauf auf |
| `internal/mail/sender.go::recipientBlockedForVerification` | function | schon heute host-unabhängig (faktisch Zweck `verification`); S5 hängt deshalb **nicht** an S4b |
| `internal/egress/guard.go` | gate | Staging erlaubt SMTP nur zu `mail.henemm.com`; macht den Google-Weg dort ohnehin tot |
| `tests/test_mail_recipient_parity.py`, `internal/mail/recipient_parity_test.go` | test | Prüfwerkzeug aus S2a; Nachweis für Parität ohne Ausnahmen |
| `.claude/hooks/renderer_mail_gate.py` (#811) | gate | verlangt Modus-Matrix-Test + `briefing_mail_validator.py` gegen echt zugestellte Staging-Mail |
| `docs/specs/modules/fix_1412_s1_guard_am_echten_postausgang.md`, `…_s2a_…`, `…_s2b_…`, `…_s4a_…` | spec | Vorgänger; S1 verwies das ADR an S5 |

## Implementation Details

### 1. D1: eine Regel für jeden Nicht-Resend-Postausgang (Variante A′)

`recipientBlocked(host, to)` in `sender.go`:

- **Resend-Host** (`host` enthält „resend“): unverändert — Fangnetz `rawContainsTestMailbox`, Allowlist verifizierter Profile, Betreiber-Adresse.
- **Jeder andere Host** (Stalwart, Google, künftige): die **Python-Lokalregel**. Pro Empfänger-Kandidat aus `splitRecipientField`:
  - Kandidat ohne `@` (oder leer) ⇒ block;
  - Domain = Teil nach dem **letzten** `@`, lowercase, `rstrip(".")`; ist sie reserviert (`isReservedTestDomain`) ⇒ block;
  - Domain ist nicht exakt `henemm.com` ⇒ block;
  - `len(parts)==0` ⇒ block; sonst allow.
- Fangnetz `rawContainsTestMailbox` ist auf dem Nicht-Resend-Zweig **bewusst aus** (sonst wäre `gregor-test@`/`gregor-staging@henemm.com` nicht mehr lokal zustellbar — wie in Python, `email.py:807-817`).
- Ein Block liefert `ErrGuardBlocked` mit klarem Fehlertext und Logzeile (Host, Anzahl, maskierte Empfänger über `maskAddrForLog`). `SendWithFallback` bricht dann ohne zweiten Versuch ab (S1).
- **Keine Google-Ausnahme.** Begründung: kein belegter Bedarf (Test-/Wegwerf-Konten nutzen `gregor-test+…@henemm.com`), Hostname-Raten (`"google"` im Host) wäre eine ungeprüfte Lockerung und eine Go-only-Divergenz, auf Staging ist der Google-Weg per Egress-Wächter ohnehin gesperrt. Fail-closed: jeder unbekannte Host bekommt die strengste Regel.
- Die Lokalregel kommt in eine eigene kleine Funktion; liegt sie außerhalb der `guardRegionFuncs` des Go-Läufers (`recipient_parity_test.go:346-354`), wird sie dort aufgenommen — die Ratsche muss die neue Entscheidungsfläche mitzählen.

Kommentar bei `SendVerificationMail` („genau EIN … Aufrufer“) wird korrigiert: es sind vier Aufrufer (Verifikations-Mail im Profil, Magic-Link, Google-Hinweis, Lösch-Code).

### 2. Passwort-Reset: sichtbar blocken, nach außen unverändert

`auth.go`, Reset-Goroutine: liefert `sendResetMailFn` einen Fehler mit `errors.Is(err, mail.ErrGuardBlocked)`, schreibt sie **eine eigene, eindeutig auffindbare Logzeile** (fester Marker `password reset: Empfängerschutz hat Versand blockiert`, Host-Klasse resend/lokal/andere, Hinweis „kein Fallback“). **Kein Klartext-Empfänger, kein Benutzername** in dieser Zeile. Die HTTP-Antwort bleibt in jedem Fall `{"status":"ok"}` (Anti-Enumeration — ein Angreifer erfährt nicht, ob ein Konto existiert oder die Adresse gesperrt ist).

Wirkung: Auf Staging (Primärweg Stalwart) wird ein Reset an eine Fremdadresse geblockt — gewollt. In Prod ändert sich im Normalbetrieb **nichts**: `GZ_SMTP_HOST=smtp.resend.com`, `GZ_FALLBACK_SMTP_HOST` nicht gesetzt. Die neue Regel greift dort nur, falls jemand Host oder Fallback auf Stalwart stellt — genau dafür ist sie da.

### 3. C3-20: Sollwerte und Python-Mechanik

Ist-Verhalten (gelesen am Code und mit Python 3.12.3 gemessen; Go-Seite aus `splitRecipientField`/`recipientBlocked` abgeleitet, vom Go-Läufer zu bestätigen):

| Fall | Eingabe | Go heute Resend / Stalwart | Python heute Resend / Stalwart | **Soll (beide Seiten, beide Hosts)** |
|---|---|---|---|---|
| A | `a@henemm.com, garbage` | block / **allow** (D1) | **allow** / **allow** (Guard verwirft das Fragment `garbage`, der Postausgang bekommt es trotzdem) | **block / block** |
| B | `a@henemm.com garbage` (ohne Komma) | allow¹ / allow | block / block (Python liest `a@henemm.comgarbage`) | **block / block** (Entscheid Q1) |
| C | `"x y"@henemm.com` | block / allow | block / allow | **Resend block, Stalwart allow** (unverändert, nur festnageln) |
| Z1 | `Nachname, Vorname <a@henemm.com>` (ungequotet) | block / allow (D1) | **allow** / **allow** | **block / block** |
| Z2 | `"Nachname, Vorname" <a@henemm.com>` (gequotet) | allow¹ / allow | allow¹ / allow | **allow / allow** (D2 aus S2b, festnageln) |

¹ vorausgesetzt, `a@henemm.com` steht in der Allowlist des Fixture-Nutzers; auf Stalwart gilt „lokal“.

**Abweichung vom Analyse-Stand (wichtig):** Die Analyse ging davon aus, dass Fall B auf beiden Seiten heute `allow` ist. Gemessen ist das nicht so: Pythons `getaddresses` klebt `a@henemm.com garbage` zu `a@henemm.comgarbage`, die Domain ist dann nicht lokal und nicht in der Allowlist ⇒ Python blockt. Go extrahiert dagegen im Whitespace-Fallback `a@henemm.com` und lässt durch (so auch in der S2b-Spec, Known Limitation 2, vermerkt). „B ⇒ allow, nur festnageln“ ist deshalb ohne Verbreiterung des Python-Guards nicht erreichbar. Entschieden als Q1 (Tech Lead, 2026-10-14): **block**.

**Python-Mechanik für A und Z1 (Entscheidung):** Der Guard bewertet die **quote-bewusste Hauptliste** — `getaddresses([recipient])` über das ganze Feld, also dieselbe Zerlegung, die der Postausgang (RFC-Parser) tatsächlich sieht. Enthält diese Liste einen Eintrag mit **nicht-leerer Adresse ohne `@`** (`garbage`, `Nachname`), ist der **gesamte Versand blockiert** (fail-closed, beide Zweige: Resend und Nicht-Resend). Die zusätzlichen Fragment-Strategien in `_normalized_addrs_for_guard` (Trennzeichen-Split, Whitespace-Split) bleiben unverändert als zusätzliches Netz für Test-Postfächer und Domains; ihre `@`-losen Fragmente werden weiterhin verworfen, sie dürfen also nicht blockieren.

Begründung der Wahl:
- Kleinste Wirkfläche: Eine gequotete Form wie `"Nachname, Vorname" <a@henemm.com>` oder `"Foo; Bar" <addr>` erzeugt in der Hauptliste **keinen** `@`-losen Eintrag (sie wird als EINE Adresse aufgelöst), bleibt also erlaubt — Parität zu Go (`ParseAddressList` vor dem Split, S2b D2). Ein blindes „jedes `@`-lose Fragment aus allen Strategien ⇒ block“ würde diese legitimen Formen sprengen, weil die Fragment-Strategien bei Quotes mit Komma/Semikolon gerade solche Reste erzeugen (`email.py:145-146`).
- „Guard und Postausgang auf dieselbe Liste“ als Umbau (Empfängerliste vor dem Versand neu schreiben) hätte eine deutlich größere Wirkfläche: `server.sendmail` bekommt die Liste unverändert (`email.py:543`), jeder Aufrufer müsste mitgeprüft werden. Das Blocken bei Abweichung erreicht dasselbe Schutzziel (nichts geht an einen Empfänger, den der Guard nicht gesehen hat), ohne den Versandweg anzufassen.
- Entspricht dem Go-Verhalten: dort bleibt ein `@`-loser Rest im Fallback-Split als Kandidat stehen und blockt.

### 4. Falltabelle und Ratsche

`tests/fixtures/mail_recipient_parity/faelle.json`: Ausnahme D1 entfernen; `ausnahmen_hoechstzahl` 1 → 0; die Fälle A, B, C, Z1, Z2 **je Host** (`mail.henemm.com` und Resend-Host) aufnehmen; `verzweigungen_go` (und falls sich die Python-Region ändert, `verzweigungen_python`) auf den vom Läufer genannten **exakten** Wert setzen. Läufer-Code ändert sich nur, falls eine neue Fallform es verlangt.

### 5. Bestandstests umstellen (nicht löschen)

Go-Tests mit `Host: "127.0.0.1"`, die „Stalwart ungeschützt“ festnageln, drehen ihr Soll: Fremdadresse ⇒ `ErrGuardBlocked`, `@henemm.com` ⇒ erlaubt. Betroffen (Zeilen aus der Analyse, vor der Umstellung am Stand prüfen): `sender_allowlist_test.go:141` (`TestRecipientBlocked_StalwartHostGuardInactive`), `recipient_guard_test.go:102`, `resend_guard_test.go:100`, `fallback_guard_test.go:66`, `sender_egress_test.go:56` (prüfen), `sender_integration_test.go:55` (Tag `integration`, prüfen). Jeder umgestellte Test bekommt eine **Gegenprobe**: Mutation „Nicht-Resend-Zweig gibt wieder `nil`“ muss genau diese Tests namentlich rot machen.

### 6. Dokumentation

- **Fünf Testköpfe** mit toten Spec-Verweisen auf `docs/specs/_archive/modules/…` umstellen: `sender_allowlist_test.go:12`, `recipient_guard_test.go:9`, `resend_guard_test.go:12`, `sender_verified_allowlist_test.go:6`, `verify_send_test.go:9`.
- **S4a-Spec** `fix_1412_s4a_empfaengervertrag_telegram.md:271-275`: Known Limitation „PUT-Profil nimmt `telegram_chat_id` als Freitext“ ist veraltet. Neu: seit #2141 übernimmt `PUT /api/auth/profile` nur den Leerstring („Telegram trennen“); gesetzt wird die `chat_id` ausschließlich über den Einmal-Token-Flow `/start TOKEN` → `PostTelegramConnectHandler` (`telegram_connect.go`).
- **ADR-0087** `docs/adr/0087-empfaengerschutz.md` (Nummer geprüft: höchste vorhandene ist 0086) + Zeile im Index `docs/adr/README.md`. Inhalt: (a) Grundsatz — Fremdadressen nur über Resend + verifizierte Allowlist, jeder andere Postausgang nur eigene Domain, reservierte Test-Domains immer gesperrt, Entscheidung am **tatsächlich benutzten** Postausgang (S1); (b) Zwecke `user_profile`, `inbound_reply`, `verification` (Go faktisch via `recipientBlockedForVerification`, host-unabhängig); (c) Fangnetz Test-Postfach nur auf Resend; (d) C3-20-Sollwerte; (e) Telegram-`chat_id` nur über Einmal-Token-Flow (#2141); (f) Go versendet keine Briefings/Alerts; (g) Paritäts-Prüfwerkzeug als Wächter (Python + Go gegen gemeinsame Sollwerte, Ausnahmen mit Frist, Höchstzahl 0).

### 7. Renderer-Commit-Gate #811

`email.py` wird gestaged ⇒ vor dem Commit beide Nachweise frisch: `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün **und** `briefing_mail_validator.py` gegen eine echt zugestellte Staging-Mail (nach dem Stagen, mit gesetzter Workflow-Kennung).

## Expected Behavior

- **Input:** Empfängerfeld eines Mail-Versands (Go: Passwort-Reset, Tarif-Antrag; Python: Briefing/Alert) und der benutzte Postausgang (Resend oder anderer Host).
- **Output:** Resend: unverändert. Anderer Host: nur `@henemm.com` (auch mit abschließendem Punkt) kommt durch; Fremdadressen, reservierte Test-Domains und `@`-lose Empfängerreste werden mit `ErrGuardBlocked` (Go) bzw. `OutputConfigError` (Python) geblockt, ohne Fallback-Versuch.
- **Side effects:** Auf Staging werden Reset-Mails an Fremdadressen nicht mehr zugestellt (gewollt); der Block steht als Logzeile im Journal. Prod-Normalbetrieb unverändert.

## Acceptance Criteria

- **AC-1:** Stalwart: Fremdadresse block — Given der Postausgang ist nicht Resend (z. B. das lokale Mail-Relay `mail.henemm.com`) / When die Go-API eine Mail an eine Fremdadresse wie `fremd@gmail.com` versenden soll / Then wird der Versand mit `ErrGuardBlocked` abgelehnt und es verlässt keine Mail den Server — wie auf dem Python-Sendeweg schon heute.
  - Test: Falltabellen-Fall `D1` (`soll=block`) ist im Go-Läufer **ohne Ausnahme** grün; Go-Kerntest ruft `recipientBlocked` für Host-Klassen Stalwart und `127.0.0.1` mit zwei verschiedenen Fremdadressen auf.

- **AC-2:** Stalwart: eigene Domain allow, auch mit Endpunkt — Given derselbe nicht-Resend-Postausgang / When die Mail an `henning@henemm.com`, `GREGOR-Test@HENEMM.COM` oder `henning@henemm.com.` (abschließender Punkt, Fall N2b) geht / Then kommt der Empfänger durch — Groß-/Kleinschreibung und Endpunkt ändern nichts.
  - Test: Fall `N2b` bleibt in beiden Läufern `soll=allow` ohne Ausnahme; Gegenprobe (Entfernen von `rstrip(".")` in der neuen Lokalregel) macht genau `N2b` im Go-Läufer namentlich rot.

- **AC-3:** reservierte Test-Domains block — Given ein nicht-Resend-Postausgang / When der Empfänger auf einer reservierten Testdomäne liegt (`x@example.com`, `x@sub.example.org`, `x@foo.test`, `x@localhost`) / Then wird der Versand geblockt, auch wenn die Adresse sonst formal gültig ist.
  - Test: Go-Kerntest je Domainform; Gegenprobe (Reserved-Prüfung in der Lokalregel entfernen) macht diese Tests rot. Die Domain `henemm.com` selbst wird dadurch nicht gesperrt.

- **AC-4:** Resend-Zweig unverändert — Given der Postausgang ist Resend / When Mails an verifizierte Profil-Adressen, an Test-Postfächer (`gregor-test@`, `gregor-staging@henemm.com`) und an unverifizierte Adressen gehen / Then gilt exakt das bisherige Verhalten: nur Allowlist-Adressen und die Betreiber-Adresse kommen durch, Test-Postfächer sind über das Fangnetz gesperrt.
  - Test: alle bestehenden Resend-Tests (`recipient_guard_test.go`, `sender_allowlist_test.go`, `sender_verified_allowlist_test.go`, `resend_guard_test.go`) bleiben ohne inhaltliche Änderung grün; die Resend-Fälle der Falltabelle sind unverändert.

- **AC-5:** Test-Postfach auf lokalem Relay bleibt zustellbar — Given ein nicht-Resend-Postausgang / When die Mail an `gregor-test@henemm.com` oder `gregor-test+abc@henemm.com` geht / Then kommt sie durch, weil das Fangnetz auf diesem Zweig bewusst aus ist — nur so erreicht ein Wegwerf-Konto das Stalwart-Testpostfach.
  - Test: Go-Kerntest je Adresse (zwei verschiedene Plus-Zusätze); Gegenprobe (Fangnetz im Nicht-Resend-Zweig einschalten) macht ihn rot.

- **AC-6:** kein Fallback nach Block — Given der Primärweg blockt die Mail per Empfängerschutz und ein Ersatz-Postausgang ist konfiguriert / When `SendWithFallback` aufgerufen wird / Then wird kein zweiter Versand über den Ersatzweg versucht und derselbe Fehler (`ErrGuardBlocked`) kommt zurück.
  - Test: Go-Kerntest mit lokalem Fallback-Host und einem zählenden SMTP-Sink (echter lokaler Listener, kein Mock des Prüflings): Sink zählt 0 Verbindungen nach Block einer Fremdadresse.

- **AC-7:** Reset: sichtbare Logzeile, Antwort bleibt „ok“ — Given ein Konto mit Fremdadresse als Empfänger und ein nicht-Resend-Postausgang / When jemand „Passwort vergessen“ für dieses Konto auslöst / Then antwortet die API unverändert `{"status":"ok"}` (HTTP 200, identisch zur Antwort für ein unbekanntes Konto), schreibt aber genau eine eindeutige Logzeile „Empfängerschutz hat Versand blockiert“ ohne Klartext-Empfänger und ohne Benutzername, und versendet nichts.
  - Test: Go-Handlertest mit zwei verschiedenen Nutzern (Fremdadresse und `@henemm.com`): Antwortkörper beider Fälle ist bytegleich; Log enthält den Marker nur im Blockfall und weder `@` noch Benutzernamen; Gegenprobe (Logzeile entfernt) lässt den Test rot werden.

- **AC-8:** C3-20 A — `a@henemm.com, garbage` — Given ein Empfängerfeld mit einer gültigen Adresse und einem angehängten Textrest hinter dem Komma / When der Guard auf Python- oder Go-Seite, auf Resend- oder Nicht-Resend-Postausgang prüft / Then wird der gesamte Versand geblockt.
  - Test: Falltabellen-Fall `C3-20-A` je Host (zwei Fälle), `soll=block`, beide Läufer ohne Ausnahme; Gegenprobe (Python-Hauptlisten-Prüfung entfernen) macht genau die Python-Läufer-Fälle `C3-20-A` rot.

- **AC-9:** C3-20 B — `a@henemm.com garbage` — Given ein Empfängerfeld mit einer gültigen Adresse und einem durch Leerzeichen (ohne Komma) angehängten Textrest / When der Guard auf beiden Seiten und beiden Hosts prüft / Then entscheiden Python und Go **gleich** `block` (fail-closed; so liest auch der Postausgang das Feld, nämlich als `a@henemm.comgarbage`).
  - Test: Falltabellen-Fall `C3-20-B` je Host, Soll `block`, beide Läufer ohne Ausnahme; Gegenprobe zeigt, dass die Fälle den Whitespace-Zweig von `splitRecipientField` (Go) bzw. die Hauptliste (Python) bewachen.

- **AC-10:** C3-20 C — gequoteter Local-Part — Given die Adresse `"x y"@henemm.com` / When sie geprüft wird / Then ist sie auf dem Resend-Postausgang geblockt (kein Allowlist-Eintrag) und auf dem lokalen Relay erlaubt (Domain `henemm.com`) — auf Python- und Go-Seite gleich.
  - Test: Falltabellen-Fall `C3-20-C` je Host, `soll=block` (Resend) bzw. `soll=allow` (Stalwart), beide Läufer ohne Ausnahme.

- **AC-11:** C3-20 Zusatz — Anzeigename mit Komma — Given `Nachname, Vorname <a@henemm.com>` ohne Anführungszeichen / When geprüft wird / Then wird der Versand auf beiden Seiten und beiden Hosts geblockt (der Name wird sonst als eigener Empfänger gelesen); die gequotete Form `"Nachname, Vorname" <a@henemm.com>` kommt dagegen durch.
  - Test: Falltabellen-Fälle `C3-20-Z1` (`block`) und `C3-20-Z2` (`allow`) je Host; Z2 entspricht dem bereits bestehenden Fall `D2` und darf durch die Python-Änderung nicht kippen.

- **AC-12:** Parität ohne Ausnahmen — Given alle Änderungen dieser Scheibe / When beide Paritäts-Läufer (Python und Go) gegen `faelle.json` laufen / Then enthält die Falltabelle **keine** Ausnahme mehr, `ausnahmen_hoechstzahl` steht auf 0, und `verzweigungen_go` (sowie ggf. `verzweigungen_python`) nennt den exakten neuen Wert.
  - Test: `test_ausnahmen_deckel_im_ausgelieferten_stand_nicht_ueberschritten` und die Verzweigungsratschen beider Sprachen grün; Gegenprobe: Wiedereinfügen der Ausnahme D1 oder Zurücksetzen der Lokalregel lässt den Läufer namentlich auf `D1` rot werden.

- **AC-13:** Bestandstests umgestellt, nicht gelöscht — Given die Go-Tests, die bisher „Stalwart ungeschützt“ festnagelten / When Fremdadresse und `@henemm.com` gegen den lokalen Host geprüft werden / Then erwarten sie jetzt Block bzw. Allow, und keiner dieser Tests wurde ersatzlos entfernt.
  - Test: `go test ./internal/mail/...` grün; Mutation „Nicht-Resend-Zweig liefert wieder `nil`“ lässt namentlich `TestRecipientBlocked_StalwartHost…` (umbenannt nach Verhalten) und die Fremdadress-Fälle in `recipient_guard_test.go`/`resend_guard_test.go`/`fallback_guard_test.go` rot werden.

- **AC-14:** Dokumentation lebt — Given der Merge dieser Scheibe / When man `docs/adr/` und die fünf Go-Testköpfe öffnet / Then existiert `docs/adr/0087-empfaengerschutz.md` mit Status „Akzeptiert“ und den Inhalten (a)–(g), der Index `docs/adr/README.md` führt ihn, die fünf Testköpfe verweisen auf existierende Spec-Dateien, die S4a-Spec nennt den Einmal-Token-Flow statt des Freitext-PUT, und der Kommentar bei `SendVerificationMail` nennt vier Aufrufer.
  - Test: `tests/test_adr_index_drift.py` grün (Index↔Datei); Testköpfe: ein Kerntest löst jeden in den fünf Köpfen genannten Spec-Pfad auf und verlangt, dass die Datei existiert.

- **AC-15:** Staging-Nachweis — Given der Stand ist auf Staging ausgeliefert (Primärweg Stalwart) / When ein normales Staging-Konto (ohne Testflag) mit einer Fremdadresse einen Passwort-Reset auslöst / Then antwortet die API `ok`, `journalctl -u gregor-api-staging` zeigt die Block-Logzeile aus AC-7, und im Stalwart-Testpostfach kommt nichts an; Gegenprobe: ein Wegwerf-Konto `gregor-test+abc123@henemm.com` löst denselben Reset aus und die Reset-Mail erscheint im Stalwart-Testpostfach (IMAP).
  - Test: Live-Schicht (`/e2e-verify`), zwei verschiedene Nutzer; PASS nur mit beiden Hälften. Ist das Journal nicht lesbar oder das Testpostfach nicht erreichbar, lautet das Urteil `NOT_MEASURABLE_ON_STAGING`, nie PASS.

## Test Plan

- **Kern-Schicht (deterministisch, offline, keine Mocks des Prüflings, keine Dateiinhalt-Checks):** neue Dateien nach Verhalten benannt — `internal/mail/recipient_guard_nonresend_test.go` (AC-1 bis AC-6, AC-8 bis AC-11 auf Go-Seite), `internal/handler/password_reset_guard_blocked_test.go` (AC-7, zwei Nutzer), `tests/test_email_guard_recipient_list.py` (AC-8, AC-9, AC-11 Python-Seite: Guard blockt `@`-lose Hauptlisten-Einträge, gequotete Formen bleiben erlaubt). Die Paritäts-Läufer beider Sprachen decken AC-12 ab. Nur benannte Testdateien, `--disable-socket` für Python. SMTP-Sink für AC-6 ist ein echter lokaler Listener.
- **Live-Schicht:** AC-15 über `/e2e-verify` gegen Staging.
- **Mutations-Gegenprobe (Pflicht für den Adversary):** Nicht-Resend-Zweig wieder `nil`; `rstrip(".")` entfernt; Reserved-Prüfung entfernt; Fangnetz auf Nicht-Resend eingeschaltet; Python-Hauptlisten-Prüfung entfernt; `ErrGuardBlocked` durch einfachen Fehler ersetzt (Fallback würde feuern); Logzeile entfernt. Jede Mutation muss einen **benannten** Test rot machen.

## Known Limitations

1. **Staging-Resets an Fremdadressen werden geblockt.** Gewollt. Wer auf Staging eine echte Reset-Mail braucht, nimmt ein Wegwerf-Konto `gregor-test+…@henemm.com`.
2. **Google-SMTP-Weg:** Test-Konten über `GZ_GOOGLE_SMTP_HOST` erreichen künftig ebenfalls nur `@henemm.com`. Rückbau des Google-Wegs ist nicht Teil dieser Scheibe.
3. **Prod unverändert, solange Resend Primärweg ist.** Fällt Resend aus und ist ein Stalwart-Fallback gesetzt (heute nicht), werden Resets an Fremdadressen geblockt und nur über die Logzeile sichtbar — nach außen bleibt es `ok`.
4. Die aus S2a geerbten Grenzen des Prüfwerkzeugs gelten unverändert (siehe `fix_1412_s2a_regelwerk_paritaet.md`).

## Entschiedene Fragen

- **Q1 (Fall B, `a@henemm.com garbage`) — entschieden: block (Tech Lead, 2026-10-14):** Der Analyse-Sollwert „allow, beide Seiten heute gleich“ stimmt mit dem Code nicht überein (Go `allow`, Python `block`, siehe Tabelle). Zwei Wege: **(1) block** — Go ändert nur den Whitespace-Fallback in `splitRecipientField`: enthält ein durch Leerzeichen getrenntes Fragment ein Feld ohne `@`, bleibt das ganze Fragment als Kandidat stehen und blockt; Python bleibt unverändert, Wirkfläche klein, fail-closed, entspricht dem, was der Postausgang tatsächlich als Empfänger liest. Preis: ungequotete Namen wie `Max Mustermann a@b.de` (ohne `<>`) werden geblockt. **(2) allow** — Python müsste `a@henemm.comgarbage` wieder in `a@henemm.com` + `garbage` zerlegen, also die Hauptliste gezielt lockern; verbreitert die erlaubte Menge und öffnet genau den Guard-/Postausgang-Unterschied, den Fall A schließt. Entscheid: Variante (1) — fail-closed, kleinste Wirkfläche, deckt sich mit der Leitlinie „im Zweifel blocken“ der Analyse; der Preis (ungequotete Namen ohne `<>` werden geblockt) ist sichtbar statt still, weil ein Block eine Logzeile erzeugt.

## Out of Scope

- **S4b** (Zweck `verification` als benannter Python-Begriff). S5 hängt nicht daran.
- **Prod-Konfiguration** (`/etc/gregor/mail-prod.env`, Fallback-Host setzen oder nicht).
- **Rückbau des Google-SMTP-Wegs** und der Test-Konto-Sonderbehandlung.
- Tarif-Antrag (geht an `gregor_zwanzig@henemm.com`, lokal, unberührt) und die vier Verifikations-Mail-Aufrufer (`SendVerificationMail`, schon host-unabhängig).

## Risks

- **Staging-Verhalten ändert sich** (Reset an Fremdadressen dort geblockt) — gewollt und über AC-15 nachgewiesen.
- **Prod unverändert:** Resend-Zweig bleibt wortgleich, `GZ_FALLBACK_SMTP_HOST` ist nicht gesetzt; kein Normalbetriebs-Effekt.
- **Python-Guard strenger bei Fall A/Z1:** Empfängerfelder mit `@`-losen Resten wurden bisher still durchgelassen und gehen künftig nicht mehr raus. Betrifft nur kaputt eingegebene Felder; gequotete Formen bleiben erlaubt (AC-11). Renderer-Commit-Gate #811 ist Pflicht.
- **Ratsche zählt neu:** `verzweigungen_go`/`_python` ändern sich; der Läufer nennt den Sollwert selbst. Liegt die neue Lokalregel-Funktion außerhalb von `guardRegionFuncs`, würde die Ratsche sie nicht sehen — daher Aufnahme (Abschnitt 1).
- **Fünf, nicht vier** Testköpfe tragen tote Spec-Verweise.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0087 (neu, `docs/adr/0087-empfaengerschutz.md`)
- **Rationale:** Der Empfängerschutz ist seit S1 bis S5 über mehrere Scheiben gewachsen und gilt in zwei Sprachen und mehreren Postausgängen. Die Grundsatzregel (Fremdadressen nur Resend + Allowlist, sonst nur eigene Domain, Entscheidung am tatsächlichen Postausgang, Paritätswächter) ist eine Entscheidungsfläche im Sinne der ADR-Pflicht und muss dokumentiert sein, damit sie nicht still rückgängig gemacht wird.

## Changelog

- 2026-10-14: Initial spec created (S5, aus `docs/context/feat-1412-s5-go-empfaengerschutz.md`). Abweichung vom Context: Fall B Ist gemessen (Go allow / Python block), Soll als Q1 vom Tech Lead auf block entschieden.
