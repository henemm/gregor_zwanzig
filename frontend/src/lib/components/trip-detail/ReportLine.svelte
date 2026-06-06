<script lang="ts">
	import ChannelDot from './ChannelDot.svelte';

	interface Props {
		kind: 'morning' | 'evening' | 'alert';
		time: string;
		channels: string[];
		active?: boolean;
		alert?: boolean;
	}
	let { kind, time, channels, active = false, alert = false }: Props = $props();

	const dotColor = $derived(
		active && alert
			? 'var(--g-accent)'
			: active
				? 'var(--g-good)'
				: 'var(--g-rule)'
	);

	const labels: Record<string, string> = {
		morning: 'Morgen-Briefing',
		evening: 'Abend-Briefing',
		alert: 'Alert-Trigger'
	};
</script>

<div
	style="
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 8px 0;
		border-bottom: 1px solid var(--g-rule-soft);
	"
>
	<span
		style="
			width: 6px;
			height: 6px;
			border-radius: 50%;
			background: {dotColor};
			flex-shrink: 0;
		"
	></span>
	<span style="flex: 1; font-size: 13px; color: var(--g-ink);">{labels[kind] ?? kind}</span>
	<span
		style="
			font-family: var(--g-font-mono, ui-monospace, monospace);
			font-size: 11px;
			color: var(--g-ink-3);
		"
	>{time}</span>
	<div style="display: flex; gap: 3px; align-items: center;">
		{#each channels as ch}
			<ChannelDot kind={ch as 'email' | 'telegram' | 'sms'} />
		{/each}
	</div>
</div>
