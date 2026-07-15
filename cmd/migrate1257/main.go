// Command migrate1257: materialisiert Issue #1257 (alert_rules) rückwirkend.
// Dünner Wrapper um store.MigrateAllTripsAlertRules. Backup vorher gemäß
// operations_playbook.md. NICHT ausgeführt — nur erstellt.
// Usage: go run ./cmd/migrate1257 -data-dir=data
package main

import (
	"flag"
	"log"

	"github.com/henemm/gregor-api/internal/store"
)

func main() {
	dataDir := flag.String("data-dir", "data", "root data directory (containing users/)")
	flag.Parse()
	migrated, err := store.MigrateAllTripsAlertRules(*dataDir)
	if err != nil {
		log.Fatalf("migration failed: %v", err)
	}
	log.Printf("migrate1257: %d Trip(s) migriert", migrated)
}
