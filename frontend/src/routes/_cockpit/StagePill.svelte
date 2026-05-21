<script lang="ts">
	import { Pill } from '$lib/components/ui/pill';
	import type { Stage } from '$lib/types.js';

	interface Props {
		stage: Stage;
		active: boolean;
		muted: boolean;
		riskTone?: 'success' | 'warning' | 'danger';
	}

	let { stage, active, muted, riskTone }: Props = $props();

	const tone = $derived<'default' | 'accent' | 'success' | 'warning' | 'danger'>(
		active ? 'accent' : (riskTone ?? 'default')
	);

	const label = $derived(stage.name ?? stage.date ?? '—');
</script>

<span
	data-testid="stage-pill"
	class="stage-pill"
	class:muted
	class:active
	title={label}
>
	<Pill {tone}>
		<span class="stage-pill__label">{label}</span>
	</Pill>
</span>

<style>
	.stage-pill {
		flex: 0 0 auto;
		max-width: 180px;
	}
	.stage-pill__label {
		display: inline-block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 100%;
		vertical-align: middle;
	}
	.stage-pill.muted {
		opacity: 0.5;
	}
	.stage-pill.active .stage-pill__label {
		font-weight: 600;
	}
</style>
