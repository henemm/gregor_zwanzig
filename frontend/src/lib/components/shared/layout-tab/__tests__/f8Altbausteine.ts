// Issue #3020 — vom F8-Pruefstand abgetrennter Teil: Render des Ausgabe-Layout-Editors (OutputLayoutEditor,
// Restbestand von #3020 R2). Der Layout-Reiter (LayoutTab, LTCutLine) ist mit #3366 geloescht. Einziger Nutzer:
// layout_korridor_sprache.test.ts, dort nur in den Faellen dieses Editors (dynamischer Import), damit der
// Pruefstand und seine uebrigen Nutzer (GPX-Seite) ohne den Restbestand laden. Faellt mit R2.
// Pfadregel #1409: alles relativ zu DIESER Datei.

import path from 'node:path';
import { html, komp, SHARED } from './f8Pruefstand.ts';

const OutputLayoutEditor = await komp(path.join(SHARED, 'OutputLayoutEditor.svelte'));

/** Metrik-Katalog wie GET /api/metrics (Labels sind API-Daten, nicht Paket-Texte). */
const KATALOG = {
	temperature: [{ id: 'temperature', label: 'Temperatur', unit: '°C', category: 'temperature', default_enabled: true, col_label: 'Temp' }],
	wind: [
		{ id: 'wind', label: 'Wind', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Wind' },
		{ id: 'gust', label: 'Böen', unit: 'km/h', category: 'wind', default_enabled: true, col_label: 'Gust' }
	],
	precipitation: [{ id: 'precipitation', label: 'Niederschlag', unit: 'mm', category: 'precipitation', default_enabled: true, col_label: 'Rain' }]
};
const BUCKETS = { primary: ['temperature', 'wind', 'gust'], secondary: ['precipitation'], off: [] as string[] };
const LEER = { primary: [] as string[], secondary: [] as string[], off: ['temperature'] };

/** Ausgabe-Layout-Editor fuer einen Kanal (Props wie im frueheren Layout-Reiter-Pruefstand). */
export function ausgabeLayoutRendern(channel: 'email' | 'telegram' | 'sms', variante: 'voll' | 'leer' | 'ohne_detail' = 'voll'): string {
	return html(OutputLayoutEditor, {
		catalog: KATALOG,
		buckets: variante === 'leer' ? LEER : BUCKETS,
		friendlyMap: {},
		channel,
		templates: [{ id: 'wandern', label: 'Wandern', metrics: ['temperature', 'wind'] }],
		hideDetailBucket: variante === 'ohne_detail'
	});
}
