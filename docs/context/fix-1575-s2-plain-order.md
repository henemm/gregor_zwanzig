# Context: Fix #1575 Scheibe 2 — Plain-Text-Mail Spaltenreihenfolge

## Request Summary

Die im Editor eingestellte Metrik-Reihenfolge wirkt seit Scheibe 1 (PR #1580, gemergt)
im **HTML**-Teil der Briefing-Mail. Der **Plain-Text**-Teil kennt den Mechanismus
(`col_order` aus `dc.metrics`) gar nicht und sortiert weiterhin strikt nach
Katalog-Reihenfolge. Zusätzlich divergieren HTML und Plain schon heute in der Position
von `TmpMin` (`temperature_cold`, `selectable=False`) — Position 2 im Plain-Teil,
vorletzte Stelle im HTML-Teil. Beides soll in dieser Scheibe angeglichen werden.

Explizit in Scheibe 1 als „Nicht in dieser Scheibe" vertagt (siehe
`docs/specs/modules/fix_1575_mail_column_order.md` → Abschnitt „Nicht in dieser
Scheibe"), weil die Änderung eine gate-geschützte Mail-Inhalts-Datei berührt
(`renderer_mail_gate.py` / Issue #811) und einen `briefing_mail_validator.py`-Lauf
gegen eine echt zugestellte Staging-Mail per IMAP braucht — in der Vorgänger-Session
(Remote, ohne IMAP/Staging-Zugriff) nicht lieferbar.

## Related Files

| File | Relevance |
|------|-----------|
| `src/output/renderers/email/plain.py` | Ziel der Änderung. `_render_text_table()` (Z.54-86) ruft `visible_cols(rows)` (Alt-Pfad) auf, kennt `dc` zwar als Parameter von `render_plain()`, nutzt es aber nirgends für die Spaltenreihenfolge. |
| `src/output/renderers/email/helpers.py` | `visible_cols()` (Z.250-296): zwei Aufrufformen. Alt-Pfad (Z.292-296, von `plain.py` und `html.py` genutzt) liefert `(col_key, label)`-Paare strikt in `get_col_defs()`-Katalogreihenfolge — kennt `order`/`bucket` nicht. Neuer Pfad (Z.267-290, DisplayMetric-Configs) filtert bereits nach `selectable`/`enabled`/Horizont, aber wird aktuell nicht für die Spaltenreihenfolge der Tabellen verwendet. |
| `src/output/renderers/email/html.py` | Referenzmechanismus. Z.1018-1029 baut `_col_order` aus `dc.metrics` (bereits durch `get_metrics_for_channel` sortiert, Scheibe 1), überspringt disabled **und nicht-selectable** Größen. `_render_html_table()` Z.664-682: `cols = visible_cols(rows)` (Katalog-Reihenfolge, alle in den Row-Daten vorhandenen Spalten) → dann `ordered = [col_order-Treffer]` + `remaining = [Rest in Katalog-Reihenfolge]` → `cols = ordered + remaining`. **Das ist der Mechanismus, den Plain nachziehen muss.** |
| `src/app/models.py` | `UnifiedWeatherDisplayConfig.get_metrics_for_channel()` (Z.700-732) — seit Scheibe 1 liefert diese Methode für alle Kanäle bereits nach `(bucket, order)` sortierte `dc.metrics` (`_sorted_by_layout`, stabil). Plain bekommt dieselbe sortierte Liste über den `dc`-Parameter von `render_plain()` — die Sortierung selbst ist also schon da, nur die Spalten-Zuordnung im Renderer fehlt. |
| `src/app/metric_catalog.py` | `get_col_defs()` (Z.994-1001): Katalog-Reihenfolge als `(col_key, label, col_key)`-Tripel. `temperature_cold` (Z.121-129): `selectable=False`, `col_key="temp_cold"`, `col_label="TmpMin"` — interne Alarm-Pseudogröße, „never shown in user catalog or /api/metrics". Nicht nutzerkonfigurierbar; die Positionsfrage ist ein Implementierungsdetail, kein Bedienkonzept. |
| `src/output/renderers/channel_layout.py` | `render_for_channel()` Z.89-94 — die etablierte Sortier-Semantik `(bucket, order)` für Telegram/Ortsvergleich. Referenz, nicht Ziel dieser Scheibe (AC-5 aus Scheibe 1 hält Telegram/Compare unverändert; dieselbe Erwartung gilt hier). |
| `docs/specs/modules/fix_1575_mail_column_order.md` | Spec Scheibe 1 (bereits umgesetzt, gemergt). Abschnitt „Nicht in dieser Scheibe" beschreibt exakt den Scope dieser Scheibe 2 inkl. der TmpMin-Divergenz-Ursache. |
| `tests/unit/test_mail_column_order.py` | Test-Pattern aus Scheibe 1: misst am Wirkort (`format_email`/gerenderte Mail), nicht an der Sortierfunktion isoliert. `_label_of()`-Helper mappt `metric_id` → Spaltenlabel über `get_col_defs()`. Für Scheibe 2 analog: Spaltenfolge aus dem **Plain**-Text-Teil parsen (Header-Zeile von `_render_text_table`) statt `<thead>`. |
| `.claude/hooks/renderer_mail_gate.py` | Commit-Gate #811: blockiert jeden Commit, der `plain.py` staged, bis (1) `tests/tdd/test_issue_811_mode_matrix.py` grün UND (2) frischer `briefing_mail_validator.py`-Lauf vorliegen. Un-überspringbar seit #1431 (tokenbasierte Git-Erkennung). |
| `.claude/hooks/briefing_mail_validator.py` | Pflicht-Validator für `X-GZ-Mail-Type: trip-briefing`. Prüft u. a. `_has_hourly_table_plain()`, Layer-Konsistenz HTML/Plain (`_check_layer_consistency`). Läuft gegen echt zugestellte Staging-Mail (`gregor-test@henemm.com`, `GZ_IMAP_*`). |

## Existing Patterns

- **Sortiermechanismus bereits etabliert:** `_sorted_by_layout()` in `models.py` (Scheibe 1) sortiert `(bucket, order)` stabil — alle Kanäle inkl. Plain bekommen über `dc.metrics` bereits die richtige Reihenfolge. Es fehlt nur der Renderer-seitige Verbrauch dieser Reihenfolge im Plain-Pfad.
- **HTML macht es vor:** `_col_order` aus `dc.metrics` bauen (enabled + selectable filtern) → `ordered + remaining`-Merge mit der Katalog-Cols-Liste. Dieselbe Logik lässt sich 1:1 auf `_render_text_table()` übertragen (Header-Reihenfolge statt `<th>`-Reihenfolge).
- **Kandidat für geteilten Helper:** Die `_col_order`-Bauschleife (html.py Z.1018-1029) ist reine `dc.metrics`-Iteration ohne HTML-Spezifisches — Extraktion nach `helpers.py` (z. B. `resolve_metric_col_order(dc)`) vermeidet Duplikation zwischen `html.py` und `plain.py`. Kein Trip/Compare-Pendant-Thema (beide Dateien sind Trip-Mail-intern, `email/`-Verzeichnis liegt außerhalb des `pendant_gate`-Scopes `trip-detail/`\`compare-new/`).
- **Nachweis am Wirkort:** Scheibe-1-Tests prüfen die gerenderte Mail, nicht die Sortierfunktion isoliert (Lehre aus #1457). Für Scheibe 2 gilt dasselbe: Plain-Header-Zeile aus der tatsächlichen `render_plain()`-Ausgabe parsen.

## Dependencies

- **Upstream:** `UnifiedWeatherDisplayConfig.get_metrics_for_channel` (bereits sortiert, Scheibe 1) · `MetricCatalog` (`selectable`, `col_key`, `col_label`, `bucket`) · `visible_cols()` Alt-Pfad in `helpers.py`.
- **Downstream:** `renderer_mail_gate.py` (#811, blockiert Commit ohne frischen Validator-Lauf) · `briefing_mail_validator.py` (IMAP-Staging-Check) · `tests/tdd/test_issue_811_mode_matrix.py`.

## Existing Specs

- `docs/specs/modules/fix_1575_mail_column_order.md` — Scheibe 1 (Status: umgesetzt/gemergt), Abschnitt „Nicht in dieser Scheibe" ist die unmittelbare Vorgabe für diese Scheibe 2.
- `docs/reference/mail_validators.md` — Details zu Plausibilitäts-Schwellen und Anti-Stale-Mechanik des Mail-Validators.

## Risks & Considerations

- **Gate #811 ist un-überspringbar:** Commit auf `plain.py` erfordert zwingend frischen `briefing_mail_validator.py`-Lauf gegen echte Staging-Mail (IMAP `GZ_IMAP_*`/Test-Postfach `gregor-test@henemm.com`) — diese Session braucht Staging-Zugriff (im Gegensatz zur Vorgänger-Session).
- **Design-Entscheidung TmpMin-Divergenz:** Da `temperature_cold` nicht user-selectable ist, ist die Zielposition kein PO-Bedienkonzept, sondern eine technische Konsistenzfrage HTML↔Plain. Naheliegende, risikoärmste Richtung: Plain an das bereits produktiv laufende HTML-Verhalten angleichen (nicht umgekehrt) — vermeidet eine zweite Verhaltensänderung am bereits verifizierten HTML-Pfad.
- **AC-3-Parallele zu Scheibe 1:** Für Altbestand-Trips mit `order=0` überall darf sich die Plain-Spaltenfolge nicht ändern (Stabilität von `sorted()` bereits durch Scheibe 1 sichergestellt) — muss auch für den Plain-Renderer explizit getestet werden.
- **Formatierungs-Constraint Plain:** `_render_text_table()` baut feste Spaltenbreiten aus `headers`-Liste (Z.60-71) — die Header-Reihenfolge muss synchron mit der Datenzeilen-Reihenfolge bleiben (beide aus derselben `headers`-Liste, sollte automatisch konsistent sein, aber im Test verifizieren).
- **`visible_cols()` Alt-Pfad wird von html.py UND plain.py geteilt** — eine Änderung an der Funktionssignatur/dem Verhalten des Alt-Pfads könnte html.py mitbetreffen. Sauberer: Reihenfolge-Logik als zusätzlicher Schritt NACH `visible_cols()` (wie html.py es macht), nicht durch Änderung von `visible_cols()` selbst.

## Analysis

*Hinweis: `bug-intake`-Agent lieferte trotz zweifacher Nachfrage keinen inhaltlichen Bericht
(bekanntes Muster, `feedback_developer_agents_go_idle_without_report`). Die vier Investigations-
Fragen aus dem Auftrag wurden daher selbst am Code verifiziert (reine Read-Only-Prüfung,
keine Vermutung).*

### Type

Bug (Feature-Regression an bestehendem Kanal — Plain-Text-Hälfte wurde bei der
HTML-Reihenfolge-Reparatur in Scheibe 1 bewusst ausgeklammert).

### Investigations-Fragen selbst verifiziert

1. **Root Cause vollständig?** Ja, bestätigt. Einzige Stelle, die die Tabellen-Spaltenfolge
   im Plain-Pfad bestimmt, ist `visible_cols(rows)` (Alt-Pfad) in `_render_text_table()`
   (`plain.py:59`) — für **beide** Aufrufstellen (Segment-Tabellen Z.280, Nacht-Tabelle
   Z.287). `build_units_legend`/`build_column_legend` (`helpers.py:520-547`) nutzen
   `visible_cols(rows)` ebenfalls, sind aber Prosa-Aufzählungen (Einheiten-/Spalten-Legende),
   keine Tabellenspalten — das Issue nennt ausdrücklich nur „Spaltenfolge der
   Stundentabelle". Empfehlung: Legenden bewusst außerhalb des Scopes lassen (kein AC).
2. **Weitere Divergenzen außer TmpMin?** Geprüft: alle `selectable=False`-Metriken im
   Katalog sind `temperature_cold` (TmpMin, Alarm-Pseudogröße, col_key vorhanden, steht
   real in den Tabellenzeilen) und `confidence` (`metric_catalog.py:294-307`,
   `default_enabled=False` + hartes PO-Verbot ADR-0005/#710: darf nie als Tabellenspalte
   erscheinen — erreicht die Tabellen-Rows strukturell gar nicht). Keine weiteren
   Kandidaten. TmpMin bleibt die einzige zu klärende Divergenz.
3. **Shared-Helper-Ansatz umsetzbar?** Ja. `dc` liegt in `render_plain()` bereits im Scope
   (Parameter, Z.95); beide `_render_text_table()`-Aufrufe (Segment Z.280, Nacht Z.287)
   können denselben vorab berechneten `col_order` erhalten. Kein struktureller Blocker.
   Empfehlung: die `_col_order`-Bauschleife aus `html.py:1018-1029` (dc.metrics → enabled +
   selectable filtern → Liste von `col_key`s) nach `helpers.py` extrahieren (z. B.
   `resolve_metric_col_order(dc) -> list[str]`), von `html.py` UND `plain.py` genutzt.
   `_render_text_table()` bekommt einen neuen optionalen `col_order`-Parameter, Merge-Logik
   analog `html.py:664-682` (`ordered = Treffer aus cols`, `remaining = Rest in
   Katalog-Reihenfolge`, `cols = ordered + remaining`).
4. **Bestandsdaten-Risiko (order=0, channel_layouts)?** Bereits durch Scheibe 1 auf
   Modell-Ebene abgedeckt: `get_metrics_for_channel()` liefert `dc.metrics` für **jeden**
   Konsumenten (HTML wie Plain) bereits stabil sortiert (`_sorted_by_layout`, Altbestand
   mit `order=0` behält seine Reihenfolge). Plain fängt lediglich an, dieselbe bereits
   sortierte Liste zu konsumieren — kein neues Migrations-/Datenrisiko.

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/email/helpers.py` | MODIFY | Neuer geteilter Helper `resolve_metric_col_order(dc)`, extrahiert aus der `_col_order`-Bauschleife in `html.py` |
| `src/output/renderers/email/html.py` | MODIFY | `_col_order`-Bauschleife (Z.1018-1029) durch Aufruf des neuen Helpers ersetzen — reines Refactoring, Verhalten unverändert (Regressionsschutz per Test) |
| `src/output/renderers/email/plain.py` | MODIFY | `_render_text_table()` um `col_order`-Parameter erweitern (Merge-Logik analog html.py); `render_plain()` berechnet `col_order` einmal aus `dc.metrics` und übergibt ihn an beide Aufrufstellen (Segment- und Nacht-Tabelle) |
| `tests/unit/test_mail_plain_column_order.py` | CREATE | Tests analog `test_mail_column_order.py`, aber am Plain-Text-Wirkort (`render_plain`/Plain-Teil von `format_email`) — Reihenfolge-AC + TmpMin-Konvergenz-AC + Altbestand-AC (order=0 unverändert) |
| `tests/tdd/test_issue_811_mode_matrix.py` | RUN (keine Änderung erwartet) | Gate-Pflichttest (#811) — muss grün bleiben, da `plain.py` und `html.py` gate-geschützte Dateien sind |

### Scope Assessment

- Files: 4 geändert/neu (3 Produktivcode-Dateien MODIFY, 1 Testdatei CREATE)
- Estimated LoC: ~+50/-15 Produktivcode (Helper-Extraktion + Merge-Logik in plain.py), ~+150 Test
- Risk Level: MEDIUM — gate-geschützter Mail-Content-Pfad (#811, betrifft jede Briefing-Mail),
  aber der Mechanismus ist in HTML bereits produktiv erprobt (Scheibe 1, deployt); reines
  Nachziehen + Konsolidieren, keine neue Logik

### Technical Approach

**Empfehlung:** Helper-Extraktion statt Duplikation. `resolve_metric_col_order(dc)` in
`helpers.py` kapselt die enabled+selectable-Filterung aus `dc.metrics`; `html.py` und
`plain.py` rufen ihn gleich auf. Die `ordered+remaining`-Merge-Logik (html.py:664-682)
wird 1:1 in `_render_text_table()` übernommen (Header- UND Datenzeilen-Reihenfolge aus
derselben `cols`-Liste, damit beide synchron bleiben — Risiko aus Context-Dok).

**TmpMin-Konvergenzrichtung:** Plain an das bereits produktive HTML-Verhalten angleichen
(TmpMin landet über den `remaining`-Zweig am Ende, wie in HTML) — nicht umgekehrt. Das ist
kein PO-Bedienkonzept (temperature_cold ist nicht user-selectable), sondern eine technische
Konsistenzentscheidung mit dem risikoärmeren Weg: der bereits verifizierte HTML-Pfad bleibt
unverändert, nur Plain zieht nach.

### Dependencies

Siehe „Dependencies" oben (unverändert seit Context-Phase) — keine neuen Abhängigkeiten
durch die Analyse aufgedeckt.

### Open Questions

- [x] Sollen Einheiten-/Spalten-Legenden der Reihenfolge folgen? → Nein, außerhalb des
  Scopes (Prosa, kein AC im Issue). Empfehlung, keine Rückfrage nötig.
- [x] TmpMin-Konvergenzrichtung? → Plain an HTML angleichen (Empfehlung s.o.), wird als AC
  in der Spec festgeschrieben und dem PO zur Freigabe vorgelegt (Standard-Checkpoint).
