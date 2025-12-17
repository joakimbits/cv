# cv.py
"""
Class-based CV & cover-letter generator for Joakim Pettersson.

Content corresponds to the compressed 2025-11-11 CV, with ONE deliberate change:

- The first PROFILE bullet ("Embedded software developer with 14+ years...")
  is removed to keep the base CV less branch-specific.

Styling is based on the original procedural cv.py:
- A4 page, 25/20 mm margins
- Calibri 10 pt
- Accent blue section headings
- Bold dark-blue hyperlinks (no underline)
- Hanging indents for Technology and artifact lines
"""

from __future__ import annotations

import regex as re
import docx
from docx.document import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, Mm, RGBColor
from docx.enum.text import WD_BREAK
from docx.enum.style import WD_STYLE_TYPE
from traits.api import HasTraits, File, List, Str, Tuple, Int
from numpy import array, argwhere
from traitsui.api import View, Item, VGroup, HGroup, Group, Tabbed, TreeEditor, TreeNode

# ---- Branding / colors ----
ACCENT_BLUE = RGBColor(0x00, 0x66, 0xB3)  # Additude headings
LINK_BLUE_HEX = "004A99"                  # Bold dark blue for hyperlinks (no underline)

# =====================================================================
# StyledDocument – wrapper around python-docx.Document
# =====================================================================


class StyledDocument:
    """Wrapper around docx.Document with shared layout and style helpers."""

    def __init__(self) -> None:
        self.doc: DocxDocument = docx.Document()
        self._set_page()
        self._set_base_style()

    # --- Page + base styles ----------------------------------------------

    def _set_page(self) -> None:
        s = self.doc.sections[0]
        # A4
        s.page_width, s.page_height = Mm(210), Mm(297)
        # Margins
        s.left_margin = s.right_margin = Mm(25)
        s.top_margin = Mm(20)
        s.bottom_margin = Mm(20)

    def _set_base_style(self) -> None:
        st = self.doc.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10)

    # --- Section & paragraph helpers -------------------------------------

    def add_section_heading(
        self,
        text: str,
        *,
        level: int = 1,
        space_before: int = 18,
        space_after: int = 6,
    ):
        """
        Add a colored heading using Word's heading styles.

        `text` is uppercased for visual consistency.
        """
        h = self.doc.add_heading(text, level=level)
        for r in h.runs:
            r.font.color.rgb = ACCENT_BLUE

        h.paragraph_format.space_before = Pt(space_before)
        h.paragraph_format.space_after = Pt(space_after)
        h.paragraph_format.keep_with_next = True
        return h

    def add_company_role_title(self, company, url, role):
        """
        Example:
            add_company_role_title(
                doc,
                "Elonroad",
                "https://www.elonroad.com",
                " (2025) – Software Developer, Lund",
            )
        """
        p = self.add_section_heading("", level=3, space_before=8, space_after=0)

        # Linked, bold company name
        self.add_hyperlink(p, company, url, bold=False)

        # Rest of the line (years, role, location)
        p.add_run(" " + role)

        return p

    def add_para(self, text: str, space_before: int = 0, space_after: int = 2, left_indent: float = 0.5, right_indent: float = 0.):
        """
        Normal paragraph with tight rhythm (0 before, 2 after).
        """
        p = self.doc.add_paragraph(text)
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.left_indent = Cm(left_indent)
        p.paragraph_format.right_indent = Cm(right_indent)
        return p

    def add_bullet(self, text: str):
        p = self.doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5 + 0.63)
        p.paragraph_format.first_line_indent = Cm(-0.63)
        p.add_run(text)
        return p

    # --- Hyperlink + artifact + technology -------------------------------

    def add_hyperlink(self, paragraph, text: str, url: str,
                      bold: bool = True, color_hex: str = LINK_BLUE_HEX, underline: bool = False):
        """
        Add a clickable hyperlink to `paragraph` with custom styling.
        """

        if not url:
            return paragraph.add_run(text)

        part = paragraph.part
        r_id = part.relate_to(
            url,
            docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK,
            is_external=True,
        )
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), r_id)

        run = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")

        # Color
        color = OxmlElement("w:color")
        color.set(qn("w:val"), color_hex)
        rPr.append(color)

        # Bold?
        if bold:
            rPr.append(OxmlElement("w:b"))

        # Underline?
        u = OxmlElement("w:u")
        u.set(qn("w:val"), "single" if underline else "none")
        rPr.append(u)

        run.append(rPr)
        t = OxmlElement("w:t")
        t.text = text
        run.append(t)

        link.append(run)
        paragraph._p.append(link)
        return paragraph

    def add_artifact(self, title: str, url: str):
        """
        Add a hanging-indent artifact line:

            → Title (hyperlink)

        with left indent and negative first-line indent.
        """
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.add_run("→ ")
        self.add_hyperlink(p, title, url)
        return p

    def add_tech(self, *items: str):
        """
        Add a hanging-indent Technology line:

            Technology: <comma-separated items>   (italic)
        """
        if not items:
            return None
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        r1 = p.add_run("Technology: ")
        r1.bold = True
        r1.italic = True
        r2 = p.add_run(", ".join(items))
        r2.italic = True
        return p

    # --- Save ------------------------------------------------------------

    def save(self, filename: str) -> None:
        self.doc.save(filename)


# =====================================================================
# BaseCV – compressed 2025-11-11 CV (with 1 profile bullet removed)
# =====================================================================


def joined(items: list[str], sep=", ", final_sep=" & "):
    n = len(items)
    if n == 0:
        return ""
    if n == 1:
        return items[0]
    return sep.join(items[:-1]) + final_sep + items[-1]


class BaseCV(StyledDocument, HasTraits):
    """Base CV corresponding to the compressed 2025-11-11 version."""

    # ----------------- Header --------------------------------------------

    name = Str
    role = Str
    level = Str
    specialities = List(Str)
    industries = List(Str)
    email = Str
    phone = Str
    linkedin_profile = Str

    def add_header(self) -> None:
        # Name + subtitle in a tight block
        p = self.doc.add_heading()
        p.paragraph_format.space_after = Pt(0)
        p.add_run(self.name).font.size = Pt(18)

        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.add_run(f"{self.level} {joined(self.specialities)} {self.role} – {joined(self.industries)}"
                  ).font.size = Pt(12)

        # Contact line
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        p.add_run(f"📧 {self.email}  📱 {self.phone}  🔗 ")
        # Hyperlink for LinkedIn
        self.add_hyperlink(p, self.linkedin_profile.rstrip('/').lstrip('https://www.'), self.linkedin_profile)

    # ----------------- Profile -------------------------------------------

    profile = List(Str)

    def add_profile(self) -> None:
        self.add_section_heading("PROFILE")
        for bullet in self.profile:
            self.add_bullet(bullet)

    # ----------------- Core competence -----------------------------------

    core_competence = List(Tuple(Str, List(Str)))

    def add_core_competence(self) -> None:
        self.add_section_heading("CORE COMPETENCE")
        for category, items in self.core_competence:
            p = self.doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(2)
            r = p.add_run(f"{category}: ")
            r.bold = True
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.5)
            p.add_run(" • ".join(items))

    # ----------------- Experience ----------------------------------------

    Experience = Tuple(Tuple(Str, Str, Str), List(Str), List(Str), List(Tuple(Str, Str)))
    experience = List(Tuple(Str, List(Experience)))

    LINK = re.compile(r"\[\**([^\*\]]*)\**\]\(([^)]*)\)")  # [text](url)

    def add_experience(self) -> None:
        for heading, experience in self.experience:
            self.add_section_heading(heading.upper())
            for (company, company_url, role), bullets, technologies, artifacts in experience:
                self.add_company_role_title(company, company_url, role)
                for bullet in bullets:
                    i = 0
                    for m in self.LINK.finditer(bullet):
                        if i:
                            p.add_run(bullet[i:m.start()])
                        else:
                            p = self.add_bullet(bullet[0:m.start()])

                        self.add_hyperlink(p, *m.groups())
                        i = m.end()

                    if i:
                        p.add_run(bullet[i:])
                    else:
                        self.add_bullet(bullet)

                self.add_tech(*technologies)
                for artifact, url in artifacts:
                    self.add_artifact(artifact, url)

    # ----------------- Working approach & personal ------------------------

    environment_approaches = List(Tuple(Str, List(Str)))

    def add_working_approach_and_personal(self) -> None:
        for environment, approaches in self.environment_approaches:
            self.add_section_heading(environment.upper())
            for approach in approaches:
                self.add_bullet(approach)

    # ----------------- Top-level build -----------------------------------

    def build_cv(self, filename: str) -> None:
        self.add_header()
        self.add_profile()
        self.add_core_competence()
        self.add_experience()
        self.add_working_approach_and_personal()
        self.save(filename)
        print(self.__class__.__name__, "saved to", filename)


# =====================================================================
# BaseCoverLetter – neutral, extendable
# =====================================================================


class BaseCoverLetter(BaseCV):
    """Generic, neutral cover letter structure (content intentionally broad)."""
    role = Str
    organization  = Str
    to_ask = Str
    to = Str
    location = Str
    affiliation = Str
    work = Str
    motivation = Str
    arguments = List(Str)
    hook = Str

    def add_field(self, paragraph, style_name: str, text: str, eols: int = 1):
        # 1) create a character style (always new as you wanted)
        style = self.doc.styles.add_style(style_name, WD_STYLE_TYPE.CHARACTER)

        # 2) add run and *force* rStyle onto the run's rPr so Pandoc keeps it
        run = paragraph.add_run(text)
        r = run._r
        rPr = r.get_or_add_rPr()
        rStyle = OxmlElement('w:rStyle')
        rStyle.set(qn('w:val'), style_name)
        # ensure rStyle exists even if no visible font deltas
        rPr.insert(0, rStyle)

        # 3) wrap with SDT tagged the same
        sdt = OxmlElement('w:sdt')
        pr = OxmlElement('w:sdtPr')
        tag = OxmlElement('w:tag');
        tag.set(qn('w:val'), style_name)
        pr.append(tag)
        pr.append(OxmlElement('w:text'))
        sdt.append(pr)
        content = OxmlElement('w:sdtContent')
        r.addprevious(sdt)
        content.append(r)
        sdt.append(content)
        for i in range(eols):
            run.add_break(WD_BREAK.LINE)

        return run

    def add_contact_block(self) -> None:
        p = self.doc.add_paragraph()

        r = self.add_field(p, "name", self.name)
        r = self.add_field(p, "location", self.location)
        r = self.add_field(p, "phone", self.phone)
        r = self.add_field(p, "email", self.email)
        r = self.add_field(p, "engagement", self.affiliation, 2)

        r = p.add_run(self.to_ask)
        r = self.add_field(p, "to", f"{self.to},")
        r = self.add_field(p, "organization", self.organization)

    def add_opening(self) -> None:
        p = self.add_section_heading("Application for ")
        self.add_field(p, "role", self.role, 0)

    def add_intro(self) -> None:
        self.doc.add_paragraph(
            f"I am writing to express my interest in supporting {self.organization} as {self.role} "
            f"working with {self.work}. With {self.motivation}, I believe I can contribute from day one:"
        )

    def add_body(self) -> None:
        for argument in self.arguments:
            self.add_para(argument, 18, 18, 1.5, 1.5)

    def add_closing(self) -> None:
        self.doc.add_paragraph(self.hook)
        p = self.doc.add_paragraph()
        p.add_run("Kind regards,\n")
        p.add_run(self.name).bold = True

    def build_cover(self, filename: str) -> None:
        self.__init__()  # Clear doc
        self.add_contact_block()
        self.add_opening()
        self.add_intro()
        self.add_body()
        self.add_closing()
        self.save(filename)
        print(self.__class__.__name__, "saved to", filename)


CR = "(?: <br>)"
EOL = rf"{CR}? \n"
SEP = rf"(?: \h* \n | \h* <br> \n | \h+)"
CHAR = r"[^<\n#]"
TEXT = f"{CHAR}*"
PHONE = "[+ ,0-9]*"
EMAIL = "[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]*"
COMMA_EOL = f"\s* , \s* {EOL}"

def spaceout(text: str) -> str:
    return text.replace(" ", " \h+ ")

def choice(name, *alternatives):
    return f"\h* (?: (?P<{name}> {' | '.join(map(spaceout, alternatives))}) :? \h*)"

def ask(name, pattern, *alternatives):
    return f"(?: {choice(f'{name}_ask', *alternatives)}? (?P<{name}> {pattern}) {SEP})"

ROLE = choice('role', 'Engineer', 'Programmer', 'Developer', 'Designer', 'Manager')
LETTER = rf"""
(?P<add_contact_block> 
  {ask('name', TEXT, 'Full name', 'Name')}?
  {ask('location', TEXT, 'Home address', 'Address')}?
  {ask('phone', PHONE, 'Phone', 'Mobile')}?
  {ask('email', EMAIL, 'Email')}?
  {ask('affiliation', TEXT, 'Affiliation')}?
  {EOL}*
  (?: \h* (?: (?P<to_ask> To :? \h*))? (?P<to> (?: (?! {COMMA_EOL}) [^<\n#])*) {COMMA_EOL})?
  {ask('organization', TEXT, 'Organization')}?
)
  \s*
(?P<add_opening>
  (^ \#+)? {ask('role', TEXT, 'Application for ')}
)
  \s*
(?P<add_intro>
  (?:
    working \h+ with \h+ (?P<work> [^\.]*) \. |
    With \h+ (?P<motivation> (?: (?! , \h+ (?: I | we) \h) .)*) , \h+ (?P<group> I | we) \h+ |
    (?P=organization) | (?P=role) |
    {CHAR}
  )+ {EOL}
)
(?P<add_body>
  (?: \s* ^ > \h+ (?P<arguments> (?: (?! \n\n).)*) \n\n)*
)
(?P<add_closing> 
  \s* (?P<hook> (?: (?! Sincerely | Kind | Greetings | \** (?P=name) |  ^ ---+ \n) {TEXT})*) \n\n
  \s* (?: (?! \** (?P=name) | ^ ---+ \n) {TEXT} {EOL})*
  \s* \** (?P=name) \**
)
"""

CV = rf"""
(?P<add_header>
    \#* \h* (?P=name) \n\n
    
    \h* (?P<level> Senior | Junior)
    \h* (?: (?P<specialities> (?: (?! (?P=role)) [^,&<\n])*) [, &]+)*
    (?P=role)?
    \h [-–—] \h
    (?: (?P<industries> (?: (?! \h* [,&\n]) .)+) \h* [,&]? \h*)* \n\n
    
    \h* (?: Email | 📧)? \h* (?P=email)
    \h* (?: Phone| Mobile | 📱)? \h* (?P=phone)
    \h* (?: LinkedIn | 🔗)? :? \h*
    \[ \** (?: linkedin.com/in/)? (?P<linkedin_name> [^/*\]<\n]*) /? \** \]
    \( (?P<linkedin_profile> (?: https?://www.)? linkedin.com/in/(?P=linkedin_name) /?)? \) \n\n
)
(?P<add_profile>
    \#* \h PROFILE\n\n
    (?: - \h (?P<profile> (?: (?! \n\n).)*) \n\n)*
)
(?P<add_core_competence>
    \#* \h CORE \h COMPETENCE\n\n
    (?:
        \** (?P<_categories> [^:]*) : \** \n\n
        > \h (?: (?: \h•\h)? (?P<_items> (?: (?! \h•\h | \n\n) .)*))* \n\n
    )*
)
(?P<add_experience>
    (?:
        \s* ^ \# \h (?! MENTORSHIP | COLLABORATION | PERSONAL) (?P<_headings> [^\n]*) \n\n
        (?:
            \s* ^ \#\#\# \h \[? (?P<_companies> [^\](]*) \]?
            (?: \( (?P<_company_urls> https?:// [^\)]*) \))? \h
            (?P<_roles> [^\n]*) \n\n
            (?: - \h (?P<_bullets> (?: (?! \n\n).)*) \n\n)*
            (?: > \h \** Technology: \** \h (?: (?: ,\h)? (?P<_technologies> [^,\*]*))* \*\n\n)?
            (?: > \h → \h \[ \** (?P<_artifacts> [^\*]*) \** \] \( (?P<_artifact_urls> https?:// [^\)]*) \)\n\n)*
        )*
    )*
)
(?P<add_working_approach_and_personal>
    (?:
        \s* ^ \# \h (?P<_environments> [^\n]*) \n\n
        (?: - \h (?P<_approaches> (?: (?! \n\n).)*) \n\n)*
    )*
)
"""

FILE = rf"""(?mxs)
  \A
(?P<letter> {LETTER})
(?:
  \n\n ---+ \n\n
)
(?P<cv> {CV})
  \Z
"""

class Proposal(BaseCoverLetter):
    """Handle an assignment proposal file

    Regenerates the same build_cv() and build_cover() Word documents that MarkdownBuilder used for the proposal file.
    """
    file = File()
    size = int
    _categories = _items = \
        _headings = _companies = _company_urls = _roles = _bullets = _technologies = _artifacts = _artifact_urls = \
        _environments = _approaches = List(Str)

    # For the edit_traits() method:
    traits_view = View
    file_positions = [-1]  # Every pubic trait needs _positions so that we can sort them all into traits_view.

    def _file_changed(self):
        md = open(self.file, encoding="utf-8").read()
        self.size = len(md)
        m = re.match(FILE, md)
        if not m:
            raise SyntaxError((f"{self.file} does not match Python https://regex101.com/ {FILE}"
                               " - All (indented) patterns above must match with the file."
                               " Correct FILE pattern or file content until they match.").replace(
                r'\h', r'[^\S\n]').replace(
                '📧', r'\U0001F4E7').replace(
                '📱', r'\U0001F4F1').replace(
                '🔗', r'\U0001F517'))

        # Flat data
        groupdict = m.groupdict()
        for attr, handler in self.traits().items():
            if attr in groupdict:
                info = handler.full_info(self, attr, None)
                if info == 'a string':
                    setattr(self, attr, m[attr] or "")
                elif info == 'a list of items which are a string':
                    setattr(self, attr, m.captures(attr))
                    setattr(self, attr + '_index', 0)

                setattr(self, attr + '_positions', array(m.spans(attr) + [(self.size, self.size)])[:,0])

        # Structured data
        self.core_competence, self.core_competence_positions = self.structured(
            [('_categories', [
                '_items'])])
        self.experience, self.experience_positions = self.structured(
            [('_headings', [(
                ('_companies', '_company_urls', '_roles'),
                ['_bullets'],
                ['_technologies'],
                [('_artifacts', '_artifact_urls')])])])
        self.environment_approaches, self.environment_approaches_positions = self.structured(
            [('_environments', [
                '_approaches'])])

        # Make a view for all public traits sorted by _positions[0]
        pos_attrs = sorted([(getattr(self, attr + '_positions')[0], attr)
                            for attr in self.traits().keys() if self.is_view_item(attr)])
        attrs = array(pos_attrs)[:,1]
        self.traits_view = View(*map(Item, attrs), title="Proposal", resizable=True, buttons=["OK"])

    def is_view_item(self, attr: str):
        """
        Return the first class in the MRO that defines `trait_name` in its __dict__.
        Works for Traits since class attributes are descriptors stored on the class.
        """
        if not attr[0].islower():
            return False

        here = False
        for cls in type(self).__mro__:
            if hasattr(cls, 'class_traits'):
                somewhere = attr in cls.class_traits()
                if cls.__module__ == "__main__":
                    here |= somewhere
                else:
                    here &= not somewhere

        return here

    def structured(self, structure, span=None):
        """Return a str with one value, a tuple or a list; and the _positions span used

        In case of a str, the span is updated to not include the previous and next one.
        """
        span = span or [0, self.size]
        if isinstance(structure, str):
            values = getattr(self, structure)
            positions = getattr(self, structure + '_positions')
            index = getattr(self, structure + '_index')
            if positions[index] >= span[1]:
                return '', span

            span[0], span[1] = positions[index:index + 2]
            setattr(self, structure + '_index', index + 1)
            return values[index], span

        if isinstance(structure, tuple):
            items = []
            for branch_index, branch in enumerate(structure):
                item, span = self.structured(branch, span)
                assert branch_index or item
                items.append(item)

            return tuple(items), span

        # List
        item = structure[0]
        if isinstance(item, str):
            values = getattr(self, item)
            positions = getattr(self, item + '_positions')
            index = getattr(self, item + '_index')
            next_structure_index = index + argwhere(positions[index:] >= span[1])[0][0]
            setattr(self, item + '_index', next_structure_index)
            values = values[index:next_structure_index]
            if values and not values[-1]:
                del values[-1]

            return values, span

        forest = []
        first = True
        while True:
            try:
                tree, span_here = self.structured(item, span[:])
                forest.append(tree)
                if first:
                    span[0] = span_here[0]
            except AssertionError:
                return forest, span


proposal = Proposal()
try:
    proposal.file = 'cover_and_cv.md'
except FileNotFoundError:
    pass

def edit():
    try:
        from pyface.api import GUI
    except ImportError:
        raise ImportError("pip install pyside6<6.6  # Only available in Python <3.11")

    proposal.edit_traits(view=proposal.traits_view)
    GUI().start_event_loop()


if __name__ == "__main__":
    import fire
    fire.Fire(dict(edit=edit))

    from build_cover_letter_and_cv_markdown import MarkdownBuilder

    cv = f"{proposal.name}_CV.docx"
    cover = f"{proposal.name}-{proposal.role}-{proposal.organization}.docx"
    proposal.build_cv(cv)
    proposal.build_cover(cover)
    MarkdownBuilder(cover=cover, cv=cv)()
