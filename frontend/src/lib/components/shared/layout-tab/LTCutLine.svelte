<script lang="ts">
	// LTCutLine — Issue #1232 Scheibe 3a: geteilte Trennlinie "✂ ab hier
	// {Kanal}-Limit (max {N})" aus claude-code-handoff/current/jsx/layout-tab.jsx
	// (LT_RouteOrderDense).
	//
	// KL-1: als Primitiv bereits jetzt gebaut, in dieser Scheibe von keiner
	// Vergleichs-UI konsumiert — Konsument ist Scheibe 3b (context="route",
	// WeatherMetricsTab-Reihenfolge).
	//
	// Spec: docs/specs/modules/layout_tab_vergleich.md (Implementation Details §1, KL-1)

	interface Props {
		label: string;
		max: number;
	}
	let { label, max }: Props = $props();
</script>

<div class="lt-cut-line mono" data-testid="lt-cut-line">
	✂ ab hier {label}-Limit (max {max})
</div>

<style>
	.lt-cut-line {
		padding: 5px 14px;
		font-size: 10.5px;
		color: var(--g-warn-deep, #8a6210);
		background: rgba(192, 138, 26, 0.07);
		border-top: 1.5px dashed var(--g-warn);
		border-bottom: 1.5px dashed var(--g-warn);
	}
</style>
