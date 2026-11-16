#!/usr/bin/env python3
"""Render APTREDLIGHT procurement checklist from the approved Markdown source."""
from pathlib import Path
from xml.sax.saxutils import escape
import re
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch

BASE=Path(__file__).resolve().parent.parent
SRC=BASE/'resources/oem-private-label-buyers-checklist.md'
DST=BASE/'resources/oem-private-label-buyers-checklist.pdf'
RED=HexColor('#B53132'); INK=HexColor('#202126'); MUTED=HexColor('#64646C')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='CoverAPT',fontName='Helvetica-Bold',fontSize=22,leading=27,textColor=INK,spaceAfter=11))
styles.add(ParagraphStyle(name='SubAPT',fontName='Helvetica-Bold',fontSize=12,leading=17,textColor=RED,spaceAfter=14))
styles.add(ParagraphStyle(name='SectionAPT',fontName='Helvetica-Bold',fontSize=13,leading=18,textColor=INK,spaceBefore=15,spaceAfter=9,keepWithNext=True))
styles.add(ParagraphStyle(name='BodyAPT',fontName='Helvetica',fontSize=9,leading=14,textColor=INK,spaceAfter=8))
styles.add(ParagraphStyle(name='CheckAPT',fontName='Helvetica',fontSize=9,leading=14,textColor=INK,leftIndent=18,firstLineIndent=-18,spaceAfter=8))
styles.add(ParagraphStyle(name='NoteAPT',fontName='Helvetica-Oblique',fontSize=8.3,leading=12,textColor=MUTED,spaceBefore=8,spaceAfter=10))
def format_text(txt):
    txt=escape(txt.strip())
    return re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',txt)
def footer(c:Canvas,doc):
    c.saveState();width,height=doc.pagesize
    c.setStrokeColor(HexColor('#E8DFDB'));c.line(46,45,width-46,45)
    c.setFillColor(RED);c.setFont('Helvetica-Bold',8);c.drawString(46,32,'APTREDLIGHT | OEM/ODM BUYER CHECKLIST')
    c.setFillColor(MUTED);c.setFont('Helvetica',8);c.drawRightString(width-46,32,f'Page {doc.page}')
    c.restoreState()
DST.parent.mkdir(parents=True,exist_ok=True)
story=[]
for line in SRC.read_text(encoding='utf-8').splitlines():
    line=line.strip()
    if not line:continue
    if line.startswith('# '):story.append(Paragraph(format_text(line[2:]),styles['CoverAPT']))
    elif line.startswith('## '):story.append(Paragraph(format_text(line[3:]),styles['SubAPT']))
    elif line.startswith('### '):story.append(Paragraph(format_text(line[4:]),styles['SectionAPT']))
    elif line.startswith('- [ ] '):story.append(Paragraph('&#9633; '+format_text(line[6:]),styles['CheckAPT']))
    elif line=='---':story.append(HRFlowable(width='100%',thickness=1,color=HexColor('#E7D8D4'),spaceBefore=7,spaceAfter=9))
    elif line.startswith('**Note:**'):story.append(Paragraph(format_text(line),styles['NoteAPT']))
    else:story.append(Paragraph(format_text(line),styles['BodyAPT']))
doc=SimpleDocTemplate(str(DST),pagesize=(595.28,841.89),leftMargin=47,rightMargin=47,topMargin=42,bottomMargin=61,title="APTREDLIGHT OEM Private Label Buyer's Checklist",author="APTREDLIGHT")
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(f'Generated {DST}: {DST.stat().st_size} bytes')
