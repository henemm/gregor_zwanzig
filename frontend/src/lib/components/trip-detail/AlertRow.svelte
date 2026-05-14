<script lang="ts">
	// Issue #222 W2 — Eine Zeile pro AlertRule in der AlertsPreviewCard.
	// Spec: docs/specs/modules/issue_222_w2_frontend_alert_konfigurator.md §5.
	//
	// Zeigt: {Label_DE}  {Comparison} {Value}{Unit}  [Severity-Pill]
	// Spezialfall THUNDER_LEVEL: zeigt "MITTEL"/"HOCH" statt 1.0/2.0.

	import type { AlertRule } from '$lib/types';
	import { Pill } from '$lib/components/ui/pill';
	import {
		ALERT_METRIC_LABELS,
		ALERT_SEVERITY_TONE,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';

	interface Props {
		rule: AlertRule;
	}

	let { rule }: Props = $props();

	// Defense (F004): unbekannte Metric (z.B. zukuenftige API-Erweiterung) →
	// info ist undefined, Row wird im Template uebersprungen statt zu crashen.
	let info = $derived(ALERT_METRIC_LABELS[rule.metric]);
	let valueText = $derived(
		!info
			? ''
			: rule.metric === 'thunder_level'
				? thunderLevelLabel(rule.threshold)
				: `${rule.threshold} ${info.unit}`.trim()
	);
</script>

{#if info}
	<div class="alert-row" data-testid="alert-row">
		<span class="label">{info.label_de}</span>
		<span class="threshold">{info.comparison} {valueText}</span>
		<Pill tone={ALERT_SEVERITY_TONE[rule.severity]}>{rule.severity}</Pill>
	</div>
{/if}

<style>
	.alert-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.875rem;
	}
	.label {
		flex: 0 0 auto;
		font-weight: 500;
	}
	.threshold {
		flex: 1;
		color: var(--g-ink-muted, #6b7280);
	}
</style>
