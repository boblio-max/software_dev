from typing import List, Dict, Any
from sqlalchemy.orm import Session
from ..models import Skill, SkillPrerequisite, UserSkillMastery


class KnowledgeGraph:
    """
    Manages the directed acyclic graph of skills and user mastery traversal.
    """

    def __init__(self, db: Session):
        self.db = db

    # Backwards/typo-compatible aliases
    def get_unstole_skills(self, user_id: int) -> List[Dict[str, Any]]:
        return self.get_unlocked_skills(user_id)

    def get_unlocked_skills(self, user_id: int) -> List[Dict[str, Any]]:
        """Returns skills user can attempt given their current mastery."""
        all_skills = self.db.query(Skill).all()
        mastery_map = self._mastery_map(user_id)

        prereq_map = {}
        for sp in self.db.query(SkillPrerequisite).all():
            prereq_map.setdefault(sp.skill_id, []).append(sp)

        unlocked = []
        for skill in all_skills:
            can_attempt = True
            for prereq in prereq_map.get(skill.id, []):
                prereq_mastery = mastery_map.get(prereq.prerequisite_id, 0.0)
                prereq_skill = self.db.query(Skill).filter(Skill.id == prereq.prerequisite_id).first()
                threshold = prereq_skill.mastery_threshold if prereq_skill else 80
                if prereq_mastery < threshold:
                    can_attempt = False
                    break

            if can_attempt:
                unlocked.append({
                    "skill_id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "domain": skill.domain,
                    "difficulty_base": skill.difficulty_base,
                    "current_mastery": mastery_map.get(skill.id, 0.0)
                })

        return unlocked

    def get_skill_graph_for_user(self, user_id: int) -> Dict[str, Any]:
        """Full graph structure with mastery levels for visualization."""
        all_skills = self.db.query(Skill).all()
        mastery_map = self._mastery_map(user_id)

        flat_edges = []
        for skill in all_skills:
            for prereq in self.db.query(SkillPrerequisite).filter(SkillPrerequisite.skill_id == skill.id).all():
                flat_edges.append({
                    "from": prereq.prerequisite_id,
                    "to": skill.id,
                    "weight": prereq.weight,
                })

        return {
            "nodes": [
                {
                    "id": s.id,
                    "name": s.name,
                    "domain": s.domain,
                    "difficulty_base": s.difficulty_base,
                    "mastery": mastery_map.get(s.id, 0.0)
                } for s in all_skills
            ],
            "edges": flat_edges
        }

    def check_mastery_gate(self, user_id: int, skill_id: int) -> bool:
        """Check if user has sufficient mastery to attempt a skill."""
        prereqs = self.db.query(SkillPrerequisite).filter(
            SkillPrerequisite.skill_id == skill_id
        ).all()

        mastery_map = self._mastery_map(user_id)

        for prereq in prereqs:
            prereq_skill = self.db.query(Skill).filter(Skill.id == prereq.prerequisite_id).first()
            threshold = prereq_skill.mastery_threshold if prereq_skill else 80
            if mastery_map.get(prereq.prerequisite_id, 0) < threshold:
                return False
        return True

    def get_recommended_next_skill(self, user_id: int) -> Dict[str, Any]:
        """Find the best next skill for the learner based on ZPD."""
        unlocked = self.get_unlocked_skills(user_id)

        if not unlocked:
            return {"recommendation": "No skills available; needs foundational content"}

        suitable = [s for s in unlocked if s["current_mastery"] < 80]

        if not suitable:
            return sorted(unlocked, key=lambda x: x["current_mastery"])[0]

        # Prefer the skill closest to mastery among unlocked (ZPD sweet spot).
        return max(suitable, key=lambda x: x["current_mastery"])

    def _mastery_map(self, user_id: int) -> Dict[int, float]:
        user_mastery = self.db.query(UserSkillMastery).filter(
            UserSkillMastery.user_id == user_id
        ).all()
        return {m.skill_id: m.mastery_level for m in user_mastery}