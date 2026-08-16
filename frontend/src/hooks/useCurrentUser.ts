import { useEffect, useState } from 'react';

export interface CurrentUser {
    email: string;
    roles: string[];
    tenantId: string;
    workspaceId: string;
    displayName: string;
    initials: string;
}

function decodeJwtPayload(token: string): any | null {
    try {
        const parts = token.split('.');
        if (parts.length < 2) return null;
        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
        const json = atob(padded);
        return JSON.parse(json);
    } catch {
        return null;
    }
}

function displayNameFromEmail(email: string): string {
    const local = email.split('@')[0] || email;
    return (
        local
            .split(/[._\-]+/)
            .filter(Boolean)
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' ') || email
    );
}

function buildUser(payload: any): CurrentUser {
    const email: string = payload?.email || 'unknown@nemoguard';
    const roles: string[] = payload?.roles || ['viewer'];
    const tenantId: string = payload?.tenant_id || 'default_tenant';
    const workspaceId: string = payload?.workspace_id || 'default_workspace';
    const displayName = displayNameFromEmail(email);
    const initials =
        displayName
            .split(/\s+/)
            .filter(Boolean)
            .slice(0, 2)
            .map((p) => p[0]?.toUpperCase())
            .join('') || 'U';

    return { email, roles, tenantId, workspaceId, displayName, initials };
}

const DEFAULT_USER: CurrentUser = {
    email: '',
    roles: ['viewer'],
    tenantId: 'default_tenant',
    workspaceId: 'default_workspace',
    displayName: 'Signed out',
    initials: '—',
};

/** Reads the JWT from localStorage and decodes it client-side purely for display. */
export function useCurrentUser(): CurrentUser {
    const [user, setUser] = useState<CurrentUser>(DEFAULT_USER);

    useEffect(() => {
        const readUser = () => {
            const token = localStorage.getItem('nemoguard_token');
            if (!token) {
                setUser(DEFAULT_USER);
                return;
            }
            const payload = decodeJwtPayload(token);
            setUser(payload ? buildUser(payload) : DEFAULT_USER);
        };

        readUser();
        window.addEventListener('storage', readUser);
        return () => window.removeEventListener('storage', readUser);
    }, []);

    return user;
}
