// Rework #3020 R1, AC-13: Premium-SMS im Reiter „Zustellung“ fuer Trip UND Ortsvergleich (EIN Code).
// Mit Premium-SMS-Rueckadresse (Handler vorhanden) ist das Kaestchen schaltbar, ohne gesperrt; im Vergleich
// ist der Premium-SMS-Block sichtbar und schaltbar, und Schalten landet in der Nutzlast des Kontexts.
// Ersatz fuer die mit #3357 geloeschten premium_sms_context_gating_render.test.ts und
// compare_versand_zeigt_schaltbare_premium_sms.test.ts.
//
// Spec: docs/specs/modules/rework_3020_pruefungen_wiederherstellen.md (AC-13)
//
// Server-Render der ECHTEN organisms/zustellung-tab/KanalTabelle.svelte (Muster feat3202_kanalzeile_mockup),
// gespeist aus dem echten Modell (`kanalStatus`, `standAusTrip`/`standAusPreset`), plus echte Nutzlast.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/rework_3020_premium_sms_schaltbar.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';
import { locale } from '../../../../i18n/index.ts';
import { kanalStatus, standAusPreset, standAusTrip, type Kontext, type ZustellungStand } from '../zustellungModell.ts';
import { zustellungNutzlast } from '../zustellungSpeicherung.ts';
import { presetVoll, profilAllesVerbunden, profilMit, tripVoll, type Json } from './zustellungTabDaten.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../../../../..');
const KANAL_TABELLE = path.join(FRONTEND, 'src', 'lib', 'components', 'organisms', 'zustellung-tab', 'KanalTabelle.svelte');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);
const { render } = await import('svelte/server');
afterEach(() => locale.set('de'));

const STAND: Record<Kontext, () => ZustellungStand> = {
	route: () => standAusTrip(tripVoll()),
	vergleich: () => standAusPreset(presetVoll())
};
/** Profil ohne Premium-SMS-Handler: noch nie gemeldet bzw. Tarif ohne Premium-SMS. */
const OHNE_HANDLER: Record<string, Json> = {
	nie_gemeldet: profilMit({ premium_sms_reply_state: 'none', premium_sms_reply_to: '', premium_sms_reply_at: null }),
	tarif_ohne: profilMit({ premium_sms_allowed: false, tier: 'free' })
};

async function premiumZeile(stand: ZustellungStand, profil: Json): Promise<{ zeile: string; briefing: string }> {
	const KanalTabelle = (await import(pathToFileURL(KANAL_TABELLE).href)).default;
	const h = render(KanalTabelle, { props: { stand, status: kanalStatus(profil), onaendern: () => {} } }).body.replace(/<!--[\s\S]*?-->/g, '');
	const zeile = h.match(/<tr[^>]*data-testid="zustellung-kanal-premium_sms"[\s\S]*?<\/tr>/)?.[0] ?? '';
	const briefing = zeile.match(/<[a-z]+\b[^>]*zustellung-kanal-premium_sms-briefing[^>]*>/)?.[0] ?? '';
	return { zeile, briefing };
}

for (const context of ['route', 'vergleich'] as const) {
	describe(`Rework #3020 AC-13 (${context}): Premium-SMS folgt dem Handler`, () => {
		test('Handler vorhanden: Zeile sichtbar, Briefing-Kaestchen und Alarm schaltbar', async () => {
			const { zeile, briefing } = await premiumZeile(STAND[context](), profilAllesVerbunden());
			assert.ok(zeile, 'Premium-SMS-Zeile fehlt');
			assert.ok(briefing, 'Premium-SMS-Briefing-Kaestchen fehlt');
			assert.ok(!/\sdisabled\b/.test(briefing) && !/aria-disabled="true"/.test(briefing), `Kaestchen gesperrt: ${briefing}`);
			assert.ok(!zeile.includes('zustellung-kanal-premium_sms-alarm-gesperrt'), 'Alarm-Zelle gesperrt trotz Handler');
			assert.ok(zeile.includes('zustellung-kanal-premium_sms-alarm"'), 'Alarm-Schalter fehlt');
		});

		for (const [fall, profil] of Object.entries(OHNE_HANDLER)) {
			test(`kein Handler (${fall}): Zeile sichtbar, Kaestchen gesperrt, Alarm gesperrt`, async () => {
				const { zeile, briefing } = await premiumZeile(STAND[context](), profil);
				assert.ok(zeile, 'die Zeile bleibt sichtbar (D3)');
				assert.ok(/\sdisabled\b/.test(briefing) || /aria-disabled="true"/.test(briefing), `Kaestchen nicht gesperrt: ${briefing}`);
				assert.ok(zeile.includes('zustellung-kanal-premium_sms-alarm-gesperrt'), 'Alarm-Zelle nicht gesperrt');
			});
		}

		test('Schalten wirkt: Briefing- und Alarm-Premium-SMS landen in der Nutzlast des Kontexts', () => {
			const vorher = STAND[context]();
			const jetzt: ZustellungStand = {
				...vorher,
				briefing: { ...vorher.briefing, premium_sms: !vorher.briefing.premium_sms },
				alarme: { ...vorher.alarme, premium_sms: !vorher.alarme.premium_sms }
			};
			const n = zustellungNutzlast(context, vorher, jetzt);
			const versand = (context === 'route' ? (n.versand as Json)?.report_config : n.versand) as Json;
			assert.equal(versand?.send_premium_sms, jetzt.briefing.premium_sms, `send_premium_sms fehlt: ${JSON.stringify(n.versand)}`);
			assert.equal((n.alarme as Json)?.alert_channels?.premium_sms, jetzt.alarme.premium_sms, `alert_channels.premium_sms fehlt: ${JSON.stringify(n.alarme)}`);
		});
	});
}
