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

	"github.com/henemm/gregor-api/internal/provider/openmeteo"
)

const (
	mcpWetterCorePfad = "/api/_internal/mcp/wetter"
	mcpWetterTimeout  = 60 * time.Second
	mcpWetterMaxBytes = 4 << 20
	// mcpZeitMaxZeichen: dieselbe Grenze wie der Core-Parameter (max_length).
	mcpZeitMaxZeichen = 40

	// Gruende einer Ablehnung mit Wartezeit.
	MCPGrundBremse     = "bremse"
	MCPGrundKontingent = "kontingent"

	// Codes der Eingabefehler; gleichlautend mit den Core-Codes
	// (api.fehler.<code>), Scheibe 2 bildet sie auf mcp.json ab.
	MCPCodeZeitpunktUngueltig   = "mcp_zeitpunkt_ungueltig"
	MCPCodeBisVorVon            = "mcp_bis_vor_von"
	MCPCodeKoordinatenUngueltig = "mcp_koordinaten_ungueltig"
)

var (
	ErrMCPWetterdienst = errors.New("mcp-wetter: wetterdienst nicht erreichbar")
	ErrMCPOhneNutzer   = errors.New("mcp-wetter: ohne nutzerkennung")
	ErrMCPZeitraum     = errors.New("mcp-wetter: zeitraum ungueltig")
	ErrMCPKoordinaten  = errors.New("mcp-wetter: koordinaten ungueltig")
)

// mcpZeitFormate: ISO 8601 mit oder ohne Offset, auf Minute, Sekunde oder Tag.
var mcpZeitFormate = []string{
	time.RFC3339Nano, "2006-01-02T15:04Z07:00",
	"2006-01-02T15:04:05.999999999", "2006-01-02T15:04", "2006-01-02",
}

// MCPWetterAnfrage: Koordinaten und Zeitraum (ISO 8601; ohne Offset Ortszeit).
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

// MCPEingabeFehler: ungueltige Anfrage (Code wie im Core-Katalog; Detail ist
// der Text des Core, falls er die Anfrage abgewiesen hat, sonst leer).
type MCPEingabeFehler struct {
	Code, Detail string
	wurzel       error
}

func (e *MCPEingabeFehler) Error() string {
	return fmt.Sprintf("%v (%s)", e.wurzel, e.Code)
}

func (e *MCPEingabeFehler) Unwrap() error { return e.wurzel }

func zeitraumFehler(code, detail string) error {
	return &MCPEingabeFehler{Code: code, Detail: detail, wurzel: ErrMCPZeitraum}
}

// mcpZeitpunkt liest einen Zeitpunkt; ohne Offset in der Zone ort.
func mcpZeitpunkt(text string, ort *time.Location) (time.Time, bool) {
	if len(text) > mcpZeitMaxZeichen {
		return time.Time{}, false
	}
	for _, format := range mcpZeitFormate {
		if t, err := time.ParseInLocation(format, text, ort); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

// pruefeMCPAnfrage weist Eingabefehler ab, BEVOR Bremse oder Kontingent
// belastet werden. Dieselben Regeln wie der Core: bis muss nach von liegen.
func pruefeMCPAnfrage(a MCPWetterAnfrage) error {
	if !(a.Lat >= -90 && a.Lat <= 90 && a.Lon >= -180 && a.Lon <= 180) {
		return &MCPEingabeFehler{Code: MCPCodeKoordinatenUngueltig, wurzel: ErrMCPKoordinaten}
	}
	// gz-store-scope-call: time.LoadLocation ist die Zeitzone der Standardbibliothek, kein Store-Aufruf
	ort, err := time.LoadLocation(openmeteo.TimezoneForCoords(a.Lat, a.Lon))
	if err != nil {
		ort = time.UTC
	}
	von := time.Now()
	if a.Von != "" {
		t, ok := mcpZeitpunkt(a.Von, ort)
		if !ok {
			return zeitraumFehler(MCPCodeZeitpunktUngueltig, "")
		}
		von = t
	}
	if a.Bis == "" {
		return nil
	}
	bis, ok := mcpZeitpunkt(a.Bis, ort)
	if !ok {
		return zeitraumFehler(MCPCodeZeitpunktUngueltig, "")
	}
	if !bis.After(von) {
		return zeitraumFehler(MCPCodeBisVorVon, "")
	}
	return nil
}

// MCPWetterAbrufen holt die Stundenwerte fuer einen Ort; bremsen darf nil sein.
func MCPWetterAbrufen(ctx context.Context, bremsen *NutzerBremsen, coreURL, userID string, a MCPWetterAnfrage) (json.RawMessage, error) {
	if userID == "" {
		return nil, ErrMCPOhneNutzer
	}
	if err := pruefeMCPAnfrage(a); err != nil {
		return nil, err
	}
	if ok, warten := bremsen.ZulassenVorhersage(ctx, userID); !ok {
		return nil, &MCPWartenFehler{Grund: MCPGrundBremse, WartenS: wartenSekunden(warten)}
	}
	if urteil, err := reserviereForecastBudget(coreURL, userID); err != nil {
		log.Printf("[mcp-wetter] WARN: budget reserve fehlgeschlagen, fail-open: %v", err)
	} else if !urteil.Allowed {
		return nil, &MCPWartenFehler{Grund: MCPGrundKontingent, WartenS: klemmeRetryAfter(urteil.RetryAfterS)}
	}
	return holeMCPWetter(ctx, coreURL, a)
}

func holeMCPWetter(ctx context.Context, coreURL string, a MCPWetterAnfrage) (json.RawMessage, error) {
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
	if err == nil && resp.StatusCode >= 400 && resp.StatusCode < 500 {
		return nil, coreEingabeFehler(roh)
	}
	if err != nil || resp.StatusCode != http.StatusOK || !json.Valid(roh) {
		log.Printf("[mcp-wetter] core antwortete mit Status %d (%v)", resp.StatusCode, err)
		return nil, ErrMCPWetterdienst
	}
	return roh, nil
}

// coreEingabeFehler uebernimmt Code und Text einer 4xx-Antwort des Core
// ({"detail": "<Text>", "code": "<code>"}); eine Validierungsantwort von
// FastAPI (detail als Liste) wird zu invalid_params ohne Text.
func coreEingabeFehler(roh []byte) error {
	var antwort struct {
		Code   string          `json:"code"`
		Detail json.RawMessage `json:"detail"`
	}
	_ = json.Unmarshal(roh, &antwort)
	var detail string
	_ = json.Unmarshal(antwort.Detail, &detail)
	if antwort.Code == "" {
		antwort.Code = "invalid_params"
	}
	return zeitraumFehler(antwort.Code, detail)
}
