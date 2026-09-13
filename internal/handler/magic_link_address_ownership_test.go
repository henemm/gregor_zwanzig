package handler

// TDD RED — Issue #2147 Scheibe A (+ #2311, Epic #2138): Der Magic-Link ordnet
// eine per Code nachgewiesene Adresse GENAU EINEM Konto zu.
// Spec: docs/specs/modules/magic_link_adress_eindeutigkeit.md — AC-1 bis AC-11.
//
// Geprüft wird am WIRKORT: echter Zwei-Schritt-Fluss über MagicLinkRequestHandler
// und MagicLinkVerifyHandler gegen einen echten store.Store auf t.TempDir().
// Das Ergebnis wird frisch von der Platte gelesen — Kontenzahl, rohe
// user.json-Bytes, Gästeliste (sessions.json), Session-Cookie. Die Datei nennt
// bewusst KEINE neuen Store-Symbole: sie misst Verhalten, nicht die innere
// Aufteilung der Implementierung.
//
// Liegt in `package handler`, weil der Code im paketprivaten otpStore entsteht
// (Griff: otpCodeFor aus email_verify_selbstheilung_test.go) und die Versand-Naht
// sendVerificationMailFn paketprivat ist.

import (
	"bytes"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

const eindeutigSecret = "test-secret-32-chars-minimum-ok!"

// --- Hilfen -------------------------------------------------------------------

func eindeutigCfg() *config.Config {
	// SMTPHost leer → der Anforderungs-Schritt versendet nichts.
	return &config.Config{SessionSecret: eindeutigSecret}
}

func jetztBestaetigt() *time.Time {
	t := time.Now().UTC().Add(-time.Hour)
	return &t
}

func speichereKonto(t *testing.T, s *store.Store, u model.User) {
	t.Helper()
	if u.CreatedAt.IsZero() {
		u.CreatedAt = time.Now().UTC()
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("Konto %q anlegen: %v", u.ID, err)
	}
}

func kontenAnzahl(t *testing.T, s *store.Store) int {
	t.Helper()
	ids, err := s.ListUserIDs()
	if err != nil {
		t.Fatalf("ListUserIDs: %v", err)
	}
	return len(ids)
}

func rohesKonto(t *testing.T, s *store.Store, uid string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.UserDir(uid), "user.json"))
	if err != nil {
		t.Fatalf("user.json von %q lesen: %v", uid, err)
	}
	return b
}

// roheGaesteliste liefert die sessions.json-Bytes (nil, wenn es keine gibt).
func roheGaesteliste(t *testing.T, s *store.Store, uid string) []byte {
	t.Helper()
	b, err := os.ReadFile(filepath.Join(s.UserDir(uid), "sessions.json"))
	if err != nil && !os.IsNotExist(err) {
		t.Fatalf("sessions.json von %q lesen: %v", uid, err)
	}
	return b
}

func sitzungen(t *testing.T, s *store.Store, uid string) []store.Session {
	t.Helper()
	list, err := s.LoadSessions(uid)
	if err != nil {
		t.Fatalf("LoadSessions(%q): %v", uid, err)
	}
	return list
}

func alteSitzung(t *testing.T, s *store.Store, uid string) string {
	t.Helper()
	sid, err := middleware.NewSessionID()
	if err != nil {
		t.Fatalf("NewSessionID: %v", err)
	}
	if err := s.AddSession(uid, sid); err != nil {
		t.Fatalf("AddSession(%q): %v", uid, err)
	}
	return sid
}

// anfordern führt NUR den Anforderungs-Schritt aus und liefert den hinterlegten Code.
func anfordern(t *testing.T, s *store.Store, cfg *config.Config, email string) string {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link",
		strings.NewReader(`{"email":"`+email+`"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	MagicLinkRequestHandler(s, cfg).ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("Magic-Link-Anforderung: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
	return otpCodeFor(t, email)
}

func einloesen(s *store.Store, cfg *config.Config, email, code string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
		strings.NewReader(`{"email":"`+email+`","code":"`+code+`"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	MagicLinkVerifyHandler(s, cfg).ServeHTTP(w, req)
	return w
}

func angemeldetesKonto(w *httptest.ResponseRecorder) string {
	var body map[string]string
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	return body["id"]
}

func hatSessionCookie(w *httptest.ResponseRecorder) bool {
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" {
			return true
		}
	}
	return false
}

// pruefeNeutraleAbweisung: dieselbe 400 wie bei falschem Code, kein Merkmal.
func pruefeNeutraleAbweisung(t *testing.T, ac string, w *httptest.ResponseRecorder) {
	t.Helper()
	if w.Code != http.StatusBadRequest {
		t.Errorf("%s: erwartet neutrale 400, bekommen %d: %s (angemeldet in %q)",
			ac, w.Code, w.Body.String(), angemeldetesKonto(w))
	}
	if !strings.Contains(w.Body.String(), `"invalid_or_expired_code"`) {
		t.Errorf("%s: Antwort muss von falschem Code ununterscheidbar sein "+
			`({"error":"invalid_or_expired_code"}), bekommen: %s`, ac, w.Body.String())
	}
	if hatSessionCookie(w) {
		t.Errorf("%s: abgewiesene Einlösung darf kein gz_session-Cookie ausstellen", ac)
	}
}

// --- AC-1 ---------------------------------------------------------------------

// AC-1: Anfordern für eine kontolose Adresse legt KEIN Konto an; der Code geht
// über den Bestätigungsmail-Weg (sendVerificationMailFn) an genau diese Adresse.
func TestMagicLinkAnfordernLegtKeinKontoAnUndNutztBestaetigungsweg_AC1(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	const adresse = "neu-ac1-2147@beispiel.de"

	type versand struct {
		to  string
		msg mail.Mail
	}
	gesehen := make(chan versand, 4)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, msg mail.Mail) error {
		gesehen <- versand{to: to, msg: msg}
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })

	// SMTPHost gesetzt, sonst überspringt der Handler den Versand. 127.0.0.1:1
	// verhindert, dass ein Irrweg über SendWithFallback je das Netz erreicht.
	cfg := &config.Config{SessionSecret: eindeutigSecret, SMTPHost: "127.0.0.1", SMTPPort: 1}
	code := anfordern(t, s, cfg, adresse)

	if n := kontenAnzahl(t, s); n != 0 {
		t.Errorf("AC-1: das Anfordern darf kein Konto anlegen — %d Konto/Konten vorhanden", n)
	}

	select {
	case v := <-gesehen:
		if v.to != adresse {
			t.Errorf("AC-1: Code ging an %q statt an %q", v.to, adresse)
		}
		if !strings.Contains(v.msg.PlainBody, code) {
			t.Errorf("AC-1: die versendete Mail enthält den hinterlegten Code nicht")
		}
	case <-time.After(3 * time.Second):
		t.Errorf("AC-1: kein Versand über den Bestätigungsmail-Weg (sendVerificationMailFn) " +
			"— der Code erreicht auf Resend-Hosts eine kontolose Adresse sonst nie")
	}
}

// --- AC-2 ---------------------------------------------------------------------

// AC-2: Das Konto entsteht erst beim korrekten Einlösen — bestätigt, mit der
// Adresse in beiden Feldern, und die Sitzung gehört genau ihm.
func TestMagicLinkEinloesenLegtGenauJetztEinBestaetigtesKontoAn_AC2(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const adresse = "neu-ac2-2147@beispiel.de"

	code := anfordern(t, s, cfg, adresse)
	if n := kontenAnzahl(t, s); n != 0 {
		t.Errorf("AC-2: vor dem Einlösen darf kein Konto existieren — %d vorhanden", n)
	}

	w := einloesen(s, cfg, adresse, code)
	if w.Code != http.StatusOK || !hatSessionCookie(w) {
		t.Fatalf("AC-2: Einlösen erwartet 200 mit Session-Cookie, bekommen %d: %s", w.Code, w.Body.String())
	}
	ids, _ := s.ListUserIDs()
	if len(ids) != 1 {
		t.Fatalf("AC-2: nach dem Einlösen muss genau ein Konto existieren, vorhanden: %v", ids)
	}
	uid := ids[0]
	if angemeldetesKonto(w) != uid || !strings.HasPrefix(uid, "m-") {
		t.Errorf("AC-2: Anmeldung in %q, neues Konto ist %q (erwartet Präfix m-)", angemeldetesKonto(w), uid)
	}
	u := ladeKonto(t, s, uid)
	if u.EmailVerifiedAt == nil || u.Email != adresse || u.MailTo != adresse {
		t.Errorf("AC-2: neues Konto muss bestätigt sein und email=mail_to=%q tragen, ist: verified=%v email=%q mail_to=%q",
			adresse, u.EmailVerifiedAt, u.Email, u.MailTo)
	}
	if n := len(sitzungen(t, s, uid)); n != 1 {
		t.Errorf("AC-2: das neue Konto muss genau eine Sitzung haben, hat %d", n)
	}
}

// --- AC-3 ---------------------------------------------------------------------

// AC-3 (Kernlücke #2147): B hat opfer@ als bestätigte Kontaktadresse, A trägt
// opfer@ nur im Feld email. Die Einlösung landet in B — in BEIDEN
// Verzeichnis-Reihenfolgen (ListUserIDs sortiert nach Kennung, deshalb wird
// über die Kennungen parametrisiert, nicht über die Anlage-Reihenfolge).
func TestMagicLinkLandetBeimBestaetigtenInhaberNieImNebenfeldKonto_AC3(t *testing.T) {
	const opfer = "opfer-ac3-2147@beispiel.de"
	faelle := []struct{ name, idA, idB string }{
		{"nebenfeld-konto-zuerst", "u1-nebenfeld", "u2-inhaber"},
		{"inhaber-zuerst", "u2-nebenfeld", "u1-inhaber"},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			t.Cleanup(ResetOTPStoreForTest)
			s := newTestStore(t)
			cfg := eindeutigCfg()
			speichereKonto(t, s, model.User{ID: f.idA, Email: opfer,
				MailTo: "a-kontakt-ac3@beispiel.de", EmailVerifiedAt: jetztBestaetigt()})
			speichereKonto(t, s, model.User{ID: f.idB, Email: opfer,
				MailTo: opfer, EmailVerifiedAt: jetztBestaetigt()})
			vorherA := rohesKonto(t, s, f.idA)

			w := einloesen(s, cfg, opfer, anfordern(t, s, cfg, opfer))

			if w.Code != http.StatusOK || angemeldetesKonto(w) != f.idB {
				t.Errorf("AC-3: erwartet 200 mit Anmeldung in B=%q, bekommen %d in %q: %s",
					f.idB, w.Code, angemeldetesKonto(w), w.Body.String())
			}
			if n := len(sitzungen(t, s, f.idA)); n != 0 {
				t.Errorf("AC-3: Nebenfeld-Konto A=%q darf keine Sitzung erhalten, hat %d", f.idA, n)
			}
			if n := len(sitzungen(t, s, f.idB)); n != 1 {
				t.Errorf("AC-3: Inhaber B=%q muss genau eine Sitzung haben, hat %d", f.idB, n)
			}
			if !bytes.Equal(vorherA, rohesKonto(t, s, f.idA)) {
				t.Errorf("AC-3: user.json von A=%q wurde verändert", f.idA)
			}
			if n := kontenAnzahl(t, s); n != 2 {
				t.Errorf("AC-3: kein Zweitkonto erlaubt — %d Konten statt 2", n)
			}
		})
	}
}

// --- AC-4 ---------------------------------------------------------------------

// AC-4: Adresse steht NUR im Nebenfeld eines bestätigten Kontos → neutrale
// Abweisung, kein neues Konto, A unverändert.
func TestMagicLinkWeistAdresseNurImNebenfeldNeutralAb_AC4(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const opfer = "opfer-ac4-2147@beispiel.de"
	const idA = "u-nebenfeld-ac4"
	speichereKonto(t, s, model.User{ID: idA, Email: opfer,
		MailTo: "a-kontakt-ac4@beispiel.de", EmailVerifiedAt: jetztBestaetigt()})
	vorher := rohesKonto(t, s, idA)

	w := einloesen(s, cfg, opfer, anfordern(t, s, cfg, opfer))

	pruefeNeutraleAbweisung(t, "AC-4", w)
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-4: kein neues Konto erlaubt — %d Konten statt 1", n)
	}
	if n := len(sitzungen(t, s, idA)); n != 0 {
		t.Errorf("AC-4: Konto A darf keine Sitzung erhalten, hat %d", n)
	}
	if !bytes.Equal(vorher, rohesKonto(t, s, idA)) {
		t.Errorf("AC-4: user.json von A wurde verändert")
	}
}

// --- AC-5 ---------------------------------------------------------------------

// AC-5 (#2311): email=alt@, bestätigte Kontaktadresse neu@ → Einlösen für neu@
// landet im bestehenden Konto; kein Zweitkonto; vorhandene Sitzung bleibt.
func TestMagicLinkMitKontaktadresseLandetImBestehendenKonto_AC5(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const uid = "u-umzug-ac5"
	const neu = "neu-ac5-2311@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: "alt-ac5-2311@beispiel.de",
		MailTo: neu, EmailVerifiedAt: jetztBestaetigt()})
	vorhanden := alteSitzung(t, s, uid)

	w := einloesen(s, cfg, neu, anfordern(t, s, cfg, neu))

	if w.Code != http.StatusOK || angemeldetesKonto(w) != uid {
		t.Errorf("AC-5: erwartet 200 mit Anmeldung in %q, bekommen %d in %q: %s",
			uid, w.Code, angemeldetesKonto(w), w.Body.String())
	}
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-5: kein Zweitkonto erlaubt (#2311) — %d Konten statt 1", n)
	}
	list := sitzungen(t, s, uid)
	gefunden := false
	for _, sess := range list {
		if sess.ID == vorhanden {
			gefunden = true
		}
	}
	if !gefunden || len(list) != 2 {
		t.Errorf("AC-5: vorhandene Sitzung muss bleiben und genau eine neue hinzukommen — "+
			"alte vorhanden=%v, Anzahl=%d", gefunden, len(list))
	}
}

// --- AC-6 ---------------------------------------------------------------------

// AC-6: unbestätigte Kontaktadresse neu@ an einem Konto MIT Zugangsdaten →
// keine Anmeldung, kein Zweitkonto, Konto samt Gästeliste byteidentisch.
func TestMagicLinkUebernimmtNieUnbestaetigtesKontoMitZugangsdaten_AC6(t *testing.T) {
	const neu = "neu-ac6-2147@beispiel.de"
	stempel := time.Date(2026, 9, 1, 8, 0, 0, 0, time.UTC)
	faelle := []struct {
		name   string
		zugang func(u *model.User)
	}{
		{"passwort", func(u *model.User) { u.PasswordHash = "$2a$10$diesIstEinBcryptHashAC6x" }},
		{"passkey", func(u *model.User) {
			u.PasskeyCredentials = []model.WebAuthnCredential{{
				ID: []byte{4, 5, 6}, PublicKey: []byte{7, 8, 9},
				AttestationType: "none", Transport: []string{"internal"},
				CreatedAt: stempel, Label: "Telefon",
			}}
		}},
		{"google", func(u *model.User) { u.OAuthProvider, u.OAuthSub = "google", "sub-ac6-2147" }},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			t.Cleanup(ResetOTPStoreForTest)
			s := newTestStore(t)
			cfg := eindeutigCfg()
			const uid = "u-zugang-ac6"
			konto := model.User{ID: uid, Email: "alt-ac6-2147@beispiel.de", MailTo: neu}
			f.zugang(&konto)
			speichereKonto(t, s, konto)
			alteSitzung(t, s, uid)
			vorherKonto := rohesKonto(t, s, uid)
			vorherSitzungen := roheGaesteliste(t, s, uid)

			w := einloesen(s, cfg, neu, anfordern(t, s, cfg, neu))

			pruefeNeutraleAbweisung(t, "AC-6/"+f.name, w)
			if n := kontenAnzahl(t, s); n != 1 {
				t.Errorf("AC-6/%s: kein Zweitkonto erlaubt — %d Konten statt 1", f.name, n)
			}
			if !bytes.Equal(vorherKonto, rohesKonto(t, s, uid)) {
				t.Errorf("AC-6/%s: user.json wurde verändert (Zugangsdaten/Bestätigung angefasst)", f.name)
			}
			if !bytes.Equal(vorherSitzungen, roheGaesteliste(t, s, uid)) {
				t.Errorf("AC-6/%s: Gästeliste wurde verändert", f.name)
			}
		})
	}
}

// --- AC-7 ---------------------------------------------------------------------

// dateienAusserKontoUndSitzungen hält alle Nutzdaten eines Kontos fest — alles
// unter UserDir außer user.json und sessions.json.
func dateienAusserKontoUndSitzungen(t *testing.T, s *store.Store, uid string) map[string][]byte {
	t.Helper()
	root := s.UserDir(uid)
	out := map[string][]byte{}
	err := filepath.Walk(root, func(p string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return err
		}
		rel, _ := filepath.Rel(root, p)
		if rel == "user.json" || rel == "sessions.json" {
			return nil
		}
		b, rerr := os.ReadFile(p)
		if rerr != nil {
			return rerr
		}
		out[rel] = b
		return nil
	})
	if err != nil {
		t.Fatalf("Nutzdaten von %q erfassen: %v", uid, err)
	}
	return out
}

// AC-7: zugangsloses, unbestätigtes Konto mit opfer@ als Kontaktadresse und
// laufender Sitzung → Einlösen bestätigt das Konto, die alte Sitzung erlischt,
// nur der Einlösende hat eine Sitzung; Nutzdaten bleiben byteidentisch.
func TestMagicLinkUebernimmtZugangslosesKontoUndBeendetAlteSitzungen_AC7(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const uid = "u-offen-ac7"
	const opfer = "opfer-ac7-2147@beispiel.de"
	speichereKonto(t, s, model.User{ID: uid, Email: opfer, MailTo: opfer, DisplayName: "Offenes Konto"})
	alt := alteSitzung(t, s, uid)
	seedTrip(t, s.WithUser(uid), "trip-ac7-2147", "Probe-Tour")
	vorherDaten := dateienAusserKontoUndSitzungen(t, s, uid)
	if len(vorherDaten) == 0 {
		t.Fatalf("AC-7: Fixture ohne Nutzdaten — der Erhalt-Nachweis wäre leer")
	}
	vorherKonto := ladeKonto(t, s, uid)

	w := einloesen(s, cfg, opfer, anfordern(t, s, cfg, opfer))

	if w.Code != http.StatusOK || angemeldetesKonto(w) != uid || !hatSessionCookie(w) {
		t.Fatalf("AC-7: erwartet 200 mit Cookie und Anmeldung in %q, bekommen %d in %q: %s",
			uid, w.Code, angemeldetesKonto(w), w.Body.String())
	}
	nachher := ladeKonto(t, s, uid)
	if nachher.EmailVerifiedAt == nil {
		t.Errorf("AC-7: das übernommene Konto muss bestätigt sein")
	}
	nachher.EmailVerifiedAt = nil
	a, _ := json.Marshal(vorherKonto)
	b, _ := json.Marshal(nachher)
	if !bytes.Equal(a, b) {
		t.Errorf("AC-7: außer email_verified_at darf sich am Konto nichts ändern:\nvorher:  %s\nnachher: %s", a, b)
	}
	list := sitzungen(t, s, uid)
	for _, sess := range list {
		if sess.ID == alt {
			t.Errorf("AC-7: die alte Sitzung muss nach der Übernahme ungültig sein, steht noch auf der Gästeliste")
		}
	}
	if len(list) != 1 {
		t.Errorf("AC-7: genau eine Sitzung (die des Einlösenden) erwartet, vorhanden: %d", len(list))
	}
	if n := kontenAnzahl(t, s); n != 1 {
		t.Errorf("AC-7: kein Zweitkonto erlaubt — %d Konten statt 1", n)
	}
	nachherDaten := dateienAusserKontoUndSitzungen(t, s, uid)
	if len(nachherDaten) != len(vorherDaten) {
		t.Errorf("AC-7: Nutzdaten-Dateien vorher %d, nachher %d", len(vorherDaten), len(nachherDaten))
	}
	for rel, inhalt := range vorherDaten {
		if !bytes.Equal(inhalt, nachherDaten[rel]) {
			t.Errorf("AC-7: Nutzdatei %q wurde verändert oder gelöscht", rel)
		}
	}
}

// --- AC-8 ---------------------------------------------------------------------

// AC-8: Bestandsduplikat — zwei bestätigte Inhaber derselben Kontaktadresse →
// neutrale Abweisung, kein neues Konto, Log ohne Klartext-Adresse.
func TestMagicLinkWeistBestandsduplikatAbOhneAdresseImLog_AC8(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	cfg := eindeutigCfg()
	const opfer = "Opfer-Doppel-AC8@beispiel.de"
	norm := strings.ToLower(opfer)
	speichereKonto(t, s, model.User{ID: "u1-doppel-ac8", Email: norm, MailTo: norm, EmailVerifiedAt: jetztBestaetigt()})
	speichereKonto(t, s, model.User{ID: "u2-doppel-ac8", Email: norm, MailTo: norm, EmailVerifiedAt: jetztBestaetigt()})
	vorher1 := rohesKonto(t, s, "u1-doppel-ac8")
	vorher2 := rohesKonto(t, s, "u2-doppel-ac8")
	code := anfordern(t, s, cfg, opfer)

	// Mitschnitt NUR um den Einlöse-Schritt (der Anforderungs-Schritt ohne SMTP
	// ist nicht Gegenstand dieses AC).
	var mitschnitt bytes.Buffer
	log.SetOutput(&mitschnitt)
	w := einloesen(s, cfg, opfer, code)
	log.SetOutput(os.Stderr)

	pruefeNeutraleAbweisung(t, "AC-8", w)
	if n := kontenAnzahl(t, s); n != 2 {
		t.Errorf("AC-8: kein neues Konto erlaubt — %d Konten statt 2", n)
	}
	if !bytes.Equal(vorher1, rohesKonto(t, s, "u1-doppel-ac8")) || !bytes.Equal(vorher2, rohesKonto(t, s, "u2-doppel-ac8")) {
		t.Errorf("AC-8: die Duplikat-Konten dürfen nicht verändert werden")
	}
	protokoll := strings.ToLower(mitschnitt.String())
	if strings.Contains(protokoll, norm) || strings.Contains(protokoll, "opfer-doppel-ac8") {
		t.Errorf("AC-8: das Server-Log nennt die Adresse im Klartext: %q", mitschnitt.String())
	}
	if mitschnitt.Len() == 0 {
		t.Errorf("AC-8: die Mehrdeutigkeit muss protokolliert werden (Konto-IDs bzw. Anzahl, ohne Adresse) — Log ist leer")
	}
}

// --- AC-9 ---------------------------------------------------------------------

// AC-9: zwei gleichzeitige Einlösungen desselben gültigen Codes → genau eine
// Erfolgsantwort, genau ein Konto. Startschranke, mehrfach wiederholt.
func TestMagicLinkCodeWirktBeiGleichzeitigerEinloesungNurEinmal_AC9(t *testing.T) {
	// Das Zeitfenster zwischen Nachschlagen und Verbrauch ist schmal: gemessen
	// am Altcode fiel die Doppel-Einlösung erst in Runde 12–276 von 300 auf.
	// 1000 Runden halten den Nachweis stabil rot, kosten unter einer Sekunde.
	const runden = 1000
	t.Cleanup(ResetOTPStoreForTest)
	log.SetOutput(io.Discard) // 1000× „SMTP not configured" überdeckt sonst den Befund
	t.Cleanup(func() { log.SetOutput(os.Stderr) })
	for i := 0; i < runden; i++ {
		ResetOTPStoreForTest()
		s := newTestStore(t)
		cfg := eindeutigCfg()
		const adresse = "parallel-ac9-2147@beispiel.de"
		code := anfordern(t, s, cfg, adresse)

		// Anfragen VOR der Startschranke bauen: hinter der Schranke läuft nur
		// noch der Handler, damit beide Aufrufe im selben Zeitfenster prüfen.
		h := MagicLinkVerifyHandler(s, cfg)
		start := make(chan struct{})
		var wg sync.WaitGroup
		antworten := make([]*httptest.ResponseRecorder, 2)
		for k := 0; k < 2; k++ {
			req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
				strings.NewReader(`{"email":"`+adresse+`","code":"`+code+`"}`))
			req.Header.Set("Content-Type", "application/json")
			antworten[k] = httptest.NewRecorder()
			wg.Add(1)
			go func(w *httptest.ResponseRecorder, r *http.Request) {
				defer wg.Done()
				<-start
				h.ServeHTTP(w, r)
			}(antworten[k], req)
		}
		close(start)
		wg.Wait()

		erfolge, neutral := 0, 0
		for _, w := range antworten {
			switch {
			case w.Code == http.StatusOK:
				erfolge++
			case w.Code == http.StatusBadRequest && strings.Contains(w.Body.String(), `"invalid_or_expired_code"`):
				neutral++
			}
		}
		n := kontenAnzahl(t, s)
		if erfolge != 1 || neutral != 1 || n != 1 {
			t.Fatalf("AC-9 (Runde %d/%d): erwartet 1 Erfolg + 1 neutrale 400 + 1 Konto, "+
				"bekommen Erfolge=%d neutral=%d Konten=%d (Antworten: %d %q / %d %q)",
				i+1, runden, erfolge, neutral, n,
				antworten[0].Code, antworten[0].Body.String(), antworten[1].Code, antworten[1].Body.String())
		}
	}
	ResetOTPStoreForTest()
}

// --- AC-10 --------------------------------------------------------------------

// AC-10: trägt nur ein Testkonto die Adresse, wird es ignoriert — Anmeldung in
// ein neu angelegtes reguläres Konto, das Testkonto bleibt unberührt.
func TestMagicLinkIgnoriertTestkonten_AC10(t *testing.T) {
	for _, testID := range []string{"tg-live-e2e", "gz-test-ac10"} {
		t.Run(testID, func(t *testing.T) {
			t.Cleanup(ResetOTPStoreForTest)
			s := newTestStore(t)
			cfg := eindeutigCfg()
			const adresse = "fixture-ac10-2147@beispiel.de"
			speichereKonto(t, s, model.User{ID: testID, Email: adresse, MailTo: adresse, EmailVerifiedAt: jetztBestaetigt()})
			vorher := rohesKonto(t, s, testID)

			w := einloesen(s, cfg, adresse, anfordern(t, s, cfg, adresse))

			uid := angemeldetesKonto(w)
			if w.Code != http.StatusOK || uid == testID || !strings.HasPrefix(uid, "m-") {
				t.Errorf("AC-10: erwartet 200 mit Anmeldung in ein neues m-Konto, bekommen %d in %q: %s",
					w.Code, uid, w.Body.String())
			}
			if n := len(sitzungen(t, s, testID)); n != 0 {
				t.Errorf("AC-10: Testkonto %q darf keine Sitzung erhalten, hat %d", testID, n)
			}
			if !bytes.Equal(vorher, rohesKonto(t, s, testID)) {
				t.Errorf("AC-10: Testkonto %q wurde verändert", testID)
			}
			if n := kontenAnzahl(t, s); n != 2 {
				t.Errorf("AC-10: erwartet Testkonto + genau ein neues reguläres Konto, vorhanden: %d", n)
			}
		})
	}
}

// --- AC-11 --------------------------------------------------------------------

// AC-11 (Regressionswächter, heute schon grün): Bestandsduplikat mit je eigenem
// Passwort — der Passwort-Login bleibt für beide Inhaber unverändert.
func TestPasswortLoginBleibtBeiBestandsduplikatFuerBeideMoeglich_AC11(t *testing.T) {
	s := newTestStore(t)
	const adresse = "doppelt-ac11-2147@beispiel.de"
	konten := map[string]string{"u1-doppelpw-ac11": "geheim-eins-11", "u2-doppelpw-ac11": "geheim-zwei-11"}
	for uid, pw := range konten {
		hash, err := bcrypt.GenerateFromPassword([]byte(pw), bcrypt.MinCost)
		if err != nil {
			t.Fatalf("bcrypt: %v", err)
		}
		speichereKonto(t, s, model.User{ID: uid, Email: adresse, MailTo: adresse,
			PasswordHash: string(hash), EmailVerifiedAt: jetztBestaetigt()})
	}
	for uid, pw := range konten {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/login",
			strings.NewReader(`{"username":"`+uid+`","password":"`+pw+`"}`))
		w := httptest.NewRecorder()
		LoginHandler(s, eindeutigSecret).ServeHTTP(w, req)
		if w.Code != http.StatusOK || !hatSessionCookie(w) {
			t.Errorf("AC-11: Passwort-Login für %q erwartet 200 mit Cookie, bekommen %d: %s", uid, w.Code, w.Body.String())
		}
		if n := len(sitzungen(t, s, uid)); n != 1 {
			t.Errorf("AC-11: %q muss genau eine Sitzung haben, hat %d", uid, n)
		}
	}
}
