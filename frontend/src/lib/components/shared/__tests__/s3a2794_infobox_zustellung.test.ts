// Issue #2794 S3a, Teil-PR 2 (Fix-Loop 2, Adversary Runde 3: F009).
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-6 (Anlege-Schritte Wetter/Zustellung)
// und infoboxKeys.ts: bis Teil-PR 3/S3b zeigen die Schritte `wetter`/`zustellung` den Text ihrer
// bisherigen Bausteine — Wetter den der Metrik-Auswahl, Zustellung den des Versands.
//
// Der Alt-Test (s3a2794_ac6_infobox_schluessel_fuer_neue_kennungen) prueft nur, DASS ein
// Schluessel existiert. Mutation N11 (`zustellung: 'info.alarme.route'`) blieb gruen. Hier wird
// die ECHTE Infobox (molecules/Infobox.svelte) unter svelte/server gerendert und ihr sichtbarer
// Text fuer den Schritt `zustellung` mit dem des Versand-Bausteins verglichen (je Kontext), dazu
// der exakte Katalogschluessel.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/s3a2794_infobox_zustellung.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { lade, renderKomponente, innen, sichtbarerText } from './infoboxSsr.ts';
import { infoboxKey } from '../infoboxKeys.ts';

const SOLL: Record<'route' | 'vergleich', Record<'wetter' | 'zustellung', { schluessel: string; wieReiter: string }>> = {
	route: {
		wetter: { schluessel: 'info.wetter-metriken.route', wieReiter: 'wetter-metriken' },
		zustellung: { schluessel: 'info.versand.route', wieReiter: 'versand' }
	},
	vergleich: {
		wetter: { schluessel: 'info.wetter-metriken.vergleich', wieReiter: 'wetter-metriken' },
		zustellung: { schluessel: 'info.versand.vergleich', wieReiter: 'versand' }
	}
};

async function text(reiter: string, context: string): Promise<string> {
	const Infobox = await lade('molecules/Infobox.svelte');
	const html = renderKomponente(Infobox, { reiter, context });
	return sichtbarerText(innen(html, `infobox-${reiter}-${context}`));
}

describe('AC-6 (F009): Infobox der Anlege-Schritte Wetter/Zustellung zeigt den Text ihres Bausteins', () => {
	for (const ctx of ['route', 'vergleich'] as const) {
		for (const schritt of ['zustellung', 'wetter'] as const) {
			const { schluessel, wieReiter } = SOLL[ctx][schritt];
			test(`s3a2794_f009_infobox_${schritt}_${ctx}_zeigt_text_von_${wieReiter}`, async () => {
				assert.equal(
					(infoboxKey as (c: string, r: string) => string | undefined)(ctx, schritt),
					schluessel,
					`F009: Schritt ${schritt} (${ctx}) zeigt nicht ${schluessel}`
				);
				const ist = await text(schritt, ctx);
				const soll = await text(wieReiter, ctx);
				assert.ok(soll.length > 10, `Messaufbau: Infobox ${wieReiter}/${ctx} ohne Text`);
				assert.equal(ist, soll, `F009: Infobox ${schritt}/${ctx} zeigt „${ist}“ statt des ${wieReiter}-Texts „${soll}“`);
			});
		}
	}
});
