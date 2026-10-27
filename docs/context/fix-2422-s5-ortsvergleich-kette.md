# Context: fix-2422-s5-ortsvergleich-kette

## Request Summary
#2422 Scheibe S5 (L4): Kette Ortsvergleich testen — was im Vergleichs-JSON (`ComparePreset`) eingestellt ist, muss im tatsächlich gesendeten Text je Kanal ankommen (Metrik-Auswahl `channel_active_metrics`, Kanalwahl, Slots, Alarm-Kanäle). Bugs, die dabei auftauchen, werden im Ticket gefixt, nicht als Ausnahme geparkt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/scheduler_dispatch_service.py:430` | `send_one_compare_preset(...)` — Einstieg; Sinks `mail_sink`/`sms_sink`/`telegram_sink`/`premium_sms_sink` |
| `src/services/scheduler_dispatch_service.py:414-427` | `_effective_compare_briefing_channels` — Wrapper |
| `src/services/compare_alert_channels.py:32-63` | Briefing-Kanalwahl (E-Mail immer an; Telegram/SMS/Premium je `send_*` + `can_send_*` + Tier) |
| `src/services/compare_alert_channels.py:66-77` | `effective_compare_telegram_style` (liest `display_config.telegram_style`, Default `rich`) |
| `src/services/report_config_resolver.py:~300-339` | baut `CompareRenderOptions`; `enabled_metrics_by_channel` nur für email/telegram/sms, NICHT premium_sms |
| `src/output/renderers/compare_metric_ids.py:200-240` | `resolve_channel_enabled_metrics` — Kanal darf Grundauswahl nur abwählen (Schnitt), Reihenfolge = Kanal-Liste |
| `src/services/notification_service.py:1240-1370` | `send_compare_report`; Premium-SMS bekommt denselben `sms_text` wie SMS (:1342-1364); E-Mail-Import zur Laufzeit aus `output.channels.email` (~:1295) |
| `src/services/compare_alert.py:110,603,632` | Compare-Alarm-Kanäle über `effective_alert_channels` (getrennt vom Briefing) |
| `src/services/compare_slot_scheduler.py:168-170` | Slot-Semantik morning/evening (S3 D17 verwies auf S5) |
| `internal/model/compare_preset.go:48,76,91-99,107,134` | `DisplayConfig` (opake Map), `SendTelegram/Sms/PremiumSms`, `AlertChannels`, `EndDate` |
| `internal/handler/compare_preset.go:70,338-340` | End-Date-Validierung + Sentinel `""`→nil |

## Existing Patterns
- Orakel-Grundsatz S1: Erwartung nur aus rohem `json.load` + statischem Katalog, nie aus Produktcode (`tests/helpers/einstellung_auslieferung_orakel.py`; Parser `parse_email_html/plain`, `parse_telegram_rich`, `parse_sms_artig`, `vorbedingung_pruefen`).
- `tests/helpers/transport_mitschrift.py` (`aufzeichner_installieren`) patcht `ns.EmailOutput` etc.
- `tests/tdd/test_kanal_an_aus_kette.py` (S3): Datei in User-Verzeichnis schreiben, echter Loader, Kanalmatrix × Tier.
- `tests/tdd/test_compare_dispatch_channel_fanout.py`: `send_one_compare_preset` mit Sinks, `_install_engine_and_snapshot_seams`.
- Go-Zwei-Nutzer-Muster: `internal/handler/compare_preset_alert_channels_test.go:361`; Python: `tests/tdd/test_alarm_szenario_mandantentrennung.py`.

## Dependencies
- Upstream: Go-Store/PUT (Preset-JSON) → Python-Loader → `report_config_resolver` → Renderer → `send_compare_report` → Transporte.
- Downstream: Compare-Mail (Header `X-GZ-Mail-Type: compare`, Validator `email_spec_validator.py`), Telegram, SMS, Premium-SMS.

## Existing Specs
- `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md` (S1, L4-Zeile :51/:63)
- `fix_2422_s3_kanal_an_aus_kette.md` (D17 :99, :632-646), `fix_2422_s4_alarm_familie_kette.md` (:47-52, :295-302: Compare-Alarm-Kette ausgeklammert, wartete auf #2293)
- `docs/context/fix-2422-konfig-auslieferung-testluecken.md` (:113-115 teils veraltet)

## Befunde / Lücken (ungeprüfte Zusicherungen)
1. `display_config.channel_active_metrics[kanal]` → Zellen im gesendeten Text je Kanal: keine Kette Preset-JSON→Loader→Resolver→Sink getestet (nur `test_compare_kanal_metriken.py` als reiner Render).
2. Semantik „Kanal nur abwählen / ohne Eintrag folgt Grundauswahl / leer heißt leer / Reihenfolge aus Kanal-Liste“ steht nur im Docstring.
3. **Produktfrage:** Premium-SMS hat keine eigene Metrik-Auswahl und bekommt den SMS-Text. Weicht `channel_active_metrics["premium_sms"]` von `["sms"]` ab, ist unklar, ob Bug oder Absicht.
4. Kanal an/aus: `send_email` wird nicht persistiert (E-Mail immer an); `send_premium_sms` ohne `alert_channels` ⇒ kein Premium-Briefing (Altbestand-Eckfall); Tier-Gates `sms_allowed`/`premium_sms_allowed`.
5. Header `X-GZ-Mail-Type: compare` über die Sink-Naht nicht beobachtbar.
6. Go-Roundtrip `display_config.channel_active_metrics` (opake Map) durch PUT/GET ohne Verlust: kein Test.
7. `end_date`-Sentinel-Kette (PUT `""` → Feld fehlt → Versand nicht ausgesetzt): nicht als Test gefunden; `api_contract.md:2217` (KL-7) widerspricht evtl. dem Handler-Code.
8. Compare-Alarm-Kette (Radar/amtlich am `ComparePreset`): Voraussetzung #2293 ist erfüllt (CLOSED, PR #2457 live 29.09.) — Nachziehen jetzt möglich.
9. Slot-Regel (morning/evening) im Ortsvergleich (S3-D17).
10. Telegram-Kurzstil im Compare-Briefing: nicht abschließend geprüft, ob `telegram_style` den Briefing-Renderaufruf erreicht.

## Risks & Considerations
- **Mitschrift-Falle:** `send_compare_report` importiert `EmailOutput` zur Laufzeit aus `output.channels.email`; die Kanalmitschrift patcht `ns.EmailOutput` ⇒ fängt Compare-Mail vermutlich nicht ein ⇒ 0 Sendungen könnten grün wirken. `vorbedingung_pruefen` bzw. `mail_sink` nutzen.
- SMS-Tageslimit (`_sms_gate_reserve`) und Tier-Profil in Tests setzen, sonst blockt SMS/Premium still.
- Erwartung unabhängig aus JSON rechnen, nicht `resolve_channel_enabled_metrics` aufrufen (sonst Spiegel-Test).
- `end_date`: schreiben `""`, lesen FEHLT — Tests mit `toBeUndefined()`/`is None`, nie truthy/falsy.
- Multi-User: jeder datenbewegende Test mit zwei Nutzern.
- Bekannte Abweichung nie befristet ins Register (PO-Regel) — im Ticket fixen oder als Produktfrage vorlegen.

## Analysis

### Type
Bug/Testlücke (Sammel-Ticket #2422, Scheibe S5 „Kette Ortsvergleich"): Prüfen und ggf. fixen, dass jede Einstellung am `ComparePreset` im tatsächlich gesendeten Text je Kanal ankommt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_compare_einstellung_auslieferung_kette.py` | CREATE | Kette Preset-JSON → Loader → Resolver → Sink für E-Mail/Telegram/SMS/Premium-SMS; Erwartung aus rohem JSON (Orakel), zwei Nutzer |
| `internal/handler/compare_preset_*_test.go` | CREATE/MODIFY | Go-Roundtrip `display_config.channel_active_metrics` + `end_date`-Sentinel, zwei Nutzer |
| `src/services/report_config_resolver.py` (~:336) | MODIFY (nur falls Befund) | `enabled_metrics_by_channel` ohne `premium_sms` — Produktfrage/Fix |
| `src/services/notification_service.py` (:1342-1364) | MODIFY (nur falls Befund) | Premium-SMS bekommt `sms_text` |
| `docs/reference/api_contract.md:2217` | MODIFY | KL-7 „end_date nicht zurücksetzbar" widerspricht Handler-Sentinel `""`→nil |
| `docs/specs/modules/fix_2422_s5_ortsvergleich_kette.md` | CREATE (Phase 3) | Spec mit ACs |

### Scope Assessment
- Files: ~4–6
- Estimated LoC: +400 (überwiegend Tests) / Produktcode nur bei Befunden
- Risk Level: MEDIUM — Tests sind additiv; Risiko liegt in gefundenen Abweichungen (Premium-SMS-Metriken, Slot-Regel, Alarm-Kette) und dem Zwang, sie im Ticket zu fixen

### Technical Approach
Wie S3/S4: eigene Testdatei, Preset-JSON in User-Verzeichnis schreiben, echter Loader, `send_one_compare_preset` mit Sinks, Erwartung ausschließlich aus rohem JSON + Katalog (`einstellung_auslieferung_orakel.py`), nie aus `resolve_channel_enabled_metrics`. Blöcke: (A) `channel_active_metrics` je Kanal (Abwählen/Grundauswahl/leer/Reihenfolge); (B) Kanal an/aus × Tier (`send_*`, `can_send_*`, Premium ohne `alert_channels`); (C) Slots morning/evening (D17); (D) Compare-Alarm-Kette Radar/amtlich (#2293 erfüllt); (E) `end_date`-Sentinel; (F) Telegram-Kurzstil erreicht Briefing-Render; (G) Mail-Header `compare` über `mail_sink`. Mitschrift-Falle: `EmailOutput` wird zur Laufzeit importiert → `mail_sink` nutzen, `vorbedingung_pruefen` gegen 0 Sendungen. SMS-Tageslimit/Tier in Tests setzen.

### Dependencies
Go-PUT/Store → Python-Loader → `report_config_resolver` → Renderer → `send_compare_report` → Transporte; Compare-Alarm getrennt über `effective_alert_channels`. Vorbilder: S3 `test_kanal_an_aus_kette.py`, S4-Kette, `test_compare_dispatch_channel_fanout.py`.

### Open Questions
- [ ] **Produktfrage (Befund 3):** Premium-SMS hat keine eigene Metrik-Auswahl, bekommt SMS-Text. Soll `channel_active_metrics["premium_sms"]` existieren, oder ist „Premium = SMS-Inhalt" gewollt (dann als AC festschreiben)? Empfehlung: gewollt festschreiben, sofern Editor keinen eigenen Premium-Schalter anbietet — im Spec-Schritt am Editor prüfen.
- [ ] Ist Compare-Alarm-Kette (Befund 8) in S5 oder eigene Scheibe S6? Empfehlung: in S5 aufnehmen, falls LoC-Limit (Override 500) reicht, sonst S6.
- [ ] `end_date`: Verhalten real messen (Handler vs. KL-7-Doku), Doku angleichen.
