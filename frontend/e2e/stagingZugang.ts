// Issue #2961 (FE8) — Zugangsdaten fuer Playwright-Laeufe gegen Staging.
//
// Staging-Zugangsdaten stehen NIE im Quelltext (oeffentliches Repo). Sie kommen
// ausschliesslich aus der Umgebung; Herkunft laut
// docs/reference/operations_playbook.md, Abschnitt „Zugangsdaten: DREI Quellen":
//   - vorgeschaltete nginx-Schranke: GZ_VALIDATOR_USER / GZ_VALIDATOR_PASS
//     (.claude/validator.env)
//   - Anmeldung der Anwendung auf Staging: GZ_AUTH_USER / GZ_AUTH_PASS
//     (Staging-.env)
//   - E2E_USER / E2E_PASS als bisherige Alternativen
// Fehlt eine Variable, bricht der Lauf mit einer klaren Meldung ab, statt mit
// einem Standardpasswort zu arbeiten.
//
// Der isolierte CI-Stack (e2e/ci-stack.sh, testUser.ts) ist davon nicht
// betroffen: er arbeitet absichtlich mit festen Testwerten eines lokal
// hochgefahrenen, leeren Servers.

import { randomBytes } from 'node:crypto';

/**
 * Wert der ersten gesetzten (nicht leeren) Umgebungsvariable aus `namen`.
 * Ist keine gesetzt: Abbruch mit Nennung aller Namen und ihrer Quelle.
 */
export function ausUmgebung(...namen: string[]): string {
	if (namen.length === 0) throw new Error('ausUmgebung: mindestens ein Variablenname noetig');
	for (const name of namen) {
		const wert = process.env[name];
		if (wert !== undefined && wert !== '') return wert;
	}
	throw new Error(
		`Staging-Zugangsdaten fehlen: keine der Umgebungsvariablen ${namen.join(', ')} ist gesetzt. ` +
			'Quelle siehe docs/reference/operations_playbook.md, Abschnitt „Zugangsdaten: DREI Quellen" ' +
			'(GZ_VALIDATOR_* aus .claude/validator.env, GZ_AUTH_* aus der Staging-.env). ' +
			'Ohne sie laeuft kein Staging-Test — es gibt bewusst keinen Standardwert.'
	);
}

/**
 * Passwort fuer ein Wegwerf-Konto, das ein Test selbst anlegt und wieder
 * entfernt: je Lauf zufaellig, steht nirgends im Quelltext.
 */
export function wegwerfPasswort(): string {
	return `Gz-${randomBytes(12).toString('base64url')}-9!`;
}
