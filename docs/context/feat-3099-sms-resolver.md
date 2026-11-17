# Context: feat-3099-sms-resolver

## Request Summary
Phase 3d von #3047 (Epic #3058): SMS (Trip und Orte) bezieht Metrik-Auswahl, Reihenfolge und Roh/Einfach aus dem Kanal-Listen-Resolver (ADR-0121). Amtliche Warnungen bleiben bewusst am Ende (ADR-0121 Nr. 6: „E-Mail und Telegram vorn, SMS und Premium-SMS hinten"; keine Zeile der Liste, nicht abwählbar). Eigene Fallliste `fallliste_sms.json` im Prüfkatalog, vom Wächter mitgezählt. PO-Auflage (Kommentar 17.11.): Fälle im heutigen Format (`channel_layouts.sms`), werden beim Neuschnitt (#3122/ADR-0124) umformuliert.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/trip_report.py:145-148` | `_channel_view = resolve_channel_lists(_dc_uncollapsed, "trip", report_type)` liegt schon vor; `.sms` / `.premium_sms` ungenutzt |
| `src/output/renderers/trip_report.py:375-490` | Trip-SMS-Altpfad: `:389` `_dc_uncollapsed.get_metrics_for_channel("sms", report_type)` → `sms_metric_ids`, `_sms_position_by_metric` (:390-399), deaktivierte Specs #944, `_sms_format_by_metric` (nur `SMS_FORMAT_MODE_METRIC_IDS`), `build_extended_metric_specs`, `SMS_MULTI_SYMBOLS_BY_METRIC` (:414-472); `:485` `SMSTripFormatter().format_sms(...)`, `:517` in Report |
| `src/output/renderers/trip_report.py:478-483` | einzige wirksame SMS-Schwelle: `trip.alert_channel_thresholds["sms"]` → `sms_alert_min_level` (bleibt unberührt); `sms_threshold` je Metrik wirkt nicht mehr (#2792 E1) |
| `src/output/renderers/trip_report.py:316` + `src/output/renderers/email/helpers.py:1283` | Telegram-Vorbild #3098: `telegram_metric_configs(rows, dc)` ChannelRow → MetricConfig |
| `src/output/renderers/sms_trip.py:66,96,133,549,561` | `build_extended_metric_specs`, `sms_format_fields`, amtliche Einträge, `format_sms` (Specs mit `position`) |
| `src/output/tokens/builder.py:318,600-605` | Warnblock `_official_alerts` am Ende, danach nur `X?`/`_fire`/`_wintersport` |
| `src/services/report_config_resolver.py:311,345-352,71` | Orte-SMS liest bereits `view.sms` → `enabled_metrics_by_channel["sms"]`, `metric_formats("sms")`; Premium = `sms_text` |
| `src/output/renderers/comparison.py:1223,1341,1389,1415` | `render_compare_sms`, `_sms_location_variants`, amtliche Einträge Orte, Endmarker `X?` |
| `src/services/scheduler_dispatch_service.py:1072-1078`, `compare_preview_service.py:90` | Orte-Versand/Vorschau SMS; Telegram-Kurzform = SMS-Text |
| `src/services/channel_list_resolver.py:24,53-54,159-162,234-235` | Resolver; `premium_sms` = Kopie von `sms` |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py:36,68-76` | `TEILDATEIEN` (+ "sms"), `PY_TEST_GLOBS` (+ `test_3099_*`) |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte,editor}.json` | Bestands-SMS-Fälle (`trip-r7-sms-*`, `R7-KAT-trip-sms-*`, `R7-KAT-trip-premium-gleich-sms-kuerzung`, Orte `O…`/`R…`, `E-R8-T1-SMS-LADEN-*`) – bleiben, IDs global eindeutig |

## Existing Patterns
- #3096 (Mail) und #3098 (Telegram): Zeilen einmal aus dem Resolver auf dem UNKOLLABIERTEN dc, Adapter, Altpfad gelöscht, Goldens byte-gleich, eigene Fallliste + Wächter-Registrierung, Zwei-Nutzer-Nachweis, Nachweis „Altpfad wird nicht mehr gelesen" per Unterklasse, die `get_metrics_for_channel("sms")` abweichend überschreibt.
- Orte-SMS ist schon resolver-basiert → dort nur Fälle/Tests (Muster #3098).
- Premium-SMS hat keinen eigenen Inhaltspfad (sendet `sms_text`), nur eigenes Zeichenlimit 153.

## Dependencies
- Upstream: `resolve_channel_lists`, `trip_channel_metrics`, `get_metric`, `SMS_FORMAT_MODE_METRIC_IDS`, `SMS_MULTI_SYMBOLS_BY_METRIC`.
- Downstream: Trip-SMS-/Premium-SMS-Versand, Telegram-Kurzform (Orte), Vorschau, Golden `tests/golden/test_sms_golden.py`, `tests/golden/vergleichs_mail/telegram_sms.*`.

## Existing Specs
- `docs/specs/modules/feat_3057_kanal_liste_resolver.md`, `feat_3096_mail_resolver.md`, `feat_3098_telegram_resolver.md`, `feat_3047_einstellung_gleich_mail_pruefkatalog.md`
- `docs/reference/sms_format.md` §2 (:80 „Token-Reihenfolge (fix)" – muss auf Resolver-Folge angepasst/präzisiert werden), §3.4c (:310), §3.4e (:379 Quelle Kurzform), §9, §12 Changelog; `premium_sms_format.md:25,130`; ADR-0121, ADR-0095, ADR-0049.

## Tests
`tests/golden/test_sms_golden.py`, `tests/tdd/test_issue_944_disabled_metrics_sms.py`, `test_compare_sms_official_alerts.py`, `test_compare_sms_kuerzel.py`, `test_3047_runde7_orte_sms_kuerzung.py`, `test_official_alert_sms_marker.py`, `test_ac6_sms_byte_identity_without_wc.py`, `test_compare_premium_sms_versand.py`, `test_telegram_kurzform_ignoriert_telegram_auswahl.py`, Fixtures `_sms_einfach_fixtures.py`, `_sms_token_format_fixtures.py`, `test_3047_r7_kanaele_trip.py`.

## Risks & Considerations
- Zugestellte SMS muss in allen Bestandsfällen byte-gleich bleiben (Golden), inkl. Kürzung (≤160, Premium 153).
- Abgewählte Metriken erzeugen deaktivierte Specs für SMS-Symbole (#944) – Adapter darf nur enabled-Zeilen als Ausgabe liefern, die Deaktiviert-Info aber nicht verlieren.
- Roh/Einfach nur für `SMS_FORMAT_MODE_METRIC_IDS`; `format=None` ≠ Roh (Lehre #3098).
- Warnblock-Position: bleibt hinten (vor `X?`/Feuer/Wintersport, wie heute) – nicht durch die Liste verschiebbar.
- `premium_sms`-Zeilen = `sms`-Zeilen; Premium bleibt textgleich zur SMS.
- Zwei-Nutzer-Nachweis.

## Analysis

### Type
Feature (Ausgabe-Umstellung Trip-SMS auf Kanal-Listen-Resolver, ADR-0121; Orte-SMS bereits umgestellt → nur Fälle/Tests)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | :389-399 + :441-445 — `sms_metric_ids`, `_sms_position_by_metric`, `_sms_format_by_metric` aus `_channel_view.sms` (Resolver-Lauf :145) statt `get_metrics_for_channel("sms")`; Kommentarblock kürzen |
| `src/output/renderers/sms_trip.py` (oder `email/helpers.py`) | MODIFY | kleiner Adapter `sms_rows_to_maps(rows)` → `(ids, position_by_metric, format_by_metric)`, isoliert testbar |
| `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json` | CREATE | eigene SMS-Fallliste (Trip + Orte), Format `channel_layouts.sms` (PO-Auflage), IDs global eindeutig |
| `tests/tdd/test_3099_*.py` | CREATE | Fälle-Runner, Altpfad-Nachweis (Unterklasse überschreibt `get_metrics_for_channel("sms")` abweichend), Zwei-Nutzer-Nachweis, Warnblock bleibt hinten, Premium = SMS-Text |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN` + "sms" (:36), `PY_TEST_GLOBS` + `test_3099_*` (:68-76) |
| `docs/reference/sms_format.md` | MODIFY | §2 (:80) „fix" → „Standardreihenfolge; wirksam ist die Resolver-Folge, nur Warnblock/`X?`/DBG fix am Ende"; Quelle `resolve_channel_lists(...).sms`; §12 Changelog |
| `docs/specs/modules/feat_3099_sms_resolver.md` | CREATE | Spec |

### Scope Assessment
- Files: ~7 (2 Code, 3 Tests/Fixtures, 2 Docs)
- Estimated LoC Code: +~30/-~20; Tests/Fälle zusätzlich
- Risk Level: LOW — `get_metrics_for_channel` delegiert bereits an `trip_channel_metrics`, der Resolver liefert identische Menge/Folge; Goldens müssen byte-gleich bleiben.

### Technical Approach
- SMS-eigener Adapter (kein Umbau von `telegram_metric_configs`; SMS braucht keine `MetricConfig`, nur `{id: index}` und `{id: mode}`).
- `ids = {r.metric_id for r in rows if r.enabled}`, `position = {r.metric_id: i}` (Resolver-Folge), `format = _resolve_format_mode({"format_mode": r.format}, id)` nur für `SMS_FORMAT_MODE_METRIC_IDS`.
- Byte-Gleichheit geprüft: alle vier `SMS_FORMAT_MODE_METRIC_IDS` haben `format_modes=("raw","symbol")`, default `symbol` (metric_catalog.py:581-650, :820) → `format="raw"` bleibt Roh, `None` → Katalog-Standard. Unbekannte IDs wirkungslos (`SMS_SYMBOL_BY_METRIC` nach ID), `_resolve_format_mode` fängt KeyError.
- #944 deaktivierte Specs unverändert: `enabled = metric_id in ids`.
- Einziger Leser von `get_metrics_for_channel("sms")` in `src/` ist trip_report.py:389 (grep) → Unterklassen-Nachweis aussagekräftig.
- Warnblock bleibt in builder.py:600-605 am Ende, keine Zeile der Liste.
- Premium-SMS: Versand nimmt `report.sms_text` (premium_sms.py:19); Resolver-Zweig `premium_sms` (eigene Trip-Kaskade) wird in `src/` nicht gelesen → bewusste Nicht-Änderung, in Spec festhalten.
- Reihenfolge: Spec → Fälle + RED-Tests → Adapter + Austausch → Goldens prüfen → Wächter/Docs.

### Dependencies
`resolve_channel_lists`, `trip_channel_metrics`, `_trip_format`, `app.loader._resolve_format_mode`, `SMS_FORMAT_MODE_METRIC_IDS`, `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC`, `build_extended_metric_specs`. Downstream: Trip-SMS/Premium-SMS-Versand, Goldens `tests/golden/test_sms_golden.py`, `test_issue_944_disabled_metrics_sms.py`, `test_ac6_sms_byte_identity_without_wc.py`.

### Open Questions
- keine (Premium-eigene Trip-Liste bleibt bewusst außerhalb; Warnblock-Position ist durch ADR-0121 Nr. 6 entschieden)

## Befund aus TDD RED (17.11.)
- Premium-Limit 153: Trip-Premium-SMS sendet heute unverändert `report.sms_text` (bis 160 Zeichen, belegt durch `test_3047_r7_kanaele_trip.py::test_ac23_sms_kuerzt_vom_listenende_warnung_bleibt`). Die Spec-Formulierung „Premium höchstens 153" (AC-1/AC-6) trifft für lange Trip-Texte nicht zu; maßgeblich ist ADR-0095/Spec-Grundsatz „Bestandsfälle unverändert". Keine Verhaltensänderung in #3099; der Adversary soll das bewusst prüfen, ggf. eigenes Issue.
- RED: 11 rot (8 Adapter `sms_rows_to_maps` ImportError, 2 AC-9 Altpfad statt Resolver, 1 AC-11 Wächter kennt `sms` nicht), 41 grün (Bestandsschutz). Wächter-Registrierung (`TEILDATEIEN` + "sms", `PY_TEST_GLOBS` + `test_3099_*`) gehört in die Umsetzung; Probelauf ergab 0 Fehler mit der neuen Fallliste.
