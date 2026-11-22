"""Measure the existing bounded-model workflow using synthetic architecture.

Run from the repository root with mise exec -- python -B scripts/benchmark-large-model.py.
Outputs are isolated under build and contain no creative-project data.
"""
import argparse
import ctypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '.agents/skills/minecraft-nbt-modeler/scripts'
sys.path.insert(0, str(SCRIPTS))


def process_rss_tree(root):
    """Return sampled resident bytes for the live process tree, where supported."""
    if os.name != 'nt':
        entries = {}
        for proc in Path('/proc').glob('[0-9]*'):
            try:
                status = (proc / 'status').read_text(encoding='ascii')
                fields = {line.split(':', 1)[0]: line.split(':', 1)[1].strip() for line in status.splitlines() if ':' in line}
                entries[int(proc.name)] = (int(fields['PPid']), int(fields.get('VmRSS', '0 kB').split()[0]) * 1024)
            except (OSError, KeyError, ValueError):
                continue
    else:
        from ctypes import wintypes
        class Entry(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('usage', wintypes.DWORD), ('pid', wintypes.DWORD), ('heap', ctypes.c_size_t), ('module', wintypes.DWORD), ('threads', wintypes.DWORD), ('parent', wintypes.DWORD), ('priority', wintypes.LONG), ('flags', wintypes.DWORD), ('name', wintypes.WCHAR * 260)]
        class Memory(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD), ('peak', ctypes.c_size_t), ('working', ctypes.c_size_t), ('quota_peak_paged', ctypes.c_size_t), ('quota_paged', ctypes.c_size_t), ('quota_peak_nonpaged', ctypes.c_size_t), ('quota_nonpaged', ctypes.c_size_t), ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
        snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
        if snapshot == ctypes.c_void_p(-1).value:
            return None
        entries = {}
        try:
            entry = Entry(); entry.size = ctypes.sizeof(Entry)
            ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                entries[entry.pid] = (entry.parent, 0)
                ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
        for pid, (parent, _) in list(entries.items()):
            handle = kernel.OpenProcess(0x1000 | 0x10, False, pid)
            if handle:
                try:
                    memory = Memory(); memory.cb = ctypes.sizeof(Memory)
                    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
                        entries[pid] = (parent, memory.working)
                finally:
                    kernel.CloseHandle(handle)
    descendants = {root}
    while True:
        expanded = descendants | {pid for pid, (parent, _) in entries.items() if parent in descendants}
        if expanded == descendants:
            break
        descendants = expanded
    return sum(entries[pid][1] for pid in descendants if pid in entries)


def measure(name, command, output):
    started = time.perf_counter()
    log = output / (name + '.log')
    with log.open('wb') as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        peak = 0
        while process.poll() is None:
            sampled = process_rss_tree(process.pid)
            if sampled is not None:
                peak = max(peak, sampled)
            time.sleep(.25)
    result = dict(stage=name, seconds=round(time.perf_counter() - started, 3), peak_sampled_tree_rss_bytes=peak or None,
                  returncode=process.returncode, log=log.name)
    print(json.dumps(result), flush=True)
    if process.returncode:
        raise RuntimeError(name + ' failed; see ' + str(log))
    return result


def internal(stage, output):
    from nbt_assembly import Volume
    from nbt_history import History
    from nbt_refine import read_master, save_master
    from nbt_working_model import WorkingModel, value_at
    workspace = output / 'workspace'
    version = workspace / 'nbt_models/standalone/synthetic-large/v01'
    source = version / 'master/source.master.json.gz'
    if stage == 'prepare':
        source.parent.mkdir(parents=True)
        model = Volume((240, 192, 240))
        model.blocks = {(x, y, z): 'minecraft:stone_bricks' for y in (0, 32, 64, 96, 128, 160) for x in range(240) for z in range(240)}
        walls = {(0, y, z) for y in (0, 32, 64, 96, 128, 160) for z in range(240)}
        save_master(source, model, walls)
        (version / 'coordinates.json').write_text(json.dumps(dict(mode='standalone', openings=[])), encoding='utf8')
        (output / 'cameras.json').write_text(json.dumps([dict(id='overview', role='合成大模型', eye=[350,250,-350], target=[120,80,120], fov=48)]), encoding='utf8')
        History(workspace).record(dict(source=str(source), message='合成基线'))
    elif stage == 'load':
        model, walls = read_master(source)
        assert len(model.blocks) == 345600 and len(walls) == 1440
    elif stage == 'patch':
        model = WorkingModel.open(workspace, source, source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
        p = (100, 32, 100)
        result = model.patch([dict(pos=list(p), before=value_at(model.model, model.walls, p), after=['minecraft:gold_block', False])])
        assert result['changed_blocks'] == 1
    elif stage == 'append':
        target = version.parent / 'v02'
        shutil.copytree(version, target)
        result = History(workspace).record(dict(source=str(target / 'master/source.master.json.gz'), message='合成后续版本'))
        assert result['commit'] and not result['unchanged']
    else:
        raise ValueError('unknown benchmark stage')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--internal', choices=['prepare', 'load', 'patch', 'append'])
    args = parser.parse_args()
    if args.internal:
        internal(args.internal, args.output.resolve())
        return
    output = (args.output or ROOT / 'build' / ('large-model-benchmark-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    python = sys.executable
    def phase(name):
        return [python, '-B', str(Path(__file__).resolve()), '--internal', name, '--output', str(output)]
    prepare = measure('prepare', phase('prepare'), output)
    source = output / 'workspace/nbt_models/standalone/synthetic-large/v01/master/source.master.json.gz'
    node = shutil.which('node')
    if not node:
        raise ValueError('Node is required; run via mise exec')
    rows = [measure('load', phase('load'), output), measure('patch', phase('patch'), output),
            measure('render', [node, str(ROOT / 'scripts/cli.mjs'), '--workspace', str(output / 'workspace'), 'render', '--source', str(source), '--cameras', str(output / 'cameras.json'), '--output', str(output / 'render'), '--width', '320', '--height', '240'], output),
            measure('append', phase('append'), output)]
    report = dict(size=[240, 192, 240], blocks=345600, wall_positions=1440,
                  scope='Existing <=294-axis workflow; sampled aggregate process-tree resident memory every 250 ms; not an upper bound on transient peaks.',
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(), prepare=prepare, stages=rows)
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(dict(passed=True, output=str(output))), flush=True)


if __name__ == '__main__':
    main()
