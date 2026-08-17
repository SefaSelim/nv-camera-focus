"""
AutofocusController — closed-loop autofocus by hill-climbing a focus score.

Pure, testable control logic: it never talks to the camera directly. Each call
takes the CURRENT focus score (e.g. the Tenengrad focus_measure of the frame
just captured), decides the next absolute focus position, commands it through
the passed CameraController, and returns an updated state dict. The state is a
plain dict so the executor can persist it in bootstrap across frames.

Model of operation (one-frame lag): the score passed in corresponds to the
focus position that was commanded on the PREVIOUS step. The search:
  - starts at the camera's current focus, probes one step in a direction,
  - keeps going while the score improves,
  - reverses and halves the step when the score drops,
  - converges when the step falls below min_step and parks the lens at the best
    position seen.
Zoom is held fixed (supplied by the caller); only focus is driven.
"""


class AutofocusController:
    @staticmethod
    def initial_state(step=0.02, min_step=0.002):
        return {
            "position": None,        # focus position whose score we are evaluating
            "direction": 1,          # +1 or -1
            "step": float(step),
            "min_step": float(min_step),
            "best_score": None,
            "best_position": None,
            "converged": False,
        }

    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def step(controller, focus_score, state, zoom):
        """
        Advance the search by one frame.

        controller  : CameraController (uses get_focus_status / set_focus_zoom)
        focus_score : focus measure of the frame at the current focus position
        state       : dict from initial_state() (persisted across frames)
        zoom        : absolute zoom to hold (0.0-1.0)

        Returns the updated state dict.
        """
        if state is None:
            state = AutofocusController.initial_state()

        # Already converged: hold the lens at the best position, do nothing.
        if state.get("converged"):
            return state

        # Ignore unusable scores (e.g. NaN) without moving the lens.
        if focus_score is None or focus_score != focus_score:
            return state

        # First call: learn the current focus position from the camera, record
        # its score as the baseline, and probe one step in the current direction.
        if state["position"] is None:
            status = controller.get_status()
            current = status.get("focus")
            current = 0.5 if current is None else AutofocusController._clamp01(current)
            state["position"] = current
            state["best_score"] = focus_score
            state["best_position"] = current
            next_position = AutofocusController._clamp01(current + state["direction"] * state["step"])
            controller.set_focus(next_position)
            state["position"] = next_position
            return state

        # The score belongs to state["position"] (the last commanded probe).
        if focus_score > state["best_score"]:
            # Improved: keep this position as the best, continue same direction.
            state["best_score"] = focus_score
            state["best_position"] = state["position"]
            next_position = AutofocusController._clamp01(
                state["position"] + state["direction"] * state["step"])
        else:
            # Worse: reverse direction and shrink the step, search around the best.
            state["direction"] = -state["direction"]
            state["step"] = state["step"] * 0.5
            if state["step"] < state["min_step"]:
                # Converged: park the lens at the best position seen.
                controller.set_focus(state["best_position"])
                state["position"] = state["best_position"]
                state["converged"] = True
                return state
            next_position = AutofocusController._clamp01(
                state["best_position"] + state["direction"] * state["step"])

        controller.set_focus_zoom(next_position, zoom)
        state["position"] = next_position
        return state
