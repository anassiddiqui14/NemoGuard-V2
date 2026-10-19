/**
 * NemoGuard brand mark -- a sonar/periscope ring, not corner brackets.
 *
 * BRAND IDENTITY OVERHAUL: "NemoGuard" draws its name from Captain Nemo's
 * Nautilus -- a vessel that watches from the deep and surfaces only when
 * something needs attention. That gives the product a genuine, ownable
 * visual concept instead of a generic "AI SaaS" gradient-blob identity:
 * concentric sonar rings with an active ping sweep, like a periscope
 * scanning for threats below the surface. Every bespoke icon in the app
 * now shares this same ring-frame motif (see NemoIcons.tsx) instead of
 * the previous "four corner brackets" frame, which read as interchangeable
 * with any other dashboard product's generic "monitoring" icon set.
 */
export function Logomark({ className = 'w-6 h-6' }: { className?: string }) {
    return (
        <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
            {/* Outer sonar ring -- the periscope aperture */}
            <circle cx="16" cy="16" r="13.5" stroke="currentColor" strokeWidth="1.6" strokeOpacity="0.3" />
            {/* Mid ring -- a single "ping" ripple, deliberately not centered
                evenly, so it reads as an active scan rather than a static
                bullseye */}
            <circle cx="16" cy="16" r="9.2" stroke="currentColor" strokeWidth="1.8" strokeOpacity="0.55" />
            {/* Sweep arc -- the one asymmetric element that makes this read
                as "actively scanning" rather than a generic target icon */}
            <path d="M16 2.5a13.5 13.5 0 0 1 11.3 6.2" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
            {/* Core -- the submerged contact being tracked */}
            <circle cx="16" cy="16" r="3.6" fill="currentColor" />
        </svg>
    );
}

export function Wordmark({ className = '' }: { className?: string }) {
    return (
        <span className={`font-semibold tracking-tight text-text-primary ${className}`}>
            Nemo<span className="text-primary">Guard</span>
        </span>
    );
}

export function BrandLockup({ iconClassName = 'w-6 h-6', textClassName = 'text-[15px]' }: { iconClassName?: string; textClassName?: string }) {
    return (
        <span className="inline-flex items-center gap-2 text-primary">
            <Logomark className={iconClassName} />
            <Wordmark className={textClassName} />
        </span>
    );
}
