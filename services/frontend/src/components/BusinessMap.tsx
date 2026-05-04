'use client';

import { useEffect, useRef } from 'react';

interface BusinessMapProps {
    lat: number;
    lng: number;
    name: string;
}

/**
 * Leaflet map showing a single business pin.
 * Loaded client-side only (ssr:false via dynamic() in parent) to avoid
 * the "window is not defined" error that Leaflet throws on the server.
 */
export default function BusinessMap({ lat, lng, name }: BusinessMapProps) {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        let map: import('leaflet').Map | null = null;
        let cancelled = false;

        (async () => {
            const L = (await import('leaflet')).default;

            // Fix default marker icon paths broken by webpack asset hashing
            delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
            L.Icon.Default.mergeOptions({
                iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
                iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
                shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
            });

            if (cancelled || !containerRef.current) return;

            map = L.map(containerRef.current).setView([lat, lng], 15);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19,
            }).addTo(map);

            L.marker([lat, lng])
                .addTo(map)
                .bindPopup(`<strong>${name}</strong>`)
                .openPopup();
        })();

        return () => {
            cancelled = true;
            map?.remove();
        };
    }, [lat, lng, name]);

    return (
        <>
            {/* Leaflet CSS loaded inline — avoids need for a global import */}
            {/* eslint-disable-next-line @next/next/no-page-custom-font */}
            <link
                rel="stylesheet"
                href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
                integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
                crossOrigin=""
            />
            <div
                ref={containerRef}
                className="business-map"
                aria-label={`Map showing location of ${name}`}
                role="img"
            />
        </>
    );
}
