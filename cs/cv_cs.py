# cs/cs_cv.py
from cv import BaseCV, BaseCoverLetter


class CSCV(BaseCV):

    def add_profile(self):
        super().add_profile()
        self.p(
            "Specialised in motion systems, radar calibration, embedded control, real-time "
            "DAQ, PLC systems, Python/C++ tooling, and hardware/software co-design."
        )

    def add_core_competence(self):
        self.p().add_run("CORE COMPETENCE").bold = True
        self.p(
            "Instrumentation • Motion systems • Python • Embedded C/C++ • "
            "LabVIEW RT/FPGA • EMI-hardened systems • Automotive control • "
            "Detector integration • Real-time signal chains"
        )

    def build(self, filename):
        self.add_header()
        self.add_profile()
        self.add_core_competence()
        self.add_experience()
        self.add_education()
        self.add_working_approach()
        self.save(filename)


class CSCoverLetter(BaseCoverLetter):

    def add_cs_background(self):
        self.p(
            "My background spans radar calibration motion systems, MBE/e-beam nanofabrication "
            "equipment, drivetrain simulation, PLC-controlled thermal systems, Python/C++ "
            "instrumentation tooling and EMI-robust embedded designs."
        )

    def build(self, filename, role="Control Systems Engineer", org="your organisation"):
        self.add_contact_block()
        self.add_opening(role, org)
        self.add_generic_intro()
        self.add_cs_background()
        self.add_generic_closing()
        self.save(filename)

if __name__ == "__main__":
    cv = CSCV()
    cv.build("Joakim_Pettersson_CV_CS.docx")

    letter = CSCoverLetter()
    letter.build(
        filename="Joakim_Pettersson_Cover_Letter_CS.docx",
        role="Control Systems Engineer",
        org="your organisation",
    )

    print("Generated CS CV and cover letter.")
