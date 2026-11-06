"""Build the RAIN oral demo talk track (.docx).

Follows the oral-demo-talk-track skill: cover, reading guide, plain-language
glossary, a presenter brief before each persona act, labeled turns with a
spoken "why they ask next" beat, impact beats, transition cards, a click
sequence table and a word-count audit.

House format: Calibri; spoken lines 12pt; highlighted-chip clicks as numbered
purple pills (#6A1B9A, badge #4A1170, purple used nowhere else); every other
action bold red; italic-gray stage directions; teal timing markers.

Usage: python3 build_talk_track.py <out.docx>
"""
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

OUT = sys.argv[1]
WPS = 2.3
CLICK_SECONDS = 3  # load and land time per click, chip or pane question

NAVY = RGBColor(0x0C, 0x49, 0x64)
TEAL = RGBColor(0x05, 0x96, 0xAE)
RED = RGBColor(0xC0, 0x00, 0x00)
GRAY = RGBColor(0x66, 0x66, 0x66)
INK = RGBColor(0x23, 0x1F, 0x20)
PURPLE = '6A1B9A'
PURPLE_DARK = '4A1170'

doc = Document()
for s in doc.sections:
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(1)
st = doc.styles['Normal']
st.font.name = 'Calibri'
st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn('w:eastAsia'), 'Calibri')


# ─── Rendering helpers ──────────────────────────────────────────────────────

def border(p, color, side='left', sz=36):
    pPr = p._p.get_or_add_pPr()
    b = OxmlElement('w:pBdr')
    e = OxmlElement(f'w:{side}')
    e.set(qn('w:val'), 'single')
    e.set(qn('w:sz'), str(sz))
    e.set(qn('w:space'), '8')
    e.set(qn('w:color'), color)
    b.append(e)
    pPr.append(b)


def para(text='', size=11, bold=False, italic=False, color=INK, align=None, before=0, after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    if align is not None:
        p.alignment = align
    if text:
        r = p.add_run(text)
        r.font.size = Pt(size)
        r.bold = bold
        r.italic = italic
        r.font.color.rgb = color
    return p


def h1(t): para(t, 16, True, color=NAVY, before=18, after=4)
def h2(t): para(t, 13, True, color=NAVY, before=12, after=4)
def label(t): para(t, 11.5, True, color=NAVY, before=8, after=2)
def meta(t): para(t, 11, True, color=TEAL, after=8)
def spoken(t): para(t, 12, color=INK, after=1)
def gap(): para('', after=4)
def stage(t): para(t, 11, italic=True, color=GRAY, before=4, after=4)
def click(t): para(t, 11, True, color=RED, before=4, after=4)
def timing(t): para(t, 11, True, color=TEAL, before=2, after=6)


def breath_lines(t, limit=9):
    """Split a sentence at commas and colons, then halve any chunk over the limit."""
    chunks = [c for c in re.split(r'(?<=[,:])\s+', t) if c]
    out = []
    for c in chunks:
        w = c.split()
        while len(w) > limit:
            cut = len(w) // 2
            out.append(' '.join(w[:cut]))
            w = w[cut:]
        out.append(' '.join(w))
    return out


def impact(t):
    lines = breath_lines(t)
    for i, ln in enumerate(lines):
        p = para(ln, 12, color=INK, before=4 if i == 0 else 0, after=4 if i == len(lines) - 1 else 0)
        border(p, '2E8B57')


def run_shaded(p, text, fill, size=10.5):
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    rPr = r._r.get_or_add_rPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    rPr.append(shd)
    return r


def chip_pill(n, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(6)
    run_shaded(p, f' CHIP {n} ', PURPLE_DARK)
    run_shaded(p, f'  {text}  ', PURPLE, 11)


def shade_cell(c, fill):
    tcPr = c._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    tcPr.append(shd)


def brief_box(lines):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.rows[0].cells[0]
    shade_cell(c, 'F2F7F9')
    tcPr = c._tc.get_or_add_tcPr()
    bd = OxmlElement('w:tcBorders')
    for side, sz, col in [('top', 4, 'B7D7E0'), ('bottom', 4, 'B7D7E0'), ('right', 4, 'B7D7E0'), ('left', 36, '0596AE')]:
        e = OxmlElement(f'w:{side}')
        e.set(qn('w:val'), 'single')
        e.set(qn('w:sz'), str(sz))
        e.set(qn('w:color'), col)
        bd.append(e)
    tcPr.append(bd)
    p = c.paragraphs[0]
    r = p.add_run('PRESENTER BRIEF, read to yourself before this act, not aloud.')
    r.bold = True
    r.font.color.rgb = TEAL
    r.font.size = Pt(10.5)
    for ln in lines:
        q = c.add_paragraph()
        q.paragraph_format.space_after = Pt(3)
        m = re.match(r'^(.+?:)(\s.*)$', ln)
        if m and len(m.group(1)) < 44:
            a = q.add_run(m.group(1))
            a.bold = True
            a.font.size = Pt(10.5)
            a.font.color.rgb = INK
            b = q.add_run(m.group(2))
        else:
            b = q.add_run(ln)
        b.font.size = Pt(10.5)
        b.font.color.rgb = INK
    gap()


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = 'Table Grid'
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ''
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(10)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade_cell(c, '0C4964')
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ''
            p = cells[i].paragraphs[0]
            if isinstance(v, tuple) and v[0] == 'chip':
                run_shaded(p, f' CHIP {v[1]} ', PURPLE_DARK, 9)
                run_shaded(p, f' {v[2]} ', PURPLE, 9.5)
            elif isinstance(v, tuple) and v[0] == 'click':
                r = p.add_run(v[1])
                r.bold = True
                r.font.color.rgb = RED
                r.font.size = Pt(9.5)
            else:
                italic = isinstance(v, str) and v.startswith('_')
                r = p.add_run(v.strip('_') if isinstance(v, str) else str(v))
                r.font.size = Pt(9.5)
                r.italic = italic
    if widths:
        t.autofit = False
        grid = t._tbl.tblGrid
        for i, gc in enumerate(grid.findall(qn('w:gridCol'))):
            gc.set(qn('w:w'), str(int(widths[i] * 1440)))
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    gap()


def transition_card(text):
    p = para('', after=0)
    border(p, 'BFBFBF', 'bottom', 6)
    para(text, 10.5, italic=True, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER, before=6, after=6)
    p = para('', after=6)
    border(p, 'BFBFBF', 'top', 6)


# ─── The script ─────────────────────────────────────────────────────────────
# Item kinds: ('s', lines) spoken; ('chip', label) highlighted chip;
# ('click', text) any other action; ('stage', text); ('impact', text) spoken;
# ('why', heading, lines) spoken mindset beat.

PROLOGUE = [
    ('stage', '[Before you start: signed in at /login/rain, Reset demo clicked, browser at least 1,280 pixels wide so Ask AI sits beside each workbench. Switch personas only from the avatar menu.]'),
    ('s', """Rural health care runs on thin margins
and long drives.
We believe value-based care works
when everyone on the team
sees the same patients,
the same numbers,
and the next step."""),
    ('stage', '[Gesture to the Ask AI screen behind you.]'),
    ('s', """Meet Sierra Basin Community Health.
A rural health center network.
7 sites.
9,400 Medicaid members."""),
    ('s', """On January 1,
Nevada moved its rural counties
into managed care.
Sierra Basin signed its first
value-based contract.
The Q3 reconciliation just arrived."""),
    ('click', '[Point to the KPI row under the signals]'),
    ('s', """Cost: 6.7% above expected.
The quality gate needs 3 of 5 measures.
They meet 2.
58 days are left.
If the gate fails,
there are no shared savings."""),
    ('click', '[Open the avatar menu to show the 6 personas, then close it]'),
    ('s', """Today, 6 people work that same checkpoint.
4 find the problem and decide.
2 turn it into calls and visits.
And 1 patient closes the loop.
Let's start at the top."""),
]

ACTS = [
    dict(
        name='Gregory Haskins', short='Gregory', role='Chief Executive Officer', select=None,
        brief=[
            'Who / altitude / stakes: Gregory Haskins, MBA, is CEO of Sierra Basin Community Health, a fictional 7-site rural health center network. Highest altitude in the demo: money and the contract. He answers to his board and to High Desert Health Plan, and he is on the hook for shared savings and the 2027 renegotiation.',
            'Scenario / why now: the demo opens on him because the Q3 reconciliation is about money first. He is the default persona and lands on Ask AI.',
            'Turn 1: no click. Point to the 3 signal cards, the KPI row and the 58 Days Left tile. Point: the problem surfaces before he asks.',
            'Turn 2: CHIP 1 "Break down the gap". AI returns the $26 waterfall ($12 coding + $8 avoidable ED + $5.50 low-value care + $0.50 other) and the member segmentation (236 / 1,180 / 7,984). Point: about half the gap is documentation, not spending.',
            'Turn 3: CHIP 2 "What can we still recover by December 31?". AI returns do-nothing vs three moves (6.7% to about 3.5%, gate 2 to 3 of 5, $1.1M avoided) and a 4-step timeline. Point: there is a path inside 58 days.',
            'Turn 4: CHIP 3 "Generate the board brief", then CHIP 4 "Approve both hand-offs". AI returns a 1-page brief and 2 hand-off cards that flip to "Approved and sent". Point: insight becomes action, with a person approving.',
            'The one message: Gregory sees where the money goes and starts the fix the same morning.',
            'Delivery notes: pause on the waterfall. Lines that must hit: "Half of this gap is paperwork." and the principle, planted here: "The AI does the analysis. Gregory makes the call." Skip "Open in Value Insights" on the main run.',
            'In plain English (this act): PMPM = cost per member per month; expected = the contract benchmark; coding gap = conditions not recorded this year; avoidable ED = ER visits good primary care prevents; quality gate = 3 of 5 measures to earn savings. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Gregory Haskins.
He's the CEO of Sierra Basin.
7 sites.
9,400 attributed members.
1 value-based contract.
@@
His question this morning is simple:
will this contract make money,
or lose it?
He answers to a board,
and in 2027 he renegotiates this contract.
He doesn't open a dashboard.
He lands on Ask AI.""",
        turns=[
            ('Turn 1: The Morning Briefing', [
                ('stage', '[Pause. Let the 3 signal cards land.]'),
                ('s', """Before Gregory types a word,
the platform has read the Q3 file.
3 signals."""),
                ('click', '[Point to the Cost Running Above Expected card]'),
                ('s', """$412 against $386
per member per month.
6.7% above expected.
About $2.9 million a year."""),
                ('s', """The quality gate:
2 of the 3 measures he needs.
And $618K a year in low-value care."""),
                ('click', '[Point to the Days Left in Contract Year tile]'),
                ('s', """58 days left.
That's proactive detection.
The problem finds Gregory,
not the other way around."""),
                ('why', 'Why Gregory asks next', """Now Gregory knows he's over.
But 6.7% hides a lot.
Is this real spending,
or something else?
He can't defend a number to his board
that he can't explain.
So he asks for the breakdown."""),
            ]),
            ('Turn 2: The $26 Gap, in 4 Parts', [
                ('chip', 'Break down the gap'),
                ('stage', '[Pause. Let the waterfall land.]'),
                ('s', """$26 per member per month.
4 parts."""),
                ('s', """$12 is a coding gap.
Not spending.
73 high-need members
whose conditions weren't recorded this year.
So the benchmark thinks they're healthier
than they are."""),
                ('s', """$8 is avoidable ER use.
$5.50 is low-value care.
50 cents is noise."""),
                ('click', '[Scroll to the member segmentation card]'),
                ('s', """And here's who drives it.
236 high-need members:
41% of spend.
1,180 rising-risk members
who can still change."""),
                ('click', '[Point to the 1,180 row]'),
                ('s', """Half of this gap is paperwork.
And that matters.
Spending takes a year to change.
Documentation can be fixed at the next visit.
That's explainable UI:
the system shows its math,
not just its answer."""),
                ('why', 'Why Gregory asks next', """Now Gregory knows the gap is partly fixable on paper.
But a board doesn't want a diagnosis.
It wants a plan.
And there are only 58 days.
So he asks what he can still recover."""),
            ]),
            ('Turn 3: 3 Moves in 58 Days', [
                ('chip', 'What can we still recover by December 31?'),
                ('stage', '[Pause. Let the scenario panel land.]'),
                ('s', """Do nothing:
6.7% over.
Gate at 2 of 5.
$0 avoided."""),
                ('s', """3 moves:
about 3.5% over.
Gate at 3 of 5.
$1.1 million avoided over 12 months."""),
                ('click', '[Point to the timeline under the scenario]'),
                ('s', """Move 1: recapture coding for the 73.
That alone halves the gap on paper."""),
                ('click', '[Point to step 2 of the timeline]'),
                ('s', """Move 2: about 180 more blood pressure readings
under control.
Home cuffs count.
So telehealth works
for the 268 members who drive over an hour."""),
                ('click', '[Point to step 4, 2027]'),
                ('s', """Move 3: start outreach to the top 300 now.
That pays off mostly in 2027,
right when he renegotiates."""),
                ('impact', 'For Sierra Basin, that is the difference between keeping shared savings and walking into 2027 from a weak position.'),
                ('why', 'Why Gregory asks next', """Now Gregory has a plan.
But a plan in a chat isn't a decision.
His board needs it on 1 page,
and his team needs owners.
So he asks for the board brief."""),
            ]),
            ('Turn 4: The Board Brief and 2 Hand-offs', [
                ('chip', 'Generate the board brief'),
                ('stage', '[Pause. Let the brief preview land.]'),
                ('s', """1 page.
The checkpoint.
The 4-part gap.
3 moves, with owners and dates.
And the 2027 position."""),
                ('click', '[Scroll to the 2 hand-off cards]'),
                ('s', """And 2 hand-offs, ready.
The top 300 outreach list,
to the care team.
The 73-member coding list,
to Dr. Castellanos.
Each lands on its owner's own screen,
with the list attached
and the reason written down."""),
                ('chip', 'Approve both hand-offs'),
                ('s', """Approved and sent,
in 1 click."""),
                ('click', '[Point to the 2 cards, now Approved and sent]'),
                ('s', """Notice what he didn't do.
No spreadsheet export.
No email to 3 people.
No meeting to kick it off.
Zero data re-entry."""),
                ('s', """His board gets 1 page.
His team gets the work.
The AI does the analysis.
Gregory makes the call.
Remember that."""),
            ]),
        ],
        impact='In 4 questions, Gregory went from a bad number to an approved plan, before his first meeting of the day.',
        switch=('Why we switch to Dr. Naomi Castellanos', """Gregory owns the money.
He can approve a plan.
He can't change how a clinician orders an X-ray.
And the quality gate isn't a money problem.
It's clinical.
Blood pressure, screenings,
how providers order care.
That belongs to his chief medical officer,
Dr. Naomi Castellanos."""),
        transition='Transition: Gregory Haskins to Dr. Naomi Castellanos | CMO and quality lead | "The gate is clinical" | ~3 seconds',
    ),
    dict(
        name='Dr. Naomi Castellanos', short='Naomi', role='Chief Medical Officer and Quality Lead', select='Dr. Naomi Castellanos',
        brief=[
            'Who / altitude / stakes: Dr. Naomi Castellanos is CMO and the value-based care quality lead. A clinician-executive: she owns the 5 gate measures and how providers order care. She needs 3 measures at target to keep shared savings, and she has to change practice without alienating clinicians.',
            'Scenario / why now: Gregory just sent her the 73-member coding list. The gate is the clinical half of his problem, so she takes the stage next.',
            'Turn 1: no click. The quality gate tracker shows 2 of 5 met; BP control 58% against 65%. Point: the target is reachable, because 412 are within 10 points.',
            'Turn 2: CHIP 5 "What is happening at Winnemucca?". AI returns imaging by site (27% vs 9%), a monthly trend marked at the April locum rotation, and the top 5 low-value measures. Point: a pattern, not one provider.',
            'Turn 3: CHIP 6 "Which gaps can we close in 58 days?". AI returns current vs projected vs target for each measure and the 268 / 144 / 37 visit-mode tiles. Point: spend 58 days on the measure that can move.',
            'Turn 4: CHIP 7 "Launch the BP campaign", then CHIP 8 "Approve and send to the Worklist". AI returns the 412-member campaign with the top 5 (Linda Garcia is rank 1) and a launch card. Point: a ranked list, approved by a person, lands on the care team\'s screen.',
            'The one message: Naomi puts her 58 days where the measure can move, and fixes waste without blaming a doctor.',
            'Delivery notes: plant Linda at the top-5 table ("Remember Linda.") and give it a beat. Must hit: "A missing order set, not a bad doctor." Do not click Open on the launch card on the main run.',
            'In plain English (this act): CMS165 = blood pressure control measure; CMS122 = HbA1c over 9%, lower is better; CMS130 = colorectal screening; locum = temporary rotating clinician; order set = a clinic\'s default orders; FIT kit = mail-in colon screening test. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Dr. Naomi Castellanos.
Chief medical officer,
and the quality lead for this contract.
5 measures.
7 sites.
She needs 3 measures at target
to keep shared savings.
Right now she has 2.
@@
She's a physician.
She knows every quality number
is really hundreds of patient visits.
Same Ask AI.
Her own morning.""",
        turns=[
            ('Turn 1: The Quality Gate at a Glance', [
                ('stage', '[Pause. Let the quality gate tracker land.]'),
                ('s', """2 of 5 met.
3 needed.
Blood pressure control: 58%.
The target is 65%.
58 days."""),
                ('click', '[Point to the BP Control Short of Target card]'),
                ('s', """But read the second line.
412 hypertensive members
are within 10 points of control.
So the target is reachable.
That's the difference
between a red number and a plan."""),
                ('click', '[Point to the Winnemucca and coding signal cards]'),
                ('s', """And 2 more signals:
an imaging cluster at Winnemucca,
and the 73 members Gregory just sent her."""),
                ('why', 'Why Naomi asks next', """Naomi knows blood pressure is her best shot.
But something else bothers her.
Wasted imaging at 1 site
is money, and it's a provider conversation
she has to get right.
So she starts with Winnemucca."""),
            ]),
            ('Turn 2: 1 Site, 1 Pattern', [
                ('chip', 'What is happening at Winnemucca?'),
                ('stage', '[Pause. Let the site chart land.]'),
                ('s', """Low back pain imaging.
9% across the network.
27% at Winnemucca."""),
                ('click', '[Scroll to the monthly trend]'),
                ('s', """It jumped in April.
The same month the locum rotation began."""),
                ('click', '[Scroll to the low-value measures table]'),
                ('s', """71% of $162K
in low-value imaging
comes from that 1 site.
No red-flag diagnoses coded."""),
                ('click', '[Scroll back to the line under the trend: 3 rotating clinicians]'),
                ('s', """And 3 rotating clinicians
order at the same rate.
So this isn't 1 bad doctor.
It's a missing order set.
A rotation started,
and the default orders never followed it."""),
                ('stage', '[Pause. Let that land.]'),
                ('s', """Notice what the platform didn't do.
It didn't hand her a list of doctors
to call in.
It handed her the reason.
That's anomaly detection,
with the context to act fairly."""),
                ('why', 'Why Naomi asks next', """Now Naomi knows how to fix the imaging:
a protocol, not a reprimand.
But imaging doesn't pass the gate.
Measures do.
With 58 days left,
she needs to know which ones can still move."""),
            ]),
            ('Turn 3: The 1 to Win', [
                ('chip', 'Which gaps can we close in 58 days?'),
                ('stage', '[Pause. Let the projection chart land.]'),
                ('s', """Blood pressure is the one to win.
About 210 of the 412
should reach control with a recheck.
She needs 180."""),
                ('click', '[Point to the 3 tiles under the chart]'),
                ('s', """268 drive more than an hour.
They get a telehealth recheck
with a home cuff.
Home readings count for the measure.
144 come in person.
37 need a cuff shipped first."""),
                ('click', '[Point to CMS130 and CMS122 in the chart]'),
                ('s', """Colorectal screening gains about 4 points
with mailed FIT kits.
Worth starting,
but short of the gate this year.
HbA1c won't move in 58 days.
That's a Q1 plan."""),
                ('stage', '[Pause.]'),
                ('s', """It's also telling her
where not to spend her 58 days.
That's just as valuable.
That's predictive intelligence:
effort goes where the measure can move."""),
                ('why', 'Why Naomi asks next', """Now Naomi has picked her measure.
But a projection doesn't book a visit.
She needs a real list,
ranked,
with a visit mode for every member.
So she launches the campaign."""),
            ]),
            ('Turn 4: The Campaign, Ranked', [
                ('chip', 'Launch the BP campaign'),
                ('stage', '[Pause. Let the campaign preview land.]'),
                ('s', """412 members,
ranked by how likely they are
to reach control."""),
                ('click', '[Point to row 1 of the top 5 table]'),
                ('s', """Rank 1.
Linda Garcia.
148 over 92 in August.
An 81-minute drive.
No visit in 7 months.
She isn't a statistic.
She's someone who would come in,
if coming in didn't take 3 hours round trip.
Remember Linda."""),
                ('stage', '[The launch card can open Quality Gate and Campaigns. Do not click Open on the main run.]'),
                ('chip', 'Approve and send to the Worklist'),
                ('click', '[Point to the hand-off card: Approved and sent]'),
                ('s', """Approved.
She saw the ranking and the visit modes
before she said yes.
The campaign is on the care team's worklist.
Teresa's 46 are flagged top priority this week."""),
                ('click', '[Point to the Teresa line in the answer]'),
                ('s', """Every member carries a visit mode
and a reason.
Nobody rebuilds it from a spreadsheet.
The reasons travel with the list.
Naomi decided.
The platform delivered."""),
            ]),
        ],
        impact='For Sierra Basin, about 210 controlled readings is the gate: 3 of 5, and shared savings kept.',
        switch=('Why we switch to Raj Malhotra', """Naomi trusts the ranking.
But should she?
That ranking comes from a risk model.
Every call follows that order.
If the model is wrong,
the care team calls the wrong people first.
The person who answers for that model
is the CIO, Raj Malhotra."""),
        transition='Transition: Dr. Naomi Castellanos to Raj Malhotra | CIO and AI governance lead | "Can we trust the ranking?" | ~3 seconds',
    ),
    dict(
        name='Raj Malhotra', short='Raj', role='Chief Information Officer and AI Governance Lead', select='Raj Malhotra',
        brief=[
            'Who / altitude / stakes: Raj Malhotra is CIO and the data and AI governance lead. Technical executive: he owns the pipelines, data freshness and the impactability model. He is accountable that an AI ranking is fair before it decides who gets a call.',
            'Scenario / why now: Gregory approved the top 300 and Naomi launched a ranked campaign. Both rest on Raj\'s model, and the model just failed its fairness check.',
            'Turn 1: no click. The model card says v1.3, subgroup check failed; freshness tiles show the 45-day claims lag. Point: the platform audits its own AI.',
            'Turn 2: CHIP 9 "Show me the subgroup result". AI returns rank by condition group (frontier vs town), drive time vs visits, and a map of frontier places. Point: the bias is explained in plain terms.',
            'Turn 3: CHIP 10 "What changes if we fix it?". AI returns 4 tiles (gap 18% to 3%, 57 in and 57 out, 41 count toward CMS165, accuracy 0.81) and a sample of the swaps. Point: fairness and the quality gate move together.',
            'Turn 4: CHIP 11 "Generate the governance packet", then CHIP 12 "Sign off and release". AI returns the packet, a preview of the care team\'s banner, then the sign-off card waiting on the CMO. Point: 2 people sign before the model changes who gets called.',
            'The one message: the platform checks its own AI, explains the bias, and a person signs before anything changes.',
            'Delivery notes: must hit "Fewer visits is not the same as healthier." Plant the banner ("Remember that banner."); it comes back on Teresa\'s worklist. Do not click Open on the launch card.',
            'In plain English (this act): impactability score = ranks who can still change; subgroup check = fairness test across groups; frontier = remote, very sparse area; AUC = ranking accuracy, 0.5 is a coin flip; claims lag = bills arrive 45 days late; ADT = hospital admit alerts. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Raj Malhotra.
CIO,
and the lead for data and AI governance.
Every number you've seen so far
comes through his pipelines.
@@
And every ranking
comes from a model he signs off on.
When a regulator asks,
why did your AI skip this patient,
Raj is the one who answers.""",
        turns=[
            ('Turn 1: A Model That Failed Its Check', [
                ('stage', '[Pause. Let the model card land.]'),
                ('s', """Raj's briefing doesn't start with a dashboard.
It starts with a warning.
The impactability model,
version 1.3,
failed its subgroup check."""),
                ('click', '[Point to the first signal card]'),
                ('s', """Members in frontier ZIP codes
rank 18% lower
than similar members in town.
57 high-need frontier members
are missing from the top 300.
That's the list Gregory just approved."""),
                ('click', '[Point to the freshness tiles]'),
                ('s', """Plus the usual 45-day claims lag."""),
                ('why', 'Why Raj asks next', """Raj knows the model is unfair to someone.
He doesn't know why yet.
And he can't defend a fix
he can't explain.
So he asks for the subgroup result."""),
            ]),
            ('Turn 2: Fewer Visits Is Not Healthier', [
                ('chip', 'Show me the subgroup result'),
                ('stage', '[Pause. Let the subgroup chart land.]'),
                ('s', """Frontier members rank lower
in every condition group."""),
                ('click', '[Scroll to the drive-time chart]'),
                ('s', """Here's why.
A 74-minute median drive.
190 with no broadband.
31% fewer primary care visits."""),
                ('s', """Fewer visits mean fewer claims.
And the model reads fewer claims
as lower risk."""),
                ('click', '[Scroll to the frontier places map]'),
                ('s', """Same conditions.
Same labs.
Ranked lower,
because they live far away."""),
                ('click', '[Point to the frontier places on the map]'),
                ('s', """This isn't a bug in the code.
It's a bias in the data.
The model learned that people who don't come in
must be healthy.
In rural Nevada,
that's backwards."""),
                ('stage', '[Pause.]'),
                ('s', """Fewer visits is not the same as healthier."""),
                ('s', """That's explainable AI:
the cause in plain language,
not a black box."""),
                ('stage', '[The launch card offers Model Governance. Do not click Open on the main run.]'),
                ('why', 'Why Raj asks next', """Now Raj knows the cause.
But fixing a model has a cost.
He has to know it won't break accuracy,
or the gate Naomi is chasing.
So he asks what changes if he fixes it."""),
            ]),
            ('Turn 3: The Fix, Before It Ships', [
                ('chip', 'What changes if we fix it?'),
                ('stage', '[Pause. Let the 4 tiles land.]'),
                ('s', """Add access to the model:
drive time,
broadband,
missed visits,
shortage areas."""),
                ('s', """The frontier gap drops
from 18% to 3%.
Inside the 5% release threshold.
57 frontier members enter the top 300.
57 lower-need town members leave.
They still get care.
They just aren't first."""),
                ('click', '[Point to the Count toward CMS165 tile]'),
                ('s', """And 41 of them
are in the blood pressure measure.
Fairness and the quality gate
move in the same direction."""),
                ('click', '[Point to the accuracy tile]'),
                ('s', """Accuracy holds at 0.81.
That's the trade-off a CIO fears:
fix fairness,
lose accuracy.
Here, he loses nothing."""),
                ('impact', 'For Sierra Basin, the patients hardest to reach stop being the patients the model forgets.'),
                ('why', 'Why Raj asks next', """Raj is convinced.
But he can't flip a switch
on a model that decides who gets a call.
Governance needs a record,
and a second signature.
So he asks for the governance packet."""),
            ]),
            ('Turn 4: The Packet and the Sign-off', [
                ('chip', 'Generate the governance packet'),
                ('stage', '[Pause. Let the packet preview land.]'),
                ('s', """Updated model card.
Before and after results.
The feature change log.
A sign-off page for Raj and Dr. Castellanos."""),
                ('click', '[Scroll to the banner preview]'),
                ('s', """And this banner.
Until both sign,
the care team sees the current ranking,
with a pending-fix note.
Remember that banner."""),
                ('chip', 'Sign off and release'),
                ('s', """Signed.
Raj's half of the release is done."""),
                ('click', '[Point to the 2 signature rows]'),
                ('s', """The release now waits
on 1 more signature:
Naomi's.
2 people sign
before the model changes who gets called.
And the packet is the audit trail.
If anyone asks next year
why the ranking changed,
the answer is already written,
with both names on it."""),
                ('stage', '[Pause.]'),
                ('s', """That's governance built into the work,
not bolted on after."""),
            ]),
        ],
        impact='In 4 questions, Raj found a bias, proved the fix, and documented it for audit.',
        switch=('Why we switch to Dr. Lauren Pike', """Raj fixed this inside 1 network.
But the same pattern,
long drives,
thin claims,
missed care,
shows up across rural Nevada.
And it can't be fixed
1 network at a time.
The person who sees all of it
is the state program lead,
Dr. Lauren Pike."""),
        transition='Transition: Raj Malhotra to Dr. Lauren Pike | State program lead | "The same pattern, statewide" | ~3 seconds',
    ),
    dict(
        name='Dr. Lauren Pike', short='Lauren', role='Program Lead, Rural Health Outcomes Accelerator', select='Dr. Lauren Pike',
        brief=[
            'Who / altitude / stakes: Dr. Lauren Pike runs the Rural Health Outcomes Accelerator, 1 of Nevada\'s 4 Rural Health Transformation (RHTP) initiatives (an illustrative role). State altitude: she decides where funds go across networks and reports outcomes to CMS, without identified patient data.',
            'Scenario / why now: Raj saw the access pattern inside 1 network. Lauren sees it across 4 networks, 6 counties and 31,600 members, aggregated and de-identified.',
            'Turn 1: no click. The county map and 3 signals: primary care visits down 14% in Lander and Pershing, $2.4M low-value care, 6 low-broadband ZIP areas. Point: the same story at state scale.',
            'Turn 2: CHIP 13 "Show me the county view". AI returns the 6-county table; a dash marks a suppressed cell. Point: where it hurts, with privacy built in.',
            'Turn 3: CHIP 14 "Where should Outcomes Accelerator funds go first?". AI returns options A, B and C, the recommendation (fund A and C, run B as a data service) and a targeting map. Point: a defensible funding choice.',
            'Turn 4: CHIP 15 "Generate the CMS progress summary", then CHIP 16 "Export PDF". AI returns the summary preview and an export card. Point: reporting in 1 click.',
            'The one message: state money goes where the need is proven, and the report to CMS writes itself, privacy-safe.',
            'Delivery notes: must hit "No patient names. Ever." Do not click Open on the County Explorer launch card or Open print view on the main run.',
            'In plain English (this act): RHTP = federal Rural Health Transformation Program; HPSA = federal shortage area; SVI = social vulnerability index; suppressed cell = count under 11, hidden for privacy; grantee = a network receiving funds. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Dr. Lauren Pike.
She runs the Rural Health Outcomes Accelerator,
1 of Nevada's 4
rural health transformation initiatives.
She decides where state funds go,
and she reports results to CMS.
Without ever seeing
a patient's name.
@@
Her grantees each report
on a different template.
And her county data lives
in a dozen federal files.""",
        turns=[
            ('Turn 1: The State View', [
                ('stage', '[Pause. Let the county map land.]'),
                ('s', """4 participating networks.
18 sites.
6 rural counties.
31,600 members,
aggregated and de-identified."""),
                ('click', '[Point to the first signal card]'),
                ('s', """Since the managed care move,
primary care visits fell 14%
in Lander and Pershing.
And avoidable ER use went up."""),
                ('s', """About $2.4 million a year in low-value care
across the networks.
And 6 frontier ZIP areas
where broadband can't carry a video visit."""),
                ('why', 'Why Lauren asks next', """Lauren sees the drop.
But a statewide average can hide where it hurts.
Before she moves money,
she needs every county,
side by side.
So she asks for the county view."""),
            ]),
            ('Turn 2: 6 Counties, Side by Side', [
                ('chip', 'Show me the county view'),
                ('stage', '[Pause. Let the county table land.]'),
                ('s', """6 counties.
Same state,
very different counties.
Hypertension, diabetes, vulnerability,
shortage status, broadband,
visits and ER use."""),
                ('click', '[Point to the Lander and Pershing rows]'),
                ('s', """Lander and Pershing stand out.
The highest hypertension.
Whole-county shortage areas.
The largest visit drop.
The most avoidable ER visits."""),
                ('click', '[Point to the PC Visits and ED columns]'),
                ('s', """It's the pattern Raj saw in 1 network,
now at state scale.
Long drives,
fewer visits,
more ER.
And the counties hit hardest
have the least slack:
whole-county shortage areas,
and the weakest broadband."""),
                ('click', '[Point to the dash in the HF Members column]'),
                ('s', """And this dash.
Fewer than 11 members,
so the cell is suppressed.
No patient names.
Ever.
That's privacy by design,
not by policy memo."""),
                ('why', 'Why Lauren asks next', """Now Lauren knows where.
But she has 1 budget
and 3 ways to spend it.
She has to defend the choice to CMS
and to 4 networks.
So she asks where funds should go first."""),
            ]),
            ('Turn 3: 3 Options, 1 Recommendation', [
                ('chip', 'Where should Outcomes Accelerator funds go first?'),
                ('stage', '[Pause. Let the options table land.]'),
                ('s', """3 options, modeled."""),
                ('s', """A: care coordinators and telehealth rechecks
in Lander and Pershing.
About 5,000 members.
$1.4 million.
Avoidable ER down about 12% within a year."""),
                ('click', '[Point to row B]'),
                ('s', """B: shared low-value care feedback
across all 4 networks.
No new funds.
About a third of the $2.4 million."""),
                ('click', '[Point to row C]'),
                ('s', """C: mobile clinic days
for the 6 low-broadband ZIP areas.
$600K.
The access floor that A depends on."""),
                ('click', '[Scroll to the targeting map]'),
                ('s', """The recommendation:
fund A and C,
run B as a data service.
Notice how they connect.
A needs telehealth.
Telehealth needs broadband.
Where broadband fails,
C is the fallback.
And B costs nothing,
so it starts now."""),
                ('why', 'Why Lauren asks next', """Lauren has her answer.
But a recommendation in a chat
isn't a report CMS accepts.
It has to be sourced,
suppressed,
and ready to send.
So she asks for the progress summary."""),
            ]),
            ('Turn 4: The Report, in 1 Click', [
                ('chip', 'Generate the CMS progress summary'),
                ('stage', '[Pause. Let the summary preview land.]'),
                ('s', """People served, by county.
Outcome measures, by county.
The recommended funding.
Every figure tied to its source.
Small cells suppressed.
The funding options and county charts
ride along in the appendix."""),
                ('click', '[Scroll through the preview]'),
                ('chip', 'Export PDF'),
                ('s', """Ready to save."""),
                ('click', '[Point to the export card. Do not click Open print view.]'),
                ('s', """This is the report she used to build by hand,
from 4 networks' templates.
It's already de-identified,
so it can go to CMS
and back to the networks
as it is."""),
                ('click', '[Point back to the summary preview]'),
                ('s', """Every number traces back
to a public source
or the networks' own data.
The networks report in.
The state reports up.
Nobody retypes a number.
Weeks of grantee templates,
in 1 click,
for the whole state."""),
            ]),
        ],
        impact='For Nevada, that is funding aimed at 2 counties with evidence, and a CMS report that writes itself.',
        switch=('Why we switch to Teresa Lopez', """Everything so far has been insight.
Decisions, approvals, sign-offs.
The state can fund the work.
But someone still has to pick up the phone.
Now it has to become phone calls.
Naomi's campaign just landed
on a community health worker's list.
Let's meet Teresa Lopez."""),
        transition='Transition: Dr. Lauren Pike to Teresa Lopez | From insights to care management: different screens, on purpose | ~3 seconds',
    ),
    dict(
        name='Teresa Lopez', short='Teresa', role='Community Health Worker and Care Coordinator', select='Teresa Lopez',
        brief=[
            'Who / altitude / stakes: Teresa Lopez is a community health worker for Winnemucca and Battle Mountain. Front line and hands-on: about 200 open patients, a phone and a lot of road. She is on the hook for getting the right patients in, and she cannot tell from spreadsheets who matters most this week.',
            'Scenario / why now: this is the hand-off from insights to care management. Naomi\'s campaign and Gregory\'s top 300 just landed on her list. Her Ask AI is a task briefing, and her real work happens on traditional screens with Ask AI on the right.',
            'Turn 1: no click. Today\'s queue: 46 top priority, 5 no callback, 62 of 412 booked, 18 controlled. Point: a to-do list, not analytics.',
            'Turn 2: CHIP 17 "Open my worklist". The Worklist opens by itself, Linda selected, Ask AI on the right. Banners at the top: Naomi\'s campaign, Gregory\'s top 300 and, if Raj signed, the pending-fix banner. Point: every row says why this person, and why now.',
            'Turn 3: click "Why is she ranked first?" and "Give me talking points in Spanish for this patient" in the Ask AI pane. AI returns the ranking (94%, telehealth, cuff on file) and the talking points in Spanish and English. Point: help inside the screen she already uses.',
            'Turn 4: scroll to Call (phone, best time, shared family phone), then After the call; click Book visit. Scheduling opens on Linda. Point: she books while Linda is on the line, with zero data re-entry.',
            'The one message: Teresa\'s screen tells her who to call, why, what to say, and how to book.',
            'Delivery notes: this is the Linda callback ("And remember Linda?") and the banner callback ("remember Raj\'s banner?"). If the amber banner is not showing, skip that line. Do not click Confirm booking as Teresa; Brandon confirms in the next act. For questions: logging Declined, Wrong number or Left message switches booking off and says why; clicking the outcome again clears it.',
            'In plain English (this act): CHW = community health worker; worklist = ranked list of patients to call; visit mode = telehealth or in person; home cuff = blood pressure monitor at home; C or R = the patient\'s text reply, confirm or reschedule. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Teresa Lopez.
A community health worker.
2 sites,
Winnemucca and Battle Mountain,
and a lot of road.
About 200 open patients.
Until now,
she worked from spreadsheets
and sticky notes.
@@
Her question is the most practical
in the whole demo:
who do I call today,
and what do they need?""",
        turns=[
            ('Turn 1: Today\'s Calls', [
                ('stage', '[Pause. Let the task briefing land.]'),
                ('s', """Notice the change.
No signals.
No cost charts.
Teresa's briefing is a to-do list."""),
                ('click', '[Point to the Today\'s queue card]'),
                ('s', """46 top-priority patients this week.
5 people she called yesterday
haven't called back."""),
                ('click', '[Point to the progress bar]'),
                ('s', """And the campaign so far:
62 of 412 booked,
18 controlled.
The 5 who haven't called back
are flagged,
so nobody falls through
just because a message went unanswered."""),
                ('s', """Progressive disclosure:
only what she needs
to start her day."""),
                ('why', 'Why Teresa asks next', """Teresa knows how many.
But a number doesn't tell her
who to dial first.
She needs the list,
in order,
with the reasons.
So she opens her worklist."""),
            ]),
            ('Turn 2: The Worklist', [
                ('chip', 'Open my worklist'),
                ('stage', '[Pause. The Worklist opens on its own, with Ask AI on the right.]'),
                ('s', """This is a traditional screen.
A table, filters, a patient card.
And Ask AI comes along,
right beside it."""),
                ('click', '[Point to the banners at the top]'),
                ('s', """Naomi's campaign.
Gregory's top 300, queued next.
And remember Raj's banner?
Here it is.
A ranking update is pending.
Teresa keeps working the current list."""),
                ('click', '[Point to row 1]'),
                ('s', """And remember Linda?
Rank 1.
148 over 92.
An 81-minute drive.
No visit in 7 months."""),
                ('click', '[Point to the Top 3 reasons column]'),
                ('s', """Every row tells Teresa
why this person,
and why now.
The work arrives with its context.
She doesn't need to know
what a risk model is.
She sees the reasons in her own words:
a reading,
a drive,
a gap in visits."""),
                ('why', 'Why Teresa asks next', """Teresa trusts the list.
But she's about to call Linda,
and she wants to sound like she knows her.
Why is Linda first?
And what does she say,
in Spanish?"""),
            ]),
            ('Turn 3: Why Linda, and What to Say', [
                ('click', '[Click "Why is she ranked first?" in the Ask AI pane]'),
                ('stage', '[Pause. Let the answer land.]'),
                ('s', """94% likely to reach control
with 1 recheck.
Telehealth.
Cuff on file.
Near control,
still changeable,
held back by the drive."""),
                ('click', '[Click "Give me talking points in Spanish for this patient" in the Ask AI pane]'),
                ('s', """Spanish on the left.
English on the right.
Short and plain:
we can do a video visit,
with no drive to the clinic."""),
                ('click', '[Point to the note under the talking points]'),
                ('s', """And 1 guardrail:
no clinical advice by phone script.
Clinical questions go to the care team."""),
                ('s', """A spreadsheet could never do this.
It knows Linda prefers Spanish,
has a cuff at home,
and lives 81 minutes away.
And it writes the call around that.
Teresa just reads it."""),
                ('click', '[Point to "Viewing: Linda Garcia" at the top of the pane]'),
                ('s', """The pane knows which patient she's on.
That's context-aware help,
inside the screen she already uses."""),
                ('why', 'Why Teresa asks next', """Teresa is ready.
She has the reason
and the words.
Now she needs the number,
and a way to book Linda
before she hangs up."""),
            ]),
            ('Turn 4: Call and Book', [
                ('click', '[Scroll to Call in the patient card]'),
                ('s', """(775) 555-0107.
Best after 5 PM.
A shared family phone:
ask for Linda.
Small details.
They're the difference
between 1 call that connects
and 3 that don't.
Teresa calls.
Linda says yes
to a video visit.
No call notes to retype later."""),
                ('click', '[Scroll to After the call]'),
                ('s', """The card tells her what to do next.
If you reach them,
book while they're on the line.
If not,
log what happened.
If Linda had declined,
booking would switch off,
and the card would say why."""),
                ('click', '[Click Book visit]'),
                ('s', """Scheduling opens on Linda.
Her booking goes to central scheduling
with everything Teresa learned on the call.
No retyping.
Zero data re-entry."""),
                ('stage', '[Do not click Confirm booking as Teresa. Brandon confirms it in the next act.]'),
            ]),
        ],
        impact='For Sierra Basin, every booked recheck is 1 step closer to 180, and 1 fewer patient lost to a long drive.',
        switch=('Why we switch to Brandon Kee', """Teresa got the yes.
But a booking is more than a time.
Coverage has to check out,
and Linda has missed 2 visits before.
Teresa can't see 7 sites' calendars.
Brandon can.
That's central scheduling.
Let's meet Brandon Kee."""),
        transition='Transition: Teresa Lopez to Brandon Kee | Patient access coordinator | "The yes becomes a visit" | ~3 seconds',
    ),
    dict(
        name='Brandon Kee', short='Brandon', role='Patient Access Coordinator', select='Brandon Kee',
        brief=[
            'Who / altitude / stakes: Brandon Kee is the patient access coordinator: central scheduling for 7 sites and 2 telehealth providers. Hands-on and high volume. Patients who drive more than an hour miss visits at twice the rate, and every no-show is a wasted slot.',
            'Scenario / why now: Teresa got Linda\'s yes. Her booking is first in Brandon\'s queue of 23.',
            'Turn 1: no click. Today\'s queue: 23 bookings, 9 unconfirmed for tomorrow, 4 R replies; first booking is Linda. Point: the queue is already in order.',
            'Turn 2: CHIP 18 "Start bookings". Scheduling opens on Linda with Ask AI on the right: her phone and best time, telehealth recommended, slots sorted by drive time (Thursday 2 PM video selected), coverage active. Point: the right slot and coverage on 1 screen.',
            'Turn 3: click "Why telehealth for this patient?" in the Ask AI pane; scroll to Review and confirm; click Confirm booking. The reminder plan gives its reasons (2 missed visits, 81-minute drive, no visit in 7 months). Point: nothing is sent until Brandon confirms.',
            'Turn 4: click Reminders, point to Linda\'s SMS log and the call-task tile, then click Open the patient view. Point: reminders the patient answers, and a call task when she does not.',
            'The one message: the right slot, coverage checked and a reminder plan built on why patients miss, all before anything is sent.',
            'Delivery notes: must hit "Nothing is sent to Linda until Brandon confirms." Pause after Booked appears.',
            'In plain English (this act): eligibility check (270/271) = the insurance coverage question and answer; quiet hours = no texts 8 PM to 8 AM; R reply = the patient asks to reschedule; lapsed = coverage has ended. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Brandon Kee.
Patient access coordinator.
He books for 7 sites
and 2 telehealth providers.
Patients who drive more than an hour
miss visits at twice the rate.
Every missed visit
is a wasted slot.
@@
His day is a puzzle:
the right patient,
the right mode,
the right time,
across hours of road.""",
        turns=[
            ('Turn 1: The Queue', [
                ('stage', '[Pause. Let the queue card land.]'),
                ('s', """23 bookings waiting
from Teresa's worklist.
9 visits tomorrow,
still unconfirmed.
4 patients replied R,
and need new slots."""),
                ('click', '[Point to the First booking line]'),
                ('s', """First in line:
Linda Garcia.
Telehealth recheck.
81-minute drive.
Prefers Spanish.
He didn't build this queue.
Teresa's yes did.
Each booking arrives with the visit mode,
the reason
and the language attached.
Intelligent triage:
the queue is already in order."""),
                ('why', 'Why Brandon asks next', """Brandon knows where to start.
But he can't book from a summary.
He needs the slots,
the coverage,
and the reminder plan,
on 1 screen.
So he starts bookings."""),
            ]),
            ('Turn 2: The Right Slot', [
                ('chip', 'Start bookings'),
                ('stage', '[Pause. Scheduling opens on Linda, with Ask AI on the right.]'),
                ('s', """Step 1: choose a slot.
Linda's number and best time,
right at the top."""),
                ('click', '[Point to the recommendation line]'),
                ('s', """Telehealth recommended.
81-minute drive.
Broadband at home.
Visit type eligible."""),
                ('click', '[Point to the slot table]'),
                ('s', """Slots sorted by drive time.
Video visits first:
no drive at all.
Then the mobile clinic,
then in person.
Thursday, 2 PM, video, is selected.
For an in-person slot,
Linda would drive 81 minutes.
For this one,
she drives 0."""),
                ('click', '[Scroll to Check coverage]'),
                ('s', """Step 2: coverage.
Active with High Desert Health Plan.
Checked before he commits,
not after a denial.
If coverage had lapsed,
he'd see a flag
and an enrollment task,
and the booking would still go ahead."""),
                ('why', 'Why Brandon asks next', """Brandon has a slot and coverage.
But Linda has missed 2 visits.
A booking she doesn't show up for
is worse than no booking.
So he checks why telehealth,
and how the reminders will run."""),
            ]),
            ('Turn 3: Review, Then Confirm', [
                ('click', '[Click "Why telehealth for this patient?" in the Ask AI pane]'),
                ('s', """The reasons, in plain terms.
An 81-minute drive.
Broadband available.
Visit type eligible.
And home cuff readings count for the measure."""),
                ('click', '[Scroll to Review and confirm]'),
                ('s', """Step 3: the reminder plan.
Text, in Spanish.
72 hours, 24 hours and 3 hours before."""),
                ('click', '[Point to the Timing line]'),
                ('s', """Why 3?
2 missed visits,
an 81-minute drive,
and no visit in 7 months.
Quiet hours respected.
This is where patients usually slip:
a generic reminder,
in the wrong language,
at the wrong time.
Nothing is sent to Linda
until Brandon confirms.
That's the plan.
Now he commits."""),
                ('click', '[Click Confirm booking]'),
                ('s', """Booked.
Thursday, 2 PM, video."""),
                ('impact', 'For Sierra Basin, a reminder plan built on why patients miss visits protects every slot on the schedule.'),
                ('why', 'Why Brandon asks next', """The booking is done.
But Brandon's job isn't finished
until Linda shows up.
He wants to see
what Linda will actually receive."""),
            ]),
            ('Turn 4: The Reminder Log', [
                ('click', '[Click Reminders]'),
                ('stage', '[Pause. Let the reminder plans land.]'),
                ('s', """Every row is a patient and a plan.
Confirmed,
no reply,
or a change requested.
Brandon works the exceptions,
not the whole list."""),
                ('click', '[Point to Linda\'s SMS log]'),
                ('s', """Linda's log.
Booking confirmed by Brandon.
The 72-hour reminder, in Spanish.
And her reply:
C.
Confirmed.
She answered the first text.
She'd missed her last 2 visits.
That's the difference a plan makes."""),
                ('click', '[Point to the tiles at the top]'),
                ('s', """9 unconfirmed for tomorrow.
No reply by 24 hours before
becomes a call for Teresa.
4 R replies get 3 new slots by text,
without a phone call.
The loop runs itself.
That's what Brandon cares about.
Not a booked slot.
A filled one."""),
                ('click', '[Click Open the patient view]'),
            ]),
        ],
        impact='For Sierra Basin, every filled slot is a visit that counts: Brandon booked, checked coverage and planned reminders on 1 screen, with nothing re-keyed.',
        switch=('Why we switch to Linda Garcia', """We've seen 6 people work this checkpoint.
A CEO, a CMO, a CIO,
a state lead,
and 2 people on the front line.
None of it matters
unless 1 patient
gets her blood pressure checked.
So let's see it from her side."""),
        transition='Transition: Brandon Kee to Linda Garcia | The patient, by text only | ~3 seconds',
    ),
    dict(
        name='Linda Garcia', short='Linda', role='Patient (text messages only)', select=None,
        brief=[
            'Who / altitude / stakes: Linda Garcia is 58, a Medicaid member in Battle Mountain with hypertension and type 2 diabetes. An 81-minute drive, a shared family phone, prefers Spanish. She does not use a patient portal; she answers texts. She is not a RAIN user: she only receives texts.',
            'Scenario / why now: the end of the chain. Everything the 6 operators did reaches her as 4 texts.',
            'Turn 1: the patient view opens in a phone frame, in Spanish. Click English once for reviewers, then Next twice: the 72-hour reminder, her C reply and confirmation, the day-of reminder and a clinical question the text declines to answer. Point: no app, no portal, no drive.',
            'Turn 2: click Next once more. Her reading, 132/84, arrives; the green line above the phone says the gap is closed and the campaign is at 19 controlled. Point: the loop closes.',
            'The one message: the system meets Linda where she is, and her reading flows straight back into the quality measure.',
            'Delivery notes: pause on the green line. This resolves the Linda thread: "Remember Linda?"',
            'In plain English (this act): C or R = confirm or reschedule; 132/84 = under 140/90, so controlled; closed loop = the result counts toward the measure the same day. See the Plain-Language Glossary for the rest.',
        ],
        intro="""This is Linda.
58.
Battle Mountain.
Hypertension and diabetes.
She doesn't use a patient portal.
She does answer texts,
in Spanish.
No app.
No portal.
@@
The gap, the campaign,
the model fix, the booking:
all of it reaches her
as a few texts.
Here's her side.""",
        turns=[
            ('Turn 1: 4 Texts, No App', [
                ('click', '[Click English above the phone]'),
                ('s', """72 hours before:
first name, date, time, clinic.
Nothing else.
Reply C or R."""),
                ('click', '[Click Next on the phone]'),
                ('s', """She replies C.
Confirmed,
with her video link,
and 1 line:
have your monitor ready."""),
                ('click', '[Click Next on the phone]'),
                ('s', """The day of:
the link again.
And a question:
do I take my pill before the visit?
No medical advice by text.
The front desk calls her.
A guardrail Linda never sees,
and always benefits from."""),
                ('why', 'Why the last text matters', """The visit happens.
But the measure only counts
what it can see.
So the last text
matters most."""),
            ]),
            ('Turn 2: 132 Over 84', [
                ('click', '[Click Next on the phone]'),
                ('stage', '[Pause. Let the reading land.]'),
                ('s', """132 over 84.
Controlled.
This is the moment
the whole demo was built for.
1 reading,
from 1 patient,
at home,
on her own phone."""),
                ('click', '[Point to the green line above the phone]'),
                ('s', """Reading received.
Her blood pressure gap is closed.
The campaign now has 19 controlled.
Teresa's progress bar moves too.
And her next step is already set:
a recheck in 3 months,
with a reminder."""),
                ('click', '[Point to the last 2 texts in the phone]'),
                ('s', """Remember Linda?
Rank 1 on Naomi's list.
Called by Teresa.
Booked by Brandon.
Controlled,
from her kitchen table.
81 minutes of driving,
saved.
And that reading counts toward the measure
the same day.
No paper form.
No data entry at the clinic."""),
            ]),
        ],
        impact=None, switch=None, transition=None,
    ),
]

CLOSE = [
    ('click', '[Click Back to RAIN. Select Dr. Naomi Castellanos from the avatar menu. Click Quality Gate and Campaigns. Scroll to Closed loop.]'),
    ('s', """Back where we started.
Naomi's quality gate."""),
    ('click', '[Point to Progress from the care team]'),
    ('s', """63 of 412 booked.
19 controlled.
1 more patient
toward 180."""),
                ('click', '[Point to the Goal line]'),
                ('s', """The same morning
Gregory saw the gap."""),
    ('impact', 'For Sierra Basin, that is how the quality gate moves: 1 controlled reading at a time, counted the same day.'),
    ('s', """Every hand-off,
every sign-off,
every booking:
a person confirmed it.
The AI does the analysis.
People make the call."""),
    ('stage', '[Pause. Let the closed loop land.]'),
    ('click', '[Point to the Synthetic label on the card]'),
    ('s', """Under it:
19 public data sources
and clearly labeled synthetic data,
1 file per persona,
ready to swap for live APIs."""),
    ('s', """What you just saw is the beginning.
1 contract.
1 network.
1 patient.
The same platform
works for every network
in rural Nevada."""),
]


# ─── Counting, numbering and timing ─────────────────────────────────────────

def words(text):
    return len(re.findall(r"[A-Za-z0-9$%][A-Za-z0-9$%',.:/-]*", text))


def item_words(it):
    if it[0] in ('s', 'impact'):
        return words(it[1])
    if it[0] == 'why':
        return words(it[2])
    return 0


def item_actions(it):
    return 1 if it[0] in ('chip',) or (it[0] == 'click' and it[1].startswith('[Click')) else 0


def secs(items):
    return sum(item_words(i) for i in items) / WPS + CLICK_SECONDS * sum(item_actions(i) for i in items)


def mmss(t):
    t = int(round(t))
    return f'{t // 60}:{t % 60:02d}'


chip_no = 0
CHIPS = []  # (n, label, persona, turn)
CLICKS = []  # (persona, turn, text)
for act in ACTS:
    for title, items in act['turns']:
        for it in items:
            if it[0] == 'chip':
                chip_no += 1
                CHIPS.append((chip_no, it[1], act['short'], title))
            elif it[0] == 'click' and it[1].startswith('[Click'):
                CLICKS.append((act['short'], title, it[1]))

AUDIT = []  # (section, words, seconds, target)


def act_sections(act):
    out = []
    first, _, rest = act['intro'].partition('\n@@\n')
    intro = [('s', first)] + ([('click', '[Point to the name and role in the header]'), ('s', rest)] if rest else [])
    if act['select']:
        intro = [('click', f"[Select {act['select']} from the avatar menu]")] + intro
    out.append(('Introduction', intro, '45-70'))
    n = len(act['turns'])
    for i, (title, items) in enumerate(act['turns']):
        has_why = any(x[0] == 'why' for x in items)
        target = '80-130' if i == 0 else ('130-170' if has_why else '100-140')
        out.append((title, items, target))
    if act['switch']:
        out.append(('Session impact and switch', [('impact', act['impact']), ('why',) + act['switch']], '60-90'))
    return out


# ─── Document ───────────────────────────────────────────────────────────────

pro_secs = secs(PROLOGUE)
close_secs = secs(CLOSE)
act_totals = []
for act in ACTS:
    act_totals.append(sum(secs(items) for _, items, _ in act_sections(act)))
spoken_words = sum(item_words(i) for i in PROLOGUE + CLOSE) + sum(item_words(i) for act in ACTS for _, items, _ in act_sections(act) for i in items)
spoken_secs = spoken_words / WPS
live_secs = pro_secs + close_secs + sum(act_totals) + 3 * (len(ACTS) - 1)

# Cover
para('', after=60)
para('RAIN: Value-Based Care Intelligence', 24, True, color=NAVY, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)
para('Oral Demo Talk Track', 16, color=TEAL, align=WD_ALIGN_PARAGRAPH.CENTER, after=18)
para('University of Nevada, Reno  ·  Rural Health AI Infrastructure for Nevada', 12, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
para('State, Local & Education market', 12, align=WD_ALIGN_PARAGRAPH.CENTER, after=24)
para('Prologue  +  6 Persona Demo (4 insights, 2 care team)  +  Patient View  +  Close', 12, True, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
para(f'~{mmss(spoken_secs)} spoken  |  ~{mmss(live_secs)} live with clicks and screen loads', 12, True, color=TEAL, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
para('Slot: full persona walkthrough for review', 11, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
para('1 presenter, who drives the prototype and narrates every act', 11, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
para('Draft v1', 11, align=WD_ALIGN_PARAGRAPH.CENTER, after=30)
para('Sierra Basin Community Health and High Desert Health Plan are fictional. Every person in the demo is fictional, and all data is synthetic or illustrative.', 10, italic=True, color=GRAY, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# Reading guide
h1('Reading Guide')
table(['Convention', 'What it means'], [
    ('Near-black, one thought per line', 'Spoken content. Each line break is a breath pause.'),
    ('Shaded box, teal label', 'Presenter Brief. Read it to yourself before the act. Never spoken, never counted.'),
    ('Italic gray', 'Stage direction: pauses, notes, what to skip. Not spoken.'),
    (('chip', 'n', 'Chip label'), 'A highlighted chip on the golden path. Click exactly this chip. Numbered 1 to 18 across the demo.'),
    (('click', '[Click ...] / [Point to ...]'), 'Any other action on the prototype: a pane question, a button, a scroll, a point.'),
    ('Bold navy "Why ... asks next"', 'The persona\'s reasoning before the next click. Spoken.'),
    ('Green left border', 'Organizational impact beat. Spoken.'),
    ('Teal bold [m:ss]', 'Timing marker: where you should be, live, at the end of each turn.'),
    ('Centered gray card between rules', 'Transition card between persona acts. Visual only.'),
], widths=[2.3, 4.2])
label('Plant, callback, resolve: Linda')
para('PLANT (Naomi, Turn 4): "Rank 1. Linda Garcia. ... Remember Linda."', 11)
para('CALLBACK (Teresa, Turn 2): "And remember Linda? Rank 1."', 11)
para('RESOLVE (Linda, Turn 2): "Remember Linda? Rank 1 on Naomi\'s list. Called by Teresa. Booked by Brandon. Controlled, from her kitchen table."', 11)
label('Second thread: Raj\'s banner')
para('PLANT (Raj, Turn 4): "Remember that banner."   CALLBACK (Teresa, Turn 2): "And remember Raj\'s banner? Here it is."', 11)
label('Recurring principle')
para('Planted by Gregory (Turn 4): "The AI does the analysis. Gregory makes the call."  Called back at the close: "The AI does the analysis. People make the call."', 11)
label('Before you start')
for t in [
    'Sign in at /login/rain (credentials: app/docs/demo-credentials.md). Click Reset demo under the chat box, so every count starts from the morning.',
    'Use a browser window at least 1,280 pixels wide, so Ask AI sits beside each workbench instead of collapsing.',
    'Switch personas only from the avatar menu. Typing an address reloads the page and clears the demo\'s state (approvals, the booking, Linda\'s reading).',
    'Leave Auto-open workbenches off. The insights personas open a workbench only if you click Open; the care team\'s screens open by themselves.',
    'If a chip does not respond, type its label into the Ask AI box. Reset demo returns everyone to the morning.',
]:
    para('•  ' + t, 11, after=3)
doc.add_page_break()

# Glossary
h1('Plain-Language Glossary for the Presenter')
table(['Term', 'What it means', 'Why it matters here'], [
    ('_The setting and the stakes_', '', ''),
    ('Value-based contract', 'A deal where the health plan pays more if care costs less and quality is good', 'Sierra Basin signed its first one this year; the whole demo is its Q3 checkpoint'),
    ('Shared savings', 'The money the network keeps if cost lands under the benchmark', 'Lost if the quality gate fails; that is what is at stake'),
    ('Quality gate', 'A rule: 3 of 5 quality measures must hit target to earn shared savings', 'They meet 2. Naomi\'s act is about getting the third'),
    ('PMPM', 'Cost per member per month', '$412 actual against $386 expected: 6.7% over'),
    ('Expected cost (benchmark)', 'What the contract says care should cost, adjusted for how sick members are', 'Unrecorded conditions make it too low, which is the $12 coding gap'),
    ('58 days', 'Days left in the contract year', 'Every persona plans against this clock'),
    ('_The core process and its objects_', '', ''),
    ('Coding recapture', 'Recording a patient\'s chronic conditions again this year', 'Fixes the benchmark for 73 members; halves the gap on paper'),
    ('Avoidable ED', 'ER visits that good primary care usually prevents', '312 per 1,000 against 251; $8 of the gap'),
    ('Low-value care', 'Tests and treatments that add cost without helping', '$618K a year; Winnemucca\'s imaging is the biggest item'),
    ('Rising risk (impactable)', 'Members not yet expensive but heading there, who can still change', 'The 1,180; the top 300 get outreach first'),
    ('Hand-off', 'An approved list sent from one person\'s screen to another\'s', 'How insights become work: Gregory to the care team, Naomi to Teresa'),
    ('Worklist', 'Teresa\'s ranked list of patients to call', 'Where the campaign lands; Linda is rank 1'),
    ('Telehealth recheck with home cuff', 'A video visit with a home blood pressure reading', 'Counts for the measure and removes the 81-minute drive'),
    ('Reminder plan; C and R replies', 'Scheduled texts; the patient replies C to confirm or R to reschedule', 'Brandon reviews it before anything is sent; Linda replies C'),
    ('Closed loop', 'A result flowing back to the measure it affects', 'Linda\'s reading moves Naomi\'s tracker to 19 controlled'),
    ('_Quality measures_', '', ''),
    ('CMS165', 'Blood pressure under control (below 140/90)', 'The measure to win: 58% now, 65% target'),
    ('CMS122', 'Diabetes patients with HbA1c over 9% (lower is better)', 'Too slow to move in 58 days; planned for Q1'),
    ('CMS130', 'Colorectal cancer screening', 'FIT kits add about 4 points, short of target this year'),
    ('CMS125 and CMS2', 'Breast cancer screening; depression screening', 'The 2 measures already met'),
    ('FIT kit', 'A mail-in colon cancer screening test', 'Naomi\'s second-best move'),
    ('_Data and AI_', '', ''),
    ('Impactability score', 'The model that ranks who can still change', 'It decides the top 300 and the campaign order'),
    ('Subgroup check', 'A fairness test comparing how the model treats groups', 'It failed for frontier members; Raj\'s act'),
    ('Frontier', 'A very remote, sparsely populated area', 'Frontier members ranked 18% lower than similar town members'),
    ('AUC 0.81', 'How well the model ranks: 0.5 is a coin flip, 1 is perfect', 'Accuracy holds after the fix'),
    ('Claims lag; ADT', 'Bills arrive about 45 days late; hospital admit and discharge alerts arrive in under an hour', 'Why ED data looks old, and how Raj fills the gap'),
    ('Eligibility check (270/271)', 'The standard insurance coverage question and answer', 'Brandon sees "Active" before he confirms'),
    ('Synthetic data', 'Generated records that look real but describe nobody', 'Every patient, figure and organization in the demo'),
    ('_The state view_', '', ''),
    ('RHTP', 'The federal Rural Health Transformation Program', 'Lauren runs 1 of Nevada\'s 4 initiatives under it'),
    ('Outcomes Accelerator', 'Lauren\'s initiative (illustrative): value-based care for rural providers', 'The funds she allocates in Turn 3'),
    ('HPSA', 'A federally designated health professional shortage area', 'Lander and Pershing are whole-county shortage areas'),
    ('SVI', 'Social vulnerability index, 0 to 1', 'A column in the county table'),
    ('Suppressed cell', 'A count under 11 hidden as a dash, for privacy', 'Why no patient can be identified in Lauren\'s view'),
    ('_People and places (all fictional)_', '', ''),
    ('Sierra Basin Community Health', 'A 7-site rural health center network', 'The network in the story'),
    ('High Desert Health Plan', 'The managed care plan on the contract', 'Sent the Q3 reconciliation; covers Linda'),
    ('Winnemucca, Battle Mountain', 'Teresa\'s 2 sites', 'Winnemucca is also the imaging cluster'),
    ('Lander and Pershing', 'The 2 counties with the largest visit drop', 'Where option A puts the money'),
], widths=[1.6, 2.5, 2.4])
table(['Capability tag', 'In plain English'], [
    ('Proactive Intelligence', 'It flags the problem before anyone asks'),
    ('Converged Conversation', 'One question, answered across every source at once'),
    ('Anomaly Detection', 'It spots the pattern that does not belong, and explains it'),
    ('Predictive Intelligence', 'It projects what each option will do before you choose'),
    ('Automated Action', 'It drafts, packages and routes the work; a person approves'),
    ('Explainable UI / AI', 'It shows its reasoning, not just its answer'),
    ('Progressive disclosure', 'Only what this person needs now, with detail on demand'),
    ('Intelligent triage', 'The work arrives already in the right order'),
    ('Zero data re-entry', 'Nothing is typed twice; it carries from screen to screen'),
], widths=[2.0, 4.5])
doc.add_page_break()

# Click sequence at a glance
h1('Click Sequence at a Glance')
rows = []
for n, lab, who, turn in CHIPS:
    rows.append((who, turn.split(':')[0], ('chip', n, lab)))
table(['Persona', 'Turn', 'Highlighted chip'], rows, widths=[1.2, 1.0, 4.3])
para('Other actions, in order:', 11, True, color=NAVY, before=6)
table(['Persona', 'Turn', 'Action'], [(w, t.split(':')[0], ('click', c)) for w, t, c in CLICKS], widths=[1.2, 1.0, 4.3])
doc.add_page_break()

# Prologue
h1('Prologue')
meta(f'~{mmss(pro_secs)}  |  Presenter, on Gregory\'s Ask AI briefing')
elapsed = 0.0


def render(items):
    global chip_no
    for it in items:
        k = it[0]
        if k == 's':
            for ln in it[1].split('\n'):
                spoken(ln)
            gap()
        elif k == 'chip':
            chip_no += 1
            chip_pill(chip_no, it[1])
        elif k == 'click':
            click(it[1])
        elif k == 'stage':
            stage(it[1])
        elif k == 'impact':
            impact(it[1])
        elif k == 'why':
            label(it[1])
            for ln in it[2].split('\n'):
                spoken(ln)
            gap()


chip_no = 0
render(PROLOGUE)
elapsed += pro_secs
timing(f'[{mmss(elapsed)}]')

for ai, act in enumerate(ACTS):
    doc.add_page_break()
    n_turns = len(act['turns'])
    h1(f"Persona {ai + 1}: {act['name']}" if ai < 6 else f"Patient View: {act['name']}")
    meta(f"~{mmss(act_totals[ai])}  |  {n_turns} turns  |  {act['role']}")
    brief_box(act['brief'])
    for title, items, target in act_sections(act):
        if title == 'Introduction':
            label('Persona Introduction')
        elif title == 'Session impact and switch':
            label('Session Impact')
        else:
            h2(title)
        render(items)
        elapsed += secs(items)
        if title != 'Introduction':
            timing(f'[{mmss(elapsed)}]')
        AUDIT.append((f"{act['short']}: {title.split(':')[0]}", sum(item_words(i) for i in items), secs(items), target))
    if act['transition']:
        elapsed += 3
        transition_card(f"[{act['transition']}]")

doc.add_page_break()
h1('Close')
meta(f'~{mmss(close_secs)}  |  Back on Dr. Castellanos\'s Quality Gate')
render(CLOSE)
elapsed += close_secs
timing(f'[{mmss(elapsed)}]')

# Audit
doc.add_page_break()
h1('Word Count Audit')
rows = [('Prologue', str(sum(item_words(i) for i in PROLOGUE)), mmss(sum(item_words(i) for i in PROLOGUE) / WPS), 'under 207')]
flags = []
for sec, w, s, target in AUDIT:
    lo, hi = (int(x) for x in target.split('-'))
    note = target if lo <= w <= hi else f'{target} (now {w})'
    if not lo <= w <= hi:
        flags.append(sec)
    rows.append((sec, str(w), mmss(w / WPS), note))
cw = sum(item_words(i) for i in CLOSE)
rows.append(('Close', str(cw), mmss(cw / WPS), '120-200'))
rows.append(('Total spoken', str(spoken_words), mmss(spoken_secs), f'~{mmss(live_secs)} live'))
table(['Section', 'Spoken words', 'Spoken time (2.3 wps)', 'Target words'], rows, widths=[2.6, 1.1, 1.4, 1.4])
para(f'TOTAL: {spoken_words} words  |  ~{mmss(spoken_secs)} spoken  |  ~{mmss(live_secs)} live, adding {CLICK_SECONDS} seconds per chip or click for screens to load and land, and 3 seconds per transition card.', 11, True)
para('Counted: spoken lines, persona introductions, "why ... asks next" beats, impact beats and the switch lines. Not counted: Presenter Briefs, the glossary, the reading guide, chips, clicks, stage directions and timing markers. There are no backend bridges or setup slides in this version.', 10, color=GRAY)
doc.save(OUT)
print('spoken words', spoken_words, 'spoken', mmss(spoken_secs), 'live', mmss(live_secs), 'chips', len(CHIPS))
print('outside target:', flags)
