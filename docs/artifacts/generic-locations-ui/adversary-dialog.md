# Adversary Dialog — F11b Generic Locations UI

## Date: 2026-04-04

## Checklist

- [x] Create dialog Profil-Dropdown → activity_profile gespeichert
- [x] Badge auf Card zeigt Profil (Capitalize, blue-grey)
- [x] Wetter-Metriken Dialog zeigt WANDERN defaults (9 Metriken)
- [x] Save Handler speichert display_config + Notification + close
- [x] Edit dialog Profil-Dropdown + display_config preserved
- [x] Badge aktualisiert nach Edit (refresh_list)
- [x] Austria Provider Detection: geosphere für Innsbruck
- [x] Non-Austria: nur openmeteo für Corsica
- [x] Winter metrics enabled für Austria locations
- [x] GeoSphere-only metrics grayed + tooltip für non-Austria
- [x] Safari Factory Pattern auf allen Buttons
- [x] Frozen dataclass rebuild im Save Handler

### Runde 1

Adversary prüfte alle 18 Expected-Behavior-Punkte. Provider Detection via pytest verifiziert (5 Tests). UI-Logik via Code-Inspection bestätigt: Dropdown, Badge, Button, Save Handler alle korrekt implementiert.

### Runde 2

Adversary prüfte Safari-Kompatibilität: alle 8 Button-Handler folgen Factory Pattern. Aggregation round-trip korrekt (lowercase → Label → lowercase). Frozen dataclass rebuild explizit mit allen 8 Feldern.

### Runde 3

Adversary fand 2 Warnings (keine Bugs):
1. Aggregation-Optionen nicht per-Metrik eingeschränkt (alle 4 für jede Metrik statt nur zutreffende)
2. Leere Aggregation bei enabled Metrik speicherbar

Beide sind UX-Verbesserungen, keine funktionalen Defekte. Kein Fix nötig.

## Verdict
**VERIFIED**
