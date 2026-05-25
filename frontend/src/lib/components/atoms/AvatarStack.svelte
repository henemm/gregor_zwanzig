<script lang="ts" module>
	export interface AvatarUser {
		name: string;
		initials?: string;
		color?: string;
	}
</script>

<script lang="ts">
	// Issue #371 — AvatarStack-Atom (kanonisch aus atoms.jsx, Svelte 5).
	//
	// Ueberlappende, kreisfoermige Avatare aus users[] (negativer margin-left),
	// Border in var(--g-card) zur Trennung. Initialen aus name, falls nicht gesetzt.
	//
	// Spec: docs/specs/modules/issue_371_atoms.md (AC-6)

	interface Props {
		users?: AvatarUser[];
		size?: number;
		class?: string;
	}

	let { users = [], size = 26, class: className = '' }: Props = $props();

	function initialsOf(u: AvatarUser): string {
		return u.initials || u.name.slice(0, 2).toUpperCase();
	}
</script>

<div data-slot="avatar-stack" class={className} style:display="inline-flex">
	{#each users as u, i (i)}
		<div
			title={u.name}
			style:width="{size}px"
			style:height="{size}px"
			style:border-radius="50%"
			style:background={u.color || `hsl(${(i * 70) % 360} 30% 65%)`}
			style:color="#fff"
			style:font-size="{size * 0.42}px"
			style:font-weight="600"
			style:font-family="var(--g-font-sans)"
			style:display="inline-flex"
			style:align-items="center"
			style:justify-content="center"
			style:border="2px solid var(--g-card)"
			style:margin-left="{i === 0 ? 0 : -size * 0.3}px"
		>
			{initialsOf(u)}
		</div>
	{/each}
</div>
