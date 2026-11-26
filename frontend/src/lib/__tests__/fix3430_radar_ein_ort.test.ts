// Fix #3430: Radar-Regen-Hinweis im Reiter Wetter bei genau einem Ort „deinen Ort" statt „deine Orte".
// Spec: docs/specs/fast/fix-3430-radar-ein-ort.md (AC-1 bis AC-4), ADR-0124 Nr. 10.
//
// Gemessen dort, wo es WIRKT: alle Attribute der echten Einbettung <WarnungenRadarKarte> in
// WetterTabInhalt.svelte werden gegen das Instanz-Skript ausgewertet (svelteInstanzPruefstand.ts),
// die echte Karte damit serverseitig gerendert (svelte/server). Die Ortszahl kommt aus den
// `location_ids` des Abos — derselben Quelle wie die Vorlagen-Bestätigung (#3111).
//
//   cd frontend && npm test -- src/lib/__tests__/fix3430_radar_ein_ort.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { aufgeloestVon } from '../components/shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { standAusAbo, type AboSicht } from '../components/shared/wetter-tab/wetterZustand.ts';
import { umgebungFuer, findeKomponenten, attributAusdruck, attributNamen, werte } from '../components/shared/__tests__/svelteInstanzPruefstand.ts';
import { svelteAst } from '../components/shared/__tests__/s3a2794Ast.ts';
import { radarZiel } from '../components/organisms/wetter-tab/warnungenRadarZeilen.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../..');
const WT_DIR = join(FRONTEND, 'src', 'lib', 'components', 'organisms', 'wetter-tab');
const WETTER_TAB = join(WT_DIR, 'WetterTabInhalt.svelte');

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

const text = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();

const vergleich = (ids: string[] | undefined): AboSicht =>
	({
		id: 'cp-3430',
		radar_alert_enabled: true,
		...(ids ? { location_ids: ids } : {}),
		display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] }
	}) as AboSicht;
const TRIP: AboSicht = {
	id: 'trip-3430',
	report_config: { day_window_start_hour: 5, day_window_end_hour: 18 },
	display_config: { metrics: [{ metric_id: 'wind', enabled: true }] }
};

/** Rendert die echte Karte mit den Props, die WetterTabInhalt im Kontext tatsächlich übergibt. */
async function karteImReiter(context: 'route' | 'vergleich', abo: AboSicht, sprache: 'de' | 'en'): Promise<string> {
	locale.set(sprache);
	try {
		const { u } = await umgebungFuer(WETTER_TAB, {
			context,
			trip: context === 'route' ? abo : undefined,
			preset: context === 'vergleich' ? abo : undefined
		});
		u.stand = standAusAbo(context, abo, aufgeloestVon(abo));
		const { ast, quelle } = svelteAst(WETTER_TAB);
		const karten = findeKomponenten(ast, 'WarnungenRadarKarte');
		assert.equal(karten.length, 1, 'Messaufbau: genau eine WarnungenRadarKarte im WetterTab erwartet');
		const props: Record<string, unknown> = {};
		for (const name of attributNamen(karten[0]))
			props[name] = name.startsWith('on') ? () => {} : werte(attributAusdruck(karten[0], quelle, name)!, u);
		const Karte = (await import(pathToFileURL(join(WT_DIR, 'WarnungenRadarKarte.svelte')).href)).default;
		return text(render(Karte, { props }).body);
	} finally {
		locale.set('de');
	}
}

describe('reine Auswahl radarZiel(kontext, ortAnzahl)', () => {
	test('AC-4: Trip bleibt „deine Etappe", unabhängig von einer Ortszahl', () => {
		assert.equal(radarZiel('route', 1), 'wetter.radar.deine_etappe');
		assert.equal(radarZiel('route', undefined), 'wetter.radar.deine_etappe');
		assert.equal(radarZiel('route', 3), 'wetter.radar.deine_etappe');
	});
	test('AC-1/AC-2: Orte mit genau einem Ort ⇒ „deinen Ort"', () => {
		assert.equal(radarZiel('vergleich', 1), 'wetter.radar.dein_ort');
	});
	test('AC-3: Orte mit 0, ≥ 2 oder unbekannter Ortszahl ⇒ „deine Orte"', () => {
		for (const n of [0, 2, 3, undefined]) assert.equal(radarZiel('vergleich', n), 'wetter.radar.deine_orte', `ortAnzahl=${n}`);
	});
});

describe('echte Einbettung im Reiter Wetter (Kontext Orte)', () => {
	test('AC-1: ein Ort (DE) ⇒ „… Regen auf deinen Ort zukommt", nicht „deine Orte"', async () => {
		const t = await karteImReiter('vergleich', vergleich(['a']), 'de');
		assert.ok(t.includes('Alarm, wenn in der nächsten Stunde Regen auf deinen Ort zukommt'), `AC-1: Text fehlt in: ${t}`);
		assert.ok(!t.includes('deine Orte'), `AC-1: „deine Orte" erscheint bei einem Ort: ${t}`);
	});
	test('AC-2: ein Ort (EN) ⇒ „… towards your location within …", nicht „your locations"', async () => {
		const t = await karteImReiter('vergleich', vergleich(['a']), 'en');
		assert.ok(t.includes('Alert when rain is coming towards your location within the next hour'), `AC-2: Text fehlt in: ${t}`);
		assert.ok(!t.includes('your locations'), `AC-2: „your locations" erscheint bei einem Ort: ${t}`);
	});
	test('AC-3: drei Orte bleiben bei „deine Orte" / „your locations"', async () => {
		assert.ok((await karteImReiter('vergleich', vergleich(['a', 'b', 'c']), 'de')).includes('Regen auf deine Orte zukommt'));
		assert.ok((await karteImReiter('vergleich', vergleich(['a', 'b', 'c']), 'en')).includes('towards your locations within'));
	});
	test('AC-3: unbekannte Ortszahl (ohne location_ids) bleibt bei „deine Orte"', async () => {
		assert.ok((await karteImReiter('vergleich', vergleich(undefined), 'de')).includes('Regen auf deine Orte zukommt'));
	});
	test('AC-4: Trip bleibt bei „deine Etappe" / „your stage"', async () => {
		const de = await karteImReiter('route', TRIP, 'de');
		assert.ok(de.includes('Regen auf deine Etappe zukommt'), de);
		assert.ok((await karteImReiter('route', TRIP, 'en')).includes('towards your stage within'));
	});
});
