#!/usr/bin/env python3
"""機場捷運時刻查詢

Usage:
  python3 query.py --from A21 --to A17 [--start HH:MM] [--end HH:MM]
  python3 query.py --from 領航站 --to 台北車站 --start 14:00 --end 15:00
"""
import argparse
import re
import sys
from pathlib import Path

AVAILABLE = {"A1", "A12", "A13", "A17", "A18", "A21", "A22"}

NAME_TO_CODE = {
    "台北車站": "A1", "台北": "A1",
    "機場第一航廈": "A12", "第一航廈": "A12",
    "機場第二航廈": "A13", "第二航廈": "A13",
    "領航站": "A17", "領航": "A17",
    "高鐵桃園站": "A18", "高鐵桃園": "A18",
    "環北站": "A21", "環北": "A21",
    "老街溪站": "A22", "老街溪": "A22",
}

CODE_TO_NAME = {
    "A1": "台北車站",
    "A12": "機場第一航廈",
    "A13": "機場第二航廈",
    "A17": "領航站",
    "A18": "高鐵桃園站",
    "A21": "環北站",
    "A22": "老街溪站",
}

# 直達車（無符號）停靠站
DIRECT_STOPS = {"A1", "A3", "A8", "A12", "A13"}
# 尖峰增停直達車（★）停靠站
STAR_STOPS = {"A1", "A3", "A8", "A12", "A13", "A18", "A21"}
# 尖峰跳站普通車（◆）停靠站：A21, A18, A13, A12, A9→A1 每站
DIAMOND_STOPS = {"A21", "A18", "A13", "A12"} | {f"A{i}" for i in range(1, 10)}


def normalize_station(s: str) -> str:
    s = s.strip()
    if s.upper() in AVAILABLE:
        return s.upper()
    if s in NAME_TO_CODE:
        return NAME_TO_CODE[s]
    return s.upper()


def station_num(code: str) -> float:
    code = code.upper()
    if code == "A14A":
        return 14.5
    return int(code[1:])


def parse_time(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def determine_direction(origin: str, dest: str) -> str:
    """北上（往 A1）= 'north'；南下（往 A22）= 'south'。"""
    o, d = station_num(origin), station_num(dest)
    if o > d:
        return "north"
    if o < d:
        return "south"
    raise ValueError("起訖站相同")


def direction_label(direction: str) -> str:
    return "往台北車站、機場方向" if direction == "north" else "往中壢（老街溪站）方向"


def direction_keyword(direction: str) -> str:
    # 注意：A12 南下標題為「往機場、中壢...」，故只用 "中壢" 而非 "往中壢"
    return "往台北車站" if direction == "north" else "中壢"


def parse_timetable(text: str, station: str, direction: str):
    """從 markdown 中擷取指定車站、指定方向的所有班次。

    回傳 list of (hour, minute, marker, raw)。
    """
    keyword = direction_keyword(direction)
    section_pat = re.compile(rf"^## {re.escape(station)} ", re.MULTILINE)
    m = section_pat.search(text)
    if not m:
        return None

    section_start = m.start()
    next_section = re.search(r"^## ", text[section_start + 1:], re.MULTILINE)
    section_end = section_start + 1 + next_section.start() if next_section else len(text)
    section = text[section_start:section_end]

    sub_pat = re.compile(rf"^### .*{re.escape(keyword)}.*", re.MULTILINE)
    sm = sub_pat.search(section)
    if not sm:
        # 單向站（如 A1 起點站只往機場、A22 終點站只往台北）
        # 若方向與該站唯一方向相符，直接使用整個 section
        if station == "A1" and direction == "south":
            sm_match = re.search(r"^\*\*往機場", section, re.MULTILINE)
            if sm_match:
                sub_start = sm_match.start()
                sub = section[sub_start:]
                return _parse_table_lines(sub)
        return None

    sub_start = sm.start()
    # 跳過目前 ### 標題那一整行，再尋找下一個區段邊界
    line_end = section.find("\n", sub_start)
    search_from = line_end + 1 if line_end != -1 else sub_start + 1
    next_sub = re.search(r"^### ", section[search_from:], re.MULTILINE)
    next_main = re.search(r"^## ", section[search_from:], re.MULTILINE)
    candidates = [r for r in (next_sub, next_main) if r]
    sub_end = search_from + min(r.start() for r in candidates) if candidates else len(section)
    sub = section[sub_start:sub_end]
    return _parse_table_lines(sub)


def _parse_table_lines(sub: str):
    entries = []
    for line in sub.splitlines():
        m = re.match(r"\|\s*(\d{1,2})\s*\|\s*(.+?)\s*\|", line)
        if not m:
            continue
        if m.group(2).strip() in ("分", "") or set(m.group(2).strip()) <= set("-: "):
            continue
        hour = int(m.group(1))
        for raw in m.group(2).split(","):
            raw = raw.strip()
            tm = re.match(r"(\d+)\s*([★◆▼]?)", raw)
            if not tm:
                continue
            minute = int(tm.group(1))
            marker = tm.group(2) or ""
            entries.append((hour, minute, marker, raw))
    return entries


def train_type(marker: str) -> str:
    return {
        "": "普通車",
        "★": "尖峰增停直達車",
        "◆": "尖峰跳站普通車",
        "▼": "增開往機場班次",
    }.get(marker, f"未知({marker})")


def stops_at(marker: str, origin: str, dest: str, direction: str):
    """判斷該班是否停靠 dest。回傳 True / False / None（模糊）。"""
    if marker == "▼":
        # ▼ 北上：A22→A12 全停；南下：A1→A13 全停
        d = station_num(dest)
        if direction == "north":
            return 12 <= d <= 22
        else:
            return 1 <= d <= 13
    if marker == "★":
        return dest in STAR_STOPS
    if marker == "◆":
        # ◆ 為北上方向（A21→A18→A13→A12→A9-A1）
        if direction != "north":
            return False
        return dest in DIAMOND_STOPS
    # 無符號
    if origin not in DIRECT_STOPS:
        # 起站不在直達車停靠列表 → 必為普通車（每站皆停）
        return True
    # 起站在直達車停靠列表
    if dest in DIRECT_STOPS:
        return True  # 直達或普通皆停
    return None  # 模糊：可能是直達（不停 dest）也可能是普通（停 dest）


def find_timetable_file() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / "airport_mrt_timetable.md"
        if candidate.exists():
            return candidate
    raise FileNotFoundError("找不到 airport_mrt_timetable.md")


def main() -> int:
    p = argparse.ArgumentParser(description="機場捷運時刻查詢")
    p.add_argument("--from", dest="origin", required=True, help="起站（A 編號或中文名）")
    p.add_argument("--to", dest="dest", required=True, help="迄站（A 編號或中文名）")
    p.add_argument("--start", default="00:00", help="時間窗起點 HH:MM（預設 00:00）")
    p.add_argument("--end", default="23:59", help="時間窗終點 HH:MM（預設 23:59）")
    p.add_argument("--all", action="store_true", help="列出所有班次（含不停靠目的地者）")
    args = p.parse_args()

    origin = normalize_station(args.origin)
    dest = normalize_station(args.dest)

    if origin not in AVAILABLE:
        print(f"錯誤：{args.origin} 不在資料中。可用：{sorted(AVAILABLE)}", file=sys.stderr)
        return 1
    if dest not in AVAILABLE and station_num(dest) > 22:
        print(f"錯誤：{args.dest} 站名無法解析", file=sys.stderr)
        return 1
    if origin == dest:
        print("錯誤：起訖站相同", file=sys.stderr)
        return 1

    direction = determine_direction(origin, dest)
    tt_file = find_timetable_file()
    text = tt_file.read_text(encoding="utf-8")
    entries = parse_timetable(text, origin, direction)
    if entries is None:
        print(f"錯誤：找不到 {origin} {direction_label(direction)} 的時刻表", file=sys.stderr)
        return 1

    start_min = parse_time(args.start)
    end_min = parse_time(args.end)

    # 篩選時間窗（00:xx 視為 24:xx 之後）
    in_window = []
    for hour, minute, marker, raw in entries:
        t = hour * 60 + minute
        if hour < 5:  # 00:xx 是凌晨班，視為前一日延伸
            t += 24 * 60
        if start_min <= t <= end_min:
            in_window.append((hour, minute, marker, raw))

    origin_name = CODE_TO_NAME.get(origin, origin)
    dest_name = CODE_TO_NAME.get(dest, dest)

    print(f"{origin}({origin_name}) → {dest}({dest_name})  方向：{direction_label(direction)}")
    print(f"時間窗：{args.start}–{args.end}")
    print()

    if not in_window:
        print("此時段無班次。")
        return 0

    can_take = []
    cannot_take = []
    ambiguous = []

    print(f"{'時刻':<7} {'符號':<3} {'車型':<14} 停靠目的地")
    print("-" * 50)
    for hour, minute, marker, raw in in_window:
        s = stops_at(marker, origin, dest, direction)
        time_str = f"{hour:02d}:{minute:02d}"
        sym = marker if marker else "·"
        ttype = train_type(marker)
        if s is True:
            status = "✅ 停"
            can_take.append(time_str)
        elif s is False:
            status = "❌ 不停"
            cannot_take.append(time_str)
        else:
            status = "⚠ 模糊"
            ambiguous.append(time_str)
        if args.all or s is not False:
            print(f"{time_str:<7} {sym:<3} {ttype:<14} {status}")

    print()
    print(f"可搭：{len(can_take)} 班    排除：{len(cannot_take)} 班    模糊：{len(ambiguous)} 班")
    if not args.all and cannot_take:
        print(f"（已自動隱藏不停靠 {dest} 的 {len(cannot_take)} 班；加 --all 可顯示）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
