---
entity_id: issue_1108_email_spec_validator_v2
type: module
created: 2026-07-08
updated: 2026-07-08
status: draft
version: "1.0"
issue: 1108
tags: [compare, email, validator, gate, python]
---

# Issue #1108 — Compare-Mail-Validator auf v2-Vertrag umstellen

## Approval

- [ ] Approved

## Purpose

Stellt `.claude/hooks/email_spec_validator.py` (das Acceptance-Gate für die Orts-Vergleich-Mail)
vom veralteten Score/Winner-Vertrag auf den seit Issue #1110 gültigen v2-Mail-Vertrag um
(Übersichtstabelle Metriken × Orte mit Warn-Zeile, Stundentabellen für alle gelisteten Orte,
kein Score/Winner). Ohne diese Umstellung ist der Validator gegen die neue Mail strukturell
nie bestehbar (Dauer-Exit-1) und blockiert die E2E-Verifikation sowie den Prod-Deploy von #1110.

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `validate_structure()` (Kern-Umschreibung), `extract_locations()`,
  `extract_table_rows()`, `validate_hourly_table()` (Anpassung an v2-Spaltenvertrag)

> **Schicht-Hinweis:** Reines Hook-Tooling (`.claude/hooks/`), kein Frontend-, Go-API- oder
> Python-Core-Domain-Code betroffen. Kein Endpoint, kein Datenmodell.

## Estimated Scope

- **LoC:** ~150–250 (Validator-Kernfunktionen umschreiben + Vertragstest-Datei umschreiben +
  einen Test entskippen + Doku-Absatz)
- **Files:** 3 (`.claude/hooks/email_spec_validator.py`,
  `tests/tdd/test_issue_1046_email_validator_table_contract.py`,
  `docs/reference/mail_validators.md`) + 1 Einzeiler-Änderung
  (`tests/tdd/test_issue_1110_compare_mail_v2.py`, skip-Marker entfernen)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `render_compare_html()` (`src/output/renderers/email/compare_html.py`) | intern | Quelle der Wahrheit für den v2-Vertrag — liefert Übersichtstabelle (Warn-Zeile zuerst) + Stundentabellen aller Orte, kein Score/Winner |
| `CV2_METRICS` (`src/output/renderers/email/compare_html.py:70`) | intern | Metrik-Katalog der Übersichtstabelle; Zeilenanzahl variiert je nach `enabled_metrics`-Filter (#1104) — Validator darf keine feste Zeilenzahl verlangen |
| `docs/specs/modules/issue_1110_compare_mail_v2.md` §2/§8 | intern | Vertragsbeschreibung (Übersichtstabelle, Warn-Zeile, Stundentabellen-Spalten, delegierte Validator-Anforderung) |
| `tests/tdd/test_issue_1110_compare_mail_v2.py::TestCompareMailV2Validator` | intern | Enthält den skip-markierten AC-9-Test (`test_ac9_…`), der in diesem Workflow entskippt wird |
| Marker-Header `X-GZ-Mail-Type: compare` (`build_mime_message()`) | intern | Bleibt unverändertes Dispatch-Kriterium — dieses Issue ändert nichts am Dispatch, nur am Struktur-/Plausibilitätsvertrag |
| Stalwart Test-Postfach (`gregor-test@henemm.com`, `GZ_TEST_IMAP_*`) | extern | E2E-Nachweis (AC-8) — echte zugestellte Mail, kein Mock |

## Implementation Details

Betroffene Kernfunktionen im heutigen (Alt-)Validator und was sich ändert:

- `validate_structure()` (aktuell `email_spec_validator.py:175–246`): verwirft den
  festen 8-Zeilen-Vertrag (`expected_labels`, Z. 214–224, englische Ski-Labels
  „Score"/„Snow Depth"/„Sunny Hours"…) sowie die Klassen-basierte Tabellenzählung
  (`_KNOWN_TABLE_CLASSES`/`_find_matrix_table_html`, Z. 119–172, `class="matrix-table"`
  existiert im v2-Renderer nicht mehr). Neuer Vertrag: Übersichtstabelle wird über ihre
  erste Datenzeile „Amtliche Warnungen" identifiziert (nicht über CSS-Klasse), Orte über
  die Kopfzeile dieser Tabelle extrahiert; für jeden so extrahierten Ort MUSS eine
  Stundentabelle existieren (identifiziert über den Spaltenkopf „Zeit", nicht über
  CSS-Klasse) mit exakt den 8 Spalten Zeit/Temp/Gef./Wind/Böen/Regen/Wolken/UV in dieser
  Reihenfolge.
- Pflicht-Sektionen (Z. 236–244): der Eintrag `(["Recommendation", "Empfehlung"], "Winner-Box")`
  entfällt ersatzlos — stattdessen wird das Vorhandensein von Score-/Winner-Sprache
  („Score", „Empfehlung", „Bester Standort", „🏆") als **Fehler** gewertet (Negativ-Check,
  Umkehrung der bisherigen Pflicht-Logik).
- `validate_hourly_table()` (Z. 354–364): der feste Stunden-Fenster-Check (09–16 Uhr String-
  Presence) bleibt sinngemäß erhalten, wird aber pro extrahiertem Ort ausgewertet statt
  global, damit ein fehlender Ort eindeutig benennbar ist (AC-3).
- Zeilenanzahl der Übersichtstabelle wird NICHT mehr fix geprüft (#1104 filtert Zeilen je
  Preset) — Mindestanforderung: Warn-Zeile + mindestens eine numerische Metrik-Zeile.
- `validate_plausibility()`/`validate_format()`: Format-Regeln (z. B. Wind/Böen-Zahlenformat,
  Prozent-/Grad-Werte) werden auf die v2-Spaltenformate der Stundentabellen umgestellt statt
  auf die alten englischen Zeilen-Labels der Übersichtstabelle.
- `docs/reference/mail_validators.md` Abschnitt 1: Beschreibung des Compare-Gate-Vertrags
  (Winner-Box/Vergleichstabelle-Sprache) wird auf den v2-Vertrag aktualisiert.

## Expected Behavior

- **Input:** HTML-Body einer per IMAP abgerufenen, tatsächlich zugestellten Orts-Vergleich-Mail
  (oder synthetisches v2-Struktur-Fixture in Tests).
- **Output:** Liste von Fehlermeldungen (leer = Exit 0) bzw. Prozess-Exit-Code
  (0 = Vertrag erfüllt, 1 = Spec-Verletzung, 2 = technischer Fehler wie gehabt).
- **Side effects:** keine — reiner Lese-/Prüfpfad gegen IMAP, kein Versand, keine Datenänderung.

## Acceptance Criteria

- **AC-1:** Given eine über `render_compare_html()` erzeugte bzw. echt an
  `gregor-test@henemm.com` zugestellte v2-Ortsvergleich-Mail (Übersichtstabelle mit Warn-Zeile
  als erster Datenzeile, Stundentabellen aller gelisteten Orte) / When der Validator diese Mail
  prüft / Then liefert er eine leere Fehlerliste (Exit-Code-0-Äquivalent).
  - Test: `validate_structure()` gegen v2-HTML-Fixture bzw. echte Staging-Mail aufrufen,
    Ergebnisliste auf Leerheit prüfen.

- **AC-2:** Given eine Mail im veralteten Vertrag (Winner-Box/„Empfehlung"-Sektion, Tabelle mit
  `class="matrix-table"`, englische Zeilen-Labels wie „Snow Depth") / When der Validator diese
  Mail prüft / Then meldet er mindestens einen Fehler — eine Alt-Mail darf niemals als
  vertragskonform durchgehen.
  - Test: Alt-Struktur-Fixture (Winner-Box + matrix-table-Klasse) gegen `validate_structure()`
    laufen lassen, nicht-leere Fehlerliste erwarten.

- **AC-3:** Given eine v2-Mail, deren Übersichtstabelle einen Ort listet, für den jedoch keine
  zugehörige Stundentabelle im Body existiert / When der Validator diese Mail prüft / Then
  meldet er einen Fehler, der den fehlenden Ort konkret benennt.
  - Test: Fixture mit 3 Orten in der Übersichtstabelle, aber nur 2 Stundentabellen gegen
    `validate_structure()` laufen lassen, Fehlermeldung auf den fehlenden Ortsnamen prüfen.

- **AC-4:** Given eine Mail, deren Body an irgendeiner Stelle einen Score-Wert, eine
  „Bester Standort"/„Empfehlung"-Aussage oder ein Gewinner-Symbol (z. B. „🏆") enthält / When
  der Validator diese Mail prüft / Then meldet er einen Fehler — Score-/Winner-Sprache ist im
  v2-Vertrag ein Verstoß, kein optionales Extra.
  - Test: v2-Struktur-Fixture, angereichert um eine künstliche „Empfehlung: Ort X (Score 87)"-
    Zeile, gegen `validate_structure()` prüfen, nicht-leere Fehlerliste erwarten.

- **AC-5:** Given eine v2-Mail, deren Übersichtstabelle preset-bedingt nur auf die Warn-Zeile
  plus eine einzelne numerische Metrik (z. B. Wind) gefiltert ist (#1104) / When der Validator
  diese Mail prüft / Then bleibt sie fehlerfrei (Exit 0) — der Validator verlangt keine feste
  Metrik-Anzahl, nur Warn-Zeile plus mindestens eine numerische Zeile.
  - Test: Übersichtstabellen-Fixture mit genau 2 Zeilen (Warn + Wind) statt der vollen
    Metrik-Liste gegen `validate_structure()` prüfen, leere Fehlerliste erwarten.

- **AC-6:** Given eine Stundentabelle mit falscher, unvollständiger oder umsortierter
  Spaltenreihenfolge (Soll: Zeit/Temp/Gef./Wind/Böen/Regen/Wolken/UV) / When der Validator diese
  Mail prüft / Then meldet er einen Fehler, der die Spaltenabweichung für den betroffenen Ort
  benennt.
  - Test: Fixture mit einer auf 3 Spalten verkürzten Stundentabelle für einen von drei Orten
    gegen `validate_structure()` prüfen, Fehlermeldung referenziert Spalten/Stunden-Kontext.

- **AC-7:** Given der in Issue #1110 skip-markierte Test
  `test_ac9_validate_structure_akzeptiert_v2_html_fehlerfrei`
  (`tests/tdd/test_issue_1110_compare_mail_v2.py`) / When der `@pytest.mark.skip`-Marker nach
  Abschluss der Validator-Umstellung entfernt und der Test ausgeführt wird / Then läuft er grün.
  - Test: `uv run pytest tests/tdd/test_issue_1110_compare_mail_v2.py::TestCompareMailV2Validator::test_ac9_validate_structure_akzeptiert_v2_html_fehlerfrei`
    ohne Skip, Exit 0.

- **AC-8:** Given eine über den internen Compare-Versandpfad frisch ausgelöste, tatsächlich an
  `gregor-test@henemm.com` zugestellte v2-Ortsvergleich-Mail auf Staging (nach Deploy des
  #1110-Stands) / When `uv run python3 .claude/hooks/email_spec_validator.py` dagegen läuft /
  Then endet der Prozess mit Exit-Code 0.
  - Test: Echter Validator-Lauf gegen das Stalwart-Test-Postfach (`GZ_TEST_IMAP_*`), Exit-Code
    als Beweis protokollieren — kein Mock, keine synthetische Mail.

## Known Limitations

- **Config-bewusste Prüfung ist Folge-Scope (#1107):** Dieser Workflow prüft nur den
  statischen v2-Struktur-Vertrag (Warn-Zeile + ≥1 numerische Zeile genügt). Ob die tatsächlich
  im Preset aktivierten Metriken korrekt angezeigt werden, prüft #1107, nicht dieses Issue.
- **Trip-Briefing-Validator unberührt:** `briefing_mail_validator.py` ist nicht Teil dieses
  Workflows; sein Vertrag (Stundentabellen pro Etappe, kein Compare-Bezug) bleibt unverändert.
- **AC-8 ist an den #1110-Deploy gekoppelt:** Der E2E-Nachweis gegen eine echte v2-Mail ist erst
  möglich, nachdem Staging den #1110-Commit ausgeliefert hat (~5 Min Auto-Deploy nach Push).
  Vor diesem Zeitpunkt kann AC-8 nur gegen ein synthetisches v2-Fixture (AC-1) vorab-bewiesen
  werden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Vertragsanpassung eines bestehenden Prüf-Tools (Hook) an einen bereits
  beschlossenen Renderer-Vertrag (#1110) — keine neue Architekturentscheidung, keine neue
  Abstraktionsebene.

## Changelog

- 2026-07-08: Initial spec erstellt — Issue #1108, folgt aus PO-Umscoping von #1110 §8.
