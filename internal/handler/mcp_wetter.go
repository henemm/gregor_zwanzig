package handler

// Wetter-Datenweg des MCP-Konnektors „Gregor Wetter“ (Issue #3281, Scheibe 1;
// SPEC docs/specs/modules/mcp_wetter_konnektor.md). Noch ohne oeffentliche
// Route: Scheibe 2 ruft MCPWetterAbrufen aus dem Werkzeug `wetter` auf.
//
// Reihenfolge je Abruf: Mengenbremse `vorhersage` (lokal) -> Tageskontingent
// `user_interactive` (reserviereForecastBudget, ADR-0117, fail-open wie
// /api/forecast) -> Core-Endpunkt /api/_internal/mcp/wetter (X-GZ-Core-Auth
// ueber den DefaultTransport, ADR-0062). Der Core-Abruf traegt keine user_id:
// der Konnektor liest keine Nutzerdaten.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	mcpWetterCorePfad = "/api/_internal/mcp/wetter"
	mcpWetterTimeout  = 60 * time.Second
	mcpWetterMaxBytes = 4 << 20

	// Gruende einer Ablehnung mit Wartezeit.
	MCPGrundBremse     = "bremse"
	MCPGrundKontingent = "kontingent"
)

var (
	ErrMCPWetterdienst = errors.New("mcp-wetter: wetterdienst nicht erreichbar")
	ErrMCPOhneNutzer   = errors.New("mcp-wetter: ohne nutzerkennung")
)

// MCPWetterAnfrage: Koordinaten und Zeitraum (ISO 8601, prueft der Core).
type MCPWetterAnfrage struct {
	Lat, Lon float64
	Von, Bis string
}

// MCPWartenFehler: Abruf abgelehnt (Mengenbremse oder Tageskontingent).
type MCPWartenFehler struct {
	Grund   string
	WartenS int
}

func (e *MCPWartenFehler) Error() string {
	return fmt.Sprintf("mcp-wetter: abgelehnt (%s), warten %d s", e.Grund, e.WartenS)
}

// MCPWetterAbrufen holt die Stundenwerte fuer einen Ort; bremsen darf nil sein.
func MCPWetterAbrufen(ctx context.Context, bremsen *NutzerBremsen, coreURL, userID string, a MCPWetterAnfrage) (json.RawMessage, error) {
	if userID == "" {
		return nil, ErrMCPOhneNutzer
	}
	if ok, warten := bremsen.ZulassenVorhersage(ctx, userID); !ok {
		return nil, &MCPWartenFehler{Grund: MCPGrundBremse, WartenS: wartenSekunden(warten)}
	}
	if urteil, err := reserviereForecastBudget(coreURL, userID); err != nil {
		log.Printf("[mcp-wetter] WARN: budget reserve fehlgeschlagen, fail-open: %v", err)
	} else if !urteil.Allowed {
		return nil, &MCPWartenFehler{Grund: MCPGrundKontingent, WartenS: klemmeRetryAfter(urteil.RetryAfterS)}
	}

	frage := url.Values{}
	frage.Set("lat", strconv.FormatFloat(a.Lat, 'f', -1, 64))
	frage.Set("lon", strconv.FormatFloat(a.Lon, 'f', -1, 64))
	if a.Von != "" {
		frage.Set("von", a.Von)
	}
	if a.Bis != "" {
		frage.Set("bis", a.Bis)
	}
	ziel := strings.TrimSuffix(coreURL, "/") + mcpWetterCorePfad + "?" + frage.Encode()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, ziel, nil)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrMCPWetterdienst, err)
	}
	resp, err := (&http.Client{Timeout: mcpWetterTimeout}).Do(req)
	if err != nil {
		log.Printf("[mcp-wetter] core-Abruf fehlgeschlagen: %v", err)
		return nil, ErrMCPWetterdienst
	}
	defer resp.Body.Close()
	roh, err := io.ReadAll(io.LimitReader(resp.Body, mcpWetterMaxBytes))
	if err != nil || resp.StatusCode != http.StatusOK || !json.Valid(roh) {
		log.Printf("[mcp-wetter] core antwortete mit Status %d (%v)", resp.StatusCode, err)
		return nil, ErrMCPWetterdienst
	}
	return roh, nil
}
