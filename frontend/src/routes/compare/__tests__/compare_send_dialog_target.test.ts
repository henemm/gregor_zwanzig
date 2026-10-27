// Bugfix #1471 "Sende-Dialog nennt das tatsaechliche Versandziel" — Stand nach #2278.
// Spec: docs/specs/modules/fix_1471_sende_dialog_ziel.md (AC-1, AC-3/AC-4, AC-5) und
//       docs/specs/modules/feat_2278_aktionsmodell.md (AC-3, AC-10).
//
// Mit #2278 steckt der Sende-Dialog im geteilten Baustein `SendConfirmDialog` (Ziel und Sperre aus
// `sendTargetLabel` via `sendConfirmModel`, bewacht in molecules/__tests__/send_confirm_dialog.test.ts,
// Zwei-Nutzer-Nachweis in lib/server/__tests__/profileLoader.test.ts). Diese Datei bewacht nur noch
// die VERDRAHTUNG der Compare-Liste: Dialog bekommt das Konto-Profil aus dem Server-Load, die
// Empfaenger-Zaehlung (seit #1452 dauerhaft 0) wird nirgends mehr gelesen.
//
// Pruefstand: ECHTER Svelte-Compiler (AST), kein Dateiinhalt-Grep.
//
// Ausfuehrung:
//   cd frontend && npm test -- src/routes/compare/__tests__/compare_send_dialog_target.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	komponenten,
	attribut,
	ids,
	erreichbar
} from '../../../lib/components/shared/__tests__/aktionsmodellAst.ts';

const here = path.dirname(fileURLToPath(import.meta.url));
const ast = ladeSvelte(path.join(here, '..', '+page.svelte'));
const wert = (a: any) => (a ? (Array.isArray(a.value) ? a.value : [a.value]) : []);

describe('#1471 AC-1/AC-5 (nach #2278): Compare-Liste -> SendConfirmDialog mit Konto-Profil', () => {
	test('genau ein SendConfirmDialog, kind="vergleich", Profil aus data.profile', () => {
		const dlgs = komponenten(ast, 'SendConfirmDialog');
		assert.equal(dlgs.length, 1);
		const kind = attribut(dlgs[0], 'kind');
		assert.ok(kind, 'kind fehlt');
		const profil = attribut(dlgs[0], 'profile');
		assert.ok(profil, 'Sende-Dialog bekommt kein Konto-Profil');
		const namen = ids(wert(profil));
		assert.ok(namen.has('data') && namen.has('profile'), 'profile stammt nicht aus data.profile (Server-Load)');
	});

	test('die Empfaenger-Zaehlung wird nirgends mehr gelesen', () => {
		assert.ok(!ids(ast.instance).has('empfaenger'));
		assert.ok(!ids(ast.fragment).has('empfaenger'));
	});

	test('der Dialog sendet erst ueber seine Bestaetigung (sendSubscription), nicht beim Oeffnen', () => {
		const dlg = komponenten(ast, 'SendConfirmDialog')[0];
		assert.ok(erreichbar(ast, wert(attribut(dlg, 'onConfirm'))).bezeichner.has('sendSubscription'));
		const oeffnen = erreichbar(ast, wert(attribut(dlg, 'open')));
		assert.ok(!oeffnen.bezeichner.has('sendSubscription'));
	});
});
