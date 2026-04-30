'use client';

import { useRouter } from 'next/navigation';
import { useState, useTransition, FormEvent } from 'react';

interface Props {
    initialCity?: string;
    initialQuery?: string;
    initialMinStars?: string;
    cityOptions?: string[];
}

export default function SearchForm({ initialCity = '', initialQuery = '', initialMinStars = '', cityOptions = [] }: Props) {
    const router = useRouter();
    const [city, setCity] = useState(initialCity);
    const [query, setQuery] = useState(initialQuery);
    const [minStars, setMinStars] = useState(initialMinStars);
    const [isPending, startTransition] = useTransition();

    function handleSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();
        const params = new URLSearchParams();
        if (query.trim()) params.set('q', query.trim());
        if (city.trim()) params.set('city', city.trim());
        if (minStars) params.set('min_stars', minStars);
        startTransition(() => {
            router.push(`/?${params.toString()}`);
        });
    }

    return (
        <form onSubmit={handleSubmit} className="search-form">
            <input
                id="searchQuery"
                name="searchQuery"
                type="text"
                placeholder="Search businesses (e.g. pizza, sushi bar, coffee)"
                value={query}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setQuery(e.target.value)}
                className="search-input"
                disabled={isPending}
                autoComplete="off"
            />
            <input
                id="city"
                name="city"
                type="text"
                list="city-options"
                placeholder="City (e.g. Philadelphia, Tucson…)"
                value={city}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCity(e.target.value)}
                className="search-input"
                disabled={isPending}
                autoComplete="off"
            />
            <datalist id="city-options">
                {cityOptions.map((optionCity) => (
                    <option key={optionCity} value={optionCity} />
                ))}
            </datalist>
            <select
                id="minStars"
                name="minStars"
                value={minStars}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setMinStars(e.target.value)}
                className="search-select"
                aria-label="Minimum star rating"
                disabled={isPending}
            >
                <option value="">Any rating</option>
                <option value="2">★★ 2+</option>
                <option value="3">★★★ 3+</option>
                <option value="4">★★★★ 4+</option>
                <option value="4.5">★★★★½ 4.5+</option>
            </select>
            <button type="submit" className={`search-btn${isPending ? ' search-btn--loading' : ''}`} disabled={isPending}>
                {isPending ? 'Searching…' : 'Search'}
            </button>
        </form>
    );
}
