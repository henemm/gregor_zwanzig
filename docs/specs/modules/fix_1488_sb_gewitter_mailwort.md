---
entity_id: fix_1488_sb_gewitter_mailwort
type: bugfix
created: 2026-08-16
updated: 2026-08-16
status: draft
version: "1.0"
tags: [gewitter, mail-renderer, trip-briefing, backend]
---

# #1488 Scheibe B — Gewitterwort in der Mail-Textfassung (schließt #1488)

## Approval

- [ ] Approved

## Purpose

Die Trip-Briefing-Mail-Textfassung zeigt für Gewitter-Stufen englisch `⚡MED`/`⚡HIGH`
statt der kanonischen deutschen Wörter `⚡mittel`/`⚡hoch`. Kanonische Quelle ist bereits
`THUNDER_LABEL_DE` (`src/output/metric_format.py:246-251`); die Wortquelle für den
betroffenen Fallback-Zweig kopiert die Wörter jedoch noch selbst, teils veraltet
englisch. Scheibe B zieht diesen Zweig auf die kanonische Quelle und schließt damit
#1488 endgültig ab (Scheibe A, `d519f4c5`/PR #1902, entfernte bereits die wirkungslose
Gewitter-Alarm-Absolutregel im Editor — ein separater Bedienflächen-Bug).

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `_THUNDER_MAP` (Modul-Konstante) / `format_trend_tokens()`

> Schicht: **Python-Core / Backend-Renderer** (`src/output/renderers/...`, FastAPI-Core,
> Trip-Briefing-Mailversand). Kein Go- und kein Frontend-Code betroffen.

## Estimated Scope

- **LoC:** ~130 (touched) — Kernänderung ~30 Zeilen, Kommentarkorrekturen ~6 Zeilen,
  neuer Testfall ~90 Zeilen
- **Files:** 7 (2 Kernänderung, 4 reine Kommentarkorrektur, 1 neue Testdatei)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `THUNDER_LABEL_DE` (`src/output/metric_format.py:246-251`) | Konstante | kanonische deutsche Stufenwörter — neue Ableitungsquelle für `_THUNDER_MAP["plain"]`/`["word"]` |
| `resolve_thunder_day_branch()` (`src/output/renderers/email/thunder_branch.py:54-79`) | Funktion | wählt den `"plain"`-Zweig, der von diesem Fix betroffen ist — bleibt unverändert, ist nur Konsument der korrigierten Werte |
| `format_trend_tokens()` (`helpers.py:905-…`) | Funktion | einzige Erzeugungsstelle des betroffenen Dict; von allen drei Renderern aufgerufen |
| `outlook.py:382,386` / `compact.py:104,106` / `narrow.py:603,605` | Renderer | lesen `tok["thunder_plain"]` im `"plain"`-Zweig — keine eigene Änderung nötig, Fix wirkt automatisch durch |
| `tests/tdd/test_thunder_low_output_channels.py::test_ac11_trend_block_zeigt_leicht` (#1474 AC-11) | Bestandstest | harter Konsument von `tokens["thunder_word"]` — Feld bleibt bestehen und wird ebenfalls korrigiert, nicht gelöscht (Abweichung von der Ausgangsanalyse, s. „Known Limitations") |

## Implementation Details

**1. `_THUNDER_MAP` in `helpers.py:872-902`:** `"plain"` und `"word"` für alle vier
Stufen aus `THUNDER_LABEL_DE` ableiten statt hartkodierter Strings, damit künftige
Stufenänderungen an einer Stelle greifen (dasselbe Muster wie `narrow.py:278-280`):

```python
from output.metric_format import THUNDER_LABEL_DE, ThunderLevel

_THUNDER_MAP = {
    "NONE": {"word": THUNDER_LABEL_DE[ThunderLevel.NONE], "plain": "⚡–"},
    "LOW":  {"word": THUNDER_LABEL_DE[ThunderLevel.LOW],
             "plain": f"⚡{THUNDER_LABEL_DE[ThunderLevel.LOW]}"},
    "MED":  {"word": THUNDER_LABEL_DE[ThunderLevel.MED],
             "plain": f"⚡{THUNDER_LABEL_DE[ThunderLevel.MED]}"},
    "HIGH": {"word": THUNDER_LABEL_DE[ThunderLevel.HIGH],
             "plain": f"⚡{THUNDER_LABEL_DE[ThunderLevel.HIGH]}"},
}
```

`"plain": "⚡–"` bei `NONE` bleibt Sonderfall (kein Wort, Gedankenstrich) — unverändert,
kein Bug dort.

**2. Tote Felder entfernen:** Die Keys `"sms"`, `"sq_color"`, `"word_color"` fallen aus
allen vier `_THUNDER_MAP`-Einträgen weg. In `format_trend_tokens()` (Rückgabe-Dict,
`helpers.py:1074-1078`) entfallen entsprechend `"thunder_sms"`, `"thunder_sq_color"`,
`"thunder_word_color"`. `"thunder_word"` **bleibt erhalten** (s. Known Limitations).

**3. Docstring korrigieren** (`helpers.py:931-935`): Zeilen zu `thunder_sq_color`,
`thunder_word_color`, `thunder_sms` streichen; `thunder_word`/`thunder_plain`-Beispiele
auf die deutschen Wörter (`'kein' / 'leicht' / 'mittel' / 'hoch'` bzw.
`'⚡–' / '⚡leicht' / '⚡mittel' / '⚡hoch'`) korrigieren.

**4. Kommentarkorrektur (reine Textänderung, keine Verhaltensänderung)** — veraltete
Dreier-Skala `NONE=0/MED=1/HIGH=2` auf die seit #1474 gültige Vierer-Skala
`NONE=0/LOW=1/MED=2/HIGH=3` korrigieren:
- `src/services/weather_change_detection.py:814-816`
- `src/services/alert_preset.py:75-77`
- `tests/tdd/test_alert_sensitivity_levels.py:6`
- `tests/tdd/test_day_comparison_service.py:8`
- `tests/integration/test_friendly_format_email_and_alerts.py:717` (Zeile verifiziert, kein Drift)

## Expected Behavior

- **Input:** Etappe ohne stündliche Gewitterdaten (`stage["hourly_thunder"]` leer)
  mit `thunder="MED"` bzw. `"HIGH"`, gerendert in Outlook-Klartext, Kompaktformat-Mail
  oder Telegram/SMS-Trendblock.
- **Output:** `⚡mittel` bzw. `⚡hoch` statt bisher `⚡MED`/`⚡HIGH`. Der `"day"`-Zweig
  (Etappe MIT stündlicher Gewitterreihe und gesetztem Tagesfenster-Token) ist von der
  Änderung nicht betroffen — er liest weiterhin aus dem Token, nicht aus `_THUNDER_MAP`.
- **Side effects:** keine. Kein Ortsvergleich-Konsument (`format_trend_tokens()` wird
  von Compare-Renderern nicht aufgerufen — per Grep verifiziert, Compare bleibt
  unberührt).

## Acceptance Criteria

- **AC-1:** Given eine Etappe ohne stündliche Gewitterdaten (`hourly_thunder` leer)
  mit Stufe `MED` bzw. `HIGH`, When die Mail-Textfassung über die drei produktiven
  Renderer-Funktionen (`render_outlook_plain`/`_compact_thunder_field`/den
  Telegram-Trendblock) gerendert wird, Then zeigt die Ausgabe `⚡mittel` bzw. `⚡hoch`
  statt `⚡MED`/`⚡HIGH`.
  - Test: neuer Testfall in `tests/tdd/test_trend_plain_branch_shows_german_thunder_words.py`,
    ruft alle drei produktiven Renderer-Funktionen direkt mit einer Stage ohne
    `hourly_thunder` auf (kein Dateiinhalt-Check, echte Renderfunktionen).

- **AC-2 (Positivkontrolle):** Given eine Etappe MIT stündlicher Gewitterreihe, die im
  Tagesfenster eine Stufe trägt (`resolve_thunder_day_branch()` liefert `"day"`), When
  dieselben drei Renderer aufgerufen werden, Then bleibt das gerenderte Wort unverändert
  aus dem Tages-Token abgeleitet (`_thunder_token_parts()`) — der `"day"`-Zweig liest
  weiterhin nicht aus `_THUNDER_MAP`.
  - Test: derselbe neue Testfall, Gegenprobe im selben Testlauf mit gesetztem
    `hourly_thunder` und passendem Tagesfenster-Token.

- **AC-3 (Erreichbarkeit belegt, kein toter Zweig):** Given `stage.get("hourly_thunder")`
  ist leer und `thunder="HIGH"`, When `resolve_thunder_day_branch()` direkt ausgewertet
  wird, Then liefert sie `"plain"` — der reproduzierbare Beleg, dass dieser Zweig für
  Etappen ohne stündliche Gewitterdaten tatsächlich greift.
  - Test: Teil desselben neuen Testfalls, direkter Aufruf von
    `resolve_thunder_day_branch()` ohne Umweg über die Renderer.

- **AC-4 (Bestandsschutz #1474 AC-11):** Given der bestehende Test
  `test_thunder_low_output_channels.py::test_ac11_trend_block_zeigt_leicht`, When
  Scheibe B umgesetzt ist, Then liefert `format_trend_tokens(...)["thunder_word"]` bei
  `ThunderLevel.LOW` weiterhin exakt `"leicht"` — das Feld wird korrigiert (aus
  `THUNDER_LABEL_DE` abgeleitet), nicht gelöscht, und der Bestandstest bleibt
  unverändert grün.
  - Test: bestehender Test `tests/tdd/test_thunder_low_output_channels.py`, unverändert
    lauffähig, CI-Lauf als Beleg.

- **AC-5 (tote Felder restlos entfernt):** Given `_THUNDER_MAP` nach dem Fix, When
  `format_trend_tokens()` für eine beliebige Stufe aufgerufen wird, Then enthält das
  zurückgegebene Dict keine Schlüssel `thunder_sms`, `thunder_sq_color`,
  `thunder_word_color` mehr.
  - Test: neuer Testfall (gleiche Datei wie AC-1), prüft
    `{"thunder_sms", "thunder_sq_color", "thunder_word_color"} & tokens.keys() == set()`
    plus vollständiger Lauf der bestehenden Trend-Testsuite (kein KeyError, keine
    Regression).

## Known Limitations

- **Abweichung von der Ausgangsanalyse:** Das Analyse-Dokument
  (`docs/context/fix-1488-sb-gewitter-mailwort.md`) stufte `thunder_word` als toten
  Nebeneffekt ein („kein Konsument außerhalb `helpers.py`", per Grep über `src/`/`api/`).
  Gegenprüfung ergab einen Konsumenten außerhalb dieses Bereichs: der Bestandstest
  `tests/tdd/test_thunder_low_output_channels.py:73-85` liest
  `format_trend_tokens(...)["thunder_word"]` direkt als AC-11-Nachweis für #1474
  („E-Mail Trend-Block" ist einer von sechs geprüften Render-Einstiegspunkten für die
  Stufe „leicht"). Lösung: `thunder_word` **bleibt erhalten** und wird — konsistent mit
  `thunder_plain` — aus `THUNDER_LABEL_DE` abgeleitet, statt gelöscht zu werden. Damit
  bleibt der #1474-Test unverändert grün, und die (vorher unreachable, aber latent
  falsche) `MED`/`HIGH`-Werte in `thunder_word` werden als Nebeneffekt korrekt.
  `thunder_sms`, `thunder_sq_color`, `thunder_word_color` sind dagegen per Grep über
  `src/` UND `tests/` bestätigt konsumentenlos und werden wie geplant entfernt.
- Für eine Etappe mit stündlicher Gewitterreihe, aber leerem Tagesfenster
  (`resolve_thunder_day_branch()` → `"none"`), bleibt `_THUNDER_MAP["NONE"]["plain"]`
  (`"⚡–"`) unverändert — kein Wort, kein MED/HIGH-Bug, nicht Teil dieser Scheibe.
- Ortsvergleich (Compare) ist von dieser Änderung nicht betroffen — `format_trend_tokens()`
  wird von keinem Compare-Renderer aufgerufen (per Grep verifiziert). Keine Teilungsfrage
  Trip/Compare hier, da kein Compare-Pendant existiert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** Reine Bugfix-Konsolidierung auf eine bereits bestehende kanonische
  Quelle (`THUNDER_LABEL_DE`). Kein neues Architekturprinzip, kein neuer
  Entscheidungsraum.

## Changelog

- 2026-08-16: Initial spec created (spec-writer, Workflow `fix-1488-sb-gewitter-mailwort`)
