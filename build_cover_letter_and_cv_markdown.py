#!/usr/bin/env python3.10
# build_cover_letter_and_cv_atext.py
"""
Builds a single GFM MD document from a Cover Letter DOCX and a CV DOCX.
- Output: CL body + CV as [appendix]
- Uses Pandoc under the hood; requires it in PATH.

Requirements:
$?/pandoc
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from traits.api import HasTraits, File, Str

# ---------------- AdocBuilder ----------------

class MarkdownBuilder(HasTraits):
    """
    Build a single `cover_and_cv.md` from two DOCX files (Cover Letter + CV).

    Requirements: Pandoc in PATH
    """

    # Enforce real files at assignment time
    cover: Path = File(exists=True, allow_none=False)
    cv: Path    = File(exists=True, allow_none=False)

    # Output may not exist yet; default provided
    out: Path   = File(exists=False)

    schema: str = Str("cv_atext_v1")
    wrap: str   = Str("none")
    ref_loc: str= Str("block")

    def __call__(self, cover: str = None, cv: str = None, out: str = 'cover_and_cv.md', **kw):
        """Generate cover_and_cv.md (front-matter + CL body + CV as appendix)

        Args:
          cover: Path to cover-letter .docx (must exist)
          cv:    Path to CV .docx (must exist)
          out:   Output .md path (default: cv.md)
          schema: YAML schema tag to embed in front matter
          wrap:   Pandoc --wrap (none/auto/preserve)
          ref_loc: Pandoc --reference-location (block/section)
        """
        self.__init__(cover=cover or self.cover, cv=cv or self.cv, out=out, **kw)
        cl = self._pandoc_docx_to_gfm(self.cover)
        cv = self._pandoc_docx_to_gfm(self.cv)
        body = (
                "<!-- >>> BEGIN cl -->\n" + cl + "\n<!-- <<< END cl -->\n\n" +
                "<!-- >>> BEGIN cv -->\n" + cv + "\n<!-- <<< END cv -->\n"
        )
        open(self.out, "w", encoding="utf-8").write(body)
        print(f"Wrote {self.out}")

    # ---- helpers ----
    def _run(self, cmd: list[str], *, input_bytes: bytes | None = None) -> bytes:
        p = subprocess.run(cmd, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed ({' '.join(cmd)}):\n{p.stderr.decode('utf-8', 'ignore')}")
        return p.stdout

    def _pandoc_docx_to_gfm(self, docx: Path, wrap="none"):
        args = ["pandoc", str(docx), "-f", "docx", "-t", "gfm", "--wrap", self.wrap]
        return re.sub(r'(?m)^>*\r?\n', '', self._run(args).decode("utf-8", "replace"))

    @classmethod
    def _drop_empty_blockquote_paras(md: str) -> str:
        # Normalize newlines so the regex is stable
        md = md.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse one or more blank blockquote paras (lines that are only '>') into a single newline
        md = re.sub(r'(?:\n>\s*\n)+', '\n', md)
        return md


if __name__ == "__main__":
    import fire

    class LocalActionGroup(fire.helptext.ActionGroup):
        def Add(self, name, member=None):
            if member is not None and name in MarkdownBuilder.__dict__:
                self.names.append(name)
                self.members.append(member)

    fire.helptext.ActionGroup = LocalActionGroup
    fire.Fire(MarkdownBuilder(cover='Joakim_Pettersson-Engineer-your organisation.docx', cv='Joakim_Pettersson_CV.docx'))
