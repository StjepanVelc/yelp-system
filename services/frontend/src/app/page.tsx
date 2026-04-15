import { fetchBusinesses } from '@/lib/api';
import SearchForm from '@/components/SearchForm';
import BusinessCard from '@/components/BusinessCard';

interface Props {
    searchParams: { city?: string; min_stars?: string; page?: string };
}

export default async function HomePage({ searchParams }: Props) {
    const city = searchParams.city ?? '';
    const minStars = searchParams.min_stars ? parseFloat(searchParams.min_stars) : undefined;
    const page = searchParams.page ? parseInt(searchParams.page) : 1;

    const businesses = await fetchBusinesses({ city, min_stars: minStars, page, limit: 20 });

    const hasFilter = city || minStars != null;

    return (
        <>
            <section style={{ marginBottom: '2rem' }}>
                <h1 className="page-title">Find a Business</h1>
                <SearchForm initialCity={city} initialMinStars={searchParams.min_stars ?? ''} />
            </section>

            {hasFilter && (
                <p className="results-count">
                    {businesses.length === 0
                        ? 'No results found.'
                        : `${businesses.length} result${businesses.length !== 1 ? 's' : ''}${city ? ` in ${city}` : ''}${minStars != null ? ` · ${minStars}+ stars` : ''}`}
                </p>
            )}

            <div className="card-grid">
                {businesses.map((b) => (
                    <BusinessCard key={b.id} business={b} />
                ))}
            </div>

            {businesses.length === 20 && (
                <div className="pagination">
                    <a
                        href={`/?city=${city}&min_stars=${searchParams.min_stars ?? ''}&page=${page + 1}`}
                        className="btn-page"
                    >
                        Next page →
                    </a>
                </div>
            )}
        </>
    );
}
