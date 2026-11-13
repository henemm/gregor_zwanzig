package handler

// Issue #2961 Welle 2 (ADR-0116, Spec AC-13/AC-14): "Verbindung trennen" fuer
// Premium-SMS. DELETE /api/auth/premium-sms-reply loescht Rueckadresse und
// Zeitstempel des ANGEMELDETEN Kontos (Kennung nur aus dem Auth-Kontext); der
// Verknuepfungs-Code bleibt, alle anderen Felder und alle anderen Konten
// bleiben unberuehrt. Gemessen am echten Handler mit echtem Store.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
)

func newDisconnectRequest(userID string) *http.Request {
	req := httptest.NewRequest(http.MethodDelete, "/api/auth/premium-sms-reply", nil)
	if userID != "" {
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	}
	return req
}

func TestPremiumSmsDisconnectClearsOnlyOwnReplyAddress(t *testing.T) {
	s := learnTestStore(t)
	at := time.Now().UTC().Add(-time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-anna", Tier: "premium", Email: "anna@example.invalid",
		PremiumSmsReplyTo: "4917000000051", PremiumSmsReplyAt: &at,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-bert", Tier: "premium",
		PremiumSmsReplyTo: "4917000000052", PremiumSmsReplyAt: &at,
	})
	mustSaveLinkCode(t, s, "premium-anna", linkCodeAnna)
	bertVorher := readUserJSON2154(t, s, "premium-bert")
	codeVorher, err := os.ReadFile(linkCodePath(s, "premium-anna"))
	if err != nil {
		t.Fatal(err)
	}

	rr := httptest.NewRecorder()
	DeletePremiumSmsReplyHandler(s)(rr, newDisconnectRequest("premium-anna"))
	if rr.Code != http.StatusNoContent {
		t.Fatalf("erwartet 204, bekam %d: %s", rr.Code, rr.Body.String())
	}

	anna := mustLoadUser(t, s, "premium-anna")
	if anna.PremiumSmsReplyTo != "" || anna.PremiumSmsReplyAt != nil {
		t.Errorf("anna: Rueckadresse muss geloescht sein, hat %q / %v", anna.PremiumSmsReplyTo, anna.PremiumSmsReplyAt)
	}
	if anna.Email != "anna@example.invalid" || anna.Tier != "premium" {
		t.Errorf("anna: uebrige Felder muessen bleiben, bekam %+v", anna)
	}
	if codeNachher, err := os.ReadFile(linkCodePath(s, "premium-anna")); err != nil || !bytes.Equal(codeVorher, codeNachher) {
		t.Errorf("der Verknuepfungs-Code muss unveraendert bleiben (err=%v)", err)
	}
	if bertNachher := readUserJSON2154(t, s, "premium-bert"); !bytes.Equal(bertVorher, bertNachher) {
		t.Errorf("bert darf nicht beruehrt werden.\nvorher:  %s\nnachher: %s", bertVorher, bertNachher)
	}

	// Danach meldet sich ein Absender aus der alten Nummer ohne Code: er wird
	// nicht mehr anna zugeordnet.
	lr := httptest.NewRecorder()
	PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget))(
		lr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": "4917000000051"}))
	if lr.Code == http.StatusOK {
		t.Fatalf("nach dem Trennen darf die alte Nummer ohne Code nicht zuordnen: %s", lr.Body.String())
	}
}

func TestPremiumSmsDisconnectWithoutAuthContextNeverTouchesDefault(t *testing.T) {
	s := learnTestStore(t)
	at := time.Now().UTC()
	mustSaveUser(t, s, model.User{ID: "default", Tier: "premium", PremiumSmsReplyTo: "4917000000053", PremiumSmsReplyAt: &at})
	vorher := readUserJSON2154(t, s, "default")

	rr := httptest.NewRecorder()
	DeletePremiumSmsReplyHandler(s)(rr, newDisconnectRequest(""))
	if rr.Code != http.StatusUnauthorized {
		t.Fatalf("ohne Auth-Kontext erwartet 401, bekam %d", rr.Code)
	}
	if nachher := readUserJSON2154(t, s, "default"); !bytes.Equal(vorher, nachher) {
		t.Errorf("das Konto default darf nie beruehrt werden")
	}
}

func TestPremiumSmsDisconnectUnknownUserIs404(t *testing.T) {
	s := learnTestStore(t)
	rr := httptest.NewRecorder()
	DeletePremiumSmsReplyHandler(s)(rr, newDisconnectRequest("premium-gibtsnicht"))
	if rr.Code != http.StatusNotFound {
		t.Fatalf("erwartet 404, bekam %d", rr.Code)
	}
}
