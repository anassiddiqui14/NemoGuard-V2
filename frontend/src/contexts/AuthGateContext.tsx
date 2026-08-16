import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';

interface AuthGateContextValue {
    // Whether the mock/no-credential login endpoint is reachable at all in
    // THIS deployment (server-derived; only ever true when the API's ENV is
    // development/dev/local). Replaces the old client-only `requireLogin`
    // toggle, which let anyone flip a switch in Settings and bypass sign-in
    // even in a real deployment.
    devLoginEnabled: boolean;
    // Whether real email/password sign-in is available (i.e. at least one
    // active platform_user account has been provisioned via
    // scripts/create_user.py). Once true, this is a real production
    // deployment and the login screen should not advertise any bypass.
    credentialLoginEnabled: boolean;
    loading: boolean;
    refresh: () => void;
}

const TOKEN_KEY = 'nemoguard_token';

const AuthGateContext = createContext<AuthGateContextValue>({
    devLoginEnabled: false,
    credentialLoginEnabled: false,
    loading: true,
    refresh: () => { },
});

export function AuthGateProvider({ children }: { children: React.ReactNode }) {
    const [devLoginEnabled, setDevLoginEnabled] = useState(false);
    const [credentialLoginEnabled, setCredentialLoginEnabled] = useState(false);
    const [loading, setLoading] = useState(true);

    const load = useCallback(() => {
        setLoading(true);
        fetch('/api/v2/auth/config')
            .then((r) => (r.ok ? r.json() : { dev_login_enabled: false, credential_login_enabled: false }))
            .then((data) => {
                setDevLoginEnabled(!!data.dev_login_enabled);
                setCredentialLoginEnabled(!!data.credential_login_enabled);
            })
            .catch(() => {
                setDevLoginEnabled(false);
                setCredentialLoginEnabled(false);
            })
            .finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    return (
        <AuthGateContext.Provider value={{ devLoginEnabled, credentialLoginEnabled, loading, refresh: load }}>
            {children}
        </AuthGateContext.Provider>
    );
}

export function useAuthGate() {
    return useContext(AuthGateContext);
}

/**
 * Decodes a JWT's payload without verifying its signature -- purely so the
 * frontend can inspect claims like `exp` for expiry-check purposes. The
 * backend is always the source of truth for actual verification.
 */
function decodeJwtPayload(token: string): any | null {
    try {
        const parts = token.split('.');
        if (parts.length < 2) return null;
        const payload = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const padded = payload + '='.repeat((4 - (payload.length % 4)) % 4);
        return JSON.parse(atob(padded));
    } catch {
        return null;
    }
}

/**
 * True if `token` is a well-formed JWT whose `exp` claim is still in the
 * future (with a 30s safety buffer).
 */
function isTokenValid(token: string): boolean {
    const payload = decodeJwtPayload(token);
    if (!payload || typeof payload.exp !== 'number') return false;
    const nowSeconds = Date.now() / 1000;
    return payload.exp - 30 > nowSeconds;
}

/**
 * Silently mints a development-only token via the mock-login endpoint. Only
 * ever succeeds when the API's ENV is development/dev/local (the endpoint
 * 404s otherwise) -- this is NOT a way to bypass authentication in a real
 * deployment.
 */
export async function acquireDemoToken(role: string = 'commander'): Promise<string | null> {
    const existing = localStorage.getItem(TOKEN_KEY);
    if (existing && isTokenValid(existing)) return existing;
    if (existing) localStorage.removeItem(TOKEN_KEY);
    try {
        const res = await fetch(`/api/v2/auth/mock-login?role=${encodeURIComponent(role)}`);
        if (res.ok) {
            const data = await res.json();
            localStorage.setItem(TOKEN_KEY, data.access_token);
            return data.access_token;
        }
    } catch {
        // ignore
    }
    return null;
}

/**
 * Wraps `fetch` for authenticated API calls: attaches the current bearer
 * token, and if the backend rejects the request with 401 (token expired
 * mid-session, or the underlying JWT_SECRET rotated), tries once to obtain
 * a fresh token before giving up. In production deployments (no dev login
 * available) this refresh is only possible by the user signing in again --
 * acquireDemoToken() itself will simply fail closed since the mock-login
 * endpoint is unreachable, and the caller will surface the resulting 401.
 */
export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
    const attempt = async (token: string) => {
        const headers = new Headers(init.headers);
        if (token) headers.set('Authorization', `Bearer ${token}`);
        return fetch(url, { ...init, headers });
    };

    let token = localStorage.getItem(TOKEN_KEY) || '';
    if (!token || !isTokenValid(token)) {
        const refreshed = await acquireDemoToken();
        if (refreshed) token = refreshed;
    }

    let res = await attempt(token);
    if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        const refreshed = await acquireDemoToken();
        if (refreshed) {
            res = await attempt(refreshed);
        }
    }
    return res;
}
