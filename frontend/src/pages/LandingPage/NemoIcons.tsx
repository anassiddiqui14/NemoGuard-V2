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
