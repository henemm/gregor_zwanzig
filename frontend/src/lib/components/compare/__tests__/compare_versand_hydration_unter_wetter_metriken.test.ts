// TDD RED — Issue #1743 (Spec feat_1743_reiter_aufraeumen §4, AC-3, AC-9): im Ortsvergleich-Hub
// haengen Versand- und Wetter-Hydration beide am Reiter `wetter-metriken`. Wer den Hub mit
// `?tab=wetter-metriken#versand` (oder dem Alt-Link `?tab=versand`) oeffnet, bekommt den
// Versand-Abschnitt mit den GESPEICHERTEN Werten — nie mit Platzhaltern.
//
// Messweise (Muster hub_reiter_gemeinsame_aufloesung.test.ts): das ECHTE Instanz-Skript von
// CompareTabs wird mit gesaetem Vergleich ausgewertet; ausgefuehrt wird der ECHTE
// Versand-Hydrations-Effekt (ausgewaehlt ueber den Aufruf `hydrateVersandFieldsFromPreset`).
// Issue #2727 (Epic #2345, DoD-1; Spec feat_2727_compare_wizardstate_abloesen.md AC-15/AC-22): der
// Hub haelt seinen Feldsatz lokal als `$state(compareFeldsatzStandard())` — der Pruefstand wertet
// diese Deklaration SELBST aus (frueher wurde ein leeres Objekt gesaet, weil die Klasse nicht
// bindbar war). Der Feldsatz wird ueber das Argument von `versandPropsAus(…)` im Markup gefunden,
// nicht ueber einen Variablennamen. Neu: Fall „Daten kommen spaet" (erst Standard lesen, dann
// hydrieren; ein vorher gesetzter Nutzerwert in einem nicht hydrierten Feld bleibt).
// Heute rot (nur die Faelle mit Feldsatz): der Hub instanziiert noch die Klasse (VERTRAG FEHLT).
// Zusaetzlich (Template-AST): der Baustein im Panel `wetter-metriken` haengt am Flag
// `versandHydrated` (umschliessender Block oder Prop) — er mountet also erst nach der Hydration.
//
// Grenze: „kein PUT mit Platzhaltern" bei verzoegerter Hydration im Browser misst Playwright (/50);
// der Speicherweg selbst ist in wetter_metriken_versand_panel_speicherung.test.ts bewacht.
//
// Pfadregel #1409: Pruefling relativ zu DIESER Datei.
//
// Ausfuehren (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/compare/__tests__/compare_versand_hydration_unter_wetter_metriken.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { umgebungFuer, effekteVon, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';
import { vollerVergleich } from '../../shared/__tests__/goMergeServerPruefstand.ts';
import { hydrateVersandFieldsFromPreset } from '../../shared/versandVergleichSpeicherung.ts';
import { versandPropsAus } from '../versandPropsAus.ts';
import { alarmePropsAus } from '../alarmePropsAus.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../..');
const HUB = join(HIER, '..', 'CompareTabs.svelte');
register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const globaleAlt = { window: (globalThis as Knoten).window, history: (globalThis as Knoten).history };
afterEach(() => {
	(globalThis as Knoten).window = globaleAlt.window;
	(globalThis as Knoten).history = globaleAlt.history;
});

/** Vergleich mit gespeicherten Versandwerten, die sich von jedem Platzhalter unterscheiden. */
function gespeicherterVergleich(): Knoten {
	return {
		...vollerVergleich('c-1743'),
		morning_enabled: true,
		morning_time: '05:45:00',
		evening_enabled: true,
		evening_time: '19:15:00',
		send_email: true,
		send_telegram: true,
		send_sms: false
	};
}

async function hubOeffnen(tab: string): Promise<{ u: Knoten; ast: Knoten; quelle: string }> {
	(globalThis as Knoten).window = {
		location: { href: `http://localhost/compare/c-1743?tab=${tab}`, search: `?tab=${tab}`, pathname: '/compare/c-1743', hash: '' },
		matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
	};
	(globalThis as Knoten).history = { state: null, replaceState() {}, pushState() {} };
	const preset = gespeicherterVergleich();
	return umgebungFuer(
		HUB,
		{
			initialTab: tab,
			preset,
			locations: [],
			orteCount: 3,
			goto: () => Promise.resolve(),
			page: { url: new URL(`http://localhost/compare/c-1743?tab=${tab}`) }
		},
		{ jsAlsTs: true }
	);
}

/** Der lokale Feldsatz des Hubs: das Objekt, das der Hub an `wetterMetrikenPropsAus(…)` uebergibt.
 *  #2795 S3b Teilschritt 1b: der Hub ruft versandPropsAus nicht mehr (der neue Reiter Zustellung
 *  liest das Preset selbst); derselbe Feldsatz haengt weiter am Panel-Buendel im Markup. */
function hubFeldsatz(ast: Knoten, u: Knoten): Knoten {
	let name: string | null = null;
	(function lauf(n: unknown): void {
		if (name || n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach(lauf);
		const k = n as Knoten;
		if (k.type === 'CallExpression' && k.callee?.name === 'wetterMetrikenPropsAus' && k.arguments?.[0]?.type === 'Identifier') {
			name = k.arguments[0].name;
			return;
		}
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
	})(ast.fragment);
	assert.ok(name, 'Messaufbau: kein wetterMetrikenPropsAus(<Bezeichner>) im Hub-Markup');
	const f = u[name!];
	assert.ok(
		f && typeof f === 'object',
		`VERTRAG FEHLT (#2727): der Hub haelt keinen eigenen Feldsatz \`${name}\` ($state(compareFeldsatzStandard())) — vom Pruefstand nicht auswertbar`
	);
	return f as Knoten;
}

// Issue #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md AC-2/AC-5): der Versand-Abschnitt liegt im
// Reiter `zustellung`; die Versand-Hydration haengt dort. Alt-Links `?tab=versand`, `?tab=alarme`
// fuehren dorthin. Die Zusicherungen (gespeicherte Werte statt Platzhalter, Nutzerwert bleibt,
// Mount erst nach der Hydration) bleiben.
describe('#1743 AC-9 / #2794: Versand-Hydration haengt am Reiter zustellung', () => {
	for (const tab of ['zustellung', 'versand', 'alarme']) {
		test(`?tab=${tab}: der Versand-Hydrations-Effekt fuellt die gespeicherten Werte (kein Platzhalter)`, async () => {
			const { u, ast, quelle } = await hubOeffnen(tab);
			assert.equal(u.activeTab, 'zustellung', `Vorbedingung: ?tab=${tab} oeffnet Zustellung`);
			const feldsatz = hubFeldsatz(ast, u);
			const effekte = effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset');
			assert.ok(effekte.length >= 1, 'Messaufbau: kein Versand-Hydrations-Effekt gefunden');
			for (const e of effekte) e();
			assert.equal(u.versandHydrated, true, 'die Versand-Hydration laeuft im Reiter zustellung nicht');
			const soll = hydrateVersandFieldsFromPreset(u.currentPreset);
			for (const feld of ['morningEnabled', 'morningTime', 'eveningEnabled', 'eveningTime', 'sendEmail', 'sendTelegram', 'sendSms']) {
				assert.deepEqual(feldsatz[feld], (soll as Knoten)[feld], `Feldsatz.${feld} traegt nicht den gespeicherten Wert`);
			}
		});
	}

	test('#2727 AC-15 „Daten kommen spaet": vor der Hydration Standardwerte, danach Preset-Werte; Nutzerwert bleibt', async () => {
		const { u, ast, quelle } = await hubOeffnen('zustellung');
		const feldsatz = hubFeldsatz(ast, u);
		// Vor der Hydration: der Reiter ist nicht leer, er zeigt die Anlege-Standardwerte.
		const vorher = versandPropsAus(feldsatz);
		assert.equal(vorher.morningTime, '07:00');
		assert.equal(vorher.morningEnabled, true);
		assert.equal(vorher.eveningEnabled, false);
		// Nutzer schaltet im Alarme-Reiter den Radar-Alarm an (Feld, das die Versand-Hydration nicht anfasst).
		alarmePropsAus(feldsatz).onRadarAlertChange(true);
		// Jetzt kommen die Daten: der Versand-Hydrations-Effekt laeuft.
		for (const e of effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset')) e();
		const nachher = versandPropsAus(feldsatz);
		assert.equal(nachher.morningTime, '05:45', 'Versand-Reiter zeigt nach der Hydration nicht den gespeicherten Wert');
		assert.equal(nachher.eveningEnabled, true);
		assert.equal(nachher.eveningTime, '19:15');
		assert.equal(nachher.sendTelegram, true);
		assert.equal(alarmePropsAus(feldsatz).radarAlertEnabled, true, 'die spaete Hydration hat einen Nutzerwert ueberschrieben');
	});

	test('Gegenprobe: im Reiter Uebersicht wird der Versand nicht hydriert (lazy wie bisher)', async () => {
		const { u, ast, quelle } = await hubOeffnen('uebersicht');
		for (const e of effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset')) e();
		assert.equal(u.versandHydrated, false);
	});

	test('Gegenprobe: im Reiter Wetter (ohne Versand-Abschnitt) wird der Versand nicht hydriert', async () => {
		const { u, ast, quelle } = await hubOeffnen('wetter');
		for (const e of effekteVon(ast, quelle, u, 'hydrateVersandFieldsFromPreset')) e();
		assert.equal(u.versandHydrated, false);
	});
});

// ── Template-AST: der Baustein mountet erst nach der Versand-Hydration ─────────

/** Einbettungen `name` samt umschliessender Knoten. */
function mitVorfahren(knoten: unknown, name: string): Array<{ k: Knoten; vorfahren: Knoten[] }> {
	const treffer: Array<{ k: Knoten; vorfahren: Knoten[] }> = [];
	(function lauf(n: unknown, kette: Knoten[]): void {
		if (n === null || typeof n !== 'object') return;
		if (Array.isArray(n)) return n.forEach((x) => lauf(x, kette));
		const k = n as Knoten;
		if (k.type === 'Component' && k.name === name) treffer.push({ k, vorfahren: kette });
		const weiter = typeof k.type === 'string' ? [...kette, k] : kette;
		for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key], weiter);
	})(knoten, []);
	return treffer;
}

// #2794 S3a: der Versand-Abschnitt kommt im Hub ueber den geteilten ZustellungTab (Panel `zustellung`).
describe('#1743 AC-9 (Template): der Zustellungs-Baustein haengt an versandHydrated', () => {
	test('ZustellungTab steht unter einer Bedingung mit versandHydrated oder erhaelt das Flag als Prop', async () => {
		const { ast, quelle } = await hubOeffnen('zustellung');
		const treffer = mitVorfahren(ast.fragment, 'ZustellungTab');
		assert.equal(treffer.length, 1, 'genau ein ZustellungTab im Vergleichs-Hub erwartet');
		const { k, vorfahren } = treffer[0];
		const imBlock = vorfahren.some(
			(v) => v.type === 'IfBlock' && /\bversandHydrated\b/.test(quelle.slice(v.test.start, v.test.end))
		);
		const alsProp = ((k.attributes ?? []) as Knoten[]).some(
			(a) =>
				a.type === 'Attribute' &&
				a.value?.type === 'ExpressionTag' &&
				/\bversandHydrated\b/.test(quelle.slice(a.value.expression.start, a.value.expression.end))
		);
		assert.ok(imBlock || alsProp, 'der Versand-Abschnitt kann vor seiner Hydration mounten (Platzhalter-Risiko)');
	});
});
