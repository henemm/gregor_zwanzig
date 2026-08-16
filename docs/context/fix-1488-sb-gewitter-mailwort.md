# Context + Analyse: #1488 Scheibe B — Gewitterwort in der Mail-Textfassung

## Request Summary
Die Mail-Textfassung (Trip-Briefing) zeigt für Gewitter-Stufen `MED`/`HIGH` (englisch) statt
`mittel`/`hoch` — kanonisch ist `THUNDER_LABEL_DE` (`kein`/`leicht`/`mittel`/`hoch`,
`src/output/metric_format.py:246-251`). Quelle der englischen Wörter: `_THUNDER_MAP`
(`src/output/renderers/email/helpers.py:872-902`). Schließt #1488 (Scheibe A war
`d519f4c5`/PR #1902, entfernte die wirkungslose Alarm-Absolutregel im Editor).

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/email/helpers.py:872-902` | `_THUNDER_MAP` — die Wortquelle. `plain`-Feld trägt `⚡MED`/`⚡HIGH`, muss `⚡mittel`/`⚡hoch` werden |
| `src/output/renderers/email/helpers.py:918-1085` | `format_trend_tokens()` — baut `tok["thunder_plain"]` aus `_THUNDER_MAP`; Docstring nennt an `:931-935` ebenfalls `'MED'/'HIGH'` (stale) |
| `src/output/renderers/email/outlook.py:382,386` | Konsument 1 — Klartext-Ausblickzeile, Fallback-Zweig `"plain"` |
| `src/output/renderers/email/compact.py:104,106` | Konsument 2 — Kompaktformat-Zeile, gleicher Fallback-Zweig |
| `src/output/renderers/narrow.py:603,605` | Konsument 3 — Telegram/SMS-Trendblock, gleicher Fallback-Zweig |
| `src/output/renderers/email/thunder_branch.py:50-79` | `resolve_thunder_day_branch()` — geteilte Zweigwahl aller drei Aufrufer, s. Analyse unten |
| `src/output/metric_format.py:246-251` | `THUNDER_LABEL_DE` — kanonische deutsche Stufenwörter (bereits Ziel für andere Konsumenten, z. B. `narrow.py:278-280`) |
| `src/services/weather_change_detection.py:814-816` | Kommentar nennt veraltete Ordinalskala `MED=1/HIGH=2` (fehlt `LOW`, seit #1474 vierstufig) |
| `src/services/alert_preset.py:75-77` | Gleicher veralteter Skalen-Kommentar `NONE=0/MED=1/HIGH=2` |
| `tests/tdd/test_alert_sensitivity_levels.py:6-10` | Docstring nennt dieselbe veraltete Dreier-Skala |
| `tests/tdd/test_day_comparison_service.py:8` | dito |
| `tests/integration/test_friendly_format_email_and_alerts.py:717` | dito (zu verifizieren, ob Zeile noch aktuell) |

## Existing Patterns
- **Geteilte Quelle statt Kopien** ist bereits etabliertes Muster hier: `resolve_thunder_day_branch()`
  (#1671) zentralisierte die Zweigwahl für alle drei Renderer; `THUNDER_LABEL_DE`
  (`metric_format.py`) ist bereits die kanonische deutsche Wortquelle für `narrow.py:278-280`
  und den Ampel-/HTML-Pfad. Der naheliegende Fix: `_THUNDER_MAP["plain"]` aus `THUNDER_LABEL_DE`
  ableiten statt eine vierte Kopie zu pflegen — genau das Muster, das Scheibe A bereits einmal
  angewendet hat (Entfernen/Vereinheitlichen statt Umbenennen).
- Renderer-Commit-Gate + `briefing_mail_validator.py` sind Pflicht vor „E2E bestanden"
  (`docs/reference/gates_und_ratschen.md`), weil dies eine Mail-Inhalts-Datei betrifft.

## Analyse: welcher Zweig feuert wirklich?

`resolve_thunder_day_branch()` (`thunder_branch.py:50-79`) hat drei Ausgänge:
- `"day"` — Tagesfenster trägt einen Token → Wort kommt aus dem **Token selbst**
  (`_thunder_token_parts()` zerlegt z. B. `leicht@5(hoch@15)`), **nicht** aus `_THUNDER_MAP`.
  Diese Wörter sind bereits deutsch (`THUNDER_LABEL_DE`-Werte fließen in den Token ein).
- `"none"` — Stundenreihe vorhanden, Tagesfenster leer → `_THUNDER_MAP["NONE"]["plain"]` = `"⚡–"`.
  Enthält kein `MED`/`HIGH`, unkritisch.
- `"plain"` — **keine Stundenreihe** (`stage.get("hourly_thunder")` leer) → Rückfall auf
  `tok["thunder_plain"]`, das volle 24h-Aggregat aus `_THUNDER_MAP[level]["plain"]`.
  **Hier — und nur hier — kann `⚡MED`/`⚡HIGH` in einer zugestellten Mail erscheinen.**

Dieser dritte Zweig ist **kein toter Code**: er greift bei jeder Etappe ohne stündliche
Gewitterdaten (z. B. Fallback-Provider ohne stündliche Auflösung, `docs/reference/decision_matrix.md`).
Erreichbarkeit ist damit gegeben — anders als bei Scheibe A, wo die Absolutregel nie griff.

**Konsequenz für den Zuschnitt:** Der Fix muss an der Quelle (`_THUNDER_MAP["MED"/"HIGH"]["plain"]`)
ansetzen, nicht an den drei Aufrufer-Stellen — die lesen nur `tok["thunder_plain"]` durch.
Eine Änderung in `_THUNDER_MAP` wirkt automatisch in allen drei Renderern.

## Tote Felder (Positivbefund über Grep, kein Konsument außerhalb `helpers.py`)
`thunder_word`, `thunder_sms`, `thunder_sq_color`, `thunder_word_color` (und die zugehörigen
`_THUNDER_MAP`-Keys `"word"`, `"sms"`, `"sq_color"`, `"word_color"`) werden nirgends außerhalb
von `helpers.py` gelesen — bestätigt per `grep -rn` über `src/`, `api/`. Empfehlung: in dieser
Scheibe entfernen statt weiter mitzupflegen (reduziert vier Wortkopien auf eine echte).

## Dependencies
- Upstream: `_THUNDER_MAP` wird nur mit dem `"plain"`-Feld tatsächlich konsumiert (über
  `format_trend_tokens()`); die übrigen Felder sind Sackgassen (s. o.).
- Downstream: drei Trip-Briefing-Renderer (`outlook.py`, `compact.py`, `narrow.py`) — alle über
  denselben `tok["thunder_plain"]`-Zugriff im `"plain"`-Zweig betroffen. Kein Ortsvergleich-Konsument
  (`format_trend_tokens()` wird von Compare-Renderern nicht aufgerufen — geprüft per Grep).

## Existing Specs
- Kein bestehendes Spec-Modul für `_THUNDER_MAP`/Trend-Tokens. Vorlage: `docs/specs/modules/fix_1488_sa_gewitter_absolutregel.md` (Scheibe A) als Formatvorbild, neue Spec-Datei für Scheibe B nötig.

## Risks & Considerations
- **Renderer-Commit-Gate**: Änderung an `helpers.py`/`outlook.py`/`compact.py`/`narrow.py` löst
  Modus-Matrix-Test + `briefing_mail_validator.py` aus — vor „E2E bestanden" Pflicht.
- **Positivkontrolle nötig**: sicherstellen, dass der `"day"`-Zweig (Token-Wörter) unverändert
  bleibt — der Fix darf nur das `plain`-Feld in `_THUNDER_MAP` betreffen, nicht die Token-Zerlegung.
- **Stale-Kommentar-Cleanup ist eine andere Baustelle als die Wortkorrektur**: die Kommentare in
  `weather_change_detection.py`/`alert_preset.py`/Testdateien beziehen sich auf die *Ordinalskala*
  (fehlendes `LOW` seit #1474), nicht auf die MED/HIGH-Wörter selbst — inhaltlich getrennter,
  aber laut Vorgänger-Session (#1488-Memory) bewusst mitgezogener Nebenaufwand. Nur Kommentartext
  ändern, keine Verhaltensänderung.
- **Test-Nachweis**: `THUNDER_LABEL_DE` ist bereits die Zielquelle — Fix sollte `_THUNDER_MAP["plain"]`
  daraus ableiten (`f"⚡{THUNDER_LABEL_DE[level]}"`), damit künftige Stufenänderungen an einer Stelle
  greifen. Reproduktion des Bugs: Stage ohne `hourly_thunder` mit `thunder=MED` erzeugen → aktuell
  `⚡MED`, nach Fix `⚡mittel`.
