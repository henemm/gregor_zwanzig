# ADR-0010: Vorboten-Metriken sind keine Alert-Auslöser

- **Status:** Akzeptiert
- **Datum:** 2026-06-26
- **Bezug:** GitHub-Issue #889, Spec `docs/specs/_archive/modules/issue_889_feuchte_alerts.md`

## Kontext

Sechs Anzeige-Metriken (Luftfeuchtigkeit, Taupunkt, Regenwahrscheinlichkeit, Bewölkung,
Luftdruck, gefühlte Temperatur) lösten unbeabsichtigt Abweichungs-Alerts aus, weil jede
Anzeige-Metrik mit einem `default_change_threshold` automatisch in den Alert-Mechanismus
`from_display_config` eingespeist wird.

Diese Metriken sind konzeptionell **Vorboten**: Sie zeigen sich dann verändert, wenn die
eigentlich entscheidungsrelevanten Größen (Gewitter, Wind, Niederschlag, CAPE, Sicht) sich
ändern — die aber bereits durch eigenständige Alert-Metriken abgedeckt werden. Eine
Feuchte- oder Taupunkt-Änderung allein führt zu keiner anderen Wanderentscheidung; sie
ist immer Signal für etwas, das ein direkterer Alert schon meldet.

Präzedenz: ADR-0005 (Confidence) — gleiche Trennung „Anzeige ja / Alert-Auslöser nein".

## Entscheidung

Die sechs Vorboten-Metriken werden **komplett aus dem Alert-Mechanismus entfernt**.
Ihre Anzeige im Briefing (Spalten, Berechnungen, gespeicherte Werte) bleibt vollständig
erhalten. Konkret:

- `humidity`, `dewpoint`, `rain_probability`, `cloud_total`, `pressure`, `wind_chill` erhalten
  `default_change_threshold = None` in `MetricDefinition` → schließt den `from_display_config`-Pfad.
- Die `HUMIDITY`-Preset-Zeile wird aus `alert_preset.py` entfernt → schließt den
  `from_alert_rules`/Preset-Pfad.
- `AlertMetric.HUMIDITY` wird aus den Field-Mappings in `weather_change_detection.py` entfernt
  → schließt den Detection-Pfad vollständig.
- `AlertMetric.HUMIDITY`-Enum-Wert bleibt erhalten (Backward-Compat: alte persistierte
  AlertRules laden fehlerfrei, erzeugen aber keinen Alert mehr).

Die elf behaltenen Alert-Metriken (Temperatur, Wind, Böen, Niederschlagsmenge, Gewitter,
CAPE, Schneefallgrenze, Neuschnee, Schneehöhe, Sicht, UV) bleiben unverändert.

## Verworfene Alternativen

- **Nur Feuchte entfernen, Rest belassen** — verworfen: das Problem ist generisch (jede
  Anzeige-Metrik mit Threshold kann zum Alert-Auslöser werden). Halbherzige Lösung würde
  Taupunkt, Bewölkung usw. weiterhin Alerts erzeugen lassen.
- **Alert-Schwelle hochsetzen statt auf None** — verworfen: kaschiert das Problem; bei
  extremen Wetterlagen würden trotzdem Alerts ausgelöst, die keine eigenständige
  Entscheidungsrelevanz haben.
- **Neues `alertable`-Flag in MetricDefinition** — verworfen: Überengineering für den
  aktuellen Scope. `default_change_threshold = None` erzeugt bereits das gewünschte
  Verhalten und ist lesbar.

## Konsequenzen

- **Positiv:** Alert-Kanal wird auf eigenständig entscheidungsrelevante Metriken beschränkt;
  kein Rauschen durch abgeleitete Vorboten-Signale. Direkte Parallele zu ADR-0005 stärkt
  das konzeptionelle Modell.
- **Negativ / Preis:** `AlertMetric.HUMIDITY`-Enum-Wert bleibt als toter Eintrag im Code
  (nötig für Backward-Compat). Alte Trips mit `humidity`-AlertRule laden still und zeigen
  keine Fehlermeldung — das Schweigen könnte bei zukünftiger Pflege verwirren.
- **Folgepflichten:** Neue Anzeige-Metriken dürfen nur dann einen `default_change_threshold`
  erhalten, wenn die Metrik **eigenständig entscheidungsrelevant** für Wanderentscheidungen
  ist — nicht wenn sie Vorbote einer bereits abgedeckten Größe ist. Bei Berührung von
  `metric_catalog.py` oder `alert_preset.py` ist diese Regel zu prüfen.
