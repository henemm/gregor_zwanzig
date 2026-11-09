# Context: fix-1767-nowcast-mehrort-kurzform

## Request Summary
Issue #1767: Ein Nowcast-/Radar-Onset-Alarm im Ortsvergleich mit mehreren auslösenden Orten baut N `OnsetEvent`s, die Kurzform-Kanäle (SMS, Premium-SMS, Telegram) werten aber nur `events[0]` aus. Mit Nachzug B2-51 (aus #1199).

## Ist-Stand (Code-Stand origin/main 2026-11-09, R = src/output/renderers/alert/render.py)

| Kanal | Stelle | Verhalten bei >1 Event |
|---|---|---|
| Betreff | R:602-607 `_render_subject_onset` | korrekt: Bündel-Betreff `alarm.regen.buendel` |
| E-Mail | R:954 → `_render_email_onset_multi` R:919-951 | korrekt: eine Zeile je Ort |
| Telegram (Langform) | R:981 `_render_telegram_onset` | **falsch**: Kopf `trip_short` = alle Ortsnamen, Wert/Zeit nur von Ort 1, dazu `km 0–0` (`_km_str_onset` R:441-447) |
| SMS | R:1801 `render_sms` → `_render_sms_body` R:1823 → `_render_sms_onset` R:1173/1191 | Kopf nur Name von Ort 1 (`e.location_label[:24]`, R:1244), übrige Orte verschwiegen; `location_positions` wird im Onset-Zweig ignoriert |
| Premium-SMS | kein eigener Renderer; `_dispatch_alert_message` rendert `sms_body` mit Limit 140 (src/services/notification_service.py:2053-2058) | wie SMS |
| Telegram Kurzstil | notification_service.py:2160-2176 sendet `sms_body` | wie SMS |

**Die Issue-Beschreibung ist für SMS überholt:** Seit #1948 S4 (Spec `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md`) lautet die Compare-Onset-SMS `Zermatt: R@H:MM`, ohne Ortsliste und ohne `km0-0`. Der im Issue zitierte Goldstring `Zermatt, Chamoni km0-0: R!8` steht nur noch in einer alten Spec. Die SMS ist also nicht mehr irreführend, sie verschweigt aber die übrigen Orte. **Telegram-Langform ist weiterhin irreführend** (alle Namen, Wert von Ort 1).

## Produkt-Zielkonflikt (vor der Spec mit dem PO klären)
- **PO-Entscheid 3b vom 2026-08-19** (#1948 S4, `docs/context/fix-1948-s4-nowcast-sms.md:146`, Spec :285-288): „kein `+N`-Zähler — die Nachricht wertet nur den führenden Ort aus; ein Zähler verspräche Vollständigkeit, die sie nicht einlöst. Verschweigen der übrigen Orte ist gewollt.“
- **Danach:** PO-Korrektur Empfangslage 2026-09-05, ADR-0095 (2026-10-21) „jeder Kanal beantwortet jede Frage mit demselben Inhalt“. Die E-Mail nennt alle Orte, die Kurzform nur einen; das widerspricht der Kanal-Parität.
- **Vorschlag aus dem Issue:** Muster des Änderungsalarms (`location_positions`, PO-Entscheid #1467 S2 AG3b): Ortsnummer vor jedem Token, kein Namenskopf, z. B. `1:R@14:05 2:R@14:40`. Das wäre echte Vollständigkeit und kein Zähler, ist mit dem Grund von 3b also vereinbar, kehrt aber das „gewollte Verschweigen“ um. Eine **Abweichung braucht den PO** (Entscheidungen nie still rückgängig machen).
- Telegram-Langform: entweder eine Sprechblase je Ort (wie Änderungsalarm, `telegram_groups`) oder eine Nachricht mit einer Zeile je Ort. Spec #1467 S2 (`docs/specs/modules/rework_1467_s2_aenderungsalarm.md:161/179/379-380`) hielt Radar-Onset „bewusst“ gebündelt.

## Related Files
| File | Relevance |
|---|---|
| src/output/renderers/alert/render.py | `_render_telegram_onset` R:981, `_render_sms_onset` R:1173, `_render_sms_body` R:1823, `_sms_token`/location_positions R:1699-1890, `_km_str_onset` R:441 |
| src/output/renderers/alert/project.py | `to_multi_location_onset_alert_message` :547 (OnsetEvent je Ort, `location_label` nur bei >1 Ort :648, `trip_short` = Join :685-688, `msg.location_label` nicht gesetzt) |
| src/services/compare_radar_alert.py:431 | einziger Versand-Aufrufer von `send_multi_location_radar_alert`; hat `preset`, berechnet aber keine Positionen |
| src/services/notification_service.py | `send_multi_location_radar_alert` :1262-1332 (ohne `telegram_groups`/`sms_location_positions`), `_dispatch_alert_message` :1997ff, Telegram-Auffächerung :2177-2238 (nutzt Abweichungs-Projektion, für Onset nicht direkt wiederverwendbar) |
| src/services/compare_alert.py:575-605 | `_location_positions(location_ids, all_locations)`, Vorbild für Positionen (1-basiert über `preset["location_ids"]`) |
| src/services/compare_alert_preview_service.py:162-187 | Vorschau `_onset`: `render_sms(msg, location_positions=None)`; Paritätstest Vorschau = Versand erzwingt gleichzeitige Änderung |

## Dependencies / Dependents
- Trip-Onset baut immer genau EIN OnsetEvent (notification_service.py:1922/1967, radar_alert_service.py:69/88, validator_render_service.py:129). Ein Zweig nur für `len(events) > 1` lässt den Trip-Fall unberührt.
- Tests, die bei Formatänderung brechen (bewusst nachzuziehen): `tests/tdd/test_alert_sms_location_positions.py:1028`, `tests/tdd/test_alert_sms_onset_zeitpunkt.py:253`, `tests/tdd/test_onset_menge_kanalparitaet.py:174`, `tests/tdd/test_compare_alert_telegram_per_location.py:584` (bei Telegram-Auffächerung), `tests/tdd/test_alert_preview_compare_paritaet.py:412`.
- Unberührt: `tests/tdd/test_multi_location_onset_alert.py:275` (Ein-Event), Golden `tests/golden/abweichungs_radar_alarm/regen_buendel.*` (nur E-Mail).

## Limits und Sprache
- Alarm-SMS 140 Zeichen (auch für Premium-SMS gerendert), Premium-SMS-Limit 153, absolut 160 (`docs/reference/sms_format.md:399/419`, `premium_sms_format.md:27/52`). Bei vielen Orten Budget-Regel nötig (wie Änderungsalarm).
- SMS-Tokens (R, TH, now, @) sind Protokoll, nie übersetzt; Telegram-/E-Mail-Texte über Katalog `src/i18n/messages/{de,en}/alarm.json`.

## B2-51 (Nachzug)
`render_email` R:1525 `_datablock_single(e, e.location_label or msg.location_label)`. Laut project.py:491-524 trägt bei mehreren Gruppen jedes AlertEvent seinen eigenen Ortsnamen; der Rückfall auf `msg.location_label` greift nur bei genau einer Gruppe (dann derselbe Ort) oder leerem Ortsnamen. Nach Code-Lage nicht erreichbar → in der Analyse per Test belegen und abhaken. Nebenbeobachtung: Sammelbezeichnung im Telegram-Kopf/Betreff, wenn der zweite Ort nur eine Beginn-Verschiebung beiträgt (R:1650-1652, R:1293); Überschneidung mit #2598.

## Analysis

### Type
Bug (nutzersichtbare Irreführung Telegram-Langform; Kanal-Paritätslücke SMS/Premium-SMS/Telegram-Kurzstil)

### Befunde (Plan-Agent, 2026-11-09)
- `_render_sms_body` (R:1823ff) hat eine Greedy-Budgetschleife (Tokens nach Severity, Rest als `+k`), nicht ausgelagert; Onset verlässt den Pfad vorher (`msg.source is not None → _render_sms_onset`, nur `events[0]`).
- Keine Obergrenze der Orte je Ortsvergleich (`location_ids` ungedeckelt, models.py:1327; weder Python- noch Go-Validierung) → Überlaufregel für 140 Zeichen nötig.
- `_location_positions` ist Methode von `compare_alert.py`-Klasse; Positionen über alle auflösbaren Preset-Orte, Schlüssel Ortsname (Kollision bei Namensdopplung, wie schon beim Änderungsalarm).
- Positionen müssen in `compare_radar_alert.py:431` (dort `preset`, `all_locations`) berechnet und als neuer optionaler Parameter durch `send_multi_location_radar_alert` (:1262) → `_dispatch_alert_message` gereicht werden.
- Vorschau `compare_alert_preview_service._onset` (:162-187) muss gleichzeitig mitziehen (Paritätstest `test_alert_preview_compare_paritaet.py:412`).
- Trip-Onset (immer 1 Event) bleibt unberührt, wenn der neue Zweig nur bei `len(events) > 1` greift.
- **B2-51 nicht erreichbar:** project.py:493-524 setzt bei mehreren Gruppen `location_label` je Event; Rückfall auf `msg.location_label` nur bei 1 Gruppe (derselbe Ort) oder leerem Namen (dann Sammel-Join, kein fremder Ort). → per Test belegen, abhaken, kein Codefix.

### Varianten
| | A (Blase je Ort) | A' (Zeile je Ort) | B (nur Telegram-Langform) |
|---|---|---|---|
| Irreführung Telegram behoben | ja | ja | ja |
| SMS/Premium-SMS nennt alle Orte | ja | ja | nein |
| Konflikt mit PO-Entscheid 3b | ja | ja | nein |
| Konflikt mit ADR-0095 (Kanal-Parität) | nein | nein | ja |
| Telegram-Nachrichten | N | 1 | 1 |
| Aufwand (LoC Code) | ~150 | ~100 | ~40 |
| Risiko | hoch (Fan-out, Überlappung #2598) | mittel | niedrig |

### Technical Approach (Empfehlung Tech Lead)
**A'**, in einem Durchgang (Epics nicht abspalten): SMS/Premium-SMS/Telegram-Kurzstil bei >1 Ort `pos:token` je Ort ohne Namenskopf (Muster Änderungsalarm), Greedy-Budget aus `_render_sms_body` in Helfer auslagern und wiederverwenden; Telegram-Langform eine Nachricht mit einer Zeile je Ort (analog `_render_email_onset_multi`), ohne Namens-Join-Kopf und ohne `km 0–0`. Vorschau gleichzeitig. Begründung: ADR-0095 (später als 3b) verlangt gleichen Inhalt auf jedem Kanal; Premium-SMS ist ggf. einziger Kanal.

### Affected Files
| File | Change | Description |
|---|---|---|
| src/output/renderers/alert/render.py | MODIFY | Mehrort-Zweig `_render_sms_onset`, `_render_telegram_onset`; Budget-Helfer |
| src/services/compare_radar_alert.py | MODIFY | Positionen berechnen, durchreichen |
| src/services/notification_service.py | MODIFY | `send_multi_location_radar_alert` Parameter Positionen |
| src/services/compare_alert.py | MODIFY | `_location_positions` als freie Funktion teilbar |
| src/services/compare_alert_preview_service.py | MODIFY | Vorschau mit Positionen |
| tests/tdd/ (5 bestehende + neue) | MODIFY/CREATE | Formatänderung, Mehrort-Kurzform, B2-51-Beleg |

### Scope Assessment
- Dateien: ~5 Code + ~6 Tests; LoC ca. +100/-20 Code, +200 Tests; Risiko MITTEL

### Open Questions
- [x] PO-Entscheid 2026-11-09 (AskUserQuestion): **„Alle Orte überall" = Variante A'**. Hebt Entscheid 3b (#1948 S4) auf; Kurzform `pos:token` je Ort, Telegram eine Nachricht mit Zeile je Ort, bei Überlauf `+k` am Ende (PO hat die Option mit `+2`-Beispiel gewählt). Spec muss die Ablösung von 3b ausdrücklich vermerken (ggf. ADR-Nachtrag).
- [ ] Spec: Überlaufverhalten >140 Zeichen (`+k`), Sortierung (Position vs. Beginnzeit), Abgleich #2598

## Risks & Considerations
- Überschneidung mit #2598 (Compare-Änderungsalarm-Telegram-Kopf, gleiche Dateien): nicht doppeln.
- Paritätstest Vorschau/Versand: beide Pfade gemeinsam ändern.
- Zeichenbudget bei 3+ Orten mit Zeitangaben.
