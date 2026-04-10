import tkinter as tk
from tkinter import PhotoImage
import random
import os
import json

# -----------------------------
#   GAME LOGIC
# -----------------------------

class AuroraGame:
    def __init__(self):
        # Core stats
        self.stats = {"Stability": 70, "Equality": 70, "Prosperity": 70, "Freedom": 70}
        self.year = 1
        self.max_years = 15
        # Advisors & reputation
        self.advisors = {
            "economy": {
                "name": "Ada",
                "trust": 50,
                "portrait": os.path.join(os.path.dirname(__file__), 'assets', 'images', 'advisor_economy.png'),
                "bio": "Chief Economist — pragmatic, pro-growth, favors industry and trade.",
                "personality": {
                    "agree": [
                        "I back {choice} — it's a sound economic move for {stat}.",
                        "{choice} makes sense financially; it should boost {stat}.",
                        "From a market view, {choice} is sensible — expect gains in {stat}.",
                        "I'd endorse {choice}; it'll shore up investment and confidence.",
                        "This move should stimulate growth and help {stat}.",
                        "On paper, {choice} looks like a solid economic step."
                    ],
                    "disagree": [
                        "I'm worried {choice} will dent our {stat}.",
                        "{choice} seems risky economically; it could harm {stat} by {score}.",
                        "I can't support {choice}; it undermines economic stability.",
                        "This could increase volatility and hurt long-term {stat}.",
                        "I fear {choice} benefits a few at the expense of broader {stat}.",
                        "It's fiscally imprudent; I advise caution."
                    ],
                    "follow_agree": [
                        "Specifically, it improves investment and jobs.",
                        "It should increase production and tax revenues.",
                        "You'll see improvements in trade and output.",
                        "Expect higher capital inflows and employment.",
                        "It will likely raise productivity in affected sectors."
                    ],
                    "follow_disagree": [
                        "My concern is longer-term inequality and debt.",
                        "This could create bubbles or favor insiders.",
                        "It risks crowding out important social spending.",
                        "I worry it consolidates wealth rather than broadening prosperity.",
                        "This may saddle future budgets with unsustainable obligations."
                    ]
                }
            },
            "rights": {
                "name": "Leo",
                "trust": 50,
                "portrait": os.path.join(os.path.dirname(__file__), 'assets', 'images', 'advisor_rights.png'),
                "bio": "Civil Rights Advisor — principled defender of liberties and social justice.",
                "personality": {
                    "agree": [
                        "I support {choice}; it defends our citizens' rights.",
                        "{choice} upholds equality — that's essential.",
                        "This aligns with our values; I'm in favour of {choice}.",
                        "This is the kind of policy that protects our core freedoms.",
                        "It's a moral imperative to adopt {choice}."
                    ],
                    "disagree": [
                        "I oppose {choice}; it threatens liberties.",
                        "{choice} would roll back protections we fought for.",
                        "I can't back {choice} — it harms civil rights.",
                        "This policy could silence vulnerable voices.",
                        "It risks institutional discrimination if implemented."
                    ],
                    "follow_agree": [
                        "It will empower marginalized communities.",
                        "It reduces discrimination and strengthens fairness.",
                        "This helps ensure equal access for everyone.",
                        "It increases protections where they're most needed.",
                        "This fosters social cohesion and trust."
                    ],
                    "follow_disagree": [
                        "My worry is surveillance or reduced freedoms.",
                        "It may disproportionately hurt vulnerable groups.",
                        "It risks institutionalizing bias.",
                        "This could lead to unequal enforcement.",
                        "It may curtail legitimate dissent and speech."
                    ]
                }
            },
            "security": {
                "name": "Kai",
                "trust": 50,
                "portrait": os.path.join(os.path.dirname(__file__), 'assets', 'images', 'advisor_security.png'),
                "bio": "Security Chief — calm under pressure, prioritizes order and public safety.",
                "personality": {
                    "agree": [
                        "I agree with {choice}; it strengthens stability.",
                        "{choice} helps keep people safe — I'm for it.",
                        "This reduces immediate risk; I support {choice}.",
                        "This is a pragmatic move to prevent escalation.",
                        "It should lower threats and reassure the public."
                    ],
                    "disagree": [
                        "I'm uneasy about {choice}; it may weaken our defenses.",
                        "{choice} could expose us to disorder.",
                        "I don't back {choice}; it raises security risks.",
                        "This could create operational blind spots.",
                        "It might inflame tensions rather than calm them."
                    ],
                    "follow_agree": [
                        "It tightens patrols and improves response times.",
                        "We'll reduce incidents and reassure citizens.",
                        "This helps prevent escalation.",
                        "It improves coordination among responders.",
                        "It gives us tools to intervene early."
                    ],
                    "follow_disagree": [
                        "It might erode trust between citizens and authorities.",
                        "Overreach could provoke backlash.",
                        "It may be costly and inefficient.",
                        "This could undermine legitimacy and compliance.",
                        "It risks diverting resources from prevention to enforcement."
                    ]
                }
            }
        }
        # mark all as active initially
        for k in list(self.advisors.keys()):
            self.advisors[k]["active"] = True
            self.advisors[k]["left_reason"] = ""
        self.conflict = {key: 0 for key in self.advisors}
        self.event_history = []
        # persisted set of seen event signatures to avoid repeats across save/load
        self.seen_event_sigs = set()
        # advisor preference mapping for reuse
        # Note: Rights advisor prefers Freedom (so 'Ignore the protests' benefits them).
        self.advisor_prefs = {"economy": "Prosperity", "rights": "Freedom", "security": "Stability"}
        # build a pool of up to 50 possible events
        self.event_pool = []
        self.build_event_pool()
        # If scripted debate files exist, replace the default year prompts
        # with events that reference those scripts. This allows explicit
        # per-prompt debate control via assets/debates/*.json files.
        try:
            self._override_events_from_debates()
        except Exception:
            pass
        # advisor personality templates are used as authored in advisor data
        # Map regions
        self.regional_stats = {"North": {"Prosperity": 70}, "South": {"Prosperity": 70},
                               "East": {"Prosperity": 70}, "West": {"Prosperity": 70}}

    def apply_effects(self, effects):
        for stat, change in effects.items():
            if stat in self.stats:
                self.stats[stat] = max(0, min(100, self.stats[stat] + change))
        self.update_conflict(effects)
        self.update_reputation(effects)

    def collapsed(self):
        return any(v <= 0 for v in self.stats.values())

    # -----------------------------
    # Conflict / reputation system
    # -----------------------------
    def update_conflict(self, effects):
        if effects.get("Prosperity", 0) < 0:
            self.conflict["economy"] += 5
        if effects.get("Equality", 0) < 0 or effects.get("Freedom", 0) < 0:
            self.conflict["rights"] += 5
        if effects.get("Stability", 0) < 0:
            self.conflict["security"] += 5
        for key in self.conflict:
            self.conflict[key] = min(100, self.conflict[key])

    def update_reputation(self, effects):
        # Positive stat change increases trust
        for advisor, stat_map in zip(self.advisors, ["Prosperity","Equality","Stability"]):
            change = effects.get(stat_map, 0)
            self.advisors[advisor]["trust"] += change // 2
            self.advisors[advisor]["trust"] = min(100, max(0, self.advisors[advisor]["trust"]))

    def check_advisor_rebellion(self):
        return [adv for adv, val in self.conflict.items() if val >= 60]

    def get_advisor_recommendations(self, event):
        # Advisors prefer different stats; recommend the choice that helps their preferred stat most
        pref = self.advisor_prefs
        recommendations = {}
        for adv_key, info in self.advisors.items():
            if not info.get("active", True):
                continue
            stat = pref.get(adv_key, None)
            best_choice = None
            best_score = -999
            for choice_key, (desc, effects) in event["choices"].items():
                score = 0
                if stat:
                    score = effects.get(stat, 0)
                # small bonus for positive overall effect
                score += sum(v for v in effects.values()) * 0.01
                # if the event text explicitly mentions the advisor's preferred stat,
                # give a small contextual boost so the advisor is more likely to
                # recommend options tied to that stat (helps debate pairing be sensible)
                try:
                    text_blob = (event.get('title','') + ' ' + event.get('description','')).lower()
                    if stat and stat.lower() in text_blob:
                        score += 2
                except Exception:
                    pass
                if score > best_score:
                    best_score = score
                    best_choice = choice_key
            # Natural-language comment based on their preferred stat and the choice
            if stat:
                if best_score > 0:
                    comment = f"I favour {best_choice} — it helps our {stat.lower()} ({best_score:+.0f})."
                elif best_score == 0:
                    comment = f"{best_choice} is neutral for {stat.lower()}, but it's acceptable."
                else:
                    comment = f"I'm wary of {best_choice}; it could harm {stat.lower()} ({best_score:+.0f})."
            else:
                comment = f"I recommend {best_choice}."
            recommendations[adv_key] = {"choice": best_choice, "reason": comment, "score": best_score}
        return recommendations

    def get_personalized_line(self, adv_key, agreed, rec):
        """Return a varied, personality-driven line for an advisor."""
        info = self.advisors.get(adv_key, {})
        pers = info.get('personality', {})
        stat = self.advisor_prefs.get(adv_key, None)
        tpl_list = pers.get('agree' if agreed else 'disagree', [])
        if not tpl_list:
            # fallback
            return f"{info.get('name','Advisor')}: {'agrees' if agreed else 'disagrees'} with {rec.get('choice')} — {rec.get('reason')}"
        tpl = random.choice(tpl_list)
        try:
            return tpl.format(choice=rec.get('choice'), stat=(stat or '').lower(), score=int(rec.get('score',0)), reason=rec.get('reason'))
        except Exception:
            return tpl

    def get_personalized_followup(self, adv_key, agreed, rec):
        info = self.advisors.get(adv_key, {})
        pers = info.get('personality', {})
        key = 'follow_agree' if agreed else 'follow_disagree'
        tpl_list = pers.get(key, [])
        if not tpl_list:
            return rec.get('reason')
        tpl = random.choice(tpl_list)
        try:
            return tpl.format(choice=rec.get('choice'), stat=self.advisor_prefs.get(adv_key, '').lower(), score=int(rec.get('score',0)), reason=rec.get('reason'))
        except Exception:
            return tpl

    def build_event_pool(self):
        # Create a diverse pool of events (up to 50) using stat-focused templates and variety
        templates = {
            "Stability": [
                ("Civil unrest is growing in the streets.", {"A": ("Increase police presence.", {"Stability": +5, "Freedom": -4}),
                                                                        "B": ("Organize town halls.", {"Stability": +2, "Freedom": +2, "Equality": +1}),
                                                                        "C": ("Ignore the protests.", {"Stability": -5, "Freedom": +3})}),
                ("A surge of strikes threatens order.", {"A": ("Negotiate with unions.", {"Stability": +3, "Prosperity": -1}),
                                                         "B": ("Force workers back.", {"Stability": +4, "Freedom": -3}),
                                                         "C": ("Let it pass.", {"Stability": -2, "Freedom": +2})}),
                ("Border skirmishes worry regional leaders.", {"A": ("Deploy peacekeepers.", {"Stability": +3, "Prosperity": -1}), "B": ("Call for talks.", {"Stability": +1}), "C": ("Escalate defenses.", {"Stability": +4, "Freedom": -2})}),
            ],
            "Prosperity": [
                ("Markets are sluggish and unemployment rises.", {"A": ("Invest in infrastructure.", {"Prosperity": +5, "Equality": -2}),
                                                                     "B": ("Cut business taxes.", {"Prosperity": +3, "Stability": -2, "Freedom": +1}),
                                                                     "C": ("No intervention.", {"Prosperity": -3, "Freedom": +1})}),
                ("A major export partner imposes tariffs.", {"A": ("Subsidize exporters.", {"Prosperity": +4}),
                                                            "B": ("Find new markets.", {"Prosperity": +2}),
                                                            "C": ("Accept losses.", {"Prosperity": -3, "Freedom": +1})}),
                ("Inflation spikes, eroding purchasing power.", {"A": ("Tighten monetary policy.", {"Prosperity": -1, "Stability": +2}), "B": ("Subsidize staples.", {"Equality": +1, "Prosperity": -2}), "C": ("Do nothing.", {"Prosperity": -3})}),
            ],
            "Equality": [
                ("Reports surface of discrimination in hiring.", {"A": ("Enforce anti-discrimination.", {"Equality": +5, "Stability": -2}),
                                                                    "B": ("Offer training programs.", {"Equality": +2, "Prosperity": -1}),
                                                                    "C": ("No action.", {"Equality": -4, "Freedom": +2})}),
                ("Subsidies favor the wealthy, widening gaps.", {"A": ("Redistribute taxes.", {"Equality": +4, "Prosperity": -2}),
                                                                       "B": ("Stimulate growth.", {"Prosperity": +3}),
                                                                       "C": ("Keep policy.", {"Equality": -2, "Freedom": +1})}),
                ("Rural schools face chronic underfunding.", {"A": ("Redirect funds to rural areas.", {"Equality": +3, "Prosperity": -1}), "B": ("Encourage private partnerships.", {"Prosperity": +1}), "C": ("Maintain budgets.", {"Equality": -1})}),
            ],
            "Freedom": [
                ("A spy scandal raises surveillance calls.", {"A": ("Increase oversight.", {"Freedom": -3, "Stability": +2}),
                                                               "B": ("Strengthen privacy laws.", {"Freedom": +4}),
                                                               "C": ("Do nothing.", {"Freedom": -1, "Stability": 0})}),
                ("A public health emergency tempts restrictions.", {"A": ("Impose strict controls.", {"Freedom": -4, "Stability": +3}),
                                                                         "B": ("Targeted measures.", {"Freedom": -1, "Stability": +1}),
                                                                         "C": ("Avoid restrictions.", {"Freedom": +2})}),
                ("Rumors of censorship after a controversial ban.", {"A": ("Clarify regulations.", {"Freedom": 0, "Stability": +1}), "B": ("Reverse the ban.", {"Freedom": +2}), "C": ("Double-down.", {"Stability": +2, "Freedom": -2})}),
            ]
        }

        # flatten templates and add many phrasing variations to reach ~50 events
        pool = []
        variation_prefixes = ["", "Urgent:", "Update:", "Breaking:", "New:", "Developing:"]
        suffixes = ["", " — public concerned", " — experts weigh in", " — overnight reports", " — experts divided"]
        for stat, items in templates.items():
            for title, choices in items:
                for pref in variation_prefixes:
                    for suf in suffixes[:3]:
                        desc = " ".join(p for p in (pref, title + (suf if suf else "")) if p).strip()
                        pool.append({"title": f"{stat} Issue", "description": desc, "choices": choices})

        # Add more unique topical events to diversify the pool
        topical = [
            ("A diplomatic rift with a neighbor.", {"A": ("Seek compromise.", {"Stability": +2}), "B": ("Retaliate.", {"Stability": -1}), "C": ("Stay neutral.", {"Stability": 0})}),
            ("A technology boom shifts jobs.", {"A": ("Support retraining.", {"Prosperity": +2, "Equality": +1}), "B": ("Let market decide.", {"Prosperity": +1}), "C": ("Restrict tech.", {"Prosperity": -1})}),
            ("An environmental disaster affects agriculture.", {"A": ("Fund relief.", {"Prosperity": -1, "Equality": +1}), "B": ("Ignore.", {"Prosperity": -3}), "C": ("International aid.", {"Prosperity": +1})}),
            ("A viral social trend damages public trust.", {"A": ("Counter-campaign.", {"Stability": +1}), "B": ("Let it fade.", {"Stability": -1}), "C": ("Regulate platforms.", {"Freedom": -1})}),
            ("A foreign investor offers a large deal.", {"A": ("Accept investment.", {"Prosperity": +3}), "B": ("Renegotiate terms.", {"Prosperity": +1, "Equality": +1}), "C": ("Decline.", {"Prosperity": -1})}),
            ("New medical research promises a cure.", {"A": ("Fast-track approval.", {"Freedom": -1, "Stability": +1}), "B": ("Wait for trials.", {"Stability": 0}), "C": ("Public funding.", {"Prosperity": -1, "Equality": +1})}),
        ]
        for title, choices in topical:
            for pref in ["", "Update:"]:
                for suf in ["", " — urgent"]:
                    pool.append({"title": "Event", "description": f"{pref} {title}{suf}".strip(), "choices": choices})

        # Additional unique events (15 more) to ensure variety across years
        extra = [
            ("A regional drought threatens crops.", {"A": ("Ration water.", {"Prosperity": -1, "Equality": +1}), "B": ("Import supplies.", {"Prosperity": 0}), "C": ("Invest in irrigation.", {"Prosperity": +2, "Stability": +1})}),
            ("A controversial mining contract surfaces.", {"A": ("Renegotiate terms.", {"Prosperity": +1, "Equality": +1}), "B": ("Approve quickly.", {"Prosperity": +3}), "C": ("Halt until review.", {"Prosperity": -1, "Stability": +1})}),
            ("A popular entertainer endorses a policy.", {"A": ("Leverage their platform.", {"Stability": +1}), "B": ("Ignore celebrity.", {"Freedom": +1}), "C": ("Fact-check claims.", {"Stability": 0})}),
            ("Small businesses report rising costs.", {"A": ("Subsidize costs.", {"Prosperity": +2}), "B": ("Cut red tape.", {"Prosperity": +1}), "C": ("Let market adjust.", {"Prosperity": -1})}),
            ("A city requests special autonomy.", {"A": ("Grant autonomy.", {"Freedom": +2, "Stability": -1}), "B": ("Deny request.", {"Stability": +1}), "C": ("Negotiate compromise.", {"Freedom": +1, "Stability": 0})}),
            ("An education scandal weakens trust in schools.", {"A": ("Overhaul curriculum.", {"Equality": +2}), "B": ("Increase oversight.", {"Stability": +1}), "C": ("Do nothing.", {"Equality": -1})}),
            ("A cyberattack exposes personal data.", {"A": ("Tighten cybersecurity.", {"Stability": +2, "Freedom": -1}), "B": ("Public apology.", {"Freedom": 0}), "C": ("Private remediation.", {"Prosperity": -1})}),
            ("A breakthrough in clean energy emerges.", {"A": ("Invest heavily.", {"Prosperity": +2, "Equality": +1}), "B": ("Let private sector lead.", {"Prosperity": +1}), "C": ("Regulate cautiously.", {"Stability": 0})}),
            ("A scandal implicates a foreign contractor.", {"A": ("Cancel contracts.", {"Prosperity": -1}), "B": ("Investigate quietly.", {"Stability": +1}), "C": ("Renegotiate terms.", {"Prosperity": +1})}),
            ("A health campaign lowers vaccination rates.", {"A": ("Mandate programs.", {"Freedom": -2, "Stability": +1}), "B": ("Public education.", {"Freedom": +1}), "C": ("Incentivize uptake.", {"Prosperity": 0})}),
            ("A rising tide floods low-lying neighborhoods.", {"A": ("Relocate families.", {"Equality": +1, "Prosperity": -1}), "B": ("Build defenses.", {"Prosperity": +1}), "C": ("Offer temporary aid.", {"Prosperity": 0})}),
            ("A labor union demands faster wage increases.", {"A": ("Negotiate terms.", {"Equality": +2, "Prosperity": -1}), "B": ("Crack down.", {"Stability": +1, "Freedom": -2}), "C": ("No action.", {"Prosperity": -1})}),
            ("New AI regulation proposals surface.", {"A": ("Adopt strict rules.", {"Freedom": -1, "Stability": +1}), "B": ("Encourage innovation.", {"Prosperity": +2}), "C": ("Delay decision.", {"Stability": 0})}),
            ("A major cultural festival has safety concerns.", {"A": ("Cancel event.", {"Freedom": -1, "Stability": +1}), "B": ("Improve safety.", {"Prosperity": +1}), "C": ("Proceed as planned.", {"Freedom": +1})}),
            ("A scandal over resource allocation emerges.", {"A": ("Redistribute funds.", {"Equality": +2}), "B": ("Audit agencies.", {"Stability": +1}), "C": ("Maintain course.", {"Prosperity": 0})}),
        ]
        for title, choices in extra:
            pool.append({"title": "Event", "description": title, "choices": choices})

        # Ensure we have at least 50 items; if more, trim to 50 for predictable behavior
        if len(pool) < 50:
            # duplicate with small rewordings until reach 50
            i = 0
            while len(pool) < 50:
                e = pool[i % len(pool)].copy()
                e = {"title": e["title"], "description": e["description"] + f" (variant {i})", "choices": e["choices"]}
                pool.append(e)
                i += 1

        # shuffle so different stats and topical/extra items are mixed
        try:
            random.shuffle(pool)
        except Exception:
            pass
        self.event_pool = pool[:50]

    def generate_dynamic_event(self):
        # If scripted debates are enabled via assets/debates, prefer returning
        # events only from the scripted `event_pool`. This prevents any
        # dynamically-generated events from being used when the designer
        # provided explicit debate JSON files.
        if getattr(self, 'only_debates', False):
            try:
                if isinstance(self.event_pool, list) and self.event_pool:
                    return random.choice(self.event_pool)
            except Exception:
                return None

        # Prefer events that match low stat but fall back to random from pool for variety
        low_stat = min(self.stats, key=self.stats.get)

        def _normalize_sig(e):
            # create a normalized signature that ignores common metadata and variants
            s = (e.get('title','') + ' ' + e.get('description','')).lower()
            import re
            # remove common metadata tokens anywhere
            s = re.sub(r"\b(update|breaking|urgent|new|developing)\b:?", "", s)
            # remove generic labels like 'stability issue' or 'event'
            s = re.sub(r"\b(stability issue|event|issue)\b", "", s)
            # remove common suffix fragments
            for suf in [" — public concerned", " — experts weigh in", " — overnight reports", " — experts divided", " — urgent"]:
                if suf in s:
                    s = s.replace(suf, '')
            # remove variant tags like '(variant 3)'
            s = re.sub(r"\(variant \d+\)", "", s)
            # strip punctuation and collapse whitespace
            s = re.sub(r"[\-—:(),]", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s

        unseen_pool = []
        try:
            for e in self.event_pool:
                sig = _normalize_sig(e)
                if sig and sig not in getattr(self, 'seen_event_sigs', set()):
                    unseen_pool.append((e, sig))
        except Exception:
            unseen_pool = []

        # prefer unseen events that match the low stat
        if unseen_pool:
            matches = [pair for pair in unseen_pool if low_stat.lower() in (pair[0].get('title','') + ' ' + pair[0].get('description','')).lower()]
            if matches:
                choice, sig = random.choice(matches)
                self.seen_event_sigs.add(sig)
                return choice
            choice, sig = random.choice(unseen_pool)
            self.seen_event_sigs.add(sig)
            return choice

        # otherwise fall back to picking events that mention the low stat,
        # preferring ones whose normalized signature hasn't been seen yet
        candidates = [e for e in self.event_pool if low_stat.lower() in (e.get('title','') + ' ' + e.get('description','')).lower()]
        # filter out already-seen normalized signatures
        fresh_candidates = [e for e in candidates if _normalize_sig(e) not in getattr(self, 'seen_event_sigs', set())]
        if fresh_candidates:
            chosen = random.choice(fresh_candidates)
            try:
                self.seen_event_sigs.add(_normalize_sig(chosen))
            except Exception:
                pass
            return chosen
        # if none fresh, try any unseen event from the whole pool
        all_fresh = [e for e in self.event_pool if _normalize_sig(e) not in getattr(self, 'seen_event_sigs', set())]
        if all_fresh:
            chosen = random.choice(all_fresh)
            try:
                self.seen_event_sigs.add(_normalize_sig(chosen))
            except Exception:
                pass
            return chosen
        # as a last resort, return any random event (pool exhausted)
        chosen = random.choice(self.event_pool)
        try:
            self.seen_event_sigs.add(_normalize_sig(chosen))
        except Exception:
            pass
        return chosen

    def adjust_trust_after_choice(self, chosen_key, recommendations, event_choices=None):
        # Update trust based on whether advisors agreed with chosen option.
        # Use the actual effects of the chosen option (from event_choices) so
        # predicted deltas shown in the UI match the real trust changes.
        results = {}
        left = []
        leave_threshold = 15
        # fallback if no event_choices provided
        event_choices = event_choices or {}
        for adv_key, rec in recommendations.items():
            # skip inactive advisors
            if not self.advisors.get(adv_key, {}).get("active", True):
                continue
            # compute advisor-specific score for the chosen option
            effects = {}
            try:
                effects = event_choices.get(chosen_key, (None, {}))[1]
            except Exception:
                effects = {}
            pref = self.advisor_prefs.get(adv_key)
            score_for_choice = 0
            if pref and effects:
                score_for_choice = effects.get(pref, 0)
            # small bonus for overall positive impact (same heuristic used elsewhere)
            try:
                score_for_choice += sum(v for v in effects.values()) * 0.01
            except Exception:
                pass

            # Recalibrated deltas: make agreement more rewarding and disagreement
            # somewhat harsher so advisors' trust moves feel more consequential.
            # Base: +4 for agreeing recommendation, -3 for disagreeing.
            if rec.get("choice") == chosen_key:
                delta = 4
            else:
                delta = -3
            # Additional penalty if the chosen action harms their preferred stat
            if score_for_choice < 0:
                delta += -3

            self.advisors[adv_key]["trust"] = max(0, min(100, self.advisors[adv_key]["trust"] + delta))
            results[adv_key] = (delta >= 0)
            # if trust falls very low, advisor may leave
            if self.advisors[adv_key]["trust"] <= leave_threshold and self.advisors[adv_key].get("active", True):
                self.advisors[adv_key]["active"] = False
                reason = f"Resigned after trust fell to {self.advisors[adv_key]['trust']}"
                self.advisors[adv_key]["left_reason"] = reason
                left.append(adv_key)
        return results, left

    # Personality templates are used directly from advisor definitions.
    # Automatic expansion was removed so authored JSON/personality entries
    # remain the single source of personality lines.

    def _override_events_from_debates(self):
        """If assets/debates/*.json files exist, construct simple events
        that reference them and replace the event_pool. Each debate file
        becomes an event with a `script_key` matching the filename (without
        extension) so the UI loader uses the scripted turns we created.
        """
        try:
            base = os.path.join(os.path.dirname(__file__), 'assets', 'debates')
        except Exception:
            base = os.path.join('assets', 'debates')
        if not os.path.isdir(base):
            return
        try:
            files = [f for f in os.listdir(base) if f.lower().endswith('.json')]
        except Exception:
            return

        events = []
        for fn in files:
            # skip a mapping file named debates.json (it may contain many keys)
            if fn.lower() == 'debates.json':
                continue
            path = os.path.join(base, fn)
            key = os.path.splitext(fn)[0]
            # attempt to read and parse the debate JSON; skip any file that fails
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
            except Exception:
                # skip unreadable or malformed debate files so we don't leave
                # dangling events that reference missing content
                continue

            # pull a short description from the first turn if available
            desc = ''
            try:
                if isinstance(raw, dict) and 'turns' in raw and isinstance(raw['turns'], list) and raw['turns']:
                    first = raw['turns'][0]
                    desc = first.get('text', '')[:200]
                elif isinstance(raw, list) and raw:
                    first = raw[0]
                    desc = first.get('text', '')[:200]
            except Exception:
                desc = ''

            title = (raw.get('title') if isinstance(raw, dict) and raw.get('title') else key.replace('_', ' ').title())

            # If the debate JSON provides explicit `choices`, copy them into the event;
            # otherwise create safe placeholder choices. We already ensured `raw` parsed above.
            choices_field = None
            try:
                if isinstance(raw, dict) and 'choices' in raw and isinstance(raw['choices'], dict):
                    choices_field = {}
                    for ck, cv in raw['choices'].items():
                        if isinstance(cv, dict):
                            title_txt = cv.get('title') or cv.get('text') or str(cv)
                            effects = cv.get('effects') if isinstance(cv.get('effects'), dict) else {}
                            choices_field[ck] = (title_txt, effects)
            except Exception:
                choices_field = None

            if not choices_field:
                choices_field = {
                    'A': ("Support option A", {'Prosperity': 0, 'Equality': 0, 'Freedom': 0, 'Stability': 0}),
                    'B': ("Support option B", {'Prosperity': 0, 'Equality': 0, 'Freedom': 0, 'Stability': 0}),
                    'C': ("No action", {'Prosperity': 0, 'Equality': 0, 'Freedom': 0, 'Stability': 0}),
                }

            evt = {
                'title': title,
                'description': (raw.get('description') if isinstance(raw, dict) and raw.get('description') else desc or f"Scripted debate: {title}"),
                'choices': choices_field,
                'script_key': key
            }
            events.append(evt)

        if events:
            # replace event_pool with only the successfully-parsed scripted events
            try:
                self.event_pool = events
                self.only_debates = True
            except Exception:
                pass

    # -----------------------------
    # Dynamic event generator
    # -----------------------------
    # Note: full implementation defined earlier in the file when building the event pool.
    # The earlier implementation (which prefers unseen events and matches low stats)
    # must be the one used. This placeholder is removed to avoid overriding it.

    def get_ending_scene(self):
        stats = self.stats
        if min(stats.values()) <= 0:
            return "collapse", "Aurora has fallen into chaos."
        if stats["Freedom"] > 70 and stats["Equality"] > 70:
            return "utopia", "Aurora has become a beacon of freedom and equality."
        if stats["Stability"] > 70 and stats["Freedom"] < 40:
            return "authoritarian", "Aurora is stable, but freedom is lost."
        if stats["Prosperity"] > 70:
            return "economic_power", "Aurora thrives economically, but at a cost."
        return "mixed", "Aurora stands, but its future remains uncertain."

    def get_loyal_advisor(self):
        # return the active advisor with highest trust
        active = {k: v for k, v in self.advisors.items() if v.get("active", True)}
        if not active:
            return max(self.advisors, key=lambda a: self.advisors[a]["trust"])
        return max(active, key=lambda a: active[a]["trust"]) 


# -----------------------------
#   GUI APPLICATION
# -----------------------------

class AuroraGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Aurora: Build the Perfect Society")
        self.root.geometry("800x600")
        self.game = AuroraGame()

        # -------------------------
        # Fonts
        # -------------------------
        self.pixel_font = ("PressStart2P", 10)

        # Debate tuning (can be adjusted via Settings)
        self.debate_chance = 0.35
        self.debate_line_delay = 700  # ms between lines in debate modal
        # preload advisor portraits (used during debates and intro)
        self.advisor_images = {}
        for key, info in self.game.advisors.items():
            try:
                img = PhotoImage(file=info.get('portrait'))
                try:
                    img = img.subsample(4, 4)
                except Exception:
                    pass
                self.advisor_images[key] = img
            except Exception:
                self.advisor_images[key] = None

        # -------------------------
        # TITLE SCREEN
        # -------------------------
        self.show_title()

    # -------------------------
    # TITLE SCREEN
    # -------------------------
    def show_title(self):
        self.clear_screen()
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text="AURORA", font=("PressStart2P", 24)).pack(pady=10)
        tk.Label(frame, text="Build the Perfect Society", font=("PressStart2P", 14)).pack(pady=5)

        tk.Button(frame, text="Start Game", font=self.pixel_font,
                  command=self.start_game).pack(pady=10)
        tk.Button(frame, text="Sources", font=self.pixel_font, command=self.show_sources).pack(pady=4)
        tk.Button(frame, text="Quit", font=self.pixel_font,
                  command=self.root.quit).pack()

    # -------------------------
    # GAME START
    # -------------------------
    def start_game(self):
        self.clear_screen()
        self.show_advisors_scene()

    # -------------------------
    # ADVISOR INTRO SCENE
    # -------------------------
    def show_advisors_scene(self):
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        tk.Label(frame, text="ADVISORS", font=("PressStart2P", 18)).pack(pady=5)

        adv_frame = tk.Frame(frame)
        adv_frame.pack(pady=5)

        # Use preloaded images when available
        for key, info in self.game.advisors.items():
            slot = tk.Frame(adv_frame, bd=2, relief="groove")
            slot.pack(side="left", padx=10)
            img = self.advisor_images.get(key)
            if img:
                tk.Label(slot, image=img).pack()
            else:
                tk.Label(slot, text="[Image Missing]", font=self.pixel_font).pack()
            # Name and trust
            tk.Label(slot, text=f"{info['name']}\nTrust: {info['trust']}", font=self.pixel_font).pack(pady=4)
            # Bio under name
            bio = info.get('bio', '')
            if bio:
                tk.Label(slot, text=bio, font=("Arial", 8), wraplength=160, justify="center").pack(pady=2)

        tk.Button(frame, text="Continue", font=self.pixel_font,
                  command=lambda: (frame.destroy(), self.build_game_ui())).pack(pady=10)

    # -------------------------
    # BUILD GAME UI
    # -------------------------
    def build_game_ui(self):
        # Map & flag panel (fade in/out handled manually later)
        self.top_panel = tk.Frame(self.root)
        self.top_panel.pack(pady=5)
        try:
            self.flag_img = PhotoImage(file="aurora_flag.png").subsample(3,3)
            tk.Label(self.top_panel, image=self.flag_img).pack(side="left", padx=10)
        except:
            tk.Label(self.top_panel, text="[Flag Missing]", font=self.pixel_font).pack(side="left", padx=10)

        try:
            self.map_img = PhotoImage(file="aurora_map.png").subsample(3,3)
            tk.Label(self.top_panel, image=self.map_img).pack(side="left", padx=10)
        except:
            tk.Label(self.top_panel, text="[Map Missing]", font=self.pixel_font).pack(side="left", padx=10)

        # Advisor panel
        self.advisor_panel = tk.Frame(self.root)
        self.advisor_panel.pack(pady=5)
        self.left_advisor = tk.Frame(self.advisor_panel)
        self.left_advisor.pack(side="left", padx=5)
        self.right_advisor = tk.Frame(self.advisor_panel)
        self.right_advisor.pack(side="left", padx=5)
        # Recommendations display
        self.recommendation_frame = tk.Frame(self.advisor_panel)
        self.recommendation_frame.pack(side="left", padx=10)

        # Button to view advisor trust
        tk.Button(self.top_panel, text="Advisor Trust", font=self.pixel_font,
                  command=self.show_trust_popup).pack(side="right", padx=8)
        tk.Button(self.top_panel, text="Debate Settings", font=self.pixel_font,
                  command=self.show_debate_settings).pack(side="right", padx=4)
        tk.Button(self.top_panel, text="Sources", font=self.pixel_font,
              command=self.show_sources).pack(side="right", padx=4)

        # Dialogue
        self.dialogue_label = tk.Label(self.root, text="", font=self.pixel_font, wraplength=780, justify="left")
        self.dialogue_label.pack(pady=5)

        # Choices
        self.button_frame = tk.Frame(self.root)
        self.button_frame.pack(pady=10)

        self.choice_buttons = {}
        for idx, key in enumerate(["A","B","C"]):
            btn = tk.Button(self.button_frame, text=f"Choice {key}", font=self.pixel_font,
                            width=50, command=lambda k=key: self.choose(k))
            btn.pack(pady=2)
            self.choice_buttons[key] = btn

        # Start first event
        self.new_event()

    # -------------------------
    # GAME FLOW
    # -------------------------
    def new_event(self):
        event = self.game.generate_dynamic_event()
        self.current_event = event
        self.dialogue_label.config(text="")

        # prevent choices from being activated while text is typing
        for btn in self.choice_buttons.values():
            btn.config(state="disabled")

        # Show advisor recommendations for this event
        self.current_recommendations = self.game.get_advisor_recommendations(event)
        for widget in self.recommendation_frame.winfo_children():
            widget.destroy()
        # color mapping for recommended choices
        choice_colors = {"A": "#88cc88", "B": "#88aacc", "C": "#cc8888"}
        for key, info in self.game.advisors.items():
            # skip advisors who have left
            if not info.get('active', True):
                continue
            rec = self.current_recommendations.get(key, {})
            # container for advisor recommendation
            c = tk.Frame(self.recommendation_frame)
            c.pack(pady=2, anchor="w")
            # small colored indicator showing recommended choice
            color = choice_colors.get(rec.get('choice'), "#dddddd")
            indicator = tk.Label(c, width=2, bg=color)
            indicator.pack(side="left", padx=(0,6))
            # compute predicted trust delta for each possible player choice
            rec_choice = rec.get('choice')
            pref_stat = self.game.advisor_prefs.get(key)
            deltas = {}
            for ch, (desc, effects) in event['choices'].items():
                # compute advisor-specific score for this choice (same heuristic used earlier)
                score_for_choice = 0
                if pref_stat:
                    score_for_choice = effects.get(pref_stat, 0)
                score_for_choice += sum(v for v in effects.values()) * 0.01
                # base delta: +3 if advisor recommended this choice, else -2
                delta = 3 if (rec_choice and ch == rec_choice) else -2
                # harsher penalty if this particular choice harms their preferred stat
                if score_for_choice < 0:
                    delta += -3
                deltas[ch] = int(delta)

            # format per-choice predicted trust like "A:+3->53 B:-2->47 C:-5->44"
            current_trust = info.get('trust', 0)
            pred_parts = []
            for k, d in deltas.items():
                predicted = max(0, min(100, current_trust + d))
                pred_parts.append(f"{k}:{d:+d}->{predicted}")
            pred_str = " ".join(pred_parts)

            txt = f"{info['name']} (Trust {current_trust}): {rec.get('choice')} — {rec.get('reason')}  ({pred_str})"
            tk.Label(c, text=txt, font=("Arial", 8), justify="left").pack(side="left")

        # Update buttons
        for key, btn in self.choice_buttons.items():
            btn.config(text=f"{key}) {event['choices'][key][0]}")

        # start typing, and only enable buttons after typing finishes
        def _on_typing_done():
            for btn in self.choice_buttons.values():
                btn.config(state="normal")
            # clear any busy flag
            try:
                self._busy = False
            except Exception:
                pass

        self.type_text(f"Year {self.game.year}: {event['title']}\n{event['description']}", on_complete=_on_typing_done)

    # -------------------------
    # TYPING EFFECT
    # -------------------------
    def type_text(self, text, idx=0, on_complete=None):
        # start typing; call on_complete() when finished
        if idx == 0:
            try:
                self._busy = True
            except Exception:
                pass
        if idx < len(text):
            self.dialogue_label.config(text=self.dialogue_label.cget("text")+text[idx])
            self.root.after(20, lambda: self.type_text(text, idx+1, on_complete))
        else:
            try:
                self._busy = False
            except Exception:
                pass
            if on_complete:
                try:
                    on_complete()
                except Exception:
                    pass

    # -------------------------
    # CHOICES
    # -------------------------
    def choose(self, key):
        # ignore presses while another action/typing is in progress
        if getattr(self, '_busy', False):
            return

        # mark busy immediately to prevent rapid double-activation
        self._busy = True

        _, effects = self.current_event["choices"][key]
        self.game.apply_effects(effects)
        for btn in self.choice_buttons.values():
            btn.config(state="disabled")

        # Adjust trust
        agreements, left = self.game.adjust_trust_after_choice(key, self.current_recommendations, self.current_event.get('choices'))

        # if any advisors left, show a resignation popup first
        if left:
            self.show_resignation_popup(left)

        # Decide whether to show a debate: occasional or when tensions are high
        show_debate = False
        # small random chance (tunable)
        if random.random() < self.debate_chance:
            show_debate = True
        # or if any conflict is high or any trust is low
        if any(v >= 50 for v in self.game.conflict.values()):
            show_debate = True
        if any(info['trust'] < 30 and info.get('active', True) for info in self.game.advisors.values()):
            show_debate = True

        if show_debate:
            self.show_advisor_debate(agreements)
        else:
            # No debate: proceed to next year
            if self.game.collapsed() or self.game.year >= self.game.max_years:
                self.root.after(400, self.end_game)
            else:
                self.game.year += 1
                self.root.after(400, self.new_event)

    # -------------------------
    # END GAME
    # -------------------------
    def end_game(self):
        self.clear_screen()
        frame = tk.Frame(self.root)
        frame.pack(expand=True)

        scene_type, scene_text = self.game.get_ending_scene()
        loyal = self.game.get_loyal_advisor()
        rebels = self.game.check_advisor_rebellion()

        tk.Label(frame, text="FINAL OUTCOME", font=("PressStart2P",14)).pack(pady=5)
        tk.Label(frame, text=scene_text, font=self.pixel_font, wraplength=780).pack(pady=5)

        tk.Label(frame, text=f"Loyal Advisor: {self.game.advisors[loyal]['name']}", font=self.pixel_font, fg="green").pack()
        if rebels:
            rebel_names = [self.game.advisors[r]["name"] for r in rebels]
            tk.Label(frame, text=f"Rebels: {', '.join(rebel_names)}", font=self.pixel_font, fg="red").pack()

        for stat, val in self.game.stats.items():
            tk.Label(frame, text=f"{stat}: {val}", font=self.pixel_font).pack()

        tk.Button(frame, text="Play Again", font=self.pixel_font, command=self.reset_and_start).pack(pady=5)
        tk.Button(frame, text="Quit", font=self.pixel_font, command=self.root.quit).pack(pady=5)

    def show_advisor_debate(self, agreements):
        # Use a modal Toplevel so the debate is centered and blocks the main window
        top = tk.Toplevel(self.root)
        top.transient(self.root)
        top.title("Advisor Debate")
        # compute a larger modal size based on main window and center it
        try:
            self.root.update_idletasks()
            rw = max(600, self.root.winfo_width())
            rh = max(420, self.root.winfo_height())
        except Exception:
            rw, rh = 800, 600
        # target size: slightly smaller than root but with sensible minimums/maximums
        w = max(700, min(1000, rw - 80))
        h = max(420, min(800, rh - 120))
        x = self.root.winfo_rootx() + max(0, (rw - w) // 2)
        y = self.root.winfo_rooty() + max(0, (rh - h) // 2)
        try:
            top.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            try:
                top.geometry(f"800x480")
            except Exception:
                pass
        # make modal blocking and fixed size so it opens large enough automatically
        try:
            top.grab_set()
            top.minsize(640, 360)
            top.resizable(False, False)
        except Exception:
            pass

        container = tk.Frame(top, bd=2, relief="ridge")
        container.pack(fill="both", expand=True, padx=8, pady=8)
        header = tk.Label(container, text="Advisor Debate", font=("PressStart2P", 12))
        header.pack(pady=(0,6))

        # Compose a short back-and-forth dialogue where advisors state what they agree/disagree on
        dialogue_box = tk.Frame(container)
        dialogue_box.pack(fill="both", expand=True)

        # Build lines using personalized templates for each advisor
        # Combine the main line and follow-up into a single utterance to avoid
        # repeated openings or duplicated starting phrases.
        lines = []
        for adv_key, agreed in agreements.items():
            # skip if advisor left
            if not self.game.advisors.get(adv_key, {}).get('active', True):
                continue
            rec = self.current_recommendations.get(adv_key, {})
            main = self.game.get_personalized_line(adv_key, agreed, rec)
            follow = self.game.get_personalized_followup(adv_key, agreed, rec)
            # combine into one line; avoid prepending the advisor name again
            combined = main
            if follow:
                combined = (combined + " " + follow).strip()
            # include adv_key so we can show/highlight portrait while they speak
            lines.append((combined, agreed, adv_key))

        # Show lines one by one with colored text
        # compute wraplength based on modal width so text wraps cleanly
        try:
            wraplen = int(w - 220)
        except Exception:
            wraplen = 600

        # portrait area to the left of the dialogue
        portrait_frame = tk.Frame(container, bd=2, relief="flat", padx=6, pady=6)
        portrait_frame.pack(side="left", fill="y", padx=(4,8))
        portrait_label = tk.Label(portrait_frame)
        portrait_label.pack()

        def pulse_border(color="#ffd24d", times=2, ms=180):
            # simple border flash/pulse effect by toggling highlight
            def _on(step, remaining):
                if remaining <= 0:
                    portrait_frame.config(highlightthickness=0)
                    return
                # alternate highlight on/off
                if step % 2 == 0:
                    portrait_frame.config(highlightbackground=color, highlightthickness=4)
                else:
                    portrait_frame.config(highlightthickness=0)
                top.after(ms, lambda: _on(step+1, remaining-1))
            _on(0, times*2)

        def show_line(i=0):
            if i >= len(lines):
                # show continue button
                btn = tk.Button(container, text="Continue", font=self.pixel_font, command=finish)
                btn.pack(pady=6)
                return
            text, positive, adv_key = lines[i]
            # update portrait for current speaker and animate
            img = self.advisor_images.get(adv_key)
            if img:
                portrait_label.config(image=img, bd=2, relief="solid")
                portrait_label.image = img
            else:
                portrait_label.config(text=self.game.advisors[adv_key]['name'], font=self.pixel_font)
            # highlight color: greenish for agree, red for disagree
            fg = "#1a8f00" if positive else "#b00000"
            # slightly different pulse color for agree/disagree
            pulse_color = "#8fe08f" if positive else "#ff9a9a"
            pulse_border(color=pulse_color, times=2, ms=140)
            lbl = tk.Label(dialogue_box, text=text, font=self.pixel_font, wraplength=wraplen, justify="left", fg=fg)
            lbl.pack(anchor="w", pady=2)
            top.update_idletasks()
            # schedule next line using tunable delay
            top.after(self.debate_line_delay, lambda: show_line(i+1))

        def finish():
            try:
                top.grab_release()
                top.destroy()
            except Exception:
                pass
            # proceed to next year or end
            if self.game.collapsed() or self.game.year >= self.game.max_years:
                self.root.after(200, self.end_game)
            else:
                self.game.year += 1
                self.root.after(200, self.new_event)

        show_line(0)

    def show_trust_popup(self):
        # Simple popup showing advisor trust levels
        popup = tk.Toplevel(self.root)
        popup.title("Advisor Trust")
        popup.geometry("300x200")
        for key, info in self.game.advisors.items():
            status = f"{info['trust']}"
            if not info.get('active', True):
                status = f"Resigned ({info.get('left_reason','left')})"
            tk.Label(popup, text=f"{info['name']}: {status}", font=self.pixel_font).pack(pady=4)
        tk.Button(popup, text="Close", command=popup.destroy, font=self.pixel_font).pack(pady=6)

    def show_resignation_popup(self, left_keys):
        s = tk.Toplevel(self.root)
        s.title("Advisor Resignation")
        s.geometry("420x160")
        frm = tk.Frame(s, padx=8, pady=8)
        frm.pack(fill="both", expand=True)
        lines = []
        for k in left_keys:
            info = self.game.advisors.get(k, {})
            lines.append(f"{info.get('name','Advisor')} has resigned: {info.get('left_reason','')}")
        tk.Label(frm, text="Advisor Resignations", font=("PressStart2P", 12)).pack(pady=(0,6))
        for L in lines:
            tk.Label(frm, text=L, font=self.pixel_font, wraplength=380, justify="left").pack(anchor="w", pady=4)
        tk.Button(frm, text="Close", command=s.destroy, font=self.pixel_font).pack(pady=6)

    def show_sources(self):
        # Show citations/sources in a modal. Try loading common files; otherwise show defaults.
        s = tk.Toplevel(self.root)
        s.title("Sources & Citations")
        s.geometry("600x400")
        frm = tk.Frame(s)
        frm.pack(fill="both", expand=True, padx=8, pady=8)
        text = tk.Text(frm, wrap="word")
        sb = tk.Scrollbar(frm, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)

        # Try reading SOURCES.txt or CITATIONS.md
        content = None
        for fname in ("SOURCES.txt", "CITATIONS.md", "SOURCES.md"):
            if os.path.exists(fname):
                try:
                    with open(fname, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception:
                    content = None
                break

        if not content:
            content = (
                "Sources and Citations\n\n"
                "- Event templates: internal game design and synthetic templates.\n"
                "- Personality templates: authored in-game for narrative variety.\n"
                "- Images: expected in workspace as advisor_economy.png, advisor_rights.png, advisor_security.png.\n"
                "\nTo customize, add a SOURCES.txt or CITATIONS.md file to the game folder and reopen this dialog."
            )

        text.insert("1.0", content)
        text.config(state="disabled")
        tk.Button(s, text="Close", command=s.destroy, font=self.pixel_font).pack(pady=6)

    def reset_and_start(self):
        # Reset game state fully and start fresh from year 1
        try:
            self.game = AuroraGame()
        except Exception:
            # fallback: reassign minimal state
            self.game = AuroraGame()

        # Refresh preloaded advisor images in case advisors changed
        for key, info in self.game.advisors.items():
            try:
                img = PhotoImage(file=info.get('portrait'))
                try:
                    img = img.subsample(4, 4)
                except Exception:
                    pass
                self.advisor_images[key] = img
            except Exception:
                self.advisor_images[key] = None

        # Return to advisor intro and then into the game
        self.clear_screen()
        self.show_advisors_scene()

    def show_debate_settings(self):
        # Popup to tune debate chance and line delay
        s = tk.Toplevel(self.root)
        s.title("Debate Settings")
        s.geometry("360x180")
        tk.Label(s, text="Debate chance (%)", font=self.pixel_font).pack(pady=(8,0))
        chance_scale = tk.Scale(s, from_=0, to=100, orient="horizontal")
        chance_scale.set(int(self.debate_chance * 100))
        chance_scale.pack(fill="x", padx=12)

        tk.Label(s, text="Line delay (ms)", font=self.pixel_font).pack(pady=(6,0))
        delay_scale = tk.Scale(s, from_=100, to=2000, orient="horizontal")
        delay_scale.set(self.debate_line_delay)
        delay_scale.pack(fill="x", padx=12)

        def apply_settings():
            self.debate_chance = max(0.0, min(1.0, chance_scale.get() / 100.0))
            self.debate_line_delay = int(delay_scale.get())
            s.destroy()

        tk.Button(s, text="Apply", command=apply_settings, font=self.pixel_font).pack(pady=8)

    # -------------------------
    # CLEAR SCREEN UTILITY
    # -------------------------
    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()


# -----------------------------
#   RUN APP
# -----------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = AuroraGUI(root)
    root.mainloop()