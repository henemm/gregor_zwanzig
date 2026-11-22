package mcp

// MCP-Endpunkt (Streamable HTTP, nur POST mit JSON-Antwort; Friedas do_POST,
// antwort_fuer, antwort_auf, frieda_antwort). Jeder Aufruf prueft das
// Bearer-Token, die Kontosperre und GZ_MCP_USER_IDS neu.

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"strings"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/model"
)

// Protokolle wie Friedas PROTOKOLLE; das erste ist die Vorgabe.
var Protokolle = []string{"2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"}

func bearer(r *http.Request) string {
	a := r.Header.Get("Authorization")
	if len(a) > 7 && strings.EqualFold(a[:7], "bearer ") {
		return strings.TrimSpace(a[7:])
	}
	return ""
}

// tokenKonto: Konto zum Bearer-Token oder nil (unbekannt, abgelaufen,
// gesperrt, ohne Freigabe).
func (h *Handler) tokenKonto(r *http.Request) *model.User {
	uid, ok := h.ablage.accessNutzer(bearer(r))
	if !ok {
		return nil
	}
	u, ok := h.konto(uid)
	if !ok {
		return nil
	}
	return u
}

func (h *Handler) ohneToken(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("WWW-Authenticate", h.wwwAuthenticate(bearer(r) != ""))
	lang := i18n.FromRequest(r, nil)
	jsonAntwort(w, http.StatusUnauthorized, map[string]string{"error": "unauthorized", "message": i18n.T(lang, "mcp.fehler.anmeldung", nil)})
}

// OhnePost: GET/DELETE auf /api/mcp -- ohne Token 401, sonst 405 (kein SSE).
func (h *Handler) OhnePost(w http.ResponseWriter, r *http.Request) {
	if h.tokenKonto(r) == nil {
		h.ohneToken(w, r)
		return
	}
	w.Header().Set("Allow", "POST")
	jsonAntwort(w, http.StatusMethodNotAllowed, map[string]string{"error": "method_not_allowed"})
}

// Endpunkt: POST /api/mcp.
func (h *Handler) Endpunkt(w http.ResponseWriter, r *http.Request) {
	u := h.tokenKonto(r)
	if u == nil {
		h.ohneToken(w, r)
		return
	}
	roh, err := io.ReadAll(r.Body)
	roh = bytes.TrimSpace(roh)
	if err != nil || !json.Valid(roh) {
		jsonAntwort(w, http.StatusBadRequest, rpcFehler(nil, -32700, "Parse error"))
		return
	}
	s := sitzung{h: h, ctx: r.Context(), uid: u.ID, lang: i18n.Parse(u.Lang())}
	var antwort any
	if roh[0] == '[' {
		var liste []json.RawMessage
		json.Unmarshal(roh, &liste)
		var antworten []any
		for _, n := range liste {
			if a := s.antwortAuf(n); a != nil {
				antworten = append(antworten, a)
			}
		}
		if len(antworten) > 0 {
			antwort = antworten
		}
	} else if a := s.antwortAuf(roh); a != nil {
		antwort = a
	}
	if antwort == nil {
		w.WriteHeader(http.StatusAccepted)
		return
	}
	jsonAntwort(w, http.StatusOK, antwort)
}

func rpcFehler(id json.RawMessage, code int, text string) map[string]any {
	return map[string]any{"jsonrpc": "2.0", "id": id, "error": map[string]any{"code": code, "message": text}}
}

// antwortAuf: eine JSON-RPC-Nachricht -> Antwort oder nil (Benachrichtigung).
func (s sitzung) antwortAuf(nachricht json.RawMessage) any {
	var m map[string]json.RawMessage
	var methode, version string
	if json.Unmarshal(nachricht, &m) != nil || json.Unmarshal(m["jsonrpc"], &version) != nil || version != "2.0" ||
		json.Unmarshal(m["method"], &methode) != nil {
		return rpcFehler(nil, -32600, "Invalid Request")
	}
	id, hatID := m["id"]
	if !hatID {
		return nil
	}
	ok := func(ergebnis any) any { return map[string]any{"jsonrpc": "2.0", "id": id, "result": ergebnis} }
	var p struct {
		ProtocolVersion string         `json:"protocolVersion"`
		Name            string         `json:"name"`
		Arguments       map[string]any `json:"arguments"`
	}
	json.Unmarshal(m["params"], &p)
	switch methode {
	case "initialize":
		version := Protokolle[0]
		for _, v := range Protokolle {
			if v == p.ProtocolVersion {
				version = v
			}
		}
		return ok(map[string]any{"protocolVersion": version, "capabilities": map[string]any{"tools": map[string]any{}},
			"serverInfo":   map[string]any{"name": "gregor-wetter", "title": "Gregor Wetter", "version": "1"},
			"instructions": i18n.T(s.lang, "mcp.anleitung", nil)})
	case "ping":
		return ok(map[string]any{})
	case "tools/list":
		return ok(map[string]any{"tools": werkzeuge(s.lang)})
	case "tools/call":
		text, fehler := s.werkzeugAufrufen(p.Name, p.Arguments)
		return ok(map[string]any{"content": []map[string]any{{"type": "text", "text": text}}, "isError": fehler})
	}
	return rpcFehler(id, -32601, "Method not found: "+methode)
}
