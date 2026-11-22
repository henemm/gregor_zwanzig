package mcp

// Einzelregeln des OAuth-Servers (Issue #3281): Ruecksprungadressen und
// Client-ID-Metadaten-Dokument (CIMD). Der Gesamtablauf durch den echten
// Router steht in internal/router/mcp_oauth_test.go.
//
// Das Client-Dokument liefert hier ein echter httptest-Server, abgerufen ueber
// eine Funktion, die nur Adresse auf Server umschreibt; gezaehlt wird, was dort
// ankommt (der abgeschottete Abruf selbst: internal/resolver/clientdokument_test.go).

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
	"time"

	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const cimdID = "https://claude.ai/oauth/mcp-client-metadata"

func TestRedirectRegeln(t *testing.T) {
	for uri, want := range map[string]bool{
		ClaudeCallback: true, "http://localhost/cb": true, "http://127.0.0.1:9999/cb": true,
		"https://claude.ai/anders": false, "https://evil.example/cb": false, "http://user@localhost/cb": false,
		ClaudeCallback + "#x": false, "https://localhost/cb": false, "http://localhost.evil.example/cb": false,
	} {
		if redirectErlaubt(uri) != want {
			t.Errorf("redirectErlaubt(%q) = %v", uri, !want)
		}
	}
	reg := []string{"http://localhost/callback"}
	if !redirectPasst(reg, "http://localhost:54321/callback") || redirectPasst(reg, "http://localhost:54321/anders") ||
		redirectPasst(reg, ClaudeCallback) {
		t.Errorf("Loopback-Port-Regel verletzt")
	}
	for id, want := range map[string]bool{cimdID: true, "https://claude.ai/": false, "https://claude.ai": false,
		"http://claude.ai/x": false, "https://claude.ai:444/x": false, "https://evil.example/x": false} {
		if cimdErlaubt(id) != want {
			t.Errorf("cimdErlaubt(%q) = %v", id, !want)
		}
	}
}

type cimdWelt struct {
	h      *Handler
	s      *store.Store
	mu     sync.Mutex
	abrufe []string
	doc    string
	kaputt bool
}

func neueCIMDWelt(t *testing.T) *cimdWelt {
	t.Helper()
	w := &cimdWelt{doc: `{"client_id":"` + cimdID + `","client_name":"Claude","redirect_uris":["` + ClaudeCallback + `"]}`}
	srv := httptest.NewServer(http.HandlerFunc(func(rw http.ResponseWriter, r *http.Request) {
		w.mu.Lock()
		defer w.mu.Unlock()
		w.abrufe = append(w.abrufe, r.URL.Path)
		if w.kaputt {
			rw.WriteHeader(http.StatusForbidden)
			return
		}
		rw.Write([]byte(w.doc))
	}))
	t.Cleanup(srv.Close)
	dir := t.TempDir()
	w.s = store.New(dir, "")
	w.h = Neu(Optionen{Basis: "https://gregor.test", DataDir: dir, SessionSecret: "geheim", Nutzer: w.s,
		Freigegeben: map[string]struct{}{"anna": {}},
		ClientDokument: func(ctx context.Context, adresse string) ([]byte, error) {
			u, _ := url.Parse(adresse)
			resp, err := http.Get(srv.URL + u.Path)
			if err != nil {
				return nil, err
			}
			defer resp.Body.Close()
			if resp.StatusCode != http.StatusOK {
				return nil, errors.New(resp.Status)
			}
			return io.ReadAll(resp.Body)
		}})
	if err := w.s.SaveUser(model.User{ID: "anna", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	if err := w.s.AddSession("anna", "s1"); err != nil {
		t.Fatal(err)
	}
	return w
}

func (w *cimdWelt) zahl() int {
	w.mu.Lock()
	defer w.mu.Unlock()
	return len(w.abrufe)
}

func (w *cimdWelt) authorize(methode string, q url.Values) *httptest.ResponseRecorder {
	var req *http.Request
	if methode == http.MethodGet {
		req = httptest.NewRequest(methode, AuthorizePfad+"?"+q.Encode(), nil)
	} else {
		req = httptest.NewRequest(methode, AuthorizePfad, strings.NewReader(q.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Origin", "https://gregor.test")
	}
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID("anna", "s1", "geheim")})
	rec := httptest.NewRecorder()
	w.h.Autorisieren(rec, req)
	return rec
}

func TestCIMD_ClaudeAIWirdEinmalGeladenUndZwischengespeichert(t *testing.T) {
	w := neueCIMDWelt(t)
	v := strings.Repeat("v3rif1er-", 6)
	s := sha256.Sum256([]byte(v))
	q := url.Values{"response_type": {"code"}, "client_id": {cimdID}, "redirect_uri": {ClaudeCallback},
		"code_challenge": {base64.RawURLEncoding.EncodeToString(s[:])}, "code_challenge_method": {"S256"}, "state": {"z"}}
	rec := w.authorize(http.MethodGet, q)
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "claude.ai") {
		t.Fatalf("Zustimmung fuer CIMD-Client: %d %s", rec.Code, rec.Body.String())
	}
	q.Set("aktion", "erlauben")
	rec = w.authorize(http.MethodPost, q)
	loc, _ := url.Parse(rec.Header().Get("Location"))
	form := url.Values{"grant_type": {"authorization_code"}, "code": {loc.Query().Get("code")}, "redirect_uri": {ClaudeCallback},
		"client_id": {cimdID}, "code_verifier": {v}}
	req := httptest.NewRequest(http.MethodPost, TokenPfad, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	trec := httptest.NewRecorder()
	w.h.Token(trec, req)
	if trec.Code != http.StatusOK {
		t.Fatalf("Token fuer CIMD-Client: %d %s", trec.Code, trec.Body.String())
	}
	if w.zahl() != 1 {
		t.Errorf("Client-Dokument %d-mal geladen (erwartet 1, dann aus dem Speicher)", w.zahl())
	}
}

func TestCIMD_FremdeHostsNieAbrufenUndFalscheDokumenteAblehnen(t *testing.T) {
	w := neueCIMDWelt(t)
	if _, ok := w.h.clientFinden(context.Background(), "https://evil.example/meta"); ok || w.zahl() != 0 {
		t.Fatalf("fremder Host abgerufen oder akzeptiert: %d", w.zahl())
	}
	w.doc = `{"client_id":"https://claude.ai/anderes","redirect_uris":["` + ClaudeCallback + `"]}`
	if _, ok := w.h.clientFinden(context.Background(), cimdID); ok {
		t.Errorf("Dokument mit fremder client_id akzeptiert")
	}
	w2 := neueCIMDWelt(t)
	w2.kaputt = true
	w2.h.clientFinden(context.Background(), cimdID)
	w2.h.clientFinden(context.Background(), cimdID)
	if w2.zahl() != 1 {
		t.Errorf("nach Fehlschlag sofort erneut abgerufen: %d", w2.zahl())
	}
}
