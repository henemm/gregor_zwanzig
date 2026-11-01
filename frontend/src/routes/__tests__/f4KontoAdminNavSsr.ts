// Issue #2653 (i18n F4, Epic #2644) — gemeinsamer SSR-Pruefstand fuer die
// Konto-Seite, die Admin-Seite und die Navigation (Sidebar, BottomNav,
// Konto-Blatt ueber das ECHTE +layout.svelte). Feste Zeit 2026-10-29T06:00+02:00,
// Zone Europe/Berlin, Nutzer `golden-de`. Die feste Uhr ist eine Zeit-Fixture
// (nur `new Date()` ohne Argument und `Date.now()`), keine Attrappe des Prueflings.
// Das Konto-Blatt ist im SSR sonst zu: `konto-sheet-offen.hooks.mjs` oeffnet
// NUR das generische Bottom-Sheet, Layout und KontoSheet laufen echt.
// Golden: tests/golden/f4_konto_admin_nav/<fall>.de.html = Ist-Stand VOR der
// Umstellung (nie neu schreiben); <fall>.en.html = Review-Hilfe, aktualisiert mit
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/routes/account/__tests__/konto_sprache_je_nutzer.test.ts
// Spec: docs/specs/modules/i18n_f4_konto_admin_nav_2653.md (Implementation Details 7)

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { FRONTEND, ROUTES, HERE, render, ohneKommentare } from './onboardingSsr.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-app-environment-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
// Zuletzt registriert => laeuft zuerst: oeffnet nur mobile/Sheet.svelte.
register(pathToFileURL(path.join(HERE, 'konto-sheet-offen.hooks.mjs')).href, base);
// Benutzer-Menue der Sidebar nur mit `globalThis.__gzSidebarMenueOffen` offen (Golden: zu).
register(pathToFileURL(path.join(HERE, 'sidebar-menue-offen.hooks.mjs')).href, base);

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

export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f4_konto_admin_nav');
export const { locale, trFor, trnFor } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/index.ts')).href);

const seite = async (rel: string) => (await import(pathToFileURL(path.join(ROUTES, rel)).href)).default;
const KontoSeite = await seite('account/+page.svelte');
const AdminSeite = await seite('admin/+page.svelte');
const Layout = await seite('+layout.svelte');
export const layoutLoad = (await import(pathToFileURL(path.join(ROUTES, '+layout.server.ts')).href)).load;

/** Vor `JETZT_MS` um `min` Minuten (ISO). */
export const vorMinuten = (min: number) => new EchtesDate(JETZT_MS - min * 60000).toISOString();

/** Profil-Fixture wie GET /api/auth/profile (Tier Premium, Telegram gekoppelt). */
export function profil(over: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		id: 'golden-de',
		display_name: 'Golden',
		email: 'golden@example.org',
		mail_to: 'golden@example.org',
		pending_contact_address: 'neu@example.org',
		sms_to: '+491511234567',
		sms_verified: false,
		telegram_chat_id: '987654321',
		email_verified: true,
		has_password: true,
		tier: 'premium',
		requested_tier: 'standard',
		created_at: '2026-09-01T10:00:00Z',
		quota: { trips: 5, compare_presets: 3, locations: 20 },
		passkeys: [
			{ id: 'pk1', label: 'Laptop', authenticator_name: 'iCloud-Schlüsselbund', created_at: '2026-09-02T10:00:00Z', last_used_at: '2026-10-20T08:00:00Z' }
		],
		...over
	};
}

/** Daten der Konto-Seite (Loader-Form, account/+page.server.ts). */
export function kontoDaten(over: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		profile: profil(),
		scheduler: {
			jobs: [
				{
					id: 'trip_reports_hourly',
					next_run: '2026-10-29T07:00:00+02:00',
					last_run: { time: vorMinuten(3), status: 'error', error: 'timeout' }
				}
			]
		},
		health: { status: 'ok', version: '1.2.3' },
		templates: [
			{ id: 'wandern', label: 'Wandern', metrics: ['temperature', 'wind'] },
			{ id: 'frei', name: 'Frei', description: 'ohne Metriken' }
		],
		trips: [{ id: 't1', name: 'GR20' }],
		comparePresets: [],
		locations: [
			{ id: 'l1', name: 'Innsbruck', lat: 47.27, lon: 11.4 },
			{ id: 'l2', name: 'Ajaccio', lat: 41.9, lon: 8.7 }
		],
		metricPresets: [
			{ id: 'mp1', name: 'Sommer', metrics: ['temperature', 'wind', 'gust'], is_default: true },
			{ id: 'mp2', name: 'Winter', metrics: ['fresh_snow'] }
		],
		premiumSmsLinkCodeExists: true,
		smsDailyUsage: {
			sms: { used: 3, limit: 10, reserve: 2 },
			premium_sms: { used: 6, limit: 4, reserve: 1 }
		},
		...over
	};
}

const adminNutzer = (over: Record<string, unknown>) => ({
	id: 'u',
	email: 'u@example.org',
	display_name: 'U',
	tier: 'free',
	requested_tier: '',
	requested_at: '',
	email_verified_at: '',
	created_at: '2026-08-01T10:00:00Z',
	disabled: false,
	is_test_user: false,
	last_trip_report_run: null,
	open_meteo_calls_today: 0,
	...over
});
const einladung = (over: Record<string, unknown>) => ({
	id: 'i1',
	tier: 'standard',
	note: '',
	status: 'open',
	created_at: '2026-10-06T10:00:00Z',
	created_by: 'golden-de',
	used_by: '',
	used_at: null,
	revoked_at: null,
	...over
});

/** Daten der Admin-Seite: zwei Nutzer, Einladungen (offen, benutzt, widerrufen). */
export function adminDaten(): Record<string, unknown> {
	return {
		selfId: 'golden-de',
		users: [
			adminNutzer({ id: 'golden-de', display_name: 'Golden', tier: 'premium', requested_tier: 'standard', requested_at: '2026-10-27T09:00:00Z', open_meteo_calls_today: 12 }),
			adminNutzer({
				id: 'bert',
				display_name: '',
				email: 'bert@example.org',
				is_test_user: true,
				disabled: true,
				last_trip_report_run: { time: '2026-10-29T05:00:00+02:00', status: 'ok' }
			})
		],
		invites: [
			einladung({ id: 'offen', note: '' }),
			einladung({ id: 'benutzt', note: 'Onkel Karl', tier: 'premium', status: 'used', used_by: 'karl', used_at: '2026-10-07T08:00:00Z' }),
			einladung({ id: 'weg', note: 'Cousin', tier: 'free', status: 'revoked', revoked_at: '2026-10-08T09:00:00Z' })
		]
	};
}

/** Layout-Daten eines angemeldeten Nutzers (Sprache aus data.lang wie im Layout-Loader). */
export function layoutDaten(lang: 'de' | 'en', over: Record<string, unknown> = {}): Record<string, unknown> {
	return { userId: 'golden-de', displayName: 'Golden', isAdmin: true, lang, ...over };
}

const html = (komp: unknown, props: Record<string, unknown>) => ohneKommentare(render(komp as never, { props } as never).body);

export const kontoRendern = (data: Record<string, unknown>) => html(KontoSeite, { data });
export const adminRendern = (data: Record<string, unknown>) => html(AdminSeite, { data });
/** Echtes +layout.svelte (setzt `locale` aus data.lang), Konto-Blatt offen, Pfad /trips. */
export function navRendern(data: Record<string, unknown>): string {
	(globalThis as Record<string, unknown>).__gzLayoutTestPath = '/trips';
	return html(Layout, { data, children: (r: { push: (s: string) => void }) => r.push('<div>INHALT</div>') });
}

/** Ersetzt nur die Netzgrenze: `fetch` antwortet je Sitzungs-Cookie mit eigenen Daten (sonst 404). */
export async function mitApi<T>(antworten: Record<string, Record<string, unknown>>, lauf: () => Promise<T>): Promise<T> {
	const echt = globalThis.fetch;
	globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
		const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
		const daten = antworten[sitzung]?.[new URL(String(u)).pathname];
		return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
	}) as unknown as typeof fetch;
	try {
		return await lauf();
	} finally {
		globalThis.fetch = echt;
	}
}

export const cookiesFuer = (sitzung: string) => ({ get: (n: string) => (n === 'gz_session' ? sitzung : undefined) });

/** Die Faelle der Golden-Fixture (Spec Implementation Details 7). */
export const FAELLE: Record<string, (lang: 'de' | 'en') => string> = {
	konto: () => kontoRendern(kontoDaten()),
	admin: () => adminRendern(adminDaten()),
	navigation: (lang) => navRendern(layoutDaten(lang))
};

/** Schreibt die Golden-Dateien einer Sprache. */
export function schreibeGolden(lang: 'de' | 'en'): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	for (const [fall, f] of Object.entries(FAELLE)) {
		locale.set(lang);
		writeFileSync(path.join(GOLDEN_DIR, `${fall}.${lang}.html`), f(lang) + '\n');
	}
	locale.set('de');
}
