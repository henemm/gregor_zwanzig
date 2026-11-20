# Context: feat-3155-ein-name-ausblick (Issue #3155, Scheibe B4 von #3122)

## Request Summary
Der 3-Tages-Ausblick soll überall gleich heißen („3-Tages-Ausblick“, EN „3-day outlook“) und von genau einer Stelle gesteuert werden, die in allen Ausgaben (HTML-, Nur-Text-, Kompakt-Mail, Telegram) gleich wirkt, auch für Bestands-Abos. „Mehrtages-Trend“ entfällt. Die Falllisten des Prüfkatalogs werden um Morgen/Abend und den Namen (DE/EN) erweitert; Mail-Validatoren Trip und Orte gehören dazu.

## Verbindliche Grundlage (bereits freigegeben)
- Spec `docs/specs/modules/feat_3122_was_steht_wo.md` (status approved, PO 2026-11-17). Scheibe B4 = ACs **8, 9, 12, 34**; Spec-Teil A Nr. 6 (eine steuernde Stelle), Nr. 8 (Umrechnung Altbestand, Ausblick-Zeilen), Teil B Nr. 13 (Speichern `outlook_reports`), Nr. 15 (Name). Dateiliste B4 in der Bau-Tabelle der Spec (Zeile B4).
- ADR-0124 Nr. 6 (eine steuernde Stelle ersetzt `show_outlook`, `multi_day_trend_reports`, `outlook_enabled`, „leere Liste = aus“), ADR-0055 Nr. 2, ADR-0104 (DE/EN über Katalog).
- Epic #3122 Abschnitt „Bau-Umfang F“.
- Eine Scheiben-Spec darf die ACs zitieren, aber nicht ändern.

## Stand der Vorgänger-Scheiben
- B1 (Speicherformat `placements`, `src/services/placements.py`, Resolver-Eingang) ist im Code: `resolve_outlook_reports`, `outlook_applies` (placements.py:252–272), `_legacy_outlook_reports` (placements.py:325) für die Umrechnung des Altbestands.
- B2/B3 (Endpoint, Karte `WasStehtWoKarte.svelte`, Schalter „Ausblick im Morgen-/Abend-Briefing“ schreiben `outlook_reports`) sind ausgeliefert (#3154 gemergt). B5 (#3153) geschlossen. B6 (#3157, Migration/Rückbau Altfelder) offen.

## Related Files
| Datei | Relevanz |
|---|---|
| `src/services/report_config_resolver.py:117–175` | Trip: mit Tabelle steuert das View-Model den Ausblick (`show_multi_day_trend = bool(view.outlook)`), ohne Tabelle Altpfad `show_outlook` + `multi_day_trend_reports` (Zeilen 150–175). Orte: `outlook_enabled` (233, 323, 415). |
| `src/services/placements.py` | `resolve_outlook_reports`, `outlook_applies`, `_legacy_outlook_reports` (Altbestand → eine Stelle). |
| `src/services/channel_list_resolver.py:99,129–258` | View-Model `outlook_reports`, `outlook` = `()` wenn Block aus. |
| `src/output/renderers/email/html.py:832,1189,1266,1272,1418` | `show_outlook` gate + Eyebrow `mail.ausblick.eyebrow`. |
| `src/output/renderers/email/plain.py:176,274,355,385` | dito Nur-Text. |
| `src/output/renderers/email/__init__.py:69,180,218` | Durchreichen `show_outlook`. |
| `src/output/renderers/email/outlook_state_hint.py:101` | Titel `mail.ausblick.titel`. |
| `src/output/renderers/trip_report.py:248–284` | Ausblick-Auswahl aus `view.outlook`, `options.show_outlook`. |
| `src/output/renderers/narrow.py:707,1029` | Telegram-Kopf `telegram.kopf.ausblick`. |
| `src/output/renderers/comparison.py:193,403,482,488,1144` | Orte-Mail/Telegram, `outlook_enabled`, `vergleich.ausblick.titel`, `telegram.kopf.ausblick`. |
| `src/output/renderers/email/compare_html.py:1403–1450` | Orte-HTML-Ausblick-Kopf (`vergleich.ausblick.eyebrow`/`titel`). |
| `src/services/compare_briefing_aufbau.py:114,147` | Orte: `outlook_enabled` durchgereicht. |
| `src/i18n/messages/{de,en}/mail.json` | `mail.ausblick.titel` = „Ausblick“/„Outlook“, `mail.ausblick.eyebrow` = „Ausblick · nächste 3 Tage“/„Outlook · next 3 days“. |
| `src/i18n/messages/{de,en}/telegram.json` | `telegram.kopf.ausblick` = „Ausblick“/„Outlook“. |
| `src/i18n/messages/{de,en}/vergleich.json` | `vergleich.ausblick.titel` schon „3-Tages-Ausblick“/„3-day outlook“, Eyebrow „AUSBLICK“/„OUTLOOK“. |
| `frontend/src/lib/components/shared/versand-tab/VTSchedulePlan.svelte:23,184–196` | Karte „Mehrtages-Trend“ (nur Trip) mit eigenen Morgen/Abend-Haken, schreibt `multi_day_trend_reports` — zweite steuernde Stelle neben `WasStehtWoKarte`. |
| `frontend/src/lib/i18n/messages/{de,en}/versand.json:44–45` | `versand.zeitplan.trend` „Mehrtages-Trend“, `trend_sub` „Sonntags · 3–7-Tage-Ausblick (optional)“ (falsch). |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json:73` | `wertebereiche.ausblick.titel` = „3-Tages-Vorschau“ (verbotener Name). Zeile 52 „Ausblick/Trend-Block“, Zeile 24 „Ausblick“. |
| `frontend/src/lib/i18n/messages/{de,en}/layout.json:56,63` | `layout.mail_inhalt.ausblick` = „Ausblick“ (prüfen, ob noch sichtbar). |
| `frontend/src/lib/i18n/messages/de/wetter.json:173–179` | Karte: „3-Tages-Ausblick“, Schalter „Ausblick im Morgen-/Abend-Briefing“. |
| `frontend/src/lib/components/shared/OutlookLayoutControls.svelte`, `WeatherMetricsTab.svelte`, `organisms/zustellung-tab/UebergangBlock.svelte` | weitere Fundstellen von Trend/Ausblick-Texten. |
| `.claude/hooks/briefing_mail_validator.py` (Trip), `.claude/hooks/email_spec_validator.py` (Orte) | Validatoren; prüfen bisher Ausblick-Tabelle über `mail.ausblick.spalte_tag`, nicht den Blocknamen. |
| `tests/fixtures/einstellung_gleich_mail/fallliste_trip.json`, `fallliste_orte.json` | Prüfkatalog: `trip-paar-ausblick-*` (21, Formate html/klartext/kompakt), `trip-ausblick-aus--show_outlook--*` (3), `O-AB-*` (Orte, html/klartext). Kein Morgen/Abend-, kein Telegram-, kein Namens-Fall. |
| `tests/tdd/test_einstellung_gleich_mail_trip.py` (+ Orte-Pendant über `tests/helpers/einstellung_gleich_mail_orte.py`) | Treiber der Falllisten. |

## Existing Patterns
- Nutzertexte nur über Katalog (`t(key, lang)`), Protokoll-Token nie übersetzen (`docs/reference/i18n_konventionen.md`).
- Neue Prüffälle als Einträge der Falllisten (statt eigener Einzeltests), Spec AC-8-Test-Zeile.
- Steuerung des Ausblicks über View-Model (`view.outlook == ()` ⇒ Block aus), Renderer lesen keine Block-Schalter selbst (Spec Nr. 7).

## Dependencies
- Upstream: `placements.py`, `channel_list_resolver.py`, Katalog `src/i18n`, Frontend-i18n.
- Downstream: alle vier Ausgaben Trip und Orte, beide Mail-Validatoren, Falllisten-Tests, Frontend-Reiter Versand (Zeitplan) und Wetter.

## Existing Specs
- `docs/specs/modules/feat_3122_was_steht_wo.md` (verbindlich, ACs 8/9/12/34)
- `docs/specs/modules/feat_3065_ausblick_stundenverlauf_resolver.md`, `fix_3061_ausblick_alle_groessen.md` (Vorgeschichte Ausblick-Auflösung)

## Offene Punkte für die Analyse
1. Wirkt die eine Stelle schon in allen Ausgaben, auch ohne gespeicherte Tabelle (Altbestand ohne `placements`)? `_options_bisher` nutzt weiter `show_outlook`/`multi_day_trend_reports`; laut Epic zeigen Kompakt-Mail und Telegram bei `show_outlook: false` den Ausblick trotzdem. Orte: Morgen/Abend gibt es im Altpfad nicht (`outlook_enabled`).
2. `VTSchedulePlan` „Mehrtages-Trend“-Karte: zweite steuernde Stelle — entfernen (Steuerung liegt in der Karte „Was steht wo“) statt nur umbenennen.
3. Blocktitel in der Trip-Mail (HTML-Eyebrow, Klartext, Kompakt) und Telegram-Kopf: welche Schlüssel tragen den sichtbaren Namen, wie lautet der Eyebrow künftig.
4. Falllisten-Erweiterung: Dimension Briefing-Typ (morning/evening), Telegram als Ausgabeform, Name DE/EN; Orte-Fallliste kennt kein Kompakt.
5. Validatoren: Prüfung „Blockname = 3-Tages-Ausblick“ und „Ausblick nur im eingestellten Briefing“.

## Risks & Considerations
- Renderer-Commit-Gate: Mail-Inhalts-Änderungen brauchen frischen Modus-Matrix-Test und Validator-Lauf.
- Altbestand ohne `placements` darf seine Ausgabe nicht still ändern, außer dort, wo die Spec es ausdrücklich verlangt (Ausblick-Schalter wirkt in jeder Ausgabe gleich; AC-12-Umrechnung).
- Frontend-Tests (`node --test`), E2E-Specs mit Texten „Mehrtages-Trend“/`report-*-trend`-Testids müssen nachgezogen werden.
- Zwei-Nutzer-Test, falls ein Endpoint berührt wird.

## Analysis

### Type
Feature (Scheibe B4 von Epic #3122; enthält den Fehler „Ausblick-Schalter wirkt in Kompakt-Mail und Telegram nicht“, Epic Abschnitt F).

### Befund Ist-Stand (geprüft)
- Trip mit `placements`: Ausblick hängt allein an `view.outlook` (`outlook_reports` × Stelle outlook) → wirkt in allen vier Ausgaben (report_config_resolver.py:139-146).
- Trip Altpfad `_options_bisher` (report_config_resolver.py:149-177): `show_multi_day_trend` nur aus `multi_day_trend_reports` (:174); `show_outlook` blendet nur HTML (html.py:1418) und Nur-Text (plain.py:355) aus. Kompakt (compact.py:259) und Telegram (narrow.py:1017-1026) zeigen den Ausblick bei `show_outlook:false` trotzdem.
- Orte: Altpfad entscheidet bereits über eine Stelle (`view.outlook`, `_abo_schalter` channel_list_resolver.py:159-170), keine Morgen/Abend-Unterscheidung (Spec Nr. 8: heutiges Verhalten). Mit Tabelle wird `outlook_enabled` ignoriert (korrekt).
- `ALTBESTAND_UEBER_UMRECHNUNG = False` (channel_list_resolver.py:39); Kommentar „B3 legt den Schalter um“ ist veraltet → gehört zu B6 (#3157).
- Zweite steuernde Stelle: Karte „Mehrtages-Trend“ in `VTSchedulePlan.svelte:181-199`, nur in der Trip-Anlage (TripNewEditor → WetterMetrikenVersandPanel → VersandTab). Schreibt `multi_day_trend_morning/evening` → `reportConfigPayload.ts:107-126`/`tripNewLogic.ts:326-327` → `multi_day_trend_reports` (heute bei Standard `[]`, Test `standardwerte_payload_paritaet_trip.test.ts:99-110`).
- Namen: Trip-HTML-Eyebrow `mail.ausblick.eyebrow` „Ausblick · nächste 3 Tage“; Zustandshinweis `mail.ausblick.titel` „Ausblick“; Trip-Nur-Text- und Kompakt-Blocktitel ist `mail.ausblick.naechste_etappen` „Nächste Etappen“ (outlook.py:355, compact.py:123, plain.py:391); Telegram `telegram.kopf.ausblick` „Ausblick“ (narrow.py:707,1029; comparison.py:1144). Orte `vergleich.ausblick.titel` schon richtig. Frontend: `versand.zeitplan.trend(_sub)`, `wertebereiche.ausblick.titel` „3-Tages-Vorschau“, `wertebereiche.schwelle.hinweis` „Ausblick/Trend-Block“, `layout.mail_inhalt.ausblick` „Ausblick“ (MailInhaltCard, Sichtbarkeit prüfen). Toter Hardcode `compare_html.py:1382 OUTLOOK_HEADING`.
- Validatoren: Soll in `.claude/hooks/_soll_aus_konfiguration.py:386-396` (`trip_soll`) und :765 (`orte_soll`) nur aus Altfeldern, kennt `placements`/`outlook_reports` nicht; Blockname wird nicht geprüft; `_check_compact_blocks` (briefing_mail_validator.py:660-687) nennt „Naechste Etappen“.
- Falllisten: Trip-Paartests rendern nur evening, kein Telegram (test_einstellung_gleich_mail_trip.py:128, :213); Orte-Helper `sende_orte_mail` (tests/helpers/einstellung_gleich_mail_orte.py:199) ohne `report_type`, ohne Telegram-Mitschnitt. Muster für beides in `*_tabelle.py` (`_ausblick_ueberall`, telegram_bubbles).

### Variantenvergleich „eine Stelle auch für Bestands-Abos“
| Kriterium | A: Altpfad-Ausblick über `_legacy_outlook_reports` | B: `ALTBESTAND_UEBER_UMRECHNUNG=True` | C: Kompakt/Telegram lesen `show_outlook` |
|---|---|---|---|
| Spec Nr. 6/8, AC-12 | konform (dieselbe Funktion wie Umrechnung, inkl. Kompakt-Ausnahme) | konform, zieht B6 hinein | widerspricht Nr. 6 |
| Stille Änderung anderer Abos | nur bewusst: Telegram bei `show_outlook:false` ohne Ausblick | ja (Reihenfolge, Formate, AC-11-Probelauf) | nein |
| Risiko | gering | hoch | mittel |

### Technical Approach (Entscheidung Tech Lead)
1. **Backend-Weiche, Variante A minimal:** in `_options_bisher`, nur Zweig mit `report_config`: `show_multi_day_trend = report_type in _legacy_outlook_reports(...)`. `show_outlook` steuert weiter nur die Großwetterlage (AC-12). Zweig ohne `report_config` (`dc.multi_day_trend_reports or ["evening"]`) unverändert lassen (sonst stiller Randfall `[]`). Orte-Ausgabe: keine Änderung nötig. Kommentar zu `ALTBESTAND_UEBER_UMRECHNUNG` auf B6 korrigieren.
2. **Anlage-Vorbelegung (AC-9):** Trend-Karte aus `VTSchedulePlan` entfernen; `baueReportConfigPayload`/`tripNewLogic` schreiben `multi_day_trend_reports` nach Spec-Nr.-6-Regel (`['morning']` nur wenn allein Morgen an, sonst `['evening']`; vorhandener Wert gewinnt). Orte-Anlage: neue Orte-Abos haben keine `placements` und bekämen im Altpfad den Ausblick in jedem Briefing → AC-9 (freigegeben, gilt für Trip UND Orte) verlangt Vorbelegung auch dort; Spec-Phase legt fest, wo die Orte-Anlage die Vorbelegung schreibt (bevorzugt `outlook_reports` über denselben Resolver-Eingang `resolve_outlook_reports`), statt AC-9 einzuschränken (ACs der Epic-Spec sind nicht änderbar).
3. **Ein Name:** `mail.ausblick.eyebrow`, `mail.ausblick.titel`, `telegram.kopf.ausblick` → „3-Tages-Ausblick“/„3-day outlook“; neuer Schlüssel `mail.ausblick.name` ersetzt `naechste_etappen` als Blocktitel in Nur-Text und Kompakt (Kompakt ASCII über `_ascii`); Frontend `wertebereiche.ausblick.titel`, `wertebereiche.schwelle.hinweis`; `versand.zeitplan.trend(_sub)` entfallen; `layout.mail_inhalt.ausblick` nur, falls noch sichtbar (in Spec klären). `OUTLOOK_HEADING` entfernen. Großwetterlage, `mail.outlook_state.*`, `spalte_tag` unberührt.
4. **Falllisten + Treiber:** Felder `briefing`, `sprache`, Format `telegram` in beiden Falllisten; Trip-`_senden` und Orte-`sende_orte_mail` um `report_type` und Telegram-Mitschnitt erweitern; Fälle je Briefing × Form × Sprache für `trip-paar-ausblick-*`, `trip-ausblick-aus--*` (Altpfad `show_outlook` + Tabelle `outlook_reports: []`), `O-AB-*`; Namensfall positiv (Katalogwert) und negativ („Mehrtages-Trend“, „3-Tages-Vorschau“, „Nächste Etappen“ als Titel).
5. **Validatoren:** Soll `ausblick_an` über eine Regel (`placements` → `resolve_outlook_reports`/`outlook_applies`, sonst `_legacy_outlook_reports`); Blockname prüfen; Orte-Validator optional `--briefing`.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/report_config_resolver.py | MODIFY | Altpfad-Ausblick über `_legacy_outlook_reports` |
| src/services/channel_list_resolver.py | MODIFY | Kommentar B3→B6 |
| src/i18n/messages/{de,en}/{mail,telegram}.json | MODIFY | Name, neuer Schlüssel `mail.ausblick.name` |
| src/output/renderers/email/{outlook,plain,compact,html,outlook_state_hint,compare_html}.py, narrow.py | MODIFY | Schlüsselwechsel, toten Hardcode entfernen |
| Orte-Anlage (in Spec zu verorten) | MODIFY | Ausblick-Vorbelegung AC-9 |
| frontend/.../versand-tab/VTSchedulePlan.svelte, VersandTab.svelte, reportConfigPayload.ts, trip-new/tripNewLogic.ts | MODIFY | Trend-Karte weg, Vorbelegung |
| frontend/src/lib/i18n/messages/{de,en}/{versand,wertebereiche,layout}.json | MODIFY | Namen |
| .claude/hooks/_soll_aus_konfiguration.py, briefing_mail_validator.py, email_spec_validator.py | MODIFY | Soll über eine Stelle, Blockname |
| tests/fixtures/einstellung_gleich_mail/fallliste_{trip,orte}.json, tests/tdd/test_einstellung_gleich_mail_{trip,orte}.py, tests/helpers/einstellung_gleich_mail_orte.py, _einstellung_gleich_mail_trip_fixtures.py | MODIFY | Dimensionen Briefing/Sprache/Telegram |
| Goldens/Fixtures (trip_briefing_aufbau, outlook_trip_parity, f5/f6/f8/f9, de_katalog_vor_i18n.json, KatalogAnker), E2E issue-88, standardwerte-und-hilfe, s3a2794, was-steht-wo-karte | MODIFY | Namen/Karte nachziehen |

### Scope Assessment
- Dateien: ~25 Code/Test + viele Goldens (mechanisch)
- Estimated LoC: Code ~+150/-80, Validatoren ~+100, Tests ~+300 (ohne Golden-Regeneration)
- Risk Level: MEDIUM — Mail-Inhalt aller Ausgaben (Renderer-Gate, Goldens), bewusste Ausgabeänderung Telegram bei `show_outlook:false`.

### Dependencies
Upstream `placements.py` (`_legacy_outlook_reports`, `resolve_outlook_reports`, `outlook_applies`), Katalog `src/i18n`. Downstream alle vier Ausgaben Trip/Orte, beide Validatoren, Falllisten, Frontend Anlage/Wetter-Reiter. Abgrenzung: globale Umstellung des Altbestands und Altfelder-Entfernung = B6 (#3157).

### Reihenfolge
1 Backend-Weiche + Tests · 2 Katalognamen + Goldens · 3 Falllisten/Helper, Validatoren · 4 Frontend (Karte, Vorbelegung, Kataloge, Goldens, E2E) · 5 Modus-Matrix, Validator-Lauf DE/EN.

### Open Questions (technisch, in der Spec zu klären, keine PO-Frage)
- [ ] Wo schreibt die Orte-Anlage die Ausblick-Vorbelegung (AC-9 Orte)?
- [ ] Ist die Checkbox `layout.mail_inhalt.ausblick` (MailInhaltCard) noch sichtbar? Wenn ja: Name/Text nach Nr. 15.

## Übergabe an /50-implement (aus TDD RED, 2026-11-19)
Folgende angepasste Bestandstests liegen nur im Arbeitsverzeichnis (nicht committet), weil das Commit-Gate „Tests der berührten Dateien" vorher grüne Tests, die rot werden, nur zusammen mit der Implementierung zulässt. Sie MÜSSEN mit dem Implementierungs-Commit eingecheckt werden:
- `frontend/src/lib/components/shared/{layout-tab/__tests__/f8KatalogAnker.ts, versand-tab/__tests__/f6KatalogAnker.ts, weather-metrics-tab/__tests__/f5KatalogAnker.ts}` (Anker der neuen/entfallenen Katalogschlüssel)
- `frontend/src/lib/components/trip-new/__tests__/standardwerte_payload_paritaet_trip.test.ts` (AC-7 Vorbelegung nur bei Anlage, Klarstellung 9)
- `frontend/src/lib/i18n/__tests__/deutsch_unveraendert.test.ts` (entfallene Schlüssel)
- `frontend/src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts` (Trend-Karte weg, Anker-Gegencheck)
- `tests/fixtures/einstellung_auslieferung/report_config_nach_speichern_golden_d.json` (Trend-Bool-Felder weg, `multi_day_trend_reports` bleibt `[]`)
Offen für den Entwickler: Literal `wertebereiche.schwelle.hinweis` in `wertebereiche_sprache.test.ts:191` an den neuen Wortlaut anpassen (muss „3-Tages-Ausblick“/„3-day outlook“ nennen, kein „Trend“). Python-Goldens (`trip_briefing_aufbau`, `outlook_trip_parity`, f5/f6/f8/f9) werden mit der Implementierung maschinell neu erzeugt, je Datei nur Namenswechsel. `frontend/node_modules` ist im Worktree ein Symlink auf das Haupt-Repo (gitignored).
