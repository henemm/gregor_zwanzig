# sv

Everything you need to build a Svelte project, powered by [`sv`](https://github.com/sveltejs/cli).

## Creating a project

If you're seeing this, you've probably already done this step. Congrats!

```sh
# create a new project
npx sv create my-app
```

To recreate this project with the same configuration:

```sh
# recreate this project
npx sv@0.15.1 create --template minimal --types ts --no-install /home/hem/gregor_zwanzig/frontend
```

## Developing

Once you've created a project and installed dependencies with `npm install` (or `pnpm install` or `yarn`), start a development server:

```sh
npm run dev

# or start the server and open the app in a new browser tab
npm run dev -- --open
```

## Building

To create a production version of your app:

```sh
npm run build
```

You can preview the production build with `npm run preview`.

> To deploy your app, you may need to install an [adapter](https://svelte.dev/docs/kit/adapters) for your target environment.

## Atomic-Design-Disziplin

Das Frontend folgt einer Atomic-Design-Bibliothek (Epic #368). Vier Schichten,
eine Quelle pro Baustein.

### Lese-Regel (PFLICHT vor jeder UI-Arbeit)

Vor dem Bauen oder Ändern einer Route **erst die Showcase ansehen**:
`frontend/src/routes/_design-system/` (`/_design-system`). Dort sind ALLE
Brand-, Atom-, Molecule- und Mobile-Bausteine in allen Varianten gerendert.
Ein Muster muss hier sichtbar sein, bevor es in eine echte Route geht — die
Showcase ist die Regressions-Referenz. Inline-Defs von Komponenten, die es in
der Bibliothek schon gibt, sind verboten (Drop-in nutzen).

### Naming-Konvention

| Präfix / Schicht | Import aus | Beispiele |
|------------------|-----------|-----------|
| `Brand*` | `$lib/brand` | `BrandWordmark`, `BrandIcon`, `BrandIconSquare` |
| `M*` (Mobile-Touch) | `$lib/components/mobile` | `MBtn`, `MSwitch`, `MTab`, `Sheet`, `Toast`, `MobileShell` |
| Atoms (ohne Präfix) | `$lib/components/atoms` | `Btn`, `Pill`, `Input`, `Switch`, `WIcon`, `Dot`, `Eyebrow`, `SectionH`, `AvatarStack` |
| Molecules (ohne Präfix) | `$lib/components/molecules` | `Field`, `DetailRow`, `StagePill`, `ChannelRow`, `Stat`, `AlertRow`, … |

Jede Schicht hat ein kanonisches Barrel (`index.ts`) — immer von dort
importieren, nie direkt aus der `.svelte`-Datei.

### Konflikt-Regel

Bei gleichem Konzept in mehreren Schichten gewinnt zuerst das **brand-kit**
(`$lib/brand`), dann die **Atoms** (`$lib/components/atoms`). Ein Wordmark/Logo
kommt immer aus `$lib/brand`; eine generische Pill/Btn immer aus den Atoms.
Komponenten in `ui/` sind Bridge-Pendants — neue Aufrufer nutzen die
Atom-/Molecule-/Brand-Barrels.
