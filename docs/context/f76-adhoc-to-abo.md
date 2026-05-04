# Context: F76 Ad-hoc → Abo

## Request Summary
Aus einem Orts-Vergleich-Ergebnis soll der User direkt ein Auto-Report-Abo erstellen können ("Als Auto-Report speichern"). Die Vergleichs-Parameter (Locations, Zeitfenster, Forecast-Stunden, Aktivitätsprofil) werden vorausgefüllt.

## Daten-Mapping

| Compare-Parameter | Subscription-Feld | Mapping |
|---|---|---|
| location_ids | locations | Direkt |
| time_window_start/end | time_window_start/end | Direkt |
| forecast_hours | forecast_hours | Direkt |
| activity_profile | activity_profile | Direkt |
| target_date | — | Nicht übernommen (Abo ist recurring) |
| — | name | User-Eingabe nötig |
| — | schedule | User-Eingabe nötig (daily_morning/daily_evening/weekly) |
| — | send_email/signal/telegram | Defaults aus Profil |
| — | top_n | Default 3 |
| — | include_hourly | Default false |

## Related Files

| File | Relevance |
|------|-----------|
| frontend/src/routes/compare/+page.svelte | Compare-Seite — hier kommt der Button hin |
| frontend/src/routes/compare/+page.server.ts | Lädt Locations, Subscriptions, Templates |
| frontend/src/lib/components/SubscriptionForm.svelte | Bestehende Abo-Form — muss pre-fill unterstützen |
| frontend/src/routes/subscriptions/+page.svelte | Abo-Liste — Referenz für CRUD-Pattern |
| internal/handler/subscription.go | Go CRUD Handler — bereits komplett |
| internal/model/subscription.go | CompareSubscription Model |
| api/routers/compare.py | Python Compare-Backend |

## Existing Patterns
- SubscriptionForm.svelte hat bereits alle Felder und Validierung
- POST /api/subscriptions akzeptiert komplettes CompareSubscription JSON
- Keine Backend-Änderungen nötig — rein Frontend

## Risks & Considerations
- SubscriptionForm ist für eigene Seite designed — muss als Dialog/Modal auf Compare-Seite funktionieren
- Location-IDs im Compare kommen als Query-Params, im Abo als String-Array
- Name muss eindeutig sein (ID wird aus Name generiert)
