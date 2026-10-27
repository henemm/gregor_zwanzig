package router

// Kontoloeschung im verdrahteten Router — Issue #2160, AC-1, AC-2, AC-17.
//
// Echter Produktions-Router (adminTestRouter -> router.New) inkl.
// AuthMiddleware und echten gz_session-Cookies. Die Zusicherungen liegen dort,
// wo sie WIRKEN: die alte DELETE-Route muss im Router fehlen (nicht nur im
// Handler), die Rate-Limiter haengen an den Routen.

import (
	"encoding/json"
	"net"
	"net/http"
	"strconv"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const routerPasswort = "geheim-123"

func nutzerMitPasswort(t *testing.T, s *store.Store, id string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(routerPasswort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	if err := s.SaveUser(model.User{ID: id, Email: id + "@beispiel.de", PasswordHash: string(hash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser %s: %v", id, err)
	}
	if err := s.AddSession(id, sessionIDFor(id)); err != nil {
		t.Fatalf("AddSession %s: %v", id, err)
	}
}

func kontoAnfrage(r http.Handler, secret, method, pfad, body, userID string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(method, pfad, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	if userID != "" {
		req.AddCookie(sessionCookieFor(userID, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// AC-2: der alte DELETE-Weg ist weg — er loescht nichts mehr.
func TestAlteDeleteRouteLoeschtKeinKonto(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	nutzerMitPasswort(t, s, "alice")

	w := kontoAnfrage(r, secret, http.MethodDelete, "/api/auth/account", "", "alice")
	if w.Code != http.StatusNotFound && w.Code != http.StatusMethodNotAllowed {
		t.Errorf("DELETE /api/auth/account: expected 404/405, got %d: %s", w.Code, w.Body.String())
	}
	if u, err := s.LoadUser("alice"); err != nil || u == nil {
		t.Fatal("DELETE /api/auth/account hat das Konto geloescht (Route nicht entfernt)")
	}
}

// AC-1 im Router: nur POST /api/auth/account/delete loescht, mit Nachweis.
func TestPostKontoLoeschen_ImRouter_LoeschtNurMitNachweis(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	nutzerMitPasswort(t, s, "alice")
	nutzerMitPasswort(t, s, "carol")

	if w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{"password":"falsch"}`, "alice"); w.Code != 403 {
		t.Fatalf("falsches Passwort: expected 403, got %d: %s", w.Code, w.Body.String())
	}
	if w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{}`, "alice"); w.Code != 400 {
		t.Fatalf("ohne Nachweis: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("alice"); u == nil {
		t.Fatal("alice darf ohne gueltigen Nachweis nicht geloescht sein")
	}

	w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{"password":"`+routerPasswort+`"}`, "alice")
	if w.Code != 200 || !strings.Contains(w.Body.String(), `"status":"deleted"`) {
		t.Fatalf("expected 200 deleted, got %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("alice"); u != nil {
		t.Error("alice muss geloescht sein")
	}
	if u, _ := s.LoadUser("carol"); u == nil {
		t.Error("carol darf durch alices Löschung nicht betroffen sein")
	}
}

// Beide neuen Endpunkte sind anmeldepflichtig (nicht in der Public-Allowlist).
func TestKontoLoeschEndpunkte_BrauchenAnmeldung(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "")
	for _, pfad := range []string{"/api/auth/account/delete", "/api/auth/account/delete-code"} {
		w := kontoAnfrage(r, secret, http.MethodPost, pfad, `{"password":"x"}`, "")
		if w.Code != http.StatusUnauthorized {
			t.Errorf("%s ohne Cookie: expected 401, got %d", pfad, w.Code)
		}
	}
}

// AC-17: 5 Versuche pro 15 Minuten und IP auf /account/delete, der 6. -> 429.
func TestKontoLoeschen_SechsterVersuchVonDerselbenIP_429(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "")
	nutzerMitPasswort(t, s, "alice")

	for i := 1; i <= 5; i++ {
		w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{"password":"falsch"}`, "alice")
		if w.Code != 403 {
			t.Fatalf("Versuch %d: expected 403, got %d: %s", i, w.Code, w.Body.String())
		}
	}
	w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{"password":"falsch"}`, "alice")
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("6. Versuch: expected 429, got %d: %s", w.Code, w.Body.String())
	}
	// Auch das korrekte Passwort kommt im Sperrfenster nicht durch.
	w = kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete", `{"password":"`+routerPasswort+`"}`, "alice")
	if w.Code != http.StatusTooManyRequests {
		t.Errorf("korrektes Passwort im Sperrfenster: expected 429, got %d", w.Code)
	}
	if u, _ := s.LoadUser("alice"); u == nil {
		t.Error("im Sperrfenster darf nichts geloescht werden")
	}
}

// AC-17: Mindestpause je Nutzer im verdrahteten Router — derselbe Nutzer
// fordert zweimal binnen einer Minute an, die zweite Antwort ist 429
// rate_limit_exceeded. Der Limiter steht im Handler VOR dem Versand; der
// SMTP-Host zeigt auf einen geschlossenen lokalen Port, der Versand scheitert
// also rein lokal (502), die Kontingent-Buchung ist trotzdem erfolgt. Die
// Adresse liegt zusaetzlich in einer reservierten Domain (#1477).
func TestLoeschCodeAnfordern_ZweiteAnforderungDesselbenNutzers_429(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	port := ln.Addr().(*net.TCPAddr).Port
	ln.Close()
	t.Setenv("SMTP_HOST", "127.0.0.1")
	t.Setenv("SMTP_PORT", strconv.Itoa(port))
	r, s, secret, _ := adminTestRouter(t, "")
	if err := s.SaveUser(model.User{ID: "dora", Email: "dora@example.com", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := s.AddSession("dora", sessionIDFor("dora")); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	erste := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete-code", `{}`, "dora")
	if erste.Code == http.StatusTooManyRequests || erste.Code == http.StatusNotFound {
		t.Fatalf("erste Anforderung: unerwartet %d: %s", erste.Code, erste.Body.String())
	}
	zweite := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete-code", `{}`, "dora")
	var body struct {
		Error string `json:"error"`
	}
	_ = json.Unmarshal(zweite.Body.Bytes(), &body)
	if zweite.Code != http.StatusTooManyRequests || body.Error != "rate_limit_exceeded" {
		t.Fatalf("zweite Anforderung: expected 429 rate_limit_exceeded, got %d: %s", zweite.Code, zweite.Body.String())
	}
}

// AC-17: 3 Anforderungen pro 15 Minuten und IP auf /account/delete-code, die
// 4. -> 429. Vier VERSCHIEDENE Nutzer, damit die Mindestpause je Nutzer die
// IP-Grenze nicht verdeckt.
func TestLoeschCodeAnfordern_VierteAnforderungVonDerselbenIP_429(t *testing.T) {
	t.Setenv("SMTP_HOST", "")
	r, s, secret, _ := adminTestRouter(t, "")
	ids := []string{"u1", "u2", "u3", "u4"}
	for _, id := range ids {
		nutzerMitPasswort(t, s, id)
	}
	for i, id := range ids {
		w := kontoAnfrage(r, secret, http.MethodPost, "/api/auth/account/delete-code", `{}`, id)
		if w.Code == http.StatusMethodNotAllowed || w.Code == http.StatusNotFound {
			t.Fatalf("Anforderung %d: Route /api/auth/account/delete-code fehlt (%d)", i+1, w.Code)
		}
		if i < 3 && w.Code == http.StatusTooManyRequests {
			t.Fatalf("Anforderung %d darf noch nicht 429 sein: %s", i+1, w.Body.String())
		}
		if i == 3 && w.Code != http.StatusTooManyRequests {
			t.Fatalf("4. Anforderung: expected 429, got %d: %s", w.Code, w.Body.String())
		}
	}
}
