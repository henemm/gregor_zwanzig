package router

// Admin-Einladungslinks (Spec admin_einladungslinks_2519), AC-1 bis AC-10, AC-12.
// Echter Produktions-Router ueber adminTestRouter (alice = Admin, bob = normaler
// Nutzer), echte Sitzungs-Cookies, echte Dateien. Kein Mock.

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
	"testing"
	"time"
)

type invDTO struct {
	ID        string  `json:"id"`
	Tier      string  `json:"tier"`
	Note      string  `json:"note"`
	Status    string  `json:"status"`
	UsedBy    string  `json:"used_by"`
	UsedAt    *string `json:"used_at"`
	RevokedAt *string `json:"revoked_at"`
}

// ivErstellen legt als Admin eine Einladung an und liefert DTO + Token.
func ivErstellen(t *testing.T, r http.Handler, secret, tier, note string) (invDTO, string) {
	t.Helper()
	body, _ := json.Marshal(map[string]string{"tier": tier, "note": note})
	w := auRuf(t, r, secret, http.MethodPost, "/api/admin/invites", "alice", string(body))
	if w.Code != http.StatusCreated {
		t.Fatalf("POST /api/admin/invites: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	var out struct {
		Invite invDTO `json:"invite"`
		Link   string `json:"link"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("Antwort kein JSON: %v", err)
	}
	const marker = "/register?invite="
	i := strings.Index(out.Link, marker)
	if i < 0 {
		t.Fatalf("Link enthaelt %q nicht: %q", marker, out.Link)
	}
	return out.Invite, out.Link[i+len(marker):]
}

func ivListe(t *testing.T, r http.Handler, secret string) ([]invDTO, string) {
	t.Helper()
	w := auRuf(t, r, secret, http.MethodGet, "/api/admin/invites", "alice", "")
	if w.Code != http.StatusOK {
		t.Fatalf("GET /api/admin/invites: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	var out struct {
		Invites []invDTO `json:"invites"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &out); err != nil {
		t.Fatalf("Liste kein JSON: %v", err)
	}
	return out.Invites, w.Body.String()
}

func ivRegistrieren(t *testing.T, r http.Handler, name, email, invite string) *httptest.ResponseRecorder {
	t.Helper()
	m := map[string]string{"username": name, "password": "geheim-2519-pw", "email": email}
	if invite != "" {
		m["invite"] = invite
	}
	b, _ := json.Marshal(m)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", bytes.NewReader(b))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)
	return w
}

func ivBody(w *httptest.ResponseRecorder) string { return strings.TrimSpace(w.Body.String()) }

// AC-1 + AC-9
func TestAdminInvites_ErstellenUndAuflisten_TokenNieImKlartext(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "alice")
	dto, token := ivErstellen(t, r, secret, "standard", "Tante Erna")
	if token == "" || dto.ID == "" || dto.Tier != "standard" || dto.Note != "Tante Erna" {
		t.Fatalf("DTO/Token unvollstaendig: %+v token=%q", dto, token)
	}
	liste, rohListe := ivListe(t, r, secret)
	if len(liste) != 1 || liste[0].Status != "open" || liste[0].Tier != "standard" || liste[0].Note != "Tante Erna" {
		t.Errorf("Liste: %+v", liste)
	}
	if strings.Contains(rohListe, token) {
		t.Errorf("Token-Klartext im Listen-Body")
	}
	// Datei: kein Klartext, Hash passt
	cfgDir := filepath.Dir(filepath.Dir(s.UserDir("alice")))
	raw, err := os.ReadFile(filepath.Join(cfgDir, "invites.json"))
	if err != nil {
		t.Fatalf("invites.json: %v", err)
	}
	if strings.Contains(string(raw), token) {
		t.Errorf("Token-Klartext in invites.json")
	}
	sum := sha256.Sum256([]byte(token))
	if !strings.Contains(string(raw), hex.EncodeToString(sum[:])) {
		t.Errorf("SHA-256 des Tokens fehlt in invites.json")
	}
}

// AC-8
func TestAdminInvites_AnonymAlt401_NichtAdmin403_AufAllenDreiRouten(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "alice")
	dto, token := ivErstellen(t, r, secret, "premium", "x")
	routen := []struct{ method, pfad, body string }{
		{http.MethodPost, "/api/admin/invites", `{"tier":"free","note":""}`},
		{http.MethodGet, "/api/admin/invites", ""},
		{http.MethodPost, "/api/admin/invites/" + dto.ID + "/revoke", ""},
	}
	for _, rt := range routen {
		if w := auRuf(t, r, secret, rt.method, rt.pfad, "", rt.body); w.Code != http.StatusUnauthorized {
			t.Errorf("anonym %s %s: erwartet 401, bekommen %d", rt.method, rt.pfad, w.Code)
		}
		w := auRuf(t, r, secret, rt.method, rt.pfad, "bob", rt.body)
		auAssertJSONFehler(t, w, http.StatusForbidden, `{"error":"forbidden"}`, "bob "+rt.method+" "+rt.pfad)
	}
	liste, _ := ivListe(t, r, secret)
	if len(liste) != 1 || liste[0].Status != "open" {
		t.Errorf("abgewiesene Aufrufe haben die Einladung veraendert: %+v", liste)
	}
	// Positivkontrolle: Einladung ist noch einloesbar
	if w := ivRegistrieren(t, r, "neuling", "neuling@example.org", token); w.Code != http.StatusCreated {
		t.Errorf("Einladung nach abgewiesenen Aufrufen nicht einloesbar: %d %s", w.Code, w.Body.String())
	}
}

// AC-12
func TestAdminInvites_UngueltigesLevelOderLangeNotiz_400_NichtsGespeichert(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "alice")
	for name, body := range map[string]string{
		"level gold": `{"tier":"gold","note":""}`,
		"note 201":   `{"tier":"free","note":"` + strings.Repeat("a", 201) + `"}`,
		"kaputt":     `nope`,
		"tier fehlt": `{"note":"x"}`,
		"tier gross": `{"tier":"Premium","note":""}`,
	} {
		if w := auRuf(t, r, secret, http.MethodPost, "/api/admin/invites", "alice", body); w.Code != http.StatusBadRequest {
			t.Errorf("%s: erwartet 400, bekommen %d: %s", name, w.Code, w.Body.String())
		}
	}
	if liste, _ := ivListe(t, r, secret); len(liste) != 0 {
		t.Errorf("Liste muss leer bleiben: %+v", liste)
	}
	// 200 Zeichen sind erlaubt (Grenze)
	ivErstellen(t, r, secret, "free", strings.Repeat("a", 200))
}

// AC-2 + AC-10: Level direkt, kein Antrag, Login erst nach Bestaetigung.
func TestRegisterMitEinladung_SetztLevel_OhneAntrag_LoginErstNachBestaetigung(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "alice")
	_, token := ivErstellen(t, r, secret, "premium", "")
	if w := ivRegistrieren(t, r, "erna", "erna@example.org", token); w.Code != http.StatusCreated {
		t.Fatalf("Register: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
	u, err := s.LoadUser("erna")
	if err != nil || u == nil {
		t.Fatalf("Konto fehlt: %v", err)
	}
	if u.Tier != "premium" || u.RequestedTier != "" || u.RequestedAt != nil {
		t.Errorf("Tier=%q RequestedTier=%q RequestedAt=%v", u.Tier, u.RequestedTier, u.RequestedAt)
	}
	if u.EmailVerifiedAt != nil {
		t.Errorf("E-Mail darf durch die Einladung nicht als bestaetigt gelten")
	}
	if w := auLogin(t, r, "erna", "geheim-2519-pw"); w.Code != http.StatusForbidden {
		t.Errorf("Login vor Bestaetigung: erwartet 403, bekommen %d: %s", w.Code, w.Body.String())
	}
	jetzt := time.Now().UTC()
	u.EmailVerifiedAt = &jetzt
	if err := s.SaveUser(*u); err != nil {
		t.Fatal(err)
	}
	if w := auLogin(t, r, "erna", "geheim-2519-pw"); w.Code != http.StatusOK {
		t.Errorf("Login nach Bestaetigung: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestRegisterOhneEinladung_BleibtFree(t *testing.T) {
	r, s, _, _ := adminTestRouter(t, "alice")
	if w := ivRegistrieren(t, r, "frei", "frei@example.org", ""); w.Code != http.StatusCreated {
		t.Fatalf("Register: %d %s", w.Code, w.Body.String())
	}
	u, _ := s.LoadUser("frei")
	if u == nil || u.EffectiveTier() != "free" || u.RequestedTier != "" {
		t.Errorf("Konto ohne Einladung: %+v", u)
	}
}

// AC-3 + AC-7
func TestRegisterMitBenutzterEinladung_400_KeinKonto_ListeZeigtBenutztVon(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "alice")
	_, token := ivErstellen(t, r, secret, "standard", "")
	if w := ivRegistrieren(t, r, "erster", "erster@example.org", token); w.Code != http.StatusCreated {
		t.Fatalf("erste Registrierung: %d %s", w.Code, w.Body.String())
	}
	w := ivRegistrieren(t, r, "zweiter", "zweiter@example.org", token)
	auAssertJSONFehler(t, w, http.StatusBadRequest, `{"error":"invite_invalid"}`, "zweite Registrierung")
	if s.UserExists("zweiter") {
		t.Errorf("trotz abgelehnter Einladung wurde ein Konto angelegt")
	}
	liste, _ := ivListe(t, r, secret)
	if len(liste) != 1 || liste[0].Status != "used" || liste[0].UsedBy != "erster" || liste[0].UsedAt == nil {
		t.Errorf("Liste nach Einloesung: %+v", liste)
	}
}

// AC-5
func TestWiderrufeneEinladung_Register400_ListeZeigtWiderrufen_BenutzteNichtWiderrufbar(t *testing.T) {
	r, s, secret, _ := adminTestRouter(t, "alice")
	offen, tokOffen := ivErstellen(t, r, secret, "standard", "")
	benutzt, tokBenutzt := ivErstellen(t, r, secret, "standard", "")
	if w := ivRegistrieren(t, r, "nutzer", "nutzer@example.org", tokBenutzt); w.Code != http.StatusCreated {
		t.Fatalf("Register: %d", w.Code)
	}
	if w := auRuf(t, r, secret, http.MethodPost, "/api/admin/invites/"+offen.ID+"/revoke", "alice", ""); w.Code != http.StatusOK {
		t.Fatalf("Revoke: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	w := ivRegistrieren(t, r, "spaet", "spaet@example.org", tokOffen)
	auAssertJSONFehler(t, w, http.StatusBadRequest, `{"error":"invite_invalid"}`, "widerrufen")
	if s.UserExists("spaet") {
		t.Errorf("Konto trotz widerrufener Einladung")
	}
	if w := auRuf(t, r, secret, http.MethodPost, "/api/admin/invites/"+benutzt.ID+"/revoke", "alice", ""); w.Code != http.StatusConflict {
		t.Errorf("Revoke benutzt: erwartet 409, bekommen %d", w.Code)
	}
	if w := auRuf(t, r, secret, http.MethodPost, "/api/admin/invites/gibtesnicht/revoke", "alice", ""); w.Code != http.StatusNotFound {
		t.Errorf("Revoke unbekannt: erwartet 404, bekommen %d", w.Code)
	}
	liste, _ := ivListe(t, r, secret)
	st := map[string]string{}
	for _, i := range liste {
		st[i.ID] = i.Status
	}
	if st[offen.ID] != "revoked" || st[benutzt.ID] != "used" {
		t.Errorf("Status je Einladung: %+v", st)
	}
}

// AC-6
func TestEinladungBleibtOffen_WennRegistrierungAnEmailTakenScheitert(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "alice")
	if w := ivRegistrieren(t, r, "belegt", "belegt@example.org", ""); w.Code != http.StatusCreated {
		t.Fatalf("Vorbereitung: %d", w.Code)
	}
	_, token := ivErstellen(t, r, secret, "premium", "")
	w := ivRegistrieren(t, r, "versuch", "belegt@example.org", token)
	auAssertJSONFehler(t, w, http.StatusConflict, `{"error":"email_taken"}`, "email_taken")
	if liste, _ := ivListe(t, r, secret); len(liste) != 1 || liste[0].Status != "open" {
		t.Errorf("Einladung nicht mehr offen: %+v", liste)
	}
	if w := ivRegistrieren(t, r, "versuch", "frei2@example.org", token); w.Code != http.StatusCreated {
		t.Errorf("zweiter Versuch: erwartet 201, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func TestRegisterMitUnbekanntemToken_400_KeinStillesFreeKonto(t *testing.T) {
	r, s, _, _ := adminTestRouter(t, "alice")
	w := ivRegistrieren(t, r, "fremd", "fremd@example.org", "gibt-es-nicht")
	auAssertJSONFehler(t, w, http.StatusBadRequest, `{"error":"invite_invalid"}`, "unbekanntes Token")
	if s.UserExists("fremd") {
		t.Errorf("Konto trotz ungueltiger Einladung angelegt")
	}
}

// Oeffentlicher Vorab-Check: offen -> 200 {tier}, sonst 404 invite_invalid
// (kein Unterschied zwischen unbekannt/benutzt/widerrufen), ohne Sitzung.
func TestInviteCheck_OeffentlichOhneSitzung_OffenOk_SonstNeutral404(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "alice")
	offen, tokOffen := ivErstellen(t, r, secret, "premium", "")
	_, tokBenutzt := ivErstellen(t, r, secret, "free", "")
	if w := ivRegistrieren(t, r, "wer", "wer@example.org", tokBenutzt); w.Code != http.StatusCreated {
		t.Fatalf("Register: %d", w.Code)
	}
	w := auRuf(t, r, secret, http.MethodGet, "/api/auth/invite/"+tokOffen, "", "")
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"tier":"premium"`) {
		t.Errorf("offen: erwartet 200 mit tier, bekommen %d %s", w.Code, w.Body.String())
	}
	for name, tok := range map[string]string{"unbekannt": "nope", "benutzt": tokBenutzt} {
		w := auRuf(t, r, secret, http.MethodGet, "/api/auth/invite/"+tok, "", "")
		auAssertJSONFehler(t, w, http.StatusNotFound, `{"error":"invite_invalid"}`, name)
	}
	_ = offen
}

func TestInviteCheck_WiderrufenUndRateLimit(t *testing.T) {
	r, _, secret, _ := adminTestRouter(t, "alice")
	dto, tok := ivErstellen(t, r, secret, "standard", "")
	auRuf(t, r, secret, http.MethodPost, "/api/admin/invites/"+dto.ID+"/revoke", "alice", "")
	w := auRuf(t, r, secret, http.MethodGet, "/api/auth/invite/"+tok, "", "")
	auAssertJSONFehler(t, w, http.StatusNotFound, `{"error":"invite_invalid"}`, "widerrufen")
	var last int
	for i := 0; i < 8; i++ {
		last = auRuf(t, r, secret, http.MethodGet, "/api/auth/invite/raten"+string(rune('a'+i)), "", "").Code
	}
	if last != http.StatusTooManyRequests {
		t.Errorf("nach 9 Aufrufen erwartet 429, bekommen %d", last)
	}
}
