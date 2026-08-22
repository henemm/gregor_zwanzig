# Context: Gewitter-Stufenwörter und -Ampelfarbe aus der kanonischen Quelle speisen (#2010 + #2011)

## Request Summary
Zwei Kanäle bauen die Gewitter-Stufenskala (`ThunderLevel`: NONE/LOW/MED/HIGH) lokal
statt aus der kanonischen Quelle `src/output/metric_format.py` zu lesen: Telegram
(`trip_command_processor.py`, #2010, Wortdrift „mäßig"/„keins" statt „mittel"/„kein")
und die Briefing-Mail-Ampelfarbe (`email/html.py`, #2011, `_thunder_risk_level` weicht
vom eigenen Docstring ab und verschmilzt LOW/MED im Zahlen-Fallback). Diese sechs
Fundstellen sind bereits **namentlich als Altlasten des #1480-Wächters erfasst** — das
ist die verbindliche Liste dessen, was zu sanieren ist.

## Kanonische Quelle (Ziel jeder Sanierung)
`src/output/metric_format.py`:
- `THUNDER_LABEL_DE: dict[ThunderLevel, str]` (Zeile 283) — NONE→"kein", LOW→"leicht",
  MED→"mittel", HIGH→"hoch". NONE fehlt bewusst nicht; Konsumenten mit abweichender
  NONE-Darstellung (z.B. "—") überschreiben nur diesen einen Eintrag lokal.
- `thunder_ampel_band(level: Optional[ThunderLevel]) -> Optional[str]` (Zeile 302) —
  NONE→"green", LOW→"yellow", MED→"orange", HIGH→"red". `None` (keine Aussage) liefert
  `None` — Aufrufer zeigen dafür einen Strich, NIEMALS ein Ampelband (Issue #1491 AC-1).

Vorbild für korrekte Nutzung: `src/output/renderers/narrow.py` und
`src/output/renderers/email/helpers.py` importieren `THUNDER_LABEL_DE` direkt statt
eine eigene Zuordnung zu pflegen.

## Verbindliche Fundstellen-Liste (aus `tests/tdd/test_thunder_scale_local_copy_guard.py::ALTLASTEN`)

Diese Liste ist Teil des #1480-Wächters und **muss beim Fix um exakt diese Einträge
schrumpfen** (`test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` schlägt sonst an —
„Sanierte Stelle => Zeile in ALTLASTEN streichen"):

| Datei | Symbol | Regel | Grund | Issue |
|---|---|---|---|---|
| `src/output/renderers/email/html.py` | `_thunder_risk_level` | B | eigene Stufen-Wort-Kette statt `thunder_ampel_band()`, obwohl Docstring die Angleichung behauptet | #2011 |
| `src/output/renderers/email/html.py` | `_thunder_risk_level` | C | Zahlen-Fallback verschmilzt LOW und MED zu 'watch' | #2011 |
| `src/services/trip_command_processor.py` | `_THUNDER_LABEL` | A | Telegram-Label mit Wortdrift ('mäßig' statt 'mittel') | #2010 |
| `src/services/trip_command_processor.py` | `_MAP_EMOJI` | A | Emoji-Karte mit Wortdrift ('keins'/'mäßig') | #2010 |
| `src/services/trip_command_processor.py` | `_MAP_PLAIN` | A | Klartext-Karte, unabhängig gepflegtes Duplikat von `_MAP_EMOJI` | #2010 |
| `src/services/trip_command_processor.py` | `_handle_hours_drilldown` | B | Stundentabelle verzweigt auf rohe Stufen-Strings mit eigenen Wörtern | #2010 |

**Wichtig:** Die tatsächliche Codelage hat eine vierte #2010-Fundstelle, die das Issue
selbst noch nicht nennt (Zeilennummern haben sich seit Issue-Erfassung verschoben), aber
in `ALTLASTEN` bereits korrekt als `_handle_hours_drilldown` registriert ist — dort
verzweigt die Stundentabelle (Zeile ~806-816, `t_sym = "mäßig"` im MED-Zweig) direkt auf
rohe Strings statt `THUNDER_LABEL_DE` zu lesen.

Zwei weitere Altlasten-Einträge (`day_window.py::_NIGHT_ADDENDUM_WORD`,
`trip_report_scheduler.py::_thunder_entry_from_trend_row` /
`_build_thunder_forecast`) gehören **nicht** zu #2010/#2011 und bleiben unangetastet.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py:139-146` | `_THUNDER_LABEL` — Dict NONE/LOW/MED/HIGH → deutsche Wörter, „mäßig" statt „mittel" |
| `src/services/trip_command_processor.py:223-230` | `_MAP_EMOJI`/`_MAP_PLAIN` — „keins"/„mäßig" statt „kein"/„mittel" |
| `src/services/trip_command_processor.py:806-816` | `_handle_hours_drilldown` — if/elif-Kette mit eigenem `"mäßig"`-Literal für MED |
| `src/services/trip_command_processor.py:1028,1095,1155` | Drei Aufrufstellen von `_THUNDER_LABEL.get(...)` — bleiben unverändert, solange `_THUNDER_LABEL` selbst aus `THUNDER_LABEL_DE` gespeist wird |
| `src/output/renderers/email/html.py:168-204` | `_thunder_risk_level` — eigene if/elif-Kette (String-Zweig) + Zahlen-Fallback, der LOW/MED verschmilzt |
| `src/output/renderers/email/html.py:207-224` | `_row_risk` — einziger Aufrufer von `_thunder_risk_level`, kombiniert Gewitter-Risikostufe mit Wind/Böen/Regen/Sicht zur „schärfsten Stufe" der Zeile (Vokabular `ok/yellow/watch/risk`) |
| `src/output/renderers/email/html.py:843-862` | Zweiter Aufrufer: `elif key == "thunder"` — String-Rohwert nutzt bereits korrekt `thunder_ampel_band()`; nur der `else`-Zweig (numerischer Legacy-Rohwert, `#1491`-Regression AC-10) fällt auf `_thunder_risk_level()` zurück, gemappt über `{"risk": "red", "watch": "orange"}` (kein "yellow"!) |
| `src/output/metric_format.py:279-320` | Kanonische Quelle: `THUNDER_LABEL_DE`, `_THUNDER_AMPEL_BAND`, `thunder_ampel_band()` |
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | #1480-Wächter — `ALTLASTEN` (Zeile 285-347) ist die verbindliche Fundstellen-Liste; `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` (Zeile 1109) verlangt, sanierte Einträge zu streichen |
| `tests/tdd/test_thunder_risk_dot_and_tint.py`, `test_row_risk_thunder_pair_escalation.py` | Bestehende Tests auf `_thunder_risk_level`/`_row_risk` — Verhalten dieser Funktionen ist bereits getestet, Fix darf diese Erwartungen nicht brechen (Vokabular `risk/watch/yellow` muss erhalten bleiben, nur die INTERNE Berechnung ändert sich) |
| `tests/tdd/test_telegram_thunder_low_level.py`, `test_thunder_low_output_channels.py` | Bestehende Tests auf Telegram-Ausgabe der Gewitterstufen — prüfen vermutlich bereits die (noch falschen) Wörter; ggf. Anpassung nötig |

## Existing Patterns
- **Geteilte Quelle statt Kopie** (Issue #1474/#1491-Muster): `narrow.py` und
  `email/helpers.py` importieren `THUNDER_LABEL_DE`/`thunder_ampel_band` direkt, statt
  eigene Zuordnungen zu pflegen — das ist die Bauform, an die #2010/#2011 angeglichen
  werden.
- **Symbolscharfe Whitelist statt Dateiweite**: der #1480-Wächter duldet nur benannte
  Symbole in `metric_format.py`, keine ganze Datei — verhindert, dass eine neue Kopie
  dort unsichtbar entsteht.

## Dependencies
- Upstream: `src/output/metric_format.py::THUNDER_LABEL_DE`, `thunder_ampel_band()`
  (kanonische Quelle, ADR-0025, Issue #1491).
- Downstream:
  - `_THUNDER_LABEL`/`_MAP_EMOJI`/`_MAP_PLAIN` werden an mehreren Telegram-Drilldown-
    und Zusammenfassungsstellen in `trip_command_processor.py` gelesen (Zeilen 1028,
    1095, 1155 u.a.) — deren Aufrufer bleiben unverändert, solange die Dicts selbst
    korrekt aus `THUNDER_LABEL_DE` gespeist werden.
  - `_thunder_risk_level()` wird von `_row_risk()` (Zeilen-Gesamtrisiko der
    Stundentabelle) und von einem zweiten Aufrufer (Zell-Tönung bei numerischem
    Legacy-Rohwert, Zeile 861) genutzt. Beide erwarten weiterhin das Vokabular
    `"risk"/"watch"/"yellow"/None` — die interne Berechnung darf sich ändern, die
    Rückgabewerte-Menge nicht, sonst brechen `_row_risk` und die `{"risk":...,
    "watch":...}`-Zuordnung bei Zeile 861.
  - `tests/tdd/test_thunder_scale_local_copy_guard.py::ALTLASTEN` — muss um die
    sanierten Einträge schrumpfen.

## Existing Specs
- `docs/specs/modules/thunder_scale_guard.md` — Spec des #1480-Wächters, definiert
  Regeln A-D und Duldungsmechanik.
- `docs/specs/modules/thunder_threshold_katalog.md` — evtl. relevante Schwellenwerte-
  Doku (noch nicht gelesen, bei Bedarf in Analyse-Phase).

## Risks & Considerations
- **Vokabular-Bruch bei `_thunder_risk_level`**: `THUNDER_LABEL_DE`/`thunder_ampel_band`
  sprechen `kein/leicht/mittel/hoch` bzw. `green/yellow/orange/red` —
  `_thunder_risk_level` spricht `risk/watch/yellow/None`. Ein einfaches „ruft
  `thunder_ampel_band()` auf" reicht nicht; es braucht eine explizite Zuordnung
  `{green:None (oder "ok"?), yellow:"yellow", orange:"watch", red:"risk"}` — das ist
  Analyse-/Spec-Arbeit, keine mechanische Umbenennung.
- **Toter-Code-Verdacht beim Zahlen-Fallback** (#2011 Abgrenzung): Vor dem Fix klären,
  ob der `isinstance(thunder, str)`-Zweig in der Praxis IMMER greift (weil
  `ThunderLevel` von `str` erbt) und der numerische Fallback (`_safe_float`) nie
  erreicht wird außer im expliziten Legacy-Pfad bei Zeile 861. Ein Test, der den
  Fallback nachweislich erreicht, ist laut Issue der Nachweis — sonst ist „entfernen"
  die richtige Behebung statt „reparieren".
- **NONE-Sonderfall**: `thunder_ampel_band(NONE)` liefert `"green"`, aber
  `_thunder_risk_level` liefert für `"NONE"` `None` (keine Fußzeile-Farbe). Eine direkte
  1:1-Übernahme von `thunder_ampel_band` würde `_row_risk` grün statt "ok" einfärben —
  muss in der Spec explizit entschieden werden.
- **#1480-Wächter als Testorakel**: Nach dem Fix muss `ALTLASTEN` um die sechs Einträge
  schrumpfen, sonst schlägt `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` an.
  Das ist ein zusätzlicher, expliziter Implementierungsschritt (keine Testdatei einfach
  löschen — nur die betroffenen `Altlast(...)`-Zeilen entfernen).
- **Bestehende Tests könnten falsches Verhalten fixieren**: `test_telegram_thunder_low_level.py`
  und `test_thunder_low_output_channels.py` prüfen vermutlich die heutigen (falschen)
  Wörter „mäßig"/„keins" — die Analyse-Phase muss prüfen, ob diese Tests aktualisiert
  werden müssen (Bug-Nachweis-Pflicht: mindestens ein Test muss den Bug aus
  Nutzersicht rot zeigen vor dem Fix).

## Analysis

### Type
Bug (zwei getrennte, aber thematisch verbundene Bugs — beide sanieren Altlasten des
#1480-Wächters).

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/trip_command_processor.py` | MODIFY | `_THUNDER_LABEL`/`_MAP_PLAIN` aus `THUNDER_LABEL_DE` ableiten statt Wert-Kopie; `_MAP_EMOJI` kombiniert weiterhin hartcodierten Emoji-Präfix mit abgeleitetem Label; `_handle_hours_drilldown` (~806-816) auf Lookup gegen dieselbe abgeleitete Karte umstellen (NONE-Sonderfall "—" bleibt) |
| `src/output/renderers/email/html.py` | MODIFY | `_thunder_risk_level()` ruft `thunder_ampel_band()` auf + explizite Übersetzung `{"green":"ok","yellow":"yellow","orange":"watch","red":"risk"}`; Zahlen-Fallback-Zweig bleibt erhalten (aktiv genutzt bei Zeile ~861) |
| `tests/tdd/test_command_reply_channel_emoji.py` | MODIFY | Zeilen 157, 190: `"mäßig"` → `"mittel"` |
| `tests/tdd/test_issue_654_telegram_thunder_drilldown.py` | MODIFY | Zeile 185: `label_keywords` `"keins"`/`"mäßig"` → `"kein"`/`"mittel"` |
| `tests/tdd/test_thunder_scale_local_copy_guard.py` | MODIFY | 6 sanierte `Altlast(...)`-Einträge aus `ALTLASTEN` streichen (sonst `test_altlasten_basislinie_hat_keinen_leerlauf_eintrag` rot) |

### Scope Assessment
- Files: ~5 (2 Produktivdateien, 2 Testdateien mit Wortkorrektur, 1 Wächter-Bereinigung)
- Estimated LoC: ~+25/-20 (deutlich unter 250-LoC-Limit)
- Risk Level: LOW — beide Fixes sind lokal begrenzt, kanonische Quelle bereits etabliert
  und anderswo (`narrow.py`, `email/helpers.py`) korrekt genutzt

### Technical Approach

**#2010:** `_THUNDER_LABEL` und `_MAP_PLAIN` werden aus `THUNDER_LABEL_DE`
(`metric_format.py`) abgeleitet statt einzelne Werte von Hand zu kopieren (z.B.
`{level.name: label for level, label in THUNDER_LABEL_DE.items()}`) — jede
Wert-für-Wert-Ersetzung von Hand wäre derselbe Kopier-Fehler, den #2010 gerade behebt.
`_MAP_EMOJI` kombiniert einen weiterhin hartcodierten Emoji-Präfix (⚪/🟢/🟡/🔴 — kein
Teil von `THUNDER_LABEL_DE`) mit dem abgeleiteten Wort-Suffix. `_handle_hours_drilldown`
verzweigt nicht mehr per if/elif mit eigenem `"mäßig"`-Literal, sondern liest dieselbe
abgeleitete Karte; die NONE-Sonderdarstellung ("—" statt Wort) bleibt als eigener Zweig
bestehen. Die drei reinen Lesestellen (`_THUNDER_LABEL.get(...)`, ~Zeilen 1028/1095/1155)
bleiben unverändert.

**#2011:** `_thunder_risk_level()` ruft `thunder_ampel_band()` tatsächlich auf (löst die
Docstring-Diskrepanz) und übersetzt dessen vierwertiges Ampel-Vokabular
(`green/yellow/orange/red`) explizit auf das von `_row_risk()` erwartete Vokabular
(`ok/yellow/watch/risk`/`None`): `{"green":"ok","yellow":"yellow","orange":"watch",
"red":"risk"}`. **NONE/green → `"ok"`** (nicht `None` wie bisher) — geprüft
verhaltensneutral: weder `_row_risk` noch die zweite Aufrufstelle (Zeile ~861,
`{"risk":...,"watch":...}.get(...)`) unterscheiden `None` von `"ok"`, beide fallen an
jeder Prüfstelle gleich wirkungslos durch. `ThunderLevel(str, Enum)` verhält sich beim
Vergleich wie sein String-Wert — die bestehende `.upper()`-Normalisierung vor dem
`thunder_ampel_band()`-Aufruf bleibt erhalten, damit sowohl Enum-Instanzen als auch rohe
Strings funktionieren.

**Korrektur gegenüber der Kontext-Phase:** Der Zahlen-Fallback-Zweig in
`_thunder_risk_level` (`num > 20`/`num > 0`) ist **NICHT tot**. Er wird beim zweiten
Aufrufer (Zeile ~855-862, `else`-Zweig für nicht-string `raw_val`) für ältere Test-/
Datenpfade mit rohem numerischem `thunder`-Wert aktiv gebraucht (Kommentar Zeile
849-854 bestätigt das explizit als einzigen Zweck). Bleibt erhalten — Entfernen wäre
eine stille Regression auf `None`-Zellfärbung für diese seltene Datenform.

### Dependencies
Bestätigt aus Context-Phase, keine neuen Funde. `_row_risk`-Vokabular bleibt stabil
(`_RISK_LEVEL_TO_AMPEL` kennt weiterhin genau `ok/yellow/watch/risk`).

### Open Questions
Keine offenen — beide Ansätze sind vollständig bestimmt. Reihenfolge: #2010 zuerst
(einfachere reine Label-Ableitung), #2011 danach (Vokabular-Übersetzung).
