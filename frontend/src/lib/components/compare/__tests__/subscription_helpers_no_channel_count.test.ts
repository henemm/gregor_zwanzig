// TDD RED — Bugfix "Sende-Dialog nennt das tatsaechliche Versandziel".
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md — AC-7.
//
// `channelCountLabel()` liest dieselbe seit #1452 inerte Laenge wie der kaputte
// Dialog und ist nachgemessen tot (kein .svelte importiert sie). Sie muss weg,
// sonst bleibt eine zweite Stelle stehen, die die falsche Zaehlung wiederbeleben
// kann. Geprueft wird an der Modul-Schnittstelle (echter Import), nicht am
// Dateiinhalt.
//
// RED heute: die Funktion ist exportiert und ihr Test liegt noch da.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/subscription_helpers_no_channel_count.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const helpers: Record<string, unknown> = await import('../subscriptionHelpers.ts');

describe('AC-7: die tote Kanal-Zaehlung ist samt Test entfernt', () => {
	test('`subscriptionHelpers` exportiert kein `channelCountLabel` mehr', () => {
		assert.equal(
			'channelCountLabel' in helpers,
			false,
			'`channelCountLabel()` ist weiterhin exportiert — sie liest dieselbe inerte Laenge ' +
				'wie der kaputte Dialog und kann die falsche Zaehlung jederzeit wiederbeleben (AC-7).'
		);
	});

	test('die Nachfolgerin `channelNamesLabel` ist unveraendert nutzbar', () => {
		assert.equal(
			typeof helpers.channelNamesLabel,
			'function',
			'`channelNamesLabel()` fehlt — die Entfernung hat die Nachfolgerin mitgerissen (AC-7).'
		);
	});

	test('der Test der entfernten Funktion liegt nicht mehr im Baum', () => {
		const alt = join(here, '..', 'channelCountLabel.test.ts');
		assert.equal(
			existsSync(alt),
			false,
			`Der Test der entfernten Funktion liegt noch unter ${alt} — er wuerde beim naechsten ` +
				'Lauf mit einem Import-Fehler abbrechen (AC-7).'
		);
	});

	test('der Negativtest, der die Abwesenheit bewacht, bleibt erhalten', () => {
		const waechter = join(here, 'compare_mobile_shared_hub.test.ts');
		assert.ok(
			existsSync(waechter),
			`Der Waechter ${waechter} wurde mitentfernt — ohne ihn koennte die Bespoke-Zaehlung ` +
				'auf der Hub-Seite unbemerkt zurueckkehren (AC-7).'
		);
	});
});
