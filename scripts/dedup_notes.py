#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dedup_notes.py —— 检查并去除 Neo4j 中的重复 Note 节点。

判据（确定重复，直接删除多余项，每组保留一个）：
1. md_path 路径变体：Windows 大小写不敏感 / 相对 vs 绝对形式混用
   （同一磁盘文件对应两个 Note 节点）
2. content 归一化后完全相同（同一文档被重复导入）

仅报告不删除：
3. title 相同但 content 不同（可能是同名不同篇，需人工判断）

用法：
    python dedup_notes.py          # dry-run：只列出将被删除的节点
    python dedup_notes.py --apply  # 实际删除（每组保留一个，DETACH DELETE）

保留规则（按优先级）：
    md_path 对应磁盘文件存在 > 有 qwen_embedding 向量 >
    有 content 且字数多 > 星级高
"""
import sys
from pathlib import Path
from collections import defaultdict

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HERE = Path(__file__).resolve().parent            # code/scripts
CODE = HERE.parent                                # code
sys.path.insert(0, str(CODE))
SCRIPTS = HERE if (HERE / 'neo4j_kg.py').is_file() else (
    Path.home() / '.codebuddy' / 'skills' / 'md-index' / 'scripts')
sys.path.insert(0, str(SCRIPTS))

from neo4j_kg import PersonalKG, norm_path  # noqa: E402
from API import secret_manager              # noqa: E402

FILES_DIR = Path(CODE).parent / 'Files'


def canon_path(p):
    """路径规范化用于比较：相对路径基于 Files/ 补全，统一小写。"""
    p = (p or '').strip()
    if not p:
        return ''
    if not Path(p).is_absolute():
        p = str(FILES_DIR / p)
    return norm_path(p).lower()


def norm_text(t):
    """content 归一化：去掉所有空白后比较。"""
    return ''.join((t or '').split())


class UF:
    """并查集：合并来自不同判据的重叠重复组。"""

    def __init__(self, nodes):
        self.parent = {id(n): id(n) for n in nodes}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(id(a)), self.find(id(b))
        if ra != rb:
            self.parent[rb] = ra


def depth_of(p):
    """Files/ 下的目录深度：Files/政治/x.md -> 2, Files/x.md -> 1。"""
    try:
        return len(Path(p).relative_to(FILES_DIR).parts)
    except ValueError:
        return 0


def pick_keep(nodes):
    """每组保留一个：磁盘文件存在 > 主题子目录(深度大) > 有向量 >
    有内容且字数多 > 星级高。"""
    if not nodes:
        return None

    def score(n):
        p = n.get('md_path') or ''
        on_disk = Path(p).is_file()
        return (on_disk, depth_of(p), bool(n.get('qwen_embedding')),
                bool((n.get('content') or '').strip()),
                n.get('word_count') or 0, n.get('stars') or 0)

    best = nodes[0]
    bs = score(best)
    for n in nodes[1:]:
        s = score(n)
        if s > bs:
            best, bs = n, s
    return best


def main():
    apply = '--apply' in sys.argv
    secrets = secret_manager.read_secrets_from_env()
    kg = PersonalKG(
        uri=secrets.get('local_neo4j_url', 'bolt://localhost:7687'),
        user=secrets.get('local_neo4j_username', 'neo4j'),
        password=secrets.get('local_neo4j_password', ''),
        files_dir=str(FILES_DIR))
    rows = kg.run(
        "MATCH (n:Note) OPTIONAL MATCH (n)-[:ON]->(s:Subject) "
        "WITH n, collect(s.name) AS subjects "
        "RETURN n{.*, subjects: subjects} AS note")
    notes = [r['note'] for r in rows]
    print(f'共 {len(notes)} 个 Note 节点\n')

    # ---------- 判据 1：md_path 变体 ----------
    case_map = defaultdict(list)
    for n in notes:
        case_map[canon_path(n.get('md_path'))].append(n)
    case_dups = [v for v in case_map.values() if len(v) > 1]
    print(f'[路径变体重复] {len(case_dups)} 组')

    # ---------- 判据 2：content 完全相同 ----------
    content_map = defaultdict(list)
    for n in notes:
        c = norm_text(n.get('content'))
        if c:
            content_map[c].append(n)
    content_dups = [v for v in content_map.values() if len(v) > 1]
    print(f'[内容完全重复] {len(content_dups)} 组\n')

    # ---------- 合并重叠组 ----------
    dup_nodes = []
    for g in case_dups + content_dups:
        dup_nodes.extend(g)
    uf = UF(dup_nodes)
    for g in case_dups + content_dups:
        for i in range(1, len(g)):
            uf.union(g[0], g[i])
    clusters = defaultdict(list)
    for n in dup_nodes:
        clusters[uf.find(id(n))].append(n)
    clusters = sorted(clusters.values(), key=lambda c: -len(c))

    # ---------- title 相同但内容不同（仅报告） ----------
    title_map = defaultdict(list)
    for n in notes:
        t = (n.get('title') or '').strip()
        if t:
            title_map[t].append(n)
    title_only = [
        v for v in title_map.values()
        if len(v) > 1 and len({norm_text(x.get('content')) for x in v}) > 1
    ]

    if not clusters:
        print('未发现确定重复的 Note，无需删除。')
    else:
        print(f'合并后共 {len(clusters)} 组确定重复，将删除 '
              f'{sum(len(c) - 1 for c in clusters)} 个节点'
              f'及对应磁盘 md 文件：\n')
        for c in clusters:
            keep = pick_keep(c)
            print(f'── 组（{len(c)} 个）保留:')
            print(f'    KEEP {keep.get("md_path")}'
                  f'  [{keep.get("title")}]'
                  f'（字数 {keep.get("word_count")}, '
                  f'向量 {"有" if keep.get("qwen_embedding") else "无"}, '
                  f'磁盘文件 {"存在" if Path(keep.get("md_path") or "").is_file() else "缺失"}）')
            for n in c:
                if n is keep:
                    continue
                p = n.get('md_path') or ''
                disk = '存在' if Path(p).is_file() else '缺失'
                print(f'    DEL  {p}'
                      f'  [{n.get("title")}]'
                      f'（字数 {n.get("word_count")}, '
                      f'向量 {"有" if n.get("qwen_embedding") else "无"}, '
                      f'磁盘文件 {disk}）')
            print()

    if title_only:
        print(f'[提示] {len(title_only)} 组 title 相同但内容不同（未自动删除，请人工判断）：')
        for v in title_only[:20]:
            print(f'  · {v[0].get("title")}: '
                  + ' | '.join(n.get("md_path") for n in v))
        if len(title_only) > 20:
            print(f'  … 其余 {len(title_only) - 20} 组略')

    if not apply:
        print('\n[dry-run] 未执行删除。确认无误后运行: python dedup_notes.py --apply')
        return

    # ---------- 实际删除 ----------
    deleted, del_disk, failed, skipped_disk = [], [], [], []
    for c in clusters:
        keep = pick_keep(c)
        for n in c:
            if n is keep:
                continue
            md = n.get('md_path') or ''
            try:
                kg.delete_note(md)
                deleted.append(md)
            except Exception as e:  # noqa: BLE001
                failed.append((md, str(e)))
                continue
            # 磁盘上重复 md 文件：与保留文件内容一致才删除（防止误删）
            kp = keep.get('md_path') or ''
            if md and Path(md).is_file() and kp and Path(kp).is_file():
                try:
                    if norm_text(Path(md).read_text(encoding='utf-8',
                                                    errors='replace')) == \
                       norm_text(Path(kp).read_text(encoding='utf-8',
                                                    errors='replace')):
                        Path(md).unlink()
                        del_disk.append(md)
                    else:
                        skipped_disk.append(md)
                except Exception as e:  # noqa: BLE001
                    skipped_disk.append(f'{md} ({e})')
    print(f'\n删除完成：Neo4j 节点成功 {len(deleted)} 个，失败 {len(failed)} 个')
    print(f'磁盘 md 文件已删除 {len(del_disk)} 个，跳过（内容不一致/读取失败）'
          f'{len(skipped_disk)} 个')
    for p, e in failed:
        print(f'  [节点失败] {p}: {e}')
    for p in skipped_disk:
        print(f'  [磁盘未删] {p}')


if __name__ == '__main__':
    main()
