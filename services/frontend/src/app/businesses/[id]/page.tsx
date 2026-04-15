import { fetchBusiness, fetchRecommendations } from '@/lib/api';
import BusinessCard from '@/components/BusinessCard';
import { notFound } from 'next/navigation';
import Link from 'next/link';

interface Props {
    params: { id: string };
}

export default async function BusinessPage({ params }: Props) {
    const [business, recommendations] = await Promise.all([
        fetchBusiness(params.id),
        fetchRecommendations(params.id, 6),
    ]);

    if (!business) notFound();

    const categories = business.categories?.split(', ').filter(Boolean) ?? [];
    const full = Math.floor(business.stars);
    const half = business.stars % 1 >= 0.5;
    const empty = 5 - full - (half ? 1 : 0);

    return (
        <div className="detail-layout">
            {/* ── Main ─────────────────────────────────────────────────────────── */}
            <div>
                <Link href="/" className="back-link">← Back to search</Link>

                <h1 className="detail-name">{business.name}</h1>

                <div className="detail-stars">
                    {'★'.repeat(full)}
                    {half ? '½' : ''}
                    {'☆'.repeat(empty)}
                    <span className="stars-value"> {business.stars}</span>
                    <span className="detail-reviews"> · {business.review_count.toLocaleString()} reviews</span>
                </div>

                <span className={`status-badge ${business.is_open ? 'open' : 'closed'}`}>
                    {business.is_open ? '● Open' : '● Closed'}
                </span>

                <div className="detail-info">
                    <div className="info-row">
                        <span className="info-label">Address</span>
                        <span>
                            {business.address}, {business.city}, {business.state} {business.postal_code}
                        </span>
                    </div>

                    {categories.length > 0 && (
                        <div className="info-row">
                            <span className="info-label">Categories</span>
                            <div className="tags">
                                {categories.map((c) => (
                                    <span key={c} className="tag">{c.trim()}</span>
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="info-row">
                        <span className="info-label">Coordinates</span>
                        <span>
                            {business.latitude.toFixed(5)}, {business.longitude.toFixed(5)}
                        </span>
                    </div>
                </div>
            </div>

            {/* ── Sidebar ──────────────────────────────────────────────────────── */}
            <aside className="detail-sidebar">
                <h2 className="sidebar-title">Similar Businesses</h2>
                {recommendations.length === 0 ? (
                    <p style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>No recommendations found.</p>
                ) : (
                    <div className="sidebar-list">
                        {recommendations.map((r) => (
                            <BusinessCard key={r.id} business={r} />
                        ))}
                    </div>
                )}
            </aside>
        </div>
    );
}
