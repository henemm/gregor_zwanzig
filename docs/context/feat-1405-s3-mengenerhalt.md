# Context: #1405 S3 — Mengenerhalt über die gerenderte Ausgabe

Workflow: `feat-1405-s3-mengenerhalt` · Epic #2505 (letzter offener Punkt) · Stand: 2026-10-27

## Ausgangslage

S1/S2 (AST-Wächter, Protokoll-Pflicht) und S4a/S4b (Erfolg heißt Wirkung) sind live.
Zielbild-Satz 1 und 3 des Tickets sind nur zur Hälfte erfüllt: Der Wächter erzwingt
„Verworfenes landet im `logger.warning`“, **nicht** „ist in Mail/SMS/Telegram erkennbar“
(`docs/specs/modules/waechter_1405_stille_aufloesung.md`, Known Limitations). Ein AC für S3
existiert nirgends — er muss in der neuen Spec entstehen.

## Analysis

### Type
Feature (Verhaltensnachweis + Reparatur der dabei gefundenen stillen Verluste).

### Befund: wo Auswahl → Ausgabe heute still verliert

Stichproben am Code gegengeprüft (nicht nur aus dem Agentenbericht).

| # | Stelle | Verhalten | Kanal / Fläche |
|---|---|---|---|
| L1 | `src/output/renderers/email/compare_html.py:816` `_visible_metrics` (`if k in by_key`) | gewählte Metrik ohne CV2-Zeile verschwindet ohne Markierung | Ortsvergleich E-Mail |
| L2 | `src/output/renderers/comparison.py:143` `_ordered_rows` (`if m in by_id`) | dito | Ortsvergleich Klartext |
| L3 | `src/output/renderers/compare_metric_ids.py:~175` `resolve_enabled_metrics` | unmappbare Auswahl nur geloggt, im Output unsichtbar | Ortsvergleich, alle Kanäle |
| L4 | `src/output/renderers/comparison.py:611` `_sms_metric_cell` → `None` | fehlender Wert: Zelle entfällt „ohne Platz oder Zähler“ | Ortsvergleich SMS (Telegram zählt, SMS nicht) |
| L5 | Trip: `_allowed_col_keys_for_horizon` (`email/html.py:912`) | ungeprüft, ob gefilterte Spalten still fallen | Trip E-Mail (offen, in Analyse der Spec klären) |

Bereits sauber (nicht anfassen): Trip-SMS (`-`/`?` Null-Form und Lückenform), Trip-Telegram (`–`),
Trip-E-Mail-Zellen (`–`), Ortsvergleich-Telegram (`+N gewählte Wettergrößen ohne Wert`).

### Vorhandene Tests (Teilabdeckung)
- `tests/tdd/test_compare_render_options_resolver.py` — nur Negativ: Abgewähltes fehlt.
- `tests/tdd/test_trip_outlook_metric_selection.py` — Auswahl → Spalten/Zellen (Trip-Outlook-HTML).
- `tests/test_metric_id_resolution_is_reported.py` — nur Protokoll, nicht Ausgabe.
- **Nicht vorhanden:** ein Test „Eingabemenge = Ausgabemenge ∪ ausdrücklich Markiertes“, für keine Fläche und keinen Kanal.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/test_selection_conservation_rendered.py` | CREATE | Mengenerhalt-Matrix: Fläche × Kanal, gewählte Größen rein → jede erscheint oder ist markiert |
| `src/output/renderers/email/compare_html.py` | MODIFY | L1: Markierung für gewählte, nicht darstellbare Metrik |
| `src/output/renderers/comparison.py` | MODIFY | L2 + L4: Markierung bzw. Zähler analog Telegram |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | L3: Verworfenes an den Renderer durchreichen statt nur loggen |
| `docs/reference/sms_format.md` | MODIFY | SSOT: Wire-Vertrag für den Zähler in der Ortsvergleich-SMS |
| `docs/specs/modules/…` | CREATE | Spec mit ACs (S3 hat bisher keine) |

### Scope Assessment
- Files: ~6 produktiv/Test + Spec/Doku
- Estimated LoC: +250/−20 (Test-Matrix ~120, Reparatur ~80, Rest Doku) → `loc_limit_override` nötig, vorher `workflow.py status` fragen
- Risk Level: MEDIUM — berührt das 153-Zeichen-Budget der SMS und den Wire-Vertrag (SSOT `sms_format.md`)

### Technical Approach
1. **Test zuerst (RED):** Parametrisierte Matrix. Eingabe: Auswahl aus N Metriken, davon eine bewusst ohne Daten und eine mit unmappbarer ID. Ausgabe je Kanal (E-Mail HTML+Plain, Telegram, SMS; Premium-SMS wo eigener Renderer) muss jede gewählte Größe zeigen **oder** die Zahl der nicht gezeigten nennen. Deterministisch über den vorhandenen Builder `_make_comparison_result` und die Fixtures `tests/fixtures/compare_kette/`; Trip über `tests/helpers/trip_outlook_selection.py`.
2. **Reparatur nach Telegram-Vorbild** (`comparison.py:763-764`: „+N gewählte Wettergrößen ohne Wert an diesem Ort“): Das Muster existiert, wird auf die übrigen Flächen übertragen — keine neue Formulierung erfinden.
3. **L3 als Kern:** `resolve_enabled_metrics` gibt neben der Liste auch die verworfenen Einträge zurück (oder legt sie am Ergebnisobjekt ab), damit jeder Renderer sie benennen kann. Aufrufseite prüfen statt Signaturen flächendeckend umzubauen (Lehre #1402).
4. **Reihenfolge einhalten:** keine Schwellen/Erwartungen anpassen, damit etwas grün wird; roter Test = Fund.

### Dependencies
- `docs/reference/sms_format.md` (SSOT SMS/Premium-SMS-Tokens): Änderung dort zuerst, Premium-SMS nutzt laut Doku denselben `sms_text`-Pfad.
- Trip-/Compare-Teilung (CLAUDE.md): Die Markierungslogik soll **ein** gemeinsamer Baustein sein, kein zweiter Satz Formulierungen pro Fläche.
- Mail-Validatoren: Änderung an Mail-Inhalt ⇒ Renderer-Commit-Gate (Modus-Matrix-Test + `email_spec_validator.py` bzw. `briefing_mail_validator.py` frisch grün).
- #1412 / #2345 P4 laufen parallel in anderen Epics — Dateikollision in `comparison.py` vor Start per `git log HEAD..origin/main -- <datei>` prüfen.

### Open Questions
- [ ] L5: Fallen im Trip durch `_allowed_col_keys_for_horizon` gewählte Spalten still weg? (in der Spec-Phase per Test klären, nicht raten)
- [ ] Ortsvergleich-SMS: Zähler `+N` kostet Zeichen im 153-Budget. Technische Entscheidung (Tech Lead): Zähler nur anhängen, wenn etwas fehlt; sonst unverändert ⇒ kein Mehrverbrauch im Normalfall.
- [ ] Premium-SMS im Ortsvergleich: eigener Renderer oder SMS-Text? (Agent: „nicht vollständig geprüft“) — in der Spec-Phase verifizieren.
- [ ] Abgrenzung der alten Spec („S3 ändert keinen Produktivcode“) ist überholt: L1–L4 sind Fund, nach PO-Regel im selben Ticket zu beheben, nicht als Ausnahme zu parken.
