"""
MIT License

Copyright (c) 2024 HiGHS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



# This is an example of the N-Queens problem, which is a classic combinatorial problem.
# The problem is to place N queens on an N x N chessboard so that no two queens attack each other.
#
# We show how to model the problem as a MIP and solve it using highspy.
# Using numpy can simplify the construction of the constraints (i.e., diagonal).

import highspy
import numpy as np
from datetime import datetime

N = 64
h = highspy.Highs()
h.silent()

x = h.addBinaries(N, N)

h.addConstrs(x.sum(axis=0) == 1)    # each row has exactly one queen
h.addConstrs(x.sum(axis=1) == 1)    # each col has exactly one queen

y = np.fliplr(x)
h.addConstrs(x.diagonal(k).sum() <= 1 for k in range(-N + 1, N))   # each diagonal has at most one queen
h.addConstrs(y.diagonal(k).sum() <= 1 for k in range(-N + 1, N))   # each 'reverse' diagonal has at most one queen

start_time = datetime.now()
h.solve()
solving_time = datetime.now() - start_time

sol = h.vals(x)
print('Queens:')
for i in range(N):
    print(''.join('Q' if sol[i, j] > 0.5 else '*' for j in range(N)))

print("Solving time: {}", solving_time)