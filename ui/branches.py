# file: git_file_history_tree.py
from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List as TList, Sequence, Tuple

from traits.api import Any, Bool, Button, HasTraits, Instance, Int, List, Property, Str, observe
from traitsui.api import HGroup, Item, TreeEditor, TreeNode, UItem, VGroup, View


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


def _relpath_in_repo(repo_root: Path, file_path: Path) -> Path:
    fp = file_path.expanduser().resolve()
    rr = repo_root.expanduser().resolve()
    try:
        return fp.relative_to(rr)
    except ValueError as e:
        raise GitError("File path is not inside the selected repository.") from e


def _chunked(xs: TList[str], chunk_size: int) -> Iterable[TList[str]]:
    for i in range(0, len(xs), chunk_size):
        yield xs[i : i + chunk_size]


@dataclass(frozen=True)
class CommitMeta:
    sha: str
    parents: TList[str]
    author: str
    date_iso: str
    subject: str


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
    for chunk in _chunked(shas, chunk_size=200):  # Windows-safe
        out = _run_git(repo_root, ["show", "-s", "--date=iso-strict", f"--pretty=format:{fmt}", *chunk], timeout_s=60)
        metas.update(_parse_show_records(out))
    return metas


def _rev_list_with_parents(
    repo_root: Path, start_ref: str, file_rel: Path, max_commits: int
) -> TList[Tuple[str, TList[str]]]:
    out = _run_git(
        repo_root,
        ["rev-list", "--parents", "--topo-order", f"-n{max_commits}", start_ref, "--", str(file_rel)],
        timeout_s=60,
    )
    rows: TList[Tuple[str, TList[str]]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        toks = line.split()
        rows.append((toks[0], toks[1:]))
    return rows


def _branch_tip_decorations(repo_root: Path, include_remotes: bool) -> Dict[str, TList[str]]:
    """
    tip_sha -> [ref short names]
    (these are branch tips only; often none of these commits touch your file)
    """
    refs = ["refs/heads"]
    if include_remotes:
        refs.append("refs/remotes")

    out = _run_git(repo_root, ["for-each-ref", "--format=%(refname:short)\t%(objectname)", *refs], timeout_s=30)

    tip_map: Dict[str, TList[str]] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if "\t" not in line:
            continue
        name, sha = line.split("\t", 1)
        name, sha = name.strip(), sha.strip()
        if not (name and sha):
            continue
        tip_map.setdefault(sha, []).append(name)

    for sha, names in tip_map.items():
        names.sort(key=str.casefold)
        tip_map[sha] = names

    return tip_map


def _name_rev_map(repo_root: Path, shas: TList[str], include_remotes: bool) -> Dict[str, str]:
    """
    sha -> "best name" like: main, main~12, feature^2~3
    Fast, and gives you a branch-ish label for every commit.
    """
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
            timeout_s=60,
        )
        names = [ln.strip() for ln in out.splitlines() if ln.strip()]
        # name-rev with --name-only prints one name per input sha, in order
        for sha, name in zip(chunk, names, strict=False):
            out_map[sha] = name
    return out_map


class CommitNode(HasTraits):
    sha = Str
    author = Str
    date_iso = Str
    subject = Str

    parents = List(Instance("CommitNode"))

    tip_refs = List(Str)     # exact refs that point to this commit (often empty)
    name_rev = Str           # always-ish present: main~12, etc.

    label = Property(Str, depends_on="sha,subject,date_iso,tip_refs,name_rev")
    details = Property(Str, depends_on="sha,author,date_iso,subject,tip_refs,name_rev")

    def _get_label(self) -> str:
        short = self.sha[:10] if self.sha else ""
        date_part = self.date_iso[:10] if self.date_iso else ""
        if self.tip_refs:
            deco = f"[{', '.join(self.tip_refs)}]"
        elif self.name_rev:
            deco = f"[{self.name_rev}]"
        else:
            deco = ""
        return f"{short}  {date_part}  {self.subject}  {deco}".rstrip()

    def _get_details(self) -> str:
        tips = ", ".join(self.tip_refs) if self.tip_refs else ""
        return (
            f"Commit:   {self.sha}\n"
            f"Author:   {self.author}\n"
            f"Date:     {self.date_iso}\n"
            f"Title:    {self.subject}\n"
            f"Name-rev: {self.name_rev}\n"
            f"Tip refs: {tips}\n"
        )


class HistoryRoot(HasTraits):
    heads = List(Instance(CommitNode))

    label = Property(Str, depends_on="heads")

    def _get_label(self) -> str:
        if not self.heads:
            return "History"
        return f"History (from {self.heads[0].sha[:10]})"


class RepoHistoryModel(HasTraits):
    repo_path = Str
    file_path = Str

    start_ref = Str("HEAD")
    max_commits = Int(500)

    include_remotes = Bool(False)
    show_tip_refs = Bool(True)
    show_name_rev = Bool(True)

    refresh = Button("Refresh")

    root = Instance(HistoryRoot)
    selected = Any
    status = Str

    selected_details = Property(Str, depends_on="selected")
    tree_root = Property(Any)

    def _root_default(self) -> HistoryRoot:
        return HistoryRoot(heads=[])

    def _get_tree_root(self) -> Any:
        return self.root

    def _get_selected_details(self) -> str:
        sel = self.selected
        if isinstance(sel, CommitNode):
            return sel.details
        if isinstance(sel, HistoryRoot):
            return sel.label
        return ""

    def _make_tree_editor(self) -> TreeEditor:
        return TreeEditor(
            nodes=[
                TreeNode(node_for=[HistoryRoot], auto_open=True, children="heads", label="label"),
                TreeNode(node_for=[CommitNode], auto_open=False, children="parents", label="label"),
            ],
            editable=False,
            selected="selected",
            hide_root=False,
        )

    def _build_tree(self, repo_root: Path, file_rel: Path) -> None:
        start = self.start_ref.strip() or "HEAD"
        rows = _rev_list_with_parents(repo_root, start, file_rel, max(1, int(self.max_commits)))

        if not rows:
            self.root = HistoryRoot(heads=[])
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
        tip_decos = _branch_tip_decorations(repo_root, include_remotes=bool(self.include_remotes)) if self.show_tip_refs else {}
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
                tip_refs=tip_decos.get(sha, []),
                name_rev=name_revs.get(sha, ""),
            )
            nodes[sha] = node
            return node

        for sha, parents in rows:
            n = get_node(sha)
            n.parents = [get_node(p) for p in parents]

        head_sha = rows[0][0]
        self.root = HistoryRoot(heads=[get_node(head_sha)])
        self.status = (
            f"{repo_root} | {file_rel} | from {start} | up to {self.max_commits} commits"
            + (" | incl remotes" if self.include_remotes else "")
        )

    def reload(self) -> None:
        try:
            self.status = ""
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

            self._build_tree(repo_root, file_rel)
        except Exception as e:
            self.status = f"Error: {e}"
            self.root = HistoryRoot(heads=[])

    @observe("refresh")
    def _on_refresh(self, _event) -> None:
        self.reload()

    def traits_view(self) -> View:
        tree_editor = self._make_tree_editor()
        return View(
            VGroup(
                HGroup(
                    Item("repo_path", label="Repo", width=0.5),
                    Item("file_path", label="File", width=0.5),
                ),
                HGroup(
                    Item("start_ref", label="Start ref", width=0.2),
                    Item("max_commits", label="Max commits", width=0.15),
                    Item("include_remotes", label="Include remotes", width=0.15),
                    Item("show_name_rev", label="Show name-rev", width=0.15),
                    Item("show_tip_refs", label="Show tip refs", width=0.15),
                    UItem("refresh"),
                ),
                HGroup(
                    VGroup(
                        UItem("tree_root", editor=tree_editor, style="custom"),
                        show_border=True,
                        label="History tree (commit → parents)",
                    ),
                    VGroup(
                        Item("selected_details", style="readonly", show_label=False),
                        show_border=True,
                        label="Details",
                    ),
                ),
                Item("status", style="readonly", show_label=False),
            ),
            title="Git file history tree (TraitsUI) + branch names",
            width=1100,
            height=650,
            resizable=True,
        )


def main() -> None:
    model = RepoHistoryModel(repo_path=str(Path.cwd()), file_path="flow_list_str_editor.py", show_tip_refs=True)
    model.reload()
    model.configure_traits()


if __name__ == "__main__":
    main()
