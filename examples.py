#!/usr/bin/env python
"""examples.py — Bundled example presentations + installer generation."""
import os
import re
import sys
import json
import html
import shutil
import argparse
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional
import textwrap

@dataclass
class SlideContent:
    title: str
    body: str = ""
    layout: str = "hero"
    kicker: str = ""
    headline: str = ""
    items: List[str] = field(default_factory=list)
    script: str = ""
    tone: str = "engaging"

@dataclass
class ExampleProject:
    slug: str
    title: str
    category: str
    description: str
    accent: str = "#ff3b3b"
    tags: List[str] = field(default_factory=list)
    slides: List[SlideContent] = field(default_factory=list)
    disclaimer: str = ""

    @property
    def slide_count(self) -> int:
        return len(self.slides)

    @property
    def est_runtime(self) -> str:
        total_words = sum(len(s.script.split()) for s in self.slides)
        minutes = max(1, round(total_words / 150))
        return f"{minutes} min"

def S(title, body="", layout="hero", kicker="", headline="",
      items=None, script="", tone="engaging") -> SlideContent:
    return SlideContent(title, body, layout, kicker, headline,
                        items or [], script, tone)

_BASE_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  width: 1920px; height: 1080px; overflow: hidden;
  font-family: 'Helvetica Neue', Arial, sans-serif;
  background: radial-gradient(ellipse at 30% 40%, #1a0a0a 0%, #070707 70%);
  color: #f2f2f2; padding: 90px 110px;
  display: flex; flex-direction: column; position: relative;
}
.kicker {
  display: inline-block; align-self: flex-start;
  font-size: 26px; letter-spacing: 7px; text-transform: uppercase;
  color: var(--accent); border: 2px solid var(--accent);
  padding: 10px 26px; border-radius: 4px; margin-bottom: 46px;
}
h1 {
  font-size: 112px; font-weight: 900; line-height: 1.02;
  letter-spacing: -3px; text-transform: uppercase;
}
h1 .accent { color: var(--accent); }
h2 { font-size: 56px; font-weight: 800; line-height: 1.15; }
p { font-size: 38px; line-height: 1.55; color: #b9b9b9; }
.header { display: flex; align-items: center; gap: 34px; margin-bottom: 56px; }
.num {
  font-size: 110px; font-weight: 900; color: var(--accent);
  opacity: .55; line-height: 1;
}
.header h1 { font-size: 82px; }
.footer {
  position: absolute; bottom: 42px; left: 110px; right: 110px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 22px; letter-spacing: 3px; color: #666;
  text-transform: uppercase;
}
.progress { height: 5px; background: #222; border-radius: 3px; overflow: hidden; }
.progress span { display: block; height: 100%; background: var(--accent); }
.fade { animation: fadeUp .8s ease both; }
.d1 { animation-delay: .12s; } .d2 { animation-delay: .26s; }
.d3 { animation-delay: .40s; } .d4 { animation-delay: .54s; }
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(34px); }
  to { opacity: 1; transform: translateY(0); }
}
"""

_LAYOUT_CSS = {
    "hero": """
body { justify-content: center; align-items: flex-start; }
h1 { font-size: 164px; max-width: 1650px; margin-bottom: 46px; }
.subtitle { font-size: 44px; max-width: 1450px; color: #bdbdbd; }
""",
    "split": """
.split { display: grid; grid-template-columns: 1fr 1fr; gap: 56px; flex: 1; }
.panel { padding: 54px; border-radius: 16px; background: #151515;
  border: 1px solid #2c2c2c; }
.panel.accent { background: linear-gradient(160deg, #241010, #120808);
  border-color: var(--accent); }
.panel h2 { margin-bottom: 26px; }
.panel ul { list-style: none; }
.panel li { font-size: 34px; color: #c7c7c7; padding: 15px 0;
  border-bottom: 1px solid #2a2a2a; }
.panel li::before { content: "▸ "; color: var(--accent); font-weight: 900; }
""",
    "compare": """
.compare { display: grid; grid-template-columns: 1fr 120px 1fr;
  align-items: center; gap: 24px; flex: 1; }
.box { padding: 60px 44px; border-radius: 18px; text-align: center;
  background: #151515; border: 2px solid #333; }
.box.a { border-color: var(--accent); background: #1c0d0d; }
.box.b { border-color: #4ec9b0; background: #0d1c19; }
.box .label { font-size: 26px; letter-spacing: 4px; color: #888;
  text-transform: uppercase; margin-bottom: 26px; }
.box h2 { font-size: 62px; margin-bottom: 22px; }
.box p { font-size: 30px; }
.vs { font-size: 88px; font-weight: 900; color: #ffcc00;
  font-style: italic; text-align: center; }
""",
    "spectrum": """
.spectrum { display: flex; flex-direction: column; gap: 30px; flex: 1;
  justify-content: center; }
.bar { height: 150px; border-radius: 14px; padding: 0 46px;
  display: flex; flex-direction: column; justify-content: center; }
.bar strong { font-size: 42px; text-transform: uppercase; letter-spacing: 2px; }
.bar span { font-size: 26px; opacity: .85; margin-top: 8px; }
.bar:nth-child(1) { background: linear-gradient(90deg,#5c1010,#a32626); }
.bar:nth-child(2) { background: linear-gradient(90deg,#8a6500,#d9a400);
  color: #111; transform: scale(1.025);
  box-shadow: 0 0 60px rgba(255,204,0,.25); }
.bar:nth-child(3) { background: linear-gradient(90deg,#0d3a2c,#1a7358); }
.marker { text-align: center; margin-top: 34px; font-size: 30px;
  color: #ffcc00; letter-spacing: 4px; text-transform: uppercase; }
""",
    "grid": """
.grid { display: grid; grid-template-columns: repeat(3,1fr);
  grid-template-rows: repeat(2,1fr); gap: 26px; flex: 1; }
.cell { background: #151515; border: 1px solid #2e2e2e; border-radius: 14px;
  padding: 34px; display: flex; flex-direction: column;
  justify-content: center; }
.cell h3 { font-size: 36px; color: var(--accent); margin-bottom: 14px;
  text-transform: uppercase; }
.cell p { font-size: 26px; line-height: 1.45; }
""",
    "quote": """
body { justify-content: center; }
.quote-mark { font-size: 200px; color: var(--accent); line-height: .6;
  font-family: Georgia, serif; margin-bottom: 20px; }
blockquote { font-size: 100px; font-weight: 800; line-height: 1.15;
  max-width: 1600px; letter-spacing: -2px; }
.attribution { margin-top: 56px; font-size: 32px; color: #888;
  letter-spacing: 3px; text-transform: uppercase; }
""",
    "verdict": """
body { align-items: center; text-align: center; justify-content: center; }
.stamp { font-size: 132px; font-weight: 900; text-transform: uppercase;
  color: var(--accent); border: 10px solid var(--accent);
  padding: 28px 70px; transform: rotate(-4deg);
  letter-spacing: 6px; margin-bottom: 70px; line-height: 1.05; }
.points { display: flex; gap: 34px; width: 100%; text-align: left; }
.point { flex: 1; background: #151515; border-left: 5px solid var(--accent);
  border-radius: 10px; padding: 32px; }
.point h3 { font-size: 28px; color: #ffcc00; text-transform: uppercase;
  letter-spacing: 2px; margin-bottom: 14px; }
.point p { font-size: 25px; }
""",
    "cta": """
body { justify-content: center; align-items: center; text-align: center; }
h1 { font-size: 132px; margin-bottom: 40px; }
.subtitle { font-size: 40px; max-width: 1400px; margin-bottom: 70px; }
.buttons { display: flex; gap: 32px; }
.btn { padding: 28px 56px; border-radius: 12px; font-size: 34px;
  font-weight: 800; text-transform: uppercase; letter-spacing: 3px; }
.btn.red { background: var(--accent); color: #fff; }
.btn.white { background: #f2f2f2; color: #111; }
.btn.gold { background: #ffcc00; color: #111; }
""",
}

def render_slide(s: SlideContent, num: int, total: int,
                 accent: str = "#ff3b3b", brand: str = "Presentation Studio") -> str:
    esc = lambda t: html.escape(str(t))
    kick = esc(s.kicker or f"Chapter {num:02d}")
    title = esc(s.title)
    
    if s.layout == "hero":
        inner = f'''
<div class="kicker fade">{kick}</div>
<h1 class="fade d1">{title}</h1>
<p class="subtitle fade d2">{esc(s.body)}</p>'''
    elif s.layout == "split":
        lis = "".join(f"<li>{esc(i)}</li>" for i in s.items)
        inner = f'''
<div class="header fade"><span class="num">{num:02d}</span>
<h1>{title}</h1></div>
<div class="split">
  <div class="panel accent fade d1">
    <h2>{esc(s.headline or "The Claim")}</h2>
    <p>{esc(s.body)}</p>
  </div>
  <div class="panel fade d2"><h2>The Details</h2><ul>{lis}</ul></div>
</div>'''
    elif s.layout == "compare":
        a = (s.items + ["", ""])[:2]
        parts = [a[0].split(" | "), a[1].split(" | ")]
        inner = f'''
<div class="header fade"><span class="num">{num:02d}</span>
<h1>{title}</h1></div>
<div class="compare">
  <div class="box a fade d1">
    <div class="label">{esc(s.headline or "Position A")}</div>
    <h2>{esc(parts[0][0])}</h2><p>{esc(parts[0][1] if len(parts[0])>1 else "")}</p>
  </div>
  <div class="vs fade d2">VS</div>
  <div class="box b fade d3">
    <div class="label">Position B</div>
    <h2>{esc(parts[1][0])}</h2><p>{esc(parts[1][1] if len(parts[1])>1 else "")}</p>
  </div>
</div>'''
    elif s.layout == "spectrum":
        bars = ""
        for i, item in enumerate(s.items[:3]):
            parts = item.split(" | ")
            bars += (f'<div class="bar fade d{i+1}"><strong>{esc(parts[0])}</strong>'
                     f'<span>{esc(parts[1] if len(parts)>1 else "")}</span></div>')
        inner = f'''
<div class="header fade"><span class="num">{num:02d}</span>
<h1>{title}</h1></div>
<div class="spectrum">{bars}</div>
<div class="marker fade d4">{esc(s.body)}</div>'''
    elif s.layout == "grid":
        cells = ""
        for i, item in enumerate(s.items[:6]):
            parts = item.split(" | ")
            cells += (f'<div class="cell fade d{(i % 3)+1}">'
                      f'<h3>{esc(parts[0])}</h3>'
                      f'<p>{esc(parts[1] if len(parts)>1 else "")}</p></div>')
        inner = f'''
<div class="header fade"><span class="num">{num:02d}</span>
<h1>{title}</h1></div>
<div class="grid">{cells}</div>'''
    elif s.layout == "quote":
        inner = f'''
<div class="quote-mark fade">“</div>
<blockquote class="fade d1">{esc(s.body or s.title)}</blockquote>
<div class="attribution fade d2">{esc(s.headline or "The opening premise")}</div>'''
    elif s.layout == "verdict":
        points = ""
        for i, item in enumerate(s.items[:3]):
            parts = item.split(" | ")
            points += (f'<div class="point fade d{i+2}"><h3>{esc(parts[0])}</h3>'
                       f'<p>{esc(parts[1] if len(parts)>1 else "")}</p></div>')
        inner = f'''
<div class="stamp fade">{title}</div>
<div class="points">{points}</div>'''
    else:
        inner = f'''
<div class="kicker fade">{kick}</div>
<h1 class="fade d1">{title}</h1>
<p class="subtitle fade d2">{esc(s.body)}</p>
<div class="buttons fade d3">
  <div class="btn red">👍 Like</div>
  <div class="btn white">🔔 Subscribe</div>
  <div class="btn gold">💬 Comment</div>
</div>'''
    
    pct = int(num / total * 100)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{esc(s.title)}</title>
<style>
:root {{ --accent: {accent}; }}
{_BASE_CSS}
{_LAYOUT_CSS.get(s.layout, _LAYOUT_CSS['hero'])}
</style>
</head>
<body>
{inner}
<div class="footer">
  <span>{esc(brand)}</span>
  <div class="progress" style="width:420px"><span style="width:{pct}%"></span></div>
  <span>{num:02d} / {total:02d}</span>
</div>
</body>
</html>
"""

def render_thumbnail(p: ExampleProject) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Thumbnail</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:1280px; height:720px; overflow:hidden;
  font-family:'Helvetica Neue',Arial,sans-serif;
  background:radial-gradient(ellipse at 25% 50%, #2a0a0a 0%, #050505 75%);
  color:#fff; padding:60px; display:flex; align-items:center; gap:50px; }}
.left {{ flex:1.4; }}
.badge {{ display:inline-block; background:{p.accent}; padding:8px 20px;
  font-size:20px; font-weight:900; letter-spacing:3px;
  text-transform:uppercase; margin-bottom:24px; border-radius:4px; }}
h1 {{ font-size:104px; font-weight:900; line-height:.96;
  text-transform:uppercase; letter-spacing:-3px; }}
h1 span {{ color:{p.accent}; }}
.stamp {{ flex:.7; border:8px solid {p.accent}; color:{p.accent};
  font-size:76px; font-weight:900; text-align:center;
  padding:26px 10px; transform:rotate(-10deg);
  text-transform:uppercase; letter-spacing:4px; }}
</style></head>
<body>
<div class="left">
  <div class="badge">{html.escape(p.category)}</div>
  <h1>{html.escape(p.title)}</h1>
</div>
<div class="stamp">Watch</div>
</body>
</html>"""

def _hasan() -> ExampleProject:
    return ExampleProject(
        slug="hasan-not-socialist",
        title="Hasan Piker Is Not a Socialist",
        category="video_essay",
        description=("A materialist-style critique arguing that a successful leftist media "
                     "brand can still operate as a capitalist business."),
        accent="#ff3b3b",
        tags=["hasan piker", "socialism", "capitalism", "political commentary",
              "video essay", "leftist critique", "media business"],
        disclaimer=("OPINION / DEBATE EXAMPLE. Claims about any person's finances, ownership, "
                    "lifestyle or policy positions MUST be fact-checked before publishing."),
        slides=[
            S("Hasan Piker Is Not a Socialist",
              "The internet's biggest communist runs a multi-million dollar media company.",
              "hero", "The Controversial Claim",
              script="He tells millions of young people that capitalism is a dystopia.\n"
                     "He built one of the biggest left-wing media brands on earth doing it.\n"
                     "So here's the question his chat hates: is he a socialist — or is "
                     "anti-capitalism the product?"),
            S("The Core Question",
              "A socialist owns the means of production collectively. A capitalist owns "
              "them privately and pays workers a wage.",
              "split", "Definitions First", "What Are We Actually Testing?",
              items=[
                  "Socialism: social or worker ownership",
                  "Capitalism: private ownership + wage labour",
                  "Judge the structure, not the aesthetics",
                  "Judge the policy, not the vocabulary"
              ],
              script="Before we argue about a person, we need a definition.\n"
                     "Not a vibe. Not a t-shirt. Not a slogan.\n"
              "The classic materialist definition turns on one thing: who owns the "
              "means of production, and who receives the surplus?"),
            S("Who Owns the Business?",
              "Apply the same test to a media company that you'd apply to a factory.",
              "compare", "Leftovers Media",
              items=["Hasan | Owner, sets strategy and pay",
                     "Staff | Produce the content, receive a wage"],
              script="Now apply that test to the business.\n"
                     "One person owns the company. Other people do the work and receive "
                     "a salary. The owner decides where the surplus goes."),
            S("The 'Good Boss' Fallacy",
              "Paying well is a virtue. It is not an ownership structure.",
              "compare", "Benevolent ≠ Socialist",
              items=["Henry Ford | $5 a day — a smarter capitalist",
                     "A Good Boss | Fair pay — still a capitalist"],
              script="The reply is always the same: but he pays well! He treats people "
                     "nicely! He funds good causes!\n"
                     "None of that is the question. A benevolent employer is still an "
                     "employer."),
            S("Socialism Is Not Social Democracy",
              "Hasan's platform lives in the middle bar — and that's a real position.",
              "spectrum", "The Policy Spectrum", "Welfare State ≠ Worker Ownership",
              items=["Socialism | Abolish the wage relation",
                     "Social Democracy | Regulate and redistribute",
                     "Liberal Capitalism | Minimal intervention"],
              script="This is where the vocabulary does the heavy lifting.\n"
                     "Universal healthcare. Strong unions. Taxing the rich. Those are "
                     "social-democratic demands inside a market economy."),
            S("The Consumption Problem",
              "The tension isn't having nice things. It's the message the "
              "lifestyle sends.",
              "grid", "The Aesthetic Contradiction", items=[
                  "Housing | Multi-million dollar property",
                  "Cars | Frequently showcased vehicles",
                  "Watches | High-end collections",
                  "Setup | Expensive streaming rig",
                  "Merch | Branded consumer goods",
                  "Affiliates | Commerce integrated into content",
              ],
              script="Here's the cultural criticism, and it's separate from the "
                     "economic one.\n"
                     "A show that attacks consumerism while showcasing luxury "
                     "purchases creates a mixed message."),
            S("The Strongest Defense",
              "He funds the left. He platforms organizers. He reaches people "
              "nobody else reaches. That matters.",
              "split", "Steelman the Counterargument", "Yes — And It's a Real Argument",
              items=["Reach: millions of new political learners",
                      "Funding: mutual aid and strike support",
                      "Platform: organizers get an audience",
                      "But: philanthropy is not worker power"],
              script="Let me make the best case for him, because it's a good one.\n"
                     "Without this business, a lot of that money and reach disappears."),
            S("The Verdict",
              "", "verdict", "Calling Things What They Are", items=[
                  "Structure | Privately owned media business",
                  "Policy | Social-democratic platform",
                  "Culture | Consumerist brand aesthetics",
              ],
              script="So: is he a socialist?\n"
                     "By the ownership test, no. By the policy test, he's much "
                     "closer to a social democrat."),
            S("What Do You Think?",
              "Is this a category error, or is the definition itself too narrow?",
              "cta", "Your Turn",
              script="Now I want the counterargument.\n"
                     "Is the ownership test too rigid for a digital creator "
                     "economy? Is social democracy just a stepping stone?"),
        ],
    )

def _housing() -> ExampleProject:
    return ExampleProject(
        slug="housing-crisis",
        title="The Housing Crisis Isn't an Accident",
        category="explainer",
        description="A five-slide explainer on why housing became unaffordable.",
        accent="#4ec9b0",
        tags=["housing", "economics", "housing crisis", "policy", "explainer"],
        slides=[
            S("The Housing Crisis Isn't an Accident",
              "Decisions made over decades produced this outcome.",
              "hero", "An Explainer",
              script="Housing didn't become unaffordable by accident.\n"
                     "It became unaffordable through thousands of specific "
                     "choices: what we allowed builders to build, what we "
                     "encouraged banks to finance, and what we told ourselves "
                     "about our own neighborhoods."),
            S("Six Forces Behind the Shortage", "", "grid", "The Causes", items=[
                "Land Use | Single-family zoning dominates",
                "Construction Costs | Labor, materials, financing",
                "Financing | Cheap credit bids up land",
                "Speculation | Housing as an asset class",
                "Incomes | Wages lagged productivity",
                "Timing | Building slowed after 2008",
            ],
              script="Six forces, all reinforcing each other.\n"
                     "Restrictive land rules limit supply. Cheap credit increases "
                     "demand for the same limited land."),
            S("Three Ways to Think About Housing",
              "Most arguments fail because people are using different frameworks.",
              "spectrum", "The Frameworks", "Most Debates Are Actually About This",
              items=["A Consumption Good | A place to live",
                     "An Investment Asset | A store of wealth",
                     "Public Infrastructure | A foundation for the economy"],
              script="Ask someone what a house is and you'll get three answers.\n"
                     "A place to live. An investment. A piece of infrastructure."),
            S("The Numbers That Matter",
              "Compare growth in household formation against growth in housing "
              "units over the same period.",
              "split", "How To Check The Claim", "Don't Trust A Screenshot",
              items=["Households formed vs. homes built",
                     "Median income vs. median rent",
                     "Local rules vs. neighboring regions",
                     "Build your own chart from primary data"],
              script="Here's a habit worth building.\n"
                     "Never accept a housing chart without checking the time window "
              "and the geography."),
            S("What Can Actually Change?",
              "Zoning reform. Social housing. Tenant protections. Land value tax.",
              "cta", "The Toolbox",
              script="There is no magic policy.\n"
                     "There is a toolbox: build more in the right places, "
                     "decompress the investment demand, protect tenants, and "
                     "make land speculation less attractive."),
        ],
    )

def _ai_career() -> ExampleProject:
    return ExampleProject(
        slug="ai-career",
        title="AI Won't Replace You. A Person Using AI Might.",
        category="tutorial",
        description="A practical four-slide tutorial separating automatable tasks "
                    "from durable judgment.",
        accent="#75beff",
        tags=["ai", "careers", "future of work", "tutorial", "skills"],
        slides=[
            S("AI Won't Replace You.\nA Person Using AI Might.",
              "The useful unit of analysis is the task, not the job title.",
              "hero", "A Practical Guide",
              script="Ignore the headline that says AI will replace your entire "
                     "profession.\n"
                     "Jobs are bundles of tasks. Some of those tasks automate "
                     "fast. Others barely move."),
            S("Automatable vs. Durable",
              "Repetitive, well-specified, low-consequence work automates first.",
              "compare", "The Task Test",
              items=["Automatable | Drafts, summaries, formatting, lookup",
                     "Durable | Trust, accountability, ambiguity, taste"],
              script="Run this test on your own week.\n"
                     "How much time goes into producing a first draft, reformatting "
                     "information, or looking things up?"),
            S("Five Skills That Compound", "", "grid", "Invest Here", items=[
                "Problem Framing | Define the right question",
                "Evaluation | Know when output is wrong",
                "Domain Depth | Context the model lacks",
                "Communication | Turn output into decisions",
                "Experimentation | Build fast, measure honestly",
                "Accountability | Be the person who owns it",
            ],
              script="These six skills get more valuable as the tools get "
                     "cheaper.\n"
                     "Because when everyone can generate a draft, the scarce "
                     "skill is knowing which draft is good."),
            S("Your 30-Day Plan",
              "Week 1: automate one annoying task. Week 2: build an evaluation. "
              "Week 3: ship something small. Week 4: teach it to a colleague.",
              "cta", "Start This Week",
              script="Don't take a course. Don't read ten hot takes.\n"
                     "Pick one task you dislike. Automate it. Then build a way "
                     "to tell whether the output is actually correct."),
        ],
    )

def _tired() -> ExampleProject:
    return ExampleProject(
        slug="why-tired",
        title="You're Not Lazy. You're Exhausted.",
        category="documentary",
        description="An empathetic four-slide piece distinguishing individual "
                    "rest from structural recovery.",
        accent="#dcdcaa",
        tags=["burnout", "mental health", "work culture", "documentary"],
        slides=[
            S("You're Not Lazy.",
              "You're exhausted. Those are different problems, and they need "
              "different solutions.",
              "quote", "The Premise", "A Note To Anyone Running On Empty",
              script="If you've spent a year trying to fix yourself with a "
                     "better morning routine, hear this.\n"
                     "Exhaustion is not a character flaw."),
            S("Rest Is Not the Problem",
              "You can sleep eight hours and still be depleted.",
              "split", "The Distinction", "Two Different Kinds of Tired",
              items= ["Physical fatigue | Fixed by sleep and recovery",
               "Decision fatigue | Fixed by fewer choices",
               "Moral injury | Fixed by changing the situation",
               "Chronic uncertainty | Fixed by stability"],
              script="There's tired you can sleep off.\n"
                     "And there's tired that survives a full night's sleep because "
                     "the thing draining you is still there on Monday."),
            S("Sleep ≠ Recovery",
              "Recovery requires safety, autonomy, and meaning.",
              "compare", "The Missing Variable",
              items=["Sleep | Hours unconscious",
                     "Recovery | Feeling safe and in control"],
              script="Two people can sleep the same seven hours and wake up "
                     "completely different.\n"
                     "One feels safe. One is bracing."),
            S("Three Experiments",
              "Track your energy for a week. Identify one drain you can remove.",
              "cta", "Start Small",
              script="Try three small things.\n"
                     "Track when you actually feel depleted, not just when "
                     "you feel sleepy."),
        ],
    )

def _demo() -> ExampleProject:
    return ExampleProject(
        slug="quick-demo",
        title="Hello, Presentation Studio",
        category="demo",
        description="A three-slide smoke test. Fastest way to verify rendering, "
                    "TTS, validation, execution and export all work end to end.",
        accent="#4ec9b0",
        tags=["demo", "test", "getting started"],
        slides=[
            S("Hello, Presentation Studio",
              "Three slides. One script. A complete pipeline from prompt to video.",
              "hero", "Quick Demo",
              script="This is your smoke test.\n"
                     "Three slides, three narration scripts, and a full set of "
                     "YouTube metadata. Small enough to render in seconds."),
            S("How This Works",
              "The app generates a prompt. An AI returns a bash script. "
              "You validate it, approve it, and execute it inside the workspace.",
              "split", "The Pipeline", "Prompt → Script → Project",
              items=[
                  "Generate a prompt from a topic",
                  "Paste the AI's bash script into the editor",
                  "Validate syntax, paths, and dangerous commands",
                  "Approve and execute with live console output",
                  "Preview slides, then export to HTML, PDF or PPTX"
              ],
              script="Here's the whole workflow.\n"
              "Generate a prompt. Copy it to your AI. Paste the returned "
              "script back here. Validate it. Approve it. Run it."),
            S("Your Turn",
              "Install this demo, open the first slide, and press play.",
              "cta", "Go Build Something",
              script="Now try it yourself.\n"
                     "Open the first slide in the HTML editor. Change the "
                     "title. Watch the preview update."),
        ],
    )

def all_examples() -> List[ExampleProject]:
    return [_demo(), _hasan(), _housing(), _ai_career(), _tired()]

def format_script(s: SlideContent, num: int) -> str:
    out = [
        "=" * 70,
        f"SLIDE {num:02d} — {s.title.replace(chr(10), ' ').upper()}",
        "=" * 70,
        "",
        f"[Tone: {s.tone}]",
        "",
    ]
    for para in s.script.split("\n"):
        if para.strip():
            out += [para.strip(), "", "[PAUSE]", ""]
    out += ["[END]", "=" * 70]
    return "\n".join(out)

def clean_for_tts(text: str) -> str:
    kept = []
    for line in text.splitlines():
        t = line.strip()
        if not t or t.startswith("="):
            continue
        if t.startswith("[") and t.endswith("]"):
            continue
        t = re.sub(r"\[[^\]]*\]", "", t).strip()
        if t:
            kept.append(t)
    return " ".join(kept)

def build_metadata(p: ExampleProject) -> Dict[str, str]:
    chapters = [f"{i * 90 // 60}:{(i * 90) % 60:02d} — {s.title.replace(chr(10),' ')}"
                for i, s in enumerate(p.slides)]
    description = (
        f"{p.title}\n{p.description}\n"
        "⏱ CHAPTERS\n" + "\n".join(chapters) + "\n"
        "💬 DEBATE IN THE COMMENTS\n"
        "What's the strongest counterargument? I'll reply to the best ones.\n"
        "Subscribe for more deep dives.\n"
        + " ".join("#" + t.replace(" ", "") for t in p.tags[:6])
    )
    if p.disclaimer:
        description += "\n⚠️ EDITORIAL NOTE\n" + p.disclaimer
    return {
        "title_options.txt": "\n".join([
            f"1. {p.title}",
            f"2. {p.title} — Here's Why",
            f"3. The Truth About {p.title.split(' ')[0]}",
        ]),
        "description.txt": description,
        "tags.txt": ", ".join(p.tags + [p.category, "video essay", "explainer"]),
        "chapters.txt": "\n".join(chapters),
        "pinned_comment.txt": (
            f"🔥 REAL QUESTION:\nWhat's the strongest argument AGAINST this "
            f"video's thesis?\nI'll pin the best counterargument. "
            f"Make your case 👇"
        ),
        "community_post.txt": (
            f"🚨 NEW VIDEO DROPPING\n{p.title}\n"
            f"{p.description}\nDrop your prediction in the replies. 🔔"
        ),
    }


def build_readme(p: ExampleProject) -> str:
    # 1. Pre-calculate the optional section to keep the f-string clean
    disclaimer_section = f"## ⚠️ Editorial Note\n{p.disclaimer}" if p.disclaimer else ""
    
    raw_readme = f"""
    # 🎬 {p.title}
    **Category:** {p.category} · **Slides:** {p.slide_count} · **Est. runtime:** {p.est_runtime}

    {p.description}

    ## Structure
    ```text
    slides/      {p.slide_count} self-contained 1920x1080 HTML slides + thumbnail.html
    scripts/     Per-slide narration + full_script.txt + editing_notes.txt
    youtube/     Titles, description, tags, chapters, pinned comment, community post
    install.sh   Self-contained bash installer
    example.json Machine-readable manifest
    ```

    ## Load It
    1. Open the app → **Examples** gallery
    2. Select **{p.slug}**
    3. Click **Install** (direct) or **Run Via Bash** (full workflow)

    {disclaimer_section}
    """
    
    # 2. Dedent removes the indentation, strip() removes leading/trailing newlines
    return textwrap.dedent(raw_readme).strip()

def build_editing_notes(p: ExampleProject) -> str:
    lines = [
        "=" * 70,
        f"EDITOR'S NOTES — {p.title.upper()}",
        "=" * 70,
        "",
        f"Slides: {p.slide_count}   Est. runtime: {p.est_runtime}",
        "Pacing: ~150 spoken words per minute",
        "",
    ]
    for i, s in enumerate(p.slides, 1):
        words = len(clean_for_tts(s.script).split())
        lines += [
            f"{i:02d}. {s.title.replace(chr(10), ' ')}",
            f"    Layout: {s.layout}   Words: {words}   ~{words/150*60:.0f}s",
            f"    Tone: {s.tone}",
            "",
        ]
    return "\n".join(lines)

class ExampleLibrary:
    """Materialize, inspect and install bundled examples."""
    def __init__(self, root: str = "examples"):
        self.root = os.path.abspath(root)

    def list_all(self) -> List[ExampleProject]:
        return all_examples()

    def get(self, slug: str) -> Optional[ExampleProject]:
        return next((p for p in all_examples() if p.slug == slug), None)

    def manifest(self) -> List[Dict]:
        return [{
            "slug": p.slug, "title": p.title, "category": p.category,
            "description": p.description, "slides": p.slide_count,
            "runtime": p.est_runtime, "accent": p.accent, "tags": p.tags,
        } for p in self.list_all()]

    def installed(self) -> List[Dict]:
        found = []
        if not os.path.isdir(self.root): return found
        for name in sorted(os.listdir(self.root)):
            meta = os.path.join(self.root, name, "example.json")
            if os.path.isfile(meta):
                try:
                    with open(meta, "r", encoding="utf-8") as f:
                        found.append(json.load(f))
                except: pass
        return found

    def install(self, slug: str, dest_root: Optional[str] = None) -> str:
        p = self.get(slug)
        if not p: raise ValueError(f"Unknown example: {slug}")
        root = os.path.abspath(dest_root or self.root)
        target = os.path.join(root, p.slug)
        os.makedirs(os.path.join(target, "slides"), exist_ok=True)
        os.makedirs(os.path.join(target, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(target, "youtube"), exist_ok=True)

        def write(path, content):
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

        for i, s in enumerate(p.slides, 1):
            write(os.path.join(target, "slides", f"slide_{i:02d}.html"),
                  render_slide(s, i, p.slide_count, p.accent, p.category.upper()))
            write(os.path.join(target, "scripts", f"script_{i:02d}.txt"),
                  format_script(s, i))
        
        write(os.path.join(target, "slides", "thumbnail.html"), render_thumbnail(p))
        
        full = ["=" * 70, p.title.upper(), f"{p.slide_count} slides", "=" * 70, ""]
        for i, s in enumerate(p.slides, 1):
            full += [f"[SLIDE {i:02d} — {s.title.replace(chr(10),' ').upper()}]",
                     s.script, "", "[PAUSE]", ""]
        write(os.path.join(target, "scripts", "full_script.txt"), "\n".join(full))
        write(os.path.join(target, "scripts", "editing_notes.txt"), build_editing_notes(p))
        
        for name, content in build_metadata(p).items():
            write(os.path.join(target, "youtube", name), content)
            
        write(os.path.join(target, "README.md"), build_readme(p))
        write(os.path.join(target, "install.sh"), self.installer_script(slug))
        
        manifest = {
            "slug": p.slug, "title": p.title, "category": p.category,
            "description": p.description, "slide_count": p.slide_count,
            "accent": p.accent, "tags": p.tags, "disclaimer": p.disclaimer,
            "created_at": datetime.now().isoformat(),
            "slides": [{"number": i, "title": s.title, "layout": s.layout}
                       for i, s in enumerate(p.slides, 1)],
        }
        write(os.path.join(target, "example.json"), json.dumps(manifest, indent=2))
        
        script_path = os.path.join(target, "install.sh")
        try: os.chmod(script_path, 0o755)
        except: pass
        return target

    def install_all(self, dest_root: Optional[str] = None) -> List[str]:
        return [self.install(p.slug, dest_root) for p in self.list_all()]

    def installer_script(self, slug: str) -> str:
        p = self.get(slug)
        if not p: raise ValueError(f"Unknown example: {slug}")
        safe = re.sub(r"[^a-zA-Z0-9]", "", p.slug).upper()
        lines = [
            "#!/usr/bin/env bash",
            f"# Example installer: {p.title}",
            f"# Generated by AI Presentation Studio",
            "set -euo pipefail",
            "",
            f'PROJECT="${{1:-{p.slug}}}"',
            'mkdir -p "$PROJECT/slides" "$PROJECT/scripts" "$PROJECT/youtube"',
            "",
            f'echo "[1/4] Creating {p.slide_count} slides..."',
        ]
        def heredoc(path: str, content: str, tag_base: str) -> List[str]:
            tag = f"AI_EX_{safe}_{tag_base}"
            while tag in content.splitlines():
                tag += "X"
            return [f"cat <<'{tag}' > \"{path}\"",
                    content.rstrip("\n"), tag, ""]
        
        for i, s in enumerate(p.slides, 1):
            lines += heredoc(
                f"$PROJECT/slides/slide_{i:02d}.html",
                render_slide(s, i, p.slide_count, p.accent, p.category.upper()),
                f"SLIDE{i:02d}")
        
        lines += [f'echo "[2/4] Creating narration scripts..."']
        for i, s in enumerate(p.slides, 1):
            lines += heredoc(f"$PROJECT/scripts/script_{i:02d}.txt",
                             format_script(s, i), f"SCRIPT{i:02d}")
        
        full = ["=" * 70, p.title.upper(), "=" * 70, ""]
        for i, s in enumerate(p.slides, 1):
            full += [s.script, "", "[PAUSE]", ""]
        lines += heredoc("$PROJECT/scripts/full_script.txt",
                         "\n".join(full), "FULL")
        lines += heredoc("$PROJECT/scripts/editing_notes.txt",
                         build_editing_notes(p), "NOTES")
        
        lines += [f'echo "[3/4] Creating YouTube metadata..."']
        for name, content in build_metadata(p).items():
            key = re.sub(r"[^A-Z]", "", name.upper())
            lines += heredoc(f"$PROJECT/youtube/{name}", content, key)
        
        lines += [f'echo "[4/4] Writing manifest and README..."']
        manifest = {
            "slug": p.slug, "title": p.title, "category": p.category,
            "slide_count": p.slide_count, "accent": p.accent,
        }
        lines += heredoc("$PROJECT/example.json",
                         json.dumps(manifest, indent=2), "MANIFEST")
        lines += heredoc("$PROJECT/README.md", build_readme(p), "README")
        
        lines += [f'echo "✅ Project complete: {p.slug}"']
        return "\n".join(lines) + "\n"

    def verify(self, slug: str, path: str) -> Dict:
        p = self.get(slug)
        checks = []
        def check(name, ok, detail=""):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})
        
        check("slides directory", os.path.isdir(os.path.join(path, "slides")))
        check("scripts directory", os.path.isdir(os.path.join(path, "scripts")))
        check("youtube directory", os.path.isdir(os.path.join(path, "youtube")))
        
        for i in range(1, p.slide_count + 1):
            check(f"slide_{i:02d}.html",
                  os.path.isfile(os.path.join(path, "slides", f"slide_{i:02d}.html")))
            check(f"script_{i:02d}.txt",
                  os.path.isfile(os.path.join(path, "scripts", f"script_{i:02d}.txt")))
        
        html_path = os.path.join(path, "slides", "slide_01.html")
        if os.path.isfile(html_path):
            with open(html_path, encoding="utf-8") as f:
                content = f.read()
            check("slide has 1920x1080 viewport", "1920px" in content and "1080px" in content)
            check("slide is self-contained", "<style>" in content and "<!DOCTYPE" in content)
        
        script_path = os.path.join(path, "scripts", "script_01.txt")
        if os.path.isfile(script_path):
            with open(script_path, encoding="utf-8") as f:
                check("script has narration", len(clean_for_tts(f.read()).split()) > 10)
        
        return {
            "slug": slug,
            "passed": all(c["ok"] for c in checks),
            "total": len(checks),
            "checks": checks,
        }

def self_test() -> int:
    import tempfile
    lib = ExampleLibrary()
    failures = 0
    with tempfile.TemporaryDirectory(prefix="ai_studio_examples_") as tmp:
        for p in lib.list_all():
            path = lib.install(p.slug, tmp)
            result = lib.verify(p.slug, path)
            status = "✅" if result["passed"] else "❌"
            print(f"{status} {p.slug:26s} {p.slide_count} slides  "
                  f"{result['total']} checks")
            if not result["passed"]:
                failures += 1
                for c in result["checks"]:
                    if not c["ok"]:
                        print(f"     ✗ {c['name']}")
            
            bash = shutil.which("bash")
            if bash:
                script = lib.installer_script(p.slug)
                proc = subprocess.run([bash, "-n"], input=script,
                                      capture_output=True, text=True)
                if proc.returncode != 0:
                    print(f"     ✗ Installer syntax: {proc.stderr}")
                    failures += 1
                else:
                    rebuilt = os.path.join(tmp, "rebuilt", p.slug)
                    os.makedirs(rebuilt, exist_ok=True)
                    run = subprocess.run([bash, "-c", script, "bash", rebuilt],
                                         capture_output=True, text=True, timeout=30)
                    if run.returncode != 0:
                        print(f"     ✗ Installer execution: {run.stderr}")
                        failures += 1
                    else:
                        print(f"     ✓ Installer executed successfully")
    print()
    
    print("FAILURES:", failures)
    return 1 if failures else 0

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description="Bundled example presentation library")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--install", metavar="SLUG|all")
    ap.add_argument("--installer", metavar="SLUG")
    ap.add_argument("--dest", default="examples")
    ap.add_argument("--verify", metavar="SLUG")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    
    lib = ExampleLibrary(args.dest)
    
    if args.self_test:
        sys.exit(self_test())
    
    if args.list or not any([args.install, args.installer, args.verify]):
        print(f"{'SLUG':26} {'CATEGORY':14} {'SLIDES':7} {'RUNTIME':9} TITLE")
        print("-" * 100)
        for p in lib.list_all():
            print(f"{p.slug:26} {p.category:14} {p.slide_count:<7} "
                  f"{p.est_runtime:9} {p.title.replace(chr(10),' ')}")
        return
    
    if args.install:
        paths = (lib.install_all(args.dest) if args.install == "all"
                 else [lib.install(args.install, args.dest)])
        for path in paths:
            print(f"✅ Installed → {path}")
        return
    
    if args.installer:
        sys.stdout.write(lib.installer_script(args.installer))
        return
    
    if args.verify:
        path = os.path.join(args.dest, args.verify)
        result = lib.verify(args.verify, path)
        for c in result["checks"]:
            print(f"{'✅' if c['ok'] else '❌'} {c['name']}")
        print(f"\n{'PASS' if result['passed'] else 'FAIL'}: "
              f"{result['total']} checks")
        sys.exit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()
