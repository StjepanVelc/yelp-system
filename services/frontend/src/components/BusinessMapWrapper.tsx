'use client';

import dynamic from 'next/dynamic';

const BusinessMap = dynamic(() => import('./BusinessMap'), { ssr: false });

interface Props {
    lat: number;
    lng: number;
    name: string;
}

export default function BusinessMapWrapper({ lat, lng, name }: Props) {
    return <BusinessMap lat={lat} lng={lng} name={name} />;
}
