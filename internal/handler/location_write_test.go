package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/go-chi/chi/v5"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func seedLocation(t *testing.T, s *store.Store, id, name string) {
	loc := model.Location{ID: id, Name: name, Lat: 47.0, Lon: 11.0}
	s.SaveLocation(loc)
}

func TestCreateLocationHandler(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"new-loc","name":"New Location","lat":47.5,"lon":11.5}`

	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["id"] != "new-loc" {
		t.Errorf("expected id new-loc, got %v", resp["id"])
	}
}

func TestCreateLocationHandlerInvalidName(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"no-name","lat":47.0,"lon":11.0}`

	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
}

func TestCreateLocationHandlerZeroCoords(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"zero","name":"Zero","lat":0,"lon":0}`

	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for zero coords, got %d", w.Code)
	}
}

func TestUpdateLocationHandler(t *testing.T) {
	s := newTestStore(t)
	seedLocation(t, s, "existing", "Old Name")

	body := `{"id":"existing","name":"Updated","lat":47.5,"lon":11.5}`

	r := chi.NewRouter()
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))

	req := httptest.NewRequest("PUT", "/api/locations/existing", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

func TestUpdateLocationHandlerNotFound(t *testing.T) {
	s := newTestStore(t)

	body := `{"id":"ghost","name":"Ghost","lat":47.0,"lon":11.0}`

	r := chi.NewRouter()
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))

	req := httptest.NewRequest("PUT", "/api/locations/ghost", strings.NewReader(body))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 404 {
		t.Fatalf("expected 404, got %d", w.Code)
	}
}

func TestDeleteLocationHandler(t *testing.T) {
	s := newTestStore(t)
	seedLocation(t, s, "to-delete", "Delete Me")

	r := chi.NewRouter()
	r.Delete("/api/locations/{id}", DeleteLocationHandler(s))

	req := httptest.NewRequest("DELETE", "/api/locations/to-delete", nil)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 204 {
		t.Fatalf("expected 204, got %d", w.Code)
	}
}
