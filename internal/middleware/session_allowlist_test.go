package middleware

// TDD RED — Issue #2129: dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal.
// Spec: docs/specs/modules/session_allowlist.md
//
// Diese Datei prüft die Prüfstelle selbst: Zerlegung des Anmelde-Merkmals,
// Format-Weiche alt/neu, stille Hebung des Altformats und die Ablehnungsgründe.
// Geprüft wird ausschließlich über die HTTP-Oberfläche (echte AuthMiddleware,
// echter httptest-Request) — nicht über interne Funktionen: die Zusicherung
// lautet "200 gegen 401", und dort muss sie gemessen werden.

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/store"
)

// makeNewSessionCookie baut das neue vierteilige Anmelde-Merkmal:
// {userId}.{sessionId}.{ts}.{sig}, HMAC-SHA256 über "{userId}:{sessionId}:{ts}".
func makeNewSessionCookie(userId, sessionId string, ts int64, secret string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(fmt.Sprintf("%s:%s:%d", userId, sessionId, ts)))
	sig := hex.EncodeToString(mac.Sum(nil))
	return fmt.Sprintf("%s.%s.%d.%s", userId, sessionId, ts, sig)
}

// seedUserRecord legt das Konto auf der Platte an. Noetig, weil der
// Legacy-Zweig seit Issue #2129 prueft, ob das Konto ueberhaupt noch existiert
// — ein Alt-Merkmal traegt keine Anmelde-Kennung, die man gegen eine Liste
// halten koennte, und wuerde nach einer Kontoloeschung sonst weiter durchgehen.
func seedUserRecord(t *testing.T, dataDir, userID string) {
	t.Helper()
	dir := filepath.Join(dataDir, "users", userID)
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	body := fmt.Sprintf(`{"id":%q,"created_at":"2026-09-06T00:00:00Z"}`, userID)
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(body), 0644); err != nil {
		t.Fatalf("WriteFile user.json: %v", err)
	}
}

// writeAllowlist legt die Gästeliste eines Nutzers auf der Platte an.
//
// RED-PHASEN-FESTLEGUNG: Die Spec legt die JSON-Gestalt von
// data/users/<user_id>/sessions.json nicht fest. Sie wird hier an EINER Stelle
// festgelegt (PO-/Lead-bestätigt 2026-09-05); die GREEN-Phase erzeugt entweder
// genau dieses Format oder passt ausschließlich diesen Helfer an.
//
// Zwei Auflagen aus der Bestätigung, die die Gestalt mittragen muss:
//   - Der Eintrag ist ein OBJEKT, kein blanker String — später kommt womöglich
//     eine Geräteübersicht dazu (Known Limitations der Spec), und die darf
//     ohne Formatbruch hineinwachsen.
//   - Eine fehlende Datei bedeutet "leere Liste", nie einen Fehler. Bewacht
//     von TestNewFormatCookie_NoAllowlistFile_Returns401NotServerError.
func writeAllowlist(t *testing.T, dataDir, userID string, sessionIDs ...string) {
	t.Helper()
	seedUserRecord(t, dataDir, userID)
	dir := filepath.Join(dataDir, "users", userID)
	type entry struct {
		ID        string    `json:"id"`
		CreatedAt time.Time `json:"created_at"`
	}
	payload := struct {
		Sessions []entry `json:"sessions"`
	}{}
	for _, id := range sessionIDs {
		payload.Sessions = append(payload.Sessions, entry{ID: id, CreatedAt: time.Now()})
	}
	data, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		t.Fatalf("Marshal: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "sessions.json"), data, 0644); err != nil {
		t.Fatalf("WriteFile sessions.json: %v", err)
	}
}

// authProbe schickt eine echte Anfrage mit dem gegebenen Cookie durch die echte
// AuthMiddleware auf einen geschützten Pfad.
//
// dataDir ist die Wurzel des Datenbestands (dataDir/users/<id>/sessions.json),
// aus der die Middleware ihre Gästeliste liest — bei jeder Anfrage direkt von
// der Platte, ohne Zwischenspeicher.
func authProbe(t *testing.T, dataDir, secret, cookieValue string) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest("GET", "/api/trips", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	rr := httptest.NewRecorder()
	AuthMiddleware(secret, store.New(dataDir, ""))(dummyHandler()).ServeHTTP(rr, req)
	return rr
}

// upgradedCookie liefert das im Antwort-Header nachgesetzte Anmelde-Merkmal
// (leer, wenn keines gesetzt wurde).
func upgradedCookie(rr *httptest.ResponseRecorder) string {
	for _, c := range rr.Result().Cookies() {
		if c.Name == "gz_session" {
			return c.Value
		}
	}
	return ""
}

func segments(value string) int {
	return len(strings.Split(value, "."))
}

// AC-1 (Prüfseite): Ein vierteiliges Merkmal, dessen Anmelde-Kennung auf der
// Gästeliste steht, wird angenommen und trägt die richtige Nutzerkennung.
func TestNewFormatCookie_ListedSession_Returns200(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "alice", "sess-aaaa1111")

	cookie := makeNewSessionCookie("alice", "sess-aaaa1111", time.Now().Unix(), testSecret)
	if segments(cookie) != 4 {
		t.Fatalf("Testaufbau kaputt: erwartet 4 Segmente, sind %d", segments(cookie))
	}

	rr := authProbe(t, dataDir, testSecret, cookie)

	if rr.Code != http.StatusOK {
		t.Errorf("AC-1: erwartet 200 für gelistete Anmelde-Kennung, bekommen %d", rr.Code)
	}
	if rr.Body.String() != "alice" {
		t.Errorf("AC-1: erwartet Nutzerkennung 'alice' im Kontext, bekommen %q", rr.Body.String())
	}
}

// AC-3: Das neue Merkmal bleibt jenseits der alten 24-Stunden-Grenze gültig.
// Die Systemuhr wird nicht gestellt, sondern der Zeitstempel im Merkmal wird
// vordatiert — dieselbe Wirkung, ohne Prozess-Zustand anzufassen.
func TestNewFormatCookie_ValidBeyond24Hours(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "alice", "sess-old00001")

	// 25 Stunden alt — nach der alten Regel längst abgelaufen.
	ts := time.Now().Add(-25 * time.Hour).Unix()
	cookie := makeNewSessionCookie("alice", "sess-old00001", ts, testSecret)

	rr := authProbe(t, dataDir, testSecret, cookie)

	if rr.Code != http.StatusOK {
		t.Errorf("AC-3: 25 h altes vierteiliges Merkmal muss gültig bleiben, bekommen %d", rr.Code)
	}
}

// AC-10: Ein gültiges dreiteiliges Alt-Merkmal wird angenommen UND im selben
// Zug durch ein vierteiliges ersetzt.
func TestLegacyCookie_AcceptedAndUpgradedToFourPart(t *testing.T) {
	dataDir := t.TempDir()
	seedUserRecord(t, dataDir, "alice")
	legacy := makeSessionCookie("alice", time.Now().Unix(), testSecret)

	rr := authProbe(t, dataDir, testSecret, legacy)

	if rr.Code != http.StatusOK {
		t.Fatalf("AC-10: gültiges Alt-Merkmal muss angenommen werden, bekommen %d", rr.Code)
	}
	up := upgradedCookie(rr)
	if up == "" {
		t.Fatalf("AC-10: erwartet nachgesetztes gz_session-Cookie in der Antwort, keines gesetzt")
	}
	if segments(up) != 4 {
		t.Fatalf("AC-10: nachgesetztes Merkmal muss 4 Segmente haben, hat %d (%q)", segments(up), up)
	}
	if !strings.HasPrefix(up, "alice.") {
		t.Errorf("AC-10: nachgesetztes Merkmal muss auf 'alice' lauten, ist %q", up)
	}

	// Zweite Anfrage MIT dem gehobenen Merkmal. Ohne sie prüft der Test nur
	// die FORM des neuen Cookies, nicht seine Brauchbarkeit — und wäre auch
	// dann grün, wenn die Hebung das Merkmal gar nicht in die Gästeliste
	// einträgt. Genau das ist der Fall, den AC-10 ausschließt: der Nutzer darf
	// sich nicht erneut anmelden müssen, das gehobene Merkmal muss sofort
	// tragen.
	rrUpgraded := authProbe(t, dataDir, testSecret, up)
	if rrUpgraded.Code != http.StatusOK {
		t.Errorf("AC-10: das gehobene Merkmal muss sofort gültig sein, bekommen %d", rrUpgraded.Code)
	}
	if rrUpgraded.Body.String() != "alice" {
		t.Errorf("AC-10: gehobenes Merkmal muss Nutzerkennung 'alice' tragen, bekommen %q",
			rrUpgraded.Body.String())
	}
}

// AC-11: Ein Alt-Merkmal jenseits von 24 Stunden wird abgewiesen.
//
// Positivkontrolle voran: ein frisches Alt-Merkmal MUSS durchkommen (und
// gehoben werden). Ohne diese Kontrolle bestünde der Test auch dann, wenn die
// Prüfstelle jedes Alt-Merkmal pauschal abwiese — er prüfte dann nichts.
func TestLegacyCookie_OlderThan24Hours_Rejected(t *testing.T) {
	dataDir := t.TempDir()
	seedUserRecord(t, dataDir, "alice")

	fresh := makeSessionCookie("alice", time.Now().Add(-23*time.Hour).Unix(), testSecret)
	rrFresh := authProbe(t, dataDir, testSecret, fresh)
	if rrFresh.Code != http.StatusOK {
		t.Fatalf("AC-11 Positivkontrolle: 23 h altes Alt-Merkmal muss gültig sein, bekommen %d", rrFresh.Code)
	}
	if segments(upgradedCookie(rrFresh)) != 4 {
		t.Errorf("AC-11 Positivkontrolle: 23 h altes Alt-Merkmal muss gehoben werden, nachgesetzt wurde %q",
			upgradedCookie(rrFresh))
	}

	stale := makeSessionCookie("alice", time.Now().Add(-25*time.Hour).Unix(), testSecret)
	rrStale := authProbe(t, dataDir, testSecret, stale)
	if rrStale.Code != http.StatusUnauthorized {
		t.Errorf("AC-11: 25 h altes Alt-Merkmal muss abgewiesen werden, bekommen %d", rrStale.Code)
	}
}

// Fehlerzweig der Widerrufs-Prüfung: ist die Gästeliste unlesbar (kaputtes
// oder halb geschriebenes JSON), wird das Alt-Merkmal abgewiesen — die
// Prüfstelle macht ZU, nicht auf.
//
// Warum das zählt: bei fail-open würde eine beschädigte Datei jedes
// Alt-Merkmal durchwinken, auch ein zuvor widerrufenes. Der Widerruf hinge
// dann an der Unversehrtheit einer Datei, die niemand überwacht — dieselbe
// Fehlerklasse wie ein Merkmal, das eine Kontolöschung überlebt, nur über
// einen anderen Auslöser.
//
// Eine FEHLENDE Datei ist etwas anderes und bleibt der leere Stand
// (TestNewFormatCookie_NoAllowlistFile_Returns401NotServerError, und die
// Positivkontrolle hier läuft ebenfalls ohne Datei).
func TestLegacyCookie_CorruptAllowlistFile_Rejected(t *testing.T) {
	// Dasselbe Merkmal in beiden Hälften — der einzige Unterschied ist der
	// Zustand der Datei.
	legacy := makeSessionCookie("alice", time.Now().Unix(), testSecret)

	// Positivkontrolle in EIGENEM Datenbestand: bei intaktem Bestand muss
	// genau dieses Merkmal durchkommen. Ohne sie bestünde der Test auch dann,
	// wenn Alt-Merkmale generell abgewiesen würden.
	okDir := t.TempDir()
	seedUserRecord(t, okDir, "alice")
	if rr := authProbe(t, okDir, testSecret, legacy); rr.Code != http.StatusOK {
		t.Fatalf("Positivkontrolle: bei intaktem Bestand muss das Alt-Merkmal gültig sein, bekommen %d",
			rr.Code)
	}

	// Defektfall: sessions.json ist kein gültiges JSON.
	badDir := t.TempDir()
	seedUserRecord(t, badDir, "alice")
	corrupt := filepath.Join(badDir, "users", "alice", "sessions.json")
	if err := os.WriteFile(corrupt, []byte(`{"sessions": [ das ist kein JSON`), 0644); err != nil {
		t.Fatalf("WriteFile sessions.json: %v", err)
	}

	rr := authProbe(t, badDir, testSecret, legacy)
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("unlesbare Gästeliste muss das Alt-Merkmal abweisen (fail-closed), bekommen %d", rr.Code)
	}
}

// AC-12 (a): Ein einzeln verändertes Signatur-Segment wird abgewiesen.
// Mit Positivkontrolle: dasselbe Merkmal unverändert muss angenommen werden.
func TestNewFormatCookie_TamperedSignature_Rejected(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "alice", "sess-tamper01")

	intact := makeNewSessionCookie("alice", "sess-tamper01", time.Now().Unix(), testSecret)
	if rr := authProbe(t, dataDir, testSecret, intact); rr.Code != http.StatusOK {
		t.Fatalf("AC-12a Positivkontrolle: unverändertes Merkmal muss gültig sein, bekommen %d", rr.Code)
	}

	parts := strings.Split(intact, ".")
	sig := []byte(parts[3])
	if sig[0] == 'a' {
		sig[0] = 'b'
	} else {
		sig[0] = 'a'
	}
	parts[3] = string(sig)
	tampered := strings.Join(parts, ".")

	rr := authProbe(t, dataDir, testSecret, tampered)
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("AC-12a: manipulierte Signatur muss abgewiesen werden, bekommen %d", rr.Code)
	}
}

// AC-12 (b): Ein korrekt signiertes Merkmal, dessen Anmelde-Kennung NICHT auf
// der Gästeliste steht, wird abgewiesen.
// Mit Positivkontrolle: dieselbe Kennung gelistet muss angenommen werden —
// sonst bestünde der Test auch dann, wenn jedes vierteilige Merkmal abgewiesen
// würde (genau der heutige Zustand).
func TestNewFormatCookie_UnlistedSession_Rejected(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "alice", "sess-listed01")

	listed := makeNewSessionCookie("alice", "sess-listed01", time.Now().Unix(), testSecret)
	if rr := authProbe(t, dataDir, testSecret, listed); rr.Code != http.StatusOK {
		t.Fatalf("AC-12b Positivkontrolle: gelistete Kennung muss gültig sein, bekommen %d", rr.Code)
	}

	unlisted := makeNewSessionCookie("alice", "sess-notlisted", time.Now().Unix(), testSecret)
	rr := authProbe(t, dataDir, testSecret, unlisted)
	if rr.Code != http.StatusUnauthorized {
		t.Errorf("AC-12b: nicht gelistete Anmelde-Kennung muss abgewiesen werden, bekommen %d", rr.Code)
	}
}

// AC-12 (b), Sonderfall "Nutzer hat noch nie eine Gästeliste gehabt":
// Eine FEHLENDE sessions.json bedeutet leere Liste, nicht Fehler. Das Merkmal
// wird abgewiesen (401) — der Dienst darf daran nicht mit 5xx scheitern, sonst
// sperrte ein fehlender Dateiname jeden Bestandsnutzer mit einem Serverfehler
// aus statt mit einer Anmeldeaufforderung.
func TestNewFormatCookie_NoAllowlistFile_Returns401NotServerError(t *testing.T) {
	dataDir := t.TempDir() // bewusst leer: keine users/, keine sessions.json

	cookie := makeNewSessionCookie("alice", "sess-nofile01", time.Now().Unix(), testSecret)
	rr := authProbe(t, dataDir, testSecret, cookie)

	if rr.Code != http.StatusUnauthorized {
		t.Errorf("AC-12b: fehlende sessions.json muss 401 ergeben (leere Liste), bekommen %d", rr.Code)
	}
	if rr.Code >= 500 {
		t.Errorf("AC-12b: fehlende sessions.json darf kein Serverfehler sein, bekommen %d", rr.Code)
	}
}

// AC-14 (Go-Seite): Eine Nutzerkennung mit Punkt wird von rechts zerlegt —
// beide Formate müssen dieselbe Kennung liefern.
//
// GEMESSEN WIRD SEIT ISSUE #2140 die Zerlegung selbst (validateSession), nicht
// mehr die Ende-zu-Ende-Strecke über authProbe: die Pfad-Traversal-Sperre
// lässt eine Kennung mit Punkt nicht mehr an den Datenbestand
// (store.ValidUserID, `^[a-zA-Z0-9_-]+$`) — ein 200 ist mit dieser Fixture
// also strukturell nicht mehr erreichbar, die 200-Erwartung hätte den Wächter
// nur noch über einen Stellvertreter gemessen. Die #2129-Zusicherung "von
// RECHTS zerlegen" bleibt unverändert bewacht, jetzt an der Stelle, an der sie
// wirkt. Das Frontend-Gegenstück steht in frontend/src/lib/session_format.test.ts.
func TestDottedUserID_SplitFromTheRight(t *testing.T) {
	const uid = "alice.smith"
	const sid = "sess-dot00001"

	t.Run("neues Format", func(t *testing.T) {
		cookie := makeNewSessionCookie(uid, sid, time.Now().Unix(), testSecret)
		gotUID, gotSID, _, isNew, ok := validateSession(cookie, testSecret)
		if !ok {
			t.Fatalf("AC-14: Merkmal mit %q muss gültig zerlegt werden, wurde verworfen", uid)
		}
		if !isNew {
			t.Errorf("AC-14: vierteiliges Merkmal muss als neues Format gelesen werden")
		}
		if gotUID != uid {
			t.Errorf("AC-14: erwartet Nutzerkennung %q, bekommen %q", uid, gotUID)
		}
		if gotSID != sid {
			t.Errorf("AC-14: erwartet Anmelde-Kennung %q, bekommen %q", sid, gotSID)
		}
	})

	t.Run("Altformat", func(t *testing.T) {
		cookie := makeSessionCookie(uid, time.Now().Unix(), testSecret)
		gotUID, gotSID, _, isNew, ok := validateSession(cookie, testSecret)
		if !ok {
			t.Fatalf("AC-14: Alt-Merkmal mit %q muss gültig zerlegt werden, wurde verworfen", uid)
		}
		if isNew {
			t.Errorf("AC-14: dreiteiliges Merkmal darf nicht als neues Format gelesen werden")
		}
		if gotUID != uid {
			t.Errorf("AC-14: erwartet Nutzerkennung %q, bekommen %q", uid, gotUID)
		}
		if gotSID != "" {
			t.Errorf("AC-14: Alt-Merkmal trägt keine Anmelde-Kennung, bekommen %q", gotSID)
		}
	})
}

// Issue #2140: Die Pfad-Traversal-Sperre muss auch auf dem Weg durch die
// Anmelde-Prüfung wirken — und zwar mit 401, NICHT mit einem Serverfehler.
// Dieselbe Zusicherung wie bei der fehlenden sessions.json
// (TestNewFormatCookie_NoAllowlistFile_Returns401NotServerError): ein Fehler
// aus dem Datenbestand darf nie als 5xx durchschlagen.
//
// Der scharfe Fall ist "../users/bob": filepath.Join(dataDir, "users",
// "../users/bob") landet GENAU im Verzeichnis des real angelegten "bob" — vor
// der Sperre las die Middleware dort dessen echte Gästeliste, fand die
// Anmelde-Kennung und ließ den Angreifer mit fremder Nutzerkennung durch.
func TestTraversalUserIDInCookie_Returns401NotServerError(t *testing.T) {
	dataDir := t.TempDir()
	writeAllowlist(t, dataDir, "bob", "sess-bobs00001")

	cases := []struct {
		name   string
		cookie string
	}{
		{"neues Format", makeNewSessionCookie("../bob", "sess-bobs00001", time.Now().Unix(), testSecret)},
		{"Altformat", makeSessionCookie("../bob", time.Now().Unix(), testSecret)},
		{"users-Nutzlast trifft Bobs echtes Verzeichnis", makeNewSessionCookie("../users/bob", "sess-bobs00001", time.Now().Unix(), testSecret)},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			rr := authProbe(t, dataDir, testSecret, tc.cookie)
			if rr.Code >= 500 {
				t.Fatalf("#2140: Traversal-Kennung darf keinen Serverfehler ergeben, bekommen %d", rr.Code)
			}
			if rr.Code != http.StatusUnauthorized {
				t.Errorf("#2140: erwartet 401 für Traversal-Kennung, bekommen %d (Kontext-Kennung %q)", rr.Code, rr.Body.String())
			}
		})
	}
}
