# biomax_cv.py

from cs_cv import CSCV, CSCoverLetter


class BioMAXCV(CSCV):
    """
    BioMAX-specific CV.

    Extends CSCV by appending a short ESS/BioMAX-related paragraph
    to the existing profile section, reusing the standard build()
    sequence from BaseCV.
    """

    def add_profile(self):
        # First add the control-systems profile from CSCV
        super().add_profile()

        # Then append a compact BioMAX/ESS-specific paragraph
        self.add_para(
            "Experience working in radiation-exposed and EMI-sensitive environments at ESS, "
            "including signal-chain conditioning, detector integration, commissioning tasks, "
            "and stabilisation of complex experimental setups."
        )


class BioMAXCoverLetter(CSCoverLetter):
    """
    BioMAX-specific cover letter.

    Extends CSCoverLetter by appending a BioMAX/ESS-oriented block
    to the introduction, while still using BaseCoverLetter.build()
    for the overall structure.
    """
    role = "Temporary Research Engineer",
    org = "BioMAX – MAX IV Laboratory",

    def add_intro(self):
        # First include the generic control-systems intro from CSCoverLetter
        super().add_intro()

        # Then add the original BioMAX/ESS-specific content
        self.add_para(
            "At ESS I worked with Python integration for detectors and radiation-monitoring "
            "equipment, EMI auditing, reflection-free signal conditioning and commissioning of "
            "beam-adjacent instrumentation. This experience transfers directly to BioMAX "
            "operations and to supporting scientists in an operational beamline environment."
        )


if __name__ == "__main__":
    BioMAXCV().build("Joakim_Pettersson_BioMAX_CV.docx")
    BioMAXCoverLetter().build("Joakim_Pettersson_BioMAX_letter.docx")
