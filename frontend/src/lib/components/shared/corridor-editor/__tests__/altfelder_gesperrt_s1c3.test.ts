// Issue #2792 S1c-3 (AC-22, AC-24) — Altfelder sperren: Wertebereiche (Korridor-
// Zeilen) und SMS-Schwellwert-Regler sind in Trip UND Ortsvergleich nur lesbar,
// zeigen die gespeicherten Werte und den Hinweis (DE/EN). Echte SSR-Renders der
// echten Svelte-Komponenten (Pruefstaende f8Pruefstand.ts / f5Pruefstand.ts),
// kein Mock. Datenerhalt: `sms_threshold` wird beim Speichern nie geleert.
//
// Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md (AC-22, AC-24, Nachtrag S1c-3)
//
//   cd frontend && npm test -- src/lib/components/shared/corridor-editor/__tests__/altfelder_gesperrt_s1c3.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
	locale,
	korridorRendern,
	routeZustand,
	vergleichZustand
} from '../../layout-tab/__tests__/f8Pruefstand.ts';
import { routeRendern } from '../../weather-metrics-tab/__tests__/f5Pruefstand.ts';
import { buildGlobalMetricsForSave } from '../../weather-metrics-tab/weatherMetricsSavePayload.ts';

const HINWEIS = {
	de: 'Wird gerade umgebaut – deine Werte sind übernommen.',
	en: 'Being rebuilt – your values have been carried over.'
} as const;

afterEach(() => locale.set('de'));

const text = (html: string) =>
	html
		.replace(/<style[\s\S]*?<\/style>/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/&amp;/g, '&')
		.replace(/\s+/g, ' ');

/** Alle öffnenden Tags `<tag …>` eines Elementtyps (Attribute vollständig). */
const tags = (html: string, tag: string) => html.match(new RegExp(`<${tag}\\b[^>]*>`, 'g')) ?? [];
const istGesperrt = (t: string) => /\sdisabled(=|\s|>)/.test(t);

const BEDIENELEMENTE = /class="[^"]*\b(?:ce|cem)-(open-btn|ordinal-btn|clear-btn|step-btn|effect|remove|pool-btn)\b/;

type Fall = { name: string; kontext: 'route' | 'vergleich'; fassung: 'desktop' | 'mobil' };
const FAELLE: Fall[] = (['route', 'vergleich'] as const).flatMap((kontext) =>
	(['desktop', 'mobil'] as const).map((fassung) => ({ name: `${kontext}/${fassung}`, kontext, fassung }))
);
const zustandFuer = (k: Fall['kontext']) => (k === 'route' ? routeZustand(false) : vergleichZustand(1));

describe('AC-22: Korridor-Zeilen des Reiters Wertebereiche sind nur lesbar', () => {
	for (const f of FAELLE) {
		test(`${f.name}: alle Zahleneingaben und Bedienknöpfe sind gesperrt (nicht leer geprüft)`, () => {
			const html = korridorRendern(f.kontext, f.fassung, zustandFuer(f.kontext));
			const knoepfe = tags(html, 'button').filter((t) => BEDIENELEMENTE.test(t));
			assert.ok(knoepfe.length >= 4, `Vorbedingung: Bedienknöpfe müssen gerendert sein, gefunden ${knoepfe.length}`);
			const offen = knoepfe.filter((t) => !istGesperrt(t));
			assert.deepEqual(offen, [], `Diese Knöpfe sind noch bedienbar:\n${offen.join('\n')}`);
			if (f.fassung === 'mobil') {
				// Pool-Knöpfe sind in der mobilen Fassung MBtn-Komponenten (kein ce-/cem-Klassenname).
				const poolKnoepfe = html
					.split('data-testid="corridor-editor-pool-item-')
					.slice(1)
					.map((teil) => tags(teil, 'button')[0]);
				assert.ok(poolKnoepfe.length >= 1, 'Vorbedingung: Pool-Knöpfe (Hinzufügen) müssen gerendert sein');
				const offenePool = poolKnoepfe.filter((t) => !t || !istGesperrt(t));
				assert.deepEqual(offenePool, [], `Hinzufügen-Knöpfe noch bedienbar:\n${offenePool.join('\n')}`);
			}
			const eingaben = tags(html, 'input').filter((t) => /type="number"/.test(t));
			if (f.fassung === 'desktop') {
				assert.ok(eingaben.length >= 1, 'Vorbedingung: Zahleneingaben müssen gerendert sein');
			}
			const offeneEingaben = eingaben.filter((t) => !istGesperrt(t));
			assert.deepEqual(offeneEingaben, [], `Diese Eingaben sind noch bedienbar:\n${offeneEingaben.join('\n')}`);
		});

		for (const sprache of ['de', 'en'] as const) {
			test(`${f.name}/${sprache}: Hinweis „${HINWEIS[sprache]}" steht im Reiter`, () => {
				locale.set(sprache);
				const sichtbar = text(korridorRendern(f.kontext, f.fassung, zustandFuer(f.kontext)));
				assert.ok(sichtbar.includes(HINWEIS[sprache]), `Hinweis fehlt (${sprache}) in: ${sichtbar.slice(0, 600)}`);
			});
		}

		test(`${f.name}: gespeicherte Werte bleiben sichtbar`, () => {
			const html = korridorRendern(f.kontext, f.fassung, zustandFuer(f.kontext));
			const erwartet = f.kontext === 'route' ? '70' : '40';
			assert.ok(
				text(html).includes(erwartet) || html.includes(`value="${erwartet}"`),
				`gespeicherter Grenzwert ${erwartet} wird nicht angezeigt`
			);
		});
	}
});

describe('AC-22: SMS-Schwellwert-Regler im Reiter Wetter sind nur lesbar', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`Trip/${sprache}: alle Stufen-Knöpfe gesperrt, Hinweis im SMS-Block`, () => {
			locale.set(sprache);
			const html = routeRendern();
			const knoepfe = tags(html, 'button').filter((t) => /data-testid="threshold-level-/.test(t));
			assert.ok(knoepfe.length >= 6, `Vorbedingung: Regler-Knöpfe müssen gerendert sein, gefunden ${knoepfe.length}`);
			const offen = knoepfe.filter((t) => !istGesperrt(t));
			assert.deepEqual(offen, [], `Diese Regler-Knöpfe sind noch bedienbar:\n${offen.join('\n')}`);
			const start = html.indexOf('data-testid="sms-thresholds"');
			assert.ok(start > 0, 'SMS-Schwellwert-Block fehlt');
			const block = text(html.slice(Math.max(0, start - 900), html.indexOf('</table>', start)));
			assert.ok(block.includes(HINWEIS[sprache]), `Hinweis fehlt im SMS-Block (${sprache}): ${block.slice(-500)}`);
		});
	}

	test('Trip: der gespeicherte Stufenwert bleibt angezeigt (Wertzelle vorhanden)', () => {
		const html = routeRendern();
		assert.ok(/data-testid="threshold-value-wind"/.test(html), 'Wertzelle der Wind-Schwelle fehlt');
	});
});

describe('AC-24: sms_threshold geht beim Speichern nie verloren', () => {
	const katalog = {
		temperature: [{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'temperature', default_enabled: true, has_friendly_format: false }]
	};
	const buckets = { primary: ['wind'], secondary: [], off: [] };

	test('Bestand 42 + leerer Regler-Zustand → gespeichert wird 42', () => {
		const out = buildGlobalMetricsForSave(
			{ metrics: [{ metric_id: 'wind', sms_threshold: 42 } as unknown as { metric_id: string }] },
			buckets, {}, {}, katalog, {}, ['wind']
		);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind.sms_threshold, 42);
	});

	test('Bestand 42 + leerer String → gespeichert wird 42', () => {
		const out = buildGlobalMetricsForSave(
			{ metrics: [{ metric_id: 'wind', sms_threshold: 42 } as unknown as { metric_id: string }] },
			buckets, {}, {}, katalog, { wind: '' }, ['wind']
		);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal(wind.sms_threshold, 42);
	});

	test('Metrik ohne Bestandswert bekommt keinen erfundenen sms_threshold', () => {
		const out = buildGlobalMetricsForSave({ metrics: [{ metric_id: 'wind' }] }, buckets, {}, {}, katalog, {}, ['wind']);
		const wind = out.find((m) => m.metric_id === 'wind') as unknown as Record<string, unknown>;
		assert.equal('sms_threshold' in wind && wind.sms_threshold !== undefined, false);
	});
});
