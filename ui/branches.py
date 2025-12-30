# file: branches_git_pathspec.py
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
    Directory,
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
    HGroup,
    Item,
    TreeEditor,
    TreeNode,
    UItem,
    VGroup,
    View,
)


class GitError(RuntimeError):
    def __init__(self, message: str, *, cmd: str = "", stderr: str = "") -> None:
        super().__init__(message)
        self.cmd = cmd
        self.stderr = stderr


def _fmt_cmd(args: Sequence[str]) -> str:
    return "git " + " ".join(shlex.quote(a) for a in args)


def _run_git(repo_root: Path, args: Sequence[str], timeout_s: int = 60) -> str:
    cmd = ["git", "-C", str(repo_root), *args]
    try:
        cp = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        return cp.stdout
    except FileNotFoundError as e:
        raise GitError("git executable not found in PATH.", cmd=_fmt_cmd(cmd), stderr=str(e)) from e
    except subprocess.TimeoutExpired as e:
        raise GitError("git command timed out.", cmd=_fmt_cmd(cmd), stderr=str(e)) from e
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        msg = stderr or stdout or "Unknown git error."
        raise GitError(msg, cmd=_fmt_cmd(cmd), stderr=stderr) from e


def _show_error_dialog(message: str, title: str) -> None:
    try:
        from pyface.message_dialog import error as msg_error
    except Exception:
        return

    try:
        msg_error(message, title=title)  # some versions
    except TypeError:
        msg_error(None, message, title)  # other versions


def _find_repo_root(repo_dir: Path) -> Path:
    out = _run_git(repo_dir, ["rev-parse", "--show-toplevel"], timeout_s=30)
    root = Path(out.strip())
    if not root.exists():
        raise GitError("Failed to resolve repo root.", cmd="git rev-parse --show-toplevel")
    return root


def _normalize_pathspec(s: str) -> str:
    """
    Git pathspecs are repo-relative; normalize Windows slashes.
    Keep it intentionally minimal: no filesystem probing.
    """
    return (s or "").strip().replace("\\", "/")


def _chunked(xs: TList[str], chunk_size: int) -> Iterable[TList[str]]:
    for i in range(0, len(xs), chunk_size):
        yield xs[i : i + chunk_size]


# -----------------------------
# Branches mode: branch -> commits that match pathspec
# -----------------------------

@dataclass(frozen=True)
class TouchCommitInfo:
    sha: str
    author: str
    date_iso: str
    subject: str


def _list_local_branches(repo_root: Path) -> TList[str]:
    out = _run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"], timeout_s=30)
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


def _commits_touching_pathspec(repo_root: Path, branch: str, pathspec: str) -> TList[TouchCommitInfo]:
    fmt = "%H%x1f%an%x1f%ad%x1f%s"
    out = _run_git(
        repo_root,
        ["log", "--date=iso-strict", f"--pretty=format:{fmt}", branch, "--", pathspec],
        timeout_s=120,
    )
    return _parse_git_log_lines(out.splitlines())


# -----------------------------
# History / Branch-out: commit graph subset from `git log --pretty="%H %P" ... -- <pathspec>`
# -----------------------------

@dataclass(frozen=True)
class CommitMeta:
    sha: str
    parents: TList[str]
    author: str
    date_iso: str
    subject: str


def _log_with_parents(
    repo_root: Path,
    *,
    pathspec: str,
    max_commits: int,
    start_ref: str,
    all_refs: bool,
) -> TList[Tuple[str, TList[str]]]:
    args: TList[str] = ["log", "--topo-order", f"-n{max_commits}", "--pretty=format:%H %P"]
    if all_refs:
        args.insert(1, "--all")
    else:
        args.append(start_ref)
    args.extend(["--", pathspec])

    out = _run_git(repo_root, args, timeout_s=180)

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
            timeout_s=180,
        )
        metas.update(_parse_show_records(out))
    return metas


def _name_rev_map(
    repo_root: Path,
    shas: TList[str],
    include_remotes: bool,
    all_refs: bool = False,   # ✅ default fixes your TypeError
) -> Dict[str, str]:
    if not shas:
        return {}

    base_args: TList[str] = ["name-rev", "--name-only"]
    if all_refs:
        base_args.append("--all")
    else:
        refs = ["refs/heads/*"]
        if include_remotes:
            refs.append("refs/remotes/*")
        base_args.append(f"--refs={','.join(refs)}")

    out_map: Dict[str, str] = {}
    for chunk in _chunked(shas, chunk_size=200):
        out = _run_git(repo_root, [*base_args, *chunk], timeout_s=180)
        names = [ln.strip() for ln in out.splitlines()]
        for sha, name in zip(chunk, names, strict=False):
            out_map[sha] = "" if (not name or name.lower() == "undefined") else name
    return out_map


# -----------------------------
# Traits nodes / roots
# -----------------------------

class CommitNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str

    parents = List(Instance("CommitNode"))
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


class ForwardCommitNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str

    children = List(Instance("ForwardCommitNode"))
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
        return f"{self.name}  ({len(self.commits)})"


class BranchRoot(HasTraits):
    branches = List(Instance(BranchNode))
    label = Str("Branches")


class HistoryRoot(HasTraits):
    heads = List(Instance(CommitNode))
    label = Str("History (parents)")


class BranchOutRoot(HasTraits):
    roots = List(Instance(ForwardCommitNode))
    label = Str("Branch-out (children)")


# -----------------------------
# App model
# -----------------------------

class AppModel(HasTraits):
    repo_path = Directory
    pathspec = Str  # ✅ git pathspec, not filesystem file

    mode = Enum("Branches", "History", "Branch-out")

    # Branches options
    branch_filter = Str

    # History options
    start_ref = Str("HEAD")
    max_commits = Int(800)
    include_remotes = Bool(False)
    show_name_rev = Bool(True)

    # Branch-out options
    branch_out_all_refs = Bool(True)

    # Debug / UX
    crash_on_error = Bool(False)
    show_error_dialog = Bool(True)

    refresh = Button("Refresh")

    root = Any
    selected = Any
    status = Str
    last_git_cmd = Str
    last_git_stderr = Str

    selected_details = Property(Str, depends_on="selected")

    def _root_default(self) -> TypingAny:
        return BranchRoot(branches=[], label="Branches")

    def _get_selected_details(self) -> str:
        sel = self.selected
        if isinstance(sel, (CommitNode, ForwardCommitNode)):
            return sel.details
        if isinstance(sel, BranchNode):
            return f"Branch: {sel.name}\nCommits: {len(sel.commits)}\n"
        if isinstance(sel, (BranchRoot, HistoryRoot, BranchOutRoot)):
            return sel.label
        return ""

    def _make_tree_editor(self) -> TreeEditor:
        return TreeEditor(
            nodes=[
                TreeNode(node_for=[BranchRoot], auto_open=True, children="branches", label="label"),
                TreeNode(node_for=[HistoryRoot], auto_open=True, children="heads", label="label"),
                TreeNode(node_for=[BranchOutRoot], auto_open=True, children="roots", label="label"),
                TreeNode(node_for=[BranchNode], auto_open=False, children="commits", label="label"),
                TreeNode(node_for=[CommitNode], auto_open=False, children="parents", label="label"),
                TreeNode(node_for=[ForwardCommitNode], auto_open=False, children="children", label="label"),
            ],
            editable=False,
            selected="selected",
            hide_root=False,
        )

    def _refresh_fired(self) -> None:
        self.reload()

    def _fail(self, e: Exception) -> None:
        msg = f"{type(e).__name__}: {e}"
        self.status = f"Error: {msg}"

        if isinstance(e, GitError):
            self.last_git_cmd = e.cmd
            self.last_git_stderr = e.stderr
        else:
            self.last_git_cmd = ""
            self.last_git_stderr = ""

        if self.show_error_dialog:
            details = self.last_git_cmd
            if self.last_git_stderr:
                details += "\n\n" + self.last_git_stderr
            _show_error_dialog(f"{self.status}\n\n{details}".strip(), "Git tree error")

        if self.crash_on_error:
            raise

    def reload(self) -> None:
        self.selected = None
        self.status = ""
        self.last_git_cmd = ""
        self.last_git_stderr = ""

        repo_dir = Path(str(self.repo_path)).expanduser().resolve()
        if not repo_dir.exists():
            raise GitError(f"Repo path does not exist: {repo_dir}")

        repo_root = _find_repo_root(repo_dir)

        ps = _normalize_pathspec(self.pathspec)
        if not ps:
            raise GitError("Pathspec is empty (e.g. README.md).")

        if self.mode == "Branches":
            self._build_branches(repo_root, ps)
        elif self.mode == "History":
            self._build_history(repo_root, ps)
        else:
            self._build_branch_out(repo_root, ps)

    def _build_branches(self, repo_root: Path, pathspec: str) -> None:
        branches = _list_local_branches(repo_root)
        bf = self.branch_filter.strip()
        if bf:
            branches = [b for b in branches if bf.lower() in b.lower()]

        branch_nodes: TList[BranchNode] = []
        for b in branches:
            commits = _commits_touching_pathspec(repo_root, b, pathspec)
            commit_nodes = [
                CommitNode(sha=c.sha, author=c.author, date_iso=c.date_iso, subject=c.subject, parents=[], name_rev="")
                for c in commits
            ]
            branch_nodes.append(BranchNode(name=b, commits=commit_nodes))

        branch_nodes.sort(key=lambda bn: (-len(bn.commits), bn.name.lower()))
        self.root = BranchRoot(branches=branch_nodes, label=f"Branches ({len(branch_nodes)})")
        self.status = f"{repo_root} | {pathspec} | branches={len(branch_nodes)}"

    def _build_history(self, repo_root: Path, pathspec: str) -> None:
        start = self.start_ref.strip() or "HEAD"
        rows = _log_with_parents(
            repo_root,
            pathspec=pathspec,
            max_commits=max(1, int(self.max_commits)),
            start_ref=start,
            all_refs=False,
        )

        if not rows:
            self.root = HistoryRoot(heads=[], label="History (parents) (0)")
            self.status = f"{repo_root} | {pathspec} | rows=0 (no commits found from {start})"
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
            get_node(sha).parents = [get_node(p) for p in parents]

        head_sha = rows[0][0]
        self.root = HistoryRoot(heads=[get_node(head_sha)], label=f"History (parents) ({len(rows)})")
        self.status = f"{repo_root} | {pathspec} | rows={len(rows)} | from {start}"

    def _build_branch_out(self, repo_root: Path, pathspec: str) -> None:
        start = self.start_ref.strip() or "HEAD"
        rows = _log_with_parents(
            repo_root,
            pathspec=pathspec,
            max_commits=max(1, int(self.max_commits)),
            start_ref=start,
            all_refs=bool(self.branch_out_all_refs),
        )

        if not rows:
            scope = "--all" if self.branch_out_all_refs else start
            self.root = BranchOutRoot(roots=[], label="Branch-out (children) (0)")
            self.status = f"{repo_root} | {pathspec} | rows=0 (no commits found, scope={scope})"
            return

        node_shas = {sha for sha, _ in rows}

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

        nodes: Dict[str, ForwardCommitNode] = {}

        def get_node(sha: str) -> ForwardCommitNode:
            if sha in nodes:
                return nodes[sha]
            m = metas.get(sha)
            node = ForwardCommitNode(
                sha=sha,
                author=(m.author if m else ""),
                date_iso=(m.date_iso if m else ""),
                subject=(m.subject if m else ""),
                children=[],
                name_rev=name_revs.get(sha, ""),
            )
            nodes[sha] = node
            return node

        children_map: Dict[str, TList[str]] = {sha: [] for sha in node_shas}
        for child_sha, parents in rows:
            for p in parents:
                if p in node_shas:
                    children_map[p].append(child_sha)

        for parent_sha, child_shas in children_map.items():
            get_node(parent_sha).children = [get_node(c) for c in child_shas]

        roots: TList[ForwardCommitNode] = []
        for sha, parents in rows:
            if not any(p in node_shas for p in parents):
                roots.append(get_node(sha))

        roots = list(dict.fromkeys(roots))
        scope = "--all" if self.branch_out_all_refs else start
        self.root = BranchOutRoot(roots=roots, label=f"Branch-out (children) ({len(rows)})")
        self.status = f"{repo_root} | {pathspec} | rows={len(rows)} | scope={scope}"

    def traits_view(self) -> View:
        tree_editor = self._make_tree_editor()
        return View(
            VGroup(
                HGroup(
                    Item("repo_path", label="Repo", editor=DirectoryEditor()),
                    Item("pathspec", label="Git path", width=0.5),
                ),
                HGroup(
                    Item("mode", label="Mode"),
                    UItem("refresh"),
                    Item("crash_on_error", label="Crash"),
                    Item("show_error_dialog", label="Dialog"),
                ),
                HGroup(
                    VGroup(
                        Item("branch_filter", label="Branch filter"),
                        visible_when='mode == "Branches"',
                        show_border=True,
                        label="Branches options",
                    ),
                    VGroup(
                        Item("start_ref", label="Start ref"),
                        Item("max_commits", label="Max commits"),
                        Item("include_remotes", label="Include remotes"),
                        Item("show_name_rev", label="Show name-rev"),
                        visible_when='mode != "Branches"',
                        show_border=True,
                        label="History options",
                    ),
                    VGroup(
                        Item("branch_out_all_refs", label="Use --all scope"),
                        visible_when='mode == "Branch-out"',
                        show_border=True,
                        label="Branch-out options",
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
                VGroup(
                    Item("last_git_cmd", style="readonly", label="Last git"),
                    Item("last_git_stderr", style="readonly", label="stderr"),
                    show_border=True,
                    label="Debug",
                ),
            ),
            title="Git views (TraitsUI): Branches + History + Branch-out (Git pathspec)",
            width=1250,
            height=820,
            resizable=True,
        )


def main() -> None:
    model = AppModel(
        repo_path=r"C:\home\joakimbits\normalize",
        pathspec="README.md",
        mode="Branches",
    )
    model.reload()
    model.configure_traits()


if __name__ == "__main__":
    main()
