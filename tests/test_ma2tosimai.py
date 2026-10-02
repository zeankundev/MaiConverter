from maiconverter.maima2 import MaiMa2, SlideNote as Ma2SlideNote
from maiconverter.converter import ma2_to_simai, simai_to_ma2
from maiconverter.simai import TouchHoldNote, pattern_from_int
from maiconverter.simai.simai import SimaiChart
from maiconverter.simai.simai_parser import parse_fragment
from maiconverter.simai.tools import convert_to_fragment


def test_slide360_conversion():
    """Tests whether a ma2 360 degree slide is properly converted in Simai.
    Addresses https://github.com/donmai-me/MaiConverter/issues/9"""
    ma2_cw_360_1 = MaiMa2()
    ma2_cw_360_1.set_bpm(0.0, 120)
    ma2_cw_360_1.add_slide(1.0, 1, 1, 1.0, 3)  # Pattern 3 is CW

    ma2_cw_360_2 = MaiMa2()
    ma2_cw_360_2.set_bpm(0.0, 120)
    ma2_cw_360_2.add_slide(1.0, 4, 4, 1.0, 3)  # Pattern 3 is CW

    ma2_ccw_360_1 = MaiMa2()
    ma2_ccw_360_1.set_bpm(0.0, 120)
    ma2_ccw_360_1.add_slide(1.0, 1, 1, 1.0, 2)  # Pattern 2 is CCW

    ma2_ccw_360_2 = MaiMa2()
    ma2_ccw_360_2.set_bpm(0.0, 120)
    ma2_ccw_360_2.add_slide(1.0, 4, 4, 1.0, 2)  # Pattern 2 is CCW

    simai_cw_360_1 = ma2_to_simai(ma2_cw_360_1)
    assert len(simai_cw_360_1.notes) == 1
    simai_cw_360_slide = simai_cw_360_1.notes[0]
    assert simai_cw_360_slide.position == simai_cw_360_slide.end_position
    assert simai_cw_360_slide.pattern == ">"

    simai_cw_360_2 = ma2_to_simai(ma2_cw_360_2)
    assert len(simai_cw_360_2.notes) == 1
    simai_cw_360_slide = simai_cw_360_2.notes[0]
    assert simai_cw_360_slide.position == simai_cw_360_slide.end_position
    assert simai_cw_360_slide.pattern == "<"

    simai_ccw_360_1 = ma2_to_simai(ma2_ccw_360_1)
    assert len(simai_ccw_360_1.notes) == 1
    simai_ccw_360_slide = simai_ccw_360_1.notes[0]
    assert simai_ccw_360_slide.position == simai_ccw_360_slide.end_position
    assert simai_ccw_360_slide.pattern == "<"

    simai_ccw_360_2 = ma2_to_simai(ma2_ccw_360_2)
    assert len(simai_ccw_360_2.notes) == 1
    simai_ccw_360_slide = simai_ccw_360_2.notes[0]
    assert simai_ccw_360_slide.position == simai_ccw_360_slide.end_position
    assert simai_ccw_360_slide.pattern == ">"


def test_touch_hold_fragment_keeps_touch_position():
    touch_hold = TouchHoldNote(
        measure=1.0,
        position=0,
        region="E",
        duration=0.25,
        is_firework=True,
    )

    fragment = convert_to_fragment([touch_hold], current_bpm=120)

    assert fragment == "E1hf[4:1]"
    assert parse_fragment(fragment)[0]["location"] == 0


def test_weird_slide_patterns_map_to_simai_routes():
    cases = [
        (11, 0, 4),
        (12, 0, 4),
        (2, 0, 0),
        (3, 0, 0),
    ]

    for pattern, start, end in cases:
        simai_pattern, reflect_position = pattern_from_int(pattern, start, end)
        assert simai_pattern in {"V", "^", ">", "<"}
        if simai_pattern == "V":
            assert reflect_position is not None


def test_no_star_chained_slide_keeps_tapless_path():
    ma2 = MaiMa2()
    ma2.set_bpm(0.0, 120)
    ma2.add_tap(1.0, 0)
    ma2.add_slide(1.0, 0, 2, 1.0, 1)
    ma2.add_slide(1.0, 2, 4, 1.0, 1, is_chain=True)

    fragment = ma2_to_simai(ma2).export()

    assert "1?-3[1:1]*-5[1:1]" in fragment


def test_chain_flag_is_preserved_in_simai_to_ma2_conversion():
    simai = SimaiChart()
    simai.set_bpm(1.0, 120)
    simai.add_slide(1.0, 0, 2, 1.0, "-")
    simai.add_slide(1.0, 2, 4, 1.0, "-", is_chain=True)

    ma2 = simai_to_ma2(simai)
    slides = [note for note in ma2.notes if isinstance(note, Ma2SlideNote)]

    assert len(slides) == 2
    assert slides[0].is_chain is False
    assert slides[1].is_chain is True
