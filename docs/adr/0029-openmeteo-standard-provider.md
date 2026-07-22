# ADR-0029: Open-Meteo als Standard-Wetterdaten-Provider

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-07-22 — die Entscheidung ist seit der Go/SvelteKit-Migration gelebte Praxis, hatte aber kein positives ADR; Issue #1343)
- **Datum:** 2026-07-22
- **Bezug:** Löst ADR-0002 ab. `docs/reference/decision_matrix.md` (Ist-Stand), ADR-0018 (Intra-Modell-Fallback, #1115), Epic #1127 (Cross-Provider-Fallback)

## Kontext

ADR-0002 (MVP-Ära) legte MET Norway als Standard mit MOSMIX-Ausnahme-Gate fest.
Mit der Migration auf den Dual-Stack wurde faktisch Open-Meteo die einzige
Standard-Quelle aller Produktionspfade — MET/MOSMIX wurden nie im neuen Stack
implementiert. Die Live-Entscheidung lebte nur in `decision_matrix.md`, nicht
als ADR — genau die Lücke, die ADRs schließen sollen.

## Entscheidung

Alle Produktionspfade (Briefings, Orts-Vergleich, Alerts, Vorschau) beziehen
Wetterdaten über `get_provider("openmeteo")` (`src/providers/base.py`).
Ausfall-Verhalten in dieser Reihenfolge: (1) Intra-Open-Meteo-Modell-Fallback
ohne Kaschieren (ADR-0018), (2) Cross-Provider-Fallback auf regionale
Direktanbindungen AT/DE/FR (`src/providers/region_routing.py`, Epic #1127).
`brightsky` (DWD) dient dem Radar-Pfad, `radar_dpc` dem Nowcast Italien.

## Verworfene Alternativen

- **MET Norway + MOSMIX-Gate (ADR-0002)** — nie in den neuen Stack portiert;
  zwei Quellen mit Auswahl-Heuristik erhöhen Komplexität ohne belegten
  Genauigkeitsgewinn für die Zielgebiete.
- **Direkt-Anbindung je Landeswetterdienst als Standard** — höherer
  Pflegeaufwand (n Parser statt 1 Verteiler); bleibt als Fallback-Stufe 2.

## Konsequenzen

- **Positiv:** Ein Verteiler, ein Metrik-Mapping, ein Kontingent-Modell.
- **Negativ / Preis:** Abhängigkeit von einem Drittanbieter-Aggregator;
  Kontingent-Grenzen (#1329: Radar-Pfad dominiert den Verbrauch — Cache +
  Budget-Steuerung sind Pflicht).
- **Folgepflichten:** Neue Abruf-Pfade immer gegen das Kontingent denken;
  Fallback-Kette nicht kaschierend halten (ADR-0018); `decision_matrix.md`
  bleibt die operative Kurzreferenz.
