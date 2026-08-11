---
entity_id: fix_1596_user_json_fehler_laut
type: module
created: 2026-08-11
updated: 2026-08-11
status: draft
version: "1.0"
tags: [bug, auth, tier-gating, mail, logging]
---

# Unlesbare/defekte user.json wird laut statt still (Issue #1596)

## Approval

- [x] Approved (2026-08-11, PO)

## Purpose

Eine vorhandene, aber unlesbare oder inhaltlich kaputte `user.json` wird an drei Stellen
(Login, Tier-Gating, Mail-Allowlist) aktuell identisch zu einer **fehlenden** `user.json`
behandelt (legitimer Default-Fall). Der Fix trennt diese beiden Fälle serverseitig durch
Logging, ohne das nach außen sichtbare Verhalten (Statuscode, Response-Body, Rückgabewerte,
Timing) zu verändern — ein Bug (Design-Lücke seit Ursprungscommit `19a41682`), keine
Regression.

## Source

- **File:** `internal/handler/auth.go`
- **Identifier:** `LoginHandler` (Zeilen 122-160, betroffener Zweig Zeile 132-137)

- **File:** `src/services/user_tier.py`
- **Identifier:** `sms_allowed`, `premium_sms_allowed`, `daily_alert_limit` (gesamte Datei,
  je ein `except (json.JSONDecodeError, OSError)`-Zweig pro Funktion)

- **File:** `src/output/channels/email.py`
- **Identifier:** `_load_resend_allowlist` (Zeile 239-284, betroffener Zweig Zeile 275-276)

> Schicht-Hinweis: `auth.go` liegt korrekt in der Go-API (`internal/handler/`, Production-API
> Port 8090). `user_tier.py` und `email.py` liegen korrekt im Python-Core
> (`src/services/`, `src/output/channels/`). Keine Schichtverwechslung — verifiziert per grep
> auf die drei Symbolnamen vor Spec-Erstellung.

## Estimated Scope

- **LoC:** ~+30/-10
- **Files:** 3 Kern-Dateien (`internal/handler/auth.go`, `src/services/user_tier.py`,
  `src/output/channels/email.py`) + 2 Testdateien (`internal/handler/auth_test.go`,
  `tests/unit/test_user_tier.py`)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store/user.go` (`LoadUser`) | Upstream | Unterscheidet bereits korrekt `(nil, nil)` = Datei fehlt von `(nil, err)` = Datei existiert, ist aber unlesbar/kaputt. Keine Änderung nötig — der Fix konsumiert diese bestehende Unterscheidung nur an den drei genannten Aufrufstellen. |
| `app.loader.get_data_dir` / `get_data_root` | Upstream | Liefert den Pfad zu `<data_root>/users/<id>/`, den `user_tier.py` und `email.py` lesen. Keine Änderung. |
| SvelteKit `/login`-Form-Action | Downstream | Konsumiert `LoginHandler`-Antwort; Statuscode/Body bleiben unverändert, daher kein Frontend-Änderungsbedarf. |
| Alarm-Versand, SMS-Kanal, Premium-SMS-Kanal | Downstream | Konsumieren `daily_alert_limit`/`sms_allowed`/`premium_sms_allowed`; Rückgabewerte bleiben unverändert, daher kein Konsumenten-Änderungsbedarf. |
| Mail-Versandpfad (#1219 Allowlist) | Downstream | Konsumiert `_load_resend_allowlist`; Filterverhalten bleibt unverändert, nur zusätzliches Log bei übersprungenem Profil. |

## Implementation Details

```
# internal/handler/auth.go — LoginHandler, Zeile 132-137 (aktuell):
user, err := s.LoadUser(req.Username)
if err != nil || user == nil {
    w.WriteHeader(401)
    w.Write([]byte(`{"error":"invalid credentials"}`))
    return
}

# Neu — Zweig auftrennen, Client-Antwort bleibt in BEIDEN Zweigen identisch:
user, err := s.LoadUser(req.Username)
if err != nil {
    log.Printf("login: user.json unreadable/corrupt for %s: %v", req.Username, err)
    w.WriteHeader(401)
    w.Write([]byte(`{"error":"invalid credentials"}`))
    return
}
if user == nil {
    w.WriteHeader(401)
    w.Write([]byte(`{"error":"invalid credentials"}`))
    return
}
```

```python
# src/services/user_tier.py — Muster in allen drei Funktionen (additiv, kein
# neuer Kontrollfluss): Logger-Import + logger.warning() im except-Zweig.
import json
import logging

from app.loader import get_data_dir

logger = logging.getLogger("user_tier")

def sms_allowed(user_id: str) -> bool:
    ...
    try:
        profile = json.loads(profile_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("user.json unreadable/corrupt for %s at %s: %s", user_id, profile_path, exc)
        return False
    ...

# premium_sms_allowed und daily_alert_limit: identisches Muster, Rückgabewert
# (False bzw. tier="free") bleibt in JEDEM except-Zweig unangetastet.
```

```python
# src/output/channels/email.py — _load_resend_allowlist, Zeile 275-276:
for user_id in user_ids:
    profile_path = users_root / user_id / "user.json"
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("user.json unreadable/corrupt for %s at %s: %s", user_id, profile_path, exc)
        continue
    ...
```

`email.py` hat bereits ein Modul-Logging (zu verifizieren beim Implementieren — falls kein
`logger` existiert, analog `alert_state.py`/`alert_gate.py` einführen:
`logger = logging.getLogger("email")`).

## Expected Behavior

- **Input:** Eine `user.json`-Datei existiert am erwarteten Pfad, ist aber entweder nicht
  lesbar (Permission, I/O-Fehler) oder enthält kein valides JSON-Objekt.
- **Output:**
  - Login: HTTP 401, Body `{"error":"invalid credentials"}` — **identisch** zum
    Nicht-gefunden-Fall und zum Falsches-Passwort-Fall. Zusätzlich: ein Server-Log-Eintrag mit
    Nutzername/Pfad/Fehlerursache.
  - Tier-Gating: `sms_allowed()` → `False`, `premium_sms_allowed()` → `False`,
    `daily_alert_limit()` → `2` (free-Default) — **identisch** zum Bestandsverhalten.
    Zusätzlich: ein `logger.warning(...)`-Eintrag mit User-ID/Pfad/Fehlerursache.
  - Mail-Allowlist: das betroffene Profil wird übersprungen, alle anderen Profile normal
    verarbeitet — **identisch** zum Bestandsverhalten. Zusätzlich: ein
    `logger.warning(...)`-Eintrag mit User-ID/Pfad/Fehlerursache.
- **Side effects:** Ausschließlich neue Log-Zeilen (Go: `log.Printf`, stdout/systemd-Journal;
  Python: `logger.warning`, Standard-Logging-Handler). Keine Änderung an Statuscodes,
  Response-Bodies, Rückgabewerten oder Timing.

## Acceptance Criteria

- **AC-1:** Given eine vorhandene, aber inhaltlich kaputte (nicht valides JSON) `user.json`
  für einen Nutzer / When dieser Nutzer sich einloggt / Then antwortet der Server mit
  identischem 401 + `{"error":"invalid credentials"}` wie bei falschem Passwort, UND es
  erscheint ein Server-Log-Eintrag mit Nutzername und Fehlerursache.
  - Test: `internal/handler/auth_test.go` — neuer Testfall, der eine `user.json` mit kaputtem
    Inhalt (nicht valides JSON, aber Datei existiert) anlegt, `LoginHandler` aufruft, den
    401-Statuscode UND (per Log-Capture, z. B. `log.SetOutput` auf einen `bytes.Buffer`) das
    Vorhandensein eines Log-Eintrags mit dem Nutzernamen prüft.

- **AC-2:** Given eine vorhandene, aber inhaltlich kaputte `user.json` / When
  `sms_allowed()`, `premium_sms_allowed()` oder `daily_alert_limit()` für diesen Nutzer
  aufgerufen wird / Then bleibt der Rückgabewert unverändert (`False` bzw. `2`/free-Default,
  `premium_sms_allowed()` insbesondere weiterhin `False`), UND es erscheint ein
  `logger.warning`-Eintrag mit User-ID und Fehlerursache.
  - Test: `tests/unit/test_user_tier.py` — neue Testfälle für alle drei Funktionen mit einer
    absichtlich kaputten `user.json` (z. B. `(path / "user.json").write_text("{not json")`),
    die sowohl den unveränderten Rückgabewert als auch (via `caplog`/`pytest`-Log-Capture)
    das Vorhandensein einer Warnung mit der User-ID prüfen.

- **AC-3:** Given ein Nutzerprofil mit kaputter `user.json` unter mehreren sonst gültigen
  Profilen / When `_load_resend_allowlist()` aufgerufen wird / Then enthält das Ergebnis die
  gültigen Profile normal, das kaputte Profil wird übersprungen (kein Crash), UND es
  erscheint pro übersprungenem Profil ein `logger.warning`-Eintrag mit User-ID und
  Fehlerursache.
  - Test: bestehende/erweiterte Testdatei für `email.py`-Allowlist (Test-Suite zu #1219
    finden und erweitern) — Fixture mit einem validen und einem kaputten Profil, prüft
    Allowlist-Inhalt UND Log-Eintrag.

- **AC-4 (Abgrenzung):** Given eine **fehlende** `user.json` (Datei existiert nicht) / When
  Login, Tier-Gating-Funktionen oder Allowlist-Aufbau für diesen Nutzer laufen / Then bleibt
  das Verhalten wie bisher (401 bzw. `False`/free-Default bzw. übersprungen), UND es
  erscheint **kein** neuer Log-Eintrag — der Normalfall „nicht registriert"/„noch kein
  Profil" bleibt bewusst still.
  - Test: in denselben drei Testdateien je ein Regressions-Testfall mit tatsächlich fehlender
    Datei, der die Abwesenheit eines Log-Eintrags prüft (z. B. leerer Log-Buffer/kein
    passender `caplog`-Treffer).

## Known Limitations

- **Scope bewusst auf drei Stellen begrenzt (PO-Entscheid 2026-08-08, Nebenbefund-Triage):**
  Das identische Muster (`err != nil || user == nil` bzw. `except (...): <stiller Fallback>`)
  kommt strukturell an **19+6 weiteren Stellen** vor: Go — `auth.go` selbst hat 9 Stellen
  gesamt (Zeile 133, 168, 344, 406, 518, 534, 737, 778 sowie die hier gefixte 132-137),
  `telegram_connect.go` (3), `passkey.go` (6), `premium_sms_connect.go` (1, in einer
  Nutzer-Schleife mit `continue`); Python — `config.py`
  (`is_test_user_id`, `with_user_profile`), `loader.py` (2 Reverse-Lookups). Diese sind
  **nicht** Teil dieses Fixes. Nach Abschluss als Checkbox-Zeilen mit `file:line` in #1199
  buchen — kein Auto-Fix, keine Konsolidierung zu einem gemeinsamen Helper (siehe unten,
  warum ein Helper hier bewusst vermieden wird).
- **`internal/scheduler/tier_request_health.go:34-38` bleibt unangetastet:** dort ist
  Fail-Soft explizit dokumentierte Absicht (Aggregat-Job darf an einem kaputten Profil nicht
  abbrechen) — kein Bug, kein Ziel dieses Fixes.
- **Kein gemeinsamer Helper für die drei `user_tier.py`-Funktionen:** `premium_sms_allowed()`
  delegiert absichtlich nicht an `sms_allowed()` (sonst stille Rechte-Ausweitung von
  `standard` auf Premium-SMS-Berechtigung). Eine Konsolidierung des Lade-/Log-Musters in
  einen Helper würde diese bewusste Trennung aufweichen und ist daher out of scope.
- **Kein gemeinsamer Go-Helper für `LoginHandler`:** nur eine Stelle betroffen, ein Helper für
  eine einzelne Aufrufstelle wäre Overengineering; die 8 weiteren Stellen mit demselben Muster
  sind bewusst nicht Teil dieser Änderung (s. o.).
- **Log-Format nicht strukturiert:** `log.Printf`/`logger.warning` mit Freitext-Nachricht,
  konsistent mit der bestehenden Konvention in `auth.go` (z. B. Zeile 290, 634) und
  `alert_state.py`/`alert_gate.py`. Kein strukturiertes Logging (JSON-Log-Felder) — wäre ein
  separates, projektweites Vorhaben.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Rein additive Logging-Ergänzung ohne Änderung des nach außen sichtbaren
  Verhaltens (Statuscode, Response-Body, Rückgabewerte, Timing bleiben in jedem Zweig
  identisch). Keine neue Entscheidungsfläche (kein neuer Kanal, kein neuer Provider, kein
  Datenmodell-/Persistenz-Wechsel, keine Auth-Verhaltensänderung) — betrifft ausschließlich
  Server-seitige Beobachtbarkeit eines bereits vorhandenen Fehlerfalls.

## Changelog

- 2026-08-11: Initial spec created
