from decimal import Decimal
from fractions import Fraction

from .models import Language


DURATION_SECONDS = 300


def target_seconds(*, language, correct_count, target_per_minute):
    """Convert correct Han characters or correct English keystrokes to target time."""
    if language not in Language.values or type(correct_count) is not int or correct_count < 0:
        raise ValueError('Invalid typing language or correct count')
    speed = Fraction(str(target_per_minute))
    if speed <= 0:
        raise ValueError('Typing target speed must be positive')

    units = Fraction(correct_count, 5) if language == Language.ENGLISH else correct_count
    return units * 60 / speed


def progress_for(total_target_seconds):
    return max(Fraction(0), min(Fraction(total_target_seconds) / DURATION_SECONDS, Fraction(1)))


def score_for(progress):
    if progress >= 1:
        return Decimal('100.0')

    # Round half up to a tenth while keeping 100 exclusive to summits.
    rounded_tenths = int(progress * 1000 + Fraction(1, 2))
    return Decimal(min(rounded_tenths, 999)).scaleb(-1)
