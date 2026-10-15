import { useEffect, useRef } from 'react';

/*
 * UI MODERNIZATION (Phase 14, spec Section 21 -- component ownership /
 * reuse over duplication): the identical "close this dropdown when
 * clicking outside it" pattern (a ref + useEffect + mousedown listener)
 * was independently hand-written in both UserMenu.tsx and AppShell.tsx's
 * NotificationBell. Both would silently drift out of sync if one needed
 * a behavior tweak (e.g. also closing on Escape) without the other
 * getting it. This hook consolidates that pattern into one place.
 */
export function useClickOutside<T extends HTMLElement>(onOutsideClick: () => void) {
    const ref = useRef<T>(null);

    useEffect(() => {
        const handleClick = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) {
                onOutsideClick();
            }
        };
        document.addEventListener('mousedown', handleClick);
        return () => document.removeEventListener('mousedown', handleClick);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return ref;
}
