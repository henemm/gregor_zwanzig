---
entity_id: fix_1219_resend_allowlist
type: bugfix
created: 2026-07-10
updated: 2026-07-10
status: draft
version: "1.0"
tags: [mail, security, resend, allowlist]
workflow: fix-1219-resend-allowlist
---

<!-- Issue #1219 — Positive Empfänger-Allowlist für Resend-Versand -->

# Fix #1219 — Positive Empfänger-Allowlist für Resend-Versand

## Approval

- [x] Approved (PO, 2026-07-10)

## Purpose

Über Resend darf künftig **nur** an E-Mail-Adressen zugestellt werden, die zu einem
**angelegten, echten Nutzerkonto** gehören (Union aus `mail_to` + `email` über alle
Profile in `data/users/<id>/user.json`, exklusive Test-Nutzer). Das ersetzt die
heutige 2-Adressen-**Denylist** (nur `gregor-test@`/`gregor-staging@henemm.com`
werden ausgeschlossen, alles andere geht durch) durch eine echte **Allowlist**
(nur bekannte, echte Empfänger dürfen durch, alles andere wird hart abgewiesen).
Grund: wiederholt sind Test-Mails über Resend an reale Fremdadressen rausgegangen,
weil die Denylist jede nicht explizit gesperrte Adresse akzeptiert hat.

## Source

- **File:** `src/output/channels/email.py` — Empfänger-Guard `EmailOutput.send()` @313
  (Python-Core, `src/output/`). NEU: `_load_resend_allowlist(data_dir="data") -> frozenset[str]`
  in dieser Datei, importiert `is_test_user_id` aus `src/app/config.py`.
- **File:** `internal/mail/sender.go` — `recipientBlocked()` @169, aufgerufen aus `Send()` @195
  (Go-API, `internal/`). NEU: `loadResendAllowlist(dataDir string) map[string]bool` in dieser
  Datei, nutzt bestehendes `IsTestUser()` @46.

> Beide Chokepoints sind unabhängige Sende-Implementierungen ohne gemeinsamen
> `resolve_recipients()`. Symmetrie zwischen Python und Go ist Pflicht — beide
> müssen für dieselbe Eingabe dasselbe Verdikt liefern.

## Estimated Scope

- **LoC:** ~+120 / -30
- **Files:** 4 (`src/output/channels/email.py` MODIFY, `internal/mail/sender.go` MODIFY,
  je eine neue Testdatei Python + Go CREATE)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `is_test_user_id()` (`src/app/config.py:30`) | function | Test-User-Ausschluss aus der Allowlist (Python) |
| `IsTestUser()` (`internal/mail/sender.go:46`) | function | Test-User-Ausschluss aus der Allowlist (Go) |
| `_normalized_addrs_for_guard()` / `_extract_addr()` (`src/output/channels/email.py:41,58`) | function | Adress-Normalisierung (parseaddr, lowercase, plus-Kappung) — wird für Allowlist-Abgleich wiederverwendet |
| `normalizedAddrForGuard()` (`internal/mail/sender.go:107`) | function | Go-Pendant zur Adress-Normalisierung |
| `splitRecipientField()` (`internal/mail/sender.go:132`) | function | Zerlegt Empfänger-Rohstring an Komma/Semikolon vor Normalisierung (Go) |
| `data/users/<id>/user.json` | data | Quelle der echten Empfängeradressen (`mail_to`, `email`) |
| Safe-Send-Trias #1122/#1147/#1148 | feature | Bestehende Guard-Infrastruktur, auf der dieser Fix aufbaut — Resend-Erkennung (`"resend" in host`), Dial-Reihenfolge, Bash-Hook bleiben unverändert |

## Implementation Details

### Allowlist-Aufbau (beide Sprachen)

Neue Funktion `_load_resend_allowlist()` (Python, in `email.py`) bzw.
`loadResendAllowlist()` (Go, in `sender.go`):

1. Alle Verzeichnisse unter `data/users/` einlesen (`os.listdir` / `os.ReadDir`).
2. Pro Verzeichnis: User-ID = Verzeichnisname. Ist `is_test_user_id(user_id)` /
   `IsTestUser(userID)` `True` → Verzeichnis überspringen (konservativ: im
   Zweifel als Test behandeln → nicht in Allowlist → über Resend blockiert).
3. `user.json` laden, Felder `mail_to` und `email` lesen. Leere/fehlende Felder
   überspringen (kein leerer String in der Allowlist).
4. Jede gefundene Adresse normalisieren (siehe unten) und in ein Set/`frozenset`
   bzw. `map[string]bool` aufnehmen.
5. Fail-soft: fehlende/kaputte `user.json` → Verzeichnis überspringen, kein Crash
   des Sendepfads.

### Guard-Inversion an den Chokepoints

- **Python** (`email.py` @313, aktueller Block prüft `TEST_MAILBOXES`-Treffer):
  Block wird umgebaut auf Allowlist-Prüfung mittels `_load_resend_allowlist()`.
  Bedingung `"resend" in (self._host or "").lower()` bleibt unverändert
  (Wirkungsbereich-Gate). Für jeden normalisierten Empfänger
  (`_normalized_addrs_for_guard(r)`): ist die normalisierte Adresse NICHT in der
  geladenen Allowlist → Treffer → `OutputConfigError` VOR
  `build_mime_message()`/Dial, mit Log-Eintrag (Empfänger maskiert, z.B. nur
  Domain oder Hash — kein Klartext-Leak ins Log).
- **Go** (`sender.go`, `recipientBlocked()` @169): gleiche Struktur mittels
  `loadResendAllowlist()`. Nach dem bestehenden `"resend" in host`-Gate wird
  `splitRecipientField(to)` + je Teil `normalizedAddrForGuard(part)` gegen die
  geladene Allowlist geprüft (statt `testMailboxes[...]`). Kein Treffer in der
  Allowlist → `fmt.Errorf` VOR `Send()`s SMTP-Dial, mit `log`-Eintrag (Empfänger
  maskiert).
- Beide Guards behalten die bestehende Reihenfolge bei: Empfänger-Guard läuft
  VOR dem SMTP-Dial (Python: vor `build_mime_message`/`smtplib.SMTP(...)`; Go:
  vor `smtp.SendMail` in `Send()`).

### Adress-Normalisierung (Symmetrie Python↔Go)

- Python: `_extract_addr()` (parseaddr) + `.lower()` + `.strip()`, analog zur
  bestehenden `_normalize_addr_for_guard()`-Pipeline — sowohl für Allowlist-
  Einträge (aus `user.json`) als auch für den zu prüfenden Empfänger.
- Go: `mail.ParseAddress` + `strings.ToLower(strings.TrimSpace(...))`, analog
  zur bestehenden `normalizedAddrForGuard()` — für Allowlist-Einträge (aus
  `user.json`) und den zu prüfenden Empfänger identisch angewendet.
- Damit werden Whitespace-/Casing-Umgehungen (vgl. #1152) auf beiden Seiten
  gleich behandelt: `" Henning@HENEMM.com "` normalisiert zu
  `henning@henemm.com` und matcht den Allowlist-Eintrag `henning@henemm.com`.
- Plus-Adressierungs-Kappung (`+foo`) wird NICHT auf Allowlist-Einträge
  angewendet (echte Nutzeradressen werden 1:1 verglichen) — nur die bestehende
  Normalisierungskette (parseaddr/ParseAddress + lowercase/trim) ist Pflicht.

### Ablösung der Denylist

- `TEST_MAILBOXES` (Python `email.py:27`) / `testMailboxes` (Go `sender.go:73`)
  werden durch den Allowlist-Loader ersetzt bzw. funktional absorbiert: die
  beiden Test-Postfächer (`gregor-test@`, `gregor-staging@henemm.com`) gehören
  zu keinem echten (Nicht-Test-)Nutzerprofil und tauchen daher in der Allowlist
  nicht auf → über Resend weiterhin blockiert. Über Stalwart (`mail.henemm.com`)
  bleiben sie unverändert erreichbar, da der Guard dort inaktiv ist.
- Die rohen Fangnetz-Scans (`_raw_contains_test_mailbox` / `rawContainsTestMailbox`,
  Fix-Loop 4 / F005) werden NICHT entfernt — sie bleiben als zusätzliche
  Absicherung gegen Parser-Umgehungen bestehen, laufen aber nur noch ergänzend
  zur Allowlist-Prüfung (kein Ersatz für sie).

### Bekannte Grenzen

- Eine Bestätigungsmail an eine **noch nicht angelegte** Adresse (z.B. bei
  Neuregistrierung) würde blockiert, da kein Nutzerprofil existiert. Aktuell
  ist kein solcher Flow aktiv — Passwort-Reset und Magic-Link senden ausschließlich
  an bereits existierende Nutzer (`auth.go:212`, `auth_magic.go`). Falls ein
  Registrierungs-Bestätigungs-Flow später eingeführt wird, muss der Nutzer VOR
  dem Mailversand angelegt sein.
- `admin` hat kein `mail_to`/`email` gesetzt → erhält über Resend keine Mail
  (korrektes Verhalten, da kein Empfänger konfiguriert ist).

## Expected Behavior

- **Input:** Sendeaufruf mit Ziel-Host + einem oder mehreren Empfängern (Python:
  `EmailOutput.send(to=...)`; Go: `mail.Send(cfg, to, msg)` / `SendWithFallback`).
- **Output:** Bei Resend-Host und mindestens einem Empfänger außerhalb der
  Allowlist: Exception (Python `OutputConfigError`) bzw. Error (Go) VOR dem SMTP-
  Dial, kein Mail-Versand, ein Log-Eintrag mit maskiertem Empfänger. Bei Resend-
  Host und ausschließlich Allowlist-Empfängern: Versand läuft normal weiter. Bei
  Stalwart-Host: Guard greift nicht, Verhalten unverändert zu heute.
- **Side effects:** Log-Eintrag bei Blockade (kein Klartext-Empfänger im Log).

## Acceptance Criteria

- **AC-1:** Given ein Sendeaufruf über einen Resend-Host mit einer Empfängeradresse, die zu keinem Nutzerprofil unter `data/users/` gehört / When `EmailOutput.send()` bzw. `mail.Send()` ausgeführt wird / Then wird der Versand VOR dem SMTP-Dial hart abgewiesen (Exception/Error), kein Mail geht raus.
  - Test: Sendeaufruf mit Fremdadresse `unbekannt@example.com` gegen einen Resend-Host auslösen und prüfen, dass `OutputConfigError`/Go-Error geworfen wird und kein SMTP-Connect stattfindet.

- **AC-2:** Given ein Sendeaufruf über einen Resend-Host mit der `mail_to`-Adresse eines echten, angelegten (Nicht-Test-)Nutzerprofils / When der Versand ausgeführt wird / Then wird die Zustellung erlaubt (kein Guard-Abbruch).
  - Test: Fixture-Nutzerprofil mit `mail_to` anlegen, Sendeaufruf mit genau dieser Adresse gegen Resend-Host ausführen, prüfen dass kein Guard-Fehler geworfen wird.

- **AC-3:** Given ein Sendeaufruf über einen Resend-Host mit einer Adresse, die zu einem als Test-Nutzer erkannten Profil gehört (`is_test_user_id`/`IsTestUser` liefert `True`) / When der Versand ausgeführt wird / Then wird die Zustellung abgewiesen, obwohl die Adresse formal in einem `user.json` steht.
  - Test: Test-User-Verzeichnis (z.B. `tdd-1219-fixture`) mit `mail_to` anlegen, Sendeaufruf mit dieser Adresse gegen Resend-Host ausführen, prüfen dass der Guard blockiert.

- **AC-4:** Given ein Sendeaufruf über einen Stalwart-Host (`mail.henemm.com`) mit einer beliebigen, nicht in der Allowlist enthaltenen Adresse / When der Versand ausgeführt wird / Then greift der Allowlist-Guard nicht, Zustellung läuft unverändert wie vor diesem Fix.
  - Test: Denselben Fremdadress-Sendeaufruf wie in AC-1, aber mit Stalwart-Host statt Resend-Host ausführen, prüfen dass kein Allowlist-Guard-Fehler auftritt.

- **AC-5:** Given eine Allowlist-Adresse mit abweichender Groß-/Kleinschreibung oder umgebendem Whitespace (z.B. `" Henning@HENEMM.com "` gegen Allowlist-Eintrag `henning@henemm.com`) / When der Empfänger gegen die Allowlist geprüft wird / Then wird die Adresse nach Normalisierung (parseaddr/ParseAddress + lowercase/trim) korrekt als erlaubt erkannt — identisch in Python UND Go.
  - Test: Denselben Whitespace-/Casing-Testfall einmal gegen den Python-Guard und einmal gegen den Go-Guard laufen lassen, beide müssen den Empfänger als erlaubt bewerten.

- **AC-6:** Given ein durch die Allowlist abgewiesener Sendeversuch / When der Guard den Versand blockiert / Then wird ein Log-Eintrag erzeugt, der die Blockade dokumentiert, ohne die volle Empfängeradresse im Klartext zu loggen.
  - Test: Blockierten Sendeversuch (wie AC-1) auslösen und den erzeugten Log-Eintrag/die Fehlermeldung darauf prüfen, dass die volle Rohadresse nicht im Klartext enthalten ist (z.B. maskiert oder nur Domain).

- **AC-7:** Given die bisherige 2-Adressen-Denylist (`gregor-test@henemm.com`, `gregor-staging@henemm.com`) / When ein Sendeaufruf über einen Resend-Host mit genau einer dieser Adressen erfolgt / Then wird die Zustellung weiterhin abgewiesen, weil diese Adressen zu keinem echten Nutzerprofil gehören (Denylist-Verhalten bleibt über die Allowlist erhalten).
  - Test: Sendeaufruf mit `gregor-test@henemm.com` gegen Resend-Host ausführen, prüfen dass der Guard weiterhin blockiert (Regressionsschutz für die abgelöste Denylist).

## Known Limitations

- Eine Bestätigungsmail an eine noch nicht angelegte Adresse (Registrierungs-Flow) würde blockiert; aktuell existiert kein solcher Flow. Bei künftiger Einführung muss der Nutzer vor dem Mailversand angelegt werden.
- `admin` ohne gesetztes `mail_to`/`email` erhält über Resend keine Mail (erwartetes Verhalten, kein Bug).
- Die Allowlist wird pro Sendeaufruf aus dem Dateisystem neu geladen (kein Caching in dieser Iteration) — bei sehr vielen Nutzerprofilen ist das ein I/O-Overhead pro Send, aber bei der aktuellen Nutzerzahl vernachlässigbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Dies ist eine Guard-Invertierung (Denylist → Allowlist) innerhalb der bestehenden, bereits durch #1122/#1147/#1148 etablierten Empfänger-Guard-Architektur — kein neuer Architekturbaustein, keine neue Technologieentscheidung, sondern eine Härtung des bestehenden Musters.

## Changelog

- 2026-07-10: Initial spec erstellt — Issue #1219, PO-Entscheidung 2026-07-10
