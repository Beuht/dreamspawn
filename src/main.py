"""
DREAMSPAWN — prototype Metroidvania dark fantasy
=================================================
v3 : phases plus dures, Jugement Lunaire en phase 1, Phase 5 mode Sans
     avec gaster blasters, plein écran F11, dash sur A.

Mécanique signature :
  TRIPLE JUMP = CHANGEMENT DE DIMENSION
  - 1er appui sur espace : saut
  - 2e appui en l'air  : double saut
  - 3e appui en l'air  : FISSURE DE LA REALITE (swap de dimension)

Contrôles :
  Déplacement  : Flèches / WASD / ZQSD
  Saut         : Espace (3 fois en l'air = swap dimension)
  Dash         : A ou Maj gauche (peut traverser les projectiles roses = PARRY)
  Arc          : Clic gauche pour tirer (cooldown 35 frames anti-spam,
                 dégâts fixes à 4 par flèche, plus de charge à maintenir)
  Plein écran  : F (ou F11)
  Pause        : Échap
  Restart      : R (après défaite ou victoire)

Boss complet : LA LUNE en 5 phases
  Phase 1 — L'Œil Insomniaque (avec attaque majeure "Le Jugement Lunaire")
  Phase 2 — La Marée
  Phase 3 — L'Éclipse
  Phase 4 — La Couronne Brisée
  Phase 5 — Le Croissant Inversé (mode Sans : trois patterns en parallèle)
"""

import math
import os
import random
import sys
from collections import deque

import pygame


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1280, 720
FPS = 60

GRAVITY = 0.62
MAX_FALL = 17.0
MOVE_SPEED = 5.8
JUMP_FORCE = -13.8
COYOTE_FRAMES = 6
JUMP_BUFFER_FRAMES = 6

DASH_SPEED = 14.0
DASH_FRAMES = 10
DASH_COOLDOWN = 45

TRIPLE_TAP_WINDOW = 75
SWAP_COOLDOWN     = 300   # 5 sec entre chaque switch de dimension
DREAM_MAX_STAY    = 1200  # 20 sec max dans le rêve avant retour forcé
SWAP_INVULN_FRAMES = 25

INVULN_FRAMES = 50
PLAYER_MAX_HP = 15

ARROW_SPEED = 13.5
ARROW_LIFETIME = 100
BOW_COOLDOWN = 55    # anti-spam : cadence plus lente, dégâts plus forts
BOW_DAMAGE = 5       # dégât fixe par flèche

DIM_REAL = 0
DIM_DREAM = 1


# ---------------------------------------------------------------------------
# Palette (deux dimensions très contrastées)
# ---------------------------------------------------------------------------

class Pal:
    R_BG       = (10, 6, 20)
    R_BG_FAR   = (24, 14, 40)
    R_BG_STAR  = (180, 170, 220)
    R_GROUND   = (50, 30, 70)
    R_GROUND_E = (110, 70, 150)
    R_ACCENT   = (180, 60, 130)
    R_FOG      = (40, 20, 60)
    R_PARTICLE = (200, 120, 230)

    D_BG       = (245, 235, 252)
    D_BG_FAR   = (215, 200, 245)
    D_BG_STAR  = (255, 130, 200)
    D_GROUND   = (255, 140, 210)
    D_GROUND_E = (255, 210, 240)
    D_ACCENT   = (90, 200, 255)
    D_FOG      = (255, 220, 245)
    D_PARTICLE = (130, 240, 255)

    P_BODY_R   = (245, 240, 230)
    P_ROBE_R   = (45, 25, 60)
    P_CAPE_R   = (130, 30, 80)
    P_BODY_D   = (255, 250, 245)
    P_ROBE_D   = (180, 100, 220)
    P_CAPE_D   = (90, 220, 255)
    P_EYE      = (40, 0, 70)
    P_GLOW     = (200, 180, 255)

    UI         = (235, 220, 250)
    UI_DIM     = (140, 130, 170)
    UI_BG      = (15, 8, 30)
    UI_DARK    = (10, 5, 18)
    HP_FILL    = (220, 50, 90)
    HP_BG      = (50, 15, 35)
    BOSS_HP    = (210, 220, 250)
    BOSS_HP_BG = (40, 30, 60)
    BOSS_HP_D  = (255, 120, 200)

    ARROW      = (255, 230, 130)
    ARROW_CH1  = (255, 200, 100)
    ARROW_CH2  = (255, 150, 80)

    MOON_LIGHT = (240, 240, 250)
    MOON_DARK  = (130, 130, 170)
    MOON_GLOW  = (200, 220, 255)
    MOON_CRESC_R = (200, 210, 240)
    MOON_CRESC_D = (255, 220, 150)
    METEOR_CORE = (255, 200, 150)
    METEOR_TAIL = (255, 120, 80)
    BEAM_FILL  = (255, 245, 220)
    BEAM_EDGE  = (255, 200, 150)
    TELEGRAPH  = (255, 90, 130)
    TELEGRAPH_S = (255, 60, 100)  # plus saturé pour les gros tells


def pal_bg(dim):       return Pal.D_BG if dim == DIM_DREAM else Pal.R_BG
def pal_bg_far(dim):   return Pal.D_BG_FAR if dim == DIM_DREAM else Pal.R_BG_FAR
def pal_ground(dim):   return Pal.D_GROUND if dim == DIM_DREAM else Pal.R_GROUND
def pal_ground_e(dim): return Pal.D_GROUND_E if dim == DIM_DREAM else Pal.R_GROUND_E
def pal_fog(dim):      return Pal.D_FOG if dim == DIM_DREAM else Pal.R_FOG
def pal_part(dim):     return Pal.D_PARTICLE if dim == DIM_DREAM else Pal.R_PARTICLE
def pal_star(dim):     return Pal.D_BG_STAR if dim == DIM_DREAM else Pal.R_BG_STAR
def pal_accent(dim):   return Pal.D_ACCENT if dim == DIM_DREAM else Pal.R_ACCENT
def pal_body(dim):     return Pal.P_BODY_D if dim == DIM_DREAM else Pal.P_BODY_R
def pal_robe(dim):     return Pal.P_ROBE_D if dim == DIM_DREAM else Pal.P_ROBE_R
def pal_cape(dim):     return Pal.P_CAPE_D if dim == DIM_DREAM else Pal.P_CAPE_R


# ---------------------------------------------------------------------------
# Particules / poussière ambiante
# ---------------------------------------------------------------------------

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "grav")

    def __init__(self, x, y, vx, vy, life, color, size=3, grav=0.0):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.life = life; self.max_life = life
        self.color = color
        self.size = size
        self.grav = grav

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.grav
        self.life -= 1

    def alive(self): return self.life > 0

    def draw(self, surf, cam):
        t = max(0.0, self.life / self.max_life)
        r = max(1, int(self.size * t))
        pygame.draw.circle(surf, self.color, (int(self.x - cam[0]), int(self.y - cam[1])), r)


def burst(particles, x, y, n=14, color=(255, 255, 255), speed=4.0, life=30, grav=0.1, size=3):
    for _ in range(n):
        a = random.uniform(0, math.tau)
        s = random.uniform(speed * 0.3, speed)
        particles.append(Particle(x, y, math.cos(a) * s, math.sin(a) * s,
                                  random.randint(int(life * 0.6), life), color, size, grav))


class DustField:
    def __init__(self, count=50, bounds=(0, 0, WIDTH, HEIGHT)):
        self.bounds = bounds
        self.motes = []
        for _ in range(count):
            self.motes.append([
                random.uniform(bounds[0], bounds[2]),
                random.uniform(bounds[1], bounds[3]),
                random.uniform(-0.3, 0.3),
                random.uniform(-0.4, -0.1),
                random.uniform(1.0, 2.5),
                random.uniform(0.2, 1.0),
            ])

    def update(self):
        bx, by, bw, bh = self.bounds[0], self.bounds[1], self.bounds[2], self.bounds[3]
        for m in self.motes:
            m[0] += m[2]; m[1] += m[3]
            m[2] += random.uniform(-0.04, 0.04)
            m[2] = max(-0.6, min(0.6, m[2]))
            if m[1] < by:
                m[1] = bh; m[0] = random.uniform(bx, bw)
            if m[0] < bx: m[0] = bw
            if m[0] > bw: m[0] = bx

    def draw(self, surf, cam, dim):
        col = pal_part(dim)
        for m in self.motes:
            x = int(m[0] - cam[0] * m[5])
            y = int(m[1] - cam[1] * m[5])
            r = max(1, int(m[4]))
            a = int(80 + 120 * m[5])
            s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, a), (r + 1, r + 1), r)
            surf.blit(s, (x - r - 1, y - r - 1))


# ---------------------------------------------------------------------------
# Arrows (joueur)
# ---------------------------------------------------------------------------

class Arrow:
    def __init__(self, x, y, vx, vy, dmg=1, dim=DIM_REAL):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.dmg = dmg
        self.dim = dim
        self.life = ARROW_LIFETIME
        self.dead = False
        self.pierce = min(1, max(0, dmg - 2))   # 1 pierce sur les flèches puissantes
        self.size = 3 + min(dmg, 4)

    @property
    def rect(self):
        s = self.size
        return pygame.Rect(int(self.x) - s, int(self.y) - s // 2, s * 2, max(2, s))

    def update(self):
        self.x += self.vx; self.y += self.vy
        self.life -= 1
        if self.life <= 0: self.dead = True

    def draw(self, surf, cam):
        ang = math.atan2(self.vy, self.vx)
        cx, cy = self.x - cam[0], self.y - cam[1]
        if self.dmg >= 3:   col = Pal.ARROW_CH2
        elif self.dmg >= 2: col = Pal.ARROW_CH1
        else: col = Pal.ARROW
        length = 12 + self.dmg * 4
        x2 = cx - math.cos(ang) * length
        y2 = cy - math.sin(ang) * length
        pygame.draw.line(surf, col, (cx, cy), (x2, y2), 2 + self.dmg)
        pygame.draw.circle(surf, col, (int(cx), int(cy)), 2 + self.dmg)
        if self.dmg >= 2:
            s = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col, 80), (12, 12), 11)
            surf.blit(s, (int(cx) - 12, int(cy) - 12))


# ---------------------------------------------------------------------------
# Projectiles du boss
# ---------------------------------------------------------------------------

class BossProjectile:
    def __init__(self, x, y, vx, vy, dim, radius=10, life=300, homing=0.0, target=None,
                 color=None, kind="crescent", parry=False, dmg=2, hits_any_dim=False):
        self.x = x; self.y = y
        self.vx = vx; self.vy = vy
        self.dim = dim
        self.radius = radius
        self.life = life
        self.homing = homing
        self.target = target
        self.color = color or (Pal.MOON_CRESC_R if dim == DIM_REAL else Pal.MOON_CRESC_D)
        self.kind = kind
        self.parry = parry
        self.dmg = dmg
        # En phase 1, les attaques touchent quelle que soit la dimension du joueur
        self.hits_any_dim = hits_any_dim
        self.dead = False
        self.rot = 0.0
        self.spin = random.uniform(-0.15, 0.15)

    @property
    def rect(self):
        r = self.radius
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def update(self):
        if self.homing > 0 and self.target is not None:
            tx, ty = self.target.center()
            dx, dy = tx - self.x, ty - self.y
            d = math.hypot(dx, dy) + 1e-6
            self.vx += (dx / d) * self.homing
            self.vy += (dy / d) * self.homing
            sp = math.hypot(self.vx, self.vy)
            cap = 9.0
            if sp > cap:
                self.vx *= cap / sp; self.vy *= cap / sp
        self.x += self.vx; self.y += self.vy
        self.rot += self.spin
        self.life -= 1
        if self.life <= 0: self.dead = True

    def draw(self, surf, cam):
        cx, cy = int(self.x - cam[0]), int(self.y - cam[1])
        r = self.radius
        if self.parry:
            pulse = 1.0 + 0.2 * math.sin(self.life * 0.2)
            s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (255, 100, 180, 100), (r * 2, r * 2), int(r * 1.8 * pulse))
            surf.blit(s, (cx - r * 2, cy - r * 2))
            pygame.draw.circle(surf, (255, 200, 230), (cx, cy), r)
            pygame.draw.circle(surf, (255, 120, 200), (cx, cy), r, 2)
            return
        if self.kind == "crescent":
            pygame.draw.circle(surf, self.color, (cx, cy), r)
            off_x = int(math.cos(self.rot) * r * 0.45)
            off_y = int(math.sin(self.rot) * r * 0.45)
            bg = pal_bg(self.dim)
            pygame.draw.circle(surf, bg, (cx + off_x, cy + off_y), r)
        elif self.kind == "orb":
            pygame.draw.circle(surf, self.color, (cx, cy), r + 2, 2)
            pygame.draw.circle(surf, self.color, (cx, cy), max(1, r - 3))
        elif self.kind == "meteor":
            pygame.draw.circle(surf, Pal.METEOR_TAIL, (cx - int(self.vx * 1.4), cy - int(self.vy * 1.4)), r)
            pygame.draw.circle(surf, Pal.METEOR_CORE, (cx, cy), max(2, r - 2))
        elif self.kind == "star":
            pygame.draw.polygon(surf, self.color,
                                [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)])


class Ring:
    def __init__(self, x, y, dim, max_r=400, life=100, color=None, dmg=2, hits_any_dim=False):
        self.x = x; self.y = y
        self.dim = dim
        self.max_r = max_r
        self.life = life
        self.max_life = life
        self.color = color or Pal.MOON_GLOW
        self.dmg = dmg
        self.hits_any_dim = hits_any_dim
        self.dead = False
        self.hit_thickness = 22

    @property
    def r(self):
        return int(self.max_r * (1 - self.life / self.max_life))

    @property
    def rect(self):
        r = self.r
        return pygame.Rect(int(self.x) - r, int(self.y) - r, r * 2, r * 2)

    def update(self):
        self.life -= 1
        if self.life <= 0: self.dead = True

    def hits(self, target_rect):
        cx, cy = target_rect.center
        d = math.hypot(cx - self.x, cy - self.y)
        return abs(d - self.r) < self.hit_thickness

    def draw(self, surf, cam):
        cx = int(self.x - cam[0]); cy = int(self.y - cam[1])
        r = self.r
        if r <= 0: return
        s = pygame.Surface((r * 2 + 20, r * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, 130), (r + 10, r + 10), r, 3)
        pygame.draw.circle(s, (*self.color, 70), (r + 10, r + 10), max(1, r - 4), 2)
        pygame.draw.circle(s, (*self.color, 200), (r + 10, r + 10), r, 1)
        surf.blit(s, (cx - r - 10, cy - r - 10))


class Beam:
    def __init__(self, rect, dim, life=24, color=None, dmg=1, hits_any_dim=False):
        self.rect = rect
        self.dim = dim
        self.life = life
        self.max_life = life
        self.color = color or Pal.BEAM_FILL
        self.dmg = dmg
        self.hits_any_dim = hits_any_dim
        self.dead = False

    def update(self):
        self.life -= 1
        if self.life <= 0: self.dead = True

    def draw(self, surf, cam):
        t = max(0.0, self.life / self.max_life)
        alpha = int(220 * t)
        edge_a = int(180 * t)
        s = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        s.fill((*self.color, alpha))
        if self.rect.w >= self.rect.h:
            pygame.draw.rect(s, (*Pal.BEAM_EDGE, edge_a), (0, 0, self.rect.w, 4))
            pygame.draw.rect(s, (*Pal.BEAM_EDGE, edge_a), (0, self.rect.h - 4, self.rect.w, 4))
        else:
            pygame.draw.rect(s, (*Pal.BEAM_EDGE, edge_a), (0, 0, 4, self.rect.h))
            pygame.draw.rect(s, (*Pal.BEAM_EDGE, edge_a), (self.rect.w - 4, 0, 4, self.rect.h))
        surf.blit(s, (self.rect.x - cam[0], self.rect.y - cam[1]))


# ---------------------------------------------------------------------------
# Telegraph (anticipation visuelle d'attaque)
# ---------------------------------------------------------------------------

class Telegraph:
    def __init__(self, kind, duration, dim, on_fire=None, color=None, **params):
        self.kind = kind
        self.timer = duration
        self.duration = duration
        self.dim = dim
        self.on_fire = on_fire
        self.color = color or Pal.TELEGRAPH
        self.params = params
        self.dead = False

    @property
    def t(self):
        return 1.0 - (self.timer / self.duration)

    def update(self):
        self.timer -= 1
        if self.timer <= 0:
            if self.on_fire: self.on_fire()
            self.dead = True

    def draw(self, surf, cam):
        t = self.t
        pulse = 0.6 + 0.4 * math.sin(self.timer * 0.4)
        if self.kind == "beam_v":
            x = self.params["x"] - cam[0]
            top = self.params.get("top", -200) - cam[1]
            bottom = self.params.get("bottom", HEIGHT + 200) - cam[1]
            final_w = self.params.get("final_width", 50)
            w = int(6 + t * (final_w - 6) * pulse)
            a = int(80 + 140 * t)
            s = pygame.Surface((max(2, w), max(1, int(bottom - top))), pygame.SRCALPHA)
            s.fill((*self.color, a))
            surf.blit(s, (int(x - w / 2), int(top)))
            pygame.draw.line(surf, self.color,
                             (int(x - final_w / 2), int(top)),
                             (int(x - final_w / 2), int(bottom)), 2)
            pygame.draw.line(surf, self.color,
                             (int(x + final_w / 2), int(top)),
                             (int(x + final_w / 2), int(bottom)), 2)
            pygame.draw.line(surf, self.color, (int(x), int(top)), (int(x), int(bottom)), 2)
        elif self.kind == "beam_h":
            y = self.params["y"] - cam[1]
            left = self.params.get("left", -200) - cam[0]
            right = self.params.get("right", WIDTH + 200) - cam[0]
            final_h = self.params.get("final_height", 50)
            h = int(6 + t * (final_h - 6) * pulse)
            a = int(80 + 140 * t)
            s = pygame.Surface((max(1, int(right - left)), max(2, h)), pygame.SRCALPHA)
            s.fill((*self.color, a))
            surf.blit(s, (int(left), int(y - h / 2)))
            pygame.draw.line(surf, self.color,
                             (int(left), int(y - final_h / 2)),
                             (int(right), int(y - final_h / 2)), 2)
            pygame.draw.line(surf, self.color,
                             (int(left), int(y + final_h / 2)),
                             (int(right), int(y + final_h / 2)), 2)
            pygame.draw.line(surf, self.color, (int(left), int(y)), (int(right), int(y)), 2)
        elif self.kind == "circle":
            x = int(self.params["x"] - cam[0])
            y = int(self.params["y"] - cam[1])
            r = int(self.params.get("r", 50))
            a = int(80 + 140 * t)
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, int(40 + 70 * t)), (r + 2, r + 2), r)
            pygame.draw.circle(s, (*self.color, a), (r + 2, r + 2), r, 3)
            surf.blit(s, (x - r - 2, y - r - 2))
            if t > 0.6:
                pygame.draw.line(surf, self.color, (x - 8, y), (x + 8, y), 2)
                pygame.draw.line(surf, self.color, (x, y - 8), (x, y + 8), 2)
        elif self.kind == "fan":
            ox = self.params["x"] - cam[0]
            oy = self.params["y"] - cam[1]
            ang = self.params["angle"]
            spread = self.params["spread"]
            count = self.params.get("count", 5)
            length = self.params.get("length", 700)
            ws = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            alpha = int(60 + 170 * t)
            thickness = 1 + int(3 * t)
            for i in range(count):
                tt = i / (count - 1) if count > 1 else 0.5
                a = ang - spread / 2 + spread * tt
                x2 = ox + math.cos(a) * length
                y2 = oy + math.sin(a) * length
                pygame.draw.line(ws, (*self.color, alpha),
                                 (int(ox), int(oy)), (int(x2), int(y2)), thickness)
            surf.blit(ws, (0, 0))
        elif self.kind == "ring":
            x = int(self.params["x"] - cam[0])
            y = int(self.params["y"] - cam[1])
            r = int(self.params.get("r", 200) * (0.3 + 0.7 * t))
            a = int(70 + 150 * t)
            s = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, a), (r + 3, r + 3), r, 3)
            surf.blit(s, (x - r - 3, y - r - 3))
        elif self.kind == "star_curtain":
            y = self.params.get("y", 0) - cam[1]
            left = self.params.get("left", -200) - cam[0]
            right = self.params.get("right", WIDTH + 200) - cam[0]
            h = int(4 + 14 * t)
            a = int(80 + 140 * t)
            s = pygame.Surface((max(1, int(right - left)), max(2, h)), pygame.SRCALPHA)
            s.fill((*self.color, a))
            surf.blit(s, (int(left), int(y)))
            for gx_local in self.params.get("gaps", []):
                gx = gx_local - cam[0]
                pygame.draw.line(surf, (255, 255, 255), (int(gx), int(y) + h),
                                 (int(gx), int(y) + h + 14), 2)


# ---------------------------------------------------------------------------
# Damage Numbers
# ---------------------------------------------------------------------------

class DamageNumber:
    def __init__(self, x, y, value, color=(255, 255, 255), font=None):
        self.x = x; self.y = y
        self.vy = -1.8
        self.life = 38
        self.max_life = self.life
        self.value = value
        self.color = color
        self.font = font

    def update(self):
        self.y += self.vy
        self.vy *= 0.94
        self.life -= 1

    def alive(self): return self.life > 0

    def draw(self, surf, cam):
        if not self.font: return
        t = self.life / self.max_life
        a = int(255 * t)
        text = self.font.render(str(self.value), True, self.color)
        text.set_alpha(a)
        surf.blit(text, (int(self.x - cam[0] - text.get_width() / 2),
                         int(self.y - cam[1])))


# ---------------------------------------------------------------------------
# Joueur
# ---------------------------------------------------------------------------

class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 28, 44)
        self.vx = 0.0; self.vy = 0.0
        self.on_ground = False
        self.facing = 1

        self.jumps_used = 0
        self.max_jumps = 2
        self.jump_history = deque()
        self.coyote = 0
        self.jump_buffer = 0

        self.dash_timer = 0
        self.dash_cooldown = 0
        self.dash_dir = 1
        self.dash_trail = deque(maxlen=10)

        self.swap_cooldown  = 0
        self.swap_invuln    = 0
        self.invuln         = 0
        self.dream_stay_t   = 0   # frames passées en rêve (max DREAM_MAX_STAY)

        self.max_hp = PLAYER_MAX_HP
        self.hp = self.max_hp

        self.dimension = DIM_REAL

        self.bow_cd = 0   # cooldown unique, plus de charge

        self.score = 0
        self.spawn = (x, y)
        self.frame = 0
        self.cape_history = deque(maxlen=12)
        # 9 segments de cape avec contraintes de distance
        self.cape_segments = [(x, y + 20 + i * 4) for i in range(9)]

    def center(self):
        return self.rect.center

    def respawn(self):
        self.rect.topleft = self.spawn
        self.vx = 0; self.vy = 0
        self.hp = self.max_hp
        self.dimension = DIM_REAL
        self.dash_timer = 0; self.dash_cooldown = 0
        self.swap_cooldown = 0; self.swap_invuln = 0; self.invuln = 0
        self.jumps_used = 0
        self.jump_history.clear()

    def press_jump(self, particles):
        self.jump_buffer = JUMP_BUFFER_FRAMES
        self.jump_history.append(self.frame)
        while self.jump_history and (self.frame - self.jump_history[0]) > TRIPLE_TAP_WINDOW:
            self.jump_history.popleft()

        if self.on_ground or self.coyote > 0:
            self.vy = JUMP_FORCE
            self.on_ground = False
            self.coyote = 0
            self.jumps_used = 1
            burst(particles, self.rect.centerx, self.rect.bottom, 8,
                  pal_part(self.dimension), 3.0, 18, 0.2, 3)
            return "JUMP"

        if self.jumps_used < self.max_jumps:
            self.vy = JUMP_FORCE * 0.92
            self.jumps_used += 1
            burst(particles, self.rect.centerx, self.rect.bottom, 12,
                  pal_part(self.dimension), 4.0, 22, 0.1, 3)
            return "DOUBLE"

        if len(self.jump_history) >= 3 and self.swap_cooldown <= 0:
            self.swap_dimension(particles)
            self.jump_history.clear()
            return "SWAP"
        return "NONE"

    def release_jump(self):
        if self.vy < -5:
            self.vy *= 0.55

    def try_dash(self, particles):
        if self.dash_cooldown <= 0 and self.dash_timer <= 0:
            self.dash_timer = DASH_FRAMES
            self.dash_cooldown = DASH_COOLDOWN
            self.dash_dir = self.facing
            self.invuln = max(self.invuln, DASH_FRAMES + 4)
            self.dash_trail.clear()
            burst(particles, self.rect.centerx, self.rect.centery, 14,
                  pal_part(self.dimension), 5.0, 20, 0.0, 3)
            return True
        return False

    def fire_bow(self, mouse_x, mouse_y, cam):
        """Tir d'arc unique. Plus de charge. Cooldown fixe pour anti-spam."""
        if self.bow_cd > 0: return None
        self.bow_cd = BOW_COOLDOWN
        tx = mouse_x + cam[0]
        ty = mouse_y + cam[1]
        cx, cy = self.rect.center
        dx, dy = tx - cx, ty - cy
        d = math.hypot(dx, dy) + 1e-6
        vx = dx / d * ARROW_SPEED
        vy = dy / d * ARROW_SPEED
        self.facing = 1 if vx >= 0 else -1
        return Arrow(cx, cy, vx, vy, dmg=BOW_DAMAGE, dim=self.dimension)

    def swap_dimension(self, particles):
        self.dimension = DIM_DREAM if self.dimension == DIM_REAL else DIM_REAL
        self.swap_cooldown = SWAP_COOLDOWN
        self.swap_invuln = SWAP_INVULN_FRAMES
        self.invuln = max(self.invuln, SWAP_INVULN_FRAMES)
        self.dream_stay_t = 0   # reset chrono à chaque switch
        cx, cy = self.rect.center
        burst(particles, cx, cy, 50, pal_part(self.dimension), 9.0, 45, 0.0, 5)
        burst(particles, cx, cy, 24, pal_accent(self.dimension), 6.0, 30, 0.0, 4)

    def hurt(self, dmg=1):
        if self.invuln > 0: return False
        self.hp -= dmg
        self.invuln = INVULN_FRAMES
        return True

    def update(self, keys, platforms, particles, pull_x=None, pull_y=None, pull_force=0.0):
        self.frame += 1
        if self.bow_cd > 0: self.bow_cd -= 1
        if self.dash_cooldown > 0: self.dash_cooldown -= 1
        if self.swap_cooldown > 0: self.swap_cooldown -= 1
        if self.swap_invuln > 0: self.swap_invuln -= 1
        if self.invuln > 0: self.invuln -= 1
        if self.dimension == DIM_DREAM:
            self.dream_stay_t = min(self.dream_stay_t + 1, DREAM_MAX_STAY + 60)
        else:
            self.dream_stay_t = 0
        if self.coyote > 0: self.coyote -= 1
        if self.jump_buffer > 0: self.jump_buffer -= 1

        # Mouvement (note : K_a est réservé au DASH, pas au mouvement gauche)
        if self.dash_timer > 0:
            self.vx = self.dash_dir * DASH_SPEED
            self.dash_timer -= 1
            self.dash_trail.append((self.rect.x, self.rect.y))
        else:
            left = keys[pygame.K_LEFT] or keys[pygame.K_q]
            right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
            target_vx = 0
            if left and not right:
                target_vx = -MOVE_SPEED; self.facing = -1
            elif right and not left:
                target_vx = MOVE_SPEED; self.facing = 1
            self.vx += (target_vx - self.vx) * 0.35

        # Force d'attraction du boss (phase 2)
        if pull_force > 0 and pull_x is not None and pull_y is not None and self.dash_timer <= 0:
            dx = pull_x - self.rect.centerx
            dy = pull_y - self.rect.centery
            d = math.hypot(dx, dy) + 1e-6
            self.vx += (dx / d) * pull_force
            self.vy += (dy / d) * pull_force * 0.6

        if self.dash_timer > 0:
            self.vy = 0
        else:
            self.vy += GRAVITY
            if self.vy > MAX_FALL: self.vy = MAX_FALL

        self.rect.x += int(round(self.vx))
        for p in platforms:
            if p.collides(self.dimension) and self.rect.colliderect(p.rect):
                if self.vx > 0: self.rect.right = p.rect.left
                elif self.vx < 0: self.rect.left = p.rect.right
                self.vx = 0

        was_on_ground = self.on_ground
        self.on_ground = False
        self.rect.y += int(round(self.vy))
        for p in platforms:
            if p.collides(self.dimension) and self.rect.colliderect(p.rect):
                if self.vy > 0:
                    self.rect.bottom = p.rect.top
                    self.on_ground = True
                    self.jumps_used = 0
                elif self.vy < 0:
                    self.rect.top = p.rect.bottom
                self.vy = 0

        if was_on_ground and not self.on_ground and self.vy >= 0:
            self.coyote = COYOTE_FRAMES

        if self.frame % 2 == 0:
            self.cape_history.append((self.rect.centerx, self.rect.centery + 6))
        self._update_cape()

    def _update_cape(self):
        if not self.cape_segments:
            return
        shoulder_x = self.rect.centerx - self.facing * 4
        shoulder_y = self.rect.y + 18
        self.cape_segments[0] = (shoulder_x, shoulder_y)
        seg_len = 5.0
        gravity_per_seg = 0.7
        for i in range(1, len(self.cape_segments)):
            px, py = self.cape_segments[i - 1]
            cx, cy = self.cape_segments[i]
            wind = math.sin(self.frame * 0.13 + i * 0.55) * 1.4
            target_x = px - self.facing * 1.6 - self.vx * 0.4 + wind
            target_y = py + gravity_per_seg
            nx = cx + (target_x - cx) * 0.32
            ny = cy + (target_y - cy) * 0.32
            dx, dy = nx - px, ny - py
            d = math.hypot(dx, dy) + 1e-6
            if d > seg_len:
                nx = px + dx / d * seg_len
                ny = py + dy / d * seg_len
            self.cape_segments[i] = (nx, ny)

    def draw(self, surf, cam):
        if self.dash_trail:
            for i, (tx, ty) in enumerate(self.dash_trail):
                alpha = int(40 + 120 * (i / max(1, len(self.dash_trail))))
                gh = pygame.Surface((self.rect.w, self.rect.h), pygame.SRCALPHA)
                pygame.draw.rect(gh, (*pal_accent(self.dimension), alpha),
                                 gh.get_rect(), border_radius=6)
                surf.blit(gh, (tx - cam[0], ty - cam[1]))

        if self.invuln > 0 and (self.invuln // 3) % 2 == 0:
            return

        body = pal_body(self.dimension)
        robe = pal_robe(self.dimension)
        cape = pal_cape(self.dimension)

        x = self.rect.x - cam[0]
        y = self.rect.y - cam[1]

        # CAPE chain physics
        if len(self.cape_segments) >= 3:
            n = len(self.cape_segments)
            left_pts = []
            right_pts = []
            for i, (sx, sy) in enumerate(self.cape_segments):
                width = max(2.0, 9.0 - i * 0.85)
                if i < n - 1:
                    nx2, ny2 = self.cape_segments[i + 1]
                    dx, dy = nx2 - sx, ny2 - sy
                else:
                    px2, py2 = self.cape_segments[i - 1]
                    dx, dy = sx - px2, sy - py2
                d = math.hypot(dx, dy) + 1e-6
                perp_x = -dy / d * width
                perp_y = dx / d * width
                left_pts.append((sx + perp_x - cam[0], sy + perp_y - cam[1]))
                right_pts.append((sx - perp_x - cam[0], sy - perp_y - cam[1]))
            poly = left_pts + list(reversed(right_pts))
            pygame.draw.polygon(surf, cape, poly)
            pygame.draw.polygon(surf, pal_accent(self.dimension), poly, 1)
            center_pts = [(sx - cam[0], sy - cam[1]) for sx, sy in self.cape_segments]
            if len(center_pts) >= 2:
                darker = tuple(max(0, c - 30) for c in cape)
                pygame.draw.lines(surf, darker, False, center_pts, 1)

        # ROBE / CORPS
        pygame.draw.rect(surf, robe, (x + 2, y + 18, self.rect.w - 4, self.rect.h - 18), border_radius=6)
        pygame.draw.circle(surf, body, (x + self.rect.w // 2, y + 14), 12)
        pygame.draw.arc(surf, robe, (x - 2, y - 2, self.rect.w + 4, 32),
                        math.radians(20), math.radians(160), 6)
        ex = x + self.rect.w // 2 + 3 * self.facing
        pygame.draw.circle(surf, Pal.P_EYE, (ex, y + 14), 2)

        # Aura swap
        if self.swap_invuln > 0:
            t = self.swap_invuln / SWAP_INVULN_FRAMES
            r = int(28 + (1 - t) * 30)
            a = int(120 * t)
            s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(s, (*pal_accent(self.dimension), a), (r + 2, r + 2), r, 3)
            surf.blit(s, (x + self.rect.w // 2 - r - 2, y + self.rect.h // 2 - r - 2))


# ---------------------------------------------------------------------------
# Plateformes
# ---------------------------------------------------------------------------

class Platform:
    def __init__(self, x, y, w, h, dim_only=None, kind="ground"):
        self.rect = pygame.Rect(x, y, w, h)
        self.dim_only = dim_only
        self.kind = kind

    def collides(self, dim):
        return self.dim_only is None or self.dim_only == dim

    def draw(self, surf, cam, current_dim):
        active = self.collides(current_dim)
        rect = self.rect.move(-cam[0], -cam[1])
        if not active:
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            ghost_dim = self.dim_only
            base = pal_ground(ghost_dim)
            pygame.draw.rect(s, (*base, 50), s.get_rect(), border_radius=4)
            for i in range(0, rect.h, 6):
                pygame.draw.line(s, (*base, 40), (0, i), (rect.w, i), 1)
            surf.blit(s, rect.topleft)
            return
        base = pal_ground(current_dim)
        edge = pal_ground_e(current_dim)
        pygame.draw.rect(surf, base, rect, border_radius=4)
        pygame.draw.rect(surf, edge, rect, width=3, border_radius=4)


# ---------------------------------------------------------------------------
# Fragments orbitaux (phase 4)
# ---------------------------------------------------------------------------

class MoonFragment:
    """Fragment orbital de la phase 4. Le radius est calculé à partir d'un
    base_radius (l'orbite stable) + une oscillation, ce qui empêche les
    dérives à long terme. Le contract (quand des fragments meurent) ne
    réduit que la base, jamais en dessous du minimum."""
    def __init__(self, center, angle, radius, dim):
        self.center = center
        self.angle = angle
        self.base_radius = float(radius)
        self.radius = float(radius)
        self.r = 28
        self.dim = dim
        self.hp = 22   # plus tanky pour compenser dmg arc augmenté
        self.dead = False
        self.angular = 0.014
        self.min_radius = 110   # ne se rapproche jamais plus que ça
        self.max_radius = 280   # ne s'éloigne jamais plus que ça

    @property
    def x(self): return self.center[0] + math.cos(self.angle) * self.radius
    @property
    def y(self): return self.center[1] + math.sin(self.angle) * self.radius

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.r, int(self.y) - self.r, self.r * 2, self.r * 2)

    def center_xy(self):
        return (int(self.x), int(self.y))

    def update(self, particles, contract=0.0):
        self.angle += self.angular
        # contract réduit l'orbite (les fragments restants se rapprochent du centre)
        self.base_radius -= contract
        self.base_radius = max(self.min_radius, min(self.max_radius, self.base_radius))
        # Oscillation visible (12px) autour de la base, qui ne dérive jamais
        self.radius = self.base_radius + math.sin(self.angle * 1.5) * 12.0

    def hurt(self, dmg, current_dim):
        if self.dim != current_dim: return False
        self.hp -= dmg
        if self.hp <= 0:
            self.dead = True
        return True

    def draw(self, surf, cam, current_dim):
        cx, cy = int(self.x - cam[0]), int(self.y - cam[1])
        active = (self.dim == current_dim)
        col_main = Pal.MOON_LIGHT if self.dim == DIM_REAL else Pal.MOON_CRESC_D
        col_dark = Pal.MOON_DARK if self.dim == DIM_REAL else (200, 100, 60)
        if not active:
            s = pygame.Surface((self.r * 2 + 6, self.r * 2 + 6), pygame.SRCALPHA)
            pygame.draw.circle(s, (*col_main, 70), (self.r + 3, self.r + 3), self.r, 2)
            surf.blit(s, (cx - self.r - 3, cy - self.r - 3))
            return
        pygame.draw.circle(surf, col_main, (cx, cy), self.r)
        pygame.draw.circle(surf, col_dark, (cx + 6, cy + 4), 5)
        pygame.draw.circle(surf, col_dark, (cx - 8, cy - 6), 4)
        pygame.draw.circle(surf, col_dark, (cx - 2, cy + 9), 3)


# ---------------------------------------------------------------------------
# BOSS : LA LUNE
# ---------------------------------------------------------------------------

PHASE_THRESHOLDS = {1: 1.00, 2: 0.80, 3: 0.60, 4: 0.40, 5: 0.20}
# HP de la phase dans la barre (low inclus, high = début de phase)
PHASE_HP_RANGES  = {1: (800, 1000), 2: (600, 800), 3: (400, 600), 4: (200, 400), 5: (0, 200)}

PHASE_NAMES = {
    1: "L'ŒIL INSOMNIAQUE",
    2: "LA MARÉE",
    3: "L'ÉCLIPSE",
    4: "LA COURONNE BRISÉE",
    5: "LE CROISSANT INVERSÉ",
}


class MoonBoss:
    def __init__(self, center_x, center_y, game):
        self.cx = center_x; self.cy = center_y
        self.x = center_x; self.y = -120
        self.target_x = center_x; self.target_y = center_y - 140
        self.radius = 70
        self.max_hp_total = 1000   # 200 HP par phase × 5
        self.hp = self.max_hp_total
        self.phase = 1
        self.state = "intro"
        self.intro_t = 0
        self.transition_t = 0
        self.next_phase = 1
        self.attack_timer = 60
        self.subattack_timer = 0
        # Pour le mode Sans en phase 5 : 2e timer d'attaque en parallèle
        self.gaster_timer = 0
        # Sous-phase enragée à <6% HP (phase 5 final form)
        self.final_form = False
        self.dim = DIM_REAL
        self.dim_timer = 0
        self.dead = False
        self.fragments = []
        self.float_offset = 0.0
        self.bob_t = 0.0
        self.hit_flash = 0
        self.stun_timer = 0
        self.face_state = "calm"
        self.eye_offset = (0, 0)
        self.game = game
        self.attacks_since_judgment = 0   # compteur pour déclencher Jugement Lunaire
        self.last_resort_active = False
        self.last_resort_t      = 0
        self.last_resort_done   = False

        # Chargement du sprite de la Lune (moon_sprite.png dans le même dossier)
        _base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        _sprite_path = os.path.join(_base_dir, "assets", "images", "moon_sprite.png")
        try:
            _raw = pygame.image.load(_sprite_path).convert_alpha()
            # Pré-scale à la taille du boss (radius*2 x radius*2)
            self._moon_sprite = pygame.transform.scale(_raw, (self.radius * 2, self.radius * 2))
        except Exception:
            self._moon_sprite = None  # fallback dessin procédural si fichier absent

        # Compteurs de pattern rotatif par phase
        self.p1_step = 0
        self.p2_step = 0
        self.p3_step = 0
        self.p4_sub_step = 0
        self.p5_step = 0

        self.ax_left = -180
        self.ax_right = 1480
        self.ay_top = -200
        self.ay_bottom = 720

    @property
    def rect(self):
        return pygame.Rect(int(self.x) - self.radius, int(self.y) - self.radius,
                           self.radius * 2, self.radius * 2)

    def center(self):
        return (int(self.x), int(self.y))

    def update(self, player, beams, projectiles, rings, telegraphs, particles):
        self.bob_t += 0.04
        if self.hit_flash > 0: self.hit_flash -= 1
        if self.stun_timer > 0:
            self.stun_timer -= 1
            return

        if self.state == "intro":
            self._update_intro(player, beams, telegraphs, particles)
        elif self.state == "fighting":
            t_phase = self._compute_target_phase()
            if t_phase != self.phase:
                self.state = "transition"
                self.transition_t = 0
                self.next_phase = t_phase
                self._start_desperate(self.phase, beams, projectiles, rings, telegraphs, particles, player)
            else:
                self._update_phase(player, beams, projectiles, rings, telegraphs, particles)
        elif self.state == "transition":
            self._update_transition(player, beams, projectiles, rings, telegraphs, particles)

        self.float_offset = math.sin(self.bob_t) * 12
        dx = player.rect.centerx - self.x
        dy = player.rect.centery - self.y
        d = math.hypot(dx, dy) + 1e-6
        self.eye_offset = (dx / d * 4, dy / d * 4)

    def _compute_target_phase(self):
        frac = self.hp / self.max_hp_total
        for p in (5, 4, 3, 2):
            if frac <= PHASE_THRESHOLDS[p]:
                return p
        return 1

    # ------------------------------------------------------------------
    # INTRO
    # ------------------------------------------------------------------
    def _update_intro(self, player, beams, telegraphs, particles):
        self.intro_t += 1
        if self.intro_t < 90:
            t = self.intro_t / 90.0
            self.y = -120 + (self.target_y - (-120)) * (1 - (1 - t) ** 3)
            self.x = self.target_x
            if self.intro_t % 3 == 0:
                burst(particles, self.x, self.y, 4, Pal.MOON_GLOW, 3.0, 30, 0.05, 3)
        elif self.intro_t == 90:
            self.game.announce_phase(PHASE_NAMES[1])
        elif self.intro_t == 150:
            # Le jeu commence directement par un Jugement Stellaire
            self._cast_lunar_judgment(beams, telegraphs, particles, player)
        elif self.intro_t >= 440:
            self.state = "fighting"
            self.face_state = "calm"
            self.attack_timer = 60
            self.p1_step = 0

    def _cast_giant_beam_v(self, target_x, beams, telegraphs, particles):
        """ÉNORME rayon vertical d'ouverture : 280px, 3 dmg, gros tell."""
        width = 280
        def fire():
            rect = pygame.Rect(target_x - width // 2, self.ay_top,
                               width, self.ay_bottom - self.ay_top + 400)
            beams.append(Beam(rect, DIM_REAL, life=42, dmg=3, color=(255, 240, 210)))
            for px in range(-width // 2, width // 2 + 1, 18):
                burst(particles, target_x + px, 220, 14, Pal.BEAM_FILL, 9.0, 50, 0.05, 5)
                burst(particles, target_x + px, 500, 14, Pal.BEAM_EDGE, 9.0, 50, 0.05, 5)
            self.game.add_shake(22, 45)
        telegraphs.append(Telegraph("beam_v", 110, DIM_REAL, on_fire=fire,
                                    color=Pal.TELEGRAPH_S, x=target_x,
                                    top=self.ay_top, bottom=self.ay_bottom + 400,
                                    final_width=width))

    # ------------------------------------------------------------------
    # PHASE
    # ------------------------------------------------------------------
    def _update_phase(self, player, beams, projectiles, rings, telegraphs, particles):
        if self.phase == 1: self._update_p1(player, beams, projectiles, rings, telegraphs, particles)
        elif self.phase == 2: self._update_p2(player, beams, projectiles, rings, telegraphs, particles)
        elif self.phase == 3: self._update_p3(player, beams, projectiles, rings, telegraphs, particles)
        elif self.phase == 4: self._update_p4(player, beams, projectiles, rings, telegraphs, particles)
        elif self.phase == 5: self._update_p5(player, beams, projectiles, rings, telegraphs, particles)

    # ---- PHASE 1 : L'ŒIL INSOMNIAQUE ----
    def _update_p1(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "calm"
        target_x = max(self.ax_left + 200, min(self.ax_right - 200, player.rect.centerx))
        self._drift_to(target_x, self.target_y, 1.9)
        self.attack_timer -= 1
        if self.attack_timer <= 0:
            self.attacks_since_judgment += 1
            # Jugement Lunaire toutes les 4 attaques (cycle complet)
            if self.attacks_since_judgment >= 4:
                self._cast_lunar_judgment(beams, telegraphs, particles, player)
                self.attacks_since_judgment = 0
                self.p1_step = 0  # repart du début après le jugement
                self.attack_timer = 220
                return
            # Séquence rotative : fan → meteor → fan → star_curtain
            P1_SEQ = ["fan", "meteor", "fan", "star_curtain"]
            choice = P1_SEQ[self.p1_step % len(P1_SEQ)]
            self.p1_step += 1
            if choice == "fan":
                self._tg_crescent_fan(player, projectiles, telegraphs, dim=DIM_REAL, hits_any_dim=True)
                self.attack_timer = 65
            elif choice == "meteor":
                self._tg_meteor_targets(player, projectiles, telegraphs, particles, hits_any_dim=True)
                self.attack_timer = 85
            else:  # star_curtain
                self._tg_star_curtain(player, projectiles, telegraphs, hits_any_dim=True)
                self.attack_timer = 110

    def _cast_lunar_judgment(self, beams, telegraphs, particles, player):
        """LE JUGEMENT STELLAIRE : chaîne de 6 ÉNORMES rayons (320px chacun)
        qui balayent l'arène en cascade rapide non-linéaire. Très brutal."""
        self.face_state = "open"
        self.game.announce_phase("JUGEMENT STELLAIRE")
        self.game.add_shake(10, 20)
        width = 320
        base_left = self.ax_left + 200
        base_right = self.ax_right - 200
        step = (base_right - base_left) / 5
        sequence = [0, 3, 1, 4, 2, 5]
        positions = [(base_left + i * step, idx) for idx, i in enumerate(sequence)]
        cascade_delay = 30
        tg_base = 60
        for tx, idx in positions:
            delay = 20 + idx * cascade_delay
            def make_fire(tx=tx):
                def fire():
                    rect = pygame.Rect(tx - width // 2, self.ay_top,
                                       width, self.ay_bottom - self.ay_top + 400)
                    # hits_any_dim=True : inévitable par changement de dimension
                    beams.append(Beam(rect, DIM_REAL, life=32, dmg=3,
                                      color=(255, 240, 210), hits_any_dim=True))
                    burst(particles, tx, 280, 35, Pal.BEAM_FILL, 9.0, 50, 0.05, 5)
                    burst(particles, tx, 540, 35, Pal.BEAM_EDGE, 9.0, 50, 0.05, 5)
                    self.game.add_shake(16, 22)
                return fire
            telegraphs.append(Telegraph("beam_v", delay + tg_base, DIM_REAL,
                                        on_fire=make_fire(),
                                        color=Pal.TELEGRAPH_S, x=tx,
                                        top=self.ay_top, bottom=self.ay_bottom + 400,
                                        final_width=width))

    # ---- PHASE 2 : LA MARÉE ----
    def _update_p2(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "tense"
        self.dim_timer -= 1
        if self.dim_timer <= 0:
            self.dim = DIM_DREAM if self.dim == DIM_REAL else DIM_REAL
            self.dim_timer = 230
            burst(particles, self.x, self.y, 40, pal_accent(self.dim), 6.0, 40, 0.0, 4)
        ang = self.bob_t * 0.6
        target_x = self.cx + math.cos(ang) * 320
        target_y = self.target_y + math.sin(ang * 1.3) * 50
        self._drift_to(target_x, target_y, 2.6)

        self.attack_timer -= 1
        if self.attack_timer <= 0:
            # Séquence rotative : vague → éventail → guidées → éventail
            P2_SEQ = ["wave", "fan_dim", "homing", "fan_dim"]
            choice = P2_SEQ[self.p2_step % len(P2_SEQ)]
            self.p2_step += 1
            if choice == "wave":
                self._tg_tide_wave(player, beams, telegraphs)
                self.attack_timer = 80
            elif choice == "homing":
                # Réduit à 2 orbes (une par dimension)
                self._fire_homing_orb(player, projectiles, DIM_REAL)
                self._fire_homing_orb(player, projectiles, DIM_DREAM)
                self.attack_timer = 55
            else:  # fan_dim
                self._tg_crescent_fan(player, projectiles, telegraphs, dim=self.dim, count=8)
                self.attack_timer = 60

    # ---- PHASE 3 : L'ÉCLIPSE ----
    def _update_p3(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "tense"
        self._drift_to(self.cx, self.target_y - 30, 1.7)
        self.attack_timer -= 1
        if self.attack_timer <= 0:
            px, py = player.rect.centerx, player.rect.centery
            step = self.p3_step % 6
            self.p3_step += 1
            if step == 0:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=65, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 75
            elif step == 1:
                ty = max(120, min(580, py))
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=65, height=70, dmg=3, hits_any_dim=True)
                self.attack_timer = 75
            elif step == 2:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + 220))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=60, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 70
            elif step == 3:
                ty = max(120, min(580, py - 110))
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=60, height=70, dmg=3, hits_any_dim=True)
                self.attack_timer = 70
            elif step == 4:
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px - 220))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=60, width=85, dmg=3, hits_any_dim=True)
                self.attack_timer = 70
            else:
                # Croix finale — les deux rayons couvrent les deux dimensions
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-50, 50)))
                ty = max(120, min(580, py + random.randint(-30, 30)))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=65, width=75, dmg=3, hits_any_dim=True)
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=65, height=65, dmg=3, hits_any_dim=True)
                self.attack_timer = 90

    # ---- PHASE 4 : LA COURONNE BRISÉE ----
    def _update_p4(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "crack"
        self._drift_to(self.cx, self.target_y - 40, 1.4)

        if not self.fragments:
            for i in range(4):
                a = i * math.pi / 2 - math.pi / 2
                dim = DIM_REAL if i % 2 == 0 else DIM_DREAM
                self.fragments.append(MoonFragment((self.cx, self.cy - 60), a, 210, dim))

        alive = [f for f in self.fragments if not f.dead]
        if not alive:
            self.hp = min(self.hp, self.max_hp_total * (PHASE_THRESHOLDS[5] - 0.001))
            return

        # Contract : les fragments restants se rapprochent à mesure que les
        # autres meurent. Limité par min_radius dans MoonFragment.update
        # → plus de dérive infinie, les fragments restent toujours dans
        # une zone raisonnable autour du boss.
        contract = max(0.0, 0.15 * (4 - len(alive)))
        for f in self.fragments:
            if not f.dead:
                f.update(particles, contract=contract)

        self.attack_timer -= 1
        if self.attack_timer <= 0:
            for f in alive:
                self._fragment_shot(f, projectiles, telegraphs)
            # Tous les 2 tirs de fragments, le boss attaque aussi
            if self.p4_sub_step % 2 == 1:
                if self.p4_sub_step % 4 == 1:
                    # Éventail court depuis le boss
                    self._tg_crescent_fan(player, projectiles, telegraphs,
                                          dim=DIM_REAL, count=5, spread_deg=55)
                else:
                    # Paire d'orbes guidées (une par dimension)
                    self._fire_homing_orb(player, projectiles, DIM_REAL)
                    self._fire_homing_orb(player, projectiles, DIM_DREAM)
            self.p4_sub_step += 1
            self.attack_timer = max(40, 78 - 10 * (4 - len(alive)))

    # ---- PHASE 5 : LE CROISSANT INVERSÉ — CHORÉGRAPHIE EN 6 ÉTAPES ----
    def _update_p5(self, player, beams, projectiles, rings, telegraphs, particles):
        self.face_state = "rage"

        # ── DERNIERS RECOURS : < 100 HP, une seule fois ──────────────────────
        if self.hp < 100 and not self.last_resort_done:
            self.last_resort_done   = True
            self.last_resort_active = True
            self.last_resort_t      = 0
            self.game.announce_phase("DERNIERS RECOURS")
            self.game.add_shake(24, 60)
            self.game.start_slowmo(35)

        if self.last_resort_active:
            self._update_last_resort(beams, telegraphs, particles)
            return   # pas d'autres attaques pendant la séquence

        if not self.final_form and self.hp / self.max_hp_total < 0.06:
            self.final_form = True
            self.game.announce_phase("DERNIER SOUFFLE")
            self.game.add_shake(20, 30)
            self.game.start_slowmo(20)

        self._drift_to(self.cx + math.sin(self.bob_t * 0.7) * 100, self.target_y + 40, 2.6)

        # Changement de dimension régulier (toujours lisible)
        self.dim_timer -= 1
        if self.dim_timer <= 0:
            self.dim = DIM_DREAM if self.dim == DIM_REAL else DIM_REAL
            self.dim_timer = 90 if self.final_form else 115

        # ── SÉQUENCE PRINCIPALE (6 étapes fixes, difficile mais apprenables) ──
        self.attack_timer -= 1
        if self.attack_timer <= 0:
            # Téléportation entre les étapes seulement (25% de chance) → lisible
            if random.random() < 0.25:
                tgt_x = random.uniform(self.ax_left + 220, self.ax_right - 220)
                tgt_y = random.uniform(self.target_y - 60, self.target_y + 80)
                burst(particles, self.x, self.y, 25, (180, 50, 140), 6.0, 25, 0.0, 3)
                self.x = tgt_x
                self.y = tgt_y
                burst(particles, self.x, self.y, 25, (180, 50, 140), 6.0, 25, 0.0, 3)

            step = self.p5_step % 6
            self.p5_step += 1
            # En final form : cadence 40% plus rapide
            spd = 0.6 if self.final_form else 1.0
            px, py = player.rect.center

            if step == 0:
                # Étape 0 — CROIX : vertical + horizontal simultanés
                # Le joueur doit se mettre dans un coin : pattern le plus lisible
                tx = max(self.ax_left + 100, min(self.ax_right - 100, px + random.randint(-70, 70)))
                ty = max(130, min(570, py + random.randint(-35, 35)))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=72, width=82, dmg=2)
                self._tg_beam_horizontal(ty, beams, telegraphs, dim=DIM_REAL, duration=72, height=68, dmg=2)
                self.attack_timer = int(88 * spd)

            elif step == 1:
                # Étape 1 — GRAND ÉVENTAIL
                count = 12 if self.final_form else 10
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=self.dim, count=count, spread_deg=128)
                self.attack_timer = int(62 * spd)

            elif step == 2:
                # Étape 2 — ORBES GUIDÉES (une par dimension, apprend la mécanique de dimension)
                self._fire_homing_orb(player, projectiles, DIM_REAL)
                self._fire_homing_orb(player, projectiles, DIM_DREAM)
                if self.final_form:
                    self._fire_homing_orb(player, projectiles, self.dim)
                self.attack_timer = int(58 * spd)

            elif step == 3:
                # Étape 3 — GASTERS CARDINAUX (depuis N, S, E, O → prévisible)
                n = 5 if self.final_form else 4
                self._cast_gaster_blasters(player, beams, telegraphs, particles, n=n)
                self.attack_timer = int(72 * spd)

            elif step == 4:
                # Étape 4 — RIDEAU D'ÉTOILES (réduit, plus lent)
                self._tg_star_curtain(player, projectiles, telegraphs, hits_any_dim=True)
                self.attack_timer = int(82 * spd)

            else:
                # Étape 5 — DOUBLE ÉVENTAIL (real + dream simultanés) → fin de cycle
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=DIM_REAL, count=8, spread_deg=100)
                self._tg_crescent_fan(player, projectiles, telegraphs,
                                      dim=DIM_DREAM, count=8, spread_deg=100)
                self.attack_timer = int(58 * spd)

        # ── ORBE PARRY : cadence fixe, toujours viseuse → apprenable ──
        self.subattack_timer -= 1
        if self.subattack_timer <= 0:
            self._fire_parry_orb(player, projectiles)
            self.subattack_timer = int(38 * (0.65 if self.final_form else 1.0))

        # ── PLUIE DU CIEL (final form uniquement) ──
        if self.final_form:
            if not hasattr(self, "_p5_sky_timer"):
                self._p5_sky_timer = 0
            self._p5_sky_timer -= 1
            if self._p5_sky_timer <= 0:
                self._cast_sky_gaster_rain(player, beams, telegraphs, particles)
                self._p5_sky_timer = 95

    def _cast_sky_gaster_rain(self, player, beams, telegraphs, particles):
        """PHASE 5 final form : pluie de 3 gaster blasters verticaux qui
        tombent du ciel à des positions aléatoires. Très peu de tell."""
        for _ in range(3):
            tx = random.uniform(self.ax_left + 100, self.ax_right - 100)
            width = 80
            def make_fire(tx=tx, w=width):
                def fire():
                    rect = pygame.Rect(int(tx - w / 2), self.ay_top,
                                       int(w), self.ay_bottom - self.ay_top + 400)
                    beams.append(Beam(rect, DIM_REAL, life=18, dmg=2,
                                      color=(255, 130, 200)))
                    burst(particles, tx, 360, 22, (255, 100, 180),
                          7.0, 32, 0.05, 4)
                    self.game.add_shake(10, 14)
                return fire
            telegraphs.append(Telegraph("beam_v", 40, DIM_REAL,
                                        on_fire=make_fire(),
                                        color=(255, 60, 130),
                                        x=tx, top=self.ay_top, bottom=self.ay_bottom + 400,
                                        final_width=width))

    def _cast_gaster_blasters(self, player, beams, telegraphs, particles, n=2):
        """Mini-rayons "gaster" : depuis un point hors-écran, on charge
        rapidement un beam directionnel vers le joueur."""
        px, py = player.rect.center
        for i in range(n):
            # point d'origine : sur un cercle autour du boss à grande distance
            ang = random.uniform(0, math.tau)
            ox = self.x + math.cos(ang) * 380
            oy = self.y + math.sin(ang) * 380
            # le rayon vise le joueur depuis ce point
            dx = px - ox; dy = py - oy
            d = math.hypot(dx, dy) + 1e-6
            # Le beam est rectangulaire orienté — on simule en faisant un beam_h
            # ou beam_v selon l'orientation dominante
            length = 1200
            thickness = 60
            # Pour simplifier : on tire toujours un rayon vertical
            # localisé sur l'X de l'origine, mais à courte distance, le tell
            # est très bref → vraiment sansien
            tx = ox
            def make_fire(tx=tx, oy=oy):
                def fire():
                    rect = pygame.Rect(int(tx) - thickness // 2,
                                       int(oy) - length // 2,
                                       thickness, length)
                    beams.append(Beam(rect, DIM_REAL, life=18, dmg=2,
                                      color=(255, 180, 220)))
                    burst(particles, tx, oy, 24, (255, 100, 180),
                          6.0, 28, 0.05, 4)
                    self.game.add_shake(8, 12)
                return fire
            # telegraph court : Sans-style, peu de temps pour réagir
            telegraphs.append(Telegraph("beam_v", 35, DIM_REAL,
                                        on_fire=make_fire(),
                                        color=(255, 90, 170),
                                        x=tx,
                                        top=oy - length / 2,
                                        bottom=oy + length / 2,
                                        final_width=thickness))

    # ------------------------------------------------------------------
    # ATTAQUES AVEC TELEGRAPH
    # ------------------------------------------------------------------
    def _tg_crescent_fan(self, player, projectiles, telegraphs, dim=DIM_REAL,
                         count=7, spread_deg=70, hits_any_dim=False):
        tx, ty = player.rect.center
        dx, dy = tx - self.x, ty - self.y
        base_ang = math.atan2(dy, dx)
        spread = math.radians(spread_deg)
        ox, oy = self.x, self.y
        ph = self
        col = (Pal.MOON_CRESC_R if dim == DIM_REAL else Pal.MOON_CRESC_D)
        def fire():
            for i in range(count):
                t = i / (count - 1) if count > 1 else 0.5
                ang = base_ang - spread / 2 + spread * t
                sp = 6.2
                projectiles.append(BossProjectile(
                    ph.x, ph.y,
                    math.cos(ang) * sp, math.sin(ang) * sp,
                    dim=dim, radius=12, life=220, kind="crescent", color=col,
                    hits_any_dim=hits_any_dim, dmg=1
                ))
        telegraphs.append(Telegraph("fan", 45, dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, x=ox, y=oy,
                                    angle=base_ang, spread=spread, count=count, length=800))

    def _tg_meteor_targets(self, player, projectiles, telegraphs, particles, hits_any_dim=False):
        n = 5
        for i in range(n):
            tx = player.rect.centerx + random.randint(-260, 260) + i * 30
            ty = 580
            d = random.choice([DIM_REAL, DIM_DREAM])
            color = Pal.METEOR_CORE if d == DIM_REAL else (255, 200, 230)
            def make_fire(tx=tx, ty=ty, d=d, color=color, had=hits_any_dim):
                def fire():
                    projectiles.append(BossProjectile(
                        tx + random.uniform(-20, 20), -50,
                        random.uniform(-1.5, 1.5), 8.5,
                        dim=d, radius=14, life=200, kind="meteor", color=color,
                        hits_any_dim=had, dmg=1
                    ))
                return fire
            telegraphs.append(Telegraph("circle", 60 + i * 8, d, on_fire=make_fire(),
                                        color=Pal.TELEGRAPH, x=tx, y=ty, r=40))

    def _tg_lullaby_ring(self, player, rings, telegraphs, hits_any_dim=False):
        ox, oy = self.x, self.y
        dim = DIM_REAL
        def fire():
            rings.append(Ring(ox, oy, dim, max_r=560, life=95,
                              color=Pal.MOON_GLOW, hits_any_dim=hits_any_dim))
        telegraphs.append(Telegraph("ring", 50, dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, x=ox, y=oy, r=560))

    def _tg_star_curtain(self, player, projectiles, telegraphs, hits_any_dim=False):
        y_line = 80
        gap1 = random.randint(int(self.ax_left + 200), int(self.ax_right - 200))
        gap2 = gap1 + random.choice([-380, 380])
        gaps = [gap1, gap2]
        left = self.ax_left
        right = self.ax_right
        def fire():
            n = 13  # divisé par 2 (était 26)
            for i in range(n):
                t = i / (n - 1)
                px = left + (right - left) * t
                if any(abs(px - g) < 70 for g in gaps):
                    continue
                projectiles.append(BossProjectile(
                    px, y_line, 0, 4.5,
                    dim=DIM_REAL, radius=7, life=280, kind="star",
                    color=(255, 230, 180), hits_any_dim=hits_any_dim, dmg=2
                ))
        telegraphs.append(Telegraph("star_curtain", 70, DIM_REAL, on_fire=fire,
                                    color=Pal.TELEGRAPH, y=y_line, left=left, right=right, gaps=gaps))

    def _tg_tide_wave(self, player, beams, telegraphs):
        y = 540
        dim = self.dim
        left = self.ax_left
        right = self.ax_right
        def fire():
            rect = pygame.Rect(int(left), int(y - 30), int(right - left), 60)
            beams.append(Beam(rect, dim, life=22,
                              color=(Pal.MOON_GLOW if dim == DIM_REAL else (255, 180, 220))))
        telegraphs.append(Telegraph("beam_h", 50, dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, y=y, left=left, right=right,
                                    final_height=60))

    def _tg_beam_vertical(self, x, beams, telegraphs, dim=DIM_REAL, duration=70, width=70, dmg=3, hits_any_dim=False):
        def fire():
            rect = pygame.Rect(int(x - width / 2), self.ay_top,
                               int(width), self.ay_bottom - self.ay_top + 400)
            beams.append(Beam(rect, dim, life=22, dmg=dmg, hits_any_dim=hits_any_dim))
        telegraphs.append(Telegraph("beam_v", duration, dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, x=x,
                                    top=self.ay_top, bottom=self.ay_bottom + 400,
                                    final_width=width))

    def _tg_beam_horizontal(self, y, beams, telegraphs, dim=DIM_REAL, duration=70, height=60, dmg=3, hits_any_dim=False):
        def fire():
            rect = pygame.Rect(self.ax_left, int(y - height / 2),
                               self.ax_right - self.ax_left, int(height))
            beams.append(Beam(rect, dim, life=22, dmg=dmg, hits_any_dim=hits_any_dim))
        telegraphs.append(Telegraph("beam_h", duration, dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, y=y,
                                    left=self.ax_left, right=self.ax_right,
                                    final_height=height))

    def _fire_homing_orb(self, player, projectiles, dim):
        ang = random.uniform(0, math.tau)
        sp = 3.0
        projectiles.append(BossProjectile(
            self.x, self.y,
            math.cos(ang) * sp, math.sin(ang) * sp,
            dim=dim, radius=11, life=320, homing=0.13, target=player,
            kind="orb", dmg=1,
            color=(Pal.MOON_GLOW if dim == DIM_REAL else (255, 150, 220))
        ))

    def _fire_parry_orb(self, player, projectiles):
        ang = math.atan2(player.rect.centery - self.y, player.rect.centerx - self.x)
        sp = 4.8
        projectiles.append(BossProjectile(
            self.x, self.y,
            math.cos(ang) * sp, math.sin(ang) * sp,
            dim=self.dim, radius=14, life=260, kind="orb",
            color=(255, 120, 200), parry=True
        ))

    def _fragment_shot(self, frag, projectiles, telegraphs):
        def fire():
            for off in (-0.25, 0, 0.25):
                a = math.atan2(frag.y - (self.cy - 60), frag.x - self.cx) + off
                sp = 5.3
                projectiles.append(BossProjectile(
                    frag.x, frag.y,
                    math.cos(a) * sp, math.sin(a) * sp,
                    dim=frag.dim, radius=10, life=200, kind="orb", dmg=1,
                    color=(Pal.MOON_GLOW if frag.dim == DIM_REAL else (255, 160, 220))
                ))
        telegraphs.append(Telegraph("fan", 35, frag.dim, on_fire=fire,
                                    color=Pal.TELEGRAPH, x=frag.x, y=frag.y,
                                    angle=math.atan2(frag.y - (self.cy - 60), frag.x - self.cx),
                                    spread=math.radians(40), count=3, length=600))

    def parry_hit(self, particles):
        self.stun_timer = 60
        self.hit_flash = 30
        burst(particles, self.x, self.y, 36, (255, 120, 200), 7.0, 35, 0.0, 4)
        self.hp -= 12
        if self.hp < 0: self.hp = 0
        return True

    def _update_last_resort(self, beams, telegraphs, particles):
        """Séquence Derniers Recours : 6 secondes (360 frames) invincible.
        Un rayon colossal couvrant toute l'arène se déclenche à t=80."""
        self.last_resort_t += 1
        t = self.last_resort_t

        # Montée en tension : éclairs de particules et secousses
        if t < 80:
            if t % 10 == 0:
                burst(particles, self.x, self.y, 22, (255, 70, 20), 9.0, 28, 0.0, 5)
            if t % 25 == 0:
                self.game.add_shake(12, 18)

        # À t=80 : tir du rayon colossal (toute l'arène, toutes dimensions)
        if t == 80:
            rect = pygame.Rect(int(self.ax_left),
                               int(self.ay_top),
                               int(self.ax_right - self.ax_left),
                               int(self.ay_bottom - self.ay_top + 600))
            beams.append(Beam(rect, DIM_REAL, life=55, dmg=10,
                              hits_any_dim=True, color=(255, 50, 20)))
            burst(particles, self.x, self.y, 90, (255, 100, 40), 14.0, 55, 0.0, 6)
            self.game.add_shake(35, 50)
            self.game.start_slowmo(25)

        # Fin de la séquence (6 sec = 360 frames)
        if t >= 360:
            self.last_resort_active = False

    def display_bar_fraction(self):
        """Fraction d'affichage : 0→1 dans la phase courante.
        Pendant transition : se vide puis se remplit pour la nouvelle phase."""
        if self.state == "intro":
            return 1.0
        if self.state == "transition":
            t = self.transition_t
            if t < 35:
                return max(0.0, 1.0 - t / 35)   # vide en 35 frames
            if t < 75:
                return 0.0
            k = (t - 75) / 35
            return min(1.0, k ** 0.5)             # remplissage rapide
        low, high = PHASE_HP_RANGES.get(self.phase, (0, 1))
        span = max(1, high - low)
        return max(0.0, min(1.0, (self.hp - low) / span))

    def _start_desperate(self, phase, beams, projectiles, rings, telegraphs, particles, player):
        self.game.start_slowmo(20)
        burst(particles, self.x, self.y, 50, Pal.MOON_GLOW, 8.0, 50, 0.0, 5)

        if phase == 1:
            for i in range(32):
                px = self.ax_left + i * (self.ax_right - self.ax_left) / 32 + random.uniform(-20, 20)
                projectiles.append(BossProjectile(
                    px, -50 + random.randint(-40, 40),
                    random.uniform(-0.6, 0.6), random.uniform(5.5, 7.5),
                    dim=DIM_REAL, radius=7, life=240, kind="star", color=(255, 220, 160), dmg=2
                ))
        elif phase == 2:
            for k, ang_off in enumerate((-30, 0, 30)):
                count = 12
                spread = math.radians(150)
                base_ang = math.radians(90 + ang_off)
                for i in range(count):
                    t = i / (count - 1)
                    ang = base_ang - spread / 2 + spread * t
                    projectiles.append(BossProjectile(
                        self.x, self.y,
                        math.cos(ang) * 5.8, math.sin(ang) * 5.8,
                        dim=self.dim if k % 2 == 0 else (DIM_DREAM if self.dim == DIM_REAL else DIM_REAL),
                        radius=12, life=220, kind="crescent", dmg=1
                    ))
        elif phase == 3:
            for dx in (-300, 0, 300):
                tx = max(self.ax_left + 100, min(self.ax_right - 100, player.rect.centerx + dx))
                self._tg_beam_vertical(tx, beams, telegraphs, dim=DIM_REAL, duration=55, width=85, dmg=2)
        elif phase == 4:
            for f in [fr for fr in self.fragments if not fr.dead]:
                for i in range(14):
                    a = i * math.tau / 14
                    projectiles.append(BossProjectile(
                        f.x, f.y, math.cos(a) * 5.5, math.sin(a) * 5.5,
                        dim=f.dim, radius=10, life=200, kind="orb", dmg=1,
                        color=(Pal.MOON_GLOW if f.dim == DIM_REAL else (255, 160, 220))
                    ))
                f.dead = True
        elif phase == 5:
            pass

    def _update_transition(self, player, beams, projectiles, rings, telegraphs, particles):
        self.transition_t += 1
        if self.transition_t >= 110:
            self.phase = self.next_phase
            self.state = "fighting"
            self.transition_t = 0
            self.attack_timer = 60
            self.subattack_timer = 40
            self.gaster_timer = 70
            self.dim_timer = 100
            self.fragments = []
            # Remise à zéro des patterns rotatifs
            self.p1_step = 0
            self.p2_step = 0
            self.p3_step = 0
            self.p4_sub_step = 0
            self.p5_step = 0
            self.attacks_since_judgment = 0
            self.game.announce_phase(PHASE_NAMES[self.phase])
            if self.phase == 5:
                self.game.start_slowmo(30)

    def _drift_to(self, tx, ty, speed=1.4):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy) + 1e-6
        if d > 1:
            self.x += dx / d * min(speed, d)
            self.y += dy / d * min(speed, d)

    def take_dmg(self, dmg, current_dim, particles):
        if self.state in ("intro", "transition"): return 0
        if self.last_resort_active: return 0   # invincible pendant Derniers Recours
        if self.phase == 4:
            return 0
        if self.phase == 2 and current_dim != self.dim:
            return 0
        actual = dmg
        if self.phase == 5:
            actual = int(dmg * 1.6) + 1
        self.hp -= actual
        if self.hp < 0: self.hp = 0
        self.hit_flash = 8
        if self.hp == 0 and self.phase == 5:
            self.dead = True
        return actual

    def draw(self, surf, cam, current_dim):
        if self.phase == 4:
            for f in self.fragments:
                if not f.dead:
                    f.draw(surf, cam, current_dim)
            cx, cy = int(self.cx - cam[0]), int(self.cy - 60 - cam[1])
            s = pygame.Surface((140, 140), pygame.SRCALPHA)
            pygame.draw.circle(s, (*Pal.MOON_LIGHT, 70), (70, 70), 50)
            surf.blit(s, (cx - 70, cy - 70))
            return

        cx = int(self.x - cam[0])
        cy = int(self.y + self.float_offset - cam[1])

        glow_col = Pal.MOON_GLOW
        if self.phase == 2:
            glow_col = Pal.MOON_GLOW if self.dim == DIM_REAL else (255, 180, 220)
        elif self.phase == 5:
            glow_col = (180, 50, 140) if not self.final_form else (255, 30, 60)
        s = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(s, (*glow_col, 50), (self.radius * 2, self.radius * 2), self.radius * 2)
        pygame.draw.circle(s, (*glow_col, 80), (self.radius * 2, self.radius * 2), int(self.radius * 1.4))
        surf.blit(s, (cx - self.radius * 2, cy - self.radius * 2))

        if self._moon_sprite:
            # ── Dessin via sprite ──
            sprite = self._moon_sprite.copy()

            # Tinte selon la phase — BLEND_RGB_ADD : ne touche PAS l'alpha,
            # les pixels transparents restent transparents (pas de carré noir)
            tint = pygame.Surface(sprite.get_size())  # pas SRCALPHA : RGB seulement
            apply_tint = False
            if self.phase == 3:
                tint.fill((10, 10, 28))        # Éclipse : bleu sombre (30,30,80 * 90/255)
                apply_tint = True
            elif self.phase == 5:
                if self.final_form:
                    tint.fill((102, 0, 15))    # Final form : rouge sang (200,0,30 * 130/255)
                else:
                    tint.fill((46, 4, 28))     # Phase 5 : violet sombre (130,10,80 * 90/255)
                apply_tint = True
            elif self.phase == 2 and self.dim == DIM_DREAM:
                tint.fill((19, 0, 14))         # Dimension rêve : rose (80,0,60 * 60/255)
                apply_tint = True
            if apply_tint:
                sprite.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

            # Flash de hit : overlay blanc — BLEND_RGB_ADD uniquement
            if self.hit_flash > 0:
                flash_val = min(220, self.hit_flash * 22)
                flash = pygame.Surface(sprite.get_size())
                flash.fill((flash_val, flash_val, flash_val))
                sprite.blit(flash, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

            surf.blit(sprite, (cx - self.radius, cy - self.radius))
        else:
            # ── Fallback procédural (si le sprite est absent) ──
            col_main = Pal.MOON_LIGHT
            if self.phase == 2:
                col_main = Pal.MOON_LIGHT if self.dim == DIM_REAL else (255, 220, 240)
            elif self.phase == 3:
                col_main = (200, 200, 230)
            elif self.phase == 5:
                col_main = (180, 50, 110) if not self.final_form else (220, 10, 50)
            if self.hit_flash > 0:
                col_main = (255, 230, 230)
            pygame.draw.circle(surf, col_main, (cx, cy), self.radius)
            crater_col = Pal.MOON_DARK if self.phase != 5 else (50, 10, 30)
            pygame.draw.circle(surf, crater_col, (cx + 18, cy + 8), 10)
            pygame.draw.circle(surf, crater_col, (cx - 22, cy - 14), 8)
            pygame.draw.circle(surf, crater_col, (cx - 6, cy + 24), 6)
            pygame.draw.circle(surf, crater_col, (cx + 30, cy - 22), 4)

        # Fissures (phase 4+) dessinées par-dessus le sprite
        if self.phase >= 4:
            pygame.draw.line(surf, (30, 5, 20), (cx - 30, cy - 10), (cx + 10, cy + 18), 2)
            pygame.draw.line(surf, (30, 5, 20), (cx + 4, cy - 32), (cx + 20, cy - 4), 2)

        self._draw_face(surf, cx, cy)

    def _draw_face(self, surf, cx, cy):
        ex_off, ey_off = self.eye_offset
        eye_y = cy - 6 + int(ey_off)
        eye_left_x = cx - 16 + int(ex_off)
        eye_right_x = cx + 16 + int(ex_off)
        face = self.face_state
        if face == "calm":
            pygame.draw.line(surf, Pal.UI_DARK, (cx - 24, eye_y), (cx - 14, eye_y - 4), 3)
            pygame.draw.line(surf, Pal.UI_DARK, (cx + 14, eye_y - 4), (cx + 24, eye_y), 3)
            pygame.draw.arc(surf, Pal.UI_DARK, (cx - 22, cy + 10, 44, 24),
                            math.radians(20), math.radians(160), 3)
        elif face == "tense":
            pygame.draw.line(surf, Pal.UI_DARK, (cx - 26, eye_y - 8), (cx - 12, eye_y), 4)
            pygame.draw.line(surf, Pal.UI_DARK, (cx + 12, eye_y), (cx + 26, eye_y - 8), 4)
            pygame.draw.line(surf, Pal.UI_DARK, (cx - 14, cy + 18), (cx + 14, cy + 18), 3)
        elif face == "open":
            # Yeux : iris brillant + pupille noire + reflet
            for ex in (eye_left_x, eye_right_x):
                pygame.draw.circle(surf, (200, 40, 70), (ex, eye_y), 10)
                pygame.draw.circle(surf, Pal.UI_DARK, (ex, eye_y), 7)
                pygame.draw.circle(surf, (255, 200, 100), (ex - 2, eye_y - 2), 2)
            # Bouche : gouffre + crocs triangulaires
            mouth_x = cx - 19
            mouth_y = cy + 10
            mouth_w = 38
            mouth_h = 22
            pygame.draw.ellipse(surf, (6, 0, 14), (mouth_x, mouth_y, mouth_w, mouth_h))
            pygame.draw.ellipse(surf, (38, 10, 30),
                                (mouth_x + 2, mouth_y + 2, mouth_w - 4, mouth_h - 4), 1)
            upper_y = mouth_y + 2
            for i in range(5):
                tt = (i + 0.5) / 5
                fx = mouth_x + 4 + (mouth_w - 8) * tt
                fang_h = 11 if i % 2 == 0 else 7
                pygame.draw.polygon(surf, (245, 240, 220),
                                    [(int(fx - 2.5), upper_y),
                                     (int(fx + 2.5), upper_y),
                                     (int(fx), upper_y + fang_h)])
                pygame.draw.line(surf, (200, 180, 170),
                                 (int(fx - 1.2), upper_y + 1),
                                 (int(fx), upper_y + fang_h - 1), 1)
            lower_y = mouth_y + mouth_h - 2
            for i in range(3):
                tt = (i + 0.5) / 3
                fx = mouth_x + 9 + (mouth_w - 18) * tt
                pygame.draw.polygon(surf, (245, 240, 220),
                                    [(int(fx - 2), lower_y),
                                     (int(fx + 2), lower_y),
                                     (int(fx), lower_y - 8)])
        elif face == "crack":
            pygame.draw.line(surf, Pal.UI_DARK, (cx - 28, eye_y - 4), (cx - 12, eye_y - 4), 4)
            pygame.draw.line(surf, Pal.UI_DARK, (cx + 12, eye_y - 4), (cx + 28, eye_y - 4), 4)
            pygame.draw.arc(surf, Pal.UI_DARK, (cx - 26, cy + 10, 52, 24),
                            math.radians(200), math.radians(340), 3)
            pygame.draw.line(surf, (255, 255, 255), (cx - 16, eye_y + 2), (cx - 16, eye_y + 14), 2)
        elif face == "rage":
            pygame.draw.line(surf, (255, 40, 70), (cx - 30, eye_y - 14), (cx - 8, eye_y + 4), 5)
            pygame.draw.line(surf, (255, 40, 70), (cx + 8, eye_y + 4), (cx + 30, eye_y - 14), 5)
            pygame.draw.circle(surf, (255, 220, 210), (eye_left_x + 3, eye_y - 6), 3)
            pygame.draw.circle(surf, (255, 220, 210), (eye_right_x - 3, eye_y - 6), 3)
            mouth_x = cx - 22
            mouth_y = cy + 13
            mouth_w = 44
            mouth_h = 14
            pygame.draw.polygon(surf, (8, 0, 14),
                                [(mouth_x, mouth_y),
                                 (mouth_x + mouth_w, mouth_y),
                                 (mouth_x + mouth_w - 4, mouth_y + mouth_h),
                                 (mouth_x + 4, mouth_y + mouth_h)])
            for i in range(7):
                tt = (i + 0.5) / 7
                fx = mouth_x + 4 + (mouth_w - 8) * tt
                fang_h = 9 if i % 2 == 0 else 6
                pygame.draw.polygon(surf, (245, 235, 215),
                                    [(int(fx - 2), mouth_y),
                                     (int(fx + 2), mouth_y),
                                     (int(fx), mouth_y + fang_h)])
            for i in range(5):
                tt = (i + 0.5) / 5
                fx = mouth_x + 8 + (mouth_w - 16) * tt
                pygame.draw.polygon(surf, (245, 235, 215),
                                    [(int(fx - 1.5), mouth_y + mouth_h),
                                     (int(fx + 1.5), mouth_y + mouth_h),
                                     (int(fx), mouth_y + mouth_h - 5)])

    def hit_targets(self, current_dim):
        if self.state in ("intro", "transition"):
            return []
        if self.phase == 4:
            return [f for f in self.fragments if not f.dead and f.dim == current_dim]
        if self.phase == 2 and current_dim != self.dim:
            return []
        class _T:
            def __init__(s, r): s.rect = r
        return [_T(self.rect)]

    def get_pull(self):
        if self.state == "fighting" and self.phase == 2:
            return (self.x, self.y, 0.14)
        return (None, None, 0.0)


# ---------------------------------------------------------------------------
# Hub & Arena
# ---------------------------------------------------------------------------

class Portal:
    def __init__(self, x, y, label, target, available=True):
        self.rect = pygame.Rect(x, y, 80, 110)
        self.label = label
        self.target = target
        self.available = available
        self.t = 0.0

    def update(self):
        self.t += 0.05

    def draw(self, surf, cam, current_dim, font):
        r = self.rect.move(-cam[0], -cam[1])
        col_inner = (40, 20, 60) if self.available else (30, 25, 40)
        col_outer = pal_accent(current_dim) if self.available else (90, 70, 110)
        pygame.draw.ellipse(surf, col_inner, r)
        pygame.draw.ellipse(surf, col_outer, r, 4)
        cx, cy = r.center
        for i in range(4):
            ang = self.t + i * math.pi / 2
            px = cx + math.cos(ang) * (r.w * 0.25)
            py = cy + math.sin(ang) * (r.h * 0.25)
            pygame.draw.circle(surf, col_outer, (int(px), int(py)), 5)
        icon = {"MOON": "☾", "SUN": "☼", "BLACKHOLE": "●"}.get(self.target, "?")
        s = font.render(icon, True, col_outer)
        surf.blit(s, s.get_rect(center=(cx, cy)))
        lbl = font.render(self.label + ("" if self.available else "  (à venir)"),
                          True, Pal.UI if self.available else Pal.UI_DIM)
        surf.blit(lbl, lbl.get_rect(midtop=(cx, r.bottom + 8)))


def make_hub():
    platforms = []
    ground_y = 560
    platforms.append(Platform(-200, ground_y, 2400, 200))
    platforms.append(Platform(180, 470, 140, 22))
    platforms.append(Platform(420, 400, 140, 22))
    platforms.append(Platform(680, 330, 200, 22))
    platforms.append(Platform(960, 400, 140, 22))
    platforms.append(Platform(1180, 470, 140, 22))
    platforms.append(Platform(560, 250, 100, 18, dim_only=DIM_DREAM))
    platforms.append(Platform(820, 200, 100, 18, dim_only=DIM_REAL))
    platforms.append(Platform(1380, 380, 120, 20, dim_only=DIM_DREAM))
    platforms.append(Platform(60, 380, 100, 20, dim_only=DIM_REAL))
    platforms.append(Platform(-200, 0, 80, 760))
    platforms.append(Platform(1700, 0, 80, 760))
    portals = [
        Portal(280, ground_y - 110, "LA LUNE", "MOON", available=True),
        Portal(740, ground_y - 110, "LE SOLEIL", "SUN", available=False),
        Portal(1240, ground_y - 110, "LE TROU NOIR", "BLACKHOLE", available=False),
    ]
    return platforms, portals, (140, ground_y - 44)


def make_moon_arena():
    platforms = []
    arena_left = -200
    arena_right = 1500
    ground_y = 600
    platforms.append(Platform(arena_left, ground_y, arena_right - arena_left + 200, 200))
    platforms.append(Platform(120, 470, 220, 18))
    platforms.append(Platform(940, 470, 220, 18))
    platforms.append(Platform(540, 360, 200, 18))
    platforms.append(Platform(360, 250, 140, 18, dim_only=DIM_REAL))
    platforms.append(Platform(780, 250, 140, 18, dim_only=DIM_DREAM))
    platforms.append(Platform(-220, -200, 100, 1100))
    platforms.append(Platform(1500, -200, 100, 1100))
    return platforms, (140, ground_y - 44)


class StarField:
    def __init__(self, count=80):
        self.stars = [(random.uniform(0, WIDTH * 2), random.uniform(0, HEIGHT),
                       random.uniform(0.1, 0.6), random.uniform(1, 3))
                      for _ in range(count)]
        self.t = 0.0

    def update(self):
        self.t += 1

    def draw(self, surf, cam, dim):
        col = pal_star(dim)
        for sx, sy, par, size in self.stars:
            x = (sx - cam[0] * par) % (WIDTH + 40) - 20
            y = (sy - cam[1] * par * 0.3) % (HEIGHT + 40) - 20
            tw = 0.5 + 0.5 * math.sin(self.t * 0.05 + sx)
            r = max(1, int(size * (0.6 + 0.4 * tw)))
            c = tuple(max(0, min(255, int(c * (0.6 + 0.4 * tw)))) for c in col)
            pygame.draw.circle(surf, c, (int(x), int(y)), r)


# ---------------------------------------------------------------------------
# GAME
# ---------------------------------------------------------------------------

STATE_TITLE = "title"
STATE_HUB = "hub"
STATE_MOON = "moon"
STATE_VICTORY = "victory"
STATE_GAMEOVER = "gameover"


class Game:
    def __init__(self):
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        self.fullscreen = False
        # SCALED demande un renderer GPU. Si dispo on l'utilise (rendering pixel-perfect),
        # sinon fallback sur le mode classique.
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Dreamspawn — Prototype v3")
        self.clock = pygame.time.Clock()

        self.font_big = pygame.font.SysFont("georgia", 64, bold=True)
        self.font_med = pygame.font.SysFont("georgia", 28, bold=True)
        self.font_sm = pygame.font.SysFont("georgia", 18)
        self.font_icon = pygame.font.SysFont("dejavusans", 28, bold=True)
        self.font_announce = pygame.font.SysFont("georgia", 56, bold=True)
        self.font_dmg = pygame.font.SysFont("georgia", 22, bold=True)

        self.state = STATE_TITLE
        self.particles = []
        self.projectiles_boss = []
        self.beams = []
        self.rings = []
        self.telegraphs = []
        self.arrows = []
        self.damage_numbers = []
        self.starfield = StarField()
        self.dust = DustField(60, bounds=(-200, 0, 1500, 720))

        # Background images avec parallax
        _base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        def _load_bg(name, w=WIDTH, h=HEIGHT):
            try:
                img = pygame.image.load(os.path.join(_base_dir, name)).convert_alpha()
                return pygame.transform.scale(img, (w, h))
            except Exception:
                return None
        # Couche 0 : ciel de base (statique)
        self.bg_sky        = _load_bg("bg_sky.png")
        # Couche 1 : nuages lointains (parallax lent)
        self.bg_clouds_back  = _load_bg("bg_clouds_back.png",  WIDTH + 300, HEIGHT)
        # Couche 2 : nuages proches (parallax rapide)
        self.bg_clouds_front = _load_bg("bg_clouds_front.png", WIDTH + 500, HEIGHT)

        self.cam = [0, 0]
        self.shake = 0
        self.shake_strength = 0
        self.slowmo = 0

        self.player = None
        self.platforms = []
        self.portals = []
        self.boss = None
        self.frame = 0

        self.announce_text = ""
        self.announce_t = 0
        self.announce_max = 110

        self.show_controls_popup = False
        self.title_pulse_t = 0

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        try:
            if self.fullscreen:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT),
                                                      pygame.FULLSCREEN | pygame.SCALED)
            else:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
        except pygame.error:
            # Fallback sans SCALED si l'environnement ne le supporte pas
            flags = pygame.FULLSCREEN if self.fullscreen else 0
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    def reset_to_title(self):
        self.state = STATE_TITLE
        self.particles = []
        self.projectiles_boss = []
        self.beams = []
        self.rings = []
        self.telegraphs = []
        self.arrows = []
        self.damage_numbers = []

    def start_hub(self):
        self.particles.clear()
        self.projectiles_boss.clear()
        self.beams.clear()
        self.rings.clear()
        self.telegraphs.clear()
        self.arrows.clear()
        self.damage_numbers.clear()
        self.platforms, self.portals, spawn = make_hub()
        self.player = Player(*spawn)
        self.cam = [0, 0]
        self.state = STATE_HUB

    def start_moon(self):
        self.particles.clear()
        self.projectiles_boss.clear()
        self.beams.clear()
        self.rings.clear()
        self.telegraphs.clear()
        self.arrows.clear()
        self.damage_numbers.clear()
        self.platforms, spawn = make_moon_arena()
        self.player = Player(*spawn)
        self.boss = MoonBoss(640, 360, self)
        self.cam = [0, 0]
        self.state = STATE_MOON

    def add_shake(self, strength, frames=10):
        self.shake = max(self.shake, frames)
        self.shake_strength = max(self.shake_strength, strength)

    def start_slowmo(self, frames):
        self.slowmo = max(self.slowmo, frames)

    def announce_phase(self, text):
        self.announce_text = text
        self.announce_t = self.announce_max

    def update_camera(self, target_rect, bounds=None):
        target_x = target_rect.centerx - WIDTH // 2
        target_y = target_rect.centery - HEIGHT // 2 - 60
        self.cam[0] += (target_x - self.cam[0]) * 0.10
        self.cam[1] += (target_y - self.cam[1]) * 0.10
        if bounds:
            self.cam[0] = max(bounds[0], min(bounds[2] - WIDTH, self.cam[0]))
            self.cam[1] = max(bounds[1], min(bounds[3] - HEIGHT, self.cam[1]))
        if self.shake > 0:
            self.shake -= 1
            self.cam[0] += random.uniform(-self.shake_strength, self.shake_strength)
            self.cam[1] += random.uniform(-self.shake_strength, self.shake_strength)
            if self.shake == 0: self.shake_strength = 0

    def run(self):
        running = True
        while running:
            self.frame += 1
            self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        if self.state == STATE_TITLE:
                            running = False
                        else:
                            self.reset_to_title()
                    elif event.key == pygame.K_F11 or event.key == pygame.K_f:
                        # F11 (Windows) ET F (universel, Mac n'intercepte pas)
                        self.toggle_fullscreen()
                    elif event.key == pygame.K_RETURN and self.state == STATE_TITLE:
                        self.start_hub()
                    elif event.key == pygame.K_c and self.state == STATE_TITLE:
                        self.show_controls_popup = not self.show_controls_popup
                    elif event.key == pygame.K_r and self.state in (STATE_GAMEOVER, STATE_VICTORY):
                        self.start_hub()
                    elif event.key == pygame.K_SPACE and self.state in (STATE_HUB, STATE_MOON):
                        self.player.press_jump(self.particles)
                    elif event.key in (pygame.K_a, pygame.K_LSHIFT, pygame.K_RSHIFT) and self.state in (STATE_HUB, STATE_MOON):
                        if self.player.try_dash(self.particles) and self.state == STATE_MOON and self.boss:
                            self._check_parry()
                elif event.type == pygame.KEYUP:
                    if event.key == pygame.K_SPACE and self.state in (STATE_HUB, STATE_MOON):
                        self.player.release_jump()
                elif event.type == pygame.MOUSEBUTTONDOWN and self.state in (STATE_HUB, STATE_MOON):
                    if event.button == 1:
                        mx, my = event.pos
                        a = self.player.fire_bow(mx, my, self.cam)
                        if a: self.arrows.append(a)

            do_update = True
            if self.slowmo > 0:
                self.slowmo -= 1
                if self.frame % 2 != 0:
                    do_update = False

            if self.state == STATE_TITLE:
                self.title_pulse_t += 1
                self.draw_title()
            elif self.state == STATE_HUB:
                if do_update: self.update_hub()
                self.draw_world(in_arena=False)
                self.draw_hub_overlay()
            elif self.state == STATE_MOON:
                if do_update: self.update_moon()
                self.draw_world(in_arena=True)
                self.draw_boss_ui()
                self.draw_announce()
            elif self.state == STATE_GAMEOVER:
                self.draw_world(in_arena=(self.boss is not None))
                self.draw_gameover()
            elif self.state == STATE_VICTORY:
                self.draw_world(in_arena=True)
                self.draw_victory()

            pygame.display.flip()

        pygame.quit()

    def _check_parry(self):
        if not self.boss: return
        for proj in self.projectiles_boss:
            if proj.parry and not proj.dead and proj.dim == self.player.dimension:
                if proj.rect.colliderect(self.player.rect.inflate(20, 20)):
                    self.boss.parry_hit(self.particles)
                    proj.dead = True
                    self.damage_numbers.append(
                        DamageNumber(self.boss.x, self.boss.y - 40, "PARRY!", (255, 130, 200), self.font_dmg))
                    self.add_shake(8, 12)
                    return

    def update_hub(self):
        keys = pygame.key.get_pressed()
        self.player.update(keys, self.platforms, self.particles)
        for p in self.portals: p.update()
        for portal in self.portals:
            if portal.rect.colliderect(self.player.rect):
                if portal.available and portal.target == "MOON":
                    self.start_moon()
                    return
        for part in self.particles: part.update()
        self.particles[:] = [p for p in self.particles if p.alive()]
        self.update_camera(self.player.rect, bounds=(-150, -200, 1700, 800))
        self.starfield.update()
        self.dust.update()

    def _check_dream_timeout(self):
        """Expulse le joueur du rêve après DREAM_MAX_STAY frames + anim de fissure."""
        if (self.player.dimension == DIM_DREAM
                and self.player.dream_stay_t >= DREAM_MAX_STAY):
            self.player.dimension = DIM_REAL
            self.player.dream_stay_t = 0
            self.player.swap_cooldown = SWAP_COOLDOWN
            cx, cy = self.player.rect.center
            burst(self.particles, cx, cy, 60, Pal.D_ACCENT, 10.0, 50, 0.0, 5)
            burst(self.particles, cx, cy, 30, (255, 255, 255), 7.0, 35, 0.0, 4)
            self.add_shake(18, 25)

    def update_moon(self):
        keys = pygame.key.get_pressed()
        pull_x, pull_y, pull_force = (None, None, 0.0)
        if self.boss:
            pull_x, pull_y, pull_force = self.boss.get_pull()
        self.player.update(keys, self.platforms, self.particles,
                           pull_x=pull_x, pull_y=pull_y, pull_force=pull_force)
        self._check_dream_timeout()
        if self.boss:
            self.boss.update(self.player, self.beams, self.projectiles_boss,
                             self.rings, self.telegraphs, self.particles)

        for tg in self.telegraphs: tg.update()
        self.telegraphs[:] = [t for t in self.telegraphs if not t.dead]

        for b in self.beams: b.update()
        for r in self.rings: r.update()
        for a in self.arrows: a.update()
        for proj in self.projectiles_boss: proj.update()

        # Beams → player (b.dmg, hits_any_dim ignore le filtre de dim)
        for b in self.beams:
            if (b.hits_any_dim or b.dim == self.player.dimension) and b.rect.colliderect(self.player.rect):
                if self.player.hurt(b.dmg):
                    self.add_shake(8 + b.dmg * 4, 10 + b.dmg * 3)
                    burst(self.particles, self.player.rect.centerx, self.player.rect.centery,
                          24 + b.dmg * 8, Pal.HP_FILL, 5.0, 28, 0.15, 4)

        # Rings → player
        for r in self.rings:
            if (r.hits_any_dim or r.dim == self.player.dimension) and r.hits(self.player.rect):
                if self.player.hurt(r.dmg):
                    self.add_shake(5 + r.dmg * 2, 6 + r.dmg * 2)

        # Projectiles → player (utilise proj.dmg = 2 par défaut)
        for proj in self.projectiles_boss:
            if (proj.hits_any_dim or proj.dim == self.player.dimension) and proj.rect.colliderect(self.player.rect):
                if self.player.hurt(proj.dmg):
                    self.add_shake(6 + proj.dmg * 2, 8 + proj.dmg * 2)
                    burst(self.particles, self.player.rect.centerx, self.player.rect.centery,
                          18 + proj.dmg * 4, Pal.HP_FILL, 5.0, 24, 0.15, 4)
                proj.dead = True

        # Arrows → boss
        if self.boss:
            targets = self.boss.hit_targets(self.player.dimension)
            for a in self.arrows:
                if a.dead: continue
                for tgt in targets:
                    if a.rect.colliderect(tgt.rect):
                        if isinstance(tgt, MoonFragment):
                            if tgt.hurt(a.dmg, self.player.dimension):
                                self.damage_numbers.append(
                                    DamageNumber(a.x, a.y - 20, str(a.dmg),
                                                 (255, 240, 240), self.font_dmg))
                                burst(self.particles, a.x, a.y, 12,
                                      pal_part(self.player.dimension), 4.0, 22, 0.1, 3)
                                self.add_shake(3, 4)
                        else:
                            dmg_done = self.boss.take_dmg(a.dmg, self.player.dimension, self.particles)
                            if dmg_done > 0:
                                self.damage_numbers.append(
                                    DamageNumber(a.x, a.y - 20, str(dmg_done),
                                                 (255, 240, 240), self.font_dmg))
                                burst(self.particles, a.x, a.y, 12,
                                      pal_part(self.player.dimension), 4.0, 22, 0.1, 3)
                                self.add_shake(3, 4)
                        if a.pierce > 0:
                            a.pierce -= 1
                        else:
                            a.dead = True
                        break

        # Arrows ↔ projectiles (les flèches peuvent annuler les projectiles
        # dual-dim peu importe la dimension du joueur)
        for proj in self.projectiles_boss:
            if proj.kind in ("crescent", "star") and not proj.parry:
                for a in self.arrows:
                    if a.dead: continue
                    if (proj.hits_any_dim or proj.dim == self.player.dimension) and a.rect.colliderect(proj.rect):
                        proj.dead = True
                        if a.dmg <= 2:
                            a.dead = True

        # Slice assignment — important pour préserver les references capturées
        self.projectiles_boss[:] = [p for p in self.projectiles_boss if not p.dead]
        self.arrows[:] = [a for a in self.arrows if not a.dead]
        self.beams[:] = [b for b in self.beams if not b.dead]
        self.rings[:] = [r for r in self.rings if not r.dead]
        for part in self.particles: part.update()
        self.particles[:] = [p for p in self.particles if p.alive()]
        for d in self.damage_numbers: d.update()
        self.damage_numbers[:] = [d for d in self.damage_numbers if d.alive()]
        if self.announce_t > 0: self.announce_t -= 1

        if self.player.hp <= 0:
            self.state = STATE_GAMEOVER
            burst(self.particles, self.player.rect.centerx, self.player.rect.centery,
                  60, Pal.HP_FILL, 8.0, 50, 0.0, 5)

        if self.boss and self.boss.dead:
            self.state = STATE_VICTORY
            self.player.score += 1500
            for _ in range(6):
                burst(self.particles, 640 + random.randint(-200, 200),
                      300 + random.randint(-150, 150),
                      40, pal_accent(self.player.dimension), 8.0, 60, 0.0, 5)

        self.update_camera(self.player.rect, bounds=(-220, -200, 1600, 800))
        self.starfield.update()
        self.dust.update()

    def draw_world(self, in_arena):
        dim = self.player.dimension if self.player else DIM_REAL

        # ── Couche 0 : ciel de base (statique) ──
        if self.bg_sky:
            self.screen.blit(self.bg_sky, (0, 0))
        else:
            # Fallback gradient procédural
            bg = pal_bg(dim); bg2 = pal_bg_far(dim)
            for y in range(0, HEIGHT, 4):
                t = y / HEIGHT
                c = (int(bg[0]*(1-t)+bg2[0]*t),
                     int(bg[1]*(1-t)+bg2[1]*t),
                     int(bg[2]*(1-t)+bg2[2]*t))
                pygame.draw.rect(self.screen, c, (0, y, WIDTH, 4))
            self.starfield.draw(self.screen, self.cam, dim)

        # ── Couche 1 : nuages lointains (parallax 15%) ──
        if self.bg_clouds_back:
            off_back = int(self.cam[0] * 0.15) % (WIDTH + 300)
            self.screen.blit(self.bg_clouds_back, (-off_back, 0))
            if off_back > 0:
                self.screen.blit(self.bg_clouds_back, (WIDTH + 300 - off_back, 0))

        # ── Couche 2 : nuages proches (parallax 30%) ──
        if self.bg_clouds_front:
            off_front = int(self.cam[0] * 0.30) % (WIDTH + 500)
            self.screen.blit(self.bg_clouds_front, (-off_front, 0))
            if off_front > 0:
                self.screen.blit(self.bg_clouds_front, (WIDTH + 500 - off_front, 0))

        # ── Overlay dimension rêve : teinte pastel ──
        if dim == DIM_DREAM:
            dream_ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            dream_ov.fill((220, 200, 255, 120))
            self.screen.blit(dream_ov, (0, 0))

        self.dust.draw(self.screen, self.cam, dim)
        fog = pal_fog(dim)
        fs = pygame.Surface((WIDTH, 200), pygame.SRCALPHA)
        for i in range(200):
            a = int(120 * (i / 200))
            pygame.draw.rect(fs, (*fog, a), (0, 200 - i, WIDTH, 1))
        self.screen.blit(fs, (0, HEIGHT - 200))

        for p in self.platforms:
            p.draw(self.screen, self.cam, dim)

        if self.state == STATE_HUB:
            for p in self.portals:
                p.draw(self.screen, self.cam, dim, self.font_icon)

        if in_arena and self.boss:
            self.boss.draw(self.screen, self.cam, dim)

        for tg in self.telegraphs:
            if tg.dim == dim:
                tg.draw(self.screen, self.cam)
            else:
                old = tg.color
                tg.color = (180, 180, 200)
                tg.draw(self.screen, self.cam)
                tg.color = old

        for b in self.beams:
            if b.hits_any_dim or b.dim == dim:
                b.draw(self.screen, self.cam)
            else:
                s = pygame.Surface(b.rect.size, pygame.SRCALPHA)
                s.fill((*b.color, 60))
                self.screen.blit(s, (b.rect.x - self.cam[0], b.rect.y - self.cam[1]))

        for r in self.rings:
            if r.hits_any_dim or r.dim == dim:
                r.draw(self.screen, self.cam)

        for proj in self.projectiles_boss:
            if proj.hits_any_dim or proj.dim == dim:
                proj.draw(self.screen, self.cam)
            else:
                tmp = pygame.Surface((proj.radius * 4 + 8, proj.radius * 4 + 8), pygame.SRCALPHA)
                col = proj.color
                pygame.draw.circle(tmp, (*col, 70),
                                   (proj.radius * 2 + 4, proj.radius * 2 + 4),
                                   proj.radius, 2)
                self.screen.blit(tmp,
                                 (int(proj.x) - proj.radius * 2 - 4 - self.cam[0],
                                  int(proj.y) - proj.radius * 2 - 4 - self.cam[1]))

        for a in self.arrows: a.draw(self.screen, self.cam)

        if in_arena and self.boss and self.boss.state == "fighting" and self.boss.phase == 3 and dim == DIM_REAL:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 245))   # quasi-noir en réalité seulement (rêve = visible)
            for (sx, sy, rd) in (
                (self.player.rect.centerx - self.cam[0], self.player.rect.centery - self.cam[1], 110),
                (int(self.boss.x - self.cam[0]), int(self.boss.y - self.cam[1]), 140)):
                pygame.draw.circle(overlay, (0, 0, 0, 0), (int(sx), int(sy)), int(rd))
            self.screen.blit(overlay, (0, 0))

        if self.player: self.player.draw(self.screen, self.cam)

        for part in self.particles: part.draw(self.screen, self.cam)

        for d in self.damage_numbers: d.draw(self.screen, self.cam)

        if self.player:
            self.draw_hud()
            if self.player.dimension == DIM_DREAM:
                self._draw_dream_warning()

    def _draw_dream_warning(self):
        """Fissures à l'écran quand le joueur approche la limite du rêve (20 sec)."""
        t = self.player.dream_stay_t / DREAM_MAX_STAY
        if t < 0.65: return
        intensity = min(1.0, (t - 0.65) / 0.35)
        alpha = int(255 * intensity)
        crack_col = (*Pal.D_ACCENT, alpha)
        s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Fissures depuis les 4 coins — générées une seule fois via seed stable
        rng = [
            ((0, 0),       [(80, 55), (45, 100), (110, 40), (30, 80), (65, 130)]),
            ((WIDTH, 0),   [(WIDTH-80, 55), (WIDTH-45, 100), (WIDTH-110, 40), (WIDTH-30, 80)]),
            ((0, HEIGHT),  [(80, HEIGHT-55), (45, HEIGHT-100), (110, HEIGHT-40)]),
            ((WIDTH, HEIGHT), [(WIDTH-80, HEIGHT-55), (WIDTH-45, HEIGHT-100), (WIDTH-110, HEIGHT-40)]),
        ]
        for origin, tips in rng:
            for tip in tips:
                pygame.draw.line(s, crack_col, origin, tip, max(1, int(2 * intensity)))
                # petites branches
                mid = ((origin[0] + tip[0]) // 2, (origin[1] + tip[1]) // 2)
                branch = (mid[0] + (tip[1] - origin[1]) // 3,
                          mid[1] - (tip[0] - origin[0]) // 3)
                pygame.draw.line(s, crack_col, mid, branch, 1)
        # Bordure rouge-violet qui pulse
        border_alpha = int(80 + 80 * math.sin(self.frame * 0.25) * intensity)
        pygame.draw.rect(s, (*Pal.D_ACCENT, border_alpha), (0, 0, WIDTH, HEIGHT), max(3, int(12 * intensity)))
        self.screen.blit(s, (0, 0))
        # Texte d'avertissement
        if intensity > 0.5:
            warn_a = int(200 * ((intensity - 0.5) / 0.5))
            w = self.font_sm.render("FISSURE INSTABLE — retour imminent", True, Pal.D_ACCENT)
            w.set_alpha(warn_a)
            self.screen.blit(w, w.get_rect(midbottom=(WIDTH // 2, HEIGHT - 6)))

    def draw_hud(self):
        x, y = 24, 20
        w = 240; h = 22
        pygame.draw.rect(self.screen, Pal.HP_BG, (x, y, w, h), border_radius=6)
        frac = max(0.0, self.player.hp / self.player.max_hp)
        pygame.draw.rect(self.screen, Pal.HP_FILL, (x, y, int(w * frac), h), border_radius=6)
        pygame.draw.rect(self.screen, Pal.UI, (x, y, w, h), 2, border_radius=6)
        hp_lbl = self.font_sm.render(f"HP  {self.player.hp}/{self.player.max_hp}", True, Pal.UI)
        self.screen.blit(hp_lbl, (x + 8, y - 1))

        lbl = "RÉALITÉ" if self.player.dimension == DIM_REAL else "RÊVE BRISÉ"
        col = pal_accent(self.player.dimension)
        d_surf = self.font_sm.render(lbl, True, col)
        self.screen.blit(d_surf, (x + 8, y + h + 4))   # sous la barre HP joueur

        cd_w = 220
        cd_x = WIDTH // 2 - cd_w // 2
        cd_y = 56
        pygame.draw.rect(self.screen, Pal.UI_BG, (cd_x, cd_y, cd_w, 8), border_radius=4)
        ready = self.player.swap_cooldown <= 0
        frac = 1.0 if ready else 1.0 - self.player.swap_cooldown / SWAP_COOLDOWN
        pygame.draw.rect(self.screen, col, (cd_x, cd_y, int(cd_w * frac), 8), border_radius=4)
        if ready:
            r_lbl = self.font_sm.render("FISSURE PRÊTE — triple saut", True, col)
            self.screen.blit(r_lbl, r_lbl.get_rect(midtop=(WIDTH // 2, cd_y + 12)))

        d_ready = self.player.dash_cooldown <= 0
        d_col = (255, 230, 130) if d_ready else (130, 100, 130)
        pygame.draw.circle(self.screen, d_col, (40, HEIGHT - 40), 12, 0 if d_ready else 2)
        d_l = self.font_sm.render("DASH (A)", True, d_col)
        self.screen.blit(d_l, (60, HEIGHT - 50))

        # Indicateur de cooldown d'arc (cercle en bas à droite)
        bow_ready = self.player.bow_cd <= 0
        b_col = Pal.ARROW if bow_ready else (140, 110, 60)
        pygame.draw.circle(self.screen, b_col, (WIDTH - 40, HEIGHT - 40),
                           12, 0 if bow_ready else 2)
        if not bow_ready:
            # arc de progression
            frac = 1.0 - self.player.bow_cd / BOW_COOLDOWN
            pygame.draw.arc(self.screen, Pal.ARROW,
                            (WIDTH - 56, HEIGHT - 56, 32, 32),
                            -math.pi / 2, -math.pi / 2 + math.tau * frac, 3)
        b_l = self.font_sm.render("ARC", True, b_col)
        self.screen.blit(b_l, (WIDTH - 80, HEIGHT - 50))

    def draw_boss_ui(self):
        if not self.boss: return
        bw, bh = 500, 14
        bx = WIDTH // 2 - bw // 2
        by = 14   # haut de l'écran, à la place du texte dimension

        # Couleur selon la phase
        if self.boss.phase == 5:
            col = (255, 30, 80) if self.boss.final_form else (200, 60, 120)
        elif self.boss.phase == 4: col = Pal.BOSS_HP_D
        elif self.boss.phase == 3: col = (160, 160, 220)
        else: col = Pal.BOSS_HP

        # Fond
        pygame.draw.rect(self.screen, Pal.BOSS_HP_BG, (bx, by, bw, bh), border_radius=6)
        # Remplissage par phase (s'anime 0→1 à chaque transition)
        frac = self.boss.display_bar_fraction()
        pygame.draw.rect(self.screen, col, (bx, by, int(bw * frac), bh), border_radius=6)
        # Contour
        pygame.draw.rect(self.screen, Pal.UI, (bx, by, bw, bh), 2, border_radius=6)

        # Nom au-dessus
        name = self.font_sm.render(f"LA LUNE  —  Phase {self.boss.phase}", True, Pal.UI)
        self.screen.blit(name, name.get_rect(midbottom=(WIDTH // 2, by - 2)))

        # Phase 2 : dimension vulnérable
        if self.boss.phase == 2 and self.boss.state == "fighting":
            dlbl = "Vulnérable : " + ("RÉALITÉ" if self.boss.dim == DIM_REAL else "RÊVE BRISÉ")
            dc = pal_accent(self.boss.dim)
            s = self.font_sm.render(dlbl, True, dc)
            self.screen.blit(s, s.get_rect(midtop=(WIDTH // 2, by + bh + 4)))

        # Derniers Recours : flash rouge pendant la séquence
        if self.boss.last_resort_active:
            pulse = int(180 + 75 * math.sin(self.frame * 0.22))
            w_surf = self.font_sm.render("⚠  DERNIERS RECOURS  ⚠", True, (255, 80, 20))
            w_surf.set_alpha(pulse)
            self.screen.blit(w_surf, w_surf.get_rect(midtop=(WIDTH // 2, by + bh + 4)))

    def draw_announce(self):
        if self.announce_t <= 0 or not self.announce_text: return
        t = self.announce_t / self.announce_max
        # Fondu propre : apparition sur les 15 premières frames, pleine opacité, disparition sur les 15 dernières
        if t > 0.85:
            fade = (1.0 - t) / 0.15   # fade in : 0 → 1
        elif t < 0.15:
            fade = t / 0.15            # fade out : 1 → 0
        else:
            fade = 1.0
        fade = max(0.0, min(1.0, fade))
        text = self.font_announce.render(self.announce_text, True, Pal.UI)
        text.set_alpha(int(255 * fade))
        band = pygame.Surface((WIDTH, 120), pygame.SRCALPHA)
        band.fill((10, 5, 20, int(140 * fade)))
        self.screen.blit(band, (0, HEIGHT // 2 - 60))
        self.screen.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        pygame.draw.line(self.screen, pal_accent(self.player.dimension if self.player else DIM_REAL),
                         (0, HEIGHT // 2 - 60), (WIDTH, HEIGHT // 2 - 60), 2)
        pygame.draw.line(self.screen, pal_accent(self.player.dimension if self.player else DIM_REAL),
                         (0, HEIGHT // 2 + 60), (WIDTH, HEIGHT // 2 + 60), 2)

    def draw_hub_overlay(self):
        tip = "Approche un portail. Espace x3 en l'air = fissure la réalité. A = dash. Clic G = tirer (anti-spam). F = plein écran."
        s = self.font_sm.render(tip, True, Pal.UI_DIM)
        self.screen.blit(s, s.get_rect(midbottom=(WIDTH // 2, HEIGHT - 16)))

    def draw_title(self):
        # Fond dégradé
        for y in range(0, HEIGHT, 4):
            t = y / HEIGHT
            c = (int(Pal.R_BG[0] * (1 - t) + Pal.R_BG_FAR[0] * t),
                 int(Pal.R_BG[1] * (1 - t) + Pal.R_BG_FAR[1] * t),
                 int(Pal.R_BG[2] * (1 - t) + Pal.R_BG_FAR[2] * t))
            pygame.draw.rect(self.screen, c, (0, y, WIDTH, 4))
        self.starfield.update()
        self.starfield.draw(self.screen, [0, 0], DIM_REAL)

        # Glow pulsé sur le titre
        pulse = 0.7 + 0.3 * math.sin(self.title_pulse_t * 0.04)
        title_surf = self.font_big.render("DREAMSPAWN", True, Pal.UI)
        glow_surf = self.font_big.render("DREAMSPAWN", True, (100, 60, 200))
        glow_surf.set_alpha(int(110 * pulse))
        tr = title_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80))
        for dx, dy in ((-4, 0), (4, 0), (0, -4), (0, 4), (-3, -3), (3, 3), (-3, 3), (3, -3)):
            self.screen.blit(glow_surf, (tr.x + dx, tr.y + dy))
        self.screen.blit(title_surf, tr)

        # Sous-titre
        sub = self.font_med.render("Brise la réalité. Tombe les rois du ciel.", True, Pal.UI_DIM)
        self.screen.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 16)))

        # Bouton démarrer
        start_lbl = self.font_med.render("ENTRÉE — commencer", True, Pal.UI)
        self.screen.blit(start_lbl, start_lbl.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))

        # Hint contrôles en bas
        hint_col = (180, 160, 220)
        hint = self.font_sm.render("[C]  Contrôles", True, hint_col)
        self.screen.blit(hint, hint.get_rect(midbottom=(WIDTH // 2, HEIGHT - 24)))

        # Popup contrôles
        if self.show_controls_popup:
            lines = [
                ("ESPACE",       "Saut  /  Double saut  /  3× en l'air = changer de dimension"),
                ("A  ou  MAJ",   "Dash  —  traverse les projectiles roses = PARRY"),
                ("Clic gauche",  "Tirer une flèche  (maintenir = charge)"),
                ("F  ou  F11",   "Plein écran"),
                ("ÉCHAP",        "Retour au titre / quitter"),
            ]
            pad = 28
            lh = 30
            panel_w = 680
            panel_h = pad * 2 + len(lines) * lh + 10
            panel_x = WIDTH // 2 - panel_w // 2
            panel_y = HEIGHT // 2 + 70
            panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
            panel.fill((12, 6, 28, 210))
            self.screen.blit(panel, (panel_x, panel_y))
            pygame.draw.rect(self.screen, (100, 60, 200),
                             (panel_x, panel_y, panel_w, panel_h), 2, border_radius=8)
            for i, (key, action) in enumerate(lines):
                ky = panel_y + pad + i * lh
                k_surf = self.font_sm.render(key, True, (200, 180, 255))
                a_surf = self.font_sm.render(action, True, Pal.UI_DIM)
                self.screen.blit(k_surf, (panel_x + 18, ky))
                self.screen.blit(a_surf, (panel_x + 190, ky))

    def draw_gameover(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 5, 18, 200))
        self.screen.blit(overlay, (0, 0))
        s = self.font_big.render("VOUS AVEZ PÉRI", True, Pal.HP_FILL)
        self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30)))
        t = self.font_med.render("R — réessayer    ÉCHAP — titre", True, Pal.UI)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))

    def draw_victory(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((245, 235, 252, 180))
        self.screen.blit(overlay, (0, 0))
        s = self.font_big.render("LA LUNE EST TOMBÉE", True, Pal.R_ACCENT)
        self.screen.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 30)))
        t = self.font_med.render(f"Score : {self.player.score}    R — retour au hub", True, Pal.UI_DARK)
        self.screen.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 40)))


def main():
    pygame.init()
    pygame.display.init()
    Game().run()
    sys.exit(0)


if __name__ == "__main__":
    main()
