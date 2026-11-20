---
entity_id: feat_3156_renderer_nachzug_roh_einfach
type: feature
created: 2026-11-20
updated: 2026-11-20
status: draft
version: "1.0"
workflow: feat-3156-renderer-nachzug-roh-einfach
tags: [renderer, katalog, roh-einfach, epic-3122]
---

# Renderer-Nachzug Roh/Einfach aus einer Quelle (#3156)

## Approval

- [ ] Approved

## Purpose

Die Katalog-Quelle `zwei_formen_stellen` legt fest, an welcher Stelle (E-Mail, Telegram, Stundenverlauf, 3-Tages-Ausblick) eine Metrik Roh und Einfach hat. Der Renderpfad entscheidet bisher über eigene, nicht deckungsgleiche Listen. Diese Spec zieht die Renderer auf die eine Quelle nach und baut die zwei offenen Fälle: Wortstufe der Regenwahrscheinlichkeit in der Trip-Nur-Text-Mail und Ampelpunkt der Regenwahrscheinlichkeit in der Orte-HTML-Übersicht. Sie setzt nur um, was die freigegebene Spec `feat_3122_was_steht_wo.md` (Teil A Nr. 4, AC-5, AC-6, Nr. 8, AC-11) und ADR-0124 Nr. 5 festlegen, und ändert dieses Verhalten nicht.

## Source

- **File:** `src/app/metric_catalog.py` (Quelle), Verbraucher in `src/output/renderers/`
- **Identifier:** `STELLEN_ZWEI_FORMEN` / `zwei_formen_stellen`, `fmt_val` (pop-Zweig), `_friendly_effective`, `resolve_hourly_metric_formats`, `_hour_einfach_text`, `_FRIENDLY_AMPEL_METRIC_IDS`

> **Schicht-Hinweis:** Alles liegt im Python-Core (`src/app/`, `src/output/renderers/`, `src/services/`) und im Validator unter `.claude/hooks/`. Kein Go, kein Frontend (Frontend-Listen gehören zu #3154).
> **Trip/Ortsvergleich:** Die Änderungen wirken in den geteilten Katalog-Funktionen für beide Flächen; es entsteht keine neue Komponente.
> **Mandantentrennung:** Keine Nutzerdaten werden bewegt oder geschrieben; reine Darstellung. Die Tests laufen mit zwei verschiedenen Konfigurationen (Trip und Orte), nicht gegen `"default"`.
> **Kanäle:** E-Mail (HTML und Nur-Text) und Telegram sind betroffen; SMS und Premium-SMS bleiben unverändert (keine Wahl, ADR-0124 Nr. 5).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/metric_catalog.py` | MODIFY | `rain_probability` bekommt `format_modes=("raw","simplified")` (Standard bleibt raw). Neue abgeleitete Ampel-Menge (E-Mail-Stelle mit Zwei-Formen UND Schwellen: wind, gust, precipitation, rain_probability). `outlook_friendly_capable` und `normalize_outlook_metric_formats` fragen `"outlook" in zwei_formen_stellen`. `OUTLOOK_FRIENDLY_CAPABLE` bleibt als abgeleiteter Alias für den Frontend-Drift-Test bis #3154. |
| `src/output/renderers/email/helpers.py` | MODIFY | `fmt_val` pop-Zweig: Einfach ohne HTML liefert die Wortstufe (`format_rain_probability_scale`). `_AMPEL_CAPABLE_METRIC_IDS` wird Alias auf die Katalog-Menge (Alarm-Pfad und Validator importieren ihn). |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_FRIENDLY_AMPEL_METRIC_IDS` und die feste Liste in `_hour_einfach_text` kommen aus dem Katalog. |
| `src/output/renderers/compare_metric_ids.py` | MODIFY | `_friendly_effective` entscheidet je Stelle über `zwei_formen_stellen` statt über `len(format_modes)>1`. |
| `src/output/renderers/compare_outlook_metric_ids.py` | MODIFY | `resolve_hourly_metric_formats` filtert auf `"hourly" in zwei_formen_stellen`. |
| `src/services/placements.py` | MODIFY | `heutige_form` und `_regel_changes` nutzen die Katalog-Ampelmenge. |
| `.claude/hooks/_soll_aus_konfiguration.py` | MODIFY | Validator-Soll: Trip-Nur-Text erwartet für rain_probability bei Einfach die Wortstufe; Imports auf die Quelle. |
| `tests/tdd/test_katalog_stellen_formen.py` | MODIFY | Deckungstests umgeschrieben auf „Renderer folgt der Quelle“. |
| `tests/tdd/test_einstellung_gleich_mail_trip_tabelle.py` | MODIFY | xfail(strict) für Nur-Text-Wortstufe entfernt. |
| `tests/tdd/test_einstellung_gleich_mail_orte_tabelle.py` | MODIFY | xfail(strict) für HTML-Ampel entfernt. |
| `fallliste_trip.json`, `fallliste_orte.json` (Prüfkatalog) | MODIFY | Fälle `T-3122-B1B-AC5-REGENWAHRSCHEINLICHKEIT-NUR-TEXT` und `O-3122-AC5-REGENWAHRSCHEINLICHKEIT-HTML-AMPEL` auf `gruen`. |
| `tests/helpers/metrik_listen_scan.py`, `tests/unit/test_metrik_listen_register_ratchet.py` | MODIFY | Ratsche Metrik-Listen-Register: entfernte Listen austragen, neue Ableitung eintragen. |
| `tests/tdd/test_outlook_darstellungsform.py` | MODIFY | an die abgeleitete Fähigkeitsabfrage angepasst. |

### Estimated Changes

- Files: ca. 14
- LoC: Produktion +70/-40, Tests und Wächter +80/-60
- Effort: Medium (Mail-Inhalt, Renderer-Commit-Gate)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `docs/specs/modules/feat_3122_was_steht_wo.md` | spec | Übergeordnete freigegebene Spec (Teil A Nr. 4, Nr. 8, AC-5, AC-6, AC-11) |
| `docs/adr/0124-was-steht-wo-eine-tabelle.md` | adr | Nr. 5: eine Quelle für Roh/Einfach |
| `src/services/weather_metrics.py` `format_rain_probability_scale` | function | Wortstufe der Regenwahrscheinlichkeit (Grenzen 25/50/75; die Katalog-Schwellen 30/60/80 gelten nur für die Ampelfarbe) |
| `src/services/placements.py` | module | Nutzt die Quelle bereits; Zielmuster |
| `src/output/renderers/alert/hours.py`, `src/services/notification_service.py` | module | Importieren `_AMPEL_CAPABLE_METRIC_IDS` (Alarm-Pfad); Alias muss bleiben, Verhalten unverändert |
| `frontend/.../outlookFriendlyCapability.ts` und Drift-Test | test | Ruft `OUTLOOK_FRIENDLY_CAPABLE` live; Alias bleibt bis #3154 |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | hook | Staging-Mail-Validatoren mit `--konfig` |

## Implementation Details

Reihenfolge der Umsetzung (jede Stufe in sich testbar, ein Workflow):

1. **Katalog und Deckungstest:** `rain_probability` erhält die zweite Form; die Ampel-Menge wird aus `zwei_formen_stellen` (E-Mail) plus vorhandenen Schwellen abgeleitet. thunder bleibt außen, weil ohne Schwellen: Ampelpunkt nur in der HTML-Mail über den eigenen Zweig, in Texten immer Stufenwort.
2. **Fall 1, Trip-Nur-Text:** Im pop-Zweig von `fmt_val` liefert Einfach ohne HTML die Wortstufe, so wie bei wind/gust/precipitation. Es wird nicht über `build_friendly_keys` gearbeitet. Die HTML-Trip-Mail bleibt unverändert, weil sie die Ampel über `indicator_keys` bekommt. Validator-Soll gleichziehen.
3. **Fall 2, Orte-HTML-Übersicht:** `_FRIENDLY_AMPEL_METRIC_IDS` aus der Katalog-Ampelmenge; rain_probability zeigt bei Einfach den Ampelpunkt. Beim Bau prüfen, über welchen Pfad die Einfach-Zelle ankommt (Zeilenformat aus placements oder `channel_layouts`), damit der Ampel-Zweig tatsächlich greift.
4. **Listenablösung:** Ausblick (`normalize_outlook_metric_formats`, `outlook_friendly_capable`), Orte-Stundenverlauf (`resolve_hourly_metric_formats`, `_hour_einfach_text`), Orte-Telegram und Klartext (`_friendly_effective`) und placements entscheiden über die eine Quelle.
5. **Wächter:** Ratsche und Register, Modus-Matrix-Test, Validator `--konfig`, Staging-Mail-Validator.

Erwartete, von der Epic-Spec gewollte Verhaltensänderungen (nur dort, wo ein Einfach-Format gespeichert ist):

- Orte-Stundenverlauf: sunshine und wind_direction bekommen dort kein Einfach mehr (Stundenverlauf-Spalte Sonne gesperrt, Windrichtung immer Kompass).
- Orte-Telegram und Klartext: rain_probability bekommt Einfach; thunder verliert Einfach, der Text zeigt ohnehin das Stufenwort, die Ausgabe bleibt sichtbar gleich.
- Orte-HTML-Übersicht: rain_probability wechselt bei Einfach von Wortstufe auf Ampelpunkt.

Nicht im Scope: Alarm-Pfad (ADR-0124 Nr. 11), Frontend-Listen (`INDICATOR_MAP`, `outlookFriendlyCapability.ts`, `hourlyFriendlyMap.ts`, #3154), `SMS_FORMAT_MODE_METRIC_IDS` (steuert die Kürzelform, keine Fähigkeitsabfrage), die schreibende Migration (B6) und die Änderung „Nur-Text folgt der HTML-Mail“ für Altbestand (Epic-Spec Nr. 8, Migration B6).

Bestandsdaten (Prod, gemessen 2026-11-20): `hourly_metric_formats=true` bei einem Abo ohne sunshine/wind_direction, also keine Änderung; Orte-`channel_layouts` mit `use_friendly_format:true` für rain_probability je ein Abo (email, telegram), wechselt bewusst; Trip ohne solchen Eintrag.

## Expected Behavior

- **Input:** Ein Trip- oder Orte-Abo mit gespeichertem Format Roh oder Einfach je Metrik und Stelle.
- **Output:** Jede Stelle mit zwei Formen liefert in der echten Ausgabe beide Formen; jede Stelle ohne zwei Formen ignoriert das gespeicherte Format.
- **Side effects:** Keine Schreibzugriffe auf Nutzerdaten; `/api/metrics` liefert für rain_probability zusätzlich `simplified` in `format_modes` (Frontend nutzt das Feld nur als optionalen Typ, keine UI-Wirkung; im Editor gegenprüfen).

## Definition of Done

- AC-1 bis AC-10 durch die benannten Tests grün; die beiden xfail(strict)-Tests ohne xfail grün, beide Falllisten-Einträge auf `gruen`.
- Adversary mit Mutations-Gegenprobe ohne offenen Befund; alle sechs CI-Checks grün.
- Renderer-Commit-Gate: Modus-Matrix-Test und zuständige Mail-Validatoren frisch grün.
- Staging: Mail-Validator mit `--konfig` gegen echt zugestellte Trip- und Orte-Mail (HTML und Nur-Text) grün; Prod-Deploy mit Selftest-Exit 0.
- Mit dem Bau nachgezogen: `renderer_email_spec.md`, `telegram_format.md`, `mail_validators.md` (soweit Ausgabe betroffen).

## Test Plan

### Automated Tests (TDD RED)

Alle Tests laufen durch den echten Renderer mit echten Konfigurationen, ohne `Mock()`/`patch()`.

- [ ] Test 1: GIVEN Trip mit rain_probability Einfach WHEN die Nur-Text-Mail gerendert wird THEN steht die Wortstufe (bestehende Wortskala 25/50/75 wie im Orte-Vergleich und Ausblick), bei Roh die Zahl (bestehender xfail-Test wird grün, xfail entfernt).
- [ ] Test 2: GIVEN dieselbe Konfiguration WHEN die HTML-Trip-Mail gerendert wird THEN ist die Ausgabe gegenüber dem Stand vorher byte-gleich (Ampelpunkt).
- [ ] Test 3: GIVEN Orte-Abo mit rain_probability Einfach WHEN die HTML-Übersicht gerendert wird THEN steht ein Ampelpunkt statt Wortstufe, bei Roh die Zahl (bestehender xfail-Test wird grün).
- [ ] Test 4: GIVEN Roh/Einfach-Matrix über jede Metrik und jede Stelle WHEN gerendert THEN unterscheidet sich die Ausgabe genau dort, wo `zwei_formen_stellen` zwei Formen nennt (Parametrisierung aus der Quelle, Fallliste gruen).
- [ ] Test 5: GIVEN sunshine/wind_direction mit gespeichertem Einfach im Orte-Stundenverlauf WHEN gerendert THEN bleibt die Ausgabe gleich wie bei Roh.
- [ ] Test 6: GIVEN Orte-Telegram mit rain_probability Einfach bzw. thunder Einfach WHEN gerendert THEN zeigt rain_probability Einfach, thunder weiterhin das Stufenwort.
- [ ] Test 7: GIVEN Altbestand ohne gespeicherte Einfach-Einstellung (Trip und Orte, je eine eigene Konfiguration) WHEN gerendert THEN ist die Ausgabe zeichengleich zum Stand vor der Änderung.
- [ ] Test 8: GIVEN gespeichertes Format für die SMS WHEN die SMS gerendert wird THEN ist sie zeichengleich.
- [ ] Test 9: Deckungstest „Renderer folgt der Quelle“: jede Fähigkeitsabfrage im Renderpfad liefert dasselbe wie `zwei_formen_stellen` (Alias `OUTLOOK_FRIENDLY_CAPABLE` bleibt für den Frontend-Drift-Test deckungsgleich).
- [ ] Test 10: Ratsche Metrik-Listen-Register zählt die entfernten und neu abgeleiteten Listen korrekt.

### Live-Nachweis

- Staging-Mail-Validator (`briefing_mail_validator.py`, `email_spec_validator.py`) mit `--konfig` gegen echt zugestellte Mails: HTML und Nur-Text grün; Renderer-Commit-Gate (Modus-Matrix-Test und Validator frisch grün).

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Regenwahrscheinlichkeit auf Einfach in der E-Mail / When die Nur-Text-Mail erzeugt wird / Then steht dort die Wortstufe der bestehenden Regenwahrscheinlichkeits-Skala (unwahrscheinlich/möglich/wahrscheinlich/sehr wahrscheinlich, Grenzen 25/50/75, dieselbe wie Orte-Vergleich und Ausblick) statt der Zahl, und mit Roh steht die Zahl.
  - Test: Echte Nur-Text-Mail aus dem Renderer, je einmal Roh und Einfach, Vergleich der Zelle der Regenwahrscheinlichkeit.
- **AC-2:** Given derselbe Trip mit Regenwahrscheinlichkeit auf Einfach / When die HTML-Mail erzeugt wird / Then zeigt sie weiterhin den Ampelpunkt und ist gegenüber dem Stand vor der Änderung unverändert.
  - Test: HTML-Ausgabe vor und nach Änderung bytegleich, Ampelpunkt in der Zelle vorhanden.
- **AC-3:** Given ein Orte-Abo mit Regenwahrscheinlichkeit auf Einfach / When die HTML-Übersicht der Mail erzeugt wird / Then zeigt die Zelle einen Ampelpunkt (nicht die Wortstufe), und mit Roh die Zahl.
  - Test: Echte Orte-HTML-Mail, Zelle der Regenwahrscheinlichkeit je Roh und Einfach.
- **AC-4:** Given Ausblick, Orte-Stundenverlauf und Orte-Telegram/Klartext mit gespeichertem Einfach / When die Ausgabe erzeugt wird / Then entscheidet allein die Katalog-Liste „zwei Formen je Stelle“, ob Einfach wirkt, und keine zweite Fähigkeitsliste im Renderpfad widerspricht ihr.
  - Test: Matrix über alle Metriken und Stellen, Ausgabe unterscheidet sich genau dort, wo die Liste zwei Formen nennt (AC-6 der Epic-Spec).
- **AC-5:** Given Sonnenstunden oder Windrichtung mit gespeichertem Einfach im Orte-Stundenverlauf / When der Stundenverlauf erzeugt wird / Then ist die Ausgabe gleich der mit Roh, weil dort nur eine Form existiert.
  - Test: Stundenverlauf-Ausgabe für beide Formate ist identisch.
- **AC-6:** Given Orte-Telegram mit Regenwahrscheinlichkeit auf Einfach und Gewitter auf Einfach / When Telegram oder Klartext erzeugt wird / Then zeigt die Regenwahrscheinlichkeit Einfach und das Gewitter wie bisher das Stufenwort.
  - Test: Telegram-Text aus dem echten Renderer, beide Metriken.
- **AC-7:** Given ein Bestands-Abo ohne gespeicherte Einfach-Einstellung (Trip und Orte) / When das Briefing erzeugt wird / Then ist die Ausgabe in jeder Stelle zeichengleich zu vorher (AC-11 der Epic-Spec).
  - Test: Zeichengleichheit vor und nach der Änderung für je ein Trip- und ein Orte-Abo ohne Einfach-Angabe.
- **AC-8:** Given ein gespeichertes Format an einer Stelle ohne zwei Formen, die SMS oder Premium-SMS / When erzeugt / Then bleibt die Ausgabe unverändert; SMS, Alarm-Pfad und Frontend-Listen (#3154) werden nicht angefasst.
  - Test: SMS-Ausgabe zeichengleich; Alarm-Ausgabe unverändert.
- **AC-9:** Given der Nachzug ist gebaut / When die Wächter laufen / Then sind die beiden xfail(strict)-Tests grün und ohne xfail, beide Falllisten-Einträge stehen auf `gruen`, der Deckungstest prüft „Renderer folgt der Quelle“, die Ratsche Metrik-Listen-Register ist gepflegt und das Validator-Soll erwartet die Wortstufe.
  - Test: Die genannten Testdateien laufen grün; Falllisten werden vom Prüfkatalog-Test ausgewertet.
- **AC-10:** Given die Änderung liegt auf Staging / When der Staging-Mail-Validator mit `--konfig` echt zugestellte HTML- und Nur-Text-Mails prüft / Then ist das Ergebnis grün (Exit 0).
  - Test: Validator-Lauf gegen Staging-Mail im Test-Postfach, Trip und Orte, HTML und Nur-Text.

## Known Limitations

- Die Nur-Text-Mail folgt bei Altbestand erst mit der Migration (B6) der HTML-Mail; hier wirkt Einfach nur, wo `format_mode="simplified"` gespeichert ist.
- Frontend-Listen und die Editor-Anzeige bleiben bis #3154 unverändert; der Alias `OUTLOOK_FRIENDLY_CAPABLE` bleibt bis dahin.
- Fällt das Änderungsvolumen über das LoC-Gate, werden Schritte 4 und 5 als eigenes Kind-Issue unter #3122 abgespalten.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0124 (Nr. 5), keine neue Entscheidung
- **Rationale:** Diese Spec setzt die bereits getroffene Entscheidung „eine Quelle für Roh/Einfach“ im Renderpfad um; es weicht nichts davon ab.

## Changelog

- 2026-11-20: Initial spec created
- 2026-11-20 (Phase 5): Wortstufen-Grenzen präzisiert: bestehende Skala `format_rain_probability_scale` (25/50/75), damit jeder Kanal dieselben Wörter zeigt; 30/60/80 sind die Ampelfarb-Schwellen. Keine Verhaltensänderung gegenüber der Freigabe-Absicht (Wortstufe wie bei Orte).
