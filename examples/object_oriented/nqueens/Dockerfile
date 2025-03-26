# Run build command in greyjack-solver-python dir
#docker build -f ./examples/object_oriented/nqueens/Dockerfile . -t nqueens

FROM python:3.12.1-slim-bullseye

WORKDIR greyjack-solver-python

RUN python3 -m pip install greyjack numba

ADD ./examples/object_oriented/nqueens ./examples/object_oriented/nqueens/

EXPOSE 8000

CMD python3 /greyjack-solver-python/examples/object_oriented/nqueens/scripts/solve_nqueens.py
#CMD ls