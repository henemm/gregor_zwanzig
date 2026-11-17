# Context: feature-3098-telegram-resolver

## Request Summary
Phase 3c von #3047 (Epic #3058): Telegram (Trip und Orte) bezieht Metriken, Reihenfolge und Roh/Einfach direkt aus dem Kanal-Listen-Resolver (ADR-0121), eigene Fallliste im Prüfkatalog, geprüft an der echten Telegram-Ausgabe. Die offenen Telegram-Funde aus #3063 werden mit erledigt.

## Stand #3063 (wichtig für den Scope)
Beide Funde aus #3063 sind auf dem aktuellen Stand (Worktree = origin/main) bereits behoben (#3047 Runde 7):
- Kopf: `src/output/renderers/narrow.py:854` nutzt `briefing_typ(report_type, lang)` (`src/output/renderers/briefing_typ.py:10`, Katalog `mail.kopf.typ_*`), nicht mehr `report_type.title()`.
- Windrichtung Roh: `trip_report.py` reicht `format_modes=build_format_modes(_dc_telegram)` an `render_telegram_bubbles`; Fälle `trip-r7-telegram-windrichtung-roh-{de,en}`, `-einfach`, `-roh-gleich-mail` grün (`tests/tdd/test_3047_r7_kanaele_trip.py`).
⇒ #3063 braucht nur noch den Nachweis an der echten Telegram-Ausgabe im neuen Pfad (bleibt grün) und kann mit #3098 geschlossen werden.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/channel_list_resolver.py` | Resolver: `resolve_channel_lists(dc, surface, report_type) -> MailViewModel` (:72), Felder `email/telegram/sms/premium_sms` als `ChannelRow(metric_id, enabled, format)`; `trip_channel_metrics` (:85) ADR-0050-Kaskade; `_trip_format` (:108); `_trip_model` (:117) setzt `format`→`format_mode` |
| `src/output/renderers/trip_report.py:141-160` | Muster aus #3096: `_email_rows = resolve_channel_lists(_dc_uncollapsed,"trip",report_type).email` VOR Kollabierung |
| `src/output/renderers/trip_report.py:295-340` | Trip-Telegram-Altpfad: `_dc_uncollapsed.get_metrics_for_channel("telegram", ...)` → `_dc_telegram` (enabled erzwungen) → `render_telegram_bubbles(dc=_dc_telegram, friendly_keys=build_friendly_keys(...), format_modes=build_format_modes(...))` |
| `src/output/renderers/email/helpers.py:1283` | `build_format_modes(dc)`: col_key → format_mode aus `MetricConfig` (nicht aus Resolver-Zeile) |
| `src/output/renderers/email/helpers.py:66` | `should_merge_wind_dir(dc)`: liest `format_mode == "scale"` aus `dc.metrics` |
| `src/output/renderers/narrow.py` | `render_telegram_bubbles`; `_cell` (:88) → `fmt_val(format_modes=)`; Layout via `render_for_channel("telegram", dc, report_type)` (:818); Kurzübersicht iteriert `dc.get_enabled_metric_ids()` (:917), Windrichtung-Merge (:915-919); Kopf (:854) |
| `src/services/report_config_resolver.py:311,387-393,237` | Orte: `resolve_channel_lists(display_config,"compare")`, füllt `enabled_metrics_by_channel["telegram"]` aus `view.telegram`; `metric_formats(channel)` |
| `src/output/renderers/comparison.py:917` | `render_compare_telegram(enabled_metrics, metric_formats, outlook…)` |
| `src/services/scheduler_dispatch_service.py:1077-1079` | Orte-Versand Telegram (Kurzform → SMS-Text) |
| `src/services/compare_preview_service.py:73` | Orte-Vorschau Telegram |
| `src/output/renderers/compare_metric_ids.py:253-294` | Altquelle `channel_active_metrics` (nur ohne `channel_layouts`) – Abbau ist #3102 |
| `tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte,validatoren,editor}.json` | Prüfkatalog; Telegram-Fälle heute verteilt in trip/orte (R7, P9) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | Wächter: `TEILDATEIEN` (:35), Pflichtfelder (:37), Status (:38), `PY_TEST_GLOBS` (:70), `pruefe_kanal_abdeckung` (:395) |

## Existing Patterns
- #3096 (Phase 3a): Zeilen EINMAL aus dem Resolver auf dem unkollabierten dc, Adapter `email_col_order(rows)` (metric_id → col_key, Folge erhalten, enabled/selectable filtern), Altpfad gelöscht, Golden-Mails byte-gleich.
- Orte-Telegram liest bereits `view.telegram` (über `resolve_compare_render_options`) – dort ist der Rest-Umbau klein.
- Telegram-Kurzform sendet den SMS-Text (ADR/telegram_format.md:39,46) – folgt der SMS-Auswahl, gehört zu #3099.

## Dependencies
- Upstream: `resolve_channel_lists`, `trip_channel_metrics`, Metrik-Katalog `get_metric` (col_key), `fmt_val`.
- Downstream: Telegram-Versand Trip (Scheduler/Handversand), Telegram-Vorschau, Golden `tests/golden/telegram_briefing/`, `tests/golden/vergleichs_mail/telegram_sms.*`.

## Existing Specs
- `docs/specs/modules/feat_3057_kanal_liste_resolver.md` (Resolver, ADR-0121)
- `docs/specs/modules/feat_3096_mail_resolver.md` (Muster Phase 3a)
- `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`, `feat_3097_orte_stundenverlauf_darstellung.md`
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md`
- `docs/reference/telegram_format.md`, ADR-0121, ADR-0095, ADR-0050

## Tests
`tests/golden/test_telegram_briefing_golden.py`, `tests/test_telegram_briefing_zweisprachig.py`, `tests/test_i18n_ratsche_narrow_telegram.py`, `tests/tdd/test_telegram_kurzstil_trip_briefing.py`, `tests/tdd/test_telegram_felt_temperature_overview.py`, `tests/tdd/test_3047_runde7_telegram_tagesfenster.py`, `tests/tdd/test_telegram_metric_notice.py`, `tests/unit/test_telegram_kuerzel_folgt_register.py`, `tests/unit/test_telegram_thunder_window_konsistenz.py`, `tests/tdd/test_3047_r7_kanaele_trip.py`, Resolver: `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_compare_render_options_resolver.py`.

## Risks & Considerations
- Zugestellte Telegram-Nachricht muss in allen bestehenden Fällen gleich bleiben (Golden-Telegram), ADR-0095 Kanal-Parität.
- `narrow.py` liest `dc` an mehreren Stellen direkt (Kurzübersicht, Fußzeile, Windrichtung-Merge, `render_for_channel`) – Reihenfolge/Format müssen an allen Stellen aus derselben Zeilenliste kommen (Adversary F004 aus #1719).
- Format-Standard ohne Angabe: Trip Katalog, Orte Roh – bleibt (Entscheidung #3096).
- „Eigene Fallliste“: neue Datei `fallliste_telegram.json` im Wächter registrieren vs. Bestand in trip/orte; Kanal-Abdeckung (`pruefe_kanal_abdeckung`) darf nicht sinken.
- Kurzform (SMS-Text) nicht Teil dieses Schnitts (#3099).
- Zwei-Nutzer-Nachweis (Mandantentrennung) wie bei #3096.

## Analysis

### Type
Feature (Umbau Telegram-Datenquelle auf Kanal-Listen-Resolver, ADR-0121, Phase 3c von #3047/Epic #3058)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/trip_report.py` | MODIFY | `_tg_rows = resolve_channel_lists(_dc_uncollapsed,"trip",report_type).telegram` neben `_email_rows` (:141); Altpfad :304-309 (`_dc_uncollapsed.get_metrics_for_channel("telegram", …)`) löschen; `_dc_telegram` aus Adapter; Kommentare :274-293/:311-322 aktualisieren |
| `src/output/renderers/email/helpers.py` (oder `channel_layout.py`) | MODIFY | Neuer Adapter `telegram_metric_configs(rows, dc)`: ChannelRow → MetricConfig-Liste (siehe Ansatz) |
| `src/output/renderers/narrow.py` | (keine Verhaltensänderung) | liest weiter `dc` an :818 `render_for_channel`, :907/:917/:964 `get_enabled_metric_ids`, :916 `should_merge_wind_dir` – alle aus derselben `_dc_telegram` |
| Orte (`report_config_resolver.py:311,387-393,237`, `comparison.py:947/966/1050`, `scheduler_dispatch_service.py:1079-1084`, `compare_preview_service.py:73-80`) | keine | bereits resolver-basiert (Reihenfolge + Format aus `view.telegram`/`metric_formats`); Fallback ohne `channel_layouts` ist #3102 |
| `tests/fixtures/einstellung_gleich_mail/fallliste_telegram.json` | CREATE | eigene Telegram-Fallliste (neue IDs) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN` (:35) + "telegram", `_syn_daten()` (:560-593), Fehlerzahl-Selbsttests (:775, :844), ggf. `PY_TEST_GLOBS` (:70) um `test_3098_*.py` |
| `tests/tdd/test_3098_telegram_resolver.py` | CREATE | Verhaltensnachweise an echter Telegram-Ausgabe (Trip+Orte, DE/EN, Zwei-Nutzer) |
| `docs/specs/modules/feat_3098_telegram_resolver.md` | CREATE | Spec |

### Scope Assessment
- Files: ~3 Code (1 MODIFY Kern, 1 Adapter), 3 Test/Fixture, 1 Spec
- Estimated LoC: Code ca. +50/-10; Tests ca. +200; JSON ca. +200
- Risk Level: MEDIUM (zugestellte Telegram-Nachricht, Golden `tests/golden/telegram_briefing/briefing_normalstil.{de,en}.txt` muss byte-gleich bleiben)

### Technical Approach
1. Trip: Resolver-Zeilen `.telegram` einmal auf dem UNKOLLABIERTEN dc ziehen (Muster #3096). Die Kaskade ist identisch (`trip_channel_metrics`), Menge/Folge ändern sich nicht – nur die Quelle.
2. Adapter Zeilen → MetricConfig ist PFLICHT (ein `email_col_order`-artiger col_key-Adapter reicht nicht), weil `narrow.py` an mehreren Stellen `dc` direkt liest und `build_friendly_keys`/`build_format_modes` MetricConfigs brauchen. Regeln:
   - nur `enabled`-Zeilen, unbekannte IDs überspringen, `enabled=True` erzwingen (`_dp_to_row` trägt nur enabled-Metriken ein);
   - `bucket`, `order`, `sms_threshold` aus dem Quell-MetricConfig der Grundauswahl übernehmen (`ChannelRow` hat nur `metric_id, enabled, format, order`; `render_for_channel` sortiert nach `bucket`/`order`, `channel_layout.py:147-150`, und kappt Telegram auf `max_table_cols`) – Gleichheit zur Resolver-Folge per Test sichern; Schwellen-Fallback wie `_globale_schwelle` (:154);
   - Format zurückschreiben (Umkehr von `_trip_format`, `channel_list_resolver.py:108`): `None` = Katalog-Standard (MetricConfig unverändert, NICHT als Roh deuten), `raw` → `format_mode="raw"`, `use_friendly_format=False`, sonst `format_mode=<format>`.
3. Orte: kein Code, nur Fälle/Tests.
4. Fallliste: neue `fallliste_telegram.json` mit NEUEN IDs; bestehende Telegram-Fälle (`trip-r7-telegram-*`, `R7-KAT-trip-telegram-*`, `T-P9-TG-*`, `O-R7-TG-*`, `O-P9-TG-*`) bleiben in trip/orte (IDs global eindeutig, andere Tests referenzieren sie). Fall-Achsen: Trip/Orte × DE/EN × Roh/Einfach (inkl. Windrichtung-Merge, #3063 P2) × Katalog- vs. Ziehfolge × Kanal-Ebene nie/leer/gesetzt × morning/evening; Kopf `briefing_typ` (#3063 P1). `format: "telegram"`, `aspekte` auswahl/reihenfolge/darstellung; `pruefe_kanal_abdeckung` darf nicht sinken.
5. Reihenfolge: RED (u. a. Nachweis, dass der Altpfad nicht mehr gelesen wird) → Adapter → `trip_report.py` umstellen, Altpfad löschen → Golden/Katalog grün → Fallliste + Wächter → #3063 mit schließen.

### Dependencies
- Upstream: `resolve_channel_lists`/`trip_channel_metrics`, `get_metric`, `fmt_val`, `build_friendly_keys`, `build_format_modes`, `should_merge_wind_dir`, `render_for_channel`.
- Downstream: Telegram-Versand Trip (Scheduler/Handversand), Telegram-Vorschau, Golden Telegram-Briefing. `tests/golden/vergleichs_mail/telegram_sms.*` (Kurzform = SMS-Text) unberührt → #3099.

### Risiken / Befunde gegen den Plan
- ChannelRow verliert `bucket`/`order`/`sms_threshold` → Adapter muss sie aus der Grundauswahl ergänzen, sonst kippen Spaltenverteilung, 7-Spalten-Kappung und Kurzübersicht-Schwelle.
- `format=None` darf nicht als Roh gelesen werden (friendly_keys-Menge änderte sich).
- Zwei-Nutzer-Nachweis: zwei display_configs mit unterschiedlicher Telegram-Folge/-Format im selben Prozess; Orte `orte_ac12_nutzer1/2.json` wiederverwenden.

### Open Questions
- keine Produktfragen (Format-Standard ohne Angabe: Trip Katalog, Orte Roh – Entscheidung #3096; Kurzform → #3099).

## TDD RED (Phase 5) – Hinweise für GREEN
- Testdatei: `tests/tdd/test_3098_telegram_resolver.py`; RED-Beleg `docs/artifacts/feature-3098-telegram-resolver/test-red-output.txt` (10 rot, 37 Bestandsschutz grün).
- AC-8 rot: Unterklasse `_AbweichendesModell` überschreibt `get_metrics_for_channel("telegram")` (HU/UV); Nachricht muss der Resolver-Liste (G/R/T) folgen. Achtung: `render_for_channel` liest ebenfalls `dc.get_metrics_for_channel(channel, ...)` – auf `_dc_telegram` (metrics = Adapter-Liste, keine Kanal-Ebenen) ist das der global-Zweig. Darum `_dc_telegram` ohne `per_channel_layouts`/`per_report_layouts` bilden (bzw. die Unterklasse fällt sonst wieder auf den Altpfad).
- Adapter-Test `test_adapter_bucket_order_schwelle_aus_grundauswahl`: Grundauswahl hat gust order 0, cloud_total order 2, Zeilen kommen cloud_total vor gust – Tabellenfolge muss der Zeilenfolge folgen ⇒ `order` aus `ChannelRow.order` (Resolver-Folge), `bucket`/`sms_threshold` aus dem Quell-MetricConfig.
- AC-9: GREEN legt `fallliste_telegram.json` an (IDs `telegram-*`, Pflicht-IDs siehe Test), trägt `"telegram"` in `TEILDATEIEN` und `tests/tdd/test_3098_*.py` in `PY_TEST_GLOBS` ein, passt `_syn_daten()`/Selbsttest-Zahlen an.
- Orte: nicht genannte Grundauswahl-Größen hängt Orte-Telegram hinten an; Tests speichern daher die volle Liste (Rest `enabled: false`), wie der Editor.
