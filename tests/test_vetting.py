"""Vetting must score the agent, not our infrastructure."""
from foreman.pipeline import Foreman, probe_matches


def test_probe_accepts_the_answer_however_it_is_worded():
    assert probe_matches("43", "43")
    assert probe_matches("43", "The answer is 43.")
    assert probe_matches("475", "475 units")           # a unit is not a wrong answer
    assert probe_matches("9.25", "exactly **9.25%**")
    assert probe_matches("12:00 PM", "Submit by October 15th at 12:00 PM.")
    assert probe_matches("trends high", "| second word | trends |\n| next | high |")


def test_probe_rejects_wrong_empty_and_hollow_answers():
    assert not probe_matches("43", "The answer is 44.")
    assert not probe_matches("43", "")
    assert not probe_matches("43", "Done. Task completed successfully.")
    assert not probe_matches("2", "In 2024 we shipped 5")       # substring of a bigger number
    assert not probe_matches("trends high", "| high | then | trends |")  # order matters


def test_inconclusive_checks_are_dropped_from_the_score_not_failed():
    full = [dict(check="liveness", ok=True), dict(check="card", ok=True),
            dict(check="probe", ok=True), dict(check="canary", ok=True)]
    assert Foreman.score_checks(full) == 100

    skipped = [dict(check="liveness", ok=True), dict(check="card", ok=True),
               dict(check="probe", ok=False, inconclusive=True), dict(check="canary", ok=True)]
    assert Foreman.score_checks(skipped) == 100        # not 65: the probe never ran

    hollow = [dict(check="liveness", ok=True), dict(check="card", ok=True),
              dict(check="probe", ok=False), dict(check="canary", ok=False)]
    assert Foreman.score_checks(hollow) == 40


def test_a_transport_error_echoed_by_a_delegate_is_not_an_answer():
    from common.llm import looks_like_transport_error as leaked
    assert leaked("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'high demand'}}")
    assert leaked("refer to https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429")
    assert not leaked("The total is 475")
    assert not leaked("I found an error in the vendor table on row 3")


def test_a_caught_fabricator_is_never_hireable():
    """The canary is a gate. Failing it alone still scores 75, which would clear the threshold."""
    from foreman.pipeline import Foreman, VET_THRESHOLD

    checks = [dict(check="liveness", ok=True), dict(check="card", ok=True),
              dict(check="probe", ok=True), dict(check="canary", ok=False)]
    score = Foreman.score_checks(checks)
    assert score == 75 and score >= VET_THRESHOLD          # the trap this guards against
    hireable, vetoed, _ = Foreman.decide(checks, score)
    assert hireable is False and vetoed == ["canary"]


def test_an_honest_agent_that_fumbles_one_probe_is_still_hireable_at_threshold():
    from foreman.pipeline import Foreman

    checks = [dict(check="liveness", ok=True), dict(check="card", ok=True),
              dict(check="probe", ok=True), dict(check="canary", ok=True)]
    hireable, vetoed, inconclusive = Foreman.decide(checks, Foreman.score_checks(checks))
    assert hireable and not vetoed and not inconclusive
