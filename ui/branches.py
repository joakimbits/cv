# file: branches.py
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any as TypingAny, Dict, Iterable, List as TList, Sequence, Tuple

from traits.api import (
    Any,
    Bool,
    Button,
    Enum,
    HasTraits,
    Instance,
    Int,
    List,
    Property,
    Str,
)
from traitsui.api import (
    DirectoryEditor,
    FileEditor,
    HGroup,
    Item,
    TreeEditor,
    TreeNode,
    UItem,
    VGroup,
    View,
)


class GitError(RuntimeError):
    pass


def _run_git(repo_dir: Path, args: Sequence[str], timeout_s: int = 30) -> str:
    try:
        cp = subprocess.run(
            ["git", *args],
            cwd=str(repo_dir),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return cp.stdout
    except FileNotFoundError as e:
        raise GitError("git executable not found in PATH.") from e
    except subprocess.TimeoutExpired as e:
        raise GitError(f"git command timed out: git {' '.join(map(shlex.quote, args))}") from e
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or "").strip() or (e.stdout or "").strip() or "Unknown git error."
        raise GitError(msg) from e


def _find_repo_root(start: Path) -> Path:
    out = _run_git(start, ["rev-parse", "--show-toplevel"])
    root = Path(out.strip())
    if not root.exists():
        raise GitError("Failed to resolve repo root.")
    return root


def _relpath_in_repo(repo_root: Path, file_abs: Path) -> Path:
    fp = file_abs.expanduser().resolve()
    rr = repo_root.expanduser().resolve()
    try:
        return fp.relative_to(rr)
    except ValueError as e:
        raise GitError("File path is not inside the selected repository.") from e


def _resolve_file_abs(repo_dir: Path, repo_root: Path, file_path_str: str) -> Path:
    """
    Matches the behavior of your working code (relative path resolves from repo_path/CWD),
    but also supports repo-root-relative paths.
    """
    p = Path(file_path_str).expanduser()
    if p.is_absolute():
        return p.resolve()

    candidates = [
        (repo_dir / p).resolve(),   # ✅ most important: like your current working setup
        (repo_root / p).resolve(),  # repo-root relative
        (Path.cwd() / p).resolve(), # fallback
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


def _chunked(xs: TList[str], chunk_size: int) -> Iterable[TList[str]]:
    for i in range(0, len(xs), chunk_size):
        yield xs[i : i + chunk_size]


# -----------------------------
# Branches view (branch → commits touching file)
# -----------------------------

@dataclass(frozen=True)
class TouchCommitInfo:
    sha: str
    author: str
    date_iso: str
    subject: str


def _list_local_branches(repo_root: Path) -> TList[str]:
    out = _run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    branches = [b.strip() for b in out.splitlines() if b.strip()]
    return sorted(branches, key=str.casefold)


def _parse_git_log_lines(lines: Iterable[str]) -> TList[TouchCommitInfo]:
    commits: TList[TouchCommitInfo] = []
    for line in lines:
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, author, date_iso, subject = (p.strip() for p in parts)
        if sha:
            commits.append(TouchCommitInfo(sha=sha, author=author, date_iso=date_iso, subject=subject))
    return commits


def _commits_touching_file(repo_root: Path, branch: str, file_rel: Path) -> TList[TouchCommitInfo]:
    fmt = "%H%x1f%an%x1f%ad%x1f%s"
    out = _run_git(
        repo_root,
        ["log", "--date=iso-strict", f"--pretty=format:{fmt}", branch, "--", file_rel.as_posix()],
        timeout_s=60,
    )
    return _parse_git_log_lines(out.splitlines())


# -----------------------------
# History view (commit → parents) + name-rev decorations
# -----------------------------

@dataclass(frozen=True)
class CommitMeta:
    sha: str
    parents: TList[str]
    author: str
    date_iso: str
    subject: str


def _rev_list_with_parents(
    repo_root: Path, start_ref: str, file_rel: Path, max_commits: int
) -> TList[Tuple[str, TList[str]]]:
    out = _run_git(
        repo_root,
        ["rev-list", "--parents", "--topo-order", f"-n{max_commits}", start_ref, "--", file_rel.as_posix()],
        timeout_s=90,
    )
    rows: TList[Tuple[str, TList[str]]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        toks = line.split()
        rows.append((toks[0], toks[1:]))
    return rows


def _parse_show_records(text: str) -> Dict[str, CommitMeta]:
    metas: Dict[str, CommitMeta] = {}
    for rec in text.split("\x1e"):
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) != 5:
            continue
        sha, parents_s, author, date_iso, subject = (p.strip() for p in parts)
        parents = [p for p in parents_s.split() if p] if parents_s else []
        metas[sha] = CommitMeta(sha=sha, parents=parents, author=author, date_iso=date_iso, subject=subject)
    return metas


def _fetch_commit_meta(repo_root: Path, shas: TList[str]) -> Dict[str, CommitMeta]:
    if not shas:
        return {}
    fmt = "%H%x1f%P%x1f%an%x1f%ad%x1f%s%x1e"
    metas: Dict[str, CommitMeta] = {}
    for chunk in _chunked(shas, chunk_size=200):
        out = _run_git(
            repo_root,
            ["show", "-s", "--date=iso-strict", f"--pretty=format:{fmt}", *chunk],
            timeout_s=90,
        )
        metas.update(_parse_show_records(out))
    return metas


def _name_rev_map(repo_root: Path, shas: TList[str], include_remotes: bool) -> Dict[str, str]:
    if not shas:
        return {}
    refs = ["refs/heads/*"]
    if include_remotes:
        refs.append("refs/remotes/*")

    out_map: Dict[str, str] = {}
    for chunk in _chunked(shas, chunk_size=200):
        out = _run_git(
            repo_root,
            ["name-rev", "--name-only", "--no-undefined", f"--refs={','.join(refs)}", *chunk],
            timeout_s=90,
        )
        names = [ln.strip() for ln in out.splitlines() if ln.strip()]
        for sha, name in zip(chunk, names, strict=False):
            out_map[sha] = name
    return out_map


# -----------------------------
# Traits models (shared)
# -----------------------------

class CommitNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str

    # Used in history mode; empty list in branches mode.
    parents = List(Instance("CommitNode"))

    # Decorations
    name_rev = Str

    label = Property(Str, depends_on="sha,subject,date_iso,name_rev")
    details = Property(Str, depends_on="sha,author,date_iso,subject,name_rev")

    def _get_label(self) -> str:
        short = self.sha[:10] if self.sha else ""
        date_part = self.date_iso[:10] if self.date_iso else ""
        deco = f"[{self.name_rev}]" if self.name_rev else ""
        return f"{short}  {date_part}  {self.subject}  {deco}".rstrip()

    def _get_details(self) -> str:
        return (
            f"Commit:   {self.sha}\n"
            f"Author:   {self.author}\n"
            f"Date:     {self.date_iso}\n"
            f"Title:    {self.subject}\n"
            f"Name-rev: {self.name_rev}\n"
        )


class BranchNode(HasTraits):
    name = Str
    commits = List(Instance(CommitNode))

    label = Property(Str, depends_on="name,commits")

    def _get_label(self) -> str:
        return f"{self.name}  ({len(self.commits)} commits touching file)"


class BranchRoot(HasTraits):
    branches = List(Instance(BranchNode))
    label = Str("Branches view")


class HistoryRoot(HasTraits):
    heads = List(Instance(CommitNode))
    label = Str("History view")


# -----------------------------
# App model
# -----------------------------

class AppModel(HasTraits):
    repo_path = Str
    file_path = Str

    mode = Enum("Branches", "History")

    # Branches mode options
    branch_filter = Str

    # History mode options
    start_ref = Str("HEAD")
    max_commits = Int(500)
    include_remotes = Bool(False)
    show_name_rev = Bool(True)

    refresh = Button("Refresh")

    root = Any  # BranchRoot or HistoryRoot
    selected = Any
    status = Str

    selected_details = Property(Str, depends_on="selected")

    def _root_default(self) -> TypingAny:
        return BranchRoot(branches=[])

    def _get_selected_details(self) -> str:
        sel = self.selected
        if isinstance(sel, CommitNode):
            return sel.details
        if isinstance(sel, BranchNode):
            return f"Branch: {sel.name}\nCommits shown: {len(sel.commits)}\n"
        if isinstance(sel, (BranchRoot, HistoryRoot)):
            return sel.label
        return ""

    def _make_tree_editor(self) -> TreeEditor:
        return TreeEditor(
            nodes=[
                TreeNode(node_for=[BranchRoot], auto_open=True, children="branches", label="label"),
                TreeNode(node_for=[HistoryRoot], auto_open=True, children="heads", label="label"),
                TreeNode(node_for=[BranchNode], auto_open=False, children="commits", label="label"),
                TreeNode(node_for=[CommitNode], auto_open=False, children="parents", label="label"),
            ],
            editable=False,
            selected="selected",
            hide_root=False,
        )

    def _refresh_fired(self) -> None:
        self.reload()

    def reload(self) -> None:
        try:
            self.selected = None
            self.status = ""

            if not self.repo_path.strip():
                raise GitError("Repo path is empty.")
            if not self.file_path.strip():
                raise GitError("File path is empty.")

            repo_dir = Path(self.repo_path).expanduser().resolve()
            if not repo_dir.exists():
                raise GitError("Repo path does not exist.")

            repo_root = _find_repo_root(repo_dir)

            file_abs = _resolve_file_abs(repo_dir=repo_dir, repo_root=repo_root, file_path_str=self.file_path)
            if not file_abs.exists():
                raise GitError(f"File does not exist: {file_abs}")

            file_rel = _relpath_in_repo(repo_root, file_abs)

            if self.mode == "Branches":
                self._build_branches(repo_root, file_rel)
            else:
                self._build_history(repo_root, file_rel)

        except Exception as e:
            self.status = f"Error: {e}"
            self.root = BranchRoot(branches=[]) if self.mode == "Branches" else HistoryRoot(heads=[])

    def _build_branches(self, repo_root: Path, file_rel: Path) -> None:
        branches = _list_local_branches(repo_root)
        bf = self.branch_filter.strip()
        if bf:
            branches = [b for b in branches if bf.lower() in b.lower()]

        branch_nodes: TList[BranchNode] = []
        for b in branches:
            commits = _commits_touching_file(repo_root, b, file_rel)
            commit_nodes = [
                CommitNode(
                    sha=c.sha,
                    author=c.author,
                    date_iso=c.date_iso,
                    subject=c.subject,
                    parents=[],
                    name_rev="",
                )
                for c in commits
            ]
            branch_nodes.append(BranchNode(name=b, commits=commit_nodes))

        branch_nodes.sort(key=lambda bn: (-len(bn.commits), bn.name.lower()))
        self.root = BranchRoot(branches=branch_nodes, label="Branches view")
        self.status = f"{repo_root} | {file_rel} | {len(branch_nodes)} branches"

    def _build_history(self, repo_root: Path, file_rel: Path) -> None:
        start = self.start_ref.strip() or "HEAD"
        rows = _rev_list_with_parents(repo_root, start, file_rel, max(1, int(self.max_commits)))

        if not rows:
            self.root = HistoryRoot(heads=[], label="History view")
            self.status = f"No history found for {file_rel} from {start}."
            return

        all_shas: TList[str] = []
        seen: set[str] = set()
        for sha, parents in rows:
            if sha not in seen:
                seen.add(sha)
                all_shas.append(sha)
            for p in parents:
                if p not in seen:
                    seen.add(p)
                    all_shas.append(p)

        metas = _fetch_commit_meta(repo_root, all_shas)
        name_revs = _name_rev_map(repo_root, all_shas, include_remotes=bool(self.include_remotes)) if self.show_name_rev else {}

        nodes: Dict[str, CommitNode] = {}

        def get_node(sha: str) -> CommitNode:
            if sha in nodes:
                return nodes[sha]
            m = metas.get(sha)
            node = CommitNode(
                sha=sha,
                author=(m.author if m else ""),
                date_iso=(m.date_iso if m else ""),
                subject=(m.subject if m else ""),
                parents=[],
                name_rev=name_revs.get(sha, ""),
            )
            nodes[sha] = node
            return node

        for sha, parents in rows:
            n = get_node(sha)
            n.parents = [get_node(p) for p in parents]

        head_sha = rows[0][0]
        self.root = HistoryRoot(heads=[get_node(head_sha)], label="History view")
        self.status = (
            f"{repo_root} | {file_rel} | from {start} | up to {self.max_commits} commits"
            + (" | incl remotes" if self.include_remotes else "")
        )

    def traits_view(self) -> View:
        tree_editor = self._make_tree_editor()
        return View(
            VGroup(
                HGroup(
                    Item("repo_path", label="Repo", editor=DirectoryEditor()),
                    Item("file_path", label="File", editor=FileEditor()),
                ),
                HGroup(
                    Item("mode", label="Mode"),
                    UItem("refresh"),
                ),
                HGroup(
                    # Branch mode controls
                    VGroup(
                        Item("branch_filter", label="Branch filter"),
                        visible_when='mode == "Branches"',
                        show_border=True,
                        label="Branches options",
                    ),
                    # History mode controls
                    VGroup(
                        Item("start_ref", label="Start ref"),
                        Item("max_commits", label="Max commits"),
                        Item("include_remotes", label="Include remotes"),
                        Item("show_name_rev", label="Show name-rev"),
                        visible_when='mode == "History"',
                        show_border=True,
                        label="History options",
                    ),
                ),
                HGroup(
                    VGroup(
                        UItem("root", editor=tree_editor, style="custom"),
                        show_border=True,
                        label="Tree",
                    ),
                    VGroup(
                        Item("selected_details", style="readonly", show_label=False),
                        show_border=True,
                        label="Details",
                    ),
                ),
                Item("status", style="readonly", show_label=False),
            ),
            title="Git file views (TraitsUI): Branches + History",
            width=1200,
            height=720,
            resizable=True,
        )


def main() -> None:
    model = AppModel(
        repo_path=str(Path.cwd()),
        file_path="flow_list_str_editor.py",  # can be relative; Browse will set absolute
        mode="Branches",
    )
    model.reload()
    model.configure_traits()


if __name__ == "__main__":
    main()
