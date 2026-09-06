package handler_test

// TDD RED — Issue #2129: dauerhafte Anmeldung mit widerrufbarem Anmelde-Merkmal.
// Spec: docs/specs/modules/session_allowlist.md — AC-2, 4, 5, 6, 7, 8, 9, 15, 16.
//
// Externes Testpaket (handler_test) mit Absicht: der Endpunkt "auf allen
// Geräten abmelden" existiert noch nicht. Über den echten router.New
// adressiert bricht kein Symbolaufruf die Kompilierung — der Request läuft
// heute in ein 404, und in der GREEN-Phase greift die Route automatisch, ohne
// dass dieser Test angefasst werden muss. Ein Go-Test, der eine noch nicht
// existierende Funktion aufruft, nähme das ganze Paket mit in den
// Kompilierfehler; dann fielen auch alle Bestandstests aus, und das wäre kein
// brauchbares RED.
//
// Kein Mock: echte HTTP-Anfragen gegen den vollständig verdrahteten Router mit
// echtem Dateispeicher in einem Temp-Verzeichnis. Kein Netz, kein Versand —
// der "Passwort vergessen"-Mailweg wird umgangen, indem das Reset-Token direkt
// über den Store gesetzt wird.

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"
	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Umgebung --------------------------------------------------------------

type authEnv struct {
	router  http.Handler
	store   *store.Store
	dataDir string
	secret  string
}

func newAuthEnv(t *testing.T) *authEnv {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()

	s := store.New(cfg.DataDir, cfg.UserID)

	wa, err := webauthn.New(&webauthn.Config{
		RPID:          cfg.WebAuthnRPID,
		RPDisplayName: cfg.WebAuthnRPDisplayName,
		RPOrigins:     []string{"http://localhost:5173"},
	})
	if err != nil {
		t.Fatalf("webauthn.New: %v", err)
	}

	sched, err := scheduler.New(cfg, s)
	if err != nil {
		t.Fatalf("scheduler.New: %v", err)
	}
	t.Cleanup(sched.Stop)

	r := router.New(router.Deps{
		Config:             cfg,
		Store:              s,
		WeatherProvider:    nil,
		WebAuthn:           wa,
		ChallengeStore:     handler.NewChallengeStore(),
		Scheduler:          sched,
		TelegramTokenStore: handler.NewTelegramTokenStore(cfg.DataDir),
		GitCommit:          "test",
	})

	return &authEnv{router: r, store: s, dataDir: cfg.DataDir, secret: cfg.SessionSecret}
}

// seedUser legt ein Konto direkt im Datenbestand an.
//
// JEDER TEST DIESER DATEI BENUTZT EINE EIGENE KONTO-KENNUNG. Das ist keine
// Kosmetik: `SignSession` (internal/middleware/auth.go:77-83) kennt nur
// Sekundenauflösung und keine Anmelde-Kennung, liefert für dieselbe
// Nutzerkennung innerhalb derselben Sekunde also ein IDENTISCHES Merkmal — und
// die heutige Sperrliste ist eine paketglobale sync.Map, die alle Tests
// desselben Prozesses teilen. Mit einer gemeinsamen Kennung würde ein
// Abmelde-Test jeden nachfolgenden Test vergiften: dessen frisch ausgestelltes
// Merkmal wäre buchstabengleich mit dem gesperrten und käme als 401 zurück.
// Gemessen im ersten RED-Lauf, sechs Tests scheiterten daran am falschen Grund.
func (e *authEnv) seedUser(t *testing.T, id, password string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	if err := e.store.SaveUser(model.User{
		ID: id, PasswordHash: string(hash), Email: id + "@example.com", CreatedAt: time.Now(),
	}); err != nil {
		t.Fatalf("SaveUser %s: %v", id, err)
	}
}

// login meldet ein Gerät an und liefert den Wert des ausgestellten Merkmals.
func (e *authEnv) login(t *testing.T, id, password string) string {
	t.Helper()
	cookie, err := e.loginNoFatal(id, password)
	if err != nil {
		t.Fatalf("Anmeldung %s: %v", id, err)
	}
	return cookie
}

// loginNoFatal ist die aus Nebenläufigkeit aufrufbare Fassung: t.Fatalf aus
// einer fremden Goroutine heraus ist unzulässig, deshalb wird der Fehler
// zurückgegeben und erst in der Test-Goroutine ausgewertet.
func (e *authEnv) loginNoFatal(id, password string) (string, error) {
	req := httptest.NewRequest("POST", "/api/auth/login",
		strings.NewReader(fmt.Sprintf(`{"username":%q,"password":%q}`, id, password)))
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	if w.Code != 200 {
		return "", fmt.Errorf("erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" {
			return c.Value, nil
		}
	}
	return "", fmt.Errorf("kein gz_session-Cookie in der Antwort")
}

// probe legt das Merkmal einem geschützten Endpunkt vor (gleicher Prozess).
func (e *authEnv) probe(t *testing.T, cookieValue string) int {
	t.Helper()
	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w.Code
}

func (e *authEnv) post(t *testing.T, path, cookieValue, body string) int {
	t.Helper()
	return e.do(t, "POST", path, cookieValue, body)
}

func (e *authEnv) do(t *testing.T, method, path, cookieValue, body string) int {
	t.Helper()
	return e.doResp(t, method, path, cookieValue, body).Code
}

func (e *authEnv) doResp(t *testing.T, method, path, cookieValue, body string) *httptest.ResponseRecorder {
	t.Helper()
	var req *http.Request
	if body == "" {
		req = httptest.NewRequest(method, path, nil)
	} else {
		req = httptest.NewRequest(method, path, strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
	}
	if cookieValue != "" {
		req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	}
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w
}

// sessionCookieOf liefert das in einer Antwort gesetzte Anmelde-Merkmal
// (leer, wenn keines oder ein geloeschtes gesetzt wurde).
func sessionCookieOf(w *httptest.ResponseRecorder) string {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.MaxAge > 0 {
			return c.Value
		}
	}
	return ""
}

func fourSegments(t *testing.T, ac, label, cookieValue string) {
	t.Helper()
	if n := len(strings.Split(cookieValue, ".")); n != 4 {
		t.Errorf("%s: %s muss 4 Punkt-Segmente haben, hat %d (%q)", ac, label, n, cookieValue)
	}
}

// --- Neustart-Sonde --------------------------------------------------------

const (
	probeEnvFlag   = "GZ_RESTART_PROBE"
	probeEnvDir    = "GZ_RESTART_DATADIR"
	probeEnvSecret = "GZ_RESTART_SECRET"
	probeEnvCookie = "GZ_RESTART_COOKIE"
	probeMarker    = "PROBE_STATUS="
)

// probeAfterRestart startet eine ECHTE zweite Prozess-Instanz des
// Testbinaries und legt ihr dasselbe Anmelde-Merkmal vor.
//
// WAS ZWISCHEN DEN DURCHGÄNGEN VERWORFEN WIRD: der komplette Adressraum des
// ersten Durchgangs. Namentlich die paketglobale middleware.sessionBlacklist
// (sync.Map, internal/middleware/auth.go:16), jede store.Store-Instanz, der
// ChallengeStore, der otpStore, sämtliche Ratenbegrenzer und jeder
// Zwischenspeicher, den die GREEN-Phase noch einbauen könnte. Die EINZIGE
// Brücke zwischen den beiden Durchgängen sind vier Zeichenketten in
// Umgebungsvariablen: Datenverzeichnis, Geheimnis, Cookie-Wert und das
// Sonden-Flag. Keine Pipe, die Objekte trägt, kein gemeinsamer Speicher, kein
// Socket. Das Dateisystem wird ABSICHTLICH geteilt — ein echter Dienst-Neustart
// behält die Platte ja auch; genau das ist die Zusicherung.
//
// WARUM NICHT EINFACH sessionBlacklist ZURÜCKSETZEN: das setzte genau den
// Zustand zurück, den man heute KENNT. Käme in GREEN ein Allowlist-
// Zwischenspeicher hinzu, bliebe er stehen und der Test bewiese still nichts
// mehr. Der Kindprozess ist gleichgültig dagegen, welcher Zustand existiert.
//
// GRENZE DER AUSSAGE: bewiesen wird "kein Zustand INNERHALB dieses Prozesses".
// Läge der Widerrufsstand jemals in einem zweiten, langlebigen Dienst, sähe das
// Kind ihn weiter und die Sonde wäre blind. Nach dem gewählten Entwurf (nur
// Dateien, ausdrücklich kein Zwischenspeicher) trifft das nicht zu — aber das
// ist die Bedingung, unter der der Nachweis trägt. Einen echten
// systemd-Neustart in Produktion beweist er ohnehin nicht; das bleibt Sache
// der Staging-Prüfung.
func probeAfterRestart(t *testing.T, dataDir, secret, cookieValue string) int {
	t.Helper()

	cmd := exec.Command(os.Args[0], "-test.run=^TestRestartProbeChild$", "-test.count=1")
	cmd.Env = append(os.Environ(),
		probeEnvFlag+"=1",
		probeEnvDir+"="+dataDir,
		probeEnvSecret+"="+secret,
		probeEnvCookie+"="+cookieValue,
	)
	out, err := cmd.CombinedOutput()

	// HARTE ABBRUCHREGEL: ohne Marker gibt es kein Ergebnis. Eine stumme Sonde
	// — Kind überspringt sich, Elternprozess bucht das als Erfolg — wäre
	// schlimmer als gar keine Sonde. Es gibt hier keinen Pfad, auf dem "keine
	// Antwort" zu "bestanden" wird.
	for _, line := range strings.Split(string(out), "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, probeMarker) {
			continue
		}
		code, convErr := strconv.Atoi(strings.TrimPrefix(line, probeMarker))
		if convErr != nil {
			t.Fatalf("Neustart-Sonde: unlesbarer Statuscode %q (%v)\nAusgabe:\n%s", line, convErr, out)
		}
		return code
	}
	t.Fatalf("Neustart-Sonde lieferte keinen %s-Marker (exec-Fehler: %v).\n"+
		"Ohne Marker gibt es kein Messergebnis — der Test besteht NICHT still.\nAusgabe:\n%s",
		probeMarker, err, out)
	return 0
}

// TestRestartProbeChild ist die Sonde selbst und läuft nur im Kindprozess.
// Im regulären Testlauf überspringt sie sich; die Rekursionssperre über
// probeEnvFlag verhindert, dass das Kind seinerseits Kinder startet.
func TestRestartProbeChild(t *testing.T) {
	if os.Getenv(probeEnvFlag) != "1" {
		t.Skip("Neustart-Sonde: läuft nur als Kindprozess von probeAfterRestart")
	}

	dataDir := os.Getenv(probeEnvDir)
	secret := os.Getenv(probeEnvSecret)
	cookieValue := os.Getenv(probeEnvCookie)
	if dataDir == "" || secret == "" || cookieValue == "" {
		t.Fatalf("Neustart-Sonde: unvollständige Übergabe (dir=%q secret gesetzt=%v cookie gesetzt=%v)",
			dataDir, secret != "", cookieValue != "")
	}

	// Frischer Store aus dem Datenverzeichnis — nichts aus dem Elternprozess.
	// Die Gästeliste wird ausschließlich von der Platte gelesen; das ist die
	// einzige Brücke zwischen den beiden Durchgängen.
	fresh := store.New(dataDir, "")

	req := httptest.NewRequest("GET", "/api/auth/profile", nil)
	req.AddCookie(&http.Cookie{Name: "gz_session", Value: cookieValue})
	rr := httptest.NewRecorder()
	authmw.AuthMiddleware(secret, fresh)(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if authmw.UserIDFromContext(r.Context()) == "" {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		w.WriteHeader(http.StatusOK)
	})).ServeHTTP(rr, req)

	fmt.Printf("%s%d\n", probeMarker, rr.Code)
}

// --- AC-2 ------------------------------------------------------------------

// AC-2: Eine frisch ausgestellte Anmeldung übersteht einen echten Neustart.
//
// Die Vierteiligkeit wird mitgeprüft, weil der Test sonst HEUTE SCHON grün
// wäre: das dreiteilige Merkmal übersteht einen Neustart ebenfalls — es gibt
// ja überhaupt keinen Zustand. Erst mit der Segmentzahl misst der Test die
// dateibasierte Gästeliste statt der bloßen Abwesenheit von Zustand.
func TestSessionSurvivesServiceRestart(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac2"
	e.seedUser(t, uid, "geheim123")
	cookie := e.login(t, uid, "geheim123")

	fourSegments(t, "AC-2", "ausgestelltes Merkmal", cookie)

	if code := e.probe(t, cookie); code != http.StatusOK {
		t.Fatalf("AC-2: Merkmal muss vor dem Neustart gültig sein, bekommen %d", code)
	}
	if code := probeAfterRestart(t, e.dataDir, e.secret, cookie); code != http.StatusOK {
		t.Errorf("AC-2: Merkmal muss den Neustart überleben, bekommen %d", code)
	}
}

// --- AC-4 ------------------------------------------------------------------

// AC-4: Abmelden auf einem Gerät wirkt sofort UND über einen echten Neustart
// hinweg. Der zweite Teil ist die Gegenprobe, die heute fehlschlägt: die
// Sperrliste ist reiner Prozessspeicher.
func TestLogoutRevokesSessionAcrossRestart(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac4"
	e.seedUser(t, uid, "geheim123")
	cookie := e.login(t, uid, "geheim123")

	if code := e.probe(t, cookie); code != http.StatusOK {
		t.Fatalf("AC-4 Positivkontrolle: Merkmal muss vor dem Abmelden gültig sein, bekommen %d", code)
	}
	if code := e.post(t, "/api/auth/logout", cookie, ""); code != http.StatusOK {
		t.Fatalf("AC-4: Abmelden erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-4: Merkmal muss sofort ungültig sein, bekommen %d", code)
	}
	if code := probeAfterRestart(t, e.dataDir, e.secret, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-4: Merkmal muss auch nach dem Neustart ungültig bleiben, bekommen %d", code)
	}
}

// --- AC-5 ------------------------------------------------------------------

// AC-5: Abmelden auf einem Gerät lässt das andere Gerät angemeldet.
//
// Die Zusicherungen "A != B" und "beide vierteilig" stehen voran, weil der
// Test sonst sekundengenau flatterig wäre: SignSession kennt nur
// Sekundenauflösung und keine Anmelde-Kennung, zwei Anmeldungen innerhalb
// derselben Sekunde liefern also ein IDENTISCHES Merkmal — dann sperrt das
// Abmelden von A zwangsläufig auch B aus, aber nur, wenn die Sekunde nicht
// zufällig übergesprungen ist.
func TestLogoutOneDeviceKeepsOtherDevice(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac5"
	e.seedUser(t, uid, "geheim123")

	deviceA := e.login(t, uid, "geheim123")
	deviceB := e.login(t, uid, "geheim123")

	fourSegments(t, "AC-5", "Merkmal Gerät A", deviceA)
	fourSegments(t, "AC-5", "Merkmal Gerät B", deviceB)
	if deviceA == deviceB {
		t.Errorf("AC-5: zwei Anmeldungen desselben Kontos müssen verschiedene Merkmale liefern, "+
			"beide sind %q", deviceA)
	}

	if code := e.post(t, "/api/auth/logout", deviceA, ""); code != http.StatusOK {
		t.Fatalf("AC-5: Abmelden erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, deviceA); code != http.StatusUnauthorized {
		t.Errorf("AC-5: Gerät A muss abgemeldet sein, bekommen %d", code)
	}
	if code := e.probe(t, deviceB); code != http.StatusOK {
		t.Errorf("AC-5: Gerät B muss angemeldet bleiben, bekommen %d", code)
	}
}

// --- AC-6 ------------------------------------------------------------------

// AC-6: "Auf allen Geräten abmelden" macht alle Anmeldungen ungültig, auch
// über einen echten Neustart hinweg.
func TestLogoutAllDevicesRevokesAcrossRestart(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac6"
	e.seedUser(t, uid, "geheim123")

	deviceA := e.login(t, uid, "geheim123")
	deviceB := e.login(t, uid, "geheim123")

	if code := e.post(t, "/api/auth/logout-all", deviceA, ""); code != http.StatusOK {
		t.Fatalf("AC-6: 'alle abmelden' erwartet 200, bekommen %d "+
			"(404 heißt: Route nicht registriert)", code)
	}

	if code := e.probe(t, deviceA); code != http.StatusUnauthorized {
		t.Errorf("AC-6: Gerät A muss abgemeldet sein, bekommen %d", code)
	}
	if code := e.probe(t, deviceB); code != http.StatusUnauthorized {
		t.Errorf("AC-6: Gerät B muss abgemeldet sein, bekommen %d", code)
	}
	if code := probeAfterRestart(t, e.dataDir, e.secret, deviceA); code != http.StatusUnauthorized {
		t.Errorf("AC-6: Gerät A muss nach dem Neustart abgemeldet bleiben, bekommen %d", code)
	}
	if code := probeAfterRestart(t, e.dataDir, e.secret, deviceB); code != http.StatusUnauthorized {
		t.Errorf("AC-6: Gerät B muss nach dem Neustart abgemeldet bleiben, bekommen %d", code)
	}
}

// --- AC-7 ------------------------------------------------------------------

// AC-7: Mandantentrennung — der Widerruf bei Nutzer 1 lässt Nutzer 2 unberührt.
// Zwei echte, getrennte Konten im selben Datenbestand.
func TestLogoutAllDevicesLeavesSecondUserUntouched(t *testing.T) {
	e := newAuthEnv(t)
	e.seedUser(t, "u-ac7-alice", "geheim123")
	e.seedUser(t, "u-ac7-bob", "geheim456")

	alice := e.login(t, "u-ac7-alice", "geheim123")
	bob := e.login(t, "u-ac7-bob", "geheim456")

	if code := e.post(t, "/api/auth/logout-all", alice, ""); code != http.StatusOK {
		t.Fatalf("AC-7: 'alle abmelden' erwartet 200, bekommen %d "+
			"(404 heißt: Route nicht registriert)", code)
	}

	if code := e.probe(t, alice); code != http.StatusUnauthorized {
		t.Errorf("AC-7: Nutzer 1 muss abgemeldet sein, bekommen %d", code)
	}
	if code := e.probe(t, bob); code != http.StatusOK {
		t.Errorf("AC-7: Nutzer 2 muss unberührt angemeldet bleiben, bekommen %d", code)
	}
}

// --- AC-8 ------------------------------------------------------------------

// AC-8: Der Passwortwechsel macht das zuvor gültige Merkmal ungültig.
func TestPasswordChangeRevokesSessions(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac8"
	e.seedUser(t, uid, "geheim123")
	cookie := e.login(t, uid, "geheim123")

	if code := e.probe(t, cookie); code != http.StatusOK {
		t.Fatalf("AC-8 Positivkontrolle: Merkmal muss vorher gültig sein, bekommen %d", code)
	}

	// Zweites Gerät: es muss den Passwortwechsel NICHT überleben.
	other := e.login(t, uid, "geheim123")

	resp := e.doResp(t, "PUT", "/api/auth/password", cookie,
		`{"old_password":"geheim123","new_password":"nochgeheimer1"}`)
	if resp.Code != http.StatusOK {
		t.Fatalf("AC-8: Passwortwechsel erwartet 200, bekommen %d: %s", resp.Code, resp.Body.String())
	}

	if code := e.probe(t, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-8: das zuvor gültige Merkmal muss ungültig sein, bekommen %d", code)
	}
	if code := e.probe(t, other); code != http.StatusUnauthorized {
		t.Errorf("AC-8: das andere Gerät muss abgemeldet sein, bekommen %d", code)
	}

	// Zweite Hälfte: das wechselnde Gerät darf NICHT ausgesperrt werden. Ohne
	// diese Zusicherung bewacht nichts, dass der Nutzer nach dem
	// Passwortwechsel weiterarbeiten kann — er säße vor einer Seite, deren
	// Datenabrufe alle 401 geben.
	fresh := sessionCookieOf(resp)
	if fresh == "" {
		t.Fatalf("AC-8: die Antwort des Passwortwechsels muss ein neues Anmelde-Merkmal tragen")
	}
	if fresh == cookie {
		t.Errorf("AC-8: das neue Merkmal muss sich vom widerrufenen unterscheiden")
	}
	fourSegments(t, "AC-8", "neu ausgestelltes Merkmal", fresh)
	if code := e.probe(t, fresh); code != http.StatusOK {
		t.Errorf("AC-8: das neu ausgestellte Merkmal muss sofort funktionieren, bekommen %d", code)
	}
}

// Abgrenzung zu AC-8: Passwort-Zurücksetzen, "auf allen Geräten abmelden" und
// Kontolöschung stellen KEIN neues Merkmal aus. Wer zurücksetzt, weil das
// Passwort abgegriffen wurde, soll ausgesperrt bleiben — ein frischer Nachweis
// in der Antwort würde genau den Angreifer wieder hereinlassen, der den
// Zurücksetzen-Ablauf ausgelöst hat.
func TestOnlyPasswordChangeIssuesAFreshSession(t *testing.T) {
	t.Run("Zurücksetzen", func(t *testing.T) {
		e := newAuthEnv(t)
		const uid = "u-nofresh-reset"
		e.seedUser(t, uid, "geheim123")
		e.login(t, uid, "geheim123")

		const resetToken = "reset-token-nofresh"
		hash, err := bcrypt.GenerateFromPassword([]byte(resetToken), bcrypt.MinCost)
		if err != nil {
			t.Fatalf("bcrypt: %v", err)
		}
		if err := e.store.SaveResetToken(uid, model.PasswordResetToken{
			TokenHash: string(hash), ExpiresAt: time.Now().Add(time.Hour),
		}); err != nil {
			t.Fatalf("SaveResetToken: %v", err)
		}

		resp := e.doResp(t, "POST", "/api/auth/reset-password", "",
			fmt.Sprintf(`{"username":%q,"token":%q,"new_password":"nochgeheimer1"}`, uid, resetToken))
		if resp.Code != http.StatusOK {
			t.Fatalf("Zurücksetzen erwartet 200, bekommen %d", resp.Code)
		}
		if fresh := sessionCookieOf(resp); fresh != "" {
			t.Errorf("Zurücksetzen darf kein neues Merkmal ausstellen, bekommen %q", fresh)
		}
	})

	t.Run("alle Geräte abmelden", func(t *testing.T) {
		e := newAuthEnv(t)
		const uid = "u-nofresh-all"
		e.seedUser(t, uid, "geheim123")
		cookie := e.login(t, uid, "geheim123")

		resp := e.doResp(t, "POST", "/api/auth/logout-all", cookie, "")
		if resp.Code != http.StatusOK {
			t.Fatalf("'alle abmelden' erwartet 200, bekommen %d", resp.Code)
		}
		if fresh := sessionCookieOf(resp); fresh != "" {
			t.Errorf("'alle abmelden' darf kein neues Merkmal ausstellen, bekommen %q", fresh)
		}
	})

	t.Run("Kontolöschung", func(t *testing.T) {
		e := newAuthEnv(t)
		const uid = "u-nofresh-delete"
		e.seedUser(t, uid, "geheim123")
		cookie := e.login(t, uid, "geheim123")

		resp := e.doResp(t, "DELETE", "/api/auth/account", cookie, "")
		if resp.Code != http.StatusOK {
			t.Fatalf("Kontolöschung erwartet 200, bekommen %d", resp.Code)
		}
		if fresh := sessionCookieOf(resp); fresh != "" {
			t.Errorf("Kontolöschung darf kein neues Merkmal ausstellen, bekommen %q", fresh)
		}
	})
}

// Abmelden mit einem ALT-Merkmal wirkt ebenfalls — die Zusage "Abmelden wirkt"
// bekommt auch im 24-Stunden-Übergangsfenster keine Ausnahme.
//
// Der gefährliche Fall ist der ohne jede authentifizierte Anfrage dazwischen:
// nur dann bleibt das Alt-Merkmal ungehoben, steht auf keiner Gästeliste und
// hätte ohne Widerrufs-Vermerk nichts, woran ein Abmelden greifen könnte.
func TestLogoutWithLegacyCookieRevokesIt(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-legacy-logout"
	e.seedUser(t, uid, "geheim123")

	legacy := authmw.SignSession(uid, e.secret)
	if n := len(strings.Split(legacy, ".")); n != 3 {
		t.Fatalf("Testaufbau: Alt-Merkmal muss 3 Segmente haben, hat %d", n)
	}

	// KEINE authentifizierte Anfrage vor dem Abmelden — sonst höbe die
	// Middleware das Merkmal aufs neue Format und der Fall verschwände.
	if code := e.post(t, "/api/auth/logout", legacy, ""); code != http.StatusOK {
		t.Fatalf("Abmelden erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, legacy); code != http.StatusUnauthorized {
		t.Errorf("Alt-Merkmal muss nach dem Abmelden ungültig sein, bekommen %d", code)
	}
}

// AC-16 im Altformat: ein Alt-Merkmal überlebt die Kontolöschung nicht.
//
// `e.login()` liefert immer das NEUE vierteilige Merkmal, der Legacy-Zweig
// wird vom regulären AC-16-Test also nie erreicht. Fiele die Konto-Prüfung
// dort weg, bliebe ein vor der Löschung ausgestelltes und nie gehobenes
// Alt-Merkmal bis zu 24 Stunden gültig — und die stille Hebung würde den
// gelöschten Nutzerordner sogar neu anlegen.
//
// Dass der Legacy-Zweig grundsätzlich durchlässt, belegt
// TestLegacyCookieWithoutLogoutStillWorks; deshalb misst dieser Test hier die
// Löschung und nicht die Grundfunktion.
func TestLegacyCookieDoesNotSurviveAccountDeletion(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-legacy-delete"
	e.seedUser(t, uid, "geheim123")

	// Alt-Merkmal VOR der Löschung ausstellen und bewusst NICHT benutzen —
	// jede authentifizierte Anfrage damit würde es aufs neue Format heben und
	// den zu prüfenden Fall wegnehmen.
	legacy := authmw.SignSession(uid, e.secret)
	if n := len(strings.Split(legacy, ".")); n != 3 {
		t.Fatalf("Testaufbau: Alt-Merkmal muss 3 Segmente haben, hat %d", n)
	}

	// Löschung über den echten Endpunkt, mit einem regulären neuen Merkmal.
	current := e.login(t, uid, "geheim123")
	if code := e.do(t, "DELETE", "/api/auth/account", current, ""); code != http.StatusOK {
		t.Fatalf("Kontolöschung erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, legacy); code != http.StatusUnauthorized {
		t.Errorf("Alt-Merkmal muss nach der Kontolöschung ungültig sein, bekommen %d", code)
	}
	// Gegenprobe zur Nebenwirkung: die stille Hebung ruft AddSession, und das
	// legt das Nutzerverzeichnis per MkdirAll an. Geprüft wird deshalb das
	// VERZEICHNIS, nicht UserExists — das schaut auf die user.json, die die
	// Hebung gar nicht schreibt, und sähe die Wiederauferstehung nicht.
	if _, err := os.Stat(e.store.UserDir(uid)); err == nil {
		t.Errorf("der Ordner des gelöschten Kontos %q darf durch das Alt-Merkmal nicht wieder entstehen", uid)
	}
}

// Positivkontrolle zum vorigen Test, in EIGENER Umgebung: ohne das Abmelden
// wäre dieselbe Anfrage 200. Ohne sie misst der Test nur, dass Alt-Merkmale
// generell abgewiesen werden — und wäre auch dann grün, wenn der
// Legacy-Zweig ganz kaputt wäre.
func TestLegacyCookieWithoutLogoutStillWorks(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-legacy-ok"
	e.seedUser(t, uid, "geheim123")

	legacy := authmw.SignSession(uid, e.secret)
	if code := e.probe(t, legacy); code != http.StatusOK {
		t.Errorf("Positivkontrolle: gültiges Alt-Merkmal ohne Abmelden muss 200 liefern, bekommen %d", code)
	}
}

// --- AC-9 ------------------------------------------------------------------

// AC-9: Das Zurücksetzen des Passworts macht das zuvor gültige Merkmal
// ungültig. Sicherheitlich der schwerere Fall: wer zurücksetzt, WEIL das
// Passwort abgegriffen wurde, muss den Angreifer damit hinauswerfen.
//
// Das Reset-Token wird direkt über den Store gesetzt — der "Passwort
// vergessen"-Mailweg wird bewusst nicht angefasst, der Test versendet nichts.
func TestPasswordResetRevokesSessions(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac9"
	e.seedUser(t, uid, "geheim123")
	cookie := e.login(t, uid, "geheim123")

	if code := e.probe(t, cookie); code != http.StatusOK {
		t.Fatalf("AC-9 Positivkontrolle: Merkmal muss vorher gültig sein, bekommen %d", code)
	}

	const resetToken = "reset-token-2129"
	hash, err := bcrypt.GenerateFromPassword([]byte(resetToken), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	if err := e.store.SaveResetToken(uid, model.PasswordResetToken{
		TokenHash: string(hash), ExpiresAt: time.Now().Add(time.Hour),
	}); err != nil {
		t.Fatalf("SaveResetToken: %v", err)
	}

	code := e.post(t, "/api/auth/reset-password", "",
		fmt.Sprintf(`{"username":%q,"token":%q,"new_password":"nochgeheimer1"}`, uid, resetToken))
	if code != http.StatusOK {
		t.Fatalf("AC-9: Zurücksetzen erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-9: altes Merkmal muss nach dem Zurücksetzen ungültig sein, bekommen %d", code)
	}
}

// --- AC-15 -----------------------------------------------------------------

// AC-15 (a): Zwei gleichzeitige Anmeldungen desselben Kontos verdrängen
// einander nicht.
func TestTwoParallelLoginsDoNotEvictEachOther(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac15a"
	e.seedUser(t, uid, "geheim123")

	var wg sync.WaitGroup
	cookies := make([]string, 2)
	errs := make([]error, 2)
	for i := range cookies {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			cookies[idx], errs[idx] = e.loginNoFatal(uid, "geheim123")
		}(i)
	}
	wg.Wait()
	for i, err := range errs {
		if err != nil {
			t.Fatalf("AC-15a: parallele Anmeldung %d fehlgeschlagen: %v", i+1, err)
		}
	}

	fourSegments(t, "AC-15a", "erstes Merkmal", cookies[0])
	fourSegments(t, "AC-15a", "zweites Merkmal", cookies[1])
	if cookies[0] == cookies[1] {
		t.Errorf("AC-15a: parallele Anmeldungen müssen verschiedene Merkmale liefern, beide sind %q",
			cookies[0])
	}
	for i, c := range cookies {
		if code := e.probe(t, c); code != http.StatusOK {
			t.Errorf("AC-15a: Merkmal %d muss nach beiden Anmeldungen gültig sein, bekommen %d", i+1, code)
		}
	}
}

// AC-15 (b): Ein Widerruf parallel zu einer Profiländerung desselben Nutzers
// geht nicht verloren.
//
// Unbedingt geprüft wird "der Widerruf hält" — das ist die Zusicherung, die
// der Wettlauf gefährdet, und sie FIELE, läge die Gästeliste in der user.json:
// ein gleichzeitiger Profil-Schreiber schreibt dort das ganze Nutzerobjekt
// zurück und würfe den Widerruf damit weg. Die Dateitrennung
// (sessions.json getrennt von user.json) ist deshalb kein Zierrat, sondern
// genau das, was dieser Test bewacht.
//
// Die Profiländerung wird nur dann auf Persistenz geprüft, wenn sie 200 bekam:
// gewinnt der Widerruf das Rennen, bekommt sie 401 und darf gar nichts
// gespeichert haben. Eine Erwartung "beides immer" wäre reihenfolgeabhängig
// und damit flatterig.
func TestLogoutAllConcurrentWithProfileUpdate(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac15b"
	e.seedUser(t, uid, "geheim123")

	const rounds = 5
	for round := 0; round < rounds; round++ {
		cookie := e.login(t, uid, "geheim123")
		wantName := fmt.Sprintf("Runde %d", round)

		var wg sync.WaitGroup
		var profileCode, revokeCode int
		wg.Add(2)
		go func() {
			defer wg.Done()
			profileCode = e.do(t, "PUT", "/api/auth/profile", cookie,
				fmt.Sprintf(`{"display_name":%q}`, wantName))
		}()
		go func() {
			defer wg.Done()
			revokeCode = e.post(t, "/api/auth/logout-all", cookie, "")
		}()
		wg.Wait()

		if revokeCode != http.StatusOK {
			t.Fatalf("AC-15b Runde %d: 'alle abmelden' erwartet 200, bekommen %d "+
				"(404 heißt: Route nicht registriert)", round, revokeCode)
		}
		if code := e.probe(t, cookie); code != http.StatusUnauthorized {
			t.Fatalf("AC-15b Runde %d: der Widerruf darf durch den gleichzeitigen Profil-Schreiber "+
				"nicht verloren gehen, bekommen %d", round, code)
		}
		if profileCode == http.StatusOK {
			user, err := e.store.LoadUser(uid)
			if err != nil || user == nil {
				t.Fatalf("AC-15b Runde %d: LoadUser: %v", round, err)
			}
			if user.DisplayName != wantName {
				t.Errorf("AC-15b Runde %d: angenommene Profiländerung muss gespeichert sein, "+
					"erwartet %q, gespeichert %q", round, wantName, user.DisplayName)
			}
		}
	}
}

// --- AC-16 -----------------------------------------------------------------

// AC-16: Die Kontolöschung macht das Merkmal ungültig — auch über einen echten
// Neustart hinweg.
func TestAccountDeletionRevokesSessionAcrossRestart(t *testing.T) {
	e := newAuthEnv(t)
	const uid = "u-ac16"
	e.seedUser(t, uid, "geheim123")
	cookie := e.login(t, uid, "geheim123")

	if code := e.probe(t, cookie); code != http.StatusOK {
		t.Fatalf("AC-16 Positivkontrolle: Merkmal muss vorher gültig sein, bekommen %d", code)
	}
	if code := e.do(t, "DELETE", "/api/auth/account", cookie, ""); code != http.StatusOK {
		t.Fatalf("AC-16: Kontolöschung erwartet 200, bekommen %d", code)
	}

	if code := e.probe(t, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-16: Merkmal muss sofort ungültig sein, bekommen %d", code)
	}
	if code := probeAfterRestart(t, e.dataDir, e.secret, cookie); code != http.StatusUnauthorized {
		t.Errorf("AC-16: Merkmal muss auch nach dem Neustart ungültig bleiben, bekommen %d", code)
	}
}
