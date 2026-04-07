from datetime import time


def time_from_int(value: int) -> time:
    hours = value // 3600
    minutes = (value % 3600) // 60
    seconds = value % 60
    return time(hours, minutes, seconds)
