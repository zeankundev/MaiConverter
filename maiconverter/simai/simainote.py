from typing import Optional, Tuple

from ..event import Event, EventType
from ..event.note import SimaiNote, NoteType
from ..tool import slide_distance, slide_is_cw


# For straightforward slide pattern conversion from simai to sxt/ma2.
# Use simai_pattern_to_int to cover all simai slide patterns.
slide_dict = {
    "-": 1,
    "p": 4,
    "q": 5,
    "s": 6,
    "z": 7,
    "v": 8,
    "pp": 9,
    "qq": 10,
    "w": 13,
}

slide_patterns = [
    "-",
    "^",
    ">",
    "<",
    "p",
    "q",
    "s",
    "z",
    "v",
    "pp",
    "qq",
    "V",
    "w",
]


class TapNote(SimaiNote):
    def __init__(
        self,
        measure: float,
        position: int,
        is_break: bool = False,
        is_star: bool = False,
        is_ex: bool = False,
    ) -> None:
        measure = round(100000.0 * measure) / 100000.0
        if is_ex and is_star:
            super().__init__(measure, position, NoteType.ex_star)
        elif is_ex and not is_star:
            super().__init__(measure, position, NoteType.ex_tap)
        elif is_star and is_break:
            super().__init__(measure, position, NoteType.break_star)
        elif is_star and not is_break:
            super().__init__(measure, position, NoteType.star)
        elif is_break:
            super().__init__(measure, position, NoteType.break_tap)
        else:
            super().__init__(measure, position, NoteType.tap)

        self.is_break = is_break
        self.is_ex = is_ex
        self.is_star = is_star


class HoldNote(SimaiNote):
    def __init__(
        self,
        measure: float,
        position: int,
        duration: float,
        is_ex: bool = False,
        is_break: bool = False,
    ) -> None:
        if duration < 0:
            raise ValueError(f"Hold duration is negative: {duration}")

        measure = round(100000.0 * measure) / 100000.0
        duration = round(100000.0 * duration) / 100000.0
        if is_ex:
            super().__init__(measure, position, NoteType.ex_hold)
        else:
            super().__init__(measure, position, NoteType.hold)

        self.is_ex = is_ex
        self.is_break = is_break
        self.duration = duration


class SlideNote(SimaiNote):
    def __init__(
        self,
        measure: float,
        start_position: int,
        end_position: int,
        duration: float,
        pattern: str,
        delay: float = 0.25,
        reflect_position: Optional[int] = None,
        is_chain: bool = False,
    ) -> None:
        """Produces a simai slide note.

        Note: Simai slide durations does not include slide delay.

        Args:
            measure (float): Measure where the slide note begins.
            start_position (int): Button where slide begins. [0, 7]
            end_position (int): Button where slide ends. [0, 7]
            duration (float): Total duration, in measures, of
                the slide, including delay.
            pattern (str): Simai slide pattern. If 'V', then
                reflect_position should not be None.
            delay (float, optional): Time duration, in measures,
                from where slide appears and when it starts to move.
                Defaults to 0.25.
            reflect_position (Optional[int], optional): For 'V'
                patterns. Defaults to None.

        Raises:
            ValueError: When duration is not positive
                or when delay is negative
        """
        measure = round(100000.0 * measure) / 100000.0
        duration = round(100000.0 * duration) / 100000.0
        delay = round(100000.0 * delay) / 100000.0
        if duration <= 0:
            raise ValueError("Duration is not positive " + str(duration))
        if delay < 0:
            raise ValueError("Delay is negative " + str(duration))
        if pattern not in slide_patterns:
            raise ValueError("Unknown slide pattern " + str(pattern))
        if pattern == "V" and reflect_position is None:
            raise Exception("Slide pattern 'V' is given " + "without reflection point")

        super().__init__(measure, start_position, NoteType.complete_slide)
        self.duration = duration
        self.end_position = end_position
        self.pattern = pattern
        self.delay = delay
        self.reflect_position = reflect_position
        self.is_chain = is_chain
        # Connected-slide bookkeeping. Filled in by link_chained_slides().
        # chain_head: first segment of the connected slide (None if this
        #   note is a head or a standalone slide).
        # chain_next: the segment that continues from this one.
        # chain_rel_start: time, in measures, between the head finishing its
        #   delay and this segment starting to move.
        self.chain_head: Optional["SlideNote"] = None
        self.chain_next: Optional["SlideNote"] = None
        self.chain_rel_start: float = 0.0


class TouchTapNote(SimaiNote):
    def __init__(
        self, measure: float, position: int, region: str, is_firework: bool = False
    ) -> None:
        measure = round(measure * 100000.0) / 100000.0

        super().__init__(measure, position, NoteType.touch_tap)
        self.is_firework = is_firework
        self.region = region


class TouchHoldNote(SimaiNote):
    def __init__(
        self,
        measure: float,
        position: int,
        region: str,
        duration: float,
        is_firework: bool = False,
    ) -> None:
        measure = round(measure * 100000.0) / 100000.0
        duration = round(duration * 100000.0) / 100000.0

        super().__init__(measure, position, NoteType.touch_hold)
        self.is_firework = is_firework
        self.region = region
        self.duration = duration


class BPM(Event):
    def __init__(self, measure: float, bpm: float) -> None:
        if bpm <= 0:
            raise ValueError("BPM is not positive " + str(bpm))

        measure = round(measure * 100000.0) / 100000.0

        super().__init__(measure, EventType.bpm)
        self.bpm = bpm


def link_chained_slides(slides, tolerance: float = 0.002) -> None:
    """Attach every ma2 ``CN`` segment to the slide it continues.

    A connected slide is ONE slide in simai: ``1-3[4:1]-5[4:1]``. The ``*``
    operator is a different thing (a second slide from the same start button)
    and makes the editor spawn an extra star, so segments must be merged
    into their head instead of being exported as separate notes.

    ma2 files are not consistent on how a CN line is timed (own measure with
    zero delay, or head measure with the delay as an offset), so a segment is
    matched to the open tail that ends on its start button and either ends
    exactly when the segment begins, or starts at the same measure.
    """
    heads = [s for s in slides if not s.is_chain]
    chains = [s for s in slides if s.is_chain]
    chains.sort(key=lambda s: (s.measure, s.measure + s.delay))
    open_tails = list(heads)

    def tail_end(note) -> float:
        head = note.chain_head or note
        return head.measure + head.delay + note.chain_rel_start + note.duration

    for seg in chains:
        seg_start = seg.measure + seg.delay
        best = None
        best_score = None
        for tail in open_tails:
            if tail.end_position != seg.position or tail.chain_next is not None:
                continue
            head = tail.chain_head or tail
            if abs(tail_end(tail) - seg_start) <= tolerance:
                score = 0
            elif abs(head.measure - seg.measure) <= tolerance:
                score = 1
            else:
                continue
            if best_score is None or score < best_score:
                best, best_score = tail, score

        if best is None:
            # Orphan segment: keep it as a normal slide so it is not lost.
            print(
                f"Warning: chained slide at measure {seg.measure} "
                f"(button {seg.position + 1}) has no parent slide"
            )
            seg.is_chain = False
            open_tails.append(seg)
            continue

        head = best.chain_head or best
        seg.chain_head = head
        seg.chain_rel_start = best.chain_rel_start + best.duration
        best.chain_next = seg
        seg.measure = head.measure
        open_tails.append(seg)


def slide_to_pattern_str(slide_note: SlideNote) -> str:
    pattern = slide_note.pattern
    if pattern != "V":
        return pattern

    if slide_note.reflect_position is None:
        raise Exception("Slide has 'V' pattern but no reflect position")

    return "V{}".format(slide_note.reflect_position + 1)


def pattern_from_int(
    pattern: int, start_position: int, end_position: int
) -> Tuple[str, Optional[int]]:
    top_list = [0, 1, 6, 7]
    inv_slide_dict = {v: k for k, v in slide_dict.items()}
    dict_result = inv_slide_dict.get(pattern)
    if dict_result is not None:
        return dict_result, None
    if pattern in [2, 3]:
        # Have I told you how much I hate the simai format?
        is_cw = pattern == 3
        distance = slide_distance(start_position, end_position, is_cw)
        if 0 < distance <= 3:
            return "^", None
        if distance == 0:
            if start_position in top_list and is_cw:
                return ">", None
            if start_position in top_list and not is_cw:
                return "<", None
            if start_position not in top_list and is_cw:
                return "<", None

            return ">", None
        if (start_position in top_list and is_cw) or not (
            start_position in top_list or is_cw
        ):
            return ">", None

        return "<", None
    if pattern in [11, 12]:
        if pattern == 11:
            reflect_position = start_position - 2
            if reflect_position < 0:
                reflect_position += 8
        else:
            reflect_position = start_position + 2
            if reflect_position > 7:
                reflect_position -= 8

        return "V", reflect_position

    raise ValueError(f"Unknown pattern: {pattern}")


def pattern_to_int(slide_note: SlideNote) -> int:
    pattern = slide_note.pattern
    top_list = [0, 1, 6, 7]

    dict_result = slide_dict.get(pattern)
    if dict_result is not None:
        return dict_result
    elif pattern == "^":
        is_cw = slide_is_cw(slide_note.position, slide_note.end_position)
        if is_cw:
            return 3
        else:
            return 2
    elif pattern == ">":
        is_top = slide_note.position in top_list
        if is_top:
            return 3
        else:
            return 2
    elif pattern == "<":
        is_top = slide_note.position in top_list
        if is_top:
            return 2
        else:
            return 3
    elif pattern == "V":
        if slide_note.reflect_position is None:
            raise ValueError("Slide pattern 'V' has no reflect position defined")

        is_cw = slide_is_cw(slide_note.position, slide_note.reflect_position)
        if is_cw:
            return 12
        else:
            return 11
    else:
        raise ValueError(f"Unknown slide pattern {pattern}")