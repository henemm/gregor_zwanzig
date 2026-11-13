package handler

// ADR-0117 Punkt 4 (#2961): Orte je Sofortvergleich hoechstens die
// Tarif-Quote. Echter Store im Temp-Verzeichnis, echte Policy-Middleware,
// Nachfolger zaehlt nur, ob er erreicht wurde. Zwei Nutzer mit verschiedenem
// Tarif, ein Admin ohne Grenze.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func vogAnlegen(t *testing.T, s *store.Store, uid, tier string, orte int) {
	t.Helper()
	if err := s.SaveUser(model.User{ID: uid, Email: uid + "@example.com", Tier: tier,
		CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser %s: %v", uid, err)
	}
	us := s.WithUser(uid)
	for i := 0; i < orte; i++ {
		if err := us.SaveLocation(model.Location{ID: fmt.Sprintf("o%d", i), Name: "Ort",
			Lat: 47, Lon: 11}); err != nil {
			t.Fatalf("SaveLocation: %v", err)
		}
	}
}

func vogAufruf(s *store.Store, admins map[string]struct{}, uid, ids string) (*httptest.ResponseRecorder, int) {
	erreicht := 0
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		erreicht++
		w.WriteHeader(http.StatusOK)
	})
	h := QuotaPolicyMiddleware(admins, nil)(VergleichOrteGrenze(s, next))
	req := httptest.NewRequest(http.MethodGet, "/api/compare?location_ids="+ids, nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec, erreicht
}

func TestVergleichOrteGrenze_ListeUeberFreeQuote422(t *testing.T) {
	s := store.New(t.TempDir(), "")
	vogAnlegen(t, s, "frieda", "free", 0)
	vogAnlegen(t, s, "stefan", "standard", 0)
	ids := make([]string, 11)
	for i := range ids {
		ids[i] = fmt.Sprintf("x%d", i)
	}

	rec, erreicht := vogAufruf(s, nil, "frieda", strings.Join(ids, ","))
	if rec.Code != http.StatusUnprocessableEntity || erreicht != 0 {
		t.Fatalf("free mit 11 Orten: Status %d, Core erreicht %d -- erwartet 422 ohne Weiterreichen",
			rec.Code, erreicht)
	}
	var body map[string]any
	_ = json.Unmarshal(rec.Body.Bytes(), &body)
	if body["code"] != "limit_exceeded" || body["limit"] != float64(10) || body["current"] != float64(11) {
		t.Errorf("Fehlerobjekt unerwartet: %v", body)
	}
	if msg, _ := body["message"].(string); !strings.Contains(msg, "10") {
		t.Errorf("Katalogtext nennt die Grenze nicht: %q", msg)
	}

	if rec, erreicht := vogAufruf(s, nil, "stefan", strings.Join(ids, ",")); rec.Code != http.StatusOK || erreicht != 1 {
		t.Errorf("standard mit 11 Orten muss durch: Status %d, erreicht %d", rec.Code, erreicht)
	}
}

func TestVergleichOrteGrenze_DoppelteUndLeereZaehlenNicht(t *testing.T) {
	s := store.New(t.TempDir(), "")
	vogAnlegen(t, s, "frieda", "free", 0)
	liste := strings.Repeat("a,", 30) + ",,b"
	if rec, erreicht := vogAufruf(s, nil, "frieda", liste); rec.Code != http.StatusOK || erreicht != 1 {
		t.Errorf("zwei verschiedene Orte: Status %d, erreicht %d", rec.Code, erreicht)
	}
}

func TestVergleichOrteGrenze_SternZaehltGespeicherteOrte(t *testing.T) {
	s := store.New(t.TempDir(), "")
	vogAnlegen(t, s, "frieda", "free", 12) // Altbestand ueber der Quote
	vogAnlegen(t, s, "fritz", "free", 3)
	if rec, erreicht := vogAufruf(s, nil, "frieda", "*"); rec.Code != http.StatusUnprocessableEntity || erreicht != 0 {
		t.Errorf("'*' mit 12 Orten bei free: Status %d, erreicht %d", rec.Code, erreicht)
	}
	if rec, erreicht := vogAufruf(s, nil, "fritz", "*"); rec.Code != http.StatusOK || erreicht != 1 {
		t.Errorf("'*' mit 3 Orten bei free: Status %d, erreicht %d", rec.Code, erreicht)
	}
	admins := map[string]struct{}{"frieda": {}}
	if rec, erreicht := vogAufruf(s, admins, "frieda", "*"); rec.Code != http.StatusOK || erreicht != 1 {
		t.Errorf("Admin ist unbegrenzt: Status %d, erreicht %d", rec.Code, erreicht)
	}
}
