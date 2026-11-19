# Context: feat-3153-name-orte (B5 aus Epic #3122)

## Request Summary
Der fertige Bau B5 (PR #3136, Branch `feat/3122-b5-name-orte`, Cloud-Sitzung, Adversary + Fix-Loop durch) ausliefern: einheitlicher Name „Orte“ (EN „Locations“) und Ein-Ort-Texte in Mail, Telegram, SMS, Befehlsantworten und API-Fehlertexten (ADR-0124 Nr. 10; Spec `docs/specs/modules/feat_3122_was_steht_wo.md` Teil B Nr. 16, AC-35, AC-36 — bereits vom PO freigegeben am 17.11.).

Kein Neubau. Arbeit: `origin/main` in den B5-Zweig mergen, Konflikte und semantische Konflikte (Golden-Dateien, neue Tests auf main mit altem Wortlaut) lösen, Kern-Tests grün, Validator-Nachweis gegen echt zugestellte Staging-Mail, Liefer-Workflow.

## Ausgangslage (Stand 19.11.)
- Merge-Base `b7e14cd4b`; main seither: B1b (#3140), #3101 (#3147), B2-Nachzug, Trip-Berichtsaufbau (#3149) — alles auf Prod (`8cfe49848`, 07:45 UTC).
- Textuelle Konflikte nur: `docs/reference/sms_format.md`, `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` (beide Seiten ergänzen Fälle/Abschnitte → zusammenführen).
- Auto-gemergt, aber auf beiden Seiten berührt: `src/output/renderers/comparison.py` (B5: Kopf/SMS-Anfang; main #3101/B1b: Adapter vor dem Renderer), `renderer_email_spec.md`, `tests/unit/test_compare_mail_blocks.py`.

## Related Files (B5-Seite, 92 Dateien)
| Datei | Relevanz |
|---|---|
| `src/output/renderers/comparison.py` | SMS-Anfang „Orte TT.MM.“ / „{Ort} TT.MM.“, „keine Daten“, Telegram-Kopf |
| `src/output/renderers/email/compare_html.py` | Kopf „ORTE“, Titel, Fuß „1 Ort · Vorlage …“, Knopf „In der App öffnen“ |
| `src/services/trip_command_processor.py` | Befehlsantworten ohne „Ortsvergleich“ |
| `src/i18n/messages/{de,en}/{vergleich,mail,versand,inbound,api,allgemein}.json` | alle Texte über den Katalog, `.one`/`.other` |
| `.claude/hooks/email_spec_validator.py` | Prüfung Bereichsname mit `--konfig`, Ein-Ort-Fall |
| `.claude/hooks/_soll_aus_konfiguration.py` | Soll-Ableitung (kleine Ergänzung) |
| `tests/tdd/test_orte_bereichsname_in_ausgaben.py`, `test_orte_befehlsantworten_ohne_alten_namen.py` | neue Nachweise B5 |
| Golden: `tests/golden/{vergleichs_mail,compare_briefing_aufbau,inbound,scheduler_texte,versand,amtliche_warnungen}/…`, `tests/fixtures/mail/compare_{de,en}.eml` | neu erzeugte Ausgaben |

## Main-Seite, die B5 berühren kann
| Datei | Risiko |
|---|---|
| `tests/fixtures/ein_vokabular_3101/*.golden.json`, `pruefkatalog_golden.sha256.json` | enthalten Orte-Ausgaben mit altem Wortlaut → nach Merge gezielt neu erzeugen, Diff nur Namensänderung |
| `tests/golden/f10_vergleich_flaechen/hub_orte.*.html` | Oberflächen-Golden, prüfen |
| `src/services/compare_alert.py`, `compare_briefing_aufbau.py`, `placements_beispiel.py` (SMS-Beispielzeile der Tabelle) | erzeugen Orte-Texte über den Renderer; Beispielzeile muss neuen SMS-Anfang tragen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | Konflikt; beide Fallgruppen behalten |

## Existing Patterns
- Golden-Dateien werden per Regenerierungsschalter der jeweiligen Tests neu erzeugt; Diff je Datei prüfen (nur Namenswechsel erlaubt).
- Mail-Inhalts-Commits sind durch das Renderer-Commit-Gate geschützt (Modus-Matrix + Validator frisch grün).
- Validator `email_spec_validator.py` gegen Staging-Postfach (Stalwart), `--konfig`.

## Dependencies
- Upstream: Renderer-Adapter aus #3101 (`compare_metric_ids.py`), View-Model aus B1b.
- Downstream: Scheduler-Versand Orte, Inbound-Befehle, Alarm-Texte Orte, Tabelle „Was steht wo“ (SMS-Beispielzeile, B2).

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (freigegeben) — Teil B Nr. 16, AC-35/36.
- ADR-0124 Nr. 10.

## Risks & Considerations
- Semantische Konflikte: neue Tests/Golden auf main mit „Vergleich“-Wortlaut werden nach dem Merge rot — nicht als Regression werten, sondern prüfen, ob es nur der Name ist.
- SMS-Kopf 5 Zeichen kürzer → in voll gekürzten SMS passt teils eine Wertzelle mehr (bewusst, PR-Text).
- „Orte-Abo“ als neues sichtbares Wort (Befehlsantworten) — bei der Abnahme #3037 zeigen.
- Abgrenzung zu #2798 (Reiter Orte, Anlegen, Menü) — nicht in diesem Schritt.

## Analysis

### Type
Feature (Auslieferung eines fertigen Baus; Spec `feat_3122_was_steht_wo.md` Teil B Nr. 16, AC-35/AC-36, freigegeben 17.11.). Kein neuer Spec-Inhalt; Phase 3 = Spec-Verweis/Bestätigung.

### Befund Probe-Merge (19.11., merge-tree origin/main × origin/feat/3122-b5-name-orte)
- main `8cfe49848`, B5 `dbf189a25`, Merge-Base `b7e14cd4b`.
- **Textkonflikte nur zwei:** `docs/reference/sms_format.md`, `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` (beide Seiten ergänzen → zusammenführen, nichts verwerfen).
- Auto-merged beidseitig: `docs/reference/renderer_email_spec.md`, `tests/unit/test_compare_mail_blocks.py`. `comparison.py` ist NICHT beidseitig berührt.
- **Semantische Konflikte (sicher rot nach Merge):** `tests/fixtures/ein_vokabular_3101/{b2b_altpfad_kanalauswahl,b2b_altpfad_layouts,b2b_tabelle,versand_altpfad_kanalauswahl,versand_altpfad_layouts,versand_tabelle}.golden.json` + `pruefkatalog_golden.sha256.json` tragen „Vergleich TT.MM.:“ (SMS/Premium-SMS, auch SMS-Beispielzeile der Tabelle „Was steht wo“) und „ORTS-VERGLEICH“ (Mail-Text, Telegram-Kopf). Neu erzeugen mit `EIN_VOKABULAR_GOLDEN_SCHREIBEN=1` über `tests/tdd/test_3101_ein_vokabular.py`; Diff darf nur Namenswechsel + ggf. eine zusätzliche Wertzelle (SMS-Kopf 5 Zeichen kürzer) zeigen.
- Main-seitig neue Tests auf Orte-Ausgaben, nach Merge gezielt laufen lassen: `test_orte_ausgaben_lesen_view_model.py`, `test_einstellung_gleich_mail_orte_tabelle.py`, `test_einstellung_gleich_mail_fallliste.py`, `test_3101_ein_vokabular.py`, `test_compare_render_options_resolver.py`, `test_placements_*`, `tests/unit/test_compare_mail_blocks.py`, `test_compare_top_n_render_invariance.py`.
- `tests/golden/f10_vergleich_flaechen/*` = Oberflächen-Golden (Frontend); B5 ändert kein Frontend → unberührt, Reiter-/Menünamen gehören zu #2798.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| (B5-Zweig, 92 Dateien) | MERGE | 15 src-Dateien: i18n-Kataloge DE/EN, `comparison.py`, `compare_html.py`, `trip_command_processor.py`; Tests/Golden/Validator |
| `docs/reference/sms_format.md` | MODIFY | Konflikt zusammenführen |
| `tests/fixtures/einstellung_gleich_mail/fallliste_orte.json` | MODIFY | Konflikt zusammenführen (beide Fallgruppen) |
| `tests/fixtures/ein_vokabular_3101/*.golden.json` + sha256 | MODIFY | neu erzeugen (nur Namenswechsel) |

### Scope Assessment
- Files: ~95 (fast alles fertig im Zweig), Eigenarbeit ~10 Dateien
- Estimated LoC eigen: ca. +40/-40 (Konflikte), Golden-Regenerierung maschinell
- Risk Level: MEDIUM — reine Textänderung, aber in allen vier Kanälen und Befehlsantworten; Golden-Diffs einzeln auf „nur Name“ prüfen.

### Technical Approach
1. Arbeitszweig aus `origin/feat/3122-b5-name-orte`, `origin/main` hineinmergen, zwei Konflikte zusammenführen.
2. B5-Tests + main-seitige Orte-Tests (Liste oben) laufen lassen; rote nur per Regenerierungsschalter neu erzeugen, wenn Diff ausschließlich Namenswechsel ist.
3. Kein neuer RED-Test nötig: B5 bringt `test_orte_bereichsname_in_ausgaben.py` und `test_orte_befehlsantworten_ohne_alten_namen.py` (AC-35/36). RED-Nachweis in Phase 4: diese Tests gegen main-Stand (rot).
4. `email_spec_validator.py --konfig` gegen echt zugestellte Staging-Mails: drei Orte + ein Ort, DE + EN.
5. Liefer-Workflow (PR „Refs #3153“, PR #3136 ersetzen/schließen), Prod-Deploy, Selftest.

### Dependencies
Upstream: Renderer-Adapter #3101 (`compare_metric_ids.py`), View-Model B1b. Downstream: Scheduler-Versand Orte, Inbound-Befehle, Orte-Alarme (`compare_alert.py`), Tabelle „Was steht wo“ (SMS-Beispielzeile kommt aus dem Renderer, ändert sich automatisch).

### Open Questions
- keine (Spec freigegeben; „Orte-Abo“ in Befehlsantworten ist Teil davon, Abnahme #3037 zeigt es).
