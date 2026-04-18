'use client';

import { useState } from 'react';

const LIMIT = 280;

export default function ReviewText({ text }: { text: string }) {
    const [expanded, setExpanded] = useState(false);

    if (text.length <= LIMIT) {
        return <p className="review-text">{text}</p>;
    }

    return (
        <p className="review-text">
            {expanded ? text : text.slice(0, LIMIT) + '…'}
            <button className="read-more-btn" onClick={() => setExpanded((e) => !e)}>
                {expanded ? ' Show less' : ' Read more'}
            </button>
        </p>
    );
}
