import { fetchBusiness, fetchRecommendations, fetchReviews } from '@/lib/api';
import BusinessCard from '@/components/BusinessCard';
import ReviewText from '@/components/ReviewText';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const BusinessMap = dynamic(() => import('@/components/BusinessMap'), { ssr: false });

function avatarClass(userId: string): string {
    const code = (userId.charCodeAt(0) || 0) + (userId.charCodeAt(1) || 0);
    return `avatar-c${code % 6}`;
}

function avatarInitial(userId: string): string {
    return userId ? userId[0].toUpperCase() : '?';
}

const ONE_YEAR_AGO = new Date();
ONE_YEAR_AGO.setFullYear(ONE_YEAR_AGO.getFullYear() - 1);

interface Props {
    params: Promise<{ id: string }>;
}

export default async function BusinessPage({ params }: Props) {
    const { id } = await params;
    const [business, recommendations, reviews] = await Promise.all([
        fetchBusiness(id),
        fetchRecommendations(id, 6),
        fetchReviews(id, 1, 20),
    ]);

    if (!business) notFound();

    const categories = business.categories?.split(', ').filter(Boolean) ?? [];
    const ratingCls = business.stars >= 4.5 ? 'rating-high' : business.stars >= 3.5 ? 'rating-mid' : 'rating-low';

    return (
        <div className="detail-layout">
            {/* ── Main ─────────────────────────────────────────────────────────── */}
            <div>
                <Link href="/" className="back-link">← Back to search</Link>

                <h1 className="detail-name">{business.name}</h1>

                <div className="detail-stars">
                    <span className={`rating-badge rating-badge-lg ${ratingCls}`}>
                        ★ {business.stars.toFixed(1)}
                    </span>
                    <span className="detail-reviews">{business.review_count.toLocaleString()} reviews</span>
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

                {/* ── Map ──────────────────────────────────────────────────── */}
                {business.latitude !== 0 && business.longitude !== 0 && (
                    <section className="map-section">
                        <h2 className="map-title">Location</h2>
                        <BusinessMap
                            lat={business.latitude}
                            lng={business.longitude}
                            name={business.name}
                        />
                    </section>
                )}

                {/* ── Reviews ──────────────────────────────────────────────── */}
                <section className="reviews-section">
                    <h2 className="reviews-title">Reviews</h2>
                    {reviews.length === 0 ? (
                        <p className="no-reviews">No reviews yet.</p>
                    ) : (
                        <div className="reviews-list">
                            {reviews.map((r) => {
                                const rc = r.stars >= 4.5 ? 'rating-high' : r.stars >= 3.5 ? 'rating-mid' : 'rating-low';
                                const dateStr = r.date ? r.date.slice(0, 10) : '';
                                const isRecent = r.date ? new Date(r.date) >= ONE_YEAR_AGO : false;
                                const colorCls = avatarClass(r.user_id);
                                const initial = avatarInitial(r.user_id);
                                return (
                                    <div key={r.review_id} className="review-card">
                                        <div className="review-header">
                                            <span
                                                className={`review-avatar ${colorCls}`}
                                                aria-hidden="true"
                                            >{initial}</span>
                                            <span className={`rating-badge ${rc}`}>★ {r.stars.toFixed(1)}</span>
                                            {isRecent && <span className="review-recent">Recent</span>}
                                            <span className="review-date">{dateStr}</span>
                                            <span className="review-votes">
                                                👍 {r.useful} &nbsp; 😄 {r.funny} &nbsp; 😎 {r.cool}
                                            </span>
                                        </div>
                                        <ReviewText text={r.text} />
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </section>
            </div>

            {/* ── Sidebar ──────────────────────────────────────────────────────── */}
            <aside className="detail-sidebar">
                <h2 className="sidebar-title">Similar Businesses</h2>
                <div className="rec-reason">
                    <p className="rec-reason-label">Similar businesses based on:</p>
                    <ul className="rec-reason-list">
                        <li>📍 Geographic proximity</li>
                        <li>🏷️ Category overlap</li>
                        <li>⭐ Rating similarity</li>
                    </ul>
                </div>
                {recommendations.length === 0 ? (
                    <p className="no-recs">No recommendations found.</p>
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
