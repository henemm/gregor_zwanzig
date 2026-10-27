# Context: fix-2028-gewitter-satzvorlagen

## Request Summary
Issue #2028: Die drei letzten geduldeten Altlasten aus dem Gewitter-Skalen-Wächter (#1480) sanieren —
die doppelt gepflegten Satzvorlagen des Gewitter-Vorschausatzes (Trend-Weg + Fetch-Weg) an EINE Stelle
bringen und die lokale Nacht-Wortliste `_NIGHT_ADDENDUM_WORD` kanonisch ableiten. Fertig = alle drei
Einträge aus `ALTLASTEN` gestrichen, Wächter-Suite grün, Nutzer-Wortlaut unverändert.

## Ist-Stand (origin/main 84b50d72, 2026-09-24)

Seit Ticket-Erstellung (21.08.) hat sich der Fall verengt:
- **#2176** hat LOW aus beiden Satzvorlagen herausgenommen → beide rufen `thunder_low_statement_sentence("kurz", carriers)`.
  Doppelt bleiben nur noch NONE/MED/HIGH.
- `_NIGHT_ADDENDUM_WORD` enthält nur noch `{"MED": "mittleres", "HIGH": "starkes"}` (LOW läuft über `thunder_low_statement`).
- **#2011 und #2010 sind CLOSED** → die im Ticket genannte Reihenfolge-Abhängigkeit („Nacht-Wortliste nach #2011") entfällt.

### Die zwei Satzvorlagen (Regel B)

| Stufe | Trend-Weg `_thunder_entry_from_trend_row` (trs.py ~2901) | Fetch-Weg `_build_thunder_forecast` (trs.py ~3178) |
|---|---|---|
| NONE | `Kein Gewitter erwartet` | `Kein Gewitter erwartet` |
| LOW | `{low_sentence} ab {when}` **oder ohne `ab`, wenn `when` fehlt** | `{low_sentence} ab {when}` (when immer gesetzt) |
| MED | `Gewitter möglich ab {when}` / ohne when: `Gewitter möglich` | `Gewitter möglich ab {when}` |
| HIGH | `Starkes Gewitter erwartet ab {when}` / ohne when: `Starkes Gewitter erwartet` | `Starkes Gewitter erwartet ab {when}` |

Unterschied im Format von `when`: Trend-Weg `f"{hour:02d}:00"` (kann None sein), Fetch-Weg `strftime("%H:%M")` aus
dem frühesten Zeitstempel der Tagesstufe (immer gesetzt). Der geteilte Baustein muss nur den Satzkopf aus
`(level, when|None, carriers)` bauen — `when`-Herleitung bleibt je Weg (verschiedene Datenquellen).

Die nachfolgenden Anhänge (Herkunft ` · …`, Hagel ` · …`, Nacht-Zusatz) sind in beiden Wegen schon über
geteilte Bausteine (`thunder_signal_label`, `format_hail_note`, `format_night_addendum`) gebaut, aber die
**Reihenfolge-Logik** (Level-Check vor Herkunft, Hagel vor Nacht) ist ebenfalls zweimal ausgeschrieben.
→ Analyse-Frage: nur Satzkopf teilen oder die ganze Anhänge-Kette? Wächter verlangt nur den Satzkopf.

### Die Nacht-Wortliste (Regel A)
`src/app/day_window.py:257` `_NIGHT_ADDENDUM_WORD` + `format_night_addendum()` (einzige Nutzerin, ~Z. 262–294).
Kanonische Skala `src/app/thunder_scale.py:281` `THUNDER_LABEL_DE = {NONE:"kein", LOW:"leicht", MED:"mittel", HIGH:"hoch"}`
→ **„hoch" ≠ „starkes"**: eine reine Adjektiv-Flexion aus der Grundform reicht für HIGH nicht (hoch → „hohes Gewitter"
wäre Wortlaut-Änderung). Die gebeugte Form muss als eigene kanonische Größe in `thunder_scale.py` stehen
(z. B. Satzwort-Tabelle je Stufe) oder die Nacht-Wörter werden aus derselben Tabelle wie die Tages-Satzvorlagen
gezogen („Starkes Gewitter" ↔ „starkes Gewitter"). Wortlaut beim Nutzer muss unverändert bleiben.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py` (~2792–2960, ~3051–3220) | beide Bauwege, zu vereinheitlichen |
| `src/app/day_window.py` (~250–294) | `_NIGHT_ADDENDUM_WORD`, `format_night_addendum` |
| `src/app/thunder_scale.py` | kanonische Quelle (`THUNDER_LABEL_DE`, `thunder_low_statement*`, `format_hail_note`, `thunder_signal_label`) — Zielort für den geteilten Baustein |
| `tests/tdd/test_thunder_scale_local_copy_guard.py:290` | `ALTLASTEN` — drei Einträge streichen; `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` + `test_ac12_echter_backend_baum…` bewachen |
| `docs/specs/modules/thunder_scale_guard.md` | Spec des Wächters |
| `docs/specs/modules/briefing_parity_night_thunder.md` | Spec der Wortgleichheit beider Wege (Nacht) |

## Bestehende Tests, die den Wortlaut festnageln (Regressionsnetz)
`tests/unit/test_thunder_night_addendum.py`, `tests/unit/test_thunder_night_addendum_parity.py`,
`tests/unit/test_thunder_forecast_day_window.py`, `tests/unit/test_preview_night_block.py`,
`tests/unit/test_trip_report_formatter_v2.py`, `tests/tdd/test_briefing_parity_night_thunder.py`,
`tests/tdd/test_thunder_forecast_low_level.py`, `tests/tdd/test_thunder_low_no_event_claim.py`,
`tests/tdd/test_thunder_origin_trip.py`, `tests/tdd/test_thunder_origin_preview.py`,
`tests/tdd/test_hagel_im_nachthalbsatz.py`, `tests/tdd/test_hail_multiday_preview_and_sms_tomorrow.py`,
`tests/tdd/test_preview_thunder_matches_sent.py`, `tests/tdd/test_issue_721_email_outlook.py`,
`tests/tdd/test_issue_790_briefing_simplify.py`, `tests/tdd/test_issue_640_trend_threshold_times.py`,
`tests/tdd/test_issue_816_alert_deviation.py`, `tests/tdd/test_bug_874_th_plus_sms.py`,
`tests/tdd/test_th_plus_follows_thunder_metric_and_gap.py`, Fixture `tests/fixtures/trip_outlook_reference/telegram_bubble.txt`.

## Existing Patterns
- Geteilte Wortlaut-Bausteine leben in `src/app/thunder_scale.py` (Domänenschicht), Aufruf per lokalem Import in
  `day_window.py` / Scheduler (`from app.thunder_scale import …`).
- `thunder_low_statement` / `thunder_low_statement_sentence`: Muster „klein geschriebener Baustein + Satzanfangs-Variante"
  — direkt übertragbar auf MED/HIGH-Satzkopf und Nacht-Wort.
- Wächter-Duldung per Whitelist kanonischer Quellen (`test_whitelist_kanonischer_quellen_hat_keinen_leerlauf_eintrag`) —
  eine neue Stufen→Wort-Tabelle in `thunder_scale.py` muss dort als kanonisch gelten, sonst neuer Fund.

## Dependencies
- Upstream: `ThunderLevel` (`app.models`), `thunder_ordinal`, `summarize_points`, `night_addendum`, `format_hail_note`.
- Downstream: `forecast[key]["text"]` → Trip-Briefing E-Mail (full/compact), Telegram, SMS-Umfeld, Vorschau
  (`/api/preview`) — alle vier Kanäle. Renderer-Commit-Gate + `briefing_mail_validator.py` greifen.

## Nebenbefunde aus Ticket-Kommentar (#1199-Übertrag)
- **B2-64** = Kern dieses Tickets.
- **B2-65** veraltete 3-Stufen-Kommentare: `CorridorEditor.svelte:447` („3-Stufen-Band statt …", PO-Entscheid 2026-07-12)
  und `CorridorEditorMobile.svelte:433` („3 Ordinal-Buttons"). Zu prüfen, ob der Korridor-Editor tatsächlich
  noch 3 Buttons rendert (dann Kommentar korrekt) oder 4 (dann veraltet). State-Kommentar nicht mehr auffindbar.
- **B2-63** Go `internal/model/forecast.go` kennt `ThunderLow` nicht; `GET /api/forecast` ohne Frontend-Aufrufer →
  gehört zu **#2019 (OPEN, Rückbau Forecast-Endpunkt)**, nicht in diesen Workflow. Dort vermerken.

## Risks & Considerations
- **Wortlaut-Drift durch die Zusammenführung selbst**: Trend-Weg kennt den `when=None`-Zweig, Fetch-Weg nicht →
  geteilte Funktion muss beides abbilden, ohne dem Fetch-Weg neues Verhalten zu geben.
- Renderer-Commit-Gate: Scheduler-Textbau zählt ggf. als Mail-Inhalts-Datei → Modus-Matrix-Test + Validator frisch nötig.
- Wächter-Regel A/B dürfen die neue kanonische Tabelle nicht als neuen Fund melden (Whitelist symbolscharf).
- Ratsche leeren → abhängiger Test vakuum-grün (Memory #2151): Rückdreh-Gegenprobe (Kopie wieder einbauen ⇒ Wächter rot) Pflicht.
- Schema-Dateien nicht betroffen.

## Analysis

### Type
Bug (latenter Defekt / strukturelle Doppelpflege) — kein heute sichtbarer Fehler, Nutzer-Wortlaut bleibt byte-gleich.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/thunder_scale.py` | MODIFY | Neue kanonische Funktion `thunder_headline_sentence(level, when, carriers)` (Satzkopf NONE/LOW/MED/HIGH inkl. `when=None`-Zweig; LOW delegiert an `thunder_low_statement_sentence`) + Tabelle `THUNDER_NIGHT_ADJECTIVE_DE = {MED:"mittleres", HIGH:"starkes"}`; beide in `__all__` |
| `src/services/trip_report_scheduler.py` | MODIFY | `_thunder_entry_from_trend_row` (~2901) und `_build_thunder_forecast` (~3178): if/elif-Kette über `level` ersetzt durch EINEN Aufruf; `when`-Herleitung bleibt je Weg |
| `src/app/day_window.py` | MODIFY | `_NIGHT_ADDENDUM_WORD` entfällt, `format_night_addendum` importiert die kanonische Tabelle |
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | MODIFY | 3 `ALTLASTEN`-Einträge raus; 2 neue `canonical_symbols`-Einträge (`thunder_scale.py::thunder_headline_sentence` Regel B, `::THUNDER_NIGHT_ADJECTIVE_DE` Regel A) |
| `tests/tdd/test_thunder_headline_sentence.py` | CREATE | Matrix 4 Stufen × (`when` gesetzt / `None`) gegen den Wortlaut von heute + Wege-Vergleich Trend vs. Fetch bei gleichem Input |

### Scope Assessment
- Files: 5 (3 produktiv, 2 Tests)
- Estimated LoC: produktiv ca. +50/−45; Tests ca. +80
- Risk Level: LOW–MEDIUM (reine Zusammenführung, aber Wortlaut läuft in alle vier Kanäle)

### Technical Approach
Option (a): nur den **Satzkopf** teilen. Wächter-Regel B (`_regel_b`) meldet eine Funktion, sobald sie `level` gegen ≥2 Stufen vergleicht und ein Zweig ein eigenes Literal trägt — die Verzweigung muss also aus beiden Scheduler-Methoden vollständig verschwinden. Die Anhänge-Kette (Herkunft · Hagel · Nacht) ist bereits über geteilte Bausteine gebaut und erzeugt keinen Wächter-Fund; sie mitzuziehen (Option b) wäre Mehr-Risiko ohne Wächter-Nutzen.
Duldung der neuen kanonischen Symbole über `ScaleSpec.canonical_symbols` (Testdatei Z. 130, symbolscharf) — **nicht** per Marker. `test_whitelist_kanonischer_quellen_hat_keinen_leerlauf_eintrag` verlangt, dass beide neuen Einträge echte Funde erzeugen (tun sie).
Nachtwort als eigene Tabelle, nicht aus `THUNDER_LABEL_DE` abgeleitet („hoch" ≠ „starkes"; „mittleres" hat im MED-Satzkopf keine Entsprechung). Damit ist die im Ticket offene Produktfrage beantwortet: **flektierte Form als eigene kanonische Größe**, Wortlaut unverändert — keine PO-Entscheidung nötig.

### Dependencies
services → app ist bestehendes Importmuster (kein Zirkelbezug, kein Schichtbruch). Downstream: `forecast[key]["text"]` → E-Mail full/compact, Telegram, SMS-Umfeld, `/api/preview`.

### Risks
- `when=None`-Zweig existiert nur im Trend-Weg; der Fetch-Weg ruft stets mit gesetztem `when` → kein neues Verhalten dort.
- Rückdreh-Gegenprobe Pflicht: Kopie testweise wieder einbauen ⇒ `test_ac12_echter_backend_baum…` muss rot werden (Ratschen-Leerlauf, vgl. #2151).
- Renderer-Commit-Gate: `trip_report_scheduler.py` vor dem Commit gegen die Gate-Dateiliste prüfen (`docs/reference/gates_und_ratschen.md`).

### Out of Scope (bewusst)
- `_trend_note` (trs.py ~215–231, `notes.append("Gewitter möglich")`): weitere, vom Wächter nicht gesehene Stelle (Expr-Call statt Assign), aber andere Semantik (Kurzhinweis ohne Uhrzeit, MED+HIGH zusammengefasst) → Sammel-Eintrag #1199.
- B2-63 (Go `ThunderLow`) → gehört zu #2019 (OPEN), dort vermerken.
- B2-65 (Frontend-Kommentare „3-Stufen-Band"): Korridor-Editor-Band wurde 2026-07-12 vom PO auf 3 Stufen festgelegt — Kommentare vermutlich korrekt, keine Vorschausatz-Frage → nicht in diesem Workflow; Checkbox im Ticket-Kommentar mit dieser Begründung schließen.

### Open Questions
- keine (Nachtwort-Frage durch unveränderten Wortlaut + eigene Tabelle aufgelöst; #2011 ist geschlossen)

## RED-Phase-Erkenntnisse (2026-09-24, für /50-implement)
- **Testname-Korrektur zu AC-1/AC-6:** Die Spec nennt `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag`. Bei leerer `ALTLASTEN` ist dieser Test strukturell grün (kein toter Eintrag möglich). Der Zweig „unbekannter Fund" steckt in **`test_altlasten_basislinie_deckt_nichts_zu_das_nicht_in_ihr_steht`** — das ist der Test, der zusammen mit `test_ac12_echter_backend_baum…` rot war und bei der Mutations-Gegenprobe (AC-6) rot werden muss.
- LOW-Literal in `test_thunder_headline_sentence.py`: `carriers=["cape"]` → „Instabile Luftmasse (leicht)[ ab 14:00]".
- RED-Stand: 15 rot (13 neue Tests + 2 Wächter mit genau den drei Fundstellen), 77 grün. Sicherung: Scratchpad `red_backup/`.
