"""Generate realistic demo data for the agency intelligence system"""
import json
import statistics
from datetime import datetime, timedelta
from random import choice, randint, uniform, random
from database import get_conn, init_db
from classifier import (
    classify_email, calculate_sentiment, calculate_personalization_depth,
    extract_prospect_info
)


PROSPECTS = [
    {"name": "Sarah Chen", "email": "sarah@luminary.ai", "company": "Luminary AI", "industry": "AI", "role": "Head of Marketing", "location": "San Francisco"},
    {"name": "Marcus Johnson", "email": "marcus@growthloop.io", "company": "GrowthLoop", "industry": "SaaS", "role": "CMO", "location": "New York"},
    {"name": "Emily Rodriguez", "email": "emily@wellnesswave.com", "company": "Wellness Wave", "industry": "Health & Wellness", "role": "Brand Director", "location": "Los Angeles"},
    {"name": "David Park", "email": "david@devhub.com", "company": "DevHub", "industry": "Developer Tools", "role": "CEO", "location": "Austin"},
    {"name": "Jessica Thompson", "email": "jessica@shopvivid.com", "company": "ShopVivid", "industry": "DTC E-commerce", "role": "Founder", "location": "Miami"},
    {"name": "Alex Novak", "email": "alex@finwise.ai", "company": "FinWise", "industry": "Financial Services", "role": "VP Marketing", "location": "Chicago"},
    {"name": "Sophie Williams", "email": "sophie@learncraft.io", "company": "LearnCraft", "industry": "Education", "role": "Head of Growth", "location": "London"},
    {"name": "Ryan O'Brien", "email": "ryan@creativelaunch.com", "company": "CreativeLaunch", "industry": "Agencies", "role": "Director", "location": "Toronto"},
    {"name": "Maya Patel", "email": "maya@consumerlab.app", "company": "ConsumerLab", "industry": "Consumer Apps", "role": "Growth Lead", "location": "Berlin"},
    {"name": "Tom Anderson", "email": "tom@enterpriseforge.com", "company": "EnterpriseForge", "industry": "B2B Software", "role": "CEO", "location": "Seattle"},
    {"name": "Lisa Kim", "email": "lisa@pureglow.co", "company": "PureGlow", "industry": "Health & Wellness", "role": "Founder", "location": "New York"},
    {"name": "Chris Miller", "email": "chris@dataweave.io", "company": "DataWeave", "industry": "AI", "role": "CTO", "location": "San Francisco"},
    {"name": "Amanda Foster", "email": "amanda@eduspark.com", "company": "EduSpark", "industry": "Education", "role": "VP Product", "location": "Boston"},
    {"name": "James Wilson", "email": "james@retailnext.com", "company": "RetailNext", "industry": "DTC E-commerce", "role": "Marketing Director", "location": "Denver"},
    {"name": "Natasha Kumar", "email": "natasha@nexuspay.io", "company": "NexusPay", "industry": "Financial Services", "role": "Head of Growth", "location": "Singapore"},
    {"name": "Daniel Martinez", "email": "daniel@pixelperfect.dev", "company": "PixelPerfect", "industry": "Developer Tools", "role": "Founder", "location": "Portland"},
    {"name": "Rachel Green", "email": "rachel@greenecosystem.com", "company": "Green Ecosystem", "industry": "Consumer Apps", "role": "CEO", "location": "Amsterdam"},
    {"name": "Kevin Brown", "email": "kevin@stackbase.co", "company": "StackBase", "industry": "SaaS", "role": "VP Sales", "location": "Dublin"},
    {"name": "Olivia Taylor", "email": "olivia@nurture.ai", "company": "Nurture AI", "industry": "AI", "role": "CMO", "location": "Tel Aviv"},
    {"name": "Brandon Lee", "email": "brandon@fitpulse.com", "company": "FitPulse", "industry": "Health & Wellness", "role": "Brand Manager", "location": "Sydney"},
    {"name": "Stephanie Wright", "email": "stephanie@codelab.io", "company": "CodeLab", "industry": "Developer Tools", "role": "Head of Product", "location": "Vancouver"},
    {"name": "Michael Torres", "email": "michael@shopstream.com", "company": "ShopStream", "industry": "DTC E-commerce", "role": "Growth Director", "location": "Atlanta"},
    {"name": "Priya Sharma", "email": "priya@sagewellness.com", "company": "Sage Wellness", "industry": "Health & Wellness", "role": "Founder", "location": "Mumbai"},
    {"name": "Andrew Scott", "email": "andrew@logixml.com", "company": "LogiXML", "industry": "B2B Software", "role": "CEO", "location": "Phoenix"},
    {"name": "Hannah Baker", "email": "hannah@creatorhub.io", "company": "CreatorHub", "industry": "Agencies", "role": "Director of Partnerships", "location": "Nashville"},
    {"name": "Nathan Drake", "email": "nathan@exploremore.io", "company": "ExploreMore", "industry": "Consumer Apps", "role": "CEO", "location": "Melbourne"},
    {"name": "Elena Fisher", "email": "elena@newsvault.com", "company": "NewsVault", "industry": "SaaS", "role": "Head of Content", "location": "San Francisco"},
    {"name": "Victor Sullivan", "email": "victor@antiqueco.com", "company": "Antique & Co", "industry": "DTC E-commerce", "role": "Founder", "location": "London"},
    {"name": "Chloe Frazer", "email": "chloe@desertbloom.com", "company": "Desert Bloom", "industry": "Health & Wellness", "role": "Brand Director", "location": "Dubai"},
    {"name": "Samuel Drake", "email": "samuel@deepdive.ai", "company": "DeepDive AI", "industry": "AI", "role": "CTO", "location": "Boston"},
    {"name": "Nadine Ross", "email": "nadine@shoreline.dev", "company": "Shoreline Dev", "industry": "Developer Tools", "role": "VP Engineering", "location": "Seattle"},
    {"name": "Charlie Cutter", "email": "charlie@cutterco.com", "company": "Cutter & Co", "industry": "Agencies", "role": "Managing Partner", "location": "Manchester"},
    {"name": "Marlowe", "email": "marlowe@heritageinstitute.com", "company": "Heritage Institute", "industry": "Education", "role": "Director", "location": "Oxford"},
    {"name": "Rika Raja", "email": "rika@capitalbridge.com", "company": "Capital Bridge", "industry": "Financial Services", "role": "VP Growth", "location": "Mumbai"},
]

SUBJECT_TEMPLATES = {
    "cold_outreach": [
        "{prospect_name}, quick idea for {company}",
        "Helping {company} scale creator partnerships",
        "{company}'s influencer opportunity",
        "Idea for {company}'s creator strategy",
        "Quick thought re: {company}",
        "{prospect_name}, noticed something about {company}",
        "{company} x influencer marketing",
        "Strategic partnership idea for {company}",
        "How we helped similar brands grow 3x",
        "{prospect_name}, a growth angle for {company}",
    ],
    "follow_up": [
        "Re: {subject}",
        "Following up: {subject}",
        "Bumping this up",
        "Quick follow up, {prospect_name}",
        "Circling back on this",
        "{prospect_name}, any thoughts?",
        "Just checking in",
        "Wanted to make sure you saw this",
    ],
    "positive_reply": [
        "Re: {subject}",
        "Thanks! Let's discuss",
        "Interested - tell me more",
        "Sounds great, let's talk",
        "Re: {subject} - schedule?",
    ],
    "meeting_booked": [
        "Re: {subject} - Confirmed",
        "Meeting confirmed: {company} x Agency",
        "Calendar invite: Discovery call",
        "Looking forward to our chat",
    ],
    "proposal_sent": [
        "Proposal for {company}: Creator Partnership Program",
        "Scope of work: {company} x Agency",
        "Agreement - {company} Creator Strategy",
        "Proposed approach for {company}",
    ],
    "objection": [
        "Re: {subject}",
        "Not right now, but thanks",
        "Not a fit at this time",
    ],
}

BODY_TEMPLATES = {
    "cold_outreach": [
        "Hey {prospect_name},\n\nI've been following {company}'s growth and noticed your recent {achievement}. Your approach to {topic} is really impressive.\n\nWe specialize in helping {industry} brands build scalable influencer marketing programs. Recently helped a similar company achieve {result} through creator partnerships.\n\nWould you be open to a quick 15-min chat to explore if there's a fit?\n\nBest,\n{Agency}",
        "Hi {prospect_name},\n\nCame across {company} and love what you're doing with {topic}. Given your growth trajectory, I think we could help accelerate your creator marketing efforts.\n\nWe work with {industry} companies to {value_prop}. A client in your space saw {result} within 60 days.\n\nOpen to a brief call this week?\n\nCheers,\n{Agency}",
        "Hello {prospect_name},\n\n{company} has been on my radar - impressive work with {topic}. I have a specific idea for how you could leverage influencer partnerships to drive {result}.\n\nWe've helped {industry} brands generate {result_metric} through creator-led campaigns.\n\nWorth a quick conversation?\n\nBest,\n{Agency}",
    ],
    "follow_up": [
        "Hey {prospect_name},\n\nJust bumping this up in case it got buried. Would love to share how we helped {similar_company} achieve {result}.\n\nAny interest in a quick chat?\n\nBest,\n{Agency}",
        "Hi {prospect_name},\n\nFollowing up on my note from last week. Here's a quick case study of a {industry} brand we worked with: {result_detail}.\n\nWould a 15-min call make sense?\n\nBest,\n{Agency}",
        "{prospect_name},\n\nLast note on this - I really think we could move the needle for {company}'s creator strategy.\n\nWould you be open to a 10-min intro call?\n\nBest,\n{Agency}",
    ],
    "positive_reply": [
        "Thanks for the note! I'd love to learn more about how you work with creators. Could you share some examples?",
        "This looks interesting! Tell me more about your approach and what a typical engagement looks like.",
        "Sounds promising! Let's find a time to discuss further. What does your calendar look like next week?",
        "I'm intrigued. Can you send over some case studies or examples of work you've done?",
    ],
    "meeting_booked": [
        "Great, looking forward to our chat on {date}. Here's a Calendly link to confirm: https://calendly.com/agency/discovery",
        "Perfect, {date} works. I'll send a calendar invite. Looking forward to discussing how we can help {company} grow through creator partnerships.",
        "Confirmed! Talk then. In the meantime, here's a quick overview of how we work: [link]",
    ],
    "objection": [
        "Thanks for reaching out, but we're currently focused on other initiatives and don't have the budget for this right now.",
        "Appreciate the note, but we're already working with an agency on our influencer strategy. Not looking to switch at this time.",
        "This looks interesting but it's not a priority for us right now. Maybe check in next quarter?",
    ],
}

AGENCY_NAME = "Growth Creators Agency"
AGENCY_EMAIL = "hello@growthcreators.com"

INDUSTRY_ACHIEVEMENTS = {
    "AI": {"topic": "AI product development", "achievement": "fundraising round", "result": "40% increase in influencer-driven pipeline"},
    "SaaS": {"topic": "growth initiatives", "achievement": "product expansion", "result": "3x ROI on creator partnerships"},
    "Health & Wellness": {"topic": "wellness content", "achievement": "brand refresh", "result": "200% increase in UGC content output"},
    "DTC E-commerce": {"topic": "brand building", "achievement": "growth in DTC", "result": "50% reduction in CAC through creators"},
    "Developer Tools": {"topic": "community building", "achievement": "developer traction", "result": "25K+ creator-generated content pieces"},
    "Financial Services": {"topic": "financial education", "achievement": "market expansion", "result": "35% higher engagement through creator content"},
    "Education": {"topic": "learning content", "achievement": "course expansion", "result": "60% increase in enrollment via creators"},
    "Consumer Apps": {"topic": "app growth", "achievement": "user acquisition", "result": "4x organic reach through creator campaigns"},
    "Agencies": {"topic": "agency partnerships", "achievement": "capability expansion", "result": "$500K+ in creator partnership revenue"},
    "B2B Software": {"topic": "B2B marketing", "achievement": "brand awareness", "result": "200+ qualified leads through creator content"},
}


def generate_demo_data():
    init_db()
    conn = get_conn()

    # Clear existing data
    conn.execute("DELETE FROM emails")
    conn.execute("DELETE FROM conversations")
    conn.commit()

    now = datetime.now()
    email_id_counter = 0
    conversation_data = {}

    for prospect in PROSPECTS:
        # Outcome probability - separate rolls for different stages
        pos_roll = random()
        meet_roll = random()
        close_roll = random()
        has_positive_outcome = pos_roll < 0.40
        has_meeting_outcome = has_positive_outcome and meet_roll < 0.55
        has_close_outcome = has_meeting_outcome and close_roll < 0.50

        # Random number of touch points based on outcome
        if has_close_outcome:
            num_touches = randint(7, 10)
        elif has_meeting_outcome:
            num_touches = randint(5, 7)
        elif has_positive_outcome:
            num_touches = randint(3, 5)
        else:
            num_touches = randint(2, 4)
        base_time = now - timedelta(days=randint(30, 180))

        industry_info = INDUSTRY_ACHIEVEMENTS.get(prospect["industry"], {
            "topic": "content strategy",
            "achievement": "recent success",
            "result": "significant growth",
        })
        conversation_id = None

        for touch in range(num_touches):
            touch_date = base_time + timedelta(days=touch * randint(2, 7))

            if touch == 0:
                # Cold outreach
                subject = choice(SUBJECT_TEMPLATES["cold_outreach"]).format(
                    prospect_name=prospect["name"].split()[0],
                    company=prospect["company"],
                )
                body_template = choice(BODY_TEMPLATES["cold_outreach"])
                body = body_template.format(
                    prospect_name=prospect["name"].split()[0],
                    company=prospect["company"],
                    industry=prospect["industry"],
                    topic=industry_info["topic"],
                    achievement=industry_info["achievement"],
                    result=industry_info["result"],
                    result_metric=industry_info["result"].lower(),
                    value_prop="build scalable creator programs that drive measurable ROI",
                    similar_company=choice(["a comparable SaaS company", "a similar brand", "a peer in your space"]),
                    result_detail=f"achieved {industry_info['result']} within 60 days",
                    Agency=AGENCY_NAME,
                )
                cat = "cold_outreach"
            elif touch < 4:
                # Follow up or reply
                if has_positive_outcome and touch == 2:
                    # Positive reply
                    subject = choice(SUBJECT_TEMPLATES["positive_reply"]).format(subject=subject)
                    body = choice(BODY_TEMPLATES["positive_reply"])
                    cat = "positive_reply"
                    conversation_id = "pos_" + prospect["email"]
                elif not has_positive_outcome and touch == 3 and random() < 0.4:
                    # Objection
                    subject = choice(SUBJECT_TEMPLATES["objection"]).format(subject=subject)
                    body = choice(BODY_TEMPLATES["objection"])
                    cat = "objection"
                    conversation_id = "obj_" + prospect["email"]
                else:
                    subject = choice(SUBJECT_TEMPLATES["follow_up"]).format(
                        prospect_name=prospect["name"].split()[0],
                        subject=subject[:30],
                    )
                    body = choice(BODY_TEMPLATES["follow_up"]).format(
                        prospect_name=prospect["name"].split()[0],
                        industry=prospect["industry"],
                        similar_company=choice(["a leading brand", "a company like yours", "a peer company"]),
                        result=industry_info["result"],
                        result_detail=f"achieved {industry_info['result']}",
                        Agency=AGENCY_NAME,
                        company=prospect["company"],
                    )
                    cat = "follow_up"
            else:
                if has_close_outcome and touch == 5:
                    subject = choice(SUBJECT_TEMPLATES["meeting_booked"]).format(
                        subject=subject[:30],
                        company=prospect["company"],
                    )
                    body = choice(BODY_TEMPLATES["meeting_booked"]).format(
                        date=(touch_date + timedelta(days=3)).strftime("%A, %B %d"),
                        company=prospect["company"],
                    )
                    cat = "meeting_booked"
                elif has_meeting_outcome and touch == 4:
                    subject = choice(SUBJECT_TEMPLATES["meeting_booked"]).format(
                        subject=subject[:30],
                        company=prospect["company"],
                    )
                    body = choice(BODY_TEMPLATES["meeting_booked"]).format(
                        date=(touch_date + timedelta(days=3)).strftime("%A, %B %d"),
                        company=prospect["company"],
                    )
                    cat = "meeting_booked"
                elif has_close_outcome and touch == 6:
                    # Proposal sent
                    subject = choice(SUBJECT_TEMPLATES["proposal_sent"]).format(
                        company=prospect["company"],
                    )
                    body = "Here is our proposal for the creator partnership program. We're excited about the opportunity to work together."
                    cat = "proposal_sent"
                elif has_close_outcome and touch == 7:
                    # Closed won
                    subject = "Welcome to the team!"
                    body = "We're thrilled to start working together. Let's kick off next week."
                    cat = "closed_won"
                elif conversation_id and "obj_" in str(conversation_id):
                    break
                else:
                    continue

            email_id_counter += 1
            email_id = f"demo_{email_id_counter}"

            is_reply = 1 if touch > 0 else 0
            sentiment = calculate_sentiment(body)
            personalization = calculate_personalization_depth(body, prospect["name"].split()[0], prospect["company"])

            email_data = {
                "id": email_id,
                "thread_id": f"thread_{prospect['email'].replace('@', '_')}",
                "subject": subject,
                "sender": AGENCY_EMAIL if touch == 0 else prospect["email"],
                "sender_name": AGENCY_NAME if touch == 0 else prospect["name"],
                "recipient": prospect["email"] if touch == 0 else AGENCY_EMAIL,
                "recipient_name": prospect["name"] if touch == 0 else AGENCY_NAME,
                "body": body,
                "body_plain": body,
                "date_sent": touch_date.isoformat(),
                "label": "SENT" if touch == 0 else "INBOX",
                "category": cat,
                "is_reply": is_reply,
                "in_reply_to": f"msg_{email_id_counter - 1}" if is_reply else "",
                "message_count": touch + 1,
                "engagement_score": uniform(0, 1) if cat == "positive_reply" else uniform(0, 0.5),
                "sentiment_score": sentiment,
                "personalization_score": personalization,
                "word_count": len(body.split()),
                "has_attachment": 0,
                "has_tracking": 0,
                "prospect_name": prospect["name"],
                "prospect_email": prospect["email"],
                "prospect_company": prospect["company"],
                "prospect_role": prospect["role"],
                "prospect_industry": prospect["industry"],
                "prospect_location": prospect["location"],
                "raw_metadata": {"demo": True, "touch_number": touch + 1},
            }

            sql = (
                "INSERT INTO emails ("
                "id, thread_id, subject, sender, sender_name, recipient, recipient_name, "
                "body, body_plain, date_sent, label, category, is_reply, in_reply_to, "
                "message_count, engagement_score, sentiment_score, personalization_score, "
                "word_count, has_attachment, has_tracking, prospect_name, prospect_email, "
                "prospect_company, prospect_role, prospect_industry, prospect_location, "
                "raw_metadata"
                ") VALUES ("
                "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?"
                ")"
            )
            conn.execute(sql, (
                email_data["id"], email_data["thread_id"], email_data["subject"],
                email_data["sender"], email_data["sender_name"],
                email_data["recipient"], email_data["recipient_name"],
                email_data["body"], email_data["body_plain"],
                email_data["date_sent"], email_data["label"],
                email_data["category"], email_data["is_reply"],
                email_data["in_reply_to"], email_data["message_count"],
                email_data["engagement_score"], email_data["sentiment_score"],
                email_data["personalization_score"], email_data["word_count"],
                email_data["has_attachment"], email_data["has_tracking"],
                email_data["prospect_name"], email_data["prospect_email"],
                email_data["prospect_company"], email_data["prospect_role"],
                email_data["prospect_industry"], email_data["prospect_location"],
                json.dumps(email_data["raw_metadata"])
            ))

        # Create conversation record
        thread_id = f"thread_{prospect['email'].replace('@', '_')}"
        conv_emails = conn.execute(
            "SELECT * FROM emails WHERE thread_id = ? ORDER BY date_sent",
            (thread_id,)
        ).fetchall()

        if conv_emails:
            emails_list = [dict(e) for e in conv_emails]
            first = emails_list[0]
            last = emails_list[-1]

            categories = [e["category"] for e in emails_list]
            has_positive = "positive_reply" in categories
            has_meeting = "meeting_booked" in categories
            has_proposal = "proposal_sent" in categories
            has_objection = "objection" in categories

            # Determine outcome
            if has_close_outcome:
                outcome = "closed_won"
                deal_value = round(uniform(5000, 25000), 2)
                stage = "closed_won"
                funnel_stage = "closed_won"
                is_won = 1
                cat = "closed_won"
            elif has_meeting_outcome:
                outcome = "meeting_done"
                deal_value = 0
                stage = "negotiation"
                funnel_stage = "meeting"
                is_won = 0
                cat = "meeting_booked"
            elif has_positive_outcome:
                outcome = "positive_no_meeting"
                deal_value = 0
                stage = "qualified"
                funnel_stage = "interest"
                is_won = 0
                cat = "positive_reply"
            elif has_objection:
                outcome = "lost"
                deal_value = 0
                stage = "lost"
                funnel_stage = "closed_lost"
                is_won = 0
                cat = "closed_lost"
            else:
                outcome = "no_reply"
                deal_value = 0
                stage = "outreach"
                funnel_stage = "awareness"
                is_won = 0
                cat = "cold_outreach"

            try:
                first_date = datetime.fromisoformat(first["date_sent"])
                last_date = datetime.fromisoformat(last["date_sent"])
                cycle_days = (last_date - first_date).days
            except (ValueError, TypeError):
                cycle_days = 0

            follow_ups = len([e for e in emails_list if e["category"] == "follow_up"])
            reply_count = len([e for e in emails_list if e["is_reply"]])
            pos_count = len([e for e in emails_list if e["category"] == "positive_reply"])
            sentiments = [e["sentiment_score"] for e in emails_list if e["sentiment_score"] != 0]
            sentiment_trend = "positive" if (sentiments and statistics.mean(sentiments) > 0.1) else "negative" if (sentiments and statistics.mean(sentiments) < -0.1) else "neutral"



            conv_data = {
                "id": f"conv_{prospect['email'].replace('@', '_')}",
                "thread_id": thread_id,
                "subject": first["subject"],
                "prospect_email": prospect["email"],
                "prospect_name": prospect["name"],
                "prospect_company": prospect["company"],
                "prospect_industry": prospect["industry"],
                "prospect_role": prospect["role"],
                "prospect_location": prospect["location"],
                "first_contact_date": first["date_sent"],
                "last_contact_date": last["date_sent"],
                "total_messages": len(emails_list),
                "category": cat,
                "subcategory": "",
                "deal_stage": stage,
                "deal_value": deal_value,
                "outcome": outcome,
                "sales_cycle_days": cycle_days,
                "num_follow_ups": follow_ups,
                "reply_count": reply_count,
                "positive_reply_count": pos_count,
                "sentiment_trend": sentiment_trend,
                "personalization_depth": round(uniform(0.2, 0.8), 2) if not has_objection else round(uniform(0.1, 0.4), 2),
                "primary_category": cat,
                "is_positive": 1 if has_positive else 0,
                "is_meeting_booked": 1 if has_meeting else 0,
                "is_proposal_sent": 1 if has_proposal else 0,
                "is_closed_won": is_won,
                "funnel_stage": funnel_stage,
                "tags": "",
                "notes": "",
                "raw_data": json.dumps({"emails": [e["id"] for e in emails_list]}),
            }

            sql = (
                "INSERT INTO conversations ("
                "id, thread_id, subject, prospect_email, prospect_name, prospect_company, "
                "prospect_industry, prospect_role, prospect_location, first_contact_date, "
                "last_contact_date, total_messages, category, subcategory, deal_stage, "
                "deal_value, outcome, sales_cycle_days, num_follow_ups, reply_count, "
                "positive_reply_count, sentiment_trend, personalization_depth, "
                "primary_category, is_positive, is_meeting_booked, is_proposal_sent, "
                "is_closed_won, funnel_stage, tags, notes, raw_data"
                ") VALUES ("
                "?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?"
                ")"
            )
            conn.execute(sql, (
                conv_data["id"], conv_data["thread_id"], conv_data["subject"],
                conv_data["prospect_email"], conv_data["prospect_name"],
                conv_data["prospect_company"], conv_data["prospect_industry"],
                conv_data["prospect_role"], conv_data["prospect_location"],
                conv_data["first_contact_date"], conv_data["last_contact_date"],
                conv_data["total_messages"], conv_data["category"],
                conv_data["subcategory"], conv_data["deal_stage"],
                conv_data["deal_value"], conv_data["outcome"],
                conv_data["sales_cycle_days"], conv_data["num_follow_ups"],
                conv_data["reply_count"], conv_data["positive_reply_count"],
                conv_data["sentiment_trend"], conv_data["personalization_depth"],
                conv_data["primary_category"], conv_data["is_positive"],
                conv_data["is_meeting_booked"], conv_data["is_proposal_sent"],
                conv_data["is_closed_won"], conv_data["funnel_stage"],
                conv_data["tags"], conv_data["notes"], conv_data["raw_data"]
            ))

    conn.commit()
    conn.close()
    print(f"Demo data generated: {email_id_counter} emails, {len(PROSPECTS)} prospects")


if __name__ == "__main__":
    generate_demo_data()
