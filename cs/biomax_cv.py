# biomax_cv.py
# Add a Temporary Research Engineer - BioMAX – MAX IV Laboratory profile
# Recommended base profile branch: cs
# Recommended new profile branch: BioMAX
from cv import proposal, main

proposal.org = "BioMAX – MAX IV Laboratory",
proposal.role = "Temporary Research Engineer"
proposal.profile.append(
    "Experience working in radiation-exposed and EMI-sensitive environments at ESS, "
    "including signal-chain conditioning, detector integration, commissioning tasks, "
    "and stabilisation of complex experimental setups."
)
proposal.arguments.append(
    "At ESS I worked with Python integration for detectors and radiation-monitoring "
    "equipment, EMI auditing, reflection-free signal conditioning and commissioning of "
    "beam-adjacent instrumentation. This experience transfers directly to BioMAX "
    "operations and to supporting scientists in an operational beamline environment."
)

if __name__ == "__main__":
    main()