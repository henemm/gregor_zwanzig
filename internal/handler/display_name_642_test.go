package handler

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// ============================================================================
// Issue #642 — User-Anzeigename (display_name) änderbar machen (TDD RED)
//
// Echte Handler + echter Store + echte Platte. Keine Mocks.
// Der Login-Name (User.ID) bleibt unverändert; display_name ist davon entkoppelt.
// ============================================================================

func writeUser642(t *testing.T, s *store.Store, id, raw string) string {
	t.Helper()
	dir := filepath.Join(s.DataDir, "users", id)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(raw), 0644); err != nil {
		t.Fatal(err)
	}
	return dir
}

// AC-2: PUT /api/auth/profile mit display_name => persistiert, GET liefert es zurück.
func TestUpdateProfileSetsDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := writeUser642(t, s, "hugo", `{"id":"hugo","password_hash":"`+string(hash)+`"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"display_name":"Hugo Wanderer"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "hugo"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["display_name"] != "Hugo Wanderer" {
		t.Errorf("expected display_name 'Hugo Wanderer' in response, got '%v'", resp["display_name"])
	}
	// Login-Name (id) bleibt unverändert
	if resp["id"] != "hugo" {
		t.Errorf("login id must stay 'hugo', got '%v'", resp["id"])
	}

	// Persistenz prüfen
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if !strings.Contains(string(data), `"display_name"`) || !strings.Contains(string(data), `Hugo Wanderer`) {
		t.Errorf("expected display_name persisted in user.json, got: %s", string(data))
	}
}

// AC-1/AC-3 (Datengrundlage): GET liefert gespeicherten display_name zurück.
func TestGetProfileReturnsDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	writeUser642(t, s, "iris", `{"id":"iris","password_hash":"`+string(hash)+`","display_name":"Iris vom Berg"}`)

	h := GetProfileHandler(s)
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "iris"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d", w.Code)
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["display_name"] != "Iris vom Berg" {
		t.Errorf("expected display_name 'Iris vom Berg', got '%v'", resp["display_name"])
	}
}

// AC-2 (Normalisierung): führende/abschließende Whitespaces werden getrimmt.
func TestUpdateProfileTrimsDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	writeUser642(t, s, "jan", `{"id":"jan","password_hash":"`+string(hash)+`"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"display_name":"   Jan Tal   "}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "jan"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]interface{}
	json.Unmarshal(w.Body.Bytes(), &resp)
	if resp["display_name"] != "Jan Tal" {
		t.Errorf("expected trimmed 'Jan Tal', got '%v'", resp["display_name"])
	}
}

// AC-4: leerer display_name löscht das Feld (Fallback auf Login-Name).
func TestUpdateProfileClearsDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := writeUser642(t, s, "kara", `{"id":"kara","password_hash":"`+string(hash)+`","display_name":"Alter Name"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"display_name":"   "}` // nur Whitespace => leeren
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "kara"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200 for cleared display_name, got %d: %s", w.Code, w.Body.String())
	}
	// Persistenz: alter Name weg
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if strings.Contains(string(data), "Alter Name") {
		t.Errorf("expected display_name cleared, old value still present: %s", string(data))
	}
	// GET liefert keinen/leeren display_name
	g := GetProfileHandler(s)
	gr := httptest.NewRequest("GET", "/api/auth/profile", nil)
	gr = gr.WithContext(middleware.ContextWithUserID(gr.Context(), "kara"))
	gw := httptest.NewRecorder()
	g.ServeHTTP(gw, gr)
	var resp map[string]interface{}
	json.Unmarshal(gw.Body.Bytes(), &resp)
	if v, ok := resp["display_name"]; ok && v != "" {
		t.Errorf("expected display_name absent or empty after clear, got '%v'", v)
	}
}

// AC-5: Mandantentrennung — A ändert seinen display_name, B bleibt unberührt.
func TestUpdateProfileDisplayNameIsolatedPerUser(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	writeUser642(t, s, "userA", `{"id":"userA","password_hash":"`+string(hash)+`","display_name":"A Original"}`)
	dirB := writeUser642(t, s, "userB", `{"id":"userB","password_hash":"`+string(hash)+`","display_name":"B Original"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"display_name":"A Geändert"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "userA"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	// B auf der Platte unverändert
	dataB, _ := os.ReadFile(filepath.Join(dirB, "user.json"))
	if !strings.Contains(string(dataB), "B Original") {
		t.Errorf("userB display_name must stay 'B Original', got: %s", string(dataB))
	}
	if strings.Contains(string(dataB), "A Geändert") {
		t.Errorf("userA change leaked into userB: %s", string(dataB))
	}

	// B via GET unverändert
	g := GetProfileHandler(s)
	gr := httptest.NewRequest("GET", "/api/auth/profile", nil)
	gr = gr.WithContext(middleware.ContextWithUserID(gr.Context(), "userB"))
	gw := httptest.NewRecorder()
	g.ServeHTTP(gw, gr)
	var respB map[string]interface{}
	json.Unmarshal(gw.Body.Bytes(), &respB)
	if respB["display_name"] != "B Original" {
		t.Errorf("expected userB display_name 'B Original', got '%v'", respB["display_name"])
	}
}

// AC-6: überlanger Anzeigename (>50 Zeichen) wird abgewiesen (kein 500, keine Persistenz).
func TestUpdateProfileRejectsTooLongDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := writeUser642(t, s, "lars", `{"id":"lars","password_hash":"`+string(hash)+`"}`)

	h := UpdateProfileHandler(s, config.Config{})
	tooLong := strings.Repeat("x", 51)
	body := `{"display_name":"` + tooLong + `"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "lars"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for >50 char display_name, got %d: %s", w.Code, w.Body.String())
	}
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	if strings.Contains(string(data), tooLong) {
		t.Errorf("overlong display_name must NOT be persisted: %s", string(data))
	}
}

// AC-6: Steuerzeichen/Zeilenumbruch im Anzeigenamen werden abgewiesen.
func TestUpdateProfileRejectsControlCharsInDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	writeUser642(t, s, "mona", `{"id":"mona","password_hash":"`+string(hash)+`"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"display_name":"Zeile1\nZeile2"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "mona"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("expected 400 for control chars in display_name, got %d: %s", w.Code, w.Body.String())
	}
}

// AC-7: Legacy-user.json ohne display_name — Update eines anderen Feldes (mail_to)
// erhält alle Bestandsfelder (Read-Modify-Write-Merge, kein Datenverlust).
func TestUpdateProfilePreservesFieldsWithoutDisplayName(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	dir := writeUser642(t, s, "nina",
		`{"id":"nina","password_hash":"`+string(hash)+`","mail_to":"nina@old.example","sms_to":"+49KEEPME","telegram_chat_id":"777"}`)

	h := UpdateProfileHandler(s, config.Config{})
	body := `{"mail_to":"nina@new.example"}`
	req := httptest.NewRequest("PUT", "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "nina"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	data, _ := os.ReadFile(filepath.Join(dir, "user.json"))
	var onDisk map[string]interface{}
	if err := json.Unmarshal(data, &onDisk); err != nil {
		t.Fatalf("user.json not valid JSON: %v", err)
	}
	if onDisk["mail_to"] != "nina@new.example" {
		t.Errorf("expected updated mail_to, got '%v'", onDisk["mail_to"])
	}
	if onDisk["sms_to"] != "+49KEEPME" {
		t.Errorf("sms_to must be preserved (merge), got '%v'", onDisk["sms_to"])
	}
	if onDisk["telegram_chat_id"] != "777" {
		t.Errorf("telegram_chat_id must be preserved (merge), got '%v'", onDisk["telegram_chat_id"])
	}
}
