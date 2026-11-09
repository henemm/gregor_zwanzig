<script lang="ts">
	import { Pill } from '$lib/components/atoms';
	import type { Stage } from '$lib/types';
	import { riskToPill } from '$lib/utils/stageRisk';
	import { locale } from '$lib/i18n';

	interface Props {
		stage: Stage;
		index: number;
		active?: boolean;
		onclick?: () => void;
		risk?: 'green' | 'yellow' | 'red' | null;
	}
	let { stage, index, active = false, onclick, risk }: Props = $props();

	// i18n F9: riskToPill liest die Sprache per tr() — `$locale` haelt die Pille reaktiv.
	const pill = $derived.by(() => (void $locale, riskToPill(risk)));

	const wpCount = $derived(stage.waypoints?.length ?? 0);
	const kmVal = $derived((stage as Stage & { distance_km?: number }).distance_km ?? 0);
	const ascentVal = $derived((stage as Stage & { ascent_m?: number }).ascent_m ?? 0);
	const descentVal = $derived((stage as Stage & { descent_m?: number }).descent_m ?? 0);
	const elevVal = $derived((stage as Stage & { elevation_m?: number }).elevation_m ?? 0);
	const summaryVal = $derived((stage as Stage & { summary?: string }).summary ?? '');

	function makeClickHandler() {
		return function doClick() {
			onclick?.();
		};
	}
	const handleClick = makeClickHandler();
</script>

<div
	role="button"
	tabindex="0"
	data-testid="trip-stage-row-{index}"
	class="stage-row"
	style="
		border-left: 3px solid {active ? 'var(--g-accent)' : 'transparent'};
		background: {active ? 'rgba(196,90,42,0.05)' : 'transparent'};
	"
	onclick={handleClick}
	onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
>
	<!-- Col 1: Stage code -->
	<div
		style="
			font-family: var(--g-font-mono, ui-monospace, monospace);
			font-size: 11px;
			color: var(--g-ink-3);
			align-self: center;
		"
	>
		{(stage as Stage & { code?: string }).code ?? String(index + 1).padStart(2, '0')}
	</div>

	<!-- Col 2: Title + meta -->
	<div style="align-self: center; min-width: 0;">
		<div class="stage-name" style="font-size: 14px; font-weight: 500; color: var(--g-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
			{stage.name}
		</div>
		<!-- #2878: Meta-Zeile = Reihe unteilbarer Teile; Umbruch nur zwischen den Teilen, der Trenner hängt am Teil. -->
		<div class="stage-meta" style="font-family: var(--g-font-mono, ui-monospace, monospace); font-size: 11px; color: var(--g-ink-3); margin-top: 3px;">
			{#if stage.date}<span class="stage-meta-part">{stage.date}</span>{/if}
			{#if kmVal}<span class="stage-meta-part">{`· ${kmVal.toFixed(1)} km`}</span>{/if}
			{#if ascentVal}<span class="stage-meta-part">{`· ↑${ascentVal} m`}</span>{/if}
			{#if descentVal}<span class="stage-meta-part">{`· ↓${descentVal} m`}</span>{/if}
			{#if elevVal}<span class="stage-meta-part">{`· ${elevVal} m`}</span>{/if}
			{#if wpCount}<span class="stage-meta-part">{`· ${wpCount} WP`}</span>{/if}
		</div>
	</div>

	<!-- Col 3: Summary -->
	<div
		class="stage-row-summary"
		style="
			font-size: 12px;
			font-style: italic;
			color: var(--g-ink-2);
			align-self: center;
			overflow: hidden;
			display: -webkit-box;
			-webkit-line-clamp: 2;
			-webkit-box-orient: vertical;
		"
	>
		{summaryVal}
	</div>

	<!-- Col 4: Risk pill -->
	<div style="align-self: center; display: flex; justify-content: flex-end;">
		<Pill tone={pill.tone}>{pill.label}</Pill>
	</div>
</div>

<style>
	.stage-row {
		display: grid;
		grid-template-columns: 60px minmax(0, 1fr) 280px 100px;
		gap: 16px;
		padding: 14px 18px;
		border-bottom: 1px solid var(--g-rule-soft);
		cursor: pointer;
	}
	.stage-meta {
		display: flex;
		flex-wrap: wrap;
		column-gap: 1ch;
	}
	.stage-meta-part {
		white-space: nowrap;
	}
	/* Mobile: Summary-Spalte entfällt, Pill rückt ans Zeilenende. */
	@media (max-width: 899px) {
		.stage-row {
			grid-template-columns: 40px minmax(0, 1fr) auto;
			gap: 10px;
			padding: 12px 14px;
		}
		.stage-row .stage-row-summary {
			display: none !important;
		}
	}
	/* #2878: dieselbe Regel nach der Breite der Etappenliste (HubOverview `etappenliste`) — am
	   Computer ist die linke Spalte schmaler als 640 px, das starre Raster liesse dem Namen 0 px. */
	@container etappenliste (max-width: 639px) {
		.stage-row {
			grid-template-columns: 40px minmax(0, 1fr) auto;
			gap: 10px;
			padding: 12px 14px;
		}
		.stage-row .stage-row-summary {
			display: none !important;
		}
	}
</style>
