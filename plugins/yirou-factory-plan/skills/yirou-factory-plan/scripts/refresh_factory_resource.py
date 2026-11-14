"""Read an XLSX without modifying it; build the skill's offline Markdown/images."""
import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'xdr': 'http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'}

def part(base, target):
    return target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.join(posixpath.dirname(base), target))

def rels(z, base):
    name = posixpath.join(posixpath.dirname(base), '_rels', posixpath.basename(base) + '.rels')
    if name not in z.namelist():
        return {}
    return {e.get('Id'): part(base, e.get('Target')) for e in ET.fromstring(z.read(name)) if e.get('TargetMode') != 'External'}

def column(ref):
    n = 0
    for c in re.match(r'[A-Z]+', ref).group():
        n = n * 26 + ord(c) - 64
    return n - 1

def read_book(z):
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        shared = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
    mapping = rels(z, 'xl/workbook.xml')
    sheets = []
    for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', NS):
        root = ET.fromstring(z.read(mapping[sheet.get('{'+NS['r']+'}id')]))
        rows = []
        width = 0
        for row in root.findall('s:sheetData/s:row', NS):
            cells = {}
            for c in row.findall('s:c', NS):
                v = c.find('s:v', NS)
                formula = c.find('s:f', NS)
                val = v.text if v is not None and v.text is not None else ''
                if c.get('t') == 's' and val:
                    val = shared[int(val)]
                elif c.get('t') == 'inlineStr':
                    val = ''.join(t.text or '' for t in c.findall('.//s:t', NS))
                if formula is not None:
                    val = '=' + (formula.text or '')
                if val != '':
                    cells[column(c.get('r'))] = val
            if cells:
                width = max(width, max(cells) + 1)
                rows.append((int(row.get('r')), cells))
        if rows:
            sheets.append({'name': sheet.get('name'), 'rows': [(n, [c.get(i, '') for i in range(width)]) for n, c in rows],
                           'merges': [e.get('ref') for e in root.findall('s:mergeCells/s:mergeCell', NS)]})
    return sheets

def image_map(z):
    base = 'xl/cellimages.xml'
    if base not in z.namelist():
        return {}
    mapping = rels(z, base)
    result = {}
    for pic in ET.fromstring(z.read(base)).findall('.//xdr:pic', NS):
        name = pic.find('xdr:nvPicPr/xdr:cNvPr', NS)
        blip = pic.find('.//a:blip', NS)
        if name is not None and blip is not None:
            target = mapping.get(blip.get('{'+NS['r']+'}embed'))
            if target in z.namelist():
                result[name.get('name')] = target
    return result

def escape(value):
    return str(value).replace('|', '&#124;').replace('\r', '').replace('\n', '<br>') or '—'

def refresh(workbook, output, as_of):
    data = workbook.read_bytes()
    refs = output / 'references'
    refs.mkdir(parents=True, exist_ok=True)
    lines = ['# 依柔工厂设备、工艺与配件离线资源', '',
             f'- 快照生成日期：{as_of}（读取日期，不代表库存盘点日期）',
             f'- 来源文件：`{workbook.as_posix()}`',
             f'- 来源 SHA256：`{hashlib.sha256(data).hexdigest()}`', '',
             '本地表格无法读取时直接使用本资源继续生成方案，并注明快照日期。原表空白以“—”表示，不代表零、不支持或无库存；字段原文保留，不自动补齐或纠正单位。图片来自工作簿内嵌图片，不是 AI 样品图。', '',
             '## 使用时需要核对的字段', '',
             '- 设计与 BOM 优先匹配合适的已有配件，注明配件编号、用途、颜色/规格、单套用量；库存数量与价格为空时标为待核实。',
             '- 未编号设备可以按设备名及来源行引用，不自行生成 YR 编号。机器工作范围不等于所有列出材料均适用于当前加工路径。',
             '- 设备参数、材料单位或规格含义异常时保留原值并标记待核实；可继续完成不依赖该参数的设计。', '',
             '## 数据目录', '']
    gallery = []
    counts = {}
    with ZipFile(workbook) as z:
        sheets = read_book(z)
        images = image_map(z)
        for sheet in sheets:
            counts[sheet['name']] = len(sheet['rows']) - 1
            lines.append(f"- {sheet['name']}：{counts[sheet['name']]} 条记录")
        for sheet in sheets:
            lines += ['', '## ' + sheet['name'], '']
            if sheet['merges']:
                lines += ['原表合并区域：' + '、'.join(sheet['merges']) + '。仅在这些区域内解释共享标题，其他空白不继承。', '']
            headers = sheet['rows'][0][1]
            lines += ['| 原表行 | ' + ' | '.join(escape(x) for x in headers) + ' |',
                      '|' + '---|' * (len(headers) + 1)]
            for n, values in sheet['rows'][1:]:
                rendered = list(values)
                for i, value in enumerate(values):
                    match = re.search(r'DISPIMG\("([^"]+)"', value)
                    if not match:
                        continue
                    target = images.get(match.group(1))
                    if target:
                        code = next((v for h, v in zip(headers, values) if h.strip() == '配件编号'), '')
                        label = next((v for h, v in zip(headers, values) if h.strip() == '配件名'), code)
                        key = re.sub(r'[^a-zA-Z0-9_-]', '_', code or match.group(1))
                        suffix = Path(target).suffix.lower()
                        dest = output / 'assets' / 'accessories' / (key + suffix)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(z.read(target))
                        link = '../assets/accessories/' + dest.name
                        rendered[i] = f'[配件图片]({link})'
                        gallery += [f'### {code} {label}', '', f'![{code} {label}]({link})', '']
                    else:
                        rendered[i] = value + '（图片未提取，不能据此推断外观）'
                lines.append('| ' + str(n) + ' | ' + ' | '.join(escape(v) for v in rendered) + ' |')
        if gallery:
            lines += ['', '## 配件图片索引', ''] + gallery
    (refs / 'factory-capabilities.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'records': counts, 'images': len(gallery)//4, 'as_of': as_of}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', required=True, type=Path)
    parser.add_argument('--output-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--as-of', required=True, help='Client date, YYYY-MM-DD')
    args = parser.parse_args()
    refresh(args.workbook.resolve(), args.output_root.resolve(), args.as_of)
