# ADR-0013: Alert-Renderer — `threshold` ist die Δ-Sensitivitätsschwelle, kein Absolut-Referenzwert

- **Status:** Akzeptiert
- **Datum:** 2026-07-02
- **Bezug:** GitHub-Issue #958 (Bündel #958/#980/#981/#982), `docs/specs/modules/fix_alert_bundle_958ff.md`, ADR-0009 (Alerts als Abweichungs-Wächter), ADR-0011 (ein Backend-Renderer)

## Kontext

`AlertEvent.threshold` stammt aus `WeatherChange.threshold` und bedeutet dort laut
Docstring und Katalog (`default_change_threshold`): „löse Alarm aus, wenn sich der
Wert seit dem letzten Briefing um mindestens X ändert" — eine **Δ-Schwelle**. Der
Renderer (`over_thr()`/`side_label()`) verglich aber `value_to` (Absolutwert) mit
dieser Δ-Schwelle. Für Metriken, deren Absolutwerte weit über der Δ-Schwelle liegen
(Nullgradgrenze: Werte 1000–4000 m, Schwelle 200–400 m), war das Ergebnis konstant
falsch („unter" bei steigender Nullgradgrenze, realer Nutzer-Report 2026-07-01).
Bei anderen Metriken sah das Label nur zufällig plausibel aus.

## Entscheidung

1. Im kanonischen Alert-Renderer (`src/output/renderers/alert/`) gilt:
   `AlertEvent.threshold` **ist immer die Δ-Auslöseschwelle**. Ein Event ist
   „über Schwelle" ⇔ `abs(value_to − value_from) ≥ threshold`.
2. Alle abgeleiteten Anzeigen (Verdict-Farbe, Zähler „N über Schwelle",
   Top-3-Auswahl, Dämpfung, Sortierung) bauen auf dieser einen Definition auf.
3. Das Wording macht die Δ-Natur explizit: „Änderung über/unter deiner
   Alarm-Schwelle (400 m)" statt „jetzt über Schwelle 400 m".
4. `AlertEvent.cmp` bleibt für Katalog-Zuordnung/Richtung erhalten, wird aber
   nicht mehr als Vergleichsoperator gegen Absolutwerte verwendet.

## Verworfene Alternativen

- **Absolut-Vergleich beibehalten und pro Metrik einen Absolut-Grenzwert
  einführen** — verworfen: Der Abweichungs-Alert (ADR-0009) hat keinen
  Absolut-Grenzwert; ein zweites Schwellen-Konzept würde Konfiguration und
  Mail-Wording verdoppeln.
- **Richtungswort rein aus `direction(e)` („gestiegen/gefallen") ohne
  Schwellen-Bezug** — verworfen (PO-Entscheidung bei Spec-Freigabe): Der Bezug
  zur konfigurierten Alarm-Schwelle ist die Kerninformation des Alerts.

## Konsequenzen

- **Positiv:** Ein konsistentes, fachlich korrektes „über/unter" über alle
  Kanäle; Zähler/Dämpfung/Sortierung teilen dieselbe Wahrheit.
- **Negativ / Preis:** Bestehende Renderer-Test-Fixtures, die `threshold` als
  Absolutwert konstruierten, mussten auf Δ-realistische Werte umkalibriert
  werden (#958-Bündel, dokumentiert in der Spec).
- **Folgepflichten:** Jede künftige Alert-Metrik und jeder künftige
  Renderer-Aufrufer muss `threshold` als Δ-Schwelle befüllen. **Known
  Limitation:** `_detect_absolute_changes()` (`weather_change_detection.py`,
  `AlertRuleKind.ABSOLUTE`) setzt `old_value=0.0` und ist mit dieser Semantik
  inkompatibel — im Versandpfad seit #816 tot (`include_absolute=False`),
  siehe Folge-Issue aus Adversary-Finding F001. Vor einer Reaktivierung von
  Absolut-Regeln muss dieser Pfad einen eigenen Render-Vertrag bekommen.
