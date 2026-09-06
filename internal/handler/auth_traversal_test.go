package handler

import (
	"bytes"
	"encoding/json"
	"io/fs"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// TDD RED — Issue #2140 Scheibe 1 (Nutzer-Achse). SPEC:
// docs/specs/modules/fix_2140_pfad_traversal_nutzer_kennung.md
//
// Diese Tests belegen, dass die vier oeffentlichen Auth-Routen eine
// Pfad-Traversal-Kennung (z.B. "../marker") heute UNGEPRUEFT an
// Store.UserDir(id) durchreichen, wodurch Store-Operationen ausserhalb des
// data/users/-Baums greifen. Sie muessen gegen den UNVERAENDERTEN
// Produktivcode fehlschlagen.
//
// Methodik: weil filepath.Join("<DataDir>/users", "../marker") NACH "users"
// zurueckspringt und bei "<DataDir>/marker" landet (Geschwister-Verzeichnis
// von "users", NICHT innerhalb eines existierenden Nutzers), wird der reale
// Ziel-Pfad ueber die exportierte Methode s.UserDir(id) ermittelt und dort
// gezielt ein "Opfer"-Datensatz platziert. Das bildet exakt den im Kontext-
// Dokument beschriebenen Laufzeit-Nachweis nach (Token/Datei ausserhalb des
// Nutzerbaums).

// writeJSONFile schreibt beliebige Rohdaten an einen Pfad, legt das
// Verzeichnis bei Bedarf an. Wird genutzt, um "Opfer"-Dateien AUSSERHALB des
// von Store vorgesehenen data/users/-Baums zu platzieren (simuliert, was ein
// Traversal-Angriff dort vorfinden bzw. anlegen kann).
func writeJSONFile(t *testing.T, dir, name string, v any) {
	t.Helper()
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll(%s): %v", dir, err)
	}
	data, err := json.Marshal(v)
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, name), data, 0644); err != nil {
		t.Fatalf("WriteFile(%s/%s): %v", dir, name, err)
	}
}

// readFileOrEmpty liefert den Inhalt einer Datei oder "" wenn sie nicht existiert.
func readFileOrEmpty(t *testing.T, path string) string {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return ""
		}
		t.Fatalf("ReadFile(%s): %v", path, err)
	}
	return string(data)
}

// findFilesOutsideUsersTree durchsucht dataDir nach Dateien mit dem
// angegebenen Namen, die NICHT unter dataDir/users/ liegen — das ist exakt
// die Prüfung, die AC-3/AC-12 verlangen ("das Dateisystem oberhalb von
// data/users/ durchsuchen").
func findFilesOutsideUsersTree(t *testing.T, dataDir, filename string) []string {
	t.Helper()
	usersRoot := filepath.Join(dataDir, "users")
	var found []string
	err := filepath.WalkDir(dataDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		if d.Name() != filename {
			return nil
		}
		rel, relErr := filepath.Rel(usersRoot, path)
		if relErr == nil && !strings.HasPrefix(rel, "..") {
			return nil // liegt innerhalb von data/users/
		}
		found = append(found, path)
		return nil
	})
	if err != nil {
		t.Fatalf("WalkDir(%s): %v", dataDir, err)
	}
	return found
}

// -----------------------------------------------------------------------
// AC-1 / AC-2 — LoginHandler
// -----------------------------------------------------------------------

// AC-1: Traversal-Kennung im username-Feld muss wie ein schlicht unbekannter
// Nutzer behandelt werden (401, identischer Body). Heute liest LoadUser
// klaglos aus dem per ".." erreichten Verzeichnis — existiert dort ein
// user.json mit passendem Passwort-Hash, meldet sich der Angreifer
// erfolgreich an (200 + Session-Cookie statt 401).
func TestLoginHandler_TraversalUsername_RejectedSameAsUnknownUser_AC1(t *testing.T) {
	s := newTestStore(t)

	// Opfer-Datei GENAU dort platzieren, wo UserDir("../marker") heute landet
	// (Geschwister von "users", siehe Methodik-Kommentar oben).
	victimHash, _ := bcrypt.GenerateFromPassword([]byte("attackerpass123"), bcrypt.MinCost)
	victimDir := s.UserDir("../marker")
	writeJSONFile(t, victimDir, "user.json", model.User{
		ID: "../marker", PasswordHash: string(victimHash), CreatedAt: time.Now(),
	})

	secret := "test-secret-32-chars-long-enough"
	h := LoginHandler(s, secret)

	attack := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(`{"username":"../marker","password":"attackerpass123"}`))
	wAttack := httptest.NewRecorder()
	h.ServeHTTP(wAttack, attack)

	unknown := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(`{"username":"garantiert-unbekannt-xyz","password":"irrelevant123"}`))
	wUnknown := httptest.NewRecorder()
	h.ServeHTTP(wUnknown, unknown)

	if wAttack.Code != 401 {
		t.Errorf("AC-1: expected 401 for traversal username, got %d: %s", wAttack.Code, wAttack.Body.String())
	}
	if wAttack.Body.String() != `{"error":"invalid credentials"}` {
		t.Errorf("AC-1: expected body '{\"error\":\"invalid credentials\"}', got %q", wAttack.Body.String())
	}
	if wAttack.Code != wUnknown.Code || wAttack.Body.String() != wUnknown.Body.String() {
		t.Errorf("AC-1: traversal response must be byte-identical to unknown-user response: attack=%d %q vs unknown=%d %q",
			wAttack.Code, wAttack.Body.String(), wUnknown.Code, wUnknown.Body.String())
	}
}

// AC-1 (Cross-User-Nutzlast) — Nachschärfung auf PO-Wunsch: "../marker" landet
// nur GESCHWISTER von "users" und trifft nie einen real registrierten
// Zweitnutzer (siehe Methodik-Kommentar oben). Die Nutzlast "../users/bob"
// dagegen kappt "users" und haengt es sofort wieder an:
// filepath.Join(DataDir,"users","../users/bob") = DataDir/users/bob — GENAU
// das Verzeichnis des real registrierten "bob". Dieser Test prueft, ob sich
// ein Angreifer damit tatsaechlich als der REALE Bob anmelden kann.
func TestLoginHandler_TraversalUsersBobPayload_CanImpersonateRealUser_AC1(t *testing.T) {
	s := newTestStore(t)

	bobHash, _ := bcrypt.GenerateFromPassword([]byte("bobs-real-pass"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: string(bobHash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}

	h := LoginHandler(s, "test-secret-32-chars-long-enough")
	req := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(`{"username":"../users/bob","password":"bobs-real-pass"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code == 200 {
		t.Errorf("AC-1 (Cross-User): '../users/bob' + bob's real password IMPERSONATES the real second user — got 200: %s", w.Body.String())
	}
	if w.Code != 401 || w.Body.String() != `{"error":"invalid credentials"}` {
		t.Errorf("AC-1 (Cross-User): expected 401 {\"error\":\"invalid credentials\"} after the fix, got %d %q", w.Code, w.Body.String())
	}
}

// AC-2 (Positivkontrolle): ein real registrierter Nutzer meldet sich weiterhin an.
func TestLoginHandler_ValidCredentials_StillWorks_AC2(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "alice", PasswordHash: string(hash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	h := LoginHandler(s, "test-secret-32-chars-long-enough")
	req := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(`{"username":"alice","password":"geheim123"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-2: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	found := false
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			found = true
		}
	}
	if !found {
		t.Error("AC-2: expected gz_session cookie to be set")
	}
}

// -----------------------------------------------------------------------
// AC-3 / AC-4 / AC-5 — ForgotPasswordHandler
// -----------------------------------------------------------------------

// AC-3: Traversal-Kennung darf KEINE password_reset.json ausserhalb des
// Nutzerbaums erzeugen. Heute erzeugt sie eine, sobald am Zielpfad ein
// e-mail-loser "Nutzer" liegt (identischer Mechanismus wie der
// dokumentierte Laufzeit-Nachweis, Log "token written but not sent").
func TestForgotPassword_TraversalUsername_NoFileOutsideTree_AC3(t *testing.T) {
	s := newTestStore(t)

	victimDir := s.UserDir("../marker")
	writeJSONFile(t, victimDir, "user.json", model.User{ID: "../marker", CreatedAt: time.Now()})

	h := ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"../marker"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 || w.Body.String() != `{"status":"ok"}` {
		t.Errorf("AC-3: expected 200 {\"status\":\"ok\"}, got %d %q", w.Code, w.Body.String())
	}
	if _, err := os.Stat(filepath.Join(victimDir, "password_reset.json")); err == nil {
		t.Error("AC-3: password_reset.json must NOT be created outside the users tree")
	}
	if outside := findFilesOutsideUsersTree(t, s.DataDir, "password_reset.json"); len(outside) > 0 {
		t.Errorf("AC-3: found password_reset.json outside data/users/: %v", outside)
	}
}

// AC-4: Traversal-Kennung und syntaktisch gueltige, aber unbekannte Kennung
// muessen byte-identische Antworten liefern (Enumerationsschutz).
// Hinweis: diese AC ist bereits am unveraenderten Stand gruen (die Route
// antwortet fuer BEIDE Faelle ohne Opfer-Datei sofort 200 {"status":"ok"}) —
// sie bewacht ab jetzt gegen Rueckschritt, nicht gegen den urspruenglichen Bug.
func TestForgotPassword_TraversalVsUnknownUser_IdenticalResponse_AC4(t *testing.T) {
	s := newTestStore(t)
	h := ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"})

	traversal := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"../marker2"}`))
	wTraversal := httptest.NewRecorder()
	h.ServeHTTP(wTraversal, traversal)

	unknown := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"garantiert-unbekannt-xyz"}`))
	wUnknown := httptest.NewRecorder()
	h.ServeHTTP(wUnknown, unknown)

	if wTraversal.Code != wUnknown.Code || wTraversal.Body.String() != wUnknown.Body.String() {
		t.Errorf("AC-4: expected byte-identical responses, got traversal=%d %q vs unknown=%d %q",
			wTraversal.Code, wTraversal.Body.String(), wUnknown.Code, wUnknown.Body.String())
	}
}

// AC-5 (Positivkontrolle): ein real registrierter Nutzer mit E-Mail bekommt
// weiterhin ein Reset-Token in seinem EIGENEN Verzeichnis.
func TestForgotPassword_RealUserStillGetsResetToken_AC5(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "erika", Email: "erika@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	h := ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"erika"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-5: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	tokenFile := filepath.Join(s.UserDir("erika"), "password_reset.json")
	if _, err := os.Stat(tokenFile); os.IsNotExist(err) {
		t.Error("AC-5: password_reset.json should be created in erika's own directory")
	}
}

// -----------------------------------------------------------------------
// AC-6 / AC-7 — ResetPasswordHandler
// -----------------------------------------------------------------------

// AC-6: Traversal-Kennung + (fuer den Angreifer erreichbares) passendes
// Token darf das Passwort NICHT setzen — weder das eines ausserhalb
// erreichten Datensatzes noch das eines real registrierten zweiten Nutzers.
// Heute prueft ResetPasswordHandler die Kennung nicht vor dem Store-Zugriff:
// stimmen Token und Pfad ueberein, wird das Passwort am ausserhalb liegenden
// Datensatz TATSAECHLICH geaendert und die Route antwortet 200 statt 400.
func TestResetPassword_TraversalUsername_RejectedNoHashChange_AC6(t *testing.T) {
	s := newTestStore(t)

	// Opfer ausserhalb des Baums, exakt am Ziel von UserDir("../bob").
	victimDir := s.UserDir("../bob")
	oldHash, _ := bcrypt.GenerateFromPassword([]byte("victim-old-pass"), bcrypt.MinCost)
	writeJSONFile(t, victimDir, "user.json", model.User{ID: "../bob", PasswordHash: string(oldHash), CreatedAt: time.Now()})
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("attackertoken123"), bcrypt.MinCost)
	writeJSONFile(t, victimDir, "password_reset.json", model.PasswordResetToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(30 * time.Minute),
	})

	// Real registrierter zweiter Nutzer "bob" — muss unberuehrt bleiben.
	realHash, _ := bcrypt.GenerateFromPassword([]byte("bobs-real-pass"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: string(realHash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	realUserFileBefore := readFileOrEmpty(t, filepath.Join(s.UserDir("bob"), "user.json"))

	h := ResetPasswordHandler(s, bcrypt.MinCost)
	req := httptest.NewRequest("POST", "/api/auth/reset-password",
		strings.NewReader(`{"username":"../bob","token":"attackertoken123","new_password":"newpass1234"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 || w.Body.String() != `{"error":"invalid token"}` {
		t.Errorf("AC-6: expected 400 {\"error\":\"invalid token\"}, got %d %q", w.Code, w.Body.String())
	}

	victimUserData := readFileOrEmpty(t, filepath.Join(victimDir, "user.json"))
	var victimUser model.User
	json.Unmarshal([]byte(victimUserData), &victimUser)
	if victimUser.PasswordHash != string(oldHash) {
		t.Error("AC-6: password hash of the out-of-tree victim must not change")
	}

	realUserFileAfter := readFileOrEmpty(t, filepath.Join(s.UserDir("bob"), "user.json"))
	if realUserFileBefore != realUserFileAfter {
		t.Error("AC-6: real second user's user.json must stay byte-identical")
	}
}

// AC-6 (Cross-User-Nutzlast) — Nachschärfung auf PO-Wunsch: "../users/bob"
// kappt "users" und haengt es sofort wieder an, trifft also GENAU das
// Verzeichnis des real registrierten "bob" (siehe AC-1-Pendant oben). Dieser
// Test prueft die schwerste Folge: kann ein Angreifer mit Bobs eigenem,
// gueltigem Reset-Token das Passwort des REALEN Bob setzen?
func TestResetPassword_TraversalUsersBobPayload_HitsRealSecondUser_AC6(t *testing.T) {
	s := newTestStore(t)

	oldHash, _ := bcrypt.GenerateFromPassword([]byte("bobs-old-pass"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "bob", PasswordHash: string(oldHash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("bobs-real-token"), bcrypt.MinCost)
	if err := s.SaveResetToken("bob", model.PasswordResetToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(30 * time.Minute),
	}); err != nil {
		t.Fatalf("SaveResetToken(bob): %v", err)
	}
	bobFile := filepath.Join(s.UserDir("bob"), "user.json")
	infoBefore, err := os.Stat(bobFile)
	if err != nil {
		t.Fatalf("Stat(bob) before: %v", err)
	}
	contentBefore := readFileOrEmpty(t, bobFile)

	h := ResetPasswordHandler(s, bcrypt.MinCost)
	req := httptest.NewRequest("POST", "/api/auth/reset-password",
		strings.NewReader(`{"username":"../users/bob","token":"bobs-real-token","new_password":"attackerchosen1"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code == 200 {
		t.Errorf("AC-6 (Cross-User): '../users/bob' + bob's own valid token changed the REAL user's password — got 200: %s", w.Body.String())
	}
	if w.Code != 400 || w.Body.String() != `{"error":"invalid token"}` {
		t.Errorf("AC-6 (Cross-User): expected 400 {\"error\":\"invalid token\"} after the fix, got %d %q", w.Code, w.Body.String())
	}

	contentAfter := readFileOrEmpty(t, bobFile)
	if contentBefore != contentAfter {
		t.Error("AC-6 (Cross-User): bob's real user.json content must stay byte-identical")
	}
	infoAfter, err := os.Stat(bobFile)
	if err != nil {
		t.Fatalf("Stat(bob) after: %v", err)
	}
	if !infoBefore.ModTime().Equal(infoAfter.ModTime()) {
		t.Error("AC-6 (Cross-User): bob's real user.json mtime must stay unchanged")
	}
}

// AC-7 (Positivkontrolle): ein real registrierter Nutzer mit gueltigem Token
// kann sein Passwort weiterhin zuruecksetzen.
func TestResetPassword_RealUserStillWorks_AC7(t *testing.T) {
	s := newTestStore(t)
	oldHash, _ := bcrypt.GenerateFromPassword([]byte("oldpass"), bcrypt.MinCost)
	if err := s.SaveUser(model.User{ID: "carla", PasswordHash: string(oldHash), CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("realtoken123"), bcrypt.MinCost)
	if err := s.SaveResetToken("carla", model.PasswordResetToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(30 * time.Minute),
	}); err != nil {
		t.Fatalf("SaveResetToken: %v", err)
	}

	h := ResetPasswordHandler(s, bcrypt.MinCost)
	req := httptest.NewRequest("POST", "/api/auth/reset-password",
		strings.NewReader(`{"username":"carla","token":"realtoken123","new_password":"brandneu1234"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-7: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	loginHandler := LoginHandler(s, "test-secret-32-chars-long-enough")
	loginReq := httptest.NewRequest("POST", "/api/auth/login", strings.NewReader(`{"username":"carla","password":"brandneu1234"}`))
	wLogin := httptest.NewRecorder()
	loginHandler.ServeHTTP(wLogin, loginReq)
	if wLogin.Code != 200 {
		t.Errorf("AC-7: expected login with new password to succeed, got %d: %s", wLogin.Code, wLogin.Body.String())
	}
}

// -----------------------------------------------------------------------
// AC-8 / AC-9 — VerifyEmailHandler
// -----------------------------------------------------------------------

// AC-8: Traversal-Kennung im user-Feld darf EmailVerifiedAt keines Nutzers
// setzen — weder ausserhalb noch bei einem real registrierten zweiten Nutzer.
func TestVerifyEmail_TraversalUsername_RejectedNoVerification_AC8(t *testing.T) {
	s := newTestStore(t)

	victimDir := s.UserDir("../bob")
	writeJSONFile(t, victimDir, "user.json", model.User{ID: "../bob", CreatedAt: time.Now()})
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("attackertoken123"), bcrypt.MinCost)
	writeJSONFile(t, victimDir, "email_verification.json", model.EmailVerificationToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(24 * time.Hour),
	})

	if err := s.SaveUser(model.User{ID: "bob", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}

	h := VerifyEmailHandler(s)
	req := httptest.NewRequest("POST", "/api/verify-email",
		strings.NewReader(`{"user":"../bob","token":"attackertoken123"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 400 || w.Body.String() != `{"error":"invalid token"}` {
		t.Errorf("AC-8: expected 400 {\"error\":\"invalid token\"}, got %d %q", w.Code, w.Body.String())
	}

	victimUserData := readFileOrEmpty(t, filepath.Join(victimDir, "user.json"))
	var victimUser model.User
	json.Unmarshal([]byte(victimUserData), &victimUser)
	if victimUser.EmailVerifiedAt != nil {
		t.Error("AC-8: EmailVerifiedAt of the out-of-tree victim must stay nil")
	}

	realBob, err := s.LoadUser("bob")
	if err != nil || realBob == nil {
		t.Fatalf("LoadUser(bob): %v", err)
	}
	if realBob.EmailVerifiedAt != nil {
		t.Error("AC-8: real second user's EmailVerifiedAt must stay nil")
	}
}

// AC-8 (Cross-User-Nutzlast) — Nachschärfung auf PO-Wunsch: "../users/bob"
// trifft GENAU das Verzeichnis des real registrierten "bob" (siehe
// AC-1/AC-6-Pendants oben). Prueft, ob ein Angreifer mit Bobs eigenem,
// gueltigem Verifikations-Token dessen E-Mail-Adresse als "verifiziert"
// markieren kann.
func TestVerifyEmail_TraversalUsersBobPayload_HitsRealSecondUser_AC8(t *testing.T) {
	s := newTestStore(t)

	if err := s.SaveUser(model.User{ID: "bob", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("bobs-real-verify-token"), bcrypt.MinCost)
	if err := s.SaveVerificationToken("bob", model.EmailVerificationToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(24 * time.Hour),
	}); err != nil {
		t.Fatalf("SaveVerificationToken(bob): %v", err)
	}

	h := VerifyEmailHandler(s)
	req := httptest.NewRequest("POST", "/api/verify-email",
		strings.NewReader(`{"user":"../users/bob","token":"bobs-real-verify-token"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code == 200 {
		t.Errorf("AC-8 (Cross-User): '../users/bob' + bob's own valid token verified the REAL user's email — got 200: %s", w.Body.String())
	}
	if w.Code != 400 || w.Body.String() != `{"error":"invalid token"}` {
		t.Errorf("AC-8 (Cross-User): expected 400 {\"error\":\"invalid token\"} after the fix, got %d %q", w.Code, w.Body.String())
	}

	realBob, err := s.LoadUser("bob")
	if err != nil || realBob == nil {
		t.Fatalf("LoadUser(bob): %v", err)
	}
	if realBob.EmailVerifiedAt != nil {
		t.Error("AC-8 (Cross-User): real second user's EmailVerifiedAt must stay nil")
	}
}

// AC-9 (Positivkontrolle): ein real registrierter Nutzer mit gueltigem Token
// wird weiterhin verifiziert.
func TestVerifyEmail_RealUserStillWorks_AC9(t *testing.T) {
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "dieter", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	tokenHash, _ := bcrypt.GenerateFromPassword([]byte("realtoken123"), bcrypt.MinCost)
	if err := s.SaveVerificationToken("dieter", model.EmailVerificationToken{
		TokenHash: string(tokenHash), ExpiresAt: time.Now().Add(24 * time.Hour),
	}); err != nil {
		t.Fatalf("SaveVerificationToken: %v", err)
	}

	h := VerifyEmailHandler(s)
	req := httptest.NewRequest("POST", "/api/verify-email", strings.NewReader(`{"user":"dieter","token":"realtoken123"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-9: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	user, err := s.LoadUser("dieter")
	if err != nil || user == nil || user.EmailVerifiedAt == nil {
		t.Errorf("AC-9: expected EmailVerifiedAt to be set, err=%v user=%+v", err, user)
	}
}

// -----------------------------------------------------------------------
// AC-10 — Zwei-Nutzer-Nachweis (ADR-0003)
// -----------------------------------------------------------------------

// AC-10: zwei real angelegte Nutzer; ein Traversal-Angriff ueber
// password-forgot darf weder den realen zweiten Nutzer beruehren noch
// ausserhalb des Baums ein Token hinterlassen.
func TestForgotPassword_TwoRealUsers_SecondUserUntouched_AC10(t *testing.T) {
	s := newTestStore(t)

	if err := s.SaveUser(model.User{ID: "alice", Email: "alice@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(alice): %v", err)
	}
	if err := s.SaveUser(model.User{ID: "bob", Email: "bob@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	bobFile := filepath.Join(s.UserDir("bob"), "user.json")
	infoBefore, err := os.Stat(bobFile)
	if err != nil {
		t.Fatalf("Stat(bob user.json) before attack: %v", err)
	}
	contentBefore := readFileOrEmpty(t, bobFile)

	// Zusaetzlich ein e-mail-loses Opfer GENAU am Ziel von "../bob" platzieren
	// (Geschwister von "users", siehe Methodik-Kommentar) — das macht den
	// Angriff wirksam nachweisbar (Log "token written but not sent").
	victimDir := s.UserDir("../bob")
	writeJSONFile(t, victimDir, "user.json", model.User{ID: "../bob", CreatedAt: time.Now()})

	h := ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"})
	req := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"../bob"}`))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)

	if w.Code != 200 {
		t.Fatalf("AC-10: expected 200, got %d: %s", w.Code, w.Body.String())
	}

	infoAfter, err := os.Stat(bobFile)
	if err != nil {
		t.Fatalf("Stat(bob user.json) after attack: %v", err)
	}
	contentAfter := readFileOrEmpty(t, bobFile)
	if contentBefore != contentAfter {
		t.Error("AC-10: bob's real user.json content must stay byte-identical")
	}
	if !infoBefore.ModTime().Equal(infoAfter.ModTime()) {
		t.Error("AC-10: bob's real user.json mtime must stay unchanged")
	}

	if _, err := os.Stat(filepath.Join(victimDir, "password_reset.json")); err == nil {
		t.Error("AC-10: password_reset.json must NOT be created outside the users tree")
	}

	// Nachschärfung auf PO-Wunsch: "../bob" trifft den realen Bob NICHT
	// (siehe Methodik-Kommentar oben) — die Nutzlast, die "users" kappt und
	// sofort wieder anhängt, ist "../users/bob" und landet exakt in Bobs
	// echtem Verzeichnis (filepath.Join(DataDir,"users","../users/bob") =
	// DataDir/users/bob). Bob hat bereits eine E-Mail-Adresse hinterlegt
	// (s.o.), er hatte bislang aber KEIN password_reset.json — entsteht nach
	// diesem Aufruf eins in seinem ECHTEN Verzeichnis, ist das der direkte
	// Cross-User-Nachweis (kein Geschwister-Verzeichnis, kein Opfer-Platzhalter).
	realResetFile := filepath.Join(s.UserDir("bob"), "password_reset.json")
	if _, err := os.Stat(realResetFile); err == nil {
		t.Fatalf("AC-10 setup invariant broken: bob already has a password_reset.json before the cross-user payload")
	}

	req2 := httptest.NewRequest("POST", "/api/auth/forgot-password", strings.NewReader(`{"username":"../users/bob"}`))
	w2 := httptest.NewRecorder()
	h.ServeHTTP(w2, req2)

	if w2.Code != 200 {
		t.Fatalf("AC-10 (Cross-User): expected 200, got %d: %s", w2.Code, w2.Body.String())
	}
	if _, err := os.Stat(realResetFile); err == nil {
		t.Error("AC-10 (Cross-User): '../users/bob' created a password_reset.json in BOB'S REAL directory — cross-user reachability confirmed")
	}
}

// -----------------------------------------------------------------------
// AC-15 — Server-seitiger Log-Eintrag bei Ablehnung
// -----------------------------------------------------------------------

// AC-15: eine abgelehnte Traversal-Kennung muss serverseitig geloggt werden —
// auf ALLEN VIER oeffentlichen Routen, nicht nur beim Login (F001 aus dem
// Fix-Loop: die Vorpruefungen der drei uebrigen Routen liessen sich entfernen,
// ohne dass ein Test rot wurde).
//
// Geprueft wird je Route dreierlei: die abgelehnte Kennung steht im Log, die
// Route ist am Log-Praefix erkennbar, und die Ablehnung ist als solche
// ausgewiesen — nicht als generischer Sammel-Fehler. Beim Login ist das der
// Kern des Adversary-Einwands: die Meldung darf nicht mit dem bestehenden
// "user.json unreadable/corrupt"-Zweig verschwimmen, sonst laesst sich aus dem
// Log nicht ablesen, ob die Sperre gegriffen hat oder eine Datei kaputt war.
func TestAuthRoutes_TraversalRejection_LogsRoute_AC15(t *testing.T) {
	const attack = "../marker3"
	const rejectionPhrase = "rejected path-unsafe user id"

	cases := []struct {
		name    string
		prefix  string // Erkennungsmerkmal der Route im Log
		request func(s *store.Store) (http.Handler, *http.Request)
	}{
		{
			name:   "LoginHandler",
			prefix: "login:",
			request: func(s *store.Store) (http.Handler, *http.Request) {
				return LoginHandler(s, "test-secret-32-chars-long-enough"),
					httptest.NewRequest("POST", "/api/auth/login",
						strings.NewReader(`{"username":"`+attack+`","password":"x"}`))
			},
		},
		{
			name:   "ForgotPasswordHandler",
			prefix: "password reset:",
			request: func(s *store.Store) (http.Handler, *http.Request) {
				return ForgotPasswordHandler(s, bcrypt.MinCost, config.Config{PublicHost: "https://test.example.com"}),
					httptest.NewRequest("POST", "/api/auth/forgot-password",
						strings.NewReader(`{"username":"`+attack+`"}`))
			},
		},
		{
			name:   "ResetPasswordHandler",
			prefix: "password reset confirm:",
			request: func(s *store.Store) (http.Handler, *http.Request) {
				return ResetPasswordHandler(s, bcrypt.MinCost),
					httptest.NewRequest("POST", "/api/auth/reset-password",
						strings.NewReader(`{"username":"`+attack+`","token":"x","new_password":"12345678"}`))
			},
		},
		{
			name:   "VerifyEmailHandler",
			prefix: "email verification:",
			request: func(s *store.Store) (http.Handler, *http.Request) {
				return VerifyEmailHandler(s),
					httptest.NewRequest("POST", "/api/verify-email",
						strings.NewReader(`{"user":"`+attack+`","token":"x"}`))
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			s := newTestStore(t)

			var logBuf bytes.Buffer
			log.SetOutput(&logBuf)
			defer log.SetOutput(os.Stderr)

			h, req := tc.request(s)
			h.ServeHTTP(httptest.NewRecorder(), req)

			got := logBuf.String()
			if !strings.Contains(got, attack) {
				t.Errorf("AC-15: expected a log entry mentioning the rejected id %q, got: %q", attack, got)
			}
			if !strings.Contains(got, tc.prefix) {
				t.Errorf("AC-15: expected the log entry to identify the route via %q, got: %q", tc.prefix, got)
			}
			if !strings.Contains(got, rejectionPhrase) {
				t.Errorf("AC-15: expected the log entry to name the rejection (%q), got: %q", rejectionPhrase, got)
			}
			if strings.Contains(got, "unreadable/corrupt") {
				t.Errorf("AC-15: the traversal rejection must not be logged as the generic corrupt-file case, got: %q", got)
			}
		})
	}
}
