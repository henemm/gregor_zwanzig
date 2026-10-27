// Issue #2226 (Defekt 2) — Geteilte Auflösung (Single Source of Truth) für
// den E2E-Testnutzer (Rolle C). Vorher lasen `global.setup.ts` und
// `helpers.ts::login()` unabhängig voneinander zwei verschiedene
// Umgebungsvariablen (`E2E_USER` vs. `GZ_E2E_USER`) — wer nur eine setzte,
// bog die Suite nur zur Hälfte um.
//
// Rolle A (`GZ_VALIDATOR_USER`, nginx-Basic-Auth) und Rolle B
// (`GZ_AUTH_USER`, Staging-App-Login) werden hier bewusst NICHT gelesen —
// eigenständige Rollen, s. docs/specs/modules/fix_2226_testdaten_isolation.md
// Non-Goals.
//
// Default bleibt `admin`/`test1234` — der CI-e2e-Job seedet denselben
// Account serverseitig und verlässt sich darauf (Non-Goal, kein
// fail-closed hier; der wirksame Schutz gegen echte Konten ist
// `prodUrlGuard.ts`).

export interface E2ETestUser {
	user: string;
	pass: string;
}

export function resolveE2EUser(): E2ETestUser {
	return {
		user: process.env.E2E_USER ?? process.env.GZ_E2E_USER ?? 'admin',
		pass: process.env.E2E_PASS ?? process.env.GZ_E2E_PASS ?? 'test1234'
	};
}
