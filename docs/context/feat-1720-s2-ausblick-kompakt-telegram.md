# Context: feat-1720-s2-ausblick-kompakt-telegram

<!-- Issue #1720 Scheibe 2 — Ausblick-Spaltenauswahl auf Kompakt-Mail und Telegram ausweiten -->
<!-- Gemessen 2026-08-17 gegen origin/main b66799c6. Alle Zeilenangaben aus dieser Messung. -->

## Request Summary

Scheibe 1 (#1720, PR #1840, live seit `9961b2cd`) hat die 3-Tages-Vorschau
katalog-getrieben gemacht — aber nur für HTML- und Klartext-Trip-Mail.
Kompakt-Mail und Telegram zeigen weiterhin ihre alten, fest verdrahteten
Felder, unabhängig davon, was der Nutzer im Abschnitt „3-Tages-Vorschau"
auswählt. ADR-0055 kündigt Scheibe 2 ausdrücklich an und schreibt vor:
**zuerst ein Charakterisierungstest des Ist-Zustands**, weil dort kein
Byte-Wächter existiert (`metric_output_matrix.md:237-243`).

## Der Ist-Stand, gemessen

### Die Zeilen-Daten liegen für alle vier Ausgabeorte bereits bereit

`trip_report_scheduler.py:2329` baut `multi_day_trend` EINMAL über
`build_outlook_row(..., trip_display_config=dc, report_type=report_type)`
und reicht dasselbe Ergebnis an alle vier Renderer weiter
(`trip_report_scheduler.py:1418,1433,1477`). Ist `outlook_metrics` gesetzt
(`metrics is not None` in `build_outlook_row()`, `outlook.py:588-652`),
trägt **jeder Stage-Eintrag bereits** `row["cells"]` (formatierte Zellwerte,
`outlook.py:635-644`) und `row["cell_bg"]` — Kompakt und Telegram müssten sie
nur lesen. Es gibt keinen fehlenden Datenabruf, nur eine fehlende
Darstellung.

### Zwei eigenständige, fest verdrahtete Renderer

| Ausgabeort | Datei | Was heute passiert |
|---|---|---|
| Kompakt-Mail | `src/output/renderers/email/compact.py:258-270` — Inline-Loop in `render_compact()` | `format_trend_tokens(stage)` liest die festen Rohfelder (`temp_str`, `precip_str`, `wind_str`) + `_compact_thunder_field()` (`compact.py:84-111`, eigener Gewitter-Helfer). Fünf feste Felder, kein Katalog-Bezug. |
| Telegram | `src/output/renderers/narrow.py:572-613` — `_outlook_lines(multi_day_trend)`, Aufruf in `render_telegram_bubbles()` bei `narrow.py:833-835` | Ebenfalls über `format_trend_tokens(stage)`, feste Zeile `weekday · temp · precip · wind · thunder`. Kein `metrics`/`dc`-Parameter, obwohl `render_telegram_bubbles()` selbst schon ein `dc:`-Kwarg besitzt (`narrow.py:639`) — nur nicht an `_outlook_lines()` durchgereicht. |

### Die Auflösung existiert bereits — nur zwei Aufrufstellen bekommen sie nicht

`trip_report.py:218-220` löst `outlook_metrics` bereits EINMAL aus dem
ungekollabierten Stand auf: `resolve_trip_outlook_metrics(_dc_uncollapsed,
report_type)`. Das Ergebnis geht als `render_email(outlook_metrics=…)`
(`trip_report.py:201-249`) — aber:

1. **`render_email()`'s `compact`-Zweig verwirft es.** `email/__init__.py:111-132`:
   der frühe Return bei `email_format == "compact"` ruft `render_compact(...)`
   auf und übergibt dabei **kein** `outlook_metrics=` — der Parameter fehlt
   im Aufruf komplett, obwohl `render_compact()` selbst (Signatur
   `compact.py:130-150`) über `**_ignored` sowieso jeden unbekannten Kwarg
   schluckt. Selbst wenn `outlook_metrics` gesetzt wäre, käme es nicht an.
2. **`render_telegram_bubbles()` bekommt gar keinen `outlook_metrics`-Aufruf.**
   `trip_report.py:290-309` ruft die Funktion mit `dc=_dc_telegram`,
   `multi_day_trend=effective_trend` — aber ohne `outlook_metrics=`. Die
   Auflösung passiert für Telegram nirgends; `_outlook_lines()` kennt den
   Parameter (`narrow.py:572`) gar nicht in ihrer Signatur.

**Das ist der zentrale Befund:** Scheibe 2 ist strukturell keine neue
Auflösung, sondern (a) zwei fehlende Durchreichungen + (b) zwei Renderer, die
zwischen Legacy-Feldern und `row["cells"]` umschalten müssen.

## Wiederverwendbare Bausteine (Compare, unverändert)

Dieselben Funktionen, die Scheibe 1 für HTML/Klartext genutzt hat, tragen
auch hier:

| Funktion | Datei | Zweck |
|---|---|---|
| `resolve_trip_outlook_metrics(dc, report_type)` | `compare_outlook_metric_ids.py:78-102` | Bereits vorhandene Auflösung + Schnitt gegen Grundauswahl — **keine neue Funktion nötig**, nur an zwei weiteren Stellen aufrufen |
| `outlook_columns(metrics)` | `compare_outlook_metric_ids.py:118-142` | Auswahl → geordnete Spalten mit deutschem Label |
| `format_outlook_value(value, column)` | `compare_outlook_metric_ids.py:145-` | Zellentext (Zahl/Ordinal/Enum) |
| `row["cells"]` / `row["cell_bg"]` | bereits in `multi_day_trend` enthalten | Liegt für alle vier Kanäle vor, sobald `outlook_metrics` beim Zeilenbau gesetzt war |

## Verhalten bei `[]` und `None` — muss dem HTML/Klartext-Muster folgen

HTML/Klartext lösen das über eine erweiterte Bedingung an der Aufrufstelle
(ADR-0055 Implementation Details Punkt 2): `if multi_day_trend and
_outlook_metrics != []:`. Kompakt (`compact.py:258`) und Telegram
(impliziert durch `narrow.py:833-835`) haben aktuell nur `if multi_day_trend:`
bzw. äquivalent — dieselbe Erweiterung fehlt dort und muss ergänzt werden,
sonst zeigt eine bewusst geleerte Auswahl (`outlook_metrics=[]`) dort weiter
die Legacy-Felder oder eine leere Überschrift ohne Zeilen.

## Hinweistext „Erscheint nur in der E-Mail" — wird für den Trip falsch

`CompareOutlookLayoutControls.svelte:181-183` zeigt den Hinweis
`outlook-email-hint`, geteilt zwischen Compare- und Trip-Einbindung. Für
**Compare** bleibt er richtig: `render_compare_telegram()`
(`comparison.py`) hat nie einen Ausblick-Block, nur `render_compare_email()`
zeigt ihn — bestätigt, kein Telegram-Ausblick-Renderpfad im
Compare-Code (`comparison.py`, `compare_html.py` enthalten keinen
Telegram-Ausblick-Aufruf). Für den **Trip** wird die Aussage mit Scheibe 2
falsch: die Auswahl wirkt dann auch in Kompakt-Mail und Telegram. Der Hinweis
muss kontextabhängig werden (Compare: unverändert stehen bleiben; Trip:
entfällt oder wird umformuliert) — S1 (AC-7) hatte ihn bewusst mit dem
Vermerk „bis Scheibe 2" für den Trip übernommen.

## Fehlender Wächter (der Befund, der die Testplanung bestimmt)

Es gibt für Kompakt-Mail- und Telegram-Ausblick **keinen** Byte-Golden-Test
— bestätigt durch Grep: `test_issue_729_render_compact_empty.py`,
`test_issue_1001_telegram_bubbles.py`, `test_channel_metric_matrix.py`
decken andere Aspekte ab, keiner den heutigen Ist-Zustand des
Ausblick-Blocks byte-genau. `test_trip_outlook_parity.py` ruft ausschließlich
`render_outlook_table()`/`render_outlook_plain()` (den HTML/Klartext-Pfad)
auf — Kompakt/Telegram nie. **Vor jeder Änderung an `compact.py`/`narrow.py`
muss deshalb zuerst ein Charakterisierungstest den heutigen Legacy-Zustand
(`outlook_metrics=None`) festschreiben**, sonst gibt es keinen Beleg, dass
Scheibe 2 den Altbestand nicht verändert hat.

## Betroffene Dateien (Schätzung)

| Datei | Änderung |
|---|---|
| `src/output/renderers/email/__init__.py` | `outlook_metrics=outlook_metrics` in den `render_compact(...)`-Aufruf (Zeile ~112-131) ergänzen |
| `src/output/renderers/email/compact.py` | `render_compact()`-Signatur um `outlook_metrics` erweitern; `if multi_day_trend:`-Block (Zeile 258-270) auf Katalog-Zweig umstellen, analog `outlook.py`s Spaltenbau |
| `src/output/renderers/narrow.py` | `_outlook_lines()`-Signatur um `outlook_metrics` erweitern, Katalog-Zweig ergänzen; `render_telegram_bubbles()` reicht `outlook_metrics` durch |
| `src/output/renderers/trip_report.py` | `outlook_metrics=resolve_trip_outlook_metrics(_dc_uncollapsed, report_type)` an den `render_telegram_bubbles(...)`-Aufruf (Zeile 290-309) ergänzen — für `render_email()` bereits vorhanden, muss dort nur noch bis zum `compact`-Zweig durchdringen |
| `frontend/src/lib/components/shared/CompareOutlookLayoutControls.svelte` | Hinweistext „Erscheint nur in der E-Mail" für Trip-Kontext entfernen/umformulieren |
| **neu:** ein Charakterisierungstest für Kompakt+Telegram-Ausblick (Legacy) | Golden/Byte-Vergleich vor jeder Änderung |
| **neu:** Wirkort-Test analog `test_trip_outlook_dispatch_mail.py` für Kompakt+Telegram | Katalog-Auswahl bis in die zugestellte Kompakt-Mail/Telegram-Bubble verfolgt |

## Offene Fragen für die Spec

1. **Reihenfolge/Format der Kompakt-Zeile bei aktiver Auswahl** — heute feste
   Feldbreiten (`f"{weekday:<3} {name:<26} ..."`). Mit variabler Spaltenzahl
   (1 bis N gewählte Größen) muss ein Format ohne feste Breiten pro Spalte
   entstehen. Vorschlag: Label-Wert-Paare durch Trenner, analog wie
   `outlook_columns()` es für die Spaltenköpfe liefert — Details in der Spec.
2. **Telegram-Zeilenformat** analog — heute `weekday  temp  precip  wind
   thunder` mit `_wrap()` auf Prosa-Breite. Bei Katalog-Auswahl müssen die
   Spalten-Labels (aus `outlook_columns()`) mit erscheinen (die feste Zeile
   trägt heute keine Labels, nur Werte — bei freier Auswahl unklar ohne
   Beschriftung, welche Zahl was ist).
3. **`[]`-Fall in Kompakt/Telegram**: Soll wie HTML/Klartext die Überschrift
   „Naechste Etappen" (Kompakt) / „Ausblick" (Telegram) ganz entfallen, wenn
   `outlook_metrics == []`? (Ja, analog AC-4 aus S1 — zur Bestätigung in der
   Spec aufnehmen.)
4. **Hinweistext-Formulierung** für den Trip-Kontext nach Scheibe 2: ganz
   entfernen oder durch nichts ersetzen (da jetzt alle vier relevanten Kanäle
   erreicht werden — SMS/Premium-SMS bleiben weiterhin baulich unerreichbar,
   aber das war nie Teil des Hinweises).

## Nicht betroffen

- SMS/Premium-SMS — bleiben baulich unerreichbar (`sms_trip.py` kennt
  `multi_day_trend` nicht, unverändert seit ADR-0055).
- Ortsvergleich — `resolve_outlook_metrics()`, `comparison.py`,
  `compare_html.py` bleiben unangetastet.
- `report_config.show_outlook`-Semantik — unverändert, einziger Ein/Aus-Schalter.
- Persistenzformat `display_config.outlook_metrics` — unverändert, Scheibe 1
  hat Lesen/Schreiben bereits vollständig verdrahtet.
