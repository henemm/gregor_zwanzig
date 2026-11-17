# Context: 2986-alarmvorschau-versandprojektion

## Request Summary
Issue #2986 (Paar P05 aus der Paritäts-Bestandsaufnahme #1986): Die Alarm-Vorschau des
Ortsvergleichs baut Nachricht und Kanaltexte selbst nach, statt dieselbe Projektion/
Kanal-Aufbereitung wie der Versand zu nutzen. Doppelung zu EINEM Baustein zusammenführen;
der Paritätstest bleibt danach als Regressionswächter (oder wird überflüssig).
Reines Refactoring: Nutzer-sichtbares Verhalten (Vorschau UND Versand) bleibt byte-gleich.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/compare_alert_preview_service.py` (259 Z.) | Seite A: `render_compare_alert_preview` → `_deviation`, `_onset`, `_official`, `_channels`. Baut AlertMessage, SMS (Limit 140 + Ortsnummern), Telegram-Blasen (Kurzform = SMS, sonst je Ort / eine), amtliche Texte selbst nach. |
| `src/services/notification_service.py` | Seite B: `send_multi_location_deviation_alert` (~1200, Projektion `to_multi_point_alert_message`), `send_multi_location_radar_alert` (~1271, `to_multi_location_onset_alert_message`), `send_multi_location_official_alert` (1687, amtliche Komposition), `_dispatch_alert_message` (1973: Betreff/Mail/SMS/Telegram-Rendern + Kurzform-Zweig + `telegram_groups`-Auffächerung ~2193 mit Fehlerhärtung je Ort). Helfer `_official_subject/_official_mail_bodies/_official_telegram_rich/_official_allclear_source_label/_official_source_url_for` (513–596) sind schon geteilt. |
| `src/services/compare_alert.py:477`, `compare_radar_alert.py:432`, `compare_official_alert.py:367` | Aufrufer der drei Versand-Methoden (Parameter: Positionen via `CompareAlertService._location_positions`, Stil via `effective_compare_telegram_style`, Cooldown via `_format_cooldown_display`). |
| `api/routers/validator.py:410` | Einziger Produktiv-Aufrufer der Vorschau (Route Alarm-Vorschau Ortsvergleich). |
| `src/services/validator_render_service.py:162` | Trip-Pendant `render_alert_preview` (nicht Gegenstand; P02/#2983 behandelt Trip-Bericht). |
| `tests/tdd/test_alert_preview_compare_paritaet.py` (:338/:420/:512) | Bewachender Paritätstest: echter Versand am Draht (lokale Telegram-/seven.io-Stubs, mail_sink) vs. Vorschau. |
| `tests/tdd/test_profil_ampel_kette.py:891` (`DIENST_EINSTIEGE`) | Ratsche: zählt `resolve_ampel`-Einstiege je (Datei, Funktion), „darf nur schrumpfen“ — wandert die Projektion, muss die Liste angepasst werden (schrumpfen ist erlaubt). |
| `tests/tdd/test_s1c4b_einstiege_loesen_das_abo_auf.py:516` | Ruft `cap._onset`/`cap._deviation` direkt auf — interne Signaturen sind von Tests abhängig. |
| weitere Vorschau-Tests | `test_fix_1767_nowcast_mehrort_kurzform.py`, `test_alert_hour_rows.py:1329`, `test_fix_2598_ortsvergleich_alarm_kopfzeile.py:557`, `tests/integration/test_alert_preview_kind_isolation.py`. |

## Existing Patterns
- ADR-0011 (ein Alarm-Renderer) / ADR-0021 (Rendering/Versand geteilt): `_dispatch_alert_message` ist der gemeinsame Kanal-Dispatcher für Trip-Δ, Trip-Radar, Compare-Δ, Compare-Radar.
- Amtlich: Bausteine schon als Modul-Funktionen geteilt; nur die Komposition (Reihenfolge Quelle→Betreff→Bodies→SMS→Telegram) ist doppelt.
- Vorschau darf NICHT über `send_*` mit Senken laufen: SMS-Zweig reserviert vorher das SMS-Tageskontingent (Docstring Vorschau-Modul). Daher: reine Render-Funktionen herauslösen, die Versand UND Vorschau aufrufen.
- Zuletzt gleiches Muster: #2982 (ein Baustein `onset_event_from_fields` statt Bau an vier Stellen).

## Dependencies
- Upstream: `output.renderers.alert.project` (`to_multi_point_alert_message`, `to_multi_location_onset_alert_message`), `output.renderers.alert.render` (`render_subject/email/sms/telegram`), `official_alerts` (`build_compare_official_alert_notices`, `render_official_alert_sms_with_allclears`), `app.ampel.resolve_ampel`, `utils.timezone`.
- Downstream: Validator-Route (Vorschau), drei Compare-Alarm-Services (Versand), Trip-Alarmwege über `_dispatch_alert_message`.

## Existing Specs
- `docs/specs/modules/shared_preview_tab.md` (#2283 S4, AC-17..19 Alarm-Vorschau = Versand)
- `docs/specs/modules/compare_channel_preview_dispatch.md` (#1270)

## Risks & Considerations
- `_dispatch_alert_message` bedient auch Trip-Alarme → Herauslösen der Kanal-Aufbereitung berührt kritischen Versandpfad; Byte-Gleichheit für alle vier Aufrufer nötig.
- Telegram-Auffächerung je Ort hat Fehlerhärtung (ein Render-Fehler bei einem Ort darf die anderen nicht abbrechen, `telegram_fully_sent`, Teilzustellungs-Hinweis). Ein gemeinsamer Baustein muss diese Semantik erhalten (Rendern je Ort einzeln fehlertolerant).
- Kurzform-Zweig steht im Versand VOR der Auffächerung (#1467 K-6) — Reihenfolge erhalten.
- Unterschiede heute: Vorschau berechnet `stand_at` selbst, Versand ebenfalls; tz-Herleitung Δ: Vorschau aus Ort (`tz_for_coords(first.lat, first.lon)`), Versand aus `points[0]` — ggf. leicht verschieden (Frisch-Punkt vs. Ort) → bei Zusammenführung bewusst entscheiden.
- `reference_at` / `official_notices`-Zweig nur im Versand relevant; Vorschau setzt sie nicht.
- Ratschen-Liste `DIENST_EINSTIEGE` und direkte `_onset/_deviation`-Aufrufe in Tests anpassen.
- Kein Nutzer-sichtbarer Unterschied gewollt → Nachweis über bestehenden Paritätstest + neue Tests, dass die Vorschau den geteilten Baustein aufruft (wirkort-geprüft).

## Analysis

### Type
Feature (reines Refactoring, Nutzer-Verhalten von Vorschau UND Versand byte-gleich)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_channel_texts.py` | CREATE | Reine Bausteine ohne I/O (lazy Import von notification_service-Helfern): `build_deviation_message`, `build_onset_message`, `render_channel_texts` → `AlertChannelTexts(subject, html, plain, telegram_body, sms_body)`, `plan_telegram` → `TelegramPlan(fan_out, bubbles[label, parse_mode, render()])`, `official_header_texts`, `official_telegram_text`. SMS-Limit 140 lebt nur noch hier. |
| `src/services/notification_service.py` | MODIFY | `send_multi_location_deviation_alert`/`_radar_alert` nutzen `build_*_message`; `_dispatch_alert_message` nutzt `render_channel_texts` (Z. ~2011–2072) + `plan_telegram`, Versandschleife (~2193–2250) mit try/except je Blase, `failed_count`, `telegram_fully_sent`, Teilzustellungs-Hinweis und RuntimeError „alle gescheitert" bleiben im Dispatcher. Amtlich: Komposition 1735–1750 und Telegram-Entscheidung 1819–1858 über `official_*`. Netto ca. −60. |
| `src/services/compare_alert_preview_service.py` | MODIFY | `_deviation/_onset/_official/_channels` werden dünne Wrapper (Namen/Signaturen bleiben, Tests rufen sie direkt) über die geteilten Bausteine; `_SMS_LIMIT` und Eigenbauten entfallen. Netto ca. −80. |
| `tests/tdd/test_profil_ampel_kette.py` | MODIFY | `DIENST_EINSTIEGE` (exakte Gleichheit je Funktion, :957): Einträge `_deviation`, `_onset`, `send_multi_location_*` fallen weg, `build_deviation_message`/`build_onset_message` kommen hinzu (schrumpft). |
| `tests/tdd/test_alarmvorschau_versandbaustein.py` (Name in Spec) | CREATE | Struktur-/Wirkort-Tests (siehe unten). |
| `tests/tdd/test_alert_preview_compare_paritaet.py` | KEEP | Bleibt als Regressionswächter am Draht. |

### Scope Assessment
- Files: 5 (1 neu Produktiv, 2 Produktiv geändert, 2 Tests)
- Estimated LoC: Diff ca. +300/−300, überwiegend verschobener Code; neuer Produktivcode netto < 100
- Risk Level: MEDIUM — `_dispatch_alert_message` bedient auch Trip-Δ/Trip-Radar (kritischer Versandpfad), aber reine Verschiebung mit vorhandenen Drahttests

### Technical Approach
Tech-Lead-Entscheidung: EIN Workflow für alle drei Alarmarten (Δ, Radar, amtlich). Plan-Agent schlug Schnitt A (Δ+Radar) / B (amtlich, ~40 LoC) vor; verworfen, weil das Issue genau EINEN Baustein fordert, B klein ist und kleine verwandte Teile als Paket in einem Durchlauf geliefert werden (PO-Vorgabe 15.11.). Fällt das LoC-Gate, wird B als Kind-Issue abgespalten.

Reihenfolge: (1) Schutznetz grün (Paritätstest :338/:420/:512, Trip-Alarm-Tests, Teilzustellung #1467); (2) `render_channel_texts` aus Dispatcher ziehen, nur Versand umstellen; (3) `build_*_message`, Versand + Vorschau umstellen; (4) `plan_telegram` (Kurzform VOR Fan-out, K-6), Dispatcher-Schleife, dann Vorschau; (5) amtliche Bausteine (Telegram-Text pro Kanal lazy, kein eager compose); (6) Vorschau-Eigenbauten + `_SMS_LIMIT` raus, Ratsche anpassen.

Festgelegte Detailentscheidungen:
- tz Δ: Versandvariante (`tz_for_coords` von `groups[0]`-Punkt). Vorschau liefert praktisch dieselben Koordinaten (frischer Punkt aus `loc.lat/lon`) → kein sichtbarer Unterschied.
- Radar/amtlich: `resolve_location_tz(first) or UTC` auf beiden Seiten, unverändert; `tz`-Override bleibt nur Versand-Parameter.
- `stand_at` einmal in `build_*_message` (`local_fmt(now_utc, tz)`).
- `reference_at`: bleibt nur im Versand (Vorschau setzt es heute nicht) — bewusst unverändert, in Spec nennen.
- Fehlerverhalten Vorschau: `render()` ohne try (heutiges Verhalten); `vergleich_keine_warnung` vs. `sent=False` bleibt in den Wrappern.

Tests (keine Mocks): Mutation im geteilten Baustein (SMS-Limit 140→139, Kurzform/Fan-out-Reihenfolge, Ortsnummern, Betreff) muss Vorschau- UND Versand-Test rot machen; AST-Strukturtest: Vorschau-Modul ruft keine `render_sms/render_telegram/render_email/render_subject/to_multi_*_alert_message` direkt, Versand ruft die geteilten Funktionen; Fehlerhärtung je Ort (kaputte echte Eingabe wie #1467) liefert weiter übrige Blasen + `telegram_fully_sent=False`; Byte-Vergleich Trip-Δ, Trip-Radar, Compare-Δ, Compare-Radar über bestehende Tests.

### Dependencies
Upstream: `output.renderers.alert.project` / `.render`, `official_alerts`, `app.ampel.resolve_ampel`, `utils.timezone`. Downstream: Validator-Route Alarm-Vorschau (`api/routers/validator.py:410`), `compare_alert.py:477`, `compare_radar_alert.py:432`, `compare_official_alert.py:367`, Trip-Alarmwege über `_dispatch_alert_message`.

### Nebenbefund (Folge-Issue)
Δ-Alarm (Vorschau und Versand) nutzt `tz_for_coords` und ignoriert `SavedLocation.timezone`, Radar/amtlich nutzen `resolve_location_tz`. Inkonsistenz, Fix wäre Verhaltensänderung → eigenes Issue.

### Open Questions
- keine (reines Refactoring, keine Produktentscheidung offen)
