// Issue #2652 (i18n F3, Epic #2644) — AC-3, AC-4, AC-5: Cockpit und Listen
// sprechen die Nutzersprache. Echter SSR-Render (svelte/server, Pruefstand
// f3HomeListenSsr.ts) mit fester Zeit-Fixture:
//   * AC-4: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f3_home_listen/*.de.html, aus dem Ist-Stand geschrieben),
//   * AC-3: Trip-Liste und Archiv auf Englisch, Plural ueber tn(),
//   * AC-5: zwei Nutzer (en/de) nacheinander durch die ECHTEN Loader
//     (+layout.server.ts fuer die Sprache, trips/archiv +page.server.ts fuer die Daten).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation tr()/$t -> trFor('de', …) macht ihn rot.
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md
//
//   cd frontend && npm test -- src/routes/__tests__/listen_sprache_je_nutzer.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
	FAELLE,
	GOLDEN_DIR,
	locale,
	ladeArchivGolden,
	schreibeGolden
} from './f3HomeListenSsr.ts';

before(async () => {
	await ladeArchivGolden();
	if (process.env.GZ_GOLDEN_SCHREIBEN === '1') {
		schreibeGolden('de');
		schreibeGolden('en');
	}
});
afterEach(() => locale.set('de'));

describe('AC-4: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			locale.set('en');
			FAELLE[fall]();
			locale.set('de');
			assert.equal(FAELLE[fall]() + '\n', golden);
		});
	}
});
