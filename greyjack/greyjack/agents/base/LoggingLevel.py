

from enum import Enum

class LoggingLevel(Enum):
    FreshOnly = 0 # log only new solutions, that are best than previous
    Info = 1 # log all new solutions
    Warn = 2 # log only warning situations