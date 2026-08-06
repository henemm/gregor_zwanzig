// TDD RED — Fix #923b: SMS-Fidelity-Vorschau an die live gerenderte
// Komponente WeatherV2MailPreview.svelte anschließen.
// Spec: docs/specs/modules/fix_923b_wire_live_sms_preview.md — AC-1, AC-2, AC-3.
//
// #923 verdrahtete den Backend-Endpoint gegen tote Komponenten
// (ChannelFidelitySMS.svelte u. a.) — die Trip-Editor-Route rendert
// tatsächlich WeatherV2MailPreview.svelte, die weiterhin ihre eigene,
// veraltete SMS-Simulation (SMS_TOK-Dict, 140-Zeichen-Limit, Z:WATCH-Anhang)
// zeigt. Migriert die Kernassertionen aus dem (in der GREEN-Phase zu
// löschenden) trip-detail/__tests__/channel_sms_fidelity_backend_render.test.ts.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponente (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks der
// Komponente selbst, keine reine Datei-Inhalt-Prüfung — der HTML-String IST
// hier das geprüfte Verhalten (CLAUDE.md Test-Politik).
//
// `previewOverride`-Prop (RED-Infrastruktur, analog `profileOverride` in
// VTBriefingChannels.svelte): svelte/server's render() führt weder onMount
// noch $effect aus — ohne Override bliebe die Vorschau in SSR-Tests immer
// leer/lokal simuliert. Erwartete Prop-Form (von dieser RED-Phase
// festgelegt, Implementierung folgt in /50-implement):
//   previewOverride?: { line: string; char_count: number; max_length: number;
//                        carried_ids: string[] } | null
//   context?: 'route' | 'vergleich' (Default 'route')
//
// RED heute:
//   - WeatherV2MailPreview.svelte kennt weder `context` noch `previewOverride`
//     → beide Props werden ignoriert, die Komponente zeigt weiterhin die
//     eigene SMS_TOK-Simulation mit hartcodiertem /140-Zähler und rendert
//     die SMS-Kachel auch bei context='vergleich' → alle Assertions unten
//     schlagen fehl.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/shared/weather-metrics-tab/__tests__/weather_v2_mail_preview_sms_fidelity.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> weather-metrics-tab -> shared -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const WeatherV2MailPreview = (
	await import(
		pathToFileURL(
			path.join(FRONTEND, 'src/lib/components/shared/weather-metrics-tab/WeatherV2MailPreview.svelte')
		).href
	)
).default;

interface MetricEntry {
	id: string;
	label: string;
	unit: string;
	category: string;
	default_enabled: boolean;
	has_friendly_format: boolean;
	sms_code?: string;
}

interface SmsFidelityPreview {
	line: string;
	char_count: number;
	max_length: number;
	carried_ids: string[];
}

function metricEntry(id: string, label: string, sms_code: string): MetricEntry {
	return {
		id,
		label,
		unit: '',
		category: 'weather',
		default_enabled: true,
		has_friendly_format: false,
		sms_code
	};
}

const METRIC_BY_ID: Record<string, MetricEntry> = {
	temperature: metricEntry('temperature', 'Temperatur', 'D'),
	wind: metricEntry('wind', 'Wind', 'W')
};

/** Sichtbarer Text eines SSR-Ergebnisses (Tags + Svelte-Kommentar-Anker raus). */
function visibleText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function renderPreview(
	channel: 'email' | 'telegram' | 'sms',
	previewOverride: SmsFidelityPreview | null,
	context?: 'route' | 'vergleich'
): string {
	return render(WeatherV2MailPreview, {
		props: {
			primaryColumns: ['temperature', 'wind'],
			metricById: METRIC_BY_ID,
			friendlyMap: {},
			telegramKurzform: false,
			highlight: null,
			channel,
			previewOverride,
			...(context !== undefined ? { context } : {})
		}
	}).body;
}

// ─── AC-1 ────────────────────────────────────────────────────────────────────

describe('AC-1: SMS-Kachel zeigt exakt die vom Server gelieferte line-Zeile', () => {
	test('line-Text erscheint unverändert im DOM, keine eigene SMS_TOK-Neuberechnung', () => {
		// Bewusst eine "unrealistische" Zeile, die die alte lokale Simulation
		// (SMS_TOK-Präfix "BSPTOUR:", Z:WATCH-Anhang) niemals erzeugen würde.
		const preview: SmsFidelityPreview = {
			line: 'Etappe: ??SERVER-ONLY-MARKER?? D99 K-12',
			char_count: 40,
			max_length: 160,
			carried_ids: ['temperature']
		};
		const html = renderPreview('sms', preview, 'route');
		const text = visibleText(html);

		assert.ok(
			text.includes(preview.line),
			`AC-1: erwarteter Server-Text "${preview.line}" fehlt im gerenderten DOM. Sichtbarer Text: "${text}"`
		);
		assert.ok(
			!text.includes('BSPTOUR:'),
			'AC-1: alter fiktiver Präfix BSPTOUR: darf nicht mehr im DOM erscheinen (alte lokale Simulation).'
		);
		assert.ok(
			!text.includes('Z:WATCH'),
			'AC-1: alter fiktiver Anhang Z:WATCH darf nicht mehr im DOM erscheinen.'
		);
	});
});

// ─── AC-2 ────────────────────────────────────────────────────────────────────

describe('AC-2: Zeichenzähler-Anzeige übernimmt char_count/max_length exakt vom Server', () => {
	test('Zeichenzähler zeigt "{char_count}/{max_length} Zeichen" mit Server-Werten ungleich 140', () => {
		const preview: SmsFidelityPreview = {
			line: 'Etappe: D10',
			char_count: 42,
			max_length: 160,
			carried_ids: ['temperature']
		};
		const html = renderPreview('sms', preview, 'route');
		const text = visibleText(html);

		assert.ok(
			text.includes('42/160'),
			`AC-2: erwarte "42/160" (Server-Werte) im Zeichenzähler, Text: "${text}"`
		);
		assert.ok(
			!text.includes('/140'),
			'AC-2: die alte hartcodierte 140-Zeichen-Grenze darf nicht mehr angezeigt werden.'
		);
	});
});

// ─── AC-3 ────────────────────────────────────────────────────────────────────

describe('AC-3: context="vergleich" blendet die SMS-Kachel vollständig aus', () => {
	test('data-testid="wm2-sms-line" fehlt komplett im DOM, unabhängig vom channel-Prop', () => {
		const preview: SmsFidelityPreview = {
			line: 'Etappe: D10',
			char_count: 42,
			max_length: 160,
			carried_ids: ['temperature']
		};
		const html = renderPreview('sms', preview, 'vergleich');

		assert.ok(
			!html.includes('data-testid="wm2-sms-line"'),
			`AC-3: die SMS-Kachel darf bei context='vergleich' nicht gerendert werden. HTML: "${html}"`
		);
	});
});

// ─── Mutations-taugliche Gegenprobe ────────────────────────────────────────

describe('Gegenprobe: Komponente zeigt den übergebenen Serverwert 1:1, keine lokale Simulation', () => {
	test('eine zweite, abweichende previewOverride-Zeile kommt unverändert im DOM an', () => {
		const previewA: SmsFidelityPreview = {
			line: 'Etappe: MARKER-EINS',
			char_count: 20,
			max_length: 160,
			carried_ids: ['temperature']
		};
		const previewB: SmsFidelityPreview = {
			line: 'Etappe: MARKER-ZWEI',
			char_count: 21,
			max_length: 160,
			carried_ids: ['temperature']
		};

		const textA = visibleText(renderPreview('sms', previewA, 'route'));
		const textB = visibleText(renderPreview('sms', previewB, 'route'));

		assert.ok(textA.includes(previewA.line), `Gegenprobe: "${previewA.line}" fehlt in Text A: "${textA}"`);
		assert.ok(textB.includes(previewB.line), `Gegenprobe: "${previewB.line}" fehlt in Text B: "${textB}"`);
		assert.ok(
			!textA.includes(previewB.line) && !textB.includes(previewA.line),
			'Gegenprobe: beide Renders dürfen sich nicht gegenseitig durchmischen — jede Zeile ist eindeutig ihrem previewOverride zuzuordnen.'
		);
	});
});
