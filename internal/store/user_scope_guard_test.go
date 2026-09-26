// Waechter-Test fuer Issue #2151 Scheibe B (fail-closed Go-Store, AC-5/AC-6).
//
// Jede exportierte *Store-Methode muss hier entweder "guarded" (muss bei
// leerer Nutzerkennung fehlschlagen UND darf dabei keine Datei direkt unter
// dir/users/ anlegen) oder "exempt" (mit Begruendung) eingetragen sein. Eine
// neue exportierte Methode ohne Eintrag laesst TestStoreMethodRegisterHasParity
// fehlschlagen (AC-6) -- ohne die zentrale Pruefung requireUser() erst noch
// nachzubauen zu muessen.
package store

import (
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
)

// guardEntry ist EINE Zeile im Wächter-Register (AC-5/AC-6).
type guardEntry struct {
	// call ruft die Methode mit plausiblen Argumenten auf und liefert NUR den
	// Fehler zurück -- bei Mehrfach-Rückgaben werden die übrigen Werte
	// verworfen (Vorgabe: "bei Methoden mit Mehrfach-Rückgabe nur den error
	// auswerten").
	call func(s *Store) error
	// exemptReason ist bei "exempt"-Einträgen gesetzt; bei "guarded"-Einträgen
	// leer.
	exemptReason string
}

func guarded(call func(s *Store) error) guardEntry {
	return guardEntry{call: call}
}

func exempt(reason string) guardEntry {
	return guardEntry{exemptReason: reason}
}

// storeMethodRegister ordnet jede exportierte *Store-Methode ein (Issue
// #2151 Scheibe B, Spec "Implementation Details" Punkt 2).
var storeMethodRegister = map[string]guardEntry{
	// --- guarded: bauen (direkt oder transitiv) einen Pfad aus s.UserID -----
	"LoadGroups":  guarded(func(s *Store) error { _, err := s.LoadGroups(); return err }),
	"SaveGroup":   guarded(func(s *Store) error { return s.SaveGroup(model.Group{ID: "g1", Name: "G1"}) }),
	"DeleteGroup": guarded(func(s *Store) error { return s.DeleteGroup("g1") }),

	"LoadLocations":  guarded(func(s *Store) error { _, err := s.LoadLocations(); return err }),
	"LoadLocation":   guarded(func(s *Store) error { _, err := s.LoadLocation("loc1"); return err }),
	"SaveLocation":   guarded(func(s *Store) error { return s.SaveLocation(model.Location{ID: "loc1", Name: "Loc"}) }),
	"DeleteLocation": guarded(func(s *Store) error { return s.DeleteLocation("loc1") }),

	"LoadMetricPresets": guarded(func(s *Store) error { _, err := s.LoadMetricPresets(); return err }),
	"SaveMetricPresets": guarded(func(s *Store) error {
		return s.SaveMetricPresets([]model.MetricPreset{{ID: "p1", Name: "P1"}})
	}),

	"LoadBriefing": guarded(func(s *Store) error { _, err := s.LoadBriefing("b1"); return err }),
	"SaveBriefing": guarded(func(s *Store) error {
		return s.SaveBriefing(&model.BriefingSubscription{ID: "b1", Kind: "route"})
	}),

	"LoadTrips":  guarded(func(s *Store) error { _, err := s.LoadTrips(); return err }),
	"LoadTrip":   guarded(func(s *Store) error { _, err := s.LoadTrip("t1"); return err }),
	"SaveTrip":   guarded(func(s *Store) error { return s.SaveTrip(&model.Trip{ID: "t1", Name: "T1"}) }),
	"DeleteTrip": guarded(func(s *Store) error { return s.DeleteTrip("t1") }),

	"LoadComparePresets": guarded(func(s *Store) error { _, err := s.LoadComparePresets(); return err }),
	"LoadComparePreset":  guarded(func(s *Store) error { _, err := s.LoadComparePreset("c1"); return err }),
	"SaveComparePreset": guarded(func(s *Store) error {
		return s.SaveComparePreset(model.ComparePreset{ID: "c1", Name: "C1"})
	}),
	"SaveComparePresets": guarded(func(s *Store) error {
		return s.SaveComparePresets([]model.ComparePreset{{ID: "c1", Name: "C1"}})
	}),
	"DeleteComparePreset": guarded(func(s *Store) error { return s.DeleteComparePreset("c1") }),

	"BriefingFingerprint": guarded(func(s *Store) error { _, err := s.BriefingFingerprint("b1"); return err }),

	"LoadBriefingLog":     guarded(func(s *Store) error { _, err := s.LoadBriefingLog(); return err }),
	"LoadAlertLog":        guarded(func(s *Store) error { _, err := s.LoadAlertLog(); return err }),
	"BriefingCountByTrip": guarded(func(s *Store) error { _, err := s.BriefingCountByTrip(); return err }),
	"AlertCountByEntity":  guarded(func(s *Store) error { _, err := s.AlertCountByEntity(); return err }),

	// --- exempt: Kennung als expliziter Parameter, kein Pfad aus s.UserID ---
	"LoadUser":                exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"SaveUser":                exempt("Kennung als expliziter Parameter (user.ID), nicht s.UserID"),
	"SetUserTier":             exempt("Kennung als expliziter Parameter id, nicht s.UserID (#2423)"),
	"UserExists":              exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"ListUserIDs":             exempt("baut keinen Pfad aus s.UserID — listet alle Nutzer"),
	"UserDir":                 exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"ProvisionUserDirs":       exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"DeleteUser":              exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"ExportUser":              exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"SaveResetToken":          exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"LoadResetToken":          exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"DeleteResetToken":        exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"SaveLinkCode":            exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"LoadLinkCode":            exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"SaveVerificationToken":   exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"LoadVerificationToken":   exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"DeleteVerificationToken": exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	// Issue #2406 — SMS-Bestaetigungscode, Bauart wie die drei Zeilen darueber.
	"SaveSmsVerification":      exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"LoadSmsVerification":      exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"DeleteSmsVerification":    exempt("Kennung als expliziter Parameter, nicht s.UserID"),
	"FindUserByOAuthSub":       exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),
	"FindUserByTelegramChatID": exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),

	"AddSession":    exempt("Kennung als expliziter Parameter (userId), nicht s.UserID"),
	"RemoveSession": exempt("Kennung als expliziter Parameter (userId), nicht s.UserID"),
	"ClearSessions": exempt("Kennung als expliziter Parameter (userId), nicht s.UserID"),
	"LoadSessions":  exempt("Kennung als expliziter Parameter (userId), nicht s.UserID"),
	"HasSession":    exempt("Kennung als expliziter Parameter (userId), nicht s.UserID"),

	"CountAddressCollisions":       exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),
	"LogAddressCollisions":         exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),
	"ResolveAddressOwner":          exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),
	"IsAddressTakenByOtherAccount": exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),

	"MigrateClearPremiumSmsReplyAddresses": exempt("iteriert über ListUserIDs/LoadUser(id), nicht s.UserID"),

	"WithUser":     exempt("baut keinen Pfad, liefert nur eine Kopie mit anderer Kennung"),
	"LockBriefing": exempt("baut keinen Dateipfad, nur einen In-Memory-Sperrschlüssel"),

	"LocationsDir": exempt("dokumentierter Rest: kein error-Rückgabewert, produktiv außerhalb des Stores unbenutzt"),
	"PresetsFile":  exempt("dokumentierter Rest: kein error-Rückgabewert, produktiv außerhalb des Stores unbenutzt"),
	"BriefingsDir": exempt("dokumentierter Rest: kein error-Rückgabewert, produktiv außerhalb des Stores unbenutzt"),
}

// exportedStoreMethodNames liefert alle exportierten Methodennamen von
// *Store per Reflection -- die Ist-Seite der Parität.
func exportedStoreMethodNames() []string {
	t := reflect.TypeOf(&Store{})
	names := make([]string, 0, t.NumMethod())
	for i := 0; i < t.NumMethod(); i++ {
		m := t.Method(i)
		if m.PkgPath == "" { // PkgPath leer == exportiert
			names = append(names, m.Name)
		}
	}
	return names
}

// missingRegisterEntries vergleicht eine Liste von Methodennamen gegen ein
// Register: missing = Methoden ohne Eintrag, stale = Einträge ohne
// zugehörige Methode (Karteileichen). Eigenständig testbar mit einer
// synthetischen Liste (AC-6), unabhängig vom echten *Store.
func missingRegisterEntries(methodNames []string, register map[string]guardEntry) (missing, stale []string) {
	present := map[string]bool{}
	for _, n := range methodNames {
		present[n] = true
		if _, ok := register[n]; !ok {
			missing = append(missing, n)
		}
	}
	for n := range register {
		if !present[n] {
			stale = append(stale, n)
		}
	}
	sort.Strings(missing)
	sort.Strings(stale)
	return missing, stale
}

// TestStoreMethodRegisterHasParity haelt storeMethodRegister gegen die
// tatsächlichen exportierten *Store-Methoden gegen. Eine neue Methode ohne
// Eintrag laesst diesen Test fehlschlagen (AC-6).
func TestStoreMethodRegisterHasParity(t *testing.T) {
	missing, stale := missingRegisterEntries(exportedStoreMethodNames(), storeMethodRegister)
	if len(missing) > 0 {
		t.Errorf("exportierte Store-Methoden ohne Registereintrag: %v", missing)
	}
	if len(stale) > 0 {
		t.Errorf("Registereinträge ohne zugehörige Store-Methode (Karteileichen): %v", stale)
	}
}

// TestNewExportedMethodWithoutRegisterEntryFails ist die Mutations-Fixture
// aus AC-6: eine synthetische Methodenliste mit einer Methode ohne
// Registereintrag muss von missingRegisterEntries gemeldet werden -- geprüft
// unabhängig vom echten *Store, damit die Prüf-LOGIK selbst nachgewiesen ist.
func TestNewExportedMethodWithoutRegisterEntryFails(t *testing.T) {
	synthetic := []string{"LoadGroups", "SaveGroup", "NeueMethodeOhneEintrag"}
	fakeRegister := map[string]guardEntry{
		"LoadGroups": guarded(func(s *Store) error { return nil }),
		"SaveGroup":  guarded(func(s *Store) error { return nil }),
	}
	missing, _ := missingRegisterEntries(synthetic, fakeRegister)
	if len(missing) != 1 || missing[0] != "NeueMethodeOhneEintrag" {
		t.Fatalf("erwartet genau ['NeueMethodeOhneEintrag'] als fehlend, bekommen: %v", missing)
	}
}

// TestGuardedMethodsRejectEmptyUserID prüft AC-5: jede guarded-Methode muss
// auf einem Store ohne Nutzerkennung mit ErrInvalidUserID scheitern. Jede
// Methode läuft als eigener Subtest auf einem frischen Store (Vorgabe: "die
// Annahme 'ein Lese-Guard deckt automatisch die Schreib-Methode mit ab' wird
// damit GEMESSEN, nicht nur behauptet").
func TestGuardedMethodsRejectEmptyUserID(t *testing.T) {
	for name, entry := range storeMethodRegister {
		if entry.call == nil {
			continue // exempt
		}
		name, entry := name, entry
		t.Run(name, func(t *testing.T) {
			s := New(t.TempDir(), "")
			err := entry.call(s)
			if !errors.Is(err, ErrInvalidUserID) {
				t.Fatalf("%s: erwartet ErrInvalidUserID, bekommen: %v", name, err)
			}
		})
	}
}

// TestGuardedMethodsCreateNoFileOutsideUserDir prüft den zweiten Teil von
// AC-5: nach dem Aufruf einer guarded-Methode auf einem Store ohne
// Nutzerkennung darf unter dir/users/ keine Datei/kein Ordner entstanden
// sein (z. B. keine "users/groups.json" statt "users/<id>/groups.json").
// users/ existiert VOR dem Aufruf schon, damit Schreibpfade tatsächlich
// schreiben würden statt trivial an einem fehlenden Elternordner zu scheitern.
func TestGuardedMethodsCreateNoFileOutsideUserDir(t *testing.T) {
	for name, entry := range storeMethodRegister {
		if entry.call == nil {
			continue // exempt
		}
		name, entry := name, entry
		t.Run(name, func(t *testing.T) {
			dir := t.TempDir()
			if err := os.MkdirAll(filepath.Join(dir, "users"), 0755); err != nil {
				t.Fatalf("setup mkdir users/: %v", err)
			}
			s := New(dir, "")
			_ = entry.call(s)

			entries, err := os.ReadDir(filepath.Join(dir, "users"))
			if err != nil {
				t.Fatalf("users/ lesen: %v", err)
			}
			if len(entries) != 0 {
				names := make([]string, len(entries))
				for i, e := range entries {
					names[i] = e.Name()
				}
				t.Fatalf("%s hat Eintrag(e) direkt unter users/ erzeugt: %v", name, names)
			}
		})
	}
}
