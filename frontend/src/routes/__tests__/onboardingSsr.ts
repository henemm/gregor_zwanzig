// Gemeinsamer SSR-Aufbau fuer die Onboarding-Tests (Spec onboarding_willkommen_checkliste.md).
// Registriert dieselben Hooks wie admin_nav_nur_fuer_admin.test.ts, damit
// +page.svelte, +layout.server.ts und die _home-Bausteine echt (serverseitig)
// laufen. Pfadregel #1409: alles relativ zu DIESER Datei.

import assert from 'node:assert/strict';
import { register } from 'node:module';
import { existsSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
export const FRONTEND = path.resolve(HERE, '../../..');
export const ROUTES = path.resolve(HERE, '..');
const base = pathToFileURL(FRONTEND + '/').href;

register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, base);
register(
	pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-new/__tests__/ssrRunesHook.mjs')).href,
	base
);
register(pathToFileURL(path.join(HERE, 'layout-ssr-hooks.mjs')).href, base);
register(pathToFileURL(path.join(HERE, '../admin/__tests__/server-load-resolve.hooks.mjs')).href, base);

export const { render } = await import('svelte/server');

export const CHECKLISTE_DATEI = path.join(ROUTES, '_home/StartklarCheckliste.svelte');
export const EMPTY_KACHEL_DATEI = path.join(ROUTES, '_home/EmptyKachel.svelte');

/** Laedt eine Svelte-Komponente; fehlt sie, kommt `null` (der Test meldet das selbst). */
export async function ladeKomponente(datei: string): Promise<any | null> {
	if (!existsSync(datei)) return null;
	return (await import(pathToFileURL(datei).href)).default;
}

export const Page = (await import(pathToFileURL(path.join(ROUTES, '+page.svelte')).href)).default;

// Vereinigte deutsche Katalogkarte (Issue #2647: Bereichsdateien statt de.json).
export const KATALOG = (await import(pathToFileURL(path.join(FRONTEND, 'src/lib/i18n/messages/de/index.ts')).href))
	.de as Record<string, string>;

/** Katalogwert, der fuer den Test existieren MUSS. */
export function text(key: string): string {
	const v = KATALOG[key];
	assert.ok(typeof v === 'string' && v.trim().length > 0, `Katalogschluessel ${key} fehlt oder ist leer (messages/de/)`);
	return v;
}

export const ohneKommentare = (html: string) => html.replace(/<!--[\s\S]*?-->/g, '');

/** HTML-Teilbaum des Elements mit `data-testid="<id>"` (inkl. Start-/Endtag), sonst null. */
export function teilbaum(html: string, testid: string): string | null {
	const h = ohneKommentare(html);
	const pos = h.indexOf(`data-testid="${testid}"`);
	if (pos < 0) return null;
	const start = h.lastIndexOf('<', pos);
	const tag = /^<([a-zA-Z0-9-]+)/.exec(h.slice(start))![1];
	const re = new RegExp(`<${tag}\\b[^>]*?(/?)>|</${tag}>`, 'g');
	re.lastIndex = start;
	let tiefe = 0;
	let m: RegExpExecArray | null;
	while ((m = re.exec(h))) {
		if (m[0].startsWith('</')) tiefe--;
		else if (m[1] !== '/') tiefe++;
		if (tiefe === 0) return h.slice(start, re.lastIndex);
	}
	return h.slice(start);
}

/** Alle <a>-Links: href + sichtbarer Text. */
export function links(html: string): { href: string; text: string }[] {
	const aus: { href: string; text: string }[] = [];
	for (const m of ohneKommentare(html).matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/g)) {
		const href = /\bhref="([^"]*)"/.exec(m[1])?.[1] ?? '';
		aus.push({ href, text: m[2].replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim() });
	}
	return aus;
}

/** Sichtbarer Text eines HTML-Stuecks (Tags entfernt, Entities grob dekodiert). */
export function sichtbar(html: string): string {
	return html
		.replace(/<[^>]*>/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/\s+/g, ' ')
		.trim();
}

/** Profil-JSON wie GET /api/auth/profile (Go) fuer einen frisch angelegten Nutzer. */
export function profilNeu(over: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		id: 'neu-1',
		display_name: 'Neu',
		role: 'user',
		onboarding_pending: true,
		onboarding_dismissed: false,
		checklist_dismissed: false,
		email_verified: false,
		sms_allowed: false,
		premium_sms_allowed: false,
		...over
	};
}

/** OnboardingProfil (Frontend-Form, Vertrag onboardingSichtbarkeit.ts). */
export function onboardingNeu(over: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		pending: true,
		dismissed: false,
		checklistDismissed: false,
		testMailSentAt: null,
		firstBriefingAt: null,
		emailVerified: false,
		telegramVerknuepft: false,
		smsAllowed: false,
		premiumSmsAllowed: false,
		...over
	};
}

/** Aktiver Ortsvergleich (deriveStatusFromPreset === 'active'). */
export function aktiverVergleich(id = 'cmp-1'): Record<string, unknown> {
	return {
		id,
		name: 'Huettenvergleich',
		location_ids: ['loc-1', 'loc-2'],
		schedule: 'daily',
		weekday: 0,
		profil: 'allgemein',
		hour_from: 9,
		hour_to: 16,
		forecast_hours: 48,
		empfaenger: [],
		created_at: '2026-10-01T00:00:00Z',
		display_config: {}
	};
}

/** Trip, der in der Zukunft beginnt (Planungsmodus der Startseite). */
export function kuenftigerTrip(id = 'trip-1'): Record<string, unknown> {
	const tag = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString().slice(0, 10);
	return {
		id,
		name: 'Zukunfts-Trip',
		stages: [
			{
				id: `${id}-s1`,
				name: 'Etappe 1',
				date: tag(20),
				waypoints: [
					{ id: 'w1', name: 'A', lat: 47.2, lon: 11.4, elevation_m: 600 },
					{ id: 'w2', name: 'B', lat: 47.3, lon: 11.5, elevation_m: 900 }
				]
			}
		]
	};
}

export function renderStartseite(data: Record<string, unknown>): string {
	return ohneKommentare(render(Page, { props: { data: { cockpitStatus: null, userId: 'u1', ...data } } }).body);
}
