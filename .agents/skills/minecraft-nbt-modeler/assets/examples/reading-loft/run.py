"""Run the reading loft example through the calling creative project's frozen CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp

from plan import reading_loft
from courtyard import courtyard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=("open", "blocked", "wrong-side", "courtyard"))
    case = parser.parse_args().case
    workspace = Path.cwd()
    entry = workspace / ".agents/skills/nbtcreator-workspace/nbt.py"
    if not entry.is_file():
        parser.error("请从已同步对外 Skill 的创作项目根目录运行。")
    examples = workspace / "nbt_models/_workspaces/examples"
    examples.mkdir(parents=True, exist_ok=True)
    run = Path(mkdtemp(prefix=f"reading-loft-{case}-", dir=examples))
    print(f"本次请求与回执目录 {run}", flush=True)

    def invoke(action, request):
        path = run / f"{action}.json"
        path.write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding="utf8")
        result = subprocess.run([sys.executable, "-B", str(entry), "architect", action, "--request", str(path)],
                                stdout=subprocess.PIPE, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        receipt = run / f"{action}-result.json"
        receipt.write_bytes(result.stdout)
        if result.returncode:
            error = json.loads(result.stdout)["error"] if result.stdout else f"退出码 {result.returncode}"
            if error.startswith("ROUTE_FAILED: "):
                report, = json.loads(error.removeprefix("ROUTE_FAILED: "))
                for target in report["targets"]:
                    print(f'{target["name"]} {target["feet"]} {target.get("reason", "可达")}', file=sys.stderr)
                print(f"ROUTE_FAILED，完整通路证据见 {receipt}", file=sys.stderr)
            elif error.startswith("DESIGN_INVALID: "):
                for row in json.loads(error.removeprefix("DESIGN_INVALID: ")):
                    print(f'{row["id"]} {row["kind"]}', file=sys.stderr)
                    for face in row.get("use_faces", []):
                        if not face["passed"]:
                            print(f'第 {face["stop_index"] + 1} 站 {face["part"]}.{face["interface"]} {face["reason"]}', file=sys.stderr)
                print(f"DESIGN_INVALID，完整检查见 {receipt}", file=sys.stderr)
            else:
                print(error, file=sys.stderr)
            raise SystemExit(result.returncode)
        return json.loads(result.stdout)

    plan = courtyard() if case == "courtyard" else reading_loft(blocked=case == "blocked", wrong_side=case == "wrong-side")
    record = invoke("plan-save", dict(revision=0, plan=plan))
    build = dict(plan_id=record["id"], revision=record["revision"])
    if case in ("blocked", "wrong-side"):
        invoke("plan-build", build)
        parser.exit(2, "预期失败的候选通过了建模检查，请检查 plan-build-result.json。\n")
    build["save_draft"] = dict(name_zh=f"{plan['name']}样例-{run.name.rsplit('-', 1)[-1]}")
    source = Path(invoke("plan-build", build)["saved"]["source"])
    binding = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    invoke("plan-check", binding)
    pack = invoke("review-prepare", dict(**binding, output=str(run / "review")))
    if not pack["coverage"]["coverage_passed"]:
        raise SystemExit("机位或审阅点被遮挡，请检查 review-prepare-result.json。")
    subprocess.run([sys.executable, "-B", str(entry), *pack["render_command"]], check=True)
    if case == "open":
        cameras = Path(__file__).with_name("loft-sections.json")
        subprocess.run([sys.executable, "-B", str(entry), "render", "--source", str(source), "--cameras", str(cameras),
                        "--output", str(run / "sections")], check=True)
        print(f"逐层平面与纵剖 {run / 'sections'}")
    print("\n".join(pack["coverage"]["delivery_summary"]))
    print(f"制作版 {source}\n请查看 {run / 'review/render'} 内各机位的 PNG。")


if __name__ == "__main__":
    main()
