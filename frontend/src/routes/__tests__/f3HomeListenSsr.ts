// Issue #2652 (i18n F3, Epic #2644) — gemeinsamer SSR-Pruefstand fuer Cockpit
// und Listen (Trips, Ortsvergleiche, Orte, Archiv). Echte Seiten (svelte/server)
// mit deterministischer Fixture: feste Zeit 2026-10-29T06:00+02:00, Zone
// Europe/Berlin, Nutzer `golden-de`. Die feste Uhr ist eine Zeit-Fixture (nur
// `new Date()` ohne Argument und `Date.now()`), keine Attrappe des Prueflings.
// Golden: tests/golden/f3_home_listen/<fall>.de.html = Ist-Stand VOR der Umstellung
// (Commit 8a2a0d2b7, nie neu schreiben); <fall>.en.html = Review-Hilfe, aktualisiert mit
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/routes/__tests__/listen_sprache_je_nutzer.test.ts
// Spec: docs/specs/modules/i18n_f3_home_listen_2652.md (Implementation Details 9)

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { FRONTEND, ROUTES, render, ohneKommentare, aktiverVergleich } from './onboardingSsr.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);

process.env.TZ = 'Europe/Berlin';
export const JETZT_MS = Date.parse('2026-10-29T06:00:00+02:00');
const EchtesDate = Date;
class FesteUhr extends EchtesDate {
	constructor(...args: unknown[]) {
		if (args.length === 0) super(JETZT_MS);
		else super(...(args as [string]));
	}
	static now(): number {
		return JETZT_MS;
	}
}
globalThis.Date = FesteUhr as unknown as DateConstructor;

export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f3_home_listen');
export const { locale, trFor, trnFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const seite = async (rel: string) => (await import(pathToFileURL(path.join(ROUTES, rel)).href)).default;
const Cockpit = await seite('+page.svelte');
const TripListe = await seite('trips/+page.svelte');
const CompareListe = await seite('compare/+page.svelte');
const OrteListe = await seite('locations/+page.svelte');
const ArchivSeite = await seite('archiv/+page.svelte');
export const archivLoad = (await import(pathToFileURL(path.join(ROUTES, 'archiv/+page.server.ts')).href)).load;
export const tripsLoad = (await import(pathToFileURL(path.join(ROUTES, 'trips/+page.server.ts')).href)).load;
export const layoutLoad = (await import(pathToFileURL(path.join(ROUTES, '+layout.server.ts')).href)).load;

const RC = {
	enabled: true,
	morning_enabled: true,
	evening_enabled: true,
	morning_time: '07:00:00',
	evening_time: '18:00:00',
	send_email: true,
	send_telegram: true
};
const wp = (id: string, h: number) => ({ id, name: id, lat: 42.2, lon: 9.0, elevation_m: h });
const etappe = (id: string, date: string) => ({ id, name: `Etappe ${id}`, date, waypoints: [wp(`${id}a`, 900), wp(`${id}b`, 1600)] });

export function tripAktiv(id = 'trip-gr20', name = 'GR20 Nord') {
	return {
		id,
		name,
		region: 'Korsika',
		stages: [etappe('e1', '2026-10-28'), etappe('e2', '2026-10-29'), etappe('e3', '2026-10-30')],
		report_config: RC,
		display_config: {}
	};
}
export function tripGeplant(id = 'trip-pyr', name = 'Pyrenäen-Traverse') {
	return { id, name, region: 'Pyrenäen', stages: [etappe('p1', '2026-11-10')], report_config: RC, display_config: {} };
}
export function tripFertig() {
	return { id: 'trip-alt', name: 'Dolomiten Höhenweg', stages: [etappe('d1', '2026-09-01'), etappe('d2', '2026-09-03')] };
}
export function vergleich(id = 'cmp-stubai') {
	return {
		...aktiverVergleich(id),
		name: 'Hüttenvergleich Stubai',
		location_ids: ['l1', 'l2', 'l3'],
		letzter_versand: '2026-10-28T07:00:00+01:00',
		display_config: { region: 'Tirol', profile_label: 'Wandern' }
	};
}
const NB = (local_time: string, slot: string) => ({
	at: `2026-10-29T${local_time}:00+01:00`,
	local_date: '2026-10-29',
	local_time,
	tz: 'Europe/Berlin',
	tz_abbr: 'CET',
	slot
});

const html = (komp: unknown, data: Record<string, unknown>) =>
	ohneKommentare(render(komp as never, { props: { data } as never }).body);

const SEITEN = { cockpit: Cockpit, trips: TripListe, compare: CompareListe, locations: OrteListe, archiv: ArchivSeite };
/** Rendert eine der Seiten dieses Pakets mit den Daten eines Loaders. */
export const seiteRendern = (seite: keyof typeof SEITEN, data: Record<string, unknown>) => html(SEITEN[seite], data);

/** Die Faelle der Golden-Fixture (Spec Implementation Details 9) plus Planung und Orte. */
export const FAELLE: Record<string, () => string> = {
	cockpit_trip: () =>
		html(Cockpit, {
			userId: 'golden-de',
			trips: [tripAktiv(), tripGeplant(), tripFertig()],
			presets: [vergleich()],
			nextBriefings: { trips: { 'trip-gr20': NB('18:00', 'evening') }, compare: { 'cmp-stubai': NB('07:00', 'morning') } },
			cockpitStatus: {
				briefings: [],
				alerts: [
					{ entity_type: 'trip', entity_id: 'trip-gr20', sent_at: '2026-10-29T05:30:00+02:00', severity: 'HIGH', changes_count: 2 },
					{ entity_type: 'trip', entity_id: 'trip-gr20', sent_at: '2026-10-29T04:10:00+02:00', severity: 'LOW', changes_count: 1 }
				]
			}
		}),
	cockpit_vergleich: () =>
		html(Cockpit, {
			userId: 'golden-de',
			trips: [tripFertig()],
			presets: [vergleich(), { ...vergleich('cmp-zwei'), name: 'Zweiter Vergleich' }],
			nextBriefings: { trips: {}, compare: { 'cmp-stubai': NB('07:00', 'morning') } },
			cockpitStatus: null
		}),
	cockpit_planung: () =>
		html(Cockpit, {
			userId: 'golden-de',
			trips: [tripGeplant(), tripFertig()],
			presets: [{ ...vergleich('cmp-entwurf'), location_ids: [] }],
			nextBriefings: null,
			cockpitStatus: null
		}),
	trip_liste: () => html(TripListe, { trips: [tripAktiv(), tripGeplant()], profile: null }),
	compare_liste_leer: () => html(CompareListe, { presets: [], profile: null }),
	orte_liste: () =>
		html(OrteListe, {
			locations: [{ id: 'o1', name: 'Innsbruck', lat: 47.2692, lon: 11.4041, elevation_m: 574, activity_profile: 'wandern' }]
		}),
	archiv: () => html(ArchivSeite, { entries: ARCHIV_EINTRAEGE_GOLDEN() })
};

/** Fetch-Stub-Antworten fuer die echten Server-Loader (je Sitzung eigene Daten). */
export function archivApi(name: string, etappen: number, orte: number) {
	const archived_at = '2026-10-20T08:00:00Z';
	return {
		trips: [{ ...tripFertig(), id: `t-${name}`, name: `Trip ${name}`, stages: tripAktiv().stages.slice(0, etappen), archived_at }],
		presets: [{ ...vergleich(`c-${name}`), name: `Vergleich ${name}`, location_ids: ['a', 'b'].slice(0, orte), archived_at }]
	};
}

let archivGolden: unknown[] = [];
const ARCHIV_EINTRAEGE_GOLDEN = () => archivGolden;

/** Ruft einen Loader mit einem fetch-Stub auf, der je Sitzungs-Cookie antwortet. */
export async function mitApi<T>(antworten: Record<string, Record<string, unknown>>, lauf: () => Promise<T>): Promise<T> {
	const echt = globalThis.fetch;
	globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
		const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
		const pfad = new URL(String(u)).pathname;
		const daten = antworten[sitzung]?.[pfad];
		return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
	}) as unknown as typeof fetch;
	try {
		return await lauf();
	} finally {
		globalThis.fetch = echt;
	}
}

export const cookiesFuer = (sitzung: string) => ({ get: (n: string) => (n === 'gz_session' ? sitzung : undefined) });

/** Archiv-Eintraege der Golden-Fixture ueber den ECHTEN Loader (1 Trip mit 3 Etappen, 1 Vergleich mit 1 Ort). */
export async function ladeArchivGolden(): Promise<void> {
	const api = archivApi('golden', 3, 1);
	const data = await mitApi({ S: { '/api/trips': api.trips, '/api/compare/presets': api.presets } }, () =>
		archivLoad({ cookies: cookiesFuer('S'), locals: { userId: 'golden-de', lang: 'de' } } as never)
	);
	archivGolden = (data as { entries: unknown[] }).entries;
}

/** Schreibt die Golden-Dateien einer Sprache (Test-Lauf mit GZ_GOLDEN_SCHREIBEN=en). */
export function schreibeGolden(lang: 'de' | 'en'): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	for (const [fall, f] of Object.entries(FAELLE)) {
		locale.set(lang);
		writeFileSync(path.join(GOLDEN_DIR, `${fall}.${lang}.html`), f() + '\n');
	}
	locale.set('de');
}
