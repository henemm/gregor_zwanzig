// Command migrate2154: verwirft alle vor Issue #2154 gelernten
// Premium-SMS-Rueckadressen (AC-10). Duenner Wrapper um
// store.(*Store).MigrateClearPremiumSmsReplyAddresses, Muster cmd/migrate1258.
// Backup vorher gemaess operations_playbook.md. NICHT ausgefuehrt — nur
// erstellt; der Lauf gehoert einmalig zum Umstieg, nicht in den Serverstart.
// Usage: go run ./cmd/migrate2154 -data-dir=data
package main

import (
	"flag"
	"log"

	"github.com/henemm/gregor-api/internal/store"
)

func main() {
	dataDir := flag.String("data-dir", "data", "root data directory (containing users/)")
	flag.Parse()
	s := store.New(*dataDir, "default")
	cleared, err := s.MigrateClearPremiumSmsReplyAddresses()
	if err != nil {
		log.Fatalf("migration failed: %v", err)
	}
	log.Printf("migrate2154: %d Rueckadresse(n) verworfen", cleared)
}
