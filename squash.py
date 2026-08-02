#!/usr/bin/env python3
"""将 8-14 天前的 commit 合并为一个，保持最近 7 天不变"""

import subprocess
import datetime
import os


def run(cmd, fatal=True, env=None):
    """执行 shell 命令，返回 (stdout, returncode)"""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
    if fatal and r.returncode != 0:
        print(f"[FAIL] {cmd}")
        if r.stderr:
            print(r.stderr[:500])
    return r.stdout.strip(), r.returncode


def main():
    # 设置时区为上海，与 CI 中 runner 的时区保持一致
    os.environ['TZ'] = 'Asia/Shanghai'

    today = datetime.date.today()
    keep_start = today - datetime.timedelta(days=6)       # 例: 6/9 — 保留 6/9 及之后
    squash_start = today - datetime.timedelta(days=13)    # 例: 6/2 — 合并区间起点
    squash_end = today - datetime.timedelta(days=7)       # 例: 6/8 — 合并区间终点

    label = f"{squash_start} ~ {squash_end}"
    squash_msg = f"squash: {label}"

    print(f"今天: {today}")
    print(f"保留范围: {keep_start} ~ {today}")
    print(f"合并范围: {label}")

    # 1. 检查是否已有合并 commit
    out, _ = run(f"git log --oneline --grep='{squash_msg}'", fatal=False)
    if out:
        print(f"已存在合并 commit，跳过")
        return

    # 2. 获取合并区间内的 commit（--since 包含当日，--until 不包含当日）
    out, _ = run(
        f"git log --reverse --since='{squash_start}' --until='{keep_start}' --format='%H'"
    )
    squash_hashes = [h for h in out.split('\n') if h]
    print(f"合并区间内 {len(squash_hashes)} 个 commit")

    if len(squash_hashes) < 2:
        print("不到 2 个 commit，无需合并")
        return

    # 3. 获取合并区间第一个 commit 的父 commit
    parent, code = run(f"git rev-parse {squash_hashes[0]}~1")
    if code != 0:
        print("无法获取父 commit，退出")
        return

    # 4. 获取保留区间的 commit（后续需 cherry-pick 回来）
    out, _ = run(f"git log --reverse --since='{keep_start}' --format='%H'")
    keep_hashes = [h for h in out.split('\n') if h]
    print(f"保留区间 {len(keep_hashes)} 个 commit 待 cherry-pick")

    # 5. 准备工作
    run("git config user.name left916", fatal=False)
    run("git config user.email 1379771811@qq.com", fatal=False)
    run("git config --global --add safe.directory /github/workspace", fatal=False)
    run("git fetch --unshallow origin 2>/dev/null; git fetch origin", fatal=False)

    # 6. 在临时分支上操作
    ts = int(datetime.datetime.now().timestamp())
    branch = f"squash-temp-{ts}"
    print(f"创建临时分支: {branch}")

    _, code = run(f"git checkout -b {branch} {parent}")
    if code != 0:
        print("创建临时分支失败")
        run("git checkout main || git checkout master", fatal=False)
        return

    # 7. 取出合并区间最后一个 commit 的文件状态
    _, code = run(f"git checkout {squash_hashes[-1]} -- .")
    if code != 0:
        print("checkout 文件失败，回滚")
        run("git checkout main || git checkout master", fatal=False)
        run(f"git branch -D {branch}", fatal=False)
        return

    # 8. 创建合并 commit
    _, code = run(
        f"git commit -m '{squash_msg}' "
        f"-m '合并了 {label} 的 {len(squash_hashes)} 个存档备份 commit'"
    )
    if code != 0:
        print("创建合并 commit 失败")
        run("git checkout main || git checkout master", fatal=False)
        run(f"git branch -D {branch}", fatal=False)
        return

    print(f"已创建合并 commit: {squash_msg}")

    # 9. Cherry-pick 保留区间的 commit，保留原始提交者信息
    for i, h in enumerate(keep_hashes):
        cn, _ = run(f"git log -1 --format='%cn' {h}", fatal=False)
        ce, _ = run(f"git log -1 --format='%ce' {h}", fatal=False)
        cd, _ = run(f"git log -1 --format='%ci' {h}", fatal=False)

        cp_env = os.environ.copy()
        cp_env['GIT_COMMITTER_NAME'] = cn
        cp_env['GIT_COMMITTER_EMAIL'] = ce
        cp_env['GIT_COMMITTER_DATE'] = cd

        _, code = run(f"git cherry-pick {h}", env=cp_env)
        if code != 0:
            print(f"Cherry-pick 第 {i+1}/{len(keep_hashes)} ({h[:7]}) 失败，回滚")
            run("git cherry-pick --abort", fatal=False)
            run("git checkout main || git checkout master", fatal=False)
            run(f"git branch -D {branch}", fatal=False)
            return
        print(f"  cherry-pick {i+1}/{len(keep_hashes)} ({h[:7]}) 作者/提交者/日期已保留")

    # 10. 强制推送
    print("推送到远程...")
    _, code = run(f"git push --force-with-lease origin {branch}:main")
    if code != 0:
        print("推送失败")
        run("git checkout main || git checkout master", fatal=False)
        run(f"git branch -D {branch}", fatal=False)
        return

    print("推送成功")
    run("git checkout main || git checkout master", fatal=False)
    run(f"git branch -D {branch}", fatal=False)
    print("完成")


if __name__ == '__main__':
    main()
