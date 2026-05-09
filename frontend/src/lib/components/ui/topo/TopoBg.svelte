<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		opacity?: number;
		children?: Snippet;
	}

	let { opacity = 0.04, children }: Props = $props();
</script>

<div class="relative overflow-hidden">
	<div
		data-slot="topo-bg"
		class="g-topo absolute inset-0"
		style:--g-topo-opacity={opacity}
	></div>
	<div class="relative">
		{@render children?.()}
	</div>
</div>
