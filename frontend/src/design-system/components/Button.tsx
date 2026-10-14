import React from 'react';
import { Loader2 } from 'lucide-react';

/*
 * NemoGuard design-system Button primitive.
 *
 * WHY THIS EXISTS (UI Modernization Spec, Section 21/66):
 * Audited the codebase before writing this -- the "primary filled button"
 * pattern (press-scale + rounded-lg/xl + bg-primary + text-white +
 * disabled:opacity-50 + loading-spinner-swap) was independently
 * hand-written 7+ times across TeamsRoutesTab, ModelEvaluationTab,
 * ModelSettingsTab, IncidentMemoryTab, RecoveryRail, CommanderPanel, and
 * HeroSection -- each with slightly different padding/sizing/disabled
 * opacity values. This component consolidates that into one place while
 * preserving the EXACT existing visual language (same press-scale
 * micro-interaction, same color tokens, same radii) so it's a drop-in
 * replacement rather than a redesign.
 *
 * Variants/sizes map directly onto patterns already observed in the
 * codebase -- nothing here is invented from scratch.
 */

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'quiet';
type Size = 'sm' | 'md' | 'lg';

export interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'className'> {
    variant?: Variant;
    size?: Size;
    loading?: boolean;
    leadingIcon?: React.ReactNode;
    trailingIcon?: React.ReactNode;
    fullWidth?: boolean;
    className?: string;
}

const variantClasses: Record<Variant, string> = {
    primary: 'bg-primary text-white hover:brightness-110 disabled:opacity-50',
    secondary: 'bg-white/[0.04] text-text-secondary ring-1 ring-white/[0.08] hover:bg-white/[0.07] hover:text-text-primary disabled:opacity-40',
    ghost: 'bg-primary/15 text-primary ring-1 ring-primary/30 hover:bg-primary/20 disabled:opacity-40',
    danger: 'bg-critical/15 text-critical ring-1 ring-critical/30 hover:bg-critical/20 disabled:opacity-40',
    quiet: 'text-text-secondary hover:text-text-primary hover:bg-white/[0.04] disabled:opacity-40',
};

const sizeClasses: Record<Size, string> = {
    sm: 'text-[11.5px] px-3 py-1.5 rounded-lg gap-1.5',
    md: 'text-[12.5px] px-4 py-2.5 rounded-xl gap-2',
    lg: 'text-[14.5px] px-6 py-3 rounded-xl gap-2',
};

export function Button({
    variant = 'primary',
    size = 'md',
    loading = false,
    leadingIcon,
    trailingIcon,
    fullWidth = false,
    disabled,
    children,
    className = '',
    ...rest
}: ButtonProps) {
    return (
        <button
            disabled={disabled || loading}
            // press-scale is the existing app-wide micro-interaction utility
            // (src/index.css) -- reused rather than reinvented so this
            // component feels identical to every hand-rolled button it
            // replaces.
            className={`press-scale focus-ring inline-flex items-center justify-center font-semibold transition-colors disabled:cursor-not-allowed ${variantClasses[variant]} ${sizeClasses[size]} ${fullWidth ? 'w-full' : ''} ${className}`}
            {...rest}
        >
            {loading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
                leadingIcon
            )}
            {children}
            {!loading && trailingIcon}
        </button>
    );
}
