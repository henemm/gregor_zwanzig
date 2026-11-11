// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 1.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-10.
//
// Soll:
//   - organisms/index.ts exportiert die neun Organismen des Wetter-Reiters aus ./wetter-tab/.
//   - docs/design-system/COMPONENTS.md nennt die neun Organismen, TOKENS.md die Maß-Tokens
//     --g-tap-min und --g-size-* (neuer Abschnitt Maß-Tokens).
//
// Messweise: Export-Deklarationen des Barrels (ohne Kommentare) und Doku als Text:
// doc-compliance-test
//
// RED heute: Barrel und Doku kennen den Wetter-Reiter nicht.
//
// Teil 2 (Workflow feature-2913-teil2, K-1): organisms/wetter-tab/WetterTab.svelte ist zu WetterTabInhalt.svelte
// geworden; der Barrel exportiert WetterTabInhalt statt WetterTab (die Seite WetterTab liegt unter shared/ und ist
// kein Organismus). COMPONENTS.md nennt entsprechend WetterTabInhalt.
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_barrel.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HIER = dirname(fileURLToPath(import.meta.url));
const ORGANISMS = join(HIER, '..');
const REPO = join(ORGANISMS, '..', '..', '..', '..', '..');
const BARREL = readFileSync(join(ORGANISMS, 'index.ts'), 'utf8').replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, '');
const COMPONENTS_MD = readFileSync(join(REPO, 'docs', 'design-system', 'COMPONENTS.md'), 'utf8');
const TOKENS_MD = readFileSync(join(REPO, 'docs', 'design-system', 'TOKENS.md'), 'utf8');

// Teil 2 (K-1): WetterTabInhalt statt WetterTab.
const NEUN = [
	'WetterTabInhalt',
	'VorlageKarte',
	'MetrikZeile',
	'GrenzenEditor',
	'WarnungenRadarKarte',
	'AmpelLeiste',
	'AlarmAbKopf',
	'NichtImBriefing',
	'AnpassenKarte'
];

/** export { default as X } from '<pfad>' → Map X → pfad */
const EXPORTE = new Map<string, string>();
for (const m of BARREL.matchAll(/export\s*\{\s*default\s+as\s+(\w+)\s*\}\s*from\s*['"]([^'"]+)['"]/g)) EXPORTE.set(m[1], m[2]);

describe('AC-10: Barrel exportiert die neun Organismen aus ./wetter-tab/', () => {
	for (const n of NEUN) {
		test(`${n} im Barrel aus ./wetter-tab/${n}.svelte`, () => {
			assert.equal(EXPORTE.get(n), `./wetter-tab/${n}.svelte`, `TDD RED: Barrel-Export ${n} fehlt oder zeigt woanders hin`);
		});
	}
});

describe('AC-10 (Teil 2, K-1): Barrel exportiert keinen Organismus WetterTab mehr', () => {
	test('kein Export WetterTab aus ./wetter-tab/WetterTab.svelte', () => {
		assert.equal(EXPORTE.has('WetterTab'), false, `TDD RED: Barrel exportiert noch WetterTab (${EXPORTE.get('WetterTab')})`);
	});
});

describe('AC-10: Doku beschreibt Organismen und Maß-Tokens', () => {
	test('COMPONENTS.md nennt alle neun Organismen des Wetter-Reiters', () => {
		const fehlt = NEUN.filter((n) => !COMPONENTS_MD.includes(n));
		assert.deepEqual(fehlt, [], `COMPONENTS.md ohne: ${fehlt.join(', ')}`);
	});
	test('TOKENS.md beschreibt --g-tap-min und --g-size-*', () => {
		assert.match(TOKENS_MD, /--g-tap-min/);
		assert.match(TOKENS_MD, /--g-size-/);
	});
});
