#!/usr/bin/env python3
"""Regenerate the 'Contributed to' list in README.md from merged PRs.

Searches merged PRs authored by USER in repos USER doesn't own, dedupes by
repo, sorts by stars (desc), and rewrites only the block between
<!-- CONTRIB:START --> and <!-- CONTRIB:END -->.
"""
import json, os, re, sys, urllib.parse, urllib.request

USER = os.environ.get("CONTRIB_USER", "ganeshmshetty")
README = os.environ.get("README_PATH", "README.md")
START, END = "<!-- CONTRIB:START -->", "<!-- CONTRIB:END -->"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def gh(path, params=None):
    url = "https://api.github.com" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"{USER}-contrib-updater",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_repos():
    q = f"is:pr is:merged author:{USER} -user:{USER}"
    repos, page = {}, 1
    while True:
        data = gh("/search/issues", {"q": q, "per_page": 100, "page": page})
        if data.get("incomplete_results"):
            sys.exit("Search returned incomplete results; not updating.")
        for item in data["items"]:
            full = item["repository_url"].split("/repos/", 1)[1]
            merged = (item.get("pull_request") or {}).get("merged_at") or item.get("closed_at") or ""
            if merged > repos.get(full, ""):
                repos[full] = merged
        if len(data["items"]) < 100 or page * 100 >= data["total_count"]:
            break
        page += 1
    out = []
    for full, merged in repos.items():
        info = gh(f"/repos/{full}")
        if info.get("private") or info["owner"]["login"].lower() == USER.lower():
            continue
        out.append({"repo": info["full_name"], "stars": info["stargazers_count"], "lastMerged": merged})
    out.sort(key=lambda r: (-r["stars"], r["repo"].lower()))
    return out


def main():
    repos = fetch_repos()
    if not repos:
        sys.exit("No merged PRs found; refusing to empty the list.")
    lines = [f"- [{r['repo']}](https://github.com/{r['repo']}) "
             f"![Stars](https://badgen.net/github/stars/{r['repo']}?icon=github)" for r in repos]
    text = open(README, encoding="utf-8").read()
    pat = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pat.search(text):
        sys.exit(f"Markers {START} / {END} not found in {README}.")
    new = pat.sub(lambda _: START + "\n" + "\n".join(lines) + "\n" + END, text, count=1)
    if new != text:
        open(README, "w", encoding="utf-8").write(new)
        print(f"Updated {README} with {len(repos)} repos.")
    else:
        print("No changes.")
    for r in repos:
        print(f"  {r['repo']} ({r['stars']} stars, last merged {r['lastMerged']})")


if __name__ == "__main__":
    main()
