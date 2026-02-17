# Context: F6 Trip-Umplanung per Kommando

## Request Summary
Wanderer soll unterwegs — ohne Web-UI — per E-Mail-Reply oder SMS-Reply Befehle an den Trip senden koennen. Erste User Story: "Ruhetag heute" verschiebt alle Folge-Etappen um +1 Tag.

## Related Files

### Trip Data Model & Persistence
| File | Relevance |
|------|-----------|
| `src/app/trip.py` | Trip, Stage, Waypoint dataclasses — Stage.date muss verschoben werden |
| `src/app/models.py` | DTOs (UnifiedWeatherDisplayConfig, TripReportConfig etc.) |
| `src/app/loader.py` | CRUD: load_trip, save_trip, delete_trip — Persistenz nach Umplanung |

### Report Pipeline (wird durch Umplanung beeinflusst)
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py` | Orchestrator: Trip → Segments → Weather → Email. Waehlt Stage nach Datum. |
| `src/services/segment_weather.py` | Fetches weather per TripSegment |
| `src/formatters/trip_report.py` | TripReportFormatter: generiert HTML/plain-text Email |
| `src/web/scheduler.py` | APScheduler cron jobs (hourly reports, 30min alerts) |

### Web UI (Trip Cards)
| File | Relevance |
|------|-----------|
| `src/web/pages/trips.py` | Trip CRUD UI, Button-Handlers (Factory Pattern) |
| `src/web/pages/report_config.py` | Report scheduling config dialog |
| `src/web/pages/weather_config.py` | Metric selection dialog |

### Email Output (nur Senden, kein Empfang!)
| File | Relevance |
|------|-----------|
| `src/outputs/email_output.py` | EmailOutput.send() — nur SMTP outbound |
| `tests/tdd/test_html_email.py` | E2E Email-Tests mit IMAP-Abruf |

## Existing Patterns

1. **Stage-Datum als Planungs-Grundlage:** Der Report-Scheduler waehlt die Stage, deren `date` zum Report-Datum passt (`_convert_trip_to_segments(trip, target_date)`). Verschieben der Stage-Daten aendert automatisch, welche Stage wann reported wird.

2. **Trip-Save-Pattern:** `loader.save_trip(trip, user_id="default")` schreibt Trip als JSON. Alle Configs (display_config, report_config) bleiben erhalten.

3. **Factory Pattern (Safari):** Alle UI-Buttons nutzen `make_<action>_handler()` Pattern.

4. **Scheduler-Integration:** APScheduler laeuft in `web/scheduler.py`, prueft stuendlich welche Trips Reports brauchen.

## Dependencies

### Upstream (was F6 nutzen wird)
- `loader.py` — Trip laden und nach Datum-Shift speichern
- `trip.py` — Stage.date Felder modifizieren
- E-Mail-Empfang (IMAP) — **EXISTIERT NOCH NICHT**, muss neu gebaut werden
- SMS-Empfang — **EXISTIERT NOCH NICHT** (F1 ist Voraussetzung)

### Downstream (was von F6 beeinflusst wird)
- `trip_report_scheduler.py` — waehlt Stage nach Datum, neue Daten = neuer Report
- `trip_alert.py` — Alert-Snapshots beziehen sich auf Stage-Daten
- `weather_snapshot.py` — gespeicherte Snapshots werden durch Datum-Shift ungueltig

## Existing Specs
| Spec | Status | Relevanz |
|------|--------|----------|
| `docs/specs/trip_edit.md` | approved | Trip-Edit-Dialog (UI-basiert, nicht command-basiert) |
| `docs/specs/modules/trip_report_scheduler.md` | implemented | Report-Scheduling, Date-Matching-Logik |
| `docs/specs/modules/trip_alert.md` | implemented | Alert-Service, Snapshot-Vergleich |
| **Kein F6-Spec** | - | Muss noch geschrieben werden |

## Roadmap-Eintrag (aus epics.md)

```
Epic: Asynchrone Trip-Steuerung
Goal: Trip unterwegs per Kommando anpassen — ohne Web-UI
Business Value: Innovativstes Feature. Asynchrone Steuerung per SMS/Email-Reply.

User Story:
- "Ruhetag heute" → Folge-Etappen +1 Tag verschieben
- Email-Reply und SMS-Reply als Input-Kanal
- Bestaetigung per SMS/Email
```

## Risks & Considerations

1. **IMAP-Polling vs Webhook:** Fuer Email-Reply braucht es einen IMAP-Polling-Dienst (kein Webhook bei Gmail). Muss als Background-Job im Scheduler laufen.

2. **Command-Parsing:** Natuerlichsprachige Befehle ("Ruhetag heute", "Rest day") erfordern robustes Parsing. Alternativ: strenge Syntax (z.B. `RUHETAG 2026-02-17` oder `+1`).

3. **Snapshot-Invalidierung:** Wenn Etappen verschoben werden, sind gespeicherte Weather-Snapshots (fuer Alert-Vergleich) ungueltig. Muessen geloescht oder neu erzeugt werden.

4. **Authentifizierung:** Wer darf Befehle senden? Aktuell nur ein User ("default"). Bei Email-Reply: Absender-Adresse pruefen.

5. **Idempotenz:** Was passiert bei doppeltem "Ruhetag heute"? Shift +2 oder ignorieren? Braucht eine Command-History.

6. **SMS-Kanal (F1):** SMS-Reply ist in der User Story, aber F1 (SMS-Kanal) existiert noch nicht. Email-Reply ist der realistische Einstieg.

7. **Bestaetigung:** User erwartet Bestaetigung per Email/SMS. Der bestehende EmailOutput kann dafuer wiederverwendet werden.
