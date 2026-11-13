package router

import (
	"errors"
	"testing"

	"github.com/henemm/gregor-api/internal/model"
	"github.com/henemm/gregor-api/internal/store"
)

// kontoVollSchreiben legt ein Konto an oder ueberschreibt ein vorhandenes
// VOLLSTAENDIG, inklusive Sicherheitsfeldern (Testvorbereitung). Seit Issue
// #2961 (GA6) laesst SaveUser die Sicherheitsfelder einer vorhandenen
// user.json auf dem Plattenstand; geschrieben werden sie ueber UpdateUser.
func kontoVollSchreiben(t *testing.T, s *store.Store, u model.User) {
	t.Helper()
	_, err := s.UpdateUser(u.ID, func(f *model.User) error { *f = u; return nil })
	if errors.Is(err, store.ErrUserNotFound) {
		err = s.SaveUser(u)
	}
	if err != nil {
		t.Fatalf("Konto %s schreiben: %v", u.ID, err)
	}
}
