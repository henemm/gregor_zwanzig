// Issue #2792 S1c-3 (AC-22, AC-24) — Altfelder sperren: die SMS-Schwellwert-Regler
// sind nur lesbar, zeigen die gespeicherten Werte und den Hinweis (DE/EN). Echter
// SSR-Render der echten Svelte-Komponente (Pruefstand f5Pruefstand.ts), kein Mock.
// Datenerhalt: `sms_threshold` wird beim Speichern nie geleert.
//
// #2794 S3a Teil-PR 4a (AC-31): die Faelle zu den Korridor-Zeilen des alten Reiters
// Wertebereiche (CorridorEditor/CorridorEditorMobile) sind mit der Oberflaeche
// entfernt; die Datei zog aus shared/corridor-editor/__tests__/ hierher, weil die
// bleibenden Faelle den Wetter-Metriken-Baustein (SMS-Schwellen) pruefen.
//
// Spec: docs/specs/modules/feat_2792_s1_profil_ampel.md (AC-22, AC-24, Nachtrag S1c-3)
//
//   cd frontend && npm test -- src/lib/components/shared/weather-metrics-tab/__tests__/altfelder_gesperrt_s1c3.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, routeRendern } from './f5Pruefstand.ts';
import { buildGlobalMetricsForSave } from '../weatherMetricsSavePayload.ts';

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
