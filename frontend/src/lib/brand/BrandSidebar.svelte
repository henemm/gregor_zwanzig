<script lang="ts">
	// BrandSidebar — kanonische App-Navigation. Vier Workspace-Items, fest in dieser
	// Reihenfolge. 1:1 portiert aus brand-kit.jsx (BrandSidebar + BrandSidebarItem + BrandSidebarIcon).
	import BrandWordmark from './BrandWordmark.svelte';
	import BrandUserBadge from './BrandUserBadge.svelte';

	interface Props {
		active?: 'home' | 'trips' | 'compare' | 'archive';
		counts?: Record<string, number>;
		onNavigate?: (id: string) => void;
		user?: { name?: string; sub?: string; accent?: boolean };
	}

	let { active = 'home', counts = {}, onNavigate, user }: Props = $props();

	const NAV_ITEMS = [
		{ id: 'home', label: 'Startseite', icon: 'home' },
		{ id: 'trips', label: 'Meine Touren', icon: 'trip' },
		{ id: 'compare', label: 'Orts-Vergleich', icon: 'compare' },
		{ id: 'archive', label: 'Archiv', icon: 'archive' }
	] as const;

	function iconColor(isActive: boolean): string {
		return isActive ? 'var(--g-accent)' : 'var(--g-ink-3)';
	}
</script>

<aside
	style="width:220px;flex:0 0 220px;background:var(--g-paper-deep);border-right:1px solid var(--g-rule);display:flex;flex-direction:column;padding:24px 0 0;height:100%;font-family:var(--g-font-sans)"
>
	<div style="padding:0 18px 24px">
		<BrandWordmark size="md" />
	</div>

	<nav style="display:flex;flex-direction:column;gap:2px;padding:0 12px">
		{#each NAV_ITEMS as it (it.id)}
			{@const isActive = active === it.id}
			{@const count = counts[it.id]}
			<a
				href={`#${it.id}`}
				onclick={() => onNavigate?.(it.id)}
				style="display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:var(--g-r-3);background:{isActive
					? 'rgba(196,90,42,0.10)'
					: 'transparent'};color:{isActive
					? 'var(--g-accent-deep)'
					: 'var(--g-ink-2)'};font-size:13px;font-weight:{isActive
					? 600
					: 500};text-decoration:none;cursor:pointer;transition:background 120ms"
			>
				{#if it.icon === 'home'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={iconColor(isActive)} stroke-width="1.7" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" /></svg>
				{:else if it.icon === 'trip'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={iconColor(isActive)} stroke-width="1.7" stroke-linejoin="round"><path d="M3 19l5-9 4 6 4-3 5 6" /><circle cx="8" cy="10" r="1.2" fill={iconColor(isActive)} /><circle cx="16" cy="13" r="1.2" fill={iconColor(isActive)} /></svg>
				{:else if it.icon === 'compare'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={iconColor(isActive)} stroke-width="1.7"><path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3" /></svg>
				{:else if it.icon === 'archive'}
					<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={iconColor(isActive)} stroke-width="1.7" stroke-linejoin="round"><rect x="3" y="5" width="18" height="4" rx="1" /><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4" /></svg>
				{/if}
				<span style="flex:1">{it.label}</span>
				{#if count != null}
					<span
						style="font-family:var(--g-font-mono);font-size:10px;color:{isActive
							? 'var(--g-accent-deep)'
							: 'var(--g-ink-4)'};background:{isActive
							? 'rgba(196,90,42,0.12)'
							: 'rgba(26,26,24,0.05)'};padding:1px 6px;border-radius:var(--g-r-pill);font-weight:600;letter-spacing:0.02em"
					>{count}</span>
				{/if}
			</a>
		{/each}
	</nav>

	<div style="flex:1"></div>

	<div style="padding:16px 18px;border-top:1px solid var(--g-rule-soft)">
		<BrandUserBadge
			name={user?.name ?? 'Gregor Henemm'}
			sub={user?.sub ?? 'henemm.com'}
			accent={user?.accent ?? false}
		/>
	</div>
</aside>
