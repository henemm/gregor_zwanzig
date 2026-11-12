package handler

// Issue #2961 (GA1) — Haertung der Anmeldung per Einmal-Code.
// Spec: docs/specs/modules/security_haertung_2026_11_go_anmeldung.md (AC-1 bis AC-5).
//
// Echte Handler gegen einen echten Store in t.TempDir(); der Code wird ueber
// die Versand-Naht sendVerificationMailFn (Transportgrenze) mitgelesen bzw. aus
// dem paketprivaten Code-Speicher (otpCodeFor). Uhrzeit fuer die Sperrdauer
// ueber die Uhr-Naht der Fehlversuchsbremse.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/config"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/model"
)

var achtZiffern2961 = regexp.MustCompile(`^[0-9]{8}$`)

// codeMailZaehler2961 faengt jeden Versand an der Transportgrenze ab.
type codeMailZaehler2961 struct {
	mu    sync.Mutex
	mails []mail.Mail
	an    []string
	dran  chan struct{}
}

func neuerCodeMailZaehler2961(t *testing.T) *codeMailZaehler2961 {
	t.Helper()
	z := &codeMailZaehler2961{dran: make(chan struct{}, 64)}
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, m mail.Mail) error {
		z.mu.Lock()
		z.mails = append(z.mails, m)
		z.an = append(z.an, to)
		z.mu.Unlock()
		z.dran <- struct{}{}
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return z
}

// warteAuf wartet, bis n Mails eingegangen sind, und prueft danach, dass keine
// weitere folgt.
func (z *codeMailZaehler2961) warteAuf(t *testing.T, n int) []mail.Mail {
	t.Helper()
	for i := 0; i < n; i++ {
		select {
		case <-z.dran:
		case <-time.After(3 * time.Second):
			t.Fatalf("erwartet %d Mail(s), bekommen %d", n, i)
		}
	}
	select {
	case <-z.dran:
		t.Fatalf("erwartet genau %d Mail(s), es kam eine weitere", n)
	case <-time.After(150 * time.Millisecond):
	}
	z.mu.Lock()
	defer z.mu.Unlock()
	return append([]mail.Mail(nil), z.mails...)
}

func codeCfg2961() *config.Config {
	// SMTPHost gesetzt, damit der Versandweg laeuft; 127.0.0.1:1 erreicht nie
	// ein echtes Netz (die Naht faengt vorher ab).
	return &config.Config{SessionSecret: "test-secret-32-chars-minimum-ok!", SMTPHost: "127.0.0.1", SMTPPort: 1}
}

func codeAnfordern2961(t *testing.T, h http.Handler, email string) {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link", strings.NewReader(`{"email":"`+email+`"}`))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusOK || !strings.Contains(w.Body.String(), `"ok"`) {
		t.Fatalf("Anforderung: erwartet neutrale 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

func fehlerCode2961(w *httptest.ResponseRecorder) string {
	var body map[string]any
	_ = json.Unmarshal(w.Body.Bytes(), &body)
	s, _ := body["code"].(string)
	return s
}

// AC-4: Der Code hat acht Ziffern, wird in der Mail zugestellt und ist
// einloesbar.
func TestAnmeldeCode_HatAchtZiffernUndStehtInDerMail(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	z := neuerCodeMailZaehler2961(t)
	s := newTestStore(t)
	cfg := codeCfg2961()
	h := MagicLinkRequestHandler(s, cfg)

	codeAnfordern2961(t, h, "acht@beispiel.de")
	code := otpCodeFor(t, "acht@beispiel.de")
	if !achtZiffern2961.MatchString(code) {
		t.Fatalf("Code muss genau 8 Ziffern haben, ist %q", code)
	}
	mails := z.warteAuf(t, 1)
	if !strings.Contains(mails[0].PlainBody, code) || !strings.Contains(mails[0].HTMLBody, code) {
		t.Fatalf("Mail muss den Code %q tragen", code)
	}
	if w := einloesen(s, cfg, "acht@beispiel.de", code); w.Code != http.StatusOK {
		t.Fatalf("Einloesen des 8-stelligen Codes: erwartet 200, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-3: Eine erneute Anforderung entwertet einen noch gueltigen Code nicht —
// derselbe Code wird erneut zugestellt, der Ablauf bleibt stehen.
func TestAnmeldeCode_NeuanforderungStelltDenselbenCodeErneutZu(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	z := neuerCodeMailZaehler2961(t)
	s := newTestStore(t)
	cfg := codeCfg2961()
	h := MagicLinkRequestHandler(s, cfg)
	const adresse = "laufend@beispiel.de"

	codeAnfordern2961(t, h, adresse)
	erster := otpCodeFor(t, adresse)
	v, _ := otpStore.Load(adresse)
	ablaufVorher := v.(*otpEntry).expiresAt

	codeAnfordern2961(t, h, adresse)
	if zweiter := otpCodeFor(t, adresse); zweiter != erster {
		t.Fatalf("Neuanforderung hat den laufenden Code ersetzt: %q -> %q", erster, zweiter)
	}
	v, _ = otpStore.Load(adresse)
	if !v.(*otpEntry).expiresAt.Equal(ablaufVorher) {
		t.Errorf("Ablauf darf sich durch die Neuanforderung nicht verschieben")
	}
	mails := z.warteAuf(t, 2)
	for i, m := range mails {
		if !strings.Contains(m.PlainBody, erster) {
			t.Errorf("Mail %d traegt nicht den laufenden Code %q", i+1, erster)
		}
	}
	if w := einloesen(s, cfg, adresse, erster); w.Code != http.StatusOK {
		t.Fatalf("der urspruengliche Code muss gueltig bleiben, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-1: Fehlversuche zaehlen je Adresse und ueberleben eine Neuanforderung.
// Nach fuenf Fehlversuchen wird auch der richtige Code neutral abgelehnt; nach
// Ablauf der Sperrfrist geht es wieder.
func TestAnmeldeCode_FehlversuchsSperreJeAdresseUeberlebtNeuanforderung(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	jetzt := time.Now()
	magicFailGuard.setNow(func() time.Time { return jetzt })
	s := newTestStore(t)
	if err := s.SaveUser(model.User{ID: "sperre1", Email: "sperre@beispiel.de", CreatedAt: time.Now()}); err != nil {
		t.Fatal(err)
	}
	cfg := &config.Config{SessionSecret: "test-secret-32-chars-minimum-ok!"}
	h := MagicLinkRequestHandler(s, cfg)
	const adresse = "sperre@beispiel.de"

	codeAnfordern2961(t, h, adresse)
	richtig := otpCodeFor(t, adresse)
	falsch := "00000000"
	if falsch == richtig {
		falsch = "11111111"
	}
	for i := 0; i < 3; i++ {
		einloesen(s, cfg, adresse, falsch)
	}
	// Der erste Code ist nach drei Fehlversuchen verbraucht; eine neue
	// Anforderung liefert einen frischen — der Adresszaehler laeuft weiter.
	codeAnfordern2961(t, h, adresse)
	richtig = otpCodeFor(t, adresse)
	for i := 0; i < 2; i++ {
		if w := einloesen(s, cfg, adresse, falsch); fehlerCode2961(w) != "invalid_or_expired_code" {
			t.Fatalf("Fehlversuch %d: erwartet invalid_or_expired_code, bekommen %d %s", 4+i, w.Code, w.Body.String())
		}
	}
	w := einloesen(s, cfg, adresse, richtig)
	if w.Code != http.StatusBadRequest || fehlerCode2961(w) != "invalid_or_expired_code" {
		t.Fatalf("in der Sperre muss auch der richtige Code neutral abgelehnt werden, bekommen %d: %s", w.Code, w.Body.String())
	}
	for _, c := range w.Result().Cookies() {
		if c.Name == "gz_session" && c.Value != "" {
			t.Fatal("in der Sperre darf keine Sitzung entstehen")
		}
	}

	// Nach 15 Minuten ist die Sperre vorbei.
	jetzt = jetzt.Add(15*time.Minute + time.Second)
	codeAnfordern2961(t, h, adresse)
	richtig = otpCodeFor(t, adresse)
	if w := einloesen(s, cfg, adresse, richtig); w.Code != http.StatusOK {
		t.Fatalf("nach Ablauf der Sperre muss der richtige Code wieder gelten, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-1 (Gegenprobe Mandanten): die Sperre einer Adresse beruehrt eine andere
// Adresse nicht.
func TestAnmeldeCode_SperreTrifftNurDieBetroffeneAdresse(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	s := newTestStore(t)
	cfg := &config.Config{SessionSecret: "test-secret-32-chars-minimum-ok!"}
	h := MagicLinkRequestHandler(s, cfg)

	codeAnfordern2961(t, h, "opfer@beispiel.de")
	for i := 0; i < 2; i++ {
		for j := 0; j < 3; j++ {
			einloesen(s, cfg, "opfer@beispiel.de", "99999999")
		}
		codeAnfordern2961(t, h, "opfer@beispiel.de")
	}
	codeAnfordern2961(t, h, "andere@beispiel.de")
	if w := einloesen(s, cfg, "andere@beispiel.de", otpCodeFor(t, "andere@beispiel.de")); w.Code != http.StatusOK {
		t.Fatalf("eine fremde Adresse darf nicht mitgesperrt sein, bekommen %d: %s", w.Code, w.Body.String())
	}
}

// AC-1: viele gleichzeitige Fehlversuche fuehren hoechstens zu fuenf
// Vergleichen je Adresse — der Zaehler wird vor dem Vergleich erhoeht.
func TestAnmeldeCode_GleichzeitigeFehlversucheZaehlenVorDemVergleich(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	s := newTestStore(t)
	cfg := &config.Config{SessionSecret: "test-secret-32-chars-minimum-ok!"}
	const adresse = "parallel@beispiel.de"
	otpStore.Store(adresse, &otpEntry{code: "12345678", expiresAt: time.Now().Add(15 * time.Minute)})

	var wg sync.WaitGroup
	for i := 0; i < 40; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			einloesen(s, cfg, adresse, "87654321")
		}()
	}
	wg.Wait()
	if n := magicFailGuard.count(adresse); n > 5 {
		t.Fatalf("hoechstens 5 gezaehlte Versuche je Adresse erwartet, gezaehlt %d", n)
	}
	v, _ := otpStore.Load(adresse)
	if e := v.(*otpEntry); e.attempts > 3 {
		// Je Code hoechstens drei Vergleiche; jeder weitere Zugriff wird vor
		// dem Vergleich abgewiesen.
		t.Fatalf("Code-Eintrag zeigt %d Vergleiche, erwartet hoechstens 3", e.attempts)
	}
}

// AC-2: hoechstens fuenf Code-Anforderungen je Adresse und Stunde; darueber
// bleibt die Antwort neutral, es geht aber keine Mail mehr hinaus. Eine
// andere Adresse ist davon unberuehrt.
func TestAnmeldeCode_AnforderungsBremseJeAdresse(t *testing.T) {
	t.Cleanup(ResetOTPStoreForTest)
	ResetOTPStoreForTest()
	z := neuerCodeMailZaehler2961(t)
	s := newTestStore(t)
	h := MagicLinkRequestHandler(s, codeCfg2961())

	for i := 0; i < 7; i++ {
		codeAnfordern2961(t, h, "flut@beispiel.de")
	}
	z.warteAuf(t, 5)
	codeAnfordern2961(t, h, "frei@beispiel.de")
	z.warteAuf(t, 1)
	z.mu.Lock()
	defer z.mu.Unlock()
	if letzte := z.an[len(z.an)-1]; letzte != "frei@beispiel.de" {
		t.Fatalf("letzte Mail ging an %q, erwartet frei@beispiel.de", letzte)
	}
}
