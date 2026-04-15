import Link from 'next/link';
import { Business } from '@/lib/api';

function Stars({ value }: { value: number }) {
    const full = Math.floor(value);
    const half = value % 1 >= 0.5;
    const empty = 5 - full - (half ? 1 : 0);
    return (
        <span className="stars" title={`${value} stars`}>
            {'★'.repeat(full)}
            {half ? '½' : ''}
            {'☆'.repeat(empty)}
            <span className="stars-value"> {value}</span>
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
            <Stars value={business.stars} />
            <p className="card-meta">{business.review_count.toLocaleString()} reviews</p>
            <p className="card-location">
                {business.city}, {business.state}
            </p>
            {cats && <p className="card-cats">{cats}</p>}
        </Link>
    );
}
