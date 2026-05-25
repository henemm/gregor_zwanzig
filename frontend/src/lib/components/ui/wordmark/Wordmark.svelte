<script lang="ts">
	// Thin-Wrapper (Issue #370): delegiert an die kanonische Brand-Bibliothek.
	// Bewahrt Link-Verhalten + aria-label; BrandWordmark selbst hat kein href.
	import BrandWordmark from '$lib/brand/BrandWordmark.svelte';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		href?: string;
	}

	let { size = 'md', href = '/' }: Props = $props();

	// Backward-Compat: kompakte sm-Variante (Mobile TopAppBar) zeigt keinen
	// Untertitel — wie die fruehere Wordmark-Logik ({#if size !== 'sm'}).
	const caption = $derived(size === 'sm' ? null : undefined);
</script>

<a {href} aria-label="Gregor Zwanzig — Home" style="text-decoration:none;display:inline-block">
	<BrandWordmark {size} icon="left" {caption} />
</a>
