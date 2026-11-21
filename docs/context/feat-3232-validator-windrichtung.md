# Context: feat-3232-validator-windrichtung

## Request Summary
Issue #3232 (Epic #3222, Nachzug zu #3228): Die beiden Mail-Validatoren (Trip-Briefing und
Orts-Vergleich) sollen die Windrichtungs-Färbung (Tönung + Ampelpunkt der Wind-Zelle je Stunde,
beim Vergleich zusätzlich die Windrichtungs-Zeile) gegen ein explizites Soll prüfen
(`--windrichtung JSON`). Ohne den Schalter bleibt das Verhalten unverändert. Eigener Workflow,
weil Validator-Änderungen nie im Feature-Workflow laufen, dessen Ergebnis sie prüfen.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/briefing_mail_validator.py` | neue `pruefe_windrichtung`, Helfer `_etappen_tabellen_attrs` (aus `_soll_ampel` herausgezogen), `validate_message(windrichtung=…)`, CLI `--windrichtung` |
| `.claude/hooks/email_spec_validator.py` | Windrichtungs-Zeile + Wind-Zelle je Ort gegen Soll, CLI `--windrichtung` |
| `.claude/hooks/_soll_aus_konfiguration.py` | `zellstufe()` (Stufe aus `<td>`-Attribut), gemeinsam genutzt |
| `scripts/send_gate_test_mails.py` | Soll-Stufen explizit: 4. Tupel-Element in `RAD_ETAPPEN`, `windrichtung_soll()["wind_zellen"]`, `COMPARE_WIND_STUFEN` / `compare_windrichtung_soll()["orte"]`; druckt schon „Soll Windrichtung:" (Z. 564/569) |
| `.claude/commands/e2e-verify.md` | Aufruf um `--windrichtung` ergänzen |
| `docs/reference/mail_validators.md` | Abschnitt für den neuen Schalter (analog `--konfig`, Z. 137 ff.) |
| `tests/tdd/test_feat_3228_windrichtung_validatoren.py` (neu) | Gold-Standard: echte Renderer → `build_mime_message` → `validate_message`; Gegenprobe per String-Ersetzung |

## Existing Patterns
- `--konfig PFAD` (#3047): optionales Soll, ohne Schalter unverändertes Verhalten — gleiches Muster.
- `_soll_ampel` prüft Ampelfarben der Etappen-Stundentabellen über `<td>`-Attribute; der Entwurf zieht das Tabellen-Parsing in `_etappen_tabellen_attrs` heraus (reine Refaktorierung, beide nutzen es).
- Soll-Werte stehen explizit im Sendeskript, der Validator rechnet die Stufe nicht nach (Schutz gegen Selbstbestätigung).

## Dependencies
- Upstream: Renderer-Ausgabe aus #3228 (Wind-Zelle mit verschmolzenem Kompass, Tönung), `design_tokens.tone_css`, `_soll_modul()._REG`.
- Downstream: `/e2e-verify` (ruft Validatoren mit der Soll-Zeile aus dem Sendeskript), Renderer-Commit-Gate, bestehende Validator-Tests (`tests/tdd/test_issue_733_briefing_mail_validator.py`, `test_einstellung_gleich_mail_validatoren.py`, `test_3047_*`).

## Existing Specs
- `docs/specs/modules/feat_3228_windrichtung_mail.md` — Soll-Stufen, Abschnitt „Validatoren gegen echt zugestellte Staging-Mail"
- `docs/specs/modules/feat_3222_windrichtung.md` — Epic-Spec
- `docs/specs/modules/feat_3047_einstellung_gleich_mail_pruefkatalog.md` — `--konfig`-Muster

## Stand des Entwurfs
Entwurf (hooks.patch + send_gate_soll.patch + Testdatei) liegt im Issue-Body; beide Patches lassen
sich auf dem aktuellen Stand sauber anwenden (`git apply --check` ok, 2026-11-21).

## Risks & Considerations
- Änderung an `.claude/hooks/` = Gate-Code → hohes Risiko, Adversary ≥2 Runden, PO-`override` nötig.
- Refaktorierung `_soll_ampel` darf bestehende Ampel-Prüfung nicht verändern (bestehende Tests grün halten).
- Alte Gate-Mails ohne Soll-Zeile und andere Mailpfade: ohne `--windrichtung` exakt unverändert.
- Segment-Zuordnung „Segment N = N-te Etappen-Stundentabelle" ist positionsabhängig; fehlende Tabelle muss als Fehler gemeldet werden, nicht still übersprungen.
- Mutations-Gegenprobe: jede Verfälschung einer Zelltönung muss genau eine Meldung erzeugen.

## Analysis

### Type
Feature (Gate-/Validator-Erweiterung, Nachzug #3228)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | `_etappen_tabellen_attrs` (aus `_soll_ampel` herausgezogen, verhaltensgleich), `pruefe_windrichtung`, `validate_message(windrichtung=)`, CLI `--windrichtung` |
| `.claude/hooks/email_spec_validator.py` | MODIFY | `_find_location_hour_table(roh=)`, `pruefe_windrichtung_orte`, `validate_message(windrichtung=)`, CLI `--windrichtung` |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | `zellstufe()` (Tönung + Ampelpunkt einer Zelle) |
| `scripts/send_gate_test_mails.py` | MODIFY | Soll-Stufe je Stunde (4. Tupel-Element), `wind_zellen`, `COMPARE_WIND_STUFEN`/`orte` |
| `.claude/commands/e2e-verify.md` | MODIFY | Validator-Aufrufe (Z. ~176–179, DE+EN) um `--windrichtung '<Zeile "Soll Windrichtung">'` |
| `docs/reference/mail_validators.md` | MODIFY | Abschnitt `--windrichtung` analog `--konfig` (Soll-Format, Positionsregel, Exit-Codes, nur Format full) |
| `tests/tdd/test_feat_3228_windrichtung_validatoren.py` | CREATE | Gold-Standard aus Issue-Entwurf (11 Tests) + Zusatztests unten |

### Scope Assessment
- Files: 6 MODIFY + 1 CREATE
- Estimated LoC: ~+150/-15 Code, ~+170 Tests, ~+25 Doku
- Risk Level: MEDIUM (Gate-Code unter `.claude/hooks/` → PO-`override`, Adversary ≥2 Runden; Refaktorierung `_soll_ampel` verhaltensgleich)

### Verifikation des Entwurfs (2026-11-21)
- Beide Patches aus dem Issue-Body lassen sich auf den aktuellen Stand anwenden (`git apply --check`).
- In einer Arbeitskopie: neue 11 Tests + `test_feat_3228_windrichtung_mail*.py` + `test_issue_733_briefing_mail_validator.py` grün (54 passed).

### Technical Approach
Entwurf aus dem Issue übernehmen, mit diesen Korrekturen (strategische Bewertung, Plan/Sonnet):
1. **Eingabeprüfung `--windrichtung` (Befund mittel):** in `email_spec_validator.py` liegt `json.loads` außerhalb des `try` → Traceback/Exit 1 (= „Spec verletzt“, nicht unterscheidbar). Im Briefing-Validator Exit 2 mit irreführender Meldung „Mail konnte nicht geladen werden“. Beide: Soll früh parsen und validieren (`dict`; Schlüssel `wind_zellen` bzw. `orte`; Segment-IDs numerisch), Fehler `FEHLER: --windrichtung ungültig: …` + `sys.exit(2)`.
2. **Soll gegeben, Format ≠ full (Befund mittel):** Briefing-Validator prüft dann still nichts → Meldung `SOLL: Windrichtung nur im Format full prüfbar (X-GZ-Format=…)`.
3. **`zellstufe` Punkt-Erkennung (Befund mittel):** Teilstring `"border-radius:50%"` toleriert keine Leerzeichen, anders als `ampel_farbe` (`border-radius:\s*50%`). Gleichen Regex verwenden, damit eine geänderte Schreibweise laut wird statt still „Punkt = Tönung“.
4. **Segment-Grenzen (gering):** `not 1 <= int(sid) <= len(tabellen)` statt `int(sid) > len(tabellen)` (sonst `sid<=0` → `tabellen[-1]`). Positionsregel „Segment N = N-te Etappen-Stundentabelle (ohne Nacht), lückenlose IDs ab 1“ im Docstring + Doku festhalten (stimmt für die Gate-Mail: Segment 1 + Rad-Segmente 2–5).
5. **Vergleich Stundenverlauf (optional):** Liste statt Menge vergleichen, damit die Meldung die Stunde nennt; Mengenvergleich maskiert fehlende Zellen nicht („fehlt“), daher kein Muss.
6. Zusatztests: ungültiges JSON → Exit 2 (beide CLIs), Format compact + Soll → Meldung, `sid` außerhalb → Meldung.
7. `e2e-verify.md` + `mail_validators.md` ergänzen.

### Dependencies
- Upstream: #3228 auf main (Renderer-Wind-Zelle mit Kompass, Tönung), `design_tokens.tone_css`, `_soll_modul()._REG`, `ampel_farbe`.
- Downstream: `/e2e-verify`, Renderer-Commit-Gate, Validator-Tests #733/#3047/einstellung_gleich/#3228.

### Open Questions
- keine Produktfrage. Technische Entscheidung für die Spec: Im Entwurf gilt eine getönte Zelle OHNE Ampelpunkt still als Punkt = Tönung. Korrektur: Ist die Tönung ≠ green und fehlt der Punkt, liefert `zellstufe` `Toenung X/Punkt fehlt` (laut statt still) — vorher am Renderer verifizieren, dass getönte Wind-Zellen immer einen Punkt tragen.
- Regression in der Arbeitskopie: Validator-Tests #3047/einstellung_gleich/#1148 grün bis auf zwei Falllisten-Tests (`test_testverweise_auffindbar`, `test_template_literal_titel_alle_gefunden`), die Frontend-Testdateien suchen — in der Kopie ohne `frontend/` erwartbar rot, kein Bezug zum Entwurf; in Phase 5 im Worktree erneut laufen lassen.
