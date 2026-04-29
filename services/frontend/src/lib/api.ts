export interface Review {
    review_id: string;
    user_id: string;
    stars: number;
    text: string;
    date: string;
    useful: number;
    funny: number;
    cool: number;
}

export interface Business {
    id: string;
    name: string;
    address: string;
    city: string;
    state: string;
    postal_code: string;
    stars: number;
    review_count: number;
    is_open: number;
    categories: string;
    latitude: number;
    longitude: number;
}

const API_BASE = process.env.API_URL ?? 'http://localhost:8000';

function resolveAuthToken(): string | null {
    const envToken = process.env.NEXT_PUBLIC_API_AUTH_TOKEN ?? process.env.API_AUTH_TOKEN;
    if (envToken) return envToken;

    if (typeof window !== 'undefined') {
        return window.localStorage.getItem('api_auth_token');
    }

    return null;
}

function buildAuthHeaders(): HeadersInit {
    const token = resolveAuthToken();
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
}

export async function fetchBusinesses(params: {
    city?: string;
    min_stars?: number;
    page?: number;
    limit?: number;
}): Promise<Business[]> {
    const url = new URL(`${API_BASE}/businesses`);
    if (params.city) url.searchParams.set('city', params.city);
    if (params.min_stars != null) url.searchParams.set('min_stars', String(params.min_stars));
    if (params.page) url.searchParams.set('page', String(params.page));
    if (params.limit) url.searchParams.set('limit', String(params.limit));

    try {
        const res = await fetch(url.toString(), { cache: 'no-store', headers: buildAuthHeaders() });
        if (!res.ok) return [];
        return res.json();
    } catch (_e) {
        return [];
    }
}

export async function fetchCities(): Promise<string[]> {
    try {
        const res = await fetch(`${API_BASE}/businesses/cities`, {
            cache: 'no-store',
            headers: buildAuthHeaders(),
        });
        if (!res.ok) return [];
        return res.json();
    } catch (_e) {
        return [];
    }
}

export async function fetchBusiness(id: string): Promise<Business | null> {
    try {
        const res = await fetch(`${API_BASE}/businesses/${id}`, { cache: 'no-store', headers: buildAuthHeaders() });
        if (!res.ok) return null;
        return res.json();
    } catch (_e) {
        return null;
    }
}

export async function fetchReviews(id: string, page = 1, limit = 20): Promise<Review[]> {
    try {
        const res = await fetch(`${API_BASE}/businesses/${id}/reviews?page=${page}&limit=${limit}`, {
            cache: 'no-store',
            headers: buildAuthHeaders(),
        });
        if (!res.ok) return [];
        return res.json();
    } catch (_e) {
        return [];
    }
}

export async function fetchRecommendations(id: string, limit = 6): Promise<Business[]> {
    try {
        const res = await fetch(`${API_BASE}/recommendations/${id}?limit=${limit}`, {
            cache: 'no-store',
            headers: buildAuthHeaders(),
        });
        if (!res.ok) return [];
        return res.json();
    } catch (_e) {
        return [];
    }
}
