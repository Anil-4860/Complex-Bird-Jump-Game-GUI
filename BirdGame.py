"""
Complex Colorful Bird Jump Game

Features:
- Flappy-Bird-like gameplay with physics-based bird (tilt on velocity)
- Parallax background and scrolling ground for a lively GUI
- Multi-colored pipes, animated bird, particle effects
- Power-ups (shield, slow gravity, score boost)
- Lives (multiple chances) + respawn with temporary invulnerability
- Pause, mute, restart controls
- High score saved to local file
- Each step is explained with comments above the relevant code blocks

Run:
1) Install pygame if needed: pip install pygame

Notes: audio is optional — placeholders included so you can drop in sound files if desired.
"""

import math
import os
import random
import sys
import time

import pygame

# -----------------------------
# CONFIGURATION / CONSTANTS
# -----------------------------
WIDTH, HEIGHT = 480, 720  # window size
FPS = 60  # frames per second (logic will use delta-time for smoothness)

# Bird physics constants
BIRD_X = 120
BIRD_RADIUS = 18
GRAVITY = 1000.0  # pixels per second^2 (large because we use dt in seconds)
JUMP_VELOCITY = -380.0  # pixels per second
MAX_FALL_SPEED = 800.0

# Pipe settings
PIPE_WIDTH = 88
PIPE_GAP = 190
PIPE_MIN_TOP = 90
PIPE_SPEED_BASE = 180.0  # pixels per second (will scale with difficulty)
PIPE_SPAWN_INTERVAL = 1.6  # seconds between pipes (scales with difficulty)

# Power-up settings
POWERUP_TYPES = ["shield", "slow", "score"]
POWERUP_RADIUS = 12
POWERUP_SPAWN_CHANCE = 0.12  # chance to spawn after a pipe is spawned
POWERUP_DURATION = 4.0  # seconds

# UI / Gameplay
START_LIVES = 3
INVULNERABILITY_AFTER_HIT = 1.6  # seconds of invulnerability after losing a life
HIGH_SCORE_FILE = "bird_highscore.txt"

# Visuals: color palettes for lively appearance
SKY_TOP = (135, 206, 235)
SKY_BOTTOM = (255, 250, 240)
GROUND_COLOR = (90, 56, 34)
PIPE_PALETTE = [
    (239, 71, 111),  # pink/red
    (255, 209, 102), # warm yellow
    (6, 214, 160),   # mint green
    (17, 138, 178),  # teal
    (131, 56, 236),  # purple
]
POWERUP_COLORS = {
    "shield": (255, 215, 0),  # gold
    "slow": (102, 204, 255),   # light blue
    "score": (255, 102, 178),  # pink
}

# Fonts (created later after pygame.init())

# -----------------------------
# HELPER FUNCTIONS
# -----------------------------

def clamp(v, a, b):
    """Clamp value v between a and b."""
    return max(a, min(b, v))


def load_highscore():
    """Load high score from disk, return 0 if missing or invalid."""
    try:
        with open(HIGH_SCORE_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0


def save_highscore(score):
    """Save high score to disk. Overwrites existing file."""
    try:
        with open(HIGH_SCORE_FILE, "w") as f:
            f.write(str(int(score)))
    except Exception:
        pass


def draw_text(surf, text, size, pos, color=(10, 10, 10), center=False):
    """Convenience to draw text on a surface. Fonts are created in Game.__init__"""
    font = pygame.font.SysFont(None, size)
    surf_t = font.render(text, True, color)
    rect = surf_t.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    surf.blit(surf_t, rect)


def circle_rect_collision(circle_pos, circle_rad, rect):
    """Check collision between a circle and a rectangle.
    This is used for bird (circle) vs pipe (rect) collision tests.
    """
    cx, cy = circle_pos
    # find closest point on rect to circle center
    closest_x = clamp(cx, rect.left, rect.right)
    closest_y = clamp(cy, rect.top, rect.bottom)
    dx = cx - closest_x
    dy = cy - closest_y
    return (dx * dx + dy * dy) <= (circle_rad * circle_rad)


# -----------------------------
# GAME OBJECTS
# -----------------------------

class Bird:
    """Represents the player's bird with physics, tilt/rotation and visual state.
    We intentionally avoid external sprite files and draw the bird using pygame primitives
    so the file is self-contained.
    """

    def __init__(self, x, y):
        # Position stored as floats for smooth movement
        self.x = float(x)
        self.y = float(y)
        self.vel = 0.0  # vertical velocity (px/sec)
        self.radius = BIRD_RADIUS
        self.alive = True
        # Flap animation state (for wing bob)
        self.flap_phase = 0.0

    def flap(self):
        """Apply an instant upwards velocity to simulate a flap/jump."""
        self.vel = JUMP_VELOCITY
        # nudge flap animation
        self.flap_phase = 0.4

    def update(self, dt):
        """Update physics: integrate velocity and position using delta-time dt (seconds)."""
        self.vel += GRAVITY * dt
        # clamp fall speed for stability
        self.vel = clamp(self.vel, -1000.0, MAX_FALL_SPEED)
        self.y += self.vel * dt

        # update flap animation phase towards 0
        self.flap_phase = max(0.0, self.flap_phase - dt * 3.0)

    def draw(self, surf, angle_mul=1.0):
        """Draw the bird as a circle with an eye and a simple wing. Rotate/tilt based on velocity.
        angle_mul allows external scaling of rotation for visual effect.
        """
        # compute tilt angle (more negative vel -> tilt up)
        angle = clamp(-self.vel / 600.0 * 45.0 * angle_mul, -45, 60)

        # Body
        body_center = (int(self.x), int(self.y))
        pygame.draw.circle(surf, (255, 215, 64), body_center, self.radius)  # bright body
        pygame.draw.circle(surf, (10, 10, 10), body_center, self.radius, 2)  # outline

        # Eye (slightly above center)
        eye_x = int(self.x + self.radius * 0.3)
        eye_y = int(self.y - self.radius * 0.35)
        pygame.draw.circle(surf, (255, 255, 255), (eye_x, eye_y), max(2, self.radius // 6))
        pygame.draw.circle(surf, (10, 10, 10), (eye_x, eye_y), max(1, self.radius // 12))

        # Wing: we draw a rotated ellipse manually by offsetting a polygon
        # wing bob amplitude depends on flap_phase
        bob = int(self.flap_phase * 6)
        wing_color = (255, 170, 44)
        wing_points = [
            (self.x - 6, self.y + 2 + bob),
            (self.x - 22, self.y - 6 + bob),
            (self.x - 12, self.y - 2 + bob),
        ]
        pygame.draw.polygon(surf, wing_color, wing_points)
        pygame.draw.polygon(surf, (10, 10, 10), wing_points, 1)

    def get_circle(self):
        """Return current circle (x, y, r) for collision checks."""
        return (self.x, self.y, self.radius)


class Pipe:
    """Represents an obstacle pair (top and bottom pipe) that moves left across the screen."""

    def __init__(self, x, top_height, gap=PIPE_GAP, color=(40, 180, 99)):
        self.x = float(x)
        self.top = top_height
        self.gap = gap
        self.width = PIPE_WIDTH
        self.color = color
        self.passed = False  # whether the bird has passed the pipe (for scoring)

    def update(self, dt, speed):
        """Move pipe left by speed (px/sec)."""
        self.x -= speed * dt

    def draw(self, surf):
        """Render the top and bottom pipes with a stylized rim and shadow."""
        # Top rect
        top_rect = pygame.Rect(int(self.x), 0, self.width, int(self.top))
        bottom_rect = pygame.Rect(int(self.x), int(self.top + self.gap), self.width, int(HEIGHT - (self.top + self.gap)))

        # draw body
        pygame.draw.rect(surf, self.color, top_rect)
        pygame.draw.rect(surf, self.color, bottom_rect)

        # add lighter rim at inner edges to give depth
        rim_w = 8
        rim_color = tuple(min(255, c + 30) for c in self.color)
        # bottom of top pipe
        pygame.draw.rect(surf, rim_color, (int(self.x), int(self.top - rim_w), self.width, rim_w))
        # top of bottom pipe
        pygame.draw.rect(surf, rim_color, (int(self.x), int(self.top + self.gap), self.width, rim_w))

    def collides_with_circle(self, circle):
        """Check if the pipe collides with a circle (bird)."""
        cx, cy, cr = circle
        top_rect = pygame.Rect(int(self.x), 0, self.width, int(self.top))
        bottom_rect = pygame.Rect(int(self.x), int(self.top + self.gap), self.width, int(HEIGHT - (self.top + self.gap)))
        return circle_rect_collision((cx, cy), cr, top_rect) or circle_rect_collision((cx, cy), cr, bottom_rect)

    def off_screen(self):
        return self.x + self.width < -40


class PowerUp:
    """Floating power-up that gives temporary bonuses when collected by the bird."""

    def __init__(self, x, y, ptype):
        self.x = float(x)
        self.y = float(y)
        self.type = ptype
        self.radius = POWERUP_RADIUS
        self.collected = False

    def update(self, dt, speed):
        # power-ups drift left with the pipes
        self.x -= speed * dt
        # small bobbing motion
        self.y += math.sin(time.time() * 4.0 + self.x) * 8 * dt

    def draw(self, surf):
        c = POWERUP_COLORS.get(self.type, (255, 255, 255))
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, (10, 10, 10), (int(self.x), int(self.y)), self.radius, 2)
        draw_text(surf, self.type[0].upper(), 20, (int(self.x) - 6, int(self.y) - 10), color=(10, 10, 10))

    def collides_with_circle(self, circle):
        cx, cy, cr = circle
        dx = cx - self.x
        dy = cy - self.y
        return dx * dx + dy * dy <= (cr + self.radius) ** 2


class Particle:
    """Very simple particle for visual effects (on pickup/crash)."""

    def __init__(self, x, y, color, vx, vy, life):
        self.x = float(x)
        self.y = float(y)
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.max_life = life

    def update(self, dt):
        self.vy += 300 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt

    def draw(self, surf):
        if self.life <= 0:
            return
        alpha = clamp(self.life / self.max_life, 0.0, 1.0)
        r = int(3 + 5 * alpha)
        s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        col = (*self.color, int(255 * alpha))
        pygame.draw.circle(s, col, (r, r), r)
        surf.blit(s, (int(self.x - r), int(self.y - r)))


# -----------------------------
# MAIN GAME CLASS
# -----------------------------

class Game:
    """Holds overall game state, contains update and render loops, and handles input.
    Comments describe the purpose of each block.
    """

    def __init__(self):
        # initialize pygame and create the window
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Complex Colorful Bird Jump")
        self.clock = pygame.time.Clock()

        # base font used across the game
        self.font = pygame.font.SysFont(None, 30)
        self.large_font = pygame.font.SysFont(None, 56)

        # load or initialize persistent high score
        self.high_score = load_highscore()

        # create initial game variables
        self.reset()

        # Prepare parallax clouds for background
        self.clouds = [
            {"x": random.randint(0, WIDTH), "y": random.randint(20, 200), "r": random.randint(20, 45), "speed": random.uniform(10, 40)}
            for _ in range(10)
        ]

        # particle list
        self.particles = []

        # Sound toggles and placeholders
        self.sound_on = True
        # You can add: self.sfx_flap = pygame.mixer.Sound('flap.wav') etc.

    def reset(self):
        """Reset variables for a fresh play session (not persistent high score)."""
        self.bird = Bird(BIRD_X, HEIGHT // 2)
        self.pipes = []
        self.powerups = []
        self.score = 0
        self.lives = START_LIVES
        self.invulnerable_timer = 0.0
        self.powerup_timers = {}  # e.g., {"shield": remaining_seconds}

        # difficulty scaling variables
        self.pipe_speed = PIPE_SPEED_BASE
        self.pipe_spawn_interval = PIPE_SPAWN_INTERVAL
        self.time_since_last_pipe = 0.0

        # game states: MENU, PLAYING, PAUSED, GAME_OVER
        self.state = "MENU"
        self.menu_select = 0

        # timers
        self.last_time = time.time()

    # -----------------------------
    # STATE MANAGEMENT / INPUT
    # -----------------------------
    def handle_input(self):
        """Process events from pygame's queue and translate into game actions."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit()
            elif event.type == pygame.KEYDOWN:
                if self.state == "MENU":
                    # In the menu, SPACE starts the game
                    if event.key == pygame.K_SPACE:
                        self.state = "PLAYING"
                        # small delay so player isn't caught off guard
                        self.time_since_last_pipe = 0.0
                    elif event.key == pygame.K_q:
                        self.quit()
                elif self.state == "PLAYING":
                    if event.key == pygame.K_SPACE:
                        self.bird.flap()
                        # sfx placeholder: if self.sound_on: self.sfx_flap.play()
                    elif event.key == pygame.K_p:
                        self.state = "PAUSED"
                    elif event.key == pygame.K_m:
                        self.sound_on = not self.sound_on
                elif self.state == "PAUSED":
                    if event.key == pygame.K_p:
                        self.state = "PLAYING"
                elif self.state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        # Restart full game
                        self.reset()
                        self.state = "PLAYING"
                    elif event.key == pygame.K_q:
                        self.quit()

    # -----------------------------
    # GAME LOGIC
    # -----------------------------
    def spawn_pipe(self):
        """Create a new pipe with a random top height and a color from the palette."""
        top_h = random.randint(PIPE_MIN_TOP, HEIGHT - PIPE_GAP - 140)
        color = random.choice(PIPE_PALETTE)
        pipe = Pipe(WIDTH + 40, top_h, gap=PIPE_GAP, color=color)
        self.pipes.append(pipe)
        # chance to spawn a powerup near this pipe
        if random.random() < POWERUP_SPAWN_CHANCE:
            # spawn in the gap region
            px = pipe.x + pipe.width // 2 + random.randint(20, 60)
            py = top_h + pipe.gap * random.uniform(0.25, 0.75)
            ptype = random.choice(POWERUP_TYPES)
            self.powerups.append(PowerUp(px, py, ptype))

    def apply_powerup(self, ptype):
        """Apply the effect of a powerup type by setting timers or state variables."""
        if ptype == "shield":
            self.powerup_timers["shield"] = POWERUP_DURATION
        elif ptype == "slow":
            self.powerup_timers["slow"] = POWERUP_DURATION
        elif ptype == "score":
            self.powerup_timers["score"] = POWERUP_DURATION

    def spawn_particles(self, x, y, color, count=20):
        """Create many small particles for visual flair at (x,y)."""
        for _ in range(count):
            vx = random.uniform(-220, 220)
            vy = random.uniform(-200, -40)
            life = random.uniform(0.5, 1.2)
            self.particles.append(Particle(x, y, color, vx, vy, life))

    def handle_collisions(self):
        """Check collisions between bird and pipes/powerups and react accordingly."""
        # circle representing bird
        circ = self.bird.get_circle()

        # PowerUp collisions: pick up and apply
        for pu in list(self.powerups):
            if pu.collides_with_circle(circ):
                self.apply_powerup(pu.type)
                pu.collected = True
                self.powerups.remove(pu)
                # visual + score feedback
                self.spawn_particles(self.bird.x, self.bird.y, POWERUP_COLORS.get(pu.type, (255, 255, 255)), 18)
                if pu.type == "score":
                    self.score += 2

        # Pipe collisions: only if not invulnerable and not shielded
        if self.invulnerable_timer <= 0.0 and self.powerup_timers.get("shield", 0.0) <= 0.0:
            for pipe in self.pipes:
                if pipe.collides_with_circle(circ):
                    # bird hit a pipe -> lose a life
                    self.lives -= 1
                    self.invulnerable_timer = INVULNERABILITY_AFTER_HIT
                    # give a small bounce back
                    self.bird.vel = -160
                    self.spawn_particles(self.bird.x, self.bird.y, (255, 80, 80), 30)
                    if self.lives <= 0:
                        self.state = "GAME_OVER"
                        # check highscore
                        if self.score > self.high_score:
                            self.high_score = self.score
                            save_highscore(self.high_score)
                    break

        # ground collision (if bird hits the ground)
        if self.bird.y + self.bird.radius >= HEIGHT - 30:
            if self.invulnerable_timer <= 0.0 and self.powerup_timers.get("shield", 0.0) <= 0.0:
                self.lives -= 1
                self.invulnerable_timer = INVULNERABILITY_AFTER_HIT
                self.spawn_particles(self.bird.x, self.bird.y, (255, 80, 80), 18)
                self.bird.vel = -120
                if self.lives <= 0:
                    self.state = "GAME_OVER"
                    if self.score > self.high_score:
                        self.high_score = self.score
                        save_highscore(self.high_score)

    # -----------------------------
    # UPDATE / DRAW LOOP
    # -----------------------------
    def update(self, dt):
        """Update all game objects. dt is elapsed time in seconds since last frame."""
        if self.state != "PLAYING":
            # update only limited things in non-playing states (like background)
            # but we still move clouds for a living menu screen
            for c in self.clouds:
                c["x"] -= c["speed"] * dt * 0.25
                if c["x"] < -80:
                    c["x"] = WIDTH + 60
            return

        # timers
        self.time_since_last_pipe += dt

        # difficulty scaling by score: as score increases, pipes get faster and spacing tighter
        difficulty_factor = 1.0 + math.log(1 + max(0, self.score)) * 0.05
        speed = self.pipe_speed * difficulty_factor * (0.6 if self.powerup_timers.get("slow", 0.0) > 0.0 else 1.0)
        spawn_interval = max(1.0, self.pipe_spawn_interval / difficulty_factor)

        # spawn pipes at intervals
        if self.time_since_last_pipe >= spawn_interval:
            self.spawn_pipe()
            self.time_since_last_pipe = 0.0

        # update bird physics
        self.bird.update(dt)

        # update pipes
        for pipe in list(self.pipes):
            pipe.update(dt, speed)
            # scoring: if pipe passed left of bird and not yet counted
            if not pipe.passed and pipe.x + pipe.width < self.bird.x:
                pipe.passed = True
                self.score += 1
                # visual: spawn confetti particles
                self.spawn_particles(self.bird.x, self.bird.y, (180, 255, 200), 8)
            if pipe.off_screen():
                self.pipes.remove(pipe)

        # update power-ups
        for pu in list(self.powerups):
            pu.update(dt, speed)
            if pu.x < -40:
                self.powerups.remove(pu)

        # update particles and cull dead
        for p in list(self.particles):
            p.update(dt)
            if p.life <= 0:
                try:
                    self.particles.remove(p)
                except ValueError:
                    pass

        # update invulnerability and powerup timers
        if self.invulnerable_timer > 0.0:
            self.invulnerable_timer -= dt

        to_del = []
        for k, t in self.powerup_timers.items():
            self.powerup_timers[k] = t - dt
            if self.powerup_timers[k] <= 0.0:
                to_del.append(k)
        for k in to_del:
            del self.powerup_timers[k]

        # handle collisions after movement
        self.handle_collisions()

        # keep bird from going too high
        if self.bird.y < 20:
            self.bird.y = 20
            self.bird.vel = 0

    def draw_background(self):
        """Draw gradient sky and parallax cloud layers. We fill from top to bottom."""
        # vertical linear gradient between SKY_TOP and SKY_BOTTOM
        for i in range(HEIGHT // 2):
            u = i / (HEIGHT // 2)
            r = int(SKY_TOP[0] * (1 - u) + SKY_BOTTOM[0] * u)
            g = int(SKY_TOP[1] * (1 - u) + SKY_BOTTOM[1] * u)
            b = int(SKY_TOP[2] * (1 - u) + SKY_BOTTOM[2] * u)
            pygame.draw.line(self.screen, (r, g, b), (0, i), (WIDTH, i))
        # lower half
        for i in range(HEIGHT // 2, HEIGHT):
            self.screen.fill(SKY_BOTTOM, (0, i, WIDTH, 1))

        # clouds
        for c in self.clouds:
            x = int(c["x"]) % (WIDTH + 200) - 100
            pygame.draw.circle(self.screen, (255, 255, 255), (x, int(c["y"])), c["r"])
            pygame.draw.circle(self.screen, (250, 250, 250), (x + int(c["r"] * 0.6), int(c["y"] - c["r"] * 0.1)), int(c["r"] * 0.7))

    def draw_ground(self):
        """Draw a repeating ground band at the bottom with simple tiles for motion impression."""
        ground_h = 90
        pygame.draw.rect(self.screen, GROUND_COLOR, (0, HEIGHT - ground_h, WIDTH, ground_h))
        # draw simple tile shapes to show movement
        tile_w = 40
        offset = (pygame.time.get_ticks() // 10) % tile_w
        for x in range(-tile_w + offset, WIDTH, tile_w):
            pygame.draw.rect(self.screen, (100, 65, 40), (x + 10, HEIGHT - ground_h + 10, tile_w - 18, ground_h - 20))

    def draw(self):
        """Draw everything: background, pipes, power-ups, bird, particles, and UI."""
        # background + clouds
        self.draw_background()

        # pipes behind bird (but their drawing order doesn't matter much visually)
        for pipe in self.pipes:
            pipe.draw(self.screen)

        # powerups
        for pu in self.powerups:
            pu.draw(self.screen)

        # particles under the bird so they appear behind in depth
        for p in self.particles:
            p.draw(self.screen)

        # bird with slight tilt multiplier if slow effect is active
        angle_mul = 0.7 if "slow" in self.powerup_timers else 1.0
        # if invulnerable show blinking by skipping draw some frames
        if self.invulnerable_timer > 0.0 and int(self.invulnerable_timer * 10) % 2 == 0:
            # skip draw to indicate blink
            pass
        else:
            self.bird.draw(self.screen, angle_mul=angle_mul)

        # draw HUD: score, highscore, lives
        draw_text(self.screen, f"Score: {self.score}", 28, (12, 12), color=(20, 20, 20))
        draw_text(self.screen, f"High: {self.high_score}", 20, (12, 44), color=(20, 20, 20))

        # lives display
        for i in range(self.lives):
            x = WIDTH - 20 - i * 28
            y = 24
            pygame.draw.circle(self.screen, (255, 80, 80), (x, y), 8)
            pygame.draw.circle(self.screen, (10, 10, 10), (x, y), 8, 1)

        # active powerups
        if self.powerup_timers:
            y = 80
            for k, t in self.powerup_timers.items():
                c = POWERUP_COLORS.get(k, (255, 255, 255))
                pygame.draw.circle(self.screen, c, (WIDTH - 32, y), 12)
                draw_text(self.screen, f"{k} {int(t)}s", 18, (WIDTH - 88, y - 12), color=(10, 10, 10))
                y += 28

        # draw ground
        self.draw_ground()

        # overlays for MENU / PAUSE / GAME OVER
        if self.state == "MENU":
            # semi-transparent overlay for menu
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 255, 255, 200))
            self.screen.blit(overlay, (0, 0))
            draw_text(self.screen, "Complex Colorful Bird Jump", 42, (WIDTH // 2, HEIGHT // 2 - 60), color=(30, 30, 30), center=True)
            draw_text(self.screen, "Press SPACE to start", 28, (WIDTH // 2, HEIGHT // 2), color=(30, 30, 30), center=True)
            draw_text(self.screen, "SPACE = Flap | P = Pause | M = Mute | R = Restart (game over)", 20, (WIDTH // 2, HEIGHT // 2 + 50), color=(30, 30, 30), center=True)
        elif self.state == "PAUSED":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 140))
            self.screen.blit(overlay, (0, 0))
            draw_text(self.screen, "Paused", 48, (WIDTH // 2, HEIGHT // 2), color=(255, 255, 255), center=True)
        elif self.state == "GAME_OVER":
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))
            draw_text(self.screen, "Game Over", 56, (WIDTH // 2, HEIGHT // 2 - 40), color=(255, 255, 255), center=True)
            draw_text(self.screen, f"Score: {self.score}", 34, (WIDTH // 2, HEIGHT // 2 + 10), color=(255, 255, 255), center=True)
            draw_text(self.screen, "Press R to restart or Q to quit", 22, (WIDTH // 2, HEIGHT // 2 + 60), color=(255, 255, 255), center=True)

        # final flip
        pygame.display.flip()

    # -----------------------------
    # RUN / QUIT
    # -----------------------------
    def run(self):
        """Main loop. We use delta-time for consistent physics and timers."""
        running = True
        while running:
            # compute dt in seconds
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_input()
            self.update(dt)
            self.draw()

    def quit(self):
        pygame.quit()
        sys.exit()


# -----------------------------
# ENTRY POINT
# -----------------------------

if __name__ == "__main__":
    Game().run()
