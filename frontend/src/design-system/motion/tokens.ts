/*
 * NemoGuard design-system motion tokens.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 16/17):
 * Audited the codebase before writing this -- found 33+ distinct inline
 * `transition={{ duration: 0.XX }}` call sites across components, with
 * durations ranging 0.15-0.6s with no shared vocabulary (some panels use
 * 0.18s, others 0.22s, 0.25s, 0.28s, 0.3s, 0.35s, 0.5s, 0.6s for what are
 * functionally the same kind of transition -- a card/row fading in).
 * shared.tsx already had the right idea (fadeInUp/fadeIn/modalBackdrop/
 * modalPanel presets) but most components still write their own inline
 * values instead of reusing them. This file centralizes the vocabulary so
 * future (and migrated) components reach for a named duration instead of
 * picking an arbitrary number.
 *
 * CRITICAL FINDING (verified, not hypothetical): the CSS
 * `prefers-reduced-motion` media query in index.css only disables CSS
 * transitions/@keyframes -- it has NO effect on Framer Motion's
 * JS-driven transform/opacity animations (every `motion.div` with
 * `animate={{opacity:1,y:0}}` etc). grep confirmed `useReducedMotion`
 * (Framer Motion's actual reduced-motion hook) is used NOWHERE in the
 * codebase. This means every one of those 33+ animated components
 * currently still animates for users who have explicitly requested
 * reduced motion at the OS level.
 *
 * FIX: rather than requiring every one of those 33+ call sites to be
 * individually migrated to check a reduced-motion flag, Framer Motion
 * ships <MotionConfig reducedMotion="user"> -- wrapping the app root in
 * it (see main.tsx) automatically disables transform/layout animation
 * for every motion.* component in the subtree when the OS-level
 * preference is set, with zero per-component changes required. This is
 * the actual fix for the gap described above.
 *
 * `useMotionPreference()` below remains available for the rare case
 * where a component needs to brach its OWN logic (not just suppress
 * animation) based on the user's preference -- e.g. skipping a
 * multi-step staggered reveal entirely rather than just making it
 * instant.
 */
import { useReducedMotion } from 'framer-motion';

export const duration = {
    instant: 0.08,
    fast: 0.12,
    normal: 0.18,
    emphasized: 0.24,
    slow: 0.32,
} as const;

export const easing = {
    standard: [0.2, 0, 0, 1] as const,
    enter: [0.16, 1, 0.3, 1] as const,
    exit: [0.4, 0, 1, 1] as const,
};

export const spring = {
    interactive: {
        type: 'spring' as const,
        stiffness: 420,
        damping: 32,
    },
};

/*
 * Central reduced-motion hook. Components that build their own motion
 * variants (rather than using the shared presets in dashboard/shared.tsx,
 * which should be migrated to call this too) should call this and
 * collapse their transition duration to ~0 when true, per spec Section 19:
 * "no unnecessary transform animations" / "instant or near-instant
 * transitions where appropriate" under reduced motion.
 *
 * Usage:
 *   const prefersReducedMotion = useMotionPreference();
 *   transition={{ duration: prefersReducedMotion ? 0 : duration.normal }}
 */
export function useMotionPreference(): boolean {
    return useReducedMotion() ?? false;
}
