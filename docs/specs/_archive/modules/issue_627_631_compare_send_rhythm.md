---
entity_id: issue_627_631_compare_send_rhythm
type: module
created: 2026-06-07
updated: 2026-06-07
status: completed
version: "1.0"
tags: [compare, scheduler, multi-user, frontend, go-proxy]
---

# Compare-Preset: Einzel-Sofortversand (#627) + Wochen-Rhythmus erhalten (#631)

## Approval

- [x] Approved

## Purpose

Zwei Folge-Issues aus #626 am Compare-Preset-Listenmenü:
- **#627:** Kebab-Aktion „Briefing jetzt senden" löst das Vergleichs-Briefing sofort an die konfigurierten Empfänger aus (echter Versand statt Stub).
- **#631:** Pausieren/Reaktivieren eines Vergleichs erhält den Wochen-Rhythmus (`weekly`) statt ihn auf `daily` zurückzusetzen.

## Source

- **File (#627 Python):** `api/routers/scheduler.py` — neue Funktion `_send_compare_preset` + Endpoint `POST /api/scheduler/compare-presets/{id}/send`
- **File (#627 Go):** `internal/handler/compare_preset.go` `SendComparePresetHandler` → Proxy; Route in `cmd/server/main.go`
- **File (#627/#631 Frontend):** `frontend/src/lib/components/compare/subscriptionHelpers.ts`, `CompareGrid.svelte`, `CompareTabs.svelte`
- **File (#631 Go):** `internal/model/compare_preset.go` `ComparePreset` (+ `previous_schedule`)
- **File (#631 Python):** `api/routers/scheduler.py` / Persistenz-Pfad (Feld durchreichen)

## Estimated Scope

- **LoC:** ~180–230 produktiv (Tests zusätzlich, zählen mock-frei mit)
- **Files:** ~7
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_run_compare_presets_daily` | Python | Versandlogik-Quelle, aus der der Einzelversand extrahiert wird |
| `SendSubscriptionProxyHandler` | Go | Vorbild POST-Proxy mit `{id}` + `appendUserID` |
| `appendUserID` | Go | Anti-Spoofing user_id-Durchreichung (Bug #200) |
| `ComparisonEngine` / `render_compare_html` / `EmailOutput` | Python | Erzeugen + Versenden des Vergleichs |
| `deriveStatusFromPreset` / `compareActions` | Frontend | Status-Ableitung + Kebab-Menü |

## Implementation Details

### #627 — Einzel-Sofortversand

```
Python (scheduler.py):
  _send_compare_preset(user_id, preset_id, data_root=None) -> dict
    - lädt compare_presets.json[user_id], findet preset_id (404 wenn fehlt)
    - IGNORIERT schedule (sendet auch bei manual/weekly/pausiert) — Knopfdruck ≠ Zeitplan
    - empfaenger-Check + mail_to-Fallback (wie Daily); kein Empfänger → Fehler (kein stiller Skip)
    - ComparisonEngine.run → render_compare_html + render_comparison_text → EmailOutput.send
    - _save_preset_status(user_id, preset_id, top_ort)
    - return {"status":"ok","winner":top_ort,"empfaenger_count":N}
  Endpoint: POST /api/scheduler/compare-presets/{id}/send?user_id=...
    - 404 wenn Preset fehlt; 400/422 wenn kein Empfänger; 200 mit Ergebnis

Go (compare_preset.go):
  SendComparePresetHandler → Proxy (Vorbild SendSubscriptionProxyHandler)
    - chi.URLParam(id) + appendUserID(query, UserIDFromContext)  ← ECHTE user_id
    - POST PythonURL + /api/scheduler/compare-presets/{id}/send
    - Status + Body 1:1 durchreichen; 120s Timeout
  HINWEIS: braucht pythonURL — Handler-Signatur ggf. auf (pythonURL string) ändern,
  Route in cmd/server/main.go:221 entsprechend anpassen.

Frontend:
  subscriptionHelpers.compareActions: 'send'-Eintrag { id:'send', label:'Briefing jetzt senden' }
    wieder aufnehmen (oben, vor 'preview')
  CompareGrid.handleAction: id==='send' → sendBriefing(preset)
  sendBriefing: ConfirmDialog "Briefing jetzt an N Empfänger senden?" (N = empfaenger.length)
    → bei Bestätigung POST /api/compare/presets/{id}/send
    → Erfolg: Erfolgs-/Fehlerhinweis; Fehler: error-State
```

### #631 — Wochen-Rhythmus erhalten

```
Go (model/compare_preset.go):
  + PreviousSchedule string `json:"previous_schedule,omitempty"`  // additiv, omitempty
  Altdaten ohne Feld → "" (kein Datenverlust, keine Migration nötig außer Roundtrip-Beweis)
  Erhalt server-managed in Update-Handler (wie LetzterVersand): nicht aus leerem
  Request-Body überschreiben, wenn Body das Feld nicht trägt — Read-Modify-Write.

Frontend (Quelle der Pause/Reaktivier-Logik):
  CompareGrid.togglePause:
    - Pausieren: nextSchedule='manual', previous_schedule = aktuelles schedule (≠ 'manual')
    - Reaktivieren: nextSchedule = preset.previous_schedule || 'daily'
    - PUT trägt schedule + previous_schedule
  CompareTabs.handleToggleActive:
    - previousSchedule-State initial aus preset.previous_schedule (überlebt Reload)
    - beim Pausieren previous_schedule mit-persistieren
  types.ts ComparePreset: + previous_schedule?: string
```

## Expected Behavior

- **Input #627:** Klick „Briefing jetzt senden" → Confirm → POST.
- **Output #627:** E-Mail an alle `empfaenger` des Presets des **eingeloggten** Nutzers; 200 mit Winner.
- **Side effects #627:** `letzter_versand` + `top_ort_letzter_versand` aktualisiert.
- **Input #631:** wöchentliches Preset pausieren, dann reaktivieren.
- **Output #631:** `schedule` ist wieder `weekly` (nicht `daily`); persistent über Reload.

## Acceptance Criteria

- **AC-1:** Given ein Preset mit 2 Empfängern des eingeloggten Nutzers / When `POST /api/compare/presets/{id}/send` aufgerufen wird / Then werden beide Empfänger per E-Mail beliefert und die Antwort ist HTTP 200 mit Winner-Ort.
  - Test: Echter HTTP-POST gegen Go-API → IMAP-Prüfung (Stalwart `gregor-test@henemm.com`), dass die Vergleichs-Mail ankommt; Antwort-JSON enthält `status:ok`.
- **AC-2:** Given Nutzer A und Nutzer B haben je ein eigenes Preset mit unterschiedlichen Empfängern / When Nutzer A `POST .../{A-preset}/send` auslöst / Then geht die Mail ausschließlich an A's Empfänger und Nutzer B erhält nichts (keine `user_id="default"`-Vermischung).
  - Test: Zwei reale Nutzer (Auth-Kontext), POST als A, IMAP/Versand-Mitschnitt beweist nur A's Empfänger; B's Preset unberührt.
- **AC-3:** Given ein Preset mit `schedule='manual'` (pausiert) / When „Briefing jetzt senden" ausgelöst wird / Then wird trotzdem sofort versendet (Sofortversand ignoriert den Zeitplan).
  - Test: Realer POST auf pausiertes Preset → Versand erfolgt, HTTP 200.
- **AC-4:** Given ein Preset ohne Empfänger und ohne `mail_to`-Fallback / When „Briefing jetzt senden" ausgelöst wird / Then antwortet der Endpoint mit Fehler (kein HTTP 200, keine stille Erfolgsmeldung).
  - Test: Realer POST → Statuscode ≥ 400, keine Mail versendet.
- **AC-5:** Given die Compare-Liste mit einem aktiven Preset / When der Nutzer das Kebab-Menü öffnet und „Briefing jetzt senden" wählt / Then erscheint eine Rückfrage „Briefing jetzt an N Empfänger senden?" mit korrekter Empfänger-Anzahl, bevor gesendet wird.
  - Test: Playwright gegen Staging als eingeloggter Nutzer — Menüeintrag sichtbar, Klick öffnet Confirm-Dialog mit Empfänger-Zahl.
- **AC-6:** Given ein **wöchentliches** Preset (`schedule='weekly'`) / When es über das Listen-Menü pausiert und danach wieder aktiviert wird / Then ist `schedule` wieder `weekly` (nicht `daily`).
  - Test: Playwright/HTTP — pausieren (`schedule='manual'`, `previous_schedule='weekly'` persistiert), reaktivieren → GET zeigt `schedule='weekly'`.
- **AC-7:** Given das wöchentliche Preset aus AC-6 wurde pausiert / When die Seite neu geladen und dann reaktiviert wird / Then bleibt der Rhythmus `weekly` erhalten (Backend-Feld überlebt Reload, nicht nur Session-State).
  - Test: HTTP-Roundtrip — pausieren, Preset frisch laden (neuer Request), reaktivieren → `weekly`.
- **AC-8:** Given ein bestehendes Preset ohne `previous_schedule`-Feld (Altdaten) / When es geladen, gespeichert und erneut geladen wird / Then bleiben alle vorhandenen Felder unverändert erhalten (kein Datenverlust durch das additive Feld).
  - Test: Roundtrip — Altdaten-JSON laden → speichern → neu laden → Feld-für-Feld-Vergleich identisch (Stage-/Empfänger-/Schedule-Erhalt).
- **AC-9:** Given die Detail-Ansicht eines wöchentlichen Vergleichs (CompareTabs) / When dort pausiert und reaktiviert wird / Then verhält sie sich identisch zur Liste (Rhythmus bleibt `weekly`).
  - Test: Playwright gegen Staging — Detail-Ansicht pausieren/reaktivieren → `weekly` erhalten.

## Out of Scope

- Telegram-/SMS-Versand des Compare-Briefings auf Knopfdruck (Endpoint sendet wie der Daily-Scheduler nur E-Mail).
- Änderung der Daily-/Weekly-Scheduler-Fälligkeitslogik.
