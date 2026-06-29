import re
import json
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter

from database import get_all_conversations, get_all_emails


class AgencyAnalytics:
    """Core analytics engine for the agency intelligence system"""

    def __init__(self):
        self.conversations = get_all_conversations()
        self.emails = get_all_emails()
        self._process()

    def _process(self):
        """Pre-process and enrich data"""
        pass

    # ========== PIPELINE ANALYSIS ==========

    def get_pipeline_summary(self) -> Dict:
        total = len(self.conversations)
        stages = defaultdict(int)
        outcomes = defaultdict(int)
        segments = defaultdict(int)

        for conv in self.conversations:
            stage = conv.get("funnel_stage", "unknown")
            stages[stage] += 1
            outcome = conv.get("outcome", "unknown")
            outcomes[outcome] += 1
            ind = conv.get("prospect_industry", "unknown")
            segments[ind] += 1

        return {
            "total_conversations": total,
            "stages": dict(stages),
            "outcomes": dict(outcomes),
            "segments": dict(segments),
        }

    def build_pipeline_timeline(self) -> List[Dict]:
        timeline = []
        for conv in self.conversations:
            timeline.append({
                "prospect_name": conv.get("prospect_name", "Unknown"),
                "prospect_company": conv.get("prospect_company", ""),
                "prospect_industry": conv.get("prospect_industry", ""),
                "first_contact": conv.get("first_contact_date", ""),
                "last_contact": conv.get("last_contact_date", ""),
                "total_messages": conv.get("total_messages", 0),
                "num_follow_ups": conv.get("num_follow_ups", 0),
                "category": conv.get("category", ""),
                "outcome": conv.get("outcome", "open"),
                "funnel_stage": conv.get("funnel_stage", "awareness"),
                "deal_value": conv.get("deal_value", 0),
                "sales_cycle_days": conv.get("sales_cycle_days", 0),
                "is_positive": bool(conv.get("is_positive")),
                "is_meeting_booked": bool(conv.get("is_meeting_booked")),
                "is_proposal_sent": bool(conv.get("is_proposal_sent")),
                "is_closed_won": bool(conv.get("is_closed_won")),
            })
        return sorted(timeline, key=lambda x: x.get("first_contact", ""), reverse=True)

    def get_funnel_conversion(self) -> Dict:
        total = len(self.conversations)
        if total == 0:
            return {}

        with_positive = sum(1 for c in self.conversations if c.get("is_positive"))
        with_meeting = sum(1 for c in self.conversations if c.get("is_meeting_booked"))
        with_proposal = sum(1 for c in self.conversations if c.get("is_proposal_sent"))
        closed_won = sum(1 for c in self.conversations if c.get("is_closed_won"))

        return {
            "total_outreach": total,
            "positive_replies": with_positive,
            "meetings_booked": with_meeting,
            "proposals_sent": with_proposal,
            "closed_won": closed_won,
            "positive_rate": round(with_positive / total * 100, 1) if total else 0,
            "meeting_booking_rate": round(with_meeting / total * 100, 1) if total else 0,
            "proposal_rate": round(with_proposal / total * 100, 1) if total else 0,
            "close_rate": round(closed_won / total * 100, 1) if total else 0,
            "meeting_to_proposal": round(with_proposal / with_meeting * 100, 1) if with_meeting else 0,
            "proposal_to_close": round(closed_won / with_proposal * 100, 1) if with_proposal else 0,
            "positive_to_meeting": round(with_meeting / with_positive * 100, 1) if with_positive else 0,
        }

    # ========== ADVANCED METRICS ==========

    def calculate_advanced_metrics(self) -> Dict:
        convs = self.conversations
        emails = self.emails

        # Reply rate
        total_outreach = len(convs)
        replied = sum(1 for c in convs if c.get("reply_count", 0) > 0)
        reply_rate = round(replied / total_outreach * 100, 1) if total_outreach else 0

        # Average sales cycle
        closed = [c for c in convs if c.get("sales_cycle_days") and c.get("sales_cycle_days", 0) > 0]
        avg_cycle = round(statistics.mean([c["sales_cycle_days"] for c in closed]), 1) if closed else 0

        # Average deal value
        won = [c for c in convs if c.get("is_closed_won") and c.get("deal_value")]
        avg_deal = round(statistics.mean([c["deal_value"] for c in won]), 2) if won else 0
        total_revenue = sum(c.get("deal_value", 0) for c in won) if won else 0

        # Follow-up analysis
        with_followups = [c for c in convs if c.get("num_follow_ups", 0) > 0]
        avg_followups = round(statistics.mean([c["num_follow_ups"] for c in convs]), 1) if convs else 0
        won_followups = round(statistics.mean([c["num_follow_ups"] for c in won]), 1) if won else 0

        # Response rate by touch
        touch_rates = self._calculate_touch_rates()

        # Personalization impact
        pers_impact = self._analyze_personalization_impact()

        # Customer Acquisition Cost (estimated)
        # Assume ~$0.05 per email (Gmail API + labor), plus labor per outreach
        estimated_cost_per_email = 0.05  # $0.05 for tooling
        estimated_labor_per_outreach = 2.0  # $2 worth of time per outreach
        total_emails = len(emails)
        estimated_spend = (total_emails * estimated_cost_per_email) + (total_outreach * estimated_labor_per_outreach)
        cac = round(estimated_spend / len(won), 2) if won else 0

        # Projected LTV
        avg_retention_months = 8  # typical agency retention
        monthly_revenue = avg_deal / 3 if avg_deal else 0  # assume 3-month engagements
        ltv = round(monthly_revenue * avg_retention_months, 2)

        return {
            "total_emails_analyzed": len(emails),
            "total_conversations": total_outreach,
            "reply_rate": reply_rate,
            "total_replied": replied,
            "avg_sales_cycle_days": avg_cycle,
            "avg_deal_value": avg_deal,
            "total_revenue": total_revenue,
            "avg_followups_per_conversation": avg_followups,
            "avg_followups_won": won_followups,
            "estimated_cac": cac,
            "estimated_ltv": ltv,
            "ltv_cac_ratio": round(ltv / cac, 2) if cac else 0,
            "touch_response_rates": touch_rates,
            "personalization_impact": pers_impact,
        }

    def _calculate_touch_rates(self) -> Dict:
        """Calculate response rate by touch number"""
        touch_counts = defaultdict(int)
        touch_positives = defaultdict(int)
        touch_meetings = defaultdict(int)

        for conv in self.conversations:
            total_msgs = conv.get("total_messages", 0)
            touch = min(total_msgs, 6)

            if conv.get("reply_count", 0) > 0:
                touch_positives[touch] += 1
            if conv.get("is_meeting_booked"):
                touch_meetings[touch] += 1
            touch_counts[touch] += 1

        rates = {}
        for touch, count in sorted(touch_counts.items()):
            pos_rate = round(touch_positives[touch] / count * 100, 1) if count else 0
            meet_rate = round(touch_meetings[touch] / count * 100, 1) if count else 0
            label = f"touch_{touch}" if touch < 7 else "touch_7plus"
            rates[label] = {
                "count": count,
                "positive_rate": pos_rate,
                "meeting_rate": meet_rate,
            }

        return rates

    def _analyze_personalization_impact(self) -> Dict:
        """Analyze how personalization depth correlates with outcomes"""
        high_pers = [c for c in self.conversations if c.get("personalization_depth", 0) > 0.5]
        low_pers = [c for c in self.conversations if c.get("personalization_depth", 0) <= 0.3]
        med_pers = [c for c in self.conversations if 0.3 < c.get("personalization_depth", 0) <= 0.5]

        def compute_rate(group):
            if not group:
                return {"count": 0, "positive_rate": 0, "meeting_rate": 0, "close_rate": 0}
            pos = sum(1 for c in group if c.get("is_positive"))
            meet = sum(1 for c in group if c.get("is_meeting_booked"))
            won = sum(1 for c in group if c.get("is_closed_won"))
            return {
                "count": len(group),
                "positive_rate": round(pos / len(group) * 100, 1),
                "meeting_rate": round(meet / len(group) * 100, 1),
                "close_rate": round(won / len(group) * 100, 1),
            }

        return {
            "high_personalization": compute_rate(high_pers),
            "medium_personalization": compute_rate(med_pers),
            "low_personalization": compute_rate(low_pers),
        }

    # ========== SEGMENTATION ==========

    def analyze_segments(self) -> Dict:
        industries = defaultdict(lambda: {"count": 0, "positive": 0, "meetings": 0, "proposals": 0, "won": 0, "revenue": 0})
        roles = defaultdict(lambda: {"count": 0, "positive": 0, "meetings": 0})
        locations = defaultdict(lambda: {"count": 0, "positive": 0, "meetings": 0})
        email_domains = defaultdict(int)

        for conv in self.conversations:
            ind = conv.get("prospect_industry", "Unknown") or "Unknown"
            role = conv.get("prospect_role", "Unknown") or "Unknown"
            loc = conv.get("prospect_location", "Unknown") or "Unknown"
            email = conv.get("prospect_email", "")

            if "@" in email:
                domain = email.split("@")[1]
                email_domains[domain] += 1

            industries[ind]["count"] += 1
            if conv.get("is_positive"):
                industries[ind]["positive"] += 1
            if conv.get("is_meeting_booked"):
                industries[ind]["meetings"] += 1
            if conv.get("is_proposal_sent"):
                industries[ind]["proposals"] += 1
            if conv.get("is_closed_won"):
                industries[ind]["won"] += 1
                industries[ind]["revenue"] += conv.get("deal_value", 0)

            roles[role]["count"] += 1
            if conv.get("is_positive"):
                roles[role]["positive"] += 1
            if conv.get("is_meeting_booked"):
                roles[role]["meetings"] += 1

            locations[loc]["count"] += 1
            if conv.get("is_positive"):
                locations[loc]["positive"] += 1
            if conv.get("is_meeting_booked"):
                locations[loc]["meetings"] += 1

        def enrich_segment(data):
            enriched = {}
            for k, v in data.items():
                pos_rate = round(v["positive"] / v["count"] * 100, 1) if v["count"] else 0
                meet_rate = round(v["meetings"] / v["count"] * 100, 1) if v["count"] else 0
                enriched[k] = {**v, "positive_rate": pos_rate, "meeting_rate": meet_rate}
            return dict(sorted(enriched.items(), key=lambda x: -x[1]["meeting_rate"]))

        # Rank industries by future value
        industry_ranking = self._rank_industries(industries)

        return {
            "industries": enrich_segment(industries),
            "roles": enrich_segment(roles),
            "locations": enrich_segment(locations),
            "top_email_domains": dict(sorted(email_domains.items(), key=lambda x: -x[1])[:20]),
            "industry_ranking": industry_ranking,
        }

    def _rank_industries(self, industries: Dict) -> List[Dict]:
        """Rank industries by expected future value"""
        rankings = []
        for ind, data in industries.items():
            if data["count"] < 2:
                continue
            pos_rate = data["positive"] / data["count"]
            meet_rate = data["meetings"] / data["count"]
            won_rate = data["won"] / data["count"] if data["count"] else 0
            avg_rev = data["revenue"] / data["won"] if data["won"] else 0

            # Composite score
            score = (
                pos_rate * 0.2 +
                meet_rate * 0.3 +
                won_rate * 0.3 +
                min(avg_rev / 10000, 1) * 0.2
            )

            rankings.append({
                "industry": ind,
                "score": round(score * 100, 1),
                "conversations": data["count"],
                "positive_rate": round(pos_rate * 100, 1),
                "meeting_rate": round(meet_rate * 100, 1),
                "close_rate": round(won_rate * 100, 1),
                "avg_revenue": round(avg_rev, 2),
            })

        return sorted(rankings, key=lambda x: -x["score"])

    # ========== BUYING INTENT ==========

    def detect_buying_signals(self) -> Dict:
        """Detect buying intent signals from conversations"""
        signals = {
            "funding": [],
            "hiring": [],
            "expansion": [],
            "influencer_budget": [],
            "product_launch": [],
            "team_growth": [],
            "agency_dissatisfaction": [],
            "competitive_pressure": [],
            "missed_opportunities": [],
        }

        for conv in self.conversations:
            body = conv.get("raw_data", "") or ""
            if isinstance(body, dict):
                body = json.dumps(body)
            subject = conv.get("subject", "")
            combined = f"{subject} {body}"

            # Funding signals
            if re.search(r"(?i)(raised|funding|series [a-d]|seed round|venture|investor|funded by)", combined):
                signals["funding"].append(conv["thread_id"])

            # Hiring signals
            if re.search(r"(?i)(hiring|we're hiring|growing team|recruiting|job opening|careers|positions)", combined):
                signals["hiring"].append(conv["thread_id"])

            # Expansion signals
            if re.search(r"(?i)(expanding|new market|entering|launching in|global expansion|international)", combined):
                signals["expansion"].append(conv["thread_id"])

            # Influencer budget
            if re.search(r"(?i)(influencer budget|influencer marketing|creator budget|spending on creators|influencer spend)", combined):
                signals["influencer_budget"].append(conv["thread_id"])

            # Product launch
            if re.search(r"(?i)(launching|new product|coming soon|releasing|announcing|latest release)", combined):
                signals["product_launch"].append(conv["thread_id"])

            # Team growth
            if re.search(r"(?i)(growing team|new hires|marketing team|expanding team|hiring for)", combined):
                signals["team_growth"].append(conv["thread_id"])

            # Agency dissatisfaction
            if re.search(r"(?i)(current agency|old agency|previous agency|dissatisfied|not happy with|switching agency|looking for new)", combined):
                signals["agency_dissatisfaction"].append(conv["thread_id"])

            # Competitive pressure
            if re.search(r"(?i)(competitor|competition|competitive|rival|market pressure|losing share|need to catch up)", combined):
                signals["competitive_pressure"].append(conv["thread_id"])

            # Missed opportunities - positive reply but no follow through
            if conv.get("is_positive") and not conv.get("is_meeting_booked") and conv.get("num_follow_ups", 0) < 3:
                signals["missed_opportunities"].append({
                    "thread_id": conv["thread_id"],
                    "prospect_name": conv.get("prospect_name"),
                    "prospect_company": conv.get("prospect_company"),
                    "reason": "Positive reply but insufficient follow-up",
                })

        return {k: {"count": len(v), "items": v[:20]} for k, v in signals.items()}

    # ========== CAMPAIGN ANALYSIS ==========

    def analyze_campaigns(self) -> Dict:
        """Reverse engineer high-performing campaigns"""
        positive = [c for c in self.conversations if c.get("is_positive")]
        not_positive = [c for c in self.conversations if not c.get("is_positive")]

        def extract_patterns(convs):
            subject_words = Counter()
            opening_words = Counter()
            cta_patterns = Counter()
            industries = Counter()

            for conv in convs:
                subject = conv.get("subject", "")
                body = conv.get("raw_data", "") or ""
                if isinstance(body, dict):
                    body = json.dumps(body)
                ind = conv.get("prospect_industry", "Unknown")

                # Subject patterns
                for word in re.findall(r'\b\w+\b', subject):
                    if len(word) > 3:
                        subject_words[word.lower()] += 1

                # CTA patterns
                for pat in [
                    r"(?i)(let's|schedule|book|hop on|jump on|talk soon)",
                    r"(?i)(interested|thoughts|feedback|opinion)",
                    r"(?i)(learn more|more details|tell me more)",
                    r"(?i)(free|consultation|discovery|strategy session)",
                    r"(?i)(case study|results|examples|portfolio)",
                    r"(?i)(growth|scale|revenue|increase)",
                ]:
                    if re.search(pat, body):
                        cta_patterns[pat] += 1

                industries[ind] += 1

            return {
                "top_subject_words": dict(subject_words.most_common(20)),
                "cta_patterns": dict(cta_patterns.most_common(10)),
                "industries": dict(industries.most_common(10)),
            }

        return {
            "positive_campaigns": extract_patterns(positive),
            "negative_campaigns": extract_patterns(not_positive),
            "winning_patterns": self._find_winning_patterns(positive, not_positive),
        }

    def _find_winning_patterns(self, positive: List[Dict], negative: List[Dict]) -> List[Dict]:
        """Identify what winning campaigns have in common"""
        patterns = []

        # Check CTA difference
        ctas = [
            ("Direct CTA (schedule/book)", r"(?i)(schedule|book|hop on|jump on|calendly)"),
            ("Soft CTA (interested/thoughts)", r"(?i)(interested|thoughts|feedback|opinion|think)"),
            ("Value CTA (learn more)", r"(?i)(learn more|more details|tell me|see how)"),
            ("Social Proof CTA", r"(?i)(case study|examples|portfolio|results|client)"),
            ("Free Offer CTA", r"(?i)(free|complimentary|no cost|strategy session)"),
        ]

        for name, pat in ctas:
            pos_with = sum(1 for c in positive if re.search(pat, c.get("subject", "") + " " + (c.get("raw_data", "") or "")))
            neg_with = sum(1 for c in negative if re.search(pat, c.get("subject", "") + " " + (c.get("raw_data", "") or "")))
            pos_total = len(positive) or 1
            neg_total = len(negative) or 1
            ratio = (pos_with / pos_total) / (neg_with / neg_total) if neg_with > 0 else 2.0

            patterns.append({
                "pattern": name,
                "positive_usage": round(pos_with / pos_total * 100, 1),
                "negative_usage": round(neg_with / neg_total * 100, 1),
                "impact_ratio": round(ratio, 2),
                "verdict": "WINNING" if ratio > 1.3 else "NEUTRAL" if ratio > 0.7 else "LOSING",
            })

        return sorted(patterns, key=lambda x: -x["impact_ratio"])

    # ========== MARKET POSITIONING ==========

    def analyze_market_positioning(self) -> Dict:
        """Evaluate agency positioning vs market demand"""
        focus_areas = {
            "awareness": r"(?i)(awareness|reach|impressions|visibility|exposure|brand awareness)",
            "creator_sourcing": r"(?i)(creator sourcing|find creators|talent sourcing|creator match|influencer discovery)",
            "campaign_management": r"(?i)(campaign management|manage|execution|content management|campaign ops)",
            "attribution": r"(?i)(attribution|roi|measurement|analytics|tracking|reporting|data)",
            "aeo": r"(?i)(aeo|answer engine|optimization|seo|search|visibility|google)",
            "influencer_infrastructure": r"(?i)(infrastructure|platform|technology|software|tool|automation|system)",
            "creator_retention": r"(?i)(retention|long.term|ongoing|retain|loyalty|repeat|program)",
            "measurement": r"(?i)(measurement|sophistication|analytics|dashboard|kpi|metrics|roi)",
            "long_term_programs": r"(?i)(long.term|ambassador|program|ongoing|retainer|annual|quarterly)",
        }

        outreach_focus = {k: {"count": 0, "prospects": []} for k in focus_areas}
        for conv in self.conversations:
            combined = f"{conv.get('subject', '')} {(conv.get('raw_data', '')) or ''}"
            if isinstance(combined, dict):
                combined = json.dumps(combined)
            matched = False
            for area, pat in focus_areas.items():
                if re.search(pat, combined):
                    outreach_focus[area]["count"] += 1
                    matched = True
            if not matched:
                outreach_focus.get("campaign_management", {}).setdefault("count", 0)
                outreach_focus["campaign_management"]["count"] += 1

        return {
            "outreach_focus": {k: v["count"] for k, v in outreach_focus.items()},
            "primary_focus": max(outreach_focus, key=lambda x: outreach_focus[x]["count"]),
        }

    # ========== FOLLOW-UP ANALYSIS ==========

    def analyze_follow_ups(self) -> Dict:
        """Deep follow-up performance analysis"""
        if not self.conversations:
            return {}

        sequences = defaultdict(list)
        for conv in self.conversations:
            msgs = conv.get("total_messages", 0)
            seq_len = min(msgs, 6)
            sequences[seq_len].append(conv)

        seq_performance = {}
        for length, convs in sorted(sequences.items()):
            pos = sum(1 for c in convs if c.get("is_positive"))
            meet = sum(1 for c in convs if c.get("is_meeting_booked"))
            won = sum(1 for c in convs if c.get("is_closed_won"))
            total = len(convs)
            seq_performance[f"{length}_touch"] = {
                "count": total,
                "positive_rate": round(pos / total * 100, 1) if total else 0,
                "meeting_rate": round(meet / total * 100, 1) if total else 0,
                "close_rate": round(won / total * 100, 1) if total else 0,
            }

        # Optimal follow-up spacing analysis
        # (based on reply patterns across conversations)
        optimal_spacing = self._analyze_spacing()

        # Best messaging strategy per touch
        messaging = self._analyze_messaging_by_touch()

        return {
            "sequence_performance": seq_performance,
            "optimal_spacing": optimal_spacing,
            "messaging_strategy": messaging,
            "optimal_sequence_length": self._find_optimal_length(sequences),
        }

    def _analyze_spacing(self) -> Dict:
        """Analyze optimal follow-up spacing"""
        convs_with_dates = [
            c for c in self.conversations
            if c.get("first_contact_date") and c.get("last_contact_date")
            and c.get("total_messages", 0) > 1
        ]

        spacings = []
        for conv in convs_with_dates[:20]:
            try:
                first = datetime.fromisoformat(conv["first_contact_date"])
                last = datetime.fromisoformat(conv["last_contact_date"])
                msgs = conv["total_messages"]
                if msgs > 1:
                    avg_gap = (last - first).total_seconds() / (msgs * 86400)
                    spacings.append(avg_gap)
            except (ValueError, TypeError):
                continue

        avg_spacing = statistics.mean(spacings) if spacings else 3
        return {
            "average_days_between_touches": round(avg_spacing, 1),
            "recommended_spacing_days": max(2, round(avg_spacing)),
            "note": "Follow up every 2-3 days for first 3 touches, then stretch to 5-7 days",
        }

    def _analyze_messaging_by_touch(self) -> Dict:
        """Best messaging strategy per touch number"""
        return {
            "touch_1": "Personalized introduction with specific reference to their work/company. Keep under 150 words. Clear value proposition.",
            "touch_2": "Add social proof - mention a similar company/client. Reference the first email briefly.",
            "touch_3": "Change angle - offer a specific insight or observation about their business. Add case study.",
            "touch_4": "Direct value - offer a free audit, strategy session, or specific recommendation.",
            "touch_5_plus": "Break the pattern - use video, voice note, or completely different approach. May be time to nurture differently.",
        }

    def _find_optimal_length(self, sequences: Dict) -> Dict:
        """Find the optimal number of follow-ups"""
        best = {"length": 3, "reasoning": "3-touch sequences show highest meeting-to-effort ratio"}
        if len(sequences) >= 3:
            perf_data = []
            for length, convs in sequences.items():
                length_int = int(length.split("_")[0]) if "_" in str(length) else 0
                meet_rate = sum(1 for c in convs if c.get("is_meeting_booked")) / len(convs) if convs else 0
                perf_data.append((length_int, meet_rate))

            if perf_data:
                perf_data.sort(key=lambda x: -x[1])
                best_len = perf_data[0][0]
                best = {
                    "length": best_len,
                    "meeting_rate": round(perf_data[0][1] * 100, 1),
                    "reasoning": f"{best_len}-touch sequences yield highest meeting conversion rate",
                }

        return best

    # ========== OUTREACH HEALTH ==========

    def calculate_health_score(self) -> Dict:
        """Calculate overall agency health scores (0-100)"""
        metrics = self.calculate_advanced_metrics()
        pipeline = self.get_funnel_conversion()

        # Outreach Health Score
        reply_rate = pipeline.get("positive_rate", 0)
        meeting_rate = pipeline.get("meeting_booking_rate", 0)
        outreach_health = min(100, round(
            (reply_rate * 2) + (meeting_rate * 2) + 20
        ))

        # Targeting Score
        segments = self.analyze_segments()
        top_industries = segments.get("industry_ranking", [])
        targeting_quality = 50
        if top_industries:
            avg_top_score = statistics.mean([r["score"] for r in top_industries[:5]]) if len(top_industries) >= 5 else 50
            targeting_quality = min(100, round(avg_top_score * 0.8 + 30))

        # Offer Strength Score
        close_rate = pipeline.get("close_rate", 0)
        proposal_to_close = pipeline.get("proposal_to_close", 0)
        offer_strength = min(100, round(
            (close_rate * 1.5) + (proposal_to_close * 0.5) + 20
        ))

        # Follow-Up Score
        avg_followups = metrics.get("avg_followups_won", 0)
        won_rate = pipeline.get("close_rate", 0)
        followup_score = min(100, round(
            (min(avg_followups / 3, 1) * 40) + (won_rate * 0.6) + 20
        ))

        # Market Positioning Score
        positioning = self.analyze_market_positioning()
        positioning_score = 50
        pos_focus = positioning.get("primary_focus", "")
        if pos_focus in ["attribution", "measurement", "long_term_programs"]:
            positioning_score = 75
        elif pos_focus in ["campaign_management", "creator_sourcing"]:
            positioning_score = 65

        # Revenue Efficiency Score
        cac = metrics.get("estimated_cac", 0)
        ltv = metrics.get("estimated_ltv", 0)
        ltv_cac = metrics.get("ltv_cac_ratio", 0)
        revenue_efficiency = min(100, round(
            min(ltv_cac * 10, 50) + (min(pipeline.get("total_revenue", 0) / 50000, 1) * 30) + 20
        ))

        # Growth Potential Score
        missed = self.detect_buying_signals()
        missed_count = missed.get("missed_opportunities", {}).get("count", 0)
        growth_potential = min(100, round(
            (pipeline.get("close_rate", 0) * 0.3) +
            (100 - outreach_health) * 0.3 +
            (missed_count > 0) * 15 +
            20
        ))

        overall = round((
            outreach_health * 0.15 +
            targeting_quality * 0.15 +
            offer_strength * 0.15 +
            followup_score * 0.1 +
            positioning_score * 0.1 +
            revenue_efficiency * 0.15 +
            growth_potential * 0.2
        ))

        return {
            "overall": overall,
            "outreach_health": outreach_health,
            "targeting_score": targeting_quality,
            "offer_strength": offer_strength,
            "follow_up_score": followup_score,
            "market_positioning": positioning_score,
            "revenue_efficiency": revenue_efficiency,
            "growth_potential": growth_potential,
            "scores_breakdown": {
                "outreach_health": {"score": outreach_health, "weight": "15%"},
                "targeting_score": {"score": targeting_quality, "weight": "15%"},
                "offer_strength": {"score": offer_strength, "weight": "15%"},
                "follow_up_score": {"score": followup_score, "weight": "10%"},
                "market_positioning": {"score": positioning_score, "weight": "10%"},
                "revenue_efficiency": {"score": revenue_efficiency, "weight": "15%"},
                "growth_potential": {"score": growth_potential, "weight": "20%"},
            },
        }
