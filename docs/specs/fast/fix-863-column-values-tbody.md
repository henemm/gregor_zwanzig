# Mini-Spec: fix-863 — _column_values liest nur tbody-Zeilen

## Was ändert sich

- `_column_values()` sucht `<tr>`-Elemente nur noch innerhalb von `<tbody>`-Tags
- `_column_hours_sum()` ebenso (nutzt `_column_values` → erbt den Fix)
- Neue Regex `_TBODY_RE` extrahiert `<tbody>`-Inhalte vor dem Row-Scan

## Was darf sich nicht ändern

- Stunden-Tabelle (`class="resp"`, mit `<tbody>`) wird weiterhin vollständig gelesen
- Trend-Tabelle (kein `<tbody>`) und Stats-Tabelle (kein `<tbody>`) bleiben unsichtbar
- Alle anderen Validator-Checks (AC-1 bis AC-10) bleiben unverändert
- Exit-Code-Semantik (0/1/2) bleibt gleich

## Ursache

`_ROW_RE` trifft auf alle `<tr>` im gesamten HTML-Body. Die 3-Tage-Trend-Tabelle
enthält Tages-Aggregat-Werte (z. B. 200 km/h Windmax, 300 mm Regen) die bei
identischer Spalten-Index-Position als Stunden-Datenpunkt fehlgedeutet werden.
Die Stunden-Tabellen haben `<tbody>`, die Trend-Tabelle nicht.

## Manuelle Test-Schritte

1. Test-Briefing auf Staging triggern
2. `uv run python3 .claude/hooks/briefing_mail_validator.py` ausführen → Exit 0
3. Kein "Ebenen-Widerspruch"-Fehler für Wind oder Regen

## Inline-Test

- [ ] `_column_values()` gibt bei einer HTML mit Trend-Tabelle (kein tbody) +
  Stunden-Tabelle (mit tbody) nur die Stunden-Werte zurück
