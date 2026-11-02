# Context: fix-1670-mail-formatdetails

## Request Summary
#1670 "Formatdetails Trips E-Mail": (a) mobil fehlen Leerzeichen in den Pillen des Metriken-Überblicks ("Max16:00", "km/hab 15:00·", "stärkste14:00"); (b) fünf übertragene Grammatik-Befunde (C5-04, 07, 13, 30, 66).

## Hauptbefund (a) — belegt
- `src/output/renderers/email/helpers.py:1392` `pill_html`: `display:inline-flex;align-items:center`. Mobile Mail-Apps machen die Uhrzeit zu einem eigenen Element (im Screenshot unterstrichen); in einem Flex-Container fällt das Leerzeichen zwischen Textknoten und Element weg. Die Quelltexte enthalten die Leerzeichen (`helpers.py:1483,1565`: "ab HH:00 · …", "· Max HH:00").
- Vermuteter Fix: `inline-block` statt `inline-flex` (Analyse bestätigt; Desktop ist laut Ticket OK).
- Aufrufer: `html.py:1294-1302` (`build_metrics_summary_pills` → `pill_html`). Weitere `pill_html`-Nutzer in der Analyse prüfen.

## Die fünf Grammatik-Befunde — Stand gegen aktuellen Code
| ID | Stand |
|----|-------|
| C5-04 Uhrzeit `@4` vs `04:00` | `@{hour}` steht in `src/output/tokens/metrics.py:86-126` (SMS-Token-Notation, gewollt). Ob der HTML-Ausblick sie zeigt, ist in der Analyse zu klären. |
| C5-07 Compare-Preset `outlook_metrics`, Label-Wert-Zweig ohne Onset | `outlook.py` (Zeile ~331 verschoben), in der Analyse prüfen |
| C5-13 EM DASH vs EN DASH in der Compare-Mail | belegt: `compare_html.py:172-194` "—", `narrow.py:89` "–" |
| C5-30 Wind aus Etappenaggregat, Böen aus rohen Samples | `outlook.py:272-275` (hourly_gust), `:627` (wind_max_kmh); ungemessen |
| C5-66 zwei `TH`-Kürzel | vermutlich erledigt: #2417 AC-27 hat Warn-Kürzel auf `TS` umgestellt (`hazard_symbols.py:15-21`); Rest-`TH` nur noch ThunderLevel |

## Existing Patterns / Specs
- Specs: `docs/specs/modules/email_metrics_summary_664.md`, `email_redesign_613.md`, `fix_2136_outlook_col_label.md`
- Referenz: `docs/reference/mail_validators.md`, `renderer_email_spec.md`

## Dependencies / Dependents
- Upstream: `metrics.py`-Token-Renderer, `get_metric(...).col_label`
- Downstream: Trip-Mail HTML (`html.py`), Compare-Mail (`compare_html.py`), `briefing_mail_validator.py`

## Risks & Considerations
- Renderer-Commit-Gate: Modus-Matrix-Test + `briefing_mail_validator` (Exit 0) gegen echte Staging-Mail nötig.
- Compare-Mail-Änderungen (C5-13, C5-07) brauchen zusätzlich `email_spec_validator.py`.
- Mobile Darstellung: Gegenprobe nur über echten Mail-Client; der Test muss das Verhalten (kein Flex-Container um Textknoten) prüfen, nicht nur eine CSS-Zeichenkette.
- Befunde, die schon erledigt sind, werden im Ticket abgehakt, nicht neu gebaut.

## Analysis

### Type
Bug (Teil a: mobile Darstellung) + Sammel-Nachprüfung von fünf Grammatik-Befunden (Teil b).

### Befund gegen aktuellen Code
| Teil | Stand | Konsequenz |
|------|-------|------------|
| (a) Pillen ohne Leerzeichen mobil | Ursache belegt: `helpers.py:1392` `pill_html` = `display:inline-flex`; Pillen stehen in einem Flex-Container (`html.py:1304`, `display:flex;gap:6px`). Mobile Mail-Apps machen die Uhrzeit zum eigenen Element, im Flex-Container fällt das Leerzeichen am Textknoten-Rand weg. Quelltext hat die Leerzeichen (`helpers.py:1483`). | FIX: Pille auf `display:inline-block` (Textfluss statt Flex). Container mit `gap` bleibt (Pillen sind dort Flex-Items, unkritisch). Einziger Aufrufer von `pill_html`: `html.py:1302`. |
| C5-04 `@4` vs `04:00` | `@{hour}` ist SMS/Telegram-Token-Notation (`tokens/metrics.py`), gewollt kompakt; Pille nutzt `HH:00`. Kanal-Notationen, kein Mail-Fehler. | Ticket-Punkt als „gewollt/kanalbedingt" abhaken. Nur falls der HTML-Ausblick `@4` zeigt, wäre es ein Fix. In Phase 3 per Test am gerenderten Ausblick gegenprüfen. |
| C5-07 Compare-Ausblick Label-Wert-Zweig ohne Onset | `outlook.py` Datei referenziert `outlook_metrics` nur noch im Trip-Pfad (Z.568-608); Compare-Zweig liegt in `compare_outlook_metric_ids.py`. Nicht abschließend gemessen. | Offen: in Phase 3 mit realer Compare-Konfiguration messen; sonst als erledigt/nicht reproduzierbar abhaken. |
| C5-13 EM DASH vs EN DASH Compare-Mail | belegt: `compare_html.py:170-194` `_fmt_*` liefern „—", `compare_outlook_metric_ids.py:492` und `narrow.py:89` liefern „–". | FIX: ein Platzhalter-Zeichen (SSoT-Konstante, EN DASH wie Trip-Mail/Ausblick `outlook.py`). |
| C5-30 Wind (Etappenaggregat) vs. Böen (rohe Samples) | `outlook.py:272-275` Böen = max über `hourly_gust`, Wind = `wind_kmh` (Aggregat). Ungemessen, fachliche Frage (Fenster). | Nicht blind ändern: erst messen, ob Böen > Etappenfenster möglich sind. Entweder Messung + Fix oder begründet abhaken. |
| C5-66 zwei `TH`-Kürzel | `hazard_symbols.py:15`: #2417 AC-27 hat Warn-Kürzel auf `TS` umgestellt; `TH` nur noch ThunderLevel. | ERLEDIGT. Im Ticket abhaken, nicht neu bauen. |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/output/renderers/email/helpers.py | MODIFY | `pill_html`: `inline-flex;align-items:center` → `inline-block` (+ vertikale Ausrichtung per `line-height`/`vertical-align`) |
| src/output/renderers/email/compare_html.py | MODIFY | Platzhalter-Strich vereinheitlichen (C5-13) |
| src/output/renderers/compare_outlook_metric_ids.py | MODIFY | gleiche Konstante |
| tests/… (neu, nach Verhalten benannt) | CREATE | Pille mobil: gerenderte Pille enthält kein Flex um Textknoten und das Leerzeichen vor der Uhrzeit bleibt; Compare-Mail enthält nur ein Platzhalterzeichen |
| docs/specs/modules/email_metrics_summary_664.md | MODIFY | Pillen-Darstellung (inline-block) dokumentieren |

### Scope Assessment
- Files: ~3 Code + 1-2 Tests + 1 Spec
- Estimated LoC: +40/-10
- Risk Level: LOW-MEDIUM. `pill_html` hat genau einen Aufrufer; Optik-Regression (Höhe/Zentrierung der Pille) in Outlook/Gmail möglich → Mail-Validator gegen echte Staging-Mail.

### Technical Approach
1. (a) `inline-block` statt `inline-flex`; Zeilenumbruch zwischen Pillen regelt der Flex-Container weiter. Test prüft das Verhalten am gerenderten Mail-HTML (Pille ist kein Flex-Container, Label unverändert mit Leerzeichen), nicht nur eine CSS-Zeichenkette. Rot-Nachweis: aktueller Code liefert `inline-flex`.
2. C5-13: eine Konstante für „kein Wert" in Compare-Mail (Übersicht + Stundentabelle), Test über die ganze gerenderte Compare-Mail.
3. C5-04/07/30: je zuerst messen (Phase 3 Spec legt Messung als AC fest); C5-66 abhaken.
4. Gates: Renderer-Commit-Gate → Modus-Matrix-Test + `briefing_mail_validator.py` Exit 0; Compare-Änderung zusätzlich `email_spec_validator.py` Exit 0, gegen echte Staging-Mail.

### Dependencies
Upstream: `build_metrics_summary_pills` (`helpers.py`). Downstream: Trip-Mail HTML (`html.py:1302`), Compare-Mail, Validatoren.

### Open Questions
- [ ] C5-30: Soll Wind wie Böen aus dem Tagesfenster gemessen werden (Messung nötig, Spec-Entscheidung)?
- [ ] C5-07: lässt sich der Zweig mit realer Compare-Konfiguration reproduzieren?
- [ ] Soll das Ticket in zwei Lieferungen (a+C5-13 sofort; C5-04/07/30 nach Messung) laufen? Empfehlung: ein Workflow, Messungen als ACs.
