package router

// TDD RED — Issue #2155 Scheibe S3 (Admin-API: Nutzerliste, Tier setzen,
// Konto sperren), AC-1 bis AC-9.
//
// Spec: docs/specs/modules/admin_rolle_s3_admin_api.md
//
// Echter Produktions-Router ueber adminTestRouter (admin_trigger_test.go):
// Nutzer alice, bob, ops mit Konto und gueltiger Sitzung, AuthMiddleware und
// echte gz_session-Cookies. Kein Mock.
//
// Bewusst KEIN neues Produktions-Symbol referenziert (kein model.User.Disabled,
// kein Store.SetUserDisabled, kein handler.Admin*Handler): das RED soll eine
// Verhaltens-Assertion sein, kein Uebersetzungsfehler. Gesperrt wird
// deshalb IMMER ueber das Produkt (PUT /api/admin/users/{id}/disabled) — so
// ist der Schreibweg selbst bewacht; gelesen wird das Flag roh aus user.json.
//
// Nach jedem Admin-Aufruf gilt ausserdem: der Python-Core wird NIE erreicht
// (die Admin-API ist reine Go-API).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const auPasswort = "geheim-2155-s3"

// auRuf sendet eine Anfrage mit beliebigem Rohkoerper; userID == "" heisst
// ohne Cookie.
func auRuf(t *testing.T, r http.Handler, secret, method, pfad, userID, body string) *httptest.ResponseRecorder {
	t.Helper()
	var rdr *strings.Reader
	if body == "" {
		rdr = strings.NewReader("")
	} else {
		rdr = strings.NewReader(body)
	}
	req := httptest.NewRequest(method, pfad, rdr)
	req.Header.Set("Content-Type", "application/json")
	if userID != "" {
		req.AddCookie(sessionCookieFor(userID, secret))
	}
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

// auRufMitSitzung wie auRuf, aber mit frei gewaehlter Anmelde-Kennung.
func auRufMitSitzung(t *testing.T, r http.Handler, secret, method, pfad, userID, sessionID, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(method, pfad, strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID(userID, sessionID, secret)})
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func auUserJSONPfad(s *store.Store, id string) string {
	return filepath.Join(s.UserDir(id), "user.json")
}

func auRohBytes(t *testing.T, s *store.Store, id string) []byte {
	t.Helper()
	b, err := os.ReadFile(auUserJSONPfad(s, id))
	if err != nil {
		t.Fatalf("user.json von %s nicht lesbar: %v", id, err)
	}
	return b
}

func auRohFelder(t *testing.T, s *store.Store, id string) map[string]json.RawMessage {
	t.Helper()
	var m map[string]json.RawMessage
	if err := json.Unmarshal(auRohBytes(t, s, id), &m); err != nil {
		t.Fatalf("user.json von %s ist kein JSON-Objekt: %v", id, err)
	}
	return m
}

// auRohGesperrt liest das Flag "disabled" ROH aus user.json (fehlt == false).
func auRohGesperrt(t *testing.T, s *store.Store, id string) bool {
	t.Helper()
	raw, ok := auRohFelder(t, s, id)["disabled"]
	if !ok {
		return false
	}
	var v bool
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatalf("user.json von %s: disabled ist kein bool: %s", id, raw)
	}
	return v
}

// auMitPasswort legt ein Konto mit bcrypt-Hash und bestaetigter Adresse an —
// sonst stoppt der Login am Bestaetigungs-Gate (#2271) statt an der Sperre.
func auMitPasswort(t *testing.T, s *store.Store, id string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(auPasswort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	jetzt := time.Now().UTC()
	if err := s.SaveUser(model.User{
		ID: id, Email: id + "@example.org", PasswordHash: string(hash),
		EmailVerifiedAt: &jetzt, CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser %s: %v", id, err)
	}
}

func auLogin(t *testing.T, r http.Handler, id, passwort string) *httptest.ResponseRecorder {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"username": id, "password": passwort})
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func auSessionCookie(w *httptest.ResponseRecorder) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" && c.MaxAge >= 0 {
			return c
		}
	}
	return nil
}

func auSperren(t *testing.T, r http.Handler, secret, admin, ziel string, gesperrt bool) *httptest.ResponseRecorder {
	t.Helper()
	body := `{"disabled":false}`
	if gesperrt {
		body = `{"disabled":true}`
	}
	return auRuf(t, r, secret, http.MethodPut, "/api/admin/users/"+ziel+"/disabled", admin, body)
}

// auListe ruft GET /api/admin/users als admin und liefert die Eintraege je id.
func auListe(t *testing.T, r http.Handler, secret, admin string) (map[string]map[string]json.RawMessage, string) {
	t.Helper()
	w := auRuf(t, r, secret, http.MethodGet, "/api/admin/users", admin, "")
	if w.Code != http.StatusOK {
		t.Fatalf("GET /api/admin/users als %s: erwartet 200, bekommen %d: %s", admin, w.Code, w.Body.String())
	}
	var body struct {
		Users []map[string]json.RawMessage `json:"users"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Liste ist kein JSON {users:[...]}: %v — %s", err, w.Body.String())
	}
	out := map[string]map[string]json.RawMessage{}
	for _, u := range body.Users {
		var id string
		_ = json.Unmarshal(u["id"], &id)
		out[id] = u
	}
	return out, w.Body.String()
}

func auAssertJSONFehler(t *testing.T, w *httptest.ResponseRecorder, wantCode int, wantBody, kontext string) {
	t.Helper()
	if w.Code != wantCode {
		t.Errorf("%s: erwartet %d, bekommen %d: %s", kontext, wantCode, w.Code, w.Body.String())
		return
	}
	if wantBody != "" {
		if got := strings.TrimSpace(w.Body.String()); got != wantBody {
			t.Errorf("%s: Body erwartet %s, bekommen %q", kontext, wantBody, got)
		}
	}
	if ct := w.Header().Get("Content-Type"); !strings.HasPrefix(ct, "application/json") {
		t.Errorf("%s: Content-Type erwartet application/json, bekommen %q", kontext, ct)
	}
}

// ---------------------------------------------------------------------------
// AC-1: ohne Sitzung 401, Nicht-Admin 403 forbidden — auf allen drei Routen,
// kein Datensatz aendert sich. Der Admin im selben Lauf erreicht die Liste.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC1_AnonymousAndNonAdminRejected_OnAllThreeRoutes(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "alice")

	vorher := map[string][]byte{}
	for _, id := range []string{"alice", "bob", "ops"} {
		vorher[id] = auRohBytes(t, s, id)
	}

	routen := []struct{ method, pfad, body string }{
		{http.MethodGet, "/api/admin/users", ""},
		{http.MethodPut, "/api/admin/users/alice/tier", `{"tier":"premium"}`},
		{http.MethodPut, "/api/admin/users/alice/disabled", `{"disabled":true}`},
	}
	for _, rt := range routen {
		anon := auRuf(t, r, secret, rt.method, rt.pfad, "", rt.body)
		if anon.Code != http.StatusUnauthorized {
			t.Errorf("AC-1 anonym %s %s: erwartet 401, bekommen %d", rt.method, rt.pfad, anon.Code)
		}
		bob := auRuf(t, r, secret, rt.method, rt.pfad, "bob", rt.body)
		auAssertJSONFehler(t, bob, http.StatusForbidden, `{"error":"forbidden"}`,
			"AC-1 Nicht-Admin bob "+rt.method+" "+rt.pfad)
	}

	for id, alt := range vorher {
		if neu := auRohBytes(t, s, id); !bytes.Equal(alt, neu) {
			t.Errorf("AC-1: user.json von %s wurde durch abgewiesene Aufrufe veraendert:\nvorher %s\nnachher %s", id, alt, neu)
		}
	}

	// Positivkontrolle im selben Lauf: die Route existiert und der Admin kommt durch.
	if w := auRuf(t, r, secret, http.MethodGet, "/api/admin/users", "alice", ""); w.Code != http.StatusOK {
		t.Errorf("AC-1 Admin alice GET /api/admin/users: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-1: die Admin-API darf den Python-Core nie erreichen, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-2: Liste mit allen DTO-Feldern, ohne Geheimnisse im Rohtext.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC2_ListHasDTOFields_AndLeaksNoSecrets(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "alice")

	// alice und bob mit Passwort-Hash UND Passkey-Daten; bob mit offenem Antrag.
	credID := []byte("CRED-ID-2155-S3-GEHEIM")
	pubKey := []byte("PUBKEY-2155-S3-GEHEIM")
	hashes := map[string]string{}
	for _, id := range []string{"alice", "bob"} {
		hash, _ := bcrypt.GenerateFromPassword([]byte(auPasswort+id), bcrypt.MinCost)
		hashes[id] = string(hash)
		verifiziert := time.Date(2026, 9, 1, 10, 0, 0, 0, time.UTC)
		u := model.User{
			ID: id, Email: id + "@example.org", DisplayName: strings.ToUpper(id[:1]) + id[1:],
			PasswordHash: string(hash), EmailVerifiedAt: &verifiziert,
			CreatedAt: time.Date(2026, 9, 1, 9, 58, 0, 0, time.UTC), Tier: "free",
			PasskeyCredentials: []model.WebAuthnCredential{{
				ID: append([]byte(nil), credID...), PublicKey: pubKey,
				AttestationType: "none", CreatedAt: time.Now().UTC(),
			}},
		}
		if id == "bob" {
			antrag := time.Date(2026, 9, 20, 8, 0, 0, 0, time.UTC)
			u.RequestedTier = "premium"
			u.RequestedAt = &antrag
		}
		if err := s.SaveUser(u); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
	}

	liste, roh := auListe(t, r, secret, "alice")

	if len(liste) != 3 || liste["alice"] == nil || liste["bob"] == nil || liste["ops"] == nil {
		t.Fatalf("AC-2: Liste muss exakt {alice, bob, ops} enthalten, bekommen %v — %s", keysOf(liste), roh)
	}

	pflicht := []string{"id", "email", "display_name", "tier", "requested_tier", "requested_at",
		"email_verified_at", "created_at", "disabled", "is_test_user", "last_trip_report_run"}
	for id, eintrag := range liste {
		for _, feld := range pflicht {
			if _, ok := eintrag[feld]; !ok {
				t.Errorf("AC-2: Eintrag %s ohne Pflichtfeld %q (kein omitempty im DTO): %v", id, feld, keysOf2(eintrag))
			}
		}
		if lr, ok := eintrag["last_trip_report_run"]; ok && string(lr) != "null" {
			t.Errorf("AC-2: %s hat keinen Lauf — last_trip_report_run muss null sein, ist %s", id, lr)
		}
		if d, ok := eintrag["disabled"]; ok && string(d) != "false" {
			t.Errorf("AC-2: %s ist nicht gesperrt — disabled muss false sein, ist %s", id, d)
		}
	}
	if bob := liste["bob"]; bob != nil {
		if string(bob["requested_tier"]) != `"premium"` {
			t.Errorf("AC-2: bob requested_tier erwartet \"premium\", bekommen %s", bob["requested_tier"])
		}
		if string(bob["email"]) != `"bob@example.org"` {
			t.Errorf("AC-2: bob email erwartet \"bob@example.org\", bekommen %s", bob["email"])
		}
	}

	// Rohtext: keine Geheimnisse, weder als Feldname noch als Wert.
	low := strings.ToLower(roh)
	for _, verboten := range []string{"password_hash", "passkey", "token", "code_hash", "\"code\"", "public_key"} {
		if strings.Contains(low, verboten) {
			t.Errorf("AC-2: Rohtext der Liste enthaelt %q — %s", verboten, roh)
		}
	}
	for id, h := range hashes {
		if strings.Contains(roh, h) {
			t.Errorf("AC-2: Rohtext enthaelt den bcrypt-Hash von %s", id)
		}
	}
	credB64, _ := json.Marshal(credID) // []byte -> base64-String
	if strings.Contains(roh, strings.Trim(string(credB64), `"`)) {
		t.Errorf("AC-2: Rohtext enthaelt die Passkey-Credential-ID")
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-2: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

func keysOf(m map[string]map[string]json.RawMessage) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

func keysOf2(m map[string]json.RawMessage) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

// ---------------------------------------------------------------------------
// AC-3: Tier setzen = Roh-Merge; requested_tier UND requested_at weg,
// Zusatzfeld bleibt, bob unveraendert.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC3_SetTier_ClearsRequest_KeepsUnknownField_OtherUserUntouched(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")

	antrag := time.Date(2026, 9, 20, 8, 0, 0, 0, time.UTC)
	if err := s.SaveUser(model.User{
		ID: "alice", Email: "alice@example.org", Tier: "free",
		RequestedTier: "premium", RequestedAt: &antrag, CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser alice: %v", err)
	}
	// Unbekanntes Zusatzfeld ROH einfuegen (typisiertes Modell kennt es nicht).
	felder := auRohFelder(t, s, "alice")
	zusatz := json.RawMessage(`{"herkunft":"altbestand","n":7}`)
	felder["zz_unbekannt_2155"] = zusatz
	out, _ := json.MarshalIndent(felder, "", "  ")
	if err := os.WriteFile(auUserJSONPfad(s, "alice"), out, 0644); err != nil {
		t.Fatalf("Zusatzfeld schreiben: %v", err)
	}

	if err := s.SaveUser(model.User{ID: "bob", Tier: "standard", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser bob: %v", err)
	}
	bobVorher := auRohBytes(t, s, "bob")

	w := auRuf(t, r, secret, http.MethodPut, "/api/admin/users/alice/tier", "ops", `{"tier":"premium"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3: PUT tier erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var eintrag map[string]json.RawMessage
	if err := json.Unmarshal(w.Body.Bytes(), &eintrag); err != nil {
		t.Fatalf("AC-3: Antwort ist kein Listeneintrag: %v — %s", err, w.Body.String())
	}
	if string(eintrag["id"]) != `"alice"` || string(eintrag["tier"]) != `"premium"` {
		t.Errorf("AC-3: Antwort muss der aktualisierte Eintrag von alice sein (tier premium), bekommen %s", w.Body.String())
	}

	nachher := auRohFelder(t, s, "alice")
	if string(nachher["tier"]) != `"premium"` {
		t.Errorf("AC-3: user.json tier erwartet \"premium\", ist %s", nachher["tier"])
	}
	if v, ok := nachher["requested_tier"]; ok {
		t.Errorf("AC-3: requested_tier muss aus user.json entfernt sein, steht noch: %s", v)
	}
	if v, ok := nachher["requested_at"]; ok {
		t.Errorf("AC-3: requested_at muss aus user.json entfernt sein, steht noch: %s", v)
	}
	var kompaktAlt, kompaktNeu bytes.Buffer
	_ = json.Compact(&kompaktAlt, zusatz)
	if v, ok := nachher["zz_unbekannt_2155"]; !ok {
		t.Errorf("AC-3: unbekanntes Zusatzfeld ging verloren (Replace statt Roh-Merge)")
	} else {
		_ = json.Compact(&kompaktNeu, v)
		if kompaktAlt.String() != kompaktNeu.String() {
			t.Errorf("AC-3: Zusatzfeld veraendert: vorher %s, nachher %s", kompaktAlt.String(), kompaktNeu.String())
		}
	}
	if string(nachher["email"]) != `"alice@example.org"` {
		t.Errorf("AC-3: Bestandsfeld email veraendert: %s", nachher["email"])
	}
	if bobNachher := auRohBytes(t, s, "bob"); !bytes.Equal(bobVorher, bobNachher) {
		t.Errorf("AC-3: user.json von bob wurde veraendert:\nvorher %s\nnachher %s", bobVorher, bobNachher)
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-3: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-4: ungueltiges Tier / kaputtes JSON => 400; unbekannte bzw.
// Path-Traversal-ID => 404 (JSON, nicht der Text-404 des Routers); nichts
// geschrieben.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC4_InvalidTierOrBody_400_UnknownOrTraversalID_404_NothingWritten(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")
	vorher := map[string][]byte{}
	for _, id := range []string{"alice", "bob", "ops"} {
		vorher[id] = auRohBytes(t, s, id)
	}

	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/alice/tier", "ops", `{"tier":"gold"}`),
		http.StatusBadRequest, "", "AC-4 tier gold")
	// Exakte Whitelist: auch Gross-/Kleinschreibung zaehlt (kein EffectiveTier-Fallback).
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/alice/tier", "ops", `{"tier":"Premium"}`),
		http.StatusBadRequest, "", "AC-4 tier Premium (Grossschreibung)")
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/alice/tier", "ops", `{"tier":`),
		http.StatusBadRequest, "", "AC-4 kaputtes JSON (tier)")
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/alice/disabled", "ops", `{"disabled":`),
		http.StatusBadRequest, "", "AC-4 kaputtes JSON (disabled)")

	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/niemand/tier", "ops", `{"tier":"premium"}`),
		http.StatusNotFound, "", "AC-4 unbekannte ID (tier)")
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/niemand/disabled", "ops", `{"disabled":true}`),
		http.StatusNotFound, "", "AC-4 unbekannte ID (disabled)")
	// Kodierte Traversal-ID: erreicht das {id}-Segment (unkodiert "../x" wuerde
	// schon der Router als eigenes Segment verwerfen und bewiese nichts).
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/..%2Fx/tier", "ops", `{"tier":"premium"}`),
		http.StatusNotFound, "", "AC-4 Path-Traversal-ID (tier)")
	auAssertJSONFehler(t, auRuf(t, r, secret, http.MethodPut, "/api/admin/users/..%2Fx/disabled", "ops", `{"disabled":true}`),
		http.StatusNotFound, "", "AC-4 Path-Traversal-ID (disabled)")

	for id, alt := range vorher {
		if neu := auRohBytes(t, s, id); !bytes.Equal(alt, neu) {
			t.Errorf("AC-4: user.json von %s wurde trotz Ablehnung veraendert", id)
		}
	}
	for _, p := range []string{
		filepath.Join(s.DataDir, "users", "niemand"),
		filepath.Join(s.DataDir, "x"),
		filepath.Join(s.DataDir, "users", "x"),
	} {
		if _, err := os.Stat(p); err == nil {
			t.Errorf("AC-4: abgelehnter Aufruf hat %s angelegt", p)
		}
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-4: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-5: Sperren widerruft die bestehende Sitzung sofort; bob unberuehrt.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC5_Disable_RevokesExistingSession_OtherUserUntouched(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")

	// Vorbedingung: beide Sitzungen sind gueltig.
	for _, id := range []string{"alice", "bob"} {
		if w := auRuf(t, r, secret, http.MethodGet, "/api/auth/profile", id, ""); w.Code != http.StatusOK {
			t.Fatalf("Vorbedingung: %s GET /api/auth/profile erwartet 200, bekommen %d", id, w.Code)
		}
	}

	w := auSperren(t, r, secret, "ops", "alice", true)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-5: Sperren erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var eintrag map[string]json.RawMessage
	if err := json.Unmarshal(w.Body.Bytes(), &eintrag); err != nil || string(eintrag["disabled"]) != "true" {
		t.Errorf("AC-5: Antwort muss der Eintrag mit disabled:true sein, bekommen %s", w.Body.String())
	}

	if w := auRuf(t, r, secret, http.MethodGet, "/api/auth/profile", "alice", ""); w.Code != http.StatusUnauthorized {
		t.Errorf("AC-5: bisherige Sitzung von alice muss sofort 401 liefern, bekommen %d", w.Code)
	}
	if w := auRuf(t, r, secret, http.MethodGet, "/api/auth/profile", "bob", ""); w.Code != http.StatusOK {
		t.Errorf("AC-5: bob mit eigener Sitzung muss unberuehrt bleiben (200), bekommen %d", w.Code)
	}
	if sess, err := s.LoadSessions("alice"); err != nil || len(sess) != 0 {
		t.Errorf("AC-5: Gaesteliste von alice muss leer sein, ist %v (err %v)", sess, err)
	}
	if sess, _ := s.LoadSessions("bob"); len(sess) != 1 {
		t.Errorf("AC-5: Gaesteliste von bob muss unveraendert 1 Eintrag haben, hat %d", len(sess))
	}
	if !auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-5: user.json von alice muss disabled:true tragen")
	}
	if auRohGesperrt(t, s, "bob") {
		t.Errorf("AC-5: bob darf nicht gesperrt sein")
	}

	liste, roh := auListe(t, r, secret, "ops")
	if a := liste["alice"]; a == nil || string(a["disabled"]) != "true" {
		t.Errorf("AC-5: Liste muss alice mit disabled:true zeigen — %s", roh)
	}
	if b := liste["bob"]; b == nil || string(b["disabled"]) != "false" {
		t.Errorf("AC-5: Liste muss bob mit disabled:false zeigen — %s", roh)
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-5: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-6: Reihenfolge Flag-vor-Clear; ClearSessions scheitert => 500, Flag
// bleibt; Wiederholung idempotent 200.
//
// Fehlerinjektion: sessions.json wird durch ein (nicht leeres) VERZEICHNIS
// ersetzt. writeFileAtomic benennt die tmp-Datei auf diesen Pfad um — das
// scheitert (EISDIR) auch als root, waehrend user.json im selben
// Nutzerordner weiter schreibbar bleibt. Ein schreibgeschuetzter Ordner
// taugte hier nicht: user.json und sessions.json teilen sich UserDir, der
// Flag-Schreibvorgang scheiterte mit.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC6_FlagBeforeClear_ClearFails500_FlagStays_RetryIdempotent(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")

	sessPfad := filepath.Join(s.UserDir("alice"), "sessions.json")
	if err := os.Remove(sessPfad); err != nil {
		t.Fatalf("sessions.json entfernen: %v", err)
	}
	if err := os.MkdirAll(filepath.Join(sessPfad, "blockade"), 0755); err != nil {
		t.Fatalf("Fehlerinjektion anlegen: %v", err)
	}

	w := auSperren(t, r, secret, "ops", "alice", true)
	if w.Code != http.StatusInternalServerError {
		t.Errorf("AC-6: scheiternder Sitzungs-Widerruf muss 500 liefern, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-6: das Flag muss VOR ClearSessions gesetzt sein und nach dessen Fehlschlag gesetzt bleiben — user.json: %s",
			auRohBytes(t, s, "alice"))
	}

	if err := os.RemoveAll(sessPfad); err != nil {
		t.Fatalf("Fehlerinjektion entfernen: %v", err)
	}
	w2 := auSperren(t, r, secret, "ops", "alice", true)
	if w2.Code != http.StatusOK {
		t.Errorf("AC-6: Wiederholung muss idempotent 200 liefern, bekommen %d: %s", w2.Code, w2.Body.String())
	}
	if !auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-6: nach der Wiederholung muss alice gesperrt sein")
	}
	if fi, err := os.Stat(sessPfad); err == nil && fi.IsDir() {
		t.Errorf("AC-6: sessions.json ist nach der Wiederholung noch ein Verzeichnis")
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-6: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-7: gesperrt + richtiges Passwort => 403 account_disabled, kein Cookie;
// falsches Passwort bleibt 401 (kein Hinweis auf die Sperre).
// ---------------------------------------------------------------------------

func TestAdminUsers_AC7_DisabledLogin_403WithoutCookie_WrongPasswordStays401(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")
	auMitPasswort(t, s, "alice")
	auMitPasswort(t, s, "bob")

	// Vorbedingung: Login funktioniert vor der Sperre.
	if w := auLogin(t, r, "alice", auPasswort); w.Code != http.StatusOK {
		t.Fatalf("Vorbedingung: Login alice vor der Sperre erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	if w := auSperren(t, r, secret, "ops", "alice", true); w.Code != http.StatusOK {
		t.Fatalf("AC-7: Sperren erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	w := auLogin(t, r, "alice", auPasswort)
	auAssertJSONFehler(t, w, http.StatusForbidden, `{"error":"account_disabled"}`, "AC-7 gesperrt, richtiges Passwort")
	if c := auSessionCookie(w); c != nil {
		t.Errorf("AC-7: gesperrter Login darf kein gz_session-Cookie setzen, bekommen %q", c.Value)
	}
	if sess, _ := s.LoadSessions("alice"); len(sess) != 0 {
		t.Errorf("AC-7: gesperrter Login darf keine Sitzung eintragen, Gaesteliste hat %d", len(sess))
	}

	falsch := auLogin(t, r, "alice", "falsch-falsch")
	auAssertJSONFehler(t, falsch, http.StatusUnauthorized, `{"error":"invalid credentials"}`, "AC-7 gesperrt, falsches Passwort")

	// Zwei-Nutzer-Gegenprobe: bob meldet sich normal an.
	if w := auLogin(t, r, "bob", auPasswort); w.Code != http.StatusOK || auSessionCookie(w) == nil {
		t.Errorf("AC-7: bob (nicht gesperrt) muss sich normal anmelden (200 + Cookie), bekommen %d", w.Code)
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-7: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-8 (Teil 1): der Profil-PUT kann das Flag weder zuruecksetzen noch setzen.
//
// Nach dem Sperren hat alice keine Sitzung mehr; um den Profil-PUT eines
// gesperrten Kontos ueberhaupt zu erreichen (Lost-Update-Fenster), erhaelt
// alice hier direkt im Store eine zweite Anmelde-Kennung.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC8_ProfilePut_CannotResetOrSetDisabled(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")

	if w := auSperren(t, r, secret, "ops", "alice", true); w.Code != http.StatusOK {
		t.Fatalf("AC-8: Sperren erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	const zweiteSitzung = "sess-alice-nach-sperre"
	if err := s.AddSession("alice", zweiteSitzung); err != nil {
		t.Fatalf("AddSession: %v", err)
	}

	w := auRufMitSitzung(t, r, secret, http.MethodPut, "/api/auth/profile", "alice", zweiteSitzung,
		`{"display_name":"Alice Neu","disabled":false}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: Profil-PUT von alice erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if !auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-8: Profil-PUT mit disabled:false hat die Sperre zurueckgesetzt — user.json: %s", auRohBytes(t, s, "alice"))
	}
	if string(auRohFelder(t, s, "alice")["display_name"]) != `"Alice Neu"` {
		t.Errorf("AC-8: Vorbedingung — der Profil-PUT muss den Anzeigenamen geschrieben haben")
	}

	// "kein Setzen" (Regressionswaechter, heute schon gruen): bob sperrt sich
	// nicht selbst ueber das Profil.
	wb := auRuf(t, r, secret, http.MethodPut, "/api/auth/profile", "bob", `{"display_name":"Bob","disabled":true}`)
	if wb.Code != http.StatusOK {
		t.Fatalf("AC-8: Profil-PUT von bob erwartet 200, bekommen %d: %s", wb.Code, wb.Body.String())
	}
	if auRohGesperrt(t, s, "bob") {
		t.Errorf("AC-8: Profil-PUT mit disabled:true darf das Flag nicht setzen")
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-8: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-8 (Teil 2): Entsperren => Login wieder 200, die alte Sitzung bleibt 401.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC8_Enable_LoginWorksAgain_OldSessionStays401(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops")
	auMitPasswort(t, s, "alice")

	if w := auSperren(t, r, secret, "ops", "alice", true); w.Code != http.StatusOK {
		t.Fatalf("AC-8: Sperren erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if w := auLogin(t, r, "alice", auPasswort); w.Code != http.StatusForbidden {
		t.Errorf("AC-8: Vorbedingung — gesperrter Login erwartet 403, bekommen %d", w.Code)
	}

	we := auSperren(t, r, secret, "ops", "alice", false)
	if we.Code != http.StatusOK {
		t.Fatalf("AC-8: Entsperren erwartet 200, bekommen %d: %s", we.Code, we.Body.String())
	}
	if auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-8: nach dem Entsperren darf user.json kein disabled:true mehr tragen")
	}

	w := auLogin(t, r, "alice", auPasswort)
	if w.Code != http.StatusOK || auSessionCookie(w) == nil {
		t.Errorf("AC-8: nach dem Entsperren muss der Login wieder 200 + Cookie liefern, bekommen %d: %s", w.Code, w.Body.String())
	}
	// Die Fixture-Sitzung sess-alice (vor der Sperre) wird NICHT wiederhergestellt.
	if w := auRuf(t, r, secret, http.MethodGet, "/api/auth/profile", "alice", ""); w.Code != http.StatusUnauthorized {
		t.Errorf("AC-8: die alte Sitzung von vor der Sperre muss 401 bleiben, bekommen %d", w.Code)
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-8: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}

// ---------------------------------------------------------------------------
// AC-9: Selbstsperre 409, eigenes Entsperren idempotent 200, anderer Admin
// sperrbar 200.
// ---------------------------------------------------------------------------

func TestAdminUsers_AC9_SelfDisable409_SelfEnableIdempotent_OtherAdminDisableable(t *testing.T) {
	r, s, secret, ziel := adminTestRouter(t, "ops,alice")
	opsVorher := auRohBytes(t, s, "ops")

	w := auSperren(t, r, secret, "ops", "ops", true)
	auAssertJSONFehler(t, w, http.StatusConflict, `{"error":"cannot_disable_self"}`, "AC-9 Selbstsperre")
	if auRohGesperrt(t, s, "ops") {
		t.Errorf("AC-9: Selbstsperre darf das Flag nicht setzen")
	}
	if !bytes.Equal(opsVorher, auRohBytes(t, s, "ops")) {
		t.Errorf("AC-9: user.json von ops wurde durch die abgewiesene Selbstsperre veraendert")
	}
	if w := auRuf(t, r, secret, http.MethodGet, "/api/auth/profile", "ops", ""); w.Code != http.StatusOK {
		t.Errorf("AC-9: die Sitzung des Admins muss nach abgewiesener Selbstsperre gueltig bleiben, bekommen %d", w.Code)
	}

	if w := auSperren(t, r, secret, "ops", "ops", false); w.Code != http.StatusOK {
		t.Errorf("AC-9: eigenes Entsperren muss idempotent 200 liefern, bekommen %d: %s", w.Code, w.Body.String())
	}

	if w := auSperren(t, r, secret, "ops", "alice", true); w.Code != http.StatusOK {
		t.Errorf("AC-9: ein anderer Admin (alice) muss sperrbar sein (200), bekommen %d: %s", w.Code, w.Body.String())
	}
	if !auRohGesperrt(t, s, "alice") {
		t.Errorf("AC-9: alice muss nach dem Sperren disabled:true tragen")
	}
	if got := ziel.gesamt(); got != 0 {
		t.Errorf("AC-9: Python-Core darf nicht erreicht werden, Zaehler=%d", got)
	}
}
