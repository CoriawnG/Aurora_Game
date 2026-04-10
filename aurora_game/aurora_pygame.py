"""
Integrated Pygame front-end for Aurora.

This file provides a pixel-style Title screen, Options screen (music/SFX),
Game screen (uses AuroraGame logic), and a simple Debate screen. It expects
optional assets under ./assets/audio, ./assets/sfx, and ./assets/images.

Run with: python aurora_pygame.py
"""
import os
import sys
import math
import random
import pygame
import json
from datetime import datetime
import re

# try to import the existing game logic
try:
    from aurora_gui import AuroraGame
except Exception:
    AuroraGame = None

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
IMAGES_DIR = os.path.join(ASSETS_DIR, "images")
AUDIO_DIR = os.path.join(ASSETS_DIR, "audio")
SFX_DIR = os.path.join(ASSETS_DIR, "sfx")

WIDTH, HEIGHT = 960, 640
FPS = 60

BUTTON_COLOR = (50, 50, 60)
BUTTON_HOVER = (80, 80, 100)
BUTTON_TEXT = (200, 230, 255)
BG_TOP = (12, 18, 30)
BG_BOTTOM = (36, 12, 40)

pygame.init()
try:
    pygame.mixer.init()
except Exception:
    pass
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Aurora - Pixel Prototype")
clock = pygame.time.Clock()


# Load audio if present
def load_music():
    music_path = os.path.join(AUDIO_DIR, "music.ogg")
    if os.path.exists(music_path):
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(0.6)
            pygame.mixer.music.play(-1)
            print("Playing music:", music_path)
        except Exception as e:
            print("Failed to load music:", e)


def load_click():
    path = os.path.join(SFX_DIR, "click.wav")
    if os.path.exists(path):
        try:
            return pygame.mixer.Sound(path)
        except Exception as e:
            print("Failed to load click SFX:", e)
    return None


click_sfx = load_click()
load_music()


# Pixel-style font rendering helper: render small then scale up for crisp pixels
def pixel_text(font_name, size, text, scale=3, color=(255,255,255)):
    # prefer bundled pixel font if available
    font_path = None
    fonts_dir = os.path.join(ASSETS_DIR, 'fonts')
    if os.path.isdir(fonts_dir):
        for fn in os.listdir(fonts_dir):
            if fn.lower().endswith('.ttf') or fn.lower().endswith('.otf'):
                font_path = os.path.join(fonts_dir, fn)
                break

    try:
        # prefer an explicitly-named Press Start font if present for consistent pixel rendering
        preferred = None
        if font_path:
            for fn in os.listdir(os.path.join(ASSETS_DIR, 'fonts')):
                if fn.lower().startswith('press') and fn.lower().endswith(('.ttf', '.otf')):
                    preferred = os.path.join(ASSETS_DIR, 'fonts', fn)
                    break
        chosen = preferred or font_path
        if chosen:
            f = pygame.font.Font(chosen, size)
        else:
            f = pygame.font.SysFont(font_name, size)
    except Exception:
        f = pygame.font.SysFont(font_name, size)

    surf = f.render(text, True, color)
    # integer scale to preserve crisp pixel look
    if scale != 1 and isinstance(scale, int) and scale > 0:
        surf = pygame.transform.scale(surf, (surf.get_width()*scale, surf.get_height()*scale))
    return surf
# Tuned base sizes and scale factors for crisp pixel UI
def fit_pixel_text(text, base_size, max_scale, max_width, color=(255,255,255)):
    """Return a surface for text scaled down (integer) to fit max_width.
    Tries scales from max_scale down to 1, then truncates with ellipsis if needed.
    """
    for s in range(max_scale, 0, -1):
        surf = pixel_text(None, base_size, text, scale=s, color=color)
        if surf.get_width() <= max_width:
            return surf
    # If no integer scale fits, try reducing the base font size (avoid ellipsis)
    for reduced_size in range(base_size - 1, max(6, base_size - 12), -1):
        try:
            surf = pixel_text(None, reduced_size, text, scale=1, color=color)
            if surf.get_width() <= max_width:
                return surf
        except Exception:
            continue
    # As a last resort, fall back to truncation with ellipsis
    t = text
    surf = pixel_text(None, base_size, t, scale=1, color=color)
    if surf.get_width() <= max_width:
        return surf
    while len(t) > 3:
        t = t[:-1]
        surf = pixel_text(None, base_size, t + '...', scale=1, color=color)
        if surf.get_width() <= max_width:
            return surf
    return surf


def wrap_text_into_surfaces(text, base_size, max_scale, max_width, color=(255,255,255)):
    """Wrap `text` into multiple pixel surfaces that each fit `max_width`.
    Returns a list of surfaces (top->bottom).
    """
    words = text.split()
    if not words:
        return [pixel_text(None, base_size, '', scale=1, color=color)]
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + ' ' + w
        s = pixel_text(None, base_size, test, scale=max_scale, color=color)
        if s.get_width() <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    # now create surfaces, try to use max_scale downwards per line
    surfs = []
    for line in lines:
        for s in range(max_scale, 0, -1):
            surf = pixel_text(None, base_size, line, scale=s, color=color)
            if surf.get_width() <= max_width:
                surfs.append(surf)
                break
        else:
            # line too long even at smallest scale — trim progressively and add ellipsis
            trimmed = None
            for L in range(len(line), 0, -1):
                candidate = (line[:L].rstrip() + '...') if L < len(line) else line
                surf = pixel_text(None, base_size, candidate, scale=1, color=color)
                if surf.get_width() <= max_width:
                    trimmed = surf
                    break
            if not trimmed:
                # as a last resort, show a very short ellipsis
                trimmed = pixel_text(None, base_size, '...', scale=1, color=color)
            surfs.append(trimmed)
    return surfs


class QuitPopup:
    """Modal popup shown when an advisor quits.
    Displays a quit image (if found) and the advisor's left_reason text.
    Click or press Enter/Space to dismiss.
    """
    def __init__(self, app, game, adv_key):
        self.app = app
        self.game = game
        self.adv_key = adv_key
        self.closed = False
        self.start_time = pygame.time.get_ticks()
        # resolve advisor info
        self.info = self.game.advisors.get(adv_key, {}) if getattr(self.game, 'advisors', None) else {}
        self.name = self.info.get('name', adv_key)
        self.reason = self.info.get('left_reason', 'No reason given.')
        self.image = self._load_quit_image()

    def _load_quit_image(self):
        # look for files like 'Ada quit.png' or 'ada quit.png' or '<adv_key> quit.png'
        try:
            files = os.listdir(IMAGES_DIR) if os.path.exists(IMAGES_DIR) else []
        except Exception:
            files = []
        files_map = {f.lower(): f for f in files}
        candidates = []
        # add name-based candidates
        if self.name:
            candidates.append(f"{self.name} quit.png".lower())
            candidates.append(f"{self.name} quit.jpg".lower())
            candidates.append(f"{self.name.lower()}.png")
        # adv_key candidate
        candidates.append(f"{self.adv_key} quit.png")
        candidates.append(f"{self.adv_key}_quit.png")
        # check
        for cand in candidates:
            if cand in files_map:
                path = os.path.join(IMAGES_DIR, files_map[cand])
                try:
                    return pygame.image.load(path).convert_alpha()
                except Exception:
                    continue
        return None

    def update(self, events, dt):
        # If a quit popup is active, forward input to it and block normal updates
        try:
            if getattr(self, 'current_quit_popup', None):
                self.current_quit_popup.update(events, dt)
                if getattr(self.current_quit_popup, 'closed', False):
                    # popup dismissed: show next or resume game
                    self.current_quit_popup = None
                    try:
                        if getattr(self, 'pending_quit_keys', None):
                            next_key = self.pending_quit_keys.pop(0)
                            self.current_quit_popup = QuitPopup(self.app, self.game, next_key)
                        else:
                            if self.game.collapsed() or self.game.year >= self.game.max_years:
                                try:
                                    self.app.current_screen = EndScreen(self.app, self.game)
                                except Exception:
                                    self.app.current_screen = self.app.title_screen
                                return
                            else:
                                self.game.year += 1
                                self.new_event()
                    except Exception:
                        self.current_quit_popup = None
                return
        except Exception:
            pass
        # dismiss on mouse click inside popup or Enter/Space; fallback polls input
        try:
            for e in events:
                # mouse
                if e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
                    btn = getattr(e, 'button', None)
                    if btn == 1:
                        try:
                            mx, my = getattr(e, 'pos', pygame.mouse.get_pos())
                        except Exception:
                            mx, my = pygame.mouse.get_pos()
                        bw = min(WIDTH - 160, 760)
                        bh = min(HEIGHT - 160, 320)
                        bx = (WIDTH - bw)//2
                        by = (HEIGHT - bh)//2
                        if bx <= mx <= bx + bw and by <= my <= by + bh:
                            self.closed = True
                            return
                # keyboard
                if e.type == pygame.KEYDOWN:
                    if getattr(e, 'key', None) in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self.closed = True
                        return
        except Exception:
            pass

        # Fallback polling if events aren't received by the popup for some reason
        try:
            mx, my = pygame.mouse.get_pos()
            pressed = pygame.mouse.get_pressed()
            bw = min(WIDTH - 160, 760)
            bh = min(HEIGHT - 160, 320)
            bx = (WIDTH - bw)//2
            by = (HEIGHT - bh)//2
            if pressed and pressed[0] and bx <= mx <= bx + bw and by <= my <= by + bh:
                self.closed = True
                return
        except Exception:
            pass
        try:
            keys = pygame.key.get_pressed()
            if keys and (keys[pygame.K_RETURN] or keys[pygame.K_SPACE]):
                self.closed = True
                return
        except Exception:
            pass

    def draw(self):
        # dim background
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))
        # central box
        bw = min(WIDTH - 160, 760)
        bh = min(HEIGHT - 160, 320)
        bx = (WIDTH - bw)//2
        by = (HEIGHT - bh)//2
        pygame.draw.rect(screen, (18,18,22), (bx, by, bw, bh), border_radius=8)
        pygame.draw.rect(screen, (120,120,130), (bx, by, bw, bh), 2, border_radius=8)
        # draw image left if present
        pad = 18
        img_w = min(220, int(bh - pad*2))
        if self.image:
            try:
                img = pygame.transform.smoothscale(self.image, (img_w, img_w))
                screen.blit(img, (bx + pad, by + pad))
            except Exception:
                pass
        else:
            # placeholder box
            pygame.draw.rect(screen, (70,70,80), (bx + pad, by + pad, img_w, img_w))
            init = "".join([w[0] for w in self.name.split()[:2]]).upper()
            s = fit_pixel_text(init, ADVISOR_NAME_SIZE, ADVISOR_NAME_SCALE, img_w-8, color=(220,220,220))
            screen.blit(s, (bx + pad + (img_w - s.get_width())//2, by + pad + (img_w - s.get_height())//2))

        # draw text area to the right
        tx = bx + pad + img_w + 16
        tw = bw - (img_w + pad*3 + 16)
        title = pixel_text(None, OPTIONS_TITLE_SIZE, f"{self.name} has quit", scale=OPTIONS_TITLE_SCALE, color=(240,200,200))
        screen.blit(title, (tx, by + pad))
        # reason wrapped
        reason_lines = wrap_text_into_surfaces(self.reason, OPTIONS_LABEL_SIZE, OPTIONS_LABEL_SCALE, tw, color=(220,220,220))
        y = by + pad + title.get_height() + 12
        for s in reason_lines:
            screen.blit(s, (tx, y))
            y += s.get_height() + 6
        # hint
        hint = pixel_text(None, OPTIONS_LABEL_SIZE, "Click or press Enter to continue", scale=OPTIONS_LABEL_SCALE, color=(180,180,200))
        screen.blit(hint, (bx + bw - pad - hint.get_width(), by + bh - pad - hint.get_height()))

# Tuned base sizes and scale factors for crisp pixel UI


# Tuned base sizes and scale factors for crisp pixel UI
TITLE_SIZE = 12
TITLE_SCALE = 8
SUBTITLE_SIZE = 8
SUBTITLE_SCALE = 3
BUTTON_SIZE = 10
# reduce button text scale so buttons remain visually dominant
BUTTON_SCALE = 2
OPTIONS_TITLE_SIZE = 10
OPTIONS_TITLE_SCALE = 4
OPTIONS_LABEL_SIZE = 8
OPTIONS_LABEL_SCALE = 2
# slightly reduce dialog size for readability in gameplay
DIALOG_SIZE = 9
DIALOG_SCALE = 2
# advisor HUD text slightly smaller
ADVISOR_NAME_SIZE = 9
ADVISOR_NAME_SCALE = 2
ADVISOR_DELTA_SIZE = 8
ADVISOR_DELTA_SCALE = 1
DEBATE_TITLE_SIZE = 10
DEBATE_TITLE_SCALE = 4
DEBATE_BODY_SIZE = 9
DEBATE_BODY_SCALE = 2
# separate, smaller title used in gameplay (keeps main TitleScreen large)
GAME_TITLE_SIZE = 10
GAME_TITLE_SCALE = 4

# Ending configuration (tweak thresholds here)
THRESH_CATASTROPHIC_MIN = 20
THRESH_RESOUNDING_AVG = 80
THRESH_PROSPEROUS_AVG = 65
THRESH_MIXED_AVG = 45
THRESH_STRAINED_AVG = 30

# Global downscale factor for EndScreen text (helps fit small/fullscreen)
ENDING_SCALE_FACTOR = 0.75

# Per-advisor ending notes (keyed by advisor id or a substring of advisor name)
ADVISOR_END_MESSAGES = {
    'economy': "Stabilized markets and fiscal gains credited to this advisor.",
    'security': "Maintained order and national security during crises.",
    'rights': "Advocated civil liberties and checks on power.",
}
# Debates are fully scripted by JSON files in `assets/debates/`.
# All dynamic generation and voice-template helpers have been removed
# so the system uses only the data contained in those JSON files.
def load_debate_script(game, event):
    """Load a debate JSON from assets/debates.
    Returns the parsed dict (or None). The loader checks these keys in order:
      - event['script_key'], event['id'], sanitized title
      - year_<n>
    It also supports a mapping file assets/debates.json with keys -> script bodies.
    Expected script form: {
      "title":..., "description":..., "choices": {"A": {"title":..., "effects": {...}}, ...},
      "turns": [{"speaker":"economy","text":"..."}, ...]
    }
    """
    try:
        candidates = []
        if event and isinstance(event, dict):
            if 'script_key' in event:
                candidates.append(str(event['script_key']))
            if 'id' in event:
                candidates.append(str(event['id']))
            title = (event.get('title') or '').strip()
            if title:
                tk = re.sub(r"\s+", "_", title.lower())
                tk = re.sub(r"[^a-z0-9_]+", "", tk)
                candidates.append(tk)
        try:
            y = getattr(game, 'year', None)
            if y is not None:
                candidates.append(f"year_{y}")
        except Exception:
            pass

        debates_dir = os.path.join(ASSETS_DIR, 'debates')
        # try files
        for k in candidates:
            if not k:
                continue
            p = os.path.join(debates_dir, f"{k}.json")
            if os.path.exists(p):
                try:
                    with open(p, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return data
                    # handle plain list by wrapping
                    if isinstance(data, list):
                        return {'turns': data}
                except Exception:
                    continue

        # fallback mapping file
        # prefer a mapping file located inside the debates folder only
        map_path = os.path.join(debates_dir, 'debates.json')
        if os.path.exists(map_path):
            try:
                with open(map_path, 'r', encoding='utf-8') as f:
                    dd = json.load(f)
                if isinstance(dd, dict):
                    for k in candidates:
                        if not k:
                            continue
                        if k in dd and isinstance(dd[k], (dict, list)):
                            if isinstance(dd[k], dict):
                                return dd[k]
                            return {'turns': dd[k]}
            except Exception:
                pass
    except Exception:
        pass
    return None

# Debate system temporarily disabled. Previously there was a DebateScreen class here.
# Debates are skipped and the game advances directly after choices until this
class Button:
    def __init__(self, rect, text, action=None):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.action = action
        self.hover = False
        self.base_surf = pixel_text(None, BUTTON_SIZE, text, scale=BUTTON_SCALE, color=BUTTON_TEXT)

    def draw(self, surf):
        col = BUTTON_HOVER if self.hover else BUTTON_COLOR
        pygame.draw.rect(surf, col, self.rect, border_radius=8)
        inner = self.rect.inflate(-6, -6)
        pygame.draw.rect(surf, (max(0,col[0]-10), max(0,col[1]-10), max(0,col[2]-10)), inner, border_radius=6)
        ts = self.base_surf
        tx = self.rect.centerx - ts.get_width()//2
        ty = self.rect.centery - ts.get_height()//2
        surf.blit(ts, (tx, ty))

    def update(self, mouse_pos, mouse_up):
        self.hover = self.rect.collidepoint(mouse_pos)
        if self.hover and mouse_up:
            if click_sfx:
                click_sfx.play()
            if self.action:
                self.action()


class OptionsScreen:
    def __init__(self, app):
        self.app = app
        # simple volume sliders represented as values 0..1
        try:
            self.music_vol = pygame.mixer.music.get_volume() if pygame.mixer.get_init() else 0.6
        except Exception:
            self.music_vol = 0.6
        try:
            self.sfx_vol = click_sfx.get_volume() if click_sfx else 0.8
        except Exception:
            self.sfx_vol = 0.8
        self.show = True
        # back button
        self.back = Button((WIDTH//2 - 80, HEIGHT - 120, 160, 48), "Back", self.close)
        # dragging state for smooth slider interaction
        self.dragging_music = False
        self.dragging_sfx = False
        self.dragging_debate = False

    def close(self):
        # return to the screen that opened Options if available, otherwise title
        prev = getattr(self, 'previous_screen', None)
        try:
            if prev:
                self.app.current_screen = prev
            else:
                self.app.current_screen = self.app.title_screen
        except Exception:
            self.app.current_screen = self.app.title_screen

    def handle_event(self, events):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        self.back.update(mouse_pos, mouse_up)
        # slider interactions (support click+drag)
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                # music slider area
                if WIDTH//2 - 200 <= mx <= WIDTH//2 + 200 and HEIGHT//2 - 20 <= my <= HEIGHT//2 + 4:
                    self.dragging_music = True
                    self.music_vol = (mx - (WIDTH//2 - 200)) / 400.0
                    try:
                        pygame.mixer.music.set_volume(self.music_vol)
                    except Exception:
                        pass
                # sfx slider area
                if WIDTH//2 - 200 <= mx <= WIDTH//2 + 200 and HEIGHT//2 + 40 <= my <= HEIGHT//2 + 64:
                    self.dragging_sfx = True
                    self.sfx_vol = (mx - (WIDTH//2 - 200)) / 400.0
                    if click_sfx:
                        click_sfx.set_volume(self.sfx_vol)
                # debate probability slider area
                if WIDTH//2 - 200 <= mx <= WIDTH//2 + 200 and HEIGHT//2 + 100 <= my <= HEIGHT//2 + 124:
                    self.dragging_debate = True
                    val = (mx - (WIDTH//2 - 200)) / 400.0
                    try:
                        self.app.debate_prob = max(0.0, min(1.0, val))
                    except Exception:
                        pass
            elif e.type == pygame.MOUSEMOTION:
                mx, my = e.pos
                if getattr(self, 'dragging_music', False):
                    self.music_vol = max(0.0, min(1.0, (mx - (WIDTH//2 - 200)) / 400.0))
                    try:
                        pygame.mixer.music.set_volume(self.music_vol)
                    except Exception:
                        pass
                if getattr(self, 'dragging_sfx', False):
                    self.sfx_vol = max(0.0, min(1.0, (mx - (WIDTH//2 - 200)) / 400.0))
                    if click_sfx:
                        click_sfx.set_volume(self.sfx_vol)
                if getattr(self, 'dragging_debate', False):
                    val = max(0.0, min(1.0, (mx - (WIDTH//2 - 200)) / 400.0))
                    try:
                        self.app.debate_prob = val
                    except Exception:
                        pass
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self.dragging_music = False
                self.dragging_sfx = False
                self.dragging_debate = False

    def update(self, events):
        # pass events to handlers (keep OptionsScreen simple)
        self.handle_event(events)
        # normal options update

    def draw(self):
        # dim backdrop
        screen.fill((10, 10, 12))
        title = pixel_text(None, OPTIONS_TITLE_SIZE, "Options", scale=OPTIONS_TITLE_SCALE, color=(200,240,255))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 60))
        # Music slider
        pygame.draw.rect(screen, (60,60,70), (WIDTH//2 - 200, HEIGHT//2 - 20, 400, 24))
        pygame.draw.rect(screen, (120,200,180), (WIDTH//2 - 200, HEIGHT//2 - 20, int(400*self.music_vol), 24))
        # music knob
        mx_x = WIDTH//2 - 200 + int(400 * self.music_vol)
        pygame.draw.circle(screen, (240,240,240), (mx_x, HEIGHT//2 - 8), 8)
        mlabel = pixel_text(None, OPTIONS_LABEL_SIZE, f"Music Volume: {int(self.music_vol*100)}%", scale=OPTIONS_LABEL_SCALE)
        screen.blit(mlabel, (WIDTH//2 - mlabel.get_width()//2, HEIGHT//2 - 60))
        # SFX slider
        pygame.draw.rect(screen, (60,60,70), (WIDTH//2 - 200, HEIGHT//2 + 40, 400, 24))
        pygame.draw.rect(screen, (220,160,160), (WIDTH//2 - 200, HEIGHT//2 + 40, int(400*self.sfx_vol), 24))
        sfx_x = WIDTH//2 - 200 + int(400 * self.sfx_vol)
        pygame.draw.circle(screen, (240,240,240), (sfx_x, HEIGHT//2 + 52), 8)
        slabel = pixel_text(None, OPTIONS_LABEL_SIZE, f"SFX Volume: {int(self.sfx_vol*100)}%", scale=OPTIONS_LABEL_SCALE)
        screen.blit(slabel, (WIDTH//2 - slabel.get_width()//2, HEIGHT//2 + 80))
        # Debate probability slider
        dp = getattr(self.app, 'debate_prob', 0.25)
        pygame.draw.rect(screen, (60,60,70), (WIDTH//2 - 200, HEIGHT//2 + 100, 400, 24))
        pygame.draw.rect(screen, (180,180,220), (WIDTH//2 - 200, HEIGHT//2 + 100, int(400*dp), 24))
        db_x = WIDTH//2 - 200 + int(400 * dp)
        pygame.draw.circle(screen, (240,240,240), (db_x, HEIGHT//2 + 112), 8)
        dlabel = pixel_text(None, OPTIONS_LABEL_SIZE, f"Debate Chance: {int(dp*100)}%", scale=OPTIONS_LABEL_SCALE)
        screen.blit(dlabel, (WIDTH//2 - dlabel.get_width()//2, HEIGHT//2 + 140))
        self.back.draw(screen)
        


class SourcesScreen:
    def __init__(self, app):
        self.app = app
        self.lines = []
        self.offset = 0
        self.back = Button((WIDTH//2 - 80, HEIGHT - 120, 160, 48), "Back", self.close)
        # try to load Sources.txt next to the script
        try:
            base = os.path.dirname(__file__)
            p = os.path.join(base, 'Sources.txt')
            if not os.path.exists(p):
                p = os.path.join(ASSETS_DIR, 'README.txt')
            if os.path.exists(p):
                with open(p, 'r', encoding='utf-8') as f:
                    self.lines = [ln.rstrip() for ln in f.readlines()]
        except Exception:
            self.lines = ["No sources available."]
        # pre-render surfaces for performance and set content area
        self.content_start_y = 120
        self.surfaces = []
        try:
            for ln in self.lines:
                surf = fit_pixel_text(ln, OPTIONS_LABEL_SIZE, OPTIONS_LABEL_SCALE, WIDTH - 120, color=(200,200,200))
                self.surfaces.append(surf)
        except Exception:
            self.surfaces = [pixel_text(None, OPTIONS_LABEL_SIZE, "No sources available.", scale=OPTIONS_LABEL_SCALE, color=(200,200,200))]
        self._recalc_total_height()

    def _recalc_total_height(self):
        self.total_height = sum(s.get_height() + 8 for s in self.surfaces)
        # leave bottom margin for back button
        self.max_offset = max(0, self.total_height - (HEIGHT - self.content_start_y - 160))

    def close(self):
        self.app.current_screen = self.app.title_screen

    def update(self, events, dt):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN:
                if e.button == 4:  # wheel up
                    self.offset = max(0, self.offset - 20)
                elif e.button == 5:  # wheel down
                    self.offset = min(self.max_offset, self.offset + 20)
            elif e.type == pygame.KEYDOWN:
                # support page up/down
                if e.key == pygame.K_PAGEUP:
                    self.offset = max(0, self.offset - (HEIGHT//2))
                elif e.key == pygame.K_PAGEDOWN:
                    self.offset = min(self.max_offset, self.offset + (HEIGHT//2))
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        self.back.update(mouse_pos, mouse_up)

    def draw(self):
        screen.fill((8,8,10))
        title = pixel_text(None, OPTIONS_TITLE_SIZE, "SOURCES & CREDITS", scale=OPTIONS_TITLE_SCALE, color=(220,220,240))
        # header background to keep it readable
        header_rect = pygame.Rect(0, 24, WIDTH, 64)
        pygame.draw.rect(screen, (6,6,8), header_rect)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 40))
        y = self.content_start_y - self.offset
        for s in self.surfaces:
            if y + s.get_height() < self.content_start_y:
                y += s.get_height() + 8
                continue
            if y > HEIGHT - 160:
                break
            screen.blit(s, (60, y))
            y += s.get_height() + 8
        self.back.draw(screen)


class IntroScreen:
    def __init__(self, app):
        self.app = app
        self.page = 0
        self.pages = []
        self.next_btn = Button((WIDTH - 180, HEIGHT - 120, 140, 48), "Next", self.next_page)
        self.back_btn = Button((40, HEIGHT - 120, 140, 48), "Back", self.prev_page)
        self.start_btn = Button((WIDTH//2 - 160, HEIGHT - 140, 320, 64), "Start Game", self.start_game)
        # placeholders; build_pages will populate pages, images, and rendered surfaces
        self.flag_image = None
        self.map_image = None
        self.page_surfaces = []
        self.advisor_entries = []
        # build based on current game metadata (if any)
        self.build_pages()

    def build_pages(self):
        """Construct pages, load images and advisor headshots, and pre-render text surfaces."""
        # Story page
        story_text = [
            "Welcome to Aurora — a new nation born from hardship and hope.",
            "As Leader, you steward scarce resources, laws, and the people's faith.",
            "Each year brings events that require difficult trade-offs and counsel.",
            "The flag of Aurora stands for unity, resilience, and the promise of tomorrow.",
            "Aurora Flag — a symbol of unity and renewal."
        ]
        # Map page
        map_text = [
            "Map of Aurora — regions, resources, and strategic chokepoints."
        ]
        # Advisors page will be filled from game metadata when possible
        adv_lines = []
        try:
            gm = self.app.game
            if gm and getattr(gm, 'advisors', None):
                for k, info in gm.advisors.items():
                    name = info.get('name', k)
                    bio = info.get('bio') or info.get('intro') or info.get('role') or "No description available."
                    adv_lines.append(f"{name}: {bio}")
            else:
                adv_lines = ["Advisors will guide you: Economy, Security, Rights, Infrastructure."]
        except Exception:
            adv_lines = ["Advisors will guide you: Economy, Security, Rights, Infrastructure."]

        self.pages = [("Aurora: The Story", story_text), ("Aurora: The Map", map_text), ("Aurora: Advisors", adv_lines)]

        # load images
        self.flag_image = None
        self.map_image = None
        try:
            fpath = os.path.join(IMAGES_DIR, 'aurora_flag.png')
            if os.path.exists(fpath):
                self.flag_image = pygame.image.load(fpath).convert_alpha()
                self.flag_image = pygame.transform.smoothscale(self.flag_image, (160, 96))
        except Exception:
            self.flag_image = None
        try:
            mpath = os.path.join(IMAGES_DIR, 'aurora_map.png')
            if os.path.exists(mpath):
                self.map_image = pygame.image.load(mpath).convert_alpha()
                mw = min(360, self.map_image.get_width())
                mh = int(self.map_image.get_height() * (mw / max(1, self.map_image.get_width())))
                self.map_image = pygame.transform.smoothscale(self.map_image, (mw, mh))
        except Exception:
            self.map_image = None

        # build advisor entries with headshots (flexible filename matching)
        self.advisor_entries = []
        try:
            files = []
            try:
                files = os.listdir(IMAGES_DIR)
            except Exception:
                files = []
            files_map = {f.lower(): f for f in files}

            def find_file_for(labels):
                """Return a matching filename from IMAGES_DIR given a list of label keywords.
                Fallbacks: prefer 'headshot', then any candidate; finally match role + generic picture keywords.
                """
                candidates = []
                for fname_lower, orig in files_map.items():
                    ok = True
                    for kw in labels:
                        if kw not in fname_lower:
                            ok = False
                            break
                    if ok:
                        candidates.append(orig)
                # prefer files that contain 'headshot'
                for c in candidates:
                    if 'headshot' in c.lower():
                        return c
                if candidates:
                    return candidates[0]
                # fallback: match role keyword and any picture-like keyword
                role = labels[0] if labels else ''
                picture_kw = ('headshot', 'head', 'heads', 'portrait', 'avatar', 'pic', 'photo', 'face')
                for fname_lower, orig in files_map.items():
                    if role and role in fname_lower:
                        for p in picture_kw:
                            if p in fname_lower:
                                return orig
                return None

            # roles to look for and sensible defaults
            known_roles = [
                ("Economy", ['economy', 'headshot']),
                ("Rights", ['rights', 'headshot']),
                ("Security", ['security', 'headshot']),
            ]
            for label, kws in known_roles:
                img = None
                match = find_file_for(kws)
                if match:
                    try:
                        img = pygame.image.load(os.path.join(IMAGES_DIR, match)).convert_alpha()
                        img = pygame.transform.smoothscale(img, (96, 96))
                    except Exception:
                        img = None
                # pick name and bio from game metadata if available
                name = label
                bio = ''
                try:
                    gm = self.app.game
                    if gm and getattr(gm, 'advisors', None):
                        for k, info in gm.advisors.items():
                            nm = info.get('name', '')
                            if label.lower() in nm.lower() or label.lower() in k.lower():
                                name = info.get('name', name)
                                bio = info.get('bio') or info.get('intro') or info.get('role') or ''
                                break
                except Exception:
                    pass
                if not bio:
                    if label == 'Economy':
                        bio = 'Manages fiscal policy, trade, and budgets.'
                    elif label == 'Security':
                        bio = 'Keeps order, defends borders, and manages crisis response.'
                    elif label == 'Rights':
                        bio = 'Advocates for civil liberties and checks on power.'
                self.advisor_entries.append({'role': label, 'name': name, 'bio': bio, 'img': img})
        except Exception:
            self.advisor_entries = []

        # pre-render page surfaces for story and map/advisor captions
        self.page_surfaces = []
        try:
            for heading, lines in self.pages:
                hs = pixel_text(None, OPTIONS_TITLE_SIZE, heading, scale=OPTIONS_TITLE_SCALE, color=(220,220,255))
                line_surfs = [hs]
                for ln in lines:
                    surf = fit_pixel_text(ln, OPTIONS_LABEL_SIZE, OPTIONS_LABEL_SCALE, WIDTH - 120, color=(210,210,210))
                    line_surfs.append(surf)
                self.page_surfaces.append(line_surfs)
        except Exception:
            self.page_surfaces = [[pixel_text(None, OPTIONS_TITLE_SIZE, 'Intro', scale=OPTIONS_TITLE_SCALE)]]

    def next_page(self):
        if self.page < len(self.pages)-1:
            self.page += 1

    def prev_page(self):
        if self.page > 0:
            self.page -= 1

    def start_game(self):
        # initialize game if missing then go to GameScreen
        if not self.app.game and AuroraGame:
            try:
                self.app.game = AuroraGame()
            except Exception:
                self.app.game = None
        # proceed to a LoadingScreen to allow assets to finalize loading
        if self.app.game:
            try:
                self.app.current_screen = LoadingScreen(self.app)
            except Exception:
                self.app.current_screen = GameScreen(self.app)
        else:
            self.app.current_screen = self.app.title_screen

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        self.next_btn.update(mouse_pos, mouse_up)
        self.back_btn.update(mouse_pos, mouse_up)
        self.start_btn.update(mouse_pos, mouse_up)

    def draw(self):
        screen.fill((10,10,12))
        # use pre-rendered page surfaces for performance
        if 0 <= self.page < len(self.page_surfaces):
            ps = self.page_surfaces[self.page]
        else:
            ps = [pixel_text(None, OPTIONS_TITLE_SIZE, 'Intro', scale=OPTIONS_TITLE_SCALE, color=(220,220,255))]
        # draw heading area
        heading_surf = ps[0]
        screen.blit(heading_surf, (WIDTH//2 - heading_surf.get_width()//2, 40))
        # page-specific layout handling
        if self.page == 0:
            # Story + flag: flag at left, story text at right column
            y = 120
            if self.flag_image:
                screen.blit(self.flag_image, (60, y))
                text_x = 60 + self.flag_image.get_width() + 24
            else:
                text_x = 60
            for s in ps[1:]:
                if y > HEIGHT - 200:
                    break
                screen.blit(s, (text_x, y))
                y += s.get_height() + 8
        elif self.page == 1:
            # Map page: center the map and place caption below it
            y = 120
            if self.map_image:
                mx = WIDTH//2 - self.map_image.get_width()//2
                screen.blit(self.map_image, (mx, y))
                y += self.map_image.get_height() + 12
            # draw any caption lines
            for s in ps[1:]:
                if y > HEIGHT - 200:
                    break
                screen.blit(s, (WIDTH//2 - s.get_width()//2, y))
                y += s.get_height() + 8
        elif self.page == 2:
            # Advisors page: show each advisor headshot with name and bio beneath
            top_y = 120
            cols = max(1, min(3, len(self.advisor_entries)))
            col_w = (WIDTH - 120) // cols
            # precompute max cell height to avoid overlap
            cell_heights = []
            for entry in self.advisor_entries:
                name_s = fit_pixel_text(entry.get('name', entry.get('role','')), ADVISOR_NAME_SIZE, ADVISOR_NAME_SCALE, col_w - 16, color=(220,220,220))
                bio_surfs = wrap_text_into_surfaces(entry.get('bio',''), OPTIONS_LABEL_SIZE, OPTIONS_LABEL_SCALE, col_w - 16, color=(200,200,200))
                h = 96 + 8 + name_s.get_height() + sum(s.get_height() + 4 for s in bio_surfs) + 12
                cell_heights.append(h)
            cell_h = max(cell_heights) if cell_heights else 160
            rows = (len(self.advisor_entries) + cols - 1) // cols
            for idx, entry in enumerate(self.advisor_entries):
                row = idx // cols
                col = idx % cols
                x = 60 + col * col_w + (col_w - 96) // 2
                y = top_y + row * cell_h
                # image
                if entry.get('img'):
                    screen.blit(entry['img'], (x, y))
                else:
                    pygame.draw.circle(screen, (80,80,80), (x + 48, y + 48), 48)
                # name and wrapped bio below
                ny = y + 96 + 8
                name_s = fit_pixel_text(entry.get('name', entry.get('role','')), ADVISOR_NAME_SIZE, ADVISOR_NAME_SCALE, col_w - 16, color=(220,220,220))
                screen.blit(name_s, (x + (96 - name_s.get_width())//2, ny))
                ny += name_s.get_height() + 6
                bio_surfs = wrap_text_into_surfaces(entry.get('bio',''), OPTIONS_LABEL_SIZE, OPTIONS_LABEL_SCALE, col_w - 16, color=(200,200,200))
                for bs in bio_surfs:
                    screen.blit(bs, (x + (96 - bs.get_width())//2, ny))
                    ny += bs.get_height() + 4
            # no further text
        else:
            # fallback: draw remaining text lines
            y = 120
            for s in ps[1:]:
                if y > HEIGHT - 200:
                    break
                screen.blit(s, (60, y))
                y += s.get_height() + 8
        # draw navigation
        if self.page >= len(self.pages)-1:
            self.start_btn.draw(screen)
        else:
            self.next_btn.draw(screen)
            if self.page > 0:
                self.back_btn.draw(screen)


# DebateScreen (older personalized variant removed in favor of unified DebateScreen below)


class LoadingScreen:
    def __init__(self, app, duration=1000):
        self.app = app
        self.start = pygame.time.get_ticks()
        self.duration = duration  # ms to show loading
        # attempt to load map image (reuse IntroScreen logic if available)
        self.map_image = None
        try:
            p = os.path.join(IMAGES_DIR, 'aurora_map.png')
            if os.path.exists(p):
                self.map_image = pygame.image.load(p).convert_alpha()
                mw = min(160, self.map_image.get_width())
                mh = int(self.map_image.get_height() * (mw / max(1, self.map_image.get_width())))
                self.map_image = pygame.transform.smoothscale(self.map_image, (mw, mh))
        except Exception:
            self.map_image = None
        self.angle = 0

    def update(self, events, dt):
        # increment rotation
        self.angle = (self.angle + dt * 0.18) % 360
        now = pygame.time.get_ticks()
        if now - self.start >= self.duration:
            # ensure game object exists
            if not self.app.game and AuroraGame:
                try:
                    self.app.game = AuroraGame()
                except Exception:
                    self.app.game = None
            if self.app.game:
                try:
                    self.app.current_screen = GameScreen(self.app)
                except Exception:
                    self.app.current_screen = self.app.title_screen

    def draw(self):
        screen.fill((6,6,8))
        msg = pixel_text(None, OPTIONS_TITLE_SIZE, "Loading...", scale=OPTIONS_TITLE_SCALE, color=(220,220,255))
        screen.blit(msg, (WIDTH//2 - msg.get_width()//2, HEIGHT//2 - 40))
        # draw rotating map at bottom-right
        if self.map_image:
            rot = pygame.transform.rotozoom(self.map_image, self.angle, 1.0)
            mx = WIDTH - 20 - rot.get_width()
            my = HEIGHT - 20 - rot.get_height()
            screen.blit(rot, (mx, my))
        else:
            # fallback spinner
            cx = WIDTH - 60
            cy = HEIGHT - 60
            r = 20
            end_angle = math.radians(self.angle)
            ex = cx + int(math.cos(end_angle) * r)
            ey = cy + int(math.sin(end_angle) * r)
            pygame.draw.circle(screen, (80,80,80), (cx, cy), r, 4)
            pygame.draw.circle(screen, (220,220,220), (ex, ey), 6)


class GameScreen:
    def __init__(self, app):
        self.app = app
        self.game = app.game
        self.current_event = None
        self.current_recommendations = {}
        self.dialogue_full = ""
        self.dialogue_idx = 0
        self.typing = False
        self.typing_speed = 20  # ms per char
        self.time_acc = 0
        self.choice_buttons = []
        # create choice areas
        for i, key in enumerate(["A","B","C"]):
            bx = WIDTH//2 - 220
            by = HEIGHT - 160 + i*56
            self.choice_buttons.append((pygame.Rect(bx, by, 440, 48), key))
        self.debate_screen = None
        # debate offer state shown after dialogue finishes
        self.debate_offered = False
        self.debate_prompt_rect = None
        # ensure we only evaluate debate probability once per event
        self.debate_offer_checked = False
        # Options button in-game (replaces debug Debate button)
        try:
            # set the options screen's previous_screen before switching so Back returns correctly
            self.options_btn = Button((WIDTH-140, 60, 120, 40), "Options",
                                      lambda app=self.app: (setattr(app.options, 'previous_screen', app.current_screen), setattr(app, 'current_screen', app.options)))
        except Exception:
            self.options_btn = None
        # debate blink/animation state
        self.debate_blink_count = 0
        self.last_blink_visible = False
        self.debate_animating = False
        self.debate_animation_start = None
        # quit popup state: list of advisor keys who left and the current modal
        self.pending_quit_keys = []
        self.current_quit_popup = None
        self.new_event()

    def load_portrait(self, adv_key):
        # search IMAGES_DIR for likely headshot filenames (case-insensitive)
        try:
            files = os.listdir(IMAGES_DIR) if os.path.exists(IMAGES_DIR) else []
        except Exception:
            files = []
        files_map = {f.lower(): f for f in files}

        # gather candidate names (lowercase)
        candidates = []
        # advisor key variants
        for ext in ("png", "jpg", "jpeg"):
            candidates.append(f"advisor_{adv_key}_headshot.{ext}")
            candidates.append(f"advisor_{adv_key}.{ext}")

        # try advisor name-based variants (use game metadata if available)
        info = {}
        try:
            info = self.game.advisors.get(adv_key, {}) if self.game else {}
        except Exception:
            info = {}
        name = (info.get('name') or "").strip()
        if name:
            name_lower = name.lower()
            name_underscore = name_lower.replace(' ', '_')
            for ext in ("png", "jpg", "jpeg"):
                candidates.append(f"{name_lower} advisor headshot.{ext}")
                candidates.append(f"{name_lower} headshot.{ext}")
                candidates.append(f"{name_underscore}_advisor_headshot.{ext}")
                candidates.append(f"{name_underscore}_headshot.{ext}")
                candidates.append(f"{name_underscore}.{ext}")

        # include any portrait path specified in game metadata (basename)
        p = info.get('portrait') if isinstance(info, dict) else None
        if p:
            candidates.insert(0, os.path.basename(p).lower())

        # look for a matching file
        for cand in candidates:
            if cand in files_map:
                path = os.path.join(IMAGES_DIR, files_map[cand])
                try:
                    return pygame.image.load(path).convert_alpha()
                except Exception:
                    break

        # fallback: try advisor_{key}.png explicitly and crop to headshot
        default_path = os.path.join(IMAGES_DIR, f"advisor_{adv_key}.png")
        if os.path.exists(default_path):
            try:
                img = pygame.image.load(default_path).convert_alpha()
                try:
                    w, h = img.get_width(), img.get_height()
                    crop_h = int(h * 0.6)
                    crop_h = min(crop_h, w)
                    crop_x = max(0, w//2 - crop_h//2)
                    crop_y = max(0, int(h * 0.06))
                    head = pygame.Surface((crop_h, crop_h), pygame.SRCALPHA)
                    head.blit(img, (0, 0), (crop_x, crop_y, crop_h, crop_h))
                    return head
                except Exception:
                    return img
            except Exception:
                return None

        # try provided portrait path if absolute/relative
        if p:
            try:
                if os.path.exists(p):
                    img = pygame.image.load(p).convert_alpha()
                    try:
                        w, h = img.get_width(), img.get_height()
                        crop_h = int(h * 0.6)
                        crop_h = min(crop_h, w)
                        crop_x = max(0, w//2 - crop_h//2)
                        crop_y = max(0, int(h * 0.06))
                        head = pygame.Surface((crop_h, crop_h), pygame.SRCALPHA)
                        head.blit(img, (0, 0), (crop_x, crop_y, crop_h, crop_h))
                        return head
                    except Exception:
                        return img
            except Exception:
                pass

        return None

    def new_event(self):
        # attempt to generate an event different from recent ones stored on the game
        prev_sig = None
        if self.current_event:
            prev_sig = (self.current_event.get('title','') + '|' + self.current_event.get('description','')).strip()
        chosen = None
        # ensure the game has a persistent seen_event_sigs set to track shown prompts
        try:
            if not hasattr(self.game, 'seen_event_sigs') or not isinstance(self.game.seen_event_sigs, set):
                self.game.seen_event_sigs = set()
        except Exception:
            try:
                self.game.seen_event_sigs = set()
            except Exception:
                pass
        seen = getattr(self.game, 'seen_event_sigs', set())
        # try many times to avoid repeating the same text (higher limit to minimize repeats)
        attempts = 0
        max_attempts = 200
        last_ev = None
        # If the game indicates scripted debates are present, only pick
        # from the game's `event_pool` (these are constructed from
        # assets/debates/*.json). This prevents fallback to generated
        # events or other sources.
        use_only_debates = getattr(self.game, 'only_debates', False)
        while attempts < max_attempts:
            try:
                if use_only_debates:
                    # pick a candidate from the provided event_pool
                    pool = getattr(self.game, 'event_pool', []) or []
                    if not pool:
                        ev = None
                    else:
                        ev = random.choice(pool)
                else:
                    ev = self.game.generate_dynamic_event()
            except Exception:
                ev = None
            if not ev:
                attempts += 1
                last_ev = ev
                continue
            last_ev = ev
            sig = (ev.get('title','') + '|' + ev.get('description','')).strip()
            # accept if different from the immediate previous and not seen before
            if sig and sig != prev_sig and sig not in seen:
                chosen = ev
                break
            attempts += 1
        # fallback: if game exposes a candidate pool, try to pick an unseen from it
        if not chosen:
            try:
                candidates = getattr(self.game, 'list_candidate_events', None)
                if callable(candidates):
                    for ev in candidates():
                        sig = (ev.get('title','') + '|' + ev.get('description','')).strip()
                        if sig and sig != prev_sig and sig not in seen:
                            chosen = ev
                            break
            except Exception:
                pass
        if not chosen:
            # fallback: accept last generated event (may be duplicate if unavoidable)
            chosen = last_ev
        self.current_event = chosen
        # remember signature on the game object to persist across save/load
        try:
            if self.current_event:
                def _normalize_sig_local(e):
                    s = (e.get('title','') + ' ' + e.get('description','')).lower()
                    import re
                    s = re.sub(r"\b(update|breaking|urgent|new|developing)\b:?", "", s)
                    s = re.sub(r"\b(stability issue|event|issue)\b", "", s)
                    for suf in [" — public concerned", " — experts weigh in", " — overnight reports", " — experts divided", " — urgent"]:
                        if suf in s:
                            s = s.replace(suf, '')
                    s = re.sub(r"\(variant \d+\)", "", s)
                    s = re.sub(r"[\-—:(),]", " ", s)
                    s = re.sub(r"\s+", " ", s).strip()
                    return s
                sig_to_add = _normalize_sig_local(self.current_event)
                if sig_to_add:
                    self.game.seen_event_sigs.add(sig_to_add)
        except Exception:
            pass
        self.current_recommendations = self.game.get_advisor_recommendations(self.current_event)
        # dialogue text excludes the Year header (drawn separately)
        self.dialogue_full = f"{self.current_event['title']}\n{self.current_event['description']}"
        self.dialogue_idx = 0
        self.typing = True
        self.time_acc = 0
        # reset debate offer for new prompt
        self.debate_offered = False
        self.debate_prompt_rect = None
        # ensure we only evaluate debate probability once per event
        self.debate_offer_checked = False

    def handle_choice(self, key):
        if self.typing:
            return
        _, effects = self.current_event['choices'][key]
        self.game.apply_effects(effects)
        # compute agreements and apply trust changes using actual event choices
        agreements, left = self.game.adjust_trust_after_choice(key, self.current_recommendations, self.current_event.get('choices'))
        # Extra penalty for obviously wrong or do-nothing choices:
        # If the chosen option strongly harms an advisor's preferred stat,
        # apply an additional trust penalty so the advisor's trust drops noticeably.
        try:
            # detect obvious "do nothing"/no-action labels in the chosen text
            chosen_text = self.current_event['choices'][key][0].lower() if key in self.current_event.get('choices', {}) else ''
            do_nothing_keywords = ('do nothing', 'no action', 'stand pat', 'status quo', 'maintain current', 'do-nothing')
            is_do_nothing = any(k in chosen_text for k in do_nothing_keywords)
            # determine a conservative threshold for "strong harm"
            impact_threshold = 6
            extra_penalty_base = 6
            # For each advisor, if their preferred stat is strongly harmed by this choice,
            # subtract extra trust (clamped 0..100). If the choice is an explicit do-nothing
            # and that choice yields net negative effects for an advisor, penalize more.
            advisors_iter = list(self.game.advisors.items()) if getattr(self.game, 'advisors', None) else []
            for adv_key, adv_info in advisors_iter:
                try:
                    pref_stat = None
                    if hasattr(self.game, 'advisor_prefs') and isinstance(self.game.advisor_prefs, dict):
                        pref_stat = self.game.advisor_prefs.get(adv_key)
                    impact = 0
                    if pref_stat and isinstance(effects, dict):
                        impact = effects.get(pref_stat, 0)
                    else:
                        # fallback: measure overall negative impact (sum of negative values)
                        if isinstance(effects, dict):
                            impact = sum(v for v in effects.values() if v < 0)
                    # if impact is strongly negative for this advisor, apply extra penalty
                    if impact <= -impact_threshold or (is_do_nothing and impact < 0):
                        penalty = extra_penalty_base + int(min(20, abs(impact)))
                        if is_do_nothing:
                            penalty = max(penalty, extra_penalty_base + 6)
                        # apply penalty directly to advisor trust, if present
                        try:
                            if adv_key in self.game.advisors and isinstance(self.game.advisors[adv_key], dict):
                                cur = int(self.game.advisors[adv_key].get('trust', 0))
                                new = max(0, cur - penalty)
                                self.game.advisors[adv_key]['trust'] = new
                        except Exception:
                            pass
                except Exception:
                    continue
        except Exception:
            pass
        # If any advisors left, show a modal quit popup sequence first
        if left:
            try:
                self.pending_quit_keys = list(left)
                # create first popup
                first = self.pending_quit_keys.pop(0)
                self.current_quit_popup = QuitPopup(self.app, self.game, first)
            except Exception:
                self.pending_quit_keys = []
                self.current_quit_popup = None
            return

        # Decide if the game ended; otherwise advance to next year/event
        if self.game.collapsed() or self.game.year >= self.game.max_years:
            # switch to end screen to show outcome
            try:
                self.app.current_screen = EndScreen(self.app, self.game)
            except Exception:
                self.app.current_screen = self.app.title_screen
            return
        else:
            self.game.year += 1
            self.new_event()

    def update(self, events, dt):
        # If a quit popup is active, forward input to it and block normal updates
        try:
            if getattr(self, 'current_quit_popup', None):
                self.current_quit_popup.update(events, dt)
                if getattr(self.current_quit_popup, 'closed', False):
                    # popup dismissed: show next or resume game
                    self.current_quit_popup = None
                    try:
                        if getattr(self, 'pending_quit_keys', None):
                            next_key = self.pending_quit_keys.pop(0)
                            self.current_quit_popup = QuitPopup(self.app, self.game, next_key)
                        else:
                            if self.game.collapsed() or self.game.year >= self.game.max_years:
                                try:
                                    self.app.current_screen = EndScreen(self.app, self.game)
                                except Exception:
                                    self.app.current_screen = self.app.title_screen
                                return
                            else:
                                self.game.year += 1
                                self.new_event()
                    except Exception:
                        self.current_quit_popup = None
                return
        except Exception:
            pass

        # typing progression
        if self.typing:
            self.time_acc += dt
            while self.time_acc >= self.typing_speed:
                self.time_acc -= self.typing_speed
                if self.dialogue_idx < len(self.dialogue_full):
                    self.dialogue_idx += 1
                else:
                    self.typing = False
                    break

        # when typing finishes, offer a debate based on configured probability
        # Evaluate probability only once per event (not every frame).
        if not self.typing and not self.debate_offered and not getattr(self, 'debate_offer_checked', False):
            try:
                # allow forcing debate every prompt
                if getattr(self.app, 'always_offer_debate', False):
                    self.debate_offered = True
                    try:
                        self.debate_offer_checked = True
                    except Exception:
                        pass
                    return

                prob = getattr(self.app, 'debate_prob', 0.0)
                # normalize probability: accept floats 0..1, but also allow 1..100 as percent
                try:
                    prob = float(prob)
                except Exception:
                    prob = 0.0
                if prob > 1.0 and prob <= 100.0:
                    prob = prob / 100.0
                prob = max(0.0, min(1.0, prob))

                year = getattr(self.game, 'year', None)
                # ensure the game stores a persistent set of offered years
                if not hasattr(self.game, 'debates_offered_years') or not isinstance(self.game.debates_offered_years, set):
                    try:
                        self.game.debates_offered_years = set()
                    except Exception:
                        pass
                offered_set = getattr(self.game, 'debates_offered_years', set())
                already_offered = (year in offered_set) if year is not None else False
                if not already_offered and prob > 0 and random.random() < prob:
                    # mark offered; actual prompt is drawn in draw()
                    self.debate_offered = True
                # mark that we've checked for this event so we don't sample again
                try:
                    self.debate_offer_checked = True
                except Exception:
                    pass
            except Exception:
                pass

        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        # If a debate is currently offered, block answer clicks so the player
        # cannot advance the year by selecting an answer while the prompt is active.
        if mouse_up and not self.typing and not getattr(self, 'debate_offered', False):
            for rect, k in self.choice_buttons:
                if rect.collidepoint(mouse_pos):
                    if click_sfx:
                        click_sfx.play()
                    self.handle_choice(k)
        # If a debate prompt is visible, require the player to click it (or press Enter/Space)
        try:
            if not self.typing and getattr(self, 'debate_offered', False):
                # Auto-start debate after three visible blink pulses to match
                # the requested UX. Also allow clicking the prompt or pressing
                # Enter/Space to start immediately.
                if getattr(self, 'debate_blink_count', 0) >= 3 and not getattr(self, 'debate_animating', False):
                    self.debate_animating = True
                    self.debate_animation_start = pygame.time.get_ticks()
                # mouse click on the prompt rectangle still starts the debate early
                if mouse_up:
                    rect = getattr(self, 'debate_prompt_rect', None)
                    if rect is None:
                        try:
                            db_s = pixel_text(None, OPTIONS_TITLE_SIZE, "DEBATE", scale=OPTIONS_TITLE_SCALE, color=(240,160,120))
                            rx = WIDTH//2 - db_s.get_width()//2
                            ry = HEIGHT//2 - db_s.get_height()//2
                            rect = pygame.Rect(rx-12, ry-8, db_s.get_width()+24, db_s.get_height()+16)
                        except Exception:
                            rect = pygame.Rect(WIDTH//2-80, HEIGHT//2-20, 160, 40)
                    if rect and rect.collidepoint(mouse_pos):
                        self.debate_animating = True
                        self.debate_animation_start = pygame.time.get_ticks()
                        try:
                            print(f"debate: user clicked prompt, animating start at {self.debate_animation_start}", file=sys.stderr)
                        except Exception:
                            pass
                # keyboard start (Enter/Space)
                for e in events:
                    if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        self.debate_animating = True
                        self.debate_animation_start = pygame.time.get_ticks()
                        break
        except Exception:
            pass
        # update options button
        if getattr(self, 'options_btn', None):
            self.options_btn.update(mouse_pos, mouse_up)

    def draw_advisors(self):
        x = 32
        # place advisors between the dialogue box and the choice buttons
        dialog_top = 120
        dialog_h = 200
        dialog_bottom = dialog_top + dialog_h
        top_y = dialog_bottom + 12
        buttons_top = HEIGHT - 160
        # compute available height and number of active advisors
        active_advisors = [k for k, v in self.game.advisors.items() if v.get('active', True)]
        n = max(1, len(active_advisors))
        available_h = max(80, buttons_top - top_y - 20)
        # portrait size scaled to fit; allow larger headshots for clarity (clamp between 40 and 96)
        portrait_size = max(40, min(96, available_h // n - 10))
        name_x_offset = portrait_size + 8
        max_text_width = WIDTH - (x + name_x_offset) - 40
        # precompute choices from current_event to avoid NameError during rendering
        choices = self.current_event.get('choices', {}) if getattr(self, 'current_event', None) else {}
        y = top_y
        for key, info in self.game.advisors.items():
            if not info.get('active', True):
                continue
            # portrait
            img = self.load_portrait(key)
            if img:
                s = portrait_size
                # draw circular background for consistent framing
                center = (x + s//2, y + s//2)
                pygame.draw.circle(screen, (60,60,70), center, s//2)
                # scale and mask image to a circle
                try:
                    img_surf = pygame.transform.smoothscale(img, (s, s)).convert_alpha()
                    mask = pygame.Surface((s, s), pygame.SRCALPHA)
                    pygame.draw.circle(mask, (255,255,255,255), (s//2, s//2), s//2)
                    img_surf.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(img_surf, (x, y))
                except Exception:
                    # fallback to simple blit if masking fails
                    surf = pygame.transform.scale(img, (s, s))
                    screen.blit(surf, (x, y))
                # thin outline
                pygame.draw.circle(screen, (220,220,220), center, s//2, 2)
            else:
                # circular placeholder with initials
                s = portrait_size
                center = (x + s//2, y + s//2)
                pygame.draw.circle(screen, (80,80,80), center, s//2)
                initials = "".join([w[0] for w in info.get('name','?').split()[:2]]).upper()
                init_surf = fit_pixel_text(initials, ADVISOR_NAME_SIZE, ADVISOR_NAME_SCALE, s-8, color=(220,220,220))
                screen.blit(init_surf, (x + (s - init_surf.get_width())//2, y + (s - init_surf.get_height())//2))
            # name and predicted trust
            rec = self.current_recommendations.get(key, {})
            t = info.get('trust', 0)
            name_surf = fit_pixel_text(f"{info['name']} ({t})", ADVISOR_NAME_SIZE, ADVISOR_NAME_SCALE, max_text_width, color=(220,220,220))
            screen.blit(name_surf, (x+name_x_offset, y+6))
            # predicted deltas display
            pref_stat = self.game.advisor_prefs.get(key)
            deltas = {}
            for ch, (desc, effects) in choices.items():
                score_for_choice = 0
                if pref_stat:
                    score_for_choice = effects.get(pref_stat, 0)
                score_for_choice += sum(v for v in effects.values()) * 0.01
                delta = 3 if (rec.get('choice') and ch == rec.get('choice')) else -2
                if score_for_choice < 0:
                    delta += -3
                deltas[ch] = int(delta)
            parts = [f"{k}:{d:+d}->{max(0,min(100,t+d))}" for k,d in deltas.items()]
            dline = " ".join(parts)
            d_surf = fit_pixel_text(dline, ADVISOR_DELTA_SIZE, ADVISOR_DELTA_SCALE, max_text_width, color=(180,200,200))
            screen.blit(d_surf, (x+name_x_offset, y+28))
            y += portrait_size + 12

    def draw(self):
        # background
        for y in range(0, HEIGHT, 8):
            t = y / HEIGHT
            r = int(BG_TOP[0] * (1-t) + BG_BOTTOM[0] * t)
            g = int(BG_TOP[1] * (1-t) + BG_BOTTOM[1] * t)
            b = int(BG_TOP[2] * (1-t) + BG_BOTTOM[2] * t)
            pygame.draw.rect(screen, (r,g,b), (0, y, WIDTH, 8))
        # title
        title_surf = pixel_text(None, GAME_TITLE_SIZE, "AURORA", scale=GAME_TITLE_SCALE, color=(200,240,255))
        screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 12))
        # dialogue box
        pygame.draw.rect(screen, (10,10,14), (220, 120, WIDTH-260, 200), border_radius=8)
        # always show the current year as a small header inside the dialogue box
        # place it at the dialog's top-right with padding so it doesn't crowd body text
        try:
            year_s = fit_pixel_text(f"Year {self.game.year}", DIALOG_SIZE, DIALOG_SCALE, 180, color=(200,220,240))
            dialog_x = 220
            dialog_w = WIDTH - 260
            rx = dialog_x + dialog_w - year_s.get_width() - 12
            ry = 124
            screen.blit(year_s, (rx, ry))
        except Exception:
            pass
        # render wrapped dialogue text to fit inside the box
        dialog_shown = self.dialogue_full[:self.dialogue_idx]
        lines = dialog_shown.split("\n")
        y = 136
        # inner width of dialogue content (dialog rect right - inner x)
        dialog_right = 220 + (WIDTH - 260)
        inner_x = 236
        inner_width = max(80, dialog_right - inner_x - 8)
        for line in lines:
            try:
                surfs = wrap_text_into_surfaces(line, DIALOG_SIZE, DIALOG_SCALE, inner_width, color=(210,230,240))
            except Exception:
                surfs = [pixel_text(None, DIALOG_SIZE, line, scale=DIALOG_SCALE, color=(210,230,240))]
            for surf in surfs:
                screen.blit(surf, (inner_x, y))
                y += surf.get_height() + 6

        # if debate was offered, show a blinking 'DEBATE' prompt in the center
        self.debate_prompt_rect = None
        if not self.typing and getattr(self, 'debate_offered', False):
            now = pygame.time.get_ticks()
            visible = ((now // 500) % 2 == 0)
            if visible:
                db_s = pixel_text(None, OPTIONS_TITLE_SIZE, "DEBATE", scale=OPTIONS_TITLE_SCALE, color=(240,160,120))
                rx = WIDTH//2 - db_s.get_width()//2
                ry = HEIGHT//2 - db_s.get_height()//2
                # draw a subtle background to make it noticeable
                br = pygame.Rect(rx-12, ry-8, db_s.get_width()+24, db_s.get_height()+16)
                pygame.draw.rect(screen, (30,18,18), br, border_radius=8)
                screen.blit(db_s, (rx, ry))
                self.debate_prompt_rect = br
            # count visible pulses; when visible toggles from False->True increment
            if visible and not self.last_blink_visible:
                self.debate_blink_count += 1
            self.last_blink_visible = visible
            # blinking indicates availability; starting the debate now requires
            # an explicit click or keypress (handled in update()) to avoid
            # accidental activation from mouse motion.

        # if animating, draw a simple fade-in overlay and start debate when complete
        if getattr(self, 'debate_animating', False):
            now = pygame.time.get_ticks()
            start = self.debate_animation_start or now
            dur = 700
            t = min(1.0, (now - start) / float(dur))
            # fade to black with a growing vertical curtain effect
            alpha = int(200 * t)
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0,0,0,alpha))
            screen.blit(overlay, (0,0))
            if t >= 1.0:
                # clear offer state and transition to DebateScreen
                try:
                    self.start_debate()
                except Exception:
                    pass
                return

        # draw advisors list
        self.draw_advisors()

        # choices
        for rect, k in self.choice_buttons:
            color = (70,110,90) if not self.typing else (50,50,50)
            pygame.draw.rect(screen, color, rect, border_radius=8)
            choice_text = f"{k}) {self.current_event['choices'][k][0]}"
            text_surf = fit_pixel_text(choice_text, BUTTON_SIZE, BUTTON_SCALE, rect.width - 16, color=(230,230,230))
            screen.blit(text_surf, (rect.x + 8, rect.y + (rect.height - text_surf.get_height())//2))
        # debug debate button (or in-game trigger)
        if getattr(self, 'debate_btn', None):
            try:
                self.debate_btn.draw(screen)
            except Exception:
                pass
        # options button (in-game)
        if getattr(self, 'options_btn', None):
            try:
                self.options_btn.draw(screen)
            except Exception:
                pass

        # draw quit popup on top if active
        try:
            if getattr(self, 'current_quit_popup', None):
                self.current_quit_popup.draw()
        except Exception:
            pass

    def start_debate(self):
        # start a debate using game state; avoid repetition via game.debate_history
        try:
            print("start_debate: invoked", file=sys.stderr)
        except Exception:
            pass
        if not self.game:
            return
        if not hasattr(self.game, 'debate_history'):
            try:
                self.game.debate_history = set()
            except Exception:
                self.game.debate_history = set()
        # pick two distinct active advisors, preferring those who favor different choices
        try:
            active = [k for k,v in self.game.advisors.items() if v.get('active', True)]
        except Exception:
            active = []
        # fallback: if fewer than two active advisors, try to use any advisors available
        if len(active) < 2:
            try:
                all_keys = list(self.game.advisors.keys()) if getattr(self.game, 'advisors', None) else []
            except Exception:
                all_keys = []
            if len(all_keys) >= 2:
                active = all_keys[:2]
            else:
                # no advisors available — log and abort gracefully
                try:
                    print("start_debate: insufficient advisors to run debate", file=sys.stderr)
                except Exception:
                    pass
                return
        # compute each advisor's per-choice impact for their preferred stat (or fallback)
        best_choice = {}
        choices = self.current_event.get('choices', {}) if self.current_event else {}
        choice_impacts = {}
        try:
            for k in active:
                choice_impacts[k] = {}
                pref_stat = None
                if hasattr(self.game, 'advisor_prefs') and isinstance(self.game.advisor_prefs, dict):
                    pref_stat = self.game.advisor_prefs.get(k)
                best = None
                best_score = -9e9
                for ch, data in choices.items():
                    try:
                        effects = data[1] if isinstance(data, (list, tuple)) and len(data) > 1 else {}
                    except Exception:
                        effects = {}
                    # primary impact: effect on advisor's preferred stat, fallback to net negative sum
                    impact = 0
                    if pref_stat and isinstance(effects, dict):
                        impact = effects.get(pref_stat, 0)
                    else:
                        impact = sum(v for v in effects.values()) if isinstance(effects, dict) else 0
                    choice_impacts[k][ch] = impact
                    # keep same scoring for best_choice fallback (prefer larger positive impact)
                    score = impact
                    if score > best_score:
                        best_score = score
                        best = ch
                best_choice[k] = best
        except Exception:
            # if anything goes wrong, fall back to simpler best_choice mapping
            best_choice = {}
            for k in active:
                best_choice[k] = None

        # prefer pairs where advisors have *opposing high-stakes* impacts
        pairs = [(a,b) for i,a in enumerate(active) for b in active[i+1:]]
        random.shuffle(pairs)
        chosen = None
        # If the app requests a fixed debate pair, and both advisors exist and are active,
        # use that pair deterministically instead of the selection heuristics.
        try:
            if getattr(self.app, 'force_fixed_debate', False) and getattr(self.app, 'fixed_debate_pair', None):
                p = tuple(self.app.fixed_debate_pair)
                if isinstance(p, (list, tuple)) and len(p) == 2:
                    a_key, b_key = p[0], p[1]
                    if a_key in active and b_key in active:
                        chosen = (a_key, b_key)
        except Exception:
            pass
        # threshold for "high stakes" (can be tuned)
        impact_threshold = 8
        for a,b in pairs:
            try:
                a_choice = best_choice.get(a)
                b_choice = best_choice.get(b)
                if not a_choice or not b_choice:
                    continue
                a_imp_for_a = choice_impacts.get(a, {}).get(a_choice, 0)
                a_imp_for_b = choice_impacts.get(b, {}).get(a_choice, 0)
                b_imp_for_b = choice_impacts.get(b, {}).get(b_choice, 0)
                b_imp_for_a = choice_impacts.get(a, {}).get(b_choice, 0)
                # check that each advisor strongly benefits from their choice
                # and the opponent would strongly lose from that same choice
                if (a_imp_for_a >= impact_threshold and a_imp_for_b <= -impact_threshold and
                    b_imp_for_b >= impact_threshold and b_imp_for_a <= -impact_threshold):
                    sig = f"{a}|{b}"
                    rsig = f"{b}|{a}"
                    if sig not in self.game.debate_history and rsig not in self.game.debate_history:
                        chosen = (a,b)
                        break
            except Exception:
                continue
        # fallback to previous logic (prefer different best_choice)
        if not chosen:
            for a,b in pairs:
                if best_choice.get(a) and best_choice.get(b) and best_choice.get(a) != best_choice.get(b):
                    sig = f"{a}|{b}"
                    rsig = f"{b}|{a}"
                    if sig not in self.game.debate_history and rsig not in self.game.debate_history:
                        chosen = (a,b)
                        break
        if not chosen:
            # fallback to any non-recent pair
            for a,b in pairs:
                sig = f"{a}|{b}"
                rsig = f"{b}|{a}"
                if sig not in self.game.debate_history and rsig not in self.game.debate_history:
                    chosen = (a,b)
                    break
        if not chosen and pairs:
            chosen = pairs[0]
        a,b = chosen
        # record debate signature
        try:
            self.game.debate_history.add(f"{a}|{b}")
        except Exception:
            pass
        # determine the choice each advisor will argue for
        a_choice = best_choice.get(a) or (list(choices.keys())[0] if choices else None)
        b_choice = best_choice.get(b) or (list(choices.keys())[0] if choices else None)
        # record that a debate occurred this year (so it won't repeat for this event/year)
        try:
            y = getattr(self.game, 'year', None)
            if y is not None:
                if hasattr(self.game, 'debates_offered_years'):
                    self.game.debates_offered_years.add(y)
                else:
                    self.game.debates_offered_years = {y}
        except Exception:
            pass
        # clear offered state and open DebateScreen with event context
        # clear offered state and animation flags, then open DebateScreen with event context
        try:
            self.debate_offered = False
            self.debate_prompt_rect = None
            # clear animation so returning to this GameScreen won't immediately re-trigger
            self.debate_animating = False
            self.debate_animation_start = None
            self.debate_blink_count = 0
            self.last_blink_visible = False
        except Exception:
            pass
        try:
            self.app.current_screen = DebateScreen(self.app, self.game, a, b, event=self.current_event, a_choice=a_choice, b_choice=b_choice)
        except Exception as e:
            # log error to help debugging — don't crash the game loop
            try:
                print(f"Failed to open DebateScreen: {e}", file=sys.stderr)
            except Exception:
                pass


class App:
    def __init__(self):
        self.game = AuroraGame() if AuroraGame else None
        self.title_screen = None
        self.options = OptionsScreen(self)
        self.intro = IntroScreen(self)
        self.sources = SourcesScreen(self)
        self.current_screen = None
        # probability (0..1) that a debate is offered after an event
        self.debate_prob = 0.25
        # Optional: force debates between a fixed pair of advisors when enabled
        # Set `force_fixed_debate = True` and `fixed_debate_pair = ('economy','rights')`
        # to always use that pair. Leave False/None for automatic pairing.
        self.force_fixed_debate = False
        self.fixed_debate_pair = None
        # Optional: always offer a debate after every prompt (bypass probability)
        self.always_offer_debate = False
        # Optional: force the game to only show a single debate (script_key)
        # Set to the script key (e.g. 'major_pharmaceutical_recall') to limit
        # the game's events to that single scripted debate. Leave `None` to
        # allow all scripted debates found in `assets/debates/` to be used.
        self.forced_debate_key = None
        # remember windowed size so we can restore after fullscreen
        self.windowed_size = (WIDTH, HEIGHT)
        self.fullscreen = False
        # create title screen after app exists
        self.title_screen = TitleScreen(screen, self)
        self.current_screen = self.title_screen

    def run(self):
        running = True
        while running:
            dt = clock.tick(FPS)
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    # toggle fullscreen: F11 or Alt+Enter
                    try:
                        if event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_ALT)):
                            self.toggle_fullscreen()
                    except Exception:
                        pass
            # support screens that have update(events, dt) or update(events)
            try:
                self.current_screen.update(events, dt)
            except TypeError:
                self.current_screen.update(events)
            try:
                self.current_screen.draw()
            except Exception:
                pass
            pygame.display.flip()
        pygame.quit()

    def toggle_fullscreen(self):
        """Toggle between windowed and fullscreen modes and update global screen."""
        global screen, WIDTH, HEIGHT
        try:
            if not self.fullscreen:
                info = pygame.display.Info()
                WIDTH, HEIGHT = info.current_w, info.current_h
                screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
                self.fullscreen = True
            else:
                WIDTH, HEIGHT = self.windowed_size
                screen = pygame.display.set_mode((WIDTH, HEIGHT))
                self.fullscreen = False
            # update any screen references stored on screens
            if hasattr(self, 'title_screen') and self.title_screen:
                try:
                    self.title_screen.screen = screen
                except Exception:
                    pass
        except Exception:
            pass


class TitleScreen:
    def __init__(self, screen, app):
        self.screen = screen
        self.app = app
        self.buttons = []
        # sample actions (Start, Intro, Options, Sources, Quit)
        # position buttons so title/subtitle remain visible but not off-screen
        start_y = HEIGHT//2 - 40
        gap = 72
        self.buttons.append(Button((WIDTH//2 - 160, start_y + 0*gap, 320, 64), "Start Game", self.start_game))
        self.buttons.append(Button((WIDTH//2 - 160, start_y + 1*gap, 320, 64), "Options", self.open_options))
        self.buttons.append(Button((WIDTH//2 - 160, start_y + 2*gap, 320, 64), "Sources", self.open_sources))
        self.buttons.append(Button((WIDTH//2 - 160, start_y + 3*gap, 320, 64), "Quit", self.quit_game))
        self.bg_offset = 0
        self.error_msg = None

    def start_game(self):
        # switch to GameScreen, but guard if game logic is missing
        if not self.app.game:
            # try to instantiate if the AuroraGame class is available
            if AuroraGame:
                try:
                    self.app.game = AuroraGame()
                except Exception:
                    self.app.game = None
            else:
                self.error_msg = "Game logic not found (aurora_gui.py)"
                return
        # rebuild intro pages now that game metadata may be available
        try:
            if hasattr(self.app, 'intro') and self.app.intro:
                try:
                    self.app.intro.build_pages()
                except Exception:
                    pass
        except Exception:
            pass
        if self.app.game:
            # diagnostic: report whether scripted debates were loaded and pool size
            try:
                only = getattr(self.app.game, 'only_debates', False)
                pool = getattr(self.app.game, 'event_pool', None)
                cnt = len(pool) if isinstance(pool, (list, tuple)) else 0
                print(f"[debug] only_debates={only}, event_pool_size={cnt}", file=sys.stderr)
                if cnt:
                    try:
                        sample_titles = [e.get('title') for e in (pool[:5] if isinstance(pool, list) else [])]
                        print(f"[debug] sample event titles: {sample_titles}", file=sys.stderr)
                    except Exception:
                        pass
            except Exception:
                pass
            # If a forced debate key is set on the app, filter the game's event_pool
            try:
                forced = getattr(self.app, 'forced_debate_key', None)
                if forced:
                    pool = getattr(self.app.game, 'event_pool', []) or []
                    def matches_key(e, key):
                        try:
                            if isinstance(e, dict) and e.get('script_key') == key:
                                return True
                            # also accept normalized title forms
                            t = (e.get('title') or '').strip().lower()
                            nk = re.sub(r"\s+", "_", t)
                            nk = re.sub(r"[^a-z0-9_]+", "", nk)
                            return nk == key
                        except Exception:
                            return False
                    filtered = [e for e in pool if matches_key(e, forced)]
                    if filtered:
                        try:
                            self.app.game.event_pool = filtered
                            self.app.game.only_debates = True
                            print(f"[debug] forced_debate_key={forced} applied, pool_size={len(filtered)}", file=sys.stderr)
                        except Exception:
                            pass
                    else:
                        try:
                            print(f"[debug] forced_debate_key={forced} set but no matching event found in event_pool", file=sys.stderr)
                        except Exception:
                            pass
            except Exception:
                pass
            # open the IntroScreen first instead of jumping straight into the game
            self.app.current_screen = self.app.intro
        else:
            self.error_msg = "Failed to initialize game logic"

    def open_options(self):
        try:
            # record opener so Options can return to the right screen
            self.app.options.previous_screen = self.app.current_screen
        except Exception:
            pass
        self.app.current_screen = self.app.options

    def open_intro(self):
        self.app.current_screen = self.app.intro

    def open_sources(self):
        self.app.current_screen = self.app.sources

    def quit_game(self):
        pygame.quit()
        sys.exit()

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        for b in self.buttons:
            b.update(mouse_pos, mouse_up)
        self.bg_offset += 1

    def draw_background(self):
        # draw a simple pixelated gradient background
        for y in range(0, HEIGHT, 8):
            t = y / HEIGHT
            r = int(BG_TOP[0] * (1-t) + BG_BOTTOM[0] * t)
            g = int(BG_TOP[1] * (1-t) + BG_BOTTOM[1] * t)
            b = int(BG_TOP[2] * (1-t) + BG_BOTTOM[2] * t)
            pygame.draw.rect(self.screen, (r,g,b), (0, y, WIDTH, 8))
        # simple moving stars for parallax
        for i in range(50):
            x = (i * 47 + self.bg_offset) % WIDTH
            y = (i * 31 + (self.bg_offset//2)) % HEIGHT
            pygame.draw.rect(self.screen, (255,255,255), (x, y, 2, 2))

    def draw_title(self):
        title_surf = pixel_text(None, TITLE_SIZE, "AURORA", scale=TITLE_SCALE, color=(200,240,255))
        sub_surf = pixel_text(None, SUBTITLE_SIZE, "Build the Perfect Society", scale=SUBTITLE_SCALE, color=(170,200,220))
        self.screen.blit(title_surf, (WIDTH//2 - title_surf.get_width()//2, 80))
        self.screen.blit(sub_surf, (WIDTH//2 - sub_surf.get_width()//2, 170))

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        for b in self.buttons:
            b.update(mouse_pos, mouse_up)
        self.bg_offset += 1

    def draw(self):
        self.draw_background()
        self.draw_title()
        for b in self.buttons:
            b.draw(self.screen)
        # transient error message (displayed when Start fails)
        if getattr(self, 'error_msg', None):
            em = pixel_text(None, OPTIONS_LABEL_SIZE, self.error_msg, scale=OPTIONS_LABEL_SCALE, color=(240,160,160))
            self.screen.blit(em, (WIDTH//2 - em.get_width()//2, HEIGHT//2 + 140))


class DebateScreen:
    """Minimal Debate player that only presents scripted debates from assets/debates/.
    This class intentionally avoids any dynamic debate generation — if no
    scripted file is found for the current event, it shows a short message
    and returns to the previous screen.
    """
    def __init__(self, app, game, adv_a_key=None, adv_b_key=None, event=None, a_choice=None, b_choice=None):
        self.app = app
        self.game = game
        self.previous_screen = getattr(app, 'current_screen', None)
        self.event = event or {}
        self.idx = 0
        self.ignore_mouse_until = pygame.time.get_ticks() + 200

        # Load script strictly via loader (which reads only assets/debates/)
        try:
            script = load_debate_script(game, self.event)
        except Exception:
            script = None

        if not script or not isinstance(script, dict) or not script.get('turns'):
            # No scripted debate available — show a brief message and provide Return
            self.turns = [("system", "No scripted debate found in assets/debates/.")]
            self.has_script = False
        else:
            self.has_script = True
            try:
                self.turns = [(t.get('speaker') or 'system', t.get('text') or '') for t in script.get('turns') if isinstance(t, dict) and t.get('text')]
            except Exception:
                self.turns = []

        # identify unique speakers (preserve order of first appearance)
        # Resolve speaker labels to advisor keys when possible so headshots
        # and display names are sourced from `game.advisors`.
        def resolve_speaker_label(tok):
            if not tok:
                return None
            t = str(tok).strip()
            if not t:
                return None
            # direct key match
            if isinstance(self.game, object) and getattr(self.game, 'advisors', None):
                if t in self.game.advisors:
                    return t
                tl = t.lower()
                # try matching against advisor display names or normalized forms
                for k, info in self.game.advisors.items():
                    name = (info.get('name') or '').lower()
                    if not name:
                        continue
                    if tl == name or tl == k or tl == k.replace('_', ''):
                        return k
                    if tl in name or name in tl:
                        return k
                    # normalized title match (e.g., 'economy advisor' -> 'economy')
                    nk = re.sub(r"[^a-z0-9]+", "", tl)
                    if nk == re.sub(r"[^a-z0-9]+", "", k.lower()):
                        return k
            return t

        seen = []
        for s, _ in self.turns:
            rs = resolve_speaker_label(s)
            if rs and rs not in seen and rs != 'system':
                seen.append(rs)
        self.speakers = seen

        # load speaker portraits (if available) and names
        self.speaker_images = {}
        self.speaker_names = {}
        self.speaker_resolved = {}
        self.speaker_loaded = {}
        for s in self.speakers:
            info = self.game.advisors.get(s, {}) if getattr(self.game, 'advisors', None) else {}
            pname = info.get('name') or s
            self.speaker_names[s] = pname
            portrait = info.get('portrait') if isinstance(info.get('portrait'), str) else None
            img = None
            resolved = None
            # deterministic candidate list (try these in order)
            candidates = []
            if portrait:
                candidates.append(portrait)
                candidates.append(os.path.join(IMAGES_DIR, os.path.basename(portrait)))
            candidates.append(os.path.join(IMAGES_DIR, f"advisor_{s}.png"))
            candidates.append(os.path.join(IMAGES_DIR, f"advisor_{s}.jpg"))
            if pname:
                name_tokens = [t for t in re.split(r"\W+", pname.lower()) if t]
                if name_tokens:
                    joined = " ".join(name_tokens)
                    candidates.append(os.path.join(IMAGES_DIR, joined + " advisor headshot.png"))
                    candidates.append(os.path.join(IMAGES_DIR, joined + " headshot.png"))
                    candidates.append(os.path.join(IMAGES_DIR, joined.replace(' ', '_') + ".png"))
            try:
                if os.path.isdir(IMAGES_DIR):
                    for fn in os.listdir(IMAGES_DIR):
                        if s.lower() in fn.lower():
                            candidates.append(os.path.join(IMAGES_DIR, fn))
            except Exception:
                pass

            tried = set()
            for cand in candidates:
                if not cand or cand in tried:
                    continue
                tried.add(cand)
                try:
                    exists = os.path.exists(cand)
                except Exception:
                    exists = False
                try:
                    print(f"[debug] Trying portrait candidate for {s}: {cand!r} exists={exists}", file=sys.stderr)
                except Exception:
                    pass
                if exists:
                    try:
                        img = pygame.image.load(cand).convert_alpha()
                        resolved = cand
                        break
                    except Exception as e:
                        try:
                            print(f"[debug] Failed to load image {cand!r}: {e}", file=sys.stderr)
                        except Exception:
                            pass
                        img = None
            # create a visible placeholder when no image found so UI shows an avatar
            if not img:
                try:
                    # placeholder size; pick reasonable default
                    pw = min(96, max(48, WIDTH//10))
                    ph = pw
                    surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
                    # color by advisor key hash for variety
                    h = abs(hash(s)) % 255
                    col = ((100 + h) % 255, (160 + h*2) % 255, (200 + h*3) % 255)
                    surf.fill(col)
                    # initials
                    label = ''.join([w[0].upper() for w in (pname or s).split() if w])[:2]
                    try:
                        lab = pixel_text(None, ADVISOR_NAME_SIZE, label, scale=max(1, ADVISOR_NAME_SCALE), color=(8,8,8))
                        surf.blit(lab, (pw//2 - lab.get_width()//2, ph//2 - lab.get_height()//2))
                    except Exception:
                        pass
                    img = surf
                except Exception:
                    img = None
            if img:
                # scale to avatar size keeping aspect
                max_w = min(160, WIDTH//6)
                max_h = min(160, HEIGHT//6)
                try:
                    iw, ih = img.get_size()
                    scale = min(max_w / iw, max_h / ih, 1.0)
                    img = pygame.transform.smoothscale(img, (max(32, int(iw*scale)), max(32, int(ih*scale))))
                except Exception:
                    pass
            self.speaker_images[s] = img
            # record resolved path and loaded flag for debugging overlay
            try:
                self.speaker_resolved[s] = resolved
                self.speaker_loaded[s] = bool(img)
            except Exception:
                pass
            try:
                exists = False
                if isinstance(resolved, str):
                    exists = os.path.exists(resolved)
                print(f"[debug] DebateScreen init: speaker={s!r} portrait_field={portrait!r} resolved={resolved!r} exists={exists} loaded={bool(img)}", file=sys.stderr)
            except Exception:
                pass

        # UI controls
        self.back_btn = Button((WIDTH//2 - 160, HEIGHT - 120, 160, 64), "Return", self.close)
        self.next_btn = Button((WIDTH//2 + 8, HEIGHT - 120, 160, 64), "Next", self.next_turn)

        # typing state for progressive text display
        self.typing_speed_cps = 120.0  # chars per second
        self.current_text = ""
        self.target_text = self.turns[0][1] if self.turns else ""
        self.fully_typed = False

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        try:
            if pygame.time.get_ticks() < getattr(self, 'ignore_mouse_until', 0):
                mouse_up = False
        except Exception:
            pass
        self.back_btn.update(mouse_pos, mouse_up)
        self.next_btn.update(mouse_pos, mouse_up)
        # typing progression
        try:
            if not self.fully_typed and self.target_text is not None:
                # dt may be None if called via older update signature
                ms = dt if isinstance(dt, (int, float)) else 16
                add = int((ms/1000.0) * self.typing_speed_cps)
                if add <= 0:
                    add = 1
                if len(self.current_text) < len(self.target_text):
                    new_len = min(len(self.target_text), len(self.current_text) + add)
                    self.current_text = self.target_text[:new_len]
                    if len(self.current_text) >= len(self.target_text):
                        self.fully_typed = True
                else:
                    self.fully_typed = True
        except Exception:
            pass

    def draw(self):
        screen.fill((10,10,12))
        title = pixel_text(None, OPTIONS_TITLE_SIZE, "DEBATE", scale=OPTIONS_TITLE_SCALE, color=(240,220,200))
        screen.blit(title, (WIDTH//2 - title.get_width()//2, 24))

        # draw debate panel
        box_y = 100
        panel_rect = pygame.Rect(80, box_y, WIDTH-160, HEIGHT - 260)
        pygame.draw.rect(screen, (12,12,16), panel_rect, border_radius=8)

        # compute portrait layout extents (don't draw yet) so content can be placed below
        max_bottom = panel_rect.y + 12
        portrait_layout = []
        if self.speakers:
            cols = len(self.speakers)
            imgs = [self.speaker_images.get(s) for s in self.speakers]
            slot_w = (panel_rect.width - 40) // max(1, cols)
            for s_idx, s in enumerate(self.speakers):
                img = imgs[s_idx]
                cx = panel_rect.x + 20 + s_idx * slot_w + slot_w//2
                py = panel_rect.y + 12
                if img:
                    iw, ih = img.get_size()
                    ix = cx - iw//2
                    iy = py
                    nm = self.speaker_names.get(s, s)
                    n_surf = pixel_text(None, ADVISOR_NAME_SIZE, nm, scale=ADVISOR_NAME_SCALE, color=(220,220,220))
                    name_y = iy + ih + 6
                    portrait_layout.append((s, img, ix, iy, iw, ih, name_y, n_surf))
                    max_bottom = max(max_bottom, name_y + n_surf.get_height())
                else:
                    pw = min(96, slot_w-16)
                    ph = pw
                    ix = cx - pw//2
                    iy = py
                    nm = self.speaker_names.get(s, s)
                    n_surf = pixel_text(None, ADVISOR_NAME_SIZE, nm, scale=ADVISOR_NAME_SCALE, color=(220,220,220))
                    name_y = iy + ph + 6
                    portrait_layout.append((s, None, ix, iy, pw, ph, name_y, n_surf))
                    max_bottom = max(max_bottom, name_y + n_surf.get_height())

        # compute content area start below portraits to avoid overlap
        content_y = max(panel_rect.y + 120, max_bottom + 12)

        # show only the current turn's text (one speaker per slide)
        if self.turns and 0 <= self.idx < len(self.turns):
            speaker, full_text = self.turns[self.idx]
            name = 'System' if speaker == 'system' else (self.game.advisors.get(speaker, {}).get('name', speaker))
            # speaker label
            sp_surf = pixel_text(None, OPTIONS_LABEL_SIZE, name + ":", scale=OPTIONS_LABEL_SCALE, color=(240,200,200))
            tx = panel_rect.x + 20
            ty = content_y
            screen.blit(sp_surf, (tx, ty))
            ty += sp_surf.get_height() + 8
            # use progressively-typed current_text when available
            display_text = self.current_text if getattr(self, 'current_text', None) is not None else full_text
            lines = wrap_text_into_surfaces(display_text, DEBATE_BODY_SIZE, DEBATE_BODY_SCALE, panel_rect.width - 80, color=(210,230,240))
            for l in lines:
                screen.blit(l, (tx + 20, ty))
                ty += l.get_height() + 6
        else:
            msg = "No debate turns available."
            lines = wrap_text_into_surfaces(msg, DEBATE_BODY_SIZE, DEBATE_BODY_SCALE, panel_rect.width - 80, color=(210,230,240))
            ty = panel_rect.y + 120
            for l in lines:
                screen.blit(l, (panel_rect.x + 40, ty))
                ty += l.get_height() + 6

        # draw portraits last so they appear in front of the panel
        for entry in portrait_layout:
            s, img, ix, iy, iw, ih, name_y, n_surf = entry
            if img:
                screen.blit(img, (ix, iy))
                rect = pygame.Rect(ix-4, iy-4, iw+8, ih+8)
                cur_speaker = self.turns[self.idx][0] if self.turns else None
                if cur_speaker == s:
                    pygame.draw.rect(screen, (200,220,120), rect, width=3, border_radius=8)
                else:
                    pygame.draw.rect(screen, (60,60,70), rect, width=2, border_radius=8)
                screen.blit(n_surf, (ix + iw//2 - n_surf.get_width()//2, name_y))
            else:
                pygame.draw.rect(screen, (40,40,48), (ix, iy, iw, ih), border_radius=8)
                screen.blit(n_surf, (ix + iw//2 - n_surf.get_width()//2, name_y))
            # (debug overlay removed) — keep stderr logs but do not render file paths

        self.back_btn.draw(screen)
        self.next_btn.draw(screen)

    def next_turn(self):
        # If text is still typing, finish typing first. Otherwise advance.
        try:
            if not getattr(self, 'fully_typed', True):
                # finish current turn immediately
                self.current_text = self.target_text or ''
                self.fully_typed = True
                return
        except Exception:
            pass
        # advance to next turn or close
        if self.idx < len(self.turns) - 1:
            self.idx += 1
            # reset typing state for the new turn
            try:
                self.target_text = self.turns[self.idx][1]
            except Exception:
                self.target_text = ''
            self.current_text = ''
            self.fully_typed = False
        else:
            self.close()

    def close(self):
        prev = getattr(self, 'previous_screen', None)
        try:
            if prev:
                self.app.current_screen = prev
            else:
                self.app.current_screen = self.app.title_screen
        except Exception:
            try:
                self.app.current_screen = self.app.title_screen
            except Exception:
                pass


class EndScreen:
    def __init__(self, app, game):
        self.app = app
        self.game = game
        self.buttons = []
        # Play Again: try to re-init the AuroraGame and restart
        self.buttons.append(Button((WIDTH//2 - 160, HEIGHT - 140, 320, 64), "Play Again", self.play_again))
        self.buttons.append(Button((WIDTH//2 - 160, HEIGHT - 68, 320, 48), "Quit", self.quit_game))
        # compute outcome details and save summary immediately
        try:
            self.summary = self._compute_summary()
            self._save_summary()
        except Exception:
            self.summary = None

    def play_again(self):
        try:
            self.app.game = AuroraGame() if AuroraGame else None
        except Exception:
            self.app.game = None
        if self.app.game:
            self.app.current_screen = GameScreen(self.app)
        else:
            self.app.current_screen = self.app.title_screen

    def quit_game(self):
        pygame.quit()
        sys.exit()

    def update(self, events, dt):
        mouse_pos = pygame.mouse.get_pos()
        mouse_up = any(e.type == pygame.MOUSEBUTTONUP and e.button == 1 for e in events)
        for b in self.buttons:
            b.update(mouse_pos, mouse_up)

    def draw(self):
        screen.fill((6,6,8))
        # adapt layout and font scales for smaller windows so content fits
        scale_factor = min(1.0, HEIGHT / 620.0)
        # apply global EndScreen downscale factor as well
        title_scale = max(1, int(OPTIONS_TITLE_SCALE * scale_factor * ENDING_SCALE_FACTOR))
        label_scale = max(1, int(OPTIONS_LABEL_SCALE * scale_factor * ENDING_SCALE_FACTOR))
        name_max_scale = max(1, int(ADVISOR_NAME_SCALE * scale_factor * ENDING_SCALE_FACTOR))
        # draw header
        title = pixel_text(None, OPTIONS_TITLE_SIZE, "FINAL OUTCOME", scale=title_scale, color=(240,220,200))
        title_y = int(40 * scale_factor)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, title_y))
        # compute outcome using advisors' trust values and provide detailed notes
        advisors = list(self.game.advisors.items()) if self.game else []
        trusts = [v.get('trust', 0) for _, v in advisors]
        avg = int(sum(trusts)/len(trusts)) if trusts else 0
        mn = min(trusts) if trusts else 0
        mx = max(trusts) if trusts else 0
        # identify advisors with min/max trust
        low_names = [info.get('name', k) for k, info in advisors if info.get('trust', 0) == mn]
        high_names = [info.get('name', k) for k, info in advisors if info.get('trust', 0) == mx]
        # advisors who quit / became inactive (often due to very low trust)
        quit_names = [info.get('name', k) for k, info in advisors if not info.get('active', True)]

        # outcome mapping
        if mn < 20:
            header = "Catastrophic Collapse"
            msg = f"At least one advisor lost nearly all trust ({', '.join(low_names)}). The nation collapsed."
        elif avg >= 80 and mn >= 50:
            header = "Resounding Success"
            msg = f"Strong trust across advisors; prosperity and stability achieved. Top advisor(s): {', '.join(high_names)}."
        elif avg >= 65:
            header = "Prosperous"
            msg = f"Generally trusted leadership produced positive outcomes. Top advisor(s): {', '.join(high_names)}."
        elif avg >= 45:
            header = "Mixed Results"
            msg = f"Results were uneven; several advisors had middling trust. Lowest: {', '.join(low_names)}."
        elif avg >= 30:
            header = "Strained"
            msg = f"Advisor distrust undermined policy; recovery is uncertain. Lowest: {', '.join(low_names)}."
        else:
            header = "Failure"
            msg = f"Low overall trust led to systemic failure. Lowest: {', '.join(low_names)}."

        # Append quit advisor notice if any advisors became inactive (quit)
        try:
            if quit_names:
                msg = msg + " Advisors who quit due to low trust: " + ', '.join(quit_names) + "."
        except Exception:
            pass

        hdr_s = pixel_text(None, OPTIONS_TITLE_SIZE, header, scale=title_scale, color=(240,200,160))
        hdr_y = title_y + int(44 * scale_factor)
        screen.blit(hdr_s, (WIDTH//2 - hdr_s.get_width()//2, hdr_y))
        # wrap main outcome message to fit width and available space
        max_msg_w = WIDTH - 160
        # try with current label_scale, otherwise step down to fit vertical space
        msg_scale = label_scale
        msg_surfs = wrap_text_into_surfaces(msg, OPTIONS_LABEL_SIZE, msg_scale, max_msg_w, color=(220,200,200))
        # limit total message height to a fraction of screen
        max_msg_h = int(HEIGHT * 0.22)
        total_h = sum(s.get_height() + 6 for s in msg_surfs)
        while total_h > max_msg_h and msg_scale > 1:
            msg_scale -= 1
            msg_surfs = wrap_text_into_surfaces(msg, OPTIONS_LABEL_SIZE, msg_scale, max_msg_w, color=(220,200,200))
            total_h = sum(s.get_height() + 6 for s in msg_surfs)
        # clamp if still too tall
        if total_h > max_msg_h:
            # truncate lines to fit
            h = 0
            kept = []
            for s in msg_surfs:
                if h + s.get_height() + 6 > max_msg_h:
                    break
                kept.append(s)
                h += s.get_height() + 6
            msg_surfs = kept
            total_h = h
        # blit message lines centered — add extra spacing below the header
        my = hdr_y + int(56 * scale_factor)
        for s in msg_surfs:
            screen.blit(s, (WIDTH//2 - s.get_width()//2, my))
            my += s.get_height() + 6

        # list advisors and trusts in two columns if many
        y = max(int(180 * scale_factor), my + 12)
        left_x = WIDTH//2 - int(180 * scale_factor)
        right_x = WIDTH//2 + int(20 * scale_factor)
        for idx, (key, info) in enumerate(advisors):
            name = info.get('name', key)
            t = info.get('trust', 0)
            line = f"{name}: {t}%"
            s = pixel_text(None, ADVISOR_NAME_SIZE, line, scale=name_max_scale, color=(200,200,200))
            x = left_x if idx % 2 == 0 else right_x
            screen.blit(s, (x, y + (idx//2) * (s.get_height() + 6)))
        # show advisor-specific note lines below the list, but clamp to avoid overflow
        s_height = s.get_height() if advisors else pixel_text(None, ADVISOR_NAME_SIZE, ' ', scale=name_max_scale).get_height()
        ny = y + ((len(advisors)+1)//2) * (s_height + 6) + int(12 * scale_factor)
        for key, info in advisors:
            note = None
            # check by key first, then by name substring
            lk = key.lower() if isinstance(key, str) else ''
            if lk in ADVISOR_END_MESSAGES:
                note = ADVISOR_END_MESSAGES[lk]
            else:
                nm = info.get('name','').lower()
                for kmsg, txt in ADVISOR_END_MESSAGES.items():
                    if kmsg in nm:
                        note = txt
                        break
            if note:
                note_lines = wrap_text_into_surfaces(f"{info.get('name','')}: {note}", OPTIONS_LABEL_SIZE, label_scale, WIDTH - 160, color=(180,180,180))
                for ns in note_lines:
                    if ny + ns.get_height() > HEIGHT - 140:
                        break
                    screen.blit(ns, (WIDTH//2 - ns.get_width()//2, ny))
                    ny += ns.get_height() + int(6 * scale_factor)
                if ny > HEIGHT - 140:
                    break

    def _compute_summary(self):
        advisors = list(self.game.advisors.items()) if self.game else []
        trusts = [v.get('trust', 0) for _, v in advisors]
        avg = int(sum(trusts)/len(trusts)) if trusts else 0
        mn = min(trusts) if trusts else 0
        mx = max(trusts) if trusts else 0
        low_names = [info.get('name', k) for k, info in advisors if info.get('trust', 0) == mn]
        high_names = [info.get('name', k) for k, info in advisors if info.get('trust', 0) == mx]
        # pick header/msg using thresholds
        if mn < THRESH_CATASTROPHIC_MIN:
            header = "Catastrophic Collapse"
            msg = f"At least one advisor lost nearly all trust ({', '.join(low_names)}). The nation collapsed."
        elif avg >= THRESH_RESOUNDING_AVG and mn >= 50:
            header = "Resounding Success"
            msg = f"Strong trust across advisors; prosperity achieved. Top: {', '.join(high_names)}."
        elif avg >= THRESH_PROSPEROUS_AVG:
            header = "Prosperous"
            msg = f"Generally trusted leadership produced positive outcomes. Top: {', '.join(high_names)}."
        elif avg >= THRESH_MIXED_AVG:
            header = "Mixed Results"
            msg = f"Results were uneven; several advisors had middling trust. Lowest: {', '.join(low_names)}."
        elif avg >= THRESH_STRAINED_AVG:
            header = "Strained"
            msg = f"Advisor distrust undermined policy; recovery is uncertain. Lowest: {', '.join(low_names)}."
        else:
            header = "Failure"
            msg = f"Low overall trust led to systemic failure. Lowest: {', '.join(low_names)}."
        # detect advisors who quit / became inactive and include them in the summary
        quit_advisors = [info.get('name', k) for k, info in advisors if not info.get('active', True)]
        if quit_advisors:
            msg = msg + " Advisors who quit due to low trust: " + ', '.join(quit_advisors) + "."
        summary = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'avg_trust': avg,
            'min_trust': mn,
            'max_trust': mx,
            'low_advisors': low_names,
            'high_advisors': high_names,
            'quit_advisors': quit_advisors,
            'header': header,
            'message': msg,
            'advisors': {k: v for k, v in advisors}
        }
        return summary

    def _save_summary(self):
        try:
            out_dir = os.path.join(ASSETS_DIR, 'endings')
            os.makedirs(out_dir, exist_ok=True)
            fname = f"ending_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.json"
            path = os.path.join(out_dir, fname)
            # convert advisors to serializable form
            s = dict(self.summary)
            s['advisors'] = {k: {k2: (v2 if not isinstance(v2, (set,)) else list(v2)) for k2, v2 in v.items()} for k, v in s.get('advisors', {}).items()}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(s, f, indent=2)
        except Exception:
            pass

        for b in self.buttons:
            b.draw(screen)
        # transient error message (displayed when Start fails)
        if getattr(self, 'error_msg', None):
            em = pixel_text(None, OPTIONS_LABEL_SIZE, self.error_msg, scale=OPTIONS_LABEL_SCALE, color=(240,160,160))
            self.screen.blit(em, (WIDTH//2 - em.get_width()//2, HEIGHT//2 + 140))


def main():
    app = App()
    app.run()


if __name__ == '__main__':
    main()
