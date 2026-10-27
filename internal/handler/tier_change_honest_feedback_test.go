package handler

// TDD RED — Issue #2436: Tier-Antrag meldet ehrlich, ob der Betreiber
// benachrichtigt wurde (AC-1..AC-5).
// Spec: docs/specs/modules/fix_2436_tier_antrag_ehrliche_rueckmeldung.md
//
// Ersetzt wird nur die Transportgrenze (sendTierChangeMailFn). Geprueft wird
// das beobachtbare Ergebnis aus HTTP-Antwort und user.json.

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

func fullMailCfg() config.Config {
	return config.Config{
		PoEmail: "po@example.com", SMTPHost: "smtp.fixture.test", SMTPPort: 587,
		SMTPUser: "u", SMTPPass: "p", SMTPFrom: "gregor_zwanzig@henemm.com",
	}
}

func withTierMailFn(t *testing.T, fn func(c, fb mail.MailConfig, to string, msg mail.Mail) error) {
	t.Helper()
	old := sendTierChangeMailFn
	sendTierChangeMailFn = fn
	t.Cleanup(func() { sendTierChangeMailFn = old })
}

func postTierRequest(t *testing.T, s *store.Store, cfg config.Config, uid, tier string) (int, map[string]any) {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"requested_tier": tier})
	req := httptest.NewRequest("POST", "/api/auth/tier-change-request", bytes.NewReader(body))
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
	w := httptest.NewRecorder()
	RequestTierChangeHandler(s, cfg).ServeHTTP(w, req)
	var resp map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	return w.Code, resp
}

func rawUserJSON(t *testing.T, s *store.Store, uid string) map[string]any {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.DataDir, "users", uid, "user.json"))
	if err != nil {
		t.Fatalf("user.json lesen: %v", err)
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatalf("user.json parsen: %v", err)
	}
	return m
}

func seedFree(t *testing.T, s *store.Store, ids ...string) {
	t.Helper()
	for _, id := range ids {
		if err := s.SaveUser(model.User{ID: id, Tier: "free"}); err != nil {
			t.Fatalf("SaveUser %s: %v", id, err)
		}
	}
}

func okSend(c, fb mail.MailConfig, to string, msg mail.Mail) error { return nil }

// AC-1
func TestTierChangeHonest_AC1_PoEmailFehlt(t *testing.T) {
	called := false
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { called = true; return nil })
	s := newTestStore(t)
	seedFree(t, s, "alice")
	cfg := fullMailCfg()
	cfg.PoEmail = ""
	code, resp := postTierRequest(t, s, cfg, "alice", "standard")
	if code != 200 || resp["po_notified"] != false {
		t.Fatalf("want 200 + po_notified=false, got %d %v", code, resp)
	}
	if called {
		t.Error("ohne PO_EMAIL darf kein Versand versucht werden")
	}
	u, _ := s.LoadUser("alice")
	if u.RequestedTier != "standard" {
		t.Errorf("Antrag muss gespeichert sein, got %q", u.RequestedTier)
	}
}

// AC-2
func TestTierChangeHonest_AC2_SmtpHostFehlt(t *testing.T) {
	withTierMailFn(t, okSend)
	s := newTestStore(t)
	seedFree(t, s, "alice")
	cfg := fullMailCfg()
	cfg.SMTPHost = ""
	code, resp := postTierRequest(t, s, cfg, "alice", "standard")
	if code != 200 || resp["po_notified"] != false {
		t.Fatalf("want 200 + po_notified=false, got %d %v", code, resp)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; ok {
		t.Error("requested_notified_at darf nicht gesetzt sein")
	}
}

// AC-3 (Fehler)
func TestTierChangeHonest_AC3_VersandFehler(t *testing.T) {
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { return errors.New("smtp down") })
	s := newTestStore(t)
	seedFree(t, s, "alice")
	code, resp := postTierRequest(t, s, fullMailCfg(), "alice", "premium")
	if code != 200 || resp["po_notified"] != false {
		t.Fatalf("want 200 + po_notified=false, got %d %v", code, resp)
	}
	u, _ := s.LoadUser("alice")
	if u.RequestedTier != "premium" {
		t.Errorf("Antrag muss gespeichert bleiben, got %q", u.RequestedTier)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; ok {
		t.Error("requested_notified_at darf nicht gesetzt sein")
	}
}

// AC-3 (Haenger): Timeout greift, Antrag bleibt gespeichert. Die 15 s sind der
// Standardwert; der Test verkuerzt ihn nur, um nicht 15 s zu warten.
func TestTierChangeHonest_AC3_VersandHaengerTimeout(t *testing.T) {
	if tierChangeMailTimeout != 15*time.Second {
		t.Fatalf("Standard-Timeout muss 15s sein, got %v", tierChangeMailTimeout)
	}
	oldTO := tierChangeMailTimeout
	tierChangeMailTimeout = 300 * time.Millisecond
	t.Cleanup(func() { tierChangeMailTimeout = oldTO })
	release := make(chan struct{})
	t.Cleanup(func() { close(release) })
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { <-release; return nil })
	s := newTestStore(t)
	seedFree(t, s, "alice")
	start := time.Now()
	code, resp := postTierRequest(t, s, fullMailCfg(), "alice", "standard")
	el := time.Since(start)
	if code != 200 || resp["po_notified"] != false {
		t.Fatalf("want 200 + po_notified=false, got %d %v", code, resp)
	}
	if el < 250*time.Millisecond || el > 3*time.Second {
		t.Errorf("Antwort muss nach dem Timeout kommen (nicht sofort, nicht ewig), got %v", el)
	}
	u, _ := s.LoadUser("alice")
	if u.RequestedTier != "standard" {
		t.Errorf("Antrag muss gespeichert bleiben, got %q", u.RequestedTier)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; ok {
		t.Error("requested_notified_at darf bei Timeout nicht gesetzt sein")
	}
}

// AC-4 + Zwei-Nutzer-Isolation
func TestTierChangeHonest_AC4_ErfolgZweiNutzer(t *testing.T) {
	var gotTo string
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { gotTo = to; return nil })
	s := newTestStore(t)
	seedFree(t, s, "alice", "bob")
	code, resp := postTierRequest(t, s, fullMailCfg(), "alice", "standard")
	if code != 200 || resp["po_notified"] != true || resp["status"] != "ok" {
		t.Fatalf("want 200 ok + po_notified=true, got %d %v", code, resp)
	}
	if gotTo != "po@example.com" {
		t.Errorf("Mail muss an PO_EMAIL gehen, got %q", gotTo)
	}
	if v, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; !ok || v == "" {
		t.Error("requested_notified_at muss gesetzt sein")
	}
	// bob unberuehrt
	bob := rawUserJSON(t, s, "bob")
	if _, ok := bob["requested_tier"]; ok {
		t.Error("bob darf keinen Antrag haben")
	}
	if _, ok := bob["requested_notified_at"]; ok {
		t.Error("bob darf keinen Nachweis haben")
	}
	// bob beantragt mit Fehlschlag: alice' Nachweis bleibt, bob hat keinen
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { return errors.New("x") })
	_, resp = postTierRequest(t, s, fullMailCfg(), "bob", "premium")
	if resp["po_notified"] != false {
		t.Errorf("bob: want po_notified=false, got %v", resp)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; !ok {
		t.Error("alice' Nachweis darf durch bobs Antrag nicht verschwinden")
	}
	if _, ok := rawUserJSON(t, s, "bob")["requested_notified_at"]; ok {
		t.Error("bob hat keinen Nachweis")
	}
}

// AC-5
func TestTierChangeHonest_AC5_AlterNachweisGiltNichtFuerNeuenAntrag(t *testing.T) {
	withTierMailFn(t, okSend)
	s := newTestStore(t)
	seedFree(t, s, "alice")
	if _, resp := postTierRequest(t, s, fullMailCfg(), "alice", "standard"); resp["po_notified"] != true {
		t.Fatalf("erster Antrag muss gemeldet sein: %v", resp)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; !ok {
		t.Fatal("Vorbedingung: Nachweis gesetzt")
	}
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { return errors.New("down") })
	_, resp := postTierRequest(t, s, fullMailCfg(), "alice", "premium")
	if resp["po_notified"] != false {
		t.Fatalf("zweiter Antrag: want po_notified=false, got %v", resp)
	}
	if _, ok := rawUserJSON(t, s, "alice")["requested_notified_at"]; ok {
		t.Error("alter Nachweis muss bei neuem, gescheitertem Antrag geloescht sein")
	}
}

// Profil traegt den Nachweis (Grundlage fuer AC-6 nach Reload).
func TestTierChangeHonest_ProfilLiefertRequestedNotifiedAt(t *testing.T) {
	withTierMailFn(t, okSend)
	s := newTestStore(t)
	seedFree(t, s, "alice")
	postTierRequest(t, s, fullMailCfg(), "alice", "standard")
	preq := httptest.NewRequest("GET", "/api/auth/profile", nil)
	preq = preq.WithContext(middleware.ContextWithUserID(preq.Context(), "alice"))
	pw := httptest.NewRecorder()
	GetProfileHandler(s, nil).ServeHTTP(pw, preq)
	var resp map[string]any
	_ = json.Unmarshal(pw.Body.Bytes(), &resp)
	if v, ok := resp["requested_notified_at"]; !ok || v == "" {
		t.Errorf("Profil muss requested_notified_at tragen, got %v", resp)
	}
}

// Adversary F001 (a): Admin gibt den Antrag frei, waehrend die Mail unterwegs
// ist. Der Nachweis darf nicht nachtraeglich an den freigegebenen Nutzer geraten.
func TestTierChangeHonest_F001_FreigabeWaehrendVersandStempeltNicht(t *testing.T) {
	s := newTestStore(t)
	seedFree(t, s, "alice")
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error {
		return s.SetUserTierAdmin("alice", "standard")
	})
	code, resp := postTierRequest(t, s, fullMailCfg(), "alice", "standard")
	if code != 200 || resp["po_notified"] != false {
		t.Fatalf("want 200 + po_notified=false, got %d %v", code, resp)
	}
	m := rawUserJSON(t, s, "alice")
	for _, k := range []string{"requested_tier", "requested_at", "requested_notified_at"} {
		if _, ok := m[k]; ok {
			t.Errorf("%s darf nach Freigabe nicht (wieder) auftauchen", k)
		}
	}
	if m["tier"] != "standard" {
		t.Errorf("Freigabe muss erhalten bleiben, got %v", m["tier"])
	}
}

// Adversary F001 (b): Ein spaeter Versand zu Antrag 1 darf Antrag 2 nicht stempeln.
func TestTierChangeHonest_F001_SpaeterVersandStempeltNeuerenAntragNicht(t *testing.T) {
	s := newTestStore(t)
	seedFree(t, s, "alice")
	withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error {
		// Mitten im Versand von Antrag 1 stellt der Nutzer Antrag 2, dessen Mail scheitert.
		withTierMailFn(t, func(c, fb mail.MailConfig, to string, msg mail.Mail) error { return errors.New("down") })
		if _, r2 := postTierRequest(t, s, fullMailCfg(), "alice", "premium"); r2["po_notified"] != false {
			t.Errorf("Antrag 2 muss po_notified=false melden, got %v", r2)
		}
		return nil // Antrag 1 gilt als erfolgreich versendet
	})
	_, resp := postTierRequest(t, s, fullMailCfg(), "alice", "standard")
	if resp["po_notified"] != false {
		t.Errorf("Antrag 1 ist nicht mehr der aktuelle: po_notified muss false sein, got %v", resp)
	}
	m := rawUserJSON(t, s, "alice")
	if m["requested_tier"] != "premium" {
		t.Errorf("aktueller Antrag muss premium sein, got %v", m["requested_tier"])
	}
	if _, ok := m["requested_notified_at"]; ok {
		t.Error("Nachweis von Antrag 1 darf Antrag 2 nicht stempeln")
	}
}
