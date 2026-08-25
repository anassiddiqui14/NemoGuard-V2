/**
 * NemoGuard brand mark: a perimeter-watch glyph — four corner brackets
 * framing a live pulse. It reads as "something is being watched, in real
 * time" without resorting to sparkles, robot glyphs, or gradient blobs.
 */
export function Logomark({ className = 'w-6 h-6' }: { className?: string }) {
    return (
        <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
            <path d="M4 11V6a2 2 0 0 1 2-2h5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M28 11V6a2 2 0 0 0-2-2h-5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M4 21v5a2 2 0 0 0 2 2h5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M28 21v5a2 2 0 0 1-2 2h-5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
            <circle cx="16" cy="16" r="3.4" fill="currentColor" />
            <circle cx="16" cy="16" r="7" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.4" />
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
