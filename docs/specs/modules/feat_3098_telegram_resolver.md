---
entity_id: feat_3098_telegram_resolver
type: refactor
created: 2026-11-17
updated: 2026-11-17
status: draft
version: "1.0"
workflow: feature-3098-telegram-resolver
tags: [epic-3058, phase-3c, epic-3047, resolver, kanal-liste, telegram, pruefkatalog]
---

# Telegram (Trip und Orte) liest aus dem Kanal-Listen-Resolver (Phase 3c von #3047)

## Approval

- [ ] Approved

## Purpose

Die Telegram-Nachricht eines Trips bezieht Metriken, Reihenfolge und Roh/Einfach künftig aus dem gemeinsamen Resolver `resolve_channel_lists` (ADR-0121) statt aus dem eigenen Altpfad `get_metrics_for_channel("telegram", ...)` in `trip_report.py`. Die Orte-Telegram-Nachricht liest bereits aus dem Resolver; sie bekommt nur Nachweis-Fälle. Für den Nutzer bleibt die zugestellte Telegram-Nachricht in allen Bestandsfällen unverändert (ADR-0095); neu ist eine eigene Prüfkatalog-Fallliste für Telegram. Die offenen Telegram-Funde aus #3063 (Kopf-Typ, Windrichtung Roh) sind im Code bereits behoben und werden hier an der echten Telegram-Ausgabe im neuen Pfad nachgewiesen und mit geschlossen.

## Source

- **File:** `src/output/renderers/trip_report.py`, `src/output/renderers/email/helpers.py`
- **Identifier:** `TripReportFormatter` (Telegram-Zweig, `_dc_telegram`), neuer Adapter `telegram_metric_configs`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/output/renderers/`, `src/services/`). Kein Frontend, keine Go-API. Der Editor (Frontend) bleibt unberührt.
>
> **Trip/Orte-Teilung:** Weiter ein Resolver mit `surface="trip"|"compare"`; keine neue Regel im Renderer, kein Pendant-Paar (ADR-0097). Der Adapter wird nur vom Trip-Pfad gebraucht, weil Orte schon `ChannelRow`-Listen direkt verarbeitet.
>
> **Mandantentrennung:** Die Änderung bewegt keine neuen Nutzerdaten, aber Telegram-Folge und -Format werden je Nutzer aus dessen Konfiguration abgeleitet; ein Zwei-Nutzer-Test (AC-7) belegt, dass keine Auswahl in die Nachricht eines anderen Nutzers wandert. `user_id` kommt aus dem Auth-Kontext, kein Fallback auf `"default"`.
>
> **Kanäle:** Betroffen ist nur Telegram. E-Mail bleibt (Phase 3a, #3096), SMS und Premium-SMS bleiben unverändert (#3099, #3100). Die Telegram-Kurzform (= SMS-Text) folgt der SMS-Auswahl und gehört zu #3099 (ADR-0095: alle vier Kanäle gleichrangig, kein Inhalt geht verloren).

## Scope

Phase 3c von #3047 (Epic #3058).

In Scope:
- Trip-Telegram: Zeilen einmal aus dem Resolver, Altpfad gelöscht, Adapter Zeile nach `MetricConfig`.
- Orte-Telegram: kein Code, nur Nachweis-Fälle.
- Eigene Fallliste `fallliste_telegram.json` im Prüfkatalog samt Registrierung im Wächter.
- Nachweis #3063 im neuen Pfad.

Nicht in Scope:
- Telegram-Kurzform = SMS-Text (#3099).
- Abbau der Altquelle `channel_active_metrics` samt Orte-Fallback ohne `channel_layouts` (#3102; erledigt, #3102: #3277, #3351).
- Vereinheitlichung des Format-Standards ohne Angabe (Trip: Katalog, Orte: Roh; Entscheidung #3096, bleibt).
- Jede sichtbare Änderung der zugestellten Telegram-Nachricht.

## Estimated Scope

- **LoC:** Code ca. +50/-10, Tests ca. +200, Fixture-JSON ca. +200
- **Files:** 2 Code, 3 Test/Fixture, 1 Spec
- **Effort:** medium (Risiko MEDIUM: zugestellte Telegram-Nachricht, bewacht durch Golden `tests/golden/telegram_briefing/` und Prüfkatalog)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_channel_lists`, `MailViewModel`, `ChannelRow` (`src/services/channel_list_resolver.py`) | module | Einzige Quelle der Telegram-Zeilen (`.telegram`); bleibt unverändert |
| `trip_channel_metrics`, `get_metrics_for_channel` (`src/app/models.py`) | function | ADR-0050-Kaskade hinter dem Trip-Resolver; Kollabierung in `trip_report.py` bleibt für SMS/Premium-SMS |
| `get_metric(...)` (`app/metric_catalog.py`) | function | Adapter: Katalog-Spalte/Existenzprüfung unbekannter IDs |
| `build_friendly_keys`, `build_format_modes`, `should_merge_wind_dir` (`email/helpers.py`) | function | brauchen `MetricConfig`, daher Adapter statt reiner Spaltenliste |
| `render_telegram_bubbles`, `render_for_channel` (`narrow.py`, `channel_layout.py`) | function | Telegram-Rendering; liest `dc` an mehreren Stellen (Tabelle, Kurzübersicht, Fußzeile, Windrichtung-Merge) |
| `briefing_typ` (`renderers/briefing_typ.py`) | function | Kopf-Typ (#3063 P1) |
| `resolve_compare_render_options`, `render_compare_telegram` (`report_config_resolver.py`, `comparison.py`) | function | Orte-Telegram, bereits resolver-basiert |
| Golden `tests/golden/telegram_briefing/briefing_normalstil.{de,en}.txt` | tests | Messlatte, bleibt byte-gleich |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | tests | Wächter: `TEILDATEIEN`, Pflichtfelder, `pruefe_kanal_abdeckung` |
| ADR-0121, ADR-0095, ADR-0097, ADR-0050 | ADR | Entscheidungsgrundlage |

## Implementation Details

Reihenfolge: RED, Adapter, Umstellung, Golden/Prüfkatalog grün, Fallliste und Wächter, #3063 schließen.

1. **Quelle (Trip):** In `trip_report.py` neben `_email_rows` (Muster #3096) einmal `resolve_channel_lists(_dc_uncollapsed, "trip", report_type).telegram` auf dem UNKOLLABIERTEN `dc` ziehen. Menge und Folge ändern sich nicht (gleiche Kaskade `trip_channel_metrics`), nur die Quelle. Der Altpfad `_dc_uncollapsed.get_metrics_for_channel("telegram", ...)` wird gelöscht; zugehörige Kommentare werden angepasst.
2. **Adapter `telegram_metric_configs(rows, dc)`** (in `email/helpers.py`): Zeilen nach `MetricConfig`-Liste, weil `narrow.py`, `build_friendly_keys` und `build_format_modes` `MetricConfig` brauchen. Regeln:
   - nur `enabled`-Zeilen; unbekannte `metric_id` überspringen; `enabled=True` erzwingen;
   - `bucket`, `order` und `sms_threshold` stammen aus dem Quell-`MetricConfig` der Grundauswahl (`ChannelRow` trägt sie nicht); die Reihenfolge nach `bucket`/`order` in `render_for_channel` muss der Resolver-Folge entsprechen (per Test gesichert); Schwellen-Fallback wie `_globale_schwelle`;
   - Format zurückschreiben (Umkehr von `_trip_format`): `None` = Katalog-Standard, MetricConfig unverändert (nicht als Roh deuten); `raw` leitet `format_mode="raw"` und `use_friendly_format=False` ab; jedes andere Format setzt `format_mode=<format>`.
3. **Eine Liste für alle Lesestellen:** `_dc_telegram` entsteht ausschließlich aus dem Adapter. Alle `dc`-Lesestellen in `narrow.py` (Tabelle über `render_for_channel`, Kurzübersicht über `get_enabled_metric_ids`, Fußzeile, Windrichtung-Merge über `should_merge_wind_dir`) bleiben im Verhalten unverändert und lesen dieselbe Liste (Adversary F004 aus #1719). `narrow.py` selbst wird nicht umgebaut.
4. **Orte:** `resolve_compare_render_options` füllt `enabled_metrics_by_channel["telegram"]` aus `view.telegram` und `metric_formats("telegram")`; Versand und Vorschau nutzen das bereits. Kein Code, nur Fälle. Fallback ohne `channel_layouts` bleibt bis #3102 (erledigt, #3102: #3277, #3351).
5. **Fallliste:** neue Datei `tests/fixtures/einstellung_gleich_mail/fallliste_telegram.json` mit NEUEN IDs (Präfix `telegram-`); bestehende Telegram-Fälle (`trip-r7-telegram-*`, `R7-KAT-trip-telegram-*`, `T-P9-TG-*`, `O-R7-TG-*`, `O-P9-TG-*`) bleiben in `fallliste_trip`/`fallliste_orte` (IDs global eindeutig, andere Tests referenzieren sie). Eintrag `"telegram"` in `TEILDATEIEN` des Wächters, `_syn_daten()` und die Fehlerzahl-Selbsttests entsprechend angepasst, `PY_TEST_GLOBS` um `test_3098_*.py` erweitert. Achsen: Trip/Orte × DE/EN × Roh/Einfach (inkl. Windrichtung-Merge) × Katalog- vs. Ziehfolge × Kanal-Ebene nie/leer/gesetzt × morning/evening; Kopf `briefing_typ`. `pruefe_kanal_abdeckung` darf nicht sinken.
6. **#3063:** Fälle `telegram-kopf-typ-*` und `telegram-windrichtung-roh-*` im neuen Pfad; nach Auslieferung wird #3063 mit geschlossen.

### Designentscheidung: Format-Standard ohne Angabe bleibt

Ohne Format-Angabe nutzt Trip Katalog-Darstellung (aus `MetricConfig`), Orte Roh. Bleibt bewusst (Entscheidung #3096): eine Vereinheitlichung würde die Golden-Nachricht ändern und ist eine Produktentscheidung mit sichtbarer Wirkung. Falls gewünscht eigenes Folge-Issue.

### Umsetzungsabweichungen

- **Format `None` = Katalog-Standard:** Der Adapter `telegram_metric_configs` lässt den Quell-Eintrag der Grundauswahl unverändert, wenn er schon den Katalog-Standard zeigt; sonst wird er auf den Katalog-Standard zurückgesetzt (`format_mode=None`, `use_friendly_format=True`). Ein Roh der Grundauswahl wird also nicht geerbt; das entspricht dem Altverhalten (die Telegram-Ebene trug ihren eigenen Eintrag ohne Format).
- **`order` = Resolver-Index:** `bucket` und `sms_threshold` kommen aus der Grundauswahl, `order` aber aus der Position in der Resolver-Telegram-Liste, damit die Sortierung in `render_for_channel` der Resolver-Folge entspricht.

## Expected Behavior

- **Input:** `display_config` eines Trips oder Orts-Vergleichs, `report_type`, Sprache.
- **Output:** Telegram-Nachricht (Trip morning/evening, Orte) Zeichen für Zeichen gleich dem Stand vor der Änderung in allen Bestandsfällen; Spalten, Folge und Roh/Einfach stammen aus der Resolver-Telegram-Liste.
- **Side effects:** keine; Resolver ist rein lesend, Eingabe wird nicht verändert.

## Acceptance Criteria

- **AC-1:** Given Trip-Konfigurationen aus den Golden-Fixtures und allen bestehenden Telegram-Fällen des Prüfkatalogs / When die Telegram-Nachricht nach der Umstellung gerendert und zugestellt wird / Then ist sie Zeichen für Zeichen gleich der bisherigen Nachricht (Golden unverändert), und die bestehenden Telegram-Fälle laufen unverändert grün.
  - Test: `tests/golden/test_telegram_briefing_golden.py`, `test_3047_r7_kanaele_trip.py`, `test_3047_runde7_telegram_tagesfenster.py`, `test_telegram_briefing_zweisprachig.py` einzeln; Golden-Dateien unverändert; Staging-Prüfung gegen echt zugestellte Telegram-Nachricht.

- **AC-2:** Given ein Trip mit eigener Telegram-Auswahl in anderer Folge als die Grundauswahl und mit abgewählten Metriken / When die Telegram-Nachricht für Morgen- und Abendbericht erzeugt wird / Then enthält die Tabelle genau die aktiven Telegram-Metriken in der gewählten Folge, und die Kurzübersicht und die Windrichtung-Zusammenfassung richten sich nach derselben Liste.
  - Test: Rendern über `render_telegram_bubbles` aus `TripReportFormatter` mit Soll-Folge aus Resolver `.telegram`; Spaltenköpfe, Kurzübersicht und Windrichtung-Zeile im Ergebnis; Fälle morning und evening.

- **AC-3:** Given ein Trip mit Telegram-Metriken in den Formaten Roh, Einfach und ohne Format-Angabe / When die Telegram-Nachricht erzeugt wird / Then zeigt Roh den Rohwert, Einfach die einfache Darstellung, und ohne Angabe bleibt die Katalog-Darstellung unverändert (nicht als Roh gedeutet).
  - Test: Drei Konfigurationen, Zellwerte in der echten Telegram-Ausgabe verglichen mit Soll aus der Katalog-/Roh-/Einfach-Darstellung; Adapter-Test: `format=None` verändert das `MetricConfig` nicht.

- **AC-4:** Given ein Trip mit Windrichtung als Roh und derselbe Trip mit Einfach, jeweils in Deutsch und Englisch, in Morgen- und Abendbericht / When die Telegram-Nachricht erzeugt wird / Then zeigt Roh die Windrichtung als eigene Angabe und Einfach die zusammengefasste Darstellung, und der Kopf nennt den Berichtstyp in der Sprache des Nutzers.
  - Test: Fälle `telegram-windrichtung-roh-{de,en}`, `telegram-windrichtung-einfach-{de,en}`, `telegram-kopf-typ-{de,en}` über die echte Telegram-Ausgabe; schließt #3063 (Kopf-Typ, Windrichtung Roh) im neuen Pfad.

- **AC-5:** Given ein Trip mit Telegram-Kanal-Ebene „nie gesetzt", „leer" und „gesetzt" / When die Telegram-Nachricht erzeugt wird / Then folgt sie ohne Kanal-Ebene der Grundauswahl, bei leerer Ebene keiner Metrik-Tabelle und bei gesetzter Ebene genau dieser Auswahl.
  - Test: Drei Konfigurationen, Ergebnis der echten Telegram-Ausgabe gegen die Soll-Folge aus der ADR-0050-Kaskade.

- **AC-6:** Given ein Orts-Vergleich mit Telegram-Auswahl in eigener Folge, mit Roh und Einfach, in Deutsch und Englisch / When die Telegram-Nachricht des Orte-Vergleichs erzeugt wird (Versand und Vorschau) / Then stimmen Spalten, Folge und Darstellung mit der Telegram-Auswahl überein, und ohne Format-Angabe bleibt Roh.
  - Test: Fälle `telegram-orte-*` über `render_compare_telegram` aus `resolve_compare_render_options`; Vorschau und Versand derselben Konfiguration verglichen.

- **AC-7:** Given zwei verschiedene Nutzer mit unterschiedlicher Telegram-Folge und unterschiedlichem Format / When für beide hintereinander Trip- und Orte-Telegram-Nachrichten erzeugt werden / Then enthält jede Nachricht ausschließlich die Auswahl des eigenen Nutzers, unabhängig von der Aufrufreihenfolge.
  - Test: Zwei `display_config`s im selben Prozess (Orte: `orte_ac12_nutzer1/2.json` wiederverwendet), beide Aufrufreihenfolgen, Zellen und Spaltenfolge je Nutzer; kein Fallback auf `"default"`.

- **AC-8:** Given der Code nach der Umstellung / When der Trip-Telegram-Pfad gerendert wird / Then wird der Altpfad `get_metrics_for_channel("telegram", ...)` nicht mehr gelesen, und eine Konfiguration, in der Resolver-Liste und Grundauswahl voneinander abweichen, folgt der Resolver-Liste.
  - Test: Verhaltenstest an der Telegram-Ausgabe mit gezielt abweichender Telegram-Folge (rot vor der Umstellung); kein Dateiinhalt-Check.

- **AC-9:** Given die neue Fallliste `fallliste_telegram.json` / When der Wächter `test_einstellung_gleich_mail_fallliste.py` läuft / Then ist die Datei registriert, alle Pflichtfelder sind gefüllt, die IDs sind global eindeutig, und die Kanal-Abdeckung ist nicht kleiner als vor der Änderung.
  - Test: `test_einstellung_gleich_mail_fallliste.py` einzeln inklusive Selbsttests der Fehlerzahl; Abdeckung über `pruefe_kanal_abdeckung` gegen den Vorher-Stand.

- **AC-10:** Given Trip-Konfigurationen mit E-Mail-, SMS- und Premium-SMS-Auswahl sowie die Telegram-Kurzform / When das Briefing gerendert wird / Then bleiben diese Kanäle inhaltsgleich zum Stand vor der Änderung.
  - Test: `test_channel_metric_matrix.py`, `tests/golden/vergleichs_mail/telegram_sms.*` und die E-Mail-Golden-Dateien einzeln unverändert grün.

## Definition of Done

- AC-1 bis AC-10 durch benannte Tests grün; Golden-Telegram und Prüfkatalog einzeln grün, Golden-Dateien unverändert.
- Mutations-Gegenprobe durch den Adversary (siehe Test Plan).
- Vor dem ersten Code gegen `origin/main` abgeglichen.
- Alle 6 CI-Checks grün, Staging-Verifikation mit echt zugestellter Telegram-Nachricht (Trip und Orte) unverändert, Prod-Selftest bestanden.
- #3063 mit geschlossen.

## Test Plan

### Automated Tests (TDD RED)

Zusicherungen am Ergebnis der Telegram-Ausgabe, kein Mock-Theater (kein `Mock()`/`patch()`).

- [ ] Neu `tests/tdd/test_3098_telegram_resolver.py`: GIVEN Trip mit abweichender Telegram-Folge und abgewählten Metriken WHEN Telegram-Nachricht morning/evening THEN Folge und Menge gleich Resolver `.telegram`, Kurzübersicht und Windrichtung gleiche Liste (AC-2, AC-8). Rot vor der Umstellung.
- [ ] Neu: GIVEN Formate Roh/Einfach/ohne Angabe WHEN Telegram THEN je erwartete Zellen; Adapter lässt `format=None` unverändert (AC-3).
- [ ] Neu: GIVEN Windrichtung Roh/Einfach, DE/EN WHEN Telegram THEN eigene bzw. zusammengefasste Angabe, Kopf `briefing_typ` (AC-4).
- [ ] Neu: GIVEN Kanal-Ebene nie/leer/gesetzt WHEN Telegram THEN Kaskade (AC-5).
- [ ] Neu: GIVEN Orte-Telegram Folge/Format/DE/EN WHEN Versand und Vorschau THEN gleich und passend zur Auswahl (AC-6).
- [ ] Neu: GIVEN zwei Nutzer WHEN beide Aufrufreihenfolgen THEN je eigene Nachricht (AC-7).
- [ ] Neu: `fallliste_telegram.json` und Wächter-Anpassung (AC-9); Wächter-Selbsttests an neue Fehlerzahl angepasst.
- [ ] Unverändert grün (Regression, einzeln benannt): `tests/golden/test_telegram_briefing_golden.py`, `test_telegram_briefing_zweisprachig.py`, `test_i18n_ratsche_narrow_telegram.py`, `test_telegram_kurzstil_trip_briefing.py`, `test_telegram_felt_temperature_overview.py`, `test_3047_runde7_telegram_tagesfenster.py`, `test_telegram_metric_notice.py`, `unit/test_telegram_kuerzel_folgt_register.py`, `unit/test_telegram_thunder_window_konsistenz.py`, `test_3047_r7_kanaele_trip.py`, `test_3057_channel_list_resolver.py`, `test_3096_mail_resolver.py`, `test_compare_render_options_resolver.py`.
- [ ] Mutations-Gegenprobe durch den Adversary (Kopie extern, String-Ersetzung, nie `git checkout/stash/reset`): Adapter ohne `enabled`-Filter; Adapter vertauscht Folge; `format=None` als Roh gedeutet; `bucket`/`order` nicht aus der Grundauswahl übernommen; Resolver auf kollabiertem statt unkollabiertem `dc`; Windrichtung-Merge liest andere Liste als die Tabelle. Jede Verfälschung muss mindestens einen Test an der Telegram-Ausgabe rot machen.
- Live-E2E: echt zugestellte Telegram-Nachricht auf Staging (Trip und Orte), Ergebnis unverändert.

## Affected Files

| Datei | Änderung | Beschreibung |
|-------|----------|--------------|
| `src/output/renderers/trip_report.py` | MODIFY | Resolver `.telegram` einmal vor Kollabierung, Altpfad löschen, `_dc_telegram` aus Adapter |
| `src/output/renderers/email/helpers.py` | MODIFY | Adapter `telegram_metric_configs` |
| `src/output/renderers/narrow.py` | keine Änderung | liest weiter `dc`, jetzt aus derselben Resolver-Liste |
| Orte (`report_config_resolver.py`, `comparison.py`, `scheduler_dispatch_service.py`, `compare_preview_service.py`) | keine Änderung | bereits resolver-basiert |
| `tests/fixtures/einstellung_gleich_mail/fallliste_telegram.json` | CREATE | Telegram-Fallliste (neue IDs) |
| `tests/tdd/test_einstellung_gleich_mail_fallliste.py` | MODIFY | `TEILDATEIEN`, `_syn_daten()`, Selbsttests, `PY_TEST_GLOBS` |
| `tests/tdd/test_3098_telegram_resolver.py` | CREATE | Verhaltensnachweise Trip und Orte, DE/EN, Zwei-Nutzer |
| `docs/specs/modules/feat_3098_telegram_resolver.md` | CREATE | diese Spec |

## Known Limitations

- Format-Standard ohne Angabe bleibt zwischen Trip (Katalog) und Orte (Roh) verschieden (Designentscheidung).
- Telegram-Kurzform = SMS-Text bleibt bei der SMS-Auswahl bis #3099.
- Orte-Fallback ohne `channel_layouts` (`channel_active_metrics`) bleibt bis #3102 (erledigt, #3102: #3277, #3351).
- `ChannelRow` trägt `bucket`/`order`/`sms_threshold` nicht; der Adapter ergänzt sie aus der Grundauswahl.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121 (kein neues ADR, kein Nachtrag nötig)
- **Rationale:** Setzt die Adapter-Vorgabe des ADR-0121 für Telegram um, analog Phase 3a (#3096); keine bestehende Entscheidung wird geändert. ADR-0095 (Kanal-Parität) bleibt erfüllt, weil die zugestellte Nachricht gleich bleibt.

## Changelog

- 2026-11-17: Initial spec created (Phase 3c, Issue #3098, Epic #3058)
- 2026-11-17: Umsetzungsabweichungen ergänzt (Implementation Details): Format `None` = Katalog-Standard ohne Erben eines Roh der Grundauswahl; `order` = Resolver-Index
