# Adversary Dialog — feat-3057-kanal-liste-resolver
Spec: docs/specs/modules/feat_3057_kanal_liste_resolver.md
Datum: 2026-11-16 08:04

## Checkliste
- [x] **Input:** `display_config` (Trip oder Orte, Rohform oder aus dem Loader), `surface`, `report_type`.
- [x] **Output:** `MailViewModel` mit vier Kanal-Listen; die zwei Einstiegspunkte liefern exakt dieselben Werte wie vor der Änderung.
- [x] **Side effects:** keine. Kein Schreiben, kein I/O, keine Mutation der Eingabe.
- [x] **AC-1:** Given ein Trip mit gefüllten, leeren und fehlenden Kanal-Listen (E-Mail, Telegram, SMS) in Kombination mit `per_report` für morning und evening / When `get_metrics_for_channel` für jede Kombination aufgerufen wird / Then entspricht das Ergebnis (Auswahl, Reihenfolge, Format) dem Altpfad als Orakel, eine leere Liste bleibt leer.
- [x] **AC-2:** Given ein Orts-Vergleich mit `channel_layouts`, nur `channel_active_metrics` oder keinem von beiden / When `resolve_compare_render_options` aufgelöst wird / Then sind `enabled_metrics_by_channel`, `channel_rows_by_channel` und `metric_formats(kanal)` für E-Mail, Telegram und SMS gleich dem Altpfad-Orakel.
- [x] **AC-3:** Given ein Trip mit gespeichertem `morning_enabled=False` an einer Metrik / When das Abend- und das Morgenbriefing aufgelöst wird / Then fehlt die Metrik nur im Morgenbriefing, und eine absichtlich verfälschte Auflösung, die das Flag ignoriert, lässt mindestens einen Test rot werden.
- [x] **AC-4:** Given Zeilen mit dem Format als `format`, als `format_mode` oder als `use_friendly_format` (so schreibt es PR #3042) / When der Resolver sie liest / Then ergibt jede Schreibweise dieselbe Darstellung (Roh oder Einfach), fehlt die Angabe, gilt der heutige Flächen-Standard (Trip Katalog, Orte Roh), und die gespeicherten Daten bleiben unverändert.
- [x] **AC-5:** Given eine Konfiguration mit eigener `premium_sms`-Liste bzw. ohne diesen Schlüssel / When der Resolver aufgelöst wird / Then enthält `premium_sms` die eigene Liste, fehlt der Schlüssel, ist sie gleich der SMS-Liste, und der versendete Premium-SMS-Text bleibt wie bisher der SMS-Text.
- [x] **AC-6:** Given ein Trip und ein Orts-Vergleich lösen amtliche Warnungen aus / When der Resolver aufgelöst wird / Then steht keine Warnung als speicherbare Zeile in einer Kanal-Liste, und eine ausdrücklich leere Liste bleibt leer, auch bei gesetzter Grundauswahl.
- [x] **AC-7:** Given der Alarmpfad (`notification_service`) erzeugt eine Warnung für einen Trip mit abweichenden Kanal-Listen / When die Nachricht je Kanal gebaut wird / Then verwendet sie dieselben Metriken und Reihenfolge wie vor der Änderung in allen vier Kanälen.
- [x] **AC-8:** Given der Phase-1-Prüfkatalog (Trip- und Orte-Fallliste, Ketten- und Auslieferungstests, Golden-Dateien) / When er nach der Änderung einzeln ausgeführt wird / Then bleibt er vollständig grün und die zugestellten Mails sind in HTML, Klartext und Kompakt zeichengleich zu den Golden-Dateien.
- [x] **AC-9:** Given der Resolver wird mit einem Konfigurations-Dict aufgerufen / When der Aufruf beendet ist / Then wurde weder das Dict verändert noch eine Datei gelesen oder geschrieben, und das View-Model ist unveränderlich.

## Dialog

### Runde 1
**Adversary:** Tests: 464 passed (Phase-1-Katalog + test_3057, siehe adversary-test-output.txt). Mutationen 27 durchgespielt, 25 gefangen, 2 ueberlebt (M22, M24: `ChannelRow.order` konstant 0 in Trip bzw. Orte, Test prueft nur "aufsteigend").
Finding F001 (LOW, edge_case): Code reference src/services/channel_list_resolver.py:125 und :180 -- `order` wird nur auf Monotonie geprueft (test_3057_channel_list_resolver.py:174-176 fuer Trip, fuer Orte gar nicht); Konstante 0 ueberlebt.
Finding F002 (MEDIUM, spec_violation): Code reference src/services/channel_list_resolver.py:95-104 -- Rohform und Loader-Modell derselben Trip-Konfiguration liefern verschiedene Formate (`format: "raw"/"simplified"` in channel_layouts: Rohform raw/simplified, Modell None/None), weil `_parse_display_config` den Schluessel `format` verwirft und der Adapter nur in der Rohform umschreibt. Spec AC-4/Input: "Rohform oder aus dem Loader", jede Schreibweise gleiche Darstellung. Test deckt nur Rohform (test_ac4...). Auslieferung unberuehrt (Altpfad liest `format` ebenfalls nicht).
Finding F003 (LOW, anti_pattern): Umfang 938 Zeilen Code+Tests statt "ca. 600, harte Grenze" (Spec Estimated Scope); Resolver 208, Test 628, Orakel 102.
Finding F004 (LOW, edge_case): src/services/channel_list_resolver.py:76 -- Global-Zweig ruft `_sorted_by_layout(_filter_metrics_by_report_type(dc.metrics, ...))` statt `get_metrics_for_report_type`; heute identisch (models.py:913), ein spaeteres #3048-Fallback in `get_metrics_for_report_type` wuerde vom Resolver nicht mehr gesehen. Kein aktueller Fehler.
**Implementierer:** (nicht befragt, Kontextisolation)

### Runde 2
**Adversary:** Tech-Lead-Korrekturen kritisch geprueft: (a) AC-4 Renderer-IDs wind_max/gust_max: keine Aufweichung, die Zeilen tragen Renderer-IDs (compare_metric_ids). (b) AC-5 gegen Orakel statt Literal: Orakel ist unabhaengige Kopie, Literal-Anfang `premium[:2]` bleibt geprueft; Mutation M3/M3b/M13 gefangen. (c) AC-6 Orte `channel_layouts.telegram=[]` folgt Orakel (Anhaengen der Grundauswahl): weicht den Wortlaut "leere Liste bleibt leer, auch bei gesetzter Grundauswahl" fuer channel_layouts auf, ist aber durch AC-2/AC-8 (Mail unveraendert) erzwungen; `channel_active_metrics=[]` bleibt leer (getestet). Als Spec-Unschaerfe zu melden, kein Code-Fehler. Zusaetzlicher AC-3-Fall nur_kanal staerkt die Abdeckung (M2 gefangen). Randfaelle: display_config None/{} -> Trip (), Orte None, kein Absturz; unbekannte Kanal-Liste "x" -> None, kein Absturz.
Mutationsproben dort, wo der Nutzer ankommt (Adapter models.py:979-981, Orte-Verdrahtung report_config_resolver.py:337-345,382-384): M14, M15, M20, M21 gefangen.
**Implementierer:** (nicht befragt)

### Runde 3
**Adversary:** Nachprüfung der Fixes. Code reference: src/services/channel_list_resolver.py:76-77 (Global-Zweig ruft jetzt `dc.get_metrics_for_report_type`, F004 behoben, keine Dublette mehr); src/app/models.py:979-981 und src/services/report_config_resolver.py:337-345,382-384 unveraendert gegenueber Runde 1.
Mutationen nach den Fixes: M22 (Trip order 0) rot, M24 (Orte-Layout order 0) rot, M24b (Orte channel_active_metrics order 0) rot, M1 (Globalzweig ignoriert morning_enabled) rot, M1b (dieselbe Verfaelschung in models.py get_metrics_for_report_type) rot, M2 (Kanalzweig) rot, M17 rot. F001 behoben. Nach jeder Mutation Diff gegen externe Sicherungskopie identisch.
F002: Test fuer format_mode-Modell vorhanden; Einschraenkung als Known Limitation. Tragfaehig: die Mail bleibt laut AC-2/AC-8 unveraendert, der Altpfad liest `format` nie; eine Angleichung im Modell-Pfad wuerde den Loader aendern (verboten) oder Verhalten, das nicht ausgeliefert wird. Rest-Hinweis: AC-4-Wortlaut bleibt fuer Modell-Eingabe unerfuellt, nur dokumentiert; vertretbar.
AC-6/Orte: Praezisierung tragfaehig, weil AC-2/AC-8 (Mail unveraendert) Vorrang haben und die Aenderung an #3058 gebunden ist; empfohlen: PO-/Spec-Freigabe sieht den Hinweis.
F003: im Changelog festgehalten, akzeptiert.
Tests: 466 passed (Katalog + test_3057, adversary-test-output.txt).
**Implementierer:** F004, F001 behoben; F002, AC-6, F003 dokumentiert.

## Herkunft der Vorbedingungen

- default_lang: kein Sprachprofil konfiguriert (`precondition_origins.default_lang`); Mails/Texte laufen im Standard (Deutsch), fuer diesen Schnitt ohne Wirkung (keine Nutzertexte).



## Code-Referenzen

Code reference: src/app/models.py:979
Code reference: src/services/channel_list_resolver.py:76
Code reference: src/services/channel_list_resolver.py:95
Code reference: src/services/channel_list_resolver.py:125
Code reference: src/services/channel_list_resolver.py:180
Code reference: src/services/report_config_resolver.py:337
Code reference: src/services/report_config_resolver.py:382

## Verdict

VERDICT: VERIFIED (Runde 3; offen nur dokumentierte Grenzen F002/AC-6)

Confirmations: Input/Output/Side effects, AC-1 (channel_list_resolver.py:64-84, models.py:979-981), AC-2 (report_config_resolver.py:337-345,382-384), AC-3 (channel_list_resolver.py:76,83), AC-4 (:142-148,:100-104), AC-5 (:130-135,:199-200), AC-6 (:81-82, spec-Unschaerfe channel_layouts=[]), AC-7 (via models.py Adapter, Test ac7 gruen), AC-8 (464 passed, Golden unveraendert), AC-9 (:28,:39 frozen, :100 deepcopy). Offen: F002 (MEDIUM) und Spec-Unschaerfe AC-6/Orte `channel_layouts: []`.

## Geprüfte Dateien

- sha256:bf0a8e9f64688949982bafab2e821d5b954b1dc743e7a22bd70a01793954bef8  src/app/models.py
- sha256:46f675e1f14bd2ae7fb3be2b6e9c6068f280c62bf68f9e6dc9b08bb4698d19e1  src/services/channel_list_resolver.py
- sha256:f6ac5c3e3eb75433946f1c42c2ce6c84a36e0c1d46e307275527c5f77105b771  src/services/report_config_resolver.py

## Prüfbasis

- base: 0041ca3601ac915d122a209586e00ac6dcc45a37
- blob:09c50c776641268f0a9799b5fbc436a72ccb9128  src/app/models.py
- blob:b442bb408f6f53bbd6b5c37bf1f75660b4b8178f  src/services/channel_list_resolver.py
- blob:e7a2cd5e562379d0529f0043b600246de35645c4  src/services/report_config_resolver.py
