# Context: Fix #1505 — Orts-Vergleich, Ausblick-Zeile verschwindet still

## Request Summary

Der 3-Tages-Ausblick im Orts-Vergleich verschwindet heute wortlos, wenn ein Fehler vorlag oder
Daten fehlen — für den Empfänger ununterscheidbar vom Normalfall (Trend vorhanden, aber leer).
Compare-Pendant zu #1486 (Trip-Pfad, bereits geliefert), mit strukturell anderem Datenpfad.

## Related Files

| File | Relevanz |
|------|----------|
| `src/output/renderers/email/compare_html.py:1115-1147` (`_render_location_outlook`) | HTML-Renderer, **zwei** stille Ausstiege: `loc.error is not None or not loc.outlook_hourly_data` (Z.1128) UND `if not rows: return ""` (Z.1131, nach `_build_location_outlook_rows`) — im Issue-Text wird nur der erste genannt |
| `src/output/renderers/comparison.py:260-335` (`render_comparison_text`/`render_comparison_plain`) | **Klartext-Pendant**, eigene, unabhängige stille Bedingung: `outlook_rows = [...] if outlook_enabled and loc_result.outlook_hourly_data else []` (Z.280-284) — bei leer/Fehler entfällt der Block hier ebenso lautlos, UND bei `not have_hourly and not outlook_rows` fällt der ganze Ort aus der Mail (Z.284/`continue`) |
| `src/services/comparison_engine.py:127-169` | Datenerzeugung: `loc.error` bei Fetch-Fehler (Z.135, Z.352 Exception) ODER `outlook_hourly_data = []`, wenn `_outlook_days` (Tage nach `_last_detail_day` innerhalb der 96h-Fetch-Antwort) leer bleibt |
| `src/app/user.py:117-` (`LocationResult`) | Datenklasse mit `error: Optional[str]`, `outlook_hourly_data: list` — kein eigenes Zustandsfeld, das Grund von Leere unterscheidet |
| `src/output/renderers/email/outlook_state_hint.py` | Fertiger, geteilter Baustein aus #1486: `OutlookState`-Enum (`FOUND/NO_STAGES/BEYOND_HORIZON/UNAVAILABLE`), `outlook_state_text/should_warn/render_*_html/render_*_plain` — bewusst generisch (keine Trip-Typen in Signatur), für Compare vorgesehen |
| `src/app/models.py:780-810` | `OutlookState`(Enum)/`TrendResult`(Dataclass) — Domänenschicht, hier liegt die eigentliche Zustandslogik |
| `src/output/renderers/email/outlook.py` | GETEILTER Tabellen-Renderer (`build_outlook_row`, `render_outlook_table`, `render_outlook_plain`) — bleibt unverändert, Paritäts-Golden (`tests/tdd/test_trip_outlook_parity.py`) |
| `tests/tdd/test_outlook_state_named_not_silent.py`, `tests/tdd/test_outlook_state_visible_in_channels.py` | Bestehende Tests für den Trip-Pfad — Vorbild für Compare-Äquivalent, NICHT verändern (Trip-Verhalten fixiert) |

## Existing Patterns

- **#1486 (Trip-Pfad, geliefert 2026-08-05):** `_build_stage_trend()` gibt `TrendResult(rows, state, horizon_days)` zurück; vier Renderer (HTML/Plain/Compact/Telegram) prüfen `if multi_day_trend: <Tabelle> elif outlook_state not in (None, FOUND): <Zustandstext>`. Styling: `NO_STAGES`/`BEYOND_HORIZON` = neutraler Fließtext (`G_INK_MUTED`, kein Rahmen), `UNAVAILABLE` = Danger-Box/`⚠️`.
- **Compare hat NUR E-Mail (HTML + Klartext) für den Ausblick** — geprüft: `render_compare_telegram()` und `render_compare_sms()` (`comparison.py:651-`, `942-`) haben KEINE `outlook_*`-Parameter. Der Ausblick existiert im Compare-Pfad nur in der E-Mail (zwei Fassungen). Kleinerer Blast Radius als #1486 (4 Kanäle).
- **`undelivered_hint.py`** wird bereits von `compare_html.py` als geteilter, kanal-neutraler Hinweisbaustein genutzt (Z.1563-1569) — Präzedenzfall für „Hinweisbaustein rein, Compare bindet ein".

## Dependencies

- **Upstream:** `comparison_engine.py::ComparisonEngine.run()` — einzige Quelle für `LocationResult.error`/`outlook_hourly_data`. `target_date` ist bei Scheduler-Versand `date.today()` (Compare hat kein „Tour zu Ende"-Konzept wie Trip-Etappen); nur im interaktiven Preview-Pfad (`compare_preview_service.py`) frei wählbar — dort könnte ein weit in der Zukunft liegendes `target_date` faktisch den Vorhersagehorizont überschreiten.
- **Downstream:** Renderer-Commit-Gate #811 greift auf `compare_html.py`. `email_spec_validator.py` (Marker `X-GZ-Mail-Type: compare`) ist der Pflicht-Validator vor „E2E bestanden" — validiert nur den HTML-Body (Klartext ist blinder Fleck, s. `reference_compare_mail_plaintext_blind_spot`).

## Existing Specs

- `docs/specs/modules/fix_1486_outlook_silent_exit.md` (v1.0, Trip-Pfad) — Abschnitt „Known Limitations" benennt den Compare-Bug ausdrücklich als eigenständig, NICHT 1:1 übertragbar.
- `docs/specs/modules/multi_day_trend.md` (v5.0) — Trip-Ausblick-Spec, referenziert nicht den Compare-Pfad.
- Kein bestehendes Spec-Modul für den Compare-Ausblick-Zustand.

## Risks & Considerations

1. **Drei stille Ausstiege, nicht zwei.** Das Issue nennt nur `loc.error is not None or not loc.outlook_hourly_data` (Z.1128). Gemessen existiert ein dritter, unabhängiger Ausstieg: `if not rows: return ""` nach `_build_location_outlook_rows()` (Z.1131) — auch wenn `outlook_hourly_data` nicht leer ist, kann die Zeilenbildung leer zurückkommen (z.B. Metrik-Filterung). Muss im Zustandsmodell mitgedacht werden.
2. **Klartext-Pfad ist eigenständig fehlerhaft, nicht nur ein zweiter Aufrufer.** `comparison.py` hat eine eigene Bedingung, die NICHT von einer Zustandskorrektur in `compare_html.py` mitgefixt wird. Beide Dateien müssen geändert werden. Zusätzliche Falle: fehlt sowohl Stundenverlauf als auch Ausblick, fällt der Ort im Klartext-Pfad komplett aus der Mail (Z.284), im HTML-Pfad nicht (dort bleibt nur der Ausblick-Block leer) — dieses Auseinanderlaufen ist bereits vorhanden und nicht Teil des Ausblick-Bugs, aber beim Umbau sichtbar.
3. **„Leer ≠ unbekannt" (Lehre aus #1492 S2b):** `outlook_hourly_data = []` kann heißen „Horizont/Fetch-Fenster erschöpft" (analog Klasse B) ODER „Fetch fehlgeschlagen, aber `error` aus irgendeinem Grund nicht gesetzt" — die beiden Fälle sind im aktuellen Datenmodell nicht scharf getrennt. Muss in der Spec-Phase geklärt werden, ob Compare eine eigene, kleinere Zustands-Taxonomie braucht (kein Trip-Äquivalent zu `NO_STAGES`, da Compare kein „Tour zu Ende" kennt) oder ob nur `UNAVAILABLE` + `FOUND` reichen.
4. **Kein Compare-Äquivalent zu `NO_STAGES`.** Trip kennt „Tour ist zu Ende" als normalen, nicht-warnungswürdigen Grund. Compare hat kein Etappen-Konzept — die Frage, ob es hier überhaupt einen „harmlosen Leer"-Zustand gibt (oder ob leer bei Compare IMMER auf Fehler/Datenlücke hindeutet, weil das 96h-Fenster normalerweise ausreicht), ist eine Analyse-Entscheidung mit Konsequenz für Logging (WARNING ja/nein) und Text.
5. **Pendant-Sperre (#1481 B):** Neue Dateien in `compare_html.py`-Nähe oder in `comparison.py` sind okay (Bestandsdateien, keine Neuanlage), aber ein etwaiger neuer Compare-spezifischer Hilfsbaustein braucht entweder Ablage unter `shared/`-Äquivalent (hier: `outlook_state_hint.py` direkt wiederverwenden, keine Kopie) oder eine `gz-eigenstaendig`-Begründung.
6. **Renderer-Commit-Gate #811 + Mail-Validator-Pflicht** vor jedem Commit, der `compare_html.py` staged.
7. **`OutlookState`/`TrendResult` liegen in `app/models.py`** (Domänenschicht) — falls Compare eine eigene, kleinere Enum-Teilmenge braucht, ist zu klären: neue Werte im bestehenden Enum ergänzen oder eigenen State für Compare definieren (Architekturfrage für die Spec-Phase).

## Scope-Abgrenzung (aus Issue #1505 + Known-Limitations #1486)

**In Scope:** `compare_html.py::_render_location_outlook()`, `comparison.py` (Klartext-Ausblick-Block),
ggf. `comparison_engine.py` (nur falls Fehler-vs-leer schärfer unterschieden werden muss),
Wiederverwendung von `outlook_state_hint.py` (kein Nachbau).

**Explizit NICHT in Scope:** `render_compare_telegram`/`render_compare_sms` (kein Ausblick dort),
`outlook.py` (geteilter Tabellen-Renderer, unverändert), #1563 (Vertretungshinweis — anderer Bug,
selbe Datei, andere Zeilen).

**PO-Entscheidung 2026-08-08 (eng vs. breit):** Fix bleibt auf die Ausblick-Zeile begrenzt.
`comparison.py:275` (`if loc_result.error is not None: continue` — lässt bei Fehler den GESAMTEN
Orts-Block inkl. Stundenverlauf aus dem Klartext verschwinden, nicht nur den Ausblick) bleibt
UNVERÄNDERT. Das ist breiter als der Ausblick-Bug (betrifft auch Stundenverlauf) und geht als
Nebenbefund nach #1199, kein eigenes Issue, kein Teil dieses Fixes.

## Analysis

### Type
Bug (nutzersichtbares Fehlverhalten, Compare-Pendant zu #1486).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/output/renderers/email/compare_html.py` | MODIFY | `_render_location_outlook()`: die drei stillen `return ""`-Ausstiege (Z.1128 `loc.error`/`not outlook_hourly_data`, Z.1131 `not rows`) werden zu einem einzigen Zustands-Check zusammengeführt, der bei „nichts zu zeigen" `render_outlook_state_html(OutlookState.UNAVAILABLE)` aus dem bestehenden `outlook_state_hint.py` rendert statt `""` |
| `src/output/renderers/comparison.py` | MODIFY | `render_comparison_text`/Klartext-Ausblick-Block (Z.280-284): dieselbe Zusammenführung für den Fall `loc_result.error is None` (der Fehlerfall bleibt bei Z.275 unverändert, s.o. PO-Entscheidung); nutzt `render_outlook_state_plain(OutlookState.UNAVAILABLE)` |
| `src/services/comparison_engine.py` | MODIFY | Zwei bisher fehlende `logger.warning(...)`-Aufrufe: (a) wenn `raw_result.get("error")`/Exception zu `LocationResult(error=...)` führt (Z.~135, Z.~352 — aktuell komplett unprotokolliert), (b) wenn `outlook_hourly_data` nach erfolgreichem Fetch leer bleibt (Z.~167) |
| `tests/tdd/test_compare_outlook_state_named_not_silent.py` (neu) | CREATE | Analog zu `tests/tdd/test_outlook_state_named_not_silent.py` (Trip-Pfad) — HTML + Klartext, alle Ursachen (`error`, leeres `outlook_hourly_data`, leere `rows`), inkl. `caplog`-Prüfung |
| `docs/specs/modules/fix_1505_compare_outlook_silent_exit.md` (neu) | CREATE | Spec-Modul, referenziert `fix_1486_outlook_silent_exit.md` als Vorbild |

Kein neues Produktivmodul nötig — `outlook_state_hint.py` wird unverändert wiederverwendet
(keine neuen `OutlookState`-Werte, keine Compare-eigene Kopie, Pendant-Sperre #1481 B bleibt
unberührt weil keine neue Datei in einem einseitigen Verzeichnis entsteht).

### Scope Assessment
- Files: 3 Produktiv-Änderungen (kein neues Produktivmodul) + 1 neue Testdatei + 1 neue Spec
- Estimated LoC: ~60-100 (Produktivcode ~30-50, Tests ~40-60) — innerhalb des 250-LoC-Budgets,
  kein `loc_limit_override` nötig
- Risk Level: MEDIUM (Renderer-Commit-Gate #811 greift auf `compare_html.py`; Mail-Validator-Pflicht
  vor „E2E bestanden"; zwei unabhängige Renderer müssen konsistent geändert werden)

### Technical Approach

**Zwei-Zustands-Modell statt Trips Vier-Zustands-Modell (bewusste Vereinfachung, kein Bug):**
Compare hat kein „Tour zu Ende"-Konzept (kein `NO_STAGES`-Äquivalent) und `target_date` ist bei
Scheduler-Versand `date.today()` mit festem 96h-Fetch-Fenster — ein `BEYOND_HORIZON`-Fall ist im
Regelbetrieb praktisch ausgeschlossen. Alle drei bestehenden stillen Ursachen (`loc.error`,
leeres `outlook_hourly_data`, leere `rows`) werden deshalb einheitlich als
`OutlookState.UNAVAILABLE` behandelt — Wiederverwendung des bestehenden Enum-Werts aus #1486, keine
neue Taxonomie nötig.

**Single-Source-Logging:** Die neuen WARNING-Logs kommen in `comparison_engine.py::run()` (Datenschicht,
läuft genau einmal pro Ort und Vergleichslauf) — NICHT in den Renderern, weil `render_compare_email()`
(`comparison.py:410-`) HTML- und Klartext-Renderer für dasselbe `ComparisonResult` in einem Aufruf
verkettet; ein Log in beiden Renderern hätte doppelt geloggt.

### Dependencies
Siehe „Related Files"/„Dependencies" oben — keine neuen Abhängigkeiten, nur Wiederverwendung.

### Open Questions
- [x] Klartext-Fehlerfall (Z.275) eng oder breit? → PO-Entscheidung: eng, Nebenbefund #1199.
