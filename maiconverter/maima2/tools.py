from typing import List
from .ma2note import note_dict, slide_dict

_ignored_v1 = [
    "VERSION",
    "FES_MODE",
    "BPM_DEF",
    "MET_DEF",
    "CLK_DEF",
    "CLK",
    "COMPATIBLE_CODE",
    "T_REC_TAP",
    "T_REC_BRK",
    "T_REC_XTP",
    "T_REC_HLD",
    "T_REC_XHO",
    "T_REC_STR",
    "T_REC_BST",
    "T_REC_XST",
    "T_REC_TTP",
    "T_REC_THO",
    "T_REC_SLD",
    "T_REC_ALL",
    "T_NUM_TAP",
    "T_NUM_BRK",
    "T_NUM_HLD",
    "T_NUM_SLD",
    "T_NUM_ALL",
    "T_JUDGE_TAP",
    "T_JUDGE_HLD",
    "T_JUDGE_SLD",
    "T_JUDGE_ALL",
    "TTM_EACHPAIRS",
    "TTM_SCR_TAP",
    "TTM_SCR_BRK",
    "TTM_SCR_HLD",
    "TTM_SCR_SLD",
    "TTM_SCR_ALL",
    "TTM_SCR_S",
    "TTM_SCR_SS",
    "TTM_RAT_ACV",
]

_MAGICAL_PREFIXES = ("NM", "EX", "BR", "BX", "CN")

def _normalize_new_type(line_type: str) -> str:
    if len(line_type) != 5 or line_type[:2] not in _MAGICAL_PREFIXES:
        return line_type
    prefix, base = line_type[:2], line_type[2:]
    
    # Return base pattern for CN slide chains
    if prefix == "CN":
        return base
        
    if base == "TAP":
        return {"NM": "TAP", "EX": "XTP", "BR": "BRK", "BX": "BXTP"}[prefix]
    if base == "HLD":
        return {"NM": "HLD", "EX": "XHO", "BR": "BRHLD", "BX": "BXHLD"}[prefix]
    if base == "STR":
        return {"NM": "STR", "EX": "XST", "BR": "BST", "BX": "BXST"}[prefix]
    return base

def parse_v1(ma2, values: List[str]) -> None:
    """Ma2 line parser for versions 1.02.00 and 1.03.00 currently."""
    if values[0].startswith(("T_REC_", "T_NUM_", "T_JUDGE", "TTM_")):
        return
    
    raw_type = values[0]
    new_type = _normalize_new_type(raw_type)
    if new_type == "":
        return
    
    # Keep track of original raw_type for slide chain detection
    values = [new_type] + values[1:]
    line_type = values[0]
    
    if line_type in _ignored_v1:
        return
    if line_type == "RESOLUTION":
        ma2._resolution = int(values[1])
    elif line_type == "BPM":
        measure = float(values[1]) + float(values[2]) / ma2.resolution
        bpm = float(values[3])
        ma2.set_bpm(measure, bpm)
    elif line_type == "MET":
        measure = float(values[1]) + float(values[2]) / ma2.resolution
        ma2.set_meter(measure, int(values[3]), int(values[4]))
    elif line_type in list(note_dict.keys()):
        _handle_notes_v1(ma2, values)
    elif line_type in list(slide_dict.keys()):
        _handle_slides_v1(ma2, values, raw_type=raw_type)
    else:
        print(f"Warning: Ignoring unknown line type {line_type}")


def _handle_notes_v1(ma2, values: List[str]) -> None:
    line_type = values[0]
    measure = float(values[1]) + float(values[2]) / ma2.resolution
    position = int(values[3])
    if line_type in ["TAP", "BRK", "XTP", "BXTP", "STR", "BST", "XST", "BXST"]:
        is_break = line_type in ["BRK", "BST", "BXTP", "BXST"]
        is_ex = line_type in ["XTP", "BXTP", "XST", "BXST"]
        is_star = line_type in ["STR", "BST", "XST", "BXST"]
        ma2.add_tap(measure, position, is_break, is_star, is_ex)
    elif line_type in ["XHO", "HLD", "BRHLD", "BXHLD"]:
        is_ex = line_type in ["XHO", "BXHLD"]
        is_break = line_type in ["BRHLD", "BXHLD"]
        duration = float(values[4]) / ma2.resolution
        ma2.add_hold(measure, position, duration, is_ex=is_ex, is_break=is_break)
    elif line_type == "TTP":
        region = values[4]
        is_firework = values[5] == "1"
        size = values[6] if len(values) > 6 else "M1"
        ma2.add_touch_tap(measure, position, region, is_firework, size)
    elif line_type == "THO":
        duration = float(values[4]) / ma2.resolution
        region = values[5]
        is_firework = values[6] == "1"
        size = values[7] if len(values) > 7 else "M1"
        ma2.add_touch_hold(measure, position, region, duration, is_firework, size)


def _handle_slides_v1(ma2, values: List[str], raw_type: str = "") -> None:
    is_chain = raw_type.startswith("CN")
    line_type = values[0]
    pattern = slide_dict[line_type]
    
    measure = float(values[1]) + float(values[2]) / ma2.resolution
    start_position = int(values[3])
    delay = int(values[4]) / ma2.resolution
    duration = int(values[5]) / ma2.resolution
    end_position = int(values[6])
    
    ma2.add_slide(
        measure,
        start_position,
        end_position,
        duration,
        pattern,
        delay,
        is_chain=is_chain,
    )