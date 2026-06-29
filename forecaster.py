from typing import Dict, List
import statistics
from collections import defaultdict

from database import get_all_conversations, get_all_emails


class RevenueForecaster:
    """AI-powered revenue forecasting engine"""

    def __init__(self):
        self.conversations = get_all_conversations()
        self.emails = get_all_emails()

    def forecast(self) -> Dict:
        won = [c for c in self.conversations if c.get("is_closed_won") and c.get("deal_value")]
        avg_deal = statistics.mean([c["deal_value"] for c in won]) if won else 5000
        total_outreach = len(self.conversations)
        reply_rate = len([c for c in self.conversations if c.get("is_positive")]) / total_outreach if total_outreach else 0.05
        meeting_rate = len([c for c in self.conversations if c.get("is_meeting_booked")]) / total_outreach if total_outreach else 0.02
        close_rate = len(won) / total_outreach if total_outreach else 0.01

        pipeline = {
            "current_mrr": self._calculate_current_mrr(),
            "avg_deal_value": avg_deal,
            "reply_rate": reply_rate,
            "meeting_rate": meeting_rate,
            "close_rate": close_rate,
        }

        scenarios = {
            "conservative": self._build_scenario(pipeline, 1.0),
            "realistic": self._build_scenario(pipeline, 1.5),
            "aggressive": self._build_scenario(pipeline, 3.0),
        }

        bottlenecks = self._identify_bottlenecks(pipeline)
        revenue_impact = self._calculate_bottleneck_impact(pipeline, bottlenecks)

        return {
            "pipeline_assumptions": pipeline,
            "scenarios": scenarios,
            "bottlenecks": bottlenecks,
            "bottleneck_revenue_impact": revenue_impact,
            "projections": self._project_monthly(targets=[10000, 25000, 50000, 100000]),
        }

    def _calculate_current_mrr(self) -> float:
        won = [c for c in self.conversations if c.get("is_closed_won") and c.get("deal_value")]
        total_rev = sum(c["deal_value"] for c in won)
        # Assume deals span 3 months on average
        return round(total_rev / max(len(won) * 3, 3), 2)

    def _build_scenario(self, pipeline: Dict, multiplier: float) -> Dict:
        avg_deal = pipeline["avg_deal_value"]
        reply = pipeline["reply_rate"]
        meet = pipeline["meeting_rate"]
        close = pipeline["close_rate"]

        # Scale outreach volume
        monthly_outreach = 200 * multiplier
        monthly_replies = monthly_outreach * reply
        monthly_meetings = monthly_outreach * meet
        monthly_clients = monthly_outreach * close
        monthly_revenue = monthly_clients * avg_deal

        # 3-month projection
        mrr = monthly_revenue
        three_month = mrr * 3
        annualized = mrr * 12

        return {
            "monthly_outreach": round(monthly_outreach),
            "monthly_replies": round(monthly_replies),
            "monthly_meetings": round(monthly_meetings),
            "monthly_clients": round(monthly_clients),
            "monthly_revenue": round(monthly_revenue, 2),
            "mrr": round(mrr, 2),
            "three_month_revenue": round(three_month, 2),
            "annualized_revenue": round(annualized, 2),
            "scenario_multiplier": multiplier,
        }

    def _identify_bottlenecks(self, pipeline: Dict) -> List[Dict]:
        bottlenecks = []

        reply_rate = pipeline["reply_rate"]
        if reply_rate < 0.10:
            bottlenecks.append({
                "area": "Reply Rate",
                "current": f"{reply_rate:.1%}",
                "target": "10%+",
                "severity": "critical" if reply_rate < 0.05 else "high",
                "impact": "Few prospects engage with initial outreach",
                "fix": "Improve personalization depth, refine ICP targeting, optimize subject lines",
            })

        meeting_rate = pipeline["meeting_rate"]
        if meeting_rate < 0.05:
            bottlenecks.append({
                "area": "Meeting Booking Rate",
                "current": f"{meeting_rate:.1%}",
                "target": "5%+",
                "severity": "critical" if meeting_rate < 0.02 else "high",
                "impact": "Prospects engage but don't convert to meetings",
                "fix": "Add clearer CTA, reduce friction, offer specific value in meeting",
            })

        close_rate = pipeline["close_rate"]
        if close_rate < 0.02:
            bottlenecks.append({
                "area": "Close Rate",
                "current": f"{close_rate:.1%}",
                "target": "2%+",
                "severity": "high" if close_rate < 0.01 else "medium",
                "impact": "Meetings don't convert to paying clients",
                "fix": "Improve proposal quality, address objections earlier, add case studies",
            })

        avg_deal = pipeline["avg_deal_value"]
        if avg_deal < 5000:
            bottlenecks.append({
                "area": "Deal Size",
                "current": f"${avg_deal:.0f}",
                "target": "$5,000+",
                "severity": "medium",
                "impact": "Revenue per client is below target",
                "fix": "Bundle services, upsell, target larger companies, raise rates",
            })

        return bottlenecks

    def _calculate_bottleneck_impact(self, pipeline: Dict, bottlenecks: List[Dict]) -> List[Dict]:
        impacts = []
        avg_deal = pipeline["avg_deal_value"]

        for bt in bottlenecks:
            if "Reply Rate" in bt["area"]:
                current = pipeline["reply_rate"]
                target = 0.10
                improvement = (target - current) * 200 * avg_deal * pipeline["close_rate"]
                impacts.append({
                    "bottleneck": bt["area"],
                    "annual_revenue_impact": round(improvement * 12, 2),
                    "effort": "medium",
                })

            elif "Meeting" in bt["area"]:
                current = pipeline["meeting_rate"]
                target = 0.08
                improvement = (target - current) * 200 * avg_deal * pipeline["close_rate"]
                impacts.append({
                    "bottleneck": bt["area"],
                    "annual_revenue_impact": round(improvement * 12, 2),
                    "effort": "low",
                })

            elif "Close" in bt["area"]:
                current = pipeline["close_rate"]
                target = 0.05
                improvement = (target - current) * 200 * avg_deal * pipeline["meeting_rate"]
                impacts.append({
                    "bottleneck": bt["area"],
                    "annual_revenue_impact": round(improvement * 12, 2),
                    "effort": "medium",
                })

            elif "Deal Size" in bt["area"]:
                current = avg_deal
                target = 8000
                improvement = (target - current) * 200 * pipeline["close_rate"]
                impacts.append({
                    "bottleneck": bt["area"],
                    "annual_revenue_impact": round(improvement * 12, 2),
                    "effort": "low",
                })

        return sorted(impacts, key=lambda x: -x["annual_revenue_impact"])

    def _project_monthly(self, targets: List[int]) -> List[Dict]:
        """Project what it takes to hit different revenue targets"""
        won = [c for c in self.conversations if c.get("is_closed_won") and c.get("deal_value")]
        avg_deal = statistics.mean([c["deal_value"] for c in won]) if won else 5000
        total = len(self.conversations)
        reply_rate = len([c for c in self.conversations if c.get("is_positive")]) / total if total else 0.05
        meet_rate = len([c for c in self.conversations if c.get("is_meeting_booked")]) / total if total else 0.02
        close_rate = len(won) / total if total else 0.01

        projections = []
        for target in targets:
            clients_needed = target / avg_deal
            meetings_needed = clients_needed / close_rate if close_rate else 999
            replies_needed = meetings_needed / meet_rate if meet_rate else 999
            outreach_needed = replies_needed / reply_rate if reply_rate else 999

            projections.append({
                "target_mrr": target,
                "clients_needed": round(clients_needed),
                "meetings_needed": round(meetings_needed),
                "replies_needed": round(replies_needed),
                "outreach_needed": round(outreach_needed),
                "months_to_achieve": "Varies",
            })

        return projections


class StrategicReport:
    """Generates executive strategic report"""

    def __init__(self):
        self.conversations = get_all_conversations()
        self.emails = get_all_emails()

    def generate(self) -> Dict:
        from analytics import AgencyAnalytics
        analytics = AgencyAnalytics()
        forecaster = RevenueForecaster()

        metrics = analytics.calculate_advanced_metrics()
        pipeline = analytics.get_funnel_conversion()
        segments = analytics.analyze_segments()
        health = analytics.calculate_health_score()
        signals = analytics.detect_buying_signals()
        followups = analytics.analyze_follow_ups()
        campaigns = analytics.analyze_campaigns()
        positioning = analytics.analyze_market_positioning()
        forecast = forecaster.forecast()

        return {
            "executive_summary": self._executive_summary(health, metrics, pipeline),
            "competitive_advantage": self._competitive_advantage(segments, campaigns),
            "niche_priorities": self._niche_priorities(segments),
            "outreach_angles": self._best_outreach_angles(campaigns),
            "regional_opportunities": self._regional_opportunities(segments),
            "decision_maker_insights": self._decision_maker_insights(segments),
            "highest_impact_changes": self._highest_impact_changes(forecast, signals, followups),
            "recommendations": self._recommendations(health, signals, followups),
            "quick_wins": self._quick_wins(signals, followups),
        }

    def _executive_summary(self, health: Dict, metrics: Dict, pipeline: Dict) -> str:
        overall = health["overall"]
        reply = pipeline.get("positive_rate", 0)
        close = pipeline.get("close_rate", 0)
        cac = metrics.get("estimated_cac", 0)
        ltv = metrics.get("estimated_ltv", 0)
        return (
            f"The agency scores {overall}/100 overall on the Intelligence Health Index. "
            f"Current outreach generates a {reply}% positive reply rate with a {close}% close rate. "
            f"Estimated CAC is ${cac} with an LTV of ${ltv} (ratio {metrics.get('ltv_cac_ratio', 0):.1f}x). "
            f"{'The LTV:CAC ratio indicates a healthy business model.' if metrics.get('ltv_cac_ratio', 0) > 3 else 'The LTV:CAC ratio suggests room for significant optimization.'} "
            f"Key bottleneck: {pipeline.get('positive_to_meeting', 0)}% of positive replies convert to meetings, "
            f"indicating {'strong' if pipeline.get('positive_to_meeting', 0) > 50 else 'weak'} call-to-action effectiveness."
        )

    def _competitive_advantage(self, segments: Dict, campaigns: Dict) -> str:
        top_industry = ""
        if segments.get("industry_ranking"):
            top_industry = segments["industry_ranking"][0]["industry"]

        winning = campaigns.get("winning_patterns", [])
        top_pattern = winning[0] if winning else {"pattern": "Need more data"}

        return (
            f"True competitive advantage lies in {top_industry or 'specialized niche'} vertical expertise, "
            f"with {top_pattern['pattern']} being the most effective outreach pattern "
            f"({top_pattern.get('impact_ratio', 'N/A')}x impact ratio vs standard approaches)."
        )

    def _niche_priorities(self, segments: Dict) -> List[Dict]:
        rankings = segments.get("industry_ranking", [])
        return [
            {
                "rank": i + 1,
                "niche": r["industry"],
                "score": r["score"],
                "meeting_rate": r["meeting_rate"],
                "close_rate": r["close_rate"],
                "priority": "high" if i < 3 else "medium" if i < 6 else "low",
            }
            for i, r in enumerate(rankings[:10])
        ]

    def _best_outreach_angles(self, campaigns: Dict) -> List[str]:
        patterns = campaigns.get("winning_patterns", [])
        return [
            p["pattern"] for p in patterns if p["verdict"] == "WINNING"
        ] or ["Personalized value-driven outreach with social proof"]

    def _regional_opportunities(self, segments: Dict) -> List[Dict]:
        locations = segments.get("locations", {})
        enriched = []
        for loc, data in sorted(locations.items(), key=lambda x: -x[1]["meeting_rate"]):
            if loc == "Unknown" or data["count"] < 2:
                continue
            enriched.append({
                "region": loc,
                "conversations": data["count"],
                "meeting_rate": data["meeting_rate"],
                "recommendation": "PRIORITY" if data["meeting_rate"] > 20 else "EXPLORE" if data["meeting_rate"] > 10 else "MONITOR",
            })
        return enriched[:10]

    def _decision_maker_insights(self, segments: Dict) -> List[Dict]:
        roles = segments.get("roles", {})
        enriched = []
        for role, data in sorted(roles.items(), key=lambda x: -x[1]["meeting_rate"]):
            if role == "Unknown" or data["count"] < 2:
                continue
            enriched.append({
                "role": role,
                "conversations": data["count"],
                "meeting_rate": data["meeting_rate"],
                "response_rate": data["positive_rate"],
            })
        return enriched[:10]

    def _highest_impact_changes(self, forecast: Dict, signals: Dict, followups: Dict) -> List[Dict]:
        impacts = forecast.get("bottleneck_revenue_impact", [])
        return [
            {
                "change": f"Fix {i['bottleneck']}",
                "annual_revenue_impact": i["annual_revenue_impact"],
                "effort": i["effort"],
                "roi_quality": "HIGH" if i["effort"] == "low" and i["annual_revenue_impact"] > 50000 else "MEDIUM",
            }
            for i in impacts[:5]
        ]

    def _recommendations(self, health: Dict, signals: Dict, followups: Dict) -> List[str]:
        recs = []
        if health["outreach_health"] < 50:
            recs.append("Overhaul outreach templates: reduce generic language, increase personalization depth")
        if health["follow_up_score"] < 50:
            recs.append("Implement structured 5-touch follow-up sequence with value-add at each touch")
        missed = signals.get("missed_opportunities", {}).get("count", 0)
        if missed > 0:
            recs.append(f"Re-engage {missed} prospects who showed interest but were not followed up aggressively")
        if health["targeting_score"] < 50:
            recs.append("Refine ICP: focus on top 3 performing industry segments with highest meeting rates")
        recs.append("Implement CRM tracking for all prospect interactions to enable data-driven decisions")
        return recs

    def _quick_wins(self, signals: Dict, followups: Dict) -> List[str]:
        wins = []
        missed = signals.get("missed_opportunities", {}).get("count", 0)
        if missed:
            wins.append(f"Re-engage {missed} warm leads within 48 hours - highest ROI action available")

        seq_perf = followups.get("sequence_performance", {})
        if seq_perf:
            best_seq = max(seq_perf.items(), key=lambda x: x[1]["meeting_rate"])
            wins.append(f"Standardize to {best_seq[0].replace('_', ' ')} follow-up sequence (highest conversion)")

        wins.append("Add personalized video outreach for top 10 prospects this week")

        return wins
