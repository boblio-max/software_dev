from typing import Dict, Any, Optional
from openai import OpenAI
import ast
import json
from datetime import datetime
import re

class CognitiveState:
    def __init__(self):
        self.frustration_level = 0  # 0-100
        self.conceptual_gap = None
        self.attempt_quality = 0  # 0-100
        self.error_category = None
        self.struggle_indicators = {
            "repeated_error": False,
            "long_pause": False,
            "delete_pattern": False,
            "incremental_progress": False,
        }
    
    def to_dict(self):
        return {
            "frustration_level": self.frustration_level,
            "conceptual_gap": self.conceptual_gap,
            "attempt_quality": self.attempt_quality,
            "error_category": self.error_category,
            "struggle_indicators": self.struggle_indicators
        }

class ScaffoldEngine:
    """
    AI-Driven Adaptive Scaffolding Engine
    
    Core innovation: Generates Socratic hints that fade intensity based on
    learner struggle patterns, never revealing the solution directly.
    """
    
    def __init__(self, llm_provider="openai", model="gpt-4o-mini", api_key=None):
        self.provider = llm_provider
        self.model = model
        self.api_key = api_key
        self._client = None
        if llm_provider not in ("openai", "none"):
            raise ValueError(f"Unsupported provider: {llm_provider}")

    @property
    def client(self):
        if self._client is None and self.provider == "openai" and self.api_key:
            try:
                self._client = OpenAI(api_key=self.api_key)
            except Exception:
                self._client = None
        return self._client
    
    def analyze_attempt(self, code: str, task_intent: str, expected_solution: str, 
                        struggle_history: Dict) -> CognitiveState:
        """
        Deep analysis of learner's attempt beyond simple pass/fail.
        """
        state = CognitiveState()
        
        # 1. Parse learner code
        try:
            tree = ast.parse(code)
            state.error_category = None
        except SyntaxError as e:
            state.error_category = "syntax_error"
            state.conceptual_gap = f"Syntax issue at line {e.lineno}: {e.msg}"
            state.attempt_quality = 20
        except Exception as e:
            state.error_category = "parse_error"
            state.conceptual_gap = str(e)
            state.attempt_quality = 10
        
        # 2. Check struggle indicators from history
        state = self._assess_struggle(state, struggle_history)
        
        # 3. Calculate attempt quality via LLM comparison
        state.attempt_quality = self._calculate_quality(code, expected_solution)
        
        # 4. Post-process: if syntax error, don't put too much frustration
        # (syntax errors are normal, frustration comes from logic errors)
        if state.error_category == "syntax_error" and state.attempt_quality > 50:
            state.frustration_level = min(state.frustration_level, 40)
        
        # 5. Determine conceptual gap
        if state.attempt_quality < 30:
            state.conceptual_gap = self._identify_gap(code, task_intent, expected_solution)
        
        return state
    
    def _assess_struggle(self, state: CognitiveState, history: Dict) -> CognitiveState:
        """Detect struggle patterns from submission history"""
        attempts = history.get("attempts", [])
        
        # Repeated same error = high frustration
        errors = [a.get("error_category") for a in attempts]
        if len(errors) > 1 and errors[-1] == errors[-2]:
            state.struggle_indicators["repeated_error"] = True
            state.frustration_level += 20
        
        # Long pause (>2 min since last edit) = potentially stuck
        last_edit = history.get("last_edit_time")
        if last_edit:
            try:
                if isinstance(last_edit, str):
                    last_edit = datetime.fromisoformat(last_edit.replace("Z", "+00:00")).replace(tzinfo=None)
                pause_seconds = (datetime.utcnow() - last_edit).total_seconds()
                if pause_seconds > 120:
                    state.struggle_indicators["long_pause"] = True
                    state.frustration_level += 15
            except Exception:
                pass
        
        # Multiple hints already used = dependency risk
        hints_used = history.get("hints_used", 0)
        if hints_used > 3:
            state.frustration_level += 10
        
        # Track delete/redo patterns
        if history.get("delete_count", 0) > 5:
            state.struggle_indicators["delete_pattern"] = True
        
        # Capped frustration
        state.frustration_level = min(state.frustration_level, 100)
        
        return state
    
    def _calculate_quality(self, code: str, expected: str) -> int:
        """
        Calculate attempt quality 0-100 using semantic similarity 
        to expected solution intent.
        """
        # Simple heuristic: check presence of key constructs
        expected_keywords = set(re.findall(r'\b[a-zA-Z_]\w*\b', expected.lower()))
        user_keywords = set(re.findall(r'\b[a-zA-Z_]\w*\b', code.lower()))
        
        if not expected_keywords:
            return 50  # Unknown expected
        
        # Jaccard similarity
        intersection = len(expected_keywords & user_keywords)
        union = len(expected_keywords | user_keywords)
        similarity = (intersection / union) * 100 if union > 0 else 0
        
        # Adjust for structural match
        if 'for ' in code.lower() and 'for ' in expected.lower():
            similarity += 5
        if 'def ' in code.lower() and 'def ' in expected.lower():
            similarity += 5
        if 'return' in code.lower() and 'return' in expected.lower():
            similarity += 5
            
        return min(100, int(similarity))
    
    def _identify_gap(self, code: str, intent: str, expected: str) -> str:
        """Use LLM to identify the specific conceptual gap"""
        prompt = f"""
Analyze this learner's code attempt against the task intent.
Return ONLY a JSON object with:
{{
  "gap_type": "missing_concept" | "wrong_approach" | "incomplete_implementation",
  "specific_gap": "description of exactly what's missing/wrong",
  "next_concept_to_introduce": "the next cognitive step"
}}

TASK INTENT:
{intent}

EXPECTED APPROACH (conceptual, not exact code):
{expected}

LEARNER'S CODE:
{code}
"""
        if self.client is None:
            return "Conceptual gap could not be analyzed without an LLM; review fundamentals and retry."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert educational analyst specializing in detecting conceptual gaps in code. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            data = json.loads(response.choices[0].message.content)
            return data.get("specific_gap", "Unknown gap")
        except Exception as e:
            return f"Analysis error: {e}"
    
    def generate_hint(self, cognitive_state: Dict, context: Dict) -> Dict:
        """
        Generate a Socratic hint based on cognitive state and scaffold history.
        
        Returns:
            {
                "hint_type": "question" | "concept_nudge" | "step_prompt",
                "content": "The actual hint text",
                "target_step": "Which step to address",
                "intensity": 0.0-1.0,
                "suggested_action": "What learner should try next"
            }
        """
        frustration = cognitive_state.get("frustration_level", 0)
        quality = cognitive_state.get("attempt_quality", 50)
        gap = cognitive_state.get("conceptual_gap", "")
        hints_used = context.get("hints_used", 0)
        
        # Calculate base intensity
        base_intensity = self._calculate_base_intensity(frustration, quality, hints_used)
        
        # Intensity adjustment based on gap severity
        if quality < 20:
            base_intensity = max(0.2, base_intensity - 0.15)  # More support for low quality
        elif quality > 70:
            base_intensity = min(0.9, base_intensity + 0.2)   # Less support for high quality
        
        # Socratic hint prompt - NEVER reveal solution
        prompt = f"""
Generate a SOCRACTIC hint for this learner attempting a coding task.

CRITICAL RULES:
1. DO NOT provide the solution code or any code snippet
2. DO NOT give the specific fix - only guide thinking
3. Ask a question that points toward the missing concept
4. Maximum 2 sentences
5. Use encouraging, professional tone

LEARNER STATE:
- Frustration: {frustration}/100
- Attempt Quality: {quality}/100
- Conceptual Gap: {gap}
- Hints Already Used: {hints_used}

CONTEXT:
- Task Type: {context.get('task_type', 'coding')}
- Domain: {context.get('domain', 'unknown')}
- Previous Hints: {json.dumps(context.get('previous_hints', []))}

Return JSON:
{{
  "hint_type": "question" | "concept_nudge" | "step_prompt",
  "content": "The hint text (max 2 sentences, no code)",
  "target_step": "which cognitive step to address",
  "suggested_action": "what learner should try next"
}}
"""
        
        if self.client is None:
            return {
                "hint_type": "concept_nudge",
                "content": "Step back and identify the smallest part of the task you can complete next; build from there.",
                "target_step": "decomposition",
                "intensity": base_intensity,
                "suggested_action": "Attempt one small, testable piece of the task",
            }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a pedagogical Socratic tutor. NEVER reveal solutions. Guide discovery through questions."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.6
            )
            data = json.loads(response.choices[0].message.content)
            data["intensity"] = base_intensity
            return data
        except Exception as e:
            return {
                "hint_type": "concept_nudge",
                "content": "Think about what structure could handle the repetition pattern you need.",
                "target_step": "pattern identification",
                "intensity": base_intensity,
                "suggested_action": "Identify the loop structure needed",
                "error": str(e)
            }
    
    def _calculate_base_intensity(self, frustration: int, quality: int, hints_used: int) -> float:
        """
        Novel intensity calculation (original research contribution).
        
        Args:
            frustration: 0-100, higher = more stuck
            quality: 0-100, attempt quality
            hints_used: cumulative hints in session
        
        Returns:
            intensity: 0.0 (full support) to 1.0 (minimal support)
        """
        # Base: start moderate
        intensity = 0.5
        
        # Adjust for frustration (high frustration = more support)
        if frustration > self.get_frustration_threshold():
            intensity -= 0.2
        
        # Adjust for quality (higher quality = less support needed)
        intensity += (quality / 100) * 0.3
        
        # Hint history fade: each hint reduces intensity (fading)
        fade = 1 - (0.05 * hints_used)  # Gradual fade
        intensity *= fade
        
        # Random reduction injection (prevents dependency on fixed patterns)
        import random
        intensity += random.uniform(-0.05, 0.05)
        
        # Clamp
        return max(0.1, min(0.95, intensity))
    
    def get_frustration_threshold(self) -> int:
        return 70
    
    def update_mastery(self, current_mastery: float, attempt_result: Dict) -> float:
        """
        Update skill mastery using asymmetric learning rate.
        Successes grow mastery; failures have smaller penalty (constructive).
        Mastery decay is applied separately in UserSkillMastery.apply_decay()
        """
        passed = attempt_result.get("passed", False)
        score = attempt_result.get("score", 0)
        
        if passed:
            # Success: growth proportional to difficulty conquered
            delta = 5 + (score / 20)  # 5-10 points gain
            learning_rate = 0.15
            new_mastery = current_mastery + learning_rate * delta
        else:
            # Failure: small penalty (we want to encourage, not discourage)
            # But track for difficulty gating
            if score < 30:
                delta = -2  # Bad attempt
            else:
                delta = -0.5  # Good attempt, wrong direction
            new_mastery = current_mastery + delta
        
        return max(0.0, min(100.0, new_mastery))
