---
spec: docs/specs/modules/external_validator_auth.md
date: 2026-05-03
server_in_session: https://gregor20.henemm.com
server_per_spec_default: https://staging.gregor20.henemm.com
verdict: BROKEN
---

# External Validator Report

**Spec:** `docs/specs/modules/external_validator_auth.md`
**Datum:** 2026-05-03
**Server (Session-Argument):** `https://gregor20.henemm.com`
**Server (Spec-Default laut `Implementation Details` Z.47):** `https://staging.gregor20.henemm.com`

## Vorbemerkung

Die Spec liefert sechs konkrete Datei-Outputs (`.claude/validate-external.sh`, `scripts/setup-validator-user.sh`, `.claude/validator.env.example`, `.claude/agents/external-validator.md`-Erweiterung, `.claude/commands/5-implement.md`-Aenderung, `.gitignore`-Eintrag). Ich habe diese gegen Spec geprueft und parallel die referenzierten API-Endpoints live angesprochen.

Auslegung "LIES NICHT `src/`": Spec-Gegenstand ist Tooling unter `.claude/` und `scripts/` — das ist nicht `src/`. Diese Dateien sind die zu validierenden Outputs.

Empirischer Schnellbefund: Diese Validator-Session wurde **ohne** Auth-Cookie-Block im Prompt gestartet, obwohl die Spec genau das als zentralen Output garantiert. Damit ist die Expected-Behavior-Sektion bereits durch den Aufruf selbst widerlegt. Der Rest des Reports stuetzt das mit Datei- und Endpoint-Beweisen.

## Checklist

| # | Expected Behavior (Spec) | Beweis | Verdict |
|---|--------------------------|--------|---------|
| 1 | Launcher sourct `.claude/validator.env`, ruft `POST /api/auth/login`, extrahiert `gz_session`-Cookie und injiziert ihn als `AUTH_BLOCK` in den Prompt (Spec Z.41-72). | `grep "validator.env\|auth/login\|gz_session\|AUTH_BLOCK\|GZ_VALIDATOR\|COOKIE" .claude/validate-external.sh` → 0 Treffer. Skript hat 57 Zeilen, kein einziger `curl`-Aufruf. | **FAIL** |
| 2 | Default-URL = `https://staging.gregor20.henemm.com` (Spec Z.47, Dependencies Z.33). | `.claude/validate-external.sh:27` setzt Default auf `https://gregor20.henemm.com` (Production). Test-User existiert laut Spec nur auf Staging — Default-Pfad waere damit nutzlos. | **FAIL** |
| 3 | `scripts/setup-validator-user.sh` existiert, idempotent (`POST /api/auth/register`, HTTP 201/409). | `ls /home/hem/gregor_zwanzig/scripts/setup-validator-user.sh` → "No such file or directory". | **FAIL** |
| 4 | `.claude/validator.env.example` existiert als Credentials-Template (Spec Z.96-105). | `ls /home/hem/gregor_zwanzig/.claude/validator.env.example` → "No such file or directory". | **FAIL** |
| 5 | `.gitignore` enthaelt `.claude/validator.env` (Spec Z.134-138). | `grep "validator.env" .gitignore` → 0 Treffer (nur `data/users/validator_test/` matcht "validator", unrelated). | **FAIL** |
| 6 | `.claude/agents/external-validator.md` enthaelt neuen Abschnitt `## Authenticated Requests` nach `## Input` (Spec Z.107-122). | `grep "Authenticated Requests\|Cookie\|gz_session" .claude/agents/external-validator.md` → 0 Treffer. Datei endet wie zuvor. | **FAIL** |
| 7 | `.claude/commands/5-implement.md` ersetzt alten Issue-#110-Hinweis durch Setup-Anleitung (Spec Z.124-132). | `5-implement.md:182` enthaelt weiterhin: *„Issue #110 (External Validator braucht App-Zugangsdaten) muss fuer Mail-/Trip-Verifikationen vorher erledigt sein, sonst ist der Validator fuer eingeloggte Features blind."* Kein Verweis auf `setup-validator-user.sh` oder `validator.env`. | **FAIL** |
| 8 | Side-effect-Voraussetzung: `/api/auth/login` und `/api/auth/register` auf Staging erreichbar (Spec Dependencies). | `POST https://staging.gregor20.henemm.com/api/auth/login` mit falschen Creds → HTTP 401 (Endpoint existiert). Endpoint reagiert wie erwartet. | PASS (nur Vorbedingung) |
| 9 | Validator gegen Production laeuft ohne Auth (Spec Known Limitations Z.149). | `POST https://gregor20.henemm.com/api/auth/login` ebenfalls HTTP 401. Spec dokumentiert: kein Test-User auf Prod — nicht weiter pruefbar ohne Insider-Wissen. | UNKLAR |

## Findings

### Finding 1 — Launcher praktisch unveraendert
- **Severity:** CRITICAL
- **Expected:** Vor `claude --print` ein Login-Block (Spec Z.41-60), der `validator.env` sourct, `curl POST /api/auth/login` macht, `gz_session=...` aus `Set-Cookie` extrahiert; bedingte `AUTH_BLOCK`-Variable wird in `${PROMPT}` interpoliert (Spec Z.62-72).
- **Actual:** `.claude/validate-external.sh` ist unveraendert: Spec-Pfad-Validierung, fester Prompt mit nur `${SPEC_PATH}` und `${VALIDATION_URL}`, dann `claude --print "$PROMPT"`. Keine Login-Logik, kein Cookie, kein Auth-Block.
- **Evidence:** Vollstaendiges Skript (57 Zeilen):
  ```
  Z.27: VALIDATION_URL="${GZ_VALIDATION_URL:-https://gregor20.henemm.com}"
  Z.30-42: PROMPT (ohne ${AUTH_BLOCK})
  Z.56: claude --print "$PROMPT"
  ```
  Empirisch: Mein Session-Prompt enthielt keinen Cookie-Block.

### Finding 2 — Setup-Skript fehlt vollstaendig
- **Severity:** CRITICAL
- **Expected:** `scripts/setup-validator-user.sh` (Spec Z.74-94) — idempotent gegen `POST /api/auth/register`, Behandlung 201/409/sonstige.
- **Actual:** Datei existiert nicht. Ohne dieses Skript hat ein Operator keinen dokumentierten Weg, den Test-User in Staging anzulegen.
- **Evidence:** `ls /home/hem/gregor_zwanzig/scripts/setup-validator-user.sh` → "No such file or directory".

### Finding 3 — Credentials-Template fehlt + `.gitignore` nicht ergaenzt
- **Severity:** HIGH
- **Expected:** `.claude/validator.env.example` als Template (Spec Z.96-105) und `.claude/validator.env` als `.gitignore`-Eintrag (Spec Z.134-138).
- **Actual:** Beide fehlen. Falls jemand `.claude/validator.env` manuell anlegt, ist sie nicht vor Commit geschuetzt.
- **Evidence:** `ls .claude/validator.env.example` → fehlt; `grep "validator.env" .gitignore` → 0 Treffer.

### Finding 4 — Default-URL zeigt auf Production statt Staging
- **Severity:** HIGH
- **Expected:** `VALIDATION_URL="${GZ_VALIDATION_URL:-https://staging.gregor20.henemm.com}"` (Spec Z.47, Dependencies-Tabelle "Ziel-Server fuer Validator-Tests (Default); kein Test-User auf Production").
- **Actual:** `.claude/validate-external.sh:27` → `https://gregor20.henemm.com`. Diametral entgegengesetzt zur Spec-Absicht.
- **Evidence:** Datei-Inhalt Zeile 27.

### Finding 5 — Agent-Doku kennt das Auth-Konzept nicht
- **Severity:** HIGH
- **Expected:** Abschnitt `## Authenticated Requests` in `.claude/agents/external-validator.md` mit Cookie-Verwendung, Public-Routen-Liste, 401→AMBIGUOUS-Regel, Playwright-Cookie-Snippet (Spec Z.107-122).
- **Actual:** Abschnitt fehlt. Selbst wenn der Launcher einen Cookie injizierte, haette der Agent keine Anleitung zur Nutzung.
- **Evidence:** `grep "Authenticated Requests\|Cookie\|gz_session" .claude/agents/external-validator.md` → 0 Treffer.

### Finding 6 — `5-implement.md` verweist weiter auf "Issue #110 muss erledigt sein"
- **Severity:** MEDIUM
- **Expected:** Hinweis ersetzt durch Setup-Anleitung (Spec Z.128-132).
- **Actual:** `.claude/commands/5-implement.md:182` enthaelt unveraendert den Blocker-Hinweis. Ein zukuenftiger Implementer wuerde faelschlich annehmen, das Modul sei noch nicht ready.
- **Evidence:** `grep -n "Issue #110" .claude/commands/5-implement.md` → Treffer in Z.182.

### Finding 7 — Live-Smoke: Endpoints existieren, werden aber nicht genutzt
- **Severity:** INFO
- **Expected:** Login-Endpoint auf Staging erreichbar (Voraussetzung).
- **Actual:** `POST https://staging.gregor20.henemm.com/api/auth/login` antwortet HTTP 401 bei falschem Passwort — Infrastruktur ist da; Implementation nutzt sie aber nicht.
- **Evidence:**
  ```
  $ curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST \
      https://staging.gregor20.henemm.com/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"username":"validator","password":"wrong"}'
  HTTP 401
  ```

## Verdict: **BROKEN**

### Begruendung

Von 9 pruefbaren Punkten der `Expected Behavior`/`Implementation Details`-Sektionen:
- **7 FAIL**: Login-Block, Default-URL, Setup-Skript, Env-Template, `.gitignore`, Agent-Doku, Implement-Command-Hinweis.
- **1 PASS** (nur Vorbedingung — Endpoints existieren, werden aber von der nicht implementierten Logik nicht genutzt).
- **1 UNKLAR** (Prod-Side-Effect — laut Spec ohne Test-User, also nicht beweisbar).

Das **zentrale Spec-Ziel** ("Validator hat vollen Zugriff auf geschuetzte `/api/*`-Routen via Cookie-Injection in den Prompt") ist nicht erreicht. Der lebende Beweis: Diese Validator-Session lief ohne Cookie-Block, exakt wie vor der Spec.

Konkrete Wirkung fuer einen heute aufrufenden Operator: `bash .claude/validate-external.sh <spec>` verhaelt sich identisch zum Pre-Spec-Stand — kein Login, kein Cookie, und der Default-Server ist zudem Production statt Staging.

### Empfehlung

Die Implementierer-Session hat die Spec offenbar nicht ausgefuehrt — keine der sechs in `Source` und `Implementation Details` benannten Datei-Aenderungen ist im Working Tree sichtbar. Nicht partiell nachbessern, sondern vollstaendig nach Spec implementieren (die Code-Bloecke in der Spec sind copy-paste-faehig). Default-URL-Diskrepanz im Launcher korrigieren, nicht in der Spec — Spec ist konsistent.
