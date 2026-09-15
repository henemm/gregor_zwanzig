package store

// TDD RED — Issue #2147 Scheibe C, AC-16/AC-17: numerischer Kollisionszähler
// für Bestandsduplikate von E-Mail-Adressen.
// Spec: docs/specs/modules/google_login_adress_verknuepfung.md
//
// Erwartete Produktivsymbole (entstehen in /50, NICHT hier deklariert — der
// Build-Fehler dieses Pakets ist das beabsichtigte RED):
//
//	type AddressCollisionCount struct {
//		Addresses int // normalisierte Adressen, die >1 echtes Konto hält
//		Accounts  int // verschiedene echte Konten, die mindestens eine davon halten
//	}
//	func (s *Store) CountAddressCollisions() (AddressCollisionCount, error)
//	func (s *Store) LogAddressCollisions() // fail-soft, nur Zahlen ins Log; Aufruf in cmd/server/main.go nach store.New
//
// Definition „hält": NormalizeEmailAddress(email) == X ODER
// NormalizeEmailAddress(mail_to) == X (kreuzweise), leere Adresse zählt nie,
// Testkonten (model.IsTestUserID, wie forEachRealAccount) zählen nie. Ein
// Konto, das X in beiden Feldern trägt, hält X einmal.
//
// Echter Store auf t.TempDir(), kein Mock.

import (
	"bytes"
	"log"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func kollisionKonto(t *testing.T, s *Store, u model.User) {
	t.Helper()
	if u.CreatedAt.IsZero() {
		u.CreatedAt = time.Date(2026, 9, 1, 0, 0, 0, 0, time.UTC)
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("Konto %q anlegen: %v", u.ID, err)
	}
}

// kollisionBestand baut den gemischten Bestand:
//
//	dup1: alpha (email+mail_to, gemischte Schreibung) · bravo (mail_to mit Leerzeichen/Großschreibung)
//	      + tg-live-e2e (Testkonto, zählt nicht)
//	dup2: bravo (email) · charlie (email) · delta (mail_to, Großschreibung) — kreuzweise
//	      bravo hält dup1 UND dup2 -> als Konto nur einmal gezählt
//	dup3: echo (echt) + gz-test-dup3 (Testkonto) -> KEINE Kollision
//	nurtest: gz-test-eins + tdd-zwei -> KEINE Kollision (nur Testkonten)
//	leer: foxtrot + golf ohne email/mail_to -> KEINE Kollision
//	solo: hotel allein
//
// Erwartung: Addresses=2 (dup1, dup2), Accounts=4 (alpha, bravo, charlie, delta).
func kollisionBestand(t *testing.T) *Store {
	t.Helper()
	s := New(t.TempDir(), "default")
	kollisionKonto(t, s, model.User{ID: "alpha-kollision", Email: "Dup1-Kollision@Beispiel.de", MailTo: "dup1-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "bravo-kollision", Email: "dup2-kollision@beispiel.de", MailTo: "  DUP1-kollision@beispiel.de "})
	kollisionKonto(t, s, model.User{ID: "charlie-kollision", Email: "dup2-kollision@beispiel.de", MailTo: "charlie-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "delta-kollision", Email: "delta-kollision@beispiel.de", MailTo: "Dup2-Kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "tg-live-e2e", Email: "dup1-kollision@beispiel.de", MailTo: "dup1-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "echo-kollision", Email: "dup3-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "gz-test-dup3", MailTo: "dup3-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "gz-test-eins", Email: "nurtest-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "tdd-zwei", MailTo: "nurtest-kollision@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "foxtrot-kollision"})
	kollisionKonto(t, s, model.User{ID: "golf-kollision", Email: "  ", MailTo: ""})
	kollisionKonto(t, s, model.User{ID: "hotel-kollision", Email: "hotel-kollision@beispiel.de", MailTo: "hotel-kollision@beispiel.de"})
	return s
}

// kollisionFixtureMerkmale: alles, was nie im Log stehen darf.
var kollisionFixtureMerkmale = []string{
	"@", "beispiel.de", "dup1-kollision", "dup2-kollision", "dup3-kollision", "nurtest-kollision",
	"alpha-kollision", "bravo-kollision", "charlie-kollision", "delta-kollision", "echo-kollision",
	"foxtrot-kollision", "golf-kollision", "hotel-kollision", "tg-live-e2e", "gz-test", "tdd-zwei",
}

func kollisionMitschnitt(t *testing.T, fn func()) string {
	t.Helper()
	var puffer bytes.Buffer
	log.SetOutput(&puffer)
	defer log.SetOutput(os.Stderr)
	fn()
	return puffer.String()
}

// AC-16: korrekte Zählung (kreuzweise, Groß-/Kleinschreibung, Testkonten und
// leere Adressen ausgenommen, Mehrfach-Halter einmal gezählt).
func TestAddressCollisions_AC16_ZaehltNurEchteKontenKreuzweise(t *testing.T) {
	s := kollisionBestand(t)

	got, err := s.CountAddressCollisions()
	if err != nil {
		t.Fatalf("AC-16: CountAddressCollisions: unerwarteter Fehler: %v", err)
	}
	if got.Addresses != 2 {
		t.Errorf("AC-16: erwartet 2 betroffene Adressen (dup1, dup2), gezählt %d", got.Addresses)
	}
	if got.Accounts != 4 {
		t.Errorf("AC-16: erwartet 4 betroffene echte Konten (alpha, bravo, charlie, delta), gezählt %d", got.Accounts)
	}
}

// AC-16 (Nullfall): ein Bestand ohne Duplikat unter echten Konten liefert 0/0 —
// auch wenn Testkonten oder leere Adressen sich „teilen".
func TestAddressCollisions_AC16_OhneDuplikatNull(t *testing.T) {
	s := New(t.TempDir(), "default")
	kollisionKonto(t, s, model.User{ID: "india-kollision", Email: "india@beispiel.de", MailTo: "india@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "juliett-kollision", Email: "juliett@beispiel.de"})
	kollisionKonto(t, s, model.User{ID: "kilo-kollision"})
	kollisionKonto(t, s, model.User{ID: "lima-kollision"})
	kollisionKonto(t, s, model.User{ID: "gz-test-india", Email: "INDIA@beispiel.de"})

	got, err := s.CountAddressCollisions()
	if err != nil {
		t.Fatalf("AC-16: CountAddressCollisions: unerwarteter Fehler: %v", err)
	}
	if got.Addresses != 0 || got.Accounts != 0 {
		t.Errorf("AC-16: erwartet 0 Adressen / 0 Konten, gezählt %d / %d", got.Addresses, got.Accounts)
	}
}

// AC-16 (Log): der Start-Log nennt die Zahlen, aber weder Adressen noch
// user_ids der Fixture.
func TestAddressCollisions_AC16_LogNurZahlen(t *testing.T) {
	s := kollisionBestand(t)

	protokoll := kollisionMitschnitt(t, func() { s.LogAddressCollisions() })

	if strings.TrimSpace(protokoll) == "" {
		t.Fatalf("AC-16: der Zähler muss eine Logzeile schreiben — Log ist leer")
	}
	klein := strings.ToLower(protokoll)
	for _, m := range kollisionFixtureMerkmale {
		if strings.Contains(klein, strings.ToLower(m)) {
			t.Errorf("AC-16: das Log nennt %q (Adresse/user_id): %q", m, protokoll)
		}
	}
	zahlen := regexp.MustCompile(`\b\d+\b`).FindAllString(
		regexp.MustCompile(`^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} `).ReplaceAllString(protokoll, ""), -1)
	hat := map[string]bool{}
	for _, z := range zahlen {
		hat[z] = true
	}
	if !hat["2"] || !hat["4"] {
		t.Errorf("AC-16: das Log muss die Zahlen 2 (Adressen) und 4 (Konten) nennen, gefunden %v in %q", zahlen, protokoll)
	}
}

// AC-17: eine unlesbare Kontodatei -> CountAddressCollisions liefert einen
// Fehler (keine falsche Zahl), LogAddressCollisions schreibt eine Fehlerzeile
// ohne Adresse/user_id und kehrt zurück (kein Panic, kein log.Fatal).
func TestAddressCollisions_AC17_UnlesbareKontodateiIstFailSoft(t *testing.T) {
	s := kollisionBestand(t)
	dir := filepath.Join(s.DataDir, "users", "defekt-kollision")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("MkdirAll: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte("{das ist kein json"), 0644); err != nil {
		t.Fatalf("beschädigte user.json schreiben: %v", err)
	}

	if _, err := s.CountAddressCollisions(); err == nil {
		t.Errorf("AC-17: bei unlesbarer Kontodatei muss CountAddressCollisions einen Fehler liefern, nicht still weiterzählen")
	}

	var panicWert interface{}
	protokoll := kollisionMitschnitt(t, func() {
		defer func() { panicWert = recover() }()
		s.LogAddressCollisions()
	})
	if panicWert != nil {
		t.Fatalf("AC-17: LogAddressCollisions darf nicht paniken, Panic: %v", panicWert)
	}
	if strings.TrimSpace(protokoll) == "" {
		t.Errorf("AC-17: bei Scan-Fehler muss eine Fehlerzeile geloggt werden — Log ist leer")
	}
	klein := strings.ToLower(protokoll)
	for _, m := range append(kollisionFixtureMerkmale, "defekt-kollision") {
		if strings.Contains(klein, strings.ToLower(m)) {
			t.Errorf("AC-17: die Fehlerzeile nennt %q (Adresse/user_id): %q", m, protokoll)
		}
	}
}
