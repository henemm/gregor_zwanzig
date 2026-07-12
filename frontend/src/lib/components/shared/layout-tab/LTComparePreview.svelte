<script lang="ts">
	// LTComparePreview — Issue #1232 Scheibe 3a: neutrale Orts-Vergleich-Vorschau
	// des LayoutTab-Organism (context="vergleich"). Ersetzt compare/LayoutPreview.svelte
	// vollständig.
	//
	// Design-Prinzip C1 (PO 2026-07-08): der Orts-Vergleich ist neutral — KEIN
	// Rang, KEIN Score, KEIN Empfehlungs-Banner. Kernunterschied zum ersetzten
	// Bestand: Orte als SPALTEN statt als Zeilen, Werte im Idealbereich grün.
	//
	// Datenquelle: statische Demo-Zeilen (KL-3, kein API-Call) via
	// selectPreviewRows(pickedIds, DUMMY_LOCATIONS) — unveraendert aus dem
	// ersetzten Bestand uebernommen (Crash-Guard #1093).
	//
	// Adversary F002/F003 (Fix-Runde): (a) der Footer zaehlt die ECHTE
	// Orts-/Spaltenzahl (pickedIds.length), nicht die demo-gekappte
	// rows.length — die Demo-Tabelle zeigt weiterhin max. 3 Beispiel-Orte
	// (DUMMY_LOCATIONS.length), formuliert das aber transparent, wenn die
	// echte Auswahl groesser ist. (b) Gruenfaerbung liest die echten
	// wizard.idealRanges (Step 3) ueber ltIdealRange.isIdealGood — fehlt fuer
	// eine Metrik ein Range, faellt sie auf die bisherigen JSX-Demo-
	// Schwellen zurueck (siehe ltIdealRange.ts).
	//
	// Design-Quelle (1:1): claude-code-handoff/current/jsx/layout-tab.jsx (LT_ComparePreview)
	// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §4)

	import { Eyebrow } from '$lib/components/atoms';
	import { selectPreviewRows } from '../../compare/layoutPreviewRows.js';
	import { CHANNEL_COL_BUDGET } from '$lib/components/trip-detail/metricsEditor';
	import { isIdealGood, type IdealRangeLite } from './ltIdealRange';
	import type { ChannelId } from './ltChannels';

	interface Props {
		channel: ChannelId;
		pickedIds: string[];
		/** wizard.idealRanges (Step 3) — Key = compareMetricDefs-Metrik-Key. */
		idealRanges?: Record<string, IdealRangeLite>;
	}
	let { channel, pickedIds, idealRanges = {} }: Props = $props();

	interface DummyLocation {
		id: string;
		name: string;
		snow: number;
		newSnow: number;
		wind: number;
		gust: number;
		dir: string;
		feels: number;
		sun: number;
	}

	// 1:1 aus compare/LayoutPreview.svelte (Bestand) uebernommen.
	const DUMMY_LOCATIONS: DummyLocation[] = [
		{ id: 'loc-01', name: 'Hintertux', snow: 180, newSnow: 22, wind: 18, gust: 31, dir: 'NW', feels: -3, sun: 4.5 },
		{ id: 'loc-07', name: 'Ischgl', snow: 140, newSnow: 12, wind: 24, gust: 40, dir: 'W', feels: -5, sun: 2.1 },
		{ id: 'loc-08', name: 'Zermatt', snow: 210, newSnow: 8, wind: 31, gust: 55, dir: 'SW', feels: -7, sun: 5.8 }
	];

	// Crash-Guard #1093: selectPreviewRows gibt bei pickedIds.length===0 alle
	// Dummy-Zeilen zurück (unveraendert). Der explizite Empty-State-Zweig unten
	// greift VOR diesem Aufruf — zusätzliche Absicherung darüber (KL-3).
	const rows = $derived(
		pickedIds.length === 0 ? [] : selectPreviewRows(pickedIds, DUMMY_LOCATIONS).slice(0, 4)
	);

	// Metrik-Key-Mapping auf compareMetricDefs.ts (Adversary F003) — verifiziert
	// gegen die dortigen kanonischen Keys. "Temp gef." (gefühlte Temperatur)
	// hat KEINE Entsprechung in compareMetricDefs (nur temp_max_c = rohe
	// Tageshöchsttemperatur, semantisch verschieden) — metricKey bleibt null,
	// diese Zeile nutzt daher immer die JSX-Demo-Schwelle statt einer falschen
	// Zuordnung.
	interface MetricRow {
		label: string;
		metricKey: string | null;
		value: (r: DummyLocation) => number;
		fmt: (r: DummyLocation) => string;
		fallbackGood: (v: number) => boolean;
	}
	const metricRows = $derived.by((): MetricRow[] => {
		const base: MetricRow[] = [
			{
				label: 'Schnee',
				metricKey: 'snow_depth_cm',
				value: (r) => r.snow,
				fmt: (r) => `${r.snow} cm`,
				fallbackGood: (v) => v >= 80
			},
			{
				label: 'Neuschnee',
				metricKey: 'snow_new_sum_cm',
				value: (r) => r.newSnow,
				fmt: (r) => `+${r.newSnow}`,
				fallbackGood: (v) => v >= 10
			},
			{
				// Adversary F005: wind_max_kmh ist laut compareMetricDefs.ts
				// "Windspitzen" (Böen-Peak), nicht Dauerwind — der Ideal-Check
				// muss daher r.gust auswerten (Zelle zeigt weiter wind/gust
				// kombiniert). Sonst wuerde z. B. Zermatt (wind=31/gust=55) bei
				// Range max=40 faelschlich gruen markiert.
				label: 'Wind/Böen',
				metricKey: 'wind_max_kmh',
				value: (r) => r.gust,
				fmt: (r) => `${r.wind}/${r.gust} ${r.dir}`,
				fallbackGood: (v) => v <= 30
			},
			{
				label: 'Temp gef.',
				metricKey: null,
				value: (r) => r.feels,
				fmt: (r) => `${r.feels >= 0 ? '+' : ''}${r.feels}°`,
				fallbackGood: (v) => v >= -8 && v <= 2
			}
		];
		if (channel === 'email') {
			base.push({
				label: 'Sonne',
				metricKey: 'sunny_hours_h',
				value: (r) => r.sun,
				fmt: (r) => `~${r.sun} h`,
				fallbackGood: (v) => v >= 3
			});
		}
		return base;
	});

	function metricRowGood(m: MetricRow, r: DummyLocation): boolean {
		const range = m.metricKey ? idealRanges[m.metricKey] : undefined;
		return isIdealGood(m.value(r), range, m.fallbackGood);
	}

	// F002: Footer zaehlt die ECHTE Orts-/Spaltenzahl (pickedIds.length), nicht
	// die demo-gekappte rows.length (max. DUMMY_LOCATIONS.length = 3 Beispiele).
	const realOrteCount = $derived(pickedIds.length);
	const orteCols = $derived(realOrteCount + 1);
	const demoNote = $derived(
		rows.length < realOrteCount ? ` · Ansicht zeigt ${rows.length} Beispiel-Orte` : ''
	);

	const smsBody = $derived.by(() => {
		const parts = rows
			.slice(0, 3)
			.map((r) => `${r.name} ${r.snow}cm +${r.newSnow} ${r.feels >= 0 ? '+' : ''}${r.feels}°`);
		return `GZ Fr–So: ${parts.join(' · ')}`;
	});
</script>

<div data-testid="compare-step4-layout-preview" class="lt-compare-preview">
	{#if pickedIds.length === 0}
		<div class="lt-empty-state">Keine Orte ausgewählt — zurück zu „Orte".</div>
	{:else if channel === 'sms'}
		<div class="lt-sms-branch">
			<Eyebrow style="margin-bottom: 10px;">SMS · ≤ 140 Z.</Eyebrow>
			<div data-testid="compare-step4-preview-sms" class="lt-sms-block mono">{smsBody}</div>
			<div class="mono lt-sms-hint">
				{smsBody.length} Zeichen · keine Tabelle — alle Orte nacheinander, ohne Rangfolge.
			</div>
		</div>
	{:else}
		<div class="lt-table-branch">
			<div class="lt-preview-header">
				<Eyebrow style="margin-bottom: 4px;">Übersicht · Fr 12. – So 14.06.</Eyebrow>
				<div class="lt-preview-note">
					Werte nebeneinander — <span class="lt-good-label">grün</span> = in deinem Idealbereich. Kein
					Ranking.
				</div>
			</div>
			<div class="lt-table-wrap">
				<table>
					<thead>
						<tr>
							<th class="lt-th-metric">Metrik</th>
							{#each rows as r (r.id)}
								<th class="lt-th-ort">{r.name}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each metricRows as m (m.label)}
							<tr>
								<td class="lt-td-metric">{m.label}</td>
								{#each rows as r (r.id)}
									<td class="lt-td-value" class:lt-good-cell={metricRowGood(m, r)}>{m.fmt(r)}</td>
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<div class="mono lt-table-footer">
				{channel === 'email'
					? 'Email · alle Metrik-Zeilen + Stunden je Ort'
					: `Telegram · Label + ${realOrteCount} Orte = ${orteCols} Spalten (max ${CHANNEL_COL_BUDGET.telegram})${demoNote}`}
			</div>
		</div>
	{/if}
</div>

<style>
	.lt-compare-preview {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		overflow: hidden;
	}
	.lt-empty-state {
		padding: 40px 20px;
		border: 1px dashed var(--g-rule);
		border-radius: var(--g-r-3, 10px);
		text-align: center;
		color: var(--g-ink-4);
		font-size: 13px;
	}
	.lt-sms-branch {
		padding: 18px;
	}
	.lt-sms-block {
		padding: 12px 14px;
		background: var(--g-paper-deep);
		border-radius: var(--g-r-2, 6px);
		font-size: 12.5px;
		line-height: 1.5;
		color: var(--g-ink);
	}
	.lt-sms-hint {
		margin-top: 8px;
		font-size: 10px;
		color: var(--g-ink-4);
	}
	.lt-preview-header {
		padding: 14px 16px;
		border-bottom: 1px solid var(--g-rule-soft);
		background: var(--g-card-alt);
	}
	.lt-preview-note {
		font-size: 12px;
		color: var(--g-ink-2);
		line-height: 1.5;
	}
	.lt-good-label {
		color: var(--g-good);
		font-weight: 600;
	}
	.lt-table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-family: var(--g-font-mono);
		font-variant-numeric: tabular-nums;
	}
	th {
		padding: 8px 8px;
		text-align: center;
		font-size: 10px;
		color: var(--g-ink);
		font-weight: 600;
		font-family: var(--g-font-sans);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.lt-th-metric {
		text-align: left;
		padding-left: 12px;
		font-size: 9.5px;
		color: var(--g-ink-4);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		font-family: var(--g-font-mono);
	}
	td {
		padding: 8px;
		font-size: 11.5px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.lt-td-metric {
		padding-left: 12px;
		font-family: var(--g-font-sans);
		font-weight: 500;
		font-size: 11px;
		color: var(--g-ink-3);
	}
	.lt-td-value {
		text-align: center;
		font-weight: 500;
		color: var(--g-ink);
	}
	.lt-good-cell {
		color: var(--g-good);
		font-weight: 700;
	}
	.lt-table-footer {
		padding: 8px 14px;
		background: var(--g-paper-deep);
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.04em;
	}
</style>
