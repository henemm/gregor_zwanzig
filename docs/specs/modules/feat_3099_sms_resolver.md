---
entity_id: feat_3099_sms_resolver
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feat-3099-sms-resolver
tags: [epic-3058, phase-3d, epic-3047, resolver, kanal-liste, sms, pruefkatalog]
---

# SMS (Trip und Orte) liest aus dem Kanal-Listen-Resolver (Phase 3d von #3047)

## Approval

- [ ] Approved

## Purpose

Die Trip-SMS bezieht Metrik-Auswahl, Reihenfolge und Roh/Einfach künftig aus dem gemeinsamen Resolver `resolve_channel_lists(...).sms` (ADR-0121) statt aus dem Altpfad `get_metrics_for_channel("sms", ...)` in `trip_report.py`. Die Orte-SMS liest bereits aus dem Resolver und bekommt nur Nachweis-Fälle. Für den Nutzer bleibt die zugestellte SMS in allen Bestandsfällen Zeichen für Zeichen gleich (ADR-0095); neu ist eine eigene Prüfkatalog-Fallliste für SMS. Amtliche Warnungen bleiben wie heute am Ende der SMS (ADR-0121 Nr. 6).

## Source

- **File:** `src/output/renderers/trip_report.py`, `src/output/renderers/sms_trip.py`
- **Identifier:** `TripReportFormatter` (SMS-Zweig, `sms_metric_ids`, `_sms_position_by_metric`, `_sms_format_by_metric`), neuer Adapter `sms_rows_to_maps`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/output/renderers/`, `src/services/`). Kein Frontend, keine Go-API.
>
> **Trip/Orte-Teilung:** Weiter ein Resolver mit `surface="trip"|"compare"`; kein neues Pendant-Paar (ADR-0097). Der Adapter wird nur vom Trip-Pfad gebraucht, weil Orte `ChannelRow`-Listen schon direkt verarbeiten.
>
> **Mandantentrennung:** SMS-Auswahl und -Folge werden je Nutzer aus dessen Konfiguration abgeleitet; ein Zwei-Nutzer-Test (AC-8) belegt, dass keine Auswahl in die SMS eines anderen Nutzers wandert. `user_id` kommt aus dem Auth-Kontext, kein Fallback auf `"default"`.
>
> **Kanäle:** Betroffen ist die SMS (und über ihren Text Premium-SMS und die Orte-Telegram-Kurzform). E-Mail (#3096) und Telegram (#3098) bleiben unverändert. ADR-0095: alle vier Kanäle gleichrangig, kein Inhalt geht verloren.

## Scope

Phase 3d von #3047 (Epic #3058).

In Scope:
- Trip-SMS: Zeilen einmal aus dem Resolver (UNKOLLABIERTER Display-Config), kleiner Adapter, Altpfad nicht mehr gelesen.
- Orte-SMS: kein Code, nur Nachweis-Fälle.
- Eigene Fallliste `fallliste_sms.json` samt Registrierung im Wächter.
- Doku `docs/reference/sms_format.md` §2 präzisieren.

Nicht in Scope:
- Premium-SMS-eigener Resolver-Zweig `premium_sms` (bewusste Nicht-Änderung, siehe Implementation Details).
- Neuformulierung der Fälle im Format des Neuschnitts (#3122/ADR-0124; PO-Auflage 17.11.: Fälle bleiben vorerst im heutigen Format `channel_layouts.sms`).
- Abbau der Altquelle `channel_active_metrics` (#3102).
- Jede sichtbare Änderung der zugestellten SMS und der SMS-Schwelle.

## Estimated Scope

- **LoC:** Code ca. +30/-20, Tests ca. +200, Fixture-JSON ca. +150, Doku ca. +15
- **Files:** 2 Code, 3 Test/Fixture, 2 Doku (inkl. Spec)
- **Effort:** low bis medium (Risiko LOW: `get_metrics_for_channel` delegiert bereits an `trip_channel_metrics`, Menge und Folge sind identisch; bewacht durch Golden)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_channel_lists`, `ChannelRow` (`src/services/channel_list_resolver.py`) | module | Einzige Quelle der SMS-Zeilen (`.sms`); bleibt unverändert |
| `trip_channel_metrics`, `get_metrics_for_channel` (`src/app/models.py`) | function | Kaskade hinter dem Trip-Resolver; Altpfad wird für SMS nicht mehr gelesen |
| `SMS_FORMAT_MODE_METRIC_IDS`, `SMS_SYMBOL_BY_METRIC`, `SMS_MULTI_SYMBOLS_BY_METRIC` (`src/app/metric_catalog.py`) | const | Roh/Einfach nur für die vier Format-Metriken; Symbole nach Metrik-ID |
| `_resolve_format_mode` (`src/app/loader.py`) | function | Format-Auflösung je Metrik, fängt unbekannte IDs |
| `build_extended_metric_specs`, `format_sms` (`sms_trip.py`) | function | Bauen die SMS-Specs (inkl. deaktivierter Specs #944) |
| `_official_alerts` (`src/output/tokens/builder.py`) | function | Warnblock am Ende, danach nur `X?`/Feuer/Wintersport |
| `render_compare_sms`, `resolve_compare_render_options` (`comparison.py`, `report_config_resolver.py`) | function | Orte-SMS, bereits resolver-basiert |
| `premium_sms.py` | module | Premium-SMS sendet `report.sms_text` (Limit 153) |
| Golden `tests/golden/test_sms_golden.py`, `tests/golden/vergleichs_mail/telegram_sms.*` | tests | Messlatte, bleibt byte-gleich |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | tests | Wächter: `TEILDATEIEN`, `PY_TEST_GLOBS`, Pflichtfelder |
| ADR-0121 (Nr. 6), ADR-0095, ADR-0097, ADR-0049 | ADR | Entscheidungsgrundlage |

## Implementation Details

Reihenfolge: Spec, Fälle und RED-Tests, Adapter und Austausch, Goldens prüfen, Wächter und Doku.

1. **Quelle (Trip):** `_channel_view = resolve_channel_lists(_dc_uncollapsed, "trip", report_type)` liegt in `trip_report.py` schon vor (Muster #3096/#3098); `.sms` wird jetzt gelesen. Der Altpfad `_dc_uncollapsed.get_metrics_for_channel("sms", report_type)` wird dort nicht mehr gelesen; er war der einzige Leser in `src/`.
2. **Adapter `sms_rows_to_maps(rows)`** (in `sms_trip.py`, isoliert testbar) liefert `(ids, position_by_metric, format_by_metric)`:
   - `ids` = Menge der `metric_id` aller `enabled`-Zeilen;
   - `position_by_metric` = `{metric_id: Index in der Resolver-Folge}`;
   - `format_by_metric` nur für `SMS_FORMAT_MODE_METRIC_IDS`, über `_resolve_format_mode`. `format=None` heißt Katalog-Standard (alle vier Format-Metriken haben `("raw","symbol")`, Standard `symbol`), NICHT Roh; `format="raw"` bleibt Roh. Unbekannte IDs bleiben wirkungslos.
3. **Abgewählte Metriken (#944):** Die deaktivierten Specs entstehen unverändert über `enabled = metric_id in ids`; abgewählte Metriken behalten ihre SMS-Symbole als deaktivierte Specs.
4. **Warnblock hinten:** Amtliche Warnungen sind keine Zeile der Liste und nicht abwählbar. Sie stehen weiter am Ende (Warnblock in `builder.py`, danach nur `X?`/Feuer/Wintersport) und wandern durch Umsortieren der Liste nicht. ADR-0121 Nr. 6.
5. **Premium-SMS (bewusste Nicht-Änderung):** Premium sendet `report.sms_text`, ist also textgleich zur SMS, nur das Limit unterscheidet sich (153 statt 160). Der Resolver-Zweig `premium_sms` (Kopie von `sms`) wird in `src/` nicht gelesen und bewusst auch jetzt nicht angebunden; eine eigene Premium-Liste wäre ein eigener Produktentscheid.
6. **Schwelle:** Einzige wirksame SMS-Schwelle bleibt `trip.alert_channel_thresholds["sms"]` (`sms_alert_min_level`); unverändert. Ein `sms_threshold` je Metrik wirkt nicht (#2792 E1).
7. **Orte:** `resolve_compare_render_options` füllt `enabled_metrics_by_channel["sms"]` aus `view.sms` und `metric_formats("sms")`; Versand und Vorschau nutzen das bereits. Kein Code, nur Fälle.
8. **Fallliste:** `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json` (Trip und Orte) im heutigen Format `channel_layouts.sms`, NEUE IDs (Präfix `sms-`), global eindeutig; bestehende SMS-Fälle (`trip-r7-sms-*`, `R7-KAT-trip-sms-*`, `R7-KAT-trip-premium-gleich-sms-kuerzung`, Orte `O…`/`R…`, `E-R8-T1-SMS-LADEN-*`) bleiben in ihren Dateien. Wächter: `TEILDATEIEN` + `"sms"`, `PY_TEST_GLOBS` + `test_3099_*.py`. Achsen: Trip/Orte × Roh/Einfach × Katalog- vs. Ziehfolge × Kanal-Ebene nie/leer/gesetzt × abgewählte Metriken × Kürzung 160/153 × Warnung vorhanden.
9. **Doku:** `docs/reference/sms_format.md` §2 „Token-Reihenfolge (fix)" wird zu „Standardreihenfolge; wirksam ist die Resolver-Folge, fix am Ende nur Warnblock/`X?`/DBG"; Quelle in §3.4e `resolve_channel_lists(...).sms`; Eintrag in §12 Changelog.

## Expected Behavior

- **Input:** `display_config` eines Trips oder Orts-Vergleichs, `report_type`, Sprache.
- **Output:** SMS (Trip morning/evening, Orte) und Premium-SMS Zeichen für Zeichen gleich dem Stand vor der Änderung in allen Bestandsfällen, inkl. Kürzung auf höchstens 160 (Premium 153) Zeichen; Auswahl, Folge und Roh/Einfach stammen aus der Resolver-SMS-Liste.
- **Side effects:** keine; der Resolver ist rein lesend.

## Acceptance Criteria

- **AC-1:** Given Trip-Konfigurationen aus den SMS-Golden-Fixtures und allen bestehenden SMS-Fällen des Prüfkatalogs / When die SMS nach der Umstellung gerendert wird / Then ist sie Zeichen für Zeichen gleich der bisherigen SMS (Golden unverändert) und bleibt höchstens 160 Zeichen lang, bei Premium-SMS höchstens 153.
  - Test: `tests/golden/test_sms_golden.py`, `test_ac6_sms_byte_identity_without_wc.py`, `test_3047_r7_kanaele_trip.py`, `test_3047_runde7_orte_sms_kuerzung.py`, `test_compare_premium_sms_versand.py` einzeln; Golden-Dateien unverändert.

- **AC-2:** Given ein Trip mit eigener SMS-Auswahl in anderer Folge als die Grundauswahl / When die SMS für Morgen- und Abendbericht erzeugt wird / Then enthält die SMS genau die aktiven SMS-Metriken in der gewählten Folge.
  - Test: Rendern über `TripReportFormatter`, Soll-Folge aus `resolve_channel_lists(...).sms`; Token-Reihenfolge in `sms_text` geprüft, Fälle morning und evening.

- **AC-3:** Given ein Trip mit SMS-Metriken in den Formaten Roh, Einfach und ohne Format-Angabe / When die SMS erzeugt wird / Then zeigt Roh den Rohwert, Einfach die einfache Darstellung, und ohne Angabe bleibt die Katalog-Darstellung (nicht als Roh gedeutet).
  - Test: Drei Konfigurationen mit den vier Format-Metriken, Tokens in der echten SMS gegen Soll; Adapter-Test: `format=None` ergibt Katalog-Standard, `format="raw"` ergibt Roh.

- **AC-4:** Given ein Trip, in dem der Nutzer Metriken für die SMS abgewählt hat / When die SMS erzeugt wird / Then erscheinen die abgewählten Metriken nicht als Wert in der SMS, ihre SMS-Symbole bleiben aber als deaktivierte Angaben erhalten (#944) und ändern keine aktiven Tokens.
  - Test: `test_issue_944_disabled_metrics_sms.py` einzeln grün; neuer Fall mit abgewählter Metrik, Adapter liefert sie nicht in `ids`.

- **AC-5:** Given ein Trip mit amtlicher Warnung und einer SMS-Liste in beliebiger, auch umsortierter Folge / When die SMS erzeugt wird / Then steht der Warnblock immer am Ende, vor `X?`/Feuer/Wintersport wie bisher, ist keine Zeile der Liste und lässt sich weder abwählen noch durch Umsortieren verschieben.
  - Test: Zwei Folgen derselben Auswahl, Position des Warnblocks in der echten SMS gleich; `test_official_alert_sms_marker.py` einzeln grün.

- **AC-6:** Given ein Trip mit Premium-SMS als Kanal / When das Briefing versendet wird / Then ist der Premium-SMS-Text gleich dem SMS-Text (nur mit Limit 153), und der Resolver-Zweig `premium_sms` ändert den Inhalt nicht.
  - Test: Trip mit abweichender `premium_sms`-Konfiguration, gesendeter Premium-Text gleich `sms_text`; `test_compare_premium_sms_versand.py` einzeln grün.

- **AC-7:** Given ein Orts-Vergleich mit SMS-Auswahl in eigener Folge, mit Roh und Einfach / When die Orte-SMS erzeugt wird (Versand und Vorschau) / Then stimmen Auswahl, Folge und Darstellung mit der SMS-Auswahl überein, und die Telegram-Kurzform bleibt gleich dem SMS-Text.
  - Test: Fälle `sms-orte-*` über `render_compare_sms` aus `resolve_compare_render_options`; `test_compare_sms_kuerzel.py`, `test_compare_sms_official_alerts.py`, `test_telegram_kurzform_ignoriert_telegram_auswahl.py` einzeln grün.

- **AC-8:** Given zwei verschiedene Nutzer mit unterschiedlicher SMS-Auswahl und unterschiedlicher Reihenfolge / When für beide hintereinander Trip- und Orte-SMS erzeugt werden / Then enthält jede SMS ausschließlich die Auswahl und Folge des eigenen Nutzers, unabhängig von der Aufrufreihenfolge.
  - Test: Zwei `display_config`s im selben Prozess, beide Aufrufreihenfolgen, Tokens je Nutzer; kein Fallback auf `"default"`.

- **AC-9:** Given der Code nach der Umstellung / When die Trip-SMS gerendert wird / Then wird der Altpfad `get_metrics_for_channel("sms")` nicht mehr gelesen, und weichen Altpfad und Resolver-Liste voneinander ab, folgt die SMS der Resolver-Liste.
  - Test: Unterklasse der Display-Config überschreibt `get_metrics_for_channel("sms")` abweichend; die SMS bleibt unverändert (rot vor der Umstellung); Verhaltenstest an der SMS, kein Dateiinhalt-Check.

- **AC-10:** Given ein Trip mit gesetzter SMS-Schwelle `alert_channel_thresholds["sms"]` und abweichendem `sms_threshold` einer Metrik / When die SMS erzeugt wird / Then wirkt allein die Kanal-Schwelle der SMS, wie vor der Änderung.
  - Test: Zwei Konfigurationen mit unterschiedlicher Kanal-Schwelle und gleichem Metrik-`sms_threshold`; Ausgabe gleich dem Stand vor der Umstellung.

- **AC-11:** Given die neue Fallliste `fallliste_sms.json` im heutigen Format `channel_layouts.sms` / When der Wächter `test_einstellung_gleich_mail_fallliste.py` läuft / Then ist die Datei registriert, alle Pflichtfelder sind gefüllt, die IDs sind global eindeutig, und die Kanal-Abdeckung ist nicht kleiner als vorher.
  - Test: `test_einstellung_gleich_mail_fallliste.py` einzeln inklusive Selbsttests der Fehlerzahl; `test_3099_*` wird über `PY_TEST_GLOBS` mitgezählt.

- **AC-12:** Given Trip-Konfigurationen mit E-Mail- und Telegram-Auswahl / When das Briefing gerendert wird / Then bleiben E-Mail und Telegram inhaltsgleich zum Stand vor der Änderung.
  - Test: `test_channel_metric_matrix.py`, `tests/golden/test_telegram_briefing_golden.py` und E-Mail-Golden einzeln unverändert grün.

## Definition of Done

- AC-1 bis AC-12 durch benannte Tests grün; SMS-Golden und Prüfkatalog einzeln grün, Golden-Dateien unverändert.
- Mutations-Gegenprobe durch den Adversary (siehe Test Plan).
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks grün, Staging-Verifikation mit echt zugestellter SMS-Ausgabe (Trip und Orte) unverändert, Prod-Selftest bestanden.

## Test Plan

### Automated Tests (TDD RED)

Zusicherungen am Ergebnis der SMS-Ausgabe, kein Mock-Theater (kein `Mock()`/`patch()`).

- [ ] Neu `tests/tdd/test_3099_sms_resolver.py`: GIVEN Trip mit abweichender SMS-Folge WHEN SMS morning/evening THEN Folge und Menge gleich Resolver `.sms` (AC-2).
- [ ] Neu: GIVEN Formate Roh/Einfach/ohne Angabe WHEN SMS THEN je erwartete Tokens; Adapter `sms_rows_to_maps` isoliert getestet, `format=None` nicht Roh (AC-3).
- [ ] Neu: GIVEN abgewählte Metrik WHEN SMS THEN kein Wert, deaktivierte Spec erhalten (AC-4).
- [ ] Neu: GIVEN Warnung und zwei Listenfolgen WHEN SMS THEN Warnblock gleiche Position am Ende (AC-5).
- [ ] Neu: GIVEN Premium-SMS WHEN Versand THEN Text gleich SMS-Text (AC-6).
- [ ] Neu: GIVEN Orte-SMS Folge/Format WHEN Versand und Vorschau THEN gleich und passend (AC-7).
- [ ] Neu: GIVEN zwei Nutzer WHEN beide Aufrufreihenfolgen THEN je eigene SMS (AC-8).
- [ ] Neu: Unterklasse überschreibt `get_metrics_for_channel("sms")` abweichend, SMS unverändert (AC-9); rot vor der Umstellung.
- [ ] Neu: Kanal-Schwelle gegen Metrik-`sms_threshold` (AC-10).
- [ ] Neu: `fallliste_sms.json` und Wächter-Anpassung `TEILDATEIEN`/`PY_TEST_GLOBS` (AC-11).
- [ ] Unverändert grün (Regression, einzeln benannt): `tests/golden/test_sms_golden.py`, `test_issue_944_disabled_metrics_sms.py`, `test_compare_sms_official_alerts.py`, `test_compare_sms_kuerzel.py`, `test_3047_runde7_orte_sms_kuerzung.py`, `test_official_alert_sms_marker.py`, `test_ac6_sms_byte_identity_without_wc.py`, `test_compare_premium_sms_versand.py`, `test_telegram_kurzform_ignoriert_telegram_auswahl.py`, `test_3047_r7_kanaele_trip.py`, `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_3098_telegram_resolver.py`.
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): Adapter ohne `enabled`-Filter; Adapter vertauscht Folge; `format=None` als Roh gedeutet; Format für Nicht-Format-Metriken gesetzt; Resolver auf kollabiertem statt unkollabiertem `dc`; Warnblock folgt der Listenfolge; `#944`-Specs entfallen. Jede Verfälschung muss mindestens einen Test an der SMS-Ausgabe rot machen.
- Live-E2E: echt zugestellte SMS-Ausgabe auf Staging (Trip und Orte), Ergebnis unverändert.

## Affected Files

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `src/output/renderers/trip_report.py` | MODIFY | `sms_metric_ids`, Positionen, Formate aus `_channel_view.sms`; Altpfad nicht mehr gelesen; Kommentare kürzen |
| `src/output/renderers/sms_trip.py` | MODIFY | Adapter `sms_rows_to_maps` |
| Orte (`report_config_resolver.py`, `comparison.py`, `scheduler_dispatch_service.py`, `compare_preview_service.py`) | keine Änderung | bereits resolver-basiert |
| `tests/fixtures/einstellung_gleich_mail/fallliste_sms.json` | CREATE | SMS-Fallliste (Trip + Orte), neue IDs |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN` + `"sms"`, `PY_TEST_GLOBS` + `test_3099_*` |
| `tests/tdd/test_3099_sms_resolver.py` | CREATE | Verhaltensnachweise Trip und Orte, Altpfad, Zwei-Nutzer |
| `docs/reference/sms_format.md` | MODIFY | §2 Reihenfolge präzisieren, §3.4e Quelle, §12 Changelog |
| `docs/specs/modules/feat_3099_sms_resolver.md` | CREATE | diese Spec |

## Known Limitations

- Fälle stehen im heutigen Format `channel_layouts.sms`; sie werden beim Neuschnitt (#3122/ADR-0124) umformuliert (PO-Auflage 17.11.).
- Premium-SMS hat keine eigene Inhaltsliste; der Zweig `premium_sms` des Resolvers bleibt ungelesen.
- Orte-Fallback ohne `channel_layouts` (`channel_active_metrics`) bleibt bis #3102.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121 (kein neues ADR, kein Nachtrag nötig)
- **Rationale:** Setzt die Adapter-Vorgabe des ADR-0121 für SMS um, analog #3096 und #3098; Nr. 6 (Warnungen bei SMS/Premium-SMS hinten, keine Zeile der Liste, nicht abwählbar) bleibt erfüllt. ADR-0095 (Kanal-Parität) bleibt erfüllt, weil die zugestellte SMS gleich bleibt.

## Changelog

- 2026-11-17: Initial spec created (Phase 3d, Issue #3099, Epic #3058)
