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
  - keeps going while the score improves, and keeps the same step while a probe
    stays within the noise band, so the search can travel far from its start,
  - reverses and halves the step only once a probe is clearly worse (below the
    best by more than the noise margin, or repeatedly unconvincing),
  - converges when the step falls below min_step and parks the lens at the best
    position seen,
  - and keeps watching afterwards: the search restarts when the lens drifts away
    from the converged position (someone focused from the camera's own UI) or
    when the focus score stays well below the best seen (scene change).
Zoom is held fixed (supplied by the caller); only focus is driven.
"""


class AutofocusController:
    @staticmethod
    def initial_state(step=0.02, min_step=0.002, refocus_ratio=0.88, refocus_patience=4,
                      drift_tolerance=0.05, noise_margin=0.04, miss_patience=2):
        return {
            "position": None,        # focus position whose score we are evaluating
            "direction": 1,          # +1 or -1
            "step": float(step),
            "initial_step": float(step),
            "min_step": float(min_step),
            "best_score": None,
            "best_position": None,
            "converged": False,
            # continuous refocus: once converged, restart the search if the score
            # stays below refocus_ratio * best for refocus_patience frames. 0.88 is
            # deliberately tight so the loop reacts before the image visibly softens.
            "refocus_ratio": float(refocus_ratio),
            "refocus_patience": int(refocus_patience),
            "low_count": 0,
            "score_ema": None,       # smoothed score, so frame noise alone
                                     # cannot trigger a needless refocus
            # how far the lens may drift from the converged position before the
            # search restarts (catches focus changed outside the package)
            "drift_tolerance": float(drift_tolerance),
            "settled_position": None,   # where the lens actually came to rest
            # the score swings with scene content, so a probe only counts as
            # "worse" when it is below the best by more than noise_margin, and
            # only after miss_patience such probes does the search turn around
            "noise_margin": float(noise_margin),
            "miss_patience": int(miss_patience),
            "miss_count": 0,

        }

    @staticmethod
    def _rearm(state):
        """Reset the search so hill-climbing starts again from the lens's
        current position."""
        state.update({
            "position": None,
            "direction": 1,
            "step": state.get("initial_step", state["step"]),
            "best_score": None,
            "best_position": None,
            "converged": False,
            "low_count": 0,
            "score_ema": None,
            "settled_position": None,
            "miss_count": 0,
        })

    @staticmethod
    def _clamp01(value):
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def step(controller, focus_score, state, zoom):
        """
        Advance the search by one frame.

        controller  : CameraController (uses get_status / set_focus)
        focus_score : focus measure of the frame at the current focus position
        state       : dict from initial_state() (persisted across frames)
        zoom        : absolute zoom to hold (0.0-1.0)

        Returns the updated state dict.
        """
        if state is None:
            state = AutofocusController.initial_state()

        # Converged: hold position, but keep watching the score so the loop can
        # refocus by itself when the scene changes or someone defocuses the lens.
        if state.get("converged"):
            # Primary trigger: did the lens move behind our back? Someone
            # focusing from the camera's own UI changes the position without
            # necessarily lowering the focus score (the measure swings with
            # scene content, so a score comparison alone misses this), so the
            # position is the reliable signal.
            reference = state.get("settled_position", state.get("best_position"))
            if reference is not None:
                status = controller.get_status() or {}
                current = status.get("focus")
                if current is not None and                         abs(current - reference) > state.get("drift_tolerance", 0.05):
                    AutofocusController._rearm(state)
                    return state

            if focus_score is None or focus_score != focus_score:
                return state
            # Smooth the incoming score: the focus measure fluctuates from frame
            # to frame, and a single dip must not restart the search.
            ema = state.get("score_ema")
            ema = focus_score if ema is None else (0.7 * ema + 0.3 * focus_score)
            state["score_ema"] = ema
            best = state.get("best_score")
            ratio = state.get("refocus_ratio", 0.88)
            if best and ema < best * ratio:
                state["low_count"] = state.get("low_count", 0) + 1
                if state["low_count"] >= state.get("refocus_patience", 4):
                    # sharpness dropped for a while -> search again from here
                    AutofocusController._rearm(state)
            else:
                state["low_count"] = 0
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
        margin = state.get("noise_margin", 0.04)
        best = state["best_score"]
        if focus_score > best:
            # Improved: keep this position as the best, continue same direction
            # with the same step so the search can travel as far as it needs to.
            state["best_score"] = focus_score
            state["best_position"] = state["position"]
            state["miss_count"] = 0
            next_position = AutofocusController._clamp01(
                state["position"] + state["direction"] * state["step"])
        elif focus_score >= best * (1.0 - margin):
            # Within the noise band: not an improvement, but not evidence that we
            # passed the peak either. Keep probing in the same direction instead
            # of shrinking the step on a single noisy sample.
            state["miss_count"] = state.get("miss_count", 0) + 1
            if state["miss_count"] < state.get("miss_patience", 2):
                next_position = AutofocusController._clamp01(
                    state["position"] + state["direction"] * state["step"])
                controller.set_focus(next_position)
                state["position"] = next_position
                return state
            state["miss_count"] = 0
            state["direction"] = -state["direction"]
            state["step"] = state["step"] * 0.5
            if state["step"] < state["min_step"]:
                controller.set_focus(state["best_position"])
                state["position"] = state["best_position"]
                settled = (controller.get_status() or {}).get("focus")
                state["settled_position"] = state["best_position"] if settled is None else settled
                state["converged"] = True
                return state
            next_position = AutofocusController._clamp01(
                state["best_position"] + state["direction"] * state["step"])
        else:
            # Clearly worse: we passed the peak -- reverse and refine.
            state["miss_count"] = 0
            state["direction"] = -state["direction"]
            state["step"] = state["step"] * 0.5
            if state["step"] < state["min_step"]:
                # Converged: park the lens at the best position seen and record
                # where it actually settled -- the seek has its own tolerance, so
                # the reading is the honest reference for drift detection.
                controller.set_focus(state["best_position"])
                state["position"] = state["best_position"]
                settled = (controller.get_status() or {}).get("focus")
                state["settled_position"] = state["best_position"] if settled is None else settled
                state["converged"] = True
                return state
            next_position = AutofocusController._clamp01(
                state["best_position"] + state["direction"] * state["step"])

        controller.set_focus(next_position)
        state["position"] = next_position
        return state
