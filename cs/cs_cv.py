# cs/cs_cv.py
# Add an Embedded & Real-time Control Systems Engineer profile
# Recommended base profile branch: main
# Recommended new profile branch: cs
"""
Instruction (profile tool specification):
1. Checkout main
2. Run python -m cs.cs_cv (generates cs-profiled Word documents and updates cover_and_cv.md from them)
3. Inspect the generated Word documents.
4. Fix this cs/cs_cv.py and commit if needed on main.
5. Checkout cs and commit the profile (merge in Markdown format if needed).
6. Edit the word documents if necessary.
7. On word document touch: Run python -m cs.cs_cv again and make sure the word documents stay the same.
9. Commit the profile again if needed (now using word document touches also).
10. Push both main and the now updated cs branch.

This procedure allows editing of the profile in Python, Word and Markdown formats.
Make sure the name and role is exactly the same if edited manually in Word or Markdown format.
"""

from cv import proposal, main

proposal.specialities = ['Embedded', 'Real-time']
proposal.role = "Control Systems Engineer"
proposal.profile = [
    "Experienced in embedded C/C++, Python, PLC→MCU→FPGA timing, and EMI-robust real-time control.",

    "Background includes motion systems, power electronics and HVAC configuration tools.",

    "Comfortable with maintenance, operational stability and user-facing engineering work.",
]
proposal.work = "real-time control, embedded systems and practical engineering"
proposal.motivation = ( # With {}, I believe
    "a background spanning PLC-scale sequencing, microsecond MCU control and FPGA-based signal paths, "
    "I am comfortable working directly with hardware, instrumentation and timing-sensitive systems. "
    "Therefore"
)
proposal.arguments.append(
    "In addition to development work, I am fully comfortable with routine maintenance, "
    "operational stability and user-facing engineering tasks. I enjoy supporting "
    "colleagues in instrumentation environments, tracing issues through hardware, "
    "firmware and Python/C-based automation layers to maintain reliable operation."
)

if __name__ == "__main__":
    main()