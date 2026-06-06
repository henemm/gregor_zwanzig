# Spec: Signal app-weit als Kanal entfernen — Backend (#610, Schritt 2/2)

**Status:** In Arbeit
**Created:** 2026-06-06
**Issue:** #610 (Schritt 2/2; Schritt 1/2 Frontend bereits live: 3675fd0d)
**Kontext:** #590 hat backend-seitig bereits `SignalOutput`/`outputs/signal.py`, `Settings.signal_phone` und `can_send_signal()` entfernt. Übrig blieb **toter/baumelnder Signal-Code** (würde bei Ausführung crashen) + Renderer-Pfade + deprecated Modellfeld. Dieser Schritt entfernt die Reste app-weit. Kanäle danach: **Email · Telegram · SMS**.

## Scope

Entfernen aller **Signal-Kanal**-Reste im Backend (Python `src/`, `api/`). **Nicht** angefasst: Unix-`signal`/`SIGTERM` o.ä. **Nicht** in diesem Schritt: Telegram-Budget/PRIMARY_SLOTS auf 8 (gehört zu #587).

Betroffen (aus Analyse): `src/outputs/base.py` (signal-Factory-Zweig + dangling `from outputs.signal import`), `api/routers/scheduler.py` (toter `if sub.send_signal`/`can_send_signal`-Block), `src/output/renderers/channel_layout.py` (signal in CHANNEL_LIMITS + Kommentare), `src/output/renderers/narrow.py` (signal-Breite/-Zweige; telegram bleibt), `src/formatters/trip_report.py` (`signal_text`-Aufbau), `src/app/models.py` (`signal_text`-Feld — schema-relevant), `src/app/cli.py` (`signal`-Choice), `api/routers/preview.py` (`/api/preview/{trip}/signal`), `src/services/preview_service.py` (`render_signal_preview`), `api/routers/validator.py` (Channel-Beschreibung).

## Acceptance Criteria

**AC-1:** Given die Output-Factory in `outputs/base.py`, When ein Kanal angefordert wird, Then existiert kein `signal`-Zweig und kein Import von `outputs.signal` mehr; ein Versuch `get_output("signal")` wird nicht unterstützt (kein dangling Import, kein Crash-Pfad).

**AC-2:** Given der Scheduler-Versandpfad (`api/routers/scheduler.py`), When ein Briefing versendet wird, Then existiert kein Signal-Block mehr (keine Referenz auf `send_signal`, `can_send_signal`, `SignalOutput`); Email/Telegram/SMS-Versand bleibt funktional.

**AC-3:** Given die Renderer `channel_layout.py` und `narrow.py`, When für einen Kanal gerendert wird, Then ist `signal` kein gültiger Kanal mehr (kein Eintrag in CHANNEL_LIMITS, keine signal-Breite); `render_narrow("telegram", …)` und Email-Rendering funktionieren unverändert.

**AC-4:** Given `trip_report.py` und die CLI, When ein Report gebaut bzw. die CLI mit `--channel` aufgerufen wird, Then wird kein `signal_text` mehr erzeugt und `signal` ist keine gültige `--channel`-Option mehr.

**AC-5:** Given der Vorschau-Endpoint, When `/api/preview/{trip_id}/signal` aufgerufen wird, Then existiert die Route nicht mehr (404); `render_signal_preview` ist entfernt; Email-/Telegram-Vorschau funktionieren weiter.

**AC-6:** Given ein gespeicherter Trip/Report-Datensatz mit altem `signal_text`/`send_signal`-Feld, When er geladen, migriert und wieder gespeichert wird, Then lädt er **fehlerfrei** (Altfeld wird ignoriert, kein Crash) und **kein anderes Feld geht verloren** (Roundtrip-Vergleich); das Modell hat kein `signal_text` mehr.

**AC-7:** Given die Test-Suite, When `uv run pytest` läuft, Then keine **neuen** Failures ggü. Baseline; die bestehenden #590-Signal-Removal-Tests bleiben grün; Briefing-Rendering für Email/Telegram/SMS unverändert korrekt.

## Verifikation (mock-frei)

- Echte `uv run pytest` (Baseline-Vergleich, keine neuen Failures) — AC-7.
- Echter Roundtrip: realer Trip-JSON mit `signal_text`/`send_signal` laden → migrieren → speichern → laden → Feld-Diff (nur signal-Felder weg, Rest identisch) — AC-6.
- Echter Render-Aufruf `render_narrow("telegram", …)` + Email-Render liefern korrekte Ausgabe — AC-3/AC-7.
- Staging nach Deploy: `/api/preview/{trip}/signal` → 404; `/api/health` 200 — AC-5.
- Daten-Schema-Pflicht: automatischer `data_schema_backup`-Snapshot vor `models.py`-Edit; Read-Modify-Write (Merge), keine Sibling-Felder zerstören.

## Out of Scope
- Telegram-Budget/PRIMARY_SLOTS auf 8 (#587)
- Frontend-Signal (Schritt 1/2, bereits live)
- Aktualisierung der CLAUDE.md-Notiz „Signal als Channel (Feature-Idee)" (separater Doku-Edit nach Abschluss)
