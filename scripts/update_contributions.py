"""Refresh public experiment attribution; --data allows a reproducible offline render."""
import argparse
import collections
import html
import json
import os
from pathlib import Path
import urllib.request

ORG = "SUEP-24371OS-GroupSix"
ROOT = Path(__file__).resolve().parents[1]

def api(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "group-six-contributions"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com" + path, headers=headers), timeout=60) as response:
        return json.load(response)

def pages(path):
    result = []
    page = 1
    while True:
        rows = api(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
        result.extend(rows)
        if len(rows) < 100:
            return result
        page += 1

def collect():
    result = []
    for repo in pages(f"/orgs/{ORG}/repos?type=public"):
        if repo["name"] == ".github":
            continue
        meta = api(f"/repos/{ORG}/{repo['name']}")
        commits = pages(f"/repos/{ORG}/{repo['name']}/commits") if meta["size"] else []
        counts = collections.Counter()
        for commit in commits:
            author = commit.get("author")
            # Never publish unlinked author email addresses.
            label = author["login"] if author else "未关联 GitHub 账号"
            counts[label] += 1
        result.append({"name": repo["name"], "parent": (meta.get("parent") or {}).get("full_name"),
                       "authors": dict(sorted(counts.items(), key=lambda x: (-x[1], x[0])))})
    return sorted(result, key=lambda x: x["name"])

def render(data):
    totals = collections.Counter()
    for repo in data:
        totals.update(repo["authors"])
    rows = sorted(totals.items(), key=lambda x: (-x[1], x[0]))
    height = 110 + max(1, len(rows)) * 58
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}" role="img" aria-label="实验仓库提交作者贡献图">',
           f'<rect width="900" height="{height}" rx="16" fill="#f6f8fa"/>',
           '<g font-family="Arial, Microsoft YaHei, sans-serif" fill="#1f2328">',
           '<text x="28" y="38" font-size="22" font-weight="bold">实验仓库 · 提交作者贡献</text>',
           '<text x="28" y="64" font-size="13" fill="#59636e">默认分支全部历史 · 含 Fork 继承提交 · 提交数不等于工作量</text>']
    maximum = max(totals.values(), default=1)
    for i, (user, count) in enumerate(rows):
        y = 100 + i * 58
        svg.extend([f'<text x="28" y="{y+18}" font-size="16">{html.escape(user)}</text>',
                    f'<rect x="280" y="{y}" width="{max(2, 510*count/maximum):.1f}" height="28" rx="6" fill="#0969da"/>',
                    f'<text x="810" y="{y+20}" font-size="16">{count} 次</text>'])
    if not rows:
        svg.append('<text x="28" y="118" font-size="16">暂无提交记录</text>')
    svg.append('</g></svg>\n')
    out = ROOT / "profile"
    out.mkdir(exist_ok=True)
    (out / "contributions.svg").write_text("\n".join(svg), encoding="utf-8")
    (out / "contributions.json").write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    section = ["<!-- contributions:start -->",
               "## 贡献者与 Fork 来源", "",
               f"![按提交作者统计的贡献图](https://raw.githubusercontent.com/{ORG}/.github/main/profile/contributions.svg)", "",
               "| 实验仓库 | Fork 来源 | 提交作者与次数 | 提交记录 |",
               "| --- | --- | --- | --- |"]
    for repo in data:
        name = repo["name"]
        url = f"https://github.com/{ORG}/{name}"
        parent = repo["parent"]
        source = f"[{parent}](https://github.com/{parent})" if parent else "独立仓库（非 Fork）"
        authors = "、".join((f"[{u}](https://github.com/{u})" if u != "未关联 GitHub 账号" else u) + f"：{n} 次" for u, n in repo["authors"].items()) or "暂无提交"
        section.append(f"| [{name}]({url}) | {source} | {authors} | [查看记录]({url}/commits) |")
    section.extend(["", "**统计口径**：按公开实验仓库默认分支的 GitHub 提交作者统计，包含 Fork 继承的历史和合并提交；同一提交出现在不同仓库时分别计数。统计不代表实际上传操作人、独立原创程度或工作量。未关联账号的作者单独汇总，不公开邮箱。",
                    "", "**署名方式**：每位同学使用自己的 GitHub 账号提交；本地 Git 的提交邮箱需关联到自己的账号。代传材料请在提交说明中写明原作者与分工。Fork 来源保留上游署名。",
                    "", "每日自动刷新，也可在本仓库 Actions 中手动运行 **更新贡献图**。新建公开实验仓库会自动纳入；尚未合并到默认分支的提交暂不计入。",
                    "<!-- contributions:end -->"])
    readme = out / "README.md"
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- contributions:start -->", "<!-- contributions:end -->"
    block = "\n".join(section)
    if start in text and end in text:
        before, tail = text.split(start, 1)
        _, after = tail.split(end, 1)
        text = before + block + after
    else:
        text = text.replace("## 课程展示要求", block + "\n\n## 课程展示要求")
    readme.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path)
    args = parser.parse_args()
    render(json.loads(args.data.read_text(encoding="utf-8")) if args.data else collect())
