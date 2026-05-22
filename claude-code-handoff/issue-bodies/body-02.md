## Problem

Aktuelle Sidebar rendert `<h1>Gregor 20</h1>` als plain Inter-Tight bold — kein Markenausdruck. Auch im Mobile-Top-Bar identisch.

Entscheidung (vom Product Owner): **Variante B — Mono-Tag "gregor.zwanzig"** mit dezentem System-Untertitel. Das passt zum „Datenehrlich"-Ton des Produkts (mono-Schrift für alles Operative).

## Files

- `src/lib/components/ui/sidebar/Sidebar.svelte`
  - Line ~57: `<span class="text-sm font-bold">Gregor 20</span>` (mobile top bar)
  - Line ~78: `<h1 class="mb-6 text-lg font-bold">Gregor 20</h1>` (desktop sidebar)

## Required changes

### 1. Add a `<Wordmark />` component (Variante B)

`src/lib/components/ui/wordmark/Wordmark.svelte`:

```svelte
<script lang="ts">
  let { size = 'md', href = '/' }: { size?: 'sm' | 'md' | 'lg'; href?: string } = $props();
</script>

<a {href} class="g-wordmark g-wordmark--{size}" aria-label="Gregor Zwanzig — Home">
  <span class="g-wordmark__row">
    <span class="g-wordmark__first">gregor</span><span class="g-wordmark__sep">.</span><span class="g-wordmark__second">zwanzig</span>
  </span>
  <span class="g-wordmark__sub">v0.20 · wetter-briefing</span>
</a>

<style>
  .g-wordmark {
    display: inline-flex;
    flex-direction: column;
    text-decoration: none;
    line-height: 1;
  }
  .g-wordmark__row {
    font-family: var(--g-font-data); /* JetBrains Mono */
    font-weight: 500;
    letter-spacing: 0.04em;
    color: var(--g-ink);
  }
  .g-wordmark__first { color: var(--g-ink); }
  .g-wordmark__sep   { color: var(--g-ink-faint); }
  .g-wordmark__second { color: var(--g-accent); }
  .g-wordmark__sub {
    margin-top: 3px;
    font-family: var(--g-font-data);
    font-size: 9px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--g-ink-faint);
  }
  .g-wordmark--sm .g-wordmark__row { font-size: 14px; }
  .g-wordmark--md .g-wordmark__row { font-size: 18px; }
  .g-wordmark--lg .g-wordmark__row { font-size: 24px; }
  .g-wordmark--sm .g-wordmark__sub { display: none; } /* compact mobile bar */
</style>
```

### 2. Use it in the sidebar

```diff
- <span class="text-sm font-bold">Gregor 20</span>
+ <Wordmark size="sm" />
```

```diff
- <h1 class="mb-6 text-lg font-bold">Gregor 20</h1>
+ <div class="mb-6"><Wordmark size="md" /></div>
```

### 3. Document title

`src/app.html` — change document title from "Gregor 20" to "Gregor Zwanzig".

## Acceptance criteria

- [ ] Sidebar shows `gregor.zwanzig` in JetBrains Mono, with the dot in `--g-ink-faint` and "zwanzig" in `--g-accent`.
- [ ] Subtitle `v0.20 · wetter-briefing` in uppercase mono caps below.
- [ ] Mobile top bar uses `sm` size (no subtitle).
- [ ] Clicking the wordmark links to `/`.

## 📎 Screenshots

**Soll: Variante B (gewählt vom Product Owner)**

![soll-sidebar-B](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/soll-sidebar-B.png)

**Ist: aktueller Plain-Text-Header**

![current](https://raw.githubusercontent.com/henemm/gregor_zwanzig/main/.github/issue-assets/01-trips-list.png)