// Package mcp ist der MCP-Konnektor „Gregor Wetter“ (Issue #3281, ADR-0128):
// ein OAuth-2.1-Server und ein MCP-Endpunkt (Streamable HTTP, nur POST mit
// JSON-Antwort). Verhalten 1:1 nach henemm/frieda-reist (engine/oauth.py,
// engine/konnektor.py, engine/konten.py); die Anmeldung nutzt Gregors
// Sitzung (gz_session), die Ablage sind Dateien statt SQLite.
//
// Endpunkte (Basis = GZ_PUBLIC_HOST):
//
//	POST /api/mcp                                         MCP mit Bearer-Token
//	GET  /.well-known/oauth-protected-resource[/api/mcp]  RFC 9728
//	GET  /.well-known/oauth-authorization-server          RFC 8414
//	POST /api/mcp/oauth/register                          RFC 7591 (DCR)
//	GET  /api/mcp/oauth/authorize                         Anmeldung, dann Zustimmung
//	POST /api/mcp/oauth/authorize                         Zustimmung -> Code (state, iss)
//	POST /api/mcp/oauth/token                             authorization_code (PKCE S256), refresh_token
//
// Zugang nur fuer Nutzer in GZ_MCP_USER_IDS, nie fuer gesperrte Konten
// (ADR-0080); beides wird bei jedem Token-Gebrauch neu geprueft. Der
// Konnektor liest keine Trips, Orte, Vergleiche oder Empfaenger.
package mcp

import (
	"context"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"log"
	"mime"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/resolver"
)

const (
	ClaudeCallback      = "https://claude.ai/api/mcp/auth_callback"
	RessourcePfad       = "/api/mcp"
	AuthorizePfad       = "/api/mcp/oauth/authorize"
	TokenPfad           = "/api/mcp/oauth/token"
	RegisterPfad        = "/api/mcp/oauth/register"
	MetadatenRessPfad   = "/.well-known/oauth-protected-resource"
	MetadatenServerPfad = "/.well-known/oauth-authorization-server"

	cimdCacheDauer       = 24 * time.Hour
	cimdAbrufeJeMinute   = 20
	cimdFehlschlagPause  = 10 * time.Minute
	registrierungenJeTag = 500
)

var (
	scopes          = []string{"wetter", "offline_access"}
	challengeMuster = regexp.MustCompile(`^[A-Za-z0-9._~-]{43,128}$`)
	cimdHosts       = map[string]bool{"claude.ai": true}
)

// NutzerQuelle ist der Ausschnitt des Stores, den der Konnektor braucht:
// Konto (Sperre, Sprache) und Gaesteliste der Sitzungen.
type NutzerQuelle interface {
	LoadUser(id string) (*model.User, error)
	HasSession(userId, sessionId string) (bool, error)
}

// Ortssuche ist die Signatur von resolver.OrtSuchen.
type Ortssuche func(ctx context.Context, text, sprache string) ([]resolver.OrtKandidat, error)

// Optionen des Konnektors; Ortssuche und ClientDokument nil = Produktionsweg.
type Optionen struct {
	Basis          string
	DataDir        string
	SessionSecret  string
	Nutzer         NutzerQuelle
	Freigegeben    map[string]struct{}
	CoreURL        string
	Bremsen        *handler.NutzerBremsen
	Ortssuche      Ortssuche
	ClientDokument func(ctx context.Context, adresse string) ([]byte, error)
	Jetzt          func() time.Time
}

// Handler beantwortet alle Konnektor-Pfade.
type Handler struct {
	o      Optionen
	basis  string
	ablage *Ablage

	mu              sync.Mutex
	cimdAbrufe      []time.Time
	cimdFehlschlag  map[string]time.Time
	registrierungen []time.Time
}

// Neu baut den Handler.
func Neu(o Optionen) *Handler {
	if o.Ortssuche == nil {
		o.Ortssuche = resolver.OrtSuchen
	}
	if o.ClientDokument == nil {
		o.ClientDokument = resolver.ClientDokumentHolen
	}
	if o.Jetzt == nil {
		o.Jetzt = time.Now
	}
	if o.Freigegeben == nil {
		o.Freigegeben = map[string]struct{}{}
	}
	return &Handler{o: o, basis: strings.TrimRight(o.Basis, "/"), ablage: neueAblage(o.DataDir, o.Jetzt),
		cimdFehlschlag: map[string]time.Time{}}
}

func (h *Handler) ressource() string { return h.basis + RessourcePfad }

func jsonAntwort(w http.ResponseWriter, status int, wert any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	enc.Encode(wert)
}

// MetadatenRessource: RFC 9728 (unter beiden Pfaden).
func (h *Handler) MetadatenRessource(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	jsonAntwort(w, http.StatusOK, map[string]any{
		"resource": h.ressource(), "authorization_servers": []string{h.basis}, "scopes_supported": scopes,
		"bearer_methods_supported": []string{"header"}, "resource_name": "Gregor Wetter"})
}

// MetadatenServer: RFC 8414.
func (h *Handler) MetadatenServer(w http.ResponseWriter, r *http.Request) {
	b := h.basis
	w.Header().Set("Access-Control-Allow-Origin", "*")
	jsonAntwort(w, http.StatusOK, map[string]any{
		"issuer": b, "authorization_endpoint": b + AuthorizePfad, "token_endpoint": b + TokenPfad,
		"registration_endpoint": b + RegisterPfad, "response_types_supported": []string{"code"},
		"grant_types_supported":                 []string{"authorization_code", "refresh_token"},
		"code_challenge_methods_supported":      []string{"S256"},
		"token_endpoint_auth_methods_supported": []string{"none"}, "scopes_supported": scopes,
		"client_id_metadata_document_supported":          true,
		"authorization_response_iss_parameter_supported": true})
}

func (h *Handler) wwwAuthenticate(fehler bool) string {
	z := `Bearer resource_metadata="` + h.basis + MetadatenRessPfad + RessourcePfad + `"`
	if fehler {
		z += `, error="invalid_token"`
	}
	return z
}

// ---------------------------------------------------------------- Redirects und Clients

// loopback: http://localhost bzw. 127.0.0.1, jeder Port, ohne Nutzer-Info.
func loopback(uri string) bool {
	u, err := url.Parse(uri)
	return err == nil && u.Scheme == "http" && (u.Hostname() == "localhost" || u.Hostname() == "127.0.0.1") && u.User == nil
}

// redirectErlaubt: darf ueberhaupt ein Code an diese Adresse gehen?
func redirectErlaubt(uri string) bool {
	if len(uri) > 500 || strings.Contains(uri, "#") {
		return false
	}
	return uri == ClaudeCallback || loopback(uri)
}

// redirectPasst: uri ist registriert; Loopback ohne Ruecksicht auf den Port
// (RFC 8252 7.3).
func redirectPasst(registriert []string, uri string) bool {
	if !redirectErlaubt(uri) {
		return false
	}
	u, _ := url.Parse(uri)
	for _, r := range registriert {
		if r == uri {
			return true
		}
		if loopback(uri) && loopback(r) {
			v, _ := url.Parse(r)
			if v.Hostname() == u.Hostname() && v.Path == u.Path && v.RawQuery == u.RawQuery {
				return true
			}
		}
	}
	return false
}

func cimdErlaubt(clientID string) bool {
	u, err := url.Parse(clientID)
	return err == nil && u.Scheme == "https" && cimdHosts[u.Hostname()] && u.Port() == "" && u.User == nil &&
		u.Path != "" && u.Path != "/"
}

// cimdAbrufErlaubt bremst Abrufe: /token und /authorize sind ohne Anmeldung
// erreichbar, jede unbekannte client_id loeste sonst einen Abruf aus.
func (h *Handler) cimdAbrufErlaubt(clientID string) bool {
	h.mu.Lock()
	defer h.mu.Unlock()
	jetzt := h.o.Jetzt()
	if t, ok := h.cimdFehlschlag[clientID]; ok && jetzt.Sub(t) < cimdFehlschlagPause {
		return false
	}
	frisch := h.cimdAbrufe[:0]
	for _, t := range h.cimdAbrufe {
		if jetzt.Sub(t) < time.Minute {
			frisch = append(frisch, t)
		}
	}
	h.cimdAbrufe = frisch
	if len(h.cimdAbrufe) >= cimdAbrufeJeMinute {
		return false
	}
	h.cimdAbrufe = append(h.cimdAbrufe, jetzt)
	return true
}

func (h *Handler) cimdGescheitert(clientID string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	if len(h.cimdFehlschlag) > 1000 {
		h.cimdFehlschlag = map[string]time.Time{}
	}
	h.cimdFehlschlag[clientID] = h.o.Jetzt()
}

// cimdLaden holt das Client-Dokument (nur claude.ai, abgeschotteter Client).
func (h *Handler) cimdLaden(ctx context.Context, clientID string) (clientEintrag, bool) {
	if !cimdErlaubt(clientID) {
		u, _ := url.Parse(clientID)
		if u != nil {
			log.Printf("[mcp] Client-Dokument von nicht freigegebenem Host abgelehnt: %q", u.Hostname())
		}
		return clientEintrag{}, false
	}
	alt, ok := h.ablage.client(clientID)
	if ok && alt.Art == "cimd" && h.o.Jetzt().Sub(alt.Erstellt) < cimdCacheDauer {
		return alt, true
	}
	if !h.cimdAbrufErlaubt(clientID) {
		return alt, ok
	}
	roh, err := h.o.ClientDokument(ctx, clientID)
	if err != nil {
		h.cimdGescheitert(clientID)
		log.Printf("[mcp] Client-Dokument nicht lesbar: %v", err)
		return alt, ok
	}
	var doc struct {
		ClientID     string   `json:"client_id"`
		ClientName   string   `json:"client_name"`
		RedirectURIs []string `json:"redirect_uris"`
	}
	if json.Unmarshal(roh, &doc) != nil || doc.ClientID != clientID || doc.RedirectURIs == nil {
		return clientEintrag{}, false
	}
	c := clientEintrag{ClientID: clientID, Name: kuerzen(doc.ClientName, 200), RedirectURIs: doc.RedirectURIs,
		Art: "cimd", Erstellt: h.o.Jetzt()}
	h.ablage.cimdSpeichern(c)
	return c, true
}

func kuerzen(s string, n int) string {
	r := []rune(s)
	if len(r) > n {
		return string(r[:n])
	}
	return s
}

func (h *Handler) clientFinden(ctx context.Context, clientID string) (clientEintrag, bool) {
	if strings.HasPrefix(clientID, "https://") {
		return h.cimdLaden(ctx, clientID)
	}
	if clientID == "" || len(clientID) >= 100 {
		return clientEintrag{}, false
	}
	return h.ablage.client(clientID)
}

func (h *Handler) registrierungErlaubt() bool {
	h.mu.Lock()
	defer h.mu.Unlock()
	jetzt := h.o.Jetzt()
	frisch := h.registrierungen[:0]
	for _, t := range h.registrierungen {
		if jetzt.Sub(t) < 24*time.Hour {
			frisch = append(frisch, t)
		}
	}
	h.registrierungen = frisch
	if len(h.registrierungen) >= registrierungenJeTag {
		return false
	}
	h.registrierungen = append(h.registrierungen, jetzt)
	return true
}

// Registrieren: DCR (RFC 7591); die IP-Bremse haengt im Router davor.
func (h *Handler) Registrieren(w http.ResponseWriter, r *http.Request) {
	if !h.registrierungErlaubt() {
		jsonAntwort(w, http.StatusTooManyRequests, map[string]string{"error": "too_many_requests"})
		return
	}
	var roh struct {
		RedirectURIs []string `json:"redirect_uris"`
		ClientName   string   `json:"client_name"`
		AuthMethod   *string  `json:"token_endpoint_auth_method"`
	}
	if err := json.NewDecoder(r.Body).Decode(&roh); err != nil {
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "invalid_client_metadata", "error_description": "not JSON"})
		return
	}
	ok := len(roh.RedirectURIs) > 0 && len(roh.RedirectURIs) <= 10
	for _, u := range roh.RedirectURIs {
		ok = ok && redirectErlaubt(u)
	}
	if !ok {
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "invalid_redirect_uri",
			"error_description": "Only the Claude callback address and loopback addresses are allowed."})
		return
	}
	if roh.AuthMethod != nil && *roh.AuthMethod != "none" {
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "invalid_client_metadata", "error_description": "public clients only (none)"})
		return
	}
	c := clientEintrag{ClientID: "c_" + zufall(16), Name: kuerzen(roh.ClientName, 200), RedirectURIs: roh.RedirectURIs,
		Art: "dcr", Erstellt: h.o.Jetzt()}
	if err := h.ablage.clientRegistrieren(c); err != nil {
		log.Printf("[mcp] Registrierung nicht gespeichert: %v", err)
		jsonAntwort(w, http.StatusServiceUnavailable, map[string]string{"error": "temporarily_unavailable"})
		return
	}
	jsonAntwort(w, http.StatusCreated, map[string]any{"client_id": c.ClientID, "client_id_issued_at": c.Erstellt.Unix(),
		"client_name": c.Name, "redirect_uris": c.RedirectURIs, "token_endpoint_auth_method": "none",
		"grant_types": []string{"authorization_code", "refresh_token"}, "response_types": []string{"code"}})
}

// ---------------------------------------------------------------- Token

func s256(verifier string) string {
	s := sha256.Sum256([]byte(verifier))
	return base64.RawURLEncoding.EncodeToString(s[:])
}

// kontoOK: Konto vorhanden, nicht gesperrt, in GZ_MCP_USER_IDS.
func (h *Handler) kontoOK(uid string) bool {
	_, ok := h.konto(uid)
	return ok
}

func (h *Handler) konto(uid string) (*model.User, bool) {
	if _, frei := h.o.Freigegeben[uid]; !frei || uid == "" {
		return nil, false
	}
	u, err := h.o.Nutzer.LoadUser(uid)
	if err != nil || u == nil || u.Disabled {
		return nil, false
	}
	return u, true
}

// Token: POST /token (application/x-www-form-urlencoded).
func (h *Handler) Token(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "no-store")
	if mt, _, _ := mime.ParseMediaType(r.Header.Get("Content-Type")); mt != "application/x-www-form-urlencoded" || r.ParseForm() != nil {
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "invalid_request", "error_description": "form expected"})
		return
	}
	f := r.PostForm
	clientID := f.Get("client_id")
	if _, ok := h.clientFinden(r.Context(), clientID); !ok {
		jsonAntwort(w, http.StatusUnauthorized, map[string]string{"error": "invalid_client"})
		return
	}
	var t TokenAntwort
	var ok bool
	switch f.Get("grant_type") {
	case "authorization_code":
		v := f.Get("code_verifier")
		// Abweichung von Frieda (AC-8): auch ein fehlender oder unbrauchbarer
		// Verifier verbraucht den Code.
		pruefen := func(ch string) bool {
			return challengeMuster.MatchString(v) && subtle.ConstantTimeCompare([]byte(s256(v)), []byte(ch)) == 1
		}
		t, ok = h.ablage.codeEinloesen(f.Get("code"), clientID, f.Get("redirect_uri"), pruefen, h.kontoOK)
	case "refresh_token":
		t, ok = h.ablage.erneuern(f.Get("refresh_token"), clientID, h.kontoOK)
	default:
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "unsupported_grant_type"})
		return
	}
	if !ok {
		jsonAntwort(w, http.StatusBadRequest, map[string]string{"error": "invalid_grant"})
		return
	}
	jsonAntwort(w, http.StatusOK, t)
}
