// Issue #3020 S1 — vom F9-Pruefstand abgetrennter Teil: Renders der Alt-Bausteine, die kein Nutzer mehr sieht
// (Ausgabe-Layout-Bausteine, Scheibe S2; BriefingScheduleTab, Scheibe S3). Einziger Nutzer:
// trip_hub_sprache.test.ts, dort nur in den Faellen dieser Bausteine (dynamischer Import). Faellt mit ihnen.
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { html, komp, variante, td, nix, tr, tripLaufend, KATALOG } from './f9Pruefstand.ts';

const K = {
	ReportLine: await komp(td('ReportLine.svelte')),
	BucketSection: await komp(td('BucketSection.svelte')),
	BucketSectionOff: await komp(td('BucketSectionOff.svelte')),
	BucketSectionOffOffen: await variante(td('BucketSectionOff.svelte'), [['let open = $state(false);', 'let open = $state(true);']]),
	ActiveMetricRow: await komp(td('ActiveMetricRow.svelte')),
	ChannelLimitMarkers: await komp(td('ChannelLimitMarkers.svelte')),
	PresetRow: await komp(td('PresetRow.svelte')),
	TablePreview: await komp(td('TablePreview.svelte')),
	WeatherV2Kanaele: await komp(td('WeatherV2Kanaele.svelte')),
	BriefingScheduleStatus: await variante(td('BriefingScheduleTab.svelte'), [["let statusMsg = $state('');", "let statusMsg = $state('Gespeichert.');"]])
};
const ZeitplanFehler = await variante(td('BriefingScheduleTab.svelte'), [['let statusKey = $state<MessageKey | null>(null);', "let statusKey = $state<MessageKey | null>('trip.fehler_speichern');"]]);

const metricById = Object.fromEntries(Object.values(KATALOG).flat().map((m) => [m.id, m]));
const ACHT = ['temperature', 'wind', 'gust', 'cloud_total', 'temperature', 'wind', 'gust', 'cloud_total', 'wind'];

export function layoutRendern(): string {
	const viele = Array.from({ length: 9 }, (_, i) => `m${i}`);
	const vieleById = Object.fromEntries(viele.map((id, i) => [id, { ...metricById[ACHT[i]], id }]));
	const base = { metricById: vieleById, shortById: {}, friendlyMap: {}, indicatorCapable: (id: string) => id === 'm1', onMode: nix, onMove: nix, onDndReorder: nix };
	return [
		// Ueberschriften reicht der Aufrufer (OutputLayoutEditor, F8) aus seinem Katalog herein.
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.spalten_eyebrow'), title: tr('layout.ausgabe.spalten'), hint: 'h', bucket: 'primary', items: viele, showLimitMarkers: true }),
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.detail_eyebrow'), title: tr('layout.ausgabe.detail_werte'), hint: 'h', bucket: 'secondary', items: [] }),
		html(K.BucketSection, { ...base, eyebrow: tr('layout.ausgabe.detail_eyebrow'), title: tr('layout.ausgabe.detail_werte'), hint: 'h', bucket: 'secondary', items: ['m0', 'm1'] }),
		html(K.BucketSectionOffOffen, { items: ['temperature', 'gust', 'cloud_total'], metricById, shortById: { gust: 'G' }, categoryLabels: { temperature: 'Temperatur', wind: 'Wind', atmosphere: 'Atmosphäre' }, categoryOrder: ['temperature', 'wind', 'atmosphere'], onAdd: nix }),
		html(K.BucketSectionOffOffen, { items: ['gust'], metricById, shortById: {}, categoryLabels: {}, categoryOrder: [], onAdd: nix, hideDetailButton: true }),
		html(K.BucketSectionOff, { items: ['gust'], metricById, shortById: {}, categoryLabels: {}, categoryOrder: [], onAdd: nix }),
		html(K.ChannelLimitMarkers, { count: 9 }),
		html(K.PresetRow, { id: 'wandern', label: 'Wandern', metricCount: 6, isActive: true, onSelect: nix }),
		html(K.PresetRow, { id: 'eins', label: 'Eins', metricCount: 1, isActive: false, onSelect: nix }),
		html(K.TablePreview, { catalog: KATALOG, enabledMap: { temperature: true, gust: true }, friendlyMap: { gust: true }, horizonsMap: { gust: { today: true, tomorrow: false, day_after: false }, temperature: { today: true, tomorrow: false, day_after: false } }, categoryOrder: ['temperature', 'wind'], indicatorCapable: (id: string) => id === 'gust' }),
		html(K.WeatherV2Kanaele, { channels: { email: true, telegram: true, sms: true }, primaryCount: 10, telegramKurzform: true, onChange: nix, onKurzformChange: nix, availability: { email: true, telegram: true, sms: false } }),
		...(['morning', 'evening', 'alert'] as const).map((kind) => html(K.ReportLine, { kind, time: '07:00', channels: ['email', 'telegram'], active: true, alert: kind === 'alert' })),
		html(K.BriefingScheduleStatus, { trip: tripLaufend() })
	].join('\n');
}

/** Fehler ohne Server-Text: der Zeitplan-Reiter haelt nur den Schluessel (trip.fehler_speichern). */
export const zeitplanFehlerRendern = (): string => html(ZeitplanFehler, { trip: tripLaufend() });

/** Golden-Faelle der Alt-Bausteine (zusaetzlich zu `htmlFaelle()` des Pruefstands). */
export const altFaelle = (): Record<string, () => string> => ({ layout_bausteine: layoutRendern });
