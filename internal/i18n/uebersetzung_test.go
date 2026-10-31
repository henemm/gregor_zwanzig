package i18n

// Issue #2675 (i18n G1) — T, Tn, Platzhalter, Fallback, Suchkette ErrorBody.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-7 (und Punkt 2).
//
// Keine Mocks: echte Kataloge aus testing/fstest.MapFS ueber NewCatalog,
// der echte Standardkatalog bleibt unberuehrt. Die Fallback-Logzeilen werden
// ueber log.SetOutput mitgelesen.

import (
	"bytes"
	"log"
	"strings"
	"testing"
	"testing/fstest"
)

func mapCatalog(t *testing.T, files map[string]string) *Catalog {
	t.Helper()
	fsys := fstest.MapFS{}
	for name, body := range files {
		fsys[name] = &fstest.MapFile{Data: []byte(body)}
	}
	c, err := NewCatalog(fsys)
	if err != nil {
		t.Fatalf("NewCatalog: %v", err)
	}
	return c
}

// captureLog lenkt das Standard-Log fuer die Testdauer in einen Puffer.
func captureLog(t *testing.T) *bytes.Buffer {
	t.Helper()
	var buf bytes.Buffer
	orig, flags := log.Writer(), log.Flags()
	log.SetOutput(&buf)
	log.SetFlags(0)
	t.Cleanup(func() { log.SetOutput(orig); log.SetFlags(flags) })
	return &buf
}

func nurDeKatalog(t *testing.T) *Catalog {
	return mapCatalog(t, map[string]string{
		"messages/de/fach.json": `{"fach.gruss.one":"Ein Ort für {name}","fach.gruss.other":"{count} Orte für {name}","fach.hallo":"Hallo {name}"}`,
		"messages/en/fach.json": `{}`,
	})
}

// AC-7: Tn waehlt .one bei 1 und .other sonst, {count} ist implizit gesetzt.
func TestTnWaehltPluralformUndSetztCount(t *testing.T) {
	c := mapCatalog(t, map[string]string{
		"messages/de/fach.json": `{"fach.orte.one":"Ein Ort","fach.orte.other":"{count} Orte"}`,
		"messages/en/fach.json": `{"fach.orte.one":"One location","fach.orte.other":"{count} locations"}`,
	})
	cases := []struct {
		lang  Lang
		count int
		want  string
	}{
		{En, 1, "One location"}, {En, 2, "2 locations"}, {En, 0, "0 locations"},
		{De, 1, "Ein Ort"}, {De, 7, "7 Orte"},
	}
	for _, tc := range cases {
		if got := c.Tn(tc.lang, "fach.orte", tc.count, nil); got != tc.want {
			t.Errorf("Tn(%s, %d) = %q, erwartet %q", tc.lang, tc.count, got, tc.want)
		}
	}
}

// AC-7: fehlender en-Text faellt auf de zurueck; Platzhalter werden ersetzt.
func TestFehlenderEnglischerTextFaelltAufDeutschZurueck(t *testing.T) {
	captureLog(t)
	c := nurDeKatalog(t)
	if got := c.T(En, "fach.hallo", Args{"name": "Anna"}); got != "Hallo Anna" {
		t.Errorf("T(En, fach.hallo) = %q, erwartet \"Hallo Anna\"", got)
	}
	if got := c.Tn(En, "fach.gruss", 1, Args{"name": "Anna"}); got != "Ein Ort für Anna" {
		t.Errorf("Tn(En, 1) = %q, erwartet \"Ein Ort für Anna\"", got)
	}
	if got := c.Tn(En, "fach.gruss", 2, Args{"name": "Anna"}); got != "2 Orte für Anna" {
		t.Errorf("Tn(En, 2) = %q, erwartet \"2 Orte für Anna\"", got)
	}
}

// AC-7: zwei Aufrufe desselben Schluessels erzeugen genau eine Logzeile.
func TestFallbackWirdJeSchluesselGenauEinmalGeloggt(t *testing.T) {
	buf := captureLog(t)
	c := nurDeKatalog(t)
	c.T(En, "fach.hallo", Args{"name": "Anna"})
	c.T(En, "fach.hallo", Args{"name": "Bert"})
	c.T(De, "fach.hallo", Args{"name": "Carl"})
	if n := strings.Count(buf.String(), "i18n fallback: fach.hallo"); n != 1 {
		t.Errorf("Logzeilen fuer fach.hallo: %d, erwartet 1 (Log: %q)", n, buf.String())
	}
	c.T(En, "fach.unbekannt_x", nil)
	c.T(En, "fach.unbekannt_x", nil)
	if n := strings.Count(buf.String(), "i18n fallback: fach.unbekannt_x"); n != 1 {
		t.Errorf("Logzeilen fuer fehlenden Schluessel: %d, erwartet 1 (Log: %q)", n, buf.String())
	}
}

// Schluessel in keiner Sprache: der Schluessel selbst kommt zurueck.
func TestSchluesselOhneTextLiefertSchluessel(t *testing.T) {
	captureLog(t)
	c := nurDeKatalog(t)
	if got := c.T(De, "fach.gibt_es_nicht", nil); got != "fach.gibt_es_nicht" {
		t.Errorf("T = %q, erwartet den Schluessel", got)
	}
}

// Platzhalter ohne Argument bleibt sichtbar stehen; Nicht-Strings via fmt.Sprint.
func TestPlatzhalterOhneArgumentBleibtStehen(t *testing.T) {
	c := mapCatalog(t, map[string]string{
		"messages/de/fach.json": `{"fach.satz":"{name} hat {anzahl} Etappen"}`,
		"messages/en/fach.json": `{"fach.satz":"{name} has {anzahl} stages"}`,
	})
	if got := c.T(En, "fach.satz", Args{"anzahl": 3}); got != "{name} has 3 stages" {
		t.Errorf("T = %q, erwartet \"{name} has 3 stages\"", got)
	}
}

// Tn darf die Argumente des Aufrufers nicht veraendern (kein geteilter Zustand).
func TestTnVeraendertArgsDesAufrufersNicht(t *testing.T) {
	c := nurDeKatalog(t)
	args := Args{"name": "Anna"}
	c.Tn(De, "fach.gruss", 2, args)
	if _, ok := args["count"]; ok {
		t.Errorf("Tn hat count in die Argumente des Aufrufers geschrieben: %v", args)
	}
}

// Der echte Standardkatalog liefert die Start-Schluessel in beiden Sprachen.
func TestStandardkatalogStartSchluessel(t *testing.T) {
	if got := T(En, "fehler.not_found", nil); got != "Not found." {
		t.Errorf("T(En, fehler.not_found) = %q", got)
	}
	if got := T(De, "fehler.not_found", nil); got != "Nicht gefunden." {
		t.Errorf("T(De, fehler.not_found) = %q", got)
	}
	if got := T(En, "fehler.unbekannt", Args{"code": "x_y"}); got != "Unknown error (x_y)." {
		t.Errorf("T(En, fehler.unbekannt) = %q", got)
	}
	if !Has("fehler.kind_required") || Has("fehler.gibt_es_nicht") {
		t.Errorf("Has: kind_required muss vorhanden, gibt_es_nicht darf nicht vorhanden sein")
	}
	if got := Tn(De, "fehler.not_found", 1, nil); got == "" {
		t.Errorf("Tn auf dem Standardkatalog liefert leeren Text")
	}
}

// Parse: genau "en" ist Englisch, alles andere Deutsch.
func TestParse(t *testing.T) {
	for in, want := range map[string]Lang{"en": En, "de": De, "": De, "fr": De, "EN": De, " en": De} {
		if got := Parse(in); got != want {
			t.Errorf("Parse(%q) = %q, erwartet %q", in, got, want)
		}
	}
}

func suchKatalog(t *testing.T) *Catalog {
	return mapCatalog(t, map[string]string{
		"messages/de/fehler.json": `{"fehler.not_found":"Nicht gefunden.","fehler.unbekannt":"Unbekannter Fehler ({code}).","fehler.zu_gross":"Höchstens {max} erlaubt."}`,
		"messages/en/fehler.json": `{"fehler.not_found":"Not found.","fehler.unbekannt":"Unknown error ({code}).","fehler.zu_gross":"At most {max} allowed."}`,
		"messages/de/auth.json":   `{"auth.fehler.login_falsch":"Anmeldung fehlgeschlagen."}`,
		"messages/en/auth.json":   `{"auth.fehler.login_falsch":"Sign-in failed."}`,
		"messages/de/konto.json":  `{"konto.fehler.mail_belegt":"Adresse vergeben.","konto.fehler.mail_belegt_sms":"Nummer vergeben."}`,
		"messages/en/konto.json":  `{"konto.fehler.mail_belegt":"Address taken.","konto.fehler.mail_belegt_sms":"Number taken."}`,
		"messages/de/fach.json":   `{"fach.fehler.etag":"Veraltet."}`,
		"messages/en/fach.json":   `{"fach.fehler.etag":"Outdated."}`,
	})
}

// Suchkette fehler. -> auth.fehler. -> konto.fehler. -> fach.fehler., Variante zuerst.
func TestErrorBodySuchkette(t *testing.T) {
	c := suchKatalog(t)
	cases := []struct {
		code    string
		args    Args
		message string
	}{
		{"not_found", nil, "Not found."},
		{"login_falsch", nil, "Sign-in failed."},
		{"mail_belegt", nil, "Address taken."},
		{"mail_belegt", Args{"variante": "sms"}, "Number taken."},
		{"mail_belegt", Args{"variante": "gibtsnicht"}, "Address taken."},
		{"etag", nil, "Outdated."},
		{"zu_gross", Args{"max": 5}, "At most 5 allowed."},
		{"voellig_neu", nil, "Unknown error (voellig_neu)."},
	}
	for _, tc := range cases {
		b := c.ErrorBody(En, tc.code, tc.args)
		if b["code"] != tc.code || b["error"] != tc.code {
			t.Errorf("%s: code=%v error=%v, erwartet beide %q", tc.code, b["code"], b["error"], tc.code)
		}
		if b["message"] != tc.message {
			t.Errorf("%s %v: message=%v, erwartet %q", tc.code, tc.args, b["message"], tc.message)
		}
		if b["detail"] != tc.message {
			t.Errorf("%s: detail=%v, erwartet message %q", tc.code, b["detail"], tc.message)
		}
	}
}

// detail traegt einen technischen Zusatz, wenn args["detail"] ein nicht leerer String ist.
func TestErrorBodyDetailAusArgs(t *testing.T) {
	c := suchKatalog(t)
	b := c.ErrorBody(De, "not_found", Args{"detail": "trip abc fehlt"})
	if b["detail"] != "trip abc fehlt" || b["message"] != "Nicht gefunden." {
		t.Errorf("detail=%v message=%v", b["detail"], b["message"])
	}
	b = c.ErrorBody(De, "not_found", Args{"detail": ""})
	if b["detail"] != "Nicht gefunden." {
		t.Errorf("leeres detail: detail=%v, erwartet message", b["detail"])
	}
}

// Ladepruefung: Zeichen, Segmentzahl und Bereichs-Praefix.
func TestNewCatalogWeistUngueltigeSchluesselAb(t *testing.T) {
	cases := map[string]string{
		"Grossbuchstaben":  `{"fach.Gross":"x"}`,
		"Bindestrich":      `{"fach.a-b":"x"}`,
		"ein Segment":      `{"fach":"x"}`,
		"fuenf Segmente":   `{"fach.a.b.c.d":"x"}`,
		"fremder Bereich":  `{"auth.login":"x"}`,
		"kein flacher Text": `{"fach.a":{"b":"c"}}`,
	}
	for name, body := range cases {
		_, err := NewCatalog(fstest.MapFS{"messages/de/fach.json": &fstest.MapFile{Data: []byte(body)}})
		if err == nil {
			t.Errorf("%s: NewCatalog akzeptiert %s", name, body)
			continue
		}
		if !strings.Contains(err.Error(), "fach.json") {
			t.Errorf("%s: Fehler nennt die Datei nicht: %v", name, err)
		}
	}
	_, err := NewCatalog(fstest.MapFS{"messages/de/fach.json": &fstest.MapFile{Data: []byte(`{"fach.a-b":"x"}`)}})
	if err == nil || !strings.Contains(err.Error(), "fach.a-b") {
		t.Errorf("Fehler nennt den Schluessel nicht: %v", err)
	}
}
