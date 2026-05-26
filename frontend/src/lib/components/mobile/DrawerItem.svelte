<script lang="ts">
	// Issue #373 — DrawerItem (interner Helfer, aus mobile-shell.jsx).
	//
	// Navigations-Eintrag im Drawer mit Icon, Label, optionalem Badge.
	// min-height 44px (Touch). Token-basiert.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md
	import type { MIconKind } from './MIcon.svelte';
	import MIcon from './MIcon.svelte';

	interface Props {
		icon?: MIconKind | string;
		label: string;
		badge?: string | number | null;
		active?: boolean;
		href?: string;
		onclick?: () => void;
	}

	let { icon, label, badge = null, active = false, href = '#', onclick }: Props = $props();
	const iconColor = $derived(active ? 'var(--g-accent-deep)' : 'var(--g-ink-3)');
</script>

<a
	{href}
	{onclick}
	style:display="flex"
	style:align-items="center"
	style:gap="14px"
	style:padding="12px 12px"
	style:min-height="44px"
	style:text-decoration="none"
	style:color={active ? 'var(--g-ink)' : 'var(--g-ink-2)'}
	style:font-size="15px"
	style:font-weight={active ? '600' : '500'}
	style:background={active ? 'var(--g-card)' : 'transparent'}
	style:border-radius="var(--g-r-3)"
>
	{#if icon}
		<MIcon kind={icon} size={20} color={iconColor} />
	{/if}
	<span style:flex="1">{label}</span>
	{#if badge}
		<span
			class="mono"
			style:font-size="11px"
			style:padding="2px 8px"
			style:border-radius="var(--g-r-pill)"
			style:background="var(--g-paper-deep)"
			style:color="var(--g-ink-3)"
		>{badge}</span>
	{/if}
</a>
