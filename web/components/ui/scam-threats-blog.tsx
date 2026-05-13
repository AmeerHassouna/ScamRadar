import { Blog7 } from "@/components/ui/blog7"

const posts = [
  {
    id: "threat-1",
    title: "Fake Bank SMS Alert: Credential-Harvesting Portals on New Domains",
    summary:
      "Attackers impersonating major banks send urgent account-suspension SMS messages. Links redirect to lookalike portals registered hours before the campaign — bypassing blocklists entirely.",
    label: "Critical · SMS Phishing",
    author: "FTC Consumer Advice",
    published: "2024",
    url: "https://consumer.ftc.gov/articles/bank-impersonators-try-steal-your-money",
    image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=800&h=450&fit=crop",
  },
  {
    id: "threat-2",
    title: "PayPal Spoofed Email Campaign Relays 2FA Codes in Real Time",
    summary:
      "Lookalike PayPal domains collect login credentials and OTP codes simultaneously, relaying them to attacker-controlled servers before the victim realises anything is wrong.",
    label: "High · Email Phishing",
    author: "CISA",
    published: "2024",
    url: "https://www.cisa.gov/news-events/news/avoiding-social-engineering-and-phishing-attacks",
    image: "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800&h=450&fit=crop",
  },
  {
    id: "threat-3",
    title: "WhatsApp Crypto Giveaway Scams Surge — Celebrity Endorsement Fakes",
    summary:
      "Fake celebrity-endorsed giveaways spread via WhatsApp and Telegram, requesting a small 'verification' transfer to unlock fabricated winnings. FTC data shows crypto scam losses topped $1.4B in 2023.",
    label: "High · Social Engineering",
    author: "FTC Data Spotlight",
    published: "2024",
    url: "https://www.ftc.gov/news-events/data-visualizations/data-spotlight/2022/06/reports-show-scammers-cashing-crypto-craze",
    image: "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=800&h=450&fit=crop",
  },
  {
    id: "threat-4",
    title: "DHL & FedEx Impersonation SMS Now Drops Device-Credential Malware",
    summary:
      "Carrier impersonation texts with 'package held' alerts now link to malware-laced tracking pages that harvest device credentials and banking details in a single visit.",
    label: "Medium · SMS Phishing",
    author: "FTC Consumer Advice",
    published: "2024",
    url: "https://consumer.ftc.gov/articles/package-delivery-scams",
    image: "https://images.unsplash.com/photo-1566576721346-d4a3b4eaeb55?w=800&h=450&fit=crop",
  },
  {
    id: "threat-5",
    title: "LinkedIn Fake Job Offers Demand Upfront Equipment Fees",
    summary:
      "Remote work scams on LinkedIn and email promise high-paying positions, then ask victims to pay an upfront 'equipment fee' or share banking details for payroll setup.",
    label: "High · Advance Fee Fraud",
    author: "FBI",
    published: "2024",
    url: "https://www.fbi.gov/scams-and-safety/common-scams-and-crimes/job-scams",
    image: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800&h=450&fit=crop",
  },
  {
    id: "threat-6",
    title: "Pig-Butchering Crypto Scams: Months-Long Grooming via SMS",
    summary:
      "Slow-burn romance-to-crypto scams build trust over weeks before introducing a 'private trading platform' that locks funds on withdrawal. FBI IC3 flagged this as one of the fastest-growing fraud types.",
    label: "Critical · Pig Butchering",
    author: "FBI IC3",
    published: "2022",
    url: "https://www.ic3.gov/PSA/2022/PSA220916",
    image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&h=450&fit=crop",
  },
]

export function ScamThreatsBlog() {
  return (
    <Blog7
      tagline="Latest Threat Intelligence"
      heading={`ACTIVE SCAM\nCAMPAIGNS`}
      description="Real-world scam campaigns tracked by ScamRadar+ intelligence. Each entry reflects attack patterns our model was trained to detect — and is now actively blocking."
      buttonText="Scan a suspicious message"
      buttonUrl="/#home"
      posts={posts}
    />
  )
}
