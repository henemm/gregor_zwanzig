// TDD RED — Issue #2913 (Einstellungen neu, Schritt 3: Bausteine), Teil 2.
// Spec: docs/specs/modules/feat_2913_s3_bausteine.md — AC-21, Klarstellung K-4.
//
// Soll:
//   - Die Texte des Wetter-Reiters (wetter.json DE und EN) sind durch die Lieferung unverändert. Gemessen
//     gegen den Abzweigpunkt des Arbeitsstands von origin/main (git merge-base HEAD origin/main): die Datei im
//     Arbeitsbaum ist byte-gleich zur Fassung dort. Auf main selbst ist der Abzweigpunkt HEAD — der Test
//     bleibt also dauerhaft gültig und sperrt keine spätere, bewusste Textänderung in einem eigenen PR.
//     Ohne git/origin (z. B. flacher Checkout) wird der Vergleich mit Begründung übersprungen.
//   - Die neuen bzw. umgebauten Bausteine (Skelett, Einstellungszeile, ChipLeiste, Seite shared/WetterTab,
//     Organismus WetterTabInhalt) enthalten keinen hartcodierten Nutzertext (Scanner der i18n-Ratsche #2649).
//     Ein etwaiger Skelett-Standardtext liegt im Allgemein-Katalog (K-4), nicht in wetter.json.
//
// Hinweis Rote Phase: der Katalogvergleich ist reines Erhaltungsverhalten und darf heute grün sein; ROT sind
// die Scans der noch fehlenden Dateien.
//
// Quellregeln (Kataloge, Markup-Scan):
// doc-compliance-test
//
//   cd frontend && npm test -- src/lib/components/organisms/__tests__/wetter_tab_i18n.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { scanneMarkup } from '../../../i18n/__tests__/hardcode_scan.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KOMP = path.resolve(HERE, '..', '..'); // src/lib/components
const FRONTEND = path.resolve(KOMP, '..', '..', '..');
const REPO = path.resolve(FRONTEND, '..');

function git(args: string[]): string | null {
	try {
		return execFileSync('git', args, { cwd: REPO, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
	} catch {
		return null;
	}
}
const BASIS = git(['merge-base', 'HEAD', 'origin/main'])?.trim() || null;

// #2913 Scheibe (c) (Spec feat_2913_scheibe_c_wetter_rest.md, AC-5/AC-8): diese Lieferung ergänzt bewusst genau
// zwei neue Schlüssel. Der Erhaltungsschutz bleibt: jeder Bestandsschlüssel ist mit byte-gleichem Wert vorhanden,
// kein Schlüssel entfällt, und hinzukommen dürfen nur die hier freigegebenen Schlüssel.
const NEU_FREIGEGEBEN = new Set(['wetter.anpassen.hinweis', 'wetter.anpassen.ueber_mitternacht']);

describe('AC-21: wetter.json DE/EN — Bestandstexte unverändert gegenüber dem Abzweigpunkt von origin/main', () => {
	for (const lang of ['de', 'en']) {
		const rel = `frontend/src/lib/i18n/messages/${lang}/wetter.json`;
		test(`${lang}/wetter.json: Bestandsschlüssel byte-gleich, nur freigegebene Schlüssel neu`, (t) => {
			if (!BASIS) return t.skip('git merge-base HEAD origin/main nicht verfügbar (flacher Checkout)');
			const vorherText = git(['show', `${BASIS}:${rel}`]);
			assert.ok(vorherText !== null, `${rel} fehlt am Abzweigpunkt ${BASIS}`);
			const vorher: Record<string, string> = JSON.parse(vorherText!);
			const jetzt: Record<string, string> = JSON.parse(readFileSync(path.join(REPO, rel), 'utf8'));
			for (const [k, v] of Object.entries(vorher)) {
				assert.equal(jetzt[k], v, `${rel}: ${k} wurde gegenüber ${BASIS.slice(0, 9)} verändert oder entfernt (AC-21: Texte unverändert)`);
			}
			const neu = Object.keys(jetzt).filter((k) => !(k in vorher));
			assert.deepEqual(neu.filter((k) => !NEU_FREIGEGEBEN.has(k)), [], `${rel}: nicht freigegebene neue Schlüssel`);
		});
	}
	test('DE und EN haben dieselben wetter.*-Schlüssel', () => {
		const de = Object.keys(JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', 'de', 'wetter.json'), 'utf8'))).sort();
		const en = Object.keys(JSON.parse(readFileSync(path.join(KOMP, '..', 'i18n', 'messages', 'en', 'wetter.json'), 'utf8'))).sort();
		assert.deepEqual(en, de);
	});
});

describe('AC-21: keine hartcodierten Nutzertexte in den neuen Bausteinen', () => {
	const NEU = [
		'atoms/Skelett.svelte',
		'molecules/Einstellungszeile.svelte',
		'molecules/ChipLeiste.svelte',
		'shared/WetterTab.svelte',
		'organisms/wetter-tab/WetterTabInhalt.svelte'
	];
	for (const rel of NEU) {
		test(`${rel}: kein Textknoten/beschriftendes Attribut außerhalb des Katalogs`, () => {
			const p = path.join(KOMP, rel);
			assert.ok(existsSync(p), `TDD RED: ${rel} fehlt`);
			assert.deepEqual(scanneMarkup(readFileSync(p, 'utf8')), []);
		});
	}
});
