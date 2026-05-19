package handler

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

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

// AC-1: POST setzt created_at automatisch server-seitig
func TestCreateLocationHandlerSetsCreatedAt(t *testing.T) {
	s := newTestStore(t)

	body := `{"name":"Timestamp Test","lat":47.5,"lon":11.5}`

	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	createdAt, ok := resp["created_at"]
	if !ok || createdAt == nil || createdAt == "" {
		t.Fatalf("expected non-empty created_at in response, got %v", createdAt)
	}

	createdAtStr, ok := createdAt.(string)
	if !ok {
		t.Fatalf("expected created_at to be a string, got %T", createdAt)
	}
	parsed, err := time.Parse(time.RFC3339, createdAtStr)
	if err != nil {
		t.Fatalf("expected created_at to be RFC3339, got %q: %v", createdAtStr, err)
	}
	if since := time.Since(parsed); since < 0 || since >= 5*time.Second {
		t.Fatalf("expected created_at within last 5 seconds, got %v ago", since)
	}
}

// AC-2: Timezone und DataSource werden korrekt persistiert und zurückgegeben
func TestCreateLocationHandlerWithTimezoneAndDataSource(t *testing.T) {
	s := newTestStore(t)

	body := `{"name":"TZ Test","lat":47.5,"lon":11.5,"timezone":"Europe/Berlin","data_source":"dwd_icon"}`

	h := CreateLocationHandler(s)
	req := httptest.NewRequest("POST", "/api/locations", strings.NewReader(body))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 201 {
		t.Fatalf("expected 201, got %d: %s", w.Code, w.Body.String())
	}

	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["timezone"] != "Europe/Berlin" {
		t.Errorf("expected timezone 'Europe/Berlin', got %v", resp["timezone"])
	}
	if resp["data_source"] != "dwd_icon" {
		t.Errorf("expected data_source 'dwd_icon', got %v", resp["data_source"])
	}
}

// AC-3: PUT bewahrt created_at aus dem Bestandsdatensatz
func TestUpdateLocationHandlerPreservesCreatedAt(t *testing.T) {
	s := newTestStore(t)

	// 1. Location via POST anlegen, damit CreatedAt server-seitig gesetzt wird
	createBody := `{"id":"with-ts","name":"With Timestamp","lat":47.0,"lon":11.0}`
	createHandler := CreateLocationHandler(s)
	createReq := httptest.NewRequest("POST", "/api/locations", strings.NewReader(createBody))
	createW := httptest.NewRecorder()
	createHandler.ServeHTTP(createW, createReq)

	if createW.Code != 201 {
		t.Fatalf("setup: expected 201 on POST, got %d: %s", createW.Code, createW.Body.String())
	}

	// 2. CreatedAt aus Response lesen
	var createResp map[string]interface{}
	if err := json.Unmarshal(createW.Body.Bytes(), &createResp); err != nil {
		t.Fatalf("setup: failed to parse POST response: %v", err)
	}
	originalStr, ok := createResp["created_at"].(string)
	if !ok || originalStr == "" {
		t.Fatalf("setup: expected non-empty created_at string in POST response, got %v", createResp["created_at"])
	}
	original, err := time.Parse(time.RFC3339, originalStr)
	if err != nil {
		t.Fatalf("setup: failed to parse original created_at %q: %v", originalStr, err)
	}

	// 3. PUT ohne created_at im Body senden
	updateBody := `{"name":"Updated Name","lat":47.5,"lon":11.5}`

	r := chi.NewRouter()
	r.Put("/api/locations/{id}", UpdateLocationHandler(s))

	req := httptest.NewRequest("PUT", "/api/locations/with-ts", strings.NewReader(updateBody))
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// 4. Location aus Store laden
	loaded, err := s.LoadLocation("with-ts")
	if err != nil {
		t.Fatalf("LoadLocation failed: %v", err)
	}
	if loaded == nil {
		t.Fatal("expected loaded location, got nil")
	}

	// 5. Assert: CreatedAt bleibt erhalten und entspricht dem Original
	if loaded.CreatedAt == nil {
		t.Fatal("expected CreatedAt to be preserved, got nil")
	}
	if !loaded.CreatedAt.Equal(original) {
		t.Fatalf("expected CreatedAt %v, got %v", original, *loaded.CreatedAt)
	}
}
