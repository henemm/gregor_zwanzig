# Context: fix-1483-temp-gap-marker

## Request Summary
Issue #1483: In der Kurznachricht ist eine Datenlücke bei Temperatur-Kürzeln (`N`/`K`/`D`/`FN`/`FK`/`FD`) nicht von „geprüft, nichts über der Schwelle" unterscheidbar — beides zeigt `-`. Die Schwellwert-Kürzel (`R`/`PR`/`W`/`G`/`TH:`/`TH+:`) kennen dieselbe Unterscheidung bereits (`?` bei Lücke). Zuschnitt: die Temperatur-Schleife in `builder.py` an das bestehende `has_gap`-Signal anschließen — kein neuer Datenbedarf, reine Verdrahtungslücke — über einen kleinen gemeinsamen Helfer, damit die `-`→`?`-Regel nicht ein zweites Mal separat im Code steht.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/tokens/builder.py:120-142` | `_mk_metric()` — enthält die bestehende Regel `if value == "-" and has_gap: value = "?"` (Zeile 135-136), angewandt auf die Schwellwert-Schleife (R/PR/W/G/TH:/TH+:) |
| `src/output/tokens/builder.py:225-284` | `build_token_line()` — Temperatur-Schleife (Zeile 251-284) ruft `render_temperature(val)` direkt auf, ohne `has_gap` zu prüfen. Hier ist der Fix anzubringen |
| `src/output/tokens/metrics.py:70-74` | `render_temperature()` (alias `render_int`) — reine Zahl-oder-`-`-Formatierung, kennt `has_gap` bewusst nicht und soll es auch nicht kennen (wird auch für Wintersport-Ganzzahlen verwendet, `render_int`-Alias in Zeile 221 `builder.py`) |
| `src/output/tokens/dto.py:45` | `DailyForecast.has_data_gap: bool` — das Signal existiert bereits pro Tag |
| `src/output/renderers/sms_trip.py:351,461` | Setzt `has_data_gap` für `today` (Zeile 351) und `tomorrow` (Zeile 461) aus `notification_service.compute_has_gap()` — Datenquelle ist vorhanden und fließt bereits bis zu `NormalizedForecast.days[*]` |
| `tests/tdd/test_sms_unknown_on_missing_data.py` | Bestehende Testsuite zu #1328 — belegt aktuelles Verhalten für R/PR/W/G/TH:, wählt Temperatur-Kürzel bewusst ab (`_TEMPERATURE_OFF`), weil sie damals nicht am `?`-Verhalten teilnahmen. Direkte Vorlage für Fixtures/Aufrufmuster (`_error_segment`, `_regular_segment`, `compute_has_gap`, `SMSTripFormatter().format_sms()`) |
| `docs/specs/modules/fix_1482_th_plus_metrik_luecke.md` | Spec des strukturell identischen Vorgänger-Fixes (`TH+:` bekam dieselbe Anbindung) — Vorlage für AC-Formulierung |
| `docs/reference/sms_format.md` §2 „Bekannte Ist-Abweichungen" Punkt 1, §4 Zeile 353, Changelog 2.15/2.17 | Dokumentiert die Lücke bereits explizit als offene Ist-Abweichung inkl. exakter Codestelle — nach dem Fix zu streichen/nachzuziehen |

## Existing Patterns

- **Gap-Signal-Fluss:** `notification_service.compute_has_gap()` → `has_gap`-Parameter durch `format_sms()`/`SMSTripFormatter` → `NormalizedForecast.days[i].has_data_gap` → `build_token_line()`. Einziger Berechnungspunkt, wie in mehreren Docstrings (`sms_trip.py:177`, `narrow.py:207`) betont — der Fix darf diesen NICHT duplizieren, sondern nur den bereits vorhandenen Wert konsumieren.
- **Bereits gelöster Analogfall (#1482):** `TH+:` hatte exakt dieselbe Lücke (Regel existierte, aber `tomorrow.has_data_gap` wurde nicht durchgereicht) — der damalige Fix bestand darin, den vorhandenen `_mk_metric()`-Aufruf mit dem korrekten `has_gap`-Wert zu füttern, keine neue Logik. Strukturell identisch zu #1483, nur dass hier ein ganzer Zweig (die Temperatur-Schleife) nie an `_mk_metric()` angeschlossen war.
- **Metrik-Abwahl bleibt unabhängig:** `_visible(spec, rt)` entscheidet vor jeder Gap-Prüfung, ob ein Token überhaupt erscheint (Issue #1415). Der Gap-Fix darf diese Reihenfolge nicht umkehren — abgewählt bleibt "kein Token", nicht `?`.

## Dependencies
- **Upstream:** `has_data_gap` kommt fertig berechnet aus `notification_service.compute_has_gap()` — keine neue Datenquelle nötig.
- **Downstream (korrigiert per Bug-Intake):** `build_token_line()` wird von `sms_trip.py` (SMS, Zeile 524) und `cli.py` (Zeile 228, Debug-Konsument) genutzt. `narrow.py` (Telegram-Kurzform) konstruiert seine Token **parallel** und ruft `build_token_line()` NICHT auf — ist von diesem Fix nicht betroffen, anders als in der ursprünglichen Vermutung angenommen.
- **Isolation Wintersport:** `_wintersport()` (`builder.py:196-222`) nutzt denselben `render_int`/`render_temperature`-Alias, DARF aber durch den Fix kein `?` bekommen (Datenlücke bei Schnee/Lawine bleibt bewusst stumm). Strukturell sauber gelöst über einen gemeinsamen Helfer, den nur `_mk_metric()` und die Temperatur-Schleife aufrufen — `_wintersport()` bleibt unverändert.

## Existing Specs
- `docs/specs/modules/sms_unknown_on_missing_data.md` — Ursprungs-Spec zu #1328 (Grundregel).
- `docs/specs/modules/fix_1482_th_plus_metrik_luecke.md` — Vorgänger-Fix, engste Vorlage für Struktur/AC-Stil.

## Risks & Considerations
- **Reihenfolge Abwahl vs. Lücke:** Test muss beide Fälle trennen (Metrik abgewählt ⇒ kein Token, unabhängig von Lücke; Metrik gewählt + Lücke ⇒ `?`) — sonst nur zufällig erfüllt (Issue-Text fordert das explizit).
- **Echt-nichts-vorhergesagt bleibt `-`:** Muss von „Lücke" unterscheidbar bleiben (kein Wert, aber `has_gap=False` ⇒ weiterhin `-`).
- **Zeichenbudget:** `?` und `-` sind gleich lang, 160-Zeichen-Grenze unberührt — im Test belegen, nicht nur behaupten (Issue-Vorgabe).
- **Mutations-Gegenprobe Pflicht (CLAUDE.md):** Adversary muss den `?`-Zweig gezielt wirkungslos machen und zeigen, dass ein Test rot wird.
- **Dokupflege:** `docs/reference/sms_format.md` §2/§4/Changelog müssen nach dem Fix angepasst werden (Ist-Abweichung entfällt).

## Analysis

### Type
Bug (Verdrahtungslücke — Mechanismus existiert, ein Zweig war nie angeschlossen).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/tokens/builder.py` | MODIFY | Neuer kleiner Helfer `_gap_or(value, has_gap)` (extrahiert aus `_mk_metric()`-Inline-Zeile 135-136); `_mk_metric()` ruft ihn statt der Inline-Zeile; Temperatur-Schleife (Zeile 279-284) wrappt `render_temperature(val)` zusätzlich mit `_gap_or(..., today.has_data_gap)`. `_wintersport()` bleibt unverändert (nackter `render_int()`-Aufruf, keine Gap-Kopplung) |
| `tests/tdd/test_sms_unknown_on_missing_data.py` | MODIFY | `_TEMPERATURE_OFF` für die Gap-Fälle entfernen/anpassen, `?`-Erwartung für N/K/D/FN/FK/FD ergänzen, Negativ-Test für Wintersport-Symbole (bleiben Zahl-oder-`-`, nie `?`) |
| `docs/reference/sms_format.md` | MODIFY | §2 „Bekannte Ist-Abweichungen" Punkt 1 streichen, §4 Zeile ~353 nachziehen, Changelog-Eintrag ergänzen |

### Scope Assessment
- Files: 2 Code-Dateien + 1 Doku-Datei
- Estimated LoC: ~10-15 (Helfer + 2 Call-Sites) + ~20-30 (Testanpassung) — deutlich unter dem 250-LoC-Limit
- Risk Level: LOW — kein Signaturbruch, `?`/`-` gleich lang (Zeichenbudget unberührt), keine externen Call-Sites außerhalb `builder.py` betroffen, Telegram-Kurzform nicht berührt

### Technical Approach
Gemeinsamer Helfer `_gap_or(value: str, has_gap: bool) -> str` statt Signaturänderung an `render_temperature()`/`render_int` (Alias würde sonst jede Wintersport-Aufrufstelle zwingen, explizit `has_gap=False` mitzuschleppen — fehleranfällig). `_mk_metric()` und die Temperatur-Schleife rufen den Helfer auf; `_wintersport()` bleibt unangetastet — Isolation ist damit strukturell garantiert, nicht per Default-Parameter. Analog zu #1482 (Regel-Wiederverwendung statt Duplikation). Reihenfolge: (a) RED-Test erweitern, (b) Helfer einführen + in `_mk_metric()` einsetzen (reines Refactoring, kein Verhaltenswechsel), (c) Helfer in Temperatur-Schleife anwenden (eigentlicher Fix), (d) Negativ-Test Wintersport ergänzen.

### Dependencies
Keine neuen. `has_data_gap` ist bereits vorhanden und fließt bis `builder.py` durch (siehe oben).

### Open Questions
- [x] Zeigen N/K/D UND FN/FK/FD beide `?`? — Ja, Issue-Text nennt explizit alle sechs Kürzel.
- [x] Suche nach weiteren `"K-"`/`"D-"`-Assertions außerhalb der bekannten Testdatei: nur zwei Treffer, beide harmlos (`test_compare_sms_kuerzel.py:542` betrifft ein anderes Kürzel-Paar `D+`/`D-` im Ortsvergleich-Kontext; `test_token_builder.py:171` ist ein Kommentar, die zugehörige Regex matcht Ziffer/`-`/`?` gleichermaßen und testet keinen Gap-Fall). Keine weiteren Tests würden durch den Fix rot.
