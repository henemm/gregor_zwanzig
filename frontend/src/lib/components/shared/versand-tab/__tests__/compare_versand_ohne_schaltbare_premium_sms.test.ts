// Regressionswaechter — Issue #1738, AC-8.
// Spec: docs/specs/modules/fix_1738_trips_new_versand_tab.md — AC-8.
//
// ⚠️ DIESER TEST IST VON ANFANG AN GRUEN. Er sichert Bestand, kein neues
// Verhalten: die Zusicherung aus #1717 AC-1 (Premium-SMS ist laut ADR-0049
// ausschliesslich ein Trip-Briefing-Kanal, im Orts-Vergleich steht der feste
// Platzhalter) darf durch die #1738-Migration nicht reissen.
//
// Warum er trotzdem hier steht: mit #1738 benutzt auch /trips/new denselben
// geteilten Baustein. Wer den Premium-SMS-Schalter dort "einfach immer
// sichtbar" macht, indem er das Prop-Gating in VTBriefingChannels aufweicht,
// schaltet ihn damit zugleich in den drei Vergleichs-Mounts frei. Genau diese
// Verwechslung faengt dieser Test.
//
// Ueberschneidet sich bewusst mit premium_sms_context_gating_render.test.ts
// (#1717 AC-1) — dort ist es die Zusicherung selbst, hier die Gegenprobe zur
// Migration.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausfuehrung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/versand-tab/__tests__/compare_versand_ohne_schaltbare_premium_sms.test.ts

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
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/shared/VersandTab.svelte')).href
	)
).default;

function renderVersand(context: 'route' | 'vergleich'): string {
	return render(VersandTab, { props: { context } }).body;
}

/** Der schaltbare Premium-SMS-Block bringt Verbindungsstatus + Hinweis mit;
 *  der feste Platzhalter hat beides nicht. */
const SCHALTBAR = 'data-testid="channel-status-premium-sms"';
const PLATZHALTER_TEXT = 'bald verfügbar';

describe('AC-8: der Ortsvergleich behaelt seinen festen Premium-SMS-Platzhalter', () => {
	test('vergleich_zeigt_keinen_schaltbaren_premium_sms_block', () => {
		const vergleich = renderVersand('vergleich');

		// Gegenprobe zuerst: im Trip-Briefing IST der schaltbare Block da. Ohne
		// sie bliebe der Test auch dann gruen, wenn der Marker nirgends mehr
		// entstuende — dann bewachte er nichts.
		assert.ok(
			renderVersand('route').includes(SCHALTBAR),
			'AC-8 (Gegenprobe): Im Trip-Briefing muss der schaltbare Premium-SMS-Block existieren — ' +
				'sonst prueft die Zusicherung unten nichts.'
		);

		assert.ok(
			!vergleich.includes(SCHALTBAR),
			'AC-8: Im Versand-Bereich des Ortsvergleichs ist ein schaltbarer Premium-SMS-Block ' +
				'entstanden. Premium-SMS ist laut ADR-0049 ausschliesslich ein Trip-Briefing-Kanal ' +
				'(#1717 AC-1).'
		);
		assert.ok(
			vergleich.includes(PLATZHALTER_TEXT),
			`AC-8: Der feste "${PLATZHALTER_TEXT}"-Hinweis fehlt im Ortsvergleich — der Kanal staende ` +
				'dort ohne jede Erklaerung.'
		);
	});
});
