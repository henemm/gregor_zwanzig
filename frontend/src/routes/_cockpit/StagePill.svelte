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

<span data-testid="stage-pill" class={muted ? 'opacity-50' : ''}>
	<Pill {tone}>
		{label}
	</Pill>
</span>
