<script lang="ts">
	// Issue #409 — Alert-Preview-Karte für die rechte Spalte im
	// Trip-Detail Overview-Tab.

	import type { Trip, AlertRule } from '$lib/types';
	import { GCard } from '$lib/components/ui/g-card';
	import { Eyebrow, Pill } from '$lib/components/atoms';
	import {
		ALERT_METRIC_LABELS,
		ALERT_SEVERITY_TONE,
		SEVERITY_LABEL_DE,
		normalizeAlertMetric,
		thunderLevelLabel
	} from '$lib/utils/alertMetricLabels';

	interface Props {
		trip: Trip;
	}

	let { trip }: Props = $props();

	const enabledRules = $derived((trip.alert_rules ?? []).filter((r) => r.enabled).slice(0, 5));
	const isEmpty = $derived(enabledRules.length === 0);

	function metricLabel(rule: AlertRule): string {
		const key = normalizeAlertMetric(rule.metric);
		const meta = key ? ALERT_METRIC_LABELS[key] : undefined;
		if (!meta) return rule.metric;
		if (key === 'thunder_level') return `Gewitter ${thunderLevelLabel(rule.threshold)}`;
		const unit = meta.unit ? ` ${meta.unit}` : '';
		return `${meta.label_de} ${meta.comparison} ${rule.threshold}${unit}`;
	}

	function severityTone(rule: AlertRule): 'info' | 'warning' | 'danger' {
		return ALERT_SEVERITY_TONE[rule.severity] ?? 'info';
	}

	function severityLabel(rule: AlertRule): string {
		return SEVERITY_LABEL_DE[rule.severity] ?? rule.severity;
	}
</script>

<GCard data-testid="right-card-alerts" class="alerts-card">
	<Eyebrow>Alarmregeln</Eyebrow>
	<h3 class="card-title">Alert-Schwellen</h3>

	{#if isEmpty}
		<p data-testid="right-card-alerts-empty" class="empty-state">
			Noch keine Alerts konfiguriert
		</p>
	{:else}
		<ul class="alert-list">
			{#each enabledRules as rule (rule.metric + rule.threshold + rule.id)}
				<li data-testid="alert-row" class="alert-row">
					<span class="alert-metric">{metricLabel(rule)}</span>
					<Pill tone={severityTone(rule)}>{severityLabel(rule)}</Pill>
				</li>
			{/each}
		</ul>
	{/if}

	<a href="#alerts" data-testid="right-card-alerts-edit-link" class="edit-link">
		Regeln bearbeiten →
	</a>
</GCard>

<style>
	:global([data-testid='right-card-alerts']) {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--g-ink-faint);
		border-radius: 0.5rem;
		background: var(--g-surface-1, #fff);
	}
	.card-title {
		font-size: var(--g-text-md);
		font-weight: 600;
		margin: 0;
	}
	.empty-state {
		font-size: var(--g-text-sm);
		color: var(--g-ink-muted);
		margin: 0;
	}
	.alert-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: var(--g-s-1, 0.375rem);
	}
	.alert-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: var(--g-s-2, 0.5rem);
		font-size: var(--g-text-sm);
	}
	.alert-metric {
		flex: 1;
		color: var(--g-ink);
		min-width: 0;
	}
	.edit-link {
		display: inline-block;
		font-size: var(--g-text-sm);
		color: var(--g-accent-deep);
		text-decoration: none;
		margin-top: 0.25rem;
	}
	.edit-link:hover {
		text-decoration: underline;
	}
</style>
