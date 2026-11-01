# Mini-Spec: fix-2696-meteoalarm-live-nebel

Refs #2696, #1442. Nur Test-Code, kein Produktivcode.

## Was ändert sich
- Die Zonen-Auswahl der drei MeteoAlarm-Live-Tests nimmt nur noch Warnungen, deren
  `awareness_type` (führende Ganzzahl, z. B. `4` aus `4; Fog`) in
  `services.official_alerts.meteoalarm._TYPE_HAZARD_MAP` steht. Die Typliste wird aus dem
  Produktivcode importiert, nicht kopiert.
- Betroffene Dateien: `tests/tdd/test_meteoalarm_feed_pt_nl_pl_live.py` (`_aktive_zonen`),
  `tests/tdd/test_meteoalarm_feed_es_live.py` (`_aktive_zonen`),
  `tests/tdd/test_meteoalarm_feed_nordics_live.py` (`_aktiv`, wirkt für Polygon- und Geocode-Auswahl).
- Eine Warnung ohne oder mit nicht lesbarem `awareness_type` zählt als nicht auswählbar
  (wie vom Produktivcode verworfen).

## Was darf sich nicht ändern
- Produktivcode (`src/`) bleibt unverändert; Nebel (#1430) bleibt bewusst verworfen.
- Gibt der Feed keine auswählbare Warnung her, bleibt das Ergebnis SKIP mit Grund, nie Bestehen.
- Stufe ≥ 2, Zeitfenster, `AllClear`, `Cancel` und die Prüfpunkte bleiben wie bisher.
- Nicht Teil dieses Fixes: Suche über alle Zonen der Zonendatei (im Ticket als optional genannt).

## Acceptance Criteria
**AC-1:** Given ein Feed, dessen einzige aktive Warnung für eine Prüfzone den Typ `4; Fog` trägt, When die Live-Test-Auswahl läuft, Then wird diese Zone nicht gewählt und der Test endet mit SKIP statt mit einem falschen Rot.
**AC-2:** Given ein Feed mit einer aktiven Warnung eines Typs aus `_TYPE_HAZARD_MAP` (z. B. `1; Wind`) für eine Prüfzone, When die Live-Test-Auswahl läuft, Then wird die Zone gewählt wie bisher.
**AC-3:** Given jeder Warntyp, den der Produktivcode in `_TYPE_HAZARD_MAP` kennt, und jeder in `_DISCARDED_TYPES` (z. B. Nebel, Küstenereignis), When die Live-Test-Auswahl je Typ eine Fixture-Warnung prüft, Then werden genau die Typen aus `_TYPE_HAZARD_MAP` gewählt und alle verworfenen nicht. Ändert sich die Typliste im Produktivcode, folgt die Auswahl automatisch, weil der Test beide Listen daraus liest.

## Manuelle Test-Schritte
1. Die drei Live-Tests lokal mit `-m live` laufen lassen: NL rot wegen Nebel darf nicht mehr auftreten.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Netzfreier Test je Datei (alle drei Auswahl-Funktionen) mit Fixture-Feed: Nebel-Zone wird verworfen, Wind-Zone gewählt (AC-1, AC-2)
- [ ] Netzfreier Test, parametrisiert über alle Schlüssel aus `_TYPE_HAZARD_MAP` und `_DISCARDED_TYPES` (aus dem Produktivcode gelesen): gewählt genau bei `_TYPE_HAZARD_MAP` (AC-3)
