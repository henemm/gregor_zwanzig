// Issue #371 — Atoms-Schicht: kanonische Re-Export-Barrel (Bridge-Ansatz).
//
// Eine Quelle fuer alle 13 Atome:
//   import { Switch, Eyebrow, Pill, Card, Btn, Input, Dot, WIcon,
//            ElevSparkline, SectionH, AvatarStack, TopoBg, KV }
//     from '$lib/components/atoms';
//
// 9 Re-Export-Wrapper auf bestehende ui/-Pendants + 4 neue Atome.
//
// Spec: docs/specs/modules/issue_371_atoms.md (AC-1)

// 4 neue Atome
export { default as Switch } from './Switch.svelte';
export { default as SectionH } from './SectionH.svelte';
export { default as AvatarStack } from './AvatarStack.svelte';
export { default as KV } from './KV.svelte';

// 9 Re-Export-Wrapper (Bridge auf ui/)
export { default as Eyebrow } from './Eyebrow.svelte';
export { default as Pill } from './Pill.svelte';
export { default as Card } from './Card.svelte';
export { default as Btn } from './Btn.svelte';
export { default as Input } from './Input.svelte';
export { default as Dot } from './Dot.svelte';
export { default as WIcon } from './WIcon.svelte';
export { default as ElevSparkline } from './ElevSparkline.svelte';
export { default as TopoBg } from './TopoBg.svelte';

// Typen aus neuen Atomen
export type { SwitchSize, SwitchTone } from './Switch.svelte';
export type { AvatarUser } from './AvatarStack.svelte';
