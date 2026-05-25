<script lang="ts">
	// BrandShell — Convenience-Wrapper fuer ganze Screens: Sidebar + Main.
	// 1:1 portiert aus brand-kit.jsx.
	import BrandSidebar from './BrandSidebar.svelte';
	import type { Snippet } from 'svelte';

	interface Props {
		active?: string;
		counts?: Record<string, number>;
		user?: { name?: string; sub?: string; accent?: boolean };
		onNavigate?: (id: string) => void;
		children?: Snippet;
	}

	let { active = 'home', counts = {}, user, onNavigate, children }: Props = $props();
</script>

<div style="width:100%;height:100%;display:flex;flex-direction:row;background:var(--g-paper);overflow:hidden">
	<BrandSidebar
		active={active as 'home' | 'trips' | 'compare' | 'archive'}
		{counts}
		{user}
		{onNavigate}
	/>
	<main style="flex:1;min-width:0;height:100%;overflow:auto">
		{@render children?.()}
	</main>
</div>
