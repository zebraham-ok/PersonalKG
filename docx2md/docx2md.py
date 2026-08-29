#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
docx2md —— 将 Word (.docx/.doc) 高效批量转换为 Markdown，尽量保留原有格式。

特性
----
* 标题层级 Heading 1-6 → # ~ ######（含 outlineLvl / Title / Subtitle 样式）
* 行内格式：加粗、斜体、下划线、删除线、上标、下标、高亮、等宽字体(行内代码)
* 有序 / 无序 / 多级列表（按 Word 编号定义自动编号与缩进）
* 表格（GFM 风格，保留单元格行内格式，处理简单合并单元格）
* 图片提取（保存到 assets/<文档名>/ 并在 md 中引用）
* 超链接、连续代码段落合并为代码块（语言自动识别或手动指定）
* 引用样式段落 → 块引用
* 批量 / 递归目录 / 多线程并发
* 可选：Windows + Word COM 将 .doc 先转换为 .docx

用法
----
    python docx2md.py 文件.docx                        # 默认输出到 Files/（保持相对结构）
    python docx2md.py 目录/ --no-recursive
    python docx2md.py a.docx b.docx --out md/ --overwrite --jobs 4
    python docx2md.py 论文目录/ --recursive --meta
    python docx2md.py 目录/ --out Files/ --dedupe   # 转换后按内容自动去重

依赖
----
    pip install python-docx
    （可选，.doc 支持）pip install pywin32
"""

import argparse
import concurrent.futures
import os
import re
import sys
import threading
from pathlib import Path

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
except ImportError:
    print('缺少依赖 python-docx，请先安装：pip install python-docx', file=sys.stderr)
    sys.exit(1)

# Windows 中文控制台（cmd, 代码页 936）下 Python 默认即用 GBK 输出中文；
# 若在 UTF-8 终端下出现乱码，可取消下面两行的注释强制 UTF-8 输出。
# try:
#     if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
#         sys.stdout.reconfigure(encoding='utf-8', errors='replace')
# except Exception:
#     pass

MONO_FONTS = {
    'consolas', 'courier new', 'courier', 'monaco', 'menlo',
    'dejavu sans mono', 'source code pro', 'lucida console',
    'liberation mono', 'andale mono', 'ubuntu mono', 'fira code',
    'jetbrains mono', 'cascadia code', 'sf mono', 'operator mono',
    'inconsolata', 'droid sans mono',
}
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp',
              '.tif', '.tiff', '.emf', '.wmf'}


class RunFmt:
    """单个文本片段的行内格式。"""
    __slots__ = ('bold', 'italic', 'underline', 'strike', 'sup', 'sub',
                 'highlight', 'code', 'link')

    def __init__(self, bold=False, italic=False, underline=False, strike=False,
                 sup=False, sub=False, highlight=False, code=False, link=None):
        self.bold = bold
        self.italic = italic
        self.underline = underline
        self.strike = strike
        self.sup = sup
        self.sub = sub
        self.highlight = highlight
        self.code = code
        self.link = link

    def is_plain(self):
        return not (self.bold or self.italic or self.underline or self.strike
                    or self.sup or self.sub or self.highlight or self.code or self.link)

    def key(self):
        return (self.bold, self.italic, self.underline, self.strike,
                self.sup, self.sub, self.highlight, self.code, self.link)

    def __eq__(self, other):
        return isinstance(other, RunFmt) and self.key() == other.key()

    def __hash__(self):
        return hash(self.key())


def _sname(p):
    """返回 (样式名, 样式ID)。"""
    st = getattr(p, 'style', None)
    if st is None:
        return '', ''
    return (st.name or '').strip(), (st.style_id or '').strip()


def iter_block_items(doc):
    """按文档实际顺序产出 段落 / 表格（图片等内嵌在段落中）。"""
    body = doc.element.body
    for child in body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            yield Table(child, doc)


class Docx2Md:
    def __init__(self, opts):
        self.opts = opts
        self.lines = []
        self.code_buffer = []
        self.img_counter = 0
        self.ordered_counts = {}
        self.last_ordered_key = None
        self.doc = None
        self.stem = ''
        self.assets_dir = None
        self.assets_rel = Path('.')

    # ------------------------------------------------------------------
    # 文本与行内格式
    # ------------------------------------------------------------------
    @staticmethod
    def escape_text(s):
        s = s.replace('\\', '\\\\')
        s = s.replace('*', '\\*')
        s = s.replace('_', '\\_')
        s = s.replace('`', '\\`')
        s = s.replace('[', '\\[')
        s = s.replace(']', '\\]')
        return s

    @staticmethod
    def escape_cell_text(s):
        return Docx2Md.escape_text(s).replace('|', '\\|')

    def render_inline(self, text, fmt):
        if fmt.code:
            return f'`{text}`'
        if fmt.link:
            return f'[{text}]({fmt.link})'
        pre, post = '', ''
        if fmt.highlight:
            pre += '<mark>'
            post = '</mark>' + post
        if fmt.underline:
            pre += '<u>'
            post = '</u>' + post
        if fmt.sup:
            pre += '<sup>'
            post = '</sup>' + post
        if fmt.sub:
            pre += '<sub>'
            post = '</sub>' + post
        if fmt.bold and fmt.italic:
            pre += '***'
            post = '***' + post
        elif fmt.bold:
            pre += '**'
            post = '**' + post
        elif fmt.italic:
            pre += '*'
            post = '*' + post
        if fmt.strike:
            pre += '~~'
            post = '~~' + post
        return pre + text + post

    def render_text_items(self, items, escape_fn=None):
        if escape_fn is None:
            escape_fn = self.escape_text
        merged = self.merge_items(items)
        out = []
        for kind, payload, fmt in merged:
            if kind == 'image':
                rel = (self.assets_rel / payload).as_posix()
                out.append(f'![{payload}]({rel})')
            elif kind == 'text':
                text = payload
                if not fmt.code:
                    text = escape_fn(text)
                out.append(self.render_inline(text, fmt))
            else:  # 换行
                out.append('<br>')
        return ''.join(out)

    @staticmethod
    def merge_items(items):
        """合并相邻且格式相同的文本片段，减少冗余标记。"""
        out = []
        for kind, payload, fmt in items:
            if kind == 'text' and out and out[-1][0] == 'text' and out[-1][2] == fmt:
                out[-1][1] += payload
            else:
                out.append([kind, payload, fmt])
        return out

    # ------------------------------------------------------------------
    # 段落类型判定
    # ------------------------------------------------------------------
    def get_heading_level(self, p):
        name, sid = _sname(p)
        m = re.match(r'^(heading|标题)\s*(\d+)$', name, re.I)
        if m:
            return max(1, min(int(m.group(2)), 6))
        m2 = re.match(r'^heading(\d+)$', sid, re.I)
        if m2:
            return max(1, min(int(m2.group(1)), 6))
        if name.lower() in ('title', '标题'):
            return 1
        if name.lower() in ('subtitle', '副标题'):
            return 2
        pPr = p._element.pPr
        if pPr is not None:
            ol = pPr.find(qn('w:outlineLvl'))
            if ol is not None and ol.get(qn('w:val')) is not None:
                try:
                    v = int(ol.get(qn('w:val')))
                except ValueError:
                    v = -1
                if 0 <= v <= 8:
                    return v + 1
        return None

    def is_quote(self, p):
        name, sid = _sname(p)
        low = (name + ' ' + sid).lower()
        return any(k in low for k in ('quote', 'blockquote', '引用', '引文'))

    def is_code_paragraph(self, p):
        name, sid = _sname(p)
        low = (name + ' ' + sid).lower()
        if any(k in low for k in ('source code', 'html preformatted',
                                  'preformatted', 'code block', '代码')):
            return True
        runs = [r for r in p.runs if r.text.strip()]
        if not runs:
            return False
        # 整段全部为等宽字体的段落视为代码块（与正文混排的等宽片段走行内 code）
        return all(self._is_mono(r) for r in runs)

    @staticmethod
    def _is_mono(r):
        """判断 run 是否使用等宽字体。兼容 Run 对象与 w:r XML 元素。"""
        if hasattr(r, 'font'):
            name = r.font.name
        else:
            rPr = r.find(qn('w:rPr'))
            if rPr is None:
                return False
            rFonts = rPr.find(qn('w:rFonts'))
            if rFonts is None:
                return False
            name = rFonts.get(qn('w:ascii')) or rFonts.get(qn('w:hAnsi')) or ''
        if not name:
            return False
        name = name.strip().strip('"').strip("'").lower()
        return name in MONO_FONTS

    # ------------------------------------------------------------------
    # 列表
    # ------------------------------------------------------------------
    def get_list_info(self, p):
        """识别列表项，返回 (ilvl, numId, fmt) 或 None。"""
        pPr = p._element.pPr
        numPr = pPr.find(qn('w:numPr')) if pPr is not None else None
        numId = ilvl = 0
        if numPr is not None:
            numId_el = numPr.find(qn('w:numId'))
            ilvl_el = numPr.find(qn('w:ilvl'))
            numId = int(numId_el.get(qn('w:val')) or 0) if numId_el is not None else 0
            ilvl = int(ilvl_el.get(qn('w:val')) or 0) if ilvl_el is not None else 0
        name, sid = _sname(p)
        low = (name + '|' + sid).lower()
        style_bullet = 'list bullet' in low or 'listbullet' in low
        style_number = 'list number' in low or 'listnumber' in low
        if numId == 0 and not (style_bullet or style_number):
            return None
        if numId == 0:
            # numPr 在样式定义中（如 List Bullet / List Number），从样式名取层级
            m = re.search(r'list\s*(bullet|number)\s*(\d+)?', low)
            if m and m.group(2):
                ilvl = int(m.group(2)) - 1
            fmt = 'decimal' if style_number else 'bullet'
        else:
            fmt = self.num_fmt(numId, ilvl)
            if fmt is None:
                fmt = 'decimal' if style_number else 'bullet'
        return ilvl, numId, fmt

    def num_fmt(self, numId, ilvl):
        """读取编号定义，返回 'decimal' / 'bullet' / 其他。"""
        try:
            numbering = self.doc.part.numbering_part.element
        except Exception:
            return None
        a_num_id = None
        for num in numbering.findall(qn('w:num')):
            if num.get(qn('w:numId')) == str(numId):
                aid = num.find(qn('w:abstractNumId'))
                if aid is not None:
                    a_num_id = aid.get(qn('w:val'))
                break
        if a_num_id is None:
            return None
        for absnum in numbering.findall(qn('w:abstractNum')):
            if absnum.get(qn('w:abstractNumId')) == a_num_id:
                for lvl in absnum.findall(qn('w:lvl')):
                    if lvl.get(qn('w:ilvl')) == str(ilvl):
                        nf = lvl.find(qn('w:numFmt'))
                        if nf is not None:
                            return nf.get(qn('w:val'))
                break
        return None

    # ------------------------------------------------------------------
    # run / 超链接 / 图片
    # ------------------------------------------------------------------
    def iter_inline(self, p):
        """按 XML 顺序产出 ('text', text, fmt) / ('image', fname, None)。"""
        for child in p._element.iterchildren():
            tag = child.tag
            if tag == qn('w:r'):
                text = self._run_text(child)
                if text:
                    yield ('text', text, self._run_fmt(child))
                # 图片可能直接内嵌在 run 中（add_picture 常见形态）
                if not self.opts.no_images:
                    for dtag in (qn('w:drawing'), qn('w:pict')):
                        for d in child.findall(dtag):
                            for fname in self._extract_images(d):
                                yield ('image', fname, None)
            elif tag == qn('w:hyperlink'):
                url = self._hyperlink_url(p, child)
                text, fmt = '', RunFmt()
                for r in child.findall(qn('w:r')):
                    t = self._run_text(r)
                    if t:
                        text += t
                        if fmt.is_plain():
                            fmt = self._run_fmt(r)
                if text:
                    fmt.link = url
                    yield ('text', text, fmt)
            elif tag in (qn('w:drawing'), qn('w:pict')) and not self.opts.no_images:
                for fname in self._extract_images(child):
                    yield ('image', fname, None)

    @staticmethod
    def _run_text(r):
        parts = []
        for node in r.iterchildren():
            if node.tag == qn('w:t'):
                parts.append(node.text or '')
            elif node.tag == qn('w:br'):
                parts.append('<br>')
            elif node.tag == qn('w:tab'):
                parts.append('    ')
            elif node.tag == qn('w:noBreakHyphen'):
                parts.append('-')
        return ''.join(parts)

    def _run_fmt(self, r):
        """从 w:r 的 rPr 解析行内格式（r 为 CT_R 元素）。"""
        rPr = r.find(qn('w:rPr'))

        def _on(prop):
            if rPr is None:
                return False
            el = rPr.find(qn(prop))
            if el is None:
                return False
            val = el.get(qn('w:val'))
            return val not in ('0', 'false', 'off', 'none')

        sup = sub = False
        hl = None
        if rPr is not None:
            va = rPr.find(qn('w:vertAlign'))
            if va is not None:
                v = va.get(qn('w:val'))
                sup = v == 'superscript'
                sub = v == 'subscript'
            hl_el = rPr.find(qn('w:highlight'))
            if hl_el is not None:
                hl = None if hl_el.get(qn('w:val')) == 'none' else True

        return RunFmt(bold=_on('w:b'), italic=_on('w:i'),
                      underline=_on('w:u'), strike=_on('w:strike'),
                      sup=sup, sub=sub, highlight=hl is not None,
                      code=self._is_mono(r))

    def _hyperlink_url(self, p, hl):
        rel_id = hl.get(qn('r:id'))
        if rel_id:
            try:
                return p.part.rels[rel_id].target_ref
            except KeyError:
                return ''
        anchor = hl.get(qn('w:anchor'))
        return '#' + anchor if anchor else ''

    def _extract_images(self, el):
        out = []
        for blip in el.iter(qn('a:blip')):
            rid = blip.get(qn('r:embed'))
            if not rid:
                continue
            try:
                part = self.doc.part.related_parts[rid]
            except KeyError:
                continue
            self.img_counter += 1
            ext = Path(part.partname).suffix.lower()
            if ext not in IMAGE_EXTS:
                ext = '.png'
            fname = f'{self.stem}_img{self.img_counter:04d}{ext}'
            if self.assets_dir is not None:
                (self.assets_dir / fname).write_bytes(part.blob)
            out.append(fname)
        return out

    # ------------------------------------------------------------------
    # 段落渲染
    # ------------------------------------------------------------------
    def flush_code(self):
        if self.code_buffer:
            lang = self.opts.code_lang or self.guess_lang('\n'.join(self.code_buffer))
            self.lines.append('```' + lang)
            self.lines.extend(self.code_buffer)
            self.lines.append('```')
            self.code_buffer = []

    @staticmethod
    def guess_lang(text):
        if re.search(r'^\s*(import |from |def |class |print\(|if __name__)', text, re.M):
            return 'python'
        if re.search(r'^\s*(function |const |let |var |console\.log|export )', text, re.M):
            return 'javascript'
        if re.search(r'^\s*(#include|int |void |printf\(|return 0;)', text, re.M):
            return 'c'
        if re.search(r'^\s*(SELECT |INSERT INTO|CREATE TABLE)', text, re.I | re.M):
            return 'sql'
        return ''

    def append_blank(self):
        if self.lines and self.lines[-1] != '':
            self.lines.append('')

    @staticmethod
    def fix_line_start(text):
        """转义行首可能被误解析为列表/标题/引用的字符。"""
        m = re.match(r'^(\s*)([-+*#>]|\d{1,3}[.)])(\s|$)', text)
        if m:
            return text[:m.start(2)] + '\\' + m.group(2) + text[m.end(2):]
        return text

    def append_img_line(self, name):
        rel = (self.assets_rel / name).as_posix()
        self.lines.append(f'![{name}]({rel})')

    def render_paragraph(self, p):
        items = list(self.iter_inline(p))
        images = [n for k, n, _ in items if k == 'image']
        texts = [x for x in items if x[0] != 'image']
        text = self.render_text_items(texts) if texts else ''

        hlevel = self.get_heading_level(p)
        if hlevel:
            self.flush_code()
            self.last_ordered_key = None
            self.lines.append('#' * hlevel + (' ' + text if text else ''))
            for n in images:
                self.append_img_line(n)
            return

        if self.is_code_paragraph(p):
            # 代码段落：保留原始文本（不做行内转义/内联标记）
            raw_parts = []
            for node in p._element.iter():
                if node.tag == qn('w:t'):
                    raw_parts.append(node.text or '')
                elif node.tag == qn('w:br'):
                    raw_parts.append('\n')
                elif node.tag == qn('w:tab'):
                    raw_parts.append('\t')
            raw = ''.join(raw_parts).rstrip('\n')
            if raw:
                self.code_buffer.append(raw)
            return

        self.flush_code()
        li = self.get_list_info(p)
        if li:
            ilvl, numId, fmt = li
            indent = '    ' * ilvl
            if fmt == 'decimal':
                key = (numId, ilvl)
                if key == self.last_ordered_key:
                    self.ordered_counts[key] += 1
                else:
                    self.ordered_counts[key] = 1
                self.last_ordered_key = key
                marker = f'{self.ordered_counts[key]}. '
            else:
                self.last_ordered_key = None
                marker = '- '
            self.lines.append(indent + marker + text)
            for n in images:
                self.append_img_line(n)
            return

        self.last_ordered_key = None
        if self.is_quote(p) and text:
            self.lines.append('> ' + text)
        elif text:
            self.lines.append(self.fix_line_start(text))
        elif not images:
            self.append_blank()
        for n in images:
            self.append_img_line(n)

    # ------------------------------------------------------------------
    # 表格
    # ------------------------------------------------------------------
    def _is_vmerge_continue(self, cell):
        tcPr = cell._tc.find(qn('w:tcPr'))
        if tcPr is None:
            return False
        vm = tcPr.find(qn('w:vMerge'))
        if vm is None:
            return False
        return vm.get(qn('w:val')) != 'restart'

    def cell_text(self, cell):
        parts = []
        for p in cell.paragraphs:
            items = list(self.iter_inline(p))
            imgs = [f'[图片: {n}]' for k, n, _ in items if k == 'image']
            texts = [x for x in items if x[0] != 'image']
            t = self.render_text_items(texts, escape_fn=self.escape_cell_text)
            if t:
                parts.append(t)
            parts.extend(imgs)
        return ' <br> '.join(p for p in parts if p)

    def render_table(self, table):
        self.flush_code()
        self.last_ordered_key = None
        rows, ncols = [], 0
        seen_tc = set()
        for row in table.rows:
            cells, prev_tc = [], None
            for cell in row.cells:
                tc = cell._tc
                if tc is prev_tc:
                    continue  # 水平合并（gridspan）
                prev_tc = tc
                if tc in seen_tc and self._is_vmerge_continue(cell):
                    cells.append('')
                    continue
                seen_tc.add(tc)
                cells.append(self.cell_text(cell))
            ncols = max(ncols, len(cells))
            rows.append(cells)
        if not rows:
            return
        rows = [r + [''] * (ncols - len(r)) for r in rows]
        self.lines.append('')
        self.lines.append('| ' + ' | '.join(rows[0]) + ' |')
        self.lines.append('| ' + ' | '.join(['---'] * ncols) + ' |')
        for r in rows[1:]:
            self.lines.append('| ' + ' | '.join(r) + ' |')
        self.lines.append('')

    # ------------------------------------------------------------------
    # 文档级转换
    # ------------------------------------------------------------------
    def build_front_matter(self):
        cp = self.doc.core_properties
        fm = ['---']
        if cp.title:
            fm.append(f'title: "{cp.title}"')
        if cp.author:
            fm.append(f'author: "{cp.author}"')
        if cp.created:
            fm.append(f'date: "{cp.created.isoformat()}"')
        fm.append('---')
        return '\n'.join(fm)

    def convert(self, docx_path, md_path, stem=None):
        self.doc = Document(str(docx_path))
        self.stem = stem or Path(docx_path).stem
        md_path = Path(md_path)
        if not self.opts.no_images:
            self.assets_dir = md_path.parent / self.opts.assets / self.stem
            self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.assets_rel = Path(self.opts.assets) / self.stem

        if self.opts.meta:
            fm = self.build_front_matter()
            if fm:
                self.lines.append(fm)
                self.lines.append('')

        for block in iter_block_items(self.doc):
            if isinstance(block, Paragraph):
                self.render_paragraph(block)
            else:
                self.render_table(block)

        self.flush_code()
        while self.lines and self.lines[-1] == '':
            self.lines.pop()
        return '\n'.join(self.lines) + '\n'


# ----------------------------------------------------------------------
# 批量处理
# ----------------------------------------------------------------------
def collect_files(paths, recursive=True):
    out = []
    for p in paths:
        p = Path(p).expanduser()
        if p.is_dir():
            out.extend(p.glob('**/*.docx' if recursive else '*.docx'))
            out.extend(p.glob('**/*.doc' if recursive else '*.doc'))
        elif p.is_file() and p.suffix.lower() in ('.docx', '.doc'):
            out.append(p)
        else:
            print(f'警告：跳过（不存在或不是 Word 文件）：{p}', file=sys.stderr)
    seen, uniq = set(), []
    for f in sorted(out):
        if f.name.startswith('~$'):
            continue  # Word 打开时的临时锁文件，跳过
        try:
            if f.stat().st_size == 0:
                print(f'[跳过] 空文件（0B，可能为快捷方式/损坏）: {f}',
                      file=sys.stderr)
                continue
        except OSError:
            continue
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def norm_text(t):
    """内容归一化：去掉全部空白后比较（用于判定重复条目）。"""
    return ''.join((t or '').split())


class DedupeIndex:
    """按归一化内容索引已有 md（线程安全）。

    用途：转换完成后，若生成的内容与 --out 目录（或 Files/）中已有 md
    相同（说明同一文档被重复导入），自动删除刚生成的 md 并跳过，
    避免重复条目。文件名（stem）不同的同内容文档同样被判定为重复。
    """

    def __init__(self, out_dir):
        self._lock = threading.Lock()
        self._hashes = {}
        if out_dir:
            for f in Path(out_dir).rglob('*.md'):
                try:
                    h = norm_text(f.read_text(encoding='utf-8', errors='replace'))
                except OSError:
                    continue
                if h:
                    self._hashes.setdefault(h, str(f))

    def check(self, text, self_path):
        """返回与 text 内容相同的既有 md 路径；无则登记 self_path 并返回 None。"""
        h = norm_text(text)
        if not h:
            return None
        with self._lock:
            hit = self._hashes.get(h)
            if hit is None:
                self._hashes[h] = str(self_path)
            return hit


def common_base(paths):
    """返回输入文件的公共父目录（用于 --out 时保持相对结构）。"""
    parts = [list(p.resolve().parts) for p in paths]
    common = []
    for items in zip(*parts):
        if len(set(items)) == 1:
            common.append(items[0])
        else:
            break
    if not common:
        return Path.cwd()
    base = Path(*common)
    # 仅一个输入文件时公共前缀会落到文件本身，退回其父目录
    if base.is_file():
        return base.parent
    return base


def doc_to_docx(src):
    """用 Word COM 将 .doc 转为临时 .docx（Windows + 已安装 Microsoft Word）。"""
    try:
        import win32com.client
        import pythoncom
    except ImportError as e:
        raise RuntimeError(f'需要 pywin32（pip install pywin32）才能转换 .doc: {e}')
    pythoncom.CoInitialize()
    import tempfile
    tmp = Path(tempfile.mktemp(prefix='docx2md_', suffix='.docx'))
    word = win32com.client.DispatchEx('Word.Application')
    word.Visible = False
    try:
        d = word.Documents.Open(str(src.resolve()))
        d.SaveAs2(str(tmp), FileFormat=16)  # 16 = wdFormatXMLDocument
        d.Close(False)
    finally:
        word.Quit()
        pythoncom.CoUninitialize()
    return tmp


def convert_one(src, opts, base, dedupe=None):
    src = Path(src)
    tmp_docx = None
    if src.suffix.lower() == '.doc':
        if not opts.doc2docx:
            return 'skip_doc', src, None
        tmp_docx = doc_to_docx(src)
        work, out_stem = tmp_docx, src.stem
    else:
        work, out_stem = src, None
    try:
        if opts.out:
            try:
                rel = src.resolve().relative_to(base.resolve())
            except ValueError:
                rel = Path(src.name)
            md = (Path(opts.out) / rel).with_suffix('.md')
        else:
            md = src.with_suffix('.md')
        if md.exists() and not opts.overwrite:
            return 'skip', src, md
        c = Docx2Md(opts)
        text = c.convert(work, md, stem=out_stem)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(text, encoding='utf-8')
        if dedupe is not None:
            hit = dedupe.check(text, md)
            if hit is not None and Path(hit) != md:
                try:
                    md.unlink(missing_ok=True)
                except OSError:
                    pass
                return 'dup', src, Path(hit)
        return 'ok', src, md
    finally:
        if tmp_docx is not None:
            try:
                tmp_docx.unlink(missing_ok=True)
            except OSError:
                pass


def _report(status, src, md):
    if status == 'ok':
        print(f'[完成] {src} -> {md}')
    elif status == 'skip':
        print(f'[跳过] 已存在: {md}（加 --overwrite 强制重转）')
    elif status == 'dup':
        print(f'[去重] 内容与既有条目重复，已丢弃: {src} == {md}')
    else:
        print(f'[跳过] 旧格式 .doc: {src}')


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='docx2md',
        description='将 Word (.docx/.doc) 批量转换为 Markdown，尽量保留原有格式。')
    ap.add_argument('paths', nargs='+', help='要转换的 .docx/.doc 文件或目录')
    ap.add_argument('--out', metavar='DIR', default='Files',
                    help='输出目录（默认当前目录下的 Files，保持源文件的相对结构；'
                         '可用 --out 指定任意目录）')
    ap.add_argument('--assets', default='assets', help='图片存放子目录名（默认 assets）')
    ap.add_argument('--jobs', type=int, default=0, help='并发转换数（默认按 CPU 自动）')
    ap.add_argument('--no-recursive', action='store_true', help='目录只扫描顶层，不递归子目录')
    ap.add_argument('--overwrite', action='store_true', help='覆盖已存在的 .md 文件')
    ap.add_argument('--no-images', action='store_true', help='不提取图片')
    ap.add_argument('--meta', action='store_true', help='输出 YAML front matter（标题/作者/日期）')
    ap.add_argument('--code-lang', default='', help='代码块语言标记（默认自动识别）')
    ap.add_argument('--doc2docx', action='store_true',
                    help='用 Word COM 将 .doc 先转为 .docx（Windows + 已安装 Word）')
    ap.add_argument('--dedupe', action='store_true',
                    help='转换后按内容与 --out 下既有 md 去重：内容相同则删除并跳过'
                         '（自动排除重复条目，含同名不同路径）')
    ap.add_argument('--verbose', action='store_true', help='打印额外信息')
    args = ap.parse_args(argv)

    if args.jobs <= 0:
        args.jobs = min(4, os.cpu_count() or 1)

    files = collect_files(args.paths, recursive=not args.no_recursive)
    if not files:
        print('未找到任何 .docx/.doc 文件。')
        return 1

    doc_files = [f for f in files if f.suffix.lower() == '.doc']
    if doc_files and not args.doc2docx:
        print(f'提示：发现 {len(doc_files)} 个 .doc 旧格式文件，已跳过'
              f'（加 --doc2docx 自动转换，或先用 Word 另存为 .docx）')
        if args.verbose:
            for f in doc_files[:10]:
                print('  ', f)
    work = files if (args.doc2docx or not doc_files) else [f for f in files if f.suffix.lower() == '.docx']

    # Word COM 不适合多线程并发：.doc（走 doc_to_docx）串行处理，.docx 可并发
    if args.doc2docx:
        doc_work = sorted(f for f in work if f.suffix.lower() == '.doc')
        docx_work = sorted(f for f in work if f.suffix.lower() != '.doc')
    else:
        doc_work, docx_work = [], work

    base = common_base(work) if args.out else None
    dedupe = DedupeIndex(Path(args.out) if args.out else None) if args.dedupe else None
    ok = skip = dup = failed = 0
    errors = []

    def _run(src, args_, base_, dedupe_):
        nonlocal ok, skip, dup, failed
        try:
            status, s, md = convert_one(src, args_, base_, dedupe=dedupe_)
        except Exception as e:
            failed += 1
            errors.append((src, e))
            return
        _report(status, s, md)
        ok += status == 'ok'
        dup += status == 'dup'
        skip += status not in ('ok', 'dup')

    # .doc 串行
    for src in doc_work:
        _run(src, args, base, dedupe)

    # .docx 并发（无 docx 或不足则退化为串行）
    if not docx_work or len(docx_work) <= 1 or args.jobs <= 1:
        for src in docx_work:
            _run(src, args, base, dedupe)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futures = {ex.submit(convert_one, src, args, base, dedupe=dedupe):
                       src for src in docx_work}
            for fut in concurrent.futures.as_completed(futures):
                src = futures[fut]
                try:
                    status, s, md = fut.result()
                except Exception as e:
                    failed += 1
                    errors.append((src, e))
                    continue
                _report(status, s, md)
                ok += status == 'ok'
                dup += status == 'dup'
                skip += status not in ('ok', 'dup')

    print(f'汇总：成功 {ok}，去重 {dup}，跳过 {skip}，失败 {failed}'
          f'（共 {len(work)}）')
    for src, e in errors:
        print(f'  失败: {src}: {e}', file=sys.stderr)
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
