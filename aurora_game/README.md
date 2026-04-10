Project upgrade notes

This workspace now includes a Pygame-based prototype for a pixel-style title screen.

Files:
- `aurora_pygame.py`: title-screen prototype with basic buttons, pixel text rendering, background, and audio if provided.
- `requirements.txt`: lists `pygame` and `Pillow`.
- `assets/`: place your music and sfx here.

How to run the prototype:

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Add optional assets:
- `assets/audio/music.ogg` for looping background music
- `assets/sfx/click.wav` for button clicks

3. Run:

```bash
python aurora_pygame.py
```

Next steps:
- Replace placeholder visuals with real pixel art (background, title, portraits).
- Add options UI for volume and toggles.
- Integrate Pygame UI with existing game logic or port game logic into Pygame.
