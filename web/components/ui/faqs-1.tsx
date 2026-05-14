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
        title: 'How accurate is ScamRadar+?',
        content:
            'Our Calibrated Logistic Regression model achieves 97.39% accuracy, 97.47% precision, and 97.12% recall on a held-out test set of 9,272 messages drawn from the full 46,360-message corpus across SMS, email, URL, and Reddit channels.',
    },
    {
        id: 'item-2',
        title: 'What types of scams can it detect?',
        content:
            'SMS phishing, email phishing, WhatsApp scams, crypto fraud, fake delivery alerts, advance-fee fraud, romance scams, pig-butchering, investment scams, job offer scams, OTP theft, impersonation, and social engineering attacks — 17 scam categories in total.',
    },
    {
        id: 'item-3',
        title: 'How fast is the analysis?',
        content:
            'The full verdict — confidence score, label, flagged URLs, and tone signals — is returned in under 200 ms for cached results. First-time requests on a warm server take around 300–500 ms. Note: the API runs on Render\'s free tier and may take up to 60 seconds to wake after a period of inactivity.',
    },
    {
        id: 'item-4',
        title: 'What is vector pattern matching?',
        content:
            'We use FAISS nearest-neighbour search on Sentence Transformer embeddings to surface the closest known scam patterns from our training corpus, giving real context on why a message was flagged rather than just a binary label.',
    },
    {
        id: 'item-5',
        title: 'Can it produce false positives?',
        content:
            'Yes — no model is perfect. Legitimate security alerts from services like Google, Apple, or banks can occasionally be flagged because they use urgency language and link patterns similar to phishing. Always use the confidence score alongside the verdict. Scores below 85% warrant human review.',
    },
    {
        id: 'item-6',
        title: 'Does it work in languages other than English?',
        content:
            'The model was trained exclusively on English-language messages and performs best on English text. Detection quality for Arabic, Hebrew, French, or other languages is significantly lower and results should not be relied upon for non-English input.',
    },
    {
        id: 'item-7',
        title: 'Does it work on any platform?',
        content:
            'Yes — ScamRadar+ works on any plain-text input: SMS, email, WhatsApp, Telegram, or any custom integration through our API. No channel-specific retraining required.',
    },
    {
        id: 'item-8',
        title: 'Is there a developer API?',
        content:
            'Yes. The FastAPI endpoint at scamradar-api-l2vv.onrender.com accepts plain text and returns a full analysis including confidence score, verdict, flagged URLs, tone scores, and scam type. Rate limit: 30 requests/minute on /predict, 20/minute on conversation endpoints.',
    },
    {
        id: 'item-9',
        title: 'What does the confidence score mean?',
        content:
            'A 0–100 score reflecting how certain the model is. For SCAM verdicts it represents scam confidence; for LEGIT verdicts it is inverted (100 − score = legitimacy confidence). Scores above 85 are high-confidence; 50–85 warrant a closer look.',
    },
    {
        id: 'item-10',
        title: 'Is ScamRadar+ free to use?',
        content:
            'Yes — completely free. No account, no subscription, no credit card required. Paste any message and get an instant verdict. The tool is free to use directly on this site, and the developer API is also openly accessible.',
    },
    {
        id: 'item-11',
        title: 'Are my messages stored or shared?',
        content:
            'No. Messages you submit are analysed in real time and are not stored, logged, or used for model retraining. The API processes your text and returns a result — nothing is written to a database. Do not submit passwords or highly sensitive personal data as a general security practice.',
    },
    {
        id: 'item-12',
        title: 'What should I do after ScamRadar+ flags a message as SCAM?',
        content:
            'Do not click any links or call any numbers in the message. Block and report the sender on the platform you received it. If you already shared financial information, contact your bank immediately. You can report scams to the FTC at reportfraud.ftc.gov (US), Action Fraud at actionfraud.police.uk (UK), or your local consumer protection authority.',
    },
    {
        id: 'item-13',
        title: 'How is this different from Gmail\'s spam filter or built-in phone protection?',
        content:
            'Standard spam filters are trained to detect known bad senders and bulk mail — they block most obvious spam but miss targeted social engineering, romance scams, WhatsApp fraud, and sophisticated phishing that uses clean domains. ScamRadar+ analyses the actual text content and tone of a message, catches slow-burn manipulation tactics, and works on any platform — not just email.',
    },
];
