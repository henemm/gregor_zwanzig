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

	// Issue #2794 S3a, Teil-PR 3 (AC-21, AC-40, ADR-0111): von/bis ueber das Select-Atom
	// (ui/select/Select.svelte) statt nativem <select>; Clamp unveraendert. Optionale
	// Beschriftungen fuer die Karte „Anpassen" des Reiters Wetter.
	import { Card } from '$lib/components/atoms';
	import { Select } from '$lib/components/ui/select';
	import { t } from '$lib/i18n';
	import { clampDayWindowEndHour } from '../versand-tab/dayWindowClamp.ts';

	interface Props {
		startHour: number;
		endHour: number;
		onStartHour: (v: number) => void;
		onEndHour: (v: number) => void;
		/** Beschriftungen (Default: Wertebereiche-Texte). */
		titel?: string;
		vonLabel?: string;
		bisLabel?: string;
	}
	let { startHour, endHour, onStartHour, onEndHour, titel, vonLabel, bisLabel }: Props = $props();

	const dayWindowHourOptions = Array.from({ length: 24 }, (_, h) => h);
	const stunde = (h: number) => ({ value: String(h), label: `${h.toString().padStart(2, '0')}:00` });
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
		return function doSetStart(wert: string) {
			const v = Number(wert);
			onStartHour(v);
			onEndHour(clampDayWindowEndHour(v, endHour));
		};
	}
	function makeEndHandler() {
		return function doSetEnd(wert: string) {
			onEndHour(Number(wert));
		};
	}
</script>

<Card padding={18} data-testid="day-window-control">
	<div class="dwc-head">
		<div class="dwc-title">{titel ?? $t('wertebereiche.tagesfenster.titel')}</div>
		<div class="dwc-sub">{$t('wertebereiche.tagesfenster.untertitel')}</div>
	</div>
	<div class="dwc-body">
		<div class="dwc-time-label">
			<span class="dwc-time-caption">{vonLabel ?? $t('wertebereiche.tagesfenster.von')}</span>
			<Select
				data-testid="day-window-start-hour"
				aria-label={vonLabel ?? $t('wertebereiche.tagesfenster.von')}
				class="dwc-time-input"
				style="min-height: 44px; min-width: 96px"
				options={dayWindowStartOptions.map(stunde)}
				value={String(startHour)}
				onValueChange={makeStartHandler()}
			/>
		</div>
		<div class="dwc-time-label">
			<span class="dwc-time-caption">{bisLabel ?? $t('wertebereiche.tagesfenster.bis')}</span>
			<Select
				data-testid="day-window-end-hour"
				aria-label={bisLabel ?? $t('wertebereiche.tagesfenster.bis')}
				class="dwc-time-input"
				style="min-height: 44px; min-width: 96px"
				options={dayWindowEndOptions.map(stunde)}
				value={String(endHour)}
				onValueChange={makeEndHandler()}
			/>
		</div>
	</div>
	{#if wrapsMidnight}
		<div class="dwc-wrap-hint" data-testid="day-window-wrap-hint">
			{$t('wertebereiche.tagesfenster.ueber_mitternacht')}
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
		font-size: 11px;
		color: var(--g-ink-3);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	:global(.dwc-time-input) {
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
		:global(.dwc-time-input) {
			min-height: 44px;
			font-size: 16px;
		}
	}
</style>
