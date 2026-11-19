---
entity_id: feat_3101_ein_vokabular
type: refactor
created: 2026-11-18
updated: 2026-11-18
status: draft
version: "1.0"
workflow: feat-3101-ein-vokabular
tags: [orte, view-model, katalog-ids, epic-3058, issue-3101]
---

# Ein Vokabular für Metrik-Kennungen in Orte-Kanälen

## Approval

- [ ] Approved

## Purpose

Die Orte-Kanallisten des View-Models (`email`, `telegram`, `sms`, `premium_sms`, `layout_channels`) sprechen heute Renderer-Kennungen (`temp_max`), während Ausblick, Stundenverlauf und `rows` Katalog-IDs (`temperature`) nutzen. Diese Spec vereinheitlicht auf Katalog-IDs; die Übersetzung auf Renderer-Kennungen macht ein zentraler Adapter vor dem Renderer. Die zugestellte Ausgabe aller vier Kanäle bleibt Zeichen für Zeichen gleich.

Grundlage: `docs/specs/modules/feat_3122_was_steht_wo.md` Teil A Nr. 2 und Nr. 129, AC-11 (Bytegleichheit Altbestand). Issue #3101, Epic #3058.

## Source

- **File:** `src/services/channel_list_resolver.py`
- **Identifier:** `ChannelRow`, `MailViewModel`, `_compare_view`, `_layout_rows`, `_kanal_rows`, `_orte_standard`, `katalog_id`

> **Schicht:** reine Python-Core-Änderung (`src/services/`, `src/output/renderers/`). Kein Go-, kein Frontend-Code (Frontend liest nur Katalog-Keys/-IDs der Placements-API).
> **Trip/Ortsvergleich-Teilung:** Der Trip-Pfad nutzt bereits Katalog-IDs (`channel_metric_configs`); Orte ziehen nach. Kein neuer UI-Baustein.
> **Mandantentrennung:** reine Funktionen ohne Nutzerdaten-Zugriff; bestehende Zwei-Nutzer-Tests bleiben grün.
> **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS sind alle betroffen und werden bytegleich geprüft.

## Estimated Scope

- **LoC:** produktiv +150..200 / -80; Tests +200..300
- **Files:** ~6 produktiv + ADR/Doku, ~9 Testdateien
- **Effort:** medium (Risiko MEDIUM-HIGH wegen Bytegleichheit)

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/channel_list_resolver.py` | MODIFY | `ChannelRow` um `aggregation` erweitern; `metric_id` = Katalog-ID in allen Orte-Kanallisten; Zwei-Vokabular-Docstring entfällt |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | Helfer (Katalog-ID, Aggregation) zu Renderer-Kennung und zurück, gestützt auf `COMPARE_METRIC_CATALOG` |
| `src/output/renderers/compare_metric_catalog.py` | READ | `COMPARE_METRIC_CATALOG` liefert Katalog-ID + Aggregation je Renderer-Zeile; Reihenfolge bestimmt die Aufweitung (unverändert) |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY (falls nötig) | `_kennungen_aus_renderer_ids` (Rückrichtung) auf denselben zentralen Helfer stützen, keine zweite Abbildung |
| `src/services/report_config_resolver.py` | MODIFY | Ein Adapter an der Grenze `channel_rows` / `enabled_metrics_by_channel`: View-Model-Zeilen zu Renderer-Kennungen |
| `src/services/placements_view_service.py` | MODIFY | Leser von `vm.sms` / `vm.telegram` (B2b-Tabelle) über den Adapter, Ausgabe unverändert |
| `src/services/placements.py` | MODIFY | Alt/Neu-Vergleich auf Katalog-ID normalisieren |
| `docs/adr/0121-*.md`, `docs/adr/README.md` | MODIFY | Neuer Nachtrag löst Nachtrag 2b Nr. 1 ab |
| `docs/reference/api_contract.md` | MODIFY (falls MailViewModel beschrieben) | Vertrag Katalog-ID + Aggregation |
| bestehende Tests (`test_placements_aufloesung.py`, `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_3098_telegram_resolver.py`, `test_3099_sms_resolver.py`, `test_channel_metric_matrix.py`, `test_placements_umrechnung_altbestand.py`, `tests/helpers/kanal_liste_orakel.py`) | MODIFY | Erwartung von Renderer-Kennung auf (Katalog-ID, Aggregation) |
| `tests/tdd/test_3101_ein_vokabular.py` | CREATE | Neue Tests dieser Spec |

Bewusst außerhalb des Scopes: Alarm-Pfad `src/services/compare_alert.py` (liest das View-Model nicht, eigene Abbildung, wird von B1b umgebaut), `compare_briefing_aufbau.py`, `email/helpers.py` (bekommen Renderer-Listen aus `CompareRenderOptions`), Frontend.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `COMPARE_METRIC_CATALOG` | module | Katalog-Key zu Katalog-ID und Aggregation |
| `FRONTEND_TO_RENDERER_METRIC_ID` | map | Zielkennungen des Adapters |
| `_renderer_ids_for_kennung` / `_kennungen_aus_renderer_ids` | functions | Aufweitung und Rückrichtung |
| `CompareRenderOptions` | dataclass | Übergabe der Renderer-Listen an die vier Orte-Renderer |
| `tests/fixtures/einstellung_gleich_mail/` | fixtures | Golden-Mails/TXT als Bytegleichheits-Orakel |
| PR #3140 (B1b) | Reihenfolge | ändert dieselben Resolver-Stellen; wird vor `/50-implement` gemerged, sonst auf dessen Branch stapeln, nie parallel auf `main` |

## Implementation Details

Variante A (Tech-Lead-Entscheidung, siehe `docs/context/feat-3101-ein-vokabular.md`): Jede `ChannelRow` bleibt 1:1 zu einer Renderer-Zeile, trägt aber `metric_id` = Katalog-ID (z. B. `temperature`) und das neue Feld `aggregation` (z. B. `max`). Dadurch bleiben kanal-spezifische Teilauswahl (nur `temp_max` in SMS) und Reihenfolge (`temp_max`, `wind_max`, `temp_min`) erhalten, was eine reine Katalog-ID-Liste nicht leisten kann.

Ein einziger Adapter vor dem Renderer bildet (Katalog-ID, Aggregation) über `COMPARE_METRIC_CATALOG` und `FRONTEND_TO_RENDERER_METRIC_ID` auf Renderer-Kennungen ab. Weitere Verbraucher (B2b-Tabelle, Alt/Neu-Vergleich) gehen über dieselbe Abbildung; `katalog_id()` wird für Orte trivial. Keine Datenmigration, da Renderer-Kennungen nirgends gespeichert sind.

## Expected Behavior

- **Input:** gespeicherte Orte-Konfiguration (unverändert, Katalog-Keys)
- **Output:** View-Model mit Katalog-ID + Aggregation je Zeile; zugestellte Mail, Telegram, SMS, Premium-SMS und die B2b-Tabelle identisch zu heute
- **Side effects:** keine

## Test Plan

### Automated Tests (TDD RED), `tests/tdd/test_3101_ein_vokabular.py`
Echte Resolver-Läufe und echte Renderer-Ausgabe, kein Mock-Theater.

- [ ] GIVEN Orte-Konfiguration mit Temperatur+Wind WHEN View-Model gebaut THEN tragen alle fünf Kanallisten Katalog-IDs plus Aggregation
- [ ] GIVEN SMS nur mit Höchsttemperatur, E-Mail mit Höchst- und Tiefstwert WHEN View-Model gebaut THEN SMS-Liste hat nur `(temperature, max)`, E-Mail beide
- [ ] GIVEN Kanalreihenfolge Höchstwert, Wind, Tiefstwert WHEN gebaut THEN bleibt diese Reihenfolge
- [ ] GIVEN jede Golden-Konfiguration WHEN alle vier Kanäle gerendert THEN Bytegleichheit zu den Golden-Dateien
- [ ] GIVEN Ort mit gespeicherter Tabelle WHEN B2b-Tabelle erzeugt THEN identisch zum Stand vor der Änderung
- [ ] GIVEN Alt- und Neusicht mit Max/Min-Doppelzeilen WHEN verglichen THEN kein Unterschied
- [ ] GIVEN zwei Nutzer mit verschiedenen Konfigurationen WHEN je Nutzer gebaut THEN keine Vermischung
- [ ] GIVEN ADR-Verzeichnis WHEN Index-Drift-Test läuft THEN grün mit neuem Nachtrag

## Acceptance Criteria

- **AC-1:** Given eine Orte-Konfiguration mit Temperatur und Wind in allen vier Kanälen / When das View-Model gebaut wird / Then tragen `email`, `telegram`, `sms`, `premium_sms` und `layout_channels` ausschließlich Katalog-IDs (z. B. `temperature`) samt `aggregation` und keine Renderer-Kennungen wie `temp_max`.
  - Test: Resolver-Lauf über die Fixtures, Prüfung aller fünf Listen auf Katalog-IDs plus Aggregation.

- **AC-2:** Given ein Kanal, der nur den Höchstwert der Temperatur zeigt (z. B. SMS), während die E-Mail Höchst- und Tiefstwert zeigt / When das View-Model gebaut wird / Then enthält die SMS-Liste nur die Zeile Temperatur-Maximum und die E-Mail-Liste beide Zeilen.
  - Test: Konfiguration mit enger Kanalauswahl, Vergleich der Zeilen je Kanal.

- **AC-3:** Given Kanalreihenfolge Höchsttemperatur, Wind, Tiefsttemperatur / When das View-Model gebaut und an den Renderer übergeben wird / Then bleibt genau diese Reihenfolge erhalten, auch nach der Abbildung auf Renderer-Kennungen.
  - Test: Reihenfolge der Zeilen im View-Model und in der gerenderten Ausgabe.

- **AC-4:** Given die Golden-Konfigurationen in `tests/fixtures/einstellung_gleich_mail/` / When Mail, Telegram, SMS und Premium-SMS neu erzeugt werden / Then ist jede zugestellte Ausgabe Zeichen für Zeichen gleich der Golden-Datei, die Golden-Dateien selbst bleiben unverändert.
  - Test: Byte-Vergleich aller vier Kanäle gegen die Golden-Dateien.

- **AC-5:** Given ein Ort mit gespeicherter Tabelle (B2b, `placements_view_service`) / When die Tabellen-Antwort erzeugt wird / Then entspricht sie Zeile für Zeile, inklusive SMS-Beispielwerten und Rest-Zähler, der Antwort vor der Umstellung.
  - Test: Vergleich der Tabellen-Antwort gegen das bisherige Ergebnis der bestehenden B2b-Tests.

- **AC-6:** Given eine Alt- und eine Neusicht derselben Konfiguration mit Höchst- und Tiefstwert / When `placements.py` beide vergleicht / Then gelten sie als gleich, die beiden Temperaturzeilen fallen auf eine Katalog-ID zusammen.
  - Test: Alt/Neu-Vergleich mit Doppelzeilen ergibt keinen Unterschied.

- **AC-7:** Given zwei Nutzer mit unterschiedlichen Orte-Konfigurationen / When für beide das View-Model und die Ausgabe erzeugt werden / Then enthält jede Ausgabe nur die Einstellungen des jeweiligen Nutzers, und die bestehenden Mandantentrennungs-Tests bleiben grün.
  - Test: Zwei-Nutzer-Lauf plus bestehende Tests der angepassten Dateien.

- **AC-8:** Given der neue Nachtrag zu ADR-0121, der Nachtrag 2b Nr. 1 ablöst / When der ADR-Index-Drift-Test läuft / Then ist er grün, und der alte Nachtrag verweist auf „Abgelöst durch" den neuen.
  - Test: `tests/test_adr_index_drift.py` (doc-compliance-test).

- **AC-9:** Given der Stand auf Staging / When `email_spec_validator.py` gegen eine echt zugestellte Orts-Vergleich-Mail im Stalwart-Test-Postfach läuft / Then endet er mit Exit 0 („E2E bestanden"), und der Nachweis liegt in `.claude/e2e_verified/<sha>.json`.
  - Test: Validator gegen echt zugestellte Staging-Mail in `/e2e-verify`, nicht lokal.

## Definition of Done

- AC-1 bis AC-8 durch benannte Tests in der Kern-Schicht grün, Adversary mit Mutations-Gegenprobe ohne offenen Befund, alle sechs CI-Checks grün.
- Golden-Dateien in `tests/fixtures/einstellung_gleich_mail/` unverändert (Bytegleichheit aller vier Kanäle).
- AC-9: `email_spec_validator.py` gegen echt zugestellte Staging-Mail Exit 0, Prod-Selftest Exit 0.
- Mit dem Bau nachgezogen: ADR-0121-Nachtrag samt Index, `docs/reference/api_contract.md` (falls `MailViewModel` dort beschrieben).

## Known Limitations

- Alarm-Pfad `compare_alert.py` behält seine eigene Abbildung (bewusst außerhalb des Scopes).
- Reihenfolge zu PR #3140 (B1b): Bau erst nach dessen Merge oder gestapelt auf dessen Branch.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** neuer Nachtrag zu ADR-0121 (löst Nachtrag 2b Nr. 1 ab)
- **Rationale:** Die Zwei-Vokabular-Lage war dort als bewusst und „gehört zu #3058" festgehalten; mit dieser Spec wird sie aufgehoben, und eine Entscheidung wird nie still rückgängig gemacht.

## Changelog

- 2026-11-18: Initial spec created
