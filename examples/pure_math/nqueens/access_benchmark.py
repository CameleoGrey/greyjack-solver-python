

import numpy as np
from datetime import datetime

# TODO: add possibility of int (i64, usize) naming for variables inside MathModel

n = 1000000
dict_int = {}
dict_string = {}
for i in range(n):
    dict_int[i] = i
    dict_string[f"x_{i}"] = i

list_int = [i for i in range(n)]
list_string = ["x_{}".format(i) for i in range(n)]
array = np.arange(0, n)
print(type(array))


start_time = datetime.now()
for i in range(n):
    value = dict_int[i]
print("Access time for dict_int: {}", datetime.now() - start_time)

start_time = datetime.now()
for i in range(n):
    value = dict_string["x_{}".format(i)]
print("Access time for dict_string: {}", datetime.now() - start_time)

start_time = datetime.now()
for i in range(n):
    value = dict_string[list_string[i]]
print("Access time for dict_string by using cached str ids: {}", datetime.now() - start_time)

start_time = datetime.now()
for i in range(n):
    value = list_int[i]
print("Access time for list_int: {}", datetime.now() - start_time)

start_time = datetime.now()
for i in range(n):
    value = array[i]
print("Access time for array: {}", datetime.now() - start_time)


start_time = datetime.now()
sum([dict_int[i] for i in range(n)])
print("Sum time for dict_int: {}", datetime.now() - start_time)

start_time = datetime.now()
sum([list_int[i] for i in range(n)])
print("Sum time for list_int: {}", datetime.now() - start_time)

start_time = datetime.now()
np.sum(array)
print("Sum time for array: {}", datetime.now() - start_time)

start_time = datetime.now()
np.sum([list_int[i] for i in range(n)])
print("Sum time for np.sum() for list_int: {}", datetime.now() - start_time)