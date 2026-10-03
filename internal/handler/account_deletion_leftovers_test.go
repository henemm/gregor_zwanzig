package handler

// Restebereinigung und Lösch-Code bei der Kontoloeschung — Issue #2160
// (Epic #2138 Multi-User), Spec docs/specs/modules/account_deletion.md.
//
// Zusicherungen werden dort geprueft, wo sie WIRKEN:
//   - Telegram-Tokens: die Datei telegram_tokens.json wird von PLATTE gelesen,
//     nicht die Map im Speicher (AC-10).
//   - Login-OTPs: das uebriggebliebene OTP geht durch den ECHTEN
//     MagicLinkVerifyHandler; es darf kein neues Konto entstehen (AC-11).
//   - Speicherfehler: ein VERZEICHNIS am Zielpfad (chmod-Tricks versagen unter
//     root) — kein Mock (AC-13/AC-14).
//
// Neuer Vertrag (siehe Abschlussbericht): deleteCodeStore (package-level
// sync.Map, Schluessel UserID, Wert *deleteCodeEntry), RequestDeleteCodeHandler,
// (*TelegramTokenStore).RemoveByUser / IssueToken, DeleteAccountHandler(s, ts).
//
// Alle Tests schreiben in den package-level otpStore/deleteCodeStore, raeumen per
// t.Cleanup auf und laufen nicht parallel.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// --- Helfer -----------------------------------------------------------------

func zuruecksetzenLoeschCodes() {
	deleteCodeStore.Range(func(k, _ any) bool {
		deleteCodeStore.Delete(k)
		return true
	})
}

func setzeLoeschCode(userID, code string, expiresAt time.Time, attempts int32) *deleteCodeEntry {
	e := &deleteCodeEntry{code: code, expiresAt: expiresAt, attempts: attempts}
	deleteCodeStore.Store(userID, e)
	return e
}

func setzeLoginOTP(address, code string, expiresAt time.Time, attempts int32) *otpEntry {
	e := &otpEntry{code: code, expiresAt: expiresAt, attempts: attempts}
	otpStore.Store(store.NormalizeEmailAddress(address), e)
	return e
}

// tokensVonPlatte liest telegram_tokens.json direkt aus dem Datenverzeichnis.
func tokensVonPlatte(t *testing.T, dir string) map[string]pendingTelegramToken {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(dir, "telegram_tokens.json"))
	if err != nil {
		t.Fatalf("telegram_tokens.json nicht lesbar: %v", err)
	}
	var m map[string]pendingTelegramToken
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("telegram_tokens.json ist kein gueltiges JSON (halbe Datei?): %v", err)
	}
	return m
}

func tokenAnzahlFuer(m map[string]pendingTelegramToken, userID string) int {
	n := 0
	for _, pt := range m {
		if pt.UserID == userID {
			n++
		}
	}
	return n
}

func mustIssueToken(t *testing.T, ts *TelegramTokenStore, userID string) string {
	t.Helper()
	tok, err := ts.IssueToken(userID)
	if err != nil {
		t.Fatalf("IssueToken(%s): %v", userID, err)
	}
	return tok
}

func dateiBytes(t *testing.T, path string) []byte {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	return b
}

// gesendeteMail ist die vom Versand-Seam beobachtete echte Mail.
type gesendeteMail struct {
	to   string
	body string
}

// beobachteVersandMails haengt sich an die echte Versand-Naht
// sendVerificationMailFn (Muster auth_oauth_test.go): echter Empfaenger, echte
// gerenderte Mail — nur der SMTP-Dial entfaellt. fehler != nil laesst den
// Versand scheitern.
func beobachteVersandMails(t *testing.T, fehler error) func() []gesendeteMail {
	t.Helper()
	var mu sync.Mutex
	var mails []gesendeteMail
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(cfg mail.MailConfig, to string, msg mail.Mail) error {
		mu.Lock()
		mails = append(mails, gesendeteMail{to: to, body: msg.PlainBody})
		mu.Unlock()
		return fehler
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return func() []gesendeteMail {
		mu.Lock()
		defer mu.Unlock()
		return append([]gesendeteMail(nil), mails...)
	}
}

var sechsStellig = regexp.MustCompile(`\b(\d{6})\b`)

func postLoeschCodeAnfordern(h http.Handler, userID string) *httptest.ResponseRecorder {
	req := httptest.NewRequest(http.MethodPost, "/api/auth/account/delete-code", strings.NewReader(`{}`))
	req.Header.Set("Content-Type", "application/json")
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), userID))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	return w
}

func mailKonfig() config.Config {
	return config.Config{SMTPHost: "smtp.beispiel.invalid", SMTPPort: 587, SessionSecret: "test-secret"}
}

// --- AC-1 + AC-10: Zwei Nutzer, Token-Datei von Platte ----------------------

func TestKontoLoeschen_ZweiNutzer_TokenDateiOhneGeloeschtenNutzer(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	bertram := passwortKonto(t, s, "bertram", "bertram@beispiel.de")
	os.WriteFile(filepath.Join(s.DataDir, "users", "bertram", "marker.json"), []byte(`{"b":1}`), 0644)

	ts := NewTelegramTokenStore(s.DataDir)
	annaTok1 := mustIssueToken(t, ts, "anna")
	annaTok2 := mustIssueToken(t, ts, "anna")
	bertramTok := mustIssueToken(t, ts, "bertram")

	bertramUserJSON := dateiBytes(t, filepath.Join(s.DataDir, "users", "bertram", "user.json"))
	bertramMarker := dateiBytes(t, filepath.Join(s.DataDir, "users", "bertram", "marker.json"))

	h := DeleteAccountHandler(s, ts)
	w := postKontoLoeschen(h, "anna", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	onDisk := tokensVonPlatte(t, s.DataDir)
	if n := tokenAnzahlFuer(onDisk, "anna"); n != 0 {
		t.Errorf("telegram_tokens.json (Platte) enthaelt noch %d Token(s) des geloeschten Nutzers", n)
	}
	for _, tok := range []string{annaTok1, annaTok2} {
		if _, ok := onDisk[tok]; ok {
			t.Errorf("Token %s des geloeschten Nutzers steht noch auf der Platte", tok)
		}
	}
	if pt, ok := onDisk[bertramTok]; !ok || pt.UserID != "bertram" {
		t.Errorf("Token des anderen Nutzers muss unveraendert auf der Platte stehen, ist %+v (vorhanden=%v)", pt, ok)
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Ordner des geloeschten Nutzers muss weg sein")
	}
	if !bytes.Equal(bertramUserJSON, dateiBytes(t, filepath.Join(s.DataDir, "users", "bertram", "user.json"))) ||
		!bytes.Equal(bertramMarker, dateiBytes(t, filepath.Join(s.DataDir, "users", "bertram", "marker.json"))) {
		t.Error("Ordner des anderen Nutzers wurde veraendert")
	}
	if u, err := s.LoadUser(bertram.ID); err != nil || u == nil {
		t.Errorf("anderer Nutzer muss ladbar bleiben: %v", err)
	}
	// Auch der Speicher des Stores kennt die Tokens des Geloeschten nicht mehr.
	if _, ok := ts.ResolveAndDelete(annaTok1); ok {
		t.Error("Token des geloeschten Nutzers ist noch aufloesbar")
	}
}

// --- AC-3: falsches Passwort veraendert NICHTS ------------------------------

func TestKontoLoeschen_FalschesPasswort_LaesstTokensOTPsUndCodeUnberuehrt(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	u := passwortKonto(t, s, "anna", "anna@beispiel.de")
	u.MailTo = "anna-mail@beispiel.de"
	u.PendingContactAddress = "anna-neu@beispiel.de"
	mustSaveUser(t, s, u)

	ts := NewTelegramTokenStore(s.DataDir)
	tok := mustIssueToken(t, ts, "anna")
	vorher := dateiBytes(t, filepath.Join(s.DataDir, "telegram_tokens.json"))

	otpEmail := setzeLoginOTP("anna@beispiel.de", "111111", time.Now().Add(10*time.Minute), 0)
	otpMailTo := setzeLoginOTP("anna-mail@beispiel.de", "222222", time.Now().Add(10*time.Minute), 1)
	otpPending := setzeLoginOTP("anna-neu@beispiel.de", "333333", time.Now().Add(10*time.Minute), 0)
	code := setzeLoeschCode("anna", "444444", time.Now().Add(10*time.Minute), 0)

	h := DeleteAccountHandler(s, ts)
	w := postKontoLoeschen(h, "anna", `{"password":"falsch"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "wrong_password") {
		t.Fatalf("expected 403 wrong_password, got %d: %s", w.Code, w.Body.String())
	}

	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Ordner muss bleiben")
	}
	if !bytes.Equal(vorher, dateiBytes(t, filepath.Join(s.DataDir, "telegram_tokens.json"))) {
		t.Error("telegram_tokens.json (Platte) wurde bei falschem Passwort veraendert")
	}
	if pt, ok := tokensVonPlatte(t, s.DataDir)[tok]; !ok || pt.UserID != "anna" {
		t.Error("Token des Nutzers muss auf der Platte bleiben")
	}
	for addr, want := range map[string]*otpEntry{
		"anna@beispiel.de": otpEmail, "anna-mail@beispiel.de": otpMailTo, "anna-neu@beispiel.de": otpPending,
	} {
		got, ok := otpStore.Load(store.NormalizeEmailAddress(addr))
		if !ok || got.(*otpEntry) != want {
			t.Errorf("Login-OTP fuer %s wurde bei falschem Passwort entfernt/ersetzt", addr)
		}
	}
	if got, ok := deleteCodeStore.Load("anna"); !ok || got.(*deleteCodeEntry) != code {
		t.Error("Lösch-Code wurde bei falschem Passwort entfernt/ersetzt")
	}
	if code.attempts != 0 {
		t.Errorf("Passwortweg darf den Fehlversuchszaehler des Lösch-Codes nicht veraendern, ist %d", code.attempts)
	}
}

// --- AC-4: ohne Nachweis keinerlei Nebenwirkung ------------------------------

func TestKontoLoeschen_OhneNachweis_LaesstTokenDateiUnberuehrt(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	ts := NewTelegramTokenStore(s.DataDir)
	mustIssueToken(t, ts, "anna")
	vorher := dateiBytes(t, filepath.Join(s.DataDir, "telegram_tokens.json"))

	w := postKontoLoeschen(DeleteAccountHandler(s, ts), "anna", `{}`)
	if w.Code != 400 {
		t.Fatalf("expected 400, got %d", w.Code)
	}
	if !bytes.Equal(vorher, dateiBytes(t, filepath.Join(s.DataDir, "telegram_tokens.json"))) {
		t.Error("Token-Datei wurde ohne Nachweis veraendert")
	}
}

// --- AC-5: Code geht an EffectiveContactAddress, eigener Store ---------------

func TestLoeschCodeAnfordern_GehtAnWirksameAdresseUndLiegtImEigenenStore(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	mails := beobachteVersandMails(t, nil)
	h := RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(10, time.Hour))

	// A: mail_to weicht von email ab -> mail_to gewinnt.
	mustSaveUser(t, s, model.User{ID: "anna", Email: "alt@beispiel.de", MailTo: "neu@beispiel.de", CreatedAt: time.Now()})
	// B: kein mail_to -> email.
	mustSaveUser(t, s, model.User{ID: "bertram", Email: "bertram@beispiel.de", CreatedAt: time.Now()})

	for _, id := range []string{"anna", "bertram"} {
		w := postLoeschCodeAnfordern(h, id)
		if w.Code != 200 {
			t.Fatalf("%s: expected 200, got %d: %s", id, w.Code, w.Body.String())
		}
	}

	got := mails()
	if len(got) != 2 {
		t.Fatalf("expected genau 2 Mails, got %d: %+v", len(got), got)
	}
	if got[0].to != "neu@beispiel.de" {
		t.Errorf("Code fuer anna muss an mail_to gehen, ging an %q", got[0].to)
	}
	if got[1].to != "bertram@beispiel.de" {
		t.Errorf("Code fuer bertram muss an email gehen, ging an %q", got[1].to)
	}
	for i, id := range []string{"anna", "bertram"} {
		m := sechsStellig.FindStringSubmatch(got[i].body)
		if m == nil {
			t.Fatalf("%s: kein 6-stelliger Code in der Mail: %q", id, got[i].body)
		}
		e, ok := deleteCodeStore.Load(id)
		if !ok {
			t.Fatalf("%s: Lösch-Code nicht im Store (Schluessel UserID)", id)
		}
		entry := e.(*deleteCodeEntry)
		if entry.code != m[1] {
			t.Errorf("%s: gespeicherter Code %q != versendeter %q", id, entry.code, m[1])
		}
		if d := time.Until(entry.expiresAt); d < 14*time.Minute || d > 16*time.Minute {
			t.Errorf("%s: TTL soll 15 Minuten sein, ist %v", id, d)
		}
	}
	// Getrennte Stores: das Anfordern legt KEIN Login-OTP an.
	n := 0
	otpStore.Range(func(_, _ any) bool { n++; return true })
	if n != 0 {
		t.Errorf("Lösch-Code darf nicht im Login-OTP-Store landen, dort liegen %d Eintraege", n)
	}
}

// AC-5 (Sicherheitsfall): die ausstehende Adresse ist genau das Feld, das ein
// Sitzungsdieb setzen kann — der Code darf NIE dorthin gehen (anders als die
// Verifikationsmail, die bewusst an die ausstehende Adresse geht).
func TestLoeschCodeAnfordern_GehtNieAnAusstehendeAdresse(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	mails := beobachteVersandMails(t, nil)
	mustSaveUser(t, s, model.User{
		ID: "anna", Email: "alt@beispiel.de", MailTo: "echt@beispiel.de",
		PendingContactAddress: "dieb@beispiel.de", CreatedAt: time.Now(),
	})

	w := postLoeschCodeAnfordern(RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(10, time.Hour)), "anna")
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	got := mails()
	if len(got) != 1 || got[0].to != "echt@beispiel.de" {
		t.Fatalf("Code muss genau einmal an die wirksame Adresse gehen, Mails: %+v", got)
	}
	for _, m := range got {
		if strings.Contains(m.to, "dieb@") {
			t.Errorf("Lösch-Code ging an die ausstehende Adresse: %q", m.to)
		}
	}
}

func TestLoeschCodeAnfordern_MailVersandScheitert_502_KeinCodeGespeichert(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	beobachteVersandMails(t, errMailDown)
	mustSaveUser(t, s, model.User{ID: "anna", Email: "anna@beispiel.de", CreatedAt: time.Now()})

	w := postLoeschCodeAnfordern(RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(10, time.Hour)), "anna")
	if w.Code != 502 || !strings.Contains(w.Body.String(), "mail_failed") {
		t.Fatalf("expected 502 mail_failed, got %d: %s", w.Code, w.Body.String())
	}
	if _, ok := deleteCodeStore.Load("anna"); ok {
		t.Error("bei fehlgeschlagenem Versand darf kein Code gespeichert sein")
	}
}

func TestLoeschCodeAnfordern_ZweiteAnforderungDesselbenNutzersWirdGedrosselt(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	beobachteVersandMails(t, nil)
	mustSaveUser(t, s, model.User{ID: "anna", Email: "anna@beispiel.de", CreatedAt: time.Now()})
	h := RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(1, time.Hour))

	if w := postLoeschCodeAnfordern(h, "anna"); w.Code != 200 {
		t.Fatalf("erste Anforderung: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	w := postLoeschCodeAnfordern(h, "anna")
	var body struct {
		Error string `json:"error"`
	}
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	if w.Code != 429 || body.Error != "rate_limit_exceeded" {
		t.Fatalf("zweite Anforderung: expected 429 rate_limit_exceeded, got %d: %s", w.Code, w.Body.String())
	}
}

var errMailDown = &mailDownError{}

type mailDownError struct{}

func (*mailDownError) Error() string { return "smtp down" }

// Ende-zu-Ende des Code-Weges: Mail -> Code aus der Mail -> Löschung.
func TestKontoLoeschen_MitCodeAusDerVersandtenMail(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	mails := beobachteVersandMails(t, nil)
	passwortlosKonto(t, s, "m-0a0b0c0d", "magic@beispiel.de")

	if w := postLoeschCodeAnfordern(RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(10, time.Hour)), "m-0a0b0c0d"); w.Code != 200 {
		t.Fatalf("Anforderung: %d %s", w.Code, w.Body.String())
	}
	got := mails()
	if len(got) != 1 {
		t.Fatalf("expected 1 Mail, got %d", len(got))
	}
	code := sechsStellig.FindStringSubmatch(got[0].body)[1]

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "m-0a0b0c0d", `{"code":"`+code+`"}`)
	if w.Code != 200 {
		t.Fatalf("Löschung mit Mail-Code: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "m-0a0b0c0d") {
		t.Error("Konto muss geloescht sein")
	}
}

// --- AC-8: Login-OTP und Lösch-Code sind getrennte Welten ---------------------

func TestKontoLoeschen_LoginOTPAlsLoeschCode_403InvalidCode(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortlosKonto(t, s, "m-aaaa0001", "magic@beispiel.de")
	setzeLoginOTP("magic@beispiel.de", "987654", time.Now().Add(10*time.Minute), 0)

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "m-aaaa0001", `{"code":"987654"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "m-aaaa0001") {
		t.Error("ein Login-OTP darf kein Konto loeschen")
	}
}

func TestMagicLinkVerify_LoeschCodeAlsLoginOTP_NichtEinloesbar(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortlosKonto(t, s, "m-aaaa0002", "magic@beispiel.de")
	setzeLoeschCode("m-aaaa0002", "246810", time.Now().Add(10*time.Minute), 0)

	cfg := &config.Config{SessionSecret: "test-secret"}
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
		strings.NewReader(`{"email":"magic@beispiel.de","code":"246810"}`))
	w := httptest.NewRecorder()
	MagicLinkVerifyHandler(s, cfg).ServeHTTP(w, req)

	if w.Code != 400 {
		t.Fatalf("Lösch-Code als Login-OTP: expected 400, got %d: %s", w.Code, w.Body.String())
	}
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" {
			t.Error("mit einem Lösch-Code darf keine Sitzung ausgestellt werden")
		}
	}
	if _, ok := deleteCodeStore.Load("m-aaaa0002"); !ok {
		t.Error("der Login-Pfad darf den Lösch-Code nicht verbrauchen")
	}
}

// --- AC-9: Ablauf, Einmaligkeit, Sperre ---------------------------------------

func TestKontoLoeschen_LoeschCodeAbgelaufen_403(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "555555", time.Now().Add(-1*time.Second), 0)

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna", `{"code":"555555"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("abgelaufen: expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("abgelaufener Code darf nichts loeschen")
	}
}

func TestKontoLoeschen_DreiFehlversucheSperrenAuchDenRichtigenCode(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "666666", time.Now().Add(10*time.Minute), 0)
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	for i := 0; i < 3; i++ {
		w := postKontoLoeschen(h, "anna", `{"code":"000000"}`)
		if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
			t.Fatalf("Fehlversuch %d: expected 403 invalid_code, got %d: %s", i+1, w.Code, w.Body.String())
		}
	}
	w := postKontoLoeschen(h, "anna", `{"code":"666666"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("richtiger Code nach 3 Fehlversuchen: expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("gesperrter Code darf nichts loeschen")
	}
}

func TestKontoLoeschen_ZweiFehlversucheDannRichtigerCodeLoescht(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "777777", time.Now().Add(10*time.Minute), 0)
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	for i := 0; i < 2; i++ {
		if w := postKontoLoeschen(h, "anna", `{"code":"000000"}`); w.Code != 403 {
			t.Fatalf("Fehlversuch %d: expected 403, got %d", i+1, w.Code)
		}
	}
	if w := postKontoLoeschen(h, "anna", `{"code":"777777"}`); w.Code != 200 {
		t.Fatalf("richtiger Code nach 2 Fehlversuchen: expected 200, got %d: %s", w.Code, w.Body.String())
	}
}

// --- AC-11: uebriggebliebene Login-OTPs legen kein neues Konto an --------------

func TestKontoLoeschen_LoginOTPsAllerAdressenNachLoeschungNichtMehrEinloesbar(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	s := newTestStore(t)
	u := passwortKonto(t, s, "anna", "Anna@Beispiel.de")
	u.MailTo = "Anna-Mail@Beispiel.de"
	u.PendingContactAddress = "Anna-Neu@Beispiel.de"
	mustSaveUser(t, s, u)
	passwortKonto(t, s, "bertram", "bertram@beispiel.de")

	exp := time.Now().Add(10 * time.Minute)
	setzeLoginOTP("anna@beispiel.de", "100001", exp, 0)
	setzeLoginOTP("anna-mail@beispiel.de", "100002", exp, 2) // gesperrt-nah: wird trotzdem geraeumt
	setzeLoginOTP("anna-neu@beispiel.de", "100003", exp, 0)
	fremd := setzeLoginOTP("fremd@beispiel.de", "100004", exp, 0)

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(s.DataDir)), "anna", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	cfg := &config.Config{SessionSecret: "test-secret"}
	for addr, code := range map[string]string{
		"anna@beispiel.de": "100001", "anna-mail@beispiel.de": "100002", "anna-neu@beispiel.de": "100003",
	} {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
			strings.NewReader(`{"email":"`+addr+`","code":"`+code+`"}`))
		rr := httptest.NewRecorder()
		MagicLinkVerifyHandler(s, cfg).ServeHTTP(rr, req)
		if rr.Code != 400 {
			t.Errorf("OTP fuer %s nach Löschung: expected 400, got %d: %s", addr, rr.Code, rr.Body.String())
		}
	}
	ids, _ := s.ListUserIDs()
	if len(ids) != 1 || ids[0] != "bertram" {
		t.Errorf("nach den Einloese-Versuchen darf es nur bertram geben (kein neues Konto), ist %v", ids)
	}

	// OTP fuer eine fremde Adresse ist kein Nutzerdatum: bleibt unberuehrt
	// und einloesbar.
	if got, ok := otpStore.Load("fremd@beispiel.de"); !ok || got.(*otpEntry) != fremd {
		t.Fatal("OTP einer fremden Adresse wurde angetastet")
	}
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/verify",
		strings.NewReader(`{"email":"fremd@beispiel.de","code":"100004"}`))
	rr := httptest.NewRecorder()
	MagicLinkVerifyHandler(s, cfg).ServeHTTP(rr, req)
	if rr.Code != 200 {
		t.Errorf("fremdes OTP muss einloesbar bleiben, got %d: %s", rr.Code, rr.Body.String())
	}
}

// --- AC-12: Lösch-Code gehoert genau einem Nutzer -----------------------------

func TestKontoLoeschen_FremderLoeschCodeLoeschtNichtUndEigenerCodeGehtMitDemKonto(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	passwortKonto(t, s, "bertram", "bertram@beispiel.de")
	annasCode := setzeLoeschCode("anna", "313131", time.Now().Add(10*time.Minute), 0)
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	// B versucht, mit A's Code zu loeschen.
	w := postKontoLoeschen(h, "bertram", `{"code":"313131"}`)
	if w.Code != 403 || !strings.Contains(w.Body.String(), "invalid_code") {
		t.Fatalf("B mit A's Code: expected 403 invalid_code, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "bertram") || !nutzerOrdnerVorhanden(s, "anna") {
		t.Fatal("weder A noch B darf durch B's Versuch geloescht sein")
	}
	if got, ok := deleteCodeStore.Load("anna"); !ok || got.(*deleteCodeEntry) != annasCode || annasCode.attempts != 0 {
		t.Error("A's Lösch-Code darf durch B's Versuch weder verbraucht noch hochgezaehlt werden")
	}

	// A loescht mit dem eigenen Code: Code ist danach aus dem Store.
	if w := postKontoLoeschen(h, "anna", `{"code":"313131"}`); w.Code != 200 {
		t.Fatalf("A mit eigenem Code: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if _, ok := deleteCodeStore.Load("anna"); ok {
		t.Error("A's Lösch-Code muss bei A's Löschung entfernt sein")
	}
	if !nutzerOrdnerVorhanden(s, "bertram") {
		t.Error("B darf durch A's Löschung nicht betroffen sein")
	}
}

// Auch ein Lösch-Code, der NICHT zum Konto passt, wird bei Passwort-Konten
// mit gleichzeitig korrektem Passwort nicht zur Sperre: Passwort genuegt.
func TestKontoLoeschen_PasswortKontoMitKorrektemPasswort_UnabhaengigVomLoeschCode(t *testing.T) {
	t.Cleanup(zuruecksetzenLoeschCodes)
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	setzeLoeschCode("anna", "818181", time.Now().Add(10*time.Minute), 3) // gesperrt
	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 200 {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}
	// AC-12: die Kaskade raeumt auch auf dem Passwortweg den Lösch-Code ab.
	if _, ok := deleteCodeStore.Load("anna"); ok {
		t.Error("Lösch-Code muss nach der Löschung (Passwortweg) aus dem Store sein")
	}
}

// --- AC-13: Speicherfehler im Token-Store => 500, Ordner bleibt, wiederholbar ---

func TestKontoLoeschen_TokenStoreNichtPersistierbar_500OrdnerBleibtWiederholbar(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	ts := NewTelegramTokenStore(s.DataDir)
	mustIssueToken(t, ts, "anna")

	// Fehler ohne Mock: am Zielpfad steht ein VERZEICHNIS.
	pfad := filepath.Join(s.DataDir, "telegram_tokens.json")
	if err := os.Remove(pfad); err != nil {
		t.Fatalf("remove: %v", err)
	}
	if err := os.Mkdir(pfad, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	h := DeleteAccountHandler(s, ts)
	body := `{"password":"` + loeschPasswort + `"}`
	w := postKontoLoeschen(h, "anna", body)
	if w.Code != 500 || !strings.Contains(w.Body.String(), "internal") {
		t.Fatalf("expected 500 internal, got %d: %s", w.Code, w.Body.String())
	}
	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Fatal("bei Speicherfehler muss der Nutzerordner erhalten bleiben")
	}

	// Fehler behoben -> Löschung ist wiederholbar und raeumt vollstaendig.
	if err := os.Remove(pfad); err != nil {
		t.Fatalf("remove dir: %v", err)
	}
	w = postKontoLoeschen(h, "anna", body)
	if w.Code != 200 {
		t.Fatalf("Wiederholung: expected 200, got %d: %s", w.Code, w.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Konto muss nach der Wiederholung geloescht sein")
	}
	if _, err := os.Stat(pfad); err == nil {
		if n := tokenAnzahlFuer(tokensVonPlatte(t, s.DataDir), "anna"); n != 0 {
			t.Errorf("nach der Wiederholung stehen noch %d Token(s) von anna auf der Platte", n)
		}
	}
}

// --- AC-14: atomares save() mit Fehlerrueckgabe ---------------------------------

func TestTelegramLink_SpeicherfehlerLiefert500StattNieGespeichertemToken(t *testing.T) {
	t.Setenv("TELEGRAM_BOT_USERNAME", "gregor_test_bot")
	s := newTestStore(t)
	mustSaveUser(t, s, model.User{ID: "anna", CreatedAt: time.Now()})
	ts := NewTelegramTokenStore(s.DataDir)
	pfad := filepath.Join(s.DataDir, "telegram_tokens.json")
	if err := os.Mkdir(pfad, 0755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/api/auth/telegram-link", nil)
	req = req.WithContext(middleware.ContextWithUserID(req.Context(), "anna"))
	w := httptest.NewRecorder()
	GetTelegramLinkHandler(s, ts).ServeHTTP(w, req)

	if w.Code != 500 {
		t.Fatalf("expected 500 bei Speicherfehler, got %d: %s", w.Code, w.Body.String())
	}
	if strings.Contains(w.Body.String(), "t.me/") || strings.Contains(w.Body.String(), "start=") {
		t.Errorf("es darf kein nie gespeicherter Token ausgegeben werden: %s", w.Body.String())
	}
	if _, err := ts.IssueToken("anna"); err == nil {
		t.Error("IssueToken muss den Speicherfehler als error zurueckgeben")
	}
	entries, _ := os.ReadDir(s.DataDir)
	for _, e := range entries {
		if e.Name() != "telegram_tokens.json" && strings.Contains(e.Name(), "telegram_tokens") {
			t.Errorf("Temp-Rest %q nach fehlgeschlagenem save()", e.Name())
		}
	}
}

func TestTelegramTokenStore_SaveSchreibtAtomarOhneTempRest(t *testing.T) {
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	tok := mustIssueToken(t, ts, "anna")

	m := tokensVonPlatte(t, dir) // gueltiges JSON = keine halbe Datei
	if pt, ok := m[tok]; !ok || pt.UserID != "anna" {
		t.Fatalf("Token nicht auf der Platte: %+v", m)
	}
	entries, _ := os.ReadDir(dir)
	if len(entries) != 1 || entries[0].Name() != "telegram_tokens.json" {
		names := []string{}
		for _, e := range entries {
			names = append(names, e.Name())
		}
		t.Errorf("nach save() darf nur telegram_tokens.json im Verzeichnis liegen, ist %v", names)
	}
	info, _ := os.Stat(filepath.Join(dir, "telegram_tokens.json"))
	if info.Mode().Perm() != 0600 {
		t.Errorf("Token-Datei muss 0600 haben, hat %v", info.Mode().Perm())
	}
}

func TestTelegramTokenStore_RemoveByUserEntferntNurDenEigenenUndPersistiert(t *testing.T) {
	dir := t.TempDir()
	ts := NewTelegramTokenStore(dir)
	a1 := mustIssueToken(t, ts, "anna")
	a2 := mustIssueToken(t, ts, "anna")
	b := mustIssueToken(t, ts, "bertram")

	if err := ts.RemoveByUser("anna"); err != nil {
		t.Fatalf("RemoveByUser: %v", err)
	}
	m := tokensVonPlatte(t, dir)
	if _, ok := m[a1]; ok {
		t.Error("anna-Token 1 noch auf Platte")
	}
	if _, ok := m[a2]; ok {
		t.Error("anna-Token 2 noch auf Platte")
	}
	if pt, ok := m[b]; !ok || pt.UserID != "bertram" {
		t.Error("bertram-Token muss bleiben")
	}
	// Ein Nutzer ohne Tokens ist kein Fehler.
	if err := ts.RemoveByUser("niemand"); err != nil {
		t.Errorf("RemoveByUser ohne Treffer: %v", err)
	}
}

// --- AC-16: Connect nach Löschung legt keinen Ordner neu an ----------------------

func TestTelegramConnect_NachLoeschungKeinZombieOrdner(t *testing.T) {
	s := telegramConnectTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	// Zweiter Store simuliert einen Token, der die Löschung "ueberlebt hat"
	// (z. B. ein Connect, dessen Token vor der Löschung aufgeloest wurde).
	tsAlt := NewTelegramTokenStore(t.TempDir())
	token := mustIssueToken(t, tsAlt, "anna")

	w := postKontoLoeschen(DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir())), "anna", `{"password":"`+loeschPasswort+`"}`)
	if w.Code != 200 {
		t.Fatalf("Löschung: %d %s", w.Code, w.Body.String())
	}

	req := newTelegramConnectRequest("127.0.0.1:54321", nil, map[string]any{"token": token, "chat_id": "424242"})
	rr := httptest.NewRecorder()
	PostTelegramConnectHandler(s, tsAlt)(rr, req)

	if rr.Code == 200 {
		t.Errorf("Connect fuer geloeschten Nutzer darf nicht 200 liefern: %s", rr.Body.String())
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Connect nach Löschung hat den Nutzerordner neu angelegt (Zombie)")
	}
}

// Die Race-Naht: Connect darf den Nutzer erst UNTER telegramConnectMu laden.
// Haelt die Löschung den Mutex und entfernt den Ordner, waehrend ein Connect
// bereits eingetroffen ist, muss der Connect danach den fehlenden Nutzer
// sehen — sonst schreibt SaveUser den Ordner als Zombie neu.
func TestTelegramConnect_LaedtNutzerErstUnterDemMutex(t *testing.T) {
	s := telegramConnectTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	ts := NewTelegramTokenStore(t.TempDir())
	token := mustIssueToken(t, ts, "anna")

	telegramConnectMu.Lock()
	gesperrt := true
	t.Cleanup(func() {
		if gesperrt {
			telegramConnectMu.Unlock()
		}
	})

	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		req := newTelegramConnectRequest("127.0.0.1:54321", nil, map[string]any{"token": token, "chat_id": "515151"})
		rr := httptest.NewRecorder()
		PostTelegramConnectHandler(s, ts)(rr, req)
		done <- rr
	}()
	time.Sleep(300 * time.Millisecond) // Connect ist eingetroffen und steht am Mutex

	if err := s.DeleteUser("anna"); err != nil { // die Löschung, die den Mutex haelt
		t.Fatalf("DeleteUser: %v", err)
	}
	telegramConnectMu.Unlock()
	gesperrt = false

	select {
	case rr := <-done:
		if rr.Code == 200 {
			t.Errorf("Connect lief nach der Löschung noch mit 200 durch: %s", rr.Body.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Connect-Handler hing")
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Connect hat den geloeschten Nutzerordner neu angelegt (Zombie)")
	}
}

// AC-10/AC-16, Link-Seite: ein Link-Request, der vor der Löschung eintrifft,
// darf den Nutzer erst UNTER telegramConnectMu laden. Sonst schreibt er nach
// der Kaskade noch einen Token fuer den geloeschten Nutzer auf die Platte.
func TestTelegramLink_LaedtNutzerErstUnterDemMutex(t *testing.T) {
	t.Setenv("TELEGRAM_BOT_USERNAME", "gregor_test_bot")
	s := telegramConnectTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	passwortKonto(t, s, "bert", "bert@beispiel.de")
	tsDir := t.TempDir()
	ts := NewTelegramTokenStore(tsDir)
	mustIssueToken(t, ts, "bert") // Datei existiert, fremder Token bleibt stehen

	telegramConnectMu.Lock()
	gesperrt := true
	t.Cleanup(func() {
		if gesperrt {
			telegramConnectMu.Unlock()
		}
	})

	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		req := httptest.NewRequest(http.MethodGet, "/api/auth/telegram-link", nil)
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), "anna"))
		rr := httptest.NewRecorder()
		GetTelegramLinkHandler(s, ts)(rr, req)
		done <- rr
	}()

	select {
	case rr := <-done:
		t.Fatalf("Link-Request lief trotz gehaltenem telegramConnectMu durch: %d %s", rr.Code, rr.Body.String())
	case <-time.After(200 * time.Millisecond): // steht am Mutex
	}

	if err := s.DeleteUser("anna"); err != nil { // die Löschung, die den Mutex haelt
		t.Fatalf("DeleteUser: %v", err)
	}
	telegramConnectMu.Unlock()
	gesperrt = false

	select {
	case rr := <-done:
		if rr.Code != http.StatusNotFound {
			t.Errorf("expected 404 fuer geloeschten Nutzer, got %d: %s", rr.Code, rr.Body.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Link-Handler hing")
	}
	platte := tokensVonPlatte(t, tsDir)
	if n := tokenAnzahlFuer(platte, "anna"); n != 0 {
		t.Errorf("telegram_tokens.json (Platte) enthaelt %d Token(s) des geloeschten Nutzers", n)
	}
	if n := tokenAnzahlFuer(platte, "bert"); n != 1 {
		t.Errorf("fremder Token von bert muss erhalten bleiben, gefunden: %d", n)
	}
}

// AC-10/AC-16, Link-Seite, zweite Haelfte: telegramConnectMu muss auch ueber
// IssueToken gehalten werden — ein Lock nur um LoadUser liesse die Kaskade
// zwischen Laden und Token-Schreiben durch. Der Test haelt ts.mu, damit der
// Request in IssueToken steht, und prueft, dass er den Mutex dabei haelt.
func TestTelegramLink_HaeltMutexUeberTokenAusgabe(t *testing.T) {
	t.Setenv("TELEGRAM_BOT_USERNAME", "gregor_test_bot")
	s := telegramConnectTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	ts := NewTelegramTokenStore(t.TempDir())

	ts.mu.Lock()
	tsGesperrt := true
	t.Cleanup(func() {
		if tsGesperrt {
			ts.mu.Unlock()
		}
	})

	done := make(chan *httptest.ResponseRecorder, 1)
	go func() {
		req := httptest.NewRequest(http.MethodGet, "/api/auth/telegram-link", nil)
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), "anna"))
		rr := httptest.NewRecorder()
		GetTelegramLinkHandler(s, ts)(rr, req)
		done <- rr
	}()
	time.Sleep(200 * time.Millisecond) // Request steht in IssueToken an ts.mu

	frei := telegramConnectMu.TryLock()
	if frei {
		telegramConnectMu.Unlock()
		t.Error("telegramConnectMu war frei, waehrend der Link-Request in IssueToken stand — Kaskade koennte dazwischen")
	}
	ts.mu.Unlock()
	tsGesperrt = false

	select {
	case rr := <-done:
		if rr.Code != http.StatusOK {
			t.Errorf("expected 200, got %d: %s", rr.Code, rr.Body.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Link-Handler hing")
	}
}

// AC-16, Gegenseite: die Löschung nimmt DENSELBEN Mutex. Haelt ihn jemand
// (z. B. ein laufender Connect), darf der Ordner nicht vorher verschwinden.
func TestKontoLoeschen_WartetAufTelegramConnectMutex(t *testing.T) {
	s := newTestStore(t)
	passwortKonto(t, s, "anna", "anna@beispiel.de")
	h := DeleteAccountHandler(s, NewTelegramTokenStore(t.TempDir()))

	telegramConnectMu.Lock()
	gesperrt := true
	t.Cleanup(func() {
		if gesperrt {
			telegramConnectMu.Unlock()
		}
	})
	done := make(chan *httptest.ResponseRecorder, 1)
	go func() { done <- postKontoLoeschen(h, "anna", `{"password":"`+loeschPasswort+`"}`) }()
	time.Sleep(300 * time.Millisecond)

	if !nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Löschung hat den Ordner entfernt, obwohl telegramConnectMu gehalten wurde")
	}
	telegramConnectMu.Unlock()
	gesperrt = false

	select {
	case w := <-done:
		if w.Code != 200 {
			t.Errorf("expected 200 nach Freigabe des Mutex, got %d: %s", w.Code, w.Body.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Löschung hing nach Freigabe des Mutex")
	}
	if nutzerOrdnerVorhanden(s, "anna") {
		t.Error("Konto muss nach Freigabe des Mutex geloescht sein")
	}
}

// --- AC-19: has_password im Profil ------------------------------------------------

func TestProfil_HasPasswordTrueFuerPasswortKontoFalseFuerPasswortloses_NieDerHash(t *testing.T) {
	s := newTestStore(t)
	mitPw := passwortKonto(t, s, "anna", "anna@beispiel.de")
	passwortlosKonto(t, s, "m-bbbb0001", "magic@beispiel.de")
	h := GetProfileHandler(s, map[string]struct{}{})

	holen := func(id string) (map[string]any, string) {
		req := httptest.NewRequest(http.MethodGet, "/api/auth/profile", nil)
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), id))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("%s: expected 200, got %d", id, w.Code)
		}
		var m map[string]any
		if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
			t.Fatalf("%s: kein JSON: %v", id, err)
		}
		return m, w.Body.String()
	}

	m, raw := holen("anna")
	if v, ok := m["has_password"]; !ok || v != true {
		t.Errorf("Passwort-Konto: has_password muss true sein, ist %v (vorhanden=%v)", v, ok)
	}
	if strings.Contains(raw, mitPw.PasswordHash) || strings.Contains(raw, "password_hash") {
		t.Errorf("Profil darf den Passwort-Hash nie ausliefern: %s", raw)
	}

	m, raw = holen("m-bbbb0001")
	if v, ok := m["has_password"]; !ok || v != false {
		t.Errorf("passwortloses Konto: has_password muss immer vorhanden und false sein, ist %v (vorhanden=%v)", v, ok)
	}
	if strings.Contains(raw, "password_hash") {
		t.Errorf("Profil darf password_hash nie ausliefern: %s", raw)
	}
}
