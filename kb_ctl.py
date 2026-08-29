#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""个人知识库（前端 + 后端）一键启动/停止/状态管理（Windows）。

用法:
    python kb_ctl.py start      # 开发模式：检查 Neo4j → 启动后端(8000) + 前端(5173)
    python kb_ctl.py stop       # 停止前端与后端进程
    python kb_ctl.py restart    # 先 stop 再 start（开发模式）
    python kb_ctl.py prod       # 生产模式：仅启动后端(8000)，托管 frontend/dist
    python kb_ctl.py status     # 查看各组件状态
    python kb_ctl.py open       # 用默认浏览器打开前端页面
"""
import os
import re
import socket
import subprocess
import sys
import time

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(CODE_DIR, 'frontend')
BACKEND_LOG = os.path.join(CODE_DIR, '_backend.log')
FRONTEND_LOG = os.path.join(FRONTEND_DIR, '_frontend.log')

NEO4J_PORT = 7687
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

DETACHED = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


def port_open(port, host='localhost', timeout=1.0):
    """尝试 host 的 IPv4/IPv6 全部解析结果，任一可连即视为在线。"""
    try:
        infos = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError:
        return False
    for af, socktype, proto, _, sa in infos:
        try:
            with socket.socket(af, socktype, proto) as s:
                s.settimeout(timeout)
                if s.connect_ex(sa) == 0:
                    return True
        except OSError:
            continue
    return False


def find_pids(port):
    """用 netstat 解析占用端口的 PID 列表。"""
    try:
        out = subprocess.run(['netstat', '-ano'],
                             capture_output=True, text=True).stdout
    except OSError:
        return []
    pids = []
    for line in out.splitlines():
        if 'LISTENING' not in line:
            continue
        m = re.search(r':%d\s+\S+\s+LISTENING\s+(\d+)' % port, line)
        if m and m.group(1) not in pids:
            pids.append(m.group(1))
    return [int(p) for p in pids]


def kill_pids(pids):
    for pid in pids:
        r = subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f'  [OK] 已终止 PID {pid}')
        else:
            msg = (r.stderr or r.stdout or '').strip()
            print(f'  [!!] PID {pid} 终止失败: {msg}')


def _spawn(cmd, cwd, logfile, label, port):
    with open(logfile, 'ab') as log:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=DETACHED, close_fds=True)
    print(f'[{label}] 已启动 PID {p.pid}，日志: {logfile}')
    for _ in range(40):  # 最多等 20 秒
        if port_open(port):
            break
        time.sleep(0.5)
    if port_open(port):
        print(f'[{label}] 就绪 (http://localhost:{port})')
        return True
    print(f'[{label}] 启动超时/失败，请查看日志: {logfile}')
    return False


def cmd_start(prod=False):
    print('=== 1/3 检查 Neo4j ===')
    if port_open(NEO4J_PORT, '127.0.0.1'):
        print('  Neo4j 在线')
    else:
        print('  Neo4j 未在线！请先启动：')
        print('    命令:  neo4j console')
        print('    或:    Neo4j Desktop 打开数据库')
        print('  （数据库在线后再运行 start）')
        return 1

    print('=== 2/3 后端 (8000) ===')
    if port_open(BACKEND_PORT):
        print('  后端已在运行，跳过')
    elif not _spawn([sys.executable, '-m', 'uvicorn', 'backend.main:app',
                     '--port', str(BACKEND_PORT)],
                    CODE_DIR, BACKEND_LOG, '后端', BACKEND_PORT):
        return 1

    if not prod:
        print('=== 3/3 前端 (5173) ===')
        if port_open(FRONTEND_PORT):
            print('  前端已在运行，跳过')
        elif not _spawn(['npm.cmd', 'run', 'dev'],
                        FRONTEND_DIR, FRONTEND_LOG, '前端', FRONTEND_PORT):
            return 1

    print()
    if prod:
        print('生产模式就绪，请访问: http://localhost:8000')
    else:
        print('全部就绪，请访问: http://localhost:5173  (开发模式，/api 自动代理到 8000)')
    return 0


def cmd_stop():
    for name, port in [('前端(5173)', FRONTEND_PORT), ('后端(8000)', BACKEND_PORT)]:
        pids = find_pids(port)
        if not pids:
            print(f'[{name}] 无进程在运行')
        else:
            print(f'[{name}] 发现进程 PID {pids}，正在终止...')
            kill_pids(pids)
    time.sleep(1)
    for name, port in [('前端(5173)', FRONTEND_PORT), ('后端(8000)', BACKEND_PORT)]:
        if port_open(port):
            print(f'[!] {name} 端口 {port} 仍在监听，请手动结束相应进程')
    print('停止完成')


def cmd_status():
    neo = port_open(NEO4J_PORT, '127.0.0.1')
    be = port_open(BACKEND_PORT)
    fe = port_open(FRONTEND_PORT)
    print('组件状态：')
    print(f'  Neo4j :7687  {"在线" if neo else "离线"}')
    print(f'  后端  :8000  {"在线" if be else "离线"}'
          + (f'  PID={find_pids(BACKEND_PORT)}' if be else ''))
    print(f'  前端  :5173  {"在线" if fe else "离线"}'
          + (f'  PID={find_pids(FRONTEND_PORT)}' if fe else ''))
    if be:
        try:
            r = subprocess.run(
                ['curl', '-s', '-o', 'nul', '-w', '%{http_code}',
                 'http://localhost:8000/api/health'],
                capture_output=True, text=True, timeout=10)
            print(f'  后端健康检查: HTTP {r.stdout}')
        except Exception:
            pass
    return 0


def cmd_open():
    if port_open(FRONTEND_PORT):
        url = 'http://localhost:5173'
    elif port_open(BACKEND_PORT):
        url = 'http://localhost:8000'
    else:
        print('服务未运行，请先 kb start')
        return 1
    print(f'打开 {url}')
    os.startfile(url)
    return 0


def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'help').lower()
    if cmd == 'start':
        return cmd_start(prod=False)
    if cmd == 'prod':
        return cmd_start(prod=True)
    if cmd == 'stop':
        return cmd_stop()
    if cmd == 'restart':
        cmd_stop()
        time.sleep(1)
        return cmd_start(prod=False)
    if cmd == 'status':
        return cmd_status()
    if cmd == 'open':
        return cmd_open()
    print(__doc__)
    return 0


if __name__ == '__main__':
    sys.exit(main())
