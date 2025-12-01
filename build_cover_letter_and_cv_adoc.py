#!/usr/bin/env python3
# build_cover_letter_and_cv_atext.py
"""
Builds a single `cv.adoc` from a Cover Letter DOCX and a CV DOCX.
- Output: YAML front-matter + CL body + CV as [appendix]
- Uses Pandoc under the hood; requires it in PATH.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, Any

from traits.api import HasTraits, File, Str, TraitError
import yaml  # pip install PyYAML

# ---------------- AdocBuilder ----------------

class AdocBuilder(HasTraits):
    """
    Build a single `cv.adoc` from two DOCX files (Cover Letter + CV).

    Output: YAML front matter + cover letter body + CV as [appendix].
    Requirements: Pandoc in PATH; PyYAML installed.
    """

    # Enforce real files at assignment time
    cover: Path = File(exists=True, allow_none=False)
    cv: Path    = File(exists=True, allow_none=False)

    # Output may not exist yet; default provided
    out: Path   = File(exists=False)

    schema: str = Str("cv_atext_v1")
    wrap: str   = Str("none")
    ref_loc: str= Str("block")

    def __call__(self, cover: str = None, cv: str = None, out: str = 'cv.adoc', **kw):
        """Generate cv.adoc (front-matter + CL body + CV as appendix)

        Args:
          cover: Path to cover-letter .docx (must exist)
          cv:    Path to CV .docx (must exist)
          out:   Output .adoc path (default: cv.adoc)
          schema: YAML schema tag to embed in front matter
          wrap:   Pandoc --wrap (none/auto/preserve)
          ref_loc: Pandoc --reference-location (block/section)
        """
        self.__init__(cover=cover or self.cover, cv=cv or self.cv, out=out, **kw)
        cl_adoc = self._clean_title(self._pandoc_docx_to_adoc(self.cover))
        cv_adoc = self._ensure_appendix(self._clean_title(self._pandoc_docx_to_adoc(self.cv)))

        front = {
            "_schema": str(self.schema),
            "shared": self._extract_shared(cl_adoc, cv_adoc),
            "cl": {},
            "cv": {},
        }
        body = (
            "// >>> BEGIN cl\n" + cl_adoc +
            "// <<< END cl\n\n" +
            "// >>> BEGIN cv\n" + cv_adoc +
            "// <<< END cv\n"
        )
        text = f"---\n{yaml.safe_dump(front, sort_keys=True, allow_unicode=True)}---\n{body}"
        open(self.out, "w", encoding="utf-8").write(text)
        print(f"Wrote {self.out}")

    # ---- helpers (unchanged logic) ----
    def _run(self, cmd: list[str], *, input_bytes: bytes | None = None) -> bytes:
        p = subprocess.run(cmd, input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if p.returncode != 0:
            raise RuntimeError(f"Command failed ({' '.join(cmd)}):\n{p.stderr.decode('utf-8', 'ignore')}")
        return p.stdout

    def _pandoc_docx_to_adoc(self, docx: Path) -> str:
        args = ["pandoc", str(docx), "-f", "docx", "-t", "asciidoc", "--wrap", self.wrap, "--reference-location", self.ref_loc]
        return self._run(args).decode("utf-8", "replace")

    @staticmethod
    def _clean_title(text: str) -> str:
        ls = text.splitlines()
        if ls and not ls[0].startswith("="):
            i = next((i for i, l in enumerate(ls[:5]) if l.strip()), 0)
            ls.insert(0, f"= {ls[i].strip()}")
        s = "\n".join(ls).strip()
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s + "\n"

    @staticmethod
    def _ensure_appendix(cv_adoc: str) -> str:
        ls = cv_adoc.splitlines()
        for i, ln in enumerate(ls[:20]):
            if ln.startswith("== "): ls.insert(i, "[appendix]"); break
            if ln.startswith("= "):  ls.insert(i + 1, "[appendix]"); break
        return "\n".join(ls) + "\n"

    @staticmethod
    def _guess_name(text: str) -> str | None:
        for ln in text.splitlines():
            s = ln.strip()
            if s and not s.startswith(("=", "[", "*", "_", "To ")):
                if 2 <= len(s.split()) <= 5 and s[0].isupper():
                    return s
        return None

    @staticmethod
    def _extract_shared(cl_text: str, cv_text: str) -> Dict[str, Any]:
        blob = cl_text + "\n" + cv_text
        meta: Dict[str, Any] = {}
        m_email = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", blob, re.I)
        m_phone = re.search(r"(?:\+?\d[\d\s\-()]{6,}\d)", blob)
        m_li = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/[^\s]+", blob, re.I)
        name = AdocBuilder._guess_name(cl_text) or AdocBuilder._guess_name(cv_text)
        if name:    meta["name"] = name
        if m_email: meta["email"] = m_email.group(0)
        if m_phone: meta["mobile"] = m_phone.group(0)
        if m_li:
            url = m_li.group(0)
            meta["linkedin_profile"] = url if url.startswith("http") else "https://" + url
        return meta


if __name__ == "__main__":
    import fire

    class LocalActionGroup(fire.helptext.ActionGroup):
        def Add(self, name, member=None):
            if member is not None and name in AdocBuilder.__dict__:
                self.names.append(name)
                self.members.append(member)

    fire.helptext.ActionGroup = LocalActionGroup
    fire.Fire(AdocBuilder(cover='Joakim_Pettersson-Engineer-your organisation.docx', cv='Joakim_Pettersson_CV.docx'))
