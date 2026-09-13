package handler

// TDD RED — Issue #2154 Scheibe A, Artefakt 2 (neue Flaechen, Konto-Endpoint).
// Spec: docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md v1.0
//
// Uebersetzungsfehler ist hier der ERWARTETE RED-Beleg. Von den Tests
// geforderte, neue Produktiv-Signaturen (s. Bericht "Abweichungen"):
//   PostPremiumSmsLinkCodeHandler(s *store.Store, bcryptCost int) http.HandlerFunc
//   GetPremiumSmsLinkCodeHandler(s *store.Store) http.HandlerFunc
//   model.PremiumSmsLinkCode{CodeHash string, CreatedAt time.Time}
//   (*store.Store).SaveLinkCode(userID string, c model.PremiumSmsLinkCode) error
//   (*store.Store).LoadLinkCode(userID string) (*model.PremiumSmsLinkCode, error)
// bcryptCost als Parameter nach dem Vorbild RegisterHandler/ForgotPasswordHandler
// (internal/handler/auth.go:31,231) — sonst kostet jeder Test Sekunden.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// Alphabet der Code-Gestalt (Spec D2): 7 Zeichen, ohne I/L/O/0/1.
const linkCodeLength = 7

var linkCodeForbiddenChars = "ILO01"

// mustSaveLinkCode legt einen Verknuepfungs-Code als bcrypt-Hash ab — genau
// so, wie es der Konto-Endpoint tut. Wird auch von
// premium_sms_learn_with_code_test.go benutzt.
func mustSaveLinkCode(t *testing.T, s *store.Store, userID, code string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(code), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt-Hash fuer %s fehlgeschlagen: %v", userID, err)
	}
	if err := s.SaveLinkCode(userID, model.PremiumSmsLinkCode{
		CodeHash: string(hash), CreatedAt: time.Now().UTC(),
	}); err != nil {
		t.Fatalf("SaveLinkCode(%s) fehlgeschlagen: %v", userID, err)
	}
}

func newLinkCodeRequest(method, userID string) *http.Request {
	req := httptest.NewRequest(method, "/api/auth/premium-sms-link-code", nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	return req
}

func linkCodeBody(t *testing.T, rr *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var body map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &body); err != nil {
		t.Fatalf("Antwort nicht JSON-dekodierbar: %v (%s)", err, rr.Body.String())
	}
	return body
}

// createLinkCode ruft den Erzeugungs-Endpoint auf und liefert den Klartext.
func createLinkCode(t *testing.T, s *store.Store, userID string) string {
	t.Helper()
	rr := httptest.NewRecorder()
	PostPremiumSmsLinkCodeHandler(s, bcrypt.MinCost)(rr, newLinkCodeRequest(http.MethodPost, userID))
	if rr.Code != http.StatusOK {
		t.Fatalf("Code-Erzeugung fuer %s: erwartet 200, bekam %d, body=%s", userID, rr.Code, rr.Body.String())
	}
	code, _ := linkCodeBody(t, rr)["code"].(string)
	if code == "" {
		t.Fatalf("Code-Erzeugung fuer %s lieferte keinen Klartext-Code, body=%s", userID, rr.Body.String())
	}
	return code
}

func linkCodePath(s *store.Store, userID string) string {
	return filepath.Join(s.DataDir, "users", userID, "premium_sms_link.json")
}

// ---------------------------------------------------------------------------
// AC-5 (1/3): der Klartext existiert genau einmal — in der Antwort des
// Erzeugungs-Aufrufs. Auf der Platte liegt ausschliesslich der bcrypt-Hash.
// ---------------------------------------------------------------------------

func TestLinkCodeReturnsCodeOnceInPlaintext(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna", Tier: "premium"})

	code := createLinkCode(t, s, "anna")

	if len(code) != linkCodeLength {
		t.Errorf("AC-5/D2: erwartet %d Zeichen, bekam %d (%q)", linkCodeLength, len(code), code)
	}
	if i := strings.IndexAny(code, linkCodeForbiddenChars); i >= 0 {
		t.Errorf("AC-5/D2: verwechselbares Zeichen %q im Code %q — verboten sind %q",
			code[i], code, linkCodeForbiddenChars)
	}

	stored, err := s.LoadLinkCode("anna")
	if err != nil || stored == nil {
		t.Fatalf("AC-5: gespeicherter Code nicht ladbar: %v (%v)", err, stored)
	}
	if strings.Contains(stored.CodeHash, code) {
		t.Errorf("AC-5: der Klartext darf NIE auf der Platte landen, gespeichert wurde %q", stored.CodeHash)
	}
	if err := bcrypt.CompareHashAndPassword([]byte(stored.CodeHash), []byte(code)); err != nil {
		t.Errorf("AC-5: der gespeicherte Hash gehoert nicht zum ausgelieferten Code: %v", err)
	}
}

// ---------------------------------------------------------------------------
// AC-5 (2/3): der Statusaufruf verraet weder Code noch Hash.
//
// Geprueft wird der ROHE Antwortkoerper gegen beide Geheimnisse, nicht die
// Abwesenheit eines "code"-Schluessels: ein Leck unter anderem Namen bliebe
// sonst unentdeckt.
// ---------------------------------------------------------------------------

func TestLinkCodeStatusNeverExposesCodeOrHash(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna", Tier: "premium"})

	rrBefore := httptest.NewRecorder()
	GetPremiumSmsLinkCodeHandler(s)(rrBefore, newLinkCodeRequest(http.MethodGet, "anna"))
	if rrBefore.Code != http.StatusOK {
		t.Fatalf("AC-5: Statusaufruf ohne Code erwartet 200, bekam %d, body=%s", rrBefore.Code, rrBefore.Body.String())
	}
	if exists, _ := linkCodeBody(t, rrBefore)["exists"].(bool); exists {
		t.Errorf("AC-5: ohne erzeugten Code muss exists=false gemeldet werden, body=%s", rrBefore.Body.String())
	}

	code := createLinkCode(t, s, "anna")
	stored, err := s.LoadLinkCode("anna")
	if err != nil || stored == nil {
		t.Fatalf("AC-5: gespeicherter Code nicht ladbar: %v (%v)", err, stored)
	}

	rr := httptest.NewRecorder()
	GetPremiumSmsLinkCodeHandler(s)(rr, newLinkCodeRequest(http.MethodGet, "anna"))
	if rr.Code != http.StatusOK {
		t.Fatalf("AC-5: Statusaufruf erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	raw := rr.Body.String()
	if exists, _ := linkCodeBody(t, rr)["exists"].(bool); !exists {
		t.Errorf("AC-5: nach der Erzeugung muss exists=true gemeldet werden, body=%s", raw)
	}
	if strings.Contains(raw, code) {
		t.Errorf("AC-5: der Statusaufruf gibt den KLARTEXT-Code heraus, body=%s", raw)
	}
	if strings.Contains(raw, stored.CodeHash) {
		t.Errorf("AC-5: der Statusaufruf gibt den HASH heraus, body=%s", raw)
	}
}

// ---------------------------------------------------------------------------
// AC-5 (3/3): Erneuern entwertet den alten Code — gemessen dort, wo es wirkt:
// am Lernaufruf, nicht an der Datei.
// ---------------------------------------------------------------------------

func TestLinkCodeRegenerateInvalidatesOldCode(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna", Tier: "premium"})

	oldCode := createLinkCode(t, s, "anna")
	newCode := createLinkCode(t, s, "anna")
	if oldCode == newCode {
		t.Fatalf("AC-5: der erneuerte Code ist derselbe (%q) — kein Ersatz, kein Entwerten", oldCode)
	}

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))

	rrOld := httptest.NewRecorder()
	h(rrOld, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": oldCode}))
	if rrOld.Code == http.StatusOK {
		t.Errorf("AC-5: der ALTE Code muss abgelehnt werden, bekam %d, body=%s", rrOld.Code, rrOld.Body.String())
	}
	if u := mustLoadUser(t, s, "anna"); u.PremiumSmsReplyTo != "" {
		t.Errorf("AC-5: der alte Code darf nichts verknuepfen, hat aber %q gesetzt", u.PremiumSmsReplyTo)
	}

	rrNew := httptest.NewRecorder()
	h(rrNew, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCoded, "code": newCode}))
	if rrNew.Code != http.StatusOK {
		t.Fatalf("AC-5: der NEUE Code muss angenommen werden, bekam %d, body=%s", rrNew.Code, rrNew.Body.String())
	}
	if u := mustLoadUser(t, s, "anna"); u.PremiumSmsReplyTo != garminFromCoded {
		t.Errorf("AC-5: erwartet Rueckadresse %q nach dem neuen Code, bekam %q", garminFromCoded, u.PremiumSmsReplyTo)
	}
}

// ---------------------------------------------------------------------------
// AC-6: echte user_id aus dem Auth-Kontext, zwei Nutzer, nie "default".
//
// learnTestStore baut den Store mit der Vorgabe-Kennung "default"
// (store.New(tmpDir, "default")). Ein Handler, der statt des Kontexts auf
// s.UserID zurueckfaellt, schriebe nach users/default/ — deshalb wird die
// ABWESENHEIT dieser Datei mitgeprueft. "beide Hashes verschieden" allein
// wuerde eine dritte Schreibung nach default nicht bemerken.
// ---------------------------------------------------------------------------

func TestLinkCodeUsesRealUserIDNeverDefault(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "alice", Tier: "premium"})
	mustSaveUser(t, s, model.User{ID: "bob", Tier: "premium"})

	aliceCode := createLinkCode(t, s, "alice")
	bobCode := createLinkCode(t, s, "bob")

	if aliceCode == bobCode {
		t.Fatalf("AC-6: zwei Nutzer duerfen nie denselben Code bekommen (%q)", aliceCode)
	}

	for _, c := range []struct{ userID, own, foreign string }{
		{"alice", aliceCode, bobCode},
		{"bob", bobCode, aliceCode},
	} {
		stored, err := s.LoadLinkCode(c.userID)
		if err != nil || stored == nil {
			t.Fatalf("AC-6: %s hat keinen eigenen gespeicherten Code: %v (%v)", c.userID, err, stored)
		}
		if err := bcrypt.CompareHashAndPassword([]byte(stored.CodeHash), []byte(c.own)); err != nil {
			t.Errorf("AC-6: der Hash von %s gehoert nicht zu seinem eigenen Code: %v", c.userID, err)
		}
		if err := bcrypt.CompareHashAndPassword([]byte(stored.CodeHash), []byte(c.foreign)); err == nil {
			t.Errorf("AC-6: der Hash von %s passt auf den FREMDEN Code — Konten vermischt", c.userID)
		}
	}

	if _, err := os.Stat(linkCodePath(s, "default")); err == nil {
		t.Errorf("AC-6: es wurde nach users/default/ geschrieben (%s) — Rueckfall auf die "+
			"Vorgabe-Kennung statt der Kennung aus dem Auth-Kontext", linkCodePath(s, "default"))
	}

	rrAnon := httptest.NewRecorder()
	PostPremiumSmsLinkCodeHandler(s, bcrypt.MinCost)(rrAnon, newLinkCodeRequest(http.MethodPost, ""))
	if rrAnon.Code != http.StatusUnauthorized {
		t.Errorf("AC-6: ohne Auth-Kontext erwartet 401, bekam %d, body=%s", rrAnon.Code, rrAnon.Body.String())
	}
	if _, err := os.Stat(linkCodePath(s, "default")); err == nil {
		t.Errorf("AC-6: der Aufruf ohne Auth-Kontext hat nach users/default/ geschrieben")
	}
}

// ---------------------------------------------------------------------------
// AC-6, LESE-Haelfte (Adversary-Befund F003): Spiegelbild des Anon-Falls oben,
// der nur den SCHREIBENDEN Aufruf abdeckt.
//
// Der lesende Aufruf hat keine Schreibspur, an der man einen Rueckfall auf die
// Vorgabe-Kennung bemerken wuerde — er wuerde ihn STILL beantworten. Deshalb
// traegt hier ausgerechnet "default" einen Code: ein Handler, der ohne
// Auth-Kontext auf s.UserID zurueckfaellt (learnTestStore baut den Store mit
// store.New(tmpDir, "default")), meldete dessen Vorhandensein an einen
// Unangemeldeten weiter — eine Aussage ueber ein fremdes Konto.
//
// Positiv-Kontrolle voran: derselbe Aufruf MIT Kontext muss exists=true melden.
// Ohne sie bestuende der Test auch dann, wenn der Statusaufruf ueberhaupt nichts
// mehr faende.
// ---------------------------------------------------------------------------

func TestLinkCodeStatusWithoutAuthContextNeverFallsBackToDefault(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "default", Tier: "premium"})
	mustSaveLinkCode(t, s, "default", linkCodeAnna)

	rrAuth := httptest.NewRecorder()
	GetPremiumSmsLinkCodeHandler(s)(rrAuth, newLinkCodeRequest(http.MethodGet, "default"))
	if rrAuth.Code != http.StatusOK {
		t.Fatalf("Positiv-Kontrolle: mit Auth-Kontext erwartet 200, bekam %d, body=%s",
			rrAuth.Code, rrAuth.Body.String())
	}
	if exists, _ := linkCodeBody(t, rrAuth)["exists"].(bool); !exists {
		t.Fatalf("Positiv-Kontrolle: der gesetzte Code muss mit Kontext als exists=true gemeldet werden, body=%s",
			rrAuth.Body.String())
	}

	rrAnon := httptest.NewRecorder()
	GetPremiumSmsLinkCodeHandler(s)(rrAnon, newLinkCodeRequest(http.MethodGet, ""))
	raw := rrAnon.Body.String()
	if rrAnon.Code != http.StatusUnauthorized {
		t.Errorf("F003: der Statusaufruf ohne Auth-Kontext erwartet 401, bekam %d, body=%s", rrAnon.Code, raw)
	}
	if strings.Contains(raw, "exists") {
		t.Errorf("F003: der anonyme Statusaufruf BEANTWORTET die Frage — Rueckfall auf die "+
			"Vorgabe-Kennung users/default/ statt der Kennung aus dem Auth-Kontext, body=%s", raw)
	}
}
