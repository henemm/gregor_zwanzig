// TDD RED — Issue #2837 Scheibe S1 (Epic #2345): geteilter Hub-Kopf `HubKopf` für
// Trip (`context="route"`) und Ortsvergleich (`context="vergleich"`).
// Spec: docs/specs/modules/rework_2837_s1_hub_kopf.md
//   Entscheidungen 1 (ein Markup, context nur Textwahl/Datenmarke), 2 (Senden
//   Btn primary in der Leiste), 3 (Vergleich-Entwurf: „Setup abschließen" auf dem
//   Platz von Senden), 4 (Breadcrumb Elternteil Link, Kind kein Link), 5 (Status als
//   Badge in der Titelzeile), 6 (Kebab vertikal), 10 (testids).
//   AC-1, AC-3, AC-4, AC-6, AC-7, AC-9, AC-11, AC-13 (Baustein-Anteil).
//
// Echte Komponente, serverseitig gerendert (svelte/server, Hooks
// frontend/test-svelte-ssr-hooks.mjs) — kein Mock, kein Datei-Grep. Lage-Zusicherungen
// über einen Element-Baum des SSR-Outputs (htmlBaum.ts). Die Wirkung an den Seiten
// prüft hub_kopf_seiten_paritaet.test.ts (beide Seiten gerendert), Farbe/Lage im
// echten Browser die E2E frontend/e2e/hub-kopf-paritaet-compare-trip.spec.ts.
//
// Vertrag (Spec „Implementation Details" Punkt 2; Kebab-Namen von RED festgelegt):
//   context, parent {label, href}, crumb, sendLabel, onSend, sendDisabled,
//   sendMode ('senden' | 'setup'), onSetup (Klick auf „Setup abschließen“, von RED festgelegt), titleSize, testidPrefix (an SubscriptionHeader),
//   Durchreichung name/region/profile/profileOptions/profileLabel/regionMaxLength/
//   titleTestid/saveController/onSaveField, Snippets status/eyebrow/namePrefix/meta/
//   meldungen; Kebab: actions, onSelect (wie SubscriptionKebab), mobil, onSheetOpen.
//   Gemeinsame testids: hub-kopf-leiste, hub-kopf-breadcrumb, hub-kopf-status;
//   Senden bleibt `subscription-hub-send`, Kebab `subscription-kebab`.
//
// RED HEUTE: `shared/hub-kopf/HubKopf.svelte` existiert nicht. Import in `lade()`,
// damit jeder Test einzeln mit eigener Meldung scheitert.
//
// Pfadregel #1409: Prüfling relativ zu DIESER Datei.
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/components/shared/hub-kopf/__tests__/hub_kopf_baustein.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { baum, alle, einzig, mitTestid, text, liegtIn, lage, vorfahren, type Knoten } from './htmlBaum.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> hub-kopf -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const { render } = await import('svelte/server');
const { createRawSnippet } = await import('svelte');
const { locale, trFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const PRUEFLING = path.join(HERE, '..', 'HubKopf.svelte');
async function lade(): Promise<unknown> {
	return (await import(pathToFileURL(PRUEFLING).href)).default;
}

afterEach(() => locale.set('de'));

type Ctx = 'route' | 'vergleich';
const roh = (html: string) => createRawSnippet(() => ({ render: () => html }));

const OPTIONEN = [
	{ value: 'trekking', label: 'Trekking' },
	{ value: 'skitour', label: 'Skitour' }
];

/** Gleiche Durchreich-Props für beide Arten: der EINZIGE Unterschied ist context/parent/crumb. */
function props(context: Ctx, extra: Record<string, unknown> = {}, lang: 'de' | 'en' = 'de'): Record<string, unknown> {
	const parent =
		context === 'route'
			? { label: trFor(lang, 'listen.trips.titel'), href: '/trips' }
			: { label: trFor(lang, 'listen.vergleiche.titel'), href: '/compare' };
	return {
		context,
		parent,
		crumb: context === 'route' ? 'GR20' : 'Dolomiten Süd',
		sendLabel: trFor(lang, 'aktionen.senden'),
		onSend: () => {},
		sendDisabled: false,
		sendMode: 'senden',
		onSetup: () => {},
		actions: [{ id: 'pause', label: 'Pausieren' }],
		onSelect: () => {},
		mobil: false,
		onSheetOpen: () => {},
		name: context === 'route' ? 'GR20 Nord' : 'Dolomiten Süd',
		region: 'Korsika',
		profile: 'trekking',
		profileOptions: OPTIONEN,
		profileLabel: 'Trekking',
		regionMaxLength: 60,
		testidPrefix: 'kopf',
		titleSize: 38,
		onSaveField: async () => {},
		status: roh('<span data-testid="probe-status-badge">Aktiv</span>'),
		...extra
	};
}

async function render_(p: Record<string, unknown>): Promise<{ html: string; wurzel: Knoten }> {
	const Komponente = await lade();
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const html = render(Komponente as any, { props: p }).body;
	return { html, wurzel: baum(html) };
}

const h1 = (w: Knoten): Knoten => {
	const t = alle(w, (n) => n.tag === 'h1');
	assert.equal(t.length, 1, `genau eine Überschrift erwartet, gefunden ${t.length}`);
	return t[0];
};

for (const context of ['route', 'vergleich'] as const) {
	describe(`#2837 S1 HubKopf (${context}) — Leiste, Breadcrumb, Senden`, () => {
		test(`AC-11 (${context}): genau eine Leiste und genau eine Überschrift; Leiste steht VOR der Überschrift`, async () => {
			const { wurzel } = await render_(props(context));
			const leiste = einzig(wurzel, 'hub-kopf-leiste');
			const titel = h1(wurzel);
			assert.ok(leiste.nr < titel.nr, 'die Leiste muss oben stehen (vor dem Titel)');
			assert.ok(!liegtIn(titel, leiste), 'die Überschrift darf nicht IN der Leiste stehen');
		});

		test(`Entscheidung 1 (${context}): data-kind="${context}" am Baustein (Vorfahre der Leiste)`, async () => {
			const { wurzel } = await render_(props(context));
			const leiste = einzig(wurzel, 'hub-kopf-leiste');
			const marke = [leiste, ...vorfahren(leiste)].find((n) => n.attrs['data-kind'] !== undefined);
			assert.ok(marke, 'kein Element mit data-kind über der Leiste');
			assert.equal(marke.attrs['data-kind'], context);
		});

		test(`AC-4 (${context}): Breadcrumb — Elternteil ist EIN Link auf die Liste mit Katalogtext, Kind ist kein Link`, async () => {
			const p = props(context);
			const { wurzel } = await render_(p);
			const leiste = einzig(wurzel, 'hub-kopf-leiste');
			const krumen = einzig(wurzel, 'hub-kopf-breadcrumb');
			assert.ok(liegtIn(krumen, leiste), 'Breadcrumb steht nicht in der Leiste');
			const links = alle(krumen, (n) => n.tag === 'a');
			assert.equal(links.length, 1, `genau ein Link im Breadcrumb erwartet, gefunden ${links.length}`);
			const eltern = p.parent as { label: string; href: string };
			assert.equal(links[0].attrs.href, eltern.href);
			assert.equal(text(links[0]), eltern.label, 'Elternteil-Text muss der Katalogtext sein (keine Großschreibung im Markup)');
			assert.ok(text(krumen).includes(String(p.crumb)), `Kind „${p.crumb}" fehlt im Breadcrumb: „${text(krumen)}"`);
			assert.ok(!text(links[0]).includes(String(p.crumb)), 'das Kind darf nicht Teil des Links sein');
		});

		test(`AC-4 (${context}): kein Krümel „Hub" in der Leiste`, async () => {
			const { wurzel } = await render_(props(context));
			const t = text(einzig(wurzel, 'hub-kopf-leiste'));
			assert.ok(!/(?<![A-Za-zÄÖÜäöü])Hub(?![A-Za-zÄÖÜäöü])/.test(t), `„Hub" steht in der Leiste: „${t}"`);
		});

		test(`AC-2 (${context}): mobiler Zurück-Link in der Leiste, Ziel = Liste, Aria-Text aus dem Katalog`, async () => {
			const p = props(context);
			const { wurzel } = await render_(p);
			const leiste = einzig(wurzel, 'hub-kopf-leiste');
			const zurueck = alle(leiste, (n) => n.attrs['data-testid'] === 'back-link');
			assert.equal(zurueck.length, 1, `genau ein Zurück-Link in der Leiste erwartet, gefunden ${zurueck.length}`);
			assert.equal(zurueck[0].attrs.href, (p.parent as { href: string }).href);
			assert.equal(zurueck[0].attrs['aria-label'], trFor('de', 'aktionen.zurueck_uebersicht'));
		});

		test(`AC-1 (${context}): Senden ist Btn primary in der Leiste (testid subscription-hub-send), Text = sendLabel`, async () => {
			const { wurzel } = await render_(props(context));
			const leiste = einzig(wurzel, 'hub-kopf-leiste');
			const senden = einzig(wurzel, 'subscription-hub-send');
			assert.ok(liegtIn(senden, leiste), 'Senden steht nicht in der Leiste');
			assert.equal(senden.tag, 'button');
			assert.equal(senden.attrs['data-slot'], 'btn', 'Senden ist kein Btn');
			assert.equal(senden.attrs['data-variant'], 'primary', `Senden hat variant „${senden.attrs['data-variant']}" (erwartet primary = Ink)`);
			assert.equal(text(senden), trFor('de', 'aktionen.senden'));
			assert.ok(!('disabled' in senden.attrs), 'Senden ist ohne sendDisabled gesperrt');
		});

		test(`AC-3 (${context}): sendDisabled ⇒ Senden sichtbar gesperrt (disabled), bleibt an seinem Platz`, async () => {
			const frei = await render_(props(context));
			const gesperrt = await render_(props(context, { sendDisabled: true }));
			const s = einzig(gesperrt.wurzel, 'subscription-hub-send');
			assert.ok('disabled' in s.attrs, 'Senden ist trotz sendDisabled nicht disabled');
			const leisteF = einzig(frei.wurzel, 'hub-kopf-leiste');
			const leisteG = einzig(gesperrt.wurzel, 'hub-kopf-leiste');
			assert.equal(lage(s, leisteG), lage(einzig(frei.wurzel, 'subscription-hub-send'), leisteF), 'gesperrtes Senden sitzt an anderer Stelle');
		});

		test(`Entscheidung 6 (${context}): Kebab steht in der Leiste, Symbol vertikal (Desktop und mobil)`, async () => {
			for (const mobil of [false, true]) {
				const { html, wurzel } = await render_(props(context, { mobil }));
				const leiste = einzig(wurzel, 'hub-kopf-leiste');
				const kebab = mitTestid(wurzel, 'subscription-kebab');
				assert.equal(kebab.length, 1, `mobil=${mobil}: genau ein Kebab erwartet, gefunden ${kebab.length}`);
				assert.ok(liegtIn(kebab[0], leiste), `mobil=${mobil}: Kebab steht nicht in der Leiste`);
				const icons = alle(kebab[0], (n) => n.tag === 'svg').map((n) => n.attrs.class ?? '');
				assert.ok(icons.some((c) => /\blucide-ellipsis-vertical\b/.test(c)), `mobil=${mobil}: kein vertikales Symbol (${icons.join(' | ')})`);
				assert.ok(!/lucide-ellipsis(?!-vertical)|lucide-more-horizontal/.test(html), `mobil=${mobil}: horizontales Symbol im Kopf`);
			}
		});

		test(`AC-6 (${context}): status-Snippet landet genau einmal als Badge in der TITELZEILE (gleiches Elternelement wie die Überschrift)`, async () => {
			const { wurzel } = await render_(props(context));
			const titel = h1(wurzel);
			const huelle = einzig(wurzel, 'hub-kopf-status');
			assert.equal(mitTestid(wurzel, 'probe-status-badge').length, 1, 'Status nicht genau einmal');
			assert.ok(liegtIn(einzig(wurzel, 'probe-status-badge'), huelle), 'Status steht nicht in hub-kopf-status');
			// #2878: Überschrift und Stift bilden eine innere Gruppe in der Titelzeile (Stift springt beim
			// Umbruch nie allein weg) — die Titelzeile ist daher das Elternelement dieser Gruppe.
			assert.equal(huelle.eltern, titel.eltern?.eltern, 'hub-kopf-status steht nicht in derselben Zeile wie die Überschrift');
		});

		test(`AC-9 (${context}): titleSize 38 wird an die Überschrift durchgereicht`, async () => {
			const { wurzel } = await render_(props(context));
			assert.ok((h1(wurzel).attrs.class ?? '').includes('desktop:text-[38px]'), `h1-Klasse: ${h1(wurzel).attrs.class}`);
		});
	});
}

describe('#2837 S1 Entscheidung 3 — Vergleich-Entwurf: „Setup abschließen" auf dem Platz von Senden', () => {
	test('sendMode="setup": kein subscription-hub-send, statt dessen Btn primary mit dem Setup-Text an derselben Stelle', async () => {
		const senden = await render_(props('vergleich'));
		const setupLabel = trFor('de', 'vergleich.hub.setup_abschliessen');
		const setup = await render_(props('vergleich', { sendMode: 'setup', sendLabel: setupLabel }));
		assert.equal(mitTestid(setup.wurzel, 'subscription-hub-send').length, 0, 'im Setup-Modus darf kein Senden-Knopf stehen');
		const leiste = einzig(setup.wurzel, 'hub-kopf-leiste');
		const knopf = alle(leiste, (n) => n.attrs['data-slot'] === 'btn' && text(n) === setupLabel);
		assert.equal(knopf.length, 1, `„${setupLabel}" nicht genau einmal als Btn in der Leiste`);
		assert.equal(knopf[0].attrs['data-variant'], 'primary');
		assert.equal(
			lage(knopf[0], leiste),
			lage(einzig(senden.wurzel, 'subscription-hub-send'), einzig(senden.wurzel, 'hub-kopf-leiste')),
			'„Setup abschließen" sitzt nicht auf dem Platz von „Senden"'
		);
	});
});

describe('#2837 S1 Entscheidung 1 — ein Markup, context wählt nur Text und Datenmarke', () => {
	/** Tag-Folge des Gerüsts: Tag + testid + Klassen + data-slot/-variant; Texte und Hrefs weg. */
	const geruest = (w: Knoten): string[] =>
		alle(w, () => true).map(
			(n) => `${n.tag}|${n.attrs['data-testid'] ?? ''}|${n.attrs.class ?? ''}|${n.attrs['data-slot'] ?? ''}|${n.attrs['data-variant'] ?? ''}`
		);

	test('route und vergleich rendern dasselbe Gerüst (gleiche Durchreich-Props)', async () => {
		const a = await render_(props('route'));
		const b = await render_(props('vergleich'));
		assert.deepEqual(geruest(b.wurzel), geruest(a.wurzel));
	});

	test('mobil: route und vergleich rendern dasselbe Gerüst', async () => {
		const a = await render_(props('route', { mobil: true }));
		const b = await render_(props('vergleich', { mobil: true }));
		assert.deepEqual(geruest(b.wurzel), geruest(a.wurzel));
	});

	test('der einzige Attribut-Unterschied ist data-kind (und die Eltern-Hrefs)', async () => {
		const attrs = (w: Knoten) =>
			alle(w, () => true).map((n) =>
				Object.entries(n.attrs)
					.filter(([k]) => k !== 'data-kind' && k !== 'href' && k !== 'id' && !k.startsWith('aria-controls'))
					.map(([k, v]) => `${k}=${v}`)
					.join(' ')
			);
		const a = await render_(props('route'));
		const b = await render_(props('vergleich'));
		assert.deepEqual(attrs(b.wurzel), attrs(a.wurzel));
	});
});

// Adversary F006 (#2837 S1): die Optik des HubKopf darf nicht nach Art unterscheiden — weder über
// das Stylesheet (Selektor nach data-kind bzw. einer aus context abgeleiteten Klasse) noch über
// class/style im Markup. Das Markup deckt „der einzige Attribut-Unterschied ist data-kind" oben ab
// (alle Attribute inkl. class/style, beide Arten mit identischen Durchreich-Props gerendert);
// hier zusätzlich class/style ausdrücklich, mobil wie Desktop, und das ECHTE Stylesheet.
// Ausnahme Testids: der Präfix (`testidPrefix`, z. B. trip-/compare-hub-) kommt bewusst von der Seite
// und ist Prüf-Anker, keine Optik; im Baustein-Render tragen beide Arten denselben Präfix.
describe('#2837 S1 Entscheidung 1 / F006 — keine Optik nach Art', () => {
	test('kompiliertes CSS des HubKopf: kein Selektor nach data-kind oder nach Art benannten Klassen', async () => {
		const { compile } = await import('svelte/compiler');
		const { readFileSync } = await import('node:fs');
		const css = (compile(readFileSync(PRUEFLING, 'utf-8'), { generate: 'client', filename: PRUEFLING }).css?.code ?? '').replace(/\/\*[\s\S]*?\*\//g, '');
		assert.ok(css.includes('.hub-kopf'), 'Messaufbau: kein Stylesheet des HubKopf gefunden');
		const selektoren = [...css.matchAll(/([^{}@]+)\{/g)].map((m) => m[1].trim());
		const nachArt = selektoren.filter((s) => /data-kind|\[kind\b|\.(route|vergleich|trip|compare)(?![a-zA-Z0-9_-])|\.kind-|\.context-/.test(s));
		assert.deepEqual(nachArt, [], 'Stylesheet unterscheidet nach Art (F006)');
	});
	for (const mobil of [false, true]) {
		test(`class und style aller Elemente gleich für route und vergleich (mobil=${mobil})`, async () => {
			const stil = (w: Knoten) => alle(w, () => true).map((n) => `${n.tag}|${n.attrs.class ?? ''}|${n.attrs.style ?? ''}`);
			const a = await render_(props('route', { mobil }));
			const b = await render_(props('vergleich', { mobil }));
			assert.deepEqual(stil(b.wurzel), stil(a.wurzel));
		});
	}
});

describe('#2837 S1 AC-13 — Texte des Bausteins aus dem Katalog (de und en)', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: Aria-Texte von Zurück und Kebab folgen der Nutzersprache`, async () => {
			locale.set('de');
			const de = await render_(props(context, {}, 'de'));
			locale.set('en');
			const en = await render_(props(context, {}, 'en'));
			for (const [lang, r] of [['de', de], ['en', en]] as const) {
				const leiste = einzig(r.wurzel, 'hub-kopf-leiste');
				const zurueck = alle(leiste, (n) => n.attrs['data-testid'] === 'back-link')[0];
				assert.ok(zurueck, `${lang}: kein Zurück-Link`);
				assert.equal(zurueck.attrs['aria-label'], trFor(lang, 'aktionen.zurueck_uebersicht'), `${lang}: Zurück-Aria`);
				assert.equal(einzig(r.wurzel, 'subscription-kebab').attrs['aria-label'], trFor(lang, 'aktionen.weitere'), `${lang}: Kebab-Aria`);
			}
			assert.equal(text(alle(einzig(en.wurzel, 'hub-kopf-breadcrumb'), (n) => n.tag === 'a')[0]), trFor('en', context === 'route' ? 'listen.trips.titel' : 'listen.vergleiche.titel'));
		});
	}
});
