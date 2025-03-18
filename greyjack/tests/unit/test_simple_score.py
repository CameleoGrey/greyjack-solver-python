

from greyjack.score_calculation.scores.SimpleScore import SimpleScore


def test_sum_simple_scores():

    score_1 = SimpleScore(0)
    score_2 = SimpleScore(1)
    score_3 = score_1 + score_2
    assert score_3 == SimpleScore(1)