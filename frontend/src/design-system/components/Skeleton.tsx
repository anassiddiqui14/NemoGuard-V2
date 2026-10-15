/*
 * NemoGuard design-system Skeleton primitives.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 38/41/63):
 * Audited loading states across the app -- every single one is a plain
 * text string ("Loading incidents…", "Loading scorecard...", "Loading
 * runs...") with a spinner icon at best. The spec explicitly calls for
 * structural skeletons that approximate the final layout (table rows,
 * cards) rather than a generic spinner, reserving spinners for localized
 * actions (buttons) -- which the Phase 2 Button primitive already
 * handles correctly.
 *
 * `shimmer` is the existing app-wide CSS animation utility (index.css) --
 * reused here rather than re-implemented, and it's automatically
 * disabled under `prefers-reduced-motion` via the existing global rule
 * in index.css, so no extra reduced-motion handling is needed here.
 */

export function SkeletonBlock({ className = '' }: { className?: string }) {
    return <div className={`shimmer rounded-md bg-white/[0.04] ${className}`} />;
}

/** Approximates a table's row structure instead of a blank "Loading…" row. */
export function SkeletonTableRows({ columns = 4, rows = 5 }: { columns?: number; rows?: number }) {
    return (
        <>
            {Array.from({ length: rows }).map((_, r) => (
                <tr key={r} className="border-b border-white/[0.04] last:border-b-0">
                    {Array.from({ length: columns }).map((_, c) => (
                        <td key={c} className="px-4 py-3">
                            <SkeletonBlock className={`h-3.5 ${c === 0 ? 'w-20' : c === columns - 1 ? 'w-14' : 'w-32'}`} />
                        </td>
                    ))}
                </tr>
            ))}
        </>
    );
}

/** Approximates the IncidentQueue's row card structure. */
export function SkeletonQueueRows({ count = 4 }: { count?: number }) {
    return (
        <div className="space-y-2">
            {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="rounded-xl p-3.5 bg-white/[0.02] ring-1 ring-white/[0.04]">
                    <div className="flex items-center gap-2 mb-2">
                        <SkeletonBlock className="h-4 w-14 rounded-full" />
                        <SkeletonBlock className="h-3 w-16 ml-auto" />
                    </div>
                    <SkeletonBlock className="h-3.5 w-full mb-1.5" />
                    <SkeletonBlock className="h-3.5 w-3/4 mb-2.5" />
                    <SkeletonBlock className="h-2.5 w-20" />
                </div>
            ))}
        </div>
    );
}

/** Generic card skeleton for dashboard/metric-style blocks. */
export function SkeletonCard({ className = '' }: { className?: string }) {
    return (
        <div className={`rounded-xl p-3.5 bg-white/[0.02] ring-1 ring-white/[0.05] ${className}`}>
            <SkeletonBlock className="h-3 w-16 mb-2" />
            <SkeletonBlock className="h-6 w-12 mb-1" />
            <SkeletonBlock className="h-2.5 w-20" />
        </div>
    );
}
