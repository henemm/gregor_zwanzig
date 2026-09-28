// Charakterisierungs-Test — Issue #2422 S3, AC-25 (Verdikt 5: "konsistent").
// Spec: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md
//
// AC-25: Given `report_config` (a) ohne `send_email`, (b) ohne `send_telegram`/
// `send_sms`/`send_premium_sms`, (c) ganz ohne `report_config` / When der
// Versand-Reiter serverseitig gerendert wird / Then ist E-Mail angehakt und die
// anderen drei nicht — dieselbe Aussage wie AC-10 fuer die Auslieferung
// (Loader `loader.py:587` Default an; `_resolve_channel_flags` ohne
// report_config => nur E-Mail).
//
// ERWARTUNG: GRUEN schon heute (Charakterisierung, kein RED). Die Startwerte der
// vier Kanal-Haken entstehen beim Erzeugen der Komponente
// (`$state(untrack(() => reportConfig?.send_email !== false))`,
// VersandTab.svelte:143; EditReportConfigSection.svelte:78), also unter
// svelte/server messbar. Der Test bewacht, dass niemand den Editor-Default
// (E-Mail an, Rest aus) von der Auslieferung entkoppelt.
//
// Zwei Naehte, weil dieselbe Zusicherung an zwei Wirkorten steht:
//   - VersandTab (route)                     -> /trips/[id], Versand-Reiter
//   - EditReportConfigSection (showChannels) -> /trips/new (Zeitplan-Tab)
//
// Gegenprobe im Test: mit EXPLIZIT gesetzten Werten (send_email=false,
// send_telegram=true, ...) kippen die Haken — sonst wuerde der Test auch dann
// gruen bleiben, wenn die Komponente die Konfiguration gar nicht liest.
//
// Kein Mock. Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/versand_tab_defaults_gleich_auslieferung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const VersandTab = (
	await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte')).href)
).default;
const EditReportConfigSection = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/edit/EditReportConfigSection.svelte')).href
	)
).default;

const KANAELE = ['channel-email', 'channel-telegram', 'channel-sms', 'channel-premium-sms'] as const;
type Kanal = (typeof KANAELE)[number];
type Haken = Record<Kanal, boolean>;

/** true nur, wenn das boolsche `checked`-Attribut im <input> hinter dem Testid steht. */
function istAngehakt(html: string, testid: string): boolean {
	const marker = `data-testid="${testid}"`;
	const i = html.indexOf(marker);
	assert.notEqual(i, -1, `Testid "${testid}" nicht im gerenderten HTML gefunden.`);
	const start = html.indexOf('<input', i);
	assert.notEqual(start, -1, `Kein <input> nach Testid "${testid}".`);
	const tag = html.slice(start, html.indexOf('>', start) + 1);
	return /\bchecked(=""|(?=[\s/>]))/.test(tag);
}

function hakenAus(html: string): Haken {
	return Object.fromEntries(KANAELE.map((k) => [k, istAngehakt(html, k)])) as Haken;
}

function renderVersandTab(reportConfig: Record<string, unknown> | undefined): string {
	return render(VersandTab, { props: { context: 'route', reportConfig } }).body;
}

function renderEditSection(reportConfig: Record<string, unknown> | undefined): string {
	return render(EditReportConfigSection, {
		props: {
			reportConfig,
			mode: 'edit',
			showMailContent: false,
			showSchedule: false,
			showChannels: true,
			profileOverride: null
		}
	}).body;
}

const NUR_EMAIL: Haken = {
	'channel-email': true,
	'channel-telegram': false,
	'channel-sms': false,
	'channel-premium-sms': false
};

const FAELLE: { name: string; rc: Record<string, unknown> | undefined; erwartet: Haken }[] = [
	{
		name: '(a) report_config ohne send_email',
		rc: { enabled: true, send_telegram: false, send_sms: false, send_premium_sms: false },
		erwartet: NUR_EMAIL
	},
	{
		name: '(b) report_config ohne send_telegram/send_sms/send_premium_sms',
		rc: { enabled: true, send_email: true },
		erwartet: NUR_EMAIL
	},
	{ name: '(c) ganz ohne report_config', rc: undefined, erwartet: NUR_EMAIL },
	{ name: '(c2) leerer report_config-Block', rc: {}, erwartet: NUR_EMAIL },
	{
		name: 'Gegenprobe: explizit gesetzte Werte kippen die Haken',
		rc: { enabled: true, send_email: false, send_telegram: true, send_sms: true, send_premium_sms: true },
		erwartet: {
			'channel-email': false,
			'channel-telegram': true,
			'channel-sms': true,
			'channel-premium-sms': true
		}
	}
];

describe('AC-25 — Editor-Kanal-Defaults gleich Auslieferung (SSR, Charakterisierung)', () => {
	for (const f of FAELLE) {
		test(`VersandTab(route) — ${f.name}`, () => {
			assert.deepEqual(
				hakenAus(renderVersandTab(f.rc)),
				f.erwartet,
				`Kanal-Haken fuer ${JSON.stringify(f.rc)}: E-Mail an, Telegram/SMS/Premium-SMS aus ` +
					'(Default der Auslieferung, loader.py:587 / _resolve_channel_flags)'
			);
		});
		test(`EditReportConfigSection(showChannels) — ${f.name}`, () => {
			assert.deepEqual(
				hakenAus(renderEditSection(f.rc)),
				f.erwartet,
				`Kanal-Haken (Edit-Sektion) fuer ${JSON.stringify(f.rc)}`
			);
		});
	}
});
