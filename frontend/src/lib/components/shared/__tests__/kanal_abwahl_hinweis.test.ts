// TDD RED — Issue #2438 (S2b von #2422, Epic #2507): Editor-Hinweis
// „Kanal kann nur abwählen" (B6, ADR-0050 Regel 1–3).
//
// Spec: docs/specs/modules/feat_2438_kanal_abwahl_hinweis.md
//   AC-3  leere Aus-Gruppe zeigt den Hinweis trotzdem
//   AC-4  globale Grundauswahl-Ansicht (ohne `offColumns`) zeigt ihn NICHT
//   AC-6  exakter Wortlaut, nur Regelbeschreibung (keine Handlungsempfehlung)
//   AC-7  Aus-Zeile + Wiederherstellen bleiben unverändert (befüllte Gruppe)
//
// Gerendert wird der ECHTE Baustein serverseitig (svelte/server) — kein Mock.
// `ltKanalAbwahlHinweisText` und der Hinweis werden NUR dynamisch importiert,
// damit ein (in RED) fehlender Export jeden Test einzeln rot macht statt die
// Datei mit einem Ladefehler zu kippen.
//
// Verdrahtung: die Einbettungen in WeatherMetricsTab.svelte werden per AST
// belegt, NICHT per SSR. Grund: der Metrik-Katalog lädt dort per $effect, und
// der läuft unter svelte/server nie — der Baustein bliebe im Ladezustand, ein
// SSR-Test sähe die Einbettung nie. Muster und Eingrenzung (Start-Offset
// vergleich- vs. route-Zweig) wie in
// weather_metrics_tab_vergleich_uebersicht_kanal_tabs.test.ts: reines Parsen
// mit dem echten Svelte-Compiler, kein Quelltext-String-Check.
//
// Ausführen:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/__tests__/kanal_abwahl_hinweis.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { parse } from 'svelte/compiler';
// registriert die Runen-/.svelte-Hooks (Nebenwirkung des Imports)
import '../../trip-new/__tests__/tripNewSsr.ts';

const here = dirname(fileURLToPath(import.meta.url));
const WORTLAUT =
	'Ein Kanal zeigt höchstens, was in der Grundauswahl gewählt ist. Was dort fehlt, erscheint in keinem Kanal.';

async function hinweisText(): Promise<string> {
	const mod: any = await import(
		pathToFileURL(join(here, '..', 'layout-tab', 'ltChannels.ts')).href
	);
	assert.equal(
		typeof mod.ltKanalAbwahlHinweisText,
		'function',
		'ltChannels.ts muss ltKanalAbwahlHinweisText() exportieren'
	);
	return mod.ltKanalAbwahlHinweisText();
}

async function rendere(
	offColumns?: string[],
	kanal: string = 'email',
	showAbwahlHinweis?: boolean
): Promise<string> {
	const { render } = await import('svelte/server');
	const comp: any = (
		await import(
			pathToFileURL(join(here, '..', 'weather-metrics-tab', 'WeatherV2Reihenfolge.svelte')).href
		)
	).default;
	const metricById: Record<string, any> = {
		temperature: { id: 'temperature', label: 'Temperatur', unit: '°C' },
		wind: { id: 'wind', label: 'Wind', unit: 'km/h' }
	};
	const props: Record<string, unknown> = {
		primaryColumns: ['temperature'],
		metricById,
		friendlyMap: {},
		activeChannel: kanal,
		highlight: null,
		onRemove: () => {},
		onDndReorder: () => {},
		onMode: () => {},
		kuerzelById: {}
	};
	if (offColumns !== undefined) {
		props.offColumns = offColumns;
		props.onRestore = () => {};
	}
	if (showAbwahlHinweis !== undefined) props.showAbwahlHinweis = showAbwahlHinweis;
	return render(comp, { props }).body;
}

describe('#2438 Kanal-Abwahl-Hinweis', () => {
	test('AC-6: exakter Wortlaut, keine Handlungsempfehlung', async () => {
		const t = await hinweisText();
		assert.equal(t, WORTLAUT);
		assert.doesNotMatch(t, /\b(solltest|sollte|bitte|wähle|aktiviere|schalte)\b/i);
	});

	// #3297/#3020: Render- und Verdrahtungsfaelle von weather-metrics-tab/WeatherV2Reihenfolge,
	// OutlookLayoutControls und WeatherMetricsTab entfallen (Dateien geloescht); es bleibt der Hinweistext.


	for (const kanal of ['telegram', 'sms']) {
	}


	// Fix #2438 (fix_2438_hinweis_nur_kanal_block): Opt-in, Default aus.

});

// ── Verdrahtung: Opt-in `showAbwahlHinweis` nur an den Kanal-Block-Einbettungen ──
const SHARED_FILE = join(here, '..', 'WeatherMetricsTab.svelte');
const OUTLOOK_FILE = join(here, '..', 'OutlookLayoutControls.svelte');
// Issue #3276: CompareHourlyLayoutControls.svelte ist geloescht (Stundenverlauf nur in „Was steht wo").

function findAttr(node: any, name: string): any {
	return (node?.attributes ?? []).find((a: any) => a.type === 'Attribute' && a.name === name);
}

function findComponentsNamed(subtree: unknown, name: string): any[] {
	const found: any[] = [];
	function visit(node: unknown): void {
		if (node === null || typeof node !== 'object') return;
		if (Array.isArray(node)) {
			node.forEach(visit);
			return;
		}
		const n = node as Record<string, any>;
		if (n.type === 'Component' && n.name === name) found.push(n);
		for (const key of Object.keys(n)) {
			if (key === 'parent') continue;
			visit(n[key]);
		}
	}
	visit(subtree);
	return found;
}

/** Der EINE WeatherV2Reihenfolge-Aufruf im vergleich- bzw. route-Zweig. */
function einbettung(zweig: 'vergleich' | 'route'): any {
	const code = readFileSync(SHARED_FILE, 'utf-8');
	const markupStart = code.indexOf("{#if context === 'vergleich'}");
	const routeStart = code.indexOf('\n{:else}', markupStart);
	assert.ok(
		markupStart > 0 && routeStart > markupStart,
		'Markup-Verzweigung nicht gefunden — Test ist blind geworden.'
	);
	const alle = findComponentsNamed(parse(code, { modern: true }).fragment, 'WeatherV2Reihenfolge');
	const treffer = alle.filter((n) =>
		zweig === 'vergleich' ? n.start >= markupStart && n.start < routeStart : n.start >= routeStart
	);
	assert.equal(
		treffer.length,
		1,
		`Erwartet genau einen WeatherV2Reihenfolge-Aufruf im ${zweig}-Zweig, gefunden ${treffer.length} — Test ist blind geworden.`
	);
	return treffer[0];
}

