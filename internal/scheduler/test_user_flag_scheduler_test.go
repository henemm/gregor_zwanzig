package scheduler

// TDD RED — Issue #2152, AC-1 / AC-3: Testkonto-Status im Scheduler-Fan-out
// ueber das Profilfeld is_test_user statt ueber die Namens-Heuristik.
// Spec: docs/specs/modules/testkonto_profilfeld.md
//
// Gemessen wird am WIRKORT (runForAllUsers → HTTP-Aufruf je Nutzer), nicht an
// filterOutTestUsers isoliert — damit ist dieser Test unabhaengig von der in
// GREEN gewaehlten Signatur. Vorgeschlagene GREEN-Signatur (Methode statt freier
// Funktion, damit s.store.LoadUser erreichbar ist):
//
//	func (s *Scheduler) filterOutTestUsers(jobID string, allUserIDs []string) []string
//	  → je ID s.store.LoadUser(id); uebersprungen wird, wenn model.IsTestAccount(u)
//	    (u.IsTestUser || strings.EqualFold(u.ID, "tg-live-e2e")).
//
// Bewusst KEIN neues Symbol in diesem Paket referenziert: das RED ist eine
// Assertion, kein Compile-Fehler — nach GREEN bleibt sichtbar, welche
// Zusicherung rot war. Die Assertion ist die EXAKTE Nutzermenge (nicht
// "enthaelt"), sonst passt AC-3 heute zufaellig (mitarbeiter42 faellt nicht
// unter die Namens-Heuristik) und eine Mutation "Flag ignorieren" wuerde nicht
// gefangen.

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"testing"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/store"
)

// writeFlagProfile legt users/<id>/user.json als Roh-JSON an — mit oder ohne
// is_test_user-Flag. Eigener Helfer, damit createTestUsers/testStoreWithUsers
// (Fremdnutzer) unveraendert bleiben.
func writeFlagProfile(t *testing.T, dataDir, id string, isTestUser bool) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", id)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir %s: %v", dir, err)
	}
	body := fmt.Sprintf(`{"id":%q,"mail_to":"%s@example.com"}`, id, id)
	if isTestUser {
		body = fmt.Sprintf(`{"id":%q,"mail_to":"%s@example.com","is_test_user":true}`, id, id)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(body), 0644); err != nil {
		t.Fatalf("write user.json for %s: %v", id, err)
	}
}

// runFanOutAndCollect fuehrt runForAllUsers gegen einen aufzeichnenden
// httptest-Server aus und liefert die sortierte Menge der bedienten user_ids.
func runFanOutAndCollect(t *testing.T, dataDir string, s *store.Store) []string {
	t.Helper()
	var mu sync.Mutex
	var served []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		served = append(served, r.URL.Query().Get("user_id"))
		mu.Unlock()
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, `{"status":"ok"}`)
	}))
	defer server.Close()

	cfg := &config.Config{PythonCoreURL: server.URL, SchedulerTimezone: "Europe/Vienna"}
	sched, err := New(cfg, s)
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	if err := sched.runForAllUsers("trip_reports", "/api/scheduler/trip-reports"); err != nil {
		t.Fatalf("runForAllUsers error: %v", err)
	}
	mu.Lock()
	defer mu.Unlock()
	out := append([]string(nil), served...)
	sort.Strings(out)
	return out
}

// TestUserFlag_FanOut_ServesProtesterWithoutFlag_AC1 — "protester" traegt
// "test" im Namen, aber KEIN Flag → wird regulaer bedient. Gegenprobe im
// selben Bestand (AC-3): "mitarbeiter42" mit is_test_user=true wird
// uebersprungen, obwohl der Name neutral ist. Erwartete EXAKTE Menge:
// {henning, protester}.
func TestUserFlag_FanOut_ServesProtesterWithoutFlag_AC1(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	writeFlagProfile(t, tmpDir, "henning", false)
	writeFlagProfile(t, tmpDir, "protester", false)
	writeFlagProfile(t, tmpDir, "mitarbeiter42", true)

	served := runFanOutAndCollect(t, tmpDir, s)

	want := []string{"henning", "protester"}
	if strings.Join(served, ",") != strings.Join(want, ",") {
		t.Fatalf("AC-1/AC-3: Fan-out bediente %v, erwartet exakt %v "+
			"(protester ohne Flag ist ein echter Nutzer; mitarbeiter42 mit Flag ist Testkonto)",
			served, want)
	}
}

// TestUserFlag_FanOut_SkipsFlaggedNeutralName_AC3 — isolierte Gegenprobe:
// NUR "mitarbeiter42" (neutraler Name, is_test_user=true) und "henning" im
// Bestand → genau "henning" wird bedient. Faengt die Mutation "Flag wird nicht
// gelesen" auch dann, wenn AC-1 aus anderem Grund gruen ist.
func TestUserFlag_FanOut_SkipsFlaggedNeutralName_AC3(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	writeFlagProfile(t, tmpDir, "henning", false)
	writeFlagProfile(t, tmpDir, "mitarbeiter42", true)

	served := runFanOutAndCollect(t, tmpDir, s)

	if strings.Join(served, ",") != "henning" {
		t.Fatalf("AC-3: Fan-out bediente %v, erwartet exakt [henning] "+
			"(mitarbeiter42 traegt is_test_user=true und muss uebersprungen werden)", served)
	}
}

// TestUserFlag_FanOut_TgLiveE2eStaysSkippedWithoutFlag_AC5 — die feste
// Fixture-Konstante bleibt ohne Flag Testkonto (Regressions-Pin, heute
// bereits gruen; sichert gegen Mitreissen in GREEN).
func TestUserFlag_FanOut_TgLiveE2eStaysSkippedWithoutFlag_AC5(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	writeFlagProfile(t, tmpDir, "henning", false)
	writeFlagProfile(t, tmpDir, "tg-live-e2e", false)

	served := runFanOutAndCollect(t, tmpDir, s)

	if strings.Join(served, ",") != "henning" {
		t.Fatalf("AC-5: Fan-out bediente %v, erwartet exakt [henning] "+
			"(tg-live-e2e ist die feste Fixture-Konstante und bleibt Testkonto)", served)
	}
}

// TestUserFlag_FanOut_UnreadableProfileIsServedFailOpen — GREEN-Ergaenzung
// (#2152): ein unlesbares user.json (kaputtes JSON) darf keinen echten Nutzer
// stumm schalten — filterOutTestUsers ist an dieser Stelle fail-open und
// bedient das Konto (mit Log). Bewacht die Fehlerpolitik, die kein AC-Test
// mit validen Profilen fangen wuerde.
func TestUserFlag_FanOut_UnreadableProfileIsServedFailOpen(t *testing.T) {
	tmpDir := t.TempDir()
	s := store.New(tmpDir, "default")
	writeFlagProfile(t, tmpDir, "henning", false)
	dir := filepath.Join(tmpDir, "users", "kaputt")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(`{"id":"kaputt",`), 0644); err != nil {
		t.Fatalf("write: %v", err)
	}

	served := runFanOutAndCollect(t, tmpDir, s)

	if strings.Join(served, ",") != "henning,kaputt" {
		t.Fatalf("fail-open: Fan-out bediente %v, erwartet exakt [henning kaputt] "+
			"(unlesbares Profil zaehlt als echter Nutzer)", served)
	}
}
