package store

// TDD RED — Issue #2687 (ADR-0101): SaveUser = Read-Modify-Write mit Merge.
// Spec: docs/specs/modules/saveuser_merge.md — AC-1 bis AC-7.
//
// SaveUser darf dem Modell unbekannte Felder der vorhandenen user.json nicht
// mehr verwerfen. Gesetzte bekannte Felder werden aktualisiert, leere
// omitempty-Felder verschwinden (nicht wiederbelebt).

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func smRawLesen(t *testing.T, s *Store, id string) map[string]json.RawMessage {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(s.UserDir(id), "user.json"))
	if err != nil {
		t.Fatalf("user.json lesen: %v", err)
	}
	var m map[string]json.RawMessage
	if err := json.Unmarshal(data, &m); err != nil {
		t.Fatalf("user.json kein JSON-Objekt: %v", err)
	}
	return m
}

func smAltdatei(t *testing.T, s *Store, id string, extra map[string]interface{}) {
	t.Helper()
	m := map[string]interface{}{
		"id":         id,
		"email":      id + "@example.com",
		"created_at": "2026-06-01T12:00:00Z",
	}
	for k, v := range extra {
		m[k] = v
	}
	dir := s.UserDir(id)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	data, _ := json.MarshalIndent(m, "", "  ")
	if err := os.WriteFile(filepath.Join(dir, "user.json"), data, 0o644); err != nil {
		t.Fatal(err)
	}
}

func smFremdfeld() map[string]interface{} {
	return map[string]interface{}{"x": 1, "liste": []interface{}{"a", "b"}}
}

func smGleichJSON(t *testing.T, got json.RawMessage, want interface{}) bool {
	t.Helper()
	var a, b interface{}
	if err := json.Unmarshal(got, &a); err != nil {
		t.Fatal(err)
	}
	w, _ := json.Marshal(want)
	_ = json.Unmarshal(w, &b)
	return reflect.DeepEqual(a, b)
}

// AC-1: Fremdfeld bleibt, display_name wird aktualisiert.
func TestSaveUserMerge_AC1_FremdfeldBleibtErhalten(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	smAltdatei(t, s, "alice", map[string]interface{}{"zukunftsfeld": smFremdfeld()})

	u, err := s.LoadUser("alice")
	if err != nil || u == nil {
		t.Fatalf("LoadUser: %v %v", u, err)
	}
	u.DisplayName = "Alice Neu"
	if err := s.SaveUser(*u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	m := smRawLesen(t, s, "alice")
	raw, ok := m["zukunftsfeld"]
	if !ok {
		t.Fatal("Fremdfeld 'zukunftsfeld' ging bei SaveUser verloren (Datenverlust)")
	}
	if !smGleichJSON(t, raw, smFremdfeld()) {
		t.Errorf("Fremdfeld verändert: %s", raw)
	}
	var dn string
	_ = json.Unmarshal(m["display_name"], &dn)
	if dn != "Alice Neu" {
		t.Errorf("display_name = %q, erwartet %q", dn, "Alice Neu")
	}
}

// AC-2: leeres omitempty-Feld wird entfernt, Fremdfeld bleibt.
func TestSaveUserMerge_AC2_LeeresOmitemptyFeldNichtWiederbelebt(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	smAltdatei(t, s, "bob", map[string]interface{}{
		"pending_sms_to": "+491701234567",
		"zukunftsfeld":   smFremdfeld(),
	})

	u, err := s.LoadUser("bob")
	if err != nil || u == nil {
		t.Fatalf("LoadUser: %v %v", u, err)
	}
	u.PendingSmsTo = ""
	if err := s.SaveUser(*u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	m := smRawLesen(t, s, "bob")
	if _, da := m["pending_sms_to"]; da {
		t.Error("pending_sms_to wurde wiederbelebt, obwohl das Modell es geleert hat")
	}
	if _, da := m["zukunftsfeld"]; !da {
		t.Error("Fremdfeld 'zukunftsfeld' ging verloren (Datenverlust)")
	}
}

// AC-3: Erstanlage ohne Datei und ohne Verzeichnis, Round-Trip über LoadUser.
func TestSaveUserMerge_AC3_ErstanlageOhneDatei(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	u := model.User{
		ID:          "carol",
		Email:       "carol@example.com",
		DisplayName: "Carol",
		CreatedAt:   time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC),
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser Erstanlage: %v", err)
	}
	got, err := s.LoadUser("carol")
	if err != nil || got == nil {
		t.Fatalf("LoadUser: %v %v", got, err)
	}
	if got.Email != u.Email || got.DisplayName != u.DisplayName || !got.CreatedAt.Equal(u.CreatedAt) {
		t.Errorf("Round-Trip abweichend: %+v", got)
	}
}

// AC-4: Kaputte Altdatei darf das Speichern nicht blockieren.
func TestSaveUserMerge_AC4_KaputteDateiBleibtSpeicherbar(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	dir := s.UserDir("dave")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte("{{{ kein json"), 0o644); err != nil {
		t.Fatal(err)
	}
	u := model.User{
		ID:        "dave",
		Email:     "dave@example.com",
		CreatedAt: time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC),
	}
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser darf bei kaputter Datei nicht fehlschlagen: %v", err)
	}
	got, err := s.LoadUser("dave")
	if err != nil || got == nil || got.Email != "dave@example.com" {
		t.Fatalf("LoadUser nach Reparatur: %+v %v", got, err)
	}
}

// AC-5: Mandantentrennung — Datei von B bleibt byte-identisch.
func TestSaveUserMerge_AC5_ZweiNutzerGetrennt(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	smAltdatei(t, s, "erika", map[string]interface{}{"fremd_a": "A-Wert"})
	smAltdatei(t, s, "frank", map[string]interface{}{"fremd_b": "B-Wert"})
	vorher, err := os.ReadFile(filepath.Join(s.UserDir("frank"), "user.json"))
	if err != nil {
		t.Fatal(err)
	}

	a, err := s.LoadUser("erika")
	if err != nil || a == nil {
		t.Fatalf("LoadUser: %v %v", a, err)
	}
	a.DisplayName = "Erika Neu"
	if err := s.SaveUser(*a); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	nachher, _ := os.ReadFile(filepath.Join(s.UserDir("frank"), "user.json"))
	if !bytes.Equal(vorher, nachher) {
		t.Error("Datei von Nutzer B wurde durch SaveUser(A) verändert")
	}
	mA := smRawLesen(t, s, "erika")
	if _, da := mA["fremd_a"]; !da {
		t.Error("Fremdfeld von A ging verloren (Datenverlust)")
	}
	if _, da := mA["fremd_b"]; da {
		t.Error("Fremdfeld von B ist in A gelandet (Cross-User-Leck)")
	}
}

// AC-6: passkey_credentials wird als Ganzes ersetzt, Fremdfeld bleibt.
func TestSaveUserMerge_AC6_PasskeyAlsGanzesErsetzt(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	smAltdatei(t, s, "gina", map[string]interface{}{
		"zukunftsfeld": smFremdfeld(),
		"passkey_credentials": []interface{}{
			map[string]interface{}{"id": "AQID", "label": "alt", "unbekanntes_unterfeld": "weg"},
		},
	})

	u, err := s.LoadUser("gina")
	if err != nil || u == nil {
		t.Fatalf("LoadUser: %v %v", u, err)
	}
	if len(u.PasskeyCredentials) != 1 {
		t.Fatalf("Passkey nicht geladen: %+v", u.PasskeyCredentials)
	}
	u.PasskeyCredentials[0].Label = "neu"
	if err := s.SaveUser(*u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}

	m := smRawLesen(t, s, "gina")
	if _, da := m["zukunftsfeld"]; !da {
		t.Error("Fremdfeld 'zukunftsfeld' ging verloren (Datenverlust)")
	}
	var creds []map[string]interface{}
	if err := json.Unmarshal(m["passkey_credentials"], &creds); err != nil || len(creds) != 1 {
		t.Fatalf("passkey_credentials unlesbar: %v %s", err, m["passkey_credentials"])
	}
	if creds[0]["label"] != "neu" {
		t.Errorf("label = %v, erwartet neu", creds[0]["label"])
	}
	if _, da := creds[0]["unbekanntes_unterfeld"]; da {
		t.Error("Unterfeld im Passkey-Eintrag blieb erhalten, Schlüssel gehört aber dem Modell (Grenze laut Spec)")
	}
}

// AC-7: Round-Trip eines gefüllten Nutzers plus Fremdfeld-Erhalt über den Merge.
func TestSaveUserMerge_AC7_RoundTripVollerNutzer(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	jetzt := time.Date(2026, 7, 1, 8, 30, 0, 0, time.UTC)
	u := model.User{
		ID:                     "hans",
		Email:                  "hans@example.com",
		PasswordHash:           "$2a$04$abcdefghijklmnopqrstuv",
		CreatedAt:              time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC),
		MailTo:                 "hans@example.com",
		SmsTo:                  "+491701234567",
		TelegramChatID:         "4242",
		DisplayName:            "Hans",
		Tier:                   "standard",
		EmailVerifiedAt:        &jetzt,
		PasskeyPromptDismissed: true,
		PendingSmsTo:           "+491709999999",
		Disabled:               true,
		OnboardingDismissed:    true,
		Language:               "en",
	}
	smAltdatei(t, s, "hans", map[string]interface{}{"zukunftsfeld": smFremdfeld()})
	if err := s.SaveUser(u); err != nil {
		t.Fatalf("SaveUser: %v", err)
	}
	got, err := s.LoadUser("hans")
	if err != nil || got == nil {
		t.Fatalf("LoadUser: %v %v", got, err)
	}
	if !reflect.DeepEqual(*got, u) {
		t.Errorf("Round-Trip abweichend:\n got=%+v\nwant=%+v", *got, u)
	}
	if _, da := smRawLesen(t, s, "hans")["zukunftsfeld"]; !da {
		t.Error("Fremdfeld ging im Round-Trip verloren (Datenverlust)")
	}
}

// AC-4 (F001): user.json enthält exakt `null` -> wie kaputte Datei behandeln,
// kein Fehler, keine Panic, Modellstand wird geschrieben.
func TestSaveUserMerge_AC4_NullDateiBleibtSpeicherbar(t *testing.T) {
	s := &Store{DataDir: t.TempDir()}
	dir := s.UserDir("ida")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "user.json"), []byte("null"), 0o644); err != nil {
		t.Fatal(err)
	}
	u := model.User{
		ID:          "ida",
		Email:       "ida@example.com",
		DisplayName: "Ida",
		CreatedAt:   time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC),
	}
	func() {
		defer func() {
			if r := recover(); r != nil {
				t.Fatalf("SaveUser panict bei user.json = null: %v", r)
			}
		}()
		if err := s.SaveUser(u); err != nil {
			t.Fatalf("SaveUser darf bei user.json = null nicht fehlschlagen: %v", err)
		}
	}()
	got, err := s.LoadUser("ida")
	if err != nil || got == nil {
		t.Fatalf("LoadUser: %+v %v", got, err)
	}
	if got.Email != u.Email || got.DisplayName != u.DisplayName || !got.CreatedAt.Equal(u.CreatedAt) {
		t.Errorf("LoadUser nach null-Datei abweichend: %+v", got)
	}
}

// Implementierungsdetail (Adversary-Befund F002, Schutz der Bestandsdaten nach
// ADR-0101): Lesefehler außer „Datei fehlt" -> Fehler statt Überschreiben.
func TestSaveUserMerge_LesefehlerUeberschreibtNicht(t *testing.T) {
	u := model.User{
		ID:        "jana",
		Email:     "jana@example.com",
		CreatedAt: time.Date(2026, 6, 1, 12, 0, 0, 0, time.UTC),
	}

	t.Run("nicht_lesbar", func(t *testing.T) {
		if os.Geteuid() == 0 {
			t.Skip("als root sind Dateirechte wirkungslos")
		}
		s := &Store{DataDir: t.TempDir()}
		smAltdatei(t, s, "jana", map[string]interface{}{"zukunftsfeld": smFremdfeld()})
		path := filepath.Join(s.UserDir("jana"), "user.json")
		vorher, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		if err := os.Chmod(path, 0o000); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() { _ = os.Chmod(path, 0o644) })

		if err := s.SaveUser(u); err == nil {
			t.Error("SaveUser muss bei nicht lesbarer user.json einen Fehler liefern")
		}
		if err := os.Chmod(path, 0o644); err != nil {
			t.Fatal(err)
		}
		nachher, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("user.json nach SaveUser nicht mehr lesbar: %v", err)
		}
		if !bytes.Equal(vorher, nachher) {
			t.Errorf("nicht lesbare user.json wurde überschrieben (Datenverlust):\n%s", nachher)
		}
	})

	t.Run("verzeichnis", func(t *testing.T) {
		s := &Store{DataDir: t.TempDir()}
		path := filepath.Join(s.UserDir("jana"), "user.json")
		if err := os.MkdirAll(path, 0o755); err != nil {
			t.Fatal(err)
		}
		if err := s.SaveUser(u); err == nil {
			t.Error("SaveUser muss einen Fehler liefern, wenn user.json ein Verzeichnis ist")
		}
		fi, err := os.Stat(path)
		if err != nil || !fi.IsDir() {
			t.Errorf("user.json-Verzeichnis wurde ersetzt: %v %v", fi, err)
		}
	})
}

// F003: userJSONKeys liefert die reinen JSON-Schlüssel der Top-Level-Felder.
func TestSaveUserMerge_UserJSONKeysSindReineTagNamen(t *testing.T) {
	keys := userJSONKeys()
	menge := map[string]bool{}
	for _, k := range keys {
		if k == "" || k == "-" {
			t.Errorf("ungültiger Schlüssel %q in userJSONKeys", k)
		}
		for _, c := range k {
			if c == ',' {
				t.Errorf("Schlüssel %q enthält Tag-Optionen (Komma)", k)
				break
			}
		}
		menge[k] = true
	}
	for _, want := range []string{"id", "email", "display_name", "pending_sms_to", "passkey_credentials", "created_at"} {
		if !menge[want] {
			t.Errorf("userJSONKeys fehlt %q (Liste: %v)", want, keys)
		}
	}
	for _, unerwuenscht := range []string{"Email", "DisplayName", "PendingSmsTo"} {
		if menge[unerwuenscht] {
			t.Errorf("userJSONKeys enthält Go-Feldnamen %q statt JSON-Tag", unerwuenscht)
		}
	}
}
