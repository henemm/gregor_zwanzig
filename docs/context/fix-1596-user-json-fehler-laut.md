# Context: fix-1596-user-json-fehler-laut

## Request Summary

Issue #1596: Eine unlesbare/defekte `user.json` wird an drei Stellen wie eine **fehlende**
`user.json` behandelt (legitimer Default), statt als **Fehler** laut zu werden. Betroffen:
Login (täuscht „falsches Kennwort" vor, kein Log), Tier-Gating (stiller Rückfall premium→free,
z. B. Limit-Absenkung von unlimited auf 2), Mail-Allowlist (Empfänger wird stillschweigend
übersprungen). PO-Vorgabe: Client-Antwort darf generisch bleiben (kein User-Enumeration-Leak),
aber serverseitig MUSS ein Fehler mit Pfad/Ursache geloggt werden.

## Related Files

| File | Relevance |
|------|-----------|
| `internal/store/user.go:48-65` | `LoadUser()` — unterscheidet bereits sauber `(nil, nil)` = nicht gefunden von `(nil, err)` = Lesefehler. Kein Änderungsbedarf hier, die Unterscheidung existiert schon. |
| `internal/handler/auth.go:122-162` (`LoginHandler`) | Kollabiert `err != nil` und `user == nil` in denselben 401-Zweig (Z.132-138), kein Log. **Primäres Ziel des Fixes.** |
| `src/services/user_tier.py` | Drei Funktionen (`sms_allowed`, `premium_sms_allowed`, `daily_alert_limit`), alle mit identischem Muster: `except (json.JSONDecodeError, OSError): return False` / `tier = "free"` — kein Log, keine Unterscheidung fehlt/kaputt. |
| `src/output/channels/email.py:271-273` | Allowlist-Aufbau: `except (OSError, ValueError): continue` — überspringt kaputtes Profil ohne Log. |

## Existing Patterns

- **`LoadUser()` selbst macht die Unterscheidung schon richtig** (Go): `os.IsNotExist(err)` →
  `(nil, nil)`; jeder andere Fehler (Permission, I/O, JSON-Parse) → `(nil, err)`. Die Aufrufer
  ignorieren diese Unterscheidung aktuell durchgängig.
- **Systemisches Muster im Go-Handler-Layer:** `if err != nil || user == nil { ... }` taucht
  identisch an **mindestens 8 weiteren Stellen** auf: `telegram_connect.go` (3×), `passkey.go`
  (5×), `premium_sms_connect.go` (1×, im Loop über alle User — dort `continue` statt Abbruch),
  `tier_request_health.go`. Alle kollabieren ebenfalls Fehler und Nicht-Gefunden.
- **Etablierter Projekt-Grundsatz „leer ≠ unbekannt"** (#1492, an anderer Stelle im
  Wetter-Fallback-Code): `None`/Fehler explizit von einer legitimen leeren Menge unterscheiden,
  nie stillschweigend gleichsetzen. Dieselbe Denkfigur, neue Stelle.
- **`premium_sms_allowed()` ist bewusst fail-closed** (Docstring verweist auf #1676 S2a
  AC-8/D7): bei fehlender/kaputter `user.json` bleibt Premium-SMS verweigert — Absicht, nicht
  Bug. Diese Sicherheitsrichtung darf der Fix **nicht** umkehren, nur laut machen.

## Dependencies

- **Upstream:** `internal/store/user.go` (`LoadUser`, bereits korrekt), `app.loader.get_data_dir`
  (Python, liefert Pfad zu `<data_root>/users/<id>/`).
- **Downstream:**
  - `LoginHandler` wird vom Frontend-Login-Formular aufgerufen (SvelteKit `/login`-Action).
  - `user_tier.py`-Funktionen werden von Alarm-Versand (`daily_alert_limit`), SMS-Kanal
    (`sms_allowed`) und Premium-SMS-Kanal (`premium_sms_allowed`) konsumiert — direkte
    Kanal-Verfügbarkeit hängt daran.
  - `email.py`-Allowlist wird vom gesamten Mail-Versandpfad genutzt (positive Filterliste,
    #1219).

## Existing Specs

- `docs/specs/modules/issue_1069_tier_channel_gating.md` (Archiv) — ursprüngliches
  Tier-Gating-Modell, relevant für Vokabular (`free`/`standard`/`premium`).
- Kein bestehender Spec zu Fehlerbehandlung bei kaputten `user.json`-Dateien — Neuland für
  diese spezifische Zusicherung.

## Risks & Considerations

- **Sicherheitsrichtung nicht umkehren:** `premium_sms_allowed()` muss bei kaputter Datei
  weiterhin `False` liefern (fail-closed bleibt korrekt) — der Fix fügt nur Logging hinzu,
  ändert nicht den Rückgabewert.
- **Kein User-Enumeration-Leak:** Client-Antwort bei Login bleibt generisch (401
  `invalid credentials`) für sowohl „nicht gefunden" als auch „defekt" — nur serverseitiges
  Log unterscheidet.
- **Scope-Entscheidung nötig in `/20-analyse`:** Die 8 weiteren Go-Callsites mit identischem
  Muster sind NICHT Teil der Issue-Beschreibung (#1596 nennt nur `LoginHandler`). Ratsche vs.
  gezielter Fix nur an der beschriebenen Stelle — Nebenbefund-Triage-Frage für die Analyse-Phase,
  kein automatisches Ausweiten.
- **Prüfbarer Nachweis laut Issue:** Test mit vorhandener, aber unlesbarer/defekter `user.json`
  muss belegen: Login liefert nicht mehr stumm 401 (sondern loggt), Tier fällt nicht mehr
  unbemerkt zurück. Mutation „Fehler zurück in den alten Zweig" muss einen Test rot machen.
- **Relevanz für KHW-Wanderung (PO, 2026-08-11):** Betrifft PO's eigenes Konto, exakt dieser
  Fehler ist ihm bereits einmal passiert (2026-08-07/08). Stiller Tier-Rückfall würde Premium-SMS
  kappen — der einzige Kanal, der an der KHW-Hütte ankommt (nur Satellit). Zeitdruck: Tour ab
  ca. 2026-08-20.

## Analysis

### Type

Bug — kein Regressions-Bruch. `git log -L` über `internal/store/user.go` zeigt: `LoadUser()`
unterscheidet seit dem Ursprungscommit `19a41682` korrekt fehlend/defekt; `LoginHandler` kollabiert
seit demselben Commit beide Fälle. Design-Lücke seit Tag 1, nie durch einen späteren Commit
eingeführt.

### Tatsächlicher Musterumfang (3 parallele Investigator-Agenten, verifiziert)

Deutlich breiter als der Issue-Text wörtlich nennt:

- **Go**, `err != nil || user == nil` → identische Fehlerantwort, kein Log: `auth.go` (9 Stellen,
  davon `LoginHandler` Z.132-138 = PO-Vorfall), `telegram_connect.go` (3), `passkey.go` (6),
  `premium_sms_connect.go` (1, in Schleife mit `continue`). **19 Stellen gesamt.**
- **Go, bewusst NICHT anfassen:** `internal/scheduler/tier_request_health.go:34-38` — explizit
  dokumentiertes Fail-Soft (Aggregat-Job darf an einem kaputten Profil nicht crashen).
- **Python**, identisches Muster, kein Log: `user_tier.py` (3 Funktionen), `email.py:239-284`
  (Allowlist), `config.py` (`is_test_user_id`, `with_user_profile`), `loader.py` (2
  Reverse-Lookups). **6 Dateien gesamt.**

### Affected Files (Scope-Entscheidung: nur die 3 im Issue benannten Stellen)

| File | Change Type | Description |
|------|-------------|--------------|
| `internal/handler/auth.go` | MODIFY | `LoginHandler` Z.132-138: `err != nil`-Zweig von `user == nil`-Zweig trennen, `log.Printf` im Fehlerfall (Konvention aus derselben Datei, z. B. Z.290/634). Client-Antwort (401, generischer Body) bleibt in beiden Zweigen identisch. |
| `internal/handler/auth_test.go` | MODIFY | Neuer Testfall: defekte (nicht fehlende) `user.json` → Log-Assertion, Statuscode unverändert 401. |
| `src/services/user_tier.py` | MODIFY | `import logging` ergänzen (Datei hat aktuell keinen Logger); in allen drei `except (JSONDecodeError, OSError)`-Zweigen `logger.warning(...)` mit Pfad ergänzen. Rückgabewerte unverändert — `premium_sms_allowed()` bleibt fail-closed. |
| Zugehöriger Python-Testfall | CREATE/MODIFY | Bestehende Testdatei für `user_tier.py` finden und erweitern (Namensregel: nach Verhalten, nicht Issue-Nummer). |
| `src/output/channels/email.py` | MODIFY | `_load_resend_allowlist` Z.271-273: `logger.warning(...)` im `except`-Zweig ergänzen, `continue`-Verhalten unverändert. |

**Bewusst außerhalb des Scopes** (Nebenbefund-Triage, PO-Vorgabe „keine Bevormundung" — #1596
begrenzt sich explizit auf drei Stellen): die 8 weiteren Go-Aufrufstellen und die weiteren
Python-Dateien (`config.py`, `loader.py`) tragen denselben strukturellen Fehler, sind aber nicht
Teil des PO-Auftrags vom 2026-08-08. Nach Abschluss als Checkbox-Zeilen mit `file:line` in #1199
buchen, kein Auto-Fix, keine Konsolidierung zu einem Helper (siehe Risiko unten).

### Scope Assessment

- Files: 3 Kern-Dateien + 2 Testdateien
- Estimated LoC: +~30/-~10 (additiv: Logging + Zweig-Trennung, keine Verhaltensänderung sonst)
- Risk Level: MEDIUM — Auth-kritischer Pfad, aber externes Verhalten (Statuscode, Body, Timing)
  bleibt unverändert; einziges echtes Risiko ist eine versehentliche Umkehrung von fail-closed.

### Technical Approach

- **Go:** Kein gemeinsamer Helper für eine einzelne Stelle — Zweig direkt in `LoginHandler`
  auftrennen, bestehende `log.Printf("<context>: <was> for %s: %v", ...)`-Konvention aus
  derselben Datei übernehmen.
- **Python (`user_tier.py`):** Logger neu einführen (Datei hat aktuell keinen), Konvention aus
  `alert_state.py`/`alert_gate.py` übernehmen. **Bewusst KEIN gemeinsamer Helper für die drei
  Tier-Funktionen** — `premium_sms_allowed()` delegiert absichtlich nicht an `sms_allowed()`
  (sonst stille Rechte-Ausweitung), eine Konsolidierung würde diese Trennung aufweichen.
- **Python (`email.py`):** Isolierte Ergänzung im bestehenden `except`-Zweig, kein struktureller
  Umbau.

### Dependencies

Go-Fix und Python-Fix sind vollständig unabhängig (getrennte Prozesse, kein gemeinsamer Code,
keine Reihenfolge nötig). Innerhalb Python sind `user_tier.py` und `email.py` unabhängig
voneinander.

### Leitplanken für die Spec (aus Strategie-Bewertung)

1. `premium_sms_allowed()` bleibt fail-closed — Log-Call ist rein additiv, Rückgabewert-Zweige
   unangetastet. Mutations-Pflichtfrage: Rückgabewert im `except`-Zweig kippen → muss Test rot
   machen.
2. Mutations-Pflichtfrage: Log-Call entfernen → muss ebenfalls Test rot machen (beweist, dass der
   Log-Call selbst geprüft wird, nicht nur das Rückgabeverhalten).
3. Client-seitiges Verhalten (Statuscode, Response-Body, Timing) darf sich an keiner der drei
   Stellen ändern — nur das Server-Log gewinnt eine neue Aussage.

### Open Questions

- [ ] Keine — Scope, Ansatz und Sicherheits-Leitplanken sind durch die Analyse geklärt.
