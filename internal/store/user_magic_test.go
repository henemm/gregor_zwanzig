package store

// Issue #2147 Scheibe A: ResolveAddressOwner ordnet eine Adresse genau einem
// Konto zu (ersetzt die frühere reine email-Feld-Suche aus Issue #449).
// Spec: docs/specs/modules/magic_link_adress_eindeutigkeit.md — Regeltabelle.
// Echter Store auf t.TempDir(), kein Mock.

import (
	"testing"
	"time"

	"github.com/henemm/gregor-api/internal/model"
)

func bestaetigtAm() *time.Time {
	t := time.Date(2026, 9, 1, 8, 0, 0, 0, time.UTC)
	return &t
}

func TestResolveAddressOwner(t *testing.T) {
	const x = "inhaber@example.com"
	faelle := []struct {
		name      string
		konten    []model.User
		adresse   string
		wantRes   AddressResolution
		wantOwner string
	}{
		{"frei", []model.User{{ID: "anderer", Email: "b@example.com", MailTo: "b@example.com"}},
			x, AddressFree, ""},
		{"leere-adresse-trifft-nie", []model.User{{ID: "ohne-mail"}},
			"  ", AddressAmbiguous, ""},
		{"ein-bestaetigter-inhaber", []model.User{{ID: "alice", Email: x, MailTo: x, EmailVerifiedAt: bestaetigtAm(), PasswordHash: "h"}},
			x, AddressOwned, "alice"},
		{"gross-klein-und-leerraum-egal", []model.User{{ID: "bob", Email: x, MailTo: x, EmailVerifiedAt: bestaetigtAm()}},
			"  INHABER@Example.COM ", AddressOwned, "bob"},
		{"bestaetigter-gewinnt-gegen-nebenfeld", []model.User{
			{ID: "a-nebenfeld", Email: x, MailTo: "a@example.com", EmailVerifiedAt: bestaetigtAm()},
			{ID: "b-inhaber", Email: "b-alt@example.com", MailTo: x, EmailVerifiedAt: bestaetigtAm()}},
			x, AddressOwned, "b-inhaber"},
		{"testkonto-uebersprungen", []model.User{{ID: "tg-live-e2e", Email: x, MailTo: x, EmailVerifiedAt: bestaetigtAm()}},
			x, AddressFree, ""},
		{"nur-nebenfeld-ist-mehrdeutig", []model.User{{ID: "carl", Email: x, MailTo: "carl@example.com", EmailVerifiedAt: bestaetigtAm()}},
			x, AddressAmbiguous, ""},
		{"unbestaetigt-mit-passwort", []model.User{{ID: "dora", Email: x, MailTo: x, PasswordHash: "h"}},
			x, AddressAmbiguous, ""},
		{"unbestaetigt-mit-passkey", []model.User{{ID: "dora", Email: x, MailTo: x, PasskeyCredentials: []model.WebAuthnCredential{{ID: []byte{1}}}}},
			x, AddressAmbiguous, ""},
		{"unbestaetigt-mit-google", []model.User{{ID: "dora", Email: x, MailTo: x, OAuthProvider: "google", OAuthSub: "sub"}},
			x, AddressAmbiguous, ""},
		{"unbestaetigt-zugangslos-kontaktadresse-ueber-email", []model.User{{ID: "emil", Email: x}},
			x, AddressOwned, "emil"},
		{"unbestaetigt-zugangslos-nur-nebenfeld", []model.User{{ID: "emil", Email: x, MailTo: "emil@example.com"}},
			x, AddressAmbiguous, ""},
		{"zwei-unbestaetigte-inhaber", []model.User{{ID: "f1", Email: x}, {ID: "f2", MailTo: x}},
			x, AddressAmbiguous, ""},
		{"zwei-bestaetigte-inhaber", []model.User{
			{ID: "g1", Email: x, MailTo: x, EmailVerifiedAt: bestaetigtAm()},
			{ID: "g2", MailTo: x, EmailVerifiedAt: bestaetigtAm()}},
			x, AddressAmbiguous, ""},
	}
	for _, f := range faelle {
		t.Run(f.name, func(t *testing.T) {
			s := New(t.TempDir(), "test")
			for _, u := range f.konten {
				u.CreatedAt = time.Now()
				if err := s.SaveUser(u); err != nil {
					t.Fatalf("SaveUser(%q): %v", u.ID, err)
				}
			}
			owner, res, err := s.ResolveAddressOwner(f.adresse)
			if err != nil {
				t.Fatalf("ResolveAddressOwner: %v", err)
			}
			got := ""
			if owner != nil {
				got = owner.ID
			}
			if res != f.wantRes || got != f.wantOwner {
				t.Errorf("erwartet (%d, %q), bekommen (%d, %q)", f.wantRes, f.wantOwner, res, got)
			}
		})
	}
}
