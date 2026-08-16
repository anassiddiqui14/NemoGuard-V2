# NemoGuard — Landing Page, Login Gate & Dashboard Personalization
## Design & Implementation Plan (v1)

**Status:** DRAFT — for review before implementation begins.
**Scope:** Frontend only (`pipeline-copilot/frontend`). No backend contract changes required except one optional endpoint (§8.4).

---

## 0. Why this document exists

The user asked for three things, with an explicit instruction to think it through and document before writing code:

1. A modern, sophisticated **3D landing page** with scroll effects that proves "how real this app is" — enterprise-grade, not a toy marketing page.
2. A **login screen**, with a **switch/toggle to disable the login requirement** whenever needed (demo-friendly, but still feels like a real gated product).
3. **Dashboard personalization** — greeting, richer navigation with sections, "new features" surfacing — to make the Command Center feel like a complete, living product rather than a single dense screen.

This document captures the current-state audit, the design decisions, the exact component/file plan, the data model, the technical risks, and a phased build order. Nothing gets built until this is reviewed.

---

## 1. Current-state audit (what exists today)

### 1.1 Stack
- **Build tool:** Vite 8, React 19, TypeScript 6.
- **Styling:** Tailwind CSS v4 (CSS-first `@theme` tokens in `src/index.css`), no component library (hand-rolled everything).
- **Animation:** `framer-motion` v13 already installed and used throughout (`AnimatePresence`, `motion.div`, spring transitions). **No 3D library exists yet** (no `three`, `@react-three/fiber`, `@react-three/drei`).
- **Icons:** `lucide-react`.
- **Charts:** `recharts` (unused so far in the audited files, likely used in `InvestigationPanels.tsx`/analytics).
- **Toasts:** `react-hot-toast`.
- **Routing:** **None.** The whole app is a single `<App />` that unconditionally renders `<TopBar />` + `<Dashboard />`. No React Router, no route-based code splitting.
- **State:** No global store (Redux/Zustand). Local `useState`/`useEffect` + polling (`setInterval` every 2s for incidents, 5s for notifications) + one SSE hook (`useIncidentEvents`) for live agent events. `localStorage` is used directly for the JWT token and the theme preference.
- **Theming:** `ThemeContext` toggles a `light`/`dark` class on `<html>`, backed by CSS custom properties. Already solid and reusable.

### 1.2 Entry point flow today
```
main.tsx
  └─ ThemeProvider
       └─ App.tsx
            ├─ useAuthToken()  → auto-fetches a mock JWT on mount, no login UI at all
            ├─ TopBar (search, theme toggle, notification bell, avatar "SR")
            └─ Dashboard (the whole Command Center: queue, situation header, panels, recovery rail)
```

### 1.3 Auth reality (`src/api/auth.py`)
- Real JWT-based auth exists on the backend (`create_access_token`, `get_current_user`, `require_role`), using `PyJWT` + `HS256`, secret from `JWT_SECRET` env var. Roles: e.g. `commander`, `admin`, `viewer`.
- **There is no real login endpoint** — only a **mock-login** dev endpoint:
  `GET /api/v2/auth/mock-login?role=commander` — only enabled when `ENV` is `development`/`dev`/`local` (guarded in `main.py`), returns a 24h-lived JWT for a hardcoded mock user (`test@nemoguard.com`, `tenant_A`, `ws_alpha`).
- The frontend's `useAuthToken()` hook silently calls this mock-login on mount and stores the token in `localStorage['nemoguard_token']` — this is why the app currently has **zero visible login/auth UX**: it self-authenticates invisibly.
- This means: **today, "login" is a fiction that already always succeeds.** Our job is to build a *real-looking* login screen that sits in front of this existing mock-login call (and remains swappable for real OIDC later), plus a way to bypass it entirely.

### 1.4 Dashboard reality (`Dashboard.tsx`, `App.tsx`)
- `TopBar` already has: logo/wordmark, search box (visual only, not wired), theme toggle, notification bell (wired to `useNotifications` polling), and a static avatar with initials "SR" (hardcoded, not personalized).
- No greeting, no user menu, no settings, no "what's new", no side navigation with sections — it's a single dense operational view (queue / workspace / recovery rail), which matches the internal blueprint doc's "mission control" vision, but has zero "product" framing around it (no sense of *whose* command center this is, no light/dark polish tour, no notion of multiple pages).
- `nemoguard_enterprise_command_center_ui_blueprint.md` (already in the repo, read in full) describes a fuller IA — Command Center / Incidents / Agent Operations / Automations / Evidence / Analytics / Scenario Lab / Settings — of which **only Command Center is actually implemented**. This gives us a ready-made naming system to reuse for the nav "sections" the user asked for, without inventing new terminology that conflicts with existing docs.

### 1.5 Visual system already in place (reuse, don't replace)
- Color tokens (`--color-primary`, `--color-agent-active`, `--color-healthy`, `--color-warning`, `--color-critical`, `--color-info`) + light/dark overrides are already carefully tuned. The 3D landing page and login screen **must reuse these tokens** so they feel like the same product, not a bolted-on marketing site.
- `.glass-panel`, `.text-gradient`, `.glow-primary`, `.press-scale`, `.shimmer` utility classes already exist and read as "premium enterprise SaaS" — reuse these on the landing/login pages.
- Font: Inter (body) + JetBrains Mono (technical values) already loaded via Google Fonts in `index.html`.

### 1.6 Docker/deploy reality
- Frontend is a static Vite build served by nginx (`Dockerfile.frontend`, `nginx.conf`), proxying `/api/` to the `api` service. No SSR, no server-side routing needed — any client-side router (React Router) works fine as long as nginx `try_files` falls back to `index.html` for unknown paths (it already does: `try_files $uri $uri/ /index.html;` ✅ confirmed in `nginx.conf`).

---

## 2. Design intent — what "modern, sophisticated, real" means here

The pitfall to avoid: a generic "AI SaaS" landing page with floating gradient blobs and a hero headline that could belong to any startup. The instruction was explicit: *"should show how real this app is."* That means the landing page's 3D/visual centerpiece should be **a stylized visualization of the actual product** — the agent constellation, the incident lifecycle, the live event stream — not abstract decoration.

### 2.1 Landing page narrative (scroll sections)
A single-page, full-bleed, scroll-driven marketing/product page at route `/` (unauthenticated), composed of:

1. **Hero** — Full-viewport 3D scene: a rotating/orbiting "constellation" of agent nodes (Watcher, RCA, Impact, Runbook, Safety, Verifier — same 6 roles as `AgentConstellation.tsx`) connected by animated light-trail edges, built with `@react-three/fiber` + `@react-three/drei`, sitting behind the headline and a "Enter Command Center" CTA. This deliberately mirrors the real in-app `AgentConstellation` component so a viewer who later logs in recognizes it — reinforcing "this is real, not staged."
   - Scroll-linked parallax: camera slowly orbits / nodes drift as the user scrolls (using `framer-motion`'s `useScroll` + `useTransform`, driving the Three.js camera or group rotation — no extra scroll library needed).
2. **"Live incident, real agents" section** — A recreated (static/looping, not connected to prod data) mini version of the Situation Header + lifecycle stepper (`Detected → Correlated → Investigating → Plan Ready → Approval → Executing → Verifying → Resolved`) that animates through the stages on scroll-into-view, proving the product's real state machine exists.
3. **"Evidence-grounded decisions" section** — A side-by-side of a hypothesis ranking table (reusing real visual language: confidence %, supporting/contradicting evidence counts) and a short "recovery plan" card with risk badge + approval button, scroll-revealed with staggered fade/slide (`framer-motion` `whileInView`).
4. **Metrics / trust strip** — A row of animated counters (e.g. "Alerts consolidated", "Mean time to recovery", "Actions gated by human approval") — counting up on scroll into view. These should be sourced from realistic, clearly-labelled *demo* numbers (not fabricated as "real customers", since this is a hackathon project — copy will say "demo environment" honestly, consistent with the blueprint's "no-go" list: never overclaim, never lie about what's real).
5. **Feature grid** — 5–6 cards (Real-time agent visibility, Human-in-the-loop approval, Evidence-first RCA, Automated rollback & verification, SSE-based live console, Role-based access) each with a small icon + one-line description, subtle 3D tilt-on-hover (`framer-motion`'s `whileHover` with rotateX/rotateY, cheap and GPU-friendly, no need for react-three here).
6. **Final CTA band** — Reiterates "Enter Command Center", plus a secondary "Explore without an account" link if login is disabled (see §3).
7. **Footer** — Minimal: product name, environment badge (Demo/Development), small links (GitHub/Docs if applicable) — reuses `.glass-panel`.

### 2.2 Motion/perf principles (carried over from the internal blueprint's "sparse, meaningful animation" rule)
- 3D scene renders at capped pixel ratio (`Math.min(devicePixelRatio, 2)`) and pauses `requestAnimationFrame` work when the tab is hidden or the hero section is scrolled out of view (use an `IntersectionObserver`-driven `active` flag passed into the R3F `<Canvas frameloop="demand"|"always">`).
- Respect `prefers-reduced-motion`: if set, skip camera auto-orbit and heavy parallax; keep only fade/opacity transitions (matches blueprint §21 accessibility rule).
- Lazy-load the R3F scene behind `React.lazy` + `Suspense` so the login page and dashboard bundles are not penalized by the 3D dependency weight.

---

## 3. Login screen + "disable login" switch

### 3.1 UX
- Route `/login`, reachable from the landing page's primary CTA (`/` → `/login` → on success → `/app`).
- Visual: split layout — left ~45% a condensed static reprise of the hero 3D scene (small `<Canvas>` reused as a decorative panel with slow idle rotation only, no scroll-linking needed here); right ~55% the actual form on a `.glass-panel` card:
  - Email + password fields (styled, client-validated, but not really required for auth to succeed — see below).
  - "Sign in" button → calls the existing mock-login endpoint (`GET /api/v2/auth/mock-login?role=commander`), stores the returned JWT in `localStorage['nemoguard_token']`, navigates to `/app`.
  - Small role selector (Commander / Admin / Viewer) mapped to the `role` query param — this is honest: it's clearly labelled "Demo role" so it doesn't pretend to be enterprise SSO while still feeling like a real gated app with RBAC.
  - "Forgot password" and "SSO with Okta/Google" as **visually present but disabled/tooltip-explained** buttons — reinforces "real SaaS" framing without lying about functionality (tooltip: "SSO integration available in production deployments").
- Footer link: "Continue without an account →" — only rendered when the disable-login switch (§3.2) is ON; clicking it sets a `guest` flag and also performs the same mock-login call under the hood (guest still needs *a* token to hit the real backend, since every incident endpoint requires `Authorization: Bearer <jwt>` per `auth.py`). This is the cleanest way to satisfy "switch to disable login" without breaking backend calls: **the switch does not remove authentication from the wire protocol — it removes the *human gate* in the UI.**

### 3.2 The "disable login" switch — design decision

Three options were considered:

| Option | Description | Verdict |
|---|---|---|
| A. Env var only (`VITE_REQUIRE_LOGIN=false` baked at build time) | Simple, but requires a rebuild to toggle — not a "switch you can flip whenever needed" | ❌ Too rigid for the ask |
| B. Runtime `localStorage` flag toggled from a hidden dev panel | Flexible, no rebuild, but not discoverable/demo-safe (a real operator could accidentally disable auth) | ⚠️ Useful as a *fallback*, not primary |
| **C. Runtime flag exposed as a visible, labelled toggle in a small "Demo Settings" affordance (gear icon, bottom-left corner, on both `/` and `/login`), persisted to `localStorage`, defaulting to "login required"** | Discoverable, reversible, no rebuild needed, and is itself presented as a legitimate feature ("Demo Mode") rather than a hack | ✅ **Chosen approach** |

**Chosen implementation (Option C):**
- New `AuthGateContext` (`src/contexts/AuthGateContext.tsx`) exposing `{ requireLogin: boolean, setRequireLogin: (v: boolean) => void }`, backed by `localStorage['nemoguard_require_login']` (default: `"true"`).
- A small floating `DemoModeToggle` component (bottom-left, both landing and login routes) — a switch labelled **"Demo Mode: skip login"** with an info icon explaining "For presentations. Real deployments should keep this off." This is honest and on-brand with the blueprint's "trust presentation" principles (§22 of the internal blueprint: never hide what's really happening).
- When `requireLogin === false`:
  - The landing page's primary CTA button label changes from "Sign in to enter" → "Enter Command Center" and goes straight to `/app` (silently performing the same mock-login call in the background, so the app still has a valid bearer token).
  - Visiting `/login` directly still shows the form (so the login page always stays demoable), but shows a banner: "Login is currently optional — Demo Mode is on."
- A **route guard** (`RequireAuth` wrapper, or a simple check inside `App`'s router) protects `/app/*`:
  - If `requireLogin === true` and there's no token in `localStorage`, redirect to `/login`.
  - If `requireLogin === false`, allow `/app/*` even without a prior explicit login click, transparently acquiring a token via the same mock-login call the first time it's needed (keeps existing `useAuthToken()` behavior as the "silent" fallback path).

This satisfies the literal ask — "a switch to disable login whenever needed" — while keeping the experience honest (it's presented *as* Demo Mode, not as a hidden bypass) and while not breaking the backend's real bearer-token requirement.

---

## 4. Dashboard personalization plan

### 4.1 Greeting
- Add a `GreetingBar` (or fold into `TopBar`) that renders "Good morning/afternoon/evening, `{name}`" based on local time + the user's name resolved from the JWT payload (decode client-side, no verification needed — purely cosmetic; email prefix as a fallback display name, e.g. `test@nemoguard.com` → "Test").
- Small one-line contextual sub-text under the greeting summarizing current state, e.g. "3 active incidents, 1 awaiting your approval" — sourced from data already being polled in `Dashboard.tsx` (no new backend calls).
- Shown once per session at the top of the Command Center (collapsible/dismissible via a small chevron, persisted per-session in `sessionStorage` so it doesn't nag on every incident refresh but does reappear on a fresh visit).

### 4.2 Left navigation with sections (replacing the current no-nav single view)
Introduce a slim, collapsible **Global Nav Rail** (72px collapsed / 220px expanded — matching the width spec already defined in the internal blueprint §6) with icon-only or icon+label items:

1. **Command Center** (existing Dashboard — default/home route `/app`)
2. **Incidents** — searchable history/queue view (new lightweight page reusing `IncidentQueue` list styling but as a full-width sortable/filterable table; can start as a simple wrapper around existing `/api/v2/incidents?state=all` data — no new backend work).
3. **Agent Operations** — a page listing recent/replayed agent runs, reusing `AgentConstellation` + event stream components in a read-only historical mode.
4. **What's New** — a dedicated panel (see §4.3) surfacing recent product changes.
5. **Settings** — theme, Demo Mode toggle relocated here (single source of truth instead of only being on the landing/login pages), notification preferences (visual only initially).

**Note (revised per user feedback):** Scenario Lab is dropped entirely — it added a page with no real backing functionality and cluttered the nav. Only sections with genuine content ship.

Each nav item gets a subtle top-border/left-border active-state highlight using existing `--color-primary` token, consistent with `.glass-panel`/`.press-scale` visual language — no new visual system invented.

### 4.2.1 Decluttering the Command Center itself (new, per user feedback)

The user's core complaint isn't just "add nav" — it's that the current single-view Command Center feels dense/cluttered and needs things "placed in the correct place." Concretely, today `Dashboard.tsx` renders, simultaneously, on one screen: incident queue (left) + situation header + alerts panel + agent/hypothesis row + activity/impact row (center) + recovery rail (right) — five to six visually competing panels with no breathing room, no grouping, and no progressive disclosure.

Redesign approach:
- **Group by intent, not by data source.** Today panels are arranged by *what API they came from* (alerts, hypothesis, impact, activity) rather than *what question the operator is asking*. Reorganize the center workspace into clearly delineated zones with generous spacing and section headers: "Situation" (header + stepper + metrics) → "What's happening" (agent constellation + live event stream, collapsed by default, expandable) → "Why" (hypothesis + evidence, tabbed rather than stacked) → "Impact" (only shown once impact data exists, not as an empty card).
- **Tabs instead of stacked rows.** `AgentAndHypothesisRow` and `ActivityAndImpactRow` currently stack multiple dense cards side-by-side unconditionally. Convert to a tabbed interface (Overview / Evidence / Impact / Activity) within the main workspace — matches the *already-designed* IA in the internal blueprint doc (§10) that was never implemented — so only one focused view is visible at a time instead of 4 simultaneous panels.
- **Collapse, don't remove.** Nothing that exists today gets deleted; it gets organized into expand/collapse sections (reusing the same disclosure pattern as `IncidentQueue`'s "Resolved" section, which already collapses cleanly) so the first viewport is calm (Situation + primary tab) and detail is one click away.
- **Recovery rail stays pinned** (per the internal blueprint's "climax of the screen" principle) but gets tightened — remove duplicate/redundant labels, consistent spacing scale (8px grid, per blueprint §20.4).
- **Queue simplification:** ensure the incident queue's visual hierarchy (severity → title → status) is the loudest signal; de-emphasize secondary metadata.

This decluttering pass happens in **Phase 3** (dashboard personalization), replacing the original "add nav only" scope — it's now "add nav + reorganize the existing workspace layout for clarity."

### 4.3 "New features" surfacing
- A `WhatsNewPanel` — a slide-in panel (reuse the existing `NotificationBell` dropdown pattern in `App.tsx` as the interaction template) triggered by a small "sparkle" badge in the nav rail's Settings/What's New entry.
- Content is a **static, versioned changelog array** shipped in the frontend bundle (`src/data/changelog.ts`), e.g.:
  ```ts
  export const CHANGELOG: ChangelogEntry[] = [
    { version: '1.3.0', date: '2026-08-10', title: 'Resolved incidents now show accurate time-to-resolve', tag: 'fix' },
    { version: '1.3.0', date: '2026-08-10', title: 'New landing experience and optional login', tag: 'feature' },
    { version: '1.2.0', date: '2026-08-01', title: 'Live agent event streaming via SSE', tag: 'feature' },
    ...
  ];
  ```
- A small red dot badge appears on the nav item until the latest entry's version has been "seen" (tracked via `localStorage['nemoguard_last_seen_changelog']`).
- This is deliberately simple (no backend/CMS) — appropriate for the project's scale, but instantly makes the product feel maintained and alive, which is exactly what was asked for ("new features etc to make it a complete app").

### 4.4 User menu
- Replace the static "SR" avatar in `TopBar` with a real dropdown: avatar initials derived from the JWT's `email`/`sub`, showing:
  - Name/email, role badge (commander/admin/viewer), tenant/workspace id (already present in the JWT payload — surfaces real backend data, reinforcing "how real this app is").
  - Theme toggle (moved here or kept in both places — decide during implementation; likely keep the quick-access icon in the topbar and duplicate the control inside the menu for discoverability).
  - "Demo Mode" shortcut linking to Settings.
  - "Sign out" — clears `localStorage['nemoguard_token']`, redirects to `/login` (or `/` if Demo Mode is on).

---

## 5. Routing plan

Introduce `react-router-dom` v6 (new dependency — currently absent). Route tree:

```
/                     → LandingPage (public)
/login                → LoginPage (public)
/app                  → RequireAuth → AppShell (TopBar + GlobalNavRail)
  /app                    → Dashboard (Command Center) [index]
  /app/incidents          → IncidentsPage
  /app/agent-operations   → AgentOperationsPage
  /app/settings           → SettingsPage
*                     → NotFound (redirects to /)
```

`main.tsx` changes from directly rendering `<App />` to rendering `<BrowserRouter><AppRoutes /></BrowserRouter>`, with `AppRoutes` defined in a new `src/app/routes.tsx` (matches the naming already anticipated in the internal blueprint's suggested component structure, §25).

**nginx compatibility:** already confirmed `try_files $uri $uri/ /index.html;` handles arbitrary client-side routes correctly — no server config changes needed.

---

## 6. New dependencies required

| Package | Purpose | Bundle-size mitigation |
|---|---|---|
| `react-router-dom` | Client-side routing for `/`, `/login`, `/app/*` | Small, no special handling needed |
| `three` | Core 3D engine, required peer of `@react-three/fiber` | Only imported by the landing page bundle (route-level code splitting via `React.lazy`) |
| `@react-three/fiber` | React renderer for Three.js — declarative 3D scene composition | Same as above |
| `@react-three/drei` | Helper primitives (`OrbitControls`, `Float`, `Line`, `Html`, `PerspectiveCamera`) to avoid hand-writing boilerplate Three.js | Same as above; only the specific helpers used are tree-shaken in where possible |

No other new dependencies are needed — `framer-motion` already covers all 2D scroll/hover animation, `lucide-react` covers all new icons (nav items, toggle, sparkle badge, etc.), and `recharts` can be reused if any landing-page "metric strip" wants an actual mini-chart instead of a plain counter.

**Total added dependency weight** is the primary technical risk of this whole plan (three.js + fiber + drei is typically 150–250kB gzipped). Mitigation: strictly isolate the 3D scene to the `/` route only, lazy-loaded, never imported by `/app/*` or `/login` bundles. The login page's "reprise" of the hero (§3.1) will use a **static screenshot/SVG loop** rather than a second live Canvas, to avoid pulling the 3D bundle into the login flow at all — this was reconsidered from the original idea and is the safer choice.

---

## 7. New file/component plan

```
frontend/src/
  app/
    routes.tsx                     # React Router route table
    RequireAuth.tsx                # Route guard component (checks AuthGateContext + token)
  contexts/
    AuthGateContext.tsx            # requireLogin flag + setter, localStorage-backed
    ThemeContext.tsx               # (existing, unchanged)
  data/
    changelog.ts                   # Static CHANGELOG array + types
  pages/
    LandingPage/
      LandingPage.tsx              # Top-level composition of all scroll sections
      HeroScene.tsx                # React-three-fiber Canvas + AgentConstellation3D
      AgentConstellation3D.tsx     # 3D node/edge visualization (mirrors AgentConstellation.tsx roles)
      LifecycleShowcase.tsx        # Animated lifecycle stepper section
      EvidenceShowcase.tsx         # Hypothesis + plan card scroll section
      MetricsStrip.tsx             # Animated counters
      FeatureGrid.tsx              # 3D-tilt feature cards
      CtaBand.tsx                  # Final CTA + guest link
      DemoModeToggle.tsx           # Shared floating toggle (also used on LoginPage)
    LoginPage/
      LoginPage.tsx                # Split layout, form, role selector, guest link
      LoginHeroPanel.tsx           # Static/looping visual reprise (no live 3D)
    IncidentsPage/
      IncidentsPage.tsx            # Full incident history table (reuses shared.tsx helpers)
    AgentOperationsPage/
      AgentOperationsPage.tsx      # Historical agent-run browser
    SettingsPage/
      SettingsPage.tsx             # Theme + Demo Mode + notification prefs
  components/
    shell/
      AppShell.tsx                 # Wraps TopBar + GlobalNavRail + <Outlet/>
      GlobalNavRail.tsx            # Collapsible left nav with sections
      GreetingBar.tsx              # Personalized greeting + quick stats
      UserMenu.tsx                 # Avatar dropdown (replaces static "SR" block)
      WhatsNewPanel.tsx            # Changelog slide-in panel
    dashboard/ ...                 # (existing, unchanged)
  hooks/
    useCurrentUser.ts              # Decodes JWT payload client-side → { email, roles, tenant_id, workspace_id }
    useGreeting.ts                 # Time-of-day greeting string helper
    ... (existing hooks unchanged)
```

`App.tsx` is retired as the root component; its current contents (TopBar layout, ThemeToggle, NotificationBell) get redistributed into `AppShell.tsx` + `UserMenu.tsx`/`GreetingBar.tsx`. `main.tsx` becomes:

```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <AuthGateProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthGateProvider>
    </ThemeProvider>
  </StrictMode>,
)
```

---

## 8. Data model & integration notes

### 8.1 `useCurrentUser` (client-side JWT decode)
No new backend endpoint required. Decode the existing JWT's payload (base64 middle segment) purely for display — never trust it for authorization (that's still enforced server-side via `require_role`/`get_current_user`). Returns `{ email, roles, tenant_id, workspace_id, displayName }` where `displayName` is derived (`email.split('@')[0]`, capitalized).

### 8.2 `AuthGateContext`
```ts
interface AuthGateContextValue {
  requireLogin: boolean;
  setRequireLogin: (v: boolean) => void;
}
```
Persisted key: `nemoguard_require_login` (`"true"` | `"false"`, default `"true"`).

### 8.3 `RequireAuth`
```tsx
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { requireLogin } = useAuthGate();
  const hasToken = !!localStorage.getItem('nemoguard_token');
  if (requireLogin && !hasToken) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```
Note: when `requireLogin` is false, `AppShell`'s mount effect calls the same silent mock-login (`useAuthToken()`-equivalent) to guarantee a bearer token exists before any `/api/v2/...` fetches fire — preserving all existing data-fetching code in `Dashboard.tsx`, `useIncidentData.ts`, etc. unchanged.

### 8.4 Optional backend addition (not required for v1)
If we want the login page's role selector to feel even more real, we could add a tiny `POST /api/v2/auth/login` that accepts `{email, password}` and, for any non-empty input, returns the same mock JWT (still gated by `ENV=development` in production, matching the existing mock-login's guard). This is **optional** and deferred — the existing `GET /api/v2/auth/mock-login?role=...` is sufficient to ship v1 without backend changes.

---

## 9. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Three.js/fiber/drei bundle bloat slows down `/app` or `/login` | Strict route-level code-splitting; 3D only ever imported by `LandingPage.tsx` via `React.lazy` |
| Scroll-jank on lower-end machines during the 3D hero | `frameloop="demand"` + IntersectionObserver pause-when-offscreen + capped pixel ratio + `prefers-reduced-motion` fallback to a static poster frame |
| React Router migration breaking existing incident-selection deep link behavior (`focusIncidentId` passed into `Dashboard`) | Preserve by passing `focusIncidentId` via route state/query param (`/app?incident=INC-xxxx`) instead of prop-drilling from `App.tsx`, migrated during Phase 3 below |
| "Disable login" switch being mistaken for an actual security bypass in a real deployment | All copy explicitly labels it "Demo Mode"; default is always `requireLogin = true`; documented here and in in-app tooltip text |
| Scope creep — trying to build too many nav sections fully | Ship Command Center (already done) + Settings + What's New fully; Incidents/Agent Operations as functional-but-simple wrappers of existing data. No placeholder/dead-end pages are shipped (Scenario Lab removed from scope entirely per user feedback) |
| TypeScript build breaking due to new router/3D types | Add `@types/three` if not bundled; run `tsc -b` after each phase, not just at the end |

---

## 10. Phased build order

1. **Phase 1 — Routing skeleton (no visual change to existing dashboard):**
   Add `react-router-dom`, create `routes.tsx`, wrap existing `Dashboard`+`TopBar` behavior inside `AppShell` at `/app`, redirect `/` → `/app` temporarily. Verify `tsc -b && vite build` passes and the app behaves identically to today at `/app`.
2. **Phase 2 — Auth gate + Login page:**
   Add `AuthGateContext`, `RequireAuth`, `LoginPage` (without the 3D reprise first — plain gradient panel), wire mock-login call, Demo Mode toggle, verify `/app` redirects to `/login` when gate is on and no token, and that guest/demo flow works.
3. **Phase 3 — Dashboard personalization + declutter:**
   Add `GreetingBar`, `UserMenu`, `GlobalNavRail` (Command Center, Incidents, Agent Operations, What's New, Settings — all real, no placeholders), `WhatsNewPanel` + `changelog.ts`. Reorganize the Command Center workspace per §4.2.1 (tabbed Overview/Evidence/Impact/Activity, collapsible agent console, tightened recovery rail). Migrate `focusIncidentId` to query-param based routing.
4. **Phase 4 — Landing page (2D pass):**
   Build all scroll sections with `framer-motion` only (no 3D yet) to lock copy, layout, spacing, and scroll-reveal timing against the real design tokens.
5. **Phase 5 — 3D hero upgrade:**
   Add `three`/`@react-three/fiber`/`@react-three/drei`, build `AgentConstellation3D`, wire scroll-linked camera motion, perf-gate with IntersectionObserver + reduced-motion checks, lazy-load behind `Suspense`.
6. **Phase 6 — Polish & verification:**
   Full `tsc -b && vite build` pass, manual check of both themes (light/dark) on every new page, Docker rebuild + redeploy, smoke-test the full flow: `/` → toggle Demo Mode → `/login` (or skip) → `/app` → navigate all nav sections → sign out → back to `/login`.

---

## 11. Acceptance criteria for this initiative

- [ ] Visiting `/` shows a full-bleed 3D scroll-driven landing page that visually echoes the real in-app agent constellation, lifecycle stepper, and hypothesis/plan UI.
- [ ] Visiting `/login` shows a polished split-layout login form; submitting it (with any role selected) grants access to `/app`.
- [ ] A visible, labelled "Demo Mode" toggle exists and reliably lets a user skip the login screen and land directly in `/app` while the backend still receives a valid bearer token on every request.
- [ ] `/app` now has a personalized greeting (time-of-day + resolved display name), a collapsible left nav rail with 5 real sections (Command Center, Incidents, Agent Operations, What's New, Settings — no placeholder/dead pages), a real user dropdown menu (replacing the static "SR" avatar), and a "What's New" changelog panel with an unread-indicator badge.
- [ ] `tsc -b && vite build` passes cleanly with no new type errors.
- [ ] Both dark and light themes render correctly on every new page (landing, login, all nav sections).
- [ ] The frontend Docker image builds and the `nemoguard-frontend` container starts successfully; `curl http://localhost/` returns 200 for `/`, `/login`, and `/app`.
- [ ] No secrets, raw credentials, or unmasked backend internals are exposed anywhere in the new UI (consistent with the existing security/trust principles already documented in the internal blueprint).

---

## 12. Decisions confirmed with the user

1. **3D library:** Approved — proceed with `react-three-fiber` + `drei` for a genuine 3D hero, isolated to the landing page route only.
2. **Login realism:** Approved — "Sign in" uses the existing mock-login (no real password check), clearly labelled as a demo/role-based sign-in.
3. **Scenario Lab:** **Removed from scope entirely.** The user explicitly does not want a Scenario Lab page — it would be a placeholder with no real functionality and adds clutter for no benefit.
4. **Core redesign directive (user feedback, incorporated into §4.2.1):** The primary ask is not just "add navigation" — it's a genuine reorganization of where things live in the UI so the product feels user-friendly and uncluttered. This is now a first-class part of Phase 3, not an afterthought: the Command Center's dense stacked-panel layout is being restructured into grouped, tabbed, progressively-disclosed sections (Situation → What's happening → Why → Impact), with the recovery rail tightened and the incident queue's visual hierarchy sharpened.

This plan is now finalized and ready for implementation.
