import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.ai.scaffold_engine import ScaffoldEngine, CognitiveState


def test_cognitive_state():
    state = CognitiveState()
    assert state.frustration_level == 0
    assert state.attempt_quality == 0
    
def test_quality_calculation():
    engine = ScaffoldEngine.__new__(ScaffoldEngine)
    # Bypass __init__ (needs no real LLM for heuristic)
    engine.get_frustration_threshold = lambda: 70
    score = engine._calculate_quality("for i in range(5): print(i)", "print each number")
    assert score > 0
    print("Quality score:", score)

def test_intensity_calculation():
    engine = ScaffoldEngine.__new__(ScaffoldEngine)
    engine.get_frustration_threshold = lambda: 70
    val = engine._calculate_base_intensity(40, 60, 2)
    assert 0.0 <= val <= 1.0
    print("Intensity:", val)

def test_mastery_update():
    engine = ScaffoldEngine.__new__(ScaffoldEngine)
    m = engine.update_mastery(50.0, {"passed": True, "score": 100})
    assert m >= 50.0
    print("Post-success mastery:", m)
    m2 = engine.update_mastery(m, {"passed": False, "score": 20})
    print("Post-fail mastery:", m2)

if __name__ == "__main__":
    test_cognitive_state()
    test_quality_calculation()
    test_intensity_calculation()
    test_mastery_update()
    print("All tests passed")
