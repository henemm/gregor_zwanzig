# Context: F76 Konto erweitern

## Request Summary
Die Konto-Seite soll laut Issue #76 erweitert werden um: Kanäle einrichten, gespeicherte Templates verwalten, System-Status integrieren.

## Ist-Zustand (bereits implementiert!)

Die Account-Seite (`frontend/src/routes/account/`) hat bereits:

| Feature | Status | Details |
|---------|--------|---------|
| **Profil** | Done | Username, Mitglied seit |
| **Kanäle** | Teilweise | E-Mail, Signal (+API Key), Telegram funktionieren. SMS + Satellite sind disabled Platzhalter ("Kommt bald") |
| **Passwort** | Done | Ändern mit alter/neuer Bestätigung |
| **Deine Reports** | Done | Scheduler-Status (Morgen/Abend/Trip-Checks) mit last_run/next_run |
| **Dein Account** | Done | Zähler (Trips/Abos/Locations), Kanal-Badges, Wetter-Modelle pro Location |
| **Verfügbarkeit** | Done | Health-Check mit ok/degraded/offline |
| **Wetter-Templates** | Read-only | Zeigt System-Templates mit Metrik-Anzahl, kein CRUD |
| **Account löschen** | Done | Gefahrenzone mit Bestätigung |

## Was fehlt tatsächlich?

1. **Templates verwalten** — Aktuell nur read-only Anzeige der System-Templates. Laut Issue: "gespeicherte Templates verwalten" = User soll eigene Templates aus Trips/Orts-Vergleichen speichern und verwalten können
2. **SMS/Satellite** — Nur disabled Platzhalter. Backend-Infrastruktur fehlt (kein SMS-Provider, kein Satellite-Integration)
3. **Kanal-Test** — Kein "Test senden" Button um zu prüfen ob Kanal funktioniert

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/account/+page.svelte` | Hauptseite — 498 Zeilen, alle Sections |
| `frontend/src/routes/account/+page.server.ts` | SSR Data Loading — profile, scheduler, health, templates, trips, subscriptions, locations |
| `src/app/metric_catalog.py` | WEATHER_TEMPLATES Registry (7 System-Templates) |
| `src/outputs/email.py` | E-Mail Output |
| `src/outputs/signal.py` | Signal Output via Callmebot |
| `src/outputs/telegram.py` | Telegram Output |
| `docs/specs/modules/weather_templates.md` | Template-Spec (Phase A draft) |
| `docs/specs/modules/account_page.md` | Account-Spec (F61, implemented) |
| `docs/specs/modules/account_page_extend.md` | Account-Erweiterung (F72/F73 draft) |
| `docs/specs/modules/user_profile_channels.md` | Channel-Config Struktur |

## Existing Patterns
- Kanäle werden im Go-Auth-System als Profil-Felder gespeichert (mail_to, signal_phone, signal_api_key, telegram_chat_id)
- Templates kommen aus Python metric_catalog.py, werden über Go-API proxied
- User-Daten liegen in `data/users/{user_id}/`

## Risks & Considerations
- SMS und Satellite haben kein Backend — nur UI-Platzhalter sinnvoll
- Custom Templates brauchen Persistenz (wo? user.json? eigene Datei?)
- Template-CRUD braucht neue API-Endpoints (Go + Python)
