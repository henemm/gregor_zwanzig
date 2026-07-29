---
entity_id: fix_1418_gewitter_risikopunkt
type: bugfix
created: 2026-07-29
updated: 2026-07-29
status: draft
version: "1.0"
tags: [bugfix, gewitter, ampel, issue-1418, epic-1419]
---

<!-- Issue #1418 (Fehler 1) — Scheibe S1 von Epic #1419 -->

# Gewitter-Risikopunkt und Zellfärbung (Scheibe S1)

## Nachtrag 2026-07-29 — Umfang geschrumpft, AC-1 ist anderweitig erledigt

Diese Spec entstand parallel zu einer zweiten Sitzung, die denselben Issue
bearbeitet und ihren Fix zuerst geliefert hat (Commit `659ada95`, live
2026-07-29). Dort ist **AC-1 (Risiko-Punkt reagiert auf Gewitter) bereits
umgesetzt** — über einen eigenen Helfer `_thunder_risk_level()` in
`html.py`, nicht über `thunder_ordinal()`. Der dortige Weg behält zusätzlich
den historischen Zahlenvergleich als Fallback, um den AC-7-Regressionsschutz
aus #1377 zu bedienen.

**Verbindliche PO-Entscheidung 2026-07-29:** Der bereits gelieferte Code
bleibt **unangetastet**. Diese Spec deckt nur noch die dort ausdrücklich
offen gelassene Lücke ab:

| AC | Status |
|---|---|
| AC-1 (Punkt bei HIGH → rot) | **erledigt durch `659ada95`** — nicht erneut umsetzen |
| **AC-2 (Gewitterzelle bei HIGH → `#f6c5bf`)** | **offen — Gegenstand dieser Lieferung** |
| **AC-3 (MED → Zelle `#fad6b8`)** | **Zellteil offen**; der Punkt-Teil ist durch `659ada95` erledigt |
| AC-4 (NONE/fehlend bleibt unauffällig) | für den Punkt erledigt; gilt weiter für die Zelle |

Gemessen gegen den Stand `346c3d16`: von den vier Tests in
`tests/tdd/test_thunder_risk_dot_and_tint.py` sind AC-1 und AC-4 grün, AC-2
und AC-3 rot. Das ist der RED-Nachweis für die verbleibende Arbeit.

**Abweichung von „Implementation Details" unten:** Der Abschnitt „Stelle 1
(`_row_risk`)" ist gegenstandslos. Für „Stelle 2 (Zell-Tönung)" gilt
zusätzlich: Werkzeug ist der bereits vorhandene `_thunder_risk_level()` aus
`659ada95`, **nicht** `thunder_ordinal()` — eine zweite Stufenquelle direkt
neben der ersten wäre genau die Doppelung, die dieses Projekt vermeidet. Die
Zuordnung `'risk'` → `#f6c5bf`, `'watch'` → `#fad6b8`, `None` → ungefärbt
bleibt unverändert.

## Approval

- [ ] Approved

## Purpose

In der Briefing-Mail zeigt die Gewitterspalte pro Stunde korrekt ein Symbol
(⚡/⚡⚡) und einen Text („mögl."/„hoch"), aber der Risiko-Punkt am Zeilenende
bleibt bei Gewitter immer grün und die Gewitterspalte bleibt immer ungefärbt.
Ursache: Der Gewitterwert ist ein Stufenwort (`ThunderLevel`-Enum: NONE/MED/
HIGH), wird an zwei Stellen aber als Zahl gelesen (`float("HIGH")` wirft eine
Ausnahme und fällt still auf 0 zurück). S1 stellt die Reaktion des Punkts und
der Zellfärbung auf Gewitter wieder her — mit dem heutigen Stufenmodell, ohne
das Vier-Stufen-Modell aus #1419 vorwegzunehmen.

## Source

- **File:** `src/output/renderers/email/html.py`
- **Identifier:** `_row_risk` (Zeilen 148–179), Zell-Tönung innerhalb
  `_render_html_table` (Zeilen 622–659)
- **Schicht:** Python-Core (`src/output/renderers/email/`)

## Estimated Scope

- **LoC:** ~20–30 in `html.py`, plus Testanpassungen
- **Files:** 1 Produktivdatei + 1 bestehende Testdatei (Ersatz zweier Tests) +
  Golden-Snapshots (`tests/golden/email/*-html.txt`, regeneriert, zählen nicht
  als LoC)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `thunder_ordinal()` (`src/output/metric_format.py:221-229`) | upstream | einziges zu nutzendes Werkzeug — liefert die kanonische Ordnung NONE=0 < MED=1 < HIGH=2, verträgt sowohl `ThunderLevel`-Instanzen als auch rohe Namen-Strings |
| `ThunderLevel` (`src/app/models.py:35-39`) | upstream | `str`-Enum, einzige Quelle: `providers/openmeteo.py:754` aus WMO-Code 95/96/99 |
| `compare_html._THUNDER_SEV` (`src/output/renderers/email/compare_html.py:157`) | Vorbild | Farbzuordnung `{"MED": "warn", "HIGH": "danger"}` — S1 übernimmt dieselbe Aussage in Trip-Farben |
| `_render_html_table` (`html.py`) | downstream | einziger Aufrufer von `_row_risk` (Zeile 673) und der Zell-Tönung |
| `docs/specs/modules/ampel_schwellen_renderer.md` | Spec | regelt die übrigen Katalog-Schwellen desselben Renderers; Gewitter dort ausdrücklich ausgenommen — diese Spec füllt genau diese Lücke, ohne den Katalogweg zu nutzen (s. „Implementation Details") |

## Implementation Details

### 1. `_row_risk` (`html.py:148-179`)

Heute: `thunder = _safe_float(r.get("thunder"))`, danach `thunder > 20` (Zeile
158, führt zu `"risk"`) und `thunder > 0` (Zeile 177, führt zu `"watch"`).
Beide Vergleiche laufen ins Leere, weil `_safe_float` ein `ThunderLevel`-Enum
nicht in eine Zahl umwandeln kann und dann `0.0` zurückgibt.

Soll: `thunder_ordinal(r.get("thunder"))` ersetzt `_safe_float(...)` an dieser
Stelle. Die beiden Zahlenvergleiche werden durch einen Stufenvergleich
ersetzt:

- Ordinal `2` (HIGH) → sofort `"risk"` (ersetzt `thunder > 20`)
- Ordinal `1` (MED) trägt zum `"watch"`-Ergebnis bei, zusammen mit den
  bereits vorhandenen `yellow`/`orange`-Stufen der übrigen Metriken (ersetzt
  `thunder > 0`)
- Ordinal `0` (NONE oder `None`) trägt nichts bei

Die übrige Logik (Wind/Böen/Regen/Regenwahrscheinlichkeit/Sicht über
`severity_for`) bleibt unverändert.

### 2. Zell-Tönung (`html.py:622-659`, konkret die `elif key == "thunder"`-
Zeile 658)

Heute: `numeric = float(raw_val) if raw_val is not None else None` (Zeile
624) liefert für ein `ThunderLevel`-Enum immer `None` (die Ausnahme wird
gefangen). Die Bedingung `key == "thunder" and numeric is not None and
numeric > _THUNDER_THRESHOLD` (Zeile 658) ist dadurch strukturell nie erfüllt
— die Spalte bleibt immer ungefärbt.

Soll: Dieser `elif`-Zweig liest für `thunder` nicht `numeric`, sondern
`thunder_ordinal(raw_val)` direkt aus dem Roh-Wert der Zelle (`raw_val`, nicht
über die `float()`-Konvertierung). Farbzuordnung:

- Ordinal `2` (HIGH) → `"#f6c5bf"` (rot — dieselbe Farbkonstante, die die
  Zell-Tönung an dieser Stelle bereits für andere Metriken auf Stufe „rot"
  verwendet)
- Ordinal `1` (MED) → `"#fad6b8"` (orange — dieselbe Farbkonstante wie
  „orange" bei den übrigen Metriken)
- Ordinal `0` (NONE oder `None`) → keine Tönung (`cell_bg` bleibt `None`)

Diese zweistufige Farbabbildung (rot/orange, kein Gelb) ist bewusst: Gewitter
kennt nur zwei Warnstufen (MED/HIGH), nicht drei wie die übrigen Metriken.

**Erreichbarkeit verifiziert (2026-07-29):** Der `elif key == "thunder"`-Zweig
wird tatsächlich erreicht — keine der beiden vorangehenden Verzweigungen fängt
Gewitter ab. `"thunder"` steht weder in `_COL_KEY_TO_METRIC_ID`
(`html.py:565-571`) noch in `_FALLBACK_COL_KEY_TO_METRIC_ID` (`html.py:577-584`),
und `build_html_indicator_keys` (`helpers.py:989-1009`) filtert hart gegen die
Whitelist `_AMPEL_CAPABLE_METRIC_IDS = {wind, gust, precipitation,
rain_probability, cape}`, in der Gewitter nicht vorkommt. `indicator_keys` kann
`"thunder"` daher in keinem Produktivpfad enthalten (einziger Erzeuger:
`email/__init__.py:113`).

### Ausdrücklich NICHT zu tun

- **Nicht über `severity_for()` / den Metrik-Katalog gehen.** Der Katalog
  führt für `thunder` kein `display_thresholds`; `severity_for("thunder", …)`
  liefert für jeden Eingabewert `None` — unabhängig davon, was man ihm
  übergibt. Ein Fix, der Gewitter naiv in den `severity_for`-Pfad hängt
  (z. B. analog zum `elif`-Zweig für Wind/Regen/Sicht), würde weiterhin gar
  nichts färben — und das wäre nicht sofort sichtbar, weil kein Fehler
  geworfen wird, sondern nur wieder `None` zurückkommt. Diese Spec verlangt
  ausdrücklich den direkten Weg über `thunder_ordinal()`.
- **Nicht `thunder_label_value()` verwenden.** Das ist eine andere Skala
  (SMS-Render-Werte `{0, 2, 3}`, ADR-0025) und für diesen Zweck falsch.
- **Kein viertes Punkt-Vokabular.** Der Risiko-Punkt bleibt bei drei Farben
  (`ok`/`watch`/`risk`); MED trägt zu `"watch"` bei, HIGH zu `"risk"` —
  dieselbe Abbildung, die die übrigen Metriken schon für `yellow`/`orange`
  bzw. `red` verwenden.

## Expected Behavior

- **Input:** `r["thunder"]` als `ThunderLevel`-Enum-Instanz, als roher
  Namen-String (`"NONE"`/`"MED"`/`"HIGH"`) oder als `None`
- **Output:**
  - Risiko-Punkt am Zeilenende: HIGH → rot (`"risk"`), MED → orange
    (`"watch"`, zusammen mit anderen Metriken), NONE/`None` → kein Beitrag
  - Gewitterzelle: HIGH → rote Hinterlegung (`#f6c5bf`), MED → orange
    Hinterlegung (`#fad6b8`), NONE/`None` → keine Hinterlegung
- **Side effects:** Golden-Snapshots (`tests/golden/email/*-html.txt`), die
  bislang „nie roter Gewitterpunkt" konservieren, ändern sich für jede Zeile
  mit Gewitterlage und müssen bewusst neu abgenommen werden.

## Sichtbare Wirkung (bewusst, PO-informiert)

Eine Stundenzeile mit Gewitterstufe „hoch" zeigt künftig einen roten Punkt am
Zeilenende und eine rot hinterlegte Gewitterzelle — heute bleibt in diesem
Fall der Punkt grün und die Zelle ungefärbt, obwohl das Symbol ⚡⚡ bereits
korrekt erscheint. Das ist die eigentliche Fehlerbehebung dieser Scheibe.

## Bestehende Tests, die ersetzt werden

`tests/tdd/test_renderer_katalog_schwellen.py`:

- `test_ac7_thunder_row_risk_unchanged` (Zeilen 246–253) füttert
  `_row_risk({"thunder": 25})` und erwartet `"risk"` — eine Zahl, die im
  Produktivpfad nie vorkommt (`r["thunder"]` trägt dort immer ein Enum oder
  einen Namen-String). Dieser Test zementiert exakt die falsche Annahme, die
  den Bug ausmacht.
- `test_ac7_thunder_cell_tint_unchanged` (Zeilen 256–263) füttert
  `{"thunder": 25.0}` und erwartet Tönung `"orange"` — dieselbe falsche
  Datenform.

Nach der Test-Politik des Projekts (CLAUDE.md, „Test-Politik: Zwei
Schichten") prüfen beide Tests veraltetes Verhalten und werden **ersetzt**,
nicht übersprungen und nicht gelöscht ohne Ersatz. Die Ersatztests füttern
`ThunderLevel`-Enum-Werte (bzw. die entsprechenden Namen-Strings) und prüfen
die neuen, korrigierten Erwartungen aus AC-1 bis AC-4.

## Acceptance Criteria

- **AC-1 (Risikopunkt bei hoher Gewittergefahr):** Given eine Stundenzeile mit
  Gewitterstufe HIGH und sonst unauffälligen Werten / When die Briefing-Mail
  gerendert wird / Then zeigt der Risiko-Punkt am Zeilenende Rot — heute
  bleibt er in diesem Fall grün, obwohl das Gewittersymbol ⚡⚡ bereits korrekt
  in der Zelle erscheint.
  - Test: Ganzer Renderer-Aufruf (`_render_html_table` bzw. äquivalenter
    Aufruf der Trip-Mail-Erzeugung) mit einer Zeile `{"thunder":
    ThunderLevel.HIGH, ...}`; das erzeugte HTML enthält die rote
    Punktfarbe für diese Zeile, kein isolierter Aufruf nur der Hilfsfunktion.

- **AC-2 (Gewitterzelle bei hoher Gewittergefahr):** Given dieselbe
  Stundenzeile mit Gewitterstufe HIGH / When die Briefing-Mail gerendert
  wird / Then ist die Gewitterspalte dieser Zeile rot hinterlegt
  (`#f6c5bf`) — heute bleibt sie in jedem Fall ungefärbt, unabhängig vom
  Wert.
  - Test: dasselbe gerenderte HTML wie AC-1; die Zell-Hintergrundfarbe der
    Gewitterspalte ist nicht mehr leer/transparent, sondern die rote
    Tonwert-Farbe.

- **AC-3 (mittlere Gewittergefahr färbt orange, nicht rot):** Given eine
  Stundenzeile mit Gewitterstufe MED / When die Briefing-Mail gerendert wird
  / Then zeigt der Risiko-Punkt „Achtung" (orange/watch) und die
  Gewitterzelle ist orange hinterlegt (`#fad6b8`) — nicht rot, nicht grün.
  Dieser AC sichert die Mittelstufe bereits jetzt korrekt ab, obwohl kein
  Wetterdienst heute MED tatsächlich liefert (das ist eine spätere,
  eigenständige Scheibe desselben Epics); die Abbildung muss aber schon
  jetzt stimmen.
  - Test: gerendertes HTML mit einer Zeile `{"thunder": ThunderLevel.MED,
    ...}`; Punktfarbe „watch"-Ton, Zellfarbe `#fad6b8`.

- **AC-4 (keine Gewittergefahr bleibt unauffällig, Regressionsschutz):**
  Given eine Stundenzeile mit Gewitterstufe NONE bzw. ganz ohne
  Gewitterwert (`None`) und sonst unauffälligen Werten / When die
  Briefing-Mail gerendert wird / Then bleibt der Risiko-Punkt grün und die
  Gewitterzelle ungefärbt — wie heute, damit die Behebung von AC-1/AC-2
  keine falschen Positiv-Meldungen erzeugt.
  - Test: gerendertes HTML mit `{"thunder": ThunderLevel.NONE, ...}` sowie
    zusätzlich mit fehlendem `"thunder"`-Schlüssel; beide bleiben grün bzw.
    ungefärbt.

## Known Limitations

- **Die unerreichbare Mittelstufe MED selbst ist nicht Teil dieser Scheibe.**
  Kein Provider liefert heute `ThunderLevel.MED` — das ist Scheibe S2 des
  Epics #1419 (eigene Datenquelle nötig). AC-3 sichert lediglich zu, dass die
  Farbabbildung bereits korrekt ist, damit S2 ohne weiteren Eingriff an
  dieser Stelle wirksam wird.
- **`_render_mobile_hour_list` (`html.py:216`) bleibt außen vor.** Verifiziert
  per Grep: seit Commit `bf5ef21f` ohne jeden Aufrufer, toter Code (= #1418
  Fehler 3). Eine Änderung dort hätte keine Nutzer-Wirkung. Kandidat für
  einen Sammel-Eintrag (#1199), keine eigene Umstellung in S1.
- **„Keine Aussage" (`None`) bleibt vorerst wie heute ohne eigene Behandlung.**
  Ein fehlender Gewitterwert trägt weiterhin nicht zum Risiko-Punkt bei
  (AC-4). Das steht in Spannung zum `None`-Kontrakt aus #1377 („keine
  Aussage ist nicht dasselbe wie Entwarnung") — Gewitter überlebt heute
  keinen Ausfall des Hauptwetterdienstes unauffällig sichtbar. Eine saubere
  Auflösung hängt an späteren Scheiben (S3/S4) desselben Epics und wird hier
  bewusst nicht vorweggenommen.
- **Die Risiko-Legende (`html.py:1381-1386`) führt vier Farben, gerendert
  werden nach dieser Änderung weiterhin nur drei** (`_RISK_DOT_COLORS`).
  Diese Diskrepanz bestand bereits vor S1 und wird hier nicht behoben —
  Kandidat für den Sammel-Eintrag #1199.
- **Der Katalogweg (`severity_for`/`display_thresholds`) trägt für Gewitter
  weiterhin nicht.** Diese Scheibe löst das bewusst über den direkten
  `thunder_ordinal()`-Vergleich, nicht über den Katalog — eine spätere
  Erweiterung des Katalogs um Gewitterschwellen (falls sie je käme) müsste
  diese Stelle erneut anfassen.

## Validierung (PFLICHT vor Commit)

`html.py` ist eine Mail-Inhalts-Datei — das Renderer-Commit-Gate (#811)
greift und blockiert den Commit, bis beides frisch vorliegt:

1. `uv run pytest tests/tdd/test_issue_811_mode_matrix.py` grün
2. Ein erfolgreicher Lauf von `uv run python3
   .claude/hooks/briefing_mail_validator.py` gegen eine echt zugestellte
   Staging-Mail (Marker `X-GZ-Mail-Type: trip-briefing`)

„E2E bestanden" darf nur bei Exit 0 des Validators gesagt werden — kein Mock,
keine Gmail-Zustellung, ausschließlich Stalwart-Test-Postfach.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Fehlerbehebung eines bestehenden, bereits
  spezifizierten Anzeigeverhaltens (Gewitterstufen existieren seit ADR-0025).
  Es wird keine neue Grundsatzentscheidung getroffen, nur die fehlerhafte
  Typkonvertierung an zwei Stellen korrigiert.

## Changelog

- 2026-07-29: Initial spec created (Scheibe S1 von Epic #1419, Issue #1418
  Fehler 1)
