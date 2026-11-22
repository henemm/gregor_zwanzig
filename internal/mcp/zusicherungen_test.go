package mcp

// Zusicherungen des OAuth-Servers und des MCP-Endpunkts, die der Adversary
// (PR #3282) als ungetestet gemeldet hat (F001-F010). Echte Handler, echte
// Dateiablage unter t.TempDir(), die Uhr ueber Optionen.Jetzt; das
// Client-Dokument (CIMD) liefert ein httptest-Server.

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
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

const zBasis = "https://gregor.test"

type zWelt struct {
	t      *testing.T
	h      *Handler
	s      *store.Store
	mu     sync.Mutex
	jetzt  time.Time
	abrufe []string
	docs   map[string]string // Pfad -> Dokument; fehlt = 404
}

func neueZWelt(t *testing.T) *zWelt {
	t.Helper()
	w := &zWelt{t: t, jetzt: time.Date(2026, 11, 22, 12, 0, 0, 0, time.UTC), docs: map[string]string{}}
	srv := httptest.NewServer(http.HandlerFunc(func(rw http.ResponseWriter, r *http.Request) {
		w.mu.Lock()
		defer w.mu.Unlock()
		w.abrufe = append(w.abrufe, r.URL.Path)
		doc, ok := w.docs[r.URL.Path]
		if !ok {
			rw.WriteHeader(http.StatusNotFound)
			return
		}
		rw.Write([]byte(doc))
	}))
	t.Cleanup(srv.Close)
	dir := t.TempDir()
	w.s = store.New(dir, "")
	w.h = Neu(Optionen{Basis: zBasis, DataDir: dir, SessionSecret: "geheim", Nutzer: w.s,
		Freigegeben: map[string]struct{}{"anna": {}},
		Jetzt: func() time.Time {
			w.mu.Lock()
			defer w.mu.Unlock()
			return w.jetzt
		},
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

func (w *zWelt) vor(d time.Duration) {
	w.mu.Lock()
	w.jetzt = w.jetzt.Add(d)
	w.mu.Unlock()
}

func (w *zWelt) zahlAbrufe() int {
	w.mu.Lock()
	defer w.mu.Unlock()
	return len(w.abrufe)
}

func (w *zWelt) registrieren(uris ...string) (int, string) {
	body, _ := json.Marshal(map[string]any{"client_name": "Claude", "redirect_uris": uris})
	rec := httptest.NewRecorder()
	w.h.Registrieren(rec, httptest.NewRequest(http.MethodPost, RegisterPfad, strings.NewReader(string(body))))
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	id, _ := m["client_id"].(string)
	return rec.Code, id
}

const zVerifier = "v3rif1er-v3rif1er-v3rif1er-v3rif1er-v3rif1er-v3rif1er-"

func zAnfrage(client, redirect, challenge string) url.Values {
	return url.Values{"response_type": {"code"}, "client_id": {client}, "redirect_uri": {redirect},
		"code_challenge": {challenge}, "code_challenge_method": {"S256"}, "state": {"z"}}
}

func (w *zWelt) authorize(methode string, q url.Values, sid string) *httptest.ResponseRecorder {
	var req *http.Request
	if methode == http.MethodGet {
		req = httptest.NewRequest(methode, AuthorizePfad+"?"+q.Encode(), nil)
	} else {
		req = httptest.NewRequest(methode, AuthorizePfad, strings.NewReader(q.Encode()))
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Origin", zBasis)
	}
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID("anna", sid, "geheim")})
	rec := httptest.NewRecorder()
	w.h.Autorisieren(rec, req)
	return rec
}

// code holt einen Authorization-Code fuer client an redirect.
func (w *zWelt) code(client, redirect string) string {
	w.t.Helper()
	q := zAnfrage(client, redirect, s256(zVerifier))
	q.Set("aktion", "erlauben")
	rec := w.authorize(http.MethodPost, q, "s1")
	loc, _ := url.Parse(rec.Header().Get("Location"))
	if rec.Code != http.StatusSeeOther || loc.Query().Get("code") == "" {
		w.t.Fatalf("kein Code: %d %q %s", rec.Code, rec.Header().Get("Location"), rec.Body.String())
	}
	return loc.Query().Get("code")
}

func (w *zWelt) token(form url.Values) (int, map[string]any) {
	req := httptest.NewRequest(http.MethodPost, TokenPfad, strings.NewReader(form.Encode()))
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	rec := httptest.NewRecorder()
	w.h.Token(rec, req)
	var m map[string]any
	json.Unmarshal(rec.Body.Bytes(), &m)
	return rec.Code, m
}

func codeForm(code, client, redirect string) url.Values {
	return url.Values{"grant_type": {"authorization_code"}, "code": {code}, "client_id": {client},
		"redirect_uri": {redirect}, "code_verifier": {zVerifier}}
}

func (w *zWelt) tokens(client string) map[string]any {
	w.t.Helper()
	status, t := w.token(codeForm(w.code(client, ClaudeCallback), client, ClaudeCallback))
	if status != http.StatusOK {
		w.t.Fatalf("Token: %d %v", status, t)
	}
	return t
}

func (w *zWelt) mcp(access, body string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, RessourcePfad, strings.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+access)
	rec := httptest.NewRecorder()
	w.h.Endpunkt(rec, req)
	return rec
}

// F001: der Code ist an die redirect_uri gebunden und nach dem Fehlversuch verbraucht.
func TestCode_AnRedirectURIGebunden(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback, "http://localhost/cb")
	code := w.code(c, ClaudeCallback)
	if status, f := w.token(codeForm(code, c, "http://localhost/cb")); status != http.StatusBadRequest || f["error"] != "invalid_grant" {
		t.Fatalf("andere redirect_uri: %d %v", status, f)
	}
	if status, _ := w.token(codeForm(code, c, ClaudeCallback)); status != http.StatusBadRequest {
		t.Errorf("Code nach Fehlversuch nicht verbraucht: %d", status)
	}
}

// F002: der Code ist an den Client gebunden.
func TestCode_AnClientGebunden(t *testing.T) {
	w := neueZWelt(t)
	_, a := w.registrieren(ClaudeCallback)
	_, b := w.registrieren(ClaudeCallback)
	code := w.code(a, ClaudeCallback)
	if status, f := w.token(codeForm(code, b, ClaudeCallback)); status != http.StatusBadRequest || f["error"] != "invalid_grant" {
		t.Fatalf("Code von A mit B: %d %v", status, f)
	}
	if status, _ := w.token(codeForm(code, a, ClaudeCallback)); status != http.StatusBadRequest {
		t.Errorf("Code nach Fehlversuch nicht verbraucht: %d", status)
	}
}

// F003: Codes leben 5 Minuten.
func TestCode_Laeuft5MinutenNachAusstellungAb(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	frisch := w.code(c, ClaudeCallback)
	alt := w.code(c, ClaudeCallback)
	w.vor(5*time.Minute - time.Second)
	if status, f := w.token(codeForm(frisch, c, ClaudeCallback)); status != http.StatusOK {
		t.Fatalf("Code kurz vor Ablauf: %d %v", status, f)
	}
	w.vor(2 * time.Second)
	if status, _ := w.token(codeForm(alt, c, ClaudeCallback)); status != http.StatusBadRequest {
		t.Errorf("Code nach 5 Minuten noch gueltig: %d", status)
	}
}

func refreshForm(refresh, client string) url.Values {
	return url.Values{"grant_type": {"refresh_token"}, "refresh_token": {refresh}, "client_id": {client}}
}

// F004: Refresh-Tokens leben 90 Tage und sind an den Client gebunden.
func TestRefresh_Ablauf90TageUndClientBindung(t *testing.T) {
	w := neueZWelt(t)
	_, a := w.registrieren(ClaudeCallback)
	_, b := w.registrieren(ClaudeCallback)
	frisch, alt := w.tokens(a), w.tokens(a)
	if status, f := w.token(refreshForm(frisch["refresh_token"].(string), b)); status != http.StatusBadRequest || f["error"] != "invalid_grant" {
		t.Fatalf("Refresh von A mit Client B: %d %v", status, f)
	}
	w.vor(90*24*time.Hour - time.Minute)
	if status, f := w.token(refreshForm(frisch["refresh_token"].(string), a)); status != http.StatusOK {
		t.Fatalf("Refresh kurz vor 90 Tagen: %d %v", status, f)
	}
	w.vor(2 * time.Minute)
	if status, _ := w.token(refreshForm(alt["refresh_token"].(string), a)); status != http.StatusBadRequest {
		t.Errorf("Refresh nach 90 Tagen noch gueltig: %d", status)
	}
}

// F005: Access-Tokens leben 1 Stunde.
func TestAccess_Laeuft1StundeNachAusstellungAb(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	access := w.tokens(c)["access_token"].(string)
	ping := `{"jsonrpc":"2.0","id":1,"method":"ping"}`
	w.vor(59 * time.Minute)
	if rec := w.mcp(access, ping); rec.Code != http.StatusOK {
		t.Fatalf("Access-Token nach 59 Minuten: %d", rec.Code)
	}
	w.vor(2 * time.Minute)
	if rec := w.mcp(access, ping); rec.Code != http.StatusUnauthorized {
		t.Errorf("Access-Token nach 61 Minuten noch gueltig: %d", rec.Code)
	}
}

// F006 + F009: Callback exakt, Loopback-Port nur leer oder 1..65535.
func TestRedirect_ExaktUndLoopbackPort(t *testing.T) {
	for _, uri := range []string{ClaudeCallback + "/x", ClaudeCallback + ".evil", ClaudeCallback + "?x",
		"http://localhost:99999/cb", "http://localhost:/cb", "http://localhost:0/cb", "http://127.0.0.1:65536/cb",
		"http://localhost:+80/cb"} {
		if redirectErlaubt(uri) {
			t.Errorf("redirectErlaubt(%q) = true", uri)
		}
	}
	for _, uri := range []string{ClaudeCallback, "http://localhost/cb", "http://localhost:1/cb", "http://127.0.0.1:65535/cb"} {
		if !redirectErlaubt(uri) {
			t.Errorf("redirectErlaubt(%q) = false", uri)
		}
	}
	if status, _ := neueZWelt(t).registrieren("http://localhost:99999/cb"); status != http.StatusBadRequest {
		t.Errorf("Registrierung mit Port 99999: %d", status)
	}
}

// F006: ein Client-Dokument darf keine fremde Redirect-URI einschleusen.
func TestCIMD_FremdeRedirectURIImDokumentWirdAbgelehnt(t *testing.T) {
	w := neueZWelt(t)
	id := "https://claude.ai/oauth/boese"
	w.docs["/oauth/boese"] = `{"client_id":"` + id + `","redirect_uris":["https://evil.com/cb"]}`
	rec := w.authorize(http.MethodGet, zAnfrage(id, "https://evil.com/cb", s256(zVerifier)), "s1")
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("fremde Redirect-URI aus dem Dokument akzeptiert: %d", rec.Code)
	}
	q := zAnfrage(id, "https://evil.com/cb", s256(zVerifier))
	q.Set("aktion", "erlauben")
	if rec := w.authorize(http.MethodPost, q, "s1"); strings.Contains(rec.Header().Get("Location"), "code=") {
		t.Errorf("Code an fremde Redirect-URI: %q", rec.Header().Get("Location"))
	}
}

// F007: Tagesgrenze der Registrierung (500 je 24 h); Zahlen bewusst als
// Literal, damit eine geaenderte Konstante auffaellt.
func TestDCR_Tagesgrenze(t *testing.T) {
	w := neueZWelt(t)
	for i := 0; i < 500; i++ {
		if status, _ := w.registrieren(ClaudeCallback); status != http.StatusCreated {
			t.Fatalf("Registrierung %d: %d", i+1, status)
		}
	}
	if status, _ := w.registrieren(ClaudeCallback); status != http.StatusTooManyRequests {
		t.Fatalf("Registrierung %d: %d (erwartet 429)", 500+1, status)
	}
	w.vor(24*time.Hour + time.Second)
	if status, _ := w.registrieren(ClaudeCallback); status != http.StatusCreated {
		t.Errorf("nach 24 Stunden: %d", status)
	}
}

// F007: hoechstens 20 Abrufe von Client-Dokumenten je Minute.
func TestCIMD_AbrufbremseJeMinute(t *testing.T) {
	w := neueZWelt(t)
	id := func(i int) string { return fmt.Sprintf("https://claude.ai/oauth/c%d", i) }
	for i := 0; i <= 20; i++ {
		w.docs[fmt.Sprintf("/oauth/c%d", i)] = `{"client_id":"` + id(i) + `","redirect_uris":["` + ClaudeCallback + `"]}`
	}
	for i := 0; i < 20; i++ {
		if _, ok := w.h.clientFinden(context.Background(), id(i)); !ok {
			t.Fatalf("Dokument %d nicht geladen", i)
		}
	}
	if _, ok := w.h.clientFinden(context.Background(), id(20)); ok || w.zahlAbrufe() != 20 {
		t.Fatalf("Abruf %d trotz Bremse: ok=%v, Abrufe %d", 20+1, ok, w.zahlAbrufe())
	}
	w.vor(time.Minute + time.Second)
	if _, ok := w.h.clientFinden(context.Background(), id(20)); !ok {
		t.Errorf("nach einer Minute weiter gebremst")
	}
}

// F007: nach einem Fehlschlag 10 Minuten Pause je client_id.
func TestCIMD_PauseNachFehlschlag(t *testing.T) {
	w := neueZWelt(t)
	id := "https://claude.ai/oauth/spaeter"
	w.h.clientFinden(context.Background(), id)
	w.docs["/oauth/spaeter"] = `{"client_id":"` + id + `","redirect_uris":["` + ClaudeCallback + `"]}`
	w.vor(10*time.Minute - time.Second)
	if _, ok := w.h.clientFinden(context.Background(), id); ok || w.zahlAbrufe() != 1 {
		t.Fatalf("Abruf in der Pause: ok=%v, Abrufe %d", ok, w.zahlAbrufe())
	}
	w.vor(2 * time.Second)
	if _, ok := w.h.clientFinden(context.Background(), id); !ok || w.zahlAbrufe() != 2 {
		t.Errorf("nach der Pause nicht erneut geladen: ok=%v, Abrufe %d", ok, w.zahlAbrufe())
	}
}

// F008: PKCE-Mindestlaenge 43 fuer Challenge und Verifier.
func TestPKCE_Mindestlaenge43(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	kurz := strings.Repeat("a", 42)
	if rec := w.authorize(http.MethodGet, zAnfrage(c, ClaudeCallback, kurz), "s1"); rec.Code != http.StatusBadRequest {
		t.Errorf("Challenge mit 42 Zeichen: %d", rec.Code)
	}
	if rec := w.authorize(http.MethodGet, zAnfrage(c, ClaudeCallback, kurz+"a"), "s1"); rec.Code != http.StatusOK {
		t.Errorf("Challenge mit 43 Zeichen: %d", rec.Code)
	}
	verifier := strings.Repeat("v", 42)
	q := zAnfrage(c, ClaudeCallback, s256(verifier))
	q.Set("aktion", "erlauben")
	loc, _ := url.Parse(w.authorize(http.MethodPost, q, "s1").Header().Get("Location"))
	form := codeForm(loc.Query().Get("code"), c, ClaudeCallback)
	form.Set("code_verifier", verifier)
	if status, f := w.token(form); status != http.StatusBadRequest || f["error"] != "invalid_grant" {
		t.Errorf("Verifier mit 42 Zeichen: %d %v", status, f)
	}
}

// F008: eine widerrufene Sitzung fuehrt zur Anmeldung, nie zur Zustimmung.
func TestAuthorize_WiderrufeneSitzung(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	q := zAnfrage(c, ClaudeCallback, s256(zVerifier))
	if err := w.s.RemoveSession("anna", "s1"); err != nil {
		t.Fatal(err)
	}
	rec := w.authorize(http.MethodGet, q, "s1")
	if rec.Code != http.StatusFound || !strings.HasPrefix(rec.Header().Get("Location"), "/login?redirect=") {
		t.Errorf("GET mit widerrufener Sitzung: %d %q", rec.Code, rec.Header().Get("Location"))
	}
	q.Set("aktion", "erlauben")
	if rec := w.authorize(http.MethodPost, q, "s1"); strings.Contains(rec.Header().Get("Location"), "code=") {
		t.Errorf("Code mit widerrufener Sitzung: %q", rec.Header().Get("Location"))
	}
}

// F008: /token nimmt nur Formulare.
func TestToken_NurFormular(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	code := w.code(c, ClaudeCallback)
	body, _ := json.Marshal(map[string]string{"grant_type": "authorization_code", "code": code, "client_id": c,
		"redirect_uri": ClaudeCallback, "code_verifier": zVerifier})
	req := httptest.NewRequest(http.MethodPost, TokenPfad+"?"+codeForm(code, c, ClaudeCallback).Encode(), strings.NewReader(string(body)))
	req.Header.Set("Content-Type", "application/json")
	rec := httptest.NewRecorder()
	w.h.Token(rec, req)
	if rec.Code != http.StatusBadRequest || !strings.Contains(rec.Body.String(), "invalid_request") {
		t.Errorf("JSON an /token: %d %s", rec.Code, rec.Body.String())
	}
}

// F008 + F010: JSON-RPC-Rahmen.
func TestJSONRPC_UngueltigeNachrichtenUndLeererBatch(t *testing.T) {
	w := neueZWelt(t)
	_, c := w.registrieren(ClaudeCallback)
	access := w.tokens(c)["access_token"].(string)
	for name, body := range map[string]string{
		"jsonrpc 1.0":    `{"jsonrpc":"1.0","id":1,"method":"ping"}`,
		"ohne jsonrpc":   `{"id":1,"method":"ping"}`,
		"leerer Batch":   `[]`,
		"method fehlt":   `{"jsonrpc":"2.0","id":1}`,
		"Batch mit Zahl": `[1]`,
	} {
		rec := w.mcp(access, body)
		var a any
		json.Unmarshal(rec.Body.Bytes(), &a)
		if liste, ok := a.([]any); ok && len(liste) == 1 {
			a = liste[0]
		}
		m, _ := a.(map[string]any)
		fehler, _ := m["error"].(map[string]any)
		if rec.Code != http.StatusOK || fehler["code"] != float64(-32600) {
			t.Errorf("%s: %d %s (erwartet -32600 Invalid Request)", name, rec.Code, rec.Body.String())
		}
	}
}
