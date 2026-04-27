#!/usr/bin/env python3
"""Extract HSR.pdf into hsr_schedule.md.

Run from repo root:
    python3 .claude/skills/hsr-lookup/scripts/extract_hsr_pdf.py

Requires: pdfplumber (`pip install pdfplumber`).
"""
import json
import re
import sys
from pathlib import Path

import pdfplumber

DAYS = ['一', '二', '三', '四', '五', '六', '日']
STATIONS_SB = ['南港', '台北', '板橋', '桃園', '新竹', '苗栗',
               '台中', '彰化', '雲林', '嘉義', '台南', '左營']
STATIONS_NB = list(reversed(STATIONS_SB))


def parse_page(page):
    chars = page.chars
    day_positions = []
    for c in chars:
        if c['text'] in DAYS and c['top'] < 60:
            day_positions.append({'day': c['text'], 'x': (c['x0'] + c['x1']) / 2})
    day_positions.sort(key=lambda d: d['x'])

    columns = []
    cur = []
    for dp in day_positions:
        if not cur or dp['x'] - cur[-1]['x'] < 50:
            cur.append(dp)
        else:
            columns.append(cur)
            cur = [dp]
    if cur:
        columns.append(cur)

    cols_meta = []
    for col in columns:
        day_x = {}
        for dp in col:
            day_x.setdefault(dp['day'], dp['x'])
        if set(day_x.keys()) == set(DAYS):
            cols_meta.append({
                'xmin': min(day_x.values()) - 5,
                'xmax': max(day_x.values()) + 5,
                'day_x': [day_x[d] for d in DAYS],
            })

    def dot_to_days(dots):
        if not dots:
            return ''
        cx = (dots[0]['x0'] + dots[0]['x1']) / 2
        col = next((c for c in cols_meta if c['xmin'] <= cx <= c['xmax']), None)
        if col is None:
            return '?'
        ds = set()
        for d in dots:
            cx = (d['x0'] + d['x1']) / 2
            best = min(range(7), key=lambda i: abs(col['day_x'][i] - cx))
            ds.add(DAYS[best])
        return ''.join(d for d in DAYS if d in ds)

    words = page.extract_words(keep_blank_chars=False)
    train_words = [w for w in words if re.fullmatch(r'\d{3,4}', w['text'])]
    dot_words = [w for w in words if w['text'] == '●']
    time_words = [w for w in words if re.fullmatch(r'(?:\d{1,2}:\d{2}|─)', w['text'])]

    out = []
    for tw in train_words:
        ty, tx = tw['top'], tw['x0']
        dots = sorted(
            (d for d in dot_words if abs(d['top'] - ty) <= 3.5 and tx + 5 < d['x0'] < tx + 70),
            key=lambda d: d['x0'],
        )
        times = sorted(
            (t for t in time_words if abs(t['top'] - ty) <= 3.5 and t['x0'] > tx + 30),
            key=lambda t: t['x0'],
        )
        if dots:
            min_x = max(d['x0'] for d in dots) + 5
            times = [t for t in times if t['x0'] > min_x]
        times = [t for t in times if t['x0'] - tx < 530]
        if 4 <= len(times) <= 12:
            time_strs = [t['text'] for t in times]
            while len(time_strs) < 12:
                time_strs.append('─')
            out.append({'train': tw['text'], 'days': dot_to_days(dots), 'times': time_strs})
    return out


def render_table(rows, station_order, title):
    lines = [f'## {title}', '']
    lines.append('| 車次 | 行駛日 | ' + ' | '.join(station_order) + ' |')
    lines.append('|---|---|' + '---|' * len(station_order))
    for r in rows:
        days = r['days'] if r['days'] else '每日'
        cells = [r['train'], days] + r['times']
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def main():
    repo = Path(__file__).resolve().parents[4]
    pdf_path = repo / 'HSR.pdf'
    out_path = repo / 'hsr_schedule.md'
    if not pdf_path.exists():
        print(f'Error: {pdf_path} not found', file=sys.stderr)
        sys.exit(1)

    with pdfplumber.open(pdf_path) as pdf:
        nb = parse_page(pdf.pages[0])
        sb = parse_page(pdf.pages[1])

    def sort_key(r):
        for t in r['times']:
            if t != '─':
                return t
        return '99:99'
    nb.sort(key=sort_key)
    sb.sort(key=sort_key)

    body = [
        '# 高鐵班次時刻表（自動萃取自 HSR.pdf，2026-02-02 起適用）',
        '',
        '## 欄位說明',
        '- **車次**：高鐵車次編號（如 803、1321）',
        '- **行駛日**：「每日」或標示中文週幾（一=週一 … 日=週日）；空格代表每日行駛',
        '- **時刻**：HH:MM；`─` 表示該車次不停靠該站',
        '',
        render_table(sb, STATIONS_SB, '南下 Southbound（南港 → 左營）'),
        '',
        render_table(nb, STATIONS_NB, '北上 Northbound（左營 → 南港）'),
        '',
    ]
    out_path.write_text('\n'.join(body), encoding='utf-8')
    print(f'Wrote {out_path} ({len(sb)} southbound, {len(nb)} northbound trains)')


if __name__ == '__main__':
    main()
