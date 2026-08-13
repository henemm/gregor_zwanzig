# Context: feat-1703-s7-reihenfolge-matrix

Epic #1703 Scheibe 7 — „Reihenfolge-Wächter jenseits E-Mail/Telegram-rich".
Deckt Fläche 5 aus `docs/reference/metric_output_matrix.md` (Abschnitt 4.2).

## Request Summary

Die vom Nutzer eingestellte **Metrik-Reihenfolge** soll in denjenigen Ausgabeorten
bewacht werden, die heute keinen katalog-vollständigen Reihenfolge-Wächter haben —
Trip-Kompaktformen und die Compare-Übersichtstabelle über alle vier Kanäle.
Zuschnitt für Compare bleibt auf die **Übersicht** beschränkt (Ausblick und
Stundenverlauf haben nach ADR-0053 weiterhin keine Kanal-Ebene).

## 🔴 Gemessener Ist-Stand — der Issue-Text schneidet zu breit zu

Fläche 5 ist im Matrix-Dokument als „Reihenfolge in **allen** Kanälen außer E-Mail
und Telegram-rich" beschrieben. **Gemessen trifft das nicht mehr zu.** Zwei der drei
dort genannten Orte sind längst bewacht — dieselbe Prämissen-Falle wie bei Scheibe 2
und Scheibe 5.

| Ausgabeort | Reihenfolge bewacht? | Wächter | Deckung |
|---|---|---|---|
| Trip E-Mail-Vollformat | ✅ ja | `test_channel_metric_matrix.py` AC-13 | katalog-getrieben, alle 26 |
| Trip Telegram-rich | ✅ ja | AC-14 | katalog-getrieben |
| **Trip SMS-Kurzform** | ✅ **ja** | AC-15 (c) + AC-12 | katalog-getrieben — die in Fläche 5 genannte `tokens/builder.py`-Lücke ist mit #1677/#1660 B geschlossen (`_POSITION_SORTABLE_CATEGORIES`) |
| Trip Kurz-E-Mail (Pillen) | ❌ **nein** | AC-S4-1/2/3 prüfen nur Auswahl/Abwahl | — |
| Trip Telegram-Kurzform | ❌ **nein** | AC-S4-12/13/14 prüfen nur Auswahl/Abwahl | — |
| Trip Kompakt-Zusammenfassung | ❌ **nein** | AC-S4-6..10 (feste Positivliste, 10 von 26) | — |
| **Compare Übersicht** (HTML · Klartext · Telegram · SMS) | ⚠️ **teilweise** | `tests/unit/test_compare_metric_order.py` (#1359) | **4 fest getippte Metriken** von 25 wählbaren, **eine globale Liste** |
| **Compare: je Kanal eigene Reihenfolge** | ❌ **gar nicht** | — | seit Scheibe 8 (2026-08-13) überhaupt erst möglich |

Der Kopfkommentar von `test_channel_metric_matrix.py` (Zeile 20) nennt den
SMS-Reihenfolge-Teil noch „RED" — das ist veraltet, der Test läuft grün. Die Zeile
gehört als Nebenprodukt dieser Scheibe korrigiert.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `tests/tdd/test_channel_metric_matrix.py` (3663 Z.) | Zielort der neuen Achse `AC-S7-*` — Option C aus #1514: kein zweites Register, kein neues Gate |
| `tests/unit/test_compare_metric_order.py` | Bestandswächter #1359: HTML/Klartext/Telegram/SMS mit `ORDER_A`/`ORDER_B` (`cloud_avg`, `temp_max`, `sunny_hours`, `wind_max`) — Prinzip bewacht, Katalog-Deckung nicht |
| `src/output/renderers/compare_metric_ids.py:200-241` | `resolve_channel_enabled_metrics()` (S8) — Docstring sagt ausdrücklich: „Die Reihenfolge des Ergebnisses ist die der KANAL-Liste" |
| `src/services/report_config_resolver.py:206-208`, `:309` | `CompareRenderOptions.enabled_metrics_by_channel` — additiv neben `enabled_metrics` |
| `src/services/scheduler_dispatch_service.py:439/505/509` | Versandpfad: E-Mail/Telegram/SMS lesen je ihre Kanal-Liste |
| `src/services/compare_preview_service.py:65/70/105/122/186` | Vorschaupfad, dieselben drei Kanäle |
| `src/output/renderers/comparison.py:143/704/995` | `render_comparison_text()`, `render_compare_telegram()`, `render_compare_sms()`; `_DAILY_PLAIN_ROWS`/`_PLAIN_ROWS` (`:70`/`:100`) sind handgeschriebene Tupel-Listen |
| `src/output/renderers/email/compare_html.py:1526` | `render_compare_html()` — Zeilenfolge der Übersicht |
| `src/output/renderers/email/compact.py:96`, `:162-181` | `render_compact()` → `resolve_trip_active_metrics()` → `build_metrics_summary_pills()` — Pillen-Reihenfolge |
| `src/output/renderers/narrow.py:625` | `render_telegram_bubbles()` — Telegram-Kurzform |
| `src/output/tokens/builder.py:47/78/112` | `PRIORITY`/`POSITIONAL`/`DEFAULTS` — die Trip-SMS-Sortierung, bereits über AC-15 gedeckt |
| `docs/reference/metric_output_matrix.md` | Fläche 5 + Abschnitt 6 → Definition of Done: Zelle auf den neuen Wächter umtragen |

## Existing Patterns

- **Achsen-Muster der Scheiben 1–5:** neue AC-Gruppe `AC-S<n>-*` in
  `test_channel_metric_matrix.py`, Soll-Menge aus dem Katalog **gerechnet**
  (`get_compare_metric_catalog()` bzw. `get_all_metrics()`), nie getippt; Helper
  bei Bedarf unter `tests/helpers/` (Vorbild `outlook_columns.py` aus S2).
- **Ausnahme S6:** eigene Testdatei, wenn die „1 Zeile = 1 Metrik"-Matrix die
  Struktur nicht ausdrücken kann (dort 1:n). Für Reihenfolge gilt das nicht —
  paarweise Reihenfolge ist bereits das Muster von AC-13/14/15.
- **Nachweis am Wirkort:** Ist-Werte aus dem echten Renderer-Aufruf
  (`render_compare_email()` liefert HTML und Klartext in einem Zug), nicht aus
  isolierten Hilfsfunktionen.
- **Paarweise Reihenfolge:** dieselbe Metrik-MENGE in zwei Reihenfolgen rendern und
  die Indizes vergleichen — schlägt sowohl bei „Reihenfolge ignoriert" als auch bei
  „intern neu sortiert" an.

## Dependencies

- **Upstream:** `get_compare_metric_catalog()` / `get_all_metrics()` (Soll-Mengen),
  `resolve_channel_enabled_metrics()`, `resolve_trip_active_metrics()`,
  `CompareRenderOptions`.
- **Downstream:** kein Produktivcode hängt am Wächter. Ein etwaiger *Fix* träfe die
  Compare-Renderer (`comparison.py`, `compare_html.py`) bzw. die Trip-Kompaktformen
  — beides nutzersichtbare Mail-/Telegram-/SMS-Ausgabe, damit Renderer-Commit-Gate
  (#811) und Mail-Validator-Pflicht.

## Existing Specs

- `docs/specs/modules/compare_metric_order.md` — #1359, die Reihenfolge-Zusicherung
  für den Ortsvergleich
- `docs/specs/modules/fix_1677_sms_reihenfolge.md` — AC-13/14/15, der Trip-Teil
- `docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md` — die Kanal-Ebene, auf der
  diese Scheibe aufsetzt
- `docs/adr/0053-compare-kanal-eigene-metrikauswahl-uebersicht.md` — Zuschnitt:
  nur Übersicht, Ausblick/Stundenverlauf bleiben global
- `docs/adr/0050` — Metrik-Kaskade Regel 1/2 („Grundauswahl ist das MAXIMUM, ein
  Kanal darf nur ABWÄHLEN")

## Risks & Considerations

1. **🔴 Wirkungslücken-Risiko (S8-Fehlerklasse).** `resolve_channel_enabled_metrics()`
   *behauptet* im Docstring, die Ergebnis-Reihenfolge sei die der Kanal-Liste.
   Ob die acht Aufrufstellen und die vier Renderer diese Reihenfolge tatsächlich bis
   in die zugestellte Ausgabe tragen, ist **ungemessen**. In Scheibe 8 waren viermal
   die reine Funktion getestet und die Aufrufstelle nicht. Leitfrage: *Ist die
   Zusicherung dort geprüft, wo sie WIRKT?*
2. **Prämissen-Risiko.** Bei S2 und S5 war der Issue-Zuschnitt falsch. Hier bereits
   nachgewiesen: Trip-SMS ist entgegen der Flächenbeschreibung schon bewacht. Der
   endgültige Zuschnitt gehört vor die ACs gemessen, nicht danach.
3. **Möglicher Produktivcode-Fix.** Fläche 5 notiert: „Compare-Klartext nutzt die
   Nutzer-Reihenfolge nur als Sichtbarkeitsfilter (#1356)". Ob das nach #1359 noch
   gilt, ist offen — falls ja, ist es ein nutzersichtbarer Defekt und der Fix gehört
   in die Scheibe (Muster S2/S6).
4. **Compare-SMS und das Zeichenbudget.** Die Reihenfolge bestimmt dort, was bei
   Kappung wegfällt — ein Reihenfolge-Fehler ist in der SMS ein *Inhalts*-Fehler.
   Drei Grenzen beachten: 160/153/140 Zeichen.
5. **Renderer-Commit-Gate #811.** Sobald eine Mail-Inhalts-Datei staged wird, sind
   `test_issue_811_mode_matrix.py` **und** ein frischer `briefing_mail_validator.py`-
   bzw. `email_spec_validator.py`-Lauf Pflicht.
6. **Kein neues Gate.** Leitplanke des Epics: Erweiterung des budgetierten Gates
   #1677 B, kein zweites Register, kein neues Prüfdatum.

## Analysis

### Type

**Feature** (Wächter-Ausbau nach dem Muster der Scheiben 1–5) — mit **zwei
Kandidaten für einen nutzersichtbaren Produktivcode-Fix**, beide unten belegt.

### Am Code gemessen — die vier offenen Fragen aus dem Kontext

**1. Compare-Klartext folgt der Nutzer-Reihenfolge.** Fläche 5 notiert „nutzt die
Nutzer-Reihenfolge nur als Sichtbarkeitsfilter (#1356)" — das ist **veraltet**.
`_ordered_rows()` (`comparison.py:126-140`) setzt sie seit #1359 um; die HTML-Seite
tut dasselbe über `_visible_metrics()` (`compare_html.py:798`). Beide bauen die
Zeilenliste generisch aus `enabled_metrics`, sind also strukturell katalog-fähig.

**2. 🔴 Die Kurz-E-Mail verwirft die Reihenfolge — belegt.**
`build_metrics_summary_pills()` (`email/helpers.py:1844`) kollabiert die geordnete
Liste zu `ids_set = set(metric_ids)` und rendert ausdrücklich „in **catalog order**"
(Docstring + Codekommentar `:1899`). Die im Editor eingestellte Reihenfolge kann den
Pillen-Überblick der Kurz-E-Mail damit **strukturell nicht erreichen**. Kein Test
bemerkt das: AC-S4-1/2/3 prüfen nur Auswahl und Abwahl.

**3. 🔴 Altbestands-Reihenfolge divergiert zwischen HTML und Klartext derselben
Compare-Mail — Kandidat, in RED zu belegen.** Bei `enabled_metrics=None` (Preset ohne
gespeicherte Auswahl) behält jede Seite ihre eigene Quellcode-Reihenfolge:

| Position | HTML (`CV2_METRICS`) | Klartext (`_PLAIN_ROWS`) |
|---|---|---|
| 1 | temp_max | temp_max |
| 2 | wind_max | wind_max |
| **3** | **precip_sum** | **temp_min** |
| 4 | pop_max | gust_max |

Beide Mengen sind identisch (25 Zeilen), nur die Ordnung nicht. Der Bestandswächter
`test_plaintext_order_matches_html_order_in_same_mail` prüft die Parität ausschließlich
mit **explizit gesetzter** `ORDER_A` — der Altbestandsfall läuft an ihm vorbei.

**4. Trip-Telegram-Kurzübersicht und Compare-Telegram folgen der Reihenfolge, aber
über zwei verschiedene Wege.** `render_telegram_bubbles()` iteriert die Kurzübersicht
über `dc.get_enabled_metric_ids()` (`narrow.py:741`) — **nicht** über das
`render_for_channel()`-Layout, das dieselbe Funktion zwei Zeilen vorher für die
Tabellen-Bubbles baut. `render_compare_telegram()` (`comparison.py:729-731`) übernimmt
`enabled_metrics` als `dedup_ids`, schickt sie aber durch
`_channel_layout_for_metrics()` mit `max_table_cols = 7`: bei mehr als sieben Größen
entscheidet die Reihenfolge, **welche** Metrik überhaupt erscheint. Ob das Layout die
Nutzer-Reihenfolge dabei erhält oder nach eigener Priorität umsortiert, ist der
eigentliche Prüfpunkt.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_channel_metric_matrix.py` | MODIFY | Neue Achse `AC-S7-*`; zusätzlich Kopfkommentar Z. 20 korrigieren („RED" für AC-15c ist überholt) |
| `tests/helpers/compare_order.py` | CREATE (evtl.) | Gerechnete Soll-Menge + Label-Auslese je Kanal, Vorbild `outlook_columns.py` (S2) |
| `docs/specs/modules/fix_1703_s7_reihenfolge_matrix.md` | CREATE | Spec mit ACs |
| `docs/reference/metric_output_matrix.md` | MODIFY | Fläche 5 + Abschnitt 6 umtragen (Definition of Done) — inkl. der beiden hier belegten Prämissen-Korrekturen |
| `src/output/renderers/email/helpers.py` | MODIFY (**nur bei PO-Entscheidung**) | Pillen-Reihenfolge der Kurz-E-Mail |
| `src/output/renderers/comparison.py` | MODIFY (**nur bei PO-Entscheidung**) | Altbestands-Reihenfolge an `CV2_METRICS` angleichen |

### Scope Assessment

- Dateien: 4 sicher, +2 bei Fix
- Geschätzte LoC: Tests **+380/-15**, Produktivcode **0** (reine Charakterisierung)
  bzw. **+15/-8** bei beiden Fixes
- Risiko: **MEDIUM** — der Wächter selbst ist risikofrei; ein Fix ändert die
  Zeilenfolge in zugestellter E-Mail und im Ortsvergleich, und in der Compare-SMS
  entscheidet die Reihenfolge unter Zeichendruck über den *Inhalt*

### Technical Approach

Achse `AC-S7-*` in `tests/tdd/test_channel_metric_matrix.py` (Option C: kein zweites
Register, kein neues Gate), gegliedert in drei Blöcke:

1. **Compare-Übersicht × 4 Kanäle × Katalog** — Soll-Menge aus
   `get_compare_metric_catalog()` **gerechnet**, paarweise Reihenfolge (dieselbe
   MENGE in zwei Ordnungen, Indizes vergleichen) gegen die echten Renderer
   `render_compare_email()` (HTML + Klartext in einem Aufruf), `render_compare_telegram()`,
   `render_compare_sms()`. Ersetzt die vier getippten Metriken aus #1359 durch
   Katalog-Deckung, ohne den Bestandstest anzufassen.
2. **Kanalweise unterschiedliche Reihenfolge in EINER Sendung** — der Nachweis, den
   Scheibe 8 für die *Auswahl* geführt hat (9/5/2 Metriken), jetzt für die *Ordnung*:
   `enabled_metrics_by_channel` mit drei verschiedenen Reihenfolgen, geprüft an der
   zugestellten Ausgabe je Kanal, nicht an `resolve_channel_enabled_metrics()`.
3. **Trip-Kompaktformen** — Kurz-E-Mail-Pillen, Telegram-Kurzübersicht,
   Kompakt-Zusammenfassung: Reihenfolge-Achse belegen oder als benannte, begründete
   Ausnahme charakterisieren.

**Kein neues Gate, kein neues Prüfdatum** (Epic-Leitplanke). Soll-Mengen gerechnet,
nie getippt — mit der Einschränkung aus S2 F001: *Rechnen sichert Vollständigkeit,
nie Zuordnung*; die Zuordnung braucht eine eigene Assertion.

### Dependencies

Upstream: `get_compare_metric_catalog()`, `resolve_channel_enabled_metrics()`,
`resolve_trip_active_metrics()`, `CompareRenderOptions`.
Downstream: kein Produktivcode hängt am Wächter. Ein Fix träfe Mail-Inhalts-Dateien →
Renderer-Commit-Gate #811 (`test_issue_811_mode_matrix.py` + frischer Validator-Lauf).

### Open Questions — für die Spec-Freigabe

- [ ] **Kurz-E-Mail-Pillen (Befund 2): charakterisieren oder fixen?**
      *Empfehlung: fixen.* Der Nutzer stellt je Kanal eine Reihenfolge ein; dass sie
      in genau einem Ausgabeort verworfen wird, ist ein Bedienelement ohne Wirkung —
      exakt die Fehlerklasse, gegen die dieses Epic gebaut wurde. Der Eingriff ist
      klein (`set()` → geordnete Liste). Risiko: die Pillen-Reihenfolge ändert sich
      für alle Trips, die eine eigene Ordnung gespeichert haben.
- [ ] **Altbestands-Divergenz HTML/Klartext (Befund 3): charakterisieren oder fixen?**
      *Empfehlung: erst in RED belegen, dann fixen*, indem `_PLAIN_ROWS` der
      `CV2_METRICS`-Ordnung folgt. Betrifft nur Presets ohne gespeicherte Auswahl;
      Presets mit Auswahl sind bereits konsistent. Gegenargument: die
      `_PLAIN_ROWS`-Ordnung ist in `test_compare_metric_order.py` AC-7 ausdrücklich
      als Altbestands-Standard **eingefroren** — ein Fix zieht diesen Bestandstest mit.
