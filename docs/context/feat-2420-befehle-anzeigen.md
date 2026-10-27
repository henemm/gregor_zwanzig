# Context: feat-2420-befehle-anzeigen (#2420)

## Request Summary
Epic #2506 (Kanal-Parität). Die PO-Frage „Werden alle verfügbaren Befehle angezeigt?" ist nach #2417 an zwei Stellen mit Nein beantwortet:
1. Die Befehlsverarbeitung akzeptiert `abbruch`, `startdatum`, `report` und das Tippwort `columns`, aber Hilfe, Mail-Tabelle und Telegram-Menü bieten sie nicht an.
2. Die Ortsvergleichs-Mail hat keine Befehlsliste. Trip-Briefings haben die Tabelle „Antwort-Kommandos".

## Befunde zum Ist-Stand (belegt)

| Befehl | Ist-Zustand | Konsequenz |
|---|---|---|
| `abbruch` | `_BARE_KEYWORD_MAP["stop"] = "abbruch"` (`trip_command_processor.py:214`). STOP steht in `_COMMAND_SPECS` ("Briefings dauerhaft deaktivieren"), `_cancel_trip` ist die Wirkung (`:3242`). | ABBRUCH ist **kein eigener Befehl**, sondern der interne Schlüssel von STOP. `### abbruch` ist nur der E-Mail-Weg. Kein eigener Eintrag nötig, höchstens Alias-Hinweis in der Beschreibung. |
| `startdatum` | Nur `### startdatum: JJJJ-MM-TT` oder, bei Telegram, das Freitextwort über den `_VALID_COMMANDS`-Fallback (`inbound_telegram_reader.py:688`). Kein Bare-Keyword (`_BARE_KEYWORD_MAP`), `bare_keywords()` kennt es nicht. | Per E-Mail (`###`) und Telegram erreichbar, per Premium-SMS **nicht erkannt** (Verknüpfungscode-Trennung nutzt `bare_keywords()`). |
| `report` | `### report: morning\|evening` löst `_trigger_report` aus (`:2600`). Kein Bare-Keyword. Am Ortsvergleich gibt es die Übergangsantwort `_compare_transitional` (`:1370`). | Gleiche Lage wie `startdatum`. Wirkung ist ein sofortiger Briefing-Versand. |
| `columns` | Telegram-Button „📊 Spalten" (`:558`), `_show_columns_info` (`:2798`) liefert nur einen Hinweistext (Spalten gibt es nur im Frontend-Editor). | Kein Befehlswort, sondern ein Button-Callback. Kein Angebotskandidat. |

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py:256` | `_COMMAND_SPECS` (13 Einträge, Feldname-Zugriff, `kinds`, `arg_en`, `wirkung_en`). EINE Quelle für Hilfe, Fehlertexte, beide Mail-Blöcke. |
| `src/services/trip_command_processor.py:202-222` | `_VALID_COMMANDS`, `_BARE_KEYWORD_MAP`; `_BARE_KEYWORD_MAP.update(...)` aus den Specs (`:288`). |
| `src/services/trip_command_processor.py:1379` | `_show_help_for_kind(kind)`, filtert auf `kinds`; `hilfe_kurzform(kind)` für Kurzform. |
| `src/services/trip_command_processor.py:1350-1378` | `_dispatch_compare`: Vergleich kennt nur hilfe, kuerzel, pause, weiter, report/heute/morgen (Übergang), sonst `_compare_unavailable`. |
| `src/output/renderers/email/plain.py:365` | Trip-Klartext-Befehlsblock aus `command_rows()`. |
| `src/output/renderers/email/html.py:474` | `_render_kommandos_section()` aus `command_rows()`. |
| `src/output/renderers/email/compare_html.py:1735-1760` | Compare-HTML: Blockreihenfolge … legend, `abo_html`, `app_footer_html`. Hier fehlt der Befehlsblock. |
| `src/output/renderers/comparison.py:414` | Compare-Klartext endet mit `---` / `Gregor Zwanzig`. Hier fehlt der Befehlsblock. |
| `src/output/channels/telegram.py:131` | `BOT_COMMANDS` als ausgeschriebenes Literal (wegen `prod_selftest.py` / `ast.literal_eval`); Drift bewacht `test_befehlsangebot_vollstaendig.py`. |
| `frontend/src/lib/i18n/messages/de.json:83-109` | Hilfeseite `/hilfe`: statische Kopie der Befehle. Drift bewacht `tests/test_hilfe_befehle_drift.py` (#2521). |
| `src/services/inbound_sms_reader.py` | Premium-SMS-Eingang, trennt Verknüpfungscode vom Befehlstext über `bare_keywords()`. |

## Existing Patterns
- **EINE Quelle** `_COMMAND_SPECS`; Aliase stehen in der Beschreibung statt als eigener Eintrag (Kommentar `:225-235`).
- **Pendant-Regel:** Trip- und Compare-Mail sollen denselben Baustein nutzen. Der Block steht heute in `plain.py`/`html.py` (Trip-Dateien, `command_rows()` ungefiltert). Für den Vergleich braucht es eine Variante, gefiltert auf `kind="vergleich"`, im selben Baustein und mit Parameter, nicht als zweite Kopie.
- `command_rows()` ist bewusst Funktion statt Konstante (Mutations-Gegenprobe AC-10 aus #2134).

## Dependencies / Downstream (was bricht, wenn `_COMMAND_SPECS` wächst)
- `tests/test_hilfe_befehle_drift.py`: neuer Befehl ⇒ `de.json` muss `hilfe.befehle.<wort>.befehl/.text` bekommen (sonst rot).
- `BOT_COMMANDS` in `telegram.py` (Literal) plus `test_befehlsangebot_vollstaendig.py` (zählt „12 Befehle", Menü/Langhilfe/Kurzhilfe).
- Goldene Mails: `tests/golden/email/*-plain.txt` und `*-html.txt` enthalten den Befehlsblock der Trip-Mail ⇒ bei Änderung der Trip-Zeilen neu aufzeichnen.
- `test_kommandoliste_einzelquelle.py`, `test_kurzform_befehle_englisch.py`, `test_issue_731_unified_commands.py`, `test_trip_renderer_characterization.py`, `test_shared_outlook_renderer.py`.
- Neue Zeilen im Compare-Mail-Template ⇒ **Renderer-Commit-Gate** und `email_spec_validator.py` (`X-GZ-Mail-Type: compare`) an echter Staging-Mail.
- Kurzform englisch (#2417): jeder neue Befehl braucht `wort_en`, `arg_en`, `wirkung_en` und `kinds`.

## Existing Specs
- `docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md` (Ursprung, schließt #2420 aus)
- `docs/specs/modules/feat_2417_kurzform_englisch.md`
- `docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md` (EINE Quelle, AC-9..12)
- `docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md` (`kinds`, Vergleichs-Hilfe, S2/S3 offen als #2345 P5)

## Risks & Considerations
- **Epic-Vorgabe:** Jeder Kanal muss jede Frage beantworten können. Ein Befehl, der in der E-Mail-Tabelle erscheint, aber per Premium-SMS nicht erkannt wird (`startdatum`, `report`), verspricht mehr, als der Kanal hält. Erst Eingangswege klären, dann anbieten.
- **REPORT beim Ortsvergleich** ist nur eine Übergangsantwort („bitte nutze die Web-App"). Anbieten im Vergleich wäre ein Versprechen ohne Wirkung ⇒ im Vergleich nicht listen, solange #2282 S2/S3 offen sind.
- **STARTDATUM** verändert die Etappendaten (Persistenz-Schreibpfad `_speichere`); bei Aufnahme in SMS/Telegram-Kurzform ist die Datumsform (`JJJJ-MM-TT`) zeichenknapp. SMS-Zeichengrenze der Kurzhilfe prüfen.
- **REPORT** löst einen echten Versand aus (`send_test_report_outcome`) ⇒ Missbrauchs-/Mehrfachversand-Frage beim Anbieten über SMS; Antwortzeit-Epic (#2439) beachten.
- **Fünf Kopien** der Befehlsliste (Specs, `BOT_COMMANDS`, `de.json`, Goldens, Kurzform) ⇒ LoC-Limit 250 könnte bei Aufnahme neuer Befehle plus Goldens knapp werden; `loc_limit_override` ggf. nötig (Goldens/Tests zählen laut Regel nur produktive Spec-Dateien).
- Nicht-Ziel (Nutzer-Memory): keine Handlungsempfehlungen, nur Daten; kein „Tour", immer „Trip".

## Offene Entscheidung für die Spec
Welche der vier Wörter werden angeboten:
- ABBRUCH: Alias in der STOP-Beschreibung, kein eigener Eintrag (Empfehlung).
- COLUMNS: nicht listen, da Button-Callback ohne Wirkung außerhalb des Frontends (Empfehlung).
- STARTDATUM und REPORT: anbieten setzt voraus, dass der Eingang sie in allen vier Kanälen erkennt (E-Mail ja, Telegram ja, Premium-SMS nein, Ortsvergleich nur Übergang). Empfehlung wird in der Analyse an den Reader-Codes gemessen.

## Analysis

### Type
Bug (Label `bug`, nutzersichtbar): Befehlsangebot und Befehlswirkung stimmen nicht überein.

### Messung am Eingang (Entscheidungsgrundlage)
| Wort | E-Mail (`###`) | Telegram | Premium-SMS | Ortsvergleich |
|---|---|---|---|---|
| ABBRUCH | ja (interner Schlüssel von STOP) | über STOP | über STOP | STOP: „gibt es nicht" |
| STARTDATUM | ja | ja (`_VALID_COMMANDS`-Fallback) | **nein** (`_parse_command` kennt nur `_BARE_KEYWORD_MAP`) | nein |
| REPORT | ja | ja | **nein** (nur Sonderfall `:1364` im Vergleichs-Zweig) | nur Übergangsantwort |
| COLUMNS | – | Button-Callback | – | – |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| src/services/trip_command_processor.py | MODIFY | `_COMMAND_SPECS`: STARTDATUM + REPORT (kinds=route, `wort_en`/`arg_en`/`wirkung_en`); `_BARE_KEYWORD_MAP` erkennt beide als Alleinwort (SMS-Eingang); STOP-Beschreibung nennt ABBRUCH als Alias |
| src/output/renderers/email/plain.py + html.py | MODIFY | Befehlsblock parametrisieren (`kind`), `command_rows(kind)` gefiltert |
| src/output/renderers/email/compare_html.py | MODIFY | Befehlsblock aus geteiltem Baustein, kind=vergleich |
| src/output/renderers/comparison.py | MODIFY | Klartext-Befehlsblock vor Fußzeile |
| src/output/channels/telegram.py | MODIFY | `BOT_COMMANDS`-Literal um neue Befehle |
| frontend/src/lib/i18n/messages/de.json (+en) | MODIFY | `hilfe.befehle.startdatum/report` (Drift-Test) |
| tests/golden/email/* | RE-RECORD | Trip-Befehlsblock wächst |
| tests/ (neu, nach Verhalten benannt) | CREATE | Eingang je Kanal, Compare-Mail-Block, Zwei-Nutzer-Test |

### Scope Assessment
- Files: ca. 8 produktiv + Goldens/Tests
- Estimated LoC: +120/-20 produktiv (Goldens zählen nicht)
- Risk Level: MITTEL (Compare-Mail-Template ⇒ Renderer-Gate; STARTDATUM schreibt Persistenz)

### Technical Approach
1. ABBRUCH: kein eigener Eintrag, Alias-Hinweis in STOP-Beschreibung (Konvention `:225`).
2. COLUMNS: nicht anbieten (Button ohne Wirkung außerhalb des Frontends).
3. STARTDATUM + REPORT anbieten, aber erst den SMS-Eingang schließen (Alleinwort in `_BARE_KEYWORD_MAP`; `bare_keywords()` folgt automatisch, Verknüpfungscode-Trennung bleibt intakt). Sonst verspräche die Tabelle mehr, als Premium-SMS hält (Epic #2506).
4. Beide nur `kinds=route`: im Vergleich wirkungslos (REPORT = Übergangsantwort) ⇒ dort nicht listen; Vergleichs-Mail zeigt PAUSE/WEITER/HILFE/KÜRZEL (= `_show_help_for_kind("vergleich")`).
5. Befehlsblock als EIN Baustein mit Parameter `kind` (Pendant-Regel), kein zweiter Renderer.
6. Alle Kopien aus EINER Quelle nachziehen (BOT_COMMANDS, de.json, Goldens).

### Dependencies
Siehe oben (Drift-Tests, Goldens, Renderer-Commit-Gate, `email_spec_validator.py` für Compare, `briefing_mail_validator.py` für Trip).

### Open Questions
- [ ] REPORT per SMS: Mehrfachversand-Schutz nötig? (Antwortzeit-Pfad #2439; Spec soll Verhalten bei Wiederholung festlegen, ggf. vorhandenes `already_in_progress`)
- [ ] STARTDATUM per SMS: Kurzform-Zeichenbudget der Hilfe (160 Zeichen) prüfen
