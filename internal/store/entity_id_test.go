package store

import (
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

// TDD RED — Issue #2140 Scheibe 2 (Entitaets-Achse), Store-Ebene. SPEC:
// docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md AC-8, AC-10 (Vorbereitung).
//
// ValidEntityID/ErrInvalidEntityID existieren noch nicht -> das Paket
// kompiliert nicht -> ALLE Tests in diesem Package sind rot. Das allein waere
// der SCHWAECHSTE RED-Grund (fehlendes Symbol). Deshalb pruefen die Tests
// unten zusaetzlich, was nach einem leeren/permissiven Platzhalter-Guard
// (der immer true liefert) noch fehlt: die tatsaechliche DURCHSETZUNG in den
// Store-Methoden (AC-8) bleibt auch dann rot.
//
// Methodik (siehe pathsafe_test.go, dortiger Kommentar): "../../bob/user" ist
// KEIN Geschwister-Pfad wie in Scheibe 1 ("../bob" bei UserDir, EINE Ebene
// unter data/users/), sondern trifft ueber briefingsDir()
// (data/users/<uid>/briefings/, ZWEI Ebenen unter data/users/) DIREKT die
// user.json des echten Bob: filepath.Join("data/users/<uid>/briefings",
// "../../bob/user.json") kappt "briefings" und "<uid>" und haengt "bob/
// user.json" an "data/users/" an -> data/users/bob/user.json. Empirisch
// bestaetigt (siehe Bericht an den Team-Lead): unguarded SaveTrip mit dieser
// ID ueberschreibt Bobs echte user.json tatsaechlich mit Trip-JSON.

// seedRealBob legt einen echten zweiten Nutzer "bob" an und liefert dessen
// user.json-Pfad plus den Inhalt VOR dem Angriff — Bezugspunkt fuer die
// Unveraendert-Pruefung nach jedem Direktaufruf.
func seedRealBob(t *testing.T) (s *Store, bobUserFile string, before []byte) {
	t.Helper()
	tmpDir := t.TempDir()
	bob := New(tmpDir, "bob")
	if err := bob.SaveUser(model.User{ID: "bob", PasswordHash: "bobs-real-hash", CreatedAt: time.Now()}); err != nil {
		t.Fatalf("SaveUser(bob): %v", err)
	}
	bobUserFile = filepath.Join(bob.UserDir("bob"), "user.json")
	before, err := os.ReadFile(bobUserFile)
	if err != nil {
		t.Fatalf("ReadFile(bob user.json) setup: %v", err)
	}
	// Aufrufender Store gehoert NICHT bob — Analogie zum HTTP-Fall, wo ein
	// beliebiger authentifizierter Nutzer (nie bob selbst) den Angriff fährt.
	return New(tmpDir, "alice"), bobUserFile, before
}

// -----------------------------------------------------------------------
// AC-8 — Guard im Store, direkter Aufruf unter Umgehung des Handlers
// -----------------------------------------------------------------------

func TestPathTraversal_StoreDirectTripCalls_RejectInvalidID_AC8(t *testing.T) {
	const attack = "../../bob/user"

	t.Run("SaveTrip", func(t *testing.T) {
		s, bobFile, before := seedRealBob(t)
		attackTrip := model.Trip{ID: attack, Name: "Angreifer-Trip"}
		err := s.SaveTrip(&attackTrip)
		if err == nil {
			t.Error("AC-8: SaveTrip mit Traversal-ID erwartet einen Fehler, bekam nil")
		}
		after, rerr := os.ReadFile(bobFile)
		if rerr != nil {
			t.Fatalf("ReadFile(bob user.json) after SaveTrip: %v", rerr)
		}
		if string(before) != string(after) {
			t.Errorf("AC-8: Bobs echte user.json wurde durch SaveTrip(%q) veraendert:\nvorher:  %s\nnachher: %s", attack, before, after)
		}
	})

	t.Run("LoadTrip", func(t *testing.T) {
		s, bobFile, before := seedRealBob(t)
		trip, err := s.LoadTrip(attack)
		if err == nil {
			t.Errorf("AC-8: LoadTrip(%q) erwartet einen Fehler, bekam trip=%+v err=nil", attack, trip)
		}
		after, rerr := os.ReadFile(bobFile)
		if rerr != nil {
			t.Fatalf("ReadFile(bob user.json) after LoadTrip: %v", rerr)
		}
		if string(before) != string(after) {
			t.Error("AC-8: LoadTrip darf Bobs user.json nicht veraendern")
		}
	})

	t.Run("DeleteTrip", func(t *testing.T) {
		s, bobFile, _ := seedRealBob(t)
		err := s.DeleteTrip(attack)
		if err == nil {
			t.Error("AC-8: DeleteTrip mit Traversal-ID erwartet einen Fehler, bekam nil")
		}
		if _, statErr := os.Stat(bobFile); statErr != nil {
			t.Errorf("AC-8: Bobs echte user.json darf durch DeleteTrip(%q) nicht verschwinden, Stat-Fehler: %v", attack, statErr)
		}
	})
}

// -----------------------------------------------------------------------
// ValidEntityID — Einheitsfaelle der Pruefung selbst
// -----------------------------------------------------------------------

func TestValidEntityID_RejectsUnsafeSegments(t *testing.T) {
	cases := []string{
		"",             // leer
		"/",            // reiner Trenner
		"a/b",          // enthaelt Trenner
		"\\",           // Backslash (Windows-Trenner)
		"a\\b",         // enthaelt Backslash
		"a\x00b",       // NUL-Byte eingebettet
		".",            // Punkt-Segment
		"..",           // Traversal-Segment
		"../x",         // beginnt mit Traversal
		"../../bob/user", // die im Kontext-Dokument nachgewiesene Ausbruchs-ID
		".hidden",      // fuehrender Punkt
	}
	for _, id := range cases {
		if ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = true, erwartet false (unsicheres Pfadsegment)", id)
		}
	}
}

// Positivkontrolle (PFLICHT, nicht "vereinfachen" — Spec-Praeambel AC-1..11):
// unterscheidet die Segment-Pruefung von der verworfenen ASCII-Whitelist.
// Bestandsorte mit Diakritika (docs/specs/modules/fix_2140_entitaets_id_pfadsperre.md,
// Abschnitt "Warum die ... ASCII-Whitelist verworfen wurde") muessen zulaessig bleiben.
func TestValidEntityID_AcceptsUnicodeLetters(t *testing.T) {
	cases := []string{
		"trip123",
		"cp-a1b2c3d4",
		"hochfügen",
		"pollença",
		"übergangsjoch-zillertal-arena",
		"serfaus-schöngamp-berg",
		"mühlbach",
	}
	for _, id := range cases {
		if !ValidEntityID(id) {
			t.Errorf("ValidEntityID(%q) = false, erwartet true (gueltiges Unicode-Pfadsegment ohne Trenner)", id)
		}
	}
}
