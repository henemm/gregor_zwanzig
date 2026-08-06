// TDD RED — Issue #923: Briefing-SMS-Fidelity über Backend-Feed.
// Spec: docs/specs/modules/fix_923_sms_fidelity_backend.md — AC-5 (Frontend-Teil),
// AC-6, AC-7, AC-8.
//
// Echtes serverseitiges Rendern der echten Svelte-Komponenten (svelte/server
// `render`, Hooks: frontend/test-svelte-ssr-hooks.mjs). Keine Mocks der
// Komponenten selbst, keine reine Datei-Inhalt-Prüfung — der HTML-String IST
// hier das geprüfte Verhalten (CLAUDE.md Test-Politik).
//
// `previewOverride`-Prop (RED-Infrastruktur, analog `profileOverride` in
// VTBriefingChannels.svelte / channel_checkbox_dedupe_render.test.ts): beide
// Komponenten laden ihre SMS-Vorschau künftig per `api.post(
// '/api/_validator/sms-fidelity-preview', {metric_ids})` (Muster
// AlertPreviewCard.svelte). `svelte/server`s `render()` führt weder
// `onMount` noch `$effect` aus — ohne Override bliebe die Vorschau in
// SSR-Tests immer leer. Erwartete Prop-Form (von dieser RED-Phase
// festgelegt, Implementierung folgt in /50-implement):
//   previewOverride?: { line: string; char_count: number; max_length: number;
//                        carried_ids: string[] } | null
// Gesetzt (auch explizit `null`) → der Fetch entfällt, die Vorschau wird
// direkt aus der Prop initialisiert. Ohne Übergabe unverändertes Verhalten
// (Fetch bei Mount/Änderung von primary/secondary).
//
// RED heute:
//   - Beide Komponenten kennen `previewOverride` noch nicht → die Prop wird
//     ignoriert, die serverseitige Vorschau bleibt leer/lokal simuliert
//     (`SMS_TOK`/`smsRender`/`smsCounters` existieren noch) → alle
//     Text-Assertions unten schlagen fehl.
//
// Pfadregel #1409: alle Pfade relativ zu DIESER Datei.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/__tests__/channel_sms_fidelity_backend_render.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> trip-detail -> components -> lib -> src -> frontend
const FRONTEND = path.resolve(HERE, '../../../../..');

register(
	pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href,
	pathToFileURL(FRONTEND + '/').href
);

const { render } = await import('svelte/server');
const ChannelFidelitySMS = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-detail/ChannelFidelitySMS.svelte')).href
	)
).default;
const ChannelPreviewCard = (
	await import(
		pathToFileURL(path.join(FRONTEND, 'src/lib/components/trip-detail/ChannelPreviewCard.svelte')).href
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
	wind: metricEntry('wind', 'Wind', 'W'),
	gust: metricEntry('gust', 'Böen', 'G'),
	thunder: metricEntry('thunder', 'Gewitter', 'TH')
};

/** Sichtbarer Text eines SSR-Ergebnisses (Tags + Svelte-Kommentar-Anker raus). */
function visibleText(html: string): string {
	return html
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/<[^>]*>/g, ' ')
		.replace(/\s+/g, ' ')
		.trim();
}

function renderFidelitySms(
	primary: string[],
	secondary: string[],
	previewOverride: SmsFidelityPreview | null
): string {
	return render(ChannelFidelitySMS, {
		props: {
			primary,
			secondary,
			metricById: METRIC_BY_ID,
			previewOverride
		}
	}).body;
}

function renderPreviewCard(
	primary: string[],
	secondary: string[],
	previewOverride: SmsFidelityPreview | null
): string {
	return render(ChannelPreviewCard, {
		props: {
			channelId: 'sms',
			label: 'SMS',
			glyph: '✉',
			maxCols: Infinity,
			primary,
			secondary,
			metricById: METRIC_BY_ID,
			active: false,
			onSelect: () => {},
			previewOverride
		}
	}).body;
}

// ─── AC-6 ────────────────────────────────────────────────────────────────────

describe('AC-6: ChannelFidelitySMS zeigt exakt die vom Server gelieferte line-Zeile', () => {
	test('line-Text erscheint unverändert im DOM, keine eigene Kürzungsberechnung', () => {
		// Bewusst eine "unrealistische" Zeile, die eine clientseitige
		// smsRender()-Neuberechnung (KHW03:-Präfix, Z:WATCH:2447-Anhang,
		// Auswahlreihenfolge-Kürzung) niemals erzeugen würde.
		const preview: SmsFidelityPreview = {
			line: 'Etappe: ??SERVER-ONLY-MARKER?? D99 K-12',
			char_count: 40,
			max_length: 160,
			carried_ids: ['temperature']
		};
		const html = renderFidelitySms(['temperature'], [], preview);
		const text = visibleText(html);

		assert.ok(
			text.includes(preview.line),
			`AC-6: erwarteter Server-Text "${preview.line}" fehlt im gerenderten DOM. Sichtbarer Text: "${text}"`
		);
		assert.ok(
			!text.includes('KHW03:'),
			'AC-6: alter fiktiver Präfix KHW03: darf nicht mehr im DOM erscheinen (Known Limitation, gewollte Korrektur).'
		);
		assert.ok(
			!text.includes('Z:WATCH:2447'),
			'AC-6: alter fiktiver Anhang Z:WATCH:2447 darf nicht mehr im DOM erscheinen.'
		);
	});
});

// ─── AC-5 (Frontend-Teil) ───────────────────────────────────────────────────

describe('AC-5: Zeichenzähler-Anzeige übernimmt char_count/max_length exakt vom Server', () => {
	test('Zeichenzähler zeigt "{char_count}/{max_length} Zeichen" mit Server-Werten ungleich 140', () => {
		const preview: SmsFidelityPreview = {
			line: 'Etappe: D10',
			char_count: 42,
			max_length: 999,
			carried_ids: ['temperature']
		};
		const html = renderFidelitySms(['temperature'], [], preview);
		const text = visibleText(html);

		assert.ok(
			text.includes('42/999'),
			`AC-5: erwarte "42/999" (Server-Werte) im Zeichenzähler, Text: "${text}"`
		);
		assert.ok(
			!text.includes('/140'),
			'AC-5: die alte hartcodierte 140-Zeichen-Grenze darf nicht mehr angezeigt werden.'
		);
	});
});

// ─── AC-7 ────────────────────────────────────────────────────────────────────

describe('AC-7: ChannelPreviewCard leitet "X als Code" / "Y fallen weg" aus carried_ids der Serverantwort ab', () => {
	test('Kachel zeigt X = carried_ids.length und Y = metric_ids.length - carried_ids.length', () => {
		const primary = ['temperature', 'wind'];
		const secondary = ['thunder', 'gust'];
		// carried_ids weicht bewusst von einer plausiblen Eigenberechnung ab:
		// alle vier Metriken haben in METRIC_BY_ID einen sms_code, eine naive
		// Neuberechnung würde alle vier als "carried" zählen. Die
		// Serverantwort lässt zwei fallen (Kürzung/Symbol-Mapping).
		const preview: SmsFidelityPreview = {
			line: 'Etappe: D10 TH5%@12',
			char_count: 20,
			max_length: 160,
			carried_ids: ['temperature', 'thunder']
		};
		const html = renderPreviewCard(primary, secondary, preview);
		const text = visibleText(html);

		assert.ok(
			text.includes('2'),
			`AC-7: erwarte die Zahl 2 (carried_ids.length) im DOM. Text: "${text}"`
		);
		assert.ok(
			text.includes('2 fallen weg'),
			`AC-7: erwarte "2 fallen weg" (4 angefragt - 2 carried) im DOM, aus der Serverantwort abgeleitet — nicht aus einer Eigenberechnung (die bei diesen vier Metriken 0 dropped ergäbe). Text: "${text}"`
		);
	});
});

// ─── AC-8 ────────────────────────────────────────────────────────────────────

describe('AC-8: ChannelFidelitySMS und ChannelPreviewCard stimmen bei identischer Serverantwort überein', () => {
	test('"als Code"-Zahl in ChannelPreviewCard == Länge der "mit SMS-Code"-Liste in ChannelFidelitySMS', () => {
		const primary = ['temperature', 'wind'];
		const secondary = ['thunder', 'gust'];
		const preview: SmsFidelityPreview = {
			line: 'Etappe: D10 TH5%@12',
			char_count: 20,
			max_length: 160,
			carried_ids: ['temperature', 'thunder']
		};

		const fidelityHtml = renderFidelitySms(primary, secondary, preview);
		const cardHtml = renderPreviewCard(primary, secondary, preview);

		const fidelityText = visibleText(fidelityHtml);
		const cardText = visibleText(cardHtml);

		// ChannelFidelitySMS zeigt "✓ {N} mit SMS-Code" — N muss carried_ids.length sein.
		assert.ok(
			fidelityText.includes(`${preview.carried_ids.length} mit SMS-Code`),
			`AC-8: ChannelFidelitySMS zeigt nicht "${preview.carried_ids.length} mit SMS-Code". Text: "${fidelityText}"`
		);
		// ChannelPreviewCard zeigt dieselbe Zahl als "als Code"-Kennzahl.
		assert.ok(
			cardText.includes(String(preview.carried_ids.length)),
			`AC-8: ChannelPreviewCard zeigt nicht die Zahl ${preview.carried_ids.length}. Text: "${cardText}"`
		);
	});
});
