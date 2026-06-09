---
entity_id: issue_670_inbound_keywords
type: module
created: 2026-06-09
updated: 2026-06-09
status: draft
version: "1.0"
tags: [inbound, email, telegram, scheduler, trip_command_processor, mandantentrennung]
---

# Antwort-Kommandos als echte Inbound-Keywords (PAUSE/SKIP/STOP/STATUS/CONFIG/HELP)

## Approval

- [x] Approved

## Purpose

E-Mail-Antworten (und der gemeinsame Telegram-Inbound-Pfad) sollen Aktionen per **bloßem
Schlüsselwort am Zeilenanfang** auslösen — ohne `###`-Präfix. `PAUSE <dauer>` pausiert
Briefings, `SKIP` überspringt den nächsten geplanten Versand, `STOP` deaktiviert dauerhaft,
`STATUS`/`HELP` mappen auf den Bestand, `CONFIG` liefert einen Einstellungs-Link. Damit
`PAUSE`/`SKIP`/`STOP` überhaupt wirken, wird der Scheduler-Sende-Pfad erstmals an
`report_config.enabled`/`paused_until`/`skip_next` gegated (behebt den latenten STOP-Bug).

## Source

- **File:** `src/services/trip_command_processor.py` — **Identifier:** `TripCommandProcessor._parse_command`, `_VALID_COMMANDS`, neue Handler `_apply_pause`/`_apply_skip` (`STOP` nutzt `_cancel_trip`, `CONFIG` neuer `_show_config`)
- **File:** `src/app/models.py` — **Identifier:** `TripReportConfig` (+ `paused_until`, `skip_next`)
- **File:** `src/app/loader.py` — **Identifier:** `report_config`-De-/Serialisierung
- **File:** `src/services/trip_report_scheduler.py` — **Identifier:** `_get_active_trips` (Gating)
- **File:** `src/output/renderers/email/html.py` — **Identifier:** `render_html` (Block „Antwort-Kommandos")

Schicht: **Python-Backend** (FastAPI Core). Kein Go-, kein SvelteKit-Code betroffen
(E-Mail wird serverseitig in Python gerendert).

## Estimated Scope

- **LoC:** ~180–220 (Code in `src/`) → **LoC-Limit-Override auf 400** nötig
- **Files:** 5 Source-Dateien + Tests
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportConfig` (`models.py`) | Persistenz | Neue Felder `paused_until`, `skip_next` |
| `load_all_trips`/`save_trip` (`loader.py`) | Persistenz | Read-Modify-Write der Felder |
| `TripReportSchedulerService._get_active_trips` | Scheduler | Gating der geplanten Versände |
| `InboundEmailReader` / `InboundTelegramReader` | Inbound | Liefern `InboundMessage` an `process()` (unverändert) |

## Implementation Details

```
1. TripReportConfig (models.py):
   + paused_until: Optional[datetime] = None   # PAUSE: Briefings ruhen bis zu diesem UTC-Zeitpunkt
   + skip_next: bool = False                    # SKIP: einmaliges Überspringen des nächsten Versands

2. loader.py: beide Felder additiv de-/serialisieren.
   - Lesen: rc_data.get("paused_until") → datetime.fromisoformat falls vorhanden, sonst None;
            rc_data.get("skip_next", False).
   - Schreiben: paused_until.isoformat() falls gesetzt sonst None; skip_next: bool.
   - Rückwärtskompatibel: alte JSON ohne Felder → Defaults (None / False).

3. trip_report_scheduler.py _get_active_trips(): nach dem stage-Filter zusätzlich filtern:
   - report_config.enabled == False           → trip raus (STOP wirkt)
   - paused_until gesetzt und now() < paused_until → trip raus (PAUSE wirkt)
   - skip_next == True → trip raus FÜR DIESEN LAUF, Flag löschen (skip_next=False) und
     save_trip(user_id) → einmalig konsumiert (SKIP wirkt, chronologisch nächster Versand).
   Reihenfolge: enabled vor paused_until vor skip_next (SKIP wird nicht verbraucht, wenn
   ohnehin gestoppt/pausiert). now() = datetime.now(timezone.utc).
   On-Demand-Versand (send_test_report) bleibt ungegated.

4. trip_command_processor.py:
   a) _parse_command: zusätzlich zum ### -Pfad bloße Keywords am Anfang der ersten
      nicht-leeren Zeile erkennen (case-insensitiv). Mapping auf interne Keys:
        PAUSE  → ("pause", <rest als dauer-arg>)
        SKIP   → ("skip", None)
        STOP   → ("abbruch", None)        # Bestand
        STATUS → ("status", None)         # Bestand
        CONFIG → ("config", None)
        HELP   → ("hilfe", None)          # Bestand
      Der ###-Pfad und die deutschen Befehle bleiben unverändert (additiv).
   b) _VALID_COMMANDS += {"pause", "skip", "config"}.
   c) Dispatch:
        pause  → _apply_pause(trip, value, user_id): Dauer parsen (Nd Tage / Nh Stunden /
                 bare N = Tage). Ungültig/fehlend → Fehler-Bestätigung. Gültig →
                 paused_until = now + delta, save_trip, Bestätigung „pausiert bis <Datum/Zeit>".
        skip   → _apply_skip(trip, user_id): skip_next=True, save_trip, Bestätigung
                 „nächstes Briefing wird übersprungen". Idempotent (erneutes SKIP bleibt True).
        config → _show_config(trip): Bestätigung mit Link
                 https://gregor20.henemm.com/trips/<id> (kein Inline-Edit).
   d) _show_help / Hilfe-Text + Unbekannt-Fehlertexte um die neuen Keywords ergänzen.

5. html.py render_html: dedizierter Block „Antwort-Kommandos" (Info-Box-Optik,
   G_BOX_INFO_BG + G_ACCENT-Border) vor dem Footer, Desktop + Mobile sichtbar.
   Listet PAUSE/SKIP/STOP/STATUS/CONFIG/HELP mit Kurzbeschreibung. Die veraltete
   Footer-Befehlszeile (html.py:800) wird entfernt/auf den neuen Stand gebracht.

Mandantentrennung: Scheduler ist pro Nutzer instanziiert (self._user_id → load_all_trips
/ save_trip user-scoped). Processor verwendet msg.user_id (aus lookup_user_by_email, kein
default-Fallback bei Treffer) durch alle verändernden Pfade. Kein "default" in
authentifizierten Pfaden.
```

## Expected Behavior

- **Input:** E-Mail-Antwort mit erster nicht-leerer Zeile = Keyword (z. B. `PAUSE 2d`),
  Betreff enthält `[Trip-Name]`; Absender ist einem `user_id` zugeordnet.
- **Output:** Bestätigungs-Antwort (E-Mail/Telegram) mit `confirmation_subject`/`_body`;
  persistierte Zustandsänderung am `report_config` des betroffenen Trips.
- **Side effects:** `save_trip(user_id)` (paused_until/skip_next/enabled); SKIP konsumiert
  beim nächsten Scheduler-Lauf; keine Mutation für STATUS/HELP/CONFIG (read-only).

## Acceptance Criteria

- **AC-1:** Given ein Trip eines Nutzers mit aktivem `report_config` / When eine Inbound-Nachricht mit erster Zeile `PAUSE 2d` verarbeitet wird / Then ist `report_config.paused_until` persistiert auf ~jetzt+2 Tage, der nächste geplante Scheduler-Lauf liefert den Trip NICHT in `_get_active_trips`, und die Bestätigung nennt das Pausen-Ende-Datum.
  - Test: Echte `InboundMessage` durch `TripCommandProcessor().process()`, danach `load_all_trips(user_id)` prüfen (paused_until gesetzt) und `_get_active_trips` ruft den Trip nicht; nach Ablauf (paused_until in der Vergangenheit) erscheint er wieder.

- **AC-2:** Given ein Trip mit geplanten Etappen für heute UND morgen / When eine Nachricht mit erster Zeile `SKIP` verarbeitet wird / Then ist `skip_next=True` persistiert, der unmittelbar folgende `_get_active_trips`-Lauf lässt den Trip aus UND setzt `skip_next` zurück auf False (gespeichert), der darauffolgende Lauf liefert den Trip wieder.
  - Test: `process()` mit `SKIP`, dann zwei aufeinanderfolgende `_get_active_trips`-Aufrufe gegen echte Persistenz — erster ohne Trip + Flag zurückgesetzt, zweiter mit Trip.

- **AC-3:** Given ein Trip mit `report_config.enabled=True` / When eine Nachricht mit erster Zeile `STOP` verarbeitet wird / Then ist `enabled=False` persistiert und der Trip taucht in keinem folgenden `_get_active_trips`-Lauf mehr auf (STOP wirkt jetzt tatsächlich auf geplante Versände).
  - Test: `process()` mit `STOP`, danach `_get_active_trips` für morning UND evening — Trip fehlt in beiden; Bestätigung bestätigt Deaktivierung.

- **AC-4:** Given Bestands-Inbound mit `STATUS` bzw. `HELP` / When verarbeitet / Then liefert `STATUS` die Etappenübersicht (wie `status`) und `HELP` die Befehlsliste (wie `hilfe`), und der Hilfe-Text enthält die neuen Keywords PAUSE/SKIP/STOP/CONFIG. `CONFIG` liefert eine Bestätigung mit einem Link auf die Trip-Einstellungen (kein Inline-Edit, keine State-Mutation).
  - Test: Je eine `process()`-Verarbeitung; Assertions auf `confirmation_body`-Verhalten (Etappen vorhanden / Keyword-Liste / Link enthalten); danach `load_all_trips` zeigt unveränderten `report_config` (read-only).

- **AC-5:** Given zwei verschiedene Nutzer (A, B) mit je einem gleichnamigen-unabhängigen Trip / When Nutzer A `PAUSE 2d` (bzw. `STOP`) auslöst / Then ändert sich ausschließlich A's Trip; B's `report_config` bleibt unverändert (`paused_until=None`, `enabled=True`), und B's Trip bleibt in `_get_active_trips` aktiv. Keine `default`-Persistenz wird berührt.
  - Test: Zwei reale `user_id`-Verzeichnisse, `process()` mit `msg.user_id=A`; danach `load_all_trips(A)` vs. `load_all_trips(B)` vergleichen — nur A geändert, `data/users/default` unberührt. (Lehre #663.)

- **AC-6:** Given der bestehende `### key: value`-Pfad und die deutschen Befehle (`ruhetag`, `report`, `startdatum`, `status`, `hilfe`, `now`, Query-/Drilldown-Keys) / When eine entsprechende Nachricht verarbeitet wird / Then funktionieren sie unverändert (Bare-Keyword-Parsing ist rein additiv, keine Regression im Telegram- oder E-Mail-Pfad).
  - Test: Bestehende Processor-Tests bleiben grün; je ein `### ruhetag` und ein Query-Key (`glance`) liefern unverändertes Verhalten.

- **AC-7:** Given eine gerenderte Briefing-E-Mail / When der HTML-Body erzeugt wird / Then enthält er einen sichtbaren Block „Antwort-Kommandos" mit den sechs Keywords, sowohl im Desktop- als auch im Mobile-Markup, und die veraltete Footer-Befehlszeile ist entfernt/aktualisiert.
  - Test: `render_html(...)` erzeugen, Block-Sichtbarkeit Desktop (`.desktop-only` bzw. immer sichtbarer Abschnitt) und Mobile (kein `display:none` für diesen Block) prüfen; E2E via `email_spec_validator` gegen Staging-Mail (IMAP), keine Mocks.

- **AC-8:** Given eine Inbound-Nachricht mit `PAUSE` ohne/ungültige Dauer (z. B. `PAUSE xyz`) / When verarbeitet / Then erfolgt KEINE State-Mutation und die Bestätigung erklärt das erwartete Format (`PAUSE 2d` / `PAUSE 12h`).
  - Test: `process()` mit ungültiger Dauer; `load_all_trips` zeigt `paused_until=None`; `success=False` mit Format-Hinweis im Body.

## Known Limitations

- `CONFIG` ist bewusst auf einen Settings-Link beschränkt (kein Inline-Editieren per Mail) — Issue-Empfehlung; spätere Erweiterung möglich.
- `SKIP`-Semantik = chronologisch nächster geplanter Versand (morning ODER evening). Eine getrennte „nur morgens"/„nur abends"-Steuerung ist nicht Teil dieses Specs.
- Bare-Keyword-Erkennung nur am Anfang der ersten nicht-leeren Zeile; Keywords mitten im Fließtext lösen bewusst nichts aus (False-Positive-Schutz).
- E-Mail-Zustellung der Bestätigung ist best-effort (bestehendes Retry in `EmailOutput`); Persistenz-Änderung erfolgt unabhängig vom Zustell-Erfolg.

## Changelog

- 2026-06-09: Initial spec created (Issue #670)
