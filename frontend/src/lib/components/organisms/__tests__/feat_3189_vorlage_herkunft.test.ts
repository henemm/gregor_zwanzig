// TDD RED — Issue #3189: Herkunft eigener Wetter-Vorlagen (Trip und Orts-Vergleich, geteilter Code), DE und EN.
// Spec: docs/specs/modules/feat_3189_vorlage_herkunft.md (AC-1, AC-4, AC-5; Implementation Details 7 und 8).
//
// Server-Render der ECHTEN VorlageKarte (Muster feat_3111_wetter_dialoge_mockup.test.ts; offenes Menü über
// startzustandHook.mjs), dazu die echten reinen Funktionen aus ampelSchreiben.ts und wetterTabLaden.ts. Kein Mock.
//
// Festgelegte API (neu):
//   EigeneVorlageEingabe.herkunft?: { id: string; name: string }        (ampelSchreiben.ts)
//     eigeneVorlagePayload schreibt `herkunft` nur mit nicht leerem (getrimmtem) Namen.
//   EigeneVorlage.herkunftName?: string                                (wetterTabLaden.ts)
//     eigeneVorlageAus füllt es aus `p.herkunft?.name`.
//   vorlageHerkunft(abo: { id?: unknown; name?: unknown } | undefined, createMode: boolean)
//     -> { id: string; name: string } | undefined                     (wetterTabLaden.ts)
//     Ableitung im Hub (WetterTabInhalt): id = Abo-ID, name = Trip- bzw. Vergleichsname; im Anlege-Modus
//     oder ohne Namen undefined.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test src/lib/components/organisms/__tests__/feat_3189_vorlage_herkunft.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { aufloesungPost, live } from '../../shared/wetter-tab/__tests__/wetterTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../..');
const WT = path.resolve(HERE, '..', 'wetter-tab');
const SHARED_WT = path.resolve(HERE, '../../shared/wetter-tab');

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
register(pathToFileURL(path.join(HERE, 'startzustandHook.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);
const laden: any = await import(pathToFileURL(path.join(SHARED_WT, 'wetterTabLaden.ts')).href);
const schreiben: any = await import(pathToFileURL(path.join(SHARED_WT, 'ampelSchreiben.ts')).href);
after(() => locale.set('de'));

const noop = () => {};
/** Eigene Vorlagen, wie der Reiter sie lädt (echter Lader, Auflösung mit echtem Python, #2988). */
const eigene = async (antwort: unknown, kind: string) => {
	const d = live();
	const daten: Record<string, unknown> = { '/api/metrics': d.metrics, '/api/templates': d.templates, '/api/metric-presets': antwort };
	return (await laden.ladeWetterDaten({ get: async (p: string) => daten[p], post: aufloesungPost() }, kind, {})).eigene;
};
const AMPEL = { template: 'wandern', metrics: { wind: { enabled: true } } };

const ENTITAETEN: Record<string, string> = { '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#39;': "'", '&nbsp;': ' ' };
const entschluesseln = (s: string) => s.replace(/&(amp|lt|gt|quot|#39|nbsp);/g, (m) => ENTITAETEN[m]);
const norm = (s: string) => s.replace(/\s+/g, ' ').trim();

/** Element (samt Inhalt) ab dem öffnenden Tag mit passendem data-testid. */
function elementMit(h: string, testid: string): string {
	const m = h.match(new RegExp(`<([a-z0-9]+)\\b[^>]*data-testid="${testid}"[^>]*>`));
	assert.ok(m && m.index !== undefined, `Element mit data-testid="${testid}" fehlt`);
	const zaehler = new RegExp(`<${m![1]}\\b[^>]*>|</${m![1]}>`, 'g');
	zaehler.lastIndex = m!.index! + m![0].length;
	let tiefe = 1;
	for (let x = zaehler.exec(h); x; x = zaehler.exec(h)) {
		tiefe += x[0].startsWith('</') ? -1 : 1;
		if (tiefe === 0) return h.slice(m!.index!, x.index + x[0].length);
	}
	throw new Error(`Element ${testid} nicht geschlossen`);
}
/** Text der Unterzeile (`<small>`) einer eigenen Vorlage im Menü. */
function unterzeile(h: string, id: string): string {
	const el = elementMit(h, `wetter-vorlage-eigene-${id}`);
	const m = el.match(/<small\b[^>]*>([\s\S]*?)<\/small>/);
	assert.ok(m, `keine Unterzeile an ${id}: ${el}`);
	return norm(entschluesseln(m![1].replace(/<[^>]+>/g, '')));
}

const PICKER = 'let pickerOffen = $state(false);';
const OFFEN: [string, string][] = [[PICKER, PICKER.replace('(false)', '(true)')]];
async function menue(sprache: 'de' | 'en', context: 'route' | 'vergleich', eigene: unknown[]): Promise<string> {
	locale.set(sprache);
	const k = (await import(pathToFileURL(path.join(WT, 'VorlageKarte.svelte')).href + `?start=${encodeURIComponent(JSON.stringify(OFFEN))}`)).default;
	const props = {
		context, vorlageId: 'wandern', liste: [{ id: 'wandern', label: 'Wandern', anzahl: 1, stichworte: ['wind'] }], eigene, abweichungen: 0,
		metrikName: (id: string) => id, aboAmpel: {}, onUebernehmen: noop, onEigene: noop, onZuruecksetzen: noop, onGespeichert: noop,
	};
	return render(k, { props }).body.replace(/<!--[\s\S]*?-->/g, '');
}

// ---------------------------------------------------------------------------------------------------------------
// AC-1 / AC-5: POST-Body des Dialogs
// ---------------------------------------------------------------------------------------------------------------
describe('#3189 AC-1/AC-5: eigeneVorlagePayload schreibt herkunft nur mit Namen', () => {
	for (const kind of ['route', 'vergleich'] as const) {
		test(`AC-1 (${kind}): herkunft {id, name} steht im Body`, () => {
			const body = schreiben.eigeneVorlagePayload({ name: 'Mallorca Frühling', beschreibung: '', alsStandard: false, kind, ampel: AMPEL, herkunft: { id: 'gr221', name: 'GR221' } });
			assert.deepEqual(body.herkunft, { id: 'gr221', name: 'GR221' }, `herkunft fehlt im POST-Body: ${JSON.stringify(body)}`);
			assert.equal(body.kind, kind);
		});
	}
	test('AC-5: leerer Name (nur Leerraum) -> kein herkunft-Feld', () => {
		const body = schreiben.eigeneVorlagePayload({ name: 'X', beschreibung: '', alsStandard: false, kind: 'route', ampel: AMPEL, herkunft: { id: 'gr221', name: '   ' } });
		assert.equal('herkunft' in body, false, JSON.stringify(body));
	});
	test('AC-5: ohne herkunft (Anlege-Modus) -> kein herkunft-Feld', () => {
		const body = schreiben.eigeneVorlagePayload({ name: 'X', beschreibung: '', alsStandard: false, kind: 'route', ampel: AMPEL });
		assert.equal('herkunft' in body, false, JSON.stringify(body));
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-5 / Implementation Details 7: Herkunftsableitung im Hub (Trip und Orts-Vergleich, derselbe Code)
// ---------------------------------------------------------------------------------------------------------------
describe('#3189 AC-5: vorlageHerkunft — aus Trip bzw. Orts-Vergleich, nie im Anlege-Modus', () => {
	test('AC-1 Trip: {id, name} des Trips', () => {
		assert.equal(typeof laden.vorlageHerkunft, 'function', 'wetterTabLaden.vorlageHerkunft fehlt');
		assert.deepEqual(laden.vorlageHerkunft({ id: 'gr221', name: 'GR221' }, false), { id: 'gr221', name: 'GR221' });
	});
	test('AC-1 Orts-Vergleich: {id, name} des Vergleichs', () => {
		assert.equal(typeof laden.vorlageHerkunft, 'function', 'wetterTabLaden.vorlageHerkunft fehlt');
		assert.deepEqual(laden.vorlageHerkunft({ id: 'cmp-1', name: 'Mallorca Nord', location_ids: ['a'] }, false), { id: 'cmp-1', name: 'Mallorca Nord' });
	});
	test('AC-5: Anlege-Modus liefert keine Herkunft, auch mit Name', () => {
		assert.equal(typeof laden.vorlageHerkunft, 'function', 'wetterTabLaden.vorlageHerkunft fehlt');
		assert.equal(laden.vorlageHerkunft({ id: 'gr221', name: 'GR221' }, true), undefined);
	});
	test('AC-5: ohne Name bzw. ohne Abo keine Herkunft', () => {
		assert.equal(typeof laden.vorlageHerkunft, 'function', 'wetterTabLaden.vorlageHerkunft fehlt');
		assert.equal(laden.vorlageHerkunft({ id: 'gr221', name: '  ' }, false), undefined);
		assert.equal(laden.vorlageHerkunft({ id: 'gr221' }, false), undefined);
		assert.equal(laden.vorlageHerkunft(undefined, false), undefined);
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-1: Abbildung MetricPreset -> EigeneVorlage (Laden UND frisch gespeichert über die POST-Antwort)
// ---------------------------------------------------------------------------------------------------------------
describe('#3189 AC-1: eigeneVorlageAus übernimmt den Herkunftsnamen', () => {
	test('mit herkunft: herkunftName gesetzt', () => {
		const e = laden.eigeneVorlageAus({ id: 'n1', name: 'Neu', kind: 'route', metrics: [], herkunft: { id: 'gr221', name: 'GR221' } }, AMPEL);
		assert.equal(e.herkunftName, 'GR221', JSON.stringify(e));
	});
	test('ohne herkunft: kein herkunftName-Feld', () => {
		const e = laden.eigeneVorlageAus({ id: 'n2', name: 'Neu', kind: 'route', metrics: [] }, AMPEL);
		assert.equal('herkunftName' in e, false, JSON.stringify(e));
	});
	test('geladene Liste trägt den Herkunftsnamen je Vorlage', async () => {
		const l = await eigene({ presets: [{ id: 'v1', name: 'V', kind: 'vergleich', metrics: [], herkunft: { id: 'c1', name: 'Mallorca Nord' } }] }, 'vergleich');
		assert.equal(l.length, 1);
		assert.equal(l[0].herkunftName, 'Mallorca Nord', JSON.stringify(l[0]));
	});
});

// ---------------------------------------------------------------------------------------------------------------
// AC-4 / AC-5: Unterzeile im Vorlagen-Menü — Beschreibung > Herkunft > nur „eigene“, DE und EN, beide Kontexte
// ---------------------------------------------------------------------------------------------------------------
const ANTWORT = (kind: string) => ({
	presets: [
		{ id: 'mitbeschr', name: 'Mit Beschreibung', kind, description: 'für den Frühling', metrics: [], herkunft: { id: 'gr221', name: 'GR221' } },
		{ id: 'mitherk', name: 'Mallorca Frühling', kind, metrics: [], herkunft: { id: 'gr221', name: 'GR221' } },
		{ id: 'ohne', name: 'Ohne alles', kind, metrics: [] },
	],
});
const ERWARTET = {
	de: { mitbeschr: 'eigene · für den Frühling', mitherk: 'eigene · aus GR221 gespeichert', ohne: 'eigene' },
	en: { mitbeschr: 'own · für den Frühling', mitherk: 'own · saved from GR221', ohne: 'own' },
} as const;

describe('#3189 AC-4: Unterzeile eigener Vorlagen nach Priorität', () => {
	for (const sprache of ['de', 'en'] as const) {
		for (const context of ['route', 'vergleich'] as const) {
			test(`${sprache}, ${context}: Beschreibung vor Herkunft vor nur „${ERWARTET[sprache].ohne}“`, async () => {
				const h = await menue(sprache, context, await eigene(ANTWORT(context), context));
				for (const id of ['mitbeschr', 'mitherk', 'ohne'] as const) {
					assert.equal(unterzeile(h, id), ERWARTET[sprache][id], `${sprache}/${context}/${id}`);
				}
			});
		}
	}
	test('AC-1/AC-4: frisch gespeicherte Vorlage (POST-Antwort) zeigt die Herkunft ohne Neuladen', async () => {
		const neu = laden.eigeneVorlageAus({ id: 'frisch', name: 'Neu', kind: 'route', metrics: [], herkunft: { id: 'gr221', name: 'GR221' } }, AMPEL);
		const h = await menue('de', 'route', [neu]);
		assert.equal(unterzeile(h, 'frisch'), 'eigene · aus GR221 gespeichert');
	});
	test('AC-4: Name ist Nutzertext und wird nie übersetzt (EN behält „Mallorca Frühling“)', async () => {
		const e = laden.eigeneVorlageAus({ id: 'u', name: 'X', kind: 'route', metrics: [], herkunft: { id: 't', name: 'Mallorca Frühling' } }, AMPEL);
		const h = await menue('en', 'route', [e]);
		assert.equal(unterzeile(h, 'u'), 'own · saved from Mallorca Frühling');
	});
});
