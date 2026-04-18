export default function HomeLoading() {
    return (
        <>
            <section className="sk-section">
                <div className="skeleton sk-title" />
                <div className="sk-search-row">
                    <div className="skeleton sk-input" />
                    <div className="skeleton sk-select" />
                    <div className="skeleton sk-btn" />
                </div>
            </section>
            <div className="card-grid">
                {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="card card--inert">
                        <div className="sk-card-row">
                            <div className="skeleton sk-card-title" />
                            <div className="skeleton sk-card-badge" />
                        </div>
                        <div className="skeleton sk-card-stars" />
                        <div className="skeleton sk-card-meta" />
                        <div className="skeleton sk-card-cats" />
                    </div>
                ))}
            </div>
        </>
    );
}
