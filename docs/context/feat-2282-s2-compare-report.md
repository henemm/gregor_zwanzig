# Context: feat-2282-s2-compare-report

## Request Summary
#2282 Scheibe S2 (Epic #2345, Etappe P5): Die Befehle `report` (mehrkanalig wie beim Trip) und `heute`/`morgen` (kanaltreu, Antwort auf dem Anfragekanal) sollen am Ortsvergleich tatsächlich ein Vergleichs-Briefing ausliefern statt der Übergangsantwort aus S1. Zusatzauftrag: prüfen, ob der fehlende Vorhersage-Cache im Vergleichspfad (#2234) die Antwortzeit-Ziele aus #2439 reißt.

## Related Files
| File | Relevance |
|------|-----------|
| src/services/trip_command_processor.py:1125-1127 | `_process()` ruft `_resolve_vergleich` vor jedem Trip-Zweig |
| src/services/trip_command_processor.py:1328-1356 | `_resolve_vergleich` (resolved_kind/preset_id vom Reader, Fallback Namenssuche `_find_compare_preset` :1311) |
| src/services/trip_command_processor.py:1358-1385 | `_dispatch_compare`; :1378f `report/heute/morgen` → `_compare_transitional` |
| src/services/trip_command_processor.py:1416-1430 | `_compare_transitional` — die zu ersetzende Übergangsantwort (Docstring nennt S2: `restrict_to_channel` in `send_compare_report`) |
| src/services/trip_command_processor.py:257-291 | `_COMMAND_SPECS`: heute/morgen/report sind `_ROUTE_ONLY` |
| src/services/trip_selection.py:71, 239-300 | `_BEIDE_KINDS_ONLY_SCHLUESSEL={"pause","weiter"}`; `resolve_trip_only_target` ignoriert Vergleiche ohne Namenspräfix |
| src/services/trip_command_processor.py:2616, 2649 | Trip-`report`: `_trigger_report` → `send_test_report_outcome`; `_report_reply_body` |
| src/services/trip_command_processor.py:1544-1583, 1671 | Trip-`heute`/`morgen`: `_handle_query` → `_trigger_on_demand(..., channel=msg.channel)` |
| src/services/trip_report_scheduler.py:1381-1470, 1499, 2122-2179 | `send_test_report_outcome`, `send_on_demand_report(restrict_to_channel)`, `_resolve_channel_flags` (nur Anfragekanal, Tarif-Gates aktiv) |
| src/services/scheduler_dispatch_service.py:455-794 | `send_one_compare_preset` (Kanäle → Rechnung → Render → Versand → briefing_log/Anker/Status); `target_date` + `tage_ab_ortstag` nur gemeinsam (:500-511) |
| src/services/scheduler_dispatch_service.py:797ff | `send_compare_preset` Handversand (`on_demand=True`, `weather_failure_as_outcome`, Send-Lock `"compare"`, `SendOutcomeError.code`) — Vorbild für `report` |
| src/services/notification_service.py:1429-1543 | `send_compare_report(effective_channels=…)` — kein `restrict_to_channel`; Premium-SMS-Zweig seit #2275 |
| src/services/compare_alert_channels.py:32-62 | `effective_compare_briefing_channels` (E-Mail immer, Telegram/SMS Opt-in, Premium-SMS mit Tarif-Gate) |
| src/services/compare_slot_scheduler.py:39-40, 199-202 | `MORGEN_SLOT_VERSATZ=0`, `ABEND_SLOT_VERSATZ=1` — Zieltag-Semantik heute/morgen |
| src/services/report_config_resolver.py:220 | `resolve_compare_time_window` (Tagesfenster) |
| src/services/compare_preview_service.py:82-129 | Einzelkanal-Rendern ohne Versand |
| src/services/comparison_engine.py:40, 412 | `fetch_forecast_for_location` ohne Cache, 96 h |
| src/services/comparison_parallel.py:42 | `MAX_PARALLEL_LOCATIONS=4` |
| src/services/weather_cache.py:66 | `WeatherCacheService` (600 s TTL) — nur Trip-`segment_weather` nutzt ihn |
| src/services/inbound_telegram_reader.py:335-400 | Ladehinweis „⏳ Wetter wird geladen…" — am Vergleich unterdrückt (F001) |
| internal/handler/telegram_webhook.go:40/61, api/routers/webhook.py:53-109 | Telegram-Eingang synchron (Go 5 s Timeout, immer 200) |

## Existing Patterns
- Kanaltreue Ad-hoc-Antwort (`feat_2126_kanaltreue_adhoc_antwort.md:156-157`): `heute`/`morgen` nur Anfragekanal, `report` bleibt mehrkanalig.
- Trip-Ergebnis-Codes für `report`: sent / no_stage / no_weather / no_channels / channels_unreachable / already_in_progress → Antworttext; heute/morgen: `OnDemandErgebnis(outcome, zieltag)`, bei „sent" `suppress_email_reply=True`.
- Compare-Handversand mit Send-Lock und Fehlercodes existiert (#2280) — wiederverwenden statt neu bauen (ADR-0097).
- S1-Muster: Weiche `_dispatch_compare`, gleicher Wortlaut wie Trip wo sinnvoll, Zwei-Nutzer-Test.

## Dependencies
- Upstream: drei Inbound-Reader (setzen `resolved_kind`/`resolved_preset_id`), `_COMMAND_SPECS`, `trip_selection`, Hilfe-Text.
- Downstream: `briefing_log` (kind-neutral seit #2281; `tage_ab_ortstag≠0` → Slot „evening"), `save_compare_preset_status`, Δ-Anker (bei `on_demand=True` unberührt), SMS-Tageslimit, Premium-SMS-Tarif-Gate, Compare-Mail (`mail_type="compare"`, Renderer unverändert).

## Existing Specs
- `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md` — S1-Spec, S2 skizziert (Zeilenangabe 1154-1242 dort veraltet)
- `docs/specs/modules/feat_2126_kanaltreue_adhoc_antwort.md` — Kanaltreue-Regeln
- `docs/specs/modules/feat_2439_befehle_antwortzeit.md:36` — Budget: HEUTE/MORGEN kalt < 60 s je Lauf, Median < 45 s; Befehle ohne Wetterabruf < 30 s
- ADRs: 0095 (Kanal-Parität), 0097 (Code-Teilung Trip/Vergleich), 0049 (Premium-SMS), 0044/0051 (Ortstag), 0035 (Tagesfenster), 0086 (Erfolg = Zustellung), 0070/0038 (Wartebudgets)

## Tests (Anknüpfungspunkte)
- `tests/tdd/test_vergleich_befehlsablehnung.py` (Fixture `versand` zählt Transporte; Test ~:142 erwartet Übergangsantwort → in S2 umzudrehen; :221 belegt `_ROUTE_ONLY`-Verhalten ohne Namen)
- `test_eingangsauswahl_trip_und_vergleich.py`, `test_vergleich_pause_weiter.py`, `test_trip_eingang_regressionskontrolle.py`
- `test_kanaltreue_adhoc_antwort.py`, `test_compare_dispatch_channel_fanout.py`, `_compare_kette_fixtures.py`, `test_compare_send_lock.py`, `test_compare_preview_user_isolation.py`

## Laufzeit-Befund (#2234 vs. #2439)
- #2234 nennt 75 s für 3 Orte, gemessen 2026-08-15 — **vor** der Parallelisierung (#1765 B1b, `e0d53bc7e`, 2026-08-16). Aktueller Wert ungemessen.
- Trip-HEUTE nach #2439 auf Staging (19.10.): max 32,7 s, Median 21,9 s.
- Vergleichspfad nutzt keinen Cache, 96 h Abruf je Ort, max 4 Orte parallel.
- **Offen für /20-analyse:** reale Laufzeit des Vergleichs messen (Staging oder lokal mit echter API), dann entscheiden, ob #2234 vorgezogen/mitgeschnitten werden muss.

## Risks & Considerations
- **Laufzeit:** ungemessen; kann das 60-s-Budget reißen; langes HEUTE blockiert denselben Kanal (Spec 2439 Entscheidung 6).
- **Adressierung ohne Namen:** `_ROUTE_ONLY` lässt report/heute/morgen ohne Namen am Vergleich vorbeilaufen („Kein aktiver Trip…"). Entscheidung nötig: `kinds` erweitern + Mehrdeutigkeits-Rückfrage (wie pause/weiter) — betrifft Hilfe-Text und Schlüsselmengen.
- **Kanal-Override:** Anfragekanal, der im Preset nicht aktiviert ist, fehlt in `effective_channels`; Trip setzt den Anfragekanal per `_resolve_channel_flags` aktiv — Parität bewusst entscheiden.
- **Zieltag:** `target_date` und `tage_ab_ortstag` müssen gemeinsam gesetzt werden; „morgen" → Versatz 1.
- **Doppelversand:** Send-Lock `"compare"` mit Scheduler/Handversand teilen.
- **Mail-Validator:** Compare-Mail-Inhalt unverändert, trotzdem `email_spec_validator.py` gegen echte Staging-Mail Pflicht.
- **Ladehinweis** am Vergleich bisher unterdrückt — bei langen Läufen nötig?
- **Mandantentrennung:** Zwei-Nutzer-Test Pflicht.

## Analysis

### Type
Feature (Scheibe S2 von #2282, Epic #2345 P5)

### Verifizierte Abweichungen zur Kontext-Tabelle
- `report`/`heute`/`morgen` **ohne Namen** bei reinem Vergleichsnutzer (kein Trip) landen NICHT in der Übergangsantwort, sondern seit #2417 bei `KEIN_AKTIVES_ZIEL_TEXT` „Kein aktiver Trip. Dieser Befehl gilt nur für Trips, nicht für Ortsvergleiche." (`trip_selection.py:239-263`) — mit S2 sachlich falsch, muss sich ändern.
- `effective_compare_briefing_channels` verlangt für Premium-SMS zusätzlich `preset["alert_channels"] is not None` (#2293, `compare_alert_channels.py:55`).
- `send_one_compare_preset` gibt ein Tupel zurück; `send_compare_preset` ein dict `{"status", "fehlende_orte"}`; Codes: ok/already_in_progress/no_weather/no_channels/channels_unreachable/invalid_preset. Seit #2286 (`8a0036794`) ist „alle Orte fehlerhaft → no_weather" unbedingt (:611).
- `send_compare_report` hat keinen `restrict_to_channel` — Einschränkung nur über ein Ein-Element-`effective_channels`; Kanalsatz entsteht in `send_one_compare_preset:530`.

### Laufzeit (Zusatzauftrag #2234 vs. #2439) — gemessen 2026-10-22
`run_comparison_parallel` (`comparison_parallel.py:86`), live Open-Meteo, kalt, ohne Render/Versand, lokal **ohne** Météo-France-Schlüssel (401 → Ersatzquelle eu_direct). Skript: Scratchpad `m.py`.

| Variante | Lauf 1 | Lauf 2 | Lauf 3 |
|---|---|---|---|
| 3 Orte | 11,2 s | 9,7 s | 14,1 s |
| 6 Orte | 25,5 s | 19,0 s | 17,1 s |

Budget #2439: < 60 s je Lauf, Median < 45 s → **gehalten, #2234 wird NICHT vorgezogen.** Vorbehalt: Render/Versand und Météo-France fehlen → Staging-Kaltlauf mit ≥ 6 Orten als AC. Ladehinweis „⏳ Wetter wird geladen…" am Vergleich für report/heute/morgen einschalten (Parität, 10–25 s stille Wartezeit).

### Seiteneffekt briefing_log (geprüft, kein Defekt)
On-demand-Einträge (`on_demand=True`) werden von der Rückwärts-Ableitung `briefing_slots._log_bezeugt_versand` (:367ff) übersprungen → eine Anfrage nimmt dem Nutzer nicht sein reguläres Briefing (#1725 AC-12). `send_compare_preset` setzt `on_demand=True` → Anker/Erst-Briefing-Markierung unberührt (:767). Slot im Log: `"evening" if tage_ab_ortstag else "morning"` (truthy-Test; 0 → morning korrekt).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_report_scheduler.py | MODIFY | `_resolve_channel_flags` (:2121) Restrict-Zweig (:2150-2165) in geteilte Modulfunktion auslagern, Methode delegiert |
| src/services/user_tier.py o. neue kleine Datei | MODIFY/CREATE | `resolve_restricted_channel_flags(restrict, user_id)` — EINE Auflösung für Trip + Vergleich (ADR-0097) |
| src/services/scheduler_dispatch_service.py | MODIFY | `restrict_to_channel` + `tage_ab_ortstag` an `send_compare_preset` (:797) / `send_one_compare_preset` (:455, :530); `None` = byte-gleich |
| src/services/compare_slot_scheduler.py | MODIFY | Ortstag-Berechnung (:173, Zeitzone des Presets) in `preset_ortstag(...)` extrahieren; Cron und Befehl nutzen sie |
| src/services/trip_command_processor.py | MODIFY | `_dispatch_compare` (:1378) → neuer Versandzweig statt `_compare_transitional` (:1416, entfällt); Antworttexte über dieselben Tabellen wie Trip (`_report_reply_body` :2649, `_on_demand_failure_body` :890) mit Label Trip/Ortsvergleich; `invalid_preset` + `fehlende_orte` ergänzen; heute/morgen bei Erfolg `suppress_email_reply=True` |
| src/services/trip_selection.py | MODIFY | Adressierung ohne Namen (nach PO-Entscheidung, s. u.) |
| src/services/inbound_telegram_reader.py | MODIFY | Ladehinweis am Vergleich für report/heute/morgen (:335-400) |
| Hilfe-Text / `_COMMAND_SPECS` (:257-291) | MODIFY | `hilfe` am Vergleich zeigt report/heute/morgen |
| tests/tdd/test_vergleich_befehlsablehnung.py | MODIFY | :142 (Übergangsantwort) und :258 (Ladehinweis unterdrückt) umdrehen |
| tests/tdd/test_ortsvergleich_befehle_versand.py (Name vorläufig) | CREATE | report mehrkanalig, heute/morgen kanaltreu + Ortstag, Fehlercodes, Lock, Zwei-Nutzer-Test, Parität Kanal-Auflösung Trip/Vergleich |
| docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md / neue S2-Spec | MODIFY/CREATE | AC-11 abgelöst |

### Scope Assessment
- Files: ~8 produktiv + 2 Tests + Spec
- Estimated LoC: ca. +170/-40 produktiv (Limit 250)
- Risk Level: MEDIUM — einzige Trip-Berührung ist die Auslagerung der Kanal-Auflösung (abgesichert durch `test_kanaltreue_adhoc_antwort.py`); Versandpfad Vergleich wird nur um optionale Parameter erweitert.

### Technical Approach
Ein gemeinsamer Pfad: alle drei Befehle rufen den bestehenden Handversand `send_compare_preset` (Send-Lock „compare", `on_demand=True`, `weather_failure_as_outcome=True`).
- `report` → ohne Einschränkung, mehrkanalig über `effective_compare_briefing_channels`, Zieltag heute (wie Web-Handversand; S1-Spec :45-49).
- `heute`/`morgen` → `restrict_to_channel=msg.channel`, `tage_ab_ortstag` 0/1, Zieltag = Ortstag des Presets + Versatz (gleiche Funktion wie Cron, ADR-0044/0051).
- Eingeschränkter Pfad: Anfragekanal aktiv auch ohne Preset-Opt-in, **nur Tarif-Gates** (`sms_allowed`/`premium_sms_allowed`) wie beim Trip; die `alert_channels`-Bedingung gilt dort NICHT (expliziter Nutzerwunsch, Parität ADR-0095). In der Spec ausdrücklich festhalten.
- Gates im Versand (`can_send_*`, SMS-Tageslimit) bleiben aktiv; unerreichbarer Anfragekanal → `channels_unreachable`-Text.
- Reihenfolge: (1) Kanal-Auflösung extrahieren, Trip grün halten (2) `preset_ortstag` + Parameter im Dispatch (3) Prozessor-Weiche + Texte (4) Ladehinweis (5) Adressierung ohne Namen (6) Staging: echte Compare-Mail (≥ 3 Orte) gegen `email_spec_validator.py`, Kaltlauf 6 Orte, Telegram-/Premium-SMS-Eingang echt.

### Adressierung ohne Namen — Varianten
| Variante | Verhalten | Folgen |
|---|---|---|
| A | Nur Vergleich(e), kein Trip → an den Vergleich (mehrere Vergleiche → Rückfrage). Trip + Vergleich → Trip wie bisher; Vergleich mit Namen | Trip-Nutzer unverändert; weicht vom Issue-AC-3-Entwurf ab |
| B | Wie pause/weiter: bei Trip + Vergleich immer Rückfrage | Erfüllt AC-3-Entwurf wörtlich; jedes `heute` ohne Namen (auch inReach) kostet eine Rückfrage-Runde für alle Trip-Nutzer mit Vergleich |
| C | Unverändert, nur mit Namen | Reiner Vergleichsnutzer bekommt sachlich falschen Text — verworfen |
Empfehlung Tech Lead war A. **PO-Entscheidung 2026-10-22: Variante B — „Immer nachfragen“.** `report`/`heute`/`morgen` kommen wie `pause`/`weiter` in die Beide-kinds-Auswahl (`_BEIDE_KINDS_ONLY_SCHLUESSEL`, `trip_selection.py:71`; `_COMMAND_SPECS` :257-291): Trip + Vergleich ohne Namen → Rückfrage ohne Wirkung (S1-Muster AC-4, Premium-SMS ≤ 160 Zeichen); nur Vergleich(e) → Vergleich bzw. Rückfrage bei mehreren; nur Trip → unverändert. Spec muss die Trip-Regressionsfälle (nur Trip, kein Vergleich) ausdrücklich als unverändert sichern und die Telegram-Query-Keys (glance/gewitter etc.) bleiben trip-only.

### Dependencies
Upstream: drei Inbound-Reader (`resolved_kind`/`resolved_preset_id`), `_COMMAND_SPECS`, `trip_selection`. Downstream: `briefing_log` (kind-neutral), Send-Lock, SMS-Tageslimit, Premium-SMS-Tarif-Gate, Compare-Mail-Renderer (unverändert, `X-GZ-Mail-Type: compare`). #2275 (Premium-SMS-Zweig) erfüllt.

### Open Questions
- [x] PO: Adressierung ohne Namen bei Trip + Vergleich → **B (immer nachfragen)**, entschieden 2026-10-22.
- Keine weiteren offenen Fragen.
