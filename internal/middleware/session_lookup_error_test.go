package middleware

// TDD RED — Issue #2353: Auth-Middleware verwechselt Lesefehler der
// Gästeliste mit "nicht angemeldet".
// Spec: docs/specs/modules/fix_2353_auth_lookup_fehler_503.md
//
// Diese Datei prüft ausschließlich den neuen Fehlerzweig: ein I/O-Fehler beim
// Lesen von sessions.json muss 503 (statt 401) ergeben, den nachgelagerten
// Handler NICHT aufrufen, Mandanten nicht gegenseitig beeinflussen und eine
// Log-Zeile OHNE sessionId schreiben. Geprüft wird über dieselbe
// HTTP-Oberfläche wie in session_allowlist_test.go (echte AuthMiddleware,
// echter httptest-Request) — dieselben Helfer (authProbe, writeAllowlist,
// seedUserRecord, makeNewSessionCookie, testSecret) werden wiederverwendet.

import (
	"bytes"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// authProbeCallTracking ist wie authProbe, verdrahtet next aber mit einem
// Handler, der ein called-Flag setzt statt die Nutzerkennung in den Body zu
// schreiben. Ein reiner Body-/Status-Vergleich (wie bisher) bleibt unauffällig,
// wenn next ZUSÄTZLICH zum 503 aufgerufen wird — httptest.ResponseRecorder
// ignoriert einen zweiten WriteHeader. Der geteilte authProbe-Helfer (~20
// weitere Nutzer) bleibt deshalb unangetastet (Adversary-Finding F001,
// Fix-Loop 1).
func authProbeCallTracking(t *testing.T, dataDir, secret, cookieValue string) (*httptest.ResponseRecorder, *bool) {
	t.Helper()
	called := false
	next := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		called = true
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(UserIDFromContext(r.Context())))
	})
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	rr := httptest.NewRecorder()
	AuthMiddleware(secret, store.New(dataDir, ""))(next).ServeHTTP(rr, req)
	return rr, &called
}

// brokenAllowlistDir legt für userID eine sessions.json an, die als
// VERZEICHNIS statt als Datei existiert — os.ReadFile scheitert daran mit
// EISDIR, einem I/O-Fehler, der von os.IsNotExist NICHT erfasst wird
// (internal/store/sessions.go:readSessionFile). Liefert den erzeugten Pfad
// zurück, damit Aufrufer ihn aus einer Log-Zeile herausrechnen können — der
// *PathError* von os.ReadFile trägt den Pfad in seinem Fehlertext, und der
// Pfad enthält seinerseits die userID (data/users/<id>/sessions.json). Ohne
// das herauszurechnen, würde ein Log-Aufruf OHNE userId-Argument (Bug) den
// Test trotzdem bestehen, weil die Kennung beiläufig über den Pfad im Text
// steht.
func brokenAllowlistDir(t *testing.T, dataDir, userID string) string {
	t.Helper()
	seedUserRecord(t, dataDir, userID)
	brokenPath := filepath.Join(dataDir, "users", userID, "sessions.json")
	if err := os.MkdirAll(brokenPath, 0755); err != nil {
		t.Fatalf("MkdirAll sessions.json als Verzeichnis: %v", err)
	}
	return brokenPath
}

// AC-2: I/O-Fehler beim Lesen der Gästeliste ergibt 503, next() läuft nicht.
func TestLookupError_UnreadableAllowlist_Returns503(t *testing.T) {
	dataDir := t.TempDir()
	brokenAllowlistDir(t, dataDir, "alice")

	cookie := makeNewSessionCookie("alice", "sess-broken001", time.Now().Unix(), testSecret)
	rr, called := authProbeCallTracking(t, dataDir, testSecret, cookie)

	if rr.Code != http.StatusServiceUnavailable {
		t.Errorf("AC-2: erwartet 503 bei unlesbarer Gästeliste, bekommen %d", rr.Code)
	}
	// Beleg, dass next() NICHT lief — direkt am Handler-Aufruf gemessen, nicht
	// am Body: ein zusätzlicher next.ServeHTTP-Aufruf neben dem 503 bliebe an
	// Status/Body unauffällig (F001).
	if *called {
		t.Fatalf("AC-2: nachgelagerter Handler darf bei 503 nicht laufen")
	}
}

// AC-3: Mandantentrennung — der Lesefehler eines Nutzers darf einen anderen
// Nutzer im selben Datenbestand nicht beeinflussen.
func TestLookupError_DoesNotAffectOtherUserInSameDataDir(t *testing.T) {
	dataDir := t.TempDir()
	brokenAllowlistDir(t, dataDir, "alice")
	writeAllowlist(t, dataDir, "bob", "sess-bobs-ok01")

	aliceCookie := makeNewSessionCookie("alice", "sess-broken001", time.Now().Unix(), testSecret)
	bobCookie := makeNewSessionCookie("bob", "sess-bobs-ok01", time.Now().Unix(), testSecret)

	aliceRR, aliceCalled := authProbeCallTracking(t, dataDir, testSecret, aliceCookie)
	if aliceRR.Code != http.StatusServiceUnavailable {
		t.Errorf("AC-3: alice (kaputte Gästeliste) erwartet 503, bekommen %d", aliceRR.Code)
	}
	if *aliceCalled {
		t.Fatalf("AC-3: nachgelagerter Handler darf für alice bei 503 nicht laufen (F001)")
	}

	// Positivkontrolle (F002): ohne sie bestünde authProbeCallTracking auch
	// dann, wenn das called-Flag nie gesetzt würde.
	bobRR, bobCalled := authProbeCallTracking(t, dataDir, testSecret, bobCookie)
	if bobRR.Code != http.StatusOK {
		t.Errorf("AC-3: bob (intakte Gästeliste) erwartet 200, bekommen %d", bobRR.Code)
	}
	if !*bobCalled {
		t.Fatalf("Positivkontrolle: bei gelisteter Sitzung muss der nachgelagerte Handler laufen")
	}
	if bobRR.Body.String() != "bob" {
		t.Errorf("AC-3: erwartet Nutzerkennung 'bob' im Kontext, bekommen %q", bobRR.Body.String())
	}
}

// AC-4: die Log-Zeile bei 503 enthält die Nutzerkennung, aber NIE die
// Anmelde-Kennung (sessionId) oder den rohen Cookie-Wert.
func TestLookupError_LogsUserIdNotSessionId(t *testing.T) {
	dataDir := t.TempDir()
	brokenPath := brokenAllowlistDir(t, dataDir, "alice")

	const secretSessionID = "sess-geheim-4711"
	cookie := makeNewSessionCookie("alice", secretSessionID, time.Now().Unix(), testSecret)

	var buf bytes.Buffer
	log.SetOutput(&buf)
	t.Cleanup(func() { log.SetOutput(os.Stderr) })

	rr := authProbe(t, dataDir, testSecret, cookie)
	if rr.Code != http.StatusServiceUnavailable {
		t.Fatalf("AC-4 Testaufbau: erwartet 503, bekommen %d — Log kann so nicht sinnvoll geprüft werden", rr.Code)
	}

	logged := buf.String()
	// Der *PathError* von os.ReadFile traegt den vollen Pfad im Fehlertext,
	// und der Pfad enthaelt seinerseits "alice" (.../users/alice/sessions.json).
	// Ohne den Pfad herauszurechnen, wuerde ein Log-Aufruf OHNE eigenstaendiges
	// userId-Argument den Test bestehen, weil die Kennung nur beilaeufig ueber
	// den Pfad im Text steht — genau die Mutation, die diese Zusicherung
	// eigentlich fangen soll.
	ohnePfad := strings.ReplaceAll(logged, brokenPath, "<pfad>")
	if !strings.Contains(ohnePfad, "alice") {
		t.Errorf("AC-4: die Nutzerkennung 'alice' muss eigenstaendig geloggt werden, nicht nur "+
			"beilaeufig im Dateipfad des Fehlers: %q", logged)
	}
	if strings.Contains(logged, secretSessionID) {
		t.Errorf("AC-4: Log-Zeile darf die Anmelde-Kennung (sessionId) NICHT enthalten, bekommen %q", logged)
	}
	if strings.Contains(logged, cookie) {
		t.Errorf("AC-4: Log-Zeile darf den rohen Cookie-Wert NICHT enthalten, bekommen %q", logged)
	}
}

// AC-1 (Regression, im selben File nachgewiesen): eine Kennung, die schlicht
// nicht auf einer LESBAREN Gästeliste steht, bleibt 401 — nicht 503.
func TestLookupError_ListedFileButUnlistedSession_StaysStatus401(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "alice", "sess-listed0001")

	cookie := makeNewSessionCookie("alice", "sess-notlisted01", time.Now().Unix(), testSecret)
	rr := authProbe(t, dataDir, testSecret, cookie)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("AC-1: nicht gelistete Kennung bei lesbarer Gästeliste muss 401 bleiben, bekommen %d", rr.Code)
	}
}
