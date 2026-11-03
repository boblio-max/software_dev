"""
Peer pairing and review-quality scoring for SynapseFlow.
"""
from typing import List, Dict
from sqlalchemy.orm import Session
from ..models import Submission, PeerReview, UserSkillMastery, User

class PeerPairingEngine:
    def __init__(self, db: Session):
        self.db = db
    
    def _review_quality_history(self, user_id: int) -> float:
        reviews = self.db.query(PeerReview).filter(PeerReview.reviewer_id == user_id).all()
        if not reviews:
            return 0.5
        scores = [ (r.coverage_score or 0) + (r.actionability_score or 0) + (r.tone_score or 0) for r in reviews ]
        return sum(scores) / (len(scores) * 3 * 5) if reviews else 0.5
    
    def _mastery_distance(self, a: int, b: int) -> float:
        ma = self.db.query(UserSkillMastery).filter(UserSkillMastery.user_id == a).all()
        mb = self.db.query(UserSkillMastery).filter(UserSkillMastery.user_id == b).all()
        map_a = {m.skill_id: m.mastery_level for m in ma}
        map_b = {m.skill_id: m.mastery_level for m in mb}
        keys = set(map_a) | set(map_b)
        if not keys:
            return 0.5
        dist = sum(abs(map_a.get(k, 0) - map_b.get(k, 0)) for k in keys) / len(keys)
        return dist / 100.0
    
    def match_reviewers(self, submission_id: int, k: int = 3) -> List[Dict]:
        submission = self.db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            return []
        candidates = self.db.query(User).filter(User.id != submission.user_id).all()
        scored = []
        for c in candidates:
            # Avoid duplicate reviews
            existing = self.db.query(PeerReview).filter(
                PeerReview.submission_id == submission_id,
                PeerReview.reviewer_id == c.id
            ).first()
            if existing:
                continue
            quality = self._review_quality_history(c.id)
            proximity = 1 - self._mastery_distance(c.id, submission.user_id)
            score = 0.6 * proximity + 0.4 * quality
            scored.append({"user": c, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return [{"reviewer_id": s["user"].id, "username": s["user"].username, "match_score": round(s["score"], 3)} for s in scored[:k]]
    
    def score_feedback(self, feedback: str, covered_points: List[str]) -> Dict:
        lower = feedback.lower()
        coverage = sum(1 for p in covered_points if any(w in lower for w in p.lower().split())) / max(1, len(covered_points))
        actionability = 1.0 if any(w in lower for w in ["try", "change", "add", "remove", "consider"]) else 0.4
        # Tone heuristic
        negative = sum(1 for w in ["bad", "wrong", "stupid", "terrible"] if w in lower)
        tone = 1.0 if negative == 0 else max(0.2, 1 - 0.2 * negative)
        return {
            "coverage": round(coverage, 3),
            "actionability": round(actionability, 3),
            "tone": round(tone, 3),
            "total": round((coverage + actionability + tone) / 3, 3)
        }
