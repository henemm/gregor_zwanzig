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

	//
	// Issue #3047 Runde 8 (F3, PO-Entscheidung Spec-Nachtrag Runde 7 „Nichts
	// fällt weg“, AC-24): die Linie behauptet keine Kappung mehr, sondern sagt,
	// was die Ausgabe ab Platz {platz} tut — Trip: nur noch Kurzübersicht statt
	// Stundentabelle; Orts-Vergleich: zweite Telegram-Zeile je Ort.

	import { t } from '$lib/i18n';

	interface Props {
		label: string;
		/** Erste Position, die nicht mehr in der ersten Zeile/Tabelle steht. */
		platz: number;
		context: 'route' | 'vergleich';
	}
	let { label, platz, context }: Props = $props();
</script>

<div class="lt-cut-line mono" data-testid="lt-cut-line">
	{context === 'vergleich'
		? $t('layout.kappung.schnittlinie_vergleich', { kanal: label, platz })
		: $t('layout.kappung.schnittlinie_route', { kanal: label, platz })}
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
