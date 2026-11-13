package handler

// Issue #2961 (GA8) — Bremsen fuer Passwortwechsel, Tarif-Antrag und
// Telegram-Verknuepfungslink.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-21 bis AC-24).
//
// Echte Handler, echter Store in t.TempDir(); die Betreiber-Mail wird an der
// Transportgrenze sendTierChangeMailFn mitgezaehlt.

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
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
	"github.com/henemm/gregor-api/internal/model"
)

const bremsenSecret2961 = "bremsen-2961-secret-32-zeichen!!"

func alsNutzer2961(req *http.Request, uid string) *http.Request {
	return req.WithContext(middleware.ContextWithUserID(req.Context(), uid))
}

func pwKonto2961(t *testing.T, uid, pw string) model.User {
	t.Helper()
	hash, _ := bcrypt.GenerateFromPassword([]byte(pw), bcrypt.MinCost)
	now := time.Now().UTC()
	return model.User{ID: uid, PasswordHash: string(hash), Email: uid + "@beispiel.de", CreatedAt: now, EmailVerifiedAt: &now}
}

// AC-21: hoechstens 5 Fehlversuche des alten Passworts je Nutzer und 15
// Minuten; danach 429 — auch mit dem richtigen Passwort. Ein anderer Nutzer
// ist unberuehrt.
func TestPasswortwechsel_FehlversuchsBremseJeNutzer(t *testing.T) {
	s := newTestStore(t)
	for _, u := range []model.User{pwKonto2961(t, "pwa", "richtig-123"), pwKonto2961(t, "pwb", "richtig-456")} {
		if err := s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}
	h := ChangePasswordHandler(s, bcrypt.MinCost, bremsenSecret2961, "")
	wechsel := func(uid, alt string) *httptest.ResponseRecorder {
		body := `{"old_password":"` + alt + `","new_password":"neues-passwort-1"}`
		req := alsNutzer2961(httptest.NewRequest(http.MethodPut, "/api/auth/password", strings.NewReader(body)), uid)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}
	for i := 1; i <= 5; i++ {
		if w := wechsel("pwa", "falsch"); w.Code != http.StatusForbidden {
			t.Fatalf("Fehlversuch %d: erwartet 403, bekommen %d: %s", i, w.Code, w.Body.String())
		}
	}
	w := wechsel("pwa", "richtig-123")
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("nach 5 Fehlversuchen erwartet 429, bekommen %d: %s", w.Code, w.Body.String())
	}
	if u, _ := s.LoadUser("pwa"); bcrypt.CompareHashAndPassword([]byte(u.PasswordHash), []byte("richtig-123")) != nil {
		t.Fatal("in der Sperre darf das Passwort nicht geaendert werden")
	}
	if w := wechsel("pwb", "richtig-456"); w.Code != http.StatusOK {
		t.Fatalf("anderer Nutzer: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-22: Tarif-Antrag hoechstens 3 je Nutzer und Tag; eine identische
// Wiederholung eines bereits gemeldeten Antrags schickt keine neue Mail.
func TestTarifAntrag_BremseUndKeineDoppelMail(t *testing.T) {
	var mails int32
	orig := sendTierChangeMailFn
	sendTierChangeMailFn = func(_, _ mail.MailConfig, _ string, _ mail.Mail) error {
		atomic.AddInt32(&mails, 1)
		return nil
	}
	t.Cleanup(func() { sendTierChangeMailFn = orig })

	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "tarif", Tier: "free"}); err != nil {
		t.Fatal(err)
	}
	h := RequestTierChangeHandler(s, config.Config{PoEmail: "po@example.com", SMTPHost: "127.0.0.1", SMTPPort: 1})
	antrag := func(tier string) *httptest.ResponseRecorder {
		body, _ := json.Marshal(map[string]string{"requested_tier": tier})
		req := alsNutzer2961(httptest.NewRequest(http.MethodPost, "/api/auth/tier-change-request", bytes.NewReader(body)), "tarif")
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		return w
	}
	if w := antrag("standard"); w.Code != http.StatusOK {
		t.Fatalf("1. Antrag: %d %s", w.Code, w.Body.String())
	}
	w := antrag("standard")
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"po_notified":true`) {
		t.Fatalf("identische Wiederholung: erwartet 200 po_notified=true, bekommen %d %s", w.Code, w.Body.String())
	}
	if n := atomic.LoadInt32(&mails); n != 1 {
		t.Fatalf("identische Wiederholung darf keine neue Mail ausloesen, Mails: %d", n)
	}
	for i, tier := range []string{"premium", "standard"} {
		if w := antrag(tier); w.Code != http.StatusOK {
			t.Fatalf("Antrag %d (%s): %d %s", i+2, tier, w.Code, w.Body.String())
		}
	}
	w = antrag("premium")
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("4. Antrag am Tag: erwartet 429, bekommen %d %s", w.Code, w.Body.String())
	}
	if n := atomic.LoadInt32(&mails); n != 3 {
		t.Fatalf("erwartet genau 3 Mails, bekommen %d", n)
	}
}

func telegramLinkHolen2961(t *testing.T, h http.Handler, uid string) (string, int) {
	t.Helper()
	req := alsNutzer2961(httptest.NewRequest(http.MethodGet, "/api/auth/telegram-link", nil), uid)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		return "", w.Code
	}
	var b struct {
		Link string `json:"link"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &b)
	i := strings.Index(b.Link, "?start=")
	if i < 0 {
		t.Fatalf("Link ohne Token: %q", b.Link)
	}
	return b.Link[i+len("?start="):], w.Code
}

// AC-23: je Nutzer nur EIN gueltiges Token (ein neues ersetzt das alte),
// in der Datei nur als SHA-256, abgelaufene Eintraege werden beim Schreiben
// entfernt; Tokens anderer Nutzer bleiben gueltig.
func TestTelegramLink_EinTokenJeNutzerNurAlsHash(t *testing.T) {
	s := newTestStore(t)
	for _, uid := range []string{"tga", "tgb"} {
		if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
	}
	ts := NewTelegramTokenStore(s.DataDir)
	// Abgelaufener Alt-Eintrag (Klartextschluessel wie vor #2961).
	ts.mu.Lock()
	ts.tokens["abgelaufen00000000000000000000000"] = pendingTelegramToken{UserID: "tgx", ExpiresAt: time.Now().Add(-time.Hour)}
	ts.mu.Unlock()
	h := GetTelegramLinkHandler(s, ts, "gregor_bot")

	alt, _ := telegramLinkHolen2961(t, h, "tga")
	fremd, _ := telegramLinkHolen2961(t, h, "tgb")
	neu, _ := telegramLinkHolen2961(t, h, "tga")

	roh, err := os.ReadFile(filepath.Join(s.DataDir, "telegram_tokens.json"))
	if err != nil {
		t.Fatal(err)
	}
	var datei map[string]pendingTelegramToken
	if err := json.Unmarshal(roh, &datei); err != nil {
		t.Fatal(err)
	}
	for _, tok := range []string{alt, neu, fremd} {
		if strings.Contains(string(roh), tok) {
			t.Fatalf("Token %q steht im Klartext in der Datei", tok)
		}
	}
	summe := sha256.Sum256([]byte(neu))
	if _, ok := datei[hex.EncodeToString(summe[:])]; !ok {
		t.Fatalf("das aktuelle Token muss als SHA-256 in der Datei stehen")
	}
	if len(datei) != 2 {
		t.Fatalf("erwartet genau 2 Eintraege (je Nutzer einer, Abgelaufenes entfernt), bekommen %d: %s", len(datei), roh)
	}
	if _, ok := ts.ResolveAndDelete(alt); ok {
		t.Fatal("das ersetzte Token darf nicht mehr einloesbar sein")
	}
	if pt, ok := ts.ResolveAndDelete(neu); !ok || pt.UserID != "tga" {
		t.Fatalf("das neue Token muss tga gehoeren (ok=%v, %+v)", ok, pt)
	}
	if pt, ok := ts.ResolveAndDelete(fremd); !ok || pt.UserID != "tgb" {
		t.Fatalf("das Token des anderen Nutzers muss gueltig bleiben (ok=%v, %+v)", ok, pt)
	}
}

// AC-23: Tokens aus einer Datei vor #2961 (Klartextschluessel) bleiben nach
// dem Laden einloesbar.
func TestTelegramLink_AltdateiMitKlartextBleibtEinloesbar(t *testing.T) {
	dir := t.TempDir()
	tok := "0123456789abcdef0123456789abcdef"
	alt := map[string]pendingTelegramToken{tok: {UserID: "altnutzer", ExpiresAt: time.Now().Add(time.Hour)}}
	b, _ := json.Marshal(alt)
	if err := os.WriteFile(filepath.Join(dir, "telegram_tokens.json"), b, 0o660); err != nil {
		t.Fatal(err)
	}
	ts := NewTelegramTokenStore(dir)
	if pt, ok := ts.ResolveAndDelete(tok); !ok || pt.UserID != "altnutzer" {
		t.Fatalf("Alt-Token muss einloesbar bleiben (ok=%v, %+v)", ok, pt)
	}
}

// AC-24: Mengenbremse je Nutzer fuer den Verknuepfungslink.
func TestTelegramLink_MengenbremseJeNutzer(t *testing.T) {
	s := newTestStore(t)
	for _, uid := range []string{"tgflut", "tgruhig"} {
		if err := s.SaveUser(model.User{ID: uid, CreatedAt: time.Now()}); err != nil {
			t.Fatal(err)
		}
	}
	h := GetTelegramLinkHandler(s, NewTelegramTokenStore(s.DataDir), "gregor_bot")
	for i := 1; i <= 10; i++ {
		if _, c := telegramLinkHolen2961(t, h, "tgflut"); c != http.StatusOK {
			t.Fatalf("Abruf %d: erwartet 200, bekommen %d", i, c)
		}
	}
	if _, c := telegramLinkHolen2961(t, h, "tgflut"); c != http.StatusTooManyRequests {
		t.Fatalf("11. Abruf: erwartet 429, bekommen %d", c)
	}
	if _, c := telegramLinkHolen2961(t, h, "tgruhig"); c != http.StatusOK {
		t.Fatalf("anderer Nutzer: erwartet 200, bekommen %d", c)
	}
}
