package router

// Testwelt des MCP-Konnektors „Gregor Wetter“ (Issue #3281, Scheibe 2).
// SPEC: docs/specs/modules/mcp_wetter_konnektor.md
//
// Alles laeuft durch den ECHTEN Produktions-Router (router.New) mit allen
// Schutzschichten (AuthMiddleware, OriginGuard, RequireJSONBody, LimitBody).
// Der Python-Core ist ein httptest-Server, der die Kontingent-Reservierung
// beantwortet und fuer den Wetterabruf echte, aufgezeichnete Antworten des
// Core-Endpunkts ausliefert (internal/mcp/testdata/core_*.json, aufgezeichnet
// mit dem FixtureProvider aus tests/fixtures/mcp_wetter). Die Ortssuche ist
// ueber Deps.MCPOrtssuche durch eine feste Kandidatenliste ersetzt (die echte
// Nominatim-Anbindung prueft internal/resolver/ortssuche_test.go netzfrei).

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/resolver"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	mcpBasis    = "https://gregor.test"
	mcpCallback = "https://claude.ai/api/mcp/auth_callback"
)

// Feste Kandidaten der Ortssuche (Werte aus den aufgezeichneten
// Nominatim-Antworten in internal/resolver/testdata).
var (
	kandidatFrankfurtMain = resolver.OrtKandidat{Name: "Frankfurt am Main", Anzeigename: "Frankfurt am Main, Hessen, Deutschland",
		Land: "Deutschland", Lat: 50.1106444, Lon: 8.6820917, Zeitzone: "Europe/Berlin"}
	kandidatFrankfurtOder = resolver.OrtKandidat{Name: "Frankfurt (Oder)", Anzeigename: "Frankfurt (Oder), Brandenburg, Deutschland",
		Land: "Deutschland", Lat: 52.3412273, Lon: 14.549452, Zeitzone: "Europe/Berlin"}
	kandidatMuenster = resolver.OrtKandidat{Name: "Münster", Anzeigename: "Münster, Nordrhein-Westfalen, Deutschland",
		Land: "Deutschland", Lat: 51.9625101, Lon: 7.6251879, Zeitzone: "Europe/Berlin"}
)

type mcpCore struct {
	srv      *httptest.Server
	mu       sync.Mutex
	reserve  []string // user_id je Reservierung
	wetter   []url.Values
	nowcast  []url.Values // Aufrufe von /api/_internal/mcp/nowcast (Issue #3398)
	voll     map[string]bool
	gestoert bool
	// abweisung: 4xx-Rumpf, mit dem der Core den Wetterabruf ablehnt (leer = keiner).
	abweisung string
}

func ladeCoreAufzeichnung(t *testing.T, name string) []byte {
	t.Helper()
	roh, err := os.ReadFile("../mcp/testdata/" + name)
	if err != nil {
		t.Fatalf("Aufzeichnung %s fehlt: %v", name, err)
	}
	return roh
}

func neuerMCPCoreServer(t *testing.T) *mcpCore {
	t.Helper()
	aufz := map[string][]byte{
		"frankfurt": ladeCoreAufzeichnung(t, "core_frankfurt_2h.json"),
		"muenster":  ladeCoreAufzeichnung(t, "core_muenster_72h.json"),
		"zehn":      ladeCoreAufzeichnung(t, "core_frankfurt_10tage.json"),
		// Issue #3398: Nowcast-Antworten im Format des Core-Endpunkts.
		"nc_regen":      ladeCoreAufzeichnung(t, "core_nowcast_regen.json"),
		"nc_trocken":    ladeCoreAufzeichnung(t, "core_nowcast_trocken.json"),
		"nc_nv":         ladeCoreAufzeichnung(t, "core_nowcast_nicht_verfuegbar.json"),
		"nc_gedrosselt": ladeCoreAufzeichnung(t, "core_nowcast_gedrosselt.json"),
		// Adversary F004/F008: Horizont-Hinweis und Vorrang gedrosselt vor trocken.
		"nc_horizont":           ladeCoreAufzeichnung(t, "core_nowcast_horizont.json"),
		"nc_gedrosselt_trocken": ladeCoreAufzeichnung(t, "core_nowcast_gedrosselt_trocken.json"),
	}
	c := &mcpCore{voll: map[string]bool{}}
	c.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		defer c.mu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		q := r.URL.Query()
		switch r.URL.Path {
		case "/api/_internal/forecast-budget/reserve":
			c.reserve = append(c.reserve, q.Get("user_id"))
			if c.voll[q.Get("user_id")] {
				w.Write([]byte(`{"allowed": false, "retry_after_s": 5400}`))
				return
			}
			w.Write([]byte(`{"allowed": true}`))
		case "/api/_internal/mcp/wetter":
			c.wetter = append(c.wetter, q)
			if c.abweisung != "" {
				w.WriteHeader(http.StatusUnprocessableEntity)
				w.Write([]byte(c.abweisung))
				return
			}
			if c.gestoert {
				w.WriteHeader(http.StatusBadGateway)
				w.Write([]byte(`{"detail":{"error":"provider_error"}}`))
				return
			}
			switch {
			case strings.HasPrefix(q.Get("bis"), "2099"):
				w.Write(aufz["zehn"])
			case strings.HasPrefix(q.Get("lat"), "51.96"):
				w.Write(aufz["muenster"])
			default:
				w.Write(aufz["frankfurt"])
			}
		case "/api/_internal/mcp/nowcast":
			c.nowcast = append(c.nowcast, q)
			switch {
			case strings.HasPrefix(q.Get("lat"), "51.96"):
				w.Write(aufz["nc_trocken"])
			case strings.HasPrefix(q.Get("lat"), "40"):
				w.Write(aufz["nc_nv"])
			case strings.HasPrefix(q.Get("lat"), "41"):
				w.Write(aufz["nc_gedrosselt"])
			case strings.HasPrefix(q.Get("lat"), "42"):
				w.Write(aufz["nc_horizont"])
			case strings.HasPrefix(q.Get("lat"), "43"):
				w.Write(aufz["nc_gedrosselt_trocken"])
			default:
				w.Write(aufz["nc_regen"])
			}
		default:
			w.WriteHeader(http.StatusOK)
			w.Write([]byte(`{}`))
		}
	}))
	t.Cleanup(c.srv.Close)
	return c
}

func (c *mcpCore) zaehle() (reserve, wetter int) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.reserve), len(c.wetter)
}

type mcpWelt struct {
	t    *testing.T
	r    chi.Router
	cfg  *config.Config
	s    *store.Store
	core *mcpCore
}

// neueMCPWelt baut den echten Router; freigegeben landet in GZ_MCP_USER_IDS.
func neueMCPWelt(t *testing.T, freigegeben ...string) *mcpWelt {
	t.Helper()
	core := neuerMCPCoreServer(t)
	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = core.srv.URL
	cfg.PublicHost = mcpBasis
	cfg.MCPUserIDs = strings.Join(freigegeben, ",")
	cfg.SMTPHost, cfg.GoogleSMTPHost, cfg.FallbackSMTPHost = "", "", ""
	s := store.New(cfg.DataDir, "")
	r := neuerRouterMitConfig(t, cfg, s)
	return &mcpWelt{t: t, r: r, cfg: cfg, s: s, core: core}
}

// neuerRouterMitConfig baut den echten Router zu cfg und s; die Ortssuche
// antwortet aus der festen Kandidatenliste.
func neuerRouterMitConfig(t *testing.T, cfg *config.Config, s *store.Store) chi.Router {
	t.Helper()
	wa, err := webauthn.New(&webauthn.Config{RPID: "localhost", RPDisplayName: "t", RPOrigins: []string{"http://localhost:5173"}})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)
	orte := map[string][]resolver.OrtKandidat{
		"Frankfurt am Main": {kandidatFrankfurtMain},
		"Frankfurt":         {kandidatFrankfurtMain, kandidatFrankfurtOder},
		"Münster":           {kandidatMuenster},
	}
	return New(Deps{
		Config: cfg, Store: s, WeatherProvider: stillerProvider{}, WebAuthn: wa,
		ChallengeStore: handler.NewChallengeStore(), Scheduler: sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir), GitCommit: "test",
		MCPOrtssuche: func(_ context.Context, text, _ string) ([]resolver.OrtKandidat, error) {
			return orte[text], nil
		},
	})
}

// konto legt ein Konto mit Sitzung an und liefert das Sitzungs-Cookie.
func (w *mcpWelt) konto(u model.User) *http.Cookie {
	w.t.Helper()
	if u.CreatedAt.IsZero() {
		u.CreatedAt = time.Now()
	}
	kontoVollSchreiben(w.t, w.s, u)
	if err := w.s.AddSession(u.ID, sessionIDFor(u.ID)); err != nil {
		w.t.Fatalf("AddSession: %v", err)
	}
	return sessionCookieFor(u.ID, w.cfg.SessionSecret)
}

func (w *mcpWelt) anfrage(req *http.Request) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	w.r.ServeHTTP(rec, req)
	return rec
}

func (w *mcpWelt) registrieren(uris ...string) (int, map[string]any) {
	w.t.Helper()
	body, _ := json.Marshal(map[string]any{"client_name": "Claude", "redirect_uris": uris})
	req := httptest.NewRequest(http.MethodPost, "/api/mcp/oauth/register", strings.NewReader(string(body)))
	req.Header.Set("Content-Type", "application/json")
	rec := w.anfrage(req)
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	return rec.Code, m
}

func pkcePaar() (verifier, challenge string) {
	verifier = strings.Repeat("v3rif1er-", 6)
	sum := sha256.Sum256([]byte(verifier))
	return verifier, base64.RawURLEncoding.EncodeToString(sum[:])
}

func authorizeWerte(client, challenge string) url.Values {
	return url.Values{
		"response_type": {"code"}, "client_id": {client}, "redirect_uri": {mcpCallback},
		"code_challenge": {challenge}, "code_challenge_method": {"S256"}, "state": {"zustand-1"},
		"scope": {"wetter offline_access"}, "resource": {mcpBasis + "/api/mcp"},
	}
}

func (w *mcpWelt) authorizeGet(q url.Values, keks *http.Cookie) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodGet, "/api/mcp/oauth/authorize?"+q.Encode(), nil)
	if keks != nil {
		req.AddCookie(keks)
	}
	return w.anfrage(req)
}

func (w *mcpWelt) authorizePost(q url.Values, aktion string, keks *http.Cookie, origin string) *httptest.ResponseRecorder {
	form := url.Values{}
	for k, v := range q {
		form[k] = v
	}
	form.Set("aktion", aktion)
	req := httptest.NewRequest(http.MethodPost, "/api/mcp/oauth/authorize", strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	if origin != "" {
		req.Header.Set("Origin", origin)
	}
	if keks != nil {
		req.AddCookie(keks)
	}
	return w.anfrage(req)
}

// zustimmen: GET (Zustimmungsseite) + POST erlauben -> Location mit code.
func (w *mcpWelt) zustimmen(client, challenge string, keks *http.Cookie) string {
	w.t.Helper()
	q := authorizeWerte(client, challenge)
	if rec := w.authorizeGet(q, keks); rec.Code != http.StatusOK {
		w.t.Fatalf("Zustimmungsseite: Status %d, %s", rec.Code, rec.Body.String())
	}
	rec := w.authorizePost(q, "erlauben", keks, mcpBasis)
	if rec.Code != http.StatusSeeOther {
		w.t.Fatalf("Zustimmung: Status %d, %s", rec.Code, rec.Body.String())
	}
	return rec.Header().Get("Location")
}

func codeAus(location string) string {
	u, err := url.Parse(location)
	if err != nil {
		return ""
	}
	return u.Query().Get("code")
}

func (w *mcpWelt) token(felder url.Values) (int, map[string]any) {
	w.t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/mcp/oauth/token", strings.NewReader(felder.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	rec := w.anfrage(req)
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	return rec.Code, m
}

// verbinden: wie die Claude-App registrieren, zustimmen, Token holen.
func (w *mcpWelt) verbinden(keks *http.Cookie) (tokens map[string]any, client string) {
	w.t.Helper()
	code, c := w.registrieren(mcpCallback)
	if code != http.StatusCreated {
		w.t.Fatalf("Registrierung: %d %v", code, c)
	}
	client, _ = c["client_id"].(string)
	v, ch := pkcePaar()
	loc := w.zustimmen(client, ch, keks)
	status, t := w.token(url.Values{"grant_type": {"authorization_code"}, "code": {codeAus(loc)},
		"redirect_uri": {mcpCallback}, "client_id": {client}, "code_verifier": {v}})
	if status != http.StatusOK {
		w.t.Fatalf("Token: %d %v", status, t)
	}
	return t, client
}

// mcp schickt eine JSON-RPC-Nachricht an /api/mcp.
func (w *mcpWelt) mcp(access, methode string, params any) (*httptest.ResponseRecorder, map[string]any) {
	w.t.Helper()
	body, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": 1, "method": methode, "params": params})
	req := httptest.NewRequest(http.MethodPost, "/api/mcp", strings.NewReader(string(body)))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json, text/event-stream")
	if access != "" {
		req.Header.Set("Authorization", "Bearer "+access)
	}
	rec := w.anfrage(req)
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	return rec, m
}

// werkzeug ruft tools/call und liefert (Text, isError).
func (w *mcpWelt) werkzeug(access, name string, args map[string]any) (string, bool) {
	w.t.Helper()
	rec, a := w.mcp(access, "tools/call", map[string]any{"name": name, "arguments": args})
	if rec.Code != http.StatusOK {
		w.t.Fatalf("tools/call %s: Status %d %s", name, rec.Code, rec.Body.String())
	}
	res, _ := a["result"].(map[string]any)
	inhalt, _ := res["content"].([]any)
	if len(inhalt) == 0 {
		w.t.Fatalf("tools/call %s ohne content: %s", name, rec.Body.String())
	}
	erster, _ := inhalt[0].(map[string]any)
	text, _ := erster["text"].(string)
	fehler, _ := res["isError"].(bool)
	return text, fehler
}

func nahe(a, b float64) bool { return math.Abs(a-b) < 1e-6 }
