'use client';

import { useRouter } from 'next/navigation';
import { useState, FormEvent } from 'react';

interface Props {
    initialCity?: string;
    initialMinStars?: string;
}

export default function SearchForm({ initialCity = '', initialMinStars = '' }: Props) {
    const router = useRouter();
    const [city, setCity] = useState(initialCity);
    const [minStars, setMinStars] = useState(initialMinStars);

    function handleSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();
        const params = new URLSearchParams();
        if (city.trim()) params.set('city', city.trim());
        if (minStars) params.set('min_stars', minStars);
        router.push(`/?${params.toString()}`);
    }

    return (
        <form onSubmit={handleSubmit} className="search-form">
            <input
                type="text"
                placeholder="City (e.g. Phoenix, Las Vegas…)"
                value={city}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCity(e.target.value)}
                className="search-input"
            />
            <select
                value={minStars}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setMinStars(e.target.value)}
                className="search-select"
                aria-label="Minimum star rating"
            >
                <option value="">Any rating</option>
                <option value="2">★★ 2+</option>
                <option value="3">★★★ 3+</option>
                <option value="4">★★★★ 4+</option>
                <option value="4.5">★★★★½ 4.5+</option>
            </select>
            <button type="submit" className="search-btn">Search</button>
        </form>
    );
}
