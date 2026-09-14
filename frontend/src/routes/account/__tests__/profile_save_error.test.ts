// TDD RED — Issue #2147 Scheibe B1 (#2311, Epic #2138), AC-16: reine
// Uebersetzungsfunktion fuer Profil-Speicherfehler — `email_taken` bekommt
// einen verstaendlichen deutschen Satz statt eines rohen Fehlercodes;
// unbekannte Codes behalten das bisherige Verhalten
// (`body.detail ?? body.error ?? 'Speichern fehlgeschlagen'`, siehe
// account/+page.svelte:298-299).
// Spec: docs/specs/modules/adress_eindeutigkeit_schreibpfade.md §7, AC-16.
//
// Die geprueft Funktion `profileSaveErrorMessage` existiert noch nicht
// (frontend/src/routes/account/profileSaveError.ts) — dieser Test schlaegt
// heute schon am Import fehl (RED).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/routes/account/__tests__/profile_save_error.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> account -> routes -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../..');

const { profileSaveErrorMessage } = (await import(
	pathToFileURL(path.join(FRONTEND, 'src/routes/account/profileSaveError.ts')).href
)) as { profileSaveErrorMessage: (status: number, body: unknown) => string };

describe('#2147 Scheibe B1 AC-16 — Profil-Speicherfehler verstaendlich uebersetzt', () => {
	test('email_taken_zeigt_verstaendlichen_satz', () => {
		const meldung = profileSaveErrorMessage(409, { error: 'email_taken' });
		assert.equal(
			meldung,
			'Diese E-Mail-Adresse wird bereits von einem anderen Konto verwendet.',
			'AC-16: email_taken muss den verstaendlichen deutschen Satz liefern.'
		);
	});

	// Regressionswaechter: bisheriges Fallback-Verhalten bleibt fuer alle
	// anderen Fehlercodes unveraendert (account/+page.svelte:299).
	test('unbekannter_code_mit_detail_faellt_auf_detail_zurueck', () => {
		const meldung = profileSaveErrorMessage(500, { detail: 'irgendein Detail' });
		assert.equal(meldung, 'irgendein Detail');
	});

	test('unbekannter_code_ohne_detail_faellt_auf_error_zurueck', () => {
		const meldung = profileSaveErrorMessage(400, { error: 'validation failed' });
		assert.equal(meldung, 'validation failed');
	});

	test('kein_detail_kein_error_faellt_auf_generische_meldung_zurueck', () => {
		const meldung = profileSaveErrorMessage(500, {});
		assert.equal(meldung, 'Speichern fehlgeschlagen');
	});
});
