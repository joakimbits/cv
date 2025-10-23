# build_cv_additude_final.py
# Generates: Joakim_Pettersson_CV_Additude_M4_2025-10-22.docx

from docx import Document
from docx.shared import Pt, RGBColor, Mm, Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# ---- Branding / colors ----
ACCENT_BLUE    = RGBColor(0x00, 0x66, 0xB3)   # Additude headings
LINK_BLUE_HEX  = "004A99"                     # Bold dark blue for hyperlinks (no underline)
FILENAME_DATE  = "2025-10-22"

# ---- Page + base styles ----
def set_page(doc):
    s = doc.sections[0]
    s.page_width, s.page_height = Mm(210), Mm(297)  # A4
    s.left_margin = s.right_margin = Mm(25)
    s.top_margin  = Mm(20)
    s.bottom_margin = Mm(20)

def set_base_style(doc):
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)

# ---- Helpers ----
def add_section_heading(doc, text, level=1, space_before=0, space_after=6):
    h = doc.add_heading(text, level=level)
    for r in h.runs:
        r.font.color.rgb = ACCENT_BLUE
        r.bold = True
    h.paragraph_format.space_before = Pt(space_before)
    h.paragraph_format.space_after = Pt(space_after)
    h.paragraph_format.keep_with_next = True
    return h

def add_role_title(doc, text):
    p = doc.add_paragraph(text)
    if p.runs:
        p.runs[0].bold = True
    p.paragraph_format.space_before = Pt(6)  # small gap above
    p.paragraph_format.space_after  = Pt(2)  # tight below
    p.paragraph_format.keep_with_next = True
    return p

def add_para(doc, text):
    p = doc.add_paragraph(text)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(2)  # tight rhythm
    return p

def add_hyperlink(paragraph, text, url, bold=True, color_hex=LINK_BLUE_HEX, underline=False):
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")

    color = OxmlElement("w:color")
    color.set(qn("w:val"), color_hex)
    rPr.append(color)

    if bold:
        rPr.append(OxmlElement("w:b"))

    u = OxmlElement("w:u")
    u.set(qn("w:val"), "none" if not underline else "single")
    rPr.append(u)

    run.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    run.append(t)

    link.append(run)
    paragraph._p.append(link)
    return paragraph

def add_artifact(doc, title, url):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.first_line_indent = Cm(-0.5)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(2)
    p.add_run("→ ")
    add_hyperlink(p, title, url, bold=True)
    return p

def add_tech(doc, *items):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.first_line_indent = Cm(-0.5)
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(2)   # tight; sits right above artifacts
    r1 = p.add_run("Technology: ")
    r1.bold = True
    r1.italic = True
    r2 = p.add_run(", ".join(items))
    r2.italic = True
    return p

def add_header(doc):
    # Name + subtitle (no extra gap)
    h = doc.add_paragraph()
    h.paragraph_format.space_after = Pt(0)
    run1 = h.add_run("Joakim Pettersson\n")
    run1.bold = True
    run1.font.size = Pt(16)
    run2 = h.add_run("Senior Embedded & Control Systems Engineer\nICT Additude | M4 Gothenburg")
    run2.font.size = Pt(11)

    # Contact (tight above/below)
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(6)
    p.add_run("📧 joakim.pettersson@additude.se 📱 +46 708 29 99 74 🔗 ")
    add_hyperlink(p, "linkedin.com/in/joakimbits", "http://se.linkedin.com/in/joakimbits", bold=True)

# ---- Sections ----
def add_profile_and_competence(doc):
    add_section_heading(doc, "PROFILE", level=2, space_before=0, space_after=6)
    add_para(
        doc,
        "Consultant and software developer with 14+ years of experience building, integrating and troubleshooting "
        "embedded control and distributed systems for automotive, energy and industrial applications. Combines hands-on "
        "embedded C/C++ and Python development with system-level insight from automotive AI, sensor fusion and real-time "
        "architectures. Skilled in integrating complex control architectures across embedded and distributed systems, "
        "enabling smooth transitions between generations of hardware and software. Recognized for dependable integration "
        "work, clear communication and collaboration across hardware, software and testing teams.",
    )

    add_section_heading(doc, "CORE COMPETENCE", level=2, space_before=0, space_after=6)
    p1 = add_para(doc, "")
    p1.add_run("Hardware Architectures: ").bold = True
    p1.add_run("PowerPC • ARM • Intel x86 • Altera • Xilinx")
    p2 = add_para(doc, "")
    p2.add_run("Software & Systems: ").bold = True
    p2.add_run(
        "Embedded C/C++ • Python • CAN / J1939 / CANopen • Ethernet / UDP / TCP/IP • "
        "RTOS • LabVIEW • AI/ML • System Architecture • Distributed Control • KVM / Docker • EMC & Safety"
    )

def add_experience(doc):
    hdr = add_section_heading(doc, "EXPERIENCE", level=1, space_before=0, space_after=6)
    hdr.paragraph_format.space_before = Pt(0)

    # --- Elonroad (2025) ---
    add_role_title(doc, "Elonroad (2025) – Software Developer, Lund")
    add_para(
        doc,
        "Collaborated with firmware, electronics and control engineers to improve real-time performance and timing guarantees "
        "in motion-control and sensor systems for electric-road charging infrastructure.",
    )
    add_para(
        doc,
        "Introduced SI-unit scaling and a defined coordinate system, aligning motion tracking, communication and physical geometry "
        "to achieve reproducible results across all development setups.",
    )
    add_para(
        doc,
        "Integrated the J1939 CAN framework to synchronize tracker, charger and vehicle communication with precise timing alignment, "
        "and implemented architecture changes for harnesses and switch locations to reduce EMI and significantly lower cabling cost.",
    )
    add_tech(doc, "Python", "C", "CMake", "STM32CubeMX", "CANopen", "J1939")
    add_artifact(
        doc,
        "J1939 signaling in heavy vehicles",
        "https://www.linkedin.com/in/joakimbits/overlay/1758097448773/single-media-viewer",
    )

    # --- ESS (2023–2024) ---
    add_role_title(doc, "ESS – European Spallation Source (2023–2024) – Senior Electronics Systems Engineer")
    add_para(
        doc,
        "Audited and repaired signal integrity across distributed beam-monitor installations; introduced automated instrument "
        "control and reproducible reporting to stabilize maintenance and documentation.",
    )
    add_tech(doc, "Python", "QCoDeS", "Make", "Git", "Altium", "Ubuntu")
    add_artifact(doc, "Report arbitrarily nested projects (2024)", "https://github.com/joakimbits/normalize/pull/3")

    # --- SiB Solutions (2022–2023) ---
    add_role_title(doc, "SiB Solutions (2022–2023) – Technical Lead, AI Camera Systems")
    add_para(
        doc,
        "Re-engineered EdgeTPU training pipeline for small-object detection and implemented CI/CD for deterministic "
        "model builds and tests.",
    )
    add_tech(doc, "TensorFlow", "Python", "Make", "Docker", "Kafka", "Git")
    add_artifact(
        doc,
        "Detect objects in objects (2023)",
        "https://www.linkedin.com/in/joakimbits/details/experience/1713969601372/single-media-viewer",
    )

    # --- myFC (2022) ---
    add_role_title(doc, "myFC (2022) – Senior Embedded Developer – Fuel-Cell Electronics")
    add_para(
        doc,
        "Implemented synchronous sampling and cell-group self-identification for stack control; contributed EMC and thermal "
        "layout improvements.",
    )
    add_tech(doc, "C", "FreeRTOS", "Altium", "KiCad", "Python")

    # --- Sandvine (2018–2021) ---
    add_role_title(doc, "Sandvine (2018–2021) – Senior Software Developer, Telecom Infrastructure")
    add_para(
        doc,
        "Developed distributed packet-processing features with tight latency budgets and strengthened CI with containerized "
        "performance tests and compliance reviews.",
    )
    add_tech(doc, "C", "C++", "Python", "Clang", "Docker", "Jenkins", "Ubuntu")
    add_artifact(
        doc,
        "Just Data! (2021)",
        "https://www.linkedin.com/in/joakimbits/details/experience/2387352724/multiple-media-viewer",
    )

    # --- Join (2011–2018) ---
    add_role_title(doc, "Join Business & Technology (2011–2018) – Systems Engineering Consultant, Lund")
    p = add_para(doc, "Delivered embedded control and measurement systems for ")
    add_hyperlink(p, "Orbital Systems", "https://www.orbital-systems.se/"); p.add_run(", ")
    add_hyperlink(p, "Baxter", "https://www.baxter.se/"); p.add_run(", ")
    add_hyperlink(p, "Sensefarm", "https://www.sensefarm.com/"); p.add_run(", ")
    add_hyperlink(p, "Luda.farm", "https://www.luda.farm/product/luda-fence/"); p.add_run(", ")
    add_hyperlink(p, "ETAS", "https://www.etas.com/"); p.add_run(" and ")
    add_hyperlink(p, "Swegon", "https://www.swegon.com/"); p.add_run(".")
    add_tech(doc, "Micropython", "C/C++", "LabVIEW", "Make", "Git", "Excel automation")
    add_artifact(
        doc,
        "Fluid Test Bench (2014)",
        "https://www.linkedin.com/in/joakimbits/details/experience/266729404/multiple-media-viewer",
    )
    add_artifact(
        doc,
        "SE542440C2 – Sound valve speaker for regulating pressure (2020)",
        "https://www.linkedin.com/in/joakimbits/overlay/1761124217062/single-media-viewer",
    )

    # --- Ericsson (2000–2010) ---
    add_role_title(doc, "Ericsson Group (2000–2010) – Senior Systems Engineer, Lund / Stockholm / Montréal")
    add_para(
        doc,
        "Worked across multiple Ericsson organizations, bridging RF, embedded and system-performance teams in Sweden, Canada, "
        "the U.S. and China.",
    )
    add_para(
        doc,
        "Designed, simulated and verified Bluetooth radios and ASIC interfaces, then advanced from ad-hoc network performance "
        "(Bluetooth, Wi-Fi) through cellular performance (2G/3G) to product-level performance such as 911 location latency.",
    )
    add_para(
        doc,
        "Collaborated with global design, compliance and manufacturing teams to stabilise system behaviour across radio, baseband "
        "and software domains from prototype to mass production.",
    )
    add_tech(
        doc,
        "C", "C++", "Python", "LabVIEW", "VHDL", "Matlab", "RF design",
        "Bluetooth", "GSM/GPRS", "Java", "Jython", "Excel", "Project", "Jira"
    )
    add_artifact(
        doc,
        "Bluetooth Programmable Logic Device (2002)",
        "https://www.linkedin.com/in/joakimbits/details/experience/1717428026690/single-media-viewer",
    )
    add_artifact(
        doc,
        "First 911-certified advanced camera phone (2008)",
        "https://www.linkedin.com/in/joakimbits/details/experience/1717421728587/single-media-viewer",
    )

    # --- Volvo (1997–2000) ---
    add_role_title(doc, "Volvo Technological Development (1997–2000) – Research Engineer, Göteborg")
    add_para(
        doc,
        "Developed an AI-based expert system (radial-basis neural networks) for gearshift comfort, verified against Volvo’s top "
        "evaluators.",
    )
    add_para(
        doc,
        "The system included a reliability metric that triggered automatic capture of new training data and allowed the test driver "
        "to retrain the model in real time with a single numeric key press.",
    )
    add_para(
        doc,
        "Led a national hydrogen-storage study for fuel-cell drivetrains, assessing metal hydrides, pressure vessels and cryogenic "
        "options for vehicle use.",
    )
    add_para(
        doc,
        "Supervised diploma workers on hybrid-drivetrain optimisation; findings led to a recommendation for pure electric "
        "drivetrains over hybrids.",
    )
    add_tech(doc, "C", "Matlab", "LabVIEW", "AI/ML", "Sensor fusion", "Vehicle dynamics")
    add_artifact(
        doc,
        "Quality assurance of driver comfort for automatic transmissions (2000)",
        "https://www.linkedin.com/in/joakimbits/details/experience/142498903/multiple-media-viewer?treasuryMediaId=1717429329020",
    )
    add_artifact(
        doc,
        "Hydrogen storage alternatives (1999)",
        "https://www.linkedin.com/in/joakimbits/details/experience/142498903/multiple-media-viewer?treasuryMediaId=1717429329019",
    )

def add_education_research(doc):
    add_section_heading(doc, "EDUCATION & RESEARCH", level=1, space_before=6, space_after=6)

    # Ph.D. (use role-title rhythm)
    add_role_title(doc, "Ph.D. studies in Applied Solid-State Physics – Chalmers University of Technology, Gothenburg (1992–1996, unexamined)")
    add_para(
        doc,
        "Completed full doctoral research and publications within the Semiconductor Physics group, covering nano-fabrication, "
        "quantum waveguides and single-electron transistors. Taught solid-state and low-temperature physics and contributed to "
        "one EU research project. Established departmental standards for simulation and measurement automation using LabVIEW and "
        "custom drawing tools.",
    )
    add_tech(doc, "Molecular beam epitaxy", "Electron-beam lithography", "Superfluids", "LabVIEW", "Pascal")

    # Physics publications as portfolio-style items (no subheading; no duplicates with experience)
    add_artifact(
        doc,
        "Extending the high-frequency limit of a single-electron transistor by on-chip impedance transformation, Phys. Rev. B (1996)",
        "https://www.researchgate.net/publication/13306616_Extending_the_high-frequency_limit_of_a_single-electron_transistor_by_on-chip_impedance_transformation",
    )
    add_artifact(
        doc,
        "Submicron air-bridge interconnection process for complex gate geometries, J. Vac. Sci. Technol. B (1997)",
        "https://www.researchgate.net/publication/249510567_Submicron_air-bridge_interconnection_process_for_complex_gate_geometries",
    )
    add_artifact(
        doc,
        "Conductance oscillations in quantum dots, Phys. Rev. B / Physica B / J. Phys. Cond. Matter (1994–1999)",
        "https://iopscience.iop.org/article/10.1088/0953-8984/7/19/007",
    )

    # M.Sc. (use role-title rhythm)
    add_role_title(doc, "M.Sc. Engineering Physics – Chalmers University of Technology, Gothenburg (1986–1992)")
    add_para(
        doc,
        "Thesis on nanofabrication, with studies in mathematics, physics, chemistry, and medicine, and early experience in "
        "programming, measurement automation, and computational methods across scientific and engineering domains.",
    )

def add_working_approach(doc):
    add_section_heading(doc, "WORKING APPROACH", level=1, space_before=6, space_after=0)
    add_para(
        doc,
        "Collaborative, analytical and dependable in cross-disciplinary environments. Joins early to stabilise interfaces and logging; "
        "prefers small reproducible setups and measurement-first validation. Documents and automates what others rely on manually, "
        "preventing ambiguity and easing handovers. Bridges hardware, embedded and data teams so decisions remain explainable both "
        "technically and organisationally.",
    )

# ---- Build ----
def main():
    doc = Document()
    set_page(doc)
    set_base_style(doc)

    add_header(doc)
    add_profile_and_competence(doc)
    add_experience(doc)
    add_education_research(doc)
    add_working_approach(doc)   # at the end

    filename = f"Joakim_Pettersson_CV_Additude_M4_{FILENAME_DATE}.docx"
    doc.save(filename)
    print(f"Created: {filename}")

if __name__ == "__main__":
    main()
