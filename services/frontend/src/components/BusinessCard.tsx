import Link from 'next/link';
import { Business } from '@/lib/api';

function RatingBadge({ value }: { value: number }) {
    const cls = value >= 4 ? 'rating-high' : value >= 3 ? 'rating-mid' : 'rating-low';
    return (
        <span className={`rating-badge ${cls}`} title={`${value} out of 5 stars`}>
            ★ {value.toFixed(1)}
        </span>
    );
}

export default function BusinessCard({ business }: { business: Business }) {
    const cats = business.categories?.split(', ').slice(0, 3).join(' · ') ?? '';

    return (
        <Link href={`/businesses/${business.id}`} className="card">
            <div className="card-header">
                <h3 className="card-title">{business.name}</h3>
                <span className={`badge ${business.is_open ? 'badge-open' : 'badge-closed'}`}>
                    {business.is_open ? 'Open' : 'Closed'}
                </span>
            </div>
            <div className="card-rating-row">
                <RatingBadge value={business.stars} />
                <span className="card-meta">{business.review_count.toLocaleString()} reviews</span>
            </div>
            <p className="card-location">
                {business.city}, {business.state}
            </p>
            {cats && <p className="card-cats">{cats}</p>}
        </Link>
    );
}
