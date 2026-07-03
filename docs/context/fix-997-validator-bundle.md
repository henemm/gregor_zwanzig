# Context: fix-997-validator-bundle

Bündel #997 + #921 (Rest) + #993. Standard Track (Intake 1/1/0 = 2).
Vorgänger-Bündel fix-alert-bundle-958ff (b65f22a0, live) hat alle drei Befunde
erzeugt bzw. dokumentiert; Diagnose-Beweise von 2026-07-03 liegen in den Issues.

## Request Summary

Den False-Positive im Briefing-Mail-Validator beheben (#997, blockiert das
Renderer-Commit-Gate #811 strukturell), danach den dadurch zurückgestellten
#921-Rest (toter `report_type='alert'`-Zweig) einspielen und den
`allOff`-Einzeiler (#993) mitnehmen.

## Related Files

| File | Relevanz |
|------|----------|
| `.claude/hooks/briefing_mail_validator.py:158-179` | `_column_values()` — mappt Header-Index der 14-spaltigen Stundentabelle auf ALLE tbody-Zeilen; Trend-Zeile (9 Zellen) liefert Fremdwerte (#997-Kern) |
| `.claude/hooks/briefing_mail_validator.py:239-262` | `_check_overview_consistency` — „kein Regen"-Regel (Z.256-261) und Sonnen-Regel nutzen `_column_num_sum`/`_column_values` |
| `tests/tdd/test_issue_733_briefing_mail_validator.py` | Bestehende Validator-Tests (synthetische MIME-Mails, direkte Funktionsaufrufe) — Stil-Vorbild für Regressionstest |
| `src/formatters/trip_report.py:616-622` | #921-Rest: toter `'alert'→'update'`-Sonderfall; fertiger Patch im #921-Kommentar (2026-07-03) und `scratchpad/921_trip_report.patch` |
| `frontend/src/lib/components/alerts-tab/AlertsTab.svelte:50,106` | #993: `allOff = displayMetrics.every(...)` vacuously true bei leerem Array → `.subdued` fälschlich auf Cooldown/QuietHours |

## Diagnose-Beweise (2026-07-03, Live-Staging)

- `_column_values(html,'Rain')` → `[0.0×16, 35.0]`; Streu-Zeile:
  `['So','31°','37°','0.0','0%','16','35','–','']` (9 Zellen) — Index 6 der
  Stunden-Header trifft die **Böen**-Zelle der Trend-Zeile.
- #863-Guard-Annahme („Trend-/Stats-Tabellen ohne tbody") ist seit dem
  Mail-Redesign (#898-901-Ära) falsch: Trend-Tabelle hat eigenes tbody.
- 3× reproduziert mit verschiedenen Trips/Wetterlagen (0.1/38/35 „mm" bei
  realem Regen 0,0 — Assuan-Beweis).

## Fix-Ansatz (#997)

`_column_values()`: Zeilen überspringen, deren `<td>`-Zellenzahl nicht zur
Header-Spaltenzahl (`len(headers)`) passt — betrifft identisch auch
`_column_hours_sum` (Sonnen-Regel, Z.182ff) falls dieselbe Row-Quelle. Kein
Aufweichen: Die Regel bleibt aktiv, sie liest nur die richtigen Zeilen.
Regressionstest: synthetische full-Mail mit 14-Spalten-Stundentabelle
(Regen 0,0), separater Trend-tbody-Tabelle (9 Zellen, Zahl an Index 6) und
„kein Regen"-Pill → muss PASS (heute: FAIL = RED-Nachweis).

## Abhängigkeiten / Reihenfolge

1. #997 zuerst (RED→GREEN am Validator).
2. #921-Rest: Patch anwenden; Commit staged dann `src/formatters/trip_report.py`
   → Renderer-Gate verlangt frischen Matrix-Lauf + frischen GRÜNEN
   Validator-Lauf gegen echte Staging-Mail (Trigger: Port 8001,
   validator-issue110, Trip mit aktuellen Etappen-Daten — siehe
   Memory `reference_staging_briefing_trigger_internal_port` und
   `reference_alert_preview_probe_howto`).
3. #993 unabhängig (Frontend-Einzeiler + Playwright-/Unit-Nachweis).

## Risks & Considerations

- **Geteiltes Gate-Werkzeug:** Fix macht die Prüfung korrekter, nicht lascher
  (PO-Mandat „weiter" nach Empfehlung #997-zuerst; Issue dokumentiert).
  Keine Schwellen ändern, keine Regel deaktivieren.
- Gate-Läufe für #921 brauchen frisches Staging-Wetter — Trips im
  validator-issue110-Konto haben fast alle Datum 2026-08-01 (leere Tabellen);
  Trip mit aktuellen Daten nötig (074a5d84 endet 2026-07-03!). Ggf. neuen
  Kurz-Trip seeden (Muster tdd-958-dry, gelöscht — neu anlegbar).
- `doc-compliance`/Gate-Tests zu Hooks existieren (test_issue_833_gate.py) —
  bei Signatur-Änderungen mitprüfen.
- LoC klein (~40-60); kein Override nötig.
