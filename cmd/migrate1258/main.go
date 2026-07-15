// Command migrate1258: materialisiert Issue #1258 (official_warnings)
// rückwirkend. Dünner Wrapper um store.MigrateAllOfficialWarnings. Backup
// vorher gemäß operations_playbook.md. NICHT ausgeführt — nur erstellt.
// Usage: go run ./cmd/migrate1258 -data-dir=data
package main

import (
	"flag"
	"log"

	"github.com/henemm/gregor-api/internal/store"
)

func main() {
	dataDir := flag.String("data-dir", "data", "root data directory (containing users/)")
	flag.Parse()
	migrated, err := store.MigrateAllOfficialWarnings(*dataDir)
	if err != nil {
		log.Fatalf("migration failed: %v", err)
	}
	log.Printf("migrate1258: %d Trip(s)/Preset(s) migriert", migrated)
}
