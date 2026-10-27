package handler

// TDD RED — Issue #2154 Scheibe A: Premium-SMS Verknuepfungscode.
// Spec: docs/specs/modules/fix_2154_premium_sms_verknuepfungscode.md v1.0
//
// Diese Datei benutzt AUSSCHLIESSLICH heute existierende Symbole
// (PostPremiumSmsLearnHandler, store.New, model.User, model.PremiumSmsReplyTTL
// sowie die Helfer aus premium_sms_connect_test.go). Grund: `go test`
// uebersetzt immer das GANZE Paket. Stuende hier auch nur ein Test, der ein
// erst zu bauendes Symbol nennt, waere der RED-Beleg ein Uebersetzungsfehler
// statt der Bug-Reproduktion. Alles, was neue Symbole braucht, liegt in
// premium_sms_learn_with_code_test.go / premium_sms_link_code_test.go
// (Artefakt 2).
//
// Erfundene Rufnummern (Repo ist oeffentlich), disjunkt zu garminFromA/B.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const (
	garminFromStale = "4917000000003"
	garminFromFresh = "4917000000004"
)

// readUserJSON2154 liest die ROHE user.json. Der Byte-Vergleich ist bewusst
// schaerfer als ein Feldvergleich: er faengt auch ein Schreiben, das ein
// anderes Feld beruehrt oder die Datei neu formatiert.
func readUserJSON2154(t *testing.T, s *store.Store, id string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json von %s nicht lesbar: %v", id, err)
	}
	return data
}

// userFieldsExcept2154 zerlegt die user.json generisch und entfernt genau ein
// Feld. Generisch statt Positivliste: ein neu hinzukommendes Profilfeld faellt
// sonst still aus der Pruefung.
func userFieldsExcept2154(t *testing.T, raw []byte, skip string) map[string]any {
	t.Helper()
	var fields map[string]any
	if err := json.Unmarshal(raw, &fields); err != nil {
		t.Fatalf("user.json nicht als JSON lesbar: %v (%s)", err, raw)
	}
	delete(fields, skip)
	return fields
}

// ---------------------------------------------------------------------------
// AC-1 — BUG-REPRODUKTION (heute rot).
//
// Genau ein Premium-Nutzer, eine fremde Garmin-Nummer, kein Code im Body.
// Heute greift der Ein-Kandidaten-Fallback (premium_sms_connect.go:71-73) und
// schreibt die fremde Nummer als Rueckadresse dieses Nutzers — Uebernahme des
// Rueckkanals ohne jedes Geheimnis, mit Kostenwirkung. Erwartet wird das
// Gegenteil: Fehlerstatus und eine bit-identische user.json.
// ---------------------------------------------------------------------------

func TestLearnRejectsSoleCandidateWithoutCode(t *testing.T) {
	s := learnTestStore(t)
	mustSaveUser(t, s, model.User{ID: "premium-user", Tier: "premium", Email: "premium@example.invalid"})
	before := readUserJSON2154(t, s, "premium-user")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromA})
	rr := httptest.NewRecorder()
	h(rr, req)

	after := readUserJSON2154(t, s, "premium-user")
	if !bytes.Equal(before, after) {
		t.Errorf("AC-1: user.json MUSS unveraendert bleiben — eine fremde Nummer ohne Code "+
			"darf keine Rueckadresse setzen.\nvorher:  %s\nnachher: %s", before, after)
	}
	if rr.Code == http.StatusOK {
		t.Errorf("AC-1: erwartet Fehlerstatus (kein 200), bekam %d, body=%s", rr.Code, rr.Body.String())
	}
}

// ---------------------------------------------------------------------------
// AC-4 (Ablehn-Haelfte) — heute rot.
//
// Gespeicherte Rueckadresse, deren PremiumSmsReplyAt aelter als
// model.PremiumSmsReplyTTL ist (Alter TTL + 1 Tag = 31 Tage). Heute vergleicht
// premium_sms_connect.go:63-65 NUR die Nummer, ohne Frist — der veraltete
// Treffer bestaetigt sich selbst und Garmin kann die Nummer laengst einem
// fremden Geraet zugeteilt haben.
//
// Zwei Premium-Kandidaten, damit der Ein-Kandidaten-Fallback als Grund
// ausscheidet: rot bzw. gruen wird dieser Test allein an der Frist.
// Die zweite Haelfte von AC-4 (mit korrektem Code wird dieselbe Nachricht
// anschliessend zugeordnet) braucht neue Symbole und steht in Artefakt 2.
// ---------------------------------------------------------------------------

func TestLearnRejectsStaleStoredMatchWithoutCode(t *testing.T) {
	s := learnTestStore(t)
	staleAt := time.Now().UTC().Add(-(model.PremiumSmsReplyTTL + 24*time.Hour))
	mustSaveUser(t, s, model.User{
		ID: "premium-stale", Tier: "premium",
		PremiumSmsReplyTo: garminFromStale, PremiumSmsReplyAt: &staleAt,
	})
	// Zweiter Premium-Nutzer OHNE gespeicherte Rueckadresse: kein konkurrierender
	// storedMatch, aber auch kein eindeutiger Einzelkandidat.
	mustSaveUser(t, s, model.User{ID: "premium-other", Tier: "premium"})

	beforeStale := readUserJSON2154(t, s, "premium-stale")
	beforeOther := readUserJSON2154(t, s, "premium-other")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromStale})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code == http.StatusOK {
		t.Errorf("AC-4: ein Treffer aelter als PremiumSmsReplyTTL (%v) darf NICHT ohne Code "+
			"bestaetigt werden, bekam %d, body=%s", model.PremiumSmsReplyTTL, rr.Code, rr.Body.String())
	}
	if after := readUserJSON2154(t, s, "premium-stale"); !bytes.Equal(beforeStale, after) {
		t.Errorf("AC-4: user.json des veralteten Treffers MUSS unveraendert bleiben "+
			"(auch der Zeitstempel darf sich nicht auffrischen).\nvorher:  %s\nnachher: %s",
			beforeStale, after)
	}
	if after := readUserJSON2154(t, s, "premium-other"); !bytes.Equal(beforeOther, after) {
		t.Errorf("AC-4: der zweite Premium-Nutzer darf NIE beruehrt werden.\nvorher:  %s\nnachher: %s",
			beforeOther, after)
	}
}

// ---------------------------------------------------------------------------
// AC-3 — ERHALTUNGS-WAECHTER, heute GRUEN und danach ebenfalls gruen.
//
// KEINE RED-Evidenz: dieser Test belegt nicht den Bug, sondern dass der Fix
// den einzigen legitimen code-losen Pfad nicht mit abraeumt. Ein frischer
// gespeicherter Treffer bestaetigt weiterhin ohne Code, und zwar so, dass sich
// AUSSCHLIESSLICH der Zeitstempel bewegt.
//
// Abgrenzung zu TestLearnPrefersStoredMatchOverSoleCandidateRule
// (premium_sms_connect_test.go:147): der prueft zwei Felder namentlich, dieser
// prueft generisch, dass sich sonst NICHTS in der Datei bewegt hat.
// ---------------------------------------------------------------------------

func TestLearnConfirmsFreshStoredMatchWithoutCode(t *testing.T) {
	s := learnTestStore(t)
	freshAt := time.Now().UTC().Add(-1 * time.Hour)
	mustSaveUser(t, s, model.User{
		ID: "premium-fresh", Tier: "premium", Email: "fresh@example.invalid",
		PremiumSmsReplyTo: garminFromFresh, PremiumSmsReplyAt: &freshAt,
	})
	mustSaveUser(t, s, model.User{ID: "premium-bystander", Tier: "premium"})

	beforeFresh := readUserJSON2154(t, s, "premium-fresh")
	beforeBystander := readUserJSON2154(t, s, "premium-bystander")

	h := PostPremiumSmsLearnHandler(s, NewPremiumSmsRateLimiter(5))
	req := newLearnRequest("127.0.0.1:54321", map[string]any{"from": garminFromFresh})
	rr := httptest.NewRecorder()
	h(rr, req)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-3: ein frischer gespeicherter Treffer muss ohne Code weiterhin bestaetigen, "+
			"bekam %d, body=%s", rr.Code, rr.Body.String())
	}

	afterFresh := readUserJSON2154(t, s, "premium-fresh")
	beforeRest := userFieldsExcept2154(t, beforeFresh, "premium_sms_reply_at")
	afterRest := userFieldsExcept2154(t, afterFresh, "premium_sms_reply_at")
	if !reflect.DeepEqual(beforeRest, afterRest) {
		t.Errorf("AC-3: ausser dem Zeitstempel darf sich KEIN Feld aendern.\nvorher:  %+v\nnachher: %+v",
			beforeRest, afterRest)
	}

	updated := mustLoadUser(t, s, "premium-fresh")
	if updated.PremiumSmsReplyTo != garminFromFresh {
		t.Errorf("AC-3: PremiumSmsReplyTo muss %q bleiben, bekam %q", garminFromFresh, updated.PremiumSmsReplyTo)
	}
	if updated.PremiumSmsReplyAt == nil || !updated.PremiumSmsReplyAt.After(freshAt) {
		t.Errorf("AC-3: der Zeitstempel haette aufgefrischt werden muessen (alt=%v, neu=%v)",
			freshAt, updated.PremiumSmsReplyAt)
	}

	if after := readUserJSON2154(t, s, "premium-bystander"); !bytes.Equal(beforeBystander, after) {
		t.Errorf("AC-3: kein anderer Kandidat darf beruehrt werden.\nvorher:  %s\nnachher: %s",
			beforeBystander, after)
	}
}
