# ADR-0014: Nullgradgrenze — `snow_line` und `freezing_level` konsolidiert zu einer Alert-Metrik

- **Status:** Akzeptiert
- **Datum:** 2026-07-02
- **Bezug:** GitHub-Issue #959 (Bündel), #946 (Ursprung), #961 (Übergangslösung), `docs/specs/modules/fix_alert_bundle_958ff.md`

## Kontext

Seit #946 existierten zwei Alert-Metriken für dieselbe physikalische Größe:
`snow_line` (UI-Label „Schneefallgrenze") beobachtete das Summary-Feld
`freezing_level_m`, während das per #946 eingeführte `freezing_level`
(„Nullgradgrenze") im Change-Detector nie verdrahtet war — Regeln dafür wurden
stillschweigend verworfen (tote Einstellung). Zusätzlich führten beide
unterschiedliche Preset-Schwellen. „Schneefallgrenze" (`snowfall_limit_m`) ist
fachlich eine **andere** Wettergröße mit eigenem Katalog-Eintrag und bleibt als
Briefing-Metrik unberührt.

## Entscheidung

1. Es gibt genau **eine** Alert-Metrik für diese Größe: `freezing_level`
   („Nullgradgrenze"), voll verdrahtet in `weather_change_detection.py`
   (Summary-Feld `freezing_level_m`).
2. `AlertMetric.SNOW_LINE` bleibt als toter Enum-Wert für
   Backward-Compat-Deserialisierung erhalten (Muster: `HUMIDITY`, ADR-0010).
3. Bestandsdaten: `metric_alert_levels.snow_line` wird beim Trip-Laden per
   Read-Modify-Write auf `freezing_level` migriert (kein Datenverlust, bei
   Konflikt gewinnt ein vorhandener `freezing_level`-Eintrag);
   `expand_per_metric_levels()` normalisiert Legacy-Keys zusätzlich als
   Sicherheitsnetz für nicht migrierte In-Memory-Zustände.
4. Preset-Schwellen der konsolidierten Metrik: **600/400/200 m**
   (die bisher tatsächlich wirksamen `snow_line`-Werte; PO-freigegeben).
5. Frontend bietet nur noch „Nullgradgrenze" an; `snow_line` wird über die
   Legacy-Map weiterhin aufgelöst.

## Verworfene Alternativen

- **Option (b): beide Metriken getrennt voll verdrahten** (`snow_line` auf das
  echte `snowfall_limit_m` umziehen) — verworfen: verdoppelt Konfiguration und
  Erklärungsbedarf für nahezu identische Winter-Information; `snowfall_limit`
  bleibt als Briefing-Metrik verfügbar. Eine spätere eigenständige
  Schneefallgrenze-Alert-Metrik bräuchte eine neue Spezifikation.
- **Nur Label vereinheitlichen, Doppel-Enum behalten** — verworfen: lässt die
  tote `freezing_level`-Einstellung bzw. die Zwei-Namen-Verwirrung bestehen.

## Konsequenzen

- **Positiv:** Keine tote Konfigurationsoption mehr; ein Name in UI, Mail und
  Backend; eine Preset-Zeile.
- **Negativ / Preis:** Migrationscode im Loader + Normalisierung im
  Preset-Expander müssen erhalten bleiben, solange Alt-Daten existieren.
- **Folgepflichten:** Keine zweite Nullgradgrenze-/Schneefallgrenze-Alert-Metrik
  einführen; neue Winter-Alert-Metriken müssen gegen diesen ADR geprüft werden.
