<script lang="ts">
	// Issue #373 — NavIcon (interner Helfer fuer BottomNav, aus mobile-shell.jsx).
	//
	// Vier Workspace-Icons (home/trip/compare/archive). Aktiv -> --g-ink,
	// inaktiv -> --g-ink-3. Unbekanntes kind -> leerer Platzhalter.
	//
	// Spec: docs/specs/modules/issue_373_mobile.md

	interface Props {
		kind: string;
		active?: boolean;
		size?: number;
	}

	let { kind, active = false, size = 22 }: Props = $props();
	const c = $derived(active ? 'var(--g-ink)' : 'var(--g-ink-3)');
</script>

{#if kind === 'home'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={c} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />
	</svg>
{:else if kind === 'trip'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={c} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M3 19l5-9 4 6 4-3 5 6" /><circle cx="8" cy="10" r="1.2" fill={c} /><circle cx="16" cy="13" r="1.2" fill={c} />
	</svg>
{:else if kind === 'compare'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={c} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3" />
	</svg>
{:else if kind === 'archive'}
	<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={c} stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
		<rect x="3" y="5" width="18" height="4" rx="1" /><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4" />
	</svg>
{:else}
	<span style:width="{size}px" style:height="{size}px" style:display="inline-block"></span>
{/if}
