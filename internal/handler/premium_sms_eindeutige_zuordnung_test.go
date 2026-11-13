package handler

// Issue #2961 Welle 2 (ADR-0116, Spec
// security_haertung_2026_11_premium_sms_rueckkanal.md AC-1..AC-4):
// eindeutige Zuordnung der Premium-SMS-Rueckadresse.
//
//   - Ein mitgeschickter GUELTIGER Verknuepfungscode gewinnt immer gegen einen
//     gespeicherten Rueckadress-Treffer eines anderen Kontos (Garmin vergibt
//     Absendernummern aus einem rotierenden Pool neu).
//   - Lernt Konto X die Rueckadresse N, verliert jedes andere Konto N
//     (Eindeutigkeit wie bei der Telegram-chat_id); nur die beiden
//     Rueckadress-Felder werden entfernt, alle uebrigen Felder bleiben.
//   - Ein falscher Code eines bereits zugeordneten Absenders kippt dessen
//     Zuordnung nicht.
//
// Gemessen am echten Lern-Handler mit echtem Store auf Temp-Verzeichnis, je mit
// mehreren Konten (Mandantentrennung).

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

const garminFromPool = "4917000000021"

// rohesProfil liest user.json als Roh-Map — misst, was auf der Platte steht.
func rohesProfil(t *testing.T, dataDir, id string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join(dataDir, "users", id, "user.json"))
	if err != nil {
		t.Fatalf("user.json von %s nicht lesbar: %v", id, err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("user.json von %s kein JSON: %v", id, err)
	}
	return m
}

// AC-1: gueltiger Code schlaegt den frischen Treffer eines ANDEREN Kontos.
// "premium-pool-bert" haelt die Nummer frisch (frueherer Pool-Inhaber),
// "premium-pool-anna" schickt aus derselben Nummer ihren gueltigen Code.
func TestLearnValidCodeWinsOverForeignFreshStoredMatch(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-2 * time.Hour)
	mustSaveUser(t, s, model.User{ID: "premium-pool-anna", Tier: "premium"})
	mustSaveUser(t, s, model.User{
		ID: "premium-pool-bert", Tier: "premium",
		PremiumSmsReplyTo: garminFromPool, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveLinkCode(t, s, "premium-pool-anna", linkCodeAnna)

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget))
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromPool, "code": linkCodeAnna}))

	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}
	if got, _ := learnResponseBody(t, rr)["user_id"].(string); got != "premium-pool-anna" {
		t.Fatalf("der gueltige Code muss gewinnen: erwartet premium-pool-anna, bekam %q", got)
	}
	if got := mustLoadUser(t, s, "premium-pool-anna").PremiumSmsReplyTo; got != garminFromPool {
		t.Errorf("anna: Rueckadresse %q, erwartet %q", got, garminFromPool)
	}
	bert := mustLoadUser(t, s, "premium-pool-bert")
	if bert.PremiumSmsReplyTo != "" || bert.PremiumSmsReplyAt != nil {
		t.Errorf("bert muss die neu vergebene Nummer verlieren, hat %q / %v", bert.PremiumSmsReplyTo, bert.PremiumSmsReplyAt)
	}
}

// AC-2: Lernen entfernt die Nummer bei allen anderen Konten — auch bei
// veralteten Eintraegen und bei Konten ausserhalb des Premium-Tarifs —, laesst
// deren uebrige (auch dem Modell unbekannte) Felder unberuehrt und fasst
// Konten mit anderer Nummer nicht an.
func TestLearnRemovesReplyAddressFromAllOtherAccounts(t *testing.T) {
	s := learnTestStore(t)
	staleAt := time.Now().UTC().Add(-(model.PremiumSmsReplyTTL + 48*time.Hour))
	otherAt := time.Now().UTC().Add(-time.Hour)
	mustSaveUser(t, s, model.User{ID: "premium-pool-anna", Tier: "premium"})
	mustSaveUser(t, s, model.User{
		ID: "premium-pool-bert", Tier: "premium", Email: "bert@example.invalid",
		PremiumSmsReplyTo: garminFromPool, PremiumSmsReplyAt: &staleAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "standard-pool-dora", Tier: "standard",
		PremiumSmsReplyTo: garminFromPool, PremiumSmsReplyAt: &staleAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-pool-carl", Tier: "premium",
		PremiumSmsReplyTo: "4917000000099", PremiumSmsReplyAt: &otherAt,
	})
	// Ein dem Modell unbekanntes Feld bei bert: muss das Entfernen ueberleben.
	pfad := filepath.Join(s.DataDir, "users", "premium-pool-bert", "user.json")
	roh := rohesProfil(t, s.DataDir, "premium-pool-bert")
	roh["kuenftiges_feld"] = "bleibt"
	data, _ := json.Marshal(roh)
	if err := os.WriteFile(pfad, data, 0o600); err != nil {
		t.Fatal(err)
	}
	carlVorher := readUserJSON2154(t, s, "premium-pool-carl")
	mustSaveLinkCode(t, s, "premium-pool-anna", linkCodeAnna)

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget))
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromPool, "code": linkCodeAnna}))
	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200, bekam %d: %s", rr.Code, rr.Body.String())
	}

	for _, id := range []string{"premium-pool-bert", "standard-pool-dora"} {
		m := rohesProfil(t, s.DataDir, id)
		if _, ok := m["premium_sms_reply_to"]; ok {
			t.Errorf("%s: premium_sms_reply_to muss entfernt sein: %v", id, m)
		}
		if _, ok := m["premium_sms_reply_at"]; ok {
			t.Errorf("%s: premium_sms_reply_at muss entfernt sein: %v", id, m)
		}
	}
	bert := rohesProfil(t, s.DataDir, "premium-pool-bert")
	if bert["kuenftiges_feld"] != "bleibt" || bert["email"] != "bert@example.invalid" {
		t.Errorf("bert: uebrige Felder muessen erhalten bleiben (Merge), bekam %v", bert)
	}
	if nachher := readUserJSON2154(t, s, "premium-pool-carl"); string(nachher) != string(carlVorher) {
		t.Errorf("carl (andere Nummer) darf nicht angefasst werden.\nvorher:  %s\nnachher: %s", carlVorher, nachher)
	}
}

// AC-3: Ein falscher Code aus der Nummer eines bereits eindeutig zugeordneten
// Kontos kippt die Zuordnung nicht — der Befehl gehoert weiter dem Inhaber,
// kein anderes Konto wird beruehrt.
func TestLearnWrongCodeKeepsOwnFreshStoredMatch(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-pool-anna", Tier: "premium",
		PremiumSmsReplyTo: garminFromPool, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{ID: "premium-pool-bert", Tier: "premium"})
	mustSaveLinkCode(t, s, "premium-pool-bert", linkCodeBert)

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(DefaultPremiumSmsLinkCodeBudget))
	rr := httptest.NewRecorder()
	h(rr, newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromPool, "code": "XXZZZZZ999"}))
	if rr.Code != http.StatusOK {
		t.Fatalf("erwartet 200 (eigener frischer Treffer), bekam %d: %s", rr.Code, rr.Body.String())
	}
	if got, _ := learnResponseBody(t, rr)["user_id"].(string); got != "premium-pool-anna" {
		t.Fatalf("erwartet premium-pool-anna, bekam %q", got)
	}
	if got := mustLoadUser(t, s, "premium-pool-bert").PremiumSmsReplyTo; got != "" {
		t.Errorf("bert darf nichts lernen, hat %q", got)
	}
}
