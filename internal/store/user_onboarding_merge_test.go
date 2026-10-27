package store

// TDD RED — Onboarding S2: Merge-Setter fuer die Onboarding-Felder.
// Spec: docs/specs/modules/onboarding_willkommen_checkliste.md — AC-7
// (Store-Roundtrip), Grundlage fuer AC-4/5/11.
//
// Festgelegte Signaturen (Muster SetUserDisabled, ueber mergeUserJSON):
//
//	func (s *Store) SetUserOnboardingFlags(id string, onboardingDismissed, checklistDismissed *bool) error
//	func (s *Store) SetUserTestMailSentAt(id string, at time.Time) error
//
// nil-Zeiger = Flag unberuehrt. Beide schreiben NUR ihre Schluessel; ein
// unbekanntes Fremdfeld und alle Nachbarfelder der Altdatei bleiben erhalten.
// Fuer eine fehlende user.json legen sie nichts an (Fehler statt Neuanlage).
// Vergleich inhaltlich (MarshalIndent rueckt verschachtelte Werte neu ein).

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

func onbStoreAltdatei(t *testing.T, s *Store, id string) map[string]json.RawMessage {
	t.Helper()
	m := map[string]interface{}{
		"id":                       id,
		"email":                    id + "@example.com",
		"password_hash":            "$2a$04$abcdefghijklmnopqrstuv",
		"created_at":               "2026-06-01T12:00:00Z",
		"mail_to":                  id + "@example.com",
		"telegram_chat_id":         "4242",
		"tier":                     "standard",
		"passkey_prompt_dismissed": true,
		"email_verified_at":        "2026-07-01T08:30:00Z",
		"zukunftsfeld":             map[string]interface{}{"x": 1, "liste": []interface{}{"a", "b"}},
	}
	dir := s.UserDir(id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.MarshalIndent(m, "", "  ")
	if err := os.WriteFile(filepath.Join(dir, "user.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
	return onbStoreRaw(t, s, id)
}

func onbStoreRaw(t *testing.T, s *Store, id string) map[string]json.RawMessage {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json von %q nicht lesbar: %v", id, err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("user.json kein JSON: %v", err)
	}
	return m
}

func onbStoreEqual(a, b json.RawMessage) bool {
	var va, vb interface{}
	if json.Unmarshal(a, &va) != nil || json.Unmarshal(b, &vb) != nil {
		return false
	}
	return reflect.DeepEqual(va, vb)
}

// onbStoreUnveraendert: jeder Schluessel aus vorher steht inhaltlich gleich in
// nachher, ausser den ausdruecklich erlaubten.
func onbStoreUnveraendert(t *testing.T, ac string, vorher, nachher map[string]json.RawMessage, erlaubt ...string) {
	t.Helper()
	ok := map[string]bool{}
	for _, k := range erlaubt {
		ok[k] = true
	}
	for k, alt := range vorher {
		if ok[k] {
			continue
		}
		neu, da := nachher[k]
		if !da {
			t.Errorf("%s: Schluessel %q ging verloren (vorher %s)", ac, k, alt)
			continue
		}
		if !onbStoreEqual(alt, neu) {
			t.Errorf("%s: Schluessel %q veraendert: %s -> %s", ac, k, alt, neu)
		}
	}
}

func onbTrue() *bool  { v := true; return &v }
func onbFalse() *bool { v := false; return &v }

// AC-7: SetUserOnboardingFlags einzeln — nur das gesetzte Flag, Rest erhalten.
func TestSetUserOnboardingFlagsMergesSingleFlag(t *testing.T) {
	s := New(t.TempDir(), "test")
	const uid = "flora2521"
	vorher := onbStoreAltdatei(t, s, uid)

	if err := s.SetUserOnboardingFlags(uid, onbTrue(), nil); err != nil {
		t.Fatalf("SetUserOnboardingFlags: %v", err)
	}
	nach1 := onbStoreRaw(t, s, uid)
	if string(nach1["onboarding_dismissed"]) != "true" {
		t.Errorf("AC-7: onboarding_dismissed nicht true: %s", nach1["onboarding_dismissed"])
	}
	if v, da := nach1["checklist_dismissed"]; da && string(v) != "false" {
		t.Errorf("AC-7: checklist_dismissed mitgesetzt (%s), obwohl nil uebergeben", v)
	}
	onbStoreUnveraendert(t, "AC-7 (onboarding_dismissed)", vorher, nach1, "onboarding_dismissed")

	if err := s.SetUserOnboardingFlags(uid, nil, onbTrue()); err != nil {
		t.Fatalf("SetUserOnboardingFlags: %v", err)
	}
	nach2 := onbStoreRaw(t, s, uid)
	if string(nach2["checklist_dismissed"]) != "true" {
		t.Errorf("AC-7: checklist_dismissed nicht true: %s", nach2["checklist_dismissed"])
	}
	if string(nach2["onboarding_dismissed"]) != "true" {
		t.Errorf("AC-7: zweiter Aufruf (nur checklist) hat onboarding_dismissed veraendert: %s", nach2["onboarding_dismissed"])
	}
	onbStoreUnveraendert(t, "AC-7 (checklist_dismissed)", vorher, nach2, "onboarding_dismissed", "checklist_dismissed")

	// Zuruecksetzen mit false: Flag gilt danach als false (fehlt oder false).
	if err := s.SetUserOnboardingFlags(uid, onbFalse(), nil); err != nil {
		t.Fatalf("SetUserOnboardingFlags(false): %v", err)
	}
	if v, da := onbStoreRaw(t, s, uid)["onboarding_dismissed"]; da && string(v) != "false" {
		t.Errorf("AC-7: onboarding_dismissed nach false = %s", v)
	}

	// Typisiert gelesen: LoadUser kennt die Felder.
	u, err := s.LoadUser(uid)
	if err != nil || u == nil {
		t.Fatalf("LoadUser: %v", err)
	}
	if !u.ChecklistDismissed || u.OnboardingDismissed {
		t.Errorf("AC-7: LoadUser liest ChecklistDismissed=%v OnboardingDismissed=%v, erwartet true/false",
			u.ChecklistDismissed, u.OnboardingDismissed)
	}
}

// AC-7: SetUserTestMailSentAt einzeln — Zeitstempel RFC3339, Rest erhalten.
func TestSetUserTestMailSentAtMergesTimestamp(t *testing.T) {
	s := New(t.TempDir(), "test")
	const uid = "timo2521"
	vorher := onbStoreAltdatei(t, s, uid)
	at := time.Date(2026, 10, 16, 9, 41, 7, 0, time.UTC)

	if err := s.SetUserTestMailSentAt(uid, at); err != nil {
		t.Fatalf("SetUserTestMailSentAt: %v", err)
	}
	nach := onbStoreRaw(t, s, uid)
	var str string
	if err := json.Unmarshal(nach["test_mail_sent_at"], &str); err != nil {
		t.Fatalf("AC-7: test_mail_sent_at fehlt oder ist kein String: %s", nach["test_mail_sent_at"])
	}
	if got, err := time.Parse(time.RFC3339Nano, str); err != nil || !got.Equal(at) {
		t.Errorf("AC-7: test_mail_sent_at=%q, erwartet %s", str, at.Format(time.RFC3339))
	}
	onbStoreUnveraendert(t, "AC-7 (test_mail_sent_at)", vorher, nach, "test_mail_sent_at")

	u, err := s.LoadUser(uid)
	if err != nil || u == nil || u.TestMailSentAt == nil || !u.TestMailSentAt.Equal(at) {
		t.Errorf("AC-7: LoadUser liest TestMailSentAt nicht zurueck: %+v (%v)", u, err)
	}
}

// AC-7: beide Setter nacheinander — keiner loescht das Ergebnis des anderen,
// das Fremdfeld ueberlebt beide.
func TestOnboardingSettersTogetherPreserveEachOtherAndForeignField(t *testing.T) {
	s := New(t.TempDir(), "test")
	const uid = "beide2521"
	vorher := onbStoreAltdatei(t, s, uid)
	at := time.Date(2026, 10, 16, 10, 0, 0, 0, time.UTC)

	if err := s.SetUserTestMailSentAt(uid, at); err != nil {
		t.Fatalf("SetUserTestMailSentAt: %v", err)
	}
	if err := s.SetUserOnboardingFlags(uid, onbTrue(), onbTrue()); err != nil {
		t.Fatalf("SetUserOnboardingFlags: %v", err)
	}
	nach := onbStoreRaw(t, s, uid)
	if string(nach["onboarding_dismissed"]) != "true" || string(nach["checklist_dismissed"]) != "true" {
		t.Errorf("AC-7: Flags nicht beide true: %s / %s", nach["onboarding_dismissed"], nach["checklist_dismissed"])
	}
	if _, da := nach["test_mail_sent_at"]; !da {
		t.Errorf("AC-7: SetUserOnboardingFlags hat test_mail_sent_at geloescht")
	}
	onbStoreUnveraendert(t, "AC-7 (zusammen)", vorher, nach,
		"onboarding_dismissed", "checklist_dismissed", "test_mail_sent_at")
}

// Fehlende user.json: kein Anlegen eines Rumpfprofils; ungueltige Kennung
// wird abgewiesen (Pfad-Schutz wie mergeUserJSON).
func TestOnboardingSettersDoNotCreateMissingUserAndRejectInvalidID(t *testing.T) {
	s := New(t.TempDir(), "test")

	if err := s.SetUserOnboardingFlags("gibtsnicht", onbTrue(), nil); err == nil {
		t.Errorf("SetUserOnboardingFlags fuer fehlendes Konto: Fehler erwartet")
	}
	if err := s.SetUserTestMailSentAt("gibtsnicht", time.Now()); err == nil {
		t.Errorf("SetUserTestMailSentAt fuer fehlendes Konto: Fehler erwartet")
	}
	if _, err := os.Stat(filepath.Join(s.UserDir("gibtsnicht"), "user.json")); err == nil {
		t.Errorf("Setter haben fuer ein fehlendes Konto eine user.json angelegt")
	}
	if err := s.SetUserOnboardingFlags("../boese", onbTrue(), nil); !errors.Is(err, ErrInvalidUserID) {
		t.Errorf("SetUserOnboardingFlags(../boese): ErrInvalidUserID erwartet, bekommen %v", err)
	}
	if err := s.SetUserTestMailSentAt("../boese", time.Now()); !errors.Is(err, ErrInvalidUserID) {
		t.Errorf("SetUserTestMailSentAt(../boese): ErrInvalidUserID erwartet, bekommen %v", err)
	}
}

// Fix-Loop 1 (F006) — LoadFirstBriefingAt liest nur unter einer GUELTIGEN
// Kennung. Mit "../x" (Pfad-Ausbruch) liefert es "" und liest nichts ausserhalb
// des Nutzerordners, auch wenn dort eine passende Datei liegt.
//
// Mutation, die hier rot werden MUSS: die ValidUserID-Pruefung entfernen.
func TestLoadFirstBriefingAtRejectsInvalidUserID(t *testing.T) {
	s := New(t.TempDir(), "test")
	// Koeder: eine Ebene ueber dem Nutzerordner von "a" liegt der Ordner "x";
	// "../x" aus <users>/<id>/ ... wuerde ihn erreichen. Positivkontrolle gleich mit.
	koeder := filepath.Join(s.UserDir("x"), "first_briefing.json")
	if err := os.MkdirAll(filepath.Dir(koeder), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(koeder, []byte(`{"first_briefing_at":"2026-01-01T00:00:00Z"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	if got := s.LoadFirstBriefingAt("x"); got != "2026-01-01T00:00:00Z" {
		t.Fatalf("Positivkontrolle: gueltige Kennung liest nicht (%q)", got)
	}
	// Koeder dort, wohin "../x" tatsaechlich aufloest (ausserhalb von users/),
	// und Zwischenordner "a" fuer "a/../x".
	for _, dir := range []string{s.UserDir("../x"), s.UserDir("a")} {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(s.UserDir("../x"), "first_briefing.json"),
		[]byte(`{"first_briefing_at":"2026-01-01T00:00:00Z"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, bad := range []string{"../x", "a/../x", "x/../x", ""} {
		if got := s.LoadFirstBriefingAt(bad); got != "" {
			t.Errorf("LoadFirstBriefingAt(%q) = %q, erwartet \"\" (ungueltige Kennung)", bad, got)
		}
	}
}

// AC-8: ein zweiter Aufruf ersetzt den bisherigen Zeitstempel (kein
// "nur beim ersten Mal setzen").
func TestSetUserTestMailSentAtOverwritesEarlierTimestamp(t *testing.T) {
	s := New(t.TempDir(), "test")
	const uid = "timo2521neu"
	onbStoreAltdatei(t, s, uid)
	frueher := time.Date(2026, 10, 1, 8, 0, 0, 0, time.UTC)
	spaeter := time.Date(2026, 10, 17, 9, 30, 0, 0, time.UTC)

	if err := s.SetUserTestMailSentAt(uid, frueher); err != nil {
		t.Fatalf("SetUserTestMailSentAt (1): %v", err)
	}
	if err := s.SetUserTestMailSentAt(uid, spaeter); err != nil {
		t.Fatalf("SetUserTestMailSentAt (2): %v", err)
	}
	u, err := s.LoadUser(uid)
	if err != nil || u == nil || u.TestMailSentAt == nil || !u.TestMailSentAt.Equal(spaeter) {
		t.Errorf("AC-8: zweiter Aufruf muss den Zeitstempel ersetzen, gelesen: %+v (%v)", u, err)
	}
}
