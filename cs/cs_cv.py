# cs_cv.py
#
# Control Systems CV and Cover Letter
# Inherits from BaseCV and BaseCoverLetter defined in cv.py
#

from cv import BaseCV, BaseCoverLetter


class CSCV(BaseCV):
    """
    Control Systems–oriented CV.
    Overrides only the profile section for now (extremely compact Version 3).
    """

    def add_profile(self):
        """Add the CSCV-specific compact profile."""
        self.add_section_heading("PROFILE")

        # --- Version 3 ultra-compact CSCV profile (approved) ---
        self.add_para(
            "Control-systems engineer experienced in embedded C/C++, Python, "
            "PLC→MCU→FPGA timing, and EMI-robust real-time control."
        )
        self.add_para(
            "Background includes motion systems, power electronics and HVAC configuration "
            "tools (Swegon ProWISE/MVC)."
        )
        self.add_para(
            "Comfortable with maintenance, operational stability and user-facing engineering "
            "work, including support of instrumentation and drivers at ESS."
        )
        # --------------------------------------------------------


class CSCoverLetter(BaseCoverLetter):
    """
    Cover letter specialised for control-systems-oriented roles.
    Extends BaseCoverLetter with a CSC-specific intro paragraph.
    """
    role = "Control Systems Engineer"

    def add_intro(self):
        """Insert CSCV-specific introduction before the BaseCoverLetter body."""
        self.add_para(
            "I am applying for roles that combine real-time control, embedded systems and "
            "practical engineering. With a background spanning PLC-scale sequencing, "
            "microsecond MCU control and FPGA-based signal paths, I am comfortable working "
            "directly with hardware, instrumentation and timing-sensitive systems."
        )
        self.add_para(
            "In addition to development work, I am fully comfortable with routine maintenance, "
            "operational stability and user-facing engineering tasks. I enjoy supporting "
            "colleagues in instrumentation environments, tracing issues through hardware, "
            "firmware and Python/C-based automation layers to maintain reliable operation."
        )


if __name__ == "__main__":
    CSCV().build("Joakim_Pettersson_cs_CV.docx")
    CSCoverLetter().build("Joakim_Pettersson_cs_letter.docx")

