package router

// TDD RED — Staging-only Seed-Endpoint fuer Tarif und SMS-Tageszaehler
// (Issue #2423). Spec: docs/specs/modules/staging_seed_endpoint.md
// (AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7 Go-Roundtrip, AC-11, AC-12).
//
// Gebaut wird der ECHTE Produktions-Router (Deps-Verdrahtung wie
// cmd/server/main.go) inklusive AuthMiddleware. Nur der Python-Core ist ein
// Testdouble (httptest-Server, ersetzt cfg.PythonCoreURL): er haelt den
// Zaehlerstand je Nutzer im Speicher und beantwortet den Leseweg. Der ECHTE
// Python-Schreib-/Lesepfad (Format, Lock, Tageswechsel) ist in
// tests/tdd/test_staging_seed_endpoint.py bewacht; hier geht es um die
// Go-Seite: Sperre, Anmeldepflicht, Nutzerkennung, Merge, Validierung,
// Reihenfolge, Fehlerabbildung.
//
// RED heute: die Route POST /api/auth/staging-seed ist nirgends registriert
// -> 404 auch in Staging-Lage.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

const seedPath = "/api/auth/staging-seed"

// fakeCore ist der Python-Core als Testdouble: haelt {sms, premium_sms} je
// user_id und beantwortet Schreib- und Leseweg. `fail` laesst den Schreibweg
// mit 500 antworten.
type fakeCore struct {
	mu       sync.Mutex
	counters map[string][2]int
	seedCall []map[string]any
	fail     bool
	s        *store.Store
}

func (f *fakeCore) handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/_internal/sms/seed-daily-usage", func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		defer f.mu.Unlock()
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		f.seedCall = append(f.seedCall, body)
		if f.fail {
			http.Error(w, "boom", http.StatusInternalServerError)
			return
		}
		uid, _ := body["user_id"].(string)
		c := f.counters[uid]
		if v, ok := body["sms"].(float64); ok {
			c[0] = int(v)
		}
		if v, ok := body["premium_sms"].(float64); ok {
			c[1] = int(v)
		}
		f.counters[uid] = c
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]int{"sms": c[0], "premium_sms": c[1]})
	})
	mux.HandleFunc("/api/_internal/sms/daily-usage", func(w http.ResponseWriter, r *http.Request) {
		f.mu.Lock()
		defer f.mu.Unlock()
		uid := r.URL.Query().Get("user_id")
		c := f.counters[uid]
		smsLimit, premLimit := 0, 0
		if u, _ := f.s.LoadUser(uid); u != nil {
			switch u.Tier {
			case "standard":
				smsLimit = 10
			case "premium":
				smsLimit, premLimit = 10, 15
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"sms":         map[string]int{"used": c[0], "limit": smsLimit},
			"premium_sms": map[string]int{"used": c[1], "limit": premLimit},
		})
	})
	return mux
}

// newSeedRouter baut den Produktions-Router; env "" = Produktionslage.
func newSeedRouter(t *testing.T, gzEnv string, coreURL func(*fakeCore) string) (http.Handler, *store.Store, string, *fakeCore) {
	t.Helper()
	t.Setenv("GZ_ENV", gzEnv)

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	s := store.New(cfg.DataDir, cfg.UserID)

	core := &fakeCore{counters: map[string][2]int{}, s: s}
	srv := httptest.NewServer(core.handler())
	t.Cleanup(srv.Close)
	if coreURL != nil {
		cfg.PythonCoreURL = coreURL(core)
	} else {
		cfg.PythonCoreURL = srv.URL
	}

	for _, id := range []string{"seedA", "seedB"} {
		if err := s.SaveUser(model.User{ID: id, Tier: "free", CreatedAt: time.Now()}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
		if err := s.AddSession(id, sessionIDFor(id)); err != nil {
			t.Fatalf("AddSession %s: %v", id, err)
		}
	}

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

	r := New(Deps{
		Config:             cfg,
		Store:              s,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})
	return r, s, cfg.SessionSecret, core
}

func postSeed(t *testing.T, r http.Handler, uid, secret string, body string) *httptest.ResponseRecorder {
	t.Helper()
	return doBriefingRequest(t, r, http.MethodPost, seedPath, []byte(body), sessionCookieFor(uid, secret))
}

func tierOf(t *testing.T, s *store.Store, uid string) string {
	t.Helper()
	u, err := s.LoadUser(uid)
	if err != nil || u == nil {
		t.Fatalf("LoadUser %s: %v", uid, err)
	}
	return u.Tier
}

// usageOf liest den ECHTEN Leseweg GET /api/auth/sms-daily-usage (Go-Proxy).
func usageOf(t *testing.T, r http.Handler, uid, secret string) (smsUsed, smsLimit, premUsed, premLimit int) {
	t.Helper()
	rr := doBriefingRequest(t, r, http.MethodGet, "/api/auth/sms-daily-usage", nil, sessionCookieFor(uid, secret))
	if rr.Code != http.StatusOK {
		t.Fatalf("Leseweg /api/auth/sms-daily-usage fuer %s: %d %s", uid, rr.Code, rr.Body.String())
	}
	var u struct {
		SMS        struct{ Used, Limit int } `json:"sms"`
		PremiumSMS struct{ Used, Limit int } `json:"premium_sms"`
	}
	// Feldnamen im Double sind klein geschrieben; ohne Tags matcht json case-insensitiv.
	if err := json.Unmarshal(rr.Body.Bytes(), &u); err != nil {
		t.Fatalf("Leseweg nicht dekodierbar: %v (%s)", err, rr.Body.String())
	}
	return u.SMS.Used, u.SMS.Limit, u.PremiumSMS.Used, u.PremiumSMS.Limit
}

// AC-1: Produktionslage -> 404, nichts aendert sich; Gegenprobe Staging -> 200.
func TestStagingSeedIstInProduktionslageNichtRegistriert(t *testing.T) {
	r, s, secret, core := newSeedRouter(t, "", nil)
	rr := postSeed(t, r, "seedA", secret, `{"tier":"premium","sms":3}`)
	if rr.Code != http.StatusNotFound {
		t.Fatalf("AC-1: Produktionslage erwartet 404, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	if got := tierOf(t, s, "seedA"); got != "free" {
		t.Errorf("AC-1: Tarif darf sich nicht aendern, ist %q", got)
	}
	if len(core.seedCall) != 0 {
		t.Errorf("AC-1: Python-Core darf nicht aufgerufen werden, Aufrufe=%v", core.seedCall)
	}
}

func TestStagingSeedIstInStagingLageErreichbar(t *testing.T) {
	r, s, secret, _ := newSeedRouter(t, "staging", nil)
	rr := postSeed(t, r, "seedA", secret, `{"tier":"standard"}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-1 Positivkontrolle: Staging erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	if got := tierOf(t, s, "seedA"); got != "standard" {
		t.Errorf("AC-1: Tarif muss gesetzt sein, ist %q", got)
	}
}

// AC-2: ohne Anmeldung 401 (von der Middleware), nichts geschrieben.
func TestStagingSeedOhneAnmeldungWirdVonMiddlewareAbgewiesen(t *testing.T) {
	r, s, _, core := newSeedRouter(t, "staging", nil)
	req := httptest.NewRequest(http.MethodPost, seedPath, bytes.NewReader([]byte(`{"tier":"premium","sms":3}`)))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("AC-2: erwartet 401, bekam %d body=%s", w.Code, w.Body.String())
	}
	if got := tierOf(t, s, "seedA"); got != "free" {
		t.Errorf("AC-2: Tarif darf nicht geschrieben sein, ist %q", got)
	}
	if len(core.seedCall) != 0 {
		t.Errorf("AC-2: Core darf nicht aufgerufen werden: %v", core.seedCall)
	}
}

// AC-3 + AC-12: nur das eigene Konto; Rumpf-Nutzerfelder werden ignoriert;
// kein Ordner "default".
func TestStagingSeedWirktNurAufDasEingeloggteKonto(t *testing.T) {
	r, s, secret, core := newSeedRouter(t, "staging", nil)
	rr := postSeed(t, r, "seedA", secret, `{"tier":"premium","sms":3,"user_id":"seedB","username":"seedB"}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-3: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	if got := tierOf(t, s, "seedA"); got != "premium" {
		t.Errorf("AC-3: Konto A muss premium sein, ist %q", got)
	}
	if got := tierOf(t, s, "seedB"); got != "free" {
		t.Errorf("AC-3 Datenleck: Konto B wurde veraendert, Tarif %q", got)
	}
	sU, _, pU, _ := usageOf(t, r, "seedB", secret)
	if sU != 0 || pU != 0 {
		t.Errorf("AC-3 Datenleck: Zaehler von B = %d/%d, erwartet 0/0", sU, pU)
	}
	sA, _, _, _ := usageOf(t, r, "seedA", secret)
	if sA != 3 {
		t.Errorf("AC-3: Zaehler von A erwartet 3, ist %d", sA)
	}
	if len(core.seedCall) != 1 || core.seedCall[0]["user_id"] != "seedA" {
		t.Errorf("AC-3: Core muss genau einmal mit user_id=seedA gerufen werden, war %v", core.seedCall)
	}
	// AC-12
	if _, err := os.Stat(filepath.Join(s.DataDir, "users", "default")); err == nil {
		t.Errorf("AC-12: Verzeichnis users/default darf nicht entstehen")
	}
}

func TestStagingSeedNurTarifWirktAufEingeloggtesKontoOhneNutzerfeld(t *testing.T) {
	r, s, secret, _ := newSeedRouter(t, "staging", nil)
	rr := postSeed(t, r, "seedB", secret, `{"tier":"standard"}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-12: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	if got := tierOf(t, s, "seedB"); got != "standard" {
		t.Errorf("AC-12: Tarif von seedB erwartet standard, ist %q", got)
	}
	if got := tierOf(t, s, "seedA"); got != "free" {
		t.Errorf("AC-12: seedA darf unberuehrt bleiben, Tarif %q", got)
	}
	if _, err := os.Stat(filepath.Join(s.DataDir, "users", "default")); err == nil {
		t.Errorf("AC-12: Verzeichnis users/default darf nicht entstehen")
	}
}

// AC-4: Merge statt Replace — bekannte UND unbekannte Felder bleiben erhalten.
func TestStagingSeedTarifIstMergeKeinReplace(t *testing.T) {
	r, s, secret, _ := newSeedRouter(t, "staging", nil)
	raw := `{"id":"seedA","tier":"free","display_name":"Alice","email":"a@example.org","created_at":"2026-01-01T00:00:00Z","zukunftsfeld":{"x":[1,2,3]}}`
	path := filepath.Join(s.DataDir, "users", "seedA", "user.json")
	if err := os.WriteFile(path, []byte(raw), 0o644); err != nil {
		t.Fatalf("Fixture: %v", err)
	}
	rr := postSeed(t, r, "seedA", secret, `{"tier":"standard"}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-4: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	disk, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(disk, &m); err != nil {
		t.Fatalf("user.json nicht lesbar: %v", err)
	}
	if m["tier"] != "standard" {
		t.Errorf("AC-4: tier erwartet standard, ist %v", m["tier"])
	}
	if m["display_name"] != "Alice" || m["email"] != "a@example.org" {
		t.Errorf("AC-4: bekannte Felder verloren: %v", m)
	}
	if _, ok := m["zukunftsfeld"]; !ok {
		t.Errorf("AC-4 Datenverlust: Client-unbekanntes Feld 'zukunftsfeld' ging verloren: %s", disk)
	}
}

// AC-5: Fehlfaelle -> 400, nichts geschrieben; Grenzwerte 0/1000 -> 200.
func TestStagingSeedValidierungLehntFehlfaelleAb(t *testing.T) {
	cases := []struct {
		name, body, code string
	}{
		{"leer", `{}`, "nothing_to_set"},
		{"tarif_gold", `{"tier":"gold"}`, "validation_error"},
		{"negativ", `{"sms":-1}`, "validation_error"},
		{"ueber_grenze", `{"sms":1001}`, "validation_error"},
		{"nicht_ganzzahl", `{"premium_sms":2.5}`, "validation_error"},
		{"sms_null", `{"sms":null}`, "validation_error"},
		{"premium_sms_null", `{"premium_sms":null}`, "validation_error"},
		{"gueltiger_tarif_plus_ungueltiger_zaehler", `{"tier":"premium","sms":-1}`, "validation_error"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			r, s, secret, core := newSeedRouter(t, "staging", nil)
			rr := postSeed(t, r, "seedA", secret, c.body)
			if rr.Code != http.StatusBadRequest {
				t.Fatalf("AC-5 %s: erwartet 400, bekam %d body=%s", c.name, rr.Code, rr.Body.String())
			}
			var resp map[string]any
			_ = json.Unmarshal(rr.Body.Bytes(), &resp)
			if resp["error"] != c.code {
				t.Errorf("AC-5 %s: error erwartet %q, war %v (body=%s)", c.name, c.code, resp["error"], rr.Body.String())
			}
			if got := tierOf(t, s, "seedA"); got != "free" {
				t.Errorf("AC-5 %s: Tarif darf nicht geschrieben sein, ist %q", c.name, got)
			}
			if len(core.seedCall) != 0 {
				t.Errorf("AC-5 %s: Core darf nicht aufgerufen werden: %v", c.name, core.seedCall)
			}
		})
	}
}

func TestStagingSeedGrenzwerteNullUndTausendSindGueltig(t *testing.T) {
	for _, v := range []string{"0", "1000"} {
		r, _, secret, _ := newSeedRouter(t, "staging", nil)
		rr := postSeed(t, r, "seedA", secret, `{"sms":`+v+`}`)
		if rr.Code != http.StatusOK {
			t.Errorf("AC-5: sms=%s erwartet 200, bekam %d body=%s", v, rr.Code, rr.Body.String())
		}
	}
}

// AC-6: Roundtrip ueber den echten Leseweg; Antwort nennt tier/sms/premium_sms.
func TestStagingSeedRoundtripUeberLeseweg(t *testing.T) {
	r, _, secret, _ := newSeedRouter(t, "staging", nil)
	rr := postSeed(t, r, "seedA", secret, `{"tier":"standard","sms":3}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-6: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	var resp map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Antwort nicht JSON: %v", err)
	}
	if resp["tier"] != "standard" || resp["sms"] != float64(3) || resp["premium_sms"] != float64(0) {
		t.Errorf("AC-6: Antwort erwartet tier=standard sms=3 premium_sms=0, war %v", resp)
	}
	sU, sL, pU, _ := usageOf(t, r, "seedA", secret)
	if sU != 3 || sL != 10 || pU != 0 {
		t.Errorf("AC-6: Leseweg erwartet sms 3/10, premium 0, war sms %d/%d premium %d", sU, sL, pU)
	}
}

// AC-7 (Go-Seite): Overshoot wird nicht gekappt.
func TestStagingSeedOvershootWirdNichtGekappt(t *testing.T) {
	r, _, secret, _ := newSeedRouter(t, "staging", nil)
	rr := postSeed(t, r, "seedA", secret, `{"tier":"premium","premium_sms":17}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-7: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	_, _, pU, pL := usageOf(t, r, "seedA", secret)
	if pU != 17 || pL != 15 {
		t.Errorf("AC-7: Leseweg erwartet premium 17 bei Limit 15, war %d/%d", pU, pL)
	}
}

// AC-11: Core nicht erreichbar / Fehler -> 502, Tarif unveraendert.
func TestStagingSeedCoreAusfallLiefert502UndLaesstTarifUnveraendert(t *testing.T) {
	for _, body := range []string{`{"sms":3}`, `{"tier":"premium","sms":3}`} {
		r, s, secret, _ := newSeedRouter(t, "staging", func(*fakeCore) string { return "http://127.0.0.1:1" })
		rr := postSeed(t, r, "seedA", secret, body)
		if rr.Code != http.StatusBadGateway {
			t.Errorf("AC-11 %s: erwartet 502, bekam %d body=%s", body, rr.Code, rr.Body.String())
		}
		if got := tierOf(t, s, "seedA"); got != "free" {
			t.Errorf("AC-11 %s: Tarif darf nicht geaendert sein (Zaehler zuerst), ist %q", body, got)
		}
	}
}

func TestStagingSeedCoreFehlerantwortLiefert502(t *testing.T) {
	r, s, secret, core := newSeedRouter(t, "staging", nil)
	core.fail = true
	rr := postSeed(t, r, "seedA", secret, `{"tier":"premium","sms":3}`)
	if rr.Code != http.StatusBadGateway {
		t.Fatalf("AC-11: Core 500 erwartet 502, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	if got := tierOf(t, s, "seedA"); got != "free" {
		t.Errorf("AC-11: Tarif darf nicht geaendert sein, ist %q", got)
	}
}

// F004: reiner Tarif-Aufruf liefert den Zaehlerstand des EINGELOGGTEN Nutzers,
// nie den eines anderen und nie einen Default.
func TestStagingSeedNurTarifTraegtZaehlerstandDesEigenenNutzers(t *testing.T) {
	r, _, secret, core := newSeedRouter(t, "staging", nil)
	core.mu.Lock()
	core.counters["seedA"] = [2]int{4, 2}
	core.counters["seedB"] = [2]int{9, 8}
	core.mu.Unlock()
	for uid, want := range map[string][2]float64{"seedA": {4, 2}, "seedB": {9, 8}} {
		rr := postSeed(t, r, uid, secret, `{"tier":"premium"}`)
		if rr.Code != http.StatusOK {
			t.Fatalf("F004 %s: erwartet 200, bekam %d body=%s", uid, rr.Code, rr.Body.String())
		}
		var resp map[string]any
		if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
			t.Fatalf("F004 %s: Antwort nicht JSON: %v", uid, err)
		}
		if resp["tier"] != "premium" || resp["sms"] != want[0] || resp["premium_sms"] != want[1] {
			t.Errorf("F004 %s: erwartet tier=premium sms=%v premium_sms=%v, war %v", uid, want[0], want[1], resp)
		}
	}
}

// F004: Core-Ausfall bei reinem Tarif-Aufruf ist kein Fehler: 200, Tarif gesetzt,
// keine Zaehlerfelder.
func TestStagingSeedNurTarifBeiCoreAusfallLiefert200OhneZaehlerfelder(t *testing.T) {
	r, s, secret, _ := newSeedRouter(t, "staging", func(*fakeCore) string { return "http://127.0.0.1:1" })
	rr := postSeed(t, r, "seedA", secret, `{"tier":"standard"}`)
	if rr.Code != http.StatusOK {
		t.Fatalf("F004: erwartet 200, bekam %d body=%s", rr.Code, rr.Body.String())
	}
	var resp map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Antwort nicht JSON: %v", err)
	}
	if resp["tier"] != "standard" {
		t.Errorf("F004: tier erwartet standard, war %v", resp)
	}
	if _, ok := resp["sms"]; ok {
		t.Errorf("F004: sms darf ohne Core fehlen, war %v", resp)
	}
	if _, ok := resp["premium_sms"]; ok {
		t.Errorf("F004: premium_sms darf ohne Core fehlen, war %v", resp)
	}
	if got := tierOf(t, s, "seedA"); got != "standard" {
		t.Errorf("F004: Tarif muss gesetzt sein, ist %q", got)
	}
}
