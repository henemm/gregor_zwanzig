# Context: fix-1003-regen-badge-schwelle

## Request Summary
Issue #1003 (Duplikat #1126 geschlossen): Das Metriken-Überblick-Badge im Trip-Briefing zeigt
„kein Regen", obwohl die Stundentabelle derselben Etappe eine Regensumme > 0 (z. B. 0.2 mm)
ausweist. Ursache klären und beheben.

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:1173-1188` | `_pill_for_metric()`, Zweig `precipitation` — erzeugt den Badge-Text. Fallback `return ("kein Regen", tone)` greift, wenn **keine einzelne Stunde** die SMS-Erwähnungsschwelle erreicht — die Tagessumme (`total`) wird dabei berechnet, aber im Fallback-Fall verworfen. |
| `src/output/renderers/email/helpers.py:967-987` | `_sms_mention_threshold()` — liefert die Schwelle je Metrik-ID aus `builder.DEFAULTS` (SMS-identisch, Issue #795/RC0). Für `precipitation` → Symbol `"R"`. |
| `src/output/tokens/builder.py:59` | `DEFAULTS = {"R": 0.2, ...}` — die Erwähnungsschwelle für Regen ist 0.2 mm **pro Stunde**. |
| `src/output/renderers/email/helpers.py:990-1004` | `_first_and_peak()` — findet erste Stunde mit `v >= threshold`; gibt `None` zurück, wenn keine Einzelstunde die Schwelle erreicht (unabhängig von der Summe über alle Stunden). |
| `src/output/renderers/email/helpers.py:1256-1338` | `_pill_...()`-Sammelfunktion — ruft `_pill_for_metric()` je Metrik in Katalog-Reihenfolge auf, baut die Badge-Zeile des Briefings (Issue #664/#790). |
| `src/output/renderers/email/html.py:560-600` | `_render_html_table()` — Stundentabelle, zeigt `precip_mm` je Zelle direkt (keine Schwellenlogik, reiner Wert), unabhängig von der Badge-Logik. Bestätigt: die beiden Codepfade sind vollständig disjunkt (wie in #1003 bereits vermutet). |

## Root Cause (bestätigt)
Die Badge-Logik prüft, ob **irgendeine einzelne Stunde** ≥ 0.2 mm Regen hat (`_first_and_peak`).
Ist Regen dünn über mehrere Stunden verteilt (z. B. 0.1 mm + 0.1 mm = Tagessumme 0.2 mm, aber
keine Einzelstunde erreicht 0.2 mm), gibt die Funktion `None` zurück und der Code fällt auf den
Fallback `"kein Regen"` zurück — **ohne die bereits berechnete Tagessumme (`total`) zu prüfen**.
Die Stundentabelle zeigt dagegen den rohen Zellwert (bzw. bei #1126 vermutlich eine Stunde exakt
an der Rundungsgrenze). Beide Fälle sind eine Instanz desselben strukturellen Bugs: Erwähnungs-
schwelle (Einzelstunde) und Anzeige-Kriterium „gibt es überhaupt Regen" (Summe) werden vermischt.

## Existing Patterns
- Andere Ereignis-Metriken (`wind`, `gust`, `rain_probability`) folgen demselben Muster: bei
  `fp is None` (keine Einzelstunde über Schwelle) wird die **max-Form ohne Ereignis-Framing**
  zurückgegeben (z. B. `"Wind max X km/h (HH:00)"`), NICHT ein pauschales „kein Wind". Nur
  `precipitation` hat einen textuellen Nullaussage-Fallback (`"kein Regen"`), der die Summe
  ignoriert — Inkonsistenz zum Rest der Funktion.
- `_sms_mention_threshold()` ist laut Docstring die „EINE Quelle" für SMS-identische Schwellen
  (Issue #795/RC0) — Änderungen an der Schwelle selbst würden auch die SMS-Kurzform beeinflussen
  und sind hier NICHT das Ziel; das Ziel ist die Fallback-Logik im `precipitation`-Zweig.

## Dependencies
- Upstream: `all_dps` (Zeitreihen-Datenpunkte pro Segment), `builder.DEFAULTS["R"]`.
- Downstream: E-Mail-HTML-Renderer (Badge-Zeile), `briefing_mail_validator.py` (Plausibilitäts-Regel
  „kein Regen widerspricht Tabellen-Summe" — der Validator, der den Bug in #1003/#1126 aufgedeckt hat).
- **Nicht betroffen (verifiziert):** Plain-Text-Renderer (`plain.py`) und SMS-Renderer (`sms_trip.py`)
  rufen `_pill_for_metric()` nicht auf — eigene, unabhängige Codepfade.

## Existing Specs
- Kein dediziertes Modul-Spec für die Badge-Logik; Verhalten bisher nur in Issue-Historie
  (#664, #790, #795/RC0) dokumentiert.

## Analysis (Analysis-Challenger-Agent, bestätigt)

### Type
Bug (2x unabhängig auf Staging via `briefing_mail_validator.py` gegen echt zugestellte Mails aufgedeckt).

### Root Cause — bestätigt, mit Präzisierung
`_pill_for_metric()` (`helpers.py:1173-1188`) berechnet `total = sum(...)` (Zeile 1179), verwirft
sie aber im Fallback-Zweig (Zeile 1188 `return ("kein Regen", tone)`), wenn keine Einzelstunde die
0.2mm-Erwähnungsschwelle erreicht (`_first_and_peak`, Zeile 990-1004, Vergleich `v >= threshold`).
Zwei Unterfälle, gleicher struktureller Fehler:
1. Regen dünn über mehrere Stunden verteilt (z. B. 0.1+0.1mm), keine Einzelstunde erreicht 0.2mm.
2. Floating-Point-Randfall: `precip_1h_mm` z. B. `0.19999999999999998` (Open-Meteo liefert
   ungerundete Rohwerte, `geosphere.py` rundet explizit — Quelle-abhängig), `.1f`-Anzeige rundet auf
   "0.2", aber `>= 0.2`-Vergleich schlägt knapp fehl.
Tabellen-Pfad (`html.py`, Zellwert `r.get("precip")`) und Validator (`_column_num_sum`) summieren
dieselben Rohdaten ohne Schwellenlogik — bestätigt disjunkt von der Badge-Erwähnungsschwelle.

### Weitere Vorkommen von „kein Regen"
Nur `radar_service.py:164` — anderer Kontext (2h-Nowcast-Alert), andere Datenquelle, nicht betroffen.

### Technical Approach (empfohlen)
Fallback-Zweig in `_pill_for_metric()` (`precipitation`) ändern: bei `round(total, 1) > 0` einen
Klartext-Hinweis mit der (gerundeten) Summe zeigen statt „kein Regen" — **nicht** `total > 0` als
Bedingung, sonst entsteht der gleiche Widerspruch umgekehrt (z. B. 0.05mm-Restwert würde als
Regen-Ereignis mit „0.0 mm" angezeigt, obwohl Tabelle/Text „0.0" runden). Formatierung konsistent
zum bestehenden `total_str = f"{total:.1f}".rstrip("0").rstrip(".")`-Muster (Zeile 1186) halten.
Erwähnungsschwelle (`_sms_mention_threshold`) selbst NICHT ändern (SMS-Format hängt daran, #795/RC0).

### Scope Assessment
- Files: 1 (`src/output/renderers/email/helpers.py`) + 1 Testdatei (neu oder Erweiterung von
  `tests/tdd/test_issue_795_briefing_quality.py` bzw. neue `test_issue_1003_*.py`)
- Estimated LoC: ~+8/-2
- Risk Level: LOW (isolierter Fallback-Zweig, keine Schema-/API-Änderung)

### Risks & Considerations
- **Renderer-Commit-Gate (#811):** `helpers.py` liegt im Gate-Scope — vor Commit müssen
  `test_issue_811_mode_matrix.py` grün UND ein frischer `briefing_mail_validator.py`-Lauf vorliegen.
- Rundungs-Konsistenz mit Tabelle (`.1f`) ist die zentrale Korrektheitsbedingung — RED-Test MUSS den
  Randfall (Summe > 0 aber < 0.2, rundet auf „0.0") separat abdecken.
- Test-Fixture-Muster für Regen-Testdaten bereits vorhanden in
  `tests/tdd/test_issue_795_briefing_quality.py` (Zeile ~69-116) — wiederverwendbar für RED-Tests.

### Open Questions
- [ ] Exakter Anzeigetext für den neuen Fall (Summe > 0, keine Einzelstunde über Schwelle) — wird
  in der Spec-Phase als Acceptance Criterion mit dem PO festgelegt (z. B. „Regen 0.2 mm (Spur)"
  vs. „Regen ges. 0.2 mm").
