<script lang="ts">
	// Issue #301 Lieferung B — Anzeige-Kachel pro Auto-Report (Subscription).
	// Reine Darstellung, kein Edit-Handler (Out of Scope).
	//
	// Spec: docs/specs/modules/issue_301b_auto_reports_overview.md (§3)

	import type { Subscription } from '$lib/types.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Dot } from '$lib/components/ui/dot/index.js';
	import { Pill } from '$lib/components/ui/pill/index.js';
	import { scheduleLabel, locationsLabel, formatLastRun } from './subscriptionHelpers.js';

	interface Props {
		subscription: Subscription;
	}

	let { subscription }: Props = $props();
</script>

<Card.Root data-testid="auto-report-card-{subscription.id}">
	<Card.Content class="card-body">
		<div class="card-header">
			<Dot tone={subscription.enabled ? 'success' : 'default'} size="sm" />
			<span class="card-name" data-testid="card-name-{subscription.id}">{subscription.name}</span>
		</div>
		<div class="card-schedule">
			<span class="mono">{scheduleLabel(subscription)}</span>
			<span class="separator">·</span>
			<span>{locationsLabel(subscription)}</span>
		</div>
		{#if subscription.last_run}
			<div class="card-footer">
				<span class="last-run-label">Letzter Lauf: {formatLastRun(subscription.last_run)}</span>
				<Pill tone={subscription.last_status === 'ok' ? 'success' : 'danger'}>
					{subscription.last_status === 'ok' ? 'OK' : 'Fehler'}
				</Pill>
			</div>
		{/if}
	</Card.Content>
</Card.Root>

<style>
	.card-body {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-2);
	}

	.card-header {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		min-width: 0;
	}

	.card-name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-schedule {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: 0.8125rem;
		color: var(--g-ink-muted);
	}

	.mono {
		font-family: var(--g-font-data);
	}

	.card-footer {
		display: flex;
		align-items: center;
		gap: var(--g-s-2);
		font-size: 0.75rem;
		color: var(--g-ink-muted);
	}
</style>
