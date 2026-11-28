---
entity_id: feat_3057_kanal_liste_resolver
type: module
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
tags: [epic-3047, phase-2, resolver, kanal-liste]
---

> **Hinweis (2026-11-17, [ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Der Resolver dieser Spec ist gebaut und gilt weiter. Die in Dependencies und „Out of Scope“ genannte Editor-Karte „Inhalt je Kanal“ (#3060, #3031, PR #3042) wird so nicht gebaut: ADR-0124 ersetzt sie durch die Tabelle „Was steht wo“ und schneidet das gespeicherte Format (ADR-0121) mit dem Bau zu #3122 neu (je Metrik ein Satz Stellen-Flaggen, eine Darstellung je Stelle, eine Reihenfolge). ACs unverändert.

# Kanonische Kanal-Liste und Resolver (Phase 2a von Epic #3047)

## Approval

- [ ] Approved

## Purpose

Trip und Orte beantworten die Frage „welche Metriken in welcher Folge und Darstellung je Kanal“ bisher mit getrennten Regeln und Feldern. Diese Spec führt ein gemeinsames Lese-Format (ADR-0121) und einen reinen Resolver ein, über den die bestehenden Einstiegspunkte lesen, damit Editor und Renderer in den Folgephasen aus derselben Quelle schöpfen. Die zugestellte Mail ändert sich in keinem Kanal.

## Source

- **File:** `src/services/channel_list_resolver.py`
- **Identifier:** `resolve_channel_lists`, `MailViewModel`, `ChannelRow`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/services/`, `src/app/`). Kein Frontend, keine Go-API in diesem Schnitt (Go reicht `display_config` ungeprüft durch, ADR-0077).
>
> **Trip/Orte-Teilung:** Ein Resolver mit `surface="trip"|"compare"`, kein Pendant-Paar (ADR-0097).
>
> **Kanäle:** E-Mail, Telegram, SMS, Premium-SMS sind im View-Model benannt (ADR-0095); der Inhalt je Kanal bleibt wie heute, Premium-SMS ohne eigenen Schlüssel = SMS-Liste (ADR-0049, ADR-0121 Nr. 5).
>
> **Mandantentrennung:** Der Resolver ist eine reine Funktion über ein übergebenes `display_config`, ohne Dateizugriff und ohne `user_id`. Ein Zwei-Nutzer-Test entfällt begründet, weil kein datenbewegender Endpoint entsteht (Endpoint = #3066).

## Scope

Schnitt 2a von Phase 2 (Epic #3047): kanonische Datenform (ADR-0121) und ein reiner Lese-Resolver für die vier Versandkanäle E-Mail, Telegram, SMS und Premium-SMS, für Trip und Orte, eingebunden über die zwei bestehenden Einstiegspunkte `get_metrics_for_channel` und `resolve_compare_render_options`. Die zugestellte Mail bleibt in jedem Kanal zeichengleich. Ausblick/Stundenverlauf (#3065), Lese-Endpoint (#3066), Renderer-Umstellung und Eager-Migration (#3058) sind abgespalten (siehe Out of Scope).

## Estimated Scope

- **LoC:** ca. 600 (Code + Tests, Doku zählt nicht; harte Grenze dieses Durchlaufs)
- **Files:** 5 Code-/Testdateien, 3 Doku-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `UnifiedWeatherDisplayConfig.get_metrics_for_channel` (`src/app/models.py`) | function | Trip-Einstiegspunkt, wird Adapter über den Resolver; Alarmpfad `notification_service` nutzt ihn |
| `_cascade_source_for_channel`, `_clip_to_global_maximum`, `_sorted_by_layout` (`models.py`) | function | Trip-Kaskade `per_report > channel > global` ∩ Grundauswahl, wird gebündelt, nicht neu geschrieben |
| `_effective_format_mode` (`email/helpers.py`), `_resolve_format_mode` (`loader.py`) | function | Trip-Format und Katalog-Standard |
| `resolve_compare_render_options`, `CompareRenderOptions` (`services/report_config_resolver.py`) | function | Orte-Einstiegspunkt, wird Adapter |
| `resolve_channel_layout_rows`, `resolve_channel_enabled_metrics`, `_friendly_effective` (`renderers/compare_metric_ids.py`) | function | Orte-Kaskade `channel_layouts` vor `channel_active_metrics` vor Grundauswahl |
| ADR-0049, 0050, 0059, 0077, 0095, 0097, 0101, 0119, **0121 (neu)** | ADR | Entscheidungsgrundlage |
| Phase-1-Katalog (`tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte}.json`, `tests/tdd/test_einstellung_gleich_mail_*.py`) | tests | Messlatte, bleibt unverändert grün |
| #3048 (Trip-Altbestand ohne `display_config.metrics`, läuft parallel) | issue | Ändert `get_metrics_for_channel`/`DEFAULT_TRIP_METRIC_IDS`. **Vor Implementierung gegen `origin/main` abgleichen**; dessen Rückfall wird Teil des Resolvers, nicht zweite Quelle |
| PR #3042 / #3060 (Editor-Karte) | pr | Schreibt `channel_layouts` mit `use_friendly_format`; muss verlustfrei lesbar sein, braucht keine Änderung |

## Implementation Details

1. **ADR-0121** (`docs/adr/0121-kanonische-kanal-liste.md`, Index in `docs/adr/README.md`): Datenform, Lese-Adapter, Premium-SMS-Fallback, lazy Migration.
2. **Resolver** `src/services/channel_list_resolver.py`: reine Funktion `resolve_channel_lists(display_config, surface, report_type)` gibt ein eingefrorenes `MailViewModel` zurück, je Kanal (`email`, `telegram`, `sms`, `premium_sms`) eine geordnete Liste von `ChannelRow(metric_id, enabled, format, order)`. `format` ∈ `raw|simplified|None` (None = Flächen-Standard, Trip Katalog, Orte Roh, unverändert). Format wird aus `format`, `format_mode` oder `use_friendly_format` gleichwertig gelesen. Trip nutzt die bestehende Kaskade mit `report_type` (morning/evening), Orte die bestehende `channel_layouts`-Kaskade; der Resolver ruft die Primitive auf. Eine leere Liste bleibt leer (ADR-0050). Amtliche Warnungen sind keine Zeilen. `premium_sms` fehlt ⇒ Kopie der SMS-Zeilen. Der Resolver schreibt nie und liest keine Datei.
3. **Einbindung:** `get_metrics_for_channel` (models.py) und `resolve_compare_render_options` (report_config_resolver.py) beziehen Auswahl, Folge und Format aus dem Resolver; Signaturen und Rückgabetypen (`list[MetricConfig]`, `CompareRenderOptions`) bleiben. Renderer und übrige Aufrufer bleiben unberührt (Umstellung = #3058).
4. **Lese-Adapter im Resolver**, nicht im Loader: der Loader bleibt unverändert, Bestandsdaten bleiben byte-gleich.
5. **Nachweis:** Differenztest neu = alt (Altpfad als Test-Orakel, wird in #3058 gelöscht) über die Phase-1-Fallisten und Kombinationen None/`[]`/gefüllt × `per_report` morning/evening × Format-Variante × `premium_sms` vorhanden/fehlend. Kein Mock-Theater: echte `display_config`-Dicts und echte Primitive.

## Expected Behavior

- **Input:** `display_config` (Trip oder Orte, Rohform oder aus dem Loader), `surface`, `report_type`.
- **Output:** `MailViewModel` mit vier Kanal-Listen; die zwei Einstiegspunkte liefern exakt dieselben Werte wie vor der Änderung.
- **Side effects:** keine. Kein Schreiben, kein I/O, keine Mutation der Eingabe.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gefüllten, leeren und fehlenden Kanal-Listen (E-Mail, Telegram, SMS) in Kombination mit `per_report` für morning und evening / When `get_metrics_for_channel` für jede Kombination aufgerufen wird / Then entspricht das Ergebnis (Auswahl, Reihenfolge, Format) dem Altpfad als Orakel, eine leere Liste bleibt leer.
  - Test: Differenztest über alle Kombinationen None/`[]`/gefüllt × morning/evening × E-Mail/Telegram/SMS, Vergleich neu gegen Altpfad-Orakel.

- **AC-2:** Given ein Orts-Vergleich mit `channel_layouts`, nur `channel_active_metrics` oder keinem von beiden / When `resolve_compare_render_options` aufgelöst wird / Then sind `enabled_metrics_by_channel`, `channel_rows_by_channel` und `metric_formats(kanal)` für E-Mail, Telegram und SMS gleich dem Altpfad-Orakel.
  - Test: Differenztest über die Orte-Kombinationen und alle Fälle aus `fallliste_orte.json`.

- **AC-3:** Given ein Trip mit gespeichertem `morning_enabled=False` an einer Metrik / When das Abend- und das Morgenbriefing aufgelöst wird / Then fehlt die Metrik nur im Morgenbriefing, und eine absichtlich verfälschte Auflösung, die das Flag ignoriert, lässt mindestens einen Test rot werden.
  - Test: Zweifalltest morning/evening; Mutation per String-Ersetzung mit externer Sicherungskopie, Nachweis im PR (Nachprüfungs-Punkt 6 der unabhängigen Phase-1-Nachprüfung, Kommentar in #3047 vom 16.11.2026: Mutation `morning_enabled=False` überlebte bisher).

- **AC-4:** Given Zeilen mit dem Format als `format`, als `format_mode` oder als `use_friendly_format` (so schreibt es PR #3042) / When der Resolver sie liest / Then ergibt jede Schreibweise dieselbe Darstellung (Roh oder Einfach), fehlt die Angabe, gilt der heutige Flächen-Standard (Trip Katalog, Orte Roh), und die gespeicherten Daten bleiben unverändert.
  - Test: Drei Schreibweisen derselben Liste liefern identische Zeilen; Eingabe-Dict vor und nach dem Aufruf byte-gleich; Orte-Zeile ohne Format bleibt Roh.

- **AC-5:** Given eine Konfiguration mit eigener `premium_sms`-Liste bzw. ohne diesen Schlüssel / When der Resolver aufgelöst wird / Then enthält `premium_sms` die eigene Liste, fehlt der Schlüssel, ist sie gleich der SMS-Liste, und der versendete Premium-SMS-Text bleibt wie bisher der SMS-Text. *(2026-11-28, ADR-0131: endgültig derselbe Inhalt wie die SMS, eine eigene Premium-Auswahl gibt es nicht.)*
  - Test: Resolver-Aufruf beider Varianten; bestehender Premium-SMS-Test (Orte und Trip) bleibt unverändert grün.

- **AC-6:** Given ein Trip und ein Orts-Vergleich lösen amtliche Warnungen aus / When der Resolver aufgelöst wird / Then steht keine Warnung als speicherbare Zeile in einer Kanal-Liste, und eine ausdrücklich leere Liste bleibt leer, auch bei gesetzter Grundauswahl.
  - Test: Zeilen enthalten nur Katalog-Metriken; `[]` bleibt `[]` für Trip und Orte.

- **AC-7:** Given der Alarmpfad (`notification_service`) erzeugt eine Warnung für einen Trip mit abweichenden Kanal-Listen / When die Nachricht je Kanal gebaut wird / Then verwendet sie dieselben Metriken und Reihenfolge wie vor der Änderung in allen vier Kanälen.
  - Test: bestehende Alarm-Kettentests (`test_compare_alarm_einstellung_auslieferung_kette.py` und Trip-Pendant) bleiben unverändert grün, plus Differenzfall für Alarm-Aufrufer.

- **AC-8:** Given der Phase-1-Prüfkatalog (Trip- und Orte-Fallliste, Ketten- und Auslieferungstests, Golden-Dateien) / When er nach der Änderung einzeln ausgeführt wird / Then bleibt er vollständig grün und die zugestellten Mails sind in HTML, Klartext und Kompakt zeichengleich zu den Golden-Dateien.
  - Test: `test_einstellung_gleich_mail_{trip,orte,fallliste,editor_standard,validatoren}.py`, `test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py` einzeln, ohne Änderung der Golden-Dateien.

- **AC-9:** Given der Resolver wird mit einem Konfigurations-Dict aufgerufen / When der Aufruf beendet ist / Then wurde weder das Dict verändert noch eine Datei gelesen oder geschrieben, und das View-Model ist unveränderlich.
  - Test: tiefe Kopie vor/nach dem Aufruf verglichen, Versuch einer Attributzuweisung auf dem View-Model schlägt fehl, Aufruf in einem Verzeichnis ohne Datenwurzel gelingt.

## Definition of Done

- AC-1 bis AC-9 durch benannte Tests grün; Mutation aus AC-3 nachweislich rot gefangen.
- Phase-1-Prüfkatalog einzeln grün, Golden-Dateien unverändert.
- ADR-0121 im Index, `tests/test_adr_index_drift.py` grün.
- Vor dem ersten Code gegen `origin/main` (#3048) abgeglichen.
- Alle 6 CI-Checks grün, Staging-Verifikation (`/e2e-verify`) und Prod-Selftest bestanden; zugestellte Staging-Mail per Validator unverändert.

## Test Plan

- **Kern-Schicht (deterministisch, ohne Netz):** `tests/tdd/test_3057_channel_list_resolver.py` mit Differenztest neu = alt gegen `tests/helpers/kanal_liste_orakel.py` (AC-1, AC-2, AC-7), Format-Schreibweisen und Byte-Gleichheit der Eingabe (AC-4), Premium-SMS-Fallback (AC-5), Warnungen und leere Liste (AC-6), Reinheit/Unveränderlichkeit (AC-9), Zweifall morning/evening (AC-3).
- **Regression:** Phase-1-Katalog `test_einstellung_gleich_mail_{trip,orte,fallliste,editor_standard,validatoren}.py`, `test_einstellung_gleich_auslieferung.py`, `test_compare_einstellung_auslieferung_kette.py`, `test_compare_alarm_einstellung_auslieferung_kette.py` einzeln (AC-7, AC-8).
- **Mutations-Gegenprobe:** `morning_enabled`-Auswertung im Resolver verfälscht ⇒ mindestens ein Test rot (AC-3); weitere Mutationen durch den Adversary.
- **Live-E2E:** Staging-Mail-Validatoren (`briefing_mail_validator.py`, `email_spec_validator.py`) gegen echt zugestellte Mail, Ergebnis unverändert.

## Out of Scope

- Ausblick- und Stundenverlauf-Liste im View-Model (Schlüssel `outlook`/`hourly` nur reserviert): #3065.
- Lese-Endpoint „Mail-View“ für den Editor, Go-Proxy, Zwei-Nutzer-Test: #3066.
- Umstellung der Renderer und übrigen Aufrufer, Entfernen der Altpfade, Eager-Migration (RMW), Verhaltensänderung des nie eingestellten Orte-Stundenverlaufs (Konzept §5 Pkt. 6b, ändert die Mail bestehender Orte), Roh/Einfach für Stundenverlauf: #3058.
- Oberfläche der Karte „Inhalt je Kanal“: #3060 / PR #3042 (dessen geschriebenes Format ist in AC-4 lesbar).
- Jede Änderung der zugestellten Mail in irgendeinem Kanal.

## Affected Files

| Datei | Änderung | Beschreibung | LoC |
|-------|----------|--------------|-----|
| `src/services/channel_list_resolver.py` (Python-Core) | CREATE | Resolver, `MailViewModel`, `ChannelRow`, Format-Lese-Adapter | +230 |
| `src/app/models.py` (Python-Core) | MODIFY | `get_metrics_for_channel` liest aus dem Resolver, Signatur unverändert | +25/-30 |
| `src/services/report_config_resolver.py` (Python-Core) | MODIFY | `resolve_compare_render_options` liest Kanalzeilen aus dem Resolver | +30/-35 |
| `tests/tdd/test_3057_channel_list_resolver.py` | CREATE | Differenztest neu = alt, Adapter, Mutation, Reinheit | +260 |
| `tests/helpers/kanal_liste_orakel.py` | CREATE | Altpfad als Test-Orakel (Kopie der Alt-Aufrufe, wird in #3058 gelöscht) | +50 |
| `docs/adr/0121-kanonische-kanal-liste.md`, `docs/adr/README.md` | CREATE/MODIFY | ADR und Index | Doku |
| `docs/specs/modules/feat_3057_kanal_liste_resolver.md` | CREATE | diese Spec | Doku |

Summe Code + Tests: ca. 600 (+/- 15 %); wird die Grenze überschritten, wird der Orakel-Umfang gekürzt, nicht der Prüfumfang der ACs.

## Known Limitations

- Bis #3058 existieren Altpfade und Resolver nebeneinander; der Differenztest ist die Klammer. Das Orakel wird mit den Altpfaden gelöscht.
- Die Format-Standards unterscheiden sich weiter (Trip Katalog, Orte Roh) und stehen als `None` im View-Model (ADR-0121 Nr. 1).
- Die Premium-SMS-Liste ist lesbar, aber kein Renderer wertet eine eigene Liste aus (ADR-0121 Nr. 5).
- Die Punkte 1, 3 bis 5 und 7 der unabhängigen Phase-1-Nachprüfung (Kommentar in #3047 vom 16.11.2026; Orte-Stundenverlauf ohne Schnitt mit der Grundauswahl, Validator-Lücken bei Ortsfolge und Roh/Einfach, Anhängen neuer Grundauswahl-Metriken beim Lesen im Trip) sind nicht Teil dieses Schnitts und werden durch ihn nicht verschärft.
- Konflikte mit #3048 sind möglich (gleiche Funktion); Abgleich gegen `origin/main` vor dem ersten Code ist Pflicht.
- Bei Eingabe als Loader-Modell ist nur `format_mode` lesbar, weil der Loader `format` verwirft (Loader bleibt laut Implementation Details Nr. 4 unverändert). Die Mail ist nicht betroffen, weil der Altpfad `format` ebenfalls nicht liest. Die Vereinheitlichung beim Lesen gehört zu #3058.
- Präzisierung AC-6 für Orte: Eine leere Liste in `channel_active_metrics` bleibt leer. `channel_layouts: []` hängt wie heute die Grundauswahl an (#3031/#3039), weil AC-2 und AC-8 eine unveränderte Mail verlangen; die Verhaltensänderung gehört zu #3058.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121
- **Rationale:** Datenform und gemeinsamer Resolver berühren Datenmodell und alle vier Kanäle; verfeinert ADR-0119 (Datenform, Format-Standard) und ADR-0049 (Premium-SMS-Fallback), ohne eine bestehende Entscheidung still zu ändern.

## Changelog

- 2026-11-16: Initial spec created (Phase 2, Schnitt 2a von #3057/#3047)
- 2026-11-16: Umfang Code+Tests ca. 940 Zeilen statt 600; der Mehrumfang liegt in Prüffällen und Orakel, der Prüfumfang wurde bewusst nicht gekürzt.
