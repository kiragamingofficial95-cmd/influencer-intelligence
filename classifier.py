import re
import json
from typing import Dict, List, Tuple, Optional
from datetime import datetime

CATEGORY_KEYWORDS = {
    "cold_outreach": [
        r"(?i)(introducing|reaching out|came across|noticed|stumbled upon|thought of you|would love to connect|would you be open|wanted to reach|first email|first outreach|getting in touch|hello there|hi there)",
        r"(?i)(i found|i discovered|i came across|your profile|your work|your brand|your company)",
        r"(?i)(quick introduction|brief intro|warm intro|keep this short)",
        r"(?i)(i'm reaching out because|reason i'm emailing|writing to you today)",
    ],
    "follow_up": [
        r"(?i)(following up|just checking|bumping this|bringing this to the top|quick follow up|any thoughts|any update|circling back|revisiting|touching base|checking in)",
        r"(?i)(not sure if you saw|not sure if you received|wanted to make sure|did you get a chance|any chance to review|wanted to check)",
        r"(?i)(second email|third email|just a gentle|as a follow.up)",
        r"(?i)(haven't heard back|assuming you're busy|know you're swamped|figured i'd reach)",
    ],
    "positive_reply": [
        r"(?i)(interested|sounds great|looks great|would love to|let's talk|let's hop on|would be happy|absolutely|definitely|yes please|keen to|this looks good|looks promising|very interested|quite interested|excited to)",
        r"(?i)(tell me more|send over more|more details|share more|would love to hear|let's explore|would be great to)",
        r"(?i)(thanks for reaching out|thanks for the note|appreciate the outreach)",
        r"(?i)(schedule|calendar|available|let's set up|book a time|good time to|how about|available on)",
    ],
    "objection": [
        r"(?i)(not interested|not right now|not a good fit|not looking|not the right time|unfortunately|sorry but|appreciate but)",
        r"(?i)(budget|budgetary|no budget|don't have budget|cannot afford|not in the budget|limited budget)",
        r"(?i)(already working with|already partnered|currently working|in talks with|have an agency|existing partner)",
        r"(?i)(not our priority|not a priority|other priorities|focusing on|too busy|swamped right now)",
        r"(?i)(remove me|unsubscribe|don't contact|not interested in receiving)",
    ],
    "meeting_booked": [
        r"(?i)(confirmed|scheduled|booked|calendar invite|meeting invite|call scheduled|call confirmed|google meet|zoom|calendly|we're set)",
        r"(?i)(look forward to speaking|looking forward to our call|see you on|see you at|talk then|speak then)",
        r"(?i)(how does .+ (sound|work|look)|works for me|that works|available at|let me know what works)",
        r"(?i)(rescheduled|moved to|updated meeting|new time for)",
    ],
    "proposal_sent": [
        r"(?i)(proposal|proposed|propose|scope of work|SOW|agreement|contract|terms|pricing|investment)",
        r"(?i)(here's what we're thinking|here's our proposal|attached proposal|see attached|take a look at)",
        r"(?i)(package|retainer|monthly retainer|campaign fee|management fee|service fee)",
        r"(?i)(proposed timeline|suggested approach|recommended strategy)",
    ],
    "negotiation": [
        r"(?i)(negotiate|negotiation|counter|bargain|can you do|lower|discount|reduce|flexible on)",
        r"(?i)(can you do better|can we work on|our budget is|budget is |budget of|only have)",
        r"(?i)(price|pricing|cost|fee|rate|expensive|too much|that's a lot)",
        r"(?i)(could you do|would you consider|can we adjust|revise|modified)",
    ],
    "closed_won": [
        r"(?i)(let's move forward|excited to start|looking forward to working|let's get started|start date|kickoff|onboarding)",
        r"(?i)(signed|agreed|approved|accepted|confirmed|committed|let's do it|let's go ahead)",
        r"(?i)(contract signed|agreement signed|deal closed|partnership confirmed|welcome aboard)",
        r"(?i)(payment|invoice|paid|deposit|first payment|setup fee)",
    ],
    "closed_lost": [
        r"(?i)(decided to go in a different direction|decided to pass|going with someone else|chose another|went with another)",
        r"(?i)(not going to move forward|won't be moving forward|can't move forward|can't proceed|decided against)",
        r"(?i)(not the right fit at this time|not a match|not for us|doesn't align)",
        r"(?i)(put on hold|paused|deferred|delayed|postponed indefinitely)",
    ],
    "partnership_inquiry": [
        r"(?i)(partnership|partner with|collaborate|collaboration|joint venture|strategic alliance)",
        r"(?i)(would you be interested in partnering|explore partnership|partnership opportunity)",
        r"(?i)(affiliate|referral|revenue share|commission|co.marketing)",
    ],
    "creator_outreach": [
        r"(?i)(creator|influencer|content creator|talent|ambassador|brand advocate)",
        r"(?i)(we represent|we work with creators|creator network|creator community)",
        r"(?i)(looking for influencers|seeking creators|talent sourcing|recruiting creators)",
        r"(?i)(ugc|user generated content|sponsored content|brand deal|paid partnership)",
    ],
    "brand_outreach": [
        r"(?i)(brand outreach|reaching out to brands|brand partnership|brand collaboration)",
        r"(?i)(representing|agency representing|on behalf of|working with brands)",
        r"(?i)(we help brands|we work with brands|brand strategy|brand growth)",
    ],
    "referral": [
        r"(?i)(referred by|referral from|recommended by|introduced by|heard from|suggested by)",
        r"(?i)(reference|refer|recommend|introduction)",
        r"(?i)(john suggested|sarah mentioned|your colleague|your teammate|your coworker)",
    ],
    "existing_client": [
        r"(?i)(existing client|current client|onboarding|status update|monthly report|campaign update|quarterly review)",
        r"(?i)(as discussed|per our conversation|as per our agreement|as a client)",
        r"(?i)(renewal|upsell|cross.sell|expansion|additional services)",
    ],
    "proposal": [
        r"(?i)(proposal|proposal|propose|scope of work|sow|agreement|contract|terms|pricing|investment)",
        r"(?i)(here's our|we propose|recommend|suggested approach|strategy|plan for)",
    ],
}

SUBJECT_CLASSIFIER = {
    "cold_outreach": [
        r"(?i)(intro|introduction|reaching out|opportunity|partnership idea|collaboration)",
    ],
    "follow_up": [
        r"(?i)(follow.?up|checking in|circling back|just checking)",
    ],
    "meeting": [
        r"(?i)(meeting|call|calendar|schedule|booked|confirmed|invite|google meet|zoom|calendly)",
    ],
    "proposal": [
        r"(?i)(proposal|quote|estimate|pricing|agreement|sow)",
    ],
}


def classify_email(email: Dict) -> Tuple[str, str, Dict]:
    subject = email.get("subject", "")
    body = email.get("body_plain", "") or email.get("body", "")
    sender = email.get("sender", "").lower()
    is_reply = email.get("is_reply", 0)

    combined = f"{subject} {body}"
    scores = {}

    for category, patterns in CATEGORY_KEYWORDS.items():
        score = 0
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, combined)
            score += len(matches) * (1.0 / (i + 1))
        scores[category] = score

    if is_reply:
        if scores.get("positive_reply", 0) > 2:
            scores["cold_outreach"] *= 0.3
            scores["follow_up"] *= 0.3

    for category, patterns in SUBJECT_CLASSIFIER.items():
        for pattern in patterns:
            if re.search(pattern, subject):
                if category in scores:
                    scores[category] += 2
                else:
                    scores[category] = 2

    sorted_cats = sorted(scores.items(), key=lambda x: -x[1])

    primary_category = "unclassified"
    confidence_threshold = 0.5

    if sorted_cats and sorted_cats[0][1] >= confidence_threshold:
        primary_category = sorted_cats[0][0]

    subcategory = ""
    if len(sorted_cats) > 1 and sorted_cats[1][1] >= confidence_threshold * 0.7:
        subcategory = sorted_cats[1][0]

    if is_reply and primary_category == "cold_outreach" and scores.get("positive_reply", 0) > 0:
        if scores.get("positive_reply", 0) > scores.get("cold_outreach", 0) * 0.5:
            primary_category = "positive_reply"
            subcategory = "cold_outreach"

    return primary_category, subcategory, scores


def extract_prospect_info(email: Dict) -> Dict:
    body = email.get("body_plain", "") or email.get("body", "")
    subject = email.get("subject", "")
    sender = email.get("sender", "")
    sender_name = email.get("sender_name", "")

    info = {
        "name": sender_name or "",
        "email": sender or "",
        "company": "",
        "role": "",
        "industry": "",
        "location": "",
    }

    company_patterns = [
        r"(?i)(?:at|from|with|of)\s+([A-Z][A-Za-z0-9\s&.]+?)(?:[,\.!]|\s+as|\s+where|\s+who|\s+they)",
        r"(?i)(?:founder|CEO|CMO|head|director|manager|VP|lead)\s+(?:of|at|@)\s+([A-Z][A-Za-z0-9\s&.]+)",
        r"(?i)(?:company|agency|brand|startup|firm)\s+([A-Z][A-Za-z0-9\s&.]+?)(?:[,\.!]|\s+and|\s+is|\s+that)",
    ]
    for pat in company_patterns:
        m = re.search(pat, body)
        if m:
            info["company"] = m.group(1).strip()
            break

    role_patterns = [
        r"(?i)(?:I'm\s+(?:the|a|an)\s+)?([A-Za-z\s]+(?:CEO|CMO|COO|CTO|Founder|Co-founder|Director|Manager|Head|Lead|VP|President|Owner|Partner|Consultant|Strategist|Manager|Coordinator|Specialist))",
        r"(?i)(?:role|position|title|job)\s*(?::|is|as)\s*([A-Za-z\s]+(?:CEO|CMO|COO|CTO|Founder|Director|Manager|Head|Lead|VP))",
    ]
    for pat in role_patterns:
        m = re.search(pat, body)
        if m:
            info["role"] = m.group(1).strip()
            break

    industry_keywords = {
        "AI": r"(?i)(AI|artificial intelligence|machine learning|LLM|GPT|neural)",
        "SaaS": r"(?i)(SaaS|software as a service|cloud software|subscription)",
        "B2B Software": r"(?i)(B2B|enterprise software|business software|enterprise)",
        "Developer Tools": r"(?i)(developer|devtools|API|SDK|developer platform|dev tool)",
        "Health & Wellness": r"(?i)(health|wellness|fitness|supplement|nutrition|wellbeing)",
        "DTC E-commerce": r"(?i)(DTC|direct.to.consumer|ecommerce|e.commerce|online store|shopify)",
        "Consumer Apps": r"(?i)(consumer app|mobile app|iOS|Android|app store|download)",
        "Agencies": r"(?i)(marketing agency|creative agency|digital agency|PR agency|media agency)",
        "Financial Services": r"(?i)(fintech|finance|financial|banking|insurance|wealth|invest)",
        "Education": r"(?i)(edtech|education|learning|course|training|academy|university)",
    }
    for industry, pattern in industry_keywords.items():
        if re.search(pattern, body) or re.search(pattern, subject):
            info["industry"] = industry
            break

    location_patterns = [
        r"(?i)(?:based\s+(?:in|out\s+of))\s+([A-Z][A-Za-z\s]+?)(?:[,\.!]|\s+area|\s+region)",
        r"(?i)(?:located\s+in)\s+([A-Z][A-Za-z\s]+?)(?:[,\.!]|\s+area|\s+region)",
        r"(?i)(?:from|in)\s+(San Francisco|New York|Los Angeles|Austin|Miami|Chicago|London|Berlin|Toronto|Sydney|Singapore|Dubai|Paris)",
    ]
    for pat in location_patterns:
        m = re.search(pat, body)
        if m:
            info["location"] = m.group(1).strip()
            break

    if not info["company"] and "@" in sender:
        domain = sender.split("@")[1]
        if domain not in ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "proton.me", "protonmail.com"]:
            info["company"] = domain.split(".")[0].title()

    return info


def calculate_sentiment(text: str) -> float:
    try:
        from textblob import TextBlob
        blob = TextBlob(text[:5000])
        return blob.sentiment.polarity
    except ImportError:
        pass

    positive_words = [
        "great", "excellent", "amazing", "love", "perfect", "wonderful", "fantastic",
        "interested", "exciting", "happy", "pleased", "thank", "thanks", "appreciate",
        "yes", "absolutely", "definitely", "looking forward", "excited", "welcome",
        "impressed", "outstanding", "brilliant", "awesome", "incredible", "best",
        "solution", "value", "opportunity", "growth", "success", "win", "positive",
    ]
    negative_words = [
        "not interested", "unfortunately", "sorry", "bad", "terrible", "awful",
        "hate", "disappointed", "frustrated", "angry", "upset", "worried", "concerned",
        "expensive", "too much", "no budget", "can't", "won't", "don't", "never",
        "problem", "issue", "difficult", "hard", "impossible", "waste", "poor",
        "reject", "decline", "pass", "busy", "swamped",
    ]
    text_lower = text.lower()
    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    total = pos_count + neg_count
    if total == 0:
        return 0.0
    return (pos_count - neg_count) / total


def calculate_personalization_depth(text: str, sender_name: str = "", company: str = "") -> float:
    score = 0.0
    factors = []

    if sender_name and sender_name.lower() in text.lower():
        factors.append(("name_mention", 0.2))

    if company and company.lower() in text.lower():
        factors.append(("company_mention", 0.15))

    ref_patterns = [
        (r"(?i)(saw|noticed|came across|read about)\s+(your|the)", 0.1),
        (r"(?i)(your\s+(post|article|video|content|work|website|product|service))", 0.1),
        (r"(?i)(i\s+(liked|loved|enjoyed|was impressed by))", 0.1),
        (r"(?i)(specifically|particular reason|because you)", 0.05),
        (r"(?i)(mentioned|referred|referenced|highlighted)", 0.05),
        (r"(?i)(your\s+(recent|latest|newest))", 0.05),
        (r"(?i)(i see that|understand that|noticed that|saw that)", 0.05),
    ]
    for pat, val in ref_patterns:
        if re.search(pat, text):
            factors.append((pat, val))

    generic_patterns = [
        r"(?i)(dear sir|dear madam|to whom it may concern|valued customer)",
        r"(?i)(i'm reaching out to offer|i wanted to share with you|i thought you might be interested)",
        r"(?i)(i represent|our company specializes|we are a leading)",
    ]
    for pat in generic_patterns:
        if re.search(pat, text):
            factors.append((pat, -0.1))

    score = sum(v for _, v in factors)
    return max(0.0, min(1.0, score))


def calculate_engagement_score(email: Dict) -> float:
    score = 0.0

    sentiment = email.get("sentiment_score", 0.0)
    score += sentiment * 0.3

    wc = email.get("word_count", 0)
    if wc > 200:
        score += 0.2
    elif wc > 100:
        score += 0.1

    body = email.get("body_plain", "") or email.get("body", "")
    questions = len(re.findall(r"\?", body))
    score += min(questions * 0.05, 0.2)

    if re.search(r"(?i)(call|meet|talk|discuss|hop on|schedule|book|calendar|demo)", body):
        score += 0.1

    if re.search(r"(?i)(my|i|we|our)\s+(company|team|brand|business|agency)", body):
        score += 0.1

    if len(set(body.split())) > 50:
        score += 0.1

    return max(-0.5, min(1.0, score))
