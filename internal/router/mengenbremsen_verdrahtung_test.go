package router

// Issue #2961 (ADR-0114 Punkt 3): Mengenbremsen je Nutzer, gemessen am ECHTEN
// Produktions-Router mit einem httptest-Ersatz-Core, der jede eingetroffene
// Anfrage zaehlt. Spec docs/specs/modules/security_haertung_2026_11_go_schnittstellen.md
// (AC-11 bis AC-17).

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

type bremsUmgebung struct {
	r      http.Handler
	s      *store.Store
	secret string
	core   *atomic.Int64
	// halt (falls gesetzt) blockiert den Ersatz-Core, bis er geschlossen wird.
	halt chan struct{}
	// empfangen haelt RequestURI und user_id-Werte jeder Core-Anfrage fest.
	empfMu    sync.Mutex
	empfangen []coreEmpfang
}

type coreEmpfang struct {
	uri     string
	path    string
	userIDs []string
}

func (e *bremsUmgebung) empfang() []coreEmpfang {
	e.empfMu.Lock()
	defer e.empfMu.Unlock()
	return append([]coreEmpfang(nil), e.empfangen...)
}

func neueBremsUmgebung(t *testing.T, mutiere func(*config.Config)) *bremsUmgebung {
	t.Helper()
	e := &bremsUmgebung{core: &atomic.Int64{}}
	var haltMu sync.Mutex
	core := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		e.core.Add(1)
		e.empfMu.Lock()
		e.empfangen = append(e.empfangen, coreEmpfang{uri: r.RequestURI, path: r.URL.Path, userIDs: r.URL.Query()["user_id"]})
		e.empfMu.Unlock()
		haltMu.Lock()
		h := e.halt
		haltMu.Unlock()
		if h != nil {
			<-h
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	}))
	t.Cleanup(core.Close)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.PythonCoreURL = core.URL
	cfg.TestFixtureDir = ""
	cfg.Env = ""
	cfg.AdminUserIDs = ""
	cfg.QuotaExemptUserIDs = ""
	if mutiere != nil {
		mutiere(cfg)
	}
	s := store.New(cfg.DataDir, cfg.UserID)
	wa, err := webauthn.New(&webauthn.Config{RPID: cfg.WebAuthnRPID, RPDisplayName: "t", RPOrigins: []string{"http://localhost:5173"}})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}
	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)
	e.r = New(Deps{Config: cfg, Store: s, WebAuthn: wa, ChallengeStore: handler.NewChallengeStore(),
		Scheduler: sched, TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir), GitCommit: "test"})
	e.s, e.secret = s, cfg.SessionSecret
	return e
}

func (e *bremsUmgebung) konto(t *testing.T, uid, sprache string) *http.Cookie {
	t.Helper()
	jetzt := time.Now()
	if err := e.s.SaveUser(model.User{ID: uid, Email: uid + "@beispiel.de", EmailVerifiedAt: &jetzt,
		CreatedAt: jetzt, Language: sprache}); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	if err := e.s.AddSession(uid, sessionIDFor(uid)); err != nil {
		t.Fatalf("AddSession: %v", err)
	}
	return sessionCookieFor(uid, e.secret)
}

func (e *bremsUmgebung) rufe(t *testing.T, method, pfad string, body []byte, c *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	return doBriefingRequest(t, e.r, method, pfad, body, c)
}

func erwarte429(t *testing.T, w *httptest.ResponseRecorder, variante string) {
	t.Helper()
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}
	ra, err := strconv.Atoi(w.Header().Get("Retry-After"))
	if err != nil || ra < 1 {
		t.Fatalf("Retry-After fehlt oder ungueltig: %q", w.Header().Get("Retry-After"))
	}
	var body map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &body); err != nil {
		t.Fatalf("Fehlerobjekt unlesbar: %v", err)
	}
	if body["code"] != "rate_limit_exceeded" {
		t.Fatalf("code = %v, erwartet rate_limit_exceeded", body["code"])
	}
	msg, _ := body["message"].(string)
	if msg == "" || strings.HasPrefix(msg, "Unbekannter Fehler") || strings.HasPrefix(msg, "Unknown error") {
		t.Fatalf("kein Katalogtext fuer Variante %s: %q", variante, msg)
	}
}

// AC-12: Handversand ueber alle drei Routen teilt EIN Kontingent von 20/h;
// der 21. Versand erreicht den Core nicht. Ein zweiter Nutzer ist unberuehrt.
func TestMengenbremse_HandversandGeteilt20JeStunde(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	anna := e.konto(t, "anna-bremse", "de")
	bert := e.konto(t, "bert-bremse", "de")

	pfade := []string{"/api/trips/t1/send", "/api/compare/presets/p1/send", "/api/briefings/t1/send?kind=route"}
	for i := 0; i < handler.BremseVersandJeStunde; i++ {
		w := e.rufe(t, http.MethodPost, pfade[i%3], nil, anna)
		if w.Code == http.StatusTooManyRequests {
			t.Fatalf("Versand %d vorzeitig gebremst", i+1)
		}
	}
	vorher := e.core.Load()
	erwarte429(t, e.rufe(t, http.MethodPost, pfade[0], nil, anna), "versand")
	if e.core.Load() != vorher {
		t.Fatal("gebremster Versand hat den Core dennoch erreicht")
	}
	if w := e.rufe(t, http.MethodPost, pfade[1], nil, bert); w.Code == http.StatusTooManyRequests {
		t.Fatal("zweiter Nutzer wurde von der Bremse des ersten getroffen")
	}
}

// AC-11: Kanal-Testnachricht 10/h, Meldung in der Sprache des Nutzers.
func TestMengenbremse_Testnachricht10JeStundeZweisprachig(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	clara := e.konto(t, "clara-bremse", "en")
	for i := 0; i < handler.BremseTestnachrichtJeStunde; i++ {
		if w := e.rufe(t, http.MethodPost, "/api/notify/test", []byte(`{"channel":"telegram"}`), clara); w.Code == http.StatusTooManyRequests {
			t.Fatalf("Testnachricht %d vorzeitig gebremst", i+1)
		}
	}
	w := e.rufe(t, http.MethodPost, "/api/notify/test", []byte(`{"channel":"telegram"}`), clara)
	erwarte429(t, w, "testnachricht")
	if !strings.Contains(w.Body.String(), "test messages") {
		t.Fatalf("englischer Katalogtext erwartet: %s", w.Body.String())
	}
}

// AC-13: Ortsaufloesung 30/min.
func TestMengenbremse_Ortsaufloesung30JeMinute(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	dora := e.konto(t, "dora-bremse", "de")
	body := []byte(`{"input":"<trkpt lat=\"47.1\" lon=\"11.1\"><ele>1000</ele></trkpt>"}`)
	for i := 0; i < handler.BremseAufloesenJeMinute; i++ {
		if w := e.rufe(t, http.MethodPost, "/api/locations/resolve", body, dora); w.Code != http.StatusOK {
			t.Fatalf("Aufloesung %d: %d %s", i+1, w.Code, w.Body.String())
		}
	}
	erwarte429(t, e.rufe(t, http.MethodPost, "/api/locations/resolve", body, dora), "aufloesen")
}

// AC-14: GET /api/compare 60/min.
func TestMengenbremse_Vergleich60JeMinute(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	emil := e.konto(t, "emil-bremse", "de")
	for i := 0; i < handler.BremseAbrufJeMinute; i++ {
		if w := e.rufe(t, http.MethodGet, "/api/compare?location_ids=a", nil, emil); w.Code == http.StatusTooManyRequests {
			t.Fatalf("Abruf %d vorzeitig gebremst", i+1)
		}
	}
	erwarte429(t, e.rufe(t, http.MethodGet, "/api/compare?location_ids=a", nil, emil), "abruf")
	// Eigenes Fenster je Route: die Vorschau ist davon unberuehrt.
	if w := e.rufe(t, http.MethodGet, "/api/preview/t1/sms", nil, emil); w.Code == http.StatusTooManyRequests {
		t.Fatal("Vorschau teilt faelschlich das Minutenfenster des Vergleichs")
	}
}

// AC-14: hoechstens 4 gleichzeitige schwere Abrufe je Nutzer (ueber
// Vergleich, Etappenwetter und Vorschau hinweg).
func TestMengenbremse_HoechstensVierGleichzeitig(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	frida := e.konto(t, "frida-bremse", "de")
	gustav := e.konto(t, "gustav-bremse", "de")
	e.halt = make(chan struct{})

	pfade := []string{"/api/compare?location_ids=a", "/api/trips/t1/stages/weather", "/api/preview/t1/sms", "/api/compare?location_ids=b"}
	var wg sync.WaitGroup
	for _, p := range pfade {
		wg.Add(1)
		go func(p string) { defer wg.Done(); e.rufe(t, http.MethodGet, p, nil, frida) }(p)
	}
	deadline := time.Now().Add(5 * time.Second)
	for e.core.Load() < 4 && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	if e.core.Load() != 4 {
		t.Fatalf("Messaufbau: %d laufende Abrufe, erwartet 4", e.core.Load())
	}
	erwarte429(t, e.rufe(t, http.MethodGet, "/api/trips/t1/stages/weather", nil, frida), "parallel")

	// Ein anderer Nutzer ist nicht betroffen.
	done := make(chan int, 1)
	go func() { done <- e.rufe(t, http.MethodGet, "/api/compare?location_ids=c", nil, gustav).Code }()
	for e.core.Load() < 5 && time.Now().Before(deadline) {
		time.Sleep(5 * time.Millisecond)
	}
	close(e.halt)
	wg.Wait()
	if c := <-done; c == http.StatusTooManyRequests {
		t.Fatal("zweiter Nutzer wurde von der Parallel-Grenze des ersten getroffen")
	}
	// Nach dem Ende der Abrufe ist wieder Platz.
	if w := e.rufe(t, http.MethodGet, "/api/trips/t1/stages/weather", nil, frida); w.Code == http.StatusTooManyRequests {
		t.Fatalf("Parallel-Plaetze wurden nicht freigegeben: %s", w.Body.String())
	}
}

// AC-15: GPX-Upload 30/h und hoechstens 10 MB.
func TestMengenbremse_GpxGroesseUndMenge(t *testing.T) {
	e := neueBremsUmgebung(t, nil)
	hanna := e.konto(t, "hanna-bremse", "de")

	gross := bytes.Repeat([]byte("x"), 10<<20+1)
	vorher := e.core.Load()
	w := e.rufe(t, http.MethodPost, "/api/gpx/parse", gross, hanna)
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("GPX > 10 MB: erwartet 413, bekommen %d", w.Code)
	}
	if e.core.Load() != vorher {
		t.Fatal("zu grosser GPX-Rumpf hat den Core erreicht")
	}
	// Der zu grosse Rumpf scheitert an der Rumpfgrenze des Routers, bevor die
	// Mengenbremse zaehlt; er verbraucht deshalb keinen Platz im Stundenfenster.
	for i := 0; i < handler.BremseGpxJeStunde; i++ {
		if w := e.rufe(t, http.MethodPost, "/api/gpx/parse", []byte("<gpx/>"), hanna); w.Code != http.StatusOK {
			t.Fatalf("GPX %d: %d %s", i+1, w.Code, w.Body.String())
		}
	}
	erwarte429(t, e.rufe(t, http.MethodPost, "/api/gpx/parse", []byte("<gpx/>"), hanna), "gpx")
}

// AC-16: Admins und Kennungen aus GZ_QUOTA_EXEMPT_USER_IDS sind ausgenommen.
func TestMengenbremse_AdminUndAusnahmelisteUngebremst(t *testing.T) {
	e := neueBremsUmgebung(t, func(c *config.Config) {
		c.AdminUserIDs = "ida-admin"
		c.QuotaExemptUserIDs = "jan-ausnahme"
	})
	for _, uid := range []string{"ida-admin", "jan-ausnahme"} {
		c := e.konto(t, uid, "de")
		for i := 0; i < handler.BremseVersandJeStunde+5; i++ {
			if w := e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, c); w.Code == http.StatusTooManyRequests {
				t.Fatalf("%s: Versand %d gebremst, obwohl ausgenommen", uid, i+1)
			}
		}
	}
}

// AC-17: im Fixture-Modus (CI-Stack) sind die Bremsen nicht eingehaengt.
func TestMengenbremse_FixtureModusOhneBremse(t *testing.T) {
	e := neueBremsUmgebung(t, func(c *config.Config) { c.TestFixtureDir = t.TempDir() })
	karl := e.konto(t, "karl-bremse", "de")
	for i := 0; i < handler.BremseVersandJeStunde+5; i++ {
		if w := e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, karl); w.Code == http.StatusTooManyRequests {
			t.Fatalf("Fixture-Modus: Versand %d gebremst", i+1)
		}
	}
}

// AC-24: auf Staging gelten die zehnfachen Grenzen — der 21. Sofort-Versand
// in der Stunde geht durch (E2E/Validator ohne Ausnahme-Eintrag), in
// Produktion wird er gebremst; auch auf Staging gibt es eine Obergrenze.
func TestMengenbremse_StagingZehnfacheGrenzen(t *testing.T) {
	for _, fall := range []struct {
		env, uid string
		gebremst bool
	}{{"staging", "lena-staging", false}, {"", "lena-prod", true}} {
		e := neueBremsUmgebung(t, func(c *config.Config) { c.Env = fall.env })
		c := e.konto(t, fall.uid, "de")
		for i := 0; i < handler.BremseVersandJeStunde; i++ {
			if w := e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, c); w.Code == http.StatusTooManyRequests {
				t.Fatalf("Env %q: Versand %d vorzeitig gebremst", fall.env, i+1)
			}
		}
		w := e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, c)
		if fall.gebremst {
			erwarte429(t, w, "versand")
		} else if w.Code == http.StatusTooManyRequests {
			t.Fatalf("Staging: 21. Versand gebremst: %s", w.Body.String())
		}
	}
	e := neueBremsUmgebung(t, func(c *config.Config) { c.Env = "staging" })
	c := e.konto(t, "lena-obergrenze", "de")
	for i := 0; i < handler.BremseVersandJeStunde*handler.BremseStagingFaktor; i++ {
		e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, c)
	}
	erwarte429(t, e.rufe(t, http.MethodPost, "/api/trips/t1/send", nil, c), "versand")
}
