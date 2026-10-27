package handler_test

// TDD RED — Issue #2304 (S1 aus #2271/#2146, Epic #2138): Resend-Endpoint für
// die E-Mail-Bestätigung.
// Spec: docs/specs/modules/email_verify_vorbereitung_2304.md — AC-7, AC-8.
//
// Externes Testpaket mit Absicht (Muster logout_revocation_test.go, #2129):
// die Route existiert noch nicht. Über den echten router.New adressiert bricht
// kein Symbolaufruf die Kompilierung — der Aufruf läuft heute in ein 404 und
// die Tests scheitern am VERHALTEN, nicht am Bau. Ein direkter Aufruf des noch
// fehlenden Handlers aus `package handler` hätte das gesamte Verzeichnis
// unkompilierbar gemacht und alle übrigen Nachweise mitgerissen.
//
// Gebaut wird der vollständig verdrahtete Produktions-Router inklusive
// AuthMiddleware und Rate-Limiter — damit misst der Test auch, dass die Route
// registriert und (als öffentlicher Endpunkt) exakt freigeschaltet ist.
//
// Kein Mock, kein Netz: echter Dateispeicher im Temp-Verzeichnis, echter
// Router, und der Mailversand wird an der BESTEHENDEN Naht
// `sendVerificationMailFn` (auth.go) beobachtet — über die Brücke
// handler.ObserveVerificationMailForTest. Der Empfänger und die fertig
// gerenderte Mail sind echt, nur der SMTP-Dial entfällt.

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/go-webauthn/webauthn/webauthn"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/handler"
	"github.com/henemm/gregor-api/internal/mail"
	authmw "github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/router"
	"github.com/henemm/gregor-api/internal/scheduler"
	"github.com/henemm/gregor-api/internal/store"
)

// resendPfad2304 ist der Resend-Endpoint aus der Spec (Implementation Details
// Punkt 3). Er ist öffentlich und braucht einen EXAKTEN Eintrag in der
// Public-Allowlist — der bestehende Eintrag `/api/auth/verify-email` ist ein
// exakter Pfadvergleich und deckt diesen Unterpfad NICHT mit ab.
const resendPfad2304 = "/api/auth/verify-email/resend"

// verifyPfad2304 ist der reguläre Einlöse-Endpunkt (Bestand).
const verifyPfad2304 = "/api/auth/verify-email"

// tokenAusMail zieht das 64-stellige Hex-Token aus dem Bestätigungslink der
// echten, gerenderten Mail (mail.BuildVerificationMail).
var tokenAusMail = regexp.MustCompile(`token=([0-9a-f]{64})`)

// verifyUmgebung2304 bündelt den echten Router mit seinem Datenbestand.
// Wird von dieser Datei UND von staging_verify_token_test.go benutzt.
type verifyUmgebung2304 struct {
	router http.Handler
	store  *store.Store
	secret string
}

// neueVerifyUmgebung2304 baut den ECHTEN Produktions-Router (dieselbe
// Deps-Verdrahtung wie cmd/server/main.go).
//
// Die Konfiguration wird bewusst explizit gesetzt statt aus der Umgebung
// übernommen: ohne gesetzten SMTPHost kehrt dispatchVerificationMail
// (auth.go:801-808) VOR der Goroutine um und die beobachtete Naht würde nie
// betreten — der Nachweis liefe ins Leere. Der Host trägt absichtlich kein
// "resend" im Namen (Resend-Default-Deny, mail/sender.go) und wird ohnehin nie
// gewählt, weil die Naht den Dial ersetzt.
func neueVerifyUmgebung2304(t *testing.T) *verifyUmgebung2304 {
	t.Helper()

	cfg, err := config.Load()
	if err != nil {
		t.Fatalf("config.Load: %v", err)
	}
	cfg.DataDir = t.TempDir()
	cfg.SessionSecret = "verify-2304-secret-32-zeichen-ok"
	cfg.PublicHost = "https://staging.gregor20.henemm.com"
	cfg.SMTPHost = "smtp.beispiel.invalid"
	cfg.SMTPPort = 587
	cfg.SMTPUser = "gz-test"
	cfg.SMTPPass = "geheim"
	cfg.SMTPFrom = "gregor_zwanzig@henemm.com"

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
		GitCommit:          "test-2304",
	})

	return &verifyUmgebung2304{router: r, store: s, secret: cfg.SessionSecret}
}

// konto2304 legt ein Konto an. Die Kennung darf weder "test" noch "tdd"
// enthalten (mail.IsTestUser) — sonst nimmt der Versand den Google-Zweig und
// die beobachtete Naht bliebe unberührt.
func (e *verifyUmgebung2304) konto2304(t *testing.T, uid, email, mailTo string, verifiziert *time.Time) {
	t.Helper()
	if err := e.store.SaveUser(model.User{
		ID:              uid,
		Email:           email,
		MailTo:          mailTo,
		DisplayName:     "Konto " + uid,
		EmailVerifiedAt: verifiziert,
		CreatedAt:       time.Now(),
	}); err != nil {
		t.Fatalf("Konto %q anlegen: %v", uid, err)
	}
	if err := e.store.ProvisionUserDirs(uid); err != nil {
		t.Fatalf("ProvisionUserDirs %q: %v", uid, err)
	}
}

// anmeldeCookie stellt ein gültiges Merkmal im NEUEN vierteiligen Format aus
// und trägt es auf die Gästeliste des Kontos — genau das, was die
// AuthMiddleware prüft.
func (e *verifyUmgebung2304) anmeldeCookie(t *testing.T, uid string) *http.Cookie {
	t.Helper()
	sid, err := authmw.NewSessionID()
	if err != nil {
		t.Fatalf("NewSessionID: %v", err)
	}
	if err := e.store.AddSession(uid, sid); err != nil {
		t.Fatalf("AddSession für %q: %v", uid, err)
	}
	return &http.Cookie{Name: "gz_session", Value: authmw.SignSessionWithID(uid, sid, e.secret)}
}

func (e *verifyUmgebung2304) post(t *testing.T, pfad, rumpf string, cookie *http.Cookie) *httptest.ResponseRecorder {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, pfad, strings.NewReader(rumpf))
	req.Header.Set("Content-Type", "application/json")
	if cookie != nil {
		req.AddCookie(cookie)
	}
	w := httptest.NewRecorder()
	e.router.ServeHTTP(w, req)
	return w
}

// beobachteteMail ist ein echter Aufruf der Versand-Naht.
type beobachteteMail struct {
	to  string
	msg mail.Mail
}

func beobachteVersand2304(t *testing.T) chan beobachteteMail {
	t.Helper()
	aufrufe := make(chan beobachteteMail, 8)
	wiederherstellen := handler.ObserveVerificationMailForTest(
		func(_ mail.MailConfig, to string, msg mail.Mail) error {
			aufrufe <- beobachteteMail{to: to, msg: msg}
			return nil
		})
	t.Cleanup(wiederherstellen)
	return aufrufe
}

// AC-7: Konto mit hinterlegter Kontaktadresse, kein gültiger Token → nach dem
// Resend-Aufruf existiert ein gültiger Token, die Antwort ist 200
// {"status":"ok"}, die Mail ging an die EFFEKTIVE Kontaktadresse, und das
// mitgeschickte Token wird vom regulären Verifikations-Endpunkt angenommen.
func TestResendErzeugtGueltigesTokenUndAntwortetOk_AC7(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	aufrufe := beobachteVersand2304(t)

	const uid = "rosa2304"
	const kontaktadresse = "rosa-empfang@beispiel.de"
	// mail_to hat Vorrang vor email — die abweichende email misst das mit.
	e.konto2304(t, uid, "rosa-alt@beispiel.de", kontaktadresse, nil)

	if vorher, err := e.store.LoadVerificationToken(uid); err == nil && vorher != nil {
		t.Fatalf("AC-7 Ausgangslage verletzt: es existiert bereits ein Token für %q", uid)
	}

	w := e.post(t, resendPfad2304, `{"username":"`+uid+`"}`, nil)

	if w.Code == http.StatusNotFound {
		t.Fatalf("AC-7: %s antwortet 404 — die Route ist im echten Router nicht registriert", resendPfad2304)
	}
	if w.Code == http.StatusUnauthorized {
		t.Fatalf("AC-7: %s antwortet 401 — der Endpunkt fehlt in der Public-Allowlist "+
			"(exakter Pfad nötig, der Eintrag %q deckt ihn nicht mit ab)", resendPfad2304, verifyPfad2304)
	}
	if w.Code != http.StatusOK {
		t.Fatalf("AC-7: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"status":"ok"}` {
		t.Errorf("AC-7: erwarteter Antwortkörper `{\"status\":\"ok\"}`, bekommen %q", got)
	}

	// Der Token entsteht in dispatchVerificationMail VOR der SMTP-Prüfung
	// (auth.go:787) — er ist deshalb ohne Mailweg prüfbar.
	tok, err := e.store.LoadVerificationToken(uid)
	if err != nil {
		t.Fatalf("AC-7: LoadVerificationToken: %v", err)
	}
	if tok == nil {
		t.Fatalf("AC-7: nach dem Resend-Aufruf muss ein Verifikations-Token für %q existieren — es gibt keinen", uid)
	}
	if !tok.ExpiresAt.After(time.Now()) {
		t.Errorf("AC-7: der erzeugte Token ist bereits abgelaufen (ExpiresAt %v)", tok.ExpiresAt)
	}

	var gesehen beobachteteMail
	select {
	case gesehen = <-aufrufe:
	case <-time.After(3 * time.Second):
		t.Fatalf("AC-7: binnen 3s kein Versand an der Naht beobachtet — der Resend-Endpunkt " +
			"hat dispatchVerificationMail nicht aufgerufen")
	}
	if gesehen.to != kontaktadresse {
		t.Errorf("AC-7: Mail muss an die effektive Kontaktadresse %q gehen, ging an %q",
			kontaktadresse, gesehen.to)
	}

	treffer := tokenAusMail.FindStringSubmatch(gesehen.msg.PlainBody)
	if treffer == nil {
		t.Fatalf("AC-7: kein Klartext-Token im Bestätigungslink der Mail gefunden:\n%s", gesehen.msg.PlainBody)
	}

	// Der mitgeschickte Token muss vom regulären Einlöse-Endpunkt angenommen
	// werden — erst das beweist "gültiger Verifikations-Token".
	wEinloesen := e.post(t, verifyPfad2304, `{"user":"`+uid+`","token":"`+treffer[1]+`"}`, nil)
	if wEinloesen.Code != http.StatusOK {
		t.Fatalf("AC-7: der per Resend verschickte Token wurde von %s NICHT angenommen (%d): %s",
			verifyPfad2304, wEinloesen.Code, wEinloesen.Body.String())
	}
	user, err := e.store.LoadUser(uid)
	if err != nil || user == nil {
		t.Fatalf("AC-7: Konto nach der Einlösung nicht ladbar: %v", err)
	}
	if user.EmailVerifiedAt == nil {
		t.Errorf("AC-7: nach erfolgreicher Einlösung muss email_verified_at gesetzt sein")
	}
}

// AC-8: unbekannte und bekannte Kennung liefern zeichengleiche Antworten
// (keine Konto-Enumeration).
//
// Positivkontrolle im selben Test: BEIDE Antworten müssen 200 sein, und die
// bekannte Kennung muss tatsächlich einen Token bekommen haben. Ohne diese
// zweite Hälfte wäre der Test auch grün, wenn der Endpunkt gar nicht
// existierte — zwei 404 sind ebenfalls zeichengleich.
func TestResendAntwortetEnumerationsfreiZeichengleich_AC8(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	aufrufe := beobachteVersand2304(t)

	const bekannt = "bruno2304"
	const unbekannt = "niemand2304"
	e.konto2304(t, bekannt, "bruno@beispiel.de", "bruno-empfang@beispiel.de", nil)

	wUnbekannt := e.post(t, resendPfad2304, `{"username":"`+unbekannt+`"}`, nil)
	wBekannt := e.post(t, resendPfad2304, `{"username":"`+bekannt+`"}`, nil)

	if wBekannt.Code != http.StatusOK || wUnbekannt.Code != http.StatusOK {
		t.Fatalf("AC-8: beide Aufrufe müssen 200 liefern (bekannt %d, unbekannt %d) — "+
			"zwei gleiche Fehlercodes wären zwar zeichengleich, aber kein Nachweis. "+
			"Antworten: bekannt=%q unbekannt=%q",
			wBekannt.Code, wUnbekannt.Code, wBekannt.Body.String(), wUnbekannt.Body.String())
	}
	if wBekannt.Code != wUnbekannt.Code {
		t.Errorf("AC-8: Statuscodes unterscheiden sich: bekannt %d, unbekannt %d",
			wBekannt.Code, wUnbekannt.Code)
	}
	if !bytes.Equal(wBekannt.Body.Bytes(), wUnbekannt.Body.Bytes()) {
		t.Errorf("AC-8: Antwortkörper sind nicht zeichengleich: bekannt %q, unbekannt %q",
			wBekannt.Body.String(), wUnbekannt.Body.String())
	}

	// Positivkontrolle: der bekannte Zweig hat wirklich gearbeitet.
	tok, err := e.store.LoadVerificationToken(bekannt)
	if err != nil || tok == nil {
		t.Fatalf("AC-8 Positivkontrolle: für die BEKANNTE Kennung %q muss ein Token entstanden sein "+
			"(sonst sind beide Antworten nur deshalb gleich, weil nichts geschah): %v", bekannt, err)
	}
	if tokUnbekannt, _ := e.store.LoadVerificationToken(unbekannt); tokUnbekannt != nil {
		t.Errorf("AC-8: für die unbekannte Kennung %q darf kein Token entstehen", unbekannt)
	}
	select {
	case gesehen := <-aufrufe:
		if gesehen.to != "bruno-empfang@beispiel.de" {
			t.Errorf("AC-8: Versand ging an %q statt an die Kontaktadresse des bekannten Kontos", gesehen.to)
		}
	case <-time.After(3 * time.Second):
		t.Errorf("AC-8 Positivkontrolle: binnen 3s kein Versand für die bekannte Kennung beobachtet")
	}
}

// F002 (Adversary-Befund, HIGH): der Resend-Endpunkt versendet laut Spec nur
// für ein EXISTIERENDES und UNBESTÄTIGTES Konto. Bewacht war das bisher nicht —
// die Bedingung ersatzlos zu streichen ließ alle Tests grün, weil beide
// bestehenden Resend-Tests nur unbestätigte Konten benutzen.
//
// Gemessen wird deterministisch am Token: dispatchVerificationMail stellt ihn
// SYNCHRON aus, bevor der Versand in die Goroutine geht. Für ein bestätigtes
// Konto darf keiner entstehen. Die Beobachtung der Versand-Naht kommt hinzu,
// aber nur mit Positivkontrolle im selben Test auf demselben Kanal — ohne die
// wäre "keine Mail gesehen" auch bei totem Beobachter wahr.
//
// Dritte Hälfte: die Antwort muss zeichengleich zu der eines unbestätigten
// Kontos sein. AC-8 vergleicht bekannt gegen unbekannt; dass auch der
// BESTÄTIGUNGSSTATUS nicht durchscheint, prüft erst dieser Test.
func TestResendSchweigtFuerBereitsBestaetigtesKonto_F002(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	aufrufe := beobachteVersand2304(t)

	const bestaetigtesKonto = "carla2304"
	const carlaAdresse = "carla-empfang@beispiel.de"
	const offenesKonto = "dora2304"
	const doraAdresse = "dora-empfang@beispiel.de"
	schonBestaetigt := time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)
	e.konto2304(t, bestaetigtesKonto, "carla@beispiel.de", carlaAdresse, &schonBestaetigt)
	e.konto2304(t, offenesKonto, "dora@beispiel.de", doraAdresse, nil)

	wBestaetigt := e.post(t, resendPfad2304, `{"username":"`+bestaetigtesKonto+`"}`, nil)
	if wBestaetigt.Code != http.StatusOK {
		t.Fatalf("F002: der Aufruf für ein bestätigtes Konto muss 200 liefern, bekommen %d: %s",
			wBestaetigt.Code, wBestaetigt.Body.String())
	}
	if tok, _ := e.store.LoadVerificationToken(bestaetigtesKonto); tok != nil {
		t.Errorf("F002: für das bereits bestätigte Konto %q ist ein Verifikations-Token entstanden "+
			"(ExpiresAt %v) — es darf gar kein Versand ausgelöst werden", bestaetigtesKonto, tok.ExpiresAt)
	}

	// Positivkontrolle auf demselben Weg: unbestätigtes Konto, gleicher Aufruf.
	wOffen := e.post(t, resendPfad2304, `{"username":"`+offenesKonto+`"}`, nil)
	if tok, err := e.store.LoadVerificationToken(offenesKonto); err != nil || tok == nil {
		t.Fatalf("F002 Positivkontrolle: für das UNBESTÄTIGTE Konto %q muss ein Token entstehen — "+
			"sonst misst der Nachweis oben nur einen toten Endpunkt: %v", offenesKonto, err)
	}
	if wOffen.Code != wBestaetigt.Code || !bytes.Equal(wOffen.Body.Bytes(), wBestaetigt.Body.Bytes()) {
		t.Errorf("F002: die Antwort verrät den Bestätigungsstatus — bestätigt: %d %q, unbestätigt: %d %q",
			wBestaetigt.Code, wBestaetigt.Body.String(), wOffen.Code, wOffen.Body.String())
	}

	frist := time.After(3 * time.Second)
	for gesehenOffen := false; !gesehenOffen; {
		select {
		case m := <-aufrufe:
			if m.to == carlaAdresse {
				t.Errorf("F002: an das bereits bestätigte Konto (%q) wurde eine Bestätigungsmail versandt", m.to)
			}
			gesehenOffen = m.to == doraAdresse
		case <-frist:
			t.Fatalf("F002 Positivkontrolle: binnen 3s kein Versand an %q beobachtet — "+
				"die Naht misst nichts, der Negativ-Nachweis oben wäre wertlos", doraAdresse)
		}
	}
}

// F003 (Adversary-Befund, MEDIUM): das Ratenlimit von 5 Aufrufen je Stunde und
// Absenderadresse stand nur im Code — auf 999999 erhöht fiel kein Test um.
//
// Isolation: router.New legt den Zähler JE ROUTER-INSTANZ an (router.go:70),
// und diese Umgebung baut einen eigenen. Das ist nötig, weil httptest allen
// Anfragen dieselbe Absenderadresse gibt — ein geteilter Router ließe den hier
// verbrauchten Zähler in andere Tests durchschlagen (besonders AC-8).
//
// Die Kennung ist bewusst unbekannt: der Zähler läuft im Middleware VOR dem
// Handler, aber der Handler tut dann nichts — kein Token, keine Mail, kein
// SMTP-Versuch.
func TestResendDrosseltAbDemSechstenAufrufProStunde_F003(t *testing.T) {
	e := neueVerifyUmgebung2304(t)
	const unbekannt = "niemandf0032304"
	const rumpf = `{"username":"` + unbekannt + `"}`

	for i := 1; i <= 5; i++ {
		w := e.post(t, resendPfad2304, rumpf, nil)
		if w.Code != http.StatusOK {
			t.Fatalf("F003: Aufruf %d von 5 muss noch durchgehen (Limit ist 5/Stunde), bekommen %d: %s",
				i, w.Code, w.Body.String())
		}
	}

	w := e.post(t, resendPfad2304, rumpf, nil)
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("F003: der 6. Aufruf binnen einer Stunde muss mit 429 gedrosselt werden, "+
			"bekommen %d: %s — das Ratenlimit auf %s greift nicht",
			w.Code, w.Body.String(), resendPfad2304)
	}
	if got := strings.TrimSpace(w.Body.String()); got != `{"error":"rate_limit_exceeded"}` {
		t.Errorf("F003: erwarteter Drossel-Körper `{\"error\":\"rate_limit_exceeded\"}`, bekommen %q", got)
	}
}
