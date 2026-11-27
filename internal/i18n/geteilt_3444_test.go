package i18n

// Spec: docs/specs/modules/feat_3444_gemeinsamer_katalog.md (#3444, ADR-0130)
// AC-2, AC-4, AC-5, AC-6. Echte Kataloge bzw. fstest.MapFS, kein Mock.
//
// Erwartete API (Developer implementiert genau diese Namen):
//   - package github.com/henemm/gregor-api/src/i18n, Variable `Messages embed.FS`
//     (nur messages/de/geteilt.json und messages/en/geteilt.json)
//   - func NewCatalogFrom(fsys ...fs.FS) (*Catalog, error)   (Merge mehrerer FS)
//   - func CheckNoSharedAreaInternal(fsys fs.FS) error       (Waechter AC-6;
//     Fehler, wenn messages/<lang>/geteilt.json in fsys existiert)

import (
	"encoding/json"
	"io/fs"
	"os"
	"strings"
	"testing"
	"testing/fstest"

	srci18n "github.com/henemm/gregor-api/src/i18n"
)

const kindKey = "geteilt.fehler.kind_required"

func geteiltFS(de, en string) fstest.MapFS {
	return fstest.MapFS{
		"messages/de/geteilt.json": {Data: []byte(`{"` + kindKey + `":"` + de + `"}`)},
		"messages/en/geteilt.json": {Data: []byte(`{"` + kindKey + `":"` + en + `"}`)},
	}
}

// AC-2: geaenderter Text im geteilt-FS kommt aus ErrorBody und T.
func TestGeteiltGeaenderterTextWirdAusgegeben(t *testing.T) {
	c, err := NewCatalogFrom(embedded, geteiltFS("DE-NEU", "EN-NEU"))
	if err != nil {
		t.Fatalf("NewCatalogFrom: %v", err)
	}
	if got := c.T(De, kindKey, nil); got != "DE-NEU" {
		t.Errorf("T(de) = %q", got)
	}
	body := c.ErrorBody(En, "kind_required", nil)
	if body["message"] != "EN-NEU" || body["code"] != "kind_required" {
		t.Errorf("ErrorBody(en) = %v", body)
	}
}

// AC-4: Standardkatalog hat nur den neuen Schluessel; Wortlaut = Fixture.
func TestGeteiltStandardkatalogNurNeuerSchluessel(t *testing.T) {
	if !Has(kindKey) || Has("fehler.kind_required") {
		t.Fatalf("Has(%s)=%v Has(fehler.kind_required)=%v", kindKey, Has(kindKey), Has("fehler.kind_required"))
	}
	raw, err := os.ReadFile("../../tests/fixtures/send_detail_parity/faelle.json")
	if err != nil {
		t.Fatal(err)
	}
	var soll map[string]string
	if err := json.Unmarshal(raw, &soll); err != nil {
		t.Fatal(err)
	}
	body := Default.ErrorBody(De, "kind_required", nil)
	if body["message"] != soll["kind_required"] || soll["kind_required"] == "" {
		t.Errorf("message = %v, Fixture = %q", body["message"], soll["kind_required"])
	}
}

// AC-5: aus src kommt nur der Bereich geteilt; de/en paritaetisch.
func TestGeteiltAusSrcNurBereichGeteilt(t *testing.T) {
	if err := fs.WalkDir(srci18n.Messages, ".", func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() && !strings.HasSuffix(p, "/geteilt.json") {
			t.Errorf("src-FS enthaelt fremde Datei %s", p)
		}
		return err
	}); err != nil {
		t.Fatal(err)
	}
	src, err := NewCatalogFrom(srci18n.Messages)
	if err != nil {
		t.Fatal(err)
	}
	for _, lang := range []Lang{De, En} {
		if len(src.texts[lang]) == 0 {
			t.Errorf("geteilt leer in %s", lang)
		}
		for k := range src.texts[lang] {
			if !strings.HasPrefix(k, "geteilt.") {
				t.Errorf("fremder Schluessel aus src: %s", k)
			}
		}
	}
	if err := src.Parity(); err != nil {
		t.Errorf("geteilt de/en nicht paritaetisch: %v", err)
	}
	if err := Default.Parity(); err != nil {
		t.Errorf("Default.Parity: %v", err)
	}
}

// AC-6: echter internal-Baum hat keine geteilt.json; Negativprobe schlaegt an.
func TestGeteiltWaechterInternalOhneGeteilt(t *testing.T) {
	if err := CheckNoSharedAreaInternal(embedded); err != nil {
		t.Errorf("echter internal-Baum verletzt Waechter: %v", err)
	}
	probe := fstest.MapFS{
		"messages/de/fehler.json":  {Data: []byte(`{}`)},
		"messages/de/geteilt.json": {Data: []byte(`{}`)},
	}
	if err := CheckNoSharedAreaInternal(probe); err == nil {
		t.Errorf("Negativprobe: geteilt.json unter internal nicht gemeldet")
	}
	probeEn := fstest.MapFS{
		"messages/en/fehler.json":  {Data: []byte(`{}`)},
		"messages/en/geteilt.json": {Data: []byte(`{}`)},
	}
	if err := CheckNoSharedAreaInternal(probeEn); err == nil {
		t.Errorf("Negativprobe en: geteilt.json unter internal/en nicht gemeldet")
	}
}
