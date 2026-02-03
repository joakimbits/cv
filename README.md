# Word document variants archived as Markdown file variants in git

Tested for Joakim Pettersson cover letter and cv variants on Windows

## Setup
```
git clone git@github.com:joakimbits/cv.git
cd cv
python -m venv venv
venv\Scripts\activate
python -m pip install --requirement requirements.txt
```

## See variants by their branch name
```
git remote show origin
```

## Basic usage

1. Bring up an editor for another variant of [cover_and_cv.md](cover_and_cv.md)
2. Create .docx files when closing it
3. Rebuild [cover_and_cv.md](cover_and_cv.md) from those .docx files

```
git checkout extended
python -m cv
```

## Advanced usage - importing a Hermes App CV

```
python -m cv "Additude - Hermes app.pdf"
```

The file parsers for .md and .pdf files are currently defined by regex patterns inside cv.py
but the plan is to refactor those into separate .md.fre and .pdf.fre file format files.

## Ongoing: PR for a new `git log --tree` command for viewing file variants in branches as an inheritance tree

https://github.com/joakimbits/git/tree/log-with-branch-history-tree/contrib/tree
