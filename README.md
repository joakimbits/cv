# Word document variants archived as Markdown file variants in git

Tested for Joakim Pettersson cover letter and cv variants on Windows

```
# Setup
python -m venv venv
venv\Scripts\activate
git clone git@github.com:joakimbits/cv.git
python -m pip install --requirement requirements.txt

# Commands to:
# 1. Bring up an editor for this variant of [cover_and_cv.md](cover_and_cv.md)
# 2. Create .docx files when closing it
# 3. Rebuild [cover_and_cv.md](cover_and_cv.md) from those .docx files
git checkout extended
python -m cv
```