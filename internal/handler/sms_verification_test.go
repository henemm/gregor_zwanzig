package handler_test

// TDD RED — Issue #2406 (S3 aus #2153, Epic #2138): SMS-Nummer-Verifikation
// vor erstem Versand.
// Spec: docs/specs/modules/sms_nummer_verifikation.md — AC-2, AC-3, AC-4,
// AC-7, AC-8, AC-9, AC-13, AC-16 (Go-Teil). AC-5/AC-6 stehen in
// sms_verify_ratelimit_test.go, AC-15 in sms_staging_code_test.go; die
// Umgebung (smsUmgebung) aus DIESER Datei wird von beiden mitbenutzt.
//
// Externes Testpaket mit Absicht (Muster verify_resend_test.go, #2304): die
// neuen Routen (/api/auth/sms/verify, /resend, /staging-code), die neuen
// User-Felder und der neue Limiter existieren noch nicht. Ueber den ECHTEN
// router.New adressiert bricht kein fehlendes Symbol die Kompilierung — die
// Tests scheitern heute am VERHALTEN (404, 200 statt 400, kein Versand), nicht
// am Bau. Ein Symbolverweis aus `package handler` haette das ganze Verzeichnis
// unkompilierbar gemacht.
//
// Beobachtungspunkt Versand (kein Mock-Theater): die Spec legt fest, dass Go den
// Code per POST an `cfg.PythonCoreURL + "/api/_internal/sms/verification-code"`
// mit `{"user_id","to","code"}` schickt (§3). Der Test setzt PythonCoreURL auf
// einen lokalen httptest-Server, der genau diese Aufrufe ZAEHLT und Nummer +
// Code festhaelt. Zusicherung: „wurde versandt ja/nein, an welche Nummer, fuer
// welches Konto". Der festgehaltene Klartext-Code ist zugleich die EINZIGE
// Quelle des Codes fuer den anschliessenden echten POST /api/auth/sms/verify —
// der Test kennt ihn genau so, wie ihn das Geraet hinter der Nummer kennen
// wuerde.
//
// Der Versand laeuft laut Spec asynchron (Goroutine, §2) — deshalb wird auf
// den Aufruf mit Frist gewartet, nie direkt nach dem PUT gezaehlt.
//
// Bestandsdaten mit den NEUEN Feldern (sms_verified_number, pending_sms_to)
// werden als rohes user.json geschrieben und als rohes JSON zurueckgelesen —
// so braucht der Test keine neuen model.User-Felder.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	smsCorePfad2406    = "/api/_internal/sms/verification-code"
	smsVerifyPfad2406  = "/api/auth/sms/verify"
	smsResendPfad2406  = "/api/auth/sms/resend"
	smsStagingPfad2406 = "/api/auth/sms/staging-code"
	profilPfad2406     = "/api/auth/profile"

	// Frist fuer den asynchronen Versand; Wartezeit fuer „es kommt KEIN Versand".
	smsVersandFrist2406 = 3 * time.Second
	smsStilleFrist2406  = 400 * time.Millisecond
)

// smsVersand2406 ist ein echter Aufruf des internen Python-Versand-Endpunkts.
type smsVersand2406 struct {
	UserID string `json:"user_id"`
	To     string `json:"to"`
	Code   string `json:"code"`
}

// smsCoreGegenstelle2406 bildet den Python-Core-Endpunkt ab: zaehlt die
// Aufrufe und haelt Konto, Nummer und Code fest. Antwortet wie der echte
// Endpunkt im Erfolgsfall ({"status":"sent"}).
type smsCoreGegenstelle2406 struct {
	srv     *httptest.Server
	mu      sync.Mutex
	anzahl  int
	versand chan smsVersand2406
}

func neueSmsCoreGegenstelle2406(t *testing.T) *smsCoreGegenstelle2406 {
	t.Helper()
	g := &smsCoreGegenstelle2406{versand: make(chan smsVersand2406, 64)}
	g.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != smsCorePfad2406 {
			http.NotFound(w, r)
			return
		}
		var v smsVersand2406
		if err := json.NewDecoder(r.Body).Decode(&v); err != nil {
			w.WriteHeader(http.StatusBadRequest)
			return
		}
		g.mu.Lock()
		g.anzahl++
		g.mu.Unlock()
		g.versand <- v
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"sent"}`))
	}))
	t.Cleanup(g.srv.Close)
	return g
}

func (g *smsCoreGegenstelle2406) zahl() int {
	g.mu.Lock()
	defer g.mu.Unlock()
	return g.anzahl
}

// smsUmgebung2406 buendelt den echten Produktions-Router mit Datenbestand und
// der Versand-Gegenstelle.
type smsUmgebung2406 struct {
	router  http.Handler
	store   *store.Store
	secret  string
	dataDir string
	core    *smsCoreGegenstelle2406
}

// neueSmsUmgebung2406 baut den ECHTEN Router (Verdrahtung wie
// cmd/server/main.go). staging=true setzt GZ_ENV=staging VOR router.New —
// router.go liest die Variable beim Bau (Staging-only-Routen). SMTP bleibt
// leer: ein Mail-Versand wird fuer diese Tests nicht gebraucht.
func neueSmsUmgebung2406(t *testing.T, staging bool) *smsUmgebung2406 {
	t.Helper()
	if staging {
		t.Setenv("GZ_ENV", "staging")
	} else {
		t.Setenv("GZ_ENV", "")
	}

	core := neueSmsCoreGegenstelle2406(t)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.SessionSecret = "sms-2406-secret-32-zeichen-okay!"
	cfg.PythonCoreURL = core.srv.URL
	cfg.SMTPHost = ""
	cfg.GoogleSMTPHost = ""
	cfg.FallbackSMTPHost = ""

	s := store.New(cfg.DataDir, cfg.UserID)

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := router.New(router.Deps{
		Config:             cfg,
		Store:              s,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test-2406",
	})
	return &smsUmgebung2406{router: r, store: s, secret: cfg.SessionSecret, dataDir: cfg.DataDir, core: core}
}

// konto legt ein Konto als ROHES user.json an — so lassen sich die neuen
// Felder (sms_verified_number, sms_verified_at, pending_sms_to) als Bestand
// vorbelegen, ohne dass der Test neue Go-Symbole braucht.
func (e *smsUmgebung2406) konto(t *testing.T, uid, tier string, felder map[string]any) {
	t.Helper()
	profil := map[string]any{
		"id":                uid,
		"email":             uid + "@beispiel.de",
		"mail_to":           uid + "-empfang@beispiel.de",
		"display_name":      "Konto " + uid,
		"tier":              tier,
		"email_verified_at": "2026-01-02T03:04:05Z",
		"created_at":        "2026-01-01T00:00:00Z",
	}
	for k, v := range felder {
		profil[k] = v
	}
	daten, err := json.MarshalIndent(profil, "", "  ")
	if err != nil {
		t.Fatalf("Profil %q serialisieren: %v", uid, err)
	}
	dir := filepath.Join(e.dataDir, "users", uid)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatalf("MkdirAll %q: %v", dir, err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), daten, 0o644); err != nil {
		t.Fatalf("user.json %q schreiben: %v", uid, err)
	}
	if err := e.store.ProvisionUserDirs(uid); err != nil {
		t.Fatalf("ProvisionUserDirs %q: %v", uid, err)
	}
}

func (e *smsUmgebung2406) cookie(t *testing.T, uid string) *http.Cookie {
	t.Helper()
	sid, err := authmw.NewSessionID()
	if err != nil {
		t.Fatalf("NewSessionID: %v", err)
	}
	if err := e.store.AddSession(uid, sid); err != nil {
		t.Fatalf("AddSession %q: %v", uid, err)
	}
	return &http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID(uid, sid, e.secret)}
}

func (e *smsUmgebung2406) anfrage(t *testing.T, methode, pfad, rumpf string, c *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(methode, pfad, strings.NewReader(rumpf))
	req.Header.Set("Content-Type", "application/json")
	if c != nil {
		req.AddCookie(c)
	}
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w
}

func (e *smsUmgebung2406) profilPut(t *testing.T, c *http.Cookie, rumpf string) *httptest.ResponseRecorder {
	t.Helper()
	return e.anfrage(t, http.MethodPut, profilPfad2406, rumpf, c)
}

func (e *smsUmgebung2406) verify(t *testing.T, c *http.Cookie, code string) *httptest.ResponseRecorder {
	t.Helper()
	return e.anfrage(t, http.MethodPost, smsVerifyPfad2406, fmt.Sprintf(`{"code":%q}`, code), c)
}

func (e *smsUmgebung2406) userPfad(uid string) string {
	return filepath.Join(e.dataDir, "users", uid, "user.json")
}

func (e *smsUmgebung2406) codeDateiPfad(uid string) string {
	return filepath.Join(e.dataDir, "users", uid, "sms_verification.json")
}

// userJSON liest user.json roh — neue Felder sind so ohne Go-Symbol pruefbar.
func (e *smsUmgebung2406) userJSON(t *testing.T, uid string) map[string]any {
	t.Helper()
	daten, err := os.ReadFile(e.userPfad(uid))
	if err != nil {
		t.Fatalf("user.json %q lesen: %v", uid, err)
	}
	var m map[string]any
	if err := json.Unmarshal(daten, &m); err != nil {
		t.Fatalf("user.json %q ist kein JSON: %v", uid, err)
	}
	return m
}

func (e *smsUmgebung2406) userBytes(t *testing.T, uid string) []byte {
	t.Helper()
	daten, err := os.ReadFile(e.userPfad(uid))
	if err != nil {
		t.Fatalf("user.json %q lesen: %v", uid, err)
	}
	return daten
}

// feld liefert einen String-Wert; fehlend und leer gelten beide als "".
func feld2406(m map[string]any, k string) string {
	v, _ := m[k].(string)
	return v
}

func antwortJSON2406(t *testing.T, w *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("Antwort ist kein JSON (%d): %q", w.Code, w.Body.String())
	}
	return m
}

func fehlerCode2406(w *httptest.ResponseRecorder) string {
	var m map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &m)
	v, _ := m["error"].(string)
	return v
}

// erwarteVersand wartet auf GENAU einen Code-Versand und prueft Ziel und Konto.
func (e *smsUmgebung2406) erwarteVersand(t *testing.T, uid, nummer, anlass string) smsVersand2406 {
	t.Helper()
	select {
	case v := <-e.core.versand:
		if v.To != nummer {
			t.Fatalf("%s: Code ging an %q, erwartet %q", anlass, v.To, nummer)
		}
		if v.UserID != uid {
			t.Fatalf("%s: Versand fuer Konto %q, erwartet %q (nie \"default\")", anlass, v.UserID, uid)
		}
		if len(v.Code) != 6 || strings.Trim(v.Code, "0123456789") != "" {
			t.Fatalf("%s: Code %q ist keine 6-stellige Ziffernfolge (Spec §3)", anlass, v.Code)
		}
		return v
	case <-time.After(smsVersandFrist2406):
		t.Fatalf("%s: KEIN Code-Versand an %q beim internen Python-Endpunkt %s angekommen "+
			"(Spec §2/§3: dispatchSmsVerificationCode)", anlass, nummer, smsCorePfad2406)
	}
	return smsVersand2406{}
}

// erwarteKeinenVersand prueft, dass innerhalb der Stille-Frist nichts ankommt.
func (e *smsUmgebung2406) erwarteKeinenVersand(t *testing.T, anlass string) {
	t.Helper()
	select {
	case v := <-e.core.versand:
		t.Fatalf("%s: unerwarteter Code-Versand an %q (Konto %q)", anlass, v.To, v.UserID)
	case <-time.After(smsStilleFrist2406):
	}
}

// andererCode2406 liefert garantiert einen falschen 6-stelligen Code.
func andererCode2406(code string) string {
	if code == "111111" {
		return "222222"
	}
	return "111111"
}

const (
	nummerA2406 = "+491511000001"
	nummerB2406 = "+491512000002"
	nummerC2406 = "+491513000003"
)

// bestaetigtA2406 ist der Bestand „Nummer A bestaetigt".
func bestaetigtA2406() map[string]any {
	return map[string]any{
		"sms_to":              nummerA2406,
		"sms_verified_number": nummerA2406,
		"sms_verified_at":     "2026-09-01T10:00:00Z",
	}
}

// ─── AC-2: E.164-Formatpruefung ──────────────────────────────────────────────

func TestSmsNummerUngueltigWirdAbgelehntUndNichtsGespeichert(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsformat"
	e.konto(t, uid, "standard", map[string]any{"sms_to": nummerA2406})
	c := e.cookie(t, uid)

	for _, ungueltig := range []string{
		"+49abc",
		"01511234567",       // kein "+"
		"+01511234567",      // fuehrende 0 nach "+"
		"+4915",             // zu kurz (< 8 Ziffern)
		"+4915112345678901", // zu lang (> 15 Ziffern)
		"+49 151 1234567",   // Leerzeichen innen
	} {
		vorher := e.userBytes(t, uid)
		w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q,"display_name":"Geaendert"}`, ungueltig))
		if w.Code != http.StatusBadRequest || fehlerCode2406(w) != "invalid_sms_number" {
			t.Errorf("AC-2: %q muss 400 {\"error\":\"invalid_sms_number\"} liefern, bekommen %d: %s",
				ungueltig, w.Code, w.Body.String())
		}
		if nachher := e.userBytes(t, uid); string(nachher) != string(vorher) {
			t.Errorf("AC-2: bei ungueltiger Nummer %q darf user.json nicht veraendert werden "+
				"(auch display_name nicht).\nvorher:  %s\nnachher: %s", ungueltig, vorher, nachher)
		}
	}
	e.erwarteKeinenVersand(t, "AC-2 ungueltige Nummern")
}

func TestSmsNummerGueltigWirdAngenommenUndCodeAnSieVersandt(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsgueltig"
	e.konto(t, uid, "standard", nil)
	c := e.cookie(t, uid)

	w := e.profilPut(t, c, `{"sms_to":"+491511234567"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-2: gueltige E.164-Nummer muss 200 liefern, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := feld2406(e.userJSON(t, uid), "sms_to"); got != "+491511234567" {
		t.Errorf("AC-2: gueltige Nummer muss gespeichert sein (Erst-Eintrag: direkt in sms_to), bekommen %q", got)
	}
	// Wirkung auf dem Versandweg: der Erst-Eintrag loest den Code an GENAU diese Nummer aus.
	e.erwarteVersand(t, uid, "+491511234567", "AC-2 gueltige Nummer")
	if _, err := os.Stat(e.codeDateiPfad(uid)); err != nil {
		t.Errorf("AC-2/§3: nach dem Code-Versand muss sms_verification.json existieren: %v", err)
	}
}

func TestSmsNummerLeerBleibtAlsEntfernenErlaubt(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsleer"
	e.konto(t, uid, "standard", map[string]any{"sms_to": nummerA2406})
	c := e.cookie(t, uid)

	// Ausgangslage: eine ungueltige Nummer wird abgewiesen …
	if w := e.profilPut(t, c, `{"sms_to":"+49abc"}`); w.Code != http.StatusBadRequest {
		t.Fatalf("AC-2: ungueltige Nummer muss 400 liefern, bekommen %d: %s", w.Code, w.Body.String())
	}
	// … der Leerstring dagegen ist „Nummer entfernen" und wird angenommen.
	w := e.profilPut(t, c, `{"sms_to":""}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-2: leerer sms_to muss als Entfernen 200 liefern, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := feld2406(e.userJSON(t, uid), "sms_to"); got != "" {
		t.Errorf("AC-2: nach Entfernen muss sms_to leer sein, bekommen %q", got)
	}
	e.erwarteKeinenVersand(t, "AC-2 Entfernen")
}

// ─── AC-3: bestaetigte Nummer bleibt wirksam, neue wartet als Pending ────────

func TestSmsBestaetigteNummerBleibtWirksamBisNeueBestaetigtIst(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smswechsel"
	e.konto(t, uid, "standard", bestaetigtA2406())
	c := e.cookie(t, uid)

	w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerB2406))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-3: PUT mit neuer Nummer B erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	antwort := antwortJSON2406(t, w)
	if feld2406(antwort, "sms_to") != nummerA2406 {
		t.Errorf("AC-3: Profil-Antwort sms_to muss bis zur Bestaetigung A bleiben, bekommen %v", antwort["sms_to"])
	}
	if antwort["sms_verified"] != true {
		t.Errorf("AC-3: Profil-Antwort sms_verified muss true bleiben (A ist bestaetigt), bekommen %v", antwort["sms_verified"])
	}
	if feld2406(antwort, "pending_sms_to") != nummerB2406 {
		t.Errorf("AC-3: Profil-Antwort pending_sms_to muss B sein, bekommen %v", antwort["pending_sms_to"])
	}
	nachPut := e.userJSON(t, uid)
	if feld2406(nachPut, "sms_to") != nummerA2406 || feld2406(nachPut, "pending_sms_to") != nummerB2406 ||
		feld2406(nachPut, "sms_verified_number") != nummerA2406 {
		t.Fatalf("AC-3 nach PUT: erwartet sms_to=A, pending_sms_to=B, sms_verified_number=A — user.json: %v", nachPut)
	}

	v := e.erwarteVersand(t, uid, nummerB2406, "AC-3 Wechsel auf B")

	wv := e.verify(t, c, v.Code)
	if wv.Code != http.StatusOK {
		t.Fatalf("AC-3: POST %s mit korrektem Code erwartet 200, bekommen %d: %s", smsVerifyPfad2406, wv.Code, wv.Body.String())
	}
	nachVerify := e.userJSON(t, uid)
	if feld2406(nachVerify, "sms_to") != nummerB2406 {
		t.Errorf("AC-3 nach Bestaetigung: sms_to muss B sein, bekommen %q", feld2406(nachVerify, "sms_to"))
	}
	if feld2406(nachVerify, "pending_sms_to") != "" {
		t.Errorf("AC-3 nach Bestaetigung: pending_sms_to muss geleert sein, bekommen %q", feld2406(nachVerify, "pending_sms_to"))
	}
	if feld2406(nachVerify, "sms_verified_number") != nummerB2406 {
		t.Errorf("AC-3 nach Bestaetigung: sms_verified_number muss B sein, bekommen %q", feld2406(nachVerify, "sms_verified_number"))
	}
	if feld2406(nachVerify, "sms_verified_at") == "" {
		t.Errorf("AC-3 nach Bestaetigung: sms_verified_at muss gesetzt sein")
	}
	if _, err := os.Stat(e.codeDateiPfad(uid)); !os.IsNotExist(err) {
		t.Errorf("AC-3/§4: nach erfolgreicher Bestaetigung muss sms_verification.json geloescht sein (err=%v)", err)
	}
}

// ─── AC-4: Ablauf, Fehlversuche, fremde Nummer ───────────────────────────────

func TestSmsCodeNachAblaufScheitertMitCodeExpired(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsablauf"
	e.konto(t, uid, "standard", nil)
	c := e.cookie(t, uid)

	vorPut := time.Now()
	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-4a: PUT erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	v := e.erwarteVersand(t, uid, nummerA2406, "AC-4a Erst-Eintrag")

	// Die Gueltigkeit ist 10 Minuten (Spec §3).
	roh, err := os.ReadFile(e.codeDateiPfad(uid))
	if err != nil {
		t.Fatalf("AC-4a: sms_verification.json fehlt nach Versand: %v", err)
	}
	var datei map[string]any
	if err := json.Unmarshal(roh, &datei); err != nil {
		t.Fatalf("AC-4a: sms_verification.json kein JSON: %v", err)
	}
	ablauf, err := time.Parse(time.RFC3339Nano, feld2406(datei, "expires_at"))
	if err != nil {
		t.Fatalf("AC-4a: expires_at nicht lesbar: %v (%s)", err, roh)
	}
	if d := ablauf.Sub(vorPut); d < 9*time.Minute+50*time.Second || d > 10*time.Minute+10*time.Second {
		t.Errorf("AC-4a: Code muss 10 Minuten gueltig sein, gueltig fuer %v", d)
	}
	if feld2406(datei, "number") != nummerA2406 {
		t.Errorf("AC-4a/§1: der Code muss an die Nummer gebunden sein (number=%q), bekommen %q", nummerA2406, feld2406(datei, "number"))
	}
	if strings.Contains(string(roh), v.Code) {
		t.Errorf("AC-4a/§3: sms_verification.json darf den Klartext-Code nicht enthalten (nur bcrypt-Hash)")
	}

	// 10 Minuten und 1 Sekunde vorspulen.
	datei["expires_at"] = time.Now().Add(-time.Second).UTC().Format(time.RFC3339Nano)
	neu, _ := json.Marshal(datei)
	if err := os.WriteFile(e.codeDateiPfad(uid), neu, 0o644); err != nil {
		t.Fatalf("AC-4a: Ablauf vorspulen: %v", err)
	}

	w := e.verify(t, c, v.Code)
	if w.Code != http.StatusBadRequest || fehlerCode2406(w) != "code_expired" {
		t.Errorf("AC-4a: abgelaufener (sonst korrekter) Code erwartet 400 code_expired, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := feld2406(e.userJSON(t, uid), "sms_verified_number"); got != "" {
		t.Errorf("AC-4a: sms_verified_number darf nach abgelaufenem Code nicht gesetzt sein, bekommen %q", got)
	}
}

func TestSmsCodeFuenfFehlversucheEntwertenAuchDenRichtigen(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsfehlversuch"
	e.konto(t, uid, "standard", nil)
	c := e.cookie(t, uid)

	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-4b: PUT erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	v := e.erwarteVersand(t, uid, nummerA2406, "AC-4b Erst-Eintrag")
	falsch := andererCode2406(v.Code)

	for i := 1; i <= 5; i++ {
		w := e.verify(t, c, falsch)
		if w.Code != http.StatusBadRequest || fehlerCode2406(w) != "invalid_code" {
			t.Fatalf("AC-4b: Fehlversuch %d erwartet 400 invalid_code, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	// Nach dem fuenften Fehlversuch ist der Code verbrannt — auch der RICHTIGE scheitert.
	w := e.verify(t, c, v.Code)
	if w.Code != http.StatusBadRequest || fehlerCode2406(w) != "code_expired" {
		t.Errorf("AC-4b: richtiger Code nach 5 Fehlversuchen erwartet 400 code_expired, bekommen %d: %s", w.Code, w.Body.String())
	}
	if _, err := os.Stat(e.codeDateiPfad(uid)); !os.IsNotExist(err) {
		t.Errorf("AC-4b/§4: nach dem 5. Fehlversuch muss sms_verification.json geloescht sein (err=%v)", err)
	}
	if got := feld2406(e.userJSON(t, uid), "sms_verified_number"); got != "" {
		t.Errorf("AC-4b: sms_verified_number darf nicht gesetzt sein, bekommen %q", got)
	}
}

// AC-4c: ein Code, der an eine FREMDE Nummer gebunden ist (manipulierte
// sms_verification.json: Hash passt zum eingegebenen Code, `number` gehoert
// aber weder zu sms_to noch zu pending_sms_to), darf die Nummer des Kontos
// nicht bestaetigen.
func TestSmsCodeFuerFremdeNummerBestaetigtNicht(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsfremd"
	e.konto(t, uid, "standard", map[string]any{"sms_to": nummerA2406})
	c := e.cookie(t, uid)

	const code = "424242"
	hash, err := bcrypt.GenerateFromPassword([]byte(code), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	manipuliert, _ := json.Marshal(map[string]any{
		"code_hash":  string(hash),
		"expires_at": time.Now().Add(5 * time.Minute).UTC().Format(time.RFC3339Nano),
		"number":     nummerC2406,
	})
	if err := os.WriteFile(e.codeDateiPfad(uid), manipuliert, 0o644); err != nil {
		t.Fatalf("manipulierte sms_verification.json schreiben: %v", err)
	}

	w := e.verify(t, c, code)
	if w.Code == http.StatusNotFound || w.Code == http.StatusMethodNotAllowed {
		t.Fatalf("AC-4c: Route %s fehlt (%d)", smsVerifyPfad2406, w.Code)
	}
	if w.Code != http.StatusBadRequest || fehlerCode2406(w) != "invalid_code" {
		t.Errorf("AC-4c: Code fuer fremde Nummer %s erwartet 400 invalid_code, bekommen %d: %s", nummerC2406, w.Code, w.Body.String())
	}
	if got := feld2406(e.userJSON(t, uid), "sms_verified_number"); got != "" {
		t.Errorf("AC-4c: sms_verified_number darf nicht gesetzt sein, bekommen %q", got)
	}
}

// ─── AC-7: Tier-Gate an BEIDEN Entry-Points ──────────────────────────────────

func TestSmsFreeTarifVersendetAnKeinemEintrittspunkt(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsfree"
	e.konto(t, uid, "free", nil)
	c := e.cookie(t, uid)

	w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-7a: Free-Konto darf die Nummer eintragen (200), bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := feld2406(e.userJSON(t, uid), "sms_to"); got != nummerA2406 {
		t.Errorf("AC-7a: Nummer muss gespeichert sein (direkt, keine bestaetigte Vorgaengerin), bekommen %q", got)
	}
	e.erwarteKeinenVersand(t, "AC-7a Profil-Update Free")

	wr := e.anfrage(t, http.MethodPost, smsResendPfad2406, `{}`, c)
	if wr.Code != http.StatusBadRequest || fehlerCode2406(wr) != "sms_not_allowed" {
		t.Errorf("AC-7b: Resend im Free-Tarif erwartet 400 {\"error\":\"sms_not_allowed\"}, bekommen %d: %s", wr.Code, wr.Body.String())
	}
	e.erwarteKeinenVersand(t, "AC-7b Resend Free")
	if n := e.core.zahl(); n != 0 {
		t.Errorf("AC-7: Versand-Endpunkt darf im Free-Tarif nie gerufen werden, gerufen: %d", n)
	}
}

// §4 Gegenprobe zu AC-7: im SMS-faehigen Tarif versendet Resend an die
// ausstehende Nummer; ohne Nummer antwortet er no_number.
func TestSmsResendVersendetAnAusstehendeNummer(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsresend"
	e.konto(t, uid, "standard", bestaetigtA2406())
	c := e.cookie(t, uid)

	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerB2406)); w.Code != http.StatusOK {
		t.Fatalf("PUT erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	erster := e.erwarteVersand(t, uid, nummerB2406, "§4 Wechsel auf B")

	wr := e.anfrage(t, http.MethodPost, smsResendPfad2406, `{}`, c)
	if wr.Code != http.StatusOK {
		t.Fatalf("§4: Resend erwartet 200, bekommen %d: %s", wr.Code, wr.Body.String())
	}
	zweiter := e.erwarteVersand(t, uid, nummerB2406, "§4 Resend an pending_sms_to")

	// Der neue Code ersetzt den alten (Datei wird ueberschrieben).
	if erster.Code != zweiter.Code {
		if w := e.verify(t, c, erster.Code); w.Code == http.StatusOK {
			t.Errorf("§4: nach Resend darf der ALTE Code nicht mehr bestaetigen")
		}
	}
	if w := e.verify(t, c, zweiter.Code); w.Code != http.StatusOK {
		t.Errorf("§4: der per Resend versandte Code muss bestaetigen, bekommen %d: %s", w.Code, w.Body.String())
	}

	const ohne = "smsohnenummer"
	e.konto(t, ohne, "standard", nil)
	wo := e.anfrage(t, http.MethodPost, smsResendPfad2406, `{}`, e.cookie(t, ohne))
	if wo.Code != http.StatusBadRequest || fehlerCode2406(wo) != "no_number" {
		t.Errorf("§4: Resend ohne Nummer erwartet 400 no_number, bekommen %d: %s", wo.Code, wo.Body.String())
	}
}

// ─── AC-8: zwei Konten, B traegt A's Nummer ein ─────────────────────────────

func TestSmsFremdeNummerErreichtNurDasGeraetUndBleibtUnbestaetigt(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uidA, uidB = "smsbesitzera", "smsangreiferb"
	e.konto(t, uidA, "standard", bestaetigtA2406())
	e.konto(t, uidB, "standard", nil)
	vorherA := e.userBytes(t, uidA)
	cB := e.cookie(t, uidB)

	w := e.profilPut(t, cB, fmt.Sprintf(`{"sms_to":%q}`, nummerA2406))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-8: B darf die Nummer eintragen (200), bekommen %d: %s", w.Code, w.Body.String())
	}
	// Der Code geht an die NUMMER (A's Geraet), ausgeloest fuer Konto B — nie "default".
	v := e.erwarteVersand(t, uidB, nummerA2406, "AC-8 B traegt A's Nummer ein")

	// B kennt den Code nicht; ein geratener Code bestaetigt nicht.
	if wv := e.verify(t, cB, andererCode2406(v.Code)); wv.Code != http.StatusBadRequest {
		t.Errorf("AC-8: geratener Code von B erwartet 400, bekommen %d: %s", wv.Code, wv.Body.String())
	}
	b := e.userJSON(t, uidB)
	if feld2406(b, "sms_verified_number") != "" {
		t.Errorf("AC-8: B's sms_verified_number muss leer bleiben, bekommen %q", feld2406(b, "sms_verified_number"))
	}
	wg := e.anfrage(t, http.MethodGet, profilPfad2406, "", cB)
	if p := antwortJSON2406(t, wg); p["sms_verified"] != false {
		t.Errorf("AC-8: B's Profil muss sms_verified=false zeigen, bekommen %v", p["sms_verified"])
	}
	if nachherA := e.userBytes(t, uidA); string(nachherA) != string(vorherA) {
		t.Errorf("AC-8: A's Konto darf durch B's Eintrag nicht veraendert werden.\nvorher:  %s\nnachher: %s", vorherA, nachherA)
	}
	if _, err := os.Stat(e.codeDateiPfad(uidA)); !os.IsNotExist(err) {
		t.Errorf("AC-8: fuer A darf keine sms_verification.json entstehen (err=%v)", err)
	}
}

// ─── AC-9: Entfernen raeumt vollstaendig auf ─────────────────────────────────

func TestSmsNummerEntfernenRaeumtAlleFelderUndCodeAuf(t *testing.T) {
	faelle := []struct {
		name    string
		uid     string
		bestand map[string]any
		neu     string
		ziel    string
	}{
		{"unbestaetigter_erst_eintrag", "smsentfneu", nil, nummerA2406, nummerA2406},
		{"ausstehende_nummer", "smsentfpending", bestaetigtA2406(), nummerB2406, nummerB2406},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			e := neueSmsUmgebung2406(t, false)
			uid := f.uid
			e.konto(t, uid, "standard", f.bestand)
			c := e.cookie(t, uid)

			if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, f.neu)); w.Code != http.StatusOK {
				t.Fatalf("AC-9: PUT erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
			}
			v := e.erwarteVersand(t, uid, f.ziel, "AC-9 Vorbereitung")
			if _, err := os.Stat(e.codeDateiPfad(uid)); err != nil {
				t.Fatalf("AC-9 Vorbereitung: sms_verification.json muss nach dem Versand existieren: %v", err)
			}

			if w := e.profilPut(t, c, `{"sms_to":""}`); w.Code != http.StatusOK {
				t.Fatalf("AC-9: Entfernen erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
			}
			u := e.userJSON(t, uid)
			for _, k := range []string{"sms_to", "pending_sms_to", "sms_verified_number", "sms_verified_at"} {
				if feld2406(u, k) != "" {
					t.Errorf("AC-9: %s muss nach dem Entfernen leer sein, bekommen %q", k, feld2406(u, k))
				}
			}
			if _, err := os.Stat(e.codeDateiPfad(uid)); !os.IsNotExist(err) {
				t.Errorf("AC-9: sms_verification.json muss nach dem Entfernen geloescht sein (err=%v)", err)
			}
			// Der alte Code kann die entfernte Nummer nicht mehr bestaetigen.
			if w := e.verify(t, c, v.Code); w.Code != http.StatusBadRequest || fehlerCode2406(w) != "code_expired" {
				t.Errorf("AC-9: alter Code nach Entfernen erwartet 400 code_expired, bekommen %d: %s", w.Code, w.Body.String())
			}
		})
	}
}

// ─── AC-13 (Go-Teil): Profil-Antwort traegt pending_sms_to und sms_verified ──

func TestSmsProfilAntwortTraegtPendingUndVerifiedFlag(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const mitPending, unbestaetigt = "smsprofilpend", "smsprofilunb"
	bestand := bestaetigtA2406()
	bestand["pending_sms_to"] = nummerB2406
	e.konto(t, mitPending, "standard", bestand)
	e.konto(t, unbestaetigt, "standard", map[string]any{"sms_to": nummerA2406})

	p := antwortJSON2406(t, e.anfrage(t, http.MethodGet, profilPfad2406, "", e.cookie(t, mitPending)))
	if feld2406(p, "pending_sms_to") != nummerB2406 {
		t.Errorf("AC-13: GET-Antwort muss pending_sms_to=%q enthalten, bekommen %v", nummerB2406, p["pending_sms_to"])
	}
	if v, ok := p["sms_verified"].(bool); !ok || !v {
		t.Errorf("AC-13: GET-Antwort muss sms_verified=true (Bool) enthalten, bekommen %v (vorhanden=%v)", p["sms_verified"], ok)
	}

	q := antwortJSON2406(t, e.anfrage(t, http.MethodGet, profilPfad2406, "", e.cookie(t, unbestaetigt)))
	if v, ok := q["sms_verified"].(bool); !ok || v {
		t.Errorf("AC-13: unbestaetigtes Konto muss sms_verified=false als Bool ENTHALTEN (kein omitempty), bekommen %v (vorhanden=%v)", q["sms_verified"], ok)
	}
}

// ─── AC-16: dritte Nummer ersetzt die ausstehende vollstaendig ──────────────

func TestSmsDritteNummerEntwertetCodeDerZweiten(t *testing.T) {
	e := neueSmsUmgebung2406(t, false)
	const uid = "smsdritte"
	e.konto(t, uid, "standard", bestaetigtA2406())
	c := e.cookie(t, uid)

	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerB2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-16: PUT B erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	codeB := e.erwarteVersand(t, uid, nummerB2406, "AC-16 Wechsel auf B").Code

	// Zwei Fehlversuche auf B — der Zaehler muss mit dem Wechsel auf C verfallen.
	for i := 0; i < 2; i++ {
		e.verify(t, c, andererCode2406(codeB))
	}

	if w := e.profilPut(t, c, fmt.Sprintf(`{"sms_to":%q}`, nummerC2406)); w.Code != http.StatusOK {
		t.Fatalf("AC-16: PUT C erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	codeC := e.erwarteVersand(t, uid, nummerC2406, "AC-16 Wechsel auf C").Code

	u := e.userJSON(t, uid)
	if feld2406(u, "pending_sms_to") != nummerC2406 || feld2406(u, "sms_to") != nummerA2406 {
		t.Fatalf("AC-16: C muss B als pending_sms_to vollstaendig ersetzen (sms_to bleibt A) — user.json: %v", u)
	}
	roh, err := os.ReadFile(e.codeDateiPfad(uid))
	if err != nil {
		t.Fatalf("AC-16: sms_verification.json fehlt: %v", err)
	}
	var datei map[string]any
	_ = json.Unmarshal(roh, &datei)
	if feld2406(datei, "number") != nummerC2406 {
		t.Errorf("AC-16: sms_verification.json muss auf C zeigen, zeigt auf %q", feld2406(datei, "number"))
	}
	if n, _ := datei["failed_attempts"].(float64); n != 0 {
		t.Errorf("AC-16: Fehlversuchszaehler muss mit dem neuen Code verfallen, steht auf %v", n)
	}

	if codeB != codeC {
		// Spec-AC-16 nennt code_expired; nach §4 ergibt ein nicht passender Code
		// gegen die auf C zeigende Datei invalid_code. Zugesichert wird hier der
		// Kern: 400 mit einem der beiden Codes, B wird NICHT bestaetigt.
		w := e.verify(t, c, codeB)
		if w.Code != http.StatusBadRequest || (fehlerCode2406(w) != "code_expired" && fehlerCode2406(w) != "invalid_code") {
			t.Errorf("AC-16: B-Code nach Wechsel auf C erwartet 400 code_expired/invalid_code, bekommen %d: %s", w.Code, w.Body.String())
		}
		if got := feld2406(e.userJSON(t, uid), "sms_verified_number"); got != nummerA2406 {
			t.Errorf("AC-16: B-Code darf nichts bestaetigen — sms_verified_number muss A bleiben, bekommen %q", got)
		}
	}

	w := e.verify(t, c, codeC)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-16: C-Code erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	u = e.userJSON(t, uid)
	if feld2406(u, "sms_to") != nummerC2406 || feld2406(u, "sms_verified_number") != nummerC2406 {
		t.Errorf("AC-16: nach C-Bestaetigung erwartet sms_to=C und sms_verified_number=C — user.json: %v", u)
	}
}
