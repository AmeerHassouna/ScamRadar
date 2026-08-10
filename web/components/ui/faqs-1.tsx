import React from 'react';
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from '@/components/ui/accordion';
import { SectionEyebrow } from '@/components/ui/section-eyebrow';

export function FaqsSection() {
    return (
        <div className="mx-auto w-full max-w-3xl space-y-7 px-4 pt-16 pb-16">
            <div className="space-y-2">
                <SectionEyebrow label="FAQ" meta="07 · Support" align="left" />
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
                <a href="mailto:amerrhassouna@gmail.com" className="text-green-400 hover:underline">
                    Contact us
                </a>
            </p>
        </div>
    );
}

const questions = [
    {
        id: 'item-1',
        title: 'Is it free?',
        content:
            'Yes — completely free. No account, no signup, no card. Just paste a message and get a verdict.',
    },
    {
        id: 'item-2',
        title: 'How accurate is it?',
        content:
            'About 97% accurate on a test of 25,306 messages the model had never seen. It won\'t catch every scam, but it catches the ones most likely to trick you.',
    },
    {
        id: 'item-3',
        title: 'What kinds of scams does it catch?',
        content:
            'Phishing, SMS scams, crypto and investment scams, romance scams, fake delivery notices, fake job offers, prize fraud, and more — 12 categories in total. Anything that reads like a scam.',
    },
    {
        id: 'item-4',
        title: 'Are my messages stored?',
        content:
            'No. Your message is read, analysed, and thrown away. Nothing is saved, logged, or shared.',
    },
    {
        id: 'item-5',
        title: 'What do I do if it flags something as SCAM?',
        content:
            'Don\'t click any links or reply. Block the sender. If you already sent money or account details, contact your bank right away.',
    },
    {
        id: 'item-6',
        title: 'Can it be wrong?',
        content:
            'Occasionally, yes. Real security alerts from banks or Apple can look a lot like phishing. Treat the verdict as a strong signal, not a final answer — especially on borderline scores.',
    },
    {
        id: 'item-7',
        title: 'Does it work in other languages?',
        content:
            'English only. The model was trained on English messages, so non-English text is rejected. Translate the message to English first, then paste it.',
    },
];
