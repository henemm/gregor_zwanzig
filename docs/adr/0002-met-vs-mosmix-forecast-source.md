# ADR-0002: Wetterquelle — MET Norway als Standard, MOSMIX nur als enge Ausnahme

- **Status:** Abgelöst durch ADR-0029 (2026-07-21/22) — Produktions-Provider ist Open-Meteo mit Fallback-Kette, siehe ADR-0029, ADR-0018 und `docs/reference/decision_matrix.md`. MET/MOSMIX sind nicht mehr im Code.
- **Datum:** 2025-08-28
- **Bezug:** `docs/reference/decision_matrix.md` (heute Ist-Stand Open-Meteo; `provider_mapping.md` gelöscht 2026-07-21)

## Kontext

Für einen Wegpunkt muss pro Etappe eine Wettervorhersage gewählt werden. Zur Verfügung stehen u. a.
**MET Norway (Locationforecast)** — flächendeckende Modellvorhersage für beliebige Koordinaten —
und **DWD MOSMIX** — stationsbasierte Vorhersagen, die nur am Stationsort exakt sind und mit
zunehmender Distanz/Höhendifferenz/Land-See-Wechsel an Aussagekraft verlieren. Es braucht eine
**deterministische, nachvollziehbare** Regel, welche Quelle pro Punkt gilt.

## Entscheidung

**MET Norway ist die Standardquelle.** MOSMIX wird **nur** verwendet, wenn **alle** Bedingungen
gegenüber der nächsten Station erfüllt sind:

- Distanz ≤ 25 km **und**
- |ΔHöhe| ≤ 150 m **und**
- Land/See-Flag gleich

Andernfalls: MET. Zur gewählten Quelle wird eine **Confidence** (HIGH/MED/LOW) berechnet, die
Distanz, Höhendifferenz und Gebirgs-Heuristik einrechnet. Die Auswahlentscheidung wird im Debug
nachvollziehbar protokolliert (`source.decision`, `source.chosen`, `source.confidence`).

## Verworfene Alternativen

- **MOSMIX als Standard** — verworfen: stationsbasiert; an beliebigen GPX-Wegpunkten (Grat, Tal,
  küstennah) oft weit von der nächsten Station entfernt → systematisch unzuverlässig.
- **Quellen-Mischung/Interpolation pro Metrik** — verworfen für das MVP: zu komplex, schwer
  nachvollziehbar; eine klare Einzelquelle pro Punkt ist diagnostizierbar.

## Konsequenzen

- **Positiv:** Deterministische, im Debug nachvollziehbare Quellenwahl; MOSMIX-Genauigkeit wird
  nur dort genutzt, wo sie tatsächlich gilt.
- **Negativ / Preis:** Erfordert Stützdaten (MOSMIX-Stationskatalog mit Höhen, DEM für ΔH);
  die Gebirgs-Confidence ist eine Heuristik, kein exaktes Maß.
- **Folgepflichten:** Die Gate-Schwellen (25 km / 150 m / Land-See) sind bewusst gesetzt — Änderungen
  daran sind selbst ADR-würdig. Hinweis: **Confidence** als *Anzeigegröße* ist bewusst **keine**
  wählbare Metrik — siehe [ADR-0005](0005-confidence-not-selectable-metric.md).
