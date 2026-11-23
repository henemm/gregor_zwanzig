// #3237 (Adversary F002, AC-4/AC-6): der Haken "Grosswetterlage" der Karte
// "E-Mail-Inhalt" schaltet `show_stability`, das Feld, das die Grosswetterlage
// im Kern allein steuert. Das Altfeld `show_outlook` hat keine Wirkung mehr
// (jedes Abo hat ab #3237 eine Tabelle) und bleibt beim Speichern unveraendert.
//
// Gilt fuer Editor UND Neuanlage: beide betten dieselbe Karte
// (shared/MailInhaltCard.svelte) ein (TripNewEditor, WeatherMetricsTab).
//
// Messung (Kern-Suite ist SSR-only): das ECHTE Instanz-Skript der Karte wird
// per Pruefstand ausgewertet; der `onchange`-Ausdruck des Hakens kommt aus dem
// Markup (AST) und wird mit einem Ereignis aufgerufen wie im Browser; danach
// laeuft der Schreib-`$effect` (baueReportConfigPayload) und liefert den Blob,
// den der Editor speichert.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/shared/__tests__/mail_inhalt_haken_grosswetterlage_3237.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { effekteVon, ohneTypen, werte, type Knoten } from './svelteInstanzPruefstand.ts';
import { editorUmgebung } from './standardwerteEditorPruefstand.ts';

const KARTE = join(dirname(fileURLToPath(import.meta.url)), '..', 'MailInhaltCard.svelte');
const HAKEN_TESTID = 'report-show-outlook';

/** Der `<Checkbox>` im Wrapper mit dem Testid des Hakens "Grosswetterlage". */
function hakenCheckbox(ast: Knoten): Knoten {
	let gefunden: Knoten | undefined;
	function lauf(n: unknown, imWrapper: boolean): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach((x) => lauf(x, imWrapper));
		const k = n as Knoten;
		let drin = imWrapper;
		if (k.type === 'RegularElement') {
			const tid = (k.attributes ?? []).find((a: Knoten) => a.type === 'Attribute' && a.name === 'data-testid');
			const wert = Array.isArray(tid?.value) ? tid.value.map((t: Knoten) => t.data ?? '').join('') : null;
			if (wert === HAKEN_TESTID) drin = true;
		}
		if (drin && k.type === 'Component' && k.name === 'Checkbox') gefunden ??= k;
		for (const [feld, v] of Object.entries(k)) if (feld !== 'parent' && feld !== 'metadata') lauf(v, drin);
	}
	lauf(ast.fragment, false);
	assert.ok(gefunden, `Kein <Checkbox> im Wrapper data-testid="${HAKEN_TESTID}".`);
	return gefunden as Knoten;
}

function ausdruck(einbettung: Knoten, quelle: string, name: string): string {
	const a = (einbettung.attributes ?? []).find((x: Knoten) => x.type === 'Attribute' && x.name === name);
	assert.ok(a?.value?.type === 'ExpressionTag', `Haken ohne Ausdruck \`${name}\`.`);
	// Ohne TypeScript-Annotationen (`e.target as HTMLInputElement`), per AST.
	return ohneTypen(quelle, a.value.expression);
}

/** Karte oeffnen, Haken auf `neu` setzen, gespeicherten Blob zurueckgeben. */
async function hakenSetzen(blob: Record<string, unknown>, neu: boolean): Promise<{ vorher: unknown; nachher: Knoten }> {
	const e = await editorUmgebung(KARTE, { reportConfig: JSON.parse(JSON.stringify(blob)) });
	for (const fn of e.mounts) fn();
	const schreiben = effekteVon(e.ast, e.quelle, e.u, 'baueReportConfigPayload');
	assert.ok(schreiben.length >= 1, 'Messaufbau: kein Schreib-$effect der Karte gefunden.');
	const haken = hakenCheckbox(e.ast);
	const vorher = werte(ausdruck(haken, e.quelle, 'checked'), e.u);
	const onchange = werte(ausdruck(haken, e.quelle, 'onchange'), e.u) as (ev: unknown) => void;
	onchange({ target: { checked: neu } });
	for (const fn of schreiben) fn();
	const nachher = e.u.reportConfig as Knoten;
	// Nach dem Klick zeigt der Haken den neuen Zustand (gleiche Quelle wie das gespeicherte Feld).
	assert.equal(werte(ausdruck(haken, e.quelle, 'checked'), e.u), neu, 'Haken zeigt nach dem Klick nicht den neuen Zustand.');
	return { vorher, nachher };
}

describe('#3237 F002: Haken "Grosswetterlage" schreibt show_stability, show_outlook bleibt unveraendert', () => {
	for (const show_outlook of [true, false]) {
		test(`abwaehlen -> show_stability:false, show_outlook bleibt ${show_outlook}`, async () => {
			const blob = { email_format: 'full', show_stability: true, show_outlook, enabled: true, send_email: true };
			const { vorher, nachher } = await hakenSetzen(blob, false);
			assert.equal(vorher, true, 'Messaufbau: Haken stand vorher nicht an (show_stability=true).');
			assert.equal(nachher.show_stability, false, 'Abwaehlen schreibt show_stability nicht auf false.');
			assert.equal(nachher.show_outlook, show_outlook, 'Der Haken veraendert das Altfeld show_outlook.');
		});

		test(`anwaehlen -> show_stability:true, show_outlook bleibt ${show_outlook}`, async () => {
			const blob = { email_format: 'full', show_stability: false, show_outlook, enabled: true, send_email: true };
			const { vorher, nachher } = await hakenSetzen(blob, true);
			assert.equal(vorher, false, 'Haken folgt nicht show_stability=false aus dem gespeicherten Abo.');
			assert.equal(nachher.show_stability, true, 'Anwaehlen schreibt show_stability nicht auf true.');
			assert.equal(nachher.show_outlook, show_outlook, 'Der Haken veraendert das Altfeld show_outlook.');
		});
	}

	test('Startzustand: Haken folgt show_stability, nicht show_outlook', async () => {
		for (const [blob, soll] of [
			[{ show_stability: false, show_outlook: true }, false],
			[{ show_stability: true, show_outlook: false }, true],
			[{}, true], // Loader-Standard im Kern: show_stability fehlt -> True
			[{ show_stability: null }, false] // gespeichertes null liest der Kern als None -> aus
		] as const) {
			const e = await editorUmgebung(KARTE, { reportConfig: { email_format: 'full', ...blob } });
			for (const fn of e.mounts) fn();
			const haken = hakenCheckbox(e.ast);
			assert.equal(werte(ausdruck(haken, e.quelle, 'checked'), e.u), soll, `Startzustand bei ${JSON.stringify(blob)}`);
		}
	});
});
