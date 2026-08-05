# Mini-Spec: DWD-Provider nodata-Leerpixel (#1354)

## Was ändert sich
- `_read_point_value()` in `src/providers/dwd.py` prüft den gelesenen Pixelwert gegen `dataset.nodata` (Fallback auf `THUNDER_FILL_VALUE = 9999.0`, falls `dataset.nodata` nicht gesetzt ist) und gibt `None` zurück, statt den Sentinel als Messwert durchzureichen.
- Dadurch profitieren automatisch alle Aufrufer: `_fetch_series()` (Basiswerte `t_2m`/`u_10m`/`v_10m`/`tot_prec`) UND `_thunder_point()` (Gewittersignale).
- Der jetzt redundante Vergleich `wert >= THUNDER_FILL_VALUE` in `_thunder_point()` (Zeile 362) wird entfernt, da die Prüfung bereits in `_read_point_value()` erfolgt.

## Was darf sich nicht ändern
- Rückgabetyp/-verhalten von `_read_point_value()` bei echten Werten (float) und bei GRIB-Parsing-Fehlern (`None`) bleibt gleich.
- `fetch_thunder_signals_named`/`fetch_thunder_signals` bleiben fail-soft (AC-2/AC-3 aus #1457 S2b): ein nodata-Pixel führt weiterhin zu `None`, nicht zu einer Exception.
- Bestehende Tests für Gewittersignale (`tests/tdd/test_issue_1457*` bzw. Nachfolge-Suite) dürfen nicht rot werden.

## Acceptance Criteria

- **AC-1:** Given ein ICON-D2-Rasterpunkt außerhalb des Modellgebiets (nodata-Sentinel, gemessen `dataset.nodata == 9999.0`), When `_read_point_value()` diesen Punkt liest, Then liefert die Funktion `None` statt des Sentinel-Werts `9999.0`.
- **AC-2:** Given ein ICON-D2-Rasterpunkt innerhalb des Modellgebiets mit echtem Messwert, When `_read_point_value()` diesen Punkt liest, Then bleibt der echte Wert unverändert erhalten (keine Regression durch die nodata-Prüfung).

## Manuelle Test-Schritte
1. Unit-Test mit einem GRIB2-Fixture, dessen abgefragter Punkt auf einen nodata-Pixel (9999.0) fällt, gegen `_fetch_series`/`fetch_forecast` laufen lassen → erwarteter Wert `None`, nicht `9999.0`.
2. Bestehenden Gewittersignal-Test laufen lassen → weiterhin `None` bei nodata, keine Regression.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Test: `_read_point_value` liefert `None`, wenn der Pixelwert dem nodata-Sentinel entspricht (Basiswert-Pfad, nicht nur Thunder-Pfad)
