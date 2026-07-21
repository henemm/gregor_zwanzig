---
entity_id: issue_1122_resend_default_deny
type: module
created: 2026-07-08
updated: 2026-07-08
status: approved
version: "1.0"
tags: [email, resend, guardrail, default-deny, go, python]
---

# Issue #1122 — Resend Default-Deny: Versand nur mit explizitem Token

## Approval

- [x] Approved (PO „go" 2026-07-08, Chat-Session `claude/resend-test-abuse-10jqqx`)

## Purpose

Zum 10. Mal wurde Resend (bezahlter Produktiv-Versanddienst) durch Tests belastet.
Alle bisherigen Fixes (#198, #879, #924, …) waren **Opt-in-Schutz**: Tests mussten sich
aktiv wegducken (`for_testing()`, `is_test_mode`). Wer das vergisst, leakt lautlos.

Dieses Modul **dreht die Richtung um (PO-Entscheidung): Default-Deny.** Resend ist
grundsätzlich gesperrt; nur ein Prozess mit explizitem Token `GZ_RESEND_ALLOWED=1`
(gesetzt ausschließlich in den Prod-Systemd-Units) darf einen Resend-Host verwenden.
Testläufe (pytest / `go test`) sind **auch mit Token** gesperrt — es gibt keinen
legitimen Grund, aus einem Testprozess über Resend zu senden.

## Source

- **File:** `src/app/config.py` — **Identifier:** `Settings.resend_allowed` (Field),
  `Settings._resend_default_deny` (model_validator), `_in_pytest()` (Helper)
- **File:** `internal/mail/sender.go` — **Identifier:** `resendBlocked()`, Aufruf in `Send()`

Schicht-Hinweis: Python-Core (`src/app/`) + Go-API (`internal/mail/`). Die Frontend-Schicht
ist nicht betroffen. `src/output/channels/email.py` wird **bewusst nicht angefasst**
(Renderer-Mail-Gate #811; die dortigen Guards #879/#924 bleiben unverändert als zweite Linie).

## Estimated Scope

- **LoC:** ~60 Implementierung + ~150 Tests
- **Files:** 4 (config.py, sender.go, sender_test.go, neuer TDD-Test) + 3 Bestandstest-Anpassungen
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Settings | module | Trägt Token-Feld + Default-Deny-Validator |
| EmailOutput | module | Bestehende Guards (#879/#924) bleiben zweite Linie |
| mail.Send (Go) | module | Einziger Go-SMTP-Dispatch — Guard deckt alle Go-Mails |
| henemm-infra Prod-Units | infra | Müssen `GZ_RESEND_ALLOWED=1` setzen (Vorbedingung Deploy) |

## Implementation Details

```
Python (src/app/config.py):
  - Neues Feld: resend_allowed: bool = False  (env: GZ_RESEND_ALLOWED)
  - model_validator(mode="after") _resend_default_deny:
      if "resend" in smtp_host.lower():
          if resend_allowed and not _in_pytest(): pass  # Prod mit Token
          else:
              logger.error(...)  # laut, diagnostizierbar
              smtp_host := test_smtp_host (Default mail.henemm.com)
              smtp_port := test_smtp_port
      Credentials werden NICHT umgeschrieben: Resend-Creds gegen Stalwart
      → 535 Auth-Fehler → LAUTER Fehlschlag statt stillem Reroute.
      Der sanktionierte Testpfad bleibt for_testing() (swappt auch Creds).
  - _in_pytest(): "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules

Go (internal/mail/sender.go):
  - resendBlocked(host) error:
      kein "resend" im Host        → nil
      testing.Testing()            → Fehler (auch mit Token; Go >= 1.21)
      GZ_RESEND_ALLOWED != "1"     → Fehler
  - Send() ruft resendBlocked() vor jedem Dial; SendWithFallback ist damit
    für Primary UND Fallback abgedeckt (beide laufen durch Send()).
```

**Abweichung von der Chat-AC-Skizze (transparent):** Python wirft beim
Settings-Konstrukt **keinen** harten Fehler, sondern lenkt den Host um. Grund:
(1) Ein Raise in `Settings()` würde ganze Apps (Staging-API-Startup, Previews)
crashen, nicht nur den Versand. (2) Der Versand schlägt trotzdem **laut** fehl
(535 gegen Stalwart mit Resend-Creds), weil Creds bewusst nicht mitgeswappt
werden. Die Garantie „nie Resend ohne Token" gilt strikt. Go wirft hart (dort
gibt es keinen Konstruktions-Seiteneffekt).

## Expected Behavior

- **Input:** Settings-Konstruktion / `mail.Send()`-Aufruf mit Resend-Host
- **Output:** Ohne Token (oder unter pytest/`go test`): Python-Settings tragen nie
  einen Resend-Host; Go-Send liefert Fehler vor dem Dial. Mit Token außerhalb von
  Tests: unverändert Resend.
- **Side effects:** `logger.error` bei jeder Umlenkung (Diagnose von Fehlkonfiguration).

## Acceptance Criteria

- **AC-1:** Given ein Prozess ohne `GZ_RESEND_ALLOWED` / When `Settings` mit einem
  Resend-SMTP-Host konstruiert wird (auch rohe `Settings()` ohne `for_testing()`) /
  Then enthält `smtp_host` kein „resend" mehr, sondern den Stalwart-Test-Host —
  ein `EmailOutput` aus diesen Settings kann Resend nicht erreichen.
  - Test: Konstruktion + EmailOutput-Roundtrip, Verhalten der Instanz geprüft.

- **AC-2:** Given ein pytest-Prozess mit gesetztem `GZ_RESEND_ALLOWED=1` (Token in
  Test-Shell geleakt) / When `Settings` mit Resend-Host konstruiert wird /
  Then wird trotzdem auf den Stalwart-Test-Host umgelenkt — Testprozess schlägt Token.
  - Test: In-Process-Konstruktion mit `resend_allowed=True` unter pytest.

- **AC-3:** Given ein Nicht-Test-Prozess mit `GZ_RESEND_ALLOWED=1` (Produktion) /
  When `Settings` mit Resend-Host konstruiert wird / Then bleibt der Resend-Host
  erhalten — echter User-Versand funktioniert unverändert.
  - Test: Subprocess ohne `PYTEST_CURRENT_TEST`/pytest-Import, Host-Ausgabe geprüft.

- **AC-4:** Given ein `go test`-Lauf (auch mit `GZ_RESEND_ALLOWED=1`) / When
  `mail.Send()` mit Resend-Host aufgerufen wird / Then Fehler vor jedem
  Netzwerk-Dial; Fehlertext nennt `GZ_RESEND_ALLOWED` und Issue #1122.
  - Test: Echter `Send()`-Aufruf in `go test`, Fehlerrückgabe geprüft (kein Netz nötig).

- **AC-5:** Given ein Go-Prozess ohne Token / When `mail.Send()` mit Resend-Host /
  Then Fehler; ein Nicht-Resend-Host wird vom Guard NICHT blockiert (Fehler dort
  allenfalls vom Dial, ohne Guard-Kennung).
  - Test: Guard-Fehlertext vs. Dial-Fehlertext unterschieden.

- **AC-6:** Given Settings-Bypass via `model_copy(update={"smtp_host": "smtp.resend.com"})`
  mit `is_test_mode=True` / When `EmailOutput` konstruiert wird / Then greift die
  bestehende zweite Linie (#879) mit `OutputConfigError` unverändert.
  - Test: Bestandstests umgestellt auf model_copy-Konstruktion (Validator läuft bei
    model_copy nicht — genau dafür bleibt die zweite Linie).

## Known Limitations

- `model_copy(update={"smtp_host": …})` umgeht den Validator (pydantic-Semantik) —
  dafür bleiben die EmailOutput-Guards (#879/#924) als zweite Linie bestehen (AC-6).
- Der IMAP-basierte SMTP-Fallback-Host (`imap_host`) wird nicht umgelenkt; er zeigt
  in allen bekannten Konfigurationen auf Stalwart, nie auf Resend.
- Ein Nicht-pytest-Prozess, in den das Token bewusst exportiert wird, kann Resend
  nutzen — das ist die definierte Freigabe, kein Leck. Schutzziel ist die Klasse
  „Test-/Default-Prozess erreicht Resend", nicht Vorsatz.
- **Deploy-Vorbedingung:** `GZ_RESEND_ALLOWED=1` muss in `gregor-python.service` +
  `gregor-api` (henemm-infra) gesetzt sein, BEVOR dieser Stand auf Prod geht — sonst
  schlagen echte Versände laut fehl (535, sichtbar im Scheduler-Status/Selftest #564).
  Staging bekommt das Token NICHT (ersetzt String-Check `env=="staging"` als Primärschutz).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Umkehrung eines bestehenden Schutzmusters (Opt-in → Default-Deny)
  innerhalb bestehender Module; keine neue Systemgrenze. PO-Entscheidung im Issue-Dialog
  dokumentiert (#1122), Spec hält die Abweichung (Redirect statt Raise) explizit fest.

## Changelog

- 2026-07-08: Initial Spec nach PO-„go" (Default-Deny via GZ_RESEND_ALLOWED, Issue #1122)
