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
            'The production model achieves F1 = 0.941 (precision 0.961, recall 0.923, ROC-AUC 0.995, PR-AUC 0.984) on a locked one-shot external benchmark of 25,306 messages that was held out from all model selection, tuning, and threshold optimisation. Every scoring event on that benchmark is recorded in the research repository. Full metrics and hyperparameters are published in models/e5_metadata.json.',
    },
    {
        id: 'item-2',
        title: 'What types of scams can it detect?',
        content:
            'Email phishing, SMS phishing (smishing), advance-fee fraud (419-style), email spam, recruitment scams, romance scams, marketplace and delivery scams, business-email compromise, impersonation, and general social engineering — 12 scam categories in the E5 evaluation. Recruitment scams are the weakest single class (recall 0.494); every other scam class exceeds 0.81 recall on external benchmark.',
    },
    {
        id: 'item-3',
        title: 'How fast is the analysis?',
        content:
            'Fast real-time analysis — sub-second on a warm server. The classifier itself takes under a millisecond; the rest of the wall-clock time is network round-trip and (if the message contains URLs) live URL-reputation checks against Google Safe Browsing and VirusTotal. The API runs on Render\'s free tier and may take up to 60 seconds to wake after a period of inactivity — subsequent requests are fast.',
    },
    {
        id: 'item-4',
        title: 'What does the model actually look at?',
        content:
            'The classifier reads word and character n-grams of the message text — 500,000 features in total, produced by two TF-IDF vectorisers (word 1-2 grams + character 3-6 grams). A Logistic Regression trained on 195,776 unique message clusters converts those features into a scam probability. Alongside the model verdict, the API returns tone signals, URL reputation, and a scam-type label to help you understand why the message was flagged.',
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
            'A 0–100 score showing the model\'s scam probability. Messages with confidence ≥ 59 are labelled SCAM; below 59 they are labelled LEGIT. Higher scores mean more certainty — a score of 95 is a very confident scam call, a score of 5 is a very confident legit call. Confidence between 40 and 75 is borderline and worth double-checking.',
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
