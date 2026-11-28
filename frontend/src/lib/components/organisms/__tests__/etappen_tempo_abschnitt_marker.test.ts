// TDD RED — Issue #3436 (Workflow fix-3436-tempo-abschnitt): Abschnitt-Haken der Tempo-Karte im Reiter Etappen.
// Spec: docs/specs/modules/fix_3436_tempo_abschnitt.md — AC-1, AC-2.
//
// Geprüft im Server-Render der ECHTEN Komponenten (kein Mock), Muster wetter_tab_abschnitt_marker*.test.ts:
//   AC-1: EditStagesPanelNew mit Bereichskopf (`kopf`) in allen drei Layouts — Liste (`listeZuerst`, Hub),
//         Band (Computer ohne `listeZuerst`) und mobil (`isMobileViewport` als `$state`-Startwert über den
//         F8-Hook) — die Tempo-Karte des Reiters liegt in genau einem Element mit data-abschnitt="tempo".
//   AC-2: die Tempo-Karte beim Anlegen (TripNewEditor, Computer und Handy, auch der eingebettete Etappen-Editor)
//         und die Etappen-Karte „Tempo ändern“ (TempoKarteInhalt mit nurGrundtempo; Computer-Liste und mobil
//         in StageCardM) tragen KEINEN Haken data-abschnitt="tempo" — weder an sich noch in ihren Vorfahren.
//         Ein Haken in TempoKarteInhalt (statt am Wrapper im Panel) macht AC-2 rot.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/organisms/__tests__/etappen_tempo_abschnitt_marker.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { readFileSync } from 'node:fs';

const T = await import('../../trip-detail/__tests__/f9Pruefstand.ts');
const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { baum, alle, vorfahren } = await import('../../shared/hub-kopf/__tests__/htmlBaum.ts');
type Knoten = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const PANEL = path.join(T.KOMP, 'edit', 'EditStagesPanelNew.svelte');
const EDITOR = path.join(T.KOMP, 'trip-new', 'TripNewEditor.svelte');
const { locale } = T;
afterEach(() => locale.set('de'));

const TABELLE = JSON.parse(readFileSync(path.resolve(T.FRONTEND, '..', 'tests', 'fixtures', 'naismith_dav_paritaet.json'), 'utf-8'));
const UE = TABELLE.etappen_ueberschreibung;
const TRIP_TEMPO = UE.tempo;
const PAUSE = { id: 'S3', name: 'Ruhetag', date: '2026-07-03', waypoints: [] };
const etappen = () => [...structuredClone(UE.stages), structuredClone(PAUSE)];
const kopf = () => createRawSnippet(() => ({ render: () => '<div data-testid="probe-kopf">Etappen</div>' }));

const MOBIL: [string, string] = ['let isMobileViewport = $state(false);', 'let isMobileViewport = $state(true);'];
const TEMPO_OFFEN = (id: string): [string, string] => ['let tempoEtappeId = $state<string | null>(null);', `let tempoEtappeId = $state<string | null>('${id}');`];

const HAKEN = 'tempo';
const istHaken = (n: Knoten) => n.attrs?.['data-abschnitt'] === HAKEN;
const mitTestid = (b: Knoten, id: string): Knoten[] => alle(b as never, (n: Knoten) => n.attrs['data-testid'] === id);
const hakenZahl = (b: Knoten) => alle(b as never, istHaken).length;
const unterHaken = (k: Knoten) => istHaken(k) || vorfahren(k as never).some(istHaken);
/** Die Karte des Reiters: tempo-karte, die NICHT in einer Etappen-Karte „Tempo ändern“ liegt. */
const reiterKarten = (b: Knoten) =>
	mitTestid(b, 'tempo-karte').filter(
		(k) => !vorfahren(k as never).some((v: Knoten) => v.attrs['data-testid'] === 'etappen-tempo-karte' || /\btempo-karte-mobil\b/.test(v.attrs.class ?? ''))
	);

async function panel(start: [string, string][], props: Record<string, unknown>): Promise<Knoten> {
	const K = await T.variante(PANEL, start);
	return baum(render(K as never, { props: { stages: etappen(), tripId: 't', showSave: false, tempo: TRIP_TEMPO, ...props } } as never).body);
}

const LAYOUTS: Array<{ name: string; start: [string, string][]; props: Record<string, unknown> }> = [
	{ name: 'Liste (Hub, listeZuerst)', start: [], props: { kopf: kopf(), listeZuerst: true } },
	{ name: 'Band (Computer, ohne listeZuerst)', start: [], props: { kopf: kopf(), listeZuerst: false } },
	{ name: 'mobil', start: [MOBIL], props: { kopf: kopf() } }
];

describe('#3436 AC-1: Tempo-Karte im Reiter Etappen liegt unter data-abschnitt="tempo"', () => {
	for (const l of LAYOUTS) {
		test(`${l.name}: genau ein Haken, er umschließt die Tempo-Karte, nicht Kopf oder Etappen`, async () => {
			const b = await panel(l.start, { ...l.props, kopf: kopf() });
			const karten = reiterKarten(b);
			assert.equal(karten.length, 1, `Messaufbau ${l.name}: ${karten.length} Tempo-Karten des Reiters im Render (erwartet 1)`);
			assert.ok(unterHaken(karten[0]), `${l.name}: die Tempo-Karte liegt in keinem Element mit data-abschnitt="tempo"`);
			assert.equal(hakenZahl(b), 1, `${l.name}: data-abschnitt="tempo" steht ${hakenZahl(b)}× im Render (erwartet genau 1)`);
			const bereich = alle(b as never, istHaken)[0] as Knoten;
			assert.equal(mitTestid(bereich, 'probe-kopf').length, 0, `${l.name}: der Haken umschließt den Bereichskopf`);
			for (const id of ['etappen-liste-zeile', 'mobile-stages-list', 'etappen-tempo-aendern']) {
				assert.equal(mitTestid(bereich, id).length, 0, `${l.name}: der Haken umschließt ${id}`);
			}
		});
	}
});

describe('#3436 AC-2: kein Haken an der Tempo-Karte beim Anlegen und an „Tempo ändern“', () => {
	for (const mobil of [false, true]) {
		test(`Anlegen (${mobil ? 'Handy' : 'Computer'}, Reiter Route): Tempo-Karte gerendert, kein data-abschnitt="tempo"`, async () => {
			const K = await T.komp(EDITOR);
			const b = baum(T.html(K, { stateOverride: { activeTab: 'route', isMobileViewport: mobil, name: 'GR20', startDate: '2026-07-01' } }));
			const karten = mitTestid(b, 'tempo-karte');
			assert.equal(karten.length, 1, `Messaufbau Anlegen ${mobil ? 'Handy' : 'Computer'}: ${karten.length} Tempo-Karten (erwartet 1)`);
			assert.ok(!unterHaken(karten[0]), 'Tempo-Karte beim Anlegen liegt unter data-abschnitt="tempo"');
			assert.equal(hakenZahl(b), 0, `Anlegen trägt data-abschnitt="tempo" ${hakenZahl(b)}×`);
		});
		test(`Anlegen (${mobil ? 'Handy' : 'Computer'}, eingebetteter Etappen-Editor): kein data-abschnitt="tempo"`, async () => {
			const K = await T.komp(EDITOR);
			const b = baum(
				T.html(K, { stateOverride: { activeTab: 'wegpunkte', isMobileViewport: mobil, name: 'GR20', startDate: '2026-07-01', stageNames: ['Calenzana'] } })
			);
			assert.equal(hakenZahl(b), 0, `Etappen-Editor im Anlegen trägt data-abschnitt="tempo" ${hakenZahl(b)}×`);
		});
	}

	test('Etappen-Karte „Tempo ändern“ (Computer-Liste): TempoKarteInhalt mit nurGrundtempo ohne Haken', async () => {
		const b = await panel([TEMPO_OFFEN('S1')], { kopf: kopf(), listeZuerst: true });
		const offen = mitTestid(b, 'etappen-tempo-karte');
		assert.equal(offen.length, 1, `Messaufbau: ${offen.length} offene „Tempo ändern“-Karten (erwartet 1)`);
		const karte = mitTestid(offen[0], 'tempo-karte');
		assert.equal(karte.length, 1, 'Messaufbau: TempoKarteInhalt fehlt in der „Tempo ändern“-Karte');
		assert.equal(mitTestid(karte[0], 'tempo-trip-verwenden').length, 1, 'Messaufbau: Karte ist nicht die nurGrundtempo-Variante');
		assert.ok(!unterHaken(karte[0]), '„Tempo ändern“-Karte liegt unter data-abschnitt="tempo"');
		assert.equal(alle(offen[0] as never, istHaken).length, 0, '„Tempo ändern“-Karte enthält data-abschnitt="tempo"');
	});

	test('Etappen-Karte „Tempo ändern“ (mobil, StageCardM): ohne Haken', async () => {
		const b = await panel([MOBIL, TEMPO_OFFEN('S1')], { kopf: kopf() });
		const offen = alle(b as never, (n: Knoten) => /\btempo-karte-mobil\b/.test(n.attrs.class ?? '')) as Knoten[];
		assert.equal(offen.length, 1, `Messaufbau: ${offen.length} offene mobile „Tempo ändern“-Karten (erwartet 1)`);
		const karte = mitTestid(offen[0], 'tempo-karte');
		assert.equal(karte.length, 1, 'Messaufbau: TempoKarteInhalt fehlt in der mobilen „Tempo ändern“-Karte');
		assert.ok(!unterHaken(karte[0]), 'mobile „Tempo ändern“-Karte liegt unter data-abschnitt="tempo"');
		assert.equal(alle(offen[0] as never, istHaken).length, 0, 'mobile „Tempo ändern“-Karte enthält data-abschnitt="tempo"');
	});
});
