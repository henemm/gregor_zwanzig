package store

// TDD RED — Issue #2194 (Epic #2138): E-Mail-Adresse als Login-Identifier.
// Spec: docs/specs/modules/email_login_identifier.md — Store-Teil von AC-3,
// AC-4, AC-5, AC-10, AC-13 (Lookup und ID-Generator).
//
// Festgelegte neue Symbole (package store, Datei internal/store/login_lookup.go):
//
//	func (s *Store) FindUsersByLoginEmail(addr string) ([]*model.User, error)
//
//	  Liefert ALLE Nicht-Testkonten (model.IsTestAccount == false), deren Feld
//	  `email` — und NUR `email`, nie `mail_to` — nach NormalizeEmailAddress
//	  gleich NormalizeEmailAddress(addr) ist. Normalisiert wird beidseitig
//	  (Bestandskonten koennen eine gemischt geschriebene Adresse tragen).
//	  Leere/nur-Leerzeichen-Adresse => 0 Treffer, kein Fehler (sonst passten
//	  alle Konten ohne email). Fail-closed: eine unlesbare user.json IRGENDEINES
//	  Kontos => (nil, error) — anders als FindUserByOAuthSub, das still
//	  ueberspringt. Reihenfolge der Treffer unspezifiziert.
//
//	func (s *Store) NewOpaqueUserID(prefix string) (string, error)
//
//	  prefix OHNE Bindestrich ("u" => "u-<8 hex klein>"). 8 Hex-Zeichen = 4
//	  Zufallsbytes aus opaqueIDRandFn. Kollisionspruefung gegen den Bestand
//	  (bereits existierendes Konto mit dieser ID) => neuer Versuch, nie
//	  dieselbe ID zurueck. Begrenzte Versuchszahl: liefert die Quelle immer
//	  nur belegte IDs, kommt ein Fehler statt einer Endlosschleife.
//
//	var opaqueIDRandFn func([]byte) (int, error) = crypto/rand.Read
//
//	  Paketinterne Zufallsquelle (Test-Seam fuer den Kollisionsnachweis).
//	  Vertrag: GENAU EIN Aufruf pro Versuch mit einem 4-Byte-Puffer, der
//	  hex-kodiert die 8 Zeichen der ID ergibt.
//
// RED-Beleg: Build-Fehler "undefined" fuer die drei Symbole.
//
// Kein Mock: echter Store in t.TempDir(), echte user.json-Dateien.

import (
	"bytes"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

var opakeIDMuster2194 = regexp.MustCompile(`^u-[0-9a-f]{8}$`)

func seedKonto2194(t *testing.T, s *Store, u model.User) {
	t.Helper()
	if u.CreatedAt.IsZero() {
		u.CreatedAt = time.Now()
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser %q: %v", u.ID, err)
	}
}

func trefferIDs2194(us []*model.User) []string {
	ids := make([]string, 0, len(us))
	for _, u := range us {
		if u == nil {
			ids = append(ids, "<nil>")
			continue
		}
		ids = append(ids, u.ID)
	}
	sort.Strings(ids)
	return ids
}

func gleicheIDs2194(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

// AC-1/AC-3: 0, 1 und n Treffer; Normalisierung auf BEIDEN Seiten.
func TestFindUsersByLoginEmail_NullEinsMehrereTreffer_Normalisiert_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	// Bestandskonto mit gemischt geschriebener Adresse (vor der Normalisierung).
	seedKonto2194(t, s, model.User{ID: "anna", Email: "Anna@Beispiel.DE", MailTo: "Anna@Beispiel.DE"})
	seedKonto2194(t, s, model.User{ID: "bert", Email: "bert@beispiel.de"})
	// Bestandsduplikat zweier echter Konten (vor ADR-0067 entstanden).
	seedKonto2194(t, s, model.User{ID: "dora", Email: "doppelt@beispiel.de"})
	seedKonto2194(t, s, model.User{ID: "emil", Email: "Doppelt@Beispiel.de"})

	faelle := []struct {
		name    string
		adresse string
		want    []string
	}{
		{"ein Treffer, Eingabe mit Rand-Leerzeichen und Grossbuchstaben", "  ANNA@beispiel.de ", []string{"anna"}},
		{"ein Treffer, exakt", "bert@beispiel.de", []string{"bert"}},
		{"kein Treffer", "niemand@beispiel.de", []string{}},
		{"zwei Treffer", "doppelt@beispiel.de", []string{"dora", "emil"}},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			got, err := s.FindUsersByLoginEmail(f.adresse)
			if err != nil {
				t.Fatalf("FindUsersByLoginEmail(%q): unerwarteter Fehler %v", f.adresse, err)
			}
			if ids := trefferIDs2194(got); !gleicheIDs2194(ids, f.want) {
				t.Errorf("FindUsersByLoginEmail(%q): erwartet %v, bekommen %v", f.adresse, f.want, ids)
			}
		})
	}
}

// AC-5: nur `email` zaehlt, eine abweichende Zustelladresse `mail_to` nie.
func TestFindUsersByLoginEmail_NurEmailNichtMailTo_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	seedKonto2194(t, s, model.User{ID: "carla", Email: "a@x.de", MailTo: "b@x.de"})

	got, err := s.FindUsersByLoginEmail("b@x.de")
	if err != nil {
		t.Fatalf("FindUsersByLoginEmail(b@x.de): %v", err)
	}
	if len(got) != 0 {
		t.Errorf("AC-5: mail_to darf den Login-Lookup nie aufloesen, bekommen %v", trefferIDs2194(got))
	}

	got, err = s.FindUsersByLoginEmail("a@x.de")
	if err != nil {
		t.Fatalf("FindUsersByLoginEmail(a@x.de): %v", err)
	}
	if ids := trefferIDs2194(got); !gleicheIDs2194(ids, []string{"carla"}) {
		t.Errorf("AC-5 Positivkontrolle: email muss das Konto aufloesen, bekommen %v", ids)
	}
}

// AC-4: Testkonten (Profilfeld und Fixture-ID tg-live-e2e) sind ausgeschlossen
// — auch wenn sie dieselbe Adresse tragen wie ein echtes Konto.
func TestFindUsersByLoginEmail_TestkontenAusgeschlossen_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	seedKonto2194(t, s, model.User{ID: "validator-x", Email: "geteilt@beispiel.de", IsTestUser: true})
	seedKonto2194(t, s, model.User{ID: "tg-live-e2e", Email: "geteilt@beispiel.de"})
	seedKonto2194(t, s, model.User{ID: "echt", Email: "geteilt@beispiel.de"})
	seedKonto2194(t, s, model.User{ID: "nur-test", Email: "nurtest@beispiel.de", IsTestUser: true})

	got, err := s.FindUsersByLoginEmail("geteilt@beispiel.de")
	if err != nil {
		t.Fatalf("FindUsersByLoginEmail: %v", err)
	}
	if ids := trefferIDs2194(got); !gleicheIDs2194(ids, []string{"echt"}) {
		t.Errorf("AC-4: nur das echte Konto darf treffen (Testkonten zaehlen nicht mit), bekommen %v", ids)
	}

	got, err = s.FindUsersByLoginEmail("nurtest@beispiel.de")
	if err != nil {
		t.Fatalf("FindUsersByLoginEmail: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("AC-4: ein reines Testkonto ist per E-Mail nicht auffindbar, bekommen %v", trefferIDs2194(got))
	}
}

// Leere Adresse darf nie Konten ohne email treffen.
func TestFindUsersByLoginEmail_LeereAdresseTrifftNichts_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	seedKonto2194(t, s, model.User{ID: "ohne-mail"})
	seedKonto2194(t, s, model.User{ID: "mit-mail", Email: "m@beispiel.de"})

	for _, adresse := range []string{"", "   "} {
		got, err := s.FindUsersByLoginEmail(adresse)
		if err != nil {
			t.Errorf("FindUsersByLoginEmail(%q): leere Adresse ist kein Fehlerfall, bekommen %v", adresse, err)
		}
		if len(got) != 0 {
			t.Errorf("FindUsersByLoginEmail(%q): leere Adresse darf nichts treffen, bekommen %v",
				adresse, trefferIDs2194(got))
		}
	}
}

// Fail-closed: eine unlesbare user.json bricht mit Fehler ab, statt still
// ein Konto zu uebergehen (sonst koennte aus 2 Treffern scheinbar 1 werden).
func TestFindUsersByLoginEmail_KaputteUserJSONFailClosed_2194(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "")
	seedKonto2194(t, s, model.User{ID: "heil", Email: "doppelt@beispiel.de"})
	writeRawUserJSON(t, dir, "kaputt", `{"id":"kaputt","email":"doppelt@beispiel.de",`)

	got, err := s.FindUsersByLoginEmail("doppelt@beispiel.de")
	if err == nil {
		t.Errorf("fail-closed: eine kaputte user.json muss einen Fehler liefern, bekommen Treffer %v ohne Fehler",
			trefferIDs2194(got))
	}
	if len(got) != 0 {
		t.Errorf("fail-closed: bei Fehler keine Treffer zurueckgeben, bekommen %v", trefferIDs2194(got))
	}
}

// AC-10/AC-13: Format u-<8hex>, verschiedene IDs, kein bestehendes Konto.
func TestNewOpaqueUserID_FormatUndVerschieden_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	gesehen := map[string]bool{}
	for i := 0; i < 20; i++ {
		id, err := s.NewOpaqueUserID("u")
		if err != nil {
			t.Fatalf("NewOpaqueUserID: %v", err)
		}
		if !opakeIDMuster2194.MatchString(id) {
			t.Fatalf("AC-10: ID %q passt nicht zu ^u-[0-9a-f]{8}$", id)
		}
		if !ValidUserID(id) {
			t.Fatalf("AC-10: ID %q verletzt das Nutzer-ID-Muster", id)
		}
		if gesehen[id] {
			t.Fatalf("AC-13: zwei Aufrufe lieferten dieselbe ID %q", id)
		}
		gesehen[id] = true
	}
}

// AC-13: Kollision mit vorbelegtem Konto => neuer Versuch, nie Ueberschreiben.
func TestNewOpaqueUserID_KollisionWiederholtStattUeberschreiben_2194(t *testing.T) {
	dir := t.TempDir()
	s := New(dir, "")
	seedKonto2194(t, s, model.User{ID: "u-aaaaaaaa", Email: "belegt@beispiel.de"})
	pfad := filepath.Join(dir, "users", "u-aaaaaaaa", "user.json")
	vorher, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("Ausgangslage: %v", err)
	}

	aufrufe := 0
	orig := opaqueIDRandFn
	opaqueIDRandFn = func(b []byte) (int, error) {
		fuell := byte(0xaa)
		if aufrufe > 0 {
			fuell = 0xbb
		}
		aufrufe++
		for i := range b {
			b[i] = fuell
		}
		return len(b), nil
	}
	t.Cleanup(func() { opaqueIDRandFn = orig })

	id, err := s.NewOpaqueUserID("u")
	if err != nil {
		t.Fatalf("NewOpaqueUserID: %v", err)
	}
	if id == "u-aaaaaaaa" {
		t.Fatalf("AC-13: die belegte ID u-aaaaaaaa wurde erneut vergeben")
	}
	if id != "u-bbbbbbbb" {
		t.Errorf("AC-13: nach Kollision erwartet der zweite Zug u-bbbbbbbb, bekommen %q", id)
	}
	if aufrufe < 2 {
		t.Errorf("AC-13: die Zufallsquelle muss nach der Kollision erneut befragt werden, Aufrufe=%d", aufrufe)
	}
	nachher, err := os.ReadFile(pfad)
	if err != nil {
		t.Fatalf("das vorbelegte Konto ist verschwunden: %v", err)
	}
	if !bytes.Equal(vorher, nachher) {
		t.Errorf("AC-13: das vorbelegte Konto wurde veraendert")
	}
}

// Begrenzte Wiederholung: eine Quelle, die nur belegte IDs liefert, endet in
// einem Fehler statt in einer Endlosschleife.
func TestNewOpaqueUserID_DauerkollisionLiefertFehler_2194(t *testing.T) {
	s := New(t.TempDir(), "")
	seedKonto2194(t, s, model.User{ID: "u-cccccccc"})

	orig := opaqueIDRandFn
	opaqueIDRandFn = func(b []byte) (int, error) {
		for i := range b {
			b[i] = 0xcc
		}
		return len(b), nil
	}
	t.Cleanup(func() { opaqueIDRandFn = orig })

	type ergebnis struct {
		id  string
		err error
	}
	fertig := make(chan ergebnis, 1)
	go func() {
		id, err := s.NewOpaqueUserID("u")
		fertig <- ergebnis{id, err}
	}()
	select {
	case e := <-fertig:
		if e.err == nil {
			t.Errorf("Dauerkollision: erwartet Fehler, bekommen ID %q", e.id)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Dauerkollision: NewOpaqueUserID kehrt nicht zurueck (Endlosschleife)")
	}
}
