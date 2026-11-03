# Runbook — zweiter Staging-Nutzer `en` (Issue #2681, i18n A2)

Spec: `docs/specs/modules/i18n_a2_e2e_zweisprachig_2681.md` · Skript: `scripts/staging_e2e_user_en.py`

## Zweck

`/e2e-verify` prüft jeden Mail-Pfad in **beiden** Sprachen. Dafür gibt es auf Staging zwei
getrennte Konten mit getrennter Zustellung:

| Nutzer | Sprache | Empfänger | Anmeldung |
|---|---|---|---|
| Standard-Testnutzer | `de` | `gregor-test@henemm.com` (Basispostfach) | wie bisher |
| `gzp-e2e-en` (Server-Kennung `u-…`) | `en` | `gregor-test+en@henemm.com` (Subadresse) | `GZ_E2E_EN_USER` / `GZ_E2E_EN_PASS` |

Stalwart liefert `gregor-test+<tag>@henemm.com` ins Basispostfach (Muster
`.claude/tools/staging_befehl_pruefen.py`). Die Validatoren trennen die beiden Nutzer über
`--lang` und den Empfänger (`+en@`). Keine neue Infrastruktur, kein Eingriff in Produktion.

## Aufruf

```bash
python3 scripts/staging_e2e_user_en.py                 # Staging, /home/hem/gregor_zwanzig_staging/.env
python3 scripts/staging_e2e_user_en.py --basis-url URL --env-datei PFAD
```

| Exit | Bedeutung |
|---|---|
| 0 | Nutzer vorhanden (`vorhanden`), neu angelegt (`angelegt`) oder Sprache korrigiert (`korrigiert`); `language=en`, E-Mail bestätigt |
| 1 | Zustand nicht herstellbar (Profil-Update auf `en` ohne Wirkung) |
| 2 | Aufruf-/Umgebungsfehler: Zugangsdaten fehlen, Registrierung abgelehnt (409 `email_taken`, 429), veraltete `GZ_E2E_EN_*` |

Idempotent: sind `GZ_E2E_EN_*` gesetzt und gültig, wird nur angemeldet und die Sprache geprüft
(abweichend → `PUT /api/auth/profile {"language":"en"}`). Höchstens **eine** Registrierung je Lauf,
nie ein zweites Konto, nie Löschen.

## Secrets

| Schlüssel | Inhalt | Ort |
|---|---|---|
| `GZ_E2E_EN_USER` | Server-Kennung des Kontos (`u-<8hex>`) | Staging-`.env` |
| `GZ_E2E_EN_PASS` | Passwort (`secrets.token_urlsafe(24)`) | Staging-`.env` |
| `GZ_E2E_EN_MAIL` | `gregor-test+en@henemm.com` | Staging-`.env` |
| `GZ_AUTH_USER` / `GZ_AUTH_PASS` | bestätigtes Helfer-Konto (holt `staging-token`) | Staging-`.env` |
| `GZ_TEST_IMAP_USER` | Basispostfach, aus dem die Subadresse abgeleitet wird | Staging-`.env` |

Das Skript **hängt** die drei `GZ_E2E_EN_*` bei der Erstanlage an (Dateirechte 600) und
überschreibt nie vorhandene Werte. Das Passwort steht nie in Ausgabe, Log oder Repo
(`secret_in_repo_gate.py`, `secret_output_gate.py`).

## Rate-Limit

`POST /api/auth/register` erlaubt **5 Registrierungen je IP und Stunde**. Die Playwright-Spec
`frontend/e2e/sprachwechsel.spec.ts` verbraucht je Lauf zwei davon, das Befehls-Werkzeug je Lauf eins.
Bei 429: eine Stunde warten, nicht wiederholen.

## Wiederherstellung

- **Konto fehlt** (Staging zurückgesetzt), Schlüssel fehlen ebenfalls: Skript erneut laufen lassen.
- **Exit 2 „Anmeldung des Nutzers en scheitert"** (Schlüssel vorhanden, aber 401/403): das Skript
  überschreibt nichts. Die drei Zeilen `GZ_E2E_EN_*` aus der Staging-`.env` entfernen, dann das Skript
  erneut starten.
- **Exit 2 mit `409 (email_taken)`**: die Subadresse gehört schon einem Konto, dessen Zugangsdaten
  fehlen. Altes Konto über die Admin-Nutzerverwaltung auf Staging löschen, dann das Skript erneut starten.
- Bekannter Blocker des Staging-Mailwegs für `/e2e-verify` Schritt 3b: #2774 (Plus-Adresse und
  Helfer-Konto nach Muster `.claude/tools/staging_befehl_pruefen.py`).
