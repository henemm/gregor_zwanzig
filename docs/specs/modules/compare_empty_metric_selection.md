---
entity_id: compare_empty_metric_selection
type: bugfix
created: 2026-07-26
updated: 2026-07-26
status: draft
version: "1.0"
tags: [compare, shared, metrics, leerauswahl, bugfix]
---

<!-- Issue #1366 + #1361 Befund 3 — S3 Scheibe B von Epic #1372 (Kind von Dach-Epic #1374) -->

# Leerauswahl heißt leer (Ortsvergleich, Übersicht + Stundenverlauf)

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich bedeutet eine bewusst leere Metrik-Auswahl heute versehentlich
„alle Metriken" — das genaue Gegenteil der Nutzereingabe (#1366). Ebenso werden
unauflösbare Stundenverlauf-Kennungen stillschweigend verworfen und durch die
volle Standardmenge ersetzt, ohne jede Rückmeldung (#1361 Befund 3). Diese
Spec stellt für beide Auflöser die schon im Projekt formulierte Regel her
(`src/services/compare_alert.py:237-248`):

> Feld fehlt = Altbestand → bisheriges Verhalten (alle Größen).
> Feld vorhanden, auch leer = bewusste Nutzerwahl → wird geehrt.

## Source

- **File:** `src/output/renderers/compare_metric_ids.py` — `resolve_enabled_metrics()`
- **File:** `src/output/renderers/compare_hourly_metric_ids.py` — `resolve_hourly_metrics()`
- **File:** `src/services/report_config_resolver.py` — `resolve_compare_render_options()`
- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` — `buildNewComparePresetPayload()`
- **File:** `frontend/src/lib/components/compare/compareHourlyMetricDefs.ts` — `applyHourlyMetricToggle()`

## Estimated Scope

- **LoC:** ~90–130 netto
- **Files:** 5 Quell- + 4 Testdateien
- **Effort:** medium (zentrale Auflöser, vier Ausgabewege hängen dran; entschärft
  durch: keine Bestandsdaten betroffen, Renderer setzen die Zielbedeutung
  bereits korrekt um)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_enabled_metrics()` (`compare_metric_ids.py`) | intern (MODIFY) | Übersichts-Auflöser — Kern des Fixes |
| `resolve_hourly_metrics()` (`compare_hourly_metric_ids.py`) | intern (MODIFY) | Stundenverlauf-Auflöser — Kern des Fixes, bekommt erstmals Logging |
| `resolve_compare_render_options()` (`report_config_resolver.py`) | intern (MODIFY) | einzige Aufrufstelle beider Auflöser (`:238/239`) — bildet leere/unauflösbare Stundenauswahl auf `hourly_enabled=False` ab |
| `_visible_metrics`, `_visible_hour_metrics` (`compare_html.py`) | intern (bestehend, unverändert) | unterscheiden bereits korrekt `None` (alle) von `[]` (keine) — tragen schon |
| `_ordered_rows` (`comparison.py`) | intern (bestehend, unverändert) | „Eine leere Liste bleibt leer" (AC-8 aus #1359) — trägt schon |
| `buildNewComparePresetPayload()` (`compareEditorSave.ts`) | intern (MODIFY) | F1 — Neuanlage muss `[]` explizit senden statt den Schlüssel wegzulassen |
| `applyHourlyMetricToggle()` (`compareHourlyMetricDefs.ts`) | intern (MODIFY) | F2 — Umschalter darf aus echter Leerauswahl nicht die Vorgabemenge materialisieren |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | Gate | greift, weil `comparison.py`/`compare_html.py` zu den Renderer-Dateien zählen — Pflicht-Nachweis vor Commit |
| `.claude/hooks/email_spec_validator.py` | Gate | Compare-Mail-Validator gegen echt zugestellte Staging-Mail; Zeilen `:380-386` verlangen je Ort „Zeit + mindestens 1 Wert-Spalte" — Grund für die `hourly_enabled=false`-Lösung statt einer leeren Spaltenliste |

## Implementation Details

### 1. Übersichts-Auflöser: `is None` statt Falsy-Check (P1/P1b)

`resolve_enabled_metrics()` prüft heute `if not active_metrics: return None` —
das fängt sowohl „Feld fehlt" (`None`) als auch „bewusst leer" (`[]`) im
selben Zweig ab. Zielverhalten: nur `None` (Feld fehlt) löst den
Altbestands-Rückfall aus; `[]` durchläuft die Funktion regulär und liefert
`[]` zurück. Zweite Stelle: `return resolved or None` am Ende verwandelt eine
zwar vorhandene, aber komplett unauflösbare Auswahl (alle IDs unbekannt)
wieder in `None` — das wird zu `return resolved` (kann `[]` sein). Der
bereits bestehende `isinstance(..., list)`-Defensiv-Check und die
Warn-Protokollierung bei unauflösbaren IDs (`:157-164`) bleiben unverändert
erhalten.

### 2. Stundenverlauf-Auflöser: gleiche zwei Stellen (P2/P2b) + neues Logging

`resolve_hourly_metrics()` hat die identische Bauart (`if not hourly_metrics`
/ `resolved or None`) und bekommt denselben Fix. Zusätzlich: das Modul
importiert heute kein `logging` — unauflösbare Kennungen verschwinden
kommentarlos. Analog zum Übersichts-Auflöser wird ein `logger.warning(...)`
ergänzt, sobald mindestens eine übergebene Kennung nicht in
`FRONTEND_TO_HOURLY_METRIC_ID` auftaucht (unabhängig davon, ob am Ende noch
andere Spalten übrig bleiben oder nicht).

### 3. Report-Config-Resolver: leere/unauflösbare Stundenauswahl → Block entfällt

`resolve_compare_render_options()` (`:238/239`) ruft beide Auflöser als
einzige Aufrufstelle in der gesamten Produktion auf — ein Eingriff hier wirkt
vollständig und gleichzeitig auf alle Ausgabewege, die diese Config lesen.
Würde `resolve_hourly_metrics()` nach Punkt 2 ein leeres `[]` direkt an den
HTML-Renderer durchreichen, entstünde eine Stundentabelle mit nur der
Zeit-Spalte — das lässt der Pflicht-Validator (`:380-386`) je Ort
durchfallen. Deshalb bildet der Resolver ein leeres Auflösungsergebnis auf
das bereits existierende Top-Level-Feld `hourly_enabled` ab: ist
`resolve_hourly_metrics(...)` gleich `[]` (bewusste Leerauswahl **oder**
komplett unauflösbare Auswahl — beide Fälle sind nach Punkt 2 nicht mehr von
`None` unterscheidbar, was hier auch nicht nötig ist), wird der bestehende,
vom Preset gelesene `hourly_enabled`-Wert zusätzlich mit `False` verundet.
Ein Nutzer, der `hourly_enabled` selbst bereits ausgeschaltet hat, ist davon
unberührt (bleibt `False`). `compare_html.py` prüft `hourly_enabled`, bevor
es `hourly_metrics` überhaupt liest (`:1128/1138/1144`) — ein zusätzlich
durchgereichtes leeres `hourly_metrics` ist damit folgenlos.

### 4. F1 — Neuanlage schreibt `[]` ausdrücklich

`buildNewComparePresetPayload()` (`compareEditorSave.ts`) lässt den
`active_metrics`-Schlüssel bei leerer Auswahl heute komplett weg
(`fields.activeMetricKeys.length > 0 ? {...} : {}`), wodurch die bewusste
Leerauswahl beim allerersten Speichern in „Feld fehlt" kippt. Der
Bearbeiten-Pfad (`:102-121`) schreibt `[]` bereits korrekt und unbedingt.
Die Neuanlage wird auf dasselbe Muster gezogen: `active_metrics` wird immer
gesetzt (`toStoredActiveMetrics(fields.activeMetricKeys)`), auch wenn das
Ergebnis eine leere Liste ist.

### 5. F2 — Stundenverlauf-Umschalter materialisiert keine Vorgabemenge mehr

`applyHourlyMetricToggle()` (`compareHourlyMetricDefs.ts:59-73`) baut bei
leerer aktueller Auswahl (`currentKeys.length === 0`) heute erst die volle
`DEFAULT_HOURLY_METRIC_KEYS`-Menge auf und wendet danach den Toggle an — ein
Klick aus „nichts" erzeugt „Vorgabe minus eins" statt „genau die eine
angehakte Spalte". Die Materialisierung entfällt; der Toggle arbeitet direkt
auf der übergebenen (ggf. leeren) Liste.

## Expected Behavior

- **Input:** Ortsvergleich mit `display_config.active_metrics` bzw.
  `display_config.hourly_metrics` in einem von drei Zuständen: Feld fehlt
  (Altbestand), Feld ist `[]` (bewusste Leerauswahl), Feld enthält
  Kennungen, die sich teilweise oder vollständig nicht auf bekannte
  Renderer-IDs abbilden lassen.
- **Output:** Vergleichs-Mail (HTML + Klartext), Telegram-Nachricht und SMS
  respektieren „Feld fehlt → alle" und „Feld leer/unauflösbar → keine"
  identisch für alle vier Kanäle (Übersicht). Für den Stundenverlauf gilt das
  identisch für HTML- **und** Klartext-Teil derselben Mail — Telegram und SMS
  kennen weiterhin keine Stundenspalten (Staging-Verifikation 2026-07-26
  falsifiziert die frühere Annahme „HTML-only, da nur dieser Kanal
  Stundenspalten kennt": der Klartext-Teil zeigte den Stundenblock bis zum
  Fix F003 unabhängig von Auswahl/Schalter).
- **Side effects:** Neues `logger.warning` beim Stundenverlauf-Auflöser für
  unauflösbare Kennungen; keine Datenmigration, keine Änderung an
  Bestandsverhalten für Presets ohne gespeicherte Auswahl.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Ortsvergleich alle Wettergrößen der
  Übersichtstabelle bewusst abgewählt (gespeichert als leere Liste) / When
  die Vergleichs-Mail für ihn erzeugt und zugestellt wird / Then enthält die
  zugestellte Mail in der Übersichtstabelle keine einzige Wettergrößen-Zeile
  mehr — nur die Zeile der amtlichen Warnungen bleibt stehen, weil sie nicht
  an der Metrik-Auswahl hängt.

- **AC-2:** Given ein Nutzer hat eine Metrik-Auswahl gespeichert, die sich
  beim Rendern auf keine einzige bekannte Wettergröße mehr abbilden lässt
  (z. B. nach einer Katalog-Änderung) / When die Vergleichs-Mail erzeugt
  wird / Then zeigt die Übersichtstabelle ebenfalls keine Wettergrößen-Zeile
  — genau wie bei bewusster Leerauswahl (AC-1), nicht wie bisher alle
  Wettergrößen bei gleichzeitig widersprüchlicher Protokollmeldung.

- **AC-3:** Given ein Ortsvergleich, für den noch nie eine Metrik-Auswahl
  gespeichert wurde (das Feld fehlt in der Konfiguration ganz) / When für
  ihn die Vergleichs-Mail erzeugt wird / Then zeigt die Übersichtstabelle
  weiterhin alle Wettergrößen wie vor dieser Änderung — nur „bewusst leer",
  nicht „Feld fehlt", ändert hier sein Verhalten.

- **AC-4:** Given ein Nutzer hat im Ortsvergleich alle Stundenverlauf-Spalten
  bewusst abgewählt (gespeichert als leere Liste) / When die Vergleichs-Mail
  erzeugt wird / Then enthält die zugestellte Mail für keinen Ort mehr einen
  Stundenverlauf-Block — weder Kopfzeile noch Tabelle — statt einer Tabelle,
  die nur noch die Uhrzeit-Spalte zeigt.

- **AC-5:** Given ein Nutzer hat im Stundenverlauf mehrere Kennungen
  angehakt, die sich ALLE nicht auf bekannte Spalten abbilden lassen / When
  die Vergleichs-Mail erzeugt wird / Then entfällt der Stundenverlauf-Block
  für alle Orte vollständig — genau wie bei bewusster Leerauswahl (AC-4),
  nicht die bisherigen neun Spalten.

- **AC-6:** Given ein Nutzer hat im Stundenverlauf mehrere Kennungen
  angehakt, von denen mindestens eine (aber nicht alle) sich nicht auf eine
  bekannte Spalte abbilden lässt / When die Vergleichs-Mail erzeugt wird /
  Then zeigt der Stundenverlauf-Block nur die auflösbaren Spalten in der
  gewählten Reihenfolge, UND es entsteht eine Protokollmeldung mit den
  unauflösbaren Kennungen — statt die Abweichung stillschweigend zu
  übergehen (#1361 Befund 3).

- **AC-7:** Given ein Nutzer legt einen neuen Ortsvergleich an und wählt im
  Wetter-Metriken-Tab bewusst alle Größen ab, bevor er zum ersten Mal
  speichert / When der neue Vergleich angelegt wird / Then wird diese
  bewusste Leerauswahl tatsächlich übernommen (nicht als „nie eingestellt"
  verworfen) — die erste Vergleichs-Mail für diesen neuen Vergleich zeigt
  entsprechend keine Wettergrößen-Zeile in der Übersichtstabelle.

- **AC-8:** Given ein Nutzer hat im Stundenverlauf-Tab zuvor bewusst alle
  Spalten abgewählt / When er anschließend genau eine einzelne Spalte wieder
  anhakt / Then ist danach ausschließlich diese eine Spalte aktiv — nicht
  die komplette bisherige Vorgabemenge abzüglich der zuletzt abgewählten
  Spalte.

- **AC-9:** Given ein Ortsvergleich mit bewusst leerer Wettergrößen-Auswahl
  in der Übersicht (wie AC-1) / When der Vergleich per E-Mail (HTML- und
  Klartext-Teil derselben Mail), Telegram und SMS an die konfigurierten
  Empfänger verschickt wird / Then zeigt keiner der vier Ausgabewege eine
  Wettergrößen-Zeile bzw. -Zelle für diesen Vergleich — die Regel gilt
  einheitlich für alle Kanäle, weil `resolve_enabled_metrics()` die einzige
  Weiche für alle vier ist. Für den Stundenverlauf (AC-4/AC-5) gilt seit Fix
  F003 dieselbe Einheitlichkeit für HTML **und** Klartext derselben Mail —
  Telegram/SMS rendern grundsätzlich keine Stundenspalten (unverändert, kein
  Fehlerpfad, da `_CHANNEL_METRICS` dort ausschließlich Übersichtswerte
  kennt). Die frühere Formulierung „Stundenverlauf betrifft ausschließlich
  die HTML-Mail" war durch den Staging-Fund vom 2026-07-26 widerlegt: der
  Klartext-Teil zeigte den Stundenblock unabhängig von Auswahl/Schalter.

## Invarianten

Vier Eigenschaften, die dieser Eingriff nicht brechen darf:

1. **Reihenfolge** = Erstvorkommen in der Auswahl (#1335/#1359) — bestimmt
   Zeilenfolge in Mail und Telegram und über das SMS-Budget, *welche*
   Größen die SMS überhaupt erreichen. Geschützt durch die bestehende
   `compare_metric_order`-Testsuite, die unverändert grün bleiben muss.
2. **Entdopplung** auf die Renderer-Kennung, erstes Vorkommen gewinnt
   (`dict.fromkeys`-Muster in beiden Auflösern bleibt erhalten).
3. **Gemischte Speicherformate** in derselben Liste (Zeichenkette alt +
   Objekt neu, #1373 Restrisiko R1) — der `_to_key()`-Normalisierungsschritt
   in `resolve_enabled_metrics()` bleibt unverändert, nur die beiden
   Rückgabestellen ändern sich. Geschützt durch
   `test_compare_active_metrics_dual_format.py`.
4. **Kein Absturz** bei beliebigem Fremd-Inhalt (Nicht-Liste, `int`,
   `None`-Einträge) — die defensiven `isinstance`-Prüfungen bleiben in
   beiden Auflösern erhalten, nur der Rückgabewert am Ende ändert sich.

## Abgrenzung

Nicht in dieser Scheibe:

- **#1361 Befund 2** und **#1368** (konfigurierbarer 3-Tages-Ausblick) →
  Scheibe A.
- **#1378** (zwei Zeitbasen) → Scheibe C.
- **Trip-Seite**, gleiche Fehlerklasse, anderes Speicherformat (Auswahl =
  Liste mit `enabled`-Flags, fällt auf eine fest verdrahtete Siebener-Liste
  zurück) → eigenes Ticket **#1394**.
- **Sammel-Einträge aus dem Aufmaß** (Kommentar an #1199): `corridors or
  None` (`report_config_resolver.py:241`, gleiche Bauart bei den
  Wertebereichen), der tote Prüfzweig im Mail-Validator (`:339-343`), zwei
  auseinanderlaufende Stände desselben Vergleichs (Alt-Ablage vs.
  `briefings/`).

## Test Plan

Test-Politik (CLAUDE.md „Zwei Schichten"): Kern-Tests deterministisch ohne
Netz/Live-Dienste sind Pflicht und müssen 100 % grün sein; der Nachweis aus
Nutzersicht kommt zusätzlich aus der Live-Schicht (echte Staging-Mail per
IMAP, Marker `X-GZ-Mail-Type: compare`). Keine neuen Testdateien mit
Issue-Nummer im Namen (Namensregel).

### Bestandstests, die „leer → alle" festschreiben und mitgezogen werden müssen

- `tests/unit/test_compare_metric_order.py:426-430` —
  `test_empty_active_metrics_preset_is_flattened_to_none_issue_1366`,
  markiert `xfail(strict=True)`. Schlägt nach dem Fix als XPASS fehl — das
  ist der eingebaute Umstellungs-Trigger; Marker entfernen, Test wird zum
  regulären GRÜN-Nachweis.
- `tests/tdd/test_issue_1104_compare_config_foundation.py:54-58` —
  `test_empty_list_returns_none` erwartet `resolve_enabled_metrics([]) is
  None`. Erwartung auf `== []` ändern.
- `tests/unit/test_compare_active_metrics_dual_format.py:213-220` —
  `test_empty_selection_returns_none_exactly_as_before`, verweist im
  Docstring selbst auf #1366. Erwartung auf `== []` ändern.
- `tests/tdd/test_issue_1106_hourly_metrics_config.py:137-141` —
  `test_empty_list_returns_none` (Stundenverlauf-Pendant). Erwartung auf
  `== []` ändern.

### Unverändert grün bleiben muss

- `tests/unit/test_compare_metric_order.py:393-398` —
  `test_preset_without_active_metrics_uses_default_order`: Feld fehlt ganz
  → bleibt bei „alle Größen" (AC-3). Nicht anfassen.

### Neue Kern-Tests (Ergänzung der bestehenden Suiten, keine neue Datei mit Issue-Nummer)

- Renderer-Ebene: komplett unauflösbare, aber nicht-leere Auswahl →
  `resolve_enabled_metrics([...nur unbekannte IDs])` liefert `[]`, nicht
  `None` (AC-2).
- Stundenverlauf-Auflöser: komplett unauflösbare Auswahl → `[]` (AC-5);
  teilweise unauflösbare Auswahl → auflösbare Teilmenge + `caplog`-Nachweis
  der Warnung (AC-6).
- `report_config_resolver`: leere bzw. komplett unauflösbare
  `hourly_metrics` → `CompareRenderOptions.hourly_enabled is False`,
  unabhängig vom gespeicherten `hourly_enabled`-Feld, solange dieses nicht
  bereits `False` war (AC-4/AC-5 auf Config-Ebene).
- Frontend: `buildNewComparePresetPayload()` mit leerem
  `activeMetricKeys` → Payload enthält `display_config.active_metrics: []`,
  nicht fehlenden Schlüssel (AC-7).
- Frontend: `applyHourlyMetricToggle([], key, true)` → Ergebnis ist genau
  `[key]`, nicht Vorgabemenge minus zuletzt abgewählter Spalte (AC-8).

### Live-E2E (Staging, Pflicht vor „E2E bestanden")

- Vergleichs-Preset mit bewusst leerer Übersichts-Auswahl anlegen, echte
  Vergleichs-Mail an Test-Postfach auslösen, per IMAP abrufen, mit
  `email_spec_validator.py` prüfen: Übersichtstabelle zeigt nur die
  Warn-Zeile (AC-1/AC-9).
- Vergleichs-Preset mit bewusst leerer Stundenverlauf-Auswahl: zugestellte
  Mail enthält für keinen Ort einen Stundenverlauf-Block, und der
  Pflicht-Validator (`:380-386`) läuft für diesen Teil regulär durch, weil
  die Sektion strukturell fehlt statt eine ungültige Tabelle zu zeigen
  (AC-4).

## Known Limitations

- Die Unterscheidung „bewusst leer" vs. „komplett unauflösbar" geht auf
  Ebene der Auflöser verloren (beide liefern `[]`) — das ist beabsichtigt,
  weil sich beide Fälle für den Renderer identisch verhalten sollen (AC-2,
  AC-5). Nur die Protokollmeldung (AC-6) unterscheidet noch, *warum* eine
  Kennung fehlt.
- Der Stundenverlauf-Block kann nach dieser Änderung entfallen, obwohl der
  Nutzer `hourly_enabled` selbst nie ausgeschaltet hat — das ist die
  bewusste PO-Entscheidung vom 2026-07-26 (eine Tabelle nur mit
  Uhrzeit-Spalte hat keinen Nutzwert und wäre durch den Pflicht-Validator
  ohnehin nie zustellbar).
- Trip-Seite bleibt bis Ticket #1394 in derselben Fehlerklasse.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe korrigiert zwei Auflöser auf die Bedeutung,
  die die Renderer bereits umsetzen, und nutzt für den Stundenverlauf ein
  bereits existierendes Konfigurationsfeld (`hourly_enabled`) — keine neue
  Architektur-, Datenmodell- oder Persistenzentscheidung, kein neuer Kanal,
  keine Schema-Änderung.

## Changelog

- 2026-07-26: Initial spec erstellt — Issue #1366 + #1361 Befund 3, S3
  Scheibe B von Epic #1372.
