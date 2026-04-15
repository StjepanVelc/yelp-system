import Link from 'next/link';

export default function NotFound() {
    return (
        <div className="state-msg">
            <h1>404 — Not Found</h1>
            <p>This business or page does not exist.</p>
            <Link href="/" style={{ marginTop: '1rem', display: 'inline-block' }}>
                ← Back to search
            </Link>
        </div>
    );
}
