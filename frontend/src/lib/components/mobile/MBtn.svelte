<script lang="ts" module>
	export type MBtnVariant = 'primary' | 'accent' | 'ghost' | 'quiet' | 'danger';
	export type MBtnSize = 'md' | 'lg' | 'xl';
</script>

<script lang="ts">
	// Issue #373 — MBtn (kanonisch aus mobile-shell.jsx, Svelte 5).
	//
	// Touch-Button mit drei Groessen (md 40px, lg 48px, xl 56px) und fuenf
	// Varianten. lg/xl erfuellen das 44px-Touch-Mindestmass. Token-basiert.
	// Unbekannte variant/size -> Default-Fallback (primary/lg), kein Crash.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md (AC-2, AC-6)
	import type { Snippet } from 'svelte';
	import type { MIconKind } from './MIcon.svelte';
	import MIcon from './MIcon.svelte';

	interface Props {
		variant?: MBtnVariant;
		size?: MBtnSize;
		block?: boolean;
		icon?: MIconKind | string;
		onclick?: () => void;
		children?: Snippet;
	}

	let { variant = 'primary', size = 'lg', block = false, icon, onclick, children }: Props = $props();

	// Touch-Hoehen: md 40px, lg 48px (>=44px), xl 56px (>=44px).
	const sizes = {
		md: { padX: 14, padY: 10, fs: 14, h: 40 },
		lg: { padX: 18, padY: 14, fs: 15, h: 48 },
		xl: { padX: 22, padY: 16, fs: 16, h: 56 }
	} as const;

	const variants = {
		primary: { bg: 'var(--g-ink)', fg: 'var(--g-paper)', border: '1px solid var(--g-ink)' },
		// audit:exempt — --g-accent ist hier Button-Hintergrund (bg), der Text ist #fff (keine Textfarbe)
		accent: { bg: 'var(--g-accent)', fg: '#fff', border: '1px solid var(--g-accent)' },
		ghost: { bg: 'transparent', fg: 'var(--g-ink)', border: '1px solid var(--g-rule)' },
		quiet: { bg: 'transparent', fg: 'var(--g-ink-2)', border: '1px solid transparent' },
		danger: { bg: 'transparent', fg: 'var(--g-danger)', border: '1px solid var(--g-rule)' }
	} as const;

	const s = $derived(sizes[size] ?? sizes.lg);
	const v = $derived(variants[variant] ?? variants.primary);
</script>

<button
	type="button"
	{onclick}
	data-variant={variant}
	data-size={size}
	style:display="inline-flex"
	style:align-items="center"
	style:justify-content="center"
	style:gap="8px"
	style:padding="{s.padY}px {s.padX}px"
	style:min-height="{s.h}px"
	style:width={block ? '100%' : 'auto'}
	style:font-size="{s.fs}px"
	style:font-weight="600"
	style:letter-spacing="-0.005em"
	style:font-family="var(--g-font-sans)"
	style:background={v.bg}
	style:color={v.fg}
	style:border={v.border}
	style:border-radius="var(--g-r-3)"
	style:cursor="pointer"
>
	{#if icon}
		<span style:display="inline-flex"><MIcon kind={icon} size={s.fs + 4} color={v.fg} /></span>
	{/if}
	{@render children?.()}
</button>
