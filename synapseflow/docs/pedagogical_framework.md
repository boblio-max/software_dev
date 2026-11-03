# Pedagogical Framework — SynapseFlow

## Grounding in Learning Science

- **Vygotsky's Zone of Proximal Development:** Scaffold difficulty is calibrated so the learner succeeds ~85% of the time (Bjork "Desirable Difficulty").
- **Cognitive Apprenticeship:** The AI models (fades) expert support the way an expert coach does.
- **Productive Failure:** Early attempts are allowed to fail; hints arrive only after productive struggle markers appear.

## Adaptive Hint Fading Algorithm

```
intensity(t) = clamp(0.5 + 0.3*(quality/100) - 0.2*(frustration>threshold)
               * 1/(1 + 0.05*hints_used) + U(-0.05, 0.05),
               0.1, 0.95)
```

- High attempt quality → higher intensity (less support)
- High frustration → lower intensity (more support)
- Each previous hint reduces intensity further (fade)
- 5% random injection breaks dependency patterns

## Mastery Update

Asymmetric learning rate:
- Success: `mastery += 0.15 * (5 + score/20)` (gain)
- Failure: `mastery -= 2` (if score < 30) or `mastery -= 0.5` (close but wrong)

Decay (Ebbinghaus): `mastery *= decay_rate^(days/7)`.

## Peer Review Rubric

Three dimensions scored 1-5 (normalized 0-100):
- **Coverage:** Addresses task key points
- **Actionability:** Learner can act on feedback
- **Tone:** Constructive, encouraging

## Ethical Considerations

- Never reveals full solution.
- Privacy: submissions only surfaced in peer review with consent.
- Bias: Age-adaptable prompt tone.
