from collections import deque
from dataclasses import dataclass, field

from src.phase_detector import PhaseDetectionError, confidence_label, detect_phase

MEMORY_SIZE = 2

ADVICE = {
    "requirements": "Clarify scope with the client: who uses it, acceptance criteria, and priority.",
    "design": "Sketch the architecture or UI and review it with the team before building.",
    "implementation": "Break the work into tasks, assign an owner, and estimate effort.",
    "testing": "Define test cases and success criteria; plan for regression checks.",
    "deployment": "Prepare a release checklist, rollback plan, and monitoring.",
}


@dataclass
class Interaction:
    observations: dict
    reasoning: dict
    response: dict


@dataclass
class SimpleAgent:
    memory: deque = field(default_factory=lambda: deque(maxlen=MEMORY_SIZE))

    def observe(self, user_input: dict) -> dict:
        description = user_input["description"]
        previous = self.memory[-1] if self.memory else None
        return {
            "description": description,
            "client": user_input.get("client", ""),
            "project": user_input.get("project", ""),
            "word_count": len(description.split()),
            "previous": {
                "description": previous.observations["description"],
                "project": previous.observations["project"],
                "phase": previous.reasoning.get("phase"),
            }
            if previous
            else None,
        }

    def reason(self, observations: dict) -> dict:
        steps = [f"Request has {observations['word_count']} words."]
        prev = observations["previous"]
        if prev:
            steps.append(f"Previous request was about '{prev['description']}' ({prev['phase'] or 'unclassified'}).")
            if prev["project"] == observations["project"]:
                steps.append("Same project as the previous request, so this is likely related work.")
        try:
            phase, confidence = detect_phase(observations["description"])
        except PhaseDetectionError as e:
            steps.append(f"Phase detector failed: {e}")
            return {"phase": None, "confidence": 0.0, "steps": steps}
        steps.append(f"Phase detector chose '{phase}' with {confidence_label(confidence)} confidence ({confidence:.0%}).")
        if prev and prev["phase"] and prev["phase"] != phase:
            steps.append(f"Phase differs from the previous request ('{prev['phase']}'), so this work may be at a different stage.")
        return {"phase": phase, "confidence": confidence, "steps": steps}

    def act(self, reasoning: dict) -> dict:
        phase = reasoning["phase"]
        if phase is None:
            return {"advice": "Could not classify this request. Review it manually or retry later."}
        advice = ADVICE[phase]
        if reasoning["confidence"] < 0.5:
            advice += " (Low confidence: please verify the phase manually.)"
        return {"advice": advice}

    def process(self, user_input: dict) -> Interaction:
        observations = self.observe(user_input)
        reasoning = self.reason(observations)
        response = self.act(reasoning)
        interaction = Interaction(observations, reasoning, response)
        self.memory.append(interaction)
        return interaction

    def follow_up(self, question: str) -> str:
        if not self.memory:
            return "I have no previous request in memory yet."
        last = self.memory[-1]
        lines = [f"About your last request: '{last.observations['description']}'"]
        if "why" in question.lower():
            lines += [f"- {s}" for s in last.reasoning["steps"]]
        else:
            lines.append(f"Phase: {last.reasoning['phase'] or 'unclassified'}")
            lines.append(f"Advice: {last.response['advice']}")
        if len(self.memory) > 1:
            lines.append(f"Before that: '{self.memory[0].observations['description']}'")
        return "\n".join(lines)
