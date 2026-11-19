// TDD RED — Issue #2800 (Epic #2791, Scheibe S8): Radar-Regen-Schalter auch im Trip.
// Spec: docs/specs/modules/feat_2800_trip_radar_alarm.md — AC-4 (Default), AC-6 (Reiter Wetter).
// Löst die Trip-Seite von feat_2794 AC-21 und feat_2913 AC-3 ab („Radar nur im Orts-Briefing").
//
// Gemessen dort, wo es WIRKT:
//   - Sichtbarkeit und Text: ALLE Attribute der echten Einbettung <WarnungenRadarKarte> in
//     WetterTabInhalt.svelte werden im Trip-Kontext gegen das Instanz-Skript ausgewertet
//     (svelteInstanzPruefstand.ts) und die echte Karte damit serverseitig gerendert (svelte/server).
//     Der erwartete Wortlaut kommt aus der Elementliste des Mockups (Trip-Element
//     wetter.radar.beschreibung, „… auf deine Etappe zukommt") bzw. deren EN-Muster mit „your stage".
//     Kein Prop-Name ist vorgeschrieben: wie der Trip-Text gewählt wird, entscheidet die Umsetzung.
//   - Lesen: standAusAbo('route', …) — Bestandstrip ohne Feld liest als AN (None = an), Vergleich
//     ohne Feld bleibt AUS (dokumentierte Default-Asymmetrie).
//   - Schreiben: die echte Anlege-/Speicher-Nutzlast des Reiters (onAnlegeStand ⇒ tripNutzlast) —
//     Trip-PUT-Rumpf (`tripFelder`, geht an PUT /api/trips/{id}) trägt radar_alert_enabled.
//
//   cd frontend && npm test -- src/lib/__tests__/feat2800_trip_radar_wetter.test.ts

import { test, describe, after } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { live } from '../components/shared/wetter-tab/__tests__/wetterTabDaten.ts';
import { vorlagenAusTemplates } from '../components/shared/wetter-tab/ampelModell.ts';
import { standAusAbo, type AboSicht } from '../components/shared/wetter-tab/wetterZustand.ts';
import { tripNutzlast, vergleichNutzlast } from '../components/shared/wetter-tab/wetterTabSpeicherung.ts';
import {
	umgebungFuer,
	findeKomponenten,
	attributAusdruck,
	attributNamen,
	werte
} from '../components/shared/__tests__/svelteInstanzPruefstand.ts';
import { svelteAst } from '../components/shared/__tests__/s3a2794Ast.ts';

const HIER = dirname(fileURLToPath(import.meta.url));
const FRONTEND = resolve(HIER, '../../..');
const REPO = resolve(FRONTEND, '..');
const WT_DIR = join(FRONTEND, 'src', 'lib', 'components', 'organisms', 'wetter-tab');
const WETTER_TAB = join(WT_DIR, 'WetterTabInhalt.svelte');

register(pathToFileURL(join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
const { locale } = await import(pathToFileURL(join(FRONTEND, 'src/lib/i18n/index.ts')).href);
after(() => locale.set('de'));

const vorlagen = () => vorlagenAusTemplates(live().templates);

// Soll-Wortlaut aus der Elementliste (Mockup), nicht aus der Implementierung abgeschrieben.
type ListenEl = { ctx: string; reiter: string; abschnitt: string; i18n_key: string | null; text_de: string; text_en: string | null };
const ELEMENTE = (JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8')) as { elemente: ListenEl[] }).elemente;
const tripRadarText = ELEMENTE.find(
	(e) => e.ctx === 'trip' && e.reiter === 'wetter' && e.abschnitt === 'warnungen-radar' && e.i18n_key === 'wetter.radar.beschreibung'
);
assert.ok(tripRadarText, 'Messaufbau: Elementliste ohne Trip-Radar-Beschreibung');
const SOLL_DE = tripRadarText!.text_de; // „Alarm, wenn in der nächsten Stunde Regen auf deine Etappe zukommt"
const SOLL_EN = (tripRadarText!.text_en ?? '').replace('{orte}', 'your stage');
assert.match(SOLL_DE, /deine Etappe/, 'Messaufbau: Trip-Soll nennt nicht „deine Etappe"');

const TRIP: AboSicht = {
	id: 'trip-2800',
	report_config: { day_window_start_hour: 5, day_window_end_hour: 18 },
	display_config: { metrics: [{ metric_id: 'wind', enabled: true }] }
};
const VERGLEICH: AboSicht = {
	id: 'cp-2800',
	display_config: { active_metrics: [{ metric_id: 'wind', aggregation: 'max' }] }
};

const text = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
const tagMitTestid = (h: string, id: string) => h.match(new RegExp(`<[a-z]+\\b[^>]*data-testid="${id}"[^>]*>`))?.[0] ?? null;

/** Rendert die echte Karte mit den Props, die WetterTabInhalt im Kontext tatsächlich übergibt. */
async function karteImReiter(context: 'route' | 'vergleich', abo: AboSicht): Promise<string> {
	const { u } = await umgebungFuer(WETTER_TAB, {
		context,
		trip: context === 'route' ? abo : undefined,
		preset: context === 'vergleich' ? abo : undefined
	});
	u.stand = standAusAbo(context, abo, vorlagen());
	const { ast, quelle } = svelteAst(WETTER_TAB);
	const karten = findeKomponenten(ast, 'WarnungenRadarKarte');
	assert.equal(karten.length, 1, 'Messaufbau: genau eine WarnungenRadarKarte im WetterTab erwartet');
	const props: Record<string, unknown> = {};
	// Handler (`on…`) werden beim Rendern nicht gerufen und tragen TS-Syntax (`stand!`) — Attrappe.
	for (const name of attributNamen(karten[0]))
		props[name] = name.startsWith('on') ? () => {} : werte(attributAusdruck(karten[0], quelle, name)!, u);
	const Karte = (await import(pathToFileURL(join(WT_DIR, 'WarnungenRadarKarte.svelte')).href)).default;
	return render(Karte, { props }).body;
}

describe('AC-6: Trip-Reiter Wetter zeigt die Radar-Zeile mit „deine Etappe"', () => {
	test('Trip (DE): Radar-Schalter sichtbar, Text „… auf deine Etappe zukommt"', async () => {
		locale.set('de');
		const h = await karteImReiter('route', TRIP);
		assert.ok(tagMitTestid(h, 'wetter-warnungen-schalter'), 'Messaufbau: Karte rendert nicht');
		assert.ok(tagMitTestid(h, 'wetter-radar-schalter'), 'AC-6: der Trip zeigt keinen Radar-Schalter');
		assert.ok(text(h).includes(SOLL_DE), `AC-6: Trip-Text „${SOLL_DE}" fehlt in: ${text(h)}`);
		assert.ok(!text(h).includes('deine Orte'), 'Trip spricht von „deine Orte" statt „deine Etappe"');
	});

	test('Trip (EN): Text „… towards your stage …"', async () => {
		locale.set('en');
		try {
			const h = await karteImReiter('route', TRIP);
			assert.ok(tagMitTestid(h, 'wetter-radar-schalter'), 'AC-6: der Trip zeigt keinen Radar-Schalter (EN)');
			assert.ok(text(h).includes(SOLL_EN), `AC-6: EN-Trip-Text „${SOLL_EN}" fehlt in: ${text(h)}`);
		} finally {
			locale.set('de');
		}
	});

	test('Orts-Briefing bleibt bei „deine Orte" (Gegenprobe, keine Verwechslung der Kontexte)', async () => {
		locale.set('de');
		const h = await karteImReiter('vergleich', { ...VERGLEICH, radar_alert_enabled: true });
		assert.ok(tagMitTestid(h, 'wetter-radar-schalter'));
		assert.ok(text(h).includes('Regen auf deine Orte zukommt'), `Vergleich-Text verändert: ${text(h)}`);
		assert.ok(!text(h).includes('deine Etappe'));
	});

	test('Trip-Bestand ohne Feld: Radar-Schalter steht auf an (aria-checked="true")', async () => {
		locale.set('de');
		const tag = tagMitTestid(await karteImReiter('route', TRIP), 'wetter-radar-schalter');
		assert.ok(tag, 'AC-6: der Trip zeigt keinen Radar-Schalter');
		assert.match(tag!, /aria-checked="true"/, 'AC-4/AC-6: Bestandstrip ohne Feld erscheint nicht als an');
	});
});

describe('AC-4: Lesen — Trip None = an, Vergleich None = aus', () => {
	test('Trip: fehlendes Feld ⇒ an; true ⇒ an; false ⇒ aus', () => {
		const v = vorlagen();
		assert.equal(standAusAbo('route', TRIP, v).radarAn, true, 'Bestandstrip ohne Feld liest als aus (stilles Verstummen)');
		assert.equal(standAusAbo('route', { ...TRIP, radar_alert_enabled: true }, v).radarAn, true);
		assert.equal(standAusAbo('route', { ...TRIP, radar_alert_enabled: false }, v).radarAn, false);
	});

	test('Vergleich: fehlendes Feld bleibt aus (Gegenprobe), auch im gesendeten Rumpf', () => {
		const v = vorlagen();
		const stand = standAusAbo('vergleich', VERGLEICH, v);
		assert.equal(stand.radarAn, false);
		const n = vergleichNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => VERGLEICH });
		assert.equal(n.radar_alert_enabled, false);
	});
});

describe('AC-6: Schreiben — Trip-PUT-Rumpf trägt radar_alert_enabled', () => {
	test('tripNutzlast: Stand an ⇒ true, Stand aus ⇒ false (im Trip-Rumpf, nicht im Wetter-Fragment)', () => {
		const v = vorlagen();
		for (const an of [true, false]) {
			const stand = { ...standAusAbo('route', TRIP, v), radarAn: an };
			const n = tripNutzlast({ client: null as never, stand: () => stand, vorlagen: () => v, abo: () => TRIP });
			assert.equal(
				(n.tripFelder as Record<string, unknown>).radar_alert_enabled,
				an,
				`Trip-Rumpf trägt radar_alert_enabled=${an} nicht: ${JSON.stringify(n.tripFelder)}`
			);
			assert.equal('radar_alert_enabled' in (n.weatherConfig as Record<string, unknown>), false, 'Radar gehört nicht ins display_config-Fragment');
		}
	});

	test('WetterTab (Instanz-Skript, Trip): Bestand ohne Feld wird als an gemeldet, Umlegen meldet false', async () => {
		const berichte: unknown[] = [];
		const daten = live();
		const api = {
			get: async (p: string) => (p === '/api/metrics' ? daten.metrics : p === '/api/templates' ? daten.templates : [])
		};
		const { u } = await umgebungFuer(WETTER_TAB, {
			context: 'route',
			trip: TRIP,
			preset: undefined,
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
		const felder = (b: unknown) => (b as { tripFelder: Record<string, unknown> }).tripFelder;
		assert.equal(felder(berichte[0]).radar_alert_enabled, true, 'Bestandstrip ohne Feld wird nicht als an gespeichert');
		u.aendern({ ...u.stand, radarAn: false });
		assert.equal(berichte.length, 2, 'das Umlegen des Radar-Schalters im Trip wird nicht gespeichert');
		assert.equal(felder(berichte[1]).radar_alert_enabled, false);
	});
});
