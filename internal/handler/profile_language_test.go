package handler

// Issue #2646 (i18n S1) — Sprachfeld `language` am Nutzerprofil.
// Spec: docs/specs/modules/i18n_s1_sprachfeld_nutzer_2646.md — AC-1, AC-2,
// AC-3, AC-5 (Profil-Update und Anmeldung).
//
// Keine Mocks: echte Handler ueber echte HTTP-Requests, echter Store auf
// t.TempDir(). Fixtures werden roh geschrieben (onbWriteRawUser), damit ein
// dem Modell unbekanntes Fremdfeld ueberhaupt auf der Platte steht; gemessen
// wird ebenfalls roh auf der Platte.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/store"
)

// langAltdatei: Bestandsprofil ohne Sprachfeld, mit Adressen und Fremdfeld.
// Unbestaetigt und mit SMS-Nummer: loeste der Sprach-PUT faelschlich den
// Adress-/Nummernpfad aus, entstuende hier eine Mail bzw. ein SMS-Code.
func langAltdatei(id string) map[string]interface{} {
	return map[string]interface{}{
		"id":            id,
		"email":         id + "@example.com",
		"password_hash": "$2a$04$abcdefghijklmnopqrstuv",
		"created_at":    "2026-06-01T12:00:00Z",
		"display_name":  "Anzeige " + id,
		"mail_to":       id + "-post@example.com",
		"sms_to":        "+4915112345678",
		"tier":          "premium",
		"zukunftsfeld":  map[string]interface{}{"x": 1, "liste": []interface{}{"a", "b"}},
	}
}

func langPut(t *testing.T, s *store.Store, cfg config.Config, uid, body string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPut, "/api/auth/profile", strings.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	UpdateProfileHandler(s, cfg, weitMailLimiter, weitSmsLimiter).ServeHTTP(w, req)
	return w
}

func langCookie(w *httptest.ResponseRecorder) *http.Cookie {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_lang" {
			return c
		}
	}
	return nil
}

// langPruefeCookie prueft die Attribute aus AC-5 an der echten Antwort.
func langPruefeCookie(t *testing.T, ac string, w *httptest.ResponseRecorder, want string, secure bool) {
	t.Helper()
	c := langCookie(w)
	if c == nil {
		t.Fatalf("%s: kein Set-Cookie gz_lang in der Antwort (Header %v)", ac, w.Header().Values("Set-Cookie"))
	}
	if c.Value != want {
		t.Errorf("%s: gz_lang=%q, erwartet %q", ac, c.Value, want)
	}
	if c.Path != "/" {
		t.Errorf("%s: Path=%q, erwartet /", ac, c.Path)
	}
	if c.MaxAge != 31536000 {
		t.Errorf("%s: Max-Age=%d, erwartet 31536000", ac, c.MaxAge)
	}
	if c.SameSite != http.SameSiteLaxMode {
		t.Errorf("%s: SameSite=%v, erwartet Lax", ac, c.SameSite)
	}
	if c.HttpOnly {
		t.Errorf("%s: gz_lang ist HttpOnly, darf es nicht sein", ac)
	}
	if c.Secure != secure {
		t.Errorf("%s: Secure=%v, erwartet %v", ac, c.Secure, secure)
	}
}

// langZaehleVersand ersetzt beide Versand-Nahten durch Zaehler.
func langZaehleVersand(t *testing.T) (*int32, *int32) {
	t.Helper()
	var mails, sms int32
	origMail, origSms := sendVerificationMailFn, sendSmsCodeFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		atomic.AddInt32(&mails, 1)
		return nil
	}
	sendSmsCodeFn = func(cfg config.Config, userId, number, code string) error {
		atomic.AddInt32(&sms, 1)
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn, sendSmsCodeFn = origMail, origSms })
	return &mails, &sms
}

// AC-1: A mit "en", B ohne Feld; B's Datei bleibt byte-identisch.
func TestProfileGetLiefertWirksameSpracheJeNutzer(t *testing.T) {
	s := newTestStore(t)
	a := langAltdatei("lang-anna")
	a["language"] = "en"
	onbWriteRawUser(t, s, "lang-anna", a)
	onbWriteRawUser(t, s, "lang-bert", langAltdatei("lang-bert"))
	bVorher := onbReadRawUserBytes(t, s, "lang-bert")

	for uid, want := range map[string]string{"lang-anna": `"en"`, "lang-bert": `"de"`} {
		code, m, body := onbGetProfile(t, s, uid)
		if code != http.StatusOK {
			t.Fatalf("AC-1: GET %s: Status %d: %s", uid, code, body)
		}
		if got := string(m["language"]); got != want {
			t.Errorf("AC-1: GET %s: language=%s, erwartet %s (Body %s)", uid, got, want, body)
		}
	}
	if nachher := onbReadRawUserBytes(t, s, "lang-bert"); !bytes.Equal(bVorher, nachher) {
		t.Errorf("AC-1: user.json von B nach GET veraendert:\nvorher %s\nnachher %s", bVorher, nachher)
	}
}

// AC-2: ungueltige Werte -> 400 invalid_language, Datei byte-identisch.
func TestProfilePutUngueltigeSpracheSchreibtNichts(t *testing.T) {
	s := newTestStore(t)
	onbWriteRawUser(t, s, "lang-carl", langAltdatei("lang-carl"))
	for _, body := range []string{
		`{"language":"fr"}`, `{"language":""}`, `{"language":"EN"}`,
		`{"language":"fr","display_name":"Neu"}`,
	} {
		vorher := onbReadRawUserBytes(t, s, "lang-carl")
		w := langPut(t, s, config.Config{}, "lang-carl", body)
		if w.Code != http.StatusBadRequest {
			t.Errorf("AC-2: %s: Status %d, erwartet 400 (%s)", body, w.Code, w.Body.String())
		}
		var resp map[string]string
		_ = json.Unmarshal(w.Body.Bytes(), &resp)
		if resp["error"] != "invalid_language" {
			t.Errorf("AC-2: %s: Antwort %s, erwartet {\"error\":\"invalid_language\"}", body, w.Body.String())
		}
		if nachher := onbReadRawUserBytes(t, s, "lang-carl"); !bytes.Equal(vorher, nachher) {
			t.Errorf("AC-2: %s: user.json veraendert:\nvorher %s\nnachher %s", body, vorher, nachher)
		}
		if c := langCookie(w); c != nil {
			t.Errorf("AC-2: %s: abgewiesene Anfrage setzt trotzdem gz_lang=%q", body, c.Value)
		}
	}
}

// langPruefeMerge: alle Altfelder stehen inhaltlich unveraendert, ausser denen
// in geaendert; language hat den erwarteten Wert.
func langPruefeMerge(t *testing.T, ac string, vorher, nachher map[string]json.RawMessage, geaendert map[string]string) {
	t.Helper()
	for k, alt := range vorher {
		if _, skip := geaendert[k]; skip {
			continue
		}
		neu, ok := nachher[k]
		if !ok {
			t.Errorf("%s: Feld %q verschwunden (vorher %s) — ersetzt statt gemergt", ac, k, alt)
			continue
		}
		if !onbJSONEqual(alt, neu) {
			t.Errorf("%s: Feld %q veraendert: %s -> %s", ac, k, alt, neu)
		}
	}
	for k, want := range geaendert {
		if got := string(nachher[k]); got != want {
			t.Errorf("%s: Feld %q = %s, erwartet %s", ac, k, got, want)
		}
	}
}

// langPruefeKeinVersand: weder Mail- noch SMS-Code, auch nicht als Datei.
func langPruefeKeinVersand(t *testing.T, ac string, s *store.Store, uid string, mails, sms *int32) {
	t.Helper()
	time.Sleep(100 * time.Millisecond) // Versand liefe in einer Goroutine
	if n := atomic.LoadInt32(mails); n != 0 {
		t.Errorf("%s: %d Bestaetigungsmail(s) ausgeloest, erwartet 0", ac, n)
	}
	if n := atomic.LoadInt32(sms); n != 0 {
		t.Errorf("%s: %d SMS-Code(s) ausgeloest, erwartet 0", ac, n)
	}
	for _, f := range []string{"email_verification.json", "sms_verification.json"} {
		if _, err := os.Stat(filepath.Join(s.UserDir(uid), f)); err == nil {
			t.Errorf("%s: %s wurde angelegt — Adress-/Nummernpfad faelschlich betreten", ac, f)
		}
	}
}

// AC-3 + AC-5: nur language -> Merge, kein Versand, Cookie (https-PublicHost).
func TestProfilePutNurSpracheMergtUndSetztCookie(t *testing.T) {
	s := newTestStore(t)
	mails, sms := langZaehleVersand(t)
	onbWriteRawUser(t, s, "lang-dora", langAltdatei("lang-dora"))
	onbWriteRawUser(t, s, "lang-emil", langAltdatei("lang-emil"))
	emilVorher := onbReadRawUserBytes(t, s, "lang-emil")
	vorher := onbReadRawUser(t, s, "lang-dora")

	cfg := config.Config{PublicHost: "https://gregor20.henemm.com"}
	w := langPut(t, s, cfg, "lang-dora", `{"language":"en"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3: Status %d: %s", w.Code, w.Body.String())
	}
	var resp map[string]json.RawMessage
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if string(resp["language"]) != `"en"` {
		t.Errorf("AC-3: Antwort language=%s, erwartet \"en\"", resp["language"])
	}
	langPruefeMerge(t, "AC-3 (nur language)", vorher, onbReadRawUser(t, s, "lang-dora"), map[string]string{"language": `"en"`})
	langPruefeKeinVersand(t, "AC-3 (nur language)", s, "lang-dora", mails, sms)
	langPruefeCookie(t, "AC-5 (Profil, https)", w, "en", true)
	if nachher := onbReadRawUserBytes(t, s, "lang-emil"); !bytes.Equal(emilVorher, nachher) {
		t.Errorf("Mandantentrennung: user.json eines anderen Nutzers veraendert")
	}
}

// AC-3 + AC-5: language zusammen mit display_name -> beide gesetzt, Fremdfeld
// bleibt, kein Versand, Cookie ohne Secure bei http.
func TestProfilePutSpracheMitAnzeigenameMergt(t *testing.T) {
	s := newTestStore(t)
	mails, sms := langZaehleVersand(t)
	onbWriteRawUser(t, s, "lang-fred", langAltdatei("lang-fred"))
	vorher := onbReadRawUser(t, s, "lang-fred")

	cfg := config.Config{PublicHost: "http://localhost:4173"}
	w := langPut(t, s, cfg, "lang-fred", `{"language":"en","display_name":"Fred Neu"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3: Status %d: %s", w.Code, w.Body.String())
	}
	// Der gemischte PUT schreibt laut Spec per SaveUser (typisiertes Modell):
	// das dem Modell unbekannte Fremdfeld ueberlebt dort heute schon keinen
	// display_name-PUT (Bestandsverhalten, nicht Teil dieses Pakets). Geprueft
	// werden hier alle Modellfelder; das Fremdfeld prueft der Nur-Sprache-Pfad.
	delete(vorher, "zukunftsfeld")
	langPruefeMerge(t, "AC-3 (gemischt)", vorher, onbReadRawUser(t, s, "lang-fred"),
		map[string]string{"language": `"en"`, "display_name": `"Fred Neu"`})
	langPruefeKeinVersand(t, "AC-3 (gemischt)", s, "lang-fred", mails, sms)
	langPruefeCookie(t, "AC-5 (Profil, http)", w, "en", false)

	// Rueckweg auf de ueber den Nur-Sprache-Pfad.
	w = langPut(t, s, cfg, "lang-fred", `{"language":"de"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("Rueckweg de: Status %d: %s", w.Code, w.Body.String())
	}
	if got := string(onbReadRawUser(t, s, "lang-fred")["language"]); got != `"de"` {
		t.Errorf("Rueckweg de: language=%s, erwartet \"de\"", got)
	}
	langPruefeCookie(t, "AC-5 (Profil, Rueckweg)", w, "de", false)
}

// Sprache zusammen mit einem Dismiss-Flag darf nicht im Flag-Fruehpfad verloren gehen.
func TestProfilePutSpracheMitDismissFlagSetztBeides(t *testing.T) {
	s := newTestStore(t)
	onbWriteRawUser(t, s, "lang-gina", langAltdatei("lang-gina"))
	w := langPut(t, s, config.Config{}, "lang-gina", `{"language":"en","checklist_dismissed":true}`)
	if w.Code != http.StatusOK {
		t.Fatalf("Status %d: %s", w.Code, w.Body.String())
	}
	m := onbReadRawUser(t, s, "lang-gina")
	if string(m["language"]) != `"en"` || string(m["checklist_dismissed"]) != "true" {
		t.Errorf("language=%s checklist_dismissed=%s, erwartet \"en\" und true", m["language"], m["checklist_dismissed"])
	}
}

// AC-5: Anmeldung setzt gz_lang mit der Nutzersprache (en bzw. de ohne Feld).
func TestLoginSetztSprachCookie(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("geheim123"), bcrypt.MinCost)
	for uid, lang := range map[string]string{"lang-hans": "en", "lang-ida": ""} {
		m := map[string]interface{}{
			"id": uid, "password_hash": string(hash),
			"email_verified_at": "2026-04-15T00:00:00Z", "created_at": "2026-04-15T00:00:00Z",
		}
		if lang != "" {
			m["language"] = lang
		}
		onbWriteRawUser(t, s, uid, m)
	}
	cases := []struct {
		uid, host, want string
		secure          bool
	}{
		{"lang-hans", "https://gregor20.henemm.com", "en", true},
		{"lang-ida", "http://localhost:4173", "de", false},
	}
	for _, tc := range cases {
		h := LoginHandler(s, "test-secret-32-chars-long-enough", tc.host)
		body := `{"username":"` + tc.uid + `","password":"geheim123"}`
		w := httptest.NewRecorder()
		h.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(body)))
		if w.Code != http.StatusOK {
			t.Fatalf("Login %s: Status %d: %s", tc.uid, w.Code, w.Body.String())
		}
		langPruefeCookie(t, "AC-5 (Login "+tc.uid+")", w, tc.want, tc.secure)
	}
}
