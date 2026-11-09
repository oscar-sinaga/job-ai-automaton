import { base } from '$app/paths';

/** Prefix an application-local path without changing external URLs or queries. */
export function appPath(path: string): string {
    if (!path.startsWith('/') || path.startsWith('//') || !base) return path;
    if (path === base || path.startsWith(base + '/')) return path;
    return base + path;
}

export function appRoute(pathname: string): string {
    const local = base && (pathname === base || pathname.startsWith(base + '/'))
        ? pathname.slice(base.length) || '/'
        : pathname;
    return local === '/' ? '/' : local.replace(/\/$/, '');
}
