export default function DetailLoading() {
    return (
        <div className="detail-layout">
            {/* Main */}
            <div>
                <div className="skeleton sk-back" />
                <div className="skeleton sk-detail-name" />
                <div className="skeleton sk-detail-stars" />
                <div className="skeleton sk-detail-badge" />
                <div className="detail-info">
                    {(['sk-info-val-sm', 'sk-info-val-md', 'sk-info-val-lg'] as const).map((cls, i) => (
                        <div key={i} className="info-row">
                            <div className="skeleton sk-info-label" />
                            <div className={`skeleton ${cls}`} />
                        </div>
                    ))}
                </div>
            </div>

            {/* Sidebar */}
            <aside className="detail-sidebar">
                <div className="skeleton sk-sidebar-title" />
                <div className="sk-sidebar-list">
                    {Array.from({ length: 4 }).map((_, i) => (
                        <div key={i} className="card card--inert">
                            <div className="sk-card-row">
                                <div className="skeleton sk-card-title" />
                                <div className="skeleton sk-card-badge" />
                            </div>
                            <div className="skeleton sk-card-stars" />
                            <div className="skeleton sk-card-meta" />
                        </div>
                    ))}
                </div>
            </aside>
        </div>
    );
}
