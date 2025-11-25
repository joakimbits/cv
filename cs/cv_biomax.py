# cs/MAXIV_BioMAX_cv.py
from cs.cs_cv import CSCV, CSCoverLetter


class BioMAXCV(CSCV):

    def add_biomax_specific(self):
        self.p(
            "Experience working in radiation-exposed and EMI-sensitive environments at ESS, "
            "including signal-chain conditioning, detector integration, commissioning tasks, "
            "and stabilisation of complex experimental setups."
        )

    def build(self, filename="Joakim_Pettersson_CV_MAXIV_BioMAX.docx"):
        self.add_header()
        self.add_profile()
        self.add_core_competence()
        self.add_biomax_specific()
        self.add_experience()
        self.add_education()
        self.add_working_approach()
        self.save(filename)


class BioMAXCoverLetter(CSCoverLetter):

    def add_biomax_content(self):
        self.p(
            "At ESS I worked with Python integration for detectors and radiation-monitoring "
            "equipment, EMI auditing, reflection-free signal conditioning and commissioning of "
            "beam-adjacent instrumentation. This experience transfers directly to BioMAX operations."
        )

    def build(
        self,
        filename="Joakim_Pettersson_Cover_Letter_MAXIV_BioMAX.docx",
        role="Temporary Research Engineer",
        org="BioMAX – MAX IV Laboratory",
    ):
        self.add_contact_block()
        self.add_opening(role, org)
        self.add_generic_intro()
        self.add_cs_background()
        self.add_biomax_content()
        self.add_generic_closing()
        self.save(filename)

if __name__ == "__main__":
    cv = BioMAXCV()
    cv.build("Joakim_Pettersson_CV_MAXIV_BioMAX.docx")

    letter = BioMAXCoverLetter()
    letter.build(
        filename="Joakim_Pettersson_Cover_Letter_MAXIV_BioMAX.docx",
        role="Temporary Research Engineer",
        org="BioMAX – MAX IV Laboratory",
    )

    print("Generated BioMAX CV and cover letter.")
