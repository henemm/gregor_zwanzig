// TDD RED — Issue #3036: Reiter Zustellung ohne den Rahmen „Vorübergehend hier …“.
// Spec docs/specs/modules/rework_3036_uebergangsblock_aufloesen.md, AC-7 (Implementation Details Nr. 3).
//
// Gemessen am ECHTEN serverseitigen Render von shared/zustellung-tab/ZustellungTab.svelte (Trip und Orte)
// und der Anlege-Seite des Ortsvergleichs (CompareNewEditor, Test-Seam `stateOverride`). Kein Mock.
//
// Neue Kennungen (in der GREEN-Phase einzuführen):
//   data-testid="zustellung-beispiel-alarm"  data-abschnitt="beispiel-alarm"  — Beispiel-Alarm als eigener
//                                             Abschnitt, letzter Abschnitt des Reiters (Trip und Orte)
//   data-testid="zustellung-aktivierung"     data-abschnitt="aktivierung"     — fester Abschnitt für die
//                                             Pausieren/Aktivieren-Karte der Orte (Snippet `activation`),
//                                             direkt unter dem Kopf, vor den Briefing-Zeiten
// Entfällt: data-testid="zustellung-uebergang" (data-abschnitt="uebergang") samt Kopf zustellung.uebergang.*.
//
// RED heute: UebergangBlock trägt zustellung-uebergang, Beispiel-Alarm und Aktivierung stehen darin am Ende.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/rework_3036_zustellung_ohne_uebergang.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { lade, renderKomponente, renderVergleichNeu, innen, sichtbarerText } from './infoboxSsr.ts';

const { createRawSnippet } = await import('svelte');
const { de } = await import('../../../i18n/messages/de/index.ts');

const TRIP = { id: 't-3036', name: 'SSR-3036', stages: [], alert_rules: [], report_config: undefined };
const PRESET = {
	id: 'cp-3036', name: 'SSR-3036-Orte', location_ids: ['loc-a', 'loc-b'],
	alert_channels: { email: true, telegram: true, sms: false, premium_sms: false }
};
const AKTIVIERUNG = createRawSnippet(() => ({ render: () => '<div data-testid="test-aktivierungskarte">Pausieren</div>' }));

async function reiter(context: 'route' | 'vergleich', mitAktivierung = false): Promise<string> {
	const ZustellungTab = await lade('shared/zustellung-tab/ZustellungTab.svelte');
	const props: Record<string, unknown> = context === 'route' ? { context, trip: TRIP } : { context, preset: PRESET };
	if (mitAktivierung) props.activation = AKTIVIERUNG;
	return renderKomponente(ZustellungTab, props).replace(/<!--[\s\S]*?-->/g, '');
}
const anzahl = (h: string, merkmal: string) => h.split(merkmal).length - 1;
const pos = (h: string, merkmal: string) => {
	const i = h.indexOf(merkmal);
	assert.notEqual(i, -1, `${merkmal} fehlt im Reiter`);
	return i;
};
const katalogDe = de as Record<string, string | undefined>;
const UEBERGANGSTEXT = [katalogDe['zustellung.uebergang.titel'], katalogDe['zustellung.uebergang.hinweis']].filter(Boolean) as string[];

for (const context of ['route', 'vergleich'] as const) {
	describe(`#3036 AC-7 Reiter Zustellung (${context}): kein Übergangsblock (Beispiel-Alarm entfernt, #3458)`, () => {
		test('kein Element zustellung-uebergang, kein Abschnitt „uebergang“, kein „Vorübergehend hier“', async () => {
			const h = await reiter(context, context === 'vergleich');
			assert.ok(anzahl(h, 'data-testid="zustellung-tab"') === 1, 'Messaufbau: Reiter nicht gerendert');
			assert.equal(anzahl(h, 'data-testid="zustellung-uebergang"'), 0, 'Übergangsblock noch im Reiter');
			assert.equal(anzahl(h, 'data-abschnitt="uebergang"'), 0, 'Abschnitt „uebergang“ noch im Reiter');
			const text = sichtbarerText(h);
			for (const t of UEBERGANGSTEXT) assert.ok(!text.includes(t), `Übergangstext noch sichtbar: ${t}`);
			assert.doesNotMatch(text, /Vorübergehend hier/);
		});

		// #3458: AC-7 „Beispiel-Alarm letzter Abschnitt“ abgeloest — der Beispiel-Alarm ist entfernt
		// (ersetzt durch den Test-Alarm #3441); letzter Abschnitt ist Stille Stunden.
		test('kein Abschnitt zustellung-beispiel-alarm, letzter Abschnitt ist Stille Stunden (#3458)', async () => {
			const h = await reiter(context, context === 'vergleich');
			assert.equal(anzahl(h, 'data-testid="zustellung-beispiel-alarm"'), 0, 'Abschnitt Beispiel-Alarm noch im Reiter');
			assert.doesNotMatch(h, /data-abschnitt="beispiel-alarm"/);
			const reiterHtml = innen(h, 'zustellung-tab');
			pos(reiterHtml, 'data-abschnitt="stille-stunden"');
			const abschnitte = [...reiterHtml.matchAll(/data-abschnitt="([^"]+)"/g)].map((m) => m[1]);
			assert.equal(abschnitte.at(-1), 'stille-stunden', `letzter Abschnitt ist ${abschnitte.at(-1)}`);
		});
	});
}

// #3020 R1 (E071): die Briefing-Zeiten hängen nicht daran, welche Kanäle an sind (Premium-SMS ist ein Kanal wie jeder).
const NUR_PREMIUM = { send_email: false, send_telegram: false, send_sms: false, send_premium_sms: true };
describe('#3020 E071: nur Premium-SMS an, Briefing-Zeiten bleiben bedienbar', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`nur Premium-SMS an: Briefing-Zeiten sichtbar (${context})`, async () => {
			const ZustellungTab = await lade('shared/zustellung-tab/ZustellungTab.svelte');
			const zeiten = { morning_enabled: true, morning_time: '06:45:00', evening_enabled: true, evening_time: '18:15:00' };
			const props = context === 'route'
				? { context, trip: { ...TRIP, report_config: { ...zeiten, ...NUR_PREMIUM } } }
				: { context, preset: { ...PRESET, ...zeiten, ...NUR_PREMIUM } };
			const h = renderKomponente(ZustellungTab, props).replace(/<!--[\s\S]*?-->/g, '');
			assert.equal(anzahl(h, 'data-abschnitt="briefing-zeiten"'), 1, 'Abschnitt Briefing-Zeiten fehlt');
			for (const [slot, zeit] of [['morgen', '06:45'], ['abend', '18:15']] as const) {
				const gezeigt = sichtbarerText(innen(h, `zustellung-${slot}-zeit`)).replace(/\s/g, '');
				assert.ok(gezeigt.includes(zeit), `${slot}: Uhrzeit ${zeit} nicht sichtbar („${gezeigt}“)`);
				assert.equal(anzahl(h, `data-testid="zustellung-${slot}-schalter"`), 1, `${slot}: Schalter fehlt`);
			}
		});
	}
});

describe('#3036 AC-7 Orte: Pausieren/Aktivieren als fester Abschnitt direkt unter dem Kopf', () => {
	test('Hub (Snippet activation): Karte in zustellung-aktivierung, vor den Briefing-Zeiten, genau einmal', async () => {
		const h = await reiter('vergleich', true);
		assert.equal(anzahl(h, 'data-testid="test-aktivierungskarte"'), 1, 'Aktivierungskarte nicht genau einmal');
		assert.equal(anzahl(h, 'data-testid="zustellung-aktivierung"'), 1, 'fester Abschnitt zustellung-aktivierung fehlt');
		assert.ok(innen(h, 'zustellung-aktivierung').includes('data-testid="test-aktivierungskarte"'), 'Karte nicht im Abschnitt zustellung-aktivierung');
		assert.ok(pos(h, 'data-testid="test-aktivierungskarte"') < pos(h, 'data-abschnitt="briefing-zeiten"'),
			'Aktivierungskarte steht nicht vor den Briefing-Zeiten');
	});
	test('ohne Snippet (Trip): kein leerer Aktivierungs-Abschnitt', async () => {
		const h = await reiter('route');
		assert.equal(anzahl(h, 'data-testid="zustellung-aktivierung"'), 0);
	});
	for (const mobil of [false, true]) {
		test(`Anlegen (${mobil ? 'Mobil' : 'Desktop'}): Aktivierungs-Banner vor den Briefing-Zeiten im Reiter`, async () => {
			const html = await renderVergleichNeu({ metrikenVisited: true, zustellungVisited: true, activeTab: 'zustellung', isMobileViewport: mobil });
			const r = innen(html, 'zustellung-tab').replace(/<!--[\s\S]*?-->/g, '');
			assert.equal(anzahl(r, 'data-testid="zustellung-uebergang"'), 0, 'Übergangsblock noch im Anlegen');
			assert.ok(pos(r, 'data-testid="compare-step5-activation-banner"') < pos(r, 'data-abschnitt="briefing-zeiten"'),
				'Aktivierungs-Banner steht nicht vor den Briefing-Zeiten');
		});
	}
});
