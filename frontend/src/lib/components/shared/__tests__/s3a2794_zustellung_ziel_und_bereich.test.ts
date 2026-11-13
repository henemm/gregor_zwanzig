// Issue #2794 S3a, Teil-PR 2 (Fix-Loop 2, Adversary Runde 3: F007 + F008).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-6 (Anlege-Kette Trip endet auf
// Zustellung, kein Schritt fuehrt auf einen falschen Reiter), AC-1/AC-7 (Reiter Zustellung zeigt
// die Zustellungs-Abschnitte, nicht die Wetter-Oberflaeche).
//
// F007 — Wirkstelle: der Knopf „Zustellung einrichten →“ im Trip-Anlegen (Desktop
// `trip-new-continue-zustellung`, Mobil der MBtn im Schritt Wetter). Der Alt-Test
// (anlege_weiter_knopf_zielt_auf_existierenden_reiter) prueft nur „Ziel = Literal im Aufruf“,
// er bleibt gruen, wenn der Knopf `makeEtappenContinueHandler('wetter')` ruft (Mutation N2).
// Hier wird das Ziel an das gebunden, was der Nutzer SIEHT (testid bzw. Katalogschluessel der
// Beschriftung), und der onclick-Ausdruck gegen das ECHTE Instanz-Skript des Editors
// ausgefuehrt (svelteInstanzPruefstand): gemessen wird `activeTab` nach dem Klick.
//
// F008 — Wirkstelle: der Wert, den ZustellungTab dem Panel als `bereich` uebergibt (AST der
// echten Einbettung), und was dieser Wert im echten Abschnitts-Filter
// (weatherMetricsTabSections) bewirkt. Mutation N12 (`bereich="alles"`) muss rot werden.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_zustellung_ziel_und_bereich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { svelteAst, einbettungenMitWeichen, attribut, type Knoten } from './s3a2794Ast.ts';
import { umgebungFuer, werte } from './svelteInstanzPruefstand.ts';
import { weatherMetricsTabSections } from '../weather-metrics-tab/weatherMetricsTabSections.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const KOMP = join(HIER, '..', '..');
register(
	pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const DATEI = {
	tripNeu: join(KOMP, 'trip-new', 'TripNewEditor.svelte'),
	zustellung: join(KOMP, 'shared', 'zustellung-tab', 'ZustellungTab.svelte'),
	// #2795 S3b Teilschritt 1b: das Panel steht im Uebergangsblock des Reiters (Mount-Ort).
	uebergang: join(KOMP, 'organisms', 'zustellung-tab', 'UebergangBlock.svelte'),
	panel: join(KOMP, 'shared', 'WetterMetrikenVersandPanel.svelte')
};

const LABEL_ZUSTELLUNG = 'trip.anlegen.zustellung_einrichten';
const TESTID_ZUSTELLUNG = 'trip-new-continue-zustellung';

/** Katalogschluessel aller `$t('…')`-Beschriftungen direkt im Inhalt eines Knopfs. */
function beschriftungsSchluessel(k: Knoten): string[] {
	const out: string[] = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const x = n as Knoten;
		if (x.type === 'CallExpression' && x.callee?.type === 'Identifier' && x.callee.name === '$t') {
			const a = x.arguments?.[0];
			if (a?.type === 'Literal' && typeof a.value === 'string') out.push(a.value);
		}
		for (const [f, v] of Object.entries(x)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
	})(k.fragment);
	return out;
}

/** Alle Knoepfe (Element oder Komponente) mit onclick, die „Zustellung einrichten“ zeigen. */
function zustellungsKnoepfe(ast: Knoten, quelle: string): Array<{ wo: string; onclick: string }> {
	const out: Array<{ wo: string; onclick: string }> = [];
	(function lauf(n: unknown): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if ((k.type === 'Component' || k.type === 'RegularElement') && Array.isArray(k.attributes)) {
			const oc = attribut(k, quelle, 'onclick');
			const tid = attribut(k, quelle, 'data-testid')?.literal;
			if (oc?.ausdruck && (tid === TESTID_ZUSTELLUNG || beschriftungsSchluessel(k).includes(LABEL_ZUSTELLUNG))) {
				out.push({ wo: `${k.name}${tid ? `[${tid}]` : ''}@${k.start}`, onclick: oc.ausdruck });
			}
		}
		for (const [f, v] of Object.entries(k)) if (f !== 'parent' && f !== 'loc' && f !== 'metadata') lauf(v);
	})(ast.fragment);
	return out;
}

async function tripEditor() {
	return umgebungFuer(
		DATEI.tripNeu,
		{
			untrack: (f: () => unknown) => f(),
			stateOverride: { activeTab: 'wetter', name: 'GR20', startDate: '2026-07-01' }
		},
		{ jsAlsTs: true }
	);
}

// ── F007: „Zustellung einrichten →“ im Trip-Anlegen fuehrt auf den Schritt zustellung ──

describe('AC-6 (F007): Trip-Anlegen — „Zustellung einrichten →“ schaltet auf den Schritt Zustellung', () => {
	test('s3a2794_f007_trip_zustellung_einrichten_klick_fuehrt_auf_zustellung', async () => {
		const { u, ast, quelle } = await tripEditor();
		const knoepfe = zustellungsKnoepfe(ast, quelle);
		// Desktop-Fuss (testid) und Mobil-Fuss (Beschriftung) — beide muessen da sein.
		assert.ok(
			knoepfe.some((k) => k.wo.includes(`[${TESTID_ZUSTELLUNG}]`)),
			`Messaufbau: Desktop-Knopf ${TESTID_ZUSTELLUNG} nicht gefunden (${knoepfe.map((k) => k.wo).join(', ')})`
		);
		assert.ok(knoepfe.length >= 2, `Messaufbau: erwartet Desktop- und Mobil-Knopf, gefunden ${knoepfe.length}`);
		for (const { wo, onclick } of knoepfe) {
			u.activeTab = 'wetter';
			(werte(onclick, u) as () => void)();
			assert.equal(u.activeTab, 'zustellung', `F007: ${wo} (${onclick}) schaltet auf '${u.activeTab}' statt auf 'zustellung'`);
		}
	});
});

// ── F008: ZustellungTab gibt dem Panel bereich="zustellung" ──────────────────────────

describe('AC-1/AC-7 (F008): ZustellungTab zeigt am Panel nur die Zustellungs-Abschnitte', () => {
	test('s3a2794_f008_zustellungtab_uebergibt_bereich_zustellung_und_filter_wirkt', () => {
		// #2795 S3b 1b: ZustellungTab -> UebergangBlock (genau einmal) -> Panel; gemessen am Panel-Mount.
		const z = svelteAst(DATEI.zustellung);
		assert.equal(einbettungenMitWeichen(z.ast, z.quelle, ['WetterMetrikenVersandPanel']).length, 0, 'F008: ZustellungTab bettet das Panel zusaetzlich direkt ein');
		assert.equal(einbettungenMitWeichen(z.ast, z.quelle, ['UebergangBlock']).length, 1, 'Messaufbau: ZustellungTab bettet den Uebergangsblock nicht genau einmal ein');
		const { ast, quelle } = svelteAst(DATEI.uebergang);
		const panel = einbettungenMitWeichen(ast, quelle, ['WetterMetrikenVersandPanel']);
		assert.equal(panel.length, 1, `Messaufbau: der Uebergangsblock bettet das Panel ${panel.length}× ein (erwartet 1)`);
		const attrs = panel[0].knoten.attributes as Knoten[];
		const b = attribut(panel[0].knoten, quelle, 'bereich');
		assert.ok(b, 'F008: ZustellungTab uebergibt dem Panel kein `bereich` — der Reiter zeigte alles (Wetter + Zustellung)');
		assert.equal(b!.literal, 'zustellung', `F008: ZustellungTab uebergibt bereich=${JSON.stringify(b)} statt "zustellung"`);
		// Reihenfolge: das feste `bereich` steht NACH der Streuung, sonst koennte die Streuung es ueberschreiben.
		const iBereich = attrs.findIndex((a) => a.type === 'Attribute' && a.name === 'bereich');
		const iSpread = attrs.findIndex((a) => a.type === 'SpreadAttribute');
		assert.ok(iSpread === -1 || iBereich > iSpread, 'F008: `bereich` steht vor der Streuung und kann ueberschrieben werden');

		// Wirkung des Werts im echten Abschnitts-Filter, beide Kontexte: keine Wetter-Abschnitte.
		for (const ctx of ['route', 'vergleich'] as const) {
			const zu = weatherMetricsTabSections(ctx, b!.literal as 'zustellung');
			const wetter = weatherMetricsTabSections(ctx, 'wetter');
			assert.ok(zu.length > 0, `F008 (${ctx}): Zustellung ohne Abschnitte`);
			for (const s of ['grundauswahl', 'tagesfenster']) {
				assert.ok(!zu.includes(s), `F008 (${ctx}): Reiter Zustellung zeigt den Wetter-Abschnitt '${s}' (${zu.join(', ')})`);
			}
			assert.deepEqual(zu.filter((s) => wetter.includes(s)), [], `F008 (${ctx}): Zustellung und Wetter ueberschneiden sich`);
		}
	});

	test('s3a2794_f008_panel_reicht_bereich_an_weathermetricstab_durch', () => {
		const { ast, quelle } = svelteAst(DATEI.panel);
		const wmt = einbettungenMitWeichen(ast, quelle, ['WeatherMetricsTab']);
		assert.equal(wmt.length, 1, `Messaufbau: das Panel bettet WeatherMetricsTab ${wmt.length}× ein`);
		assert.equal(attribut(wmt[0].knoten, quelle, 'bereich')?.ausdruck, 'bereich', 'F008: das Panel reicht `bereich` nicht an WeatherMetricsTab');
	});
});
