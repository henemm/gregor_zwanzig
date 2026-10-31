package i18n

// doc-compliance-test
//
// Issue #2675 (i18n G1) — Paritaetstest des Go-Katalogs.
// Spec: docs/specs/modules/i18n_g1_go_kern_2675.md — AC-5.
//
// Der echte, eingebettete Katalog muss bestehen; dieselbe Pruefung wird mit
// absichtlich fehlerhaften fstest.MapFS-Katalogen aufgerufen und muss dort
// scheitern und den Schluessel nennen.

import (
	"io/fs"
	"strings"
	"testing"
	"testing/fstest"
)

func paritaetVon(t *testing.T, files map[string]string) error {
	t.Helper()
	fsys := fstest.MapFS{}
	for name, body := range files {
		fsys[name] = &fstest.MapFile{Data: []byte(body)}
	}
	c, err := NewCatalog(fsys)
	if err != nil {
		t.Fatalf("NewCatalog: %v", err)
	}
	return c.Parity()
}

// AC-5: der echte Katalog besteht.
func TestEchterKatalogIstParitaetisch(t *testing.T) {
	if err := Default.Parity(); err != nil {
		t.Fatalf("echter Katalog verletzt die Paritaet: %v", err)
	}
}

// Konventionen Abschnitt 2: alle fuenf Go-Bereiche liegen in beiden Sprachen vor.
func TestAlleBereichsdateienAngelegt(t *testing.T) {
	for _, lang := range []string{"de", "en"} {
		for _, b := range []string{"fehler", "auth", "konto", "fach", "mail"} {
			p := "messages/" + lang + "/" + b + ".json"
			if _, err := fs.Stat(embedded, p); err != nil {
				t.Errorf("Bereichsdatei %s fehlt: %v", p, err)
			}
		}
	}
}

// AC-5: fehlender en-Text faellt auf und wird benannt.
func TestParitaetMeldetFehlendenEnglischenSchluessel(t *testing.T) {
	err := paritaetVon(t, map[string]string{
		"messages/de/fach.json": `{"fach.da":"Da","fach.nur_de":"Nur deutsch"}`,
		"messages/en/fach.json": `{"fach.da":"Here"}`,
	})
	if err == nil || !strings.Contains(err.Error(), "fach.nur_de") {
		t.Errorf("fehlender en-Schluessel nicht gemeldet: %v", err)
	}
}

// Umgekehrt: Schluessel nur in en.
func TestParitaetMeldetSchluesselNurInEnglisch(t *testing.T) {
	err := paritaetVon(t, map[string]string{
		"messages/de/fach.json": `{}`,
		"messages/en/fach.json": `{"fach.nur_en":"Only english"}`,
	})
	if err == nil || !strings.Contains(err.Error(), "fach.nur_en") {
		t.Errorf("Schluessel nur in en nicht gemeldet: %v", err)
	}
}

// AC-5: abweichende Platzhaltermengen fallen auf.
func TestParitaetMeldetAbweichendePlatzhalter(t *testing.T) {
	err := paritaetVon(t, map[string]string{
		"messages/de/fach.json": `{"fach.gruss":"Hallo {name}"}`,
		"messages/en/fach.json": `{"fach.gruss":"Hello {vorname}"}`,
	})
	if err == nil || !strings.Contains(err.Error(), "fach.gruss") {
		t.Errorf("Platzhalter-Abweichung nicht gemeldet: %v", err)
	}
}

// Eine Bereichsdatei, die nur in einer Sprache existiert, faellt auf.
func TestParitaetMeldetFehlendeBereichsdatei(t *testing.T) {
	err := paritaetVon(t, map[string]string{
		"messages/de/fach.json": `{}`,
		"messages/de/mail.json": `{}`,
		"messages/en/fach.json": `{}`,
	})
	if err == nil || !strings.Contains(err.Error(), "mail") {
		t.Errorf("fehlende en-Bereichsdatei nicht gemeldet: %v", err)
	}
}

// AC-5: ein Fehlercode in zwei der vier Bereiche ist verboten.
func TestParitaetMeldetDoppeltenFehlercode(t *testing.T) {
	err := paritaetVon(t, map[string]string{
		"messages/de/fehler.json": `{"fehler.doppelt":"A"}`,
		"messages/en/fehler.json": `{"fehler.doppelt":"A"}`,
		"messages/de/konto.json":  `{"konto.fehler.doppelt":"B"}`,
		"messages/en/konto.json":  `{"konto.fehler.doppelt":"B"}`,
	})
	if err == nil || !strings.Contains(err.Error(), "doppelt") {
		t.Errorf("doppelter Fehlercode nicht gemeldet: %v", err)
	}
}
