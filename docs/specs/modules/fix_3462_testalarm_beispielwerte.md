---
entity_id: fix_3462_testalarm_beispielwerte
type: bugfix
created: 2026-11-27
updated: 2026-11-27
status: draft
version: "1.0"
workflow: fix-3462-testalarm-beispielwerte
tags: [alert, test-alarm, bugfix, "#3462"]
---

# Fix #3462: Test-Alarm-Beispielwerte widersprechen sich

## Approval

- [ ] Approved

## Purpose

Der Test-Alarm (#3441) soll sich wie ein echter Alarm lesen. Bisher zeigt er "Änderung unter deiner Alarm-Schwelle", obwohl er ein Beispiel für eine Überschreitung sein soll, und nennt dieselbe Wettergröße mehrfach. Diese Spec ersetzt die Beispiel-Formel so, dass die Schwelle sichtbar überschritten wird und jede Größe je Block nur einmal erscheint.

## Source

- **File:** `src/services/alert_test_service.py`
- **Identifier:** `_beispiel`, `beispiel_aenderungen`

> **Schicht:** Python-Core (`src/services/`). Frontend, Go-API, Renderer und Katalog bleiben unverändert.
> **Trip/Ortsvergleich:** `beispiel_aenderungen` bedient bereits beide Kontexte aus einem Code; keine neue Komponente.
> **Mandantentrennung:** keine Nutzerdaten werden bewegt oder neu gelesen; Änderung betrifft nur Beispielzahlen.
> **Kanäle:** E-Mail, Telegram, SMS und Premium-SMS rendern über denselben Renderer; alle vier sind in den ACs benannt.

## Ablösung der Vorgänger-Formel

Diese Spec löst die Beispiel-Formel aus `docs/specs/modules/feat_3441_test_alarm.md` AC-11 ab (neu = 1.2·Schwelle, alt = 0.8·Schwelle, bei Delta alt = 0). Diese Formel ergab bei ABSOLUTE- und THRESHOLD_CROSSING-Regeln nur Δ = 0.4·S und damit das Urteil "unter". Die Vorgänger-Spec erhält bei der Implementierung an AC-11 einen Ablösungs-Hinweis auf diese Spec. Alle übrigen Zusicherungen von AC-11 (echte Etappen/Orte, Stundenzeilen, eine Änderung je Regel bzw. Metrik) gelten weiter.

## Estimated Scope

- **LoC:** ~60 Produktiv, ~150 Test
- **Files:** 4 (1 Produktiv, 2 Test, 1 Doku-Hinweis)
- **Effort:** low

## Scope (Affected Files)

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/alert_test_service.py` | MODIFY | `_beispiel`/`beispiel_aenderungen`: Richtung aus Katalog, neue Formel, Gewitterstufe, %-Deckel, Dedupe je Bezeichnung |
| `tests/tdd/test_3462_testalarm_beispielwerte.py` | CREATE | Tests am echten Renderer ohne Mock |
| `tests/tdd/test_alert_test_service.py` | MODIFY | alte Formel-Zusicherung (ca. Zeilen 42-60) auf neue Formel anpassen |
| `docs/specs/modules/feat_3441_test_alarm.md` | MODIFY | Ablösungs-Hinweis an AC-11 |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.renderers.alert.project._METRICS` | module (lesend) | Richtung je Summary-Feld über cmp "unter" |
| `output.renderers.alert.project._resolve_metric_id` | function (lesend) | aufgelöste Katalog-Metrik für Dedupe |
| `output.renderers.alert.model.over_thr` | function (lesend) | Urteil "über" = abs(neu - alt) >= Schwelle |
| `output.renderers.alert.render` | module (lesend) | echter Renderer für die Tests, `_deviation_label` für Gewitter |
| `src/i18n/messages/en/alarm.json` | catalog (lesend) | Schlüssel `alarm.abweichung.urteil`, EN-Pendant der "unter"-Seite |
| ADR-0013 / ADR-0106 | ADR | `threshold` ist die Sprung-Schwelle (Δ) |
| `docs/specs/modules/feat_3441_test_alarm.md` | spec | Vorgänger, AC-11 abgelöst |

## Implementation Details

Änderung nur in `src/services/alert_test_service.py`. S bezeichnet die Schwelle der Regel.

- **Richtung:** Je Summary-Feld aus dem Katalog: hat ein Kandidat in `_METRICS` cmp "unter", ist das Feld fallend, sonst steigend. Die `direction` der WeatherChange ist "decrease" bzw. "increase".
- **Betrag:** Die Änderung beträgt immer 1.2·|S| (Betrag der Schwelle, damit auch negative Schwellen wie Kälte −25 °C funktionieren).
- **Steigend:** alt = 0 bei DELTA-Regel, sonst 0.8·S. neu = alt + 1.2·|S|.
- **Fallend:** neu = 0.8·S, alt = neu + 1.2·|S|. Damit fällt zum Beispiel Sicht.
- **Folge:** |Δ| = 1.2·|S| ≥ S, der Renderer urteilt "über" (`over_thr`).
- **Stufenmetrik Gewitter (`thunder_level_max`):** alt = 0, neu = min(3, max(2, ceil(1.2·S))). Mindestens "mäßig", nie das Label "Luftmasse".
- **Einheit "%":** neu ≤ 100, alt = max(0, neu - 1.2·S).
- **Dedupe:** Je angezeigter Alarm-Bezeichnung (`get_alert_label(_resolve_metric_id(feld, richtung), "de")`) höchstens eine Beispiel-Änderung; die erste Regel in Reihenfolge gewinnt. Weil Kälte- und Hitzeseite im Katalog beide „Temp“ heißen, erscheint Temperatur genau einmal (Katalog bleibt unverändert). Richtung je Feld trotzdem aus dem Katalog (`temp_min_c` fallend).
- **Rückfall:** Ohne aktive Regel bleibt es bei der Böen-Regel mit Schwelle 50 (bisher 40 -> 60 mit Δ 20, künftig steigend 40 -> 100 mit Δ 60 ≥ 50).
- **Mehrere Orte im Vergleich:** je Ort ein Block, dort jede Größe einmal. Dieselbe Größe in verschiedenen Orts-Blöcken ist keine Doppelung.

## Expected Behavior

- **Input:** Trip- oder Vergleichs-Konfiguration mit aktiven Alarm-Regeln (oder keine).
- **Output:** Beispiel-Änderungen, die der echte Renderer als "über" der Schwelle beurteilt, mit höchstens einer Änderung je angezeigter Bezeichnung.
- **Side effects:** keine; echte Alarmwege, Renderer und Katalog bleiben unverändert.

## Test Plan

### Automated Tests (TDD RED), `tests/tdd/test_3462_testalarm_beispielwerte.py`

- [ ] GIVEN Trip mit ABSOLUTE-, DELTA- und THRESHOLD_CROSSING-Regeln WHEN Beispiel-Änderungen gebaut werden THEN gilt für jede `over_thr` des echten Renderers.
- [ ] GIVEN Vergleich-Standardmetriken und Rückfall WHEN gebaut THEN gilt für jede `over_thr`.
- [ ] GIVEN gerenderte Nachricht je Kanal (E-Mail, Telegram, SMS, Premium-SMS) in DE und EN THEN enthält sie nie die "unter"-Urteilsformulierung aus dem Katalog.
- [ ] GIVEN Vergleich-Standard THEN genau eine Änderung für Temperatur-Minimum/-Änderung und eine für Niederschlag-Summe/-Änderung.
- [ ] GIVEN `temp_min_c`, `temp_max_c` und Temperatur-Änderung aktiv THEN genau eine Temperatur-Änderung (Bezeichnung „Temp“ einmal); ein `temp_min_c`-Beispiel fällt.
- [ ] GIVEN Gewitter-Regel THEN Gewitter-Bezeichnung, nie "Luftmasse"; Sicht-Beispiel fällt; %-Werte liegen in 0..100.
- [ ] Bestehende `tests/tdd/test_alert_test_service.py` auf die neue Formel angepasst.

### Staging-E2E

- [ ] Echt zugestellte Test-Alarm-Mail (Stalwart-Test-Postfach) DE und EN, je Trip und Ortsvergleich, ohne "unter deiner Alarm-Schwelle" und ohne doppelte Größe je Block.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit ABSOLUTE-, DELTA- und THRESHOLD_CROSSING-Regeln, ein Ortsvergleich mit Standardmetriken und der Rückfall ohne aktive Regel / When der Test-Alarm die Beispiel-Änderungen erzeugt / Then beurteilt der echte Renderer jede Beispiel-Änderung als "über" der Schwelle (Differenz mindestens so groß wie die Schwelle).
  - Test: pytest ruft `over_thr` des echten Renderers für jede erzeugte Änderung aller drei Regelarten, der Vergleich-Standardmetriken und des Rückfalls auf, ohne Mock.

- **AC-2:** Given ein gerenderter Test-Alarm in E-Mail, Telegram, SMS und Premium-SMS, jeweils auf Deutsch und Englisch / When die Nachricht vom echten Renderer erzeugt wird / Then steht darin nie "unter deiner Alarm-Schwelle" und nie das englische Pendant der "unter"-Seite aus `alarm.abweichung.urteil`.
  - Test: pytest rendert alle vier Kanäle in DE und EN am echten Renderer ohne Mock und prüft die Abwesenheit beider "unter"-Texte sowie die Anwesenheit der "über"-Aussage.

- **AC-3:** Given ein Trip oder Ortsvergleich mit Standardmetriken, die auf dieselbe Katalog-Metrik fallen (Temperatur-Minimum und Temperatur-Änderung, Niederschlag-Summe und Niederschlag-Änderung) / When die Beispiel-Änderungen erzeugt werden / Then gibt es je angezeigter Bezeichnung höchstens eine Änderung (Temperatur erscheint genau einmal, obwohl Minimum, Maximum und Änderung aktiv sind; Niederschlag genau einmal), und ein Temperatur-Minimum-Beispiel fällt.
  - Test: pytest zählt die Alarm-Bezeichnungen der erzeugten Änderungen (keine doppelt) und prüft in der gerenderten Mail je Block jede Bezeichnung höchstens einmal.

- **AC-4:** Given eine aktive Gewitter-Regel und eine aktive Sicht-Regel / When der Test-Alarm gerendert wird / Then trägt das Gewitter-Beispiel eine Gewitter-Bezeichnung (mindestens "mäßig", nie "Luftmasse") und das Sicht-Beispiel fällt (neuer Wert kleiner als alter).
  - Test: pytest rendert Gewitter- und Sicht-Beispiel am echten Renderer ohne Mock und prüft Bezeichnung, Stufe und Richtung.

- **AC-5:** Given der Staging-Server und ein Test-Postfach / When ein Test-Alarm für Trip und für Ortsvergleich auf Deutsch und Englisch tatsächlich als Mail zugestellt wird / Then enthält die zugestellte Mail kein "unter deiner Alarm-Schwelle" (bzw. englisches Pendant) und je Block keine Wettergröße doppelt.
  - Test: Staging-E2E mit echt zugestellter Mail im Stalwart-Test-Postfach (kein Mock) für Trip und Ortsvergleich, DE und EN.

## Definition of Done

- [ ] Beispiel-Änderungen werden für jede Regelart als „über“ der Schwelle beurteilt (AC-1)
- [ ] Keine „unter“-Formulierung auf allen vier Kanälen DE/EN (AC-2)
- [ ] Je angezeigter Bezeichnung höchstens eine Beispiel-Änderung, Gewitter/Sicht korrekt (AC-3, AC-4)
- [ ] Adversary-Verdict VERIFIED mit Mutations-Gegenprobe; alle 6 CI-Checks grün; Staging-E2E Mail DE/EN grün (AC-5); ausgeliefert, Selftest grün

## Known Limitations

- Mehrere Orte im Ortsvergleich zeigen dieselbe Größe je Ort einmal; das ist gewollt (je Ort ein Block).
- Echte Alarmwege, Renderer und Katalog bleiben unverändert; wer dort "unter" urteilt, ist nicht Gegenstand dieses Fixes.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** reine Korrektur von Beispielzahlen im Test-Alarm; die Schwellen-Semantik aus ADR-0013/ADR-0106 wird eingehalten, nicht geändert.

## Changelog

- 2026-11-27: Initial spec created (Issue #3462); löst die Beispiel-Formel aus #3441 AC-11 ab.
- 2026-11-27: Dedupe je angezeigter Bezeichnung statt je Katalog-Metrik (Kälte/Hitze heißen beide „Temp“); Betrag 1.2·|S| für negative Schwellen.
