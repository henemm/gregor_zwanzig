<script lang="ts">
	// Issue #846 — Alert-Preset-Selektor.
	// Ersetzt die manuelle Schwellwert-Tabelle im Alerts-Tab durch ein einfaches Dropdown.
	// Spec: docs/specs/modules/issue_846_alert_preset.md §B.

	import type { PresetName } from './alertMetricTable.ts';

	import { t } from '$lib/i18n';
	import type { MessageKey } from '$lib/i18n';

	// Schwellwert-Popover-Daten: 13 Metriken × 3 Presets. Issue #2656 (F7): die
	// Zeilennamen sind Katalogschluessel (`alarme.preset.zeile.<id>`) — ihr
	// deutscher Wortlaut weicht teils von ALERT_METRIC_LABELS ab („Tiefsttemperatur")
	// und bleibt byte-gleich; Zahlen und Einheiten sind Daten.
	const POPOVER_ROWS: Array<{
		zeile: MessageKey;
		unit: string;
		entspannt: number | string;
		standard: number | string;
		sensibel: number | string;
	}> = [
		{ zeile: 'alarme.preset.zeile.wind_gust',            unit: 'km/h', entspannt: 35,   standard: 20,   sensibel: 12   },
		{ zeile: 'alarme.preset.zeile.precipitation_sum',    unit: 'mm',   entspannt: 20,   standard: 10,   sensibel: 5    },
		{ zeile: 'alarme.preset.zeile.thunder_level',        unit: '',     entspannt: '+1', standard: '+1', sensibel: '+1' },
		{ zeile: 'alarme.preset.zeile.snow_line',            unit: 'm',    entspannt: 600,  standard: 400,  sensibel: 200  },
		{ zeile: 'alarme.preset.zeile.temperature_min',      unit: '°C',   entspannt: 8,    standard: 5,    sensibel: 3    },
		{ zeile: 'alarme.preset.zeile.temperature_max',      unit: '°C',   entspannt: 10,   standard: 6,    sensibel: 4    },
		// #1435 E1a-2 AC-9: Wortlaut identisch zu ALERT_METRIC_LABELS (Gleichlauf
		// per Test gesichert); die Zusammenfuehrung beider Tabellen gehoert zu E4.
		{ zeile: 'alarme.preset.zeile.temperature_change',   unit: '°C',   entspannt: 14,   standard: 10,   sensibel: 6    },
		{ zeile: 'alarme.preset.zeile.wind_change',          unit: 'km/h', entspannt: 35,   standard: 25,   sensibel: 15   },
		{ zeile: 'alarme.preset.zeile.precipitation_change', unit: 'mm',   entspannt: 15,   standard: 7,    sensibel: 3    },
		{ zeile: 'alarme.preset.zeile.fresh_snow',           unit: 'cm',   entspannt: 20,   standard: 8,    sensibel: 2    },
		{ zeile: 'alarme.preset.zeile.cape',                 unit: 'J/kg', entspannt: 1200, standard: 600,  sensibel: 200  },
		{ zeile: 'alarme.preset.zeile.visibility',           unit: 'm',    entspannt: 500,  standard: 1000, sensibel: 3000 },
		{ zeile: 'alarme.preset.zeile.humidity',             unit: '%',    entspannt: 25,   standard: 15,   sensibel: 10   },
	];

	const PRESET_OPTIONS: Array<{ value: PresetName; label: MessageKey }> = [
		{ value: 'deaktiviert', label: 'alarme.preset.deaktiviert' },
		{ value: 'entspannt',   label: 'alarme.preset.entspannt'   },
		{ value: 'standard',    label: 'alarme.preset.standard'    },
		{ value: 'sensibel',    label: 'alarme.preset.sensibel'    },
	];

	let { value = $bindable<PresetName>('standard'), onchange }: {
		value?: PresetName;
		onchange?: (preset: PresetName) => void;
	} = $props();

	let popoverOpen = $state(false);

	function handleSelectChange(e: Event) {
		const sel = e.target as HTMLSelectElement;
		value = sel.value as PresetName;
		onchange?.(value);
	}

	function togglePopover() {
		popoverOpen = !popoverOpen;
	}

	function fmtNum(val: number | string, unit: string): string {
		if (typeof val === 'string') return val;
		return unit ? `${val} ${unit}` : String(val);
	}
</script>

<div class="alert-preset-selector">
	<div class="selector-row">
		<div class="select-wrapper">
			<select
				data-testid="alert-preset-select"
				value={value}
				onchange={handleSelectChange}
				class="preset-select"
			>
				{#each PRESET_OPTIONS as opt}
					<option value={opt.value}>{$t(opt.label)}</option>
				{/each}
			</select>
		</div>

		<button
			type="button"
			class="info-btn"
			data-testid="alert-preset-info"
			onclick={togglePopover}
			aria-label={$t('alarme.preset.uebersicht_anzeigen')}
		>ℹ</button>
	</div>

	{#if popoverOpen}
	<div class="popover" data-testid="alert-preset-popover">
		<div class="popover-header">
			<span class="popover-title">{$t('alarme.preset.uebersicht_titel')}</span>
			<button
				type="button"
				class="popover-close"
				data-testid="alert-preset-popover-close"
				onclick={togglePopover}
				aria-label={$t('alarme.preset.schliessen')}
			>✕</button>
		</div>
		<div class="popover-scroll">
			<table class="threshold-table">
				<thead>
					<tr>
						<th class="col-metric">{$t('alarme.tabelle.metrik')}</th>
						<th>{$t('alarme.preset.entspannt')}</th>
						<th>{$t('alarme.preset.standard')}</th>
						<th>{$t('alarme.preset.sensibel')}</th>
					</tr>
				</thead>
				<tbody>
					{#each POPOVER_ROWS as row}
					<tr>
						<td class="col-metric">{$t(row.zeile)}</td>
						<td>{fmtNum(row.entspannt, row.unit)}</td>
						<td>{fmtNum(row.standard, row.unit)}</td>
						<td>{fmtNum(row.sensibel, row.unit)}</td>
					</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
	{/if}
</div>

<style>
	.alert-preset-selector {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.selector-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.select-wrapper {
		flex: 1;
		max-width: 220px;
	}

	.preset-select {
		appearance: none;
		-webkit-appearance: none;
		width: 100%;
		padding: 8px 12px;
		font-family: var(--g-font-ui, inherit);
		font-size: var(--g-text-sm, 0.875rem);
		color: var(--g-ink, #111);
		background: var(--g-paper, #fff);
		border: 1px solid var(--g-ink-faint, #ccc);
		border-radius: var(--g-radius-sm, 4px);
		cursor: pointer;
	}

	.preset-select:focus-visible {
		outline: 2px solid var(--g-accent, #2563eb);
		outline-offset: 2px;
	}

	.info-btn {
		width: 28px;
		height: 28px;
		border-radius: 50%;
		border: 1px solid var(--g-ink-faint, #ccc);
		background: var(--g-card, #fff);
		color: var(--g-ink-2, #555);
		font-size: 13px;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.info-btn:hover {
		background: var(--g-card-alt, #f5f5f5);
	}

	.popover {
		position: absolute;
		top: calc(100% + 8px);
		left: 0;
		z-index: 100;
		background: var(--g-card, #fff);
		border: 1px solid var(--g-rule, #e5e5e5);
		border-radius: var(--g-r-2, 6px);
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
		width: min(560px, 90vw);
	}

	.popover-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
		border-bottom: 1px solid var(--g-rule, #e5e5e5);
	}

	.popover-title {
		font-size: 13px;
		font-weight: 600;
		color: var(--g-ink, #111);
	}

	.popover-close {
		background: none;
		border: none;
		color: var(--g-ink-3, #888);
		cursor: pointer;
		font-size: 14px;
		padding: 2px 4px;
	}

	.popover-scroll {
		overflow-x: auto;
		padding: 8px;
	}

	.threshold-table {
		border-collapse: collapse;
		font-size: 12.5px;
		width: 100%;
		white-space: nowrap;
	}

	.threshold-table th {
		text-align: right;
		padding: 4px 8px;
		color: var(--g-ink-2, #555);
		font-weight: 600;
		border-bottom: 1px solid var(--g-rule, #e5e5e5);
	}

	.threshold-table th.col-metric {
		text-align: left;
	}

	.threshold-table td {
		padding: 4px 8px;
		text-align: right;
		color: var(--g-ink, #111);
		border-bottom: 1px solid var(--g-rule-soft, #f0f0f0);
	}

	.threshold-table td.col-metric {
		text-align: left;
		color: var(--g-ink-2, #555);
	}
</style>
