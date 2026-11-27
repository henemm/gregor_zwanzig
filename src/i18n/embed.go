// Package i18n bettet den gemeinsamen Katalogbereich `geteilt` fuer die Go-API
// ein (ADR-0130, #3444). Gepflegt wird er nur hier in src/i18n/messages; der
// Python-Core liest dieselben Dateien. Bewusst nur geteilt.json, keine
// Python-Bereiche.
package i18n

import "embed"

// Messages enthaelt messages/de/geteilt.json und messages/en/geteilt.json.
//
//go:embed messages/de/geteilt.json messages/en/geteilt.json
var Messages embed.FS
