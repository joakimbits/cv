# file: git_file_branch_tree.py
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List as TList, Sequence

from traits.api import Any, Button, HasTraits, Instance, List, Property, Str, observe
from traitsui.api import HGroup, Item, TreeEditor, TreeNode, UItem, VGroup, View


class GitError(RuntimeError):
    pass


def _run_git(repo_dir: Path, args: Sequence[str], timeout_s: int = 20) -> str:
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
        msg = e.stderr.strip() or e.stdout.strip() or "Unknown git error."
        raise GitError(msg) from e


def _find_repo_root(start: Path) -> Path:
    out = _run_git(start, ["rev-parse", "--show-toplevel"])
    root = Path(out.strip())
    if not root.exists():
        raise GitError("Failed to resolve repo root.")
    return root


def _relpath_in_repo(repo_root: Path, file_path: Path) -> Path:
    fp = file_path.expanduser().resolve()
    rr = repo_root.expanduser().resolve()
    try:
        return fp.relative_to(rr)
    except ValueError as e:
        raise GitError("File path is not inside the selected repository.") from e


def _list_local_branches(repo_root: Path) -> TList[str]:
    out = _run_git(repo_root, ["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    branches = [b.strip() for b in out.splitlines() if b.strip()]
    return sorted(branches, key=str.casefold)


@dataclass(frozen=True)
class CommitInfo:
    sha: str
    author: str
    date_iso: str
    subject: str


def _parse_git_log_lines(lines: Iterable[str]) -> TList[CommitInfo]:
    commits: TList[CommitInfo] = []
    for line in lines:
        if not line:
            continue
        parts = line.split("\x1f")
        if len(parts) != 4:
            continue
        sha, author, date_iso, subject = (p.strip() for p in parts)
        if sha:
            commits.append(CommitInfo(sha=sha, author=author, date_iso=date_iso, subject=subject))
    return commits


def _commits_touching_file(repo_root: Path, branch: str, file_rel: Path) -> TList[CommitInfo]:
    fmt = "%H%x1f%an%x1f%ad%x1f%s"
    out = _run_git(
        repo_root,
        ["log", "--date=iso-strict", f"--pretty=format:{fmt}", branch, "--", str(file_rel)],
        timeout_s=40,
    )
    return _parse_git_log_lines(out.splitlines())


class CommitNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str

    label = Property(Str, depends_on="sha,subject")
    details = Property(Str, depends_on="sha,author,date_iso,subject")

    def _get_label(self) -> str:
        short = self.sha[:10] if self.sha else ""
        return f"{short}  {self.subject}"

    def _get_details(self) -> str:
        return (
            f"Commit: {self.sha}\n"
            f"Author: {self.author}\n"
            f"Date:   {self.date_iso}\n"
            f"Title:  {self.subject}\n"
        )


class BranchNode(HasTraits):
    name = Str
    commits = List(Instance(CommitNode))

    label = Property(Str, depends_on="name,commits")

    def _get_label(self) -> str:
        return f"{self.name}  ({len(self.commits)} commits touching file)"


class RepoTreeModel(HasTraits):
    repo_path = Str
    file_path = Str
    branch_filter = Str

    refresh = Button("Refresh")

    branches = List(Instance(BranchNode))
    selected = Any
    status = Str

    # Root object for TreeEditor must be HasTraits, not a TraitListObject.
    tree_root = Property(Any)

    selected_details = Property(Str, depends_on="selected")

    def _get_tree_root(self) -> Any:
        return self

    def _get_selected_details(self) -> str:
        sel = self.selected
        if isinstance(sel, CommitNode):
            return sel.details
        if isinstance(sel, BranchNode):
            return f"Branch: {sel.name}\nCommits touching file: {len(sel.commits)}\n"
        return ""

    def _make_tree_editor(self) -> TreeEditor:
        return TreeEditor(
            nodes=[
                TreeNode(
                    node_for=[RepoTreeModel],
                    auto_open=True,
                    children="branches",
                    label="=status",
                ),
                TreeNode(
                    node_for=[BranchNode],
                    auto_open=False,
                    children="commits",
                    label="label",
                ),
                TreeNode(
                    node_for=[CommitNode],
                    auto_open=False,
                    children="",
                    label="label",
                ),
            ],
            editable=False,
            selected="selected",
            hide_root=True,
        )

    def _load(self) -> None:
        self.status = ""
        self.branches = []

        if not self.repo_path.strip():
            raise GitError("Repo path is empty.")
        if not self.file_path.strip():
            raise GitError("File path is empty.")

        repo_dir = Path(self.repo_path).expanduser().resolve()
        if not repo_dir.exists():
            raise GitError("Repo path does not exist.")
        repo_root = _find_repo_root(repo_dir)

        file_abs = Path(self.file_path).expanduser().resolve()
        file_rel = _relpath_in_repo(repo_root, file_abs)

        branches = _list_local_branches(repo_root)
        bf = self.branch_filter.strip()
        if bf:
            branches = [b for b in branches if bf.lower() in b.lower()]

        branch_nodes: TList[BranchNode] = []
        for b in branches:
            commits = _commits_touching_file(repo_root, b, file_rel)
            commit_nodes = [
                CommitNode(sha=c.sha, author=c.author, date_iso=c.date_iso, subject=c.subject)
                for c in commits
            ]
            branch_nodes.append(BranchNode(name=b, commits=commit_nodes))

        branch_nodes.sort(key=lambda bn: (-len(bn.commits), bn.name.lower()))
        self.branches = branch_nodes
        self.status = f"{repo_root} | {file_rel} | {len(branch_nodes)} branches"

    @observe("refresh")
    def _on_refresh(self, _event) -> None:
        self.reload()

    def reload(self) -> None:
        try:
            self._load()
        except Exception as e:
            self.status = f"Error: {e}"
            self.branches = []

    # Define view at runtime so RepoTreeModel exists for node_for=[RepoTreeModel].
    def traits_view(self) -> View:
        tree_editor = self._make_tree_editor()
        return View(
            VGroup(
                HGroup(
                    Item("repo_path", label="Repo", width=0.5),
                    Item("file_path", label="File", width=0.5),
                ),
                HGroup(
                    Item("branch_filter", label="Branch filter (substring)", width=0.7),
                    UItem("refresh"),
                ),
                HGroup(
                    VGroup(
                        UItem("tree_root", editor=tree_editor, style="custom"),
                        show_border=True,
                        label="Branches → Commits touching file",
                    ),
                    VGroup(
                        Item("selected_details", style="readonly", show_label=False),
                        show_border=True,
                        label="Details",
                    ),
                ),
                Item("status", style="readonly", show_label=False),
            ),
            title="Git branches tree for a file (TraitsUI)",
            width=1100,
            height=650,
            resizable=True,
        )


def main() -> None:
    model = RepoTreeModel(repo_path=str(Path.cwd()), file_path='flow_list_str_editor.py', branch_filter="")
    model.reload()
    model.configure_traits()


if __name__ == "__main__":
    main()
