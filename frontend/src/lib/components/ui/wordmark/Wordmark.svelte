<script lang="ts">
	// Thin-Wrapper (Issue #370): delegiert an die kanonische Brand-Bibliothek.
	// Bewahrt Link-Verhalten + aria-label; BrandWordmark selbst hat kein href.
	import BrandWordmark from '$lib/brand/BrandWordmark.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		href?: string;
	}

	let { size = 'md', href = '/' }: Props = $props();

	// Kompakte sm-Variante (erste Zeile der mobilen Uebersicht) zeigt keinen
	// Untertitel — wie die fruehere Wordmark-Logik ({#if size !== 'sm'}).
	const caption = $derived(size === 'sm' ? null : undefined);
</script>

<a {href} aria-label={$t('bausteine.wordmark.home')} style="text-decoration:none;display:inline-block">
	<BrandWordmark {size} icon="left" {caption} />
</a>
