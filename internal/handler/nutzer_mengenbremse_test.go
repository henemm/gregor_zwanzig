package handler

// Issue #2961: gleitendes Zeitfenster der Nutzer-Bremse (Uhr als Testnaht)
// und generischer Anbieter-Fehler in /api/forecast. Die Verdrahtung an den
// Routen pruefen internal/router/mengenbremsen_verdrahtung_test.go.

import (
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

func TestNutzerBremse_GleitendesFensterUndRetryAfter(t *testing.T) {
	uhr := time.Date(2026, 11, 12, 10, 0, 0, 0, time.UTC)
	b := NewNutzerBremse("versand", 3, time.Hour, nil)
	b.jetzt = func() time.Time { return uhr }
	ziel := 0
	h := b.Wrap(func(w http.ResponseWriter, r *http.Request) { ziel++ })

	rufe := func() *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/x", nil)
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), "anna"))
		w := httptest.NewRecorder()
		h(w, req)
		return w
	}
	for i := 0; i < 3; i++ {
		rufe()
		uhr = uhr.Add(10 * time.Minute)
	}
	// 10:30 — drei Treffer (10:00, 10:10, 10:20) im Fenster.
	w := rufe()
	if w.Code != http.StatusTooManyRequests || ziel != 3 {
		t.Fatalf("vierter Treffer: Code %d, Ziel %d mal erreicht", w.Code, ziel)
	}
	if ra := w.Header().Get("Retry-After"); ra != "1800" {
		t.Fatalf("Retry-After %q, erwartet 1800 (bis 11:00)", ra)
	}
	// 11:00:01 — der erste Treffer ist aus dem Fenster gefallen.
	uhr = time.Date(2026, 11, 12, 11, 0, 1, 0, time.UTC)
	if w := rufe(); w.Code == http.StatusTooManyRequests || ziel != 4 {
		t.Fatalf("nach Ablauf erwartet Durchlass: Code %d, Ziel %d", w.Code, ziel)
	}
}

type fehlerProvider struct{}

func (fehlerProvider) FetchForecast(lat, lon float64, hours int) (*model.Timeseries, error) {
	return nil, errors.New("GET https://intern.example/v1?key=geheim: 500 interner Upstream-Text")
}

func TestForecastHandler_AnbieterFehlerOhneRohtext(t *testing.T) {
	stub := neuerCoreStub(t)
	h := ForecastHandler(fehlerProvider{}, stub.url())
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, angemeldet("GET", "/api/forecast?lat=39.7&lon=3.0", "anna"))
	if rec.Code != http.StatusBadGateway {
		t.Fatalf("erwartet 502, bekommen %d", rec.Code)
	}
	if strings.Contains(rec.Body.String(), "geheim") || strings.Contains(rec.Body.String(), "intern.example") {
		t.Fatalf("roher Anbieter-Fehler nach aussen gegeben: %s", rec.Body.String())
	}
	if dekodiere(t, rec)["code"] != "provider_error" {
		t.Fatalf("code provider_error erwartet: %s", rec.Body.String())
	}
}
