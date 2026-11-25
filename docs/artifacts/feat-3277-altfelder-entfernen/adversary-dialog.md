# Adversary Dialog — feat-3277-altfelder-entfernen
Spec: docs/specs/modules/feat_3277_altfelder_entfernen.md
Datum: 2026-11-25 08:20

## Checkliste
- [x] **Input:** Laden, Rendern und Speichern von Trips und Ortsvergleichen, auch mit Bestandsdateien, die noch Altfelder tragen.
- [x] **Output:** Jede Ausgabe in allen vier Kanälen ist zeichengleich zum Stand vor dem Rückbau. Gespeicherte Dateien enthalten nach einem Python-Speichern keinen der zehn Namen mehr.
- [x] **Side effects:** Beim Speichern über Python verschwinden vorhandene Altfelder aus der Datei; alle anderen Felder bleiben unverändert (Merge). Es gibt keinen Datenlauf über Bestandsdaten.
- [x] **AC-1:** Given ein Trip und ein Ortsvergleich mit Tabelle, einmal ohne und einmal mit gesetzten Altfeldern (alle zehn Namen) im Eingang / When das Briefing in E-Mail (HTML und Text), Telegram, SMS und Premium-SMS erzeugt wird / Then ist die Ausgabe jedes Kanals zeichengleich, und sie ist zeichengleich zum bisherigen Golden-Stand.
- [x] **AC-2:** Given ein gespeicherter Trip und ein gespeicherter Ortsvergleich, deren Datei noch Altfelder in `display_config`, `report_config` und auf oberster Ebene trägt / When sie geladen und über den Speicherpfad erneut gespeichert werden / Then enthält die gespeicherte Datei keinen der zehn Namen mehr, und alle übrigen Felder (auch unbekannte Zusatzfelder, `placements`, Empfänger, Orte) sind unverändert erhalten.
- [x] **AC-3:** Given Modell und Lader nach dem Rückbau / When ein Abo mit Altfeldern geladen wird / Then trägt das Modellobjekt keine Attribute `multi_day_trend_reports`, `show_outlook`, `outlook_metrics`, `outlook_metric_formats`, `per_channel_layouts`, `per_report_layouts`, und die Alt-Werte beeinflussen weder Anzeige noch Rendern.
- [x] **AC-4:** Given zwei verschiedene Nutzer mit je einem Trip und einem Ortsvergleich mit Altfeldern in den Dateien / When für Nutzer A gespeichert wird / Then sind nur A's Dateien bereinigt, B's Dateien sind byteweise unverändert, und die Speicherung nutzt die echte `user_id` (nie `"default"`).
- [x] **AC-5:** Given die E-Mail-Renderer (HTML und Text) / When sie ohne Parameter `show_outlook` aufgerufen werden / Then erscheint der Ausblick genau dann, wenn `placements.outlook_reports` Berichte nennt, und fehlt bei leerer Liste; die Signatur der Funktionen enthält `show_outlook` nicht mehr.
- [x] **AC-6:** Given Ortsvergleiche mit und ohne `rows` / When die Tabelle über Karte, Briefing und Grundauswahl aufgelöst wird / Then gibt es keinen Parameter und keine Lesestelle `outlook_enabled` mehr (Resolver, Placements-View, `placements_aus_grundauswahl`, Soll-Hook, Go-Modell), und das Ergebnis ist für alle Bestandsabos mit `outlook_enabled=true` unverändert; die Tabelle eines Abos ohne `rows` trägt `outlook_reports` nach Grundauswahl.
- [x] **AC-7:** Given der Feldnamen-Wächter `tests/test_altfeld_namen_sperre.py` / When er Backend-Code (`src`, `api`, `internal`, `cmd`, `.claude/hooks`, `scripts`) prüft / Then findet er keinen der zehn Namen außer den Einträgen der ERLAUBT-Tabelle, jeder Eintrag trägt Grund (mindestens 20 Zeichen) und Ablaufdatum.
- [x] **AC-8:** Given der Import-Wächter `tests/test_altpfad_import_sperre.py` / When er den Produktionscode prüft / Then enthalten `VERBOTEN` zusätzlich `resolve_hourly_metric_formats` (und `normalize_outlook_metric_formats`, falls gelöscht), und kein Produktionscode importiert oder ruft sie auf.
- [x] **AC-9:** Given das Request-Schema der Validator-Vorschau mit `hourly_metrics`/`hourly_metric_formats` / When die Entscheidungsregel aus Implementation Details Schritt 6 angewendet wird / Then bleibt das Schema mit begründetem ERLAUBT-Eintrag, wenn es nur Request-Parameter ohne Store-Bezug ist, andernfalls ist es auf die Tabelle umgestellt und die Felder sind entfernt; in beiden Fällen liefert die Vorschau dieselbe Mail wie zuvor.
- [x] **AC-10:** Given die Skripte `migrate_2454_derived_children.py`, `backfill_display_config_issue111.py` und `send_gate_test_mails.py` / When der Rückbau abgeschlossen ist / Then sind die beiden Einmal-Skripte gelöscht (oder mit Aufrufer-Nachweis in der Spec-Notiz begründet behalten), und `send_gate_test_mails.py` baut seine Test-Abos mit `placements` und enthält keinen der zehn Namen.
- [x] **AC-11:** Given Tests, die bisher Altfelder als Fixtures setzten / When sie auf `placements` umgestellt sind / Then bleibt die Kernschicht (Python-Dateien einzeln benannt, `go test ./...`) grün, und es wurde kein Test nur gelöscht, um Rot zu vermeiden (Löschung nur bei gelöschten Funktionen).

## Dialog

### Runde 1
**Adversary:**
Testlauf (37 benannte Dateien, ca. 1500 Tests, Ausgabe adversary-test-output.txt) alle gruen; `go test ./internal/...` ok.
Confirmation AC-1/AC-3:
Confirmation AC-2/AC-4:
Confirmation AC-5:
Confirmation AC-6:
Confirmation AC-7/8/9/10/11: Waechter gruen (tests/test_altfeld_namen_sperre.py, tests/test_altpfad_import_sperre.py: VERBOTEN enthaelt resolve_hourly_metric_formats); beide Einmal-Skripte geloescht; geloeschte Tests gehoeren zu geloeschten Skripten bzw. geloeschter Persistenz-Funktion. Status: CONFIRMED
Mutationen (String-Ersetzung, Sicherungskopie im Scratchpad, danach identisch zurueck): M1 altfelder_entfernen(merged) -> pass: GEFANGEN (ac2 x2, ac4). M2 _rmw_compare_preset ohne Entfernung: GEFANGEN. M3 Name aus ALTFELDER gestrichen: GEFANGEN (5 Tests inkl. Waechter). M4 html outlook_active invertiert: GEFANGEN (test_briefing_parity_night_thunder; die 3277-Suite allein faengt sie NICHT). M4b Stabilitaetsbedingung: GEFANGEN. M4c plain outlook_state-Zweig: GEFANGEN. M5 Zusatzfeld/placements verloren, report_config nicht bereinigt: je GEFANGEN. M6 user_id auf "default" (Vergleich und Trip): GEFANGEN. M7 Grundauswahl outlook_reports leer: GEFANGEN. M8 compare outlook_enabled fest True: GEFANGEN (nur 1 Test).
**Implementierer:** keine Rueckmeldung noetig


#### Code-Referenzen (gegen aktuellen Stand geprueft)
Code reference: src/app/models.py:799 (AC-3, Modell ohne Altfelder)
Code reference: src/app/loader.py:142 (AC-2, ALTFELDER)
Code reference: src/app/loader.py:150 (AC-2, altfelder_entfernen)
Code reference: src/app/loader.py:2102 (AC-2/AC-4, nach Merge)
Code reference: src/services/scheduler_dispatch_service.py:573 (AC-2/AC-4, Vergleich-Speichern)
Code reference: src/output/renderers/email/html.py:1198 (AC-5, Ausblick ohne show_outlook)
Code reference: src/output/renderers/email/plain.py:382 (AC-5, outlook_state-Zweig ohne show_outlook)
Code reference: src/output/renderers/trip_report.py:328 (AC-3, Telegram-Konfiguration ohne Kanal-Ebenen)
Code reference: src/output/renderers/email/__init__.py:1 (AC-5, Renderer-Bundle)
Code reference: src/output/renderers/compare_outlook_metric_ids.py:25 (AC-8, Alt-Resolver entfernt)
Code reference: src/services/report_config_resolver.py:299 (AC-6, outlook_enabled aus View-Model)
Code reference: src/services/channel_list_resolver.py:61 (AC-6, resolve_channel_lists ohne outlook_enabled)
Code reference: src/services/placements_view_service.py:195 (AC-6, erstanlage_placements)
Code reference: src/services/placements_view_service.py:217 (AC-6, _tabelle_aufloesen)
Code reference: src/services/placements.py:292 (AC-6, Grundauswahl-outlook_reports)
Code reference: .claude/hooks/_soll_aus_konfiguration.py:483 (AC-6, ausblick_briefings ohne outlook_enabled)
Code reference: internal/model/compare_preset.go:67 (AC-6, Go-Feld entfernt)

### Runde 2
**Adversary:**
Nachbohren: (a) Wirkungsort: Speicherpfade (save_trip/update_trip ueber _write_trip_locked, Vergleich ueber _rmw_compare_preset, save_location schreibt frisch) sind mit echten Dateien getestet. (b) Abo ohne rows mit outlook_enabled=false zeigt den Ausblick jetzt (vorher unterdrueckt): von Spec Schritt 3 gedeckt (Prod alle true), kein Finding. (c) Go-Speichern entfernt Altfelder nicht: Spec-Entscheidung. (d) Feldnamen-Waechter prueft nur Speicher-Schluessel (Tech-Lead-Entscheidung 25.11.): laut Spec zulaessig. (e) M4 nur ausserhalb der 3277-Suite gefangen.
Finding F001: Severity LOW, Category edge_case,
Spec requirement: AC-5. Conflict: keiner, Gesamtmenge faengt M4. Remediation: keine noetig.
**Implementierer:** zur Kenntnis

## Herkunft der Vorbedingungen

Vorbedingungen (Bestandsdateien mit Altfeldern, zwei Nutzer, tmp_path-Datenverzeichnis) erzeugen die Tests selbst; keine fremden Zustaende.

## Verdict

VERDICT: VERIFIED
Tests: ca. 1500 Python-Tests (37 Dateien) und go test ./internal/... gruen; 12 Mutationen, alle gefangen. Findings: F001 (LOW, kein Handlungsbedarf).

## Geprüfte Dateien

- sha256:38da8a54d5b332574d7afbf2d554271d995490d76f2e9237d215a30b5f100de7  src/app/loader.py
- sha256:06d7c7941994de2a760c13ce777decedd9a2dd91d7e087ec97f7e81d296fa377  src/app/models.py
- sha256:2872b90d3fd11f401ecc26bb66106fe27067de9f015ca851190235577edc4d23  src/output/renderers/compare_outlook_metric_ids.py
- sha256:8e554659bdd37dcaf54b276c8fc0b7b57f431780e5dbb5a345d033540cb7ee13  src/output/renderers/email/__init__.py
- sha256:996794e1e91330b43d51831512325e57464241b2df550ad83c38b782427af9ed  src/output/renderers/email/html.py
- sha256:9e6a2da4ae4e8d00c35b68e560754844e410969f4f9c5e09b71c66ee6927fd93  src/services/placements.py
- sha256:dbbe616708ef212eb817290729f21a2950f2142f5789c2f82d6666af57244081  src/services/report_config_resolver.py

## Prüfbasis

- base: da6991ed96414993dcab4ba9e5857f20c82b5c8c
- blob:e8fc4bf7d215560e9557f2dd2871e41306aa60ec  src/app/loader.py
- blob:b3a85e477b4e413cd6e3c6a70eedcf7134f3567e  src/app/models.py
- blob:462c6c54f5f8d74148d4769e5703804a0712706e  src/output/renderers/compare_outlook_metric_ids.py
- blob:58815e879c707a6bd3a3e78d78776320f79bf108  src/output/renderers/email/__init__.py
- blob:085b4560071e8ad334f43b1591e45e28dbef8789  src/output/renderers/email/html.py
- blob:8893e7c9465ec306f0594dc550d6e4d4821e564c  src/services/placements.py
- blob:f6b86bf1ede69adc70836f5d7c4dd5b67b536ca4  src/services/report_config_resolver.py

## Geprüfte Dateien

- sha256:ae66b72b6065c323a4e9799a25260bc21705a042cb2a0850a901c3a34bd41cc8  .claude/hooks/_soll_aus_konfiguration.py
- sha256:6ccbd43b844c728d9258a77768c737cb81f07b13cd86f7380795a2a9b3355717  internal/model/compare_preset.go
- sha256:38da8a54d5b332574d7afbf2d554271d995490d76f2e9237d215a30b5f100de7  src/app/loader.py
- sha256:06d7c7941994de2a760c13ce777decedd9a2dd91d7e087ec97f7e81d296fa377  src/app/models.py
- sha256:2872b90d3fd11f401ecc26bb66106fe27067de9f015ca851190235577edc4d23  src/output/renderers/compare_outlook_metric_ids.py
- sha256:8e554659bdd37dcaf54b276c8fc0b7b57f431780e5dbb5a345d033540cb7ee13  src/output/renderers/email/__init__.py
- sha256:996794e1e91330b43d51831512325e57464241b2df550ad83c38b782427af9ed  src/output/renderers/email/html.py
- sha256:c87eca4a5f0676c9915f5decde51694e64cbba836133676608f7a862f406781a  src/output/renderers/email/plain.py
- sha256:3fcee59a3ffa93d565d75566dc78b07762f770d336f2554ee8c12bb1da846d59  src/output/renderers/trip_report.py
- sha256:4035deb043732020f37e8ea1925c244e716b257085472bf08f3f91e2ca28caaf  src/services/channel_list_resolver.py
- sha256:9e6a2da4ae4e8d00c35b68e560754844e410969f4f9c5e09b71c66ee6927fd93  src/services/placements.py
- sha256:76419766cbffc39d412075668d85b410b8ba304e6e00527a3596d129b9897093  src/services/placements_view_service.py
- sha256:8f611f499965bfcd4630fe1feb83260c85fbb481a1e4bef30e303fc200812b07  src/services/report_config_resolver.py
- sha256:aee75a87340495429383471120251f84d7588cdd56bac7f1c1c091a7902777ec  src/services/scheduler_dispatch_service.py

## Prüfbasis

- base: ff4a0329238b2b378a34262fc62581eae3489b48
- blob:b1a8c007b8e9109295e0c6dcd430931786315209  .claude/hooks/_soll_aus_konfiguration.py
- blob:cc43f26f15772159f727d72049c7c2977b246932  internal/model/compare_preset.go
- blob:e8fc4bf7d215560e9557f2dd2871e41306aa60ec  src/app/loader.py
- blob:b3a85e477b4e413cd6e3c6a70eedcf7134f3567e  src/app/models.py
- blob:462c6c54f5f8d74148d4769e5703804a0712706e  src/output/renderers/compare_outlook_metric_ids.py
- blob:58815e879c707a6bd3a3e78d78776320f79bf108  src/output/renderers/email/__init__.py
- blob:085b4560071e8ad334f43b1591e45e28dbef8789  src/output/renderers/email/html.py
- blob:3707ddfe3bd84bc78d10834e33ee1589eb43578a  src/output/renderers/email/plain.py
- blob:a3fe577fa729374e13579dad261ff4165d46b09b  src/output/renderers/trip_report.py
- blob:2930aa532070c7369a5b53ebad869caf8a111543  src/services/channel_list_resolver.py
- blob:8893e7c9465ec306f0594dc550d6e4d4821e564c  src/services/placements.py
- blob:4ca39eede88618fd572d09f5bd50c8ec53f16efc  src/services/placements_view_service.py
- blob:6d9da3bcc06b620d4d8ab14f0c3923733be9b64d  src/services/report_config_resolver.py
- blob:f6b11c5035c48dca19b62c3583e49159ec348ef7  src/services/scheduler_dispatch_service.py
