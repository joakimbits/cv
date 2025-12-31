# file: branches.py
from __future__ import annotations

import os
import shlex
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any as TypingAny, Deque, Dict, Iterable, List as TList, Optional, Sequence, Set, Tuple

from traits.api import Any, Bool, Button, HasTraits, Instance, Int, List, Property, Str, observe
from traitsui.api import HGroup, Item, TreeEditor, TreeNode, UItem, VGroup, View


# -----------------------------
# Errors + git runner
# -----------------------------


class GitError(RuntimeError):
    def __init__(self, message: str, *, cmd: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.cmd = cmd
        self.stderr = stderr


def _fmt_cmd(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(x) for x in cmd)


def _run_git(
    repo_root: Path,
    args: Sequence[str],
    *,
    timeout_s: int = 60,
    check: bool = True,
    stdin_text: Optional[str] = None,
) -> Tuple[int, str, str]:
    cmd = ["git", "-C", str(repo_root), *args]
    try:
        cp = subprocess.run(
            cmd,
            input=stdin_text,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return cp.returncode, cp.stdout, cp.stderr
    except FileNotFoundError as e:
        raise GitError("git executable not found in PATH.", cmd=_fmt_cmd(cmd), stderr=str(e)) from e
    except subprocess.TimeoutExpired as e:
        raise GitError("git command timed out.", cmd=_fmt_cmd(cmd), stderr=str(e)) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        msg = stderr or stdout or "Unknown git error."
        raise GitError(msg, cmd=_fmt_cmd(cmd), stderr=stderr) from e


def _find_repo_root(start: Path) -> Path:
    _rc, out, _err = _run_git(start, ["rev-parse", "--show-toplevel"], timeout_s=30)
    root = Path(out.strip())
    if not root.exists():
        raise GitError("Failed to resolve repo root.")
    return root


def _normalize_pathspec(s: str) -> str:
    return (s or "").strip().replace("\\", "/")


def _chunked(xs: TList[str], n: int) -> Iterable[TList[str]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]


# -----------------------------
# Git data extraction (math layer)
# -----------------------------


@dataclass(frozen=True)
class CommitMeta:
    sha: str
    author: str
    date_iso: str
    subject: str
    epoch: int


def _head_branch(repo_root: Path) -> str:
    rc, out, _err = _run_git(repo_root, ["symbolic-ref", "-q", "--short", "HEAD"], timeout_s=30, check=False)
    return out.strip() if rc == 0 else ""


def _head_file_tip_sha(repo_root: Path, pathspec: str) -> str:
    rc, out, _err = _run_git(
        repo_root,
        ["log", "-n", "1", "--pretty=format:%H", "HEAD", "--", pathspec],
        timeout_s=90,
        check=False,
    )
    if rc != 0:
        return ""
    out = out.strip()
    return out.splitlines()[0].strip() if out else ""


def _branches_list(repo_root: Path, include_remotes: bool) -> TList[str]:
    refs = ["refs/heads"]
    if include_remotes:
        refs.append("refs/remotes")

    _rc, out, _err = _run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", *refs], timeout_s=60)
    names = [ln.strip() for ln in out.splitlines() if ln.strip()]
    names = [n for n in names if not n.endswith("/HEAD")]
    names.sort(key=str.casefold)
    return names


def _file_tip_sha(repo_root: Path, ref: str, pathspec: str) -> str:
    rc, out, _err = _run_git(
        repo_root,
        ["log", "-n", "1", "--pretty=format:%H", ref, "--", pathspec],
        timeout_s=90,
        check=False,
    )
    if rc != 0:
        return ""
    out = out.strip()
    return out.splitlines()[0].strip() if out else ""


def _touch_log_rows(repo_root: Path, pathspec: str, max_commits: int) -> TList[Tuple[str, TList[str]]]:
    """
    Commits that touched the file (across all refs), newest -> oldest, topo-ordered.
    Each row: (sha, [parents...]) parents are the real commit parents (may include non-touch commits).
    """
    args = ["log", "--all", "--topo-order", f"-n{max_commits}", "--pretty=format:%H %P", "--", pathspec]
    _rc, out, _err = _run_git(repo_root, args, timeout_s=240)
    rows: TList[Tuple[str, TList[str]]] = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        toks = ln.split()
        rows.append((toks[0], toks[1:]))
    return rows


def _ancestor_parent_graph(repo_root: Path, start_commits: TList[str]) -> Dict[str, TList[str]]:
    """
    Parent map for all ancestors reachable from start_commits.
    Uses --stdin to avoid Windows cmdline length issues.
    """
    stdin = "\n".join(start_commits) + "\n"
    rc, out, err = _run_git(
        repo_root,
        ["rev-list", "--parents", "--topo-order", "--stdin"],
        timeout_s=240,
        check=False,
        stdin_text=stdin,
    )
    if rc != 0:
        raise GitError(err.strip() or "git rev-list failed.", cmd="git rev-list --parents --stdin", stderr=err.strip())

    parents_map: Dict[str, TList[str]] = {}
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        toks = ln.split()
        parents_map[toks[0]] = toks[1:]
    return parents_map


def _fetch_meta(repo_root: Path, shas: TList[str]) -> Dict[str, CommitMeta]:
    if not shas:
        return {}
    fmt = "%H%x1f%an%x1f%ad%x1f%ct%x1f%s%x1e"
    metas: Dict[str, CommitMeta] = {}
    for chunk in _chunked(list(dict.fromkeys(shas)), 200):
        _rc, out, _err = _run_git(
            repo_root,
            ["show", "-s", "--date=iso-strict", f"--pretty=format:{fmt}", *chunk],
            timeout_s=240,
        )
        for rec in out.split("\x1e"):
            rec = rec.strip()
            if not rec:
                continue
            parts = rec.split("\x1f")
            if len(parts) != 5:
                continue
            sha, author, date_iso, epoch_s, subject = (p.strip() for p in parts)
            try:
                epoch = int(epoch_s)
            except ValueError:
                epoch = 0
            metas[sha] = CommitMeta(sha=sha, author=author, date_iso=date_iso, subject=subject, epoch=epoch)
    return metas


def _nearest_touch_commits(
    start_sha: str,
    *,
    touch_set: Set[str],
    parents_map: Dict[str, TList[str]],
    cache: Dict[str, TList[str]],
    max_bfs: int = 50_000,
) -> TList[str]:
    """
    BFS backward from start_sha over parents_map until we hit commit(s) in touch_set.
    Return hits at minimal distance.
    """
    if not start_sha:
        return []
    if start_sha in cache:
        return cache[start_sha]
    if start_sha in touch_set:
        cache[start_sha] = [start_sha]
        return cache[start_sha]

    q: Deque[Tuple[str, int]] = deque([(start_sha, 0)])
    visited: Set[str] = set()
    best_depth: Optional[int] = None
    found: TList[str] = []
    steps = 0

    while q:
        sha, depth = q.popleft()
        steps += 1
        if steps > max_bfs:
            break
        if sha in visited:
            continue
        visited.add(sha)

        if best_depth is not None and depth > best_depth:
            break

        if sha in touch_set:
            if best_depth is None:
                best_depth = depth
            if depth == best_depth:
                found.append(sha)
            continue

        for p in parents_map.get(sha, []):
            if p and p not in visited:
                q.append((p, depth + 1))

    out: TList[str] = []
    seen: Set[str] = set()
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)

    cache[start_sha] = out
    return out


def build_file_history_graph(
    repo_root: Path,
    pathspec: str,
    *,
    max_commits: int,
    include_remotes: bool,
) -> Tuple[
    TList[str],                    # touch_shas newest->oldest
    Dict[str, TList[str]],         # touch_parents: sha -> [touch_parent_sha...]
    Dict[str, CommitMeta],         # meta for touch commits
    Dict[str, TList[str]],         # branch_labels: sha -> [branch names where sha is that branch's file-tip]
    str,                           # head_file_tip_sha
    str,                           # head_branch
]:
    touch_rows = _touch_log_rows(repo_root, pathspec, max_commits=max_commits)
    touch_shas = [sha for sha, _ in touch_rows]
    touch_set = set(touch_shas)

    parents_map = _ancestor_parent_graph(repo_root, touch_shas)

    nearest_cache: Dict[str, TList[str]] = {}
    touch_parents: Dict[str, TList[str]] = {}

    for sha, direct_parents in touch_rows:
        parents_out: TList[str] = []
        for p in direct_parents:
            parents_out.extend(
                _nearest_touch_commits(
                    p,
                    touch_set=touch_set,
                    parents_map=parents_map,
                    cache=nearest_cache,
                )
            )
        seen: Set[str] = set()
        uniq: TList[str] = []
        for x in parents_out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        touch_parents[sha] = uniq

    metas = _fetch_meta(repo_root, touch_shas)

    branch_labels: Dict[str, TList[str]] = {}
    for b in _branches_list(repo_root, include_remotes=include_remotes):
        tip = _file_tip_sha(repo_root, b, pathspec)
        if tip:
            branch_labels.setdefault(tip, []).append(b)
    for sha in branch_labels:
        branch_labels[sha].sort(key=str.casefold)

    head_branch = _head_branch(repo_root)
    head_file_tip = _head_file_tip_sha(repo_root, pathspec)

    return touch_shas, touch_parents, metas, branch_labels, head_file_tip, head_branch


# -----------------------------
# Traits UI nodes (display-only)
# -----------------------------


class CommitTreeNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str
    epoch = Int(0)

    branches = Str
    is_head = Bool(False)

    children = List(Any)

    label = Property(Str, depends_on="sha,subject,date_iso,branches,is_head")

    def _get_label(self) -> str:
        short = self.sha[:10] if self.sha else ""
        date_part = self.date_iso[:10] if self.date_iso else ""
        head = "  [HEAD]" if self.is_head else ""
        br = f"  [{self.branches}]" if self.branches else ""
        return f"{short}  {date_part}  {self.subject}{head}{br}".rstrip()


class FileHistoryRoot(HasTraits):
    label = Str("File history")
    children = List(Any)


# -----------------------------
# UI model
# -----------------------------


class FileHistoryModel(HasTraits):
    repo_path = Str
    pathspec = Str
    include_remotes = Bool(False)
    max_commits = Int(2000)

    hard_crash_on_error = Bool(True)

    refresh = Button("Refresh")

    tree_root = Instance(FileHistoryRoot)
    selected = Any
    status = Str

    selected_details = Property(Str, depends_on="selected")

    def _tree_root_default(self) -> FileHistoryRoot:
        return FileHistoryRoot(label="File history", children=[])

    def _get_selected_details(self) -> str:
        sel = self.selected
        if isinstance(sel, CommitTreeNode):
            return (
                f"Commit:  {sel.sha}\n"
                f"Author:  {sel.author}\n"
                f"Date:    {sel.date_iso}\n"
                f"Title:   {sel.subject}\n"
                f"HEAD:    {bool(sel.is_head)}\n"
                f"Branches:{sel.branches}\n"
            )
        if isinstance(sel, FileHistoryRoot):
            return sel.label
        return ""

    def _make_tree_editor(self) -> TreeEditor:
        return TreeEditor(
            nodes=[
                TreeNode(node_for=[FileHistoryRoot], auto_open=True, children="children", label="label"),
                TreeNode(node_for=[CommitTreeNode], auto_open=True, children="children", label="label"),
            ],
            editable=False,
            selected="selected",
            hide_root=True,
        )

    @observe("refresh")
    def _on_refresh(self, _event) -> None:
        self.reload()

    def reload(self) -> None:
        try:
            self._load()
        except Exception:
            if self.hard_crash_on_error:
                os._exit(1)
            raise

    def _load(self) -> None:
        self.status = "Loading…"
        self.tree_root = FileHistoryRoot(label="File history", children=[])
        self.selected = None

        if not self.repo_path.strip():
            raise GitError("Repo path is empty.")
        ps = _normalize_pathspec(self.pathspec)
        if not ps:
            raise GitError("Pathspec is empty (e.g. README.md).")

        repo_dir = Path(self.repo_path).expanduser().resolve()
        if not repo_dir.exists():
            raise GitError(f"Repo path does not exist: {repo_dir}")
        repo_root = _find_repo_root(repo_dir)

        touch_shas, touch_parents, metas, branch_labels, head_file_tip, head_branch = build_file_history_graph(
            repo_root,
            ps,
            max_commits=max(1, int(self.max_commits)),
            include_remotes=bool(self.include_remotes),
        )

        if not touch_shas:
            self.tree_root = FileHistoryRoot(label=f"File history (0) — {ps}", children=[])
            self.status = f"{repo_root} | {ps} | no commits touching path"
            return

        children_of: Dict[str, TList[str]] = {sha: [] for sha in touch_shas}
        roots: TList[str] = []

        for child in touch_shas:
            parents = touch_parents.get(child, [])
            if not parents:
                roots.append(child)
            for p in parents:
                if p in children_of:
                    children_of[p].append(child)

        epoch_map = {sha: metas.get(sha).epoch if sha in metas else 0 for sha in touch_shas}
        for p, kids in children_of.items():
            kids.sort(key=lambda s: epoch_map.get(s, 0), reverse=True)

        root_order = sorted(roots, key=lambda s: epoch_map.get(s, 0))
        primary_root = root_order[0]

        if head_file_tip and head_file_tip in touch_shas:
            cur = head_file_tip
            seen: Set[str] = set()
            while True:
                if cur in seen:
                    break
                seen.add(cur)
                ps_parents = touch_parents.get(cur, [])
                if not ps_parents:
                    primary_root = cur
                    break
                cur = min(ps_parents, key=lambda x: epoch_map.get(x, 0))

        def build_display(sha: str, path: Set[str]) -> CommitTreeNode:
            if sha in path:
                m = metas.get(sha)
                return CommitTreeNode(
                    sha=sha,
                    author=m.author if m else "",
                    date_iso=m.date_iso if m else "",
                    subject=(m.subject if m else "") + "  (cycle?)",
                    epoch=m.epoch if m else 0,
                    branches=", ".join(branch_labels.get(sha, [])),
                    is_head=(sha == head_file_tip),
                    children=[],
                )
            path2 = set(path)
            path2.add(sha)

            m = metas.get(sha)
            node = CommitTreeNode(
                sha=sha,
                author=m.author if m else "",
                date_iso=m.date_iso if m else "",
                subject=m.subject if m else "",
                epoch=m.epoch if m else 0,
                branches=", ".join(branch_labels.get(sha, [])),
                is_head=(sha == head_file_tip),
                children=[],
            )
            for child_sha in children_of.get(sha, []):
                node.children.append(build_display(child_sha, path2))
            return node

        primary_node = build_display(primary_root, set())

        other_roots = [r for r in root_order if r != primary_root]
        other_nodes = [build_display(r, set()) for r in other_roots]

        label = f"File history — {ps}  (roots={len(root_order)})"
        children: TList[TypingAny] = [primary_node]
        if other_nodes:
            children.append(FileHistoryRoot(label=f"Other roots ({len(other_nodes)})", children=other_nodes))

        self.tree_root = FileHistoryRoot(label=label, children=children)
        self.status = (
            f"{repo_root} | {ps} | touch_commits={len(touch_shas)} | "
            f"head_file_tip={(head_file_tip[:10] if head_file_tip else 'none')} | "
            f"head_branch={head_branch or 'detached'}"
        )

    def traits_view(self) -> View:
        ed = self._make_tree_editor()
        return View(
            VGroup(
                HGroup(
                    Item("repo_path", label="Repo", width=0.6),
                    Item("pathspec", label="Pathspec", width=0.6),
                ),
                HGroup(
                    Item("include_remotes", label="Include remotes"),
                    Item("max_commits", label="Max commits"),
                    UItem("refresh"),
                    Item("hard_crash_on_error", label="Hard crash"),
                ),
                HGroup(
                    VGroup(
                        UItem("tree_root", editor=ed, style="custom"),
                        show_border=True,
                        label="File history tree",
                    ),
                    VGroup(
                        Item("selected_details", style="readonly", show_label=False),
                        show_border=True,
                        label="Details",
                    ),
                ),
                Item("status", style="readonly", show_label=False),
            ),
            title="Git file history tree (TraitsUI)",
            width=1250,
            height=820,
            resizable=True,
        )


def main() -> None:
    model = FileHistoryModel(
        repo_path=str(Path.cwd()),
        pathspec="README.md",
        include_remotes=False,
        max_commits=2000,
        hard_crash_on_error=True,
    )
    model.reload()
    model.configure_traits()


if __name__ == "__main__":
    main()
