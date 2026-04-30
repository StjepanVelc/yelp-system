import { fetchBusinesses, fetchCities } from '@/lib/api';
import SearchForm from '@/components/SearchForm';
import BusinessCard from '@/components/BusinessCard';

interface Props {
    searchParams: Promise<{ city?: string; q?: string; min_stars?: string; page?: string }>;
}

export default async function HomePage({ searchParams }: Props) {
    const sp = await searchParams;
    const city = sp.city ?? '';
    const q = sp.q ?? '';
    const minStars = sp.min_stars ? parseFloat(sp.min_stars) : undefined;
    const page = sp.page ? parseInt(sp.page) : 1;

    const hasFilter = !!(city || q || (minStars != null && sp.min_stars));
    const cityOptions = await fetchCities();
    const businesses = hasFilter
        ? await fetchBusinesses({ city, query: q, min_stars: minStars, page, limit: 20 })
        : [];

    return (
        <>
            {/* ── Hero ──────────────────────────────────────────────────────── */}
            <section className="hero">
                <div className="hero-glow hero-glow--left" />
                <div className="hero-glow hero-glow--right" />
                <div className="container hero-inner">
                    <div className="hero-badge">YELP OPEN DATASET</div>
                    <h1 className="hero-title">
                        Find any business,<br />
                        <span className="hero-accent">anywhere.</span>
                    </h1>
                    <p className="hero-subtitle">
                        Search 150,000+ real businesses from Yelp dataset
                    </p>
                    <p className="hero-powered">Powered by microservices &middot; PostgreSQL &middot; gRPC</p>
                    <div className="hero-search">
                        <SearchForm
                            initialCity={city}
                            initialQuery={q}
                            initialMinStars={sp.min_stars ?? ''}
                            cityOptions={cityOptions}
                        />
                    </div>
                    <div className="hero-stats">
                        <div className="hero-stat"><span className="stat-num">150K+</span><span className="stat-label">Businesses</span></div>
                        <div className="hero-stat-divider" />
                        <div className="hero-stat"><span className="stat-num">6.99M</span><span className="stat-label">Reviews</span></div>
                        <div className="hero-stat-divider" />
                        <div className="hero-stat"><span className="stat-num">10.2M</span><span className="stat-label">Records</span></div>
                        <div className="hero-stat-divider" />
                        <div className="hero-stat"><span className="stat-num">3</span><span className="stat-label">Microservices</span></div>
                    </div>
                </div>
            </section>

            {/* ── Results ───────────────────────────────────────────────────── */}
            <div className="container main-content">
                {!hasFilter && (
                    <div className="welcome-state">
                        <div className="welcome-icon">★</div>
                        <h2>Start by entering a city above</h2>
                        <p>Try <strong>Philadelphia</strong>, <strong>Tucson</strong>, <strong>Tampa</strong>, <strong>Nashville</strong> or <strong>New Orleans</strong>.</p>
                    </div>
                )}

                {hasFilter && (
                    <p className="results-count">
                        {businesses.length === 0
                            ? `No businesses found${q ? ` for "${q}"` : ''}${city ? ` in "${city}"` : ''}${minStars != null ? ` with ${minStars}+ stars` : ''}.`
                            : `${businesses.length} result${businesses.length !== 1 ? 's' : ''}${q ? ` for "${q}"` : ''}${city ? ` in ${city}` : ''}${minStars != null ? ` · ${minStars}+ stars` : ''}`}
                    </p>
                )}

                {hasFilter && businesses.length === 0 && (
                    <div className="empty-state">
                        <div className="empty-icon">🔍</div>
                        <h2>No results found</h2>
                        <p>Try a different city name or a lower minimum star rating.</p>
                    </div>
                )}

                <div className="card-grid">
                    {businesses.map((b) => (
                        <BusinessCard key={b.id} business={b} />
                    ))}
                </div>

                {hasFilter && (page > 1 || businesses.length === 20) && (
                    <div className="pagination">
                        {page > 1 && (
                            <a
                                href={`/?q=${encodeURIComponent(q)}&city=${encodeURIComponent(city)}&min_stars=${sp.min_stars ?? ''}&page=${page - 1}`}
                                className="btn-page"
                            >
                                ← Previous
                            </a>
                        )}
                        <span className="pagination-page">Page {page}</span>
                        {businesses.length === 20 && (
                            <a
                                href={`/?q=${encodeURIComponent(q)}&city=${encodeURIComponent(city)}&min_stars=${sp.min_stars ?? ''}&page=${page + 1}`}
                                className="btn-page"
                            >
                                Next →
                            </a>
                        )}
                    </div>
                )}
            </div>
        </>
    );
}