package handler

// Nowcast-Datenweg des MCP-Konnektors (Issue #3398, Scheibe 3; SPEC
// docs/specs/modules/mcp_wetter_vollstaendig.md). Dieselbe Reihenfolge wie
// MCPWetterAbrufen: Koordinaten pruefen -> Mengenbremse `vorhersage` ->
// Tageskontingent `user_interactive` -> Core /api/_internal/mcp/nowcast
// (X-GZ-Core-Auth ueber den DefaultTransport, ohne user_id).

import (
	"context"
	"encoding/json"
)

const mcpNowcastCorePfad = "/api/_internal/mcp/nowcast"

// MCPNowcastAbrufen holt den Regen-/Gewitter-Nowcast fuer einen Ort; bremsen darf nil sein.
func MCPNowcastAbrufen(ctx context.Context, bremsen *NutzerBremsen, coreURL, userID string, lat, lon float64) (json.RawMessage, error) {
	if userID == "" {
		return nil, ErrMCPOhneNutzer
	}
	if !(lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
		return nil, &MCPEingabeFehler{Code: MCPCodeKoordinatenUngueltig, wurzel: ErrMCPKoordinaten}
	}
	if err := mcpZulassen(ctx, bremsen, coreURL, userID); err != nil {
		return nil, err
	}
	return holeMCPCore(ctx, coreURL, mcpNowcastCorePfad, mcpKoordinaten(lat, lon))
}
