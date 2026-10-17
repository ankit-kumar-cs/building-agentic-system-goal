"""SDLC phase-aware agent: Observe -> Reason -> Act -> Adapt.

- Observe: collect facts about the request plus context from short-term memory.
- Reason:  ask the LLM which SDLC phase the request belongs to (with confidence).
- Act:     give phase-specific advice and generate the matching artifact document.
- Adapt:   when the user corrects a phase, store it as a new example for future prompts.
"""
import time
from dataclasses import dataclass

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage

from src import monitoring
from src.artifact_generator import generate_artifact, remove_artifact
from src.learning import add_correction
from src.phase_detector import PHASES, PhaseDetectionError, build_phase_chain, confidence_label, detect_phase_detailed

MEMORY_INTERACTIONS = 2
CONFIRM_BELOW = 0.7  # the CLI asks the user to confirm phases below this confidence

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

    @property
    def needs_confirmation(self) -> bool:
        return self.reasoning["phase"] is not None and self.reasoning["confidence"] < CONFIRM_BELOW


class SimpleAgent:
    def __init__(self) -> None:
        self.history = InMemoryChatMessageHistory()
        self._chain = None

    def _last_exchange(self) -> tuple[HumanMessage, AIMessage] | None:
        msgs = self.history.messages
        return (msgs[-2], msgs[-1]) if len(msgs) >= 2 else None

    def observe(self, user_input: dict) -> dict:
        description = user_input["description"]
        last = self._last_exchange()
        previous = (
            {
                "description": last[0].content,
                "project": last[0].additional_kwargs.get("project", ""),
                "phase": last[1].additional_kwargs.get("phase"),
            }
            if last
            else None
        )
        return {
            "id": user_input.get("id"),
            "description": description,
            "client": user_input.get("client", ""),
            "project": user_input.get("project", ""),
            "word_count": len(description.split()),
            "previous": previous,
        }

    def reason(self, observations: dict) -> dict:
        steps = [f"Request has {observations['word_count']} words."]
        prev = observations["previous"]
        if prev:
            steps.append(f"Previous request was about '{prev['description']}' ({prev['phase'] or 'unclassified'}).")
            if prev["project"] == observations["project"]:
                steps.append("Same project as the previous request, so this is likely related work.")
        started = time.perf_counter()
        try:
            self._chain = self._chain or build_phase_chain()
            result = detect_phase_detailed(observations["description"], self._chain)
        except PhaseDetectionError as e:
            steps.append(f"Phase detector failed: {e}")
            return {"phase": None, "confidence": 0.0, "steps": steps, "error": str(e),
                    "llm_ms": round((time.perf_counter() - started) * 1000)}
        phase, confidence = result["phase"], result["confidence"]
        steps.append(f"Phase detector chose '{phase}' with {confidence_label(confidence)} confidence ({confidence:.0%}).")
        if prev and prev["phase"] and prev["phase"] != phase:
            steps.append(f"Phase differs from the previous request ('{prev['phase']}'), so this work may be at a different stage.")
        return {"phase": phase, "confidence": confidence, "steps": steps, "structured": result["structured"],
                "llm_ms": round((time.perf_counter() - started) * 1000)}

    def act(self, reasoning: dict, observations: dict | None = None) -> dict:
        phase = reasoning["phase"]
        if phase is None:
            return {"advice": "Could not classify this request. Review it manually or retry later."}
        advice = ADVICE[phase]
        if reasoning["confidence"] < CONFIRM_BELOW:
            advice += " (Low confidence: please verify the phase.)"
        response = {"advice": advice}
        if observations and observations["id"] is not None:
            try:
                response["artifact_path"] = str(generate_artifact(phase, observations))
            except (OSError, ValueError) as e:
                response["artifact_error"] = str(e)
        return response

    def adapt(self, interaction: Interaction, corrected_phase: str) -> Interaction:
        """Apply a user correction: learn from it, then redo the Act step for the right phase."""
        if corrected_phase not in PHASES:
            raise ValueError(f"Unknown phase '{corrected_phase}'. Choose from: {', '.join(PHASES)}.")
        obs, reasoning = interaction.observations, interaction.reasoning
        predicted = reasoning["phase"]
        add_correction(obs["description"], predicted, corrected_phase)
        monitoring.log_correction(obs.get("id"), predicted, corrected_phase)

        reasoning = {
            **reasoning,
            "phase": corrected_phase,
            "confidence": 1.0,
            "steps": reasoning["steps"] + [f"User corrected phase '{predicted}' -> '{corrected_phase}'; saved as a learning example."],
        }
        old_artifact = interaction.response.get("artifact_path")
        updated = Interaction(obs, reasoning, self.act(reasoning, obs))
        if old_artifact and old_artifact != updated.response.get("artifact_path"):
            remove_artifact(old_artifact)
        self.history.messages = self.history.messages[:-2]
        self._remember(updated)
        return updated

    def _remember(self, interaction: Interaction) -> None:
        obs, reasoning = interaction.observations, interaction.reasoning
        self.history.add_message(
            HumanMessage(content=obs["description"], additional_kwargs={"project": obs["project"]})
        )
        self.history.add_message(
            AIMessage(
                content=interaction.response["advice"],
                additional_kwargs={"phase": reasoning["phase"], "steps": reasoning["steps"]},
            )
        )
        self.history.messages = self.history.messages[-2 * MEMORY_INTERACTIONS :]

    def process(self, user_input: dict) -> Interaction:
        started = time.perf_counter()
        observations = self.observe(user_input)
        reasoning = self.reason(observations)
        interaction = Interaction(observations, reasoning, self.act(reasoning, observations))
        self._remember(interaction)
        try:
            monitoring.log_interaction(interaction, (time.perf_counter() - started) * 1000)
        except OSError as e:
            print(f"Warning: could not write interaction log ({e}).")
        return interaction

    def follow_up(self, question: str) -> str:
        last = self._last_exchange()
        if not last:
            return "I have no previous request in memory yet."
        human, ai = last
        lines = [f"About your last request: '{human.content}'"]
        if "why" in question.lower():
            lines += [f"- {s}" for s in ai.additional_kwargs["steps"]]
        else:
            lines.append(f"Phase: {ai.additional_kwargs['phase'] or 'unclassified'}")
            lines.append(f"Advice: {ai.content}")
        if len(self.history.messages) >= 4:
            lines.append(f"Before that: '{self.history.messages[0].content}'")
        return "\n".join(lines)
