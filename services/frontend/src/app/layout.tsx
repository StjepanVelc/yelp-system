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
                    <div className="container">
                        <a href="/" className="site-logo">⭐ Yelp System</a>
                    </div>
                </header>
                <div className="container main-content">{children}</div>
                <footer className="site-footer">
                    <div className="container">
                        <p>Yelp Open Dataset · {new Date().getFullYear()}</p>
                    </div>
                </footer>
            </body>
        </html>
    );
}
