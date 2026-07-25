<script lang="ts">
	// DayWindowCard — geteilte Tagesfenster-Steuerung (Reiter Wetter-Metriken,
	// beide Kontexte). Issue #1361/#1372 S1b.
	// Spec: docs/specs/modules/compare_shared_day_window.md § AC-4
	//
	// Extrahiert 1:1 aus dem bisherigen Versand-Reiter-Markup
	// (versand-tab/VTSchedulePlan.svelte, vormals nur context="route") — jetzt
	// OHNE Kontext-Gate, damit Trip UND Ortsvergleich dieselbe Bedienfläche an
	// derselben Stelle bekommen (AC-4). Wirkt auf Stundentabelle UND
	// Vergleichswerte/SMS-Aggregation (day_window.resolve_configured_window()).
	//
	// Der Aufrufer (WeatherMetricsTab.svelte) haelt den State (reportConfig fuer
	// route, wiz fuer vergleich) und die Speicher-Kopplung — hier wird nur der
	// reine Von/Bis-Wert angezeigt und per Callback nach oben gemeldet
	// (Trip/Compare-Teilungs-Invariante: geteilt ist die Steuerung, nicht der
	// Speicher-Weg).

	import { Card } from '$lib/components/atoms';
	import { clampDayWindowEndHour } from '../versand-tab/dayWindowClamp.ts';

	interface Props {
		startHour: number;
		endHour: number;
		onStartHour: (v: number) => void;
		onEndHour: (v: number) => void;
	}
	let { startHour, endHour, onStartHour, onEndHour }: Props = $props();

	const dayWindowHourOptions = Array.from({ length: 24 }, (_, h) => h);
	// Issue #1361/#1372 S1b (PO-Entscheidung 2026-07-25): ein Fenster ueber
	// Mitternacht (Ende < Start, z. B. 22-2 Uhr) ist GUELTIG — Start bietet
	// wieder alle 24 Stunden an (der bisherige F005-Deckel auf 0..22 galt nur,
	// solange ausschliesslich Vorwaerts-Fenster moeglich waren), Ende bietet
	// alle Stunden AUSSER der gewaehlten Startstunde (die einzige verbleibende
	// Mehrdeutigkeit, s. clampDayWindowEndHour).
	const dayWindowStartOptions = dayWindowHourOptions;
	const dayWindowEndOptions = $derived(dayWindowHourOptions.filter((h) => h !== startHour));
	const wrapsMidnight = $derived(endHour < startHour);

	// Safari-Factory-Pattern (CLAUDE.md).
	function makeStartHandler() {
		return function doSetStart(e: Event) {
			const v = Number((e.target as HTMLSelectElement).value);
			onStartHour(v);
			onEndHour(clampDayWindowEndHour(v, endHour));
		};
	}
	function makeEndHandler() {
		return function doSetEnd(e: Event) {
			onEndHour(Number((e.target as HTMLSelectElement).value));
		};
	}
</script>

<Card padding={18} data-testid="day-window-control">
	<div class="dwc-head">
		<div class="dwc-title">Tagesfenster</div>
		<div class="dwc-sub">Zeitraum für Stundentabelle, Vergleichswerte, SMS/Kurzzusammenfassung</div>
	</div>
	<div class="dwc-body">
		<label class="dwc-time-label">
			<span class="dwc-time-caption">Von</span>
			<select
				data-testid="day-window-start-hour"
				class="dwc-time-input"
				value={startHour}
				onchange={makeStartHandler()}
			>
				{#each dayWindowStartOptions as h (h)}
					<option value={h}>{h.toString().padStart(2, '0')}:00</option>
				{/each}
			</select>
		</label>
		<label class="dwc-time-label">
			<span class="dwc-time-caption">Bis</span>
			<select
				data-testid="day-window-end-hour"
				class="dwc-time-input"
				value={endHour}
				onchange={makeEndHandler()}
			>
				{#each dayWindowEndOptions as h (h)}
					<option value={h}>{h.toString().padStart(2, '0')}:00</option>
				{/each}
			</select>
		</label>
	</div>
	{#if wrapsMidnight}
		<div class="dwc-wrap-hint" data-testid="day-window-wrap-hint">
			Geht über Mitternacht — endet am Folgetag.
		</div>
	{/if}
</Card>

<style>
	.dwc-head {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
	.dwc-title {
		font-size: 15px;
		font-weight: 600;
	}
	.dwc-sub {
		font-size: 12.5px;
		color: var(--g-ink-3);
	}
	.dwc-body {
		margin-top: 14px;
		padding-top: 12px;
		border-top: 1px solid var(--g-rule-soft, #e2ddd2);
		display: flex;
		gap: 18px;
	}
	.dwc-time-label {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}
	.dwc-time-caption {
		font-family: var(--g-font-mono);
		font-size: 9.5px;
		color: var(--g-ink-4);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.dwc-time-input {
		font-family: var(--g-font-mono);
		font-size: 13px;
		font-weight: 600;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-1, 4px);
		padding: 5px 8px;
		background: var(--g-card);
		color: var(--g-ink);
	}
	.dwc-wrap-hint {
		margin-top: 10px;
		font-size: 12px;
		color: var(--g-ink-3);
	}
	@media (max-width: 899px) {
		.dwc-time-input {
			min-height: 44px;
			font-size: 16px;
		}
	}
</style>
