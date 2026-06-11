# Context: Issue #736 — Tab-Reorganisation Wetter-Metriken vs. Briefing-Zeitplan

## Request Summary
Die beiden Reiter "Wetter-Metriken" und "Briefing-Zeitplan" haben verwirrende Überlappungen (doppelter "Kanäle"-Abschnitt) und irreführende Beschriftungen ("SMS-Schwellwerte" gilt auch für E-Mail und Telegram).

## Ist-Zustand

### Tab "Wetter-Metriken" (`WeatherMetricsTab.svelte`)
| Abschnitt | Inhalt | Speichert in |
|-----------|--------|-------------|
| 01 Profil | Preset-Auswahl | display_config.preset_name |
| 02 Grundauswahl | welche Metriken aktiv | display_config.metrics |
| 03 Reihenfolge & Darstellung | Reihenfolge, Roh/Einfach | display_config.metrics |
| **04 Kanäle** | E-Mail/Telegram/SMS Master-Toggle | display_config.channels |
| **05 SMS-Schwellwerte** | Schwellwerte Wind/Böen/Niederschlag/Regenw. | display_config.metrics[].sms_threshold |

### Tab "Briefing-Zeitplan" (`BriefingScheduleTab.svelte` → `EditReportConfigSection.svelte`)
| Abschnitt | Inhalt | Speichert in |
|-----------|--------|-------------|
| Morgen-Report | aktivieren, Uhrzeit, Trend | report_config.morning_* |
| Abend-Report | aktivieren, Uhrzeit, Trend | report_config.evening_* |
| **Kanäle** | wohin schicken (Checkboxen) | report_config.send_email/telegram/sms |
| E-Mail-Inhalt | Format (full/compact), Inhalts-Bausteine | report_config.email_format, show_* |

## Das Problem (konkret)

### Problem 1: Doppelter "Kanäle"-Abschnitt
- Wetter-Metriken "04 Kanäle": Master-Switch, ob ein Kanal generell aktiv ist
- Briefing-Zeitplan "Kanäle": Checkboxen für diesen Report-Slot
- Technischer Zusammenhang: `display_config.channels` GATEST welche Checkboxen in Briefing-Zeitplan überhaupt erscheinen
- Nutzer versteht den Unterschied nicht → fragt sich: "Warum stelle ich Kanäle zweimal ein?"

### Problem 2: "SMS-Schwellwerte" — falsche Beschriftung
- `sms_threshold` fließt in `format_trend_tokens()` (`helpers.py:635-637`)
- Steuert `precip_token`, `wind_token`, `gust_token` — diese erscheinen in:
  - E-Mail HTML-Trends
  - Telegram-Nachrichten
  - SMS-Kurzform
- Auch Quick-Take-Chips/-Pillen in der E-Mail nutzen Schwellwerte (allerdings `alert_threshold`, nicht `sms_threshold`)
- Die Beschriftung "SMS-Schwellwerte" ist also irreführend — gilt für alle Kanäle

## Relevante Dateien
| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Routing, TABS-Array |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` | Wetter-Metriken-Tab (groß, ~770 LoC) |
| `frontend/src/lib/components/trip-detail/WeatherV2Kanaele.svelte` | Abschnitt 04 Kanäle |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Briefing-Zeitplan-Tab |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Inhalte des Briefing-Zeitplan-Tabs |
| `src/output/renderers/email/helpers.py:635-637` | sms_threshold → alle Kanäle |
| `src/output/tokens/builder.py` | Quick-Take-Chips (alert_threshold, nicht sms_threshold) |

## Abhängigkeiten
- Upstream: `display_config.channels` → gatest `report_config.send_*` (Channel-Gating)
- Downstream: Schwellwerte → `format_trend_tokens()` → E-Mail, Telegram, SMS

## Risiken & Überlegungen
- Kanal-Merge: Wenn 04-Kanäle in Briefing-Zeitplan wandert, muss das Gating-Verhalten erhalten bleiben
- SMS-Rename: rein kosmetisch, keine Backend-Änderung
- LoC-Budget: WeatherMetricsTab.svelte hat ~770 LoC — Umbauten erhöhen das
