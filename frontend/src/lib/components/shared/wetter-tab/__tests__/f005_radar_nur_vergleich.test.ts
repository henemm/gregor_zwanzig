// Fix-Loop 1 Issue #2794 S3a Teil-PR 3, Adversary-Finding F005 (AC-21):
// Nur das Orts-Briefing zeigt den Schalter „Radar-Regen", und Speichern setzt
// `radar_alert_enabled`; der Trip zeigt ihn nicht und schreibt kein
// `radar_alert_enabled`.
//
// Gemessen dort, wo es WIRKT:
//   - Gesendeter Rumpf: der echte Vergleichs-Speicher-Baustein `vergleichNutzlast`
//     mit eingeschaltetem Radar (der Leerwert `false` bewacht kein Setzen auf `true`),
//     und der Trip-Baustein `tripNutzlast` (beide PUT-Teile) ohne Radar-Feld.
//   - Sichtbarkeit: die ECHTE `mitRadar`-Herleitung der Einbettung
//     `<WarnungenRadarKarte>` in WetterTab.svelte, ausgewertet gegen das Instanz-Skript
//     (svelteInstanzPruefstand.ts) je Kontext, und das serverseitige Rendern der
//     echten Karte (svelte/server): ohne `mitRadar` kein `wetter-radar-schalter`.
//
//   cd frontend && npm test -- src/lib/components/shared/wetter-tab/__tests__/f005_radar_nur_vergleich.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { live } from './wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../wetterTabSpeicherung.ts';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	werte
} from '../../__tests__/svelteInstanzPruefstand.ts';
import { svelteAst } from '../../__tests__/s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../../../../..');
const WETTER_TAB = join(HIER, '..', 'WetterTab.svelte');

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const vorlagen = () => vorlagenAusTemplates(live().templates);

const VERGLEICH: AboSicht = {
	id: 'cp-f005',
	radar_alert_enabled: false,
	display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] }
};
const TRIP: AboSicht = {
	id: 'trip-f005',
	report_config: { day_window_start_hour: 5, day_window_end_hour: 18 },
	display_config: { metrics: [{ metric_id: 'wind', enabled: true }] }
};

/** Alle Schluessel eines Objekts rekursiv (fuer „kommt nirgends vor"). */
function alleSchluessel(x: unknown, aus: string[] = []): string[] {
	if (x && typeof x === 'object') {
		for (const [k, v] of Object.entries(x as Record<string, unknown>)) {
			aus.push(k);
			alleSchluessel(v, aus);
		}
	}
	return aus;
}

describe('F005/AC-21: Radar-Regen speichern (nur Orts-Briefing)', () => {
	test('Orts-Briefing: Radar eingeschaltet ⇒ der gesendete Rumpf traegt radar_alert_enabled = true', () => {
		const v = vorlagen();
		const stand = { ...standAusAbo('vergleich', VERGLEICH, v), radarAn: true };
		const n = vergleichNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => VERGLEICH });
		assert.equal(n.radar_alert_enabled, true, 'Radar-Schalter an wird nicht gespeichert');
	});

	test('Orts-Briefing: Radar ausgeschaltet ⇒ false (Gegenprobe)', () => {
		const v = vorlagen();
		const abo = { ...VERGLEICH, radar_alert_enabled: true };
		const stand = { ...standAusAbo('vergleich', abo, v), radarAn: false };
		const n = vergleichNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => abo });
		assert.equal(n.radar_alert_enabled, false);
	});

	test('Trip: keiner der beiden PUT-Teile schreibt radar_alert_enabled, auch bei radarAn im Stand', () => {
		const v = vorlagen();
		const stand = { ...standAusAbo('route', TRIP, v), radarAn: true };
		const n = tripNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => TRIP });
		assert.ok(!alleSchluessel(n).includes('radar_alert_enabled'), `Trip schreibt Radar: ${JSON.stringify(n)}`);
	});
});

// Fix-Loop 2, F-A2: die Radar-Kette an Lesestelle und Aenderungs-Erkennung.
describe('F-A2/AC-21: Radar lesen und Umlegen als Aenderung erkennen', () => {
	test('standAusAbo: radar_alert_enabled true ⇒ an; false oder fehlend ⇒ aus', () => {
		const v = vorlagen();
		assert.equal(standAusAbo('vergleich', { ...VERGLEICH, radar_alert_enabled: true }, v).radarAn, true, 'Abo mit Radar an oeffnet mit Radar aus');
		assert.equal(standAusAbo('vergleich', { ...VERGLEICH, radar_alert_enabled: false }, v).radarAn, false);
		const ohne = { ...VERGLEICH };
		delete ohne.radar_alert_enabled;
		assert.equal(standAusAbo('vergleich', ohne, v).radarAn, false);
	});

	test('WetterTab (Instanz-Skript): Umlegen des Radar-Schalters loest einen Speichervorgang aus', async () => {
		const berichte: unknown[] = [];
		const daten = live();
		const api = {
			get: async (p: string) => (p === '/api/metrics' ? daten.metrics : p === '/api/templates' ? daten.templates : [])
		};
		const { u } = await umgebungFuer(WETTER_TAB, {
			context: 'vergleich',
			preset: VERGLEICH,
			trip: undefined,
			createMode: true,
			saveController: undefined,
			enqueueHubWrite: undefined,
			onTripUpdate: undefined,
			onCompareUpdate: undefined,
			onAnlegeStand: (n: unknown) => berichte.push(n),
			api
		});
		await u.laden();
		assert.equal(u.phase, 'bereit', 'Messaufbau: WetterTab hat nicht geladen');
		assert.equal(berichte.length, 1, 'Messaufbau: erster Stand-Bericht fehlt');
		u.aendern({ ...u.stand, radarAn: true });
		assert.equal(berichte.length, 2, 'das Umlegen des Radar-Schalters wird nicht gespeichert');
		assert.equal((berichte[1] as { radar_alert_enabled: boolean }).radar_alert_enabled, true);
	});
});

describe('F005/AC-21: Radar-Schalter nur im Orts-Briefing sichtbar', () => {
	async function mitRadarFuer(context: 'route' | 'vergleich'): Promise<unknown> {
		const { u } = await umgebungFuer(WETTER_TAB, { context });
		const { ast, quelle } = svelteAst(WETTER_TAB);
		const karten = findeKomponenten(ast, 'WarnungenRadarKarte');
		assert.equal(karten.length, 1, 'Messaufbau: genau eine WarnungenRadarKarte im WetterTab erwartet');
		const ausdruck = attributAusdruck(karten[0], quelle, 'mitRadar');
		assert.ok(ausdruck, 'WarnungenRadarKarte ohne mitRadar-Prop');
		return werte(ausdruck!, u);
	}

	test('WetterTab (Trip): mitRadar ist false', async () => {
		assert.equal(await mitRadarFuer('route'), false, 'der Trip zeigt den Radar-Schalter');
	});

	test('WetterTab (Orts-Briefing): mitRadar ist true', async () => {
		assert.equal(await mitRadarFuer('vergleich'), true, 'das Orts-Briefing zeigt den Radar-Schalter nicht');
	});

	test('WarnungenRadarKarte rendert den Radar-Schalter genau bei mitRadar', async () => {
		const { render } = await import('svelte/server');
		const Karte = (await import(pathToFileURL(join(HIER, '..', 'WarnungenRadarKarte.svelte')).href)).default;
		const props = (mitRadar: boolean) => ({ warnungenAn: true, radarAn: false, mitRadar, onWarnungen: () => {}, onRadar: () => {} });
		const ohne = render(Karte, { props: props(false) }).body;
		const mit = render(Karte, { props: props(true) }).body;
		assert.ok(ohne.includes('data-testid="wetter-warnungen-schalter"'), 'Messaufbau: Karte rendert nicht');
		assert.ok(!ohne.includes('data-testid="wetter-radar-schalter"'), 'Radar-Schalter ohne mitRadar sichtbar');
		assert.ok(mit.includes('data-testid="wetter-radar-schalter"'), 'Radar-Schalter mit mitRadar fehlt');
	});
});
