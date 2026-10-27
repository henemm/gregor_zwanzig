package store

// Bestandsdaten-Migration zu Issue #2154 Scheibe A (AC-10, Spec D6).
//
// Vor dieser Scheibe konnte eine fremde Garmin-Nummer die Rueckadresse eines
// Premium-Nutzers ohne jedes Geheimnis belegen (Ein-Kandidaten-Fallback). Jede
// Variante mit Bestandserhalt hielte genau die moeglicherweise entfuehrte
// Nummer als gueltigen Bestaetigungspfad am Leben — deshalb wird bewusst
// verworfen. Betroffene Nutzer verknuepfen sich einmal neu (Folge, kein
// Fehler).
//
// Aufruf ueber den duennen Wrapper cmd/migrate2154 (Muster migrate_1258.go),
// NICHT beim Serverstart: ein Start-Aufruf wuerde bei jedem Neustart auch
// legitim neu verknuepfte Rueckadressen mit abraeumen.

// MigrateClearPremiumSmsReplyAddresses verwirft PremiumSmsReplyTo/-At bei allen
// Nutzern und meldet, wie viele bereinigt wurden.
//
// Read-Modify-Write mit Merge (CLAUDE.md "Daten-Schema-Reworks"): das
// bestehende Nutzerobjekt wird geladen und nur um die beiden Zielfelder
// veraendert — SaveUser ist Replace, ein frisch gebautes model.User{ID: id}
// wuerde das halbe Profil loeschen.
func (s *Store) MigrateClearPremiumSmsReplyAddresses() (int, error) {
	ids, err := s.ListUserIDs()
	if err != nil {
		return 0, err
	}
	cleared := 0
	for _, id := range ids {
		user, err := s.LoadUser(id)
		if err != nil || user == nil {
			continue
		}
		if user.PremiumSmsReplyTo == "" && user.PremiumSmsReplyAt == nil {
			continue
		}
		user.PremiumSmsReplyTo = ""
		user.PremiumSmsReplyAt = nil
		if err := s.SaveUser(*user); err != nil {
			return cleared, err
		}
		cleared++
	}
	return cleared, nil
}
