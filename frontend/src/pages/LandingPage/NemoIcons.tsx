/**
 * NemoGuard glyph set — a small family of custom nav/section icons that
 * share the perimeter-watch frame used in the primary Logomark (four
 * corner brackets) so the product's top-level navigation carries the
 * same identity as the marketing surface, instead of borrowing generic
 * icon-library glyphs for every section.
 */
import type { SVGProps } from 'react';

function Frame({ children, ...props }: SVGProps<SVGSVGElement> & { children: React.ReactNode }) {
    return (
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
            <path d="M2.5 6.5V4.2A1.2 1.2 0 0 1 3.7 3h2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.45" />
            <path d="M17.5 6.5V4.2A1.2 1.2 0 0 0 16.3 3h-2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.45" />
            <path d="M2.5 13.5v2.3A1.2 1.2 0 0 0 3.7 17h2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.45" />
            <path d="M17.5 13.5v2.3a1.2 1.2 0 0 1-1.2 1.2h-2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeOpacity="0.45" />
            {children}
        </svg>
    );
}

export function CommandCenterIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <circle cx="10" cy="10" r="2.1" fill="currentColor" />
            <circle cx="10" cy="10" r="4.6" stroke="currentColor" strokeWidth="1.3" strokeOpacity="0.5" />
        </Frame>
    );
}

export function IncidentsIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M10 6.6v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            <circle cx="10" cy="13.1" r="0.95" fill="currentColor" />
        </Frame>
    );
}

/*
 * UI MODERNIZATION (spec Section 48 -- bespoke icon set for product
 * concepts): the original 6 icons here covered top-level nav items only.
 * The spec explicitly names Evidence, Recovery, and Memory as product
 * concepts that should get bespoke glyphs rather than generic
 * Lucide icons, specifically because they're NemoGuard-specific
 * domain concepts (not generic UI actions like "search" or "close",
 * which Lucide already handles correctly per spec Section 48's own
 * "use Lucide for generic actions" guidance). These 3 extend the same
 * Frame wrapper for visual consistency with the existing 6.
 */
export function EvidenceGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M7 6h6M7 9h6M7 12h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx="14.2" cy="13" r="2.1" stroke="currentColor" strokeWidth="1.3" />
            <path d="M15.8 14.6l1.2 1.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </Frame>
    );
}

export function RecoveryGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M13.5 7.2a4 4 0 1 0 .8 4.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
            <path d="M13.1 5.6l1.1 2.4-2.5.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </Frame>
    );
}

export function MemoryGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <rect x="6.3" y="6.3" width="7.4" height="7.4" rx="1.4" stroke="currentColor" strokeWidth="1.4" />
            <circle cx="10" cy="10" r="1.3" fill="currentColor" />
        </Frame>
    );
}

/*
 * UI MODERNIZATION (spec Section 48 completion): the spec's exact named
 * bespoke icon set is: "NemoGuard mark, Agent, Guardrail, Incident,
 * Investigation, Recovery, Scenario, Intelligence, Evidence,
 * Automation, Memory, Model Evaluation." Of these, Guardrail,
 * Investigation, Automation, and Model Evaluation were still missing --
 * these 4 close that gap, completing the full named set.
 */
export function GuardrailGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M10 5.4 13.6 6.8v2.9c0 2.3-1.5 3.9-3.6 4.5-2.1-.6-3.6-2.2-3.6-4.5V6.8L10 5.4Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            <path d="M10 8.1v2.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx="10" cy="12" r="0.55" fill="currentColor" />
        </Frame>
    );
}

export function InvestigationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <circle cx="8.9" cy="9" r="2.9" stroke="currentColor" strokeWidth="1.4" />
            <path d="M8.9 7.4v1.6l1.1 1.1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
            <path d="M11 11.1l2.9 2.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </Frame>
    );
}

export function AutomationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="1.4" />
            <path d="M10 5.6v1.5M10 12.9v1.5M14.4 10h-1.5M7.1 10H5.6M13.1 6.9l-1.1 1.1M7.9 12l-1.1 1.1M13.1 13.1l-1.1-1.1M7.9 8l-1.1-1.1" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.65" />
        </Frame>
    );
}

export function ModelEvaluationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M6.4 13.4V9.1M10 13.4V6.6M13.6 13.4v-4.9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            <path d="M5.8 13.9h8.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeOpacity="0.5" />
        </Frame>
    );
}

export function AgentOpsIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <circle cx="10" cy="6.6" r="1.3" fill="currentColor" />
            <circle cx="6.6" cy="13.2" r="1.3" fill="currentColor" />
            <circle cx="13.4" cy="13.2" r="1.3" fill="currentColor" />
            <path d="M10 7.9 6.9 12M10 7.9l3.1 4.1M7.6 13.5h4.8" stroke="currentColor" strokeWidth="1.15" strokeOpacity="0.6" strokeLinecap="round" />
        </Frame>
    );
}

export function IntelligenceIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <circle cx="8.6" cy="9.4" r="3.05" stroke="currentColor" strokeWidth="1.5" />
            <path d="M11 11.8l2.6 2.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </Frame>
    );
}

export function ScenarioIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M8.3 6.3v7.4l5.1-3.7-5.1-3.7Z" fill="currentColor" />
        </Frame>
    );
}

export function AdoptionIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Frame {...props}>
            <path d="M10 5.6 14 7v3.3c0 2.5-1.7 4.2-4 4.9-2.3-.7-4-2.4-4-4.9V7l4-1.4Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            <path d="M8.3 9.9l1.3 1.3 2.1-2.4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </Frame>
    );
}
