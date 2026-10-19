/**
 * NemoGuard glyph set — rebuilt around the sonar-ring brand motif (see
 * Brand.tsx) instead of the previous generic "four corner brackets"
 * frame every icon shared. That frame made every custom icon in the app
 * read as near-identical variations of the same shape, undermining the
 * point of having bespoke icons at all. Each icon below now has its own
 * distinct silhouette, with only a thin outer ring (echoing the
 * Logomark's sonar aperture, not literally repeating it) as the shared
 * family cue -- the way a real icon system works: a family resemblance
 * in weight/proportion, not an identical stamped-out container.
 */
import type { SVGProps } from 'react';

function Ring({ children, ...props }: SVGProps<SVGSVGElement> & { children: React.ReactNode }) {
    return (
        <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
            <circle cx="10" cy="10" r="8.6" stroke="currentColor" strokeWidth="1.1" strokeOpacity="0.22" />
            {children}
        </svg>
    );
}

export function CommandCenterIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <circle cx="10" cy="10" r="2" fill="currentColor" />
            <circle cx="10" cy="10" r="5.2" stroke="currentColor" strokeWidth="1.3" strokeOpacity="0.55" />
            <path d="M10 1.4a8.6 8.6 0 0 1 7.2 3.9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </Ring>
    );
}

export function IncidentsIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M10 5c2.4 0 4.3 2 4.3 4.5 0 3-4.3 6.6-4.3 6.6S5.7 12.5 5.7 9.5C5.7 7 7.6 5 10 5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
            <circle cx="10" cy="9.3" r="1.3" fill="currentColor" />
        </Ring>
    );
}

export function EvidenceGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M6 6.5h5.4M6 9.3h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
            <circle cx="12.4" cy="12.2" r="2.6" stroke="currentColor" strokeWidth="1.4" />
            <path d="M14.3 14.1l1.6 1.6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </Ring>
    );
}

export function RecoveryGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M14.5 7.3a4.6 4.6 0 1 0 .7 5.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" fill="none" />
            <path d="M14.1 5.6l1.2 2.6-2.7.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        </Ring>
    );
}

export function MemoryGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M10 5.4 15 7.8 10 10.2 5 7.8 10 5.4Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            <path d="M5 11.2 10 13.6l5-2.4M5 14.6l5 2.4 5-2.4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" strokeOpacity="0.75" />
        </Ring>
    );
}

export function GuardrailGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M10 4.8c2.6 1 4.3 1 4.3 1v4.6c0 3-2 5.2-4.3 5.8-2.3-.6-4.3-2.8-4.3-5.8V5.8s1.7 0 4.3-1Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            <path d="M10 8.2v3.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            <circle cx="10" cy="13.4" r="0.5" fill="currentColor" />
        </Ring>
    );
}

export function InvestigationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <circle cx="7.4" cy="7.4" r="1" fill="currentColor" opacity="0.4" />
            <circle cx="12" cy="6.2" r="1" fill="currentColor" opacity="0.6" />
            <circle cx="14.2" cy="10.6" r="1" fill="currentColor" opacity="0.8" />
            <circle cx="10.8" cy="13.4" r="1.6" fill="currentColor" />
            <path d="M7.4 7.4 12 6.2M12 6.2l2.2 4.4M14.2 10.6l-3.4 2.8" stroke="currentColor" strokeWidth="1" strokeOpacity="0.45" />
        </Ring>
    );
}

export function AutomationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <circle cx="10" cy="10" r="2.3" stroke="currentColor" strokeWidth="1.4" />
            <path d="M10 5v1.6M10 13.4V15M15 10h-1.6M6.6 10H5M13.2 6.8l-1.1 1.1M7.9 12.1l-1.1 1.1M13.2 13.2l-1.1-1.1M7.9 7.9 6.8 6.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.7" />
        </Ring>
    );
}

export function ModelEvaluationGlyphIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M6.2 14V9.6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity="0.5" />
            <path d="M10 14V6.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M13.8 14v-6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity="0.5" />
            <path d="M5.6 14.5h8.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeOpacity="0.4" />
        </Ring>
    );
}

export function AgentOpsIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <circle cx="10" cy="6.3" r="1.5" fill="currentColor" />
            <circle cx="6.1" cy="13.2" r="1.5" fill="currentColor" />
            <circle cx="13.9" cy="13.2" r="1.5" fill="currentColor" />
            <path d="M10 7.8 6.9 12M10 7.8l3.1 4.2M7.6 13.2h4.8" stroke="currentColor" strokeWidth="1" strokeOpacity="0.45" strokeLinecap="round" />
        </Ring>
    );
}

export function IntelligenceIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M4.6 10h2.5l1.3-3.2 2.1 6.4 1.4-3.2h3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </Ring>
    );
}

export function ScenarioIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <circle cx="6.2" cy="6.4" r="1.3" fill="currentColor" />
            <circle cx="6.2" cy="13.6" r="1.3" fill="currentColor" />
            <circle cx="14" cy="10" r="1.6" fill="currentColor" />
            <path d="M6.2 7.7v4.6M6.2 6.4h3.4l4.4 2.6M6.2 13.6h3.4l4.4-2.6" stroke="currentColor" strokeWidth="1.1" strokeOpacity="0.6" strokeLinecap="round" />
        </Ring>
    );
}

export function AdoptionIcon(props: SVGProps<SVGSVGElement>) {
    return (
        <Ring {...props}>
            <path d="M5.4 13.6h2v-2.4h-2v2.4Zm3.4 0h2V9.2h-2v4.4Zm3.4 0h2V6.4h-2v7.2Z" fill="currentColor" opacity="0.85" />
            <path d="M5.4 6.4l3.8 2.4 2.6-3.2 3 1.8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" strokeOpacity="0.5" />
        </Ring>
    );
}
