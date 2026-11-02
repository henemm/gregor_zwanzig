package handler

// Issue #2678 (i18n G4) — Konto-Mails in der Sprache des Empfaengers.
// Spec: docs/specs/modules/i18n_g4_go_mails_2678.md — AC-1 bis AC-6.
//
// Keine Mocks: echte Handler (Registrierung, Passwort vergessen, Einmalcode,
// Loesch-Code, Level-Antrag) auf echtem Store in t.TempDir(); abgefangen wird
// nur die fertige Mail an den bestehenden Versand-Nahten. Jeder Pfad laeuft
// mit zwei Nutzern verschiedener Sprache.

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"sync"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"

	"github.com/henemm/gregor-api/internal/i18n"
	"github.com/henemm/gregor-api/internal/mail"
	"github.com/henemm/gregor-api/internal/middleware"
	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

type kmsVersand struct {
	to  string
	msg mail.Mail
}

// kmsFangeVerifikation faengt die Naht sendVerificationMailFn (Bestaetigung,
// Einmalcode, Loesch-Code, Google-Hinweis).
func kmsFangeVerifikation(t *testing.T) chan kmsVersand {
	t.Helper()
	ch := make(chan kmsVersand, 8)
	orig := sendVerificationMailFn
	sendVerificationMailFn = func(_ mail.MailConfig, to string, msg mail.Mail) error {
		ch <- kmsVersand{to: to, msg: msg}
		return nil
	}
	t.Cleanup(func() { sendVerificationMailFn = orig })
	return ch
}

// kmsSammle wartet auf n Mails und ordnet sie nach Empfaenger.
func kmsSammle(t *testing.T, ch chan kmsVersand, n int) map[string]mail.Mail {
	t.Helper()
	out := map[string]mail.Mail{}
	for len(out) < n {
		select {
		case v := <-ch:
			if _, doppelt := out[v.to]; doppelt {
				t.Fatalf("zweite Mail an %s", v.to)
			}
			out[v.to] = v.msg
		case <-time.After(3 * time.Second):
			t.Fatalf("nur %d von %d Mails abgefangen: %v", len(out), n, out)
		}
	}
	return out
}

var (
	kmsUmlaut     = regexp.MustCompile(`[äöüÄÖÜß]|&(auml|ouml|uuml|Auml|Ouml|Uuml|szlig|bdquo);`)
	kmsSignalwort = regexp.MustCompile(`(?i)\b(hallo|bitte|ignoriere|nicht|fehlt|bestaetig\w*|zurueck\w*|dein\w*|du|und|oder|gueltig|gültig|einmalcode|anmelde\w*|konto|loesch\w*|lösch\w*)\b`)
	kmsLink       = regexp.MustCompile(`https://\S+\?user=([^&\s]+)&token=([0-9a-f]+)`)
)

func kmsPruefeEnglisch(t *testing.T, wo string, m mail.Mail) {
	t.Helper()
	text := m.Subject + "\n" + m.PlainBody + "\n" + m.HTMLBody
	if f := kmsUmlaut.FindString(text); f != "" {
		t.Errorf("%s: englische Mail enthaelt %q:\n%s", wo, f, text)
	}
	if f := kmsSignalwort.FindString(text); f != "" {
		t.Errorf("%s: englische Mail enthaelt deutsches Signalwort %q:\n%s", wo, f, text)
	}
	if m.Lang != i18n.En {
		t.Errorf("%s: Mail.Lang=%q, erwartet en", wo, m.Lang)
	}
}

func kmsGleich(t *testing.T, wo string, got, want mail.Mail) {
	t.Helper()
	if got.Subject != want.Subject || got.PlainBody != want.PlainBody || got.HTMLBody != want.HTMLBody || got.Lang != want.Lang {
		t.Errorf("%s: Mail weicht ab:\n--- got\n%+v\n--- want\n%+v", wo, got, want)
	}
}

func kmsLinkTeile(t *testing.T, wo, plain string) (user, token string) {
	t.Helper()
	m := kmsLink.FindStringSubmatch(plain)
	if m == nil {
		t.Fatalf("%s: kein Link im Klartext:\n%s", wo, plain)
	}
	u, _ := url.QueryUnescape(m[1])
	return u, m[2]
}

func kmsRegistriere(t *testing.T, h http.Handler, email, sprache string) string {
	t.Helper()
	body := `{"email":"` + email + `","password":"geheim-12345"`
	if sprache != "" {
		body += `,"language":"` + sprache + `"`
	}
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", strings.NewReader(body+"}"))
	w := httptest.NewRecorder()
	h.ServeHTTP(w, req)
	if w.Code != http.StatusCreated {
		t.Fatalf("Registrierung %s: Status %d: %s", email, w.Code, w.Body.String())
	}
	var resp map[string]string
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	return resp["id"]
}

// AC-1 + AC-2: Registrierung en -> englische Bestaetigung, de und ohne
// Sprache -> heutige deutsche Mail; Link und Empfaenger je Nutzer.
func TestRegistrierungBestaetigungsMailInNutzersprache(t *testing.T) {
	s := newTestStore(t)
	ch := kmsFangeVerifikation(t)
	cfg := testRegisterCfg()
	h := middleware.Lang(s)(RegisterHandlerWithInvites(s, 4, cfg, store.NewInviteStore(t.TempDir())))
	ids := map[string]string{
		"anna-en@example.com": kmsRegistriere(t, h, "anna-en@example.com", "en"),
		"bert-de@example.com": kmsRegistriere(t, h, "bert-de@example.com", "de"),
		"cora-xx@example.com": kmsRegistriere(t, h, "cora-xx@example.com", ""),
	}
	mails := kmsSammle(t, ch, 3)
	for to, m := range mails {
		uid, token := kmsLinkTeile(t, "AC-1 "+to, m.PlainBody)
		if uid != ids[to] {
			t.Errorf("AC-1: Mail an %s traegt Link fuer %q, erwartet %q", to, uid, ids[to])
		}
		if to == "anna-en@example.com" {
			if m.Subject != "Confirm your email address for Gregor 20" {
				t.Errorf("AC-1: Betreff %q", m.Subject)
			}
			link := cfg.PublicHost + "/verify-email?user=" + url.QueryEscape(uid) + "&token=" + token
			if !strings.Contains(m.PlainBody, "\n\n"+link+"\n\n") || !strings.Contains(m.HTMLBody, `href="`+link+`"`) {
				t.Errorf("AC-1: Link %s nicht unveraendert in Klartext/HTML", link)
			}
			kmsPruefeEnglisch(t, "AC-1", m)
			continue
		}
		kmsGleich(t, "AC-2 "+to, m, mail.BuildVerificationMail(i18n.De, cfg.PublicHost, uid, token))
	}
}

// AC-4: zwei Nutzer (en/de) loesen gleichzeitig "Passwort vergessen" aus.
func TestPasswortVergessenZweiNutzerParallelOhneVermischung(t *testing.T) {
	s := newTestStore(t)
	hash, _ := bcrypt.GenerateFromPassword([]byte("altes-passwort-1"), bcrypt.MinCost)
	for _, u := range []model.User{
		{ID: "anna-en", Email: "anna@example.com", MailTo: "anna@example.com", Language: "en"},
		{ID: "bert-de", Email: "bert@example.com", MailTo: "bert@example.com", Language: "de"},
	} {
		u.PasswordHash, u.CreatedAt = string(hash), time.Now()
		if err := s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}
	ch := make(chan kmsVersand, 4)
	orig := sendResetMailFn
	sendResetMailFn = func(_, _ mail.MailConfig, to string, msg mail.Mail) error {
		ch <- kmsVersand{to: to, msg: msg}
		return nil
	}
	t.Cleanup(func() { sendResetMailFn = orig })
	cfg := testRegisterCfg()
	h := ForgotPasswordHandler(s, bcrypt.MinCost, cfg)
	var wg sync.WaitGroup
	for _, id := range []string{"anna-en", "bert-de"} {
		wg.Add(1)
		go func(id string) {
			defer wg.Done()
			// Anfragesprache absichtlich gegenlaeufig: es zaehlt der Empfaenger.
			req := httptest.NewRequest(http.MethodPost, "/api/auth/forgot-password", strings.NewReader(`{"username":"`+id+`"}`))
			if id == "anna-en" {
				req = req.WithContext(i18n.WithLang(req.Context(), i18n.De))
			} else {
				req = req.WithContext(i18n.WithLang(req.Context(), i18n.En))
			}
			h.ServeHTTP(httptest.NewRecorder(), req)
		}(id)
	}
	wg.Wait()
	mails := kmsSammle(t, ch, 2)
	a, b := mails["anna@example.com"], mails["bert@example.com"]
	if a.Subject != "Gregor 20 — Reset your password" || !strings.Contains(a.PlainBody, "You requested a password reset for Gregor 20.") {
		t.Errorf("AC-4: Mail an A nicht englisch: %q\n%s", a.Subject, a.PlainBody)
	}
	if uid, _ := kmsLinkTeile(t, "AC-4 A", a.PlainBody); uid != "anna-en" {
		t.Errorf("AC-4: Mail an A traegt Link fuer %q", uid)
	}
	kmsPruefeEnglisch(t, "AC-4 A", a)
	uid, token := kmsLinkTeile(t, "AC-4 B", b.PlainBody)
	if uid != "bert-de" {
		t.Errorf("AC-4: Mail an B traegt Link fuer %q", uid)
	}
	kmsGleich(t, "AC-4 B", b, mail.BuildResetMail(i18n.De, cfg.PublicHost, "bert-de", token))
}

// AC-5: Einmalcode ohne Konto in der Anfragesprache (echte Lang-Middleware).
func TestEinmalcodeInAnfragesprache(t *testing.T) {
	s := newTestStore(t)
	ch := kmsFangeVerifikation(t)
	cfg := testRegisterCfg()
	h := middleware.Lang(s)(MagicLinkRequestHandler(s, &cfg))
	for email, accept := range map[string]string{"g4-magic-en@example.com": "en-US,en;q=0.9", "g4-magic-de@example.com": ""} {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/magic-link/request", strings.NewReader(`{"email":"`+email+`"}`))
		if accept != "" {
			req.Header.Set("Accept-Language", accept)
		}
		h.ServeHTTP(httptest.NewRecorder(), req)
	}
	mails := kmsSammle(t, ch, 2)
	code := func(email string) string {
		v, ok := otpStore.Load(email)
		if !ok {
			t.Fatalf("AC-5: kein Code fuer %s gespeichert", email)
		}
		return v.(*otpEntry).code
	}
	en := mails["g4-magic-en@example.com"]
	if en.Subject != "Gregor 20 — Your one-time code" || !strings.Contains(en.PlainBody, "Your one-time code for Gregor 20: "+code("g4-magic-en@example.com")) {
		t.Errorf("AC-5: Einmalcode-Mail nicht englisch oder ohne Code: %q\n%s", en.Subject, en.PlainBody)
	}
	kmsPruefeEnglisch(t, "AC-5", en)
	kmsGleich(t, "AC-5 de", mails["g4-magic-de@example.com"], mail.BuildMagicLinkMail(i18n.De, code("g4-magic-de@example.com")))
}

// AC-6: Loesch-Code je Nutzersprache, Code unveraendert im Text.
func TestLoeschCodeMailInNutzersprache(t *testing.T) {
	s := newTestStore(t)
	for _, u := range []model.User{
		{ID: "loe-en", Email: "loe-en@example.com", Language: "en"},
		{ID: "loe-de", Email: "loe-de@example.com"},
	} {
		if err := s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}
	ch := kmsFangeVerifikation(t)
	h := RequestDeleteCodeHandler(s, mailKonfig(), NewMailFloodLimiter(10, time.Hour))
	for _, id := range []string{"loe-en", "loe-de"} {
		// Anfragesprache gegenlaeufig: es zaehlt die gespeicherte Nutzersprache.
		req := httptest.NewRequest(http.MethodPost, "/api/auth/account/delete-code", strings.NewReader(`{}`))
		ctx := middleware.ContextWithUserID(req.Context(), id)
		if id == "loe-de" {
			ctx = i18n.WithLang(ctx, i18n.En)
		}
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req.WithContext(ctx))
		if w.Code != http.StatusOK {
			t.Fatalf("AC-6: Loesch-Code %s: Status %d: %s", id, w.Code, w.Body.String())
		}
	}
	mails := kmsSammle(t, ch, 2)
	code := func(id string) string {
		v, ok := deleteCodeStore.Load(id)
		if !ok {
			t.Fatalf("AC-6: kein Loesch-Code fuer %s", id)
		}
		return v.(*deleteCodeEntry).code
	}
	en := mails["loe-en@example.com"]
	if en.Subject != "Gregor 20 — Your deletion code" || !strings.Contains(en.PlainBody, "Your deletion code for Gregor 20: "+code("loe-en")) ||
		!strings.Contains(en.HTMLBody, ">"+code("loe-en")+"</p>") {
		t.Errorf("AC-6: Loesch-Code-Mail nicht englisch oder ohne Code: %q\n%s\n%s", en.Subject, en.PlainBody, en.HTMLBody)
	}
	kmsPruefeEnglisch(t, "AC-6 Loesch-Code", en)
	kmsGleich(t, "AC-6 de", mails["loe-de@example.com"], buildDeleteCodeMail(i18n.De, code("loe-de")))
}

// AC-6: Google-Hinweis je Nutzersprache ueber den echten Versandweg.
func TestGoogleHinweisMailInNutzersprache(t *testing.T) {
	ch := kmsFangeVerifikation(t)
	cfg := mailKonfig()
	sendGoogleLinkNotice(cfg, &model.User{ID: "goo-en", Email: "goo-en@example.com", Language: "en"}, "goo-en@example.com")
	sendGoogleLinkNotice(cfg, &model.User{ID: "goo-de", Email: "goo-de@example.com"}, "goo-de@example.com")
	mails := kmsSammle(t, ch, 2)
	en := mails["goo-en@example.com"]
	if en.Subject != "Google sign-in linked to your Gregor 20 account" {
		t.Errorf("AC-6: Google-Hinweis Betreff %q", en.Subject)
	}
	kmsPruefeEnglisch(t, "AC-6 Google-Hinweis", en)
	kmsGleich(t, "AC-6 Google de", mails["goo-de@example.com"], buildGoogleLinkNoticeMail(i18n.De))
}

// AC-3: Nutzer mit en beantragt ein Level -> Betreiber-Mail bleibt deutsch.
func TestLevelAntragBetreiberMailBleibtDeutsch(t *testing.T) {
	s := newTestStore(t)
	for _, u := range []model.User{{ID: "tier-en", Tier: "free", Language: "en"}, {ID: "tier-de", Tier: "free", Language: "de"}} {
		if err := s.SaveUser(u); err != nil {
			t.Fatal(err)
		}
	}
	var mu sync.Mutex
	var gesendet []kmsVersand
	withTierMailFn(t, func(_, _ mail.MailConfig, to string, msg mail.Mail) error {
		mu.Lock()
		defer mu.Unlock()
		gesendet = append(gesendet, kmsVersand{to: to, msg: msg})
		return nil
	})
	cfg := fullMailCfg()
	h := middleware.Lang(s)(RequestTierChangeHandler(s, cfg))
	for _, id := range []string{"tier-en", "tier-de"} {
		req := httptest.NewRequest(http.MethodPost, "/api/auth/tier-change-request", bytes.NewReader([]byte(`{"requested_tier":"premium"}`)))
		req.Header.Set("Accept-Language", "en")
		req = req.WithContext(middleware.ContextWithUserID(req.Context(), id))
		w := httptest.NewRecorder()
		h.ServeHTTP(w, req)
		if got := strings.TrimSpace(w.Body.String()); got != `{"po_notified":true,"status":"ok"}` {
			t.Errorf("AC-3 %s: Antwort %s", id, got)
		}
	}
	if len(gesendet) != 2 {
		t.Fatalf("AC-3: %d Mails, erwartet 2 (nur an den Betreiber)", len(gesendet))
	}
	for i, id := range []string{"tier-en", "tier-de"} {
		v := gesendet[i]
		if v.to != cfg.PoEmail {
			t.Errorf("AC-3: Mail an %q statt an den Betreiber", v.to)
		}
		if v.msg.Subject != "Gregor 20 — Level-Wechsel-Antrag von "+id || v.msg.Lang != i18n.De ||
			!strings.HasPrefix(v.msg.PlainBody, "Ein Nutzer hat einen Level-Wechsel beantragt.") {
			t.Errorf("AC-3 %s: Betreiber-Mail nicht deutsch: %q Lang=%q", id, v.msg.Subject, v.msg.Lang)
		}
	}
}

func kmsGolden(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", "golden", name))
	if err != nil {
		t.Fatalf("Golden %s fehlt: %v", name, err)
	}
	return string(b)
}

// AC-2 (Golden, vor der Umstellung erzeugt) und en-Golden als Review-Hilfe.
func TestHandlerMailsGleichGolden(t *testing.T) {
	faelle := map[string]func(i18n.Lang) mail.Mail{
		"delete_code": func(l i18n.Lang) mail.Mail { return buildDeleteCodeMail(l, "123456") },
		"google_link": buildGoogleLinkNoticeMail,
	}
	for art, bau := range faelle {
		for fall, lang := range map[string]i18n.Lang{"de": i18n.De, "": i18n.Parse(""), "en": i18n.En} {
			name := art + ".de"
			if fall == "en" {
				name = art + ".en"
			}
			m := bau(lang)
			if txt := "Subject: " + m.Subject + "\n\n" + m.PlainBody; txt != kmsGolden(t, name+".txt") {
				t.Errorf("AC-2 %s/%q: Betreff/Klartext weicht vom Golden ab:\n%s", art, fall, txt)
			}
			if m.HTMLBody != kmsGolden(t, name+".html") {
				t.Errorf("AC-2 %s/%q: HTML weicht vom Golden ab:\n%s", art, fall, m.HTMLBody)
			}
		}
	}
}

func kmsKatalog(t *testing.T, lang string) map[string]string {
	t.Helper()
	_, self, _, _ := runtime.Caller(0)
	raw, err := os.ReadFile(filepath.Join(filepath.Dir(self), "..", "i18n", "messages", lang, "mail.json"))
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]string
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}

var kmsPlatzhalter = regexp.MustCompile(`\{[a-z0-9_]+\}`)

// AC-7: jeder Katalogschluessel der zwei Handler-Mails wirkt in der Mail,
// kein gelesener Schluessel fehlt.
func TestHandlerMailsKatalogSchluessel(t *testing.T) {
	mindest := map[string]int{"delete": 10, "google_link": 7}
	for _, lang := range []i18n.Lang{i18n.De, i18n.En} {
		kat := kmsKatalog(t, string(lang))
		for art, m := range map[string]mail.Mail{"delete": buildDeleteCodeMail(lang, "123456"), "google_link": buildGoogleLinkNoticeMail(lang)} {
			gesamt := m.Subject + "\n" + m.PlainBody + "\n" + m.HTMLBody
			if strings.Contains(gesamt, "mail."+art+".") {
				t.Errorf("AC-7 %s/%s: unaufgeloester Schluessel:\n%s", art, lang, gesamt)
			}
			n := 0
			for k, v := range kat {
				if !strings.HasPrefix(k, "mail."+art+".") {
					continue
				}
				n++
				for _, stueck := range kmsPlatzhalter.Split(v, -1) {
					if stueck != "" && !strings.Contains(gesamt, stueck) {
						t.Errorf("AC-7 %s/%s: Schluessel %s (%q) wirkt nicht", art, lang, k, stueck)
					}
				}
			}
			if n < mindest[art] {
				t.Errorf("AC-7 %s/%s: nur %d Schluessel, erwartet %d", art, lang, n, mindest[art])
			}
		}
	}
}
