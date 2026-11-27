// TDD RED — Issue #3440 (S5a): Verdrahtung des Menüs „Test schicken ▾“ in beiden Hubs am AST
// (echter Svelte-5-Compiler, Prüfstand aktionsmodellAst.ts — Muster hub_kopf_seiten_bindung.test.ts).
// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md — AC-1, AC-11/AC-12 (testids), AC-15 (aria), AC-20.
//
// Warum AST: bits-ui-Menü und `mobil`-Zustand sind unter svelte/server nicht erreichbar; messbar ist die BINDUNG
// (welche Datei welchen Baustein einbindet, mit welchen Props, unter welcher Bedingung). Das Klicken prüft
// frontend/e2e/hub-send-menue.staging.spec.ts.
//
// VERTRAG:
//   * molecules/TestSchickenMenue.svelte ist EIN Baustein für beide Hubs (context="route"|"vergleich", ADR-0097),
//     trägt data-abschnitt="test-menue" und ruft keine API (kein Import von sendOutcome/subscriptionExec).
//   * Je Hub ist TestSchickenMenue in der Kette Seite → (TripHeader) → HubKopf GENAU EINMAL gebunden.
//   * Kein SendConfirmDialog mehr in den Hub-Seiten (Listen behalten ihn, AC-18).
//   * HubKopf-Knopf `subscription-hub-send`: Btn accent, aria-haspopup="menu", aria-expanded als Ausdruck, ruft nicht
//     mehr onSend; Seiten reichen `onTest` (Trip über TripHeader, Vergleich direkt an HubKopf).
//   * Rückmeldung in beiden Seiten über testids `test-schicken-ok` / `test-schicken-fehler`.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/test_schicken_menue_bindung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ladeSvelte,
	importe,
	komponenten,
	mitAttribut,
	attrKurz,
	attribut,
	bedingungen,
	ids,
	type Knoten
} from '../../__tests__/aktionsmodellAst.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../../../../..');
const KOMP = path.join(SRC, 'lib/components');
const MENUE_DATEI = path.join(KOMP, 'molecules/TestSchickenMenue.svelte');
const HUBKOPF = path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte');
const TRIPHEADER = path.join(KOMP, 'trip-detail/TripHeader.svelte');
const TRIP_SEITE = path.join(SRC, 'routes/trips/[id]/+page.svelte');
const VERGLEICH_SEITE = path.join(SRC, 'routes/compare/[id]/+page.svelte');

const KETTEN = {
	'Trip-Hub': { seite: TRIP_SEITE, kette: [TRIP_SEITE, TRIPHEADER, HUBKOPF], context: '"route"' },
	'Orte-Hub': { seite: VERGLEICH_SEITE, kette: [VERGLEICH_SEITE, HUBKOPF], context: '"vergleich"' }
} as const;

const rel = (p: string) => path.relative(SRC, p);

function menue(): Knoten {
	assert.ok(existsSync(MENUE_DATEI), `TDD RED: Baustein fehlt: ${rel(MENUE_DATEI)}`);
	return ladeSvelte(MENUE_DATEI);
}

describe('#3440 AC-1 — beide Hubs nutzen denselben Baustein TestSchickenMenue', () => {
	test('Baustein existiert, trägt data-abschnitt="test-menue" und ruft keine API', () => {
		const ast = menue();
		assert.equal(mitAttribut(ast, 'data-abschnitt', 'test-menue').length, 1, 'Abschnitt-Haken test-menue fehlt (genau einmal)');
		const quellen = importe(ast).map((i) => i.quelle);
		assert.deepEqual(
			quellen.filter((q) => /sendOutcome|subscriptionExec/.test(q)),
			[],
			'TestSchickenMenue darf nicht selbst senden (Baustein emittiert nur {kanal, berichtsart})'
		);
		assert.ok(!ids(ast.instance).has('fetch'), 'TestSchickenMenue ruft fetch');
	});

	for (const [name, { kette, context }] of Object.entries(KETTEN)) {
		test(`${name}: TestSchickenMenue genau einmal in der Kette ${kette.map((d) => path.basename(path.dirname(d)) + '/' + path.basename(d)).join(' → ')}`, () => {
			const treffer = kette.flatMap((datei) => komponenten(ladeSvelte(datei), 'TestSchickenMenue').map((k) => ({ datei, k })));
			assert.equal(treffer.length, 1, `${name}: TestSchickenMenue ${treffer.length}× gebunden (erwartet genau 1)`);
			const { datei, k } = treffer[0];
			const ctx = attrKurz(k, 'context');
			// In HubKopf reicht der Baustein den context des Kopfs durch; in einer Seite steht das Literal.
			assert.equal(ctx, datei === HUBKOPF ? 'context' : context, `${name}: context-Prop am Menü`);
		});
	}

	for (const [name, { seite }] of Object.entries(KETTEN)) {
		test(`${name}: kein SendConfirmDialog mehr im Hub (weder eingebunden noch importiert)`, () => {
			const ast = ladeSvelte(seite);
			assert.equal(komponenten(ast, 'SendConfirmDialog').length, 0, `${name} bindet SendConfirmDialog noch ein`);
			assert.deepEqual(importe(ast).map((i) => i.quelle).filter((q) => /SendConfirmDialog/.test(q)), []);
		});
	}
});

describe('#3440 AC-15 / AC-20 — Kopf-Knopf öffnet das Menü (aria), bleibt gesperrt bzw. im Setup ohne Menü', () => {
	test('subscription-hub-send: Btn accent, aria-haspopup="menu", aria-expanded als Ausdruck, disabled = sendDisabled, kein onSend', () => {
		const ast = ladeSvelte(HUBKOPF);
		const s = mitAttribut(ast, 'data-testid', 'subscription-hub-send');
		assert.equal(s.length, 1, 'Knopf genau einmal');
		assert.equal(s[0].name, 'Btn');
		assert.equal(attrKurz(s[0], 'variant'), '"accent"', 'Stil bleibt Btn accent (ADR-0118)');
		assert.equal(attrKurz(s[0], 'aria-haspopup'), '"menu"', 'aria-haspopup="menu" fehlt');
		const expanded = attribut(s[0], 'aria-expanded');
		assert.ok(expanded, 'aria-expanded fehlt');
		assert.ok(!/^"/.test(attrKurz(s[0], 'aria-expanded') ?? ''), 'aria-expanded muss dem Menüzustand folgen (Ausdruck, kein Literal)');
		assert.equal(attrKurz(s[0], 'disabled'), 'sendDisabled', 'Sperre bei archiviert muss bleiben (AC-20)');
		assert.ok(!/onSend/.test(attrKurz(s[0], 'onclick') ?? ''), `Knopf ruft noch onSend: ${attrKurz(s[0], 'onclick')}`);
	});

	test('Menü steht (falls im HubKopf) nur außerhalb des Setup-Modus — im Entwurf öffnet sich nichts', () => {
		const ast = ladeSvelte(HUBKOPF);
		const m = komponenten(ast, 'TestSchickenMenue');
		const inSeiten = [TRIP_SEITE, VERGLEICH_SEITE, TRIPHEADER].some((d) => komponenten(ladeSvelte(d), 'TestSchickenMenue').length > 0);
		assert.ok(m.length === 1 || inSeiten, 'TDD RED: TestSchickenMenue ist nirgends gebunden');
		if (m.length === 1) {
			const b = bedingungen(ast.fragment, m[0]) ?? [];
			assert.ok(b.includes('!(sendMode === "setup")'), `Menü ist im Setup-Modus erreichbar: Bedingungen ${JSON.stringify(b)}`);
		}
	});

	test('Trip-Seite reicht onTest an TripHeader, TripHeader an HubKopf; Orte-Seite reicht onTest an HubKopf', () => {
		const trip = komponenten(ladeSvelte(TRIP_SEITE), 'TripHeader');
		assert.equal(trip.length, 1);
		assert.ok(attribut(trip[0], 'onTest'), 'Trip-Seite: TripHeader ohne onTest');
		assert.equal(attribut(trip[0], 'onSend'), undefined, 'Trip-Seite: onSend (Dialog) noch gebunden');
		const th = komponenten(ladeSvelte(TRIPHEADER), 'HubKopf');
		assert.equal(th.length, 1);
		assert.ok(attribut(th[0], 'onTest'), 'TripHeader: HubKopf ohne onTest');
		const vg = komponenten(ladeSvelte(VERGLEICH_SEITE), 'HubKopf');
		assert.equal(vg.length, 1);
		assert.ok(attribut(vg[0], 'onTest'), 'Orte-Seite: HubKopf ohne onTest');
		assert.equal(attribut(vg[0], 'onSend'), undefined, 'Orte-Seite: onSend (Dialog) noch gebunden');
	});
});

describe('#3440 AC-11 / AC-12 — einheitliche Rückmeldung in beiden Hubs', () => {
	for (const [name, { seite }] of Object.entries(KETTEN)) {
		test(`${name}: Rückmeldung mit testids test-schicken-ok und test-schicken-fehler`, () => {
			const ast = ladeSvelte(seite);
			assert.equal(mitAttribut(ast, 'data-testid', 'test-schicken-ok').length, 1, `${name}: test-schicken-ok fehlt`);
			assert.equal(mitAttribut(ast, 'data-testid', 'test-schicken-fehler').length, 1, `${name}: test-schicken-fehler fehlt`);
		});
	}
});
