# Provider Selection Standard

**Domain:** Auswahl der Wetterdaten-Provider.

**Maßgeblich ist `docs/reference/decision_matrix.md`** (Ist-Stand) — dieses Dokument ist nur
der Merkzettel. Das frühere MET-Norway/MOSMIX-Auswahlmodell der MVP-Ära ist abgelöst
(ADR-0002, superseded) und gilt nicht mehr.

## Kurzfassung

- **Standard-Provider: Open-Meteo** für alle Produktionspfade (Briefings, Orts-Vergleich,
  Alerts, Vorschau) — `get_provider("openmeteo")`, Registry `src/providers/base.py`.
- **Fallback-Kette:** (1) Intra-Modell-Fallback innerhalb Open-Meteo (`REGIONAL_MODELS`,
  ADR-0018), (2) Cross-Provider-Fallback bei Totalausfall über `src/providers/region_routing.py`
  (AT → DE → FR). Ein Ausfall wird nie kaschiert.
- Weitere Provider (GeoSphere, DWD-Direkt, Météo-France, BrightSky, amtliche Warnquellen):
  Tabelle in der Decision Matrix.

## Neuer Provider

1. ADR prüfen/anlegen (`docs/adr/`) — Provider sind Entscheidungsfläche.
2. Decision Matrix und `docs/reference/api_contract.md` (DTO) **vor** dem Code aktualisieren.
3. Normalisierung auf das Standard-DTO; `None` statt `0` für „keine Aussage".
4. Tests nach `.claude/standards/no_mocked_tests.md`: Kern mit aufgezeichneten Fixtures,
   echte API-Calls nur in der Live-Schicht.
