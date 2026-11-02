package mail

// Issue #2678 (i18n G4) — Konto-Mails der Go-API zweisprachig.
// Spec: docs/specs/modules/i18n_g4_go_mails_2678.md — AC-1 (Header),
// AC-2 (Golden de), AC-6 (Katalog en), AC-7 (Schluessel je Mail-Art).
//
// Keine Mocks: echte Builder, echter eingebetteter Katalog, echter
// MIME-Aufbau (buildPayload) ueber net/mail gelesen. Die Golden-Dateien
// testdata/golden/*.de.* wurden VOR der Umstellung aus den damaligen
// Buildern erzeugt.

import (
	"encoding/json"
	"net/mail"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"testing"

	"github.com/henemm/gregor-api/internal/i18n"
)

const (
	gHost  = "https://example.invalid"
	gUser  = "golden-de"
	gToken = "tok123"
	gCode  = "123456"
)

func kmBuild(art string, lang i18n.Lang) Mail {
	switch art {
	case "verify":
		return BuildVerificationMail(lang, gHost, gUser, gToken)
	case "reset":
		return BuildResetMail(lang, gHost, gUser, gToken)
	case "magic":
		return BuildMagicLinkMail(lang, gCode)
	}
	panic("unbekannte Mail-Art " + art)
}

func kmGolden(t *testing.T, name string) string {
	t.Helper()
	b, err := os.ReadFile(filepath.Join("testdata", "golden", name))
	if err != nil {
		t.Fatalf("Golden %s fehlt: %v", name, err)
	}
	return string(b)
}

func kmVergleiche(t *testing.T, ac, fall, golden string, m Mail) {
	t.Helper()
	txt := "Subject: " + m.Subject + "\n\n" + m.PlainBody
	if want := kmGolden(t, golden+".txt"); txt != want {
		t.Errorf("%s %s: Betreff/Klartext weicht vom Golden %s.txt ab:\n--- got\n%s\n--- want\n%s", ac, fall, golden, txt, want)
	}
	if want := kmGolden(t, golden+".html"); m.HTMLBody != want {
		t.Errorf("%s %s: HTML weicht vom Golden %s.html ab:\n--- got\n%s\n--- want\n%s", ac, fall, golden, m.HTMLBody, want)
	}
}

// AC-2: Sprache de und "keine Sprache" (Parse("")) liefern die heutige Mail.
func TestKontoMailsDeutschByteGleichZumGolden(t *testing.T) {
	for _, art := range []string{"verify", "reset", "magic"} {
		for fall, lang := range map[string]i18n.Lang{"de": i18n.De, "ohne Sprache": i18n.Parse("")} {
			m := kmBuild(art, lang)
			kmVergleiche(t, "AC-2", art+"/"+fall, art+".de", m)
			if m.Lang != i18n.De {
				t.Errorf("AC-2 %s/%s: Mail.Lang=%q, erwartet de", art, fall, m.Lang)
			}
		}
	}
}

// Review-Hilfe und Regressionsschutz der englischen Fassung.
func TestKontoMailsEnglischGleichGolden(t *testing.T) {
	for _, art := range []string{"verify", "reset", "magic"} {
		m := kmBuild(art, i18n.En)
		kmVergleiche(t, "AC-1", art+"/en", art+".en", m)
		if m.Lang != i18n.En {
			t.Errorf("%s/en: Mail.Lang=%q, erwartet en", art, m.Lang)
		}
	}
}

// AC-1: englische Betreffs und unveraenderte Links/Codes.
func TestKontoMailsEnglischBetreffUndLink(t *testing.T) {
	link := func(pfad string) string { return gHost + pfad + "?user=" + gUser + "&token=" + gToken }
	faelle := []struct{ art, betreff, nutzlast string }{
		{"verify", "Confirm your email address for Gregor 20", link("/verify-email")},
		{"reset", "Gregor 20 — Reset your password", link("/reset-password")},
		{"magic", "Gregor 20 — Your one-time code", gCode},
	}
	for _, f := range faelle {
		m := kmBuild(f.art, i18n.En)
		if m.Subject != f.betreff {
			t.Errorf("AC-1 %s: Betreff %q, erwartet %q", f.art, m.Subject, f.betreff)
		}
		if !strings.Contains(m.PlainBody, f.nutzlast) || !strings.Contains(m.HTMLBody, f.nutzlast) {
			t.Errorf("AC-1 %s: %q fehlt in Klartext oder HTML", f.art, f.nutzlast)
		}
		kmPruefeEnglisch(t, "AC-1 "+f.art, m.Subject+"\n"+m.PlainBody+"\n"+m.HTMLBody)
	}
}

var (
	kmUmlaut     = regexp.MustCompile(`[äöüÄÖÜß]|&(auml|ouml|uuml|Auml|Ouml|Uuml|szlig|bdquo);`)
	kmSignalwort = regexp.MustCompile(`(?i)\b(hallo|bitte|ignoriere|nicht|fehlt|bestaetig\w*|zurueck\w*|dein\w*|du|und|oder|gueltig|gültig|einmalcode|anmelde\w*|konto)\b`)
)

func kmPruefeEnglisch(t *testing.T, wo, text string) {
	t.Helper()
	if m := kmUmlaut.FindString(text); m != "" {
		t.Errorf("%s: englischer Text enthaelt %q:\n%s", wo, m, text)
	}
	if m := kmSignalwort.FindString(text); m != "" {
		t.Errorf("%s: englischer Text enthaelt deutsches Signalwort %q:\n%s", wo, m, text)
	}
}

func kmKatalog(t *testing.T, lang string) map[string]string {
	t.Helper()
	_, self, _, _ := runtime.Caller(0)
	p := filepath.Join(filepath.Dir(self), "..", "i18n", "messages", lang, "mail.json")
	raw, err := os.ReadFile(p)
	if err != nil {
		t.Fatalf("Katalog %s: %v", p, err)
	}
	var m map[string]string
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatalf("Katalog %s: %v", p, err)
	}
	return m
}

// AC-6: alle englischen mail.*-Werte ohne Umlaute, Umlaut-Entities und
// deutsche Signalwoerter.
func TestMailKatalogEnglischOhneDeutsch(t *testing.T) {
	en := kmKatalog(t, "en")
	if len(en) < 40 {
		t.Fatalf("AC-6: en/mail.json hat nur %d Schluessel (Messaufbau leer?)", len(en))
	}
	for k, v := range en {
		kmPruefeEnglisch(t, "AC-6 "+k, v)
	}
}

var kmPlatzhalter = regexp.MustCompile(`\{[a-z0-9_]+\}`)

// kmAbdeckung prueft, dass jeder Katalogschluessel der Mail-Art in der
// gebauten Mail wirkt (jedes Textstueck zwischen Platzhaltern steht drin, der
// Betreff exakt) und dass der Code keinen fehlenden Schluessel liest (T
// liefert dann den Schluessel selbst zurueck).
func kmAbdeckung(t *testing.T, art string, kat map[string]string, m Mail, mindest int) {
	t.Helper()
	gesamt := m.Subject + "\n" + m.PlainBody + "\n" + m.HTMLBody
	if strings.Contains(gesamt, "mail."+art+".") {
		t.Errorf("AC-7 %s: Mail enthaelt einen unaufgeloesten Schluessel:\n%s", art, gesamt)
	}
	n := 0
	for k, v := range kat {
		if !strings.HasPrefix(k, "mail."+art+".") {
			continue
		}
		n++
		if k == "mail."+art+".betreff" {
			if m.Subject != v {
				t.Errorf("AC-7 %s: Betreff %q != Katalog %q", art, m.Subject, v)
			}
			continue
		}
		for _, stueck := range kmPlatzhalter.Split(v, -1) {
			if stueck != "" && !strings.Contains(gesamt, stueck) {
				t.Errorf("AC-7 %s: Schluessel %s (%q) wirkt nicht in der Mail", art, k, stueck)
			}
		}
	}
	if n < mindest {
		t.Errorf("AC-7 %s: nur %d Schluessel im Katalog, erwartet mindestens %d", art, n, mindest)
	}
}

// AC-7: jede Mail-Art liest genau die vorhandenen Schluessel, in beiden Sprachen.
func TestMailKatalogSchluesselJeMailArt(t *testing.T) {
	mindest := map[string]int{"verify": 11, "reset": 11, "magic": 11}
	for _, lang := range []i18n.Lang{i18n.De, i18n.En} {
		kat := kmKatalog(t, string(lang))
		for _, art := range []string{"verify", "reset", "magic"} {
			kmAbdeckung(t, art+"/"+string(lang), kat, kmBuild(art, lang), mindest[art])
		}
	}
}

// AC-1/AC-2: der MIME-Aufbau traegt X-GZ-Lang direkt nach MIME-Version und
// bleibt sonst byte-gleich zum bisherigen Aufbau.
func TestBuildPayloadSetztSprachHeader(t *testing.T) {
	m := Mail{Subject: "Betreff", PlainBody: "text", HTMLBody: "<p>h</p>"}
	for _, f := range []struct {
		lang i18n.Lang
		want string
	}{{"", "de"}, {i18n.De, "de"}, {i18n.En, "en"}} {
		m.Lang = f.lang
		payload := buildPayload("from@example.invalid", "to@example.invalid", "b0", m)
		wantPayload := "From: from@example.invalid\r\nTo: to@example.invalid\r\nSubject: Betreff\r\n" +
			"MIME-Version: 1.0\r\nX-GZ-Lang: " + f.want + "\r\n" +
			"Content-Type: multipart/alternative; boundary=\"b0\"\r\n\r\n" +
			"--b0\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\ntext\r\n\r\n" +
			"--b0\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n<p>h</p>\r\n\r\n--b0--\r\n"
		if string(payload) != wantPayload {
			t.Errorf("Lang %q: Payload\n%q\nerwartet\n%q", f.lang, payload, wantPayload)
		}
		msg, err := mail.ReadMessage(strings.NewReader(string(payload)))
		if err != nil {
			t.Fatalf("Lang %q: ReadMessage: %v", f.lang, err)
		}
		if got := msg.Header.Get("X-GZ-Lang"); got != f.want {
			t.Errorf("Lang %q: X-GZ-Lang=%q, erwartet %q", f.lang, got, f.want)
		}
	}
}

// AC-3: die Betreiber-Mail bleibt deutsch und traegt Lang de.
func TestBetreiberMailBleibtDeutsch(t *testing.T) {
	m := BuildTierChangeRequestMail("anna-en", "free", "premium")
	if m.Lang != i18n.De {
		t.Errorf("AC-3: Betreiber-Mail Lang=%q, erwartet de", m.Lang)
	}
	if m.Subject != "Gregor 20 — Level-Wechsel-Antrag von anna-en" {
		t.Errorf("AC-3: Betreff %q", m.Subject)
	}
	payload := buildPayload("f@example.invalid", "po@example.invalid", "b", m)
	msg, err := mail.ReadMessage(strings.NewReader(string(payload)))
	if err != nil || msg.Header.Get("X-GZ-Lang") != "de" {
		t.Errorf("AC-3: X-GZ-Lang der Betreiber-Mail nicht de (err %v)", err)
	}
}
