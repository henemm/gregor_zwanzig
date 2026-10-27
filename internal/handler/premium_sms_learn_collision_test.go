package handler

// TDD RED — Issue #2328: Premium-SMS-Rueckkanal, Kollisionserkennung beim
// "ohne Code"-Zuordnungsweg.
// Spec: docs/specs/modules/fix_2328_premium_sms_rueckkanal_kollision.md v1.0
//
// Muss FEHLSCHLAGEN bis premium_sms_connect.go die Sammelschleife auf
// storedMatches []*model.User umstellt und resolvePremiumSmsTarget bei >=2
// frischen Treffern statt sofortiger Bestaetigung zum Code-Pfad durchreicht
// (neuer Ablehnungsgrund "stored_reply_to_ambiguous"). Bewusst der
// WIRE-STRING statt einer noch nicht existierenden Konstante
// (reasonStoredReplyToAmbiguous) -- sonst waere der RED-Beleg ein
// Uebersetzungsfehler statt Verhaltensbeweis (Lehre aus #2154,
// premium_sms_learn_without_code_test.go:6-13).
//
// Fixture-IDs sind KEIN Zufall: os.ReadDir (store.ListUserIDs) sortiert
// lexikalisch, die heutige Sammelschleife ueberschreibt storedMatch
// unkommentiert mit dem ZULETZT geladenen Treffer -- "last wins" nach Namen.
// Jede Kollisions-Fixture hier ist so benannt, dass der heutige
// "last wins"-Gewinner NICHT der vom jeweiligen AC geforderte Nutzer ist.
// Sonst waere ein Test allein von der Ladereihenfolge abhaengig zufaellig
// gruen, ohne die Luecke wirklich zu pruefen.
//
// AC-5 (Ein-Kandidaten-Regression) braucht keinen neuen Test: sie ist
// TestLearnConfirmsFreshStoredMatchWithoutCode in
// premium_sms_learn_without_code_test.go -- nach der Signaturaenderung in
// /50-implement dort gegenlesen, nicht hier duplizieren.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

const garminFromCollision = "4917000000007"

func learnResponseBody(t *testing.T, rr *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var resp map[string]any
	if err := json.Unmarshal(rr.Body.Bytes(), &resp); err != nil {
		t.Fatalf("Antwort nicht JSON-dekodierbar: %v (%s)", err, rr.Body.String())
	}
	return resp
}

// ---------------------------------------------------------------------------
// AC-1: zwei frische Kollisionsnutzer, kein Code -> 409 mit
// stored_reply_to_ambiguous, KEIN SaveUser bei beiden.
//
// Heute (Bug): "last wins" macht den lexikalisch letzten Treffer zum
// storedMatch; der ist frisch, resolvePremiumSmsTarget bestaetigt ihn
// SOFORT -- SaveUser wird tatsaechlich aufgerufen, die user.json aendert
// sich. Rot unabhaengig von der Fixture-Reihenfolge.
// ---------------------------------------------------------------------------

func TestLearnRejectsAmbiguousFreshCollisionWithoutCode(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-1 * time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-a", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-b", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	beforeA := readUserJSON2154(t, s, "premium-collision-a")
	beforeB := readUserJSON2154(t, s, "premium-collision-b")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCollision})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusConflict {
		t.Errorf("AC-1: erwartet 409, bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	if reason, _ := learnResponseBody(t, rr)["reason"].(string); reason != "stored_reply_to_ambiguous" {
		t.Errorf("AC-1: erwartet reason=stored_reply_to_ambiguous, bekam %q, body=%s", reason, rr.Body.String())
	}
	if after := readUserJSON2154(t, s, "premium-collision-a"); !bytes.Equal(beforeA, after) {
		t.Errorf("AC-1: user.json von premium-collision-a MUSS unveraendert bleiben.\nvorher:  %s\nnachher: %s",
			beforeA, after)
	}
	if after := readUserJSON2154(t, s, "premium-collision-b"); !bytes.Equal(beforeB, after) {
		t.Errorf("AC-1: user.json von premium-collision-b MUSS unveraendert bleiben.\nvorher:  %s\nnachher: %s",
			beforeB, after)
	}
}

// ---------------------------------------------------------------------------
// AC-2: dieselbe Kollision, gueltiger Code eines der beiden Nutzer -> 200,
// GENAU dieser Nutzer aktualisiert, der andere unveraendert (Beweis gegen
// Self-DoS/Lockout).
//
// "premium-collision-anna" (Code-Inhaberin) sortiert lexikalisch VOR
// "premium-collision-bert" (kein Code) -- bert laedt zuletzt und gewinnt
// heute als storedMatch, ist frisch und wird SOFORT bestaetigt, der
// mitgeschickte Code wird nie geprueft. Der Handler wuerde heute bert
// aktualisieren statt anna -- eine Fixture mit umgekehrter Reihenfolge waere
// zufaellig gruen gewesen.
// ---------------------------------------------------------------------------

func TestLearnResolvesAmbiguousCollisionWithValidCode(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-1 * time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-anna", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-bert", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveLinkCode(t, s, "premium-collision-anna", linkCodeAnna)
	beforeBert := readUserJSON2154(t, s, "premium-collision-bert")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCollision, "code": linkCodeAnna})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-2: erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	if userID, _ := learnResponseBody(t, rr)["user_id"].(string); userID != "premium-collision-anna" {
		t.Errorf("AC-2: erwartet user_id=premium-collision-anna (Code-Inhaberin), bekam %q, body=%s",
			userID, rr.Body.String())
	}
	anna := mustLoadUser(t, s, "premium-collision-anna")
	if anna.PremiumSmsReplyTo != garminFromCollision {
		t.Errorf("AC-2: PremiumSmsReplyTo von anna erwartet %q, bekam %q", garminFromCollision, anna.PremiumSmsReplyTo)
	}
	if after := readUserJSON2154(t, s, "premium-collision-bert"); !bytes.Equal(beforeBert, after) {
		t.Errorf("AC-2: user.json von premium-collision-bert (kein Code) MUSS unveraendert bleiben.\n"+
			"vorher:  %s\nnachher: %s", beforeBert, after)
	}
}

// ---------------------------------------------------------------------------
// AC-3: ein frischer + ein veralteter Treffer auf derselben Nummer, kein
// Code -> deterministisch der frische Nutzer, HTTP 200, KEINE Kollision
// (Regressionswaechter gegen eine naive Treffer-Zaehlung ohne
// Freshness-Filter).
//
// "premium-collision-fresh" sortiert lexikalisch VOR
// "premium-collision-stale" -- stale laedt zuletzt und gewinnt heute als
// storedMatch, ist aber NICHT frisch: resolvePremiumSmsTarget faellt auf
// code=="" zurueck und lehnt mit 409 ab, obwohl der frische Nutzer laengst
// eindeutig waere.
// ---------------------------------------------------------------------------

func TestLearnPrefersFreshMatchOverStaleCollisionWithoutCode(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-1 * time.Hour)
	staleAt := time.Now().UTC().Add(-(model.PremiumSmsReplyTTL + 24*time.Hour))
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-fresh", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-stale", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &staleAt,
	})

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCollision})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-3: erwartet 200 (kein Kollisionsfall, nur EIN frischer Treffer), bekam %d, body=%s",
			rr.Code, rr.Body.String())
	}
	if userID, _ := learnResponseBody(t, rr)["user_id"].(string); userID != "premium-collision-fresh" {
		t.Errorf("AC-3: erwartet user_id=premium-collision-fresh, bekam %q, body=%s", userID, rr.Body.String())
	}
}

// ---------------------------------------------------------------------------
// AC-4: Dry-Run-Variante von AC-1 -> outcome "would_skip" mit
// stored_reply_to_ambiguous, KEIN SaveUser bei beiden.
// ---------------------------------------------------------------------------

func TestLearnDryRunReportsAmbiguousCollisionWithoutSaving(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-1 * time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-a", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{
		ID: "premium-collision-b", Tier: "premium",
		PremiumSmsReplyTo: garminFromCollision, PremiumSmsReplyAt: &freshAt,
	})
	beforeA := readUserJSON2154(t, s, "premium-collision-a")
	beforeB := readUserJSON2154(t, s, "premium-collision-b")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromCollision, "dry_run": true})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-4: Dry-Run meldet nie hart ab, erwartet 200, bekam %d, body=%s", rr.Code, rr.Body.String())
	}
	resp := learnResponseBody(t, rr)
	if resp["outcome"] != "would_skip" {
		t.Errorf("AC-4: erwartet outcome=would_skip, bekam %+v", resp)
	}
	if reason, _ := resp["reason"].(string); reason != "stored_reply_to_ambiguous" {
		t.Errorf("AC-4: erwartet reason=stored_reply_to_ambiguous, bekam %q, body=%s", reason, rr.Body.String())
	}
	if after := readUserJSON2154(t, s, "premium-collision-a"); !bytes.Equal(beforeA, after) {
		t.Errorf("AC-4: user.json von premium-collision-a MUSS unveraendert bleiben (Dry-Run).\n"+
			"vorher:  %s\nnachher: %s", beforeA, after)
	}
	if after := readUserJSON2154(t, s, "premium-collision-b"); !bytes.Equal(beforeB, after) {
		t.Errorf("AC-4: user.json von premium-collision-b MUSS unveraendert bleiben (Dry-Run).\n"+
			"vorher:  %s\nnachher: %s", beforeB, after)
	}
}
