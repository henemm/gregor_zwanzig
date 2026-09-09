package router

// TDD RED — Issue #2270, Verdrahtungs-Nachweis fuer GET /api/auth/export.
//
// Warum diese Datei zusaetzlich zu internal/handler/data_export_test.go
// existiert: die elf AC-Tests dort rufen ExportUserDataHandler(store) DIREKT
// auf. Sie bleiben deshalb alle gruen, wenn Store-Methode und Handler tadellos
// gebaut, die Zeile in internal/router/router.go aber nie gesetzt wird — der
// Endpunkt waere unerreichbar, die Ampel dennoch gruen.
//
// Genau diese Luecke ist bei #2130 (Passkey) gemessen aufgetreten: main.go und
// router.go zurueckdrehen liess `go test ./...` zu 100 % gruen. "Naht gebaut"
// ist nicht "Naht verdrahtet".
//
// Gebaut wird der ECHTE Produktions-Router (newBriefingTestRouter, dieselbe
// Deps-Verdrahtung wie cmd/server/main.go) inklusive AuthMiddleware.

import (
	"archive/zip"
	"bytes"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func TestExportRouteIstVerdrahtetUndGeschuetzt(t *testing.T) {
	r, s, secret := newBriefingTestRouter(t)

	const uid = "exportalice"
	if err := s.SaveUser(model.User{
		ID:          uid,
		DisplayName: "MARKER-route-alice-6e2b",
		CreatedAt:   time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	as := s.WithUser(uid)
	if err := as.ProvisionUserDirs(uid); err != nil {
		t.Fatalf("ProvisionUserDirs: %v", err)
	}
	if err := as.SaveLocation(model.Location{
		ID: "route-ort", Name: "MARKER-route-ort-6e2b", Lat: 47.1, Lon: 11.2,
	}); err != nil {
		t.Fatalf("SaveLocation: %v", err)
	}

	// --- 1. Route ist registriert und liefert das Archiv des ANGEMELDETEN
	//        Nutzers. Fehlt die Zeile in router.go, antwortet chi mit 404.
	req := httptest.NewRequest(http.MethodGet, "/api/auth/export", nil)
	req.AddCookie(sessionCookieFor(uid, secret))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code == http.StatusNotFound {
		t.Fatalf("VERDRAHTUNG FEHLT: GET /api/auth/export antwortet 404 — die Route ist im " +
			"Produktions-Router nicht registriert, der Endpunkt ist unerreichbar")
	}
	if w.Code != http.StatusOK {
		t.Fatalf("erwartet HTTP 200 fuer den angemeldeten Nutzer, bekommen %d: %s", w.Code, w.Body.String())
	}
	body := w.Body.Bytes()
	zr, err := zip.NewReader(bytes.NewReader(body), int64(len(body)))
	if err != nil {
		t.Fatalf("Antwort des echten Routers ist kein lesbares ZIP-Archiv (%d Bytes): %v", len(body), err)
	}
	gefunden := false
	for _, f := range zr.File {
		if f.FileInfo().IsDir() {
			continue
		}
		rc, oerr := f.Open()
		if oerr != nil {
			t.Fatalf("Archiv-Eintrag %q nicht lesbar: %v", f.Name, oerr)
		}
		buf := new(bytes.Buffer)
		_, _ = buf.ReadFrom(rc)
		rc.Close()
		if strings.Contains(buf.String(), "MARKER-route-ort-6e2b") {
			gefunden = true
		}
	}
	if !gefunden {
		t.Errorf("das ueber den echten Router ausgelieferte Archiv traegt die Daten des " +
			"angemeldeten Nutzers nicht")
	}

	// --- 2. Der Pfad steht NICHT in der Public-Allowlist der AuthMiddleware
	//        (internal/middleware/auth.go:50-63): ohne Anmelde-Merkmal 401,
	//        und ausdruecklich kein Archiv.
	reqAnon := httptest.NewRequest(http.MethodGet, "/api/auth/export", nil)
	wAnon := httptest.NewRecorder()
	r.ServeHTTP(wAnon, reqAnon)

	if wAnon.Code != http.StatusUnauthorized {
		t.Errorf("ohne Anmeldung erwartet HTTP 401, bekommen %d: %s", wAnon.Code, wAnon.Body.String())
	}
	if bytes.HasPrefix(wAnon.Body.Bytes(), []byte("PK\x03\x04")) {
		t.Errorf("ohne Anmeldung wurde ein ZIP-Archiv ausgeliefert")
	}
}
