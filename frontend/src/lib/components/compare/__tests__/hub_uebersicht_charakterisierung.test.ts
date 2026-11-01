// Charakterisierung — Issue #2682 (Epic #2345), Schritt 1, AC-3 / AC-13.
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md
//
// ZWECK: haelt die Vergleichs-Uebersicht (Reiter „Uebersicht" in
// CompareTabs.svelte, Wrapper data-testid="compare-detail-panel-uebersicht")
// als normalisiertes SSR-HTML gegen den IST-STAND fest. Muss VOR und NACH dem
// Umzug nach shared/hub-uebersicht/HubUebersicht.svelte gruen sein. Diese Datei
// bleibt beim Umzug UNVERAENDERT: gerendert wird CompareTabs (das den neuen
// Baustein dann einbindet), nicht der Baustein selbst.
//
// Golden: __tests__/fixtures/hub_uebersicht_charakterisierung.json, einmalig
// am Ist-Stand (Commit 2d497619d) aufgenommen. Die Datei wird NIE aus diesem
// Test heraus neu geschrieben — eine Abweichung ist ein Befund, keine
// Aufforderung zum Neuaufnehmen.
//
// Normalisierung (alles, was ein verhaltensgleicher Umzug legitim aendert):
//   - Svelte-Hydrations-Marker <!--[…-->, <!--]-->, <!---->  (Anzahl/Position
//     haengt an Komponenten-Grenzen),
//   - gescopte CSS-Klassen „svelte-xxxx" (der Hash aendert sich, wenn das CSS
//     .hub-mobile-*/.hub-summary-* in eine andere Datei zieht),
//   - Leerraum zwischen Tags und Leerraum-Laeufe,
//   - der INHALT von <div data-testid="briefing-history" data-kind="…"> wird durch
//     einen Platzhalter mit seinem data-kind ersetzt: das ist kein umziehendes
//     Markup, sondern der bereits geteilte Baustein BriefingHistory. Er bekommt in
//     Phase 6 den Lader des Bausteins (Spec Entscheidung 3) und darf im SSR dann
//     den Ladezustand statt eines vorweggenommenen Leerzustands zeigen (AC-7).
//     Position und data-kind bleiben im Golden festgehalten.
// NICHT normalisiert: Elemente, Reihenfolge, Texte, data-testid, Inline-Styles.
// Folge fuer Phase 6: der Vergleichs-Zweig des Bausteins muss dasselbe Markup
// erzeugen — Trip-eigene testids (hub-uebersicht-*) duerfen im Vergleich NICHT
// zusaetzlich auftauchen.
//
// EINZIGE bewusste Abweichung (Spec Entscheidung 5 / AC-4): bei NICHT
// aufloesbaren Orten nennt die Desktop-Karte kuenftig die Zahl der aufloesbaren
// Orte. Damit die Charakterisierung davon unberuehrt bleibt, sind in ALLEN
// Fixtures ALLE location_ids aufloesbar (Zahl gleich unter alter und neuer Regel).
// AC-4 selbst prueft shared/hub-uebersicht/__tests__/hub_uebersicht_modell.test.ts.
//
// MOBIL: `isMobileViewport` setzt CompareTabs erst im Browser per matchMedia
// (onMount). Im SSR (svelte/server) laeuft kein onMount — gerendert wird nur der
// Desktop-Zweig. Bewusst KEINE Produktaenderung, um Mobil zu erzwingen. Der
// mobile Zweig (Chevron-Stack hub-summary-row-mobile, AC-7 der S8c-Spec;
// Status-Kurzform „Laeuft autom.", AC-8) bleibt durch das E2E
// frontend/e2e/compare-hub-fidelity-s8c.spec.ts charakterisiert.
//
// Deterministisch: feste Prozess-Zone (formatLastSent nutzt
// toLocaleDateString), kein „jetzt" im Desktop-Zweig (Naechster Versand ist im
// SSR „—", weil der Lader erst im $effect laedt).
//
// Pfadregel #1409: alles relativ zu DIESER Datei.
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test \
//     src/lib/components/compare/__tests__/hub_uebersicht_charakterisierung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

process.env.TZ = 'Europe/Berlin';

const HIER = dirname(fileURLToPath(import.meta.url));
// __tests__ -> compare -> components -> lib -> src -> frontend
const FRONTEND = resolve(HIER, '..', '..', '..', '..', '..');
const basis = pathToFileURL(FRONTEND + '/').href;
const HUB = join(HIER, '..', 'CompareTabs.svelte');
const GOLDEN_DATEI = join(HIER, 'fixtures', 'hub_uebersicht_charakterisierung.json');

register(pathToFileURL(join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, basis);
register(pathToFileURL(join(FRONTEND, 'src/lib/components/shared/__tests__/svelteTsModulHook.mjs')).href, basis);

const { render } = await import('svelte/server');
const CompareTabs = (await import(pathToFileURL(HUB).href)).default;

// ── Fixtures (alle location_ids aufloesbar, s. Kopf) ─────────────────────────

const ORTE = [
	{ id: 'l1', name: 'Alpha' },
	{ id: 'l2', name: 'Beta' },
	{ id: 'l3', name: 'Gamma' },
	{ id: 'l4', name: 'Delta' }
];

const BASIS = {
	id: 'cp-2682',
	name: 'Testvergleich',
	location_ids: ['l1', 'l2', 'l3', 'l4'],
	schedule: 'daily',
	profil: 'wandern',
	hour_from: 6,
	hour_to: 18,
	empfaenger: [],
	forecast_hours: 48,
	created_at: '2026-10-01T00:00:00Z',
	display_config: { ideal_ranges: { temp_max_c: { min: 10, max: 20 }, wind_max_kmh: { min: 0, max: 30 } } }
};

const FAELLE: Record<string, Record<string, unknown>> = {
	/** Aktiv, drei Kanaele, beide Slots, letzter Versand gesetzt, >3 Orte. */
	aktiv: {
		...BASIS,
		letzter_versand: '2026-10-28T10:00:00Z',
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '18:30:00',
		send_telegram: true,
		send_premium_sms: true
	},
	/** Entwurf: leerer Name ⇒ deriveStatusFromPreset = draft, Orte bleiben aufloesbar. */
	entwurf: {
		...BASIS,
		name: '',
		location_ids: ['l1', 'l2'],
		morning_enabled: true,
		morning_time: '06:00:00'
	},
	/** Pausiert, kein letzter Versand, nur E-Mail, kein Slot. */
	pausiert: {
		...BASIS,
		schedule: 'manual',
		paused_at: '2026-10-20T08:00:00Z',
		location_ids: ['l3']
	}
};

// ── Hilfen ───────────────────────────────────────────────────────────────────

/** Normalisierung, s. Kopf. Exportiert NICHT — die Regel steht nur hier. */
function normalisiere(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, '')
		.replace(/\s*\bsvelte-[a-z0-9]+\b/g, '')
		.replace(/>\s+</g, '><')
		.replace(/\s+/g, ' ')
		.trim();
}

/** [Anfang, Ende) des <div …>…</div>, das bei `start` beginnt (Tiefe ueber div-Tags). */
function divBereich(html: string, start: number, was: string): [number, number] {
	const tag = /<(\/?)div\b[^>]*>/g;
	tag.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = tag.exec(html))) {
		tiefe += m[1] === '/' ? -1 : 1;
		if (tiefe === 0) return [start, m.index + m[0].length];
	}
	assert.fail(`Messaufbau: ${was} ist nicht geschlossen`);
}

/** Das <div data-testid="compare-detail-panel-uebersicht">…</div> samt Inhalt. */
function panelUebersicht(html: string): string {
	const start = html.indexOf('<div data-testid="compare-detail-panel-uebersicht">');
	assert.notEqual(start, -1, 'Messaufbau: Wrapper compare-detail-panel-uebersicht fehlt im SSR-HTML');
	const [a, b] = divBereich(html, start, 'Wrapper compare-detail-panel-uebersicht');
	return html.slice(a, b);
}

/** Ersetzt den Inhalt von BriefingHistory durch einen Platzhalter mit data-kind (s. Kopf). */
function ohneHistorienInhalt(panel: string): string {
	const m = /<div data-testid="briefing-history" data-kind="([a-z]+)">/.exec(panel);
	assert.ok(m, 'Messaufbau: BriefingHistory (data-testid="briefing-history") fehlt in der Uebersicht');
	const [a, b] = divBereich(panel, m!.index, 'BriefingHistory');
	return `${panel.slice(0, a)}<div data-testid="briefing-history" data-kind="${m![1]}">[Versand-Historie]</div>${panel.slice(b)}`;
}

function uebersicht(fall: string): string {
	const html = render(CompareTabs, { props: { preset: FAELLE[fall], locations: ORTE } }).body;
	return normalisiere(ohneHistorienInhalt(panelUebersicht(html)));
}

const reinerText = (html: string) => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

const GOLDEN = JSON.parse(readFileSync(GOLDEN_DATEI, 'utf-8')) as Record<string, string>;

// ── Golden ───────────────────────────────────────────────────────────────────

describe('AC-3: Vergleichs-Uebersicht (Desktop, SSR) ist gleich dem festgehaltenen Ist-Stand', () => {
	for (const fall of Object.keys(FAELLE)) {
		test(`Fall „${fall}": normalisiertes HTML byte-gleich zum Golden`, () => {
			assert.ok(GOLDEN[fall], `Golden fuer „${fall}" fehlt in ${GOLDEN_DATEI}`);
			assert.equal(uebersicht(fall), GOLDEN[fall]);
		});
	}

	test('das Golden enthaelt genau die drei Faelle (kein stilles Weglassen)', () => {
		assert.deepEqual(Object.keys(GOLDEN).sort(), Object.keys(FAELLE).sort());
	});
});

// ── Sinn-Anker: auch ein falsch aufgenommenes Golden prueft diese Texte ──────

describe('AC-3/AC-13: tragende Texte und Kennungen der Uebersicht', () => {
	test('aktiv: Langform „Läuft automatisch", Briefings, Zuletzt raus, Kanaele, 4 Kandidaten, Versand-Karte', () => {
		const html = uebersicht('aktiv');
		const t = reinerText(html);
		assert.ok(t.includes('Läuft automatisch'), t);
		assert.ok(!t.includes('Läuft autom.'), 'Desktop-SSR darf die mobile Kurzform nicht zeigen');
		assert.ok(t.includes('Nächster Versand —'), `nicht geladen ⇒ „—": ${t}`);
		assert.ok(t.includes('Morgen 07:00 · Abend 18:30'), t);
		assert.ok(t.includes('Zuletzt raus 28.10.2026'), t);
		assert.ok(t.includes('Email · Telegram · Premium-SMS'), t);
		assert.ok(t.includes('4 Kandidaten'), t);
		assert.ok(t.includes('Alpha · Beta · Gamma +1 weitere'), t);
		assert.ok(html.includes('data-testid="compare-detail-stat-briefings"'));
		assert.ok(html.includes('data-testid="compare-detail-stat-kanaele"'));
		assert.equal(html.split('data-testid="compare-hub-versand-edit"').length - 1, 1);
		assert.ok(html.includes('data-testid="briefing-history" data-kind="vergleich"'));
	});

	test('entwurf: „Entwurf · nicht aktiv" und Versand-Karte „Noch nicht geplant"', () => {
		const t = reinerText(uebersicht('entwurf'));
		assert.ok(t.includes('Entwurf · nicht aktiv'), t);
		assert.ok(t.includes('Noch nicht geplant'), t);
		assert.ok(t.includes('Briefing-Uhrzeiten unter Wetter-Metriken im Abschnitt Versand festlegen.'), t);
		assert.ok(t.includes('2 Kandidaten'), t);
	});

	test('pausiert: „Pausiert", „Noch kein Versand", Briefings „—", nur Email', () => {
		const t = reinerText(uebersicht('pausiert'));
		assert.ok(t.includes('Status Pausiert'), t);
		assert.ok(t.includes('Zuletzt raus Noch kein Versand'), t);
		assert.ok(t.includes('Briefings —'), t);
		assert.ok(t.includes('Kanäle Email'), t);
		assert.ok(t.includes('1 Kandidaten'), t);
	});
});
