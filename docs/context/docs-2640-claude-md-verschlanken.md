# Context: CLAUDE.md verschlanken (#2640)

## Request Summary
Die Projekt-`CLAUDE.md` (273 Zeilen / 27,5 KB) wird bei jeder Modell-Anfrage mitgeladen. Sie soll auf unter 120 Zeilen / 12 KB schrumpfen: Detailmechanik wandert nach `docs/reference/`, in `CLAUDE.md` bleibt je ein Satz plus Verweis. Nichts darf verloren gehen, was kein Gegenstück in `docs/` hat. Reine Doku-Änderung (Doku-Ausnahme: kein Staging, kein Prod-Deploy).

## Zuordnung Abschnitt für Abschnitt (Ist-Stand `CLAUDE.md`)

| Abschnitt in `CLAUDE.md` | Gegenstück in `docs/` | Handlung |
|---|---|---|
| Projekt-Überblick, vier Kanäle, Multi-User | keins nötig (Dauerentscheidung) | BLEIBT (leicht gekürzt) |
| Architektur (drei Prozesse) | `docs/features/architecture.md` | BLEIBT als Kurzfassung |
| Wichtige Referenzen (Tabelle) | — | BLEIBT, aber kürzen |
| ADRs / Specs | `docs/adr/README.md`, `docs/specs/_template.md` | 2 Sätze + Verweis |
| Workflow (Befehlstabelle, Adversary, Mutations-Gegenprobe, PO-Pattern, Agenten-Modelle) | Mutations-Familien in `.claude/agents/implementation-validator.md` „Step 3b"; Rest nur in `CLAUDE.md` | Kern (Spec-Freigabe, AskUserQuestion, Deploy ohne Halt, Mutations-Pflicht) BLEIBT knapp; Rest NEU nach `docs/reference/workflow_und_agenten.md` |
| Workflow-State-Tabelle | **keins** (nirgends in `docs/reference/`) und veraltet: nennt `GZ_ACTIVE_WORKFLOW`, das Plugin setzt `OPENSPEC_ACTIVE_WORKFLOW` | NEU in `workflow_und_agenten.md`, dabei korrigieren |
| Test-Politik (zwei Schichten) | nur Teile (Testnamens-Gate, „Breiter Testlauf gesperrt" in `gates_und_ratschen.md`); Zwei-Schichten-Tabelle **fehlt** | Zwei-Schichten-Tabelle NEU in `gates_und_ratschen.md`; in `CLAUDE.md` Verbot Mock-Theater + „nie `uv run pytest` ohne Dateien" als je ein Satz |
| E2E & Deploy, Liefer-Workflow (Tabelle, PR, Merge) | `operations_playbook.md` „Liefer-Workflow — Detailablauf" (Z. 237) | Tabelle raus, Verweis. Playbook sagt „5 Checks", `CLAUDE.md` „6" → Playbook angleichen |
| CI-Ampel & Merge-Regel (6 Checks) | Teilweise `gates_und_ratschen.md` (Z. 514) | Liste der 6 Checks + Merge-Regel NEU ins Playbook (Liefer-Workflow), in `CLAUDE.md` ein Satz |
| Mail-Validatoren (Tabelle) | `docs/reference/mail_validators.md` (alle vier Validatoren) | Tabelle raus, Verweis; Überschrift und Mindestinhalt bleiben (Test #732, s.u.) |
| Design-Leitprinzipien | `docs/reference/design_system.md` nennt Tokens, aber **nicht** das Kontrast-Prinzip | Prinzip NEU in `design_system.md`; in `CLAUDE.md` ein Satz |
| Trip/Ortsvergleich-Code-Teilung | Pendant-Sperre in `gates_und_ratschen.md` | BLEIBT (Dauerentscheidung, PO mehrfach bekräftigt), knapp |
| Confidence-Verbot (#710) | nur im Code (`selectable=false`) | BLEIBT als 2 Sätze |
| Daten-Schema-Reworks | `operations_playbook.md` Z. 475 ff. (Prinzip + Anti-Pattern) | BLEIBT als Regelsatz (PFLICHT), Rest Verweis |
| Backlog & Nebenbefunde, Regel-Budget | Regel-Budget-Prüfdaten in `gates_und_ratschen.md`; Nebenbefund-Triage **fehlt** | Triage NEU in `workflow_und_agenten.md`; Regel-Budget als 1 Satz (Test s.u.) |
| Betrieb (Prod/Staging, Monitoring, Pre-Test-Validierung, Session-Artefakte) | teils `operations_playbook.md` | Prod/Staging-URLs BLEIBEN; Rest NEU bzw. Verweis |
| Parallele Sessions & Token-Budget | `operations_playbook.md` „Parallele Sessions" (Z. 305); `context_budget_guard` in `gates_und_ratschen.md` Z. 495 | Raus, Verweis. Token-Budget-Regeln (`/clear`, Bash bündeln, delegieren, gezielt lesen) NEU im Playbook |
| Messaging (MQ gregor→gregor verboten) | **keins** | NEU in `workflow_und_agenten.md`; Verbot bleibt als 1 Satz in `CLAUDE.md` (Fehler wurde mehrfach gemacht) |
| Compact instructions | nur hier (wird von `/compact` gelesen) | BLEIBT, gekürzt |

## Tests, die Inhalte der `CLAUDE.md` fest erwarten (dürfen nicht brechen)

| Test | Erwartung an `CLAUDE.md` |
|---|---|
| `tests/tdd/test_issue_732_email_validator_scope_docs.py` | Abschnitt `## Mail-Validatoren & Renderer-Gate` existiert; enthält „orts-vergleich", „vergleichstabelle" (oder winner-box/min-locations), „trip-briefing", „briefing_mail_validator"; „exit 0" nur zusammen mit „orts-vergleich" |
| `tests/tdd/test_compare_validator_mail_selection.py:513-545` | Zählt Zeilen mit `email_spec_validator.py` in `CLAUDE.md`, `e2e-verify.md`, `email_formatting.md`: genau **3** Aufrufe insgesamt, also muss `CLAUDE.md` genau eine solche Zeile mit gültigem Aufruf behalten |
| `tests/tdd/test_compare_premium_sms_versand.py:501` | Zeile mit „Premium-SMS-Reichweite" enthält „Ortsvergleich-Briefing", nicht „nur im **Trip-Briefing**" |
| `tests/tdd/test_issue_339_verify_timing.py:186` | enthält nicht „ICH stoppe den alten Server" / „ICH starte den Server neu"; enthält „staging" |
| `tests/test_regel_budget_pruefdatum_einstellung_auslieferung.py` | beruft sich auf „Regel-Budget" (Docstring; vor Phase 2 klären, ob er `CLAUDE.md` einliest) |

Andere Treffer (`CLAUDE.md` in Docstrings/Kommentaren von Tests und Hooks) sind Verweise ohne maschinelle Abhängigkeit. Hooks (`test_naming_gate.py`, `pendant_gate.py`, `file_claim_gate.py`) verweisen mit Abschnittsnamen („Test-Politik: Zwei Schichten", „Trip/Ortsvergleich-Code-Teilung", „Parallele Sessions") in Meldungstexten. Diese Namen müssen als Überschriften in `CLAUDE.md` erhalten bleiben oder die Meldungen zeigen auf die neue Fundstelle.

## Existing Patterns
- Auslagerung ist schon Praxis: `CLAUDE.md` verweist heute auf `gates_und_ratschen.md`, `operations_playbook.md`, `mail_validators.md`. Die Vorarbeit (Eintrag 5 des Tickets: Liefer-Workflow liegt bei Claude) ist im Playbook-Abschnitt „Liefer-Workflow" einzupflegen.
- Neue Pflichtregeln brauchen ersetzte Regel oder Prüfdatum (+90 Tage). Diese Änderung entfernt Regeln aus `CLAUDE.md`, fügt keine hinzu.

## Dependencies
- Upstream: nichts (reine Doku).
- Downstream: jede Claude-Sitzung (lädt die Datei), die fünf Tests oben, Hook-Meldungstexte mit Abschnittsnamen, `docs/README.md` (Wegweiser) falls eine neue Datei entsteht.

## Existing Specs
- Keine Modul-Spec betroffen. Spec für diese Arbeit: `docs/specs/modules/claude_md_verschlankung.md` (neu, Phase 4). Doku-Specs mit `created >= 2026-05-11` brauchen `## Acceptance Criteria` mit `**AC-n:** Given/When/Then`.

## Risks & Considerations
1. **Stiller Regelverlust** (Hauptrisiko): Abschnitte ohne Gegenstück (Workflow-State, Zwei-Schichten-Test-Politik, Design-Kontrast, Nebenbefund-Triage, MQ-Regel, Token-Budget) müssen zuerst nach `docs/` und erst dann aus `CLAUDE.md` raus. Nachweis: Zuordnungstabelle in der Spec, Zeile für Zeile.
2. **Zielgröße** (< 120 Zeilen / 12 KB) ist knapp, weil mehrere PO-Vorgaben wörtlich stehen sollen (vier Kanäle gleichrangig, Multi-User-Isolation, Premium-SMS-Reichweite, Trip/Ortsvergleich-Teilung). Notfalls Nachweis, dass jede Zeile eine Entscheidung ist, die man sonst nicht wissen kann.
3. **Überstimmte Vorlage** (Ticket-Punkt 5): Das Plugin sagt in `/60-validate` „Merge, PR bleiben beim PO", `CLAUDE.md`/Playbook sagen „bei Claude". Nur die Projekt-Doku wird angepasst. Die Plugin-Vorlage liegt außerhalb dieses Repos und bleibt unberührt (Hinweis im Playbook).
4. **Workflow-Variable veraltet**: `GZ_ACTIVE_WORKFLOW` in `CLAUDE.md` vs. `OPENSPEC_ACTIVE_WORKFLOW` im Plugin 4.4.2. Beim Umzug korrigieren, vorher prüfen, ob Projekt-Hooks noch `GZ_ACTIVE_WORKFLOW` lesen.
5. **Doku-Ausnahme**: Kein Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`; Lieferweg PR mit grüner Ampel, kein Staging/Prod-Deploy. Zwei Tests (`tests/tdd/...`) laufen trotzdem in der CI, daher lokal vorab einzeln laufen lassen.

## Analysis

### Type
Feature (reine Doku-Änderung, kein Produktcode).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `CLAUDE.md` | MODIFY | 273 → < 120 Zeilen, < 12 KB; je ausgelagertem Block ein Satz + Verweis |
| `docs/reference/workflow_und_agenten.md` | CREATE | Workflow-State-Regeln (korrigiert: `OPENSPEC_ACTIVE_WORKFLOW`), Agenten-Modelle, PO-Pattern, Nebenbefund-Triage, Messaging/MQ-Regel |
| `docs/reference/operations_playbook.md` | MODIFY | Liefer-Workflow: 6 Checks statt 5, Merge-Regel, Rollen (PR/Merge/Deploy bei Claude, überstimmt `/60-validate`-Vorlage); Token-Budget-Regeln bei „Parallele Sessions"; Betrieb-Reste (Pre-Test-Validierung, Session-Artefakte) |
| `docs/reference/gates_und_ratschen.md` | MODIFY | Test-Politik „Zwei Schichten" (Tabelle) ergänzen |
| `docs/reference/design_system.md` | MODIFY | Design-Leitprinzip „Hoher Kontrast = Lesbarkeit" ergänzen |
| `docs/README.md` | MODIFY | neue Datei im Wegweiser |
| `docs/specs/modules/claude_md_verschlankung.md` | CREATE | Spec mit ACs und Zuordnungstabelle (Phase 3) |
| Test (neu, nach Verhalten benannt) | CREATE | `tests/test_claude_md_budget.py`: Größenobergrenze + Mindestinhalte + jedes Verweisziel existiert |

### Scope Assessment
- Files: 3 neu/ändern in `docs/`, 1 `CLAUDE.md`, 1 Test, 1 Spec
- Estimated LoC: Code/Test ~+60; Doku zählt nicht gegen das LoC-Limit
- Risk Level: MEDIUM (Datei steuert jede Sitzung; Tests lesen Inhalte; Regelverlust)

### Technical Approach
1. Zuerst auslagern, dann kürzen: jede zu entfernende Regel steht vorher wörtlich (nicht paraphrasiert) am neuen Ort.
2. `CLAUDE.md` behält: Überblick + vier Kanäle + Multi-User, Architektur, Referenzen, Workflow-Kern (Spec-Freigabe, `AskUserQuestion`, Deploy ohne Halt, Mutations-Pflicht), Test-Politik als 3 Sätze, Liefer-Workflow als 3 Sätze (PR statt Direkt-Push, Ampel, Rollen bei Claude), Mail-Validator-Abschnitt (Überschrift + 1 Zeile `email_spec_validator.py` + Verweis; Mindestinhalt für Test #732), Design-Prinzip 1 Satz, Trip/Ortsvergleich-Teilung, Confidence-Verbot, Schema-Regel, Betrieb-URLs, Parallele Sessions 2 Sätze, MQ-Verbot 1 Satz, Compact-Hinweis gekürzt.
3. Hook-Meldungen verweisen mit Abschnittsnamen: Überschriften „Test-Politik", „Trip/Ortsvergleich-Code-Teilung", „Parallele Sessions" bleiben erhalten.
4. Neuer Wächtertest begrenzt die Größe (Ratsche gegen erneutes Anwachsen) und prüft die Mindestinhalte, die Tests/Hooks erwarten. Prüfdatum +90 Tage = 2027-01-28 (Regel-Budget).

### Dependencies
Siehe Abschnitte oben (fünf lesende Tests, Hook-Meldungstexte). `GZ_ACTIVE_WORKFLOW` wird in drei Hooks (`design_fidelity_diff.py`, `pre_issue_close_design_gate.py`, `prod_selftest.py`) noch als Fallback gelesen. Die Doku nennt deshalb beide Namen und sagt, welcher gilt; die Hooks bleiben unangetastet.

### Open Questions
- [x] Fällt `test_regel_budget_pruefdatum_einstellung_auslieferung.py` bei Kürzung? Nein: nennt „Regel-Budget" nur im Docstring, liest `CLAUDE.md` nicht ein.
- [ ] Reichen 12 KB, wenn die PO-Vorgaben zu den vier Kanälen wörtlich bleiben? Falls nicht, in der Spec Zielgröße 14 KB mit Begründung vorschlagen; PO entscheidet bei der Spec-Freigabe.
