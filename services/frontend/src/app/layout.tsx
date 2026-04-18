import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
    title: 'Yelp System',
    description: 'Business search and recommendations powered by the Yelp Open Dataset',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>
                <header className="site-header">
                    <div className="container header-inner">
                        <a href="/" className="site-logo">⭐ Yelp System</a>
                        <nav className="header-nav">
                            <span className="nav-tag">microservices</span>
                            <span className="nav-tag">PostgreSQL</span>
                            <span className="nav-tag">gRPC</span>
                        </nav>
                    </div>
                </header>
                {children}
                <footer className="site-footer">
                    <div className="container">
                        <p>Yelp Open Dataset · {new Date().getFullYear()} · 150,346 businesses · 6.99M reviews</p>
                    </div>
                </footer>
            </body>
        </html>
    );
}
