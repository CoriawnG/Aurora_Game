import os, json, re, sys

# Allow running from tools/ or repo root by adding repo root to sys.path
here = os.path.dirname(__file__)
repo_root = os.path.abspath(os.path.join(here, '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from aurora_gui import AuroraGame


def safe_key(s):
    k = re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")
    if not k:
        k = "event"
    return k[:80]


def build_turns_for_event(g, ev, a, b):
    """Return a list of turns (dicts) where advisors a and b argue for their
    recommended choices and explain why. Uses the game's personalization helpers.
    """
    recs = g.get_advisor_recommendations(ev)
    a_rec = recs.get(a, {'choice': None, 'reason': ''})
    b_rec = recs.get(b, {'choice': None, 'reason': ''})
    try:
        # Opening statements advocating for their preferred choice
        t1 = g.get_personalized_line(a, True, a_rec)
    except Exception:
        t1 = f"{g.advisors.get(a,{}).get('name',a)}: I recommend {a_rec.get('choice')} because {a_rec.get('reason')}"
    try:
        t2 = g.get_personalized_line(b, True, b_rec)
    except Exception:
        t2 = f"{g.advisors.get(b,{}).get('name',b)}: I recommend {b_rec.get('choice')} because {b_rec.get('reason')}"
    try:
        t3 = g.get_personalized_followup(a, True, a_rec)
    except Exception:
        t3 = a_rec.get('reason', '')
    try:
        t4 = g.get_personalized_followup(b, True, b_rec)
    except Exception:
        t4 = b_rec.get('reason', '')
    # Closing endorsements or compromise
    try:
        closing_a = f"In summary, I urge '{a_rec.get('choice')}' because {a_rec.get('reason')}"
        closing_b = f"In summary, I urge '{b_rec.get('choice')}' because {b_rec.get('reason')}"
    except Exception:
        closing_a = ''
        closing_b = ''

    turns = []
    if t1:
        turns.append({'speaker': a, 'text': t1})
    if t2:
        turns.append({'speaker': b, 'text': t2})
    if t3:
        turns.append({'speaker': a, 'text': t3})
    if t4:
        turns.append({'speaker': b, 'text': t4})
    if closing_a:
        turns.append({'speaker': a, 'text': closing_a})
    if closing_b:
        turns.append({'speaker': b, 'text': closing_b})
    return turns


def main():
    g = AuroraGame()
    out_dir = os.path.join(repo_root, 'assets', 'debates')
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for idx, ev in enumerate(g.event_pool):
        try:
            key_base = (ev.get('title','event') or '') + "_" + str(idx+1)
            key = safe_key(key_base)
            fname = os.path.join(out_dir, f"{key}.json")
            # skip existing files to avoid overwriting
            if os.path.exists(fname):
                print(f"Skipping existing: {fname}")
                continue

            # pick two advisors with differing recommended choices if possible
            recs = g.get_advisor_recommendations(ev)
            items = sorted(recs.items(), key=lambda kv: -kv[1].get('score',0))
            a = None
            b = None
            for adv_a, ra in items:
                for adv_b, rb in items:
                    if adv_a != adv_b and ra.get('choice') != rb.get('choice') and ra.get('choice') and rb.get('choice'):
                        a, b = adv_a, adv_b
                        break
                if a:
                    break
            if not a or not b:
                # attempt to pick two distinct advisors regardless
                keys = [k for k in g.advisors.keys()]
                if 'economy' in keys and 'rights' in keys:
                    a, b = 'economy', 'rights'
                elif len(keys) >= 2:
                    a, b = keys[0], keys[1]
                else:
                    a = keys[0]
                    b = keys[0]

            # choices: try to copy event choices if present, otherwise create meaningful ones
            choices = {}
            try:
                raw_choices = ev.get('choices', {})
                for k, v in raw_choices.items():
                    # v is (desc, effects) in game event format
                    if isinstance(v, (list,tuple)) and len(v) >= 2:
                        choices[k] = {'title': v[0], 'effects': v[1]}
                    else:
                        choices[k] = {'title': str(v), 'effects': {}}
            except Exception:
                choices = {
                    'A': {'title': 'Option A', 'effects': {}},
                    'B': {'title': 'Option B', 'effects': {}},
                    'C': {'title': 'No action', 'effects': {}},
                }

            turns = build_turns_for_event(g, ev, a, b)

            data = {
                'title': ev.get('title','Event'),
                'description': ev.get('description',''),
                'script_key': key,
                'choices': choices,
                'turns': turns
            }

            with open(fname, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"Wrote: {fname}")
            count += 1
        except Exception as e:
            print(f"Failed for event {idx}: {e}")
    print(f"Done: {count} files written to {out_dir}")


if __name__ == '__main__':
    main()
