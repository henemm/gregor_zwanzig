<script lang="ts">
	// Issue #578 — AlertsCard-Organism.
	// Kanonische Quelle: screen-home.jsx (Alerts · letzte 24 h Block)
	//
	// Zeigt ausgelöste Alerts der letzten 24 Stunden.

	import { Card, Eyebrow } from '$lib/components/atoms';
	import AlertRow from '../molecules/AlertRow.svelte';
	import { t } from '$lib/i18n';

	interface Alert {
		metric: string;
		value?: string | number;
		threshold?: string | number;
		location?: string;
		when?: string;
		[key: string]: unknown;
	}

	interface Props {
		alerts?: Alert[];
		label?: string;
		class?: string;
	}

	let { alerts = [], label = '—', class: className = '' }: Props = $props();
</script>

<Card padding={20} class={className}>
	<div
		style:display="flex"
		style:justify-content="space-between"
		style:align-items="center"
		style:margin-bottom="12px"
	>
		<div>
			<Eyebrow style="margin-bottom: 4px">{$t('bausteine.alarme.titel')}</Eyebrow>
			<div style:font-size="17px" style:font-weight="600">
				{alerts.length > 0 ? $t('bausteine.alarme.ausgeloest', { anzahl: alerts.length }) : $t('bausteine.alarme.keine')}
			</div>
		</div>
		<a
			href="/alert-rules"
			style:font-size="12px"
			style:color="var(--g-ink-3)"
			style:text-decoration="none"
			style:font-family="var(--g-font-mono)"
		>{$t('bausteine.alarme.schwellen')}</a>
	</div>

	{#if alerts.length > 0}
		{#each alerts as alert, i (i)}
			<AlertRow {alert} last={i === alerts.length - 1} />
		{/each}
	{:else}
		<div style:font-size="13px" style:color="var(--g-ink-3)" style:line-height="1.5" style:padding-top="2px">
			{$t('bausteine.alarme.leer')}
		</div>
	{/if}
</Card>
