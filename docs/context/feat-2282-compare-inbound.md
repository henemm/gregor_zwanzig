# Context: feat-2282-compare-inbound

## Request Summary
Issue #2282: Der Ortsvergleich soll wie der Trip über die Eingangskanäle (Telegram, E-Mail, Premium-SMS) per Befehl ansprechbar sein — `report`, `pause`/Fortsetzen, `heute`/`morgen` — adressiert über einen Shortcode, der für beide `kind`s gilt. Heute ist die gesamte Eingangskette trip-gebunden. Vorbedingung #2133 S1–S3 ist erfüllt (Epic geschlossen 15.09.).

## Kernbefunde (verändern den AC-Entwurf aus dem Ticket)
- **A. Shortcodes werden produktiv nie vergeben.** `generate_shortcode` (`src/app/shortcode.py:9`) hat nur Test-Aufrufer; das in `docs/specs/modules/trip_shortcode_routing.md:75-78` vorgesehene Nachtragen beim Versand wurde nie gebaut, das Wizard-Feld entfiel (d7703708). Neue Trips haben `shortcode=""`. „GZ#XXXX" ist heute also auch beim Trip faktisch tot.
- **B. `report` ist bewusst mehrkanalig** (`send_test_report`, Test `tests/tdd/test_kanaltreue_adhoc_antwort.py:434`) — AC-1 („auf demselben Kanal") widerspricht dem Trip-Verhalten.
- **C. Trip-`pause` setzt `report_config.paused_until` (Dauer), nicht `paused_at`.** Es gibt kein `resume`, nur `weiter` (`enabled=True`, löscht `paused_until` nicht). Pause-Text empfiehlt „Zum Fortsetzen: STOP" (`trip_command_processor.py:2047-2052`). Vergleich pausiert dagegen über `schedule="manual"` + `previous_schedule` + `paused_at`; Go löscht `paused_at`, wenn `schedule!="manual"` (`internal/store/compare_preset.go:39-41`).
- **D. Telegram und Premium-SMS werten `GZ#` gar nicht aus** — beide nehmen `pick_active_trip`, ohne aktiven Trip Abbruch vor dem Parsen (`inbound_telegram_reader.py:211-227`, `inbound_sms_reader.py:322`).
- **E. `send_compare_report` hat keinen `premium_sms`-Zweig** und kein `restrict_to_channel` (`notification_service.py:1154-1242`), obwohl `effective_compare_briefing_channels` ihn liefert (`compare_alert_channels.py:32-53`) → Nebenbefund: Premium-SMS-Vergleichsbriefings gehen heute still verloren.
- **F. Go `ComparePreset` hat kein `Shortcode`-Feld und keine Unknown-Fields-Erhaltung** → ein von Python geschriebener Shortcode ginge beim nächsten Web-Speichern verloren (Datenverlust-Regel!).
- **G. Shortcode-Eindeutigkeit prüft nur Trips** (`shortcode.py:16`, `load_all_trips` überspringt `vergleich`).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | `InboundMessage` :59, `CommandResult` :78, Befehlstabellen :98-154, `process()` :677-833, `_find_trip` :852 (GZ#/Name, nur Trips), `_trigger_on_demand` :977, `_trigger_report` :1830, `_apply_pause` :1993, `_cancel_trip` :2334, `_resume_trip` :2348, Kurzform-Kanäle :488 |
| `src/app/shortcode.py` | Generator + Kollisionsprüfung (nur Trips) |
| `src/services/inbound_email_reader.py` | Trip nur aus `[Name]` im Betreff :66/:141-145/:200; `_find_trip_id` :304 (Duplikat zu `_find_trip`) |
| `src/services/inbound_telegram_reader.py` | `_find_active_trip` :378 → `pick_active_trip`; Parser :463-539 kennt `GZ#` nicht; Buttons :302-368 |
| `src/services/inbound_sms_reader.py` | `_verarbeite_befehl` :294-338, `pick_active_trip` :322, Link-Code :74-105 |
| `src/services/trip_selection.py` | `pick_active_trip` :27-62 (nur Etappen-Zeitraum, ignoriert Pause) |
| `src/output/channels/telegram.py` / `api/main.py:72` | `BOT_COMMANDS` :111-120 |
| `src/services/scheduler_dispatch_service.py` | `send_one_compare_preset` :367 (`on_demand` :378), `send_compare_preset` :619, `save_compare_preset_pause` :279, Vergleichs-Betreff :339 |
| `src/output/renderers/comparison.py` | `render_compare_email` :420, `_telegram` :692, `_sms` :967 |
| `src/services/notification_service.py` | `send_compare_report` :1154; Befehlsantworten :1795/:1809/:1822 |
| `src/services/compare_alert_guard.py` / `compare_slot_scheduler.py` | „aktiv" beim Vergleich: `is_silenced` :39, `presets_due_for_hour` :103 |
| `src/app/models.py` / `src/app/loader.py` | `ComparePreset` :1278 (`paused_at`, `kind`, `raw`); Trip-`shortcode` loader :642/:679/:1587; `load_all_trips` :1482, `load_compare_presets` :294 |
| `internal/model/compare_preset.go`, `internal/store/compare_preset.go` | Go-Modell ohne Shortcode; Normalize/Materialize PausedAt |
| `internal/model/briefing_subscription.go` | Gerüst gemeinsames Modell, „NOT wired" (ADR-0023) |
| `internal/model/trip.go:127` | Trip-Shortcode |

## Existing Patterns
- Prozessor sendet nie selbst: `CommandResult` → Leser antwortet über `NotificationService.send_command_reply_*` (Kanaltreue #2126, Antwort an Fragenden #2168).
- Ad-hoc `heute`/`morgen` beim Trip: `send_on_demand_report(..., restrict_to_channel=channel)`.
- Vergleich-Handversand mit `on_demand=True` lässt den Δ-Anker unberührt; `morgen` braucht `target_date` + `tage_ab_ortstag=1`.
- Befehls-/Hilfetexte aus einer Quelle `_COMMAND_SPECS` (#2134).
- Mandantentrennung: Nutzer wird im Leser aus Absender aufgelöst, nie `default` (#2147, #2173).
- Persistenz Trip+Vergleich gemeinsam unter `data/users/<id>/briefings/<id>.json`; Python-Pause mit kind-Schutz.

## Dependencies
- Upstream: Loader/Store (Trip + ComparePreset), Compare-Dispatch/Renderer, NotificationService, Kanal-Resolver, Nutzer-Lookup per Absender.
- Downstream: Go-Scheduler `inboundCommands` (scheduler.go:527) → `/inbound-commands`, `/inbound-sms`, `/inbound-telegram` (api/routers/scheduler.py), Telegram-Webhook (api/routers/webhook.py:52); Web-Editor (Go-Speichern darf Shortcode nicht verlieren).

## Existing Specs
- `docs/specs/modules/trip_command_processor.md`, `inbound_command_channels.md`, `trip_shortcode_routing.md` (draft), `command_set_merge.md`, `telegram_webhook_inbound.md`
- `feat_2126_kanaltreue_adhoc_antwort.md`, `fix_2168_antwort_an_den_fragenden.md`, `feat_2184_s4_premium_sms_kommandoverarbeiter.md`, `feat_2134_adhoc_abruf_metrik_katalog.md`, `feat_2207_kurzform_verlauf.md`, `compare_preset_zeitplan.md`
- ADRs: 0023 (gemeinsames Modell/kind), 0049 (Premium-SMS), 0035 (Tagesfenster Trip = Vergleich), 0044/0051 (Ortstag), 0053/0059 (Kanal-Metriken Vergleich)

## Existing Tests
- Prozessor: `test_trip_command_processor.py`, `test_issue_731_unified_commands.py`, `test_issue_882_pause_skip.py`, `test_issue_612_report_on_demand.py`, `test_kommandoliste_einzelquelle.py`, `test_bug_775_email_trip_lookup.py`
- Leser: `test_inbound_telegram_reader.py`, `test_premium_sms_kommandopfad.py` (:803 Zwei-Nutzer), `test_inbound_unresolved_sender_no_default.py` (`two_accounts`), `test_telegram_chat_id_ownership.py`, `test_issue_663_command_user_isolation.py`
- Kanaltreue: `test_kanaltreue_adhoc_antwort.py`, `test_antwort_an_den_fragenden.py`

## Risks & Considerations
- **Produktfragen für die Analyse/Spec (nicht technisch zu raten):** Wie adressiert der Nutzer praktisch, wenn Shortcodes nie vergeben/angezeigt werden? `report` kanaltreu oder mehrkanalig? Pause-Semantik Vergleich (unbefristet `manual`) vs. Trip (Dauer) und „identischer Wortlaut".
- **Datenverlust:** Shortcode am Vergleich braucht Go-Feld + Roundtrip-Test (Schema-Regel, Backup-Hook).
- **Shortcode-Kollision** Trip↔Vergleich: Generator muss beide kinds prüfen.
- **AC-3 Rückfrage:** braucht gemeinsame Auswahl über beide kinds mit unterschiedlicher „aktiv"-Definition (Etappen-Zeitraum vs. `is_silenced`/`end_date`).
- **Kanaltreue:** `send_compare_report` ohne Kanaleinschränkung würde Telegram-Anfrage auch per Mail/SMS beantworten; `send_one_compare_preset` scheitert ohne `mail_to`.
- **E-Mail:** Vergleichs-Betreff hat keine `[Name]`-Klammern → Antworten auf Vergleichs-Mails werden still verworfen.
- **Trip-Regression:** alle Antworttexte/Handler setzen `trip.stages`/`report_config` voraus.
- **LoC:** klar > 250 → Scheiben-Schnitt in der Analyse.
- **Nebenbefund E** (Premium-SMS-Vergleichsbriefing fehlt) ist nutzersichtbar → ggf. eigenes Issue.

## Analysis

### Type
Feature (Parität Ortsvergleich ↔ Trip, Dach-Epic #1374 / #2345)

### Korrekturen am Kontext
- Explore-Befund „Go erhält unbekannte Felder" ist falsch: `ComparePreset` hat kein Raw/Unknown-Feld, ein Top-Level-`shortcode` ginge beim Web-Speichern verloren. Relevant erst für die Shortcode-Scheibe.
- Trip-Shortcode wird im Frontend angezeigt (`TripHeader.svelte:22`, `EmailPreviewHeader.svelte:20`, Betreff `subject.py:106`), aber nur wenn gesetzt — Vergabe existiert produktiv nicht.
- Premium-SMS-Lücke im Vergleichs-Versand ist bereits **#2275** (offen, „nach #2279") → kein neues Issue.
- `mail_to`-ValueError in `send_one_compare_preset` (`scheduler_dispatch_service.py:428-432`) ist bewusst laut (KL-3); relevant erst für `report`/`heute` am Vergleich.

### Spec-Konflikt AC-1 (Ticket-Entwurf)
`feat_2126_kanaltreue_adhoc_antwort.md:156-157` + `test_kanaltreue_adhoc_antwort.py:434`: `report` bleibt **mehrkanalig**. Ticket-AC-1 („auf demselben Kanal") widerspricht. Entscheidung: Vergleich folgt dem Trip (mehrkanalig) — keine ADR-Abweichung; AC-1 wird in der Spec sichtbar umformuliert. `heute`/`morgen` bleiben kanaltreu wie beim Trip.

### Zwei „aktiv"-Prädikate (für AC-3 festzuschreiben)
- Trip: `pick_active_trip` (`trip_selection.py:27-62`) — Etappen-Zeitraum enthält Ortstag, sonst frühester zukünftiger; Pause egal.
- Vergleich (Vorschlag, symmetrisch zum Trip = Pause egal, sonst wäre `weiter` unerreichbar): nicht archiviert UND (`end_date` leer ODER ≥ Ortstag heute). `is_silenced` (pausiert) zählt NICHT als inaktiv.

### Scheiben-Schnitt
| # | Inhalt | Vorbedingung |
|---|---|---|
| **S1 (dieser Workflow)** | Kind-neutrale Auswahl in `trip_selection.py` (nimmt `trips`/`presets` als Parameter, lädt nicht selbst — 4 Testdateien patchen `inbound_telegram_reader.load_all_trips`); Rückfrage bei Mehrdeutigkeit; Telegram/Premium-SMS/E-Mail-Leser nutzen sie; `_find_trip` sucht beide kinds per Name; `_COMMAND_SPECS` bekommt kind-Menge; `pause`/`weiter` für Vergleich (Python-Resume als RMW-Gegenstück zu `save_compare_preset_pause`, kind-Guard); nicht unterstützte Befehle am Vergleich → klare Antwort aus `_COMMAND_SPECS`; Zwei-Nutzer-Test | — |
| S2 | `report` + `heute`/`morgen` am Vergleich (mehrkanalig bzw. kanaltreu, `restrict_to_channel` in `send_compare_report`) | #2275 |
| S3 | E-Mail-Antwort auf Vergleichs-Mail erkennen (Betreff `Wetter-Vergleich: {name}`) | S1 |
| S4 (optional) | Shortcode-Vergabe beide kinds + Go-Feld + Kollision + Anzeige + Backfill/Roundtrip | PO-Wunsch |

S1 berührt keine schema-relevante Datei (`models.py`, `trip.py`, `loader.py`, `internal/model/*.go`, `store.go`) → keine Migration.

### Affected Files (S1)
| File | Change | Description |
|------|--------|-------------|
| `src/services/trip_selection.py` | MODIFY | kind-neutrale Auswahl + Mehrdeutigkeits-Ergebnis |
| `src/services/trip_command_processor.py` | MODIFY | Auflösung beide kinds, Dispatch-Weiche, `_COMMAND_SPECS` kind-Menge, Vergleich-pause/weiter, Rückfrage-/Ablehnungstexte |
| `src/services/inbound_telegram_reader.py` | MODIFY | :211-227 / :340 Auswahl statt `pick_active_trip`, Abbruch vor Parsen entschärfen |
| `src/services/inbound_sms_reader.py` | MODIFY | :322 dito |
| `src/services/inbound_email_reader.py` | MODIFY | `_find_trip_id` :304 beide kinds (Duplikat zu `_find_trip` abbauen) |
| `src/services/scheduler_dispatch_service.py` | MODIFY | Python-Resume für Vergleich (RMW, kind-Guard) |
| `tests/tdd/test_*` (verhaltensbenannt) | CREATE | Auswahl/Rückfrage, pause/weiter Vergleich, Zwei-Nutzer, Trip-Regression |

### Scope Assessment
- Files: ~6 Source + 2-3 Tests
- Estimated LoC: +350/-60 → `loc_limit_override 500` nötig
- Risk Level: HIGH (gesamte Eingangskette, Trip-Regression, Mandanten)

### Technical Approach
EIN Prozessor, keine Compare-Kopie (Teilungs-Pflicht). Auflösung liefert `(kind, obj)` bzw. „mehrdeutig"; direkt danach Weiche. Trip-Pfad bleibt byte-gleich. Vergleich-Pause unbefristet über `schedule="manual"` (bestehende Mechanik), Fortsetzen stellt `previous_schedule` her und löscht `paused_at` im selben Write. Antworttexte kind-passend (Trip-Text „Zum Fortsetzen: STOP" + Dauer ist für den Vergleich sachlich falsch).

### Dependencies
Leser → `trip_selection` → Prozessor → Loader (`load_all_trips`, `load_compare_presets`) / `save_compare_preset_pause`; Antwort über `NotificationService.send_command_reply_*` unverändert.

### Open Questions (Produkt, in Spec als ACs zur Freigabe)
- [ ] Vergleich-`report` mehrkanalig wie Trip (Empfehlung) — AC-1 umformuliert
- [ ] Vergleich-Pause unbefristet bis `weiter` (Empfehlung), Dauerangabe wird ignoriert/abgelehnt
- [ ] Shortcode zurückgestellt; Adressierung über aktive Auswahl + Name bei Rückfrage
