

from greyjack.score_calculation.scores import SimpleScore, HardSoftScore, HardMediumSoftScore

#TODO: write normal unit-tests

score_0 = SimpleScore(0)
score_1 = SimpleScore(1.0)
print(score_0)
print(score_1)
print(score_1 > score_0)

score_0 = HardSoftScore(0, 1)
score_1 = HardSoftScore(1.0, 2.0)
print(score_0)
print(score_1)
print(score_1 > score_0)

score_0 = HardMediumSoftScore(0, 1, 2)
score_1 = HardMediumSoftScore(3.0, 4.0, 5.0)
print(score_0)
print(score_1)
print(score_1 > score_0)