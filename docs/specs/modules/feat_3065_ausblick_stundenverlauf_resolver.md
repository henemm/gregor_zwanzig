---
entity_id: feat_3065_ausblick_stundenverlauf_resolver
type: feature
created: 2026-11-16
updated: 2026-11-16
status: draft
version: "1.0"
workflow: feat-3065-ausblick-stundenverlauf-resolver
tags: [epic-3047, phase-2b, resolver, kanal-liste, ausblick, stundenverlauf]
---

> **Hinweis (2026-11-17, [ADR-0124](../../adr/0124-was-steht-wo-eine-tabelle.md), Issue #3122):** Die Resolver-Listen `outlook` und `hourly` sind gebaut und gelten bis zum Bau zu #3122. Der hier als Abnehmer genannte Editor (#3060) wird so nicht gebaut. Nach ADR-0124 Nr. 4 haben 3-Tages-Ausblick und Stundenverlauf keine eigene, unabhängige Liste mehr: sie folgen der E-Mail-Auswahl mit Abwahl je Metrik (Spalten der Tabelle „Was steht wo“). ACs unverändert.

# Ausblick- und Stundenverlauf-Liste im Kanal-Listen-Resolver (Phase 2b von Epic #3047)

## Approval

- [ ] Approved

## Purpose

Der gemeinsame Kanal-Listen-Resolver (#3057, ADR-0121) beantwortet bisher nur die vier Versandkanäle. Diese Spec ergänzt zwei Flächen-Listen im selben Lese-Format: den 3-Tages-Ausblick (Trip und Orte, mit Roh/Einfach je Zeile) und den Stundenverlauf (nur Orte). Damit können Editor (#3060/#3066) und Renderer (#3058) später aus einer Quelle lesen. Rein lesend: die zugestellte Mail ändert sich in keinem Kanal.

## Source

- **File:** `src/services/channel_list_resolver.py`
- **Identifier:** `MailViewModel` (neue Felder `outlook`, `hourly`), `_trip_view`, `_compare_view`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/services/`, `src/output/renderers/`). Kein Frontend, keine Go-API in diesem Schnitt.
>
> **Trip/Orte-Teilung:** Weiter ein Resolver mit `surface="trip"|"compare"`; Ausblick läuft für beide Flächen über dieselbe Regel `_erbe_grundauswahl` (ADR-0059), kein Pendant-Paar (ADR-0097).
>
> **Kanäle:** Ausblick und Stundenverlauf sind Mail-Blöcke (E-Mail). Telegram, SMS und Premium-SMS bleiben unverändert (ADR-0095); ihr Inhalt wird von dieser Scheibe nicht berührt.
>
> **Mandantentrennung:** Reine Funktion über ein übergebenes `display_config`, ohne Dateizugriff und ohne `user_id`. Zwei-Nutzer-Test entfällt begründet, weil kein datenbewegender Endpoint entsteht (Endpoint = #3066).

## Scope

Schnitt 2b von Phase 2. Der Resolver liefert zusätzlich die Listen `outlook` (Trip und Orte) und `hourly` (nur Orte). Die Werte werden ausschließlich durch Aufruf der bestehenden Altfunktionen gewonnen; keine Regel wird neu geschrieben. Einziger Eingriff in Mail-Code ist die verhaltensgleiche Zerlegung von `resolve_hourly_metrics` in eine ID-Stufe und einen `dp_field`-Schritt.

## Estimated Scope

- **LoC:** Produktivcode ca. +75/-5, Tests ca. +250, Doku ca. +80
- **Files:** 4 Code-/Testdateien, 2 Doku-Dateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_trip_outlook_metrics(dc, report_type)` (`compare_outlook_metric_ids.py`) | function | Trip-Ausblick: Grundauswahl aus `allowed_metric_ids_for_report_type`, Folge aus `get_metrics_for_report_type` |
| `resolve_compare_outlook_metrics(outlook_metrics, enabled_metrics)`, `_erbe_grundauswahl`, `_kennungen_aus_renderer_ids` (`compare_outlook_metric_ids.py`) | function | Orte-Ausblick und gemeinsame Regel None/`[]`/Schnitt/Rückfall; einzige Umkehrtabelle Renderer-Kennung nach Katalog-ID |
| `resolve_trip_outlook_formats`, `resolve_compare_outlook_formats` (`compare_outlook_metric_ids.py`) | function | Roh/Einfach je Ausblick-Zeile (`{id: bool}`) |
| `normalize_outlook_metric_formats` (`app/metric_catalog.py`) | function | nur ausblick-fähige IDs tragen ein Format |
| `resolve_hourly_metrics`, `_standard_aus_grundauswahl`, `_schnitt_mit_grundauswahl`, `HOURLY_DEFAULT_METRIC_IDS`, `HOURLY_MERGE_ONLY_METRIC_IDS` (`compare_hourly_metric_ids.py`) | function | Altpfad Stundenverlauf, wird in ID-Stufe und `dp_field`-Schritt zerlegt |
| `resolve_enabled_metrics` (`compare_metric_ids.py`) | function | Grundauswahl Orte (`global_metrics`), wird im Orte-View wiederverwendet |
| `UnifiedWeatherDisplayConfig`, `_trip_model` | class/function | Trip-Modell ungekollabiert (kanal-neutraler Stand, Adversary F001 #1720) |
| ADR-0059, 0055, 0097, 0119, 0121 | ADR | Entscheidungsgrundlage; ADR-0121 bekommt Nachtrag 2b |
| Prüfkatalog `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` (AB/SV, `O-SV-*-H1-*`, `VO-14`), `fallliste_trip.json` (`trip-paar-ausblick-*`) | tests | Messlatte, bleibt unverändert grün |
| #3067, #3048 | issue | Parallele Arbeit an Nachbarcode; vor Implementierung gegen `origin/main` abgleichen |

## Implementation Details

1. **Datenform:** `MailViewModel` erhält zwei neue Felder `outlook: Rows = None` und `hourly: Rows = None`, hinter `layout_channels`, beide mit Default, damit bestehende Konstruktionen (per Keyword) nicht brechen. `ChannelRow` bleibt unverändert.
2. **Vokabular `metric_id`:** Für `outlook` und `hourly` ist `metric_id` die Katalog-Kennung (so liefert sie der Ausblick schon, so speichert sie später der Editor). Die Orte-Kanäle bleiben Renderer-Kennungen. Diese Zwei-Vokabular-Lage ist bewusst und wird im ADR-Nachtrag dokumentiert. Keine Rückübersetzungstabelle `dp_field` nach Katalog-ID.
3. **Split `resolve_hourly_metrics`:** Die ID-Stufe (bisher innerhalb der Funktion, inklusive `_standard_aus_grundauswahl` und `_schnitt_mit_grundauswahl`) liefert Katalog-IDs oder `None`; `resolve_hourly_metrics` ruft sie auf und bildet danach per `get_metric(id).dp_field` ab. Öffentliche Signatur und Rückgabe von `resolve_hourly_metrics` bleiben unverändert, ebenso das Warn-Logging.
4. **Trip-View:** `outlook` = `resolve_trip_outlook_metrics(dc, report_type)` auf dem Modell aus `_trip_model` (ungekollabiert, kein Schnitt mit `channel_layouts.email`). `hourly` bleibt immer `None` (es gibt keine eigene Trip-Stundenverlauf-Liste, die Haupttabelle ist die E-Mail-Liste).
5. **Orte-View:** `outlook` = `resolve_compare_outlook_metrics(outlook_metrics, global_metrics)`; `hourly` = ID-Stufe von `resolve_hourly_metrics(hourly_metrics, global_metrics)`. `wind_direction` (Merge-only) wird nicht herausgefiltert, die Zeile steht wie im Altpfad.
6. **Format Ausblick:** wirksamer Wert aus `normalize_outlook_metric_formats` über die Altfunktionen `resolve_*_outlook_formats`: `True` wird `"simplified"`, ausdrücklich `False` wird `"raw"`, kein Eintrag oder nicht ausblick-fähig wird `None` (Flächen-Standard = Roh, wie heute). Stundenverlauf: `format` immer `None` (Roh/Einfach im Stundenverlauf = #3058).
7. **None-Vertrag:** `outlook`/`hourly` = `None` heißt Renderer-Vorgabemenge (Orte, Altbestand ohne Grundauswahl), `()` heißt Block entfällt (bewusst leer), sonst Zeilen in Anzeigefolge mit `order` ab 0 und `enabled=True`.
8. **Abschaltflags** `hourly_enabled` und `outlook_enabled` (Preset-Top-Level, nicht `display_config`) werden nicht abgebildet; bewusst draußen, im ADR-Nachtrag dokumentiert.
9. **Kein Adapter-Umbau** in `resolve_compare_render_options`, `trip_report.py` oder `email/outlook.py`. Niemand liest `view.outlook`/`view.hourly` in dieser Scheibe; sonst würde der Differenztest den Adapter gegen sich selbst messen.
10. **ADR-0121:** Nachtrag 2b mit Vokabular (Katalog-ID für `outlook`/`hourly`), None-Vertrag und den draußen gelassenen Abschaltflags.
11. **Nachweis:** Differenztest neu gegen alt (echte Altfunktionen als Orakel in `tests/helpers/kanal_liste_orakel.py`, keine Mocks) über Kombinationen `active_metrics` × `outlook_metrics` × `hourly_metrics` × Formate je None/`[]`/Liste/Totalschnitt, `report_type` morning/evening.

## Expected Behavior

- **Input:** `display_config` (Trip oder Orte, Rohform oder aus dem Loader), `surface`, `report_type`.
- **Output:** `MailViewModel` mit den vier Kanal-Listen wie bisher (unverändert) plus `outlook` und `hourly`.
- **Side effects:** keine. Kein Schreiben, kein I/O, keine Mutation der Eingabe.

## Acceptance Criteria

- **AC-1:** Given ein Orts-Vergleich mit Ausblick-Auswahl als nie eingestellt (None), bewusst leer (`[]`), gefüllt oder mit Totalschnitt gegen die Grundauswahl, jeweils mit und ohne gesetzte Grundauswahl / When der Resolver die Orte-Ausblick-Liste liefert / Then entsprechen Auswahl und Reihenfolge exakt dem Altpfad `resolve_compare_outlook_metrics` (Erben der Grundauswahl nach ADR-0059, None bleibt None, `[]` bleibt leer, Totalschnitt fällt wie im Altpfad zurück und ist nicht leer).
  - Test: Differenztest über alle Kombinationen None/`[]`/gefüllt/Totalschnitt × Grundauswahl gesetzt/leer/fehlend, Vergleich Resolver gegen echte Altfunktion, keine Mocks.

- **AC-2:** Given ein Trip mit enger E-Mail-Kanal-Liste (`channel_layouts.email`), ohne eigene Ausblick-Auswahl und mit Altbestand ohne `metrics` / When der Resolver den Trip-Ausblick für Morgen- und Abendbriefing (report_type morning und evening) liefert / Then entspricht die Liste je Report-Typ dem Altpfad `resolve_trip_outlook_metrics` auf dem ungekollabierten Modell, und die enge E-Mail-Liste schneidet den Ausblick nicht.
  - Test: Differenztest je morning/evening gegen die echte Altfunktion; Fall mit engem `channel_layouts.email`, dessen Ausblick länger ist als die E-Mail-Liste.

- **AC-3:** Given Ausblick-Zeilen mit Format-Angabe wahr, ausdrücklich falsch, ohne Eintrag oder bei einer nicht ausblick-fähigen Metrik / When der Resolver die Zeilen liefert / Then steht bei wahr das Format `simplified`, bei ausdrücklich falsch `raw`, und ohne Eintrag oder nicht ausblick-fähig keine Angabe (None, Flächen-Standard Roh), für Trip und Orte gleich.
  - Test: Drei Format-Fälle plus nicht ausblick-fähige ID je Fläche; Abgleich mit `resolve_*_outlook_formats` der Altpfade.

- **AC-4:** Given ein Orts-Vergleich mit Stundenverlauf-Auswahl als nie eingestellt, leer, gefüllt, Totalschnitt, mit `wind_direction` und mit leerer oder fehlender Grundauswahl / When der Resolver die Stundenverlauf-Liste liefert / Then stehen darin Katalog-IDs, deren Abbildung auf `dp_field` exakt dem Ergebnis von `resolve_hourly_metrics` entspricht (Folge, Rückfall, `[]`, None), `format` ist bei jeder Zeile None und `wind_direction` bleibt enthalten.
  - Test: Differenztest `dp_field` der Resolver-IDs gegen `resolve_hourly_metrics` über alle Kombinationen; Prüfung `format is None` für jede Zeile; `wind_direction`-Fall.

- **AC-5:** Given ein Orts-Vergleich ohne Grundauswahl und ohne Stundenverlauf-Auswahl bzw. mit bewusst leerer Auswahl / When der Resolver aufgelöst wird / Then bedeutet None bei `outlook` und `hourly` Renderer-Vorgabemenge und das leere Tupel bedeutet, dass der Block entfällt, und beide Fälle sind unterscheidbar; die Stundenverlauf-Liste eines Trips ist in jedem Fall None.
  - Test: Fälle None und `()` für beide Listen am Orte-View; Trip-View mit beliebiger Konfiguration (inklusive gefüllter Kanal-Listen) liefert `hourly is None`.

- **AC-6:** Given `resolve_hourly_metrics` wird nach dem Split mit allen Altfall-Eingaben (None, `[]`, gefüllt, historische Kurzschlüssel, ausgenommene und unbekannte Werte, Grundauswahl None/`[]`/gefüllt) aufgerufen / When das Ergebnis mit dem Stand vor dem Split verglichen wird / Then sind Signatur und Rückgabe unverändert, einschließlich Reihenfolge und `None`-Fall.
  - Test: bestehende Stundenverlauf-Tests (`compare_hourly_*`) einzeln grün und unverändert; Differenzfälle gegen eine im Test festgehaltene Eingabe-/Ausgabe-Tabelle des Vor-Split-Stands.

- **AC-7:** Given der Resolver wird mit einem Konfigurations-Dict aufgerufen / When der Aufruf beendet ist / Then wurde weder das Dict verändert noch eine Datei gelesen oder geschrieben, und die neuen Felder des View-Models sind unveränderlich.
  - Test: tiefe Kopie vor/nach dem Aufruf verglichen, Attributzuweisung auf `outlook`/`hourly` schlägt fehl, Aufruf in einem Verzeichnis ohne Datenwurzel gelingt.

- **AC-8:** Given der Prüfkatalog aus Phase 1 (Orte-Fallliste Abschnitte AB/SV, Fälle `O-SV-*-H1-*` und `VO-14`, Trip-Fallliste `trip-paar-ausblick-*`) / When er nach der Änderung einzeln ausgeführt wird / Then bleibt er vollständig grün und die zugestellten Mails sind in HTML, Klartext und Kompakt zeichengleich zu den Golden-Dateien.
  - Test: `test_einstellung_gleich_mail_{trip,orte,fallliste,editor_standard,validatoren}.py` sowie `test_einstellung_gleich_auslieferung.py` einzeln, ohne Änderung der Golden-Dateien; Staging-Validatoren (`briefing_mail_validator.py`, `email_spec_validator.py`) gegen echt zugestellte Mail unverändert.

- **AC-9:** Given bestehende Aufrufer, die `MailViewModel` ohne `outlook` und `hourly` konstruieren oder die vier Kanal-Listen lesen / When der Code nach der Änderung läuft / Then arbeiten sie unverändert weiter, und die vier Kanal-Listen sowie `layout_channels` sind für alle bisherigen Testfälle gleich dem Stand von #3057.
  - Test: Konstruktion ohne die neuen Felder liefert `outlook is None` und `hourly is None`; `tests/tdd/test_3057_channel_list_resolver.py` und die #3057-Regression laufen unverändert grün.

- **AC-10:** Given ADR-0121 / When die Phase 2b ausgeliefert ist / Then enthält das ADR einen Nachtrag 2b mit dem Vokabular (Katalog-ID für `outlook`/`hourly`), dem None-Vertrag und dem Hinweis, dass die Abschaltflags `hourly_enabled` und `outlook_enabled` bewusst nicht Teil des View-Models sind, und der ADR-Index bleibt konsistent.
  - Test: `tests/test_adr_index_drift.py` grün; Nachtrag im ADR vorhanden (`# doc-compliance-test`, einziger Dokumentations-Check dieser Spec).

## Definition of Done

- AC-1 bis AC-10 durch benannte Tests grün; Prüfkatalog (AC-8) einzeln grün, Golden-Dateien unverändert.
- Mutations-Gegenprobe durch den Adversary: verfälschte ID-Stufe, verfälschte Formatabbildung, Ausblick-Schnitt gegen gekollabierten Stand, Entfernen der `None`-Unterscheidung. Jede Verfälschung lässt mindestens einen Test rot werden.
- Vor dem ersten Code gegen `origin/main` abgeglichen (#3067, #3048).
- Alle 6 CI-Checks grün, Staging-Verifikation und Prod-Selftest bestanden, zugestellte Staging-Mail unverändert.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_3065_*.py`: GIVEN Orte-Kombinationen None/`[]`/Liste/Totalschnitt WHEN Resolver THEN Ausblick-Liste gleich `resolve_compare_outlook_metrics` (AC-1)
- [ ] GIVEN Trip mit engem `channel_layouts.email` und Altbestand ohne `metrics` WHEN morning/evening THEN Ausblick gleich `resolve_trip_outlook_metrics` auf ungekollabiertem Stand (AC-2)
- [ ] GIVEN Format wahr/falsch/ohne/nicht fähig WHEN Resolver THEN `simplified`/`raw`/None/None (AC-3)
- [ ] GIVEN Stundenverlauf-Kombinationen inklusive `wind_direction` WHEN Resolver THEN `dp_field`(ID-Stufe) gleich `resolve_hourly_metrics`, `format` None (AC-4)
- [ ] GIVEN nie eingestellt und bewusst leer WHEN Resolver THEN None unterscheidbar von `()`, Trip-`hourly` immer None (AC-5)
- [ ] GIVEN Altfall-Eingabetabelle WHEN `resolve_hourly_metrics` THEN unverändert (AC-6)
- [ ] GIVEN Dict-Eingabe WHEN Resolver THEN Eingabe unverändert, kein Dateizugriff, View eingefroren (AC-7)
- [ ] GIVEN Prüfkatalog-Fixtures WHEN einzeln ausgeführt THEN grün (AC-8)
- [ ] GIVEN Konstruktion ohne neue Felder WHEN gelesen THEN Default None (AC-9)
- Orakel `tests/helpers/kanal_liste_orakel.py` ruft ausschließlich die echten Altfunktionen auf; keine Mocks, kein `patch`.
- Live-E2E: Staging-Mail-Validatoren gegen echt zugestellte Mail, Ergebnis unverändert.

## Out of Scope

- Speicherung bewusster Abwahl je Liste (Speicherformat, Go-Merge auf Unterschlüssel): #3082.
- Umstellung der Renderer und Aufrufer auf den Resolver, Roh/Einfach im Stundenverlauf (`O-SV-H/K-DARST`), Verhaltensänderung des nie eingestellten Orte-Stundenverlaufs, Entfernen der Altpfade: #3058.
- Lese-Endpoint für den Editor, Go-Proxy, Zwei-Nutzer-Test: #3066.
- Oberfläche der Editor-Karten: #3060.
- Abbildung der Abschaltflags `hourly_enabled` und `outlook_enabled` im View-Model.
- Jede Änderung der zugestellten Mail in irgendeinem Kanal.

## Affected Files

| Datei | Änderung | Beschreibung | LoC |
|-------|----------|--------------|-----|
| `src/services/channel_list_resolver.py` (Python-Core) | MODIFY | `MailViewModel` + `outlook`, `hourly` (Default None); `_trip_view` füllt `outlook`; `_compare_view` füllt beide | +60 |
| `src/output/renderers/compare_hourly_metric_ids.py` (Python-Core) | MODIFY | `resolve_hourly_metrics` in ID-Stufe und `dp_field`-Schritt zerlegt, Verhalten gleich | +15/-5 |
| `tests/helpers/kanal_liste_orakel.py` | MODIFY | Orakel für Ausblick und Stundenverlauf aus den Altfunktionen | +50 |
| `tests/tdd/test_3065_ausblick_stundenverlauf_resolver.py` | CREATE | Differenztest, Fixtures, Eingabe unverändert, kein Dateizugriff | +200 |
| `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md` | CREATE | diese Spec | Doku |
| `docs/adr/0121-kanonische-kanal-liste.md` | MODIFY | Nachtrag 2b | Doku |

## Known Limitations

- Bis #3058 existieren Altpfade und Resolver nebeneinander; der Differenztest ist die Klammer, das Orakel wird mit den Altpfaden gelöscht.
- Zwei Vokabulare bleiben bestehen (Katalog-ID für Ausblick/Stundenverlauf, Renderer-Kennung für Orte-Kanäle); Vereinheitlichung gehört zu #3058.
- Der Stundenverlauf trägt kein Roh/Einfach (`format` immer None).
- Ein nie eingestellter Orte-Stundenverlauf liefert weiter None (Renderer-Vorgabemenge), solange die Grundauswahl fehlt; die Verhaltensänderung gehört zu #3058.
- Abschaltflags (`hourly_enabled`, `outlook_enabled`) sind nicht Teil des View-Models; der Aufrufer schaltet wie bisher ab.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0121 (Nachtrag 2b)
- **Rationale:** Erweitert das kanonische Lese-Format um zwei Flächen-Listen. Die Schlüssel `outlook`/`hourly` waren in ADR-0121 Punkt 1 für #3065 reserviert; es wird keine bestehende Entscheidung still geändert, ein neues ADR ist nicht nötig.

## Changelog

- 2026-11-16: Initial spec created (Phase 2b, Issue #3065 von Epic #3047)
