---
entity_id: i18n_p12_python_ratsche_rest_2751
type: module
created: 2026-11-03
updated: 2026-11-03
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2751, python]
---

# i18n P12: Restabbau der Python-Ratsche (Allowlist schrumpft)

**Issue:** #2751 · **Epic:** #2644 · **Folge von:** #2674 (AC-6) · **Grundsatz:** ADR-0104, `docs/reference/i18n_konventionen.md`

## Approval

- [x] Approved (PO-Freigabe 2026-11-03, an Claude delegiert)

## Purpose

Die Python-Ratsche `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` meldet nach #2674 noch
15 Dateien mit 47 Funden. Dieses Paket baut alles ab, was ohne das Renderer-Commit-Gate (#811) möglich
ist: echte Nutzertexte wandern in den Katalog (de byte-gleich, en nach Glossar), Log- und
Entwicklermeldungen tragen `# i18n-log`, und Texte, die nach einer bestehenden Entscheidung sprachfest
bleiben (Eigennamen, SMS-Kanal, Bot-Menü laut P7 #2669), tragen die neue begründete Markierung
`# i18n-fest: <Grund>`. Die Allowlist schrumpft; leer wird sie erst mit dem Renderer-Gate-Rest.

## Source

- `tests/test_i18n_keine_hartkodierten_nutzertexte_python.py` — Marker `# i18n-fest: <Grund>` (Grund ≥ 10 Zeichen)
- `src/output/renderers/compare_hourly_metric_ids.py` — `HOURLY_EXCLUSION_REASON` aus dem Katalog, `hourly_exclusion_reason(metric_id, lang)`
- `src/output/renderers/compare_metric_catalog.py` — `get_compare_metric_catalog(lang="de")`; Assert-/Fehlertexte `# i18n-log`
- `api/routers/compare.py` — `GET /api/compare/metrics?lang=de|en` (optional, sonst `de`)
- `src/i18n/messages/{de,en}/vergleich.json` — `vergleich.stunden.ausschluss.*`
- `src/output/renderers/fallback_notice.py` — tote deutsche Werte entfernen (Texte stehen bereits in `mail.fallback.*`)
- `src/output/channels/telegram.py` — `BOT_COMMANDS` mit `# i18n-fest` (bleibt deutsch, P7 #2669 Known Limitations)
- `src/output/renderers/comparison.py` (SMS), `text_report/__init__.py` (Debug-CLI), `compare_metric_ids.py`, `compare_outlook_metric_ids.py` (Logs) — Markierungen

## Implementation Details

- Die Ratsche nimmt Literale in Zeilen mit `# i18n-fest: <Grund>` aus, wenn der Grund mindestens 10 Zeichen hat. Ohne Grund wirkt der Marker nicht. `# i18n-log` bleibt für Log-, Assert- und Debug-Ausgaben.
- `HOURLY_EXCLUSION_REASON` bleibt ein Wörterbuch mit deutschen Werten (Struktur: drei Literal-Schlüssel plus Schleifen-Nachtrag, bewacht von `test_metrik_listen_register_ratchet.py`); die Werte kommen aus `t(<schlüssel>, "de")`. Die Schleife nutzt zwei ganze Sätze (`tagesrichtung_temperatur`, `tagesrichtung_gefuehlt`) statt Satzbau aus Teilstücken.
- `get_compare_metric_catalog(lang)` setzt nur `hourlyNotSelectableReason` sprachabhängig; Schlüssel, Kennungen und alle anderen Felder bleiben unverändert. Ohne `lang` ist die Antwort byte-gleich zum bisherigen Stand.
- Der Endpunkt ist statisch und ohne Nutzerbezug; die Sprache kommt als Query-Parameter. Ungültige Werte ergeben `de`. Das Frontend reicht den Parameter noch nicht mit (Known Limitations).

## Acceptance Criteria

**AC-1:** Given der Ortsvergleich-Metrikkatalog, When er ohne Sprache oder mit `lang="de"` abgefragt wird, Then ist `hourlyNotSelectableReason` für jede stündlich ausgeschlossene Größe byte-gleich zum bisherigen deutschen Text (z. B. Sonnenstunden: „Stuendlich nur als Einstrahlung (W/m²) verfuegbar, …").

**AC-2:** Given der Ortsvergleich-Metrikkatalog, When er mit `lang="en"` abgefragt wird (Funktion oder `GET /api/compare/metrics?lang=en`), Then trägt jede stündlich ausgeschlossene Größe eine nicht leere englische Begründung ohne Umlaute, und alle anderen Felder sind identisch zur deutschen Antwort.

**AC-3:** Given `GET /api/compare/metrics` mit einem unbekannten `lang`-Wert, When die Antwort kommt, Then ist sie identisch zur deutschen Antwort (Rückfall `de`, kein Fehler).

**AC-4:** Given eine Datei mit einem Literal in einer Zeile mit `# i18n-fest: Eigenname des Anbieters`, When die Ratsche läuft, Then zählt das Literal nicht als Fund; mit `# i18n-fest` ohne oder mit zu kurzem Grund zählt es weiter.

**AC-5:** Given die Herkunfts-Vertretung im Briefing, When `build_fallback_lines` mit Ersatzmodell und Metrikliste in `de` und `en` aufgerufen wird, Then sind die Zeilen unverändert zum bisherigen Stand (Rohwert bei unbekannter Kennung, „gröbere Auflösung" bzw. „coarser resolution" beim groben Modell).

**AC-6:** Given der Repo-Stand nach diesem Paket, When `python tests/test_i18n_keine_hartkodierten_nutzertexte_python.py --messen` läuft, Then bleiben nur Funde in Dateien unter dem Renderer-Commit-Gate (`src/output/renderers/alert/*`, `email/*`, `trip_report.py`), und die Allowlist enthält genau diese Dateien mit ihrer Fundzahl.

## Known Limitations

- **Renderer-Gate-Rest:** `alert/{hours,model,official_alerts,project}.py`, `email/{html,thunder_branch}.py` und `trip_report.py` brauchen für jeden Commit den Modus-Matrix-Test und einen Validator-Lauf gegen echt zugestellte Staging-Mail. Beides ist in der Entwicklungsumgebung ohne Zugang zum Staging-Postfach nicht herstellbar; das Gate wird nicht umgangen. `test_allowlist_ist_leer` bleibt `xfail(strict=True)`.
- **Bot-Menü:** `BOT_COMMANDS` bleibt deutsch mit den englischen Zusatzbefehlen (Entscheidung P7 #2669, Known Limitations: botweit, keine Sprache je Nutzer ohne Chat-Scope; `prod_selftest.py` liest das Literal per `ast.literal_eval`). Eine Sprachwahl je Chat bräuchte eine eigene Spec.
- **Frontend:** `CompareHourlyLayoutControls.svelte` zeigt die Begründung weiter aus der Antwort ohne `lang`; das Mitgeben der Sprache im Loader ist ein Frontend-Folgeschritt.

## Changelog

- 2026-11-03: Erstfassung (#2751)
