"""Generate cover-letter and CV PDFs directly: python -m pdf."""

from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re

import pymupdf


def inline(text: str) -> str:
    """Render the small inline Markdown vocabulary used by the proposal."""
    technology = re.fullmatch(r'\*\*\*Technology:\*\* (.*)\*', text)
    if technology:
        return '<i><b>Technology:</b> ' + inline(technology[1]) + '</i>'
    text = text.replace('📧', 'Email:').replace('📱', 'Phone:').replace('🔗', 'LinkedIn:')
    tokens = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)|<br>|(\*{1,3})(.+?)\3")
    parts = []
    end = 0
    for match in tokens.finditer(text):
        parts.append(escape(text[end:match.start()]))
        label, url, stars, content = match.groups()
        if url:
            parts.append(f'<a href="{escape(url, quote=True)}">{inline(label)}</a>')
        elif stars:
            tags = {1: ('<i>', '</i>'), 2: ('<b>', '</b>'),
                    3: ('<b><i>', '</i></b>')}[len(stars)]
            parts.append(tags[0] + inline(content) + tags[1])
        else:
            parts.append('<br>')
        end = match.end()
    parts.append(escape(text[end:]))
    return ''.join(parts)


def document_html(markdown: str, *, cover: bool) -> str:
    paragraphs = []
    in_list = False
    for block in re.split(r'\n\s*\n', markdown.strip()):
        bullet = block.startswith('- ')
        if in_list and not bullet:
            paragraphs.append('</ul>')
            in_list = False
        if bullet:
            if not in_list:
                paragraphs.append('<ul>')
                in_list = True
            paragraphs.append('<li>' + inline(block[2:]) + '</li>')
        elif block.startswith('### '):
            paragraphs.append('<h3>' + inline(block[4:]) + '</h3>')
        elif block.startswith('# '):
            tag = 'h1' if not paragraphs else 'h2'
            paragraphs.append(f'<{tag}>' + inline(block[2:]) + f'</{tag}>')
        elif block.startswith('> '):
            style = 'argument' if cover else 'detail'
            paragraphs.append(f'<p class="{style}">' + inline(block[2:]) + '</p>')
        else:
            paragraphs.append('<p>' + inline(block) + '</p>')
    if in_list:
        paragraphs.append('</ul>')
    return '<html><body>' + ''.join(paragraphs) + '</body></html>'


def render(markdown: str, target: Path, *, cover: bool) -> None:
    css = '''
        body { font-family: sans-serif; font-size: 10pt; line-height: 1.2; }
        p { margin: 0 0 5pt; }
        h1 { font-size: 18pt; color: #0066b3; margin: 0 0 6pt; }
        h2 { font-size: 14pt; color: #0066b3; margin: 16pt 0 6pt;
             page-break-after: avoid; }
        h3 { font-size: 11pt; color: #0066b3; margin: 10pt 0 3pt;
             page-break-after: avoid; }
        a { color: #004a99; text-decoration: none; }
        ul { margin: 0 0 5pt; padding-left: 24pt; }
        li { margin-bottom: 3pt; }
        .detail { margin-left: 14pt; }
        .argument { margin: 12pt 28pt; }
    '''
    story = pymupdf.Story(html=document_html(markdown, cover=cover),
                          user_css=css)
    page = pymupdf.paper_rect('a4')
    mm = 72 / 25.4
    area = pymupdf.Rect(25 * mm, 20 * mm, page.width - 25 * mm,
                        page.height - 20 * mm)

    def rectangles(rectangle_number, filled):
        return page, area, None

    with story.write_with_links(rectangles) as result:
        result.save(str(target), garbage=4, deflate=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', default='cover_and_cv.md')
    parser.add_argument('--output-dir', default='.')
    args = parser.parse_args()
    # Use the same parser as the Word workflow to validate the source.
    from cv import Proposal
    proposal = Proposal(file=args.source)
    text = Path(args.source).read_text(encoding='utf-8')
    letter, resume = re.split(r'\n\s*---+\s*\n', text, maxsplit=1)
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stem = proposal.name.replace(' ', '_')
    for suffix, content, cover in (
        ('Cover_Letter', letter, True), ('CV', resume, False),
    ):
        target = folder / f'{stem}_{suffix}.pdf'
        render(content, target, cover=cover)
        print(f'Saved {target}')


if __name__ == '__main__':
    main()
