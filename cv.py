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

from typing import Iterable

import docx
from docx.document import Document as DocxDocument
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, Mm, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT


# ---- Branding / colors ----
ACCENT_BLUE = RGBColor(0x00, 0x66, 0xB3)  # Additude headings
LINK_BLUE_HEX = "004A99"                  # Bold dark blue for hyperlinks (no underline)
FILENAME_DATE = "2025-11-11"


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
        space_after: int = 2,
    ):
        """
        Add a colored heading using Word's heading styles.

        `text` is uppercased for visual consistency.
        """
        h = self.doc.add_heading(text.upper(), level=level)
        for r in h.runs:
            r.font.color.rgb = ACCENT_BLUE
            r.bold = True
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
        p = self.doc.add_paragraph()
        pf = p.paragraph_format
        pf.space_before = Pt(8)
        pf.space_after = Pt(0)
        pf.keep_with_next = True

        # Linked, bold company name
        self.add_hyperlink(p, company, url)

        # Rest of the line (years, role, location)
        p.add_run(" " + role)

        return p

    def add_para(self, text: str):
        """
        Normal paragraph with tight rhythm (0 before, 2 after).
        """
        p = self.doc.add_paragraph(text)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.5)
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


class BaseCV(StyledDocument):
    """Base CV corresponding to the compressed 2025-11-11 version."""

    # ----------------- Header --------------------------------------------

    def add_header(self) -> None:
        # Name + subtitle in a tight block
        h = self.doc.add_paragraph()
        h.paragraph_format.space_after = Pt(0)
        run1 = h.add_run("Joakim Pettersson\n")
        run1.bold = True
        run1.font.size = Pt(18)
        run2 = h.add_run(
            "Senior Embedded & Control Systems Engineer – Automotive, Energy & eMobility"
        )
        run2.font.size = Pt(12)

        # Contact line
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        p.add_run("📧 joakim.pettersson@ict.eu  📱 +46 708 29 99 74  🔗 ")
        # Hyperlink for LinkedIn
        self.add_hyperlink(p,"linkedin.com/in/joakimbits","http://se.linkedin.com/in/joakimbits")

    # ----------------- Profile -------------------------------------------

    def add_profile(self) -> None:
        self.add_section_heading("Profile")

        # NOTE: First original bullet
        # "Embedded software developer with 14+ years..."
        # is intentionally removed here to keep BaseCV less branch-specific.

        self.add_bullet(
            "Combines hands-on embedded C/C++ and Python development with deep understanding "
            "of real-time communication, sensor integration and low-power control."
        )
        self.add_bullet(
            "Skilled in bridging hardware and software domains to ensure reliable, reproducible "
            "system behaviour from prototype to production."
        )

    # ----------------- Core competence -----------------------------------

    def add_core_competence(self) -> None:
        self.add_section_heading("Core competence")

        # Hardware Architectures
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run("Hardware Architectures: ")
        r.bold = True
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.add_run("ARM • Intel x86 • PowerPC • Altera • Xilinx")

        # Software & Systems
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run("Software & Systems: ")
        r.bold = True
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.add_run(
            "Python • Linux • RTOS • C/C++ • CAN / J1939 / CANopen • BLE / Wi-Fi"
            " • UDP / TCP/IP / MQTT • ML / AI • DevSecOps • EMC"
        )

        # Key expertise
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run("Key expertise: ")
        r.bold = True
        p = self.doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.add_run(
            "Real-time control • Connectivity • Sensor fusion • Algorithm integration"
            " • Cloud & mobile interaction"
        )

    # ----------------- Experience ----------------------------------------

    def add_experience(self) -> None:
        self.add_section_heading("Experience")

        # --- Elonroad (2025) ---
        self.add_company_role_title(
            "Elonroad", 'https://www.elonroad.com/',
            "(2025) – Software Developer, Lund")
        self.add_bullet(
            "Collaborated with firmware, electronics and control engineers to improve real-time "
            "performance and timing guarantees in motion-control and sensors for electric-road "
            "charging infrastructure."
        )
        self.add_bullet(
            "Introduced SI-unit scaling and coordinate consistency across software and hardware "
            "to align motion tracking, communication and physical geometry."
        )
        self.add_bullet(
            "Integrated the J1939 CAN framework to synchronize tracker, charger and vehicle "
            "communication, and redesigned harness and switch placement to reduce EMI and "
            "cabling cost."
        )
        self.add_tech("C", "Python", "CMake", "STM32CubeMX", "CANopen", "J1939")
        self.add_artifact(
            "J1939 signaling in heavy vehicles",
            "https://www.linkedin.com/in/joakimbits/overlay/1758097448773/single-media-viewer",
        )

        # --- Sandvine / Dover / Assa Abloy / deWiz / Blodtrycksdoktorn / ESS (–2024) ---
        self.add_company_role_title(
            "Sandvine / Dover / Assa Abloy / deWiz / Blodtrycksdoktorn / ESS", None,
            "(–2024) – Dependable systems engineer"
        )
        self.add_bullet(
            "Other assignments within telecom and sensors, enabling reliable signalling and "
            "automated test/CI."
        )

        # --- SiB Solutions (2022–2023) ---
        self.add_company_role_title(
            "SiB Solutions", 'https://www.sibsolutions.com/',
            "(2022–2023) – Technical Lead, AI Camera Systems")
        self.add_bullet(
            "Re-engineered AI/ML pipeline on EdgeTPU for small-object detection; automated "
            "deterministic model training and CI testing."
        )
        self.add_tech("TensorFlow", "Python", "Docker", "Git")
        self.add_artifact(
            "Detect objects in objects (2023)",
            "https://www.linkedin.com/in/joakimbits/details/experience/1713969601372/single-media-viewer",
        )

        # --- MyFC (2022) ---
        self.add_company_role_title(
            "MyFC",'https://fkg.se/volymproduktion-nasta-for-fuel-cell-technology-sweden/',
            "(2022) – Senior Embedded Developer – Fuel-Cell Electronics")
        self.add_bullet(
            "Implemented synchronous ADC sampling and cell-group self-identification logic for "
            "safe and stable fuel-cell stack control."
        )
        self.add_bullet(
            "Contributed to EMC- and thermally-informed layout decisions, improving measurement "
            "reliability."
        )
        self.add_tech("C", "FreeRTOS", "Python", "Altium", "KiCad")

        # --- Join Business & Technology (2011–2018) ---
        self.add_company_role_title(
            "Join Business & Technology",'https://www.join.se/',
            "(2011–2018) – Systems Engineering Consultant, Lund"
        )
        p = self.add_para("Delivered embedded control and measurement systems for ")
        self.add_hyperlink(p, "Orbital Systems", "https://www.orbital-systems.se/");
        p.add_run(", ")
        self.add_hyperlink(p, "Baxter", "https://www.baxter.se/");
        p.add_run(", ")
        self.add_hyperlink(p, "Sensefarm", "https://www.sensefarm.com/");
        p.add_run(", ")
        self.add_hyperlink(p, "Luda.farm", "https://www.luda.farm/product/luda-fence/");
        p.add_run(", ")
        self.add_hyperlink(p, "ETAS", "https://www.etas.com/");
        p.add_run(" and ")
        self.add_hyperlink(p, "Swegon", "https://www.swegon.com/");
        p.add_run(".")
        self.add_tech("Micropython", "C/C++", "LabVIEW", "Make", "Git", "Excel automation"
                      ).paragraph_format.keep_with_next = True
        self.add_artifact(
            "Fluid Test Bench (2014)",
            "https://www.linkedin.com/in/joakimbits/overlay/experience/266729404/multiple-media-viewer/?treasuryMediaId=1717417923021",
        ).paragraph_format.keep_with_next = True
        self.add_artifact(
            "SE542440C2 – Sound valve speaker for regulating pressure (2020)",
            "https://joakimbits.github.io/cv/audio/sound-valve-speaker.html",
        )

        # --- Ericsson Group (2000–2010) ---
        self.add_company_role_title(
            "Ericsson Group", 'https://www.ericsson.com/en/about-us',
            "(2000–2010) – Senior Systems Engineer, Lund / Stockholm / Montréal"
        )
        self.add_bullet(
            "Designed, simulated and verified Bluetooth radios and ASIC interfaces, then advanced "
            "from ad-hoc network performance (Bluetooth, Wi-Fi) through cellular performance "
            "(2G/3G) to product-level performance such as 911 location latency."
        )
        self.add_bullet(
            "Collaborated with global design, compliance and manufacturing teams to stabilise "
            "system behaviour."
        )
        self.add_tech(
            "C",
            "C++",
            "Python",
            "LabVIEW",
            "VHDL",
            "Matlab",
            "RF design",
            "Bluetooth",
            "GSM/GPRS",
            "Java",
            "Jython",
            "Excel",
            "Project",
            "Jira",
        )
        self.add_artifact(
            "Bluetooth Programmable Logic Device (2002)",
            "https://www.linkedin.com/in/joakimbits/details/experience/1717428026690/single-media-viewer",
        )
        self.add_artifact(
            "First 911-certified advanced camera phone (2008)",
            "https://www.linkedin.com/in/joakimbits/details/experience/1717421728587/single-media-viewer",
        )

        # --- Volvo Technological Development (1997–2000) ---
        self.add_company_role_title(
            "Volvo Technological Development", 'https://www.volvogroup.com/en/about-us.html',
            "(1997–2000) – Research Engineer, Göteborg"
        )
        self.add_bullet(
            "Early work in algorithmic evaluation of driving comfort and energy storage laid "
            "foundations for later e-mobility drivetrain design."
        )
        self.add_tech("C", "Matlab", "LabVIEW", "AI/ML", "Sensor fusion", "Vehicle dynamics")
        self.add_artifact(
            "Quality assurance of driver comfort for automatic transmissions (2000)",
            "https://www.linkedin.com/in/joakimbits/details/experience/142498903/multiple-media-viewer?treasuryMediaId=1717429329020",
        )
        self.add_artifact(
            "Hydrogen storage alternatives (1999)",
            "https://www.linkedin.com/in/joakimbits/details/experience/142498903/multiple-media-viewer?treasuryMediaId=1717429329019",
        )

    # ----------------- Education & research -------------------------------

    def add_education_research(self) -> None:
        self.add_section_heading("Education & research")

        # Ph.D. studies
        self.add_company_role_title(
            "Ph.D. studies in Applied Solid-State Physics – Chalmers University of Technology, Gothenburg",
            'http://www.chalmers.se/mc2/EN/laboratories/quantum-device-physics/research/experimental-mesoscopic',
            "(1992–1996, unexamined)"
        )
        self.add_para(
            "Conducted doctoral research on nano-fabrication, quantum waveguides and "
            "single-electron transistors within the Low-temperature Physics group."
        )
        # NOTE: URLs for publications are placeholders here; adjust to your actual pages if needed.
        self.add_artifact(
            "Conductance oscillations in quantum dots, Phys. Rev. B / Physica B (1994–1996)",
            "https://iopscience.iop.org/article/10.1088/0953-8984/7/19/007",
        )
        self.add_artifact(
            "Extending the high-frequency limit of a single-electron transistor, Phys. Rev. B (1996)",
            "https://www.researchgate.net/publication/13306616_Extending_the_high-frequency_limit_of_a_single-electron_transistor_by_on-chip_impedance_transformation",
        )
        self.add_artifact(
            "Submicron air-bridge interconnection process for complex gate geometries, "
            "J. Vac. Sci. Technol. B (1997)",
            "https://www.researchgate.net/publication/249510567_Submicron_air-bridge_interconnection_process_for_complex_gate_geometries",
        )

        # M.Sc.
        self.add_company_role_title(
            "M.Sc. Engineering Physics – Chalmers University of Technology, Gothenburg",
            'https://www.gu.se/en/study-gothenburg/physics-masters-programme-n2phy',
            "(1986–1992)"
        )
        self.add_para(
            "Thesis on nanofabrication with studies spanning mathematics, physics, chemistry "
            "and medicine."
        )

    # ----------------- Working approach & personal ------------------------

    def add_working_approach_and_personal(self) -> None:
        self.add_section_heading("Mentorship & collaboration")
        self.add_bullet(
            "Collaborative, analytical and dependable in cross-disciplinary environments."
        )
        self.add_bullet(
            "Prefers small reproducible setups, clear interfaces and measurement-driven validation."
        )
        self.add_bullet(
            "Bridges hardware, embedded and data teams so decisions remain explainable "
            "across domains."
        )

        self.add_section_heading("Personal")
        self.add_bullet(
            "Based in southern Sweden and living an RnDIY life in Dalby. Father of three daughters "
            "(12, 18 and 23)."
        )
        self.add_bullet(
            "Enjoys hands-on projects, sailing, cycling a Quattrovelo, and playing string instruments."
        )
        self.add_bullet(
            "Values craftsmanship, sustainability and curiosity — the same principles that guide "
            "professional work."
        )

    # ----------------- Top-level build -----------------------------------

    def build(self, filename: str) -> None:
        self.add_header()
        self.add_profile()
        self.add_core_competence()
        self.add_experience()
        self.add_education_research()
        self.add_working_approach_and_personal()
        self.save(filename)


# =====================================================================
# BaseCoverLetter – neutral, extendable
# =====================================================================


class BaseCoverLetter(StyledDocument):
    """Generic, neutral cover letter structure (content intentionally broad)."""
    role = "Engineer"
    org  = "your organisation"

    def add_contact_block(self) -> None:
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(
            "Joakim Pettersson\n"
            "Dalby, Sweden\n"
            "Phone: +46 708 29 99 74\n"
            "Email: joakim.pettersson@ict.eu\n"
            "Consultant via ICT Additude AB\n"
        )
        r.font.size = Pt(10)

    def add_opening(self) -> None:
        p = self.doc.add_paragraph()
        p.add_run(f"To the hiring committee,\n{self.org}")
        heading = self.doc.add_paragraph()
        run = heading.add_run(f"Application for {self.role}")
        run.bold = True
        run.font.size = Pt(12)

    def add_intro(self) -> None:
        self.add_para(
            f"I am writing to express my interest in supporting {self.org} as {self.role} "
            "working with instrumentation, embedded software and complex systems. With more than "
            "two decades of experience in measurement, integration and troubleshooting across "
            "research, automotive and industrial domains, I believe I can contribute from day one."
        )

    def add_body(self) -> None:
        self.add_para(
            "Throughout my career I have worked close to both hardware and software, bridging "
            "electronics, motion systems, data acquisition and automation with Python- and "
            "C/C++-based tooling. I enjoy stabilising complex setups, making behaviour observable "
            "and building small tools that help others understand and trust the systems they use."
        )
        self.add_para(
            "I am comfortable collaborating with cross-disciplinary teams, from field engineers "
            "and operators to researchers and product managers. I value clear communication, "
            "measurement-driven validation and a pragmatic approach to improving systems without "
            "losing sight of long-term maintainability."
        )

    def add_closing(self) -> None:
        self.add_para(
            "I live in Dalby and can be available on short notice. I would welcome the opportunity "
            "to discuss how my background could support your team."
        )
        p = self.doc.add_paragraph()
        p.add_run("Kind regards,\n")
        p.add_run("Joakim Pettersson").bold = True

    def build(
        self,
        filename: str,
    ) -> None:
        self.add_contact_block()
        self.add_opening()
        self.add_intro()
        self.add_body()
        self.add_closing()
        self.save(filename)


if __name__ == "__main__":
    BaseCV().build("Joakim_Pettersson_CV.docx")
    BaseCoverLetter().build("Joakim_Pettersson_letter.docx")
