package store

import (
	"fmt"
	"log"
	"os"
)

// writeFileLogged schreibt data nach path und loggt einen Schreibfehler
// serverseitig mit Pfad + Ursache (Issue #1066). Der Rückgabefehler trägt
// via %w Pfad-Kontext; die HTTP-Schicht gibt weiterhin nur generisch
// store_error zurück (kein Pfad-Leak an den Client).
func writeFileLogged(path string, data []byte) error {
	if err := os.WriteFile(path, data, 0644); err != nil {
		log.Printf("store: write %s failed: %v", path, err)
		return fmt.Errorf("write %s: %w", path, err)
	}
	return nil
}
