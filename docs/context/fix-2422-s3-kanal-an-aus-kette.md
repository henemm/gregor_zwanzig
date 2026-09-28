# Context: fix-2422-s3-kanal-an-aus-kette

## Request Summary
Issue #2422 „Konfiguration und Auslieferung nicht getestet!" — PO-Auftrag: **alle Testlücken zwischen
Einstellung und Auslieferung finden**. Scheibe **S3** (PO-bestätigt 28.09.): Kette
Kanal an/aus · Versandzeiten · `email_format` · `sms_threshold` · `bucket`/`channel_layouts_per_report`
vom gespeicherten Trip-JSON bis zur tatsächlich ausgelieferten Nachricht. S1 (Invarianten-Test
Metrik×Kanal, PR #2434) und S2a (Editor-Anzeige = gespeichert = ausgeliefert, PRs #2443/#2445) sind
live. Offen bleiben S2b (#2438), S4 (Alarme), S5 (Ortsvergleich), Fix-Scheiben B1/B2/B3(#2429)/B5.

## Verbindliche Vorgaben aus dem Bestand (nicht neu verhandeln)
Quellen: `docs/context/fix-2422-konfig-auslieferung-testluecken.md` (Schnitt, L2/L3),
`docs/specs/modules/fix_2422_s2a_editor_gleich_gespeichert.md` (Scheibenplan Z. 72, Deckungstabelle).
- Orakel = gespeicherte Einstellung (Trip-JSON), **nie** eine Produktfunktion.
- Einstieg ist das **Persistenzformat des Editors**, echter Loader, echter Formatter/Scheduler; Naht nur am Transport.
- „Still weg" ist nie korrekt: im Produkt sichtbar machen ODER als Defekt führen.
- Ausnahme-Register-Ratsche (nur Richtung Schließung); Mutations-Pflichtfänge für `/50`; kein Mock-Theater.
- Kaskade und Editor-Änderungen `bucket`/`channel_layouts_per_report` sowie „mehrere Kanäle in einem
  Speicherzyklus" sind laut S2a-Deckungstabelle explizit **S3** (Spec S2a Z. ~737).
- K8 (per-Metrik morning/evening_enabled beim Speichern) ist in S2a gefixt und entfällt hier.
- Geschätzt im Schnittplan: ~0 LoC produktiv / ~200 LoC Test — durch den Befund unten überholt (siehe Risiken).

## Feld-Kette je Einstellung (Editor → Go → Python → Steuerstelle)
| Einstellung | Steuerstelle beim Versand |
|---|---|
| Kanal an/aus (`send_email/telegram/sms/premium_sms`) | `TripReportSchedulerService._resolve_channel_flags` (`src/services/trip_report_scheduler.py:1748-1803`); SMS zusätzlich `sms_allowed`, Premium `premium_sms_allowed`; Versand je Flag `notification_service.py:594/620/643/665`; alle aus ⇒ `no_channel_configured` (`:575-581`) |
| Versandzeiten `morning_time/evening_time` | Go kappt beim Schreiben auf volle Stunde (`internal/store/slot_hour_normalization.go:71-80`); Python `_slot_stunde` (`trip_report_scheduler.py:131-140`), Fenster in `_collect_due_trips` (`:526-590`), Go-Scheduler löst nur stündlich aus (`internal/scheduler/scheduler.go:612-629`) |
| Gesamtschalter/Pause | `report_config.enabled`, `paused_until`, `skip_next` in `_get_active_trips` (`:894-951`) |
| `email_format` full/compact | `resolve_report_render_options` (`src/services/report_config_resolver.py:114-150`), Aufruf `trip_report_scheduler.py:1355`; compact ⇒ `render_compact`, Text-Mail |
| `sms_threshold` | `src/output/renderers/trip_report.py:329-365` liest **nur die globale** Metrikliste; Mail-Pillen aus `dc.metrics` (`email/html.py:1466`, `plain.py:204`, `compact.py:198`). Nicht verwechseln mit `alert_channel_thresholds.sms` (= S4) |
| `bucket`/`order`/`channel_layouts_per_report` | Kaskade `src/app/models.py:739-819` (per_report > per_channel > global), Globalmaximum `:993-1015`, Loader `loader.py:905-1030`; Go `display_config` flach gemergt (`internal/handler/config_merge.go:11-22`) |

## Bestehende Tests (Bestand) und Lücken
Bestand: Matrix `tests/tdd/test_einstellung_gleich_auslieferung.py` + Orakel
`tests/helpers/einstellung_auslieferung_orakel.py` + Fixtures `tests/tdd/_einstellung_auslieferung_fixtures.py`
+ Goldens `tests/fixtures/einstellung_auslieferung/golden_{a,b,c}.json` + Aufzeichner
`tests/helpers/transport_mitschrift.py`. Vorlage für Scheduler-Einstieg: `tests/tdd/test_kanaltreue_adhoc_antwort.py:290-352`.

**Wichtig:** `render_golden` baut den `TripReportRequest` direkt aus `rc.send_*` und **umgeht damit
`_resolve_channel_flags`, `resolve_report_render_options` und den Scheduler**. Die S1/S2a-Matrix beweist
deshalb nichts über Kanal an/aus, `email_format`, Zeiten.

Nicht bis zur Auslieferung bewacht:
1. `send_X=false` aus Trip-JSON auf dem regulären Slot-Weg (nur „alle vier an" ist geprüft, `test_kanaltreue_adhoc_antwort.py:290`).
2. `email_format=compact`: JSON → `load_trip` → Scheduler → gesendeter Body / `mail_format`.
3. `sms_threshold`: Editor-JSON → `trip_report.py:329-365` → SMS/Kurzform/Premium-Text (`golden_c.json:93,101` enthält Werte, wird nicht ausgewertet).
4. `channel_layouts_per_report` (und Vorrang vor `channel_layouts`): kein Golden, kein Test bis Text.
5. Versandzeiten im Editor-Format: Kette Editor → Go-Kappung → Python-Fälligkeit nirgends durchgehend.
6. Go-PUT-Roundtrip der **vollständigen** `report_config` (`send_*`, Zeiten, `email_format`) mit zwei Nutzern; TS-Serialisierung von `report_config` gegen eingefrorenes Golden.
7. Per-Slot-Schalter am Trip (siehe Hauptbefund) — überhaupt kein Test.

## HAUPTBEFUND (selbst gegengeprüft): Einzel-Slot-Schalter „Morgen aktiv"/„Abend aktiv" wirken nicht
- Editor: Checkbox „Aktiv" je Slot (`frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:97`),
  schreibt `report_config.enabled = morning_enabled || evening_enabled` plus `morning_enabled`/`evening_enabled`
  (`EditReportConfigSection.svelte:277-279`, `VersandTab.svelte:209-211`).
- Python: `TripReportConfig` (`src/app/models.py:1105-1200`) und Loader-Abschnitt `loader.py:583-617` haben **kein**
  Feld `morning_enabled/evening_enabled` (Treffer in `models.py` betreffen Metrik-Ebene `:668`/`:740` bzw. Compare).
  Scheduler prüft nur `rc.enabled is False` (`:933`, `:179`) — für beide Slots gleich.
- Go leitet die flachen Trip-Felder ausschließlich aus `rc["enabled"]` ab (`internal/store/trip.go:93-96`),
  Python-Pendant `loader.py:648-649`.
- Folge: „Abend aus, Morgen an" liefert trotzdem beide Slots. Trip-Übersicht zeigt pro Slot
  (`frontend/src/lib/utils/rightColumn.ts:70-71`, `cockpitHelpers568.ts:61-62`) ⇒ **Anzeige ≠ Versand**.
- Ortsvergleich hat die Semantik korrekt (`src/services/compare_slot_scheduler.py:168-170`) — Trip nicht.
- Trip-Entsprechung zu B7. Einordnung offen für `/20-analyse`: Nutzersichtbares Fehlverhalten (Triage-Kriterium a)
  ⇒ produktiver Fix in dieser Scheibe vs. eigenes Issue + Register-Eintrag. Die PO-Beschwerde („Konfiguration
  und Auslieferung nicht getestet") legt einen Fix nahe; bei Aufnahme neue Befund-Kennung (`test_ac18` sperrt
  Wiederverwendung von B4, B6–B9, K8, K9).

## Weitere Verdachtsstellen (für die Analyse zu prüfen, ungeprüft)
1. `channel_layouts_per_report` gewinnt in der Kaskade, der Editor schreibt/zeigt es nie ⇒ Altdaten neutralisieren
   Editor-Änderungen an `channel_layouts` still. Go behält es beim Speichern.
2. `sms_threshold` in Kanal-Layouts (Loader liest, `loader.py:985/1020`) wirkt in der SMS nicht; Mail nutzt ggf. kollabierte vs. unkollabierte `dc` — nicht zu Ende verfolgt.
3. `syncSendFlags` (`trip-detail/briefingChannelGating.ts:49`) schreibt still `send_*=false`, wenn ein Kanal keine aktive Metrik hat; Auslieferung danach ungeprüft.
4. Go kappt Minuten auf volle Stunde beim Schreiben; zeigt der Editor nach dem Speichern die gekappte Zeit?
5. Default `send_email=True` bei fehlendem Feld (`loader.py:587`) vs. Editor-Anzeige — Golden ohne `report_config` prüfen.
6. Merge-vs-Replace: Go-PUT flach je Top-Level-Key, verschachtelte Objekte/Listen ersetzt (`internal/handler/trip.go:335-360`); Python `save_trip` mergt mit `_deep_merge_preserve_unknown` (`loader.py:1947`).

## Existing Patterns / Erweiterungspunkte (Wiederverwendung statt Neubau)
- Neue Testdatei im selben Muster, neue Golden(s) (z. B. `golden_d.json`) mit `email_format=compact`,
  gemischten `send_*`, Slot-Zeiten, per-Slot-Flags, `channel_layouts_per_report`.
- Einstieg über `TripReportSchedulerService.send_due_reports(now_utc)` + Aufzeichner statt `render_golden`.
- Orakel `erwartete_kaskade` (`orakel.py:292-360`) um per_report-Vorrang erweitern.
- Go-Bein: Muster `internal/handler/fix_go_rmw_merge_1082_1103_test.go`; TS-Bein: Muster
  `.../versand-tab/__tests__/merge_report_config_read_modify_write.test.ts`.
- Zwei-Nutzer-Test Pflicht bei jedem datenbewegenden Endpoint.

## Dependencies
- Upstream: Loader (`src/app/loader.py`), Kaskade (`src/app/models.py`), Renderer (`src/output/renderers/trip_report.py`), Go-Store/Handler.
- Downstream: Scheduler-Versand, Preview-Pfad (`test_preview_render_options_parity.py`), Cockpit-Anzeige.

## Existing Specs
- `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md` (S1), `fix_2422_s2a_editor_gleich_gespeichert.md` (S2a)
- ADR-0050 (Metrik-Kaskade), ADR-0053 (Ortsvergleich), `fix_1677_sms_reihenfolge.md` (DEC-2 durch S2a abgelöst)

## Risks & Considerations
- **Scope-Sprung:** Bestätigt sich der Hauptbefund als Defekt, ist S3 nicht mehr „nur Tests" — LoC-Limit 250 (`loc_limit_override` bei Bedarf), ggf. Schnitt S3a (Tests+Register) / S3b (Fix).
- **Parallelsitzung #2417** ändert uncommittet `notification_service.py` und `trip_report_scheduler.py` — vor `/50` abstimmen (`ListAgents`/`SendMessage`, nie MQ `gregor`→`gregor`).
- **Herkunftssperre** `app/origin_guard.py` (#2406): Nutzerkennung ohne „test"/„tdd", `sms_verified_number` Pflicht; kann Kanal-Tests im Hauptcheckout rot machen.
- Nicht `uv run pytest` ohne benannte Testdateien; keine echten Sendungen an Produktiv-Empfänger.
- Schema-relevante Dateien (`models.py`, `loader.py`, `internal/model/*.go`, `store.go`) lösen Pre-Snapshot-Hook aus; Bestandsdaten bleiben per Read-Modify-Write erhalten.
- Ein Fix an der Slot-Semantik (`enabled` vs. Per-Slot) berührt Bestandstrips: Migration/Default so, dass Trips ohne Per-Slot-Felder unverändert ausliefern.
- Mail-Änderungen ⇒ Staging-Mail + `briefing_mail_validator.py` (Trip-Briefing), nicht `email_spec_validator.py`.

## Analysis

### Type
Bug (Nutzersichtbares Fehlverhalten, Triage-Kriterium a) **plus** Testlücken-Scheibe. PO-Auftrag #2422 „alle Testlücken finden".

### Gegenprüfung des Hauptbefunds (in /20 am Code bestätigt)
- Editor schreibt `report_config.morning_enabled`/`evening_enabled` (+ `enabled = m || e`): `VTSchedulePlan.svelte:97` (Checkbox „Aktiv"), `VersandTab.svelte:209-211`.
- Python `TripReportConfig` (`models.py:1105ff`) kennt beide Felder nicht; Loader `loader.py:583-617` liest sie nicht; Scheduler prüft nur `rc.enabled is False` (`trip_report_scheduler.py:179` und `:933`) — beide Stellen kennen `report_type`, werten ihn aber nicht aus.
- Flache Trip-Felder werden aus `rc.enabled` abgeleitet (`loader.py:648-649`, `internal/store/trip.go:93-96`) → Anzeige (`rightColumn.ts:70`, `cockpitHelpers568.ts:61`) zeigt Slot-Zustand, Versand ignoriert ihn.
- Ortsvergleich macht es richtig (`compare_slot_scheduler.py:168-170`, `api_contract.md:2640`). Freigegebene Trip-Spec `versand_tab_route.md` AC-3 sichert nur **Persistenz** zu, nicht Wirkung — die Lücke ist Spec-blind + testblind.
- Loader-Kommentar `loader.py:640-647` behauptet „`enabled` ist der EINZIGE Schalter" — das war eine Annahme aus #1250 S4, sie widerspricht dem Editor. Kein ADR legt diese Semantik fest (Grep über `docs/adr`: kein Treffer).
- Prod-Bestand (`/var/lib/gregor`) für `hem` nicht lesbar → Anzahl betroffener Prod-Trips **nicht messbar**; nicht als „keine" annehmen.

### Bewertung der Verdachtsstellen
| # | Stelle | Stand |
|---|---|---|
| H | Per-Slot-Schalter wirkt nicht | **bestätigt, Defekt** → Fix in dieser Scheibe |
| 3 | `syncSendFlags` schreibt still `send_*=false`; kennt `send_premium_sms` nicht | Kern ungeprüft; Test der Kette nötig, Premium-Lücke als Befund führen |
| 1,2,4,5,6 | per_report-Vorrang, `sms_threshold` in Layouts, Minuten-Kappung, `send_email`-Default, Go-Merge | in /30 je als Test-AC; falsche Erwartung ⇒ als Befund im Register führen, **nicht** still ausbessern |

### Affected Files (with changes)
| File | Change | Beschreibung |
|---|---|---|
| `src/app/models.py` | MODIFY | `TripReportConfig` + `morning_enabled`/`evening_enabled: Optional[bool]=None` (None ⇒ Rückfall auf `enabled`) |
| `src/app/loader.py` | MODIFY | Report-Config lesen/schreiben (Roundtrip), flache Ableitung `:648-649` aus Per-Slot statt nur `enabled` |
| `src/services/trip_report_scheduler.py` | MODIFY | Slot-Prüfung in `_get_active_trips` (`:933`) und Fälligkeits-Helfer (`:179`) je `report_type` |
| `internal/store/trip.go` | MODIFY | flache Felder aus Per-Slot-Keys, Rückfall `enabled` |
| `tests/tdd/test_kanal_an_aus_kette.py` (o. ä.) | CREATE | Scheduler-Einstieg `send_due_reports`, Aufzeichner am Transport |
| `tests/tdd/_einstellung_auslieferung_fixtures.py`, `tests/fixtures/einstellung_auslieferung/golden_d.json` | MODIFY/CREATE | Trip mit `compact`, gemischten `send_*`, Slot-Zeiten, per-Slot, `channel_layouts_per_report` |
| `tests/helpers/einstellung_auslieferung_orakel.py` | MODIFY | per_report-Vorrang in `erwartete_kaskade` |
| `internal/handler/*_test.go`, `versand-tab/__tests__/*.test.ts` | CREATE | Go-PUT-Roundtrip `report_config` (2 Nutzer), TS-Serialisierung |
| `docs/specs/modules/…`, Ausnahme-Register | MODIFY | Spec S3, neue Befundkennung (B4, B6–B9, K8, K9 gesperrt durch `test_ac18`) |

### Scope Assessment
- Produktiv: ~4 Dateien, ca. +50 LoC (Python ~35, Go ~15). Test: ca. +250–350 LoC (nicht limitzählend laut Regel „nur produktive Spec-Dateien" — vor /40 `workflow.py status` fragen, ggf. `loc_limit_override 500`).
- Risk Level: **MEDIUM** — berührt Versand-Fälligkeit und Schema-Dateien (Pre-Snapshot-Hook), Verhaltensänderung nur für Trips, deren Editor Per-Slot=false gespeichert hat (genau die Trips, bei denen Anzeige ≠ Versand ist).

### Technical Approach (Empfehlung)
1. **Ein Schnitt, nicht zwei.** Fix + Tests zusammen (Test-first: erst rot am Nutzerbild „Abend aus ⇒ nur Morgen-Mail", dann Fix). Kein getrenntes Fix-Ticket: PO-Beschwerde ist genau dieser Fall, Triage-Kriterium a.
2. **Semantik:** Per-Slot `None` ⇒ `enabled` (Altdaten unverändert); `enabled=False` schaltet beide ab (Gesamtschalter bleibt Master); Per-Slot `False` schaltet nur diesen Slot ab. Orakel = gespeichertes Trip-JSON.
3. **Ein Prüfort:** eine geteilte Hilfsfunktion `slot_aktiv(rc, report_type)`, von `_get_active_trips` und dem Fälligkeits-Helfer benutzt (Prüfort = Wirkort, verhindert Nachbau-Drift).
4. **Testbeine:** (a) Python Scheduler-Einstieg: `send_X=false`-Matrix, `compact`, Slot-Zeiten/Fenster, per-Slot, `sms_threshold`, per_report-Vorrang; (b) Go-Roundtrip `report_config` vollständig, zwei Nutzer; (c) TS-Serialisierung gegen eingefrorenes Golden; (d) Staging: Trip mit Abend=aus → kein Abend-Versand (Mail via `briefing_mail_validator.py`).
5. **Mutations-Pflichtfänge für /50:** Slot-Prüfung entfernen; `None`-Rückfall kippen; Per-Slot-Lesen im Loader entfernen; Go-Ableitung zurück auf nur `enabled`.

### Dependencies
Upstream: Editor-Persistenz (`report_config`), Go-Store/Handler, Loader. Downstream: Scheduler-Versand, Preview-Pfad (`test_preview_render_options_parity.py`), Cockpit-Anzeige (bleibt unverändert, wird durch Fix erst wahr). Parallelsitzung #2417 hat `notification_service.py`/`trip_report_scheduler.py` uncommittet in Arbeit → vor /50 per `ListAgents`/`SendMessage` abstimmen.

### Open Questions
- [ ] (PO, nicht technisch) keine — Freigabe der ACs folgt in /30.
- [ ] Prod-Bestand mit gesetzten Per-Slot-Flags nicht messbar (Rechte); Verhaltensänderung nur bei Trips mit Per-Slot=false, im Selftest/Staging absichern.
- [ ] Rückfall `enabled=True, morning=False, evening=False` (Editor schreibt dann `enabled=false`) — in Spec als AC explizit festlegen.
