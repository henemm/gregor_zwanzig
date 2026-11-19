# Context: feat-3101-ein-vokabular

## Request Summary
Issue #3101 (Epic #3058, Phase 3f von #3047): Die Orte-Kanallisten im `MailViewModel` (`email`, `telegram`, `sms`, `premium_sms`, `layout_channels`) tragen heute Renderer-Kennungen (`temp_max`), Ausblick/Stundenverlauf/`rows` Katalog-IDs (`temperature`). Ziel: überall Katalog-IDs, die Aufweitung auf Renderer-Zeilen macht der Resolver bzw. der Adapter vor dem Renderer. Zugestellte Ausgabe bleibt bytegleich. Entscheidung steht in Spec `docs/specs/modules/feat_3122_was_steht_wo.md` Teil A Nr. 2 (Z. 99) und Nr. 129 („überall Katalog-IDs“).

## Abhängigkeit B1b (PR #3140, offen)
- Branch `feat/3122-b1b-ausgaben`, alle 6 CI-Checks grün, `CLEAN`, aber **nicht gemerged**: wartet auf Validator-Nachweis gegen echt zugestellte Staging-Mails (Cloud-Sitzung hatte keinen Server-Zugang). Keine laufende Sitzung arbeitet daran (`workflow.py sessions`, 18.11.).
- B1b ändert dieselben Stellen: `channel_list_resolver.py` (+52/-16: `ChannelRow.source`, `_abo_schalter`, `Grundauswahl.unaufloesbar/nie_eingestellt`, `resolve_enabled_metrics_report`), `report_config_resolver.py` (+158/-144), `email/outlook.py`, `email/helpers.py`, `compare_briefing_aufbau.py`, `compare_alert.py`, `placements.py`, `validator_render_service.py`, plus Fixtures `fallliste_orte.json`/`fallliste_trip.json` und Tests `test_einstellung_gleich_mail_orte_tabelle.py`, `test_orte_ausgaben_lesen_view_model.py`.
- PR #3142 (B3b) soll nur zusammen mit B1b gemerged werden.
- Spec-Reihenfolge: B1 → B2 → B3 …, „#3101 wird vor B2 gebaut“. B2b ist bereits auf `main` (ebe5c5325), d. h. #3101 hinkt der Planreihenfolge nach.
- **Empfehlung für /20-analyse:** B1b zuerst ausliefern (Validator-Nachweis auf dem Server erbringen, mergen) und #3101 danach auf `main` aufsetzen. Alternativ auf dem B1b-Branch stapeln; ein paralleler Bau auf `main` erzeugt sichere Konflikte in Resolver und `report_config_resolver`. Entscheidung in der Analyse treffen (Tech-Lead).

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/channel_list_resolver.py` | `ChannelRow` (:42-47), `MailViewModel` (:53-81, Docstring :59-61 nennt Zwei-Vokabular-Lage), `_compare_view` (:416-456) mit `_layout_rows` (:400-413), `_kanal_rows` (:222-232), `grundauswahl` (:182-189, `renderer` als Renderer-Kennungen, `parents={}` für Orte), `_orte_standard` (:157-162, `CV2_ZEILEN` = Renderer-Kennungen), `katalog_id()` (:235-242), `vm_lists` (:245-261), `legacy_lists` (:264) |
| `src/output/renderers/compare_metric_ids.py` | `FRONTEND_TO_RENDERER_METRIC_ID` (:16-56), `_renderer_ids_for_kennung` (:315-332, Aufweitung Katalog → Renderer), separate Renderer→Katalog-Map für Alarm/Token (:68-73), `resolve_enabled_metrics(_report)` |
| `src/output/renderers/compare_metric_catalog.py` | `COMPARE_METRIC_CATALOG` (:107-195): Katalog-Key → Katalog-ID + Aggregation; Reihenfolge bestimmt Aufweitung (temperature → temp_max, temp_min; wind_chill → min, max) |
| `src/output/renderers/compare_outlook_metric_ids.py` | `_kennungen_aus_renderer_ids` (:268) Rückrichtung |
| `src/services/report_config_resolver.py` | :311-350 baut `channel_rows` `[(renderer_id, simplified)]` aus `layout_channels` und `CompareRenderOptions.enabled_metrics_by_channel` (Renderer-Kennungen); `view.hourly` erwartet Katalog-IDs |
| `src/services/placements_view_service.py` | :228/:633 `vm.sms` → `_orte_sms_liste` (:609), :396 `vm.telegram` → `telegram_metric_configs`, :308/:383/:561 lesen `vm.rows` (Katalog-IDs); :140 API-Zeilen Katalog-IDs |
| `src/services/placements.py` | :470-475 Vergleich Alt-/Neusicht über `katalog_id()` |
| `src/services/compare_briefing_aufbau.py` | nutzt `channel_rows`/`enabled_metrics_by_channel` (Renderer-Seite) |
| `src/services/compare_alert.py` | :72 `temp_max_c` → `temperature` (Alarm-Seite, eigene Abbildung) |
| `src/output/renderers/email/helpers.py` | `telegram_metric_configs` (:1283) |
| `docs/adr/0121-*.md` | Nachtrag 2b Nr. 1 (:37-48): Zwei-Vokabular-Lage „bewusst“, „Vereinheitlichung gehört zu #3058“ → braucht neuen Nachtrag (wird abgelöst) |

## Mapping Katalog-ID → Renderer-Kennung (Orte)
snow_depth→snow_depth_cm · fresh_snow→snow_new_cm · sunshine→sunny_hours · wind→wind_max · cloud_total→cloud_avg · visibility→visibility_min · precipitation→precip_sum · uv_index→uv_max · **temperature→temp_max, temp_min** · thunder→thunder_max · gust→gust_max · cape→cape_max (nicht wählbar) · freezing_level→freezing_level · rain_probability→pop_max · wind_direction→wind_direction_avg · **wind_chill→wind_chill_min, wind_chill_max** · humidity→humidity_avg · dewpoint→dewpoint_avg · snowfall_limit · precip_type · cloud_low/mid/high→*_avg · pressure→pressure_avg.

Konsequenz: Eine Katalog-ID kann zwei Renderer-Zeilen tragen; ein Haken pro Kanal deckt beide ab. Wo Bestandsdaten je Kanal nur eine der beiden Renderer-Zeilen wählen (z. B. nur `temp_max`), kann eine reine Katalog-ID-Liste das nicht ausdrücken → für Bytegleichheit muss die Aufweitung die gespeicherte Teilauswahl respektieren (`grund.renderer`-Filter in `_kanal_rows` macht das heute). Das ist das Kernrisiko.

## Existing Patterns
- Trip-Pfad nutzt bereits Katalog-IDs in allen Kanälen (`trip_report.py:145`, `email/helpers.py:333`) mit Adapter `channel_metric_configs`; Vorbild für Orte.
- Neuer `placements`-Eingang: `_kanal_rows` weitet Katalog-ID auf Renderer-Kennungen, gefiltert durch `grund.renderer`. Nach #3101 würde diese Aufweitung in einen Adapter am Renderer-Eingang wandern, das View-Model bliebe Katalog-ID.
- Abgeleitete Größen folgen der Eltern-Zeile (Spec Nr. 2); bei Orten heute `parents={}`.

## Dependencies
- Upstream: `COMPARE_METRIC_CATALOG`, `FRONTEND_TO_RENDERER_METRIC_ID`, `metric_catalog.get_metric`, `placements.read_placements/legacy_placements`.
- Downstream: `report_config_resolver` → `CompareRenderOptions` → Orte-Renderer (E-Mail, Telegram, SMS, Premium-SMS); `placements_view_service` (Beispielwerte/SMS-Budget der Tabelle, B2b); `placements.py` Alt/Neu-Vergleich; Validatoren über zugestellte Mail.
- Frontend: nutzt Katalog-Keys (`temp_max_c`) bzw. Katalog-IDs aus der Placements-API, keine nackten Renderer-Kennungen → voraussichtlich unbetroffen.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (Teil A Nr. 2, Nr. 129, AC-11 Bytegleichheit Altbestand)
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` (Prüfkatalog `tests/fixtures/einstellung_gleich_mail/`)
- `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`, `feat_3099_sms_resolver.md`, `feat_3100_premium_sms_fallliste.md`, `feat_3097_orte_stundenverlauf_darstellung.md`

## Tests, die das heutige Vokabular festnageln
`tests/tdd/test_placements_aufloesung.py` (:69-73, 128-130, 418, z. B. `_ids(vm,"email") == ["temp_max","wind_max"]`), `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_3098_telegram_resolver.py`, `test_3099_sms_resolver.py`, `test_channel_metric_matrix.py`, `test_placements_umrechnung_altbestand.py`, `test_placements_fixpunkt.py`, `test_einstellung_gleich_mail_editor_standard.py`, `tests/helpers/kanal_liste_orakel.py`, `test_compare_kanal_metriken.py`, `test_3047_runde7_orte_*.py`, `test_selection_conservation_rendered.py`, `tests/helpers/vergleichs_mail_fixture.py`. Fixtures in `tests/fixtures/einstellung_gleich_mail/` sind Konfig-Eingang (Katalog-Keys), Golden-HTML/TXT = Bytegleichheits-Orakel.

## Risks & Considerations
- **Bytegleichheit:** Teilauswahl (nur Höchst- oder nur Tiefstwert, nur eine Windchill-Seite) und Reihenfolge der Aufweitung müssen erhalten bleiben; Golden-Mails + Mail-Validatoren (`email_spec_validator.py`) gegen Staging sind Pflicht, Renderer-Commit-Gate greift bei Mail-Inhalts-Dateien.
- **Kollision mit B1b** (siehe oben) — größtes Prozessrisiko.
- **ADR:** Nachtrag 2b Nr. 1 von ADR-0121 wird abgelöst → neuer Nachtrag/ADR-Verweis, `tests/test_adr_index_drift.py`.
- Keine Datenmigration (Renderer-Kennungen nicht gespeichert), aber View-Model-Vertrag ändert sich für alle Orte-Ausgaben und die B2b-Tabelle (`placements_view_service`).
- Alarm-Seite (`compare_alert`, Renderer→Katalog-Map in `compare_metric_ids.py:68-73`) hat eigene Abbildung; prüfen, ob sie mitvereinheitlicht wird oder außerhalb des Scopes bleibt.
- Zwei Nutzer / Mandantentrennung nicht betroffen (reine Funktion), trotzdem bestehende Tests grün halten.

## Analysis

### Type
Feature (Refactoring des View-Model-Vertrags, Ausgabe bytegleich)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/channel_list_resolver.py` | MODIFY | `ChannelRow` + Feld `aggregation`; `metric_id` = Katalog-ID für Orte-Kanäle; `_compare_view`, `_layout_rows`, `_kanal_rows`, `_orte_standard`/`vm_lists`, `katalog_id()` (wird für Orte trivial), Docstring Zwei-Vokabular entfällt |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | Helfer (Katalog-ID, Aggregation) → Renderer-Kennung und Rückrichtung, gestützt auf `COMPARE_METRIC_CATALOG` |
| `src/services/report_config_resolver.py` | MODIFY | Ein Adapter an der Grenze `channel_rows` (:345-349) / `enabled_metrics_by_channel` (:387-393): View-Model-Zeilen → Renderer-Kennungen |
| `src/services/placements_view_service.py` | MODIFY | `vm.sms`/`vm.telegram`-Leser (:228, :396, :582, :609/_orte_sms_liste, :633, :693) über den Adapter |
| `src/services/placements.py` | MODIFY | Alt/Neu-Vergleich (:470-475) auf Katalog-ID normalisieren, Max/Min-Doppelzeilen fallen zusammen |
| `docs/adr/0121-*.md` (+ README-Index) | MODIFY | Neuer Nachtrag löst Nachtrag 2b Nr. 1 ab |
| `docs/reference/api_contract.md` | MODIFY (falls MailViewModel dort beschrieben) | Vertrag Katalog-ID + Aggregation |
| Tests: `test_placements_aufloesung.py`, `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_3098_telegram_resolver.py`, `test_3099_sms_resolver.py`, `test_channel_metric_matrix.py`, `test_placements_umrechnung_altbestand.py`, `tests/helpers/kanal_liste_orakel.py` | MODIFY | Erwartungen von Renderer-Kennung auf (Katalog-ID, Aggregation) |
| `tests/tdd/test_3101_ein_vokabular.py` | CREATE | Teilauswahl je Kanal, Reihenfolge max/wind/min, Bytegleichheit Golden-Mails |

Nicht betroffen: `compare_briefing_aufbau.py`, `email/helpers.py` (bekommen Renderer-Listen aus `CompareRenderOptions`), Frontend (liest nur Placements-API), Alarm-Pfad `compare_alert.py` (liest das View-Model nicht; eigene Abbildung, wird von B1b umgebaut → bewusst außerhalb des Scopes).

### Scope Assessment
- Files: ~6 produktiv + ADR/Doku, ~9 Testdateien
- Estimated LoC: produktiv +150..200 / -80; Tests +200..300
- Risk Level: MEDIUM-HIGH (Vertrag aller Orte-Ausgaben, Bytegleichheit Pflicht)

### Technical Approach (Entscheidung Tech Lead)
**Variante A:** Jede `ChannelRow` bleibt 1:1 zu einer Renderer-Zeile, trägt aber `metric_id` = Katalog-ID plus `aggregation` (z. B. `temperature`/`max`). Aufweitung und Rückabbildung über `COMPARE_METRIC_CATALOG` (trägt `metric_id` + `aggregation`). Ein zentraler Adapter vor dem Renderer bildet auf `FRONTEND_TO_RENDERER_METRIC_ID` ab.

Begründung (im Code geprüft, `channel_list_resolver.py:432-445`): `channel_active_metrics`/`channel_layouts` können je Kanal enger sein als `active_metrics` (z. B. nur `temp_max` in SMS) und eine eigene Reihenfolge haben (`temp_max, wind_max, temp_min`). Die Kontextidee „nur Katalog-ID + Filter über `grund.renderer`" verliert beides → bricht AC-11.

| | A: Katalog-ID + Aggregation je Zeile | B: nur Katalog-ID, Filter `grund.renderer` | C: Katalog-ID + Teilmenge je Zeile |
|---|---|---|---|
| Teilauswahl je Kanal bytegleich | ja | nein | ja |
| Reihenfolge max, wind, min | ja | nein | nein |
| Spec-konform („überall Katalog-IDs") | ja (Zusatzfeld) | ja | ja |
| Aufwand | mittel | gering | mittel |

Deckt sich mit Spec #3122 Teil A Nr. 2 („weitet auf die Auswertungen der Grundauswahl auf"); Präzedenz: Zusatzfeld `ChannelRow.source` aus B1b.

### Reihenfolge zu B1b (PR #3140) — Entscheidung
B1b ändert `report_config_resolver.py` :295-430 komplett (genau die Adapter-Stelle) sowie `ChannelRow`/`Grundauswahl` → paralleler Bau auf main = sichere Konflikte.
**Festlegung:** Spec und RED-Tests jetzt; vor `/50-implement` B1b mit Validator-Nachweis auf Staging ausliefern und mergen, #3101 danach auf main aufsetzen. Ist B1b bei Phase 5 noch offen: auf `feat/3122-b1b-ausgaben` stapeln, nie parallel auf main.

### Dependencies
`COMPARE_METRIC_CATALOG`, `FRONTEND_TO_RENDERER_METRIC_ID`, `_renderer_ids_for_kennung`, `_kennungen_aus_renderer_ids`; Downstream `CompareRenderOptions` → Orte-Renderer (4 Kanäle), B2b-Tabelle, Alt/Neu-Vergleich.

### Pflicht-Nachweise
Golden-Mails/TXT in `tests/fixtures/einstellung_gleich_mail/` unverändert; `email_spec_validator.py` gegen echt zugestellte Staging-Mail; Renderer-Commit-Gate; ADR-Index-Drift-Test.

### Open Questions
- keine Produktfrage offen (Entscheidung steht in Spec #3122 Nr. 2/129).
