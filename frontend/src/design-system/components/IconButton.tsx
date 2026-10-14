import React from 'react';

/*
 * NemoGuard design-system IconButton primitive.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 18):
 * Icon-only buttons (close, refresh, collapse-nav, notification-bell, etc.)
 * were hand-written at every call site with the same recipe --
 * `press-scale p-1.5/p-2 rounded-lg text-text-muted hover:text-text-primary
 * hover:bg-white/[0.05]` -- but with inconsistent padding (p-1, p-1.5, p-2)
 * producing inconsistent hit areas, and inconsistent accessible-name
 * handling (`title` sometimes present, sometimes missing entirely). The
 * spec explicitly calls for a minimum ~36x36px hit area and a mandatory
 * accessible label for every icon-only control.
 *
 * This component enforces both by construction: the `label` prop is
 * REQUIRED (not optional) and is wired to both `aria-label` and `title`,
 * and the default padding guarantees a consistent minimum hit area across
 * every icon button in the app.
 */

type Size = 'sm' | 'md' | 'lg';

export interface IconButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
    /** Required -- every icon-only control must have an accessible name. */
    label: string;
    size?: Size;
    active?: boolean;
    className?: string;
}

const sizeClasses: Record<Size, string> = {
    sm: 'p-1.5', // ~30px hit area, for dense inline contexts (table row actions)
    md: 'p-2', // ~36px hit area, the spec's minimum target -- default
    lg: 'p-2.5', // ~40px, for primary toolbar/topbar actions
};

export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
    ({ label, size = 'md', active = false, className = '', children, ...rest }, ref) => {
        return (
            <button
                ref={ref}
                aria-label={label}
                title={label}
                className={`press-scale focus-ring relative inline-flex items-center justify-center rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${sizeClasses[size]} ${active
                    ? 'bg-primary/[0.12] text-primary ring-1 ring-primary/25'
                    : 'text-text-secondary hover:text-text-primary hover:bg-white/[0.05]'
                    } ${className}`}
                {...rest}
            >
                {children}
            </button>
        );
    },
);
IconButton.displayName = 'IconButton';
