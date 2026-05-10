import React from 'react';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from '@/components/ui/accordion';

export function FaqsSection() {
    return (
        <div className="mx-auto w-full max-w-3xl space-y-7 px-4 pt-16 pb-16">
            <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-green-400">FAQ</p>
                <h2 className="text-3xl font-bold text-white md:text-4xl">Frequently Asked Questions</h2>
                <p className="max-w-2xl text-white/40">
                    Everything you need to know about ScamRadar+. If you don't find the answer you're looking
                    for, feel free to reach out.
                </p>
            </div>
            <Accordion
                type="single"
                collapsible
                className="w-full -space-y-px rounded-lg bg-white/[0.03]"
                defaultValue="item-1"
            >
                {questions.map((item) => (
                    <AccordionItem
                        value={item.id}
                        key={item.id}
                        className="relative border-x border-white/8 first:rounded-t-lg first:border-t last:rounded-b-lg last:border-b"
                    >
                        <AccordionTrigger className="px-4 py-4 text-[15px] leading-6 text-white/80 hover:text-green-400 hover:no-underline [&[data-state=open]]:text-green-400">
                            {item.title}
                        </AccordionTrigger>
                        <AccordionContent className="px-4 pb-4 text-white/40">
                            {item.content}
                        </AccordionContent>
                    </AccordionItem>
                ))}
            </Accordion>
            <p className="text-white/40">
                Can't find what you're looking for?{' '}
                <a href="mailto:support@scamradar.ai" className="text-green-400 hover:underline">
                    Contact our support team
                </a>
            </p>
        </div>
    );
}

const questions = [
    {
        id: 'item-1',
        title: 'How accurate is ScamRadar+?',
        content:
            'Our Calibrated Logistic Regression model achieves 97.39% accuracy, trained on 46,360 real-world scam and legitimate messages across SMS, email, WhatsApp, and social media.',
    },
    {
        id: 'item-2',
        title: 'What types of scams can it detect?',
        content:
            'SMS phishing, email phishing, WhatsApp scams, crypto fraud, fake delivery alerts, advance-fee fraud, romance scams, pig-butchering, and social engineering attacks — 17 scam categories in total.',
    },
    {
        id: 'item-3',
        title: 'How fast is the analysis?',
        content:
            'The full verdict — confidence score, label, flagged URLs, and similar scam patterns — is returned in under 200 ms via a single FastAPI endpoint.',
    },
    {
        id: 'item-4',
        title: 'What is vector pattern matching?',
        content:
            'We use FAISS nearest-neighbour search to surface the closest known scam patterns from our training corpus, giving you full context on why a message was flagged.',
    },
    {
        id: 'item-5',
        title: 'Does it work on any platform?',
        content:
            'Yes — ScamRadar+ works on any plain-text input: SMS, email, WhatsApp, Telegram, or any custom integration through our API. No channel-specific retraining required.',
    },
    {
        id: 'item-6',
        title: 'Is there a developer API?',
        content:
            'Yes. Our FastAPI endpoint accepts plain text and returns a full analysis including confidence score, verdict, flagged URLs, and the top similar scam patterns from our corpus.',
    },
    {
        id: 'item-7',
        title: 'What does the risk score mean?',
        content:
            'A 0–100 confidence score that reflects how certain the model is. Higher scores indicate stronger scam signals. You can set your own threshold for your use case.',
    },
];
