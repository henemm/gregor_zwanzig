# Context: feat-3039-vergleich-kanal-layouts

## Request Summary
Issue #3039 (Vorlauf zu #3031, Teil von #2795 / Epic #2791): Der Ortsvergleich bekommt `display_config.channel_layouts` wie der Trip (`{email|telegram|sms: [{metric_id, enabled, use_friendly_format}]}`). Resolver und Vergleichs-Renderer (Mail, Telegram, SMS; Premium-SMS folgt der SMS) setzen Reihenfolge, Aus und Roh/Einfach je Kanal um. Bestandsvergleiche ohne `channel_layouts` rendern unverändert (Lesekompatibilität über `channel_active_metrics`, dann Grundauswahl). Teilmengen-Regel ADR-0050 bleibt.

Abhängiger Stand: #3031 (Frontend-Karte, schreibt den vollen Stand `channel_layouts` + `channel_active_metrics`) ist validiert und liegt als Entwurfs-PR #3042 auf `feat-3031-inhalt-je-kanal-listen`, Merge-Sperre bis #3039 live. Spec dort: `git show feat-3031-inhalt-je-kanal-listen:docs/specs/modules/feat_3031_inhalt_je_kanal_listen.md` (Zeilen 38/65/90/118: Roh/Einfach-Wahl hängt an `format_modes`, nicht an `has_friendly_format`).

## Related Files
| File | Relevance |
|------|-----------|
| src/app/models.py:668 `MetricConfig`, :799 `_sorted_by_layout`, :843 `per_channel_layouts`, :938-990 `get_metrics_for_channel`, :992 `_clip_to_global_maximum` | Trip-Vorbild: Kaskade, Sortierung, Schnitt gegen Grundauswahl |
| src/app/loader.py:62 `_resolve_format_mode`, :98 `_friendly_from_mode`, :1035-1066 (Lesen channel_layouts), :250 `compare_preset_from_dict` | Formatregel und Leser; Vergleich hält `display_config` als Dict |
| src/services/report_config_resolver.py:163 `CompareRenderOptions`, :215 `enabled_metrics_by_channel`, :242-357 `resolve_compare_render_options` (liest `channel_active_metrics` :315) | Hauptänderungsstelle Resolver |
| src/services/compare_metric_ids.py:251-292 `resolve_channel_enabled_metrics`, :101 `_to_key`, :354 `key_for` | Kanal-Liste ∩ Grundauswahl; Kennung → Vergleichs-Zeilenschlüssel |
| src/services/compare_outlook_metric_ids.py:51 `derived_aggregations`, :248 `_kennungen_aus_renderer_ids`, :285 `resolve_compare_outlook_formats`, :440 `_friendly_outlook_text`, :481 `format_outlook_value` | Muster: Expansion Kennung→Zeilen und einzige bestehende Roh/Einfach-Kette im Vergleich (Ausblick) |
| src/output/renderers/comparison.py:744 `_plain_metric_cell`, :762-785 `_channel_layout_for_metrics`, :788 `render_compare_telegram`, :604 `_CHANNEL_METRICS`, :78-130 `_DAILY_PLAIN_ROWS`/`_PLAIN_ROWS_UNSORTED`, :690 `_sms_gsm7_safe`, :701 `_sms_metric_cell`, :999 `_sms_location_part`, :1090 `render_compare_sms`, :163/179 Klartext | Telegram/SMS/Klartext-Renderer, heute fest formatiert |
| src/output/renderers/email/compare_html.py:267 `fmt_word_cell`, :489 `derive_row_labels`, :751 `_fmt_metric`, :760-810 `_render_overview_row`, :812 `_visible_metrics` | Mail-Übersicht, Zelltönung `sev` unabhängig vom Format |
| src/output/renderers/email/helpers.py:759 `fmt_val`, :1243 `build_friendly_keys`, :1264 `build_format_modes`, :1286 `build_html_indicator_keys` | Trip-Einfachform (Wort/Ampel/Symbol) — wiederverwenden |
| src/app/metric_catalog.py:816 `SMS_FORMAT_MODE_METRIC_IDS`, :1141 `OUTLOOK_FRIENDLY_CAPABLE` | Fähigkeiten je Metrik |
| src/services/scheduler_dispatch_service.py:981-1072, src/services/compare_preview_service.py:72-178 | Konsumenten (Versand, Vorschau; Telegram-Stil „kurzform“ = SMS-Text) |
| src/services/notification_service.py:1642-1651 | Premium-SMS sendet den SMS-Text (folgt automatisch) |
| frontend/src/lib/components/compare/compareEditorSave.ts:139-144 | Altlast #1351: entfernt `channel_layouts` beim Speichern |
| scripts/migrate_1351_drop_compare_channel_layouts.py, tests/test_compare_channel_layouts_migration.py | Altlast #1351: Migration löscht den Key |
| internal/model/compare_preset.go:48, internal/handler/compare_preset.go:315, internal/handler/config_merge.go:11 | Go: `display_config` opaque, Merge eine Ebene tief ⇒ `channel_layouts` als Ganzes ersetzt; keine Go-Änderung nötig |
| docs/reference/api_contract.md §16 (:2677ff, :2825, :2892, :5761-5770) | Vertrag; `channel_active_metrics` undokumentiert |

## Existing Patterns
- Trip: `channel_layouts` → `MetricConfig` je Kanal, Reihenfolge = Listenindex, `enabled:false` rendert nicht, leere Liste bleibt leer; Format per `_resolve_format_mode` (ausdrücklich > `use_friendly_format=False`=raw > Katalog-Standard).
- Trip-SMS: Einfachform nur für Wolkengrößen (`SMS_FORMAT_MODE_METRIC_IDS`), wegen GSM-7.
- Ausblick im Vergleich: `outlook_metric_formats {id: bool}`, Standard hart „Roh“ (models.py:867-875) — Präzedenz für „Standard ohne Angabe = Roh“ im Vergleich.
- Go-Speicherung: Map + `mergeConfigMap`, unvalidiert (ADR-0077-Muster).

## Dependencies
- Upstream: metric_catalog (format_modes, default_format_mode), email/helpers `fmt_val`, compare_metric_catalog `key_for`, channel_layout `render_for_channel`.
- Downstream: scheduler_dispatch_service (Versand), compare_preview_service (Vorschau), notification_service (Premium-SMS), Frontend-Karte #3031.

## Existing Specs
- docs/specs/modules/compare_kanal_metriken.md, feat_1703_s8_compare_kanal_tabs.md, rework_1351_compare_catalog.md (Entfernung channel_layouts), compare_metric_order.md, fix_2422_einstellung_gleich_auslieferung.md, fix_1719_s3_aus_ist_ein_zustand.md
- ADR-0050 (Grundauswahl = Maximum; R4 Aus ist Zustand; R5 Reihenfolge/Roh-Einfach je Kanal), ADR-0049 (Premium-SMS erbt SMS bis S9), ADR-0095 (Kanal-Parität), ADR-0053 (Vergleich: `channel_active_metrics`, Entfernung channel_layouts #1351 — wird durch #3039 teilweise abgelöst ⇒ neues ADR/„Abgelöst durch“ nötig), ADR-0077.

## Risks & Considerations
- **ADR-0053/#1351 wird umgekehrt:** Wiedereinführung von `channel_layouts` im Vergleich ist eine Abweichung ⇒ neues ADR. `compareEditorSave.ts` und Migration 1351 dürfen den Key nicht mehr löschen (sonst löscht jeder Speichervorgang anderer Reiter den Kartenstand). Migration nicht erneut laufen lassen.
- **Vokabular:** `channel_layouts` trägt Katalog-Kennungen, Renderer Vergleichs-Zeilenschlüssel; Expansion (temperature → temp_max/temp_min) muss stabil sein, Format je Zeile über `metric_id`.
- **Standard ohne Angabe:** Vergleichs-Renderer zeigen heute faktisch „Roh“. Katalog-Standard als Default würde alle Bestandsvergleiche umstellen ⇒ Standard muss „wie heute“ sein (Issue-AC: Bestandsvergleich unverändert). Golden-Dateien `tests/golden/vergleichs_mail/*` dürfen sich für Bestand nicht ändern.
- **SMS:** ≤160 GSM-7; Emoji/Symbole schalten auf UCS-2 ⇒ Einfachform in SMS nur wie beim Trip (Wolken) oder GSM-7-sichere Wörter.
- **Telegram:** max. 7 Werte je Ort, 4096 Zeichen; „kurzform“ übernimmt SMS-Text.
- **Mail:** Zelltönung `sev` vs. Ampelpunkt bei Einfach klären; Klartext-Teil muss mitziehen (Paritätstest `test_compare_mail_plaintext_html_label_parity.py`).
- Zwei-Nutzer-Test Pflicht für datenbewegende Pfade (Speichern ist Go, unverändert; Renderer-Tests je Nutzer-Preset).
- Tests: tests/tdd/test_compare_render_options_resolver.py, tests/unit/test_compare_channel_metric_cascade.py, tests/unit/test_compare_channel_metrics_reach_the_renderer.py, tests/tdd/test_compare_einstellung_auslieferung_kette.py, tests/golden/test_vergleichs_mail_golden.py, test_compare_sms_gsm7_charset.py, test_compare_premium_sms_versand.py, test_compare_preview_service.py.

## Analysis

### Type
Feature (Vorlauf zu #3031, Teil von #2795 / Epic #2791)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/report_config_resolver.py (:163 `CompareRenderOptions`, :242-357) | MODIFY | Neues additives Feld je Kanal: geordnete Zeilen (Schlüssel + Format), Kaskade `channel_layouts` → `channel_active_metrics` → Grundauswahl; `enabled_metrics_by_channel` bleibt signaturgleich |
| src/output/renderers/compare_metric_ids.py (:251-292, :101 `_to_key`) | MODIFY | Kennung → Zeilenschlüssel-Expansion (Muster `derived_aggregations`, `compare_outlook_metric_ids.py:51`), Format der Kennung gilt für alle abgeleiteten Zeilen, Schnitt mit Grundauswahl (Pfad-Korrektur: Datei liegt in `src/output/renderers/`, nicht `src/services/`) |
| src/output/renderers/comparison.py (:619 `_fmt_overview_cell`, :744 `_plain_metric_cell`, :1090 `render_compare_sms`) | MODIFY | EINE Formatstelle für Telegram, SMS, Klartext-Mail bekommt Format-Parameter (`None` = heutiger Festzustand) |
| src/output/renderers/email/compare_html.py (:760-810 `_render_overview_row`, :751 `_fmt_metric`) | MODIFY | Format je Zeile; Einfach über `fmt_val`/`build_format_modes` (`email/helpers.py:759/:1264`) wie Trip; Zelltönung `sev` bleibt |
| src/services/scheduler_dispatch_service.py, src/services/compare_preview_service.py | MODIFY (gering) | Neues Feld an Renderer durchreichen (Versand = Vorschau) |
| frontend/src/lib/components/compare/compareEditorSave.ts:139-144 | MODIFY | Löschen von `channel_layouts` beim Speichern entfällt ersatzlos (sonst löscht jeder Speichervorgang den Kartenstand) |
| scripts/migrate_1351_drop_compare_channel_layouts.py, tests/test_compare_channel_layouts_migration.py | DELETE/MODIFY | Migration darf nie wieder laufen (kein Aufrufer außer eigenem Test gefunden) ⇒ entfernen bzw. Test streichen |
| docs/adr/NNNN-vergleich-channel-layouts.md, docs/adr/0053-*.md, docs/adr/README.md | CREATE/MODIFY | Neues ADR, ADR-0053 Teil „Entfernung channel_layouts“ „Abgelöst durch“ |
| docs/reference/api_contract.md §16 | MODIFY | `channel_layouts` (Vergleich) + `channel_active_metrics` dokumentieren |
| tests (Resolver, Kaskade, Renderer je Kanal, Golden, GSM-7, Premium-SMS, Zwei-Nutzer) | CREATE/MODIFY | Ausgabe je Kanal prüfen, nicht nur Nutzlast |

### Scope Assessment
- Files: ~12 Quell-/Doku-Dateien + Tests
- Estimated LoC: Quelle ca. +400/-60, Tests ca. +250
- Risk Level: MEDIUM — gemeinsamer Resolver für Versand und Vorschau; Wächter: Golden-Dateien `tests/golden/vergleichs_mail/*` müssen für Bestand bit-identisch bleiben

### Technical Approach (Tech-Lead-Entscheidungen)
1. **Bestand unverändert (AC hat Vorrang vor Issue-Punkt 2):** Fehlt `channel_layouts`, liefern die Fallback-Stufen nur Auswahl/Reihenfolge; Format = heutiger Festzustand (Renderer-Argument `None`). Der Katalog-Standard greift bei Bestand nie. Issue-Punkt 2 („Format = Katalog-Standard“) wird in der Spec entsprechend präzisiert.
2. **Eintrag ohne `use_friendly_format`:** Roh/Festzustand (Präzedenz `outlook_metric_formats`, fehlt → Roh). Bewusste Abweichung von `loader._resolve_format_mode`; im ADR dokumentieren.
3. **Einfach nur, wenn die Metrik mehr als einen `format_mode` hat** (gleiche Regel wie Spec #3031); sonst wird `use_friendly_format=true` ignoriert.
4. **Kanäle:** Mail Einfach = Ampelpunkt/Wort/Symbol wie Trip (`fmt_val`), Zelltönung bleibt; Klartext-Mailteil zieht dieselbe Zeilenliste samt Format (Paritätstest). Telegram nutzt dieselbe Formatstelle; wo die Metrik keine eigene Einfach-Darstellung hat, bleibt die Zahl. SMS: Einfach nur für `SMS_FORMAT_MODE_METRIC_IDS` (Wolken, GSM-7-sicher), sonst Roh; Premium-SMS folgt ohne eigenen Code.
5. **Aus-Zustand:** `enabled:false` ⇒ Zeile in diesem Kanal nicht gerendert. Teilmengen-Regel ADR-0050: Schnitt mit Grundauswahl; `global_metrics is None` = kein Schnitt; leer bleibt leer (kein Rückfall auf volle Grundauswahl, wie `resolve_channel_enabled_metrics`).
6. **Neue Metriken der Grundauswahl ohne Kanaleintrag:** erscheinen eingeschaltet am Ende (gleich Karten-Spec #3031 AC-8).
7. **Ein Workflow, kein Split:** Telegram, SMS und Klartext-Mail teilen eine einzige Formatstelle; ein Schnitt Mail/Telegram/SMS wäre künstlich und ließe Kanal-Parität (ADR-0095) zwischenzeitlich halb. #3042 bleibt gesperrt bis dieser Workflow live ist.

### Dependencies
- Upstream: metric_catalog (`format_modes`, `SMS_FORMAT_MODE_METRIC_IDS`), email/helpers `fmt_val`/`build_format_modes`, compare_metric_catalog `key_for`, compare_outlook_metric_ids `derived_aggregations`.
- Downstream: scheduler_dispatch_service, compare_preview_service, notification_service (Premium-SMS), Frontend-Karte #3031 (PR #3042).
- Go: keine Änderung (`display_config` opak, Merge ersetzt `channel_layouts` als Ganzes).

### Open Questions
- Keine Produktfrage offen: Die Akzeptanzkriterien des Issues entscheiden die Bestandsregel; Kanal-Darstellungen folgen dem Trip.
