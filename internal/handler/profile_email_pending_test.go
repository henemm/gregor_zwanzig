package handler

// TDD RED — Issue #2147 Scheibe B2 (#2311-Rest, Epic #2138): Adresswechsel
// wird erst nach Bestaetigung wirksam.
// Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md — hier AC-1,
// AC-4 (beide Varianten), AC-6, AC-7, AC-10, AC-18 (Bestandskonto + Export).
// AC-2/3/8/9/12 in verify_email_pending_address_test.go, AC-11 und der
// Staging-Token-Weg in resend_verification_pending_test.go.
//
// 🔴 Warum der neue Zustand ueber ROHES JSON gemessen wird: die Felder
// `PendingContactAddress`/`PendingContactField` (model.User) und `Address`
// (model.EmailVerificationToken) existieren vor /50 noch nicht. Ein direkter
// Feldzugriff haette das GANZE Paket unkompilierbar gemacht und damit jeden
// Regressionswaechter unmessbar. Verbindlicher JSON-Vertrag fuer /50:
//
//   user.json               pending_contact_address, pending_contact_field
//                           ("email"|"mail_to"), beide omitempty
//   email_verification.json zusaetzlich "address"
//   Profil-Antwort          pending_contact_address (nur wenn etwas aussteht),
//                           email_verified bleibt true
//   Verify-Antworten        400 {"error":"token expired"} (ersetztes Token),
//                           409 {"error":"address_taken"} (zwischenzeitlich vergeben)
//
// Gemessen wird am WIRKORT: echte Handler gegen echten store.Store auf
// t.TempDir(); der Mailversand an der bestehenden Naht sendVerificationMailFn
// (auth.go) mit echtem Empfaenger und echter, gerenderter Mail — nur der
// SMTP-Dial entfaellt. Kennungen enthalten weder "test" noch "tdd"
// (mail.IsTestUser), sonst naehme der Versand den Google-Zweig und die Naht
// bliebe unberuehrt.
//
// Helfer tragen das Praefix "ausstehend" (keine Kollision mit A/B1-Helfern).
// Wiederverwendet aus demselben Paket: newTestStore, speichereKonto,
// rohesKonto, eindeutigSecret, schreibpfadProfilAktualisieren,
// schreibpfadFehlerCode, schreibpfadRegistrieren, exportRootStore,
// exportRequest, exportUnzip, exportNamen.

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Hilfen -------------------------------------------------------------------

const ausstehendPasswort = "ausstehend-geheim-lang-1"

// ausstehendAltBestaetigt ist ein fester, deutlich in der Vergangenheit
// liegender Bestaetigungszeitpunkt: "unveraendert" und "neu gestempelt" sind
// damit am Wert unterscheidbar.
var ausstehendAltBestaetigt = time.Date(2026, 1, 2, 3, 4, 5, 0, time.UTC)

// ausstehendTokenAusMail zieht das Klartext-Token aus dem Bestaetigungslink.
var ausstehendTokenAusMail = regexp.MustCompile(`token=([0-9a-f]{64})`)

// ausstehendCfg: SMTPHost gesetzt, sonst kehrt dispatchVerificationMail vor
// der Goroutine um und die Naht wuerde nie betreten. Kein "resend" im Namen.
func ausstehendCfg() config.Config {
	return config.Config{
		PublicHost:    "https://gregor20.henemm.com",
		SMTPHost:      "smtp.beispiel.invalid",
		SMTPPort:      587,
		SMTPUser:      "u",
		SMTPPass:      "p",
		SessionSecret: eindeutigSecret,
	}
}

type ausstehendMail struct {
	to  string
	msg mail.Mail
}

// ausstehendBeobachteVersand ersetzt die Versand-Naht fuer die Testdauer.
func ausstehendBeobachteVersand(t *testing.T) chan ausstehendMail {
	t.Helper()
	ch := make(chan ausstehendMail, 32)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, msg mail.Mail) error {
		ch <- ausstehendMail{to: to, msg: msg}
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return ch
}

// ausstehendWarteAufMail liefert die naechste Mail an `an`. Mails an andere
// Adressen werden gesammelt zurueckgegeben (fuer Negativ-Nachweise).
func ausstehendWarteAufMail(t *testing.T, ch chan ausstehendMail, an string) (ausstehendMail, []ausstehendMail) {
	t.Helper()
	var andere []ausstehendMail
	frist := time.After(3 * time.Second)
	for {
		select {
		case m := <-ch:
			if m.to == an {
				return m, andere
			}
			andere = append(andere, m)
		case <-frist:
			t.Fatalf("binnen 3s keine Bestaetigungsmail an %q an der Versand-Naht beobachtet (andere: %v)",
				an, ausstehendEmpfaenger(andere))
			return ausstehendMail{}, andere
		}
	}
}

func ausstehendEmpfaenger(ms []ausstehendMail) []string {
	out := make([]string, 0, len(ms))
	for _, m := range ms {
		out = append(out, m.to)
	}
	return out
}

// ausstehendToken zieht das Klartext-Token aus einer beobachteten Mail.
func ausstehendToken(t *testing.T, m ausstehendMail) string {
	t.Helper()
	treffer := ausstehendTokenAusMail.FindStringSubmatch(m.msg.PlainBody)
	if treffer == nil {
		t.Fatalf("kein Klartext-Token im Bestaetigungslink der Mail an %q:\n%s", m.to, m.msg.PlainBody)
	}
	return treffer[1]
}

// ausstehendKeineWeitereMail wartet kurz und meldet jede weitere Mail an eine
// der genannten Adressen ("genau EINE Mail").
func ausstehendKeineWeitereMail(t *testing.T, ch chan ausstehendMail, ac string, adressen ...string) {
	t.Helper()
	frist := time.After(250 * time.Millisecond)
	for {
		select {
		case m := <-ch:
			for _, a := range adressen {
				if m.to == a {
					t.Errorf("%s: zusaetzliche Bestaetigungsmail an %q beobachtet — erwartet genau eine bzw. keine", ac, m.to)
				}
			}
		case <-frist:
			return
		}
	}
}

var ausstehendKontrollZaehler int32

// ausstehendKeinVersandAn beweist "keine Mail an verboten" MIT
// Positivkontrolle auf demselben Kanal (F002-Muster aus verify_resend_test.go):
// ein frisches, unbestaetigtes Kontrollkonto aendert seine Adresse; bis dessen
// Mail ankommt, darf keine Mail an eine verbotene Adresse erschienen sein.
// Ohne die Kontrolle waere "keine Mail gesehen" auch bei totem Beobachter wahr.
func ausstehendKeinVersandAn(t *testing.T, s *store.Store, cfg config.Config, ch chan ausstehendMail, ac string, verboten ...string) {
	t.Helper()
	n := atomic.AddInt32(&ausstehendKontrollZaehler, 1)
	uid := fmt.Sprintf("kontrolle-%d-b2", n)
	neu := fmt.Sprintf("kontrolle-%d-neu-b2@beispiel.de", n)
	speichereKonto(t, s, model.User{ID: uid, Email: fmt.Sprintf("kontrolle-%d-alt-b2@beispiel.de", n)})
	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("%s Positivkontrolle: Kontrollkonto-Update erwartet 200, bekommen %d: %s", ac, w.Code, w.Body.String())
	}
	_, andere := ausstehendWarteAufMail(t, ch, neu)
	for _, m := range andere {
		for _, v := range verboten {
			if m.to == v {
				t.Errorf("%s: an %q wurde eine Bestaetigungsmail versandt — erwartet keine", ac, m.to)
			}
		}
	}
}

// ausstehendKontoMap liest user.json roh als Map (JSON-Vertrag, siehe Kopf).
func ausstehendKontoMap(t *testing.T, s *store.Store, uid string) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(rohesKonto(t, s, uid), &m); err != nil {
		t.Fatalf("user.json von %q ist kein gueltiges JSON: %v", uid, err)
	}
	return m
}

// ausstehendTokenMap liest email_verification.json roh; ok=false wenn es
// keine gibt.
func ausstehendTokenMap(t *testing.T, s *store.Store, uid string) (map[string]any, bool) {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.UserDir(uid), "email_verification.json"))
	if os.IsNotExist(err) {
		return nil, false
	}
	if err != nil {
		t.Fatalf("email_verification.json von %q lesen: %v", uid, err)
	}
	var m map[string]any
	if err := json.Unmarshal(b, &m); err != nil {
		t.Fatalf("email_verification.json von %q ist kein gueltiges JSON: %v", uid, err)
	}
	return m, true
}

func ausstehendStr(m map[string]any, k string) string {
	v, _ := m[k].(string)
	return v
}

func ausstehendAntwortMap(t *testing.T, w *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("Antwort ist kein JSON-Objekt (%d): %q", w.Code, w.Body.String())
	}
	return m
}

// ausstehendKeinePendingFelder meldet jedes vorhandene Pending-Feld.
func ausstehendKeinePendingFelder(t *testing.T, ac string, m map[string]any) {
	t.Helper()
	for _, k := range []string{"pending_contact_address", "pending_contact_field"} {
		if v, da := m[k]; da {
			t.Errorf("%s: Feld %q darf nicht vorhanden sein (keine ausstehende Aenderung), ist %v", ac, k, v)
		}
	}
}

// ausstehendBestaetigtesKonto legt ein bestaetigtes, per Passwort anmeldbares
// Konto an.
func ausstehendBestaetigtesKonto(t *testing.T, s *store.Store, uid, email, mailTo string) {
	t.Helper()
	hash, err := bcrypt.GenerateFromPassword([]byte(ausstehendPasswort), bcrypt.MinCost)
	if err != nil {
		t.Fatalf("bcrypt: %v", err)
	}
	bestaetigt := ausstehendAltBestaetigt
	speichereKonto(t, s, model.User{
		ID: uid, Email: email, MailTo: mailTo, DisplayName: "Konto " + uid,
		PasswordHash: string(hash), EmailVerifiedAt: &bestaetigt,
	})
}

func ausstehendLogin(s *store.Store, uid string) *httptest.ResponseRecorder {
	body := fmt.Sprintf(`{"username":%q,"password":%q}`, uid, ausstehendPasswort)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	LoginHandler(s, eindeutigSecret).ServeHTTP(w, req)
	return w
}

func ausstehendProfilLesen(s *store.Store, uid string) *httptest.ResponseRecorder {
	req := withUserCtx(httptest.NewRequest(http.MethodGet, "/api/auth/profile", nil), uid)
	w := httptest.NewRecorder()
	GetProfileHandler(s).ServeHTTP(w, req)
	return w
}

func ausstehendEinloesen(s *store.Store, uid, token string) *httptest.ResponseRecorder {
	body := fmt.Sprintf(`{"user":%q,"token":%q}`, uid, token)
	req := httptest.NewRequest(http.MethodPost, "/api/auth/verify-email", strings.NewReader(body))
	w := httptest.NewRecorder()
	VerifyEmailHandler(s).ServeHTTP(w, req)
	return w
}

// ausstehendZeitstempel parst email_verified_at aus der rohen Map.
func ausstehendZeitstempel(t *testing.T, ac string, m map[string]any) *time.Time {
	t.Helper()
	roh := ausstehendStr(m, "email_verified_at")
	if roh == "" {
		return nil
	}
	ts, err := time.Parse(time.RFC3339Nano, roh)
	if err != nil {
		t.Fatalf("%s: email_verified_at %q nicht parsebar: %v", ac, roh, err)
	}
	return &ts
}

// --- AC-1 ---------------------------------------------------------------------

// AC-1: bestaetigtes Konto aendert mail_to auf eine freie neue Adresse ->
// alte Adresse bleibt wirksam und bestaetigt (email/mail_to/email_verified_at
// byteidentisch), Pending-Felder tragen die neue Adresse, genau EINE
// Bestaetigungsmail an die NEUE Adresse, Login weiter moeglich (kein 403),
// Profil-Antwort (PUT und GET) zeigt die neue Adresse nur als ausstehend.
//
// Passwort-Reset/Trip-Briefing: beide leiten ihr Ziel aus mail_to (ersatzweise
// email) ab (ForgotPasswordHandler auth.go, Python-Versand) und haben keine
// Test-Naht — ihr Ziel ist hier ueber die byteidentischen Felder gemessen.
func TestAC1_BestaetigtesKontoAdresswechselBleibtAusstehend(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "wechsel-ac1-b2"
	const email = "wechsel-ac1-email-b2@beispiel.de"
	const alt = "wechsel-ac1-alt-b2@beispiel.de"
	const neu = "wechsel-ac1-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, alt)
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-1: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	// Antwort des PUT
	antwort := ausstehendAntwortMap(t, w)
	if got := ausstehendStr(antwort, "pending_contact_address"); got != neu {
		t.Errorf("AC-1: PUT-Antwort muss pending_contact_address=%q tragen, ist %q", neu, got)
	}
	if got := ausstehendStr(antwort, "mail_to"); got != alt {
		t.Errorf("AC-1: PUT-Antwort muss die ALTE mail_to %q als aktiv zeigen, zeigt %q", alt, got)
	}
	if v, _ := antwort["email_verified"].(bool); !v {
		t.Errorf("AC-1: PUT-Antwort muss email_verified=true behalten, ist %v", antwort["email_verified"])
	}

	// Gespeicherter Zustand
	nachher := ausstehendKontoMap(t, s, uid)
	for _, k := range []string{"email", "mail_to", "email_verified_at"} {
		if !reflect.DeepEqual(vorher[k], nachher[k]) {
			t.Errorf("AC-1: %s muss byteidentisch bleiben — vorher %v, nachher %v", k, vorher[k], nachher[k])
		}
	}
	if got := ausstehendStr(nachher, "pending_contact_address"); got != neu {
		t.Errorf("AC-1: user.json muss pending_contact_address=%q tragen, ist %q", neu, got)
	}
	if got := ausstehendStr(nachher, "pending_contact_field"); got != "mail_to" {
		t.Errorf("AC-1: user.json muss pending_contact_field=\"mail_to\" tragen, ist %q", got)
	}
	if tok, da := ausstehendTokenMap(t, s, uid); !da {
		t.Errorf("AC-1: es muss ein Bestaetigungs-Token entstanden sein")
	} else if got := ausstehendStr(tok, "address"); got != neu {
		t.Errorf("AC-1: das Token muss an die neue Adresse gebunden sein (address=%q), ist %q", neu, got)
	}

	// Mail: genau eine an die NEUE Adresse, keine an die alte/email
	_, andere := ausstehendWarteAufMail(t, versand, neu)
	for _, m := range andere {
		if m.to == alt || m.to == email {
			t.Errorf("AC-1: Bestaetigungsmail ging an die bisherige Adresse %q", m.to)
		}
	}
	ausstehendKeineWeitereMail(t, versand, "AC-1", neu, alt, email)

	// Login bleibt moeglich (kein 403 email_not_verified)
	if lw := ausstehendLogin(s, uid); lw.Code != http.StatusOK {
		t.Errorf("AC-1: Anmeldung muss waehrend der ausstehenden Aenderung moeglich bleiben, bekommen %d: %s",
			lw.Code, lw.Body.String())
	}

	// GET-Profil
	gw := ausstehendProfilLesen(s, uid)
	if gw.Code != http.StatusOK {
		t.Fatalf("AC-1: GET-Profil erwartet 200, bekommen %d", gw.Code)
	}
	profil := ausstehendAntwortMap(t, gw)
	if got := ausstehendStr(profil, "pending_contact_address"); got != neu {
		t.Errorf("AC-1: GET-Profil muss pending_contact_address=%q tragen, ist %q", neu, got)
	}
	if got := ausstehendStr(profil, "mail_to"); got != alt {
		t.Errorf("AC-1: GET-Profil muss mail_to=%q (alt) zeigen, zeigt %q", alt, got)
	}
	if v, _ := profil["email_verified"].(bool); !v {
		t.Errorf("AC-1: GET-Profil muss email_verified=true zeigen")
	}
}

// AC-1, Randfall (Adversary F001/M15): bestaetigtes Konto, mail_to LEER, email
// ist also die wirksame Adresse. Ein PUT setzt gleichzeitig eine neue email UND
// eine neue mail_to. Die neue mail_to wartet als Pending auf Bestaetigung; die
// neue email darf NICHT sofort geschrieben werden — sonst waere sie (mail_to
// bleibt in der Persistenz leer) ungeprueft die wirksame Adresse. Gemessen am
// Wirkort: gespeichertes user.json, Adresszuordnung des Stores, Versand-Naht.
func TestAC1_EmailWirksamGleichzeitigerMailToWechselUebernimmtEmailNicht(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "wechsel-ac1rand-b2"
	const alt = "wechsel-ac1rand-alt-b2@beispiel.de"
	const neuEmail = "wechsel-ac1rand-neuemail-b2@beispiel.de"
	const neuMailTo = "wechsel-ac1rand-neumailto-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, alt, "")
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid,
		fmt.Sprintf(`{"email":%q,"mail_to":%q}`, neuEmail, neuMailTo))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-1-Rand: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}

	// Gespeicherter Zustand
	nachher := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(nachher, "email"); got != alt {
		t.Errorf("AC-1-Rand: email muss unveraendert %q bleiben (unbestaetigte neue email darf nicht wirksam werden), ist %q", alt, got)
	}
	if got := ausstehendStr(nachher, "mail_to"); got != "" {
		t.Errorf("AC-1-Rand: mail_to muss leer bleiben, ist %q", got)
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], nachher["email_verified_at"]) {
		t.Errorf("AC-1-Rand: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], nachher["email_verified_at"])
	}
	if got := ausstehendStr(nachher, "pending_contact_address"); got != neuMailTo {
		t.Errorf("AC-1-Rand: pending_contact_address muss %q sein, ist %q", neuMailTo, got)
	}
	if got := ausstehendStr(nachher, "pending_contact_field"); got != "mail_to" {
		t.Errorf("AC-1-Rand: pending_contact_field muss \"mail_to\" sein, ist %q", got)
	}

	// Wirksame Adresse bleibt die alte
	ownerID := func(u *model.User) string {
		if u == nil {
			return "<keins>"
		}
		return u.ID
	}
	if owner, res, err := s.ResolveAddressOwner(alt); err != nil || res != store.AddressOwned || owner == nil || owner.ID != uid {
		t.Errorf("AC-1-Rand: alte Adresse %q muss weiter dem Konto %q gehoeren, bekommen owner=%s res=%v err=%v",
			alt, uid, ownerID(owner), res, err)
	}
	if owner, res, err := s.ResolveAddressOwner(neuEmail); err != nil || (owner != nil && owner.ID == uid) {
		t.Errorf("AC-1-Rand: neue, unbestaetigte email %q darf dem Konto nicht zugeordnet werden, bekommen owner=%s res=%v err=%v",
			neuEmail, ownerID(owner), res, err)
	}

	// Mail: genau eine an die neue mail_to, keine an alt/neue email
	_, andere := ausstehendWarteAufMail(t, versand, neuMailTo)
	for _, m := range andere {
		if m.to == alt || m.to == neuEmail {
			t.Errorf("AC-1-Rand: Bestaetigungsmail ging an %q statt nur an die neue mail_to", m.to)
		}
	}
	ausstehendKeineWeitereMail(t, versand, "AC-1-Rand", neuMailTo, alt, neuEmail)
}

// --- AC-4 ---------------------------------------------------------------------

// AC-4a: bestaetigtes Konto, mail_to=a, email=b; mail_to leeren -> mail_to
// bleibt vorerst a, Pending zeigt auf b (Feld mail_to), Mail an b; erst nach
// Einloesen ist mail_to leer, email=b wirksam, neu gestempelt.
func TestAC4_MailToLeerenMitAbweichenderEmailWirdErstNachBestaetigungWirksam(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "leeren-ac4a-b2"
	const a = "leeren-ac4a-mailto-b2@beispiel.de"
	const b = "leeren-ac4a-email-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, b, a)
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, `{"mail_to":""}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4a: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	zwischen := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(zwischen, "mail_to"); got != a {
		t.Errorf("AC-4a: mail_to muss bis zur Bestaetigung auf %q stehen bleiben, ist %q", a, got)
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], zwischen["email_verified_at"]) {
		t.Errorf("AC-4a: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], zwischen["email_verified_at"])
	}
	if got := ausstehendStr(zwischen, "pending_contact_address"); got != b {
		t.Errorf("AC-4a: pending_contact_address muss den email-Wert %q tragen, ist %q", b, got)
	}
	if got := ausstehendStr(zwischen, "pending_contact_field"); got != "mail_to" {
		t.Errorf("AC-4a: pending_contact_field muss \"mail_to\" sein, ist %q", got)
	}

	m, _ := ausstehendWarteAufMail(t, versand, b)
	token := ausstehendToken(t, m)

	ew := ausstehendEinloesen(s, uid, token)
	if ew.Code != http.StatusOK {
		t.Fatalf("AC-4a: Einloesen erwartet 200, bekommen %d: %s", ew.Code, ew.Body.String())
	}
	danach := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(danach, "mail_to"); got != "" {
		t.Errorf("AC-4a: nach dem Einloesen muss mail_to leer sein, ist %q", got)
	}
	if got := ausstehendStr(danach, "email"); got != b {
		t.Errorf("AC-4a: email muss %q bleiben, ist %q", b, got)
	}
	ts := ausstehendZeitstempel(t, "AC-4a", danach)
	if ts == nil || !ts.After(ausstehendAltBestaetigt) {
		t.Errorf("AC-4a: email_verified_at muss nach dem Einloesen neu gestempelt sein, ist %v", ts)
	}
	ausstehendKeinePendingFelder(t, "AC-4a (nach Einloesen)", danach)
}

// AC-4b: bestaetigtes Konto, email == mail_to == a; mail_to leeren -> sofort
// geleert, kein Reset, kein Pending, kein Token, keine Mail.
func TestAC4_MailToLeerenBeiGleicherEmailWirktSofort(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "leeren-ac4b-b2"
	const a = "leeren-ac4b-gleich-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, a, a)
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, `{"mail_to":""}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-4b: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(nachher, "mail_to"); got != "" {
		t.Errorf("AC-4b: mail_to muss sofort leer sein, ist %q", got)
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], nachher["email_verified_at"]) {
		t.Errorf("AC-4b: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], nachher["email_verified_at"])
	}
	ausstehendKeinePendingFelder(t, "AC-4b", nachher)
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("AC-4b: es darf kein Bestaetigungs-Token entstehen")
	}
	ausstehendKeinVersandAn(t, s, cfg, versand, "AC-4b", a)
}

// --- AC-6 ---------------------------------------------------------------------

// AC-6: bestaetigtes Konto, mail_to=a wirksam; email (inaktives Feld) aendern
// -> sofort gespeichert, kein Pending, kein Reset, kein Token, keine Mail.
func TestAC6_AenderungDesInaktivenFeldsWirktSofortOhneBestaetigung(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "nebenfeld-ac6-b2"
	const a = "nebenfeld-ac6-mailto-b2@beispiel.de"
	const b = "nebenfeld-ac6-email-alt-b2@beispiel.de"
	const c = "nebenfeld-ac6-email-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, b, a)
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"email":%q}`, c))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-6: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(nachher, "email"); got != c {
		t.Errorf("AC-6: email muss sofort %q sein, ist %q", c, got)
	}
	if got := ausstehendStr(nachher, "mail_to"); got != a {
		t.Errorf("AC-6: mail_to muss %q bleiben, ist %q", a, got)
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], nachher["email_verified_at"]) {
		t.Errorf("AC-6: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], nachher["email_verified_at"])
	}
	ausstehendKeinePendingFelder(t, "AC-6", nachher)
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("AC-6: es darf kein Bestaetigungs-Token entstehen (kein Versandversuch)")
	}
	ausstehendKeinVersandAn(t, s, cfg, versand, "AC-6", a, b, c)
}

// --- AC-7 ---------------------------------------------------------------------

// AC-7 — Regressionswächter B2: heute grün.
// Unbestaetigtes Konto aendert mail_to -> sofort wirksam, kein Pending, Mail
// an die neue Adresse.
func TestAC7_UnbestaetigtesKontoAdresswechselWirktSofort(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "offen-ac7-b2"
	const alt = "offen-ac7-alt-b2@beispiel.de"
	const neu = "offen-ac7-neu-b2@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: "offen-ac7-email-b2@beispiel.de", MailTo: alt})

	w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu))
	if w.Code != http.StatusOK {
		t.Fatalf("AC-7: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	if got := ausstehendStr(nachher, "mail_to"); got != neu {
		t.Errorf("AC-7: mail_to muss sofort %q sein, ist %q", neu, got)
	}
	if _, da := nachher["email_verified_at"]; da {
		t.Errorf("AC-7: das Konto darf nicht bestaetigt sein")
	}
	ausstehendKeinePendingFelder(t, "AC-7", nachher)
	ausstehendWarteAufMail(t, versand, neu)
	ausstehendKeineWeitereMail(t, versand, "AC-7", neu, alt)
}

// --- AC-10 --------------------------------------------------------------------

// AC-10 — Regressionswächter B2: heute grün.
// Zwei Nutzer: B haelt x (unbestaetigt, nur in email). A (bestaetigt) will
// mail_to auf x -> 409 email_taken, KEIN Pending, KEIN Token, beide Konten
// byteidentisch.
func TestAC10_BelegteAdresseErzeugtKeineAusstehendeAenderung(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	const uidA = "konto-a-ac10-b2"
	const uidB = "konto-b-ac10-b2"
	const x = "belegt-ac10-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uidA, "konto-a-ac10-email-b2@beispiel.de", "konto-a-ac10-alt-b2@beispiel.de")
	speichereKonto(t, s, model.User{ID: uidB, Email: x})
	vorherA := rohesKonto(t, s, uidA)
	vorherB := rohesKonto(t, s, uidB)

	w := schreibpfadProfilAktualisieren(s, cfg, uidA, fmt.Sprintf(`{"mail_to":%q}`, x))
	if w.Code != http.StatusConflict || schreibpfadFehlerCode(w) != "email_taken" {
		t.Fatalf("AC-10: erwartet 409 email_taken, bekommen %d: %s", w.Code, w.Body.String())
	}
	if string(vorherA) != string(rohesKonto(t, s, uidA)) {
		t.Errorf("AC-10: user.json von A muss byteidentisch bleiben (kein Pending-Feld)")
	}
	ausstehendKeinePendingFelder(t, "AC-10", ausstehendKontoMap(t, s, uidA))
	if _, da := ausstehendTokenMap(t, s, uidA); da {
		t.Errorf("AC-10: fuer A darf kein Token entstehen")
	}
	if string(vorherB) != string(rohesKonto(t, s, uidB)) {
		t.Errorf("AC-10: user.json von B muss byteidentisch bleiben")
	}
}

// --- AC-18 --------------------------------------------------------------------

// AC-18 (Bestandskonto) — Regressionswächter B2: heute grün.
// Ein vor B2 angelegtes Konto (rohe user.json ohne Pending-Felder) laedt und
// speichert unveraendert: Profil-Update nur display_name -> 200, user.json
// ist bis auf display_name wertgleich, keine Pending-Felder, GET-Profil ohne
// pending_contact_address.
func TestAC18_BestandskontoOhnePendingFelderVerhaeltSichUnveraendert(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	const uid = "bestand-ac18-b2"
	dir := s.UserDir(uid)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	roh := `{"id":"bestand-ac18-b2","email":"bestand-ac18-b2@beispiel.de","created_at":"2026-03-01T10:00:00Z",` +
		`"mail_to":"bestand-ac18-mt-b2@beispiel.de","sms_to":"+430000000","display_name":"Alt",` +
		`"tier":"pro","email_verified_at":"2026-03-02T10:00:00Z"}`
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte(roh), 0o644); err != nil {
		t.Fatal(err)
	}
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, `{"display_name":"Neu"}`)
	if w.Code != http.StatusOK {
		t.Fatalf("AC-18: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	erwartet := map[string]any{}
	for k, v := range vorher {
		erwartet[k] = v
	}
	erwartet["display_name"] = "Neu"
	if !reflect.DeepEqual(erwartet, nachher) {
		t.Errorf("AC-18: user.json muss bis auf display_name unveraendert sein\nerwartet: %v\nbekommen: %v", erwartet, nachher)
	}
	ausstehendKeinePendingFelder(t, "AC-18", nachher)
	if _, da := ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid))["pending_contact_address"]; da {
		t.Errorf("AC-18: GET-Profil eines Kontos ohne ausstehende Aenderung darf pending_contact_address nicht tragen")
	}
}

// AC-18 (Export): der DSGVO-Export eines Kontos MIT ausstehender Aenderung
// enthaelt die Pending-Felder in user.json; email_verification.json (Token-
// Hash) steht nie im Archiv — Positivkontrolle: sie liegt auf der Platte.
func TestAC18_ExportEnthaeltPendingFelderAberNieDasToken(t *testing.T) {
	root := exportRootStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "export-ac18-b2"
	const neu = "export-ac18-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, root, uid, "export-ac18-email-b2@beispiel.de", "export-ac18-alt-b2@beispiel.de")
	if err := root.ProvisionUserDirs(uid); err != nil {
		t.Fatal(err)
	}

	if w := schreibpfadProfilAktualisieren(root, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("AC-18 Export: Profil-Update erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	ausstehendWarteAufMail(t, versand, neu)
	if _, da := ausstehendTokenMap(t, root, uid); !da {
		t.Fatalf("AC-18 Export Positivkontrolle: email_verification.json muss auf der Platte liegen, " +
			"sonst beweist ihr Fehlen im Archiv nichts")
	}

	archiv := exportUnzip(t, exportRequest(t, root, uid, ""))
	for name := range archiv {
		if strings.HasSuffix(name, "email_verification.json") {
			t.Errorf("AC-18 Export: das Bestaetigungs-Token %q darf nie im Archiv stehen", name)
		}
	}
	rohJSON, ok := archiv["user.json"]
	if !ok {
		t.Fatalf("AC-18 Export: user.json fehlt im Archiv — Eintraege: %v", exportNamen(archiv))
	}
	var felder map[string]any
	if err := json.Unmarshal([]byte(rohJSON), &felder); err != nil {
		t.Fatalf("AC-18 Export: exportierte user.json ist kein JSON: %v", err)
	}
	if got := ausstehendStr(felder, "pending_contact_address"); got != neu {
		t.Errorf("AC-18 Export: exportierte user.json muss pending_contact_address=%q enthalten, ist %q", neu, got)
	}
	if got := ausstehendStr(felder, "pending_contact_field"); got != "mail_to" {
		t.Errorf("AC-18 Export: exportierte user.json muss pending_contact_field=\"mail_to\" enthalten, ist %q", got)
	}
}

// --- Fix-Loop 2: F005 / F006 (Adversary Runde 4) ------------------------------

// F005 (M20): bestaetigtes Konto leert email UND mail_to in einem Aufruf ->
// es gibt keine Adresse zu beweisen: beide Felder sofort leer, kein Pending,
// email_verified_at unveraendert, kein Token, keine Mail (Sofort-Zweig
// `newEffective == ""`, auth.go UpdateProfileHandler).
func TestF005_BestaetigtesKontoLeertBeideAdressfelderSofortOhnePending(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "leeren-f005-b2"
	const email = "leeren-f005-email-b2@beispiel.de"
	const mt = "leeren-f005-mt-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, mt)
	vorher := ausstehendKontoMap(t, s, uid)

	w := schreibpfadProfilAktualisieren(s, cfg, uid, `{"email":"","mail_to":""}`)
	if w.Code != http.StatusOK {
		t.Fatalf("F005: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	for _, k := range []string{"email", "mail_to"} {
		if got := ausstehendStr(nachher, k); got != "" {
			t.Errorf("F005: user.json %s muss sofort leer sein, ist %q", k, got)
		}
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], nachher["email_verified_at"]) {
		t.Errorf("F005: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], nachher["email_verified_at"])
	}
	ausstehendKeinePendingFelder(t, "F005 user.json", nachher)
	if _, da := ausstehendTokenMap(t, s, uid); da {
		t.Errorf("F005: es darf kein Bestaetigungs-Token entstehen")
	}

	antwort := ausstehendAntwortMap(t, w)
	for _, k := range []string{"email", "mail_to"} {
		if got := ausstehendStr(antwort, k); got != "" {
			t.Errorf("F005: PUT-Antwort %s muss leer sein, ist %q", k, got)
		}
	}
	if v, _ := antwort["email_verified"].(bool); !v {
		t.Errorf("F005: PUT-Antwort muss email_verified=true behalten, ist %v", antwort["email_verified"])
	}
	ausstehendKeinePendingFelder(t, "F005 PUT-Antwort", antwort)
	ausstehendKeinePendingFelder(t, "F005 GET-Profil", ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid)))

	ausstehendKeinVersandAn(t, s, cfg, versand, "F005", email, mt)
}

// F006 (M21): bestaetigtes Konto erzeugt erst eine ausstehende Aenderung
// (mail_to -> neu), leert danach beide Adressfelder. Die verwaiste
// ausstehende Aenderung muss dabei verschwinden — sonst schickte ein
// anschliessendes "Erneut senden" (ResendVerificationHandler) den Link an die
// aufgegebene Adresse.
func TestF006_LeerenNachAusstehenderAenderungVerwirftPendingUndResendSchicktNichts(t *testing.T) {
	s := newTestStore(t)
	cfg := ausstehendCfg()
	versand := ausstehendBeobachteVersand(t)
	const uid = "verwaist-f006-b2"
	const email = "verwaist-f006-email-b2@beispiel.de"
	const alt = "verwaist-f006-alt-b2@beispiel.de"
	const neu = "verwaist-f006-neu-b2@beispiel.de"
	ausstehendBestaetigtesKonto(t, s, uid, email, alt)
	vorher := ausstehendKontoMap(t, s, uid)

	// Schritt 1: ausstehende Aenderung erzeugen (Vorbedingung messen).
	if w := schreibpfadProfilAktualisieren(s, cfg, uid, fmt.Sprintf(`{"mail_to":%q}`, neu)); w.Code != http.StatusOK {
		t.Fatalf("F006 Schritt 1: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	if got := ausstehendStr(ausstehendKontoMap(t, s, uid), "pending_contact_address"); got != neu {
		t.Fatalf("F006 Vorbedingung: pending_contact_address muss %q sein, ist %q", neu, got)
	}
	ausstehendWarteAufMail(t, versand, neu)
	ausstehendKeineWeitereMail(t, versand, "F006 Schritt 1", neu)

	// Schritt 2: beide Adressfelder leeren.
	w := schreibpfadProfilAktualisieren(s, cfg, uid, `{"email":"","mail_to":""}`)
	if w.Code != http.StatusOK {
		t.Fatalf("F006 Schritt 2: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	nachher := ausstehendKontoMap(t, s, uid)
	for _, k := range []string{"email", "mail_to"} {
		if got := ausstehendStr(nachher, k); got != "" {
			t.Errorf("F006: user.json %s muss leer sein, ist %q", k, got)
		}
	}
	if !reflect.DeepEqual(vorher["email_verified_at"], nachher["email_verified_at"]) {
		t.Errorf("F006: email_verified_at muss unveraendert bleiben — vorher %v, nachher %v",
			vorher["email_verified_at"], nachher["email_verified_at"])
	}
	ausstehendKeinePendingFelder(t, "F006 user.json", nachher)
	ausstehendKeinePendingFelder(t, "F006 PUT-Antwort", ausstehendAntwortMap(t, w))
	ausstehendKeinePendingFelder(t, "F006 GET-Profil", ausstehendAntwortMap(t, ausstehendProfilLesen(s, uid)))

	// Wirkort: "Erneut senden" darf die verwaiste Adresse nicht anschreiben.
	if rw := ausstehendResend(s, cfg, uid); rw.Code != http.StatusOK {
		t.Fatalf("F006 Resend: erwartet 200, bekommen %d: %s", rw.Code, rw.Body.String())
	}
	ausstehendKeinVersandAn(t, s, cfg, versand, "F006 Resend", neu, alt, email)
}
