# Kontext & Analyse — fix-1219-resend-allowlist

**Issue:** #1219 — Positive Empfänger-Allowlist für Resend-Versand
**Typ:** Bug / Sicherheitshärtung
**PO-Entscheidung (2026-07-10):** Über Resend nur an angelegte, **echte** Nutzerkonten senden; **Test-Nutzer ausgeschlossen**; alles andere hart abweisen + protokollieren.

## Problem (Root Cause)

Es existiert **keine positive Empfänger-Allowlist**, sondern nur eine 2-Adressen-Denylist
(`gregor-test@`, `gregor-staging@henemm.com`). Sobald Resend in Prod aktiv ist
(`GZ_RESEND_ALLOWED=1`), wird an **jede** Adresse zugestellt, die nicht exakt eine dieser
zwei ist — ohne Prüfung, ob dahinter ein echter Nutzer steckt. Das ist der Weg, über den
wiederholt Test-Mails an reale Adressen rausgehen.

## Analysis

### Type
Bug (Sicherheits-/Datenrisiko: versehentliche Fremdzustellung)

### Sende-Architektur (Ist-Zustand)
Zwei unabhängige Sende-Implementierungen, KEIN gemeinsamer `resolve_recipients()`:
- **Python:** alle Sends laufen durch `EmailOutput.send()` → SMTP-Dial `src/output/channels/email.py:349`.
  Empfänger-Guard (#1147) sitzt bei `email.py:313`.
- **Go:** alle Sends durch `mail.SendWithFallback()` → `smtp.SendMail` `internal/mail/sender.go:240`.
  Empfänger-Guard `recipientBlocked` bei `sender.go:169`.

Beide Guards sind heute **Denylists** (nur 2 Test-Postfächer, `TEST_MAILBOXES`).
Resend-Erkennung überall: Substring `"resend" in host.lower()`.

### Empfänger-Quelle in den Daten
- Nutzer-Profile: `data/users/<id>/user.json`. **Kein Login-E-Mail-Feld befüllt** — die
  User-ID ist der Login-Name (z.B. `henning`). Empfängeradresse steht in **`mail_to`**.
- Go-User-Model kennt zusätzlich `Email` (Konto-E-Mail), in JSON aktuell leer, aber im
  Auth-Pfad als Fallback genutzt (`auth.go:214`).
- Beide Auth-Flows senden an einen **existierenden** Nutzer:
  - Passwort-Reset `auth.go:212`: `recipient = user.MailTo || user.Email`.
  - Magic-Link `auth_magic.go`: findet Nutzer per Request-E-Mail, sendet an dessen Adresse.
  → Eine Allowlist aus `mail_to` + `email` aller echten Nutzer deckt diese Flows ab.

### Test-Nutzer-Erkennung (Ausschluss)
Bestehend: `is_test_user_id()` (Python `config.py:239`) / `IsTestUser` (Go `sender.go:46`) —
Substring `"test"`/`"tdd"` in User-ID. Für den **Ausschluss aus der Allowlist** ist die
konservative Richtung sicher: im Zweifel als Test behandeln → nicht in Allowlist → über
Resend blockiert. Verzeichnisse wie `tdd-1007-*`, `design_tdd`, `validator-issue110` fallen
damit raus; echte Nutzer (`henning`, `steffi`, `default`, `admin`) bleiben.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `src/output/channels/email.py` | MODIFY | Empfänger-Guard @313: Denylist → Allowlist (nur wenn Host=Resend) |
| `internal/mail/sender.go` | MODIFY | `recipientBlocked` @169: Denylist → Allowlist, symmetrisch |
| Allowlist-Loader (Py) | CREATE/MODIFY | Sammelt `mail_to`+`email` echter (Nicht-Test-)Nutzer aus `data/users/` |
| Allowlist-Loader (Go) | CREATE/MODIFY | dito, gleiche Quelle/Semantik |
| Tests (Py + Go) | CREATE | Repro: Fremdadresse über Resend → blockiert; echter Nutzer → erlaubt; Test-Nutzer → blockiert |

### Scope Assessment
- Files: ~4–6
- Estimated LoC: ~+120 / -30
- Risk Level: **MEDIUM** (sicherheitskritischer Sendepfad, doppelt Python+Go, Symmetrie-Pflicht)

### Technical Approach (Empfehlung)
1. Zentrale Allowlist-Funktion je Sprache: lädt alle `data/users/*/user.json`, überspringt
   Test-User-IDs, sammelt normalisierte `mail_to` + `email` → Set erlaubter Adressen.
2. Guard-Inversion an beiden Chokepoints, **nur wenn Zielhost Resend ist**:
   Empfänger ∉ Allowlist → harte Exception/Error + Log (kein Dial, kein stilles Verwerfen).
   Stalwart-/Test-Pfad (`mail.henemm.com`) bleibt unberührt.
3. Adress-Normalisierung wiederverwenden (parseaddr / mail.ParseAddress), damit Whitespace-/
   Casing-Umgehungen wie in #1152 nicht greifen — Symmetrie Python↔Go.
4. Bestehende 2-Postfach-Denylist entfällt bzw. wird von der Allowlist absorbiert (Test-Postfächer
   sind ohnehin keine echten Nutzer → nicht in Allowlist → über Resend blockiert; Stalwart weiter erlaubt).

### Dependencies
- Baut auf Safe-Send-Trias #1122 (Host-Default-Deny) / #1147 (Empfänger-Guard) / #1148 (Bash-Hook) auf.
- Ersetzt den Empfänger-**Denylist**-Ansatz aus #1147 durch eine echte Allowlist.

### Open Questions / Known Limitations
- [ ] Neuregistrierungs-Bestätigungsmail an eine **noch nicht angelegte** Adresse würde blockiert.
      Aktuell kein solcher Flow aktiv (Auth sendet nur an existierende Nutzer); falls später
      eingeführt: User vor Mailversand anlegen. In Spec als bekannte Grenze dokumentieren.
- [ ] `admin` hat kein `mail_to`/`email` → erhält über Resend nichts (korrekt, da kein Empfänger konfiguriert).
